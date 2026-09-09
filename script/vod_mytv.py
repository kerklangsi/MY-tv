import urllib.request
import json
import uuid
import os
import re
from urllib.parse import urlparse

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
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://mana2.my/'})
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

def make_m3u8_absolute(m3u8_text, base_url):
    if not m3u8_text:
        return f"#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-STREAM-INF:BANDWIDTH=4000000\n{base_url}\n"
    parsed = urlparse(base_url)
    base_dir = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rsplit('/', 1)[0]}/"
    query_str = f"?{parsed.query}" if parsed.query else ""
    lines = []

    for line in m3u8_text.splitlines():
        line_str = line.strip()
        if line_str and not line_str.startswith("#"):
            if not line_str.startswith("http://") and not line_str.startswith("https://"):
                # Strip stale static query string from sub-manifest name and apply fresh query string from playbackUrl
                clean_path = line_str.split('?')[0]
                if query_str:
                    line_str = base_dir + clean_path + query_str
                else:
                    line_str = base_dir + clean_path
        lines.append(line_str)
    return "\n".join(lines) + "\n"

def process_vod_shows(device_id):
    print("\n--- Processing MYTV VOD Shows & Movies ---")
    shows = []
    page = 1
    limit = 50

    while True:
        url = f"{BASE_API}/public/content?page={page}&limit={limit}"
        res = http_get(url)
        data = res.get('data', {})
        items = data.get('data', [])
        pagination = data.get('pagination', {})
        
        shows.extend(items)
        total_pages = pagination.get('totalPages', 1)
        if page >= total_pages or len(items) == 0:
            break
        page += 1

    print(f"Total MYTV VOD shows found: {len(shows)}")

    os.makedirs("streams/vod_mytv", exist_ok=True)
    if os.path.exists("streams/vod_mytv"):
        for fname in os.listdir("streams/vod_mytv"):
            fpath = os.path.join("streams/vod_mytv", fname)
            if os.path.isfile(fpath) and fname.endswith(".m3u8"):
                os.remove(fpath)

    vod_entries = []
    used_vod_slugs = set()

    for item in shows:
        item_id = item['id']
        item_title = item.get('title', 'Unknown Show')
        title_slug = slugify(item_title)
        base_slug = title_slug if title_slug else (item.get('slug') or item_id)
            
        item_slug = base_slug
        if item_slug in used_vod_slugs:
            item_slug = f"{base_slug}-{item_id}"
        used_vod_slugs.add(item_slug)

        item_type = item.get('contentType', 'movie')
        item_poster = item.get('posterLandscapeUrl') or item.get('posterPortraitUrl') or item.get('bannerUrl') or ''
        group_title = 'MYTV Shows' if item_type == 'episode' else 'MYTV Movies'

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

        if signed_stream_url:
            master_manifest = fetch_raw_text(signed_stream_url)
            abs_playlist_content = make_m3u8_absolute(master_manifest, signed_stream_url)
            vod_file_path = f"streams/vod_mytv/{item_slug}.m3u8"
            with open(vod_file_path, "w", encoding="utf-8") as f:
                f.write(abs_playlist_content)
                
            clean_url = f"{GITHUB_RAW_BASE}/streams/vod_mytv/{item_slug}.m3u8"
            extinf = f'#EXTINF:-1 tvg-id="{item_slug}" tvg-name="{item_title}" tvg-logo="{item_poster}" group-title="{group_title}",{item_title}'
            vod_entries.append((extinf, clean_url))

    print(f"Total MYTV VOD items processed: {len(vod_entries)}")
    return vod_entries
