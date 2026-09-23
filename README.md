# 🇲🇾 Malaysian Unified IPTV & EPG Provider

[![Auto Update IPTV](https://github.com/kerklangsi/MY-tv/actions/workflows/update_iptv.yml/badge.svg)](https://github.com/kerklangsi/MY-tv/actions/workflows/update_iptv.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-IPTV%20%7C%20OTT-brightgreen)](#-compatible-iptv-players)
[![GitHub Stars](https://img.shields.io/github/stars/kerklangsi/MY-tv?style=social)](https://github.com/kerklangsi/MY-tv/stargazers)

Automated IPTV and VOD provider generator for **MYTV Mana-Mana** ([mana2.my](https://mana2.my/)), **Tonton** ([watch.tonton.com.my](https://watch.tonton.com.my/)), and **Unifi TV** ([unifi.com.my](https://unifi.com.my/tv)). This project automatically fetches live channel streams (`.m3u8`), multi-resolution HLS master manifests (1080p, 720p, 540p, 360p), complete VOD Shows & Movies catalogs, and Electronic Program Guide (EPG) schedules in standard XMLTV format (`.xml` & `.xml.gz`).

---

## 📊 Provider & Catalog Overview

| Provider | Live Channels | VOD Catalog | EPG Schedule | Status |
| :--- | :---: | :---: | :---: | :---: |
| 🇲🇾 **MYTV Mana-Mana** | 46 Channels | 145 Shows & 105 Movies | ✅ XMLTV Guide | 🟢 Active |
| 🇲🇾 **Tonton** | 8 Channels | Complete Shows & Movies | ✅ XMLTV Guide | 🟢 Active |
| 🇲🇾 **Unifi TV** | Live Channels | Available | ✅ XMLTV Guide | 🟢 Active |

---

## 📚 Content & Stream Catalogs

Explore our structured catalog directories in the [`List/`](List/) folder:

- 📡 **[Live Channels Directory](List/LIVE_LIST.md)** (`List/LIVE_LIST.md`): Complete table of all 53+ Live TV and Radio channels with channel numbers, logos, EPG IDs, and direct stream links.
- 📺 **[Series & Shows Directory](List/SHOWS_LIST.md)** (`List/SHOWS_LIST.md`): Full catalog of series shows from MYTV and Tonton with episode breakdowns and direct `.m3u8` playlist links.
- 🎬 **[Feature Movies Directory](List/MOVIES_LIST.md)** (`List/MOVIES_LIST.md`): Standalone feature movies with duration, resolution details, and playable `.m3u8` manifest links.

---

## 🚀 Public Playlist & EPG Links

Paste these short GitHub Pages URLs into your IPTV client app (e.g., TiviMate, OTT Navigator, IPTV Smarters, VLC, Televizo, Kodi):

### 🍿 Combined Playlist (Live TV + Radio + VOD)
```text
https://kerklangsi.github.io/MY-tv/all.m3u
```
*(Alternative: `https://kerklangsi.github.io/MY-tv/all.m3u8`)*

### 📺 Live TV & Radio Playlist (MYTV + Tonton + Unifi)
```text
https://kerklangsi.github.io/MY-tv/playlist.m3u
```
*(Alternative: `https://kerklangsi.github.io/MY-tv/playlist.m3u8`)*

### 🎬 VOD Shows & Movies Playlist
```text
https://kerklangsi.github.io/MY-tv/vod.m3u
```
*(Alternative: `https://kerklangsi.github.io/MY-tv/vod.m3u8`)*

### 📅 Electronic Program Guide (EPG)
```text
https://kerklangsi.github.io/MY-tv/epg.xml.gz
```
*(Uncompressed XML format: `https://kerklangsi.github.io/MY-tv/epg.xml`)*

---

## 🔑 GitHub Secrets Configuration

To enable automated token refreshes and authenticated Tonton streams in GitHub Actions, configure the following secrets in your repository:

> Navigate to **Settings** > **Secrets and variables** > **Actions** > **New repository secret**:

| Secret Name | Required | Description | Example / Notes |
|---|:---:|---|---|
| `EMAIL` | **Yes** | Tonton account login email | `your-email@domain.com` |
| `PASSWORD` | **Yes** | Tonton account login password | `your-secure-password` |
| `GH_TOKEN` | Optional | Personal Access Token with `repo` and `workflow` scopes | Used for committing updates or triggering external dispatches |
| `ME_KEY` | Optional | MYTV static AES-128 key fallback | Auto-fetched dynamically from API if omitted |

---

## ⚙️ GitHub Actions & Automated Workflows

The repository includes preconfigured GitHub Actions workflows located in `.github/workflows/`:

### 1. `update_iptv.yml` (IPTV & EPG Updater)
- **Manual Trigger**: Can be manually run anytime via **Actions** tab > **Run workflow** (`workflow_dispatch`).
- **Webhook Dispatch**: Can be triggered via external repository dispatch (e.g. from **cron-job.org**):
  ```bash
  curl -X POST https://api.github.com/repos/kerklangsi/MY-tv/dispatches \
    -H "Accept: application/vnd.github.v3+json" \
    -H "Authorization: token <YOUR_GH_TOKEN>" \
    -H "User-Agent: CronJobWebHook" \
    -d '{"event_type": "update-iptv"}'
  ```

### 2. `refresh_token.yml` (Headless SSO Token Refresh)
- **Schedule**: Automatically refreshes the Tonton SSO authentication token and device pairing using headless Playwright Chromium.
- **Manual Trigger**: Can be manually run from **Actions** tab > **Refresh Token** > **Run workflow**.
- **External Webhook (cron-job.org)**: Triggered via `repository_dispatch`:
  ```bash
  curl -X POST https://api.github.com/repos/kerklangsi/MY-tv/dispatches \
    -H "Accept: application/vnd.github.v3+json" \
    -H "Authorization: token <YOUR_GH_TOKEN>" \
    -H "User-Agent: CronJobWebHook" \
    -d '{"event_type": "refresh-token"}'
  ```

#### 🌐 Setting up on cron-job.org:
1. **URL**: `https://api.github.com/repos/kerklangsi/MY-tv/dispatches`
2. **Execution Schedule**: Every 12 hours (e.g. `0 */12 * * *`)
3. **Request Method**: `POST`
4. **HTTP Headers**:
   - `Accept`: `application/vnd.github.v3+json`
   - `Authorization`: `Bearer <YOUR_GITHUB_PAT>`
   - `User-Agent`: `CronJobWebHook`
5. **Request Body (JSON)**:
   ```json
   {
     "event_type": "refresh-token"
   }
   ```

---

## 💻 Local Execution & Testing

### Prerequisites
- Python 3.10+
- Google Chrome or Chromium installed (for Playwright authentication)

```bash
# 1. Clone repository
git clone https://github.com/kerklangsi/MY-tv.git
cd MY-tv

# 2. Install Python dependencies
pip install -r requirements.txt
playwright install chromium
```

### Running Scripts Locally
```bash
# Generate Live TV & Radio Playlists, EPG XML, and List/LIVE_LIST.md
python script/update_live.py

# Refresh MYTV VOD Catalog and List/SHOWS_LIST.md & List/MOVIES_LIST.md
python script/vod_mytv.py

# Refresh Tonton VOD Catalog and Playlists
python script/vod_tonton.py

# Authenticate or Force Refresh Tonton Token via SSO Popup
python script/auth.py --force
```

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

## 🤝 Contribution & Support

Contributions, issue reports, and feature requests are welcome!

- 🐛 **Report Issues**: Found a broken channel stream or incorrect EPG schedule? Feel free to open an [Issue](https://github.com/kerklangsi/MY-tv/issues).
- 🔀 **Pull Requests**: Want to add a new provider or improve generator scripts? PRs are always appreciated!
- ⭐️ **Star the Repo**: If you find this project useful, please consider giving it a star to show your support.

---

## ⚖️ Legal & License

This project is for educational and personal interoperability purposes only. All streams, channel logos, and trademarks belong to their respective content providers (MYTV Broadcasting Sdn Bhd, Media Prima Berhad, and Telekom Malaysia Berhad). This software is released under the [MIT License](LICENSE).


- **Disclaimer**: This repository does not host or re-transmit copyrighted stream content. All stream URLs and metadata belong to their respective copyright owners (**MYTV Mana-Mana**, **Tonton**, **Unifi TV**).
- **License**: Distributed under the [MIT License](LICENSE).
