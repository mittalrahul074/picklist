import streamlit as st
import pandas as pd
import plotly.express as px
from utils import export_orders_to_excel
from database import get_db_connection,get_orders_from_db, calculate_order_counts, get_user_productivity

def render_dashboard():
    if "orders_df" not in st.session_state:
        st.session_state.orders_df = get_orders_from_db()
    
    """Render the dashboard with order statistics and visualizations"""
    st.session_state.current_index = 0
    st.header("Order Management Dashboard")
    
    # Check if database exists
    if get_db_connection() is None:
        st.info("Database not initialized. Please reload the application.")
        return
    
    # Get current order counts
    order_counts = calculate_order_counts()
    
    # Order status counts
    st.subheader("Order Status")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("New Orders", order_counts.get('new', 0))
    with col2:
        st.metric("Picked Orders", order_counts.get('picked', 0))
    with col3:
        st.metric("Validated Orders", order_counts.get('validated', 0))
    
    # Visualizations
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Pie chart for order status distribution
        status_counts = pd.DataFrame({
            'Status': ['New', 'Picked', 'Validated'],
            'Count': [
                order_counts.get('new', 0),
                order_counts.get('picked', 0),
                order_counts.get('validated', 0)
            ]
        })
        
        if sum(status_counts['Count']) > 0:
            fig = px.pie(
                status_counts, 
                values='Count', 
                names='Status',
                title='Order Status Distribution',
                color='Status',
                color_discrete_map={
                    'New': '#FFA726',       # Orange
                    'Picked': '#42A5F5',    # Blue
                    'Validated': '#66BB6A'  # Green
                }
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available for visualization")
    
    with col2:
        # Bar chart for user productivity
        productivity_df = get_user_productivity()
        
        if not productivity_df.empty:
            # Convert to long format for Plotly
            productivity_long = pd.melt(
                productivity_df,
                id_vars=['user'],
                value_vars=['picked_count', 'validated_count'],
                var_name='Action Type',
                value_name='Count'
            )
            
            # Rename columns for better display
            productivity_long['Action Type'] = productivity_long['Action Type'].map({
                'picked_count': 'Picked',
                'validated_count': 'Validated'
            })
            
            # Create bar chart
            fig = px.bar(
                productivity_long,
                x='user',
                y='Count',
                color='Action Type',
                title='User Productivity',
                barmode='group',
                color_discrete_map={
                    'Picked': '#42A5F5',    # Blue
                    'Validated': '#66BB6A'  # Green
                }
            )
            fig.update_layout(xaxis_title='User', yaxis_title='Count')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No user productivity data available yet")
    
    # Export functionality
    st.markdown("---")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Export Data")
        
        excel_data = export_orders_to_excel()
        if excel_data:
            st.download_button(
                label="Download All Orders",
                data=excel_data,
                file_name="orders_export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    # Order data tables
    st.markdown("---")
    
    # Tabs for different order status views
    tab1, tab2, tab3, tab4 = st.tabs(["All Orders", "New Orders", "Picked Orders", "Validated Orders"])
    
    with tab1:
        orders_df = st.session_state.orders_df
        if not orders_df.empty:
            st.dataframe(orders_df, use_container_width=True)
        else:
            st.info("No orders available")
    
    with tab2:
        new_orders = orders_df[orders_df['status'] == 'new']
        if not new_orders.empty:
            st.dataframe(new_orders, use_container_width=True)
        else:
            st.info("No new orders available")
    
    with tab3:
        picked_orders = orders_df[orders_df['status'] == 'picked']
        if not picked_orders.empty:
            st.dataframe(picked_orders, use_container_width=True)
        else:
            st.info("No picked orders available")
    
    with tab4:
        validated_orders = orders_df[orders_df['status'] == 'validated']
        if not validated_orders.empty:
            st.dataframe(validated_orders, use_container_width=True)
        else:
            st.info("No validated orders available")