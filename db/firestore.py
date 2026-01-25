from google.cloud import firestore
import firebase_admin
from firebase_admin import credentials, firestore
import streamlit as st


def get_db_connection():
    print("Connecting to Firestore database...")
    
    try:
        # Check if secrets exist
        if "firebase" not in st.secrets:
            error_msg = "❌ Firebase secrets not found in st.secrets"
            print(error_msg)
            # st.error(error_msg)
            return None
            
        print("Firebase secrets found")
        
        firebase_credentials = dict(st.secrets["firebase"])  # Convert secrets to dict

        # Initialize Firebase if not already initialized
        if not firebase_admin._apps:
            print("Initializing Firebase app...")
            cred = credentials.Certificate(firebase_credentials)  # Use dictionary directly
            firebase_admin.initialize_app(cred)
            print("Firebase app initialized successfully")
        else:
            print("Firebase app already initialized")

        # Connect to Firestore
        print("Creating Firestore client...")
        db = firestore.client()
        print("Firestore client created successfully")
        return db

    except Exception as e:
        error_msg = f"❌ Error connecting to Firestore: {e}"
        print(error_msg)
        # st.error(error_msg)
        return None


def init_database():
    """
    Initialize the database with the required tables
    """
    try:
        # Connect to Firestore
        print("Creating Firestore client...")
        db = firestore.client()
        print("Firestore client created successfully")
        return db

    except Exception as e:
        error_msg = f"❌ Error connecting to Firestore: {e}"
        print(error_msg)
        # st.error(error_msg)
        return None
