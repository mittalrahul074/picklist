import pandas as pd
from datetime import datetime, timedelta
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import FieldFilter
import json
import os
import traceback

from firebase_utils import add_order
from google.cloud.firestore import FieldFilter

def get_db_connection():
    print("🔥 Database accessed from:")
    traceback.print_stack(limit=3)
    try:
        firebase_credentials = dict(st.secrets["firebase"])  # Convert secrets to dict

        # Initialize Firebase if not already initialized
        if not firebase_admin._apps:
            cred = credentials.Certificate(firebase_credentials)  # Use dictionary directly
            firebase_admin.initialize_app(cred)

        # Connect to Firestore
        db = firestore.client()
        return db

    except Exception as e:
        print(f"Error connecting to Firestore: {e}")
        return None

def init_database():
    """
    Initialize the database with the required tables
    
    Args:
        db_path: Path to create the database file
    """
    # engine = get_db_connection()
    # if engine is None:
    #     print("Database connection failed.")
    #     return
    # try:
    #     with engine.begin() as conn:
    #         conn.execute(text('''
    #             CREATE TABLE IF NOT EXISTS orders (
    #                 id INT AUTO_INCREMENT PRIMARY KEY,
    #                 order_id VARCHAR(255) NOT NULL UNIQUE,
    #                 sku VARCHAR(255) NOT NULL,
    #                 quantity INT NOT NULL,
    #                 status VARCHAR(50) NOT NULL DEFAULT 'new',
    #                 picked_by VARCHAR(255),
    #                 validated_by VARCHAR(255),
    #                 platform VARCHAR(255),
    #                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    #                 updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    #                 dispatch_date DATETIME NOT NULL
    #             )
    #         '''))
    #         conn.commit()
    # except Exception as e:
    #     print(f"1Error initializing database: {e}")

def add_orders_to_db(orders_df, platform):
    """
    Add new orders to the database
    
    Args:
        orders_df: DataFrame containing order data
        platform: Name of the platform (e.g., 'flipkart', 'meesho')
    
    Returns:
        Tuple of (success boolean, count of orders added)
    """
    db = get_db_connection()
    if db is None:
        print("Database connection failed.")
        return False, 0

    batch = db.batch()  # Create a batch write object
    added_count = 0  # Track only successfully added orders

    try:
        for _, row in orders_df.iterrows():
            order_id = str(row["order_id"])
            doc_ref = db.collection("orders").document(order_id)
            # Skip if order already exists (check from our local set)
            doc_snapshot = doc_ref.get()
            if doc_snapshot.exists:
                continue

            # Add order to batch
            batch.set(doc_ref, {
                "sku": row["sku"],
                "quantity": row["quantity"],
                "status": "new",  # Default status
                "picked_by": "",
                "validated_by": "",
                "platform": platform,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "dispatch_date": row["dispatch_date"] if pd.notna(row["dispatch_date"]) else None
            })
            added_count += 1  # Increment only when added

            # Firestore allows a maximum of 500 operations per batch
            if added_count % 500 == 0:
                batch.commit()  # Commit the batch every 500 inserts
                batch = db.batch()  # Start a new batch

        # Commit any remaining writes
        batch.commit()

        st.session_state.orders_df = get_orders_from_db()

        return True, added_count  # Return count of successfully inserted orders

    except Exception as e:
        print(f"Database error: {e}")
        return False, added_count


def get_orders_from_db(status=None):
    """
    Get orders from the database
    
    Args:
        db_path: Path to the database
        status: Optional filter for order status
    
    Returns:
        DataFrame containing the orders
    """

    db = get_db_connection()
    orders_ref = db.collection("orders")

    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    query = orders_ref.where(filter=FieldFilter("created_at", ">=", seven_days_ago))

    # Apply status filter if provided
    if status:
        query = orders_ref.where(filter=FieldFilter("status", "==", status))

    orders = orders_ref.stream()
    order_list = []

    order_list = [
        {**order.to_dict(), "order_id": order.id}  # Merge Firestore data with ID
        for order in orders
    ]

    return pd.DataFrame(order_list)  if order_list else pd.DataFrame()

def get_orders_grouped_by_sku(orders_df, status=None):
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
    if orders_df.empty:
        return pd.DataFrame()  # Return empty DataFrame if no data

    # Filter by status if provided
    if status:
        orders_df = orders_df[orders_df["status"] == status]

    # Convert dispatch_date to datetime
    orders_df = orders_df.copy()
    orders_df["dispatch_date"] = pd.to_datetime(orders_df["dispatch_date"], errors="coerce")

    # Group data by SKU
    grouped_df = orders_df.groupby("sku").agg(
        total_quantity=pd.NamedAgg(column="quantity", aggfunc="sum"),
        order_count=pd.NamedAgg(column="order_id", aggfunc="count"),
        earliest_dispatch_date=pd.NamedAgg(column="dispatch_date", aggfunc="min"),
        order_ids=pd.NamedAgg(column="order_id", aggfunc=lambda x: list(x))
    ).reset_index()

    return grouped_df

def update_orders_for_sku(sku, quantity_to_process, new_status, user=None):
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
    db = get_db_connection()
    
    # Get all orders for this SKU with status 'new' (for picking) or 'picked' (for validating)
    old_status = 'new' if new_status == 'picked' else 'picked' if new_status == 'validated' else None
    
    if old_status is None:
        return 0, []
    
    orders_ref = db.collection("orders")
    orders_ref = db.collection("orders") \
               .where(filter=firestore.FieldFilter("sku", "==", sku)) \
               .where(filter=firestore.FieldFilter("status", "==", old_status)) \
               .order_by("dispatch_date").stream()

    remaining_quantity = quantity_to_process
    processed_order_ids = []
    processed_quantity = 0

    batch = db.batch()

    for order in orders_ref:
        order_data = order.to_dict()
        order_id = order.id
        order_quantity = order_data["quantity"]

        # Determine how much of this order to process
        processed_now = min(order_quantity, remaining_quantity)

        order_ref = db.collection("orders").document(order_id)
        # Prepare update data
        update_data = {
            "status": new_status,
            "updated_at": datetime.utcnow()
        }

        if new_status == "picked" and user:
            update_data["picked_by"] = user
        elif new_status == "validated" and user:
            update_data["validated_by"] = user

        batch.update(order.reference, update_data)

        remaining_quantity -= processed_now
        processed_quantity += processed_now
        processed_order_ids.append(order_id)

    batch.commit()

    if "orders_df" in st.session_state:
        df = st.session_state.orders_df.copy()

        # Update status in DataFrame for processed orders
        df.loc[df["order_id"].isin(processed_order_ids), "status"] = new_status

        # Save updated DataFrame back to session state
        st.session_state.orders_df = df

    return processed_quantity, processed_order_ids

def calculate_order_counts():
    """
    Calculate counts of orders by status
    
    Returns:
        Dictionary with counts for each status
    """
    counts = {'new': 0, 'picked': 0, 'validated': 0}

    if "orders_df" not in st.session_state:
        st.session_state.orders_df = get_orders_from_db()

    orders_df = st.session_state.orders_df  # Get the cached orders DataFrame

    if not orders_df.empty:
        counts = orders_df["status"].value_counts().to_dict()  # Count occurrences of each status
    
    # Ensure all statuses are included (even if 0)
    for status in ["new", "picked", "validated"]:
        counts.setdefault(status, 0)

    return counts

def get_user_productivity():
    """
    Get productivity data by user from Firestore.

    Returns:
        DataFrame with user productivity data
    """
    if "orders_df" not in st.session_state or st.session_state.orders_df.empty:
        return pd.DataFrame(columns=['user', 'picked_count', 'picked_quantity', 'validated_count', 'validated_quantity'])

    orders_df = st.session_state.orders_df

    # Filter and group data for picked orders
    picked_summary = (
        orders_df[orders_df["picked_by"].notna()]
        .groupby("picked_by")
        .agg(picked_count=("picked_by", "count"), picked_quantity=("quantity", "sum"))
        .reset_index()
        .rename(columns={"picked_by": "user"})
    )

    # Filter and group data for validated orders
    validated_summary = (
        orders_df[orders_df["validated_by"].notna()]
        .groupby("validated_by")
        .agg(validated_count=("validated_by", "count"), validated_quantity=("quantity", "sum"))
        .reset_index()
        .rename(columns={"validated_by": "user"})
    )

    # Merge both summaries
    productivity_df = pd.merge(picked_summary, validated_summary, on="user", how="outer").fillna(0)

    # Convert count/quantity columns to integer type
    for col in ["picked_count", "picked_quantity", "validated_count", "validated_quantity"]:
        productivity_df[col] = productivity_df[col].astype(int)

    return productivity_df