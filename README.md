# MY-tv - Malaysian Unified IPTV & EPG Provider

Automated IPTV provider generator for **MYTV Mana-Mana** ([mana2.my](https://mana2.my/)) and **Tonton** ([watch.tonton.com.my](https://watch.tonton.com.my/)). This project automatically fetches live channel streams (`.m3u8`), multi-resolution HLS master manifests (1080p, 720p, 540p, 360p), VOD Shows & Movies, and Electronic Program Guide (EPG) schedules in XMLTV format (`.xml` & `.xml.gz`).

---

## 🚀 Public Playlist & EPG Links

Use these direct raw GitHub URLs in your IPTV client app (e.g., TiviMate, OTT Navigator, IPTV Smarters, VLC, Televizo):

### 📺 Live TV & Radio Playlist (MYTV + Tonton)
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

- **Unified Master Playlist**: Merges 46 MYTV Live/Radio channels and 9 Tonton Live channels into a single `playlist.m3u8`.
- **Multi-Resolution Streams**: HLS stream files support full resolution selection (**1080p, 720p, 540p, 360p**) with absolute CDN URLs.
- **Clean & Ad-Free**: Filters out SCTE-35 ad markers, interstitial tags, Google DAI tags, and DoubleClick VAST/VMAP references.
- **Unified EPG Schedule**: Generates 7-day EPG program guide in standard XMLTV format covering all 55 channels.
- **Automated Updates**: Powered by GitHub Actions to auto-update playlists and EPG every 6 hours.

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
