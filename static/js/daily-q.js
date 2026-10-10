// ============================================
// 题目详情页（/daily/q/<id>）：题干 + 参考答案 + 右侧「同分类相关题」
// 依赖：daily-common.js（apiRequest / esc / difficultyLabel / describeFetchError）
//       markdown.js（renderMarkdownInto）、auth.js（站长的「编辑此题」按钮显隐）
//
// 数据一次取全：GET /api/daily/question?id=<id>
//   → { success, id, category, tags, difficulty, question, answer, date, siblings[] }
// date 是该题最近一次被排为「每日一题」的日期；从历史列表点进来时 URL 带 ?d=，
// 那个日期更精确（历史上的题可能被排期多次），所以优先用 URL 里的。
//
// 本页不吃匿名打卡：详情页是「查资料」，不该顺手把当天算成已作答。
// ============================================

const qState = { id: 0, sourceDate: '' };

// 从 /daily/q/12 中取出 12
function parseQuestionId() {
    const m = /\/daily\/q\/(\d+)/.exec(String(window.location.pathname || ''));
    return m ? Number(m[1]) : 0;
}

// 从 ?d=2026-10-08 中取出日期（历史题目点进来时带上）
function parseSourceDate() {
    const m = /[?&]d=(\d{4}-\d{2}-\d{2})/.exec(String(window.location.search || ''));
    return m ? m[1] : '';
}

// 右栏相关题是「有内容才成立」的一栏：没有相关题（或加载失败）就整栏收起，
// 同时撤掉 .has-related 让主栏回到居中单列 —— 否则右栏会留一块空卡片，
// 主栏也被一条无内容的列挤窄。
function setRelatedVisible(visible) {
    const aside = document.getElementById('qRelated');
    if (aside) aside.hidden = !visible;

    const layout = document.getElementById('qDetailLayout');
    if (layout) layout.classList.toggle('has-related', visible);
}

function renderDetailError(box, message) {
    box.innerHTML = `
        <div class="empty-state">
            <p>${esc(message)}</p>
            <a class="btn btn-secondary" href="/daily">返回每日一题</a>
        </div>`;

    setRelatedVisible(false);
}

function renderDetail(box, data) {
    const date = qState.sourceDate || data.date || '';
    const isDaily = !!date;
    const tags = String(data.tags || '').trim();

    box.innerHTML = `
        <div class="daily-card-head">
            <span class="daily-badge">${isDaily ? '每日一题' : '题库题目'}</span>
            ${date ? `<span class="daily-date">${esc(date)}</span>` : ''}
            <span class="daily-meta">${esc(data.category || '')} · ${esc(difficultyLabel(data.difficulty))}</span>
            <span class="daily-item-id">#${esc(data.id)}</span>
        </div>
        <h1 class="qdetail-question">${esc(data.question || '')}</h1>
        ${tags ? `<p class="daily-tags">${esc(tags)}</p>` : ''}
        <div class="qdetail-rule"></div>
        <div class="daily-answer-label">参考答案</div>
        <div class="markdown-body" id="qAnswerBody"></div>`;

    const body = document.getElementById('qAnswerBody');
    if (body) renderMarkdownInto(body, data.answer || '（这道题还没有写答案）');
}

function renderRelated(data) {
    const list = document.getElementById('qRelatedList');
    const title = document.getElementById('qRelatedTitle');
    if (!list) return;

    const items = data.siblings || [];
    if (!items.length) {
        setRelatedVisible(false);
        return;
    }

    if (title) title.textContent = data.category ? `同分类相关题 · ${data.category}` : '相关题目';

    list.innerHTML = items.map((q) => `
        <a class="qdetail-related-item" href="/daily/q/${encodeURIComponent(q.id)}">
            <span class="qdetail-related-q">${esc(q.question || '')}</span>
            <span class="qdetail-related-diff">${esc(difficultyLabel(q.difficulty))}</span>
        </a>`).join('');
    setRelatedVisible(true);
}

async function loadDetail() {
    const box = document.getElementById('qDetail');
    if (!box) return;

    if (!qState.id) {
        renderDetailError(box, '这个链接里没有题目编号，可能被截断了');
        return;
    }

    try {
        const data = await apiRequest(`${DAILY_API}/daily/question?id=${encodeURIComponent(qState.id)}`);
        if (!data || !data.success) {
            renderDetailError(box, (data && data.message) || '题目不存在或尚未发布');
            return;
        }
        renderDetail(box, data);
        renderRelated(data);
        document.title = `${data.question || '题目详情'} · LazyCat's Blog`;
    } catch (e) {
        renderDetailError(box, describeFetchError(e));
    }
}

function initDetailPage() {
    qState.id = parseQuestionId();
    qState.sourceDate = parseSourceDate();

    // 「编辑此题」由 auth.js 按 data-auth-role="main" 控制显隐，这里只负责把 id 填进链接
    const editLink = document.getElementById('qEditLink');
    if (editLink && qState.id) editLink.href = `/daily/question?id=${encodeURIComponent(qState.id)}`;

    loadDetail();
}

document.addEventListener('DOMContentLoaded', initDetailPage);
