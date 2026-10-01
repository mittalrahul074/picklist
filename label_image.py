"""
label_image.py  –  Add product images to Flipkart shipping label PDFs
Drop this file into your picklist project and add it to your navigation.

Requirements (add to requirements.txt if not already present):
    pymupdf>=1.24.0
    pdfplumber>=0.10.0
    requests>=2.31.0
    Pillow>=10.0.0

Usage:
    Upload a Flipkart multi-label PDF.
    The app auto-extracts Order IDs → fetches SKU + image from Firebase → stamps image on each label.
    Download the enhanced PDF.
"""

import streamlit as st
import fitz  # PyMuPDF
import pdfplumber
import re
import requests
import io
import tempfile
import os
from PIL import Image

# ── Reuse your existing Firebase connection ──────────────────────────────────
from firebase_utils import db  # your existing module

# ── CONFIGURE: adjust collection/field names to match your Firestore ─────────
ORDERS_COLLECTION   = "orders"     # collection where order_id is the document ID
SKU_FIELD           = "sku"        # field name inside the order document

# ⚠️  UPDATE THIS to match your products collection
# Option A – products collection where doc ID = SKU, with an image_url field
PRODUCTS_COLLECTION = "products"
IMAGE_URL_FIELD     = "image_url"  # or "image", "img_url" etc.

# Option B – if image is stored directly on the order doc, set this to True
IMAGE_ON_ORDER_DOC  = False
ORDER_IMAGE_FIELD   = "image_url"  # only used if IMAGE_ON_ORDER_DOC = True
# ─────────────────────────────────────────────────────────────────────────────

ORDER_ID_PATTERN = re.compile(r'\b(OD\d{15,20})\b')


# ── Firebase helpers ──────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def fetch_image_url(order_id: str) -> tuple[str | None, str | None]:
    """Returns (sku, image_url) for an order_id. Cached for 5 minutes."""
    try:
        order_doc = db.collection(ORDERS_COLLECTION).document(order_id).get()
        if not order_doc.exists:
            return None, None
        order_data = order_doc.to_dict()
        sku = order_data.get(SKU_FIELD)

        if IMAGE_ON_ORDER_DOC:
            return sku, order_data.get(ORDER_IMAGE_FIELD)

        if not sku:
            return None, None

        sku_lower = sku.lower()
        product_doc = db.collection(PRODUCTS_COLLECTION).document(sku_lower).get()
        if not product_doc.exists:
            return sku, None
        return sku, product_doc.to_dict().get(IMAGE_URL_FIELD)

    except Exception as e:
        st.warning(f"Firebase error for {order_id}: {e}")
        return None, None


def download_image(url: str) -> bytes | None:
    """Download an image from URL and return as bytes."""
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        return resp.content
    except Exception:
        return None


# ── PDF processing ────────────────────────────────────────────────────────────

def extract_order_id(page_text: str) -> str | None:
    """Extract OD... order ID from label text."""
    match = ORDER_ID_PATTERN.search(page_text)
    return match.group(1) if match else None


def stamp_image_on_page(page: fitz.Page, img_bytes: bytes) -> bool:
    """
    Insert a small product image into the label page.
    Targets the blank space in the SKU description row.
    Returns True if successful.
    """
    try:
        rect = page.rect
        w, h = rect.width, rect.height

        # Flipkart label: SKU row is roughly 65-85% down the page
        # Place image in the right portion of the description cell
        img_size  = min(w, h) * 0.18   # ~18% of the smaller dimension
        margin    = w * 0.02

        x1 = w - img_size - margin
        y1 = h * 0.64
        x2 = x1 + img_size
        y2 = y1 + img_size

        img_rect = fitz.Rect(x1, y1, x2, y2)

        # Convert image to PNG for reliable embedding
        pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        png_buf = io.BytesIO()
        pil_img.save(png_buf, format="PNG")
        png_bytes = png_buf.getvalue()

        page.insert_image(img_rect, stream=png_bytes, keep_proportion=True)

        # Draw a thin border around the image
        page.draw_rect(img_rect, color=(0.7, 0.7, 0.7), width=0.5)
        return True

    except Exception as e:
        return False


def process_pdf(uploaded_bytes: bytes) -> tuple[bytes, list[dict]]:
    """
    Process every page of the label PDF:
      1. Extract Order ID
      2. Fetch image URL from Firebase
      3. Stamp image onto the page
    Returns (modified_pdf_bytes, results_log).
    """
    results = []

    # --- Extract text (pdfplumber is better for text positions) ---
    page_texts = []
    with pdfplumber.open(io.BytesIO(uploaded_bytes)) as plumber_pdf:
        for p in plumber_pdf.pages:
            page_texts.append(p.extract_text() or "")

    # --- Modify PDF (PyMuPDF for image stamping) ---
    doc = fitz.open(stream=uploaded_bytes, filetype="pdf")

    for i, page in enumerate(doc):
        text = page_texts[i] if i < len(page_texts) else ""
        order_id = extract_order_id(text)

        if not order_id:
            results.append({"page": i + 1, "order_id": "—", "sku": "—", "status": "⚠️ Order ID not found"})
            continue

        sku, image_url = fetch_image_url(order_id)

        if not image_url:
            results.append({"page": i + 1, "order_id": order_id, "sku": sku or "—", "status": "⚠️ No image in DB"})
            continue

        img_bytes = download_image(image_url)
        if not img_bytes:
            results.append({"page": i + 1, "order_id": order_id, "sku": sku, "status": "❌ Image download failed"})
            continue

        ok = stamp_image_on_page(page, img_bytes)
        status = "✅ Image added" if ok else "❌ Stamp failed"
        results.append({"page": i + 1, "order_id": order_id, "sku": sku, "status": status})

    output_buf = io.BytesIO()
    doc.save(output_buf)
    doc.close()
    return output_buf.getvalue(), results


# ── Streamlit UI ──────────────────────────────────────────────────────────────

def render_label_stamper_panel():
    st.set_page_config(
        page_title="Label Image Stamper",
        page_icon="🖨️",
        layout="centered",
    )

    # Mobile-friendly CSS
    st.markdown("""
        <style>
            .stButton > button {
                width: 100%;
                height: 3.2rem;
                font-size: 1.1rem;
                border-radius: 10px;
            }
            .stDownloadButton > button {
                width: 100%;
                height: 3.5rem;
                font-size: 1.15rem;
                background-color: #1a73e8;
                color: white;
                border-radius: 10px;
            }
            .result-box {
                padding: 0.4rem 0.8rem;
                border-radius: 8px;
                margin: 4px 0;
                font-size: 0.9rem;
            }
        </style>
    """, unsafe_allow_html=True)

    st.title("🖨️ Label Image Stamper")
    st.caption("Upload Flipkart label PDF → auto-adds product images → download for printing")

    uploaded = st.file_uploader(
        "📂 Upload Label PDF",
        type=["pdf"],
        help="Download the label PDF from Flipkart seller panel and upload here",
    )

    if uploaded is None:
        st.info("👆 Upload a label PDF to get started")
        return

    pdf_bytes = uploaded.read()
    total_pages = len(list(pdfplumber.open(io.BytesIO(pdf_bytes)).pages))
    st.success(f"📄 Loaded **{total_pages} label(s)**")

    if st.button("🚀 Process Labels", type="primary"):
        with st.spinner(f"Processing {total_pages} labels… fetching images…"):
            modified_pdf, results = process_pdf(pdf_bytes)

        # Results table
        ok_count = sum(1 for r in results if "✅" in r["status"])
        st.markdown(f"### Results: {ok_count}/{total_pages} labels stamped")

        for r in results:
            color = "#d4edda" if "✅" in r["status"] else "#fff3cd" if "⚠️" in r["status"] else "#f8d7da"
            st.markdown(
                f'<div class="result-box" style="background:{color}">'
                f'<b>Page {r["page"]}</b> &nbsp;|&nbsp; {r["order_id"]} &nbsp;|&nbsp; '
                f'SKU: {r["sku"]} &nbsp;|&nbsp; {r["status"]}'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.divider()
        st.download_button(
            label="⬇️ Download Enhanced PDF",
            data=modified_pdf,
            file_name=f"labels_with_images_{uploaded.name}",
            mime="application/pdf",
        )
        st.caption("Print this PDF directly. Product images are stamped on each label.")


if __name__ == "__main__":
    main()
