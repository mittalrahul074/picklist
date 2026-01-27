"""
Returns management functions for Firestore database
"""
from db.firestore import get_db_connection
from firebase_admin import firestore
import pandas as pd
import streamlit as st
import time


def get_returns_from_db(status):
    """Fetch returns from Firestore"""
    db = get_db_connection()
    if db is None:
        error_msg = "❌ Database connection failed in get_returns_from_db"
        print(error_msg)
        st.warning(error_msg)
        return pd.DataFrame()
    
    returns_ref = db.collection("returns")

    try:
        time.sleep(0.1)  # slight delay for UX
        query = returns_ref
        # Apply status filter if provided
        if status:
            print(f"🔍 DEBUG: Applying status filter: {status}")
            query = query.where("status", "==", status)
            time.sleep(0.5)  # slight delay for UX

        rtrns = list(query.stream())
        print(f"✅ DEBUG: Found {len(rtrns)} returns from Firestore")
        time.sleep(0.1)  # slight delay for UX

        return_list = [
            {**rtrn.to_dict(), "return_id": rtrn.id}
            for rtrn in rtrns
        ]

        df = pd.DataFrame(return_list) if return_list else pd.DataFrame()
        print(f"✅ DEBUG: Created DataFrame with {len(df)} rows and columns: {list(df.columns) if not df.empty else []}")
        time.sleep(0.5)  # slight delay for UX

        return df
        
    except Exception as e:
        error_msg = f"❌ Error fetching returns from database: {e}"
        print(error_msg)
        st.warning(error_msg)
        return pd.DataFrame()


def enter_return_data(order_id, return_date, user, awb, sku, status):
    """Insert return data into Firestore"""
    db = get_db_connection()
    returns_ref = db.collection("returns").document(awb)
    # Normalize SKU to lowercase for consistent querying
    normalized_sku = str(sku).lower().strip() if sku else ""
    returns_ref.set({
        "order_id": order_id,
        "sku": normalized_sku,
        "status": status,
        "return_date": return_date,
        "processed_by": user,
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP
    })


def get_returns_grouped_by_sku(returns_df, status=None):
    """
    Groups returns by SKU.
    Each document = 1 return, so count rows per SKU.
    """
    if returns_df.empty:
        return pd.DataFrame(columns=["sku", "total_returns"])

    df = returns_df.copy()

    # Optional status filter
    if status and "status" in df.columns:
        df = df[df["status"] == status]

    if df.empty:
        return pd.DataFrame(columns=["sku", "total_returns"])

    grouped_df = (
        df.groupby("sku", as_index=False)
        .agg(
            total_returns=("sku", "count")
        )
        .sort_values("sku")
    )

    return grouped_df


def accept_returns_by_sku(sku: str, quantity_to_process: int, new_status: str, user: str = None) -> tuple[int, list[str]]:
    """
    Accept returns for a specific SKU with transactional safety
    """
    db = get_db_connection()
    if db is None:
        print("❌ Database connection failed in accept_returns_by_sku")
        return 0, []

    if not isinstance(sku, str) or not sku.strip():
        print(f"❌ Invalid SKU provided: {sku}")
        return 0, []

    print(f"🔍 DEBUG: accept_returns_by_sku called with sku={sku}, quantity_to_process={quantity_to_process}, new_status={new_status}, user={user}")

    transaction = db.transaction()

    @firestore.transactional
    def process_returns(transaction):
        """Execute transactional update for return records."""
        print(f"📝 DEBUG: Starting transaction for SKU={sku}")
        
        # Use exact SKU as it appears in the database (from grouped data)
        # Strip whitespace to handle any formatting differences
        sku_clean = sku.strip()
        
        # Try exact match first
        query = (
            db.collection("returns")
            .where("sku", "==", sku_clean.lower())
            .where("status", "==", "m_return")
            .order_by("created_at")
            .limit(quantity_to_process)
        )
        print(f"📝 DEBUG: Querying for SKU='{sku_clean}' (exact match)")
        returns = list(transaction.get(query))

        print(f"📝 DEBUG: Found {len(returns)} pending returns for SKU={sku}")

        if not returns:
            print(f"⚠️ No pending returns found for SKU: {sku}")
            return 0, []

        processed_ids = []
        total_quantity = 0

        for return_record in returns[:quantity_to_process]:  # Limit processing to requested quantity
            ref = return_record.reference
            update_fields = {
                "status": new_status,
                "updated_at": firestore.SERVER_TIMESTAMP
            }

            if user:
                update_fields["accepted_by"] = user
                print(f"📝 DEBUG: Adding user '{user}' to update fields")

            print(f"📝 DEBUG: Updating return {return_record.id} with fields: {update_fields}")
            transaction.update(ref, update_fields)
            processed_ids.append(return_record.id)
            total_quantity += return_record.to_dict().get("quantity", 1)
            print(f"✅ DEBUG: Return {return_record.id} marked for update")

        print(f"📝 DEBUG: Transaction processing complete. processed_ids={processed_ids}, total_quantity={total_quantity}")
        return total_quantity, processed_ids

    try:
        print(f"🚀 DEBUG: Executing transaction for SKU={sku}")
        processed_qty, processed_ids = process_returns(transaction)
        print(f"✅ DEBUG: Transaction executed successfully. processed_qty={processed_qty}, processed_ids={processed_ids}")
        print(f"✅ Successfully processed {len(processed_ids)} returns for SKU {sku}")
        
        # Clear session state to force fresh reload in UI layer
        if processed_ids:
            if "return_df" in st.session_state:
                del st.session_state["return_df"]
            print(f"✅ DEBUG: Cleared session state return_df - UI will reload fresh data")
        
        return processed_qty, processed_ids

    except Exception as ex:
        print(f"❌ Transaction failed for SKU {sku}: {str(ex)}")
        raise
    
    db = get_db_connection()
    if db is None:
        error_msg =     "❌ Database connection failed in get_returns_from_db"
        print(error_msg)
        st.warning(error_msg)
        return pd.DataFrame()
    
    returns_ref = db.collection("returns")

    try:
        time.sleep(0.1)  # slight delay for UX
        query = returns_ref
        # Apply status filter if provided
        if status:
            print(f"🔍 DEBUG: Applying status filter: {status}")
            query = query.where("status", "==", status)
            time.sleep(0.5)  # slight delay for UX

        rtrns = list(query.stream())
        print(f"✅ DEBUG: Found {len(rtrns)} returns from Firestore")
        time.sleep(0.1)  # slight delay for UX

        return_list = [
            {**rtrn.to_dict(), "return_id": rtrn.id}
            for rtrn in rtrns
        ]

        df = pd.DataFrame(return_list) if return_list else pd.DataFrame()
        print(f"✅ DEBUG: Created DataFrame with {len(df)} rows and columns: {list(df.columns) if not df.empty else []}")
        time.sleep(0.5)  # slight delay for UX

        return df
        
    except Exception as e:
        error_msg = f"❌ Error fetching orders from database: {e}"
        print(error_msg)
        st.warning(error_msg)
        return pd.DataFrame()

def enter_return_data(order_id, return_date, user,awb,sku,status):
    db = get_db_connection()
    #insert into returns collection document with order_id as document id
    returns_ref = db.collection("returns").document(awb)
    # Normalize SKU to lowercase for consistent querying
    normalized_sku = str(sku).lower().strip() if sku else ""
    returns_ref.set({
        "order_id":order_id,
        "sku": normalized_sku,
        "status": status,
        "return_date": return_date,
        "processed_by": user,
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP
    })

def get_returns_grouped_by_sku(returns_df, status=None):
    """
    Groups returns by SKU.
    Each document = 1 return, so count rows per SKU.
    """

    if returns_df.empty:
        return pd.DataFrame(columns=["sku", "total_returns"])

    df = returns_df.copy()

    # Optional status filter
    if status and "status" in df.columns:
        df = df[df["status"] == status]

    if df.empty:
        return pd.DataFrame(columns=["sku", "total_returns"])

    grouped_df = (
        df.groupby("sku", as_index=False)
        .agg(
            total_returns=("sku", "count")
        )
        .sort_values("sku")
    )

    return grouped_df

def accept_returns_by_sku(sku: str, quantity_to_process: int, new_status: str, user: str = None) -> tuple[int, list[str]]:
    db = get_db_connection()
    if db is None:
        print("❌ Database connection failed in accept_returns_by_sku")
        return 0, []

    if not isinstance(sku, str) or not sku.strip():
        print(f"❌ Invalid SKU provided: {sku}")
        return 0, []

    print(f"🔍 DEBUG: accept_returns_by_sku called with sku={sku}, quantity_to_process={quantity_to_process}, new_status={new_status}, user={user}")

    transaction = db.transaction()

    @firestore.transactional
    def process_returns(transaction):
        """Execute transactional update for return records."""
        print(f"📝 DEBUG: Starting transaction for SKU={sku}")
        
        # Use exact SKU as it appears in the database (from grouped data)
        # Strip whitespace to handle any formatting differences
        sku_clean = sku.strip()
        
        # Try exact match first
        query = (
            db.collection("returns")
            .where("sku", "==", sku_clean.lower())
            .where("status", "==", "m_return")
            .order_by("created_at")
            .limit(quantity_to_process)
        )
        print(f"📝 DEBUG: Querying for SKU='{sku_clean}' (exact match)")
        returns = list(transaction.get(query))

        print(f"📝 DEBUG: Found {len(returns)} pending returns for SKU={sku}")

        if not returns:
            print(f"⚠️ No pending returns found for SKU: {sku}")
            return 0, []

        processed_ids = []
        total_quantity = 0

        for return_record in returns[:quantity_to_process]:  # Limit processing to requested quantity
            ref = return_record.reference
            update_fields = {
                "status": new_status,
                "updated_at": firestore.SERVER_TIMESTAMP
            }

            if user:
                update_fields["accepted_by"] = user
                print(f"📝 DEBUG: Adding user '{user}' to update fields")

            print(f"📝 DEBUG: Updating return {return_record.id} with fields: {update_fields}")
            transaction.update(ref, update_fields)
            processed_ids.append(return_record.id)
            total_quantity += return_record.to_dict().get("quantity", 1)
            print(f"✅ DEBUG: Return {return_record.id} marked for update")

        print(f"📝 DEBUG: Transaction processing complete. processed_ids={processed_ids}, total_quantity={total_quantity}")
        return total_quantity, processed_ids

    try:
        print(f"🚀 DEBUG: Executing transaction for SKU={sku}")
        processed_qty, processed_ids = process_returns(transaction)
        print(f"✅ DEBUG: Transaction executed successfully. processed_qty={processed_qty}, processed_ids={processed_ids}")
        print(f"✅ Successfully processed {len(processed_ids)} returns for SKU {sku}")
        
        # Clear session state to force fresh reload in UI layer
        # This ensures we get fresh data after Firestore propagates the changes
        if processed_ids:
            if "return_df" in st.session_state:
                del st.session_state["return_df"]
            print(f"✅ DEBUG: Cleared session state return_df - UI will reload fresh data")
        
        return processed_qty, processed_ids

    except Exception as ex:
        print(f"❌ Transaction failed for SKU {sku}: {str(ex)}")
        raise
