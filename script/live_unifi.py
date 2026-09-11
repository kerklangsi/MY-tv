import os
from utils import cleanup_stale_files

def process_unifi_live_channels(device_id):
    print("--- Processing Unifi TV Live Channels (Placeholder) ---", flush=True)
    os.makedirs("streams/live_unifi", exist_ok=True)
    cleanup_stale_files("streams/live_unifi", set())
    return [], []

def fetch_unifi_epg_programmes(epg_channels):
    return []
