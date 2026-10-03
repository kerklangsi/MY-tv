import urllib.request
import re
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from paths import read_auth, write_auth
from utils import USER_AGENT, MANA2_URL

# Retrieve or scrape MYTV AES decryption key
def get_key():
    key_str = read_auth("me_key") or os.environ.get("ME_KEY", "").strip()
    if key_str:
        return key_str.encode("utf-8")[:32]

    print(f"[MYTV Auth] Fetching MYTV AES decryption key from {MANA2_URL}/...")
    extracted_key = ""
    headers = {"User-Agent": USER_AGENT}

    try:
        req = urllib.request.Request(f"{MANA2_URL}/", headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        scripts = re.findall(r'src=["\'](/assets/[^"\']+\.js)["\']', html)
        for s in scripts:
            js_url = f"{MANA2_URL}{s}"
            try:
                req_js = urllib.request.Request(js_url, headers=headers)
                with urllib.request.urlopen(req_js, timeout=10) as r:
                    content = r.read().decode("utf-8", errors="ignore")
                    m_direct = re.search(r'="([A-Za-z0-9]{40,60})"\.trim\(\)', content)
                    if m_direct:
                        extracted_key = m_direct.group(1)
                        break
            except Exception:
                pass
    except Exception as e:
        print(f"[MYTV Auth Warning] Dynamic mana2.my key scrape encountered: {e}")

    if extracted_key:
        write_auth("me_key", extracted_key)
        return extracted_key.encode("utf-8")[:32]
    return b""

ME_KEY = get_key()
