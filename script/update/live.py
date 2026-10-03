import uuid
import os
import sys
import gzip
import xml.etree.ElementTree as ET
from xml.dom import minidom

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from paths import EPG_XML, EPG_GZ, PLAYLIST, PLAYLIST8

from live import mytv, tonton, unifi
from utils import save_changed, merge_playlists, update_live, extract_chno, GITHUB_URL

# Orchestrate live channel processing, playlist generation, and EPG schedule merging
def main():
    device_id = str(uuid.uuid4())

    # 1. Process Live TV & Radio Channels (MYTV, Tonton & Unifi)
    print("\n--- Processing Live TV & Radio Channels ---", flush=True)
    mytv_m3u_entries, mytv_epg_channels = mytv.process_live(device_id)
    tonton_m3u_entries, tonton_epg_channels = tonton.process_live(device_id)
    unifi_m3u_entries, unifi_epg_channels = unifi.process_live(device_id)

    # 2. Build Merged Master Playlist (playlist.m3u & playlist.m3u8) sorted by tvg-chno
    all_live_entries = mytv_m3u_entries + tonton_m3u_entries + unifi_m3u_entries
    all_live_entries.sort(key=lambda item: (extract_chno(item[0]), item[0]))

    # Generate/Update List/LIVE_LIST.md catalog
    update_live(all_live_entries)

    m3u_lines = [f'#EXTM3U x-tvg-url="{GITHUB_URL}/epg.xml.gz"']

    for extinf, extra_lines, url in all_live_entries:
        if url:
            m3u_lines.append(extinf)
            for el in extra_lines:
                m3u_lines.append(el)
            m3u_lines.append(url)

    playlist_content = "\n".join(m3u_lines) + "\n"
    save_changed(PLAYLIST, playlist_content)
    save_changed(PLAYLIST8, playlist_content)
    print("Saved merged playlist.m3u and playlist.m3u8", flush=True)

    # 3. Process & Merge EPG Schedules (MYTV, Tonton & Unifi)
    mytv_programmes = mytv.fetch_epg()
    tonton_programmes = tonton.fetch_epg(tonton_epg_channels)
    unifi_programmes = unifi.fetch_epg(unifi_epg_channels)

    all_epg_channels = mytv_epg_channels + tonton_epg_channels + unifi_epg_channels
    all_epg_programmes = mytv_programmes + tonton_programmes + unifi_programmes

    print(f"\n--- Generating Merged EPG XML ({len(all_epg_channels)} channels, {len(all_epg_programmes)} programmes) ---", flush=True)

    tv_elem = ET.Element("tv", {"generator-info-name": "MY-tv IPTV Generator"})

    for ch_info in all_epg_channels:
        ch_elem = ET.SubElement(tv_elem, "channel", {"id": ch_info["id"]})
        name_elem = ET.SubElement(ch_elem, "display-name")
        name_elem.text = ch_info["name"]
        if ch_info.get("logo"):
            ET.SubElement(ch_elem, "icon", {"src": ch_info["logo"]})

    for prog_info in all_epg_programmes:
        prog_elem = ET.SubElement(tv_elem, "programme", {
            "start": prog_info["start"],
            "stop": prog_info["stop"],
            "channel": prog_info["channel"],
        })
        title_elem = ET.SubElement(prog_elem, "title", {"lang": "en"})
        title_elem.text = prog_info["title"]

        if prog_info.get("desc"):
            desc_elem = ET.SubElement(prog_elem, "desc", {"lang": "en"})
            desc_elem.text = prog_info["desc"]

        if prog_info.get("genre"):
            cat_elem = ET.SubElement(prog_elem, "category", {"lang": "en"})
            cat_elem.text = prog_info["genre"]

    raw_xml_bytes = ET.tostring(tv_elem, encoding="utf-8")
    parsed_xml = minidom.parseString(raw_xml_bytes)
    pretty_xml = parsed_xml.toprettyxml(indent="  ", encoding="utf-8")

    save_changed(EPG_XML, pretty_xml, is_binary=True)
    print("Saved merged epg.xml", flush=True)

    compressed_gz = gzip.compress(pretty_xml)
    save_changed(EPG_GZ, compressed_gz, is_binary=True)
    print("Saved merged epg.xml.gz", flush=True)

    # 4. Generate Combined Master Playlist (all.m3u & all.m3u8)
    merge_playlists()

if __name__ == "__main__":
    main()
