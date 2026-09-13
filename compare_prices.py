#!/usr/bin/env python3
"""Compare all feeds in a repository config using Python 3's standard library."""

import argparse
import csv
import json
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def fetch(base_url, feeds, timeout):
    request = Request(
        base_url.rstrip("/") + "/feed-values/",
        data=json.dumps({"feeds": feeds}).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ValueError("Expected a JSON object with a data array")
        values = {}
        for item in payload["data"]:
            feed = item["feed"]
            key = (feed["category"], feed["name"])
            if key in values:
                raise ValueError(f"Duplicate response feed: {key}")
            value = item.get("value")
            values[key] = (
                value if type(value) in (int, float) and math.isfinite(value) else None
            )
        return values, None
    except (HTTPError, URLError, OSError, ValueError, KeyError, TypeError) as error:
        return {}, str(error)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feeds", type=Path, default=Path("src/config/feeds.json"))
    parser.add_argument("--local", default="http://localhost:4101")
    parser.add_argument("--ghcr", default="http://localhost:4102")
    parser.add_argument("--timeout", type=float, default=10, help="HTTP timeout in seconds")
    parser.add_argument("--wait", type=float, default=60,
                        help="Retry window for missing prices or unavailable APIs; 0 for one attempt")
    parser.add_argument("--csv", type=Path, help="Optional CSV output path")
    args = parser.parse_args()
    if args.timeout <= 0 or args.wait < 0:
        parser.error("--timeout must be positive and --wait must be nonnegative")

    try:
        config = json.loads(args.feeds.read_text())
        feeds = []
        seen = set()
        for entry in config:
            feed = entry["feed"]
            key = (feed["category"], feed["name"])
            if key not in seen:
                seen.add(key)
                feeds.append({"category": key[0], "name": key[1]})
        if not feeds:
            raise ValueError("No feeds in config")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(f"Cannot load {args.feeds}: {error}")

    deadline = time.monotonic() + args.wait
    with ThreadPoolExecutor(max_workers=2) as pool:
        while True:
            sampled_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            # Both requests contain the same full list and run concurrently.
            local_future = pool.submit(fetch, args.local, feeds, args.timeout)
            ghcr_future = pool.submit(fetch, args.ghcr, feeds, args.timeout)
            local, local_error = local_future.result()
            ghcr, ghcr_error = ghcr_future.result()
            missing = sum(local.get(key) is None or ghcr.get(key) is None for key in seen)
            if not missing or time.monotonic() >= deadline:
                break
            print(f"Waiting: {missing}/{len(feeds)} feeds lack a price from one or both providers.",
                  file=sys.stderr)
            if local_error:
                print(f"  Local: {local_error}", file=sys.stderr)
            if ghcr_error:
                print(f"  GHCR: {ghcr_error}", file=sys.stderr)
            time.sleep(min(5, max(0, deadline - time.monotonic())))

    for label, error in (("Local", local_error), ("GHCR", ghcr_error)):
        if error:
            print(f"{label} API error: {error}", file=sys.stderr)

    rows = []
    for feed in feeds:
        key = (feed["category"], feed["name"])
        left, right = local.get(key), ghcr.get(key)
        delta = left - right if left is not None and right is not None else None
        percent = 100 * delta / right if delta is not None and right != 0 else None
        status = "OK"
        if left is None or right is None:
            status = "MISSING " + ("BOTH" if left is None and right is None else
                                   "LOCAL" if left is None else "GHCR")
        elif right == 0:
            status = "GHCR ZERO; % N/A"
        rows.append({"sample_started_utc": sampled_at, "category": key[0], "asset": key[1],
                     "local": left, "ghcr": right, "local_minus_ghcr": delta,
                     "difference_pct": percent, "status": status})

    def number(value):
        return "N/A" if value is None else f"{value:.10g}"

    print(f"Sample started (UTC): {sampled_at}")
    print(f"Local: {args.local} | GHCR: {args.ghcr}")
    print(f"{'Cat':>3}  {'Asset':<18} {'Local':>16} {'GHCR':>16} {'Local - GHCR':>16} {'Diff %':>12}  Status")
    for row in rows:
        print(f"{row['category']:>3}  {row['asset']:<18} "
              f"{number(row['local']):>16} {number(row['ghcr']):>16} "
              f"{number(row['local_minus_ghcr']):>16} {number(row['difference_pct']):>12}  {row['status']}")
    print(f"\n{len(feeds) - missing}/{len(feeds)} feeds have prices from both providers.")

    if args.csv:
        with args.csv.open("w", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"CSV saved to {args.csv}")
    # Price differences are expected; only missing data/request failures fail the run.
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
