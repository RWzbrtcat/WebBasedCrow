# -*- coding: utf-8 -*-
"""每日一题题库生成器。

把 tools/qbank/ 下的题目数据（Python 列表）汇总、校验、做 SQL 转义，
生成 tools/seed_questions.sql。

用法：python tools/gen_seed.py
"""
import io
import sys
from collections import Counter

sys.path.insert(0, "tools")

from qbank.existing import QUESTIONS as Q_EXISTING
from qbank.cpp import QUESTIONS as Q_CPP
from qbank.linux import QUESTIONS as Q_LINUX
from qbank.mysql import QUESTIONS as Q_MYSQL
from qbank.network import QUESTIONS as Q_NETWORK
from qbank.os import QUESTIONS as Q_OS
from qbank.algo import QUESTIONS as Q_ALGO
from qbank.redis import QUESTIONS as Q_REDIS
from qbank.otherdb import QUESTIONS as Q_OTHERDB

# 期望的最终分布（分类 -> 数量），生成时校验，防止漏题或重复
EXPECTED = {
    "C++": 100,
    "Linux": 90,
    "MySQL": 70,
    "Redis": 40,
    "其他数据库": 40,
    "网络": 55,
    "操作系统": 55,
    "算法": 50,
}

DIFF_LABEL = {1: "基础", 2: "进阶", 3: "困难"}


def sql_quote(s: str) -> str:
    """把 Python 字符串转成 MySQL 字符串字面量（不含外层单引号外的内容）。"""
    return "'" + s.replace("\\", "\\\\").replace("'", "''") + "'"


def validate_sql(sql: str, expected_rows: int) -> None:
    """写文件前做一次「像 MySQL 一样」的扫描，不通过就直接退出。

    起因：曾经漏掉 VALUES 语句结尾的分号，导入时报
        ERROR 1064 ... near 'INSERT INTO questions ...'
    （客户端不认为语句结束，把下一条 INSERT 一起发了过去）。
    只统计「行数/字段数」的校验发现不了这类问题，必须检查语句终止符。

    检查三件事：
      1. 单引号 / 反引号字符串是否闭合（识别 \\\\ 转义与 '' 形式）；
      2. VALUES 里的行数是否等于题目数；
      3. VALUES 语句是否以分号结束。

    第 2 项在扫描过程中顺手统计：只有「非字符串、非注释」状态下、
    位于行首的 ( 才算一行 —— 答案代码块里行首的 ( 处于字符串状态，会被整体跳过。
    """
    n = len(sql)
    i = 0
    rows = 0
    while i < n:
        c = sql[i]
        if c == "'" or c == "`":
            quote = c
            i += 1
            while True:
                if i >= n:
                    raise SystemExit("SQL 中存在未闭合的 %s 字符串" % quote)
                if sql[i] == "\\" and quote == "'":
                    i += 2
                    continue
                if sql[i] == quote:
                    # '' 或 `` 是转义写法，不算结束
                    if i + 1 < n and sql[i + 1] == quote:
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            continue
        if sql.startswith("--", i) and (i + 2 >= n or sql[i + 2] in " \t\r\n"):
            j = sql.find("\n", i)
            i = n if j < 0 else j
            continue
        if sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            if j < 0:
                raise SystemExit("SQL 中存在未闭合的 /* 注释")
            i = j + 2
            continue
        if c == "(" and (i == 0 or sql[i - 1] == "\n"):
            rows += 1
        i += 1

    if rows != expected_rows:
        raise SystemExit("VALUES 行数 %d 与题目数 %d 不一致" % (rows, expected_rows))

    marker = "INSERT INTO questions ("
    if marker not in sql:
        raise SystemExit("生成结果里找不到 " + marker)
    if not sql[: sql.index(marker)].rstrip().endswith(";"):
        raise SystemExit(
            "VALUES 语句结尾缺少分号 —— 导入会报 "
            "ERROR 1064 ... near 'INSERT INTO questions'"
        )


def main() -> str:
    all_q = list(Q_EXISTING) + Q_CPP + Q_LINUX + Q_MYSQL + Q_NETWORK + Q_OS + Q_ALGO + Q_REDIS + Q_OTHERDB

    # 校验结构
    for i, item in enumerate(all_q):
        assert isinstance(item, (tuple, list)) and len(item) == 5, f"第 {i} 条结构不对: {item!r}"
        cat, tags, diff, q, a = item
        assert isinstance(diff, int) and diff in (1, 2, 3), f"第 {i} 条 difficulty 非法: {diff}"
        assert q and q.strip(), f"第 {i} 条题干为空"
        assert a and a.strip(), f"第 {i} 条答案为空"

    # 校验分布
    dist = Counter(c for c, *_ in all_q)
    if dict(dist) != EXPECTED:
        raise SystemExit(f"分布不符：期望 {EXPECTED}\n实际 {dict(dist)}")

    # 校验去重键（分类 + 题干）唯一
    seen = {}
    for i, (cat, tags, diff, q, a) in enumerate(all_q):
        key = (cat, q)
        if key in seen:
            raise SystemExit(f"第 {seen[key]} 条与第 {i} 条题干重复（分类 {cat}）:\n  {q[:60]}")
        seen[key] = i

    # 拼接 VALUES
    buf = io.StringIO()
    for cat, tags, diff, q, a in all_q:
        buf.write("(%s, %s, %d,\n %s,\n %s, 1),\n\n"
                  % (sql_quote(cat), sql_quote(tags), diff, sql_quote(q), sql_quote(a)))

    # 去掉最后一行多余的分隔逗号，并补上语句结束分号。
    # 少了这个分号，mysql 客户端不会结束该语句，会把后面的 INSERT INTO questions
    # 一起发给服务端，报 ERROR 1064 ... near 'INSERT INTO questions'。
    values = buf.getvalue().rstrip(",\n") + ";"

    header = """-- ============================================
-- 每日一题 · 种子题库（C++ / Linux / MySQL / Redis / 其他数据库 / 网络 / 操作系统 / 算法，共 500 道）
-- ============================================
-- 用法：
--     mysql -u <用户> -p <数据库名> < tools/seed_questions.sql
-- 例（账号按实际存在的写，只有 root 就用 root）：
--     mysql -u root -p blogdb < tools/seed_questions.sql
--
-- 说明：
--   0. **可以独立执行，不依赖服务端先启动**。脚本自己会补齐 questions 表（见下面的第 0 步），
--      所以「先导库再编译重启」或「先编译重启再导库」两种顺序都可以。
--   1. 可重复执行：按「分类 + 题干」判重，已存在的题目不会重复插入，
--      因此后续手动改过的题目不会被覆盖。
--   2. 全部以「已发布」状态导入。想先审一遍的话，把最后一步的 status
--      从 1 改成 0，进后台逐条核对后再发布。
--   3. 题干与答案都是 Markdown，答案里的代码块会被前台渲染成高亮代码，
--      ```mermaid 代码块会被渲染成图表。
--   4. 本题库由 tools/gen_seed.py 从 tools/qbank/ 自动生成，改题请改 qbank 下的数据文件，
--      再重跑生成器，不要直接改本文件（会被覆盖）。
-- ============================================

-- ---------- 第 0 步：固定本次会话的字符集 ----------
-- 本文件是 UTF-8 编码。若 mysql 客户端的默认字符集是 latin1（老系统上很常见），
-- 中文会被当成 latin1 解释，这里显式声明一次，彻底摆脱对客户端默认值的依赖。
-- 顺带把结果集也设为 utf8mb4，导入后自己看 SELECT 结果也不会乱码。
SET NAMES utf8mb4;

-- ---------- 第 1 步：确保题表存在，且是 utf8mb4 ----------
-- 这张表平时由服务端启动时自动创建（src/database.cpp 的 initTable）。
-- 此处再写一份 CREATE TABLE IF NOT EXISTS，是为了让本脚本能**独立执行**：
-- 即使服务端还没跑过新版本（题表尚未创建），导入也不会因为
-- 「ERROR 1146 Table 'blogdb.questions' doesn't exist」而中断。
-- 表已存在时它是空操作；两处 DDL 必须保持一致。
CREATE TABLE IF NOT EXISTS questions(
    id INT AUTO_INCREMENT PRIMARY KEY,
    category VARCHAR(50) NOT NULL COMMENT '分类：C++ / Linux / MySQL / Redis / 其他数据库 / 网络 / 操作系统 / 算法',
    tags VARCHAR(200) NOT NULL DEFAULT '' COMMENT '标签，逗号分隔',
    difficulty TINYINT NOT NULL DEFAULT 2 COMMENT '难度：1 基础 / 2 进阶 / 3 困难',
    question TEXT NOT NULL COMMENT '题干（Markdown）',
    answer TEXT NOT NULL COMMENT '答案（Markdown，支持代码块与 mermaid）',
    status TINYINT NOT NULL DEFAULT 0 COMMENT '状态：0 草稿 / 1 已发布',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY idx_questions_cat (category, status)
)ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 幂等矫正字符集：若表是老库以 latin1 建出来的，中文会在写入时被静默替换成 '?'，
-- 且不可逆。这里先统一转成 utf8mb4，避免后续插入再被吃掉。已是 utf8mb4 时为空操作。
ALTER TABLE questions CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TEMPORARY TABLE seed_questions LIKE questions;

INSERT INTO seed_questions (category, tags, difficulty, question, answer, status) VALUES

"""

    footer = """

INSERT INTO questions (category, tags, difficulty, question, answer, status)
SELECT s.category, s.tags, s.difficulty, s.question, s.answer, 1
FROM seed_questions s
WHERE NOT EXISTS (
    SELECT 1 FROM questions q
    WHERE q.category = s.category AND q.question = s.question
);

DROP TEMPORARY TABLE seed_questions;

-- 导入结果确认
SELECT category, COUNT(*) AS total FROM questions WHERE status = 1 GROUP BY category ORDER BY category;
"""

    sql = header + values + footer
    validate_sql(sql, len(all_q))
    return sql


if __name__ == "__main__":
    sql = main()
    # newline="\n"：Windows 上文本模式会把 \n 写成 \r\n，而 \r 一旦落在字符串
    # 字面量里会被原样写进数据库（每条答案尾部多一个回车）。显式锁死 LF。
    with open("tools/seed_questions.sql", "w", encoding="utf-8", newline="\n") as f:
        f.write(sql)
    dist = Counter(c for c, *_ in (list(Q_EXISTING) + Q_CPP + Q_LINUX + Q_MYSQL + Q_NETWORK + Q_OS + Q_ALGO + Q_REDIS + Q_OTHERDB))
    print("生成完成，共 %d 道题：" % sum(dist.values()))
    for k in sorted(dist):
        print("  %s: %d" % (k, dist[k]))
    print("已写入 tools/seed_questions.sql（%d 字节）" % len(sql.encode("utf-8")))
