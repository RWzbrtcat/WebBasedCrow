// ============================================
// 导航栏登录态控制：根据登录状态显示/隐藏入口
// 带有 data-auth-role="admin" 的链接仅登录后可见。
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    fetch('/api/auth')
        .then((r) => r.json())
        .then((data) => {
            const authed = !!(data && data.authed);
            document.querySelectorAll('[data-auth-role="admin"]').forEach((el) => {
                el.hidden = !authed;
            });
        })
        .catch(() => {
            // 无法获取登录态时，默认隐藏需要登录的入口，避免向陌生人泄露
            document.querySelectorAll('[data-auth-role="admin"]').forEach((el) => { el.hidden = true; });
        });
});
