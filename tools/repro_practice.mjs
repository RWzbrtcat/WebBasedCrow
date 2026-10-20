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
assert(html.includes('id="codeCurrentLine"') && html.includes('practice-code-currentline'),
    '含当前行高亮条 codeCurrentLine');
assert(!/class="practice-editor"/.test(html), '旧的 .practice-editor 纯 textarea 已移除');

assert(js.includes('hljs.highlight') && js.includes("language: 'cpp'"), 'JS 用 hljs 做 C++ 语法高亮');
assert(js.includes('refreshCodeEditor'), 'JS 有编辑器重绘 refreshCodeEditor');
assert(js.includes('renderCodeNumbers'), 'JS 渲染行号');
assert(js.includes('syncCodeScroll'), 'JS 同步行号/高亮层滚动');
assert(js.includes('handleCodeKeydown'), 'JS 接管编辑器快捷键');
assert(js.includes('applyIndent') && js.includes('autoIndentOnEnter'), 'Tab 缩进 + Enter 自动缩进');
assert(js.includes('renderTier(currentTier)') && js.includes("INDENT = '    '"), '切档位后重绘、缩进为 4 空格');

// 3d-2. 滚动同步改用「transform 跟随」——根治高亮层/行号被 clamp 导致的错位
console.log('== 编辑器滚动同步：transform 跟随（防 clamp 错位）==');
assert(html.includes('id="codeGutterInner"'), 'HTML 行号槽含可平移内层 codeGutterInner');
assert(css.includes('.practice-code-gutter-inner'), 'style.css 含行号内层样式');
assert(js.includes("getElementById('codeGutterInner')"), 'JS 解析行号内层引用');
{
    const from = js.indexOf('function syncCodeScroll');
    const fn = from >= 0 ? js.slice(from, from + 800) : '';
    assert(fn.length > 0, '能定位 syncCodeScroll');
    assert(/codeHighlightEl\.style\.transform/.test(fn), 'syncCodeScroll 用 transform 平移高亮层');
    assert(/codeGutterInnerEl\.style\.transform/.test(fn), 'syncCodeScroll 用 transform 平移行号内层');
    assert(!/\.scrollTop\s*=/.test(fn), 'syncCodeScroll 不再对高亮层/行号槽设 scrollTop（避免被 clamp）');
}

// 3e. VS Code 级编辑规则 + 光标跟随滚动
console.log('== 编辑器：VS Code 编辑规则与光标跟随 ==');
assert(js.includes('function scrollCaretIntoView'), 'JS 有「光标跟随滚动」scrollCaretIntoView');
assert(js.includes('function onCaretActivity'), 'JS 有光标活动统一收尾 onCaretActivity');
assert(/\[.keyup., .click., .select., .focus.\]/.test(js) && js.includes('onCaretActivity'),
    'keyup/click/select/focus 绑定到光标活动（方向键移动也会跟随滚动）');
assert(js.includes('function updateCurrentLine'), 'JS 有当前行高亮 updateCurrentLine');
assert(js.includes('function toggleLineComment'), 'JS 有 Ctrl+/ 整行注释开关');
assert(js.includes('function moveLines'), 'JS 有 Alt+↑/↓ 移动行 / Shift+Alt+↑/↓ 复制行');
assert(js.includes('function smartHome'), 'JS 有智能 Home');
assert(/e\.key === .\/./.test(js) && /e\.altKey/.test(js) && /ArrowUp/.test(js),
    '注册了 Ctrl+/ 与 Alt+方向键 快捷键');
assert(js.includes('PAIRS[prev] === next'), 'Enter 在成对括号之间会展开成三行');

// 3e-2. Backspace 智能反缩进 —— 对齐 VS Code getDeleteLeftRange（缩进区内退到上一个制表位）
console.log('== 编辑器：Backspace 智能反缩进 ==');
assert(js.includes('function smartBackspace'), 'JS 有缩进区智能反缩进 smartBackspace');
assert(/INDENT_SIZE\s*=\s*INDENT\.length/.test(js), '缩进宽度由 INDENT.length 派生（供制表位计算）');
{
    const from = js.indexOf('function smartBackspace');
    const fn = from >= 0 ? js.slice(from, from + 1600) : '';
    assert(fn.length > 0, '能定位 smartBackspace');
    assert(fn.includes('/^[ \\t]*$/'), 'smartBackspace 判定「光标是否落在缩进区」（行首→光标全为空白）');
    assert(fn.includes('INDENT_SIZE - (vis % INDENT_SIZE)'), '制表符按可见列展开（tab stop）');
    assert(fn.includes('vis % INDENT_SIZE) || INDENT_SIZE'), '目标列 = 上一个缩进制表位（prevIndentTabStop 语义）');
    assert(fn.includes('pos === lineStart'), '行首不接管（交回默认合并上一行）');
    assert(/selectionStart !== ta\.selectionEnd/.test(fn), '有选区时不接管（整段删除交给默认）');
}
{
    const from = js.indexOf("e.key === 'Backspace'");
    const seg = from >= 0 ? js.slice(from, from + 900) : '';
    assert(seg.includes('smartBackspace()'), 'Backspace 分支接入 smartBackspace');
    assert(/PAIRS\[prev\] === v\[s\]/.test(seg), '成对括号删除仍优先于智能反缩进');
}

assert(css.includes('.practice-code-gutter'), 'style.css 含行号槽样式');
assert(css.includes('.practice-code-hl .hljs-keyword'), 'style.css 含编辑器 token 配色');
assert(css.includes('.practice-code-body:focus-within'), 'style.css 含编辑器聚焦态');
assert(css.includes('.practice-code-currentline'), 'style.css 含当前行高亮条样式');

// 3e-2. 代码编辑器主题切换（Dark+ / Light+ / Solarized Dark / Monokai，类似 VS Code「颜色主题」）
console.log('== 代码编辑器主题切换 ==');
{
    assert(html.includes('id="codeTheme"'), 'practice.html 含编辑器主题选择器 #codeTheme');
    assert(/<option value="dark"[\s\S]*?<option value="light"[\s\S]*?<option value="solarized"[\s\S]*?<option value="monokai"/.test(html),
        '主题选择器含 4 个选项（dark / light / solarized / monokai）');
    assert(css.includes('#codeShell[data-editor-theme="light"]')
        && css.includes('#codeShell[data-editor-theme="solarized"]')
        && css.includes('#codeShell[data-editor-theme="monokai"]'),
        'CSS 含 3 套非默认主题覆盖（仅覆盖颜色变量，结构不变）');
    const codeBlock = css.slice(css.indexOf('.practice-code {'), css.indexOf('/* 顶部标签条'));
    assert(codeBlock.includes('--c-bg') && codeBlock.includes('--c-tok-keyword'), '编辑器默认色板抽成 CSS 变量（#codeShell 作用域）');
    assert(/var\(--c-bg\)/.test(css) && /var\(--c-tok-keyword\)/.test(css), '编辑器规则引用 CSS 变量（非硬编码）');
    assert(/var\(--c-tok-comment\)/.test(css) && /var\(--c-tok-function\)/.test(css), 'token 配色随主题切换');
}
assert(js.includes('function applyEditorTheme'), 'JS 有 applyEditorTheme');
assert(js.includes('function loadEditorTheme') && js.includes('function saveEditorTheme'), 'JS 有主题读取 / 保存');
assert(js.includes('EDITOR_THEME_KEY'), 'JS 用 localStorage 键持久化主题');
assert(/codeShellEl\.dataset\.editorTheme/.test(js), 'applyEditorTheme 写 #codeShell[data-editor-theme]');
assert(js.includes('applyEditorTheme(loadEditorTheme())'), '启动时恢复上次选择的主题');
assert(/codeThemeSelEl\.addEventListener\('change'/.test(js), '主题选择器 change 事件已接线');
// 编辑器配色：默认（Dark+）= VS Code Dark+ 色板；token 规则走变量，可被 Light+/Solarized/Monokai 覆盖
{
    const defFrom = css.indexOf('.practice-code {');
    const defTo = css.indexOf('}', defFrom);                 // 默认主题变量块（首个 } 结束变量声明）
    const defBlock = defFrom >= 0 && defTo > defFrom ? css.slice(defFrom, defTo) : '';
    assert(defBlock.length > 0, '能定位编辑器默认主题变量块');
    assert(!/#c678dd/.test(defBlock) && !/#e6c07b/.test(defBlock), '编辑器 token 已弃用 Atom One Dark 配色');
    assert(/#569cd6/.test(defBlock) && /#4ec9b0/.test(defBlock) && /#6a9955/.test(defBlock) && /#ce9178/.test(defBlock),
        '默认主题（Dark+）token 为 VS Code Dark+ 色板（#569cd6/#4ec9b0/#6a9955/#ce9178）');
    assert(css.includes('.practice-code-hl .hljs-keyword') && css.includes('var(--c-tok-keyword)'),
        '编辑器 token 规则引用变量（可被多套主题覆盖）');
}

// 3e-3. 代码字号可调（顶栏 A− / A+ 步进，Ctrl / ⌘ + 滚轮缩放）
console.log('== 代码字号可调 ==');
{
    assert(html.includes('id="codeFontVal"') && html.includes('id="codeFontDown"') && html.includes('id="codeFontUp"'),
        'practice.html 含字号控件（数值 + A− / A+）');
    assert(html.includes('class="practice-code-tools"') && html.includes('class="practice-code-font"'),
        '字号与主题控件同处顶栏右侧容器');
    // 字号必须走 CSS 变量：三层（行号槽 / 高亮层 / 输入框）共用，才不会错位
    const fb = css.slice(css.indexOf('.practice-code {'), css.indexOf('/* 顶部标签条'));
    assert(/--c-fs:\s*13px/.test(fb) && /--c-lh:\s*1\.6/.test(fb), '编辑器字号 / 行高抽成变量 --c-fs / --c-lh');
    assert(/\.practice-code-gutter\s*\{[\s\S]*?font-size:\s*var\(--c-fs\)/.test(css), '行号槽字号走变量');
    assert(/\.practice-code-hl,\s*\n\.practice-code-input\s*\{[\s\S]*?font-size:\s*var\(--c-fs\)/.test(css),
        '高亮层与输入框字号走同一变量（逐像素一致的前提）');
    assert(/\.practice-code-currentline\s*\{[\s\S]*?height:\s*calc\(var\(--c-fs\) \* var\(--c-lh\)\)/.test(css),
        '当前行高亮条高度由字号变量算出');
    assert(css.includes('.practice-code-font-btn') && css.includes('.practice-code-font-val'), 'CSS 含字号控件样式');
    assert(/\.practice-code-font-btn:disabled/.test(css), '到上/下限时按钮置灰');
}
{
    assert(js.includes('function applyEditorFontSize'), 'JS 有 applyEditorFontSize');
    assert(js.includes('function stepEditorFontSize'), 'JS 有 stepEditorFontSize（步进）');
    assert(js.includes('function loadEditorFontSize') && js.includes('function saveEditorFontSize'), 'JS 有字号读取 / 保存');
    assert(js.includes('EDITOR_FONT_KEY'), 'JS 用 localStorage 键持久化字号');
    assert(/setProperty\('--c-fs'/.test(js), 'applyEditorFontSize 写 --c-fs 到 #codeShell');
    assert(/EDITOR_FONT_MIN\s*=\s*11[\s\S]{0,80}EDITOR_FONT_MAX\s*=\s*20/.test(js), '字号范围 11–20px');
    assert(js.includes('applyEditorFontSize(loadEditorFontSize())'), '启动时恢复上次选择的字号');
    assert(/codeFontDownEl\.addEventListener\('click'/.test(js) && /codeFontUpEl\.addEventListener\('click'/.test(js),
        'A− / A+ 点击已接线');
    assert(/addEventListener\('wheel'/.test(js) && /e\.ctrlKey && !e\.metaKey|!e\.ctrlKey && !e\.metaKey/.test(js)
        && /passive:\s*false/.test(js), 'Ctrl / ⌘ + 滚轮缩放已接线（且阻止浏览器整页缩放）');
    assert(/codeFontValEl\.textContent\s*=\s*String\(size\)/.test(js), '字号变化时顶栏数值同步刷新');
}

// 3f. 对比度：题解代码块底色 + 编辑器「着重显示」与选区
console.log('== 对比度：题解代码块底色与编辑器选区 ==');
{
    const solFrom = css.indexOf('.practice-solution-body pre {');
    const solTo = css.indexOf(':not(pre) > code', solFrom);
    const solPre = solFrom >= 0 && solTo > solFrom ? css.slice(solFrom, solTo) : '';
    assert(solPre.length > 0, '能定位题解代码块样式');
    assert(/#1f2328/.test(solPre), '题解代码块用深底 #1f2328（与站点代码块一致）');
    assert(!/var\(--code-bg/.test(solPre), '题解代码块不再铺浅底（浅底会让 Atom One Dark token 看不清）');
    assert(/#e5e7eb/.test(solPre), '题解代码块显式声明浅色文字');
}
assert(/\.practice-code-input\s*\{[^}]*z-index:\s*2/.test(css), '输入框 z-index:2（原生光标始终可见）');
assert(/\.practice-code-hl\s*\{[^}]*z-index:\s*1/.test(css),
    '高亮层 z-index:1（留在输入框之下，不遮挡光标）');
{
    const selFrom = css.indexOf('.practice-code-input::selection');
    const selRule = selFrom >= 0 ? css.slice(selFrom, css.indexOf('}', selFrom)) : '';
    assert(selRule.length > 0, '能定位编辑器选区样式');
    assert(/background:\s*var\(--c-sel\)/.test(selRule),
        '选区底色走变量 var(--c-sel)（Dark+ 默认仍是半透明蓝，可被主题覆盖）');
    assert(/#ffffff|#fff\b|:\s*white/.test(selRule) === false,
        '选区规则不再用不透明白字盖掉语法色（否则选中注释会突变为正体白字）');
    assert(/-webkit-text-fill-color:\s*transparent/.test(selRule),
        '选区文字保持透明，字形交给下层高亮层');
}
// Dark+ 默认选区底色仍是半透明蓝：选中注释时让下层绿色斜体透出来（防「选中变白变正体」回潮）
{
    const defFrom = css.indexOf('.practice-code {');
    const defTo = css.indexOf('}', defFrom);
    const defBlock = defFrom >= 0 && defTo > defFrom ? css.slice(defFrom, defTo) : '';
    assert(/--c-sel:\s*rgba\(\s*38\s*,\s*79\s*,\s*120\s*,\s*0?\.\d+\s*\)/.test(defBlock),
        'Dark+ 默认选区底色为半透明蓝 rgba(38,79,120,α<1)——让下层语法配色透出来');
}

// 3g. 答题工作台：头部操作区 + 去标题条 + 编辑器吃满
console.log('== 答题工作台：头部操作区与空间回收 ==');
assert(html.includes('id="topActions"'), '头部含答题操作区 #topActions');
{
    const header = extractDivBlock(html, '<div class="header-inner"');
    assert(header.includes('id="submitBtn"') && header.includes('id="resetBtn"') && header.includes('id="answerSubmitBtn"'),
        '提交运行 / 重置代码 / 提交答案 已移入头部操作区');
    assert(!/data-auth-role="admin"/.test(header), '导航不再挂 草稿 / 隐藏 / 创作（管理入口仍在头像菜单）');
}
assert(!html.includes('practice-bar') && !html.includes('practice-title') && !html.includes('practice-sub'),
    '页面标题条 .practice-bar 已删除');
{
    const side = extractDivBlock(html, '<div class="practice-side-head"');
    assert(side.includes('practiceProgress'), '进度已并入左栏栏头');
}
assert(!html.includes('practice-editor-head'), '编辑器卡表头已删（C++20 与状态栏信息重复）');
assert(!html.includes('practice-editor-actions'), '卡内底部操作条已删（按钮移入头部）');
assert(js.includes('function syncActions'), 'JS 有头部操作区切换 syncActions');
assert(/syncActions\('code'\)/.test(js) && /syncActions\('objective'\)/.test(js) && /syncActions\('none'\)/.test(js),
    '写代码题 / 客观题 / 空态三种操作区状态均已接入');
assert(!/blankSubmitBtn/.test(js), '填空题不再自建内联提交按钮');

// 代码草稿持久化（防切题 / 刷新丢代码）
assert(/DRAFT_KEY = 'practice\.draft\.v1'/.test(js), 'JS 定义草稿存储键 practice.draft.v1');
['loadDrafts', 'persistDrafts', 'saveDraftNow', 'scheduleSaveDraft', 'flushDraft', 'clearDraft'].forEach((fn) => {
    assert(js.includes('function ' + fn), '草稿函数 ' + fn + ' 已实现');
});
assert(/renderTier[\s\S]{0,400}hasOwnProperty\.call\(drafts, key\)/.test(js),
    'renderTier 优先恢复草稿，无草稿才用初始代码');
assert(/resetBtn\.addEventListener[\s\S]{0,300}clearDraft\(currentExercise\.id, currentTier\)/.test(js),
    '「重置代码」先清除本题本档草稿');
assert(/selectExercise[\s\S]{0,160}flushDraft\(\)/.test(js), '切题前 flushDraft 落盘旧题草稿');
assert(/btn\.addEventListener\('click', \(\) => \{\s*flushDraft\(\)/.test(js), '切档位前 flushDraft 落盘');
assert(/addEventListener\('input'[\s\S]{0,90}scheduleSaveDraft/.test(js), '编辑器输入 → 防抖存草稿');
// 常量必须在状态初始化之前（否则 loadDone/loadLastResults/loadDrafts 命中 TDZ，本地缓存恒读不出）
assert(js.indexOf('const DONE_KEY') < js.indexOf('let doneSet = loadDone()'),
    '存储键常量声明在状态初始化之前（防 TDZ 吞掉本地缓存）');
// 左栏章节树：学期 / 章节可折叠（多开、折叠与选中解耦、状态持久化）
console.log('== 左栏章节树：可折叠 ==');
assert(/TREE_KEY = 'practice\.tree\.v1'/.test(js), 'JS 定义章节树折叠状态键 practice.tree.v1');
assert(js.indexOf('const TREE_KEY') < js.indexOf('loadTreeState()'),
    'TREE_KEY 声明在 loadTreeState() 调用之前（防 TDZ 吞掉折叠状态）');
['loadTreeState', 'persistTreeState', 'toggleSemester', 'toggleChapter',
    'ensureChapterExercises', 'hydrateOpenChapters', 'pruneOpenChapters', 'semesterOf', 'caretSvg'].forEach((fn) => {
    assert(js.includes('function ' + fn), '章节树函数 ' + fn + ' 已实现');
});
assert(/hydrateOpenChapters[\s\S]{0,120}ensureChapterExercises/.test(js),
    '重载时预拉取上次展开章节的题目（防「展开但空白」）');
assert(/pruneOpenChapters\(\)[\s\S]{0,80}openChapters\.delete/.test(js) || /!valid\.has\(id\)[\s\S]{0,60}openChapters\.delete/.test(js),
    '丢弃已不存在章节的展开状态（题库改版后残留 id 自愈）');
assert(js.includes('openChapters') && js.includes('collapsedSemesters'), '含「展开章节」「折叠学期」两套状态');
assert(js.includes('chapterExercisesCache'), '已展开章节的题目列表有缓存（多开时不重复拉取）');
assert(/function renderExerciseList\(list\)/.test(js), 'renderExerciseList 接收列表参数（支持多章同时展开）');
assert(/open:\s*Array\.from\(openChapters\)/.test(js) && /collapsed:\s*Array\.from\(collapsedSemesters\)/.test(js),
    'persistTreeState 持久化展开 / 折叠状态');
assert(/if \(semClosed\) return;/.test(js), '学期折叠时不渲染其下章节');
assert(/openChapters\.add\(id\)/.test(js), '点击章节标题会加入展开集合（选中即展开）');
assert(/semesterOf\(id\)/.test(js) && /collapsedSemesters\.delete\(semName\)/.test(js),
    '选中章节时自动展开其所属学期（保证选中项可见）');
assert(/class="practice-caret"[^>]*>\s*'\s*\+\s*caretSvg\(false\)/.test(js),
    '学期头箭头恒为下箭头、折叠方向交给 CSS 旋转（防「右箭头再旋转」变朝上）');
assert(/practice-chapter-toggle[\s\S]{0,300}aria-expanded/.test(js), '章节折叠箭头输出 aria-expanded');
assert(/practice-chapter-toggle[\s\S]{0,400}disabled/.test(js), '无题目章节的箭头禁用（is-leaf）');
assert(css.includes('.practice-chapter-row'), 'CSS 含章节行（箭头 + 标题）容器');
assert(css.includes('.practice-chapter-toggle'), 'CSS 含章节折叠箭头样式');
assert(css.includes('.practice-chapter-toggle.is-leaf'), 'CSS 含无题目章节的箭头占位样式');
assert(css.includes('.practice-semester.is-collapsed .practice-caret'), 'CSS 含学期折叠时箭头旋转');
assert(/\.practice-semester\s*\{[^}]*font-family:\s*inherit/.test(css), '学期头由 div 改 button 后显式继承字体');
assert(/\.practice-caret\s*\{[^}]*color:\s*currentColor/.test(css), '折叠箭头用 currentColor（跟随主题文字色）');
assert(/body\.practice-page \.site-header-pill \.header-inner\s*\{[^}]*grid-template-columns:\s*1fr auto 1fr/.test(css),
    'CSS 头部为三栏网格（1fr auto 1fr）');
assert(/body\.practice-page \.site-header-pill \.nav\s*\{[^}]*grid-column:\s*3/.test(css),
    '导航置于第 3 列（右侧）');
assert(/\.practice-top-actions\s*\{[^}]*grid-column:\s*2[^}]*justify-self:\s*center/.test(css),
    '答题操作置于第 2 列并居中（提交运行 / 重置代码在导航栏中间）');
// 三列必须显式 grid-row:1 —— 否则 Grid 自动排布会因「列号回退」把第三个子项挤到第 2 行
assert(/body\.practice-page \.site-header-pill \.brand\s*\{[^}]*grid-row:\s*1/.test(css),
    '品牌 grid-row:1（锁死单行，防自动排布换行）');
assert(/body\.practice-page \.site-header-pill \.nav\s*\{[^}]*grid-row:\s*1/.test(css),
    '导航 grid-row:1（锁死单行）');
assert(/\.practice-top-actions\s*\{[^}]*grid-row:\s*1/.test(css),
    '答题操作 grid-row:1（锁死单行）');
assert(css.includes('.practice-top-actions'), 'CSS 含头部操作区样式');
// 头部「常驻单行」：宽度不足只压缩尺寸，仅极窄（<480）才回落两行
assert(/body\.practice-page \.site-header-pill \.nav\s*\{[^}]*flex-wrap:\s*nowrap/.test(css),
    '窄屏下导航强制 nowrap（头部保持单行、导航不被拆行）');
const hdrFallback = css.search(/body\.practice-page \.site-header-pill \.header-inner\s*\{[^}]*flex-wrap:\s*wrap/);
assert(hdrFallback > -1, 'CSS 含头部回落两行的兜底规则');
const bpBefore = [...css.slice(0, hdrFallback).matchAll(/@media \(max-width: (\d+)px\)/g)];
const lastBp = bpBefore.length ? Number(bpBefore[bpBefore.length - 1][1]) : 0;
assert(lastBp === 480, '头部回落两行仅在 <480px（手机）触发，当前 ' + lastBp + '）');
assert(!/\.practice-bar\s*\{/.test(css), 'CSS 中 .practice-bar 规则已清理');
assert(/\.practice-layout\s*\{[^}]*grid-template-columns:\s*200px/.test(css), '左栏收窄为 200px、右栏吃满');

// 4. seed 数据（由 tools/gen_practice_seed.py 生成）
console.log('== seed_practice.sql ==');
const seed = readFileSync(resolve(root, 'tools/seed_practice.sql'), 'utf8');
const chapterInserts = (seed.match(/INSERT INTO practice_chapters/g) || []).length;
assert(chapterInserts === 14, '14 个章节');
const exerciseInserts = (seed.match(/INSERT INTO practice_exercises/g) || []).length;
assert(exerciseInserts >= 154, '题目数不应少于 154 道（当前 ' + exerciseInserts + '）');
assert(!/INSERT IGNORE/.test(seed), 'seed 不应再有 INSERT IGNORE（已改 upsert）');
assert(/solution\s+TEXT/.test(seed), 'seed 建表含 solution（题解）列');
assert(seed.includes('ADD COLUMN solution'), 'seed 含 solution 幂等补列迁移（老库自愈，防 1054）');
assert(seed.includes('PREPARE stmt_mig FROM @ddl'), '补列迁移用 information_schema + PREPARE 动态执行');
{
    const solUpserts = (seed.match(/solution=VALUES\(solution\)/g) || []).length;
    assert(solUpserts === exerciseInserts,
        '每题都要带题解 upsert（题 ' + exerciseInserts + ' / 题解 ' + solUpserts + '）');
}
assert(seed.includes('practice_progress'), '含进度表');
// 换行符：seed 为纯 LF 的真正护栏在生成器（写盘前 assert b'\r' not in raw）。
// 本机 core.autocrlf=true 会把检出的 LF 还原成 CRLF（git 库里的 blob 仍是纯 LF），
// 所以这里只断言「无孤立 CR」——孤立的 \r 才会真落进字符串字面量。
{
    const gen = readFileSync(resolve(root, 'tools/gen_practice_seed.py'), 'utf8');
    assert(gen.includes("assert b'\\r' not in raw"), '生成器写盘前断言无 CR（seed LF 的真正护栏）');
    assert(!/\r(?!\n)/.test(seed), 'seed 不含孤立 CR');
    if (seed.includes('\r\n')) {
        console.log('  \u26a0 工作区 seed 检出为 CRLF（core.autocrlf=true）：本机直连导入前先重跑 python tools/gen_practice_seed.py');
    }
}

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

// 8. 左栏列表展示约定（无题型徽章 / 剥题型前缀 / 章节完成度 / 两行标题）
// 背景：侧栏曾只有 200px，题型徽章 + 无 flex 增长的标题把题目标题挤到不可见（见 089eefe）。
console.log('== 左栏列表展示约定 ==');
assert(js.includes('function displayTitle'), 'practice.js 有 displayTitle（剥离标题里的题型前缀）');
assert(/renderExerciseList[\s\S]{0,700}displayTitle\(ex\.title\)/.test(js), '题目列表标题走 displayTitle');
assert(/practice-work-title[\s\S]{0,60}displayTitle\(ex\.title\)/.test(js), '工作台标题同走 displayTitle');
assert(js.includes('function chapterCountHtml'), 'practice.js 有 chapterCountHtml（章节完成度计数）');
assert(js.includes('has-done'), '已完成章节计数带 has-done 标记');
assert(!js.includes('practice-ex-badge'), '题目项不再渲染题型徽章（徽章会挤压标题）');
assert(css.includes('grid-template-columns: 224px'), '左栏默认 224px（题目标题需要宽度，≤1200 回落 200px）');
assert(css.includes('.practice-chapter-count.has-done'), 'style.css 定义 .practice-chapter-count.has-done');
assert(/\.practice-ex-title[\s\S]{0,220}-webkit-line-clamp:\s*2/.test(css), '题目标题最多两行 + 省略号');
assert(/\.practice-chapter-title[\s\S]{0,260}-webkit-line-clamp:\s*2/.test(css), '章节标题最多两行 + 省略号');
assert(/\.practice-ex-title[\s\S]{0,120}flex:\s*1 1 auto/.test(css), '题目标题占满剩余宽度（不再被压到 0 宽）');

console.log(failed === 0 ? '\n\u5168\u90e8\u901a\u8fc7 \u2713' : '\n' + failed + ' \u9879\u5931\u8d25 \u2717');
process.exit(failed === 0 ? 0 : 1);
