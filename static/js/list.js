// ============================================
// 文章列表页逻辑
// ============================================

const API_BASE = '/api';

// 草稿页模式（body 上 data-mode="drafts"）
const IS_DRAFTS = document.body.dataset.mode === 'drafts';

// 全部文章数据 + 当前选中的专栏（'all' 表示全部）
let allPosts = [];
let currentTopic = 'all';
let topicsList = [];

document.addEventListener('DOMContentLoaded', () => {
    loadPosts();

    const tabs = document.getElementById('topicTabs');
    if (tabs) {
        tabs.addEventListener('click', (e) => {
            const btn = e.target.closest('.topic-tab');
            if (!btn) return;
            const idx = btn.dataset.index;
            currentTopic = idx === '-1' ? 'all' : topicsList[Number(idx)];
            renderTopicTabs(allPosts);
            renderPosts(allPosts);
        });
    }
});

async function apiRequest(url, method = 'GET', body = null) {
    const options = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) options.body = JSON.stringify(body);

    const response = await fetch(url, options);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
}

async function loadPosts() {
    const list = document.getElementById('postList');
    list.innerHTML = '<div class="loading">加载中...</div>';

    const url = IS_DRAFTS ? `${API_BASE}/drafts` : `${API_BASE}/posts`;

    try {
        const data = await apiRequest(url);
        if (data.success) {
            allPosts = data.posts || [];
            if (!IS_DRAFTS) renderTopicTabs(allPosts);
            renderPosts(allPosts);
        } else {
            list.innerHTML = `<div class="empty-state"><p>❌ ${escapeHtml(data.message || '加载失败')}</p></div>`;
        }
    } catch (e) {
        list.innerHTML = `
            <div class="empty-state">
                <p>❌ 无法连接到服务器</p>
                <p style="font-size:0.85rem;margin-top:8px;">请确保 C++ 服务正在运行</p>
            </div>
        `;
    }
}

// 顶部专栏标签页
function renderTopicTabs(posts) {
    const container = document.getElementById('topicTabs');
    topicsList = [...new Set(posts.map(p => (p.topic || '').trim()).filter(Boolean))];

    if (topicsList.length === 0) {
        container.innerHTML = '';
        container.style.display = 'none';
        return;
    }
    container.style.display = 'flex';

    let html = `<button class="topic-tab${currentTopic === 'all' ? ' active' : ''}" data-index="-1">全部文章 <span class="topic-count">${posts.length}</span></button>`;

    topicsList.forEach((t, i) => {
        const count = posts.filter(p => (p.topic || '').trim() === t).length;
        html += `<button class="topic-tab${currentTopic === t ? ' active' : ''}" data-index="${i}">${escapeHtml(t)} <span class="topic-count">${count}</span></button>`;
    });

    container.innerHTML = html;
}

function renderPosts(posts) {
    const list = document.getElementById('postList');
    if (!IS_DRAFTS) {
        document.getElementById('pageTitle').textContent = currentTopic === 'all' ? '全部文章' : currentTopic;
    }

    const filtered = currentTopic === 'all'
        ? posts
        : posts.filter(p => (p.topic || '').trim() === currentTopic);

    if (!filtered.length) {
        if (IS_DRAFTS) {
            list.innerHTML = `
                <div class="empty-state">
                    <p>还没有草稿，点击右上角「写文章」开始创作吧！</p>
                </div>
            `;
        } else if (currentTopic === 'all') {
            list.innerHTML = `
                <div class="empty-state">
                    <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                        <line x1="12" y1="18" x2="12" y2="12"/>
                        <line x1="9" y1="15" x2="15" y2="15"/>
                    </svg>
                    <p>还没有文章，点击右上角「写文章」开始创作吧！</p>
                </div>
            `;
        } else {
            list.innerHTML = `
                <div class="empty-state">
                    <p>该专栏下还没有文章</p>
                </div>
            `;
        }
        return;
    }

    list.innerHTML = filtered.map(post => {
        const topic = (post.topic || '').trim();
        const topicBadge = topic
            ? `<span class="post-topic">${escapeHtml(topic)}</span>`
            : '';
        const isDraft = post.status === 'draft';
        const draftBadge = isDraft ? `<span class="post-draft">草稿</span>` : '';
        const href = isDraft ? `/editor?id=${post.id}` : `/post?id=${post.id}`;
        const actionLink = isDraft
            ? `<a class="read-more" href="${href}">继续编辑 →</a>`
            : `<a class="read-more" href="${href}">阅读全文 →</a>`;
        const summary = makeExcerpt(post);
        const updatedHtml = post.updated_at && post.updated_at !== post.created_at
            ? `<span class="sep">·</span><span>更新于 ${formatDate(post.updated_at)}</span>`
            : '';
        return `
            <article class="post-card">
                <h2 class="post-title"><a href="${href}">${escapeHtml(post.title)}</a></h2>
                <div class="post-meta">
                    ${draftBadge}
                    ${topicBadge}
                    <span>${escapeHtml(post.author || '匿名')}</span>
                    <span class="sep">·</span>
                    <span>${formatDate(post.created_at)}</span>
                    ${updatedHtml}
                </div>
                ${summary ? `<p class="post-excerpt">${escapeHtml(summary)}</p>` : ''}
                ${actionLink}
            </article>
        `;
    }).join('');
}

function makeExcerpt(post) {
    return (post.summary || '').trim();
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
