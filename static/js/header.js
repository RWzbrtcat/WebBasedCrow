// ============================================
// 灵动岛头部：页面顶部无边框，下拉后椭圆边框
// ============================================
(function () {
    function init() {
        const header = document.querySelector('.site-header-pill');
        if (!header) return;
        const update = () => header.classList.toggle('scrolled', window.scrollY > 0);
        update();
        window.addEventListener('scroll', update, { passive: true });
    }
    document.addEventListener('DOMContentLoaded', init);
})();
