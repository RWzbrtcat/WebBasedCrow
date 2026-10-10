// ============================================
// 题目编辑页（/daily/question）：新增题库题目；带 ?id=N 时为修改已有题目
// 依赖：daily-common.js（apiRequest / showToast / describeFetchError）
//       markdown.js（renderMarkdownInto，用于答案预览）
//       auth.js（导航显隐）
// ============================================

const questionState = {
    id: 0   // 0 表示新增；> 0 表示正在修改该题目
};

// ---------- 分类建议 ----------
// 复用题库接口拿分类列表，填进 <datalist> 做输入联想。
// 拿不到也不影响录入（分类是自由文本），所以失败只记录不打扰用户。
async function loadCategoryOptions() {
    const datalist = document.getElementById('categoryOptions');
    if (!datalist) return;
    try {
        const data = await apiRequest(`${DAILY_API}/questions?page=1&page_size=1&with_drafts=1`);
        datalist.innerHTML = (data.categories || [])
            .map((c) => `<option value="${escapeAttr(c.name)}"></option>`)
            .join('');
    } catch (e) {
        console.warn('[daily-question] 分类列表加载失败，忽略', e);
    }
}

// ---------- 表单读写 ----------

function fillForm(q) {
    document.getElementById('qCategory').value = q.category || '';
    document.getElementById('qTags').value = q.tags || '';
    document.getElementById('qDifficulty').value = String(q.difficulty || 2);
    document.getElementById('qStatus').value = String(q.status === 0 ? 0 : 1);
    document.getElementById('qQuestion').value = q.question || '';
    document.getElementById('qAnswer').value = q.answer || '';
}

function readForm() {
    return {
        category: document.getElementById('qCategory').value.trim(),
        tags: document.getElementById('qTags').value.trim(),
        difficulty: Number(document.getElementById('qDifficulty').value),
        question: document.getElementById('qQuestion').value,
        answer: document.getElementById('qAnswer').value,
        status: Number(document.getElementById('qStatus').value)
    };
}

function resetForm() {
    const form = document.getElementById('questionForm');
    if (form) form.reset();
    document.getElementById('qFormHint').textContent = '';
    hidePreview();
}

// ---------- 答案预览 ----------

function hidePreview() {
    const box = document.getElementById('answerPreview');
    const btn = document.getElementById('previewToggle');
    if (!box || !btn) return;
    box.hidden = true;
    btn.textContent = '预览';
    btn.setAttribute('aria-expanded', 'false');
}

function bindPreviewToggle() {
    const btn = document.getElementById('previewToggle');
    if (!btn) return;
    btn.addEventListener('click', () => {
        const box = document.getElementById('answerPreview');
        if (!box) return;

        if (!box.hidden) {
            hidePreview();
            return;
        }
        const text = document.getElementById('qAnswer').value.trim();
        if (!text) {
            showToast('答案还是空的，先写点内容', 'error');
            return;
        }
        renderMarkdownInto(box, text);
        box.hidden = false;
        btn.textContent = '收起预览';
        btn.setAttribute('aria-expanded', 'true');
    });
}

// ---------- 提交 ----------

async function submitQuestion(e) {
    e.preventDefault();

    const payload = readForm();
    if (!payload.category || !payload.question.trim() || !payload.answer.trim()) {
        showToast('分类、题干、答案都不能为空', 'error');
        return;
    }

    const btn = document.getElementById('qSaveBtn');
    const isEdit = questionState.id > 0;
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = '保存中...';

    try {
        const url = isEdit ? `${DAILY_API}/questions/${questionState.id}` : `${DAILY_API}/questions`;
        const data = await apiRequest(url, isEdit ? 'PUT' : 'POST', payload);
        if (!data.success) {
            showToast(data.message || '保存失败', 'error');
            return;
        }

        if (isEdit) {
            showToast('已保存');
            // 让用户在每日一题页看到改动效果
            setTimeout(() => { window.location.href = '/daily'; }, 500);
        } else {
            showToast('已添加');
            resetForm();
            document.getElementById('qFormHint').textContent = '已添加，可继续录入下一题';
            document.getElementById('qQuestion').focus();
        }
    } catch (err) {
        showToast(describeFetchError(err), 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

// ---------- 初始化 ----------

function applyEditMode(id, q) {
    questionState.id = id;
    document.title = `修改题目 #${id} · LazyCat's Blog`;
    document.getElementById('questionPageTitle').textContent = `修改题目 #${id}`;
    document.getElementById('qSaveBtn').textContent = '保存修改';
    document.getElementById('qFormHint').textContent = `正在编辑 #${id} · 保存后会回到每日一题页`;
    if (q) fillForm(q);
}

async function initQuestionPage() {
    bindPreviewToggle();

    const form = document.getElementById('questionForm');
    form.addEventListener('submit', submitQuestion);

    // 只要不是「新增」，就必须先把原题读出来再让用户改
    const rawId = new URLSearchParams(window.location.search).get('id');
    const id = Number(rawId || 0);

    loadCategoryOptions();   // 不阻塞，填不满也不影响录入

    if (!rawId) return;

    if (!Number.isInteger(id) || id <= 0) {
        showToast('题目 id 无效', 'error');
        return;
    }

    applyEditMode(id, null);
    try {
        const data = await apiRequest(`${DAILY_API}/questions/${id}`);
        if (!data.success) {
            showToast(data.message || '题目不存在', 'error');
            return;
        }
        fillForm(data);
    } catch (e) {
        showToast(describeFetchError(e), 'error');
    }
}

document.addEventListener('DOMContentLoaded', initQuestionPage);
