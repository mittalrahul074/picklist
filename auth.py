import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager
from database import get_pass
from passlib.hash import bcrypt


# -------------------------------------------------
# Cookie Manager
# -------------------------------------------------
def get_cookie_manager():
    if "cookie_manager" in st.session_state:
        return st.session_state.cookie_manager

    if "auth_secret" not in st.secrets:
        return None

    manager = EncryptedCookieManager(
        prefix="oms_",
        password=st.secrets["auth_secret"]
    )

    if not manager.ready():
        return None

    st.session_state.cookie_manager = manager
    return manager


# -------------------------------------------------
# Authentication
# -------------------------------------------------
def authenticate_user(username, password):
    return get_pass(username) == password


# -------------------------------------------------
# Cookie helpers
# -------------------------------------------------
def set_cookie(name: str, value: str) -> bool:
    manager = get_cookie_manager()
    if not manager:
        return False

    manager[name] = value
    manager.save()
    return True


def get_cookie(name: str):
    manager = get_cookie_manager()
    if not manager:
        return None
    return manager.get(name)


def clear_cookie(name: str) -> None:
    manager = get_cookie_manager()
    if not manager:
        return

    manager[name] = ""
    manager.save()


# -------------------------------------------------
# Logout
# -------------------------------------------------
def logout_user():
    clear_cookie("logged_user")

    st.session_state.update({
        "authenticated": False,
        "user_role": None,
        "party_filter": None,
        "page": "dashboard"
    })
