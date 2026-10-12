// ============================================
// 练习闯关：前端逻辑
// 布局：左栏「章节 + 当前章题目」两级树，右栏答题工作台
//       （题目描述卡 | 编辑器·作答卡 并排）。
//       描述卡内 = 标签栏「题目描述 | 题解」共用一栏（默认题目描述，点题解切换）
//       + 底部固定「测试结果」条。
// 数据全部来自后端接口：
//   GET  /api/practice/chapters            章节列表（按学期分组）
//   GET  /api/practice/exercises?chapter=N 某章题目列表
//   GET  /api/practice/exercise/<id>       单题详情（题干 + 题解 + 三档脚手架/选项）
//   POST /api/practice/submit              写代码题：沙箱编译运行判定
//   POST /api/practice/answer              客观题（选择/填空）：对答案
// 题型：choice(选择) / blank(填空) / short(写代码) / boss(项目关)。
// 「已完成」状态为本地记录（localStorage），无后端依赖，清缓存即重置。
// 依赖：daily-common.js（esc / showToast / apiRequest / describeFetchError）、
//       markdown.js（renderMarkdownInto，渲染题干与题解）。
// ============================================
(function () {
    'use strict';

    // ---------- 状态 ----------
    let chaptersData = null;      // /api/practice/chapters 返回的 semesters
    let currentChapter = null;    // 当前选中章节 id
    let chapterExercises = [];    // 当前章的题目列表
    let currentExercise = null;   // 当前题目详情（/api/practice/exercise/<id> 返回）
    let currentTier = 'easy';
    let doneSet = loadDone();     // 本地记录：已通过的题目 id

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

    const TIER_LABELS = { easy: '入门', medium: '进阶', hard: '挑战' };
    const TYPE_BADGES = { choice: '选择', blank: '填空', short: '写代码', boss: 'Boss' };
    const DONE_KEY = 'practice.done.v1';

    // 描述卡为「题目描述 | 题解」共用一栏：点击标签切换，默认题目描述。
    // 题解面板为静态节点（见 practice.html），此处不再动态注入宿主。

    function badgeFor(type) {
        return TYPE_BADGES[type] || '写代码';
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
            updateProgress();
            renderChapters();
            autoSelectFirst();
        } catch (e) {
            chapterListEl.innerHTML = '<div class="empty-state">' + esc(describeFetchError(e)) + '</div>';
        }
    }

    // ---------- 渲染左栏：章节 + 当前章题目（两级树） ----------
    function renderChapters() {
        if (!chaptersData) return;
        let html = '';
        chaptersData.forEach((sem) => {
            html += '<div class="practice-semester">' + esc(sem.name) + '</div>';
            (sem.chapters || []).forEach((ch) => {
                const active = ch.id === currentChapter ? ' active' : '';
                const empty = ch.exercise_count > 0 ? '' : ' is-empty';
                html += '<button type="button" class="practice-chapter' + active + empty + '" data-id="' + ch.id + '">' +
                    '<span class="practice-chapter-num">C' + ch.id + '</span>' +
                    '<span class="practice-chapter-title">' + esc(ch.title) + '</span>' +
                    '<span class="practice-chapter-count">' + (ch.exercise_count || 0) + '</span>' +
                    '</button>';
                if (ch.id === currentChapter && chapterExercises.length) {
                    html += renderExerciseList();
                }
            });
        });
        chapterListEl.innerHTML = html;

        chapterListEl.querySelectorAll('.practice-chapter').forEach((btn) => {
            btn.addEventListener('click', () => selectChapter(Number(btn.dataset.id)));
        });
        chapterListEl.querySelectorAll('.practice-ex-item').forEach((btn) => {
            btn.addEventListener('click', () => selectExercise(Number(btn.dataset.id)));
        });
        scrollSideToCurrent();
    }

    // 当前章题目列表 HTML（每题：状态点 + 题型 + 标题）
    function renderExerciseList() {
        return '<div class="practice-ex-list">' + chapterExercises.map((ex) => {
            const isCur = !!(currentExercise && currentExercise.id === ex.id);
            const done = doneSet.has(ex.id);
            const dot = done ? '✓' : (isCur ? '●' : '○');
            const cls = 'practice-ex-item' + (isCur ? ' current' : '') + (done ? ' done' : '');
            return '<button type="button" class="' + cls + '" data-id="' + ex.id + '">' +
                '<span class="practice-ex-dot">' + dot + '</span>' +
                '<span class="practice-ex-badge">' + esc(badgeFor(ex.type)) + '</span>' +
                '<span class="practice-ex-title">' + esc(ex.title) + '</span>' +
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
        for (const sem of chaptersData) {
            for (const ch of (sem.chapters || [])) {
                if (ch.exercise_count > 0) { selectChapter(ch.id); return; }
            }
        }
        const first = chaptersData[0] && (chaptersData[0].chapters || [])[0];
        if (first) selectChapter(first.id);
        else showIdleState();
    }

    // ---------- 选中章节：拉题目列表 ----------
    async function selectChapter(id) {
        currentChapter = id;
        currentExercise = null;
        chapterExercises = [];
        renderChapters();
        try {
            const data = await apiRequest('/api/practice/exercises?chapter=' + id);
            chapterExercises = data.exercises || [];
            renderChapters();
            if (chapterExercises.length) {
                // 优先跳到本章第一道未完成的题，全部完成则回到第一题
                const firstTodo = chapterExercises.find((ex) => !doneSet.has(ex.id)) || chapterExercises[0];
                selectExercise(firstTodo.id);
            } else {
                showEmptyState('本章题目尚未录入。');
            }
        } catch (e) {
            showEmptyState(describeFetchError(e));
        }
    }

    // ---------- 选中题目：拉详情 ----------
    async function selectExercise(id) {
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

    // ---------- 工作台布局：双列 / 单列 ----------
    function setWorkLayout(single) {
        workBodyEl.classList.toggle('single', !!single);
    }

    function renderHead(ex) {
        workHeadEl.hidden = false;
        workHeadEl.innerHTML =
            '<span class="practice-badge">' + esc(badgeFor(ex.type)) + '</span>' +
            '<h2 class="practice-work-title">' + esc(ex.title) + '</h2>' +
            '<span class="practice-work-pos">' + esc(posText()) + '</span>';
    }

    function posText() {
        const total = chapterExercises.length;
        const idx = chapterExercises.findIndex((e) => currentExercise && e.id === currentExercise.id);
        if (idx < 0 || !total || currentChapter == null) return '';
        return 'C' + currentChapter + ' · 第 ' + (idx + 1) + ' / ' + total + ' 题';
    }

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

    // 描述卡「题目描述 | 题解」标签切换（共用一栏，默认题目描述）
    function switchTab(name) {
        const isSol = name === 'solution';
        if (descPaneEl) descPaneEl.hidden = isSol;
        if (solutionPaneEl) solutionPaneEl.hidden = !isSol;
        if (tabDescEl) {
            tabDescEl.classList.toggle('is-active', !isSol);
            tabDescEl.setAttribute('aria-selected', String(!isSol));
        }
        if (tabSolutionEl) {
            tabSolutionEl.classList.toggle('is-active', isSol);
            tabSolutionEl.setAttribute('aria-selected', String(isSol));
        }
    }

    function bindTabs() {
        if (tabDescEl) tabDescEl.addEventListener('click', () => switchTab('desc'));
        if (tabSolutionEl) tabSolutionEl.addEventListener('click', () => switchTab('solution'));
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
        clearResult();
    }

    // 选择题：题干 | 选项
    function renderChoice() {
        const ex = currentExercise;
        setWorkLayout(false);
        renderHead(ex);
        setPromptHtml('<div class="practice-prompt markdown-body" id="promptBody"></div>');
        renderPromptInto();
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
        clearResult();
    }

    // 填空题：单列，题干内嵌输入框 + 底部提交
    function renderBlank() {
        const ex = currentExercise;
        setWorkLayout(true);
        renderHead(ex);
        const codeHtml = esc(ex.prompt || '').replace(/_{3,}/g,
            '<input type="text" class="practice-blank-input" data-blank spellcheck="false" autocomplete="off">');
        setPromptHtml([
            '<div class="practice-prompt"><pre class="practice-blank-code"><code>' + codeHtml + '</code></pre></div>',
            '<div class="practice-editor-actions">',
            '<button type="button" class="btn btn-primary" id="blankSubmitBtn">提交答案</button>',
            '</div>',
        ].join(''));
        const blankBtn = document.getElementById('blankSubmitBtn');
        if (blankBtn) blankBtn.addEventListener('click', submit);
        editorCardEl.hidden = true;
        answerCardEl.hidden = true;
        renderSolution();
        switchTab('desc');
        clearResult();
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
        clearResult();
    }

    function clearResult() {
        resultCardEl.hidden = true;
        resultCardEl.classList.remove('is-pass', 'is-fail');
        resultBodyEl.innerHTML = '';
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
                currentTier = btn.dataset.tier;
                renderTier(currentTier);
            });
        });
    }

    function renderTier(tierKey) {
        const tiers = currentExercise.tiers || {};
        const tier = tiers[tierKey] || {};
        codeEditorEl.value = tier.starter || '';
        clearResult();
        const bar = document.getElementById('tierBar');
        if (bar) {
            bar.querySelectorAll('.practice-tier').forEach((btn) => {
                btn.classList.toggle('active', btn.dataset.tier === tierKey);
            });
        }
    }

    // ---------- 事件绑定 ----------
    function bindEvents() {
        bindTabs();
        submitBtn.addEventListener('click', submit);
        resetBtn.addEventListener('click', () => {
            if (currentExercise) renderTier(currentTier);
        });
        answerSubmitBtn.addEventListener('click', submit);
        codeEditorEl.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                submit();
            }
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
        resultCardEl.hidden = false;
        resultCardEl.classList.remove('is-pass', 'is-fail');
        resultBodyEl.innerHTML = '<div class="loading">' + esc(text || '判定中...') + '</div>';
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
