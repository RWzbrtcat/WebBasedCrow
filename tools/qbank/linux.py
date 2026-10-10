# -*- coding: utf-8 -*-
"""Linux 面试题（新增 90 道）。

字段：(category, tags, difficulty, question, answer)
difficulty: 1 基础 / 2 进阶 / 3 困难
"""

QUESTIONS = [

    (
        "Linux",
        "文件系统,目录结构",
        1,
        r"""Linux 的目录结构是怎样的？FHS 规定了哪些主要目录？""",
        r"""**FHS（Filesystem Hierarchy Standard）** 规定了各目录的用途：

| 目录 | 用途 |
|---|---|
| `/` | 根目录，所有路径的起点 |
| `/bin` | 基础用户命令（现代发行版多为 `/usr/bin` 的软链接） |
| `/sbin` | 系统管理命令 |
| `/etc` | **配置文件**（全文本，`/etc` 不应有二进制） |
| `/home` | 普通用户的家目录 |
| `/root` | root 的家目录 |
| `/tmp` | 临时文件，**重启可能被清空**，所有用户可写（有 sticky 位） |
| `/var` | 可变数据：日志 `/var/log`、缓存 `/var/cache`、数据库文件 |
| `/usr` | 用户程序与只读数据：`/usr/bin`、`/usr/lib`、`/usr/share`、`/usr/local`（本地安装） |
| `/lib` | 共享库与内核模块（常为 `/usr/lib` 的软链接） |
| `/dev` | **设备文件**（`/dev/sda`、`/dev/tty`、`/dev/null`） |
| `/proc` | **虚拟文件系统**，反映内核与进程状态（`/proc/cpuinfo`、`/proc/<pid>`） |
| `/sys` | 虚拟文件系统，暴露设备与驱动模型（sysfs） |
| `/boot` | 内核镜像（`vmlinuz`）、initramfs、GRUB 配置 |
| `/opt` | 第三方大型软件（如 `/opt/google`） |
| `/mnt` / `/media` | 临时挂载点 / 可移动介质挂载点 |
| `/srv` | 服务数据（如 web 根目录） |
| `/run` | 运行期数据（PID 文件、socket），tmpfs，重启清空 |

**要点**：
1. **一切皆文件** —— 设备、管道、socket 都有文件路径。
2. `/proc` 和 `/sys` **不占磁盘**，是内核暴露的接口（读它们就是读内核数据结构）。
3. `/etc` 放**配置**、`/var` 放**运行时可变数据**，这是运维备份策略的基础：备份 `/etc` + `/var/lib` 就抓住了大部分状态。
4. FHS 是**约定**不是强制，很多发行版按自己的方式组织（如 `/bin` → `/usr/bin` 合并，`usrmerge`）。""",
    ),
    (
        "Linux",
        "硬链接,软链接",
        1,
        r"""硬链接和软链接（符号链接）有什么区别？""",
        r"""| 维度 | 硬链接 | 软链接（符号链接） |
|---|---|---|
| 本质 | **另一个目录项指向同一个 inode** | 一个独立文件，内容是目标路径字符串 |
| inode | 与源文件**相同** | 有**自己独立的 inode** |
| 跨文件系统 | ❌ 不可以 | ✅ 可以 |
| 指向目录 | ❌ 一般不允许（除 `.`/`..`） | ✅ 可以 |
| 删除源文件 | 文件仍存在（链接计数 -1） | 变成**悬空链接**（dangling） |
| `ls -l` 显示 | 普通文件 | `l` 开头，显示 `目标 -> 路径` |
| 创建命令 | `ln src dst` | `ln -s src dst` |
| 相对路径 | 无所谓（同一 inode） | **相对路径相对于链接所在目录**（易踩坑） |

```bash
echo hi > a.txt
ln a.txt hard.txt      # 硬链接
ln -s a.txt soft.txt   # 软链接
ls -li                 # 看 inode：hard.txt 与 a.txt 相同，soft.txt 不同
rm a.txt
cat hard.txt           # ✅ 仍可读（inode 还有引用）
cat soft.txt           # ❌ No such file or directory
```

**inode 与链接计数**：`stat` 里的 `Links` 字段就是硬链接数。文件数据在**链接计数为 0 且没有进程打开**时才真正释放。

**实践用途**：
- **软链接**：版本切换（`/usr/bin/python -> python3.11`）、跨分区、指向目录。
- **硬链接**：备份（`rsync --link-dest` 做增量快照）、节省空间的多份"副本"。

**坑**：
1. `ln -s` 的**相对路径**是相对"链接文件所在目录"，不是当前工作目录 —— 用绝对路径最稳。
2. 软链接的权限位无意义（`lrwxrwxrwx`），权限由**目标**决定。
3. `rm` 一个软链接删的是链接本身；`rm -r link/`（带斜杠）会**跟随进入目标目录**，很危险。
4. `cp -a` 保留软链接，`cp -L` 解引用；`rsync` 用 `-l` 保留链接。""",
    ),
    (
        "Linux",
        "权限,chmod,umask",
        1,
        r"""Linux 的文件权限模型是怎样的？`umask` 有什么用？""",
        r"""**三组权限 × 三个对象**：

```
-rwxr-xr--  1 user group  size date file
 │└┬┘└┬┘└┬┘
 │ │  │  └── others: r--
 │ │  └───── group : r-x
 │ └──────── owner : rwx
 └────────── 类型：- 普通文件 / d 目录 / l 符号链接 / c 字符设备 / b 块设备 / s socket / p 管道
```

**数字表示**：`r=4, w=2, x=1`，三位 8 进制，如 `755`（rwxr-xr-x）、`644`（rw-r--r--）。

**目录权限的含义（容易搞错）**：
- `r`：能**列出**目录内容（`ls`）。
- `w`：能在目录里**创建/删除/重命名**条目。
- `x`：能**进入**目录（`cd`）并访问其中的文件（**访问文件内容必须对目录有 x**）。
- 只给 `w` 不给 `x`：能创建文件但列不出来。
- **删除文件看的是目录的 `w`**，与文件自身权限无关！

**`chmod`**：
```bash
chmod 755 file          # 数字
chmod u+x,g-w file      # 符号：u/g/o/a + - = r/w/x
chmod -R 750 dir        # 递归
```

**`chown` / `chgrp`**：
```bash
chown user:group file
chown -R www-data:www-data /var/www
```

**`umask`**：新文件/目录的**权限掩码**，权限 = 默认值 **按位与非** umask。
- 文件默认最大 `666`，目录默认最大 `777`（出于安全，新建文件默认不带 `x`）。
- 常见 `umask 022` → 新文件 `644`、新目录 `755`。
- `umask 077` → 新文件 `600`、新目录 `700`（私密）。
```bash
umask          # 查看
umask 027      # 设置（当前 shell 有效；持久化写到 ~/.bashrc 或 /etc/profile）
```

**默认 ACL**：需要更细粒度的权限（给特定用户额外权限）时用 `setfacl`/`getfacl`。

**注意**：
1. `root` **无视权限检查**（除执行位），这是"以 root 跑服务很危险"的原因之一。
2. 权限检查顺序：owner → group → others，**命中即停**（不是取并集）。
3. 用户属于多个组时，只要**任一所属组**匹配即可。""",
    ),
    (
        "Linux",
        "suid,sgid,sticky",
        2,
        r"""SUID、SGID、Sticky bit 分别是什么？""",
        r"""这三个是**特殊权限位**，出现在 `ls -l` 的 `x` 位置上：

| 位 | 数字 | owner 位显示 | 含义 |
|---|---|---|---|
| SUID | 4000 | `s`（无 x 时 `S`） | 执行时**以文件属主身份**运行 |
| SGID | 2000 | group 位显示 `s` | 执行时以**属组身份**运行；**目录上**表示新建文件继承目录的属组 |
| Sticky | 1000 | others 位显示 `t` | **目录上**：只有文件属主/目录属主/root 能删除 |

```bash
chmod u+s file    # SUID
chmod g+s dir     # SGID（目录）
chmod +t dir      # Sticky
```

**典型用途**：

1. **SUID**：`/usr/bin/passwd` 是 root 所有且带 SUID，普通用户执行时临时获得 root 权限去改 `/etc/shadow`。
2. **SGID 目录**：团队共享目录（如 `/var/www`），所有新建文件自动属于该组，方便协作。
3. **Sticky**：`/tmp` 通常是 `drwxrwxrwt` —— 任何用户可写，但**只能删自己的文件**。

**安全注意**：
1. **SUID 是提权高危点**：任何 SUID 程序有漏洞都可能被用来提权。审计命令：
```bash
find / -perm -4000 -type f 2>/dev/null      # 找所有 SUID 文件
find / -perm -2000 -type f 2>/dev/null      # SGID
```
2. **SUID 对脚本无效**：`#!/bin/sh` 的脚本加 SUID 会被内核忽略（历史安全问题），只对二进制生效。
3. **SUID 对目录无意义**。
4. **SUID 只改变 euid**，不改变 ruid（`getuid`/`geteuid` 可区分）。
5. 挂载 `nosuid` 的分区上 SUID 位不生效（`/tmp`、`/home` 常这样挂载）。
6. **不要给 shell 加 SUID** —— 等于给所有人 root。
7. Capabilities（`setcap`）是 SUID 的更细粒度替代：只授予某个能力（如 `cap_net_bind_service` 绑定低端口）而非完整 root。""",
    ),
    (
        "Linux",
        "进程,fork,exec",
        1,
        r"""`fork`、`vfork`、`exec` 分别做什么？它们怎么配合？""",
        r"""**`fork()`**：创建一个**子进程**（父进程的完整副本）。
- 返回值：父进程得到**子进程 PID**，子进程得到 **0**，失败返回 **-1**。
- 子进程拥有独立的地址空间（**写时复制 COW**，见后文）、独立的文件描述符表（**但共享打开文件偏移**）。
- 继承：环境变量、信号处理、当前工作目录、umask；不继承：PID、父进程 ID、挂起的信号、文件锁。

```c
pid_t pid = fork();
if (pid == 0) {
    // 子进程
} else if (pid > 0) {
    // 父进程：pid 是子进程 PID
} else {
    perror("fork");
}
```

**`vfork()`**：创建子进程但**不复制地址空间**，子进程直接使用父进程的内存，且**父进程会被挂起**直到子进程 `exec` 或退出。用于"fork 立刻 exec"的场景以省去页表复制。**现代 Linux 上 `fork` 因 COW 已足够快，`vfork` 基本不需要**（且使用不当会 UB）。`posix_spawn` 是更安全的替代。

**`exec` 家族**：**替换**当前进程的映像（不创建新进程）。
```c
execl("/bin/ls", "ls", "-l", NULL);
execv("/bin/ls", argv);
execvp("ls", argv);      // 按 PATH 查找
execle(...); execve(...); // 带环境变量 / 系统调用本身
```
- 成功后**不返回**（原代码被完全替换）；失败返回 -1。
- **`execve` 是唯一的系统调用**，其余都是库函数封装。
- 注意：`exec` 后**文件描述符默认保留**（除非设置 `FD_CLOEXEC`），这是"泄漏 fd 到子进程"的常见坑。

**经典配合模式**：
```c
pid_t pid = fork();
if (pid == 0) {
    execvp("ls", argv);      // 子进程变成 ls
    _exit(127);              // exec 失败才到这里，用 _exit 避免刷新父进程的 stdio 缓冲
}
int status;
waitpid(pid, &status, 0);    // 父进程等待
```
**注意用 `_exit` 而不是 `exit`**：`exit` 会刷新 stdio 缓冲并执行 `atexit` 处理器，在 fork 后被调可能**重复输出**父进程未刷新的缓冲内容。""",
    ),
    (
        "Linux",
        "僵尸进程,孤儿进程",
        2,
        r"""什么是僵尸进程和孤儿进程？怎么处理？""",
        r"""**孤儿进程（orphan）**：父进程先退出，子进程还在运行。
- **处理**：由 `init`（PID 1，现代系统是 `systemd`）**收养**，孤儿进程的父进程变为 1。
- **无害**，是正常现象。

**僵尸进程（zombie）**：子进程已退出，但父进程**没有调用 `wait`/`waitpid` 回收**，内核保留其退出状态（PID、退出码、资源使用）。
- **不占用内存**（地址空间已释放），但**占用一个 PID 和内核 task_struct**。
- `ps` 中状态显示为 **`Z`**，CMD 显示 `<defunct>`。
- **危害**：PID 数量有限（`/proc/sys/kernel/pid_max`，默认 32768）。僵尸堆积会耗尽 PID → 无法创建新进程。

**产生僵尸的原因**：父进程没调 `wait`，且父进程仍在运行。

**处理办法**：

1. **父进程正确 `wait`**：
```c
// 方式 A：同步等待
waitpid(pid, &status, 0);

// 方式 B：SIGCHLD 信号里回收
signal(SIGCHLD, SIG_IGN);   // 最简单：让内核自动回收（POSIX 允许）

// 方式 C：SIGCHLD handler 里循环 waitpid(-1, ..., WNOHANG)
void handler(int) {
    int st;
    while (waitpid(-1, &st, WNOHANG) > 0) {}
}
struct sigaction sa{};
sa.sa_handler = handler;
sa.sa_flags = SA_RESTART | SA_NOCLDSTOP;
sigaction(SIGCHLD, &sa, nullptr);

// 方式 D：双重 fork
// 1. fork 子进程；2. 子进程再 fork 孙进程；3. 子进程立即退出（父进程回收它）
// 4. 孙进程由 init 收养，永远不会变成僵尸
```

2. **清理已有僵尸**：僵尸**不能被杀**（`kill -9` 无效，因为它已经死了）。只能：
- **杀掉父进程**，让僵尸被 init 收养并由 init 回收。
```bash
ps -eo pid,ppid,stat,cmd | awk '$3 ~ /^Z/'
kill <父进程PID>
```

3. **排查**：`ps aux | grep -w Z`、`top` 看 `zombie` 计数。

**面试延伸**：`waitpid` 的 `WNOHANG` 表示非阻塞；`SA_NOCLDWAIT` 标志让内核不产生僵尸；容器里 PID 1（应用自己）**必须正确回收子进程**，否则僵尸堆积 —— 这是"容器里不要用 `sh -c` 当 PID 1"的原因之一（`sh` 不太会转发信号和回收）。""",
    ),
    (
        "Linux",
        "守护进程,daemon",
        2,
        r"""怎么把一个程序变成守护进程（daemon）？""",
        r"""**daemon 的特征**：脱离控制终端、在后台运行、通常以 PID 1 为父进程。

**经典 daemonize 步骤**（`man 7 daemon`）：

```c
// 1. fork，父进程退出 → 子进程不是进程组组长
pid_t pid = fork();
if (pid > 0) exit(0);

// 2. setsid 创建新会话，成为会话首进程，脱离控制终端
if (setsid() < 0) exit(1);

// 3.（可选）第二次 fork，确保不是会话首进程 → 无法再获取控制终端
pid = fork();
if (pid > 0) exit(0);

// 4. 设置 umask，避免继承干扰
umask(0);

// 5. 切换工作目录到 /（避免阻碍文件系统卸载）
chdir("/");

// 6. 关闭/重定向标准文件描述符
close(STDIN_FILENO); close(STDOUT_FILENO); close(STDERR_FILENO);
int fd = open("/dev/null", O_RDWR);
dup2(fd, STDIN_FILENO); dup2(fd, STDOUT_FILENO); dup2(fd, STDERR_FILENO);

// 7.（可选）写 PID 文件
// 8.（可选）把日志写到 syslog
```

**为什么第 3 步要第二次 fork**：`setsid` 后子进程是会话首进程，**会话首进程可以重新打开控制终端**；再 fork 一次后新进程不是会话首进程，就无法获得控制终端。

**现代做法（推荐）**：
1. **不自己 daemonize**，而是让 **systemd** 管理：
```ini
[Unit]
Description=My Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/myapp
Restart=on-failure
User=appuser
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```
systemd 负责后台化、日志（journald）、崩溃重启、资源限制（cgroup）、依赖顺序。**这是当前的标准答案**。
2. 容器中**不要 daemonize**（PID 1 应前台运行，否则容器立即退出）。
3. 第三方库：`libdaemon`、`daemon(3)`（glibc 提供一次调用版本，但它只 fork 一次、不做 chdir/chdir 的完整语义）。

**注意点**：
1. **日志不要写 `stdout` 后关闭 fd**（会丢日志）—— 交给 journald 或写自己的日志文件。
2. **信号处理**：daemon 应处理 `SIGHUP`（重载配置）、`SIGTERM`（优雅退出）。
3. **PID 文件**要处理陈旧文件（进程已死但文件还在）。
4. **不要继承父进程的 fd**（会阻止文件系统卸载）—— 用 `O_CLOEXEC` 或显式关闭。""",
    ),
    (
        "Linux",
        "信号,signal",
        2,
        r"""Linux 信号是什么？哪些信号不能被忽略？怎么安全地处理？""",
        r"""**信号**是异步通知机制，内核或其他进程发给进程的"软中断"。

**编号范围**：`1~31` 是**标准信号**（不可靠，可能丢失、不排队）；`34~64` 是**实时信号**（排队、有顺序保证）。

**常用信号**：

| 信号 | 编号 | 默认动作 | 说明 |
|---|---|---|---|
| SIGHUP | 1 | 终止 | 终端挂断；daemon 常借它做配置重载 |
| SIGINT | 2 | 终止 | `Ctrl+C` |
| SIGQUIT | 3 | 终止+core | `Ctrl+\` |
| SIGKILL | 9 | 终止 | **不可捕获、不可忽略** |
| SIGSEGV | 11 | 终止+core | 段错误 |
| SIGPIPE | 13 | 终止 | 写已关闭的管道/socket（常需忽略） |
| SIGALRM | 14 | 终止 | 定时器 |
| SIGTERM | 15 | 终止 | 默认的 `kill`，**可被捕获做优雅退出** |
| SIGCHLD | 17 | 忽略 | 子进程状态变化 |
| SIGSTOP | 19 | **停止** | **不可捕获、不可忽略** |
| SIGTSTP | 20 | 停止 | `Ctrl+Z` |
| SIGCONT | 18 | 继续 | 恢复运行 |
| SIGUSR1/2 | 10/12 | 终止 | 用户自定义 |

**不可捕获/忽略的两个**：**SIGKILL（9）和 SIGSTOP（19）** —— 这是"进程一定能被杀死/停止"的最后保障。

**处理方式**：`signal()`（简单，语义因实现而异）、**`sigaction()`（推荐，语义明确）**。

```c
volatile sig_atomic_t g_stop = 0;      // ⚠️ 只能用 volatile sig_atomic_t

void on_term(int) { g_stop = 1; }      // handler 里只做最简单的赋值

struct sigaction sa{};
sa.sa_handler = on_term;
sigemptyset(&sa.sa_mask);
sa.sa_flags = SA_RESTART;              // 自动重启被中断的系统调用
sigaction(SIGTERM, &sa, nullptr);

while (!g_stop) { /* 主循环 */ }
```

**信号处理函数的限制（重要）**：
handler 运行在**异步、可能中断任意代码**的上下文里，**只能调用 async-signal-safe 的函数**（见 `man 7 signal-safety`）。**不能用**：
- `printf`、`malloc`、`free`
- 大多数标准库函数
- 加锁（可能死锁，如果主线程正持有同一把锁）

安全做法：
1. **handler 里只设置一个 `volatile sig_atomic_t` 标志**，主循环检查。
2. 或用 **`signalfd`**（Linux 专有）把信号变成文件描述符，用 `epoll`/`select` 统一处理 —— **事件驱动程序的首选**。
3. 或用 **`self-pipe` 技巧**：handler 里 `write()` 一个字节到管道，主循环从管道读。

**其它要点**：
1. `SA_RESTART` 让被信号中断的系统调用自动重启；不加的话 `read`/`accept` 会返回 `EINTR`，**必须处理**（生产代码的常见 bug 源）。
2. 信号**不排队**：同一标准信号在处理期间又到达，会被合并。
3. `fork` 后子进程继承信号处理设置；`exec` 后自定义 handler 恢复默认（被忽略的仍被忽略）。
4. **多线程**：信号会投递给**任一线程**（不阻塞该信号的），所以常用"专门线程处理信号（`pthread_sigmask` 阻塞其他线程，只在专用线程 `sigwait`）"。
5. `kill -9` 不能被杀死的进程通常是处于**不可中断睡眠（D，磁盘 IO）**。""",
    ),
    (
        "Linux",
        "进程组,会话",
        3,
        r"""进程组、会话、控制终端是什么关系？""",
        r"""**层级关系**：

```
会话（session）
 └── 进程组（process group）  ← 每个组是"作业控制"的单位
      └── 进程
```

- **进程组（PGID）**：一组相关进程，**作业控制的最小单位**（`kill -PGID` 可以发给整个组）。`setpgid()` 修改。
- **会话（SID）**：一组进程组的集合，**会话首进程**是创建会话的进程（`setsid()`）。一个会话通常对应一个登录会话。
- **控制终端（controlling terminal）**：会话可以关联一个终端设备（`/dev/tty`）。**只有会话首进程能打开控制终端**（这也是 daemon 要二次 fork 的原因）。

```bash
ps -o pid,ppid,pgid,sid,tty,comm        # 查看 PID/父/组/会话/终端
ps -eo pid,pgid,sid,tty,cmd
```

**为什么要这样设计（作业控制）**：

```bash
$ sleep 100 &      # 后台作业，新进程组
$ jobs             # 查看作业
[1]+  Running     sleep 100 &
$ Ctrl+Z           # 暂停前台进程组
$ bg %1            # 后台继续
$ fg %1            # 调到前台
```

- 终端驱动根据**前台进程组**决定把 `Ctrl+C`（SIGINT）、`Ctrl+Z`（SIGTSTP）发给谁。
- 后台进程组**读终端**会收到 **SIGTTIN**（默认停止），写终端按 `TOSTOP` 设置可能收到 SIGTTOU —— 防止后台进程抢终端输入。

**关键系统调用**：
| 调用 | 作用 |
|---|---|
| `setpgid(pid, pgid)` | 加入/创建进程组 |
| `setsid()` | 创建新会话（调用者成为会话首进程和新进程组的组长），**脱离控制终端** |
| `tcsetpgrp(fd, pgid)` | 设置终端的前台进程组（shell 做作业控制用） |
| `tcgetpgrp(fd)` | 查询前台进程组 |

**实践影响**：
1. **daemon 必须 `setsid` + 二次 fork**，才能彻底脱离控制终端（否则终端关闭时会收到 SIGHUP 被杀）。
2. **`nohup cmd &`** 是更简单的替代：把 SIGHUP 设为忽略。
3. **shell 脚本里的进程组**：`set -m` 开启作业控制。
4. **容器里的 PID 1** 要处理孤儿进程回收与信号转发（`tini`、`dumb-init` 就是干这个）。
5. **`kill -TERM -1234`** 的负号表示"发送给进程组 1234"（常用于杀整个作业）。""",
    ),
    (
        "Linux",
        "进程,线程,clone",
        2,
        r"""Linux 的线程是怎么实现的？和进程在实现上有什么区别？""",
        r"""**核心答案：Linux 不区分进程和线程**，两者都是 **task_struct**，只是**共享资源的程度不同**。创建都用 `clone()`。

**`clone()` 的 flags 决定共享什么**：

| flag | 含义 |
|---|---|
| `CLONE_VM` | 共享地址空间 |
| `CLONE_FS` | 共享文件系统信息（cwd、umask） |
| `CLONE_FILES` | 共享文件描述符表 |
| `CLONE_SIGHAND` | 共享信号处理函数 |
| `CLONE_THREAD` | 放进同一个线程组（同 PGID/线程组 ID） |
| `CLONE_NEWNS` 等 | 创建新的 namespace（容器的基础） |
| `CLONE_PARENT_SETTID` 等 | 设置 TID |

- **`fork()`** ≈ `clone(SIGCHLD)` —— 什么都不共享。
- **`pthread_create()`** ≈ `clone(CLONE_VM | CLONE_FS | CLONE_FILES | CLONE_SIGHAND | CLONE_THREAD | ...)` —— 共享地址空间、fd 表、信号处理等。

**"线程组"**：同一进程的多个线程属于同一线程组（TGID），**TGID 就是主线程的 PID**。`getpid()` 返回 TGID（所有线程相同），`gettid()` 返回各自的 TID。
```bash
ls /proc/<pid>/task/      # 列出该进程的所有线程（每个 TID 一个目录）
ps -eLf                   # 看线程（LWP 列是 TID）
top -H -p <pid>           # 按线程显示 CPU
```

**线程创建的开销**：
| 项 | fork | pthread_create |
|---|---|---|
| 地址空间 | COW 复制页表 | **共享**，不复制 |
| 内核对象 | 新 task_struct | 新 task_struct |
| 栈 | 新栈 | 新栈（默认 8MB 虚拟） |
| 开销 | 较大（页表复制） | 较小 |

**线程共享/私有**：

| 共享 | 私有 |
|---|---|
| 地址空间（代码、数据、堆） | 栈 |
| 文件描述符表 | 寄存器、errno |
| 信号处理函数 | 信号屏蔽字（mask） |
| 当前工作目录、umask | 线程 ID、调度优先级 |
| 用户/组 ID | 信号挂起集 |

**常见坑**：
1. **`errno` 是线程局部的**（`__thread int errno`），这是正确的设计。
2. **`fork` 在多线程程序中很危险**：子进程只复制**调用 fork 的那个线程**，其他线程的锁可能处于"已加锁但持有者不存在"的状态 → 死锁。**`fork` 之后在 `exec` 之前只能调用 async-signal-safe 函数**。这就是 `posix_spawn` 更受推荐的原因。
3. **`CLONE_VM` + `CLONE_THREAD`** 意味着线程的 `kill(getpid())` 会杀整个线程组。
4. **`vfork`** 也是共享地址空间的一种（父进程挂起）。
5. **"轻量级进程（LWP）"** 是内核视角的线程 —— 历史上 LinuxThreads 用 LWP 实现线程，`ps -L` 显示的就是 LWP。

**延伸**：`/proc/<pid>/status` 的 `Threads:` 字段给出线程数；`/proc/<pid>/task/<tid>/` 下有该线程的完整信息。""",
    ),
    (
        "Linux",
        "上下文切换,调度",
        3,
        r"""什么是上下文切换？开销在哪？Linux 的 CFS 调度器是怎么工作的？""",
        r"""**上下文切换**：CPU 从执行一个任务切换到另一个任务，需要保存/恢复执行状态。

**保存什么**：
- **寄存器**（通用寄存器、PC/指令指针、栈指针、标志寄存器）。
- **程序计数器与栈**。
- **地址空间**（切换进程时才做，需要换页表 → **TLB 刷新**）。
- **内核栈指针**、浮点/SIMD 寄存器状态。
- 调度相关的记账信息。

**开销来源**：
1. **直接开销**：保存/恢复寄存器（几百纳秒）。
2. **TLB 失效**：切换地址空间后 TLB 需重建（进程切换的主要成本）。现代 CPU 有 **PCID/ASID** 减少刷新。
3. **cache 污染**：新任务的工作集不在 L1/L2 里，要重新填充。
4. **模式切换**：用户态 ↔ 内核态（系统调用也涉及，但和上下文切换是两回事）。

实测：一次上下文切换通常 **1~5 微秒**（含 cache 影响）。`vmstat` 的 `cs` 列是每秒上下文切换次数。

**查看**：
```bash
vmstat 1              # cs 列 = context switches/s
pidstat -w 1          # 每进程的 cswch/s（自愿）与 nvcswch/s（非自愿）
cat /proc/<pid>/status | grep ctxt
```

**CFS（Completely Fair Scheduler，完全公平调度器）**：

- **核心思想**：给每个任务记录"已获得的 CPU 时间"（`vruntime`，虚拟运行时间），**总是选 vruntime 最小的任务运行**。
- **红黑树**：就绪任务按 `vruntime` 排序，取最左节点 O(log n)，通常有缓存的最左节点指针 O(1)。
- **权重（weight）与 nice 值**：`vruntime` 的增长速度与权重成反比 —— nice 低（优先级高）的任务 vruntime 增长慢，得到更多 CPU。**nice 值范围 -20 ~ 19，权重按比例分配（每级约 1.25 倍）**，所以 nice 差 10 ≈ CPU 份额差 10 倍。
- **调度周期（`sched_latency`，默认 6ms）** 与 **`min_granularity`（0.75ms）**：周期内每个任务至少分到最小粒度。

```
vruntime += delta_exec * (NICE_0_LOAD / weight)
```

- **新任务与睡眠任务**：`vruntime` 会被"补偿"到不超过 `min_vruntime`，避免长期睡眠的任务醒来后独占 CPU。
- **抢占**：CFS 用 `sched_tick` 定期检查是否需要抢占；也可被更高优先级任务、I/O 唤醒抢占。

**调度类（优先级从高到低）**：
1. `stop_sched_class`（最高，迁移/停机）
2. `dl_sched_class`（Deadline，`SCHED_DEADLINE`）
3. `rt_sched_class`（实时，`SCHED_FIFO`/`SCHED_RR`）
4. `fair_sched_class`（CFS，`SCHED_NORMAL`/`SCHED_BATCH`）
5. `idle_sched_class`（最低）

**其它调度策略**：
| 策略 | 说明 |
|---|---|
| `SCHED_FIFO` | 实时，先进先出，不时间片，直到阻塞或被更高优先级抢占 |
| `SCHED_RR` | 实时，时间片轮转 |
| `SCHED_DEADLINE` | 基于 deadline（EDF），需要 `sched_setattr` |
| `SCHED_BATCH` | 批处理，减少唤醒次数 |
| `SCHED_IDLE` | 最低优先级（nice 19 也不够低时用） |

**EEVDF（新）**：Linux 6.6 起 CFS 被 **EEVDF（Earliest Eligible Virtual Deadline First）** 取代，改善了延迟敏感任务的响应，`sched_latency` 等参数被 `sched_base_slice` 替代。""",
    ),
    (
        "Linux",
        "内存布局,虚拟内存",
        2,
        r"""Linux 进程的地址空间是怎么布局的？""",
        r"""**64 位 Linux 进程地址空间（x86-64 典型布局，从低到高）**：

```
高地址
┌────────────────────────┐ 0x7fff_ffff_ffff
│  内核空间（用户不可访问） │  ← 用户态访问直接 SIGSEGV
├────────────────────────┤ 0x0000_7fff_ffff_ffff（用户空间上界，48 位）
│  栈（stack）↓           │  从高往低增长，默认 8MB
│  ...                   │
├────────────────────────┤
│  共享库 / mmap 区域      │  mmap 分配、共享库、大块 malloc
├────────────────────────┤
│  堆（heap）↑            │  brk 增长，malloc 的小对象
├────────────────────────┤
│  BSS（未初始化全局/静态） │  .bss，运行时清零
├────────────────────────┤
│  数据段（已初始化全局）    │  .data
├────────────────────────┤
│  只读数据（.rodata）      │  字符串字面量、const
├────────────────────────┤
│  代码段（.text）          │  可执行指令
└────────────────────────┘ 0x400000（典型加载地址）
低地址
```

**各段说明**：

| 段 | 内容 | 权限 |
|---|---|---|
| `.text` | 机器指令 | `r-x` |
| `.rodata` | 只读常量、字符串字面量 | `r--` |
| `.data` | 已初始化的全局/静态变量 | `rw-` |
| `.bss` | 未初始化的全局/静态变量（**不占文件空间**，运行时清零） | `rw-` |
| heap | `malloc` 的动态内存，`brk`/`mmap` 扩展 | `rw-` |
| stack | 局部变量、函数调用帧，向下增长 | `rw-` |
| mmap 区 | 共享库、`mmap` 文件映射、大块分配 | 视情况 |

**查看**：
```bash
cat /proc/<pid>/maps        # 内存映射（能看到每个段的地址范围与权限）
cat /proc/<pid>/smaps       # 更详细（RSS、PSS、脏页）
pmap -x <pid>               # 友好的视图
size a.out                  # 显示 text/data/bss 大小
readelf -S a.out            # 段表
```

**要点**：
1. **栈向下增长、堆向上增长**，中间是空闲区域，两者靠近时会"内存耗尽"（实际由 mmap 区域先撞）。
2. **`.bss` 不占磁盘空间**（`ls -l` 的文件大小不含 bss），这是"大数组未初始化不增大可执行文件"的原因。
3. **共享库映射到 mmap 区**，多个进程共享同一份物理页（只读的代码段）。
4. **`malloc` 的实现选择 `brk` 还是 `mmap`**：小分配用 `brk`（堆顶），大分配（默认阈值 `M_MMAP_THRESHOLD` = 128KB）用 `mmap` —— 后者可以直接 `munmap` 归还 OS。
5. **栈大小限制**：`ulimit -s`（默认 8MB）。**递归过深会栈溢出（SIGSEGV）**，不是堆耗尽。
6. **`alloca`/变长数组在栈上分配**，需谨慎。

**相关命令**：`ulimit -a`、`cat /proc/self/maps`、`valgrind --tool=massif`。""",
    ),
    (
        "Linux",
        "分页,页表",
        2,
        r"""Linux 的虚拟内存分页机制是怎样的？多级页表为什么能省内存？""",
        r"""**分页基本模型**：
- 虚拟地址被切成 **页（page）**，物理内存切成 **页框（page frame）**，大小都是 **4KB**（x86-64 默认）。
- **页表**把虚拟页号（VPN）映射到物理页框号（PFN）+ 权限位。

**多级页表**（x86-64 是 **4 级**，5 级可选）：

```
虚拟地址 48 位（有效）：
[ PML4 (9) ][ PDPT (9) ][ PD (9) ][ PT (9) ][ 页内偏移 (12) ]
      ↓          ↓         ↓        ↓
   逐级查表，每级 512 项，每项 8 字节 → 每张表 4KB
```

**为什么多级能省内存**：
- **单级页表**：48 位地址空间需 `2^36` 个页表项 × 8B = **512GB**，无法接受。
- **多级**：只为**实际使用的**地址范围分配中间层表。进程通常只使用地址空间的很小一部分（几百 MB），所以只需几层少数表 → 几 MB 到几十 MB。
- 代价：**一次地址翻译需要多次内存访问**（4 级 = 4 次），完全靠 **TLB** 缓解。

**TLB（Translation Lookaside Buffer）**：
- 缓存"虚拟页 → 物理页"的翻译结果（典型 64~1536 项）。
- **TLB 命中**：一次访问搞定。
- **TLB 未命中**：硬件页表遍历（page walk），多级查表 → 慢几十倍。
- **进程切换需要刷新 TLB**（不同进程页表不同）→ **PCID（Process Context ID）** 允许 TLB 保留多个进程的条目，减少刷新。
- **大页（Huge Pages）** 2MB/1GB：一个大页顶 512/262144 个 4KB 页，**TLB 覆盖范围剧增**，适合数据库/虚拟化。

**页表项的关键标志位**：
| 位 | 含义 |
|---|---|
| Present (P) | 页是否在内存（不在则触发**缺页中断**） |
| Read/Write | 可写？ |
| User/Supervisor | 用户态可访问？ |
| Accessed (A) | 是否被访问过（供 LRU 近似算法用） |
| Dirty (D) | 是否被写过（决定是否需要回写磁盘） |
| NX (No-eXecute) | 不可执行（W^X 安全） |

**`/proc/<pid>/pagemap`** 可以查每个虚拟页映射到哪个物理页（需要 root）。

**相关概念**：
1. **缺页中断（page fault）**：major（需要磁盘 IO）vs minor（只是建立映射/COW）。
2. **写时复制（COW）**：fork 后父子共享只读页，任一方写才真正复制。
3. **匿名页 vs 文件页**：前者无后端文件（堆、栈），后者对应文件（代码、mmap）。
4. **内存回收**：`kswapd` 后台回收，回收不了就 swap 或 OOM。
5. **透明大页（THP）**：内核自动把连续 4KB 页合并成 2MB，减少 TLB miss；但也可能造成**内存碎片和延迟抖动**（`/sys/kernel/mm/transparent_hugepage/enabled` 可关）。

**性能相关计数**：`/proc/vmstat` 的 `pgfault`、`pgmajfault`；`perf stat -e dTLB-load-misses`。""",
    ),
    (
        "Linux",
        "缺页中断,page fault",
        2,
        r"""什么是缺页中断？major fault 和 minor fault 有什么区别？""",
        r"""**缺页中断（page fault）**：CPU 访问的虚拟地址**没有有效的物理页映射**（PTE 的 Present 位为 0）时，触发异常，内核介入处理。

**流程**：
1. CPU 访问虚拟地址 → 硬件查页表 → Present=0 → 触发 #PF 异常。
2. 进入内核，`do_page_fault`：
   - 地址**合法**（在 VMA 里）→ 分配/加载页，更新页表，返回用户态**重试**那条指令。
   - 地址**非法**（不在任何 VMA）→ 发送 **SIGSEGV**。

**两类 fault**：

| 类型 | 含义 | 例子 |
|---|---|---|
| **minor fault**（次要） | 页**已在内存**（page cache 里），只需建立页表映射 | COW 写、共享内存、page cache 命中、THP 拆分 |
| **major fault**（主要） | 需要**磁盘 IO** 才能拿到数据 | 代码段首次加载、文件 mmap 首次读、发生 swap in |

**major fault 慢得多**（毫秒级，含磁盘 IO），minor fault 是微秒级。

**查看**：
```bash
ps -o min_flt,maj_flt -p <pid>
cat /proc/<pid>/stat | awk '{print "min="$10" maj="$12}'
/usr/bin/time -v ./prog          # 输出 Minor/Major page faults
perf stat -e page-faults,major-faults ./prog
```

**触发场景**：
1. **首次访问**：进程启动时代码/数据不在内存 → major fault。
2. **COW**：fork 后写共享页 → minor fault + 分配新页。
3. **堆增长**：`brk`/`mmap` 扩展后首次触碰 → minor fault（匿名页无内容）。
4. **swap in**：页被换出到 swap，访问时 → major fault。
5. **mmap 文件**：读未加载的页 → major fault（从文件读）。
6. **栈增长**：栈自动扩展时 → minor fault。
7. **THP 合并/拆分**：minor fault。

**`MADV_*` 建议**（优化手段）：
```c
madvise(addr, len, MADV_WILLNEED);    // 预读
madvise(addr, len, MADV_DONTNEED);    // 主动释放（匿名页清零）
madvise(addr, len, MADV_HUGEPAGE);    // 建议使用大页
madvise(addr, len, MADV_SEQUENTIAL);  // 顺序访问模式 → 加大预读
```

**性能影响与优化**：
1. **大量 major fault = 启动慢**：可用 `MAP_POPULATE`（mmap 时预读）或 `madvise(MADV_WILLNEED)`。
2. **fork 后大量 minor fault**：COW 的必然代价；能避免 fork 就用 `posix_spawn`/`vfork`。
3. **JVM/大型服务启动慢**常常是 page fault 主导 —— 这也是 **AOT/CDS/预热** 有效的原因。
4. **`MAP_HUGETLB` / THP** 大幅减少 fault 次数（一次 fault 覆盖 2MB）。
5. 用 `perf record -e page-faults` 定位 fault 热点。

**面试延伸**：**"缺页中断"其实是异常（exception）而非真正的中断**，但在 Linux 中文语境里通常都叫中断。它发生在**指令执行过程中**，处理完后会**重新执行**触发它的那条指令（区别于系统调用是主动陷入）。""",
    ),
    (
        "Linux",
        "mmap,共享内存",
        2,
        r"""`mmap` 是什么？匿名映射和文件映射有什么区别？""",
        r"""**`mmap`** 把文件或匿名内存映射进进程地址空间，之后用**普通内存访问**读写。

```c
void* mmap(void* addr, size_t len, int prot, int flags, int fd, off_t off);
int munmap(void* addr, size_t len);

// 文件映射（共享）
char* p = mmap(NULL, len, PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0);
p[0] = 'x';                    // 直接改文件内容（脏页会回写）

// 匿名映射（不是文件）
char* a = mmap(NULL, len, PROT_READ|PROT_WRITE,
               MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
```

**两种维度**：

| flags | 含义 |
|---|---|
| `MAP_SHARED` | 修改**可见于其他映射同一对象的进程**，会写回文件 |
| `MAP_PRIVATE` | 写时复制（COW），修改**不写回文件**，其他进程看不到 |
| `MAP_ANONYMOUS` | 无文件后端，内容初始为 0 |
| `MAP_FIXED` | 强制在指定地址（危险，会覆盖已有映射） |
| `MAP_POPULATE` | 预先建立页表（减少后续 fault） |
| `MAP_LOCKED` | 锁定在内存（不换出） |
| `MAP_HUGETLB` | 使用大页 |

| prot | 权限 |
|---|---|
| `PROT_READ` | 可读 |
| `PROT_WRITE` | 可写 |
| `PROT_EXEC` | 可执行 |
| `PROT_NONE` | 不可访问（作为 guard page） |

**文件映射 vs 匿名映射**：

| 维度 | 文件映射 | 匿名映射 |
|---|---|---|
| 后端 | 文件 | 无（swap 作为后备） |
| 数据来源 | 文件内容（按需读入） | 全 0 页 |
| 能否共享 | `MAP_SHARED` 可以 | `MAP_SHARED|MAP_ANONYMOUS` 可以（fork 后共享） |
| 典型用途 | 读大文件、共享内存文件、动态库加载 | `malloc` 大块、线程栈、进程私有内存 |

**用途**：
1. **高效读大文件**：避免 `read` 的内核→用户拷贝，按需分页。
2. **进程间共享内存**：
```c
// 匿名共享（父子进程）
void* shm = mmap(NULL, size, PROT_READ|PROT_WRITE,
                 MAP_SHARED|MAP_ANONYMOUS, -1, 0);   // fork 后父子共享
// 或 POSIX 共享内存对象
int fd = shm_open("/name", O_CREAT|O_RDWR, 0600);
ftruncate(fd, size);
void* p = mmap(NULL, size, PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0);
```
3. **内存映射 I/O**：映射设备寄存器（`/dev/mem`）或 GPU 显存。
4. **动态库加载**：`ld.so` 用 `mmap` 把 `.so` 的代码段（只读、可共享）和数据段（COW）映射进来。
5. **大块内存分配**：glibc 的 `malloc` 对 >128KB 的请求用 `mmap`。

**要点与坑**：
1. **映射长度会向上取整到页边界**，多余部分清零。
2. **`off` 必须是页大小的整数倍**（否则 `EINVAL`）。
3. **`MAP_SHARED` 的写入不保证立即落盘** —— 需要 `msync()` 或依赖内核回写。
4. **`munmap` 后访问是 SIGSEGV**。
5. **文件被 truncate 后访问映射区域 → SIGBUS**。
6. **`MAP_PRIVATE` 的写是 COW**，不改文件；想改文件必须 `MAP_SHARED` + 文件以可写打开。
7. **mmap 不是"零拷贝"的同义词**：仍要走 page cache，只是省了 read 的一次拷贝。
8. **`madvise`** 可优化访问模式（预读、顺序、大页、释放）。

**`/proc/<pid>/maps`** 能看到所有映射区域，包括文件路径与权限。""",
    ),
    (
        "Linux",
        "malloc,brk,mmap",
        2,
        r"""glibc 的 `malloc` 是怎么实现的？`brk` 和 `mmap` 怎么选？""",
        r"""**glibc malloc（ptmalloc2）的层次结构**：

```
进程
 └── arena（每个线程最多一个）        ← 减少锁竞争
      └── heap（主 arena 用 brk，其他 arena 用 mmap）
           └── chunk（分配单元，含 8/16 字节头部）
```

**关键机制**：

1. **chunk 与 bin**：
   - 已释放的 chunk 按大小挂到链表（**bins**）：`fastbins`（小）、`smallbins`、`largebins`、`unsorted bin`。
   - 分配时优先从 bins 里找（**复用，不还给 OS**）。
2. **`brk` vs `mmap` 的阈值**：
   - 请求 < **`M_MMAP_THRESHOLD`（默认 128KB）** → 从堆顶（`brk`）分配。
   - 请求 ≥ 阈值 → 用 `mmap` 单独映射（`munmap` 时能真正归还 OS）。
   - 阈值**动态调整**：如果 `brk` 分配被 `free` 后继续扩张，glibc 会提高阈值（避免 mmap/munmap 频繁系统调用）。
3. **arena 分割**：主 arena 是 `brk`，**其他线程的 arena 用 `mmap` 分配**（默认最多 `8 × 核数` 个 arena）。
4. **`mallopt` 调参**：
```c
mallopt(M_MMAP_THRESHOLD, 256*1024);   // 提高 mmap 阈值
mallopt(M_TRIM_THRESHOLD, 512*1024);   // 控制何时 shrink 堆顶
mallopt(M_ARENA_MAX, 4);               // 限制 arena 数（省内存）
```
环境变量：`MALLOC_ARENA_MAX`、`MALLOC_TRIM_THRESHOLD_`、`MALLOC_MMAP_THRESHOLD_`。

**"内存不还给 OS"的现象**：
```c
// 分配 100MB，free 后 RSS 可能不降
void* p = malloc(100<<20);   // 用 mmap
free(p);                      // 会 munmap，RSS 会降 ✅

// 但如果分配的是很多小块（走 brk），free 后堆顶不一定收缩
```
`malloc_trim(0)` 可以主动收缩堆顶。

**为什么"free 了内存没释放"**：
1. 走 `brk` 的内存，`free` 只把 chunk 还给 malloc 的 bins，**不还内核**（因为堆顶以下的空洞无法释放）。
2. 走 `mmap` 的会 `munmap`，能还给内核。
3. **内存碎片**：小对象穿插导致无法合并大块。

**替代实现**：

| 分配器 | 特点 |
|---|---|
| **glibc ptmalloc2** | 默认，通用，多线程下 arena 会占内存 |
| **jemalloc** | 分 size class + per-CPU arena，碎片少，Redis/Meta 常用 |
| **tcmalloc** | Google，thread cache + 中央堆，性能好 |
| **mimalloc** | 微软，轻量快速 |
| **rpmalloc/snmalloc** | 更现代的轻量选择 |

切换方式：`LD_PRELOAD=/usr/lib/libjemalloc.so ./prog` 或链接时指定。

**排查工具**：
```bash
cat /proc/<pid>/status | grep -E "VmRSS|VmSize"
pmap -x <pid>
malloc_stats()          # glibc 提供，打印 arena 统计
malloc_info(0, stderr)
mtrace()                # 检测内存泄漏
valgrind --tool=massif
heaptrack
```

**注意**：
1. **多线程 + 大量 arena = 内存膨胀**（每个 arena 有独立堆与碎片）→ 设 `MALLOC_ARENA_MAX=2~4`。
2. **`malloc(0)` 返回非 NULL 的唯一指针**（可 free）。
3. **`free` 后指针不清零** → 悬垂指针/双重释放（可用 `MALLOC_PERTURB_` 检测）。
4. **`realloc` 可能搬移**：返回新地址，旧指针失效。
5. **`calloc` 与 `malloc+memset` 的区别**：`calloc` 对 mmap 来的页是"免费清零"（内核保证零页），更快；且能检测乘法溢出。""",
    ),
    (
        "Linux",
        "OOM,内存回收",
        3,
        r"""Linux 的 OOM killer 是什么？内存回收（reclaim）怎么工作？""",
        r"""**内存回收（page reclaim）**：

当可用内存不足时，内核需要**回收（reclaim）**页：
1. **优先回收文件页**（page cache）：干净页直接丢弃，脏页先回写。
2. **回收匿名页**：需要 **swap**（换出到磁盘）。
3. 回收算法是**双 LRU 链表**：
   - **active/inactive × file/anon** 四个链表。
   - 页首次访问进入 inactive；再次访问（Accessed 位）提升到 active。
   - 回收时从 inactive 尾部取。
4. **两种触发路径**：
   - **后台回收**：`kswapd` 在低于 `watermark[low]` 时唤醒（异步，不阻塞）。
   - **直接回收（direct reclaim）**：分配内存的进程发现低于 `watermark[min]` 时**自己同步回收** → **分配延迟抖动**（性能杀手）。
5. **水位线**：`/proc/zoneinfo` 里的 `min/low/high`。`min` 之下触发直接回收并可能 OOM。

**OOM killer**：
- 当**所有回收手段都失败**（没有可回收的页、没有 swap 或 swap 已满）时触发。
- 选择受害者：给每个进程算 **`oom_score`**（基于内存占用、`oom_score_adj`、root 惩罚等），**选分数最高的杀掉**（通常是"占内存最多"的那个）。
- 被杀进程通常收到 **SIGKILL**，日志在 `dmesg` 里能看到 `Out of memory: Killed process ...`。

**调控**：
```bash
# 保护关键进程（-1000 到 1000，越小越不容易被杀）
echo -1000 > /proc/<pid>/oom_score_adj
# 查看分数
cat /proc/<pid>/oom_score
# 完全禁用 OOM killer（危险，可能让系统卡死）
echo 0 > /proc/sys/vm/oom_kill_allocating_task
# cgroup v2 内存限制会先在 cgroup 内触发 OOM
echo 512M > /sys/fs/cgroup/<group>/memory.max
cat /sys/fs/cgroup/<group>/memory.events   # 看 oom 次数
```

**关键内核参数**：
| 参数 | 说明 |
|---|---|
| `vm.swappiness` | 换出匿名页的倾向（0~100，默认 60；数据库常设为 1） |
| `vm.overcommit_memory` | 0 启发式 / 1 总是允许 / 2 严格（不超 CommitLimit） |
| `vm.overcommit_ratio` | 配合 `overcommit_memory=2` |
| `vm.min_free_kbytes` | 保留的最小空闲内存（影响水位线） |
| `vm.vfs_cache_pressure` | 回收 dentry/inode 缓存的倾向 |
| `vm.dirty_ratio` / `dirty_background_ratio` | 脏页比例阈值 |

**`overcommit` 的坑**：默认 `0`（启发式）会**允许过量分配** —— `malloc` 成功但首次访问时 OOM。这就是"`malloc` 返回 NULL 很少见，但进程被 OOM kill"的原因。严格模式（`2`）会让 `malloc` 直接失败。

**排查 OOM**：
```bash
dmesg -T | grep -i -E "oom|killed process"
journalctl -k | grep -i oom
cat /sys/fs/cgroup/memory.events
ps -eo pid,rss,comm --sort=-rss | head
free -m
cat /proc/meminfo | grep -E "MemAvailable|SwapFree|Committed_AS|CommitLimit"
```

**`MemAvailable` vs `MemFree`**：
- `MemFree` 是**完全未使用**的内存。
- **`MemAvailable`** 是"估算了可回收缓存后，应用还能申请的"内存 —— **判断"内存够不够"应该看它**（`free -h` 的 `available` 列）。
- `buff/cache` 大**不是坏事**（是 kernel 的缓存，可随时回收）。

**避免 OOM 的实践**：
1. 在 cgroup 里限制内存，**让 OOM 局限在容器内**而非整机。
2. 关键进程设 `oom_score_adj=-1000`（但容器里要小心）。
3. 应用自己做内存限制和优雅降级。
4. 用 **`earlyoom`/`systemd-oomd`** 在可用内存耗尽前主动杀进程，避免系统卡死。
5. **不要禁用 swap 后又不限制内存**。
6. 监控 `MemAvailable` 与 `pgscan`/`pgsteal`，及早发现内存压力。""",
    ),
    (
        "Linux",
        "page cache,缓冲区",
        2,
        r"""Linux 的 page cache 和 buffer cache 是什么？`free` 里的 `buff/cache` 说明什么？""",
        r"""**page cache**：缓存**文件内容**（以页为单位），加速文件读写。
**buffer cache**：历史上缓存**块设备的原始块**（磁盘元数据、超级块等）。**现代 Linux 两者已合并**（`buffer_head` 依然存在，用于元数据），`free` 里统一显示为 `buff/cache`。

**为什么需要 page cache**：
- 磁盘访问比内存慢几个数量级。
- 读文件时：**先把文件对应的页加载进 page cache**，再从内核空间拷贝到用户空间。
- 写文件时：**先写进 page cache**（标记为脏页），稍后由回写线程异步写磁盘（write-back）。

**回写（writeback）机制**：
- 脏页由 `pdflush`（旧）/ **`flusher` 线程**（现代：每设备一个 `kworker` 线程）异步回写。
- 触发条件：
  - **`dirty_background_ratio`**（默认 10%）：脏页超过此比例，**后台**开始回写。
  - **`dirty_ratio`**（默认 20%）：脏页超过此比例，**写入进程被同步阻塞**直到回写 —— **IO 抖动的主要来源！**
  - **`dirty_expire_centisecs`**（默认 30 秒）：脏页超过此时间必须回写。
- 可用 `fsync()` / `fdatasync()` 强制落盘，`sync()` 同步所有。
- **`O_DIRECT`** 绕过 page cache（数据库常用，自管理缓存）。

**`free` 的输出解读**：
```
               total        used        free      shared  buff/cache   available
Mem:           15Gi       3.0Gi       1.2Gi       200Mi        11Gi        11Gi
Swap:         2.0Gi          0B       2.0Gi
```
- `free`：完全空闲。
- `buff/cache`：**内核缓存**（可回收），**大是好事**（说明文件访问都被缓存了）。
- **`available`**：估算"应用还能用多少" —— **判断内存是否紧张看这个**。
- `used` = total - free - buff/cache。

**常见误区**：
1. ❌ "buff/cache 占了 11G，内存快满了" —— 缓存**随时可回收**，不是泄漏。
2. ✅ 正确看法：看 `available` 和 swap 使用量。
3. **压力测试后 cache 不降**是正常的（内核倾向保留缓存）。

**查看与调优**：
```bash
free -h
cat /proc/meminfo | grep -E "Cached|Dirty|Writeback|Buffers"
# 手动清缓存（测试用，生产别做）
sync; echo 3 > /proc/sys/vm/drop_caches
# 调脏页参数
sysctl vm.dirty_ratio
sysctl vm.dirty_background_ratio
```

**`Cached` 的构成**（`/proc/meminfo`）：
- `Cached`：文件页（page cache）。
- `Buffers`：块设备元数据缓存。
- `SReclaimable`：可回收的 slab（dentry、inode 缓存）。
- `Shmem`：tmpfs 与共享内存（**注意：Shmem 也算在 Cached 里，但不能直接丢弃** —— 有 swap 才能换出）。

**实践建议**：
1. **不要手动 `drop_caches`**（会让性能下降，因为要重新读盘）。
2. **数据库服务器**常用 `O_DIRECT` 或 `posix_fadvise(DONTNEED)` 自管理缓存。
3. **`dirty_ratio` 调低**（如 5%~10%）可以减小 IO 抖动，代价是更频繁的小写入。
4. **tmpfs 占的内存算在 Cached 里**，容器里用 tmpfs 要当心内存限制。
5. **`meminfo` 的 `Cached` 减去 `Shmem` 才是"可丢弃的文件缓存"**。

**相关**：`vmtouch` 工具可查看/控制哪些文件在 cache 里；`fincore` 显示单个文件的缓存页数。""",
    ),
    (
        "Linux",
        "文件系统,inode,VFS",
        2,
        r"""Linux 文件系统的核心概念：inode、dentry、VFS 分别是什么？""",
        r"""**VFS（Virtual File System）**：内核的抽象层，为所有文件系统提供统一接口（`open`/`read`/`write`/`stat`...）。上层系统调用只与 VFS 打交道，下层由具体文件系统（ext4/xfs/btrfs/NFS/tmpfs）实现。

**四个核心对象**：

| 对象 | 说明 | 内存/磁盘 |
|---|---|---|
| **superblock（超级块）** | 文件系统整体信息（大小、块数、inode 总数） | 磁盘 + 内存缓存 |
| **inode（索引节点）** | **一个文件的所有元数据**（类型、权限、大小、时间戳、数据块指针、链接计数） | 磁盘 + 内存 |
| **dentry（目录项）** | 路径中一个名字到 inode 的映射（如 `/etc` 的 `etc`） | **只在内存**（dcache） |
| **file** | 一个进程打开的文件的上下文（当前位置、打开标志、指向 dentry/inode） | 只在内存 |

**关键点：文件名不在 inode 里**。目录文件的内容是「文件名 → inode 号」的列表。

```
/var/log/syslog
  ↑   ↑   ↑
 dentry 链条（每个目录项指向一个 inode）
```

**inode 的内容**：
```
stat /etc/passwd
  File: /etc/passwd
  Size: 2845        Blocks: 8        IO Block: 4096   regular file
Device: 801h/2049d Inode: 262147    Links: 1
Access: (0644/-rw-r--r--)  Uid: (0/root)  Gid: (0/root)
Access/Modify/Change 时间戳
```

**inode 的坑：inode 数量固定**。ext4 在 `mkfs` 时确定 inode 总数（`-N` 参数）：
```bash
df -i                        # 查看 inode 使用率
# 报错 "No space left on device" 但 df 显示有空间 → 很可能是 inode 耗尽
```
**海量小文件**（如邮件队列、session 文件、Docker 层）最容易耗尽 inode。

**为什么"删除文件后空间没释放"**：
- 文件被 `rm` 后，如果**仍有进程打开着**，inode 与数据块不会释放（链接计数 0 但引用计数非 0）。
```bash
lsof +L1                  # 找出已删除但仍被打开的文件
# 找到后：重启/杀掉进程，或 `> /proc/<pid>/fd/<fd>` 清空
```
- 这是"磁盘满了但 `du` 统计不出来"的经典原因（`du` 看目录，不看已删除的打开文件）。

**ext4 的磁盘布局**：
```
[ Boot ][ Super Block ][ Group Descriptors ][ Block Bitmap ][ Inode Bitmap ][ Inode Table ][ Data Blocks ]
                                                    ↑ 这些按块组（block group）重复
```
- **extent**：ext4 用 extent（起始块 + 长度）替代间接块指针，减少元数据、支持大文件。
- **日志（journal）**：写入前先记录日志，保证崩溃一致性（`data=ordered` 默认：只记元数据，数据先写）。
- **延迟分配（delayed allocation）**：写入时先只在 page cache 里分配，回写时才真正分配块 → 减少碎片。

**其它文件系统**：
| 文件系统 | 特点 |
|---|---|
| ext4 | 稳定、通用，主流选择 |
| XFS | 大文件/高并发强，RHEL 默认 |
| Btrfs | 快照、校验和、RAID 内置，但历史上有稳定性问题 |
| ZFS | 最强大（校验、快照、压缩），OS 许可不兼容 Linux 内核 |
| tmpfs | 内存文件系统，重启清空 |
| overlayfs | 联合挂载，Docker 镜像层的基础 |
| FUSE | 用户态文件系统（sshfs、s3fs） |

**相关命令**：`df -h`/`df -i`、`du -sh`、`stat`、`debugfs`、`tune2fs -l`、`mount`。""",
    ),
    (
        "Linux",
        "文件描述符,fd",
        2,
        r"""文件描述符是什么？`open` 时内核做了什么？fd 泄漏怎么排查？""",
        r"""**文件描述符（fd）**是一个**整数索引**，指向进程的**文件描述符表**中的一项。

**三层结构**：

```
进程 A 的 fd 表          系统级打开文件表（open file description）      inode 表
 ┌──────────┐                ┌─────────────────────┐              ┌──────────┐
 │ 0 stdin  │───────────────▶│ 文件偏移、打开标志    │─────────────▶│ inode    │
 │ 1 stdout │────┐           ├─────────────────────┤              ├──────────┤
 │ 2 stderr │    └──────────▶│ 同一个描述（共享偏移）│─────────────▶│ inode    │
 │ 3 (文件)  │───────────────▶│ ...                 │              └──────────┘
 └──────────┘                └─────────────────────┘
```

- **fd 表是进程私有的**。
- **打开文件表是系统级的**：`fork` 后父子共享同一"打开文件描述"，因此**共享文件偏移**。
- **`dup`/`dup2` 让两个 fd 指向同一描述** → 共享偏移与标志。

**标准 fd**：`0` = stdin、`1` = stdout、`2` = stderr。

**`open()` 内核做了什么**：
1. 路径解析（逐级查 dcache，未命中则读目录）。
2. 权限检查。
3. 找到/创建 inode。
4. 在**系统级打开文件表**创建一项（记录偏移、标志）。
5. 在**进程 fd 表**找最小可用槽位，返回该整数。
6. 返回 fd（失败返回 -1，`errno` 说明原因）。

**`O_CLOEXEC`**：让 fd 在 `exec` 时自动关闭 —— **现代代码应该在 `open` 时就加**，否则多线程下 `open` 与 `exec` 之间有竞态（fd 泄漏到子进程）。

**`fork`/`exec` 的行为**：
- `fork`：子进程**复制 fd 表**（指向相同的打开文件描述）。
- `exec`：**除 `FD_CLOEXEC` 的以外全部保留** —— 这是"tcp socket 被继承到子进程"的常见坑。
- 非 CLOEXEC 的 fd 泄漏会让服务进程持有不该持有的连接，导致"重启后端口仍被占用"。

**fd 限制**（三处）：
```bash
ulimit -n                     # 进程级（RLIMIT_NOFILE）
cat /proc/sys/fs/file-max     # 系统级总上限
cat /proc/sys/fs/nr_open      # 单进程可设的最大值上限
cat /proc/sys/fs/file-nr      # 当前已分配/未使用/上限
```
- 软限制与硬限制：`ulimit -Hn`（硬）与 `ulimit -Sn`（软），软不能超硬。
- **`ulimit -n 65535` 只对当前 shell 生效**；持久化要改 `/etc/security/limits.conf` 或 systemd 的 `LimitNOFILE=`。
- **已运行的进程无法提高硬限制**，只能重启。

**fd 泄漏排查**：
```bash
ls -l /proc/<pid>/fd | wc -l                  # 当前 fd 数
ls -l /proc/<pid>/fd | tail                   # 看具体是什么
lsof -p <pid> | wc -l
lsof -p <pid> | awk '{print $5}' | sort | uniq -c | sort -rn   # 按类型统计
cat /proc/<pid>/limits | grep files           # 该进程的 fd 限制
ss -s                                         # 系统 socket 统计
```
**常见泄漏源**：忘记 `close`、异常路径未释放（用 RAII/`unique_ptr<FILE, decltype(&fclose)>`）、socket/`epoll` fd 未关、日志文件反复打开。

**其它要点**：
1. **fd 用尽时的表现**：`accept`/`open` 返回 `EMFILE`（进程限制）或 `ENFILE`（系统限制）。
2. **`select` 的 1024 限制**来自 `FD_SETSIZE`，与 `ulimit -n` 无关（`poll`/`epoll` 无此限制）。
3. **`/proc/<pid>/fd` 是符号链接**，指向实际对象 —— 可以定位"哪个文件被打开着"。
4. **`close` 的坑**：多线程下 `close` 一个 fd 后，该 fd 号可能立即被另一个线程 `open` 复用 —— 应先 `dup` 或加锁。
5. **`SO_REUSEADDR`/`SO_REUSEPORT`**：解决 `TIME_WAIT` 导致的端口占用问题。""",
    ),
    (
        "Linux",
        "零拷贝,sendfile",
        3,
        r"""什么是零拷贝？`sendfile`、`splice`、`mmap` 分别怎么减少拷贝？""",
        r"""**传统 read + write（4 次拷贝、4 次上下文切换）**：

```
磁盘 → [DMA] → 内核缓冲区(page cache) → [CPU] → 用户缓冲区 → [CPU] → socket 缓冲区 → [DMA] → 网卡
        ①              ②                  ③                ④
```

- 4 次拷贝（2 次 DMA、2 次 CPU）、4 次用户态/内核态切换。

**零拷贝的核心思路**：**消除内核与用户空间之间的 CPU 拷贝**，让数据在内核内部流转。

**`sendfile(out_fd, in_fd, offset, count)`**（Linux 2.0+）：
```
磁盘 → [DMA] → page cache → [CPU 拷贝描述符] → socket 缓冲区 → [DMA] → 网卡
```
- **数据完全不经过用户空间** → 省掉 2 次 CPU 拷贝、2 次上下文切换。
- 现代实现（3.0+）配合 **SG-DMA（scatter-gather）**：page cache 的**描述符**直接传给网卡，连内核内的那次 CPU 拷贝也省掉 → **真正的零拷贝**（0 次 CPU 拷贝）。
- **典型用途**：静态文件服务器（nginx 的 `sendfile on`）、Kafka（用 `sendfile` 发消息）、FTP。
- **限制**：不能修改数据；`in_fd` 必须是文件（不能是 socket）；只支持文件→socket。

**`splice()`**（2.6.17+）：
- 在两个 fd 之间移动数据，**至少有一端是 pipe**。
- 用 pipe 作为"内核内的中转"，实现 socket→socket、文件→pipe 等任意组合的零拷贝。
- **用途**：代理服务器转发数据（nginx 的 `proxy` 路径）。

**`mmap + write`**：
```
磁盘 → [DMA] → page cache ←(映射)→ 用户空间只读 → [CPU] → socket 缓冲区 → [DMA] → 网卡
```
- 省掉"内核→用户"的拷贝，但用户态的 `write` 仍要"用户→socket"的 CPU 拷贝（共 3 次，1 次 CPU）。
- 适合**需要读写文件内容**的场景（不能像 sendfile 那样完全不碰数据）。

**`MSG_ZEROCOPY`**（4.14+）：socket 发送时用"引用用户页"而非拷贝，适合大块发送。

**`io_uring`**：提供 `IORING_OP_SEND_ZC` 等真正的零拷贝发送。

**对比表**：

| 方式 | CPU 拷贝次数 | 上下文切换 | 能否修改数据 | 适用 |
|---|---|---|---|---|
| read+write | 2 | 4 | ✅ | 通用 |
| mmap+write | 1 | 4 | ✅ | 需要读写文件 |
| sendfile | 0~1 | 2 | ❌ | 文件→socket（静态服务） |
| splice | 0 | 2 | ❌ | 任意 fd 间（需 pipe） |
| MSG_ZEROCOPY | 0 | 2 | ❌ | socket 发送大块 |

**注意**：
1. **"零拷贝"不是"没有拷贝"**，而是"没有 CPU 参与的拷贝"（DMA 拷贝仍在）。
2. **page cache 仍是共享的**：数据从磁盘读入 cache 后，可以发给多个客户端而无需重复读盘（Kafka 高效的关键）。
3. **`sendfile` 在 TLS 下失效** —— 加密需要修改数据，必须回到用户态（这也是 HTTPS 静态服务性能低于 HTTP 的原因之一；`ktls` 内核 TLS 能恢复部分优势）。
4. **`TCP_CORK`/`TCP_NODELAY`** 影响发送路径的合并与延迟。
5. nginx 相关配置：`sendfile on; tcp_nopush on;`（`tcp_nopush` 让数据凑满一个 MSS 再发）。

**面试延伸**：`splice` 需要一个 pipe，而 pipe 有一定开销（但比用户态拷贝便宜）；`copy_file_range`（4.5+）在支持的文件系统上可以在内核里直接拷贝（甚至跨设备用 reflink）。""",
    ),
    (
        "Linux",
        "IO 模型,多路复用",
        2,
        r"""Linux 的 IO 模型有哪几种？`epoll` 的 LT 和 ET 有什么区别？""",
        r"""**五种 IO 模型**：

| 模型 | 说明 | 阻塞点 |
|---|---|---|
| **阻塞 IO** | `read` 一直等到数据就绪并拷贝完成 | 全程 |
| **非阻塞 IO** | `read` 立即返回 `EAGAIN`，需**轮询** | 数据拷贝阶段 |
| **IO 多路复用** | `select`/`poll`/`epoll` 一次等待多个 fd | `select`/`epoll_wait` |
| **信号驱动 IO** | 数据就绪时内核发 `SIGIO` | 拷贝阶段 |
| **异步 IO（AIO/io_uring）** | 提交请求后**完全由内核完成**，通知结果 | 无（真正的异步） |

前四种都是**同步 IO**（数据拷贝阶段仍阻塞），只有 **AIO/io_uring** 是真正的异步。

**`select`/`poll`/`epoll` 对比**：

| 维度 | select | poll | epoll |
|---|---|---|---|
| fd 上限 | `FD_SETSIZE`（1024） | 无（链表） | 无 |
| 数据结构 | 位图 | 数组 | 红黑树 + 就绪链表 |
| 每次调用 | 传全量 fd 集，内核遍历 | 同 | **只传新增/删除**，内核只报告就绪的 |
| 复杂度 | O(n) | O(n) | **O(1)（就绪数）** |
| 触发模式 | LT | LT | **LT + ET** |
| 拷贝开销 | 每次拷贝 fd 集 | 每次拷贝 | 一次注册（`epoll_ctl`） |
| 适用 | 少量连接 | 少量连接 | **海量连接** |

**`epoll` 的工作机制**：
1. `epoll_create` 创建 epoll 实例（内核里的红黑树 + 就绪链表）。
2. `epoll_ctl(ADD/MOD/DEL)` 增删改要监控的 fd（**只做一次**）。
3. `epoll_wait` 阻塞等待，返回**就绪链表**上的 fd —— **不需要遍历全部 fd**。
4. 回调机制：fd 有事件时，内核通过回调把就绪的 fd 挂到就绪链表，并唤醒 `epoll_wait`。

**LT（水平触发，默认）**：
- **只要缓冲区还有数据**，每次 `epoll_wait` 都会报告该 fd。
- 编程简单（读不完下次继续），不容易丢事件。
- 缺点：就绪的 fd 多时，每次都报告 → 略低效。

**ET（边缘触发）**：
- **只在状态变化时**报告一次（数据从无到有）。
- **必须一次性把数据读完**（循环 `read` 到 `EAGAIN`），否则剩余数据不会再触发事件 → **丢数据**。
- **必须搭配非阻塞 fd**（否则最后一次 `read` 会阻塞）。
- 效率更高（事件更少），但**编程难度大**，是很多 bug 的来源。

```c
// ET 模式下正确的读法
while (1) {
    ssize_t n = read(fd, buf, sizeof buf);
    if (n > 0) { /* 处理 */ continue; }
    if (n == 0) { /* 对端关闭 */ break; }
    if (errno == EAGAIN || errno == EWOULDBLOCK) break;   // 读干净了
    if (errno == EINTR) continue;
    /* 真错误 */ break;
}
```

**ET 的额外优势**：配合 `EPOLLONESHOT` 可以实现"一个连接同时只被一个线程处理"，简化多线程模型。

**`epoll` 的惊群问题**：
- **多个进程/线程在同一 epoll 实例上 `epoll_wait`** 时，新连接到来可能唤醒全部 → 只有一个能处理，其余白醒。
- 解决：**`EPOLLEXCLUSIVE`**（4.5+，只唤醒一个）；或让每个线程有自己的 epoll 实例（SO_REUSEPORT 或 accept 分发）。

**`io_uring`（5.1+）**：共享内存环形队列（SQ/CQ），提交/完成都不需要系统调用（`IORING_SETUP_SQPOLL` 内核线程轮询），支持真正的异步与零拷贝，是现代高性能 IO 的方向。

**实践建议**：
1. **默认用 LT**（简单正确）；只有确证是瓶颈才上 ET。
2. **ET 必须配非阻塞 + 读到 EAGAIN**。
3. 关注**惊群**与**单 fd 并发**问题。
4. 新项目考虑 **io_uring**（但要评估内核版本与生态支持）。""",
    ),
    (
        "Linux",
        "网络命令,排查",
        2,
        r"""排查网络问题常用哪些命令？各自解决什么问题？""",
        r"""**分层排查**（从下到上）：

**1. 链路与接口**
```bash
ip link show                 # 接口状态（UP/DOWN）
ip addr show                 # IP 地址
ethtool eth0                 # 网卡速率/双工/驱动
ip -s link                   # 收发包统计（errors/dropped）
```

**2. 路由与连通性**
```bash
ip route show                # 路由表
ip route get 8.8.8.8         # 查询到某地址走哪条路由
ping -c 4 host               # ICMP 连通性 + RTT
traceroute host / tracepath  # 路径追踪
mtr host                     # 持续 traceroute + 统计（更好用）
arp -a / ip neigh            # ARP 表
```

**3. DNS**
```bash
dig example.com +short       # 最详细
nslookup example.com
host example.com
cat /etc/resolv.conf         # DNS 配置
cat /etc/hosts               # 本地解析
resolvectl status            # systemd-resolved
```

**4. 端口与连接**
```bash
ss -lntp                     # 监听中的 TCP 端口 + 进程
ss -antp                     # 所有 TCP 连接
ss -s                        # 汇总统计
ss -tn state time-wait       # 按状态过滤
ss -tnp dst 10.0.0.1         # 过滤目标
netstat -anp                 # 老工具（ss 更快）
lsof -i :8080                # 谁占用了 8080
```
**`ss` 比 `netstat` 快得多**（直接读 `/proc/net` 的 netlink，不遍历全部 fd）。

**5. 抓包与流量**
```bash
tcpdump -i eth0 -nn port 80               # 抓包（-nn 不解析）
tcpdump -i any -w cap.pcap 'tcp port 443' # 存文件后 wireshark 分析
iftop -i eth0                              # 实时流量（按连接）
nethogs                                    # 实时流量（按进程）
iptraf-ng / nload                          # 接口流量
tcpflow / tshark                           # 高级分析
```

**6. 性能与带宽测试**
```bash
iperf3 -s / iperf3 -c host        # 带宽测试
sar -n DEV 1                      # 网卡历史流量
sar -n TCP,ETCP 1                 # TCP 重传/连接统计
nstat -az                         # 内核网络统计（含 TCP 重传）
```

**7. 内核参数与统计**
```bash
sysctl net.ipv4.tcp_*             # TCP 参数
cat /proc/net/snmp                # 协议统计
cat /proc/net/netstat             # 扩展统计（含 TcpExt）
netstat -s                        # 协议统计（重传、错误）
```

**8. 防火墙与转发**
```bash
iptables -L -n -v                 # 规则（含计数）
nft list ruleset                   # nftables
firewall-cmd --list-all            # firewalld
cat /proc/sys/net/ipv4/ip_forward  # 是否开启转发
```

**典型排查路径**：
1. **能 ping 通但连不上端口** → 防火墙 / 服务未监听（`ss -lntp`）/ 只绑定 127.0.0.1。
2. **DNS 慢** → `dig` 看解析耗时；检查 `/etc/resolv.conf`（多个 nameserver 会串行超时）。
3. **连接建立慢** → 看 SYN 重传（`ss -ti`、`nstat`）、MTU 问题（`ping -M do -s 1472`）。
4. **吞吐低** → 看 `ss -ti` 的 `cwnd`/`retrans`、`sar -n ETCP` 的重传率、网卡错误计数。
5. **TIME_WAIT 太多** → `ss -s`、`net.ipv4.tcp_tw_reuse`、`SO_REUSEADDR`。
6. **大量 CLOSE_WAIT** → **应用没调用 `close`**（代码 bug，不是内核问题）。

**关键命令速记**：
| 想知道 | 用 |
|---|---|
| 谁在监听端口 | `ss -lntp` |
| 连不上 | `ping` → `traceroute` → `nc -zv host port` |
| 数据包到没到 | `tcpdump` |
| 带宽/重传 | `sar -n DEV,ETCP 1`、`nstat` |
| 是 DNS 还是网络 | `dig` + `ping <IP>` 对比 |""",
    ),
    (
        "Linux",
        "TIME_WAIT,端口耗尽",
        2,
        r"""TIME_WAIT 是什么？为什么会端口耗尽？怎么优化？""",
        r"""**TIME_WAIT** 是 TCP 主动关闭方在发送最后一个 ACK 后进入的状态，持续 **2MSL**（Linux 下 60 秒）。

**为什么需要**：
1. **保证最后的 ACK 能到达**：若 ACK 丢失，对端会重发 FIN，处于 TIME_WAIT 的一方可以重发 ACK。若直接 CLOSED，对端重发的 FIN 会得到 RST。
2. **让旧连接的数据包在网络中消亡**：避免"旧连接的延迟包"被"新连接（相同四元组）"误收。

**TIME_WAIT 是主动关闭方的状态**：
```
主动关闭方：FIN_WAIT_1 → FIN_WAIT_2 → TIME_WAIT → (2MSL) → CLOSED
被动关闭方：CLOSE_WAIT → LAST_ACK → CLOSED
```

**CLOSE_WAIT 才是应用问题**：`CLOSE_WAIT` 表示"对端已关闭，我方还没 `close`" —— **大量 CLOSE_WAIT = 应用代码忘记关闭 socket**（不是内核参数能解决的）。

**端口耗尽**：
- 主动发起连接的**客户端**会积累 TIME_WAIT。可用端口范围 `/proc/sys/net/ipv4/ip_local_port_range`（默认 32768~60999，约 28k 个）。
- 如果有大量短连接（**每秒数千次连接**），60 秒内累积的 TIME_WAIT 会耗尽端口 → `Cannot assign requested address`。
- **注意**：如果服务端也主动关闭（如 HTTP/1.0 无 keep-alive），服务端也会积累 TIME_WAIT（用**本地端口 + 对端四元组**标识，理论上限高得多，但也可能耗尽）。

**优化手段**：

1. **`net.ipv4.tcp_tw_reuse = 1`**（推荐）
   - 允许**主动建立连接**时复用 TIME_WAIT 的端口（仅当 TCP 时间戳 `tcp_timestamps` 开启且新连接的时间戳更大时）。
   - **只影响出站连接**，安全。

2. **`net.ipv4.tcp_max_tw_buckets`**（默认 262144）
   - TIME_WAIT 数量上限，超过则**立即回收**并打警告。
   - **调小可以快速回收，但会削弱 TIME_WAIT 的保护作用**（有风险）。

3. **扩大端口范围**
```bash
sysctl -w net.ipv4.ip_local_port_range="1024 65535"
```

4. **用长连接替代短连接**（**最根本**）
   - HTTP keep-alive / HTTP/2 多路复用 / 连接池。
   - **这是唯一真正有效的方案**：减少连接数，从源头减少 TIME_WAIT。

5. **`SO_REUSEADDR`**（服务端）
   - 允许绑定处于 TIME_WAIT 的端口（重启服务时不报 `Address already in use`）。
   - 注意：**它不能解决出站端口耗尽**。

6. **`SO_REUSEPORT`**（多进程负载均衡）
   - 多个进程 bind 同一端口，内核做分发；也减少监听队列争用。

7. **`tcp_fin_timeout`**
   - 只影响 `FIN_WAIT_2` 的超时，**不影响 TIME_WAIT 的 2MSL**。

**不推荐的做法**：
- ❌ **`tcp_tw_recycle`**（已在 Linux 4.12 **移除**）：依赖时间戳，在 NAT 环境下会错误丢弃连接，是著名的生产事故来源。
- ❌ 让服务端直接 `RST` 关闭连接（牺牲 TIME_WAIT 保护，可能丢数据）。

**监控**：
```bash
ss -s                                       # 汇总
ss -tan state time-wait | wc -l             # 数量
ss -tan state time-wait | awk '{print $4}' | awk -F: '{print $2}' | sort | uniq -c | sort -rn | head   # 按端口统计
nstat -az | grep -i tw                      # 内核计数器
```

**实践建议**：
1. **首选长连接/连接池**。
2. 客户端侧开 `tcp_tw_reuse=1` + 扩大端口范围。
3. 服务端开 `SO_REUSEADDR`。
4. **不要动 `tcp_tw_recycle`**（已不存在）或盲目调小 `tcp_max_tw_buckets`。
5. **大量 CLOSE_WAIT 要查代码**（忘 `close`），不是调内核参数。""",
    ),
    (
        "Linux",
        "TCP backlog,队列",
        3,
        r"""`listen` 的 backlog 参数是什么？TCP 的 SYN 队列和 accept 队列有什么区别？""",
        r"""**`listen(fd, backlog)`** 的 backlog 历史上含义模糊，现代 Linux（2.2+）表示：
> **已完成连接队列（accept queue）的最大长度**。

**两个队列**：

| 队列 | 内容 | 由谁控制 |
|---|---|---|
| **SYN 队列**（半连接队列） | 收到 SYN、已回 SYN+ACK、**还没收到 ACK** 的连接（`SYN_RECV` 状态） | `net.ipv4.tcp_max_syn_backlog` |
| **accept 队列**（全连接队列） | 三次握手**已完成**、等待应用 `accept()` 取走的连接（`ESTABLISHED`） | `min(backlog, net.core.somaxconn)` |

**三次握手与队列的交互**：
```
客户端            服务端
  SYN    ──────▶  进 SYN 队列，回 SYN+ACK
  ◀────── SYN+ACK
  ACK    ──────▶  从 SYN 队列移到 accept 队列（等待 accept）
应用 accept() ◀──  从 accept 队列取出
```

**队列满时的行为（关键）**：
1. **accept 队列满**：
   - 默认（`tcp_abort_on_overflow=0`）：**丢弃最终的 ACK**，服务端以为没收到，客户端会重传 ACK/或重发数据 → 连接"看起来建立了"但应用拿不到。
   - 设为 `1`：直接回 **RST**（客户端立即报错）。
   - **常见现象**：客户端连接超时或偶发失败，`ss -lnt` 显示 `Send-Q`（accept 队列上限）与实际 `Recv-Q`（当前排队数）都很高。
2. **SYN 队列满**：默认**丢弃新 SYN**（客户端重传），若开启 **`tcp_syncookies=1`**，则**不占用队列**、直接构造 SYN+ACK（防 SYN flood 的同时保持服务可用）。

**查看队列**：
```bash
ss -lnt
# State  Recv-Q  Send-Q  Local Address:Port
# LISTEN 0       511     0.0.0.0:80     ← Send-Q 就是 accept 队列上限
# LISTEN 12      511     0.0.0.0:80     ← Recv-Q 是当前排队等待 accept 的个数
```
**注意**：`ss -lnt` 中 LISTEN 状态的 `Recv-Q` 是**当前 accept 队列长度**，`Send-Q` 是**队列上限**。非 LISTEN 状态下 `Recv-Q`/`Send-Q` 表示收发缓冲的字节数。

```bash
netstat -s | grep -i -E "SYNs to LISTEN|listen queue|overflow"
# "times the listen queue of a socket overflowed" → accept 队列溢出次数
# "SYNs to LISTEN sockets dropped" → SYN 队列溢出
```
还有 **`nstat -az | grep -i listen`**、`/proc/net/netstat` 的 `ListenOverflows`/`ListenDrops`。

**参数**：
```bash
sysctl net.core.somaxconn              # accept 队列上限（默认 4096 或 128）
sysctl net.ipv4.tcp_max_syn_backlog    # SYN 队列上限（默认 128~1024）
sysctl net.ipv4.tcp_abort_on_overflow  # 1 → 溢出时回 RST
sysctl net.ipv4.tcp_syncookies         # 1 → 启用 syncookie 防 SYN flood
sysctl net.ipv4.tcp_synack_retries     # SYN+ACK 重传次数
```

**实践要点**：
1. **`backlog` 实际生效值 = `min(backlog, somaxconn)`** —— 改了代码里的 backlog 但没调 `somaxconn` 是无效的（nnginx 的 `listen ... backlog=511` 常被 `somaxconn=128` 限制）。
2. **accept 队列溢出是典型的高并发问题**：应用 `accept` 太慢（单线程 accept + 慢业务）或 `accept` 后没及时（如 `accept` 与 `epoll_ctl` 之间有阻塞）。
3. **多线程 accept**：多个进程/线程 `accept` 同一 socket 会有**惊群**（用 `EPOLLEXCLUSIVE` 或 `SO_REUSEPORT` 缓解）。
4. **`syncookies` 的代价**：开启后放弃部分 TCP 选项（如 window scaling），高带宽长肥管道下性能有损。
5. **容器/`SO_MAX_PACING_RATE`**：容器网络里也要注意 `somaxconn`。
6. **调优套路**：`somaxconn=65535` + `tcp_max_syn_backlog=65535` + 应用提高 accept 速度 + 观测 `ListenOverflows`。""",
    ),
    (
        "Linux",
        "启动流程,systemd",
        2,
        r"""Linux 的启动流程是怎样的？systemd 做了什么？""",
        r"""**启动阶段**：

```
1. 固件（BIOS / UEFI）
   → 加电自检（POST）
   → 找到启动设备（BIOS 读 MBR/引导扇区；UEFI 读 ESP 分区里的 .efi）
2. Bootloader（GRUB2）
   → 加载内核（vmlinuz）与 initramfs 到内存
   → 传递内核参数（cmdline）
3. 内核初始化
   → 解压、初始化内存/中断/调度
   → 挂载 initramfs（临时的根文件系统，含加载真实根所需驱动）
   → 探测硬件、加载模块
   → 挂载真实根文件系统
   → 执行 PID 1（init）
4. init 阶段
   → 传统：SysV init（/etc/inittab + /etc/rc.d/rc?.d 脚本，串行）
   → 现代：systemd（并行、socket/timer 激活、cgroup 管理）
5. 用户登录
   → getty 提供终端登录，或 sshd 提供远程登录
```

**initramfs 为什么存在**：内核需要驱动才能读根分区（如 RAID、LVM、加密），而这些驱动不在内核里 → 用内存里的小文件系统先加载模块，再切到真实根（`switch_root`）。

**systemd 的核心概念**：

| 概念 | 说明 |
|---|---|
| **unit（单元）** | 配置的抽象，种类有 `.service`、`.socket`、`.target`、`.timer`、`.mount`、`.device`、`.path` |
| **target** | 一组 unit 的集合，替代运行级别（`multi-user.target` ≈ runlevel 3，`graphical.target` ≈ 5） |
| **依赖** | `Requires=`（强依赖）、`Wants=`（弱依赖，失败不影响）、`After=`/`Before=`（**只定顺序，不定依赖**） |
| **并行启动** | 按依赖图并行拉起，比 SysV 的串行快很多 |
| **按需启动** | `.socket`（有连接才起服务）、`.path`（文件变化才起）、`.timer`（定时） |
| **cgroup 集成** | 每个服务在独立 cgroup，便于资源限制与统一杀进程 |

**一个 service 示例**：
```ini
[Unit]
Description=My Blog Server
After=network.target mysql.service
Wants=network-online.target

[Service]
Type=simple                 # simple/forking/oneshot/notify/dbus
ExecStart=/usr/local/bin/task_server
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=5
User=blog
WorkingDirectory=/opt/blog
LimitNOFILE=65535
MemoryMax=512M              # cgroup 限制
Environment="MYSQL_HOST=localhost"
EnvironmentFile=-/etc/blog.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**常用命令**：
```bash
systemctl start/stop/restart/reload  blog.service
systemctl enable/disable             blog.service   # 开机自启
systemctl status                     blog.service
systemctl list-units --type=service  --state=failed
systemctl daemon-reload                              # 改 unit 文件后必须执行
systemctl cat blog.service                           # 查看 unit（含 override）
systemctl show blog.service                          # 查看所有属性
systemctl list-dependencies --reverse blog.service
journalctl -u blog.service -f                        # 跟踪日志
systemd-analyze blame / critical-chain               # 启动耗时分析
```

**`Type=` 的选择**：
| Type | 含义 |
|---|---|
| `simple`（默认） | `ExecStart` 启动的进程就是主进程 |
| `forking` | 进程自己 daemonize（传统服务） |
| `oneshot` | 执行完就退出（用于初始化任务） |
| `notify` | 进程通过 `sd_notify` 通知就绪（**最精确**） |
| `dbus` | 通过 D-Bus 获取就绪 |

**SysV 与 systemd 对比**：
| | SysV init | systemd |
|---|---|---|
| 启动 | 串行脚本 | **依赖图并行** |
| 配置 | 一堆 shell 脚本 | 声明式 unit 文件 |
| 服务管理 | `service xxx start` | `systemctl` |
| 日志 | 各服务自己写 | **journald 统一** |
| 依赖 | 只有数字顺序 | 显式依赖 |
| 按需启动 | 难 | socket/timer/path 激活 |
| 资源控制 | 无 | **cgroup 集成** |

**替代方案**：OpenRC（Gentoo/Alpine）、runit、s6（容器里常用，轻量）。

**实践建议**：
1. **改 unit 后必须 `systemctl daemon-reload`**。
2. 用 `systemctl edit` 创建 override 片段，**不要直接改发行版的 unit 文件**（升级会被覆盖）。
3. 服务**不要自己 daemonize**（`Type=simple` + systemd 后台化）。
4. 日志走 journald，`journalctl -u` 查看；持久化要设 `/var/log/journal`（否则只在 `/run` 里，重启丢失）。
5. `Restart=on-failure` + `RestartSec` 是简单的自愈。
6. 用 `MemoryMax`/`CPUQuota` 做资源限制，避免单个服务拖垮整机。""",
    ),
    (
        "Linux",
        "cron,定时任务",
        1,
        r"""Linux 的定时任务怎么配置？cron 和 systemd timer 有什么区别？""",
        r"""**cron 基础**：

```bash
crontab -e          # 编辑当前用户的定时任务
crontab -l          # 列出
crontab -r          # 删除全部（危险）
```

**格式**：`分 时 日 月 周 命令`
```
*  *  *  *  *  command
│  │  │  │  └── 星期 (0-7, 0 和 7 都是周日)
│  │  │  └───── 月 (1-12)
│  │  └──────── 日 (1-31)
│  └─────────── 时 (0-23)
└────────────── 分 (0-59)
```

**常用例子**：
```cron
*/5 * * * *   /opt/scripts/check.sh              # 每 5 分钟
0 3 * * *     /opt/scripts/backup.sh             # 每天 3:00
0 9 * * 1-5   /opt/scripts/report.sh             # 工作日 9:00
0 0 1 * *     /opt/scripts/monthly.sh            # 每月 1 号
@reboot       /opt/scripts/start.sh              # 开机
@daily / @hourly / @weekly / @monthly / @yearly  # 快捷宏
```

**位置**：
| 路径 | 说明 |
|---|---|
| `/var/spool/cron/<user>` | 用户 crontab（`crontab -e` 写这里） |
| `/etc/crontab` | 系统 crontab，**多一个"用户"字段** |
| `/etc/cron.d/` | 系统任务片段（同样带用户字段） |
| `/etc/cron.{hourly,daily,weekly,monthly}/` | 放脚本即可 |

**cron 的经典坑（高频面试点）**：
1. **环境变量极简**：cron 的 PATH 通常只有 `/usr/bin:/bin`，**不会读取 `~/.bashrc`**。所以脚本里要用**绝对路径**，或显式设置 `PATH`：
```cron
PATH=/usr/local/bin:/usr/bin:/bin
0 3 * * * /opt/scripts/backup.sh >> /var/log/backup.log 2>&1
```
2. **不加载 shell 配置**：需要环境变量时在脚本里 `source`，或在 crontab 顶部定义。
3. **标准输出/错误会发邮件**（若配置了 MTA），通常要重定向到日志文件，否则可能填满 `/var/mail`。
4. **`%` 需要转义**（在 crontab 里 `%` 是换行符），如日期格式化 `date +\%Y\%m\%d`。
5. **秒级任务不支持**（最小粒度是分钟）；需要秒级用 systemd timer 或循环。
6. **任务重叠**：上一个还没跑完下一个又启动（如冗长的备份）。**必须自己加锁**：
```bash
#!/bin/bash
exec 9>/var/lock/backup.lock
flock -n 9 || exit 0        # 拿不到锁就退出
# ... 任务
```
7. **`cron` 服务必须运行**：`systemctl status crond`（RHEL）/ `cron`（Debian）。新版 Debian/Ubuntu 由 `cron.service` 提供，而 `anacron` 处理"错过的任务"（机器关机期间）。
8. **邮件与 `MAILTO=""`**：不需要邮件就设 `MAILTO=""`。
9. **时区**：cron 用系统时区（`/etc/localtime`）；跨时区部署要设 `CRON_TZ=Asia/Shanghai`（部分实现支持）。

**systemd timer（推荐）**：

```ini
# /etc/systemd/system/backup.timer
[Unit]
Description=Daily backup

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true                 # 错过的任务开机后补跑（相当于 anacron）
RandomizedDelaySec=300          # 抖动，避免同时打爆
Unit=backup.service

[Install]
WantedBy=timers.target
```
```ini
# /etc/systemd/system/backup.service
[Unit]
Description=Backup job
[Service]
Type=oneshot
ExecStart=/opt/scripts/backup.sh
User=backup
```

```bash
systemctl enable --now backup.timer
systemctl list-timers --all
journalctl -u backup.service
systemd-analyze calendar "Mon *-*-* 03:00"
```

**对比**：

| 维度 | cron | systemd timer |
|---|---|---|
| 粒度 | 分钟 | **秒/毫秒** |
| 日志 | 邮件/自建 | **journald 统一** |
| 错过补跑 | 需 anacron | **`Persistent=true`** |
| 依赖服务 | 无 | ✅（`After=network.target`） |
| 资源限制 | ❌ | ✅（cgroup） |
| 随机抖动 | 无 | `RandomizedDelaySec` |
| 配置 | 一行 | 两个文件（略繁琐） |

**实践建议**：**新系统优先 systemd timer**（更好的日志、依赖、资源控制、错过补跑）；老系统或简单场景用 cron。**无论哪种，任务都必须自己加锁防重叠。**""",
    ),
    (
        "Linux",
        "性能排查,top,vmstat",
        2,
        r"""线上服务器 CPU/内存/IO 变慢，你会怎么排查？""",
        r"""**先建立整体印象（"黄金四指标"）**：

```bash
uptime              # 负载
top -b -n1 | head   # CPU 概览
vmstat 1 5          # 综合
iostat -xz 1        # 磁盘
free -m             # 内存
sar -n DEV 1        # 网络
```

**1. 负载平均值（load average）**
```bash
uptime
# load average: 2.10, 1.80, 1.50   ← 1 分钟 / 5 分钟 / 15 分钟
```
- **不是 CPU 使用率**，而是"**可运行 + 不可中断（D 状态）**"的平均任务数。
- 判断标准：**与核数比较**。`nproc` 是核数，load ≈ 核数表示满载。
- **load 高但 CPU 空闲** → 通常是 **IO 等待（D 状态）**，查磁盘/网络存储。
```bash
cat /proc/loadavg                        # 还给出了当前可运行/总进程数
ps -eo state,pid,comm | grep '^D'        # 找 D 状态进程
```

**2. CPU**
```bash
top            # 关注 us/sy/wa/id/si/hi
mpstat -P ALL 1   # 每核
pidstat -u 1      # 每进程
perf top          # 函数级热点
```
- **`us` 高**：应用计算密集 → `perf record` 找热点函数。
- **`sy` 高**：系统调用/内核态频繁 → `strace -c` 看哪个 syscall 多。
- **`wa` 高**：IO 等待 → 查磁盘。
- **`si`/`hi` 高**：中断开销大（网络/驱动）。
- **`st`（steal）高**：虚拟机被宿主机抢占 → 找云厂商。
- **`id` 高但很慢** → 不是 CPU 问题，查 IO/内存/锁/网络。

**3. 内存**
```bash
free -h                    # 看 available，不是 free
cat /proc/meminfo
vmstat 1                   # si/so 是 swap 换入换出
ps -eo pid,rss,comm --sort=-rss | head
smem -t -k                  # 更准确（PSS/USS）
```
- **`available` 低 + `si/so` 非 0** → 内存压力大，正在 swap。
- **RSS 高但"available 还行"** → 可能是缓存，不是问题。
- **OOM 日志**：`dmesg -T | grep -i oom`。

**4. 磁盘 IO**
```bash
iostat -xz 1              # 关键：%util, await, aqu-sz, r/s w/s
iotop -o                   # 按进程
pidstat -d 1
```
- **`%util` 接近 100%** → 设备饱和。
- **`await` 高**（> 十几 ms，HDD 更敏感）→ 排队严重。
- **`aqu-sz`** 队列深度。
- **注意**：SSD/NVMe 的 `%util` 不完全准确（并行度高），看 `await` 与 `r_await`/`w_await`。
```bash
cat /proc/diskstats | grep <dev>    # 原始计数
blktrace / bpftrace                 # 深入分析 IO 延迟
```

**5. 网络**
```bash
sar -n DEV,ETCP 1          # 流量 + 重传
ss -s                       # 连接状态汇总
ss -tan state time-wait | wc -l
nstat -az | grep -i -E "retrans|drop"
iftop / nethogs             # 实时流量
tcpdump                     # 抓包
```
- **重传率高** → 网络质量差/拥塞/MTU 问题。
- **大量 CLOSE_WAIT** → 应用没 close。
- **大量 SYN_RECV** → SYN 洪泛或 accept 太慢。

**6. 锁与调度**
```bash
perf sched latency          # 调度延迟
perf stat -e context-switches,cpu-migrations
cat /proc/<pid>/status | grep -E "voluntary|nonvoluntary"
pidstat -w 1                 # 上下文切换
```
- **`nonvoluntary_ctxt_switches` 高** → 被抢占，可能 CPU 不足。
- **自愿切换高** → 等 IO/锁。
- 锁竞争：`perf lock`、`futex` 相关热点。

**7. 全链路追踪**
```bash
perf record -g -p <pid>; perf report        # 火焰图
perf trace                                  # 系统调用时间线
bpftrace / bcc 工具集（execsnoop、biolatency、tcpconnect、runqlat）
```
**代码级**：`strace -c -p <pid>`（syscall 统计）、`gdb` 采样、语言级 profiler。

**排查套路总结**：
| 现象 | 首先看 |
|---|---|
| 什么都慢 | `uptime` load / `vmstat` |
| 响应慢但 CPU 空闲 | `iostat`、D 状态进程 |
| CPU 满 | `top` 的 us/sy/wa 分布 → `perf top` |
| 内存相关 | `free` 的 available、`vmstat` 的 si/so、OOM 日志 |
| 网络慢 | `sar -n ETCP` 重传、`ss -s`、`tcpdump` |
| 间歇性卡顿 | `perf sched`、`sar` 历史、`dmesg` |

**工具安装（在线排查必备）**：`sysstat`（sar/iostat/pidstat/mpstat）、`iotop`、`htop`、`perf`（linux-tools）、`bcc-tools`、`bpftrace`。""",
    ),
    (
        "Linux",
        "内存指标,free",
        2,
        r"""`free` 的输出各项是什么意思？怎么判断内存是否真的不足？""",
        r"""**`free -h` 输出**：
```
               total        used        free      shared  buff/cache   available
Mem:            15Gi       3.0Gi       1.2Gi       200Mi        11Gi        11Gi
Swap:          2.0Gi          0B       2.0Gi
```

| 项 | 含义 |
|---|---|
| `total` | 物理内存总量 |
| `used` | **已用** = total − free − buff/cache |
| `free` | **完全未使用**的物理内存 |
| `shared` | tmpfs 与共享内存（`/dev/shm`、`tmpfs` 挂载） |
| `buff/cache` | 内核缓冲与缓存（**可回收**） |
| **`available`** | **估算"应用还能申请多少"**（= 可回收缓存 + free 减去不可回收部分） |
| `Swap used` | 已换出到 swap 的量 |

**关键结论：判断内存是否紧张要看 `available`，不是 `free`。**

- `buff/cache` 大 = **好事**：说明文件访问都被缓存了，可以随时回收。
- `free` 小是**正常**的：Linux 倾向"用满内存做缓存"。
- **`available` 接近 0** + **swap 使用增长** = 真的紧张。

**`/proc/meminfo` 的关键字段**：
```bash
cat /proc/meminfo | grep -E "MemTotal|MemFree|MemAvailable|Buffers|Cached|Shmem|Dirty|Writeback|Slab|SReclaimable|SUnreclaim|Committed_AS|CommitLimit|SwapTotal|SwapFree|AnonPages|Mapped|HugePages"
```

| 字段 | 含义 |
|---|---|
| `MemAvailable` | 估算可用（内核用可回收页 + 水位线计算） |
| `Cached` | page cache（**注意含 `Shmem`**） |
| `Shmem` | tmpfs + 共享内存（**不能直接丢弃**） |
| `SReclaimable` | 可回收的 slab（dentry/inode 缓存） |
| `SUnreclaim` | 不可回收的 slab（内核结构） |
| `AnonPages` | 匿名页（堆、栈、私有映射） |
| `Dirty` / `Writeback` | 待回写/正在回写的脏页 |
| **`Committed_AS`** | 已承诺（overcommit）的虚拟内存量 |
| **`CommitLimit`** | 允许承诺的上限（overcommit=2 时生效） |

**"可回收"与"不可回收"缓存**：
- **可丢弃**：`Cached - Shmem`（干净的文件页）、`SReclaimable`。
- **需 swap 才能回收**：`AnonPages`（要换出）、`Shmem`（tmpfs 内容需换出或丢弃）。

**判断脚本**：
```bash
# 真正可用的"应用潜力"
echo "available: $(awk '/MemAvailable/{print $2/1024" MiB"}' /proc/meminfo)"
# 内存压力信号（非 0 表示正在 swap）
vmstat 1 3 | tail -1 | awk '{print "swap in/out:", $7, $8}'
# 无 swap 且 available 低 → 危险
awk '/SwapTotal/{st=$2} /MemAvailable/{av=$2} END{
  if (st==0 && av < 100*1024) print "⚠️ 无 swap 且可用内存 <100MiB，随时可能 OOM"
}' /proc/meminfo
```

**常见误区**：
1. ❌ "free 只有 1G，内存要爆了" —— 看 `available`。
2. ❌ "buff/cache 11G，都是泄漏" —— 可回收。
3. ❌ "进程 RSS 加起来超过总内存" —— **共享库/共享内存被重复计算**。用 **PSS**（`smem`、`/proc/<pid>/smaps`）才准确。
4. ❌ "内存不降就是泄漏" —— 需要观察 **PSS/USS 单调增长**且在压力后不回落。

**工具**：
```bash
free -h                     # 概览
smem -t -k                  # PSS/USS 汇总（最准确）
ps_mem                      # 每进程 USS/PSS
pmap -x <pid>               # 进程内存映射明细
cat /proc/<pid>/smaps_rollup # 进程 PSS 汇总
slabtop                     # 内核 slab 使用
```

**容器场景**：
- 容器**看不到宿主机的真实内存**（`/proc/meminfo` 默认暴露宿主机视图，除非用 lxcfs）。
- 应看 **cgroup** 的限制与用量：
```bash
cat /sys/fs/cgroup/memory.current      # v2
cat /sys/fs/cgroup/memory.max
cat /sys/fs/cgroup/memory.stat         # anon/file/slab 明细
cat /sys/fs/cgroup/memory.events       # oom 次数
```
- **容器的 `page cache` 也算在 cgroup 内存里**（读大文件会顶到 limit），这是"容器内存莫名超限"的常见原因。""",
    ),
    (
        "Linux",
        "内核参数,sysctl",
        2,
        r"""`sysctl` 是什么？生产环境常调哪些网络/内存参数？""",
        r"""**`sysctl`** 读写内核运行参数（`/proc/sys` 的友好接口）。

```bash
sysctl -a                         # 列出全部
sysctl net.ipv4.tcp_syncookies    # 查
sysctl -w net.ipv4.tcp_syncookies=1        # 临时改
sysctl -p                          # 从 /etc/sysctl.conf 加载
sysctl --system                    # 加载所有配置目录（/etc/sysctl.d/*.conf）

# 持久化：写 /etc/sysctl.d/99-custom.conf
net.ipv4.tcp_syncookies = 1
```

**网络参数（高频）**：

| 参数 | 作用 | 常见值 |
|---|---|---|
| `net.core.somaxconn` | accept 队列上限 | 65535 |
| `net.ipv4.tcp_max_syn_backlog` | SYN 队列上限 | 65535 |
| `net.ipv4.tcp_syncookies` | SYN flood 防护 | 1 |
| `net.ipv4.tcp_tw_reuse` | 复用 TIME_WAIT 端口（出站） | 1 |
| `net.ipv4.ip_local_port_range` | 本地端口范围 | "1024 65535" |
| `net.ipv4.tcp_fin_timeout` | FIN_WAIT_2 超时 | 15 |
| `net.ipv4.tcp_keepalive_time` | 保活探测间隔 | 600 |
| `net.ipv4.tcp_keepalive_intvl` | 探测间隔 | 30 |
| `net.ipv4.tcp_keepalive_probes` | 探测次数 | 3 |
| `net.core.rmem_max` / `wmem_max` | 单 socket 收发缓冲上限 | 16 MiB |
| `net.ipv4.tcp_rmem` / `tcp_wmem` | TCP 收发缓冲（min/default/max） | "4096 87380 16777216" |
| `net.ipv4.tcp_congestion_control` | 拥塞算法 | cubic / bbr |
| `net.core.netdev_max_backlog` | 网卡收包队列 | 65535 |
| `net.ipv4.tcp_max_tw_buckets` | TIME_WAIT 上限 | 262144 |
| `net.ipv4.tcp_slow_start_after_idle` | 空闲后是否重置 cwnd | 0（长连接优化） |

**⚠️ 已移除/不推荐**：
- `net.ipv4.tcp_tw_recycle`：**Linux 4.12 已移除**（NAT 下会误杀连接）。
- `net.ipv4.tcp_tw_reuse` 需要 `tcp_timestamps=1`（默认开）。

**内存参数**：

| 参数 | 作用 |
|---|---|
| `vm.swappiness` | 换出匿名页的倾向（0~100，默认 60）。**数据库常设 1**（只在必要时 swap），但**不要设 0**（会加剧 OOM） |
| `vm.overcommit_memory` | 0 启发式 / 1 总是允许 / 2 严格限制 |
| `vm.overcommit_ratio` | 配合 =2 时的比例 |
| `vm.min_free_kbytes` | 保留的最小空闲内存（影响回收水位） |
| `vm.dirty_ratio` | 脏页达到此比例时**写进程被阻塞**（默认 20） |
| `vm.dirty_background_ratio` | 后台回写启动阈值（默认 10） |
| `vm.dirty_expire_centisecs` | 脏页最长存活（默认 3000 = 30s） |
| `vm.dirty_writeback_centisecs` | 回写线程唤醒间隔 |
| `vm.vfs_cache_pressure` | 回收 dentry/inode 的倾向（默认 100） |
| `vm.max_map_count` | 进程最大内存映射数（**ES/大数据组件常调大**，默认 65530） |
| `vm.panic_on_oom` | OOM 时是否 panic |

**文件/进程参数**：
| 参数 | 作用 |
|---|---|
| `fs.file-max` | 系统级 fd 上限 |
| `fs.nr_open` | 单进程 fd 硬上限 |
| `fs.inotify.max_user_watches` | inotify watch 上限（**IDE/文件同步工具的常见坑**） |
| `fs.epoll.max_user_watches` | epoll 监控数上限 |
| `kernel.pid_max` | PID 上限 |
| `kernel.shmmax` / `shmall` | System V 共享内存（**Oracle/PostgreSQL 需要**） |
| `kernel.core_pattern` | core dump 路径 |
| `net.ipv4.ip_forward` | 是否开启 IP 转发（网关/容器需要） |

**典型调优场景**：

1. **高并发 Web 服务器**：
```ini
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.ip_local_port_range = 1024 65535
net.ipv4.tcp_fin_timeout = 15
fs.file-max = 1000000
```

2. **数据库服务器**：
```ini
vm.swappiness = 1
vm.dirty_ratio = 10
vm.dirty_background_ratio = 5
vm.overcommit_memory = 2
vm.overcommit_ratio = 80
```

3. **大数据/Elasticsearch**：
```ini
vm.max_map_count = 262144
vm.swappiness = 1
```

4. **长连接/即时通讯**：
```ini
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_keepalive_intvl = 30
net.ipv4.tcp_keepalive_probes = 3
net.ipv4.tcp_slow_start_after_idle = 0
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
```

**实践原则**：
1. **先监控再调参**（有基线才知道有没有改善）。
2. **一次只改一项并记录**（便于回滚）。
3. **写进 `/etc/sysctl.d/*.conf`**（不要直改 `/etc/sysctl.conf`，发行版升级可能覆盖）。
4. **容器里改 `sysctl` 可能受限**（`net.*` 命名空间相关可改，`vm.*` 多数是宿主机的）。
5. **不要照抄网上的"万能调优"**（如很多人开的 `tcp_tw_recycle` 已移除，`overcommit_memory=1` 可能掩盖真实内存问题）。""",
    ),
    (
        "Linux",
        "strace,gdb,core",
        2,
        r"""`strace`、`gdb`、core dump 分别怎么用？""",
        r"""**`strace`：跟踪系统调用**

```bash
strace ./prog                       # 全量跟踪
strace -p <pid>                     # 附加到运行中的进程
strace -f -p <pid>                  # 跟踪所有子线程/子进程
strace -e trace=openat,read,write ./prog   # 只跟某类调用
strace -c ./prog                    # 统计各 syscall 的次数/耗时/错误 ⭐
strace -T -tt ./prog                # 显示每次调用耗时与时间戳
strace -o out.log -p <pid>          # 输出到文件
strace -yy -p <pid>                 # 解析 fd 对应的路径（非常有用）
```

**典型用途**：
1. **程序卡住** → 看它卡在哪个 syscall（`futex` = 等锁；`read` = 等 IO）。
2. **`strace -c` 找"哪个系统调用被调了几百万次"** → 发现性能问题。
3. **`No such file or directory` 排查** → 看它到底 open 了什么路径（配置文件找不到的经典排查）。
4. **观察 `connect`/`accept` 失败**（`ECONNREFUSED`）。

**代价**：`strace` 会让进程**慢几十倍**（ptrace 每次系统调用都停两次），**不要在生产热路径长时间用**。更好的选择：**`perf trace`**、**bpftrace/eBPF**（低开销）。

**`ltrace`**：跟踪**库函数**调用（如 `malloc`、`strcpy`）。

**`gdb`：调试器**

```bash
gdb ./prog                          # 启动
gdb -p <pid>                        # 附加到进程 ⭐
gdb ./prog core                     # 分析 core 文件

# 常用命令
break main / b file.c:42            # 断点
run / r, continue / c, next / n, step / s
print var / p *ptr                  # 打印
bt                                  # 调用栈 ⭐
info threads / thread 3             # 线程
info registers / info locals
x/16xb ptr                          # 查看内存
watch var                           # 数据断点
attach <pid> / detach               # 附加/脱离
gcore                               # 生成 core 而不停进程太久
quit
```

**无源码/优化过的二进制**：安装 `debuginfo`/`-dbg` 包（`dnf debuginfo-install`、`apt install <pkg>-dbg`）或编译时 `-g -O0`（但生产常用 `-g -O2` 配合 `-fno-omit-frame-pointer`）。

**`gdb` 对多线程/死锁**：
```bash
gdb -p <pid>
(gdb) thread apply all bt           # 所有线程的栈 ⭐（定位死锁的关键）
(gdb) info sharedlibrary            # 加载了哪些库
```

**`pstack`/`eu-stack`**：不进入交互式 gdb 直接打印栈（`pstack <pid>`）。
**`gcore <pid>`**：生产上生成 core 而不杀进程。

**core dump**

```bash
ulimit -c unlimited                          # 允许生成 core（当前 shell）
ulimit -c                                    # 查看
cat /proc/sys/kernel/core_pattern            # core 文件路径模式
sysctl -w kernel.core_pattern=/var/crash/core.%e.%p.%t
```

**为什么"没有 core 文件"**：
1. `ulimit -c` 是 0（默认常为 0）。
2. `core_pattern` 指向 `systemd-coredump`（现代发行版默认），文件在 `/var/lib/systemd/coredump/`：
```bash
coredumpctl list
coredumpctl info <pid>
coredumpctl gdb <pid>              # 直接用 gdb 打开 ⭐
```
3. 进程被 SIGKILL（不可捕获，不产生 core）。
4. 文件系统空间不足。
5. 容器里 `core_pattern` 是 `|/...` 管道而容器内没有对应程序。

**分析步骤（拿到 core 后）**：
```bash
gdb ./prog core
(gdb) bt                        # 崩溃点的调用栈
(gdb) bt full                   # 带局部变量
(gdb) frame 3                   # 切到第 3 帧
(gdb) info locals / info args
(gdb) print ptr                 # 看是否 nullptr
(gdb) info registers
```
**常见崩溃模式**：
- `SIGSEGV` + `bt` 指向 `0x0` → 空指针解引用。
- `SIGABRT` + 栈里有 `abort` → `assert` 失败或 C++ 未捕获异常 / 堆损坏。
- `SIGFPE` → 除零。
- 堆栈里出现 `malloc`/`free` → **堆破坏**（用 ASan 更易定位）。

**实践建议**：
1. **生产开启 core dump**（`LimitCORE=infinity` in systemd + `core_pattern`）。
2. **编译时加 `-g` 但保留优化**（`-O2 -g`），否则栈信息不可读。
3. **优先用 ASan/UBSan 在测试阶段发现**，而不是靠线上 core 排查。
4. **用 bpftrace/perf 做低开销在线诊断**，`strace`/`gdb` 是最后手段。
5. **`gdb` 附加会暂停进程**，注意对生产的影响；用 `gcore` 或 `profiling` 工具替代。""",
    ),
    (
        "Linux",
        "动态库,ld.so",
        2,
        r"""静态库和动态库有什么区别？`ld.so` 怎么找到 `.so`？""",
        r"""**静态库（`.a`）**：编译期把代码**拷进**可执行文件。
**动态库（`.so`）**：运行时由**动态链接器**加载，多个进程**共享同一份物理内存**（只读的代码段）。

| 维度 | 静态库 | 动态库 |
|---|---|---|
| 时机 | 编译/链接期 | 加载期/运行期 |
| 体积 | 可执行文件大 | 可执行文件小，库可共享 |
| 内存 | 每个进程各一份 | 代码段**共享**（`MAP_SHARED` 只读页） |
| 更新 | 需要重新编译链接 | **替换 `.so` 即可**（ABI 兼容前提下） |
| 启动 | 快（无加载开销） | 略慢（加载 + 重定位） |
| 依赖 | 无 | 需要目标机有对应库 |
| 符号解析 | 链接期全部确定 | 可延迟绑定（PLT/GOT） |
| 部署 | 简单（单文件） | 需管理库版本 |

**`ld.so`（动态链接器/加载器）如何找库**（按优先级）：

1. **`DT_RPATH`**（ELF 里的 rpath，**已弃用**，除非没有 RUNPATH）
2. **`LD_LIBRARY_PATH`** 环境变量（⚠️ 影响所有程序，安全风险）
3. **`DT_RUNPATH`**（ELF 里的 runpath，现代方式；可用 `-Wl,-rpath,'$ORIGIN/lib'`）
4. **`/etc/ld.so.cache`**（由 `ldconfig` 从 `/etc/ld.so.conf` 及 `/etc/ld.so.conf.d/*.conf` 生成）—— **标准库通常走这条**
5. **`/lib`、`/usr/lib`**（默认路径）

```bash
# 写 rpath 让程序找同目录的 lib
gcc main.c -L./lib -lfoo -Wl,-rpath,'$ORIGIN/lib'
# 或
export LD_LIBRARY_PATH=/opt/app/lib:$LD_LIBRARY_PATH

# 新增库目录
echo "/opt/app/lib" | sudo tee /etc/ld.so.conf.d/app.conf
sudo ldconfig
```

**`$ORIGIN`**：ELF 里的特殊变量，表示"可执行文件所在目录"，让程序**自带库、免环境变量**（发布包的常用做法）。

**`LD_PRELOAD`**：在**所有**动态库之前先加载指定的库，可以**覆盖函数**（hook/mock）：
```bash
LD_PRELOAD=/path/libmy.so ./prog
# 常用于：替换 malloc（jemalloc）、mock 测试、性能计数
```
⚠️ **它是提权向量**（`LD_PRELOAD` 对 SUID 程序被忽略，但配置不当就危险），也是**故障排查利器**（`libstdbuf.so` 改缓冲、`libSegFault.so` 打印栈）。

**常用工具**：
```bash
ldd ./prog                 # 显示依赖的库（实际是设置 LD_TRACE_LOADED_OBJECTS 运行程序，有安全风险）
objdump -p ./prog | grep NEEDED     # 更安全的依赖查看
readelf -d ./prog          # 动态段（RPATH/RUNPATH/NEEDED）
patchelf --set-rpath '$ORIGIN/lib' ./prog   # 修改已有 ELF 的 rpath ⭐
nm -D libfoo.so            # 看动态符号
c++filt <符号>             # 还原 C++ 修饰名
LD_DEBUG=libs ./prog       # 打印库搜索过程（排查找不到库的终极手段）
strace -e openat ./prog | grep '\.so'       # 看它 open 了哪些库路径
```

**常见问题**：

1. **`error while loading shared libraries: libXXX.so: cannot open shared object file`**
   → 用 `ldd`/`LD_DEBUG=libs` 看搜索路径，检查 `LD_LIBRARY_PATH`、`ld.so.conf`、rpath。
2. **`version 'GLIBC_2.34' not found`**
   → 在**新系统编译**的二进制拿到**老系统**跑（glibc 符号版本）→ **编译机要 ≤ 运行机 glibc 版本**，或用容器/Alpine（musl）。
3. **替换 `.so` 后行为异常**
   → **ABI 不兼容**（改了类布局/虚表顺序）；或**进程仍持有旧库的映射**（删文件不等于卸载）。
4. **"删除了 `.so` 但磁盘空间没释放"** → 有进程还在用（`lsof | grep deleted`）。

**实践建议**：
1. **优先用系统包管理安装库**，不要随手手工编译安装到 `/usr/local`（会与包管理的库冲突）。
2. **发布程序时带 `$ORIGIN` rpath** + 自带依赖库，**不要依赖 `LD_LIBRARY_PATH`**。
3. **容器里固定基础镜像版本**，避免 glibc 不匹配。
4. **不要用 `LD_LIBRARY_PATH` 做长期方案**（会影响所有子进程，且顺序难以预测）。
5. 需要 **ABI 稳定**的库要遵守 C++ ABI 规则（PIMPL、避免暴露 STL 类型、不用 `inline` 影响布局）。""",
    ),
    (
        "Linux",
        "namespace,cgroup,容器",
        3,
        r"""容器的底层原理是什么？namespace 和 cgroup 各负责什么？""",
        r"""**容器 = namespace（隔离"看到什么"）+ cgroup（限制"能用多少"）+ 文件系统（rootfs/overlayfs）+ 安全（capabilities/seccomp/SELinux）**。

**Namespace：隔离视图**

| namespace | 隔离内容 | 隔离后 `unshare`/`clone` 标志 |
|---|---|---|
| **mnt** | 挂载点（文件系统树） | `CLONE_NEWNS` |
| **pid** | 进程号空间（容器内 PID 1 = 外面的某个 PID） | `CLONE_NEWPID` |
| **net** | 网络栈（网卡、IP、路由、端口） | `CLONE_NEWNET` |
| **ipc** | System V IPC、POSIX 消息队列 | `CLONE_NEWIPC` |
| **uts** | 主机名与域名 | `CLONE_NEWUTS` |
| **user** | 用户/组 ID 映射（容器内 root = 宿主普通用户） | `CLONE_NEWUSER` |
| **cgroup** | cgroup 根的视图 | `CLONE_NEWCGROUP` |
| **time**（5.6+） | 时钟（单调时钟/启动时间偏移） | `CLONE_NEWTIME` |

```bash
# 手工体验
unshare --pid --fork --mount-proc /bin/bash     # 独立的 PID 空间
unshare --net /bin/bash                          # 独立网络（只有 lo）
lsns                                             # 列出所有 namespace
ls -l /proc/<pid>/ns/                            # 看某进程的 namespace
nsenter -t <pid> -n -p ip addr                   # 进入某进程的 namespace ⭐（调试容器利器）
```

**cgroup：限制与统计资源**

**cgroup v2**（统一层级）里的控制器：

| 控制器 | 限制对象 | 关键文件 |
|---|---|---|
| `cpu` | CPU 时间（权重/上限） | `cpu.weight`、`cpu.max` |
| `cpuset` | 绑定哪些 CPU/内存节点 | `cpuset.cpus`、`cpuset.mems` |
| `memory` | 内存上限与统计 | `memory.max`、`memory.current`、`memory.stat` |
| `io` | 块设备 IO 带宽/IOPS | `io.max`、`io.stat` |
| `pids` | 进程数上限 | `pids.max` |

```bash
mount -t cgroup2 none /sys/fs/cgroup
mkdir /sys/fs/cgroup/mygroup
echo "512M" > /sys/fs/cgroup/mygroup/memory.max
echo "100000 100000" > /sys/fs/cgroup/mygroup/cpu.max   # 1 个 CPU 的量
echo $$ > /sys/fs/cgroup/mygroup/cgroup.procs
systemd-cgtop                    # 按 cgroup 看资源占用 ⭐
cat /proc/<pid>/cgroup
```

**v1 vs v2**：v1 每个控制器一个独立层级（可混搭），v2 是**统一层级**（单一树、更清晰的语义、`memory.max` 包含 page cache）。现代发行版默认 v2（`systemd.unified_cgroup_hierarchy=1`）。

**rootfs 与镜像**：
- **overlayfs**：把多个**只读层**（镜像层）叠加成一个可写视图，最上层是**可写层**（容器内的修改）。
```bash
mount -t overlay overlay -o lowerdir=lower1:lower2,upperdir=upper,workdir=work /merged
```
- **写时复制**：修改文件时从下层拷到上层（**第一次写大文件会慢**）。
- **删除文件**用 whiteout 标记。
- 镜像层是**共享**的（多个容器共用底层）→ 省磁盘。

**安全隔离**（不止 namespace/cgroup）：
| 机制 | 作用 |
|---|---|
| **Capabilities** | 把 root 权限拆成细粒度能力（`CAP_NET_BIND_SERVICE` 而非全 root） |
| **seccomp** | 过滤系统调用（Docker 默认禁掉一批危险 syscall） |
| **LSM（SELinux/AppArmor）** | 强制访问控制 |
| **user namespace** | 容器内 root 映射为宿主非特权用户（rootless 容器） |
| **read-only rootfs / no-new-privileges** | 减小攻击面 |

**为什么"容器不是虚拟机"**：
- **共享同一个内核**（隔离靠 namespace/cgroup，不是硬件虚拟化）。
- 启动快（毫秒级，无内核启动）、开销小（无额外内核）。
- **隔离性弱于 VM**：内核漏洞可以逃逸；所以有 **gVisor**（用户态内核）、**Kata**（轻量 VM）这类"更强隔离"方案。

**实践要点**：
1. **容器里 PID 1 要正确处理信号与孤儿回收**（用 `tini`/`dumb-init`，或应用自己处理）。
2. **容器内存限制包含 page cache** —— 读大文件可能顶到 `memory.max`。
3. **`/proc/meminfo` 在容器里默认显示宿主机数据**（用 lxcfs 才能看到真实限制）。
4. **调试容器**：`nsenter -t <pid> -a` 进入容器的所有 namespace。
5. **`docker stats` / `crictl stats`** 读的就是 cgroup 的数据。
6. **不要用 `--privileged`**（等于放弃隔离）。""",
    ),
    (
        "Linux",
        "中断,软中断",
        3,
        r"""硬中断和软中断有什么区别？为什么需要软中断？""",
        r"""**硬中断（硬件中断）**：
- 由硬件（网卡、磁盘、定时器）触发，**异步**打断 CPU 当前执行。
- 在**中断上下文**执行，**不能睡眠**（不能阻塞、不能让出 CPU）。
- **要求尽可能短**（长时间关中断会丢中断、增加延迟）。

**软中断（softirq）**：
- **不是**"软件触发的中断"这么简单 —— 它是 Linux 内核的一种**延迟执行机制**。
- 在**中断处理程序的后半段（下半部）**执行耗时的部分，**仍然运行在中断上下文**（不能睡眠），但**可以被硬中断打断**。
- 有类型限制（编译期固定）：`HI_SOFTIRQ`、`TIMER_SOFTIRQ`、`NET_TX_SOFTIRQ`、`NET_RX_SOFTIRQ`、`BLOCK_SOFTIRQ`、`TASKLET_SOFTIRQ`、`RCU_SOFTIRQ` 等。
- **每个 CPU 一个 `ksoftirqd` 内核线程**，在软中断负载过高时接管，避免用户进程被饿死。

**三种下半部机制对比**：

| 机制 | 上下文 | 能否睡眠 | 并行性 | 适用 |
|---|---|---|---|---|
| **软中断（softirq）** | 中断上下文 | ❌ | 同类型可多 CPU 并行 | 高频、性能关键（网络收发） |
| **tasklet** | 中断上下文 | ❌ | **同类型串行**（不同 CPU 也不能并行） | 一般驱动的下半部 |
| **工作队列（workqueue）** | **进程上下文（内核线程）** | ✅ | 并行 | 需要睡眠/耗时的操作 |

**为什么需要软中断**：
1. **硬中断要快**：关中断时间长了会导致丢中断、系统失去响应。所以把"必须立即做的"（读网卡数据到内核缓冲、确认中断）放在硬中断，把"处理数据（协议栈解析、唤醒用户进程）"推迟到软中断。
2. **减少关中断时间**，提高系统整体响应性。

**观察它们**：
```bash
# 软中断统计（各类型次数）
cat /proc/softirqs
# 中断统计（按 IRQ）
cat /proc/interrupts
# 每 CPU 的中断处理开销
mpstat -I SUM 1          # 看 %soft、%irq
top                      # 看 si（软中断）、hi（硬中断）列
```

**中断亲和性**（把中断绑定到特定 CPU）：
```bash
cat /proc/irq/<n>/smp_affinity
echo 2 > /proc/irq/<n>/smp_affinity     # 绑到 CPU1
systemctl enable irqbalance              # 自动均衡（一般保持开启）
```

**性能问题模式**：
1. **`si`（软中断）高** → 网络包处理量巨大 → **RPS/RFS**（多队列分发到多核）、**RSS**（网卡多队列）、增大 `netdev_max_backlog`、`NAPI` 减少中断。
2. **`hi` 高** → 中断太频繁 → 检查是否有异常设备（磁盘错误、网卡风暴）。
3. **单个 CPU 100% 的 `si`** → 中断集中在一核 → 调 `smp_affinity` 或开 RPS。
4. **`ksoftirqd` 占用高** → 软中断负载超出即时处理能力。

**NAPI（New API）**：网络驱动的关键优化 —— **中断 + 轮询混合**：
- 第一个包到来时禁用该设备中断，进入**轮询模式**批量处理队列里的包。
- 队列空后重新启用中断。
- **大幅减少高流量下的中断次数**（从"每包一次中断"变成"每批一次"）。

**RPS/RFS**：
- **RPS（Receive Packet Steering）**：软件层面把包分发到多个 CPU（单队列网卡也能多核处理）。
- **RFS（Receive Flow Steering）**：按"流"分发（同一个连接的处理在同一个 CPU，提升 cache 命中）。
```bash
echo f > /sys/class/net/eth0/queues/rx-0/rps_cpus
echo 4096 > /proc/sys/net/core/rps_sock_flow_entries
```

**其它要点**：
1. **`preempt_count`**：中断上下文里会加计数，`sleep` 时会检查并报 "BUG: sleeping function called from invalid context"。
2. **中断与锁**：中断上下文用 `spin_lock_irqsave`（关中断 + 自旋）。
3. **`local_bh_disable()`** 禁用软中断（用于保护 per-CPU 数据）。
4. **`SO_BUSY_POLL`/`SO_INCOMING_CPU`**：让应用轮询网卡/绑定 CPU，进一步降低延迟（DPDK/高性能网络常用）。
5. **`/proc/softirqs` 各列严重不均** → 中断/软中断亲和性问题。

**实践建议**：
1. **生产环境用 `sar -n DEV` + `mpstat -I SUM` 建立基线**。
2. 遇到"单核 si 100%"就查 **RPS/网卡队列/中断亲和**。
3. 高吞吐网络（10G+）考虑 **多队列网卡 + RSS/RPS + XDP**。
4. **不要随意关 `irqbalance`**（除非有明确的手工绑定策略）。""",
    ),
    (
        "Linux",
        "写时复制,COW",
        3,
        r"""什么是写时复制（COW）？它在 Linux 里有哪些应用？""",
        r"""**COW（Copy-On-Write）**：多个使用者**共享同一份数据**，只有当某一方**要修改**时，才真正复制出一份私有副本。

**实现机制（以 fork 为例）**：
1. `fork` 时，父进程的页表被**复制**（页表项指向**相同的物理页**），所有页在**双方页表里都标记为只读**。
2. 任一方**写入**某个页时，触发**写保护缺页中断（minor page fault）**。
3. 内核分配一个新物理页，**拷贝原内容**，把写入方的页表项指向新页并设为可写。
4. 另一方仍指向原页（内容未变）。

**代价转移**：`fork` 从"复制全部内存"变成"复制页表"（快得多），代价转移到了**第一次写**时。

**应用场景**：

1. **`fork` + `exec`（最典型）**
   - 子进程几乎立刻 `exec`，几乎不写内存 → COW 几乎不做任何实际拷贝。
   - 这是 `fork` 在现代 Linux 上足够快的原因（也让 `vfork` 变得没必要）。

2. **`MAP_PRIVATE` 的 mmap**
   - 私有文件映射：读操作共享 page cache，写操作触发 COW（**不修改文件**）。
   - 动态库的**数据段**就是这么映射的（代码段是只读共享）。

3. **overlayfs / Docker 镜像层**
   - 底层的只读镜像层被多个容器共享；容器内修改文件时，从下层**拷到上层的可写层**。
   - 这就是"容器启动快、占磁盘少"的原因，也是"容器内改大文件第一次很慢"的原因。

4. **文件系统快照（btrfs/ZFS）**
   - 快照与当前数据共享块，修改时才写新块（`reflink`）。
   - **`cp --reflink=auto`** 在支持的文件系统上可秒级"复制"大文件。

5. **`reflink` 与 `copy_file_range`**
   - 同一文件系统内可创建"共享扩展区"的副本。

6. **git 的对象存储**（应用层 COW 思想）
   - 内容寻址 + 不可变对象，新版本只存变化的 blob。

**查看与验证**：
```bash
# COW 缺页计数（minor fault）
ps -o min_flt,maj_flt -p <pid>
/usr/bin/time -v ./prog | grep -i "page faults"

# 观察 COW 的效果：fork 后 RSS 不翻倍
# 用 smem/PSS 看共享内存
```

**性能陷阱**：

1. **`fork` 在大型进程上仍然有开销**：复制页表本身要遍历所有页表项（几 GB 的进程页表拷贝要几毫秒），且会**复制 `task_struct` 与 fd 表**。
   - 解决：`posix_spawn`（内部可能用 `clone(CLONE_VM|CLONE_VFORK)`，连页表都不复制）。
2. **`fork` 后的"第一次写"很贵**：大量 minor fault。
3. **`fork` 在多线程程序中危险**：只复制调用线程，锁状态可能不一致。
4. **THP + COW**：2MB 大页触发 COW 时要复制整个 2MB → **延迟尖刺**（这是 THP 被诟病的点之一）。
5. **COW 与 `madvise(MADV_DONTFORK)`**：可以让某些映射不被 `fork` 继承（如 DPDK 的巨页）。

**相关内核机制**：
- **`page->_refcount`**：物理页的引用计数，>1 时写入要 COW。
- **反向映射（rmap）**：找到所有映射了该物理页的页表项，用于 COW 时更新它们。
- **KSM（Kernel Same-page Merging）**：主动扫描相同的匿名页并合并（去重），写时再 COW 分裂 —— 虚拟机/容器密集场景可省大量内存，但有 CPU 开销。
  ```bash
  echo 1 > /sys/kernel/mm/ksm/run
  cat /sys/kernel/mm/ksm/pages_shared
  ```

**面试延伸**：COW 是"**延迟到必要时才做**"这一思想的经典应用；同类的还有**延迟分配（delayed allocation）**、**惰性求值**、**`optional`/`lazy` 初始化**。""",
    ),
    (
        "Linux",
        "文件锁,fuser",
        2,
        r"""Linux 有哪几种文件锁？怎么防止同一个程序被重复运行？""",
        r"""**三类锁**：

| 类型 | 接口 | 语义 |
|---|---|---|
| **`flock`（BSD 锁）** | `flock(fd, LOCK_EX/LOCK_SH/LOCK_UN)` | **整个文件**加锁，**不区分进程**（同一进程多个 fd 也可能互斥） |
| **`fcntl` 记录锁（POSIX 锁）** | `fcntl(fd, F_SETLK/F_SETLKW, &flock)` | 可**按字节区间**加锁，**按进程**（同一进程不会自己阻塞自己） |
| **`open(O_EXCL)`** | 原子创建 | 创建文件本身作为"锁"（最常见） |

**特点对比**：

| 维度 | flock | fcntl 记录锁 |
|---|---|---|
| 粒度 | 整个文件 | 字节区间 |
| 跨 `fork` | **子进程共享同一把锁** | **不继承**（可 `FD_CLOEXEC`） |
| 跨 `exec` | 保留 | 保留（除非关闭 fd） |
| NFS | 需要 `NFS` 支持（现代 NFSv4 可） | 历史上不可靠 |
| 语义 | 建议性 | 建议性 |

**两者互相独立**：`flock` 与 `fcntl` 锁在 Linux 上是**两套独立的锁**，各自不干扰（不要混用！）。

**建议性 vs 强制性**：
- Linux 的文件锁**默认都是建议性的（advisory）** —— 只有**双方都主动加锁**才生效，不会阻止不守规矩的进程读写。
- 强制锁（mandatory）需要挂载 `mand` 选项 + 设置 setgid 位，**现代内核已基本废弃**。

**防止重复运行（最常用手法）**：

**方式 1：`flock` + 后台 shell**
```bash
#!/bin/bash
exec 9>/var/lock/myapp.lock
flock -n 9 || { echo "already running"; exit 1; }
# ... 主逻辑（脚本结束/进程退出时锁自动释放）
```
**关键：fd 9 必须在整个脚本生命周期内保持打开**（`exec 9>file` 就是为此）。进程退出时内核自动释放锁 —— **无需清理残留**（这与 PID 文件不同）。

**方式 2：C 代码里 `flock`**
```c
int fd = open("/var/lock/myapp.lock", O_RDWR|O_CREAT, 0644);
if (flock(fd, LOCK_EX|LOCK_NB) != 0) {
    fprintf(stderr, "already running\n");
    exit(1);
}
// 保持 fd 打开；进程退出自动释放
```
**`LOCK_NB`**：非阻塞，拿不到立刻返回 `EWOULDBLOCK`。

**方式 3：`open(O_EXCL)` 创建 PID 文件（传统做法，有坑）**
```c
int fd = open("/var/run/myapp.pid", O_RDWR|O_CREAT|O_EXCL, 0644);
if (fd < 0) { /* 文件已存在 */ 
    // 必须检查：读到 PID 后 `kill(pid, 0)` 判断进程是否真的还活着
    // 否则上次崩溃残留的文件会让程序永远无法启动！
}
```
**坑**：进程崩溃时文件残留 → **"陈旧 PID 文件"**。必须人工清理或写复杂逻辑判断。**因此 `flock` 优于 PID 文件**（锁随进程消失自动释放）。

**方式 4：`systemd`（最省事）**
- 用 `Type=simple` + systemd 保证单实例，配合 `Restart=` 自愈。
- 无需自己加锁。

**实际案例**：
```bash
# cron 里的任务防重入（最经典的需求）
*/5 * * * * flock -n /tmp/myjob.lock /opt/scripts/job.sh
# 或脚本内
exec 9>/tmp/myjob.lock; flock -n 9 || exit 0
```

**其它要点**：
1. **锁文件放 `/var/lock` 或 `/run`**（`/tmp` 有 sticky 位但也可能被清理；`/run` 是运行时目录，重启清空）。
2. **`fcntl` 记录锁的"按进程"语义**：同一进程内多次加锁不会阻塞自己（可能误以为"锁住了"）。
3. **`flock` 在 `fork` 后子进程共享**（同一把锁），所以子进程退出不会释放它 —— 要小心。
4. **NFS 上锁**要用 `lockd`/`NLM`，或直接用 `NFSv4` 的内置锁。
5. **`F_SETLK`（非阻塞）vs `F_SETLKW`（阻塞）vs `F_OFD_SETLK`（open file description 锁，更接近 flock 语义，避免同一进程问题）**。
6. **锁与 `chmod`/`unlink` 的交互**：`unlink` 锁文件后新进程可以创建同名新文件并加锁（"锁逃逸"）。**稳妥做法：锁文件不要删，只加锁/解锁。**

**实践建议**：**优先 `flock`**（简单、自动释放、跨退出安全）；需要字节区间锁（如数据库）用 `fcntl`；**不要用"检查 PID 文件是否存在"这种朴素做法**（有 TOCTOU 竞态 + 残留问题）。""",
    ),
    (
        "Linux",
        "ulimit,资源限制",
        2,
        r"""`ulimit` 是什么？常用的限制项有哪些？怎么持久化？""",
        r"""**`ulimit`** 查看/设置**当前 shell 及其子进程**的资源限制（内核的 `RLIMIT_*`）。

```bash
ulimit -a           # 列出全部
ulimit -n           # 打开文件数（最常用）
ulimit -c           # core dump 大小
ulimit -u           # 最大进程/线程数
ulimit -s           # 栈大小
ulimit -v           # 虚拟内存
```

**软限制与硬限制**：
- **软限制（soft）**：当前生效值，**普通用户可提高**（到硬限制）。
- **硬限制（hard）**：上限，**只有 root 能提高**。
- 子进程**继承**父进程的限制。

```bash
ulimit -Sn            # 软限制
ulimit -Hn            # 硬限制
ulimit -n 65535       # 同时设软和硬（若能）
ulimit -S -n 65535    # 只设软
```

**常用限制项**：

| 选项 | RLIMIT | 说明 | 常见问题 |
|---|---|---|---|
| `-n` | NOFILE | 打开 fd 数 | **高并发服务的头号坑** |
| `-u` | NPROC | 用户可创建的进程/线程数 | 线程创建失败（`EAGAIN`） |
| `-c` | CORE | core dump 大小 | 默认 0 → 没有 core 文件 |
| `-s` | STACK | 栈大小 | 递归深了 SIGSEGV |
| `-v` | AS | 虚拟地址空间 | JVM 会预留大量虚拟内存，调小会起不来 |
| `-m` | RSS | 常驻内存 | 已基本无效（现代内核忽略） |
| `-f` | FSIZE | 单文件大小 | 写大文件失败 |
| `-t` | CPU | CPU 时间（秒） | 长任务被杀 |
| `-l` | MEMLOCK | 可锁定的内存 | **大页/DPDK/Redis 需要调大** |
| `-i` | SIGPENDING | 挂起信号数 | — |
| `-q` | MSGQUEUE | POSIX 消息队列字节 | — |
| `-x` | LOCKS | 文件锁数 | — |

**持久化**：

1. **`/etc/security/limits.conf`**（PAM 加载）
```
# <domain>  <type>  <item>    <value>
*           soft    nofile    65535
*           hard    nofile    65535
@devs       soft    nproc     4096
root        soft    nofile    65535
```
2. **`/etc/security/limits.d/*.conf`**（片段，优先级高）
3. **systemd 服务**（**最常见，也最容易漏**）：
```ini
[Service]
LimitNOFILE=65535
LimitNPROC=65535
LimitCORE=infinity
LimitMEMLOCK=infinity
```
> 注意：**`limits.conf` 对 systemd 管理的服务不生效**（systemd 不通过 PAM 的 limits 模块，除非 `PAMName=`）。必须用 `LimitXXX=` 显式设置。
4. **`/etc/systemd/system.conf`** 的 `DefaultLimitNOFILE=`（所有服务的默认）。
5. **容器**：`docker run --ulimit nofile=65535:65535`；k8s 用 `securityContext` 或 Pod 的 `ulimits`。

**验证**：
```bash
cat /proc/<pid>/limits          # 某进程的实际限制 ⭐（权威）
prlimit --pid <pid>             # 查看/修改运行中进程的限制
systemctl show <svc> -p LimitNOFILE
cat /proc/sys/fs/file-max       # 系统级总上限
cat /proc/sys/fs/nr_open        # 单进程可设的最大值上限
```

**高频问题**：

1. **`Too many open files`** / `accept: EMFILE`
   - 服务进程的 `LimitNOFILE` 太小（默认 1024 常见）。
   - 排查：`ls /proc/<pid>/fd | wc -l`；`lsof -p <pid>`。
   - 修复：systemd unit 加 `LimitNOFILE=65535` + 重启。

2. **`unable to create new native thread`**（Java 常见）
   - `nproc` 限制太小 或 **cgroup pids 限制** 或 内存不足（线程栈）。
   - 检查：`ulimit -u`、`cat /sys/fs/cgroup/pids.max`、线程栈大小（`-Xss`）。

3. **`Cannot allocate memory` 但内存充足**
   - 可能是 `vm.max_map_count` 或 `-v`（虚拟内存）限制。

4. **改了 `limits.conf` 不生效**
   - **95% 的情况是服务由 systemd 启动**（不读 PAM limits）→ 用 `LimitNOFILE=`。
   - 或是**修改的是当前 shell，但服务在别处启动**。
   - 或**需要重新登录**（PAM 只在登录时读取）。

5. **`ulimit -n` 设不上去**
   - 非 root 不能超过硬限制；或系统级 `fs.nr_open` 更低。

**实践建议**：
1. 高并发服务统一设 `LimitNOFILE=65535`（或 1048576）**在 systemd unit 里**。
2. **同时调 `net.core.somaxconn` 与 `fs.file-max`**。
3. **监控 fd 数**（`node_exporter` 有 `process_open_fds`），设置告警。
4. **容器里也要设**（宿主机的 limits 不会自动继承给容器）。
5. **生产开启 core dump**（`LimitCORE=infinity` + `kernel.core_pattern`）。""",
    ),
    (
        "Linux",
        "io_uring,异步IO",
        3,
        r"""`io_uring` 是什么？它比 `epoll` 和传统 AIO 好在哪？""",
        r"""**`io_uring`**（Linux 5.1+，Jens Axboe）是新一代**异步 IO 接口**，用**共享内存环形队列**实现"提交/完成"零系统调用（可选）。

**核心结构**：
```
用户空间                        内核空间
┌──────────────┐               ┌──────────────┐
│ SQ（提交队列）│──共享内存──▶  │ 内核消费提交  │
│ CQ（完成队列）│◀─共享内存──  │ 内核写完成    │
└──────────────┘               └──────────────┘
```

- **SQ（Submission Queue）**：用户写"要做什么"（`IORING_OP_READ/WRITE/ACCEPT/SEND/RECV/...`）。
- **CQ（Completion Queue）**：内核写"做完了"（结果、返回值）。
- **SQE / CQE**：队列里的条目。

**三种运行模式**：

| 模式 | 系统调用 | 说明 |
|---|---|---|
| 默认 | `io_uring_enter` 提交并等待 | 至少 1 次系统调用，但可**批量** |
| `IORING_SETUP_SQPOLL` | **0 次** | 内核线程**轮询** SQ（消耗 CPU 换延迟） |
| `IORING_SETUP_IOPOLL` | 0 次 | 内核**轮询设备**（O_DIRECT，极低延迟） |

**对比**：

| 维度 | 传统 AIO（`libaio`） | `epoll` + 非阻塞 | `io_uring` |
|---|---|---|---|
| 异步程度 | 只支持 `O_DIRECT` 文件 IO | 只**通知就绪**，读写还要自己做 | **真正的异步**（内核完成读写） |
| 系统调用 | 每个操作 1~2 次 | 每个就绪事件 1+ 次 | **可批量/可 0 次** |
| 支持的操作 | 有限 | 网络/管道 | **几乎所有**（读、写、accept、connect、send、fsync、splice、timeout...） |
| 缓冲注册 | ❌ | ❌ | ✅ `IORING_REGISTER_BUFFERS`（**零拷贝**） |
| 文件描述符注册 | ❌ | ❌ | ✅ 注册后无需传 fd |
| 批量提交 | ❌ | ❌ | ✅ |
| 队列深度 | 有限 | — | 参数化 |

**为什么快**：
1. **减少系统调用**：可以一次 `io_uring_enter` 提交多个操作、收割多个完成。
2. **零拷贝选项**：注册固定缓冲（`IORING_REGISTER_BUFFERS`）后，内核直接使用这些页，避免每次的地址校验和 pin。
3. **SQPOLL 模式完全免系统调用**（代价是内核线程轮询的 CPU 开销）。
4. **统一的接口**：网络 + 文件 IO 用同一套 API（传统上 epoll 管网络、libaio 管文件，两套机制）。

**典型使用（liburing）**：
```c
#include <liburing.h>
struct io_uring ring;
io_uring_queue_init(256, &ring, 0);

struct io_uring_sqe* sqe = io_uring_get_sqe(&ring);
io_uring_prep_read(sqe, fd, buf, len, offset);
io_uring_sqe_set_data(sqe, my_context);

io_uring_submit(&ring);

struct io_uring_cqe* cqe;
io_uring_wait_cqe(&ring, &cqe);
// cqe->res 是返回值，io_uring_cqe_get_data(cqe) 是上下文
io_uring_cqe_seen(&ring, &cqe);
```

**限制与注意**：
1. **内核版本要求**：5.1 基础，5.6+ 才比较完善；**很多新特性（如 `IORING_OP_*` 的扩展）需要 5.10/5.15+**。发行版如 CentOS 7（3.10）**完全不支持**。
2. **`io_uring` 曾多次出安全问题**（CVE），部分发行版/容器运行时**默认禁用它**（seccomp 过滤 `io_uring_setup`）—— Google 在 ChromeOS/Android 上禁用了。**启用前先确认内核与安全策略**。
3. **O_DIRECT 与 buffered IO**：早期 io_uring 对 buffered IO 是"用 worker 线程模拟"（不是真异步）；后续内核对此有改进，但**buffered IO 的异步性要确认内核版本**。
4. **编程模型复杂**：需要管理 SQ/CQ、处理 `-EAGAIN`、注册资源、考虑并行度。
5. **监控支持**：`perf`、`bpftrace` 对 io_uring 的支持在逐步完善。

**生态**：
- **liburing**：官方用户态库，简化使用。
- **Rust**：`tokio-uring`、`glommio`、`monoio`。
- **C++**：`liburing` 直接封装。
- **Nginx** 有 io_uring 实验分支；**RocksDB** 支持 io_uring；**ScyllaDB/Redpanda** 用 io_uring 提升吞吐。

**实践建议**：
1. **先确认内核版本与安全策略**（很多容器默认禁止）。
2. **CPU-bound 场景不需要**（io_uring 是 IO 密集的优化）。
3. **`epoll` 仍然完全够用** —— 除非确认 IO 系统调用开销是瓶颈，不要为了"新"而迁移。
4. 用 **SQPOLL** 时要注意 CPU 占用（要有空闲核）。
5. **配合 `IORING_REGISTER_BUFFERS`/`REGISTER_FILES`** 才能吃到大部分性能收益。

**面试延伸**：io_uring 的设计借鉴了 Windows 的 IOCP（**完成通知模型**）与 Solaris 的 AIO；与 `epoll`（**就绪通知模型**）的核心区别是：epoll 告诉你"可以做 IO 了"，io_uring 直接帮你**做完 IO** 再通知你。""",
    ),
    (
        "Linux",
        "内核模块,设备",
        2,
        r"""字符设备和块设备有什么区别？`/dev` 里的文件是怎么工作的？""",
        r"""**Linux 的设备分类**：

| 类型 | `ls -l` 首字符 | 访问单位 | 特点 | 例子 |
|---|---|---|---|---|
| **字符设备** | `c` | 字节流 | **顺序访问**，无缓冲（或简单缓冲） | `/dev/tty`、`/dev/null`、`/dev/random`、鼠标 |
| **块设备** | `b` | 块（512B~4KB） | **随机访问**，有缓冲（page cache）、可挂载文件系统 | `/dev/sda`、`/dev/nvme0n1`、`/dev/loop0` |
| 网络设备 | — | 包 | **没有设备文件**（用 socket 接口） | `eth0`、`lo` |

**设备文件里的"两个号"**：
```bash
$ ls -l /dev/sda /dev/null
brw-rw---- 1 root disk 8, 0 /dev/sda
crw-rw-rw- 1 root root 1, 3 /dev/null
```
- **主设备号（major）**：对应**哪个驱动**。
- **次设备号（minor）**：对应**该驱动下的哪个设备实例**。
- 内核通过 `major` 找到 `file_operations`（驱动的函数表），从而把 `read`/`write` 路由到驱动。

```bash
cat /proc/devices        # 已注册的主设备号
ls -l /sys/dev/char/1:3  # 通过 sysfs 看设备
```

**创建方式**：
```bash
mknod /dev/mydev c 240 0        # 手工创建设备文件
udev / systemd-udevd            # 现代系统自动创建（响应内核 uevent）
```

**`/dev` 的常见特殊设备**：
| 设备 | 作用 |
|---|---|
| `/dev/null` | 丢弃写入，读返回 EOF |
| `/dev/zero` | 读返回无限零字节 |
| `/dev/random` | 阻塞式随机源（熵不足会阻塞） |
| `/dev/urandom` | 非阻塞随机源（现代内核两者等价，推荐 urandom） |
| `/dev/full` | 写总是返回 ENOSPC（测试用） |
| `/dev/stdin`、`/dev/stdout`、`/dev/stderr` | 指向当前进程的 fd 0/1/2 |
| `/dev/fd/N` | 指向 fd N |
| `/dev/loop0` | 把一个文件当块设备（挂载 ISO 用） |
| `/dev/tty`、`/dev/pts/N` | 终端 / 伪终端 |
| `/dev/shm` | tmpfs（共享内存目录） |

**伪设备 vs 真实设备**：`/dev/null`、`/dev/zero`、`/dev/random` **不对应任何硬件**，是内核提供的特殊字符设备。

**块设备的层次**（以 NVMe SSD 为例）：
```
/dev/nvme0n1（块设备）
   ├── nvme0n1p1（分区）
   ├── nvme0n1p2
   └── 文件系统（ext4/xfs）→ 挂载点
或
   └── LVM PV → VG → LV → 文件系统
或
   └── RAID 成员
```
查看：
```bash
lsblk                     # 块设备树（最直观）⭐
lsblk -f                  # 带文件系统/挂载点
blkid                     # 设备 UUID
fdisk -l / parted -l      # 分区表
df -h / df -i             # 文件系统用量
```

**内核模块（LKM）**：
```bash
lsmod                     # 已加载模块
modinfo <mod>             # 模块信息（依赖、参数、路径）
modprobe <mod> [param=val]# 加载（自动解决依赖）⭐
modprobe -r <mod>         # 卸载
insmod file.ko / rmmod    # 低层（不处理依赖）
depmod -a                 # 重建依赖表

# 持久化
echo "modname param=1" > /etc/modules-load.d/modname.conf   # 开机加载
echo "blacklist badmod" > /etc/modprobe.d/blacklist.conf    # 禁止加载
```

**`/sys` 与 `/proc` 的作用**：
- `/sys`（sysfs）：**设备与驱动的结构化视图**（`/sys/class/net/eth0/`、`/sys/block/sda/`），可写以调整参数。
- `/proc`：**进程与内核的统计视图**（`/proc/cpuinfo`、`/proc/meminfo`、`/proc/<pid>/`）。

**实践要点**：
1. **不要把设备文件当普通文件复制**（`cp /dev/sda` 会无限读）。
2. **`dd` 要小心**（写错设备会毁数据）：`dd if=x of=/dev/sdX` 前务必 `lsblk` 确认。
3. **`/dev/sda` vs `/dev/sda1`**：前者是整个磁盘，后者是分区。
4. **`O_DIRECT` 绕过 page cache**（数据库用）；块设备默认走缓存。
5. **设备号在重启后可能变化** → 用 **UUID/LABEL** 挂载（`/etc/fstab` 用 `UUID=`）。
6. **`/dev/random` 阻塞问题**：老系统上启动时熵不足会卡（现在都用 `urandom` 或 `getrandom(2)`）。
7. **不要 `chmod 666 /dev/sda`**（等于给所有用户裸盘访问）。""",
    ),
    (
        "Linux",
        "系统调用,syscall",
        2,
        r"""系统调用是怎么实现的？`strace` 看到的那些调用有哪些开销？""",
        r"""**系统调用（syscall）**是用户程序请求内核服务的**唯一合法入口**。

**x86-64 的调用流程**：

```
用户态                              内核态
1. 把系统调用号放入 rax
2. 参数放入 rdi, rsi, rdx, r10, r8, r9
3. 执行 syscall 指令 ──────────▶  4. CPU 切换到 ring 0，跳转到 entry_SYSCALL_64
                                  5. 保存用户寄存器到内核栈
                                  6. 通过 rax 查 sys_call_table 找到处理函数
                                  7. 执行 sys_xxx()
8. ◀────────── 9. 把返回值放 rax，执行 sysret 回到用户态
```

- **参数最多 6 个**（寄存器限制），超过要用指针传结构体。
- **返回值**：负数是错误码（`-errno`），libc 包装后设置 `errno` 并返回 -1。
- **老方式 `int 0x80`**（32 位）比 `syscall` 指令慢（要过中断门）。

**开销来源**：
1. **模式切换（用户态 ↔ 内核态）**：保存/恢复寄存器、换栈（~100ns）。
2. **安全检查**：参数校验、权限检查（`CAP_*`）、路径解析。
3. **可能的上下文切换**：如果操作阻塞（如 `read` 等磁盘），进程被换出 → 微秒级。
4. **cache/TLB 影响**：内核代码/数据不在用户的工作集里。
5. **`ptrace` 附加**：被 `strace` 跟踪时**每条 syscall 停两次** → **慢 10~100 倍**。

**为什么"系统调用慢"是重要问题**：
- 典型 `read` 一次 ~1 微秒；如果程序每秒做 100 万次小 `read`，光是 syscall 就吃掉 1 秒 CPU。
- **优化方向**：批量（`readv`/`writev`/`io_uring`）、减少调用（缓冲、`mmap`）、用 vDSO 免陷入。

**vDSO（virtual DSO）**：
- 某些调用**不需要陷入内核**，内核把实现映射到用户空间直接执行。
- **`gettimeofday`、`clock_gettime`、`time`、`getcpu`** 都走 vDSO → 调用这些几乎是普通函数调用。
- 这就是"`clock_gettime` 比 `gettimeofday` 还快"的现象来源。

**查看**：
```bash
strace -c ./prog                     # 各 syscall 次数/耗时 ⭐
strace -T -tt ./prog                 # 每次调用的耗时
perf trace ./prog                    # 低开销的系统调用追踪
ltrace ./prog                        # 库函数（不是 syscall）
cat /proc/<pid>/syscall              # 查看进程当前卡在哪个 syscall ⭐
cat /proc/<pid>/stack                # 内核栈
ausyscall --dump                     # 列出所有系统调用号
```

**常见的"系统调用热点"**：
| 模式 | 优化 |
|---|---|
| 大量小 `read`/`write` | 加缓冲、`readv`/`writev`、`sendfile` |
| 大量 `open`/`close` | 复用 fd、缓存文件内容 |
| `futex` 热点 | 锁竞争（减少锁粒度、无锁） |
| `epoll_wait` 频繁返回 | 批量处理、调 `maxevents` |
| `nanosleep`/`clock_gettime` | 用 vDSO；减少定时器精度 |
| `brk`/`mmap` 频繁 | 用内存池 |

**关于 `strace` 的正确使用**：
1. **`strace -c` 很有用**（先看统计再决定跟谁）。
2. **`strace -f -p <pid>` 会拖慢整个服务** —— 生产上优先 `perf trace` 或 eBPF。
3. **`strace -yy`** 能把 fd 解析成路径，排查"打开了哪个文件"配 `-e trace=openat` 极其高效。
4. **`strace` 会改变竞态行为**（时序变化可能让 bug 消失），这是"海森堡 bug"的经典来源。

**安全相关**：
1. **seccomp** 能按 syscall 过滤（Docker 默认禁掉一批危险调用）。
2. **`ptrace` 被滥用**（注入进程）→ `yama/ptrace_scope` 限制。
3. **`io_uring_setup` 在新版被部分环境禁用**（安全考虑）。

**面试延伸**：**系统调用 vs 库函数 vs 内核中断**：
- 库函数（`printf`）可能**不涉及** syscall（缓冲）；也可能包装若干 syscall。
- **系统调用**是"陷入内核"的显式请求；**异常**（缺页、除零）是**被动**陷入。
- **`strace` 追的是 syscall**，`ltrace` 追的是**库函数**，`gdb` 是**用户态代码**。""",
    ),
    (
        "Linux",
        "管道,IPC 对比",
        2,
        r"""Linux 的进程间通信方式有哪些？各自适合什么场景？""",
        r"""| 方式 | 方向 | 是否跨主机 | 性能 | 典型场景 |
|---|---|---|---|---|
| **匿名管道 pipe** | 半双工（单向） | ❌ | 高（内核缓冲） | shell 的 `|`、父子进程 |
| **命名管道 FIFO** | 半双工 | ❌ | 高 | 无亲缘关系的进程 |
| **消息队列（SysV/POSIX）** | 双向 | ❌ | 中 | 结构化消息、有边界 |
| **共享内存（shm）** | 双向 | ❌ | **最快** | 大数据量共享 |
| **信号量 semaphore** | 同步 | ❌ | — | 配合共享内存做互斥/同步 |
| **信号 signal** | 单向通知 | ❌ | 高 | 事件通知（不带数据） |
| **socket（Unix domain）** | 双向 | ❌ | 高 | 本机 IPC + fd 传递 |
| **socket（TCP/UDP）** | 双向 | ✅ | 中 | 跨主机 |
| **文件 + 文件锁** | 双向 | ❌ | 低 | 简单持久化交换 |
| **eventfd / signalfd / timerfd** | 事件 | ❌ | 高 | 与 epoll 集成 |

**四种主要方式详解**：

**1. 匿名管道（pipe）**
```c
int fd[2];
pipe(fd);           // fd[0] 读端，fd[1] 写端
// fork 后父子各持一份
write(fd[1], "hi", 2);
read(fd[0], buf, sizeof buf);
```
- **单向**（半双工）；要双向通信需要两根管道。
- **只能用于有亲缘关系的进程**（fd 是继承的）。
- **容量有限**（默认 64KB，`F_GETPIPE_SZ`）；写满阻塞，`O_NONBLOCK` 时返回 `EAGAIN`。
- 写端全关闭后读端 `read` 返回 0（EOF）。
- **`SIGPIPE`**：读端全关闭后写入会收到 SIGPIPE（默认终止进程）—— 网络编程里常先 `signal(SIGPIPE, SIG_IGN)`。

**2. 命名管道（FIFO）**
```bash
mkfifo /tmp/myfifo
echo hello > /tmp/myfifo &     # 一个进程写
cat /tmp/myfifo                # 另一个进程读
```
- **有文件系统路径**，任意进程（同一台机器）可打开。
- 其余语义与匿名管道相同。

**3. 共享内存（最快）**
```c
// POSIX
int fd = shm_open("/myshm", O_CREAT|O_RDWR, 0600);
ftruncate(fd, 4096);
void* p = mmap(NULL, 4096, PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0);
// 或 System V: shmget/shmat
```
- **零拷贝**：数据直接映射到双方地址空间。
- **必须自己同步**（用信号量、`futex`、互斥锁的 `PTHREAD_PROCESS_SHARED` 属性）。
- **注意 shm 里的指针**：不同进程映射的地址可能不同，**不能存绝对指针**，要存偏移量。

**4. Unix domain socket（本机 IPC 首选）**
```c
int s = socket(AF_UNIX, SOCK_STREAM, 0);
struct sockaddr_un addr;
addr.sun_family = AF_UNIX;
strcpy(addr.sun_path, "/tmp/mysock");
bind(s, (void*)&addr, sizeof addr);
```
- **比 TCP loopback 快**（不走网络协议栈、不校验和）。
- 支持 `SOCK_STREAM`（可靠字节流）和 `SOCK_DGRAM`（消息边界）。
- **权限控制**：通过 socket 文件的权限位控制访问。
- **可以传递文件描述符**（`SCM_RIGHTS`）—— 这是 TCP 做不到的，**极其有用**（nginx/系统服务把监听的 fd 传给 worker）。
- **`SO_PEERCRED`** 可以拿到对端 PID/UID/GID（做权限校验）。
- **Docker/PostgreSQL/MySQL 本机连接都用它**（也是"挂载 socket 到容器"的原因）。

**eventfd / signalfd / timerfd**（现代事件驱动）：
```c
int efd = eventfd(0, EFD_NONBLOCK);      // 一个可读写的计数器 fd
int sfd = signalfd(-1, &mask, 0);        // 把信号变成可读事件
int tfd = timerfd_create(CLOCK_MONOTONIC, 0);  // 定时器变成 fd
```
**优势**：可以统一交给 `epoll`/`io_uring` 处理，**避免信号处理的异步陷阱**。

**选择建议**：
1. **同一台机器、性能优先** → **共享内存 + 信号量**。
2. **同一台机器、通用/需要 fd 传递/需要权限校验** → **Unix domain socket**。
3. **父子进程简单通信** → **pipe**。
4. **纯事件通知（无数据）** → **signal** 或 **eventfd**。
5. **需要跨主机** → **TCP/UDP socket**。
6. **与 epoll 集成的事件驱动程序** → **socketpair + eventfd/signalfd**（self-pipe 技巧）。

**对比记忆口诀**：**管道简单单向、共享内存最快但要自己同步、UDS 通用且能传 fd、socket 唯一能跨机**。""",
    ),
    (
        "Linux",
        "CPU 亲和性,NUMA",
        3,
        r"""CPU 亲和性和 NUMA 是什么？对性能有什么影响？""",
        r"""**CPU 亲和性（affinity）**：把一个进程/线程**绑定**到特定的 CPU 核上，不参与调度迁移。

**为什么需要**：
1. **cache 局部性**：线程在同一核上运行，L1/L2 缓存保持热态；迁移到别的核要重新填充。**跨 NUMA 节点迁移代价更大**（L3 也是分片的）。
2. **确定性延迟**：避免被调度到繁忙的核。
3. **隔离干扰**：把关键线程与噪音线程分开。
4. **配合中断亲和**：把网卡中断与处理线程放在同一 NUMA 节点。

**查看与设置**：
```bash
nproc                                   # 核数
lscpu                                   # CPU 拓扑（socket/core/thread）
cat /proc/cpuinfo | grep -E "processor|physical id|core id"

taskset -c 0,1 ./prog                   # 绑定到 CPU 0 和 1 ⭐
taskset -pc 2 <pid>                     # 修改运行中进程的亲和性
taskset -p <pid>                        # 查看

# 代码里
#include <sched.h>
cpu_set_t set; CPU_ZERO(&set); CPU_SET(2, &set);
sched_setaffinity(0, sizeof set, &set);

# 线程级（pthread）
pthread_setaffinity_np(th, sizeof set, &set);
```

**NUMA（Non-Uniform Memory Access）**：

多路服务器上，每个 CPU 有**本地内存**，访问本地内存快、访问其他节点的内存慢（跨节点要走互联总线）。

```
NUMA node 0                  NUMA node 1
  CPU 0-15  ◀── QPI/UPI ──▶  CPU 16-31
  本地内存                   本地内存
  访问延迟 100ns             远端访问延迟 ~180ns
```

**查看**：
```bash
numactl --hardware            # 节点与内存分布 ⭐
numastat                      # 每个节点的命中统计
numastat -p <pid>             # 某进程的跨节点访问情况
lscpu | grep NUMA
cat /sys/devices/system/node/node0/meminfo
```

**控制**：
```bash
numactl --cpunodebind=0 --membind=0 ./prog      # 绑到 node0 的 CPU 与内存 ⭐
numactl --interleave=all ./prog                 # 交错分配（带宽优先）
numactl --preferred=0 ./prog
```

**numa_balancing**（内核自动迁移）：`/proc/sys/kernel/numa_balancing`（默认 1）。内核会周期性检测"内存访问与所在 CPU 不匹配"的页并迁移，但**有额外开销**，某些负载（数据库）会关掉它。

**性能影响（实测经验）**：
1. **跨 NUMA 访问延迟增加 ~40%~80%**，带宽下降（受互联总线限制）。
2. **"远端内存"过多会成为瓶颈**：`numastat` 显示 `numa_foreign`（本该本地却分配到了远端的页）高 → 需要 `--membind` 或调整分配策略。
3. **第一次触碰（first-touch）原则**：内存分配到"第一次访问它的 CPU"所在节点 —— 所以**多线程程序要在目标线程上初始化它要用的内存**（否则主线程初始化、其他线程访问 = 全跨节点）。
4. **线程池与 NUMA 对齐**：按 NUMA 节点分组线程和内存，是高性能服务的常见优化。

**相关工具与内核特性**：
| 特性/工具 | 作用 |
|---|---|
| `numactl` | 绑定 CPU 与内存策略 |
| `numad` | 自动 NUMA 守护进程（HPC 用） |
| `hwloc` | 查看/操作硬件拓扑（含 cache、PCI） |
| `lstopo` | 可视化拓扑图 ⭐ |
| `perf stat -e node-loads,node-load-misses` | 跨节点访问计数 |
| `migratepages` | 手工迁移页 |
| `MPOL_*`（`mbind`/`set_mempolicy`） | 代码里设置内存策略 |

**中断与 NUMA**：
```bash
cat /proc/interrupts                    # 每个 IRQ 在各 CPU 上的分布
cat /sys/class/net/eth0/device/numa_node
# 把网卡中断绑到与处理线程同一节点
echo <mask> > /proc/irq/<n>/smp_affinity
```
**最佳实践**：网卡 → 同节点的 CPU → 同节点的内存，避免数据"跨节点来回跑"。

**实践建议**：
1. **先用 `numastat -p` 确认是否有跨节点问题**，再考虑绑定。
2. **不要盲目 `numactl --interleave=all`**（带宽优先但延迟变差）；延迟敏感用 `--membind`。
3. **注意"first touch"**：让使用内存的线程自己初始化。
4. **容器环境**：`cpuset` cgroup 限制 CPU，但 **NUMA 策略要单独配置**（k8s 的 `topologyManager` 可做）。
5. **单路机器没有 NUMA 问题**（只有一个节点）。
6. **`lstopo` 是理解硬件拓扑最快的方式**（包括超线程、cache、NUMA、PCI 设备归属）。""",
    ),
    (
        "Linux",
        "HugePages,内存优化",
        3,
        r"""什么是 HugePages（大页）？为什么数据库和虚拟机要用它？""",
        r"""**大页（HugePages）**：用比默认 4KB 大得多的页（x86-64 上是 **2MB** 和 **1GB**）。

**为什么大页更快**：

1. **TLB 覆盖范围剧增**：
   - 4KB 页 × 1536 个 TLB 项 = 6MB 覆盖。
   - 2MB 页 × 1536 个 TLB 项 = **3GB 覆盖**（500 倍）。
   - → **TLB miss 大幅减少**，页表遍历（几百个周期）几乎消失。
2. **页表更小**：2MB 页省掉最后一级页表（一个页表项覆盖 2MB 而非 4KB）→ 页表内存占用减少数百倍。
3. **缺页中断更少**：一次 fault 覆盖 2MB。
4. **减少内核管理开销**：更少的 `struct page`、更少的 LRU 操作。

**两种大页**：

| 类型 | 说明 |
|---|---|
| **显式 HugePages（hugetlbfs）** | 需预先保留（`nr_hugepages`），**不会被换出**，确定性好 |
| **透明大页（THP）** | 内核自动把连续 4KB 页合并成 2MB，**无需配置** |

**显式 HugePages 配置**：
```bash
# 预留 1024 个 2MB 大页（= 2GB）
echo 1024 > /proc/sys/vm/nr_hugepages

# 查看
cat /proc/meminfo | grep -i huge
# HugePages_Total:    1024
# HugePages_Free:      980
# Hugepagesize:       2048 kB

# 持久化
echo "vm.nr_hugepages = 1024" > /etc/sysctl.d/99-hugepages.conf

# 按 NUMA 节点预留
echo 512 > /sys/devices/system/node/node0/hugepages/hugepages-2048kB/nr_hugepages
```
**使用**：
```bash
mount -t hugetlbfs none /mnt/huge
# 或 mmap with MAP_HUGETLB
void* p = mmap(NULL, len, PROT_READ|PROT_WRITE,
               MAP_PRIVATE|MAP_ANONYMOUS|MAP_HUGETLB, -1, 0);
```

**透明大页（THP）**：
```bash
cat /sys/kernel/mm/transparent_hugepage/enabled
# [always] madvise never
```
| 值 | 行为 |
|---|---|
| `always` | 尽可能用大页（默认在很多发行版上） |
| `madvise` | 只用 `madvise(MADV_HUGEPAGE)` 标记的区域 |
| `never` | 禁用 |

**THP 的问题（为什么很多数据库建议关掉）**：
1. **延迟尖刺**：后台 `khugepaged` 合并页时会暂停进程（分配 2MB 连续内存需要整理）；COW 时一个 4KB 写的 fault 要复制整个 2MB。
2. **内存浪费**：只用一个字节也要占满 2MB（除非内核做拆分）。
3. **不可预测**：分配延迟抖动，对延迟敏感的服务（Redis、MongoDB）不友好。
4. **碎片**：长期运行的系统可能无法分配 2MB 连续物理内存。

**因此的实践**：
- **Redis**：官方建议 `never` 或 `madvise`。
- **MongoDB**：建议 `never`。
- **MySQL**：用**显式 HugePages**（`innodb_buffer_pool_size` 配合大页）更好。
- **HPC / DPDK / 虚拟机（KVM）**：强烈推荐大页。

**谁在用**：
| 场景 | 用法 |
|---|---|
| **KVM/QEMU 虚拟机** | 用 2MB/1GB 大页做 guest 内存后端，显著提升性能 |
| **数据库** | InnoDB buffer pool、Oracle SGA 用大页 |
| **DPDK/高性能网络** | 必须用大页（配合 `--membind`） |
| **JVM** | `-XX:+UseLargePages` |
| **Redis** | 一般**不用**（反而受 THP 影响） |

**1GB 大页**：需要内核参数 `hugepagesz=1G hugepages=N`（**只能在启动时配置**），适合大内存的数据库/虚拟化。

**相关参数**：
| 参数 | 作用 |
|---|---|
| `vm.nr_hugepages` | 2MB 大页数量 |
| `vm.nr_overcommit_hugepages` | 允许超额（不足时从普通页池补） |
| `kernel.shmmax` | 共享内存段上限（大页常见搭配） |
| `vm.hugetlb_shm_group` | 允许用大页的用户组 |
| `transparent_hugepage/enabled` | THP 开关 |
| `transparent_hugepage/defrag` | THP 碎片整理策略 |

**监控**：
```bash
cat /proc/meminfo | grep -i huge
grep -i huge /proc/vmstat           # 大页相关的 vmstat 计数
perf stat -e dTLB-load-misses       # 对比大页前后的 TLB miss
```

**实践建议**：
1. **先测再上** —— 大页的效果高度依赖工作集大小与访问模式。
2. **延迟敏感服务的常见配置**：`THP=never` 或 `madvise`，避免抖动。
3. **数据库/虚拟化**：用**显式 HugePages**（可控、不换出）。
4. **预留大页会"吃掉"内存**（`HugePages_Total` 应接近实际需求，避免浪费）。
5. **注意 NUMA 节点上分别预留**（跨节点用大页会失去意义）。
6. **容器里用大页**需要显式挂载 `hugetlbfs` 并配置 cgroup。""",
    ),
    (
        "Linux",
        "日志,journald",
        2,
        r"""Linux 的日志系统是怎样的？怎么排查日志问题？""",
        r"""**两条并行的日志体系**：

| 体系 | 组件 | 存储 | 特点 |
|---|---|---|---|
| **传统 syslog** | `rsyslog`/`syslog-ng` | 文本文件 `/var/log/*` | 简单、可读、易解析 |
| **systemd journal** | `systemd-journald` | 二进制 `/var/log/journal/` 或 `/run/log/journal/` | 结构化、索引快、带元数据 |

现代发行版**两者都在**：应用写 syslog → journald 收集 → 也可转发到 rsyslog 落文本文件。

**传统日志文件**：
```
/var/log/messages         # 系统消息（RHEL 系）
/var/log/syslog           # 系统消息（Debian 系）
/var/log/auth.log         # 认证日志（登录、sudo）
/var/log/secure           # 认证日志（RHEL）
/var/log/kern.log         # 内核日志（dmesg 的来源）
/var/log/dmesg            # 启动时的内核日志快照
/var/log/cron             # 定时任务
/var/log/nginx/*.log      # 应用日志
/var/log/audit/audit.log  # auditd
```

**journald 常用命令**：
```bash
journalctl                          # 全部（按时间倒序的分页）
journalctl -f                       # 实时跟踪（tail -f）⭐
journalctl -u blog.service          # 按 unit ⭐
journalctl -u blog.service -f
journalctl -u blog.service --since "10 min ago"
journalctl -u blog.service --since today --until "2 hours ago"
journalctl -p err -b                # 本次启动的错误及以上
journalctl -b                       # 本次启动；-b -1 上次启动 ⭐
journalctl -k                       # 内核消息（等价 dmesg）⭐
journalctl _PID=1234                # 按 PID
journalctl /usr/sbin/sshd           # 按可执行文件
journalctl -o json-pretty -n 1      # JSON 输出（含全部元数据）⭐
journalctl -n 100 --no-pager
journalctl --disk-usage
journalctl --vacuum-size=500M       # 清理到 500M
journalctl --vacuum-time=7d
```

**字段过滤**（journald 是结构化的）：
```bash
journalctl _COMM=nginx _PID=1234
journalctl _SYSTEMD_UNIT=blog.service PRIORITY=3
journalctl SYSLOG_IDENTIFIER=myapp
```

**持久化 journal**：
```bash
mkdir -p /var/log/journal
systemd-tmpfiles --create --prefix /var/log/journal
systemctl restart systemd-journald
# 或编辑 /etc/systemd/journald.conf: Storage=persistent
```
**不持久化时**日志只存在 `/run/log/journal`（内存），**重启即失**（这是排障时"上次崩溃的日志找不到了"的原因）。

**journald 配置**（`/etc/systemd/journald.conf`）：
```ini
[Journal]
Storage=persistent
SystemMaxUse=500M
SystemMaxFileSize=50M
MaxRetentionSec=1month
ForwardToSyslog=yes
RateLimitIntervalSec=30s
RateLimitBurst=10000        # 默认限制！日志突发会被丢弃 ⭐
```
**`RateLimitBurst` 是常见坑**：默认每秒只允许有限条，日志量大时会被静默丢弃（`journalctl` 里能看到 "Suppressed N messages"）。**排查"日志缺失"时先看这个。**

**`dmesg`**（内核环形缓冲）：
```bash
dmesg -T                     # 带人类可读时间 ⭐
dmesg -T -l err,warn         # 只显示错误/警告
dmesg -w                     # 实时跟踪
dmesg | grep -i -E "oom|error|fail|panic"
```
**注意**：环形缓冲有大小限制（`kernel.printk`、`log_buf_len`），**日志会被覆盖**。

**日志排查思路**：
1. **服务起不来** → `journalctl -u <svc> -n 100 --no-pager` + `systemctl status`（含最后几行）。
2. **莫名重启** → `journalctl -b -1`（上次启动）+ `dmesg -T | grep -i oom`。
3. **日志丢了** → 检查 `Storage=`、`RateLimitBurst`、磁盘空间（`df -h /var`）。
4. **时间对不上** → 检查时区（`timedatectl`）与 `--utc`。
5. **`ssh` 登录失败** → `journalctl -u sshd` 或 `/var/log/auth.log`。
6. **磁盘满是日志** → `journalctl --disk-usage`、`du -sh /var/log/*`、配额与轮转。

**日志轮转（logrotate）**：
```bash
/etc/logrotate.conf
/etc/logrotate.d/*
# 手动触发
logrotate -f /etc/logrotate.d/nginx
```
**注意**：应用若不支持 `reopen`（`SIGHUP` 或 `copytruncate`），轮转后仍写旧的 inode → **日志"消失"**（实际写到已删除文件）。用 `lsof | grep deleted` 可确认。

**应用日志的最佳实践**：
1. **写 stdout/stderr，交给 journald/容器运行时收集**（12-factor）。
2. **不要自己管理轮转**（除非文件很大）。
3. **结构化（JSON）日志**便于检索。
4. **分级**（error/warn/info/debug），生产用 info 及以上。
5. **带 request id** 便于跨服务追踪。

**关键工具**：
| 工具 | 用途 |
|---|---|
| `journalctl` | systemd 日志 |
| `dmesg` | 内核日志 |
| `logrotate` | 日志轮转 |
| `rsyslog`/`syslog-ng` | 集中转发 |
| `logger` | 命令行写 syslog：`logger -t mytag "msg"` |
| `ELK`/`Loki`/`Graylog` | 集中式日志平台 |""",
    ),
    (
        "Linux",
        "磁盘,RAID,LVM",
        2,
        r"""磁盘分区、RAID、LVM 分别解决什么问题？""",
        r"""**三个层次**：

```
物理磁盘 /dev/sda
  └── 分区表（MBR/GPT）→ /dev/sda1, /dev/sda2
       └── 可选：RAID（mdadm）/ LVM（PV → VG → LV）
            └── 文件系统（ext4/xfs）
                 └── 挂载点
```

**1. 分区表**

| | MBR（msdos） | GPT |
|---|---|---|
| 最大磁盘 | 2 TiB | **9.4 ZiB** |
| 分区数 | 4 主分区（或 3 主 + 扩展） | **128 个**（默认） |
| 引导 | BIOS + MBR 引导代码 | UEFI + ESP 分区 |
| 备份 | ❌（分区表损坏=全丢） | ✅（头部+尾部双份） |
| 校验 | ❌ | ✅ CRC32 |

**新装机一律用 GPT**（`parted -s /dev/sda mklabel gpt`）。

**2. RAID（冗余或性能）**

| 级别 | 最少盘 | 容错 | 容量利用率 | 说明 |
|---|---|---|---|---|
| RAID 0 | 2 | ❌ 无 | 100% | 条带化，**性能最高，坏一块全丢** |
| RAID 1 | 2 | ✅ 1 块 | 50% | 镜像，读性能好 |
| RAID 5 | 3 | ✅ 1 块 | (n-1)/n | 奇偶校验，**写惩罚**，重建风险高 |
| RAID 6 | 4 | ✅ 2 块 | (n-2)/n | 双校验，重建更安全 |
| RAID 10 | 4 | ✅ 每组 1 块 | 50% | **镜像+条带，生产最常用** ⭐ |

**软 RAID**：
```bash
mdadm --create /dev/md0 --level=10 --raid-devices=4 /dev/sd[b-e]
cat /proc/mdstat                    # 状态（含重建进度）⭐
mdadm --detail /dev/md0
mdadm /dev/md0 --fail /dev/sdb1 --remove /dev/sdb1     # 模拟/处理故障
mdadm /dev/md0 --add /dev/sdf1                          # 加新盘重建
```

**硬 RAID vs 软 RAID**：
- 硬 RAID 卡有电池保护缓存（BBU），写性能好，但成本高、有厂商锁定。
- 软 RAID（mdraid）灵活免费，CPU 开销在现代多核上可接受。
- **云上一般直接用云厂商的云盘**，不需要自己 RAID（但可用 RAID 0 提升吞吐）。

**3. LVM（Logical Volume Manager）—— 灵活管理**

**三层**：
```
PV（物理卷，Physical Volume）   ← /dev/sdb1, /dev/md0
  └── VG（卷组，Volume Group）  ← 把多个 PV 合成一个池
       └── LV（逻辑卷，Logical Volume） ← 从池里切出的"虚拟分区"，/dev/vg0/lv_data
```

```bash
# 创建
pvcreate /dev/sdb1 /dev/sdc1
vgcreate vg0 /dev/sdb1 /dev/sdc1
lvcreate -L 100G -n lv_data vg0
mkfs.ext4 /dev/vg0/lv_data
mount /dev/vg0/lv_data /data

# 查看
pvs / vgs / lvs
lsblk

# 扩容（LVM 的核心价值 —— 在线扩容）⭐
lvextend -L +50G /dev/vg0/lv_data
resize2fs /dev/vg0/lv_data          # ext4 在线扩容
# 或 xfs_growfs /data                # xfs 扩容

# 快照
lvcreate -L 10G -s -n lv_snap /dev/vg0/lv_data
```

**LVM 的核心价值**：
1. **在线扩容**（不用停机改分区）。
2. **跨磁盘的卷**（一个 LV 可以横跨多个 PV）。
3. **快照**（备份用）。
4. **thin provisioning**（精简置备，超额分配）。
5. **条带/镜像**（`lvcreate -i 2 -I 256k`、`--mirrors`）。

**LVM vs 分区**：
| | 传统分区 | LVM |
|---|---|---|
| 扩容 | 需要空闲相邻空间，风险高 | **在线，任意空间** |
| 跨盘 | ❌ | ✅ |
| 快照 | ❌ | ✅ |
| 性能 | 略好（无映射层） | 略微开销（可忽略） |
| 复杂度 | 低 | 中 |

**关键实践**：
1. **`/etc/fstab` 用 UUID 或 LVM 路径**（设备名可能变）。
2. **不要把整个磁盘分给根分区**（留空间或全给 LVM，便于扩容）。
3. **RAID 10 是生产首选**（性能 + 容错兼顾）；RAID 5 在大盘下**重建期间二次故障风险高**，慎用。
4. **重建 RAID 时不要做高负载运维**（重建压力最大）。
5. **定期验证备份可恢复**（RAID 不是备份！）。
6. **云盘扩容**：先扩云盘 → 扩分区（`growpart`）→ 扩文件系统（`resize2fs`/`xfs_growfs`）。
7. **监控**：`smartctl -a /dev/sda`（SMART 健康）、`cat /proc/mdstat`（RAID 状态）、`iostat -x`。

**相关命令速查**：
| 目的 | 命令 |
|---|---|
| 看块设备树 | `lsblk` |
| 看分区表 | `fdisk -l` / `parted -l` |
| 在线扩分区 | `growpart /dev/sda 1` |
| 扩 ext4 | `resize2fs` |
| 扩 xfs | `xfs_growfs <挂载点>` |
| RAID 状态 | `cat /proc/mdstat` |
| 磁盘健康 | `smartctl -a /dev/sda` |
| IO 性能 | `iostat -xz 1` / `fio` |""",
    ),
    (
        "Linux",
        "管道,重定向",
        1,
        r"""Shell 的管道和重定向是怎么实现的？`2>&1` 是什么意思？""",
        r"""Shell 的管道和重定向本质上是**对文件描述符的 `dup2` 操作**。

**重定向**：

| 写法 | 含义 |
|---|---|
| `> file` | stdout 重定向到文件（截断） |
| `>> file` | stdout 追加到文件 |
| `< file` | stdin 来自文件 |
| `2> file` | stderr 重定向到文件 |
| `2>&1` | **把 fd 2 复制成 fd 1 的当前目标** |
| `&> file` / `> file 2>&1` | stdout 和 stderr 都到文件 |
| `2>/dev/null` | 丢弃 stderr |
| `<<EOF` | here-document |
| `<<< "str"` | here-string |
| `&>` | bash 扩展（两者都重定向） |

**`2>&1` 的顺序很重要**：
```bash
cmd > file 2>&1      # ✅ 两者都进 file
cmd 2>&1 > file      # ❌ stderr 还是到终端！先复制了当时的 stdout（终端）
```
因为 `2>&1` 是"把 fd 2 复制为**当前** fd 1 指向的目标"。所以**必须先重定向 stdout，再复制**。

**实现（C 伪代码）**：
```c
// cmd > file
int fd = open("file", O_WRONLY|O_CREAT|O_TRUNC, 0666);
dup2(fd, STDOUT_FILENO);      // 让 fd 1 指向 file
close(fd);
execvp(...);

// cmd1 | cmd2
int p[2]; pipe(p);            // p[0] 读端，p[1] 写端
if (fork() == 0) {            // 子进程 = cmd1
    dup2(p[1], STDOUT_FILENO); close(p[0]); close(p[1]);
    execvp("cmd1", ...);
}
if (fork() == 0) {            // 子进程 = cmd2
    dup2(p[0], STDIN_FILENO);  close(p[0]); close(p[1]);
    execvp("cmd2", ...);
}
close(p[0]); close(p[1]);     // 父进程必须关掉两端，否则读端不会 EOF
wait(NULL); wait(NULL);
```
**注意**：父进程必须关闭管道两端，否则**读端不会收到 EOF**（因为写端还没全关）。

**管道的特点**：
1. **并行执行**（不是先跑完左边再跑右边）→ `cmd1 | cmd2` 两者同时跑。
2. **默认只连 stdout → stdin**，stderr 仍到终端（所以要 `2>&1 |`）。
3. **管道容量有限**（默认 64KB，`ulimit -p` 相关）；满了写端阻塞（这是"背压"机制）。
4. **`set -o pipefail`**：让管道中任一环节失败导致整体失败（默认只看最后一个命令的退出码）。
```bash
set -o pipefail
cmd1 | cmd2 || echo "有命令失败"
```
5. **`PIPESTATUS`** 数组保存每个命令的退出码。

**其它相关**：
| 语法 | 作用 |
|---|---|
| `cmd \| tee file` | 既输出到终端又写文件 |
| `cmd \|& tee file` | 含 stderr |
| `exec 3>file` | 打开 fd 3 供后续使用 |
| `cmd > >(tee a) 2> >(tee b >&2)` | 进程替换（process substitution） |
| `{ cmd1; cmd2; } > file` | 命令组重定向 |
| `cmd \| xargs ...` | 把输出变成参数 |

**`/dev/fd/N`** 与 **`/dev/stdout`** 是"用文件名表示 fd"的桥梁，让只接受文件名的程序也能配合重定向。

**实践**：
```bash
# 同时看输出和保存日志
./server 2>&1 | tee server.log

# 丢弃所有输出
cmd >/dev/null 2>&1

# 分离正常输出与错误输出
cmd > out.log 2> err.log

# 逐行处理
grep ERROR app.log | awk '{print $1}' | sort | uniq -c | sort -rn
```""",
    ),
    (
        "Linux",
        "grep,sed,awk,find",
        2,
        r"""`grep`、`sed`、`awk`、`find` 的常用用法有哪些？""",
        r"""**`grep`：文本搜索**
```bash
grep -i "error" app.log            # 忽略大小写
grep -r "TODO" src/                # 递归
grep -rn --include="*.cpp" "TODO" .# 只搜 cpp，带行号
grep -v "DEBUG" app.log            # 反向（不含）
grep -c "error" app.log            # 计数
grep -E "err(or|ors)" app.log      # 扩展正则
grep -P "\d{4}-\d{2}" app.log      # Perl 正则
grep -A 3 -B 3 "panic" app.log     # 前后 3 行上下文 ⭐
grep -o '"[^"]*"' file             # 只输出匹配部分
grep -l "pattern" *.log            # 只列出文件名
grep -w "test" file                # 整词匹配
grep -m 5 "x" file                 # 最多匹配 5 次
grep -q "x" file && echo found     # 静默（只看退出码）
# 排除目录
grep -rn "x" . --exclude-dir=.git --exclude-dir=node_modules
```
**`ripgrep`（rg）** 是现代替代（默认递归、忽略 `.gitignore`、快得多）。

**`sed`：流编辑器**
```bash
sed 's/old/new/' file              # 替换（每行第一个）
sed 's/old/new/g' file             # 全局替换 ⭐
sed -i 's/old/new/g' file          # 原地修改 ⭐
sed -i.bak 's/a/b/g' file          # 原地修改 + 备份
sed -n '10,20p' file               # 打印 10~20 行
sed -n '/start/,/end/p' file       # 打印区间
sed '3d' file                      # 删除第 3 行
sed '/pattern/d' file              # 删除匹配行
sed 's/^/PREFIX /' file            # 行首插入
sed -E 's/(\w+)@(\w+)/\2@\1/' file # 扩展正则 + 反向引用
sed '/PATTERN/a\追加的行' file      # 匹配行后追加（GNU）
```
**注意**：`sed -i` 在 macOS 上要 `sed -i '' `（BSD sed 差异）。

**`awk`：结构化文本处理**
```bash
awk '{print $1, $3}' file          # 打印第 1、3 列
awk -F: '{print $1}' /etc/passwd   # 指定分隔符
awk 'NR>1 {sum += $2} END {print sum}' file   # 求和
awk '$3 > 100 {print}' file        # 条件过滤
awk '/ERROR/ {count++} END {print count}' file
awk 'BEGIN{print "start"} {print} END{print "end"}' file
awk '{a[$1]++} END {for (k in a) print k, a[k]}' file   # 分组计数 ⭐
awk 'NR%2==0' file                 # 偶数行
awk 'length($0) > 80' file
awk -v x=10 '$1 > x' file          # 外部变量
awk '{printf "%-10s %5d\n", $1, $2}' file   # 格式化输出
```
**内置变量**：`$0`（整行）、`$1..$n`（字段）、`NF`（字段数）、`NR`（行号）、`FNR`（当前文件行号）、`FS`（输入分隔符）、`OFS`（输出分隔符）。

**`find`：文件查找**
```bash
find /var/log -name "*.log"                    # 按名字
find . -iname "*.LOG"                          # 忽略大小写
find . -type f -size +100M                     # 大于 100M 的普通文件 ⭐
find . -type d -name ".git" -prune -o -name "*.cpp" -print   # 排除目录
find . -mtime -7                               # 7 天内修改
find . -mmin -60                               # 60 分钟内修改
find . -newer file.txt                         # 比某文件新
find . -perm -4000 -type f                     # SUID 文件
find . -empty                                  # 空文件/目录
find . -user nginx -o -group www               # 按属主/属组
find . -name "*.tmp" -delete                   # 删除（危险！先 -print 验证）
find . -name "*.log" -exec gzip {} \;          # 逐个执行
find . -name "*.log" -exec gzip {} +           # 批量执行（更快）⭐
find . -name "*.txt" -print0 | xargs -0 rm     # 处理含空格的文件名 ⭐
```

**组合威力示例**：
```bash
# 找出最大的 10 个文件
find / -type f -size +100M -exec du -h {} + 2>/dev/null | sort -rh | head

# 统计 nginx 日志中访问量 top10 的 IP
awk '{print $1}' /var/log/nginx/access.log | sort | uniq -c | sort -rn | head

# 统计各状态码
awk '{print $9}' access.log | sort | uniq -c | sort -rn

# 批量重命名
find . -name "*.jpeg" -exec bash -c 'mv "$0" "${0%.jpeg}.jpg"' {} \;

# 按小时统计日志量
awk '{print substr($4, 2, 14)}' access.log | uniq -c
```

**性能提示**：
1. **`grep -r` 在大目录上慢** → 用 `rg`（ripgrep）或 `ag`。
2. **`find -exec ... \;` 每个文件一次进程** → 用 `+` 或 `xargs`。
3. **`xargs` 要配 `-0`** 处理含空格文件名。
4. **`sort` 大文件**：`sort -S 2G` 加大内存缓冲、`--parallel`、`LC_ALL=C` 加速排序（字节序比较更快）。
5. **管道越短越好**（每个阶段都是一次进程 + IO）。""",
    ),
    (
        "Linux",
        "用户,组,认证",
        2,
        r"""Linux 的用户和组是怎么管理的？`/etc/passwd`、`/etc/shadow` 分别是什么？""",
        r"""**四个关键文件**：

| 文件 | 内容 | 权限 |
|---|---|---|
| `/etc/passwd` | 用户账号信息（含 UID/GID/home/shell） | `644` 所有人可读 |
| `/etc/shadow` | **密码哈希**与密码策略 | `640`（或 `000`），**只有 root 可读** ⭐ |
| `/etc/group` | 组信息（组名、GID、成员） | `644` |
| `/etc/gshadow` | 组的加密密码与管理员 | `640` |

**`/etc/passwd` 字段**：
```
root:x:0:0:root:/root:/bin/bash
 │   │ │ │  │     │      └── 登录 shell
 │   │ │ │  │     └───────── 家目录
 │   │ │ │  └─────────────── 描述（GECOS）
 │   │ │ └─────────────────  主组 GID
 │   │ └───────────────────  UID
 │   └─────────────────────  密码占位符（x 表示在 shadow 里）
 └─────────────────────────  用户名
```
**UID 约定**：
- `0` = root；`1~999` 系统账号（服务用）；`1000+` 普通用户。

**`/etc/shadow` 字段**：
```
user:$6$salt$hash:19000:0:99999:7:::
      │            │   │  │   │ └─ 过期前警告天数
      │            │   │  │   └─── 密码最长有效天数
      │            │   │  └─────── 两次修改最小间隔
      │            │   └────────── 最后修改日（从 1970-01-01 起的天数）
      │            └────────────── 距过期还有多少天时可改
      └─────────────────────────── 密码哈希（$6$ = SHA-512）
```
> **密码哈希前缀**：`$1$` MD5（已弃用）、`$5$` SHA-256、`$6$` SHA-512、`$y$` yescrypt（现代）。哈希**加盐**，用于防彩虹表。

**用户管理命令**：
```bash
useradd -m -s /bin/bash -G sudo,docker alice    # 建用户 + 家目录 + shell + 附加组 ⭐
passwd alice                                     # 设密码
usermod -aG docker alice                         # 追加组（不加 -a 会覆盖！）⭐
userdel -r alice                                 # 删除用户与家目录
id alice                                         # 查看 UID/GID/所属组 ⭐
groups alice
who / w / last / lastlog                          # 谁登录了
chage -l alice                                    # 密码过期策略
chage -M 90 -W 7 alice                            # 最长 90 天，提前 7 天警告
```
**组管理**：
```bash
groupadd devs
groupmod -n newname oldname
gpasswd -a alice devs        # 加成员
gpasswd -d alice devs        # 移成员
```
**su 与 sudo**：
```bash
su - user             # 切换用户并加载其环境（- 重要）
sudo cmd              # 以 root 执行
sudo -u nginx cmd     # 以指定用户执行
sudo -i               # 交互式 root shell
sudo -l               # 查看自己被允许的命令 ⭐
visudo                # 安全编辑 /etc/sudoers（会做语法检查）⭐
```
**`/etc/sudoers` 语法**：
```
# 用户 主机=(可切换用户) 命令
alice ALL=(ALL:ALL) ALL
%sudo ALL=(ALL:ALL) ALL              # % 表示组
www-data ALL=(root) NOPASSWD: /bin/systemctl restart nginx
Defaults    env_reset, timestamp_timeout=15
```
**推荐把自定义规则放 `/etc/sudoers.d/*`**（不要改主文件，升级会覆盖）。

**认证相关**：
| 机制 | 说明 |
|---|---|
| **PAM**（`/etc/pam.d/`） | 可插拔认证模块，控制登录、密码策略、`su`/`sudo` |
| **NSS**（`/etc/nsswitch.conf`） | 名字服务来源顺序（files → ldap → sss ...） |
| **LDAP/AD/SSSD** | 集中式用户目录（企业环境） |
| **SSSD** | 缓存 LDAP/Kerberos 认证 |
| **Kerberos** | 票据式认证 |

**SSH 密钥登录（生产必备）**：
```bash
# 客户端生成
ssh-keygen -t ed25519 -C "me@example.com"        # ed25519 现代首选
# 上传公钥
ssh-copy-id user@host
# 或手工追加到远端 ~/.ssh/authorized_keys

# 服务端 /etc/ssh/sshd_config
PermitRootLogin no                    # 禁止 root 直登 ⭐
PasswordAuthentication no             # 只用密钥 ⭐
PubkeyAuthentication yes
Port 2222                             # 改端口（弱化扫描）
AllowUsers alice                      # 白名单
```
**排查 SSH 登录失败**：
```bash
ssh -v user@host                      # 详细日志 ⭐
journalctl -u sshd -n 50
cat /var/log/auth.log | grep sshd
ls -ld ~/.ssh ~/.ssh/authorized_keys  # 权限必须 700 / 600 ⭐
```
**权限是常见坑**：`~/.ssh` 必须 `700`、`authorized_keys` 必须 `600`、家目录不能被组/其他写 —— 否则 `sshd` **拒绝使用密钥**（`StrictModes`）。

**安全实践**：
1. **禁用 root 直接登录**（`PermitRootLogin no`），用普通用户 + `sudo`。
2. **禁用密码登录**（只用密钥），并给密钥设 passphrase。
3. **不要用 `usermod -aG` 时漏掉 `-a`**（会覆盖用户的所有附加组）。
4. **`/etc/shadow` 权限不能松**（否则可离线爆破）。
5. **服务账号用 `nologin` shell**：`useradd -r -s /usr/sbin/nologin svcuser`。
6. **定期审计**：`lastlog`（哪些账号从未登录）、`awk -F: '$3>=1000' /etc/passwd`（有哪些普通用户）。
7. **`sudo` 记录到日志**（`/var/log/auth.log` 或 `journalctl -u sudo`）。""",
    ),
    (
        "Linux",
        "包管理,rpm,deb",
        2,
        r"""Linux 的包管理体系是怎样的？`rpm` 和 `deb` 有什么区别？""",
        r"""**两大体系**：

| | RPM 系 | DEB 系 |
|---|---|---|
| 发行版 | RHEL/CentOS/Fedora/openEuler/Anolis/SUSE | Debian/Ubuntu/Kali |
| 底层工具 | `rpm` | `dpkg` |
| 高层工具 | `yum`（旧）/ `dnf`（新）/ `zypper` | `apt`（底层 `apt-get`） |
| 包格式 | `.rpm` | `.deb` |
| 元数据 | `repodata/` | `Packages.gz` |
| 配置目录 | `/etc/yum.repos.d/` | `/etc/apt/sources.list`、`/etc/apt/sources.list.d/` |
| 缓存 | `/var/cache/dnf/` | `/var/cache/apt/` |

**常用命令对照**：

| 操作 | RPM 系（dnf） | DEB 系（apt） |
|---|---|---|
| 更新索引 | `dnf makecache` | `apt update` |
| 安装 | `dnf install pkg` | `apt install pkg` |
| 卸载 | `dnf remove pkg` | `apt remove pkg`（保留配置）/ `purge`（连配置删） |
| 升级全部 | `dnf upgrade` | `apt upgrade` / `full-upgrade` |
| 搜索 | `dnf search kw` | `apt search kw` |
| 查信息 | `dnf info pkg` | `apt show pkg` |
| 列出已装 | `dnf list installed` | `dpkg -l` |
| 某文件属于哪个包 | `dnf provides /bin/ls` | `apt-file search /bin/ls` / `dpkg -S` |
| 列出包内文件 | `rpm -ql pkg` | `dpkg -L pkg` |
| 装本地包 | `dnf install ./x.rpm` / `rpm -ivh x.rpm` | `apt install ./x.deb` / `dpkg -i x.deb` |
| 修复依赖 | `dnf install --skip-broken` | `apt -f install` ⭐ |
| 清理 | `dnf clean all` | `apt clean` / `autoclean` |

**底层工具（少用，除非必须）**：
```bash
rpm -ivh pkg.rpm               # 安装（不自动解决依赖！）
rpm -Uvh pkg.rpm               # 升级
rpm -e pkg                     # 卸载
rpm -qa                        # 列出所有
rpm -qf /usr/bin/ls            # 文件属于哪个包
rpm -ql pkg                    # 包里的文件
rpm -q --changelog pkg
rpm -V pkg                     # 校验文件是否被改动 ⭐

dpkg -i pkg.deb                # 安装（不解决依赖）
dpkg -r pkg / -P pkg           # 移除 / 彻底清除
dpkg -l | grep foo
dpkg -S /usr/bin/ls            # 文件属于哪个包
dpkg -L pkg
dpkg-reconfigure pkg           # 重新配置（重新弹出交互界面）
```
**`dpkg -i` 报依赖错误时用 `apt -f install` 修复** —— 这是最常见的"装本地包失败"的解法。

**仓库配置**：
```bash
# DEB
cat /etc/apt/sources.list
ls /etc/apt/sources.list.d/
# 加第三方源（现代方式，推荐）
curl -fsSL https://example.com/key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/example.gpg
echo "deb [signed-by=/usr/share/keyrings/example.gpg] https://... stable main" \
  | sudo tee /etc/apt/sources.list.d/example.list

# RPM（dnf）
ls /etc/yum.repos.d/
cat > /etc/yum.repos.d/example.repo <<'EOF'
[example]
name=Example
baseurl=https://example.com/repo
enabled=1
gpgcheck=1
gpgkey=https://example.com/RPM-GPG-KEY
EOF
```

**依赖地狱与解决**：
- **RPM 系的 `--nodeps`**：强装（危险，运行时可能崩）。
- **`--skip-broken`**：跳过有依赖问题的包。
- **`dnf repoquery --whatrequires pkg`**：谁依赖它。
- **DEB 系的 `aptitude`** 有更好的依赖求解。
- **混用源码编译与包管理**会导致"文件冲突"和"升级被覆盖" —— **尽量避免**。

**`apt` 的实用细节**：
```bash
apt list --upgradable              # 哪些可升级
apt-mark hold pkg                  # 锁定版本（不升级）⭐
apt-mark unhold pkg
apt list --installed | wc -l
apt-get autoremove                 # 清理不再需要的依赖
dpkg --get-selections > pkgs.txt   # 导出清单
dpkg --set-selections < pkgs.txt   # 恢复清单
```
**`dnf` 的实用细节**：
```bash
dnf history                        # 操作历史 ⭐
dnf history undo <id>              # 回滚某次操作 ⭐
dnf versionlock add pkg            # 锁定版本（需插件）
dnf module list / dnf module enable nginx:1.24   # 模块流（AppStream）
dnf autoremove
dnf groupinstall "Development Tools"
```

**离线/内网环境**：
```bash
# 下载包及其依赖（不安装）
dnf download --resolve --alldeps pkg          # 或 dnf install --downloadonly
apt-get install --download-only pkg
# 用本地目录做仓库
createrepo_c /path/to/rpms
dpkg-scanpackages /path/to/debs /dev/null | gzip > Packages.gz
```

**容器里装包的最佳实践**：
1. **`apt update && apt install && rm -rf /var/lib/apt/lists/*` 写在同一层**（否则缓存留在镜像层）。
2. **用 `--no-install-recommends`** 减少体积。
3. **固定版本**（`pkg=1.2.3-4`）保证可复现。
4. **多阶段构建**：编译依赖不留在最终镜像。

**常见问题**：
| 现象 | 原因/解法 |
|---|---|
| `Could not get lock /var/lib/dpkg/lock` | 另一个 apt 在跑，或上次异常退出 → `dpkg --configure -a` |
| 依赖冲突 | `apt -f install` / `dnf check`；检查第三方源 |
| GPG 签名错误 | 缺 key（导入 `gpgkey`）或系统时间不对 |
| 升级后服务起不来 | `dnf history undo` / 检查配置变更（`.rpmnew`/`.dpkg-dist` 文件）⭐ |
| 磁盘被缓存占满 | `dnf clean all` / `apt clean` |""",
    ),
    (
        "Linux",
        "iptables,防火墙",
        3,
        r"""iptables 的四表五链是什么？怎么写一条 NAT 规则？""",
        r"""**netfilter** 是内核的包过滤框架，**iptables** 是它的用户态工具（新版是 **nftables**）。

**四表（按优先级链）**：

| 表 | 作用 | 内置链 |
|---|---|---|
| **raw** | 连接跟踪豁免（`-j NOTRACK`），最先处理 | PREROUTING, OUTPUT |
| **mangle** | 修改包（TTL、TOS、MARK） | 全部 5 个 |
| **nat** | 地址转换 | PREROUTING（DNAT）、OUTPUT、POSTROUTING（SNAT） |
| **filter** | **过滤（默认表）** | INPUT, FORWARD, OUTPUT |

**五链（处理时机）**：

```
入站包：  PREROUTING → [路由判断] → INPUT → 本地进程
转发包：  PREROUTING → [路由判断] → FORWARD → POSTROUTING → 出站
出站包：  本地进程 → OUTPUT → [路由判断] → POSTROUTING → 出站
```

| 链 | 时机 |
|---|---|
| **PREROUTING** | 包刚到达网卡，路由判断**之前**（做 DNAT） |
| **INPUT** | 目标是本机的包 |
| **FORWARD** | 需要转发（不经过本机进程）的包 |
| **OUTPUT** | 本机进程发出的包 |
| **POSTROUTING** | 即将离开网卡的包（做 SNAT） |

**常见命令**：

```bash
# 查看（-n 不做 DNS 解析，-v 显示计数，--line-numbers 显示编号）
iptables -t filter -L -n -v --line-numbers
iptables -t nat -L -n -v

# 默认策略
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# 放行已建立的连接 + 本机回环（必备前两条）
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -i lo -j ACCEPT

# 放行端口
iptables -A INPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -p tcp -m multiport --dports 80,443 -j ACCEPT
iptables -A INPUT -p icmp --icmp-type echo-request -j ACCEPT
iptables -A INPUT -s 10.0.0.0/8 -p tcp --dport 3306 -j ACCEPT   # 只允许内网

# 插入到最前
iptables -I INPUT 1 -s 1.2.3.4 -j DROP

# 删除
iptables -D INPUT 3                      # 按编号
iptables -D INPUT -s 1.2.3.4 -j DROP     # 按规则内容

# 保存与恢复（重启不丢）
iptables-save > /etc/iptables/rules.v4
iptables-restore < /etc/iptables/rules.v4
# 或装 iptables-persistent / 用 firewalld
```

**NAT 规则（关键）**：

```bash
# 1) 开启 IP 转发（做网关的前提）
sysctl -w net.ipv4.ip_forward=1
echo "net.ipv4.ip_forward = 1" > /etc/sysctl.d/99-forward.conf

# 2) SNAT：让内网通过本机上网（出站改写源地址）
iptables -t nat -A POSTROUTING -s 192.168.1.0/24 -o eth0 -j MASQUERADE
# 或指定固定公网 IP（更高效）
iptables -t nat -A POSTROUTING -s 192.168.1.0/24 -o eth0 -j SNAT --to-source 1.2.3.4

# 3) DNAT：端口转发（把公网 8080 转到内网 192.168.1.10:80）
iptables -t nat -A PREROUTING -p tcp --dport 8080 -j DNAT --to-destination 192.168.1.10:80
# 别忘了放行 FORWARD
iptables -A FORWARD -p tcp -d 192.168.1.10 --dport 80 -j ACCEPT
```

**DNAT 后为什么还要 FORWARD 规则**：DNAT 只改目标地址（在 PREROUTING），包仍要经过 FORWARD 链的过滤。

**连接跟踪（conntrack）**：
- `-m conntrack --ctstate NEW/ESTABLISHED/RELATED/INVALID`
- **`ESTABLISHED,RELATED -j ACCEPT`** 是防火墙必备（让回包通过），否则所有出站请求的响应都会被 INPUT 拦掉。
- 连接跟踪表可能满：`/proc/sys/net/netfilter/nf_conntrack_max`、`conntrack -L | wc -l`。
  - 症状：`nf_conntrack: table full, dropping packet`。

**匹配扩展（`-m`）**：
| 模块 | 用途 |
|---|---|
| `conntrack` | 连接状态 |
| `multiport` | 多端口（`--dports 80,443`） |
| `iprange` | IP 段 |
| `recent` | 防暴力破解（记录近期连接） |
| `limit` | 限速（`--limit 10/s`） |
| `state` | 老版状态匹配（已被 conntrack 取代） |
| `string` | 字符串匹配（性能差） |
| `owner` | 按进程（仅 OUTPUT） |
| `comment` | 给规则加注释 |

**防暴力破解示例**：
```bash
iptables -A INPUT -p tcp --dport 22 -m conntrack --ctstate NEW \
  -m recent --set --name SSH
iptables -A INPUT -p tcp --dport 22 -m conntrack --ctstate NEW \
  -m recent --update --seconds 60 --hitcount 4 --name SSH -j DROP
```

**`firewalld`（RHEL 系默认，更友好）**：
```bash
systemctl enable --now firewalld
firewall-cmd --state
firewall-cmd --get-active-zones
firewall-cmd --zone=public --add-port=8080/tcp --permanent
firewall-cmd --zone=public --add-service=http --permanent
firewall-cmd --reload
firewall-cmd --list-all
```
**`firewalld` 底层其实还是 nftables/iptables**，规则由它生成。

**`nftables`（现代替代）**：
```bash
nft list ruleset
nft add table inet filter
nft add chain inet filter input '{ type filter hook input priority 0; policy drop; }'
nft add rule inet filter input ct state established,related accept
nft add rule inet filter input tcp dport { 22, 80, 443 } accept
```
**优势**：单一工具替代 iptables/ip6tables/arptables/ebtables、语法更清晰、性能更好、原子更新。

**实践建议**：
1. **先加"放行 SSH"再改默认策略为 DROP**（否则会把自己关在门外）。用 `iptables -I INPUT 1 ...` 保证在最前。
2. **生产用 `iptables-save`/`firewalld --permanent` 持久化**，别只在 shell 里敲。
3. **云环境**：**云厂商的安全组在 iptables 之前生效**（流量根本没到主机）—— 排查"端口不通"时先看安全组。
4. **`DOCKER-USER` 链**：Docker 会插入自己的规则；**自定义规则要放 `DOCKER-USER`**（`FORWARD` 里的 Docker 链会覆盖）。
5. **先 `-L` 看现状再改**（避免和 Docker/firewalld 的规则打架）。
6. **`conntrack` 表满**是"包被莫名丢弃"的常见原因（调 `nf_conntrack_max`）。""",
    ),
    (
        "Linux",
        "docker 网络,容器网络",
        3,
        r"""Docker 的网络模式有哪几种？容器之间怎么互通？""",
        r"""**五种网络模式**：

| 模式 | 说明 | 隔离性 |
|---|---|---|
| **bridge**（默认） | 每个容器接一个虚拟网桥（`docker0`），分配私有 IP，通过 NAT 出网 | 中 |
| **host** | 直接用宿主机的网络栈（无独立 netns） | 无 |
| **none** | 只有 `lo`，无网络 | 最高 |
| **container:<name>** | 共享另一个容器的网络栈（k8s Pod 的原理） | — |
| **overlay** | 跨主机的虚拟网络（Swarm/k8s） | — |
| **macvlan** | 容器直接获得 MAC/IP，像物理机一样接入网络 | — |

**bridge 模式的实现**：

```
容器 eth0 (172.17.0.2)
    ↕ veth pair（一对虚拟网卡，一端在容器，一端在宿主）
docker0 网桥 (172.17.0.1)
    ↕ iptables NAT (MASQUERADE)
宿主机 eth0 → 外网
```

1. **`veth pair`**：一对虚拟网卡，像"网线"连接容器与宿主网桥。
2. **`docker0`**：Linux bridge，容器默认网关是它（172.17.0.1）。
3. **SNAT**：容器出网时 iptables 做 `MASQUERADE`（源地址改成宿主 IP）。
4. **端口映射（`-p 8080:80`）**：在 `DOCKER` 链里加 **DNAT** 规则，把宿主 8080 转到容器 IP:80。
5. **容器之间**：同一 bridge 上可通过 IP 直接互通（二层转发）；**Docker 内置 DNS（127.0.0.11）** 让容器可以用**容器名**互相发现（**仅在用户自定义 bridge 网络里，默认 bridge 不支持**）。

```bash
# 创建自定义网络（推荐）
docker network create mynet
docker run --network mynet --name app nginx
docker run --network mynet --name db mysql
# app 里可以直接 ping db / 连 db:3306

docker network ls
docker network inspect mynet
ip link show type bridge
brctl show / bridge link           # 看网桥与端口
```

**查看容器的网络命名空间**：
```bash
docker inspect -f '{{.State.Pid}}' <container>       # 拿到宿主机上的 PID
nsenter -t <pid> -n ip addr                          # 进入容器的 netns ⭐
nsenter -t <pid> -n ss -lntp
```

**为什么"容器内端口通、宿主不通"**：
- `-p` 只在**宿主**加 DNAT，容器内看不到；
- 或云安全组没开；
- 或应用只绑定 `127.0.0.1`（容器内 `127.0.0.1` 是容器自己！不能从宿主访问）。

**为什么"容器内连不上别的容器"**：
- 用了**默认 bridge**（不支持 DNS 名字解析）→ 用自定义网络。
- **iptables FORWARD 策略是 DROP**（Docker 的规则在 FORWARD 链，但自定义规则可能覆盖）→ 规则要放 `DOCKER-USER` 链。
- `icc=false` 或网络被隔离。

**k8s 的网络模型（对比理解）**：
- **每个 Pod 一组网络命名空间**，Pod 内容器共享（`container:` 模式）。
- **要求"扁平网络"**：Pod IP 在整个集群内可直接路由（无 NAT）。
- 实现方案：**CNI** 插件（Calico 用 BGP/路由，Flannel 用 VXLAN overlay，Cilium 用 eBPF）。
- **Service 是虚拟 IP（VIP）**：由 kube-proxy（iptables/IPVS）或 eBPF 实现负载均衡到 Pod。
- **DNS**：CoreDNS 提供 `service.namespace.svc.cluster.local` 解析。

**overlay 网络（跨主机）**：
- **VXLAN** 把二层帧封装在 UDP 里（默认端口 4789），跨主机形成虚拟二层网络。
- 缺点：**MTU 开销**（50 字节）+ 封装解封装的 CPU 开销。
- 云环境常用 VPC 路由替代（性能更好）。

**macvlan**：容器直接拿一个"真实"IP（和宿主机同网段），**但宿主机与容器通常不能直接通信**（需要额外配置）。

**排查容器网络问题**：
```bash
# 1. 容器是否有 IP
docker exec <c> ip addr
# 2. 容器能否出网
docker exec <c> ping 8.8.8.8
docker exec <c> ping google.com          # 测 DNS
# 3. 宿主上的 iptables NAT 规则
iptables -t nat -L -n -v | head -40
iptables -t filter -L DOCKER-USER -n -v
# 4. 是否有端口映射
docker port <c>
ss -lntp | grep <port>
# 5. DNS
docker exec <c> cat /etc/resolv.conf
docker exec <c> nslookup <other>
# 6. 抓包（在容器的 netns 里抓，最直接）
nsenter -t <pid> -n tcpdump -i eth0 -nn
```

**实践建议**：
1. **总是用自定义 bridge 网络**（有 DNS 服务发现，可隔离）。
2. **不要用 `--link`**（已过时）。
3. **`--network host` 有性能优势但失去隔离**（只用端口时会冲突）—— 高性能场景（如高频交易）会用。
4. **注意 MTU**：overlay/VPN 环境要把 Docker 的 MTU 调小（`--mtu=1400`），否则大包会丢（表现为"小请求正常、大请求卡住"）。
5. **`DOCKER-USER` 链**放自定义防火墙规则。
6. **容器内不要用 `127.0.0.1` 暴露服务**（绑 `0.0.0.0`）。
7. **k8s 里**：应用绑 `0.0.0.0`，用 Service/Ingress 暴露，不要依赖 Pod IP（会变）。""",
    ),
    (
        "Linux",
        "eBPF,bpftrace",
        3,
        r"""eBPF 是什么？`bpftrace` 能解决什么问题？""",
        r"""**eBPF（extended Berkeley Packet Filter）**：内核里可安全运行的**沙箱字节码**，让用户在不改内核、不加载模块的情况下**在内核事件上执行自定义逻辑**。

**为什么重要**：
1. **可编程内核**（无需编译内核/加载模块）。
2. **安全**：验证器（verifier）静态检查字节码（禁越界、禁无限循环），不会导致内核崩溃。
3. **低开销**：JIT 编译成本地指令；**无需 ptrace**（不像 strace 每条 syscall 停两次）。
4. **可观测 + 可编程网络**：tracing（观测）与 networking（XDP/tc）两大方向。

**挂载点（hook 点）**：

| 类型 | 挂载点 | 用途 |
|---|---|---|
| **kprobe/kretprobe** | 内核函数入口/返回 | 观测内核函数 |
| **uprobe/uretprobe** | 用户态函数 | 观测应用函数 |
| **tracepoint** | 内核静态埋点（稳定 ABI） | 推荐（比 kprobe 稳定） |
| **USDT** | 用户态静态探针 | 应用自带埋点 |
| **perf_event** | 性能计数器 | 采样分析 |
| **XDP** | 网卡驱动早期 | **超高性能**包处理/丢弃 |
| **tc（traffic control）** | 网络栈 | 流量控制、负载均衡 |
| **socket filter** | socket 层 | 包过滤 |
| **LSM** | 安全钩子 | 安全策略 |
| **cgroup** | cgroup 事件 | 按容器统计/限制 |

**bpftrace**：eBPF 的高层语言（类似 awk/DTrace 语法），**一行命令就能观测**。

```bash
# 跟踪新进程（谁在频繁 fork/exec）
bpftrace -e 'tracepoint:syscalls:sys_enter_execve { printf("%s -> %s\n", comm, str(args->filename)); }'

# 统计各进程的 read 字节数
bpftrace -e 'tracepoint:syscalls:sys_exit_read { @[comm] = sum(args->ret); }'

# 每个进程的 on-CPU 时间（火焰图数据源）
bpftrace -e 'profile:hz:99 { @[comm] = count(); }'

# 跟踪 open 慢的调用
bpftrace -e 'tracepoint:syscalls:sys_enter_openat { @start[tid] = nsecs; }
             tracepoint:syscalls:sys_exit_openat /@start[tid]/ {
               @ns[comm] = hist(nsecs - @start[tid]); delete(@start[tid]); }'

# 跟踪某个函数的调用栈
bpftrace -e 'kprobe:vfs_read { @[kstack] = count(); }'

# 按 PID 跟踪 IO 延迟
bpftrace -e 'kprobe:blk_account_io_start { @start[arg0] = nsecs; }
             kprobe:blk_account_io_done /@start[arg0]/ {
               @us = hist((nsecs - @start[arg0]) / 1000); delete(@start[arg0]); }'
```

**bpftrace 语法要点**：
| 元素 | 说明 |
|---|---|
| `tracepoint:cat:name` / `kprobe:func` | 探针类型与位置 |
| `/filter/` | 过滤条件 |
| `{ actions }` | 触发时执行 |
| `@name` | 聚合变量（map） |
| `count()` `sum()` `hist()` `avg()` `min()` `max()` | 聚合函数 |
| `comm` `pid` `tid` `nsecs` `arg0..argN` `args->field` `retval` | 内置变量 |
| `kstack` / `ustack` | 内核/用户调用栈 |
| `str(ptr)` `printf()` `delete()` `exit()` `interval:s:1` | 常用函数 |

**BCC 工具集**（Python + eBPF 封装，开箱即用）：
```bash
execsnoop            # 跟踪新进程执行 ⭐
opensnoop            # 跟踪 open 调用（找出打开了什么文件）⭐
biolatency           # 块 IO 延迟分布 ⭐
biotop               # 按进程的 IO 排行 ⭐
tcpconnect/tcpaccept # 连接追踪
tcpretrans           # TCP 重传追踪 ⭐
runqlat              # 调度延迟分布（CPU 饱和诊断）⭐
runqlen              # 运行队列长度
offcputime           # 线程离开 CPU 的时间与栈（阻塞分析）⭐
profile              # CPU 采样（火焰图数据源）
funccount            # 函数调用计数
argdist              # 参数分布
```
**这套工具把"以前要改内核/上 DTrace"的能力变成了开箱可用**。

**性能对比**：

| 手段 | 开销 | 能否自定义 | 需要重启 |
|---|---|---|---|
| `strace` | **极高**（ptrace 两停） | ❌ | ❌ |
| `perf` | 低（采样） | 有限 | ❌ |
| **eBPF** | **极低**（JIT，可采样可精确） | ✅✅ | ❌ |
| 内核模块 | 零 | ✅ | ✅（危险） |

**限制**：
1. **内核版本**：4.x 基础，5.x 才完善（很多特性要 5.4/5.8/5.15+）。CentOS 7（3.10）**不支持**（需 BCC 加 backport 或升级）。
2. **需要 root/CAP_BPF**（部分探针也要求 `CAP_PERFMON`）。
3. **验证器限制**：循环次数有上限、栈深度有限（512 字节）、指令数有限（早期 4096，现 100 万）。
4. **不能随意调用内核函数**（只能调白名单 helper）。
5. **容器里默认受限**（需要 `--privileged` 或 `--cap-add=CAP_BPF`）。
6. **安全**：eBPF 曾是提权攻击面（多个 CVE）—— **生产上要限制谁能加载 eBPF**（`kernel.unprivileged_bpf_disabled=1`）。

**实践应用**：
1. **可观测性**：Cilium（用 eBPF 做 k8s 网络）、Pixie、Parca、Falco（安全）。
2. **性能分析**：火焰图（`perf` 或 `bpftrace` 出栈数据 + FlameGraph.pl）。
3. **网络加速**：XDP 做 DDoS 防护、负载均衡（Facebook 的 Katran）。
4. **安全**：实时检测异常系统调用。
5. **按 cgroup 统计**：容器粒度的资源归因。

**实践建议**：
1. **优先用现成的 BCC/bpftrace 工具**，不要一上来就写 C。
2. **用 `tracepoint` 而非 `kprobe`**（ABI 稳定，跨版本不易失效）。
3. **先 `bpftrace -l 'tracepoint:*'` 找到可用探针**。
4. **`-d` 干跑（dry run）** 检查语法与探针是否可用。
5. **注意输出量**（`printf` 在热路径会拖慢系统，用聚合 `@`）。
6. **生产使用要注意权限与性能影响**（尤其 kprobe 在超高频函数上）。""",
    ),
    (
        "Linux",
        "perf,火焰图",
        3,
        r"""`perf` 怎么用？火焰图怎么生成和解读？""",
        r"""**`perf`** 是 Linux 的**性能分析工具**，基于 `perf_events` 子系统（内核的采样与计数器框架）。

**核心子命令**：

| 命令 | 用途 |
|---|---|
| `perf stat` | 统计（IPC、cache miss、分支预测） |
| `perf record` / `perf report` | **采样 + 分析**（最常用）⭐ |
| `perf top` | 实时热点（类似 top，但是函数级） |
| `perf trace` | 类似 strace 但**低开销** |
| `perf sched` | 调度延迟分析 |
| `perf lock` | 锁竞争分析 |
| `perf mem` | 内存访问分析 |
| `perf c2c` | **cache line 竞争**（伪共享）分析 |
| `perf annotate` | 汇编级热点 |
| `perf diff` | 对比两次 profile |

**常用命令**：

```bash
# 1. 先看基本面
perf stat -a sleep 5
# 关注：task-clock, context-switches, page-faults, cycles, instructions,
#      IPC, cache-misses, branch-misses

perf stat -e cache-misses,cache-references,dTLB-load-misses ./prog

# 2. 采样（关键）
perf record -g -F 99 -p <pid> -- sleep 30      # -g 记录调用栈，-F 采样频率 ⭐
perf record -g -a -- sleep 30                  # 全系统
perf record -g -e cpu-clock ./prog             # 指定事件
perf record -g -e page-faults ./prog

# 3. 分析
perf report                    # 交互式（可展开调用栈）⭐
perf report --stdio -g graph,0.5,caller
perf report --no-children      # 只看自身开销
perf top                       # 实时
perf top -p <pid>

# 4. 调度
perf sched record -- sleep 10
perf sched latency             # 每条任务的最大/平均延迟 ⭐

# 5. 锁
perf lock record ./prog
perf lock report

# 6. cache 竞争（伪共享）
perf c2c record -a -- sleep 10
perf c2c report --stdio
```

**`perf stat` 的关键指标解读**：

| 指标 | 含义 |
|---|---|
| `task-clock` | CPU 使用时间（ms） |
| `context-switches` | 上下文切换 |
| `page-faults` | 缺页（`minor`/`major`） |
| `cycles` / `instructions` | 周期数 / 指令数 |
| **`IPC`** | `instructions / cycles`。**<1 通常是内存/io 瓶颈；>2 说明指令级并行好** |
| `cache-misses` / `cache-references` | 缓存缺失率 |
| `branch-misses` | 分支预测失败 |
| `stalled-cycles-frontend/backend` | 前端（取指）/后端（执行）停顿 |
| `LLC-load-misses` | 最后一级缓存缺失（通常是内存访问瓶颈） |

**火焰图（Flame Graph）**：

**原理**：把采样的**调用栈**聚合成一张图：
- **X 轴**：不是时间，而是**采样占比**（越宽 = 越常出现）。**顺序无意义**（已按字母排序聚合）。
- **Y 轴**：调用栈深度（下面是调用者，上面是被调用者）。
- **颜色**：通常随机（仅用于区分），或按语言/状态着色（on-CPU 红黄、off-CPU 蓝）。

**生成（最常用路径）**：
```bash
# 1. 采样
perf record -F 99 -g -p <pid> -- sleep 30
# 2. 展开栈（把二进制地址转成符号）
perf script > out.perf
# 3. 折叠
git clone https://github.com/brendangregg/FlameGraph
FlameGraph/stackcollapse-perf.pl out.perf > out.folded
# 4. 出图
FlameGraph/flamegraph.pl out.folded > flame.svg
```
**更简单**：`perf script | FlameGraph/stackcollapse-perf.pl | FlameGraph/flamegraph.pl > flame.svg`（或 `FlameGraph/flamegraph.pl --title "..." --colors java`）。

**其它火焰图类型**（Brendan Gregg 的分类）：

| 类型 | 数据源 | 回答的问题 |
|---|---|---|
| **on-CPU** | `perf record -g` | CPU 花在哪 |
| **off-CPU** | `offcputime`（BCC）/ `perf sched` | **为什么阻塞**（等锁/IO）⭐ |
| **内存** | `perf record -e page-faults` | 缺页来源 |
| **Java** | `perf -e cpu-clock --call-graph dwarf` + `perf-map-agent` | JVM 内热点（需符号） |
| 差分火焰图 | 两次 profile 相减 | 优化前后对比 |

**如何解读**：
1. **找最宽的"平顶"**（plateau）—— 那是**自身开销集中在叶子函数**。
2. **自底向上看调用链**：看到某个函数的所有调用者，判断"是这个函数慢"还是"被上层拖累"。
3. **注意 `[unknown]`** —— 缺符号（JIT/优化过/无 debuginfo）会让图失去意义。
4. **看 `[kernel.kallsyms]`** —— 内核态占比（syscall/IO/锁）。
5. **对比基线**：单张图只能看"哪宽"，差分图才能看"变化"。

**符号问题（最常见的坑）**：
```bash
# 缺符号的表现：[unknown] / 只有十六进制地址
# 解决：
# - 应用：编译加 -g -fno-omit-frame-pointer
perf record -g --call-graph dwarf ./prog        # dwarf 解析（不需 frame pointer，但更慢）
# - JVM：-XX:+PreserveFramePointer + perf-map-agent
# - 内核：安装 debuginfo（dnf debuginfo-install kernel）
# - 容器：注意符号文件路径与 /proc/sys/kernel/perf_event_paranoid
```

**`perf_event_paranoid`**：
```bash
cat /proc/sys/kernel/perf_event_paranoid
# 2（默认）：只能分析自己的进程
# 1：可以分析别人的进程（需 CAP_PERFMON）
# -1：全开放（**不安全，生产不要**）
sysctl -w kernel.perf_event_paranoid=1
```

**实践流程**：
1. **先 `perf stat`** 看是不是 CPU 饱和 / cache miss / IPC 低。
2. **`perf top`** 快速看热点函数（不用落盘）。
3. **`perf record -g` + 火焰图** 定位具体调用链。
4. **如果 CPU 不高但很慢** → 用 **off-CPU 火焰图**（`offcputime`）找阻塞点。
5. **如果怀疑伪共享** → `perf c2c`。
6. **如果怀疑调度** → `perf sched latency`。
7. **改动后再采样对比**（差分火焰图）。

**容器里用 perf**：需要 `--cap-add=SYS_ADMIN` 或 `--privileged`，且 `/sys/kernel/debug` 可挂载；k8s 里用 `bpftrace` 的 sidecar 或 node-level DaemonSet 采集。

**替代工具**：
| 工具 | 优势 |
|---|---|
| `bpftrace` | 可编程、低开销 |
| `async-profiler`（Java） | JVM 专用，含分配/锁火焰图 |
| `py-spy`（Python） | 无侵入 Python profiling |
| `pprof`（Go） | Go 内置 |
| `Intel VTune` | 硬件级分析（PMU、微架构） |
| `Parca/Pyroscope` | 持续 profiling 平台 |""",
    ),
    (
        "Linux",
        "块IO,IO调度器",
        3,
        r"""块层的 IO 是怎么走的？IO 调度器有什么用？怎么调优磁盘 IO？""",
        r"""**块 IO 的完整路径**（以 buffered write 为例）：

```
1. 应用 write()
2. VFS → 文件系统（ext4/xfs）定位逻辑块
3. page cache（写：标记脏页后返回；读：命中直接返回）
4. 回写线程 / 直接 IO 进入块层
5. 块层：合并/排序请求 → **IO 调度器** → 派发队列
6. 设备驱动 → HBA/SSD 控制器 → 磁盘
7. 完成：中断 → 软中断 → 唤醒等待者
```

**块层的两个概念**：
| | 含义 |
|---|---|
| **bio** | 块 IO 请求（描述"读写哪段数据"） |
| **request** | 经过合并/排序后交给设备的请求 |
| **合并（merge）** | 相邻的 bio 合成一个 request（**减少 IO 次数，最重要的优化**） |
| **plug/unplug** | 短暂攒住请求再一起下发（提高合并率） |

**IO 调度器（elevator）**：

| 调度器 | 特点 | 适用 |
|---|---|---|
| **none / noop** | FIFO，只做简单合并 | **SSD/NVMe**（硬件本身快且并行）、虚拟机 |
| **mq-deadline** | 每个请求有 deadline（读优先），防止饿死 | 通用、数据库 |
| **bfq**（Budget Fair Queueing） | 按进程分配带宽，**交互性好**，开销大 | 桌面、多任务 |
| **kyber** | 基于延迟目标（读/同步写/异步写） | 低延迟场景 |
| **cfq**（已移除） | 老的按进程公平队列 | 4.20 后删除（被 bfq 取代） |

**查看与设置**：
```bash
cat /sys/block/sda/queue/scheduler
# [none] mq-deadline kyber bfq      ← 方括号是当前
echo mq-deadline > /sys/block/sda/queue/scheduler
# 持久化
# udev 规则：/etc/udev/rules.d/60-iosched.rules
ACTION=="add|change", KERNEL=="sd[a-z]", ATTR{queue/scheduler}="mq-deadline"
ACTION=="add|change", KERNEL=="nvme[0-9]n[0-9]", ATTR{queue/scheduler}="none"
```
**现代实践：NVMe/云盘用 `none`（或 `mq-deadline`），HDD 用 `mq-deadline`/`bfq`。**

**关键队列参数**：
```bash
cat /sys/block/sda/queue/
# nr_requests          队列深度
# read_ahead_kb        预读大小（顺序读优化）⭐
# max_sectors_kb       单次请求最大扇区
# rotational           1=机械盘 0=SSD
# rq_affinity          完成中断绑到发起 CPU
# nomerges             合并策略
# scheduler
```
```bash
# 加大预读（顺序读场景）
echo 4096 > /sys/block/sda/queue/read_ahead_kb
# 云盘/SSD 调大队列深度
echo 1024 > /sys/block/sda/queue/nr_requests
```

**监控**：
```bash
iostat -xz 1
# 关键列：
#  r/s w/s      每秒读写次数（IOPS）
#  rkB/s wkB/s  每秒读写字节（吞吐）
#  r_await w_await  平均读写延迟（ms）⭐ 最重要的指标
#  aqu-sz       平均队列长度
#  %util       设备利用率（HDD 上接近 100% 表示饱和；SSD 上不准确）
```
```bash
pidstat -d 1                # 按进程的 IO
iotop -o                    # 按进程实时 IO
cat /proc/diskstats          # 原始计数
blktrace / btt               # 块层追踪（IO 分解到各阶段）
biosnoop（BCC）              # 每个 IO 的延迟与进程 ⭐
biolatency（BCC）            # IO 延迟直方图 ⭐
```

**诊断"IO 慢"**：

| 现象 | 可能原因 |
|---|---|
| `%util` 100% + `await` 高 | 设备饱和 |
| `await` 高但 `%util` 低 | 队列排队/驱动问题/网络存储（云盘） |
| IOPS 低但吞吐高 | 大块顺序 IO（正常） |
| IOPS 高但吞吐低 | 小块随机 IO（HDD 的噩梦，SSD 正常） |
| `w_await` 远高于 `r_await` | 写入放大/page cache 回写压力 |
| 延迟有长尾（p99 高） | 队列调度/GC/写放大（SSD） |

**调优手段**：
1. **减少 IO 次数**：合并小写（应用层缓冲）、批量提交、`O_DIRECT` 避免双缓冲。
2. **顺序化**：`read_ahead_kb` 调大、`fadvise(SEQUENTIAL)`。
3. **异步化**：`io_uring`、`libaio`、多线程。
4. **分离读写**（不同磁盘/设备）。
5. **加大队列深度**（`nr_requests`、`io.max` cgroup 限制）。
6. **`O_DIRECT`**：绕过 page cache（数据库自管理缓存，避免双份内存占用与双向拷贝）。
7. **`fdatasync` 代替 `fsync`**（只同步数据，不同步元数据，快一点）。
8. **RAID/条带化** 提升并发（RAID 10）。
9. **SSD 的 TRIM**（`fstrim` / `discard`）保持性能。
10. **云盘选型**：ESSD PL1/PL2/PL3 的 IOPS 与吞吐差异巨大；**小规格云盘的 IOPS 上限很低**是常见瓶颈。

**`iostat -x` 的关键判断**：
```bash
iostat -xz 1 5
# Device   r/s   w/s  rkB/s  wkB/s  rrqm/s wrqm/s  %rrqm %wrqm r_await w_await aqu-sz %util
# sda     1200  800  48000  32000    ...      ...      ...   ...    1.20    8.50   3.2  99.5
#   → 设备饱和（%util 99.5），读延迟 1.2ms 尚可，写延迟 8.5ms 偏高
```
**看 `await` 而不是只看 `%util`**：NVMe 上 `%util` 100% 但 `await` 很低是正常的（并行度高）。

**`vmstat` 的 IO 相关**：
```bash
vmstat 1
# bi/bo       块设备读入/写出块数（blocks/s）
# wa          IO 等待占 CPU 时间百分比
```
**`wa` 高 + `bo` 高 → 写回压力**（检查 `dirty_ratio`）。""",
    ),
    (
        "Linux",
        "时间,时区,NTP",
        1,
        r"""Linux 的时间和时区是怎么管理的？怎么同步时间？""",
        r"""**两类时钟**：

| 时钟 | 说明 |
|---|---|
| **RTC（硬件时钟）** | 主板上的电池供电时钟，关机后仍走 |
| **系统时钟（内核）** | 开机时从 RTC 读取，之后由内核维护；由 NTP 校准 |

**RTC 存的是 UTC 还是本地时间？** 两种约定：
- **UTC（推荐）**：`timedatectl set-local-rtc 0`（`/etc/adjtime` 里 `UTC`）。操作系统按自身时区显示。
- 本地时间：多系统（Linux + Windows 双启动）常用（Windows 默认把 RTC 当本地时间）。

**时区**：
```bash
timedatectl                          # 查看时间/时区/NTP 状态 ⭐
timedatectl list-timezones | grep Asia
timedatectl set-timezone Asia/Shanghai
ls -l /etc/localtime                 # 指向 /usr/share/zoneinfo/Asia/Shanghai
ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime   # 手动方式
```
**容器里的时区**：容器默认继承宿主机内核的 UTC，需要在镜像里装 `tzdata` 并设 `TZ` 环境变量或挂载 `/etc/localtime`：
```bash
docker run -e TZ=Asia/Shanghai ...
docker run -v /etc/localtime:/etc/localtime:ro ...
```

**`date` 常用**：
```bash
date                                 # 当前时间
date -u                              # UTC
date +"%Y-%m-%d %H:%M:%S"
date -d "2026-01-01" +%s             # 转 Unix 时间戳
date -d @1735689600                  # 时间戳转日期
date -d "yesterday" / "+3 days" / "-1 hour"
date -r file.txt                     # 文件的修改时间
TZ=America/New_York date             # 临时改时区
```
**注意**：Unix 时间戳**与时区无关**（是 UTC 秒数）。

**文件时间戳**：
```bash
stat file
# atime（访问）、mtime（内容修改）、ctime（inode 变更，如权限）
touch -d "2020-01-01" file           # 改时间
# 挂载 noatime 可以减少 atime 更新带来的写 IO ⭐
```

**NTP 时间同步**：

```bash
# 方式 1：chrony（现代默认，RHEL8+/Ubuntu 18+）⭐
systemctl status chronyd
chronyc sources -v                   # 时间源与状态 ⭐
chronyc tracking                     # 同步状态与偏差
chronyc makestep                     # 立即跳变（大偏差时）
cat /etc/chrony.conf
# server ntp.aliyun.com iburst
# makestep 1.0 3                     # 前 3 次允许跳变

# 方式 2：systemd-timesyncd（轻量，桌面/简单服务器）
timedatectl set-ntp true
systemctl status systemd-timesyncd
timedatectl timesync-status

# 方式 3：ntpd（传统）
systemctl status ntpd
ntpq -p
ntpdate -u ntp.aliyun.com            # 一次性同步（**必须先停 ntpd**）
```

**为什么用 chrony 而不是 ntpd**：
1. **同步更快**（`iburst` 大幅缩短初始同步时间）。
2. **对间歇性网络/VPN/虚拟机更友好**。
3. **更好的时钟频率校正**（斜差率估计）。
4. **支持硬件时间戳**。

**`makestep` 的坑**：
- NTP **默认不会"跳变"时间**（避免应用时间倒退），而是**缓慢调整**（slew）。
- 如果时间偏差太大（如虚拟机挂起后），缓慢调整要很久 → 需要 `makestep`（chrony）或 `ntpd -gq` 允许大跳变。
- **跳变会让依赖单调时间的程序出错**（如定时器、衡量耗时）→ 应用应该用**单调时钟**（`CLOCK_MONOTONIC`）测耗时。

**时区与程序**：
- **`TZ` 环境变量**覆盖系统时区（`TZ=UTC ./prog`）。
- **`/etc/timezone`**（Debian 系）与 `/etc/localtime`（符号链接）要保持一致。
- **JVM** 常需要显式 `-Duser.timezone=Asia/Shanghai`（否则可能读错）。
- **数据库**：MySQL 的 `time_zone`、PostgreSQL 的 `timezone` 要显式设置（否则跨时区数据会错）。
- **日志时间**：统一用 UTC 存储、展示时转换（否则跨时区排查很痛苦）。

**排查时间问题**：
```bash
timedatectl                          # 总览
date && date -u                      # 本地 vs UTC
chronyc sources -v && chronyc tracking
cat /etc/timezone 2>/dev/null; ls -l /etc/localtime
hwclock --show                       # 硬件时钟
dmesg | grep -i -E "clock|time"
# 虚拟机时间漂移
cat /sys/devices/system/clocksource/clocksource0/current_clocksource
```

**虚拟机的时钟问题**：
1. **挂起/恢复后时间漂移** → 装 `qemu-guest-agent` 或 `open-vm-tools`，或用 `kvm-clock`。
2. **时钟源**：`tsc`（快但可能不稳）、`kvm-clock`（KVM 下推荐）、`hpet`、`acpi_pm`。
3. **NTP 在虚拟机里要更频繁同步**。

**实践建议**：
1. **所有服务器必须开 NTP**（分布式系统的时间偏差会导致日志乱序、token 失效、分布式事务异常）。
2. **统一用 UTC 存储，展示时转换**。
3. **用 `chrony`**（配置 `iburst` + 多个源）。
4. **容器里显式设 `TZ`**。
5. **测耗时用单调时钟**（`CLOCK_MONOTONIC`/`steady_clock`），不要用墙上时间（会被 NTP 调整）。
6. **监控时钟偏差**（`chronyc tracking` 的 `System time`；Prometheus 的 `node_timex_offset_seconds` 告警）。""",
    ),
    (
        "Linux",
        "locale,编码",
        2,
        r"""Linux 的 locale 和字符编码是怎么工作的？中文乱码怎么排查？""",
        r"""**locale** 决定了**语言、日期格式、数字格式、字符分类、排序规则、字符编码**。

**分类（`LC_*`）**：

| 变量 | 影响 |
|---|---|
| `LANG` | 默认值（其他未设时用） |
| `LC_CTYPE` | **字符分类与编码**（乱码多与此相关） |
| `LC_COLLATE` | 字符串排序 |
| `LC_TIME` | 日期时间格式 |
| `LC_NUMERIC` | 数字格式（小数点/千分位） |
| `LC_MESSAGES` | 程序消息语言 |
| `LC_MONETARY` | 货币格式 |
| `LC_ALL` | **覆盖以上全部**（调试用） |

**查看与设置**：
```bash
locale                    # 当前生效值 ⭐
locale -a                 # 系统已生成的 locale 列表 ⭐
localectl status          # systemd 方式
localectl set-locale LANG=en_US.UTF-8
```
**持久化**：`/etc/locale.conf`（systemd）或 `/etc/default/locale`（Debian）。
**生成**：`localedef -i zh_CN -f UTF-8 zh_CN.UTF-8`（Debian 用 `locale-gen`）。

**推荐的服务器配置**：**`en_US.UTF-8`**
```bash
LANG=en_US.UTF-8
LC_ALL=en_US.UTF-8
```
**理由**：UTF-8 编码是必须的；`en_US` 让错误信息/日期格式是英文（便于搜索与脚本解析），且大部分服务器软件默认假设 `C`/`en_US`。

**⚠️ 关键坑：`LC_ALL=C` 的排序**
```bash
export LC_ALL=C
ls        # 按字节序排序（大写在小写前）
sort      # 字节序（**快得多**，大数据量排序可提速数倍）⭐
```
- **`LC_ALL=C` 让 `sort`/`grep`/`awk` 快 2~10 倍**（UTF-8 的分组/排序规则计算昂贵）。
- **代价**：中文排序变成按字节序（不是拼音序）；某些正则（如 `[a-z]`）行为不同。
- **实践**：处理大文件时 `LC_ALL=C sort`；需要正确中文排序时才用 `zh_CN.UTF-8`。

**字符编码基础**：

| 编码 | 说明 |
|---|---|
| **ASCII** | 7 位，0~127，只覆盖英文 |
| **ISO-8859-1 / Latin-1** | 8 位，西欧字符（0~255） |
| **GB2312 / GBK / GB18030** | 中文国标（GB18030 兼容 Unicode 全部字符） |
| **UTF-8** | **变长（1~4 字节）**，ASCII 兼容（英文 1 字节），**事实标准** ⭐ |
| **UTF-16/32** | 定长/半定长，Windows 内部用 |
| **cp1252** | Windows 西欧（Latin-1 的 Windows 变体） |

**UTF-8 的关键性质**：
- **ASCII 兼容**：0~127 与 ASCII 完全相同（所以纯英文的 UTF-8 文件就是 ASCII）。
- **中文字符 3 字节**（BMP 内），emoji 4 字节。
- **自同步**：任何字节都能判断是不是字符首字节（高位模式）。
- **不会出现 0x00**（所以与 C 字符串兼容）。

**乱码的三种形态（重要）**：

| 现象 | 原因 | 能否救回 |
|---|---|---|
| `?` | **写入时**目标字符集表示不了该字符，被**替换** | ❌ 不可逆，只能重新导入 |
| `çš„å¼•ç”¨`（mojibake） | **UTF-8 字节被当成 Latin-1/cp1252 解释** | ✅ 字节还在，可转回 |
| `ÖÐÎÄ`（GBK 被当 Latin-1） | GBK 字节被当 Latin-1 | ✅ 一般可转回 |

**`?` 与 mojibake 的区别很关键**：前者字节已丢，后者只是"解释方式错了"。**判断方法是用 `file`/`hexdump`/`iconv` 看原始字节**。

**排查工具**：
```bash
file -i file.txt                     # 猜测编码 ⭐
file --mime-encoding file.txt
hexdump -C file.txt | head           # 看原始字节 ⭐
xxd file.txt | head
iconv -f GBK -t UTF-8 file.txt       # 转码
iconv -f UTF-8 -t GBK//TRANSLIT      # 不可表示的字符用近似字符
iconv -l | grep -i utf               # 列出支持的编码
chardetect file.txt                  # python chardet
enca file.txt
```

**典型排查流程**：
1. **`file -i`** 猜编码 → 报 `charset=unknown-8bit` 说明不是合法 UTF-8。
2. **`hexdump -C`** 看字节：`E4 B8 AD` 是"中"的 UTF-8；`D6 D0` 是"中"的 GBK；`3F` 是 `?`（已丢）。
3. **判断是不是 mojibake**：如果字节看起来像"UTF-8 的字节被重复编码"（`C3 A4 C2 B8...`），就是双重编码。
4. **用 `iconv` 尝试转码**（先备份！）。

**`LANG` 引起的乱码**：
```bash
# 表现：终端里 ls 中文显示成 ??? 或问号方块
# 原因：LANG 不是 UTF-8（如 C 或 POSIX）
locale                 # 看 LC_CTYPE
export LANG=en_US.UTF-8
```
**服务/脚本环境里 LANG 常是 `C`**（cron、systemd、Docker），导致：
1. 程序输出中文乱码。
2. **Python 3 的文件默认编码是 UTF-8**（不受影响），但 **Python 2 会受影响**。
3. **`sort`/`grep` 的字符类行为不同**。
→ **在 cron/systemd 里显式设置 `LANG=en_US.UTF-8`**。

**文件内容的编码转换**：
```bash
iconv -f GBK -t UTF-8 -o out.txt in.txt
# 批量转换
find . -name "*.txt" -exec sh -c 'iconv -f GBK -t UTF-8 "$0" > "$0.utf8" && mv "$0.utf8" "$0"' {} \;
```
**文件名本身的编码**（乱码的另一种）：
```bash
convmv -f GBK -t UTF-8 -r --notest /path     # 转换文件名编码 ⭐
```

**实践建议**：
1. **统一 UTF-8 end-to-end**（文件、数据库、终端、HTTP 响应头）。
2. **服务器设 `LANG=en_US.UTF-8`**（必须有 UTF-8）。
3. **cron/systemd/容器里显式设 `LANG`/`LC_ALL`**。
4. **数据库**：库、表、列、连接四处字符集要一致（MySQL 用 `utf8mb4`）。
5. **HTTP**：响应头带 `Content-Type: text/html; charset=utf-8`。
6. **处理大文件时用 `LC_ALL=C`** 提速（注意排序语义变化）。
7. **看到 `?` 先别急着转码** —— 先确认是"写入时丢失"还是"解释错误"，两者的解法完全不同。
8. **换行符**：Windows `\r\n` vs Unix `\n` → `dos2unix`/`unix2dos` 或 `sed -i 's/\r$//'`。""",
    ),
    (
        "Linux",
        "软链接,PATH,hook",
        2,
        r"""`LD_PRELOAD` 是什么？为什么不建议长期用它？""",
        r"""**`LD_PRELOAD`** 让动态链接器在加载**所有其他**动态库之前先加载指定的库，从而**符号覆盖**后续同名符号。

```bash
LD_PRELOAD=/path/libmymalloc.so ./prog
```

**原理**：动态链接器按顺序解析符号，先加载的库里的定义**优先命中** → 可以"劫持"（hook）函数。

**典型用途**：

1. **替换分配器**（最常见）：
```bash
LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.2 ./myapp
LD_PRELOAD=/usr/lib/libtcmalloc.so ./myapp
```
2. **mock 测试**：拦截 `time()`、`rand()`、`open()` 让测试可复现。
3. **性能统计**：包一层 `malloc`/`free` 统计分配。
4. **调试**：
```bash
LD_PRELOAD=/lib/x86_64-linux-gnu/libSegFault.so ./prog    # 崩溃时打印栈
LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdbuf.so stdbuf -o0 ./prog   # 改缓冲
```
5. **修改已有二进制行为**（无源码，不想 `patchelf`）。

**写一个 hook 的骨架**：
```c
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>

static void* (*real_malloc)(size_t) = NULL;

void* malloc(size_t n) {
    if (!real_malloc) real_malloc = dlsym(RTLD_NEXT, "malloc");   // 找下一个定义
    void* p = real_malloc(n);
    // ... 记录
    return p;
}
```
```bash
gcc -shared -fPIC -o libhook.so hook.c -ldl
LD_PRELOAD=./libhook.so ./prog
```
**关键：`dlsym(RTLD_NEXT, "malloc")`** 绕过自己，找到真实的 `malloc`（否则无限递归）。

**为什么"不建议长期用"**：

1. **安全风险**：
   - `LD_PRELOAD` 是经典的**提权攻击面** —— 任何能设置环境变量的地方，攻击者就能注入代码。
   - 因此 **`LD_PRELOAD` 对 SUID/SGID 程序会被动态链接器忽略**（`AT_SECURE`），但配置不当（如 `sudo` 的 `env_keep`）就危险。
2. **难以预测的影响范围**：
   - **影响所有子进程**（包括 shell、git、编辑器），一处设置全环境生效，容易造成"某工具莫名崩溃"。
   - 与程序的其它库**冲突**（同一符号被判两个）。
3. **ABI 脆弱**：
   - 依赖内部符号/结构体布局，库升级后 hook 就失效或崩溃。
4. **可观测性差**：
   - 出问题时报错信息完全看不出是 `LD_PRELOAD` 引起的，排查成本高。
5. **不能被静态链接的程序使用**。
6. **容器里可能被 seccomp/权限限制**（且 `LD_PRELOAD` 不会进入容器，除非显式传递）。

**更稳妥的替代**：
| 需求 | 更好的做法 |
|---|---|
| 换分配器 | 编译时链接（`-ljemalloc`）或配置系统级 `malloc` 替换（glibc 的 `malloc` 钩子已废弃，但可在链接时指定） |
| 全局替换分配器 | **编译/链接期指定**，或 `systemd` 的 `Environment=LD_PRELOAD=...`（限定该服务） |
| hook 函数 | **eBPF uprobe**（无侵入、可观测、可随时关闭）⭐ |
| 修改二进制 | `patchelf`（改 rpath/依赖）、重新编译 |
| 测试 mock | 依赖注入、`--wrap` 链接选项、`faketime`（专门工具） |

**限定作用范围的技巧**：
```bash
# 只对一个命令生效（推荐）
LD_PRELOAD=/path/lib.so ./cmd

# systemd 服务级别（不污染全局）
# [Service]
# Environment=LD_PRELOAD=/path/lib.so

# 避免 LD_PRELOAD 泄漏到子进程
env -u LD_PRELOAD cmd
# 或（GNU coreutils）仅对指定变量生效
```

**`/etc/ld.so.preload`**：系统级 `LD_PRELOAD`（内容是一个路径列表）。**极其危险** —— 一旦里面的库有问题，**全系统所有动态程序都无法启动**（连 `ls` 都跑不了，要用救援模式修复）。**不要用它**，除非你有非常明确的理由并且知道怎么救。

**相关工具（正规军）**：
| 工具 | 用途 |
|---|---|
| `LD_DEBUG=libs,bindings` | 动态链接器调试（看符号绑定来源） |
| `ltrace` | 跟踪库函数调用 |
| `bpftrace` uprobe | **推荐的 hook 方式** |
| `faketime` | 专门的"伪造时间"工具 |
| `jemalloc` 的 `MALLOC_CONF` | 分配器参数（无需 hook） |

**实践建议**：
1. **不要写进 shell 的全局配置文件**（`/etc/profile`、`~/.bashrc`）。
2. **优先用 `systemd` 的 `Environment=` 限定到单个服务**。
3. **需要全局替换分配器**时，考虑在**链接时**指定或改容器基础镜像。
4. **调试用一次就撤**，不要长期留。
5. **`LD_PRELOAD` 对静态链接程序无效**（无动态链接器）。
6. **容器里要用 `--env LD_PRELOAD=...` 显式传**（宿主的不继承）。""",
    ),
    (
        "Linux",
        "rsync,备份",
        2,
        r"""`rsync` 怎么用？增量备份怎么实现？""",
        r"""**`rsync`** 是"**远程/本地文件同步**"工具，核心优势是**增量传输**（只传差异）与丰富的过滤规则。

**三种工作模式**：
```bash
# 1. 本地
rsync -av /src/ /dst/
# 2. 通过 SSH（推荐）
rsync -avz /src/ user@host:/dst/
rsync -avz user@host:/src/ /dst/
# 3. rsync daemon（rsync://，需要服务端跑 rsyncd）
rsync -av rsync://host/module/
```

**⚠️ 最经典的坑：结尾斜杠**
```bash
rsync -a /src/  /dst/     # 同步 src 的**内容** → /dst/file
rsync -a /src   /dst/     # 创建 /dst/src/ 并同步内容 → /dst/src/file
```
**带斜杠 = 同步目录内容；不带 = 把目录本身放进去。** 这是 rsync 事故的头号来源。

**常用选项**：

| 选项 | 含义 |
|---|---|
| `-a` | **归档模式**（= `-rlptgoD`：递归、保留链接/权限/时间/属组/属主/设备文件）⭐ |
| `-v` | 详细输出 |
| `-z` | 传输时压缩（CPU 换带宽；局域网可不用） |
| `-P` | = `--partial --progress`（断点续传 + 进度）⭐ |
| `-h` | 人类可读大小 |
| `-n` / `--dry-run` | **干跑，不实际改动** ⭐（**重要操作前必做**） |
| `--delete` | 删除目标端多余文件（**做成镜像**）⚠️ 危险 |
| `--exclude` / `--include` / `--exclude-from` | 过滤规则 |
| `--exclude-from=file` | 从文件读规则 |
| `-e ssh` | 指定远程 shell（如换端口：`-e "ssh -p 2222"`） |
| `--bwlimit=1000` | 限速（KB/s） |
| `--password-file` | 免交互（daemon 模式） |
| `--link-dest` | **硬链接增量备份** ⭐⭐ |
| `--backup --backup-dir=` | 保留被覆盖/删除的文件 |
| `--checksum` | 按校验和判断（默认按大小+时间） |
| `--numeric-ids` | 不映射用户/组 |
| `--sparse` | 稀疏文件优化 |
| `-x` | 不跨文件系统 |
| `--chown=user:group` | 强制指定属主 |

**典型用法**：
```bash
# 安全迁移（先干跑）
rsync -avhn --delete /src/ user@host:/dst/
# 确认无误后去掉 -n

# 带进度 + 续传
rsync -avzP file user@host:/path/

# 排除规则
rsync -av --exclude='*.log' --exclude='.git/' --exclude-from=.gitignore /src/ /dst/

# 只同步特定文件
rsync -av --include='*/' --include='*.py' --exclude='*' /src/ /dst/

# 限速（避免打满带宽）
rsync -avz --bwlimit=5000 /data/ host:/backup/

# 保持源目录不被修改（--delete 会删目标多余文件）
rsync -av --delete /src/ /mirror/     # 做成镜像 ⚠️ 源删了目标也删
```

**增量备份（`--link-dest` 硬链接快照）**——**rsync 最强大的用法**：

```bash
#!/bin/bash
# 每天一份快照，未变化的文件用硬链接，几乎不占额外空间
SRC=/data/
DEST=/backup
DATE=$(date +%Y%m%d)
LATEST=$(ls -1d $DEST/*/ 2>/dev/null | tail -1)

rsync -av --delete \
      --link-dest="$LATEST" \
      "$SRC" "$DEST/$DATE/"

# 清理 30 天前的
find $DEST -maxdepth 1 -type d -mtime +30 -exec rm -rf {} +
```
**原理**：未变化的文件在 `$DATE/` 里创建**硬链接**指向上一份快照的同一 inode → **多份快照共享数据块，只占一份空间**（变化的部分才占新空间）。这是"**时间机器式备份**"，也是 `rsync` 比 `cp -r` 更有价值的场景。

**恢复**：直接 `cp -a` 或 `rsync -a $DEST/20261009/ /restore/`（硬链接会被 `cp -a` 保留或展开，视选项）。

**与其它工具对比**：

| 工具 | 特点 |
|---|---|
| `scp` | 简单，**无法增量**，大文件传一半断了要从头来 |
| `rsync` | **增量、可续传、过滤、镜像、硬链接快照** ⭐ |
| `cp -r` | 本地，无增量 |
| `tar + ssh` | 适合一次性打包传输 |
| `restic`/`borgbackup` | **去重 + 加密 + 增量**的现代备份工具 ⭐（推荐用于重要数据） |
| `rdiff-backup` | 基于 rsync 的增量备份 |

**`scp` 已被 rsync 取代**：`scp` 的协议较老且慢（新实现用 SFTP），`rsync -zP` 更好。

**rsync daemon 模式**（`/etc/rsyncd.conf`）：
```ini
[backup]
path = /srv/backup
read only = no
auth users = backup
secrets file = /etc/rsyncd.secrets
hosts allow = 192.168.1.0/24
```
```bash
systemctl enable --now rsyncd
rsync -av --password-file=/etc/rsync.pass backup@host::backup/ /local/
```

**性能调优**：
| 场景 | 优化 |
|---|---|
| 大量小文件 | 用 `tar` 打包后传输（减少元数据往返），或用 `--whole-file` |
| 大文件 | 用 `-z`（若带宽受限）、`--partial` 续传 |
| 高延迟链路 | 减少往返（rsync 的算法对延迟敏感） |
| 文件多且变化少 | 保持默认（增量比对），但首轮可能很慢 |
| 排除无关目录 | 用 `--exclude` 大幅减少扫描（如 `.git`、`node_modules`、缓存） |

**备份的关键原则**：
1. **`--dry-run` 先看**（`-n`），**确认后再执行**。
2. **`--delete` 要非常小心**（源端误删会同步到备份）。
3. **备份不是只做一次**：脚本化 + 定时（cron/systemd timer）。
4. **一定要验证可恢复**（定期演练恢复流程）。
5. **考虑 3-2-1 原则**（3 份副本、2 种介质、1 份异地）。
6. **加密**（重要数据用 `restic`/`borg` 或加密后再传）。
7. **监控备份结果**（失败要告警，别让"以为有备份"变成事故）。""",
    ),
    (
        "Linux",
        "SSH,隧道,免密",
        2,
        r"""SSH 的原理是什么？端口转发怎么做？""",
        r"""**SSH（Secure Shell）**提供加密的远程登录与隧道能力，默认端口 22。

**连接过程（简化）**：
```
1. TCP 连接
2. 协商协议版本与算法（密钥交换、加密、MAC、压缩）
3. 密钥交换（DH/ECDH）→ 协商出会话密钥 + 验证服务器主机密钥
4. 用户认证（公钥 / 密码 / keyboard-interactive / GSSAPI）
5. 认证通过 → 建立会话通道（可多个）
```

**主机密钥验证**：
- 服务器有自己的主机密钥（`/etc/ssh/ssh_host_*_key`）。
- 客户端首次连接时把指纹存到 `~/.ssh/known_hosts`。
- **`WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!`** 出现时：
  - 服务器重装/换了密钥（正常）→ 删掉旧条目：
    `ssh-keygen -R host` 或 `sed -i '/host/d' ~/.ssh/known_hosts`
  - **也可能是中间人攻击** → 通过带外渠道核对指纹（`ssh-keyscan -t ed25519 host | ssh-keygen -lf -`）。

**免密登录（公钥认证）**：
```bash
# 1. 生成密钥对
ssh-keygen -t ed25519 -C "me@example.com"        # ed25519 现代首选 ⭐
# 老环境兼容：ssh-keygen -t rsa -b 4096
# 2. 上传公钥
ssh-copy-id user@host
# 或手工
cat ~/.ssh/id_ed25519.pub | ssh user@host 'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys'
# 3. 免密注意权限（否则 sshd 拒绝）
chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys; chmod 600 ~/.ssh/id_ed25519
chmod g-w,o-w ~            # 家目录不能被组/其他写（StrictModes）
```

**`~/.ssh/config`（强烈推荐）**：
```
Host blog
    HostName lazycat.cc
    User root
    Port 2222
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
    ServerAliveCountMax 3
    Compression yes

Host *
    AddKeysToAgent yes
    IdentitiesOnly yes
```
之后 `ssh blog` 即可。

**`ssh-agent`（避免重复输 passphrase）**：
```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
ssh-add -l
```

**端口转发（隧道）**：

| 类型 | 命令 | 用途 |
|---|---|---|
| **本地转发（-L）** | `ssh -L 8080:localhost:80 user@jump` | 把**本地** 8080 转到**远端能访问的** localhost:80 |
| **远程转发（-R）** | `ssh -R 8080:localhost:80 user@public` | 把**远端** 8080 转到**本地** 80（内网穿透）⭐ |
| **动态转发（-D）** | `ssh -D 1080 user@host` | **SOCKS5 代理**（浏览器配置 127.0.0.1:1080 即可翻墙/内网访问）⭐ |
| **跳板（-J）** | `ssh -J jumpuser@jump target` | 通过跳板机连接（ProxyJump）⭐ |

**`-L` 示意图**：
```
本地 8080 ──SSH 加密隧道──▶ jump 主机 ──▶ 目标 host:port
ssh -L 8080:db.internal:3306 user@jump
# 之后连本地 127.0.0.1:8080 就等于连 db.internal:3306
```

**`-R`（内网穿透）示意图**：
```
public 主机 8080 ──SSH 隧道──▶ 本地 80
ssh -R 8080:localhost:80 user@public
# 别人访问 public:8080 就能访问你本地的 80
# 需要 public 的 sshd 有 GatewayPorts yes（否则只绑 127.0.0.1）
```

**多层跳转**：
```bash
ssh -J a@host1,b@host2 c@host3
# 或
ssh -o ProxyCommand="ssh -W %h:%p user@jump" user@target
```

**保持连接（防止断开）**：
```bash
# 客户端（~/.ssh/config）
ServerAliveInterval 60
ServerAliveCountMax 3
# 服务端（/etc/ssh/sshd_config）
ClientAliveInterval 60
ClientAliveCountMax 3
TCPKeepAlive yes
```

**常用工具与技巧**：

| 场景 | 命令 |
|---|---|
| 执行远程命令 | `ssh host 'df -h'` |
| 传文件 | `rsync -avzP dir/ host:/dst/`（首选）；`scp file host:/path` |
| 复用连接（快） | `~/.ssh/config` 里 `ControlMaster auto` + `ControlPath ~/.ssh/cm-%r@%h:%p` ⭐ |
| 反向 DNS 慢 | sshd 里 `UseDNS no` |
| 调试 | `ssh -vvv user@host` ⭐ |
| 看服务器指纹 | `ssh-keyscan -t ed25519 host` |
| 强制某认证方式 | `ssh -o PreferredAuthentications=publickey` |
| 禁止密码登录 | sshd: `PasswordAuthentication no` |

**服务端加固（`/etc/ssh/sshd_config`）**：
```
Port 2222                    # 换端口（降低扫描噪音，非安全手段）
PermitRootLogin no           # 禁止 root 直登 ⭐
PasswordAuthentication no    # 只用密钥 ⭐
PubkeyAuthentication yes
PermitEmptyPasswords no
MaxAuthTries 3
LoginGraceTime 30
AllowUsers alice deploy      # 白名单
X11Forwarding no
UseDNS no
```
**改完要先语法检查再 reload**（否则可能把自己关在门外）：
```bash
sshd -t                      # 语法检查 ⭐
systemctl reload sshd        # reload 而不是 restart（保持现有连接）
```
> **务必保留一个已登录的会话**，改配置后**用新会话测试**，确认能登再关旧的。

**SSH 的性能提升**：
1. **算法选择**：`chacha20-poly1305` 或 `aes128-gcm`（快）；`KexAlgorithms curve25519-sha256`。
2. **关闭压缩**（局域网/已压缩数据）：`Compression no`（压缩反而慢）。
3. **关闭 DNS 反查**：`UseDNS no`（登录慢的经典原因）。
4. **`ControlMaster` 复用**（省略密钥交换）。
5. **`mosh`**：移动/高延迟网络下比 SSH 体验好得多（本地回显 + UDP）。

**常见问题**：
| 现象 | 原因 |
|---|---|
| `Permission denied (publickey)` | 权限不对（`~/.ssh` 需 700）、公钥没传对、`AllowUsers` 限制、SELinux |
| 登录很慢（十几秒） | `UseDNS yes` + DNS 慢；或 GSSAPI 超时 |
| `Connection refused` | sshd 没跑/端口不对/防火墙/安全组 |
| `Host key verification failed` | `known_hosts` 里有旧条目 → `ssh-keygen -R` |
| `Too many authentication failures` | agent 里密钥太多 → `IdentitiesOnly yes` |""",
    ),
    (
        "Linux",
        "软件编译,make",
        2,
        r"""在 Linux 上从源码编译安装软件的流程是什么？有哪些坑？""",
        r"""**经典五步**：
```bash
./configure --prefix=/usr/local/myapp   # 1. 检测环境、生成 Makefile
make -j$(nproc)                         # 2. 编译 ⭐
sudo make install                       # 3. 安装
# 4. 配置环境（PATH/LD_LIBRARY_PATH/ldconfig）
# 5. 验证
```

**各步骤说明**：

**1. `./configure`**
- 由 **Autotools**（`autoconf`/`automake`/`libtool`）生成，检测编译器、头文件、库、系统特性。
- 常用参数：
```bash
./configure --prefix=/usr/local        # 安装前缀（默认 /usr/local）
            --bindir=/usr/local/bin
            --sysconfdir=/etc
            --with-openssl=/usr/local/ssl
            --enable-debug / --disable-shared / --enable-static
            --host=x86_64-linux-gnu    # 交叉编译
```
- **看到 `checking for xxx... no` 就是缺依赖** → 装 `-devel`/`-dev` 包。
- `configure` 的结果在 `config.log`（报错时**先看它**）。

**2. `make`**
```bash
make -j$(nproc)             # 并行编译（注意内存：某些大文件并行会 OOM）
make -j4
make V=1                    # 详细输出（看实际编译命令）
make -n                     # 干跑（只看要做什么）
```
- **`make -j` 导致 OOM** 时降并发（`-j2`）或加 swap。
- 一些项目用 **CMake / Meson / Ninja / Cargo** 而非 autotools：
```bash
# CMake
mkdir build && cd build
cmake -DCMAKE_INSTALL_PREFIX=/usr/local -DCMAKE_BUILD_TYPE=Release ..
cmake --build . -j$(nproc)
cmake --install .

# Meson
meson setup build --prefix=/usr/local
ninja -C build
ninja -C build install

# Rust / Go
cargo build --release; go build
```

**3. `make install`**
- 会往 `${prefix}` 写文件。**用 `make -n install` 先看它会装到哪**（避免污染系统）⭐。
- **`DESTDIR`** 用于打包（装到临时目录）：
```bash
make install DESTDIR=/tmp/pkgroot
```

**4. 让系统能找到**
```bash
# 可执行文件
export PATH=/usr/local/bin:$PATH            # 持久化写 /etc/profile.d/xxx.sh

# 动态库（关键！）
sudo ldconfig                              # 重建 /etc/ld.so.cache ⭐
# 或显式配置目录
echo "/usr/local/lib" | sudo tee /etc/ld.so.conf.d/local.conf
sudo ldconfig -v | grep mylib

# pkg-config（供其他程序找到你）
export PKG_CONFIG_PATH=/usr/local/lib/pkgconfig:$PKG_CONFIG_PATH
```

**常见错误**：

| 报错 | 原因/解决 |
|---|---|
| `configure: error: C compiler cannot create executables` | 缺编译器：`dnf groupinstall "Development Tools"` / `apt install build-essential` |
| `xxx.h: No such file` | 缺开发包：`apt install libssl-dev` / `dnf install openssl-devel` |
| `cannot find -lxxx` | 缺库或库路径不对（用 `-L` / `ldconfig` / `LIBRARY_PATH`） |
| `undefined reference to` | 链接顺序问题（**被依赖的库要放后面**）、缺库、C++ 符号（用 `extern "C"` 或加 `-lstdc++`） |
| `error while loading shared libraries: libxxx.so` | `ldconfig` 没跑 / `LD_LIBRARY_PATH` 没设 / 装了但路径不在搜索路径 |
| `fatal error: Killed`（编译时） | **OOM**（`-j` 太大）→ 降并发或加内存/swap |
| `No space left on device` | 磁盘满（编译中间文件很大） |
| 版本冲突（系统已有旧版） | 装到独立 `--prefix`（如 `/opt/app-1.2`），用环境变量切换 |

**`-devel` / `-dev` 包**：
- 运行时库是 `libssl`，**编译需要 `libssl-dev`/`openssl-devel`**（头文件 + `.so` 符号链接 + pkg-config 文件）。
- 这是"为什么编译报缺头文件"的最常见答案。

**为什么"不要随便 `./configure && make install` 到系统目录"**：
1. **与包管理器冲突**：包管理器不知道你手工装的文件，升级时可能覆盖或冲突。
2. **可能覆盖系统库** → 导致整个系统工具崩溃（尤其升级 glibc/openssl 时）⭐。
3. **卸载困难**（`make uninstall` 不一定可靠）。
4. **难以复现**（新机器要重来一遍）。

**推荐做法**：
1. **优先用包管理器**；需要新版/自定义参数时用：
   - **官方仓库的 RPM/DEB**（如 `nginx.org`、`packages.elastic.co`）
   - **容器**（最隔离）
   - **`--prefix=/opt/app-<version>`** 独立目录 + 显式环境变量
2. **用 `checkinstall`** 把 `make install` 变成装包（可被包管理器管理）：
```bash
sudo checkinstall make install
```
3. **用 `stow`** 管理 `/usr/local/stow/*` 的软链接。
4. **绝对不要**手工 `make install` 到 `/usr`、`/lib` 覆盖系统库。

**交叉编译**：
```bash
./configure --host=aarch64-linux-gnu --build=x86_64-linux-gnu --prefix=/opt/arm
```

**编译优化选项**：
```bash
CFLAGS="-O2 -march=native -pipe" CXXFLAGS="-O2 -march=native" ./configure
# -march=native 针对本机 CPU 优化（不能跨机器分发）
# -pipe 减少临时文件
```
> ⚠️ **`-march=native` 编译的二进制不能在别的 CPU 上跑**（`Illegal instruction`）。**只在本地使用时才用**。

**并行/分布式编译**：
```bash
make -j$(nproc)                     # 本地并行
# ccache（缓存编译结果，重复编译提速数倍）⭐
sudo dnf install ccache
export CC="ccache gcc" CXX="ccache g++"
# 或全局把 /usr/lib64/ccache 加进 PATH
ccache -s                           # 统计命中率
# distcc（跨机器分布式编译）
# buildbox / sccache（Rust/云缓存）
```

**检查依赖与文档**：
```bash
cat README / INSTALL                # 大多数项目有安装说明 ⭐
cat configure --help | less
pkg-config --modversion openssl     # 检查库版本
ldd ./binary                        # 检查运行时依赖
```

**实践建议**：
1. **先 `cat INSTALL` / `README.md`**（不同项目流程不同）。
2. **`./configure` 失败先看 `config.log`**。
3. **缺头文件 = 缺 `-dev`/`-devel` 包**。
4. **`make -j` 报 Killed = OOM**，降并发。
5. **`ldconfig` + `-dev` 包 + `pkg-config`** 是三方库集成的三要点。
6. **生产环境优先容器/包**，源码编译只在前两者不可行时使用，且装到独立 prefix。""",
    ),
    (
        "Linux",
        "keepalived,VIP,高可用",
        3,
        r"""`keepalived` 和 VRRP 是怎么实现高可用的？""",
        r"""**`keepalived`** 是 Linux 上实现**高可用（HA）** 的常用工具，核心是 **VRRP 协议** + **健康检查**。

**VRRP（Virtual Router Redundancy Protocol）**：
- 一组机器组成一个**虚拟路由器**，共享一个**虚拟 IP（VIP）**。
- 一台是 **MASTER**（持有 VIP），其余是 **BACKUP**。
- MASTER 周期性发 VRRP 通告（组播/单播）；BACKUP 收不到就接管 VIP。
- **优先级（priority）** 决定谁当 MASTER（大者胜，默认 100）。

**典型拓扑（主备）**：
```
客户端 → VIP 1.2.3.4
            │
    ┌───────┴────────┐
MASTER(1.2.3.5)   BACKUP(1.2.3.6)
  绑定 VIP          待命，收不到通告则接管 VIP
```

**配置（`/etc/keepalived/keepalived.conf`）**：

```ini
vrrp_instance VI_1 {
    state MASTER                 # MASTER / BACKUP
    interface eth0
    virtual_router_id 51         # 同一组必须一致（0-255）
    priority 100                 # 越大越优先
    advert_int 1                 # 通告间隔（秒）
    authentication {
        auth_type PASS
        auth_pass 12345678
    }
    unicast_src_ip 1.2.3.5       # 用单播（云环境常禁组播）
    unicast_peer { 1.2.3.6 }
    virtual_ipaddress {
        1.2.3.4/24 dev eth0
    }
}

# 健康检查：nginx 挂了就降优先级/切换
vrrp_script chk_nginx {
    script "/usr/bin/killall -0 nginx"
    interval 2
    weight -20                   # 失败时优先级 -20
    fall 2                       # 连续 2 次失败才算失败
    rise 2                       # 连续 2 次成功才算恢复
}

vrrp_instance VI_1 {
    # ...
    track_script {
        chk_nginx
    }
}
```

```bash
systemctl enable --now keepalived
ip addr show eth0                     # 看 VIP 是否在本机 ⭐
journalctl -u keepalived -f
```

**工作原理细节**：
1. MASTER 每 `advert_int` 秒发 VRRP 通告。
2. BACKUP 在 `3 * advert_int + skew` 内没收到通告 → 认为 MASTER 挂了 → **接管 VIP**（发免费 ARP 通知交换机/网关更新 MAC 表）。
3. **原 MASTER 恢复后**：
   - 若 `state MASTER` 且优先级最高 → **抢回**（可能造成抖动）。
   - 设置 **`nopreempt`** 让恢复后不抢回（更稳定）。
4. **VIP 漂移速度**：通常 1~3 秒（取决于 `advert_int`）。

**健康检查**：
- `vrrp_script` 执行脚本，退出码 0 为成功。
- `weight` 正数表示成功时加分，负数表示失败时减分。
- 也可用 **`MISC_CHECK`** 做 HTTP/TCP 检查。
- 检查的粒度要合理（太敏感会频繁切换，太迟钝会长期不可用）。

**常见架构**：
| 架构 | 说明 |
|---|---|
| **主备（active-passive）** | 一台干活，一台待命。资源利用率 50%，但简单可靠 |
| **主主（active-active）** | 两个 VIP，各挂一个，互为主备（**注意有状态的连接**） |
| **LVS + keepalived** | keepalived 同时管理 VIP 和 LVS 规则（`virtual_server` 段）⭐ |
| **多级（LVS → Nginx → App）** | 逐层 HA |

**LVS 集成（负载均衡场景）**：
```ini
virtual_server 1.2.3.4 80 {
    delay_loop 6
    lb_algo rr               # 轮询 / wrr / lc / sh
    lb_kind DR               # Direct Routing（性能最好）
    protocol TCP
    real_server 10.0.0.10 80 {
        weight 1
        HTTP_GET {
            url { path /health  status_code 200 }
            connect_timeout 3
            nb_get_retry 3
            delay_before_retry 3
        }
    }
    real_server 10.0.0.11 80 { ... }
}
```

**云环境注意**：
| 问题 | 说明 |
|---|---|
| **组播被禁** | 云 VPC 通常禁 VRRP 组播 → **必须用 `unicast_peer`** ⭐ |
| **VIP 不在子网内** | 传统 VRRP 要求 VIP 与节点同子网；云上可能需**辅助 IP/弹性 IP** |
| **云厂商的 HA 方案** | 很多云提供"高可用虚拟 IP（HAVIP）"，**由云平台做 VIP 漂移**，不需要自己跑 keepalived |
| **安全组/网络 ACL** | 要放行 VRRP 协议（112）或单播端口 |
| **`arp_ignore`/`arp_announce`** | 做 LVS DR 时必须调（否则 ARP 冲突） |

**LVS DR 模式的 ARP 参数**（RealServer 上必配）：
```bash
# 只回答目标 IP 是自己网卡 IP 的 ARP 请求
echo 1 > /proc/sys/net/ipv4/conf/all/arp_ignore
echo 2 > /proc/sys/net/ipv4/conf/all/arp_announce
```

**其它 HA 方案对比**：
| 方案 | 特点 |
|---|---|
| **keepalived** | 独立工具，轻量，VRRP + 健康检查 |
| **Pacemaker + Corosync** | 功能强大（资源组、约束、STONITH 隔离），复杂 |
| **云厂商 HAVIP** | 托管，省心 |
| **DNS 轮询** | 简单但无健康检查、有 TTL 缓存问题 |
| **代理层（nginx/haproxy）** | 应用层高可用，可做 7 层路由 |

**关键实践（重要）**：
1. **必须解决"脑裂"（split-brain）**：网络分区时两台都以为自己是 MASTER → **同时绑 VIP → IP 冲突**。
   - 缓解：**额外的心跳线**（独立网络/串口）、Pacemaker 的 **STONITH**（直接断电对端）、云上的仲裁。
   - keepalived 的 VRRP 本身**不能完全避免脑裂**，只适合简单场景。
2. **健康检查要覆盖真实依赖**（不只是"进程在"，而是"能响应请求"）。
3. **防抖动**：`fall`/`rise`、`nopreempt`。
4. **VIP 切换后要通知下游**（免费 ARP 可能不被某些云网络正确处理）。
5. **应用要无状态或共享状态**（否则切过去后 session 丢失）→ 用 Redis/DB 存 session。
6. **监控 VIP 归属**（`ip addr` 检查、脚本告警），否则"VIP 掉到没人管的机器上"可能长期不被发现。
7. **测试切换**（定期演练，包括**主备都重启**的场景）。""",
    ),
    (
        "Linux",
        "防火墙放行,排查端口不通",
        2,
        r"""服务端口不通，你会怎么一步步排查？""",
        r"""**这是一个非常高频的实战题。按"从下到上、由近及远"的固定顺序排查**：

**第 0 步：确认现象与范围**
- 是本机访问不通，还是外部访问不通？
- 是所有端口都不通，还是只有某个端口？
- 换台机器/换个网络试（排除客户端问题）。
- 报什么错：`Connection refused`（有响应但没人监听）、`Connection timed out`（被丢包/防火墙）、`No route to host`（路由/ARP）。

**第 1 步：服务是否在监听？（最常见）**
```bash
ss -lntp | grep :8080
# 关键：看监听地址！
#   0.0.0.0:8080   → 所有网卡都能访问 ✅
#   127.0.0.1:8080 → **只有本机能访问** ❌ 外部连不上
```
- **只绑 `127.0.0.1` 是"外部不通"的头号原因**（应用配置问题，如 `bind 127.0.0.1`、`listen localhost`）。
- 检查应用日志：`journalctl -u svc -n 100`、应用自己的日志文件。

**第 2 步：本机能不能连？（区分"应用"与"网络"）**
```bash
curl -v http://127.0.0.1:8080/           # 本机 loopback
curl -v http://<本机内网IP>:8080/         # 走网卡
nc -zv 127.0.0.1 8080                    # 只测 TCP 连通 ⭐
nc -zvu 127.0.0.1 8080                   # UDP
```
- **loopback 通、网卡 IP 不通** → 应用只绑了 127.0.0.1（回到第 1 步）。
- **两者都不通** → 应用没起来/端口不对/进程挂了。

**第 3 步：本机防火墙**
```bash
iptables -L -n -v --line-numbers
iptables -t nat -L -n -v
nft list ruleset
firewall-cmd --list-all                  # firewalld
firewall-cmd --state
```
- **常见坑**：`INPUT` 默认策略是 `DROP`，但忘了放行新端口。
- **`DOCKER-USER` 链**：Docker 会插入规则，你的自定义规则可能被覆盖。
- **临时验证**：`iptables -I INPUT 1 -p tcp --dport 8080 -j ACCEPT` 试一下。

**第 4 步：云安全组（**最常被忽略**）**
- **云厂商的安全组在主机之前生效**（流量根本没到达主机）。
- **排查特征**：`tcpdump` 在主机上**抓不到任何包** → 说明被上游拦了。
- 检查：云控制台的**入站规则**、**网络 ACL**（子网级）、**安全组绑定的网卡**。
- **这是"iptables 全开但还是不通"的答案**。

**第 5 步：抓包确认包到没到（决定性证据）** ⭐
```bash
# 在服务端抓
tcpdump -i any -nn port 8080
# 同时从客户端发起请求
nc -zv <server> 8080
```
| 抓包结果 | 结论 |
|---|---|
| **看到 SYN，也看到 SYN-ACK 发出** | 服务端正常，问题在**客户端或回程路径** |
| **看到 SYN，没有 SYN-ACK** | 服务端防火墙丢弃，或服务没监听 |
| **完全抓不到 SYN** | 被**上游（安全组/路由器/中间网络）** 拦截 |
| **看到 SYN 被 RST** | 端口没监听（但主机可达） |

**第 6 步：路由与中间网络**
```bash
ping <server>                      # 基本连通
traceroute <server> / mtr <server> # 路径在哪断
ip route get <server>              # 走哪条路由
ping -M do -s 1472 <server>        # MTU 测试（MTU 问题会导致"小包通、大包卡"）⭐
```
- **MTU 问题**：TCP 握手成功但**传输大数据时卡住**（大包被丢且 ICMP 被过滤）→ 典型症状是"能连上但下载不动"。
- **回程路由**：多网卡机器可能"去程走 A 网卡、回程走 B 网卡" → 用 `tcpdump` 在两张网卡上都抓。

**第 7 步：应用层与代理**
```bash
# 反向代理（nginx/haproxy）配置
nginx -T | grep -A5 "listen\|proxy_pass"
# 上游服务是否可达（从代理机器测）
curl -v http://upstream:port/health
# TLS 问题
openssl s_client -connect host:443 -servername example.com
```
- **代理配了但上游不通**、**超时配置太短**、**TLS 证书/SNI 问题**。

**第 8 步：端口耗尽/资源限制**
```bash
ss -s                                  # 连接数汇总
ulimit -n / cat /proc/<pid>/limits     # fd 限制
dmesg | tail                           # 是否有 "nf_conntrack: table full"
netstat -s | grep -i overflow
```
- `nf_conntrack: table full` → 丢包。
- `accept queue overflow` → 应用 accept 太慢。
- fd 耗尽 → `EMFILE`。

**排查命令速查表**：

| 目的 | 命令 |
|---|---|
| 是否在监听 | `ss -lntp` |
| 监听在哪个地址 | `ss -lntp`（看 Local Address） |
| 本机能否连 | `nc -zv 127.0.0.1 <port>` |
| 防火墙 | `iptables -L -n -v` / `firewall-cmd --list-all` |
| 云安全组 | 云控制台 |
| 包到没到 | `tcpdump -i any -nn port <port>` |
| 路径 | `mtr <host>` |
| MTU | `ping -M do -s 1472 <host>` |
| 进程是否活着 | `ps aux \| grep svc`、`systemctl status svc` |
| 应用日志 | `journalctl -u svc -n 100` |
| 连接状态 | `ss -tan state time-wait`、`ss -s` |

**排查口诀**：
1. **先看监听地址**（127.0.0.1 是最常见的坑）。
2. **本机 loopback 先通**（排除网络，聚焦应用）。
3. **本机防火墙 → 云安全组**（从内到外）。
4. **抓包定位"包到没到"**（最有信息量的一步）。
5. **`Connection refused` = 没监听；`timeout` = 被拦/丢包**。

**实践建议**：
1. **部署新服务时按顺序验证**：进程起来了 → 本机 curl 通 → 绑定地址正确 → 防火墙放行 → 安全组放行 → 外部可访问。
2. **写一个 `check_port.sh`**（`ss` + `nc` + `iptables` 一起看）固化流程。
3. **生产变更前先 `tcpdump` 抓一次**（有基线才知道变化）。
4. **不要忘记容器**：端口映射（`docker port`）、容器网络（`--network host` vs bridge）、k8s 的 Service/Ingress/NetworkPolicy。""",
    ),
    (
        "Linux",
        "nohup,后台运行",
        1,
        r"""怎么让程序在后台运行、关掉终端也不退出？有哪些方式？""",
        r"""**四种方式，按推荐度排序**：

**1. systemd（生产首选）⭐**
```ini
# /etc/systemd/system/myapp.service
[Unit]
Description=My App
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/myapp
Restart=on-failure
RestartSec=3
User=appuser
WorkingDirectory=/opt/app
EnvironmentFile=-/etc/myapp.env
StandardOutput=journal
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now myapp
systemctl status myapp; journalctl -u myapp -f
```
**优势**：开机自启、崩溃自动重启、日志统一、资源限制（cgroup）、依赖管理、无终端依赖。**所有持久化服务都该这么做。**

**2. `nohup`（临时/简单场景）**
```bash
nohup ./myapp > app.log 2>&1 &
nohup ./myapp > app.log 2>&1 &      # 记下 PID
echo $! > app.pid
```
- **`nohup` 的作用**：忽略 `SIGHUP`（终端关闭时发给会话的信号），所以关终端不会杀它。
- **必须重定向输出**，否则 nohup 会写到 `nohup.out`（可能填满磁盘）。
- **`&`** 让它在后台运行。
- **注意**：`nohup` **不会**让进程脱离控制终端（不像 `setsid`），仍然能收到其他信号。

**3. `setsid`（完全脱离会话）**
```bash
setsid ./myapp > app.log 2>&1 < /dev/null &
```
- `setsid` 创建新会话，**完全脱离控制终端**（daemon 化的一种简化方式）。
- **`< /dev/null`** 让 stdin 不再指向终端（否则某些程序会读终端）。

**4. `&` + `disown`（已启动后想"脱离"）**
```bash
./myapp &
jobs
disown -h %1              # 从 shell 的作业表移除（收到 SIGHUP 也不转发）
```

**5. `screen`/`tmux`（交互式场景）**
```bash
tmux new -s work
# Ctrl+B, D 分离
tmux attach -t work
```
- 适合**需要交互**的长期任务（编译、跑脚本、看日志）。
- **比 `nohup` 更可靠**：进程的终端是伪终端，且有完整的会话管理。
- **`tmux` 推荐给 `screen`**（更现代）。

**关键区别**：

| 方式 | 脱离终端 | 开机自启 | 崩溃重启 | 日志管理 | 推荐场景 |
|---|---|---|---|---|---|
| systemd | ✅ | ✅ | ✅ | ✅ | **生产服务** ⭐ |
| nohup | 部分（忽略 SIGHUP） | ❌ | ❌ | 手动 | 临时任务 |
| setsid | ✅ | ❌ | ❌ | 手动 | 脚本里启后台 |
| screen/tmux | ✅ | ❌ | ❌ | 手动 | 交互式长期任务 |
| `&` 单独用 | ❌ | ❌ | ❌ | 手动 | 立即返回的后台任务 |

**常见坑**：

1. **关掉终端后进程还是死了**
   - 原因：没 `nohup`/`setsid`，进程收到 **SIGHUP**。
   - 或者：**stdin 被关闭读不到数据**导致程序退出。
   - 解决：`nohup cmd > log 2>&1 < /dev/null &`。

2. **`screen`/`tmux` 里跑还是被杀了**
   - 可能被 `OOM killer` 杀了（`dmesg | grep -i oom`）。
   - 或被外部脚本 `pkill`。

3. **`nohup` 会忽略 `SIGINT`（Ctrl+C）吗？**
   - **不会**！`nohup` 只处理 `SIGHUP`。但因为它在后台运行，终端不会把 Ctrl+C 发给它。

4. **进程"假死"**
   - 用 `ps -o stat` 看状态：`D`（不可中断的 IO，通常是磁盘/网络存储卡住）→ **`kill -9` 也杀不掉**。
   - `Z`（僵尸）→ 父进程没 `wait`。

5. **`&` 之后 shell 退出会怎样**
   - 交互式 bash 默认**不**给后台作业发 SIGHUP（除非 `huponexit` 开启）；但**非交互式脚本**里会。
   - 这是"脚本里 `cmd &` 后脚本结束、cmd 也被杀"的原因。

6. **`nohup.out` 越来越大**
   - 忘了重定向输出 → 磁盘被打满。
   - **一定要 `> /path/app.log 2>&1`**，并考虑 `logrotate`。

7. **`kill` 找不到进程**
   - 用 `pgrep -af myapp`、`ps aux | grep myapp`。
   - **不要用 `pkill -f myapp`**（可能误杀 `grep myapp` 或路径相似的进程）。

**实用脚本模板**（无 systemd 时的替代）：
```bash
#!/bin/bash
APP=/usr/local/bin/myapp
LOG=/var/log/myapp.log
PIDFILE=/var/run/myapp.pid

start() {
    [ -f "$PIDFILE" ] && kill -0 "$(cat $PIDFILE)" 2>/dev/null && { echo "already running"; return 1; }
    nohup "$APP" >> "$LOG" 2>&1 < /dev/null &
    echo $! > "$PIDFILE"
    echo "started pid $(cat $PIDFILE)"
}
stop() {
    [ -f "$PIDFILE" ] || { echo "not running"; return; }
    kill "$(cat $PIDFILE)" && rm -f "$PIDFILE"
}
case "$1" in
    start) start ;;
    stop)  stop ;;
    restart) stop; sleep 1; start ;;
    status) [ -f "$PIDFILE" ] && kill -0 "$(cat $PIDFILE)" && echo running || echo stopped ;;
    *) echo "usage: $0 {start|stop|restart|status}" ;;
esac
```
**注意 PID 文件的"陈旧"问题**（进程崩了但文件还在）→ 用 `kill -0` 校验（更好的是用 `flock`，见文件锁一题）。

**信号与优雅退出**：
```bash
kill -TERM <pid>     # 请求退出（应用应捕获并优雅关闭）⭐
kill -KILL <pid>     # 强杀（不可捕获，不给清理机会）
kill -HUP  <pid>     # 常被 daemon 用于"重载配置"
```
**用 `-TERM` 而不是 `-9`**，给应用时间回收资源（关闭连接、落盘、释放锁）。

**排查"后台进程莫名消失"**：
```bash
journalctl -b | grep -i -E "oom|killed"
dmesg -T | grep -i oom
grep -i "killed process" /var/log/*      # 旧系统
# 是否有其他进程/supervisor 杀了它
ps -ef --forest | grep -B5 myapp
```
**`systemd` 的好处在这里特别明显**：它会记录"为什么停"（`systemctl status` 显示 `signal=KILL`、`Main process exited`、`Failed with result 'oom-kill'`）。""",
    ),
    (
        "Linux",
        "内核编译,升级",
        3,
        r"""Linux 内核怎么编译和升级？升级后驱动（如网卡）没了怎么办？""",
        r"""**编译内核的完整流程**：

```bash
# 1. 准备工具
sudo apt install build-essential libncurses-dev bison flex libssl-dev libelf-dev
# 或 dnf install gcc make ncurses-devel bison flex elfutils-libelf-devel openssl-devel

# 2. 获取源码
cd /usr/src
wget https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.6.tar.xz
tar xf linux-6.6.tar.xz && cd linux-6.6

# 3. 配置（关键步骤）
make menuconfig               # 交互式 TUI ⭐
# 或
make oldconfig                # 基于现有 .config 只问答新选项（**升级推荐**）⭐
cp /boot/config-$(uname -r) .config && make olddefconfig
make localmodconfig           # 只编译当前加载的模块（**大幅减少编译量与体积**）⭐
make defconfig                # 发行版默认（通用）
make nconfig                  # 更好的 TUI

# 4. 编译（很耗时，用并行）
make -j$(nproc)               # 编译内核镜像与模块 ⭐
make -j$(nproc) modules_install
# 或一步：make -j$(nproc) && sudo make modules_install

# 5. 安装
sudo make install             # 装到 /boot（vmlinuz + System.map）
sudo mkinitramfs -o /boot/initrd.img-6.6 6.6      # Debian
# 或 sudo dracut -f /boot/initramfs-6.6.img 6.6   # RHEL
sudo update-grub              # 更新 GRUB 菜单 ⭐（否则重启进不了新内核）
# 或 sudo grub2-mkconfig -o /boot/grub2/grub.cfg

# 6. 重启并从新内核启动
reboot
uname -r
```

**关键配置文件**：

| 方式 | 说明 |
|---|---|
| `menuconfig` | 交互式，功能最全 |
| `oldconfig` | 只问新增项（**升级时用**） |
| `olddefconfig` | 新增项用默认值（不交互） |
| `localmodconfig` | 只保留当前用到的（**编译快、体积小**） |
| `defconfig` | 目标架构默认配置 |
| `/boot/config-$(uname -r)` | **当前内核的配置**（编译新内核时拷它最省事） |
| `.config` | 编译产出，**要备份** |

**「编译完重启，网卡/键盘/文件系统没了」——最经典的内核升级事故**：

**原因**：新 `.config` 缺少对应**驱动**（没编译进内核，也没编译成模块）。

**预防（重要）**：
1. **一定从当前内核配置出发**：
```bash
cp /boot/config-$(uname -r) .config
make olddefconfig
```
2. **不要轻易用 `localmodconfig`**，除非你确定所有需要的驱动都已加载（**U 盘启动救援设备、虚拟机的 virtio 驱动、非当前挂载的存储控制器都可能漏掉**）。
3. **`localmodconfig` 后手工加回关键驱动**（在 `menuconfig` 里搜索）：
   - 存储：`CONFIG_ATA`、`CONFIG_SATA_AHCI`、`CONFIG_VIRTIO_BLK`、`CONFIG_NVME_CORE`、RAID/LVM
   - 文件系统：`CONFIG_EXT4_FS`、`CONFIG_XFS_FS`、`CONFIG_BTRFS_FS`
   - 网络：对应厂商驱动（`CONFIG_E1000E`、`CONFIG_VIRTIO_NET`、`CONFIG_MLX5_CORE`）
   - 虚拟化：`CONFIG_VIRTIO_*`、`CONFIG_XEN_*`、`CONFIG_HYPERV_*`
4. **initramfs 要重新生成**（否则启动时挂不上根文件系统）—— **这一步漏掉是最常见的"启动直接 kernel panic"原因**。
5. **保留旧内核**，别删 `make install` 之前的老 vmlinuz 与 initrd。
6. **先在有控制台/救援能力的机器上试**（云主机改内核风险高，很多云不支持自定义内核）。

**救援流程（新内核起不来）**：
1. **重启时在 GRUB 菜单选旧内核**（GRUB 默认保留多个条目）→ 系统能起来。
2. 或用**云控制台的 VNC/串口控制台**登录。
3. 起来后：检查 `dmesg` 缺什么驱动、`/boot` 里文件是否齐全、GRUB 是否更新。
4. 修好后**再次验证 initramfs**（`lsinitramfs /boot/initrd.img-xxx | grep 驱动`）。

**内核模块相关命令**：
```bash
uname -r                       # 当前内核版本
lsmod                          # 已加载模块
modinfo <mod>                  # 模块信息（vermagic 要匹配内核！）
modprobe -v <mod>              # 加载（含依赖）
dmesg | tail                   # 加载失败的原因
# 编译单个模块（在内核源码树里）
make M=drivers/net/ethernet/intel/e1000e modules
insmod ./e1000e.ko
```
**`vermagic` 不匹配**：模块与内核版本/配置不一致 → `insmod: ERROR: could not insert module: invalid module format`。

**DKMS（动态内核模块支持）**：
- 让**第三方驱动**（NVIDIA、VirtualBox、ZFS、某些网卡）在**每次内核升级后自动重编译**。
```bash
dkms status
sudo dkms autoinstall
# 更新内核前先确认 DKMS 支持
```
**没有 DKMS 的第三方驱动 + 升级内核 = 驱动失效**（NVIDIA 显卡最常见的坑）。

**发行版内核 vs 自编译内核**：
| | 发行版内核 | 自编译 |
|---|---|---|
| 维护 | 自动更新、安全补丁 | 完全自己管 |
| 驱动 | 全打包 | **可能漏** |
| 配置 | 通用（体积大） | 精简（快、省内存） |
| 适用 | **绝大多数场景** ⭐ | 特殊需求（实时性、特定补丁、裁剪嵌入式） |
| 风险 | 低 | **高** |

**实践建议**：
1. **99% 的场景不要自己编译内核** —— 用发行版内核或官方 backport（如 `elrepo-kernel`、Ubuntu 的 `linux-generic-hwe`）。
2. **需要新内核特性**时优先用发行版的更新仓库。
3. **真要编译**：`cp /boot/config-$(uname -r) .config` + `olddefconfig` + **务必 `make install` + 生成 initramfs + `update-grub`**。
4. **在虚拟机/测试环境先跑通**，确认能启动、驱动齐全、`lsmod` 正常，再上生产。
5. **备份 `/boot` 和当前内核包**（`dnf install kernel` 式的包安装比手工 `make install` 好 — 包管理器会处理好 GRUB 与 initramfs）。
6. **云主机**：多数云不支持自定义内核（用云厂商的 `cloud-kernel`）；需要新特性优先**升级发行版**或换用支持自定义内核的实例类型。
7. **内核参数**（`/etc/default/grub` 的 `GRUB_CMDLINE_LINUX`）改完要 `update-grub`。
8. **不要在生产直接 `apt upgrade` 内核后立即重启** —— 评估 DKMS 驱动、`/boot` 空间、GRUB 条目，并在维护窗口操作。""",
    ),
    (
        "Linux",
        "磁盘满,空间排查",
        2,
        r"""磁盘满了怎么排查？"`df` 和 `du` 结果不一致"是怎么回事？""",
        r"""**第一步：确认是"空间满"还是"inode 满"**
```bash
df -h                     # 空间 ⭐
df -i                     # inode ⭐
```
| 现象 | 结论 |
|---|---|
| `df -h` 显示 100% | 空间满 |
| `df -h` 未满但 `df -i` 100% | **inode 耗尽**（海量小文件） |
| `df -h` 未满、`df -i` 也正常，但报 `No space left on device` | 可能是**保留块**、**已删除但被占用**、**磁盘配额** |

**inode 耗尽**：
```bash
df -i
# 找到 inode 最多的目录（逐层深入）
for d in /*; do echo "$d: $(find $d -xdev -printf '.' 2>/dev/null | wc -c)"; done
# 常见罪魁：session 文件、邮件队列、Docker 层、缓存目录
find /var -xdev -type f | wc -l
```
**解决**：清理小文件；对将来，`mkfs.ext4 -N <更大数量>` 或改用 XFS（XFS 动态分配 inode）。

**第二步：定位是哪个目录/文件**
```bash
du -xh --max-depth=1 / | sort -rh | head -20        # 逐层下钻 ⭐
du -xh --max-depth=1 /var | sort -rh | head
find / -xdev -type f -size +1G -exec ls -lh {} + 2>/dev/null   # 大文件 ⭐
ls -lhS /var/log | head                            # 最大的日志
# 更快的工具
ncdu /var                                          # 交互式磁盘使用分析 ⭐
duf                                                # df 的现代替代
```

**常见"吃空间"的地方**：
| 位置 | 说明 |
|---|---|
| `/var/log` | 日志（尤其未轮转的应用日志、journal） |
| `/var/lib/docker` | 镜像与容器层（`docker system prune`） |
| `/var/cache` | 包缓存（`dnf clean all`/`apt clean`） |
| `/tmp` | 临时文件 |
| journal | `journalctl --disk-usage`、`--vacuum-size=500M` |
| 数据库数据目录 | binlog、WAL、慢查询日志 |
| 用户家目录 | 缓存、下载、`.cache` |
| 内核 `/usr/lib/modules` | 多版本内核未清理 |

**⚠️ 第三步（关键）：`df` 与 `du` 不一致**

**症状**：`df` 说满了，`du` 加起来远小于容量。

**原因 1：文件被删除但仍被进程打开（最常见）** ⭐
- 文件 `unlink` 后，`du`（遍历目录）看不到它，但**inode 和数据块仍被占用**（进程还持有 fd）。
- 这是"删了大文件但空间没释放"的经典原因。

```bash
lsof +L1                       # 列出 link count < 1 的打开文件 ⭐
lsof | grep deleted
# 或
ls -l /proc/*/fd/* 2>/dev/null | grep deleted
# 找到后：
#   a) 重启/杀掉持有它的进程（释放）
#   b) 或不停进程直接清空（对日志文件有效）
> /proc/<pid>/fd/<fd>          # 截断（小心：会改变文件内容的可见性）
```

**原因 2：文件系统保留块**
- ext4 默认给 root 保留 **5%** 空间（`mke2fs -m 0` 或 `tune2fs -m 1` 可调）。
- 非 root 用户看到的 `df` 可用空间比 root 少 5%。

**原因 3：挂载覆盖（mount 背后有文件）**
```bash
# 挂载点下面原本有文件，挂载后被"遮住"，du 看不到但确实占空间
# 卸载后能看到
umount /mnt && du -sh /mnt
# 检查是否有嵌套挂载
findmnt -R /        # 或 cat /proc/mounts
```

**原因 4：稀疏文件、快照**
- 稀疏文件的 `ls` 显示大小 ≠ 实际占用（用 `du` 看实际，`ls -s`、`stat` 的 Blocks）。
- **LVM 快照**会占空间（`lvs`、`lvdisplay`）。
- **XFS 的 reflink**、**Btrfs/ZFS 的快照**会保留旧数据块。

**原因 5：`df` 统计的是文件系统，`du` 只统计你指定的目录**
- `du /var` 不会算 `/home` 的占用。
- **跨文件系统**：`du -x` 限制在单个文件系统。

**原因 6：ext4 的 journal、文件系统元数据**
- 少量差异正常。

**第四步：清理（**先归档，不要 `rm -rf`**）**
```bash
# 日志
journalctl --vacuum-size=500M
journalctl --vacuum-time=7d
find /var/log -name "*.gz" -mtime +30 -delete
# 包缓存
dnf clean all / apt clean
# Docker
docker system df                 # 查看占用 ⭐
docker system prune -a           # 清理（**会删未使用的镜像**，确认后再执行）
# 找出并处理"已删除但被占用"的文件
lsof +L1 | awk '{print $1, $2, $7, $9}'
```
**清理原则**：
1. **先看再删**（`du`/`ncdu`/`lsof` 确认）。
2. **日志优先归档/截断，不直接 rm**（保持 inode 不变，服务不用重启）。
3. **不要 `rm -rf /var/log/*`**（有些服务持有文件句柄）。
4. **清理 Docker 要小心**（`prune -a` 会删所有未运行容器的镜像）。

**第五步：预防**
```bash
# 监控
df -h | awk 'NR>1 && $5+0 > 80 {print "⚠️", $6, $5}'
# 告警（Prometheus 的 node_filesystem_avail_bytes）
# 配额
quota / edquota / xfs_quota
# 日志轮转（logrotate 配置）
# 分离日志与数据分区（避免日志写满打挂数据库）⭐
# 应用限制日志大小（如 nginx access_log 的滚动）
```

**特殊场景**：
| 场景 | 说明 |
|---|---|
| **容器磁盘满** | 检查 `docker system df`、容器日志（`/var/lib/docker/containers/*/*-json.log` 默认**无限制**！）→ 配 `log-opts` 的 `max-size`/`max-file` ⭐ |
| **overlay 层写入** | 容器内写大量数据落在 `/var/lib/docker/overlay2` |
| **tmpfs 满** | `/dev/shm` 默认是内存的一半；容器里小（64MB），应用写 shared memory 会报 `No space` |
| **NFS 满** | 显示的是服务端容量 |
| **云盘扩容后没生效** | 要 `growpart` + `resize2fs`/`xfs_growfs`（见 RAID/LVM 一题） |
| **`/boot` 满** | 内核更新失败 → 清理旧内核（`dnf remove --oldinstallonly`、`apt autoremove --purge`）⭐ |

**排查口诀**：
1. **`df -h` + `df -i`** 一起看（空间 vs inode）。
2. **`du -xh --max-depth=1`** 逐层下钻。
3. **`lsof +L1`** 查"已删除但被占用"（**df/du 不一致的答案**）。
4. **`ncdu`** 交互式找大目录。
5. **清理前先确认**，日志用截断而非删除。
6. **Docker 的 json 日志无上限**是高发坑。""",
    ),
    (
        "Linux",
        "系统卡死,hung task",
        3,
        r"""系统负载很高但 CPU 空闲，或者系统完全无响应，你会怎么排查？""",
        r"""**先分清"卡"的两种形态**：

| 现象 | 可能原因 |
|---|---|
| **load 高、CPU 空闲** | **IO 等待 / D 状态进程**（最常见） |
| **系统完全无响应（SSH 都连不上）** | 内核死锁、OOM 抖动、存储彻底失效、中断风暴 |
| **响应极慢但能动** | 内存压力（swap 抖动）、锁竞争、单核被打满 |

**第一步：load 高但 CPU 空闲 → 找 D 状态进程** ⭐
```bash
uptime                       # load 与核数比较
cat /proc/loadavg
ps -eo pid,stat,wchan:30,comm | awk '$2 ~ /D/'      # D 状态进程与内核等待点 ⭐
ps -eo state,pid,ppid,comm | grep '^D'
# 内核栈（看卡在哪个函数）
cat /proc/<pid>/stack
```
- **`wchan`** 显示进程在内核里等待什么（如 `rpc_wait_bit_killable` = NFS 卡住）。
- **D 状态是"不可中断睡眠"**，`kill -9` **杀不掉**（要等 IO 返回或超时）。
- **常见来源**：NFS/网络存储不可达、磁盘故障、`fsync` 卡在坏盘、某些驱动的 bug。

**第二步：IO 层**
```bash
iostat -xz 1
#  await 很高 + %util 高 → 设备饱和
#  await 很高但 %util 低 → 网络存储/驱动问题
vmstat 1
#  b 列（阻塞进程数）持续 > 核数 → IO 瓶颈
cat /proc/pressure/io        # PSI：IO 压力指标 ⭐
cat /proc/pressure/cpu
cat /proc/pressure/memory
```
**PSI（Pressure Stall Information）** 是现代内核（4.20+）最有用的"系统是否被拖慢"指标：
```
some avg10=12.34 avg60=... total=...
```
- `some`：至少一个任务被拖慢的时间占比。**avg10 > 10% 就已经有问题**。

**第三步：内存压力与 swap 抖动**
```bash
free -h                        # available
vmstat 1                       # si/so 非 0 = 正在 swap ⭐
cat /proc/pressure/memory
dmesg -T | grep -i -E "oom|killed"
```
- **swap 抖动（thrashing）**：内存不足 + 频繁换入换出 → 系统像卡死。
- **解决**：加内存、减少工作集、调 `vm.swappiness`、限制应用内存。

**第四步：中断与软中断**
```bash
cat /proc/interrupts
cat /proc/softirqs
mpstat -P ALL 1               # 看 %irq/%soft 是否集中在某个核
```
- **中断风暴**（某个设备狂发中断）会让单核 100% 且系统响应变差。
- **原因**：故障网卡、硬件问题、驱动 bug。

**第五步：内核卡死/死锁**
```bash
dmesg -T | tail -100
journalctl -k -n 100
# 关键关键字
dmesg | grep -i -E "hung_task|soft lockup|hard lockup|NMI watchdog|BUG:|Oops|panic|blocked for more than"
```
| 关键字 | 含义 |
|---|---|
| **`task X blocked for more than 120 seconds`** | **hung task**：进程在 D 状态超过阈值（`kernel.hung_task_timeout_secs`） |
| **`soft lockup - CPU#N stuck for Xs`** | 内核代码在单核上跑了很久（软锁） |
| **`hard lockup`** / `NMI watchdog` | 中断被长时间关闭（硬锁，通常要重启） |
| **`BUG: unable to handle kernel paging request`** | 内核空指针/越界 |
| **`call trace` + `Oops`** | 内核崩溃（可能还能活，也可能 panic） |
| **`INFO: rcu_preempt detected stall`** | RCU 停顿（内核卡住） |
| **`Out of memory: Killed process`** | OOM |

**第六步：无法 SSH 登录时的应急手段** ⭐

**用 SysRq 键**（需要 `kernel.sysrq` 允许；云主机可用控制台的"发送 SysRq"）：
```bash
echo 1 > /proc/sys/kernel/sysrq        # 启用全部 SysRq
# 通过 /proc/sysrq-trigger（串口/控制台能敲时）
echo w > /proc/sysrq-trigger    # 显示所有 D 状态任务的栈 ⭐
echo t > /proc/sysrq-trigger    # 显示所有任务栈
echo m > /proc/sysrq-trigger    # 显示内存信息
echo l > /proc/sysrq-trigger    # 显示所有 CPU 的栈（看是否死锁）
echo s > /proc/sysrq-trigger    # 同步磁盘
echo u > /proc/sysrq-trigger    # 重新挂载为只读
echo b > /proc/sysrq-trigger    # **立即重启**（最后手段，可能丢数据）
# 记忆：REISUB（Raising Elephants Is So Utterly Boring）
# r=恢复键盘  e=发 SIGTERM  i=发 SIGKILL  s=同步  u=只读挂载  b=重启
```
> 用**串口控制台/IPMI/云控制台**才能敲这些。

**第七步：其它可能性**
| 现象 | 排查 |
|---|---|
| **文件句柄耗尽** | `ls /proc/<pid>/fd | wc -l`、`ulimit -n` |
| **`nf_conntrack` 表满** | `dmesg | grep conntrack`、`conntrack -C` vs `nf_conntrack_max` |
| **进程数/PID 耗尽** | `cat /proc/sys/kernel/pid_max`，是否有僵尸堆积 |
| **锁竞争** | `perf lock`、`cat /proc/lock_stat` |
| **文件系统只读**（磁盘错误触发 remount-ro） | `dmesg` 里的 `EXT4-fs error`、`mount | grep ro` |
| **磁盘坏道** | `smartctl -a /dev/sda`、`dmesg | grep -i "I/O error"` |
| **云主机被宿主机限制** | `top` 的 `st`（steal）列高 |
| **网络存储（NFS/云盘）不可达** | D 状态进程的 `wchan` 指向 `rpc_*` |

**排查顺序总结（"卡死"专用）**：
```
1. uptime / PSI / vmstat      → 是 CPU、IO 还是内存问题？
2. ps 找 D 状态               → IO/存储问题（最常见）
3. dmesg 找 hung_task/lockup  → 内核层面问题
4. iostat                     → 设备是否饱和
5. free + vmstat si/so        → 内存抖动？
6. 无法登录时用 SysRq (w/t/l)  → 拿栈信息
7. SysRq b                    → 最后手段重启
```

**预防与配置**：
```bash
# hung task 检测（默认 120 秒）
sysctl kernel.hung_task_timeout_secs=120
sysctl kernel.hung_task_panic=0        # 1 = 直接 panic（配合 kdump 抓现场）
# soft lockup 检测
sysctl kernel.softlockup_panic=1
kernel.softlockup_all_cpu_backtrace=1  # 打印所有 CPU 栈 ⭐
# 启用 SysRq（生产常用 1 或限制值 176）
sysctl kernel.sysrq=1
# kdump（内核崩溃时自动保存 vmcore）⭐
systemctl enable --now kdump
```
**kdump**：配置好后内核 panic 会自动保存 vmcore，可用 `crash` 工具分析 —— 这是排查"内核崩溃/卡死"的**唯一可靠手段**（生产必备）。

**实践建议**：
1. **load 高先找 D 状态进程**（80% 的"卡死"是 IO/存储问题）。
2. **`/proc/pressure/*` 是判断"系统是否被拖慢"的最佳单一指标**。
3. **生产开启 `kdump` + `hung_task` 告警 + PSI 监控**。
4. **NFS 用 `hard` 挂载会把进程钉在 D 状态**（改为 `soft` 或加 `intr` 更可控，但有数据风险）。
5. **定期演练"系统不可登录"的应急流程**（控制台、SysRq、重启脚本）。
6. **监控要覆盖 load、PSI、dmesg 关键字**（很多卡死是"悄悄地"发生的）。""",
    ),
    (
        "Linux",
        "systemd 依赖,target,服务依赖",
        2,
        r"""systemd 的 unit 依赖与启动顺序是怎么控制的？服务起不来怎么排查？""",
        r"""**依赖与顺序是两回事**（最容易混淆的点）：

| 指令 | 作用 |
|---|---|
| `Requires=A` | **强依赖**：A 失败则本单元也失败；A 停止则本单元也停 |
| `Wants=A` | **弱依赖**：A 失败不影响本单元（**推荐**） |
| `BindsTo=A` | 更严格的 Requires（A 消失则立即停本单元） |
| `PartOf=A` | 反向依赖：A 重启/停止时，本单元也跟着 |
| `After=A` / `Before=A` | **只定义启动顺序**，不建立依赖 ⭐ |
| `Conflicts=A` | 互斥（启动本单元会停 A） |
| `Requisite=A` | 要求 A 已启动（否则立即失败，但不会去启动 A） |

**关键：`Wants` 不等于 `After`**。
```ini
[Unit]
Wants=mysql.service
After=mysql.service      # ← 这两行通常要成对出现
```
- 只有 `Wants`：systemd **并行**启动两者（可能你的服务先起来，连不上 MySQL）。
- 只有 `After`：**如果 MySQL 没被别的地方拉起，它不会启动**。
- **所以"启动顺序 + 依赖"要分别写**。

**为什么不用 `Requires`**：`Requires` 会连带"停"和"失败传播"，容易造成级联失败。**系统服务的实践是 `Wants` + `After`**。

**Target（目标）**：

| Target | 对应旧运行级别 | 含义 |
|---|---|---|
| `poweroff.target` | 0 | 关机 |
| `rescue.target` | 1 | 单用户 |
| `multi-user.target` | 3 | **多用户无图形**（服务器）⭐ |
| `graphical.target` | 5 | 图形界面 |
| `reboot.target` | 6 | 重启 |
| `default.target` | — | 默认（通常软链到上面之一） |

```bash
systemctl get-default
systemctl set-default multi-user.target
systemctl isolate rescue.target        # 切换到某 target
systemctl list-dependencies multi-user.target
systemctl list-dependencies --reverse blog.service   # 谁依赖我
```

**Unit 状态与排查**：
```bash
systemctl status blog.service          # 关键信息：Active、Main PID、退出码、最后日志 ⭐
systemctl --failed                     # 所有失败单元 ⭐
systemctl list-units --type=service --all
systemctl list-unit-files --state=enabled
systemctl cat blog.service             # 完整配置（含 override 片段）
systemctl show blog.service            # 所有属性（含实际生效的值）
systemctl edit blog.service            # 创建 override 片段（推荐）
systemctl daemon-reload                # **改 unit 后必须执行** ⭐
journalctl -u blog.service -n 100 --no-pager
systemd-analyze verify blog.service    # 语法与依赖检查
```

**`ExecStart`/`ExecStop` 的坑**：
1. **必须用绝对路径**（systemd 不做 PATH 查找，除非 `Environment=PATH=...` 且用 `/bin/sh -c`）。
2. **`ExecStop` 默认先发 SIGTERM**；`KillMode=` 决定杀谁：
   - `control-group`（**默认**）：杀死 cgroup 内**所有**进程。
   - `process`：只杀主进程。
   - `mixed`：SIGTERM 给主进程，SIGKILL 给其余。
   - `none`：不杀（你负责）。
3. **`KillSignal`/`TimeoutStopSec`**：优雅退出的等待时间（默认 90s）。
```ini
KillSignal=SIGTERM
TimeoutStopSec=30
KillMode=mixed
```

**`Type=` 影响 `systemctl start` 何时返回**：
| Type | 何时认为"启动完成" |
|---|---|
| `simple`（默认） | `ExecStart` 的进程 fork 出来即算成功 ⚠️（**即使它马上崩溃**） |
| `exec` | `exec()` 成功后才算（比 simple 严格一点） |
| `forking` | 父进程退出（传统 daemon） |
| `oneshot` | `ExecStart` 执行完毕 |
| `notify` | 进程发 `sd_notify(READY=1)` ⭐ 最准确 |
| `dbus` | 拿到 D-Bus 名字 |
| `idle` | 等其他任务空闲 |

**`Type=simple` 的陷阱**：应用启动后立刻崩溃（如配置错），`systemctl start` 仍返回成功 → 加 `Restart=on-failure` + 检查 `status`。

**服务起不来的排查清单**：

| 症状 | 检查 |
|---|---|
| `status` 显示 `inactive (dead)` | 从未启动成功；看 `ExecStart` 路径、权限 |
| `status` 显示 `failed` + 退出码 | `journalctl -u` 看具体错误 |
| `code=exited, status=203/EXEC` | **`ExecStart` 路径不对或没有执行权限** ⭐ |
| `status=200/CHDIR` | `WorkingDirectory` 不存在 |
| `status=226/NAMESPACE` | 权限/命名空间问题（`ProtectSystem=` 等限制过严） |
| `status=1/FAILURE` | 应用自身退出码 1 |
| `Main process exited, code=killed, signal=KILL` | 被 OOM 杀 或 `KillMode` 杀了 |
| `Failed with result 'oom-kill'` | cgroup 内存限制（`MemoryMax=`） |
| `Address already in use` | 端口被占（`ss -lntp`）；可能上次没停干净 |
| `Permission denied` | `User=` 权限不足、文件属主、能力（`AmbientCapabilities=`/`CapabilityBoundingSet=`） |
| 一直 `activating`（卡住） | `Type=notify` 但应用没发通知；或 `TimeoutStartSec` 未到 |
| 循环重启 | `Restart=always` + 应用秒退 → `journalctl` 看真实原因 |

**示例：一个不易踩坑的服务定义**
```ini
[Unit]
Description=Blog Server
Documentation=https://example.com/docs
After=network-online.target mysql.service
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=5               # 60 秒内最多重启 5 次，防止无限重启

[Service]
Type=notify                      # 或 simple（按应用支持）
ExecStart=/usr/local/bin/task_server
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=5
User=blog
Group=blog
WorkingDirectory=/opt/blog
EnvironmentFile=-/etc/blog.env   # 前缀 - 表示文件不存在也不报错
Environment=LANG=en_US.UTF-8
LimitNOFILE=65535
MemoryMax=1G
CPUQuota=200%
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ReadWritePaths=/var/lib/blog
StandardOutput=journal
StandardError=journal
SyslogIdentifier=blog

[Install]
WantedBy=multi-user.target
```

**override 与 drop-in**：
```bash
systemctl edit blog.service            # 创建 /etc/systemd/system/blog.service.d/override.conf
```
```ini
# override.conf —— 只写要改的字段（同名字段会覆盖）
[Service]
Environment=LANG=zh_CN.UTF-8
```
**注意**：**同名字段的"重置"语义** —— 想清空某字段要写 `Field=`（空值）；多个 `Environment=` 会**累加**（不是覆盖）。

**依赖相关的调试**：
```bash
systemd-analyze critical-chain blog.service    # 启动关键路径与耗时 ⭐
systemd-analyze blame                          # 各服务启动耗时排行 ⭐
systemd-analyze plot > boot.svg                # 启动时序图
journalctl -b -u blog.service
systemctl list-dependencies blog.service --all
```

**实践建议**：
1. **`Wants` + `After` 成对使用**（不要只用 `Wants`）。
2. **改完务必 `daemon-reload`**。
3. **`systemctl edit` 创建 override**，不要直改发行版 unit。
4. **`Type=simple` 下要配 `Restart=on-failure` + `StartLimitBurst`** 防止无限重启。
5. **用 `LimitNOFILE` 而不是 `limits.conf`**（systemd 不读 PAM limits）⭐。
6. **`ProtectSystem=strict` 之类的加固常导致"权限不够起不来"**（`ReadWritePaths=` 要写清）。
7. **`PrivateTmp=yes`** 会让服务看不到 `/tmp`（调试时要注意）。
8. **日志走 journald**，`journalctl -u` 是最快的排查入口。""",
    ),
    (
        "Linux",
        "man,帮助文档",
        1,
        r"""Linux 下怎么查帮助？`man` 的章节是怎么划分的？""",
        r"""**`man` 的九个章节**：

| 章节 | 内容 | 例子 |
|---|---|---|
| **1** | 用户命令 | `man 1 ls` |
| **2** | 系统调用（syscall） | `man 2 open` |
| **3** | 库函数（C 标准库） | `man 3 printf` |
| **4** | 特殊文件（设备、`/dev`） | `man 4 null` |
| **5** | 文件格式与约定 | `man 5 fstab`、`man 5 crontab` ⭐ |
| **6** | 游戏与屏保 | — |
| **7** | 杂项（协议、概念、宏） | `man 7 tcp`、`man 7 signal`、`man 7 daemon` ⭐ |
| **8** | 系统管理命令 | `man 8 mount` |
| **9** | 内核例程 | — |

**同名冲突时必须指定章节**：
```bash
man open        # 默认第 1 章（命令）
man 2 open      # 系统调用
man 3 open      # 库函数（如果有）
man -a open     # 依次显示所有章节
man -k "pattern"       # 按关键字搜索（= apropos）⭐
apropos "copy files"   # 更强大（需要 mandb 索引）
whatis ls              # 一句话摘要
man -f ls              # = whatis
```

**`man` 的常用操作**：
| 键 | 作用 |
|---|---|
| `/pattern` | 向下搜索 ⭐ |
| `?pattern` | 向上搜索 |
| `n` / `N` | 下一个 / 上一个匹配 |
| `g` / `G` | 首 / 尾 |
| `q` | 退出 |
| `h` | man 自身的帮助 |
| `Space` / `b` | 翻页 |
| `m`（在某字母上） | 设置标记 |
| `''` | 返回上一个位置 |

**`man` 的段落结构**：
```
NAME            名称与一句话说明
SYNOPSIS        语法（[] 可选，| 二选一，... 重复）
DESCRIPTION     详细说明
OPTIONS         选项
EXIT STATUS     退出码
ENVIRONMENT     环境变量
FILES           相关文件
NOTES           备注（**很多坑写在这里**）⭐
BUGS            已知问题
EXAMPLES        示例（**最有用**）⭐
SEE ALSO        相关条目 ⭐（**看这个能形成知识网**）
```

**`--help` 与 `man` 的关系**：
```bash
cmd --help          # 快速看选项（GNU 风格）
cmd -h              # 有些命令用 -h
ls --help | less
# 注意：不是所有命令都有高质量的 --help
```

**其它帮助来源**：

| 来源 | 说明 |
|---|---|
| `/usr/share/doc/<pkg>/` | 发行版包的文档（含 README、示例配置）⭐ |
| `info <cmd>` | GNU info 格式（`coreutils` 的更详细文档） |
| `help <builtin>` | **bash 内建命令**的帮助（`man` 里没有！）⭐ |
| `type <cmd>` | 判断是内建、别名还是外部命令 ⭐ |
| `pkg-config --cflags lib` | 库的编译参数 |
| 程序的 `-v` / `--version` | 版本（决定文档该看哪一版） |
| `/etc/<app>/` 示例配置 | 常带注释 |
| `man 7 ascii` / `man 7 utf-8` | 编码相关 |
| `man perlre` | PCRE 正则（跨工具通用） |

**bash 内建命令**要这样查：
```bash
help cd
help -d          # 简短描述
help -m          # man 风格
man bash         # 巨大的一份（搜索 `^  builtin`）
compgen -b       # 列出所有内建命令
```

**常见"man 里找不到"的情况**：
| 找不到 | 原因 |
|---|---|
| `man cd` | **内建命令** → `help cd` |
| `man ```` | 语法符号 → `man 1 bash` 搜 |
| `man docker` | 新工具没装 man → `docker --help` |
| `man top` 内容怪 | 可能是别的 `top`；`man 1 top` |
| 只装了 `-dev` 包 | 库文档在 `-doc` 包 |
| `no manual entry` | `mandb` 索引没建 / man 包未装 |

**建立索引**：
```bash
sudo mandb            # 重建 whatis 数据库（apropos 依赖它）⭐
sudo makewhatis        # 老系统
man -w <cmd>           # 显示 man 文件路径（判断有没有装）
echo $MANPATH          # man 搜索路径
```

**`man` 的显示格式**：
```bash
man ls | col -b > ls.txt      # 去掉退格控制符（导出为纯文本）
man ls | cat                  # 用 cat 看（适合管道处理）
man --html=... ls             # 部分实现支持输出 HTML
```
**颜色**：`man` 用 `less` 显示，颜色由 `LESS_TERMCAP_*` 或 `MANPAGER` 控制：
```bash
export MANPAGER='less -R'
```

**高效查 man 的技巧**：
1. **先 `man -k <keyword>`** 找到正确的条目名。
2. **看 `EXAMPLES` 和 `SEE ALSO`**（最快理解与实际用法）。
3. **看 `NOTES`**（坑都在这）。
4. **`SYNOPSIS` 要会读**：`[]` 可选、`|` 二选一、`...` 可重复、**加粗是字面量**、*斜体*是占位符。
5. **想查"某个函数在哪个头文件"** → `man 3 func` 顶部的 `#include`。
6. **想查"某个概念"** → `man 7 <topic>`（`tcp`、`signal`、`socket`、`epoll`、`daemon`、`cgroups` 都有）⭐。

**其它参考**：
| 资源 | 用途 |
|---|---|
| `tldr <cmd>` | **示例优先**的简化手册（最好用）⭐ |
| `cheat <cmd>` | 命令行速查表 |
| `explainshell.com` | 解析命令的每个部分 |
| `cheat.sh`（`curl cht.sh/ls`） | 在线速查 |
| `grep` 源码树的 `Documentation/` | 内核文档 |
| `info coreutils 'ls invocation'` | GNU 工具的详细信息 |

**实践建议**：
1. **`tldr` 和 `man` 配合用**：`tldr` 快速上手，`man` 查细节。
2. **`man 7 tcp` 之类的"概念手册"价值极高**（比搜索引擎更准）。
3. **脚本里要检查命令是否有对应 man**（`man -w cmd >/dev/null`）。
4. **`help` 是查 bash 内建的第一步**（很多"man 里没有"的问题都源于此）。
5. **`/usr/share/doc` 里的示例配置**是配置服务的最快路径。""",
    ),
    (
        "Linux",
        "cgroup 限制,资源隔离",
        2,
        r"""怎么限制一个进程/服务/容器的 CPU 和内存？""",
        r"""**三种主要手段**：

| 手段 | 粒度 | 持久性 | 特点 |
|---|---|---|---|
| **`ulimit`** | 单进程（fd/栈/进程数） | 会话或 systemd | 简单的资源上限 |
| **systemd 的 `MemoryMax`/`CPUQuota`** | 服务（cgroup） | ✅ | **生产推荐**（声明式） |
| **直接操作 cgroup** | 任意进程组 | 需重建 | 最灵活 |
| **容器（`docker --memory/--cpus`）** | 容器 | ✅ | 本质是 cgroup |
| **`nice`/`cpulimit`** | 单进程 | 不持久 | 只调优先级，不硬限制 |
| **`chrt`（实时调度）** | 单进程 | 不持久 | 设置调度策略/优先级 |

**1. systemd（推荐）**
```ini
[Service]
# CPU：最多用 2 个核（200%）
CPUQuota=200%
# CPU：权重（相对份额，cgroup v2 是 1~10000）
CPUWeight=100
# 绑定到指定核
AllowedCPUs=0-3
# 内存硬上限
MemoryMax=1G
MemoryHigh=800M          # 软上限（超过会回收）
MemorySwapMax=0          # 禁止 swap
# IO
IOWeight=100
IOReadBandwidthMax=/dev/sda 50M
# 进程数
TasksMax=512
```
```bash
systemctl daemon-reload && systemctl restart svc
systemctl show svc -p MemoryMax -p CPUQuota
systemd-cgtop                     # 按 cgroup 看资源占用 ⭐
```

**2. cgroup v2 直接操作**
```bash
mount | grep cgroup2              # 确认是 v2
ls /sys/fs/cgroup/

mkdir /sys/fs/cgroup/mygroup
# 内存
echo 512M > /sys/fs/cgroup/mygroup/memory.max
echo 400M > /sys/fs/cgroup/mygroup/memory.high
# CPU（100000 = 1 个核；限制为 0.5 核 → 50000）
echo "50000 100000" > /sys/fs/cgroup/mygroup/cpu.max
# CPU 权重
echo 200 > /sys/fs/cgroup/mygroup/cpu.weight
# 绑定 CPU
echo "0-3" > /sys/fs/cgroup/mygroup/cpuset.cpus
echo "0"   > /sys/fs/cgroup/mygroup/cpuset.mems
# 进程数
echo 100 > /sys/fs/cgroup/mygroup/pids.max
# 加入进程
echo $$ > /sys/fs/cgroup/mygroup/cgroup.procs

# 查看用量
cat /sys/fs/cgroup/mygroup/memory.current
cat /sys/fs/cgroup/mygroup/memory.stat
cat /sys/fs/cgroup/mygroup/cpu.stat
cat /sys/fs/cgroup/mygroup/memory.events    # oom 次数 ⭐
```

**关键文件对照（v1 → v2）**：

| 功能 | v1 | v2 |
|---|---|---|
| 内存上限 | `memory/memory.limit_in_bytes` | `memory.max` |
| 内存软限 | `memory.soft_limit_in_bytes` | `memory.high` |
| 内存用量 | `memory.usage_in_bytes` | `memory.current` |
| CPU 配额 | `cpu/cpu.cfs_quota_us` + `period_us` | `cpu.max` |
| CPU 权重 | `cpu.shares`（1024 基准） | `cpu.weight`（100 基准） |
| 进程数 | `pids/pids.max` | `pids.max` |
| 设备访问 | `devices/devices.allow` | **eBPF**（v2 用 BPF 程序） |

**3. `docker` / `k8s`**
```bash
docker run --memory=512m --memory-swap=512m --cpus=1.5 \
           --cpuset-cpus=0-2 --pids-limit=200 nginx
docker stats                       # 实时占用 ⭐
docker inspect -f '{{.HostConfig.Memory}}' <c>

# k8s
# resources:
#   requests: { cpu: "500m", memory: "256Mi" }
#   limits:   { cpu: "1",    memory: "1Gi" }
```
**k8s 的 `requests`/`limits`**：
- `requests` 影响**调度**（选节点）与 QoS 等级。
- `limits` 通过 cgroup 强制。
- **CPU 超 limit** → 被限流（throttle，表现为延迟）；**内存超 limit** → **OOMKilled**。
- **`limits` 不设** → 可能吃光节点；**`requests` 不设** → 调度不准。

**注意 `memory.max` 包含 page cache**（这是"容器内存莫名超限"的常见原因）：
```bash
cat /sys/fs/cgroup/memory.stat | grep -E "^(anon|file|slab)"
# file 是 page cache，读大文件会顶到 memory.max
```

**CPU 限制的常见误解**：
1. **`CPUQuota=100%` = 1 个核**（不是"占满整机"）。
2. **限流（throttle）不是"降频"**：超限的进程会被**强制暂停到下一个 CFS 周期**（默认 100ms）→ **延迟抖动的来源**。
   ```bash
   cat /sys/fs/cgroup/<grp>/cpu.stat
   # nr_throttled / throttled_usec 高 → 被限流严重 ⭐
   cat /sys/fs/cgroup/<grp>/cpu.max.burst     # 允许的突发额度
   ```
3. **`cpuset`（绑核）与 `cpu.max`（配额）是两回事**：
   - `cpuset` 限制"能用哪些核"（可能造成核间负载不均）。
   - `cpu.max` 限制"用多少时间"（不限定具体核）。
4. **多线程程序被限流时延迟会变差**（因为线程可能同时被挂起）。

**内存限制的行为差异**：
| 设置 | 行为 |
|---|---|
| `MemoryMax`（`memory.max`） | **硬限**：超过则 **OOM kill**（cgroup 内选受害者） |
| `MemoryHigh`（`memory.high`） | **软限**：超过则**积极回收**（page cache → swap），拖慢但不杀 |
| `MemorySwapMax=0` | 禁止 swap（避免抖动，但也更容易 OOM） |
| 完全不设 | 用多少都行（会被整机 OOM killer 盯上） |

**推荐策略**：
- **设 `MemoryHigh` 为目标的 80%**（提前回收，避免突然 OOM）。
- **设 `MemoryMax` 硬限**（防止单个服务拖垮整机）。
- **配合 `MemorySwapMax=0`**（对延迟敏感的服务，避免 swap 抖动）。

**监控**：
```bash
systemd-cgtop                                  # 按 cgroup 实时
cat /sys/fs/cgroup/<grp>/memory.events         # low/high/max/oom 次数 ⭐
cat /sys/fs/cgroup/<grp>/cpu.stat              # 限流统计
# Prometheus（node_exporter 的 cgroup 采集 / cAdvisor）
# k8s: kubectl top pod / kubectl describe pod（看 OOMKilled 与 limits）
```

**实践建议**：
1. **服务用 systemd 的 `MemoryMax`/`CPUQuota`**（声明式、持久、有日志）。
2. **容器必须设 `limits`**（否则一个容器能吃光节点）。
3. **内存 limit 要留意 page cache**（读大文件会顶到限制）。
4. **CPU 限流会带来延迟抖动** → 延迟敏感服务**宁可不限 CPU**（或用 `cpuset` 绑核）。
5. **`memory.events` 是排查"容器为什么被杀"的第一手证据**。
6. **`ulimit` 与 cgroup 是互补的**（前者管进程级上限如 fd，后者管资源量）。
7. **不要设 `CPUQuota` 太低**（应用会因限流而"随机变慢"，很难定位）。""",
    ),
    (
        "Linux",
        "源码阅读,运维脚本",
        2,
        r"""写一个健壮的 Linux 运维脚本要注意什么？""",
        r"""**一个健壮的 bash 脚本模板**：

```bash
#!/usr/bin/env bash
set -Eeuo pipefail              # ⭐⭐⭐ 最重要的三行
#   -e  命令失败即退出
#   -u  使用未定义变量报错
#   -o pipefail  管道中任一环节失败即失败
#   -E  ERR trap 在子函数/shell 中也生效

IFS=$'\n\t'                     # 只按换行和制表符分词（避免空格踩坑）

# 出错时打印行号与调用栈
trap 'echo "[ERROR] line $LINENO: $BASH_COMMAND (exit $?)" >&2' ERR
trap 'cleanup' EXIT             # 无论怎么退出都清理

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_NAME="$(basename "$0")"

log()  { echo "[$(date '+%F %T')] $*" >&2; }
die()  { log "FATAL: $*"; exit 1; }

usage() { echo "Usage: $SCRIPT_NAME [-n] <args>"; exit 1; }

cleanup() {
    # 删除临时文件、释放锁、关闭 fd
    [[ -n "${TMPDIR_CREATED:-}" ]] && rm -rf "$TMPDIR_CREATED"
}
```

**核心要点**：

**1. `set -euo pipefail`**
- **`-e` 的例外**：`if cmd; then`、`cmd || true`、`! cmd` 里的命令失败**不会**导致退出（这是设计如此）。
- 想明确忽略某个失败：`cmd || true` 或 `if ! cmd; then ...; fi`。
- **子 shell 与函数**：`-e` 在函数里生效，但 `$(...)` 里的失败会传给外层（配合 `-E` 更可靠）。

**2. 引号（最经典的坑）**
```bash
# ❌ 文件名有空格就炸
for f in $(ls); do rm $f; done
# ✅
find . -maxdepth 1 -type f -print0 | while IFS= read -r -d '' f; do rm -- "$f"; done
rm -- "$file"

# ❌ 变量展开
rm -rf $dir/*            # 若 dir 为空 → rm -rf /*
# ✅
[[ -n "$dir" ]] || die "dir is empty"
rm -rf -- "${dir:?}/"*
```
**规则**：**变量一律加双引号** `"$var"`；**用 `--` 结束选项解析**（防止文件名以 `-` 开头）。

**3. 检查前置条件**
```bash
[[ $EUID -eq 0 ]] || die "must run as root"
command -v jq >/dev/null || die "jq not found"
[[ -f "$config" ]] || die "config not found: $config"
[[ -d "$target" ]] || die "not a directory"
for arg in "$@"; do [[ -n "$arg" ]] || die "empty argument"; done
```

**4. 危险操作的保护**
```bash
# 干跑模式
DRY_RUN=0
while getopts "n" opt; do case $opt in n) DRY_RUN=1;; esac; done
run() { if (( DRY_RUN )); then echo "[dry-run] $*"; else "$@"; fi; }

# 二次确认
read -r -p "Delete $target? [y/N] " ans
[[ "$ans" == [yY] ]] || exit 1

# 路径白名单
case "$target" in
    /data/*|/var/backup/*) ;;
    *) die "refuse to operate on $target" ;;
esac

# 防误删根目录
[[ "$target" != "/" && "$target" != "" ]] || die "refusing to delete /"
```

**5. 并发防重（flock）**
```bash
exec 9>/var/lock/"$SCRIPT_NAME".lock
flock -n 9 || die "another instance is running"
```
**这是 cron 任务必须做的**（见文件锁一题）。

**6. 日志与输出**
```bash
# 时间戳、级别、输出到 stderr
log() { printf '[%s] %s\n' "$(date +'%F %T')" "$*" >&2; }
# 重定向到文件并同时显示
exec > >(tee -a "$LOG_FILE") 2>&1
# 或用 logger 写 syslog
logger -t "$SCRIPT_NAME" "message"
```
**规范**：**正常数据输出到 stdout**（供管道消费），**日志与错误输出到 stderr**。

**7. 参数解析**
```bash
# 简单场景
while [[ $# -gt 0 ]]; do
    case "$1" in
        -n|--dry-run) DRY_RUN=1; shift ;;
        -f|--file)    FILE="${2:?missing value}"; shift 2 ;;
        -h|--help)    usage ;;
        --)           shift; break ;;
        -*)           die "unknown option: $1" ;;
        *)            POSITIONAL+=("$1"); shift ;;
    esac
done
set -- "${POSITIONAL[@]}"       # 恢复位置参数

# 复杂场景用 getopts（只支持短选项）
while getopts ":nf:h" opt; do :; done
```

**8. 临时文件**
```bash
# 安全创建
TMPDIR_CREATED="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_CREATED"' EXIT
# 不要用可预测的名字（/tmp/myfile，会被竞争攻击）
# 不要用 $$ 作临时文件名（可能被复用）
```

**9. 兼容性**
```bash
#!/bin/bash                     # 明确用 bash（不要用 /bin/sh，可能是 dash）
# 或用 #!/usr/bin/env bash（更可移植）
# 检查 bash 版本
[[ ${BASH_VERSINFO[0]} -ge 4 ]] || die "bash >= 4 required"
```
**常见不兼容**：`[[ ]]`（bash 专有）、数组、`${var^^}`（大小写转换，bash 4+）、`read -d`（bash 专有）。

**10. 测试与风格**
```bash
# shellcheck 静态检查（必装）⭐
shellcheck myscript.sh
# -x 追踪执行（调试）⭐
bash -x myscript.sh
# 语法检查
bash -n myscript.sh
# 单元测试
# bats-core / shunit2
```

**11. 幂等性**
- 脚本应该**可以重复执行而不产生副作用**（"再跑一次也没事"）。
- 检查存在性：`[[ -f x ]] || touch x`、`mkdir -p`、`ln -sfn`。
- 避免 `>>` 反复追加（改用检查或截断策略）。

**12. 其它实用技巧**
```bash
# 超时控制
timeout 30s long_cmd || die "timeout"
# 重试
for i in {1..3}; do cmd && break || sleep 2; done
# 并行
xargs -P 8 -I{} do_something {}
# 等待端口就绪
until nc -z localhost 8080; do sleep 1; done
# 时间测量
SECONDS=0; work; echo "took ${SECONDS}s"
# 数组安全遍历
for x in "${arr[@]}"; do echo "$x"; done
```

**反面示例（常见错误）**：
```bash
# ❌ 没有 set -e，前面的错误被忽略
# ❌ 变量不加引号，路径有空格就炸
# ❌ 用 ls 解析文件名
# ❌ for i in $(cat file)（按空白分词）
# ❌ rm -rf $dir/*（dir 为空时灾难）
# ❌ 不检查命令是否存在
# ❌ 用 /bin/sh 但写了 bash 语法
# ❌ 没有并发锁（cron 重叠执行）
# ❌ 硬编码路径/IP/密码（用环境变量或配置文件）
# ❌ 输出混进 stdout（破坏管道）
# ❌ 不记日志（出了问题无从追溯）
```

**实践建议**：
1. **第一行 `set -Eeuo pipefail`**，第二步 `shellcheck`。
2. **变量一律加引号**，用 `--` 结束选项。
3. **危险操作加 `--dry-run` + 路径白名单 + 二次确认**。
4. **cron 任务必加 `flock`**。
5. **日志到 stderr、数据到 stdout**。
6. **`trap EXIT` 做清理**。
7. **超 100 行考虑用 Python**（可测试性、错误处理、库生态都更好）。
8. **敏感信息走环境变量/`EnvironmentFile`，不要硬编码**（git 里尤其危险）。""",
    ),
    (
        "Linux",
        "inotify,文件监控",
        2,
        r"""怎么实时监控文件变化？`inotify` 有什么限制？""",
        r"""**`inotify`** 是内核提供的文件系统事件通知机制。

**命令行工具**：
```bash
inotifywait -m -r /etc \
  -e modify,create,delete,move,attrib \
  --format '%T %e %w%f' --timefmt '%F %T'

inotifywatch -t 60 -r /var/log      # 统计一段时间内的事件
```
**`inotifywait` 的常用事件**：
| 事件 | 含义 |
|---|---|
| `create` / `delete` | 创建/删除 |
| `modify` | 内容修改 |
| `attrib` | 属性（权限/时间）变化 |
| `move` / `moved_to` / `moved_from` | 移动/重命名 |
| `close_write` | 关闭可写打开（**"写完了"的可靠信号**）⭐ |
| `open` / `access` / `close_nowrite` | 打开/访问/关闭 |
| `delete_self` / `move_self` | 被监控对象本身被删/移 |

**编程（C）**：
```c
int fd = inotify_init1(IN_NONBLOCK | IN_CLOEXEC);
int wd = inotify_add_watch(fd, "/etc", IN_MODIFY | IN_CREATE | IN_DELETE);
// fd 是可读的 → 可以放进 epoll
struct inotify_event ev;
read(fd, &ev, sizeof ev);
```
**关键：`inotify` 的 fd 可以进 `epoll`**（与其它事件统一处理），这是它比轮询优雅的地方。

**⚠️ 核心限制（面试重点）**：

1. **`max_user_watches` 上限**（每个用户可监控的**目录/文件数**）：
```bash
cat /proc/sys/fs/inotify/max_user_watches      # 默认常为 8192（老系统更低）
cat /proc/sys/fs/inotify/max_user_instances    # 每个用户的 inotify 实例数
cat /proc/sys/fs/inotify/max_queued_events     # 事件队列长度
```
```bash
sudo sysctl -w fs.inotify.max_user_watches=524288
echo "fs.inotify.max_user_watches=524288" > /etc/sysctl.d/99-inotify.conf
```
**这是"编辑器/文件同步工具报 `ENOSPC`"的经典原因**（`ENOSPC` 通常让人以为是磁盘满，实际是 watch 用尽）。

2. **递归监控需要为每个子目录单独 watch**：
- 内核**不**提供递归监控 → 库（如 Linux 的 `fanotify` 或自实现）要遍历所有子目录加 watch。
- **目录多时 watch 会爆**（`node_modules` 是经典杀手）。

3. **事件队列会溢出**：队列满时产生 `queue overflow` 事件（**会丢失事件**），必须处理。

4. **事件不携带"谁改的"**：只知道哪个文件被改了，**不知道是哪个进程**（要审计得用 `fanotify` + `FAN_OPEN_PERM` 或 `audit`）。

5. **网络文件系统（NFS/CIFS）不可靠**：inotify 依赖本地内核，远端修改**不会产生事件**。

6. **符号链接/硬链接**：`inotify` 跟随/不跟随的语义要留意（`IN_DONT_FOLLOW`）。

7. **竞态**：`inotify` 只是"事后通知"，从事件发生到处理之间有窗口期（文件可能已被改两次）。

**替代/增强方案**：

| 方案 | 特点 |
|---|---|
| **`fanotify`**（2.6.36+） | 支持**整个挂载点**监控（无需逐个目录）⭐、可提供访问决策（权限控制）、可拿到 PID |
| **`epoll` + inotify** | 事件驱动程序的正确组合 |
| **`watch` 命令** | 轮询（简单但低效） |
| **`systemd .path` 单元** | 声明式文件监控（内部用 inotify）⭐ |
| **`rsync` + `--delete` 定时** | 轮询，对 NFS 有效 |
| **`auditd`** | 审计场景（含 PID、UID、可执行文件） |

**`systemd.path` 例子**：
```ini
# /etc/systemd/system/watch-config.path
[Path]
PathModified=/etc/myapp/config.yaml

[Install]
WantedBy=multi-user.target
```
```ini
# watch-config.service
[Service]
Type=oneshot
ExecStart=/usr/bin/systemctl reload myapp
```

**典型用途**：
1. **配置热重载**（文件变了就 reload）。
2. **文件同步**（`lsyncd`、`syncthing`）。
3. **构建工具**（`watchexec`、`entr`、`nodemon`）。
4. **安全监控**（敏感文件被改 → 告警）。
5. **日志收集**（`filebeat` 的 tail 用 inotify 感知轮转）。

**实用命令**：
```bash
# 监控某个目录的变化并触发动作
inotifywait -m -e close_write /etc/nginx/ | while read -r path action file; do
    nginx -t && systemctl reload nginx
done

# entr：文件变化就重跑命令
find . -name '*.c' | entr -c make

# 统计谁的 watch 用得多
find /proc/*/fd -lname anon_inode:inotify 2>/dev/null | \
  cut -d/ -f3 | sort | uniq -c | sort -rn | head
```

**实践建议**：
1. **先调大 `max_user_watches`**（生产标配，尤其跑 IDE/同步工具的机器）。
2. **递归监控用 `fanotify` 或成熟库**，不要自己遍历所有目录。
3. **必须处理队列溢出**（否则静默丢事件）。
4. **NFS 场景不要依赖 inotify**（改用轮询）。
5. **`close_write` 比 `modify` 更适合"文件写完了"**（避免读到写一半的内容）。
6. **注意监控范围**（监控 `/` 会瞬间用尽 watch）。""",
    ),
    (
        "Linux",
        "磁盘配额,quota",
        2,
        r"""Linux 的磁盘配额（quota）怎么配置？""",
        r"""**quota** 限制**用户或组**在文件系统上可用的**空间（blocks）**与**文件数（inodes）**。

**前提条件**：
1. **文件系统支持**：ext4（`usrquota`/`grpquota`）、XFS（`uquota`/`gquota`）、btrfs 支持。
2. **挂载时启用**（编辑 `/etc/fstab`）：
```
/dev/vg0/lv_data  /data  ext4  defaults,usrquota,grpquota  0 0
# XFS 用：defaults,uquota,gquota
```
```bash
mount -o remount /data          # 或 umount/mount
```

**ext4 的配置流程**：
```bash
# 1. 检查并创建配额文件
quotacheck -cugm /data          # -c 创建, -u 用户, -g 组, -m 不重挂载
# 生成 aquota.user / aquota.group

# 2. 启用配额
quotaon -avug                   # 全部启用
# 或 quotaon /data

# 3. 设置配额
edquota -u alice                # 交互式编辑
# 或批量
setquota -u alice 1048576 2097152 10000 20000 /data
#               软限空间  硬限空间  软限文件  硬限文件（KB / 个数）

# 4. 查看
quota -u alice                  # 用户自己看
repquota -a                     # 报表 ⭐
quota -v alice
```

**XFS 的配置（不同命令）**：
```bash
# 挂载时启用 uquota,gquota
xfs_quota -x -c 'report -h' /data
xfs_quota -x -c 'limit bsoft=1g bhard=2g isoft=10000 ihard=20000 alice' /data
xfs_quota -x -c 'report -h -u' /data
```

**软限 vs 硬限**：
| | 行为 |
|---|---|
| **软限（soft）** | **允许超过**，但有**宽限期（grace period，默认 7 天）**；期内必须降回软限以下，否则软限变成硬限 |
| **硬限（hard）** | **绝对上限**，超过则写入失败（`EDQUOT`） |
| **宽限期** | `edquota -t` 设置（默认 7 天） |

**用户侧**：
```bash
quota -s                        # 看自己的（-s 人类可读）
# Disk quotas for user alice (uid 1001):
#  Filesystem  blocks   quota   limit   grace   files   quota   limit  grace
#  /dev/sdb1   1234560  1048576 2097152   6days    1234   10000   20000
```

**配额 vs 其它限制方式**：

| 方式 | 粒度 | 说明 |
|---|---|---|
| **quota** | 用户/组 × 文件系统 | 传统，文件系统层面 |
| **XFS project quota** | 目录（项目） | **XFS 独有**，可以给"目录树"配额 ⭐ |
| **cgroup** | 进程组/容器 | 内存/CPU/IO（不是磁盘空间） |
| **容器 storage-opt** | 容器 | Docker 的 `--storage-opt size=10G`（需要 overlay2 + xfs pquota） |
| **应用层** | 应用内部 | 最灵活（如 S3 的存储桶限额） |

**XFS project quota 用在容器**：
```bash
# 挂载 xfs 时带 pquota
# /dev/sdb1 /var/lib/docker xfs defaults,pquota 0 0
xfs_quota -x -c 'project -s -p /var/lib/docker/overlay2/<id> 1001' /var/lib/docker
xfs_quota -x -c 'limit -p bhard=10g 1001' /var/lib/docker
```
**这是 Docker 的 `--storage-opt size=` 的底层机制**。

**容器场景的磁盘限制**：
```bash
docker run --storage-opt size=10G ...
# 注意：只对 overlay2 + xfs(pquota) 或 devicemapper 有效；
#      且**不含**容器日志（json 日志是另一个文件）
```

**排查配额问题**：
```bash
quota -u <user>                 # 当前用量
repquota -a                     # 全部
# 报错 EDQUOT（Disk quota exceeded）时：
#   1. quota -u 看是否真的超了
#   2. 注意 inode 配额（文件数）也可能超
#   3. 注意"已删除但被打开"的文件也计入（因为 inode 还在）
```

**实践建议**：
1. **服务器上给用户家目录加配额**（防止单个用户填满整盘）。
2. **XFS 的 project quota 更适合"目录级"限制**（配额粒度比用户/组更符合实际）。
3. **软限 + 宽限期**比硬限更友好（给用户缓冲时间）。
4. **注意 inode 配额**（海量小文件场景）。
5. **容器磁盘限制**推荐用 **cgroup 的 `io` 控制器 + 日志大小限制**，而不是 quota（更简单可靠）。
6. **`df` 不显示配额**，要用 `quota`/`repquota` 查。
7. **配额与 LVM 的区别**：LVM 是"固定大小的卷"（整个卷满了就满），quota 是"共享文件系统内的按人分配"。""",
    ),
    (
        "Linux",
        "bash,作业控制",
        1,
        r"""bash 的作业控制（job control）和常用快捷键有哪些？""",
        r"""**作业控制**：

```bash
sleep 100 &              # 后台运行（[1] 12345）
jobs -l                  # 列出作业（含 PID）⭐
fg %1                    # 把作业 1 调到前台
bg %1                    # 让暂停的作业在后台继续
kill %1                  # 按作业号杀
Ctrl+Z                   # 挂起当前前台作业（发 SIGTSTP）
Ctrl+C                   # 中断（发 SIGINT）
disown -h %1             # 让作业收不到 SIGHUP
wait                     # 等所有后台作业
wait $!                   # 等最后一个后台进程
```

**`nohup cmd &` vs `cmd &`**：见"后台运行"一题。

**bash 快捷键（`emacs` 模式默认）**：

| 快捷键 | 作用 |
|---|---|
| `Ctrl+A` / `Ctrl+E` | 行首 / 行尾 ⭐ |
| `Ctrl+B` / `Ctrl+F` | 左移 / 右移一个字符 |
| `Alt+B` / `Alt+F` | 左移 / 右移一个单词 |
| `Ctrl+U` | **删除到行首** ⭐ |
| `Ctrl+K` | **删除到行尾** ⭐ |
| `Ctrl+W` | 删除光标前一个单词 |
| `Alt+D` | 删除光标后一个单词 |
| `Ctrl+Y` | 粘贴（yank）刚删的内容 ⭐ |
| `Ctrl+L` | 清屏（= `clear`）⭐ |
| `Ctrl+R` | **反向增量搜索历史** ⭐⭐ |
| `Ctrl+G` | 取消当前搜索 |
| `Ctrl+P` / `Ctrl+N` | 上一条 / 下一条历史 |
| `Ctrl+D` | 输入结束（EOF）/ 退出 shell |
| `Ctrl+C` | 取消当前命令 |
| `Ctrl+Z` | 挂起当前命令 |
| `Alt+.` | 插入上一条命令的最后一个参数 ⭐ |
| `Ctrl+XX` | 在行首与光标位置切换 |
| `Tab` | 补全（连按两次列出候选）⭐ |
| `Alt+*` | 插入所有可能的补全 |

**历史与搜索**：
```bash
history                     # 全部历史
history 20                  # 最近 20 条
!!                          # 上一条命令 ⭐
!$                          # 上一条命令的最后一个参数 ⭐
!500                        # 第 500 条
!grep                       # 最近一条以 grep 开头的命令
sudo !!                     # 给上一条命令加 sudo ⭐⭐
^old^new                    # 把上一条命令里的 old 替换成 new ⭐
Ctrl+R                      # 反向搜索（再按 Ctrl+R 继续往前）
history -c / history -w     # 清空 / 写出
```
**`HISTCONTROL`**（`~/.bashrc`）：
```bash
export HISTCONTROL=ignoreboth      # 忽略重复与以空格开头的命令（**隐藏敏感命令**）⭐
export HISTSIZE=10000
export HISTFILESIZE=20000
export HISTTIMEFORMAT='%F %T '     # 显示时间
export HISTIGNORE='ls:cd:pwd:history'
```

**常用 bash 特性**：
```bash
# 花括号展开
echo {1..10}                # 1 2 3 ... 10
echo {a,b,c}{1,2}           # a1 a2 b1 b2 c1 c2
mkdir -p project/{src,test,docs}

# 命令替换
now=$(date +%s)
files=$(ls *.txt)

# 算术
echo $(( (1+2)*3 ))
(( i++ ))

# 流程控制
if [[ -f x && -n "$y" ]]; then ...; fi
for i in {1..5}; do ...; done
while read -r line; do ...; done < file
case "$x" in a|b) ...;; *) ...;; esac

# 参数的默认值/替换
${var:-default}             # var 未设或空 → default
${var:=default}             # 同时赋值
${var:?message}             # 未设则报错退出 ⭐（用于必填参数）
${var:+alt}                 # var 已设 → alt
${#var}                     # 长度
${var#prefix} / ${var##prefix}   # 删最短/最长前缀
${var%suffix} / ${var%%suffix}   # 删最短/最长后缀 ⭐
${var/old/new}              # 替换第一个
${var//old/new}             # 替换全部 ⭐
${var^^} / ${var,,}         # 大写 / 小写（bash 4+）

# 数组
arr=(a b c)
echo "${arr[0]}" "${#arr[@]}"
for x in "${arr[@]}"; do ...; done

# 关联数组（bash 4+）
declare -A m
m[key]=value
for k in "${!m[@]}"; do echo "$k=${m[$k]}"; done
```

**重定向进阶**：
```bash
cmd 2>&1 | tee log          # 合并 + 同时显示
exec 3>&1                   # 备份 stdout
exec > log                  # 重定向全部输出
cmd |& cat                  # = 2>&1 |
cmd > >(tee a) > >(tee b)   # 多路输出（进程替换）
diff <(cmd1) <(cmd2)        # 比较两个命令的输出 ⭐
```

**安全的 bash 设置**（`~/.bashrc` 或脚本头）：
```bash
set -o noclobber            # > 不覆盖已存在文件（防止误覆盖）
set -o ignoreeof            # Ctrl+D 不退出 shell
set -o vi                   # vi 模式（若习惯 vi）
shopt -s checkwinsize       # 自动更新 LINES/COLUMNS
shopt -s histappend         # 多终端历史追加（不覆盖）⭐
shopt -s cdspell            # cd 拼写纠错
shopt -s globstar           # 允许 ** 递归通配 ⭐
shopt -s nullglob           # 无匹配时展开为空（而非保留模式串）
```

**`bash_profile` vs `bashrc`**：
| 文件 | 何时加载 |
|---|---|
| `/etc/profile` | 登录 shell（所有用户） |
| `~/.bash_profile` / `~/.bash_login` / `~/.profile` | **登录 shell**（按顺序取第一个存在的） |
| `~/.bashrc` | **交互式非登录 shell**（每次开新终端） ⭐ |
| `/etc/bashrc` / `/etc/bash.bashrc` | 系统级 bashrc |

**常见配置**：
```bash
# ~/.bashrc 里通常有：
[ -f ~/.bash_profile ] && source ~/.bash_profile
# 这样登录 shell 和交互式 shell 都能拿到相同的环境
```

**实践建议**：
1. **`Ctrl+R` 和 `!!`/`sudo !!` 是效率神器**（配合 `HISTCONTROL=ignorespace` 避免记录敏感命令）。
2. **`HISTCONTROL=ignoreboth`** 能避免历史里出现重复与带密码的命令。
3. **`shopt -s histappend`** 让多个终端的 history 不互相覆盖。
4. **`Alt+.`** 快速复用上一条命令的参数。
5. **`${var:?msg}`** 是脚本里校验必填参数的最简写法。
6. **`set -o noclobber`** 防止 `>` 误覆盖文件（但要习惯 `>|` 强制覆盖）。
7. **找命令用 `type`/`which`/`command -v`**（`type` 最准，能识别别名与内建）。""",
    ),
    (
        "Linux",
        "iperf,网络性能",
        2,
        r"""怎么测网络的带宽和延迟？`iperf3` 怎么用？""",
        r"""**网络性能的四个维度**：
| 指标 | 含义 | 工具 |
|---|---|---|
| **带宽（throughput）** | 单位时间能传多少 | `iperf3`、`nuttcp` |
| **延迟（latency / RTT）** | 一来一回多久 | `ping`、`mtr`、`hping3` |
| **抖动（jitter）** | 延迟的波动 | `iperf3 -u`、`mtr` |
| **丢包（loss）** | 丢了多少 | `ping`、`mtr`、`nstat` |

**`iperf3` 基本用法**：
```bash
# 服务端
iperf3 -s                       # 默认 5201
iperf3 -s -p 5201 -D            # 后台

# 客户端（TCP 上行：客户端→服务端）
iperf3 -c <server>              # 默认 10 秒
iperf3 -c <server> -t 30        # 跑 30 秒 ⭐
iperf3 -c <server> -P 4         # 4 个并行流 ⭐（单流常吃不满带宽）
iperf3 -c <server> -R           # 反向（服务端→客户端）⭐
iperf3 -c <server> -bidir       # 双向（3.7+）
iperf3 -c <server> -w 512K      # 窗口大小（长肥管道要调大）⭐
iperf3 -c <server> -i 1         # 每秒报告一次

# UDP（测丢包与抖动）
iperf3 -c <server> -u -b 100M   # 目标带宽 100Mbps ⭐
iperf3 -c <server> -u -b 0      # 不限速（打满）— 慎用
iperf3 -c <server> -u -l 1200   # 包大小（贴近 VoIP 场景）

# 输出 JSON（便于脚本处理）
iperf3 -c <server> -J
```

**输出解读**：
```
[ ID]   Interval         Transfer     Bitrate         Retr
[  5]   0.00-10.00 sec   1.10 GBytes   941 Mbits/sec   12    sender
[  5]   0.00-10.00 sec   1.09 GBytes   938 Mbits/sec        receiver
```
| 字段 | 含义 |
|---|---|
| `Transfer` | 传输量 |
| `Bitrate` | **带宽（注意单位是 bits，不是 bytes）** |
| **`Retr`** | **TCP 重传次数**（非 0 说明网络有问题）⭐ |
| `Cwnd` | 拥塞窗口（`-i 1` 时可见） |
| UDP 的 `Lost/Total` | 丢包率 ⭐ |
| UDP 的 `Jitter` | 抖动 |

**为什么实测带宽远低于链路带宽？**

| 原因 | 排查 |
|---|---|
| **单流受 RTT 限制** | BDP = 带宽 × RTT；窗口不够 → 用 `-P` 多流或调 `-w` ⭐ |
| **CPU 瓶颈** | `top` 看 `si`（软中断）是否 100%；用 `-P` 多核分摊；开 RSS/RPS |
| **网卡/虚拟机限速** | 云主机的带宽上限；`ethtool` 看速率；云监控看是否到顶 |
| **MTU 问题** | 大包被分片/丢弃 → `ping -M do -s 1472` 测 |
| **丢包导致降窗** | `Retr` 高 → 拥塞控制降速 |
| **磁盘 IO** | `iperf3` 是内存到内存，但如果 `-F` 读文件就受磁盘限制 |
| **中断集中** | `mpstat -P ALL` 看是否单核 `si` 100% |

**其它网络测试工具**：

| 工具 | 用途 |
|---|---|
| `ping` | RTT、丢包 |
| `mtr` | **路径 + 每跳延迟/丢包**（比 traceroute 好）⭐ |
| `traceroute` | 路径 |
| `hping3` | 自定义包（TCP/UDP/ICMP）、防火墙测试、SYN flood 测试 |
| `nuttcp` | 另一个带宽测试（更接近 netperf） |
| `netperf` | 老牌，支持多种测试模式 |
| `sockperf` | 低延迟（微秒级）测量 |
| `qperf` | 通用性能测试 |
| `nc`（netcat） | 简单连通与数据管道测试 |
| `curl -w` | HTTP 各阶段耗时 ⭐ |

**`curl` 测 HTTP 性能**：
```bash
curl -o /dev/null -s -w '\nDNS: %{time_namelookup}s\nTCP: %{time_connect}s\nTLS: %{time_appconnect}s\nTTFB: %{time_starttransfer}s\nTotal: %{time_total}s\nSpeed: %{speed_download} B/s\n' \
     https://example.com
```
**这是定位"HTTP 慢在哪一段"的最快方法**（DNS / TCP / TLS / 服务处理）。

**延迟与抖动的测量**：
```bash
# 简单 RTT
ping -c 100 -i 0.2 <host> | tail -3          # 含 min/avg/max/mdev（mdev 是抖动）
# 更精确（需要 root）
mtr --report --report-cycles 100 <host>      # 每跳的丢包与延迟 ⭐
hping3 -S -p 80 -c 100 <host>                # TCP 层 RTT
sockperf ping-pong -i <server>                # 微秒级
```

**排查网络性能问题的顺序**：
1. **`ping` 测 RTT 与丢包**（先确认基础连通与质量）。
2. **`mtr` 定位是哪一跳丢包/延迟高**（区分本地/中间/对端）。
3. **`iperf3` 测纯带宽**（排除应用因素）。
4. **`ethtool -S <iface>` 看网卡错误计数**（`rx_errors`、`rx_dropped`）。
5. **`ss -ti` 看 TCP 内部状态**（`cwnd`、`rtt`、`retrans`、`bytes_retrans`）⭐
6. **`sar -n ETCP 1` / `nstat -az`** 看重传与错误统计。
7. **`mpstat -P ALL 1`** 看是否 CPU/软中断瓶颈。
8. **`tcpdump`** 抓包看 TCP 行为（窗口、重传、乱序）。

**`ethtool` 关键用法**：
```bash
ethtool eth0                     # 速率/双工/链路状态
ethtool -S eth0 | grep -i -E "error|drop|discard"
ethtool -k eth0                  # 卸载特性（TSO/GRO/GSO）
ethtool -K eth0 gro off          # 关闭 GRO（调试用）
ethtool -g eth0                  # 环形缓冲大小
ethtool -G eth0 rx 4096          # 调大环形缓冲（高流量下减少丢包）⭐
```

**`ss -ti` 的宝藏信息**：
```bash
ss -ti dst 10.0.0.1
# ... rtt:0.5/0.3 rttvar:... cwnd:10 ... retrans:0/0 ...
```
| 字段 | 含义 |
|---|---|
| `rtt` | 平滑 RTT / 方差 |
| `cwnd` | 拥塞窗口（小且不增长 = 有丢包或窗口受限） |
| `retrans` | 重传/总发送 |
| `bytes_retrans` | 重传字节数 |
| `unacked` | 未确认的段 |
| `pacing_rate` | 发送速率（BBR 的指标） |

**实践建议**：
1. **先 `ping`/`mtr` 再 `iperf3`**（分层定位）。
2. **`iperf3` 一定用 `-P 4` 及以上**（单流测不出真实带宽）。
3. **关注 `Retr`（重传）**，非 0 就是网络有问题。
4. **长肥管道要调 `-w`**（或开 `tcp_bbr` 拥塞控制）。
5. **云主机看云监控的带宽曲线**（可能是云平台的限速）。
6. **`ss -ti` 是"为什么 TCP 慢"的第一手证据**。
7. **`ethtool -S` 的 drop 计数**能发现环形缓冲不足（调 `-G` 解决）。""",
    ),
    (
        "Linux",
        "SELinux,AppArmor",
        2,
        r"""SELinux 是什么？为什么它会导致"权限明明对但就是访问不了"？""",
        r"""**SELinux（Security-Enhanced Linux）**是内核的 **MAC（强制访问控制）** 实现：即使传统权限（DAC，`rwx` + 属主）允许，**SELinux 策略仍可能拒绝**。

**DAC vs MAC**：
| | DAC（传统权限） | MAC（SELinux/AppArmor） |
|---|---|---|
| 依据 | 用户/组 + rwx | **安全上下文（label）** + 策略 |
| root | 通常全能 | **root 也会被拒绝** ⭐ |
| 配置 | 文件属性 | 全局策略 |

**安全上下文（context）**：
```bash
ls -Z /var/www/html/           # 查看文件的 context
ps -eZ | grep nginx            # 查看进程的 context
# system_u:object_r:httpd_sys_content_t:s0
#  │         │        │              └── MLS 级别
#  │         │        └───────────────── 类型（最重要）⭐
#  │         └────────────────────────── 角色
#  └──────────────────────────────────── 用户
```
**判定主要看"类型（type）"**：策略规定"什么类型的进程能访问什么类型的文件"。

**三种模式**：
```bash
getenforce                     # Enforcing / Permissive / Disabled
sestatus                       # 详细状态
setenforce 0                   # 切到 Permissive（临时，重启恢复）
setenforce 1                   # 切回 Enforcing
# 持久化：/etc/selinux/config 的 SELINUX=enforcing|permissive|disabled
```
| 模式 | 行为 |
|---|---|
| **Enforcing** | **拦截并记录**（拒绝生效） |
| **Permissive** | **只记录不拦截**（用于调试，"会拒绝的"都写日志） ⭐ |
| **Disabled** | 完全关闭（**需要重启**；且会改变文件系统上的标签行为） |

**典型排障流程（"权限对但访问不了"）**：

```bash
# 1. 确认是否是 SELinux
getenforce                       # Enforcing？
# 2. 看审计日志（关键）⭐
sudo ausearch -m AVC -ts recent
sudo grep AVC /var/log/audit/audit.log | tail
journalctl -t audit | grep AVC
# 3. 用 sealert 读懂（安装了 setroubleshoot 后）
sealert -a /var/log/audit/audit.log
# 4. 临时验证：切 Permissive
setenforce 0
# 如果问题消失 → 确认是 SELinux
```

**AVC 拒绝日志的样子**：
```
type=AVC msg=audit(...): avc:  denied  { read } for  pid=1234 comm="nginx"
  name="index.html" dev="sda1" ino=123
  scontext=system_u:system_r:httpd_t:s0
  tcontext=unconfined_u:object_r:user_home_t:s0      ← 类型不对！
  tclass=file permissive=0
```
**读法**：`httpd_t` 类型的进程试图读 `user_home_t` 类型的文件 → 被拒。**修法是把文件类型改成 `httpd_sys_content_t`**。

**常见场景与修法**：

**1. 网站目录放错位置**（把站点放在 `/home/user/www` 而不是 `/var/www`）：
```bash
# 办法 A（推荐）：用正确的目录（/var/www）
# 办法 B：改标签
semanage fcontext -a -t httpd_sys_content_t "/home/user/www(/.*)?"
restorecon -Rv /home/user/www          # 应用（必须！）⭐

# 查看当前的 fcontext 规则
semanage fcontext -l | grep httpd
```

**2. 非标准端口**（nginx 监听 8080）：
```bash
semanage port -l | grep http_port_t
semanage port -a -t http_port_t -p tcp 8080
semanage port -m -t http_port_t -p tcp 8080
```

**3. 服务需要连接数据库/网络**：
```bash
setsebool -P httpd_can_network_connect 1          # 持久（-P）⭐
setsebool -P httpd_can_network_connect_db 1
getsebool -a | grep httpd
semanage boolean -l | grep nis_enabled
```

**4. 家目录不可访问**：
```bash
setsebool -P httpd_enable_homedirs 1
```

**5. 生成自定义策略模块（兜底方案）**：
```bash
# 从 AVC 日志生成策略（谨慎，会放行这些操作）
audit2allow -a -M mypolicy
semodule -i mypolicy.pp
# 更推荐先看具体拒绝内容：
audit2why -a
```
**⚠️ 用 `audit2allow -M` 是最简单但也最粗暴的方式**（放行了所有被拒的操作）；**应先尝试"用正确的标签/布尔值"**。

**关键命令**：
```bash
# 文件标签
ls -Z, ps -Z, id -Z
chcon -t httpd_sys_content_t file          # 临时改（restorecon 会还原）
semanage fcontext -a -t TYPE "path(/.*)?"  # 永久规则
restorecon -Rv /path                       # 应用规则 ⭐
matchpathcon /path                         # 查"应该是什么标签"

# 端口
semanage port -l
semanage port -a -t http_port_t -p tcp 8080

# 布尔值
getsebool -a
setsebool -P name 1

# 策略模块
semodule -l
semodule -i x.pp / semodule -r x

# 排障
ausearch -m AVC -ts today
sealert -a audit.log
audit2why < avc.txt
```

**AppArmor（Ubuntu/SUSE 用）**：
- 与 SELinux 目标类似，但**机制不同**：基于**路径**（不是标签），**按程序**加载 profile。
```bash
aa-status                      # 状态
aa-enforce /etc/apparmor.d/usr.sbin.nginx
aa-complain /etc/apparmor.d/usr.sbin.nginx     # 只记录（= Permissive）
apparmor_parser -r /etc/apparmor.d/usr.sbin.nginx
journalctl -k | grep -i apparmor
dmesg | grep -i "apparmor.*denied"             # 拒绝日志
```
- **更易上手**（路径匹配直观），但**隔离粒度比 SELinux 粗**。
- Ubuntu 默认装 AppArmor，RHEL/CentOS 默认装 SELinux。

**对比**：
| | SELinux | AppArmor |
|---|---|---|
| 机制 | 标签（label） | 路径（path） |
| 粒度 | 细（类型、角色、用户、MLS） | 中 |
| 学习曲线 | 陡 | 缓 |
| 发行版 | RHEL/CentOS/Fedora | Ubuntu/SUSE |
| 对"移动文件" | 标签跟着文件（**要 restorecon**） | 路径不变即无影响 |

**实践建议**：
1. **不要直接 `setenforce 0` 或禁用 SELinux** —— 这是**降低系统安全性**来"解决问题"，应该修标签/布尔值。
2. **调试时用 `Permissive` + `ausearch`** 收集完整的拒绝列表，再统一修。
3. **`restorecon` 是"文件标签不对"的标准解法**（`chcon` 是临时的，会被还原）⭐。
4. **用标准目录**（`/var/www` 而非 `/home/x/www`）能避免 90% 的 SELinux 问题。
5. **`setsebool -P`** 解决"服务需要额外能力"（网络、家目录、数据库）。
6. **容器里**：SELinux 会给容器打标签（`:z`/`:Z` 挂载选项）；RHEL 系要留意。
7. **`audit2allow` 是兜底**，但**务必看清它放行了什么**（可能是提权漏洞）。
8. **`Permissive` 模式是"只记录不拒绝"，非常适合先观察再收紧**。""",
    ),
    (
        "Linux",
        "chroot,隔离",
        2,
        r"""`chroot` 是什么？它能提供安全隔离吗？""",
        r"""**`chroot`** 把进程的根目录（`/`）改成指定目录，进程就只能看到该目录下的文件。

```bash
chroot /newroot /bin/bash
chroot --userspec=user:group /newroot /bin/sh
```
**编程接口**：`chroot() + chdir("/")`（**必须 chdir**，否则工作目录还在旧根之外）。

**典型用途**：
1. **修复系统**：从 Live CD 启动后 `chroot` 进受损系统，重装 GRUB/内核、改配置。
2. **构建/打包**：在干净的根文件系统里构建，避免污染宿主。
3. **测试软件兼容性**：不同发行版的用户态环境。
4. **服务隔离（历史上）**：FTP 服务器把用户限制在家目录（**现在已不推荐仅靠 chroot**）。
5. **容器的基础**：Docker 等会做 `pivot_root`（比 chroot 更彻底）。

**⚠️ 关键结论：`chroot` 不是安全边界！**

**为什么**：
1. **root 可以逃逸**：
```c
// 经典逃逸：在 chroot 目录外保留一个 fd，然后 fchdir 出去
mkdir /tmp/escape; chroot /jail; chdir("/");
// 若 chroot 之前就打开了外层目录的 fd：
fchdir(outer_fd); chroot(".");        // 逃出去
```
2. **`chroot` 不隔离其它资源**：
   - 进程仍共享**同一套 PID/网络/用户/IPC**（`ps` 能看到外面的进程，能 `kill`，能连网络）。
   - 没有 CPU/内存限制。
3. **特权操作仍可用**：能加载内核模块、改系统时钟、访问设备（`/dev` 若可见）。
4. **只有一次性的路径限制**（不是持续的强制访问控制）。

**真正的隔离方案**：
| 方案 | 隔离强度 | 说明 |
|---|---|---|
| `chroot` | 最弱 | 仅改根目录 |
| **namespaces** | 强 | PID/NET/MNT/USER/IPC/UTS 隔离（容器的基础）⭐ |
| **cgroups** | — | 资源限制（与 namespace 配合） |
| **seccomp** | 强 | 系统调用过滤 |
| **capabilities** | 中 | 细粒度权限 |
| **SELinux/AppArmor** | 强 | MAC |
| **容器（Docker）** | 中强 | namespace + cgroup + capabilities + seccomp |
| **gVisor** | 很强 | 用户态内核 |
| **KVM 虚拟机** | 最强 | 硬件虚拟化 |

**`pivot_root` vs `chroot`**：
- `pivot_root` 把旧根**移走**并卸载，是"真正换根"。
- **容器运行时用 `pivot_root`**（配合 mount namespace），比 `chroot` 更难逃逸。

**`chroot` 的实用细节**：

**缺少库文件会导致程序起不来**：
```bash
# 把需要的动态库拷进去
ldd /bin/bash
for lib in $(ldd /bin/bash | awk '{print $3}' | grep '^/'); do
    mkdir -p "/newroot$(dirname "$lib")"
    cp "$lib" "/newroot$lib"
done
# 或一次拷全
for f in /bin/bash /bin/ls /usr/bin/env; do
    cp --parents "$f" /newroot
    ldd "$f" | awk '{print $3}' | grep '^/' | while read -r l; do cp --parents "$l" /newroot; done
done
# /dev 需要（设备文件）
mknod /newroot/dev/null c 1 3
```

**工具**：
| 工具 | 用途 |
|---|---|
| `chroot` | 基本换根 |
| `debootstrap` | 构建 Debian/Ubuntu 根文件系统 ⭐ |
| `dnf --installroot=` | 构建 RHEL 系根文件系统 ⭐ |
| `arch-chroot` | Arch 的封装（自动挂载 /proc /sys /dev） |
| `proot` | **无需 root** 的 chroot（用户态 syscall 拦截） |
| `bwrap`（bubblewrap） | 轻量沙箱（flatpak 用），比 chroot 安全 |
| `unshare` | 手工创建 namespace |
| `systemd-nspawn` | 基于 systemd 的轻量容器 |
| `firejail` | 应用沙箱（含 seccomp） |

**修复系统时的标准流程**：
```bash
# 从 Live 环境
mount /dev/sda2 /mnt
mount /dev/sda1 /mnt/boot
mount --bind /dev  /mnt/dev
mount --bind /dev/pts /mnt/dev/pts
mount --bind /proc /mnt/proc
mount --bind /sys  /mnt/sys
mount --bind /run  /mnt/run          # 现代系统需要
chroot /mnt /bin/bash
# 在 chroot 里工作
grub-install /dev/sda && update-grub
exit
umount -R /mnt
```
**必须 bind mount `/dev`、`/proc`、`/sys`** —— 否则很多命令（`grub-install`、`apt`）会失败。

**实践建议**：
1. **`chroot` 只用于"换根做运维"**（修复、构建），**不要当作安全隔离**。
2. **需要隔离用 namespace（`unshare`/`bwrap`/容器）**；需要限制资源用 cgroup。
3. **修复系统时务必 bind mount `/dev`、`/proc`、`/sys`、`/run`**，退出后 `umount -R`。
4. **`ldd` 检查依赖库**（chroot 里"命令找不到"通常是缺库或缺 `/dev`）。
5. **`arch-chroot`/`systemd-nspawn` 比裸 `chroot` 省事**。
6. **不要把 `chroot` 当作"容器"**（它不是 —— 没有 namespace、没有 cgroup、root 可逃逸）。
7. **`proot` 可在无 root 权限时模拟**（但性能有损，且依赖 ptrace）。""",
    ),
    (
        "Linux",
        "PATH,环境变量,安全",
        2,
        r"""环境变量是怎么工作的？`PATH` 有什么安全陷阱？""",
        r"""**环境变量**是"进程私有的键值对"，通过 `fork`/`exec` **继承给子进程**（不是全局的）。

**查看与设置**：
```bash
env                        # 全部
printenv PATH
echo "$PATH"
export VAR=value           # 设置并导出给子进程 ⭐
VAR=value cmd              # 只对这条命令生效 ⭐
unset VAR
env -i cmd                 # 清空所有环境变量运行
env -u PATH cmd            # 移除某个变量
```
**`export` 与不导出的区别**：
```bash
X=1              # shell 变量（子进程看不到）
export X=1       # 环境变量（子进程能看到）
```
**注意**：**shell 变量改了不会影响父进程**（`bash` 里的 `export` 不会改变调用它的那个 shell 的环境）。

**`PATH` 的解析**：
```bash
echo "$PATH"               # /usr/local/bin:/usr/bin:/bin:...
type ls                    # 判断是不是别名/内建/外部
command -v ls              # 只找外部命令路径
which -a ls                # 所有匹配（可能有多个）
```
**查找规则**：**从左到右**，第一个匹配的先执行。**当前目录不在 PATH 里**（出于安全），所以要运行当前目录的程序必须写 `./prog`。

**`PATH` 常见坑**：

1. **`PATH` 被覆盖而不是追加**：
```bash
PATH=/new/path             # ❌ 丢失了原来的所有路径
export PATH="/new/path:$PATH"   # ✅ 追加
export PATH="$PATH:/new/path"   # ✅ 追加到末尾
```
2. **`.` 或空条目在 PATH 里**（`PATH=.:$PATH`）→ 任意目录下的恶意程序可被"意外执行"（历史漏洞）。
3. **`~/.bashrc` 里反复 `export PATH=$PATH:...`** → 每次 source 都追加一次 → `PATH` 越来越长（用去重或只在未包含时追加）。

**安全陷阱**：

**1. `sudo` 与环境变量**：
- `sudo` **默认重置环境**（`env_reset`），只保留白名单（`secure_path`）。
- `sudo PATH=... cmd` **不会**改变实际使用的 PATH（被 `secure_path` 覆盖）。
- 配置 `env_keep` 要非常小心（保留 `LD_PRELOAD`、`PYTHONPATH` 是提权路径）⭐

**2. `LD_PRELOAD`/`LD_LIBRARY_PATH`**
- 见前文：**SUID 程序会忽略它们**（安全设计），但配置不当（`sudo` 保留、`setcap` 程序）就危险。
- **不要全局设置 `LD_LIBRARY_PATH`**（影响所有程序、破坏顺序）。

**3. `IFS` 注入**：
- 若脚本用 `$IFS` 分割且环境被污染，可导致命令注入。

**4. 未加引号的环境变量**：
```bash
# ❌ 环境变量含空格/通配符时会展开
rm -rf $DIR/*
# ✅
rm -rf -- "${DIR:?}"/*
```

**5. `BASH_ENV`/`ENV` 注入**：
- `BASH_ENV` 指定非交互式 bash 启动时执行的脚本 → 可注入代码。

**6. `PATH` 劫持（提权路径）** ⭐
```bash
# 若服务脚本里这样写（没有绝对路径）：
#!/bin/bash
tar -czf /backup/x.tar.gz /data       # 依赖 PATH

# 而 cron 的 PATH 可能包含攻击者可写目录 → 攻击者放一个假的 tar
```
**修复：脚本里用绝对路径**（`/usr/bin/tar`）或**开头设置安全的 PATH**：
```bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
```

**7. `~/.bashrc` 被劫持**：
- 若攻击者能写某个用户的 `~/.bashrc`，则该用户每次登录都会执行恶意代码。
- **家目录权限要严**（`chmod 700 ~`）。

**环境变量的加载顺序（bash 登录 shell）**：
```
/etc/profile
  → /etc/profile.d/*.sh
  → ~/.bash_profile（或 ~/.bash_login 或 ~/.profile，取第一个存在的）
      → 通常 source ~/.bashrc
          → /etc/bashrc（/etc/bash.bashrc）
```
**非登录交互式 shell**：只加载 `~/.bashrc`。
**非交互式 shell**（脚本）：只加载 `BASH_ENV`（若设置）。
**systemd 服务**：**不读以上任何文件**！只有：
- unit 里的 `Environment=` / `EnvironmentFile=`
- `DefaultEnvironment=`（`/etc/systemd/system.conf`）
- `/etc/environment`（PAM 的 `pam_env` 读取，**但 systemd 服务不经过 PAM**）

**这也是"cron/systemd 里跑脚本找不到命令/环境变量不对"的根因。**

**推荐的配置组织**：
```bash
# /etc/profile.d/myapp.sh（系统级，所有用户）
export PATH="/opt/myapp/bin:$PATH"
export MYAPP_HOME=/opt/myapp

# /etc/environment（简单 KEY=VALUE，无 shell 语法）
MYAPP_HOME=/opt/myapp
LANG=en_US.UTF-8

# systemd 服务
[Service]
EnvironmentFile=/etc/myapp/env
Environment=LANG=en_US.UTF-8
```

**排查环境变量问题**：
```bash
# 看进程实际的环境变量 ⭐
cat /proc/<pid>/environ | tr '\0' '\n'
sudo strings /proc/<pid>/environ | grep PATH

# 看服务的环境
systemctl show myapp -p Environment -p EnvironmentFiles
systemd-run --pty --property=Environment=FOO=bar bash   # 测试

# 排查 PATH 问题
env -i /bin/bash --noprofile --norc -c 'echo $PATH'     # 干净环境
strace -f -e trace=execve ./script | grep PATH          # 看它执行了什么
```

**实践建议**：
1. **脚本开头设置安全的 `PATH`**（或全部用绝对路径）。
2. **追加而非覆盖**：`export PATH="$PATH:/new"`。
3. **cron/systemd 里显式设置环境变量**（不要依赖 shell 配置）⭐。
4. **服务用 `EnvironmentFile=`**（文件权限 `600`，不放 git）。
5. **不要全局设 `LD_LIBRARY_PATH`/`LD_PRELOAD`**。
6. **`sudo` 的 `env_keep` 要最小化**（尤其别留 `LD_*`、`PYTHONPATH`、`PERL5LIB`）。
7. **家目录与脚本文件权限要严**（防 `~/.bashrc` 劫持）⭐。
8. **敏感信息不要放环境变量**（`/proc/<pid>/environ` 同用户可读；`ps eww` 也可能泄露）→ 用文件（权限 600）+ 读取。
9. **用 `env -i` 复现"干净环境"的问题**。
10. **`type` 而不是 `which`**（`type` 能看到别名和内建，更准确）。""",
    ),
    (
        "Linux",
        "patch,diff,补丁",
        2,
        r"""`diff` 和 `patch` 怎么用？打补丁失败怎么办？""",
        r"""**`diff` 生成补丁**：
```bash
diff -u old.c new.c > change.patch        # 统一格式（unified，最常用）⭐
diff -u old.c new.c | tee change.patch
# 递归目录
diff -ruN old_dir/ new_dir/ > dir.patch   # -r 递归, -N 把新文件当空文件 ⭐
# -N 很关键：否则新增文件不会出现在补丁里
```
**`-u` 上下文格式**：
```diff
--- old.c	2026-01-01
+++ new.c	2026-01-02
@@ -1,5 +1,6 @@                    ← 位置 (-原文件起始行,行数 +新文件起始行,行数)
 int main() {
-    printf("old\n");             ← - 删除的行
+    printf("new\n");             ← + 新增的行
+    return 0;
     return 0;                    ← 空格开头 = 上下文（未变）
 }
```

**`patch` 应用补丁**：
```bash
patch -p1 < change.patch          # -p1 去掉路径的第一层 ⭐
patch -p0 < change.patch          # 路径完全对应
patch -p2 < change.patch
patch -R < change.patch           # 反向（撤销补丁）⭐
patch --dry-run -p1 < change.patch  # 试运行（不实际改）⭐
patch -b -p1 < change.patch       # 备份原文件（.orig）
patch -d /path/to/src -p1 < change.patch   # 在指定目录应用
```

**`-pN` 的含义**：去掉路径的前 N 层。
```
--- a/src/main.c
+++ b/src/main.c
patch -p1  → src/main.c      （去掉 "a/"）
patch -p0  → a/src/main.c
```

**打补丁失败的常见原因与解决**：

| 报错 | 原因 | 解决 |
|---|---|---|
| `Hunk #1 FAILED at 10` | 上下文不匹配（源码已改动/版本不同） | 用 `.rej` 文件手工合并；或用 `fuzz` |
| `Reversed (or previously applied) patch detected` | 已经打过 / 打反了 | 加 `-R` 或跳过 |
| `can't find file to patch` | 路径不对 | 调 `-pN` 或 `-d` 指定目录 |
| `malformed patch` | 补丁文件损坏（邮件客户端改行尾） | 检查 CRLF（`dos2unix`） |
| 部分成功 | 有些 hunk 成功有些失败 | 看 `*.rej`（未应用部分）与 `*.orig`（原始文件） |

**处理失败**：
```bash
# patch 会留下：
#   file.rej   —— 无法应用的 hunk
#   file.orig  —— 原始文件（若有 -b）
cat file.rej                # 看哪些没应用
# 手工合并后删除 .rej
find . -name '*.rej' -delete
```

**`git` 与补丁**：
```bash
git diff > change.patch                  # 生成
git diff --staged > change.patch         # 已暂存的
git format-patch -1 HEAD                 # 带提交信息的补丁（邮件格式）⭐
git apply change.patch                   # 应用（不创建提交）
git apply --check change.patch           # 只检查能否应用 ⭐
git apply -3 change.patch                # 三方合并（更容错）⭐
git am 0001-*.patch                      # 应用邮件格式补丁（保留提交信息与作者）⭐
git am --abort                           # 失败后放弃
```

**`git apply` vs `patch`**：
- `git apply` 更严格（默认不容许 fuzz），但支持 `-3`（三方合并）与索引集成。
- `patch` 更宽松（默认允许一些 fuzz 与偏移）。
- **在 git 仓库里优先 `git apply`**（能追踪、能撤销）。

**其它 diff 用法**：
```bash
diff -y a b                 # 并排显示 ⭐
diff -w a b                 # 忽略空白差异
diff -i a b                 # 忽略大小写
diff -q a b                 # 只报告"是否不同"
diff -r dir1 dir2           # 比较目录
diff <(sort a) <(sort b)    # 比较命令输出（进程替换）⭐
vimdiff a b                 # 可视化对比 ⭐
meld a b / kdiff3           # GUI 对比
```
**`colordiff`**：给 `diff` 上色（或在 git 里配 `color.diff`）。

**`git diff` 的常用形态**：
```bash
git diff                    # 工作区 vs 暂存区
git diff --staged           # 暂存区 vs HEAD
git diff HEAD               # 工作区 vs HEAD
git diff branch1..branch2
git diff --stat             # 摘要
git diff -w                 # 忽略空白
git diff --word-diff         # 词级对比
```

**`comm`（比较两个已排序文件）**：
```bash
comm -12 a.txt b.txt        # 共同行（交集）⭐
comm -23 a.txt b.txt        # 只在 a（差集）
comm -13 a.txt b.txt        # 只在 b
# 需要先排序（LC_ALL=C sort 更快）
```

**`cmp`（二进制比较）**：
```bash
cmp file1 file2             # 第一个不同的字节位置
cmp -l file1 file2 | head    # 列出所有差异
# 对比文件是否一样（含二进制）
md5sum file1 file2 / sha256sum
```

**实用场景**：
```bash
# 1. 生成配置文件差异补丁（部署时用）
diff -u /etc/nginx/nginx.conf.bak /etc/nginx/nginx.conf > nginx.patch

# 2. 备份"当前状态"，之后恢复
diff -ruN /etc /etc.bak > etc.patch
patch -p1 -d / < etc.patch    # 恢复

# 3. 打上游补丁（开源项目）
wget https://example.com/fix.patch
cd project && patch -p1 --dry-run < ../fix.patch    # 先试 ⭐
patch -p1 < ../fix.patch

# 4. 撤销
patch -R -p1 < fix.patch

# 5. 查看补丁内容（不打）
less change.patch
git apply --stat change.patch       # 只看影响的文件与行数 ⭐
```

**实践建议**：
1. **`--dry-run` / `--check` 先验证**（打补丁前必做）⭐。
2. **`patch -b` 保留 `.orig` 备份**（失败可回滚）。
3. **`-pN` 要与补丁的路径层级匹配**（看 `---`/`+++` 行的开头）。
4. **在 git 仓库里优先 `git apply -3` 或 `git am`**。
5. **补丁文件要确保行尾是 LF**（`dos2unix`）。
6. **失败的 `.rej` 要手工合并**（不要直接删了当成功）。
7. **生成补丁用 `-ruN`**（递归 + 处理新文件）。
8. **`diff -u` 比默认格式更易读、更容错**（默认要 `-c`/`-u`）。""",
    ),
    (
        "Linux",
        "硬件信息,监控",
        1,
        r"""怎么查看服务器的硬件信息（CPU/内存/磁盘/网卡/主板）？""",
        r"""**CPU**：
```bash
lscpu                       # 最全面（架构、核数、缓存、NUMA、频率）⭐
lscpu | grep -E "Model name|Socket|Core|Thread|MHz|NUMA"
cat /proc/cpuinfo | grep -E "model name|physical id|core id|flags" | head
nproc                       # 逻辑核数
nproc --all
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq   # 当前频率
cat /sys/devices/system/cpu/online
cpuid                       # 详细信息（需安装）
```
**关键解读**：
- `Socket(s)`：物理 CPU 数。
- `Core(s) per socket`：每颗 CPU 的物理核。
- `Thread(s) per core`：**每核线程数（2 = 开了超线程）**。
- **物理核数 = Socket × Core per socket**（这是判断"该开多少并行"的依据，不是 `nproc`）。

**内存**：
```bash
free -h
cat /proc/meminfo
dmidecode -t memory         # **物理内存条信息（型号/频率/插槽）** ⭐
dmidecode -t memory | grep -E "Size|Speed|Locator|Manufacturer" | head -20
lshw -class memory
# NUMA 分布
numactl --hardware
```
**`dmidecode` 需要 root**（读 SMBIOS）。

**磁盘**：
```bash
lsblk                       # 块设备树（最直观）⭐
lsblk -d -o NAME,SIZE,ROTA,MODEL,SERIAL
# ROTA=1 机械盘，ROTA=0 SSD
fdisk -l / parted -l
blkid
df -hT                      # 文件系统与类型
smartctl -a /dev/sda        # **SMART 健康、通电时长、错误计数** ⭐
cat /sys/block/sda/queue/rotational      # 1=HDD 0=SSD
nvme list                   # NVMe 设备（需 nvme-cli）
```

**网卡**：
```bash
ip -br link                 # 接口概览 ⭐
ip -br addr
lspci | grep -i ethernet
ethtool eth0                # 速率/双工/驱动
ethtool -i eth0             # 驱动与固件版本
ethtool -S eth0 | head -20  # 统计
lshw -class network
```

**主板/BIOS**：
```bash
dmidecode -t system         # 厂商/型号/序列号 ⭐
dmidecode -t bios           # BIOS 版本与日期
dmidecode -t baseboard      # 主板
dmidecode -t chassis
lshw -short                 # 硬件总览 ⭐
hwinfo --short              # 另一套（需安装）
```

**PCI/USB 设备**：
```bash
lspci                       # 所有 PCI 设备
lspci -v / lspci -vv        # 详细
lspci -nn                   # 显示设备 ID
lspci | grep -i -E "vga|3d" # 显卡
lsusb
lsusb -t                    # 树形结构
```

**综合工具**：
| 工具 | 特点 |
|---|---|
| **`lshw`** | 硬件总览（可输出 HTML/JSON）⭐ |
| **`hwinfo`** | 最详细（SUSE 系） |
| **`inxi -F`** | **一行装好、输出友好**（推荐）⭐ |
| `neofetch`/`fastfetch` | 炫酷的概览（含系统信息） |
| `hardinfo` | GUI |
| `nmon` | 交互式性能监控 |
| `sosreport` | 收集诊断信息（红帽支持用） |

```bash
inxi -F          # 完整硬件摘要
inxi -C          # CPU
inxi -M          # 主板/BIOS
inxi -D          # 磁盘
inxi -N          # 网卡
inxi -G          # 显卡
```

**运行状态监控**：
```bash
uptime                      # 负载与开机时长
who -b                      # 上次启动时间
last reboot                 # 重启历史
w / who                     # 在线用户
dmesg -T                    # 内核启动日志（硬件识别过程）⭐
journalctl -b               # 本次启动日志
systemd-analyze             # 启动耗时
```

**传感器与温度**：
```bash
sensors                     # 温度/电压/风扇（需 lm-sensors）⭐
sudo sensors-detect         # 首次配置（探测芯片）
watch -n2 sensors
cat /sys/class/thermal/thermal_zone*/temp      # 温度（毫摄氏度）⭐
cat /sys/class/hwmon/hwmon*/temp*_input
ipmitool sensor             # 服务器 BMC（远程管理卡）⭐
ipmitool sdr / ipmitool sel list               # 传感器与系统事件日志
smartctl -A /dev/sda | grep -i temp            # 磁盘温度
nvidia-smi                  # NVIDIA GPU 温度/功耗/显存 ⭐
```

**电源与功耗**：
```bash
ipmitool power status       # 服务器电源状态
ipmitool chassis status
cat /sys/class/power_supply/*/capacity         # 笔记本电池
turbostat                   # Intel 功耗与频率（需 root）⭐
powertop                    # 功耗分析
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor   # 调频策略
```

**关键系统信息**：
```bash
uname -a                    # 内核版本
cat /etc/os-release         # 发行版 ⭐
hostnamectl                 # 主机名/内核/架构/虚拟化类型 ⭐
systemd-detect-virt         # 判断是否在虚拟机/容器里 ⭐
cat /etc/*release*
lsb_release -a
```

**判断"是虚拟机还是物理机"**：
```bash
systemd-detect-virt         # kvm / vmware / docker / none
dmidecode -t system | grep -i -E "manufacturer|product"    # 云厂商标识
cat /sys/class/dmi/id/product_name
lscpu | grep -i hypervisor
```
**云主机的特征**：`dmidecode` 显示厂商名（如 `Alibaba Cloud`、`Amazon EC2`）、`product_name` 是实例类型、`lscpu` 有 `Hypervisor vendor`。

**实践建议**：
1. **`inxi -F` 或 `lshw -short`** 是"快速了解一台机器"的最快方式。
2. **`lscpu` 看物理核数**（不是 `nproc`，后者含超线程）。
3. **`dmidecode` 看内存插槽**（判断能否加内存、是否插满、频率）。⭐
4. **`smartctl` 是硬盘健康的必查项**（上线新机器、排查 IO 问题时）。
5. **`sensors`/`ipmitool` 看温度**（高温会降频，是"性能突然下降"的隐藏原因）。⭐
6. **`dmesg -T`** 看硬件识别过程（驱动加载失败都在这）。
7. **虚拟化环境要 `systemd-detect-virt`**（决定是否能改内核、是否有限制）。
8. **`hostnamectl`** 是最简洁的系统信息总览。""",
    ),
    (
        "Linux",
        "KVM,虚拟化",
        3,
        r"""KVM 虚拟化是怎么工作的？和容器有什么区别？""",
        r"""**KVM（Kernel-based Virtual Machine）**：Linux 内核内置的**硬件虚拟化**支持（利用 Intel VT-x / AMD-V）。

**架构**：
```
用户态：   QEMU（设备模拟 + 虚拟机管理）
              ↕ ioctl
内核态：   KVM 模块（/dev/kvm），负责 CPU/内存虚拟化
              ↕
硬件：     VT-x / AMD-V（CPU 虚拟化）、EPT/NPT（内存虚拟化）、VT-d（IO 虚拟化）
```

- **KVM = 内核模块**（提供虚拟化的 CPU/内存）。
- **QEMU = 用户态设备模拟器**（网卡、磁盘、显卡、USB...）。
- 两者组合叫 **QEMU/KVM**（生产中绝大多数"KVM 虚拟机"实际是 QEMU/KVM）。
- **`/dev/kvm`** 是入口；没有它就是没开虚拟化或权限不足。

**关键虚拟化技术**：
| 技术 | 作用 |
|---|---|
| **VT-x / AMD-V** | CPU 指令级虚拟化（Guest 指令直接在 CPU 上跑） |
| **EPT / NPT** | 内存虚拟化（二级页表，避免影子页表开销） |
| **VT-d / IOMMU** | **设备直通**（把物理网卡/GPU 直接给虚拟机） |
| **SR-IOV** | 一张网卡虚拟出多个"虚拟功能"（VF）给不同 VM |
| **virtio** | **半虚拟化驱动**（Guest 知道自己在虚拟化里，用优化的接口）⭐ |
| **vhost/vhost-net** | 把 virtio 的后端搬到内核/用户态（减少上下文切换） |
| **DPDK/vhost-user** | 用户态网络转发（最高性能） |

**完全虚拟化 vs 半虚拟化**：
- **完全虚拟化（HVM）**：Guest 不知道自己被虚拟化，用模拟设备（慢）。
- **半虚拟化（Paravirt/virtio）**：Guest 用专用驱动直接和宿主通信（**快得多**）。
- **现代实践**：CPU/内存用硬件虚拟化，**IO 用 virtio**（组合最优）。

**virtio 设备**（现代 VM 的标配）：
| 设备 | 用途 |
|---|---|
| `virtio-blk` / `virtio-scsi` | 磁盘（scsi 支持更多设备与热插拔） |
| `virtio-net` | 网卡（配 vhost-net 更快） |
| `virtio-balloon` | 内存气球（动态调整 VM 内存）① |
| `virtio-fs` | 文件系统共享（替代 9p） |
| `virtio-gpu` / `virtio-vsock` | 显卡 / 主机-客机通信 |

**KVM 管理工具**：
| 工具 | 层次 |
|---|---|
| **`virsh`** | libvirt 命令行（**管理 VM 的标准方式**）⭐ |
| **`libvirt`** | 统一的虚拟化管理 API/守护进程（支持 KVM/Xen/容器） |
| `virt-install` | 创建 VM |
| `virt-manager` | GUI |
| `qemu-system-x86_64` | 直接用 QEMU（调试用） |
| `virt-v2v` | 物理机/其它平台迁移 |
| `cloud-init` | VM 首次启动的自动化配置 ⭐ |

**检查虚拟化能力**：
```bash
egrep -c '(vmx|svm)' /proc/cpuinfo      # >0 表示支持
lsmod | grep kvm
ls -l /dev/kvm
kvm-ok                                  # cpu-checker 包
systemd-detect-virt                     # 自己是否在 VM 里
```

**常用 `virsh`**：
```bash
virsh list --all
virsh start vm1 / shutdown vm1 / destroy vm1
virsh console vm1                       # 串口登录
virsh dominfo vm1
virsh domblklist vm1                    # 磁盘
virsh domiflist vm1                     # 网卡
virsh edit vm1                          # 编辑 XML 定义 ⭐
virsh dumpxml vm1 > vm1.xml
virsh snapshot-create-as vm1 snap1
virsh blockresize / vcpu / setmem       # 热插拔/热调整 ⭐
virsh net-list --all
virsh pool-list --all                   # 存储池
```

**KVM vs 容器**：

| 维度 | KVM 虚拟机 | 容器（Docker/LXC） |
|---|---|---|
| 隔离 | **硬件级（独立内核）** | 内核级（namespace + cgroup） |
| 启动 | 秒~几十秒 | **毫秒~秒** |
| 开销 | 有（内核 + 模拟） | **几乎零** |
| 密度 | 每台几~几十个 | **每台几百~几千个** |
| 安全 | **强**（内核漏洞不逃逸） | 中（共享内核，逃逸风险） |
| 内核 | 各自独立（可不同版本） | **共享宿主内核** |
| 运行异构 OS | ✅（Windows/Linux/BSD） | ❌（只能是 Linux 用户态） |
| 迁移 | 成熟（热迁移 live migration） | 较复杂（CRIU） |
| 适用 | 强隔离、异构 OS、多租户 | 微服务、快速扩缩、CI |

**"虚拟机 vs 容器"的行业趋势**：
1. **容器为主**（部署密度、速度）。
2. **VM 用于**：强隔离（多租户/不可信代码）、异构 OS、需要独立内核。
3. **安全容器**（融合两者）：
   - **Kata Containers**：每个容器跑在轻量 VM 里（强隔离 + 容器体验）。
   - **gVisor**（Google）：**用户态内核**拦截系统调用（不用硬件虚拟化）。
   - **Firecracker**（AWS Lambda）：**极轻量 VM**（毫秒启动，为 Serverless 设计）。
4. **云服务器（ECS/EC2）本质就是 KVM 虚拟机**（这也是为什么云主机看不到宿主机真机信息）。

**KVM 的性能优化**：
| 优化 | 效果 |
|---|---|
| **virtio 驱动** | IO 性能大幅提升 |
| **vhost-net** | 网络数据面移到内核（减少上下文切换） |
| **SR-IOV / 直通** | 接近物理网卡性能 ⭐ |
| **vCPU 与物理核绑定（pin）** | 减少调度干扰 |
| **大页（HugePages）** | 减少 TLB miss ⭐ |
| **关闭不用的设备** | 减少模拟开销 |
| **`-cpu host`** | 暴露所有 CPU 特性（性能最好） |
| **CPU 模型与拓扑对齐** | NUMA 感知（跨节点访存慢） |
| **多队列 virtio** | 多核并行收发 |
| **`iothread`/`io_uring`** | 磁盘 IO 后端优化 |

**常见问题**：
| 现象 | 原因 |
|---|---|
| VM 里"看不到"物理硬件 | 虚拟化屏蔽（`dmidecode` 显示 QEMU） |
| VM 时钟漂移 | 缺 `kvm-clock`/`qemu-guest-agent` |
| VM 性能差 | 用了模拟设备（未用 virtio）、未开大页、NUMA 不对齐 |
| 无法热迁移 | 用了直通设备（PCI passthrough 一般不能迁移） |
| `KVM: no hardware support` | VT-x 未在 BIOS 开启 / 嵌套虚拟化未开 |

**嵌套虚拟化**：在 VM 里再跑 VM（需要宿主开 `kvm_intel nested=1`）。云主机上默认通常关闭。

**实践建议**：
1. **判断"我在 VM 里吗"** → `systemd-detect-virt`。
2. **管理 VM 用 `virsh` + libvirt**（不要手写 qemu 命令行）。
3. **IO 一律用 virtio**（性能差异巨大）。
4. **关键 VM 开大页 + vCPU pinning + NUMA 对齐**。
5. **需要强隔离（多租户）用 VM 或 Kata/gVisor**，不要只用容器。
6. **热迁移前确认没有直通设备**。
7. **云主机上"改内核/装驱动"受限**（因为你的"硬件"是 QEMU 模拟的）。
8. **`cloud-init` 是做 VM 自动化的标准工具**（配 SSH 密钥、初始化脚本）。""",
    ),
    (
        "Linux",
        "Swap,swappiness",
        2,
        r"""Swap 有什么用？`vm.swappiness` 该怎么设？""",
        r"""**Swap** 把不常访问的内存页换出到磁盘（分区或文件），**用于**：
1. **应对内存峰值**（给突发流量兜底，避免直接 OOM）。
2. **让不活跃页腾出物理内存给活跃页**（提高缓存命中）。
3. **支持休眠（hibernate）**（需要 swap 空间 ≥ 内存）。

**类型**：
| 类型 | 说明 |
|---|---|
| **swap 分区** | 独立分区，性能略好，**不能动态调整** |
| **swap 文件** | 文件，灵活（可随时扩缩），**性能差异很小**（现代内核） |
| **zram** | **压缩内存作为 swap**（内存换 CPU，速度快，**容器/嵌入式/桌面常用**）⭐ |
| **zswap** | 内核的**压缩缓存层**（在真正换出前先压缩，减少 IO）⭐ |

```bash
# swap 文件
fallocate -l 4G /swapfile     # 或 dd if=/dev/zero of=/swapfile bs=1M count=4096
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
# 持久化
echo '/swapfile none swap sw 0 0' >> /etc/fstab

swapon --show                 # 当前启用的 swap ⭐
free -h
swapoff /swapfile

# zram（推荐给内存小的机器）
modprobe zram
echo 4G > /sys/block/zram0/disksize
mkswap /dev/zram0 && swapon /dev/zram0
# 或用 systemd-zram-generator / zramctl
```

**`vm.swappiness`（0~100，默认 60）**：

语义：**"倾向于把匿名页换出，还是倾向于丢弃文件缓存"**。
- 值**高**（100）：**积极 swap**（腾出内存给文件缓存）。
- 值**低**（0~10）：**尽量不 swap**，宁可丢弃 page cache。

**重要澄清（常见误解）**：
- ❌ "swappiness=0 就完全不 swap" —— **不对**。`0` 只是"尽量避免"，**在内存严重不足时仍会 swap**（避免 OOM 的必要手段）。
- 真正的"禁止 swap"是 `swapoff -a`（或把 `MemorySwapMax=0` 的 cgroup 设置）。

**推荐配置**：
| 场景 | 建议 |
|---|---|
| **数据库（MySQL/Redis/PG）** | `1~10`（避免关键数据被换出，延迟稳定） |
| **通用服务器** | `10~30` |
| **桌面/交互式** | `60`（默认，平衡） |
| **内存大且工作集稳定** | `1` |
| **实时性要求高** | `1` + 关闭 `MemorySwapMax`（并确保内存足够） |
| **容器** | 用 cgroup 控制（`memory.swap.max`） |

```bash
sysctl vm.swappiness=10
echo "vm.swappiness = 10" > /etc/sysctl.d/99-swap.conf
```

**Swap 的性能问题**：
1. **swap 在 HDD 上极慢**（随机 IO）→ "swap 抖动"（thrashing）会让系统卡死。
2. **SSD 上 swap** 快得多，但**有写放大与寿命消耗**。
3. **zram/zswap** 用 CPU 换 IO，**对内存小的场景收益巨大**（延迟从毫秒级降到微秒级）。

**监控 swap 活动**：
```bash
free -h
vmstat 1
# si/so 是 swap 换入/换出（KB/s）⭐
# 持续非 0 → 内存压力大
sar -S 1                       # swap 统计
cat /proc/vmstat | grep -E "pswpin|pswpout"
cat /proc/meminfo | grep -i swap
# PSI（更精确的内存压力）
cat /proc/pressure/memory      # some/full 的时间占比 ⭐
```
**`/proc/pressure/memory` 的 `full`** 表示"所有任务都被内存拖慢" —— 这是最严重的内存压力信号。

**什么时候"没有 swap"是危险的**：
- **没有 swap + 内存耗尽** → 直接触发 **OOM killer**（进程被杀）。
- **有少量 swap** → 给系统一个缓冲，让不活跃页先换出，避免立刻 OOM。
- **但 swap 也不能替代内存**（性能会崩）。

**"该给多少 swap"**：
| 内存大小 | 传统建议 | 现代建议 |
|---|---|---|
| ≤ 2G | 2 × 内存 | 2G |
| 2~8G | = 内存 | 2~4G |
| 8~64G | 0.5 × 内存 | 4~8G |
| > 64G | 无 | **4~16G**（兜底即可） |
| 需要休眠 | ≥ 内存 | ≥ 内存 |

**关键洞察**：**swap 的目的是"兜底"而不是"扩容"**。现代服务器内存大，给 4~8G 只为"避免瞬间 OOM"，而不是指望它支撑工作集。

**容器与 swap**：
- **默认容器不能用 swap**（cgroup v1 的 `memory.memsw` 需显式配置）。
- **cgroup v2**：`memory.swap.max` 控制 swap 用量。
- k8s：默认 `--fail-swap-on` 禁止节点开 swap（**性能可预测性优先**）；1.28+ 有 alpha 的 swap 支持。
- **`MemorySwapMax=0`（systemd）** 对延迟敏感服务很有用。

**`zram` 的推荐用法（内存小/容器）**：
```bash
# systemd-zram-generator
# /etc/systemd/zram-generator.conf
[zram0]
zram-size = ram / 4          # 内存的 25% 作为 zram
compression-algorithm = zstd
swap-priority = 100
```
**优势**：无磁盘 IO、速度快（~微秒级）、可换出更多页。

**`zswap`（内核压缩缓存）**：
```bash
echo 1 > /sys/module/zswap/parameters/enabled
# 在内核参数里：zswap.enabled=1 zswap.compressor=lz4 zswap.max_pool_percent=20
```
**作用**：在页被真正写到 swap 设备之前，先在内存里压缩（通常是压缩到原来的一半以内）。**减少 50%+ 的 swap IO**。

**实践建议**：
1. **数据库/延迟敏感服务：`vm.swappiness=1`**，并确保内存足够。
2. **不要设 `swappiness=0` 就以为"不会 swap"**（真正要禁止是 `swapoff` 或 cgroup）。
3. **HDD 上避免大量 swap**（会卡死）；**用 SSD 或 zram**。
4. **内存小的机器用 zram**（比磁盘 swap 快几个数量级）⭐。
5. **监控 `si/so` 与 `/proc/pressure/memory`**（`full` 非 0 就是严重问题）。
6. **k8s 节点默认禁用 swap**；如需启用要显式配置并接受不确定性。
7. **容器内存限制要留意 swap**（cgroup v2 的 `memory.swap.max`）。
8. **需要休眠**就必须有 ≥ 内存大小的 swap。""",
    ),
    (
        "Linux",
        "文件系统选择,ext4,xfs",
        2,
        r"""ext4 和 XFS 该怎么选？怎么调优文件系统？""",
        r"""**主流 Linux 文件系统对比**：

| 文件系统 | 优势 | 劣势 | 适用 |
|---|---|---|---|
| **ext4** | **稳定成熟**、工具齐全、支持收缩、碎片少 | 不支持快照、单目录大文件多时性能下降、最大文件系统 1EiB | **通用首选**（尤其中小规模） |
| **XFS** | **大文件/大目录/高并发**、在线扩容、project quota、reflink | **不能收缩**、修复工具较少、元数据仍依赖日志 | 大容量、大文件、**RHEL 默认** |
| **Btrfs** | 快照、校验和（数据自愈）、压缩、RAID、子卷、可收缩 | 历史上稳定性问题、写放大、RAID5/6 有坑 | 需要快照/校验的场景 |
| **ZFS** | 最强大（校验、快照、压缩、缓存、RAID-Z） | 许可与内核不兼容（需 DKMS）、内存需求高 | 存储服务器、NAS |
| **tmpfs** | 极快（内存） | 不持久、占内存 | 临时文件、`/run`、`/dev/shm` |
| **overlayfs** | 分层只读+可写 | 不适合大写入 | **容器镜像层** |
| **f2fs** | 为闪存优化 | 生态小 | SD 卡、eMMC |

**选择建议**：
1. **通用服务器 → ext4**（稳定、省心、能收缩）。
2. **大容量/大文件/大目录（>100T、媒体存储、数据库文件）→ XFS**。
3. **需要快照/校验 → Btrfs**（或 ZFS，但评估维护成本）。
4. **RHEL/CentOS 系 → XFS**（默认，且系统工具针对它调优）。
5. **容器 → overlayfs**（运行时自动选）。

**ext4 调优**：

```bash
mkfs.ext4 -O ^has_journal /dev/sdb1        # 关日志（性能↑，崩溃后要 fsck）— 一般别关
mkfs.ext4 -m 1 /dev/sdb1                   # 只保留 1% 给 root（默认 5%，大盘可省很多空间）⭐
mkfs.ext4 -E stride=16,stripe_width=128    # RAID 对齐
mkfs.ext4 -N 10000000 /dev/sdb1             # 预先分配更多 inode（海量小文件场景）

# 挂载选项
# /etc/fstab:
UUID=xxx /data ext4 defaults,noatime,nodiratime,data=writeback,commit=60,noauto_da_alloc 0 2
```
| 选项 | 效果 |
|---|---|
| **`noatime`** | **不更新访问时间** → 减少写 IO（**最推荐的优化**）⭐ |
| `nodiratime` | 目录也不更新 atime |
| `relatime`（默认） | 只在 atime 早于 mtime 时更新（折中） |
| `data=writeback` | 只保证元数据有序（性能↑，崩溃后可能读到旧数据） |
| `data=ordered`（默认） | 数据先写再提交元数据 |
| `data=journal` | 数据和元数据都进日志（**最安全但最慢**） |
| `commit=60` | 提交间隔（秒），默认 5；**调大减少 IO 但增加崩溃时数据丢失窗口** |
| `barrier=0` | 关写屏障（**有电池保护的 RAID 卡上可开**，否则危险） |
| `discard` | 在线 TRIM（**推荐用 `fstrim` 定时而非挂载选项**） |

**XFS 调优**：
```bash
mkfs.xfs -f -d agcount=32 -l size=256m /dev/sdb1     # AG 数与日志大小
# 挂载选项
UUID=xxx /data xfs defaults,noatime,logbsize=256k,inode64 0 0
```
| 选项 | 效果 |
|---|---|
| `noatime` | 同上 ⭐ |
| `logbsize=256k` | 加大日志缓冲 |
| `inode64`（默认） | inode 分布在整个文件系统（**大文件系统必开**） |
| `allocsize=1m` | 预分配（顺序写优化） |
| `nobarrier` | 关屏障（有 BBU 时可开） |
| **`pquota`/`prjquota`** | 项目配额（容器配额的基础）⭐ |

**`/etc/fstab` 的正确写法**：
```
# <设备>                    <挂载点>  <类型>  <选项>                    <dump> <fsck>
UUID=1234-ABCD              /        ext4    defaults,noatime           0      1
UUID=abcd-efgh              /data    xfs     defaults,noatime           0      2
tmpfs                       /tmp     tmpfs   defaults,size=2G,noexec,nosuid,nodev  0 0
/dev/vg0/lv_swap            none     swap    sw                         0      0
```
**要点**：
1. **用 `UUID=` 而不是 `/dev/sdX`**（设备名会变）⭐。
2. **`fsck` 顺序**：根分区 `1`，其它 `2`，不检查 `0`。
3. **`noauto`** 临时不挂载；**`nofail`** 挂载失败也继续启动（**外部盘必须加，否则开机卡住**）⭐。
4. **`tmpfs` 的 `size=`** 要设上限（否则吃光内存）。
5. **网络文件系统（NFS）** 用 `_netdev`（等网络就绪）。

**挂载选项安全加固**：
```
noexec     # 禁止执行（数据分区/上传目录用）⭐ 很重要
nosuid     # 忽略 SUID 位 ⭐
nodev      # 不解释设备文件 ⭐
ro         # 只读
```
**上传目录/`/tmp` 一定要 `noexec,nosuid,nodev`**（防 Web Shell 与提权）。

**常用维护命令**：
```bash
# ext4
e2fsck -f /dev/sdb1            # 强制检查（**必须先卸载**，根分区要在救援模式）
tune2fs -l /dev/sdb1           # 查看参数（含保留块、inode 数）
tune2fs -m 1 /dev/sdb1          # 改保留块比例
tune2fs -O ^has_journal         # 关日志
resize2fs /dev/sdb1             # 扩容/收缩

# XFS
xfs_repair /dev/sdb1            # 修复（**必须先卸载**）
xfs_db -r /dev/sdb1             # 检查
xfs_growfs /data                # 扩容（**只能扩，不能缩**）
xfs_admin -U generate /dev/sdb1 # 重新生成 UUID
xfs_info /data                  # 查看参数
xfs_quota -x -c 'report' /data

# 通用
df -hT / df -i
mount | column -t
findmnt                        # 树形显示挂载 ⭐
blkid                          # 设备 UUID/LABEL
lsblk -f                       # 设备与文件系统总览 ⭐
dumpe2fs /dev/sdb1 | head
fstrim -av                     # 给 SSD 发 TRIM（定期执行）⭐
```

**TRIM（SSD）**：
```bash
# 方法 A：定时（推荐，避免在线 discard 的性能抖动）⭐
systemctl enable --now fstrim.timer
fstrim -v /data

# 方法 B：挂载选项 discard（实时但可能有性能开销）
# /etc/fstab 加 discard
```
**为什么重要**：SSD 需要知道哪些块已释放才能做垃圾回收（GC）与磨损均衡。**不做 TRIM 会让写性能随使用下降。**

**性能检查**：
```bash
# 文件系统层面的耗时
perf trace -e 'ext4:*' ./prog
# IO 统计
iostat -xz 1
# 模拟测试
fio --name=test --rw=randwrite --bs=4k --iodepth=32 --size=1G --runtime=30 --filename=/data/test
```

**实践建议**：
1. **通用选 ext4，大容量/大文件选 XFS**。
2. **`noatime` 是最值得加的挂载选项**（减少写 IO）。
3. **`fstab` 用 UUID + 外部盘加 `nofail`**。
4. **`/tmp`、上传目录、数据分区加 `noexec,nosuid,nodev`**。
5. **SSD 开 `fstrim.timer`**（或挂载 `discard`）。
6. **`/boot` 单独分区**（防根分区问题导致无法启动）。
7. **大内存机器给 `/tmp` 用 tmpfs**（但要设 `size=`）。
8. **XFS 不能收缩** → 分区/LV 划分时留余地。
9. **扩容顺序**：扩云盘 → `growpart` → `resize2fs`/`xfs_growfs`（**不能反**）。
10. **`noatime` + `commit=60` 是常见的性能优化组合**（但要接受崩溃时最多丢 60 秒数据）。""",
    ),
    (
        "Linux",
        "高并发服务器,综合调优",
        3,
        r"""一台服务器要支撑 10 万并发连接，你会从哪些方面调优？""",
        r"""**分层调优**：内核 → 网络 → 应用 → 架构。

**一、fd 与进程限制（最基础）**
```bash
# systemd 服务
LimitNOFILE=1048576
LimitNPROC=1048576

# 系统级
sysctl -w fs.file-max=2097152
sysctl -w fs.nr_open=2097152
# /etc/security/limits.conf（非 systemd 场景）
* soft nofile 1048576
* hard nofile 1048576
```
```bash
cat /proc/<pid>/limits | grep files    # 验证
ulimit -n
```

**二、网络内核参数**
```bash
# /etc/sysctl.d/99-highload.conf
# --- 连接队列 ---
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.core.netdev_max_backlog = 65535
net.ipv4.tcp_abort_on_overflow = 0

# --- 端口与 TIME_WAIT ---
net.ipv4.ip_local_port_range = 1024 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_max_tw_buckets = 262144

# --- 缓冲区（长肥管道）---
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
net.ipv4.tcp_mem = 786432 1048576 1572864

# --- 连接跟踪（有 NAT/防火墙时）---
net.netfilter.nf_conntrack_max = 2000000
net.netfilter.nf_conntrack_tcp_timeout_established = 1200

# --- keepalive（长连接）---
net.ipv4.tcp_keepalive_time = 600
net.ipv4.tcp_keepalive_intvl = 30
net.ipv4.tcp_keepalive_probes = 3

# --- 拥塞控制 ---
net.ipv4.tcp_congestion_control = bbr
net.core.default_qdisc = fq

# --- 其他 ---
net.ipv4.tcp_slow_start_after_idle = 0
net.ipv4.tcp_fastopen = 3
net.ipv4.tcp_notsent_lowat = 131072
net.ipv4.tcp_mtu_probing = 1
net.ipv4.tcp_syncookies = 1
```
**关键项解释**：
| 参数 | 为什么 |
|---|---|
| `somaxconn` | **accept 队列上限**（默认 4096/128 太小）⭐ |
| `tcp_max_syn_backlog` | SYN 队列 |
| `ip_local_port_range` | 出站连接可用端口（短连接多时会耗尽）⭐ |
| `tcp_tw_reuse` | 复用 TIME_WAIT（**只用出站，安全**） |
| `rmem_max`/`wmem_max` | 大 RTT 高带宽下窗口要够（BDP） |
| **`tcp_congestion_control=bbr`** | 丢包环境下比 cubic 大幅提升（**高延迟/跨境场景**）⭐ |
| `default_qdisc=fq` | BBR 需要（公平队列） |
| `nf_conntrack_max` | 有 NAT 时不调大就会丢包 |
| `somaxconn`/`netdev_max_backlog` | 高包速率下防丢包 |

**三、内存与 page cache**
```bash
sysctl -w vm.swappiness=1                  # 避免关键页被换出
sysctl -w vm.dirty_ratio=10                # 减小 IO 抖动
sysctl -w vm.dirty_background_ratio=5
sysctl -w vm.min_free_kbytes=1048576       # 保留足够空闲内存（防直接回收）
sysctl -w vm.max_map_count=262144          # 内存映射数（ES/大内存应用）
sysctl -w vm.overcommit_memory=0
```
**注意**：`vm.min_free_kbytes` 太大浪费内存，太小会导致分配时同步回收（延迟抖动）。

**四、CPU 与中断**
```bash
# 中断亲和性（网卡中断分散到多核）
cat /proc/interrupts
systemctl enable --now irqbalance

# 网卡多队列（RSS）
ethtool -l eth0
ethtool -L eth0 combined 8

# RPS/RFS（单队列网卡软件分发）
echo f > /sys/class/net/eth0/queues/rx-0/rps_cpus
echo 32768 > /proc/sys/net/core/rps_sock_flow_entries
echo 4096 > /sys/class/net/eth0/queues/rx-0/rfs_flow_cnt

# 环形缓冲（防高流量丢包）
ethtool -G eth0 rx 4096 tx 4096

# CPU 调频（高性能模式）
cpupower frequency-set -g performance
```
**常见瓶颈**：**单核软中断 100%**（`mpstat -P ALL 1` 看 `%soft`）→ 用 RSS/RPS 分散。

**五、应用层（性能的决定因素）**

| 要点 | 说明 |
|---|---|
| **IO 多路复用** | `epoll`（ET + 非阻塞）、`io_uring` |
| **连接复用** | keep-alive、HTTP/2 多路复用、连接池 |
| **无阻塞的业务** | 避免在事件循环里做**慢操作**（磁盘 IO、DNS、同步 RPC）⭐ |
| **线程模型** | 多 Reactor（`SO_REUSEPORT` 多进程、`EPOLLEXCLUSIVE`） |
| **零拷贝** | `sendfile`、`splice` |
| **内存池/对象池** | 减少 malloc 与碎片 |
| **日志异步化** | 别让日志写阻塞请求路径 |
| **拒绝策略/背压** | 队列满时快速失败，避免雪崩 |
| **协议开销** | 减少序列化、启用压缩（权衡） |
| **CPU 亲和** | 网络线程与中断同核 |

**六、架构层（单机调优的上限）**

1. **水平扩展**：多机 + 负载均衡（LVS/nginx/云 LB）。
2. **`SO_REUSEPORT` + 多进程**：利用多核（nginx 的 `worker_processes auto`）。
3. **分层**：接入层（连接）与业务层（计算）分离。
4. **异步化**：消息队列解耦。
5. **CDN/边缘**：把静态与部分动态请求挡在外面。
6. **连接数与 QPS 的区别**：**10 万连接 ≠ 10 万 QPS**（长连接场景下连接数容易，QPS 取决于业务耗时）。
7. **C10K/C10M 问题**：现代 Linux 用 epoll + 合适的调优可以做到**百万连接**（关键是**每连接的内存开销**）。

**七、每连接的内存成本（决定能否上 10 万+）**
```
每连接开销 = 内核 socket 缓冲（rmem/wmem，可用 tcp_rmem 的最小值限制）
           + 应用层状态（连接对象、读缓冲）
```
- **内核缓冲**：`net.ipv4.tcp_rmem`/`wmem` 的最小值决定下限（每连接几 KB~几十 KB）。
- **应用层**：**每个连接一个线程**的模型在 10 万连接下必然崩（10 万 × 8MB 栈）→ **必须用事件驱动（单线程/少量线程处理大量连接）**。
- **估算**：10 万连接 × (16KB 内核 + 8KB 应用) ≈ **2.4GB** —— 说明**内存规划是核心**。

**八、验证与监控**

```bash
# 压测
wrk -t8 -c10000 -d60s http://host/         # HTTP 压测 ⭐
ab / hey / vegeta / locust / k6
# 连接数压测
# 检查是否达到限制
ss -s                                       # 连接状态汇总
ss -lnt                                     # 看 Send-Q（accept 队列上限）与 Recv-Q（当前排队）⭐
ss -tan state time-wait | wc -l
nstat -az | grep -iE "listen|drop|retrans"
cat /proc/<pid>/limits | grep files
# 资源
top / htop / vmstat 1 / mpstat -P ALL 1 / iostat -xz 1 / sar -n DEV,ETCP 1
# 应用层
perf top / 火焰图
```

**常见"上不去"的原因（按出现频率）**：
| 现象 | 原因 |
|---|---|
| `accept` 报 `EMFILE` | `LimitNOFILE` 太小 |
| 连接建立失败/超时 | `somaxconn`/`tcp_max_syn_backlog` 太小 |
| 少量连接就 CPU 打满 | 每连接一线程（上下文切换爆炸）⭐ |
| 单核 `si` 100% | 中断/软中断集中（RSS/RPS/多队列） |
| `Cannot assign requested address` | 出站端口耗尽（TIME_WAIT） |
| 偶发丢包/超时 | `nf_conntrack` 表满、环形缓冲不足 |
| 延迟抖动 | CPU 限流（cgroup throttle）、swap、GC |
| 内存暴涨 | 每连接缓冲太大 / 连接泄漏 |
| 大量 CLOSE_WAIT | 应用没 close |

**实践建议（顺序很重要）**：
1. **先压测找瓶颈**，不要盲目调参（`wrk`/`ss`/`mpstat`）。
2. **`LimitNOFILE` + `somaxconn` + `ip_local_port_range`** 是三大必备项。
3. **应用架构（事件驱动而非每连接一线程）比内核调优重要得多**。
4. **`tcp_congestion_control=bbr`** 在跨境/高丢包场景收益明显。
5. **关注 `ss -lnt` 的 `Recv-Q`**（accept 队列积压 = 应用 accept 太慢）。
6. **单机有上限** —— 到瓶颈就水平扩展，不要死磕单机。
7. **每连接内存估算**是"能否撑住连接数"的核心（决定选型）。
8. **压测要在预生产环境做**，并**用真实业务流量模型**（不只是空连接）。
9. **留意云环境的额外限制**（云盘 IOPS、带宽上限、安全组连接跟踪）。""",
    ),
    (
        "Linux",
        "容器安全,capabilities",
        2,
        r"""容器的安全风险有哪些？怎么加固？""",
        r"""**容器的安全本质**：容器**共享宿主内核**，隔离靠 namespace + cgroup + capabilities + seccomp + LSM。**任何一环配错都可能被逃逸。**

**主要风险**：

| 风险 | 说明 |
|---|---|
| **内核漏洞逃逸** | 共享内核 → 内核 CVE 可越狱（如 Dirty COW、runC 的 CVE-2019-5736）⭐ |
| **`--privileged`** | 等于给容器**全部能力 + 所有设备** → 几乎等于宿主机 root ⭐ |
| **Docker socket 挂载** | 挂 `/var/run/docker.sock` 等于给了宿主机 root（能起特权容器）⭐ |
| **镜像不可信** | 基础镜像有漏洞/后门/挖矿程序 |
| **敏感信息泄漏** | 镜像层里硬编码密钥、环境变量泄露 |
| **资源耗尽** | 未设 limits → 吃光宿主 CPU/内存/磁盘 |
| **提权** | SUID 文件、`CAP_SYS_ADMIN`、可写的宿主挂载 |
| **供应链** | 依赖包被投毒（`log4j` 类事件） |

**加固清单（从镜像到运行时）**：

**1. 镜像**
```dockerfile
# 用最小基础镜像
FROM alpine:3.19          # 或 distroless / scratch ⭐
# 非 root 用户运行
RUN adduser -D -u 1000 app
USER 1000
# 多阶段构建（不把编译工具链带进最终镜像）
FROM golang:1.22 AS build
...
FROM scratch
COPY --from=build /app /app
ENTRYPOINT ["/app"]
```
- **不要 `:latest`**（不可复现），用 digest 或明确版本。
- **扫描漏洞**：`trivy image x`、`grype`、`docker scout`。⭐
- **不把密钥写进镜像**（用 secret/环境注入）。

**2. 运行时限制**
```bash
docker run \
  --user 1000:1000 \                 # 非 root ⭐
  --read-only \                      # 只读根文件系统 ⭐
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --cap-drop=ALL \                   # 丢弃所有能力 ⭐
  --cap-add=NET_BIND_SERVICE \       # 只加需要的
  --security-opt=no-new-privileges \ # 禁止提权 ⭐
  --security-opt=seccomp=/etc/seccomp.json \
  --security-opt=apparmor=docker-default \
  --pids-limit=200 \                 # 防 fork 炸弹
  --memory=512m --memory-swap=512m \ # 内存限制
  --cpus=1.5 \                       # CPU 限制
  --ulimit nofile=1024:1024 \
  --network=mynet \                  # 不用 host 网络
  myimage
```
**绝不要 `--privileged`**（除非明确知道风险）；需要设备就 `--device=` 精确指定。

**3. `capabilities`（能力）**
- Linux 把 root 权限拆成 ~40 个能力（`CAP_NET_ADMIN`、`CAP_SYS_ADMIN`、`CAP_SYS_PTRACE`...）。
- **`CAP_SYS_ADMIN` 是最危险的**（几乎等于 root 的很多能力）。
- 容器默认有 14 个能力（Docker 的默认集）→ **应 `--cap-drop=ALL` 再按需 `--cap-add`** ⭐。
```bash
capsh --print                  # 查看当前进程的能力
getpcaps <pid>
# 二进制级别（代替 SUID）
setcap cap_net_bind_service=+ep /usr/bin/myserver
```

**4. `seccomp`（系统调用过滤）**
- 限制容器能调用哪些 syscall。
- Docker 默认有一份 seccomp profile（禁掉 ~44 个危险 syscall）。
- **自定义更严格的 profile**，或对高安全需求用 **gVisor**（用户态内核）。
```json
{ "defaultAction": "SCMP_ACT_ERRNO",
  "syscalls": [ { "names": ["read","write","open",...], "action": "SCMP_ACT_ALLOW" } ] }
```

**5. LSM（SELinux/AppArmor）**
- SELinux：容器进程打上 `container_t` 标签，限制跨容器与宿主访问。
- AppArmor：`docker-default` profile。
- **不要禁用**（很多人为了省事 `--security-opt apparmor=unconfined`，等于放弃一道防线）。

**6. 文件系统与挂载**
- **挂载宿主目录要谨慎**（尤其 `/`、`/etc`、`/var/run/docker.sock`）⭐。
- **挂载选项**：`ro`、`nosuid`、`noexec`、`nodev`。
- **不要挂 Docker socket**（要用就用受限的 socket proxy，如 `docker-socket-proxy`）。

**7. 网络**
- **不用 `--network=host`**（失去网络隔离）。
- **用自定义网络 + 最小暴露端口**。
- **网络策略**（k8s 的 NetworkPolicy）限制东西向流量。

**8. k8s 特有的加固**
```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false      # ⭐
  capabilities:
    drop: ["ALL"]
    add: ["NET_BIND_SERVICE"]
  seccompProfile:
    type: RuntimeDefault               # ⭐
# Pod 级别
automountServiceAccountToken: false     # 不需要就不用
# 用 PodSecurityAdmission（restricted 级别）⭐
# 用 OPA/Gatekeeper 或 Kyverno 做策略校验
```
- **`PodSecurityPolicy` 已废弃 → 用 `PodSecurityAdmission`**（`restricted` 级别会强制非 root、只读根、drop ALL）。
- **镜像准入控制**：只允许来自可信 registry 的签名镜像（`cosign` 验签）。

**9. 宿主机侧**
- **及时更新内核与容器运行时**（逃逸漏洞多在运行时）⭐。
- **启用 `user namespace`**（rootless 容器：容器内 root 映射为宿主普通用户）。
- **限制谁能运行特权容器**（Docker 的 `authorization plugin`；k8s 的 RBAC）。
- **审计**：`auditd`、`falco`（运行时威胁检测）⭐。
- **不要在生产宿主机上装无关服务**（缩小攻击面）。

**10. 供应链安全**
- **扫描镜像漏洞**（`trivy`、`grype`、`clair`）并接入 CI。
- **镜像签名与验签**（`cosign`、Notary）。
- **SBOM**（软件物料清单，`syft` 生成）。
- **依赖锁定与定期更新**（`dependabot`）。

**检查工具**：
| 工具 | 用途 |
|---|---|
| `trivy image x` | 镜像漏洞扫描 ⭐ |
| `grype` / `clair` | 漏洞扫描 |
| `docker scout` | Docker 官方扫描 |
| `kube-bench` | k8s CIS 基线检查 ⭐ |
| `kube-hunter` | k8s 渗透测试 |
| `falco` | **运行时威胁检测**（用 eBPF 监控异常行为）⭐ |
| `sysdig` | 系统调用追踪 |
| `capsh --print` | 查看能力 |
| `docker inspect` | 看运行配置 |
| `kubescape` | k8s 安全态势 |
| `checkov` / `tfsec` | IaC 安全扫描 |

**常见错误配置（要避免）**：
```yaml
privileged: true                 # ❌ 灾难
hostNetwork: true                # ❌ 失去网络隔离
hostPID: true                    # ❌ 能看到并能杀宿主进程
hostPath: /                      # ❌ 挂载宿主根
- /var/run/docker.sock:/var/run/docker.sock   # ❌ 等于宿主机 root
runAsUser: 0                     # ❌ 以 root 运行
capabilities: { add: ["SYS_ADMIN"] }          # ❌ 几乎等于 root
```

**实践建议**：
1. **非 root + `cap-drop=ALL` + `no-new-privileges` + 只读根** 是最有效的四条 ⭐。
2. **绝不用 `--privileged`**；确实需要就精确 `--cap-add`/`--device`。
3. **绝不给应用挂 `/var/run/docker.sock`**。
4. **扫描镜像漏洞**并接入 CI；**用最小基础镜像**（distroless/scratch）。
5. **k8s 用 `PodSecurityAdmission=restricted`** + NetworkPolicy + 不使用默认 ServiceAccount token。
6. **开启 `falco` 做运行时检测**（发现异常 exec、文件访问、网络连接）。
7. **及时更新内核与容器运行时**（逃逸修复）。
8. **用 rootless 容器**（Docker rootless / k8s 的 `userns`）进一步隔离。
9. **定期跑 `kube-bench`** 对照 CIS 基线。
10. **记住：容器隔离强度 < 虚拟机** → 不可信工作负载用 **Kata/gVisor/Firecracker** 或 VM 沙箱。""",
    ),
    (
        "Linux",
        "救援模式,单用户,系统恢复",
        2,
        r"""系统启动不了（或配置改坏了）怎么救援？""",
        r"""**先判断故障层级**：

| 症状 | 可能原因 |
|---|---|
| 卡在 GRUB / 没有启动项 | GRUB 配置损坏、`/boot` 损坏 |
| `Kernel panic - not syncing` | 根文件系统挂不上（驱动/initramfs 问题）、内核参数错 |
| 卡在 `emergency mode` / `rescue mode` | 某个服务起不来、`/etc/fstab` 挂载失败 ⭐ |
| 能启动但登录不了 | PAM 配置错、`/etc/passwd`/`shadow` 损坏、shell 路径错 |
| 图形界面起不来 | 显卡驱动、X/Wayland 配置 |

**救援路径（按严重程度）**：

**1. 单用户 / 救援模式（能进 GRUB）**
```
GRUB 菜单 → 按 e 编辑启动项 → 在 linux 行末尾加：
  systemd.unit=rescue.target      # 单用户（需要 root 密码）
  systemd.unit=emergency.target   # 更早、最小环境
  init=/bin/bash                  # 直接给 root shell（**最强**）⭐
  rw                              # 以读写挂载根（默认 ro）
→ Ctrl+X 启动
```
**`init=/bin/bash` 时的操作**：
```bash
mount -o remount,rw /             # 必须重新挂载为读写才能改文件 ⭐
# 修复...
mount -o remount,ro /
# 重启
echo b > /proc/sysrq-trigger      # 或 exec /sbin/reboot
```
**注意**：`init=/bin/bash` 时**没有 /proc /sys，没有服务，没有网络**，且某些命令（如 `systemctl`）不可用。

**2. 从 Live CD/USB 救援（GRUB 也坏了）**
```bash
# 1) 用 Live 环境启动，识别根分区
lsblk / blkid
# 2) 挂载根分区
mount /dev/sda2 /mnt
# 3) bind mount 必要的虚拟文件系统 ⭐
for d in dev dev/pts proc sys run; do mount --rbind /$d /mnt/$d; done
# 4) chroot
chroot /mnt /bin/bash
# 5) 在里面修复
# 6) 退出并卸载
exit
umount -R /mnt
reboot
```
**`--rbind`** 比 `--bind` 更适合 `/dev`（因为 `/dev` 下有子挂载）。

**3. 云主机 / 远程服务器**
- **云控制台的 VNC/串口控制台**（必须先用它才能进 GRUB 或单用户）。
- **附加救援系统**：把系统盘挂到另一台机器上修复（云厂商的"救援模式"）。
- **快照回滚**（最省事，但会丢数据）。

**常见故障与修复**：

**① `/etc/fstab` 写错 → 卡在 emergency mode** ⭐（最高频）
```bash
# 修复：进 emergency mode（会要求 root 密码）后
mount -o remount,rw /
vi /etc/fstab        # 修正错误（或用 # 注释掉问题行）
# 检查语法
systemctl daemon-reload
# 验证所有挂载
mount -a             # **改 fstab 后必须测这个** ⭐
reboot
```
**预防**：外部盘加 `nofail` 选项；改 fstab 前 `cp /etc/fstab /etc/fstab.bak`。

**② `/etc/passwd` 或 `/etc/shadow` 损坏 → 登录不了**
```bash
# 单用户或 Live 环境
mount -o remount,rw /
vi /etc/shadow          # 检查格式
# 若无密码可登录的用户，可以用：
pwconv                   # 从 /etc/passwd 重建 shadow
# 或给 root 设密码：
# 用 openssl 生成哈希
openssl passwd -6
# 把哈希填进 shadow 第 2 字段
```
**注意：直接编辑 `shadow` 要极其小心**（格式破坏 = 谁都登不了）。备份很重要。

**③ PAM 配置错 → 无法登录**
```bash
# 用 init=/bin/bash 进系统
# 恢复 /etc/pam.d/ 下的文件（从备份或同版本机器拷）
# 或至少让某个入口能进（如 ssh 的 PAM 配置）
```

**④ shell 被改坏（如 `/bin/bash` 权限/内容坏了）**
```bash
# GRUB 里加 init=/bin/sh（用 sh 而不是 bash）
# 或用 Live 环境 chroot 后从包管理器重装 bash
rpm -ivh --force bash-*.rpm
# 或 apt install --reinstall bash
```
**预防**：**不要 chmod 掉 `/bin/bash` 的执行权限**（这是经典事故）。

**⑤ `/boot` 或 GRUB 损坏**
```bash
# Live 环境 chroot 后
# Debian/Ubuntu
apt install --reinstall linux-image-$(uname -r) grub-pc
grub-install /dev/sda
update-grub
# RHEL 系
grub2-install /dev/sda
grub2-mkconfig -o /boot/grub2/grub.cfg
dracut -f
```

**⑥ 内核起不来（新内核驱动缺失）**
→ 在 GRUB 菜单选**旧内核**启动，然后修好新内核。

**⑦ systemd 服务导致启动卡住**
```bash
# 临时跳过某个服务
# GRUB 里加：
systemd.mask=坏服务.service
# 或进 rescue 后
systemctl mask bad.service
systemctl disable bad.service
```
**注意**：`mask` 创建到 `/dev/null` 的软链（比 `disable` 更彻底）。

**⑧ 磁盘满了导致服务起不来**
→ 从单用户模式清理（见"磁盘满"一题）。

**⑨ 根文件系统只读（磁盘错误触发 remount-ro）**
```bash
dmesg | grep -i "EXT4-fs error\|remount"
# 需要修复文件系统
fsck -y /dev/sda2        # 必须在未挂载状态下
```

**GRUB 的几个应急操作**：
- **在 GRUB 里按 `e` 编辑**（临时，不持久）。
- **`c` 进入 GRUB 命令行**（可手工 load 内核）。
- **`init=/bin/bash` + `rw`** 是最常用的救援组合。
- **`single`**（老式写法，等价于 runlevel 1）。
- **`rd.break`**（RHEL 系，用于重置 root 密码）：
```
在 GRUB 的 linux 行末尾加 rd.break
switch_root:/# mount -o remount,rw /sysroot
switch_root:/# chroot /sysroot
sh-4.4# passwd root
sh-4.4# touch /.autorelabel     # SELinux 要重建标签 ⭐
sh-4.4# exit; exit; reboot
```

**重置 root 密码的标准流程**（物理/控制台访问）：
1. 进入 GRUB，`e` 编辑。
2. `linux` 行末尾加 `rd.break`（RHEL）或 `init=/bin/bash`。
3. 挂载读写 → `passwd root` → 设置新密码。
4. **RHEL 系要 `touch /.autorelabel`**（否则 SELinux 会拒绝登录）。
5. 重启。

**预防措施（比救援更重要）**：
1. **改 `/etc/fstab`、`/etc/ssh/sshd_config`、PAM 前先备份**，并且**用新会话验证后再关旧会话**（SSH 场景）⭐。
2. **外部盘挂载加 `nofail`**。
3. **保留多个 GRUB 内核条目**（不要只留一个）。
4. **配置 `kdump`** 保存内核崩溃现场。
5. **云主机用快照**（改配置前打一个）。
6. **有带外管理**（IPMI/iDRAC/云控制台）才能进单用户 → **确认它可用**。
7. **不要 `chmod`/`chown` 系统关键文件**（`/bin/bash`、`/etc/shadow`、`/usr`）。
8. **禁用 SELinux 前想清楚**（`setenforce 0` 重启后可能又变 enforcing）。
9. **维护一个"救援手册"**（包含具体命令），别在故障时现查。
10. **定期演练**（真的从控制台走一遍流程）。

**排查启动问题的命令**：
```bash
journalctl -b                    # 本次启动日志 ⭐
journalctl -b -1                 # 上次启动（**排查崩溃重启的关键**）⭐
journalctl -b -p err             # 只看错误
systemd-analyze blame            # 哪个服务慢
systemctl --failed               # 失败的服务 ⭐
systemctl status <svc> -l        # 详细
dmesg -T | tail -50
cat /var/log/boot.log
```
**`journalctl -b -1`** 是排查"为什么重启了"的第一入口（前提是 journal 持久化）。""",
    ),
    (
        "Linux",
        "update-alternatives,多版本",
        2,
        r"""一台机器上有多个版本的 Python/Java/GCC 时怎么管理？""",
        r"""**三种主要方式**：

**1. `update-alternatives`（Debian/RHEL 通用，系统级）**

管理"同一功能的多个实现"，通过 `/etc/alternatives/` 下的软链接切换。

```bash
# 注册
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 2
#                   ↑链接位置         ↑组名    ↑实际路径           ↑优先级

# 交互式选择 ⭐
sudo update-alternatives --config python3
#  There are 2 choices for the alternative python3:
#   Selection    Path                Priority   Status
#  * 0            /usr/bin/python3.12   2         auto mode
#    1            /usr/bin/python3.11   1         manual mode
#    2            /usr/bin/python3.12   2         manual mode

# 自动模式（选优先级最高的）
sudo update-alternatives --auto python3
# 直接指定
sudo update-alternatives --set python3 /usr/bin/python3.11

# 查看
update-alternatives --list python3
update-alternatives --display python3
# 删除
sudo update-alternatives --remove python3 /usr/bin/python3.11
```
**RHEL 系的等价命令**：`alternatives --config python3`（同源）。

**2. 环境模块（`environment-modules`，HPC 场景）**
```bash
module avail
module load python/3.12
module list
module unload python/3.12
module swap python/3.11 python/3.12
```
**适合**：一台机器上大量不同版本的编译器等（超算中心标配）。

**3. 版本管理工具（开发场景，**推荐**）**
| 语言 | 工具 |
|---|---|
| Python | **`pyenv`**、`uv`、`conda`、`virtualenv`（环境隔离）⭐ |
| Node | **`nvm`**、`fnm`、`volta` ⭐ |
| Java | **`sdkman`**、`jenv` ⭐ |
| Go | `g`、`asdf` |
| Ruby | `rbenv`、`rvm` |
| 通用 | **`asdf`**（一个工具管所有语言）⭐ |
| Rust | `rustup` |

```bash
# pyenv 例子
pyenv install 3.12.3
pyenv global 3.12.3           # 全局
pyenv local 3.11.9            # 当前目录（写入 .python-version）⭐
pyenv versions
# nvm 例子
nvm install 20
nvm use 20
nvm alias default 20
```

**⚠️ 关键区别：切换"解释器版本" vs "隔离依赖"**

- **`update-alternatives`/`pyenv`/`nvm`**：只切**版本**（共享同一套 site-packages/全局包）→ **项目依赖会互相污染**。
- **虚拟环境（venv/virtualenv/conda）**：每个项目**独立的依赖** → **这才是工程实践的标准** ⭐。

```bash
# Python 的推荐组合：版本管理 + 虚拟环境
pyenv install 3.12.3 && pyenv local 3.12.3
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# 用 uv（更快）
uv venv && uv pip install -r requirements.txt
```

**实践建议（重要）**：

1. **不要替换系统自带的 Python/Java/GCC** ⭐
   - 系统工具（`yum`/`apt`、`systemd`、各种脚本）依赖特定版本。
   - **改了 `/usr/bin/python3` 的默认版本可能让整个包管理器崩掉**。
   - **应该用 `venv`/`pyenv`/`conda` 做项目级隔离**，而不是改系统默认。

2. **需要"系统级"切换时用 `update-alternatives`**，且**只对确实需要全局统一的东西**（如 `java`）。

3. **`PATH` 顺序优于软链接**（但要注意脚本里用不用绝对路径）：
```bash
export PATH="$HOME/.pyenv/bin:$PATH"
export PATH="/opt/jdk-21/bin:$PATH"
```

4. **服务用绝对路径**（避免依赖 PATH 的版本）：
```ini
# systemd
ExecStart=/usr/bin/python3.11 /opt/app/main.py     # 明确版本 ⭐
```

5. **容器是最彻底的隔离**（每个应用一个镜像，各自版本互不干扰）⭐。

6. **多版本共存时的依赖安装**：
```bash
# 明确用哪个解释器安装
/usr/bin/python3.11 -m pip install xxx
python3.11 -m pip install xxx
# 不要裸用 pip（可能是别的版本）
```

**排查"用了哪个版本"**：
```bash
which -a python3              # 所有匹配
type -a python3               # 含别名/函数/内建 ⭐
python3 -V                    # 实际版本
head -1 $(which python3)      # 若是脚本，看 shebang
readlink -f $(which python3)  # 解析软链接链 ⭐
ls -l /usr/bin/python3
echo $PATH | tr ':' '\n'      # PATH 顺序
pip -V                        # pip 属于哪个 python（重要的交叉验证）⭐
python3 -c "import sys; print(sys.executable, sys.path)"
```

**多版本共存的常见坑**：
```bash
# pip 装了包但 import 不到 → pip 和 python 不是同一个版本 ⭐
python3 -m pip install xxx    # ✅ 用 -m 保证一致
pip3 --version                # 看它绑定的 python

# nvcc/gcc 版本不匹配
ls /usr/bin/gcc*; ls /usr/bin/g++*
update-alternatives --config gcc

# Java 版本
java -version
update-alternatives --config java
JAVA_HOME=/usr/lib/jvm/java-21-openjdk    # 显式设置 ⭐
```

**`ldconfig` 与多版本库**：
```bash
ldconfig -p | grep libssl
ls -l /usr/lib/x86_64-linux-gnu/libssl*
# 多版本库共存：用 rpath 或 LD_LIBRARY_PATH 指定（见动态库一题）
```

**实践清单**：
| 需求 | 推荐 |
|---|---|
| 项目 Python 依赖隔离 | `venv` / `uv` / `conda` ⭐ |
| 切 Python 版本 | `pyenv`（用户级） |
| 切 Java 版本 | `sdkman` / `jenv`（用户级） |
| 切 Node 版本 | `nvm` / `fnm` |
| 全语言统一管理 | `asdf` |
| 系统级统一切换 | `update-alternatives`（**慎用**） |
| 彻底隔离 | **容器** ⭐ |

**最重要的建议**：**永远不要动系统自带的解释器**（`/usr/bin/python3`、`/usr/bin/python2`）。用虚拟环境或用户级版本管理器，服务里写绝对路径或用容器。这是"改了 python 版本导致 yum/apt 崩了"这类事故的根本预防。""",
    ),
    (
        "Linux",
        "SELinux 排障实战",
        3,
        r"""服务在 CentOS/RHEL 上"权限都对了但还是报 Permission denied"，怎么定位？""",
        r"""**先做二分：是普通权限问题还是 SELinux？**

```bash
# 最快的一刀：临时切 Permissive
getenforce               # 记下当前值（Enforcing）
setenforce 0
# 复现问题
#   问题消失 → **确认是 SELinux**
#   问题依旧 → 不是 SELinux，回到普通权限排查
setenforce 1             # 恢复
```
**注意**：`setenforce 0` 只是**验证手段**，**不要作为最终解决方案**。

**如果是 SELinux，走完整排障流程**：

**第 1 步：看 AVC 拒绝日志** ⭐
```bash
# 方法 A：ausearch（最准）
sudo ausearch -m AVC -ts recent
sudo ausearch -m AVC -ts today | tail -50

# 方法 B：直接 grep
sudo grep "avc:.*denied" /var/log/audit/audit.log | tail -20
# 若 auditd 没装
sudo journalctl -t audit | grep AVC | tail
dmesg | grep -i "avc.*denied" | tail

# 方法 C：sealert（要装 setroubleshoot-server）⭐ 最友好
sudo sealert -a /var/log/audit/audit.log
# 会给出人类可读的解释 + 建议的修复命令
```

**第 2 步：读懂 AVC 日志**
```
type=AVC msg=audit(1699999999.123:456): avc:  denied  { read } for  pid=1234 comm="nginx"
  path="/home/deploy/www/index.html" dev="sda1" ino=789
  scontext=system_u:system_r:httpd_t:s0        ← 发起者（进程）的类型
  tcontext=unconfined_u:object_r:user_home_t:s0 ← 目标（文件/资源）的类型
  tclass=file permissive=0
```
**读法**：
- `denied { read }`：被拒绝的操作。
- `scontext` 的 `httpd_t`：**进程的类型**（由策略决定这个类型能做什么）。
- `tcontext` 的 **`user_home_t`**：**目标的类型**（这里是问题所在！网站文件在家目录里，标签是"用户家目录"）。
- `tclass=file`：目标类别。

**第 3 步：按"scontext/tcontext 组合"选修复方式**

| 情况 | 修复方式 |
|---|---|
| **文件标签不对**（放错位置） | `semanage fcontext` + `restorecon` ⭐ |
| **端口未授权** | `semanage port -a` |
| **服务需要额外能力**（网络/家目录/数据库） | `setsebool -P` |
| **临时验证** | `chcon`（会被 restorecon 还原） |
| **以上都不行** | `audit2allow` 自定义策略（**最后手段**） |

**修复 A：文件标签**
```bash
# 网站放在家目录 → 标签是 user_home_t，httpd_t 读不了
sudo semanage fcontext -a -t httpd_sys_content_t "/home/deploy/www(/.*)?"
sudo restorecon -Rv /home/deploy/www           # 必须执行才能生效 ⭐

# 查看"这个路径应该是什么标签"
matchpathcon /var/www/html/index.html

# 列出已有的规则
semanage fcontext -l | grep httpd_sys_content

# 删除错误规则
semanage fcontext -d "/home/deploy/www(/.*)?"
```
**`chcon` 是临时的**（`restorecon` 或 `relabel` 会还原）→ **正式修复用 `semanage fcontext`** ⭐。

**修复 B：端口**
```bash
# nginx 监听 8080 → http_port_t 只允许 80/443 等
sudo semanage port -l | grep http_port_t
sudo semanage port -a -t http_port_t -p tcp 8080
# 若端口已被别的类型占用，用 -m 修改
sudo semanage port -m -t http_port_t -p tcp 8080
sudo semanage port -l | grep 8080
```
**常见需要加端口的场景**：nginx/ssh/mysql 换端口、Tomcat 8080、自定义服务端口。

**修复 C：布尔值（服务需要额外权限）**
```bash
# 看有哪些相关布尔值
getsebool -a | grep httpd
semanage boolean -l | grep httpd      # 更详细（含说明）

# 常用开关
sudo setsebool -P httpd_can_network_connect 1        # 允许 nginx 反向代理
sudo setsebool -P httpd_can_network_connect_db 1     # 允许连数据库
sudo setsebool -P httpd_enable_homedirs 1            # 允许访问家目录
sudo setsebool -P httpd_read_user_content 1
sudo setsebool -P httpd_can_sendmail 1
sudo setsebool -P nis_enabled 1                       # 允许非标准端口（历史上的）
```
**`-P` 必须加**（持久化），否则重启失效 ⭐。

**修复 D：`audit2allow`（最后手段）**
```bash
# 从当前拒绝日志生成策略
sudo ausearch -m AVC -ts recent | audit2allow -M myapp_local

# 先看它要放行什么（**必做**）⭐
cat myapp_local.te

# 安装
sudo semodule -i myapp_local.pp
sudo semodule -l | grep myapp

# 更精确：只看某个类型的拒绝
sudo ausearch -m AVC -c nginx | audit2allow -M nginx_local
```
**⚠️ 用 `audit2allow` 生成"放行一切"的策略会削弱安全** —— **务先尝试 A/B/C 三种正规方式**（用对标签、加对端口、开对布尔值）。

**第 4 步：验证**
```bash
# 清空旧日志以便观察
sudo /usr/sbin/logrotate -f /etc/logrotate.d/auditd    # 或 truncate

# 重启服务并复现
sudo systemctl restart nginx
# 检查是否还有新的 AVC
sudo ausearch -m AVC -ts recent
# 确认 SELinux 下服务正常
getenforce        # 必须是 Enforcing ⭐
curl -I localhost:8080
```

**关键命令速查**：
```bash
# 状态
getenforce / sestatus
# 上下文
ls -Z / ps -Z / id -Z / ss -Z
matchpathcon /path
# 文件标签
semanage fcontext -a/-d/-l
restorecon -Rv /path
chcon -t TYPE /path        # 临时
# 端口
semanage port -a/-m/-d/-l
# 布尔
getsebool / setsebool -P / semanage boolean -l
# 策略模块
semodule -i/-r/-l
# 排障
ausearch -m AVC -ts recent
audit2why < avc.log
audit2allow -M name
sealert -a audit.log
```

**容器场景**：
```bash
# Docker 挂载宿主目录到容器时，SELinux 会拒绝
docker run -v /host/data:/data:z ...    # :z 重新打标签（共享）⭐
docker run -v /host/data:/data:Z ...    # :Z 私有标签（独占）
# 或临时 setenforce 0（不推荐）
```

**常见错误做法（要避免）**：
| 做法 | 问题 |
|---|---|
| `setenforce 0` 就完事 | 降低系统安全性，重启后可能又变回 enforcing |
| 在 `/etc/selinux/config` 里 `SELINUX=disabled` | **需要重启**；且文件标签不会再维护，切回来会出问题 |
| 直接 `chcon` 不改 fcontext | 会被 `restorecon`/系统更新还原 ⭐ |
| 用 `audit2allow` 一把梭 | 放行了太多权限（可能包含提权路径） |
| `setsebool` 不加 `-P` | 重启失效 |
| 改完后不验证 | 可能只是部分修好 |

**实践建议（顺序）**：
1. **`setenforce 0` 做二分确认**，然后**立即恢复**。
2. **`ausearch` / `sealert` 读拒绝详情**（`tcontext` 的类型是关键线索）。
3. **优先用"正确的标签 + `restorecon`"**（最规范）⭐。
4. **端口问题用 `semanage port`**；**能力问题用 `setsebool -P`**。
5. **`audit2allow` 只作兜底**，且要看清楚它放行了什么。
6. **把站点放在标准目录（`/var/www`）能避免 90% 的问题**。
7. **改完必须 `getenforce` 确认是 Enforcing 再验证服务**。
8. **记录修复步骤**（新机器部署时会再遇到）。""",
    ),
    (
        "Linux",
        "/proc,/sys,虚拟文件系统,调优",
        2,
        r"""`/proc` 和 `/sys` 是什么？各自有哪些常用文件？为什么它们不占磁盘空间？""",
        r"""**本质**：二者都是**伪文件系统（pseudo filesystem）**，内容由内核在内存中动态生成，读文件 = 调用内核的一段代码，写文件 = 修改内核数据结构。所以 `du` 显示为 0。

| | `/proc`（procfs） | `/sys`（sysfs） |
|---|---|---|
| 定位 | 进程信息 + 部分内核参数 | 设备 / 驱动 / 内核对象的统一模型 |
| 结构 | 平铺的文件名 | 严格的树形（bus/class/devices/...） |
| 典型读 | `/proc/cpuinfo`、`/proc/meminfo`、`/proc/loadavg` | `/sys/class/net/eth0/statistics/rx_bytes` |
| 典型写 | `/proc/sys/...`（= `sysctl`） | 设备属性、`/sys/block/.../queue/scheduler` |

**`/proc` 高频文件**：

| 文件 | 用途 |
|---|---|
| `/proc/<pid>/status` | 进程状态、内存、线程数 |
| `/proc/<pid>/fd/` | 该进程打开的 fd → 软链到真实文件（`ls -l` 就能看出句柄泄漏）|
| `/proc/<pid>/maps` | 虚拟内存映射，排查内存布局 |
| `/proc/<pid>/cwd` `/exe` | 进程的工作目录 / 可执行文件路径 ⭐ 排查"这个服务是哪个二进制" |
| `/proc/meminfo` | 内存全局视图（`MemAvailable` 才是可用内存，`MemFree` 会误导）|
| `/proc/net/tcp` | 连接表，`ss` 就是解析它 |
| `/proc/pressure/*` | PSI 压力指标 |
| `/proc/sys/...` | 内核参数，`sysctl -a` 列全部 |

**内核参数持久化**：`/etc/sysctl.d/99-xxx.conf`（不是直接改 `/etc/sysctl.conf`，`sysctl --system` 生效）。运行时写 `/proc/sys/net/core/somaxconn` 与 `sysctl -w` 等价，**重启即失效**。

**为什么不能 `cat` 大文件**：某些 `/proc` 文件（如 `/proc/kcore`、`/proc/<pid>/mem`）是海量/特殊流，直接 cat 会吃满终端。用 `dd` 或 `head -c`。

**实践**：排查"配置改了没生效"时，先看 `/proc` 里的**运行时值**而不是配置文件（配置文件可能没被加载，或有多个文件覆盖）。""",
    ),
    (
        "Linux",
        "负载,load average,性能",
        2,
        r"""`uptime` 里的 load average 三个数字分别是什么意思？负载高就一定是 CPU 不够吗？""",
        r"""**含义**：三个数字是过去 **1 分钟 / 5 分钟 / 15 分钟**的**平均负载**。

**"负载"是什么**：内核统计的**可运行 + 不可中断睡眠**的进程数：
- **R（Running/Runnable）**：正在跑或排队等 CPU。
- **D（Uninterruptible Sleep）**：卡在**不可中断**的 IO 上（磁盘 IO、NFS、驱动）。
- **不包含**：普通睡眠（S，等 socket/信号）、僵尸（Z）。

所以确切地说：**load = 每单位时间 `nr_running + nr_uninterruptible` 的指数衰减平均值**（`/proc/loadavg` 第 4 项会直接给出 R 的个数）。

**判断标准 —— 必须除以核数**：

| 条件 | 结论 |
|---|---|
| load ≈ 核数 | 刚好跑满，健康上限 |
| load < 核数 | 有余量 |
| load > 核数 | 有任务排队，偏忙 |
| load > 核数 × 2 | 明显过载 |

例：4 核机器 load 是 8 → **每个核平均排 2 个任务**，属于过载。

**关键：负载高 ≠ CPU 瓶颈** ⭐
- 三个值都高且 R 多 → **CPU 密集**（`top` 看 `%us`/`%sy`）。
- 只有 1 分钟高、15 分钟低 → **瞬时突发**，不用管。
- 三个值都高但 CPU 空闲、有大量 **D 状态**进程 → **IO 瓶颈**（`iostat -xz 1`、`vmstat` 的 `b` 列、`/proc/pressure/io`）。
- 值持续爬升**降不下来** → 常见于磁盘坏道、NFS 挂死、内核 bug（此时看 `dmesg`、hung task）。

**排查顺序**：
1. `uptime` / `cat /proc/loadavg` —— 多高、趋势。
2. `nproc` —— 除以核数。
3. `top` 按 `1` 展开看每核，`vmstat 1` 看 `r`（运行队列）和 `b`（阻塞）。
4. `r` 高 → 查 CPU；`b` 高 → 查磁盘。
5. `cat /proc/pressure/cpu` `io` `memory` —— PSI 直接告诉你**谁在拖后腿**以及**被拖了多久**。

```bash
vmstat 1 5          # r 列 = 运行队列，b 列 = 阻塞进程
iostat -xz 1        # %util 接近 100 且 await 很大 = 磁盘打满
pidstat -d 1        # 按进程看 IO
```

**一句话**：load 是"有多少活儿在等"，不区分等的是 CPU 还是磁盘；**必须结合核数和状态分布**才能定性。""",
    ),
    (
        "Linux",
        "lsof,句柄泄漏,磁盘空间",
        3,
        r"""`df` 显示磁盘 100% 满，但 `du` 怎么也找不到占用空间的文件，是怎么回事？怎么定位和解决？""",
        r"""**典型场景**：`df -h` 说 `/` 满了，`du -sh /*` 加起来却差得远。这是**内核视角与文件系统视角不一致**。

## 一、根因：文件已被删除，但仍有进程持有 fd

Unix 中**文件名只是目录里的一条记录**，删除文件（`unlink`）只是摘掉这条记录并**减一引用计数**；只有**引用计数归零**，磁盘块才真正释放。

```
进程 A: open("big.log") ──► inode 1234 (nlink=1)
rm big.log            ──► inode 1234 (nlink=0) ← 目录里看不到了
                         但进程 A 还拿着 fd ⇒ 引用计数 ≠ 0 ⇒ 磁盘块不释放
```

**`du` 遍历目录，看不见它；`df` 读文件系统统计（`statvfs`），知道块还被占着。** 两者差距就是这么来的。**日志切割（logrotate）后没让进程重开日志是最常见的触发方式。**

## 二、定位 ⭐

```bash
# 1. 确认差异确实存在
df -h /                     # Use% 100%
du -sh / 2>/dev/null | tail

# 2. 直接列出 "已删除但仍被打开" 的文件（deleted 标记）
lsof -nP | grep '(deleted)'
lsof +L1                    # 列出 link count < 1 的文件（更精准）⭐
lsof -nP +L1 | awk '{print $1,$2,$7,$9}' | sort -k3 -n -r | head
#                   ^进程 ^PID ^大小 ^路径

# 3. 没有 lsof 时：遍历 /proc（lsof 本质就是干这个）
find /proc/*/fd -ls 2>/dev/null | grep '(deleted)'
for fd in /proc/[0-9]*/fd/*; do
    t=$(readlink "$fd" 2>/dev/null)
    case "$t" in *"(deleted)"*) echo "$fd -> $t";; esac
done

# 4. 看某个可疑进程
ls -l /proc/<pid>/fd | grep deleted
```

## 三、解决（三选一）

| 方法 | 命令 | 说明 |
|---|---|---|
| **重启 / reload 该服务** | `systemctl restart nginx` | 最干净，fd 关闭后立即释放 ⭐ |
| **让进程重开日志** | `kill -USR1 <pid>` | nginx / 多数守护进程支持，**不中断服务** |
| **清空 fd 内容**（应急）| `: > /proc/<pid>/fd/<n>` | 保留 inode 但把内容截断为 0，**立刻释放空间**，进程不受影响 ⭐ |

> ⚠️ `: > /proc/<pid>/fd/<n>` 会**直接丢弃**这些数据，不可恢复；生产上属应急手段，事后再规范日志切割。

## 四、其他导致 df/du 不一致的原因

| 原因 | 现象 | 排查 |
|---|---|---|
| 挂载点被**覆盖** | `du` 看不到被盖住的目录 | `mount \| grep <dir>`，`umount` 后重看 |
| **inode 耗尽** | `df -i` 100% 而 `df -h` 不满 | `df -i`、`find / -xdev -printf '%h\n' \| sort \| uniq -c \| sort -rn \| head` 找小文件多的目录 |
| **保留块**（ext4 默认 5%）| `df` 比实际可写少 5% | `tune2fs -m 1 /dev/sdX` |
| **稀疏文件 / 快照** | LVM 快照、overlay 层占空间 | `lvs`、`docker system df` |

## 五、预防（规范 logrotate）⭐

```conf
/var/log/myapp/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    copytruncate        # ← 切断不通知进程时的兜底：先拷贝再截断原文件
    # postrotate
    #     systemctl reload myapp   # ← 更推荐：让进程自己重新 open
    # endscript
}
```

**根因一句话**：**删除 ≠ 释放**；`du` 看目录树，`df` 看 inode 引用计数，只有最后一个持有者关闭 fd，空间才回来。定位靠 `lsof +L1`。""",
    ),
]


