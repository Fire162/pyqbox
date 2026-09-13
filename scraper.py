import os
import re
import json
import time
import argparse
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

BASE_URL = "https://pyqbox.com"
OUTPUT_DIR = "pyqbox_data"
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
JSON_OUTPUT = os.path.join(OUTPUT_DIR, "all_jee_pyqs.json")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

os.makedirs(IMAGES_DIR, exist_ok=True)

def create_session(pool_size=20):
    session = requests.Session()
    session.headers.update(HEADERS)
    retries = Retry(
        total=4,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(
        max_retries=retries,
        pool_connections=pool_size,
        pool_maxsize=pool_size
    )
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def fetch_html(url, session=None, retries=3):
    client = session or requests
    for attempt in range(retries):
        try:
            resp = client.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                resp.encoding = 'utf-8'
                return resp.text
            elif resp.status_code == 404:
                return None
        except Exception as e:
            if attempt == retries - 1:
                print(f"[ERROR] Failed to fetch {url}: {e}")
                return None
            time.sleep(1)
    return None

def download_image(img_url, q_id, img_index, session=None):
    try:
        full_img_url = urllib.parse.urljoin(BASE_URL, img_url)
        parsed_path = urllib.parse.urlparse(full_img_url).path
        ext = os.path.splitext(parsed_path)[1].lower()
        if not ext or len(ext) > 5:
            ext = ".png"
        filename = f"{q_id}_{img_index}{ext}"
        save_path = os.path.join(IMAGES_DIR, filename)

        if not os.path.exists(save_path):
            client = session or requests
            resp = client.get(full_img_url, headers=HEADERS, timeout=20)
            if resp.status_code == 200:
                with open(save_path, 'wb') as f:
                    f.write(resp.content)
            else:
                return full_img_url

        return os.path.join("images", filename)
    except Exception as e:
        print(f"[WARNING] Failed to download image {img_url}: {e}")
        return img_url

def parse_question_page(q_url, chapter_meta, session=None):
    html = fetch_html(q_url, session=session)
    if not html:
        return None

    soup = BeautifulSoup(html, 'html.parser')
    art = soup.find('article')
    if not art:
        return None

    q_id = art.get('data-q', '')
    q_type = art.get('data-type', '')
    q_key = art.get('data-key', '')
    q_year = art.get('data-year', '')

    head_div = art.find('div', class_='q-head')
    metadata_str = ""
    if head_div:
        spans = head_div.find_all('span')
        if len(spans) >= 2:
            metadata_str = spans[1].get_text(strip=True)

    title_el = art.find('h1', class_='qtitle')
    question_text = title_el.get_text(separator=" ", strip=True) if title_el else ""
    question_html = str(title_el) if title_el else ""

    # Parse options if MCQ
    options = []
    opts_container = art.find(['ul', 'ol', 'div'], class_=['opts', 'mcq'])
    if opts_container:
        for opt in opts_container.find_all(['button', 'label'], class_='opt'):
            key_el = opt.find(class_='opt-key')
            key = key_el.get_text(strip=True) if key_el else opt.get('data-opt', '')
            text_el = opt.find('div') or opt
            text = text_el.get_text(separator=" ", strip=True)
            options.append({'option': key, 'text': text})

    # Parse solution
    soln_div = art.find('div', class_='soln')
    solution_text = soln_div.get_text(separator=" ", strip=True) if soln_div else ""
    solution_html = str(soln_div) if soln_div else ""

    # Handle images
    images = []
    for idx, img in enumerate(art.find_all('img'), 1):
        src = img.get('src')
        if src:
            local_img_path = download_image(src, q_id, idx, session=session)
            images.append({'original_url': src, 'local_path': local_img_path})

    return {
        'id': q_id,
        'url': q_url,
        'exam': chapter_meta['exam'],
        'subject': chapter_meta['subject'],
        'chapter': chapter_meta['chapter'],
        'year': q_year,
        'details': metadata_str,
        'type': q_type,
        'correct_answer': q_key,
        'question_text': question_text,
        'question_html': question_html,
        'options': options,
        'solution_text': solution_text,
        'solution_html': solution_html,
        'images': images
    }

def get_chapter_question_urls(chapter_url, session=None):
    html = fetch_html(chapter_url, session=session)
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    qindex = soup.find('ol', class_='qindex-list')
    if not qindex:
        return []

    urls = []
    for a in qindex.find_all('a', href=True):
        full_url = urllib.parse.urljoin(BASE_URL, a['href'])
        urls.append(full_url)
    return urls

def get_all_chapters(session=None):
    html = fetch_html(f"{BASE_URL}/jee/", session=session)
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    chapters = []

    for a in soup.find_all('a', href=True):
        href = a['href']
        m = re.match(r'^/jee/(main|advanced)/([^/]+)/([^/]+)/?$', href)
        if m:
            exam, subject, chapter_slug = m.groups()
            if subject == 'papers' or chapter_slug.startswith('#'):
                continue
            chapter_name = a.get_text(strip=True)
            full_url = urllib.parse.urljoin(BASE_URL, href)
            chapters.append({
                'url': full_url,
                'exam': exam,
                'subject': subject,
                'chapter': chapter_slug,
                'chapter_name': chapter_name
            })

    unique_chapters = {c['url']: c for c in chapters}.values()
    return list(unique_chapters)

def atomic_save_json(filepath, data):
    temp_file = f"{filepath}.tmp"
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_file, filepath)

def scrape_all(workers=10, save_interval=250, exam='all', limit_chapters=None, limit_questions=None):
    session = create_session(pool_size=workers * 2)

    print("[1/3] Scraping chapter list...")
    chapters = get_all_chapters(session=session)
    print(f"Found {len(chapters)} chapters across JEE Main and Advanced.")

    if exam in ('main', 'advanced'):
        chapters = [c for c in chapters if c['exam'] == exam]
        print(f"Filtered for JEE {exam.capitalize()} only: {len(chapters)} chapters.")

    if limit_chapters:
        chapters = chapters[:limit_chapters]
        print(f"Limiting to first {limit_chapters} chapters for this run.")

    all_q_urls = []
    print(f"[2/3] Extracting individual question URLs across {len(chapters)} chapters in parallel...")
    with ThreadPoolExecutor(max_workers=min(workers, 15)) as executor:
        futures = {executor.submit(get_chapter_question_urls, ch['url'], session): ch for ch in chapters}
        for future in as_completed(futures):
            ch = futures[future]
            try:
                q_urls = future.result()
                print(f"  {ch['exam']} / {ch['subject']} / {ch['chapter']}: {len(q_urls)} questions")
                for u in q_urls:
                    all_q_urls.append((u, ch))
            except Exception as e:
                print(f"  [ERROR] Failed extracting URLs for {ch['url']}: {e}")

    print(f"\nTotal question URLs collected: {len(all_q_urls)}")

    existing_data = []
    scraped_urls = set()
    scraped_ids = set()

    if os.path.exists(JSON_OUTPUT):
        try:
            with open(JSON_OUTPUT, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                for q in existing_data:
                    if 'url' in q:
                        scraped_urls.add(q['url'])
                    if 'id' in q and q['id']:
                        scraped_ids.add(q['id'])
            print(f"Found existing dataset with {len(existing_data)} questions. Resuming...")
        except Exception as e:
            print(f"[WARNING] Could not read existing JSON file: {e}")

    # Resume matching: match against scraped_urls or question UUID prefix
    def is_already_scraped(url):
        if url in scraped_urls:
            return True
        slug = url.rstrip('/').split('/')[-1]
        slug_short_id = slug.split('-')[-1]
        for sid in scraped_ids:
            if sid.startswith(slug_short_id):
                return True
        return False

    urls_to_scrape = [(u, meta) for u, meta in all_q_urls if not is_already_scraped(u)]
    print(f"Remaining questions to scrape: {len(urls_to_scrape)}")

    if limit_questions and limit_questions > 0:
        urls_to_scrape = urls_to_scrape[:limit_questions]
        print(f"Limiting to {len(urls_to_scrape)} questions for this run.")

    if not urls_to_scrape:
        print("All target questions have already been scraped!")
        return

    print(f"[3/3] Downloading & parsing {len(urls_to_scrape)} question pages (using {workers} workers)...")

    questions_data = list(existing_data)
    completed = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(parse_question_page, q_url, meta, session): q_url for q_url, meta in urls_to_scrape}
        for future in as_completed(futures):
            completed += 1
            res = future.result()
            if res:
                questions_data.append(res)

            if completed % save_interval == 0 or completed == len(urls_to_scrape):
                print(f"  Progress: {completed}/{len(urls_to_scrape)} processed. Saving atomically ({len(questions_data)} total)...")
                atomic_save_json(JSON_OUTPUT, questions_data)

    print(f"\nScraping complete! Final total: {len(questions_data)} questions saved to {JSON_OUTPUT}.")
    print("Done!")

def main():
    parser = argparse.ArgumentParser(description="Scrape JEE Main & Advanced PYQs from Pyqbox.com")
    parser.add_argument("--workers", type=int, default=10, help="Number of concurrent worker threads (default: 10)")
    parser.add_argument("--save-interval", type=int, default=250, help="Incremental atomic save frequency (default: 250)")
    parser.add_argument("--exam", type=str, choices=['main', 'advanced', 'all'], default='all', help="Filter by exam: main, advanced, or all (default: all)")
    parser.add_argument("--limit-chapters", type=int, default=None, help="Limit number of chapters to process (for testing)")
    parser.add_argument("--limit-questions", type=int, default=None, help="Limit number of questions to process (for testing)")

    args = parser.parse_args()
    scrape_all(
        workers=args.workers,
        save_interval=args.save_interval,
        exam=args.exam,
        limit_chapters=args.limit_chapters,
        limit_questions=args.limit_questions
    )

if __name__ == "__main__":
    main()
