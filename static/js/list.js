// ============================================
// 文章列表页逻辑
// ============================================

const API_BASE = '/api';

// 草稿页模式（body 上 data-mode="drafts"）
const IS_DRAFTS = document.body.dataset.mode === 'drafts';
// 隐藏文章页模式（body 上 data-mode="hidden"）
const IS_HIDDEN = document.body.dataset.mode === 'hidden';

// 全部文章数据 + 当前选中的专栏（'all' 表示全部）
let allPosts = [];
let currentTopic = 'all';
let currentTheme = 'all';  // 当前选中的主题（'all' 表示未按主题筛选）
let topicsData = [];   // 站长维护的专栏列表 [{ id, name }]
let isAdmin = false;

// 点赞 / 评论统计小图标（内联 SVG，避免依赖 emoji 字体）
const LIKE_ICON = '<svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor" aria-hidden="true"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>';
const COMMENT_ICON = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';

document.addEventListener('DOMContentLoaded', async () => {
    await loadAuth();

    if (IS_HIDDEN) {
        await loadHiddenPage();
        const hiddenList = document.getElementById('postList');
        if (hiddenList) hiddenList.addEventListener('click', onHiddenListClick);
        return;
    }

    if (!IS_DRAFTS) await loadTopics();
    await loadPosts();

    if (IS_DRAFTS) {
        await loadHiddenPosts();
        const hiddenList = document.getElementById('hiddenList');
        if (hiddenList) hiddenList.addEventListener('click', onHiddenListClick);
    }

    // 顶部双层筛选条：第一行选专栏，第二行选主题
    const topicRow = document.getElementById('topicTabs');
    if (topicRow) {
        topicRow.addEventListener('click', (e) => {
            // 删除专栏（仅站长）
            const del = e.target.closest('.filter-tab-del');
            if (del) {
                handleDeleteTopic(Number(del.dataset.id));
                return;
            }
            // 新增专栏（仅站长）
            if (e.target.closest('.filter-tab-add')) {
                showTopicAdd();
                return;
            }
            const tab = e.target.closest('.filter-tab');
            if (!tab) return;
            currentTopic = tab.dataset.name;
            currentTheme = 'all';
            renderTopicTabs();
            renderThemeTabs();
            renderPosts();
        });
    }

    const themeRow = document.getElementById('themeTabs');
    if (themeRow) {
        themeRow.addEventListener('click', (e) => {
            const tab = e.target.closest('.filter-tab');
            if (!tab) return;
            const name = tab.dataset.name;
            // 再次点击已选中的主题可取消，回到该专栏全部
            currentTheme = (currentTheme === name && name !== 'all') ? 'all' : name;
            renderThemeTabs();
            renderPosts();
        });
    }

    if (!IS_DRAFTS) {
        document.getElementById('topicAddConfirm').addEventListener('click', handleAddTopic);
        document.getElementById('topicAddCancel').addEventListener('click', hideTopicAdd);
        document.getElementById('topicAddInput').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                handleAddTopic();
            }
        });
    }

    // 整张卡片可点击进入文章（点击链接时由链接自身处理，避免重复跳转）
    const list = document.getElementById('postList');
    list.addEventListener('click', (e) => {
        if (e.target.closest('a')) return;
        const card = e.target.closest('.post-card');
        if (!card || !card.dataset.href) return;
        window.location.href = card.dataset.href;
    });

    // 鼠标跟随的悬停提示框（显示标题与简介）
    const tooltip = document.createElement('div');
    tooltip.className = 'post-card-tooltip';
    tooltip.innerHTML = '<div class="post-card-tooltip-title"></div><div class="post-card-tooltip-summary"></div>';
    document.body.appendChild(tooltip);

    let hoverCard = null;

    function showTooltip(card) {
        const titleEl = card.querySelector('.post-title');
        const summaryEl = card.querySelector('.post-excerpt');
        tooltip.querySelector('.post-card-tooltip-title').textContent = titleEl ? titleEl.textContent.trim() : '';
        const summaryNode = tooltip.querySelector('.post-card-tooltip-summary');
        summaryNode.textContent = summaryEl ? summaryEl.textContent.trim() : '';
        summaryNode.style.display = summaryNode.textContent ? '' : 'none';
        tooltip.classList.add('visible');
    }

    function moveTooltip(x, y) {
        const OFFSET = 16;
        let left = x + OFFSET;
        let top = y + OFFSET;
        const rect = tooltip.getBoundingClientRect();
        if (left + rect.width > window.innerWidth - 8) left = x - rect.width - OFFSET;
        if (top + rect.height > window.innerHeight - 8) top = y - rect.height - OFFSET;
        tooltip.style.left = left + 'px';
        tooltip.style.top = top + 'px';
    }

    function hideTooltip() {
        tooltip.classList.remove('visible');
    }

    list.addEventListener('mouseover', (e) => {
        const card = e.target.closest('.post-card');
        if (card && card !== hoverCard) {
            hoverCard = card;
            showTooltip(card);
            moveTooltip(e.clientX, e.clientY);
        }
    });
    list.addEventListener('mousemove', (e) => {
        if (hoverCard) moveTooltip(e.clientX, e.clientY);
    });
    list.addEventListener('mouseout', (e) => {
        const card = e.target.closest('.post-card');
        if (card && hoverCard === card && !card.contains(e.relatedTarget)) {
            hoverCard = null;
            hideTooltip();
        }
    });
});

// 失败后等待（用于自动重试前的退避）
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// 把异常翻译成用户能看懂的文案：
// NETWORK = 网络层失败（服务没起 / 断网 / 连接被重置）；BAD_JSON = 返回内容不是合法 JSON
function describeFetchError(e) {
    const msg = (e && e.message) || '';
    if (msg === '未登录') return '登录状态已失效，正在跳转到登录页…';
    if (msg === 'NETWORK') return '网络连接失败，请检查网络后重试';
    if (msg === 'BAD_JSON') return '服务器返回的数据格式有误';
    const m = msg.match(/^HTTP (\d+)$/);
    if (m) {
        const code = Number(m[1]);
        if (code >= 500) return `服务器内部错误（${code}），请稍后重试`;
        if (code === 404) return `接口不存在（404），请确认服务端已更新`;
        if (code === 403) return `没有权限执行该操作（403）`;
        return `请求失败（${code}）`;
    }
    return '加载失败，请稍后重试';
}

async function apiRequest(url, method = 'GET', body = null, retry = true) {
    const options = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) options.body = JSON.stringify(body);

    let response;
    try {
        response = await fetch(url, options);
    } catch (e) {
        // 网络层失败：GET 请求自动重试一次，抵御瞬时抖动
        if (retry && method === 'GET') {
            await sleep(700);
            return apiRequest(url, method, body, false);
        }
        console.error('[list] 请求失败', url, e);
        throw new Error('NETWORK');
    }

    if (response.status === 401) {
        window.location.href = '/login';
        throw new Error('未登录');
    }
    if (!response.ok) {
        // 5xx 服务端错误：GET 请求自动重试一次
        if (retry && method === 'GET' && response.status >= 500) {
            await sleep(700);
            return apiRequest(url, method, body, false);
        }
        console.error('[list] HTTP 错误', url, response.status);
        throw new Error(`HTTP ${response.status}`);
    }

    try {
        return await response.json();
    } catch (e) {
        console.error('[list] JSON 解析失败', url, e);
        throw new Error('BAD_JSON');
    }
}

async function loadAuth() {
    try {
        const data = await apiRequest(`${API_BASE}/auth`);
        isAdmin = !!(data && data.authed);
    } catch (e) {
        isAdmin = false;
    }
}

async function loadTopics() {
    try {
        const data = await apiRequest(`${API_BASE}/topics`);
        if (data.success) topicsData = data.topics || [];
    } catch (e) {
        topicsData = [];
    }
}

async function loadPosts() {
    const list = document.getElementById('postList');
    list.innerHTML = '<div class="loading">加载中...</div>';

    const url = IS_DRAFTS ? `${API_BASE}/drafts` : `${API_BASE}/posts`;

    try {
        const data = await apiRequest(url);
        if (data.success) {
            allPosts = data.posts || [];
            if (!IS_DRAFTS) {
                renderTopicTabs();
                renderThemeTabs();
            }
            renderPosts();
        } else {
            list.innerHTML = `<div class="empty-state"><p>❌ ${escapeHtml(data.message || '加载失败')}</p></div>`;
        }
    } catch (e) {
        console.error('[list] 加载文章失败', e);
        list.innerHTML = `
            <div class="empty-state">
                <p>❌ ${escapeHtml(describeFetchError(e))}</p>
                <p style="font-size:0.85rem;margin-top:8px;">如果频繁出现，请确认 C++ 服务仍在运行</p>
                <button type="button" class="btn btn-secondary" id="retryLoadBtn" style="margin-top:14px;">重试</button>
            </div>
        `;
        const retryBtn = document.getElementById('retryLoadBtn');
        if (retryBtn) retryBtn.addEventListener('click', loadPosts);
    }
}

// 渲染隐藏文章卡片列表
function renderHiddenPosts(posts, list) {
    list.innerHTML = posts.map(post => {
        const href = post.status === 'draft' ? `/editor?id=${post.id}` : `/post?id=${post.id}`;
        return `
        <article class="post-card" data-href="${href}">
            <h2 class="post-title"><a href="${href}">${escapeHtml(post.title)}</a></h2>
            <div class="post-meta">
                <span class="post-hidden">已隐藏</span>
                <span>${escapeHtml(post.author || '匿名')}</span>
                <span class="sep">·</span>
                <span>${formatDate(post.created_at)}</span>
            </div>
            <button type="button" class="btn btn-secondary hidden-restore-btn" data-id="${post.id}">取消隐藏</button>
        </article>
    `;
    }).join('');
}

// 草稿页：加载已隐藏文章列表（主管理员看全部，普通管理员看自己的）
async function loadHiddenPosts() {
    const section = document.getElementById('hiddenSection');
    const list = document.getElementById('hiddenList');
    if (!section || !list) return;
    try {
        const data = await apiRequest(`${API_BASE}/hidden`);
        const posts = (data && data.success) ? (data.posts || []) : [];
        if (!posts.length) {
            section.hidden = true;
            return;
        }
        section.hidden = false;
        renderHiddenPosts(posts, list);
    } catch (e) {
        section.hidden = true;
    }
}

// 隐藏文章页：加载并渲染到主列表
async function loadHiddenPage() {
    const list = document.getElementById('postList');
    if (!list) return;
    list.innerHTML = '<div class="loading">加载中...</div>';
    try {
        const data = await apiRequest(`${API_BASE}/hidden`);
        const posts = (data && data.success) ? (data.posts || []) : [];
        if (!posts.length) {
            list.innerHTML = `<div class="empty-state"><p>暂无隐藏的文章</p></div>`;
            return;
        }
        renderHiddenPosts(posts, list);
    } catch (e) {
        console.error('[list] 加载隐藏文章失败', e);
        list.innerHTML = `
            <div class="empty-state">
                <p>❌ ${escapeHtml(describeFetchError(e))}</p>
                <button type="button" class="btn btn-secondary" id="retryHiddenBtn" style="margin-top:14px;">重试</button>
            </div>
        `;
        const retryBtn = document.getElementById('retryHiddenBtn');
        if (retryBtn) retryBtn.addEventListener('click', loadHiddenPage);
    }
}

// 草稿页：处理「取消隐藏」按钮点击，以及隐藏卡片整卡跳转
async function onHiddenListClick(e) {
    const btn = e.target.closest('.hidden-restore-btn');
    if (btn) {
        const id = Number(btn.dataset.id);
        btn.disabled = true;
        try {
            const data = await apiRequest(`${API_BASE}/posts/${id}/hidden`, 'PUT', { hidden: false });
            if (data.success) {
                showToast('文章已恢复显示');
                if (IS_HIDDEN) await loadHiddenPage();
                else await loadHiddenPosts();
            } else {
                showToast(data.message || '操作失败', 'error');
                btn.disabled = false;
            }
        } catch (err) {
            showToast('操作失败，请稍后重试', 'error');
            btn.disabled = false;
        }
        return;
    }
    if (e.target.closest('a')) return;
    const card = e.target.closest('.post-card');
    if (card && card.dataset.href) window.location.href = card.dataset.href;
}

// 筛选条第一层：专栏（全部文章 + 各专栏 + 站长的「＋ 专栏」）
function renderTopicTabs() {
    const container = document.getElementById('topicTabs');
    if (!container) return;

    // 非站长且一个专栏都没有时，整行没必要出现
    if (!isAdmin && topicsData.length === 0) {
        container.innerHTML = '';
        container.hidden = true;
        return;
    }
    container.hidden = false;

    let html = '<span class="filter-label">专栏</span>';
    html += `<span class="filter-tab${currentTopic === 'all' ? ' active' : ''}" data-name="all">全部文章</span>`;

    topicsData.forEach(t => {
        const delBtn = isAdmin
            ? `<button type="button" class="filter-tab-del" data-id="${t.id}" title="删除专栏">×</button>`
            : '';
        html += `<span class="filter-tab${currentTopic === t.name ? ' active' : ''}" data-name="${escapeAttr(t.name)}">${escapeHtml(t.name)}${delBtn}</span>`;
    });

    if (isAdmin) {
        html += '<span class="filter-tab filter-tab-add" id="addTopicToggle">＋ 专栏</span>';
    }

    container.innerHTML = html;
}

// 筛选条第二层：主题（随选中专栏变化；选中「全部文章」时列出所有主题）
function renderThemeTabs() {
    const container = document.getElementById('themeTabs');
    if (!container) return;

    const inTopic = (p) => currentTopic === 'all' || (p.topic || '').trim() === currentTopic;

    const themes = [];
    const seen = new Set();
    allPosts.forEach(p => {
        if (!inTopic(p)) return;
        const th = (p.theme || '').trim();
        if (!th || seen.has(th)) return;
        seen.add(th);
        themes.push(th);
    });

    // 没有主题时整行隐藏，只留一层筛选
    if (!themes.length) {
        container.innerHTML = '';
        container.hidden = true;
        return;
    }
    container.hidden = false;

    themes.forEach(th => {
        html += `<span class="filter-tab${currentTheme === th ? ' active' : ''}" data-name="${escapeAttr(th)}">${escapeHtml(th)}</span>`;
    });

    container.innerHTML = html;
}

function renderPosts() {
    const list = document.getElementById('postList');
    if (!IS_DRAFTS) {
        let title = '全部文章';
        if (currentTheme !== 'all') title = currentTheme;
        else if (currentTopic !== 'all') title = currentTopic;
        document.getElementById('pageTitle').textContent = title;
    }

    const filtered = allPosts.filter(p => {
        if (currentTopic !== 'all' && (p.topic || '').trim() !== currentTopic) return false;
        if (currentTheme !== 'all' && (p.theme || '').trim() !== currentTheme) return false;
        return true;
    });

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
        const theme = (post.theme || '').trim();
        const topicBadge = topic
            ? `<span class="post-topic">${escapeHtml(topic)}</span>`
            : '';
        const themeBadge = theme
            ? `<span class="post-theme">${escapeHtml(theme)}</span>`
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
        const statsHtml = IS_DRAFTS ? '' : `
            <span class="sep">·</span>
            <span class="post-stat post-stat-like">${LIKE_ICON}<span>${post.likes || 0}</span></span>
            <span class="post-stat post-stat-comment">${COMMENT_ICON}<span>${post.comment_count || 0}</span></span>
        `;
        return `
            <article class="post-card" data-href="${href}">
                <h2 class="post-title"><a href="${href}">${escapeHtml(post.title)}</a></h2>
                <div class="post-meta">
                    ${draftBadge}
                    ${topicBadge}
                    ${themeBadge}
                    <span>${escapeHtml(post.author || '匿名')}</span>
                    <span class="sep">·</span>
                    <span>${formatDate(post.created_at)}</span>
                    ${updatedHtml}
                    ${statsHtml}
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

// ===== 专栏管理（仅站长） =====
function showTopicAdd() {
    const add = document.getElementById('topicAdd');
    if (add) add.hidden = false;
    const input = document.getElementById('topicAddInput');
    if (input) {
        input.value = '';
        input.focus();
    }
}

function hideTopicAdd() {
    const add = document.getElementById('topicAdd');
    if (add) add.hidden = true;
}

async function handleAddTopic() {
    const input = document.getElementById('topicAddInput');
    const name = input.value.trim();
    if (!name) {
        showToast('请输入专栏名称', 'error');
        return;
    }
    try {
        const data = await apiRequest(`${API_BASE}/topics`, 'POST', { name });
        if (data.success) {
            showToast('专栏已添加');
            hideTopicAdd();
            await loadTopics();
            renderTopicTabs();
            renderThemeTabs();
        } else {
            showToast(data.message || '添加失败', 'error');
        }
    } catch (e) {
        showToast('添加失败，请稍后重试', 'error');
    }
}

async function handleDeleteTopic(id) {
    if (!confirm('确定要删除这个专栏吗？已有文章不会受到影响。')) return;
    try {
        const data = await apiRequest(`${API_BASE}/topics/${id}`, 'DELETE');
        if (data.success) {
            const deleted = topicsData.find(t => t.id === id);
            if (deleted && currentTopic === deleted.name) {
                currentTopic = 'all';
                currentTheme = 'all';
            }
            showToast('专栏已删除');
            await loadTopics();
            renderTopicTabs();
            renderThemeTabs();
            renderPosts();
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

// 转义用于 HTML 属性值（额外转义双引号，避免属性被截断）
function escapeAttr(text) {
    return escapeHtml(text).replace(/"/g, '&quot;');
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
