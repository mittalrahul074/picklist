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
    get_returns_grouped_by_sku,
    accept_returns_by_sku,
    get_returns_from_db
)
import utils

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------
PARTY_STATUS_MAPPING = {
    "Kangan": "accepted_kangan",
    "RS": "accepted_rs"
}

RETURN_STATUS = "m_return"
SESSION_KEY_RETURN_DF = "return_df"
SESSION_KEY_FORCE_RELOAD = "force_reload_returns"
SESSION_KEY_PREFIX_QTY = "accept_qty_"

FIRESTORE_CONSISTENCY_DELAY = 0.8  # seconds

ACCEPTANCE_MODES = ["Accept One by One", "Accept All at Once"]
SESSION_KEY_ACCEPTANCE_MODE = "accept_returns_mode"


# -------------------------------------------------------------------
# Type Definitions
# -------------------------------------------------------------------
PageInfo = Dict[str, str]


# -------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------
def _get_page_configuration(party_filter: str) -> Optional[PageInfo]:
    """
    Determine the page configuration based on the selected party filter.
    
    Args:
        party_filter: The party filter value ("Kangan", "RS", or "Both")
    
    Returns:
        Dictionary containing page configuration or None if invalid party
    """
    if party_filter == "Both":
        st.error("Please select a party to proceed.")
        return None
    
    if party_filter not in PARTY_STATUS_MAPPING:
        st.error(f"Invalid party filter: {party_filter}")
        return None
    
    return {
        'page_head': "Accept Returns",
        'status': RETURN_STATUS,
        'new_status': PARTY_STATUS_MAPPING[party_filter],
    }


def _load_cancelled_data() -> pd.DataFrame:
    """
    Load cancelled data from the database with proper session state management.
    Handles force reload scenarios for data consistency.
    
    Returns:
        DataFrame containing pending returns
    """
    # Handle force reload flag
    if st.session_state.get(SESSION_KEY_FORCE_RELOAD, False):
        st.session_state.pop(SESSION_KEY_RETURN_DF, None)
        st.session_state[SESSION_KEY_FORCE_RELOAD] = False
    
    # Load data if not in session state
    if SESSION_KEY_RETURN_DF not in st.session_state:
        st.session_state[SESSION_KEY_RETURN_DF] = get_cancelled_from_db(RETURN_STATUS)
    
    return st.session_state[SESSION_KEY_RETURN_DF].copy()


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


def _initialize_quantity_key(sku: str, total_quantity: int) -> str:
    """
    Initialize and return the session state key for a SKU's quantity input.
    
    Args:
        sku: The SKU identifier
        total_quantity: The total available quantity for this SKU
    
    Returns:
        The session state key for this SKU's quantity
    """
    key = f"{SESSION_KEY_PREFIX_QTY}{sku}"
    
    if key not in st.session_state or st.session_state[key] != total_quantity:
        st.session_state[key] = total_quantity
    
    return key


def _process_return_acceptance(
    sku: str,
    quantity: int,
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
    st.session_state.pop(SESSION_KEY_RETURN_DF, None)
    
    try:
        processed_qty, processed_ids = accept_returns_by_sku(
            sku=sku,
            quantity_to_process=quantity,
            new_status=new_status,
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
    page_config = _get_page_configuration(party_filter)
    
    if page_config is None:
        return
    
    st.header("📦 Cancelled List")
    
    # Load and filter cancelled data
    cancelled_df = _load_cancelled_data()
    filtered_df = utils.get_party_filter_df(cancelled_df, party_filter)
    sku_groups = get_returns_grouped_by_sku(filtered_df)
    
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
        _render_sku_row(row, page_config, st.session_state.user_role)
        st.divider()


def _render_sku_row(row: pd.Series, page_config: PageInfo, user: str) -> None:
    """
    Render a single SKU row with acceptance controls.
    
    Args:
        row: Pandas Series containing SKU data
        page_config: Page configuration dictionary
        user: Current user identifier
    """
    sku = str(row["sku"])
    total_qty = int(row["total_returns"])
    
    col1, col2, col3 = st.columns([3, 2, 2])
    
    with col1:
        st.subheader(sku)
        st.caption(f"Available Returns: {total_qty}")
    
    with col2:
        qty_key = _initialize_quantity_key(sku, total_qty)
        quantity = st.number_input(
            "Qty to accept",
            min_value=1,
            max_value=total_qty,
            value=st.session_state[qty_key],
            key=qty_key
        )
    
    with col3:
        button_key = f"accept_{sku}"
        if st.button("✅ Accept", key=button_key, use_container_width=True):
            processed_qty, processed_ids = _process_return_acceptance(
                sku=sku,
                quantity=quantity,
                new_status=page_config["new_status"],
                user=user
            )
            _handle_acceptance_result(sku, processed_qty, processed_ids)
