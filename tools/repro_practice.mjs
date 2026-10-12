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

// 按 <div> 配平提取某个 div 整块（openTag 不含结尾 '>'）
function extractDivBlock(src, openTag) {
    const start = src.indexOf(openTag);
    if (start < 0) return '';
    let i = src.indexOf('>', start + openTag.length) + 1;
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
assert(js.includes('/api/practice/progress'), '启动时回读服务端进度');
assert(js.includes('loadProgress'), '合并服务端进度（与本地 doneSet 求并）');
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

// 3c. 描述卡：标签栏「题目描述 | 题解 | 测试结果」三标签页共用一栏
console.log('== 描述卡（题目描述 / 题解 / 测试结果 三标签页）==');
const css = readFileSync(resolve(staticDir, 'css/style.css'), 'utf8');
assert(html.includes('class="practice-tabs"') && html.includes('role="tablist"'), '描述卡含标签栏 practice-tabs');
assert(/practice-tab is-active"[^>]*id="tabDesc"/.test(html), '默认激活「题目描述」标签');
assert(/id="tabDesc"[\s\S]{0,140}题目描述<\/button>/.test(html), '标签一文案为「题目描述」');
assert(/id="tabSolution"[\s\S]{0,140}题解<\/button>/.test(html), '标签二文案为「题解」');
assert(/id="tabResult"[\s\S]{0,180}测试结果/.test(html), '标签三文案为「测试结果」');
assert(!/practice-pane-title">题目/.test(html), '不再残留旧的「题目」标题');
assert(!html.includes('practice-result-title'), '结果卡不再自带标题（改由标签承载）');
assert(html.includes('id="promptHost"'), '含题目描述宿主 promptHost');
assert(html.includes('id="resultCard"'), '含测试结果卡 resultCard');
assert(html.includes('id="resultPane"'), '含测试结果面板 resultPane');

// 三个面板：descPane 默认可见，solutionPane / resultPane 默认 hidden；依次排列
const descPaneIdx = html.indexOf('id="descPane"');
const solPaneIdx = html.indexOf('id="solutionPane"');
const resultPaneIdx = html.indexOf('id="resultPane"');
const resultCardIdx = html.indexOf('id="resultCard"');
assert(descPaneIdx > 0 && solPaneIdx > descPaneIdx && resultPaneIdx > solPaneIdx,
    '面板顺序：descPane → solutionPane → resultPane');
assert(!/id="descPane"[\s\S]{0,90}hidden/.test(html), 'descPane 默认可见（无 hidden）');
assert(/id="solutionPane"[\s\S]{0,140}hidden/.test(html), 'solutionPane 默认 hidden');
assert(/id="resultPane"[\s\S]{0,170}hidden/.test(html), 'resultPane 默认 hidden');
assert(resultCardIdx > resultPaneIdx, 'resultCard 位于 resultPane 之后（不再是独立底栏）');
{
    const paneBlock = extractDivBlock(html, '<div class="practice-desc-scroll" id="resultPane"');
    assert(paneBlock.includes('id="resultCard"'), 'resultCard 在 resultPane 内');
    assert(paneBlock.includes('id="resultBody"'), 'resultPane 内含 resultBody');
}
{
    const descBlock = extractDivBlock(html, '<div class="practice-desc-scroll" id="descPane"');
    assert(descBlock.includes('id="promptHost"'), '描述面板包含 promptHost');
    assert(!descBlock.includes('id="resultCard"'), 'resultCard 不在描述面板内');
}

assert(js.includes('switchTab'), 'practice.js 实现标签切换 switchTab');
assert(js.includes("switchTab('result')"), 'JS 有切到「测试结果」标签');
assert(js.includes('bindTabs') && js.includes("switchTab('desc')"), '绑定标签事件并在每次渲染时复位到「题目描述」');
assert(js.includes('tabResultEl') && js.includes('resultPaneEl'), 'JS 引用第三个标签与结果面板');
assert(js.includes('revealResult'), 'JS 有提交后自动切到「测试结果」的 revealResult');
assert(js.includes('restoreLastResult'), 'JS 打开题目时恢复本题上次结果 restoreLastResult');
assert(js.includes('updateResultTabDot'), 'JS 维护「测试结果」标签状态点');
assert(js.includes('practice-result-empty'), 'JS 有结果空态');
assert(js.includes('renderSolution'), 'practice.js 渲染题解');
assert(js.includes('practice-solution-body'), '题解填入 practice-solution-body');
assert(!/<details/.test(js) && !js.includes('practice-solution"'), '题解不再用 <details> 折叠（已改标签页）');
assert(js.includes('currentExercise.solution'), '读取详情里的 solution 字段');
assert(js.includes('setPromptHtml'), '只重绘描述面板（保留标签栏与结果面板）');
assert(/practice-pane-title">题目</.test(js) === false, '不再在 JS 里输出旧的「题目」标题');
assert(css.includes('.practice-tab') && css.includes('.practice-tabs'), 'style.css 含标签栏样式');
assert(css.includes('.practice-tab.is-active'), 'style.css 含激活标签样式');
assert(css.includes('#resultPane'), 'style.css 含结果面板样式');
assert(css.includes('.practice-tab-dot'), 'style.css 含标签状态点样式');
assert(css.includes('.practice-result-empty'), 'style.css 含结果空态样式');

// 3d. 代码编辑器：IDE 观感（行号槽 + 语法高亮叠加层 + 状态栏）
console.log('== 代码编辑器（行号 / 语法高亮 / 状态栏）==');
assert(html.includes('class="practice-code"'), '含编辑器外壳 practice-code');
assert(html.includes('id="codeGutter"'), '含行号槽 codeGutter');
assert(html.includes('id="codeHighlight"'), '含语法高亮叠加层 codeHighlight');
assert(html.includes('class="practice-code-hl"'), '叠加层用 practice-code-hl');
assert(html.includes('class="practice-code-input"'), '输入框用 practice-code-input');
assert(html.includes('id="codeEditor"'), '保留 codeEditor（提交逻辑依赖）');
assert(html.includes('id="codeStatusPos"'), '含状态栏光标位置 codeStatusPos');
assert(!/class="practice-editor"/.test(html), '旧的 .practice-editor 纯 textarea 已移除');

assert(js.includes('hljs.highlight') && js.includes("language: 'cpp'"), 'JS 用 hljs 做 C++ 语法高亮');
assert(js.includes('refreshCodeEditor'), 'JS 有编辑器重绘 refreshCodeEditor');
assert(js.includes('renderCodeNumbers'), 'JS 渲染行号');
assert(js.includes('syncCodeScroll'), 'JS 同步行号/高亮层滚动');
assert(js.includes('handleCodeKeydown'), 'JS 接管编辑器快捷键');
assert(js.includes('applyIndent') && js.includes('autoIndentOnEnter'), 'Tab 缩进 + Enter 自动缩进');
assert(js.includes('renderTier(currentTier)') && js.includes("INDENT = '    '"), '切档位后重绘、缩进为 4 空格');

assert(css.includes('.practice-code-gutter'), 'style.css 含行号槽样式');
assert(css.includes('.practice-code-hl .hljs-keyword'), 'style.css 含编辑器 token 配色');
assert(css.includes('.practice-code-body:focus-within'), 'style.css 含编辑器聚焦态');

// 4. seed 数据（由 tools/gen_practice_seed.py 生成）
console.log('== seed_practice.sql ==');
const seed = readFileSync(resolve(root, 'tools/seed_practice.sql'), 'utf8');
const chapterInserts = (seed.match(/INSERT INTO practice_chapters/g) || []).length;
assert(chapterInserts === 14, '14 个章节');
const exerciseInserts = (seed.match(/INSERT INTO practice_exercises/g) || []).length;
assert(exerciseInserts === 154, '应为 154 道题（当前 ' + exerciseInserts + '）');
assert(!/INSERT IGNORE/.test(seed), 'seed 不应再有 INSERT IGNORE（已改 upsert）');
assert(/solution\s+TEXT/.test(seed), 'seed 建表含 solution（题解）列');
assert(seed.includes('ADD COLUMN solution'), 'seed 含 solution 幂等补列迁移（老库自愈，防 1054）');
assert(seed.includes('PREPARE stmt_mig FROM @ddl'), '补列迁移用 information_schema + PREPARE 动态执行');
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
assert(routes.includes('"/api/practice/progress"'), '注册 /api/practice/progress');
assert(routes.includes('getPracticeProgress') && routes.includes('getAnonToken(req)'),
    'progress 路由按匿名 Cookie 查库回读进度');
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
assert(dbh.includes('getPracticeProgress'), 'database.h 声明 getPracticeProgress');
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
assert(dbc.includes('getPracticeProgress'), 'database.cpp 实现 getPracticeProgress');
assert(/FROM practice_progress[\s\S]{0,120}passed=1/.test(dbc), '进度回读查 practice_progress 且只取 passed=1');

console.log(failed === 0 ? '\n\u5168\u90e8\u901a\u8fc7 \u2713' : '\n' + failed + ' \u9879\u5931\u8d25 \u2717');
process.exit(failed === 0 ? 0 : 1);
