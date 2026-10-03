import urllib.request
import json
import uuid
import os
import sys
import re
from urllib.parse import urlparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from paths import VOD_MYTV

from utils import http_get, http_post, fetch_raw, slugify, clean_subtitle, save_changed, cleanup_files, update_shows, update_movies, GITHUB_URL, MYTV_API

PROMO_KEYWORDS = {"teaser", "trailer", "promo", "preview", "highlight", "highlights", "behind the scene", "behind the scenes", "bts", "sedutan"}

# Determine VOD series subfolder or movie category based on title
def get_subfolder(title, content_type):
    if not title:
        return "movie"

    ep_pattern = r"(?:(?:S|Season|Siri)\s*\d+\s*)?(?:Ep|Episod|Episode|Bahagian|Part)\s*\d+"
    s_slug = None

    m_start = re.match(r"^\s*" + ep_pattern + r"\s*[-:\s]+(.*)$", title, re.IGNORECASE)
    if m_start and m_start.group(1).strip():
        s_slug = slugify(m_start.group(1))

    if not s_slug:
        m_end = re.match(r"^(.*?)\s+[-:\s]*" + ep_pattern, title, re.IGNORECASE)
        if m_end and m_end.group(1).strip():
            s_slug = slugify(m_end.group(1))

    if not s_slug:
        m_num = re.match(r"^(.*?)\s+\d+$", title)
        if m_num and content_type == "episode" and m_num.group(1).strip():
            s_slug = slugify(m_num.group(1))

    if not s_slug:
        m_season = re.match(r"^(.*?)\s+[-:\s]*(?:S|Season|Siri)\s*\d+$", title, re.IGNORECASE)
        if m_season and m_season.group(1).strip():
            s_slug = slugify(m_season.group(1))

    if s_slug:
        s_slug = re.sub(r"-(?:s|season|siri)-?\d+$", "", s_slug, flags=re.IGNORECASE)
        if s_slug:
            return s_slug

    return "movie"

# Check if VOD title indicates promotional teaser or trailer
def is_promo(title):
    if not title:
        return False
    t_lower = title.lower()
    return any(re.search(r"\b" + re.escape(kw) + r"\b", t_lower) for kw in PROMO_KEYWORDS)

# Fetch and map all season episodes for a single series container
def map_series(s_id):
    try:
        res = http_get(f"{MYTV_API}/public/content/{s_id}")
        data = res.get("data", {})
        s_title = data.get("title", "")
        clean_slug = slugify(s_title)
        clean_slug = re.sub(r"-(?:s|season|siri)-?\d+$", "", clean_slug, flags=re.IGNORECASE)
        seasons = data.get("seasons", [])
        is_multi = len(seasons) > 1
        mapped = {}
        for season in seasons:
            s_num = season.get("seasonNumber")
            if is_multi and s_num:
                season_slug = f"{clean_slug}-s{s_num}"
                season_title = f"{s_title} S{s_num}"
            else:
                season_slug = clean_slug
                season_title = s_title

            for ep in season.get("episodes", []):
                c = ep.get("content") or {}
                c_id = c.get("id")
                if c_id:
                    mapped[c_id] = {
                        "slug": season_slug,
                        "title": season_title,
                        "episodeNumber": ep.get("episodeNumber"),
                    }
        return mapped
    except Exception:
        return {}

# Fetch HLS manifest for a single VOD item and write manifest
def fetch_vod(task):
    item, folder_path, item_slug, group_title, device_id, entry_title = task
    item_id = item["id"]
    item_poster = item.get("posterLandscapeUrl") or item.get("posterPortraitUrl") or item.get("bannerUrl") or ""
    master_file_path = f"{folder_path}/{item_slug}.m3u8"

    play_payload = {
        "contentId": item_id,
        "deviceId": device_id,
        "protocol": "hls",
        "context": {
            "deviceType": "web",
            "app": "mytv-web",
            "appVersion": "0.1.0",
            "os": "Windows",
            "network": "wifi",
        },
    }

    updated = False
    play_res = http_post(f"{MYTV_API}/public/streaming/play", play_payload)
    signed_stream_url = play_res.get("data", {}).get("playbackUrl", "")

    if signed_stream_url:
        master_manifest = fetch_raw(signed_stream_url)
        if master_manifest and master_manifest.strip():
            parsed_master = urlparse(signed_stream_url)
            fresh_query = f"?{parsed_master.query}" if parsed_master.query else ""
            path_dir = parsed_master.path.rsplit("/", 1)[0]
            base_cdn_dir = f"{parsed_master.scheme}://{parsed_master.netloc}{path_dir}/"

            absolute_master_lines = []
            for line in master_manifest.splitlines():
                line_str = line.strip()
                if line_str and not line_str.startswith("#"):
                    sub_filename = line_str.split("?")[0]
                    abs_sub_url = base_cdn_dir + sub_filename + fresh_query
                    absolute_master_lines.append(abs_sub_url)
                else:
                    absolute_master_lines.append(line)

            new_manifest_content = "\n".join(absolute_master_lines) + "\n"
            updated = save_changed(master_file_path, new_manifest_content)

    clean_url = f"{GITHUB_URL}/{folder_path}/{item_slug}.m3u8"
    extinf = f'#EXTINF:-1 tvg-id="{item_slug}" tvg-name="{entry_title}" tvg-logo="{item_poster}" group-title="{group_title}",{entry_title}'
    return extinf, [], clean_url, master_file_path, updated

# Process all MYTV VOD shows and movies using parallel execution
def process_vod(device_id):
    print("\n--- Processing MYTV VOD Shows & Movies ---")

    official_series_index = {}
    s_page = 1
    while True:
        s_res = http_get(f"{MYTV_API}/public/content?contentType=series&page={s_page}&limit=100")
        s_items = s_res.get("data", {}).get("data", [])
        if not s_items:
            break
        for s in s_items:
            s_id = s["id"]
            s_title = s.get("title", "")
            clean_slug = slugify(s_title)
            clean_slug = re.sub(r"-(?:s|season|siri)-?\d+$", "", clean_slug, flags=re.IGNORECASE)
            official_series_index[s_id] = {
                "raw_title": s_title,
                "clean_slug": clean_slug,
            }
        total_s = s_res.get("data", {}).get("total", 0)
        if len(official_series_index) >= total_s:
            break
        s_page += 1

    official_title_keywords = []
    for s_info in official_series_index.values():
        raw_t = s_info["raw_title"].strip()
        if len(raw_t) >= 4:
            official_title_keywords.append((raw_t.lower(), s_info["clean_slug"]))
    official_title_keywords.sort(key=lambda x: len(x[0]), reverse=True)

    items = []
    page = 1
    while True:
        res = http_get(f"{MYTV_API}/public/content?page={page}&limit=100")
        data = res.get("data", {}).get("data", [])
        if not data:
            break
        for item in data:
            if item.get("contentType") != "series" and not is_promo(item.get("title", "")):
                items.append(item)
        total = res.get("data", {}).get("total", 0)
        if page * 100 >= total or len(data) < 100:
            break
        page += 1

    print(f"Total non-promo MYTV VOD items to process: {len(items)}")

    series_slug_to_title = {s["clean_slug"]: s["raw_title"] for s in official_series_index.values()}
    detail_cache_map = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        for m in executor.map(map_series, official_series_index.keys()):
            detail_cache_map.update(m)
            for info in m.values():
                series_slug_to_title[info["slug"]] = info["title"]

    slug_counts = defaultdict(int)
    prelim_items = []

    for item in items:
        item_title = item.get("title", "")
        item_type = item.get("contentType", "video")
        subfolder = None

        if item["id"] in detail_cache_map:
            subfolder = detail_cache_map[item["id"]]["slug"]

        if not subfolder:
            t_lower = item_title.lower()
            for kw_raw, kw_slug in official_title_keywords:
                if kw_raw in t_lower:
                    subfolder = kw_slug
                    break

        if not subfolder:
            subfolder = get_subfolder(item_title, item_type)

        if not subfolder:
            subfolder = "movie"

        prelim_items.append((item, subfolder))
        slug_counts[subfolder] += 1

    items_by_subfolder = defaultdict(list)
    for item, subfolder in prelim_items:
        if subfolder != "movie" and slug_counts[subfolder] < 2:
            subfolder = "movie"

        if subfolder == "movie":
            dur_sec = item.get("durationSeconds") or 0
            if 0 < dur_sec < 1200:
                subfolder = "short-movies-and-clips"

        items_by_subfolder[subfolder].append(item)

    vod_entries = []
    used_vod_slugs = set()
    active_files_set = set()
    total_subfolders = len(items_by_subfolder)

    sorted_subfolders = sorted([sf for sf in items_by_subfolder.keys() if sf not in ["movie", "short-movies-and-clips"]])
    if "short-movies-and-clips" in items_by_subfolder:
        sorted_subfolders.append("short-movies-and-clips")

    if "movie" in items_by_subfolder:
        sorted_subfolders.append("movie")

    tasks_by_subfolder = defaultdict(list)
    for subfolder in sorted_subfolders:
        sub_items = items_by_subfolder[subfolder]
        folder_path = f"{VOD_MYTV}/{subfolder}"
        os.makedirs(folder_path, exist_ok=True)
        if subfolder == "short-movies-and-clips":
            group_title = "MYTV Short Movies"
        elif subfolder == "movie":
            group_title = "MYTV Movies"
        else:
            group_title = "MYTV Shows"

        display_series_title = series_slug_to_title.get(subfolder) or subfolder.replace("-", " ").title()

        for item in sub_items:
            item_id = item["id"]
            item_title = item.get("title", "Unknown Show")

            if subfolder in ["movie", "short-movies-and-clips"]:
                clean_t = re.sub(r"^\s*(?:(?:S|Season|Siri)\s*\d+\s*)?(?:Ep|Episod|Episode|Bahagian|Part)\s*\d+\s*[-:\s]*", "", item_title, flags=re.IGNORECASE)
                clean_t = re.sub(r"\s+[-:\s]*(?:(?:S|Season|Siri)\s*\d+\s*)?(?:Ep|Episod|Episode|Bahagian|Part)\s*\d+.*$", "", clean_t, flags=re.IGNORECASE)
                title_slug = slugify(clean_t) if clean_t.strip() else slugify(item_title)
                item_slug = title_slug if title_slug else (item.get("slug") or item_id)
                entry_title = item_title
                ep_label = item_title
            else:
                ep_num = None
                if item_id in detail_cache_map:
                    ep_num = detail_cache_map[item_id].get("episodeNumber")
                if not ep_num:
                    m_ep = re.search(r"(?:(?:S|Season|Siri)\s*\d+\s*)?(?:Ep|Episod|Episode|Bahagian|Part)\s*(\d+)", item_title, re.IGNORECASE)
                    if m_ep:
                        ep_num = int(m_ep.group(1))
                    else:
                        m_num = re.search(r"\b(\d+)\b", item_title)
                        if m_num:
                            ep_num = int(m_num.group(1))

                clean_ep = clean_subtitle(item_title, display_series_title)
                has_custom = bool(clean_ep)

                if ep_num:
                    item_slug = f"{subfolder}-ep-{ep_num}"
                    if has_custom:
                        entry_title = f"{display_series_title} - Episod {ep_num}: {clean_ep}"
                        ep_label = f"Episod {ep_num} - {display_series_title}: {clean_ep}"
                    else:
                        entry_title = f"{display_series_title} - Episod {ep_num}"
                        ep_label = f"Episod {ep_num} - {display_series_title}"
                else:
                    item_slug = slugify(clean_ep or item_title) or item_id
                    if has_custom:
                        entry_title = f"{display_series_title} - {clean_ep}"
                        ep_label = f"{display_series_title} - {clean_ep}"
                    else:
                        entry_title = f"{display_series_title} - {item_title}"
                        ep_label = f"{display_series_title} - {item_title}"

            if item_slug in used_vod_slugs:
                item_slug = f"{item_slug}-{item_id}"
            used_vod_slugs.add(item_slug)

            item["entry_title"] = entry_title
            item["ep_label"] = ep_label
            tasks_by_subfolder[subfolder].append((item, folder_path, item_slug, group_title, device_id, entry_title))

    all_tasks = []
    for subfolder in sorted_subfolders:
        all_tasks.extend(tasks_by_subfolder[subfolder])

    print(f"Fetching {len(all_tasks)} MYTV VOD items using 20 parallel threads...", flush=True)

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(fetch_vod, all_tasks))

    for (extinf, extra_lines, clean_url, master_file_path, _), (item, _, _, _, _, _) in zip(results, all_tasks):
        item["clean_url"] = clean_url
        active_files_set.add(os.path.normpath(master_file_path))
        vod_entries.append((extinf, extra_lines, clean_url))

    for idx, subfolder in enumerate(sorted_subfolders, 1):
        sub_items = items_by_subfolder[subfolder]
        folder_label = f"Category '{subfolder}'" if subfolder in ["movie", "short-movies-and-clips"] else f"Series '{subfolder}'"
        print(f"[{idx}/{total_subfolders}] Processed {folder_label} ({len(sub_items)})", flush=True)

        sorted_eps = sorted(sub_items, key=lambda x: [(0, int(c)) if c.isdigit() else (1, c) for c in re.split(r'(\d+)', x.get("ep_label", x.get("title", "")).lower())])
        for ep in sorted_eps:
            ep_t = ep.get("ep_label", ep.get("title", "Unknown"))
            ep_url = ep.get("clean_url", "")
            print(f"{ep_t} -> {ep_url}", flush=True)

    cleanup_files(VOD_MYTV, active_files_set)

    mytv_shows_dict = defaultdict(lambda: {"title": "", "episodes": []})
    mytv_movies_list = []

    for subfolder, sub_items in items_by_subfolder.items():
        if subfolder in ["movie", "short-movies-and-clips"]:
            for m in sub_items:
                m_title = m.get("title", "Unknown Movie")
                dur_sec = m.get("durationSeconds") or 0
                if subfolder == "movie" and dur_sec >= 1200:
                    mytv_movies_list.append({"title": m_title, "duration": dur_sec, "url": m.get("clean_url", "")})
        else:
            s_title = series_slug_to_title.get(subfolder) or subfolder.replace("-", " ").title()
            mytv_shows_dict[subfolder]["title"] = s_title
            for ep in sub_items:
                ep_t = ep.get("ep_label", ep.get("title", "Unknown Episode"))
                ep_url = ep.get("clean_url", "")
                ep_str = f"[{ep_t}]({ep_url})" if ep_url else ep_t
                mytv_shows_dict[subfolder]["episodes"].append(ep_str)

    update_shows("MYTV", "MYTV Shows", VOD_MYTV, mytv_shows_dict)
    update_movies("MYTV", "MYTV Feature Movies", mytv_movies_list)

    print(f"Total MYTV VOD items processed: {len(vod_entries)}")
    return vod_entries

if __name__ == "__main__":
    dev_id = str(uuid.uuid4())
    process_vod(dev_id)
