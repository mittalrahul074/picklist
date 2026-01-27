"""
Cancelled orders management functions for Firestore database
"""
import streamlit as st
from db.firestore import get_db_connection
from firebase_admin import firestore
import pandas as pd
from db.orders import get_order_details
import time


def get_cancelled_from_db(status):
    """Fetch cancelled orders from Firestore"""
    db = get_db_connection()
    if db is None:
        error_msg = "❌ Database connection failed in get_cancelled_from_db"
        print(error_msg)
        st.warning(error_msg)
        return pd.DataFrame()
    
    cancel_ref = db.collection("cancelled_orders")

    try:
        time.sleep(0.1)  # slight delay for UX
        query = cancel_ref
        # Apply status filter if provided
        if status:
            print(f"🔍 DEBUG: Applying status filter: {status}")
            query = query.where("status", "==", status)
            time.sleep(0.5)  # slight delay for UX

        rtrns = list(query.stream())
        print(f"✅ DEBUG: Found {len(rtrns)} cancelled orders from Firestore")
        time.sleep(0.1)  # slight delay for UX
        # get details of each order from get_order_details(order_id) and add to list
        cancel_list = [
            get_order_details(rtrn.to_dict().get("order_id"))
            for rtrn in rtrns
        ]

        df = pd.DataFrame(cancel_list) if cancel_list else pd.DataFrame()
        print(f"✅ DEBUG: Created DataFrame with {len(df)} rows and columns: {list(df.columns) if not df.empty else []}")
        time.sleep(0.5)  # slight delay for UX

        return df
        
    except Exception as e:
        error_msg = f"❌ Error fetching cancelled orders from database: {e}"
        print(error_msg)
        st.warning(error_msg)
        return pd.DataFrame()


def accept_cancelled(order_id, user):
    """Accept a cancelled order with transactional safety"""
    db = get_db_connection()
    if db is None:
        print("❌ Database connection failed in accept_cancelled")
        return 0, []

    transaction = db.transaction()

    @firestore.transactional
    def process_cancel(transaction):
        """Execute transactional update for cancelled orders."""
        print(f"📝 DEBUG: Starting transaction for Order_id={order_id}")
                
        # Get order and cancel documents
        query = db.collection("orders").document(order_id)
        cancel_query = (
            db.collection("cancelled_orders")
            .where("order_id", "==", order_id)
            .where("status", "==", "CANCELLED")
            .limit(1)
        )
        print(f"📝 DEBUG: Querying for Order_id='{order_id}' (exact match)")
        order_list = list(transaction.get(query))
        cancel_list = list(transaction.get(cancel_query))

        if not cancel_list:
            print(f"⚠️ No pending cancels found for Order_id: {order_id}")
            return 0, []

        cancel_ref = cancel_list[0].reference
        order_ref = query
        update_fields = {
            "status": "cancelled_accepted",
            "updated_at": firestore.SERVER_TIMESTAMP
        }

        if user:
            update_fields["accepted_by"] = user
            print(f"📝 DEBUG: Adding user '{user}' to update fields")
            print(f"📝 DEBUG: Updating cancel {cancel_list[0].id} with fields: {update_fields}")
            transaction.update(cancel_ref, update_fields)
            transaction.update(order_ref, update_fields)
            print(f"✅ DEBUG: Cancel {cancel_list[0].id} marked for update")

    try:
        print(f"🚀 DEBUG: Executing transaction for order_id={order_id}")
        process_cancel(transaction)
        print(f"✅ DEBUG: Transaction executed successfully.")
        print(f"✅ Successfully processed order_id {order_id}")
        
        # Clear session state to force fresh reload in UI layer
        if "cancelled_df" in st.session_state:
            del st.session_state["cancelled_df"]
        print(f"✅ DEBUG: Cleared session state cancelled_df - UI will reload fresh data")

        return 1, [order_id]
    except Exception as ex:
        print(f"❌ Transaction failed for order_id {order_id}: {str(ex)}")
        raise
    
    db = get_db_connection()
    if db is None:
        error_msg =     "❌ Database connection failed in get_returns_from_db"
        print(error_msg)
        st.warning(error_msg)
        return pd.DataFrame()
    
    cancel_ref = db.collection("cancelled_orders")

    try:
        time.sleep(0.1)  # slight delay for UX
        query = cancel_ref
        # Apply status filter if provided
        if status:
            print(f"🔍 DEBUG: Applying status filter: {status}")
            query = query.where("status", "==", status)
            time.sleep(0.5)  # slight delay for UX

        rtrns = list(query.stream())
        print(f"✅ DEBUG: Found {len(rtrns)} returns from Firestore")
        time.sleep(0.1)  # slight delay for UX
        # get detials of each return from get_order_details(order_id) and add to list
        cancel_list = [
            get_order_details(rtrn.to_dict().get("order_id"))
            for rtrn in rtrns
        ]

        df = pd.DataFrame(cancel_list) if cancel_list else pd.DataFrame()
        print(f"✅ DEBUG: Created DataFrame with {len(df)} rows and columns: {list(df.columns) if not df.empty else []}")
        time.sleep(0.5)  # slight delay for UX

        return df
        
    except Exception as e:
        error_msg = f"❌ Error fetching orders from database: {e}"
        print(error_msg)
        st.warning(error_msg)
        return pd.DataFrame()

def accept_cancelled(order_id,user):
    db = get_db_connection()
    if db is None:
        print("❌ Database connection failed in accept_returns_by_sku")
        return 0, []

    transaction = db.transaction()

    @firestore.transactional
    def process_cancel(transaction):
        """Execute transactional update for return records."""
        print(f"📝 DEBUG: Starting transaction for Order_id={order_id}")
                
        # Try exact match first
        query = (
            db.collection("orders").document(order_id)
        )
        cancel_query = (
            db.collection("cancelled_orders")
            .where("order_id", "==", order_id)
            .where("status", "==", "CANCELLED")
            .limit(1)
        )
        print(f"📝 DEBUG: Querying for Order_id='{order_id}' (exact match)")
        order_list = list(transaction.get(query))
        cancel_list = list(transaction.get(cancel_query))

        if not cancel_list:
            print(f"⚠️ No pending cancels found for Order_id: {order_id}")
            return 0, []

        cancel_ref = cancel_list[0].reference
        order_ref = order_list[0].reference
        update_fields = {
            "status": "cancelled_accepted",
            "updated_at": firestore.SERVER_TIMESTAMP
        }

        if user:
            update_fields["accepted_by"] = user
            print(f"📝 DEBUG: Adding user '{user}' to update fields")
            print(f"📝 DEBUG: Updating return {cancel_list[0].id} with fields: {update_fields}")
            transaction.update(cancel_ref, update_fields)
            transaction.update(order_ref, update_fields)
            print(f"✅ DEBUG: Return {cancel_list[0].id} marked for update")

    try:
        print(f"🚀 DEBUG: Executing transaction for order_id={order_id}")
        process_cancel(transaction)
        print(f"✅ DEBUG: Transaction executed successfully.")
        print(f"✅ Successfully processed order_id {order_id}")
        
        # Clear session state to force fresh reload in UI layer
        # This ensures we get fresh data after Firestore propagates the changes
        if "cancelled_df" in st.session_state:
            del st.session_state["cancelled_df"]
        print(f"✅ DEBUG: Cleared session state cancelled_df - UI will reload fresh data")

        return 1, [order_id]
    except Exception as ex:
        print(f"❌ Transaction failed for order_id {order_id}: {str(ex)}")
        raise

