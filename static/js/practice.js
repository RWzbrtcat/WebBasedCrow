// ============================================
// 练习闯关：前端逻辑
// 数据全部来自后端接口：
//   GET /api/practice/chapters        章节列表（按学期分组）
//   GET /api/practice/exercises?chapter=N  某章题目列表
//   GET /api/practice/exercise/<id>   单题详情（题干 + 三档脚手架）
//   POST /api/practice/submit         提交代码，沙箱编译运行判定
// 交互流：章节 → 题目列表 → 题目详情（题干 + 代码编辑器）→ 提交判定。
// 依赖：daily-common.js（esc / showToast / apiRequest / describeFetchError）、
//       markdown.js（renderMarkdownInto，渲染题干）。
// ============================================
(function () {
    'use strict';

    // ---------- 状态 ----------
    let chaptersData = null;      // /api/practice/chapters 返回的 semesters
    let currentChapter = null;    // 当前选中章节 id
    let chapterExercises = [];    // 当前章的题目列表
    let currentExercise = null;   // 当前题目详情（/api/practice/exercise/<id> 返回）
    let currentTier = 'easy';

    // ---------- DOM ----------
    const chapterListEl = document.getElementById('chapterList');
    const questionCardEl = document.getElementById('questionCard');
    const editorCardEl = document.getElementById('editorCard');
    const codeEditorEl = document.getElementById('codeEditor');
    const resultCardEl = document.getElementById('resultCard');
    const resultBodyEl = document.getElementById('resultBody');
    const submitBtn = document.getElementById('submitBtn');
    const resetBtn = document.getElementById('resetBtn');

    const TIER_LABELS = { easy: '入门', medium: '进阶', hard: '挑战' };

    // ---------- 章节列表 ----------
    async function loadChapters() {
        try {
            const data = await apiRequest('/api/practice/chapters');
            chaptersData = data.semesters || [];
            renderChapters();
            autoSelectFirst();
        } catch (e) {
            chapterListEl.innerHTML = '<div class="empty-state">' + esc(describeFetchError(e)) + '</div>';
        }
    }

    function renderChapters() {
        if (!chaptersData) return;
        let html = '';
        chaptersData.forEach((sem) => {
            html += '<div class="practice-semester">' + esc(sem.name) + '</div>';
            (sem.chapters || []).forEach((ch) => {
                const active = ch.id === currentChapter ? ' active' : '';
                const hasEx = ch.exercise_count > 0 ? '' : ' is-empty';
                html += '<button type="button" class="practice-chapter' + active + hasEx + '" data-id="' + ch.id + '">' +
                    '<span class="practice-chapter-num">C' + ch.id + '</span>' +
                    '<span class="practice-chapter-title">' + esc(ch.title) + '</span>' +
                    '</button>';
            });
        });
        chapterListEl.innerHTML = html;

        chapterListEl.querySelectorAll('.practice-chapter').forEach((btn) => {
            btn.addEventListener('click', () => selectChapter(Number(btn.dataset.id)));
        });
    }

    function autoSelectFirst() {
        // 优先选第一个有题目的章节；全空则选第一个章节
        let firstAny = null;
        for (const sem of chaptersData) {
            for (const ch of (sem.chapters || [])) {
                if (firstAny == null) firstAny = ch.id;
                if (ch.exercise_count > 0) {
                    selectChapter(ch.id);
                    return;
                }
            }
        }
        if (firstAny != null) selectChapter(firstAny);
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
            renderExerciseList();
        } catch (e) {
            renderEmptyChapter(describeFetchError(e));
        }
    }

    // ---------- 渲染题目列表 ----------
    function renderExerciseList() {
        hideEditor();
        if (!chapterExercises.length) {
            renderEmptyChapter('本章题目尚未录入。');
            return;
        }
        const items = chapterExercises.map((ex) => {
            const badge = ex.type === 'boss' ? 'Boss' : '写代码';
            return '<button type="button" class="practice-exercise-item" data-id="' + ex.id + '">' +
                '<span class="daily-badge">' + esc(badge) + '</span>' +
                '<span class="practice-exercise-title">' + esc(ex.title) + '</span>' +
                '</button>';
        }).join('');
        questionCardEl.innerHTML = [
            '<div class="practice-question-head">',
            '<h2 class="practice-question-title">选择题目</h2>',
            '</div>',
            '<div class="practice-exercise-list">' + items + '</div>',
        ].join('');
        questionCardEl.querySelectorAll('.practice-exercise-item').forEach((btn) => {
            btn.addEventListener('click', () => selectExercise(Number(btn.dataset.id)));
        });
    }

    // ---------- 选中题目：拉详情 ----------
    async function selectExercise(id) {
        try {
            const data = await apiRequest('/api/practice/exercise/' + id);
            currentExercise = data;
            currentTier = 'easy';
            renderQuestion();
            renderTier(currentTier);
            editorCardEl.hidden = false;
            resultCardEl.hidden = true;
        } catch (e) {
            showToast(describeFetchError(e), 'error');
        }
    }

    // ---------- 渲染题目详情 ----------
    function renderQuestion() {
        const ex = currentExercise;
        const badge = ex.type === 'boss' ? 'Boss' : '写代码';
        questionCardEl.innerHTML = [
            '<div class="practice-question-head">',
            '<span class="daily-badge">' + esc(badge) + '</span>',
            '<h2 class="practice-question-title">' + esc(ex.title) + '</h2>',
            '</div>',
            '<div class="practice-question-prompt markdown-body" id="promptBody"></div>',
            '<div class="practice-tier-bar" id="tierBar"></div>',
        ].join('');

        const promptBody = document.getElementById('promptBody');
        if (window.renderMarkdownInto) {
            renderMarkdownInto(promptBody, ex.prompt || '');
        } else {
            promptBody.textContent = ex.prompt || '';
        }
        bindTierBar();
    }

    // ---------- 难度档位切换 ----------
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
        resultCardEl.hidden = true;
        const bar = document.getElementById('tierBar');
        if (bar) {
            bar.querySelectorAll('.practice-tier').forEach((btn) => {
                btn.classList.toggle('active', btn.dataset.tier === tierKey);
            });
        }
    }

    // ---------- 空章节 / 空状态 ----------
    function renderEmptyChapter(hint) {
        hideEditor();
        questionCardEl.innerHTML = [
            '<div class="practice-question-head">',
            '<h2 class="practice-question-title">题目待补充</h2>',
            '</div>',
            '<p class="practice-empty-hint">' + esc(hint || '本章题面已设计（见 docs/practice-bank.md），尚未录入题库。') + '</p>',
        ].join('');
    }

    function hideEditor() {
        editorCardEl.hidden = true;
        codeEditorEl.value = '';
        resultCardEl.hidden = true;
    }

    // ---------- 事件绑定 ----------
    function bindEvents() {
        submitBtn.addEventListener('click', submit);
        resetBtn.addEventListener('click', () => {
            if (currentExercise) renderTier(currentTier);
        });
        // Ctrl/Cmd + Enter 提交
        codeEditorEl.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                submit();
            }
        });
    }

    // ---------- 提交与判定 ----------
    async function submit() {
        if (!currentExercise) return;
        const code = codeEditorEl.value.trim();
        if (!code) {
            showToast('请先编写代码再提交', 'error');
            return;
        }

        submitBtn.disabled = true;
        submitBtn.textContent = '判定中...';
        resultCardEl.hidden = false;
        resultBodyEl.innerHTML = '<div class="loading">编译运行中...</div>';

        try {
            const resp = await fetch('/api/practice/submit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    exercise_id: currentExercise.id,
                    tier: currentTier,
                    code: code,
                }),
            });
            const data = await resp.json();
            renderResult(data);
        } catch (err) {
            resultBodyEl.innerHTML = [
                '<div class="practice-result-head practice-result-fail">',
                '<span class="practice-result-icon">⚠</span>',
                '<span>判定服务不可用</span>',
                '</div>',
                '<p class="practice-result-note">无法连接判定服务，请稍后重试。</p>',
            ].join('');
        }

        submitBtn.disabled = false;
        submitBtn.textContent = '提交运行';
    }

    // ---------- 渲染判定结果（后端返回格式） ----------
    // 后端返回：{ success, status, passed, total, message, compile_output?, runtime_output? }
    function renderResult(result) {
        const status = result.status || (result.success ? 'passed' : 'failed');

        if (status === 'passed') {
            resultBodyEl.innerHTML = [
                '<div class="practice-result-head practice-result-pass">',
                '<span class="practice-result-icon">✓</span>',
                '<span>通过全部 ' + (result.total || 0) + ' 个用例</span>',
                '</div>',
                '<p class="practice-result-note">本档已通关。可尝试更高难度档位。</p>',
            ].join('');
            return;
        }

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

        // failed：部分用例未过
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
