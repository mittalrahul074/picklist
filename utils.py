import pandas as pd
import streamlit as st
import io
from datetime import datetime, timedelta
from database import get_orders_from_db,update_status

def next_sku():
    st.session_state.current_index += 1
    if st.session_state.current_index >= len(st.session_state.sku_groups):
        st.session_state.current_index = 0

def get_party_filter_df(df, party_filter):
    if party_filter == "Kangan":
        return df[df["sku"].str.startswith("K")]
    elif party_filter == "RS":
        return df[df["sku"].str.startswith("R")]
    return df

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

        orders_cancel_df = pd.DataFrame()

        # Extract data based on platform
        if platform == 'meesho':

            # remove canclled orders
            print("m")
            cancle_df = df[df.iloc[:, 0].str.lower().isin(['cancelled'])]
            orders_cancel_df = pd.DataFrame({
                'order_id': cancle_df.iloc[:, 1].copy(),
                'sku': cancle_df.iloc[:, 5].copy(),
                'quantity': cancle_df.iloc[:, 7].copy(),
                'dispatch_date': cancle_df.iloc[:, 2].copy(),
                'status': cancle_df.iloc[:, 0].copy()
            })

            if orders_cancel_df is not None and not orders_cancel_df.empty:
                print("if cancle")
                for _, row in orders_cancel_df.iterrows():
                    print("for cancle")
                    order_id = row["order_id"]
                    status = row["status"]
                    update_status(order_id,status)


            df = df[df.iloc[:, 0].str.lower().isin(['pending'])]
            orders_df = pd.DataFrame({
                'order_id': df.iloc[:, 1].copy(),
                'sku': df.iloc[:, 5].copy(),
                'quantity': df.iloc[:, 7].copy(),
                'dispatch_date': df.iloc[:, 2].copy()
            })
            
            # Convert to UTC first, then remove timezone
            orders_df['dispatch_date'] = pd.to_datetime(orders_df['dispatch_date'], dayfirst=True, errors='coerce') + timedelta(days=2)
                
        elif platform == 'flipkart':
            orders_df = pd.DataFrame({
                'order_id': df.iloc[:, 3].copy(),
                'sku': df.iloc[:, 8].copy(),
                'quantity': df.iloc[:, 18].copy(),
                'dispatch_date': df.iloc[:, 28].copy()
            })
            
            orders_df['dispatch_date'] = pd.to_datetime(
                orders_df['dispatch_date'].astype(str), 
                format="%b %d, %Y %H:%M:%S", errors='coerce'
            )

        else:
            st.error("Invalid platform selected")
            return None

        # Convert dispatch_date to string format "DD-MM-YYYY"
        orders_df['dispatch_date'] = orders_df['dispatch_date'].dt.strftime("%d-%m-%Y")

        # Rest of your processing remains the same...
        orders_df['status'] = 'new'
        orders_df.dropna(subset=['order_id', 'sku'], inplace=True)
        orders_df['quantity'] = pd.to_numeric(orders_df['quantity'], errors='coerce').fillna(1).astype(int)
        orders_df['sku'] = orders_df['sku'].astype(str).str.upper()
        # TO-Do: Filter SKUs based on specific criteria if needed
        # createria example: sku starts with K or L or in allowed list
        # allowed_r_skus = ["MARATHI NATH", "NEPALI HAIR PIN", "R91011"]
        # orders_df = orders_df[
        #     orders_df['sku'].str.startswith(('K', 'L'), na=False) | 
        #     orders_df['sku'].isin(allowed_r_skus)
        # ]

        return orders_df

    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        return None

def get_swipe_card_html(order_data, action_type):
    """
    Generate HTML for a swipeable card showing dispatch-wise breakdown.
    """
    sku = order_data['sku']
    total_quantity = order_data['total_quantity']
    order_count = order_data.get('order_count', 1)
    breakdown = order_data.get('dispatch_date', [])

    if action_type == 'pick':
        left_action = "Skip"
        right_action = "Pick"
        card_id = f"pick_card_{sku}"
    else:
        left_action = "Reject"
        right_action = "Validate"
        card_id = f"validate_card_{sku}"

    # Build dispatch table rows
    dispatch_table_rows = ""
    for row in breakdown:
        dispatch_table_rows += f"""<tr><td>{row['date']}</td><td style="text-align:right;">{row['quantity']}</td></tr>"""

    # Final HTML
    html = f"""<div class="swipe-card" id="{card_id}" data-sku="{sku}"><div class="card-content"><h3>SKU: {sku}</h3><table style="width:100%; margin: 10px 0; border-collapse: collapse;"><thead><tr><th style="text-align:left;">Dispatch Date</th><th style="text-align:right;">Quantity</th></tr></thead><tbody>{dispatch_table_rows}</tbody></table><p style="font-size: 1.3rem; text-align: right; margin-top: 8px;"><strong>Total Quantity:</strong> {total_quantity}</p></div></div>"""
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
