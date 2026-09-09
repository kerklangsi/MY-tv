# MYtvmana2 - MYTV Mana-Mana IPTV & EPG Provider

Automated IPTV provider generator for MYTV Mana-Mana ([mana2.my](https://mana2.my/)). This project automatically fetches live channel stream links (`.m3u8`), VOD Shows & Movies, and Electronic Program Guide (EPG) schedules in XMLTV format (`.xml` & `.xml.gz`).

---

## Public Playlist & EPG Links

Once published to your GitHub repository, use these direct raw GitHub URLs in your IPTV client app (e.g., TiviMate, OTT Navigator, IPTV Smarters, VLC, Televizo):

### 📺 Live Channels Playlist (TV & Radio)
```text
https://raw.githubusercontent.com/kerklangsi/MYtvmana2/main/playlist.m3u8
```

### 🎬 VOD Shows & Movies Playlist
```text
https://raw.githubusercontent.com/kerklangsi/MYtvmana2/main/vod.m3u8
```

### 📅 Electronic Program Guide (EPG)
```text
https://raw.githubusercontent.com/kerklangsi/MYtvmana2/main/epg.xml.gz
```
*(Alternative uncompressed format: `https://raw.githubusercontent.com/kerklangsi/MYtvmana2/main/epg.xml`)*

---

## Directory Structure

```text
MYtvmana2/
├── streams/
│   ├── live/
│   │   ├── tv1.m3u8
│   │   ├── tv2.m3u8
│   │   └── ...
│   ├── radio/
│   │   ├── fly-fm.m3u8
│   │   ├── hot-fm.m3u8
│   │   └── ...
│   └── vod/
│       ├── trip-teaser.m3u8
│       └── ...
├── playlist.m3u
├── playlist.m3u8
├── vod.m3u
├── vod.m3u8
├── epg.xml
├── epg.xml.gz
├── generate_iptv.py
├── README.md
└── .github/workflows/update_iptv.yml
```

---

## How to Deploy to GitHub

1. Push this repository to your GitHub account:
   ```bash
   git init
   git add .
   git commit -m "Organize Live and VOD playlists into dedicated live/ and vod/ directories"
   git branch -M main
   git remote add origin https://github.com/kerklangsi/MYtvmana2.git
   git push -u origin main
   ```
2. Enable GitHub Actions permissions:
   - Go to **Settings** > **Actions** > **General**.
   - Under **Workflow permissions**, choose **Read and write permissions**.
   - Click **Save**.
3. The workflow will automatically update the live streams, VOD streams, and EPG every 6 hours!
