import pandas as pd
import streamlit as st
import io
from datetime import datetime, timedelta
from database import get_orders_from_db

def extract_order_data(file_buffer, platform):
    """
    Extracts order data from Excel or CSV file based on selected platform.
    
    Args:
        file_buffer: The uploaded file buffer (Excel or CSV)
        platform: Either 'flipkart' or 'meesho'
    
    Returns:
        DataFrame with extracted order data or None on error
    """
    try:
        # Read file
        file_name = file_buffer.name.lower()
        if file_name.endswith('.csv'):
            df = pd.read_csv(file_buffer, low_memory=False)
        else:  
            df = pd.read_excel(file_buffer, engine='openpyxl')  
        
        # Column mappings
        column_map = {
            'meesho': {'order_id': 1, 'sku': 5, 'quantity': 7, 'dispatch_date': 9},
            'flipkart': {'order_id': 3, 'sku': 8, 'quantity': 18, 'dispatch_date': 17}
        }
        
        if platform not in column_map:
            st.error("Invalid platform selected")
            return None

        col_idx = column_map[platform]
        orders_df = df.iloc[:, [col_idx['order_id'], col_idx['sku'], col_idx['quantity']]].copy()  # ✅ Use .copy() to avoid warnings
        orders_df.columns = ['order_id', 'sku', 'quantity']

        # ✅ Dispatch Date Fix
        if df.shape[1] > col_idx['dispatch_date']:
            orders_df.loc[:, 'dispatch_date'] = pd.to_datetime(df.iloc[:, col_idx['dispatch_date']], errors='coerce')
        else:
            orders_df.loc[:, 'dispatch_date'] = datetime.now() + timedelta(days=3)

        # ✅ Drop NaN rows safely
        orders_df.dropna(subset=['order_id', 'sku'], inplace=True)

        # ✅ Convert quantity to integer safely
        orders_df.loc[:, 'quantity'] = pd.to_numeric(orders_df['quantity'], errors='coerce').fillna(1).astype(int)

        # ✅ Convert SKU to uppercase (Fixed Warning)
        orders_df.loc[:, 'sku'] = orders_df['sku'].str.upper()

        # ✅ Optimized SKU Filtering
        allowed_r_skus = {"R1234", "R5678", "R91011"}  
        mask = orders_df['sku'].str.startswith(('K', 'L'), na=False) | orders_df['sku'].isin(allowed_r_skus)
        orders_df = orders_df.loc[mask].copy()  # ✅ Use .copy() to avoid warnings

        # ✅ Fill missing dispatch dates safely
        orders_df.loc[orders_df['dispatch_date'].isna(), 'dispatch_date'] = datetime.now() + timedelta(days=3)

        # ✅ Add status column
        orders_df.loc[:, 'status'] = 'new'

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
    """
    Export orders to Excel file for download
    
    Args:
        db_path: Path to the database
    
    Returns:
        Excel file as bytes or None if no orders exist
    """
    # Get latest orders from database
    orders_df = get_orders_from_db()
    
    if orders_df.empty:
        return None

    for col in ["created_at", "updated_at", "dispatch_date"]:
        if col in orders_df.columns:
            orders_df[col] = pd.to_datetime(orders_df[col]).dt.strftime("%Y-%m-%d %H:%M:%S")
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        orders_df.to_excel(writer, index=False)
    
    return output.getvalue()