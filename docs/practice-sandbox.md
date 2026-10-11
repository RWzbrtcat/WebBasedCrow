# 练习闯关：接库 + 沙箱判定部署与验证说明

本文档说明练习闯关（C++ 代码编译运行判定）的部署与验证步骤。
代码：`src/practice.cpp`（沙箱判定）、`src/database.cpp`（练习查询）、`src/routes.cpp`（接口）。
题库：`tools/seed_practice.sql`（由 `tools/gen_practice_seed.py` 生成）。

## 1. 前置条件

- 服务器已安装 `g++`（验证：`which g++`）。若无，`sudo yum install gcc-c++`（OpenCloudOS/CentOS）。
- 已有 `cmake` 与 `make`（原项目依赖，应已具备）。
- 服务进程能访问 `/tmp`（用 `mkdtemp` 建临时目录）。

## 2. 部署步骤

在项目根目录（`WebBasedCrow/`）按顺序执行：

```bash
# 1) 导题库：建表 + 14 章节 + 写代码题（幂等，可重复执行）
mysql -u root -p blogdb < tools/seed_practice.sql

# 2) 编译（新增 practice.cpp，已加入 CMakeLists.txt）
cmake --build build

# 3) 重启
sudo systemctl restart blog.service
```

> 三张表（practice_chapters / practice_exercises / practice_progress）服务端启动时也会
> 自动创建（`initTable`），seed 只负责灌数据；但**题目数据必须先导**，否则前端章节全是空的。
> 若 `build` 目录是旧配置，建议重新 configure：`cmake -B build` 再 build。

## 3. 接口约定

| 接口 | 方法 | 说明 |
|---|---|---|
| `/api/practice/chapters` | GET | 章节列表（按学期分组），附每章题目数 |
| `/api/practice/exercises?chapter=N` | GET | 某章题目列表（仅列表字段） |
| `/api/practice/exercise/<id>` | GET | 单题详情：题干(markdown) + 三档脚手架（**不含隐藏测试驱动**） |
| `/api/practice/submit` | POST | 提交代码，沙箱编译运行判定 |

`POST /api/practice/submit` 的 body：

```json
{ "exercise_id": 1, "tier": "easy", "code": "..." }
```

- `code`：玩家实现的函数（**不含 main**）。服务端从库里取该题的隐藏测试驱动，拼接后编译运行。
- 返回字段：`success`、`status`、`passed`、`total`、`message`，
  失败时附 `compile_output`（编译原文）或 `runtime_output`（运行输出）。
- `status` 取值：`passed` / `failed` / `compile_error` / `runtime_error` / `timeout` / `internal_error`。
- 首次提交会下发匿名 Cookie（`blog_anon`，与每日一题共用），据此累计每题每档的进度（attempts / passed）。

## 4. curl 验证

以下均在本机 `localhost:8080` 执行。**先确认已导 seed（第 2 节第 1 步）**，否则题目查不到。

### 4.0 先验证读接口

```bash
# 章节列表（应有 3 学期、14 章，C1 的 exercise_count=2）
curl -s http://localhost:8080/api/practice/chapters

# C1 题目列表（应有 2 道短题）
curl -s "http://localhost:8080/api/practice/exercises?chapter=1"

# 单题详情（应返回 prompt + tiers.easy/medium/hard）
curl -s http://localhost:8080/api/practice/exercise/1
```

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

### 4.5 第二道题（enum class）正常通过 → 期望 `status=passed, passed=4`

```bash
curl -s -X POST http://localhost:8080/api/practice/submit \
  -H 'Content-Type: application/json' \
  -d '{"exercise_id":2,"tier":"easy","code":"#include <cstring>\nenum class LogLevel { Debug, Info, Warn, Error };\nconst char* level_to_string(LogLevel l) { switch (l) { case LogLevel::Debug: return \"Debug\"; case LogLevel::Info: return \"Info\"; case LogLevel::Warn: return \"Warn\"; default: return \"Error\"; } }\nbool level_from_string(const char* s, LogLevel& out) { if (strcmp(s,\"Debug\")==0){out=LogLevel::Debug;return true;} if (strcmp(s,\"Info\")==0){out=LogLevel::Info;return true;} if (strcmp(s,\"Warn\")==0){out=LogLevel::Warn;return true;} if (strcmp(s,\"Error\")==0){out=LogLevel::Error;return true;} return false; }"}'
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

## 6. 已知待办

1. 扩充题库：`tools/gen_practice_seed.py` 里加 C1 剩余 3 题 + C2-C14 的题（每题三档脚手架 + 隐藏测试驱动）。
2. `tier` 与隐藏用例挂钩（进阶含 easy+medium，挑战全跑）——当前三档共用同一份测试驱动，靠脚手架递减体现难度。
3. 选择题 / 填空题的独立判定（客观题无需沙箱，对答案 / 静态编译即可）。
4. 补 chroot 或 docker 隔离。
5. 数据库题（C11）的临时 schema 隔离方案。
6. 提交限流（代码提交是重操作，防滥用）。
7. 编译超时 / 内存上限按真实题压测定值（当前 10s / 512MB 为暂定）。
