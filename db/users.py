"""
User management functions for Firestore database
"""
from db.firestore import get_db_connection
import streamlit as st
import pandas as pd


def get_pass(username):
    print("Fetching password for user:", username)
    
    db = get_db_connection()
    if db is None:
        error_msg = "❌ Database connection failed in get_pass"
        print(error_msg)
        # st.error(error_msg)
        return None
        
    try:
        print(f"Querying Firestore for user: {username}")
        
        user_ref = db.collection("users").document(username)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            error_msg = f"❌ User {username} not found in Firestore"
            print(error_msg)
            # st.error(error_msg)
            return None
            
        user_data = user_doc.to_dict()
        print(f"User data retrieved for {username}: {list(user_data.keys()) if user_data else 'None'}")
        
        if 'pass' not in user_data:
            error_msg = f"❌ Password field not found for user {username}"
            print(error_msg)
            # st.error(error_msg)
            return None
            
        print(f"✅ Password retrieved successfully for {username}")
        return user_data['pass']
        
    except Exception as e:
        error_msg = f"❌ Error fetching password for {username}: {e}"
        print(error_msg)
        # st.error(error_msg)
        return None

def get_party(username):
    
    db = get_db_connection()
    if db is None:
        error_msg = "❌ Database connection failed in get_party"
        print(error_msg)
        # st.error(error_msg)
        return "Both"  # Default fallback
        
    try:        
        user_ref = db.collection("users").document(username)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            error_msg = f"❌ User {username} not found in Firestore for party lookup"
            print(error_msg)
            # st.error(error_msg)
            return "Both"  # Default fallback
            
        user_data = user_doc.to_dict()
        print(f"User data for party lookup: {list(user_data.keys()) if user_data else 'None'}")
        # st.write(f"🔍 DEBUG: User data keys for party: {list(user_data.keys()) if user_data else 'None'}")
        
        if not user_data or 'party' not in user_data:
            error_msg = f"❌ Party field not found for user {username}"
            print(error_msg)
            # st.error(error_msg)
            return "Both"  # Default fallback
            
        party_value = user_data['party']
        print(f"Party value for {username}: {party_value}")
        # st.write(f"🔍 DEBUG: Party value for {username}: {party_value}")
        
        if party_value == 1:
            result = "Kangan"
        elif party_value == 2:
            result = "RS"
        elif party_value == 3:
            result = "Both"
        else:
            print(f"Unknown party value {party_value} for user {username}, defaulting to 'Both'")
            # st.warning(f"Unknown party value {party_value} for user {username}, defaulting to 'Both'")
            result = "Both"
            
        return result
        
    except Exception as e:
        error_msg = f"❌ Error fetching party for {username}: {e}"
        print(error_msg)
        # st.error(error_msg)
        return "Both"  # Default fallback

def get_user_type(username):
    
    db = get_db_connection()
    if db is None:
        error_msg = "❌ Database connection failed in get_party"
        print(error_msg)
        # st.error(error_msg)
        return "Both"  # Default fallback
        
    try:
        print(f"Querying Firestore for user type: {username}")
        
        user_ref = db.collection("users").document(username)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            error_msg = f"❌ User {username} not found in Firestore for party lookup"
            print(error_msg)
            # st.error(error_msg)
            return "Both"  # Default fallback
            
        user_data = user_doc.to_dict()
        print(f"User data for party lookup: {list(user_data.keys()) if user_data else 'None'}")
        # st.write(f"🔍 DEBUG: User data keys for party: {list(user_data.keys()) if user_data else 'None'}")
        
        if not user_data or 'type' not in user_data:
            error_msg = f"❌ Type field not found for user {username}"
            print(error_msg)
            # st.error(error_msg)
            return "Both"  # Default fallback
            
        value = user_data['type']
        print(f"Party value for {username}: {value}")
        # st.write(f"🔍 DEBUG: Party value for {username}: {party_value}")
        
        return value
        
    except Exception as e:
        error_msg = f"❌ Error fetching user type for {username}: {e}"
        print(error_msg)
        return 1  # Default fallback


def get_user_productivity():
    """Get productivity data by user from session state"""
    import utils
    
    if "orders_df" not in st.session_state or st.session_state.orders_df.empty:
        return pd.DataFrame(columns=['user', 'picked_count', 'picked_quantity', 'validated_count', 'validated_quantity'])

    orders_df = st.session_state.orders_df
    party_filter = st.session_state.get("party_filter", "Both")
    orders_df = utils.get_party_filter_df(orders_df, party_filter)

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
