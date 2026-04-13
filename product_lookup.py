"""
product_lookup.py  –  Fast product image lookup for packing staff
Drop into your picklist project root and add to navigation.

Employee reads SKU description from the printed label → types 2-3 words → sees product image.
All 1700 SKUs are cached on first load, so search is instant after that.

── CONFIGURE BELOW ──────────────────────────────────────────────────────────
Update PRODUCTS_COLLECTION and field names to match your Firestore schema.
"""

import streamlit as st
from firebase_utils import db          # your existing Firebase connection

# ── CONFIG: match your Firestore products collection ─────────────────────────
PRODUCTS_COLLECTION = "products"       # collection where SKU data lives
SKU_FIELD           = "sku"            # field for SKU code/id (or use doc ID)
NAME_FIELD          = "name"           # product name / description field
IMAGE_URL_FIELD     = "img_url"      # image URL field  (adjust if different)
USE_DOC_ID_AS_SKU   = False             # True if document ID IS the SKU
# ─────────────────────────────────────────────────────────────────────────────


# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=600, show_spinner="Loading product catalog…")
def load_all_products() -> list[dict]:
    """
    Loads entire products collection once and caches for 10 minutes.
    Returns list of {sku, name, image_url} dicts.
    """
    docs = db.collection(PRODUCTS_COLLECTION).stream()
    products = []
    for doc in docs:
        data = doc.to_dict() or {}
        sku       = doc.id if USE_DOC_ID_AS_SKU else data.get(SKU_FIELD, doc.id)
        name      = data.get(NAME_FIELD, "")
        image_url = data.get(IMAGE_URL_FIELD, "")
        if image_url:                  # only include products that have an image
            products.append({
                "sku":       sku,
                "name":      name,
                "image_url": image_url,
                # searchable text: combine SKU + name, lowercased
                "_search":   f"{sku} {name}".lower(),
            })
    return products


def fuzzy_search(products: list[dict], query: str, max_results: int = 12) -> list[dict]:
    """
    Simple multi-word search: all words in query must appear in the searchable text.
    Returns up to max_results matches.
    """
    if not query.strip():
        return []
    words = query.lower().split()
    results = [p for p in products if all(w in p["_search"] for w in words)]
    return results[:max_results]


# ── UI ────────────────────────────────────────────────────────────────────────

def render_product_lookup_panel():
    st.set_page_config(
        page_title="Product Lookup",
        page_icon="🔍",
        layout="centered",
    )

    # Mobile-first styles
    st.markdown("""
        <style>
            /* Large search input for fat fingers */
            .stTextInput > div > input {
                font-size: 1.2rem !important;
                height: 3.2rem !important;
                border-radius: 12px !important;
            }
            /* Product card grid */
            .product-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
                gap: 12px;
                margin-top: 8px;
            }
            .product-card {
                border: 1px solid #ddd;
                border-radius: 12px;
                overflow: hidden;
                background: white;
                box-shadow: 0 1px 4px rgba(0,0,0,0.08);
                text-align: center;
            }
            .product-card img {
                width: 100%;
                aspect-ratio: 1;
                object-fit: cover;
            }
            .product-card .label {
                padding: 6px 8px;
                font-size: 0.72rem;
                color: #333;
                line-height: 1.3;
                word-break: break-word;
            }
            .product-card .sku-badge {
                font-size: 0.65rem;
                color: #888;
                padding: 0 8px 6px;
            }
            /* No results message */
            .no-result {
                text-align: center;
                padding: 2rem;
                color: #888;
                font-size: 1rem;
            }
        </style>
    """, unsafe_allow_html=True)

    st.title("🔍 Product Lookup")

    # Load catalog (cached)
    products = load_all_products()
    total    = len(products)

    if total == 0:
        st.error("No products found. Check PRODUCTS_COLLECTION and IMAGE_URL_FIELD in config.")
        return

    st.caption(f"{total} products loaded · Type to search")

    # Search box — autofocus on mobile
    query = st.text_input(
        label="Search",
        placeholder="Type product name or SKU…",
        label_visibility="collapsed",
    )

    # Results
    if not query.strip():
        st.markdown('<div class="no-result">👆 Start typing to find a product</div>', unsafe_allow_html=True)
        return

    results = fuzzy_search(products, query)

    if not results:
        st.markdown('<div class="no-result">No match — try fewer or different words</div>', unsafe_allow_html=True)
        return

    # Render image cards — 3 per row on mobile
    cols_per_row = 3
    rows = [results[i:i+cols_per_row] for i in range(0, len(results), cols_per_row)]

    for row in rows:
        cols = st.columns(cols_per_row)
        for col, product in zip(cols, row):
            with col:
                st.markdown(
                    f"<div style='font-size:0.7 rem; text-align:center; color:#333; margin-top:2px;'>"
                    f"{product['name'][:40] + '…' if len(product['name']) > 40 else product['name']}"
                    f"</div>"
                    f"<div style='font-size:1rem; text-align:center; color:#999;'>{product['sku']}</div>",
                    unsafe_allow_html=True,
                )
                try:
                    st.image(product["image_url"], use_container_width=True)
                except Exception:
                    st.markdown("🖼️ No image")

    if len(results) == 12:
        st.caption("Showing top 12 results — type more words to narrow down")


if __name__ == "__main__":
    main()