// ============================================
// 站点主题配色：加载主题 + 提供更换样式入口（由个性化下拉调用）
// ============================================
(function () {
    const API_BASE = '/api';
    const CACHE_KEY = 'blog:theme';

    // 预设配色方案：每套同时定义导航栏与内容主题的颜色
    const PRESETS = [
        { id: 'orange', name: '橙色', colors: { nav_bg: '#fdf6ee', card_bg: '#fff7ed', card_border: '#fed7aa', accent: '#c2410c', accent_dark: '#9a3412', accent_soft: '#fff1e6' } },
        { id: 'blue', name: '蓝色', colors: { nav_bg: '#eff6ff', card_bg: '#eff6ff', card_border: '#bfdbfe', accent: '#1d4ed8', accent_dark: '#1e40af', accent_soft: '#dbeafe' } },
        { id: 'green', name: '绿色', colors: { nav_bg: '#ecfdf5', card_bg: '#f0fdf4', card_border: '#a7f3d0', accent: '#15803d', accent_dark: '#166534', accent_soft: '#dcfce7' } },
        { id: 'purple', name: '紫色', colors: { nav_bg: '#faf5ff', card_bg: '#faf5ff', card_border: '#e9d5ff', accent: '#7e22ce', accent_dark: '#6b21a8', accent_soft: '#f3e8ff' } },
        { id: 'rose', name: '粉色', colors: { nav_bg: '#fff1f2', card_bg: '#fff1f2', card_border: '#fecdd3', accent: '#be123c', accent_dark: '#9f1239', accent_soft: '#ffe4e6' } },
        { id: 'slate', name: '灰蓝', colors: { nav_bg: '#f8fafc', card_bg: '#f8fafc', card_border: '#e2e8f0', accent: '#475569', accent_dark: '#334155', accent_soft: '#f1f5f9' } }
    ];

    // 主题字段 -> CSS 变量映射
    const VAR_MAP = {
        nav_bg: '--nav-bg',
        card_bg: '--card-bg',
        card_border: '--card-border',
        accent: '--accent',
        accent_dark: '--accent-dark',
        accent_soft: '--accent-soft'
    };

    // 取色条展示顺序（从左到右）
    const SWATCH_ORDER = ['accent', 'card_border', 'card_bg', 'nav_bg'];

    function applyTheme(colors) {
        const root = document.documentElement;
        for (const key of Object.keys(VAR_MAP)) {
            if (colors && colors[key]) {
                root.style.setProperty(VAR_MAP[key], colors[key]);
            }
        }
    }

    function cacheSetTheme(json) {
        try {
            if (json) localStorage.setItem(CACHE_KEY, json);
            else localStorage.removeItem(CACHE_KEY);
        } catch (e) {}
    }

    async function loadTheme() {
        try {
            const r = await fetch(`${API_BASE}/settings/theme`);
            const data = await r.json();
            if (data && data.success && data.theme) {
                applyTheme(JSON.parse(data.theme));
                cacheSetTheme(data.theme);
            }
        } catch (e) {
            // 加载失败时保持默认配色
        }
    }

    // 先用本地缓存同步应用主题，避免等待接口返回导致配色闪动
    (function () {
        try {
            const cached = localStorage.getItem(CACHE_KEY);
            if (cached) applyTheme(JSON.parse(cached));
        } catch (e) {}
    })();

    function toast(message, type) {
        document.querySelectorAll('.bg-toast').forEach((t) => t.remove());
        const el = document.createElement('div');
        el.className = `bg-toast ${type}`;
        el.textContent = message;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 2500);
    }

    function currentThemeId() {
        // 将当前 CSS 变量值与预设比对，命中则返回其 id（用于高亮）
        const cs = getComputedStyle(document.documentElement);
        const pick = (v) => (cs.getPropertyValue(v) || '').trim();
        for (const p of PRESETS) {
            let match = true;
            for (const key of Object.keys(VAR_MAP)) {
                if (pick(VAR_MAP[key]).toLowerCase() !== p.colors[key].toLowerCase()) {
                    match = false;
                    break;
                }
            }
            if (match) return p.id;
        }
        return null;
    }

    function buildModal() {
        let modal = document.getElementById('themeModal');
        if (modal) return modal;

        const overlay = document.createElement('div');
        overlay.className = 'image-modal-overlay';
        overlay.id = 'themeModal';
        overlay.hidden = true;

        const dialog = document.createElement('div');
        dialog.className = 'image-modal theme-modal';

        const header = document.createElement('div');
        header.className = 'image-modal-header';
        const title = document.createElement('h3');
        title.textContent = '更换样式';
        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'image-modal-close';
        close.setAttribute('aria-label', '关闭');
        close.innerHTML = '&times;';
        header.appendChild(title);
        header.appendChild(close);

        const body = document.createElement('div');
        body.className = 'image-modal-body';
        const grid = document.createElement('div');
        grid.className = 'theme-preset-grid';

        for (const p of PRESETS) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'theme-preset';
            btn.dataset.id = p.id;

            const swatch = document.createElement('span');
            swatch.className = 'theme-swatch';
            for (const key of SWATCH_ORDER) {
                const dot = document.createElement('span');
                dot.style.background = p.colors[key];
                swatch.appendChild(dot);
            }

            const name = document.createElement('span');
            name.className = 'theme-name';
            name.textContent = p.name;

            btn.appendChild(swatch);
            btn.appendChild(name);
            grid.appendChild(btn);
        }

        body.appendChild(grid);
        dialog.appendChild(header);
        dialog.appendChild(body);
        overlay.appendChild(dialog);
        document.body.appendChild(overlay);

        close.addEventListener('click', () => { overlay.hidden = true; });
        overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.hidden = true; });

        return overlay;
    }

    function highlightActive() {
        const id = currentThemeId();
        document.querySelectorAll('.theme-preset').forEach((btn) => {
            btn.classList.toggle('active', btn.dataset.id === id);
        });
    }

    async function saveTheme(preset) {
        const colors = preset.colors;
        try {
            const r = await fetch(`${API_BASE}/settings/theme`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(colors)
            });
            const data = await r.json();
            if (!data.success) throw new Error(data.message || '保存失败');
            applyTheme(colors);
            cacheSetTheme(JSON.stringify(colors));
            highlightActive();
            toast(`已切换为「${preset.name}」主题`, 'success');
        } catch (e) {
            toast(e.message || '更换样式失败', 'error');
        }
    }

    function openThemeModal() {
        const modal = buildModal();
        highlightActive();
        modal.hidden = false;
        modal.querySelectorAll('.theme-preset').forEach((presetBtn) => {
            presetBtn.onclick = () => {
                const preset = PRESETS.find((p) => p.id === presetBtn.dataset.id);
                if (preset) saveTheme(preset);
            };
        });
    }

    // 暴露给个性化下拉调用
    window.__blogPersonalize = window.__blogPersonalize || {};
    window.__blogPersonalize.changeTheme = openThemeModal;

    function injectPersonalize() {
        const nav = document.querySelector('.nav');
        if (!nav) return;

        const wrap = document.createElement('div');
        wrap.className = 'nav-dropdown';

        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'personalize-btn nav-dropdown-toggle';
        toggle.innerHTML = '个性化<span class="nav-dropdown-caret"></span>';

        const menu = document.createElement('div');
        menu.className = 'nav-dropdown-menu';
        menu.hidden = true;

        const bgItem = document.createElement('button');
        bgItem.type = 'button';
        bgItem.className = 'nav-dropdown-item';
        bgItem.textContent = '更换背景';

        const themeItem = document.createElement('button');
        themeItem.type = 'button';
        themeItem.className = 'nav-dropdown-item';
        themeItem.textContent = '更换样式';

        menu.appendChild(bgItem);
        menu.appendChild(themeItem);
        wrap.appendChild(toggle);
        wrap.appendChild(menu);
        nav.appendChild(wrap);

        function close() {
            menu.hidden = true;
            wrap.classList.remove('open');
        }

        toggle.addEventListener('click', (e) => {
            e.stopPropagation();
            if (menu.hidden) {
                menu.hidden = false;
                wrap.classList.add('open');
            } else {
                close();
            }
        });

        document.addEventListener('click', (e) => {
            if (!wrap.contains(e.target)) close();
        });

        bgItem.addEventListener('click', () => {
            close();
            const fn = window.__blogPersonalize && window.__blogPersonalize.changeBackground;
            if (fn) fn();
        });

        themeItem.addEventListener('click', () => {
            close();
            openThemeModal();
        });
    }

    document.addEventListener('DOMContentLoaded', async () => {
        loadTheme();
        try {
            const r = await fetch(`${API_BASE}/auth`);
            const data = await r.json();
            if (data && data.authed) injectPersonalize();
        } catch (e) {
            // 未登录时不显示个性化入口
        }
    });
})();
