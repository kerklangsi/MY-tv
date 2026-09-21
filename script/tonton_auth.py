import os
import sys
import time
import json
from playwright.sync_api import sync_playwright

TOKEN_FILE = ".tonton_token"
TOKEN_MAX_AGE_SECONDS = 86400  # 24 hours

# Retrieve active Tonton session token from local cache or browser session
def get_tonton_token(force_refresh=False):
    env_token = os.getenv("TONTON_TOKEN")
    if env_token and not force_refresh:
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

    print("[Tonton Auth] Fetching fresh session token from watch.tonton.com.my/live...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            page = context.new_page()
            page.goto("https://watch.tonton.com.my/live", timeout=30000)
            page.wait_for_timeout(4000)

            shared_dev_raw = page.evaluate("() => localStorage.getItem('SHARED_DEVICE')")
            browser.close()

            if shared_dev_raw:
                dev_data = json.loads(shared_dev_raw)
                fresh_token = dev_data.get('token')
                if fresh_token:
                    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                        f.write(fresh_token)
                    print(f"[Tonton Auth] Successfully saved fresh token to hidden {TOKEN_FILE}")
                    return fresh_token
    except Exception as e:
        print(f"[Tonton Auth Error] Automated web token fetch failed: {e}")

    fallback = "4ee33e1bf4b37a8a7087c8fbfc1e2907bc9acf16c5282d31569e8d8b2e403f8f6b911a2025c84f1c7bcc0e6bd993e525171a831e69b0110c942726f0ff705572d842e6f67fd8fe16f068d686dd390ab142f8e692eb648bd06603e87c05864482c5a48842fe3ab87f67640c7c7bb2f1c74f4e0260b33c57fb7d0929271729bee510f3e8e7e8fd23f3c5f84216462a1ed8c00f276f4493fac976b4a456043d773edd07adb237d9a012210d7b0b18c24b23808c99fd6f009b88ad7b04230b760a2ced9ebe6cd5a232a4cf0597878be09578450c3889f59c1e1cec7c0d2a684a7986e138dd6080fec74202921f1e8fdff553d2d949767b62091b60c516a0b76bdbf0cc3e20482b221c9a92e4d311cc263b5dd533abeddb3de211b152cb6ab9f2fa11d456922896be8c4573dc05fa49a8f3a38f00e6e97967b7a52322db70e935439d102b4ed053288c8a3b8cefa5cb56c309cce14e35197506bf318f86d1e817bd0fcc34740cc75c272385e599d8229ac6c4958b5154f6befd65cbaf09ab35a942343de8ac0b18f631530c79ef33ef223f3514d2fde38cd99acc0c62de666eeac21ab7e9b23973a1b875a236b0d91e601df88c7aadfc29076197d4396506c29093a278fe9a143c815c6501f19c000696e851ea97003b1eee16f02fd181a9ab4ddef01573c641920c6547fe646759e738f6b88e1cc32a3991b7b8d311ec9e7189865a33f276057d1ca4f4df10ea7ba8b3a83572fcc9c2ebdd12f4d5df5aa7e40d29101bdbd0301340e67e73efe1c967f993192e636f18e53eaa79d02b1f9baeb378854f5923b5f2acc747f473332a367130c43fdebed9459ae3e0b63a8db966ead97fb2d8f386cab59f55abd5bf69199d5017"
    return fallback

# Force refresh and overwrite the local hidden token file
def refresh_tonton_token():
    return get_tonton_token(force_refresh=True)

# Main entry point for command-line token refresh execution
def main():
    force = "--force" in sys.argv or "-f" in sys.argv
    token = get_tonton_token(force_refresh=force)
    print(f"Active Tonton Token: {token[:40]}... (Length: {len(token)})")

if __name__ == "__main__":
    main()
