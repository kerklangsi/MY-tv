import os
from utils import cleanup_stale_files

def process_tonton_vod(device_id):
    print("--- Processing Tonton VOD (Placeholder) ---")
    os.makedirs("streams/vod_tonton", exist_ok=True)
    cleanup_stale_files("streams/vod_tonton", set())
    return []
