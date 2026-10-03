import os
import sys

# Root and script directory anchors
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR   = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

# Auto-register script/ so all submodules can import utils, paths, etc.
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# Auth directory and key files
_SHARED_AUTH = os.path.abspath(os.path.join(ROOT_DIR, "..", "shared_auth", "MY-tv"))
AUTH_DIR     = _SHARED_AUTH if os.path.isdir(_SHARED_AUTH) else os.path.join(ROOT_DIR, "auth")
TOKEN_FILE   = os.path.join(AUTH_DIR, "tonton")

# Read credentials or configuration file from auth directory
def read_auth(filename):
    file_path = os.path.join(AUTH_DIR, filename)
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return ""

# Write credentials or configuration file to auth directory
def write_auth(filename, content):
    os.makedirs(AUTH_DIR, exist_ok=True)
    file_path = os.path.join(AUTH_DIR, filename)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception:
        return False

# Root output files (written to project root, run from ROOT_DIR)
EPG_XML    = "epg.xml"
EPG_GZ     = "epg.xml.gz"
PLAYLIST   = "playlist.m3u"
PLAYLIST8  = "playlist.m3u8"
VOD_M3U    = "vod.m3u"
VOD_M3U8   = "vod.m3u8"
ALL_M3U    = "all.m3u"
ALL_M3U8   = "all.m3u8"

# Catalog list files
LIST_LIVE   = "List/LIVE_LIST.md"
LIST_SHOWS  = "List/SHOWS_LIST.md"
LIST_MOVIES = "List/MOVIES_LIST.md"

# Stream output directories
LIVE_MYTV   = "streams/live_mytv"
LIVE_TONTON = "streams/live_tonton"
LIVE_UNIFI  = "streams/live_unifi"
RADIO_MYTV  = "streams/radio_mytv"
VOD_MYTV    = "streams/vod_mytv"
VOD_TONTON  = "streams/vod_tonton"
VOD_UNIFI   = "streams/vod_unifi"
