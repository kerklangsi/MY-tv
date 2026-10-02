import urllib.request
import re
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
AUTH_DIR = os.path.join(ROOT_DIR, "auth")
DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

# Read credentials or keys from auth directory
def read_auth(filename):
    file_path = os.path.join(AUTH_DIR, filename)
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return ""

# Retrieve or scrape MYTV AES decryption key
def get_key():
    key_str = read_auth("me_key") or os.environ.get("ME_KEY", "").strip()
    if key_str:
        return key_str.encode("utf-8")[:32]

    print("[MYTV Auth] Fetching MYTV AES decryption key from https://mana2.my/...")
    extracted_key = ""
    ua = read_auth("user_agent") or DESKTOP_UA
    headers = {"User-Agent": ua}

    try:
        req = urllib.request.Request("https://mana2.my/", headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        scripts = re.findall(r'src=["\'](/assets/[^"\']+\.js)["\']', html)
        for s in scripts:
            js_url = "https://mana2.my" + s
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
        os.makedirs(AUTH_DIR, exist_ok=True)
        try:
            with open(os.path.join(AUTH_DIR, "me_key"), "w", encoding="utf-8") as f:
                f.write(extracted_key)
        except Exception:
            pass
        return extracted_key.encode("utf-8")[:32]

    return b""

ME_KEY = get_key()
