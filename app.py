import streamlit as st
import pandas as pd
import os
from auth import authenticate_user, logout_user
from admin import render_admin_panel
from picker import render_picker_panel
from validator import render_validator_panel
from dashboard import render_dashboard
from firestore_delete_app import render_delete_panel
import utils
from database import init_database,get_party
from firebase_utils import add_order, get_orders
from picker_validator import render_picker_validator_panel

# App configuration
st.set_page_config(
    page_title="Order Management System",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Load custom CSS
with open("assets/styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Initialize database
if 'db_path' not in st.session_state:
    init_database()

# Initialize session state for authentication
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'order_status_count' not in st.session_state:
    st.session_state.order_status_count = {'new': 0, 'picked': 0, 'validated': 0}

# App header
st.title("Order Management System")

# Sidebar for authentication and navigation
with st.sidebar:
    st.header("Login")
    
    if not st.session_state.authenticated:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_button = st.button("Login")
        
        if login_button:
            if authenticate_user(username, password):
                st.session_state.authenticated = True
                st.session_state.user_role = username  # Store username instead of role
                st.session_state.party_filter = get_party(username)
                st.success(f"Logged in as {username}")
                st.rerun()
            else:
                st.error("Invalid credentials")
    else:
        st.success(f"Logged in as {st.session_state.user_role}")
        
        # Navigation Links (Now accessible to all)
        st.markdown("---")
        st.header("Navigation")
        if st.button("Dashboard"):
            st.session_state.page = "dashboard"
            st.rerun()
        if st.button("Upload Orders"):
            st.session_state.page = "admin"
            st.rerun()
        if st.button("Pick Orders"):
            st.session_state.page = "picker"
            st.rerun()
        if st.button("Validate Orders"):
            st.session_state.page = "validator"
            st.rerun()
        if st.session_state.user_role == "admin":
            if st.button("Delete"):
                st.session_state.page = "delete"
                st.rerun()
        
        if st.button("Logout"):
            logout_user()
            st.rerun()

# Ensure user is logged in before rendering pages
if not st.session_state.authenticated:
    st.info("Please log in to access the system.")
else:
    # Initialize page in session state if not set
    if 'page' not in st.session_state:
        st.session_state.page = "dashboard"
    
    # Render selected page
    if st.session_state.page == "dashboard":
        render_dashboard()
    elif st.session_state.page == "admin":
        render_admin_panel()
    elif st.session_state.page == "picker":
        render_picker_validator_panel("picker")
    elif st.session_state.page == "validator":
        render_picker_validator_panel("validator")
    elif st.session_state.page == "delete":
        render_delete_panel()
