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
        if platform == 'meesho':
            if file_name.endswith('.csv'):
                df = pd.read_csv(file_buffer,dtype=str, keep_default_na=False)
            else:  # Excel file (.xlsx or .xls)
                df = pd.read_excel(file_buffer,dtype=str, keep_default_na=False)
        elif platform == 'flipkart':
            if file_name.endswith('.csv'):
                df = pd.read_csv(file_buffer)
            else:  # Excel file (.xlsx or .xls)
                df = pd.read_excel(file_buffer)

        print(df.iloc[:10, 2].tolist())

        # Validate that file was read successfully
        if df is None or df.empty:
            st.error("File is empty or could not be read. Please check the file format.")
            print("Error: DataFrame is None or empty after reading file")
            return None
        
        print(f"File read successfully. Shape: {df.shape} (rows x columns)")
        print(f"Column count: {df.shape[1]}")
        
        orders_cancel_df = pd.DataFrame()

        # Extract data based on platform
        if platform == 'meesho':
            # Validate that the dataframe has enough columns
            if df.shape[1] < 8:
                st.error(f"File doesn't have enough columns. Expected at least 8 columns, found {df.shape[1]}")
                print(f"Error: File has only {df.shape[1]} columns, need at least 8")
                return None
            
            # Ensure column 0 is string type and handle NaN values
            df.iloc[:, 0] = df.iloc[:, 0].astype(str).fillna('').str.strip()
            
            # Process cancelled orders
            print("Processing cancelled orders")
            cancelled_mask = df.iloc[:, 0].str.lower().isin(['cancelled','shipped','delivered'])
            cancle_df = df[cancelled_mask].copy()
            
            if not cancle_df.empty:
                orders_cancel_df = pd.DataFrame({
                    'order_id': cancle_df.iloc[:, 1].astype(str),
                    'sku': cancle_df.iloc[:, 5].astype(str),
                    'quantity': pd.to_numeric(cancle_df.iloc[:, 7], errors='coerce').fillna(1).astype(int),
                    'dispatch_date': cancle_df.iloc[:, 2].astype(str),
                    'status': cancle_df.iloc[:, 0].astype(str)
                })
                
                print(f"Found {len(orders_cancel_df)} cancelled orders")
                for _, row in orders_cancel_df.iterrows():
                    try:
                        order_id = str(row["order_id"])
                        status = str(row["status"])
                        if order_id and order_id != 'nan':
                            update_status(order_id, status, platform)
                    except Exception as e:
                        print(f"Error updating cancelled order {row.get('order_id', 'unknown')}: {e}")

            # Filter for pending and ready_to_ship orders
            pending_mask = df.iloc[:, 0].str.lower().isin(['pending', 'ready_to_ship'])
            df = df[pending_mask].copy()
            
            if df.empty:
                cancelled_count = len(orders_cancel_df) if not orders_cancel_df.empty else 0
                if cancelled_count > 0:
                    st.success(f"✅ Processed {cancelled_count} cancelled order(s). No pending/ready_to_ship orders to add.")
                    print(f"Success: Processed {cancelled_count} cancelled orders, no pending/ready_to_ship orders found")
                else:
                    st.warning("⚠️ No pending, ready_to_ship, or cancelled orders found in the file.")
                    print("Warning: No pending, ready_to_ship, or cancelled orders found after filtering")
                # Return None to indicate no new orders to add (but cancelled orders were processed successfully)
                return None

            # Create orders dataframe
            orders_df = pd.DataFrame({
                'order_id': df.iloc[:, 1].astype(str),
                'sku': df.iloc[:, 5].astype(str),
                'quantity': pd.to_numeric(df.iloc[:, 7], errors='coerce').fillna(1).astype(int),
                'dispatch_date': df.iloc[:, 2].astype(str),
                'status': 'new'
            })

            print(f"DEBUG:  Dispatch dates before processing: {orders_df['dispatch_date']}")
            
            print(f"Created orders_df with {len(orders_df)} pending/ready_to_ship orders")
            
            # Convert to UTC first, then remove timezone

            # orders_df['dispatch_date'] = pd.to_datetime(orders_df['dispatch_date'], dayfirst=True, errors='coerce')
            # orders_df['dispatch_date'] = orders_df['dispatch_date'] + timedelta(days=2)

            orders_df['dispatch_date'] = orders_df['dispatch_date'].apply(normalize_and_shift)

            print(f"DEBUG: Dispatch dates after normalization: {orders_df['dispatch_date']}")
            
            # Remove rows with invalid dispatch dates
            orders_df = orders_df.dropna(subset=['dispatch_date'])
            print(f"DEBUG: Dispatch dates after processing: {orders_df['dispatch_date']}")
                
        elif platform == 'flipkart':
            orders_df = pd.DataFrame({
                'order_id': df.iloc[:, 3].copy(),
                'sku': df.iloc[:, 8].copy(),
                'quantity': df.iloc[:, 18].copy(),
                'dispatch_date': df.iloc[:, 28].copy(),
                'status': 'new'
            })
            
            orders_df['dispatch_date'] = pd.to_datetime(
                orders_df['dispatch_date'].astype(str), 
                format="%b %d, %Y %H:%M:%S", errors='coerce'
            )
            orders_df['dispatch_date'] = orders_df['dispatch_date'].dt.strftime("%d-%m-%Y")

        else:
            st.error("Invalid platform selected")
            return None

        # Convert dispatch_date to string format "DD-MM-YYYY"
        print(f"DEBUG: Final dispatch dates: {orders_df['dispatch_date']}")
        # Rest of your processing remains the same...
        orders_df['status'] = 'new'
        
        # Remove rows with missing critical data
        before_drop = len(orders_df)
        orders_df.dropna(subset=['order_id', 'sku'], inplace=True)
        after_drop = len(orders_df)
        
        if before_drop > after_drop:
            print(f"Dropped {before_drop - after_drop} rows with missing order_id or sku")
        
        if orders_df.empty:
            st.warning("No valid orders found after processing. All orders were filtered out (missing order_id or sku).")
            print("Warning: orders_df is empty after dropping NA values")
            return pd.DataFrame(columns=['order_id', 'sku', 'quantity', 'dispatch_date', 'status'])
        
        # Convert quantity and ensure it's numeric
        orders_df['quantity'] = pd.to_numeric(orders_df['quantity'], errors='coerce').fillna(1).astype(int)
        orders_df['sku'] = orders_df['sku'].astype(str).str.strip().str.upper()
        
        # Remove empty SKUs
        orders_df = orders_df[orders_df['sku'] != '']
        orders_df = orders_df[orders_df['sku'] != 'NAN']
        
        if orders_df.empty:
            st.warning("No valid orders found after processing. All SKUs were empty or invalid.")
            print("Warning: orders_df is empty after filtering empty SKUs")
            return pd.DataFrame(columns=['order_id', 'sku', 'quantity', 'dispatch_date', 'status'])
        
        print(f"Final orders_df shape: {orders_df.shape}")
        print(f"Sample order_id: {orders_df['order_id'].iloc[0] if len(orders_df) > 0 else 'N/A'}")
        print(f"Sample sku: {orders_df['sku'].iloc[0] if len(orders_df) > 0 else 'N/A'}")
        
        # TO-Do: Filter SKUs based on specific criteria if needed
        # createria example: sku starts with K or L or in allowed list
        # allowed_r_skus = ["MARATHI NATH", "NEPALI HAIR PIN", "R91011"]
        # orders_df = orders_df[
        #     orders_df['sku'].str.startswith(('K', 'L'), na=False) | 
        #     orders_df['sku'].isin(allowed_r_skus)
        # ]

        return orders_df

    except Exception as e:
        error_msg = f"Error processing file: {str(e)}"
        st.error(error_msg)
        print(f"Detailed error: {type(e).__name__}: {e}")
        import traceback
        print(traceback.format_exc())
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

def normalize_and_shift(raw):
    raw = str(raw).strip()

    # Case 1: ISO format (2025-12-03)
    if len(raw) == 10 and raw[4] == '-' and raw[7] == '-':
        try:
            dt = datetime.strptime(raw, "%Y-%m-%d")
            dt = dt + timedelta(days=2)
            return dt.strftime("%d-%m-%Y")   # output in DD-MM-YYYY
        except:
            pass

    # Case 2: DD-MM-YYYY (03-12-2025)
    if len(raw) == 10 and raw[2] == '-' and raw[5] == '-':
        try:
            dt = datetime.strptime(raw, "%d-%m-%Y")
            dt = dt + timedelta(days=2)
            return dt.strftime("%d-%m-%Y")
        except:
            pass

    # Fallback: return raw value
    return raw