import streamlit as st
import pandas as pd
from utils import get_swipe_card_html
from database import get_orders_grouped_by_sku, update_orders_for_sku, calculate_order_counts,get_orders_from_db
import time

def render_picker_panel():
    """Render the picker panel for User1 to pick orders"""
    st.header("Order Picking")

    if "orders_df" not in st.session_state:
        st.session_state.orders_df = get_orders_from_db()  # Fetch only once
    
    # if "sku_groups" not in st.session_state:
    st.session_state.sku_groups = get_orders_grouped_by_sku(st.session_state.orders_df, status='new')

    # if "current_index" not in st.session_state:
    st.session_state.current_index = 0
        
    sku_groups = st.session_state.sku_groups
    
    if sku_groups.empty:
        st.info("No orders available to pick. Please wait for the admin to upload orders.")
        return
    
    # Display the number of SKUs to pick
    st.subheader(f"{len(sku_groups)} SKUs to Pick")
    
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
        }, 'pick'), unsafe_allow_html=True)
        
        # Add JavaScript for swipe actions
        # js = f"""
        # <script>
        # const pickCard = document.getElementById('pick_card_{sku}');
        # let startX, movedX;
        
        # pickCard.addEventListener('touchstart', function(e) {{
        #     startX = e.touches[0].clientX;
        # }}, false);
        
        # pickCard.addEventListener('touchmove', function(e) {{
        #     movedX = e.touches[0].clientX - startX;
            
        #     // Restrict horizontal movement
        #     if (Math.abs(movedX) < 200) {{
        #         pickCard.style.transform = `translateX(${{movedX}}px)`;
                
        #         // Change background color based on swipe direction
        #         if (movedX > 50) {{
        #             pickCard.style.backgroundColor = '#c8e6c9'; // Green for right swipe (Pick)
        #         }} else if (movedX < -50) {{
        #             pickCard.style.backgroundColor = '#ffcdd2'; // Red for left swipe (Skip)
        #         }} else {{
        #             pickCard.style.backgroundColor = '#ffffff'; // Default white
        #         }}
        #     }}
        # }}, false);
        
        # pickCard.addEventListener('touchend', function(e) {{
        #     if (movedX > 100) {{
        #         // Right swipe - Pick the SKU
        #         pickCard.style.transform = 'translateX(1000px)';
        #         pickCard.style.opacity = '0';
        #         setTimeout(() => {{
        #             // Submit a form to tell Streamlit the SKU was picked
        #             document.getElementById('pick_action').value = 'pick';
        #             document.getElementById('pick_sku').value = '{sku}';
        #             document.getElementById('pick_quantity').value = '{total_quantity}';
        #             document.getElementById('pick_form').submit();
        #         }}, 300);
        #     }} else if (movedX < -100) {{
        #         // Left swipe - Skip the SKU
        #         pickCard.style.transform = 'translateX(-1000px)';
        #         pickCard.style.opacity = '0';
        #         setTimeout(() => {{
        #             // Submit a form to tell Streamlit the SKU was skipped
        #             document.getElementById('pick_action').value = 'skip';
        #             document.getElementById('pick_sku').value = '{sku}';
        #             document.getElementById('pick_form').submit();
        #         }}, 300);
        #     }} else {{
        #         // Reset card position
        #         pickCard.style.transform = 'translateX(0)';
        #         pickCard.style.backgroundColor = '#ffffff';
        #     }}
        # }}, false);
        # </script>
        # """
        # st.markdown(js, unsafe_allow_html=True)
        
        # Hidden form to capture swipe actions
        # with st.form(key="pick_form", clear_on_submit=True):
            # st.markdown('<div class="pick_form">', unsafe_allow_html=True)
            # st.markdown("<p style='display:none'>Form for swipe actions</p>", unsafe_allow_html=True)
            # action = st.text_input("Action", key="pick_action", label_visibility="collapsed")
            # sku_input = st.text_input("SKU", key="pick_sku", label_visibility="collapsed")
            # quantity_input = st.text_input("Quantity", key="pick_quantity", label_visibility="collapsed")
            # submitted = st.form_submit_button("Submit", use_container_width=True)
            
            # if submitted:
            #     # Process the swipe action
            #     if action == "pick":
            #         # Update the order status to 'picked'
            #         processed_quantity, processed_order_ids = update_orders_for_sku(
            #             sku_input, 
            #             int(quantity_input), 
            #             'picked',
            #             st.session_state.user_role
            #         )
                    
            #         # Show success message
            #         if processed_quantity > 0:
            #             st.success(f"Picked {processed_quantity} units of {sku_input}!")
                
            #     # In both cases (pick or skip), we'll load the next SKU
            #     time.sleep(0.5)  # Brief delay for better UX
            #     st.rerun()
            # st.markdown('</div>', unsafe_allow_html=True)
    
    # Alternative button controls for desktop users
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Skip", key="skip_button", use_container_width=True):
            # Skip this SKU and move to the next
            print(st.session_state.current_index)
            if len(sku_groups) > st.session_state.current_index+1:
                st.session_state.current_index += 1
            else:
                st.session_state.current_index = 0
            print("skip")
            st.rerun()
    
    with col2:
        if st.button("Pick ➡️", key="pick_button", use_container_width=True):
            # Update the order status to 'picked'
            processed_quantity, processed_order_ids = update_orders_for_sku(
                sku, 
                total_quantity, 
                'picked',
                st.session_state.user_role
            )
            
            # Show success message
            if processed_quantity > 0:
                st.success(f"Picked {processed_quantity} units of {sku}!")

            if len(sku_groups) > st.session_state.current_index+1:
                st.session_state.current_index += 1
            else:
                st.session_state.current_index = 0
            
            time.sleep(0.5)  # Brief delay for better UX
            st.rerun()
    
    # Show pick quantity adjustment
    st.markdown("---")
    st.subheader("Adjust Pick Quantity")
    
    # Allow user to adjust the quantity to pick
    pick_quantity = st.number_input(
        "Quantity to Pick", 
        min_value=1, 
        max_value=int(total_quantity), 
        value=int(total_quantity)
    )
    
    if st.button("Pick Adjusted Quantity", use_container_width=True):
        # Update the order status to 'picked' for the adjusted quantity
        processed_quantity, processed_order_ids = update_orders_for_sku(
            sku, 
            pick_quantity, 
            'picked',
            st.session_state.user_role
        )
        
        # Show success message
        if processed_quantity > 0:
            st.success(f"Picked {processed_quantity} units of {sku}!")
        
        time.sleep(0.5)  # Brief delay for better UX
        st.rerun()