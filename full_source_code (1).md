
# Order Management System - Full Source Code

This document contains all the source code files for the Order Management System application. You can copy each file's content to your local machine to recreate the project.

## Project Structure

```
├── .streamlit
│   └── config.toml
├── assets
│   └── styles.css
├── main.py
├── auth.py
├── admin.py
├── picker.py
├── validator.py
├── dashboard.py
├── utils.py
├── database.py
```

## Dependencies

Before running the application, install the required dependencies:

```bash
pip install streamlit==1.31.0 pandas==2.1.1 openpyxl==3.1.2 plotly==5.18.0
```

## File Contents

### main.py

```python
import streamlit as st
import pandas as pd
import os
from auth import authenticate_user, logout_user
from admin import render_admin_panel
from picker import render_picker_panel
from validator import render_validator_panel
from dashboard import render_dashboard
import utils
from database import init_database

# App configuration and styling
st.set_page_config(
    page_title="Order Management System",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load custom CSS
with open("assets/styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Initialize database
if 'db_path' not in st.session_state:
    # Create database file in the current directory
    st.session_state.db_path = "orders.db"
    init_database(st.session_state.db_path)

# Initialize session state for authentication
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'order_status_count' not in st.session_state:
    st.session_state.order_status_count = {'new': 0, 'picked': 0, 'validated': 0}

# App header
st.title("Order Management System")

# Sidebar for authentication
with st.sidebar:
    st.header("Login")
    
    if not st.session_state.authenticated:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_button = st.button("Login")
        
        if login_button:
            if authenticate_user(username, password):
                st.session_state.authenticated = True
                st.session_state.user_role = username  # Using username as role for simplicity
                st.success(f"Logged in as {username}")
                st.rerun()
            else:
                st.error("Invalid credentials")
    else:
        st.success(f"Logged in as {st.session_state.user_role}")
        if st.button("Logout"):
            logout_user()
            st.rerun()
    
    # Display dashboard link if authenticated
    if st.session_state.authenticated:
        st.markdown("---")
        st.header("Navigation")
        if st.button("Dashboard"):
            st.session_state.page = "dashboard"
            st.rerun()
        
        # Role-specific navigation
        if st.session_state.user_role == "admin":
            if st.button("Upload Orders"):
                st.session_state.page = "main"
                st.rerun()
        elif st.session_state.user_role == "user1":
            if st.button("Pick Orders"):
                st.session_state.page = "main"
                st.rerun()
        elif st.session_state.user_role == "user2":
            if st.button("Validate Orders"):
                st.session_state.page = "main"
                st.rerun()

# Main application content
if not st.session_state.authenticated:
    st.info("Please log in to access the system.")
else:
    # Initialize page in session state if not present
    if 'page' not in st.session_state:
        st.session_state.page = "main"
    
    # Render the appropriate page based on the user role and selected page
    if st.session_state.page == "dashboard":
        render_dashboard()
    else:
        if st.session_state.user_role == "admin":
            render_admin_panel()
        elif st.session_state.user_role == "user1":
            render_picker_panel()
        elif st.session_state.user_role == "user2":
            render_validator_panel()
        else:
            st.error("Unknown user role")
```

### database.py

```python
import sqlite3
import pandas as pd
from datetime import datetime

def get_db_connection(db_path):
    """
    Create a connection to the SQLite database
    
    Args:
        db_path: Path to the database file
    
    Returns:
        SQLite connection object
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_database(db_path):
    """
    Initialize the database with the required tables
    
    Args:
        db_path: Path to create the database file
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # Create the orders table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT NOT NULL,
        sku TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'new',
        picked_by TEXT,
        validated_by TEXT,
        platform TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        dispatch_date TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

def add_orders_to_db(db_path, orders_df, platform):
    """
    Add new orders to the database
    
    Args:
        db_path: Path to the database
        orders_df: DataFrame containing order data
        platform: Name of the platform (e.g., 'flipkart', 'meesho')
    
    Returns:
        Tuple of (success boolean, count of orders added)
    """
    try:
        conn = get_db_connection(db_path)
        cursor = conn.cursor()
        
        # Get existing order IDs to avoid duplicates
        cursor.execute("SELECT order_id FROM orders")
        existing_order_ids = set(row['order_id'] for row in cursor.fetchall())
        
        # Filter out orders that already exist
        orders_df['order_id'] = orders_df['order_id'].astype(str)
        new_orders = orders_df[~orders_df['order_id'].isin(existing_order_ids)]
        
        if new_orders.empty:
            return True, 0
        
        # Add platform information
        new_orders['platform'] = platform
        
        # Add dispatch date if available
        if 'dispatch_date' not in new_orders.columns:
            new_orders['dispatch_date'] = None
        
        # Prepare data for insertion
        order_data = []
        for _, row in new_orders.iterrows():
            order_data.append((
                row['order_id'],
                row['sku'],
                row['quantity'],
                'new',  # status
                None,   # picked_by
                None,   # validated_by
                platform,
                datetime.now(),  # created_at
                datetime.now(),  # updated_at
                row.get('dispatch_date')  # dispatch_date if available
            ))
        
        # Insert the new orders
        cursor.executemany('''
        INSERT INTO orders 
        (order_id, sku, quantity, status, picked_by, validated_by, platform, created_at, updated_at, dispatch_date) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', order_data)
        
        conn.commit()
        conn.close()
        
        return True, len(order_data)
    except Exception as e:
        print(f"Error adding orders to database: {str(e)}")
        return False, 0

def get_orders_from_db(db_path, status=None):
    """
    Get orders from the database
    
    Args:
        db_path: Path to the database
        status: Optional filter for order status
    
    Returns:
        DataFrame containing the orders
    """
    conn = get_db_connection(db_path)
    
    query = "SELECT * FROM orders"
    params = []
    
    if status:
        query += " WHERE status = ?"
        params.append(status)
    
    orders_df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    return orders_df

def get_orders_grouped_by_sku(db_path, status=None):
    """
    Get orders from database grouped by SKU
    
    Returns a DataFrame with one row per SKU, with aggregate data:
    - sku: The SKU
    - total_quantity: Sum of quantities for this SKU
    - order_count: Number of orders with this SKU
    - earliest_dispatch_date: The earliest dispatch date for this SKU
    - order_ids: List of order IDs for this SKU
    """
    # Get all relevant orders
    orders_df = get_orders_from_db(db_path, status)
    
    if orders_df.empty:
        return pd.DataFrame(columns=['sku', 'total_quantity', 'order_count', 'earliest_dispatch_date', 'order_ids'])
    
    # Group by SKU
    sku_groups = []
    for sku, group in orders_df.groupby('sku'):
        # Sort orders by dispatch date (most urgent first)
        group = group.sort_values(by='dispatch_date', na_position='last')
        
        # Get earliest dispatch date
        earliest_dispatch_date = None
        if 'dispatch_date' in group.columns:
            valid_dates = group['dispatch_date'].dropna()
            if not valid_dates.empty:
                earliest_dispatch_date = valid_dates.iloc[0]
        
        # Create a row for this SKU group
        sku_group = {
            'sku': sku,
            'total_quantity': group['quantity'].sum(),
            'order_count': len(group),
            'earliest_dispatch_date': earliest_dispatch_date,
            'order_ids': group['order_id'].tolist()
        }
        sku_groups.append(sku_group)
    
    return pd.DataFrame(sku_groups)

def update_orders_for_sku(db_path, sku, quantity_to_process, new_status, user=None):
    """
    Update the status of orders for a specific SKU, up to the given quantity
    This selects the most urgent orders first based on dispatch date
    
    Args:
        db_path: Path to the database
        sku: The SKU to update
        quantity_to_process: The quantity to process (may span multiple orders)
        new_status: The new status to set for the orders
        user: Optional user who made the change
        
    Returns:
        Tuple of (processed_quantity, processed_order_ids)
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # Get all orders for this SKU with status 'new' (for picking) or 'picked' (for validating)
    old_status = 'new' if new_status == 'picked' else 'picked' if new_status == 'validated' else None
    
    if old_status is None:
        conn.close()
        return 0, []
    
    query = f"""
    SELECT order_id, quantity, dispatch_date 
    FROM orders 
    WHERE sku = ? AND status = ?
    ORDER BY dispatch_date ASC
    """
    
    cursor.execute(query, (sku, old_status))
    orders = cursor.fetchall()
    
    # Process orders until we reach the requested quantity
    remaining_quantity = quantity_to_process
    processed_order_ids = []
    processed_quantity = 0
    
    for order_id, quantity, _ in orders:
        if remaining_quantity <= 0:
            break
            
        if remaining_quantity >= quantity:
            # Update the full order
            update_query = """
            UPDATE orders 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            """
            
            if new_status == 'picked' and user:
                update_query += ", picked_by = ?"
                cursor.execute(update_query + " WHERE order_id = ?", (new_status, user, order_id))
            elif new_status == 'validated' and user:
                update_query += ", validated_by = ?"
                cursor.execute(update_query + " WHERE order_id = ?", (new_status, user, order_id))
            else:
                cursor.execute(update_query + " WHERE order_id = ?", (new_status, order_id))
            
            remaining_quantity -= quantity
            processed_quantity += quantity
            processed_order_ids.append(order_id)
        else:
            # We need to handle this in a more complex way - create two orders
            # This would require more complex logic to split orders
            # For simplicity, we'll just update the whole order
            update_query = """
            UPDATE orders 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            """
            
            if new_status == 'picked' and user:
                update_query += ", picked_by = ?"
                cursor.execute(update_query + " WHERE order_id = ?", (new_status, user, order_id))
            elif new_status == 'validated' and user:
                update_query += ", validated_by = ?"
                cursor.execute(update_query + " WHERE order_id = ?", (new_status, user, order_id))
            else:
                cursor.execute(update_query + " WHERE order_id = ?", (new_status, order_id))
            
            processed_quantity += remaining_quantity
            processed_order_ids.append(order_id)
            remaining_quantity = 0
    
    conn.commit()
    conn.close()
    
    return processed_quantity, processed_order_ids

def calculate_order_counts(db_path):
    """
    Calculate counts of orders by status
    
    Args:
        db_path: Path to the database
    
    Returns:
        Dictionary with counts for each status
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT status, COUNT(*) as count FROM orders GROUP BY status")
    rows = cursor.fetchall()
    
    counts = {'new': 0, 'picked': 0, 'validated': 0}
    
    for row in rows:
        status = row['status']
        if status in counts:
            counts[status] = row['count']
    
    conn.close()
    return counts

def get_user_productivity(db_path):
    """
    Get productivity data by user
    
    Args:
        db_path: Path to the database
    
    Returns:
        DataFrame with user productivity data
    """
    conn = get_db_connection(db_path)
    
    # Get orders picked by each user
    picked_query = """
    SELECT picked_by as user, COUNT(*) as picked_count, SUM(quantity) as picked_quantity
    FROM orders 
    WHERE picked_by IS NOT NULL
    GROUP BY picked_by
    """
    
    # Get orders validated by each user
    validated_query = """
    SELECT validated_by as user, COUNT(*) as validated_count, SUM(quantity) as validated_quantity 
    FROM orders 
    WHERE validated_by IS NOT NULL
    GROUP BY validated_by
    """
    
    picked_df = pd.read_sql_query(picked_query, conn)
    validated_df = pd.read_sql_query(validated_query, conn)
    
    conn.close()
    
    # Merge the two dataframes
    if not picked_df.empty and not validated_df.empty:
        productivity_df = pd.merge(picked_df, validated_df, on='user', how='outer').fillna(0)
    elif not picked_df.empty:
        productivity_df = picked_df
        productivity_df['validated_count'] = 0
        productivity_df['validated_quantity'] = 0
    elif not validated_df.empty:
        productivity_df = validated_df
        productivity_df['picked_count'] = 0
        productivity_df['picked_quantity'] = 0
    else:
        productivity_df = pd.DataFrame(columns=['user', 'picked_count', 'picked_quantity', 'validated_count', 'validated_quantity'])
    
    # Convert count and quantity columns to integers
    for col in ['picked_count', 'picked_quantity', 'validated_count', 'validated_quantity']:
        if col in productivity_df.columns:
            productivity_df[col] = productivity_df[col].astype(int)
    
    return productivity_df
```

### auth.py

```python
import streamlit as st

# Simple authentication system
# In a real-world application, you would use a database and proper password hashing
USERS = {
    "admin": "admin123",
    "user1": "user123",
    "user2": "user234"
}

def authenticate_user(username, password):
    """
    Authenticates a user based on username and password.
    
    Args:
        username: The username to authenticate
        password: The password to verify
    
    Returns:
        True if authentication is successful, False otherwise
    """
    if username in USERS and USERS[username] == password:
        return True
    return False

def logout_user():
    """Clear the authentication state"""
    st.session_state.authenticated = False
    st.session_state.user_role = None
    if 'page' in st.session_state:
        st.session_state.page = "main"
```

### admin.py

```python
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
                    success, count = add_orders_to_db(st.session_state.db_path, orders_df, platform)
                    
                    if success:
                        if count > 0:
                            st.success(f"Added {count} new orders from {platform.capitalize()}")
                        else:
                            st.info("No new orders found in the file")
                            
                        # Show preview of all orders
                        with st.expander("Preview Processed Data"):
                            # Get latest data from database
                            preview_df = get_orders_from_db(st.session_state.db_path)
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
        
        order_counts = calculate_order_counts(st.session_state.db_path)
        
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
        orders_df = get_orders_from_db(st.session_state.db_path)
        if not orders_df.empty:
            st.dataframe(orders_df)
        else:
            st.info("No orders in the database yet")
```

### picker.py

```python
import streamlit as st
import pandas as pd
from utils import get_swipe_card_html
from database import get_orders_grouped_by_sku, update_orders_for_sku, calculate_order_counts
import time

def render_picker_panel():
    """Render the picker panel for User1 to pick orders"""
    st.header("Order Picking")
    
    # Get orders grouped by SKU
    sku_groups = get_orders_grouped_by_sku(st.session_state.db_path, status='new')
    
    if sku_groups.empty:
        st.info("No orders available to pick. Please wait for the admin to upload orders.")
        return
    
    # Display the number of SKUs to pick
    st.subheader(f"{len(sku_groups)} SKUs to Pick")
    
    # Display the first SKU group
    current_sku_group = sku_groups.iloc[0]
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
        js = f"""
        <script>
        const pickCard = document.getElementById('pick_card_{sku}');
        let startX, movedX;
        
        pickCard.addEventListener('touchstart', function(e) {{
            startX = e.touches[0].clientX;
        }}, false);
        
        pickCard.addEventListener('touchmove', function(e) {{
            movedX = e.touches[0].clientX - startX;
            
            // Restrict horizontal movement
            if (Math.abs(movedX) < 200) {{
                pickCard.style.transform = `translateX(${{movedX}}px)`;
                
                // Change background color based on swipe direction
                if (movedX > 50) {{
                    pickCard.style.backgroundColor = '#c8e6c9'; // Green for right swipe (Pick)
                }} else if (movedX < -50) {{
                    pickCard.style.backgroundColor = '#ffcdd2'; // Red for left swipe (Skip)
                }} else {{
                    pickCard.style.backgroundColor = '#ffffff'; // Default white
                }}
            }}
        }}, false);
        
        pickCard.addEventListener('touchend', function(e) {{
            if (movedX > 100) {{
                // Right swipe - Pick the SKU
                pickCard.style.transform = 'translateX(1000px)';
                pickCard.style.opacity = '0';
                setTimeout(() => {{
                    // Submit a form to tell Streamlit the SKU was picked
                    document.getElementById('pick_action').value = 'pick';
                    document.getElementById('pick_sku').value = '{sku}';
                    document.getElementById('pick_quantity').value = '{total_quantity}';
                    document.getElementById('pick_form').submit();
                }}, 300);
            }} else if (movedX < -100) {{
                // Left swipe - Skip the SKU
                pickCard.style.transform = 'translateX(-1000px)';
                pickCard.style.opacity = '0';
                setTimeout(() => {{
                    // Submit a form to tell Streamlit the SKU was skipped
                    document.getElementById('pick_action').value = 'skip';
                    document.getElementById('pick_sku').value = '{sku}';
                    document.getElementById('pick_form').submit();
                }}, 300);
            }} else {{
                // Reset card position
                pickCard.style.transform = 'translateX(0)';
                pickCard.style.backgroundColor = '#ffffff';
            }}
        }}, false);
        </script>
        """
        st.markdown(js, unsafe_allow_html=True)
        
        # Hidden form to capture swipe actions
        with st.form(key="pick_form", clear_on_submit=True):
            st.markdown('<div class="pick_form">', unsafe_allow_html=True)
            st.markdown("<p style='display:none'>Form for swipe actions</p>", unsafe_allow_html=True)
            action = st.text_input("Action", key="pick_action", label_visibility="collapsed")
            sku_input = st.text_input("SKU", key="pick_sku", label_visibility="collapsed")
            quantity_input = st.text_input("Quantity", key="pick_quantity", label_visibility="collapsed")
            submitted = st.form_submit_button("Submit", use_container_width=True)
            
            if submitted:
                # Process the swipe action
                if action == "pick":
                    # Update the order status to 'picked'
                    processed_quantity, processed_order_ids = update_orders_for_sku(
                        st.session_state.db_path, 
                        sku_input, 
                        int(quantity_input), 
                        'picked',
                        st.session_state.user_role
                    )
                    
                    # Show success message
                    if processed_quantity > 0:
                        st.success(f"Picked {processed_quantity} units of {sku_input}!")
                
                # In both cases (pick or skip), we'll load the next SKU
                time.sleep(0.5)  # Brief delay for better UX
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    
    # Alternative button controls for desktop users
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Skip", key="skip_button", use_container_width=True):
            # Skip this SKU and move to the next
            st.rerun()
    
    with col2:
        if st.button("Pick ➡️", key="pick_button", use_container_width=True):
            # Update the order status to 'picked'
            processed_quantity, processed_order_ids = update_orders_for_sku(
                st.session_state.db_path, 
                sku, 
                total_quantity, 
                'picked',
                st.session_state.user_role
            )
            
            # Show success message
            if processed_quantity > 0:
                st.success(f"Picked {processed_quantity} units of {sku}!")
            
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
            st.session_state.db_path, 
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
```

### validator.py

```python
import streamlit as st
import pandas as pd
from utils import get_swipe_card_html
from database import get_orders_grouped_by_sku, update_orders_for_sku, calculate_order_counts
import time

def render_validator_panel():
    """Render the validator panel for User2 to validate picked orders"""
    st.header("Order Validation")
    
    # Get picked orders grouped by SKU
    sku_groups = get_orders_grouped_by_sku(st.session_state.db_path, status='picked')
    
    if sku_groups.empty:
        st.info("No picked orders to validate. Please wait for User1 to pick some orders.")
        return
    
    # Display the number of SKUs to validate
    st.subheader(f"{len(sku_groups)} SKUs to Validate")
    
    # Display the first SKU group
    current_sku_group = sku_groups.iloc[0]
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
        js = f"""
        <script>
        const validateCard = document.getElementById('validate_card_{sku}');
        let startX, movedX;
        
        validateCard.addEventListener('touchstart', function(e) {{
            startX = e.touches[0].clientX;
        }}, false);
        
        validateCard.addEventListener('touchmove', function(e) {{
            movedX = e.touches[0].clientX - startX;
            
            // Restrict horizontal movement
            if (Math.abs(movedX) < 200) {{
                validateCard.style.transform = `translateX(${{movedX}}px)`;
                
                // Change background color based on swipe direction
                if (movedX > 50) {{
                    validateCard.style.backgroundColor = '#c8e6c9'; // Green for right swipe (Validate)
                }} else if (movedX < -50) {{
                    validateCard.style.backgroundColor = '#ffcdd2'; // Red for left swipe (Reject)
                }} else {{
                    validateCard.style.backgroundColor = '#ffffff'; // Default white
                }}
            }}
        }}, false);
        
        validateCard.addEventListener('touchend', function(e) {{
            if (movedX > 100) {{
                // Right swipe - Validate the SKU
                validateCard.style.transform = 'translateX(1000px)';
                validateCard.style.opacity = '0';
                setTimeout(() => {{
                    // Submit a form to tell Streamlit the SKU was validated
                    document.getElementById('validate_action').value = 'validate';
                    document.getElementById('validate_sku').value = '{sku}';
                    document.getElementById('validate_quantity').value = '{total_quantity}';
                    document.getElementById('validate_form').submit();
                }}, 300);
            }} else if (movedX < -100) {{
                // Left swipe - Reject the SKU
                validateCard.style.transform = 'translateX(-1000px)';
                validateCard.style.opacity = '0';
                setTimeout(() => {{
                    // Submit a form to tell Streamlit the SKU was rejected
                    document.getElementById('validate_action').value = 'reject';
                    document.getElementById('validate_sku').value = '{sku}';
                    document.getElementById('validate_quantity').value = '{total_quantity}';
                    document.getElementById('validate_form').submit();
                }}, 300);
            }} else {{
                // Reset card position
                validateCard.style.transform = 'translateX(0)';
                validateCard.style.backgroundColor = '#ffffff';
            }}
        }}, false);
        </script>
        """
        st.markdown(js, unsafe_allow_html=True)
        
        # Hidden form to capture swipe actions
        with st.form(key="validate_form", clear_on_submit=True):
            st.markdown('<div class="validate_form">', unsafe_allow_html=True)
            st.markdown("<p style='display:none'>Form for validation actions</p>", unsafe_allow_html=True)
            action = st.text_input("Action", key="validate_action", label_visibility="collapsed")
            sku_input = st.text_input("SKU", key="validate_sku", label_visibility="collapsed")
            quantity_input = st.text_input("Quantity", key="validate_quantity", label_visibility="collapsed")
            submitted = st.form_submit_button("Submit", use_container_width=True)
            
            if submitted:
                # Process the swipe action
                if action == "validate":
                    # Update the order status to 'validated'
                    processed_quantity, processed_order_ids = update_orders_for_sku(
                        st.session_state.db_path, 
                        sku_input, 
                        int(quantity_input), 
                        'validated',
                        st.session_state.user_role
                    )
                    
                    # Show success message
                    if processed_quantity > 0:
                        st.success(f"Validated {processed_quantity} units of {sku_input}!")
                
                elif action == "reject":
                    # Reset the order status to 'new'
                    processed_quantity, processed_order_ids = update_orders_for_sku(
                        st.session_state.db_path, 
                        sku_input, 
                        int(quantity_input), 
                        'new',
                        None  # No user for rejected orders
                    )
                    
                    # Show info message
                    if processed_quantity > 0:
                        st.info(f"Rejected {processed_quantity} units of {sku_input} and returned to picking queue.")
                
                # In both cases, we'll load the next SKU
                time.sleep(0.5)  # Brief delay for better UX
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    
    # Alternative button controls for desktop users
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Reject", key="reject_button", use_container_width=True):
            # Reset the order status to 'new'
            processed_quantity, processed_order_ids = update_orders_for_sku(
                st.session_state.db_path, 
                sku, 
                total_quantity, 
                'new',
                None  # No user for rejected orders
            )
            
            # Show info message
            if processed_quantity > 0:
                st.info(f"Rejected {processed_quantity} units of {sku} and returned to picking queue.")
            
            time.sleep(0.5)  # Brief delay for better UX
            st.rerun()
    
    with col2:
        if st.button("Validate ➡️", key="validate_button", use_container_width=True):
            # Update the order status to 'validated'
            processed_quantity, processed_order_ids = update_orders_for_sku(
                st.session_state.db_path, 
                sku, 
                total_quantity, 
                'validated',
                st.session_state.user_role
            )
            
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
            st.session_state.db_path, 
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
```

### dashboard.py

```python
import streamlit as st
import pandas as pd
import plotly.express as px
from utils import export_orders_to_excel
from database import get_orders_from_db, calculate_order_counts, get_user_productivity

def render_dashboard():
    """Render the dashboard with order statistics and visualizations"""
    st.header("Order Management Dashboard")
    
    # Check if database exists
    if 'db_path' not in st.session_state:
        st.info("Database not initialized. Please reload the application.")
        return
    
    # Get current order counts
    order_counts = calculate_order_counts(st.session_state.db_path)
    
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
        productivity_df = get_user_productivity(st.session_state.db_path)
        
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
        
        excel_data = export_orders_to_excel(st.session_state.db_path)
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
        orders_df = get_orders_from_db(st.session_state.db_path)
        if not orders_df.empty:
            st.dataframe(orders_df, use_container_width=True)
        else:
            st.info("No orders available")
    
    with tab2:
        new_orders = get_orders_from_db(st.session_state.db_path, status='new')
        if not new_orders.empty:
            st.dataframe(new_orders, use_container_width=True)
        else:
            st.info("No new orders available")
    
    with tab3:
        picked_orders = get_orders_from_db(st.session_state.db_path, status='picked')
        if not picked_orders.empty:
            st.dataframe(picked_orders, use_container_width=True)
        else:
            st.info("No picked orders available")
    
    with tab4:
        validated_orders = get_orders_from_db(st.session_state.db_path, status='validated')
        if not validated_orders.empty:
            st.dataframe(validated_orders, use_container_width=True)
        else:
            st.info("No validated orders available")
```

### utils.py

```python
import pandas as pd
import streamlit as st
import io
from datetime import datetime, timedelta
from database import get_orders_from_db

def extract_order_data(file_buffer, platform):
    """
    Extracts order data from Excel file or CSV file based on selected platform.
    
    Args:
        file_buffer: The uploaded file buffer (Excel or CSV)
        platform: Either 'flipkart' or 'meesho'
    
    Returns:
        DataFrame with extracted order data or None on error
    """
    try:
        # Determine file type and read accordingly
        file_name = file_buffer.name.lower()
        if file_name.endswith('.csv'):
            df = pd.read_csv(file_buffer)
        else:  # Excel file (.xlsx or .xls)
            df = pd.read_excel(file_buffer)
        
        # Create a new dataframe with the required columns
        orders_df = pd.DataFrame(columns=['order_id', 'sku', 'quantity', 'status', 'dispatch_date'])
        
        # Extract data based on platform
        if platform == 'meesho':
            # Meesho: ORDER ID (Column B), SKU (Column F), QUANTITY (Column H)
            orders_df['order_id'] = df.iloc[:, 1]  # Column B (index 1)
            orders_df['sku'] = df.iloc[:, 5]       # Column F (index 5)
            orders_df['quantity'] = df.iloc[:, 7]  # Column H (index 7)
            
            # Check if there's a dispatch date column (example - Column J)
            if df.shape[1] > 9:  # Check if column J exists
                orders_df['dispatch_date'] = df.iloc[:, 9]  # Column J (index 9)
            else:
                # Default dispatch to 3 days from now
                orders_df['dispatch_date'] = datetime.now() + timedelta(days=3)
                
        elif platform == 'flipkart':
            # Flipkart: ORDER ID (Column D), SKU (Column I), QUANTITY (Column S)
            orders_df['order_id'] = df.iloc[:, 3]   # Column D (index 3)
            orders_df['sku'] = df.iloc[:, 8]        # Column I (index 8)
            orders_df['quantity'] = df.iloc[:, 18]  # Column S (index 18)
            
            # Check if there's a dispatch date column (example - Column R)
            if df.shape[1] > 17:  # Check if column R exists
                orders_df['dispatch_date'] = df.iloc[:, 17]  # Column R (index 17)
            else:
                # Default dispatch to 3 days from now
                orders_df['dispatch_date'] = datetime.now() + timedelta(days=3)
        else:
            st.error("Invalid platform selected")
            return None
        
        # Initialize status as 'new'
        orders_df['status'] = 'new'
        
        # Clean and validate data
        orders_df = orders_df.dropna(subset=['order_id', 'sku'])
        orders_df['quantity'] = orders_df['quantity'].fillna(1).astype(int)
        
        # Convert dispatch_date to datetime if it's not None
        if 'dispatch_date' in orders_df.columns:
            orders_df['dispatch_date'] = pd.to_datetime(orders_df['dispatch_date'], errors='coerce')
            # For any NaT values, set to 3 days from now
            orders_df.loc[orders_df['dispatch_date'].isna(), 'dispatch_date'] = datetime.now() + timedelta(days=3)
        
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

def export_orders_to_excel(db_path):
    """
    Export orders to Excel file for download
    
    Args:
        db_path: Path to the database
    
    Returns:
        Excel file as bytes or None if no orders exist
    """
    # Get latest orders from database
    orders_df = get_orders_from_db(db_path)
    
    if orders_df.empty:
        return None
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        orders_df.to_excel(writer, index=False)
    
    return output.getvalue()
```

### assets/styles.css

```css
/* Main Styles */
.stApp {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

/* Swipe Card Styles */
.swipe-card {
    position: relative;
    width: 100%;
    max-width: 600px;
    margin: 0 auto 20px;
    padding: 20px;
    border-radius: 10px;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
    background-color: #ffffff;
    transition: transform 0.3s, opacity 0.3s, background-color 0.3s;
    user-select: none;
    touch-action: pan-y;
    cursor: grab;
}

.card-content {
    pointer-events: none;
}

.swipe-actions {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 20px;
    opacity: 0.5;
    font-weight: bold;
    font-size: 18px;
}

.swipe-left {
    color: #d32f2f;
    text-align: left;
}

.swipe-right {
    color: #2e7d32;
    text-align: right;
}

/* Button Styles */
.stButton button {
    border-radius: 8px;
    font-weight: 600;
    transition: all 0.2s;
}

/* Dashboard Card Styles */
.css-1r6slb0 {
    background-color: #f8f9fa;
    border-radius: 10px;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);
    padding: 20px;
    margin-bottom: 20px;
}

/* Status Color Indicators */
.status-new {
    color: #FFA726;
    font-weight: bold;
}

.status-picked {
    color: #42A5F5;
    font-weight: bold;
}

.status-validated {
    color: #66BB6A;
    font-weight: bold;
}

/* Hide Form Submit Buttons */
.pick_form .stButton, .validate_form .stButton {
    display: none;
}

/* Mobile Optimization */
@media (max-width: 768px) {
    .swipe-card {
        padding: 15px;
    }
    
    .swipe-actions {
        font-size: 16px;
    }
}
```

### .streamlit/config.toml

```toml
[server]
headless = true
address = "0.0.0.0"
port = 5000

[theme]
primaryColor = "#FF4B4B"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"
```

## How to Run the Application

1. Create the directory structure shown above
2. Save each file with its appropriate content
3. Install the dependencies: `pip install streamlit pandas openpyxl plotly`
4. Run the application: `streamlit run main.py`

## User Credentials

- Admin: username = `admin`, password = `admin123`
- User 1 (Picker): username = `user1`, password = `user123`
- User 2 (Validator): username = `user2`, password = `user234`

## Data Format Requirements

The application processes Excel or CSV files with the following column mappings:

### Meesho Format
- Order ID: Column B
- SKU: Column F
- Quantity: Column H
- Dispatch Date: Column J (optional)

### Flipkart Format
- Order ID: Column D
- SKU: Column I
- Quantity: Column S
- Dispatch Date: Column R (optional)

## Key Improvements

1. Persistent database storage with SQLite instead of in-memory session state
2. Added dispatch date tracking for order prioritization
3. SKU-based grouping for more efficient picking and validation
4. Partial quantity processing for orders
5. Detailed order history with timestamps
6. Enhanced user productivity tracking
