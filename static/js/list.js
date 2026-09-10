// ============================================
// 文章列表页逻辑
// ============================================

const API_BASE = '/api';

document.addEventListener('DOMContentLoaded', loadPosts);

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

    try {
        const data = await apiRequest(`${API_BASE}/posts`);
        if (data.success) {
            renderPosts(data.posts);
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

function renderPosts(posts) {
    const list = document.getElementById('postList');

    if (!posts.length) {
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
        return;
    }

    list.innerHTML = posts.map(post => `
        <article class="post-card">
            <h2 class="post-title"><a href="/post?id=${post.id}">${escapeHtml(post.title)}</a></h2>
            <div class="post-meta">
                <span>${escapeHtml(post.author || '匿名')}</span>
                <span class="sep">·</span>
                <span>${formatDate(post.created_at)}</span>
            </div>
            <p class="post-excerpt">${escapeHtml(makeExcerpt(post.content))}</p>
            <a class="read-more" href="/post?id=${post.id}">阅读全文 →</a>
        </article>
    `).join('');
}

function makeExcerpt(content) {
    const text = stripMarkdown(content || '');
    if (text.length <= 120) return text;
    return text.slice(0, 120) + '…';
}

// 去掉 Markdown 语法标记，生成纯文本摘要
function stripMarkdown(md) {
    return md
        .replace(/```[\s\S]*?```/g, ' ')      // 代码块
        .replace(/`[^`]*`/g, ' ')             // 行内代码
        .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1') // 图片
        .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')  // 链接
        .replace(/^#{1,6}\s+/gm, '')          // 标题
        .replace(/^\s*>\s?/gm, '')            // 引用
        .replace(/^\s*[-*+]\s+/gm, '')        // 无序列表
        .replace(/^\s*\d+\.\s+/gm, '')        // 有序列表
        .replace(/\*\*([^*]+)\*\*/g, '$1')    // 加粗
        .replace(/__([^_]+)__/g, '$1')        // 加粗
        .replace(/\*([^*]+)\*/g, '$1')        // 斜体
        .replace(/_([^_]+)_/g, '$1')          // 斜体
        .replace(/~~([^~]+)~~/g, '$1')        // 删除线
        .replace(/\s+/g, ' ')
        .trim();
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
