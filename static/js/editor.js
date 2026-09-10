// ============================================
// 编辑器页逻辑（新建 / 编辑文章）
// ============================================

const API_BASE = '/api';

// 编辑模式下的文章 id（null 表示新建）
let editingId = null;

document.addEventListener('DOMContentLoaded', () => {
    const id = new URLSearchParams(window.location.search).get('id');
    if (id) {
        editingId = id;
        loadForEdit(id);
    }

    document.getElementById('postForm').addEventListener('submit', handleSubmit);
});

async function apiRequest(url, method = 'GET', body = null) {
    const options = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) options.body = JSON.stringify(body);

    const response = await fetch(url, options);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
}

async function loadForEdit(id) {
    try {
        const data = await apiRequest(`${API_BASE}/posts/${id}`);
        if (!data.success) {
            showToast(data.message || '文章不存在', 'error');
            return;
        }
        const post = data.post;
        document.getElementById('editorTitle').textContent = '编辑文章';
        document.getElementById('title').value = post.title;
        document.getElementById('author').value = post.author || '';
        document.getElementById('content').value = post.content || '';
        document.getElementById('submitBtn').textContent = '保存';
        document.title = `编辑 · ${post.title}`;
    } catch (e) {
        showToast('加载文章失败，请稍后重试', 'error');
    }
}

async function handleSubmit(e) {
    e.preventDefault();

    const title = document.getElementById('title').value.trim();
    const author = document.getElementById('author').value.trim() || '匿名';
    const content = document.getElementById('content').value;

    if (!title) {
        showToast('请输入文章标题', 'error');
        return;
    }

    const submitBtn = document.getElementById('submitBtn');
    submitBtn.disabled = true;
    submitBtn.textContent = '提交中...';

    try {
        const url = editingId ? `${API_BASE}/posts/${editingId}` : `${API_BASE}/posts`;
        const method = editingId ? 'PUT' : 'POST';
        const data = await apiRequest(url, method, { title, author, content });

        if (data.success) {
            showToast(editingId ? '✏️ 文章已保存' : '✅ 文章发布成功');
            setTimeout(() => {
                window.location.href = `/post?id=${editingId || data.id}`;
            }, 500);
        } else {
            showToast(data.message || '操作失败', 'error');
            submitBtn.disabled = false;
            submitBtn.textContent = editingId ? '保存' : '发布';
        }
    } catch (err) {
        showToast('提交失败，请检查服务是否运行', 'error');
        submitBtn.disabled = false;
        submitBtn.textContent = editingId ? '保存' : '发布';
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
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
