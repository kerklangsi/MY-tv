import urllib.request
import json
import uuid
import os
import re
import stat
from urllib.parse import urlparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from utils import http_get, http_post, fetch_raw_text, slugify, write_if_changed, cleanup_stale_files

BASE_API = "https://co3y6iwoio.tenbytecdn.com/api/v1"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/kerklangsi/MY-tv/main"

def get_vod_subfolder(title, content_type):
    if not title:
        return 'movie'

    ep_pattern = r'(?:(?:S|Season|Siri)\s*\d+\s*)?(?:Ep|Episod|Episode|Bahagian|Part)\s*\d+'

    s_slug = None

    # 1. Episode prefix FIRST (e.g. "Episode 25 - The Trap", "Ep 10 - Draping Loose Blouse")
    m_start = re.match(r'^\s*' + ep_pattern + r'\s*[-:\s]+(.*)$', title, re.IGNORECASE)
    if m_start and m_start.group(1).strip():
        s_slug = slugify(m_start.group(1))

    # 2. Episode marker in MIDDLE/END (e.g. "Wedding Stone Ep 6", "Pemerindang Borneo S2 Ep 1", "TRIP Episod 2")
    if not s_slug:
        m_end = re.match(r'^(.*?)\s+[-:\s]*' + ep_pattern, title, re.IGNORECASE)
        if m_end and m_end.group(1).strip():
            s_slug = slugify(m_end.group(1))

    # 3. Trailing numbers if content_type == 'episode' (e.g. "Peknga 2")
    if not s_slug:
        m_num = re.match(r'^(.*?)\s+\d+$', title)
        if m_num and content_type == 'episode' and m_num.group(1).strip():
            s_slug = slugify(m_num.group(1))

    # 4. Season tag at end of title (e.g. "Khazanah Kenyalang S1", "Aroma Sungkei S2")
    if not s_slug:
        m_season = re.match(r'^(.*?)\s+[-:\s]*(?:S|Season|Siri)\s*\d+$', title, re.IGNORECASE)
        if m_season and m_season.group(1).strip():
            s_slug = slugify(m_season.group(1))

    if s_slug:
        # Strip trailing season indicators from slug (e.g. "khazanah-kenyalang-s1" -> "khazanah-kenyalang")
        s_slug = re.sub(r'-(?:s|season|siri)-?\d+$', '', s_slug, flags=re.IGNORECASE)
        if s_slug:
            return s_slug

    return 'movie'

PROMO_KEYWORDS = {'teaser', 'trailer', 'promo', 'preview', 'highlight', 'highlights', 'behind the scene', 'behind the scenes', 'bts', 'sedutan'}

def is_teaser_or_trailer(title):
    if not title:
        return False
    t_lower = title.lower()
    for kw in PROMO_KEYWORDS:
        if re.search(r'\b' + re.escape(kw) + r'\b', t_lower):
            return True
    return False

def process_vod_shows(device_id):
    print("\n--- Processing MYTV VOD Shows & Movies ---")

    # Step 1: Pre-fetch official Series Index from mana2.my API
    official_series_index = {}
    s_page = 1
    while True:
        s_res = http_get(f"{BASE_API}/public/content?contentType=series&page={s_page}&limit=100")
        s_items = s_res.get('data', {}).get('data', [])
        if not s_items:
            break
        for s in s_items:
            s_id = s['id']
            s_title = s.get('title', '')
            clean_slug = slugify(s_title)
            clean_slug = re.sub(r'-(?:s|season|siri)-?\d+$', '', clean_slug, flags=re.IGNORECASE)
            official_series_index[s_id] = {
                'raw_title': s_title,
                'clean_slug': clean_slug
            }
        total_s = s_res.get('data', {}).get('total', 0)
        if len(official_series_index) >= total_s:
            break
        s_page += 1

    print(f"Loaded {len(official_series_index)} official series from mana2.my index.", flush=True)

    # Build title keyword mapping from official series index
    official_title_keywords = []
    for s_id, s_info in official_series_index.items():
        raw_lower = s_info['raw_title'].lower().strip()
        raw_clean = re.sub(r'\s+[-:\s]*(?:S|Season|Siri)\s*\d+$', '', raw_lower, flags=re.IGNORECASE)
        if len(raw_clean) >= 3:
            official_title_keywords.append((raw_clean, s_info['clean_slug']))

    official_title_keywords.sort(key=lambda x: len(x[0]), reverse=True)

    shows = []
    page = 1
    limit = 50

    while True:
        url = f"{BASE_API}/public/content?page={page}&limit={limit}"
        res = http_get(url)
        data = res.get('data', {})
        items = data.get('data', [])
        total = data.get('total', 0)
        
        shows.extend(items)
        total_pages = (total + limit - 1) // limit if limit > 0 else 1
        if page >= total_pages or len(items) == 0:
            break
        page += 1

    print(f"Total MYTV VOD items found: {len(shows)}")

    os.makedirs("streams/vod_mytv", exist_ok=True)

    # Pre-fetch detail API for episode items in parallel
    ep_items = [
        item for item in shows
        if not is_teaser_or_trailer(item.get('title'))
        and item.get('contentType') not in ['series', 'season', 'show']
        and (item.get('contentType') == 'episode' or re.match(r'^\s*(?:Ep|Episod|Episode|S\d+)', item.get('title', ''), re.IGNORECASE))
    ]

    detail_cache_map = {}
    with ThreadPoolExecutor(max_workers=25) as executor:
        for item_id, series_info in executor.map(lambda it: (it['id'], (http_get(f"{BASE_API}/public/content/{it['id']}").get('data', {}).get('series') or {})), ep_items):
            detail_cache_map[item_id] = series_info

    # Single Pass: Resolve subfolder and count frequencies
    prelim_items = []
    slug_counts = defaultdict(int)

    for item in shows:
        item_title = item.get('title', 'Unknown Show')
        if is_teaser_or_trailer(item_title):
            continue

        item_type = item.get('contentType', 'movie')
        if item_type in ['series', 'season', 'show']:
            continue

        subfolder = None

        # 1. Detail API series metadata
        if item['id'] in detail_cache_map:
            s_info = detail_cache_map[item['id']]
            s_slug = s_info.get('slug') or slugify(s_info.get('title'))
            if s_slug:
                subfolder = re.sub(r'-(?:s|season|siri)-?\d+$', '', s_slug, flags=re.IGNORECASE)

        # 2. Official title keyword match
        if not subfolder:
            t_lower = item_title.lower()
            for kw_raw, kw_slug in official_title_keywords:
                if kw_raw in t_lower:
                    subfolder = kw_slug
                    break

        # 3. Regex title structure fallback
        if not subfolder:
            subfolder = get_vod_subfolder(item_title, item_type)

        if not subfolder:
            subfolder = 'movie'

        prelim_items.append((item, subfolder))
        slug_counts[subfolder] += 1

    # Group items into final subfolders
    items_by_subfolder = defaultdict(list)
    for item, subfolder in prelim_items:
        if subfolder != 'movie' and slug_counts[subfolder] < 2:
            subfolder = 'movie'

        if subfolder == 'movie':
            dur_sec = item.get('durationSeconds') or 0
            if 0 < dur_sec < 1200:
                subfolder = 'short-movies-and-clips'

        items_by_subfolder[subfolder].append(item)

    vod_entries = []
    used_vod_slugs = set()
    active_files_set = set()
    total_subfolders = len(items_by_subfolder)

    sorted_subfolders = sorted([sf for sf in items_by_subfolder.keys() if sf not in ['movie', 'short-movies-and-clips']])
    if 'short-movies-and-clips' in items_by_subfolder:
        sorted_subfolders.append('short-movies-and-clips')
    if 'movie' in items_by_subfolder:
        sorted_subfolders.append('movie')

    for idx, subfolder in enumerate(sorted_subfolders, 1):
        sub_items = items_by_subfolder[subfolder]
        folder_path = f"streams/vod_mytv/{subfolder}"
        os.makedirs(folder_path, exist_ok=True)
        if subfolder == 'short-movies-and-clips':
            group_title = 'MYTV Short Movies'
        elif subfolder == 'movie':
            group_title = 'MYTV Movies'
        else:
            group_title = 'MYTV Shows'

        updated_count = 0
        kept_count = 0

        for item in sub_items:
            item_id = item['id']
            item_title = item.get('title', 'Unknown Show')
            item_poster = item.get('posterLandscapeUrl') or item.get('posterPortraitUrl') or item.get('bannerUrl') or ''

            title_slug = slugify(item_title)
            if subfolder in ['movie', 'short-movies-and-clips']:
                clean_t = re.sub(r'^\s*(?:(?:S|Season|Siri)\s*\d+\s*)?(?:Ep|Episod|Episode|Bahagian|Part)\s*\d+\s*[-:\s]*', '', item_title, flags=re.IGNORECASE)
                clean_t = re.sub(r'\s+[-:\s]*(?:(?:S|Season|Siri)\s*\d+\s*)?(?:Ep|Episod|Episode|Bahagian|Part)\s*\d+.*$', '', clean_t, flags=re.IGNORECASE)
                if clean_t.strip():
                    title_slug = slugify(clean_t)
            base_slug = title_slug if title_slug else (item.get('slug') or item_id)
            item_slug = base_slug
            if item_slug in used_vod_slugs:
                item_slug = f"{base_slug}-{item_id}"
            used_vod_slugs.add(item_slug)

            play_payload = {
                "contentId": item_id,
                "deviceId": device_id,
                "protocol": "hls",
                "context": {
                    "deviceType": "web",
                    "app": "mytv-web",
                    "appVersion": "0.1.0",
                    "os": "Windows",
                    "network": "wifi"
                }
            }
            
            play_res = http_post(f"{BASE_API}/public/streaming/play", play_payload)
            signed_stream_url = play_res.get('data', {}).get('playbackUrl', '')
            master_file_path = f"{folder_path}/{item_slug}.m3u8"
            active_files_set.add(os.path.normpath(master_file_path))

            if signed_stream_url:
                master_manifest = fetch_raw_text(signed_stream_url)
                parsed_master = urlparse(signed_stream_url)
                fresh_query = f"?{parsed_master.query}" if parsed_master.query else ""
                path_dir = parsed_master.path.rsplit('/', 1)[0]
                base_cdn_dir = f"{parsed_master.scheme}://{parsed_master.netloc}{path_dir}/"
                
                absolute_master_lines = []
                for line in master_manifest.splitlines():
                    line_str = line.strip()
                    if line_str and not line_str.startswith("#"):
                        sub_filename = line_str.split('?')[0]
                        abs_sub_url = base_cdn_dir + sub_filename + fresh_query
                        absolute_master_lines.append(abs_sub_url)
                    else:
                        absolute_master_lines.append(line)
                        
                new_manifest_content = "\n".join(absolute_master_lines) + "\n"
                updated = write_if_changed(master_file_path, new_manifest_content)
                if updated:
                    updated_count += 1
                else:
                    kept_count += 1

            clean_url = f"{GITHUB_RAW_BASE}/{folder_path}/{item_slug}.m3u8"
            extinf = f'#EXTINF:-1 tvg-id="{item_slug}" tvg-name="{item_title}" tvg-logo="{item_poster}" group-title="{group_title}",{item_title}'
            vod_entries.append((extinf, clean_url))

        folder_label = f"Series '{subfolder}'" if subfolder != 'movie' else "Category 'movies'"
        print(f"[{idx}/{total_subfolders}] Processed {folder_label} ({len(sub_items)} items: {updated_count} updated, {kept_count} kept)", flush=True)

    # Clean up stale files that are no longer in the provider catalog
    cleanup_stale_files("streams/vod_mytv", active_files_set)

    print(f"Total MYTV VOD items processed: {len(vod_entries)}")
    return vod_entries
