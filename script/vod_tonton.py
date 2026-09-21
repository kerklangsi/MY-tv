import urllib.request
import json
import os
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor

from utils import http_get, fetch_raw_text_and_url, slugify, make_m3u8_absolute, write_if_changed, cleanup_stale_files
from tonton_auth import get_tonton_token

BASE_API = "https://headend-api.tonton.com.my/v600"
GITHUB_URL = "https://kerklangsi.github.io/MY-tv"
USER_AGENT_STR = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML like Gecko) Chrome/120.0.0.0 Safari/537.36"

DEFAULT_DEVICE_ID = "web-v3-0d63fbaa5090547e80c50e9ae5935bfb-6d5145cbec6729682bee9b52f23ef4a9-cmtu0gw320001dt3qqdhki7iz"

PAGE_MAP = [
    ("Cinema", "Tonton Movies"),
    ("DRAMAS", "Tonton Dramas"),
    ("SERIES", "Tonton Series"),
    ("TVTuisyen", "Tonton TV Tuisyen"),
    ("Chinese", "Tonton Chinese"),
]

# Fetch single Tonton VOD playback stream and write m3u8 file.
def process_single_vod_item(task):
    item, group_name, active_files_set, tonton_token = task
    item_id = str(item['id'])
    title = item.get('title') or item.get('name') or 'Unknown Title'
    site_id = str(item.get('siteID', 377))
    v_slug = slugify(title) or item_id
    large_img = item.get('landscapeImage') or item.get('portraitImage') or item.get('image') or ''
    logo = f"{BASE_API}/imageHelper.php?id={large_img}&w=500&appID=TONTON" if large_img else ""
    
    file_path = f"streams/vod_tonton/{v_slug}.m3u8"

    config_url = f"{BASE_API}/api/playback.class.api.php/GOgetVODConfig/{site_id}/1/{item_id}?format=json&appID=TONTON&rate=WIFIHIGH&plt=web&manufacturer=chrome&serviceID=default&model=Mozilla/5.0&firmwareVersion=10&appVersion=6.1.7&deviceOS=PCBROWSER&limitAdTracking=0&deviceId={DEFAULT_DEVICE_ID}&loginToken={tonton_token}"
    res = http_get(config_url, headers={'User-Agent': USER_AGENT_STR})
    playback_data = res.get('playback', {}) or res

    master_url = ""
    if isinstance(playback_data, dict):
        media = playback_data.get('media', {})
        streams = media.get('streams', []) if isinstance(media, dict) else []
        if streams and isinstance(streams, list) and len(streams) > 0:
            master_url = streams[0].get('url', '')
        if not master_url:
            master_url = playback_data.get('url') or playback_data.get('playbackUrl') or ""

    if not master_url:
        live_config_url = f"{BASE_API}/api/playback.class.api.php/GOgetLiveConfig/378/1/{item_id}?format=json&appID=TONTON&rate=WIFIHIGH&plt=web&manufacturer=chrome&serviceID=default&model=Mozilla/5.0&firmwareVersion=10&appVersion=6.1.7&deviceOS=PCBROWSER&limitAdTracking=0&pageId=cinema&deviceId={DEFAULT_DEVICE_ID}&loginToken={tonton_token}"
        live_res = http_get(live_config_url, headers={'User-Agent': USER_AGENT_STR})
        live_pb = live_res.get('playback', {}) or live_res
        if isinstance(live_pb, dict):
            media = live_pb.get('media', {})
            streams = media.get('streams', []) if isinstance(media, dict) else []
            if streams and isinstance(streams, list) and len(streams) > 0:
                master_url = streams[0].get('url', '')
            if not master_url:
                master_url = live_pb.get('url') or live_pb.get('playbackUrl') or ""

    if master_url:
        active_files_set.add(os.path.normpath(file_path))
        master_manifest, final_url = fetch_raw_text_and_url(master_url, headers={'User-Agent': USER_AGENT_STR})
        abs_manifest = make_m3u8_absolute(master_manifest, final_url)
        write_if_changed(file_path, abs_manifest)

        clean_m3u_url = f"{GITHUB_URL}/streams/vod_tonton/{v_slug}.m3u8"
        extinf = f'#EXTINF:-1 tvg-id="{v_slug}" tvg-name="{title}" tvg-logo="{logo}" group-title="{group_name}" http-user-agent="{USER_AGENT_STR}",{title}'
        extra_lines = [f'#EXTVLCOPT:http-user-agent={USER_AGENT_STR}']
        return (extinf, extra_lines, clean_m3u_url)

    return None

# Process all Tonton VOD shows and movies, writing m3u8 manifests and returning M3U entries.
def process_tonton_vod(device_id):
    print("--- Processing Tonton VOD Shows & Movies ---", flush=True)
    os.makedirs("streams/vod_tonton", exist_ok=True)
    active_files_set = set()
    tonton_token = get_tonton_token()

    items_to_process = []
    seen_ids = set()

    for page_id, group_name in PAGE_MAP:
        query = urlencode({
            'id': page_id,
            'version': '6.1.7',
            'format': 'json',
            'apiVersion': '2',
            'appID': 'TONTON',
            'plt': 'web',
            'entitlementToken': '6638ff581ac789188f5b82eaacf3bb22',
            'entitlementClass': 'avod',
            'serviceID': 'default'
        })
        url = f"{BASE_API}/api/bundle.class.api.php/getPage?{query}"
        res = http_get(url, headers={'User-Agent': USER_AGENT_STR})
        blocks = res.get('blocks', []) if isinstance(res, dict) else []

        for b in blocks:
            asset_items = b.get('assetItem', []) or b.get('items', [])
            for item in asset_items:
                item_id = str(item.get('id', ''))
                if item_id and item_id not in seen_ids:
                    seen_ids.add(item_id)
                    items_to_process.append((item, group_name, active_files_set, tonton_token))

    print(f"Total Tonton VOD items cataloged: {len(items_to_process)}", flush=True)

    tonton_vod_entries = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(process_single_vod_item, items_to_process)
        for res in results:
            if res:
                tonton_vod_entries.append(res)

    cleanup_stale_files("streams/vod_tonton", active_files_set)
    print(f"Finished Tonton VOD processing ({len(tonton_vod_entries)} active entries)", flush=True)

    return tonton_vod_entries
