// ============================================
// 前端主逻辑：与 C++ Crow 后端通信
// ============================================

// API 根路径（因为前端和后端同域，用相对路径即可）
const API_BASE = '/api';

// 当前筛选状态：all | pending | completed
let currentFilter = 'all';

// 页面加载完成后执行初始化
document.addEventListener('DOMContentLoaded', () => {
    loadTasks();            // 首次加载任务列表
    setupEventListeners();  // 绑定事件
});

// ============================================
// 事件监听绑定
// ============================================
function setupEventListeners() {
    // 新建任务表单提交
    document.getElementById('taskForm').addEventListener('submit', handleAddTask);

    // 编辑任务表单提交
    document.getElementById('editForm').addEventListener('submit', handleEditTask);

    // 筛选按钮点击
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            // 切换 active 样式
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            // 更新筛选条件并重新加载
            currentFilter = btn.dataset.filter;
            loadTasks();
        });
    });

    // 点击弹窗背景关闭弹窗
    document.getElementById('editModal').addEventListener('click', (e) => {
        if (e.target.id === 'editModal') closeModal();
    });
}

// ============================================
// 通用 API 请求封装
// ============================================
async function apiRequest(url, method = 'GET', body = null) {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' }
    };
    if (body) options.body = JSON.stringify(body);

    try {
        const response = await fetch(url, options);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('API 请求失败:', error);
        showToast('网络请求失败，请检查 C++ 服务是否运行', 'error');
        throw error;
    }
}

// ============================================
// 加载并渲染任务列表
// ============================================
async function loadTasks() {
    const taskList = document.getElementById('taskList');
    taskList.innerHTML = '<div class="loading">加载中...</div>';

    try {
        const data = await apiRequest(`${API_BASE}/tasks`);
        if (data.success) {
            renderTasks(data.tasks);
            updateStats(data.tasks);
        }
    } catch (e) {
        taskList.innerHTML = `
            <div class="empty-state">
                <p>❌ 无法连接到服务器</p>
                <p style="font-size: 0.875rem; margin-top: 8px;">请确保 C++ 服务正在运行</p>
            </div>
        `;
    }
}

// ============================================
// 渲染任务卡片
// ============================================
function renderTasks(tasks) {
    const taskList = document.getElementById('taskList');

    // 根据当前筛选条件过滤
    let filtered = tasks;
    if (currentFilter === 'pending') {
        filtered = tasks.filter(t => !t.completed);
    } else if (currentFilter === 'completed') {
        filtered = tasks.filter(t => t.completed);
    }

    // 空状态
    if (filtered.length === 0) {
        const msg = currentFilter === 'all' ? '还没有任务，创建一个吧！' : '该分类下没有任务';
        taskList.innerHTML = `
            <div class="empty-state">
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/>
                    <rect x="9" y="3" width="6" height="4" rx="2"/>
                    <path d="M9 14l2 2 4-4"/>
                </svg>
                <p>${msg}</p>
            </div>
        `;
        return;
    }

    // 生成 HTML
    taskList.innerHTML = filtered.map(task => `
        <div class="task-card ${task.completed ? 'completed' : ''}" data-id="${task.id}">
            <div class="task-checkbox" onclick="toggleTask(${task.id})" title="标记完成/未完成">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                    <polyline points="20 6 9 17 4 12"/>
                </svg>
            </div>
            <div class="task-content">
                <div class="task-title">${escapeHtml(task.title)}</div>
                ${task.description ? `<div class="task-desc">${escapeHtml(task.description)}</div>` : ''}
                <div class="task-meta">
                    <span class="priority-badge priority-${getPriorityClass(task.priority)}">
                        ${getPriorityLabel(task.priority)}
                    </span>
                    <span class="task-date">${formatDate(task.created_at)}</span>
                </div>
            </div>
            <div class="task-actions">
                <button class="task-btn edit"
                    onclick="openEditModal(${task.id}, '${escapeHtml(task.title)}', '${escapeHtml(task.description || '')}', ${task.priority})"
                    title="编辑">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                        <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                    </svg>
                </button>
                <button class="task-btn delete" onclick="deleteTask(${task.id})" title="删除">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                    </svg>
                </button>
            </div>
        </div>
    `).join('');
}

// ============================================
// 业务操作：增删改查
// ============================================

// 新建任务
async function handleAddTask(e) {
    e.preventDefault();

    const title = document.getElementById('title').value.trim();
    const description = document.getElementById('description').value.trim();
    const priority = parseInt(document.getElementById('priority').value);

    if (!title) {
        showToast('请输入任务标题', 'error');
        return;
    }

    try {
        const result = await apiRequest(`${API_BASE}/tasks`, 'POST', {
            title, description, priority
        });

        if (result.success) {
            showToast('✅ 任务创建成功！');
            document.getElementById('taskForm').reset();
            document.getElementById('priority').value = '2';
            loadTasks();
        } else {
            showToast(result.message || '创建失败', 'error');
        }
    } catch (e) {}
}

// 切换完成状态
async function toggleTask(id) {
    try {
        const result = await apiRequest(`${API_BASE}/tasks/${id}/toggle`, 'POST');
        if (result.success) loadTasks();
    } catch (e) {}
}

// 删除任务
async function deleteTask(id) {
    if (!confirm('确定要删除这个任务吗？')) return;

    try {
        const result = await apiRequest(`${API_BASE}/tasks/${id}`, 'DELETE');
        if (result.success) {
            showToast('🗑️ 任务已删除');
            loadTasks();
        } else {
            showToast(result.message || '删除失败', 'error');
        }
    } catch (e) {}
}

// 打开编辑弹窗
function openEditModal(id, title, description, priority) {
    document.getElementById('editId').value = id;
    document.getElementById('editTitle').value = title;
    document.getElementById('editDescription').value = description;
    document.getElementById('editPriority').value = priority;
    document.getElementById('editModal').classList.add('active');
}

// 关闭编辑弹窗
function closeModal() {
    document.getElementById('editModal').classList.remove('active');
}

// 提交编辑
async function handleEditTask(e) {
    e.preventDefault();

    const id = document.getElementById('editId').value;
    const title = document.getElementById('editTitle').value.trim();
    const description = document.getElementById('editDescription').value.trim();
    const priority = parseInt(document.getElementById('editPriority').value);

    // 保持原有完成状态
    const card = document.querySelector(`.task-card[data-id="${id}"]`);
    const completed = card ? card.classList.contains('completed') : false;

    try {
        const result = await apiRequest(`${API_BASE}/tasks/${id}`, 'PUT', {
            title, description, priority, completed
        });

        if (result.success) {
            showToast('✏️ 任务已更新');
            closeModal();
            loadTasks();
        } else {
            showToast(result.message || '更新失败', 'error');
        }
    } catch (e) {}
}

// ============================================
// 统计面板更新
// ============================================
function updateStats(tasks) {
    const total = tasks.length;
    const completed = tasks.filter(t => t.completed).length;
    const pending = total - completed;

    document.getElementById('totalTasks').textContent = total;
    document.getElementById('pendingTasks').textContent = pending;
    document.getElementById('completedTasks').textContent = completed;
}

// ============================================
// 工具函数
// ============================================

// HTML 转义，防止 XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 优先级样式类
function getPriorityClass(p) {
    return p === 1 ? 'high' : (p === 3 ? 'low' : 'medium');
}

// 优先级文字
function getPriorityLabel(p) {
    return p === 1 ? '高优先级' : (p === 3 ? '低优先级' : '中优先级');
}

// 友好时间格式
function formatDate(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now - date;

    if (diff < 3600000) return '刚刚';
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`;
    if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`;

    return date.toLocaleDateString('zh-CN', {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
    });
}

// Toast 通知
function showToast(message, type = 'success') {
    document.querySelectorAll('.toast').forEach(t => t.remove());

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = type === 'success'
        ? `<span>✓</span> ${message}`
        : `<span>✗</span> ${message}`;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'toastIn 0.3s ease-out reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}