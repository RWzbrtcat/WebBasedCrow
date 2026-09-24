// ============================================
// 文章详情页逻辑
// ============================================

const API_BASE = '/api';

let currentPostId = null;
let currentLikes = 0;
let liked = false;
let isAdmin = false;

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
        const isMain = !!(authData && authData.is_main);
        const adminId = Number(authData && authData.admin_id) || 0;
        if (postData.success) {
            renderPost(postData.post, authed, isMain, adminId);
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

function renderPost(post, authed, isMain, adminId) {
    document.title = `${post.title} · LazyCat's Blog`;

    currentPostId = post.id;
    currentLikes = Number(post.likes) || 0;
    liked = isLiked(post.id);
    isAdmin = authed;

    const updated = post.updated_at && post.updated_at !== post.created_at
        ? `<span class="sep">·</span><span>更新于 ${formatDate(post.updated_at)}</span>`
        : '';

    const topic = (post.topic || '').trim();
    const topicBadge = topic
        ? `<span class="post-topic">${escapeHtml(topic)}</span>`
        : '';
    const theme = (post.theme || '').trim();
    const themeBadge = theme
        ? `<span class="post-theme">${escapeHtml(theme)}</span>`
        : '';

    document.getElementById('postDetail').innerHTML = `
        <article class="post-full">
            <h1 class="post-title">${escapeHtml(post.title)}</h1>
            <div class="post-meta">
                ${topicBadge}
                ${themeBadge}
                <span>${escapeHtml(post.author || '匿名')}</span>
                <span class="sep">·</span>
                <span>${formatDate(post.created_at)}</span>
                ${updated}
            </div>
            ${post.hidden ? '<div class="post-hidden-banner">此文章已隐藏，仅作者与管理员可见</div>' : ''}
            <div class="post-content markdown-body" id="postContent"></div>
        </article>
    `;

    renderMarkdownInto(document.getElementById('postContent'), post.content);
    bindInternalLinks(document.getElementById('postContent'));

    const canEdit = authed && (isMain || Number(post.author_id) === adminId);
    renderPostAdminActions(post, canEdit);
    document.getElementById('floatingActions').hidden = false;
    bindPostInteractions();
    loadComments();
}

// 将编辑/隐藏/删除按钮注入顶部灵动岛头部（仅文章作者本人或主管理员可见）
function renderPostAdminActions(post, canEdit) {
    const container = document.getElementById('postAdminActions');
    if (!container) return;
    container.innerHTML = canEdit
        ? `<a class="pill-btn pill-btn-primary" href="/editor?id=${post.id}">编辑</a>
           <button class="pill-btn" id="hideBtn">${post.hidden ? '取消隐藏' : '隐藏'}</button>
           <button class="pill-btn pill-btn-danger" id="deleteBtn">删除</button>`
        : '';
    if (canEdit) {
        document.getElementById('hideBtn').addEventListener('click', () => togglePostHidden(post));
        document.getElementById('deleteBtn').addEventListener('click', () => deletePost(post.id));
    }
}

// 隐藏 / 取消隐藏文章（作者本人或主管理员）
async function togglePostHidden(post) {
    const targetHidden = !post.hidden;
    if (targetHidden && !confirm('隐藏后，普通访客将无法看到这篇文章，确定要隐藏吗？')) return;

    try {
        const data = await apiRequest(`${API_BASE}/posts/${post.id}/hidden`, 'PUT', { hidden: targetHidden });
        if (data.success) {
            post.hidden = targetHidden;
            showToast(targetHidden ? '文章已隐藏' : '文章已显示');
            renderPostAdminActions(post, true);
            updateHiddenBanner(post);
        } else {
            showToast(data.message || '操作失败', 'error');
        }
    } catch (e) {
        showToast('操作失败，请稍后重试', 'error');
    }
}

// 根据隐藏状态插入或移除正文上方的隐藏提示条
function updateHiddenBanner(post) {
    const detail = document.getElementById('postDetail');
    const article = detail ? detail.querySelector('.post-full') : null;
    if (!article) return;
    let banner = article.querySelector('.post-hidden-banner');
    if (post.hidden) {
        if (!banner) {
            banner = document.createElement('div');
            banner.className = 'post-hidden-banner';
            const content = article.querySelector('.post-content');
            article.insertBefore(banner, content);
        }
        banner.textContent = '此文章已隐藏，仅作者与管理员可见';
    } else if (banner) {
        banner.remove();
    }
}

function bindPostInteractions() {
    updateLikeButton();

    document.getElementById('likeBtn').addEventListener('click', handleLike);
    document.getElementById('commentBtn').addEventListener('click', openCommentDrawer);
    document.getElementById('donateBtn').addEventListener('click', () => {
        document.getElementById('donateModal').hidden = false;
    });
    document.getElementById('commentForm').addEventListener('submit', handleCommentSubmit);

    const drawer = document.getElementById('commentDrawer');
    document.getElementById('commentDrawerClose').addEventListener('click', closeCommentDrawer);
    drawer.addEventListener('click', (e) => {
        if (e.target === drawer) closeCommentDrawer();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && drawer && !drawer.hidden) closeCommentDrawer();
    });

    const commentsList = document.getElementById('commentsList');
    commentsList.addEventListener('click', onCommentsClick);
    commentsList.addEventListener('submit', onCommentsSubmit);
}

function openCommentDrawer() {
    const drawer = document.getElementById('commentDrawer');
    if (drawer) drawer.hidden = false;
}

function closeCommentDrawer() {
    const drawer = document.getElementById('commentDrawer');
    if (drawer) drawer.hidden = true;
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
    btn.classList.toggle('liked', liked);
    const text = document.getElementById('likeBtnText');
    if (text) text.textContent = liked ? `已点赞 · ${currentLikes}` : `点赞 · ${currentLikes}`;
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
    const commentBtnText = document.getElementById('commentBtnText');
    if (commentBtnText) commentBtnText.textContent = `评论 · ${comments.length}`;

    if (!comments.length) {
        list.innerHTML = '<p class="comments-empty">还没有评论，来抢沙发吧～</p>';
        return;
    }

    const childrenMap = new Map();
    comments.forEach((c) => {
        const pid = c.parent_id || 0;
        if (!childrenMap.has(pid)) childrenMap.set(pid, []);
        childrenMap.get(pid).push(c);
    });

    const renderThread = (c) => {
        const replies = childrenMap.get(c.id);
        const repliesHtml = replies && replies.length
            ? `<div class="comment-replies">${replies.map(renderThread).join('')}</div>`
            : '';
        return `<div class="comment-thread">${renderCommentItem(c)}${repliesHtml}</div>`;
    };

    list.innerHTML = (childrenMap.get(0) || []).map(renderThread).join('');
}

function renderCommentItem(c) {
    const hiddenBadge = c.hidden ? '<span class="comment-hidden-badge">已隐藏</span>' : '';
    const replyBtn = `<button type="button" class="comment-reply-btn" data-id="${c.id}">回复</button>`;
    const adminActions = isAdmin
        ? `<button type="button" class="comment-action" data-action="hide" data-id="${c.id}">${c.hidden ? '显示' : '隐藏'}</button>
           <button type="button" class="comment-action comment-action-danger" data-action="delete" data-id="${c.id}">删除</button>`
        : '';
    return `
        <div class="comment-item${c.hidden ? ' comment-hidden' : ''}" data-id="${c.id}" data-hidden="${c.hidden ? '1' : '0'}">
            <div class="comment-head">
                <span class="comment-nickname">${escapeHtml(c.nickname || '匿名')}</span>${hiddenBadge}
                <span class="comment-time">${formatDateTime(c.created_at)}</span>
            </div>
            <div class="comment-content">${escapeHtml(c.content)}</div>
            <div class="comment-actions">${replyBtn}${adminActions}</div>
            <div class="comment-reply-form" hidden></div>
        </div>
    `;
}

function onCommentsClick(e) {
    const replyBtn = e.target.closest('.comment-reply-btn');
    if (replyBtn) {
        const item = replyBtn.closest('.comment-item');
        const nickname = item.querySelector('.comment-nickname').textContent.trim();
        openReplyForm(item, replyBtn.dataset.id, nickname);
        return;
    }

    const cancelBtn = e.target.closest('.reply-cancel');
    if (cancelBtn) {
        const form = cancelBtn.closest('.comment-reply-form');
        if (form) {
            form.hidden = true;
            form.innerHTML = '';
        }
        return;
    }

    const actionBtn = e.target.closest('.comment-action');
    if (!actionBtn) return;
    const id = actionBtn.dataset.id;
    if (actionBtn.dataset.action === 'hide') {
        handleHideComment(id, actionBtn);
    } else if (actionBtn.dataset.action === 'delete') {
        handleDeleteComment(id);
    }
}

function onCommentsSubmit(e) {
    const form = e.target.closest('.comment-reply-form-inner');
    if (!form) return;
    e.preventDefault();
    handleReplySubmit(form);
}

function openReplyForm(item, id, nickname) {
    const formContainer = item.querySelector('.comment-reply-form');
    if (!formContainer) return;
    const placeholder = nickname && nickname !== '匿名'
        ? `回复 @${nickname} ...`
        : '写下你的回复...';
    formContainer.innerHTML = `
        <form class="comment-form comment-reply-form-inner" data-parent-id="${id}">
            <input type="text" class="reply-nickname" placeholder="昵称（可选，留空为匿名）" maxlength="50">
            <textarea class="reply-content" placeholder="${escapeHtml(placeholder)}" required></textarea>
            <div class="comment-form-actions">
                <button type="button" class="btn btn-secondary reply-cancel">取消</button>
                <button type="submit" class="btn btn-primary">回复</button>
            </div>
        </form>
    `;
    formContainer.hidden = false;
    formContainer.querySelector('.reply-content').focus();
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
        const data = await postComment(nickname, content, 0);
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

async function handleReplySubmit(form) {
    const parentId = Number(form.dataset.parentId);
    const nickname = form.querySelector('.reply-nickname').value.trim();
    const content = form.querySelector('.reply-content').value.trim();
    if (!content) {
        showToast('请输入回复内容', 'error');
        return;
    }

    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = '提交中...';

    try {
        const data = await postComment(nickname, content, parentId);
        if (data.success) {
            showToast('回复成功');
            loadComments();
        } else {
            showToast(data.message || '回复失败', 'error');
        }
    } catch (e) {
        showToast('回复失败，请稍后重试', 'error');
    }
}

async function postComment(nickname, content, parentId) {
    return apiRequest(`${API_BASE}/posts/${currentPostId}/comments`, 'POST', {
        nickname,
        content,
        parent_id: parentId
    });
}

async function handleHideComment(id, btn) {
    const item = btn.closest('.comment-item');
    const hidden = item.dataset.hidden === '1';
    try {
        const data = await apiRequest(`${API_BASE}/comments/${id}`, 'PUT', { hidden: !hidden });
        if (data.success) {
            showToast(hidden ? '评论已显示' : '评论已隐藏');
            loadComments();
        } else {
            showToast(data.message || '操作失败', 'error');
        }
    } catch (e) {
        showToast('操作失败，请稍后重试', 'error');
    }
}

async function handleDeleteComment(id) {
    if (!confirm('确定要删除这条评论吗？其下所有回复也会一并删除。')) return;
    try {
        const data = await apiRequest(`${API_BASE}/comments/${id}`, 'DELETE');
        if (data.success) {
            showToast('评论已删除');
            loadComments();
        } else {
            showToast(data.message || '删除失败', 'error');
        }
    } catch (e) {
        showToast('删除失败，请稍后重试', 'error');
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
