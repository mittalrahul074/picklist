import os
import streamlit as st

from auth import authenticate_user, logout_user, set_cookie, get_cookie
from admin import render_admin_panel
from picker import render_picker_panel
from validator import render_validator_panel
from dashboard import render_dashboard
from firestore_delete_app import render_delete_panel
from picker_validator import render_picker_validator_panel
from database import init_database, get_party
from firebase_utils import add_order, get_orders
import utils

# -------------------------------------------------------------------
# DEBUG helper
# -------------------------------------------------------------------
def debug(msg, value=None):
    print("DEBUG:", msg, value)
    st.write("🔍 **DEBUG:**", msg, value)


# -------------------------------------------------------------------
# App Config
# -------------------------------------------------------------------
st.set_page_config(
    page_title="Order Management System",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -------------------------------------------------------------------
# Session Initialization
# -------------------------------------------------------------------
debug("Initializing session_state...")

defaults = {
    "authenticated": False,
    "user_role": None,
    "party_filter": None,
    "order_status_count": {"new": 0, "picked": 0, "validated": 0},
    "page": "dashboard",
    "db_initialized": False,
    "cookies": {},
}

for key, val in defaults.items():
    if key not in st.session_state:
        debug(f"Setting default session key: {key}", val)
        st.session_state[key] = val

# -------------------------------------------------------------------
# DB Initialization
# -------------------------------------------------------------------
if not st.session_state.db_initialized:
    debug("Initializing DB...")
    try:
        init_database()
        st.session_state.db_initialized = True
        debug("DB Initialized successfully")
    except Exception as e:
        debug("DB Init FAILED", str(e))

# -------------------------------------------------------------------
# CSS Loading
# -------------------------------------------------------------------
css_path = "assets/styles.css"
debug("Checking CSS:", css_path)

if os.path.exists(css_path):
    debug("CSS Found, loading...")
    try:
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except Exception as e:
        debug("CSS Load FAILED:", str(e))
else:
    debug("CSS NOT FOUND")

# -------------------------------------------------------------------
# Try auto-login from cookies
# -------------------------------------------------------------------
debug("Checking auto-login via cookie...")

try:
    cookie_user = get_cookie("logged_user")
    debug("Cookie get result:", cookie_user)
except Exception as e:
    cookie_user = None
    debug("Cookie get FAILED:", str(e))

if cookie_user and not st.session_state.authenticated:
    debug("Auto-login triggered for user:", cookie_user)
    st.session_state.authenticated = True
    st.session_state.user_role = cookie_user

    try:
        st.session_state.party_filter = get_party(cookie_user)
        debug("Party filter set via auto-login:", st.session_state.party_filter)
    except Exception as e:
        debug("Party filter failed:", str(e))

# -------------------------------------------------------------------
# Header
# -------------------------------------------------------------------
st.title("Order Management System")

# -------------------------------------------------------------------
# SIDEBAR
# -------------------------------------------------------------------
with st.sidebar:
    st.header("Login Section")
    debug("Sidebar authenticated?", st.session_state.authenticated)

    # NOT LOGGED IN
    if not st.session_state.authenticated:
        username_input = st.text_input("Username")
        password_input = st.text_input("Password", type="password")

        login_clicked = st.button("Login")
        debug("Login button clicked?", login_clicked)

        if login_clicked:
            debug("Attempting authentication for:", username_input)
            try:
                auth_result = authenticate_user(username_input, password_input)
                debug("authenticate_user() result:", auth_result)
            except Exception as e:
                auth_result = False
                debug("authenticate_user() FAILED:", str(e))

            if auth_result:
                debug("Authentication SUCCESS")

                st.session_state.authenticated = True
                st.session_state.user_role = username_input

                # Get party
                try:
                    party = get_party(username_input)
                    st.session_state.party_filter = party
                    debug("Party filter fetched:", party)
                except Exception as e:
                    debug("get_party() FAILED:", str(e))

                # Set cookie
                try:
                    set_cookie("logged_user", username_input)
                    debug("Cookie set successfully for user:", username_input)
                except Exception as e:
                    debug("Cookie set FAILED:", str(e))

                st.success(f"Logged in as {username_input}")
                st.rerun()

            else:
                debug("Authentication FAILED", username_input)
                st.error("Invalid username or password")

    # LOGGED IN
    else:
        st.success(f"Logged in as {st.session_state.user_role}")
        debug("User is logged in:", st.session_state.user_role)

        # Fetch party again for debugging
        try:
            p = get_party(st.session_state.user_role)
            debug("Party from backend:", p)
        except Exception as e:
            debug("get_party() FAILED inside sidebar:", str(e))

        st.markdown("---")
        st.header("Navigation")

        # Party filter selection for BOTH users
        if st.session_state.party_filter == "Both":
            current = st.session_state.party_filter
            debug("Party filter (Both user):", current)

            selected = st.selectbox(
                "Select Party", ["Both", "RS", "Kangan"],
                index=["Both", "RS", "Kangan"].index(current)
            )

            debug("Party selectbox changed to:", selected)

            if selected != st.session_state.party_filter:
                st.session_state.party_filter = selected
                debug("Party filter updated in session_state:", selected)
                st.rerun()

            st.markdown("---")

        # Navigation buttons
        if st.button("Dashboard"):
            st.session_state.page = "dashboard"
            debug("Changing page -> dashboard")
            st.rerun()

        if st.button("Upload Orders"):
            st.session_state.page = "admin"
            debug("Changing page -> admin")
            st.rerun()

        if st.button("Pick Orders"):
            st.session_state.page = "picker"
            debug("Changing page -> picker")
            st.rerun()

        if st.button("Validate Orders"):
            st.session_state.page = "validator"
            debug("Changing page -> validator")
            st.rerun()

        if st.session_state.user_role == "admin":
            if st.button("Delete"):
                st.session_state.page = "delete"
                debug("Changing page -> delete")
                st.rerun()

        # Logout button
        if st.button("Logout"):
            debug("Logout clicked")
            try:
                logout_user()
                debug("logout_user() executed")
            except Exception as e:
                debug("logout_user() FAILED:", str(e))

            st.session_state.clear()
            st.rerun()

# -------------------------------------------------------------------
# MAIN CONTENT
# -------------------------------------------------------------------
debug("Rendering main content, authenticated:", st.session_state.authenticated)

if not st.session_state.authenticated:
    st.info("Please log in to access the system.")
else:
    debug("Current page:", st.session_state.page)

    if st.session_state.page == "dashboard":
        debug("Rendering dashboard")
        render_dashboard()

    elif st.session_state.page == "admin":
        debug("Rendering admin panel")
        render_admin_panel()

    elif st.session_state.page == "picker":
        debug("Rendering picker")
        render_picker_validator_panel("picker")

    elif st.session_state.page == "validator":
        debug("Rendering validator")
        render_picker_validator_panel("validator")

    elif st.session_state.page == "delete":
        debug("Rendering delete page")
        render_delete_panel()

    else:
        debug("Unknown page, fallback to dashboard")
        render_dashboard()
