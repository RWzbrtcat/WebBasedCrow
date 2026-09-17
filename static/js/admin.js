// ============================================
// 管理员管理页逻辑（仅主管理员可访问）
// ============================================

const API_BASE = '/api';

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('adminForm');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const errorEl = document.getElementById('adminError');
    const listEl = document.getElementById('adminList');

    loadAdmins();

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        errorEl.hidden = true;

        const email = emailInput.value.trim();
        const password = passwordInput.value;

        if (!email || !password) {
            showError('请输入邮箱和密码');
            return;
        }

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
    try {
        const res = await fetch(`${API_BASE}/admins`);
        if (res.status === 401) { window.location.href = '/login'; return; }
        if (res.status === 403) { window.location.href = '/'; return; }
        const data = await res.json();
        if (!data.success) {
            listEl.innerHTML = `<div class="admin-list-title">${escapeHtml(data.message || '加载失败')}</div>`;
            return;
        }
        const admins = data.admins || [];
        if (!admins.length) {
            listEl.innerHTML = '<div class="admin-list-title">暂无管理员</div>';
            return;
        }
        listEl.innerHTML = `
            <div class="admin-list-title">已有管理员（${admins.length}）</div>
            ${admins.map(a => {
                const badge = a.is_main ? '<span class="admin-item-badge">主管理员</span>' : '';
                const delBtn = a.is_main
                    ? ''
                    : `<button type="button" class="admin-item-del" data-id="${a.id}">删除</button>`;
                return `<div class="admin-item">
                    <span class="admin-item-email">${escapeHtml(a.email)}${badge}</span>
                    ${delBtn}
                </div>`;
            }).join('')}
        `;
    } catch (err) {
        listEl.innerHTML = '<div class="admin-list-title">无法连接到服务器</div>';
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
}
