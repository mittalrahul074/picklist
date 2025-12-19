import streamlit as st
import pandas as pd
from database import get_returns_grouped_by_sku, update_orders_for_sku, calculate_order_counts,get_returns_from_db
import time
import json
import utils

def get_page_info(page):
    user = st.session_state.party_filter
    if user == "Both":
        st.error("Please select a party to proceed.")
        return
    elif user == "Kangan":
        new_status = "accepted_kangan"
    elif user == "RS":
        new_status = "accepted_rs"
    return {
        'page_head': "Accept Returns",
        'status': "M_return",
        'new_status': new_status,
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

def render_accept_returns_panel():
    page_info = get_page_info("returns")
    st.header("📦 Accept Returns")

    if "return_df" not in st.session_state:
        st.session_state.return_df = get_returns_from_db()

    df = st.session_state.return_df
    df = utils.get_party_filter_df(df, st.session_state.party_filter)

    sku_groups = get_returns_grouped_by_sku(df)

    if sku_groups.empty:
        st.info("No pending returns")
        return

    st.write(f"Total SKUs: **{len(sku_groups)}**")
    st.divider()

    for idx, row in sku_groups.iterrows():
        sku = row["sku"]
        total_qty = int(row["total_returns"])

        col1, col2, col3 = st.columns([3, 2, 2])

        with col1:
            st.subheader(sku)
            st.caption(f"Available Returns: {total_qty}")

        key = f"accept_qty_{sku}"
        if key not in st.session_state:
            st.session_state[key] = total_qty

        with col2:
            qty = st.number_input(
                "Qty to accept",
                min_value=1,
                max_value=total_qty,
                value=total_qty,
                key=key
            )

        with col3:
            if st.button("✅ Accept", key=f"accept_{sku}", use_container_width=True):
                processed = accept_returns_by_sku(
                    sku=sku,
                    quantity=qty,
                    new_status=page_info["new_status"],
                    user=st.session_state.user_role
                )

                st.success(f"Accepted {processed} returns for {sku}")
                del st.session_state["return_df"]
                st.rerun()

        st.divider()
