// ============================================
// 个人资料页逻辑（昵称 + 头像，登录后可用）
// ============================================

const API_BASE = '/api';

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('profileForm');
    const nicknameInput = document.getElementById('nickname');
    const avatarInput = document.getElementById('avatar');
    const previewEl = document.getElementById('avatarPreview');
    const errorEl = document.getElementById('profileError');
    const uploadBtn = document.getElementById('avatarUploadBtn');
    const fileInput = document.getElementById('avatarFileInput');

    loadProfile();

    function renderAvatar(url) {
        if (url) {
            previewEl.src = url;
            previewEl.hidden = false;
        } else {
            previewEl.removeAttribute('src');
            previewEl.hidden = true;
        }
    }

    avatarInput.addEventListener('input', () => renderAvatar(avatarInput.value.trim()));

    uploadBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', async (e) => {
        const file = e.target.files && e.target.files[0];
        if (!file) return;
        uploadBtn.disabled = true;
        uploadBtn.textContent = '上传中...';
        try {
            const url = await uploadImage(file);
            avatarInput.value = url;
            renderAvatar(url);
            showToast('头像上传成功');
        } catch (err) {
            showToast(err.message || '上传失败', 'error');
        } finally {
            e.target.value = '';
            uploadBtn.disabled = false;
            uploadBtn.textContent = '上传图片';
        }
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        errorEl.hidden = true;

        const nickname = nicknameInput.value.trim();
        const avatar = avatarInput.value.trim();

        if (!nickname) {
            errorEl.textContent = '昵称不能为空';
            errorEl.hidden = false;
            return;
        }

        const btn = form.querySelector('button[type="submit"]');
        btn.disabled = true;
        btn.textContent = '保存中...';

        try {
            const res = await fetch(`${API_BASE}/profile`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ nickname, avatar })
            });
            if (res.status === 401) { window.location.href = '/login'; return; }
            const data = await res.json();
            if (data.success) {
                showToast('资料已保存');
                if (data.nickname) nicknameInput.value = data.nickname;
            } else {
                errorEl.textContent = data.message || '保存失败';
                errorEl.hidden = false;
            }
        } catch (err) {
            errorEl.textContent = '无法连接到服务器';
            errorEl.hidden = false;
        } finally {
            btn.disabled = false;
            btn.textContent = '保存';
        }
    });

    const passwordForm = document.getElementById('passwordForm');
    const passwordError = document.getElementById('passwordError');

    passwordForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        passwordError.hidden = true;

        const oldPassword = document.getElementById('oldPassword').value;
        const newPassword = document.getElementById('newPassword').value;
        const confirmPassword = document.getElementById('confirmPassword').value;

        if (!oldPassword || !newPassword || !confirmPassword) {
            passwordError.textContent = '请填写所有字段';
            passwordError.hidden = false;
            return;
        }
        if (newPassword.length < 6) {
            passwordError.textContent = '新密码至少 6 位';
            passwordError.hidden = false;
            return;
        }
        if (newPassword !== confirmPassword) {
            passwordError.textContent = '两次输入的新密码不一致';
            passwordError.hidden = false;
            return;
        }

        const btn = passwordForm.querySelector('button[type="submit"]');
        btn.disabled = true;
        btn.textContent = '提交中...';

        try {
            const res = await fetch(`${API_BASE}/password`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
            });
            if (res.status === 401) { window.location.href = '/login'; return; }
            const data = await res.json();
            if (data.success) {
                showToast('密码修改成功');
                passwordForm.reset();
            } else {
                passwordError.textContent = data.message || '修改失败';
                passwordError.hidden = false;
            }
        } catch (err) {
            passwordError.textContent = '无法连接到服务器';
            passwordError.hidden = false;
        } finally {
            btn.disabled = false;
            btn.textContent = '修改密码';
        }
    });
});

async function loadProfile() {
    try {
        const res = await fetch(`${API_BASE}/auth`);
        if (res.status === 401) { window.location.href = '/login'; return; }
        const data = await res.json();
        if (!data.authed) { window.location.href = '/login'; return; }
        document.getElementById('email').value = data.email || '';
        document.getElementById('nickname').value = data.nickname || '';
        document.getElementById('avatar').value = data.avatar || '';
        const preview = document.getElementById('avatarPreview');
        if (data.avatar) {
            preview.src = data.avatar;
            preview.hidden = false;
        }
    } catch (err) {
        document.getElementById('profileError').textContent = '无法连接到服务器';
        document.getElementById('profileError').hidden = false;
    }
}

async function uploadImage(file) {
    const formData = new FormData();
    formData.append('image', file);

    const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: formData });
    let msg = `HTTP ${res.status}`;
    try {
        const data = await res.json();
        if (data && data.message) msg = data.message;
        if (data && data.success) return data.url;
    } catch (e) { /* 忽略解析错误 */ }
    throw new Error(msg);
}

function showToast(message, type = 'success') {
    document.querySelectorAll('.toast').forEach(t => t.remove());

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = type === 'success'
        ? `<span>✓</span> ${escapeHtml(message)}`
        : `<span>✗</span> ${escapeHtml(message)}`;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'toastIn 0.25s ease-out reverse';
        setTimeout(() => toast.remove(), 250);
    }, 2500);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
}
