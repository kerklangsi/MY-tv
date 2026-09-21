import urllib.request
import json
import uuid
import base64
import os
import stat
import gzip
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from utils import http_get, fetch_raw_text_and_url, slugify, make_m3u8_absolute, write_if_changed, cleanup_stale_files
from tonton_auth import get_tonton_token

BASE_API = "https://headend-api.tonton.com.my/v600"
GITHUB_URL = "https://kerklangsi.github.io/MY-tv"
USER_AGENT_STR = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML like Gecko) Chrome/120.0.0.0 Safari/537.36"

DEFAULT_DEVICE_ID = "web-v3-0d63fbaa5090547e80c50e9ae5935bfb-6d5145cbec6729682bee9b52f23ef4a9-cmtu0gw320001dt3qqdhki7iz"

TONTON_LCN_MAP = {
    "TV3": 103,
    "NTV7": 107,
    "8TV": 108,
    "TV9": 109,
    "DRAMA SANGAT": 116,
    "THRILL": 119,
    "FIFA+": 120,
    "MPL MALAYSIA": 121,
}

# Convert Unix timestamp to XMLTV datetime string format.
def timestamp_to_xmltv(ts):
    if not ts:
        return ""
    dt_obj = datetime.fromtimestamp(int(ts), tz=timezone.utc)
    return dt_obj.strftime("%Y%m%d%H%M%S +0000")

# Process Tonton live TV channels, generate m3u8 manifests and M3U entries with browser headers.
def process_tonton_live_channels(device_id):
    print("--- Processing Tonton Live Channels ---")
    channels_url = f"{BASE_API}/api/categoryTree.class.api.php/GOgetLiveChannels/378?format=json&appID=TONTON&plt=web&serviceID=default&apiVersion=2"
    channels_res = http_get(channels_url, headers={'User-Agent': USER_AGENT_STR})
    live_channels = channels_res.get('liveChannel', [])
    print(f"Total Tonton Live channels found: {len(live_channels)}")

    os.makedirs("streams/live_tonton", exist_ok=True)

    tonton_m3u_entries = []
    epg_channels = []
    processed_slugs = set()
    active_files_set = set()
    tonton_token = get_tonton_token()
    dev_id = DEFAULT_DEVICE_ID

    for idx, ch in enumerate(live_channels, 1):
        c_id = ch.get('id')
        c_code = ch.get('channelCode', '')
        c_name = ch.get('title', 'Unknown')
        c_name_upper = c_name.strip().upper()
        c_code_upper = c_code.strip().upper()

        if c_name_upper in TONTON_LCN_MAP:
            c_num = TONTON_LCN_MAP[c_name_upper]
        elif c_code_upper in TONTON_LCN_MAP:
            c_num = TONTON_LCN_MAP[c_code_upper]
        else:
            raw_num = int(ch.get('channelId', 0)) if str(ch.get('channelId', '0')).isdigit() else 0
            c_num = 100 + raw_num

        c_slug = slugify(c_name) or c_code.lower() or c_id
        
        large_img = ch.get('largeImage', '')
        c_logo = f"{BASE_API}/imageHelper.php?id={large_img}&w=500&appID=TONTON" if large_img else ""
        group_title = "Tonton Live"

        config_url = f"{BASE_API}/api/playback.class.api.php/GOgetLiveConfig/378/1/{c_id}?format=json&appID=TONTON&rate=WIFIHIGH&plt=web&manufacturer=chrome&serviceID=default&model=Mozilla/5.0&firmwareVersion=10&appVersion=6.1.7&deviceOS=PCBROWSER&limitAdTracking=0&pageId=live-tv&deviceId={dev_id}&loginToken={tonton_token}"
        config_res = http_get(config_url, headers={'User-Agent': USER_AGENT_STR})
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

        ch_file_path = f"streams/live_tonton/{c_slug}.m3u8"
        
        if signed_stream_url:
            active_files_set.add(os.path.normpath(ch_file_path))
            master_manifest, final_url = fetch_raw_text_and_url(signed_stream_url, headers={'User-Agent': USER_AGENT_STR})
            abs_playlist_content = make_m3u8_absolute(master_manifest, final_url)
            updated = write_if_changed(ch_file_path, abs_playlist_content)
            status_str = "Updated" if updated else "Kept (Unchanged)"
            clean_m3u_url = f"{GITHUB_URL}/streams/live_tonton/{c_slug}.m3u8"

            extinf = f'#EXTINF:-1 tvg-id="{c_slug}" tvg-name="{c_name}" tvg-logo="{c_logo}" tvg-chno="{c_num}" group-title="{group_title}" http-user-agent="{USER_AGENT_STR}",{c_name}'
            extra_lines = [f'#EXTVLCOPT:http-user-agent={USER_AGENT_STR}']
            tonton_m3u_entries.append((extinf, extra_lines, clean_m3u_url))
            print(f"[{idx}/{len(live_channels)}] [{status_str}] Added Tonton channel {c_num}: {c_name} ({c_code}) -> {clean_m3u_url}", flush=True)
        else:
            print(f"[{idx}/{len(live_channels)}] [Warning] Tonton channel {c_num}: {c_name} requires valid TONTON_TOKEN env variable.", flush=True)

        if c_slug not in processed_slugs:
            processed_slugs.add(c_slug)
            epg_channels.append({'id': c_slug, 'name': c_name, 'logo': c_logo, 'code': c_code})

    cleanup_stale_files("streams/live_tonton", active_files_set)

    return tonton_m3u_entries, epg_channels

# Fetch EPG programme schedule for Tonton live channels across full 7-day window.
def fetch_tonton_epg_programmes(epg_channels):
    print("\n--- Fetching Tonton EPG Schedule ---")
    now_ts = int(time.time())
    
    channel_codes = [ch['code'] for ch in epg_channels if ch.get('code')]
    channels_filter = ",".join(channel_codes)
    filter_fields = "Duration,EventTitle,EpisodeTitle,ParentalRating,ShortSynopsis,ParentalAdvice,Genre,MainGenre,SubGenre,StartTimeUTC,ProgramID,EndTimeUTC,RawStartTimeUTC,RawEndTimeUTC,YearOfProduction,Keywords,ReportingGenre,ReportingSubGenre,ClosedCaption,HighDefinition,SeriesNumber,EpisodeNumber"

    epg_programmes = []
    seen_programmes = set()

    for day_offset in range(-1, 6):
        start_ts = now_ts + (day_offset * 86400)
        end_ts = start_ts + 86400
        epg_url = f"{BASE_API}/api/epg.class.api.php/getChannelListings/378?filter_starttime={start_ts}&filter_endtime={end_ts}&filter_channels={channels_filter}&filter_fields={filter_fields}&format=json&appID=TONTON&serviceId=default"
        epg_res = http_get(epg_url, headers={'User-Agent': USER_AGENT_STR})
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
                p_ep_title = evt.get('EpisodeTitle', '')
                p_ep_num = evt.get('EpisodeNumber', '')
                p_synopsis = evt.get('ShortSynopsis', '')
                p_rating = evt.get('ParentalRating', '')

                # Build rich description string
                desc_parts = []
                if p_ep_num:
                    desc_parts.append(f"Episode {p_ep_num}")
                if p_ep_title and p_ep_title != p_title:
                    desc_parts.append(p_ep_title)
                if p_synopsis:
                    desc_parts.append(p_synopsis)
                if p_rating:
                    desc_parts.append(f"[{p_rating}]")

                p_desc = " - ".join(desc_parts)
                p_genre = evt.get('Genre') or evt.get('MainGenre') or ''
                p_start = timestamp_to_xmltv(evt.get('StartTimeUTC') or evt.get('RawStartTimeUTC'))
                p_end = timestamp_to_xmltv(evt.get('EndTimeUTC') or evt.get('RawEndTimeUTC'))

                prog_key = (ch_slug, p_start, p_end, p_title)
                if p_start and p_end and p_title and prog_key not in seen_programmes:
                    seen_programmes.add(prog_key)
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
