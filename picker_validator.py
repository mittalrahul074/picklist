import streamlit as st
import pandas as pd
from utils import get_swipe_card_html,next_sku
from database import get_orders_grouped_by_sku, update_orders_for_sku, calculate_order_counts,get_orders_from_db
import time

def get_page_info(page):
    if page == "picker":
        return {
            'page_head': "Picking",
            'status': "new",
            'to_do': "pick",
            'left': "Skip",
            'right': "Pick",
            'key_left': "skip_button",
            'key_right': "pick_button",
            'new_status': "picked"
        }
    elif page == "validator":
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
    else:
        st.error("Invalid page.")
        st.stop()

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

def render_picker_validator_panel(which_page):
    # Main Picker Panel
    page_info = get_page_info(which_page)
    st.header(f"Order {page_info['page_head']}")

    if "orders_df" not in st.session_state:
        st.session_state.orders_df = get_orders_from_db()  # Fetch only once

    st.session_state.sku_groups = get_orders_grouped_by_sku(
        st.session_state.orders_df,
        status= page_info['status'])

    sku_groups = st.session_state.sku_groups

    st.subheader(f"{len(sku_groups)} SKUs to Pick")

    if "current_index" not in st.session_state:
        st.session_state.current_index = 0  # Ensure index is initialized
    elif st.session_state.current_index+1>len(sku_groups):
        st.session_state.current_index = 0

    if sku_groups.empty:
        st.info(f"No orders available to {st.session_state.page}. Please wait for the admin to upload orders.")
        st.stop()  # Prevent further execution

    # Display SKU details
    current_sku_group = sku_groups.iloc[st.session_state.current_index]
    sku = current_sku_group['sku']
    total_quantity = current_sku_group['total_quantity']
    order_count = current_sku_group['order_count']
    dispatch_date = current_sku_group['dispatch_breakdown']
    # Display SKU card
    st.markdown(get_swipe_card_html({
        'sku': sku,
        'total_quantity': total_quantity,
        'order_count': order_count,
        'dispatch_date': dispatch_date
    }, page_info['to_do']), unsafe_allow_html=True)

    # Buttons
    col1, col2 = st.columns(2)
    with col1:
        st.button(f"⬅️ {page_info['left']}", key=page_info['key_left'], use_container_width=True, on_click=next_sku)

    with col2:
        st.button(
            f"{page_info['right']} ➡️", 
            key=page_info['key_right'], 
            use_container_width=True, 
            on_click=pick_sku,
            kwargs={"page_info": page_info}
        )

    # Pick Quantity Adjustment
    st.markdown("---")
    st.subheader(f"Adjust {page_info['to_do']} Quantity")

    pick_quantity = st.number_input(
        f"Quantity to {page_info['to_do']}", 
        min_value=1, 
        max_value=int(total_quantity), 
        value=int(total_quantity)
    )
    print(pick_quantity)
    if st.button(f"{page_info['to_do']} Adjusted Quantity", use_container_width=True):
        processed_quantity, processed_order_ids = update_orders_for_sku(
            sku, 
            pick_quantity, 
            page_info['new_status'],
            st.session_state.user_role
        )

        if processed_quantity > 0:
            st.success(f"{page_info['new_status']} {processed_quantity} units of {sku}!")

        time.sleep(0.5)
        next_sku()
        st.rerun()