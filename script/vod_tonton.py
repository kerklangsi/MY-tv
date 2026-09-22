import urllib.request
import json
import os
import re
import uuid
from urllib.parse import urlencode
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from utils import http_get, fetch_raw_text_and_url, slugify, make_m3u8_absolute, write_if_changed, cleanup_stale_files, update_catalog_shows, update_catalog_movies
from auth import get_token, USER_AGENT, DEVICE_ID

BASE_API = "https://headend-api.tonton.com.my/v600"
GITHUB_URL = "https://kerklangsi.github.io/MY-tv"

PAGE_MAP = [
    ("Cinema", "Tonton Movies"),
    ("DRAMAS", "Tonton Dramas"),
    ("SERIES", "Tonton Series"),
    ("TVTuisyen", "Tonton TV Tuisyen"),
    ("Chinese", "Tonton Chinese"),
]

# Remove Chinese and non-Latin CJK characters from title strings.
def clean_chinese_chars(text):
    if not text:
        return ""
    cleaned = re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf\u2e80-\u2eff\u3000-\u303f\uff00-\uffef\u2000-\u206f\ufe30-\ufe4f]+', '', text)
    cleaned = re.sub(r'(\b\d+\b)\s+\1$', r'\1', cleaned)
    cleaned = re.sub(r'^[|\s\-:!]+|[|\s\-:!]+$', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned if cleaned else text

# Determine subfolder directory slug and display title for a Tonton VOD series or movie item.
def get_tonton_subfolder(item):
    item_type = item.get('type', '')
    raw_title = item.get('show_title') or item.get('title') or item.get('name') or 'Unknown Title'
    title = clean_chinese_chars(raw_title)
    show_id = item.get('show_id') or item.get('showId') or ''
    group_name = item.get('group_name', '')

    if item_type == 'movie' or group_name == 'Tonton Movies':
        return 'movie', 'Movies'

    if show_id:
        clean_show = re.sub(r'-(?:series|siri)$', '', show_id, flags=re.IGNORECASE)
        s_slug = slugify(clean_show)
        if s_slug and s_slug != 'movie':
            display_title = title if title else clean_chinese_chars(clean_show.replace('-', ' ').replace('_', ' ').title())
            return s_slug, display_title

    return slugify(title) or 'movie', title

# Expand a series show container item into individual episode asset items via GOgetAssetData API.
def fetch_show_episodes(item):
    item_type = item.get('type', '')
    if item_type == 'movie' or item.get('group_name') == 'Tonton Movies':
        return [item]

    show_id = item.get('showId') or item.get('id')
    if not show_id:
        return [item]

    url = f"{BASE_API}/api/asset.class.api.php/GOgetAssetData/377/0?format=json&showId={show_id}&serviceID=default&dateFormat=ISO8601&appID=TONTON"
    show_data = http_get(url, headers={'User-Agent': USER_AGENT})
    if not show_data or not isinstance(show_data, dict):
        return [item]

    raw_show_title = show_data.get('title') or item.get('title') or item.get('name') or 'Unknown Show'
    show_title = clean_chinese_chars(raw_show_title)
    seasons = show_data.get('childAssets', {}).get('items', [])
    if not seasons or not isinstance(seasons, list):
        return [item]

    episodes = []
    for s in seasons:
        child_eps = s.get('childAssets', {}).get('items', [])
        if child_eps and isinstance(child_eps, list):
            for ep in child_eps:
                ep['show_title'] = show_title
                ep['show_id'] = show_id
                ep['group_name'] = item.get('group_name', 'Tonton Dramas')
                episodes.append(ep)

    return episodes if episodes else [item]


# Fetch single Tonton VOD playback stream and write m3u8 file into subfolder using episode slug.
def process_single_vod_item(task):
    item, group_name, active_files_set, tonton_token = task
    item_id = str(item['id'])
    
    subfolder, display_show_title = get_tonton_subfolder(item)
    folder_path = f"streams/vod_tonton/{subfolder}"

    ep_num = item.get('episodeNumber')
    raw_ep_title = item.get('episodeTitle') or item.get('title') or item.get('name') or 'Unknown Episode'
    ep_title = clean_chinese_chars(raw_ep_title)
    
    if subfolder == 'movie':
        ep_slug = slugify(ep_title) or item_id
        entry_title = ep_title
    else:
        if ep_num:
            ep_slug = f"{subfolder}-ep-{ep_num}"
            entry_title = f"{display_show_title} - Episod {ep_num}"
        else:
            ep_slug = slugify(ep_title) or item_id
            entry_title = f"{display_show_title} - {ep_title}"

    file_path = f"{folder_path}/{ep_slug}.m3u8"
    site_id = str(item.get('siteID') or item.get('site_id') or 377)
    large_img = item.get('landscapeImage') or item.get('portraitImage') or item.get('image') or ''
    logo = f"{BASE_API}/imageHelper.php?id={large_img}&w=500&appID=TONTON" if large_img else ""

    config_url = f"{BASE_API}/api/playback.class.api.php/GOgetVODConfig/{site_id}/1/{item_id}?format=json&appID=TONTON&rate=WIFIHIGH&plt=web&manufacturer=chrome&serviceID=default&model=Mozilla/5.0&firmwareVersion=10&appVersion=6.1.7&deviceOS=PCBROWSER&limitAdTracking=0&deviceId={DEVICE_ID}&loginToken={tonton_token}"
    res = http_get(config_url, headers={'User-Agent': USER_AGENT})
    playback_data = res.get('playback', {}) or res

    err_code = str(res.get('errorCode') or (res.get('playback') or {}).get('errorCode') or '')

    master_url = ""
    if isinstance(playback_data, dict):
        media = playback_data.get('media', {})
        streams = media.get('streams', []) if isinstance(media, dict) else []
        if streams and isinstance(streams, list) and len(streams) > 0:
            master_url = streams[0].get('url', '')
        if not master_url:
            master_url = playback_data.get('url') or playback_data.get('playbackUrl') or ""

    if not master_url and err_code != 'PS4033' and subfolder == 'movie':
        live_config_url = f"{BASE_API}/api/playback.class.api.php/GOgetLiveConfig/378/1/{item_id}?format=json&appID=TONTON&rate=WIFIHIGH&plt=web&manufacturer=chrome&serviceID=default&model=Mozilla/5.0&firmwareVersion=10&appVersion=6.1.7&deviceOS=PCBROWSER&limitAdTracking=0&pageId=cinema&deviceId={DEVICE_ID}&loginToken={tonton_token}"
        live_res = http_get(live_config_url, headers={'User-Agent': USER_AGENT})
        live_pb = live_res.get('playback', {}) or live_res
        if isinstance(live_pb, dict):
            media = live_pb.get('media', {})
            streams = media.get('streams', []) if isinstance(media, dict) else []
            if streams and isinstance(streams, list) and len(streams) > 0:
                master_url = streams[0].get('url', '')
            if not master_url:
                master_url = live_pb.get('url') or live_pb.get('playbackUrl') or ""

    if master_url:
        os.makedirs(folder_path, exist_ok=True)
        active_files_set.add(os.path.normpath(file_path))
        master_manifest, final_url = fetch_raw_text_and_url(master_url, headers={'User-Agent': USER_AGENT})
        abs_manifest = make_m3u8_absolute(master_manifest, final_url)
        write_if_changed(file_path, abs_manifest)

        clean_m3u_url = f"{GITHUB_URL}/{folder_path}/{ep_slug}.m3u8"
        extinf = f'#EXTINF:-1 tvg-id="{ep_slug}" tvg-name="{entry_title}" tvg-logo="{logo}" group-title="{group_name}" http-user-agent="{USER_AGENT}",{entry_title}'
        extra_lines = [f'#EXTVLCOPT:http-user-agent={USER_AGENT}']
        return (extinf, extra_lines, clean_m3u_url, item, subfolder, display_show_title, True)

    return (None, [], None, item, subfolder, display_show_title, False)

# Process all Tonton VOD shows and movies, expanding series into episodes and generating catalog manifests.
def process_tonton_vod(device_id):
    print("--- Processing Tonton VOD Shows & Movies ---", flush=True)
    os.makedirs("streams/vod_tonton", exist_ok=True)
    active_files_set = set()
    tonton_token = get_token()

    raw_catalog_items = []
    seen_show_ids = set()

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
        res = http_get(url, headers={'User-Agent': USER_AGENT})
        blocks = res.get('blocks', []) if isinstance(res, dict) else []

        for b in blocks:
            asset_items = b.get('assetItem', []) or b.get('items', [])
            for item in asset_items:
                item_id = str(item.get('id', ''))
                if item_id and item_id not in seen_show_ids:
                    seen_show_ids.add(item_id)
                    item['group_name'] = group_name
                    raw_catalog_items.append(item)

    print(f"Total Tonton VOD catalog shows/movies fetched: {len(raw_catalog_items)}", flush=True)

    expanded_episodes = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = executor.map(fetch_show_episodes, raw_catalog_items)
        for ep_list in results:
            expanded_episodes.extend(ep_list)

    print(f"Total Tonton VOD expanded episodes/movies: {len(expanded_episodes)}", flush=True)

    items_to_process = [(ep, ep.get('group_name', 'Tonton Dramas'), active_files_set, tonton_token) for ep in expanded_episodes]

    tonton_vod_entries = []
    tonton_shows_dict = defaultdict(lambda: {'title': '', 'episodes': []})
    tonton_movies_list = []

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = executor.map(process_single_vod_item, items_to_process)
        for res in results:
            if not res:
                continue
            extinf, extra_lines, clean_m3u_url, ep, subfolder, display_title, is_playable = res
            if is_playable and extinf and clean_m3u_url:
                tonton_vod_entries.append((extinf, extra_lines, clean_m3u_url))

            if subfolder == 'movie':
                raw_m_t = ep.get('title') or ep.get('name') or 'Unknown Movie'
                m_t = clean_chinese_chars(raw_m_t)
                dur = ep.get('duration') or 0
                if is_playable:
                    tonton_movies_list.append({'title': m_t, 'duration': dur, 'url': clean_m3u_url})
                else:
                    tonton_movies_list.append({'title': m_t, 'duration': dur, 'url': None, 'badge': '🔒 *(Requires Tonton UP / VIP)*'})
            else:
                if subfolder not in tonton_shows_dict:
                    tonton_shows_dict[subfolder]['title'] = display_title
                raw_ep_t = ep.get('title') or ep.get('name') or ep.get('episodeTitle') or 'Unknown Episode'
                ep_t = clean_chinese_chars(raw_ep_t)
                ep_num = ep.get('episodeNumber')
                if ep_num and not ep_t.lower().startswith(f"episod {ep_num}".lower()) and not ep_t.lower().startswith(f"episode {ep_num}".lower()):
                    ep_label = f"Episod {ep_num} - {ep_t}"
                else:
                    ep_label = ep_t

                if is_playable:
                    ep_str = f"[{ep_label}]({clean_m3u_url})"
                else:
                    ep_str = f"🔒 {ep_label} *(Requires Tonton UP / VIP)*"
                tonton_shows_dict[subfolder]['episodes'].append(ep_str)

    cleanup_stale_files("streams/vod_tonton", active_files_set)

    update_catalog_shows('TONTON', 'Tonton Shows', 'streams/vod_tonton', tonton_shows_dict)
    update_catalog_movies('TONTON', 'Tonton Feature Movies', tonton_movies_list)
    print(f"Finished Tonton VOD processing ({len(tonton_vod_entries)} active entries)", flush=True)

    return tonton_vod_entries

if __name__ == '__main__':
    dev_id = str(uuid.uuid4()) if 'uuid' in dir() else 'standalone_dev'
    process_tonton_vod(dev_id)
