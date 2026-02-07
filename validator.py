import streamlit as st
import pandas as pd
import database
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
    df = df[df["status"] == page_info['status']]

    user_list = sorted([u for u in df["picked_by"].dropna().unique()])

    user_list.insert(0, "All")
    current_filter = st.session_state.get("picked_by_filter", "All")

    if st.session_state.user_type != 1:  # Not a picker-only user 
        picked_by_filter = st.selectbox(
            "Show SKUs picked by:",
            options=user_list,
            index=user_list.index(current_filter) if current_filter in user_list else 0,
            key="picked_by_filter_select"
        )
    else: # picker-only user
        picked_by_filter = st.session_state.user_role
        st.info(f"Showing SKUs picked by you: {picked_by_filter}")
    if picked_by_filter != "All":
        df = df[df["picked_by"] == picked_by_filter]
    

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
        sku_col, btn_col,wng_btn,rmv_btn = st.columns([2,2,2, 2])

        with sku_col:
            img_url  = database.get_product_image_url(sku)
            st.subheader(f"{sl_no}. SKU: {sku}")
            # if img_url then show image with link, else just show SKU
            if img_url:
                st.markdown(f"[{sku}]({img_url})", unsafe_allow_html=True)
            else:
                st.write(sku)
            st.caption(f"Total Quantity: {total_qty}")

        with rmv_btn:
            rvm_unique_key = f"remove_{sku}_{sl_no}"
            if st.button("🗑️ Remove", key=rvm_unique_key):
                # Remove all picked orders for this SKU
                cancel_qty, order_ids = update_orders_for_sku(
                    sku,
                    total_qty,  # large number = remove all picked units
                    "new",
                    st.session_state.user_role
                )

                if cancel_qty > 0:
                    st.toast(f"🗑️ Removed {cancel_qty} units for {sku}.", icon="⚠️")
                else:
                    st.toast(f"No picked orders left to remove for {sku}.", icon="⚠️")

                # Clear cached orders
                if "orders_df" in st.session_state:
                    del st.session_state["orders_df"]

                time.sleep(0.5)
                st.rerun()

        if st.session_state.user_type != 1:  # Not a picker-only user 

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
            with wng_btn:
                wng_unique_key = f"wrong_{sku}_{sl_no}"
                if st.button("❌ Wrong", key=wng_unique_key):
                    # Cancel all picked orders for this SKU
                    cancel_qty, order_ids = update_orders_for_sku(
                        sku,
                        total_qty,  # large number = cancel all picked units
                        "wrong",
                        st.session_state.user_role
                    )

                    if cancel_qty > 0:
                        st.toast(f"🚫 Wrong {cancel_qty} units for {sku}.", icon="⚠️")
                    else:
                        st.toast(f"No picked orders left to wrong for {sku}.", icon="⚠️")

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

    if st.session_state.user_type != 1:  # Not a picker-only user 
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
                        st.session_state.orders_df = get_orders_from_db()
                    # print(f"DEBUG: update_orders_for_sku returned processed_qty={processed_qty} for SKU={sku}, requested_qty={qty}")
                    total_validated += processed_qty


            st.success(f"Validated {total_validated} items successfully!")
            st.session_state.orders_df = get_orders_from_db()  # Refresh orders
            time.sleep(1)
            st.rerun()
