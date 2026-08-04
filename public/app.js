// Shared behavior across every page: nav dropdowns, scroll progress, reveal
// animations, ripple effect, back-to-top. Include after the page's own <script>
// or before, order doesn't matter, everything here is deferred to DOMContentLoaded.

const API_BASE = '/api';

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str == null ? '' : String(str);
    return div.innerHTML;
}

document.addEventListener('DOMContentLoaded', () => {
    // ---------------- Nav dropdowns ----------------
    document.querySelectorAll('.nav-dropdown').forEach((dropdown) => {
        const btn = dropdown.querySelector('.nav-dropdown-btn');
        if (!btn) return;
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const wasOpen = dropdown.classList.contains('open');
            document.querySelectorAll('.nav-dropdown.open').forEach((d) => d.classList.remove('open'));
            if (!wasOpen) dropdown.classList.add('open');
        });
    });
    document.addEventListener('click', () => {
        document.querySelectorAll('.nav-dropdown.open').forEach((d) => d.classList.remove('open'));
    });

    // ---------------- Ripple on buttons ----------------
    function attachRipple(btn) {
        btn.addEventListener('click', (e) => {
            const rect = btn.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const ripple = document.createElement('span');
            ripple.className = 'ripple';
            ripple.style.width = ripple.style.height = `${size}px`;
            ripple.style.left = `${e.clientX - rect.left - size / 2}px`;
            ripple.style.top = `${e.clientY - rect.top - size / 2}px`;
            ripple.style.background = btn.classList.contains('btn-secondary') || btn.classList.contains('btn-outline')
                ? 'rgba(15, 58, 125, 0.18)' : 'rgba(255, 255, 255, 0.5)';
            btn.appendChild(ripple);
            ripple.addEventListener('animationend', () => ripple.remove());
        });
    }
    function attachRippleToAll() {
        document.querySelectorAll('button, .btn').forEach((btn) => {
            if (!btn.dataset.rippleBound) { btn.dataset.rippleBound = '1'; attachRipple(btn); }
        });
    }
    attachRippleToAll();
    new MutationObserver(attachRippleToAll).observe(document.body, { childList: true, subtree: true });

    // ---------------- Scroll reveal ----------------
    const revealTargets = document.querySelectorAll('.card, .reveal-item, section > h2, section > .section-subtitle');
    revealTargets.forEach((el, i) => {
        el.classList.add('reveal');
        el.style.transitionDelay = `${(i % 6) * 0.07}s`;
    });
    const revealObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) { entry.target.classList.add('in-view'); revealObserver.unobserve(entry.target); }
        });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
    revealTargets.forEach((el) => revealObserver.observe(el));

    // ---------------- Scroll progress + nav shadow + back-to-top ----------------
    const scrollProgress = document.getElementById('scrollProgress');
    const mainNav = document.getElementById('mainNav');
    const backToTop = document.getElementById('backToTop');

    function onScroll() {
        const scrollTop = window.scrollY;
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        if (scrollProgress) scrollProgress.style.width = docHeight > 0 ? `${(scrollTop / docHeight) * 100}%` : '0%';
        if (mainNav) mainNav.classList.toggle('scrolled', scrollTop > 10);
        if (backToTop) backToTop.classList.toggle('visible', scrollTop > 500);
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    if (backToTop) backToTop.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));

    // ---------------- Populate the header industry dropdown (used on every page) ----------------
    const industryMenu = document.getElementById('navIndustryMenu');
    if (industryMenu) {
        fetch(`${API_BASE}/industries`).then((r) => r.json()).then((data) => {
            if (!data.ok) return;
            industryMenu.innerHTML = data.industries.map((i) =>
                `<a href="/assessment?industry=${i.id}">${escapeHtml(i.name)}</a>`
            ).join('') || '<span class="menu-group-label">No industries yet</span>';
        }).catch(() => {});
    }

    // ---------------- Animated counters ----------------
    // Usage: <span class="counter" data-target="82" data-suffix="%">0</span>
    const counters = document.querySelectorAll('.counter[data-target]');
    const counterObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            counterObserver.unobserve(entry.target);
            const el = entry.target;
            const target = parseFloat(el.dataset.target);
            const suffix = el.dataset.suffix || '';
            const decimals = el.dataset.decimals ? parseInt(el.dataset.decimals, 10) : 0;
            const duration = 1200;
            const start = performance.now();
            function tick(now) {
                const progress = Math.min(1, (now - start) / duration);
                const eased = 1 - Math.pow(1 - progress, 3);
                el.textContent = (target * eased).toFixed(decimals) + suffix;
                if (progress < 1) requestAnimationFrame(tick);
                else el.textContent = target.toFixed(decimals) + suffix;
            }
            requestAnimationFrame(tick);
        });
    }, { threshold: 0.4 });
    counters.forEach((el) => counterObserver.observe(el));

    // ---------------- Smooth accordion helper ----------------
    // Toggles max-height using the real scrollHeight so content of any length animates cleanly.
    window.toggleAccordion = function (bodyEl, open) {
        if (open) {
            bodyEl.style.maxHeight = bodyEl.scrollHeight + 'px';
        } else {
            bodyEl.style.maxHeight = '0px';
        }
    };

    // ---------------- Sticky in-page section nav ----------------
    const subnav = document.querySelector('.subnav');
    if (subnav) {
        const mainNavEl = document.getElementById('mainNav');
        function positionSubnav() {
            subnav.style.top = (mainNavEl ? mainNavEl.offsetHeight : 0) + 'px';
        }
        positionSubnav();
        window.addEventListener('resize', positionSubnav);

        const subnavLinks = subnav.querySelectorAll('a[href^="#"]');
        const subnavTargets = Array.from(subnavLinks)
            .map((a) => document.querySelector(a.getAttribute('href')))
            .filter(Boolean);
        const heroEl = document.querySelector('.hero');

        function onSubnavScroll() {
            const scrollTop = window.scrollY;
            subnav.classList.toggle('visible', heroEl ? scrollTop > heroEl.offsetHeight * 0.6 : scrollTop > 200);
            let activeIndex = -1;
            subnavTargets.forEach((section, i) => {
                if (section.getBoundingClientRect().top <= 140) activeIndex = i;
            });
            subnavLinks.forEach((a, i) => a.classList.toggle('active', i === activeIndex));
        }
        window.addEventListener('scroll', onSubnavScroll, { passive: true });
        onSubnavScroll();
    }
});
