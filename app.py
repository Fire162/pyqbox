import os
import re
import json
import sqlite3
import argparse
from flask import Flask, render_template, request, send_from_directory, abort, g, jsonify, redirect

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

def extract_middle_latex(s):
    if not s or not isinstance(s, str):
        return s
    cleaned = s.replace('\u200b', '').replace('\ue020', '').strip()
    if not cleaned:
        return ""
    
    # If string already has balanced \( ... \) with other text or multiple spans
    if r'\(' in cleaned and r'\)' in cleaned:
        if not (cleaned.startswith(r'\(') and cleaned.endswith(r'\)') and cleaned.count(r'\(') == 1):
            return cleaned

    # Strip accidental outer wrapper \( ... \) if it wraps the whole string
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

    # Search for matching prefix and suffix
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

    # Fallback: only wrap if not looking like an English sentence with spaces/words
    words = cleaned.split()
    has_english_words = any(w.lower() in {'is', 'an', 'the', 'are', 'both', 'and', 'not', 'correct', 'true', 'false', 'statement', 'reaction', 'only', 'neither'} for w in words)
    if not has_english_words:
        if not cleaned.startswith(r'\(') and not cleaned.endswith(r'\)'):
            return f"\\({cleaned}\\)"
    return cleaned

@app.template_filter('clean_math')
def clean_math_filter(s):
    return extract_middle_latex(s)

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

@app.after_request
def add_cache_headers(response):
    if response.mimetype == 'text/html':
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

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

    # Filter & Sort parameters
    current_sort = request.args.get('sort', 'desc')
    current_year = request.args.get('year', '')
    current_shift = request.args.get('shift', '')
    current_type = request.args.get('type', '')

    query = """
        SELECT id, year, details, shift, type, question_text
        FROM questions
        WHERE exam = ? AND subject = ? AND chapter = ?
    """
    params = [exam, subject, chapter]

    if current_year:
        query += " AND year = ?"
        params.append(current_year)
    if current_shift:
        query += " AND shift = ?"
        params.append(current_shift)
    if current_type:
        query += " AND type = ?"
        params.append(current_type)

    if current_sort == 'asc':
        query += " ORDER BY year ASC, id ASC"
    else:
        query += " ORDER BY year DESC, id ASC"

    rows = db.execute(query, params).fetchall()

    available_years = [r['year'] for r in db.execute("""
        SELECT DISTINCT year FROM questions
        WHERE exam = ? AND subject = ? AND chapter = ?
        ORDER BY year DESC
    """, (exam, subject, chapter)).fetchall()]

    available_shifts = [r['shift'] for r in db.execute("""
        SELECT DISTINCT shift FROM questions
        WHERE exam = ? AND subject = ? AND chapter = ? AND shift IS NOT NULL AND shift != ''
        ORDER BY year DESC, shift ASC
    """, (exam, subject, chapter)).fetchall()]

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
        total_chapter_questions=ch_meta['question_count'],
        available_years=available_years,
        available_shifts=available_shifts,
        current_sort=current_sort,
        current_year=current_year,
        current_shift=current_shift,
        current_type=current_type,
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

# ==============================================================================
@app.route('/api')
@app.route('/api/docs')
def api_docs_view():
    return render_template('api_docs.html', current_exam=None)

@app.route('/<exam>/papers/')
def paper_list_view(exam):
    if exam not in EXAM_TITLES:
        abort(404)

    db = get_db()
    rows = db.execute("""
        SELECT year, shift, paper_slug, details, count(*) as question_count
        FROM questions
        WHERE exam = ? AND paper_slug IS NOT NULL AND paper_slug != ''
        GROUP BY paper_slug
        ORDER BY year DESC, details ASC
    """, (exam,)).fetchall()

    papers_by_year = {}
    for r in rows:
        y = r['year']
        if y not in papers_by_year:
            papers_by_year[y] = []
        papers_by_year[y].append(dict(r))

    sidebar_chapters = db.execute("""
        SELECT chapter, chapter_name, question_count, subject 
        FROM chapters 
        WHERE exam = ?
        ORDER BY question_count DESC
        LIMIT 30
    """, (exam,)).fetchall()

    return render_template(
        'papers.html',
        current_exam=exam,
        exam_title=EXAM_TITLES[exam],
        papers_by_year=papers_by_year,
        total_papers=len(rows),
        sidebar_chapters=sidebar_chapters,
        is_paper_view=True
    )

@app.route('/<exam>/paper/<paper_slug>/')
def paper_detail_view(exam, paper_slug):
    if exam not in EXAM_TITLES:
        abort(404)

    db = get_db()
    rows = db.execute("""
        SELECT id, year, details, shift, type, question_text, subject, chapter, chapter_name
        FROM questions
        WHERE exam = ? AND paper_slug = ?
        ORDER BY subject ASC, id ASC
    """, (exam, paper_slug)).fetchall()

    if not rows:
        abort(404)

    paper_title = rows[0]['details'] or paper_slug
    year = rows[0]['year']

    sidebar_chapters = db.execute("""
        SELECT chapter, chapter_name, question_count, subject 
        FROM chapters 
        WHERE exam = ?
        ORDER BY question_count DESC
        LIMIT 30
    """, (exam,)).fetchall()

    return render_template(
        'paper_index.html',
        current_exam=exam,
        exam_title=EXAM_TITLES[exam],
        paper_title=paper_title,
        paper_slug=paper_slug,
        year=year,
        questions=rows,
        sidebar_chapters=sidebar_chapters,
        is_paper_view=True
    )

@app.route('/<exam>/paper/<paper_slug>/<int:q_index>/')
def paper_question_detail_view(exam, paper_slug, q_index):
    if exam not in EXAM_TITLES:
        abort(404)

    db = get_db()
    rows = db.execute("""
        SELECT id, year, details, shift, type, correct_answer, question_text, question_html, 
               options_json, solution_text, solution_html, images_json, subject, chapter, chapter_name
        FROM questions
        WHERE exam = ? AND paper_slug = ?
        ORDER BY subject ASC, id ASC
    """, (exam, paper_slug)).fetchall()

    if not rows or q_index < 1 or q_index > len(rows):
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

    paper_title = target_row['details'] or paper_slug

    prev_url = f"/{exam}/paper/{paper_slug}/{q_index - 1}/" if q_index > 1 else None
    next_url = f"/{exam}/paper/{paper_slug}/{q_index + 1}/" if q_index < len(rows) else None

    sidebar_chapters = db.execute("""
        SELECT chapter, chapter_name, question_count, subject 
        FROM chapters 
        WHERE exam = ?
        ORDER BY question_count DESC
        LIMIT 30
    """, (exam,)).fetchall()

    return render_template(
        'question_view.html',
        current_exam=exam,
        exam_title=EXAM_TITLES[exam],
        current_subject=target_row['subject'],
        current_chapter=target_row['chapter'],
        chapter_name=target_row['chapter_name'],
        paper_title=paper_title,
        paper_slug=paper_slug,
        is_paper_view=True,
        q=q_dict,
        current_index=q_index,
        total_questions=len(rows),
        prev_url=prev_url,
        next_url=next_url,
        list_url=f"/{exam}/paper/{paper_slug}/",
        list_title=paper_title,
        sidebar_chapters=sidebar_chapters
    )

@app.route('/question/<q_id>/')
def direct_question_view(q_id):
    db = get_db()
    row = db.execute("SELECT id, exam, subject, chapter, paper_slug FROM questions WHERE id = ?", (q_id,)).fetchone()
    if not row:
        abort(404)
    exam = row['exam']
    subject = row['subject']
    chapter = row['chapter']
    rows = db.execute("SELECT id FROM questions WHERE exam = ? AND subject = ? AND chapter = ? ORDER BY year DESC, id ASC", (exam, subject, chapter)).fetchall()
    idx = 1
    for i, r in enumerate(rows, 1):
        if r['id'] == q_id:
            idx = i
            break
    return redirect(f"/{exam}/{subject}/{chapter}/{idx}/")

# ==============================================================================
# REST API Endpoints (v1)
# ==============================================================================

@app.route('/api/v1/exams', methods=['GET'])
def api_exams():
    db = get_db()
    exams = []
    for exam_id, title in EXAM_TITLES.items():
        total = db.execute("SELECT count(*) as c FROM questions WHERE exam = ?", (exam_id,)).fetchone()['c']
        subjects = [r['subject'] for r in db.execute("SELECT DISTINCT subject FROM chapters WHERE exam = ? ORDER BY subject", (exam_id,)).fetchall()]
        years = [r['year'] for r in db.execute("SELECT DISTINCT year FROM questions WHERE exam = ? ORDER BY year DESC", (exam_id,)).fetchall()]
        exams.append({
            'id': exam_id,
            'title': title,
            'question_count': total,
            'subjects': subjects,
            'years': years
        })
    return jsonify({'exams': exams})

@app.route('/api/v1/chapters', methods=['GET'])
def api_chapters():
    exam = request.args.get('exam')
    subject = request.args.get('subject')
    db = get_db()
    query = "SELECT exam, subject, chapter, chapter_name, question_count FROM chapters WHERE 1=1"
    params = []
    if exam:
        query += " AND exam = ?"
        params.append(exam)
    if subject:
        query += " AND subject = ?"
        params.append(subject)
    query += " ORDER BY exam, subject, question_count DESC"
    rows = db.execute(query, params).fetchall()
    return jsonify({'chapters': [dict(r) for r in rows]})

@app.route('/api/v1/papers', methods=['GET'])
def api_papers():
    exam = request.args.get('exam')
    year = request.args.get('year')
    db = get_db()
    query = """
        SELECT exam, year, shift, paper_slug, details, count(*) as question_count
        FROM questions
        WHERE paper_slug IS NOT NULL AND paper_slug != ''
    """
    params = []
    if exam:
        query += " AND exam = ?"
        params.append(exam)
    if year:
        query += " AND year = ?"
        params.append(year)
    query += " GROUP BY paper_slug ORDER BY year DESC, details ASC"
    rows = db.execute(query, params).fetchall()
    return jsonify({'papers': [dict(r) for r in rows]})

@app.route('/api/v1/questions', methods=['GET'])
def api_questions():
    exam = request.args.get('exam')
    subject = request.args.get('subject')
    chapter = request.args.get('chapter')
    year = request.args.get('year')
    shift = request.args.get('shift')
    paper = request.args.get('paper')
    qtype = request.args.get('type')
    sort = request.args.get('sort', 'year_desc')
    page = max(1, request.args.get('page', 1, type=int))
    limit = min(100, max(1, request.args.get('limit', 20, type=int)))
    offset = (page - 1) * limit

    db = get_db()
    base_where = "WHERE 1=1"
    params = []
    if exam:
        base_where += " AND exam = ?"
        params.append(exam)
    if subject:
        base_where += " AND subject = ?"
        params.append(subject)
    if chapter:
        base_where += " AND chapter = ?"
        params.append(chapter)
    if year:
        base_where += " AND year = ?"
        params.append(year)
    if shift:
        base_where += " AND shift = ?"
        params.append(shift)
    if paper:
        base_where += " AND paper_slug = ?"
        params.append(paper)
    if qtype:
        base_where += " AND type = ?"
        params.append(qtype)

    total = db.execute(f"SELECT count(*) as c FROM questions {base_where}", params).fetchone()['c']

    order_by = "ORDER BY year ASC, id ASC" if sort == 'year_asc' else "ORDER BY year DESC, id ASC"

    query = f"""
        SELECT id, exam, subject, chapter, chapter_name, year, details, shift, paper_slug, type, question_text, images_json
        FROM questions
        {base_where}
        {order_by}
        LIMIT ? OFFSET ?
    """
    rows = db.execute(query, params + [limit, offset]).fetchall()

    questions = []
    for r in rows:
        d = dict(r)
        try:
            d['images'] = json.loads(d['images_json']) if d['images_json'] else []
        except Exception:
            d['images'] = []
        del d['images_json']
        questions.append(d)

    return jsonify({
        'total': total,
        'page': page,
        'limit': limit,
        'total_pages': (total + limit - 1) // limit if limit else 1,
        'questions': questions
    })

@app.route('/api/v1/questions/<q_id>', methods=['GET'])
def api_question_detail(q_id):
    db = get_db()
    row = db.execute("SELECT * FROM questions WHERE id = ?", (q_id,)).fetchone()
    if not row:
        return jsonify({'error': 'Question not found'}), 404
    d = dict(row)
    try:
        d['options'] = json.loads(d['options_json']) if d['options_json'] else []
    except Exception:
        d['options'] = []
    try:
        d['images'] = json.loads(d['images_json']) if d['images_json'] else []
    except Exception:
        d['images'] = []
    del d['options_json']
    del d['images_json']
    return jsonify(d)

@app.route('/api/v1/check-answer', methods=['POST'])
def api_check_answer():
    data = request.get_json(force=True, silent=True) or {}
    q_id = data.get('question_id')
    selected = str(data.get('selected_answer', '')).strip()

    if not q_id:
        return jsonify({'error': 'question_id is required'}), 400

    db = get_db()
    row = db.execute("SELECT id, correct_answer, type, solution_text, solution_html FROM questions WHERE id = ?", (q_id,)).fetchone()
    if not row:
        return jsonify({'error': 'Question not found'}), 404

    correct = (row['correct_answer'] or '').strip()
    is_correct = False
    if row['type'] == 'integer':
        try:
            is_correct = float(selected) == float(correct)
        except ValueError:
            is_correct = selected == correct
    else:
        is_correct = selected.upper() == correct.upper()

    return jsonify({
        'question_id': q_id,
        'is_correct': is_correct,
        'correct_answer': correct,
        'solution_text': row['solution_text'],
        'solution_html': row['solution_html']
    })

@app.route('/api/v1/search', methods=['GET'])
def api_search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'query': '', 'total': 0, 'results': []})

    db = get_db()
    clean_q = ''.join(c if c.isalnum() or c.isspace() else ' ' for c in query).strip()
    if not clean_q:
        return jsonify({'query': query, 'total': 0, 'results': []})

    fts_query = ' '.join(f'"{word}"' for word in clean_q.split())
    try:
        rows = db.execute("""
            SELECT q.id, q.exam, q.subject, q.chapter, q.chapter_name, q.year, q.details, q.shift, q.type, q.question_text
            FROM questions_fts f
            JOIN questions q ON q.id = f.id
            WHERE questions_fts MATCH ?
            LIMIT 50
        """, (fts_query,)).fetchall()
    except Exception:
        like_pattern = f"%{clean_q}%"
        rows = db.execute("""
            SELECT id, exam, subject, chapter, chapter_name, year, details, shift, type, question_text
            FROM questions
            WHERE question_text LIKE ? OR details LIKE ?
            LIMIT 50
        """, (like_pattern, like_pattern)).fetchall()

    return jsonify({
        'query': query,
        'total': len(rows),
        'results': [dict(r) for r in rows]
    })

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
