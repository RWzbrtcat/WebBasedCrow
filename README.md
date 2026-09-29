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
- [十五、已知限制与待办](#十五已知限制与待办)

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

### 4.3 表结构：自动创建，无需手动建表

服务启动时 `DataBase` 构造函数会自动 `CREATE TABLE IF NOT EXISTS`：

| 表 | 内容 |
|---|---|
| `posts` | 文章：标题、正文、简介、作者、`topic`（专栏）、`theme`（主题）、`status`（published/draft）、点赞数、`hidden`、创建/更新时间 |
| `topics` | 专栏（首次启动会用已有文章的 `topic` 去重填充） |
| `comments` | 评论 |
| `settings` | 站点配置（背景图、主题色），键值对 |
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
│   ├── editor.html         # Markdown 编辑器（支持 Mermaid）
│   ├── login.html          # 登录
│   ├── admin.html          # 管理员管理（主管理员可见）
│   ├── profile.html        # 个人资料
│   ├── drafts.html         # 草稿箱
│   ├── hidden.html         # 隐藏文章
│   ├── css/                # style.css（全站样式）、highlight.css
│   ├── js/                 # auth/header/theme/list/post/editor/admin/profile/login/markdown
│   └── uploads/            # 上传图片（gitignore）
├── tools/                  # 开发辅助脚本
│   ├── build_preview.py    # 生成 preview*.html 静态预览
│   ├── repro_list.mjs      # Node 模拟 DOM，回归首页渲染流程
│   └── fixture_*.json      # 线上数据快照（回归用）
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

---

## 十四、API 一览

页面路由：`/` `/post` `/login` `/logout` `/drafts` `/hidden` `/editor` `/admin` `/profile`

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
| GET/POST | `/api/posts/<id>/comments` | 评论列表 / 发表 | 公开 |
| PUT/DELETE | `/api/comments/<id>` | 修改 / 删除评论 | 登录 |
| POST | `/api/upload` | 上传图片（multipart，字段 `image`） | 登录 |
| GET/POST | `/api/topics` | 专栏列表 / 新增 | 读公开、写登录 |
| DELETE | `/api/topics/<id>` | 删除专栏 | 登录 |
| GET | `/api/settings/background` `/api/settings/theme` | 读取站点背景 / 主题色 | 公开 |
| POST | `/api/settings/background` `/api/settings/theme` | 修改站点背景 / 主题色 | 登录 |

---

## 十五、已知限制与待办

### 15.1 已知限制

- **端口写死 8080**，不支持环境变量配置。
- **会话存内存**，重启后所有人需重新登录；多实例部署无法共享登录态。
- **单数据库连接**（所有查询串行执行）+ 多线程 HTTP，高并发下数据库访问是瓶颈；`checkConnection()` 会 `mysql_ping` 自动重连。
- **Mermaid 依赖外网 CDN**，离线部署需自行本地化。
- **初始管理员为 `admin@localhost`**，与登录页默认补全的 `@lazycat.com` 不一致（见 [7.3](#73-首次启动与初始管理员)）。

### 15.2 build/ 目录被误纳入版本控制

`build/` 是 CMake 中间产物，目前有文件被提交进了 Git（含 `CMakeCache.txt`，里面有本机绝对路径）。建议清理：

```bash
echo "build/" >> .gitignore
git rm -r --cached build
git commit -m "chore: 移除误纳入版本控制的 build/ 中间产物"
```

> 执行前确认没有人在 `build/` 里放需要保留的东西。

### 15.3 待办

- [ ] 端口、上传目录等改为可配置（环境变量 / 配置文件）
- [ ] 会话持久化到数据库或 Redis，支持多实例
- [ ] 数据库连接池化，避免单连接串行
- [ ] 初始管理员邮箱改为可配置，统一为 `@lazycat.com`
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
