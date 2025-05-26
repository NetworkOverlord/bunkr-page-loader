#!/usr/bin/env python3
import os
import time
import csv
import tempfile
import requests
import argparse
from datetime import datetime, timedelta
from dotenv import load_dotenv
from multiprocessing import Pool, cpu_count
from selenium.webdriver.chrome.options import Options
import undetected_chromedriver as uc
from functools import partial

load_dotenv()
API_TOKEN = os.getenv("BUNKR_API_TOKEN")
API_BASE = "https://dash.bunkr.cr/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "token": API_TOKEN
}
STALE_THRESHOLD_DAYS = 7
NOW = datetime.utcnow()
STALE_THRESHOLD = timedelta(days=STALE_THRESHOLD_DAYS)

def get_stale_uploads(include_images=True, include_videos=True):
    page = 0
    uploads = []
    while True:
        try:
            r = requests.get(f"{API_BASE}/uploads/{page}", headers=HEADERS)
            files = r.json().get("files", [])
            if not files:
                break
            for f in files:
                last = f.get("last_visited_at")
                if not last:
                    continue
                try:
                    ts = datetime.strptime(last, "%Y-%m-%dT%H:%M:%S.000Z")
                    if NOW - ts > STALE_THRESHOLD:
                        ext = os.path.splitext(f.get("name", ""))[1].lower()
                        if (include_videos and ext in [".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v"]) or \
                           (include_images and ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"]):
                            uploads.append(f)
                            uploads.append(f)
                except:
                    continue
            page += 1
        except:
            break
    return uploads

def visit_url(finalurl, max_retries=3, diagnostic_mode=False):
    from uuid import uuid4
    import shutil
    def try_once(url):
        try:
            profile_dir = f"/tmp/uc_profile_{uuid4()}"
            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--proxy-server=direct://")
            options.add_argument("--proxy-bypass-list=*")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-background-networking")
            options.add_argument("--disable-background-timer-throttling")
            options.page_load_strategy = 'eager'
            options.add_argument(f"--user-data-dir={profile_dir}")
            driver = uc.Chrome(options=options)
            driver.set_page_load_timeout(120)
            driver.get(url)
            driver.quit()
            shutil.rmtree(profile_dir, ignore_errors=True)
            return (url, "OK", "")
        except Exception as e:
            return (url, "FAILED", str(e))
    backoff = 1
    attempts = 1 if diagnostic_mode else max_retries
    for attempt in range(attempts):
        if diagnostic_mode:
            print(f"[RETRY] Attempt {attempt + 1} for {finalurl}")
        result = try_once(finalurl)
        if result[1] == "OK":
            return result
        time.sleep(backoff)
        backoff *= 2
    return (finalurl, "FAILED", result[2])

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--videos-only", action="store_true", help="Only include video files")
    group.add_argument("--images-only", action="store_true", help="Only include image files")
    parser.add_argument("--diagnostic", action="store_true", help="Enable diagnostic mode")
    parser.add_argument("--retry-failed", type=str, help="CSV file of failed URLs to retry")
    args = parser.parse_args()
    diagnostic_mode = args.diagnostic

    print("[INFO] Fetching stale uploads")
    if args.retry_failed:
        import pandas as pd
        if not os.path.isfile(args.retry_failed):
            print(f"[ERROR] Retry file not found: {args.retry_failed}")
            return
        try:
            df = pd.read_csv(args.retry_failed)
            if 'URL' not in df.columns:
                print("[ERROR] Retry file missing 'URL' column.")
                return
            urls = [url for url in df['URL'] if isinstance(url, str) and url.startswith('https://bunkr.pk/f/')]
            if not urls:
                print("[WARN] No valid Bunkr URLs found in retry file.")
                return
            stale_files = [{'finalurl': url} for url in urls]
            print(f"[INFO] Retrying {len(stale_files)} failed URLs from: {args.retry_failed}")
        except Exception as e:
            print(f"[ERROR] Failed to read retry file: {e}")
            return
    else:
        include_videos = not args.images_only
        include_images = not args.videos_only
        stale_files = get_stale_uploads(include_images=include_images, include_videos=include_videos)

    total = len(stale_files)
    if total == 0:
        print("[✓] No stale files found. Skipping processing and log creation.")
        return
    print(f"[→] Processing {total} stale files...")
    finalurls = [f['finalurl'] for f in stale_files]
    concurrency = min(6, cpu_count())
    print(f"[INFO] Starting visit pool with {concurrency} processes")

    visit_func = partial(visit_url, max_retries=3, diagnostic_mode=diagnostic_mode)
    results = []
    ok = 0
    fail = 0
    failure_count = 0

    with Pool(processes=concurrency) as pool:
        for i, result in enumerate(pool.imap_unordered(visit_func, finalurls), 1):
            url, status, reason = result
            results.append((url, status, reason))
            if status == "OK":
                ok += 1
            if status == "FAILED":
                fail += 1
                if diagnostic_mode:
                    failure_count += 1
                    if failure_count >= 10:
                        print("[WARN] Failure cap reached in diagnostic mode. Skipping remaining tasks.")
                        break
            symbol = "✓" if status == "OK" else "✗"
            print(f"[{symbol}] {i}/{total} Complete — OK: {ok} | Failed: {fail}")

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.expanduser("~/bunkr_logs/bunkr_album_refresh_logs/bunkr_refresh_log_" + timestamp + ".csv")
    fail_log_path = log_path.replace("bunkr_refresh_log", "failed_urls")
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["URL", "Status", "Reason"])
            writer.writerows(results)
        if fail > 0:
            with open(fail_log_path, "w", newline="") as ffile:
                writer = csv.writer(ffile)
                writer.writerow(["URL", "Status", "Reason"])
                writer.writerows([r for r in results if r[1] == "FAILED"])
            print(f"[✓] Failures saved to {fail_log_path}")
        else:
            print("[✓] No failures to log.")
        print(f"[✓] Finished: {len(results)} attempted — {ok} OK, {fail} failed")
        print(f"[✓] Log saved to {log_path}")
    except Exception as e:
        print(f"[!] Error writing logs: {e}")

if __name__ == "__main__":
    main()
