import os
import json
import sqlite3
import argparse
from flask import Flask, render_template, request, send_from_directory, abort, g

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "pyqbox_data", "pyqs.db")
IMAGES_DIR = os.path.join(BASE_DIR, "pyqbox_data", "images")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"), static_folder=STATIC_DIR)

EXAM_TITLES = {
    'main': 'JEE Main',
    'advanced': 'JEE Advanced',
    'neet': 'NEET UG'
}

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/images/<path:filename>')
def serve_image(filename):
    file_path = os.path.join(IMAGES_DIR, filename)
    if not os.path.exists(file_path):
        abort(404)
    return send_from_directory(IMAGES_DIR, filename)

@app.route('/')
def index():
    db = get_db()
    stats = {}
    for exam in ['main', 'advanced', 'neet']:
        row = db.execute("SELECT count(*) as count FROM questions WHERE exam = ?", (exam,)).fetchone()
        stats[exam] = row['count'] if row else 0

    return render_template('index.html', stats=stats, current_exam=None)

@app.route('/<exam>/')
def exam_view(exam):
    if exam not in EXAM_TITLES:
        abort(404)

    db = get_db()
    rows = db.execute("SELECT DISTINCT subject FROM chapters WHERE exam = ? ORDER BY subject", (exam,)).fetchall()
    subjects = [r['subject'] for r in rows]

    current_sub = request.args.get('subject')
    if not current_sub or current_sub not in subjects:
        current_sub = subjects[0] if subjects else ''

    chapters = db.execute("""
        SELECT exam, subject, chapter, chapter_name, question_count 
        FROM chapters 
        WHERE exam = ? AND subject = ?
        ORDER BY question_count DESC
    """, (exam, current_sub)).fetchall()

    total_q = sum(ch['question_count'] for ch in chapters)

    return render_template(
        'exam.html',
        current_exam=exam,
        exam_title=EXAM_TITLES[exam],
        subjects=subjects,
        current_subject=current_sub,
        chapters=chapters,
        total_questions=total_q,
        sidebar_chapters=chapters
    )

@app.route('/<exam>/<subject>/<chapter>/')
def chapter_index_view(exam, subject, chapter):
    if exam not in EXAM_TITLES:
        abort(404)

    db = get_db()
    ch_meta = db.execute("""
        SELECT chapter_name, question_count 
        FROM chapters 
        WHERE exam = ? AND subject = ? AND chapter = ?
    """, (exam, subject, chapter)).fetchone()

    if not ch_meta:
        abort(404)

    # Lightweight query for question list
    rows = db.execute("""
        SELECT id, year, details, type, question_text
        FROM questions
        WHERE exam = ? AND subject = ? AND chapter = ?
        ORDER BY year DESC, id ASC
    """, (exam, subject, chapter)).fetchall()

    sidebar_chapters = db.execute("""
        SELECT chapter, chapter_name, question_count, subject 
        FROM chapters 
        WHERE exam = ? AND subject = ?
        ORDER BY question_count DESC
    """, (exam, subject)).fetchall()

    return render_template(
        'chapter_index.html',
        current_exam=exam,
        exam_title=EXAM_TITLES[exam],
        current_subject=subject,
        current_chapter=chapter,
        chapter_name=ch_meta['chapter_name'],
        questions=rows,
        sidebar_chapters=sidebar_chapters
    )

@app.route('/<exam>/<subject>/<chapter>/<int:q_index>/')
def question_detail_view(exam, subject, chapter, q_index):
    if exam not in EXAM_TITLES:
        abort(404)

    db = get_db()
    ch_meta = db.execute("""
        SELECT chapter_name, question_count 
        FROM chapters 
        WHERE exam = ? AND subject = ? AND chapter = ?
    """, (exam, subject, chapter)).fetchone()

    if not ch_meta:
        abort(404)

    total_q = ch_meta['question_count']
    if q_index < 1 or q_index > total_q:
        abort(404)

    # Fetch all questions in order to get the specific one
    rows = db.execute("""
        SELECT id, year, details, type, correct_answer, question_text, question_html, 
               options_json, solution_text, solution_html, images_json
        FROM questions
        WHERE exam = ? AND subject = ? AND chapter = ?
        ORDER BY year DESC, id ASC
    """, (exam, subject, chapter)).fetchall()

    if not rows or q_index > len(rows):
        abort(404)

    target_row = rows[q_index - 1]
    q_dict = dict(target_row)

    try:
        q_dict['options'] = json.loads(target_row['options_json']) if target_row['options_json'] else []
    except Exception:
        q_dict['options'] = []

    try:
        q_dict['images'] = json.loads(target_row['images_json']) if target_row['images_json'] else []
    except Exception:
        q_dict['images'] = []

    prev_url = f"/{exam}/{subject}/{chapter}/{q_index - 1}/" if q_index > 1 else None
    next_url = f"/{exam}/{subject}/{chapter}/{q_index + 1}/" if q_index < len(rows) else None

    sidebar_chapters = db.execute("""
        SELECT chapter, chapter_name, question_count, subject 
        FROM chapters 
        WHERE exam = ? AND subject = ?
        ORDER BY question_count DESC
    """, (exam, subject)).fetchall()

    return render_template(
        'question_view.html',
        current_exam=exam,
        exam_title=EXAM_TITLES[exam],
        current_subject=subject,
        current_chapter=chapter,
        chapter_name=ch_meta['chapter_name'],
        q=q_dict,
        current_index=q_index,
        total_questions=len(rows),
        prev_url=prev_url,
        next_url=next_url,
        sidebar_chapters=sidebar_chapters
    )

@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return render_template('search.html', query='', results=[])

    db = get_db()
    clean_q = ''.join(c if c.isalnum() or c.isspace() else ' ' for c in query).strip()
    if not clean_q:
        return render_template('search.html', query=query, results=[])

    fts_query = ' '.join(f'"{word}"' for word in clean_q.split())

    try:
        rows = db.execute("""
            SELECT q.id, q.exam, q.subject, q.chapter, q.chapter_name, q.details, q.question_text
            FROM questions_fts f
            JOIN questions q ON q.id = f.id
            WHERE questions_fts MATCH ?
            LIMIT 40
        """, (fts_query,)).fetchall()
    except Exception:
        like_pattern = f"%{clean_q}%"
        rows = db.execute("""
            SELECT id, exam, subject, chapter, chapter_name, details, question_text
            FROM questions
            WHERE question_text LIKE ? OR details LIKE ?
            LIMIT 40
        """, (like_pattern, like_pattern)).fetchall()

    results = [dict(r) for r in rows]
    return render_template('search.html', query=query, results=results, current_exam=None)

def main():
    parser = argparse.ArgumentParser(description="Pyqbox Practice Web Application")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5050, help="Port to run server on (default: 5050)")
    args = parser.parse_args()

    print(f"\n=======================================================")
    print(f"  PYQBox Practice Server running on http://{args.host}:{args.port}")
    print(f"  Total Questions: 22,359 (JEE Main, Advanced, NEET UG)")
    print(f"=======================================================\n")
    app.run(host=args.host, port=args.port, debug=False)

if __name__ == "__main__":
    main()
