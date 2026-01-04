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
    get_cancelled_from_db
)
import utils

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------

STATUS = "CANCELLED"
SESSION_KEY_CANCELLED_DF = "cancelled_df"
SESSION_KEY_FORCE_RELOAD = "force_reload_cancelled"
SESSION_KEY_PREFIX_QTY = "accept_qty_"

FIRESTORE_CONSISTENCY_DELAY = 0.8  # seconds


# -------------------------------------------------------------------
# Type Definitions
# -------------------------------------------------------------------
PageInfo = Dict[str, str]


# -------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------


def _load_cancelled_data() -> pd.DataFrame:
    """
    Load cancelled data from the database with proper session state management.
    Handles force reload scenarios for data consistency.
    
    Returns:
        DataFrame containing pending returns
    """
    # Handle force reload flag
    if st.session_state.get(SESSION_KEY_FORCE_RELOAD, False):
        st.session_state.pop(SESSION_KEY_CANCELLED_DF, None)
        st.session_state[SESSION_KEY_FORCE_RELOAD] = False
    
    # Load data if not in session state
    if SESSION_KEY_CANCELLED_DF not in st.session_state:
        st.session_state[SESSION_KEY_CANCELLED_DF] = get_cancelled_from_db(STATUS)
    print(f"📝 DEBUG: Loaded cancelled returns into session state")
    print(f"📝 DEBUG: {st.session_state[SESSION_KEY_CANCELLED_DF]}")
    return st.session_state[SESSION_KEY_CANCELLED_DF].copy()


def _cleanup_session_keys(current_skus: set) -> None:
    """
    Remove obsolete session state keys for SKUs that no longer exist.
    
    Args:
        current_skus: Set of SKUs that currently exist in the data
    """
    keys_to_remove = [
        key for key in st.session_state.keys()
        if key.startswith(SESSION_KEY_PREFIX_QTY)
        and key.replace(SESSION_KEY_PREFIX_QTY, "") not in current_skus
    ]
    
    for key in keys_to_remove:
        del st.session_state[key]


def _process_cancelled_acceptance(
    order_id: str,
    new_status: str,
    user: str
) -> Tuple[int, List[str]]:
    """
    Process the acceptance of returns for a specific SKU.
    
    Args:
        sku: The SKU identifier
        quantity: Number of returns to accept
        new_status: The status to set after acceptance
        user: The user performing the action
    
    Returns:
        Tuple of (processed_quantity, processed_ids)
    """
    # Clear cached data before processing to ensure consistency
    st.session_state.pop(SESSION_KEY_CANCELLED_DF, None)
    
    try:
        processed_qty, processed_ids = accept_cancelled(
            order_id=order_id,
            user=user
        )
        return processed_qty, processed_ids
    except Exception as e:
        st.error(f"Error processing returns for {sku}: {str(e)}")
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
        st.success(f"✅ Accepted {len(processed_ids)} return(s) for {sku}")
    else:
        st.warning(
            f"⚠️ No returns were processed for {sku}. "
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
def render_cancelled_list_panel() -> None:
    """
    Render the main cancelled list panel interface.
    
    This function orchestrates the entire cancelled list workflow:
    - Validates party selection
    - Loads and filters return data
    - Groups returns by SKU
    - Renders the UI with acceptance controls
    - Handles user interactions
    """
    party_filter = st.session_state.get("party_filter")
        
    st.header("📦 Cancelled List")
    
    # Load and filter cancelled data
    cancelled_df = _load_cancelled_data()
    sku_groups = cancelled_df
    print(f"📝 DEBUG: Loaded {(cancelled_df)} cancelled returns from DB")
    # Early return if no pending returns
    if sku_groups.empty:
        st.info("No pending returns")
        return
    
    # Display summary
    st.write(f"Total SKUs: **{len(sku_groups)}**")
    st.divider()
    
    # Cleanup obsolete session keys
    current_skus = {row["sku"] for _, row in sku_groups.iterrows()}
    _cleanup_session_keys(current_skus)
    
    # Render each SKU group
    for _, row in sku_groups.iterrows():
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
    order_id = str(row["order_id"])
    
    with col1:
        st.subheader(sku)
        quantity = int(row["quantity"])
        st.write(f"Pending Returns: **{quantity}**")    
    with col3:
        button_key = f"accept_{order_id}"
        if st.button("✅ Accept", key=button_key, use_container_width=True):
            processed_qty, processed_ids =_process_cancelled_acceptance(
                order_id=order_id,
                new_status="CANCELLED_ACCEPTED",
                user=user
            )
            _handle_acceptance_result(sku, processed_qty, processed_ids)
