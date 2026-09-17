#!/usr/bin/env python3
"""
Full Catalog Cloudflare Edge Cache Warmer for PYQBox (pyqs.wegenz.in)
Pre-caches all 22,359 individual question pages at Cloudflare Edge.
Supports graceful resume, high concurrency, and live progress reporting.
"""

import os
import sys
import time
import sqlite3
import asyncio
import aiohttp

DB_PATH = "/root/pyqs/pyqbox_data/pyqs.db"
STATE_FILE = "/tmp/pyqs_warmed_urls.txt"
CONCURRENCY = 25
BASE_URL = "https://pyqs.wegenz.in"
USER_AGENT = "WegenzCacheWarmer/2.0 (+https://pyqs.wegenz.in/)"

def get_all_question_urls():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        sys.exit(1)

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    rows = cur.execute("""
        SELECT exam, subject, chapter, count(*) as count
        FROM questions
        WHERE chapter IS NOT NULL AND chapter != ''
        GROUP BY exam, subject, chapter
        ORDER BY exam, subject, chapter
    """).fetchall()
    con.close()

    urls = []
    for exam, subject, chapter, count in rows:
        for idx in range(1, count + 1):
            urls.append(f"{BASE_URL}/{exam}/{subject}/{chapter}/{idx}/")
    return urls

async def fetch_worker(queue, session, state_set, state_f, stats, total, start_time):
    while True:
        try:
            url = await queue.get()
        except asyncio.CancelledError:
            break

        if url is None:
            queue.task_done()
            break

        if url in state_set:
            stats["skipped"] += 1
            stats["done"] += 1
            queue.task_done()
            continue

        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                await resp.read()
                cf_cache = resp.headers.get("cf-cache-status", "NONE")
                if resp.status == 200:
                    if cf_cache == "HIT":
                        stats["hits"] += 1
                    else:
                        stats["misses"] += 1
                    state_set.add(url)
                    state_f.write(url + "\n")
                    if stats["done"] % 25 == 0:
                        state_f.flush()
                else:
                    stats["errors"] += 1
        except Exception:
            stats["errors"] += 1

        stats["done"] += 1

        # Periodic status report
        done = stats["done"]
        if done % 250 == 0 or done == total:
            elapsed = time.time() - start_time
            rate = (done - stats["skipped"]) / elapsed if elapsed > 0 else 0
            rem = total - done
            eta_sec = rem / rate if rate > 0 else 0
            eta_min = eta_sec / 60
            pct = (done * 100) // total
            print(
                f"[{done:>5}/{total}] ({pct:>2}%) | "
                f"HIT: {stats['hits']:>5} | "
                f"CACHED: {stats['misses']:>5} | "
                f"ERR: {stats['errors']:>2} | "
                f"Rate: {rate:.1f} req/s | "
                f"ETA: {eta_min:.1f}m",
                flush=True
            )

        queue.task_done()

async def main_async():
    print("=" * 65)
    print("⚡ PYQBox Full 22,359 Question Edge Cache Warmer (High Speed)")
    print("=" * 65)

    urls = get_all_question_urls()
    total = len(urls)
    print(f"✓ Enumerated {total} question URLs from SQLite database.")

    # Load resume state if exists
    state_set = set()
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            for line in f:
                state_set.add(line.strip())
        print(f"✓ Resuming with {len(state_set)} already warmed URLs.")

    print(f"⚡ Launching {CONCURRENCY} concurrent async workers...\n", flush=True)

    stats = {
        "done": 0,
        "hits": 0,
        "misses": 0,
        "errors": 0,
        "skipped": 0
    }
    start_time = time.time()

    queue = asyncio.Queue(maxsize=CONCURRENCY * 4)
    state_f = open(STATE_FILE, "a", buffering=65536)

    connector = aiohttp.TCPConnector(limit=CONCURRENCY * 2, ttl_dns_cache=600)
    headers = {"User-Agent": USER_AGENT}
    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        workers = [
            asyncio.create_task(
                fetch_worker(queue, session, state_set, state_f, stats, total, start_time)
            )
            for _ in range(CONCURRENCY)
        ]

        # Feed queue
        for u in urls:
            await queue.put(u)

        # Wait for all tasks to be processed
        await queue.join()

        # Stop workers
        for _ in range(CONCURRENCY):
            await queue.put(None)
        await asyncio.gather(*workers)

    state_f.close()
    elapsed = time.time() - start_time
    print("\n" + "=" * 65)
    print(f"🎉 Full Question Cache Warming Finished in {elapsed/60:.1f} minutes!")
    print(f"• Total Processed: {stats['done']}")
    print(f"• Newly Cached at Edge: {stats['misses']}")
    print(f"• Already Edge HIT: {stats['hits']}")
    print(f"• Skipped (from state): {stats['skipped']}")
    print(f"• Errors: {stats['errors']}")
    print("=" * 65, flush=True)

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
