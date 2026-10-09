// ============================================
// 每日一题：今日题目 / 题库浏览 / 历史题目 / 站长题库管理
// 依赖：markdown.js（renderMarkdownInto）、auth.js（控制站长面板显隐）
// ============================================

const DAILY_API = '/api';

const dailyState = {
    category: '',
    page: 1,
    hasMore: false,
    isMain: false,
    editingId: 0,
    today: null
};

// ---------- 基础工具 ----------

function esc(text) {
    return String(text == null ? '' : text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function escapeAttr(text) {
    return esc(text).replace(/`/g, '&#96;');
}

function difficultyLabel(level) {
    if (Number(level) === 1) return '基础';
    if (Number(level) === 3) return '困难';
    return '进阶';
}

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

function describeFetchError(e) {
    const msg = e && e.message ? String(e.message) : '';
    if (msg === 'NETWORK') return '网络连接失败，请检查网络后重试';
    if (msg === 'BAD_JSON') return '服务端返回的数据异常，请稍后重试';
    const status = e && e.status;
    if (status === 403) return '没有权限执行该操作';
    if (status === 404) return '请求的内容不存在（404）';
    if (status >= 500) return `服务器内部错误（${status}），请稍后重试`;
    if (e && e.serverMessage) return e.serverMessage;
    return msg || '加载失败，请稍后重试';
}

// GET 请求失败自动重试一次：瞬时抖动可自愈
async function apiRequest(url, method = 'GET', body = null, retry = true) {
    const options = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) options.body = JSON.stringify(body);

    let response;
    try {
        response = await fetch(url, options);
    } catch (e) {
        if (retry && method === 'GET') {
            await sleep(700);
            return apiRequest(url, method, body, false);
        }
        console.error('[daily] 请求失败', url, e);
        throw new Error('NETWORK');
    }

    if (!response.ok) {
        if (retry && method === 'GET' && response.status >= 500) {
            await sleep(700);
            return apiRequest(url, method, body, false);
        }
        let serverMessage = '';
        try {
            const errBody = await response.json();
            serverMessage = (errBody && errBody.message) || '';
        } catch (e) { /* 响应不是 JSON，忽略 */ }
        console.error('[daily] HTTP 错误', url, response.status, serverMessage);
        const err = new Error(serverMessage || `HTTP ${response.status}`);
        err.status = response.status;
        err.serverMessage = serverMessage;
        throw err;
    }

    try {
        return await response.json();
    } catch (e) {
        console.error('[daily] JSON 解析失败', url, e);
        throw new Error('BAD_JSON');
    }
}

function showToast(message, type = 'success') {
    const old = document.querySelector('.toast');
    if (old) old.remove();
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2600);
}

// ---------- 今日题目 ----------

async function loadToday() {
    const box = document.getElementById('todayCard');
    if (!box) return;
    try {
        const data = await apiRequest(`${DAILY_API}/daily`);
        dailyState.today = data;
        renderCard(box, data, true);
    } catch (e) {
        box.innerHTML = `
            <div class="empty-state">
                <p>${esc(describeFetchError(e))}</p>
                <button type="button" class="btn btn-secondary" id="retryToday">重试</button>
            </div>`;
        const btn = document.getElementById('retryToday');
        if (btn) btn.addEventListener('click', loadToday);
    }
}

// 渲染题目卡片（今日题目与随机一题共用）
function renderCard(box, data, isDaily) {
    if (!data || !data.available) {
        box.innerHTML = `
            <div class="empty-state">
                <p>${esc((data && data.message) || '题库里还没有已发布的题目')}</p>
                <p class="daily-empty-hint">站长可在页面底部「题库管理」里添加，或导入 tools/seed_questions.sql</p>
            </div>`;
        return;
    }

    const streakText = data.streak > 0 ? `连答 ${data.streak} 天` : '';
    box.innerHTML = `
        <div class="daily-card-head">
            <span class="daily-badge">${isDaily ? '每日一题' : '随机一题'}</span>
            <span class="daily-date">${esc(data.date || '')}</span>
            <span class="daily-meta">${esc(data.category || '')} · ${difficultyLabel(data.difficulty)}</span>
        </div>
        <p class="daily-question">${esc(data.question || '')}</p>
        ${data.tags ? `<p class="daily-tags">${esc(data.tags)}</p>` : ''}
        <div class="daily-actions">
            <button type="button" class="btn btn-primary" id="revealBtn">查看答案</button>
            ${isDaily
                ? '<button type="button" class="btn btn-secondary" id="randomBtn">换一题</button>'
                : '<button type="button" class="btn btn-secondary" id="backTodayBtn">回到今日题目</button>'}
            <span class="daily-streak" id="streakBadge">${esc(streakText)}</span>
        </div>
        <div class="daily-answer" id="cardAnswer" hidden></div>
    `;

    const answerBox = document.getElementById('cardAnswer');
    const revealBtn = document.getElementById('revealBtn');
    revealBtn.addEventListener('click', () => revealAnswer(revealBtn, data.id, answerBox));

    if (isDaily) {
        document.getElementById('randomBtn').addEventListener('click', loadRandomQuestion);
    } else {
        document.getElementById('backTodayBtn').addEventListener('click', () => {
            renderCard(document.getElementById('todayCard'), dailyState.today, true);
        });
    }
}

async function loadRandomQuestion() {
    const box = document.getElementById('todayCard');
    const btn = document.getElementById('randomBtn');
    if (btn) btn.disabled = true;
    try {
        let url = `${DAILY_API}/daily/random`;
        if (dailyState.category) url += '?category=' + encodeURIComponent(dailyState.category);
        const data = await apiRequest(url);
        if (!data.success) {
            showToast(data.message || '没有可换的题目', 'error');
            return;
        }
        data.date = '';
        renderCard(box, data, false);
    } catch (e) {
        showToast(describeFetchError(e), 'error');
    } finally {
        if (btn) btn.disabled = false;
    }
}

// 展开 / 收起答案：答案走单独接口，避免在列表里就剧透
async function revealAnswer(btn, id, container) {
    if (!container.hidden) {
        container.hidden = true;
        btn.textContent = '查看答案';
        return;
    }

    btn.disabled = true;
    try {
        const data = await apiRequest(`${DAILY_API}/daily/answer?id=${encodeURIComponent(id)}`);
        if (!data.success) {
            showToast(data.message || '答案加载失败', 'error');
            return;
        }
        container.innerHTML = '<div class="daily-answer-label">参考答案</div><div class="markdown-body"></div>';
        renderMarkdownInto(container.querySelector('.markdown-body'), data.answer);
        container.hidden = false;
        btn.textContent = '收起答案';

        if (data.streak > 0) {
            const badge = document.getElementById('streakBadge');
            if (badge) badge.textContent = `连答 ${data.streak} 天`;
        }
    } catch (e) {
        showToast(describeFetchError(e), 'error');
    } finally {
        btn.disabled = false;
    }
}

// ---------- 题库 ----------

async function loadBank(reset) {
    const list = document.getElementById('questionList');
    if (!list) return;
    if (reset) dailyState.page = 1;

    try {
        let url = `${DAILY_API}/questions?page=${dailyState.page}&page_size=10`;
        if (dailyState.category) url += '&category=' + encodeURIComponent(dailyState.category);
        if (dailyState.isMain) url += '&with_drafts=1';

        const data = await apiRequest(url);
        dailyState.hasMore = !!data.hasMore;

        const html = buildBankItems(data.questions || []);
        if (reset) {
            list.innerHTML = html || '<div class="empty-state"><p>这个分类下还没有题目</p></div>';
        } else {
            list.insertAdjacentHTML('beforeend', html);
        }

        const moreBtn = document.getElementById('loadMoreBtn');
        if (moreBtn) moreBtn.hidden = !dailyState.hasMore;

        const count = document.getElementById('bankCount');
        if (count) count.textContent = data.total ? `共 ${data.total} 题` : '';

        if (reset) renderCategoryTabs(data.categories || []);

        if (!reset && !html) showToast('没有更多了', 'error');
    } catch (e) {
        if (reset) {
            list.innerHTML = `<div class="empty-state"><p>${esc(describeFetchError(e))}</p></div>`;
        } else {
            showToast(describeFetchError(e), 'error');
        }
    }
}

function buildBankItems(questions) {
    return questions.map((q) => `
        <article class="daily-item" data-id="${q.id}">
            <div class="daily-item-head">
                <span class="daily-item-cat">${esc(q.category)}</span>
                <span class="daily-item-diff">${difficultyLabel(q.difficulty)}</span>
                ${Number(q.status) === 0 ? '<span class="daily-item-draft">草稿</span>' : ''}
                <span class="daily-item-id">#${q.id}</span>
            </div>
            <p class="daily-item-question">${esc(q.question)}</p>
            <div class="daily-item-actions">
                <button type="button" class="daily-link q-reveal">查看答案</button>
                ${dailyState.isMain
                    ? '<button type="button" class="daily-link q-edit">编辑</button><button type="button" class="daily-link daily-link-danger q-del">删除</button>'
                    : ''}
            </div>
            <div class="daily-item-answer" hidden></div>
        </article>`).join('');
}

function renderCategoryTabs(categories) {
    const box = document.getElementById('categoryTabs');
    if (!box) return;

    let html = '<span class="filter-label">分类</span>';
    html += `<span class="filter-tab${dailyState.category === '' ? ' active' : ''}" data-name="">全部</span>`;
    categories.forEach((c) => {
        html += `<span class="filter-tab${dailyState.category === c.name ? ' active' : ''}" data-name="${escapeAttr(c.name)}">${esc(c.name)}</span>`;
    });
    box.innerHTML = html;

    const datalist = document.getElementById('categoryOptions');
    if (datalist) {
        datalist.innerHTML = categories.map((c) => `<option value="${escapeAttr(c.name)}"></option>`).join('');
    }
}

// ---------- 历史题目 ----------

async function loadHistory() {
    const box = document.getElementById('historyList');
    if (!box) return;
    try {
        const data = await apiRequest(`${DAILY_API}/daily/history?page=1`);
        const items = data.questions || [];
        if (!items.length) {
            box.innerHTML = '<div class="empty-state"><p>还没有历史记录</p></div>';
            return;
        }
        box.innerHTML = items.map((h) => `
            <div class="daily-history-row">
                <span class="daily-history-date">${esc(h.date)}</span>
                <span class="daily-history-q">${esc(h.question || '（题目已删除）')}</span>
                <span class="daily-history-cat">${esc(h.category || '')}</span>
            </div>`).join('');
    } catch (e) {
        box.innerHTML = `<div class="empty-state"><p>${esc(describeFetchError(e))}</p></div>`;
    }
}

// ---------- 站长：题库管理 ----------

function resetQuestionForm() {
    dailyState.editingId = 0;
    const form = document.getElementById('questionForm');
    if (form) form.reset();
    document.getElementById('qSaveBtn').textContent = '添加题目';
    document.getElementById('qCancelBtn').hidden = true;
    document.getElementById('qFormHint').textContent = '';
}

async function startEditQuestion(id) {
    try {
        const data = await apiRequest(`${DAILY_API}/questions/${id}`);
        if (!data.success) {
            showToast(data.message || '读取失败', 'error');
            return;
        }
        document.getElementById('qCategory').value = data.category || '';
        document.getElementById('qTags').value = data.tags || '';
        document.getElementById('qDifficulty').value = String(data.difficulty || 2);
        document.getElementById('qStatus').value = String(data.status || 0);
        document.getElementById('qQuestion').value = data.question || '';
        document.getElementById('qAnswer').value = data.answer || '';

        dailyState.editingId = id;
        document.getElementById('qSaveBtn').textContent = '保存修改';
        document.getElementById('qCancelBtn').hidden = false;
        document.getElementById('qFormHint').textContent = `正在编辑 #${id}`;

        document.getElementById('bankPanel').hidden = false;
        document.getElementById('bankToggle').setAttribute('aria-expanded', 'true');
        document.getElementById('bankAdmin').scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (e) {
        showToast(describeFetchError(e), 'error');
    }
}

async function submitQuestionForm(e) {
    e.preventDefault();

    const payload = {
        category: document.getElementById('qCategory').value.trim(),
        tags: document.getElementById('qTags').value.trim(),
        difficulty: Number(document.getElementById('qDifficulty').value),
        question: document.getElementById('qQuestion').value,
        answer: document.getElementById('qAnswer').value,
        status: Number(document.getElementById('qStatus').value)
    };
    if (!payload.category || !payload.question.trim() || !payload.answer.trim()) {
        showToast('分类、题干、答案都不能为空', 'error');
        return;
    }

    const btn = document.getElementById('qSaveBtn');
    btn.disabled = true;
    const isEdit = dailyState.editingId > 0;
    try {
        const url = isEdit ? `${DAILY_API}/questions/${dailyState.editingId}` : `${DAILY_API}/questions`;
        const data = await apiRequest(url, isEdit ? 'PUT' : 'POST', payload);
        if (data.success) {
            showToast(isEdit ? '已保存' : '已添加');
            resetQuestionForm();
            dailyState.category = '';
            loadBank(true);
            loadToday(); // 题库从空变有题时，今日题目卡片要跟着刷新
        } else {
            showToast(data.message || '保存失败', 'error');
        }
    } catch (e) {
        showToast(describeFetchError(e), 'error');
    } finally {
        btn.disabled = false;
    }
}

async function removeQuestion(id) {
    if (!confirm(`确定删除题目 #${id} 吗？\n\n此操作不可撤销，题库中该题将被永久删除（已排期的历史日期会保留，但题目内容显示为空）。`)) {
        return;
    }
    try {
        const data = await apiRequest(`${DAILY_API}/questions/${id}`, 'DELETE');
        if (data.success) {
            showToast('已删除');
            loadBank(true);
        } else {
            showToast(data.message || '删除失败', 'error');
        }
    } catch (e) {
        showToast(describeFetchError(e), 'error');
    }
}

// ---------- 事件绑定 ----------

function bindDailyEvents() {
    const tabs = document.getElementById('categoryTabs');
    if (tabs) {
        tabs.addEventListener('click', (e) => {
            const tab = e.target.closest('.filter-tab');
            if (!tab) return;
            dailyState.category = tab.dataset.name || '';
            loadBank(true);
        });
    }

    const moreBtn = document.getElementById('loadMoreBtn');
    if (moreBtn) {
        moreBtn.addEventListener('click', () => {
            dailyState.page += 1;
            loadBank(false);
        });
    }

    const list = document.getElementById('questionList');
    if (list) {
        list.addEventListener('click', (e) => {
            const item = e.target.closest('.daily-item');
            if (!item) return;
            const id = Number(item.dataset.id);

            if (e.target.closest('.q-reveal')) {
                revealAnswer(e.target.closest('.q-reveal'), id, item.querySelector('.daily-item-answer'));
            } else if (e.target.closest('.q-edit')) {
                startEditQuestion(id);
            } else if (e.target.closest('.q-del')) {
                removeQuestion(id);
            }
        });
    }

    const toggle = document.getElementById('bankToggle');
    if (toggle) {
        toggle.addEventListener('click', () => {
            const panel = document.getElementById('bankPanel');
            const willOpen = panel.hidden;
            panel.hidden = !panel.hidden;
            toggle.setAttribute('aria-expanded', String(willOpen));
        });
    }

    const form = document.getElementById('questionForm');
    if (form) form.addEventListener('submit', submitQuestionForm);

    const cancelBtn = document.getElementById('qCancelBtn');
    if (cancelBtn) cancelBtn.addEventListener('click', resetQuestionForm);
}

async function initDailyPage() {
    bindDailyEvents();
    loadToday();
    loadHistory();

    // 站长身份决定题库列表是否含草稿、以及是否显示管理面板
    try {
        const auth = await apiRequest(`${DAILY_API}/auth`);
        dailyState.isMain = !!(auth && auth.is_main);
    } catch (e) {
        dailyState.isMain = false;
    }
    loadBank(true);
}

document.addEventListener('DOMContentLoaded', initDailyPage);
