// ===== Mobile Sidebar Toggle =====
document.addEventListener('DOMContentLoaded', function() {
    // Create a hamburger menu button for mobile
    const sidebar = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');
    const wrapper = document.querySelector('.wrapper');

    if (window.innerWidth <= 768) {
        sidebar.style.display = 'none';
        const toggleBtn = document.createElement('button');
        toggleBtn.innerHTML = '☰';
        toggleBtn.className = 'hamburger';
        toggleBtn.style.cssText = `
            position: fixed; top: 10px; left: 10px; z-index: 1000;
            background: #0f172a; color: white; border: none;
            padding: 8px 12px; border-radius: 8px; font-size: 1.5rem;
            cursor: pointer;
        `;
        document.body.prepend(toggleBtn);

        toggleBtn.addEventListener('click', function() {
            if (sidebar.style.display === 'none' || sidebar.style.display === '') {
                sidebar.style.display = 'block';
                sidebar.style.position = 'fixed';
                sidebar.style.width = '280px';
                sidebar.style.height = '100vh';
                sidebar.style.top = '0';
                sidebar.style.left = '0';
                sidebar.style.zIndex = '999';
                // Add overlay
                const overlay = document.createElement('div');
                overlay.id = 'sidebar-overlay';
                overlay.style.cssText = `
                    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                    background: rgba(0,0,0,0.5); z-index: 998;
                `;
                document.body.appendChild(overlay);
                overlay.addEventListener('click', function() {
                    sidebar.style.display = 'none';
                    overlay.remove();
                });
            } else {
                sidebar.style.display = 'none';
                const overlay = document.getElementById('sidebar-overlay');
                if (overlay) overlay.remove();
            }
        });
    }

    // ===== Auto-dismiss alerts after 5 seconds =====
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.5s';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        }, 5000);
    });

    // ===== Form validation helpers =====
    const validationForms = document.querySelectorAll('.form');
    validationForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const required = this.querySelectorAll('[required]');
            let valid = true;
            required.forEach(field => {
                if (!field.value.trim()) {
                    field.style.borderColor = '#ef4444';
                    valid = false;
                } else {
                    field.style.borderColor = '';
                }
            });
            if (!valid) {
                e.preventDefault();
                alert('Please fill all required fields.');
            }
        });
    });

    // ===== Loading State Helper =====
    window.showLoading = function(buttonElement, message = 'Processing...') {
        const originalText = buttonElement.innerHTML;
        buttonElement.innerHTML = `
            <span class="loading-text">${message}</span>
            <span class="loading-spinner"></span>
        `;
        buttonElement.disabled = true;
        buttonElement.originalText = originalText;
        return function hideLoading() {
            buttonElement.innerHTML = originalText;
            buttonElement.disabled = false;
        };
    };

    // ===== Form Submission Loading States =====
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            // Show loading on submit buttons
            const submitButtons = this.querySelectorAll('button[type="submit"], input[type="submit"]');
            const hideLoaders = [];

            submitButtons.forEach(button => {
                if (!button.disabled) { // Only if not already disabled by validation
                    const hideLoader = showLoading(button, 'Working...');
                    hideLoaders.push(hideLoader);
                }
            });

            // Hide loaders after a short delay if form submission fails
            // (Success case will page redirect, failure case will stay on same page)
            setTimeout(() => {
                hideLoaders.forEach(hideLoader => hideLoader());
            }, 10000); // 10 second timeout
        });
    });

    // ===== Theme Toggle Initialization =====
    const savedTheme = localStorage.getItem('theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    const htmlElement = document.documentElement;
    htmlElement.setAttribute('data-theme', savedTheme);

    // Set initial button icon
    const toggleBtn = document.getElementById('theme-toggle-btn');
    if (toggleBtn) {
        const updateThemeButton = () => {
            const currentTheme = htmlElement.getAttribute('data-theme');
            toggleBtn.innerHTML = currentTheme === 'dark' ? '🌙/☀️' : '☀️/🌙';
        };
        updateThemeButton();
        toggleBtn.addEventListener('click', function() {
            const nextTheme = htmlElement.getAttribute('data-theme') === 'dark'
                ? 'light'
                : 'dark';
            htmlElement.setAttribute('data-theme', nextTheme);
            localStorage.setItem('theme', nextTheme);
            updateThemeButton();
        });
    }
});