import os
from utils import cleanup_stale_files

# Process Unifi TV VOD shows and movies placeholder.
def process_unifi_vod(device_id):
    print("--- Processing Unifi TV VOD (Placeholder) ---", flush=True)
    os.makedirs("streams/vod_unifi", exist_ok=True)
    cleanup_stale_files("streams/vod_unifi", set())
    return []
