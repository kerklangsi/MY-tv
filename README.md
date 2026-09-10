# 🇲🇾 Malaysian Unified IPTV & EPG Provider

[![Auto Update IPTV](https://github.com/kerklangsi/MY-tv/actions/workflows/update_iptv.yml/badge.svg)](https://github.com/kerklangsi/MY-tv/actions/workflows/update_iptv.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-IPTV%20%7C%20OTT-brightgreen)](#-compatible-iptv-players)
[![GitHub Stars](https://img.shields.io/github/stars/kerklangsi/MY-tv?style=social)](https://github.com/kerklangsi/MY-tv/stargazers)

Automated IPTV provider generator for **MYTV Mana-Mana** ([mana2.my](https://mana2.my/)), **Tonton** ([watch.tonton.com.my](https://watch.tonton.com.my/)), and **Unifi TV** ([unifi.com.my](https://unifi.com.my/tv)). This project automatically fetches live channel streams (`.m3u8`), multi-resolution HLS master manifests (1080p, 720p, 540p, 360p), VOD Shows & Movies, and Electronic Program Guide (EPG) schedules in XMLTV format (`.xml` & `.xml.gz`).

---

## 📊 Provider Overview

| Provider | Live Channels | VOD Catalog | EPG Schedule | Status |
| :--- | :---: | :---: | :---: | :---: |
| 🇲🇾 **MYTV Mana-Mana** | 46 Channels | 2,490+ Items | ✅ XMLTV Guide | 🟢 Active |
| 🇲🇾 **Tonton** | 9 Channels | Available | ✅ XMLTV Guide | 🟢 Active |
| 🇲🇾 **Unifi TV** | Live Channels | Available | ✅ XMLTV Guide | 🟢 Active |

---

## 🚀 Public Playlist & EPG Links

Use these direct raw GitHub URLs in your IPTV client app (e.g., TiviMate, OTT Navigator, IPTV Smarters, VLC, Televizo):

### 📺 Live TV & Radio Playlist (MYTV + Tonton + Unifi)
```text
https://raw.githubusercontent.com/kerklangsi/MY-tv/refs/heads/main/playlist.m3u
```

### 🎬 VOD Shows & Movies Playlist
```text
https://raw.githubusercontent.com/kerklangsi/MY-tv/refs/heads/main/vod.m3u
```

### 📅 Electronic Program Guide (EPG)
```text
https://raw.githubusercontent.com/kerklangsi/MY-tv/refs/heads/main/epg.xml.gz
```
*(Uncompressed XML format: `https://raw.githubusercontent.com/kerklangsi/MY-tv/refs/heads/main/epg.xml`)*

---

## ✨ Features

- **Unified Master Playlist**: Merges MYTV Live/Radio channels, Tonton Live channels, and Unifi TV channels into a single `playlist.m3u` / `playlist.m3u8`.
- **Structured VOD Organization**: Categorizes series episodes into show subfolders (e.g., `streams/vod_mytv/wedding-stone/`) and standalone movies into `movie/` subfolders.
- **Smart Change Detection**: Skips rewriting unchanged `.m3u8` files (`write_if_changed`), eliminating unnecessary git commit diffs.
- **Multi-Resolution Streams**: HLS stream files support full resolution selection (**1080p, 720p, 540p, 360p**) with absolute CDN URLs.
- **Clean & Ad-Free**: Filters out SCTE-35 ad markers, interstitial tags, Google DAI tags, and DoubleClick VAST/VMAP references.
- **Unified EPG Schedule**: Generates multi-day EPG program guide in standard XMLTV format covering all channels.
- **Automated Updates**: Powered by GitHub Actions to auto-update playlists and EPG on schedule.

---

## 📱 Compatible IPTV Players

| Player | OS / Platform | Status |
| :--- | :--- | :---: |
| 📺 **TiviMate** | Android TV / Fire TV | ✅ Supported |
| 📱 **OTT Navigator** | Android Phone / TV | ✅ Supported |
| 💻 **VLC Media Player** | Windows / macOS / Linux | ✅ Supported |
| 📱 **Televizo** | Android | ✅ Supported |
| 📱 **IPTV Smarters Pro** | Android / iOS / Smart TV | ✅ Supported |
| 🍿 **Kodi** (IPTV Simple Client) | Multi-Platform | ✅ Supported |

---

## 🛠️ How to Deploy & Enable Auto-Updates

1. Push this repository to your GitHub account:
   ```bash
   git remote set-url origin https://github.com/kerklangsi/MY-tv.git
   git push -u origin main
   ```
2. Enable GitHub Actions permissions:
   - Go to your repository **Settings** > **Actions** > **General**.
   - Under **Workflow permissions**, choose **Read and write permissions**.
   - Click **Save**.
3. The GitHub Actions workflow will automatically update all stream URLs, VOD playlists, and EPG schedules every 6 hours!

---

## 🤝 Contribution & Support

Contributions, issue reports, and feature requests are welcome!

- 🐛 **Report Issues**: Found a broken channel stream or incorrect EPG schedule? Feel free to open an [Issue](https://github.com/kerklangsi/MY-tv/issues).
- 🔀 **Pull Requests**: Want to add a new provider or improve generator scripts? PRs are always appreciated!
- ⭐️ **Star the Repo**: If you find this project useful, please consider giving it a star to show your support.

---

## ⚖️ Legal & License

- **Disclaimer**: This repository does not host or re-transmit copyrighted stream content. All stream URLs and metadata belong to their respective copyright owners (**MYTV Mana-Mana**, **Tonton**, **Unifi TV**).
- **License**: Distributed under the [MIT License](LICENSE).
