// ============================================
// 编辑器页逻辑（新建 / 编辑文章）
// ============================================

const API_BASE = '/api';

// 编辑模式下的文章 id（null 表示新建）
let editingId = null;

// 插入图片时的光标 / 选中上下文
let imageInsertContext = null;

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

    // 工具栏按钮
    document.getElementById('markdownToolbar').addEventListener('click', (e) => {
        const btn = e.target.closest('.md-btn');
        if (!btn) return;
        const action = btn.dataset.action;
        if (action === 'undo') { undo(); return; }
        if (action === 'redo') { redo(); return; }
        applyMarkdown(action);
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

    const id = new URLSearchParams(window.location.search).get('id');
    if (id) {
        editingId = id;
        loadForEdit(id);
    } else {
        updatePreview();
    }

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
});

async function apiRequest(url, method = 'GET', body = null) {
    const options = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) options.body = JSON.stringify(body);

    const response = await fetch(url, options);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
}

// 刷新右侧预览
function updatePreview() {
    const text = document.getElementById('content').value;
    const preview = document.getElementById('preview');

    if (!text.trim()) {
        preview.innerHTML = '<p class="empty-preview">暂无内容，开始输入以预览效果…</p>';
        return;
    }
    renderMarkdownInto(preview, text);
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
        document.getElementById('topic').value = post.topic || '';
        document.getElementById('summary').value = post.summary || '';
        document.getElementById('content').value = post.content || '';
        document.getElementById('submitBtn').textContent = '保存';
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
        const data = await apiRequest(url, method, { title, author, topic, summary, content, status });

        if (data.success) {
            if (editingId == null && data.id) editingId = data.id;

            if (isDraft) {
                showToast('📝 草稿已保存');
                document.getElementById('editorTitle').textContent = '编辑文章';
                document.getElementById('submitBtn').textContent = '保存';
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
