// ============================================
// 文章详情页逻辑
// ============================================

const API_BASE = '/api';

document.addEventListener('DOMContentLoaded', () => {
    const id = new URLSearchParams(window.location.search).get('id');
    if (!id) {
        showNotFound();
        return;
    }
    loadPost(id);
});

async function apiRequest(url, method = 'GET', body = null) {
    const options = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) options.body = JSON.stringify(body);

    const response = await fetch(url, options);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
}

async function loadPost(id) {
    const detail = document.getElementById('postDetail');

    try {
        const data = await apiRequest(`${API_BASE}/posts/${id}`);
        if (data.success) {
            renderPost(data.post);
        } else {
            showNotFound(data.message || '文章不存在');
        }
    } catch (e) {
        detail.innerHTML = `
            <div class="empty-state">
                <p>❌ 无法连接到服务器</p>
                <p style="font-size:0.85rem;margin-top:8px;">请确保 C++ 服务正在运行</p>
            </div>
        `;
    }
}

function renderPost(post) {
    document.title = `${post.title} · 我的博客`;

    const updated = post.updated_at && post.updated_at !== post.created_at
        ? `<span class="sep">·</span><span>更新于 ${formatDate(post.updated_at)}</span>`
        : '';

    const topic = (post.topic || '').trim();
    const topicBadge = topic
        ? `<span class="post-topic">${escapeHtml(topic)}</span>`
        : '';

    document.getElementById('postDetail').innerHTML = `
        <article class="post-full">
            <h1 class="post-title">${escapeHtml(post.title)}</h1>
            <div class="post-meta">
                ${topicBadge}
                <span>${escapeHtml(post.author || '匿名')}</span>
                <span class="sep">·</span>
                <span>${formatDate(post.created_at)}</span>
                ${updated}
            </div>
            <div class="post-content markdown-body" id="postContent"></div>
            <div class="post-actions">
                <a class="btn btn-secondary" href="/">← 返回列表</a>
                <a class="btn btn-primary" href="/editor?id=${post.id}">编辑</a>
                <button class="btn btn-danger" onclick="deletePost(${post.id})">删除</button>
            </div>
        </article>
    `;

    renderMarkdownInto(document.getElementById('postContent'), post.content);
}

function showNotFound(msg) {
    document.getElementById('postDetail').innerHTML = `
        <div class="empty-state">
            <p>❌ ${escapeHtml(msg || '文章不存在')}</p>
            <p style="margin-top:16px;"><a class="btn btn-secondary" href="/">← 返回列表</a></p>
        </div>
    `;
}

async function deletePost(id) {
    if (!confirm('确定要删除这篇文章吗？此操作不可恢复。')) return;

    try {
        const data = await apiRequest(`${API_BASE}/posts/${id}`, 'DELETE');
        if (data.success) {
            showToast('🗑️ 文章已删除');
            setTimeout(() => { window.location.href = '/'; }, 600);
        } else {
            showToast(data.message || '删除失败', 'error');
        }
    } catch (e) {
        showToast('删除失败，请稍后重试', 'error');
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr.replace(' ', 'T'));
    if (isNaN(date.getTime())) return dateStr;
    return date.toLocaleDateString('zh-CN', {
        year: 'numeric', month: 'long', day: 'numeric'
    });
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
