import streamlit as st
import pandas as pd
import os
from auth import authenticate_user, logout_user
from admin import render_admin_panel
from picker import render_picker_panel
from validator import render_validator_panel
from dashboard import render_dashboard
import utils
from database import init_database

# App configuration and styling
st.set_page_config(
    page_title="Order Management System",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="auto"
)

from firebase_utils import add_order, get_orders

# Load custom CSS
with open("assets/styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Initialize database
if 'db_path' not in st.session_state:
    # Create database file in the current directory
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

# Sidebar for authentication
with st.sidebar:
    st.header("Login")
    
    # if not st.session_state.authenticated:
    #     username = st.text_input("Username")
    #     password = st.text_input("Password", type="password")
    #     login_button = st.button("Login")
        
    #     if login_button:
    #         if authenticate_user(username, password):
    #             st.session_state.authenticated = True
    #             st.session_state.user_role = username  # Using username as role for simplicity
    #             st.success(f"Logged in as {username}")
    #             st.rerun()
    #         else:
    #             st.error("Invalid credentials")
    # else:
    #     st.success(f"Logged in as {st.session_state.user_role}")
    #     if st.button("Logout"):
    #         logout_user()
    #         st.rerun()
    
    # Display dashboard link if authenticated
    if st.session_state.authenticated:
        st.success(f"Logged in as {st.session_state.user_role}")
        st.markdown("---")
        st.header("Navigation")
        if st.button("Dashboard"):
            st.session_state.page = "dashboard"
            st.rerun()
        
        # Role-specific navigation
        if st.session_state.user_role == "admin":
            if st.button("Upload Orders"):
                st.session_state.page = "main"
                st.rerun()
        elif st.session_state.user_role == "user1":
            if st.button("Pick Orders"):
                st.session_state.page = "main"
                st.rerun()
        elif st.session_state.user_role == "user2":
            if st.button("Validate Orders"):
                st.session_state.page = "main"
                st.rerun()

        if st.button("Logout"):
            logout_user()
            st.rerun()

# Main application content
if not st.session_state.authenticated:
    st.info("Please log in to access the system.")

    st.header("Login")
    
    if not st.session_state.authenticated:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_button = st.button("Login")
        
        if login_button:
            if authenticate_user(username, password):
                st.session_state.authenticated = True
                st.session_state.user_role = username  # Using username as role for simplicity
                st.success(f"Logged in as {username}")
                st.rerun()
            else:
                st.error("Invalid credentials")
    else:
        st.success(f"Logged in as {st.session_state.user_role}")
        if st.button("Logout"):
            logout_user()
            st.rerun()
    
    # Display dashboard link if authenticated
    if st.session_state.authenticated:
        st.markdown("---")
        st.header("Navigation")
        if st.button("Dashboard"):
            st.session_state.page = "dashboard"
            st.rerun()
        
        # Role-specific navigation
        if st.session_state.user_role == "admin":
            if st.button("Upload Orders"):
                st.session_state.page = "main"
                st.rerun()
        elif st.session_state.user_role == "user1":
            if st.button("Pick Orders"):
                st.session_state.page = "main"
                st.rerun()
        elif st.session_state.user_role == "user2":
            if st.button("Validate Orders"):
                st.session_state.page = "main"
                st.rerun()
else:
    # Initialize page in session state if not present
    if 'page' not in st.session_state:
        st.session_state.page = "main"
    
    # Render the appropriate page based on the user role and selected page
    if st.session_state.page == "dashboard":
        render_dashboard()
    else:
        if st.session_state.user_role == "admin":
            render_admin_panel()
        elif st.session_state.user_role == "user1":
            render_picker_panel()
        elif st.session_state.user_role == "user2":
            render_validator_panel()
        else:
            st.error("Unknown user role")