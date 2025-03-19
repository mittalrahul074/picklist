import streamlit as st

# Simple authentication system
# In a real-world application, you would use a database and proper password hashing
USERS = {
    "admin": "admin123",
    "user1": "user123",
    "user2": "user234"
}

def authenticate_user(username, password):
    """
    Authenticates a user based on username and password.
    
    Args:
        username: The username to authenticate
        password: The password to verify
    
    Returns:
        True if authentication is successful, False otherwise
    """
    if username in USERS and USERS[username] == password:
        return True
    return False

def logout_user():
    """Clear the authentication state"""
    st.session_state.authenticated = False
    st.session_state.user_role = None
    if 'page' in st.session_state:
        st.session_state.page = "main"