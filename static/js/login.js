// ============================================
// 登录页逻辑
// ============================================

const API_BASE = '/api';

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('loginForm');
    const passwordInput = document.getElementById('password');
    const errorEl = document.getElementById('loginError');
    const submitBtn = form.querySelector('button[type="submit"]');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        errorEl.hidden = true;

        const password = passwordInput.value;
        submitBtn.disabled = true;
        submitBtn.textContent = '登录中...';

        try {
            const res = await fetch(`${API_BASE}/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password })
            });
            const data = await res.json();
            if (data.success) {
                window.location.href = '/';
            } else {
                errorEl.textContent = data.message || '登录失败';
                errorEl.hidden = false;
                submitBtn.disabled = false;
                submitBtn.textContent = '登录';
            }
        } catch (err) {
            errorEl.textContent = '无法连接到服务器';
            errorEl.hidden = false;
            submitBtn.disabled = false;
            submitBtn.textContent = '登录';
        }
    });
});
