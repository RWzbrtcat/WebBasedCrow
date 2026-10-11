// ============================================
// 练习闯关：前端逻辑
// 章节/题目目前仍是内置 mock 数据（仅 C1 一道示例题）；
// 提交判定走真实后端 POST /api/practice/submit（沙箱编译运行），
// 后端未部署时降级为「判定未就绪」提示。
// 依赖：daily-common.js（esc / showToast）
// ============================================
(function () {
    'use strict';

    // ---------- 章节数据（mock） ----------
    const SEMESTERS = [
        {
            name: '第一学期 · 语言地基',
            chapters: [
                { id: 1, title: '现代语法糖' },
                { id: 2, title: '移动语义与完美转发' },
                { id: 3, title: '智能指针与 RAII' },
                { id: 4, title: 'Lambda 与函数式' },
                { id: 5, title: '模板与元编程基础' },
                { id: 6, title: '现代工具类型' },
            ],
        },
        {
            name: '第二学期 · 后端应用',
            chapters: [
                { id: 7, title: 'STL 容器与算法' },
                { id: 8, title: '文件操作与流' },
                { id: 9, title: '多线程与并发' },
                { id: 10, title: '网络编程' },
                { id: 11, title: '数据库交互' },
            ],
        },
        {
            name: '第三学期 · 进阶工程',
            chapters: [
                { id: 12, title: 'constexpr 与编译期计算' },
                { id: 13, title: 'C++20 高级特性' },
                { id: 14, title: '模块与工程实践' },
            ],
        },
    ];

    // ---------- 题目数据（mock，仅 C1 有一道完整示例题） ----------
    const EXERCISES = [
        {
            id: 1,
            chapterId: 1,
            title: '短题 1 · auto 与 decltype 推导',
            type: 'short',
            promptHtml: [
                '<p>实现两个函数，验证 <code>auto</code> 的类型推导规则：</p>',
                '<ol>',
                '<li><code>get_ref()</code>：返回 <code>g_value</code> 的引用</li>',
                '<li><code>get_value()</code>：返回 <code>g_value</code> 的值拷贝</li>',
                '</ol>',
                '<p>考点：<code>auto&amp;</code> 保留引用，<code>auto</code> 丢失引用与顶层 const。</p>',
            ].join(''),
            tiers: {
                easy: {
                    label: '入门',
                    starter: [
                        '// 全局变量（题目已提供，请勿修改）',
                        'int g_value = 42;',
                        '',
                        '// TODO: 补全返回类型 —— get_ref 应返回 g_value 的「引用」',
                        '// 提示：返回类型写 int&，函数体 return g_value;',
                        '____ get_ref() {',
                        '    return g_value;',
                        '}',
                        '',
                        '// TODO: 补全返回类型 —— get_value 应返回 g_value 的「值拷贝」',
                        '// 提示：返回类型写 int（值），函数体 return g_value;',
                        '____ get_value() {',
                        '    return g_value;',
                        '}',
                        '',
                        '// 只实现函数，不要写 main（隐藏测试会提供）',
                    ].join('\n'),
                },
                medium: {
                    label: '进阶',
                    starter: [
                        '// 进阶：只给接口签名，自己实现函数体',
                        'int g_value = 42;',
                        '',
                        'int& get_ref() {',
                        '    // TODO: 返回 g_value 的引用',
                        '}',
                        '',
                        'int get_value() {',
                        '    // TODO: 返回 g_value 的值拷贝',
                        '}',
                        '',
                        '// 只实现函数，不要写 main（隐藏测试会提供）',
                    ].join('\n'),
                },
                hard: {
                    label: '挑战',
                    starter: [
                        '// 挑战：用 decltype(auto) 让返回值类别与表达式完全一致',
                        'int g_value = 42;',
                        '',
                        'decltype(auto) get_ref() {',
                        '    // TODO: 返回 g_value（引用类别）',
                        '}',
                        '',
                        'int get_value() {',
                        '    // TODO: 返回 g_value 的值拷贝',
                        '}',
                        '',
                        '// 只实现函数，不要写 main（隐藏测试会提供）',
                    ].join('\n'),
                },
            },
        },
    ];

    const EXERCISE_BY_CHAPTER = {};
    EXERCISES.forEach((e) => { EXERCISE_BY_CHAPTER[e.chapterId] = e; });

    // ---------- 状态 ----------
    let currentChapter = 1;
    let currentExercise = null;
    let currentTier = 'easy';

    // ---------- DOM ----------
    const chapterListEl = document.getElementById('chapterList');
    const questionCardEl = document.getElementById('questionCard');
    const codeEditorEl = document.getElementById('codeEditor');
    const resultCardEl = document.getElementById('resultCard');
    const resultBodyEl = document.getElementById('resultBody');
    const submitBtn = document.getElementById('submitBtn');
    const resetBtn = document.getElementById('resetBtn');

    // ---------- 渲染章节列表 ----------
    function renderChapters() {
        let html = '';
        SEMESTERS.forEach((sem) => {
            html += '<div class="practice-semester">' + esc(sem.name) + '</div>';
            sem.chapters.forEach((ch) => {
                const active = ch.id === currentChapter ? ' active' : '';
                const hasEx = EXERCISE_BY_CHAPTER[ch.id] ? '' : ' is-empty';
                html += '<button type="button" class="practice-chapter' + active + hasEx + '" data-id="' + ch.id + '">' +
                    '<span class="practice-chapter-num">C' + ch.id + '</span>' +
                    '<span class="practice-chapter-title">' + esc(ch.title) + '</span>' +
                    '</button>';
            });
        });
        chapterListEl.innerHTML = html;

        chapterListEl.querySelectorAll('.practice-chapter').forEach((btn) => {
            btn.addEventListener('click', () => {
                selectChapter(Number(btn.dataset.id));
            });
        });
    }

    // ---------- 选中章节 ----------
    function selectChapter(id) {
        currentChapter = id;
        currentTier = 'easy';
        currentExercise = EXERCISE_BY_CHAPTER[id] || null;
        renderChapters();
        if (currentExercise) {
            loadExercise();
        } else {
            renderEmptyChapter();
        }
    }

    // ---------- 加载题目 ----------
    function loadExercise() {
        renderQuestion();
        renderTier(currentTier);
        resultCardEl.hidden = true;
    }

    // ---------- 渲染题目 ----------
    function renderQuestion() {
        const ex = currentExercise;
        const tier = ex.tiers[currentTier];
        questionCardEl.innerHTML = [
            '<div class="practice-question-head">',
            '<span class="daily-badge">写代码</span>',
            '<h2 class="practice-question-title">' + esc(ex.title) + '</h2>',
            '</div>',
            '<div class="practice-question-prompt">' + ex.promptHtml + '</div>',
            '<div class="practice-tier-bar" id="tierBar"></div>',
        ].join('');
        bindTierBar();
    }

    // ---------- 难度档位切换 ----------
    function bindTierBar() {
        const bar = document.getElementById('tierBar');
        if (!bar) return;
        const ex = currentExercise;
        bar.innerHTML = Object.keys(ex.tiers).map((key) => {
            const t = ex.tiers[key];
            const active = key === currentTier ? ' active' : '';
            return '<button type="button" class="practice-tier' + active + '" data-tier="' + key + '">' + esc(t.label) + '</button>';
        }).join('');
        bar.querySelectorAll('.practice-tier').forEach((btn) => {
            btn.addEventListener('click', () => {
                currentTier = btn.dataset.tier;
                renderTier(currentTier);
            });
        });
    }

    function renderTier(tierKey) {
        const tier = currentExercise.tiers[tierKey];
        codeEditorEl.value = tier.starter;
        resultCardEl.hidden = true;
        // 更新 tierBar 的 active 态
        const bar = document.getElementById('tierBar');
        if (bar) {
            bar.querySelectorAll('.practice-tier').forEach((btn) => {
                btn.classList.toggle('active', btn.dataset.tier === tierKey);
            });
        }
    }

    // ---------- 空章节占位 ----------
    function renderEmptyChapter() {
        questionCardEl.innerHTML = [
            '<div class="practice-question-head">',
            '<h2 class="practice-question-title">题目待补充</h2>',
            '</div>',
            '<p class="practice-empty-hint">本章题面已设计（见 docs/practice-bank.md），',
            '尚未录入到前端。当前仅 C1 有一道完整示例题用于跑通交互。</p>',
        ].join('');
        codeEditorEl.value = '';
        resultCardEl.hidden = true;
        const tierBar = document.getElementById('tierBar');
        if (tierBar) tierBar.innerHTML = '';
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
            // 后端未就绪（本地预览 / 沙箱未部署）
            resultBodyEl.innerHTML = [
                '<div class="practice-result-head practice-result-fail">',
                '<span class="practice-result-icon">⚠</span>',
                '<span>后端判定未就绪</span>',
                '</div>',
                '<p class="practice-result-note">无法连接判定服务。请在服务器部署后重试（见 docs/practice-sandbox.md）。</p>',
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
                '<p class="practice-result-note">入门档通关即得 1 星。可尝试「进阶」或「挑战」档。</p>',
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
        renderChapters();
        selectChapter(1);
        bindEvents();
    });
})();
