// 首页渲染回归验证：Node 模拟最小 DOM + 线上缓存数据，执行 list.js 全流程
// 用法：node tools/_repro_list.mjs [js路径]   默认验证 static/js/list.js
import fs from 'fs';

const jsPath = process.argv[2] || 'static/js/list.js';
const postsData = JSON.parse(fs.readFileSync('tools/fixture_posts.json', 'utf8'));
const topicsData = JSON.parse(fs.readFileSync('tools/fixture_topics.json', 'utf8'));
console.log('topics success:', topicsData.success, 'topics:', (topicsData.topics || []).map(t => t.name).join(','));
console.log('posts:', postsData.posts.length, 'theme 字段:', [...new Set(postsData.posts.map(p => JSON.stringify(p.theme)))].join(' | '));

const elements = {};
function makeEl(id) {
    return {
        id, innerHTML: '', textContent: '', hidden: false,
        dataset: {}, listeners: {},
        addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); },
        querySelector: () => null,
        querySelectorAll: () => [],
        appendChild: () => {},
        classList: { add() {}, remove() {}, contains: () => false },
        getBoundingClientRect: () => ({ width: 0, height: 0, left: 0, top: 0 }),
        remove() {},
        setAttribute() {},
        focus() {},
    };
}

globalThis.document = {
    body: { dataset: { mode: '' }, appendChild() {}, classList: { add() {}, remove() {} } },
    addEventListener(type, fn) { if (type === 'DOMContentLoaded') globalThis.__domReady = fn; },
    getElementById(id) { if (!elements[id]) elements[id] = makeEl(id); return elements[id]; },
    createElement() { return makeEl('_'); },
    querySelectorAll: () => [],
};
globalThis.window = {
    location: { href: '' },
    innerWidth: 1400, innerHeight: 900,
    addEventListener() {},
};
globalThis.fetch = async (url) => {
    console.log('[fetch]', url);
    const body = String(url).includes('/topics') ? topicsData
        : String(url).includes('/auth') ? { authed: false }
        : postsData;
    return { status: 200, ok: true, json: async () => body };
};
globalThis.confirm = () => true;

const code = fs.readFileSync(jsPath, 'utf8');
eval(code);

await new Promise(r => setTimeout(r, 30));
await globalThis.__domReady();

console.log('\n=== topicTabs.innerHTML（前 240 字）===');
console.log((elements.topicTabs?.innerHTML || '').slice(0, 240));
console.log('\n=== themeTabs.hidden =', elements.themeTabs?.hidden, '===');
console.log('\n=== postList.innerHTML（前 400 字）===');
console.log((elements.postList?.innerHTML || '').slice(0, 400));
console.log('\n=== pageTitle.textContent =', elements.pageTitle?.textContent, '===');
