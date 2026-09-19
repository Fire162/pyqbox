# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.10.0] - 2026-09-19 22:48 IST

### Fixed
* Fixed horizontal overflows and viewport clipping across mobile (320px–480px), tablet (768px–850px), laptop, and desktop ([#3](https://github.com/Fire162/pyqbox/issues/3)).
* Replaced hardcoded 480px minimum chart grid on the Analysis page with responsive `.analysis-charts-grid`.
* Added responsive topbar labels with mobile abbreviation for CBT link and dot-only status pill below 640px.
* Added word-wrapping and container overflow protection for API curl samples (`.api-curl-box`).
* Made navigation buttons (`.pnav`), mode switcher tabs (`.tabs`), and exam grids gracefully scale and wrap on small viewports.
* Verified 0px overflow across 81 automated tests with Playwright.

## [1.9.0] - 2026-09-19 22:36 IST

### Fixed
* Fixed empty mobile sidebar drawer when clicking the hamburger button on screens below 900px by overriding legacy `.sb-section { display: none }` rule ([#1](https://github.com/Fire162/pyqbox/issues/1), [#2](https://github.com/Fire162/pyqbox/pull/2)).
* Added a backdrop overlay (`.sidebar-backdrop`) with tap-to-dismiss behavior.
* Added a dedicated close (`✕`) button and `Escape` key handler to dismiss the drawer.
* Fixed body scrolling when the mobile drawer is open.

## [1.8.0] - 2026-09-17 22:15 IST

### Added
* Deployed **Gunicorn 23.0 WSGI server** with 2 worker processes and 8 threads (`gthread`), backed by a 2,048-connection kernel backlog, replacing the single-threaded development server.
* Added covering database index `idx_questions_chapter_order` on `questions(exam, subject, chapter, year DESC, id ASC)` in SQLite.
* Warmed and primed all **22,359 individual question pages** across JEE Main, JEE Advanced, and NEET UG directly into Cloudflare 30-Day Edge Cache with 0 errors.

### Changed
* Optimized `question_detail_view` in `app.py` to query using `LIMIT 1 OFFSET (q_index - 1)`, reducing single question query execution from 149.5ms to 4.9ms (30x speedup) and cutting memory usage by 95%.

## [1.7.0] - 2026-09-17 21:25 IST

### Added
* Deployed 30-day (1-month) Cloudflare Edge Caching rule (`edge_ttl: 2592000`) for all historical PYQ pages with zero-downtime stale fallback (`serve_stale: true`).
* Built multithreaded Cloudflare cache warmer script (`scripts/warm_cache.py`) concurrently priming all 551 chapter and shift URLs.

### Changed
* Updated `Cache-Control` in `app.py` to `public, max-age=3600, s-maxage=2592000, stale-while-revalidate=604800` across all HTML pages, sitemaps, and REST APIs.

## [1.6.0] - 2026-09-17 21:10 IST

### Fixed
* Fixed search results opening the entire chapter instead of the specific question by replacing missing `#q-` fragment links with direct question permalinks (`/question/<q_id>/`).
* Resolved navigation so clicking any search result now immediately lands on the dedicated question page with options, KaTeX math typesetting, and worked step-by-step solution.

### Added
* Redesigned search results with Wegenz Slate design system cards, direct `⚡ View Question & Solution →` primary action, and secondary `Browse Chapter →` link.
* Added schema.org `SearchAction` structured data to enable Google Sitelinks Searchbox eligibility.

## [1.5.0] - 2026-09-17 20:56 IST

### Changed
* Refined reciprocal cross-navigation to emphasize `wegenz.in` as the primary engine for **Sample Questions, Infinite Practice Drills, Challenge Codes & CBT Mocks**.
* Updated sidebar footer link to `"SAMPLE QUESTIONS & MOCKS" -> Wegenz Practice [MOCKS]`.
* Updated topbar navigation pill to `"⚡ Sample Questions & Mocks (Wegenz)"`.
* Updated hero and chapter-level banners with clear positioning: PYQBox focuses strictly on 100% official PYQs & shifts, while Wegenz hosts 170k+ sample questions and timed CBT test simulations.

## [1.4.0] - 2026-09-17 20:45 IST

### Added
* Full design system integration matching **Wegenz Practice** (`wegenz.in`): Deep Obsidian (`#020617`), Slate-900 (`#0f172a`), Slate-800 (`#1e293b`), and Wegenz Indigo (`#6366f1` / `#4f46e5`).
* Integrated official Wegenz brand assets (`wegenz-primary-mark-96.webp`, `wegenz-primary-mark-192.webp`, `favicon.svg`, `wegenz-wordmark.jpg`) in the sidebar, metadata, and browser favicon.
* Added live pulsing operational status pill (`● All Systems Operational`) to topbar with expanding CSS pulse animation.
* Added Wegenz gradient hero banner (`from-slate-900 via-slate-950 to-indigo-950/40`) with 3D glowing squircle graphic and feature badge chip.
* Modernized exam cards into glassmorphic containers with rounded pill badges and quick-action chips (`📚 Chapters`, `📝 Shifts`, `📊 Trends`).
* High-contrast KaTeX formulas rendering in dark mode (`.dark .katex { color: #f1f5f9; }`) and rounded option cards with instant feedback states.

### Changed
* Replaced old Notion-inspired palette and rigid 4px corners with smooth modern radii (10px–24px) and translucent card borders across all templates.
* Bumped asset cache-busting strings to `?v=4` across stylesheets and scripts.

## [1.3.0] - 2026-09-17 20:25 IST

### Added
* Dynamic `/sitemap.xml` route indexing 551 distinct URLs (270 chapters, 270 official exam shift papers, and core landing portals) with 24-hour public edge caching.
* Dynamic `/robots.txt` route referencing sitemap URL and permitting complete crawler indexing.
* Dynamic OpenGraph and Twitter card metadata for social cards and rich search previews.
* Schema.org `WebSite` and `EducationalOrganization` JSON-LD structured markup in `templates/base.html`.
* Reciprocal cross-linking banners and sidebar links to the timed CBT testing engine on `https://wegenz.in/`.
* Submitted `https://pyqs.wegenz.in/sitemap.xml` and submitted priority indexing request to Google Search Console via BrowserPilot.

### Changed
* Optimized dynamic `<title>` and `<meta name="description">` tags across chapter, exam, shift paper, and question templates for high-intent search queries (`"jee pyqs"`, `"jee practice"`, `"neet previous year questions"`).
* Added crawlable semantic SEO introduction and FAQ section to `templates/index.html`.

## [1.2.0] - 2026-09-13 23:25 IST

### Added
* Deployed production endpoint to `https://pyqs.wegenz.in/` behind Cloudflare Edge Proxy with origin IP shielding and HTTP/3.
* Implemented Cloudflare Global Edge Caching with Smart Tiered Cache and `cache_everything` page rule.
* Added multi-year aggregation support to Exam Analytics & Research Lab with interactive checkbox matrix, quick presets, and dismissible year pill tags.
* Added visual accent color-coding for selected years in the historical question volume trend bar chart.
* Created composite covering indexes `idx_questions_analytics_covering` and `idx_questions_analytics_type` in SQLite for sub-10ms queries.
* Added top mode switcher tabs (`📚 Chapter-wise`, `📝 Paper & Shift-wise`, `📊 Research & Trends`) to exam and paper landing pages.
* Added quick-action navigation chips to homepage exam cards.
* Registered persistent process management in Fire PM (`fire-pyqs-app.service`) with auto-restart and boot startup.

### Changed
* Replaced temporary `no-cache` header with tiered `Cache-Control` policies (1-year immutable static assets, 30-day diagrams, 1-day edge cache for questions and analytics).
* Updated chapter practice views to accept multi-year filter query parameters.

### Fixed
* Fixed math and KaTeX options rendering by storing server-rendered KaTeX HTML directly in `options_json` across all 270 official papers (22,532 questions).
* Fixed `HEAD` request cache-control handling to ensure health probes and edge CDN correctly receive public cache headers.
* Fixed numeric option serif typography alignment with `.mn` font styling.

## [1.1.0] - 2026-09-13 18:30 IST

### Added
* Official paper & shift practice simulation for all 270 papers across JEE Main, JEE Advanced, and NEET UG.
* Full-text keyword search API endpoint (`/api/v1/search`) backed by SQLite FTS5.
* REST API endpoints (`/api/v1/exams`, `/api/v1/chapters`, `/api/v1/papers`, `/api/v1/questions`).

## [1.0.0] - 2026-09-12 14:00 IST

### Added
* Initial release of Pyqbox practice portal with 22,359 competitive exam questions.
* Chapter-wise question navigation with worked solutions and local diagrams.
* Dark / light mode UI toggle with zero client-side tracking.
