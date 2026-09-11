import urllib.request
import json
import os
import stat
import re
from urllib.parse import urlparse

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Content-Type': 'application/json'
}

class NoRaiseHTTPErrorProcessor(urllib.request.HTTPErrorProcessor):
    def http_response(self, request, response):
        return response
    https_response = http_response

opener = urllib.request.build_opener(NoRaiseHTTPErrorProcessor)

def http_get(url, headers=None):
    req_headers = DEFAULT_HEADERS.copy()
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    resp = opener.open(req)
    if 200 <= resp.status < 300:
        return json.loads(resp.read().decode('utf-8'))
    return {}

def http_post(url, payload, headers=None):
    req_headers = DEFAULT_HEADERS.copy()
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers, data=json.dumps(payload).encode('utf-8'))
    resp = opener.open(req)
    if 200 <= resp.status < 300:
        return json.loads(resp.read().decode('utf-8'))
    return {}

def fetch_raw_text(url, headers=None):
    req_headers = {'User-Agent': DEFAULT_HEADERS['User-Agent']}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    resp = opener.open(req)
    if 200 <= resp.status < 300:
        return resp.read().decode('utf-8')
    return ""

def fetch_raw_text_and_url(url, headers=None):
    req_headers = {'User-Agent': DEFAULT_HEADERS['User-Agent']}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    resp = opener.open(req)
    if 200 <= resp.status < 300:
        return resp.read().decode('utf-8'), resp.geturl()
    return "", url

def slugify(text):
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return re.sub(r'^-+|-+$', '', text)

def write_if_changed(filepath, new_content, is_binary=False):
    if os.path.exists(filepath):
        mode_read = "rb" if is_binary else "r"
        encoding = None if is_binary else "utf-8"
        with open(filepath, mode_read, encoding=encoding) as f:
            existing = f.read()
        if existing == new_content:
            return False
    mode_write = "wb" if is_binary else "w"
    encoding = None if is_binary else "utf-8"
    with open(filepath, mode_write, encoding=encoding) as f:
        f.write(new_content)
    return True

def cleanup_stale_files(base_directory, active_files_set):
    if not os.path.exists(base_directory):
        return
    deleted_count = 0
    deleted_dirs_count = 0
    for root, dirs, files in os.walk(base_directory, topdown=False):
        for fname in files:
            if fname.endswith(".m3u8"):
                full_path = os.path.normpath(os.path.join(root, fname))
                if full_path not in active_files_set:
                    if os.path.exists(full_path):
                        os.chmod(full_path, stat.S_IWRITE)
                        os.remove(full_path)
                        deleted_count += 1
        for dname in dirs:
            dir_path = os.path.join(root, dname)
            if os.path.exists(dir_path) and not os.listdir(dir_path):
                os.chmod(dir_path, stat.S_IWRITE)
                os.rmdir(dir_path)
                deleted_dirs_count += 1
    if deleted_count > 0 or deleted_dirs_count > 0:
        print(f"Cleaned up {deleted_count} stale/deleted files and {deleted_dirs_count} empty folders from {base_directory}.", flush=True)

def make_m3u8_absolute(m3u8_text, base_url):
    if not m3u8_text:
        return f"#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-STREAM-INF:BANDWIDTH=4000000\n{base_url}\n"
    parsed = urlparse(base_url)
    base_dir = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rsplit('/', 1)[0]}/"
    query_str = f"?{parsed.query}" if parsed.query else ""
    lines = []
    in_ad_block = False

    for line in m3u8_text.splitlines():
        line_str = line.strip()
        if any(ad_tag in line_str for ad_tag in [
            "#EXT-X-CUE-OUT", "#EXT-X-CUE-IN", "#EXT-X-SCTE35", 
            "#EXT-OATCLS-SCTE35", "#EXT-X-ASSET", "DATERANGE:CLASS=\"com.apple.hls.interstitial\"",
            "EXT-X-INTERSTITIAL", "pubads.g.doubleclick.net", "dai.tonton.com.my"
        ]):
            if "#EXT-X-CUE-OUT" in line_str:
                in_ad_block = True
            elif "#EXT-X-CUE-IN" in line_str:
                in_ad_block = False
            continue
            
        if in_ad_block:
            continue
            
        if line_str and not line_str.startswith("#"):
            if not line_str.startswith("http://") and not line_str.startswith("https://"):
                base_part = line_str.split('?')[0]
                if query_str and "?" not in line_str:
                    line_str = base_dir + base_part + query_str
                else:
                    line_str = base_dir + line_str
        lines.append(line_str)
    return "\n".join(lines) + "\n"
