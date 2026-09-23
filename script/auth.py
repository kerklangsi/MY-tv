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

# Real desktop Chrome UA — headless UA is blocked by Tonton's ua-barrier-menu
DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

# Return a guaranteed desktop UA, purging any stale headless UA from cache
def get_user_agent():
    cached = _read_auth_file("user_agent")
    # Reject any cached UA that contains headless/bot markers
    if cached and not any(x in cached.lower() for x in ["headless", "bot", "crawler", "python"]):
        return cached
    # Wipe stale headless UA file so it doesn't persist
    ua_file = os.path.join(AUTH_DIR, "user_agent")
    if os.path.exists(ua_file):
        try:
            os.remove(ua_file)
            print("[Tonton Auth] Removed stale/headless user_agent cache file.")
        except Exception:
            pass
    return DESKTOP_UA

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

    # 1. Check local cached token file (skip if force_refresh)
    if not force_refresh and os.path.exists(TOKEN_FILE):
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
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--window-size=1920,1080",
                    f"--user-agent={USER_AGENT}",
                ]
            )
            context = browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="Asia/Kuala_Lumpur",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9,ms;q=0.8",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                }
            )

            # Comprehensive bot detection bypass — spoof navigator properties
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
                Object.defineProperty(navigator, 'vendor', {get: () => 'Google Inc.'});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en', 'ms']});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                window.chrome = {runtime: {}};
            """)
            # Pre-seed persistent Device ID so a new device is never registered
            context.add_init_script(f"""
                localStorage.setItem('SHARED_DEVICE', JSON.stringify({{
                    'deviceId-v3': '{dev_id}',
                    'deviceId': '{dev_id}'
                }}));
            """)
            page = context.new_page()


            popup_page = None
            captured_tokens = []

            # Intercept token from request URLs (legacy fallback)
            def on_request(req):
                if "loginToken=" in req.url:
                    tok = req.url.split("loginToken=")[1].split("&")[0]
                    if tok and len(tok) > 20:
                        captured_tokens.append(tok)

            # Intercept token from PKCE OAuth2 callback response body or redirect URL
            def on_response(resp):
                try:
                    url = resp.url
                    # Log ALL tonton API responses to find where token is delivered
                    if "tonton.com.my" in url and resp.status < 400:
                        try:
                            body = resp.text()
                            if body and ("loginToken" in body or "accessToken" in body or "access_token" in body):
                                print(f"[Tonton Auth Debug] Token found in response from: {url[:120]}")
                                print(f"[Tonton Auth Debug] Response body (first 500): {body[:500]}")
                                import re as _re
                                for pattern in [r'loginToken["\']?\s*[=:,]\s*["\']?([A-Za-z0-9_\-\.]{20,})',
                                                r'accessToken["\']?\s*[=:,]\s*["\']?([A-Za-z0-9_\-\.]{20,})',
                                                r'access_token["\']?\s*[=:,]\s*["\']?([A-Za-z0-9_\-\.]{20,})']:
                                    m = _re.search(pattern, body)
                                    if m:
                                        captured_tokens.append(m.group(1))
                                        print(f"[Tonton Auth Debug] Token captured from API response")
                                        break
                        except Exception:
                            pass
                    if "loginToken=" in url:
                        tok = url.split("loginToken=")[1].split("&")[0]
                        if tok and len(tok) > 20:
                            captured_tokens.append(tok)
                            print(f"[Tonton Auth Debug] Token captured from redirect URL")
                except Exception:
                    pass

            # Single context page handler — tracks popup AND attaches token listeners
            def on_new_page(new_pg):
                nonlocal popup_page
                popup_page = new_pg
                new_pg.on("request", on_request)
                new_pg.on("response", on_response)

            context.on("page", on_new_page)
            page.on("request", on_request)
            page.on("response", on_response)

            if EMAIL and PASSWORD:
                print("[Tonton Auth] EMAIL and PASSWORD detected, attempting web login...")
                try:
                    page.goto("https://watch.tonton.com.my/login", wait_until="domcontentloaded", timeout=30000)

                    # Wait for React to mount any interactive element (up to 15s)
                    try:
                        page.wait_for_selector("input, button, a[href*='login'], a[href*='signin']", timeout=15000)
                    except Exception:
                        pass
                    page.wait_for_timeout(2000)
                    print(f"[Tonton Auth Debug] Login page URL: {page.url} | Title: {page.title()}")

                    # Dump first 1500 chars of rendered HTML for diagnosis
                    html_snippet = page.evaluate("() => document.body ? document.body.innerHTML.substring(0, 1500) : 'no body'")
                    print(f"[Tonton Auth Debug] Page HTML snippet: {html_snippet}")

                    # Save screenshot to auth dir for inspection
                    try:
                        screenshot_path = os.path.join(AUTH_DIR, "login_debug.png")
                        os.makedirs(AUTH_DIR, exist_ok=True)
                        page.screenshot(path=screenshot_path)
                        print(f"[Tonton Auth Debug] Screenshot saved to {screenshot_path}")
                    except Exception as ss_err:
                        print(f"[Tonton Auth Debug] Screenshot failed: {ss_err}")

                    # Wait for Tonton splash ad overlay to disappear before interacting
                    print("[Tonton Auth Debug] Waiting for splash ad to clear...")
                    try:
                        page.wait_for_selector(".adContainer, .adContainerSplash", state="hidden", timeout=15000)
                        print("[Tonton Auth Debug] Ad overlay gone.")
                    except Exception:
                        # Ad may not exist or may have already dismissed — try clicking it away
                        ad = page.query_selector(".adContainer, .adContainerSplash")
                        if ad:
                            try:
                                ad.click()
                                page.wait_for_timeout(1000)
                            except Exception:
                                pass
                        print("[Tonton Auth Debug] Ad wait timed out, proceeding anyway.")

                    page.wait_for_timeout(1000)

                    # Take a post-ad screenshot to confirm real page is visible
                    try:
                        page.screenshot(path=os.path.join(AUTH_DIR, "login_after_ad.png"))
                    except Exception:
                        pass

                    # Find real sign-in button — never fall back to bare 'button' (catches ad buttons)
                    sign_in_btn = page.query_selector(
                        "button:has-text('Sign In'), a:has-text('Sign In'), "
                        "button:has-text('Log In'), a:has-text('Log In'), "
                        "button:has-text('Masuk'), a:has-text('Masuk'), "
                        "button:has-text('Login'), a:has-text('Login'), "
                        "[aria-label*='login' i], [aria-label*='sign' i]"
                    )
                    print(f"[Tonton Auth Debug] Sign-in button found: {sign_in_btn is not None}")
                    if sign_in_btn:
                        btn_text = sign_in_btn.text_content()
                        print(f"[Tonton Auth Debug] Button text: {repr(btn_text)}")
                        sign_in_btn.click()

                    # Wait for popup OR inline redirect (up to 12s)
                    for _ in range(12):
                        if popup_page:
                            break
                        page.wait_for_timeout(1000)

                    print(f"[Tonton Auth Debug] Popup detected: {popup_page is not None}")
                    print(f"[Tonton Auth Debug] Current page URL after click: {page.url}")

                    # Support both popup SSO and inline redirect SSO
                    target = popup_page if popup_page else page
                    try:
                        target.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    print(f"[Tonton Auth Debug] Target URL: {target.url} | Title: {target.title()}")

                    # Wait for email/password fields to appear in SSO page
                    try:
                        target.wait_for_selector("input", timeout=10000)
                    except Exception:
                        pass
                    target.wait_for_timeout(1000)

                    # Dump SSO page HTML for diagnosis
                    target_html = target.evaluate("() => document.body ? document.body.innerHTML.substring(0, 1500) : 'no body'")
                    print(f"[Tonton Auth Debug] Target HTML snippet: {target_html}")
                    email_input = target.query_selector(
                        "input[type='email'], input[name='username'], input[name='email'], "
                        "input[placeholder*='Email'], input[placeholder*='email'], "
                        "input[placeholder*='emel'], input[id*='email'], input[id*='username']"
                    )
                    if not email_input:
                        inputs = target.query_selector_all("input")
                        email_input = inputs[0] if inputs else None
                    print(f"[Tonton Auth Debug] Email input found: {email_input is not None}")

                    if email_input:
                        email_input.fill(EMAIL)

                    pass_input = target.query_selector(
                        "input[type='password'], input[name='password'], "
                        "input[placeholder*='Password'], input[placeholder*='password']"
                    )
                    print(f"[Tonton Auth Debug] Password input found: {pass_input is not None}")
                    if pass_input:
                        pass_input.fill(PASSWORD)

                    submit_btn = target.query_selector(
                        "button[type='submit'], input[type='submit'], "
                        "button:has-text('Sign In'), button:has-text('Log In'), "
                        "button:has-text('Masuk'), button:has-text('Login'), "
                        "button:has-text('Submit')"
                    )
                    print(f"[Tonton Auth Debug] Submit button found: {submit_btn is not None}")
                    if submit_btn:
                        submit_btn.click()
                        if popup_page:
                            try:
                                popup_page.wait_for_event("close", timeout=15000)
                            except Exception:
                                pass

                    # Wait for SSO callback — token arrives via network, also check localStorage
                    try:
                        page.wait_for_function(
                            """() => {
                                try {
                                    const sd = JSON.parse(localStorage.getItem('SHARED_DEVICE') || 'null');
                                    if (sd && (sd.loginToken || sd.token)) return true;
                                    const up = JSON.parse(localStorage.getItem('USER_PROFILE') || 'null');
                                    if (up && (up.loginToken || up.token)) return true;
                                    // Only match values that are long enough to be real tokens (>50 chars)
                                    return Object.keys(localStorage).some(
                                        k => k.toLowerCase().includes('token') &&
                                             localStorage.getItem(k) &&
                                             localStorage.getItem(k).length > 50 &&
                                             !localStorage.getItem(k).startsWith('{')
                                    );
                                } catch(e) { return false; }
                            }""",
                            timeout=15000
                        )
                        print("[Tonton Auth Debug] localStorage token found via wait_for_function")
                    except Exception:
                        print("[Tonton Auth Debug] localStorage token not found — relying on network capture")
                        page.wait_for_timeout(5000)

                    print(f"[Tonton Auth Debug] Final page URL after login: {page.url} | Title: {page.title()}")
                except Exception as login_err:
                    print(f"[Tonton Auth Warning] Web login interaction encountered: {login_err}")

            # Check if token is already present before navigating
            ls_raw = page.evaluate("() => JSON.stringify(localStorage)")
            print(f"[Tonton Auth Debug] localStorage keys: {list(json.loads(ls_raw).keys()) if ls_raw else 'none'}")
            if not ls_raw or '"loginToken"' not in ls_raw:
                try:
                    page.goto("https://watch.tonton.com.my/live", timeout=30000)
                    page.wait_for_timeout(5000)
                    ls_raw = page.evaluate("() => JSON.stringify(localStorage)")
                    print(f"[Tonton Auth Debug] localStorage keys after /live: {list(json.loads(ls_raw).keys()) if ls_raw else 'none'}")
                except Exception:
                    pass
            cookies = context.cookies()
            browser.close()

            final_token = None
            final_dev_id = None

            # Debug: dump key localStorage values in full
            if ls_raw:
                ls_dict = json.loads(ls_raw)
                print(f"[Tonton Auth Debug] Full localStorage dump ({len(ls_dict)} keys):")
                for k, v in ls_dict.items():
                    v_str = str(v)[:40] if v else "(empty)"
                    print(f"  {k!r}: {v_str!r}")
                # Print FULL value of SHARED_DEVICE and any value containing 'loginToken' or 'token'
                for k, v in ls_dict.items():
                    v_str = str(v) if v else ""
                    if k == "SHARED_DEVICE" or "loginToken" in v_str or ("token" in v_str.lower() and len(v_str) > 50):
                        print(f"[Tonton Auth Debug] FULL value of {k!r}: {v_str}")
            print(f"[Tonton Auth Debug] Captured request tokens: {len(captured_tokens)}")

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
                    # Scan all keys — check both key name containing 'token' AND long string values
                    for k, val in ls_dict.items():
                        if isinstance(val, str) and len(val) > 30:
                            # Try to parse as JSON object with token inside
                            try:
                                obj = json.loads(val)
                                if isinstance(obj, dict):
                                    t = obj.get("loginToken") or obj.get("token") or obj.get("accessToken")
                                    if t and len(t) > 20:
                                        final_token = t
                                        final_dev_id = obj.get("deviceId-v3") or obj.get("deviceId")
                                        print(f"[Tonton Auth Debug] Token extracted from nested key: {k!r}")
                                        break
                            except Exception:
                                pass
                        if not final_token and "token" in k.lower() and isinstance(val, str) and len(val) > 20:
                            final_token = val
                            print(f"[Tonton Auth Debug] Token extracted from key: {k!r}")
                            break

            if not final_token and captured_tokens:
                final_token = captured_tokens[0]
                print(f"[Tonton Auth Debug] Token extracted from captured request URL")

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
