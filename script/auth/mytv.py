import re
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from paths import read_auth, write_auth
from utils import USER_AGENT, MANA2_URL

# Extract decryption key by visiting mana2 channel via Playwright
def refresh_key():
    extracted = ""
    try:
        from playwright.sync_api import sync_playwright
        print(f"[MYTV Auth] Launching browser to extract key from {MANA2_URL}...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)

            def on_resp(resp):
                nonlocal extracted
                if extracted:
                    return
                if ".js" in resp.url:
                    try:
                        m = re.search(r'="([A-Za-z0-9]{40,60})"\.trim\(\)', resp.text())
                        if m:
                            extracted = m.group(1)
                    except Exception:
                        pass

            page.on("response", on_resp)
            page.goto(f"{MANA2_URL}/channel/tv1", timeout=20000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            browser.close()
    except Exception as e:
        print(f"[MYTV Auth Warning] Browser key extraction failed: {e}")

    if extracted:
        write_auth("me_key", extracted)
        return extracted
    return ""

# Retrieve or refresh MYTV AES decryption key
def get_key(force_refresh=False, allow_browser=False):
    if not allow_browser:
        cached = read_auth("me_key") or os.environ.get("ME_KEY", "").strip()
        if not cached:
            print("[MYTV Auth Error] 'auth/me_key' not found! Please run refresh_token.yml or python script/auth.py --force to generate it.")
            return b""
        return cached.encode("utf-8")[:32]

    key_str = ""
    if not force_refresh:
        key_str = read_auth("me_key") or os.environ.get("ME_KEY", "").strip()

    if not key_str and allow_browser:
        key_str = refresh_key()

    if not key_str:
        print("[MYTV Auth Error] 'auth/me_key' not found and browser extraction failed!")
        return b""

    return key_str.encode("utf-8")[:32]

ME_KEY = get_key(allow_browser=False)

