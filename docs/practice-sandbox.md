# 练习闯关：代码沙箱部署与验证说明

本文档说明 `/api/practice/submit`（C++ 代码编译运行判定）的部署与验证步骤。
代码实现：`src/practice.cpp` + `src/practice.h`；路由：`src/routes.cpp`。

## 1. 前置条件

- 服务器已安装 `g++`（验证：`which g++`）。若系统无 g++，请先 `sudo apt install g++`（Debian/Ubuntu）或 `sudo yum install gcc-c++`（CentOS）。
- 已安装 `cmake` 与 `make`（原有项目就依赖，应已具备）。
- 服务进程能访问 `/tmp`（用 `mkdtemp` 建临时目录）。

## 2. 编译与部署

在项目根目录（`WebBasedCrow/`）执行：

```bash
cmake --build build
sudo systemctl restart blog.service
```

> 本次改动新增了 `src/practice.cpp`，已加入 `CMakeLists.txt` 的 `add_executable`。
> 若 `build` 目录是旧配置，建议重新 configure：`cmake -B build` 再 build。

## 3. 接口约定

`POST /api/practice/submit`，`Content-Type: application/json`：

```json
{ "exercise_id": 1, "tier": "easy", "code": "..." }
```

- `code`：玩家实现的函数（**不含 main**）。服务端拼隐藏测试驱动后编译运行。
- 返回字段：`success`、`status`、`passed`、`total`、`message`，
  失败时附 `compile_output`（编译原文）或 `runtime_output`（运行输出）。
- `status` 取值：`passed` / `failed` / `compile_error` / `runtime_error` / `timeout` / `internal_error`。

当前最小版**仅内置 `exercise_id = 1`** 一道示例题（C1 短题 1，`get_ref` / `get_value`），
`tier` 暂不影响判定。接数据库题库后改为查表。

## 4. curl 验证（四个场景）

以下均在本机 `localhost:8080` 执行，逐条核对返回。

### 4.1 正常通过 → 期望 `status=passed, passed=2, total=2`

```bash
curl -s -X POST http://localhost:8080/api/practice/submit \
  -H 'Content-Type: application/json' \
  -d '{"exercise_id":1,"tier":"easy","code":"int g_value = 42;\nint& get_ref() { return g_value; }\nint get_value() { return g_value; }"}'
```

### 4.2 返回类型写错（get_ref 返回值而非引用）→ 期望 `status=compile_error`

```bash
curl -s -X POST http://localhost:8080/api/practice/submit \
  -H 'Content-Type: application/json' \
  -d '{"exercise_id":1,"tier":"easy","code":"int g_value = 42;\nint get_ref() { return g_value; }\nint get_value() { return g_value; }"}'
```

> 隐藏用例里 `get_ref() = 100;` 对「返回值」的函数编译报错 `lvalue required as left operand`，
> 应被翻译层转成人话提示。

### 4.3 段错误 → 期望 `status=runtime_error`（message 含「段错误」）

```bash
curl -s -X POST http://localhost:8080/api/practice/submit \
  -H 'Content-Type: application/json' \
  -d '{"exercise_id":1,"tier":"easy","code":"int g_value = 42;\nint& get_ref() { int* p = nullptr; return *p; }\nint get_value() { return g_value; }"}'
```

### 4.4 死循环 → 期望 `status=timeout`（2 秒内返回）

```bash
curl -s -X POST http://localhost:8080/api/practice/submit \
  -H 'Content-Type: application/json' \
  -d '{"exercise_id":1,"tier":"easy","code":"int g_value = 42;\nint& get_ref() { for(;;){} return g_value; }\nint get_value() { return g_value; }"}'
```

## 5. 安全边界（务必读）

当前为**裸机 fork/exec + rlimit**，非容器：

| 闸 | 手段 | 状态 |
|---|---|---|
| 编译隔离 | g++ 进程：CPU 10s、内存 512MB、独立临时目录 | 已做 |
| 运行隔离 | a.out：CPU 2s、内存 256MB、文件 64MB、进程 32、fd 64、禁 core | 已做 |
| 系统隔离 | **未 chroot**——玩家代码可读本进程用户可读的宿主机文件 | ⚠️ 缺口 |
| 数据库隔离 | 数据库题暂未接真实 DB | ⚠️ 缺口 |

- 服务以 root 跑时 `RLIMIT_NPROC` 对 root 无效（内核不限制 root 进程数），CPU/内存/文件仍生效。
- 当前站点提交者基本是站长本人，风险可接受；**对外公开前必须补 chroot 或换 docker**。

## 6. 已知待办（对应题库文档 §7）

1. 接数据库：从 `practice_exercises` / `practice_test_cases` 取测试驱动，替换内置题。
2. `tier` 与隐藏用例挂钩（进阶含 easy+medium，挑战全跑）。
3. 补 chroot 或 docker 隔离。
4. 数据库题（C11）的临时 schema 隔离方案。
5. 提交限流（代码提交是重操作，防滥用）。
6. 编译超时 / 内存上限按真实题压测定值（当前 10s / 512MB 为暂定）。
