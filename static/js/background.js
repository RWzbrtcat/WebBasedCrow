// ============================================
// 站点背景图：加载背景 + 登录后提供更换入口
// ============================================
(function () {
    const API_BASE = '/api';

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

    async function loadBackground() {
        try {
            const r = await fetch(`${API_BASE}/settings/background`);
            const data = await r.json();
            if (data && data.success && data.url) {
                applyBackground(data.url);
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

    function injectButton() {
        const nav = document.querySelector('.nav');
        if (!nav) return;

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'bg-change-btn';
        btn.textContent = '更换背景';

        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.accept = 'image/*';
        fileInput.hidden = true;

        nav.appendChild(btn);
        nav.appendChild(fileInput);

        btn.addEventListener('click', () => fileInput.click());

        fileInput.addEventListener('change', async () => {
            const file = fileInput.files && fileInput.files[0];
            if (!file) return;

            btn.disabled = true;
            btn.textContent = '上传中...';
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
                toast('背景已更新', 'success');
            } catch (e) {
                toast(e.message || '更换背景失败', 'error');
            } finally {
                btn.disabled = false;
                btn.textContent = '更换背景';
                fileInput.value = '';
            }
        });
    }

    document.addEventListener('DOMContentLoaded', async () => {
        loadBackground();
        try {
            const r = await fetch(`${API_BASE}/auth`);
            const data = await r.json();
            if (data && data.authed) injectButton();
        } catch (e) {
            // 未登录时不显示更换入口
        }
    });
})();
