"""
Order management functions for Firestore database
"""
import re
from db.firestore import get_db_connection
from datetime import datetime, timedelta
from firebase_admin import firestore
import pandas as pd
import streamlit as st
import time

def load_orders(force=False):
    """Load orders into session state safely"""
    if force or "orders_df" not in st.session_state:
        st.session_state.orders_df = get_orders_from_db()

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
                "sku": row["sku"].upper(),
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
    
    db = get_db_connection()
    if db is None:
        error_msg =     "❌ Database connection failed in get_orders_from_db"
        print(error_msg)
        st.warning(error_msg)
        return pd.DataFrame()
    
    orders_ref = db.collection("orders")
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    try:
        # print(f"🔍 DEBUG: Querying orders from last 7 days (since {seven_days_ago})")
        time.sleep(0.5)  # slight delay for UX
        
        query = orders_ref.where("created_at", ">=", seven_days_ago)

        # Apply status filter if provided
        if status:
            # print(f"🔍 DEBUG: Applying status filter: {status}")
            query = query.where("status", "==", status)
            time.sleep(0.5)  # slight delay for UX

        orders = list(query.stream())
        # print(f"✅ DEBUG: Found {len(orders)} orders from Firestore")
        time.sleep(0.5)  # slight delay for UX
        
        order_list = [
            {**order.to_dict(), "order_id": order.id}
            for order in orders
        ]

        df = pd.DataFrame(order_list) if order_list else pd.DataFrame()
        # print(f"✅ DEBUG: Created DataFrame with {len(df)} rows and columns: {list(df.columns) if not df.empty else []}")
        time.sleep(0.5)  # slight delay for UX

        return df
        
    except Exception as e:
        error_msg = f"❌ Error fetching orders from database: {e}"
        print(error_msg)
        st.warning(error_msg)
        return pd.DataFrame()

def get_order_details(order_id):
    
    db = get_db_connection()
    if db is None:
        error_msg =     "❌ Database connection failed in get_order_details"
        print(error_msg)
        st.warning(error_msg)
        return None
    
    order_ref = db.collection("orders").document(order_id)

    try:
        order_doc = order_ref.get()
        if not order_doc.exists:
            error_msg = f"❌ Order {order_id} not found in Firestore."
            print(error_msg)
            st.warning(error_msg)
            return None
        
        order_data = order_doc.to_dict()
        order_data["order_id"] = order_doc.id
        return order_data
        
    except Exception as e:
        error_msg = f"❌ Error fetching order {order_id} from database: {e}"
        print(error_msg)
        st.warning(error_msg)
        return None

def update_status(order_id,status, platform, where=None):
    db = get_db_connection()
    orders_ref = db.collection("orders").document(order_id)

    order_data = orders_ref.get().to_dict()  # Fetch order data safely
    
    if order_data:
        if where:
            if order_data.get("status") != where:
                print(f"⚠️ Order {order_id} status is not {where}. Skipping update.")
                cancelled_ref = db.collection("cancelled_orders").document(order_id)
                cancelled_ref.set({
                    "order_id": order_id,
                    "status": status,
                    "platform": platform,
                    "timestamp": datetime.utcnow()
                })
                return
        orders_ref.update({"status": status, "updated_at": datetime.utcnow(), "validated_by": platform})
        print(f"✅ Order {order_id} {status}.")
    else:
        print(f"⚠️ Order {order_id} not found in Firestore.")

def bulk_update_status(cancelled_df: pd.DataFrame, platform: str):
    db = get_db_connection()
    if db is None:
        return

    BATCH_LIMIT = 500
    batch = db.batch()
    op_count = 0

    for _, row in cancelled_df.iterrows():
        order_id = str(row.iloc[1]).strip()
        status = str(row.iloc[0]).strip().lower()

        if not order_id:
            continue

        order_ref = db.collection("orders").document(order_id)

        batch.set(
            order_ref,
            {
                "status": status,
                "updated_at": datetime.utcnow(),
                "validated_by": platform
            },
            merge=True  # 👈 no read required
        )

        op_count += 1

        # Commit every 500 writes
        if op_count == BATCH_LIMIT:
            batch.commit()
            batch = db.batch()
            op_count = 0

    # Commit remaining writes
    if op_count > 0:
        batch.commit()

    print("✅ Bulk status update completed")


def get_orders_grouped_by_sku(orders_df, status=None):
    """
    Groups orders by SKU and dispatch date, ensuring earliest dispatch orders come first.
    """

    try:
        if orders_df.empty:
            print("⚠️ Warning: orders_df is empty before processing.")
            return pd.DataFrame()

        # Create a working copy
        orders_df = orders_df.copy()

        # print("Raw dispatch_date values:", orders_df["dispatch_date"].head(5).tolist())

        # Convert dispatch_date to datetime format
        # orders_df["dispatch_date"] = pd.to_datetime(orders_df["dispatch_date"], dayfirst=True, errors="coerce")

        # print("After conversion, dispatch_date sample:\n", orders_df[['dispatch_date']].head())

        # Filter by status if provided
        if status:
            orders_df = orders_df[orders_df["status"] == status]
            
        if orders_df.empty:
            print("⚠️ Warning: No matching records after status filter.")
            return pd.DataFrame()
        # Remove rows with invalid dispatch_date
        orders_df = orders_df.dropna(subset=['dispatch_date'])


        def get_dispatch_breakdown(sub_df):
            grouped = sub_df.groupby("dispatch_date")["quantity"].sum().reset_index()
            return [
                {
                    "date": row["dispatch_date"],
                    "quantity": int(row["quantity"])
                }
                for _, row in grouped.iterrows()
            ]

        # Group by SKU and dispatch_date
        grouped_df = orders_df.groupby("sku").apply(lambda df: pd.Series({
            "total_quantity": int(df["quantity"].sum()),
            "order_count": df["order_id"].nunique(),
            "dispatch_breakdown": get_dispatch_breakdown(df)
        })).reset_index()

        # Sort by dispatch date (earliest first)
        grouped_df = grouped_df.sort_values(by=["sku"], ascending=[True])

        return grouped_df

    except Exception as e:
        print(f"Error in grouping orders: {str(e)}")
        raise

def get_product_image_url(sku):
    try:
        db = get_db_connection()
        if db is None:
            return None
        
        sku_lower = sku.lower().strip()
        products_ref = db.collection("products").where("sku", "==", sku_lower).limit(1)
        docs = list(products_ref.stream())
        
        if not docs:
            return None
        
        return docs[0].to_dict().get("img_url")
    except Exception as e:
        print(f"Error fetching product image URL for SKU {sku}: {e}")
        return None

def update_orders_for_sku(sku, quantity_to_process, new_status, user=None):
    """
    Safe race-condition-free update for a specific SKU + dispatch_date.
    Uses Firestore transaction to prevent multiple users from corrupting data.
    """

    db = get_db_connection()
    if db is None:
        print("❌ DEBUG: Database connection failed")
        # st.error("❌ Database connection failed")
        return 0, []

    transaction = db.transaction()

    # Determine old status → what we are converting *from*
    old_status = (
        "picked" if new_status =="new" else
        "new" if new_status == "picked" else
        "picked" if new_status == "validated" else
        "picked" if new_status == "cancelled" else
        "picked" if new_status == "wrong" else
        None
    )

    print(f"🔍 DEBUG: old_status={old_status}, new_status={new_status}, sku={sku}, quantity={quantity_to_process}, user={user}")
    # st.write(f"🔍 DEBUG: old_status={old_status}, new_status={new_status}, sku={sku}")

    if old_status is None:
        print("❌ DEBUG: old_status is None - invalid transition")
        # st.error("❌ Invalid status transition")
        return 0, []

    @firestore.transactional
    def process(transaction):
        print(f"📝 DEBUG: Starting transaction for sku={sku}, old_status={old_status}")
        
        # STEP 1 — READ orders safely inside transaction
        high_query = (
            db.collection("orders")
            .where("sku", "==", sku)
            .where("status", "==", old_status)
            .where("quantity", ">", 1)
            .order_by("created_at")
        )

        low_query = (
            db.collection("orders")
            .where("sku", "==", sku)
            .where("status", "==", old_status)
            .where("quantity", "==", 1)
            .order_by("created_at")
        )

        high_orders = list(transaction.get(high_query))
        low_orders = list(transaction.get(low_query))


        high_total_available = sum(order.to_dict().get("quantity", 0) for order in high_orders)
        low_total_available = sum(order.to_dict().get("quantity", 0) for order in low_orders)
        total_available = high_total_available + low_total_available
        print(f"📝 DEBUG: Total available quantity for SKU={sku} is {total_available}")
        # st.write(f"📝 DEBUG: Total available quantity for SKU={sku} is {total_available}")

        # CRITICAL VALIDATION
        if total_available < quantity_to_process:
            print(f"⚠️ DEBUG: Insufficient orders. Found {total_available}, needed {quantity_to_process}")
            # st.warning(f"⚠️ Only {total_available} orders available instead of {quantity_to_process}")
            # st.warning("Updating local order cache to reflect current database state.")
            st.session_state.orders_df = get_orders_from_db()
            
            return -1, []

        processed_ids = []
        remaining_quantity = quantity_to_process
        processed_quantity = 0
        selected = []

        if remaining_quantity > 0:
            for order in high_orders:
                qty = order.to_dict().get("quantity", 1)
                if qty <= remaining_quantity:
                    selected.append(order)
                    remaining_quantity -= qty

        if remaining_quantity > 0:
            for order in low_orders:
                qty = order.to_dict().get("quantity", 1)
                if qty <= remaining_quantity:
                    selected.append(order)
                    remaining_quantity -= qty

        if remaining_quantity != 0:
            print(f"❌ DEBUG: Logic error - remaining_quantity should be 0 but is {remaining_quantity}")
            # st.error(f"❌ Logic error - remaining_quantity should be 0 but is {remaining_quantity}")
            return -1, []
        print(f"📝 DEBUG: Selected {len(selected)} orders for processing")

        # STEP 2 — UPDATE ORDER-BY-ORDER inside the same transaction
        for order in selected:
            ref = order.reference
            update_fields = {
                "status": new_status,
                "updated_at": datetime.utcnow()
            }

            if new_status == "new":
                update_fields = {
                    "status": new_status,
                    "picked_by": "",
                    "updated_at": datetime.utcnow()
                }

            if user:
                if new_status == "cancelled":
                    update_fields["validated_by"] = user
                else:
                    update_fields[f"{new_status}_by"] = user

            print(f"📝 DEBUG: Updating order {order.id} with fields: {update_fields}")
            transaction.update(ref, update_fields)
            # st.success(f"✅ Order {order.id} updated to {new_status}.")
            print(f"✅ Order {order.id} marked for update to {new_status}")
            processed_ids.append(order.id)
            processed_quantity += order.to_dict().get("quantity", 0)
        print(f"📝 DEBUG: Transaction processing complete. processed_quantity={processed_quantity}")
        return processed_quantity, processed_ids
    
    # RUN the transactional function
    try:
        print(f"🚀 DEBUG: Executing transaction...")
        processed_qty, processed_ids = process(transaction)
        print(f"✅ DEBUG: Transaction executed successfully. processed_qty={processed_qty}")
        # st.success(f"✅ Transaction complete: {processed_qty} orders updated")
    except Exception as ex:
        print(f"❌ DEBUG: Transaction failed with error: {str(ex)}")
        # st.error(f"❌ Transaction error: {str(ex)}")
        raise

    # STEP 3 — update Streamlit session cache (optional)
    if "orders_df" in st.session_state and processed_ids:
        print(f"📝 DEBUG: Updating session state for orders: {processed_ids}")
        df = st.session_state.orders_df
        mask = df["order_id"].isin(processed_ids)
        df.loc[mask, "status"] = new_status
        if user:
            df.loc[mask, f"{new_status}_by"] = user
        st.session_state.orders_df = df
        print(f"✅ DEBUG: Session state updated")
        # st.write(f"✅ DEBUG: Session state updated for {mask.sum()} rows")

    print(f"🎯 DEBUG: Final result - processed_qty={processed_qty}, processed_ids={processed_ids}")
    return processed_qty, processed_ids

def calculate_order_counts():
    import utils
    """
    Calculate counts of orders by status
    
    Returns:
        Dictionary with counts for each status
    """
    counts = {'new': 0, 'picked': 0, 'validated': 0}

    if "orders_df" not in st.session_state:
        st.session_state.orders_df = get_orders_from_db()

    orders_df = st.session_state.orders_df  # Get the cached orders DataFrame
    party_filter = st.session_state.get("party_filter", "Both")
    orders_df = utils.get_party_filter_df(orders_df, party_filter)

    if not orders_df.empty:
        counts = orders_df["status"].value_counts().to_dict()  # Count occurrences of each status
    
    # Ensure all statuses are included (even if 0)
    for status in ["new", "picked", "validated"]:
        counts.setdefault(status, 0)

    return counts

def make_safe_id(s):
    if not s or pd.isna(s):
        return None
    return re.sub(r'[/#?[\]. ]+', '_', str(s).strip())

def out_of_stock(sku, user):
    """
    store sku in out_of_stock collection with timestamp and user info
    """
    db = get_db_connection()
    if db is None:
        print("❌ DEBUG: Database connection failed in out_of_stock")
        # st.error("❌ Database connection failed")
        return

    safe_sku = str(sku).strip().lower()
    safe_id = make_safe_id(safe_sku)
    out_of_stock_ref = db.collection("out_of_stock").document(safe_id   )

    out_of_stock_ref.set({
        "sku": sku,
        "status": 0,#0 need admin to take action 1 if admin taken action
        "reported_by": user,
        "updated_at": datetime.utcnow()
    })