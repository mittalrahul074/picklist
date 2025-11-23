import streamlit as st
import pandas as pd
from utils import get_swipe_card_html,next_sku
from database import get_orders_grouped_by_sku, update_orders_for_sku, calculate_order_counts,get_orders_from_db
import time

def render_validator_panel():
    """Render the validator panel for User2 to validate picked orders"""
    st.header("Order Validation")
    
    if "orders_df" not in st.session_state:
        st.session_state.orders_df = get_orders_from_db()  # Fetch only once
    
    # if "sku_groups" not in st.session_state:
    picked_orders_df = st.session_state.orders_df[st.session_state.orders_df["status"] == "picked"]
    st.session_state.sku_groups = get_orders_grouped_by_sku(picked_orders_df, status='picked')

    sku_groups = st.session_state.sku_groups
    # Get picked orders grouped by SKU

    if "current_index" not in st.session_state:
        st.session_state.current_index = 0
    elif st.session_state.current_index+1>len(sku_groups):
        st.session_state.current_index = 0
    
    if sku_groups.empty:
        st.info("No picked orders to validate. Please wait for User1 to pick some orders.")
        return
    
    # Display the number of SKUs to validate
    st.subheader(f"{len(sku_groups)} SKUs to Validate")
    
    # Display the first SKU group
    current_sku_group = sku_groups.iloc[st.session_state.current_index]
    sku = current_sku_group['sku']
    total_quantity = current_sku_group['total_quantity']
    order_count = current_sku_group['order_count']
    earliest_dispatch_date = current_sku_group['dispatch_date']
    
    # Create a card for the current SKU
    st.markdown(get_swipe_card_html({
        'sku': sku,
        'total_quantity': total_quantity,
        'order_count': order_count,
        'dispatch_date': earliest_dispatch_date
    }, 'validate'), unsafe_allow_html=True)

    # Alternative button controls for desktop users
    col1, col2 = st.columns(2)
    with col1:
        st.button("⬅️ Reject", key="reject_button", use_container_width=True, on_click=next_sku)
    
    with col2:
        if st.button("Validate ➡️", key="validate_button", use_container_width=True):
            # Update the order status to 'validated'
            processed_quantity, processed_order_ids = update_orders_for_sku(
                sku, 
                total_quantity, 
                'validated',
                st.session_state.user_role
            )

            # Show success message
            if processed_quantity > 0:
                st.success(f"Validated {processed_quantity} units of {sku}!")
            
            time.sleep(0.5)  # Brief delay for better UX
            next_sku()  # Move to next SKU
            st.rerun()
    
    # Show validate quantity adjustment
    st.markdown("---")
    st.subheader("Adjust Validation Quantity")
    
    # Allow user to adjust the quantity to validate
    validate_quantity = st.number_input(
        "Quantity to Validate", 
        min_value=1, 
        max_value=int(total_quantity), 
        value=int(total_quantity)
    )
    
    if st.button("Validate Adjusted Quantity", use_container_width=True):
        # Update the order status to 'validated' for the adjusted quantity
        processed_quantity, processed_order_ids = update_orders_for_sku(
            sku, 
            validate_quantity, 
            'validated',
            st.session_state.user_role
        )
        
        # Show success message
        if processed_quantity > 0:
            st.success(f"Validated {processed_quantity} units of {sku}!")
        
        time.sleep(0.5)  # Brief delay for better UX
        next_sku()
        st.rerun()