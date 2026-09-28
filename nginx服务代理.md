# 域名接入网站服务部署文档（Nginx 反向代理 + HTTPS）

本文档记录将域名 `lazycat.cc` 接入基于 Crow (C++) 框架的博客网站服务的完整过程，包括 Nginx 反向代理、HTTPS 证书、ICP 备案号展示等。

## 一、整体架构

```
用户浏览器 → https://lazycat.cc (443) → Nginx → http://127.0.0.1:8080 → task_server (Crow)
```

- Nginx 对外只开 80/443，负责 SSL 终止 + 反向代理。
- `task_server` 跑在 8080，不需要对外暴露（更安全）。

## 二、环境信息

| 项目 | 值 |
|------|-----|
| 服务器 | 腾讯云 CVM |
| 操作系统 | OpenCloudOS 9.6（RHEL 9 系，使用 `dnf`） |
| 公网 IP | 154.8.185.169 |
| 内网 IP | 10.2.0.17 |
| 域名 | lazycat.cc（DNS 托管于 DNSPod / 腾讯云云解析） |
| 备案号 | 冀ICP备2026039047号 |
| 数据库 | MariaDB（服务名 `mariadb.service`，库名 `blogdb`） |
| 应用端口 | 8080 |

## 三、前置条件（腾讯云控制台手动操作）

这三步必须在腾讯云控制台完成，在服务器上操作无效：

1. **ICP 备案**：国内服务器上未备案的域名访问 80/443 会被直接拦截，必须先完成备案。
2. **安全组放行**：放行入方向 TCP `80`、`443`（来源 `0.0.0.0/0`）。
3. **DNS 解析**：在「云解析 DNS」为域名添加两条 A 记录：

| 主机记录 | 记录类型 | 记录值 |
|---------|---------|--------|
| `@` | A | 154.8.185.169 |
| `www` | A | 154.8.185.169 |

> 验证 DNS 是否生效（绕过本地/公共缓存，直查权威 NS）：
> ```bash
> nslookup -type=A lazycat.cc litchi.dnspod.net
> ```

## 四、部署步骤

### 1. 配置 systemd 服务，让 task_server 常驻

```bash
sudo tee /etc/systemd/system/blog.service > /dev/null <<'EOF'
[Unit]
Description=WebBasedCrow Blog Server
After=network-online.target mariadb.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/wb/projects/WebBasedCrow/bin
ExecStart=/home/wb/projects/WebBasedCrow/bin/task_server
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now blog
sudo systemctl status blog   # 确认 active (running)
```

### 2. 安装 Nginx

> 注意：OpenCloudOS 9 的 `/etc/dnf/dnf.conf` 默认 `exclude` 了 nginx，需临时覆盖排除项：

```bash
dnf install -y --setopt=exclude='' nginx
```

### 3. 配置反向代理（HTTP）

```bash
sudo tee /etc/nginx/conf.d/lazycat.conf > /dev/null <<'EOF'
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
EOF

sudo nginx -t
sudo systemctl enable --now nginx
```

### 4. 申请 HTTPS 证书（certbot + Let's Encrypt）

```bash
dnf install -y certbot python3-certbot-nginx

certbot --nginx -d lazycat.cc -d www.lazycat.cc \
  --non-interactive --agree-tos \
  --register-unsafely-without-email --redirect
```

certbot 会自动修改 Nginx 配置：添加 443 SSL 监听，并配置 HTTP → HTTPS 301 跳转。

### 5. 启用证书自动续期（关键，别漏）

certbot 安装的 `certbot-renew.timer` 默认是 **disabled**，必须手动启用，否则证书到期不会自动续期：

```bash
systemctl enable --now certbot-renew.timer
systemctl list-timers certbot-renew.timer   # 确认下次触发时间
```

### 6. 补联系邮箱（可选但推荐）

申请证书时未绑定邮箱，建议补上，以便收到证书到期 / 续期失败提醒：

```bash
certbot register --update-registration -m your@example.com
```

### 7. 网站页面添加 ICP 备案号

- 在 `static/` 下所有 HTML 页面的 `</body>` 前插入：

```html
    <footer class="site-footer">
        <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener">冀ICP备2026039047号</a>
    </footer>
```

- 在 `static/css/style.css` 末尾添加样式：

```css
.site-footer {
    text-align: center;
    padding: 24px 16px 32px;
    font-size: 13px;
    color: var(--text-muted);
}

.site-footer a {
    color: var(--text-muted);
    text-decoration: none;
}

.site-footer a:hover {
    color: var(--text-secondary);
}
```

> HTML 是运行时 `readFile` 读取的，改完无需重新编译、无需重启服务。

## 五、验证清单

```bash
# 服务状态
systemctl is-active blog nginx certbot-renew.timer

# 端口监听（应看到 80、443、8080）
ss -tlnp | grep -E ':(80|443|8080)\b'

# HTTPS 访问（本机测试，强制解析绕过本地 DNS 缓存）
curl -s -o /dev/null -w "HTTPS %{http_code}\n" \
  --resolve lazycat.cc:443:154.8.185.169 https://lazycat.cc/

# HTTP 跳转（应返回 301 到 https）
curl -s -o /dev/null -w "HTTP %{http_code} -> %{redirect_url}\n" \
  --resolve lazycat.cc:80:154.8.185.169 http://lazycat.cc/

# 证书信息
certbot certificates
```

最终访问地址：**https://lazycat.cc**

## 六、注意事项

1. **备案是硬门槛**：国内服务器未备案域名无法访问 80/443，海外服务器则无需备案。
2. **DNS 传播延迟**：A 记录加好后，部分公共 DNS（如 114.114.114.114）会缓存旧的负面结果，可能需要几小时才刷新；海外 DNS（8.8.8.8 / 1.1.1.1）通常较快。
3. **数据库密码不要写死在源码**：`src/main.cpp` 通过环境变量读取（`MYSQL_HOST` / `MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_DB` / `MYSQL_PORT`），部署时用 systemd 的 `Environment=` 或 `EnvironmentFile=` 注入，不要把密码提交进 Git。
4. **8080 端口无需对外暴露**：通过 Nginx 反代访问，安全组只开 80/443 即可。

## 七、常见故障：启动失败 `Address already in use`

### 现象

网站打不开（前端提示「网络连接失败」），`journalctl -u blog` 看到：

```
task_server[4081739]: [ERROR   ] Failed to bind to 0.0.0.0:0 - Address already in use
task_server[4081739]: [ERROR   ] Server startup failed. Aborting run().
```

### 两个坑要分清

1. **`0.0.0.0:0` 里的端口 0 是假信息**。Crow 在 `Crow/include/crow/http_server.h:87-90` 打印的是
   `acceptor_.address() << ":" << acceptor_.port()`，而这两个值是在 `bind()` **失败之后**读取的，
   此时 endpoint 并未真正绑定，所以端口恒为 0。实际尝试绑定的是 `main.cpp` 里写死的 **8080**。
2. **Crow 已经开了 `SO_REUSEADDR`**（`http_server.h:80` 的 `set_option(Acceptor::reuse_address_option())`），
   因此 TIME_WAIT 不会触发该错误。报 `Address already in use` 只可能是**另一个进程仍以 LISTEN 状态占着 8080**——
   典型场景：服务崩溃 → systemd 立刻拉起新进程 → 旧进程还没退出 → 新进程绑定失败 → 反复重启失败。

### 应急恢复

```bash
sudo systemctl stop blog
sudo pkill -f task_server            # 清掉残留进程
sudo ss -tlnp | grep ':8080'         # 确认已无占用（应无输出）
sudo systemctl start blog
systemctl is-active blog             # 应为 active
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/api/posts   # 应为 200
```

### 根治：加固 systemd unit（等端口释放 + 快速停止 + 重启限流）

```bash
sudo tee /etc/systemd/system/blog.service > /dev/null <<'EOF'
[Unit]
Description=WebBasedCrow Blog Server
After=network-online.target mariadb.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/wb/projects/WebBasedCrow/bin
Environment=MYSQL_HOST=localhost
Environment=MYSQL_USER=root
Environment=MYSQL_PASSWORD=你的数据库密码
Environment=MYSQL_DB=blogdb
# 启动前等 8080 释放（最多 30s），避免旧进程未退出导致 bind 失败
ExecStartPre=/bin/sh -c 'for i in $(seq 1 30); do ss -tln | grep -q ":8080 " || exit 0; sleep 1; done; exit 0'
ExecStart=/home/wb/projects/WebBasedCrow/bin/task_server
KillSignal=SIGTERM
TimeoutStopSec=5          # 5 秒不退出就 SIGKILL，避免端口长期占用
Restart=always
RestartSec=5              # 给端口释放留足时间
StartLimitIntervalSec=120
StartLimitBurst=5         # 2 分钟内最多重启 5 次，避免疯狂重启刷爆日志

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl restart blog
sudo systemctl status blog
```

### 查崩溃根因（为什么会重启）

```bash
# 崩溃前后 60 行日志
journalctl -u blog --since "2026-09-28 09:40" -o short-precise | tail -60

# 看是否有崩溃 / 异常终止记录
journalctl -u blog | grep -Ei 'terminate|abort|segfault|signal|gone away|FATAL'

# 数据库是否正常
systemctl is-active mariadb
```

> `Restart=always` 会掩盖崩溃：服务挂掉后自动拉起，表面上看只是"卡了一下"。
> 若日志里出现 `MySQL server has gone away` 或 `terminate called after throwing`，
> 说明是数据库连接断开 / 未捕获异常，需按具体堆栈修 `src/database.cpp`。
