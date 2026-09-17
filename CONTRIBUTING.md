# Contributing to Pyqbox

Thank you for your interest in contributing to Pyqbox! This project is an open learning resource designed to provide fast, reliable, local-first access to previous year questions for Indian competitive exams.

---

## Code of Conduct

* Be respectful, constructive, and helpful to fellow contributors.
* Keep questions and issue reports focused, actionable, and specific.

---

## Development Setup

1. **Clone the Repository**:
   ```bash
   git clone <repo-url>
   cd pyqs
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Database Setup**:
   The SQLite database resides at `pyqbox_data/pyqs.db`. To rebuild from JSONL datasets:
   ```bash
   python3 build_db.py
   ```

4. **Run the Development Server**:
   ```bash
   python3 app.py --port 5050
   ```
   Open `http://localhost:5050` in your browser.

---

## Coding Standards

* **Language**: Python 3.12+, clean standard library usage.
* **No Unnecessary Dependencies**: Prefer built-in standard library utilities and existing packages over new external dependencies.
* **Self-Hosted Assets**: Never add external CDN `<script>` or `<link>` tags. All JS, CSS, and fonts must be bundled locally in `/static/`.
* **Database Queries**: Always use parameterized SQL queries (`?` placeholders) to prevent SQL injection and leverage SQLite prepared statements.
* **Confidentiality**: Never hardcode secrets, API keys, or IP addresses in source code, configuration files, or documentation.

---

## Submitting Pull Requests

1. Check existing issues and PRs to avoid duplication.
2. Create a dedicated feature or bugfix branch.
3. Make focused, minimal changes that solve the issue without touching unrelated files.
4. Test changes locally and verify responsive layout across both light and dark themes.
5. Submit a pull request with a concise, human-written description of the changes.
