// ============================================
// 登录页逻辑
// ============================================

const API_BASE = '/api';
const EMAIL_DOMAIN = '@lazycat.com';

// 账号只填前缀，自动补全为 @lazycat.com；
// 若填写的是完整邮箱（如历史账号 admin@localhost），则原样使用。
function normalizeAccount(raw) {
    const value = String(raw || '').trim();
    if (!value) return '';
    if (value.indexOf('@') !== -1) return value;
    return value.replace(/\s+/g, '') + EMAIL_DOMAIN;
}

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('loginForm');
    const emailInput = document.getElementById('emailPrefix');
    const passwordInput = document.getElementById('password');
    const errorEl = document.getElementById('loginError');
    const submitBtn = form.querySelector('button[type="submit"]');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        errorEl.hidden = true;

        const email = normalizeAccount(emailInput.value);
        const password = passwordInput.value;

        if (!email || !password) {
            errorEl.textContent = '请输入账号和密码';
            errorEl.hidden = false;
            return;
        }

        submitBtn.disabled = true;
        submitBtn.textContent = '登录中...';

        try {
            const res = await fetch(`${API_BASE}/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
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
            errorEl.textContent = '网络连接失败，请检查网络后重试';
            errorEl.hidden = false;
            submitBtn.disabled = false;
            submitBtn.textContent = '登录';
        }
    });
});
