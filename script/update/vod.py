import uuid
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from paths import VOD_M3U, VOD_M3U8

from vod import mytv, tonton, unifi
from utils import save_changed, merge_playlists

# Orchestrate VOD processing and combined playlist creation
def main():
    device_id = str(uuid.uuid4())

    print("\n--- Processing VOD Shows & Movies ---", flush=True)
    mytv_vod_entries = mytv.process_vod(device_id)
    tonton_vod_entries = tonton.process_vod(device_id)
    unifi_vod_entries = unifi.process_vod(device_id)

    vod_lines = ["#EXTM3U"]
    for extinf, extra_lines, url in mytv_vod_entries + tonton_vod_entries + unifi_vod_entries:
        vod_lines.append(extinf)
        for el in extra_lines:
            vod_lines.append(el)
        vod_lines.append(url)

    vod_content = "\n".join(vod_lines) + "\n"
    save_changed(VOD_M3U, vod_content)
    save_changed(VOD_M3U8, vod_content)
    print("Saved merged vod.m3u and vod.m3u8", flush=True)

    merge_playlists()

if __name__ == "__main__":
    main()
