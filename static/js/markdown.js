// ============================================
// 共享 Markdown 渲染工具
// 依赖：marked.min.js、purify.min.js（需先加载）
// ============================================

// 开启 GitHub 风格 Markdown，并让单个换行也生效
marked.setOptions({
    gfm: true,
    breaks: true
});

// 将 Markdown 文本渲染为安全的 HTML 字符串
function renderMarkdown(text) {
    if (!text || !text.trim()) return '';
    const html = marked.parse(text);
    return DOMPurify.sanitize(html);
}
