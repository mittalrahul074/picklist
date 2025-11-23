import streamlit as st
import pandas as pd
from utils import get_swipe_card_html,next_sku
from database import get_orders_grouped_by_sku, update_orders_for_sku, calculate_order_counts,get_orders_from_db
import time
import json
import utils

def get_page_info(page):
    return {
        'page_head': "Validation",
        'status': "picked",
        'to_do': "validate",
        'left': "Reject",
        'right': "Validate",
        'key_left': "reject_button",
        'key_right': "validate_button",
        'new_status': "validated"
    }

def pick_sku(page_info):
    """Mark the SKU as picked and move to next"""
    current_sku_group = st.session_state.sku_groups.iloc[st.session_state.current_index]
    sku = current_sku_group['sku']
    total_quantity = current_sku_group['total_quantity']

    processed_quantity, processed_order_ids = update_orders_for_sku(
        sku, 
        total_quantity, 
        page_info['new_status'],
        st.session_state.user_role
    )
    
    if processed_quantity > 0:
        st.success(f"{page_info['new_status']} {processed_quantity} units of {sku}!")
    
    time.sleep(0.5)  # UX delay
    # next_sku()  # Move to next SKU

def render_validator_panel():
    page_info = get_page_info("validator")
    st.header("Order Validation Panel")

    if "orders_df" not in st.session_state:
        st.session_state.orders_df = get_orders_from_db()

    df = st.session_state.orders_df
    party_filter = st.session_state.get("party_filter", "Both")
    df = utils.get_party_filter_df(df, party_filter)

    sku_groups = get_orders_grouped_by_sku(
        df,
        status=page_info['status']
    )

    if sku_groups.empty:
        st.info("No validation pending")
        return

    if "validation_inputs" not in st.session_state:
        st.session_state.validation_inputs = {}

    st.write(f"Total SKUs: **{len(sku_groups)}**")
    st.markdown("---")

    sl_no = 1

    for idx, row in sku_groups.iterrows():
        sku = row["sku"]
        total_qty = int(row["total_quantity"])

        # Parse dispatch list if JSON string
        dispatch_list = row["dispatch_breakdown"]
        if isinstance(dispatch_list, str):
            dispatch_list = json.loads(dispatch_list)

        st.subheader(f"{sl_no}. SKU: {sku}")
        st.caption(f"Total Quantity: {total_qty}")

        # ROW HEADER
        cols = st.columns([2, 2, 2])
        cols[0].write("📅 Dispatch Date")
        cols[1].write("Available Qty")
        cols[2].write("Qty Validated")

        # UI per dispatch date
        for d_idx, dispatch in enumerate(dispatch_list):
            date = dispatch["date"]
            max_qty = int(dispatch["quantity"])

            key = f"{sku}_{d_idx}"  # unique key

            if key not in st.session_state.validation_inputs:
                st.session_state.validation_inputs[key] = 0

            cols = st.columns([2, 2, 2])
            cols[0].write(date)
            cols[1].write(max_qty)

            # defalut input value will be max_qty

            input_val = cols[2].number_input(
                "",
                min_value=0,
                max_value=max_qty,
                value=max_qty,
                key=key
            )

            st.session_state.validation_inputs[key] = input_val

        st.markdown("---")
        sl_no += 1

    if st.button("Submit Validation", type="primary", use_container_width=True):
        total_validated = 0
        for idx, row in sku_groups.iterrows():
            sku = row["sku"]
            dispatch_list = row["dispatch_breakdown"]
            if isinstance(dispatch_list, str):
                dispatch_list = json.loads(dispatch_list)

            for d_idx, dispatch in enumerate(dispatch_list):
                key = f"{sku}_{d_idx}"
                qty = st.session_state.validation_inputs.get(key, 0)
                
                if qty > 0:
                    processed_qty, _ = update_orders_for_sku(
                        sku,
                        qty,
                        page_info['new_status'],
                        st.session_state.user_role
                    )
                    total_validated += processed_qty

        st.success(f"Validated {total_validated} items successfully!")
        time.sleep(1)
        st.rerun()
