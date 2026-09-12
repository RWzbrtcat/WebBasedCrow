// ============================================
// 站点背景图：加载背景 + 提供更换背景入口（由个性化下拉调用）
// ============================================
(function () {
    const API_BASE = '/api';
    const CACHE_KEY = 'blog:background';

    function applyBackground(url) {
        if (url) {
            document.body.style.backgroundImage = `url("${url}")`;
            document.body.style.backgroundSize = 'cover';
            document.body.style.backgroundPosition = 'center';
            document.body.style.backgroundAttachment = 'fixed';
        } else {
            document.body.style.backgroundImage = '';
        }
    }

    function cacheGet() {
        try { return localStorage.getItem(CACHE_KEY); } catch (e) { return null; }
    }

    function cacheSet(url) {
        try {
            if (url) localStorage.setItem(CACHE_KEY, url);
            else localStorage.removeItem(CACHE_KEY);
        } catch (e) {}
    }

    // 先用本地缓存同步应用背景，避免等待接口返回导致背景出现慢
    (function () {
        const cached = cacheGet();
        if (cached) applyBackground(cached);
    })();

    async function loadBackground() {
        try {
            const r = await fetch(`${API_BASE}/settings/background`);
            const data = await r.json();
            if (data && data.success) {
                const url = data.url || '';
                applyBackground(url);
                cacheSet(url);
            }
        } catch (e) {
            // 加载失败时保持默认背景
        }
    }

    function toast(message, type) {
        document.querySelectorAll('.bg-toast').forEach((t) => t.remove());
        const el = document.createElement('div');
        el.className = `bg-toast ${type}`;
        el.textContent = message;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 2500);
    }

    let fileInput = null;

    function ensureFileInput() {
        if (fileInput) return fileInput;
        fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.accept = 'image/*';
        fileInput.hidden = true;
        document.body.appendChild(fileInput);

        fileInput.addEventListener('change', async () => {
            const file = fileInput.files && fileInput.files[0];
            if (!file) return;
            try {
                const fd = new FormData();
                fd.append('image', file);
                const upRes = await fetch(`${API_BASE}/upload`, { method: 'POST', body: fd });
                const upData = await upRes.json();
                if (!upData.success) throw new Error(upData.message || '上传失败');

                const url = upData.url;
                const saveRes = await fetch(`${API_BASE}/settings/background`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url })
                });
                const saveData = await saveRes.json();
                if (!saveData.success) throw new Error(saveData.message || '保存失败');

                applyBackground(url);
                cacheSet(url);
                toast('背景已更新', 'success');
            } catch (e) {
                toast(e.message || '更换背景失败', 'error');
            } finally {
                fileInput.value = '';
            }
        });

        return fileInput;
    }

    // 暴露给个性化下拉调用
    window.__blogPersonalize = window.__blogPersonalize || {};
    window.__blogPersonalize.changeBackground = function () {
        ensureFileInput().click();
    };

    document.addEventListener('DOMContentLoaded', async () => {
        loadBackground();
    });
})();
