// 每日一题页面渲染回归验证：Node 模拟最小 DOM + 假接口，执行 daily.js / daily-question.js 全流程
// 用法：node tools/repro_daily.mjs
//
// 为什么需要它：/daily 与 /daily/question 的渲染完全由 JS 完成，
// 静态 id 交叉核对只能证明「元素存在」，证明不了「渲染结果正确」。
// 这里用 DOM 桩把两个脚本真跑一遍，覆盖：
//   1. /daily 的今日题目、题库列表、历史题目是否都渲染出来；
//   2. 右栏「我的打卡」天数与 7 天格子、「题库分布」分类行与占比条；
//   3. 题库列表的「编辑」是否指向 /daily/question?id=N（而不是内联回填）；
//   4. 出题页的新增模式不该去拉单题详情；
//   5. 出题页带 ?id=N 时字段是否被正确回填；
//   6. 历史题目与题库条目是否都链到详情页 /daily/q/<id>（草稿除外）；
//   7. 详情页题干/答案/相关题渲染，以及 ?d= 是否优先于接口给的 date；
//   8. 详情页右栏「同分类相关题」的显隐：有相关题才切双列，没有/加载失败则回居中单列；
//   9. /daily 访客视角：题库是纯陈列（题干可点、整条无按钮），且请求不带 with_drafts；
//  10. daily.html 的打卡卡带 data-auth-role="admin"（未登录不显示打卡记录）。
import fs from 'fs';
import path from 'path';
import vm from 'vm';

const ROOT = process.cwd();
const read = (p) => fs.readFileSync(path.join(ROOT, p), 'utf8');

const problems = [];
const ok = (cond, msg) => { if (!cond) problems.push(msg); };

// ---------- 最小 DOM 桩 ----------
function makeEl(tag = 'div') {
    return {
        tagName: tag,
        innerHTML: '',
        textContent: '',
        value: '',
        hidden: false,
        disabled: false,
        dataset: {},
        children: [],
        _attrs: {},
        // 不能是空实现：详情页靠 layout.classList.toggle('has-related') 在
        // 「双列（有相关题）/ 居中单列（无相关题）」之间切换，断言要读得到。
        classList: (() => {
            const set = new Set();
            return {
                add: (c) => set.add(c),
                remove: (c) => set.delete(c),
                toggle: (c, force) => {
                    const on = force === undefined ? !set.has(c) : !!force;
                    if (on) set.add(c); else set.delete(c);
                    return on;
                },
                contains: (c) => set.has(c),
            };
        })(),
        addEventListener() {},
        removeEventListener() {},
        setAttribute(k, v) { this._attrs[k] = String(v); },
        getAttribute(k) { return this._attrs[k]; },
        removeAttribute(k) { delete this._attrs[k]; },
        querySelector() { return makeEl(); },
        querySelectorAll() { return []; },
        closest() { return null; },
        appendChild(c) { this.children.push(c); return c; },
        replaceChildren() {},
        remove() {},
        focus() {},
        reset() {},
        scrollIntoView() {},
        insertAdjacentHTML(pos, html) { this.innerHTML += html; },
    };
}

const elements = new Map();
const getEl = (id) => {
    if (!elements.has(id)) elements.set(id, makeEl());
    return elements.get(id);
};

let responses = {};
let fetchLog = [];

// 连续让出微任务队列，等所有「即发即忘」的异步渲染落地
const flush = async () => { for (let i = 0; i < 50; i++) await Promise.resolve(); };

function makeSandbox(search = '', pathname = '/') {
    const document = {
        getElementById: getEl,
        createElement: (t) => makeEl(t),
        querySelector: () => null,
        querySelectorAll: () => [],
        addEventListener() {},
        body: makeEl('body'),
    };
    // window.location 与 location 必须是同一个对象：页面代码读的是 window.location.search / pathname
    const loc = { search, href: '', pathname };
    const sandbox = {
        document,
        window: { location: loc },
        location: loc,
        console,
        setTimeout: () => 0,
        clearTimeout: () => {},
        Promise,
        URLSearchParams,
        // markdown.js 的渲染入口。真实页面由 markdown.js 提供，这里只要一个能证明
        // 「答案确实被交给渲染器」的桩，避免为了它把 marked/purify/highlight 全搬进沙箱。
        renderMarkdownInto: (el, text) => { if (el) el.innerHTML = `[md]${text}`; },
        fetch: async (url) => {
            fetchLog.push(url);
            const key = Object.keys(responses).find((k) => url.includes(k));
            return { ok: true, status: 200, json: async () => (key ? responses[key] : {}) };
        },
    };
    sandbox.globalThis = sandbox;
    return sandbox;
}

const load = (sandbox, scripts) =>
    vm.runInNewContext(scripts.map(read).join('\n'), sandbox);

// ---------- 用例 1：/daily 页 ----------
responses = {
    '/api/auth': { authed: true, is_main: true },
    '/api/daily/history': {
        questions: [{ id: 42, date: '2026-10-09', question: '昨天的题', category: 'C++', difficulty: 2 }],
    },
    '/api/daily': { available: true, id: 1, date: '2026-10-10', question: '今日的题', category: 'Linux', difficulty: 2, streak: 3 },
    '/api/questions': {
        questions: [
            { id: 7, category: 'C++', difficulty: 3, status: 1, question: '测试题干' },
            { id: 8, category: 'C++', difficulty: 1, status: 0, question: '草稿题干' },
        ],
        categories: [{ name: 'C++', count: 100 }, { name: 'Linux', count: 90 }],
        total: 2, hasMore: false,
    },
};

const sb1 = makeSandbox();
load(sb1, ['static/js/daily-common.js', 'static/js/daily.js']);
await sb1.initDailyPage();
await flush();

const bankHtml = getEl('questionList').innerHTML;
const historyHtml = getEl('historyList').innerHTML;
const todayHtml = getEl('todayCard').innerHTML;

ok(bankHtml.includes('href="/daily/question?id=7"'), '题库列表的「编辑」没有指向 /daily/question?id=7');
ok(!bankHtml.includes('q-edit'), '题库列表仍残留 q-edit 按钮（应改为链接）');
ok(bankHtml.includes('q-del'), '题库列表丢失了「删除」按钮');
ok(bankHtml.includes('href="/daily/q/7"'), '题库条目的题干没有指向详情页 /daily/q/7');
// 题库条目只陈列题干：题干即详情入口，不再重复放「详情」，也不就地展开「查看答案」
ok(!bankHtml.includes('>详情<'), '题库条目仍残留「详情」按钮（题干即入口，重复了）');
ok(!bankHtml.includes('q-reveal'), '题库条目仍残留「查看答案」按钮（答案统一去详情页看）');
ok(!bankHtml.includes('daily-item-answer'), '题库条目仍残留就地展开答案的容器');
ok(!bankHtml.includes('/daily/q/8'), '草稿题不应有详情页链接（公开接口只放行已发布题目）');
ok(historyHtml.includes('href="/daily/q/42?d=2026-10-09"'), '历史题目没有链到详情页（应为 /daily/q/42?d=2026-10-09）');
ok(historyHtml.includes('昨天的题'), '历史题目没有渲染');
ok(historyHtml.includes('daily-history-date'), '历史题目缺少日期节点');
ok(todayHtml.includes('今日的题'), '今日题目卡片没有渲染');
ok(todayHtml.includes('streakBadge'), '今日题目卡片缺少连答徽标节点');

// 右栏「我的打卡」：streak=3 且 answered 未给（视为未答）→ 应从昨天起往前 3 天点亮
// 注意正则要卡住引号/空格：class="streak-day-label" 也会被 class="streak-day 匹配到
const weekHtml = getEl('streakWeek').innerHTML;
ok(getEl('streakNum').textContent === '3', '打卡卡连答天数没有渲染（期望 3）');
ok((weekHtml.match(/class="streak-day[" ]/g) || []).length === 7, '打卡卡应渲染 7 天格子');
ok((weekHtml.match(/class="streak-day on/g) || []).length === 3, '打卡卡点亮天数应等于 streak（期望 3）');
ok(weekHtml.includes('today'), '打卡卡没有标出今天');
ok(getEl('streakStatus').textContent === '今日尚未作答', '打卡卡今日状态文案不对');

// 右栏「题库分布」：行数 = 分类数，含题量与占比条
const distHtml = getEl('catDist').innerHTML;
ok((distHtml.match(/cat-dist-row/g) || []).length === 2, '题库分布行数应等于分类数');
ok(distHtml.includes('C++') && distHtml.includes('Linux'), '题库分布没有渲染分类名');
ok(distHtml.includes('>100<'), '题库分布没有渲染题量');
ok(distHtml.includes('cat-dist-bar'), '题库分布缺少占比条');
ok(!distHtml.includes('active'), '未选中分类时不应有高亮行');

console.log('/daily        : 题库', bankHtml.includes('/daily/question?id=7') ? '✓' : '✗',
    '| 历史', historyHtml.includes('昨天的题') ? '✓' : '✗',
    '| 今日题', todayHtml.includes('今日的题') ? '✓' : '✗',
    '| 打卡', getEl('streakNum').textContent + ' 天/' +
        (weekHtml.match(/class="streak-day on/g) || []).length + ' 格 ✓',
    '| 分布', (distHtml.match(/cat-dist-row/g) || []).length + ' 类 ✓');

// ---------- 用例 2：出题页（新增模式） ----------
elements.clear();
fetchLog.length = 0;
responses = { '/api/questions': { questions: [], categories: [{ name: 'C++' }], total: 0, hasMore: false } };

const sb2 = makeSandbox('');
load(sb2, ['static/js/daily-common.js', 'static/js/daily-question.js']);
await sb2.initQuestionPage();
await flush();

ok(getEl('qSaveBtn').textContent !== '保存修改', '新增模式按钮文案不应是「保存修改」');
ok(!fetchLog.some((u) => /\/api\/questions\/\d+/.test(u)), '新增模式不应去拉取单题详情');
ok(getEl('categoryOptions').innerHTML.includes('C++'), '分类联想没有填进 datalist');
ok(getEl('qFormHint').textContent === '', '新增模式不应有「正在编辑」提示');
console.log('/daily/question: 新增模式 ✓  请求', fetchLog.length, '次（未拉单题）',
    '| datalist', getEl('categoryOptions').innerHTML.includes('C++') ? '✓' : '✗');

// ---------- 用例 3：出题页（编辑模式 ?id=5） ----------
elements.clear();
fetchLog.length = 0;
responses = {
    '/api/questions/5': {
        success: true, category: 'MySQL', tags: '索引,优化', difficulty: 3,
        status: 0, question: '什么是回表？', answer: '**回表**指 ...',
    },
    '/api/questions': { questions: [], categories: [{ name: 'MySQL' }], total: 0, hasMore: false },
};

const sb3 = makeSandbox('?id=5');
load(sb3, ['static/js/daily-common.js', 'static/js/daily-question.js']);
await sb3.initQuestionPage();
await flush();

ok(getEl('qCategory').value === 'MySQL', '编辑模式没有回填分类');
ok(getEl('qTags').value === '索引,优化', '编辑模式没有回填标签');
ok(getEl('qDifficulty').value === '3', '编辑模式没有回填难度');
ok(getEl('qStatus').value === '0', '编辑模式没有回填状态（草稿应为 0）');
ok(getEl('qQuestion').value === '什么是回表？', '编辑模式没有回填题干');
ok(getEl('qAnswer').value.includes('回表'), '编辑模式没有回填答案');
ok(getEl('qSaveBtn').textContent === '保存修改', '编辑模式按钮文案应为「保存修改」');
ok(String(getEl('questionPageTitle').textContent).includes('#5'), '编辑模式标题应带题目编号');
console.log('/daily/question: 编辑模式 ✓  分类', getEl('qCategory').value,
    '| 状态', getEl('qStatus').value, '| 按钮', getEl('qSaveBtn').textContent);

// ---------- 用例 4：出题页（id 非法） ----------
elements.clear();
const sb4 = makeSandbox('?id=abc');
load(sb4, ['static/js/daily-common.js', 'static/js/daily-question.js']);
await sb4.initQuestionPage();
await flush();
ok(getEl('qSaveBtn').textContent !== '保存修改', 'id 非法时不应进入编辑模式');
console.log('/daily/question: 坏 id 未进入编辑模式 ✓');

// ---------- 用例 5：题目详情页（/daily/q/12?d=2026-10-08） ----------
elements.clear();
fetchLog.length = 0;
responses = {
    '/api/daily/question': {
        success: true, id: 12, category: 'MySQL', tags: '索引,B+树', difficulty: 2,
        question: '什么是回表？', answer: '**回表**指 ……',
        // 接口给的是「最近一次排期」，URL 里带的是「这次从哪天的历史点进来的」——后者应当优先
        date: '2026-10-06',
        siblings: [{ id: 13, question: '相关题一', difficulty: 3 }],
    },
};

const sb5 = makeSandbox('?d=2026-10-08', '/daily/q/12');
load(sb5, ['static/js/daily-common.js', 'static/js/daily-q.js']);
await sb5.initDetailPage();
await flush();

const detailHtml = getEl('qDetail').innerHTML;
ok(detailHtml.includes('什么是回表？'), '详情页没有渲染题干');
ok(detailHtml.includes('2026-10-08'), '详情页日期应优先用 URL 的 ?d=（期望 2026-10-08）');
ok(!detailHtml.includes('2026-10-06'), '详情页日期不该退回接口的 date（URL 已给出更精确的那次）');
ok(detailHtml.includes('每日一题'), '详情页带来源日期时应显示「每日一题」徽章');
ok(getEl('qAnswerBody').innerHTML.includes('[md]'), '答案没有被交给 Markdown 渲染器');
ok(getEl('qEditLink').href === '/daily/question?id=12', '「编辑此题」没有带上课目 id');
ok((getEl('qRelatedList').innerHTML.match(/qdetail-related-item/g) || []).length === 1, '相关题没有渲染');
ok(getEl('qRelated').hidden === false, '有相关题时不该隐藏该区块');
ok(getEl('qDetailLayout').classList.contains('has-related'), '有相关题时主栏应切到双列（.has-related）');
console.log('/daily/q/12  : 题干 ✓  答案→markdown ✓  | 日期', detailHtml.includes('2026-10-08') ? '2026-10-08（来自 URL）✓' : '✗',
    '| 相关题', (getEl('qRelatedList').innerHTML.match(/qdetail-related-item/g) || []).length + ' 条 → 右栏 ✓');

// ---------- 用例 6：详情页（有题，但同分类一道相关题都没有） ----------
// 这是撤掉右栏的另一条分支：右栏整栏收起，同时撤掉 .has-related 让主栏回居中单列，
// 否则右侧会留一张空卡片、主栏也被一条无内容的列挤窄。
elements.clear();
responses = {
    '/api/daily/question': {
        success: true, id: 20, category: 'Redis', tags: '', difficulty: 1,
        question: '没有同分类相关题的题', answer: '略', date: '', siblings: [],
    },
};
const sb6 = makeSandbox('', '/daily/q/20');
load(sb6, ['static/js/daily-common.js', 'static/js/daily-q.js']);
await sb6.initDetailPage();
await flush();
ok(getEl('qRelated').hidden === true, '没有相关题时右栏应整栏收起');
ok(!getEl('qDetailLayout').classList.contains('has-related'), '没有相关题时应撤掉双列，主栏回到居中单列');
ok(getEl('qDetail').innerHTML.includes('题库题目'), '没有排期日期时应显示「题库题目」徽章');
console.log('/daily/q/20  : 无相关题 → 右栏收起、主栏居中单列 ✓');

// ---------- 用例 7：详情页（题目不存在） ----------
elements.clear();
responses = { '/api/daily/question': { success: false, message: '题目不存在或尚未发布' } };
const sb7 = makeSandbox('', '/daily/q/999');
load(sb7, ['static/js/daily-common.js', 'static/js/daily-q.js']);
await sb7.initDetailPage();
await flush();
ok(getEl('qDetail').innerHTML.includes('题目不存在或尚未发布'), '题目不存在时应显示接口给的提示');
ok(getEl('qRelated').hidden === true, '加载失败时应隐藏相关题区块');
ok(!getEl('qDetailLayout').classList.contains('has-related'), '加载失败时应撤掉双列，主栏回到居中单列');
console.log('/daily/q/999 : 失败态 ✓  相关题区块已隐藏 ✓  单列居中 ✓');

// ---------- 用例 8：/daily（访客视角，与用例 1 的站长视角对照） ----------
// 题库对访客应当是「纯陈列」：题干可点进详情页，整条没有任何按钮
// （没有「详情」「查看答案」，也没有站长的「编辑」「删除」）。
elements.clear();
fetchLog.length = 0;
responses = {
    '/api/auth': { authed: false, is_main: false },
    '/api/daily/history': { questions: [] },
    '/api/daily': { available: true, id: 1, date: '2026-10-10', question: '今日的题', category: 'Linux', difficulty: 2, streak: 0 },
    '/api/questions': {
        questions: [{ id: 7, category: 'C++', difficulty: 3, status: 1, question: '测试题干' }],
        categories: [{ name: 'C++', count: 100 }],
        total: 1, hasMore: false,
    },
};

const sb8 = makeSandbox();
load(sb8, ['static/js/daily-common.js', 'static/js/daily.js']);
await sb8.initDailyPage();
await flush();

const guestBank = getEl('questionList').innerHTML;
ok(fetchLog.every((u) => !u.includes('with_drafts')), '访客请求不该带 with_drafts（草稿不外泄）');
ok(guestBank.includes('href="/daily/q/7"'), '访客侧：题库题干仍应是详情页入口');
ok(!guestBank.includes('daily-item-actions'), '访客侧：题库条目不该有任何操作按钮');
ok(!guestBank.includes('q-del'), '访客侧：不该出现站长的「删除」');
ok(!guestBank.includes('>详情<') && !guestBank.includes('q-reveal'), '访客侧：题库不该有「详情」「查看答案」');
console.log('/daily (访客) : 题库纯陈列（题干可点，整条无按钮）✓');

// ---------- 静态结构断言：打卡卡只对登录用户显示 ----------
// 它靠 HTML 属性 + auth.js 遍历 DOM 生效，这层在桩里跑不到（桩没有 querySelectorAll），
// 所以只能查源码。删掉这个属性 = 未登录访客又会看到「别人的」打卡记录。
const dailyHtmlSrc = read('static/daily.html');
ok(/class="daily-side-card"[^>]*data-auth-role="admin"/.test(dailyHtmlSrc),
    '「我的打卡」卡缺少 data-auth-role="admin"（未登录访客会看到打卡记录）');
ok(/class="daily-side-card"[^>]*data-auth-role="admin"[^>]*hidden/.test(dailyHtmlSrc),
    '「我的打卡」卡应默认 hidden（否则登录态返回前会闪一下）');
console.log('daily.html   : 打卡卡 data-auth-role="admin" + 默认 hidden ✓');

console.log('');
if (problems.length) {
    console.log('失败 ' + problems.length + ' 项：');
    problems.forEach((p) => console.log('  ✗', p));
    process.exit(1);
}
console.log('全部通过 ✓');
