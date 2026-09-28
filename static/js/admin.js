// ============================================
// 管理员管理页逻辑（仅主管理员可访问）
// ============================================

const API_BASE = '/api';
const EMAIL_DOMAIN = '@lazycat.com';

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('adminForm');
    const emailInput = document.getElementById('emailPrefix');
    const passwordInput = document.getElementById('password');
    const errorEl = document.getElementById('adminError');
    const listEl = document.getElementById('adminList');
    const countEl = document.getElementById('adminCount');
    const toggleEl = document.getElementById('adminToggle');

    // 已有管理员列表默认折叠，点击「查看已有管理员」展开 / 收起
    toggleEl.addEventListener('click', () => {
        const expanded = toggleEl.getAttribute('aria-expanded') === 'true';
        toggleEl.setAttribute('aria-expanded', expanded ? 'false' : 'true');
        listEl.hidden = expanded;
    });

    loadAdmins();

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        errorEl.hidden = true;

        // 只填前缀，自动补全为 @lazycat.com；粘入完整邮箱时自动剥离后缀
        let prefix = emailInput.value.trim();
        const at = prefix.indexOf('@');
        if (at !== -1) prefix = prefix.slice(0, at);
        prefix = prefix.replace(/\s+/g, '');

        const password = passwordInput.value;

        if (!prefix || !password) {
            showError('请输入账号和密码');
            return;
        }
        if (!/^[A-Za-z0-9._-]+$/.test(prefix)) {
            showError('账号只能包含字母、数字、点、下划线和连字符');
            return;
        }

        const email = prefix + EMAIL_DOMAIN;

        try {
            const res = await fetch(`${API_BASE}/admins`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            if (res.status === 401) { window.location.href = '/login'; return; }
            if (res.status === 403) { window.location.href = '/'; return; }
            const data = await res.json();
            if (data.success) {
                emailInput.value = '';
                passwordInput.value = '';
                loadAdmins();
            } else {
                showError(data.message || '添加失败');
            }
        } catch (err) {
            showError('无法连接到服务器');
        }
    });

    listEl.addEventListener('click', async (e) => {
        const del = e.target.closest('.admin-item-del');
        if (!del) return;
        const id = Number(del.dataset.id);
        if (!confirm('确定要删除该管理员吗？')) return;
        try {
            const res = await fetch(`${API_BASE}/admins/${id}`, { method: 'DELETE' });
            if (res.status === 401) { window.location.href = '/login'; return; }
            if (res.status === 403) { window.location.href = '/'; return; }
            const data = await res.json();
            if (data.success) loadAdmins();
            else alert(data.message || '删除失败');
        } catch (err) {
            alert('删除失败，请稍后重试');
        }
    });

    function showError(msg) {
        errorEl.textContent = msg;
        errorEl.hidden = false;
    }
});

async function loadAdmins() {
    const listEl = document.getElementById('adminList');
    const countEl = document.getElementById('adminCount');
    try {
        const res = await fetch(`${API_BASE}/admins`);
        if (res.status === 401) { window.location.href = '/login'; return; }
        if (res.status === 403) { window.location.href = '/'; return; }
        const data = await res.json();
        if (!data.success) {
            listEl.innerHTML = `<div class="admin-loading">${escapeHtml(data.message || '加载失败')}</div>`;
            return;
        }
        const admins = data.admins || [];
        if (countEl) countEl.textContent = String(admins.length);
        if (!admins.length) {
            listEl.innerHTML = '<div class="admin-empty">暂无管理员</div>';
            return;
        }
        listEl.innerHTML = admins.map(a => {
                const badge = a.is_main ? '<span class="admin-item-badge">主管理员</span>' : '';
                const delBtn = a.is_main
                    ? ''
                    : `<button type="button" class="admin-item-del" data-id="${a.id}">删除</button>`;
                const initial = (a.nickname || a.email || '?').charAt(0).toUpperCase();
                const avatarHtml = a.avatar
                    ? `<img class="admin-item-avatar" src="${escapeAttr(a.avatar)}" alt="">`
                    : `<span class="admin-item-avatar admin-item-avatar-empty">${escapeHtml(initial)}</span>`;
                return `<div class="admin-item">
                    <div class="admin-item-info">
                        ${avatarHtml}
                        <div class="admin-item-text">
                            <span class="admin-item-nickname">${escapeHtml(a.nickname || a.email)}${badge}</span>
                            <span class="admin-item-email">${escapeHtml(a.email)}</span>
                        </div>
                    </div>
                    ${delBtn}
                </div>`;
            }).join('');
    } catch (err) {
        listEl.innerHTML = '<div class="admin-loading">无法连接到服务器</div>';
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
}

function escapeAttr(text) {
    return escapeHtml(text).replace(/"/g, '&quot;');
}
