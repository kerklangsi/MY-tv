# MYtvmana2 - MYTV Mana-Mana IPTV & EPG Provider

Automated IPTV provider generator for MYTV Mana-Mana ([mana2.my](https://mana2.my/)). This project automatically fetches live channel stream links (`.m3u8`) and Electronic Program Guide (EPG) schedules in XMLTV format (`.xml` & `.xml.gz`).

---

## Public Playlist & EPG Links

Once published to your GitHub repository, use these direct raw GitHub URLs in your IPTV client app (e.g., TiviMate, OTT Navigator, IPTV Smarters, VLC, Tivimate, Televizo):

### 📺 M3U / M3U8 Playlist URL
```text
https://raw.githubusercontent.com/kerklangsi/MYtvmana2/main/playlist.m3u8
```

### 📅 Electronic Program Guide (EPG) URL
```text
https://raw.githubusercontent.com/kerklangsi/MYtvmana2/main/epg.xml.gz
```
*(Alternative uncompressed format: `https://raw.githubusercontent.com/kerklangsi/MYtvmana2/main/epg.xml`)*

---

## Included Features & Channels

- **46 Live Channels**: TV1, TV2, SIARA TV, BERNAMA, TVS, TV ALHIJRAH, BERITA RTM, TV OKEY, DW, CNA, Al JAZEERA, SELANGOR TV, USIM TV, etc., plus live radio stations.
- **Auto-Updating Stream Tokens**: Playback URLs with signed HLS tokens are refreshed via GitHub Actions.
- **XMLTV EPG Schedule**: Multi-day programme listings with title, description, start/end times in UTC, genre tags, and channel logos.

---

## How to Deploy to GitHub

1. Push this repository to your GitHub account:
   ```bash
   git init
   git add .
   git commit -m "Initial commit of MYTV Mana-Mana IPTV Provider"
   git branch -M main
   git remote add origin https://github.com/kerklangsi/MYtvmana2.git
   git push -u origin main
   ```
2. Enable GitHub Actions permissions:
   - Go to **Settings** > **Actions** > **General**.
   - Under **Workflow permissions**, choose **Read and write permissions**.
   - Click **Save**.
3. The workflow will automatically update the streams and EPG every 6 hours!

---

## Local Generation

To run the generator script manually on your machine:
```bash
python generate_iptv.py
```
This generates/refreshes:
- `playlist.m3u` & `playlist.m3u8`
- `epg.xml` & `epg.xml.gz`
