import urllib.request
import json
import uuid
import os
import gzip
import xml.etree.ElementTree as ET
from xml.dom import minidom

import live_mytv
import vod_mytv
import live_tonton
import vod_tonton

def main():
    device_id = str(uuid.uuid4())

    # 1. Process Live TV & Radio Channels (MYTV & Tonton)
    mytv_m3u_entries, mytv_epg_channels = live_mytv.process_live_channels(device_id)
    tonton_m3u_entries, tonton_epg_channels = live_tonton.process_tonton_live_channels(device_id)

    # 2. Build Merged Master Playlist (playlist.m3u & playlist.m3u8)
    m3u_lines = ['#EXTM3U x-tvg-url="epg.xml.gz"']
    for extinf, url in mytv_m3u_entries + tonton_m3u_entries:
        m3u_lines.append(extinf)
        m3u_lines.append(url)

    playlist_content = "\n".join(m3u_lines) + "\n"
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(playlist_content)
    with open("playlist.m3u8", "w", encoding="utf-8") as f:
        f.write(playlist_content)
    print("\nSaved merged playlist.m3u and playlist.m3u8")

    # 3. Process VOD Shows & Movies (MYTV & Tonton)
    mytv_vod_entries = vod_mytv.process_vod_shows(device_id)
    tonton_vod_entries = vod_tonton.process_tonton_vod(device_id)

    # 4. Build Merged VOD Master Playlist (vod.m3u & vod.m3u8)
    vod_lines = ['#EXTM3U']
    for extinf, url in mytv_vod_entries + tonton_vod_entries:
        vod_lines.append(extinf)
        vod_lines.append(url)

    vod_content = "\n".join(vod_lines) + "\n"
    with open("vod.m3u", "w", encoding="utf-8") as f:
        f.write(vod_content)
    with open("vod.m3u8", "w", encoding="utf-8") as f:
        f.write(vod_content)
    print("Saved merged vod.m3u and vod.m3u8")

    # 5. Process & Merge EPG Schedules (MYTV & Tonton)
    mytv_programmes = live_mytv.fetch_epg_programmes()
    tonton_programmes = live_tonton.fetch_tonton_epg_programmes(tonton_epg_channels)

    all_epg_channels = mytv_epg_channels + tonton_epg_channels
    all_epg_programmes = mytv_programmes + tonton_programmes

    print(f"\n--- Generating Merged EPG XML ({len(all_epg_channels)} channels, {len(all_epg_programmes)} programmes) ---")

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

    with open("epg.xml", "wb") as f:
        f.write(pretty_xml)
    print("Saved merged epg.xml")

    with gzip.open("epg.xml.gz", "wb") as f:
        f.write(pretty_xml)
    print("Saved merged epg.xml.gz")

if __name__ == '__main__':
    main()
