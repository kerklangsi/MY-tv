import os
import sys
import paths

from paths import read_auth, AUTH_DIR
from auth.mytv import get_key, ME_KEY
from auth.tonton import (
    get_token,
    refresh_token,
    get_device,
    check_token,
    USER_AGENT,
    DEVICE_ID,
    EMAIL,
    PASSWORD,
)

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
    token = get_token(force_refresh=force, allow_browser=True)
    me_key_bytes = get_key()
    me_key_str = read_auth("me_key")

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
