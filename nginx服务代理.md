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
3. **数据库密码硬编码**：`src/main.cpp` 中数据库密码写死为 `root/123456`，生产环境建议改为环境变量或配置文件读取。
4. **8080 端口无需对外暴露**：通过 Nginx 反代访问，安全组只开 80/443 即可。
