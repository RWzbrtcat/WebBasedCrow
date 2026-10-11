#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# 练习闯关 · seed 题库生成器
# 生成 tools/seed_practice.sql（14 个章节 + 写代码题）。
#
# 用法：
#     python tools/gen_practice_seed.py
# 导入：
#     mysql -u root -p blogdb < tools/seed_practice.sql
#
# 说明：
#   - 本脚本内嵌章节与题目数据（题多了再拆 tools/qbank 目录，与每日一题一致）。
#   - 幂等：固定 id + INSERT IGNORE，重复导入不覆盖手改内容。
#   - 三张表的 DDL 与 src/database.cpp 的 initTable 保持一致（改表结构两处都要动）。
#   - 生成器负责 SQL 转义：单引号 -> ''，反斜杠 -> \\（C++ 代码里的 \n 靠这个保住）。
#   - 写文件用 newline="\n"，杜绝 Windows CRLF 混入（历史坑：\r 落进字符串字面量）。
# ============================================================

import io
import os

# ---------- 章节数据 ----------
# (id, 学期名, 标题, 章内排序)
CHAPTERS = [
    (1, '第一学期 · 语言地基', '现代语法糖', 1),
    (2, '第一学期 · 语言地基', '移动语义与完美转发', 2),
    (3, '第一学期 · 语言地基', '智能指针与 RAII', 3),
    (4, '第一学期 · 语言地基', 'Lambda 与函数式', 4),
    (5, '第一学期 · 语言地基', '模板与元编程基础', 5),
    (6, '第一学期 · 语言地基', '现代工具类型', 6),
    (7, '第二学期 · 后端应用', 'STL 容器与算法', 7),
    (8, '第二学期 · 后端应用', '文件操作与流', 8),
    (9, '第二学期 · 后端应用', '多线程与并发', 9),
    (10, '第二学期 · 后端应用', '网络编程', 10),
    (11, '第二学期 · 后端应用', '数据库交互', 11),
    (12, '第三学期 · 进阶工程', 'constexpr 与编译期计算', 12),
    (13, '第三学期 · 进阶工程', 'C++20 高级特性', 13),
    (14, '第三学期 · 进阶工程', '模块与工程实践', 14),
]

# ---------- 题目数据 ----------
# 每道题一个 dict。test_driver / starter_* 都是 C++ 源码，用 raw string（r"""）保存，
# 这样 C++ 里的 \n 等转义序列不会被 Python 提前解释。
EXERCISES = [
    {
        'id': 1,
        'chapter_id': 1,
        'type': 'short',
        'title': '短题 1 · auto 与 decltype 推导',
        'sort_order': 1,
        'prompt': (
            '实现两个函数，验证 `auto` 的类型推导规则：\n\n'
            '1. `get_ref()`：返回全局变量 `g_value` 的**引用**\n'
            '2. `get_value()`：返回全局变量 `g_value` 的**值拷贝**\n\n'
            '全局变量 `int g_value = 42;` 已由题目提供，请勿修改。\n\n'
            '> 考点：`auto&` 保留引用，`auto` 丢失引用与顶层 const。\n'
        ),
        'starter_easy': r'''// 全局变量（题目已提供，请勿修改）
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
''',
        'starter_medium': r'''// 进阶：只给接口签名，自己补全函数体
int g_value = 42;

int& get_ref() {
    // TODO: 返回 g_value 的引用
}

int get_value() {
    // TODO: 返回 g_value 的值拷贝
}

// 只实现函数，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''// 挑战：用 decltype(auto) 让返回值类别与表达式完全一致
int g_value = 42;

// TODO: 用 decltype(auto) 实现 get_ref（返回引用）与 get_value（返回拷贝）

// 只实现函数，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>

// 隐藏测试驱动（题目侧提供，玩家不可见）
int main() {
    int fail = 0;
    // 用例1：get_ref 返回引用，赋值能改 g_value
    get_ref() = 100;
    if (g_value != 100) {
        std::printf("FAIL: get_ref() 应返回引用，赋值应改变 g_value\n");
        ++fail;
    }
    // 用例2：get_value 返回拷贝，改返回值不影响 g_value
    int v = get_value();
    v = 999;
    if (g_value != 100) {
        std::printf("FAIL: get_value() 应返回拷贝，修改返回值不应影响 g_value\n");
        ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 2,
        'chapter_id': 1,
        'type': 'short',
        'title': '短题 2 · enum class 类型安全',
        'sort_order': 2,
        'prompt': (
            '用 `enum class` 定义一个日志级别，并实现它与字符串的双向转换：\n\n'
            '1. `enum class LogLevel { Debug, Info, Warn, Error };`\n'
            '2. `const char* level_to_string(LogLevel level)`：返回级别的字符串表示\n'
            '3. `bool level_from_string(const char* s, LogLevel& out)`：从字符串解析，非法字符串返回 `false`\n\n'
            '> 考点：`enum class` 是强类型、不会隐式转 `int`；序列化要处理非法输入。\n'
        ),
        'starter_easy': r'''#include <cstring>

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
''',
        'starter_medium': r'''#include <cstring>

// TODO: 定义 enum class LogLevel { Debug, Info, Warn, Error }

// 已给签名，补全实现
const char* level_to_string(LogLevel level) {
    // TODO
}

bool level_from_string(const char* s, LogLevel& out) {
    // TODO
}

// 只实现函数，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <cstring>

// 需求：定义日志级别枚举 LogLevel（Debug/Info/Warn/Error），
// 并实现：
//   const char* level_to_string(LogLevel level)
//   bool level_from_string(const char* s, LogLevel& out)
// 接口名与签名必须与上述一致，隐藏测试会直接调用。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <cstring>

int main() {
    int fail = 0;
    // 用例1：Debug -> "Debug"
    if (std::strcmp(level_to_string(LogLevel::Debug), "Debug") != 0) {
        std::printf("FAIL: level_to_string(LogLevel::Debug) 应返回 \"Debug\"\n");
        ++fail;
    }
    // 用例2：Error -> "Error"
    if (std::strcmp(level_to_string(LogLevel::Error), "Error") != 0) {
        std::printf("FAIL: level_to_string(LogLevel::Error) 应返回 \"Error\"\n");
        ++fail;
    }
    // 用例3：解析 "Warn" -> LogLevel::Warn
    LogLevel l;
    if (!level_from_string("Warn", l) || l != LogLevel::Warn) {
        std::printf("FAIL: level_from_string(\"Warn\") 应解析为 LogLevel::Warn\n");
        ++fail;
    }
    // 用例4：非法字符串应返回 false
    LogLevel bad;
    if (level_from_string("Nope", bad)) {
        std::printf("FAIL: level_from_string(\"Nope\") 应返回 false\n");
        ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 4,
        'time_limit_ms': 2000,
    },
]

# ---------- 三张表 DDL（与 src/database.cpp initTable 保持一致） ----------
DDL = """CREATE TABLE IF NOT EXISTS practice_chapters(
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
"""


def sql_literal(s):
    """把字符串转成 SQL 单引号字面量：反斜杠 -> \\，单引号 -> ''。"""
    return "'" + s.replace('\\', '\\\\').replace("'", "''") + "'"


def build():
    out = []
    out.append('-- ============================================================')
    out.append('-- 练习闯关 · seed 题库（14 章节 + 写代码题，由 gen_practice_seed.py 生成）')
    out.append('-- 用法：mysql -u root -p blogdb < tools/seed_practice.sql')
    out.append('-- 幂等：固定 id + INSERT IGNORE，重复导入不覆盖手改内容。')
    out.append('-- 注意：本文件是 UTF-8，先 SET NAMES utf8mb4 避免中文乱码。')
    out.append('-- ============================================================')
    out.append('')
    out.append('SET NAMES utf8mb4;')
    out.append('')
    out.append('-- ---------- 第 1 步：确保三张表存在 ----------')
    out.append(DDL.rstrip())
    out.append('')
    out.append('-- ---------- 第 2 步：插入 14 个章节 ----------')
    for cid, sem, title, sort in CHAPTERS:
        out.append(
            'INSERT IGNORE INTO practice_chapters (id, semester, title, sort_order, status) VALUES '
            f'({cid}, {sql_literal(sem)}, {sql_literal(title)}, {sort}, 1);'
        )
    out.append('')
    out.append('-- ---------- 第 3 步：插入题目 ----------')
    for e in EXERCISES:
        out.append(
            'INSERT IGNORE INTO practice_exercises '
            '(id, chapter_id, type, title, prompt, sort_order, starter_easy, starter_medium, '
            'starter_hard, test_driver, total_cases, time_limit_ms, status) VALUES ('
            f'{e["id"]}, {e["chapter_id"]}, {sql_literal(e["type"])}, {sql_literal(e["title"])}, '
            f'{sql_literal(e["prompt"])}, {e["sort_order"]}, '
            f'{sql_literal(e["starter_easy"])}, {sql_literal(e["starter_medium"])}, '
            f'{sql_literal(e["starter_hard"])}, {sql_literal(e["test_driver"])}, '
            f'{e["total_cases"]}, {e["time_limit_ms"]}, 1);'
        )
    out.append('')
    return '\n'.join(out)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(here, 'seed_practice.sql')
    content = build()
    with io.open(target, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)

    # 自检：无 CRLF；按「子串」计数（不能用 count(';')——test_driver 里的 C++ 代码
    # 满是分号，会被误算成 SQL 语句；这是历史踩过的坑，务必用子串）。
    raw = content.encode('utf-8')
    assert b'\r' not in raw, '生成的 SQL 里出现了 CRLF（\\r），禁止'
    n_chapters = content.count('INSERT IGNORE INTO practice_chapters')
    n_exercises = content.count('INSERT IGNORE INTO practice_exercises')
    assert n_chapters == len(CHAPTERS), f'章节 INSERT 数不符：{n_chapters} != {len(CHAPTERS)}'
    assert n_exercises == len(EXERCISES), f'题目 INSERT 数不符：{n_exercises} != {len(EXERCISES)}'
    assert 'practice_progress' in content, '缺 practice_progress 表'
    print(f'OK: 生成 {target}（{len(CHAPTERS)} 章节 / {len(EXERCISES)} 题）')


if __name__ == '__main__':
    main()
