import urllib
import os
import sys
import time
import json
import uuid
from playwright.sync_api import sync_playwright

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AUTH_DIR = os.path.join(ROOT_DIR, "auth")
TOKEN_FILE = os.path.join(AUTH_DIR, "tonton")
TOKEN_MAX_AGE_SECONDS = 86400  # 24 hours

# Read hidden auth file from auth directory
def _read_auth_file(filename):
    file_path = os.path.join(AUTH_DIR, filename)
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return ""

# Retrieve or dynamically generate User-Agent string via browser
def get_user_agent():
    ua = _read_auth_file("user_agent")
    if not ua:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                ua = page.evaluate("navigator.userAgent")
                browser.close()
        except Exception as e:
            print(f"[Auth Warning] Failed to dynamically retrieve browser User-Agent: {e}")
            ua = ""

        if ua:
            os.makedirs(AUTH_DIR, exist_ok=True)
            try:
                with open(os.path.join(AUTH_DIR, "user_agent"), "w", encoding="utf-8") as f:
                    f.write(ua)
            except Exception:
                pass
    return ua

# Retrieve or generate unique web Device ID for new users
def get_device_id():
    dev_id = _read_auth_file("device_id")
    if not dev_id:
        dev_id = f"web-v3-{uuid.uuid4().hex}-{uuid.uuid4().hex}"
        os.makedirs(AUTH_DIR, exist_ok=True)
        try:
            with open(os.path.join(AUTH_DIR, "device_id"), "w", encoding="utf-8") as f:
                f.write(dev_id)
        except Exception:
            pass
    return dev_id

# Retrieve or auto-fetch MYTV AES encryption key
def get_me_key():
    key_str = _read_auth_file("me_key")
    if key_str:
        return key_str.encode('utf-8')[:32]

    print("[MYTV Auth] Fetching MYTV AES decryption key from web API...")
    try:
        req = urllib.request.Request("https://co3y6iwoio.tenbytecdn.com/api/v1/public/config", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            fetched_key = data.get('key') or data.get('me_key') or data.get('data', {}).get('me_key') or ""
            if fetched_key:
                os.makedirs(AUTH_DIR, exist_ok=True)
                with open(os.path.join(AUTH_DIR, "me_key"), "w", encoding="utf-8") as f:
                    f.write(fetched_key)
                print("[MYTV Auth] Successfully fetched and saved ME_KEY to auth/me_key")
                return fetched_key.encode('utf-8')[:32]
    except Exception as e:
        print(f"[MYTV Auth Warning] Dynamic web key fetch encountered: {e}")

    return b""

USER_AGENT = get_user_agent()
DEVICE_ID = get_device_id()
ME_KEY = get_me_key()
EMAIL = _read_auth_file("email") or os.environ.get("EMAIL", "")
PASSWORD = _read_auth_file("password") or os.environ.get("PASSWORD", "")

# Retrieve active Tonton session token from local cache or browser session
def get_token(force_refresh=False):
    env_token = os.environ.get("TONTON_TOKEN", "").strip()
    if env_token:
        return env_token

    if not force_refresh and os.path.exists(TOKEN_FILE):
        file_age = time.time() - os.path.getmtime(TOKEN_FILE)
        if file_age < TOKEN_MAX_AGE_SECONDS:
            try:
                with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                    cached = f.read().strip()
                    if cached:
                        print(f"[Tonton Auth] Using cached token from hidden {TOKEN_FILE} (age: {int(file_age/3600)}h)")
                        return cached
            except Exception as e:
                print(f"[Tonton Auth Warning] Failed to read {TOKEN_FILE}: {e}")

    print("[Tonton Auth] Fetching fresh session token from watch.tonton.com.my...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=USER_AGENT) if USER_AGENT else browser.new_context()
            page = context.new_page()

            popup_page = None
            def on_popup(popup):
                nonlocal popup_page
                popup_page = popup

            context.on("page", on_popup)

            captured_tokens = []
            def on_request(req):
                if "loginToken=" in req.url:
                    tok = req.url.split("loginToken=")[1].split("&")[0]
                    if tok and len(tok) > 20:
                        captured_tokens.append(tok)

            page.on("request", on_request)

            if EMAIL and PASSWORD:
                print("[Tonton Auth] EMAIL and PASSWORD detected, attempting web login...")
                try:
                    page.goto("https://watch.tonton.com.my/login", wait_until="networkidle", timeout=30000)
                    page.wait_for_timeout(3000)

                    sign_in_btn = page.query_selector("button:has-text('Sign In'), a:has-text('Sign In')")
                    if not sign_in_btn:
                        sign_in_btn = page.query_selector("button")

                    if sign_in_btn:
                        sign_in_btn.click()

                    for _ in range(10):
                        if popup_page:
                            break
                        page.wait_for_timeout(1000)

                    target = popup_page if popup_page else page
                    try:
                        target.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass

                    target.wait_for_timeout(2000)
                    email_input = target.query_selector("input[type='email'], input[name='username'], input[name='email'], input[placeholder*='Email'], input[placeholder*='email']")
                    if not email_input:
                        inputs = target.query_selector_all("input")
                        if inputs:
                            email_input = inputs[0]

                    if email_input:
                        email_input.fill(EMAIL)

                    pass_input = target.query_selector("input[type='password'], input[name='password'], input[placeholder*='Password']")
                    if pass_input:
                        pass_input.fill(PASSWORD)

                    submit_btn = target.query_selector("button[type='submit'], input[type='submit'], button:has-text('Sign In'), button:has-text('Log In'), button:has-text('Masuk')")
                    if submit_btn:
                        submit_btn.click()
                        page.wait_for_timeout(7000)
                except Exception as login_err:
                    print(f"[Tonton Auth Warning] Web login interaction encountered: {login_err}")

            page.goto("https://watch.tonton.com.my/live", timeout=30000)
            page.wait_for_timeout(4000)

            ls_raw = page.evaluate("() => JSON.stringify(localStorage)")
            browser.close()

            final_token = None
            final_dev_id = None

            if ls_raw:
                ls_dict = json.loads(ls_raw)
                user_profile = ls_dict.get("USER_PROFILE")
                shared_device = ls_dict.get("SHARED_DEVICE")

                if user_profile:
                    u_obj = json.loads(user_profile) if isinstance(user_profile, str) else user_profile
                    final_token = u_obj.get("token") or u_obj.get("loginToken")
                    final_dev_id = u_obj.get("deviceId-v3") or u_obj.get("deviceId")

                if not final_token and shared_device:
                    s_obj = json.loads(shared_device) if isinstance(shared_device, str) else shared_device
                    final_token = s_obj.get("loginToken") or s_obj.get("token")
                    final_dev_id = s_obj.get("deviceId-v3") or s_obj.get("deviceId")

            if not final_token and captured_tokens:
                final_token = captured_tokens[0]

            if final_token:
                os.makedirs(AUTH_DIR, exist_ok=True)
                with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                    f.write(final_token)
                if final_dev_id:
                    with open(os.path.join(AUTH_DIR, "device_id"), "w", encoding="utf-8") as f:
                        f.write(final_dev_id)
                print(f"[Tonton Auth] Successfully saved fresh token to hidden {TOKEN_FILE}")
                return final_token
    except Exception as e:
        print(f"[Tonton Auth Error] Automated web token fetch failed: {e}")

    print("[Tonton Auth Warning] Automated web token fetch could not retrieve a token.")
    return ""

# Force refresh and overwrite the local hidden token file
def refresh_token():
    return get_token(force_refresh=True)

# Main entry point for command-line auth diagnosis & token refresh execution
def main():
    force = "--force" in sys.argv or "-f" in sys.argv
    token = get_token(force_refresh=force)
    me_key_str = _read_auth_file("me_key")
    
    print("\n====================================================")
    print("        MY-tv Authentication Diagnostics           ")
    print("====================================================")
    print(f"User-Agent   : {'[SUCCESS]' if USER_AGENT else '[FAILED / NOT SET]'}")
    print(f"Device ID    : {'[SUCCESS]' if DEVICE_ID else '[FAILED / NOT SET]'}")
    print(f"ME Key (AES) : {'[SUCCESS]' if me_key_str else '[FAILED / NOT SET]'}")
    print(f"Email        : {'[CONFIGURED]' if EMAIL else '[NOT SET]'}")
    print(f"Password     : {'[CONFIGURED]' if PASSWORD else '[NOT SET]'}")
    print(f"Tonton Token : {'[SUCCESS]' if token else '[FAILED / NOT SET]'}")
    print("====================================================\n")

if __name__ == "__main__":
    main()
