import streamlit as st
from db.orders import load_orders
from utils import extract_order_data
from database import add_orders_to_db, calculate_order_counts

def process_upload(uploaded_file, platform):
    """Handle file upload end-to-end"""
    try:
        orders_df = extract_order_data(uploaded_file, platform)
        if orders_df is None or orders_df.empty:
            return False, "No valid data found in file"

        success, count = add_orders_to_db(orders_df, platform)
        if not success:
            return False, "Database insert failed"
    
        load_orders(force=True)
        return True, count

    except Exception as e:
        return False, str(e)
    
def get_filtered_orders(party_filter):
    """Apply party filter safely"""
    df = st.session_state.orders_df.copy()
    df["sku"] = df["sku"].astype(str).str.upper()

    if party_filter == "Kangan":
        df = df[df["sku"].str.startswith(("K", "L"))]
    elif party_filter == "RS":
        df = df[df["sku"].str.startswith("R")]

    return df

def get_order_stats():
    """Cached order statistics"""
    return calculate_order_counts()