import os
import streamlit as st
import warnings

# Suppress the st.cache deprecation warning if it's coming from dependencies
warnings.filterwarnings("ignore", message=".*st.cache.*deprecated.*")

from auth import authenticate_user, logout_user, set_cookie, get_cookie
from admin import render_admin_panel
from picker_validator import render_picker_validator_panel
from validator import render_validator_panel
from dashboard import render_dashboard
from firestore_delete_app import render_delete_panel
from database import init_database, get_party

# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------
st.set_page_config(
    page_title="Order Management System",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -------------------------------------------------------------------
# BASIC CONNECTIVITY TEST
# -------------------------------------------------------------------
# Add this at the very top to test if debug messages work
st.write("🔧 **DEBUG MODE ACTIVE** - App is loading...")
print("App starting - this should appear in logs")

# Test secrets availability
try:
    if "auth_secret" in st.secrets:
        st.write("✅ Auth secret found")
    else:
        st.write("❌ Auth secret missing")
        
    if "firebase" in st.secrets:
        st.write("✅ Firebase secrets found")
        firebase_keys = list(st.secrets["firebase"].keys())
        st.write(f"📋 Firebase keys: {firebase_keys}")
    else:
        st.write("❌ Firebase secrets missing")
        
except Exception as e:
    st.write(f"❌ Error checking secrets: {e}")

st.write("---")

# -------------------------------------------------------------------
# SESSION INITIALIZATION
# -------------------------------------------------------------------
def init_state():
    defaults = {
        "authenticated": False,
        "user_role": None,
        "party_filter": None,
        "page": "dashboard",
        "db_initialized": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# -------------------------------------------------------------------
# DB INITIALIZATION
# -------------------------------------------------------------------
if not st.session_state.db_initialized:
    init_database()
    st.session_state.db_initialized = True

# -------------------------------------------------------------------
# LOAD CSS
# -------------------------------------------------------------------
css_path = "assets/styles.css"
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# -------------------------------------------------------------------
# AUTO-LOGIN FROM COOKIE
# -------------------------------------------------------------------
cookie_user = get_cookie("logged_user")

if cookie_user and not st.session_state.authenticated:
    # Auto-login user
    st.session_state.authenticated = True
    st.session_state.user_role = cookie_user
    try:
        st.session_state.party_filter = get_party(cookie_user)
    except:
        st.session_state.party_filter = None

# -------------------------------------------------------------------
# SIDEBAR LOGIN UI
# -------------------------------------------------------------------
with st.sidebar:
    st.header("Login")

    if not st.session_state.authenticated:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        print ("Username:", username)
        
        if st.button("Login"):
            print("Attempting login for user:", username)
            st.write(f"DEBUG: Login button clicked for user: {username}")
            
            # Add validation
            if not username or not password:
                st.error("Please enter both username and password")
                st.write("DEBUG: Missing username or password")
            else:
                st.write(f"DEBUG: Calling authenticate_user for: {username}")
                auth_result = authenticate_user(username, password)
                st.write(f"DEBUG: Authentication result: {auth_result}")
                
                if auth_result:
                    st.session_state.authenticated = True
                    st.session_state.user_role = username
                    
                    # Fetch party filter
                    try:
                        st.write("DEBUG: Fetching party filter...")
                        party = get_party(username)
                        st.session_state.party_filter = party
                        st.write(f"DEBUG: Party filter set to: {party}")
                    except Exception as e:
                        st.error(f"Error fetching party: {e}")
                        st.session_state.party_filter = None

                    # Save cookie → browser persistent login
                    try:
                        st.write("DEBUG: Setting cookie...")
                        set_cookie("logged_user", username)
                        st.write("DEBUG: Cookie set successfully")
                    except Exception as e:
                        st.error(f"Error setting cookie: {e}")

                    st.success("Logged in successfully!")
                    st.rerun()

                else:
                    st.error("Invalid username or password")
                    st.write("DEBUG: Authentication failed")
    else:
        st.success(f"Logged in as {st.session_state.user_role}")

        st.markdown("---")
        st.header("Navigation")

        # Party filter for Both users
        user_party = get_party(st.session_state.user_role)
        if user_party == "Both":
            selected = st.selectbox(
                "Select Party",
                ["Both", "RS", "Kangan"],
                index=["Both", "RS", "Kangan"].index(st.session_state.party_filter)
            )
            if selected != st.session_state.party_filter:
                st.session_state.party_filter = selected
                st.rerun()
        else:
            st.info(f"Party: {user_party}")

        # NAV BUTTONS
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

# -------------------------------------------------------------------
# MAIN CONTENT
# -------------------------------------------------------------------
if not st.session_state.authenticated:
    st.info("Please log in to access the system.")
else:
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
