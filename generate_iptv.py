import urllib.request
import json
import uuid
import base64
import os
import gzip
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

BASE_API = "https://co3y6iwoio.tenbytecdn.com/api/v1"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/kerklangsi/MYtvmana2/main"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Origin': 'https://mana2.my',
    'Referer': 'https://mana2.my/',
    'Content-Type': 'application/json'
}

ME_KEY = "u6nCKz4ogW09a27lOzGcYkdJP9QJ6ABgw9GZuIBmWtMWswdz".encode('utf-8')[:32]

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

def decrypt_cdn_payload(payload_b64):
    raw = base64.b64decode(payload_b64)
    iv = raw[:12]
    tag = raw[12:28]
    ciphertext = raw[28:]
    aesgcm = AESGCM(ME_KEY)
    decrypted_bytes = aesgcm.decrypt(iv, ciphertext + tag, None)
    return json.loads(decrypted_bytes.decode('utf-8'))

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
    lines = []
    for line in m3u8_text.splitlines():
        line_str = line.strip()
        if line_str and not line_str.startswith("#"):
            if not line_str.startswith("http://") and not line_str.startswith("https://"):
                line_str = base_dir + line_str
        lines.append(line_str)
    return "\n".join(lines) + "\n"

def iso_to_xmltv(iso_str):
    if not iso_str:
        return ""
    clean_str = iso_str.replace("Z", "").rsplit(".", 1)[0]
    dt_obj = datetime.strptime(clean_str, "%Y-%m-%dT%H:%M:%S")
    return dt_obj.strftime("%Y%m%d%H%M%S +0000")

def process_live_channels(device_id):
    print("--- Processing Live Channels ---")
    channels_res = http_get(f"{BASE_API}/public/channels")
    channels = channels_res.get('data', [])
    print(f"Total Live channels found: {len(channels)}")

    os.makedirs("streams/live", exist_ok=True)
    os.makedirs("streams/radio", exist_ok=True)

    # Clean up any loose .m3u8 files in streams/, streams/live/, and streams/radio/
    for subfolder in ["streams", "streams/live", "streams/radio"]:
        if os.path.exists(subfolder):
            for fname in os.listdir(subfolder):
                fpath = os.path.join(subfolder, fname)
                if os.path.isfile(fpath) and fname.endswith(".m3u8"):
                    os.remove(fpath)

    m3u_lines = ['#EXTM3U x-tvg-url="epg.xml.gz"']
    epg_channels = []
    processed_slugs = set()

    for ch in channels:
        c_id = ch.get('id')
        c_num = ch.get('channelNumber', 0)
        c_name = ch.get('name', 'Unknown')
        c_slug = ch.get('slug') or c_id
        c_logo = ch.get('logoUrl') or ch.get('thumbnailUrl') or ''
        c_type = ch.get('channelType', 'video')
        
        c_slug_lower = c_slug.lower()
        c_name_lower = c_name.lower()
        is_radio = (
            c_type == 'radio' or 
            'fm' in c_slug_lower.split('-') or 
            'radio' in c_slug_lower or 
            'fm' in c_name_lower.split() or 
            'radio' in c_name_lower
        )
        
        if is_radio:
            group_title = 'MYTV Radio'
            folder_name = 'radio'
        else:
            group_title = 'MYTV Live'
            folder_name = 'live'

        play_payload = {
            "channelId": c_id,
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
        
        play_res = http_post(f"{BASE_API}/public/streaming/channel-play", play_payload)
        play_data = play_res.get('data', {})
        master_url = play_data.get('playbackUrl') or play_data.get('playbackUrls', {}).get('hls', '')

        signed_stream_url = ""

        if master_url:
            if c_type == 'radio':
                signed_stream_url = master_url
                ch_playlist_content = f"#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-STREAM-INF:BANDWIDTH=4000000\n{signed_stream_url}\n"
            else:
                m_content = fetch_raw_text(master_url)
                parsed = urlparse(master_url)
                cdn_host = f"{parsed.scheme}://{parsed.netloc}"
                path_dir = parsed.path.rsplit('/', 1)[0]
                
                new_lines = []
                has_variants = False
                for line in m_content.splitlines():
                    line_str = line.strip()
                    if line_str and not line_str.startswith("#"):
                        has_variants = True
                        sub_rel = line_str.split('?')[0]
                        full_sub_path = sub_rel if sub_rel.startswith("/") else f"{path_dir}/{sub_rel}"
                        
                        sign_payload = {"channelId": c_id, "path": full_sub_path}
                        sign_res = http_post(f"{BASE_API}/public/streaming/sign", sign_payload)
                        if sign_res and 'data' in sign_res and 'payload' in sign_res['data']:
                            dec = decrypt_cdn_payload(sign_res['data']['payload'])
                            signed_var_url = f"{cdn_host}{full_sub_path}?md5={dec['md5']}&expires={dec['expires']}"
                            new_lines.append(signed_var_url)
                        else:
                            new_lines.append(f"{cdn_host}{full_sub_path}")
                    else:
                        new_lines.append(line)
                
                if has_variants:
                    ch_playlist_content = "\n".join(new_lines) + "\n"
                    signed_stream_url = master_url
                else:
                    signed_stream_url = master_url
                    ch_playlist_content = make_m3u8_absolute(m_content, master_url)

        if signed_stream_url:
            ch_file_path = f"streams/{folder_name}/{c_slug}.m3u8"
            with open(ch_file_path, "w", encoding="utf-8") as f:
                f.write(ch_playlist_content)
                
            clean_m3u_url = f"{GITHUB_RAW_BASE}/streams/{folder_name}/{c_slug}.m3u8"
            extinf = f'#EXTINF:-1 tvg-id="{c_slug}" tvg-name="{c_name}" tvg-logo="{c_logo}" tvg-chno="{c_num}" group-title="{group_title}",{c_name}'
            m3u_lines.append(extinf)
            m3u_lines.append(clean_m3u_url)
            print(f"Added {group_title} {c_num}: {c_name} -> {clean_m3u_url}")

        if c_slug not in processed_slugs:
            processed_slugs.add(c_slug)
            epg_channels.append({'id': c_slug, 'name': c_name, 'logo': c_logo})

    playlist_content = "\n".join(m3u_lines) + "\n"
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(playlist_content)
    with open("playlist.m3u8", "w", encoding="utf-8") as f:
        f.write(playlist_content)
        
    print("Saved playlist.m3u and playlist.m3u8 (pointing to streams/live/*.m3u8 and streams/radio/*.m3u8)")
    return epg_channels
    return epg_channels

def process_vod_shows(device_id):
    print("\n--- Processing VOD Shows & Movies ---")
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

    print(f"Total VOD shows found: {len(shows)}")

    os.makedirs("streams/vod", exist_ok=True)
    # Clean up old m3u8 files in streams/vod/
    if os.path.exists("streams/vod"):
        for fname in os.listdir("streams/vod"):
            fpath = os.path.join("streams/vod", fname)
            if os.path.isfile(fpath) and fname.endswith(".m3u8"):
                os.remove(fpath)

    vod_lines = ['#EXTM3U']
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
            vod_file_path = f"streams/vod/{item_slug}.m3u8"
            with open(vod_file_path, "w", encoding="utf-8") as f:
                f.write(abs_playlist_content)
                
            clean_url = f"{GITHUB_RAW_BASE}/streams/vod/{item_slug}.m3u8"
            extinf = f'#EXTINF:-1 tvg-id="{item_slug}" tvg-name="{item_title}" tvg-logo="{item_poster}" group-title="{group_title}",{item_title}'
            vod_lines.append(extinf)
            vod_lines.append(clean_url)
            print(f"Added VOD: {item_title} -> {clean_url}")

    vod_content = "\n".join(vod_lines) + "\n"
    with open("vod.m3u", "w", encoding="utf-8") as f:
        f.write(vod_content)
    with open("vod.m3u8", "w", encoding="utf-8") as f:
        f.write(vod_content)
        
    print("Saved vod.m3u and vod.m3u8 (pointing to streams/vod/*.m3u8)")

def process_epg(epg_channels):
    print("\n--- Fetching EPG Schedule ---")
    today = datetime.now(timezone.utc)
    epg_programmes = []

    for day_offset in range(-1, 6):
        target_date = (today + timedelta(days=day_offset)).strftime("%Y-%m-%d")
        epg_url = f"{BASE_API}/public/epg/guide?date={target_date}"
        epg_res = http_get(epg_url)
        epg_data = epg_res.get('data', [])
        
        for ch_epg in epg_data:
            c_slug = ch_epg.get('slug') or ch_epg.get('channelId')
            programmes = ch_epg.get('programmes', [])
            
            for p in programmes:
                p_title = p.get('title', '')
                p_desc = p.get('description', '')
                p_genre = p.get('genre', '')
                p_start = iso_to_xmltv(p.get('startTime'))
                p_end = iso_to_xmltv(p.get('endTime'))
                
                if p_start and p_end and p_title:
                    epg_programmes.append({
                        'channel': c_slug,
                        'start': p_start,
                        'stop': p_end,
                        'title': p_title,
                        'desc': p_desc,
                        'genre': p_genre
                    })

    print(f"Total EPG programmes collected: {len(epg_programmes)}")

    tv_elem = ET.Element('tv', {'generator-info-name': 'MYtvmana2 IPTV Generator'})

    for ch_info in epg_channels:
        ch_elem = ET.SubElement(tv_elem, 'channel', {'id': ch_info['id']})
        name_elem = ET.SubElement(ch_elem, 'display-name')
        name_elem.text = ch_info['name']
        if ch_info['logo']:
            ET.SubElement(ch_elem, 'icon', {'src': ch_info['logo']})

    for prog_info in epg_programmes:
        prog_elem = ET.SubElement(tv_elem, 'programme', {
            'start': prog_info['start'],
            'stop': prog_info['stop'],
            'channel': prog_info['channel']
        })
        title_elem = ET.SubElement(prog_elem, 'title', {'lang': 'en'})
        title_elem.text = prog_info['title']
        
        if prog_info['desc']:
            desc_elem = ET.SubElement(prog_elem, 'desc', {'lang': 'en'})
            desc_elem.text = prog_info['desc']
            
        if prog_info['genre']:
            cat_elem = ET.SubElement(prog_elem, 'category', {'lang': 'en'})
            cat_elem.text = prog_info['genre']

    raw_xml_bytes = ET.tostring(tv_elem, encoding='utf-8')
    parsed_xml = minidom.parseString(raw_xml_bytes)
    pretty_xml = parsed_xml.toprettyxml(indent="  ", encoding="utf-8")

    with open("epg.xml", "wb") as f:
        f.write(pretty_xml)
    print("Saved epg.xml")

    with gzip.open("epg.xml.gz", "wb") as f:
        f.write(pretty_xml)
    print("Saved epg.xml.gz")

def main():
    device_id = str(uuid.uuid4())
    epg_channels = process_live_channels(device_id)
    process_vod_shows(device_id)
    process_epg(epg_channels)

if __name__ == '__main__':
    main()
