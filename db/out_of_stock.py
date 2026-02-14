"""
Cancelled orders management functions for Firestore database
"""
import streamlit as st
from db.firestore import get_db_connection
from firebase_admin import firestore
import pandas as pd
from db.orders import get_order_details
import time


def get_out_of_stock_from_db():
    """Fetch out of stock orders from Firestore"""
    db = get_db_connection()
    if db is None:
        error_msg = "❌ Database connection failed in get_out_of_stock_from_db"
        print(error_msg)
        st.warning(error_msg)
        return pd.DataFrame()
    
    out_of_stock_ref = db.collection("out_of_stock")
    print("🚀 DEBUG: Fetching out of stock orders from Firestore")

    try:
        time.sleep(0.1)  # slight delay for UX
        #where status == 0
        query = out_of_stock_ref.where("status", "==", 0)
        docs = list(query.stream())
        print(f"✅ DEBUG: Found {len(docs)} out of stock orders from Firestore")
        time.sleep(0.1)  # slight delay for UX
        # get details of each order from get_order_details(order_id) and add to list
        out_of_stock_list = []

        for doc in docs:
            data = doc.to_dict()
            out_of_stock_list.append({
                "safe_sku": doc.id,
                "sku": data.get("sku"),
                "reported_by" : data.get("reported_by"),
                "status": data.get("status"),
                "updated_at": data.get("updated_at")
            })

        df = pd.DataFrame(out_of_stock_list) if out_of_stock_list else pd.DataFrame()
        print(f"✅ DEBUG: Created DataFrame with {len(df)} rows and columns: {list(df.columns) if not df.empty else []}")
        time.sleep(0.5)  # slight delay for UX

        return df
        
    except Exception as e:
        error_msg = f"❌ Error fetching cancelled orders from database: {e}"
        print(error_msg)
        st.warning(error_msg)
        return pd.DataFrame()


def accept_out_of_stock(safe_sku,sku, new_status, user):
    """Accept an out of stock order with transactional safety"""
    db = get_db_connection()
    if db is None:
        print("❌ Database connection failed in process_out_of_stock")
        return 0, []

    transaction = db.transaction()

    @firestore.transactional
    def process_out_of_stock(transaction):
        """Execute transactional update for out of stock orders."""
        print(f"📝 DEBUG: Starting transaction for safe_sku={safe_sku}")
                
        # Get order and cancel documents
        out_of_stock_query = (
            db.collection("out_of_stock")
            .where("sku", "==", sku)
            .where("status", "==", 0)
            .limit(1)
        )
        print(f"📝 DEBUG: Querying for safe_sku='{safe_sku}' (exact match)")
        out_of_stock_list = list(transaction.get(out_of_stock_query))

        if not out_of_stock_list:
            print(f"⚠️ No pending out of stock items found for safe_sku: {safe_sku}")
            return 0, []

        out_of_stock_ref = out_of_stock_list[0].reference
        update_fields = {
            "status": 1,
            "marked_by": user,
            "updated_at": firestore.SERVER_TIMESTAMP
        }

        if user:
            print(f"📝 DEBUG: Adding user '{user}' to update fields")
            print(f"📝 DEBUG: Updating out of stock item {out_of_stock_list[0].id} with fields: {update_fields}")
            transaction.update(out_of_stock_ref, update_fields)
            print(f"✅ DEBUG: Out of stock item {out_of_stock_list[0].id} marked for update")

    try:
        print(f"🚀 DEBUG: Executing transaction for safe_sku={safe_sku}")
        process_out_of_stock(transaction)
        print(f"✅ DEBUG: Transaction executed successfully.")
        print(f"✅ Successfully processed safe_sku {safe_sku}")
        
        # Clear session state to force fresh reload in UI layer
        if "out_of_stock_df" in st.session_state:
            del st.session_state["out_of_stock_df"]
        print(f"✅ DEBUG: Cleared session state out_of_stock_df - UI will reload fresh data")

        return 1, [safe_sku]
    except Exception as ex:
        print(f"❌ Transaction failed for safe_sku {safe_sku}: {str(ex)}")
        raise