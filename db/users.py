"""
User management functions for Firestore database
"""
from google.cloud import firestore as gcf
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
        elif party_value == 4:
            result = "SM"
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
            return 1  # Default fallback
            
        user_data = user_doc.to_dict()
        print(f"User data for party lookup: {list(user_data.keys()) if user_data else 'None'}")
        # st.write(f"🔍 DEBUG: User data keys for party: {list(user_data.keys()) if user_data else 'None'}")
        
        if not user_data or 'type' not in user_data:
            error_msg = f"❌ Type field not found for user {username}"
            print(error_msg)
            return 1  # Default fallback
            
        value = user_data['type']
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

def load_party_rules():
    db = get_db_connection()
    docs = db.collection("party_rules").stream()

    rules = {}
    for doc in docs:
        data = doc.to_dict()

        party_name = data.get("party_name")

        rules[party_name] = {
            "prefix": tuple(data.get("prefix", [])),
            "special_include": tuple(data.get("special_include", [])),
            "special_exclude": tuple(data.get("special_exclude", [])),
        }

    return rules

def sku_matches_party(sku: str, rules: dict) -> bool:
    sku = sku.upper().strip()

    prefix = rules.get("prefix", ())
    include = rules.get("special_include", ())
    exclude = rules.get("special_exclude", ())

    matches_prefix = sku.startswith(prefix)
    is_included = sku.startswith(include)
    is_excluded = sku.startswith(exclude)

    return (matches_prefix or is_included) and not is_excluded

def update_sku_party(sku, old_party, new_party):
    db = get_db_connection()
    if db is None:
        error_msg = "❌ Database connection failed in update_sku_party"
        print(error_msg)
        return False

    try:
        # normalize party names to match stored `party_name` values
        old_party = str(old_party).upper()
        new_party = str(new_party).upper()
        skipped_old_party = False
        #if old_party is both, then skip all operation realted to old_party
        if old_party == "BOTH":
            skipped_old_party = True

        # update the sku in the party_rules collection
        party_rules_ref = db.collection("party_rules")

        if not skipped_old_party:
            old_party_docs = party_rules_ref.where("party_name", "==", old_party).limit(1).get()
            if not old_party_docs:
                error_msg = f"❌ Old party {old_party} not found in party_rules collection"
                print(error_msg)
                return False
            old_doc_snapshot = old_party_docs[0]
            old_doc_ref = old_doc_snapshot.reference

        new_party_docs = party_rules_ref.where("party_name", "==", new_party).limit(1).get()
        if not new_party_docs:
            error_msg = f"❌ New party {new_party} not found in party_rules collection"
            print(error_msg)
            return False
        new_doc_snapshot = new_party_docs[0]
        new_doc_ref = new_doc_snapshot.reference

        #try to remove sku from special_include of old party and remove sku from special_exclude of new party
        if not skipped_old_party:
            old_doc_ref.update({"special_include": gcf.ArrayRemove([sku])})
        new_doc_ref.update({"special_exclude": gcf.ArrayRemove([sku])})

        #if the sku already follows the party rules after the above operation, then we can skip adding it to the new party's special_include and old party's special_exclude
        rules = load_party_rules()
        if sku_matches_party(sku, rules.get(new_party, {})):
            print(f"✅ SKU {sku} already matches party rules for {new_party}")
            return True

        # add sku to special_include of new party and add sku to special_exclude of old party
        if not skipped_old_party:
            old_doc_ref.update({"special_exclude": gcf.ArrayUnion([sku])})
        new_doc_ref.update({"special_include": gcf.ArrayUnion([sku])})
        print(f"✅ SKU {sku} moved from {old_party} to {new_party} successfully")
        return True
    except Exception as e:
        error_msg = f"❌ Error updating SKU party for {sku}: {e}"
        print(error_msg)
        return False