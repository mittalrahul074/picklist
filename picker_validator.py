import streamlit as st
import pandas as pd
from utils import get_swipe_card_html,next_sku
from database import get_orders_grouped_by_sku, update_orders_for_sku, calculate_order_counts,get_orders_from_db,get_product_image_url
import time
from validator import render_validator_panel
import utils

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

    # print(f"DEBUG: pick_sku called for SKU={sku}, quantity={total_quantity}")
    # st.success(f"DEBUG: pick_sku called for SKU={sku}, quantity={total_quantity}")
    time.sleep(0.5)  # UX delay

    processed_quantity, processed_order_ids = update_orders_for_sku(
        sku, 
        total_quantity, 
        page_info['new_status'],
        st.session_state.user_role
    )
    
    # print(f"DEBUG: First update returned processed_quantity={processed_quantity}")
    # st.success(f"DEBUG: First update returned processed_quantity={processed_quantity}")
    time.sleep(0.5)  # UX delay
    
    if st.session_state.get("user_type") == 3:
        # print(f"DEBUG: user_type is 3, performing secondary validation")
        # st.success(f"DEBUG: user_type is 3, performing secondary validation")
        # perform validation on the same picked orders
        processed_quantity2, processed_order_ids = update_orders_for_sku(
            sku, 
            total_quantity, 
            "validated",
            st.session_state.user_role
        )
        # print(f"DEBUG: Secondary update returned processed_quantity2={processed_quantity2}")
        # st.success(f"DEBUG: Secondary update returned processed_quantity2={processed_quantity2}")
        time.sleep(0.5)  # UX delay

    if processed_quantity == -1:
        # print(f"DEBUG: ERROR - Not enough quantity for SKU={sku}")
        st.toast(
            f"❌ Not enough quantity left for SKU={sku}. "
            f"Someone already validated/picked these orders.",
            icon="⚠️"
        )
        time.sleep(0.5)  # UX delay
        return
    
    if processed_quantity > 0:
        # print(f"DEBUG: SUCCESS - {page_info['new_status']} {processed_quantity} units of {sku}")
        st.success(f"{page_info['new_status']} {processed_quantity} units of {sku}!")
        time.sleep(0.5)  # UX delay
    
    time.sleep(0.5)  # UX delay
    # next_sku()  # Move to next SKU

# @st.cache_data(ttl=30)
def cached_orders():
    return get_orders_from_db()

# @st.cache_data
def cached_group_orders(df, status):
    return get_orders_grouped_by_sku(df, status)

def render_picker_validator_panel(which_page):
    """Render the validator panel if which_page is 'validator', else picker panel"""
    if which_page == "validator":
        # redirect to validator panel
        render_validator_panel()
        return
    # Main Picker Panel
    page_info = get_page_info(which_page)
    st.header(f"Order {page_info['page_head']}")

    if "orders_df" not in st.session_state:
        st.session_state.orders_df = cached_orders()  # Fetch only once
    
    unique_dispatch_dates = st.session_state.orders_df['dispatch_date'].unique()
    selected_dispatch_date = st.selectbox("Filter by Dispatch Date", options=["All"] + list(unique_dispatch_dates))
    if selected_dispatch_date != "All":
        st.session_state.orders_df = st.session_state.orders_df[st.session_state.orders_df['dispatch_date'] == selected_dispatch_date]

    df= st.session_state.orders_df
    party_filter = st.session_state.get("party_filter", "Both")
    df = utils.get_party_filter_df(df, party_filter)

    st.session_state.sku_groups = cached_group_orders(
        df,
        status= page_info['status'])

    sku_groups = st.session_state.sku_groups

    st.subheader(f"{len(sku_groups)} SKUs to Pick")

    if "current_index" not in st.session_state:
        st.session_state.current_index = 0  # Ensure index is initialized
    if st.session_state.current_index>=len(sku_groups):
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
    with st.expander("📷 View Product Image"):
        img_url = get_product_image_url(sku)  # or database.get_product_image_url(sku)
        if img_url:
            st.image(img_url, use_column_width=True)
        else:
            st.info("No product image found for this SKU.")
    st.markdown(get_swipe_card_html({
        'sku': sku,
        'total_quantity': total_quantity,
        'order_count': order_count,
        'dispatch_date': dispatch_date
    }, page_info['to_do']), unsafe_allow_html=True)

    # Buttons
    col1, col2 = st.columns(2)
    with col2:
        st.button(f"⬅️ {page_info['left']}", key=page_info['key_left'], use_container_width=True, on_click=next_sku)

    with col1:
        if st.button(f"{page_info['right']} ➡️", key=page_info['key_right'], use_container_width=True):
            pick_sku(page_info)
            st.session_state.current_index += 1
            st.rerun()

    st.button("Previous SKU ⬅️", key="previous_sku_button", use_container_width=True, on_click=lambda: st.session_state.update(current_index=max(0, st.session_state.current_index-1)))

    # Pick Quantity Adjustment
    st.markdown("---")
    st.subheader(f"Adjust {page_info['to_do']} Quantity")

    pick_quantity = st.number_input(
        f"Quantity to {page_info['to_do']}", 
        min_value=1, 
        max_value=int(total_quantity), 
        value=int(total_quantity)
    )

    if st.button(f"{page_info['to_do']} Adjusted Quantity", use_container_width=True):
        st.success(f"Processing {pick_quantity} units of {sku} for {page_info['to_do']}.")
        processed_quantity, processed_order_ids = update_orders_for_sku(
            sku, 
            pick_quantity, 
            page_info['new_status'],
            st.session_state.user_role
        )
        st.success(f"Processed {processed_quantity} units of {sku} for {page_info['to_do']}.")

        if processed_quantity == -1:
            st.toast(
                f"❌ Not enough quantity left for SKU={sku}. "
                f"Someone already validated/picked these orders.",
                icon="⚠️"
            )
            return

        if processed_quantity > 0:
            st.success(f"{page_info['new_status']} {processed_quantity} units of {sku}!")

        time.sleep(0.5)
        st.session_state.current_index += 1
        st.rerun()