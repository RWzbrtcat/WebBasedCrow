// ============================================
// 导航栏登录态控制：根据登录状态显示/隐藏入口
// 带有 data-auth-role="admin" 的链接仅登录后可见。
// 带有 data-auth-role="main"  的链接仅主管理员可见。
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    fetch('/api/auth')
        .then((r) => r.json())
        .then((data) => {
            const authed = !!(data && data.authed);
            const isMain = !!(data && data.is_main);
            document.querySelectorAll('[data-auth-role="admin"]').forEach((el) => {
                el.hidden = !authed;
            });
            document.querySelectorAll('[data-auth-role="main"]').forEach((el) => {
                el.hidden = !isMain;
            });
            renderNavAvatar(data, authed);
        })
        .catch(() => {
            // 无法获取登录态时，默认隐藏需要登录的入口，避免向陌生人泄露
            document.querySelectorAll('[data-auth-role="admin"], [data-auth-role="main"]').forEach((el) => { el.hidden = true; });
            hideNavAvatar();
        });
});

// 把导航栏里的「个人」链接替换为头像：有头像图则显示图片，否则显示灰色人形图标。
// 若页面没有「个人」链接（如文章页），则在导航栏末尾新建一个头像入口。
function renderNavAvatar(data, authed) {
    const nav = document.querySelector('.site-header .nav');
    if (!nav) return;

    let avatar = nav.querySelector('a.nav-avatar');
    if (!avatar) {
        const profileLink = nav.querySelector('a[href="/profile"]');
        if (profileLink) {
            avatar = profileLink;
            avatar.className = 'nav-avatar';
        } else {
            avatar = document.createElement('a');
            avatar.href = '/profile';
            avatar.className = 'nav-avatar';
            nav.appendChild(avatar);
        }
    }
    avatar.title = '个人资料';
    avatar.setAttribute('aria-label', '个人资料');

    if (!authed) {
        avatar.hidden = true;
        return;
    }
    avatar.hidden = false;

    const url = data && data.avatar ? String(data.avatar).trim() : '';

    if (url) {
        avatar.textContent = '';
        const img = document.createElement('img');
        img.src = url;
        img.alt = '头像';
        img.referrerPolicy = 'no-referrer';
        img.onerror = () => { avatar.replaceChildren(defaultAvatarSvg()); };
        avatar.appendChild(img);
    } else {
        avatar.replaceChildren(defaultAvatarSvg());
    }
}

function hideNavAvatar() {
    const nav = document.querySelector('.site-header .nav');
    if (!nav) return;
    nav.querySelectorAll('a[href="/profile"], .nav-avatar').forEach((el) => { el.hidden = true; });
}

// 默认的灰色人形占位图标（Material Design person）
function defaultAvatarSvg() {
    const SVG_NS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    const path = document.createElementNS(SVG_NS, 'path');
    path.setAttribute('d', 'M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z');
    svg.appendChild(path);
    return svg;
}
