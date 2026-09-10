import os
import stat

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

def process_tonton_vod(device_id):
    print("--- Processing Tonton VOD (Placeholder) ---")
    os.makedirs("streams/vod_tonton", exist_ok=True)
    active_files_set = set()
    cleanup_stale_files("streams/vod_tonton", active_files_set)
    return []
