// ============================================
// 个人资料页逻辑（昵称 + 头像，登录后可用）
// ============================================

const API_BASE = '/api';

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('profileForm');
    const nicknameInput = document.getElementById('nickname');
    const avatarInput = document.getElementById('avatar');
    const previewEl = document.getElementById('avatarPreview');
    const placeholderEl = document.getElementById('avatarPlaceholder');
    const pickerEl = document.getElementById('avatarPicker');
    const overlayEl = document.getElementById('avatarOverlay');
    const errorEl = document.getElementById('profileError');
    const fileInput = document.getElementById('avatarFileInput');

    const OVERLAY_TEXT = '更改头像';
    const UPLOADING_TEXT = '上传中...';

    loadProfile();

    function renderAvatar(url) {
        if (url) {
            previewEl.src = url;
            previewEl.hidden = false;
            placeholderEl.hidden = true;
        } else {
            previewEl.removeAttribute('src');
            previewEl.hidden = true;
            placeholderEl.hidden = false;
        }
    }

    // 点击头像直接选择图片上传（不再显示图片链接输入框与上传按钮）
    pickerEl.addEventListener('click', () => {
        if (pickerEl.disabled) return;
        fileInput.click();
    });

    fileInput.addEventListener('change', async (e) => {
        const file = e.target.files && e.target.files[0];
        if (!file) return;

        pickerEl.disabled = true;
        pickerEl.classList.add('is-uploading');
        overlayEl.textContent = UPLOADING_TEXT;

        try {
            const url = await uploadImage(file);
            avatarInput.value = url;
            renderAvatar(url);
            // 上传后立即保存，避免用户找不到保存入口
            const ok = await saveProfile();
            showToast(ok ? '头像已更新' : '头像已上传，但保存失败');
        } catch (err) {
            showToast(err.message || '上传失败', 'error');
        } finally {
            e.target.value = '';
            pickerEl.disabled = false;
            pickerEl.classList.remove('is-uploading');
            overlayEl.textContent = OVERLAY_TEXT;
            pickerEl.blur();
        }
    });

    // 提交资料（昵称 + 头像）；silent 为 true 时不提示成功 toast
    async function saveProfile(silent = false) {
        errorEl.hidden = true;

        const nickname = nicknameInput.value.trim();
        if (!nickname) {
            errorEl.textContent = '昵称不能为空';
            errorEl.hidden = false;
            return false;
        }

        try {
            const res = await fetch(`${API_BASE}/profile`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ nickname, avatar: avatarInput.value.trim() })
            });
            if (res.status === 401) { window.location.href = '/login'; return false; }
            const data = await res.json();
            if (data.success) {
                if (!silent) showToast('资料已保存');
                if (data.nickname) nicknameInput.value = data.nickname;
                return true;
            }
            errorEl.textContent = data.message || '保存失败';
            errorEl.hidden = false;
            return false;
        } catch (err) {
            errorEl.textContent = '无法连接到服务器';
            errorEl.hidden = false;
            return false;
        }
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const btn = form.querySelector('button[type="submit"]');
        btn.disabled = true;
        btn.textContent = '保存中...';
        try {
            await saveProfile();
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
                showToast('密码修改成功，请重新登录');
                setTimeout(() => { window.location.href = '/login'; }, 800);
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
        const placeholder = document.getElementById('avatarPlaceholder');
        if (data.avatar) {
            preview.src = data.avatar;
            preview.hidden = false;
            if (placeholder) placeholder.hidden = true;
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
