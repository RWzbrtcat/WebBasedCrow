// ============================================
// 首页 Dashboard：最近更新 / 每日一题 / 练习闯关进度
// 三个模块相互独立，任一失败只影响自己的卡片。
// ============================================
(function () {
    const API = '/api';

    async function getJSON(url) {
        const r = await fetch(url, { headers: { 'Content-Type': 'application/json' } });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
    }

    function esc(s) {
        const d = document.createElement('div');
        d.textContent = s == null ? '' : String(s);
        return d.innerHTML;
    }

    // 时间戳 → "10月19日"
    function fmtDate(s) {
        if (!s) return '';
        const d = new Date(String(s).replace(' ', 'T'));
        if (isNaN(d.getTime())) return String(s);
        return d.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' });
    }

    function timeValue(s) {
        const t = new Date(String(s || '').replace(' ', 'T')).getTime();
        return isNaN(t) ? 0 : t;
    }

    // ---------- 左栏：最近修改的 5 篇文章 ----------
    async function loadRecentPosts() {
        const host = document.getElementById('dashPostList');
        if (!host) return;
        const foot = document.getElementById('dashPostsFoot');
        try {
            const data = await getJSON(API + '/posts');
            const posts = (data.posts || []).filter((p) => p.status !== 'draft');
            posts.sort((a, b) => timeValue(b.updated_at || b.created_at) - timeValue(a.updated_at || a.created_at));

            const top = posts.slice(0, 5);
            if (foot) {
                foot.textContent = posts.length
                    ? '共 ' + posts.length + ' 篇 · 最近更新 ' + fmtDate(posts[0].updated_at || posts[0].created_at)
                    : '';
            }
            if (!top.length) {
                host.innerHTML = '<li class="dash-empty">还没有文章</li>';
                return;
            }

            host.innerHTML = top.map((p) => {
                const href = '/post?id=' + encodeURIComponent(p.id);
                const topic = (p.topic || '').trim();
                const tag = topic ? '<span class="dash-tag">' + esc(topic) + '</span>' : '';
                return (
                    '<li class="dash-post-item">' +
                        '<a class="dash-post-link" href="' + href + '">' +
                            '<span class="dash-post-title">' + esc(p.title || '无标题') + '</span>' +
                            '<span class="dash-post-side">' + tag +
                                '<span class="dash-post-date">' + fmtDate(p.updated_at || p.created_at) + '</span>' +
                            '</span>' +
                        '</a>' +
                    '</li>'
                );
            }).join('');
        } catch (e) {
            console.warn('[home] 最近文章加载失败', e);
            host.innerHTML = '<li class="dash-empty">加载失败，请稍后重试</li>';
        }
    }

    // ---------- 右上：每日一题 ----------
    async function loadDaily() {
        const qEl = document.getElementById('dashDailyQuestion');
        const metaEl = document.getElementById('dashDailyMeta');
        const dateEl = document.getElementById('dashDailyDate');
        const streakEl = document.getElementById('dashDailyStreak');
        if (!qEl) return;

        try {
            const d = await getJSON(API + '/daily');
            if (!d || !d.available) {
                qEl.textContent = '今日暂无题目';
                return;
            }
            const level = Number(d.difficulty);
            const diff = level === 1 ? '基础' : level === 3 ? '困难' : '进阶';

            dateEl.textContent = d.date || '';
            qEl.textContent = d.question || '';
            metaEl.textContent = [d.category, diff].filter(Boolean).join(' · ');
            streakEl.textContent = d.streak > 0 ? '连答 ' + d.streak + ' 天' : '';
        } catch (e) {
            console.warn('[home] 每日一题加载失败', e);
            qEl.textContent = '加载失败，点击进入查看';
        }
    }

    // ---------- 右下：练习闯关进度 ----------
    // 进度属于个人数据：未登录一律显示 0（不请求服务端进度），登录后才展示自己的完成情况。
    let authCache = null;
    async function isAuthed() {
        if (authCache !== null) return authCache;
        try {
            authCache = await (window.__blogAuthPromise || fetch(API + '/auth').then((r) => r.json()))
                .then((d) => !!(d && d.authed));
        } catch (e) {
            authCache = false;
        }
        return authCache;
    }

    function renderPracticeProgress(done, total) {
        const barEl = document.getElementById('dashPracticeBar');
        const textEl = document.getElementById('dashPracticeText');
        const pctEl = document.getElementById('dashPracticePct');
        const pct = total ? Math.round((done / total) * 100) : 0;
        if (barEl) barEl.style.width = pct + '%';
        if (textEl) textEl.textContent = '已完成 ' + done + ' / ' + total + ' 题';
        if (pctEl) pctEl.innerHTML = pct + '<small>%</small>';
    }

    async function loadPractice() {
        const metaEl = document.getElementById('dashPracticeMeta');
        if (!metaEl) return;

        // 章节规模是公开信息，始终展示
        let chapters = 0;
        let total = 0;
        try {
            const chRes = await getJSON(API + '/practice/chapters');
            (chRes.semesters || []).forEach((sem) => {
                (sem.chapters || []).forEach((ch) => {
                    chapters += 1;
                    total += Number(ch.exercise_count) || 0;
                });
            });
            metaEl.textContent = chapters + ' 章 · ' + total + ' 题';
        } catch (e) {
            console.warn('[home] 章节列表加载失败', e);
            metaEl.textContent = '点击进入';
        }

        // 先落一个确定值，避免等待登录态期间显示 "—"
        renderPracticeProgress(0, total);

        // 未登录：固定 0，且不去取任何人的刷题记录
        if (!(await isAuthed())) return;

        try {
            const progRes = await getJSON(API + '/practice/progress').catch(() => ({ passed: [] }));
            const passed = (progRes && progRes.passed) || [];
            renderPracticeProgress(Math.min(passed.length, total), total);
        } catch (e) {
            console.warn('[home] 练习进度加载失败', e);
            renderPracticeProgress(0, total);
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        loadRecentPosts();
        loadDaily();
        loadPractice();
    });
})();
