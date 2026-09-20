import urllib.request
import json
import uuid
import os
import gzip
import xml.etree.ElementTree as ET
from xml.dom import minidom

import live_mytv
import live_tonton
import live_unifi

from utils import write_if_changed, update_combined_playlist

def main():
    device_id = str(uuid.uuid4())

    # 1. Process Live TV & Radio Channels (MYTV, Tonton & Unifi)
    print("\n--- Processing Live TV & Radio Channels ---", flush=True)
    mytv_m3u_entries, mytv_epg_channels = live_mytv.process_live_channels(device_id)
    tonton_m3u_entries, tonton_epg_channels = live_tonton.process_tonton_live_channels(device_id)
    unifi_m3u_entries, unifi_epg_channels = live_unifi.process_unifi_live_channels(device_id)

    # 2. Build Merged Master Playlist (playlist.m3u & playlist.m3u8)
    m3u_lines = ['#EXTM3U x-tvg-url="epg.xml.gz"']
    for extinf, url in mytv_m3u_entries + tonton_m3u_entries + unifi_m3u_entries:
        m3u_lines.append(extinf)
        m3u_lines.append(url)

    playlist_content = "\n".join(m3u_lines) + "\n"
    write_if_changed("playlist.m3u", playlist_content)
    write_if_changed("playlist.m3u8", playlist_content)
    print("Saved merged playlist.m3u and playlist.m3u8", flush=True)

    # 3. Process & Merge EPG Schedules (MYTV, Tonton & Unifi)
    mytv_programmes = live_mytv.fetch_epg_programmes()
    tonton_programmes = live_tonton.fetch_tonton_epg_programmes(tonton_epg_channels)
    unifi_programmes = live_unifi.fetch_unifi_epg_programmes(unifi_epg_channels)

    all_epg_channels = mytv_epg_channels + tonton_epg_channels + unifi_epg_channels
    all_epg_programmes = mytv_programmes + tonton_programmes + unifi_programmes

    print(f"\n--- Generating Merged EPG XML ({len(all_epg_channels)} channels, {len(all_epg_programmes)} programmes) ---", flush=True)

    tv_elem = ET.Element('tv', {'generator-info-name': 'MY-tv Merged IPTV Generator'})

    for ch_info in all_epg_channels:
        ch_elem = ET.SubElement(tv_elem, 'channel', {'id': ch_info['id']})
        name_elem = ET.SubElement(ch_elem, 'display-name')
        name_elem.text = ch_info['name']
        if ch_info.get('logo'):
            ET.SubElement(ch_elem, 'icon', {'src': ch_info['logo']})

    for prog_info in all_epg_programmes:
        prog_elem = ET.SubElement(tv_elem, 'programme', {
            'start': prog_info['start'],
            'stop': prog_info['stop'],
            'channel': prog_info['channel']
        })
        title_elem = ET.SubElement(prog_elem, 'title', {'lang': 'en'})
        title_elem.text = prog_info['title']
        
        if prog_info.get('desc'):
            desc_elem = ET.SubElement(prog_elem, 'desc', {'lang': 'en'})
            desc_elem.text = prog_info['desc']
            
        if prog_info.get('genre'):
            cat_elem = ET.SubElement(prog_elem, 'category', {'lang': 'en'})
            cat_elem.text = prog_info['genre']

    raw_xml_bytes = ET.tostring(tv_elem, encoding='utf-8')
    parsed_xml = minidom.parseString(raw_xml_bytes)
    pretty_xml = parsed_xml.toprettyxml(indent="  ", encoding="utf-8")

    write_if_changed("epg.xml", pretty_xml, is_binary=True)
    print("Saved merged epg.xml", flush=True)

    compressed_gz = gzip.compress(pretty_xml)
    write_if_changed("epg.xml.gz", compressed_gz, is_binary=True)
    print("Saved merged epg.xml.gz", flush=True)

    # 4. Generate Combined Master Playlist (all.m3u & all.m3u8)
    update_combined_playlist()

if __name__ == '__main__':
    main()

