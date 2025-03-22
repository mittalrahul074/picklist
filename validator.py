import streamlit as st
import pandas as pd
from utils import get_swipe_card_html
from database import get_orders_grouped_by_sku, update_orders_for_sku, calculate_order_counts
import time

def render_validator_panel():
    """Render the validator panel for User2 to validate picked orders"""
    st.header("Order Validation")
    
    if "orders_df" not in st.session_state:
        st.session_state.orders_df = get_orders_from_db()  # Fetch only once
    
    if "sku_groups" not in st.session_state:
        st.session_state.sku_groups = get_orders_grouped_by_sku(st.session_state.orders_df, status='picked')

    sku_groups = st.session_state.sku_groups
    # Get picked orders grouped by SKU

    if "current_index" not in st.session_state:
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
    earliest_dispatch_date = current_sku_group['earliest_dispatch_date']
    
    # Container for the swipeable cards
    swipe_container = st.container()
    
    with swipe_container:
        # Create a card for the current SKU
        st.markdown(get_swipe_card_html({
            'sku': sku,
            'total_quantity': total_quantity,
            'order_count': order_count,
            'dispatch_date': earliest_dispatch_date
        }, 'validate'), unsafe_allow_html=True)
        
        # Add JavaScript for swipe actions
        # js = f"""
        # <script>
        # const validateCard = document.getElementById('validate_card_{sku}');
        # let startX, movedX;
        
        # validateCard.addEventListener('touchstart', function(e) {{
        #     startX = e.touches[0].clientX;
        # }}, false);
        
        # validateCard.addEventListener('touchmove', function(e) {{
        #     movedX = e.touches[0].clientX - startX;
            
        #     // Restrict horizontal movement
        #     if (Math.abs(movedX) < 200) {{
        #         validateCard.style.transform = `translateX(${{movedX}}px)`;
                
        #         // Change background color based on swipe direction
        #         if (movedX > 50) {{
        #             validateCard.style.backgroundColor = '#c8e6c9'; // Green for right swipe (Validate)
        #         }} else if (movedX < -50) {{
        #             validateCard.style.backgroundColor = '#ffcdd2'; // Red for left swipe (Reject)
        #         }} else {{
        #             validateCard.style.backgroundColor = '#ffffff'; // Default white
        #         }}
        #     }}
        # }}, false);
        
        # validateCard.addEventListener('touchend', function(e) {{
        #     if (movedX > 100) {{
        #         // Right swipe - Validate the SKU
        #         validateCard.style.transform = 'translateX(1000px)';
        #         validateCard.style.opacity = '0';
        #         setTimeout(() => {{
        #             // Submit a form to tell Streamlit the SKU was validated
        #             document.getElementById('validate_action').value = 'validate';
        #             document.getElementById('validate_sku').value = '{sku}';
        #             document.getElementById('validate_quantity').value = '{total_quantity}';
        #             document.getElementById('validate_form').submit();
        #         }}, 300);
        #     }} else if (movedX < -100) {{
        #         // Left swipe - Reject the SKU
        #         validateCard.style.transform = 'translateX(-1000px)';
        #         validateCard.style.opacity = '0';
        #         setTimeout(() => {{
        #             // Submit a form to tell Streamlit the SKU was rejected
        #             document.getElementById('validate_action').value = 'reject';
        #             document.getElementById('validate_sku').value = '{sku}';
        #             document.getElementById('validate_quantity').value = '{total_quantity}';
        #             document.getElementById('validate_form').submit();
        #         }}, 300);
        #     }} else {{
        #         // Reset card position
        #         validateCard.style.transform = 'translateX(0)';
        #         validateCard.style.backgroundColor = '#ffffff';
        #     }}
        # }}, false);
        # </script>
        # """
        # st.markdown(js, unsafe_allow_html=True)
        
        # # Hidden form to capture swipe actions
        # with st.form(key="validate_form", clear_on_submit=True):
        #     st.markdown('<div class="validate_form">', unsafe_allow_html=True)
        #     st.markdown("<p style='display:none'>Form for validation actions</p>", unsafe_allow_html=True)
        #     action = st.text_input("Action", key="validate_action", label_visibility="collapsed")
        #     sku_input = st.text_input("SKU", key="validate_sku", label_visibility="collapsed")
        #     quantity_input = st.text_input("Quantity", key="validate_quantity", label_visibility="collapsed")
        #     submitted = st.form_submit_button("Submit", use_container_width=True)
            
        #     if submitted:
        #         # Process the swipe action
        #         if action == "validate":
        #             # Update the order status to 'validated'
        #             processed_quantity, processed_order_ids = update_orders_for_sku(
        #                 sku_input, 
        #                 int(quantity_input), 
        #                 'validated',
        #                 st.session_state.user_role
        #             )
                    
        #             # Show success message
        #             if processed_quantity > 0:
        #                 st.success(f"Validated {processed_quantity} units of {sku_input}!")
                
        #         elif action == "reject":
        #             # Reset the order status to 'new'
        #             processed_quantity, processed_order_ids = update_orders_for_sku(
        #                 sku_input, 
        #                 int(quantity_input), 
        #                 'new',
        #                 None  # No user for rejected orders
        #             )
                    
        #             # Show info message
        #             if processed_quantity > 0:
        #                 st.info(f"Rejected {processed_quantity} units of {sku_input} and returned to picking queue.")
                
        #         # In both cases, we'll load the next SKU
        #         time.sleep(0.5)  # Brief delay for better UX
        #         st.rerun()
        #     st.markdown('</div>', unsafe_allow_html=True)
    
    # Alternative button controls for desktop users
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Reject", key="reject_button", use_container_width=True):
            # Reset the order status to 'new'
            if len(sku_groups) > st.session_state.current_index+1:
                st.session_state.current_index += 1
            else:
                st.session_state.current_index = 0
            time.sleep(0.5)  # Brief delay for better UX
            st.rerun()
    
    with col2:
        if st.button("Validate ➡️", key="validate_button", use_container_width=True):
            # Update the order status to 'validated'
            processed_quantity, processed_order_ids = update_orders_for_sku(
                sku, 
                total_quantity, 
                'validated',
                st.session_state.user_role
            )
            
            if len(sku_groups) > st.session_state.current_index+1:
                st.session_state.current_index += 1
            else:
                st.session_state.current_index = 0
                
            # Show success message
            if processed_quantity > 0:
                st.success(f"Validated {processed_quantity} units of {sku}!")
            
            time.sleep(0.5)  # Brief delay for better UX
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
        st.rerun()