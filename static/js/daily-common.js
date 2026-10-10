// ============================================
// 每日一题：页面共用的工具函数
// 被 daily.js（/daily）与 daily-question.js（/daily/question）共同依赖，
// 所以必须在这两个脚本之前加载。
// ============================================

const DAILY_API = '/api';

// ---------- 基础工具 ----------

function esc(text) {
    return String(text == null ? '' : text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function escapeAttr(text) {
    return esc(text).replace(/`/g, '&#96;');
}

function difficultyLabel(level) {
    if (Number(level) === 1) return '基础';
    if (Number(level) === 3) return '困难';
    return '进阶';
}

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

function describeFetchError(e) {
    const msg = e && e.message ? String(e.message) : '';
    if (msg === 'NETWORK') return '网络连接失败，请检查网络后重试';
    if (msg === 'BAD_JSON') return '服务端返回的数据异常，请稍后重试';
    const status = e && e.status;
    if (status === 403) return '没有权限执行该操作';
    if (status === 404) return '请求的内容不存在（404）';
    if (status >= 500) return `服务器内部错误（${status}），请稍后重试`;
    if (e && e.serverMessage) return e.serverMessage;
    return msg || '加载失败，请稍后重试';
}

// GET 请求失败自动重试一次：瞬时抖动可自愈
async function apiRequest(url, method = 'GET', body = null, retry = true) {
    const options = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) options.body = JSON.stringify(body);

    let response;
    try {
        response = await fetch(url, options);
    } catch (e) {
        if (retry && method === 'GET') {
            await sleep(700);
            return apiRequest(url, method, body, false);
        }
        console.error('[daily] 请求失败', url, e);
        throw new Error('NETWORK');
    }

    if (!response.ok) {
        if (retry && method === 'GET' && response.status >= 500) {
            await sleep(700);
            return apiRequest(url, method, body, false);
        }
        let serverMessage = '';
        try {
            const errBody = await response.json();
            serverMessage = (errBody && errBody.message) || '';
        } catch (e) { /* 响应不是 JSON，忽略 */ }
        console.error('[daily] HTTP 错误', url, response.status, serverMessage);
        const err = new Error(serverMessage || `HTTP ${response.status}`);
        err.status = response.status;
        err.serverMessage = serverMessage;
        throw err;
    }

    try {
        return await response.json();
    } catch (e) {
        console.error('[daily] JSON 解析失败', url, e);
        throw new Error('BAD_JSON');
    }
}

function showToast(message, type = 'success') {
    const old = document.querySelector('.toast');
    if (old) old.remove();
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2600);
}
