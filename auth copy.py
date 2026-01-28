import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager
from database import get_pass

# ---------------------------------------------------------------------
# Cookie manager - will be initialized when needed
# ---------------------------------------------------------------------
cookies = None

def init_cookies():
    """Initialize cookie manager with proper error handling"""
    global cookies
    
    if cookies is not None:
        return cookies
    
    try:
        print("Initializing cookie manager...")
        
        if "auth_secret" not in st.secrets:
            error_msg = "auth_secret not found in st.secrets"
            print(error_msg)
            st.warning("⚠️ Cookie authentication not available - auth_secret missing")
            return None
        
        cookies = EncryptedCookieManager(
            prefix="oms_",
            password=st.secrets["auth_secret"]
        )
        
        print("Cookie manager created, checking if ready...")
        
        # Check if cookie manager is ready
        if not cookies.ready():
            print("Cookie manager not ready")
            st.info("🔄 Cookie session initializing... Login will work without persistent sessions.")
            return None
        
        print("Cookie manager ready!")
        return cookies
        
    except Exception as e:
        error_msg = f"Error initializing cookie manager: {e}"
        print(error_msg)
        st.warning("⚠️ Cookie authentication not available - login will work without persistent sessions")
        return None

# ---------------------------------------------------------------------
# AUTHENTICATION LOGIC
# ---------------------------------------------------------------------
def authenticate_user(username: str, password: str) -> bool:
    """
    Return True if username and password match the DB.
    """
    print("Authenticating user:", username)
    # st.write(f"DEBUG: Attempting to authenticate user: {username}")  # Cloud-visible debug
    
    try:
        stored_password = get_pass(username)
        print(f"Retrieved password for {username}: {stored_password}")
        # st.write(f"DEBUG: Retrieved password for {username}: {bool(stored_password)}")  # Don't show actual password
        
        result = stored_password == password
        print(f"Authentication result for {username}: {result}")
        # st.write(f"DEBUG: Authentication result for {username}: {result}")
        
        return result
    except Exception as e:
        print("AUTH ERROR:", e)
        st.error(f"Authentication error: {str(e)}")  # Keep error messages for troubleshooting
        return False


def set_cookie(name: str, value: str):
    try:
        cookies_manager = init_cookies()
        if cookies_manager is None:
            print("Cookie manager not available for set_cookie")
            return False
        if not cookies_manager.ready():
            print("Cookie manager not ready for set_cookie")
            return False
        cookies_manager[name] = value
        cookies_manager.save()  # write to user's browser
        return True
    except Exception as e:
        print(f"Error setting cookie {name}: {e}")
        return False


def get_cookie(name: str):
    try:
        cookies_manager = init_cookies()
        if cookies_manager is None:
            print("Cookie manager not available for get_cookie")
            return None
        if not cookies_manager.ready():
            print("Cookie manager not ready for get_cookie")
            return None
        return cookies_manager.get(name)
    except Exception as e:
        print(f"Error getting cookie {name}: {e}")
        return None


def clear_cookie(name: str):
    try:
        cookies_manager = init_cookies()
        if cookies_manager is None:
            print("Cookie manager not available for clear_cookie")
            return False
        if not cookies_manager.ready():
            print("Cookie manager not ready for clear_cookie")
            return False
        cookies_manager[name] = ""
        cookies_manager.save()
        return True
    except Exception as e:
        print(f"Error clearing cookie {name}: {e}")
        return False


def logout_user():
    clear_cookie("logged_user")
    st.session_state.authenticated = False
    st.session_state.user_role = None
    if "party_filter" in st.session_state:
        st.session_state.party_filter = None
    st.session_state.page = "dashboard"