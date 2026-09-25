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

// 在导航栏末尾渲染「头像 + 下拉菜单」：
// - 有头像图则显示图片，否则显示灰色人形图标。
// - 点击头像弹出下拉菜单，内含「个人资料」和「退出」两个选项。
function renderNavAvatar(data, authed) {
    const nav = document.querySelector('.site-header .nav');
    if (!nav) return;

    let wrap = nav.querySelector('.nav-avatar-wrap');
    if (!wrap) {
        wrap = document.createElement('div');
        wrap.className = 'nav-avatar-wrap';
        nav.appendChild(wrap);
    }

    if (!authed) {
        wrap.hidden = true;
        return;
    }
    wrap.hidden = false;

    // 头像按钮
    let avatar = wrap.querySelector('.nav-avatar');
    if (!avatar) {
        avatar = document.createElement('button');
        avatar.type = 'button';
        avatar.className = 'nav-avatar';
        avatar.title = '个人资料';
        avatar.setAttribute('aria-label', '个人资料');
        avatar.setAttribute('aria-haspopup', 'true');
        avatar.setAttribute('aria-expanded', 'false');
        wrap.appendChild(avatar);
    }

    // 下拉菜单
    let menu = wrap.querySelector('.nav-avatar-menu');
    if (!menu) {
        menu = document.createElement('div');
        menu.className = 'nav-avatar-menu';
        menu.hidden = true;

        const profileItem = document.createElement('a');
        profileItem.href = '/profile';
        profileItem.textContent = '个人资料';

        const logoutItem = document.createElement('a');
        logoutItem.href = '/logout';
        logoutItem.textContent = '退出';

        menu.appendChild(profileItem);
        menu.appendChild(logoutItem);
        wrap.appendChild(menu);
    }

    // 绑定点击切换（仅一次）
    if (!avatar.dataset.bound) {
        avatar.dataset.bound = '1';
        avatar.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const willOpen = menu.hidden;
            menu.hidden = !menu.hidden;
            avatar.setAttribute('aria-expanded', String(willOpen));
        });
    }

    // 渲染头像图片 / 占位图标
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
    const wrap = nav.querySelector('.nav-avatar-wrap');
    if (wrap) wrap.hidden = true;
}

// 点击头像菜单以外的区域时收起菜单
document.addEventListener('click', (e) => {
    document.querySelectorAll('.nav-avatar-wrap').forEach((wrap) => {
        if (wrap.hidden || wrap.contains(e.target)) return;
        const menu = wrap.querySelector('.nav-avatar-menu');
        const avatar = wrap.querySelector('.nav-avatar');
        if (menu && !menu.hidden) {
            menu.hidden = true;
            avatar.setAttribute('aria-expanded', 'false');
        }
    });
});

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
