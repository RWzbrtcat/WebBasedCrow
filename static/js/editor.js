// ============================================
// 编辑器页逻辑（新建 / 编辑文章）
// ============================================

const API_BASE = '/api';

// 编辑模式下的文章 id（null 表示新建）
let editingId = null;

// 站长维护的专栏列表 [{ id, name }]
let topicsData = [];

// 插入图片时的光标 / 选中上下文
let imageInsertContext = null;

// Tab 键插入的缩进宽度（空格）
const TAB_INDENT = '    ';

// ===== 撤销 / 重做 =====
const MAX_HISTORY = 200;
let undoStack = [];
let redoStack = [];
let lastInputAt = 0; // 用于合并连续输入为一步

function contentTextarea() {
    return document.getElementById('content');
}

// 滚动 textarea，使指定字符偏移所在行出现在可视区中间
function scrollToOffset(ta, offset) {
    const style = getComputedStyle(ta);
    const lineHeight = parseFloat(style.lineHeight) || 20;
    const paddingTop = parseFloat(style.paddingTop) || 0;
    const lineIndex = ta.value.slice(0, offset).split('\n').length - 1;
    ta.scrollTop = Math.max(0, paddingTop + lineIndex * lineHeight - ta.clientHeight / 2);
}

// 记录当前状态到撤销栈（并清空重做栈、重置输入合并计时）
function pushUndoState() {
    const ta = contentTextarea();
    undoStack.push({ value: ta.value, selStart: ta.selectionStart, selEnd: ta.selectionEnd });
    if (undoStack.length > MAX_HISTORY) undoStack.shift();
    redoStack.length = 0;
    lastInputAt = 0;
}

function restoreState(state) {
    const ta = contentTextarea();
    ta.value = state.value;
    ta.focus({ preventScroll: true });
    ta.setSelectionRange(state.selStart, state.selEnd);
    updatePreview();
}

function undo() {
    if (!undoStack.length) return;
    const ta = contentTextarea();
    redoStack.push({ value: ta.value, selStart: ta.selectionStart, selEnd: ta.selectionEnd });
    restoreState(undoStack.pop());
}

function redo() {
    if (!redoStack.length) return;
    const ta = contentTextarea();
    undoStack.push({ value: ta.value, selStart: ta.selectionStart, selEnd: ta.selectionEnd });
    restoreState(redoStack.pop());
}

document.addEventListener('DOMContentLoaded', () => {
    const contentInput = document.getElementById('content');

    // 输入时实时刷新预览
    contentInput.addEventListener('input', updatePreview);

    // 撤销 / 重做：输入前记录状态（800ms 内连续输入合并为一步）
    contentInput.addEventListener('beforeinput', (e) => {
        if (e.inputType && e.inputType.startsWith('history')) return;
        const now = Date.now();
        if (now - lastInputAt > 800) pushUndoState();
        lastInputAt = now;
    });

    // Ctrl+Z 撤销 / Ctrl+Y（或 Ctrl+Shift+Z）重做
    contentInput.addEventListener('keydown', (e) => {
        if (!(e.ctrlKey || e.metaKey)) return;
        const key = e.key.toLowerCase();
        if (key === 'z' && !e.shiftKey) {
            e.preventDefault();
            undo();
        } else if (key === 'y' || (key === 'z' && e.shiftKey)) {
            e.preventDefault();
            redo();
        }
    });

    // 列表回车自动续接：有序列表数字递增、无序列表保持标记
    contentInput.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter' || e.shiftKey || e.ctrlKey || e.metaKey || e.isComposing) return;
        const ta = e.target;
        const pos = ta.selectionStart;
        const value = ta.value;
        const lineStart = value.lastIndexOf('\n', pos - 1) + 1;
        const before = value.slice(lineStart, pos);

        // 代码块内回车：自动继承上一行缩进，行尾是 { ( [ 或 : 时额外缩进一级
        if (isInsideCodeBlock(value, pos)) {
            e.preventDefault();
            pushUndoState();
            const indent = before.match(/^[ \t]*/)[0];
            let newIndent = indent;
            const last = before.trim().slice(-1);
            if (last === '{' || last === '(' || last === '[' || last === ':') {
                newIndent += TAB_INDENT;
            }
            const insert = '\n' + newIndent;
            ta.value = value.slice(0, pos) + insert + value.slice(pos);
            const caret = pos + insert.length;
            ta.setSelectionRange(caret, caret);
            updatePreview();
            return;
        }

        let m = before.match(/^(\s*)([-*+])\s+(.*)$/);
        if (m) {
            const indent = m[1], marker = m[2], item = m[3];
            e.preventDefault();
            pushUndoState();
            if (item.trim() === '') {
                ta.value = value.slice(0, lineStart) + indent + value.slice(pos);
                const caret = lineStart + indent.length;
                ta.setSelectionRange(caret, caret);
            } else {
                const insert = '\n' + indent + marker + ' ';
                ta.value = value.slice(0, pos) + insert + value.slice(pos);
                const caret = pos + insert.length;
                ta.setSelectionRange(caret, caret);
            }
            updatePreview();
            return;
        }

        m = before.match(/^(\s*)(\d+)([.)])\s+(.*)$/);
        if (m) {
            const indent = m[1], num = parseInt(m[2], 10), delim = m[3], item = m[4];
            e.preventDefault();
            pushUndoState();
            if (item.trim() === '') {
                ta.value = value.slice(0, lineStart) + indent + value.slice(pos);
                const caret = lineStart + indent.length;
                ta.setSelectionRange(caret, caret);
            } else {
                const insert = '\n' + indent + (num + 1) + delim + ' ';
                ta.value = value.slice(0, pos) + insert + value.slice(pos);
                const caret = pos + insert.length;
                ta.setSelectionRange(caret, caret);
            }
            updatePreview();
        }
    });

    // Tab 缩进 / Shift+Tab 反缩进（拦截 Tab 默认的焦点跳转）
    contentInput.addEventListener('keydown', (e) => {
        if (e.key !== 'Tab') return;
        e.preventDefault();
        const ta = e.target;
        const start = ta.selectionStart;
        const end = ta.selectionEnd;
        pushUndoState();

        if (start === end && !e.shiftKey) {
            ta.value = ta.value.slice(0, start) + TAB_INDENT + ta.value.slice(end);
            ta.setSelectionRange(start + TAB_INDENT.length, start + TAB_INDENT.length);
        } else {
            indentBlock(ta, start, end, e.shiftKey);
        }
        updatePreview();
    });

    // 编辑器滚动时同步高亮层
    contentInput.addEventListener('scroll', syncEditorScroll);

    // 工具栏按钮（含下拉菜单）
    document.getElementById('markdownToolbar').addEventListener('click', (e) => {
        const toggle = e.target.closest('.md-dropdown-toggle');
        if (toggle) {
            toggleDropdown(toggle.closest('.md-dropdown'));
            return;
        }

        const item = e.target.closest('.md-dropdown-item');
        if (item) {
            const wrap = item.closest('.md-dropdown');
            if (item.dataset.lang !== undefined) {
                insertCodeBlock(item.dataset.lang);
            } else if (item.dataset.action) {
                applyMarkdown(item.dataset.action);
            }
            closeDropdown(wrap);
            return;
        }

        const btn = e.target.closest('.md-btn');
        if (!btn) return;
        const action = btn.dataset.action;
        if (action === 'undo') { undo(); return; }
        if (action === 'redo') { redo(); return; }
        applyMarkdown(action);
    });

    // 点击工具栏外时收起下拉
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.md-dropdown')) closeAllToolbarDropdowns();
    });

    // 双击右侧预览 → 定位到左侧对应编辑位置
    document.getElementById('preview').addEventListener('dblclick', (e) => {
        const block = e.target.closest('[data-offset]');
        if (!block) return;
        const offset = Number(block.dataset.offset);
        if (Number.isNaN(offset)) return;
        const ta = contentTextarea();
        ta.focus({ preventScroll: true });
        ta.setSelectionRange(offset, offset);
        scrollToOffset(ta, offset);
    });

    // 目录：点击标题跳转到预览对应位置
    document.getElementById('tocList').addEventListener('click', (e) => {
        const item = e.target.closest('.toc-item');
        if (!item) return;
        jumpToHeading(Number(item.dataset.index));
    });

    const id = new URLSearchParams(window.location.search).get('id');
    loadTopics().then(() => {
        if (id) {
            editingId = id;
            loadForEdit(id);
        } else {
            updatePreview();
        }
    });

    document.getElementById('postForm').addEventListener('submit', handleSubmit);
    document.getElementById('draftBtn').addEventListener('click', () => savePost('draft'));

    // 单行输入框内按回车不提交表单（避免误提交，多行 textarea 不受影响）
    document.getElementById('postForm').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && e.target.tagName === 'INPUT') {
            e.preventDefault();
        }
    });

    // ===== 插入图片弹窗 =====
    const imageModal = document.getElementById('imageModal');
    document.getElementById('imageModalClose').addEventListener('click', closeImageModal);
    imageModal.addEventListener('click', (e) => {
        if (e.target === imageModal) closeImageModal();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !imageModal.hidden) closeImageModal();
    });

    // 上传本地图片
    document.getElementById('imageUploadBtn').addEventListener('click', () => {
        document.getElementById('imageFileInput').click();
    });
    document.getElementById('imageFileInput').addEventListener('change', async (e) => {
        const file = e.target.files && e.target.files[0];
        if (!file) return;
        try {
            const url = await uploadImage(file);
            insertImageMarkdown(url);
            showToast('图片上传成功');
        } catch (err) {
            showToast(err.message || '图片上传失败', 'error');
        } finally {
            e.target.value = '';
        }
    });

    // 使用图片链接
    document.getElementById('imageUrlConfirmBtn').addEventListener('click', () => {
        const url = document.getElementById('imageUrlInput').value.trim();
        if (!url) {
            showToast('请输入图片链接', 'error');
            return;
        }
        insertImageMarkdown(url);
    });
    document.getElementById('imageUrlInput').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            document.getElementById('imageUrlConfirmBtn').click();
        }
    });

    initResizer();
});

async function apiRequest(url, method = 'GET', body = null) {
    const options = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) options.body = JSON.stringify(body);

    const response = await fetch(url, options);
    if (response.status === 401) {
        window.location.href = '/login';
        throw new Error('未登录');
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
}

// 加载专栏列表并填充下拉框
async function loadTopics() {
    try {
        const data = await apiRequest(`${API_BASE}/topics`);
        if (data.success) topicsData = data.topics || [];
    } catch (e) {
        topicsData = [];
    }
    populateTopicSelect('');
}

// 填充专栏下拉框（selected 为当前值，若不在列表内则额外补一个选项）
function populateTopicSelect(selected) {
    const select = document.getElementById('topic');
    if (!select) return;
    let html = '<option value="">无专栏</option>';
    topicsData.forEach(t => {
        html += `<option value="${escapeHtml(t.name)}">${escapeHtml(t.name)}</option>`;
    });
    if (selected && !topicsData.some(t => t.name === selected)) {
        html += `<option value="${escapeHtml(selected)}">${escapeHtml(selected)}</option>`;
    }
    select.innerHTML = html;
    select.value = selected || '';
}

// 刷新右侧预览
function updatePreview() {
    const text = document.getElementById('content').value;
    const preview = document.getElementById('preview');

    updateEditorHighlight(text);

    if (!text.trim()) {
        preview.innerHTML = '<p class="empty-preview">暂无内容，开始输入以预览效果…</p>';
        updateToc();
        return;
    }
    renderMarkdownInto(preview, text);
    updateToc();
}

// 根据预览中渲染出的标题，重建左侧目录
function updateToc() {
    const tocList = document.getElementById('tocList');
    const preview = document.getElementById('preview');
    if (!tocList || !preview) return;

    const headings = preview.querySelectorAll('h1, h2, h3, h4, h5, h6');
    if (!headings.length) {
        tocList.innerHTML = '<p class="toc-empty">暂无标题</p>';
        return;
    }

    tocList.innerHTML = Array.from(headings).map((h, i) => {
        const level = parseInt(h.tagName.slice(1), 10);
        const text = h.textContent.trim();
        return `<button type="button" class="toc-item" data-index="${i}" style="padding-left:${10 + (level - 1) * 14}px">${escapeHtml(text)}</button>`;
    }).join('');
}

// 点击目录项：预览滚动到对应标题，并同步滚动左侧编辑区到源文本对应位置
function jumpToHeading(index) {
    const preview = document.getElementById('preview');
    if (!preview) return;
    const headings = preview.querySelectorAll('h1, h2, h3, h4, h5, h6');
    const heading = headings[index];
    if (!heading) return;

    const top = heading.getBoundingClientRect().top - preview.getBoundingClientRect().top + preview.scrollTop;
    preview.scrollTo({ top: Math.max(0, top - 8), behavior: 'smooth' });

    // 左侧编辑区：定位到该标题在源文本中的字符偏移
    const block = heading.closest('[data-offset]');
    if (!block) return;
    const offset = Number(block.dataset.offset);
    if (Number.isNaN(offset)) return;
    const ta = contentTextarea();
    ta.focus({ preventScroll: true });
    ta.setSelectionRange(offset, offset);
    scrollToOffset(ta, offset);
}

// 工具栏动作定义
const TOOLBAR_ACTIONS = {
    bold:      { prefix: '**', suffix: '**', placeholder: '加粗文本' },
    italic:    { prefix: '*',  suffix: '*',  placeholder: '斜体文本' },
    strike:    { prefix: '~~', suffix: '~~', placeholder: '删除线文本' },
    heading:   { prefix: '## ', suffix: '', placeholder: '标题', block: true },
    quote:     { prefix: '> ',  suffix: '', placeholder: '引用内容', block: true },
    ul:        { prefix: '- ',  suffix: '', placeholder: '列表项', block: true },
    ol:        { prefix: '1. ', suffix: '', placeholder: '列表项', block: true },
    code:      { prefix: '`',  suffix: '`',  placeholder: '代码' },
    codeblock: { prefix: '```\n', suffix: '\n```', placeholder: '代码块' },
    link:      { type: 'link',  placeholder: '链接文字' },
    image:     { type: 'image', placeholder: '图片描述' }
};

// 在光标处插入 / 包裹选中文本（支持再次点击取消）
function applyMarkdown(actionName) {
    const action = TOOLBAR_ACTIONS[actionName];
    if (!action) return;

    const ta = document.getElementById('content');
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const selected = ta.value.slice(start, end);

    // 链接：弹窗获取地址；图片：打开插入图片弹窗（支持本地 / 链接）
    if (action.type === 'link' || action.type === 'image') {
        if (action.type === 'link') {
            const url = prompt('请输入链接地址：', 'https://');
            if (url === null) return; // 用户取消
            const text = selected || action.placeholder || '';
            pushUndoState();
            ta.value = ta.value.slice(0, start) + '[' + text + '](' + url + ')' + ta.value.slice(end);
            ta.setSelectionRange(start + 1, start + 1 + text.length);
            ta.focus({ preventScroll: true });
            updatePreview();
        } else {
            openImageModal(start, end, selected);
        }
        return;
    }

    pushUndoState();

    if (action.block) {
        toggleBlock(ta, start, end, action.prefix, action.placeholder);
    } else {
        toggleInline(ta, start, end, action.prefix, action.suffix, action.placeholder);
    }

    ta.focus({ preventScroll: true });
    updatePreview();
}

// 工具栏下拉（列表 / 代码块）相关
function closeAllToolbarDropdowns() {
    document.querySelectorAll('.md-dropdown.open').forEach((d) => {
        d.classList.remove('open');
        const menu = d.querySelector('.md-dropdown-menu');
        if (menu) menu.hidden = true;
    });
}

function toggleDropdown(wrap) {
    if (!wrap) return;
    const menu = wrap.querySelector('.md-dropdown-menu');
    const isOpen = wrap.classList.contains('open');
    closeAllToolbarDropdowns();
    if (!isOpen) {
        wrap.classList.add('open');
        if (menu) menu.hidden = false;
    }
}

function closeDropdown(wrap) {
    if (!wrap) return;
    wrap.classList.remove('open');
    const menu = wrap.querySelector('.md-dropdown-menu');
    if (menu) menu.hidden = true;
}

// 插入带语言标记的代码块
function insertCodeBlock(lang) {
    const ta = contentTextarea();
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const selected = ta.value.slice(start, end);
    const prefix = lang ? '```' + lang + '\n' : '```\n';
    const suffix = '\n```';
    pushUndoState();
    const text = selected || '代码';
    ta.value = ta.value.slice(0, start) + prefix + text + suffix + ta.value.slice(end);
    ta.setSelectionRange(start + prefix.length, start + prefix.length + text.length);
    ta.focus({ preventScroll: true });
    updatePreview();
}

// 行内格式（加粗/斜体/删除线/行内代码/代码块）：已包裹则取消，否则包裹
function toggleInline(ta, start, end, prefix, suffix, placeholder) {
    const selected = ta.value.slice(start, end);

    // 选区整体已含前后标记（例如选中了 **加粗**）
    if (selected.length >= prefix.length + suffix.length
        && selected.startsWith(prefix) && selected.endsWith(suffix)) {
        const inner = selected.slice(prefix.length, selected.length - suffix.length);
        ta.value = ta.value.slice(0, start) + inner + ta.value.slice(end);
        ta.setSelectionRange(start, start + inner.length);
        return;
    }

    // 标记在选区外（例如只选中了内部文字）
    const before = ta.value.slice(Math.max(0, start - prefix.length), start);
    const after = ta.value.slice(end, end + suffix.length);
    if (selected && before === prefix && after === suffix) {
        ta.value = ta.value.slice(0, start - prefix.length) + selected + ta.value.slice(end + suffix.length);
        ta.setSelectionRange(start - prefix.length, start - prefix.length + selected.length);
        return;
    }

    // 否则包裹
    const text = selected || placeholder || '';
    ta.value = ta.value.slice(0, start) + prefix + text + suffix + ta.value.slice(end);
    ta.setSelectionRange(start + prefix.length, start + prefix.length + text.length);
}

// 块级（标题/引用/无序/有序列表）：行首已有前缀则取消，否则添加
function toggleBlock(ta, start, end, prefix, placeholder) {
    const lineStart = ta.value.lastIndexOf('\n', start - 1) + 1;
    const nextNewline = ta.value.indexOf('\n', start);
    const lineEnd = nextNewline === -1 ? ta.value.length : nextNewline;
    const lineText = ta.value.slice(lineStart, lineEnd);

    if (lineText.startsWith(prefix)) {
        const inner = lineText.slice(prefix.length);
        ta.value = ta.value.slice(0, lineStart) + inner + ta.value.slice(lineEnd);
        ta.setSelectionRange(lineStart, lineStart + inner.length);
    } else {
        const content = lineText.trim() ? lineText : placeholder;
        ta.value = ta.value.slice(0, lineStart) + prefix + content + ta.value.slice(lineEnd);
        ta.setSelectionRange(lineStart + prefix.length, lineStart + prefix.length + content.length);
    }
}

// 打开插入图片弹窗，记录插入位置与选中文本
function openImageModal(start, end, selected) {
    imageInsertContext = { start, end, selected };
    document.getElementById('imageUrlInput').value = '';
    document.getElementById('imageModal').hidden = false;
    document.getElementById('imageUrlInput').focus();
}

function closeImageModal() {
    document.getElementById('imageModal').hidden = true;
    imageInsertContext = null;
}

// 将图片 Markdown 插入到之前记录的光标位置
function insertImageMarkdown(url) {
    if (!imageInsertContext) return;
    const { start, end, selected } = imageInsertContext;
    const alt = selected || '图片';
    const ta = document.getElementById('content');
    const markdown = `![${alt}](${url})`;

    pushUndoState();
    ta.value = ta.value.slice(0, start) + markdown + ta.value.slice(end);
    const caret = start + markdown.length;
    ta.focus({ preventScroll: true });
    ta.setSelectionRange(caret, caret);
    updatePreview();
    closeImageModal();
}

// 上传图片到服务器，返回可访问的 URL
async function uploadImage(file) {
    const formData = new FormData();
    formData.append('image', file);

    const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: formData });
    if (!res.ok) {
        let msg = `HTTP ${res.status}`;
        try {
            const data = await res.json();
            if (data && data.message) msg = data.message;
        } catch (e) { /* 忽略解析错误 */ }
        throw new Error(msg);
    }
    const data = await res.json();
    if (!data.success) throw new Error(data.message || '上传失败');
    return data.url;
}

async function loadForEdit(id) {
    try {
        const data = await apiRequest(`${API_BASE}/posts/${id}`);
        if (!data.success) {
            showToast(data.message || '文章不存在', 'error');
            return;
        }
        const post = data.post;
        document.getElementById('editorTitle').textContent = '编辑文章';
        document.getElementById('title').value = post.title;
        document.getElementById('author').value = post.author || '';
        populateTopicSelect(post.topic || '');
        document.getElementById('theme').value = post.theme || '';
        document.getElementById('summary').value = post.summary || '';
        document.getElementById('content').value = post.content || '';
        document.getElementById('submitBtn').textContent = '发布';
        document.title = `编辑 · ${post.title}`;
        updatePreview();
    } catch (e) {
        showToast('加载文章失败，请稍后重试', 'error');
    }
}

async function handleSubmit(e) {
    e.preventDefault();
    await savePost('published');
}

// 保存文章（status 为 published 发布 / draft 草稿）
async function savePost(status) {
    let title = document.getElementById('title').value.trim();
    const author = document.getElementById('author').value.trim() || '匿名';
    const topic = document.getElementById('topic').value.trim();
    const theme = document.getElementById('theme').value.trim();
    const summary = document.getElementById('summary').value.trim();
    const content = document.getElementById('content').value;

    const isDraft = status === 'draft';

    if (!title) {
        if (!isDraft) {
            showToast('请输入文章标题', 'error');
            return;
        }
        title = '无标题草稿';
    }

    const savingBtn = isDraft ? document.getElementById('draftBtn') : document.getElementById('submitBtn');
    const originalText = savingBtn.textContent;
    savingBtn.disabled = true;
    savingBtn.textContent = isDraft ? '保存中...' : '提交中...';

    try {
        const url = editingId ? `${API_BASE}/posts/${editingId}` : `${API_BASE}/posts`;
        const method = editingId ? 'PUT' : 'POST';
        const data = await apiRequest(url, method, { title, author, topic, theme, summary, content, status });

        if (data.success) {
            if (editingId == null && data.id) editingId = data.id;

            if (isDraft) {
                showToast('📝 草稿已保存');
                document.getElementById('editorTitle').textContent = '编辑文章';
                document.getElementById('submitBtn').textContent = '发布';
                document.title = `编辑 · ${title}`;
                savingBtn.disabled = false;
                savingBtn.textContent = originalText;
            } else {
                showToast('✅ 文章发布成功');
                setTimeout(() => {
                    window.location.href = `/post?id=${editingId || data.id}`;
                }, 500);
            }
        } else {
            showToast(data.message || '操作失败', 'error');
            savingBtn.disabled = false;
            savingBtn.textContent = originalText;
        }
    } catch (err) {
        showToast('提交失败，请检查服务是否运行', 'error');
        savingBtn.disabled = false;
        savingBtn.textContent = originalText;
    }
}

// 左右分栏拖动调整宽度
function initResizer() {
    const editor = document.querySelector('.markdown-editor');
    const input = document.querySelector('.markdown-editor-input');
    const resizer = document.getElementById('markdownResizer');
    if (!editor || !input || !resizer) return;

    let dragging = false;

    resizer.addEventListener('mousedown', (e) => {
        dragging = true;
        resizer.classList.add('dragging');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!dragging) return;
        const rect = editor.getBoundingClientRect();
        // 从输入区左边缘（目录右侧）起算，避免目录宽度导致拖拽瞬间跳变
        const inputLeft = input.getBoundingClientRect().left;
        const pct = ((e.clientX - inputLeft) / rect.width) * 100;
        input.style.flexBasis = Math.min(80, Math.max(20, pct)) + '%';
    });

    document.addEventListener('mouseup', () => {
        if (!dragging) return;
        dragging = false;
        resizer.classList.remove('dragging');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
    });
}

// ===== 编辑器语法高亮（左侧代码框叠加层） =====
function highlightLayerEl() {
    return document.getElementById('highlightLayer');
}

// 将 Markdown 源码中的围栏代码块按语言高亮，其余文本原样转义，
// 保证输出与输入逐字符对齐（供透明 textarea 下方的叠加层使用）。
function highlightMarkdown(text) {
    if (!text) return '';
    const re = /(```[ \t]*([^\n`]*)[ \t]*\r?\n)([\s\S]*?)(```[ \t]*)(?=\r?\n|$)/g;
    let html = '';
    let last = 0;
    let m;
    while ((m = re.exec(text)) !== null) {
        html += escapeHtml(text.slice(last, m.index));
        const lang = (m[2] || '').trim();
        html += escapeHtml(m[1]);
        html += '<span class="hljs-code-block">' + highlightCode(m[3], lang) + '</span>';
        html += escapeHtml(m[4]);
        last = m.index + m[0].length;
    }
    html += escapeHtml(text.slice(last));
    return html;
}

function highlightCode(code, lang) {
    if (!code) return '';
    if (lang && window.hljs && window.hljs.getLanguage(lang)) {
        try {
            return window.hljs.highlight(code, { language: lang }).value;
        } catch (e) {
            return escapeHtml(code);
        }
    }
    return escapeHtml(code);
}

function updateEditorHighlight(text) {
    const layer = highlightLayerEl();
    const ta = contentTextarea();
    if (!layer) return;
    const pre = layer.parentElement;

    // 清除上次的底部补偿
    if (pre) pre.style.paddingBottom = '';

    const isEmpty = (text == null || text === '');
    layer.innerHTML = isEmpty ? '' : highlightMarkdown(text);

    // textarea 会把末尾换行渲染成额外一行，而 <pre> 会折叠尾部换行导致叠加层少一行；
    // 不同浏览器对尾部换行的处理还不一致，这里直接用两者 scrollHeight 的差值补底部内边距，
    // 保证叠加层与输入框的总高度完全一致，滚动同步和点击定位才不会错位。
    if (pre && ta && !isEmpty) {
        const diff = ta.scrollHeight - pre.scrollHeight;
        if (diff > 0) {
            const basePad = parseFloat(getComputedStyle(pre).paddingBottom) || 0;
            pre.style.paddingBottom = (basePad + diff) + 'px';
        }
    }

    syncEditorScroll();
}

function syncEditorScroll() {
    const ta = contentTextarea();
    const layer = highlightLayerEl();
    if (!ta || !layer) return;
    const pre = layer.parentElement;
    if (!pre) return;
    pre.scrollTop = ta.scrollTop;
    pre.scrollLeft = ta.scrollLeft;
}

// Tab / Shift+Tab 对选区（或当前行）整体缩进、反缩进
function indentBlock(ta, start, end, outdent) {
    const value = ta.value;
    const lineStart = value.lastIndexOf('\n', start - 1) + 1;
    const lineEnd = value.indexOf('\n', end);
    const blockEnd = lineEnd === -1 ? value.length : lineEnd;
    const block = value.slice(lineStart, blockEnd);
    const lines = block.split('\n');

    let newBlock;
    if (outdent) {
        newBlock = lines.map((line) => {
            let i = 0;
            while (i < line.length && i < TAB_INDENT.length && line[i] === ' ') i++;
            return line.slice(i);
        }).join('\n');
    } else {
        newBlock = lines.map((line) => TAB_INDENT + line).join('\n');
    }

    ta.value = value.slice(0, lineStart) + newBlock + value.slice(blockEnd);
    ta.setSelectionRange(lineStart, lineStart + newBlock.length);
}

// 判断光标是否位于围栏代码块（``` 之间）内
function isInsideCodeBlock(text, pos) {
    const before = text.slice(0, pos);
    const fences = before.match(/^```[ \t]*/gm) || [];
    return fences.length % 2 === 1;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
}

function showToast(message, type = 'success') {
    document.querySelectorAll('.toast').forEach(t => t.remove());

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = type === 'success'
        ? `<span>✓</span> ${escapeHtml(message)}`
        : `<span>✗</span> ${escapeHtml(message)}`;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'toastIn 0.25s ease-out reverse';
        setTimeout(() => toast.remove(), 250);
    }, 2500);
}
