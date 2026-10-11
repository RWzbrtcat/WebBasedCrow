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
assert(js.includes('/api/practice/submit'), '提交走真实判定');
assert(js.includes('renderExerciseList'), '有题目列表中间态');
assert(js.includes('renderMarkdownInto'), '题干走 markdown 渲染');

// 4. seed 数据（由 tools/gen_practice_seed.py 生成）
console.log('== seed_practice.sql ==');
const seed = readFileSync(resolve(root, 'tools/seed_practice.sql'), 'utf8');
const chapterInserts = (seed.match(/INSERT IGNORE INTO practice_chapters/g) || []).length;
assert(chapterInserts === 14, '14 个章节');
const exerciseInserts = (seed.match(/INSERT IGNORE INTO practice_exercises/g) || []).length;
assert(exerciseInserts >= 2, '至少 2 道题（当前 ' + exerciseInserts + '）');
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
assert(routes.includes('getPracticeTestDriver'), 'submit 查库取测试驱动');
assert(routes.includes('recordPracticeAttempt'), 'submit 记录进度');
assert(routes.includes('judgeSubmission'), '调用 judgeSubmission');

// 7. 数据库层有练习方法
console.log('== 数据库层 ==');
const dbh = readFileSync(resolve(root, 'src/database.h'), 'utf8');
const dbc = readFileSync(resolve(root, 'src/database.cpp'), 'utf8');
assert(dbh.includes('getPracticeChapters'), 'database.h 声明 getPracticeChapters');
assert(dbh.includes('getPracticeTestDriver'), 'database.h 声明 getPracticeTestDriver');
assert(dbc.includes('practice_chapters'), 'database.cpp initTable 建 practice_chapters');
assert(dbc.includes('practice_exercises'), 'database.cpp initTable 建 practice_exercises');
assert(dbc.includes('practice_progress'), 'database.cpp initTable 建 practice_progress');

console.log(failed === 0 ? '\n\u5168\u90e8\u901a\u8fc7 \u2713' : '\n' + failed + ' \u9879\u5931\u8d25 \u2717');
process.exit(failed === 0 ? 0 : 1);
