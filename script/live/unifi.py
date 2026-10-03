import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from paths import LIVE_UNIFI

from utils import cleanup_files

# Process Unifi TV live channels placeholder
def process_live(device_id):
    print("--- Processing Unifi TV Live Channels (Placeholder) ---", flush=True)
    os.makedirs(LIVE_UNIFI, exist_ok=True)
    cleanup_files(LIVE_UNIFI, set())
    return [], []

# Fetch EPG schedule for Unifi TV channels placeholder
def fetch_epg(epg_channels):
    return []
