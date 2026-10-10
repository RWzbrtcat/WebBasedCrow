# -*- coding: utf-8 -*-
"""一次性脚本：把现有 seed_questions.sql 里的题目无损提取成 Python 数据。

用法：python tools/_extract_existing.py
产出：tools/qbank/existing.py（QUESTIONS = [(category, tags, difficulty, question, answer), ...]）

提取会做反向转义：SQL 里的 '' -> ' ，\\ -> \\ ，保证 question 逐字还原，
从而与数据库中已导入的题目按「分类+题干」精确去重。
"""
import re

SRC = "tools/seed_questions.sql"
OUT = "tools/qbank/existing.py"


def split_statements(src):
    """感知字符串与行注释地把 SQL 切成语句。"""
    stmts, cur, i, n, instr = [], [], 0, len(src), False
    while i < n:
        c = src[i]
        if instr:
            if c == "\\":
                cur.append(c)
                if i + 1 < n:
                    cur.append(src[i + 1])
                    i += 2
                    continue
                i += 1
                continue
            if c == "'":
                if i + 1 < n and src[i + 1] == "'":
                    cur.append("''")
                    i += 2
                    continue
                instr = False
            cur.append(c)
            i += 1
            continue
        if c == "'":
            instr = True
            cur.append(c)
            i += 1
            continue
        if c == "-" and src.startswith("--", i):
            j = src.find("\n", i)
            if j == -1:
                break
            cur.append(src[i:j])
            i = j
            continue
        if c == ";":
            stmts.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    return stmts


def parse_value(s, i):
    """从 s[i] 处（应为 '('）解析一条记录，返回 (字段列表, 下一个位置)。"""
    assert s[i] == "(", f"expected '(' at {i}"
    fields = []
    i += 1
    n = len(s)
    while i < n:
        # 跳过空白与逗号
        while i < n and (s[i] in " \t\r\n,"):
            i += 1
        if i >= n or s[i] == ")":
            return fields, i + 1
        if s[i] == "'":
            # 字符串字面量
            i += 1
            buf = []
            while i < n:
                if s[i] == "\\":
                    nxt = s[i + 1] if i + 1 < n else ""
                    if nxt == "n":
                        buf.append("\n")
                    elif nxt == "t":
                        buf.append("\t")
                    elif nxt == "\\":
                        buf.append("\\")
                    elif nxt == "'":
                        buf.append("'")
                    elif nxt == "0":
                        buf.append("\0")
                    else:
                        buf.append(nxt)
                    i += 2
                    continue
                if s[i] == "'":
                    if i + 1 < n and s[i + 1] == "'":
                        buf.append("'")
                        i += 2
                        continue
                    i += 1
                    break
                buf.append(s[i])
                i += 1
            fields.append("".join(buf))
        elif s[i].isdigit():
            j = i
            while j < n and s[j].isdigit():
                j += 1
            fields.append(int(s[i:j]))
            i = j
        else:
            i += 1
    return fields, i


def main():
    src = open(SRC, encoding="utf-8").read()
    stmts = split_statements(src)
    insert = next(s for s in stmts if "INSERT INTO seed_questions" in s)
    # 定位 VALUES 之后的第一个 '('
    vpos = insert.index("VALUES") + len("VALUES")
    i = vpos
    while i < len(insert) and insert[i] != "(":
        i += 1

    rows = []
    while i < len(insert):
        if insert[i] != "(":
            i += 1
            continue
        fields, nxt = parse_value(insert, i)
        if len(fields) == 6:
            cat, tags, diff, q, a, _st = fields
            rows.append((cat, tags, int(diff), q, a))
        i = nxt

    # 写 Python 文件
    lines = [
        "# -*- coding: utf-8 -*-",
        "# 本文件由 tools/_extract_existing.py 自动生成，请勿手改。",
        "# 字段：(category, tags, difficulty, question, answer)",
        "QUESTIONS = [",
    ]
    for cat, tags, diff, q, a in rows:
        lines.append("    (%s, %s, %d, %r, %r)," % (repr(cat), repr(tags), diff, q, a))
    lines.append("]")
    lines.append("")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    from collections import Counter
    c = Counter(r[0] for r in rows)
    print("提取到 %d 道题：" % len(rows))
    for k, v in sorted(c.items()):
        print("  %s: %d" % (k, v))


if __name__ == "__main__":
    main()
