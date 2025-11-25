import streamlit as st
from database import get_pass
import time
import hmac
import hashlib

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
    clear_cookie("logged_user")
    st.session_state.authenticated = False
    st.session_state.user_role = None
    if "orders_df" in st.session_state:
        del st.session_state["orders_df"]
    if 'page' in st.session_state:
        st.session_state.page = "main"

SECRET_KEY = st.secrets["auth_secret"]

def _sign(value: str):
    """Create HMAC signature."""
    return hmac.new(SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()

def set_cookie(name, value, expires_days=7):
    """Stores a signed cookie in browser."""
    signed_value = value + "|" + _sign(value)

    expires = time.time() + expires_days * 24 * 3600

    st.session_state.cookies[name] = {
        "value": signed_value,
        "expires": expires
    }

def get_cookie(name):
    """Reads and validates cookie."""
    cookie = st.session_state.cookies.get(name)

    if not cookie:
        return None

    value, signature = cookie["value"].split("|")

    if signature == _sign(value):
        return value
    return None

def clear_cookie(name):
    if name in st.session_state.cookies:
        del st.session_state.cookies[name]