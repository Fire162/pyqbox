// Pyqbox Interactive Practice Client Engine

document.addEventListener('DOMContentLoaded', function() {
  // 0. Auto-render Math with KaTeX
  function initKaTeX() {
    if (typeof renderMathInElement === 'function') {
      renderMathInElement(document.body, {
        delimiters: [
          { left: '$$', right: '$$', display: true },
          { left: '$', right: '$', display: false },
          { left: '\\(', right: '\\)', display: false },
          { left: '\\[', right: '\\]', display: true }
        ],
        throwOnError: false
      });
    }
  }
  initKaTeX();
  window.addEventListener('load', initKaTeX);

  // 1. Theme Toggle
  const themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) {
    themeBtn.addEventListener('click', function() {
      const current = document.documentElement.getAttribute('data-theme') || 'light';
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('pq_theme', next);
    });
  }

  // 2. Mobile / Desktop Sidebar Toggle
  const sbToggle = document.getElementById('sb-toggle');
  const mobileMenuBtn = document.getElementById('mobile-menu-btn');
  const sidebar = document.getElementById('sidebar');

  if (sbToggle && sidebar) {
    sbToggle.addEventListener('click', function() {
      sidebar.classList.toggle('is-collapsed');
    });
  }

  if (mobileMenuBtn && sidebar) {
    mobileMenuBtn.addEventListener('click', function() {
      sidebar.classList.toggle('is-open');
    });
  }

  // 3. Interactive MCQ Option Click Check
  document.querySelectorAll('.q-card').forEach(function(card) {
    const qIndex = card.getAttribute('data-index');
    const correctKey = (card.getAttribute('data-key') || '').trim();
    const qType = card.getAttribute('data-type');
    const paletteBtn = document.getElementById('pal-' + qIndex);

    // MCQ Options
    const optButtons = card.querySelectorAll('.opt-btn');
    optButtons.forEach(function(btn) {
      btn.addEventListener('click', function() {
        if (card.getAttribute('data-answered') === 'true') return;

        card.setAttribute('data-answered', 'true');
        const selectedKey = (btn.getAttribute('data-key') || '').trim();

        if (selectedKey.toUpperCase() === correctKey.toUpperCase()) {
          btn.classList.add('is-correct');
          if (paletteBtn) paletteBtn.className = 'q-palette-btn is-answered-correct';
        } else {
          btn.classList.add('is-wrong');
          if (paletteBtn) paletteBtn.className = 'q-palette-btn is-answered-wrong';

          // Highlight the actual correct option
          optButtons.forEach(function(otherBtn) {
            if ((otherBtn.getAttribute('data-key') || '').trim().toUpperCase() === correctKey.toUpperCase()) {
              otherBtn.classList.add('is-correct');
            }
          });
        }

        // Auto open solution
        const details = card.querySelector('.soln-accordion');
        if (details) details.open = true;
      });
    });

    // Numerical / Integer Input
    const intSubmit = card.querySelector('.integer-submit-btn');
    const intInput = card.querySelector('.integer-input');
    const intFeedback = card.querySelector('.integer-feedback');

    if (intSubmit && intInput) {
      intSubmit.addEventListener('click', function() {
        if (card.getAttribute('data-answered') === 'true') return;

        const val = intInput.value.trim();
        if (!val) return;

        card.setAttribute('data-answered', 'true');
        if (val === correctKey) {
          intFeedback.textContent = '✓ Correct (' + correctKey + ')';
          intFeedback.style.color = 'var(--correct-green)';
          if (paletteBtn) paletteBtn.className = 'q-palette-btn is-answered-correct';
        } else {
          intFeedback.textContent = '✗ Incorrect. Correct Answer: ' + correctKey;
          intFeedback.style.color = 'var(--wrong-red)';
          if (paletteBtn) paletteBtn.className = 'q-palette-btn is-answered-wrong';
        }

        // Auto open solution
        const details = card.querySelector('.soln-accordion');
        if (details) details.open = true;
      });
    }
  });

  // 4. Live Filtering (Year & Question Type)
  const filterYear = document.getElementById('filter-year');
  const filterType = document.getElementById('filter-type');

  function applyFilters() {
    const selectedYear = filterYear ? filterYear.value : 'all';
    const selectedType = filterType ? filterType.value : 'all';

    document.querySelectorAll('.q-card').forEach(function(card) {
      const qYear = card.getAttribute('data-year') || '';
      const qType = card.getAttribute('data-type') || '';

      const matchYear = (selectedYear === 'all' || qYear === selectedYear);
      const matchType = (selectedType === 'all' || qType === selectedType);

      if (matchYear && matchType) {
        card.style.display = 'block';
      } else {
        card.style.display = 'none';
      }
    });
  }

  if (filterYear) filterYear.addEventListener('change', applyFilters);
  if (filterType) filterType.addEventListener('change', applyFilters);
});
