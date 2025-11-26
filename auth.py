import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager
from database import get_pass

# ---------------------------------------------------------------------
# Create encrypted, browser-persistent cookie manager
# ---------------------------------------------------------------------
cookies = EncryptedCookieManager(
    prefix="oms_",
    password=st.secrets["auth_secret"]
)

# Must stop until cookie manager is ready
if not cookies.ready():
    st.stop()

# ---------------------------------------------------------------------
# AUTHENTICATION LOGIC
# ---------------------------------------------------------------------
def authenticate_user(username: str, password: str) -> bool:
    """
    Return True if username and password match the DB.
    """
    print("Authenticating user:", username)
    try:
        stored_password = get_pass(username)
        return stored_password == password
    except Exception as e:
        print("AUTH ERROR:", e)
        return False


def set_cookie(name: str, value: str):
    cookies[name] = value
    cookies.save()  # write to user's browser


def get_cookie(name: str):
    return cookies.get(name)


def clear_cookie(name: str):
    cookies[name] = ""
    cookies.save()


def logout_user():
    clear_cookie("logged_user")
    st.session_state.authenticated = False
    st.session_state.user_role = None
    if "party_filter" in st.session_state:
        st.session_state.party_filter = None
    st.session_state.page = "dashboard"