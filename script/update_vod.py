import uuid
import vod_mytv
import vod_tonton
import vod_unifi
from utils import write_if_changed

def main():
    device_id = str(uuid.uuid4())

    print("\n--- Processing VOD Shows & Movies ---", flush=True)
    mytv_vod_entries = vod_mytv.process_vod_shows(device_id)
    tonton_vod_entries = vod_tonton.process_tonton_vod(device_id)
    unifi_vod_entries = vod_unifi.process_unifi_vod(device_id)

    vod_lines = ['#EXTM3U']
    for extinf, url in mytv_vod_entries + tonton_vod_entries + unifi_vod_entries:
        vod_lines.append(extinf)
        vod_lines.append(url)

    vod_content = "\n".join(vod_lines) + "\n"
    write_if_changed("vod.m3u", vod_content)
    write_if_changed("vod.m3u8", vod_content)
    print("Saved merged vod.m3u and vod.m3u8", flush=True)

if __name__ == '__main__':
    main()
