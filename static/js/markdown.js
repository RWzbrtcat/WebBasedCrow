// ============================================
// 共享 Markdown 渲染工具
// 依赖：marked.min.js、purify.min.js、highlight.min.js（需先加载）
// ============================================

// 开启 GitHub 风格 Markdown，并让单个换行也生效
marked.setOptions({
    gfm: true,
    breaks: true
});

// 修补 marked v12 的强调定界符正则：当包裹内容以括号等标点结尾、后面紧跟文字时
// （如 **加粗）**后面），闭合的 ** 会被误判为「仅左边界」而无法闭合，导致加粗失效。
// 这里把「标点 + 定界符 + 文字」从「左边界」改为「可左可右」，使其能正常闭合。
(function patchEmphasisDelimiters() {
    const inline = marked.Lexer.rules.inline;
    const emStrongRDelimAst = /^[^_*]*?__[^_*]*?\*[^_*]*?(?=__)|[^*]+(?=[^*])|(?!\*)[\p{P}\p{S}](\*+)(?=[\s]|$)|[^\p{P}\p{S}\s](\*+)(?!\*)(?=[\p{P}\p{S}\s]|$)|(?!\*)[\s](\*+)(?=[^\p{P}\p{S}\s])|[\s](\*+)(?!\*)(?=[\p{P}\p{S}])|(?!\*)[\p{P}\p{S}](\*+)(?!\*)(?=[\p{P}\p{S}]|[^\p{P}\p{S}\s])|[^\p{P}\p{S}\s](\*+)(?=[^\p{P}\p{S}\s])/gu;
    const emStrongRDelimUnd = /^[^_*]*?\*\*[^_*]*?_[^_*]*?(?=\*\*)|[^_]+(?=[^_])|(?!_)[\p{P}\p{S}](_+)(?=[\s]|$)|[^\p{P}\p{S}\s](_+)(?!_)(?=[\p{P}\p{S}\s]|$)|(?!_)[\s](_+)(?=[^\p{P}\p{S}\s])|[\s](_+)(?!_)(?=[\p{P}\p{S}])|(?!_)[\p{P}\p{S}](_+)(?!_)(?=[\p{P}\p{S}]|[^\p{P}\p{S}\s])/gu;
    ['normal', 'gfm', 'breaks', 'pedantic'].forEach((variant) => {
        inline[variant].emStrongRDelimAst = emStrongRDelimAst;
        inline[variant].emStrongRDelimUnd = emStrongRDelimUnd;
    });
})();

// 将 Markdown 文本渲染为安全的 HTML 字符串
function renderMarkdown(text) {
    if (!text || !text.trim()) return '';
    const html = marked.parse(text);
    return DOMPurify.sanitize(html);
}

// 渲染 Markdown 到指定元素，并对代码块做语法高亮
function renderMarkdownInto(el, text) {
    el.innerHTML = renderMarkdown(text);
    if (window.hljs) {
        el.querySelectorAll('pre code').forEach((block) => {
            // Mermaid 交给图表渲染，不做代码高亮
            if (block.classList.contains('language-mermaid') || block.classList.contains('lang-mermaid')) return;
            hljs.highlightElement(block);
        });
    }
    attachHeadingIds(el);
    attachSourceOffsets(el, text);
    renderMermaidIn(el);
}

// ===== Mermaid 图表支持 =====
// 只有文中出现 ```mermaid 时才按需加载图表库，避免拖慢首屏；多 CDN 依次回退
const MERMAID_CDNS = [
    'https://fastly.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js',  // 国内访问较快
    'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js',
    'https://unpkg.com/mermaid@11/dist/mermaid.min.js'
];
let mermaidLoading = null;

function ensureMermaid() {
    if (window.mermaid) return Promise.resolve(window.mermaid);
    if (mermaidLoading) return mermaidLoading;

    mermaidLoading = new Promise((resolve, reject) => {
        let index = 0;
        const tryNext = () => {
            if (index >= MERMAID_CDNS.length) {
                mermaidLoading = null;
                reject(new Error('Mermaid 资源加载失败'));
                return;
            }
            const script = document.createElement('script');
            script.src = MERMAID_CDNS[index++];
            script.onload = () => {
                if (!window.mermaid) { tryNext(); return; }
                try {
                    window.mermaid.initialize({
                        startOnLoad: false,
                        securityLevel: 'strict',   // 禁止图表里的 HTML 标签与点击跳转
                        theme: 'default',
                        flowchart: { curve: 'basis', useMaxWidth: true },
                        fontFamily: getComputedStyle(document.body).fontFamily || 'sans-serif'
                    });
                } catch (e) { /* 初始化失败不影响后续渲染尝试 */ }
                resolve(window.mermaid);
            };
            script.onerror = tryNext;
            document.head.appendChild(script);
        };
        tryNext();
    });
    return mermaidLoading;
}

// 编辑器里边打字边渲染代价较高：用计时器合并连续调用，只在输入停顿时渲染一次
let mermaidTimer = null;
let mermaidToken = 0;

function renderMermaidIn(el) {
    if (!el) return;
    if (mermaidTimer) clearTimeout(mermaidTimer);
    const hasMermaid = el.querySelector('pre > code.language-mermaid, pre > code.lang-mermaid');
    if (!hasMermaid) return;
    mermaidTimer = setTimeout(() => renderMermaidBlocks(el, ++mermaidToken), 300);
}

async function renderMermaidBlocks(el, token) {
    let mermaid;
    try {
        mermaid = await ensureMermaid();
    } catch (e) {
        console.warn('[mermaid] 加载失败，按普通代码块显示', e);
        return;
    }
    if (token !== mermaidToken) return;   // 已有更新的一轮渲染，放弃本次

    const blocks = Array.from(el.querySelectorAll('pre > code.language-mermaid, pre > code.lang-mermaid'));
    for (let i = 0; i < blocks.length; i++) {
        const code = blocks[i];
        const pre = code.closest('pre');
        if (!pre) continue;
        const source = code.textContent;
        const offset = pre.dataset.offset;   // 保留源文本偏移，双击预览仍能定位

        const box = document.createElement('div');
        box.className = 'mermaid-block';
        if (offset) box.dataset.offset = offset;

        try {
            const { svg } = await mermaid.render(`mermaid-${Date.now()}-${i}`, source);
            if (token !== mermaidToken) return;
            // mermaid 在 securityLevel:strict 下已自行消毒，直接插入以免 DOMPurify 破坏 SVG 结构
            box.innerHTML = svg;
        } catch (err) {
            box.classList.add('mermaid-block-error');
            const tip = document.createElement('div');
            tip.className = 'mermaid-error-tip';
            tip.textContent = 'Mermaid 语法有误，已显示源码';
            const src = document.createElement('pre');
            src.className = 'mermaid-source';
            src.textContent = source;
            box.appendChild(tip);
            box.appendChild(src);
        }
        pre.replaceWith(box);
    }
}

// 为预览中的顶层块级元素标注其在 Markdown 源文本中的字符偏移，
// 用于「双击预览 → 定位到左侧编辑位置」。
function attachSourceOffsets(el, text) {
    let tokens;
    try {
        tokens = marked.lexer(text);
    } catch (e) {
        return;
    }

    let offset = 0;
    let blockIndex = 0;
    const children = el.children;

    for (const token of tokens) {
        const raw = token.raw || '';
        if (!raw) continue;
        const idx = text.indexOf(raw, offset);
        if (idx === -1) continue;

        if (token.type !== 'space') {
            const block = children[blockIndex];
            if (block) {
                block.dataset.offset = String(idx);
                if (token.type === 'list') {
                    attachListOffsets(block, token, idx);
                }
                blockIndex++;
            }
        }
        offset = idx + raw.length;
    }
}

// 为列表的每个 <li> 标注其在源文本中的偏移，使双击可定位到具体条目
function attachListOffsets(listEl, listToken, baseOffset) {
    const items = listToken.items || [];
    const liEls = Array.from(listEl.children).filter((c) => c.tagName === 'LI');

    let itemOffset = baseOffset;
    items.forEach((item, i) => {
        const raw = item.raw || '';
        const li = liEls[i];
        if (li) {
            li.dataset.offset = String(itemOffset);

            const nested = (item.tokens || []).find((t) => t.type === 'list');
            if (nested) {
                const nestedEl = li.querySelector('ul, ol');
                const first = (nested.items && nested.items[0] && nested.items[0].raw) || '';
                const pos = first ? raw.indexOf(first) : -1;
                if (nestedEl && pos !== -1) {
                    attachListOffsets(nestedEl, nested, itemOffset + pos);
                }
            }
        }
        itemOffset += raw.length;
    });
}

// GitHub 风格标题锚点：转小写、把空格与标点折叠成连字符、保留中文等非 ASCII 字符，
// 与文章内部链接 `[文字](#锚点)` 的书写规则保持一致。
function slugify(text) {
    return String(text == null ? '' : text)
        .normalize('NFKD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .trim()
        .replace(/[\s~`!@#$%^&*()\-_+=[\]{}|\\;:"'“”‘’<>,.?/]+/g, '-')
        .replace(/-{2,}/g, '-')
        .replace(/^-|-$/g, '');
}

// 为渲染出的标题添加 id，使文章内部链接 [文字](#锚点) 可跳转；同名标题按 -1、-2 去重
function attachHeadingIds(el) {
    const used = new Map();
    el.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach((h) => {
        const base = slugify(h.textContent);
        if (!base) return;
        let id = base;
        const n = used.get(base) || 0;
        if (n > 0) id = `${base}-${n}`;
        used.set(base, n + 1);
        h.id = id;
    });
}

// 拦截文章内部锚点链接（href 以 # 开头），改为平滑滚动到对应标题，
// 避免浏览器原生 hash 跳转的瞬时定位；rootEl 内部每次渲染只绑定一次即可。
function bindInternalLinks(rootEl) {
    if (!rootEl) return;
    rootEl.addEventListener('click', (e) => {
        const a = e.target.closest('a[href^="#"]');
        if (!a) return;
        const href = a.getAttribute('href');
        if (!href || href === '#') return;
        const target = document.getElementById(href.slice(1));
        if (!target) return;
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
}
