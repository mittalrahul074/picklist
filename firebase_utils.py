import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os

# Load Firebase credentials from Streamlit secrets
firebase_credentials = dict(st.secrets["firebase"])  # Convert secrets to dict

# Initialize Firebase if not already initialized
if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_credentials)  # Use dictionary directly
    firebase_admin.initialize_app(cred)

# Connect to Firestore
db = firestore.client()

# Example: Add a new order
def add_order(order_id, sku, quantity,status,picked_by,validated_by,platform,created_at,updated_at,dispatch_date):

    doc_ref = db.collection("orders").document(order_id)
    doc_ref.set({
        "sku": sku,
        "quantity": quantity,
        "status": status,
        "picked_by": picked_by,
        "validated_by": validated_by,
        "platform": platform,
        "created_at": created_at,
        "updated_at": updated_at,
        "dispatch_date": dispatch_date
    })
    return True

# Example: Fetch all orders
def get_orders():
    orders = db.collection("orders").stream()
    return [{order.id: order.to_dict()} for order in orders]
