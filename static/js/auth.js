// ============================================
// 导航栏登录态控制：根据登录状态显示/隐藏入口
// 带有 data-auth-role="admin" 的链接仅登录后可见。
// 「个人资料」「退出」「管理员」已整合进头像下拉菜单（renderNavAvatar），
// 其中「管理员」仅主管理员（站长）可见。
// ============================================

// 登录态只查一次：脚本解析时发起，供本文件与其他脚本（首页 Dashboard 等）复用
const AUTH_PROMISE = fetch('/api/auth')
    .then((r) => r.json())
    .catch(() => null);
window.__blogAuthPromise = AUTH_PROMISE;

document.addEventListener('DOMContentLoaded', () => {
    bindCreateDropdown();
    highlightCreateDropdown();

    AUTH_PROMISE.then((data) => {
        const authed = !!(data && data.authed);
        const isMain = !!(data && data.is_main);
        document.querySelectorAll('[data-auth-role="admin"]').forEach((el) => {
            el.hidden = !authed;
        });
        document.querySelectorAll('[data-auth-role="main"]').forEach((el) => {
            el.hidden = !isMain;
        });
        // 拿不到登录态（data 为 null）时同样按未登录处理，避免向陌生人泄露入口
        renderNavAvatar(data, authed);
    });
});

// 在导航栏末尾渲染「头像 + 下拉菜单」：
// - 有头像图则显示图片，否则显示灰色人形图标。
// - 点击头像弹出下拉菜单，内含「个人资料」「退出」，站长额外含「管理员」。
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

    // 收起头像菜单
    const closeMenu = () => {
        if (menu && !menu.hidden) {
            menu.hidden = true;
            avatar.setAttribute('aria-expanded', 'false');
        }
    };

    if (!menu) {
        menu = document.createElement('div');
        menu.className = 'nav-avatar-menu';
        menu.hidden = true;

        const profileItem = document.createElement('a');
        profileItem.href = '/profile';
        profileItem.textContent = '个人资料';

        // 个性化：更换背景 / 更换样式（原独立「个性化」按钮并入头像菜单）
        const bgItem = document.createElement('button');
        bgItem.type = 'button';
        bgItem.className = 'nav-avatar-menu-item';
        bgItem.textContent = '更换背景';

        const themeItem = document.createElement('button');
        themeItem.type = 'button';
        themeItem.className = 'nav-avatar-menu-item';
        themeItem.textContent = '更换样式';

        const logoutItem = document.createElement('a');
        logoutItem.href = '/logout';
        logoutItem.textContent = '退出';

        menu.appendChild(profileItem);
        menu.appendChild(bgItem);
        menu.appendChild(themeItem);

        // 管理员入口：仅主管理员（站长）可见
        if (data && data.is_main) {
            const adminItem = document.createElement('a');
            adminItem.href = '/admin';
            adminItem.textContent = '管理员';
            menu.appendChild(adminItem);
        }

        menu.appendChild(logoutItem);
        wrap.appendChild(menu);

        bgItem.addEventListener('click', () => {
            closeMenu();
            const fn = window.__blogPersonalize && window.__blogPersonalize.changeBackground;
            if (fn) fn();
        });
        themeItem.addEventListener('click', () => {
            closeMenu();
            const fn = window.__blogPersonalize && window.__blogPersonalize.changeTheme;
            if (fn) fn();
        });
    }

    // 绑定点击切换（仅一次）
    if (!avatar.dataset.bound) {
        avatar.dataset.bound = '1';
        avatar.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            // 打开头像菜单时收起「创作」下拉，避免两个下拉同时展开
            closeCreateDropdowns();
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

// 收起所有头像菜单；skip(wrap) 返回 true 的跳过
function closeAvatarMenus(skip) {
    document.querySelectorAll('.nav-avatar-wrap').forEach((wrap) => {
        if (wrap.hidden || (typeof skip === 'function' && skip(wrap))) return;
        const menu = wrap.querySelector('.nav-avatar-menu');
        const avatar = wrap.querySelector('.nav-avatar');
        if (menu && !menu.hidden) {
            menu.hidden = true;
            avatar.setAttribute('aria-expanded', 'false');
        }
    });
}

// 收起所有「创作」下拉；skip(wrap) 返回 true 的跳过
function closeCreateDropdowns(skip) {
    document.querySelectorAll('.nav-create').forEach((wrap) => {
        if (wrap.hidden || (typeof skip === 'function' && skip(wrap))) return;
        const menu = wrap.querySelector('.nav-dropdown-menu');
        const toggle = wrap.querySelector('.nav-create-toggle');
        if (menu && !menu.hidden) {
            menu.hidden = true;
            wrap.classList.remove('open');
            toggle.setAttribute('aria-expanded', 'false');
        }
    });
}

// 点击下拉以外的区域时收起全部（点击所在下拉内部则跳过）
document.addEventListener('click', (e) => {
    closeAvatarMenus((wrap) => wrap.contains(e.target));
    closeCreateDropdowns((wrap) => wrap.contains(e.target));
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

// ============================================
// 「创作」下拉（写文章 / 草稿 / 隐藏）：切换展开
// ============================================
function bindCreateDropdown() {
    document.querySelectorAll('.nav-create').forEach((wrap) => {
        const toggle = wrap.querySelector('.nav-create-toggle');
        const menu = wrap.querySelector('.nav-dropdown-menu');
        if (!toggle || !menu || toggle.dataset.bound) return;
        toggle.dataset.bound = '1';

        toggle.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            // 打开「创作」下拉时收起头像菜单，避免两个下拉同时展开
            closeAvatarMenus();
            const willOpen = menu.hidden;
            menu.hidden = !willOpen;
            wrap.classList.toggle('open', willOpen);
            toggle.setAttribute('aria-expanded', String(willOpen));
        });
    });
}

// 当前处于「写文章 / 草稿 / 隐藏」任一页时，点亮「创作」下拉按钮
function highlightCreateDropdown() {
    const active = ['/drafts', '/hidden', '/editor'].includes(window.location.pathname);
    document.querySelectorAll('.nav-create-toggle').forEach((btn) => {
        btn.classList.toggle('active', active);
    });
}
