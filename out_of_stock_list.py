"""
Accept Returns Module

This module handles the UI and business logic for accepting returns in the order management system.
Allows users to process pending returns grouped by SKU with party-based filtering.

Author: Order Management System Team
"""

from typing import Dict, Optional, Tuple, List
import streamlit as st
import pandas as pd
import time

from database import (
    accept_cancelled,
    accept_returns_by_sku,
    get_out_of_stock_from_db
)
from db.out_of_stock import accept_out_of_stock
import utils

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------

SESSION_KEY_OUT_OF_STOCK_DF = "out_of_stock_df"
SESSION_KEY_FORCE_RELOAD = "force_reload_out_of_stock_list"

FIRESTORE_CONSISTENCY_DELAY = 0.8  # seconds


# -------------------------------------------------------------------
# Type Definitions
# -------------------------------------------------------------------
PageInfo = Dict[str, str]


# -------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------


def _load_out_of_stock_data() -> pd.DataFrame:
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
        st.session_state[SESSION_KEY_OUT_OF_STOCK_DF] = get_out_of_stock_from_db()

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
    user: str
) -> Tuple[int, List[str]]:
    """
    Process the acceptance of out of stock items for a specific SKU.
    
    Args:
        safe_sku: The safe SKU identifier
        new_status: The new status value to set
        user: The user performing the action
        new_status: The status to set after acceptance
        user: The user performing the action
    
    Returns:
        Tuple of (processed_quantity, processed_ids)
    """
    # Clear cached data before processing to ensure consistency
    st.session_state.pop(SESSION_KEY_OUT_OF_STOCK_DF, None)
    
    try:
        processed_qty, processed_ids = accept_out_of_stock(
            safe_sku=safe_sku,
            sku=sku,
            new_status=new_status,
            user=user
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
def render_out_of_stock_list_panel() -> None:
    """
    Render the main out of stock list panel interface.
    
    This function orchestrates the entire out of stock list workflow:
    - Validates party selection
    - Loads and filters return data
    - Groups returns by SKU
    - Renders the UI with acceptance controls
    - Handles user interactions
    """
    party_filter = st.session_state.get("party_filter")
        
    st.header("📦 Out of Stock List")
    
    # Load and filter cancelled data
    if party_filter:
        out_of_stock_df = utils.get_party_filter_df(_load_out_of_stock_data(),party_filter)
    else:
        out_of_stock_df = _load_out_of_stock_data()
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
        _render_sku_row(row, st.session_state.user_role)
        st.divider()


def _render_sku_row(row: pd.Series, user: str) -> None:
    """
    Render a single SKU row with acceptance controls.
    
    Args:
        row: Pandas Series containing SKU data
        user: Current user identifier
    """
    sku = str(row["sku"])    
    col1, col3 = st.columns([5, 2])    
    with col1:
        st.subheader(sku)
    with col3:
        safe_sku = str(row["safe_sku"])
        button_key = f"accept_{safe_sku}"
        if st.button("✅ Accept", key=button_key, use_container_width=True):
            processed_qty, processed_ids = _process_out_of_stock_acceptance(
                safe_sku=safe_sku,
                sku = sku,
                new_status=1,
                user=user
            )
            _handle_acceptance_result(sku, processed_qty, processed_ids)
