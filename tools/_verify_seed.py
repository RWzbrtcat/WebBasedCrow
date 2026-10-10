# -*- coding: utf-8 -*-
"""对生成的 tools/seed_questions.sql 做「客户端行为级」校验。

模拟 mysql 客户端的语句切分（quote-aware、按 ; 断句），再对每条语句做检查：
  1. 语句条数与预期一致；
  2. VALUES 语句能解析出 500 行、每行 6 字段，且与 Python 源数据逐条一致；
  3. 全文件没有未闭合的字符串；
  4. 每条语句都以 ; 结束（最后一条也要）。

用法：python tools/_verify_seed.py
"""
import sys

sys.path.insert(0, "tools")

from _extract_existing import parse_value  # noqa: E402

SQL_PATH = "tools/seed_questions.sql"


def split_like_client(s: str):
    """按 mysql 客户端的规则切分语句：字符串内的 ; 不算结束。"""
    n = len(s)
    i = 0
    start = 0
    stmts = []
    while i < n:
        c = s[i]
        if c in ("'", '"', "`"):
            q = c
            i += 1
            while True:
                if i >= n:
                    raise SystemExit("未闭合的 %s 字符串，位置 %d" % (q, i))
                if s[i] == "\\":
                    i += 2
                    continue
                if s[i] == q:
                    if i + 1 < n and s[i + 1] == q:
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            continue
        if c == "-" and s.startswith("--", i) and (i + 2 >= n or s[i + 2] in " \t\r\n"):
            j = s.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "#":
            j = s.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and s.startswith("/*", i):
            j = s.find("*/", i + 2)
            if j < 0:
                raise SystemExit("未闭合的 /* 注释")
            i = j + 2
            continue
        if c == ";":
            stmts.append(s[start : i + 1])
            start = i + 1
        i += 1
    tail = s[start:].strip()
    if tail:
        stmts.append(tail)
    return stmts


def main() -> int:
    from collections import Counter

    from qbank.algo import QUESTIONS as A
    from qbank.cpp import QUESTIONS as C
    from qbank.existing import QUESTIONS as E
    from qbank.linux import QUESTIONS as L
    from qbank.mysql import QUESTIONS as M
    from qbank.network import QUESTIONS as N
    from qbank.os import QUESTIONS as O
    from qbank.otherdb import QUESTIONS as D
    from qbank.redis import QUESTIONS as R

    allq = list(E) + C + L + M + N + O + A + R + D

    # 必须按字节读：文本模式会用「通用换行」把 \r\n 悄悄还原成 \n，
    # 于是 CRLF 这个隐患在校验里永远看不出来。但 \r 落在字符串字面量里
    # 会被原样存进数据库，所以这里直接查原始字节。
    raw = open(SQL_PATH, "rb").read()
    crlf = raw.count(b"\r\n")
    lone_cr = raw.count(b"\r") - crlf
    print("换行符: CRLF %d 处, 孤立 CR %d 处 %s"
          % (crlf, lone_cr, "(正常)" if crlf + lone_cr == 0 else "(!! 应全部为 LF)"))
    sql = raw.decode("utf-8")

    stmts = split_like_client(sql)
    print("语句条数:", len(stmts))
    for k, st in enumerate(stmts, 1):
        head = st.strip().splitlines()[0][:70]
        ok = st.rstrip().endswith(";")
        print("  #%d %-4s %s" % (k, ";" if ok else "无;", head))
        if not ok:
            print("     !! 这条语句没有以分号结束")

    vals = next(st for st in stmts if "INSERT INTO seed_questions" in st)
    i = vals.index("VALUES") + len("VALUES")
    n = len(vals)
    while i < n and vals[i] != "(":
        i += 1
    rows = []
    while i < n and vals[i] == "(":
        fields, i = parse_value(vals, i)
        rows.append(fields)
        while i < n and vals[i] in " \t\r\n,":
            i += 1

    print("VALUES 行数:", len(rows))
    print("每条字段数:", sorted({len(r) for r in rows}))
    bad = 0
    for idx, (r, q) in enumerate(zip(rows, allq)):
        cat, tags, diff, question, ans, status = r
        if (cat, tags, diff, question, ans) != q:
            bad += 1
            if bad <= 3:
                print("  不一致 #%d: %r" % (idx, q[3][:40]))
    print("与源数据不一致数:", bad)
    print("分类分布:", dict(Counter(r[0] for r in rows)))
    print("难度分布:", dict(Counter(r[2] for r in rows)))
    print("去重键重复:", len(rows) - len({(r[0], r[3]) for r in rows}))

    ok_all = (
        len(stmts) == 8
        and len(rows) == 500
        and {len(r) for r in rows} == {6}
        and bad == 0
        and all(st.rstrip().endswith(";") for st in stmts)
        and crlf + lone_cr == 0
    )
    print("总体结论:", "通过" if ok_all else "未通过")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
