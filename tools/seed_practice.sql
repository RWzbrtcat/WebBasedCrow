-- ============================================================
-- 练习闯关 · seed 题库（14 章节 + 写代码题，由 gen_practice_seed.py 生成）
-- 用法：mysql -u root -p blogdb < tools/seed_practice.sql
-- 幂等：固定 id + INSERT IGNORE，重复导入不覆盖手改内容。
-- 注意：本文件是 UTF-8，先 SET NAMES utf8mb4 避免中文乱码。
-- ============================================================

SET NAMES utf8mb4;

-- ---------- 第 1 步：确保三张表存在 ----------
CREATE TABLE IF NOT EXISTS practice_chapters(
    id INT AUTO_INCREMENT PRIMARY KEY,
    semester VARCHAR(50) NOT NULL DEFAULT '' COMMENT '学期分组',
    title VARCHAR(128) NOT NULL COMMENT '章节标题',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '0草稿/1发布'
)ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS practice_exercises(
    id INT AUTO_INCREMENT PRIMARY KEY,
    chapter_id INT NOT NULL COMMENT '所属章节',
    type VARCHAR(10) NOT NULL DEFAULT 'short' COMMENT 'short/boss',
    title VARCHAR(256) NOT NULL COMMENT '题目标题',
    prompt TEXT NOT NULL COMMENT '题目需求(markdown)',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '章内排序',
    starter_easy TEXT COMMENT '入门脚手架',
    starter_medium TEXT COMMENT '进阶脚手架',
    starter_hard TEXT COMMENT '挑战脚手架',
    test_driver TEXT NOT NULL COMMENT '隐藏测试驱动(含main)',
    total_cases INT NOT NULL DEFAULT 1 COMMENT '用例数',
    time_limit_ms INT NOT NULL DEFAULT 2000 COMMENT '运行时限',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '0草稿/1发布',
    INDEX idx_practice_chapter (chapter_id)
)ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS practice_progress(
    owner_token VARCHAR(64) NOT NULL COMMENT '匿名访客标识',
    exercise_id INT NOT NULL COMMENT '题目ID',
    tier VARCHAR(10) NOT NULL COMMENT 'easy/medium/hard',
    passed TINYINT NOT NULL DEFAULT 0 COMMENT '是否通关(0/1)',
    attempts INT NOT NULL DEFAULT 0 COMMENT '尝试次数',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (owner_token, exercise_id, tier)
)ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- 第 2 步：插入 14 个章节 ----------
INSERT IGNORE INTO practice_chapters (id, semester, title, sort_order, status) VALUES (1, '第一学期 · 语言地基', '现代语法糖', 1, 1);
INSERT IGNORE INTO practice_chapters (id, semester, title, sort_order, status) VALUES (2, '第一学期 · 语言地基', '移动语义与完美转发', 2, 1);
INSERT IGNORE INTO practice_chapters (id, semester, title, sort_order, status) VALUES (3, '第一学期 · 语言地基', '智能指针与 RAII', 3, 1);
INSERT IGNORE INTO practice_chapters (id, semester, title, sort_order, status) VALUES (4, '第一学期 · 语言地基', 'Lambda 与函数式', 4, 1);
INSERT IGNORE INTO practice_chapters (id, semester, title, sort_order, status) VALUES (5, '第一学期 · 语言地基', '模板与元编程基础', 5, 1);
INSERT IGNORE INTO practice_chapters (id, semester, title, sort_order, status) VALUES (6, '第一学期 · 语言地基', '现代工具类型', 6, 1);
INSERT IGNORE INTO practice_chapters (id, semester, title, sort_order, status) VALUES (7, '第二学期 · 后端应用', 'STL 容器与算法', 7, 1);
INSERT IGNORE INTO practice_chapters (id, semester, title, sort_order, status) VALUES (8, '第二学期 · 后端应用', '文件操作与流', 8, 1);
INSERT IGNORE INTO practice_chapters (id, semester, title, sort_order, status) VALUES (9, '第二学期 · 后端应用', '多线程与并发', 9, 1);
INSERT IGNORE INTO practice_chapters (id, semester, title, sort_order, status) VALUES (10, '第二学期 · 后端应用', '网络编程', 10, 1);
INSERT IGNORE INTO practice_chapters (id, semester, title, sort_order, status) VALUES (11, '第二学期 · 后端应用', '数据库交互', 11, 1);
INSERT IGNORE INTO practice_chapters (id, semester, title, sort_order, status) VALUES (12, '第三学期 · 进阶工程', 'constexpr 与编译期计算', 12, 1);
INSERT IGNORE INTO practice_chapters (id, semester, title, sort_order, status) VALUES (13, '第三学期 · 进阶工程', 'C++20 高级特性', 13, 1);
INSERT IGNORE INTO practice_chapters (id, semester, title, sort_order, status) VALUES (14, '第三学期 · 进阶工程', '模块与工程实践', 14, 1);

-- ---------- 第 3 步：插入题目 ----------
INSERT IGNORE INTO practice_exercises (id, chapter_id, type, title, prompt, sort_order, starter_easy, starter_medium, starter_hard, test_driver, total_cases, time_limit_ms, status) VALUES (1, 1, 'short', '短题 1 · auto 与 decltype 推导', '实现两个函数，验证 `auto` 的类型推导规则：

1. `get_ref()`：返回全局变量 `g_value` 的**引用**
2. `get_value()`：返回全局变量 `g_value` 的**值拷贝**

全局变量 `int g_value = 42;` 已由题目提供，请勿修改。

> 考点：`auto&` 保留引用，`auto` 丢失引用与顶层 const。
', 1, '// 全局变量（题目已提供，请勿修改）
int g_value = 42;

// TODO: 补全返回类型 —— get_ref 应返回 g_value 的「引用」
// 提示：返回类型写 int&，函数体 return g_value;
____ get_ref() {
    return g_value;
}

// TODO: 补全返回类型 —— get_value 应返回 g_value 的「值拷贝」
// 提示：返回类型写 int（值），函数体 return g_value;
____ get_value() {
    return g_value;
}

// 只实现函数，不要写 main（隐藏测试会提供）
', '// 进阶：只给接口签名，自己补全函数体
int g_value = 42;

int& get_ref() {
    // TODO: 返回 g_value 的引用
}

int get_value() {
    // TODO: 返回 g_value 的值拷贝
}

// 只实现函数，不要写 main（隐藏测试会提供）
', '// 挑战：用 decltype(auto) 让返回值类别与表达式完全一致
int g_value = 42;

// TODO: 用 decltype(auto) 实现 get_ref（返回引用）与 get_value（返回拷贝）

// 只实现函数，不要写 main（隐藏测试会提供）
', '#include <cstdio>

// 隐藏测试驱动（题目侧提供，玩家不可见）
int main() {
    int fail = 0;
    // 用例1：get_ref 返回引用，赋值能改 g_value
    get_ref() = 100;
    if (g_value != 100) {
        std::printf("FAIL: get_ref() 应返回引用，赋值应改变 g_value\\n");
        ++fail;
    }
    // 用例2：get_value 返回拷贝，改返回值不影响 g_value
    int v = get_value();
    v = 999;
    if (g_value != 100) {
        std::printf("FAIL: get_value() 应返回拷贝，修改返回值不应影响 g_value\\n");
        ++fail;
    }
    if (fail == 0) std::printf("PASS\\n");
    return fail;
}
', 2, 2000, 1);
INSERT IGNORE INTO practice_exercises (id, chapter_id, type, title, prompt, sort_order, starter_easy, starter_medium, starter_hard, test_driver, total_cases, time_limit_ms, status) VALUES (2, 1, 'short', '短题 2 · enum class 类型安全', '用 `enum class` 定义一个日志级别，并实现它与字符串的双向转换：

1. `enum class LogLevel { Debug, Info, Warn, Error };`
2. `const char* level_to_string(LogLevel level)`：返回级别的字符串表示
3. `bool level_from_string(const char* s, LogLevel& out)`：从字符串解析，非法字符串返回 `false`

> 考点：`enum class` 是强类型、不会隐式转 `int`；序列化要处理非法输入。
', 2, '#include <cstring>

// 日志级别（已提供，请勿修改）
enum class LogLevel { Debug, Info, Warn, Error };

// TODO: 补全实现 —— 返回 level 对应的字符串
const char* level_to_string(LogLevel level) {
    // 用 switch 返回 "Debug" / "Info" / "Warn" / "Error"
}

// TODO: 补全实现 —— 从字符串解析；非法返回 false
bool level_from_string(const char* s, LogLevel& out) {
    // 用 strcmp 逐个比对，非法字符串返回 false
}

// 只实现函数，不要写 main（隐藏测试会提供）
', '#include <cstring>

// TODO: 定义 enum class LogLevel { Debug, Info, Warn, Error }

// 已给签名，补全实现
const char* level_to_string(LogLevel level) {
    // TODO
}

bool level_from_string(const char* s, LogLevel& out) {
    // TODO
}

// 只实现函数，不要写 main（隐藏测试会提供）
', '#include <cstring>

// 需求：定义日志级别枚举 LogLevel（Debug/Info/Warn/Error），
// 并实现：
//   const char* level_to_string(LogLevel level)
//   bool level_from_string(const char* s, LogLevel& out)
// 接口名与签名必须与上述一致，隐藏测试会直接调用。

// 只实现，不要写 main（隐藏测试会提供）
', '#include <cstdio>
#include <cstring>

int main() {
    int fail = 0;
    // 用例1：Debug -> "Debug"
    if (std::strcmp(level_to_string(LogLevel::Debug), "Debug") != 0) {
        std::printf("FAIL: level_to_string(LogLevel::Debug) 应返回 \\"Debug\\"\\n");
        ++fail;
    }
    // 用例2：Error -> "Error"
    if (std::strcmp(level_to_string(LogLevel::Error), "Error") != 0) {
        std::printf("FAIL: level_to_string(LogLevel::Error) 应返回 \\"Error\\"\\n");
        ++fail;
    }
    // 用例3：解析 "Warn" -> LogLevel::Warn
    LogLevel l;
    if (!level_from_string("Warn", l) || l != LogLevel::Warn) {
        std::printf("FAIL: level_from_string(\\"Warn\\") 应解析为 LogLevel::Warn\\n");
        ++fail;
    }
    // 用例4：非法字符串应返回 false
    LogLevel bad;
    if (level_from_string("Nope", bad)) {
        std::printf("FAIL: level_from_string(\\"Nope\\") 应返回 false\\n");
        ++fail;
    }
    if (fail == 0) std::printf("PASS\\n");
    return fail;
}
', 4, 2000, 1);
