import urllib.request
import json
import uuid
import base64
import os
import stat
import gzip
import re
from xml.dom import minidom
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from utils import http_get, http_post, fetch_raw_text, slugify, make_m3u8_absolute, write_if_changed, cleanup_stale_files

BASE_API = "https://co3y6iwoio.tenbytecdn.com/api/v1"
GITHUB_URL = "https://kerklangsi.github.io/MY-tv"

ME_KEY = "u6nCKz4ogW09a27lOzGcYkdJP9QJ6ABgw9GZuIBmWtMWswdz".encode('utf-8')[:32]

# Decrypt AES-GCM encrypted CDN signature payload.
def decrypt_cdn_payload(payload_b64):
    raw = base64.b64decode(payload_b64)
    iv = raw[:12]
    tag = raw[12:28]
    ciphertext = raw[28:]
    aesgcm = AESGCM(ME_KEY)
    decrypted_bytes = aesgcm.decrypt(iv, ciphertext + tag, None)
    return json.loads(decrypted_bytes.decode('utf-8'))

# Convert ISO timestamp string to XMLTV datetime format.
def iso_to_xmltv(iso_str):
    if not iso_str:
        return ""
    clean_str = iso_str.replace("Z", "").rsplit(".", 1)[0]
    dt_obj = datetime.strptime(clean_str, "%Y-%m-%dT%H:%M:%S")
    return dt_obj.strftime("%Y%m%d%H%M%S +0000")

MYTV_LCN_MAP = {
    "TV1": 101,
    "TV2": 102,
    "TV3": 103,
    "NTV7": 107,
    "8TV": 108,
    "TV9": 109,
    "TV OKEY": 110,
    "SUKAN+": 111,
    "SUKAN RTM": 111,
    "TV ALHIJRAH": 114,
    "BERNAMA": 121,
    "BERNAMA TV": 121,
    "TVS": 122,
    "BERITA RTM": 123,
    "SIARA TV": 200,
    "FREE MOVIES": 212,
    "THE INDONESIA CHANNEL": 214,
    "CNA": 215,
    "AL JAZEERA ENGLISH HD": 216,
    "EURONEWS": 217,
    "ARIRANG": 218,
    "TAIWANPLUS": 219,
    "NHK WORLD": 220,
    "DW": 221,
    "RT INTERNATIONAL": 222,
    "AL JAZEERA ARABIC HD": 223,
    "USIM TV": 224,
    "SELANGOR TV": 225,
    "TVIKIM": 226,
    "BORNEO TV": 227,
    "MYSPORTS": 228,
    "HOT FM": 201,
    "FLY FM": 202,
    "SURIA FM": 203,
    "RAKITA FM": 204,
    "MANIS FM": 205,
    "MOLEK FM": 206,
    "BEST FM": 207,
    "IKIMFM": 208,
    "IKIM FM": 208,
    "EIGHT FM": 210,
    "KOOL FM": 211,
    "NASIONAL FM": 701,
    "TRAXX FM": 702,
    "MINNAL FM": 703,
    "AI FM": 704,
    "RADIO KLASIK": 705,
    "ASYIK FM": 706,
    "SABAH FM": 707,
    "SABAHV FM": 708,
    "SARAWAK FM": 709,
    "WAI FM": 710,
    "BERNAMA RADIO": 711,
}

# Process MYTV live TV and radio channels, signing HLS streams and generating playlists.
def process_live_channels(device_id):
    print("--- Processing MYTV Live Channels & Radio ---")
    channels_res = http_get(f"{BASE_API}/public/channels")
    channels = channels_res.get('data', [])
    print(f"Total MYTV Live/Radio channels found: {len(channels)}")

    os.makedirs("streams/live_mytv", exist_ok=True)
    os.makedirs("streams/radio_mytv", exist_ok=True)

    m3u_entries = []
    epg_channels = []
    processed_slugs = set()
    active_files_set = set()

    for idx, ch in enumerate(channels, 1):
        c_id = ch.get('id')
        c_name = ch.get('name', 'Unknown')
        c_slug = ch.get('slug') or c_id

        c_name_upper = c_name.strip().upper()
        c_slug_upper = c_slug.strip().upper().replace('-', ' ')

        if c_name_upper in MYTV_LCN_MAP:
            c_num = MYTV_LCN_MAP[c_name_upper]
        elif c_slug_upper in MYTV_LCN_MAP:
            c_num = MYTV_LCN_MAP[c_slug_upper]
        else:
            c_num = ch.get('channelNumber', 0)

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
            folder_name = 'radio_mytv'
        else:
            group_title = 'MYTV Live'
            folder_name = 'live_mytv'

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
            active_files_set.add(os.path.normpath(ch_file_path))
            updated = write_if_changed(ch_file_path, ch_playlist_content)
            status_str = "Updated" if updated else "Kept (Unchanged)"
                
            clean_m3u_url = f"{GITHUB_URL}/streams/{folder_name}/{c_slug}.m3u8"

            extinf = f'#EXTINF:-1 tvg-id="{c_slug}" tvg-name="{c_name}" tvg-logo="{c_logo}" tvg-chno="{c_num}" group-title="{group_title}",{c_name}'
            m3u_entries.append((extinf, [], clean_m3u_url))
            print(f"[{idx}/{len(channels)}] [{status_str}] Added {group_title} {c_num}: {c_name} -> {clean_m3u_url}", flush=True)

        if c_slug not in processed_slugs:
            processed_slugs.add(c_slug)
            epg_channels.append({'id': c_slug, 'name': c_name, 'logo': c_logo})

    cleanup_stale_files("streams/live_mytv", active_files_set)
    cleanup_stale_files("streams/radio_mytv", active_files_set)

    return m3u_entries, epg_channels

# Fetch EPG schedule for MYTV channels.
def fetch_epg_programmes():
    print("\n--- Fetching MYTV EPG Schedule ---")
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

    print(f"Total MYTV EPG programmes collected: {len(epg_programmes)}")
    return epg_programmes
