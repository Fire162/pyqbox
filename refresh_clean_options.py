import os
import re
import json
import sqlite3
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = "/root/pyqs"
DATA_DIR = os.path.join(BASE_DIR, "pyqbox_data")
DB_PATH = os.path.join(DATA_DIR, "pyqs.db")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120'
}

PAPER_INDEXES = [
    ('main', 'https://pyqbox.com/jee/main/papers/'),
    ('advanced', 'https://pyqbox.com/jee/advanced/papers/'),
    ('neet', 'https://pyqbox.com/neet/papers/')
]

def get_paper_urls():
    papers = []
    for exam, index_url in PAPER_INDEXES:
        try:
            r = requests.get(index_url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                seen = set()
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if '/paper/' in href and href not in seen:
                        seen.add(href)
                        full_url = f"https://pyqbox.com{href}" if href.startswith('/') else href
                        if not full_url.endswith('/'):
                            full_url += '/'
                        slug = href.strip('/').split('/')[-1]
                        papers.append({
                            'exam': exam,
                            'url': full_url,
                            'slug': slug
                        })
                print(f"[{exam}] Found {len(seen)} unique paper pages.")
        except Exception as e:
            print(f"Error fetching {index_url}: {e}")
    return papers

def fetch_clean_options_from_paper(paper):
    mock_url = f"{paper['url']}mock.json"
    results = {}
    try:
        r = requests.get(mock_url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            cards = data.get('cards', [])
            for c in cards:
                soup = BeautifulSoup(c, 'html.parser')
                art = soup.find('article')
                if not art:
                    continue
                q_id = art.get('data-q')
                if not q_id:
                    continue
                opts = []
                for opt in soup.find_all(class_='opt'):
                    key_el = opt.find(class_='opt-key')
                    key = key_el.get_text(strip=True) if key_el else opt.get('data-opt', '')
                    div = opt.find('div') or opt
                    opt_html = div.decode_contents().strip()
                    for k in div.find_all(class_='katex'):
                        ann = k.find('annotation')
                        if ann and ann.get_text():
                            k.replace_with(f"\\({ann.get_text().strip()}\\)")
                    text = div.get_text(separator=' ', strip=True)
                    opts.append({'option': key, 'text': text, 'html': opt_html})
                results[q_id] = opts
    except Exception as e:
        print(f"Error fetching {mock_url}: {e}")
    return results

def fallback_clean_option(s):
    if not s or not isinstance(s, str):
        return s
    cleaned = s.replace('\u200b', '').replace('\ue020', '').strip()
    if not cleaned:
        return ""
    if r'\(' in cleaned and r'\)' in cleaned:
        if not (cleaned.startswith(r'\(') and cleaned.endswith(r'\)') and cleaned.count(r'\(') == 1):
            return cleaned
    if cleaned.startswith(r'\(') and cleaned.endswith(r'\)'):
        inner = cleaned[2:-2].strip()
        if r'\(' not in inner and r'\)' not in inner:
            cleaned = inner
        else:
            return cleaned
    if '\\' not in cleaned and '_' not in cleaned and '^' not in cleaned:
        return cleaned

    cleaned = re.sub(r'\(\s*([A-Za-z0-9]+)\s*\)\s*\(\\mathrm\{([A-Za-z0-9]+)\}\)\s*\(\s*\1\s*\)', r'(\2)', cleaned)
    cleaned = re.sub(r'\(\s*([A-Za-z0-9]+)\s*\\mathrm\{([A-Za-z0-9]+)\}\s*\1\s*\)', r'(\2)', cleaned)
    cleaned = re.sub(r'\b([A-Za-z0-9]+)\s*\\mathrm\{([A-Za-z0-9]+)\}\s*\1\b', r'\2', cleaned)

    anchors = list(re.finditer(r'(\\[a-zA-Z]+|_[0-9a-zA-Z{]|\^[0-9a-zA-Z{]|\\%|\\rightarrow)', cleaned))
    if not anchors:
        return cleaned
    first_anchor = anchors[0].start()
    last_anchor = anchors[-1].end()

    for i in range(first_anchor, -1, -1):
        for j in range(len(cleaned), last_anchor - 1, -1):
            prefix = cleaned[:i].strip()
            middle = cleaned[i:j].strip()
            suffix = cleaned[j:].strip()
            if not prefix and not suffix:
                continue
            norm_p = re.sub(r'[\s\u200b\ue020\.\,]+', '', prefix).replace('−', '-').replace('–', '-')
            norm_s = re.sub(r'[\s\u200b\ue020\.\,]+', '', suffix).replace('−', '-').replace('–', '-')
            if norm_p and norm_s and (norm_p == norm_s or sorted(norm_p) == sorted(norm_s)):
                return f"\\({middle}\\)"

    words = cleaned.split()
    has_english_words = any(w.lower() in {'is', 'an', 'the', 'are', 'both', 'and', 'not', 'correct', 'true', 'false', 'statement', 'reaction', 'only', 'neither'} for w in words)
    if not has_english_words:
        if not cleaned.startswith(r'\(') and not cleaned.endswith(r'\)'):
            return f"\\({cleaned}\\)"
    return cleaned

def main():
    print("=== Step 1: Discovering all paper URLs ===")
    papers = get_paper_urls()
    print(f"Total papers to process: {len(papers)}")

    print("\n=== Step 2: Concurrently scraping clean options from mock.json ===")
    clean_options_map = {}
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(fetch_clean_options_from_paper, p): p for p in papers}
        done = 0
        for f in as_completed(futures):
            res = f.result()
            clean_options_map.update(res)
            done += 1
            if done % 30 == 0 or done == len(papers):
                print(f"  Scraped {done}/{len(papers)} papers... ({len(clean_options_map)} questions mapped)")

    print(f"\nTotal clean questions extracted from papers: {len(clean_options_map)}")

    print("\n=== Step 3: Updating SQLite database ===")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 1. Update questions from papers
    update_data = [
        (json.dumps(opts, ensure_ascii=False), q_id)
        for q_id, opts in clean_options_map.items()
    ]
    print(f"Updating {len(update_data)} questions in SQLite from official papers...")
    c.executemany("UPDATE questions SET options_json = ? WHERE id = ?", update_data)
    conn.commit()

    # 2. For any remaining questions not in clean_options_map, apply fallback cleaner
    all_questions = c.execute("SELECT id, options_json FROM questions").fetchall()
    fallback_updates = []
    for q_id, opt_json_str in all_questions:
        if q_id in clean_options_map:
            continue
        if not opt_json_str:
            continue
        try:
            opts = json.loads(opt_json_str)
            changed = False
            for o in opts:
                old_text = o.get('text', '')
                new_text = fallback_clean_option(old_text)
                if new_text != old_text:
                    o['text'] = new_text
                    changed = True
            if changed:
                fallback_updates.append((json.dumps(opts, ensure_ascii=False), q_id))
        except Exception:
            pass

    if fallback_updates:
        print(f"Applied fallback cleaner to {len(fallback_updates)} additional questions...")
        c.executemany("UPDATE questions SET options_json = ? WHERE id = ?", fallback_updates)
        conn.commit()

    print("SQLite database updated successfully!")

    print("\n=== Step 4: Syncing updated options to JSONL datasets ===")
    jsonl_files = ['jee_mains.jsonl', 'jee_adv.jsonl', 'neet.jsonl']
    # Load all clean options from DB
    db_options = dict(c.execute("SELECT id, options_json FROM questions").fetchall())

    for filename in jsonl_files:
        filepath = os.path.join(DATA_DIR, filename)
        tmp_filepath = filepath + ".tmp"
        updated_count = 0
        with open(filepath, 'r', encoding='utf-8') as fin, open(tmp_filepath, 'w', encoding='utf-8') as fout:
            for line in fin:
                if not line.strip():
                    continue
                rec = json.loads(line.strip())
                q_id = rec.get('id')
                if q_id in db_options and db_options[q_id]:
                    rec['options'] = json.loads(db_options[q_id])
                    updated_count += 1
                fout.write(json.dumps(rec, ensure_ascii=False) + '\n')
        os.replace(tmp_filepath, filepath)
        print(f"  Synced {updated_count} questions in {filename}")

    conn.close()
    print("\n=== All clean LaTeX options updated successfully! ===")

if __name__ == '__main__':
    main()
