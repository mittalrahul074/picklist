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
    
    if processed_quantity == -1:
        st.toast(
            f"❌ Not enough quantity left for SKU={sku}. "
            f"Someone already validated/picked these orders.",
            icon="⚠️"
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

        # SKU HEADER WITH CANCEL BUTTON
        sku_col, btn_col = st.columns([6, 2])

        with sku_col:
            st.subheader(f"{sl_no}. SKU: {sku}")
            st.caption(f"Total Quantity: {total_qty}")

        with btn_col:
            cancel_unique_key = f"cancel_{sku}_{sl_no}"
            if st.button("❌ Cancel", key=cancel_unique_key):
                # Cancel all picked orders for this SKU
                cancel_qty, order_ids = update_orders_for_sku(
                    sku,
                    total_qty,  # large number = cancel all picked units
                    "cancelled",
                    st.session_state.user_role
                )

                if cancel_qty > 0:
                    st.toast(f"🚫 Cancelled {cancel_qty} units for {sku}.", icon="⚠️")
                else:
                    st.toast(f"No picked orders left to cancel for {sku}.", icon="⚠️")

                # Clear cached orders
                if "orders_df" in st.session_state:
                    del st.session_state["orders_df"]

                time.sleep(0.5)
                st.rerun()


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
                "qty_input_hidden_label_" + key,
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
        print("DEBUG: Submit Validation clicked")
        st.write("DEBUG: Starting validation...")

        for idx, row in sku_groups.iterrows():
            sku = row["sku"]
            dispatch_list = row["dispatch_breakdown"]
            print(f"DEBUG: Processing SKU={sku}, row_index={idx}, dispatch_list_type={type(dispatch_list)}")

            if isinstance(dispatch_list, str):
                dispatch_list = json.loads(dispatch_list)
                print(f"DEBUG: Parsed dispatch_list JSON for SKU={sku}: {dispatch_list}")

            for d_idx, dispatch in enumerate(dispatch_list):
                key = f"{sku}_{d_idx}"
                qty = st.session_state.validation_inputs.get(key, 0)
                print(f"DEBUG: SKU={sku} d_idx={d_idx} key={key} qty_input={qty}")

                if qty <= 0:
                    print(f"DEBUG: Skipping SKU={sku} d_idx={d_idx} because qty={qty}")
                    continue

                processed_qty, _ = update_orders_for_sku(
                    sku,
                    qty,
                    page_info['new_status'],
                    st.session_state.user_role
                )
                if processed_qty == -1:
                    st.toast(
                        f"❌ Not enough quantity left for SKU={sku}. "
                        f"Someone already validated/picked these orders.",
                        icon="⚠️"
                    )
                    time.sleep(0.8)
                    keys_to_clear = ["orders_df"]
                    for k in keys_to_clear:
                        if k in st.session_state:
                            del st.session_state[k]
                    st.rerun()
                print(f"DEBUG: update_orders_for_sku returned processed_qty={processed_qty} for SKU={sku}, requested_qty={qty}")
                total_validated += processed_qty

        print(f"DEBUG: Total validated computed = {total_validated}")

        st.success(f"Validated {total_validated} items successfully!")
        time.sleep(1)
        st.rerun()
