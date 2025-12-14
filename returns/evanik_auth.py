import requests

LOGIN_URL = "https://app.evanik.ai/loginAuth"

def evanik_login(email, password):
    session = requests.Session()

    payload = {
        "username": email,
        "password": password,
        "remember_me": "1"
    }

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = session.post(LOGIN_URL, data=payload, headers=headers)

    # 🔍 Safety check
    if "ci_session" not in session.cookies:
        raise Exception("Login failed: ci_session not found")

    return session