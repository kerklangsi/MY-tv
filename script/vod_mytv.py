import urllib.request
import json
import uuid
import os
import re
import stat
from urllib.parse import urlparse
from collections import defaultdict

BASE_API = "https://co3y6iwoio.tenbytecdn.com/api/v1"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/kerklangsi/MY-tv/main"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Origin': 'https://mana2.my',
    'Referer': 'https://mana2.my/',
    'Content-Type': 'application/json'
}

class NoRaiseHTTPErrorProcessor(urllib.request.HTTPErrorProcessor):
    def http_response(self, request, response):
        return response
    https_response = http_response

opener = urllib.request.build_opener(NoRaiseHTTPErrorProcessor)

def http_get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    resp = opener.open(req)
    if 200 <= resp.status < 300:
        return json.loads(resp.read().decode('utf-8'))
    return {}

def http_post(url, payload):
    req = urllib.request.Request(url, headers=HEADERS, data=json.dumps(payload).encode('utf-8'))
    resp = opener.open(req)
    if 200 <= resp.status < 300:
        return json.loads(resp.read().decode('utf-8'))
    return {}

def fetch_raw_text(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 'Referer': 'https://mana2.my/'})
    resp = opener.open(req)
    if 200 <= resp.status < 300:
        return resp.read().decode('utf-8')
    return ""

def slugify(text):
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return re.sub(r'^-+|-+$', '', text)

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

def write_if_changed(filepath, new_content):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            existing = f.read()
        if existing == new_content:
            return False
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True

def cleanup_stale_files(base_directory, active_files_set):
    if not os.path.exists(base_directory):
        return
    deleted_count = 0
    for root, dirs, files in os.walk(base_directory, topdown=False):
        for fname in files:
            if fname.endswith(".m3u8"):
                full_path = os.path.normpath(os.path.join(root, fname))
                if full_path not in active_files_set:
                    if os.path.exists(full_path):
                        os.chmod(full_path, stat.S_IWRITE)
                        os.remove(full_path)
                        print(f"[Deleted] Removed deleted provider file: {full_path}", flush=True)
                        deleted_count += 1
        for dname in dirs:
            dir_path = os.path.join(root, dname)
            if os.path.exists(dir_path) and not os.listdir(dir_path):
                os.chmod(dir_path, stat.S_IWRITE)
                os.rmdir(dir_path)
                print(f"[Deleted] Removed empty folder: {dir_path}", flush=True)
    if deleted_count > 0:
        print(f"Cleaned up {deleted_count} stale/deleted files from {base_directory}.", flush=True)

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

    # Pass 1: Resolve show slug for each item and count episodes per show
    valid_items = []
    slug_counts = defaultdict(int)

    for idx, item in enumerate(shows, 1):
        item_id = item['id']
        item_title = item.get('title', 'Unknown Show')
        if is_teaser_or_trailer(item_title):
            continue

        item_type = item.get('contentType', 'movie')
        if item_type in ['series', 'season', 'show']:
            continue

        subfolder = None
        if item_type == 'episode':
            detail_res = http_get(f"{BASE_API}/public/content/{item_id}")
            series_info = detail_res.get('data', {}).get('series')
            if series_info and series_info.get('id') in official_series_index:
                subfolder = official_series_index[series_info['id']]['clean_slug']
            elif series_info and series_info.get('title'):
                series_title = series_info.get('title')
                subfolder = get_vod_subfolder(series_title, item_type)
                if subfolder == 'movie':
                    subfolder = slugify(series_title)
                    subfolder = re.sub(r'-(?:s|season|siri)-?\d+$', '', subfolder, flags=re.IGNORECASE)

        if not subfolder or subfolder == 'movie':
            subfolder = get_vod_subfolder(item_title, item_type)

        if not subfolder:
            subfolder = 'movie'

        valid_items.append((item, subfolder))
        slug_counts[subfolder] += 1

    # Pass 2: Generate VOD files. If a show folder has < 2 items, place under 'movie' so show folders are never alone!
    vod_entries = []
    used_vod_slugs = set()
    active_files_set = set()

    for idx, (item, prelim_subfolder) in enumerate(valid_items, 1):
        item_id = item['id']
        item_title = item.get('title', 'Unknown Show')
        item_type = item.get('contentType', 'movie')
        item_poster = item.get('posterLandscapeUrl') or item.get('posterPortraitUrl') or item.get('bannerUrl') or ''
        
        # Enforce rule: if a show has only 1 episode across catalog, store in 'movie' so show folders are not alone
        subfolder = prelim_subfolder
        if subfolder != 'movie' and slug_counts[subfolder] < 2:
            subfolder = 'movie'

        folder_path = f"streams/vod_mytv/{subfolder}"
        os.makedirs(folder_path, exist_ok=True)

        title_slug = slugify(item_title)
        base_slug = title_slug if title_slug else (item.get('slug') or item_id)
            
        item_slug = base_slug
        if item_slug in used_vod_slugs:
            item_slug = f"{base_slug}-{item_id}"
        used_vod_slugs.add(item_slug)

        group_title = 'MYTV Shows' if subfolder != 'movie' else 'MYTV Movies'

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
        status_str = "Skipped"

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
            status_str = "Updated" if updated else "Kept (Unchanged)"
                
        clean_url = f"{GITHUB_RAW_BASE}/{folder_path}/{item_slug}.m3u8"
        extinf = f'#EXTINF:-1 tvg-id="{item_slug}" tvg-name="{item_title}" tvg-logo="{item_poster}" group-title="{group_title}",{item_title}'
        vod_entries.append((extinf, clean_url))
        print(f"[{idx}/{len(valid_items)}] [{status_str}] Processed VOD item: {item_title} -> {clean_url}", flush=True)

    # Clean up stale files that are no longer in the provider catalog
    cleanup_stale_files("streams/vod_mytv", active_files_set)

    print(f"Total MYTV VOD items processed: {len(vod_entries)}")
    return vod_entries
