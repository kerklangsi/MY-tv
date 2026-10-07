import os
import sys
import paths

from paths import AUTH_DIR, read_auth, write_auth
from utils import DEFAULT_UA
from auth.mytv import get_key
from auth.tonton import get_token, get_device

# Load or persist custom User-Agent configuration
def init_agent():
    ua = read_auth("user_agent")
    if ua:
        print("[Auth] Loaded User-Agent from auth/user_agent")
        return ua
    print("[Auth] Saved User-Agent to auth/user_agent")
    write_auth("user_agent", DEFAULT_UA)
    return DEFAULT_UA

# Load or persist Email and Password credentials
def init_creds():
    email = os.environ.get("EMAIL", "").strip()
    pwd = os.environ.get("PASSWORD", "").strip()
    cached_email = read_auth("email")
    if cached_email and not email:
        print("[Auth] Loaded Email from auth/email")
        email = cached_email
    elif email:
        last_email = read_auth("last_email")
        if last_email and last_email != email:
            profile_dir = os.path.join(AUTH_DIR, "browser_profile")
            if os.path.exists(profile_dir):
                import shutil
                shutil.rmtree(profile_dir, ignore_errors=True)
            write_auth("tonton", "")
        write_auth("email", email)
        write_auth("last_email", email)
        print("[Auth] Saved Email to auth/email")

    cached_pwd = read_auth("password")
    if cached_pwd and not pwd:
        print("[Auth] Loaded Password from auth/password")
        pwd = cached_pwd
    elif pwd:
        write_auth("password", pwd)
        print("[Auth] Saved Password to auth/password")

    return email, pwd

# Save screenshot and log page state for auth debugging
def debug_step(label, page):
    try:
        debug_dir = os.path.join(AUTH_DIR, "debug")
        os.makedirs(debug_dir, exist_ok=True)
        shot_path = os.path.join(debug_dir, f"{label}.png")
        page.screenshot(path=shot_path, full_page=True)
        print(f"[Tonton Auth Debug] [{label}] URL: {page.url}")
        print(f"[Tonton Auth Debug] [{label}] Title: {page.title()}")
        body_text = (page.inner_text("body") or "")[:300].replace("\n", " ").encode("ascii", errors="replace").decode("ascii")
        print(f"[Tonton Auth Debug] [{label}] Body: {body_text}")
    except Exception as dbg_e:
        print(f"[Tonton Auth Debug] [{label}] Screenshot failed: {dbg_e}")

# Dump inputs and buttons from page for selector inspection
def dump_elements(page):
    try:
        inputs = page.query_selector_all("input")
        btns = page.query_selector_all("button, a[href]")
        print(f"[Tonton Auth Debug] Found {len(inputs)} input(s):")
        for el in inputs[:10]:
            t = el.get_attribute("type") or "text"
            n = el.get_attribute("name") or ""
            ph = el.get_attribute("placeholder") or ""
            i = el.get_attribute("id") or ""
            print(f"  input type={t!r} name={n!r} placeholder={ph!r} id={i!r}")
        print(f"[Tonton Auth Debug] Found {len(btns)} button/link(s):")
        for el in btns[:10]:
            txt = (el.inner_text() or "").strip()[:40]
            href = el.get_attribute("href") or ""
            cls = el.get_attribute("class") or ""
            print(f"  btn/a text={txt!r} href={href[:40]!r} class={cls[:40]!r}")
    except Exception as de:
        print(f"[Tonton Auth Debug] dump_elements error: {de}")

# Run authentication check and print diagnostic status
def main():
    force = "--force" in sys.argv or "-f" in sys.argv
    ua = init_agent()
    dev_id = get_device(verbose=True)
    email, pwd = init_creds()
    key = get_key(force_refresh=force, allow_browser=True)
    token = get_token(force_refresh=force, allow_browser=True)

    print("\n====================================================")
    print("        MY-tv Authentication Diagnostics           ")
    print("====================================================")
    print(f"User-Agent   : {'[SUCCESS]' if ua else '[FAILED / NOT SET]'}")
    print(f"Device ID    : {'[SUCCESS]' if dev_id else '[FAILED / NOT SET]'}")
    print(f"ME Key (AES) : {'[SUCCESS]' if key else '[FAILED / NOT SET]'}")
    print(f"Email        : {'[CONFIGURED]' if email else '[NOT SET]'}")
    print(f"Password     : {'[CONFIGURED]' if pwd else '[NOT SET]'}")
    print(f"Tonton Token : {'[SUCCESS]' if token else '[FAILED / NOT SET]'}")
    print("====================================================\n")

if __name__ == "__main__":
    main()
