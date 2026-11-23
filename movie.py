#!/usr/bin/env python3
"""
Alert when a movie's shows for a given date appear on a District cinema page.

    pip install requests
    python movie.py --test-alert                 # check notifications work
    python movie.py --once --date 2026-11-25     # detector test (Wednesday has shows -> MATCH)
    python movie.py --once                       # one real check for TARGET_DATE
    python movie.py                              # loop every INTERVAL seconds
"""
import argparse
import platform
import random
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ---------------- CONFIG ----------------
BASE_URL = "https://www.district.in/movies/cinepolis-centre-square-mall-ernakulam-kochi-CD122"
MOVIE = "godzilla minus zero"          # matched case-insensitively against show names
TARGET_DATE = "2026-11-26"             # Thursday
NTFY_TOPIC = "thomas-movie-alert-change-me"
INTERVAL = 15 * 60
# ----------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-IN,en;q=0.9",
}
DONE_FILE = Path(__file__).with_name(".alert_sent")
DUMP_FILE = Path(__file__).with_name("page_dump.html")
SHOW_RE = re.compile(r'"name":"([^"]*)","startDate":"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})')


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def page_url(date):
    return f"{BASE_URL}?fromdate={date}"


def fetch(date):
    r = requests.get(page_url(date), headers=HEADERS, timeout=30)
    log(f"HTTP {r.status_code}, {len(r.text)} bytes ({date})")
    return r.text if r.status_code == 200 else None


def find_shows(html, date):
    found = set()
    for name, d, t in SHOW_RE.findall(html):
        if d == date and MOVIE in name.lower():
            found.add((t, name))
    return sorted(found)


def notify(title, body, url):
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=body.encode("utf-8"),
            headers={"Title": title, "Priority": "high", "Click": url},
            timeout=15,
        )
    except requests.RequestException as e:
        log(f"ntfy failed: {e}")
    if platform.system() == "Darwin":
        script = f'display notification "{body}" with title "{title}" sound name "Glass"'
        subprocess.run(["osascript", "-e", script], check=False)


def check_once(date, is_test=False):
    if not is_test and DONE_FILE.exists():
        log("Alert already sent earlier. Delete .alert_sent to re-arm.")
        return True
    html = fetch(date)
    if html is None:
        return False
    shows = find_shows(html, date)
    if not shows:
        log(f"Not open yet: no '{MOVIE}' shows on {date}.")
        return False
    times = ", ".join(t for t, _ in shows)
    log(f"MATCH: {len(shows)} show(s) on {date}: {times}")
    notify(f"Bookings open for {date}!", f"{shows[0][1]}: {times}", page_url(date))
    if not is_test:
        DONE_FILE.write_text(datetime.now().isoformat())
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--test-alert", action="store_true")
    ap.add_argument("--date", help="override TARGET_DATE (test mode: no .alert_sent)")
    args = ap.parse_args()
    date = args.date or TARGET_DATE
    is_test = bool(args.date)

    if args.test_alert:
        notify("Test alert", "If you see this, alerts work.", BASE_URL)
        return
    if args.dump:
        html = fetch(date)
        if html:
            DUMP_FILE.write_text(html, encoding="utf-8")
            log(f"Saved to {DUMP_FILE}")
        return
    if args.once:
        check_once(date, is_test)
        return

    log(f"Watching {MOVIE!r} on {date} every {INTERVAL // 60} min. Ctrl+C to stop.")
    while True:
        try:
            if check_once(date, is_test):
                break
        except requests.RequestException as e:
            log(f"Network error: {e}")
        time.sleep(INTERVAL + random.randint(-30, 30))


if __name__ == "__main__":
    main()
