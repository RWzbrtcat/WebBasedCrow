// 练习闯关页面的静态回归：资源引用完整性 + 前端数据结构完整性 + 导航入口
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

// 2. practice.js 数据结构
console.log('== practice.js 数据结构 ==');
const js = readFileSync(resolve(staticDir, 'js/practice.js'), 'utf8');

const chapterMatches = [...js.matchAll(/\{ id: (\d+), title: '([^']+)'/g)];
const chapterIds = chapterMatches.map((m) => Number(m[1]));
assert(chapterIds.length === 14, '共 ' + chapterIds.length + ' 章（应为 14）');
assert(chapterIds.join(',') === Array.from({ length: 14 }, (_, i) => i + 1).join(','), '章节 id 连续 1-14');

const semesterCount = (js.match(/name: '第.学期/g) || []).length;
assert(semesterCount === 3, '共 ' + semesterCount + ' 个学期（应为 3）');

assert(js.includes('easy:') && js.includes('medium:') && js.includes('hard:'), 'C1 题目含 easy/medium/hard 三档');
assert(js.includes('/api/practice/submit'), '提交走 /api/practice/submit 真实判定');
assert(js.includes('decltype(auto)'), '挑战档含 decltype(auto) 测试');
assert(js.includes('get_ref') && js.includes('get_value'), '示例题含 get_ref/get_value');
assert(js.includes('selectChapter(1)'), '初始加载 C1');

// 3. 导航入口（11 个页面）
console.log('== 导航入口（11 页面） ==');
const htmlFiles = ['index', 'admin', 'editor', 'drafts', 'login', 'hidden', 'profile', 'post', 'daily', 'daily-q', 'daily-question'];
for (const f of htmlFiles) {
    const content = readFileSync(resolve(staticDir, f + '.html'), 'utf8');
    assert(content.includes('href="/practice"'), f + '.html 有练习闯关入口');
}

// 4. routes.cpp 有 /practice 路由 + 判定接口
console.log('== 后端路由 ==');
const routes = readFileSync(resolve(root, 'src/routes.cpp'), 'utf8');
assert(routes.includes('"/practice"'), 'routes.cpp 注册了 /practice 路由');
assert(routes.includes('practice.html'), 'routes.cpp 指向 practice.html');
assert(routes.includes('"/api/practice/submit"'), 'routes.cpp 注册了 /api/practice/submit');
assert(routes.includes('judgeSubmission'), 'routes.cpp 调用了 judgeSubmission');

console.log(failed === 0 ? '\n\u5168\u90e8\u901a\u8fc7 \u2713' : '\n' + failed + ' \u9879\u5931\u8d25 \u2717');
process.exit(failed === 0 ? 0 : 1);
