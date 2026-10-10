// ============================================
// 每日一题（/daily）：今日题目 / 题库浏览 / 历史题目 / 打卡与题库分布
// 依赖：daily-common.js（apiRequest / showToast / esc 等工具，必须先加载）
//       markdown.js（renderMarkdownInto）、auth.js（控制站长入口显隐）
// 三栏：左=历史题目，中=今日题目+题库，右=打卡/题库分布/题目管理
// 出题 / 改题已拆到独立页面 /daily/question（见 daily-question.js）
// ============================================

const dailyState = {
    category: '',
    page: 1,
    hasMore: false,
    isMain: false,
    today: null
};

// ---------- 今日题目 ----------

async function loadToday() {
    const box = document.getElementById('todayCard');
    if (!box) return;
    try {
        const data = await apiRequest(`${DAILY_API}/daily`);
        dailyState.today = data;
        renderCard(box, data, true);
        renderStreakCard(data);
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
                <p class="daily-empty-hint">站长可在右侧「题目管理」里点「添加题目」，或导入 tools/seed_questions.sql</p>
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
        // 揭晓答案即代表今天已作答（后端按 d + owner_token 记打卡），右栏打卡卡跟着更新
        renderStreakCard(Object.assign({}, dailyState.today, { streak: data.streak, answered: true }));
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

        if (reset) {
            renderCategoryTabs(data.categories || []);
            renderCategoryDist(data.categories || []);
        }

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
                    ? `<a class="daily-link" href="/daily/question?id=${q.id}">编辑</a><button type="button" class="daily-link daily-link-danger q-del">删除</button>`
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
}

// ---------- 右栏：题库分布 ----------
// 数据来自题库接口已有的 categories（含各分类题量），点一行即筛选题库。
// 接口返回的 categories 不受当前分类影响（始终是全量），所以这里不需要额外请求。

function renderCategoryDist(categories) {
    const box = document.getElementById('catDist');
    if (!box) return;

    if (!categories.length) {
        box.innerHTML = '<p class="cat-dist-empty">题库还是空的</p>';
        return;
    }

    const counts = categories.map((c) => Number(c.count) || 0);
    const max = Math.max.apply(null, counts) || 1;

    box.innerHTML = categories.map((c, i) => {
        const count = counts[i];
        const pct = Math.max(5, Math.round((count / max) * 100));
        const active = dailyState.category === c.name ? ' active' : '';
        return `<button type="button" class="cat-dist-row${active}" data-name="${escapeAttr(c.name)}">
            <span class="cat-dist-name">${esc(c.name)}</span>
            <span class="cat-dist-count">${count}</span>
            <span class="cat-dist-bar"><i style="width:${pct}%"></i></span>
        </button>`;
    }).join('');
}

// ---------- 右栏：我的打卡 ----------

const WEEK_LABELS = ['日', '一', '二', '三', '四', '五', '六'];

function pad2(n) {
    return n < 10 ? '0' + n : String(n);
}

function ymd(d) {
    return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

// 后端只返回 streak（连续作答天数）与 answered（今天是否已答），
// 但这两者已经唯一确定「已作答的日期集合」：从今天（已答）或昨天（未答）往前连续 streak 天。
// 因此近 7 天格子无需新增接口。
function renderStreakCard(data) {
    const numEl = document.getElementById('streakNum');
    const statusEl = document.getElementById('streakStatus');
    const weekEl = document.getElementById('streakWeek');
    if (!numEl || !statusEl || !weekEl) return;

    const streak = Number((data && data.streak) || 0);
    const answered = !!(data && data.answered);
    numEl.textContent = String(streak);

    if (!data || !data.available || !data.date) {
        statusEl.textContent = '题库还没有已发布的题目';
        weekEl.innerHTML = '';
        return;
    }

    statusEl.textContent = answered ? `今日已作答 · ${data.date}` : '今日尚未作答';

    const parts = String(data.date).split('-').map(Number);
    const base = new Date(parts[0], parts[1] - 1, parts[2]);
    if (isNaN(base.getTime())) {
        weekEl.innerHTML = '';
        return;
    }

    const done = new Set();
    const startOffset = answered ? 0 : 1;
    for (let i = 0; i < streak && i < 60; i++) {
        done.add(ymd(new Date(base.getFullYear(), base.getMonth(), base.getDate() - startOffset - i)));
    }

    const todayKey = ymd(base);
    let html = '';
    for (let i = 6; i >= 0; i--) {
        const d = new Date(base.getFullYear(), base.getMonth(), base.getDate() - i);
        const key = ymd(d);
        const isToday = key === todayKey;
        const cls = `streak-day${done.has(key) ? ' on' : ''}${isToday ? ' today' : ''}`;
        html += `<div class="${cls}" title="${key}">
            <span class="streak-dot"></span>
            <span class="streak-day-label">${isToday ? '今' : WEEK_LABELS[d.getDay()]}</span>
        </div>`;
    }
    weekEl.innerHTML = html;
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

// ---------- 站长：删除题目 ----------
// 出题与改题都在独立页面 /daily/question（见 daily-question.js），
// 这里只保留列表里就地的「删除」，因为它需要当场确认。

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

    // 右栏「题库分布」：点分类即等同于点中栏的分类筛选
    const dist = document.getElementById('catDist');
    if (dist) {
        dist.addEventListener('click', (e) => {
            const row = e.target.closest('.cat-dist-row');
            if (!row) return;
            const name = row.dataset.name || '';
            if (name === dailyState.category) return;

            dailyState.category = name;
            loadBank(true);

            // 窄屏下侧栏在题库下方，不把题库标题带回视口顶部会「看不到任何变化」。
            // window.scrollTo 在测试用的 DOM 桩里不存在，故做能力检测而非直接调用。
            const head = document.getElementById('bankSectionHead');
            if (head && typeof head.getBoundingClientRect === 'function' && typeof window.scrollTo === 'function') {
                window.scrollTo({
                    top: head.getBoundingClientRect().top + (window.pageYOffset || 0) - 88,
                    behavior: 'smooth'
                });
            }
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
            } else if (e.target.closest('.q-del')) {
                removeQuestion(id);
            }
        });
    }
}

async function initDailyPage() {
    bindDailyEvents();

    // 先取站长身份：它决定题库列表是否带出草稿；
    // 「添加题目」入口由 auth.js 按 data-auth-role 控制显隐。
    try {
        const auth = await apiRequest(`${DAILY_API}/auth`);
        dailyState.isMain = !!(auth && auth.is_main);
    } catch (e) {
        dailyState.isMain = false;
    }

    loadToday();
    loadHistory();
    loadBank(true);
}

document.addEventListener('DOMContentLoaded', initDailyPage);
