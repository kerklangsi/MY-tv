import urllib.request
import re
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
    dev_id = _read_auth_file("device_id") or os.environ.get("DEVICE_ID", "").strip()
    if not dev_id:
        dev_id = f"web-v3-{uuid.uuid4().hex}-{uuid.uuid4().hex}"
    os.makedirs(AUTH_DIR, exist_ok=True)
    dev_file = os.path.join(AUTH_DIR, "device_id")
    if not os.path.exists(dev_file) or not _read_auth_file("device_id"):
        try:
            with open(dev_file, "w", encoding="utf-8") as f:
                f.write(dev_id)
        except Exception:
            pass
    return dev_id

# Verify whether a Tonton streaming token is currently accepted by the headend API
def is_token_valid(token, device_id=None):
    if not token or len(token) < 20:
        return False
    dev = device_id or get_device_id()
    ua = USER_AGENT if 'USER_AGENT' in globals() and USER_AGENT else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    test_url = f"https://headend-api.tonton.com.my/v600/api/playback.class.api.php/GOgetLiveConfig/378/1/1?format=json&appID=TONTON&rate=WIFIHIGH&plt=web&deviceId={dev}&loginToken={token}"
    req = urllib.request.Request(test_url, headers={"User-Agent": ua})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            playback = data.get("playback") or data
            return bool(playback.get("media") or playback.get("url") or playback.get("playbackUrl"))
    except Exception:
        return False

# Retrieve or auto-fetch MYTV AES encryption key from mana2.my
def get_me_key():
    key_str = _read_auth_file("me_key") or os.environ.get("ME_KEY", "").strip()
    if key_str:
        return key_str.encode('utf-8')[:32]

    print("[MYTV Auth] Fetching MYTV AES decryption key from https://mana2.my/...")
    extracted_key = ""
    ua = USER_AGENT if 'USER_AGENT' in globals() and USER_AGENT else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    headers = {"User-Agent": ua}

    try:
        req = urllib.request.Request("https://mana2.my/", headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode('utf-8', errors='ignore')

        scripts = re.findall(r'src=["\'](/assets/[^"\']+\.js)["\']', html)
        for s in scripts:
            js_url = "https://mana2.my" + s
            try:
                req_js = urllib.request.Request(js_url, headers=headers)
                with urllib.request.urlopen(req_js, timeout=10) as r:
                    content = r.read().decode('utf-8', errors='ignore')
                    m_direct = re.search(r'="([A-Za-z0-9]{40,60})"\.trim\(\)', content)
                    if m_direct:
                        extracted_key = m_direct.group(1)
                        break

                    pl_matches = re.findall(r'assets/player-license-[^"\']+\.js', content)
                    for pl in pl_matches:
                        pl_url = "https://mana2.my/" + pl
                        req_pl = urllib.request.Request(pl_url, headers=headers)
                        with urllib.request.urlopen(req_pl, timeout=10) as r_pl:
                            pl_code = r_pl.read().decode('utf-8', errors='ignore')
                            m = re.search(r'="([A-Za-z0-9]{40,60})"\.trim\(\)', pl_code)
                            if m:
                                extracted_key = m.group(1)
                                break
                    if extracted_key:
                        break
            except Exception:
                pass
    except Exception as e:
        print(f"[MYTV Auth Warning] Dynamic mana2.my key scrape encountered: {e}")

    if extracted_key:
        os.makedirs(AUTH_DIR, exist_ok=True)
        try:
            with open(os.path.join(AUTH_DIR, "me_key"), "w", encoding="utf-8") as f:
                f.write(extracted_key)
            print("[MYTV Auth] Successfully saved ME_KEY to auth/me_key")
        except Exception:
            pass
        return extracted_key.encode('utf-8')[:32]

    return b""

USER_AGENT = get_user_agent() or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
DEVICE_ID = get_device_id()
ME_KEY = get_me_key()

EMAIL = (_read_auth_file("email") or os.environ.get("EMAIL", "")).strip()
PASSWORD = (_read_auth_file("password") or os.environ.get("PASSWORD", "")).strip()

# Persist environment credentials to local auth files if not already present
if EMAIL and not _read_auth_file("email"):
    try:
        os.makedirs(AUTH_DIR, exist_ok=True)
        with open(os.path.join(AUTH_DIR, "email"), "w", encoding="utf-8") as f:
            f.write(EMAIL)
    except Exception:
        pass

if PASSWORD and not _read_auth_file("password"):
    try:
        os.makedirs(AUTH_DIR, exist_ok=True)
        with open(os.path.join(AUTH_DIR, "password"), "w", encoding="utf-8") as f:
            f.write(PASSWORD)
    except Exception:
        pass

# Retrieve active Tonton session token from local cache or browser session
def get_token(force_refresh=False):
    dev_id = get_device_id()

    # 1. Check local cached token file
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                cached = f.read().strip()
                if cached:
                    print(f"[Tonton Auth] Testing cached token from {TOKEN_FILE}...")
                    if is_token_valid(cached, dev_id):
                        print(f"[Tonton Auth] Cached token is verified valid! Reusing token.")
                        return cached
                    print("[Tonton Auth] Cached token is expired or rejected.")
        except Exception as e:
            print(f"[Tonton Auth Warning] Failed to read {TOKEN_FILE}: {e}")

    # 2. Check environment variable token if provided
    env_token = os.environ.get("TONTON_TOKEN", "").strip()
    if env_token:
        print(f"[Tonton Auth] Testing TONTON_TOKEN environment variable...")
        if is_token_valid(env_token, dev_id):
            print(f"[Tonton Auth] Environment TONTON_TOKEN is valid!")
            try:
                os.makedirs(AUTH_DIR, exist_ok=True)
                with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                    f.write(env_token)
            except Exception:
                pass
            return env_token
        print("[Tonton Auth] Environment TONTON_TOKEN is expired or rejected.")

    print("[Tonton Auth] Token missing or expired. Fetching fresh session token from watch.tonton.com.my...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            context = browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1920, "height": 1080}
            ) if USER_AGENT else browser.new_context()

            # Mask webdriver and pre-seed the persistent Device ID so a new device is never created
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            context.add_init_script(f"""
                localStorage.setItem('SHARED_DEVICE', JSON.stringify({{
                    'deviceId-v3': '{dev_id}',
                    'deviceId': '{dev_id}'
                }}));
            """)
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

                    sign_in_btn = page.query_selector(
                        "button:has-text('Sign In'), a:has-text('Sign In'), "
                        "button:has-text('Log In'), a:has-text('Log In'), "
                        "button:has-text('Masuk'), a:has-text('Masuk')"
                    )
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
                        if popup_page:
                            try:
                                popup_page.wait_for_event("close", timeout=12000)
                            except Exception:
                                pass

                    # Wait for SSO callback to finish and write loginToken to localStorage
                    try:
                        page.wait_for_function(
                            "() => { try { const s = JSON.parse(localStorage.getItem('SHARED_DEVICE')); return !!(s && (s.loginToken || s.token)); } catch(e) { return false; } }",
                            timeout=20000
                        )
                    except Exception:
                        page.wait_for_timeout(5000)
                except Exception as login_err:
                    print(f"[Tonton Auth Warning] Web login interaction encountered: {login_err}")

            # Check if token is already present before navigating
            ls_raw = page.evaluate("() => JSON.stringify(localStorage)")
            if not ls_raw or '"loginToken"' not in ls_raw:
                try:
                    page.goto("https://watch.tonton.com.my/live", timeout=30000)
                    page.wait_for_timeout(4000)
                    ls_raw = page.evaluate("() => JSON.stringify(localStorage)")
                except Exception:
                    pass
            cookies = context.cookies()
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

                if not final_token:
                    # Scan any other key containing token
                    for k, val in ls_dict.items():
                        if "token" in k.lower() and isinstance(val, str) and len(val) > 20:
                            final_token = val
                            break

            if not final_token and captured_tokens:
                final_token = captured_tokens[0]

            if not final_token and cookies:
                for c in cookies:
                    if c.get("name") in ["loginToken", "token", "tonton_token"] and len(c.get("value", "")) > 20:
                        final_token = c.get("value")
                        break

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
    global ME_KEY
    ME_KEY = get_me_key()
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
