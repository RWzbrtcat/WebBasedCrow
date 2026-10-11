#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# 练习闯关题库静态校验
#
# 用法：python tools/_verify_practice_seed.py
#
# 背景：本机无 C++ 编译器，无法真正编译 test_driver。括号配平
#   （词法级：跳过 //、/* */、R"()"、字符串、字符字面量）是唯一
#   能做的 C++ 语法级验证；再叠加 main 唯一、客观题答案完整性、
#   id 连续性、章内排序、FAIL 用例数一致等结构性校验。
#   编译与运行验证须在服务器做（用户负责）。
# ============================================================

import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gen_practice_seed import EXERCISES, CHAPTERS  # noqa: E402


def scan_brace_balance(code):
    """C++ 词法级括号配平。返回 (bool, 描述)。

    只统计「代码区」的 () {} []：跳过 // 行注释、/* */ 块注释、
    "..." 字符串、'...' 字符、R"(...)" / R"delim(...)delim" 原始字符串。
    """
    i = 0
    n = len(code)
    stack = []
    pairs = {')': '(', '}': '{', ']': '['}

    while i < n:
        c = code[i]
        # 行注释 //
        if c == '/' and i + 1 < n and code[i + 1] == '/':
            j = code.find('\n', i)
            i = n if j == -1 else j
            continue
        # 块注释 /* */
        if c == '/' and i + 1 < n and code[i + 1] == '*':
            j = code.find('*/', i + 2)
            if j == -1:
                return False, '未闭合的块注释'
            i = j + 2
            continue
        # 原始字符串 R"(...)" 或 R"delim(...)delim"
        if c == 'R' and i + 1 < n and code[i + 1] == '"':
            j = i + 2
            delim = ''
            while j < n and code[j] != '(':
                delim += code[j]
                j += 1
            if j >= n:
                return False, 'R 原始字符串缺少 ('
            close = ')' + delim + '"'
            k = code.find(close, j + 1)
            if k == -1:
                return False, '未闭合的原始字符串'
            i = k + len(close)
            continue
        # 字符串字面量 "..."
        if c == '"':
            j = i + 1
            while j < n:
                if code[j] == '\\':
                    j += 2
                    continue
                if code[j] == '"':
                    break
                j += 1
            if j >= n:
                return False, '未闭合的字符串'
            i = j + 1
            continue
        # 字符字面量 '...'
        if c == "'":
            j = i + 1
            while j < n:
                if code[j] == '\\':
                    j += 2
                    continue
                if code[j] == "'":
                    break
                j += 1
            if j >= n:
                return False, '未闭合的字符'
            i = j + 1
            continue
        # 括号
        if c in '({[':
            stack.append(c)
        elif c in ')}]':
            if not stack or stack[-1] != pairs[c]:
                return False, '括号不匹配：%s 无对应开括号' % c
            stack.pop()
        i += 1

    if stack:
        return False, '未闭合的开括号：' + ''.join(stack)
    return True, ''


def main():
    failed = 0

    # 1. id 连续性 + 题数（154 = 14 章 × 11 题）
    ids = sorted(e['id'] for e in EXERCISES)
    if ids != list(range(1, 155)):
        missing = [x for x in range(1, 155) if x not in ids]
        dup = [x for x, c in Counter(e['id'] for e in EXERCISES).items() if c > 1]
        print('[FAIL] id 不连续：缺失 %s，重复 %s' % (missing, dup))
        failed += 1
    else:
        print('[PASS] id 连续 1..154，共 %d 道' % len(EXERCISES))

    # 2. 章节题数与章内排序
    by_chapter = defaultdict(list)
    for e in EXERCISES:
        by_chapter[e['chapter_id']].append(e)
    bad_sort = []
    for cid in range(1, len(CHAPTERS) + 1):
        sorts = sorted(e['sort_order'] for e in by_chapter.get(cid, []))
        if sorts != list(range(1, 12)):
            bad_sort.append((cid, sorts))
    if bad_sort:
        print('[FAIL] 章内排序异常：%s' % bad_sort)
        failed += 1
    else:
        print('[PASS] %d 章每章 sort_order 1..11' % len(CHAPTERS))

    # 3. 逐题校验
    for e in EXERCISES:
        eid = e['id']
        typ = e['type']
        if typ == 'choice':
            ans = e.get('answer')
            opts = e.get('options') or []
            labels = [o['label'] for o in opts]
            if not isinstance(ans, str) or ans not in labels:
                print('[FAIL] 选择题 %d answer=%r 不在选项 %s 中' % (eid, ans, labels))
                failed += 1
        elif typ == 'blank':
            ans = e.get('answer')
            if not isinstance(ans, list) or len(ans) == 0:
                print('[FAIL] 填空题 %d answer 应为非空数组，实际 %r' % (eid, ans))
                failed += 1
                continue
            blanks = e['prompt'].count('______')
            if blanks != len(ans):
                print('[FAIL] 填空题 %d 空位 %d 个 != 答案 %d 个' % (eid, blanks, len(ans)))
                failed += 1
        else:  # short / boss
            td = e.get('test_driver') or ''
            mains = re.findall(r'\bint\s+main\s*\(', td)
            if len(mains) != 1:
                print('[FAIL] 写代码题 %d test_driver 应有 1 个 main，实际 %d' % (eid, len(mains)))
                failed += 1
            fails = td.count('FAIL:')
            if fails != e.get('total_cases', 0):
                print('[FAIL] 写代码题 %d FAIL 数 %d != total_cases %s'
                      % (eid, fails, e.get('total_cases')))
                failed += 1
            for key in ('starter_easy', 'starter_medium', 'starter_hard', 'test_driver'):
                code = e.get(key) or ''
                ok, msg = scan_brace_balance(code)
                if not ok:
                    print('[FAIL] 写代码题 %d %s: %s' % (eid, key, msg))
                    failed += 1

    print('[PASS] 客观题答案完整 + 写代码题 main/FAIL 数/括号配平')

    # 4. 题型分布
    print('[INFO] 题型分布：%s' % dict(Counter(e['type'] for e in EXERCISES)))

    if failed:
        print('\n%d 项校验失败' % failed)
        sys.exit(1)
    print('\n全部通过')


if __name__ == '__main__':
    main()
