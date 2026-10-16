// ============================================
// 练习闯关：前端逻辑
// 布局：左栏「章节 + 当前章题目」两级树，右栏答题工作台
//       （题目描述卡 | 编辑器·作答卡 并排）。
//       描述卡内 = 标签栏「题目描述 | 题解 | 测试结果」共用一栏（默认题目描述，
//       点标签切换）；运行/提交后自动切到「测试结果」，无结果时显示空态或本题上次结果。
//       写代码题的编辑器卡 = IDE 观感（行号槽 + C++ 语法高亮叠加层 + 状态栏）。
// 数据全部来自后端接口：
//   GET  /api/practice/chapters            章节列表（按学期分组）
//   GET  /api/practice/exercises?chapter=N 某章题目列表
//   GET  /api/practice/exercise/<id>       单题详情（题干 + 题解 + 三档脚手架/选项）
//   GET  /api/practice/progress            服务端进度（按 blog_anon 回读已通过题目 id）
//   POST /api/practice/submit              写代码题：沙箱编译运行判定
//   POST /api/practice/answer              客观题（选择/填空）：对答案
// 题型：choice(选择) / blank(填空) / short(写代码) / boss(项目关)。
// 「已完成」状态 = 服务端进度（blog_anon 认领）∪ 本地 localStorage，启动时合并。
// 「本题上次运行结果」= 本地 localStorage 缓存（practice.last.v1，上限 40 题）。
// 依赖：daily-common.js（esc / showToast / apiRequest / describeFetchError）、
//       markdown.js（renderMarkdownInto，渲染题干与题解）、
//       highlight.min.js（hljs.highlight，编辑器 C++ 语法高亮）。
// ============================================
(function () {
    'use strict';

    // ---------- 常量 ----------
    const TIER_LABELS = { easy: '入门', medium: '进阶', hard: '挑战' };
    const TYPE_BADGES = { choice: '选择', blank: '填空', short: '写代码', boss: 'Boss' };
    const DONE_KEY = 'practice.done.v1';
    const LAST_KEY = 'practice.last.v1';    // 每题「上一次运行结果」缓存
    const LAST_MAX = 40;                    // 最多缓存多少题的最近结果
    const DRAFT_KEY = 'practice.draft.v1';  // 每题每档「代码草稿」缓存
    const DRAFT_MAX = 80;                   // 最多缓存多少份草稿
    const DRAFT_CODE_MAX = 20000;           // 单份草稿字符上限（保护 localStorage 配额）
    const TREE_KEY = 'practice.tree.v1';    // 左栏章节树「展开/折叠」状态缓存
    // ⚠ 以上常量必须在下面的状态初始化「之前」声明：loadDone / loadLastResults /
    //    loadDrafts 都会读取这些 const；若声明在后，读取会命中 TDZ 抛 ReferenceError，
    //    再被各自的 try/catch 静默吞掉 ⇒ 表现为「本地缓存永远读不出来」。
    //    （历史遗留坑，本次一并修正：此前本地 doneSet / lastResults 在启动时恒为空。）

    // ---------- 状态 ----------
    let chaptersData = null;      // /api/practice/chapters 返回的 semesters
    let currentChapter = null;    // 当前选中章节 id
    let chapterExercises = [];    // 当前章的题目列表
    let currentExercise = null;   // 当前题目详情（/api/practice/exercise/<id> 返回）
    let currentTier = 'easy';
    let doneSet = loadDone();     // 本地记录：已通过的题目 id
    let lastResults = loadLastResults();  // 本地记录：每题最近一次运行结果（{ id: {cls, html} }）
    let drafts = loadDrafts();    // 本地记录：代码草稿（{ '<id>:<tier>': code }，防切题/刷新丢代码）

    // 左栏章节树「展开 / 折叠」状态（可独立展开多个章节，互不影响）：
    //   openChapters        = 已展开的章节 id 集合
    //   collapsedSemesters  = 已折叠的学期名集合（默认全展开）
    //   chapterExercisesCache = { chapterId: [exercises] }，已展开章节直接渲染，免重复拉取
    const treeCache = loadTreeState();
    let openChapters = new Set(treeCache.open || []);
    let collapsedSemesters = new Set(treeCache.collapsed || []);
    let chapterExercisesCache = {};

    // ---------- DOM ----------
    const chapterListEl = document.getElementById('chapterList');
    const workHeadEl = document.getElementById('workHead');
    const workBodyEl = document.getElementById('workBody');
    const questionCardEl = document.getElementById('questionCard');
    const promptHostEl = document.getElementById('promptHost');
    const descPaneEl = document.getElementById('descPane');
    const solutionPaneEl = document.getElementById('solutionPane');
    const solutionHostEl = document.getElementById('solutionHost');
    const tabDescEl = document.getElementById('tabDesc');
    const tabSolutionEl = document.getElementById('tabSolution');
    const tabResultEl = document.getElementById('tabResult');
    const resultPaneEl = document.getElementById('resultPane');
    const editorCardEl = document.getElementById('editorCard');
    const codeEditorEl = document.getElementById('codeEditor');
    const answerCardEl = document.getElementById('answerCard');
    const answerBodyEl = document.getElementById('answerBody');
    const resultCardEl = document.getElementById('resultCard');
    const resultBodyEl = document.getElementById('resultBody');
    const progressEl = document.getElementById('practiceProgress');
    const submitBtn = document.getElementById('submitBtn');
    const resetBtn = document.getElementById('resetBtn');
    const answerSubmitBtn = document.getElementById('answerSubmitBtn');

    // 描述卡为「题目描述 | 题解」共用一栏：点击标签切换，默认题目描述。
    // 题解面板为静态节点（见 practice.html），此处不再动态注入宿主。

    function badgeFor(type) {
        return TYPE_BADGES[type] || '写代码';
    }

    // 题目标题里带的题型前缀（「选择 2 · 」「短题 3 · 」「Boss · 」）与相邻的题型徽章重复，
    // 而且左栏只有 224px 宽，前缀会吃掉近一半标题宽度 ⇒ 展示时剥掉，只留正题名。
    // 题库 154 条标题全部带此前缀（生成器 title 约定）；剥不到或剥空则原样返回，避免标题消失。
    function displayTitle(title) {
        const t = (title || '').trim();
        const stripped = t.replace(/^(选择|填空|短题|写代码|Boss)\s*\d*\s*[·•・.]\s*/, '').trim();
        return stripped || t;
    }

    // 章节右侧计数：已拉取过题目列表的章节显示「已完成 / 总数」（做过题才有意义），
    // 未访问过的章节只有题数（题目 id 未知，算不出完成度）。
    function chapterCountHtml(ch) {
        const list = chapterExercisesCache[ch.id];
        const total = (ch.exercise_count || 0);
        if (list && list.length) {
            const done = list.filter((ex) => doneSet.has(ex.id)).length;
            return '<span class="practice-chapter-count' + (done ? ' has-done' : '') +
                '" title="已完成 ' + done + ' / ' + list.length + ' 题">' +
                done + '/' + list.length + '</span>';
        }
        return '<span class="practice-chapter-count" title="本章 ' + total + ' 题">' + total + '</span>';
    }

    // ---------- 本地完成记录（localStorage） ----------
    function loadDone() {
        try {
            const arr = JSON.parse(localStorage.getItem(DONE_KEY) || '[]');
            return new Set(Array.isArray(arr) ? arr.map(Number) : []);
        } catch (e) {
            return new Set();
        }
    }

    function persistDone() {
        try {
            localStorage.setItem(DONE_KEY, JSON.stringify(Array.from(doneSet)));
        } catch (e) { /* 隐私模式等场景忽略 */ }
    }

    function markDone(id) {
        const n = Number(id);
        if (!n || doneSet.has(n)) return;
        doneSet.add(n);
        persistDone();
        updateProgress();
        renderChapters();
    }

    // ---------- 本地：每题最近一次运行结果 ----------
    function loadLastResults() {
        try {
            const obj = JSON.parse(localStorage.getItem(LAST_KEY) || '{}');
            return (obj && typeof obj === 'object') ? obj : {};
        } catch (e) {
            return {};
        }
    }

    function persistLastResults() {
        try {
            const keys = Object.keys(lastResults);
            if (keys.length > LAST_MAX) {
                // 超限：丢弃最早写入的一批（对象键顺序近似插入顺序）
                keys.slice(0, keys.length - LAST_MAX).forEach((k) => { delete lastResults[k]; });
            }
            localStorage.setItem(LAST_KEY, JSON.stringify(lastResults));
        } catch (e) { /* 配额或隐私模式：忽略，结果仅当次会话有效 */ }
    }

    // ---------- 本地：代码草稿（按「题号:档位」存，根治切题/刷新丢代码） ----------
    function draftKey(id, tier) {
        return String(id) + ':' + String(tier || 'easy');
    }

    function loadDrafts() {
        try {
            const obj = JSON.parse(localStorage.getItem(DRAFT_KEY) || '{}');
            return (obj && typeof obj === 'object') ? obj : {};
        } catch (e) {
            return {};
        }
    }

    function persistDrafts() {
        try {
            const keys = Object.keys(drafts);
            if (keys.length > DRAFT_MAX) {
                // 超限：丢弃最早写入的一批（对象键顺序近似插入顺序）
                keys.slice(0, keys.length - DRAFT_MAX).forEach((k) => { delete drafts[k]; });
            }
            localStorage.setItem(DRAFT_KEY, JSON.stringify(drafts));
        } catch (e) { /* 配额或隐私模式：忽略，草稿仅当次会话有效 */ }
    }

    // 把编辑器当前内容落盘。与本题本档的初始代码一致时删除草稿（保持存储精简）。
    function saveDraftNow() {
        if (!currentExercise || !currentExercise.tiers) return;
        const tier = currentExercise.tiers[currentTier] || {};
        const starter = tier.starter || '';
        const key = draftKey(currentExercise.id, currentTier);
        const code = codeEditorEl.value;
        if (code === starter) {
            if (Object.prototype.hasOwnProperty.call(drafts, key)) {
                delete drafts[key];
                persistDrafts();
            }
            return;
        }
        if (code.length > DRAFT_CODE_MAX) return;   // 过大不存，避免撑爆配额
        drafts[key] = code;
        persistDrafts();
    }

    let draftTimer = null;
    // 输入防抖：停止输入 400ms 后再落盘，避免逐字符写 localStorage
    function scheduleSaveDraft() {
        clearTimeout(draftTimer);
        draftTimer = setTimeout(saveDraftNow, 400);
    }

    // 切题 / 切档位 / 页面隐藏前立刻落盘（清掉未触发的防抖）
    function flushDraft() {
        if (draftTimer) {
            clearTimeout(draftTimer);
            draftTimer = null;
            saveDraftNow();
        }
    }

    // 清除某题某档的草稿（「重置代码」用：回到初始代码，同时丢弃草稿）
    function clearDraft(id, tier) {
        const key = draftKey(id, tier);
        if (Object.prototype.hasOwnProperty.call(drafts, key)) {
            delete drafts[key];
            persistDrafts();
            return true;
        }
        return false;
    }

    // ---------- 本地：左栏章节树展开/折叠状态 ----------
    function loadTreeState() {
        try {
            const obj = JSON.parse(localStorage.getItem(TREE_KEY) || '{}');
            return (obj && typeof obj === 'object') ? obj : {};
        } catch (e) {
            return {};
        }
    }

    function persistTreeState() {
        try {
            localStorage.setItem(TREE_KEY, JSON.stringify({
                open: Array.from(openChapters),
                collapsed: Array.from(collapsedSemesters),
            }));
        } catch (e) { /* 配额或隐私模式：忽略，折叠状态仅当次会话有效 */ }
    }

    // ---------- 服务端进度回读（与本地合并，根治「换环境/丢本地存储就归零」） ----------
    async function loadProgress() {
        try {
            const data = await apiRequest('/api/practice/progress');
            const ids = (data && data.passed) || [];
            let changed = false;
            ids.forEach((id) => {
                const n = Number(id);
                if (n && !doneSet.has(n)) { doneSet.add(n); changed = true; }
            });
            if (changed) persistDone();
            updateProgress();
            renderChapters();
        } catch (e) {
            // 进度接口失败不影响主流程：本地记录照常可用
            console.warn('[practice] 读取服务端进度失败', e);
        }
    }

    // ---------- 进度回读 ----------
    function totalExercises() {
        if (!chaptersData) return 0;
        let n = 0;
        chaptersData.forEach((sem) => {
            (sem.chapters || []).forEach((ch) => { n += ch.exercise_count || 0; });
        });
        return n;
    }

    function updateProgress() {
        if (!progressEl) return;
        progressEl.textContent = '已完成 ' + doneSet.size + ' / ' + totalExercises();
    }

    // ---------- 通用 POST JSON ----------
    async function postJson(url, payload) {
        const resp = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        return resp.json();
    }

    // ---------- 章节列表 ----------
    async function loadChapters() {
        try {
            const data = await apiRequest('/api/practice/chapters');
            chaptersData = data.semesters || [];
            pruneOpenChapters();    // 丢弃已不存在章节的展开状态
            updateProgress();
            renderChapters();
            await loadProgress();   // 合并服务端进度（失败不影响本地记录）
            await hydrateOpenChapters();   // 预拉取上次展开章节的题目列表（在自动选题之前）
            autoSelectFirst();
        } catch (e) {
            chapterListEl.innerHTML = '<div class="empty-state">' + esc(describeFetchError(e)) + '</div>';
        }
    }

    // 收起 / 丢弃「已不存在章节」的展开状态（题库改版后本地缓存可能残留旧 id）
    function pruneOpenChapters() {
        const valid = new Set();
        (chaptersData || []).forEach((sem) => (sem.chapters || []).forEach((ch) => valid.add(ch.id)));
        let changed = false;
        openChapters.forEach((id) => { if (!valid.has(id)) { openChapters.delete(id); changed = true; } });
        if (changed) persistTreeState();
    }

    // 恢复「上次展开的章节」：预拉取题目列表，否则重载后是「展开但空白」的怪状态
    async function hydrateOpenChapters() {
        const ids = Array.from(openChapters);
        await Promise.all(ids.map((id) => ensureChapterExercises(id)));
    }

    // ---------- 渲染左栏：学期 ▸ 章节 ▸ 题目（可折叠三级树） ----------
    // 折叠模型：学期可整组折叠；章节各自独立展开/折叠，可同时展开多个，互不影响。
    //   ▸ 折叠箭头 → 只切换展开/折叠，不改动当前选中题（与资源管理器一致的心智）
    //   章节标题   → 选中该章（未展开时自动展开并拉取题目列表）
    function renderChapters() {
        if (!chaptersData) return;
        let html = '';
        chaptersData.forEach((sem) => {
            const semClosed = collapsedSemesters.has(sem.name);
            const semCount = (sem.chapters || []).reduce((n, ch) => n + (ch.exercise_count || 0), 0);
            html += '<button type="button" class="practice-semester' + (semClosed ? ' is-collapsed' : '') +
                '" data-sem="' + esc(sem.name) + '" aria-expanded="' + (!semClosed) + '">' +
                '<span class="practice-caret" aria-hidden="true">' + caretSvg(false) + '</span>' +
                '<span class="practice-semester-name">' + esc(sem.name) + '</span>' +
                '<span class="practice-semester-count">' + semCount + '</span>' +
                '</button>';
            if (semClosed) return;
            (sem.chapters || []).forEach((ch) => {
                const active = ch.id === currentChapter ? ' active' : '';
                const empty = ch.exercise_count > 0 ? '' : ' is-empty';
                const hasKids = ch.exercise_count > 0;
                const open = hasKids && openChapters.has(ch.id);
                html += '<div class="practice-chapter-row">' +
                    '<button type="button" class="practice-chapter-toggle' + (hasKids ? '' : ' is-leaf') +
                    '" data-id="' + ch.id + '" aria-expanded="' + open +
                    '" aria-label="' + (open ? '折叠' : '展开') + '本章"' + (hasKids ? '' : ' disabled') + '>' +
                    caretSvg(!open) +
                    '</button>' +
                    '<button type="button" class="practice-chapter' + active + empty + '" data-id="' + ch.id + '">' +
                    '<span class="practice-chapter-num">C' + ch.id + '</span>' +
                    '<span class="practice-chapter-title">' + esc(ch.title) + '</span>' +
                    chapterCountHtml(ch) +
                    '</button>' +
                    '</div>';
                if (open && chapterExercisesCache[ch.id]) {
                    html += renderExerciseList(chapterExercisesCache[ch.id]);
                }
            });
        });
        chapterListEl.innerHTML = html;

        chapterListEl.querySelectorAll('.practice-semester').forEach((btn) => {
            btn.addEventListener('click', () => toggleSemester(btn.dataset.sem));
        });
        chapterListEl.querySelectorAll('.practice-chapter-toggle').forEach((btn) => {
            btn.addEventListener('click', () => toggleChapter(Number(btn.dataset.id)));
        });
        chapterListEl.querySelectorAll('.practice-chapter').forEach((btn) => {
            btn.addEventListener('click', () => selectChapter(Number(btn.dataset.id)));
        });
        chapterListEl.querySelectorAll('.practice-ex-item').forEach((btn) => {
            btn.addEventListener('click', () => selectExercise(Number(btn.dataset.id)));
        });
        scrollSideToCurrent();
    }

    // 折叠箭头 SVG：down=展开态(▾) / right=折叠态(▸)
    function caretSvg(collapsed) {
        const d = collapsed ? 'M6 4l4 4-4 4' : 'M4 6l4 4 4-4';
        return '<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">' +
            '<path d="' + d + '" fill="none" stroke="currentColor" stroke-width="1.6" ' +
            'stroke-linecap="round" stroke-linejoin="round"/></svg>';
    }

    // 切换某学期展开/折叠（整组隐藏/显示其下章节）
    function toggleSemester(name) {
        if (collapsedSemesters.has(name)) collapsedSemesters.delete(name);
        else collapsedSemesters.add(name);
        persistTreeState();
        renderChapters();
    }

    // 切换某章节展开/折叠；首次展开时拉取该章题目列表并缓存
    async function toggleChapter(id) {
        if (openChapters.has(id)) {
            openChapters.delete(id);
            persistTreeState();
            renderChapters();
            return;
        }
        openChapters.add(id);
        persistTreeState();
        renderChapters();
        await ensureChapterExercises(id);
    }

    // 拉取并缓存某章题目列表（已缓存则直接重绘；失败给出提示）
    async function ensureChapterExercises(id) {
        if (chapterExercisesCache[id]) { renderChapters(); return; }
        try {
            const data = await apiRequest('/api/practice/exercises?chapter=' + id);
            chapterExercisesCache[id] = data.exercises || [];
            renderChapters();
        } catch (e) {
            openChapters.delete(id);   // 拉取失败则收回展开态，避免留空展开
            persistTreeState();
            renderChapters();
            showToast(describeFetchError(e), 'error');
        }
    }

    // 章节题目列表 HTML（每题：状态点 + 标题）
    // 注：不显示「选择/填空/短题/Boss」题型徽章——徽章占位会挤压标题导致标题看不见；
    //     题型在工作台头部徽章与题目内容里已能区分。title 属性供窄栏截断时悬停查看全称。
    function renderExerciseList(list) {
        const items = list || [];
        return '<div class="practice-ex-list">' + items.map((ex) => {
            const isCur = !!(currentExercise && currentExercise.id === ex.id);
            const done = doneSet.has(ex.id);
            const dot = done ? '✓' : (isCur ? '●' : '○');
            const name = displayTitle(ex.title);
            const cls = 'practice-ex-item' + (isCur ? ' current' : '') + (done ? ' done' : '');
            return '<button type="button" class="' + cls + '" data-id="' + ex.id + '" title="' + esc(name) + '">' +
                '<span class="practice-ex-dot">' + dot + '</span>' +
                '<span class="practice-ex-title">' + esc(name) + '</span>' +
                '</button>';
        }).join('') + '</div>';
    }

    function scrollSideToCurrent() {
        const el = chapterListEl.querySelector('.practice-ex-item.current');
        if (el && el.scrollIntoView) {
            try { el.scrollIntoView({ block: 'nearest' }); } catch (e) { /* 忽略 */ }
        }
    }

    function autoSelectFirst() {
        // reveal:false —— 自动载入首题到工作区，但不展开左栏章节（章节默认折叠，点击才展开）
        for (const sem of chaptersData) {
            for (const ch of (sem.chapters || [])) {
                if (ch.exercise_count > 0) { selectChapter(ch.id, { reveal: false }); return; }
            }
        }
        const first = chaptersData[0] && (chaptersData[0].chapters || [])[0];
        if (first) selectChapter(first.id, { reveal: false });
        else showIdleState();
    }

    // 某章所属学期名（选中章节时自动展开其学期，保证选中项可见）
    function semesterOf(id) {
        for (const sem of (chaptersData || [])) {
            if ((sem.chapters || []).some((ch) => ch.id === id)) return sem.name;
        }
        return null;
    }

    // ---------- 选中章节：拉题目列表 ----------
    // opts.reveal（默认 true）：点击章节标题时展开该章并展开所属分组；
    //   首次自动选题用 reveal:false —— 只把题目载入工作区，左栏具体章节保持默认折叠。
    async function selectChapter(id, opts) {
        const reveal = !opts || opts.reveal !== false;
        if (reveal) {
            openChapters.add(id);                       // 选中即展开
            const semName = semesterOf(id);
            if (semName) collapsedSemesters.delete(semName);   // 所属学期一并展开
            persistTreeState();
        }

        // 重复点击当前章：只确保展开，不重拉、不跳题（避免打断正在做的题）
        if (id === currentChapter && (chapterExercises.length || chapterExercisesCache[id])) {
            renderChapters();
            return;
        }

        currentChapter = id;
        currentExercise = null;
        const cached = chapterExercisesCache[id];
        chapterExercises = cached || [];
        renderChapters();

        // 未缓存才请求（缓存来自「上次展开章节」的预拉取或本会话早前访问）
        if (!cached) {
            try {
                const data = await apiRequest('/api/practice/exercises?chapter=' + id);
                chapterExercises = data.exercises || [];
                chapterExercisesCache[id] = chapterExercises;
            } catch (e) {
                showEmptyState(describeFetchError(e));
                return;
            }
            renderChapters();
        }

        if (chapterExercises.length) {
            // 优先跳到本章第一道未完成的题，全部完成则回到第一题
            const firstTodo = chapterExercises.find((ex) => !doneSet.has(ex.id)) || chapterExercises[0];
            selectExercise(firstTodo.id);
        } else {
            showEmptyState('本章题目尚未录入。');
        }
    }

    // ---------- 选中题目：拉详情 ----------
    async function selectExercise(id) {
        flushDraft();   // 切题前把旧题草稿落盘
        try {
            const data = await apiRequest('/api/practice/exercise/' + id);
            currentExercise = data;
            currentTier = 'easy';
            renderQuestion();
            renderChapters();   // 更新左栏当前题高亮
        } catch (e) {
            showToast(describeFetchError(e), 'error');
        }
    }

    // ---------- 头部答题操作区：按题型切换按钮 ----------
    // code      写代码题 → 「提交运行」+「重置代码」
    // objective 客观题   → 「提交答案」
    // none      空态     → 三个按钮全隐藏（容器常驻，保证头部三栏网格稳定、导航恒居中）
    function syncActions(kind) {
        const isCode = kind === 'code';
        const isObj = kind === 'objective';
        if (submitBtn) submitBtn.hidden = !isCode;
        if (resetBtn) resetBtn.hidden = !isCode;
        if (answerSubmitBtn) answerSubmitBtn.hidden = !isObj;
    }

    // ---------- 工作台布局：双列 / 单列 ----------
    function setWorkLayout(single) {
        workBodyEl.classList.toggle('single', !!single);
    }

    function renderHead(ex) {
        workHeadEl.hidden = false;
        const prevId = neighborExerciseId(-1);
        const nextId = neighborExerciseId(1);
        workHeadEl.innerHTML =
            '<div class="practice-nav" role="group" aria-label="切题">' +
            '<button type="button" class="practice-nav-btn" id="prevExBtn" title="上一题" aria-label="上一题"' +
            (prevId == null ? ' disabled' : '') + '>' + navChevronSvg(-1) + '</button>' +
            '<button type="button" class="practice-nav-btn" id="nextExBtn" title="下一题" aria-label="下一题"' +
            (nextId == null ? ' disabled' : '') + '>' + navChevronSvg(1) + '</button>' +
            '</div>' +
            '<span class="practice-badge">' + esc(badgeFor(ex.type)) + '</span>' +
            '<h2 class="practice-work-title">' + esc(displayTitle(ex.title)) + '</h2>' +
            '<span class="practice-work-pos">' + esc(posText()) + '</span>';

        const prevBtn = document.getElementById('prevExBtn');
        const nextBtn = document.getElementById('nextExBtn');
        if (prevBtn && prevId != null) prevBtn.addEventListener('click', () => selectExercise(prevId));
        if (nextBtn && nextId != null) nextBtn.addEventListener('click', () => selectExercise(nextId));
    }

    // 本章内相邻题目的 id（dir=-1 上一题 / dir=1 下一题；越界返回 null）
    function neighborExerciseId(dir) {
        const total = chapterExercises.length;
        const idx = chapterExercises.findIndex((e) => currentExercise && e.id === currentExercise.id);
        if (idx < 0) return null;
        const j = idx + dir;
        if (j < 0 || j >= total) return null;
        return chapterExercises[j].id;
    }

    // 切题箭头 SVG：dir=-1 → '‹'，dir=1 → '›'
    function navChevronSvg(dir) {
        const d = dir < 0 ? 'M10 4l-4 4 4 4' : 'M6 4l4 4-4 4';
        return '<svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true">' +
            '<path d="' + d + '" fill="none" stroke="currentColor" stroke-width="1.7" ' +
            'stroke-linecap="round" stroke-linejoin="round"/></svg>';
    }

    function posText() {
        const total = chapterExercises.length;
        const idx = chapterExercises.findIndex((e) => currentExercise && e.id === currentExercise.id);
        if (idx < 0 || !total || currentChapter == null) return '';
        return 'C' + currentChapter + ' · 第 ' + (idx + 1) + ' / ' + total + ' 题';
    }

    // 题目描述渲染：直接渲染 prompt（写代码题=需求 markdown；选择题=纯代码块；填空题=纯代码）。
    // 选择题/填空题的「问题/说明」已由生成阶段固化到 question 字段，渲染时由 renderChoice/renderBlank 负责，
    // 这里不再解析 // 注释。
    function renderPromptInto() {
        const body = document.getElementById('promptBody');
        if (!body) return;
        const text = (currentExercise && currentExercise.prompt) || '';
        if (window.renderMarkdownInto) renderMarkdownInto(body, text);
        else body.textContent = text;
    }

    // 只重绘「题目描述」面板：#promptHost 内部整体替换，
    // 保留描述卡外层的标签栏、题解面板与底部「测试结果」卡（它们是 #promptHost 的兄弟）。
    function setPromptHtml(inner) {
        if (promptHostEl) promptHostEl.innerHTML = inner;
    }

    // 描述卡「题目描述 | 题解 | 测试结果」标签切换（共用一栏，默认题目描述）
    const TAB_MAP = () => ([
        { key: 'desc', pane: descPaneEl, tab: tabDescEl },
        { key: 'solution', pane: solutionPaneEl, tab: tabSolutionEl },
        { key: 'result', pane: resultPaneEl, tab: tabResultEl },
    ]);

    function switchTab(name) {
        TAB_MAP().forEach((it) => {
            const on = it.key === name;
            if (it.pane) it.pane.hidden = !on;
            if (it.tab) {
                it.tab.classList.toggle('is-active', on);
                it.tab.setAttribute('aria-selected', String(on));
            }
        });
    }

    function bindTabs() {
        if (tabDescEl) tabDescEl.addEventListener('click', () => switchTab('desc'));
        if (tabSolutionEl) tabSolutionEl.addEventListener('click', () => switchTab('solution'));
        if (tabResultEl) tabResultEl.addEventListener('click', () => switchTab('result'));
    }

    // 题解：填入静态题解面板（无题解时隐藏「题解」标签并给出提示）
    function renderSolution() {
        const host = solutionHostEl;
        if (!host) return;
        const md = (currentExercise && currentExercise.solution) || '';
        const has = !!md.trim();
        if (tabSolutionEl) tabSolutionEl.hidden = !has;
        if (!has) {
            host.innerHTML = '<div class="practice-prompt practice-empty">本题暂无题解。</div>';
            return;
        }
        host.innerHTML = '<div class="practice-solution-body markdown-body"></div>';
        const body = host.querySelector('.practice-solution-body');
        if (body) {
            if (window.renderMarkdownInto) renderMarkdownInto(body, md);
            else body.textContent = md;
        }
    }

    // ---------- 渲染题目（按题型分支） ----------
    function renderQuestion() {
        const ex = currentExercise;
        if (!ex) { showIdleState(); return; }
        if (ex.type === 'choice') { renderChoice(); return; }
        if (ex.type === 'blank') { renderBlank(); return; }
        renderCode();
    }

    // 写代码题（short / boss）：题干 | 编辑器
    function renderCode() {
        const ex = currentExercise;
        setWorkLayout(false);
        renderHead(ex);
        setPromptHtml([
            '<div class="practice-prompt markdown-body" id="promptBody"></div>',
            '<div class="practice-tier-bar" id="tierBar"></div>',
        ].join(''));
        renderPromptInto();
        bindTierBar();
        renderTier(currentTier);
        renderSolution();
        switchTab('desc');
        editorCardEl.hidden = false;
        answerCardEl.hidden = true;
        syncActions('code');
        restoreLastResult(ex.id);
        // 卡片可见后再刷一次：隐藏时测不到高度，行高补偿会不准
        refreshCodeEditor();
    }

    // 代码框里的 // 注释就是「问题/说明」——把它抽到代码框外展示，
    // 同时在代码框里**原地留一个 ◀ 标记**，指向问题所在的那一行。
    //（保留 /* */ 块注释与 ______ 空位不动。）
    // 返回 { question: 抽出的文字, code: 代码（注释已替换为 ◀ 标记） }。
    const PROMPT_MARKER = '◀';
    function splitPromptNotes(prompt, typ) {
        let src = prompt || '';
        if (typ === 'choice') {
            const m = src.trim().match(/^```[A-Za-z0-9]*\n([\s\S]*?)\n?```$/);
            if (m) src = m[1].replace(/\s+$/, '');
        }
        const notes = [];
        const codeLines = [];
        for (const line of src.split('\n')) {
            const ci = line.indexOf('//');
            if (ci === -1) { codeLines.push(line); continue; }
            const before = line.slice(0, ci).replace(/\s+$/, '');
            const after = line.slice(ci + 2).trim();
            if (after) notes.push(after);
            // 有代码的行：注释抽走，原地留 ◀ 标记指向该行
            if (before.trim()) codeLines.push(before + '  // ' + PROMPT_MARKER);
            // 整行注释（无代码）：纯说明，抽走后不留标记行
        }
        let code = codeLines.join('\n').replace(/\n{3,}/g, '\n\n').trim();
        if (typ === 'choice' && code) code = '```cpp\n' + code + '\n```';
        return { question: notes.join(' '), code: code };
    }

    // 选择题：问题(question 字段，缺失则从 prompt 的 // 注释抽) + 代码框(注释处留 ◀ 标记)
    function renderChoice() {
        const ex = currentExercise;
        setWorkLayout(false);
        renderHead(ex);
        setPromptHtml('<div class="practice-prompt markdown-body" id="promptBody"></div>');
        const body = document.getElementById('promptBody');
        const split = splitPromptNotes(ex.prompt, 'choice');
        const question = (ex.question || '').trim() || split.question;
        let md = '';
        if (question) md += '**问题：** ' + question + '\n\n';
        md += split.code;
        if (body) {
            if (window.renderMarkdownInto && md) renderMarkdownInto(body, md);
            else body.textContent = md;
        }
        renderSolution();
        switchTab('desc');

        let options = [];
        try { options = JSON.parse(ex.options || '[]'); } catch (e) { options = []; }
        answerBodyEl.innerHTML = '<div class="practice-choice-list">' + options.map((o) =>
            '<label class="practice-choice">' +
            '<input type="radio" name="practiceChoice" value="' + esc(o.label) + '">' +
            '<span class="practice-choice-label">' + esc(o.label) + '.</span>' +
            '<span class="practice-choice-text">' + esc(o.text) + '</span>' +
            '</label>').join('') + '</div>';

        editorCardEl.hidden = true;
        answerCardEl.hidden = false;
        syncActions('objective');
        restoreLastResult(ex.id);
    }

    // 填空题：说明(question 字段，缺失则从 prompt 的 // 注释抽) + 代码框(注释处留 ◀ 标记，空位 ______ 变输入框)
    function renderBlank() {
        const ex = currentExercise;
        setWorkLayout(true);
        renderHead(ex);
        const split = splitPromptNotes(ex.prompt, 'blank');
        const question = (ex.question || '').trim() || split.question;
        const codeHtml = esc(split.code).replace(/_{3,}/g,
            '<input type="text" class="practice-blank-input" data-blank spellcheck="false" autocomplete="off">');
        const intro = question ? '<p class="practice-blank-note">' + esc(question) + '</p>' : '';
        setPromptHtml(
            '<div class="practice-prompt">' + intro + '<pre class="practice-blank-code"><code>' + codeHtml + '</code></pre></div>');
        editorCardEl.hidden = true;
        answerCardEl.hidden = true;
        syncActions('objective');
        renderSolution();
        switchTab('desc');
        restoreLastResult(ex.id);
    }

    // ---------- 空态 ----------
    function resetSolution() {
        if (solutionHostEl) solutionHostEl.innerHTML = '';
        if (tabSolutionEl) tabSolutionEl.hidden = true;
        switchTab('desc');
    }

    function showIdleState() {
        setWorkLayout(true);
        workHeadEl.hidden = true;
        workHeadEl.innerHTML = '';
        setPromptHtml('<div class="practice-prompt practice-empty">从左侧选择一道题目开始练习。</div>');
        resetSolution();
        editorCardEl.hidden = true;
        answerCardEl.hidden = true;
        syncActions('none');
        clearResult();
    }

    function showEmptyState(hint) {
        setWorkLayout(true);
        workHeadEl.hidden = true;
        workHeadEl.innerHTML = '';
        setPromptHtml('<div class="practice-prompt practice-empty">' +
            esc(hint || '本章题目尚未录入。') + '</div>');
        resetSolution();
        editorCardEl.hidden = true;
        answerCardEl.hidden = true;
        syncActions('none');
        clearResult();
    }

    // ---------- 测试结果面板：渲染 / 记忆 / 恢复 ----------
    function emptyResultHtml() {
        return '<div class="practice-result-empty">本题还没有运行结果，运行或提交后会显示在这里。</div>';
    }

    function applyResult(cls, html) {
        resultCardEl.classList.remove('is-pass', 'is-fail');
        if (cls) resultCardEl.classList.add(cls);
        resultBodyEl.innerHTML = html || emptyResultHtml();
    }

    function updateResultTabDot(cls) {
        if (!tabResultEl) return;
        tabResultEl.classList.remove('has-result-pass', 'has-result-fail');
        if (cls === 'is-pass') tabResultEl.classList.add('has-result-pass');
        else if (cls === 'is-fail') tabResultEl.classList.add('has-result-fail');
    }

    // 清空为「空态」（结果面板不再隐藏，切到该标签时显示提示）
    function clearResult() {
        applyResult('', emptyResultHtml());
        updateResultTabDot('');
    }

    // 打开某题时：优先恢复本题上次运行结果；没有则显示空态（不自动切标签）
    function restoreLastResult(id) {
        const r = id ? lastResults[String(id)] : null;
        if (r && r.html) {
            applyResult(r.cls, r.html);
            updateResultTabDot(r.cls);
        } else {
            clearResult();
        }
    }

    // 提交完成后：记住结果 + 自动切到「测试结果」标签
    function revealResult() {
        const id = currentExercise && currentExercise.id;
        const cls = resultCardEl.classList.contains('is-pass') ? 'is-pass'
            : (resultCardEl.classList.contains('is-fail') ? 'is-fail' : '');
        const html = resultBodyEl.innerHTML;
        if (id && html) {
            lastResults[String(id)] = { cls: cls, html: html };
            persistLastResults();
        }
        updateResultTabDot(cls);
        switchTab('result');
    }

    // ---------- 难度档位切换（写代码题） ----------
    function bindTierBar() {
        const bar = document.getElementById('tierBar');
        if (!bar) return;
        const tiers = currentExercise.tiers || {};
        bar.innerHTML = Object.keys(tiers).map((key) => {
            const active = key === currentTier ? ' active' : '';
            const label = (tiers[key] && tiers[key].label) || (TIER_LABELS[key] || key);
            return '<button type="button" class="practice-tier' + active + '" data-tier="' + key + '">' + esc(label) + '</button>';
        }).join('');
        bar.querySelectorAll('.practice-tier').forEach((btn) => {
            btn.addEventListener('click', () => {
                flushDraft();               // 先把当前档位的编辑落盘，再切档
                currentTier = btn.dataset.tier;
                renderTier(currentTier);
            });
        });
    }

    function renderTier(tierKey) {
        const tiers = currentExercise.tiers || {};
        const tier = tiers[tierKey] || {};
        const key = draftKey(currentExercise.id, tierKey);
        // 有草稿则恢复草稿，否则用本题本档的初始代码
        codeEditorEl.value = Object.prototype.hasOwnProperty.call(drafts, key)
            ? drafts[key] : (tier.starter || '');
        clearResult();
        const bar = document.getElementById('tierBar');
        if (bar) {
            bar.querySelectorAll('.practice-tier').forEach((btn) => {
                btn.classList.toggle('active', btn.dataset.tier === tierKey);
            });
        }
        refreshCodeEditor();
    }

    // ---------- 代码编辑器（行号槽 + 语法高亮叠加层 + 状态栏） ----------
    // 复用文章编辑器（editor.js）的「透明 textarea 叠在高亮层上」范式：
    // 高亮层与输入框的字体/行高/内边距必须逐像素一致，否则文字与光标会错位。
    const INDENT = '    ';                                   // 4 空格缩进
    const INDENT_SIZE = INDENT.length;                       // 缩进宽度（= 制表位间距，用于回退格对齐 VS Code）
    const PAIRS = { '(': ')', '[': ']', '{': '}', '"': '"', "'": "'" };

    // 代码编辑器主题：Dark+ / Light+ / Solarized Dark / Monokai（与 CSS 的 data-editor-theme 对应）
    const EDITOR_THEME_KEY = 'practice.editorTheme.v1';
    const EDITOR_THEMES = ['dark', 'light', 'solarized', 'monokai'];
    const DEFAULT_EDITOR_THEME = 'dark';

    let codeGutterEl = null;
    let codeGutterInnerEl = null;
    let codeHighlightEl = null;
    let codeStatusPosEl = null;
    let codeCurrentLineEl = null;
    let codeShellEl = null;
    let codeThemeSelEl = null;

    function ensureCodeRefs() {
        if (!codeShellEl) codeShellEl = document.getElementById('codeShell');
        if (!codeThemeSelEl) codeThemeSelEl = document.getElementById('codeTheme');
        if (!codeGutterEl) codeGutterEl = document.getElementById('codeGutter');
        if (!codeGutterInnerEl) codeGutterInnerEl = document.getElementById('codeGutterInner');
        if (!codeHighlightEl) codeHighlightEl = document.getElementById('codeHighlight');
        if (!codeStatusPosEl) codeStatusPosEl = document.getElementById('codeStatusPos');
        if (!codeCurrentLineEl) codeCurrentLineEl = document.getElementById('codeCurrentLine');
    }

    // ---------- 代码编辑器主题（localStorage 持久化） ----------
    function loadEditorTheme() {
        try {
            const v = localStorage.getItem(EDITOR_THEME_KEY);
            return EDITOR_THEMES.includes(v) ? v : DEFAULT_EDITOR_THEME;
        } catch (e) { return DEFAULT_EDITOR_THEME; }
    }

    function saveEditorTheme(name) {
        try { localStorage.setItem(EDITOR_THEME_KEY, name); } catch (e) { /* 隐私模式等：忽略 */ }
    }

    // 把主题写到 #codeShell[data-editor-theme]，CSS 变量随之切换
    function applyEditorTheme(name) {
        ensureCodeRefs();
        if (!codeShellEl) return;
        if (!EDITOR_THEMES.includes(name)) name = DEFAULT_EDITOR_THEME;
        codeShellEl.dataset.editorTheme = name;
        if (codeThemeSelEl && codeThemeSelEl.value !== name) codeThemeSelEl.value = name;
    }

    function highlightCpp(code) {
        if (!code) return '';
        if (window.hljs && window.hljs.getLanguage('cpp')) {
            try { return window.hljs.highlight(code, { language: 'cpp' }).value; }
            catch (e) { return esc(code); }
        }
        return esc(code);
    }

    function renderCodeNumbers(code) {
        if (!codeGutterInnerEl) return;
        const lines = code.split('\n').length;
        let html = '';
        for (let i = 1; i <= lines; i++) html += '<div>' + i + '</div>';
        codeGutterInnerEl.innerHTML = html;
    }

    // 滚动同步：输入框是「唯一滚动源」，高亮层与行号槽用 transform 平移内容跟随。
    // ⚠ 不能改成给它们设 scrollTop —— 输入框自带滚动条各占 10px 布局空间，而高亮层
    //    与行号槽是 overflow:hidden（不占），两者滚动范围差 10px；靠近滚动极限时它们
    //    会被 clamp 停在原位 ⇒ 文字/行号与光标错位（实测第 20 行偏差可达 ~12px）。
    //    用 transform 平移则完全不存在 clamp 问题。
    function syncCodeScroll() {
        ensureCodeRefs();
        if (!codeEditorEl) return;
        const top = codeEditorEl.scrollTop;
        const left = codeEditorEl.scrollLeft;
        if (codeHighlightEl) codeHighlightEl.style.transform = 'translate(' + (-left) + 'px,' + (-top) + 'px)';
        if (codeGutterInnerEl) codeGutterInnerEl.style.transform = 'translateY(' + (-top) + 'px)';
        updateCurrentLine();
    }

    // 光标所在行 / 列（1-based）与偏移量
    function caretPos() {
        const v = codeEditorEl.value;
        const pos = codeEditorEl.selectionStart || 0;
        const before = v.slice(0, pos);
        const line = before.split('\n').length;
        const col = pos - (before.lastIndexOf('\n') + 1) + 1;
        return { pos, line, col };
    }

    // 一行的像素高度（高亮层与输入框行高一致，取输入框计算值）
    function codeLineHeight() {
        const lh = parseFloat(getComputedStyle(codeEditorEl).lineHeight);
        if (lh) return lh;
        return (parseFloat(getComputedStyle(codeEditorEl).fontSize) || 13) * 1.6;
    }

    function updateCodeStatus() {
        if (!codeStatusPosEl) return;
        const c = caretPos();
        codeStatusPosEl.textContent = '行 ' + c.line + '，列 ' + c.col;
    }

    // 当前行高亮条：随光标移动、随滚动平移（VS Code 的「着重显示」）
    function updateCurrentLine() {
        if (!codeCurrentLineEl || !codeEditorEl) return;
        const lh = codeLineHeight();
        const padTop = parseFloat(getComputedStyle(codeEditorEl).paddingTop) || 0;
        const y = padTop + (caretPos().line - 1) * lh - codeEditorEl.scrollTop;
        codeCurrentLineEl.style.height = lh + 'px';
        codeCurrentLineEl.style.transform = 'translateY(' + y + 'px)';
    }

    // 光标跟随：光标移出可视区时自动滚动（含程序化改文后，浏览器不会自动滚动）
    // —— 这就是「光标下移后右侧滚动条自动移动」的核心。
    function scrollCaretIntoView() {
        const ta = codeEditorEl;
        if (ta && ta.clientHeight) {
            const lh = codeLineHeight();
            const padTop = parseFloat(getComputedStyle(ta).paddingTop) || 0;
            const yTop = padTop + (caretPos().line - 1) * lh;
            const yBot = yTop + lh;
            if (yTop < ta.scrollTop) {
                ta.scrollTop = yTop;                                   // 上边界之外：顶到顶部
            } else if (yBot > ta.scrollTop + ta.clientHeight) {
                ta.scrollTop = yBot - ta.clientHeight;                 // 下边界之外：滚到底部
            }
        }
        syncCodeScroll();
    }

    // 光标/选区变化后的统一收尾：状态栏 + 当前行 + 跟随滚动
    function onCaretActivity() {
        updateCodeStatus();
        scrollCaretIntoView();
    }

    // 重绘高亮层与行号。overlay 采用「transform 跟随」方案（见 syncCodeScroll），
    // 高亮层不再自行滚动，因此无需再给 <pre> 补 paddingBottom 对齐滚动范围。
    function refreshCodeEditor() {
        ensureCodeRefs();
        const text = codeEditorEl.value;
        if (codeHighlightEl) codeHighlightEl.innerHTML = text ? highlightCpp(text) : '';
        renderCodeNumbers(text);
        scrollCaretIntoView();     // 含 syncCodeScroll + 当前行高亮
        updateCodeStatus();
    }

    // Tab / Shift+Tab：无选区插入一个缩进；有选区则整块缩进 / 反缩进
    function applyIndent(outdent) {
        const ta = codeEditorEl;
        const v = ta.value;
        const s = ta.selectionStart;
        const e = ta.selectionEnd;

        if (s === e && !outdent) {
            ta.value = v.slice(0, s) + INDENT + v.slice(e);
            ta.selectionStart = ta.selectionEnd = s + INDENT.length;
            refreshCodeEditor();
            return;
        }

        const lineStart = v.lastIndexOf('\n', s - 1) + 1;
        const nl = v.indexOf('\n', e);
        const blockEnd = nl === -1 ? v.length : nl;
        const lines = v.slice(lineStart, blockEnd).split('\n');

        let deltaFirst = 0;
        let deltaAll = 0;
        const out = lines.map((ln, i) => {
            if (outdent) {
                let remove = 0;
                while (remove < INDENT.length && ln[remove] === ' ') remove++;
                if (!remove && ln[0] === '\t') remove = 1;
                if (i === 0) deltaFirst = -remove;
                deltaAll -= remove;
                return ln.slice(remove);
            }
            if (i === 0) deltaFirst = INDENT.length;
            deltaAll += INDENT.length;
            return INDENT + ln;
        }).join('\n');

        ta.value = v.slice(0, lineStart) + out + v.slice(blockEnd);
        ta.selectionStart = Math.max(lineStart, s + deltaFirst);
        ta.selectionEnd = Math.max(ta.selectionStart, e + deltaAll);
        refreshCodeEditor();
    }

    // Backspace 智能反缩进 —— 对齐 VS Code `getDeleteLeftRange` 的「useTabStops」分支：
    //   仅当光标落在「缩进区」内（行首 → 首个非空白字符之间），一次退到「上一个缩进制表位」，
    //   而不是一格一格删空格。4 空格缩进时：
    //     行首后第 4 列 → 一次删掉整级缩进（4 空格）
    //     第 6 列 → 只删 2 个（回到第 4 列，即上一个制表位）
    //     第 1 列（行首）→ 不接管，交给浏览器默认（并到上一行行尾）
    //   制表符按可见列（tab stop）参与计算，与 VS Code 的 visibleColumnFromColumn 一致。
    function smartBackspace() {
        const ta = codeEditorEl;
        if (ta.selectionStart !== ta.selectionEnd) return false;   // 有选区：整段删除交给默认行为
        const v = ta.value;
        const pos = ta.selectionStart;
        const lineStart = v.lastIndexOf('\n', pos - 1) + 1;
        if (pos === lineStart) return false;                       // 行首：交给默认（与上一行合并）
        const before = v.slice(lineStart, pos);                    // 行首 → 光标
        if (!/^[ \t]*$/.test(before)) return false;                // 含非空白 ⇒ 不在缩进区，交给默认

        // ① 光标可见列（tab 按制表位展开）
        let vis = 0;
        for (let i = 0; i < before.length; i++) {
            vis += before[i] === '\t' ? INDENT_SIZE - (vis % INDENT_SIZE) : 1;
        }
        // ② 上一个缩进制表位（VS Code CursorColumns.prevIndentTabStop）
        const target = vis - ((vis % INDENT_SIZE) || INDENT_SIZE);
        if (target >= vis) return false;
        // ③ 可见列 → 字符下标（before 全为空白，逐字符推进可精确落位）
        let col = 0;
        let cut = 0;
        while (cut < before.length && col < target) {
            col += before[cut] === '\t' ? INDENT_SIZE - (col % INDENT_SIZE) : 1;
            cut++;
        }
        if (col !== target) return false;                          // 未精确落位（异常混排）→ 交给默认

        ta.value = v.slice(0, lineStart + cut) + v.slice(pos);
        ta.selectionStart = ta.selectionEnd = lineStart + cut;
        refreshCodeEditor();
        return true;
    }

    // Enter：① 光标夹在一对括号之间 → 展开成三行（VS Code 招牌行为）
    //        ② 否则继承上一行缩进；行尾是 { ( [ 再多一级
    function autoIndentOnEnter() {
        const ta = codeEditorEl;
        if (ta.selectionStart !== ta.selectionEnd) return false;
        const v = ta.value;
        const pos = ta.selectionStart;
        const lineStart = v.lastIndexOf('\n', pos - 1) + 1;
        const cur = v.slice(lineStart, pos);
        const m = cur.match(/^[ \t]*/);
        const outer = m ? m[0] : '';
        let indent = outer;
        if (/[\[({]\s*$/.test(cur)) indent += INDENT;

        // 夹在一对括号之间：{ | }  →  {
        //                              |
        //                          }
        const prev = v[pos - 1];
        const next = v[pos];
        if (prev && next && PAIRS[prev] === next) {
            const insert = '\n' + indent + '\n' + outer;
            ta.value = v.slice(0, pos) + insert + v.slice(pos);
            ta.selectionStart = ta.selectionEnd = pos + 1 + indent.length;
            refreshCodeEditor();
            return true;
        }

        const insert = '\n' + indent;
        ta.value = v.slice(0, pos) + insert + v.slice(pos);
        ta.selectionStart = ta.selectionEnd = pos + insert.length;
        refreshCodeEditor();
        return true;
    }

    // 智能 Home：先跳到首个非空白字符，再按一次到行首（VS Code 行为）
    function smartHome() {
        const ta = codeEditorEl;
        if (ta.selectionStart !== ta.selectionEnd) return false;
        const v = ta.value;
        const pos = ta.selectionStart;
        const lineStart = v.lastIndexOf('\n', pos - 1) + 1;
        const m = v.slice(lineStart).match(/^[ \t]*/);
        const indentEnd = lineStart + (m ? m[0].length : 0);
        if (pos !== indentEnd) {
            ta.selectionStart = ta.selectionEnd = indentEnd;
        } else if (pos !== lineStart) {
            ta.selectionStart = ta.selectionEnd = lineStart;
        } else {
            return false;
        }
        onCaretActivity();
        return true;
    }

    // 取选区覆盖的整行区间 [startIdx, endIdx)（不含末行换行符）
    function lineRange(v, s, e) {
        const startIdx = v.lastIndexOf('\n', s - 1) + 1;
        let endIdx;
        if (e > s && v[e - 1] === '\n') endIdx = e - 1;
        else {
            endIdx = v.indexOf('\n', e);
            if (endIdx === -1) endIdx = v.length;
        }
        return { startIdx, endIdx };
    }

    // Ctrl/⌘ + /：整行注释开关（// ）
    function toggleLineComment() {
        const ta = codeEditorEl;
        const v = ta.value;
        const s = ta.selectionStart;
        const e2 = ta.selectionEnd;
        const { startIdx, endIdx } = lineRange(v, s, e2);
        const lines = v.slice(startIdx, endIdx).split('\n');
        const filled = lines.filter((ln) => ln.trim() !== '');
        const allCommented = filled.length > 0 && filled.every((ln) => /^\s*\/\//.test(ln));

        let deltaFirst = 0;
        let deltaAll = 0;
        const out = lines.map((ln, i) => {
            if (ln.trim() === '') return ln;                 // 空行跳过
            let nl;
            if (allCommented) {
                nl = ln.replace(/^(\s*)\/\/\s?/, '$1');      // 去掉注释
            } else {
                const ind = (ln.match(/^\s*/) || [''])[0];
                nl = ind + '// ' + ln.slice(ind.length);     // 加注释
            }
            const d = nl.length - ln.length;
            if (i === 0) deltaFirst = d;
            deltaAll += d;
            return nl;
        }).join('\n');

        ta.value = v.slice(0, startIdx) + out + v.slice(endIdx);
        ta.selectionStart = Math.max(startIdx, s + deltaFirst);
        ta.selectionEnd = Math.max(ta.selectionStart, e2 + deltaAll);
        refreshCodeEditor();
    }

    // Alt+↑/↓ 移动行；Shift+Alt+↑/↓ 复制行（VS Code 默认键位）
    function moveLines(up, copy) {
        const ta = codeEditorEl;
        const v = ta.value;
        if (!v) return;
        const s = ta.selectionStart;
        const e2 = ta.selectionEnd;
        const { startIdx, endIdx } = lineRange(v, s, e2);
        const block = v.slice(startIdx, endIdx);

        if (copy) {
            if (up) {
                if (startIdx === 0) return;
                ta.value = v.slice(0, startIdx) + block + '\n' + v.slice(startIdx);
                ta.selectionStart = s + block.length + 1;
                ta.selectionEnd = e2 + block.length + 1;
            } else {
                if (endIdx >= v.length) return;
                ta.value = v.slice(0, endIdx) + '\n' + block + v.slice(endIdx);
                ta.selectionStart = s;
                ta.selectionEnd = e2;
            }
            refreshCodeEditor();
            return;
        }

        if (up) {
            if (startIdx === 0) return;                                     // 已在首行
            const prevStart = v.lastIndexOf('\n', startIdx - 2) + 1;
            const prevLine = v.slice(prevStart, startIdx - 1);
            ta.value = v.slice(0, prevStart) + block + '\n' + prevLine + v.slice(endIdx);
            const shift = -(prevLine.length + 1);
            ta.selectionStart = s + shift;
            ta.selectionEnd = e2 + shift;
        } else {
            if (endIdx >= v.length) return;                                 // 已在末行
            const nextStart = endIdx + 1;
            let nextEnd = v.indexOf('\n', nextStart);
            if (nextEnd === -1) nextEnd = v.length;
            const nextLine = v.slice(nextStart, nextEnd);
            ta.value = v.slice(0, startIdx) + nextLine + '\n' + block + v.slice(nextEnd);
            const shift = nextLine.length + 1;
            ta.selectionStart = s + shift;
            ta.selectionEnd = e2 + shift;
        }
        refreshCodeEditor();
    }

    const CLOSERS = { ')': 1, ']': 1, '}': 1, '"': 1, "'": 1 };

    function handleCodeKeydown(e) {
        const ta = codeEditorEl;

        // 运行：Ctrl/⌘ + Enter
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            submit();
            return;
        }
        // 整行注释：Ctrl/⌘ + /
        if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key === '/') {
            e.preventDefault();
            toggleLineComment();
            return;
        }
        // 移动 / 复制行：Alt+↑/↓、Shift+Alt+↑/↓（避开 Ctrl+Alt 组合）
        if (e.altKey && !e.ctrlKey && !e.metaKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
            e.preventDefault();
            moveLines(e.key === 'ArrowUp', e.shiftKey);
            return;
        }
        if (e.ctrlKey || e.metaKey || e.altKey) return;

        if (e.key === 'Tab') {
            e.preventDefault();
            applyIndent(e.shiftKey);
            return;
        }
        if (e.key === 'Enter') {
            if (autoIndentOnEnter()) e.preventDefault();
            return;
        }
        if (e.key === 'Home') {
            if (smartHome()) e.preventDefault();
            return;
        }

        const v = ta.value;
        const s = ta.selectionStart;
        const en = ta.selectionEnd;

        // 右半边已存在：跳过而非重复输入（引号也走这里，需在自动配对之前）
        if (CLOSERS[e.key] && s === en && v[s] === e.key) {
            e.preventDefault();
            ta.selectionStart = ta.selectionEnd = s + 1;
            onCaretActivity();
            return;
        }

        // 输入 } 时：整行只有缩进 → 反缩进一级（VS Code 行为）
        if (e.key === '}' && s === en) {
            const lineStart = v.lastIndexOf('\n', s - 1) + 1;
            const before = v.slice(lineStart, s);
            if (before.length >= INDENT.length && /^[ \t]*$/.test(before)) {
                const remove = before.endsWith(INDENT)
                    ? INDENT.length
                    : (before.length % INDENT.length) || INDENT.length;
                e.preventDefault();
                ta.value = v.slice(0, s - remove) + '}' + v.slice(s);
                ta.selectionStart = ta.selectionEnd = s - remove + 1;
                refreshCodeEditor();
                return;
            }
        }

        // Backspace：① 成对括号/引号删左半边时连带右半边；② 缩进区内智能反缩进（VS Code）
        if (e.key === 'Backspace' && s === en) {
            const prev = v[s - 1];
            if (PAIRS[prev] && PAIRS[prev] === v[s]) {
                e.preventDefault();
                ta.value = v.slice(0, s - 1) + v.slice(s + 1);
                ta.selectionStart = ta.selectionEnd = s - 1;
                refreshCodeEditor();
                return;
            }
            // 缩进区内：一次退到上一个缩进制表位（不再一格一格删空格）
            if (smartBackspace()) e.preventDefault();
            return;
        }

        // 自动补全另一半括号 / 引号
        if (PAIRS[e.key]) {
            const prevCh = s > 0 ? v[s - 1] : '';
            const nextCh = v[s] || '';
            const isQuote = (e.key === '"' || e.key === "'");
            // 引号：词内引号（如 don't）、紧跟同种引号、转义后 —— 都不自动补
            if (isQuote && (/[\w\\]/.test(prevCh) || prevCh === e.key)) return;
            e.preventDefault();
            if (s !== en) {
                const sel = v.slice(s, en);
                ta.value = v.slice(0, s) + e.key + sel + PAIRS[e.key] + v.slice(en);
                ta.selectionStart = s + 1;
                ta.selectionEnd = en + 1;
            } else {
                ta.value = v.slice(0, s) + e.key + PAIRS[e.key] + v.slice(s);
                ta.selectionStart = ta.selectionEnd = s + 1;
            }
            refreshCodeEditor();
            return;
        }
    }

    // ---------- 事件绑定 ----------
    function bindEvents() {
        ensureCodeRefs();
        applyEditorTheme(loadEditorTheme());   // 启动时恢复上次选择的编辑器主题
        if (codeThemeSelEl) {
            codeThemeSelEl.addEventListener('change', () => {
                const name = codeThemeSelEl.value;
                applyEditorTheme(name);
                saveEditorTheme(name);
            });
        }
        bindTabs();
        submitBtn.addEventListener('click', submit);
        resetBtn.addEventListener('click', () => {
            if (!currentExercise) return;
            clearDraft(currentExercise.id, currentTier);   // 重置 = 回到初始代码并丢弃草稿
            clearTimeout(draftTimer); draftTimer = null;
            renderTier(currentTier);
        });
        answerSubmitBtn.addEventListener('click', submit);

        codeEditorEl.addEventListener('keydown', handleCodeKeydown);
        codeEditorEl.addEventListener('input', () => { refreshCodeEditor(); scheduleSaveDraft(); });
        codeEditorEl.addEventListener('blur', saveDraftNow);
        codeEditorEl.addEventListener('scroll', syncCodeScroll);
        // 页面隐藏 / 关闭前落盘（清掉未触发的防抖，防漏存）
        document.addEventListener('visibilitychange', () => { if (document.hidden) flushDraft(); });
        // 光标移动（方向键 / 点击 / 选择 / 聚焦）→ 状态栏 + 跟随滚动 + 当前行高亮
        ['keyup', 'click', 'select', 'focus'].forEach((ev) => {
            codeEditorEl.addEventListener(ev, onCaretActivity);
        });
    }

    // ---------- 提交（按题型分支） ----------
    async function submit() {
        if (!currentExercise) return;
        if (currentExercise.type === 'choice') { submitChoice(); return; }
        if (currentExercise.type === 'blank') { submitBlank(); return; }
        submitCode();
    }

    function showResultLoading(text) {
        resultCardEl.classList.remove('is-pass', 'is-fail');
        resultBodyEl.innerHTML = '<div class="loading">' + esc(text || '判定中...') + '</div>';
        switchTab('result');
    }

    // ---------- 客观题：选择 ----------
    async function submitChoice() {
        const sel = answerBodyEl.querySelector('input[name="practiceChoice"]:checked');
        if (!sel) {
            showToast('请先选择一个答案', 'error');
            return;
        }
        showResultLoading('判定中...');
        try {
            const data = await postJson('/api/practice/answer', {
                exercise_id: currentExercise.id,
                answer: sel.value,
            });
            renderObjResult(data);
        } catch (e) {
            renderJudgeDown();
        }
        revealResult();
    }

    // ---------- 客观题：填空 ----------
    async function submitBlank() {
        const inputs = questionCardEl.querySelectorAll('input[data-blank]');
        const answers = Array.from(inputs).map((i) => i.value);
        if (answers.some((a) => !a.trim())) {
            showToast('请填完所有空位', 'error');
            return;
        }
        showResultLoading('判定中...');
        try {
            const data = await postJson('/api/practice/answer', {
                exercise_id: currentExercise.id,
                answer: answers,
            });
            renderObjResult(data);
        } catch (e) {
            renderJudgeDown();
        }
        revealResult();
    }

    // ---------- 写代码题：沙箱判定 ----------
    async function submitCode() {
        const code = codeEditorEl.value.trim();
        if (!code) {
            showToast('请先编写代码再提交', 'error');
            return;
        }
        submitBtn.disabled = true;
        submitBtn.textContent = '判定中...';
        showResultLoading('编译运行中...');

        try {
            const data = await postJson('/api/practice/submit', {
                exercise_id: currentExercise.id,
                tier: currentTier,
                code: code,
            });
            renderResult(data);
        } catch (err) {
            renderJudgeDown();
        }
        revealResult();

        submitBtn.disabled = false;
        submitBtn.textContent = '提交运行';
    }

    // ---------- 结果渲染 ----------
    function renderJudgeDown() {
        resultCardEl.classList.remove('is-pass');
        resultCardEl.classList.add('is-fail');
        resultBodyEl.innerHTML = [
            '<div class="practice-result-head practice-result-fail">',
            '<span class="practice-result-icon">⚠</span>',
            '<span>判定服务不可用</span>',
            '</div>',
            '<p class="practice-result-note">无法连接判定服务，请稍后重试。</p>',
        ].join('');
    }

    function renderObjResult(data) {
        if (data && data.correct) {
            resultCardEl.classList.remove('is-fail');
            resultCardEl.classList.add('is-pass');
            resultBodyEl.innerHTML = [
                '<div class="practice-result-head practice-result-pass">',
                '<span class="practice-result-icon">✓</span>',
                '<span>回答正确</span>',
                '</div>',
            ].join('');
            markDone(currentExercise.id);
            return;
        }
        resultCardEl.classList.remove('is-pass');
        resultCardEl.classList.add('is-fail');
        resultBodyEl.innerHTML = [
            '<div class="practice-result-head practice-result-fail">',
            '<span class="practice-result-icon">✗</span>',
            '<span>' + esc((data && data.message) || '回答错误') + '</span>',
            '</div>',
        ].join('');
    }

    function renderResult(result) {
        const status = result.status || (result.success ? 'passed' : 'failed');

        if (status === 'passed') {
            resultCardEl.classList.remove('is-fail');
            resultCardEl.classList.add('is-pass');
            resultBodyEl.innerHTML = [
                '<div class="practice-result-head practice-result-pass">',
                '<span class="practice-result-icon">✓</span>',
                '<span>通过全部 ' + (result.total || 0) + ' 个用例</span>',
                '</div>',
                '<p class="practice-result-note">本档已通关。可尝试更高难度档位。</p>',
            ].join('');
            markDone(currentExercise.id);
            return;
        }

        resultCardEl.classList.remove('is-pass');
        resultCardEl.classList.add('is-fail');

        if (status === 'compile_error') {
            resultBodyEl.innerHTML = [
                '<div class="practice-result-head practice-result-fail">',
                '<span class="practice-result-icon">✗</span>',
                '<span>编译失败</span>',
                '</div>',
                '<p class="practice-result-msg">' + esc(result.message || '') + '</p>',
                '<pre class="practice-result-output">' + esc(result.compile_output || '') + '</pre>',
            ].join('');
            return;
        }

        if (status === 'timeout' || status === 'runtime_error') {
            resultBodyEl.innerHTML = [
                '<div class="practice-result-head practice-result-fail">',
                '<span class="practice-result-icon">✗</span>',
                '<span>' + (status === 'timeout' ? '运行超时' : '运行出错') + '</span>',
                '</div>',
                '<p class="practice-result-msg">' + esc(result.message || '') + '</p>',
                '<pre class="practice-result-output">' + esc(result.runtime_output || '') + '</pre>',
            ].join('');
            return;
        }

        resultBodyEl.innerHTML = [
            '<div class="practice-result-head practice-result-fail">',
            '<span class="practice-result-icon">✗</span>',
            '<span>通过 ' + (result.passed || 0) + ' / ' + (result.total || 0) + ' 个用例</span>',
            '</div>',
            '<p class="practice-result-msg">' + esc(result.message || '') + '</p>',
            '<pre class="practice-result-output">' + esc(result.runtime_output || '') + '</pre>',
        ].join('');
    }

    // ---------- 启动 ----------
    document.addEventListener('DOMContentLoaded', () => {
        bindEvents();
        loadChapters();
    });
})();
