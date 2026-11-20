(function () {
    const STORAGE_KEY = 'pacTheme';

    function applyTheme(theme) {
        const isDark = theme === 'dark';
        document.documentElement.classList.toggle('dark', isDark);
        document.body.classList.toggle('dark-theme', isDark);
        const btn = document.getElementById('theme-toggle');
        if (btn) {
            btn.textContent = isDark ? '☀️' : '🌙';
            btn.setAttribute('aria-label', isDark ? 'Passa al tema chiaro' : 'Passa al tema scuro');
            btn.setAttribute('title', isDark ? 'Tema chiaro' : 'Tema scuro');
        }
        window.dispatchEvent(new CustomEvent('pacThemeChange', { detail: { theme } }));
    }

    document.addEventListener('DOMContentLoaded', function () {
        const saved = localStorage.getItem(STORAGE_KEY) || 'light';
        applyTheme(saved);

        const btn = document.getElementById('theme-toggle');
        if (btn) {
            btn.addEventListener('click', function () {
                const next = document.body.classList.contains('dark-theme') ? 'light' : 'dark';
                localStorage.setItem(STORAGE_KEY, next);
                applyTheme(next);
            });
        }

        document.querySelectorAll('.alert-close').forEach(function (closeBtn) {
            closeBtn.addEventListener('click', function () {
                const alert = closeBtn.closest('.alert');
                if (alert) alert.remove();
            });
        });
    });
})();
