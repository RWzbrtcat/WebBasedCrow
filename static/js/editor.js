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

// 当前登录管理员的昵称（作者字段只读，自动填充）
let currentNickname = '';

// 保存/发布进行中标记：按钮与快捷键可能连续触发，需去重
let saving = false;

// Tab 键插入的缩进宽度（空格）
const TAB_INDENT = '    ';

// 代码块内的括号 / 引号配对表（与练习闯关页的代码编辑器保持一致的口径）
const CODE_PAIRS = { '(': ')', '[': ']', '{': '}', '"': '"', "'": "'" };
const CODE_CLOSERS = { ')': '(', ']': '[', '}': '{', '"': '"', "'": "'" };

// ===== 撤销 / 重做 =====
const MAX_HISTORY = 200;
let undoStack = [];
let redoStack = [];
let lastInputAt = 0; // 用于合并连续输入为一步

function contentTextarea() {
    return document.getElementById('content');
}

// 测量 textarea 中指定字符偏移所在的字符在内容区内的真实 Y 坐标。
// 开启自动换行后，源文本的一行可能折成多个可视行，不能再按「换行符数 × 行高」估算；
// 这里用一个与 textarea 同宽、同字体、同换行规则的隐藏镜像来测量。
function caretY(ta, offset) {
    const mirror = offsetMirror(ta);
    mirror.style.width = ta.clientWidth + 'px';

    mirror.textContent = ta.value.slice(0, offset);
    const marker = document.createElement('span');
    marker.textContent = String.fromCharCode(0x200B);
    mirror.appendChild(marker);

    const y = marker.getBoundingClientRect().top - mirror.getBoundingClientRect().top;
    marker.remove();
    return y;
}

// 滚动 textarea，使指定字符偏移所在的字符出现在可视区中间。
function scrollToOffset(ta, offset) {
    ta.scrollTop = Math.max(0, caretY(ta, offset) - ta.clientHeight / 2);
}

// 输入 / 插入内容后，把光标滚动到可视区内（向上或向下只滚到刚好露出光标）。
// 原生自动滚动只覆盖了普通输入，程序化插入（列表/代码块回车、Tab 缩进、工具栏等）
// 直接改写 value，setSelectionRange 又不会可靠地把光标滚进可视区，这里手动补齐。
function scrollCaretIntoView(ta) {
    if (!ta || ta !== document.activeElement) return;
    if (ta.scrollHeight <= ta.clientHeight) return; // 内容未超出可视区，无需滚动
    const caret = ta.selectionEnd;
    if (caret == null) return;

    const y = caretY(ta, caret);
    const margin = 24; // 距底部留余量，避免光标紧贴边缘
    if (y < ta.scrollTop) {
        ta.scrollTop = Math.max(0, y - margin);
    } else if (y > ta.scrollTop + ta.clientHeight - margin) {
        ta.scrollTop = y - ta.clientHeight + margin;
    }
    syncEditorScroll();
}

// 惰性创建测量用镜像层，样式与 textarea 完全一致（含自动换行规则）
function offsetMirror(ta) {
    if (ta._offsetMirror && ta._offsetMirror.isConnected) return ta._offsetMirror;
    const style = getComputedStyle(ta);
    const mirror = document.createElement('div');
    mirror.style.cssText = 'position:absolute;top:0;left:0;visibility:hidden;white-space:pre-wrap;overflow-wrap:break-word;box-sizing:border-box;margin:0;border:0;pointer-events:none;';
    mirror.style.fontFamily = style.fontFamily;
    mirror.style.fontSize = style.fontSize;
    mirror.style.fontWeight = style.fontWeight;
    mirror.style.fontStyle = style.fontStyle;
    mirror.style.letterSpacing = style.letterSpacing;
    mirror.style.lineHeight = style.lineHeight;
    mirror.style.tabSize = style.tabSize;
    mirror.style.padding = style.padding;
    document.body.appendChild(mirror);
    ta._offsetMirror = mirror;
    return mirror;
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

    // 获取当前登录管理员的昵称，用于只读作者字段
    loadCurrentAuthor();

    // 输入时实时刷新预览
    contentInput.addEventListener('input', updatePreview);

    // 点击 / 用方向键、Home、End、翻页移动光标后，预览也跟到对应位置。
    // 用 setTimeout 而不是 rAF 调度：只等浏览器把新的 selection 落定，不需要渲染帧；
    // rAF 在后台标签页 / 不渲染的文档里会停摆，跟随就再也不触发了。
    const followCaret = () => { setTimeout(syncPreviewToCaret, 0); };
    contentInput.addEventListener('click', followCaret);
    contentInput.addEventListener('keyup', (e) => {
        const k = e.key;
        if (k.startsWith('Arrow') || k === 'Home' || k === 'End' || k === 'PageUp' || k === 'PageDown') {
            followCaret();
        }
    });

    // 用户自己滚预览时让位一段时间，避免和光标跟随互相拉扯出「上下跳」。
    // ⚠️ 只认用户主动产生的事件（滚轮 / 触摸 / 在滚动条上按下），**不听 scroll**：
    // 编辑时 Chrome 的滚动锚定会为了保持可见内容不动而自动微调 scrollTop，
    // 那些 scroll 事件和用户滚动长得一模一样，一旦按 scroll 判定，让位期就会被
    // 无限续期，跟随彻底失效（内容一路跑出视口）。锚定改变的是可见位置以外的
    // 补偿量，本来也不该算作用户滚走。
    const previewEl = document.getElementById('preview');
    if (previewEl) {
        const markUserScroll = () => {
            cancelPreviewAnim();
            previewWrittenTop = null;
            previewUserScrollAt = Date.now();
        };
        previewEl.addEventListener('wheel', markUserScroll, { passive: true });
        previewEl.addEventListener('touchmove', markUserScroll, { passive: true });
        previewEl.addEventListener('pointerdown', markUserScroll, { passive: true });
    }

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

    // 代码块内的括号 / 引号判定（自动配对、跳过右半边、成对删除、括号间回车展开）。
    // 必须注册在下面「回车续接列表」之前：回车相关分支要抢先处理，
    // 处理不了时返回 false，再由后面的处理器接手。
    contentInput.addEventListener('keydown', (e) => {
        handleCodeBlockEditing(e);
    });

    // 列表回车自动续接：有序列表数字递增、无序列表保持标记
    contentInput.addEventListener('keydown', (e) => {
        // 前面「代码块括号判定」已经接管过（括号间展开、续接缩进），这里不要再插一次换行
        if (e.defaultPrevented) return;
        if (e.key !== 'Enter' || e.shiftKey || e.ctrlKey || e.metaKey || e.isComposing) return;
        const ta = e.target;
        const pos = ta.selectionStart;
        const value = ta.value;
        const lineStart = value.lastIndexOf('\n', pos - 1) + 1;
        const before = value.slice(lineStart, pos);

        // 代码块内回车（兜底）：括号间展开、行尾 { ( [ 多缩进一级这两类已由
        // handleCodeBlockEditing 先行处理，走到这里的情况只继承上一行缩进
        if (isInsideCodeBlock(value, pos)) {
            e.preventDefault();
            pushUndoState();
            const indent = before.match(/^[ \t]*/)[0];
            const insert = '\n' + indent;
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
            const wrap = toggle.closest('.md-dropdown');
            if (wrap && wrap.id === 'anchorDropdown') populateAnchorMenu();
            toggleDropdown(wrap);
            return;
        }

        const item = e.target.closest('.md-dropdown-item');
        if (item) {
            const wrap = item.closest('.md-dropdown');
            if (item.dataset.anchor !== undefined) {
                insertAnchorLink(item.dataset.anchor);
            } else if (item.dataset.lang !== undefined) {
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
        // 专注按钮等「无 data-action」的按钮由自己的监听处理，不走 Markdown 插入
        if (!action) return;
        if (action === 'undo') { undo(); return; }
        if (action === 'redo') { redo(); return; }
        if (action === 'import') { importMarkdown(); return; }
        if (action === 'export') { exportMarkdown(); return; }
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
        // 用户是「看着预览点」的，别让光标跟随反过来把预览滚走
        mutePreviewSync(400);
        const ta = contentTextarea();
        ta.focus({ preventScroll: true });
        ta.setSelectionRange(offset, offset);
        scrollToOffset(ta, offset);
    });

    // 预览中的内部链接：平滑滚动到对应标题（不触发原生 hash 跳转）
    bindInternalLinks(document.getElementById('preview'));

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

    // ===== 快捷键：正文内的格式动作 =====
    // 在 keydown 阶段接管（而不是 input 之后改文本），选区语义才和工具栏按钮一致：
    // 未选中时插入占位词并选中它，选中时包裹 / 取消包裹。
    contentInput.addEventListener('keydown', (e) => {
        if (!(e.ctrlKey || e.metaKey) || e.isComposing || e.keyCode === 229) return;
        const code = e.code || '';
        const shift = !!e.shiftKey;
        const alt = !!e.altKey;
        for (const b of SHORTCUT_BINDINGS) {
            if (b.code !== code) continue;
            if (b.shift !== undefined && b.shift !== shift) continue;
            if (b.alt !== undefined && b.alt !== alt) continue;
            e.preventDefault();
            b.run();
            return;
        }
    });

    // 工具按钮的 title 补上快捷键：只写一份在 SHORTCUTS 里，HTML 不手抄
    document.querySelectorAll('[data-shortcut]').forEach((el) => {
        const item = SHORTCUTS.find((s) => s.hint === el.dataset.shortcut);
        if (!item) return;
        const combo = item.keys.join(IS_MAC ? '' : '+');
        const base = el.getAttribute('title');
        el.title = base ? `${base}（${combo}）` : combo;
    });

    // 面板入口：按钮 / 关闭 / 点遮罩 / Ctrl+/ / Esc
    const shortcutBtn = document.getElementById('shortcutBtn');
    const shortcutModal = document.getElementById('shortcutModal');
    if (shortcutBtn) shortcutBtn.addEventListener('click', () => openShortcutPanel());
    const shortcutClose = document.getElementById('shortcutClose');
    if (shortcutClose) shortcutClose.addEventListener('click', closeShortcutPanel);
    if (shortcutModal) {
        shortcutModal.addEventListener('click', (e) => {
            if (e.target === shortcutModal) closeShortcutPanel();
        });
        // 面板内只有「面板本体」「关闭按钮」两个落点，Tab 在两处循环即可，
        // 不让焦点跑到背后的表单里
        shortcutModal.addEventListener('keydown', (e) => {
            if (e.key !== 'Tab') return;
            e.preventDefault();
            const dialog = shortcutModal.querySelector('.shortcut-modal');
            const next = document.activeElement === shortcutClose ? dialog : shortcutClose;
            if (next) next.focus({ preventScroll: true });
        });
    }
    // 焦点不在正文（比如在标题框里）时也能用 Ctrl+/ 打开
    document.addEventListener('keydown', (e) => {
        if (!(e.ctrlKey || e.metaKey) || e.isComposing) return;
        if ((e.code || '') !== 'Slash') return;
        if (e.target === contentInput || isShortcutPanelOpen()) return;
        e.preventDefault();
        openShortcutPanel();
    });
    // Esc 关面板。注册在「专注模式」的 Esc 之前，并用 stopImmediatePropagation
    // 吃掉这一次按键，否则同一个 Esc 会顺手把专注模式也退掉。
    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Escape' || !isShortcutPanelOpen()) return;
        closeShortcutPanel();
        e.preventDefault();
        e.stopImmediatePropagation();
    });

    // ===== 专注模式：收起导航与字段行，把整屏高度让给正文 =====
    const focusBtn = document.getElementById('focusToggle');
    function setFocusMode(on) {
        document.body.classList.toggle('editor-focus', on);
        if (focusBtn) {
            focusBtn.setAttribute('aria-pressed', on ? 'true' : 'false');
            focusBtn.textContent = on ? '退出专注' : '专注';
        }
    }
    if (focusBtn) {
        focusBtn.addEventListener('click', () => {
            setFocusMode(!document.body.classList.contains('editor-focus'));
        });
    }
    document.addEventListener('keydown', (e) => {
        // 弹窗打开时 Esc 优先关弹窗（上面的监听已处理），这里只在专注态下响应
        if (e.key === 'Escape' && document.body.classList.contains('editor-focus')) {
            const modal = document.getElementById('imageModal');
            if (modal && !modal.hidden) return;
            setFocusMode(false);
        }
    });

    // 单行输入框内按回车不提交表单（避免误提交，多行 textarea 不受影响）
    document.getElementById('postForm').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && e.target.tagName === 'INPUT') {
            e.preventDefault();
        }
    });

    // 写作快捷键：Ctrl/⌘+S 存草稿、Ctrl/⌘+Enter 发布（发布走表单校验，标题为空会提示）
    document.addEventListener('keydown', (e) => {
        if (!(e.ctrlKey || e.metaKey) || e.altKey || e.shiftKey) return;
        const key = e.key.toLowerCase();
        if (key === 's') {
            e.preventDefault();
            savePost('draft');
        } else if (key === 'enter') {
            e.preventDefault();
            const form = document.getElementById('postForm');
            if (form && typeof form.requestSubmit === 'function') {
                form.requestSubmit();
            } else {
                savePost('published');
            }
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

    // 导入 Markdown 文件：读取本地文件并覆盖正文
    document.getElementById('markdownFileInput').addEventListener('change', (e) => {
        const input = e.target;
        const file = input.files && input.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = () => {
            const text = String(reader.result || '');
            const ta = contentTextarea();
            if (ta.value.trim() && !confirm('导入将覆盖当前正文内容，是否继续？')) {
                input.value = '';
                return;
            }
            pushUndoState();
            ta.value = text;
            ta.focus({ preventScroll: true });
            ta.setSelectionRange(0, 0);
            updatePreview();
            showToast('已导入 Markdown 文件');
            input.value = '';
        };
        reader.onerror = () => {
            showToast('读取文件失败', 'error');
            input.value = '';
        };
        reader.readAsText(file, 'utf-8');
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
    if (!response.ok) {
        let msg = `HTTP ${response.status}`;
        try {
            const data = await response.json();
            if (data && data.message) msg = data.message;
        } catch (e) { /* 忽略解析错误 */ }
        throw new Error(msg);
    }
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

// ===== 预览跟随：编辑位置 → 右侧对应位置 =====
// 左侧每次输入都会重建预览 DOM，若两侧滚动互不关联，写长文时光标在编辑区一路下移、
// 预览却停在原处，看到的就是「右边对应我编辑的那段内容一直在往下跑，最后跑出视口」。
// 这里用预览里已有的 data-offset 锚点把光标偏移换算成预览中的纵向位置，
// 并在相邻两块之间按字符比例插值 —— 比按滚动比例硬换算稳得多：
// 代码块、表格、图片在两侧的高度完全不成比例，比例法会持续漂移（表现为预览自己往下滑）。
let previewSyncMutedUntil = 0;

function mutePreviewSync(ms) {
    previewSyncMutedUntil = Date.now() + (ms || 300);
}

// 用户手动滚动预览后的「让位期」。
// 不设这段缓冲的话：用户往下看 → 敲一个字 → 光标跟随把预览拽回光标处 →
// 用户再滚 → 再被拽回，配合滚轮/触控板的惯性滚动，观感就是右侧一直在上下跳。
const PREVIEW_USER_SCROLL_GRACE = 2000;
let previewUserScrollAt = 0;

// 跟随滚动不做瞬跳，而是「持续逼近」。
// ⚠️ 关键：**不能在每次输入时重启动画**。按 200ms 动画、100ms 一个键算，
// 每个键都在动画只走到一半时把它 cancel 掉、从原地重新出发，预览就永远
// 到不了目标：左光标一路往下走、右侧只肯龟挪一小步，对应的内容于是被
// 顶出视口（就是「右边一直往下跑」）。改成只更新目标、由同一个循环
// 指数逼近，无论输入多密集都会收敛。
// 正在追的目标：{ pv, target, raf, timer, min, max }
let previewChase = null;

// 我们最后一次写进预览的 scrollTop（仅用于调试与断言，不参与滚动归属判断）
let previewWrittenTop = null;

function writePreviewTop(pv, v) {
    previewWrittenTop = v;
    pv.scrollTop = v;
}

function cancelPreviewAnim() {
    if (!previewChase) return;
    if (previewChase.raf) cancelAnimationFrame(previewChase.raf);
    if (previewChase.timer) clearTimeout(previewChase.timer);
    previewChase = null;
}

// 把预览持续推进到 top。已在追踪中则只换目标，不重启循环。
function animatePreviewScrollTo(pv, top) {
    const from = pv.scrollTop;
    if (!previewChase && Math.abs(top - from) < 1) return;

    if (previewChase) {
        previewChase.target = top;
        previewChase.min = Math.min(previewChase.min, top);
        previewChase.max = Math.max(previewChase.max, top);
    } else {
        const self = { pv: pv, target: top, raf: 0, timer: 0, min: Math.min(from, top), max: Math.max(from, top) };
        previewChase = self;
        const step = () => {
            if (previewChase !== self) return;   // 已被新一轮接管
            const cur = pv.scrollTop;
            const delta = self.target - cur;
            if (Math.abs(delta) < 1) {
                if (self.timer) clearTimeout(self.timer);
                self.timer = 0;
                self.raf = 0;
                previewChase = null;
                writePreviewTop(pv, self.target);
                return;
            }
            // 指数逼近：每帧走剩余距离的约 1/3，十来帧到位，帧稀疏也不会冲过头
            writePreviewTop(pv, cur + delta * 0.34);
            self.raf = requestAnimationFrame(step);
        };
        self.raf = requestAnimationFrame(step);

        // 看门狗：后台标签页 / 不渲染的文档里 rAF 可能一直不回调，
        // 没有它目标位置就永远落不了地（实测 30s 只跑 8 帧）。
        self.timer = setTimeout(() => {
            // ⚠️ 必须比对对象身份：目标每次更新都续期，但上一轮结束后来不及清的
            // 定时器不能把新一轮一起掐掉、把旧目标写回去。
            if (previewChase !== self) return;
            cancelPreviewAnim();
            writePreviewTop(pv, self.target);
        }, 320);
    }
}

// 元素相对预览内容顶部的偏移（预览自身就是滚动容器）
function previewTopOf(pv, pvTop, el) {
    return el.getBoundingClientRect().top - pvTop + pv.scrollTop;
}

// 源文本偏移 caret 在预览中对应的 Y 坐标
function previewYForOffset(pv, pvTop, caret) {
    const blocks = pv.querySelectorAll('[data-offset]');
    const n = blocks.length;
    if (!n) return null;
    if (n === 1) return previewTopOf(pv, pvTop, blocks[0]);

    // 二分找最后一个 offset <= caret 的块
    let lo = 0;
    let hi = n - 1;
    let idx = -1;
    while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        const off = Number(blocks[mid].dataset.offset);
        if (!Number.isNaN(off) && off <= caret) {
            idx = mid;
            lo = mid + 1;
        } else {
            hi = mid - 1;
        }
    }

    const a = idx >= 0 ? blocks[idx] : null;
    const b = blocks[idx + 1] || null;
    if (!a) return previewTopOf(pv, pvTop, blocks[0]);
    if (!b) return previewTopOf(pv, pvTop, a);

    const oa = Number(a.dataset.offset);
    const ob = Number(b.dataset.offset);
    const ya = previewTopOf(pv, pvTop, a);
    if (Number.isNaN(oa) || Number.isNaN(ob) || ob <= oa) return ya;
    const yb = previewTopOf(pv, pvTop, b);
    const r = Math.min(1, Math.max(0, (caret - oa) / (ob - oa)));
    return ya + (yb - ya) * r;
}

// 把预览滚到「光标所在内容」的位置。已在舒适区内则完全不动 ——
// 否则每敲一个字都微调一下滚动条，观感就是预览自己在往下跑。
function syncPreviewToCaret() {
    if (Date.now() < previewSyncMutedUntil) return;
    // 用户刚手动滚过预览 ⇒ 这一拍让给他，别把滚动位置抢回来
    if (Date.now() - previewUserScrollAt < PREVIEW_USER_SCROLL_GRACE) return;
    const ta = contentTextarea();
    const pv = document.getElementById('preview');
    if (!ta || !pv) return;
    // 只在真正编辑（textarea 有焦点）时跟随：加载文章时 value 赋值会让光标落到末尾，
    // 若不判断，打开一篇长文预览就会直接跳到底部。
    if (document.activeElement !== ta) return;

    const max = pv.scrollHeight - pv.clientHeight;
    if (max <= 0) return;
    const caret = ta.selectionEnd;
    if (caret == null) return;

    const pvTop = pv.getBoundingClientRect().top;
    const y = previewYForOffset(pv, pvTop, caret);
    if (y == null) return;

    const h = pv.clientHeight;
    // 判断用「这一轮追踪最终会停在哪里」，而不是追踪途中的瞬时位置：
    // 否则逼近过程中每次输入都判定为越界，目标会被反复改写成细微不同的值。
    const resting = previewChase && previewChase.pv === pv ? previewChase.target : pv.scrollTop;
    // 舒适区收窄到 28%~55%：重启问题解决后，频繁改目标是安全的，
    // 换来的是「跟着走」而不是「两百多像素一跳」。
    if (y >= resting + h * 0.28 && y <= resting + h * 0.55) return;

    // 让光标内容落在视口 38% 处
    const target = Math.max(0, Math.min(y - h * 0.38, max));
    animatePreviewScrollTo(pv, target);
}

// 刷新右侧预览
function updatePreview() {
    const text = document.getElementById('content').value;
    const preview = document.getElementById('preview');

    updateEditorHighlight(text);

    if (!text.trim()) {
        preview.innerHTML = '<p class="empty-preview">暂无内容，开始输入以预览效果…</p>';
    } else {
        renderMarkdownInto(preview, text);
    }
    updateToc();
    updateStats(text);
    scrollCaretIntoView(contentTextarea());
    syncPreviewToCaret();
}

// 更新左下角的行数 / 字数 / 词数统计
function updateStats(text) {
    const statsEl = document.getElementById('editorStats');
    if (!statsEl) return;

    const lines = text === '' ? 0 : text.split('\n').length;
    const chars = text.replace(/\s/g, '').length;
    const words = text.trim() === '' ? 0 : text.trim().split(/\s+/).length;

    statsEl.textContent = `行数 ${lines} · 字数 ${chars} · 词数 ${words}`;
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
        return `<button type="button" class="toc-item" data-index="${i}" title="${escapeHtml(text)}" style="padding-left:${10 + (level - 1) * 14}px">${escapeHtml(text)}</button>`;
    }).join('');
}

// 点击目录项：预览滚动到对应标题，并同步滚动左侧编辑区到源文本对应位置
function jumpToHeading(index) {
    const preview = document.getElementById('preview');
    if (!preview) return;
    const headings = preview.querySelectorAll('h1, h2, h3, h4, h5, h6');
    const heading = headings[index];
    if (!heading) return;

    // 平滑滚动期间别让「预览跟随光标」把它拽回去
    cancelPreviewAnim();
    mutePreviewSync(600);

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

// ===== 快捷键 =====
// 平台修饰键：Mac 显示 ⌘，其余显示 Ctrl（绑定逻辑两个键都接受）
const IS_MAC = /Mac|iPhone|iPad|iPod/.test(navigator.platform || navigator.userAgent || '');
const MOD = IS_MAC ? '⌘' : 'Ctrl';

// 面板数据 + 工具按钮 title 的唯一来源。hint 对应按钮的 data-shortcut。
const SHORTCUTS = [
    { group: '行内格式', label: '加粗', keys: [MOD, 'B'], hint: 'bold' },
    { group: '行内格式', label: '斜体', keys: [MOD, 'I'], hint: 'italic' },
    { group: '行内格式', label: '删除线', keys: [MOD, 'Shift', 'X'], hint: 'strike' },
    { group: '行内格式', label: '行内代码', keys: [MOD, 'E'], hint: 'code' },
    { group: '行内格式', label: '插入链接', keys: [MOD, 'K'], hint: 'link' },

    { group: '段落', label: '标题（一级 / 二级 / 三级）', keys: [MOD, 'Alt', '1 / 2 / 3'], hint: 'heading' },
    { group: '段落', label: '取消标题，回到正文', keys: [MOD, 'Alt', '0'] },
    { group: '段落', label: '引用', keys: [MOD, 'Shift', '.'], hint: 'quote' },
    { group: '段落', label: '无序列表', keys: [MOD, 'Shift', '8'], hint: 'ul' },
    { group: '段落', label: '有序列表', keys: [MOD, 'Shift', '7'], hint: 'ol' },

    { group: '编写与提交', label: '代码块', keys: [MOD, 'Shift', 'K'], hint: 'codeblock' },
    { group: '编写与提交', label: '保存草稿', keys: [MOD, 'S'] },
    { group: '编写与提交', label: '发布文章', keys: [MOD, 'Enter'] },
    { group: '编写与提交', label: '撤销 / 重做', keys: [MOD, 'Z / Y'] },
    { group: '编写与提交', label: '打开这个面板', keys: [MOD, '/'] }
];

// 按键绑定。⚠ 用 e.code（物理键）而不是 e.key：Shift+/ 在多数键盘上产出 '?'，
// 用 e.key 匹配会漏掉，且中文输入法状态下 e.key 不稳定。
// 同一 code 有多条时按数组顺序匹配，所以不带修饰键的必须显式写 shift: false。
const SHORTCUT_BINDINGS = [
    { code: 'KeyB', shift: false, alt: false, run: () => applyMarkdown('bold') },
    { code: 'KeyI', shift: false, alt: false, run: () => applyMarkdown('italic') },
    { code: 'KeyE', shift: false, alt: false, run: () => applyMarkdown('code') },
    { code: 'KeyK', shift: false, alt: false, run: () => applyMarkdown('link') },
    { code: 'KeyX', shift: true, alt: false, run: () => applyMarkdown('strike') },
    { code: 'KeyK', shift: true, alt: false, run: () => insertCodeBlock('') },
    { code: 'Digit7', shift: true, alt: false, run: () => applyMarkdown('ol') },
    { code: 'Digit8', shift: true, alt: false, run: () => applyMarkdown('ul') },
    { code: 'Period', shift: true, alt: false, run: () => applyMarkdown('quote') },
    { code: 'Digit0', alt: true, run: () => setHeadingLevel(0) },
    { code: 'Digit1', alt: true, run: () => setHeadingLevel(1) },
    { code: 'Digit2', alt: true, run: () => setHeadingLevel(2) },
    { code: 'Digit3', alt: true, run: () => setHeadingLevel(3) },
    // Ctrl+/ ：有的键盘要按 Shift 才打出 '/'，所以这一条不校验修饰键状态
    { code: 'Slash', run: () => openShortcutPanel() }
];

// ---------- 快捷键面板 ----------
function isShortcutPanelOpen() {
    const el = document.getElementById('shortcutModal');
    return !!el && !el.hidden;
}

function renderShortcutPanel() {
    const list = document.getElementById('shortcutList');
    if (!list) return;

    // 按 SHORTCUTS 里的 group 顺序分组（不另立分组表，改表即改面板）
    const groups = [];
    SHORTCUTS.forEach((s) => {
        let g = groups.find((x) => x.title === s.group);
        if (!g) {
            g = { title: s.group, items: [] };
            groups.push(g);
        }
        g.items.push(s);
    });

    list.innerHTML = groups.map((g) => `
        <section class="shortcut-group">
            <h4 class="shortcut-group-title">${escapeHtml(g.title)}</h4>
            ${g.items.map((it) => `
                <div class="shortcut-row">
                    <span class="shortcut-label">${escapeHtml(it.label)}</span>
                    <span class="shortcut-keys">${it.keys
                        .map((k, i) => (i ? '<span class="shortcut-plus">+</span>' : '') +
                            `<kbd class="shortcut-key">${escapeHtml(k)}</kbd>`)
                        .join('')}</span>
                </div>`).join('')}
        </section>`).join('');
}

function openShortcutPanel() {
    const el = document.getElementById('shortcutModal');
    if (!el || !el.hidden) return false;
    // 图片弹窗还开着就先收起，避免两层遮罩叠在一起
    const imageModal = document.getElementById('imageModal');
    if (imageModal && !imageModal.hidden) closeImageModal();
    renderShortcutPanel();
    el.hidden = false;
    // 内容超出时才挂底部渐隐（此时才有布局可测）
    const body = document.getElementById('shortcutList');
    if (body) el.querySelector('.shortcut-modal').classList.toggle('is-scrollable', body.scrollHeight - body.clientHeight > 1);
    const btn = document.getElementById('shortcutBtn');
    if (btn) btn.setAttribute('aria-expanded', 'true');
    // 聚焦面板本身：给键盘一个落点，又不至于让关闭按钮带上焦点环
    const dialog = el.querySelector('.shortcut-modal');
    if (dialog) dialog.focus({ preventScroll: true });
    return true;
}

function closeShortcutPanel() {
    const el = document.getElementById('shortcutModal');
    if (!el || el.hidden) return false;
    el.hidden = true;
    const btn = document.getElementById('shortcutBtn');
    if (btn) btn.setAttribute('aria-expanded', 'false');
    // 关掉后把焦点还给正文，顺手接着写
    const ta = contentTextarea();
    if (ta) ta.focus({ preventScroll: true });
    return true;
}

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
// 插入 Mermaid 代码块时给的示例（可直接渲染出图，方便在此基础上改）
const MERMAID_SAMPLE = [
    'flowchart LR',
    '    A[开始] --> B{条件判断}',
    '    B -->|是| C[执行操作]',
    '    B -->|否| D[跳过]',
    '    C --> E[结束]',
    '    D --> E'
].join('\n');

function insertCodeBlock(lang) {
    const ta = contentTextarea();
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const selected = ta.value.slice(start, end);
    const prefix = lang ? '```' + lang + '\n' : '```\n';
    const suffix = '\n```';
    pushUndoState();
    // Mermaid 给一段可直接渲染的示例，方便在此基础上改
    const text = selected || (lang === 'mermaid' ? MERMAID_SAMPLE : '代码');
    ta.value = ta.value.slice(0, start) + prefix + text + suffix + ta.value.slice(end);
    ta.setSelectionRange(start + prefix.length, start + prefix.length + text.length);
    ta.focus({ preventScroll: true });
    updatePreview();
}

// 填充「内部链接」下拉：列出预览中所有标题及其锚点
function populateAnchorMenu() {
    const menu = document.getElementById('anchorMenu');
    const preview = document.getElementById('preview');
    if (!menu) return;
    const headings = preview
        ? Array.from(preview.querySelectorAll('h1, h2, h3, h4, h5, h6')).filter((h) => h.id)
        : [];
    if (!headings.length) {
        menu.innerHTML = '<div class="md-dropdown-empty">当前没有标题</div>';
        return;
    }
    menu.innerHTML = headings.map((h) => {
        const level = parseInt(h.tagName.slice(1), 10);
        const label = '#'.repeat(level) + ' ' + h.textContent.trim();
        return `<button type="button" class="md-dropdown-item" data-anchor="${escapeHtml(h.id)}">${escapeHtml(label)}</button>`;
    }).join('');
}

// 在光标处插入指向某标题锚点的内部链接 [文字](#锚点)
function insertAnchorLink(slug) {
    const ta = contentTextarea();
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const selected = ta.value.slice(start, end);
    const text = selected || '跳转到此处';
    pushUndoState();
    const markdown = `[${text}](#${slug})`;
    ta.value = ta.value.slice(0, start) + markdown + ta.value.slice(end);
    ta.setSelectionRange(start + 1, start + 1 + text.length);
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

// 标题级别：0 = 回到正文（去掉 # 前缀），1~3 = 对应级别。
// 同一级别再按一次即取消；换级别时先剥掉旧前缀再加新的（否则会出现「# ## 标题」）。
function setHeadingLevel(level) {
    const ta = contentTextarea();
    if (!ta) return false;
    const value = ta.value;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const lineStart = value.lastIndexOf('\n', start - 1) + 1;
    const nextNewline = value.indexOf('\n', start);
    const lineEnd = nextNewline === -1 ? value.length : nextNewline;
    const lineText = value.slice(lineStart, lineEnd);

    const m = lineText.match(/^(#{1,6})[ \t]+/);
    const rest = m ? lineText.slice(m[0].length) : lineText;
    const newLine = (level === 0 || (m && m[1].length === level))
        ? rest
        : '#'.repeat(level) + ' ' + rest;
    if (newLine === lineText) return false;

    pushUndoState();
    ta.value = value.slice(0, lineStart) + newLine + value.slice(lineEnd);

    // 光标在正文内的相对位置保持不变（前缀长度会变）
    const prefixLen = newLine.length - rest.length;
    if (start === end) {
        const rel = Math.max(0, Math.min(start - lineStart - (m ? m[0].length : 0), rest.length));
        ta.setSelectionRange(lineStart + prefixLen + rel, lineStart + prefixLen + rel);
    } else {
        ta.setSelectionRange(lineStart, lineStart + newLine.length);
    }
    ta.focus({ preventScroll: true });
    updatePreview();
    return true;
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

// 打开本地文件选择框，导入 Markdown 文件
function importMarkdown() {
    document.getElementById('markdownFileInput').click();
}

// 将当前正文导出为 .md 文件（文件名取自标题）
function exportMarkdown() {
    const content = document.getElementById('content').value;
    if (!content.trim()) {
        showToast('正文内容为空，无法导出', 'error');
        return;
    }

    const title = document.getElementById('title').value.trim() || 'untitled';
    const filename = title.replace(/[\\/:*?"<>|]/g, '_') + '.md';

    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    showToast('已导出 Markdown 文件');
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

// 从登录态读取当前管理员的昵称，并填充只读作者字段
// （编辑模式会由 loadForEdit 用文章原作者覆盖，故仅当作者字段为空时填充）
async function loadCurrentAuthor() {
    try {
        const data = await apiRequest(`${API_BASE}/auth`);
        if (data && data.authed) {
            currentNickname = data.nickname || '';
            const authorInput = document.getElementById('author');
            if (authorInput && !authorInput.value) {
                authorInput.value = currentNickname;
            }
        }
    } catch (e) { /* 未登录或网络异常时忽略 */ }
}

async function loadForEdit(id) {
    try {
        const data = await apiRequest(`${API_BASE}/posts/${id}`);
        if (!data.success) {
            showToast(data.message || '文章不存在', 'error');
            return;
        }
        const post = data.post;
        document.getElementById('editorTitle').textContent = '编辑中';
        document.getElementById('title').value = post.title;
        document.getElementById('author').value = post.author || currentNickname || '';
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
    if (saving) return; // 按钮与快捷键可能连按，进行中直接忽略

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
    saving = true;
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
                document.getElementById('editorTitle').textContent = '编辑中';
                document.title = `编辑 · ${title}`;
                savingBtn.disabled = false;
                savingBtn.textContent = originalText;
                saving = false;
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
            saving = false;
        }
    } catch (err) {
        showToast(err.message || '提交失败，请检查服务是否运行', 'error');
        savingBtn.disabled = false;
        savingBtn.textContent = originalText;
        saving = false;
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

// Mermaid 不在 highlight.js 内置语言里，这里给一套轻量着色：
// 图表类型关键字 / 连接箭头 / 注释（%%），让代码块在编辑时也有反馈
// 三类 token 一次性扫出（注释 / 关键字 / 连接箭头），再逐段转义输出；
// 必须先分词后转义——否则 `-->` 会先变成 `--&gt;`，箭头就匹配不到了。
const MERMAID_TOKEN_RE = new RegExp([
    '(%%[^\\n]*)',
    '\\b(stateDiagram-v2|sequenceDiagram|classDiagram|flowchart|subgraph|erDiagram|gitgraph|mindmap|journey|gantt|graph|end|participant|actor|note|class|click|style|linkStyle|direction|TB|TD|BT|RL|LR)\\b',
    '(<<-->>|<<--|<-->>|-->>|-\\.->|->>|--o|--x|-->|==>|===|-\\.-|---)'
].join('|'), 'g');

function highlightMermaid(code) {
    let html = '';
    let last = 0;
    let m;
    MERMAID_TOKEN_RE.lastIndex = 0;
    while ((m = MERMAID_TOKEN_RE.exec(code)) !== null) {
        html += escapeHtml(code.slice(last, m.index));
        const cls = m[1] ? 'hljs-comment' : (m[2] ? 'hljs-keyword' : 'hljs-operator');
        html += `<span class="${cls}">${escapeHtml(m[0])}</span>`;
        last = m.index + m[0].length;
    }
    html += escapeHtml(code.slice(last));
    return html;
}

function highlightCode(code, lang) {
    if (!code) return '';
    if (lang === 'mermaid') return highlightMermaid(code);
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

// 标识符字符：用来判断「在已有标识符前插括号」这类情形
function isWordChar(ch) {
    return !!ch && /[A-Za-z0-9_$]/.test(ch);
}

// ===== 代码块内的括号 / 引号判定 =====// 只在围栏代码块内接管按键：正文里的圆括号、方括号是排版符号（「（一）」、
// [文本](url)），自动补全只会添乱。
// 返回 true 表示已处理（调用方无需再 preventDefault）。
function handleCodeBlockEditing(e) {
    const ta = e.target;
    if (!ta || ta.id !== 'content') return false;
    if (e.ctrlKey || e.metaKey || e.altKey || e.isComposing || e.keyCode === 229) return false;

    const key = e.key;
    const v = ta.value;
    const s = ta.selectionStart;
    const en = ta.selectionEnd;
    if (!isInsideCodeBlock(v, s)) return false;

    const prev = s > 0 ? v[s - 1] : '';
    const next = v[s] || '';

    // ① 成对括号 / 引号：删左半边时右半边一起删
    if (key === 'Backspace' && s === en && CODE_PAIRS[prev] && CODE_PAIRS[prev] === next) {
        e.preventDefault();
        pushUndoState();
        ta.value = v.slice(0, s - 1) + v.slice(s + 1);
        ta.setSelectionRange(s - 1, s - 1);
        updatePreview();
        return true;
    }

    // ② 回车：光标夹在成对括号中间 → 展开成三行（VS Code 招牌行为）
    //    行尾是 { ( [ → 比上一行多缩进一级
    if (key === 'Enter' && !e.shiftKey && s === en) {
        const lineStart = v.lastIndexOf('\n', s - 1) + 1;
        const before = v.slice(lineStart, s);
        const outer = (before.match(/^[ \t]*/) || [''])[0];

        // 引号之间回车不能展开（那是在字符串里换行），只有 () [] {} 才展开
        if (CODE_PAIRS[prev] && CODE_PAIRS[prev] === next && prev !== '"' && prev !== "'") {
            e.preventDefault();
            pushUndoState();
            const inner = outer + TAB_INDENT;
            ta.value = v.slice(0, s) + '\n' + inner + '\n' + outer + v.slice(s);
            const caret = s + 1 + inner.length;
            ta.setSelectionRange(caret, caret);
            updatePreview();
            return true;
        }
        if (/[\[({]\s*$/.test(before)) {
            e.preventDefault();
            pushUndoState();
            const insert = '\n' + outer + TAB_INDENT;
            ta.value = v.slice(0, s) + insert + v.slice(s);
            const caret = s + insert.length;
            ta.setSelectionRange(caret, caret);
            updatePreview();
            return true;
        }
        // 其余情况交回「继承上一行缩进」的原逻辑
        return false;
    }

    // ③ 行首位置输入 } → 反缩进一级（缩进不足一级时按实际宽度退，2 空格缩进也适用）
    if (key === '}' && s === en) {
        const lineStart = v.lastIndexOf('\n', s - 1) + 1;
        const before = v.slice(lineStart, s);
        if (before.length > 0 && /^[ \t]*$/.test(before)) {
            const remove = before.endsWith(TAB_INDENT)
                ? TAB_INDENT.length
                : (before.length % TAB_INDENT.length) || TAB_INDENT.length;
            e.preventDefault();
            pushUndoState();
            const caret = s - remove;
            ta.value = v.slice(0, caret) + '}' + v.slice(s);
            ta.setSelectionRange(caret + 1, caret + 1);
            updatePreview();
            return true;
        }
    }

    // ④ 右半边已经在光标后：跳过去，而不是再插一个
    if (CODE_CLOSERS[key] && s === en && next === key) {
        e.preventDefault();
        ta.setSelectionRange(s + 1, s + 1);
        return true;
    }

    if (!CODE_PAIRS[key]) return false;
    const close = CODE_PAIRS[key];
    const isQuote = key === '"' || key === "'";

    // ⑤ 有选区 → 用这一对包起来，选区落在中间，方便继续改写
    if (s !== en) {
        e.preventDefault();
        pushUndoState();
        const sel = v.slice(s, en);
        ta.value = v.slice(0, s) + key + sel + close + v.slice(en);
        ta.setSelectionRange(s + 1, en + 1);
        updatePreview();
        return true;
    }

    // ⑥ 没有选区 → 判断要不要补右半边
    //   · 引号：紧跟标识符 / 反斜杠 / 同种引号 → 这是撇号或转义引号，不补（don't、\"x）
    //   · 引号后紧跟标识符 → 不补（是在已有词前打引号）
    //   · 括号后紧跟标识符 → 只插左边，别把已有表达式挡在后面
    //   ⚠ 光标后已经是同类右括号时**照样补**：若这里也只插左边，用户想配平还得再敲一个
    //     `)`，而那个 `)` 会被上面的「跳过已存在的右半边」吃掉 —— 变成永远配不平的死胡同。
    let autoClose = true;
    if (isQuote) {
        if (isWordChar(prev) || prev === '\\' || prev === key) autoClose = false;
        if (isWordChar(next)) autoClose = false;
    } else if (isWordChar(next)) {
        autoClose = false;
    }

    e.preventDefault();
    pushUndoState();
    ta.value = v.slice(0, s) + key + (autoClose ? close : '') + v.slice(s);
    ta.setSelectionRange(s + 1, s + 1);
    updatePreview();
    return true;
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
