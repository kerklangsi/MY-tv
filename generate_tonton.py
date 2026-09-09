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
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/kerklangsi/MY-tv/main"

DEFAULT_DEVICE_ID = "web-v3-0d63fbaa5090547e80c50e9ae5935bfb-6d5145cbec6729682bee9b52f23ef4a9-cmtu0gw320001dt3qqdhki7iz"
DEFAULT_TOKEN = "e9703d2b5d5afc94230d72a108896062db0bc5e60e62253de53b75a471646cc01a2241395b6f96ca1dd1fae50e623bfb069a074e16cf8e51c4a60cc3afb7c92725952805eb226bcaef76bcfe5234eaa0a12f1c5a616e6b6e8ad686b346cb77f2a070e4a43fd1268e0c01701e8d562e6251ae07ab75f6930eb81fc2e04ffc3b7d77dde557ddd9be0162d826cf38fbdfba78db1cd65c1d45a0cc578fc8f08fb2c8fc3119bb8636b23c2edfdf141413175bae54ffe4964ef2158d8d25768822572fceea529c9bdbd1afd61dd9afb17c20fc17d04bb2772944d8caaed600b60a13571127f824c9e3364ab649d21fb20d10382cfc4cb7b9c5482db3d3cf2eed63924b84aec094fe5c774260061569d9d19aa90a6c3cb541cc0ce10fdc596c8917ff2d29bf3db232a2bbd4963adcc9e786f5b46ca41995c1bd52be24e7e0613eedea304e02d977757c213622d53342b53c61e9efc6419fbcedc3700633efaf7b2aeac6f4f83e8b50567fa3a95f782fc8cccd71fabd8dbd9a1236460b7f38a2d5a44bf92907971acb3f3f6726594fb969410d9eccf352aac739937da79ef16b5196896391a78f9d9aa2720813276885a6d40e6e11eb64849d0be42babd2aeb3a78007709c8aa859a8dd310da6cc237a71ef1888ed5f3b3b3dc68a767b7ab60bb2845ae60d522727e62e49b20b69b6de3f0fab9468ce3e3acd9ed4834ef519fa5dd04091ad8a9799deb209febe81a99b56de80bfad735e9b7bf80323db6a6faf27d8fdca558ce1d55199c54ec504abeaa2362795390fdca0ed80b6e85584e0edc3a456338192c8f268b5694de56cc3727ce7d4a66a05dacbd073b36c44c2a6622af94b317845ffe13014fe451ded35b8366b5766"

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
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 'Referer': 'https://watch.tonton.com.my/'})
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode('utf-8'), resp.geturl()
    return "", url

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
    in_ad_block = False

    for line in m3u8_text.splitlines():
        line_str = line.strip()
        
        # Filter ad tags / interstitial tags / CUE-OUT / CUE-IN / DAI / Ad URLs
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
                if "?" not in line_str and query_str:
                    line_str = base_dir + line_str + query_str
                else:
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

    tonton_m3u_entries = []
    epg_channels = []
    processed_slugs = set()
    tonton_token = os.getenv("TONTON_TOKEN", DEFAULT_TOKEN)
    dev_id = DEFAULT_DEVICE_ID

    for ch in live_channels:
        c_id = ch.get('id')
        c_code = ch.get('channelCode', '')
        c_name = ch.get('title', 'Unknown')
        c_num = ch.get('channelId', 0)
        c_slug = slugify(c_name) or c_code.lower() or c_id
        
        large_img = ch.get('largeImage', '')
        c_logo = f"{BASE_API}/imageHelper.php?id={large_img}&w=500&appID=TONTON" if large_img else ""
        group_title = "Tonton Live"

        config_url = f"{BASE_API}/api/playback.class.api.php/GOgetLiveConfig/378/1/{c_id}?format=json&appID=TONTON&rate=WIFIHIGH&plt=web&manufacturer=chrome&serviceID=default&model=Mozilla/5.0&firmwareVersion=10&appVersion=6.1.7&deviceOS=PCBROWSER&limitAdTracking=0&pageId=live-tv&deviceId={dev_id}&loginToken={tonton_token}"
        config_res = http_get(config_url)
        playback_data = config_res.get('playback', {}) or config_res
        
        master_url = ""
        if isinstance(playback_data, dict):
            media = playback_data.get('media', {})
            streams = media.get('streams', []) if isinstance(media, dict) else []
            if streams and isinstance(streams, list) and len(streams) > 0:
                master_url = streams[0].get('url', '')
            if not master_url:
                master_url = playback_data.get('url') or playback_data.get('playbackUrl') or ""

        signed_stream_url = master_url

        ch_file_path = f"streams/tonton/{c_slug}.m3u8"
        if signed_stream_url:
            master_manifest, final_url = fetch_raw_text(signed_stream_url)
            abs_playlist_content = make_m3u8_absolute(master_manifest, final_url)
            with open(ch_file_path, "w", encoding="utf-8") as f:
                f.write(abs_playlist_content)
        else:
            with open(ch_file_path, "w", encoding="utf-8") as f:
                f.write(f"#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-STREAM-INF:BANDWIDTH=4000000\n{config_url}\n")
                
        clean_m3u_url = f"{GITHUB_RAW_BASE}/streams/tonton/{c_slug}.m3u8"
        extinf = f'#EXTINF:-1 tvg-id="{c_slug}" tvg-name="{c_name}" tvg-logo="{c_logo}" tvg-chno="{c_num}" group-title="{group_title}",{c_name}'
        tonton_m3u_entries.append((extinf, clean_m3u_url))
        print(f"Added Tonton channel {c_num}: {c_name} ({c_code}) -> {clean_m3u_url}")

        if c_slug not in processed_slugs:
            processed_slugs.add(c_slug)
            epg_channels.append({'id': c_slug, 'name': c_name, 'logo': c_logo, 'code': c_code})

    return tonton_m3u_entries, epg_channels

def fetch_tonton_epg_programmes(epg_channels):
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
    return epg_programmes

def main():
    device_id = str(uuid.uuid4())
    tonton_m3u_entries, epg_channels = process_tonton_live_channels(device_id)
    epg_programmes = fetch_tonton_epg_programmes(epg_channels)

if __name__ == '__main__':
    main()

