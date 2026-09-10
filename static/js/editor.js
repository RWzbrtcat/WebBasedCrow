// ============================================
// 编辑器页逻辑（新建 / 编辑文章）
// ============================================

const API_BASE = '/api';

// 编辑模式下的文章 id（null 表示新建）
let editingId = null;

document.addEventListener('DOMContentLoaded', () => {
    const contentInput = document.getElementById('content');

    // 输入时实时刷新预览
    contentInput.addEventListener('input', updatePreview);

    // 工具栏按钮
    document.getElementById('markdownToolbar').addEventListener('click', (e) => {
        const btn = e.target.closest('.md-btn');
        if (!btn) return;
        applyMarkdown(btn.dataset.action);
    });

    const id = new URLSearchParams(window.location.search).get('id');
    if (id) {
        editingId = id;
        loadForEdit(id);
    } else {
        updatePreview();
    }

    document.getElementById('postForm').addEventListener('submit', handleSubmit);
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

// 在光标处插入 / 包裹选中文本
function applyMarkdown(actionName) {
    const action = TOOLBAR_ACTIONS[actionName];
    if (!action) return;

    const ta = document.getElementById('content');
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const selected = ta.value.slice(start, end);

    let prefix = action.prefix || '';
    let suffix = action.suffix || '';

    // 链接 / 图片：弹窗获取地址
    if (action.type === 'link' || action.type === 'image') {
        const url = prompt('请输入链接地址：', 'https://');
        if (url === null) return; // 用户取消
        prefix = action.type === 'image' ? '![' : '[';
        suffix = '](' + url + ')';
    }

    const text = selected || action.placeholder || '';
    let selStart, selEnd;

    if (action.block) {
        // 块级：在光标所在行行首插入前缀
        const lineStart = ta.value.lastIndexOf('\n', start - 1) + 1;
        ta.value = ta.value.slice(0, lineStart) + prefix + text + suffix + ta.value.slice(end);
        selStart = lineStart + prefix.length;
        selEnd = selStart + text.length;
    } else {
        ta.value = ta.value.slice(0, start) + prefix + text + suffix + ta.value.slice(end);
        selStart = start + prefix.length;
        selEnd = selStart + text.length;
    }

    ta.focus();
    ta.setSelectionRange(selStart, selEnd);
    updatePreview();
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

    const title = document.getElementById('title').value.trim();
    const author = document.getElementById('author').value.trim() || '匿名';
    const content = document.getElementById('content').value;

    if (!title) {
        showToast('请输入文章标题', 'error');
        return;
    }

    const submitBtn = document.getElementById('submitBtn');
    submitBtn.disabled = true;
    submitBtn.textContent = '提交中...';

    try {
        const url = editingId ? `${API_BASE}/posts/${editingId}` : `${API_BASE}/posts`;
        const method = editingId ? 'PUT' : 'POST';
        const data = await apiRequest(url, method, { title, author, content });

        if (data.success) {
            showToast(editingId ? '✏️ 文章已保存' : '✅ 文章发布成功');
            setTimeout(() => {
                window.location.href = `/post?id=${editingId || data.id}`;
            }, 500);
        } else {
            showToast(data.message || '操作失败', 'error');
            submitBtn.disabled = false;
            submitBtn.textContent = editingId ? '保存' : '发布';
        }
    } catch (err) {
        showToast('提交失败，请检查服务是否运行', 'error');
        submitBtn.disabled = false;
        submitBtn.textContent = editingId ? '保存' : '发布';
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
