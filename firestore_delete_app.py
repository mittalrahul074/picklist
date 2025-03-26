import streamlit as st
import pandas as pd
from datetime import datetime
import firebase_admin
from firebase_admin import firestore, credentials, initialize_app
from google.cloud.firestore_v1 import Client as FirestoreClient

# Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    initialize_app(cred)
db = firestore.client()

def get_collections():
    """Fetch all available collections"""
    collections = db.collections()
    return [col.id for col in collections]

def parse_datetime(value):
    """Try multiple datetime formats"""
    formats = [
        "%Y-%m-%d %H:%M:%S",  # Full timestamp
        "%Y-%m-%d",           # Date only
        "%Y %m %d %H:%M:%S",  # Your format with spaces
        "%Y/%m/%d %H:%M:%S"   # Slash-separated
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Invalid datetime format: {value}")

def preview_docs(collection, field, operator, value):
    """Preview documents matching the condition"""
    try:
        # Convert value to datetime if needed
        datetime_val = parse_datetime(value)
        query_ref = db.collection(collection).where(field, operator, datetime_val)
    except ValueError:
        # Treat as regular value if not datetime
        query_ref = db.collection(collection).where(field, operator, value)
    
    docs = []
    for doc in query_ref.stream():
        doc_data = doc.to_dict()
        # Convert Firestore timestamps to readable strings
        for key, val in doc_data.items():
            if isinstance(val, firestore.firestore.DatetimeWithNanoseconds):
                doc_data[key] = val.strftime("%Y-%m-%d %H:%M:%S")
        docs.append({"ID": doc.id, **doc_data})
    
    return pd.DataFrame(docs)

def delete_docs(collection, field, operator, value):
    """Delete documents matching the condition"""
    try:
        datetime_val = parse_datetime(value)
        query_ref = db.collection(collection).where(field, operator, datetime_val)
    except ValueError:
        query_ref = db.collection(collection).where(field, operator, value)
    
    docs_ref = query_ref.stream()
    batch = db.batch()
    deleted_count = 0
    
    for doc in docs_ref:
        batch.delete(doc.reference)
        deleted_count += 1
    
    batch.commit()
    return deleted_count

def render_delete_panel():
    # Streamlit UI
    st.title("🗑️ Firebase Bulk Delete (Timestamp Support)")
    st.write("Supports formats: 2025-03-26 17:52:27, 2025/03/26 17:52:27, 2025 03 26 17:52:27")

    # Step 1: Select Collection
    # collections = get_collections()
    # selected_collection = st.selectbox("Select Collection", collections)

    # Step 2: Define Condition
    col1, col2, col3 = st.columns(3)
    with col1:
        field = st.text_input("Field Name")
    with col2:
        operator = st.selectbox("Operator", ["==", ">", "<", ">=", "<="])
    with col3:
        value = st.text_input("Value", placeholder="2025-03-26 17:52:27")

    # Step 3: Preview & Delete
    if st.button("Preview Matching Documents"):
        try:
            df = preview_docs("orders", field, operator, value)
            if not df.empty:
                st.dataframe(df)
                st.success(f"Found {len(df)} documents")
                
                if st.button("⚠️ Delete All", type="primary"):
                    deleted_count = delete_docs("orders", field, operator, value)
                    st.success(f"Deleted {deleted_count} documents!")
                    st.experimental_rerun()
            else:
                st.warning("No matching documents found")
        except Exception as e:
            st.error(f"Error: {str(e)}")