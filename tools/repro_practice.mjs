// 练习闯关的静态回归：资源引用 + 前端接口对接 + seed 数据 + 导航入口 + 后端路由
// 用法：node tools/repro_practice.mjs
import { readFileSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const staticDir = resolve(root, 'static');

let failed = 0;
function assert(cond, msg) {
    if (cond) {
        console.log('  \u2713 ' + msg);
    } else {
        console.error('  \u2717 ' + msg);
        failed++;
    }
}

// 1. practice.html 引用的资源都存在（只看 <script src> 和 <link href>，排除导航 <a href>）
console.log('== practice.html 资源引用 ==');
const html = readFileSync(resolve(staticDir, 'practice.html'), 'utf8');
const scriptRefs = [...html.matchAll(/<script src="(\/[^"]+)"/g)].map((m) => m[1]);
const linkRefs = [...html.matchAll(/<link[^>]*href="(\/[^"]+)"/g)].map((m) => m[1]);
const refs = [...scriptRefs, ...linkRefs];
for (const ref of refs) {
    const p = resolve(staticDir, ref.replace(/^\//, ''));
    assert(existsSync(p), ref + ' 存在');
}

// 2. practice.html 引入 markdown 渲染栈（题干是 markdown）
console.log('== practice.html markdown 栈 ==');
assert(html.includes('/js/marked.min.js'), '引入 marked.min.js');
assert(html.includes('/js/purify.min.js'), '引入 purify.min.js');
assert(html.includes('/js/markdown.js'), '引入 markdown.js');

// 3. practice.js 走接口拉数据（不再内置 mock）
console.log('== practice.js 接口对接 ==');
const js = readFileSync(resolve(staticDir, 'js/practice.js'), 'utf8');
assert(js.includes('/api/practice/chapters'), '拉取章节列表');
assert(js.includes('/api/practice/exercises?chapter='), '按章节拉题目列表');
assert(js.includes('/api/practice/exercise/'), '拉单题详情');
assert(js.includes('/api/practice/submit'), '写代码题提交走真实判定');
assert(js.includes('/api/practice/answer'), '客观题提交走 /api/practice/answer');
assert(js.includes('renderExerciseList'), '有题目列表（左栏两级树）');
assert(js.includes('renderMarkdownInto'), '题干走 markdown 渲染');
assert(js.includes('renderChoice'), '选择题渲染分支');
assert(js.includes('renderBlank'), '填空题渲染分支');
assert(js.includes('submitChoice'), '选择题提交');
assert(js.includes('submitBlank'), '填空题提交');
assert(js.includes('setWorkLayout'), '工作台双列/单列切换');
assert(js.includes('markDone'), '本地记录已通过题目');
assert(js.includes('localStorage'), '完成状态存 localStorage');
assert(js.includes('practice-ex-item'), '左栏渲染题目项');

// 3b. practice.html 工作台布局骨架
console.log('== practice.html 工作台布局 ==');
assert(html.includes('practice-work-body'), '含并排主体容器 workBody');
assert(html.includes('id="workBody"'), 'workBody 有 id');
assert(html.includes('practice-work-head'), '含题目头容器');
assert(html.includes('id="workHead"'), 'workHead 有 id');
assert(html.includes('practice-side-head'), '左栏含标题条');
assert(html.includes('/js/daily-common.js'), '先加载 daily-common.js（共用工具）');
assert(/id="workBody"[\s\S]{0,40}single/.test(html) || html.includes('practice-work-body single'),
    '初始为单列（未选题）');
{
    const jsIdx = html.indexOf('/js/practice.js');
    const commonIdx = html.indexOf('/js/daily-common.js');
    assert(commonIdx > 0 && jsIdx > 0 && commonIdx < jsIdx, 'daily-common 在 practice.js 之前加载');
}

// 3c. 描述卡三段式：题目描述 + 题解 + 测试结果
console.log('== 描述卡（题目描述 / 题解 / 测试结果）==');
assert(html.includes('practice-pane-title">题目描述<'), '题目卡标题为「题目描述」');
assert(!/practice-pane-title">题目</.test(html), '不再残留旧的「题目」标题');
assert(html.includes('id="promptHost"'), '含题目描述宿主 promptHost');
assert(html.includes('id="resultCard"'), '含测试结果卡 resultCard');
assert(html.includes('practice-result-title">测试结果<'), '结果卡标题文案为「测试结果」');
// resultCard 必须在 .practice-desc-scroll 之外（作为其兄弟节点，固定在描述卡底部）
// 用 <div> 配平提取描述区整块，再断言 resultCard 不在其中 —— 比单纯正则可靠
function extractDivBlock(src, openTag) {
    const start = src.indexOf(openTag);
    if (start < 0) return '';
    let i = start + openTag.length;   // openTag 已含结尾 '>'，紧接其后即内容起点
    let depth = 1;
    const re = /<\/?div\b[^>]*>/g;
    re.lastIndex = i;
    let m;
    while ((m = re.exec(src))) {
        depth += m[0].startsWith('</') ? -1 : 1;
        if (depth === 0) return src.slice(i, m.index);
    }
    return '';
}
const descBlock = extractDivBlock(html, '<div class="practice-desc-scroll">');
assert(descBlock.includes('id="promptHost"'), '描述滚动区包含 promptHost');
assert(!descBlock.includes('id="resultCard"'), 'resultCard 不在描述滚动区内（固定在描述卡底部）');

assert(js.includes('renderSolution'), 'practice.js 渲染题解');
assert(js.includes('practice-solution'), '题解使用折叠容器 practice-solution');
assert(js.includes('currentExercise.solution'), '读取详情里的 solution 字段');
assert(js.includes('setPromptHtml'), '只重绘描述区（保留底部测试结果卡）');
assert(/practice-pane-title">题目</.test(js) === false, '不再在 JS 里输出旧的「题目」标题');

// 4. seed 数据（由 tools/gen_practice_seed.py 生成）
console.log('== seed_practice.sql ==');
const seed = readFileSync(resolve(root, 'tools/seed_practice.sql'), 'utf8');
const chapterInserts = (seed.match(/INSERT INTO practice_chapters/g) || []).length;
assert(chapterInserts === 14, '14 个章节');
const exerciseInserts = (seed.match(/INSERT INTO practice_exercises/g) || []).length;
assert(exerciseInserts === 154, '应为 154 道题（当前 ' + exerciseInserts + '）');
assert(!/INSERT IGNORE/.test(seed), 'seed 不应再有 INSERT IGNORE（已改 upsert）');
assert(/solution\s+TEXT/.test(seed), 'seed 建表含 solution（题解）列');
{
    const solUpserts = (seed.match(/solution=VALUES\(solution\)/g) || []).length;
    assert(solUpserts === 154, '154 题均带题解 upsert（当前 ' + solUpserts + '）');
}
assert(seed.includes('practice_progress'), '含进度表');
assert(!seed.includes('\r'), 'seed 无 CRLF');

// 5. 导航入口（11 个页面）
console.log('== 导航入口（11 页面） ==');
const htmlFiles = ['index', 'admin', 'editor', 'drafts', 'login', 'hidden', 'profile', 'post', 'daily', 'daily-q', 'daily-question'];
for (const f of htmlFiles) {
    const content = readFileSync(resolve(staticDir, f + '.html'), 'utf8');
    assert(content.includes('href="/practice"'), f + '.html 有练习闯关入口');
}

// 6. routes.cpp 有练习闯关全部路由
console.log('== 后端路由 ==');
const routes = readFileSync(resolve(root, 'src/routes.cpp'), 'utf8');
assert(routes.includes('"/practice"'), 'routes.cpp 注册了 /practice 页面路由');
assert(routes.includes('practice.html'), 'routes.cpp 指向 practice.html');
assert(routes.includes('"/api/practice/chapters"'), '注册 /api/practice/chapters');
assert(routes.includes('"/api/practice/exercises"'), '注册 /api/practice/exercises');
assert(routes.includes('"/api/practice/exercise/<int>"'), '注册 /api/practice/exercise/<int>');
assert(routes.includes('"/api/practice/submit"'), '注册 /api/practice/submit');
assert(routes.includes('"/api/practice/answer"'), '注册 /api/practice/answer');
assert(routes.includes('getPracticeTestDriver'), 'submit 查库取测试驱动');
assert(routes.includes('getPracticeAnswer'), 'answer 查库取客观题答案');
assert(routes.includes('recordPracticeAttempt'), 'submit 记录进度');
assert(routes.includes('judgeSubmission'), '调用 judgeSubmission');

// 7. 数据库层有练习方法
console.log('== 数据库层 ==');
const dbh = readFileSync(resolve(root, 'src/database.h'), 'utf8');
const dbc = readFileSync(resolve(root, 'src/database.cpp'), 'utf8');
assert(dbh.includes('getPracticeChapters'), 'database.h 声明 getPracticeChapters');
assert(dbh.includes('getPracticeTestDriver'), 'database.h 声明 getPracticeTestDriver');
assert(dbh.includes('getPracticeAnswer'), 'database.h 声明 getPracticeAnswer');
assert(dbc.includes('practice_chapters'), 'database.cpp initTable 建 practice_chapters');
assert(dbc.includes('practice_exercises'), 'database.cpp initTable 建 practice_exercises');
assert(dbc.includes('practice_progress'), 'database.cpp initTable 建 practice_progress');
assert(dbc.includes('options'), 'database.cpp practice_exercises 含 options 列');
assert(dbc.includes('answer'), 'database.cpp practice_exercises 含 answer 列');
assert(dbc.includes('solution'), 'database.cpp 含 solution（题解）列');
assert(dbc.includes('ADD COLUMN solution') || dbc.includes('columnExists("practice_exercises", "solution")'),
    'database.cpp 有旧表补 solution 列的迁移');
assert(/SELECT[\s\S]{0,200}solution\s*"/.test(dbc) || dbc.includes(', solution "'), 'getPracticeExercise 查询下发 solution');
assert(dbc.includes('result["solution"]'), '详情结果带 solution 字段');

console.log(failed === 0 ? '\n\u5168\u90e8\u901a\u8fc7 \u2713' : '\n' + failed + ' \u9879\u5931\u8d25 \u2717');
process.exit(failed === 0 ? 0 : 1);
