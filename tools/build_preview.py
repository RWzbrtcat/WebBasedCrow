# -*- coding: utf-8 -*-
"""根据优化后的 style.css 生成自包含的界面预览页 preview.html"""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS_PATH = os.path.join(ROOT, "static", "css", "style.css")
OUT_PATH = os.path.join(ROOT, "preview.html")

LIKE = '<svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor" aria-hidden="true"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>'
COMMENT = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>'


def card(title, topic, theme, author, date, likes, comments, excerpt):
    theme_badge = f'<span class="post-theme">{theme}</span>' if theme else ''
    return f'''<article class="post-card">
    <h2 class="post-title"><a href="#">{title}</a></h2>
    <div class="post-meta">
        <span class="post-topic">{topic}</span>
        {theme_badge}
        <span>{author}</span>
        <span class="sep">·</span>
        <span>{date}</span>
        <span class="sep">·</span>
        <span class="post-stat post-stat-like">{LIKE}<span>{likes}</span></span>
        <span class="post-stat post-stat-comment">{COMMENT}<span>{comments}</span></span>
    </div>
    <p class="post-excerpt">{excerpt}</p>
    <a class="read-more" href="#">阅读全文 →</a>
</article>'''


cards = "\n".join([
    card("深入理解 C++ 智能指针", "C++ 技术", "智能指针", "LazyCat", "2026年9月20日", 128, 16,
         "从 unique_ptr、shared_ptr 到 weak_ptr，彻底搞懂内存所有权语义、引用计数与循环引用问题。"),
    card("用 Crow 框架快速搭建 REST 服务", "C++ 技术", "Crow 框架", "LazyCat", "2026年9月12日", 96, 9,
         "轻量级 C++ Web 框架 Crow 的入门实践：路由、中间件、JSON 序列化与静态资源托管。"),
    card("并发编程：从线程到协程", "C++ 技术", "并发编程", "LazyCat", "2026年8月30日", 74, 5,
         "std::thread、async、mutex 与 C++20 协程的取舍与实战经验总结。"),
    card("周末徒步：山野间的松弛感", "生活随笔", "旅行", "LazyCat", "2026年8月18日", 52, 12,
         "一次说走就走的轻装徒步，记录沿途的风景与心情。"),
])

article = '''<section class="post-full" style="margin-top:40px;">
    <h1 class="post-title">深入理解 C++ 智能指针</h1>
    <div class="post-meta">
        <span class="post-topic">C++ 技术</span>
        <span class="post-theme">智能指针</span>
        <span>LazyCat</span>
        <span class="sep">·</span>
        <span>2026年9月20日</span>
    </div>
    <div class="markdown-body">
        <p>智能指针是 C++11 引入的 <strong>资源管理核心机制</strong>，通过 RAII 思想自动管理动态内存，从根本上避免内存泄漏。</p>
        <h2>三种智能指针</h2>
        <ul>
            <li><code>unique_ptr</code>：独占所有权，不可拷贝，可移动；</li>
            <li><code>shared_ptr</code>：共享所有权，基于引用计数；</li>
            <li><code>weak_ptr</code>：弱引用，用于打破循环引用。</li>
        </ul>
        <blockquote><p>优先使用 <code>unique_ptr</code>，只有在确实需要共享所有权时才考虑 <code>shared_ptr</code>。</p></blockquote>
        <h2>示例代码</h2>
        <pre><code class="hljs language-cpp"><span class="hljs-function">std::unique_ptr&lt;<span class="hljs-keyword">int</span>&gt; <span class="hljs-title">p</span><span class="hljs-params">(<span class="hljs-keyword">new</span> <span class="hljs-keyword">int</span>(<span class="hljs-number">42</span>))</span></span>;
<span class="hljs-keyword">auto</span> q = std::make_unique&lt;<span class="hljs-keyword">int</span>&gt;(<span class="hljs-number">42</span>);  <span class="hljs-comment">// 推荐</span></code></pre>
        <table>
            <thead><tr><th>类型</th><th>所有权</th><th>开销</th></tr></thead>
            <tbody>
                <tr><td>unique_ptr</td><td>独占</td><td>零额外开销</td></tr>
                <tr><td>shared_ptr</td><td>共享</td><td>引用计数</td></tr>
                <tr><td>weak_ptr</td><td>弱引用</td><td>无计数</td></tr>
            </tbody>
        </table>
        <p>更多细节可参考 <a href="#">C++ 参考手册</a>。</p>
    </div>
</section>'''

html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>界面预览 · LazyCat's Blog</title>
<style>
{css}
</style>
</head>
<body class="home-page">
    <header class="site-header site-header-pill">
        <div class="header-inner">
            <div class="brand"><a class="site-title" href="#">LazyCat</a></div>
            <nav class="nav">
                <a href="#" class="active">首页</a>
                <a href="#">草稿</a>
                <a href="#">创作</a>
                <button type="button" class="personalize-btn nav-dropdown-toggle">个性化<span class="nav-dropdown-caret"></span></button>
                <div class="nav-avatar-wrap">
                    <button type="button" class="nav-avatar" title="个人资料" aria-label="个人资料" aria-haspopup="true" aria-expanded="false"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg></button>
                    <div class="nav-avatar-menu" hidden>
                        <a href="#">个人资料</a>
                        <a href="#">退出</a>
                    </div>
                </div>
            </nav>
        </div>
    </header>

    <main class="container container-home">
        <aside class="home-sidebar">
            <div class="home-sidebar-title">主题</div>
            <div class="sidebar-group">
                <div class="sidebar-topic active">C++ 技术</div>
                <ul class="sidebar-theme-list">
                    <li class="sidebar-theme">智能指针</li>
                    <li class="sidebar-theme active">Crow 框架</li>
                    <li class="sidebar-theme">并发编程</li>
                </ul>
            </div>
            <div class="sidebar-group">
                <div class="sidebar-topic">生活随笔</div>
                <ul class="sidebar-theme-list">
                    <li class="sidebar-theme">旅行</li>
                    <li class="sidebar-theme">读书</li>
                </ul>
            </div>
        </aside>
        <div class="home-main">
            <h1 class="page-title">全部文章</h1>
            <p class="page-subtitle">记录技术 · 分享生活</p>
            <nav class="topic-tabs">
                <span class="topic-tab active">全部文章 <span class="topic-count">4</span></span>
                <span class="topic-tab">C++ 技术 <span class="topic-count">3</span></span>
                <span class="topic-tab">生活随笔 <span class="topic-count">1</span></span>
            </nav>
            <div class="post-list">
{cards}
            </div>
{article}
        </div>
    </main>

    <footer class="site-footer">
        <a href="#">冀ICP备2026039047号</a>
    </footer>
    <script>
    (function () {
        var h = document.querySelector('.site-header-pill');
        if (!h) return;
        var update = function () { h.classList.toggle('scrolled', window.scrollY > 0); };
        update();
        window.addEventListener('scroll', update, { passive: true });
    })();
    (function () {
        var avatar = document.querySelector('.nav-avatar');
        var menu = document.querySelector('.nav-avatar-menu');
        if (avatar && menu) {
            avatar.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                var willOpen = menu.hidden;
                menu.hidden = !menu.hidden;
                avatar.setAttribute('aria-expanded', String(willOpen));
            });
        }
        document.addEventListener('click', function (e) {
            var wrap = document.querySelector('.nav-avatar-wrap');
            if (wrap && !wrap.contains(e.target) && menu && !menu.hidden) {
                menu.hidden = true;
                avatar.setAttribute('aria-expanded', 'false');
            }
        });
    })();
    </script>
</body>
</html>'''

with io.open(CSS_PATH, "r", encoding="utf-8") as f:
    css = f.read()

out = html.replace("{css}", css).replace("{cards}", cards).replace("{article}", article)

with io.open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(out)

print("written:", OUT_PATH, len(out), "chars")
