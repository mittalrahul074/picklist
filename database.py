import pandas as pd
from datetime import datetime
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os

from firebase_utils import add_order

def get_db_connection():
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
    engine = get_db_connection()
    if engine is None:
        print("Database connection failed.")
        return
    try:
        with engine.begin() as conn:
            conn.execute(text('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    order_id VARCHAR(255) NOT NULL UNIQUE,
                    sku VARCHAR(255) NOT NULL,
                    quantity INT NOT NULL,
                    status VARCHAR(50) NOT NULL DEFAULT 'new',
                    picked_by VARCHAR(255),
                    validated_by VARCHAR(255),
                    platform VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    dispatch_date DATETIME NOT NULL
                )
            '''))
            conn.commit()
    except Exception as e:
        print(f"1Error initializing database: {e}")

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

def get_orders_grouped_by_sku(status=None):
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
    db = get_db_connection()

    orders_ref = db.collection("orders")

    # Apply filter only if status is provided
    if status:
        orders_ref = orders_ref.where(filter=FieldFilter("status", "==", status))

    orders = orders_ref.stream()

    sku_data = {}

    for order in orders:
        order_data = order.to_dict()
        order_id = order.id  # Firestore document ID
        sku = order_data.get("sku")
        quantity = order_data.get("quantity", 0)
        dispatch_date = order_data.get("dispatch_date")

        if sku not in sku_data:
            sku_data[sku] = {
                "sku": sku,
                "total_quantity": 0,
                "order_count": 0,
                "earliest_dispatch_date": dispatch_date,
                "order_ids": [],
            }

        sku_data[sku]["total_quantity"] += quantity
        sku_data[sku]["order_count"] += 1
        sku_data[sku]["order_ids"].append(order_id)

        # Update earliest dispatch date
        if sku_data[sku]["earliest_dispatch_date"] is None or (
            dispatch_date and dispatch_date < sku_data[sku]["earliest_dispatch_date"]
        ):
            sku_data[sku]["earliest_dispatch_date"] = dispatch_date

    return pd.DataFrame(sku_data.values())

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

    return processed_quantity, processed_order_ids

def calculate_order_counts():
    """
    Calculate counts of orders by status
    
    Returns:
        Dictionary with counts for each status
    """
    counts = {'new': 0, 'picked': 0, 'validated': 0}

    db = get_db_connection()

    if db is None:
        return counts

    try:
        orders_ref = db.collection("orders").where(filter=FieldFilter("status","in",["new","picked","validated"]))
        orders = orders_ref.stream()

        for order in orders:
            order_data = order.to_dict()
            status = order_data.get("status")
            if status in counts:
                counts[status] += 1

    except Exception as e:
        print(f"Error fetching order counts: {e}")

    return counts

def get_user_productivity():
    """
    Get productivity data by user from Firestore.

    Returns:
        DataFrame with user productivity data
    """
    db = get_db_connection()
    if db is None:
        return pd.DataFrame(columns=['user', 'picked_count', 'picked_quantity', 'validated_count', 'validated_quantity'])

    # Initialize dictionaries for aggregation
    picked_summary = {}
    validated_summary = {}

    try:
        # Fetch orders where picked_by is NOT NULL
        picked_orders = db.collection("orders").where(filter=FieldFilter("picked_by", "!=", None)).stream()
        for order in picked_orders:
            data = order.to_dict()
            user = data.get("picked_by")
            quantity = data.get("quantity", 0)

            if user:
                if user not in picked_summary:
                    picked_summary[user] = {"picked_count": 0, "picked_quantity": 0}
                picked_summary[user]["picked_count"] += 1
                picked_summary[user]["picked_quantity"] += quantity

        # Fetch orders where validated_by is NOT NULL
        validated_orders = db.collection("orders").where(filter=FieldFilter("validated_by", "!=", None)).stream()
        for order in validated_orders:
            data = order.to_dict()
            user = data.get("validated_by")
            quantity = data.get("quantity", 0)

            if user:
                if user not in validated_summary:
                    validated_summary[user] = {"validated_count": 0, "validated_quantity": 0}
                validated_summary[user]["validated_count"] += 1
                validated_summary[user]["validated_quantity"] += quantity

        # Merge picked and validated data
        all_users = set(picked_summary.keys()).union(set(validated_summary.keys()))
        data = []
        for user in all_users:
            data.append({
                "user": user,
                "picked_count": picked_summary.get(user, {}).get("picked_count", 0),
                "picked_quantity": picked_summary.get(user, {}).get("picked_quantity", 0),
                "validated_count": validated_summary.get(user, {}).get("validated_count", 0),
                "validated_quantity": validated_summary.get(user, {}).get("validated_quantity", 0),
            })

        # Convert to DataFrame
        productivity_df = pd.DataFrame(data)

    except Exception as e:
        print(f"Error fetching user productivity: {e}")
        return pd.DataFrame(columns=['user', 'picked_count', 'picked_quantity', 'validated_count', 'validated_quantity'])

    return productivity_df