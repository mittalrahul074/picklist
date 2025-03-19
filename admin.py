import streamlit as st
import pandas as pd
import os
from utils import extract_order_data, export_orders_to_excel
from database import add_orders_to_db, get_orders_from_db, calculate_order_counts

def render_admin_panel():
    """Render the admin panel for uploading Excel or CSV files"""
    st.header("Admin Panel - Order Upload")
    
    # File upload section
    st.subheader("Upload Order File")
    uploaded_file = st.file_uploader("Choose a file", type=["xlsx", "xls", "csv"])
    
    # Platform selection
    platform = st.radio(
        "Select Platform",
        ["flipkart", "meesho"],
        index=0,
        format_func=lambda x: x.capitalize()
    )
    
    # Process uploaded file
    if uploaded_file is not None:
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Process File"):
                # Extract data from the uploaded file
                orders_df = extract_order_data(uploaded_file, platform)
                
                if orders_df is not None and not orders_df.empty:
                    # Add orders to database
                    success, count = add_orders_to_db(orders_df, platform)
                    
                    if success:
                        if count > 0:
                            st.success(f"Added {count} new orders from {platform.capitalize()}")
                        else:
                            st.info("No new orders found in the file")
                            
                        # Show preview of all orders
                        with st.expander("Preview Processed Data"):
                            # Get latest data from database
                            preview_df = get_orders_from_db()
                            st.dataframe(preview_df.head(10))
                    else:
                        st.error("Failed to add orders to database")
                else:
                    st.error("Failed to process the file or no valid data found")
        
        with col2:
            # Allow downloading the current orders as Excel
            if 'db_path' in st.session_state:
                excel_data = export_orders_to_excel(st.session_state.db_path)
                if excel_data:
                    st.download_button(
                        label="Download All Orders",
                        data=excel_data,
                        file_name="orders_export.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
    
    # Display current order statistics
    if 'db_path' in st.session_state and os.path.exists(st.session_state.db_path):
        st.markdown("---")
        st.subheader("Current Order Statistics")
        
        order_counts = calculate_order_counts()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("New Orders", order_counts.get('new', 0))
        with col2:
            st.metric("Picked Orders", order_counts.get('picked', 0))
        with col3:
            st.metric("Validated Orders", order_counts.get('validated', 0))
        
        # Show all orders in a table
        st.markdown("---")
        st.subheader("All Orders")
        
        # Load latest data from database
        orders_df = get_orders_from_db()
        if not orders_df.empty:
            st.dataframe(orders_df)
        else:
            st.info("No orders in the database yet")