import pandas as pd
import streamlit as st
import io
from datetime import datetime, timedelta
from database import get_orders_from_db

def next_sku():
    st.session_state.current_index += 1
    if st.session_state.current_index >= len(st.session_state.sku_groups):
        st.session_state.current_index = 0

def extract_order_data(file_buffer, platform):
    """
    Extracts order data from Excel file or CSV file based on selected platform.
    Ensures timezone-naive datetime objects in consistent format.
    """
    try:
        # Determine file type and read accordingly
        file_name = file_buffer.name.lower()
        if file_name.endswith('.csv'):
            df = pd.read_csv(file_buffer)
        else:  # Excel file (.xlsx or .xls)
            df = pd.read_excel(file_buffer)

        # Extract data based on platform
        if platform == 'meesho':
            df = df[~df.iloc[:, 0].str.lower().isin(['shipped', 'cancelled'])]
            orders_df = pd.DataFrame({
                'order_id': df.iloc[:, 1].copy(),
                'sku': df.iloc[:, 5].copy(),
                'quantity': df.iloc[:, 7].copy(),
                'dispatch_date': df.iloc[:, 2].copy()
            })
            
            # Convert to UTC first, then remove timezone
            orders_df['dispatch_date'] = (
                pd.to_datetime(orders_df['dispatch_date'], dayfirst=True, errors='coerce')
                .dt.tz_localize('Asia/Kolkata')  # Assuming Meesho uses IST
                .dt.tz_convert('UTC')
                .dt.tz_localize(None)  # Remove timezone info
                + timedelta(days=2))
                
        elif platform == 'flipkart':
            orders_df = pd.DataFrame({
                'order_id': df.iloc[:, 3].copy(),
                'sku': df.iloc[:, 8].copy(),
                'quantity': df.iloc[:, 18].copy(),
                'dispatch_date': df.iloc[:, 28].copy()
            })
            
            # Convert to UTC first, then remove timezone
            orders_df['dispatch_date'] = (
                pd.to_datetime(orders_df['dispatch_date'].astype(str), 
                format="%b %d, %Y %H:%M:%S", errors='coerce')
                .dt.tz_localize('Asia/Kolkata')  # Assuming Flipkart uses IST
                .dt.tz_convert('UTC')
                .dt.tz_localize(None))  # Remove timezone info

        else:
            st.error("Invalid platform selected")
            return None

        # Rest of your processing remains the same...
        orders_df['status'] = 'new'
        orders_df.dropna(subset=['order_id', 'sku'], inplace=True)
        orders_df['quantity'] = pd.to_numeric(orders_df['quantity'], errors='coerce').fillna(1).astype(int)
        orders_df['sku'] = orders_df['sku'].astype(str).str.upper()
        
        allowed_r_skus = ["marathi nath", "R5678", "R91011"]
        orders_df = orders_df[
            orders_df['sku'].str.startswith(('K', 'L'), na=False) | 
            orders_df['sku'].isin(allowed_r_skus)
        ]

        return orders_df

    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        return None

def get_swipe_card_html(order_data, action_type):
    """
    Generate HTML for a swipeable card
    
    Args:
        order_data: Dictionary containing order data (sku, total_quantity, etc.)
        action_type: Either 'pick' or 'validate'
    
    Returns:
        HTML string for the swipeable card
    """
    sku = order_data['sku']
    total_quantity = order_data['total_quantity']
    order_count = order_data.get('order_count', 1)
    dispatch_date = order_data.get('dispatch_date')
    
    if action_type == 'pick':
        left_action = "Skip"
        right_action = "Pick"
        card_id = f"pick_card_{sku}"
    else:  # validate
        left_action = "Reject"
        right_action = "Validate"
        card_id = f"validate_card_{sku}"
    
    # Format dispatch date for display
    dispatch_date_display = ""
    if dispatch_date is not None:
        try:
            # Convert to datetime if it's not already
            if not isinstance(dispatch_date, datetime):
                dispatch_date = pd.to_datetime(dispatch_date)
            
            # Format the date
            dispatch_date_str = dispatch_date.strftime("%d %b %Y")
            dispatch_date_display = f"<p><strong>Dispatch Date:</strong> {dispatch_date_str}</p>"
        except:
            # If conversion fails, don't show the date
            pass
    
    html = f"""
    <div class="swipe-card" id="{card_id}" data-sku="{sku}">
        <div class="card-content">
            <h3>SKU: {sku}</h3>
            <p><strong>Order Count:</strong> {order_count}</p>
            <p style="font-size: 1.5rem; text-align: center;"><strong>Total Quantity:</strong> {total_quantity}</p>
            {dispatch_date_display}
        </div>
        <div class="swipe-actions">
            <div class="swipe-left">{left_action}</div>
            <div class="swipe-right">{right_action}</div>
        </div>
    </div>
    """
    return html

def export_orders_to_excel():
    if "orders_df" not in st.session_state:
        st.session_state.orders_df = get_orders_from_db()
    """
    Export orders to Excel file for download
    
    Args:
        db_path: Path to the database
    
    Returns:
        Excel file as bytes or None if no orders exist
    """
    # Get latest orders from database
    orders_df = st.session_state.orders_df
    
    if orders_df.empty:
        return None

    for col in ["created_at", "updated_at", "dispatch_date"]:
        if col in orders_df.columns:
            orders_df[col] = pd.to_datetime(orders_df[col]).dt.strftime("%Y-%m-%d %H:%M:%S")
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        orders_df.to_excel(writer, index=False)
    
    return output.getvalue()