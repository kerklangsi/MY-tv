import urllib.request
import json
import os
import sys
import stat
import re
from urllib.parse import urlparse
from collections import defaultdict

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Content-Type': 'application/json'
}

class NoRaiseHTTPErrorProcessor(urllib.request.HTTPErrorProcessor):
    # Handle HTTP response without raising exceptions for non-2xx status codes.
    def http_response(self, request, response):
        return response
    https_response = http_response

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

# Fetch raw text content from the specified URL.
def fetch_raw_text(url, headers=None):
    req_headers = {'User-Agent': DEFAULT_HEADERS['User-Agent']}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    resp = opener.open(req)
    if 200 <= resp.status < 300:
        return resp.read().decode('utf-8')
    return ""

redirect_opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())

# Fetch raw text content and final resolved URL following redirects.
def fetch_raw_text_and_url(url, headers=None):
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

# Convert input text string into a clean URL-friendly slug.
def slugify(text):
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return re.sub(r'^-+|-+$', '', text)

# Write content to file only if new content differs from existing file content.
def write_if_changed(filepath, new_content, is_binary=False):
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

# Remove stale m3u8 files and empty folders not matching active file set.
def cleanup_stale_files(base_directory, active_files_set):
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

# Convert relative segment and playlist paths in M3U8 content into absolute URLs.
def make_m3u8_absolute(m3u8_text, base_url):
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

# Extract integer channel number from tvg-chno attribute for sorting.
def extract_chno_from_extinf(extinf):
    match = re.search(r'tvg-chno="(\d+)"', extinf)
    if match:
        return int(match.group(1))
    return 999999

# Parse M3U playlist file into list of (extinf, extra_lines, url) entries.
def parse_m3u_entries(filepath):
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

# Merge live TV and VOD playlists into all.m3u and all.m3u8 sorted by tvg-chno.
def update_combined_playlist():
    live_entries = parse_m3u_entries("playlist.m3u")
    vod_entries = parse_m3u_entries("vod.m3u")

    live_entries.sort(key=lambda item: (extract_chno_from_extinf(item[0]), item[0]))
    vod_entries.sort(key=lambda item: (extract_chno_from_extinf(item[0]), item[0]))

    lines = ['#EXTM3U x-tvg-url="https://kerklangsi.github.io/MY-tv/epg.xml.gz"']

    for extinf, extra_lines, url in live_entries + vod_entries:
        lines.append(extinf)
        for el in extra_lines:
            lines.append(el)
        lines.append(url)

    all_content = "\n".join(lines) + "\n"
    write_if_changed("all.m3u", all_content)
    write_if_changed("all.m3u8", all_content)
    print("Saved merged all.m3u and all.m3u8 (Combined Live + VOD, sorted by tvg-chno)", flush=True)

# Update provider section in List/SHOWS_LIST.md with series shows and episodes.
def update_catalog_shows(provider_key, provider_title, folder_prefix, shows_dict):
    os.makedirs("List", exist_ok=True)
    list_path = "List/SHOWS_LIST.md"
    existing_content = ""
    if os.path.exists(list_path):
        with open(list_path, "r", encoding="utf-8") as f:
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
        mytv_wrapped = f"# VOD Series Catalog - Full Show List with Episodes\n\n<!-- SECTION:MYTV:START -->\n{existing_content.strip()}\n<!-- SECTION:MYTV:END -->\n\n{new_section}\n"
        final_content = mytv_wrapped
    else:
        header = "# VOD Series Catalog - Full Show List with Episodes\n\n" if not existing_content.strip().startswith("# VOD Series Catalog") else ""
        final_content = (existing_content.rstrip() + "\n\n" + new_section + "\n") if existing_content else (header + new_section + "\n")

    write_if_changed(list_path, final_content)

# Update provider section in List/MOVIES_LIST.md with standalone movies and durations.
def update_catalog_movies(provider_key, provider_title, movies_list):
    os.makedirs("List", exist_ok=True)
    list_path = "List/MOVIES_LIST.md"
    existing_content = ""
    if os.path.exists(list_path):
        with open(list_path, "r", encoding="utf-8") as f:
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
        mytv_wrapped = f"# VOD Standalone Movies List\n\n<!-- SECTION:MYTV:START -->\n{existing_content.strip()}\n<!-- SECTION:MYTV:END -->\n\n{new_section}\n"
        final_content = mytv_wrapped
    else:
        header = "# VOD Standalone Movies List\n\n" if not existing_content.strip().startswith("# VOD Standalone Movies List") else ""
        final_content = (existing_content.rstrip() + "\n\n" + new_section + "\n") if existing_content else (header + new_section + "\n")

    write_if_changed(list_path, final_content)

# Generate or update List/LIVE_LIST.md catalog documentation with all live TV and radio channels.
def update_catalog_live(live_entries):
    os.makedirs("List", exist_ok=True)
    list_path = "List/LIVE_LIST.md"
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

    write_if_changed(list_path, "\n".join(lines) + "\n")
    print(f"Generated Live Channel Catalog at {list_path} ({len(live_entries)} channels)", flush=True)

