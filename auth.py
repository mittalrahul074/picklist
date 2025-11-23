import streamlit as st
from database import get_pass

# Simple authentication system
# In a real-world application, you would use a database and proper password hashing

def authenticate_user(username, password):
    """
    Authenticates a user based on username and password.
    
    Args:
        username: The username to authenticate
        password: The password to verify
    
    Returns:
        True if authentication is successful, False otherwise
    """
    if get_pass(username) == password:
        return True
    return False

def logout_user():
    """Clear the authentication state"""
    st.session_state.authenticated = False
    st.session_state.user_role = None
    if "orders_df" in st.session_state:
        del st.session_state["orders_df"]
    if 'page' in st.session_state:
        st.session_state.page = "main"