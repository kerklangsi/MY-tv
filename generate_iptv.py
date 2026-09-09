import urllib.request
import json
import uuid
import os
import gzip
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta, timezone

BASE_API = "https://co3y6iwoio.tenbytecdn.com/api/v1"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Origin': 'https://mana2.my',
    'Referer': 'https://mana2.my/',
    'Content-Type': 'application/json'
}

def http_get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

def http_post(url, payload):
    req = urllib.request.Request(url, headers=HEADERS, data=json.dumps(payload).encode('utf-8'))
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

def iso_to_xmltv(iso_str):
    if not iso_str:
        return ""
    clean_str = iso_str.replace("Z", "").rsplit(".", 1)[0]
    dt_obj = datetime.strptime(clean_str, "%Y-%m-%dT%H:%M:%S")
    return dt_obj.strftime("%Y%m%d%H%M%S +0000")

def main():
    print("Fetching channel list from MYTV Mana-Mana...")
    channels_res = http_get(f"{BASE_API}/public/channels")
    channels = channels_res.get('data', [])
    print(f"Total channels found: {len(channels)}")

    m3u_lines = [
        '#EXTM3U x-tvg-url="epg.xml.gz"'
    ]

    epg_channels = []
    epg_programmes = []
    processed_slugs = set()

    for ch in channels:
        c_id = ch.get('id')
        c_num = ch.get('channelNumber', 0)
        c_name = ch.get('name', 'Unknown')
        c_slug = ch.get('slug') or c_id
        c_logo = ch.get('logoUrl') or ch.get('thumbnailUrl') or ''
        c_type = ch.get('channelType', 'video')
        group_title = 'MYTV Radio' if c_type == 'radio' else 'MYTV Live'

        # Fetch stream playback URL
        device_id = str(uuid.uuid4())
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
        stream_url = play_data.get('playbackUrl') or play_data.get('playbackUrls', {}).get('hls', '')

        if stream_url:
            extinf = f'#EXTINF:-1 tvg-id="{c_slug}" tvg-name="{c_name}" tvg-logo="{c_logo}" tvg-chno="{c_num}" group-title="{group_title}",{c_name}'
            m3u_lines.append(extinf)
            m3u_lines.append(stream_url)
            print(f"Added channel {c_num}: {c_name}")

        if c_slug not in processed_slugs:
            processed_slugs.add(c_slug)
            epg_channels.append({
                'id': c_slug,
                'name': c_name,
                'logo': c_logo
            })

    # Save M3U & M3U8 playlist files
    playlist_content = "\n".join(m3u_lines) + "\n"
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(playlist_content)
    with open("playlist.m3u8", "w", encoding="utf-8") as f:
        f.write(playlist_content)
    print("Saved playlist.m3u and playlist.m3u8")

    # Fetch EPG for past day, today, and next 5 days
    print("\nFetching EPG schedule...")
    today = datetime.now(timezone.utc)
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

    # Construct XMLTV document
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

if __name__ == '__main__':
    main()
