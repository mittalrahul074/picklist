"""
Accept Returns Module

This module handles the UI and business logic for accepting returns in the order management system.
Allows users to process pending returns grouped by SKU with party-based filtering.

Author: Order Management System Team
"""

from typing import Dict, Optional, Tuple, List
from auth import logout_user
from db.orders import get_product_image_url
import streamlit as st
import pandas as pd
import time

from database import (
    accept_cancelled,
    accept_returns_by_sku,
    get_out_of_stock_from_db
)
from db.out_of_stock import accept_out_of_stock, delete_out_of_stock
import utils

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------

SESSION_KEY_OUT_OF_STOCK_DF = "out_of_stock_df"
SESSION_KEY_FORCE_RELOAD = "force_reload_out_of_stock_list"

FIRESTORE_CONSISTENCY_DELAY = 0.8  # seconds
party_filter = st.session_state.get("party_filter")

# -------------------------------------------------------------------
# Type Definitions
# -------------------------------------------------------------------
PageInfo = Dict[str, str]


# -------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------


def _load_out_of_stock_data(user_type: int) -> pd.DataFrame:
    """
    Load out of stock data from the database with proper session state management.
    Handles force reload scenarios for data consistency.
    
    Returns:
        DataFrame containing pending returns
    """
    # Check if we need to force reload data (e.g. after processing returns)
    if st.session_state.get(SESSION_KEY_FORCE_RELOAD):
        print("🔄 Force reloading out of stock data from DB")
        st.session_state.pop(SESSION_KEY_OUT_OF_STOCK_DF, None)  # Clear cached data
        st.session_state.pop(SESSION_KEY_FORCE_RELOAD, None)  # Reset flag

    if SESSION_KEY_OUT_OF_STOCK_DF not in st.session_state:
        print("📥 Loading out of stock data from DB for the first time")
        st.session_state[SESSION_KEY_OUT_OF_STOCK_DF] = get_out_of_stock_from_db(user_type)

    print(f"📝 DEBUG: Loaded out of stock returns into session state")
    print(f"📝 DEBUG: {st.session_state[SESSION_KEY_OUT_OF_STOCK_DF]}")
    return st.session_state[SESSION_KEY_OUT_OF_STOCK_DF].copy()


def _cleanup_session_keys(current_skus: set) -> None:
    """
    Remove obsolete session state keys for SKUs that no longer exist.
    
    Args:
        current_skus: Set of SKUs that currently exist in the data
    """


def _process_out_of_stock_acceptance(
    safe_sku: str,
    sku: str,
    new_status: str,
    user: str,
    platform: str,
    user_type: int
) -> Tuple[int, List[str]]:
    """
    Process the acceptance of out of stock items for a specific SKU.
    
    Args:
        safe_sku: The safe SKU identifier
        new_status: The new status value to set
        user: The user performing the action
        platform: The platform for which to accept the items (e.g. "meesho", "flipkart")
        new_status: The status to set after acceptance
        user: The user performing the action
    
    Returns:
        Tuple of (processed_quantity, processed_ids)
    """
    if new_status == 2:
        delete_out_of_stock(sku)
        # clear session state to force fresh reload in UI layer
        st.session_state.pop(SESSION_KEY_OUT_OF_STOCK_DF, None)
        if party_filter:
            out_of_stock_df = utils.get_party_filter_df(_load_out_of_stock_data(user_type),party_filter)
        else:
            out_of_stock_df = _load_out_of_stock_data(user_type)
        return 0, []
    # Clear cached data before processing to ensure consistency
    st.session_state.pop(SESSION_KEY_OUT_OF_STOCK_DF, None)
    
    try:
        processed_qty, processed_ids = accept_out_of_stock(
            safe_sku=safe_sku,
            sku=sku,
            new_status=new_status,
            user=user,
            platform=platform
        )
        return processed_qty, processed_ids
    except Exception as e:
        st.error(f"Error processing out of stock items for {safe_sku}: {str(e)}")
        return 0, []

def _handle_acceptance_result(
    sku: str,
    processed_qty: int,
    processed_ids: List[str]
) -> None:
    """
    Handle the UI feedback and state management after return acceptance.
    
    Args:
        sku: The SKU identifier
        processed_qty: Number of returns processed
        processed_ids: List of processed return IDs
    """
    if processed_qty > 0 and processed_ids:
        st.success(f"✅ Accepted {len(processed_ids)} out of stock item(s) for {sku}")
    else:
        st.warning(
            f"⚠️ No out of stock items were processed for {sku}. "
            f"They may have been accepted by another user."
        )
    
    # Force reload on next render to reflect database changes
    st.session_state[SESSION_KEY_FORCE_RELOAD] = True
    
    # Allow Firestore eventual consistency to propagate
    time.sleep(FIRESTORE_CONSISTENCY_DELAY)
    st.rerun()

# -------------------------------------------------------------------
# Main Rendering Function
# -------------------------------------------------------------------
def render_out_of_stock_list_panel(user_type: int) -> None:
    """
    Render the main out of stock list panel interface.
    
    This function orchestrates the entire out of stock list workflow:
    - Validates party selection
    - Loads and filters return data
    - Groups returns by SKU
    - Renders the UI with acceptance controls
    - Handles user interactions
    """
    if user_type is None:
        st.error("User type not found. Please log in again.")
        print("❌ User type is missing in session state. Logging out for safety.")
        logout_user()
        st.rerun()

    st.header("📦 Out of Stock List")
    
    # Load and filter cancelled data
    if party_filter:
        out_of_stock_df = utils.get_party_filter_df(_load_out_of_stock_data(user_type),party_filter)
    else:
        out_of_stock_df = _load_out_of_stock_data(user_type)
    print(f"📝 DEBUG: Loaded {len(out_of_stock_df)} out of stock returns from DB")
    # Early return if no pending returns
    if out_of_stock_df.empty:
        st.info("No pending out of stock returns")
        return
    st.divider()
    
    # Cleanup obsolete session keys
    current_skus = {row["sku"] for _, row in out_of_stock_df.iterrows()}
    _cleanup_session_keys(current_skus)
    
    # Render each SKU group
    for _, row in out_of_stock_df.iterrows():
        _render_sku_row(row, st.session_state.user_role, user_type)
        st.divider()


def _render_sku_row(row: pd.Series, user: str, user_type: int) -> None:
    """
    Render a single SKU row with acceptance controls.
    
    Args:
        row: Pandas Series containing SKU data
        user: Current user identifier
        user_type: The type of the current user
    """
    sku = str(row["sku"])    
    col1, col3 = st.columns([5, 2])   
    # view image link if available
    if get_product_image_url(sku):
        with col1:
            # link to view image in new tab
            st.markdown(f"[🖼️ View Image]({get_product_image_url(sku)})")
    with col1:
        st.subheader(sku)
    with col3:
        if user_type == 2:
            #dont show accept and reject button for super admin
            st.write("Reported by:")
            st.write(row["reported_by"])
        else:
            safe_sku = str(row["safe_sku"])
            button_key = f"accept_{safe_sku}"
            if row["pending_platforms"] and "meesho" in row["pending_platforms"]:
                if st.button("✅Meesho Accept", key="m_" + button_key, use_container_width=True):
                    processed_qty, processed_ids = _process_out_of_stock_acceptance(
                        safe_sku=safe_sku,
                        sku = sku,
                        new_status=1,
                        user=user,
                        platform="meesho",
                        user_type=user_type
                    )
                    _handle_acceptance_result(sku, processed_qty, processed_ids)

            if row["pending_platforms"] and "flipkart" in row["pending_platforms"]:
                if st.button("✅ Flipkart Accept", key="f_" + button_key, use_container_width=True):
                    processed_qty, processed_ids = _process_out_of_stock_acceptance(
                        safe_sku=safe_sku,
                        sku = sku,
                        new_status=1,
                        user=user,
                        platform="flipkart",
                        user_type=user_type
                    )
                    _handle_acceptance_result(sku, processed_qty, processed_ids)

            if st.button("❌ Reject", key=f"reject_{safe_sku}", use_container_width=True):
                processed_qty, processed_ids = _process_out_of_stock_acceptance(
                    safe_sku=safe_sku,
                    sku = sku,
                    new_status=2,
                    user=user,
                    platform="",  # platform is not needed for rejection since it will delete the document
                    user_type=user_type
                )
