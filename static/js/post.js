// ============================================
// 文章详情页逻辑
// ============================================

const API_BASE = '/api';

let currentPostId = null;
let currentLikes = 0;
let liked = false;

document.addEventListener('DOMContentLoaded', () => {
    const id = new URLSearchParams(window.location.search).get('id');
    if (!id) {
        showNotFound();
        return;
    }
    loadPost(id);
    bindDonateModal();
    initHeaderScroll();
});

async function apiRequest(url, method = 'GET', body = null) {
    const options = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) options.body = JSON.stringify(body);

    const response = await fetch(url, options);
    if (response.status === 401) {
        window.location.href = '/login';
        throw new Error('未登录');
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
}

async function loadPost(id) {
    const detail = document.getElementById('postDetail');

    try {
        const [postData, authData] = await Promise.all([
            apiRequest(`${API_BASE}/posts/${id}`),
            apiRequest(`${API_BASE}/auth`).catch(() => ({ authed: false }))
        ]);
        const authed = !!(authData && authData.authed);
        if (postData.success) {
            renderPost(postData.post, authed);
        } else {
            showNotFound(postData.message || '文章不存在');
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

function renderPost(post, authed) {
    document.title = `${post.title} · LazyCat's Blog`;

    currentPostId = post.id;
    currentLikes = Number(post.likes) || 0;
    liked = isLiked(post.id);

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
            <div class="post-engagement">
                <button class="btn btn-secondary like-btn" id="likeBtn">点赞</button>
                <button class="btn btn-secondary" id="donateBtn">打赏</button>
            </div>
            <section class="comments">
                <h2 class="comments-title">评论 <span id="commentCount">0</span></h2>
                <div class="comments-list" id="commentsList">
                    <div class="loading">加载中...</div>
                </div>
                <form class="comment-form" id="commentForm">
                    <input type="text" id="commentNickname" placeholder="昵称（可选，留空为匿名）" maxlength="50">
                    <textarea id="commentContent" placeholder="写下你的评论..." required></textarea>
                    <button type="submit" class="btn btn-primary">发表评论</button>
                </form>
            </section>
        </article>
    `;

    renderMarkdownInto(document.getElementById('postContent'), post.content);

    renderPostAdminActions(post, authed);
    bindPostInteractions();
    loadComments();
}

// 将编辑/删除按钮注入顶部灵动岛头部（仅登录后显示）
function renderPostAdminActions(post, authed) {
    const container = document.getElementById('postAdminActions');
    if (!container) return;
    container.innerHTML = authed
        ? `<a class="pill-btn pill-btn-primary" href="/editor?id=${post.id}">编辑</a>
           <button class="pill-btn pill-btn-danger" id="deleteBtn">删除</button>`
        : '';
    if (authed) {
        document.getElementById('deleteBtn').addEventListener('click', () => deletePost(post.id));
    }
}

function bindPostInteractions() {
    updateLikeButton();

    document.getElementById('likeBtn').addEventListener('click', handleLike);
    document.getElementById('donateBtn').addEventListener('click', () => {
        document.getElementById('donateModal').hidden = false;
    });
    document.getElementById('commentForm').addEventListener('submit', handleCommentSubmit);
}

// ===== 点赞 =====
function isLiked(id) {
    try {
        const arr = JSON.parse(localStorage.getItem('liked_posts') || '[]');
        return arr.includes(Number(id));
    } catch (e) {
        return false;
    }
}

function setLiked(id, val) {
    try {
        let arr = JSON.parse(localStorage.getItem('liked_posts') || '[]');
        arr = arr.filter((x) => x !== Number(id));
        if (val) arr.push(Number(id));
        localStorage.setItem('liked_posts', JSON.stringify(arr));
    } catch (e) { /* 忽略存储失败 */ }
}

function updateLikeButton() {
    const btn = document.getElementById('likeBtn');
    if (!btn) return;
    btn.innerHTML = liked
        ? `已点赞 · ${currentLikes}`
        : `点赞 · ${currentLikes}`;
    btn.classList.toggle('liked', liked);
}

async function handleLike() {
    const action = liked ? 'unlike' : 'like';
    try {
        const data = await apiRequest(`${API_BASE}/posts/${currentPostId}/${action}`, 'POST');
        if (data.success) {
            const nowLiked = !liked;
            liked = nowLiked;
            currentLikes = (data.likes != null)
                ? Number(data.likes)
                : Math.max(0, currentLikes + (nowLiked ? 1 : -1));
            setLiked(currentPostId, liked);
            updateLikeButton();
        } else {
            showToast(data.message || '操作失败', 'error');
        }
    } catch (e) {
        showToast('操作失败，请稍后重试', 'error');
    }
}

// ===== 评论 =====
async function loadComments() {
    const list = document.getElementById('commentsList');
    try {
        const data = await apiRequest(`${API_BASE}/posts/${currentPostId}/comments`);
        if (data.success) {
            renderComments(data.comments || []);
        } else {
            list.innerHTML = '<p class="comments-empty">评论加载失败</p>';
        }
    } catch (e) {
        list.innerHTML = '<p class="comments-empty">评论加载失败</p>';
    }
}

function renderComments(comments) {
    const list = document.getElementById('commentsList');
    document.getElementById('commentCount').textContent = comments.length;

    if (!comments.length) {
        list.innerHTML = '<p class="comments-empty">还没有评论，来抢沙发吧～</p>';
        return;
    }

    list.innerHTML = comments.map((c) => `
        <div class="comment-item">
            <div class="comment-head">
                <span class="comment-nickname">${escapeHtml(c.nickname || '匿名')}</span>
                <span class="comment-time">${formatDateTime(c.created_at)}</span>
            </div>
            <div class="comment-content">${escapeHtml(c.content)}</div>
        </div>
    `).join('');
}

async function handleCommentSubmit(e) {
    e.preventDefault();

    const nickname = document.getElementById('commentNickname').value.trim();
    const content = document.getElementById('commentContent').value.trim();
    if (!content) {
        showToast('请输入评论内容', 'error');
        return;
    }

    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = '提交中...';

    try {
        const data = await apiRequest(`${API_BASE}/posts/${currentPostId}/comments`, 'POST', { nickname, content });
        if (data.success) {
            document.getElementById('commentContent').value = '';
            showToast('评论成功');
            loadComments();
        } else {
            showToast(data.message || '评论失败', 'error');
        }
    } catch (e) {
        showToast('评论失败，请稍后重试', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '发表评论';
    }
}

// ===== 打赏弹窗 =====
function bindDonateModal() {
    const modal = document.getElementById('donateModal');
    document.getElementById('donateModalClose').addEventListener('click', () => {
        modal.hidden = true;
    });
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.hidden = true;
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !modal.hidden) modal.hidden = true;
    });

    const tabs = modal.querySelectorAll('.donate-tab');
    tabs.forEach((tab) => {
        tab.addEventListener('click', () => {
            tabs.forEach((t) => t.classList.toggle('active', t === tab));
            const target = tab.dataset.tab;
            modal.querySelectorAll('.donate-qr-pane').forEach((pane) => {
                pane.hidden = pane.dataset.qr !== target;
            });
        });
    });

    modal.querySelectorAll('.donate-qr').forEach((img) => {
        img.addEventListener('error', () => {
            const placeholder = document.createElement('p');
            placeholder.className = 'donate-empty';
            placeholder.textContent = '收款二维码加载失败';
            img.replaceWith(placeholder);
        });
    });
}

// ===== 灵动岛头部：页面顶部矩形，下拉后椭圆 =====
function initHeaderScroll() {
    const header = document.querySelector('.site-header-pill');
    if (!header) return;
    const update = () => header.classList.toggle('scrolled', window.scrollY > 0);
    update();
    window.addEventListener('scroll', update, { passive: true });
}

function showNotFound(msg) {
    document.getElementById('postDetail').innerHTML = `
        <div class="empty-state">
            <p>❌ ${escapeHtml(msg || '文章不存在')}</p>
            <p style="margin-top:16px;"><a class="btn btn-secondary" href="/">← 返回主页面</a></p>
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

function formatDateTime(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr.replace(' ', 'T'));
    if (isNaN(date.getTime())) return dateStr;
    return date.toLocaleString('zh-CN', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit'
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
