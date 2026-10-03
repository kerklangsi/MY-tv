import urllib.request
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
    if not allow_browser and not force_refresh:
        cached = read_auth("me_key") or os.environ.get("ME_KEY", "").strip()
        return cached.encode("utf-8")[:32] if cached else b""

    key_str = ""
    if not force_refresh:
        key_str = read_auth("me_key") or os.environ.get("ME_KEY", "").strip()

    if not key_str and allow_browser:
        key_str = refresh_key()

    if not key_str:
        print(f"[MYTV Auth] Fetching MYTV AES decryption key from {MANA2_URL}/...")
        extracted_key = ""
        headers = {"User-Agent": USER_AGENT}
        try:
            req = urllib.request.Request(f"{MANA2_URL}/", headers=headers)
            with urllib.request.urlopen(req, timeout=12) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            scripts = re.findall(r'src=["\'](/assets/[^"\']+\.js)["\']', html)
            for s in scripts:
                try:
                    req_js = urllib.request.Request(f"{MANA2_URL}{s}", headers=headers)
                    with urllib.request.urlopen(req_js, timeout=10) as r:
                        content = r.read().decode("utf-8", errors="ignore")
                        m_direct = re.search(r'="([A-Za-z0-9]{40,60})"\.trim\(\)', content)
                        if m_direct:
                            extracted_key = m_direct.group(1)
                            break
                        chunks = re.findall(r'assets/(?:player-license|license)[^"\'\s]+\.js', content)
                        for chunk in chunks:
                            try:
                                c_req = urllib.request.Request(f"{MANA2_URL}/{chunk}", headers=headers)
                                with urllib.request.urlopen(c_req, timeout=8) as cr:
                                    c_data = cr.read().decode("utf-8", errors="ignore")
                                    m_chunk = re.search(r'="([A-Za-z0-9]{40,60})"\.trim\(\)', c_data)
                                    if m_chunk:
                                        extracted_key = m_chunk.group(1)
                                        break
                            except Exception:
                                pass
                        if extracted_key:
                            break
                except Exception:
                    pass
        except Exception as e:
            print(f"[MYTV Auth Warning] Dynamic scrape encountered: {e}")
        if extracted_key:
            write_auth("me_key", extracted_key)
            key_str = extracted_key

    return key_str.encode("utf-8")[:32] if key_str else b""

ME_KEY = get_key(allow_browser=False)

