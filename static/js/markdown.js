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
            hljs.highlightElement(block);
        });
    }
    attachHeadingIds(el);
    attachSourceOffsets(el, text);
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
