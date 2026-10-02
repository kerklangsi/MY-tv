import os
import sys

SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from utils import cleanup_stale_files

# Process Unifi TV live channels placeholder
def process_live(device_id):
    print("--- Processing Unifi TV Live Channels (Placeholder) ---", flush=True)
    os.makedirs("streams/live_unifi", exist_ok=True)
    cleanup_stale_files("streams/live_unifi", set())
    return [], []

# Fetch EPG schedule for Unifi TV channels placeholder
def fetch_epg(epg_channels):
    return []
