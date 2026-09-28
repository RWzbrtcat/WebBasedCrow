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
let expandedTopics = new Set();  // 左侧分类树中已展开的专栏名

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

    // 左侧分类树：专栏可展开主题，点击按专栏 / 主题筛选
    const sidebar = document.getElementById('themeSidebar');
    if (sidebar) {
        sidebar.addEventListener('click', (e) => {
            // 窄屏折叠开关
            const collapse = e.target.closest('.sidebar-collapse');
            if (collapse) {
                const body = document.getElementById('sidebarBody');
                const open = collapse.getAttribute('aria-expanded') === 'true';
                collapse.setAttribute('aria-expanded', open ? 'false' : 'true');
                if (body) body.classList.toggle('open', !open);
                return;
            }

            // 展开 / 收起专栏下的主题
            const caret = e.target.closest('.sidebar-caret');
            if (caret) {
                const name = caret.dataset.toggle;
                if (expandedTopics.has(name)) expandedTopics.delete(name);
                else expandedTopics.add(name);
                renderThemeSidebar();
                return;
            }

            // 删除专栏（仅站长）
            const del = e.target.closest('.sidebar-del');
            if (del) {
                handleDeleteTopic(Number(del.dataset.id));
                return;
            }

            const allBtn = e.target.closest('.sidebar-all');
            if (allBtn) {
                currentTopic = 'all';
                currentTheme = 'all';
                renderThemeSidebar();
                renderPosts();
                return;
            }

            const theme = e.target.closest('.sidebar-theme');
            if (theme) {
                const topic = theme.dataset.topic;
                const name = theme.dataset.name;
                if (currentTopic === topic && currentTheme === name) {
                    currentTheme = 'all';
                } else {
                    currentTopic = topic;
                    currentTheme = name;
                }
                renderThemeSidebar();
                renderPosts();
                return;
            }

            const topicBtn = e.target.closest('.sidebar-topic');
            if (topicBtn) {
                currentTopic = topicBtn.dataset.name;
                currentTheme = 'all';
                expandedTopics.add(currentTopic);
                renderThemeSidebar();
                renderPosts();
            }
        });
    }

    const tabs = document.getElementById('topicTabs');
    if (tabs) {
        tabs.addEventListener('click', (e) => {
            const addBtn = e.target.closest('.topic-tab-add');
            if (addBtn) showTopicAdd();
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
                renderThemeSidebar();
            }
            renderPosts();
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
        list.innerHTML = `
            <div class="empty-state">
                <p>❌ 无法连接到服务器</p>
                <p style="font-size:0.85rem;margin-top:8px;">请确保 C++ 服务正在运行</p>
            </div>
        `;
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

// 顶部标签区：专栏筛选已统一到左侧分类树，这里只保留站长的「新增专栏」入口
function renderTopicTabs() {
    const container = document.getElementById('topicTabs');
    if (!container) return;

    if (!isAdmin) {
        container.innerHTML = '';
        container.style.display = 'none';
        return;
    }
    container.style.display = 'flex';
    container.innerHTML = '<span class="topic-tab topic-tab-add" id="addTopicToggle">＋ 专栏</span>';
}

// 左侧分类树：专栏（可展开主题）+ 主题，默认展开当前选中专栏
function renderThemeSidebar() {
    const sidebar = document.getElementById('themeSidebar');
    if (!sidebar) return;

    // 按专栏收集主题（去重、保持文章出现顺序）
    const groups = topicsData.map(t => {
        const themes = [];
        const seen = new Set();
        allPosts.forEach(p => {
            if ((p.topic || '').trim() !== t.name) return;
            const theme = (p.theme || '').trim();
            if (!theme || seen.has(theme)) return;
            seen.add(theme);
            themes.push(theme);
        });
        return { id: t.id, name: t.name, themes };
    });

    if (topicsData.length === 0) {
        sidebar.innerHTML = '';
        sidebar.style.display = 'none';
        return;
    }
    sidebar.style.display = 'block';

    // 选中某专栏时自动展开它
    if (currentTopic !== 'all') expandedTopics.add(currentTopic);

    const countOf = (topic, theme) => allPosts.filter(p =>
        (p.topic || '').trim() === topic &&
        (!theme || (p.theme || '').trim() === theme)
    ).length;

    let html = `
        <div class="home-sidebar-title">专栏 · 主题</div>
        <button type="button" class="sidebar-collapse" id="sidebarCollapse" aria-expanded="false" aria-controls="sidebarBody">
            <span>专栏 · 主题</span><span class="sidebar-collapse-caret"></span>
        </button>
        <div class="sidebar-body" id="sidebarBody">
            <div class="sidebar-all${currentTopic === 'all' ? ' active' : ''}" data-name="all">全部文章<span class="sidebar-count">${allPosts.length}</span></div>
    `;

    groups.forEach(g => {
        const expanded = expandedTopics.has(g.name);
        const topicActive = currentTopic === g.name && currentTheme === 'all';
        const delBtn = isAdmin
            ? `<button type="button" class="sidebar-del" data-id="${g.id}" title="删除专栏">×</button>`
            : '';
        html += `<div class="sidebar-group">
            <div class="sidebar-topic-row">
                <button type="button" class="sidebar-caret${expanded ? ' open' : ''}" data-toggle="${escapeAttr(g.name)}" aria-label="展开主题" aria-expanded="${expanded}"></button>
                <span class="sidebar-topic${topicActive ? ' active' : ''}" data-name="${escapeAttr(g.name)}">${escapeHtml(g.name)}<span class="sidebar-count">${countOf(g.name)}</span></span>
                ${delBtn}
            </div>`;
        if (expanded && g.themes.length) {
            html += '<ul class="sidebar-theme-list">';
            g.themes.forEach(th => {
                const active = currentTopic === g.name && currentTheme === th;
                html += `<li class="sidebar-theme${active ? ' active' : ''}" data-topic="${escapeAttr(g.name)}" data-name="${escapeAttr(th)}">${escapeHtml(th)}<span class="sidebar-count">${countOf(g.name, th)}</span></li>`;
            });
            html += '</ul>';
        }
        html += '</div>';
    });

    html += '</div>';
    sidebar.innerHTML = html;
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
            expandedTopics.add(name);
            renderTopicTabs();
            renderThemeSidebar();
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
            if (deleted) {
                expandedTopics.delete(deleted.name);
                if (currentTopic === deleted.name) {
                    currentTopic = 'all';
                    currentTheme = 'all';
                }
            }
            showToast('专栏已删除');
            await loadTopics();
            renderTopicTabs();
            renderThemeSidebar();
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
