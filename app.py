import os
import warnings
import streamlit as st

from auth import authenticate_user, logout_user, set_cookie, get_cookie
from admin.admin_panel import render_admin_panel
from picker_validator import render_picker_validator_panel
from dashboard import render_dashboard
from firestore_delete_app import render_delete_panel
from database import init_database, get_party, get_user_type
from search import render_search_panel
from return_scan import render_return_scan_panel
from accept_returns import render_accept_returns_panel
from cancelled_list import render_cancelled_list_panel

# -------------------------------------------------------------------
# SUPPRESS WARNINGS (DEPENDENCY NOISE)
# -------------------------------------------------------------------
warnings.filterwarnings("ignore", message=".*st.cache.*deprecated.*")

# -------------------------------------------------------------------
# CONSTANTS
# -------------------------------------------------------------------
APP_TITLE = "Order Management System"
CSS_PATH = "assets/styles.css"

PAGE_DASHBOARD = "dashboard"
PAGE_ADMIN = "admin"
PAGE_PICKER = "picker"
PAGE_VALIDATOR = "validator"
PAGE_SEARCH = "search"
PAGE_RETURN_SCAN = "return_scan"
PAGE_ACCEPT_RETURNS = "accept_returns"
PAGE_CANCELLED_LIST = "cancelled_list"
PAGE_DELETE = "delete"

# User types (document these clearly)
USER_PICKER_ONLY = 1
USER_RETURNS_ACCESS = {2, 3, 4, 5}

# -------------------------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------------------------
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -------------------------------------------------------------------
# SESSION STATE INITIALIZATION
# -------------------------------------------------------------------
def init_session_state() -> None:
    defaults = {
        "authenticated": False,
        "user_role": None,
        "user_type": None,
        "party_filter": "Both",
        "page": PAGE_DASHBOARD,
        "db_initialized": False,
    }

    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

init_session_state()

# -------------------------------------------------------------------
# DATABASE INIT (ONCE)
# -------------------------------------------------------------------
if not st.session_state.db_initialized:
    init_database()
    st.session_state.db_initialized = True

# -------------------------------------------------------------------
# LOAD GLOBAL CSS
# -------------------------------------------------------------------
if os.path.exists(CSS_PATH):
    with open(CSS_PATH, "r", encoding="utf-8") as css_file:
        st.markdown(
            f"<style>{css_file.read()}</style>",
            unsafe_allow_html=True,
        )

# -------------------------------------------------------------------
# AUTH: AUTO LOGIN FROM COOKIE
# -------------------------------------------------------------------
def attempt_auto_login() -> None:
    if st.session_state.authenticated:
        return

    try:
        username = get_cookie("logged_user")
        if not username:
            return

        st.session_state.authenticated = True
        st.session_state.user_role = username
        st.session_state.user_type = get_user_type(username)

        try:
            st.session_state.party_filter = get_party(username)
        except Exception:
            st.session_state.party_filter = "Both"

    except Exception:
        # Silent fail: user can still log in manually
        pass

attempt_auto_login()

# -------------------------------------------------------------------
# SIDEBAR
# -------------------------------------------------------------------
def render_login_sidebar() -> None:
    with st.sidebar:
        st.header("Login")

        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            if not username or not password:
                st.error("Please enter both username and password")
                return

            if not authenticate_user(username, password):
                st.error("Invalid username or password")
                return

            # Login success
            st.session_state.authenticated = True
            st.session_state.user_role = username
            st.session_state.user_type = get_user_type(username)

            try:
                st.session_state.party_filter = get_party(username)
            except Exception:
                st.session_state.party_filter = "Both"

            try:
                set_cookie("logged_user", username)
            except Exception:
                pass

            st.success("Logged in successfully")
            st.rerun()

def render_navigation_sidebar() -> None:
    with st.sidebar:
        st.success(f"Logged in as {st.session_state.user_role}")
        st.markdown("---")

        # =========================
        # Party Selector
        # =========================
        allowed_party = get_party(st.session_state.user_role)

        if allowed_party == "Both":
            selected_party = st.selectbox(
                "Party",
                ["Both", "RS", "Kangan"],
                index=["Both", "RS", "Kangan"].index(st.session_state.party_filter),
            )

            if selected_party != st.session_state.party_filter:
                st.session_state.party_filter = selected_party
                st.rerun()
        else:
            st.info(f"Party: {st.session_state.party_filter}")

        st.markdown("---")

        # =========================
        # Navigation
        # =========================
        PAGES = {
            "Dashboard": PAGE_DASHBOARD,
            "Pick Orders": PAGE_PICKER,
            "Validate Orders": PAGE_VALIDATOR,
            "Search Orders": PAGE_SEARCH,
            "Upload Orders": PAGE_ADMIN,
            "Upload Return Scan": PAGE_RETURN_SCAN,
            "Accept Returns": PAGE_ACCEPT_RETURNS,
            "Cancelled List": PAGE_CANCELLED_LIST,
            "Delete": PAGE_DELETE,
        }

        ROLE_ACCESS = {
            1: {"Dashboard", "Pick Orders","Validate Orders"}, # Picker only
            2: {"Dashboard", "Validate Orders", "Search Orders"},
            3: {"Dashboard", "Pick Orders", "Validate Orders", "Search Orders","Accept Returns", "Cancelled List","Upload Orders", "Upload Return Scan"}, # Full access except Admin
            4: {"Dashboard", "Pick Orders", "Validate Orders", "Search Orders","Accept Returns", "Cancelled List","Upload Orders", "Upload Return Scan", "Delete"}, # Full access except Admin
            5: set(PAGES.keys()), # Admin has access to all pages
        }

        user_type = st.session_state.user_type
        print(f"USER TYPE: {user_type}")
        allowed_pages = sorted(ROLE_ACCESS.get(user_type, {"Dashboard"}))
        print(f"ALLOWED PAGES: {allowed_pages}")

        selected_page = st.selectbox(
            "Navigate",
            allowed_pages,
            index=allowed_pages.index(
                next(
                    (k for k, v in PAGES.items() if v == st.session_state.page),
                    "Dashboard",
                )
            ),
        )

        st.session_state.page = PAGES[selected_page]

        st.markdown("---")

        if st.button("Logout"):
            logout_user()
            st.rerun()

# -------------------------------------------------------------------
# MAIN ENTRY
# -------------------------------------------------------------------
if not st.session_state.authenticated:
    render_login_sidebar()
    st.info("Please log in to access the system.")
else:
    render_navigation_sidebar()

    page = st.session_state.page

    if page == PAGE_DASHBOARD:
        render_dashboard()
    elif page == PAGE_ADMIN:
        render_admin_panel()
    elif page == PAGE_PICKER:
        render_picker_validator_panel("picker")
    elif page == PAGE_VALIDATOR:
        render_picker_validator_panel("validator")
    elif page == PAGE_SEARCH:
        render_search_panel()
    elif page == PAGE_RETURN_SCAN:
        render_return_scan_panel()
    elif page == PAGE_ACCEPT_RETURNS:
        render_accept_returns_panel()
    elif page == PAGE_CANCELLED_LIST:
        render_cancelled_list_panel()
    elif page == PAGE_DELETE:
        render_delete_panel()