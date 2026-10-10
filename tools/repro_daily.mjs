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
//   5. 出题页带 ?id=N 时字段是否被正确回填。
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
        classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
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

function makeSandbox(search = '') {
    const document = {
        getElementById: getEl,
        createElement: (t) => makeEl(t),
        querySelector: () => null,
        querySelectorAll: () => [],
        addEventListener() {},
        body: makeEl('body'),
    };
    // window.location 与 location 必须是同一个对象：页面代码读的是 window.location.search
    const loc = { search, href: '', pathname: '/' };
    const sandbox = {
        document,
        window: { location: loc },
        location: loc,
        console,
        setTimeout: () => 0,
        clearTimeout: () => {},
        Promise,
        URLSearchParams,
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
    '/api/daily/history': { questions: [{ date: '2026-10-09', question: '昨天的题', category: 'C++' }] },
    '/api/daily': { available: true, id: 1, date: '2026-10-10', question: '今日的题', category: 'Linux', difficulty: 2, streak: 3 },
    '/api/questions': {
        questions: [{ id: 7, category: 'C++', difficulty: 3, status: 1, question: '测试题干' }],
        categories: [{ name: 'C++', count: 100 }, { name: 'Linux', count: 90 }],
        total: 1, hasMore: false,
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

console.log('');
if (problems.length) {
    console.log('失败 ' + problems.length + ' 项：');
    problems.forEach((p) => console.log('  ✗', p));
    process.exit(1);
}
console.log('全部通过 ✓');
