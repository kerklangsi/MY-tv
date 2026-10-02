import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from auth.mytv import get_key, ME_KEY, read_auth
from auth.tonton import (
    get_token,
    refresh_token,
    get_device,
    check_token,
    get_ua,
    USER_AGENT,
    DEVICE_ID,
    EMAIL,
    PASSWORD,
)
from auth.unifi import get_token as get_unifi_token

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
