import os
import json
import sqlite3
import time

DB_PATH = "pyqbox_data/pyqs.db"
DATA_FILES = [
    ("main", "pyqbox_data/jee_mains.jsonl"),
    ("advanced", "pyqbox_data/jee_adv.jsonl"),
    ("neet", "pyqbox_data/neet.jsonl"),
]

def slug_to_title(slug):
    words = slug.replace("-", " ").split()
    return " ".join(w.capitalize() for w in words)

def build_database():
    start_time = time.time()
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("PRAGMA journal_mode = WAL;")
    cur.execute("PRAGMA synchronous = NORMAL;")

    cur.execute("""
    CREATE TABLE questions (
        id TEXT PRIMARY KEY,
        url TEXT,
        exam TEXT NOT NULL,
        subject TEXT NOT NULL,
        chapter TEXT NOT NULL,
        chapter_name TEXT,
        year TEXT,
        details TEXT,
        type TEXT,
        correct_answer TEXT,
        question_text TEXT,
        question_html TEXT,
        options_json TEXT,
        solution_text TEXT,
        solution_html TEXT,
        images_json TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE chapters (
        exam TEXT NOT NULL,
        subject TEXT NOT NULL,
        chapter TEXT NOT NULL,
        chapter_name TEXT NOT NULL,
        question_count INTEGER DEFAULT 0,
        PRIMARY KEY (exam, subject, chapter)
    );
    """)

    cur.execute("""
    CREATE INDEX idx_q_nav ON questions(exam, subject, chapter);
    """)
    cur.execute("""
    CREATE INDEX idx_q_year ON questions(exam, year);
    """)

    cur.execute("""
    CREATE VIRTUAL TABLE questions_fts USING fts5(
        id UNINDEXED,
        exam,
        subject,
        chapter_name,
        question_text,
        details,
        tokenize = 'unicode61'
    );
    """)

    total_inserted = 0
    chapter_counts = {}

    for default_exam, file_path in DATA_FILES:
        if not os.path.exists(file_path):
            print(f"[SKIP] {file_path} does not exist.")
            continue

        print(f"Ingesting {file_path}...")
        batch = []
        batch_fts = []

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    q = json.loads(line)
                    q_id = q.get("id") or q.get("url", "")
                    exam = q.get("exam") or default_exam
                    subject = q.get("subject", "general").lower()
                    chapter = q.get("chapter", "general").lower()
                    chapter_name = q.get("chapter_name") or slug_to_title(chapter)
                    year = str(q.get("year") or "")
                    details = q.get("details", "")
                    q_type = q.get("type", "single")
                    correct_answer = str(q.get("correct_answer") or "")
                    question_text = q.get("question_text", "")
                    question_html = q.get("question_html", "")
                    options_json = json.dumps(q.get("options", []), ensure_ascii=False)
                    solution_text = q.get("solution_text", "")
                    solution_html = q.get("solution_html", "")
                    images_json = json.dumps(q.get("images", []), ensure_ascii=False)

                    batch.append((
                        q_id, q.get("url", ""), exam, subject, chapter, chapter_name,
                        year, details, q_type, correct_answer, question_text,
                        question_html, options_json, solution_text, solution_html, images_json
                    ))

                    batch_fts.append((
                        q_id, exam, subject, chapter_name, question_text, details
                    ))

                    ch_key = (exam, subject, chapter, chapter_name)
                    chapter_counts[ch_key] = chapter_counts.get(ch_key, 0) + 1

                    if len(batch) >= 2000:
                        cur.executemany("""
                        INSERT OR REPLACE INTO questions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """, batch)
                        cur.executemany("""
                        INSERT INTO questions_fts VALUES (?, ?, ?, ?, ?, ?);
                        """, batch_fts)
                        total_inserted += len(batch)
                        batch = []
                        batch_fts = []
                except Exception as e:
                    print(f"Error parsing line: {e}")

        if batch:
            cur.executemany("""
            INSERT OR REPLACE INTO questions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, batch)
            cur.executemany("""
            INSERT INTO questions_fts VALUES (?, ?, ?, ?, ?, ?);
            """, batch_fts)
            total_inserted += len(batch)

    # Insert chapters summary
    cur.executemany("""
    INSERT INTO chapters (exam, subject, chapter, chapter_name, question_count)
    VALUES (?, ?, ?, ?, ?);
    """, [(k[0], k[1], k[2], k[3], count) for k, count in chapter_counts.items()])

    conn.commit()
    conn.close()

    elapsed = time.time() - start_time
    print(f"\n[DONE] Successfully indexed {total_inserted} questions across {len(chapter_counts)} chapters into {DB_PATH} in {elapsed:.2f}s!")

if __name__ == "__main__":
    build_database()
