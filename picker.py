import streamlit as st
import pandas as pd
from utils import get_swipe_card_html
from database import get_orders_grouped_by_sku, update_orders_for_sku, calculate_order_counts,get_orders_from_db
import time

def next_sku():
    st.session_state.current_index += 1
    if st.session_state.current_index >= len(st.session_state.sku_groups):
        st.session_state.current_index = 0

def pick_sku():
    """Mark the SKU as picked and move to next"""
    current_sku_group = st.session_state.sku_groups.iloc[st.session_state.current_index]
    sku = current_sku_group['sku']
    total_quantity = current_sku_group['total_quantity']

    processed_quantity, processed_order_ids = update_orders_for_sku(
        sku, 
        total_quantity, 
        'picked',
        st.session_state.user_role
    )
    
    if processed_quantity > 0:
        st.success(f"Picked {processed_quantity} units of {sku}!")
    
    time.sleep(0.5)  # UX delay
    next_sku()  # Move to next SKU

def render_picker_panel():
    # Main Picker Panel
    st.header("Order Picking")

    if "orders_df" not in st.session_state:
        st.session_state.orders_df = get_orders_from_db()  # Fetch only once

    if "sku_groups" not in st.session_state:
        st.session_state.sku_groups = get_orders_grouped_by_sku(st.session_state.orders_df, status='new')

    if "current_index" not in st.session_state:
        st.session_state.current_index = 0  # Ensure index is initialized

    sku_groups = st.session_state.sku_groups

    if sku_groups.empty:
        st.info("No orders available to pick. Please wait for the admin to upload orders.")
        st.stop()  # Prevent further execution

    # Display SKU details
    current_sku_group = sku_groups.iloc[st.session_state.current_index]
    sku = current_sku_group['sku']
    total_quantity = current_sku_group['total_quantity']
    order_count = current_sku_group['order_count']
    earliest_dispatch_date = current_sku_group['earliest_dispatch_date']

    # Display SKU card
    st.markdown(get_swipe_card_html({
        'sku': sku,
        'total_quantity': total_quantity,
        'order_count': order_count,
        'dispatch_date': earliest_dispatch_date
    }, 'pick'), unsafe_allow_html=True)

    # Buttons
    col1, col2 = st.columns(2)
    with col1:
        st.button("⬅️ Skip", key="skip_button", use_container_width=True, on_click=next_sku)

    with col2:
        st.button("Pick ➡️", key="pick_button", use_container_width=True, on_click=pick_sku)

    # Pick Quantity Adjustment
    st.markdown("---")
    st.subheader("Adjust Pick Quantity")

    pick_quantity = st.number_input(
        "Quantity to Pick", 
        min_value=1, 
        max_value=int(total_quantity), 
        value=int(total_quantity)
    )

    if st.button("Pick Adjusted Quantity", use_container_width=True):
        processed_quantity, processed_order_ids = update_orders_for_sku(
            sku, 
            pick_quantity, 
            'picked',
            st.session_state.user_role
        )

        if processed_quantity > 0:
            st.success(f"Picked {processed_quantity} units of {sku}!")

        time.sleep(0.5)
        next_sku()