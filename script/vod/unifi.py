import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from paths import VOD_UNIFI

from utils import cleanup_files

# Process Unifi TV VOD catalog placeholder
def process_vod(device_id):
    print("--- Processing Unifi TV VOD (Placeholder) ---", flush=True)
    os.makedirs(VOD_UNIFI, exist_ok=True)
    cleanup_files(VOD_UNIFI, set())
    return []
