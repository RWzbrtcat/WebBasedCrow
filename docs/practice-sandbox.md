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

## 7. 题库数据 / 结构变更后的重导流程（运维备忘）

**适用场景**：改了下面任意一项，都需要按本流程让线上生效——
- 题库**数据**变更：`tools/seed_practice.sql`（如章节改名「第一学期→第一章节」、题面固化）。
- 题库**结构**变更：`practice_exercises` 等表新增列（如 `question`）。
- **C++ 代码**变更：`src/database.cpp`（详情查询、建表/迁移）。

> 前端 `static/` 是运行时直读、**无需重新编译**，但必须保证服务器部署目录是最新（git pull 覆盖）。

### 7.1 完整顺序（关键：编译+重启 必须在 重导 之前）

```bash
# —— 本地（开发机）——
git push origin dev-game

# —— 服务器 ——
cd <项目目录>
git pull origin dev-game          # 拉取最新代码（含 static/ 前端、src/ 后端、tools/ 题库）

# 1) 编译（若 CMakeLists.txt 有改动，先 cmake -B build 再 build）
cmake --build build

# 2) 重启（服务启动时自动执行 initTable：
#    · 旧表缺列则用 ALTER 补列，例如 question 列就是这一步加上的
#    · 三张表若不存在则自动建表）
sudo systemctl restart blog.service

# 3) 重导题库（必须在重启之后！此时 question 列已存在，INSERT 才不会报 Unknown column）
mysql -u root -p blogdb < tools/seed_practice.sql
```

### 7.2 为什么顺序不能反

`tools/seed_practice.sql` 的 `INSERT` 是**显式列出 `question` 列**的 upsert。若服务器还在跑**旧二进制**（没有 `question` 列），重导会直接报：

```
ERROR 1054 (42S22): Unknown column 'question' in 'field list'
```

而 `question` 列由 `src/database.cpp` 的 `columnExists + ALTER` 迁移在**服务启动**时补齐。所以必须先 `cmake --build build` + `restart`，让迁移跑完、列存在，再导数据。

### 7.3 验证导入结果

```bash
# 章节名已更新为「第一/二/三章节」
mysql -u root -p blogdb -e "SELECT id, semester FROM practice_chapters ORDER BY id;"

# 题面固化：抽查某道固化题带有 question（例如 id 14 是空白+说明）
mysql -u root -p blogdb -e "SELECT id, LEFT(question,40) FROM practice_exercises WHERE id IN (14,42) AND question IS NOT NULL;"
```

### 7.4 库名说明

默认库名 `blogdb`（见 `src/main.cpp` 的 `envStr("MYSQL_DB", "blogdb")`）。若服务器用环境变量 `MYSQL_DB` 指定了别的库名，上面所有 `blogdb` 处替换为实际库名即可。

### 7.5 最小重导（仅数据、无结构/代码变更）

若只是 `seed_practice.sql` 数据变了、**没有**改表结构也没有改 C++ 代码：可跳过编译，但**仍需重启一次**让线上拿到最新 `static/` 前端（前端是运行时直读），然后直接导库：

```bash
git pull origin dev-game
sudo systemctl restart blog.service   # 让前端 static/ 生效（即使没改 C++）
mysql -u root -p blogdb < tools/seed_practice.sql
```
