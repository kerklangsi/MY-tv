import urllib.request
import json
import os
import sys
import stat
import re
from urllib.parse import urlparse
from collections import defaultdict
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path: sys.path.insert(0, SCRIPT_DIR)

from paths import PLAYLIST, VOD_M3U, ALL_M3U, ALL_M3U8, LIST_LIVE, LIST_SHOWS, LIST_MOVIES, read_auth
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
USER_AGENT = read_auth("user_agent") or DEFAULT_UA

DEFAULT_HEADERS = {
    'User-Agent': USER_AGENT,
    'Content-Type': 'application/json'
}

GITHUB_URL = "https://kerklangsi.github.io/MY-tv"
MANA2_URL = "https://mana2.my"
TONTON_URL = "https://watch.tonton.com.my"
MYTV_API = "https://co3y6iwoio.tenbytecdn.com/api/v1"
TONTON_API = "https://headend-api.tonton.com.my/v600"

class NoRaiseHTTPErrorProcessor(urllib.request.HTTPErrorProcessor):
    # Handle HTTP response without raising exceptions for non-2xx status codes.
    def http_response(self, request, response):
        return response
    def https_response(self, request, response):
        return response

opener = urllib.request.build_opener(NoRaiseHTTPErrorProcessor)

# Perform HTTP GET request and return parsed JSON response data.
def http_get(url, headers=None):
    req_headers = DEFAULT_HEADERS.copy()
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    resp = opener.open(req)
    if 200 <= resp.status < 300:
        return json.loads(resp.read().decode('utf-8'))
    return {}

# Perform HTTP POST request with JSON payload and return parsed JSON response.
def http_post(url, payload, headers=None):
    req_headers = DEFAULT_HEADERS.copy()
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers, data=json.dumps(payload).encode('utf-8'))
    resp = opener.open(req)
    if 200 <= resp.status < 300:
        return json.loads(resp.read().decode('utf-8'))
    return {}

# Convert ISO string or Unix timestamp to XMLTV datetime format
def format_xmltv(val):
    if not val:
        return ""
    try:
        if isinstance(val, (int, float)) or (isinstance(val, str) and val.isdigit()):
            dt_obj = datetime.fromtimestamp(int(val), tz=timezone.utc)
        else:
            clean_str = str(val).replace("Z", "").rsplit(".", 1)[0]
            dt_obj = datetime.strptime(clean_str, "%Y-%m-%dT%H:%M:%S")
        return dt_obj.strftime("%Y%m%d%H%M%S +0000")
    except Exception:
        return ""

# Fetch raw text content from the specified URL
def fetch_raw(url, headers=None):
    return fetch_url(url, headers)[0]

redirect_opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())

# Fetch raw text content and final resolved URL following redirects
def fetch_url(url, headers=None):
    req_headers = {'User-Agent': DEFAULT_HEADERS['User-Agent']}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    try:
        resp = redirect_opener.open(req)
        if 200 <= resp.status < 300:
            return resp.read().decode('utf-8', errors='ignore'), resp.geturl()
    except Exception as e:
        pass
    return "", url

TRANSLATE_CACHE = {}

# Translate foreign text to English using Google Translate with local caching
def auto_translate(text):
    if not text or not re.search(r"[\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f]", text):
        return text
    cached = TRANSLATE_CACHE.get(text)
    if cached:
        return cached
    try:
        q = urllib.parse.urlencode({'client': 'gtx', 'sl': 'auto', 'tl': 'en', 'dt': 't', 'q': text})
        url = f"https://translate.googleapis.com/translate_a/single?{q}"
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        res = json.loads(opener.open(req, timeout=5).read().decode('utf-8'))
        translated = "".join(part[0] for part in res[0] if part and part[0]).strip()
        if translated:
            translated = translated.title()
            TRANSLATE_CACHE[text] = translated
            return translated
    except Exception:
        pass
    return text

# Convert input text string into a clean URL-friendly slug.
def slugify(text):
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return re.sub(r'^-+|-+$', '', text)

# Extract clean episode subtitle by removing series title prefix and episode numbers
def clean_subtitle(title, series):
    t = (title or "").strip()
    s = (series or "").strip()
    s_esc = re.escape(s)
    s_rx = re.sub(r'\\?\s*(?:dan|\\&|&|and)\\?\s*', r'\\s*(?:dan|&|and)\\s*', s_esc, flags=re.IGNORECASE)
    t = re.sub(r'^' + s_rx + r'[\s:|-]*', '', t, flags=re.IGNORECASE).strip()
    t = re.sub(r'^\s*(?:(?:S|Season|Siri)\s*\d+\s*)?(?:Ep|Episod|Episode|Bahagian|Part)\s*\d+\s*[-:\s]*', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s+[-:\s]*(?:(?:S|Season|Siri)\s*\d+\s*)?(?:Ep|Episod|Episode|Bahagian|Part)\s*\d+.*$', '', t, flags=re.IGNORECASE).strip()
    t = re.sub(r'^[\s:|-]+', '', t).strip()
    norm_t = re.sub(r'\s*(?:dan|&|and)\s*', ' ', t, flags=re.IGNORECASE).strip()
    norm_s = re.sub(r'\s*(?:dan|&|and)\s*', ' ', s, flags=re.IGNORECASE).strip()

    clean_cmp_t = re.sub(r'\b(?:s|season|siri)\s*\d+\b', '', norm_t, flags=re.IGNORECASE)
    clean_cmp_t = re.sub(r'[^a-zA-Z0-9]', '', clean_cmp_t).lower()
    clean_cmp_s = re.sub(r'\b(?:s|season|siri)\s*\d+\b', '', norm_s, flags=re.IGNORECASE)
    clean_cmp_s = re.sub(r'[^a-zA-Z0-9]', '', clean_cmp_s).lower()
    if clean_cmp_t == clean_cmp_s:
        return ""
    return "" if norm_t.lower() == norm_s.lower() else t

# Write content to file only if new content differs from existing file content
def save_changed(filepath, new_content, is_binary=False):
    if os.path.exists(filepath):
        mode_read = "rb" if is_binary else "r"
        encoding = None if is_binary else "utf-8"
        with open(filepath, mode_read, encoding=encoding) as f:
            existing = f.read()
        if existing == new_content:
            return False
    mode_write = "wb" if is_binary else "w"
    encoding = None if is_binary else "utf-8"
    with open(filepath, mode_write, encoding=encoding) as f:
        f.write(new_content)
    return True

# Remove stale m3u8 files and empty folders not matching active file set
def cleanup_files(base_directory, active_files_set):
    if not os.path.exists(base_directory):
        return
    deleted_count = 0
    deleted_dirs_count = 0
    for root, dirs, files in os.walk(base_directory, topdown=False):
        for fname in files:
            if fname.endswith(".m3u8"):
                full_path = os.path.normpath(os.path.join(root, fname))
                if full_path not in active_files_set:
                    if os.path.exists(full_path):
                        os.chmod(full_path, stat.S_IWRITE)
                        os.remove(full_path)
                        deleted_count += 1
        for dname in dirs:
            dir_path = os.path.join(root, dname)
            if os.path.exists(dir_path) and not os.listdir(dir_path):
                os.chmod(dir_path, stat.S_IWRITE)
                os.rmdir(dir_path)
                deleted_dirs_count += 1
    if deleted_count > 0 or deleted_dirs_count > 0:
        print(f"Cleaned up {deleted_count} stale/deleted files and {deleted_dirs_count} empty folders from {base_directory}.", flush=True)

# Convert relative segment and playlist paths in M3U8 content into absolute URLs
def make_absolute(m3u8_text, base_url):
    if not m3u8_text:
        return f"#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-STREAM-INF:BANDWIDTH=4000000\n{base_url}\n"
    parsed = urlparse(base_url)
    base_dir = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rsplit('/', 1)[0]}/"
    query_str = f"?{parsed.query}" if parsed.query else ""
    lines = []
    in_ad_block = False

    for line in m3u8_text.splitlines():
        line_str = line.strip()
        if any(ad_tag in line_str for ad_tag in [
            "#EXT-X-CUE-OUT", "#EXT-X-CUE-IN", "#EXT-X-SCTE35", 
            "#EXT-OATCLS-SCTE35", "#EXT-X-ASSET", "DATERANGE:CLASS=\"com.apple.hls.interstitial\"",
            "EXT-X-INTERSTITIAL", "pubads.g.doubleclick.net", "dai.tonton.com.my"
        ]):
            if "#EXT-X-CUE-OUT" in line_str:
                in_ad_block = True
            elif "#EXT-X-CUE-IN" in line_str:
                in_ad_block = False
            continue
            
        if in_ad_block:
            continue
            
        if line_str and not line_str.startswith("#"):
            if not line_str.startswith("http://") and not line_str.startswith("https://"):
                base_part = line_str.split('?')[0]
                if query_str and "?" not in line_str:
                    line_str = base_dir + base_part + query_str
                else:
                    line_str = base_dir + line_str
        lines.append(line_str)

    return "\n".join(lines) + "\n"

# Extract integer channel number from tvg-chno attribute for sorting
def extract_chno(extinf):
    match = re.search(r'tvg-chno="(\d+)"', extinf)
    if match:
        return int(match.group(1))
    return 999999

# Parse M3U playlist file into list of (extinf, extra_lines, url) entries
def parse_m3u(filepath):
    entries = []
    if not os.path.exists(filepath):
        return entries
    with open(filepath, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f.read().splitlines() if l.strip() and not l.startswith("#EXTM3U")]
    i = 0
    while i < len(lines):
        if lines[i].startswith("#EXTINF"):
            extinf = lines[i]
            i += 1
            extra_lines = []
            while i < len(lines) and lines[i].startswith("#EXTVLCOPT"):
                extra_lines.append(lines[i])
                i += 1
            if i < len(lines):
                url = lines[i]
                entries.append((extinf, extra_lines, url))
        i += 1
    return entries

# Merge live TV and VOD playlists into all.m3u and all.m3u8 sorted by tvg-chno
def merge_playlists():
    live_entries = parse_m3u(PLAYLIST)
    vod_entries = parse_m3u(VOD_M3U)

    live_entries.sort(key=lambda item: (extract_chno(item[0]), item[0]))
    vod_entries.sort(key=lambda item: (extract_chno(item[0]), item[0]))

    lines = [f'#EXTM3U x-tvg-url="{GITHUB_URL}/epg.xml.gz"']

    for extinf, extra_lines, url in live_entries + vod_entries:
        lines.append(extinf)
        for el in extra_lines:
            lines.append(el)
        lines.append(url)

    all_content = "\n".join(lines) + "\n"
    save_changed(ALL_M3U, all_content)
    save_changed(ALL_M3U8, all_content)
    print("Saved merged all.m3u and all.m3u8 (Combined Live + VOD, sorted by tvg-chno)", flush=True)

# Update provider section in List/SHOWS_LIST.md with series shows and episodes
def update_shows(provider_key, provider_title, folder_prefix, shows_dict):
    os.makedirs(os.path.dirname(LIST_SHOWS), exist_ok=True)
    existing_content = ""
    if os.path.exists(LIST_SHOWS):
        with open(LIST_SHOWS, "r", encoding="utf-8") as f:
            existing_content = f.read()

    section_lines = []
    section_lines.append(f"<!-- SECTION:{provider_key}:START -->")
    section_lines.append(f"## 📺 {provider_title}\n")
    total_shows = len(shows_dict)
    total_episodes = sum(len(s['episodes']) for s in shows_dict.values())
    playable_total = sum(sum(1 for ep in s['episodes'] if not ep.startswith("🔒")) for s in shows_dict.values())
    vip_total = total_episodes - playable_total
    if vip_total > 0:
        section_lines.append(f"**Total Series Shows:** {total_shows} | **Total Episodes:** {total_episodes} ({playable_total} Playable, {vip_total} VIP)\n")
    else:
        section_lines.append(f"**Total Series Shows:** {total_shows}\n")
    section_lines.append("---\n")

    sorted_slugs = sorted(shows_dict.keys(), key=lambda s: shows_dict[s]['title'].lower())
    for idx, slug in enumerate(sorted_slugs, 1):
        s_data = shows_dict[slug]
        s_title = s_data['title']
        episodes = s_data['episodes']
        playable_count = sum(1 for ep in episodes if not ep.startswith("🔒"))
        vip_count = len(episodes) - playable_count
        if vip_count > 0:
            ep_count_str = f"{len(episodes)} ({playable_count} Playable, {vip_count} VIP)"
        else:
            ep_count_str = f"{len(episodes)}"
        section_lines.append(f"### {idx}. {s_title}")
        section_lines.append(f"- **Folder**: `{folder_prefix}/{slug}`")
        section_lines.append(f"- **Total Episodes**: {ep_count_str}")
        section_lines.append("- **Episode List**:")
        for ep_str in episodes:
            section_lines.append(f"  - {ep_str}")
        section_lines.append("")
    section_lines.append(f"<!-- SECTION:{provider_key}:END -->")
    new_section = "\n".join(section_lines)

    start_tag = f"<!-- SECTION:{provider_key}:START -->"
    end_tag = f"<!-- SECTION:{provider_key}:END -->"

    if start_tag in existing_content and end_tag in existing_content:
        s_idx = existing_content.find(start_tag)
        e_idx = existing_content.find(end_tag) + len(end_tag)
        final_content = existing_content[:s_idx] + new_section + existing_content[e_idx:]
    elif provider_key == 'TONTON' and "<!-- SECTION:MYTV:START -->" not in existing_content and existing_content:
        final_content = f"# VOD Series Catalog - Full Show List with Episodes\n\n<!-- SECTION:MYTV:START -->\n{existing_content.strip()}\n<!-- SECTION:MYTV:END -->\n\n{new_section}\n"
    else:
        header = "# VOD Series Catalog - Full Show List with Episodes\n\n" if not existing_content.strip().startswith("# VOD Series Catalog") else ""
        final_content = (existing_content.rstrip() + "\n\n" + new_section + "\n") if existing_content else (header + new_section + "\n")

    save_changed(LIST_SHOWS, final_content)

# Update provider section in List/MOVIES_LIST.md with standalone movies and durations
def update_movies(provider_key, provider_title, movies_list):
    os.makedirs(os.path.dirname(LIST_MOVIES), exist_ok=True)
    existing_content = ""
    if os.path.exists(LIST_MOVIES):
        with open(LIST_MOVIES, "r", encoding="utf-8") as f:
            existing_content = f.read()

    section_lines = []
    section_lines.append(f"<!-- SECTION:{provider_key}:START -->")
    section_lines.append(f"## 🎬 {provider_title}\n")
    playable_m = sum(1 for m in movies_list if m.get('url'))
    vip_m = len(movies_list) - playable_m
    if vip_m > 0:
        section_lines.append(f"**Total Standalone Movies:** {len(movies_list)} ({playable_m} Playable, {vip_m} VIP)\n")
    else:
        section_lines.append(f"**Total Standalone Movies:** {len(movies_list)}\n")
    section_lines.append("---\n")
    section_lines.append("| # | Movie Title | Stream File | Duration | Release Date |")
    section_lines.append("|---|---|---|---|---|")

    default_badge = "🔒 *(Requires Tonton UP / VIP)*" if provider_key == 'TONTON' else "N/A"
    for idx, m in enumerate(movies_list, 1):
        m_title = m.get('title', 'Unknown Movie')
        dur = m.get('duration') or 0
        if isinstance(dur, str) and dur.isdigit():
            dur = int(dur)
        dur_str = f"{dur // 60}m {dur % 60}s" if dur > 0 else "N/A"
        m_url = m.get('url') or ""
        badge = m.get('badge') or default_badge
        stream_link = f"[Play .m3u8]({m_url})" if m_url else badge
        section_lines.append(f"| {idx} | **{m_title}** | {stream_link} | {dur_str} | N/A |")
    section_lines.append(f"\n<!-- SECTION:{provider_key}:END -->")
    new_section = "\n".join(section_lines)

    start_tag = f"<!-- SECTION:{provider_key}:START -->"
    end_tag = f"<!-- SECTION:{provider_key}:END -->"

    if start_tag in existing_content and end_tag in existing_content:
        s_idx = existing_content.find(start_tag)
        e_idx = existing_content.find(end_tag) + len(end_tag)
        final_content = existing_content[:s_idx] + new_section + existing_content[e_idx:]
    elif provider_key == 'TONTON' and "<!-- SECTION:MYTV:START -->" not in existing_content and existing_content:
        final_content = f"# VOD Standalone Movies List\n\n<!-- SECTION:MYTV:START -->\n{existing_content.strip()}\n<!-- SECTION:MYTV:END -->\n\n{new_section}\n"
    else:
        header = "# VOD Standalone Movies List\n\n" if not existing_content.strip().startswith("# VOD Standalone Movies List") else ""
        final_content = (existing_content.rstrip() + "\n\n" + new_section + "\n") if existing_content else (header + new_section + "\n")

    save_changed(LIST_MOVIES, final_content)

# Generate or update List/LIVE_LIST.md catalog documentation with all live TV and radio channels
def update_live(live_entries):
    os.makedirs(os.path.dirname(LIST_LIVE), exist_ok=True)
    categories = defaultdict(list)
    for extinf, extra_lines, url in live_entries:
        chno_m = re.search(r'tvg-chno="(\d+)"', extinf)
        name_m = re.search(r'tvg-name="([^"]+)"', extinf)
        id_m = re.search(r'tvg-id="([^"]+)"', extinf)
        logo_m = re.search(r'tvg-logo="([^"]+)"', extinf)
        group_m = re.search(r'group-title="([^"]+)"', extinf)
        chno = chno_m.group(1) if chno_m else "N/A"
        name = name_m.group(1) if name_m else "Unknown Channel"
        tvg_id = id_m.group(1) if id_m else ""
        logo = logo_m.group(1) if logo_m else ""
        group = group_m.group(1) if group_m else "Other Channels"
        categories[group].append({
            'chno': chno,
            'name': name,
            'tvg_id': tvg_id,
            'logo': logo,
            'url': url
        })

    total_ch = len(live_entries)
    playable_all = sum(1 for e in live_entries if e[2])
    vip_all = total_ch - playable_all
    tot_str = f"{total_ch} ({playable_all} Playable, {vip_all} VIP)" if vip_all > 0 else f"{total_ch}"

    lines = [
        "# 📡 Live TV & Radio Channels Directory",
        "",
        f"**Total Live Channels:** {tot_str}",
        "",
        "> Master Playlists: [`playlist.m3u`](../playlist.m3u) | [`playlist.m3u8`](../playlist.m3u8) | [`all.m3u`](../all.m3u) | [`all.m3u8`](../all.m3u8)",
        "> EPG Schedule: [`epg.xml`](../epg.xml) | [`epg.xml.gz`](../epg.xml.gz)",
        "",
        "---",
        ""
    ]

    for group, ch_list in categories.items():
        lines.append(f"## {group}")
        playable_c = sum(1 for c in ch_list if c['url'])
        vip_c = len(ch_list) - playable_c
        if vip_c > 0:
            lines.append(f"**Total Channels:** {len(ch_list)} ({playable_c} Playable, {vip_c} VIP)\n")
        else:
            lines.append(f"**Total Channels:** {len(ch_list)}\n")
        lines.append("| CH # | Logo | Channel Name | EPG ID | Stream Link |")
        lines.append("|:---:|:---:|---|---|---|")
        for ch in ch_list:
            logo_img = f'<img src="{ch["logo"]}" width="40" height="40" alt="{ch["name"]}" />' if ch["logo"] else "-"
            stream_link = f"[Play Stream]({ch['url']})" if ch['url'] else "🔒 *(Requires Tonton UP / VIP)*"
            lines.append(f"| {ch['chno']} | {logo_img} | **{ch['name']}** | `{ch['tvg_id']}` | {stream_link} |")
        lines.append("\n---\n")

    save_changed(LIST_LIVE, "\n".join(lines) + "\n")
    print(f"Generated Live Channel Catalog at {LIST_LIVE} ({len(live_entries)} channels)", flush=True)

