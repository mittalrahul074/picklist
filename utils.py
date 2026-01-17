import io
import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import streamlit as st

from database import get_orders_from_db, update_status
from db.orders import bulk_update_status

# -------------------------------------------------------------------
# Logging Configuration
# -------------------------------------------------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

DATE_OUTPUT_FORMAT = "%d-%m-%Y"

# -------------------------------------------------------------------
# Session Helpers
# -------------------------------------------------------------------
def next_sku() -> None:
    """Move to next SKU safely."""
    st.session_state.current_index = (
        st.session_state.current_index + 1
    ) % len(st.session_state.sku_groups)


# -------------------------------------------------------------------
# SKU / Party Filtering
# -------------------------------------------------------------------
def get_party_filter_df(df: pd.DataFrame, party: str) -> pd.DataFrame:
    """
    Filter orders based on SKU prefix rules.
    """
    if "sku" not in df.columns:
        logger.warning("SKU column missing. Skipping party filter.")
        return df

    sku_series = df["sku"].astype(str)

    if party == "Kangan":
        return df[sku_series.str.startswith(("K", "L"), na=False)]

    if party == "RS":
        return df[~sku_series.str.startswith(("K", "L"), na=False)]

    return df


# -------------------------------------------------------------------
# Date Utilities
# -------------------------------------------------------------------
def normalize_and_shift(raw: str) -> Optional[str]:
    """
    Normalize date to DD-MM-YYYY and add 2 days.
    """
    raw = str(raw).strip()

    formats = ("%Y-%m-%d", "%d-%m-%Y")
    for fmt in formats:
        try:
            dt = datetime.strptime(raw, fmt) + timedelta(days=2)
            return dt.strftime(DATE_OUTPUT_FORMAT)
        except ValueError:
            continue

    return None


# -------------------------------------------------------------------
# File Readers
# -------------------------------------------------------------------
def read_uploaded_file(file_buffer, platform: str) -> pd.DataFrame:
    """
    Read CSV / Excel safely.
    """
    filename = file_buffer.name.lower()

    if filename.endswith(".csv"):
        return pd.read_csv(file_buffer, dtype=str, keep_default_na=False)

    return pd.read_excel(file_buffer, dtype=str, keep_default_na=False)


# -------------------------------------------------------------------
# Meesho Processing
# -------------------------------------------------------------------
def process_meesho_orders(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    Process Meesho order file.
    """
    if df.shape[1] < 8:
        st.error("Invalid Meesho file format.")
        return None

    status_col = df.iloc[:, 0].astype(str).str.lower().str.strip()

    # --- Cancelled / Shipped / Delivered ---
    cancelled_mask = status_col.isin({"cancelled", "shipped", "delivered"})
    cancelled_df = df[cancelled_mask]

    if not cancelled_df.empty:
        bulk_update_status(cancelled_df, platform="meesho")

    # --- Pending Orders ---
    pending_mask = status_col.isin({"pending", "ready_to_ship"})
    pending_df = df[pending_mask]

    if pending_df.empty:
        st.info("No pending orders found.")
        return None

    orders = pd.DataFrame({
        "order_id": pending_df.iloc[:, 1].astype(str),
        "sku": pending_df.iloc[:, 5].astype(str).str.upper().str.strip(),
        "quantity": pd.to_numeric(
            pending_df.iloc[:, 7], errors="coerce"
        ).fillna(1).astype(int),
        "dispatch_date": pending_df.iloc[:, 2].apply(normalize_and_shift),
        "status": "new"
    })

    return clean_orders_df(orders)


# -------------------------------------------------------------------
# Flipkart Processing
# -------------------------------------------------------------------
def process_flipkart_orders(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    Process Flipkart order file.
    """
    orders = pd.DataFrame({
        "order_id": df.iloc[:, 3],
        "sku": df.iloc[:, 8].astype(str).str.upper().str.strip(),
        "quantity": pd.to_numeric(df.iloc[:, 18], errors="coerce").fillna(1),
        "dispatch_date": pd.to_datetime(
            df.iloc[:, 28],
            format="%b %d, %Y %H:%M:%S",
            errors="coerce"
        ).dt.strftime(DATE_OUTPUT_FORMAT),
        "status": "new"
    })

    return clean_orders_df(orders)


# -------------------------------------------------------------------
# Common Cleanup
# -------------------------------------------------------------------
def clean_orders_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove invalid rows and normalize schema.
    """
    df.dropna(subset=["order_id", "sku", "dispatch_date"], inplace=True)
    df = df[~df["sku"].isin({"", "NAN"})]
    df["quantity"] = df["quantity"].astype(int)

    if df.empty:
        st.warning("No valid orders after cleaning.")
        return pd.DataFrame(
            columns=["order_id", "sku", "quantity", "dispatch_date", "status"]
        )

    logger.info("Processed %d valid orders", len(df))
    return df


# -------------------------------------------------------------------
# Main Extractor
# -------------------------------------------------------------------
def extract_order_data(file_buffer, platform: str) -> Optional[pd.DataFrame]:
    """
    Platform-agnostic entry point.
    """
    try:
        df = read_uploaded_file(file_buffer, platform)

        if platform == "meesho":
            return process_meesho_orders(df)

        if platform == "flipkart":
            return process_flipkart_orders(df)

        st.error("Unsupported platform selected.")
        return None

    except Exception as exc:
        logger.exception("Order extraction failed")
        st.error("Failed to process file.")
        return None

def get_swipe_card_html(order_data, action_type):
    """
    Generate HTML for a swipeable card showing dispatch-wise breakdown.
    """
    sku = order_data['sku']
    total_quantity = order_data['total_quantity']
    order_count = order_data.get('order_count', 1)
    breakdown = order_data.get('dispatch_date', [])

    if action_type == 'pick':
        card_id = f"pick_card_{sku}"
    else:
        card_id = f"validate_card_{sku}"

    # Build dispatch table rows
    dispatch_table_rows = ""
    for row in breakdown:
        dispatch_table_rows += f"""<tr><td>{row['date']}</td><td style="text-align:right;">{row['quantity']}</td></tr>"""

    # Final HTML
    html = f"""<div class="swipe-card" id="{card_id}" data-sku="{sku}" style='
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 12px;
            margin-bottom: 12px;
            user-select: text;
            -webkit-user-select: text;
            -moz-user-select: text;
         '><div class="card-content"><h3>SKU: {sku}</h3><table style="width:100%; margin: 10px 0; border-collapse: collapse;"><thead><tr><th style="text-align:left;">Dispatch Date</th><th style="text-align:right;">Quantity</th></tr></thead><tbody>{dispatch_table_rows}</tbody></table><p style="font-size: 1.3rem; text-align: right; margin-top: 8px;"><strong>Total Quantity:</strong> {total_quantity}</p></div></div>"""
    return html

def export_orders_to_excel():
    if "orders_df" not in st.session_state:
        st.session_state.orders_df = get_orders_from_db()
    """
    Export orders to Excel file for download
    
    Args:
        db_path: Path to the database
    
    Returns:
        Excel file as bytes or None if no orders exist
    """
    # Get latest orders from database
    orders_df = st.session_state.orders_df
    
    if orders_df.empty:
        return None

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        orders_df.to_excel(writer, index=False)

    return output.getvalue()


# -------------------------------------------------------------------
# UI HTML Card
# -------------------------------------------------------------------
def get_swipe_card_html(order_data: dict, action_type: str) -> str:
    """
    Generate swipe card HTML.
    """
    rows = "".join(
        f"<tr><td>{r['date']}</td><td align='right'>{r['quantity']}</td></tr>"
        for r in order_data.get("dispatch_date", [])
    )

    return f"""
    <div class="swipe-card" data-sku="{order_data['sku']}">
        <h3>SKU: {order_data['sku']}</h3>
        <table width="100%">
            <tr><th>Dispatch</th><th align="right">Qty</th></tr>
            {rows}
        </table>
        <p align="right"><b>Total:</b> {order_data['total_quantity']}</p>
    </div>
    """
