import urllib.request
import json
import uuid
import base64
import os
import gzip
import re
import time
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

BASE_API = "https://headend-api.tonton.com.my/v600"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/kerklangsi/MYtvmana2/main"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Origin': 'https://watch.tonton.com.my',
    'Referer': 'https://watch.tonton.com.my/',
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

def fetch_raw_text(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://watch.tonton.com.my/'})
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
    lines = []
    for line in m3u8_text.splitlines():
        line_str = line.strip()
        if line_str and not line_str.startswith("#"):
            if not line_str.startswith("http://") and not line_str.startswith("https://"):
                line_str = base_dir + line_str
        lines.append(line_str)
    return "\n".join(lines) + "\n"

def timestamp_to_xmltv(ts):
    if not ts:
        return ""
    dt_obj = datetime.fromtimestamp(int(ts), tz=timezone.utc)
    return dt_obj.strftime("%Y%m%d%H%M%S +0000")

def process_tonton_live_channels(device_id):
    print("--- Processing Tonton Live Channels ---")
    channels_url = f"{BASE_API}/api/categoryTree.class.api.php/GOgetLiveChannels/378?format=json&appID=TONTON&plt=web&serviceID=default&apiVersion=2"
    channels_res = http_get(channels_url)
    live_channels = channels_res.get('liveChannel', [])
    print(f"Total Tonton Live channels found: {len(live_channels)}")

    os.makedirs("streams/tonton", exist_ok=True)
    if os.path.exists("streams/tonton"):
        for fname in os.listdir("streams/tonton"):
            fpath = os.path.join("streams/tonton", fname)
            if os.path.isfile(fpath) and fname.endswith(".m3u8"):
                os.remove(fpath)

    m3u_lines = ['#EXTM3U x-tvg-url="tonton_epg.xml.gz"']
    epg_channels = []
    processed_slugs = set()
    tonton_token = os.getenv("TONTON_TOKEN", "")

    for ch in live_channels:
        c_id = ch.get('id')
        c_code = ch.get('channelCode', '')
        c_name = ch.get('title', 'Unknown')
        c_num = ch.get('channelId', 0)
        c_slug = slugify(c_name) or c_code.lower() or c_id
        
        large_img = ch.get('largeImage', '')
        c_logo = f"{BASE_API}/imageHelper.php?id={large_img}&w=500&appID=TONTON" if large_img else ""
        group_title = "Tonton Live"

        config_url = f"{BASE_API}/api/playback.class.api.php/GOgetLiveConfig/378/1/{c_id}?format=json&appID=TONTON&rate=WIFIHIGH&plt=web&serviceID=default&appVersion=6.1.7&deviceId={device_id}&loginToken={tonton_token}"
        config_res = http_get(config_url)
        playback_data = config_res.get('playback', {}) or config_res
        
        master_url = ""
        if isinstance(playback_data, dict):
            master_url = playback_data.get('url') or playback_data.get('playbackUrl') or ""

        signed_stream_url = master_url

        ch_file_path = f"streams/tonton/{c_slug}.m3u8"
        if signed_stream_url:
            master_manifest = fetch_raw_text(signed_stream_url)
            abs_playlist_content = make_m3u8_absolute(master_manifest, signed_stream_url)
            with open(ch_file_path, "w", encoding="utf-8") as f:
                f.write(abs_playlist_content)
        else:
            with open(ch_file_path, "w", encoding="utf-8") as f:
                f.write(f"#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-STREAM-INF:BANDWIDTH=4000000\n{config_url}\n")
                
        clean_m3u_url = f"{GITHUB_RAW_BASE}/streams/tonton/{c_slug}.m3u8"
        extinf = f'#EXTINF:-1 tvg-id="{c_slug}" tvg-name="{c_name}" tvg-logo="{c_logo}" tvg-chno="{c_num}" group-title="{group_title}",{c_name}'
        m3u_lines.append(extinf)
        m3u_lines.append(clean_m3u_url)
        print(f"Added Tonton channel {c_num}: {c_name} ({c_code}) -> {clean_m3u_url}")

        if c_slug not in processed_slugs:
            processed_slugs.add(c_slug)
            epg_channels.append({'id': c_slug, 'name': c_name, 'logo': c_logo, 'code': c_code})

    playlist_content = "\n".join(m3u_lines) + "\n"
    with open("tonton_playlist.m3u", "w", encoding="utf-8") as f:
        f.write(playlist_content)
    with open("tonton_playlist.m3u8", "w", encoding="utf-8") as f:
        f.write(playlist_content)
        
    print("Saved tonton_playlist.m3u and tonton_playlist.m3u8 (pointing to streams/tonton/*.m3u8)")
    return epg_channels

def process_tonton_epg(epg_channels):
    print("\n--- Fetching Tonton EPG Schedule ---")
    now_ts = int(time.time())
    start_ts = now_ts - 86400
    end_ts = now_ts + (5 * 86400)
    
    channel_codes = [ch['code'] for ch in epg_channels if ch.get('code')]
    channels_filter = ",".join(channel_codes)

    epg_url = f"{BASE_API}/api/epg.class.api.php/getChannelListings/378?filter_starttime={start_ts}&filter_endtime={end_ts}&filter_channels={channels_filter}&format=json&appID=TONTON&serviceId=default"
    epg_res = http_get(epg_url)
    
    epg_programmes = []
    listings = epg_res if isinstance(epg_res, list) else []

    for listing in listings:
        source_ch = listing.get('SourceChannel', {})
        ch_code = source_ch.get('ChannelTag') or source_ch.get('ChannelName')
        
        # Match channel slug
        ch_slug = ch_code.lower() if ch_code else ''
        for ch in epg_channels:
            if ch.get('code') == ch_code:
                ch_slug = ch['id']

        schedule = listing.get('ChannelSchedule', {})
        events = schedule.get('EventList', [])

        for evt in events:
            p_title = evt.get('EventTitle', '')
            p_desc = evt.get('ShortSynopsis', '') or evt.get('EpisodeTitle', '') or ''
            p_genre = evt.get('Genre', '')
            p_start = timestamp_to_xmltv(evt.get('StartTimeUTC') or evt.get('RawStartTimeUTC'))
            p_end = timestamp_to_xmltv(evt.get('EndTimeUTC') or evt.get('RawEndTimeUTC'))

            if p_start and p_end and p_title:
                epg_programmes.append({
                    'channel': ch_slug,
                    'start': p_start,
                    'stop': p_end,
                    'title': p_title,
                    'desc': p_desc,
                    'genre': p_genre
                })

    print(f"Total Tonton EPG programmes collected: {len(epg_programmes)}")

    tv_elem = ET.Element('tv', {'generator-info-name': 'Tonton IPTV Generator'})

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

    with open("tonton_epg.xml", "wb") as f:
        f.write(pretty_xml)
    print("Saved tonton_epg.xml")

    with gzip.open("tonton_epg.xml.gz", "wb") as f:
        f.write(pretty_xml)
    print("Saved tonton_epg.xml.gz")

def main():
    device_id = str(uuid.uuid4())
    epg_channels = process_tonton_live_channels(device_id)
    process_tonton_epg(epg_channels)

if __name__ == '__main__':
    main()
