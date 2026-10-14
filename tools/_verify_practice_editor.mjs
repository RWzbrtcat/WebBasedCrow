// ============================================================
// 练习闯关 · 代码编辑器「编辑规则」逻辑回归（Node，无需浏览器）
// 做法：读 static/js/practice.js 源码，在受控 DOM 桩里 eval 整个 IIFE，
//       并在末尾临时注入一个导出钩子，拿到真实函数做文本改写断言。
// 跑法：node tools/_verify_practice_editor.mjs
// 只做逻辑验证，不改动任何文件。
// ============================================================
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');

let failed = 0;
function assert(cond, msg) {
    if (cond) console.log('  \u2713 ' + msg);
    else { console.error('  \u2717 ' + msg); failed++; }
}
function eq(actual, expected, msg) {
    const ok = actual === expected;
    assert(ok, msg + (ok ? '' : `\n      期望: ${JSON.stringify(expected)}\n      实际: ${JSON.stringify(actual)}`));
}

// ---------- 受控 DOM 桩 ----------
function makeEl(id) {
    const classes = new Set();
    return {
        id,
        value: '',
        selectionStart: 0,
        selectionEnd: 0,
        scrollTop: 0,
        scrollLeft: 0,
        scrollHeight: 200,
        clientHeight: 200,
        hidden: false,
        disabled: false,
        innerHTML: '',
        textContent: '',
        style: {},
        classList: {
            add: (c) => classes.add(c),
            remove: (c) => classes.delete(c),
            contains: (c) => classes.has(c),
            toggle: (c, on) => { if (on === undefined) { classes.has(c) ? classes.delete(c) : classes.add(c); } else if (on) classes.add(c); else classes.delete(c); },
        },
        addEventListener() {},
        setAttribute() {},
        getAttribute() { return null; },
        querySelectorAll() { return []; },
        appendChild() {},
        get parentElement() { return null; },
        get firstChild() { return null; },
    };
}

const els = new Map();
const codeEditor = makeEl('codeEditor');
els.set('codeEditor', codeEditor);
const curLineEl = makeEl('codeCurrentLine');
els.set('codeCurrentLine', curLineEl);

global.window = global;
// 内存版 localStorage（真实读写），用于「代码草稿持久化」的真实行为测试
const storage = new Map();
global.localStorage = {
    getItem: (k) => (storage.has(k) ? storage.get(k) : null),
    setItem: (k, v) => { storage.set(k, String(v)); },
    removeItem: (k) => { storage.delete(k); },
};
global.location = { search: '', href: 'http://localhost/practice' };
global.getComputedStyle = () => ({ lineHeight: '20.8px', paddingTop: '12px', paddingBottom: '12px', fontSize: '13px' });
global.document = {
    getElementById: (id) => els.get(id) || null,
    addEventListener() {},
    querySelectorAll: () => [],
    createElement: (tag) => makeEl(tag),
};
global.requestAnimationFrame = (cb) => cb();

// ---------- 读取源码并注入导出钩子（仅在内存中改，不落盘） ----------
let src = readFileSync(resolve(root, 'static/js/practice.js'), 'utf8');
const exportHook = 'window.__pe = { autoIndentOnEnter, toggleLineComment, moveLines, smartHome, handleCodeKeydown, applyIndent, lineRange, caretPos, scrollCaretIntoView, updateCurrentLine, syncCodeScroll, setEditor: (v) => { codeEditorEl.value = v; }, draftKey, saveDraftNow, loadDrafts, persistDrafts, clearDraft, getDrafts: () => drafts, setDrafts: (o) => { drafts = o; }, setExercise: (ex, tier) => { currentExercise = ex; currentTier = tier; } };';
src = src.replace(/\}\)\(\);\s*$/, (m) => '    ' + exportHook + '\n' + m);
// eslint-disable-next-line no-eval
eval(src);
const pe = global.__pe;

function setValue(v, s, e) {
    codeEditor.value = v;
    codeEditor.selectionStart = s === undefined ? v.length : s;
    codeEditor.selectionEnd = e === undefined ? codeEditor.selectionStart : e;
}
function key(k, extra) {
    const ev = Object.assign({ key: k, ctrlKey: false, metaKey: false, altKey: false, shiftKey: false, preventDefault() { ev._pd = true; } }, extra || {});
    return ev;
}

console.log('== Enter 自动缩进 / 括号间展开 ==');
setValue('int main() {');
assert(pe.autoIndentOnEnter() === true, 'Enter 生效');
eq(codeEditor.value, 'int main() {\n    ', '行尾 { → 新行多缩进一级');
eq(codeEditor.selectionStart, codeEditor.value.length, '光标落在新行缩进之后');

setValue('if (x) {}', 8, 8);
pe.autoIndentOnEnter();
eq(codeEditor.value, 'if (x) {\n    \n}', '光标夹在 {} 之间 → 展开成三行');
eq(codeEditor.selectionStart, 13, '光标停在中间缩进行');

setValue('    int a;');
pe.autoIndentOnEnter();
eq(codeEditor.value, '    int a;\n    ', '普通 Enter 继承上一行缩进');

setValue('a\nb', 0, 1);
eq(pe.autoIndentOnEnter(), false, '有选区时 Enter 不自动缩进');

console.log('== 智能 Home ==');
setValue('    x', 5, 5);
assert(pe.smartHome() === true, 'Home 生效');
eq(codeEditor.selectionStart, 4, '第一次 Home → 首个非空白字符');
pe.smartHome();
eq(codeEditor.selectionStart, 0, '第二次 Home → 行首');

console.log('== Ctrl/⌘ + / 整行注释 ==');
setValue('int a;\nint b;', 0, 15);
pe.toggleLineComment();
eq(codeEditor.value, '// int a;\n// int b;', '未注释 → 逐行加 //');
pe.toggleLineComment();
eq(codeEditor.value, 'int a;\nint b;', '已注释 → 逐行去掉 //');
setValue('a;\n\nb;', 0, 6);
pe.toggleLineComment();
eq(codeEditor.value, '// a;\n\n// b;', '空行不参与注释');

console.log('== Alt+↑/↓ 移动行 / Shift+Alt+↑/↓ 复制行 ==');
setValue('A\nB\nC', 0, 1);
pe.moveLines(false, false);
eq(codeEditor.value, 'B\nA\nC', 'Alt+↓ 下行与前一行交换');
eq(codeEditor.selectionStart + '-' + codeEditor.selectionEnd, '2-3', '光标跟随被移动的行');

setValue('A\nB\nC', 2, 3);
pe.moveLines(true, false);
eq(codeEditor.value, 'B\nA\nC', 'Alt+↑ 上移当前行');
eq(codeEditor.selectionStart + '-' + codeEditor.selectionEnd, '0-1', '光标跟随');

setValue('A\nB', 0, 1);
pe.moveLines(false, true);
eq(codeEditor.value, 'A\nA\nB', 'Shift+Alt+↓ 向下复制行');

setValue('A\nB', 2, 3);
pe.moveLines(true, true);
eq(codeEditor.value, 'A\nB\nB', 'Shift+Alt+↑ 向上复制行');

setValue('A\nB', 0, 1);
pe.moveLines(true, false);
eq(codeEditor.value, 'A\nB', '首行上移 → 无变化（返回早退）');

console.log('== 自动配对 / 跳过右半边（keydown） ==');
setValue('', 0, 0);
pe.handleCodeKeydown(key('('));
eq(codeEditor.value, '()', '输入 ( 自动补 )');
eq(codeEditor.selectionStart, 1, '光标停在括号中间');

setValue('()', 1, 1);
const evSkip = key(')');
pe.handleCodeKeydown(evSkip);
eq(codeEditor.value, '()', '右半边已存在 → 不重复输入');
eq(codeEditor.selectionStart, 2, '光标跳过右半边');
assert(evSkip._pd === true, '跳过时阻止了默认输入');

setValue('don', 3, 3);
pe.handleCodeKeydown(key("'"));
eq(codeEditor.value, 'don', '词内单引号（don\'t 场景）不自动补');

setValue('"x"', 2, 2);
const evQ = key('"');
pe.handleCodeKeydown(evQ);
eq(codeEditor.value, '"x"', '光标在配对引号之前 → 跳过而非重复插入');
eq(codeEditor.selectionStart, 3, '引号跳过：光标越过右半边');

setValue('"x"', 3, 3);
const evQ2 = key('"');
pe.handleCodeKeydown(evQ2);
eq(codeEditor.value, '"x"', '字符串末尾再按引号：不自动补（交回浏览器输入单个）');
assert(evQ2._pd !== true, '该情形不阻止默认输入');

console.log('== 输入 } 自动反缩进 ==');
setValue('        ', 8, 8);
pe.handleCodeKeydown(key('}'));
eq(codeEditor.value, '    }', '整行仅缩进时输入 } → 退一级缩进');
eq(codeEditor.selectionStart, 5, '光标停在 } 之后');

console.log('== 缩进（Tab）==');
setValue('    a\n    b', 0, 11);
pe.applyIndent(false);
eq(codeEditor.value, '        a\n        b', 'Tab 对多行整块缩进');
pe.applyIndent(true);
eq(codeEditor.value, '    a\n    b', 'Shift+Tab 整块反缩进');

function near(a, b, tol) {
    return Math.abs(a - b) <= (tol === undefined ? 0.01 : tol);
}

console.log('== 光标跟随滚动（本次核心诉求）==');
const LINES = Array.from({ length: 100 }, (_, i) => 'line' + (i + 1)).join('\n');
const line50Start = LINES.split('\n').slice(0, 49).join('\n').length + 1;
codeEditor.scrollTop = 0;
setValue(LINES, line50Start, line50Start);
pe.scrollCaretIntoView();
const expectDown = 12 + 50 * 20.8 - 200;      // yBot - clientHeight
assert(near(codeEditor.scrollTop, expectDown), '光标移到下方不可见处 → 自动把滚动条下移到光标可见（' + codeEditor.scrollTop.toFixed(1) + '）');

codeEditor.scrollTop = 5000;
setValue(LINES, 0, 0);                          // 光标回第 1 行
pe.scrollCaretIntoView();
assert(near(codeEditor.scrollTop, 12), '光标回到上方不可见处 → 自动把滚动条上移（' + codeEditor.scrollTop.toFixed(1) + '）');

console.log('== 当前行高亮 ==');
codeEditor.scrollTop = 0;
setValue(LINES, line50Start, line50Start);
pe.updateCurrentLine();
const ty = parseFloat(String(curLineEl.style.transform).replace(/[^0-9.\-]/g, ''));
assert(near(parseFloat(curLineEl.style.height), 20.8), '当前行高度 == 行高');
assert(near(ty, 12 + 49 * 20.8 - 0), '当前行高亮条随光标定位（' + ty.toFixed(1) + '）');

console.log('== 代码草稿持久化（防切题 / 刷新丢代码） ==');
eq(pe.draftKey(7, 'easy'), '7:easy', '草稿键 = 题号:档位');
eq(pe.draftKey(7), '7:easy', '档位缺省 → easy');

pe.setExercise({ id: 7, tiers: { easy: { starter: 'int main(){}' } } }, 'easy');
codeEditor.value = 'int main(){ /* mine */ }';
pe.saveDraftNow();
let raw = JSON.parse(storage.get('practice.draft.v1') || '{}');
eq(raw['7:easy'], 'int main(){ /* mine */ }', '编辑内容写入草稿存储');

codeEditor.value = 'int main(){}';            // 内容回到初始代码
pe.saveDraftNow();
raw = JSON.parse(storage.get('practice.draft.v1') || '{}');
assert(!Object.prototype.hasOwnProperty.call(raw, '7:easy'), '内容 == 初始代码 → 草稿自动删除（保持精简）');

console.log('== 草稿按「题号:档位」隔离 ==');
const tiers7 = { easy: { starter: 'A' }, hard: { starter: 'B' } };
pe.setExercise({ id: 7, tiers: tiers7 }, 'easy');
codeEditor.value = 'easy-code';
pe.saveDraftNow();
pe.setExercise({ id: 7, tiers: tiers7 }, 'hard');
codeEditor.value = 'hard-code';
pe.saveDraftNow();
raw = JSON.parse(storage.get('practice.draft.v1') || '{}');
eq(raw['7:easy'], 'easy-code', '同一题 easy 档草稿独立保存');
eq(raw['7:hard'], 'hard-code', '同一题 hard 档草稿独立保存');

console.log('== loadDrafts / clearDraft（重置代码语义） ==');
storage.set('practice.draft.v1', JSON.stringify({ '9:hard': 'keepme' }));
eq(pe.loadDrafts()['9:hard'], 'keepme', 'loadDrafts 读回既有草稿');
pe.setDrafts(pe.loadDrafts());                 // 让模块内存态与存储一致（模拟启动加载）
eq(pe.clearDraft(9, 'hard'), true, 'clearDraft 命中已存在草稿 → true');
eq(pe.clearDraft(9, 'hard'), false, '再次 clearDraft → false（幂等）');

console.log('== 草稿数量上限（超限裁剪） ==');
const many = {};
for (let i = 0; i < 200; i++) many['x' + i + ':easy'] = 'c' + i;
pe.setDrafts(many);
pe.persistDrafts();
eq(Object.keys(pe.getDrafts()).length, 80, '超限 → 裁剪到 DRAFT_MAX=80 份');
assert(!Object.prototype.hasOwnProperty.call(pe.getDrafts(), 'x0:easy'), '丢弃最早写入的草稿');
assert(Object.prototype.hasOwnProperty.call(pe.getDrafts(), 'x199:easy'), '保留最新写入的草稿');

console.log('');
if (failed === 0) {
    console.log('\u2713 编辑器编辑规则逻辑：全部通过');
    process.exit(0);
} else {
    console.error('\u2717 失败 ' + failed + ' 项');
    process.exit(1);
}
