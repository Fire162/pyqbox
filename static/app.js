// Pyqbox Interactive Practice Client Engine

// 0. Auto-render Math with KaTeX
window.renderAllMath = function() {
  if (typeof renderMathInElement === 'function') {
    renderMathInElement(document.body, {
      delimiters: [
        { left: '$$', right: '$$', display: true },
        { left: '$', right: '$', display: false },
        { left: '\\(', right: '\\)', display: false },
        { left: '\\[', right: '\\]', display: true }
      ],
      ignoredClasses: ["katex"],
      throwOnError: false
    });
    return true;
  }
  return false;
};

// Immediately attempt rendering
if (!window.renderAllMath()) {
  var katexTimer = setInterval(function() {
    if (window.renderAllMath()) {
      clearInterval(katexTimer);
    }
  }, 25);
  setTimeout(function() { clearInterval(katexTimer); }, 5000);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', window.renderAllMath);
} else {
  window.renderAllMath();
}
window.addEventListener('load', window.renderAllMath);

document.addEventListener('DOMContentLoaded', function() {

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
  const sbCloseBtn = document.getElementById('sb-close-btn');
  const sidebarBackdrop = document.getElementById('sidebar-backdrop');
  const sidebar = document.getElementById('sidebar');

  function openSidebar() {
    if (!sidebar) return;
    sidebar.classList.add('is-open');
    if (sidebarBackdrop) sidebarBackdrop.classList.add('is-open');
    document.body.classList.add('sidebar-locked');
  }

  function closeSidebar() {
    if (!sidebar) return;
    sidebar.classList.remove('is-open');
    if (sidebarBackdrop) sidebarBackdrop.classList.remove('is-open');
    document.body.classList.remove('sidebar-locked');
  }

  if (mobileMenuBtn) {
    mobileMenuBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      if (sidebar && sidebar.classList.contains('is-open')) {
        closeSidebar();
      } else {
        openSidebar();
      }
    });
  }

  if (sbCloseBtn) {
    sbCloseBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      closeSidebar();
    });
  }

  if (sidebarBackdrop) {
    sidebarBackdrop.addEventListener('click', function() {
      closeSidebar();
    });
  }

  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && sidebar && sidebar.classList.contains('is-open')) {
      closeSidebar();
    }
  });

  if (sidebar) {
    sidebar.querySelectorAll('a').forEach(function(link) {
      link.addEventListener('click', function() {
        if (window.innerWidth <= 900) {
          closeSidebar();
        }
      });
    });
  }

  if (sbToggle && sidebar) {
    sbToggle.addEventListener('click', function() {
      sidebar.classList.toggle('is-collapsed');
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
