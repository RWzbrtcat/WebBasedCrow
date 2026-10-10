# WebBasedCrow 博客系统

基于 **Crow（C++ 头文件库）** + **MySQL/MariaDB** 的轻量级个人博客系统。后端为单进程 C++ HTTP 服务，前端为原生 HTML/CSS/JS，无 Node 构建环节。

线上示例：https://lazycat.cc

---

## 目录

- [一、架构与特性](#一架构与特性)
- [二、快速开始（TL;DR）](#二快速开始tldr)
- [三、环境依赖安装](#三环境依赖安装)
- [四、数据库准备](#四数据库准备)
- [五、获取源码与分支约定](#五获取源码与分支约定)
- [六、编译](#六编译)
- [七、运行](#七运行)
- [八、生产部署（systemd + Nginx + HTTPS）](#八生产部署systemd--nginx--https)
- [九、更新与回滚](#九更新与回滚)
- [十、备份与日常维护](#十备份与日常维护)
- [十一、目录结构](#十一目录结构)
- [十二、前端开发与预览工具](#十二前端开发与预览工具)
- [十三、常见问题排查](#十三常见问题排查)
- [十四、API 一览](#十四api-一览)
- [十五、匿名评论身份（blog_anon）](#十五匿名评论身份blog_anon)
- [十六、每日一题](#十六每日一题)
- [十七、已知限制与待办](#十七已知限制与待办)

---

## 一、架构与特性

```
浏览器 ──https──> Nginx(443) ──http──> task_server(127.0.0.1:8080) ──> MySQL/MariaDB
                    │                        │
                    └─ SSL 终止 / 反代        └─ 直接读取 static/ 下的 HTML/CSS/JS
```

**后端**：Crow 框架（`Crow/` 已随仓库提供，无需单独安装），`src/` 共 7 个文件：

| 文件 | 职责 |
|---|---|
| `src/main.cpp` | 入口：读环境变量 → 连库 → 注册路由 → 监听 8080 |
| `src/database.cpp` | 全部 SQL：建表、文章、专栏、评论、管理员、站点设置 |
| `src/routes.cpp` | 所有 HTTP 路由（`/api/*` 与页面） |
| `src/auth.cpp` | 内存会话（Cookie `blog_session`）、登录态校验 |
| `src/utils.cpp` | 文件读写、静态目录定位、上传校验、MIME、随机数 |

**特性**：文章 Markdown 编辑与实时预览、代码块高亮、**Mermaid 图表**、专栏/主题双层筛选、草稿箱、隐藏文章、点赞与评论、管理员分级（主管理员可增删管理员）、个人资料与头像上传、主题色与背景自定义。

---

## 二、快速开始（TL;DR）

```bash
# 1. 装依赖（OpenCloudOS / RHEL / CentOS）
sudo dnf install -y gcc gcc-c++ make cmake git asio-devel \
                    mariadb-server mariadb-connector-c-devel

# 2. 建库
sudo systemctl enable --now mariadb
sudo mysql -e "CREATE DATABASE IF NOT EXISTS blogdb DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 3. 拉代码
git clone <你的仓库地址> WebBasedCrow && cd WebBasedCrow
git checkout dev-page

# 4. 编译
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)

# 5. 运行（前台）
MYSQL_PASSWORD=你的密码 ./bin/task_server
```

浏览器打开 http://localhost:8080 。首次启动会打印初始管理员账号密码（见 [7.3](#73-首次启动与初始管理员)）。

---

## 三、环境依赖安装

### 3.1 依赖清单

| 依赖 | 版本要求 | 说明 |
|---|---|---|
| 编译器 | 支持 C++17（GCC ≥ 8） | `CMAKE_CXX_STANDARD 17` |
| CMake | ≥ 3.14 | `cmake_minimum_required(VERSION 3.14)` |
| asio | standalone asio | Crow 网络层依赖，`find_package(asio REQUIRED)` |
| MySQL/MariaDB 客户端开发库 | 提供 `mysql.h` + `libmysqlclient`/`libmariadb` | 编译期链接 |
| MySQL/MariaDB 服务 | — | 运行期 |

> **Crow 不需要单独安装。** 仓库 `Crow/` 目录已包含完整源码，`CMakeLists.txt` 通过 `add_subdirectory(Crow)` 直接引入。
> 旧文档里「git clone Crow → make install」的步骤**已废弃**，照做反而会引入版本不一致。

### 3.2 OpenCloudOS / RHEL / CentOS / Fedora

```bash
sudo dnf install -y gcc gcc-c++ make cmake git
sudo dnf install -y asio-devel                      # 若提示无此包：dnf install -y epel-release 后重试
sudo dnf install -y mariadb-server mariadb-connector-c-devel
```

### 3.3 Debian / Ubuntu

```bash
sudo apt update
sudo apt install -y build-essential cmake git
sudo apt install -y libasio-dev
sudo apt install -y mariadb-server libmariadb-dev   # 或 mysql-server libmysqlclient-dev
```

### 3.4 验证依赖是否就位

```bash
# asio 头文件
ls /usr/include/asio.hpp 2>/dev/null || echo "asio 未安装"

# MySQL/MariaDB 头文件与库
ls /usr/include/mysql/mysql.h /usr/include/mysql.h 2>/dev/null
ldconfig -p | grep -E 'libmysqlclient|libmariadb'
```

### 3.5 asio 装不上时的备选方案

用 Boost.Asio 替代 standalone asio：

```bash
sudo dnf install -y boost-devel        # Debian: libboost-dev
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCROW_USE_BOOST=ON
```

---

## 四、数据库准备

### 4.1 启动服务并建库

```bash
sudo systemctl enable --now mariadb          # MySQL 上为 mysqld
sudo mysql -e "CREATE DATABASE IF NOT EXISTS blogdb DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

> 必须用 `utf8mb4`：文章正文支持中文与 emoji，`utf8`（3 字节）会存不进 emoji。

### 4.2（推荐）创建专用数据库账号

不要用 root 跑生产：

```sql
CREATE USER 'blog'@'localhost' IDENTIFIED BY '强密码';
GRANT ALL PRIVILEGES ON blogdb.* TO 'blog'@'localhost';
FLUSH PRIVILEGES;
```

然后把密码写进 systemd 的 `EnvironmentFile`（见 [8.2](#82-配置-systemd-服务)），**不要写进源码、不要提交进 Git**。

> 这一步是**可选的**。如果你服务器上只有 `root`（很常见），跳过本节即可，
> 只要把服务端的 `MYSQL_USER` 设成 `root`、`MYSQL_PASSWORD` 填 root 的密码就能正常跑。
> 本文档后续出现的 `mysql -u blog` 都只是示例，**按你实际存在的账号替换**（用 root 就是 `-u root`）。

### 4.3 表结构：自动创建，无需手动建表

服务启动时 `DataBase` 构造函数会自动 `CREATE TABLE IF NOT EXISTS`：

| 表 | 内容 |
|---|---|
| `posts` | 文章：标题、正文、简介、作者、`topic`（专栏）、`theme`（主题）、`status`（published/draft）、点赞数、`hidden`、创建/更新时间 |
| `topics` | 专栏（首次启动会用已有文章的 `topic` 去重填充） |
| `comments` | 评论 |
| `questions` | 面试题库：分类、标签、难度、题干、答案（Markdown）、`status`（草稿/已发布） |
| `daily_questions` | 每日排期：`d`（日期）→ `question_id`，当天用哪道题 |
| `daily_seen` | 答题记录：`(d, owner_token)` 主键，用于统计连续打卡天数 |
| `settings` | 站点配置（背景图、主题色、每日一题基准日），键值对 |
| `admins` | 管理员（邮箱、昵称、头像、salt、密码哈希、`is_main`） |

**升级安全**：启动时若发现旧表缺列（如 `posts.theme`、`admins.nickname`），会自动 `ALTER TABLE` 补上，无需手动迁移。

**会话不落库**：登录态是进程内存中的 `unordered_map`（`src/auth.cpp`），所以**重启服务后所有人都需要重新登录**。

---

## 五、获取源码与分支约定

```bash
git clone <你的仓库地址> WebBasedCrow
cd WebBasedCrow
git checkout dev-page
```

| 分支 | 用途 |
|---|---|
| `main` | 稳定主分支 |
| `dev-page` | **日常开发分支，所有改动提交并推送到这里** |
| `dev-blog` | 早期博客功能分支（历史遗留） |

提交前确认当前分支：

```bash
git branch --show-current     # 应为 dev-page
git checkout dev-page         # 不是就切过去
```

---

## 六、编译

### 6.1 编译命令

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
```

- 产物输出目录由 `CMAKE_RUNTIME_OUTPUT_DIRECTORY` 指定为**项目根目录的 `bin/`**，即 `bin/task_server`（不是 `build/bin/`）。
- `build/` 只是 CMake 中间目录。建议把它加入 `.gitignore`（见 [15.2](#152-build-目录被误纳入版本控制)）。
- 增量编译：改完 `src/` 后再次执行 `cmake --build build -j$(nproc)` 即可。

### 6.2 编译失败排查

| 报错 | 原因 | 解决 |
|---|---|---|
| `找不到 mysql 数据库，请安装: sudo yum install mysql-devel` | `find_path` 没找到 `mysql.h`，或 `find_library` 没找到客户端库 | 装 `mariadb-connector-c-devel`（Debian: `libmariadb-dev`） |
| `Could NOT find asio` | 缺 standalone asio | `dnf install asio-devel` / `apt install libasio-dev`，或用 `-DCROW_USE_BOOST=ON` |
| `error: 'filesystem' is not a member of 'std'` | GCC 版本过旧 | 升级到 GCC ≥ 8，或 `CXXFLAGS=-lstdc++fs` |
| 找不到 `crow.h` | `Crow/` 目录缺失或不完整 | 重新 clone，确认 `Crow/include/crow.h` 存在 |
| 链接报 `undefined reference to mysql_*` | 库找到了但架构不匹配（32/64 位） | 检查 `MYSQL_LIBRARY` 路径，删除 `build/` 重新 cmake |

排查技巧：查看 CMake 实际找到的路径

```bash
grep -E 'MYSQL_INCLUDE_DIR|MYSQL_LIBRARY' build/CMakeCache.txt
```

---

## 七、运行

### 7.1 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `MYSQL_HOST` | `localhost` | 数据库地址 |
| `MYSQL_PORT` | `3306` | 数据库端口 |
| `MYSQL_USER` | `root` | 数据库账号 |
| `MYSQL_PASSWORD` | （空） | 数据库密码 |
| `MYSQL_DB` | `blogdb` | 数据库名 |

端口固定为 **8080**（`src/main.cpp` 中 `app.port(8080).multithreaded().run()`），暂不支持环境变量覆盖；若要改端口，改源码重新编译。

### 7.2 前台运行（调试用）

```bash
cd bin
MYSQL_HOST=localhost MYSQL_USER=blog MYSQL_PASSWORD=你的密码 MYSQL_DB=blogdb ./task_server
```

停止：`Ctrl+C`。

### 7.3 首次启动与初始管理员

`admins` 表为空时，服务会**自动创建主管理员**：

```
邮箱: admin@localhost
密码: <随机 12 位十六进制，仅打印一次>
```

**务必立刻保存并登录后修改密码。** 若错过打印：

```bash
# systemd 部署的
journalctl -u blog | grep -A6 '已创建初始管理员'

# 前台运行的：往上翻终端输出
```

> ⚠️ **登录页的输入规则**：登录框只需填邮箱前缀，前端会自动补全 `@lazycat.com`；若输入内容**已包含 `@`**，则原样提交。
> 因此初始账号 `admin@localhost` 必须**完整输入** `admin@localhost`，不能只填 `admin`。
> 想统一成 `admin@lazycat.com`，直接改数据库即可（密码哈希与邮箱无关，不受影响）：
> ```sql
> UPDATE admins SET email='admin@lazycat.com' WHERE is_main=1;
> ```

### 7.4 静态文件目录（重要）

`getStaticDir()`（`src/utils.cpp`）通过 `/proc/self/exe` 定位可执行文件位置，返回 **`<exe目录>/../static`**。

因此目录结构必须是：

```
WebBasedCrow/
├── bin/task_server     ← 可执行文件
└── static/             ← 前端文件（HTML/CSS/JS）
```

把 `task_server` 单独拷到别处运行会找不到页面（表现为所有页面空白/404）。

### 7.5 上传目录

图片上传保存到 `static/uploads/`（首次上传时自动创建）。需保证服务进程对该目录**有写权限**：

```bash
mkdir -p static/uploads && chown -R 运行用户:运行用户 static/uploads
```

> `static/uploads/` 已在 `.gitignore` 中，不会入库。

---

## 八、生产部署（systemd + Nginx + HTTPS）

以下路径以 `/home/wb/projects/WebBasedCrow` 为例，按实际调整。

### 8.1 部署目录

```bash
sudo mkdir -p /home/wb/projects
cd /home/wb/projects
sudo git clone <你的仓库地址> WebBasedCrow
cd WebBasedCrow && sudo git checkout dev-page
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
mkdir -p static/uploads
sudo chown -R wb:wb /home/wb/projects/WebBasedCrow
```

### 8.2 配置 systemd 服务

密码用 `EnvironmentFile` 注入，避免明文出现在 unit 里：

```bash
sudo tee /etc/blog.env > /dev/null <<'EOF'
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=blog
MYSQL_PASSWORD=你的数据库密码
MYSQL_DB=blogdb
EOF
sudo chmod 600 /etc/blog.env && sudo chown wb:wb /etc/blog.env

sudo tee /etc/systemd/system/blog.service > /dev/null <<'EOF'
[Unit]
Description=WebBasedCrow Blog Server
After=network-online.target mariadb.service
Wants=network-online.target

[Service]
Type=simple
User=wb
WorkingDirectory=/home/wb/projects/WebBasedCrow/bin
EnvironmentFile=/etc/blog.env
# 启动前等 8080 释放（最多 30s），避免旧进程未退出导致 bind 失败
ExecStartPre=/bin/sh -c 'for i in $(seq 1 30); do ss -tln | grep -q ":8080 " || exit 0; sleep 1; done; exit 0'
ExecStart=/home/wb/projects/WebBasedCrow/bin/task_server
KillSignal=SIGTERM
TimeoutStopSec=5
Restart=always
RestartSec=5
StartLimitIntervalSec=120
StartLimitBurst=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now blog
systemctl status blog --no-pager
```

### 8.3 systemd 常用命令

```bash
systemctl status blog              # 状态与最近日志
systemctl restart blog             # 重启
systemctl stop blog                # 停止（不会自动拉起）
journalctl -u blog -f              # 实时日志
journalctl -u blog --since today   # 今日日志
```

> **为什么是 `systemctl stop blog` 而不是 `stop task_server`？**
> `systemctl` 操作的是 **unit 名**（来自 `blog.service`），不是进程名。`task_server` 只是 `ExecStart` 拉起的二进制。
> 直接 `pkill -f task_server` 会绕开 systemd，`Restart=always` 会立刻再拉一个起来——表现就是"杀不掉"。

### 8.4 Nginx 反向代理 + HTTPS

让 Nginx 对外只开 80/443，转发到本机 8080：

```nginx
server {
    listen 80;
    server_name lazycat.cc www.lazycat.cc;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

HTTPS 证书用 certbot 申请，并**务必启用自动续期**（默认 timer 是 disabled）：

```bash
sudo dnf install -y certbot python3-certbot-nginx
sudo certbot --nginx -d lazycat.cc -d www.lazycat.cc --non-interactive --agree-tos -m you@example.com --redirect
sudo systemctl enable --now certbot-renew.timer
```

> 国内服务器还需完成 **ICP 备案**（未备案域名访问 80/443 会被拦截）、**安全组放行 80/443**、**DNS A 记录解析**。
> 完整步骤（含证书续期、ICP 备案号展示、验证清单）见 **`nginx服务代理.md`**。

### 8.5 部署验证清单

```bash
systemctl is-active blog nginx certbot-renew.timer      # 三个都应 active
ss -tlnp | grep -E ':(80|443|8080)\b'                   # 端口监听
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/api/posts   # 应 200
curl -s -o /dev/null -w "%{http_code}\n" https://lazycat.cc/               # 应 200
```

---

## 九、更新与回滚

### 9.1 只改了前端（HTML/CSS/JS）—— 无需编译、无需重启

页面是运行时 `readFile` 读取的，pull 即生效：

```bash
cd /home/wb/projects/WebBasedCrow
sudo -u wb git pull origin dev-page
```

若浏览器看起来没变化，是缓存问题：强制刷新（Ctrl+F5），或在 Nginx 里给静态资源加版本号/缓存头。

### 9.2 改了 C++ 源码 —— 需重新编译并重启

```bash
cd /home/wb/projects/WebBasedCrow
sudo -u wb git pull origin dev-page
cmake --build build -j$(nproc)
sudo systemctl restart blog
sudo systemctl status blog --no-pager
```

> 注意：`git pull` 更新的是仓库里的 `static/`，而服务读的就是这个目录，所以前端改动同样生效。

### 9.3 回滚

```bash
git log --oneline -10                 # 找到目标 commit
sudo -u wb git checkout <commit> -- static/   # 只回滚前端，立即生效
sudo -u wb git checkout <commit> -- src/ && cmake --build build -j$(nproc) && sudo systemctl restart blog   # 回滚后端
```

---

## 十、备份与日常维护

### 10.1 数据库备份

```bash
# 手动备份
mysqldump -u blog -p --databases blogdb > blogdb_$(date +%F).sql

# 每日 3 点自动备份，保留 14 天（crontab -e）
0 3 * * * mysqldump -u blog -p'密码' --databases blogdb | gzip > /backup/blogdb_$(date +\%F).sql.gz && find /backup -name 'blogdb_*.sql.gz' -mtime +14 -delete
```

恢复：

```bash
mysql -u blog -p blogdb < blogdb_2026-09-29.sql
```

### 10.2 上传图片备份

```bash
tar czf uploads_$(date +%F).tar.gz -C /home/wb/projects/WebBasedCrow/static uploads
```

### 10.3 定期检查

```bash
systemctl is-active blog mariadb nginx certbot-renew.timer
df -h                                  # 磁盘
journalctl -u blog --since today | grep -Ei 'error|terminate|gone away'   # 异常
```

---

## 十一、目录结构

```
WebBasedCrow/
├── CMakeLists.txt          # 构建配置（产物输出到 bin/）
├── README.md               # 本文档
├── nginx服务代理.md         # Nginx 反代 / HTTPS / 备案 / 故障排查
├── CrowCpp_完整使用指南.md  # Crow 框架学习笔记
├── Crow/                   # Crow 源码（已合入仓库，无需单独安装）
├── src/                    # C++ 后端
│   ├── main.cpp            # 入口、环境变量、端口 8080
│   ├── database.cpp/.h     # 全部 SQL
│   ├── routes.cpp/.h       # 全部路由
│   ├── auth.cpp/.h         # 内存会话
│   └── utils.cpp/.h        # 文件/上传/工具函数
├── bin/                    # 编译产物 task_server（gitignore 建议排除或保留）
├── build/                  # CMake 中间目录（建议 gitignore）
├── static/                 # 前端（运行时读取，改完刷新即生效）
│   ├── index.html          # 首页（专栏/主题双层筛选）
│   ├── post.html           # 文章详情
│   ├── daily.html          # 每日一题（左「历史题目/题目管理」+ 中「今日题目/题库」+ 右「打卡/分布」）
│   ├── daily-q.html        # 题目详情页（/daily/q/<id>，公开只读；左读题 + 右栏相关题）
│   ├── daily-question.html # 出题 / 改题页（/daily/question，仅站长）
│   ├── editor.html         # Markdown 编辑器（支持 Mermaid）
│   ├── login.html          # 登录
│   ├── admin.html          # 管理员管理（主管理员可见）
│   ├── profile.html        # 个人资料
│   ├── drafts.html         # 草稿箱
│   ├── hidden.html         # 隐藏文章
│   ├── css/                # style.css（全站样式）、highlight.css
│   ├── js/                 # auth/header/theme/list/post/editor/admin/profile/login/markdown
│   │                       # daily-common.js（共用工具）+ daily.js + daily-q.js + daily-question.js
│   └── uploads/            # 上传图片（gitignore）
├── tools/                    # 开发辅助脚本
│   ├── build_preview.py      # 生成 preview*.html 静态预览
│   ├── repro_list.mjs        # Node 模拟 DOM，回归首页渲染流程
│   ├── gen_seed.py           # 汇总 qbank/*.py → 生成 seed_questions.sql（含 SQL 自检）
│   ├── qbank/                # 题库数据源（分类, 标签, 难度, 题干, 答案）
│   ├── _extract_existing.py  # 旧 SQL → qbank/existing.py 无损提取（勿手改产物）
│   ├── _verify_seed.py       # 校验种子 SQL：切分语句 + 逐条比对 + 换行符检查
│   ├── seed_questions.sql    # 面试题库种子（可重复执行）
│   ├── charset_precheck.sql  # 字符集诊断（只读，见 13.8）
│   ├── charset_to_utf8.sql   # 老数据 cp1252 转义 → 真 utf8mb4（见 13.8.1）
│   └── fixture_*.json        # 线上数据快照（回归用）
└── preview*.html           # 静态预览页（本地双击可看，不参与部署）
```

---

## 十二、前端开发与预览工具

改前端后没有可视化校验手段时，可用这两个脚本做低成本回归：

```bash
# 重新生成静态预览页（preview.html / preview_profile.html / ...）
python tools/build_preview.py

# 回归首页渲染：Node 模拟 DOM + fixture 数据执行 list.js，能捕获 ReferenceError 等渲染期异常
node tools/repro_list.mjs

# 回归每日一题：Node 模拟 DOM + 假接口跑 daily.js / daily-q.js / daily-question.js 全流程
# （今日题目/题库/历史是否渲染、右栏打卡天数与 7 天格子、题库分布行、编辑是否链到
#   /daily/question?id=N、历史与题库条目是否链到 /daily/q/<id>、草稿题是否被排除、
#   详情页题干/答案/相关题是否渲染且 ?d= 优先、右栏相关题显隐是否正确、出题页回填是否正确）
node tools/repro_daily.mjs
```

> ⚠️ `tools/build_preview.py` 生成的是**独立骨架的预览页**，与真实 `static/*.html` 不是同一份 HTML。
> **预览正常 ≠ 真实页面正常**，改完 `static/js/list.js` 请务必再跑一次 `node tools/repro_list.mjs`。
> （历史上曾因 `renderThemeTabs` 变量声明丢失导致首页崩溃，而预览页完全看不出来。）

**Mermaid 图表**：图表库走 CDN 懒加载（`fastly.jsdelivr.net` → `cdn.jsdelivr.net` → `unpkg.com`），只有文中出现 ```mermaid 代码块时才加载。若部署环境无法访问外网，图表不会渲染（会保留源码并提示），此时需把 `mermaid.min.js` 下载到 `static/js/` 改为本地引用。

---

## 十三、常见问题排查

### 13.1 启动失败：`Failed to bind to 0.0.0.0:0 - Address already in use`

两个坑：

1. **`0.0.0.0:0` 里的端口 0 是假信息**。Crow 在 `Crow/include/crow/http_server.h` 打印的是 `bind()` **失败之后**读取的 endpoint，此时并未真正绑定，所以端口恒为 0。实际端口就是 **8080**。
2. Crow 已开启 `SO_REUSEADDR`，TIME_WAIT 不会触发该错误。报 `Address already in use` 只可能是**另一个进程仍以 LISTEN 占用 8080**——典型是服务崩溃后 systemd 立刻拉起，旧进程还没退出。

```bash
sudo systemctl stop blog
sudo ss -tlnp | grep ':8080'      # 找到占用进程
sudo pkill -f task_server
sudo ss -tlnp | grep ':8080'      # 确认无输出
sudo systemctl start blog
```

根治：使用 [8.2](#82-配置-systemd-服务) 的加固 unit（`ExecStartPre` 等待端口释放 + `TimeoutStopSec=5` + `RestartSec=5`）。

### 13.2 页面显示「网络连接失败」「加载失败」

前端已按原因区分错误（网络 / HTTP 状态码 / JSON 解析失败），页面上会显示具体原因。按此定位：

| 页面提示 | 含义 | 处理 |
|---|---|---|
| 网络连接失败 | `fetch` 直接失败，服务没起来或端口不通 | `systemctl status blog` + `curl 127.0.0.1:8080/api/posts` |
| 服务器内部错误（500） | 后端异常（多为 SQL 失败） | `journalctl -u blog -n 100` |
| 接口不存在（404） | 前端新、后端旧（C++ 没重新编译部署） | 重新编译并重启 |
| 未授权（401）跳转登录 | 会话失效 | 正常，服务重启后会话清空，重新登录即可 |

**不要只看提示**：打开浏览器 F12 → Network，看 `/api/posts` 的真实状态码。

### 13.3 启动时 `MySQL 连接失败`

```bash
# 先确认服务活着
systemctl is-active mariadb
# 手动验证账号密码与库名
mysql -u blog -p -h localhost -e "USE blogdb; SHOW TABLES;"
```

库 `blogdb` 必须**先手动创建**（SQL 见 [4.1](#41-启动服务并建库)），表才会自动建；库不存在会直接连接失败。

### 13.4 页面空白 / 404，但服务在跑

十有八九是静态目录结构不对，见 [7.4](#74-静态文件目录重要)：`task_server` 必须在 `bin/` 下，且同级存在 `../static`。

### 13.5 登录后一刷新就掉线

会话在**进程内存**中，服务重启即失效（[4.3](#43-表结构自动创建无需手动建表)）。若频繁掉线但服务没重启，检查是不是 `Restart=always` 在悄悄重启：

```bash
journalctl -u blog --since today | grep -Ei 'Started|Stopping|terminate|gone away'
```

### 13.6 图片上传失败

- 目录无写权限：`chown -R 运行用户:运行用户 static/uploads`
- 超过 10MB 或非图片格式（png/jpg/jpeg/gif/webp/bmp）会被拒绝
- Nginx 若限制了 `client_max_body_size`，需在 nginx 配置里放大：`client_max_body_size 20m;`

### 13.7 数据库密码进了 Git

`src/main.cpp` 只用 `getenv` 读环境变量，源码里不含密码。若曾经提交过，请立即改密码并清理 Git 历史（`git filter-repo`）。

### 13.8 中文变成 `?`（每日一题 / 题库乱码）

**症状**：题库里的中文全部变成 `?`，英文与 `::`、空格等 ASCII 原样保留，例如
`std::shared_ptr ??????????????????`。

**第一步：先分清是「数据丢了」还是「只是读错了」，不要一看到 `?` 就重导。**

| 库里的真实字节 | 含义 | 处理 |
|---|---|---|
| `3F3F…`（真的 `?` 字符） | 写入时目标字符集表示不了，MySQL 静默替换，**不可逆** | 只能重新导入 |
| `E7xx…`（正常 UTF-8 汉字字节） | **数据没丢**，问题在读取/渲染层 | **不要重导**，查连接字符集 |
| `C3A7…`（latin1 双字节） | mojibake，字节还在，只是被错误解释 | 可通过转换还原 |

取 HEX 时**必须跳过 ASCII 前缀**：题干常以 `std::` 开头，前 4 个字节恒为 `7374643A`，
**无论中文有没有坏都一样**，用它判断等于没测。

```sql
SELECT id, SUBSTRING(question, 13, 3) AS cn,
       HEX(SUBSTRING(question, 13, 3)) AS cn_hex   -- 期望 E79A84E5BC95E794A8（的引用）
  FROM questions WHERE id = 1;
```

**根因（2026-10-09 定案）：应用连接的字符集，与数据的「存储形态」不一致。**

事实链（全部来自服务器实测）：

| 观测 | 结论 |
|---|---|
| `TABLE_COLLATION`：`posts` 与 `questions` **都**是 `utf8mb4_unicode_ci` | 表、列字符集都正常，**不是**表定义不一致 |
| `curl /api/questions` → 46 条全 `?`（含中文分类 `????`、tags `?,????`） | 应用读不出 `questions` 的中文 |
| 首页文章标题中文正常 | 应用读得出 `posts` 的中文 |
| 同一列在 **utf8mb4** CLI 里是 `markdown åŠŸèƒ½æµ‹è¯•`，在 **latin1** CLI 里是 `markdown 功能测试` | 老表存的是「UTF-8 字节的 cp1252 转义」 |
| `--default-character-set=latin1` 读 `questions` → 与应用接口一字不差的 `?` | 应用的连接字符集就是 latin1 |

也就是说：**老表的数据是「经 latin1 连接写进去的」**。MySQL 把应用发来的 UTF-8 字节当作
latin1 字符，转存进 utf8mb4 列 —— 字节一个没丢，只是形态变成了「UTF-8 字节的 cp1252 转义」。

于是同一条 latin1 连接：

| 数据形态 | 用 latin1 连接读 | 结果 |
|---|---|---|
| 老表：cp1252 转义 | 转回 latin1 = 原始字节 | **完全正常**（整站一直靠这个巧合工作） |
| `questions`：真中文（由 `mysql` 客户端以 utf8mb4 导入） | latin1 无法表示 → 逐字符替换 | **`?`** |

**这就是「为什么只有每日一题坏」** —— 它是全库唯一一张数据形态与其它表不同的表。

指纹：**1 个汉字 → 1 个 `?`**（不是 3 个）。只有 MySQL 按「字符」为单位转换；
若由程序或前端按字节处理，一个汉字会变成 3 个 `?`。

**诊断（只读，不改任何数据）**

```bash
mysql -u root -p --default-character-set=utf8mb4 blogdb < tools/charset_precheck.sql
```

脚本打印四段：表/列字符集、老表「当前形态 vs 迁移后」并排对照、`questions` 现状、
以及「含非 latin1 字符」的风险行统计。**关键是第 2 段** —— 若「当前形态」显示成
`åŠŸèƒ½` 这类而「迁移后」是真中文，判断即坐实。

也可以手动用 CLI 复现应用的行为：

```bash
# 应用当前等价于 latin1 连接。期望：posts 显示真中文，questions 显示 ???（与应用接口一字不差）
mysql --default-character-set=latin1 -u root -p blogdb \
  -e "SELECT id,title FROM posts LIMIT 2; SELECT id,question FROM questions LIMIT 2;"
```

**修复路线（二选一，不要混用）**

- **路线 B：全库统一到真 utf8mb4**（推荐，正解）—— 把老表数据从 cp1252 转义还原成真中文，
  之后连接统一切到 utf8mb4。做法见 13.8.1。
- **路线 A：保持 latin1 连接**（应急、治标）—— 反过来把 `questions` 的数据改成 cp1252 转义形态，
  全库回到「字节透传」，每日一题立刻正常；并给 app 设 `MYSQL_CHARSET=latin1` 钉住连接。
  代价：全库长期停留在「utf8mb4 列里存 cp1252 转义」的状态，任何用 utf8mb4 的工具
  （`mysqldump`、GUI、CLI）看到的都是乱码，属长期隐患。

**代码侧（已改，但必须等路线 B 迁移完成后才能部署）**：`DataBase::connect()` 不再写死字符集，
而是**查 `information_schema` 探测核心表后让连接自动跟随**（全 utf8mb4 → `SET NAMES utf8mb4`），
可用环境变量 `MYSQL_CHARSET` 覆盖；探测到混合字符集时**不强制、只告警**，
并把实际生效的 `character_set_client/connection/results` 打进启动日志。

> ⚠️ **顺序很重要**：在迁移数据 **之前** 部署新二进制，等于把连接切到 utf8mb4 而老数据还是
> cp1252 转义 —— 整站中文会立刻变成 `åŠŸèƒ½`。正确顺序是：备份 → 迁移数据 → 再部署。

**`questions` 不需要重新导入**：它的数据本来就是正确的真 utf8mb4。

#### 13.8.1 路线 B：把老表的 cp1252 转义还原成真 utf8mb4

**原理**：老数据的字符是「UTF-8 字节的 cp1252 转义」，三步还原：

```sql
CONVERT(col USING latin1)   -- ① 转回 latin1 字节（即原始 UTF-8 字节）
CAST(... AS BINARY)         -- ② 保留字节，禁止 MySQL 再做任何字符转换
CONVERT(... USING utf8mb4)  -- ③ 按真正的 UTF-8 解释 → 中文还原
```

合起来：`åŠŸèƒ½` → `功能`。

**两条安全保障**（`tools/charset_to_utf8.sql` 已内置）：

1. **逐列 `WHERE` 守卫**：只处理「latin1 可表示」的值。含真中文的行若被
   `CONVERT ... USING latin1` 会被写成 `?`，必须跳过；守卫
   `CONVERT(col USING latin1) = 反向转回` 恰好只对 latin1 可表示的值成立。
   **守卫必须逐列判断** —— 不能用 `title` 的守卫去改 `content`。
2. **幂等**：转换成功后守卫即不成立，重复执行不会二次转换。

**执行步骤**

```bash
# 0) 备份（错了只能靠它回滚）
mysqldump -u root -p --default-character-set=binary blogdb > blogdb.bak.sql

# 1) 只读诊断，确认判断（看第 2 段的并排对照）
mysql -u root -p --default-character-set=utf8mb4 blogdb < tools/charset_precheck.sql

# 2) 迁移：逐列 UPDATE，自带守卫与迁移前后抽样
mysql -u root -p --default-character-set=utf8mb4 blogdb < tools/charset_to_utf8.sql

# 3) 部署新二进制，连接自动切到 utf8mb4
cmake --build build -j$(nproc) && sudo systemctl restart blog.service
journalctl -u blog.service -n 40 --no-pager | grep 字符集   # 期望 results=utf8mb4
```

**为什么不用 `ALTER TABLE ... CONVERT TO CHARACTER SET`**：`CONVERT TO` 是「按字符语义重新编码」，
而这里需要的是「保持字节、只换解释方式」；用错方向会把数据再编码一次，
变成 `åŠŸèƒ½` 这类**长得几乎一样的新乱码**，极难分辨。

**验收**：迁移后重跑 `charset_precheck.sql`，第 2 段的「当前形态」与「迁移后」两列应完全一致
（都是真中文）；`charset_to_utf8.sql` 末尾的收尾自检各行应为 0。

> 说明：诊断结论已由实测坐实，但这套迁移**尚未在你的库上执行过**。务必先备份、
> 先看第 2 段的并排对照，确认无误再执行。


---

## 十四、API 一览

页面路由：`/` `/post` `/daily` `/daily/q/<id>` `/daily/question` `/login` `/logout` `/drafts` `/hidden` `/editor` `/admin` `/profile`

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| POST | `/api/login` | 登录，写入 `blog_session` Cookie | 公开 |
| GET | `/api/auth` | 当前登录态（`is_main` 等） | 公开 |
| PUT | `/api/profile` | 修改昵称/头像 | 登录 |
| PUT | `/api/password` | 修改密码（强制下线） | 登录 |
| GET/POST | `/api/admins` | 管理员列表 / 新增 | 主管理员 |
| DELETE | `/api/admins/<id>` | 删除管理员 | 主管理员 |
| GET | `/api/posts` | 已发布且未隐藏的文章列表 | 公开 |
| GET | `/api/drafts` `/api/hidden` | 草稿 / 隐藏文章 | 登录 |
| POST | `/api/posts` | 新建文章 | 登录 |
| GET | `/api/posts/<id>` | 详情（未登录看不到草稿/隐藏） | 公开 |
| PUT/DELETE | `/api/posts/<id>` | 更新 / 删除（非主管理员只能改自己的） | 登录 |
| PUT | `/api/posts/<id>/hidden` | 切换隐藏状态 | 登录 |
| POST | `/api/posts/<id>/like` `/unlike` | 点赞 / 取消 | 公开 |
| GET | `/api/posts/<id>/comments` | 评论列表（每条带 `mine` / `can_edit`） | 公开 |
| POST | `/api/posts/<id>/comments` | 发表评论 / 回复（限流：同 IP 60 秒 5 条、同访客 10 秒 1 条） | 公开 |
| PUT | `/api/comments/<id>` | `hidden` → 隐藏/显示，仅管理员；`content` → 改内容，作者（30 分钟内）或管理员 | 混合 |
| DELETE | `/api/comments/<id>` | 删除评论及其回复：管理员任意；匿名访客仅限自己发的 | 混合 |
| POST | `/api/upload` | 上传图片（multipart，字段 `image`） | 登录 |
| GET/POST | `/api/topics` | 专栏列表 / 新增 | 读公开、写登录 |
| DELETE | `/api/topics/<id>` | 删除专栏 | 登录 |
| GET | `/api/settings/background` `/api/settings/theme` | 读取站点背景 / 主题色 | 公开 |
| POST | `/api/settings/background` `/api/settings/theme` | 修改站点背景 / 主题色 | 登录 |
| GET | `/api/daily` | 今日题目（首次访问自动生成并落库，不含答案），附 `answered` / `streak` | 公开 |
| GET | `/api/daily/answer?id=` | 取题目答案，同时记录「今天看过答案」 | 公开 |
| GET | `/api/daily/history?page=` | 历史排期（按日期倒序，不含答案），含 `id` / `difficulty` 以供跳详情页 | 公开 |
| GET | `/api/daily/random?category=` | 随机换一题（不含答案） | 公开 |
| GET | `/api/daily/question?id=` | 单题详情页数据（含答案）：仅已发布题目，另附最近一次排期日期与同分类相关题 | 公开 |
| GET | `/api/questions?category=&page=&page_size=` | 题库浏览（不含答案）；站长带 `with_drafts=1` 可见草稿 | 公开 |
| GET | `/api/questions/<id>` | 单题详情（含答案，编辑回填用；含草稿） | 主管理员 |
| POST | `/api/questions` | 新增题目 | 主管理员 |
| PUT | `/api/questions/<id>` | 修改题目 | 主管理员 |
| DELETE | `/api/questions/<id>` | 删除题目 | 主管理员 |

---

## 十五、匿名评论身份（blog_anon）

访客**不需要登录**也能评论，服务端会为其下发匿名标识，用于"认领自己发的评论"（自助删除/修改）。

**机制**

1. 首次发表评论时，服务端生成 128 bit 随机 token（`randomHex(16)`），通过
   `Set-Cookie: blog_anon=<token>; HttpOnly; Path=/; SameSite=Lax; Max-Age=31536000` 下发。
2. token 一并写入 `comments.owner_token` 列；`owner_token` 为 NULL 的是历史评论，视为"无主"，仅管理员可操作。
3. 评论列表接口**只返回 `mine`（是否自己发的）和 `can_edit`（是否仍在可修改时间窗内）**，
   **`owner_token` 本身绝不返回给客户端** —— 否则任何人都能拿他人 token 冒充删评。
4. 删除/修改的归属判断全部在**服务端**完成，前端按钮只是显示与否。
5. 修改限**创建后 30 分钟内**，由 SQL 的 `created_at >= DATE_SUB(NOW(), INTERVAL 30 MINUTE)` 强制约束。

**能力边界（重要）**

不登录时**做不到"一人一 ID"**，只能做到"一浏览器一 ID"。以下情况该访客会变成"另一个人"：
清除浏览器数据、换浏览器/设备、无痕模式。届时旧评论的管理权丢失（只能由管理员处理）。
同理，同一人反复清 Cookie 可获得多个身份，所以**防刷依赖限流与内容审核，不能依赖身份**。
需要跨设备唯一就必须引入弱登录（邮箱验证码等），当前未实现。

**限流**：同一匿名 token 10 秒 1 条、同一 IP 60 秒 5 条（内存计数，重启清零）。
客户端 IP 取自 `X-Real-IP` → `X-Forwarded-For` 首个 → 直连地址，**仅用于限流，不落库**。

**表结构迁移**：服务启动时自动 `ALTER TABLE comments ADD COLUMN owner_token VARCHAR(64) NULL`
并创建 `idx_comments_owner` 索引（幂等，已有则跳过），无需手动改库。

## 十六、每日一题

首页顶部与独立页 `/daily` 展示当天题目；访客**不需要登录**，答题记录靠匿名 Cookie（`blog_anon`）。

`/daily` 为**三栏**布局，用 `grid-template-areas` 驱动回流（改断点只需重排 areas，不必动 DOM）：

```
┌──────────────────┬────────────────────────────────┬────────────────────┐
│ 历史题目          │ 今日题目卡片                    │ 我的打卡            │
│ 题目管理（站长）  │ 题库（筛选 + 加载更多）          │ 题库分布            │
└──────────────────┴────────────────────────────────┴────────────────────┘
      256px                minmax(0, 1fr)                 300px
```

| 位置 | 内容 |
|---|---|
| 左栏（吸顶） | **历史题目**：往期排期，按日期倒序，带分类标签，**整行可点进详情页**；**题目管理**（仅站长可见，只有一个「添加题目」按钮） |
| 中栏 | 今日题目卡片（查看答案 / 换一题 / 连答天数）、题库浏览（分类筛选 + 分页「加载更多」，**题干即可点进详情页**，另有「详情」入口） |
| 右栏（吸顶） | **我的打卡**（连答天数 + 今日状态 + 近 7 天格子）、**题库分布**（各分类题量与占比条，点击即筛选题库） |

- 容器由 1120px 放宽到 **1420px**（导航胶囊 `--header-width` 同步），左右栏加宽到 **256px / 300px**：两栏各向外延伸，中栏正文约 810px。
- **左栏始终有内容**：题目管理卡带 `data-auth-role="main"` 只有站长可见，但它与历史题目同处左栏，所以访客看到的仍是满满一列历史题目（早先「题目管理独占一栏会让访客看到空白」的问题已不存在）。
- 打卡与分布**不需要新增接口**：连答天数来自 `/api/daily` 的 `streak`（配合 `answered` 即可反推出「已作答的日期集合」），分类题量来自 `/api/questions` 已有的 `categories[].count`。
- 响应式：**≥1281px** 三栏 → **≤1280px** 两栏（左栏整体落到中栏下方，历史题目改多列网格，右栏跨两行继续吸顶）→ **≤880px** 单栏（主栏 → 右栏 → 左栏）。
  （三栏断点随容器加宽同步从 1200px 提到 1280px，否则中等宽度下中栏会被两侧挤压。）

出题与改题**不在列表页内联完成**，而是跳到独立页面 `/daily/question`（见 [16.4](#164-题库与出题)）：
题库列表里每题的「编辑」直接链到 `/daily/question?id=N`，避免把一整个大表单塞进列表页。
只读查看则在 `/daily/q/<id>`（见 [16.5](#165-题目详情页)）。

### 16.1 选题机制：不用定时任务

Crow 是单进程服务，没有 cron。当天题目采用**懒生成**：第一个访问当天题目的请求触发计算并落库，之后当天固定不变。

```
第一个 GET /api/daily
      ↓
daily_questions 里有今天的记录吗？
      ├─ 有   → 直接返回
      └─ 没有 → 按「日期差 + 分类轮转」算出题目 → INSERT IGNORE 落库 → 重新读取并返回
```

- **序号来源是日期差，不是行数**：`dayIndex = 今天 − daily_base_date`（基准日首次运行时写入 `settings.daily_base_date`）。这样即使某天没人访问、库里缺了那天，顺序也不会错位。
- **分类轮转**：`category = 分类列表[dayIndex % 分类数]`，再在该分类内按 `dayIndex / 分类数` 轮转。分类列表是**从 `questions` 表现查 `DISTINCT category` 动态得到的**（不是写死的），所以导入 500 道题后会自动按 C++ → Linux → MySQL → Redis → 其他数据库 → 网络 → 操作系统 → 算法 八类依次出现，而不是连着几天都是同一类。
- **用 `INSERT IGNORE` 而不是「先查再插」**：`app.multithreaded()` 是多线程的，同一秒可能有多个请求同时触发生成；靠主键 `d` 让先写入的那条生效，随后统一读回，保证所有人看到同一题。
- **题库与排期分表**：题库可以随便增删改，`daily_questions` 一旦写入就不动，历史题目不会因为改题库而跳变（被删掉的题目在历史列表里显示为空）。

### 16.2 答案为什么不跟题目一起返回

`GET /api/daily` 只返回题干，答案要单独请求 `GET /api/daily/answer?id=`。否则打开 F12 看一眼接口就剧透了——前端的「查看答案」按钮就是按这个思路做的。

答案以 Markdown 渲染，所以可以直接写代码块和 `mermaid` 图表（复用文章页同一套 `markdown.js`）。

### 16.3 连续打卡

看答案时服务端往 `daily_seen` 写一条 `(今天, blog_anon)`（`INSERT IGNORE`，一天一条）。`streak` 的计算规则：

- 今天已看 → 从今天往前数；
- 今天还没看 → 从昨天往前数（今天没过完，不算断）；
- 中间缺一天 → 归零。

最多回溯 400 天。**匿名身份绑定浏览器**：清 Cookie / 换设备 / 无痕都会归零重来，这是不登录方案的能力边界（同[第十五章](#十五匿名评论身份blog_anon)）。

### 16.4 题库维护

两种方式，按需要选。

**① 导入种子题库（推荐首次部署）**

```bash
# <用户> 填你实际连库的账号；没建专用账号就直接写 root（脚本和 root 完全兼容）
mysql -u <用户> -p --default-character-set=utf8mb4 blogdb < tools/seed_questions.sql
```

> 导入必须用 **utf8mb4**：脚本开头已有 `SET NAMES utf8mb4;`，命令行再加
> `--default-character-set=utf8mb4` 双保险。`questions` 的数据应当是**真 utf8mb4 中文**；
> 若导完之后接口读出来仍是 `?`，那是**应用连接的字符集**问题、不是导入问题 ——
> 见 [13.8](#138-中文变成-每日一题--题库乱码)，**不要**清表重导。

> 账号名取决于你有没有执行 [4.2 创建专用数据库账号](#42推荐创建专用数据库账号)：
> 建了就用 `blog`，**没建就用 `root`** —— 两者都能跑这个脚本（只用到临时表 + `INSERT`，root 权限足够）。
> 库名要和服务端的 `MYSQL_DB` 保持一致，默认是 `blogdb`。

`tools/seed_questions.sql` 含 **500 道题**（C++ 100 / Linux 90 / MySQL 70 / Redis 40 / 其他数据库 40 / 网络 55 / 操作系统 55 / 算法 50），覆盖语言特性与对象模型、Linux 系统与运维、存储引擎/索引/事务、Redis 数据结构与高可用、PostgreSQL/NoSQL/分布式数据库、TCP/HTTP 与网络安全、进程线程内存与并发、排序/查找/动态规划等。脚本**可重复执行**：先导入临时表，再按「分类 + 题干」判重插入，已存在的题目不会被覆盖 —— 手动改过的题不会被脚本冲掉。

> **题库由生成器维护，不要手改 SQL。** 题面数据放在 `tools/qbank/*.py`（每类一个模块，
> 元素为 `(category, tags, difficulty, question, answer)`），改题后重跑
> `python tools/gen_seed.py` 重新生成 `tools/seed_questions.sql`。生成器会校验：
> ① 每条结构合法；② **分类分布与 `EXPECTED` 完全一致**（防止漏题）；③ **`(分类, 题干)` 去重键唯一**；
> 并统一做 SQL 转义（`\` → `\\`、`'` → `''`），避免手写 SQL 时的字面量断裂。
> 其中 `tools/qbank/existing.py` 由 `tools/_extract_existing.py` 从旧 SQL 无损提取，请勿手改。

> **脚本不依赖服务端先启动。** `questions` 表平时由服务端启动时创建（`initTable()`），
> 而种子脚本第一步自带 `CREATE TABLE IF NOT EXISTS questions(...)`（DDL 与 `database.cpp` 保持一致，
> 已存在则为空操作），所以「先导库再编译重启」和「先编译重启再导库」两种顺序都能跑通。
> 若跳过这步直接用临时表复制，会出现 `ERROR 1146 (42S02): Table 'blogdb.questions' doesn't exist`。

**② 站长的出题页 `/daily/question`**

用主管理员登录后，`/daily` **左侧栏**（历史题目下方的「题目管理」卡）点**「添加题目」**即进入该页
（路由与 `/admin` 同级校验：未登录跳 `/login`、非站长跳 `/`）：

- 表单含分类、标签、难度（基础/进阶/困难）、状态（草稿/已发布）、题干与答案（Markdown）；
- **答案带「预览」按钮**，直接复用文章页的 `markdown.js` 渲染（含代码高亮与 mermaid），不用来回切页面看效果；
- 分类用 `<datalist>` 做输入联想，候选项来自题库现有的 `DISTINCT category`，也允许直接输入新分类
  （新分类导入后会自动参与每日轮转，见 [16.1](#161-选题机制不用定时任务)）；
- **带 `?id=N` 时同一页面复用为编辑页**：拉取 `/api/questions/<id>` 回填并改标题为「修改题目 #N」；
  新增成功后**留在本页并清空表单**，方便连续录入；修改成功则回到 `/daily`；
- 列表请求带 `with_drafts=1`，草稿会打「草稿」标记。**草稿不会进入每日排期**（选题只取 `status=1`）。

前端脚本按用途拆成四个文件，避免列表页背上编辑器的逻辑：

| 文件 | 作用 |
|---|---|
| `static/js/daily-common.js` | 共用工具（`apiRequest` 带 GET 重试、`showToast`、`esc` / `escapeAttr`、错误文案） |
| `static/js/daily.js` | `/daily`：今日题目、题库列表、历史题目、删除 |
| `static/js/daily-q.js` | `/daily/q/<id>`：题目详情（题干 + 答案 + 右栏同分类相关题及其显隐） |
| `static/js/daily-question.js` | `/daily/question`：新增 / 回填编辑 / 保存 / 答案预览 |

> `daily-common.js` 必须在这几个脚本**之前**加载（见 `static/daily.html`、`static/daily-q.html`、
> `static/daily-question.html` 的 `<script>` 顺序）。

**草稿的价值**：AI 生成或从别处摘来的题目先落草稿，人工核对答案后再发布 —— 面试题答案写错比没有更糟。

### 16.5 题目详情页

`/daily/q/<id>` 是**公开只读**的题目详情页，历史题目、题库条目的题干与「详情」都链到这里：

```
GET /api/daily/question?id=<id>          # 一次取全，避免详情页多次往返
      ↓
{ success, id, category, tags, difficulty, question, answer,
  date,          ← 该题最近一次被排为「每日一题」的日期（从未排期则为空串）
  siblings[] }   ← 同分类相关题（最多 6 道，RAND() 取，每次进来看的不完全一样）
```

- **为什么要单独开一个接口**：`/api/questions/<id>` 是主管理员的编辑回填接口（含草稿、含 `status`），
  不能给访客；而公开能拿答案的 `/api/daily/answer?id=` 又不含题干。所以新开
  `GET /api/daily/question?id=`，**只放行 `status=1` 的题目**，草稿一律返回「题目不存在或尚未发布」。
- **详情页不吃匿名打卡**：这是刻意的。在 `/daily` 展开答案算「今天作答」，而详情页是查资料 ——
  否则随手点开几道历史题的详情，当天就被记成已完成，连续天数的意义会被稀释。
- **日期优先取 URL 的 `?d=`**：历史题目点进来时带 `?d=YYYY-MM-DD`（同一道题可能被排期多次，
  那次点击的日期最精确），没有才退回接口给的 `date`。据此切换徽章文案「每日一题 / 题库题目」。
- **答案默认展开**：点进详情页的意图就是看答案，不必再点一次；答案走 `markdown.js`，代码高亮与 mermaid 都可用。
- **草稿题在列表里不给详情入口**：草稿只有站长看得到，而公开接口只放行已发布题目，
  所以 `buildBankItems()` 对 `status=0` 的题只保留「编辑 / 删除」，避免点进去必然 404。
- **页面是双列**：主栏 860px 读题（题干 + 参考答案），右栏 280px 放**同分类相关题**，
  右栏是吸顶卡片 —— 与文章页目录 `.post-toc`、`/daily` 右栏同一套做法（容器 1180px 也与文章页对齐）。
- **没有相关题时右栏整栏收起**：`siblings` 为空（或加载失败）时隐藏右栏，并撤掉 `.has-related`
  让主栏回到**居中单列** —— 否则右侧会留一张空卡片，主栏还被一条无内容的列挤窄。
- 响应式：**≤1080px**（与文章页目录同一断点）相关题落回主栏下方，改为整宽卡片 ——
  不退化成隐藏，它是页面上唯一的「继续读」入口。

### 16.6 已知边界

- **分类名称直接参与轮转**：改分类名相当于换了一批题，历史排期不受影响，但后续轮转节奏会变。
- **`ORDER BY RAND()` 只适合小题库**（几千题以内毫无压力），题量到十万级需要改成按 id 随机取。
  （详情页的「同分类相关题」同理。）
- 题库为空时首页卡片**自动隐藏不占位**，`/daily` 会给出空状态提示。

## 十七、已知限制与待办

### 17.1 已知限制

- **端口写死 8080**，不支持环境变量配置。
- **会话存内存**，重启后所有人需重新登录；多实例部署无法共享登录态。
- **单数据库连接**（所有查询串行执行）+ 多线程 HTTP，高并发下数据库访问是瓶颈；`checkConnection()` 会 `mysql_ping` 自动重连。
- **Mermaid 依赖外网 CDN**，离线部署需自行本地化。
- **初始管理员为 `admin@localhost`**，与登录页默认补全的 `@lazycat.com` 不一致（见 [7.3](#73-首次启动与初始管理员)）。
- **匿名评论身份绑定浏览器**：清 Cookie / 换设备即丢失对自己旧评论的管理权（详见 [第十五章](#十五匿名评论身份blog_anon)）。
- **点赞去重仍是纯前端 `localStorage`**，清缓存即可重复点赞，服务端无记录。
- **每日一题的连续打卡同样绑定浏览器**（详见 [16.3](#163-连续打卡)）。

### 17.2 build/ 目录被误纳入版本控制

`build/` 是 CMake 中间产物，目前有文件被提交进了 Git（含 `CMakeCache.txt`，里面有本机绝对路径）。建议清理：

```bash
echo "build/" >> .gitignore
git rm -r --cached build
git commit -m "chore: 移除误纳入版本控制的 build/ 中间产物"
```

> 执行前确认没有人在 `build/` 里放需要保留的东西。

### 17.3 待办

- [ ] 端口、上传目录等改为可配置（环境变量 / 配置文件）
- [ ] 会话持久化到数据库或 Redis，支持多实例
- [ ] 数据库连接池化，避免单连接串行
- [ ] 初始管理员邮箱改为可配置，统一为 `@lazycat.com`
- [ ] 每日一题：支持按收藏/错题重练，以及题库导入的 CSV/Markdown 格式
- [ ] 补齐自动化测试（现有 `tools/repro_list.mjs` 仅覆盖首页渲染）

---

## 附录：把 Crow 源码合入本仓库的历史操作

`Crow/` 最初是以子模块形式引入的，后来改为直接合入：

```bash
git rm --cached Crow          # 删除父仓库的子模块指针记录
rm -rf Crow/.git              # 删除 Crow 内部的 .git
git add Crow                  # 重新作为普通文件纳入版本控制
```

这也是现在**不需要单独 clone 和 install Crow** 的原因。
