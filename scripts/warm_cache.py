#!/usr/bin/env python3
"""
Cloudflare Edge Cache Warmer for PYQBox (pyqs.wegenz.in)
Fetches all sitemap URLs concurrently to prime the Cloudflare Edge Cache.
"""

import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

SITEMAP_URL = "https://pyqs.wegenz.in/sitemap.xml"
CONCURRENCY = 15
USER_AGENT = "WegenzCacheWarmer/1.0 (+https://pyqs.wegenz.in/)"

def fetch_url(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT}
    )
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            dur = (time.time() - start) * 1000
            cf_cache = resp.headers.get("cf-cache-status", "NONE")
            return url, resp.status, cf_cache, dur, None
    except Exception as e:
        dur = (time.time() - start) * 1000
        return url, 0, "ERR", dur, str(e)

def main():
    print("=" * 60)
    print("⚡ PYQBox Cloudflare Edge Cache Warmer")
    print(f"Loading sitemap from: {SITEMAP_URL}")
    print("=" * 60)

    try:
        req = urllib.request.Request(SITEMAP_URL, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            sitemap_data = resp.read()
    except Exception as e:
        print(f"❌ Failed to fetch sitemap: {e}")
        sys.exit(1)

    root = ET.fromstring(sitemap_data)
    urls = [elem.text for elem in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    total = len(urls)
    print(f"✓ Found {total} URLs in sitemap to warm up.")
    print(f"⚡ Priming edge cache with {CONCURRENCY} concurrent workers...\n")

    hits = 0
    misses = 0
    errors = 0
    completed = 0
    start_all = time.time()

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = {executor.submit(fetch_url, u): u for u in urls}
        for fut in as_completed(futures):
            completed += 1
            url, status, cf_cache, dur, err = fut.result()
            if status == 200:
                if cf_cache == "HIT":
                    hits += 1
                else:
                    misses += 1
            else:
                errors += 1

            if completed % 25 == 0 or completed == total:
                elapsed = time.time() - start_all
                rate = completed / elapsed if elapsed > 0 else 0
                print(f"[{completed}/{total}] ({completed*100//total}%) | HIT: {hits} | MISS (Cached): {misses} | ERR: {errors} | Rate: {rate:.1f} req/s")

    total_time = time.time() - start_all
    print("\n" + "=" * 60)
    print(f"🎉 Cache Warming Complete in {total_time:.2f}s!")
    print(f"• Total URLs: {total}")
    print(f"• Primed (New Edge Cache): {misses}")
    print(f"• Already Cached (HIT): {hits}")
    print(f"• Errors: {errors}")
    print("=" * 60)

if __name__ == "__main__":
    main()
