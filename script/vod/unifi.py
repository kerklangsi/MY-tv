import os
import sys

SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from utils import cleanup_stale_files

# Process Unifi TV VOD catalog placeholder
def process_vod(device_id):
    print("--- Processing Unifi TV VOD (Placeholder) ---", flush=True)
    os.makedirs("streams/vod_unifi", exist_ok=True)
    cleanup_stale_files("streams/vod_unifi", set())
    return []
