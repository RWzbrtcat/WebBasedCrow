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
#   - 幂等：固定 id + INSERT ... ON DUPLICATE KEY UPDATE（upsert）。
#     重导会「更新」已有行 —— 生成器是题库唯一真源，改 sort_order/内容都要靠重导生效。
#     历史坑：早期用 INSERT IGNORE，导致已有行（如 C1/C2 代码题的 sort_order）永远不更新，
#     与新增客观题排序冲突，页面上题序错乱。
#   - 三张表的 DDL 与 src/database.cpp 的 initTable 保持一致（改表结构两处都要动）。
#   - 生成器负责 SQL 转义：单引号 -> ''，反斜杠 -> \\（C++ 代码里的 \n 靠这个保住）。
#   - 写文件用 newline="\n"，杜绝 Windows CRLF 混入（历史坑：\r 落进字符串字面量）。
# ============================================================

import io
import json
import os

# ---------- 章节数据 ----------
# (id, 章节名, 标题, 章内排序)
CHAPTERS = [
    (1, '第一章节 · 语言地基', '现代语法糖', 1),
    (2, '第一章节 · 语言地基', '移动语义与完美转发', 2),
    (3, '第一章节 · 语言地基', '智能指针与 RAII', 3),
    (4, '第一章节 · 语言地基', 'Lambda 与函数式', 4),
    (5, '第一章节 · 语言地基', '模板与元编程基础', 5),
    (6, '第一章节 · 语言地基', '现代工具类型', 6),
    (7, '第二章节 · 后端应用', 'STL 容器与算法', 7),
    (8, '第二章节 · 后端应用', '文件操作与流', 8),
    (9, '第二章节 · 后端应用', '多线程与并发', 9),
    (10, '第二章节 · 后端应用', '网络编程', 10),
    (11, '第二章节 · 后端应用', '数据库交互', 11),
    (12, '第三章节 · 进阶工程', 'constexpr 与编译期计算', 12),
    (13, '第三章节 · 进阶工程', 'C++20 高级特性', 13),
    (14, '第三章节 · 进阶工程', '模块与工程实践', 14),
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
        'sort_order': 18,
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
        'sort_order': 19,
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
    {
        'id': 3,
        'chapter_id': 1,
        'type': 'short',
        'title': '短题 3 · override/final/=delete',
        'sort_order': 20,
        'prompt': (
            '实现一个形状类层次，验证 `override` / `final` / `=default` / `=delete` 四个关键字：\n\n'
            '1. `Shape` 抽象基类：虚析构 + 纯虚函数 `double area() const`\n'
            '2. `Circle : Shape`：构造 `Circle(double radius)`，用 `override` 重写 `area()`，返回 `π·r²`\n'
            '3. `Square : Shape`：构造 `Square(double side)`，用 `override` 重写 `area()`，返回 `side²`，且声明 `final`\n'
            '4. `NonCopyable`：可默认构造，但拷贝构造/拷贝赋值用 `=delete` 禁止\n\n'
            '> 考点：`override` 防误写；`final` 禁止再继承；`=delete` 禁拷贝。\n'
        ),
        'starter_easy': r'''#include <cmath>

// 抽象基类（已提供，请勿修改）
class Shape {
public:
    virtual ~Shape() = default;
    virtual double area() const = 0;
};

// Circle：用 override 重写 area()
class Circle : public Shape {
public:
    explicit Circle(double radius) : radius_(radius) {}
    double area() const ____ {          // 填 override
        return 3.141592653589793 * radius_ * radius_;
    }
private:
    double radius_;
};

// Square：用 override 重写 area()，并声明 final
class Square ____ : public Shape {      // 填 final
public:
    explicit Square(double side) : side_(side) {}
    double area() const ____ {          // 填 override
        return side_ * side_;
    }
private:
    double side_;
};

// NonCopyable：=delete 禁止拷贝
class NonCopyable {
public:
    NonCopyable() = default;
    NonCopyable(const NonCopyable&) ____;              // 填 = delete
    NonCopyable& operator=(const NonCopyable&) ____;   // 填 = delete
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <cmath>

// 抽象基类（已提供，请勿修改）
class Shape {
public:
    virtual ~Shape() = default;
    virtual double area() const = 0;
};

// TODO: 按以下接口实现三个类：
//   1. Circle : Shape —— explicit Circle(double radius)，override area() 返回 πr²
//   2. Square : Shape —— explicit Square(double side)，override area() 返回 side²，声明 final
//   3. NonCopyable —— 默认构造，=delete 拷贝构造与拷贝赋值

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <cmath>

// 需求：
//   - 定义抽象基类 Shape，含纯虚函数 double area() const
//   - Circle 继承 Shape，构造传半径，area 返回 πr²（override）
//   - Square 继承 Shape，构造传边长，area 返回 side²（override 且 final）
//   - NonCopyable 类，禁止拷贝构造与拷贝赋值（=delete）
//   - 隐藏测试会调用 Circle(2.0).area()、Square(3.0).area()、通过 Shape* 多态调用，
//     并检查 Square 的 final 与 NonCopyable 的不可拷贝性

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <cmath>
#include <type_traits>

int main() {
    int fail = 0;
    // 用例1：Circle area = π r²
    Circle c(2.0);
    if (std::abs(c.area() - 3.141592653589793 * 4.0) > 0.0001) {
        std::printf("FAIL: Circle(2).area() 应约等于 12.5664\n");
        ++fail;
    }
    // 用例2：Square area = side²
    Square s(3.0);
    if (std::abs(s.area() - 9.0) > 0.0001) {
        std::printf("FAIL: Square(3).area() 应等于 9\n");
        ++fail;
    }
    // 用例3：多态调用（override 生效）
    Shape* p = &s;
    if (std::abs(p->area() - 9.0) > 0.0001) {
        std::printf("FAIL: 通过 Shape* 调用应走 Square::area（虚函数）\n");
        ++fail;
    }
    // 用例4：Square 声明了 final
    if (!std::is_final<Square>::value) {
        std::printf("FAIL: Square 应声明为 final（禁止再继承）\n");
        ++fail;
    }
    // 用例5：NonCopyable 禁拷贝构造
    if (std::is_copy_constructible<NonCopyable>::value) {
        std::printf("FAIL: NonCopyable 应 =delete 拷贝构造\n");
        ++fail;
    }
    // 用例6：NonCopyable 禁拷贝赋值
    if (std::is_copy_assignable<NonCopyable>::value) {
        std::printf("FAIL: NonCopyable 应 =delete 拷贝赋值\n");
        ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 6,
        'time_limit_ms': 2000,
    },
    {
        'id': 4,
        'chapter_id': 1,
        'type': 'short',
        'title': '短题 4 · 统一初始化与范围 for',
        'sort_order': 21,
        'prompt': (
            '实现 `IntArray` 类，验证列表初始化与范围 for：\n\n'
            '1. 支持列表初始化：`IntArray a{1, 2, 3, 4};`\n'
            '2. `size()` 返回元素个数\n'
            '3. `operator[]` 访问元素\n'
            '4. 支持范围 for 遍历（`int* begin()` / `int* end()`），含引用遍历修改元素\n'
            '5. 拷贝构造与拷贝赋值用 `=delete` 禁止 —— 这个类自己管内存，'
            '默认拷贝会让两个对象指向同一块内存（`double free`）\n\n'
            '> 考点：`std::initializer_list`、统一初始化、范围 for 的引用语义、Rule of Three 的最小闭环。\n'
        ),
        'starter_easy': r'''#include <initializer_list>

// TODO: 实现 IntArray（成员变量 data_ 与 size_ 已给）
class IntArray {
public:
    // 构造：从 initializer_list 拷贝元素
    IntArray(std::initializer_list<int> init) {
        // TODO: 分配 size_ 个 int，逐个拷贝 init 的元素
    }
    ~IntArray() {
        // TODO: 释放 data_
    }
    int size() const {
        // TODO: 返回 size_
    }
    int& operator[](int i) {
        // TODO: 返回第 i 个元素
    }
    int* begin() {
        // TODO: 返回首元素指针
    }
    int* end() {
        // TODO: 返回尾后指针
    }
    // TODO: 禁止拷贝 —— 两行 =delete（否则两个对象会指向同一块 data_）
private:
    int* data_;
    int size_;
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <initializer_list>

// TODO: 实现 IntArray，接口如下：
//   IntArray(std::initializer_list<int> init)  —— 构造，拷贝元素
//   ~IntArray()                                 —— 析构，释放内存
//   int size() const                            —— 返回元素个数
//   int& operator[](int i)                      —— 访问第 i 个元素
//   int* begin()                                —— 首元素指针（支持范围 for）
//   int* end()                                  —— 尾后指针
//   IntArray(const IntArray&) = delete;          —— 禁止拷贝构造
//   IntArray& operator=(const IntArray&) = delete; —— 禁止拷贝赋值
// 需自行设计成员变量（如 int* data_; int size_;）

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <initializer_list>

// 需求：实现 IntArray 类
//   - 支持列表初始化：IntArray a{1,2,3,4};
//   - 支持 operator[] 访问元素
//   - 支持范围 for 遍历（含引用遍历修改元素）
//   - size() 返回元素个数
//   - 拷贝构造与拷贝赋值必须 =delete（自管内存，默认拷贝会 double free）
//   - 隐藏测试会：构造 {1,2,3,4}、检查 size、范围 for 累加、
//     范围 for 引用修改元素、空列表构造、is_copy_constructible 为 false

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <type_traits>

int main() {
    int fail = 0;
    // 用例1：列表初始化
    IntArray a{1, 2, 3, 4};
    if (a.size() != 4) {
        std::printf("FAIL: IntArray{1,2,3,4} 的 size() 应为 4\n");
        ++fail;
    }
    // 用例2：operator[] 访问
    if (a[0] != 1 || a[3] != 4) {
        std::printf("FAIL: operator[] 访问元素不正确\n");
        ++fail;
    }
    // 用例3：范围 for 累加
    int sum = 0;
    for (int x : a) sum += x;
    if (sum != 10) {
        std::printf("FAIL: 范围 for 累加应得 10，实际 %d\n", sum);
        ++fail;
    }
    // 用例4：范围 for 引用遍历修改元素
    for (int& x : a) x *= 2;
    if (a[0] != 2 || a[3] != 8) {
        std::printf("FAIL: 范围 for 引用遍历应能修改元素\n");
        ++fail;
    }
    // 用例5：空列表初始化
    IntArray b{};
    if (b.size() != 0) {
        std::printf("FAIL: 空列表 IntArray{} 的 size() 应为 0\n");
        ++fail;
    }
    // 用例6：拷贝必须被 =delete 掉（否则 double free）
    if (std::is_copy_constructible<IntArray>::value ||
        std::is_copy_assignable<IntArray>::value) {
        std::printf("FAIL: IntArray 应 =delete 拷贝构造与拷贝赋值\n");
        ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 6,
        'time_limit_ms': 2000,
    },
    {
        'id': 5,
        'chapter_id': 1,
        'type': 'boss',
        'title': 'Boss · 类型安全的枚举状态机',
        'sort_order': 25,
        'prompt': (
            '实现一个类型安全的 TCP 状态机，串起本章全部知识点：\n\n'
            '1. 用 `enum class` 定义 6 个状态：`Closed / Listen / Established / FinWait1 / FinWait2 / TimeWait`\n'
            '2. `bool can_transition(TcpState from, TcpState to)`：判定转移是否合法\n'
            '3. `const char* state_to_string(TcpState)`：状态转字符串\n'
            '4. `bool state_from_string(const char*, TcpState&)`：字符串转状态，非法返回 `false`\n'
            '5. `TcpStateMachine` 类：初始 `Closed`，`transition` 合法才转移（非法保持状态不变），且 `=delete` 拷贝\n\n'
            '合法转移链：`Closed → Listen → Established → FinWait1 → FinWait2 → TimeWait → Closed`\n\n'
            '> 收口：enum class（强类型）+ =delete（禁拷贝）+ 序列化（round-trip）。\n'
        ),
        'starter_easy': r'''#include <cstring>

// TCP 状态枚举（已提供，请勿修改）
enum class TcpState { Closed, Listen, Established, FinWait1, FinWait2, TimeWait };

// TODO: can_transition —— 合法转移链：Closed->Listen->Established->FinWait1->FinWait2->TimeWait->Closed
bool can_transition(TcpState from, TcpState to) {
    // TODO: 判断 from -> to 是否合法
}

// TODO: state_to_string —— 返回 "Closed"/"Listen"/"Established"/"FinWait1"/"FinWait2"/"TimeWait"
const char* state_to_string(TcpState s) {
    // TODO: switch
}

// TODO: state_from_string —— 解析字符串，非法返回 false
bool state_from_string(const char* s, TcpState& out) {
    // TODO: strcmp 逐个比对
}

// TODO: TcpStateMachine —— 初始 Closed，transition 合法才转移，state() 返回当前状态，=delete 拷贝
class TcpStateMachine {
    // TODO
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <cstring>

// TODO: 实现 TCP 状态机，接口约定如下（隐藏测试会直接调用）：
//   enum class TcpState { Closed, Listen, Established, FinWait1, FinWait2, TimeWait };
//   bool can_transition(TcpState from, TcpState to);
//   const char* state_to_string(TcpState s);
//   bool state_from_string(const char* s, TcpState& out);
//   class TcpStateMachine { TcpStateMachine(); bool transition(TcpState); TcpState state() const; };
// 合法转移链：Closed->Listen->Established->FinWait1->FinWait2->TimeWait->Closed
// TcpStateMachine 须 =delete 拷贝构造与拷贝赋值。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <cstring>

// 需求：类型安全的 TCP 状态机
//   - 用 enum class 定义 6 个状态
//   - 实现状态间合法转移判定（合法链：Closed->Listen->Established->FinWait1->FinWait2->TimeWait->Closed）
//   - 实现状态与字符串的双向序列化（round-trip）
//   - 实现 TcpStateMachine 类：初始 Closed，transition 合法才转移，
//     非法转移保持状态不变，且禁止拷贝
//   - 隐藏测试会验证：合法转移链走通、非法转移被拒、序列化 round-trip、
//     非法字符串反序列化返回 false、状态机不可拷贝

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <cstring>
#include <type_traits>

int main() {
    int fail = 0;
    // 用例1：合法转移链走通
    TcpStateMachine m;
    bool ok = true;
    ok = ok && m.transition(TcpState::Listen);
    ok = ok && m.transition(TcpState::Established);
    ok = ok && m.transition(TcpState::FinWait1);
    ok = ok && m.transition(TcpState::FinWait2);
    ok = ok && m.transition(TcpState::TimeWait);
    ok = ok && m.transition(TcpState::Closed);
    if (!ok || m.state() != TcpState::Closed) {
        std::printf("FAIL: 合法转移链应走通，最终回到 Closed\n");
        ++fail;
    }
    // 用例2：非法转移被拒（can_transition）
    if (can_transition(TcpState::Closed, TcpState::Established)) {
        std::printf("FAIL: Closed -> Established 应是非转移\n");
        ++fail;
    }
    // 用例3：非法转移状态不变
    TcpStateMachine m2;
    if (m2.transition(TcpState::Established)) {
        std::printf("FAIL: 从 Closed 直接转移到 Established 应失败\n");
        ++fail;
    }
    if (m2.state() != TcpState::Closed) {
        std::printf("FAIL: 非法转移后状态应保持 Closed\n");
        ++fail;
    }
    // 用例4：序列化
    if (std::strcmp(state_to_string(TcpState::Established), "Established") != 0) {
        std::printf("FAIL: state_to_string(Established) 应返回 \"Established\"\n");
        ++fail;
    }
    // 用例5：反序列化 round-trip
    TcpState parsed;
    if (!state_from_string("FinWait1", parsed) || parsed != TcpState::FinWait1) {
        std::printf("FAIL: state_from_string(\"FinWait1\") 应解析为 FinWait1\n");
        ++fail;
    }
    // 用例6：非法字符串反序列化
    TcpState bad;
    if (state_from_string("Nope", bad)) {
        std::printf("FAIL: state_from_string(\"Nope\") 应返回 false\n");
        ++fail;
    }
    // 用例7：状态机不可拷贝
    if (std::is_copy_constructible<TcpStateMachine>::value) {
        std::printf("FAIL: TcpStateMachine 应 =delete 拷贝构造\n");
        ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 8,
        'time_limit_ms': 2000,
    },
    {
        'id': 6,
        'chapter_id': 2,
        'type': 'short',
        'title': '短题 1 · 移动构造与移动赋值',
        'sort_order': 7,
        'prompt': (
            '实现一个**只移动**的 `Buffer` 类（持有动态分配的 `char` 数组）：\n\n'
            '1. 构造 `Buffer(std::size_t size)` 分配 `size` 字节（`size=0` 时 `data` 为 `nullptr`）\n'
            '2. 移动构造：转移 `data_` 与 `size_`，并把源对象置空（`data=nullptr`）\n'
            '3. 移动赋值：先释放自己的旧资源，再转移，并**处理自移动**（`this == &other`）\n'
            '4. 拷贝构造/拷贝赋值用 `=delete` 禁止\n\n'
            '> 考点：移动语义的资源转移、源对象置空、自移动保护、`noexcept`。\n'
        ),
        'starter_easy': r'''#include <cstddef>

// TODO: 实现只移动的 Buffer（成员变量 data_ / size_ 与构造析构已给）
class Buffer {
public:
    explicit Buffer(std::size_t size = 0)
        : data_(size > 0 ? new char[size] : nullptr), size_(size) {}

    ~Buffer() { delete[] data_; }

    // TODO: 移动构造 —— 转移 data_ 和 size_，并把源对象置空
    Buffer(Buffer&& other) noexcept {
        // TODO
    }

    // TODO: 移动赋值 —— 先释放旧资源，再转移，并处理自移动
    Buffer& operator=(Buffer&& other) noexcept {
        // TODO
        return *this;
    }

    // 禁拷贝
    Buffer(const Buffer&) = delete;
    Buffer& operator=(const Buffer&) = delete;

    std::size_t size() const { return size_; }
    char* data() const { return data_; }
private:
    char* data_;
    std::size_t size_;
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <cstddef>

// TODO: 实现只移动的 Buffer，接口如下：
//   explicit Buffer(std::size_t size = 0)     —— 分配 size 字节（0 时 data 为 nullptr）
//   ~Buffer()                                  —— 释放内存
//   Buffer(Buffer&& other) noexcept            —— 移动构造，转移资源并置空源对象
//   Buffer& operator=(Buffer&& other) noexcept —— 移动赋值，释放旧资源 + 处理自移动
//   Buffer(const Buffer&) = delete             —— 禁拷贝构造
//   Buffer& operator=(const Buffer&) = delete  —— 禁拷贝赋值
//   std::size_t size() const                   —— 返回大小
//   char* data() const                         —— 返回数据指针
// 需自行设计成员变量（如 char* data_; std::size_t size_;）

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <cstddef>

// 需求：只移动的 Buffer 类
//   - 持有动态分配的 char 数组，size() 返回大小，data() 返回指针
//   - 移动构造/移动赋值：转移资源并把源对象置空（data=nullptr）
//   - 移动赋值需处理自移动，且先释放自己的旧资源
//   - 禁止拷贝（=delete）
//   - 隐藏测试会验证：移动转移资源、源对象置空、自移动安全、不可拷贝

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <utility>
#include <type_traits>

int main() {
    int fail = 0;
    // 用例1：移动构造转移资源（指针不变，非深拷贝）
    Buffer a(100);
    char* a_data = a.data();
    Buffer b(std::move(a));
    if (b.size() != 100 || b.data() != a_data) {
        std::printf("FAIL: 移动构造应转移资源（指针不变），而非深拷贝\n");
        ++fail;
    }
    // 用例2：移动构造后源对象置空
    if (a.data() != nullptr || a.size() != 0) {
        std::printf("FAIL: 移动构造后源对象应置空（data=nullptr, size=0）\n");
        ++fail;
    }
    // 用例3：移动赋值转移资源
    Buffer c(50);
    Buffer d(200);
    char* d_data = d.data();
    c = std::move(d);
    if (c.size() != 200 || c.data() != d_data) {
        std::printf("FAIL: 移动赋值应转移资源\n");
        ++fail;
    }
    // 用例4：移动赋值后源对象置空
    if (d.data() != nullptr) {
        std::printf("FAIL: 移动赋值后源对象应置空\n");
        ++fail;
    }
    // 用例5：自移动安全
    c = std::move(c);
    if (c.size() != 200) {
        std::printf("FAIL: 自移动赋值不应破坏资源\n");
        ++fail;
    }
    // 用例6：禁拷贝
    if (std::is_copy_constructible<Buffer>::value) {
        std::printf("FAIL: Buffer 应 =delete 拷贝构造\n");
        ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 6,
        'time_limit_ms': 2000,
    },
    {
        'id': 7,
        'chapter_id': 2,
        'type': 'short',
        'title': '短题 2 · 修复移动语义的 bug',
        'sort_order': 8,
        'prompt': (
            '下面的 `Wrapper` 类独占一个 `int*` 资源，但移动语义实现有 bug。\n\n'
            '请找出并修复所有 bug，使隐藏测试全部通过：\n\n'
            '1. 移动构造必须把源对象的指针置空（否则析构时 **double free**）\n'
            '2. 移动赋值必须先释放自己的旧资源（否则**内存泄漏**）\n'
            '3. 移动赋值必须处理自移动（`this == &other`，否则资源丢失）\n\n'
            '> 考点：移动后源对象状态、自移动安全、资源所有权。\n'
        ),
        'starter_easy': r'''// 以下移动语义实现有 3 处 BUG，请修复（bug 位置已标注）
class Wrapper {
public:
    explicit Wrapper(int* p) : ptr_(p) {}
    ~Wrapper() { delete ptr_; }

    // 移动构造：转移资源
    Wrapper(Wrapper&& other) noexcept : ptr_(other.ptr_) {
        // BUG #1：这里应把 other.ptr_ 置为 nullptr，否则析构时 double free
    }

    // 移动赋值：转移资源
    Wrapper& operator=(Wrapper&& other) noexcept {
        // BUG #2：这里应先释放自己的旧资源，否则内存泄漏
        // BUG #3：这里应先判断 this == &other（自移动），否则会丢失资源
        ptr_ = other.ptr_;
        other.ptr_ = nullptr;
        return *this;
    }

    Wrapper(const Wrapper&) = delete;
    Wrapper& operator=(const Wrapper&) = delete;

    int* get() const { return ptr_; }
private:
    int* ptr_;
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''// 以下 Wrapper 的移动语义实现有 bug（未标位置），请找出并修复，
// 使隐藏测试全部通过
class Wrapper {
public:
    explicit Wrapper(int* p) : ptr_(p) {}
    ~Wrapper() { delete ptr_; }

    Wrapper(Wrapper&& other) noexcept : ptr_(other.ptr_) {}

    Wrapper& operator=(Wrapper&& other) noexcept {
        ptr_ = other.ptr_;
        other.ptr_ = nullptr;
        return *this;
    }

    Wrapper(const Wrapper&) = delete;
    Wrapper& operator=(const Wrapper&) = delete;

    int* get() const { return ptr_; }
private:
    int* ptr_;
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''// 需求：实现只移动的 Wrapper（独占 int* 资源）
//   - 构造接管指针，析构释放
//   - 移动构造/移动赋值转移所有权
//   - 禁止拷贝（=delete）
//   - 注意：移动后源对象必须置空（否则 double free）；
//     移动赋值必须先释放旧资源、处理自移动
//   - 隐藏测试会验证：移动后源对象为空、自移动安全、不可拷贝

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <utility>
#include <type_traits>

int main() {
    int fail = 0;
    // 用例1：移动构造后源对象置空
    Wrapper a(new int(42));
    Wrapper b(std::move(a));
    if (b.get() == nullptr || *b.get() != 42) {
        std::printf("FAIL: 移动构造应转移资源\n");
        ++fail;
    }
    if (a.get() != nullptr) {
        std::printf("FAIL: 移动构造后源对象应置空\n");
        ++fail;
    }
    // 用例2：移动赋值后源对象置空
    Wrapper c(new int(1));
    Wrapper d(new int(2));
    c = std::move(d);
    if (*c.get() != 2) {
        std::printf("FAIL: 移动赋值应转移资源\n");
        ++fail;
    }
    if (d.get() != nullptr) {
        std::printf("FAIL: 移动赋值后源对象应置空\n");
        ++fail;
    }
    // 用例3：自移动安全
    c = std::move(c);
    if (c.get() == nullptr || *c.get() != 2) {
        std::printf("FAIL: 自移动赋值不应丢失资源\n");
        ++fail;
    }
    // 用例4：禁拷贝
    if (std::is_copy_constructible<Wrapper>::value) {
        std::printf("FAIL: Wrapper 应 =delete 拷贝构造\n");
        ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 6,
        'time_limit_ms': 2000,
    },
    {
        'id': 8,
        'chapter_id': 2,
        'type': 'short',
        'title': '短题 3 · 只移动类（=delete 拷贝）',
        'sort_order': 9,
        'prompt': (
            '实现一个**独占资源句柄** `Resource`（类似 `unique_ptr` 的简化版）：\n\n'
            '1. 构造 `Resource(int id)`，`id` 为 0 表示「空」（不持有资源）\n'
            '2. 移动构造/移动赋值转移所有权，源对象变为空（`id=0`）\n'
            '3. 移动赋值处理自移动\n'
            '4. 拷贝构造/拷贝赋值用 `=delete` 禁止\n'
            '5. `id()` 返回资源 id，`valid()` 返回是否持有资源（`id != 0`）\n\n'
            '> 考点：独占所有权、只移动类型、移动后源对象可复用。\n'
        ),
        'starter_easy': r'''// TODO: 实现独占资源句柄 Resource（id 为 0 表示无资源）
class Resource {
public:
    explicit Resource(int id = 0) : id_(id) {}

    // TODO: 移动构造 —— 转移 id_，并把源对象 id_ 置 0
    Resource(Resource&& other) noexcept {
        // TODO
    }

    // TODO: 移动赋值 —— 转移 id_，源对象置 0，处理自移动
    Resource& operator=(Resource&& other) noexcept {
        // TODO
        return *this;
    }

    // 禁拷贝
    Resource(const Resource&) = delete;
    Resource& operator=(const Resource&) = delete;

    int id() const { return id_; }
    bool valid() const { return id_ != 0; }
private:
    int id_;
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''// TODO: 实现独占资源句柄 Resource，接口如下：
//   explicit Resource(int id = 0)                  —— id 为 0 表示无资源
//   Resource(Resource&& other) noexcept             —— 移动构造，转移 id 并置空源对象
//   Resource& operator=(Resource&& other) noexcept  —— 移动赋值，转移 id，处理自移动
//   Resource(const Resource&) = delete              —— 禁拷贝
//   int id() const                                  —— 返回资源 id
//   bool valid() const                              —— 是否持有资源（id != 0）
// 需自行设计成员变量

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''// 需求：独占资源句柄 Resource（类似 unique_ptr 的简化版）
//   - id 为 0 表示"空"（不持有资源）
//   - 移动构造/移动赋值转移所有权，源对象变为空
//   - 移动赋值处理自移动
//   - 禁止拷贝（=delete）
//   - 隐藏测试会验证：移动转移所有权、源对象置空、可重新赋值复用、不可拷贝

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <utility>
#include <type_traits>

int main() {
    int fail = 0;
    // 用例1：构造持有资源
    Resource r(42);
    if (!r.valid() || r.id() != 42) {
        std::printf("FAIL: Resource(42) 应持有 id=42 的资源\n");
        ++fail;
    }
    // 用例2：移动构造转移所有权
    Resource r2(std::move(r));
    if (!r2.valid() || r2.id() != 42) {
        std::printf("FAIL: 移动构造应转移资源\n");
        ++fail;
    }
    if (r.valid()) {
        std::printf("FAIL: 移动构造后源对象应无效\n");
        ++fail;
    }
    // 用例3：移动赋值转移所有权
    Resource r3(7);
    r3 = std::move(r2);
    if (!r3.valid() || r3.id() != 42) {
        std::printf("FAIL: 移动赋值应转移资源\n");
        ++fail;
    }
    if (r2.valid()) {
        std::printf("FAIL: 移动赋值后源对象应无效\n");
        ++fail;
    }
    // 用例4：移动后的源对象可重新赋值复用
    r2 = Resource(99);
    if (!r2.valid() || r2.id() != 99) {
        std::printf("FAIL: 移动后的源对象应可重新赋值复用\n");
        ++fail;
    }
    // 用例5：禁拷贝
    if (std::is_copy_constructible<Resource>::value) {
        std::printf("FAIL: Resource 应 =delete 拷贝构造\n");
        ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 7,
        'time_limit_ms': 2000,
    },
    {
        'id': 9,
        'chapter_id': 2,
        'type': 'short',
        'title': '短题 4 · 完美转发工厂',
        'sort_order': 10,
        'prompt': (
            '实现一个完美转发工厂 `make_thing`，保持参数的左值/右值类别：\n\n'
            '测试类 `Thing` 已提供，它通过构造重载区分左值/右值入参：\n'
            '- `Thing(int&)` → `source = "lvalue_ref"`\n'
            '- `Thing(int&&)` → `source = "rvalue_ref"`\n\n'
            '实现 `template <typename T> Thing make_thing(T&& v)`，\n'
            '用 `std::forward<T>(v)` 保持 `v` 的类别：左值入参构造出 `lvalue_ref`，右值入参构造出 `rvalue_ref`。\n\n'
            '> 考点：`std::forward` 完美转发、引用折叠、`T&&` 的推导。\n'
        ),
        'starter_easy': r'''#include <utility>

// 测试类（已提供，请勿修改）：通过构造重载区分左值/右值
struct Thing {
    Thing(int& v)  : value(v), source("lvalue_ref") {}
    Thing(int&& v) : value(v), source("rvalue_ref") {}
    int value;
    const char* source;
};

// TODO: 实现完美转发工厂 make_thing
template <typename T>
Thing make_thing(T&& v) {
    return Thing(____<T>(v));   // 填 std::forward
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <utility>

// 测试类（已提供，请勿修改）
struct Thing {
    Thing(int& v)  : value(v), source("lvalue_ref") {}
    Thing(int&& v) : value(v), source("rvalue_ref") {}
    int value;
    const char* source;
};

// TODO: 实现 make_thing，用 std::forward 保持参数类别
template <typename T>
Thing make_thing(T&& v) {
    // TODO
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <utility>

// 测试类（已提供，请勿修改）
struct Thing {
    Thing(int& v)  : value(v), source("lvalue_ref") {}
    Thing(int&& v) : value(v), source("rvalue_ref") {}
    int value;
    const char* source;
};

// 需求：实现模板工厂 make_thing(T&& v)
//   - 用完美转发（std::forward）保持参数 v 的左值/右值类别
//   - 左值入参应构造出 source=="lvalue_ref" 的 Thing
//   - 右值入参应构造出 source=="rvalue_ref" 的 Thing
//   - 隐藏测试会分别用左值和右值调用并检查 source

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <cstring>

int main() {
    int fail = 0;
    // 用例1：左值入参 → lvalue_ref
    int x = 5;
    Thing t1 = make_thing(x);
    if (std::strcmp(t1.source, "lvalue_ref") != 0) {
        std::printf("FAIL: 左值入参应构造 lvalue_ref 的 Thing\n");
        ++fail;
    }
    // 用例2：右值入参 → rvalue_ref（需 std::forward 才成立）
    Thing t2 = make_thing(5);
    if (std::strcmp(t2.source, "rvalue_ref") != 0) {
        std::printf("FAIL: 右值入参应构造 rvalue_ref 的 Thing（需 std::forward）\n");
        ++fail;
    }
    // 用例3：值正确传递
    if (t1.value != 5 || t2.value != 5) {
        std::printf("FAIL: value 未正确传递\n");
        ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 3,
        'time_limit_ms': 2000,
    },
    {
        'id': 10,
        'chapter_id': 2,
        'type': 'boss',
        'title': 'Boss · 只移动的 Buffer 类',
        'sort_order': 11,
        'prompt': (
            '实现一个完整的**只移动** `Buffer` 类，综合移动语义 + 异常安全 + 返回值优化：\n\n'
            '1. 持有动态分配的 `char` 数组，`size()` / `data()` 访问\n'
            '2. 移动构造/移动赋值声明 `noexcept`（`vector` 扩容依赖，否则退化成拷贝）\n'
            '3. 移动构造/赋值转移资源并置空源对象；移动赋值处理自移动、释放旧资源\n'
            '4. 拷贝构造/拷贝赋值 `=delete` 禁止\n'
            '5. 静态工厂 `static Buffer create(std::size_t size)` 按值返回（触发 RVO/移动）\n\n'
            '> 收口：移动语义（转移/置空）+ 异常安全（noexcept）+ RVO + 禁拷贝。\n'
        ),
        'starter_easy': r'''#include <cstddef>

// TODO: 实现只移动的 Buffer（构造/析构已给，补移动与工厂）
class Buffer {
public:
    explicit Buffer(std::size_t size = 0)
        : data_(size > 0 ? new char[size] : nullptr), size_(size) {}

    ~Buffer() { delete[] data_; }

    // TODO: 移动构造（noexcept + 转移资源 + 源置空）
    Buffer(Buffer&& other) noexcept {
        // TODO
    }

    // TODO: 移动赋值（noexcept + 释放旧资源 + 转移 + 处理自移动）
    Buffer& operator=(Buffer&& other) noexcept {
        // TODO
        return *this;
    }

    // 禁拷贝
    Buffer(const Buffer&) = delete;
    Buffer& operator=(const Buffer&) = delete;

    // 静态工厂：按值返回（测 RVO）
    static Buffer create(std::size_t size) { return Buffer(size); }

    std::size_t size() const { return size_; }
    char* data() const { return data_; }
private:
    char* data_;
    std::size_t size_;
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <cstddef>

// TODO: 实现只移动的 Buffer，接口如下：
//   explicit Buffer(std::size_t size = 0)      —— 分配 size 字节（0 时 data 为 nullptr）
//   ~Buffer()                                   —— 释放内存
//   Buffer(Buffer&& other) noexcept             —— 移动构造（转移 + 源置空）
//   Buffer& operator=(Buffer&& other) noexcept  —— 移动赋值（释放旧资源 + 自移动）
//   Buffer(const Buffer&) = delete              —— 禁拷贝
//   static Buffer create(std::size_t size)      —— 按值返回
//   std::size_t size() const / char* data() const
// 需自行设计成员变量

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <cstddef>

// 需求：只移动的 Buffer 类（综合：移动语义 + 异常安全 + RVO）
//   - 持有动态 char 数组，size()/data() 访问
//   - 移动构造/赋值 noexcept（vector 扩容依赖），转移资源并置空源对象
//   - 移动赋值处理自移动、释放旧资源
//   - 禁止拷贝（=delete）
//   - 静态工厂 create(size) 按值返回
//   - 隐藏测试会验证：移动转移、自移动、noexcept、vector 扩容、
//     禁拷贝、按值返回

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <utility>
#include <vector>
#include <type_traits>

int main() {
    int fail = 0;
    // 用例1：移动构造转移资源，源置空
    Buffer a(100);
    char* a_data = a.data();
    Buffer b(std::move(a));
    if (b.size() != 100 || b.data() != a_data) {
        std::printf("FAIL: 移动构造应转移资源\n");
        ++fail;
    }
    if (a.data() != nullptr || a.size() != 0) {
        std::printf("FAIL: 移动构造后源对象应置空\n");
        ++fail;
    }
    // 用例2：移动自赋值安全
    b = std::move(b);
    if (b.size() != 100 || b.data() == nullptr) {
        std::printf("FAIL: 自移动赋值不应破坏资源\n");
        ++fail;
    }
    // 用例3：noexcept 移动构造（vector 扩容依赖）
    if (!std::is_nothrow_move_constructible<Buffer>::value) {
        std::printf("FAIL: 移动构造应声明 noexcept\n");
        ++fail;
    }
    // 用例4：vector<Buffer> 扩容走移动
    std::vector<Buffer> v;
    v.push_back(Buffer(10));
    v.push_back(Buffer(20));
    v.push_back(Buffer(30));
    if (v.size() != 3 || v[0].size() != 10 || v[2].size() != 30) {
        std::printf("FAIL: vector<Buffer> 扩容后元素不正确\n");
        ++fail;
    }
    // 用例5：禁拷贝
    if (std::is_copy_constructible<Buffer>::value) {
        std::printf("FAIL: Buffer 应 =delete 拷贝构造\n");
        ++fail;
    }
    // 用例6：按值返回（RVO/移动）
    Buffer c = Buffer::create(64);
    if (c.size() != 64 || c.data() == nullptr) {
        std::printf("FAIL: create() 按值返回的 Buffer 应正确\n");
        ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 7,
        'time_limit_ms': 2000,
    },
    # ================= 客观题（选择题 id 11-13 / 填空题 id 14-16，C1） =================
    # C1 客观题设计口径（2026-10-20 扩充）：
    #   1) 题干不泄答案：标题里不出现「陷阱/失效」这类答案关键词，代码里不写「// BUG」。
    #   2) 四个选项都必须是「真实会犯的错」——禁止用「编译错误」「未定义行为」凑数，
    #      除非它本身就是最有吸引力的那个误解（如范围 for 遍历中扩容）。
    #   3) 每题至少一个「文档里查得到、但背不下来」的标准细节做落点。
    {
        'id': 11,
        'chapter_id': 1,
        'type': 'choice',
        'title': '选择 1 · auto 到底推成了什么',
        'sort_order': 1,
        'question': '`a` 与 `b` 的类型分别是？',
        'prompt': '''```cpp
const int& get() {
    static int x = 42;
    return x;
}

auto  a = get();
auto& b = get();
```''',
        'options': [
            {'label': 'A', 'text': 'a 是 int，b 是 const int&'},
            {'label': 'B', 'text': 'a 是 const int&，b 是 const int&'},
            {'label': 'C', 'text': 'a 是 int，b 是 int&'},
            {'label': 'D', 'text': 'a 是 int&&，b 是 const int&'},
        ],
        'answer': 'A',
    },
    {
        'id': 12,
        'chapter_id': 1,
        'type': 'choice',
        'title': '选择 2 · decltype 看的是名字还是表达式',
        'sort_order': 2,
        'question': '`z` 的类型是？',
        'prompt': '''```cpp
const int cx = 0;

decltype(cx)   y  = cx;
decltype((cx)) z  = cx;
```''',
        'options': [
            {'label': 'A', 'text': 'const int'},
            {'label': 'B', 'text': 'const int&'},
            {'label': 'C', 'text': 'int&'},
            {'label': 'D', 'text': 'int'},
        ],
        'answer': 'B',
    },
    {
        'id': 13,
        'chapter_id': 1,
        'type': 'choice',
        'title': '选择 3 · 范围 for 的两轮循环',
        'sort_order': 3,
        'question': '两轮循环都跑完之后，`v` 的内容是？',
        'prompt': '''```cpp
std::vector<int> v{1, 2, 3};

for (auto x : v)  { x *= 2; }   /* ① */
for (auto& x : v) { x += 1; }   /* ② */
```''',
        'options': [
            {'label': 'A', 'text': '{2, 3, 4}'},
            {'label': 'B', 'text': '{3, 5, 7}'},
            {'label': 'C', 'text': '{1, 2, 3}'},
            {'label': 'D', 'text': '{2, 4, 6}'},
        ],
        'answer': 'A',
    },
    {
        'id': 14,
        'chapter_id': 1,
        'type': 'blank',
        'title': '填空 1 · 0 与 nullptr 选到不同重载',
        'sort_order': 12,
        'question': '空 1 必须走到 `f(int)`，空 2 必须走到 `f(void*)`。想清楚：`0` 和 `nullptr` 各自的类型是什么。',
        'prompt': '''void f(int)   { }
void f(void*) { }

f(______);   /* 空1 */
f(______);   /* 空2 */''',
        'answer': [['0'], ['nullptr']],
    },
    {
        'id': 15,
        'chapter_id': 1,
        'type': 'blank',
        'title': '填空 2 · 漏了 const 的 draw',
        'sort_order': 13,
        'question': '派生类的 `draw` 漏写了 `const`。在空位填一个关键字，让编译器**当场报错**，而不是悄悄把它变成一个「新函数」。',
        'prompt': '''class Base {
public:
    virtual void draw() const { }
};

class Derived : public Base {
public:
    void draw() ______;   /* 空 */
};''',
        'answer': [['override']],
    },
    {
        'id': 16,
        'chapter_id': 1,
        'type': 'blank',
        'title': '填空 3 · =default / =delete',
        'sort_order': 14,
        'question': '空 1 要「默认行为」，空 2、空 3 要「彻底禁止拷贝」。三个空都是一种带等号的写法。',
        'prompt': '''class Handle {
public:
    Handle() ______;                          /* 空1 */
    Handle(const Handle&) ______;             /* 空2 */
    Handle& operator=(const Handle&) ______;  /* 空3 */
};''',
        'answer': [['= default'], ['= delete'], ['= delete']],
    },
    # ================= C2 客观题（id 17-22） =================
    {
        'id': 17,
        'chapter_id': 2,
        'type': 'choice',
        'title': '选择 1 · move 之后源对象的状态',
        'sort_order': 1,
        'prompt': '''```cpp
std::vector<int> a{1, 2, 3};
std::vector<int> b = std::move(a);
// 关于 a，正确的说法是？
```''',
        'options': [
            {'label': 'A', 'text': 'a 仍是 {1,2,3}，b 是它的拷贝'},
            {'label': 'B', 'text': 'a 资源被转移，处于"有效但未指定"状态（通常空）'},
            {'label': 'C', 'text': '访问 a 是未定义行为'},
            {'label': 'D', 'text': '编译错误'},
        ],
        'answer': 'B',
    },
    {
        'id': 18,
        'chapter_id': 2,
        'type': 'choice',
        'title': '选择 2 · 移动构造的触发（构造 vs 赋值）',
        'sort_order': 2,
        'prompt': '''```cpp
std::string s = "hello";
std::string t = std::move(s);   // 这行调用的是？
```''',
        'options': [
            {'label': 'A', 'text': '拷贝构造'},
            {'label': 'B', 'text': '移动构造'},
            {'label': 'C', 'text': '拷贝赋值'},
            {'label': 'D', 'text': '移动赋值'},
        ],
        'answer': 'B',
    },
    {
        'id': 19,
        'chapter_id': 2,
        'type': 'choice',
        'title': '选择 3 · RVO / 拷贝省略',
        'sort_order': 3,
        'prompt': '''```cpp
Widget make_widget() {
    Widget w;
    return w;              // 按值返回局部对象
}
Widget x = make_widget();
// 从 w 到 x，调用几次拷贝/移动构造？
```''',
        'options': [
            {'label': 'A', 'text': '至少一次拷贝'},
            {'label': 'B', 'text': '至少一次移动'},
            {'label': 'C', 'text': '零次（拷贝省略）'},
            {'label': 'D', 'text': '取决于编译器'},
        ],
        'answer': 'C',
    },
    {
        'id': 20,
        'chapter_id': 2,
        'type': 'blank',
        'title': '填空 1 · std::move',
        'sort_order': 4,
        'prompt': '''std::vector<int> a{1, 2, 3};
std::vector<int> b = ________(a);   // 转移 a 的资源，避免深拷贝''',
        'answer': ['std::move'],
    },
    {
        'id': 21,
        'chapter_id': 2,
        'type': 'blank',
        'title': '填空 2 · std::forward（完美转发）',
        'sort_order': 5,
        'prompt': '''template <typename T>
void wrapper(T&& arg) {
    target(________<T>(arg));   // 保持 arg 的左值/右值类别
}''',
        'answer': ['std::forward'],
    },
    {
        'id': 22,
        'chapter_id': 2,
        'type': 'blank',
        'title': '填空 3 · 移动构造的 noexcept',
        'sort_order': 6,
        'prompt': '''class Buffer {
public:
    Buffer(Buffer&& other) ________;   // 声明不抛异常
};''',
        'answer': ['noexcept'],
    },
    # ================= C3 客观题（id 23-28） =================
    {
        'id': 23,
        'chapter_id': 3,
        'type': 'choice',
        'title': '选择 1 · shared_ptr 循环引用',
        'sort_order': 1,
        'prompt': '''```cpp
struct Node {
    std::shared_ptr<Node> next;
};
auto a = std::make_shared<Node>();
auto b = std::make_shared<Node>();
a->next = b;
b->next = a;   // a、b 互相引用，会发生什么？
```''',
        'options': [
            {'label': 'A', 'text': '离开作用域后自动释放'},
            {'label': 'B', 'text': 'a、b 永远无法释放，内存泄漏'},
            {'label': 'C', 'text': '编译错误'},
            {'label': 'D', 'text': '运行时崩溃'},
        ],
        'answer': 'B',
    },
    {
        'id': 24,
        'chapter_id': 3,
        'type': 'choice',
        'title': '选择 2 · unique_ptr 独占所有权',
        'sort_order': 2,
        'prompt': '''```cpp
std::unique_ptr<int> p1 = std::make_unique<int>(42);
std::unique_ptr<int> p2 = p1;   // 这行？
```''',
        'options': [
            {'label': 'A', 'text': '编译通过，共享所有权'},
            {'label': 'B', 'text': '编译错误，unique_ptr 不可拷贝'},
            {'label': 'C', 'text': '编译通过，p2 拥有、p1 悬空'},
            {'label': 'D', 'text': '运行时错误'},
        ],
        'answer': 'B',
    },
    {
        'id': 25,
        'chapter_id': 3,
        'type': 'choice',
        'title': '选择 3 · make_shared 的异常安全',
        'sort_order': 3,
        'prompt': '''```cpp
// 哪种写法更好？
auto p1 = std::shared_ptr<Widget>(new Widget);  // A
auto p2 = std::make_shared<Widget>();           // B
```''',
        'options': [
            {'label': 'A', 'text': 'A 更好'},
            {'label': 'B', 'text': 'B 更好，单次分配 + 异常安全'},
            {'label': 'C', 'text': '两者完全等价'},
            {'label': 'D', 'text': 'A 有异常安全保证'},
        ],
        'answer': 'B',
    },
    {
        'id': 26,
        'chapter_id': 3,
        'type': 'blank',
        'title': '填空 1 · make_shared',
        'sort_order': 4,
        'prompt': '''auto sp = std::________<Widget>(/* 构造参数 */);''',
        'question': '请补全代码：用 std::make_shared 创建指向 Widget 的 shared_ptr（自动管理引用计数）。',
        'answer': ['make_shared'],
    },
    {
        'id': 27,
        'chapter_id': 3,
        'type': 'blank',
        'title': '填空 2 · weak_ptr 打破循环引用',
        'sort_order': 5,
        'prompt': '''struct Node {
    std::________<Node> next;   // 用弱引用打破循环引用
};''',
        'answer': ['weak_ptr'],
    },
    {
        'id': 28,
        'chapter_id': 3,
        'type': 'blank',
        'title': '填空 3 · weak_ptr.lock()',
        'sort_order': 6,
        'prompt': '''std::weak_ptr<int> wp = sp;   // sp 是 shared_ptr
if (auto p = wp.________()) { /* 安全使用 p */ }''',
        'answer': ['lock'],
    },
    # ================= C4 客观题（id 29-34） =================
    {
        'id': 29,
        'chapter_id': 4,
        'type': 'choice',
        'title': '选择 1 · 捕获引用悬垂',
        'sort_order': 1,
        'prompt': '''```cpp
std::function<int()> make_counter() {
    int count = 0;
    return [&]() { return ++count; };   // 返回捕获引用的 lambda
}
auto f = make_counter();
f();   // 会发生什么？
```''',
        'options': [
            {'label': 'A', 'text': '返回 1'},
            {'label': 'B', 'text': '未定义行为（悬垂引用）'},
            {'label': 'C', 'text': '编译错误'},
            {'label': 'D', 'text': '返回 0'},
        ],
        'answer': 'B',
    },
    {
        'id': 30,
        'chapter_id': 4,
        'type': 'choice',
        'title': '选择 2 · 泛型 lambda（C++14）',
        'sort_order': 2,
        'prompt': '''```cpp
auto add = [](auto a, auto b) { return a + b; };
// 这个 lambda 的实质是？
```''',
        'options': [
            {'label': 'A', 'text': '编译错误，参数不能是 auto'},
            {'label': 'B', 'text': '模板化的函数对象（operator() 是模板）'},
            {'label': 'C', 'text': '只能处理 int'},
            {'label': 'D', 'text': '只能处理同类型'},
        ],
        'answer': 'B',
    },
    {
        'id': 31,
        'chapter_id': 4,
        'type': 'choice',
        'title': '选择 3 · [=] 捕获 this 的真相',
        'sort_order': 3,
        'prompt': '''```cpp
class A {
    int v = 0;
public:
    auto get() { return [=]() { return v; }; }   // [=] 捕获了什么？
};
```''',
        'options': [
            {'label': 'A', 'text': '拷贝了 v 的值'},
            {'label': 'B', 'text': '捕获了 this 指针，经 this 访问 v'},
            {'label': 'C', 'text': '编译错误'},
            {'label': 'D', 'text': '未定义行为'},
        ],
        'answer': 'B',
    },
    {
        'id': 32,
        'chapter_id': 4,
        'type': 'blank',
        'title': '填空 1 · 按引用捕获',
        'sort_order': 4,
        'prompt': '''int threshold = 10;
auto pred = [______](int x) { return x > threshold; };   // 按引用捕获 threshold''',
        'answer': ['&'],
    },
    {
        'id': 33,
        'chapter_id': 4,
        'type': 'blank',
        'title': '填空 2 · mutable',
        'sort_order': 5,
        'prompt': '''int n = 0;
auto inc = [n]() ________ { return ++n; };   // 让 lambda 能修改按值捕获的 n''',
        'answer': ['mutable'],
    },
    {
        'id': 34,
        'chapter_id': 4,
        'type': 'blank',
        'title': '填空 3 · 泛型 lambda 参数',
        'sort_order': 6,
        'prompt': '''auto twice = [](________ x) { return x * 2; };   // 接受任意算术类型''',
        'answer': ['auto'],
    },
    # ================= C5 客观题（id 35-40） =================
    {
        'id': 35,
        'chapter_id': 5,
        'type': 'choice',
        'title': '选择 1 · 变参模板递归展开',
        'sort_order': 1,
        'prompt': '''```cpp
template <typename T>
T sum(T t) { return t; }
template <typename T, typename... Args>
T sum(T t, Args... args) { return t + sum(args...); }
// sum(1, 2, 3, 4) 的结果是？
```''',
        'options': [
            {'label': 'A', 'text': '10'},
            {'label': 'B', 'text': '编译错误'},
            {'label': 'C', 'text': '只算前两个'},
            {'label': 'D', 'text': '未定义行为'},
        ],
        'answer': 'A',
    },
    {
        'id': 36,
        'chapter_id': 5,
        'type': 'choice',
        'title': '选择 2 · if constexpr 编译期分支',
        'sort_order': 2,
        'prompt': '''```cpp
template <typename T>
auto get_value(T t) {
    if constexpr (std::is_pointer_v<T>)
        return *t;
    else
        return t;
}
// 传入 int* 时，else 分支会被编译吗？
```''',
        'options': [
            {'label': 'A', 'text': '会，运行时跳过'},
            {'label': 'B', 'text': '不会，编译期丢弃'},
            {'label': 'C', 'text': '编译错误'},
            {'label': 'D', 'text': '取决于优化'},
        ],
        'answer': 'B',
    },
    {
        'id': 37,
        'chapter_id': 5,
        'type': 'choice',
        'title': '选择 3 · typename 依赖类型',
        'sort_order': 3,
        'prompt': '''```cpp
template <typename T>
void f(T t) {
    typename T::value_type x;   // 为什么需要 typename？
}
```''',
        'options': [
            {'label': 'A', 'text': '告诉编译器 T::value_type 是类型'},
            {'label': 'B', 'text': '可选，去掉也能编译'},
            {'label': 'C', 'text': '表示运行时多态'},
            {'label': 'D', 'text': '无中生有'},
        ],
        'answer': 'A',
    },
    {
        'id': 38,
        'chapter_id': 5,
        'type': 'blank',
        'title': '填空 1 · 折叠表达式',
        'sort_order': 4,
        'prompt': '''template <typename... Args>
auto sum(Args... args) {
    return (args + ________);   // 用折叠表达式求和
}''',
        'answer': ['...'],
    },
    {
        'id': 39,
        'chapter_id': 5,
        'type': 'blank',
        'title': '填空 2 · typename',
        'sort_order': 5,
        'prompt': '''template <typename T>
void print_first(const T& c) {
    ________ T::value_type x = c.front();   // 声明依赖类型变量
}''',
        'answer': ['typename'],
    },
    {
        'id': 40,
        'chapter_id': 5,
        'type': 'blank',
        'title': '填空 3 · if constexpr',
        'sort_order': 6,
        'prompt': '''template <typename T>
void f(T t) {
    if ________ (std::is_integral_v<T>) { /* 整数路径 */ }
    else { /* 其他路径 */ }
}''',
        'question': '请补全代码：用编译期 if（if constexpr）对整型与非整型走不同分支。',
        'answer': ['constexpr'],
    },
    # ================= C6 客观题（id 41-46） =================
    {
        'id': 41,
        'chapter_id': 6,
        'type': 'choice',
        'title': '选择 1 · optional 无值',
        'sort_order': 1,
        'prompt': '''```cpp
std::optional<int> find_even(const std::vector<int>& v) {
    for (int x : v) if (x % 2 == 0) return x;
    return std::nullopt;
}
// find_even({1, 3, 5}) 返回什么？
```''',
        'options': [
            {'label': 'A', 'text': '0'},
            {'label': 'B', 'text': 'std::nullopt（无值）'},
            {'label': 'C', 'text': '抛异常'},
            {'label': 'D', 'text': '未定义行为'},
        ],
        'answer': 'B',
    },
    {
        'id': 42,
        'chapter_id': 6,
        'type': 'choice',
        'title': '选择 2 · variant vs union',
        'sort_order': 2,
        'prompt': '''```cpp
std::variant<int, double, std::string> v = 42;
```''',
        'question': '关于上面这段 std::variant 代码，下列说法正确的是？',
        'options': [
            {'label': 'A', 'text': 'v 是裸 union，同内存存三种'},
            {'label': 'B', 'text': 'v 是类型安全联合，当前持有 int'},
            {'label': 'C', 'text': 'v 同时持有三种值'},
            {'label': 'D', 'text': '编译错误'},
        ],
        'answer': 'B',
    },
    {
        'id': 43,
        'chapter_id': 6,
        'type': 'choice',
        'title': '选择 3 · string_view 悬垂',
        'sort_order': 3,
        'prompt': '''```cpp
std::string_view get_view() {
    std::string s = "hello";
    return s;   // 返回 s 的 string_view
}
auto v = get_view();
std::cout << v;   // 会发生什么？
```''',
        'options': [
            {'label': 'A', 'text': '输出 hello'},
            {'label': 'B', 'text': '悬垂引用，未定义行为'},
            {'label': 'C', 'text': '输出空'},
            {'label': 'D', 'text': '编译错误'},
        ],
        'answer': 'B',
    },
    {
        'id': 44,
        'chapter_id': 6,
        'type': 'blank',
        'title': '填空 1 · optional value_or',
        'sort_order': 4,
        'prompt': '''std::optional<int> o;
int x = o.________(42);   // 无值时给默认值''',
        'answer': ['value_or'],
    },
    {
        'id': 45,
        'chapter_id': 6,
        'type': 'blank',
        'title': '填空 2 · variant 访问',
        'sort_order': 5,
        'prompt': '''std::variant<int, std::string> v = "hi";
std::________([](auto&& arg){ /* 访问 */ }, v);''',
        'question': '请补全代码：用 std::visit 对 variant 当前持有的类型进行访问。',
        'answer': ['visit'],
    },
    {
        'id': 46,
        'chapter_id': 6,
        'type': 'blank',
        'title': '填空 3 · string_view 零拷贝切片',
        'sort_order': 6,
        'prompt': '''std::string_view view = "hello world";
auto sub = view.________(0, 5);   // 取前5个字符，不拷贝''',
        'answer': ['substr'],
    },
    # ================= C7 客观题（id 47-52） =================
    {
        'id': 47,
        'chapter_id': 7,
        'type': 'choice',
        'title': '选择 1 · 迭代器失效',
        'sort_order': 1,
        'prompt': '''```cpp
std::vector<int> v{1, 2, 3};
for (auto it = v.begin(); it != v.end(); ++it) {
    if (*it == 2) v.erase(it);
}
// 循环结束后，v 的内容是？
```''',
        'options': [
            {'label': 'A', 'text': 'v == {1, 3}'},
            {'label': 'B', 'text': 'v == {1, 2, 3}（什么也没删掉）'},
            {'label': 'C', 'text': 'v == {1}（2 后面的元素一起没了）'},
            {'label': 'D', 'text': '无法确定：可能崩溃，也可能恰好是上面任意一种'},
        ],
        'answer': 'D',
    },
    {
        'id': 48,
        'chapter_id': 7,
        'type': 'choice',
        'title': '选择 2 · map vs unordered_map',
        'sort_order': 2,
        'prompt': '''```cpp
// 需要按键有序遍历的场景，选哪个？
```''',
        'options': [
            {'label': 'A', 'text': 'unordered_map'},
            {'label': 'B', 'text': 'map'},
            {'label': 'C', 'text': 'vector'},
            {'label': 'D', 'text': 'list'},
        ],
        'answer': 'B',
    },
    {
        'id': 49,
        'chapter_id': 7,
        'type': 'choice',
        'title': '选择 3 · erase-remove 惯用法',
        'sort_order': 3,
        'prompt': '''```cpp
// 删除 vector 中所有值为 2 的元素，正确写法是？
```''',
        'options': [
            {'label': 'A', 'text': '循环里逐个 erase'},
            {'label': 'B', 'text': 'v.erase(std::remove(begin, end, 2), end)'},
            {'label': 'C', 'text': 'std::remove 直接删'},
            {'label': 'D', 'text': 'v.clear()'},
        ],
        'answer': 'B',
    },
    {
        'id': 50,
        'chapter_id': 7,
        'type': 'blank',
        'title': '填空 1 · 自定义哈希',
        'sort_order': 4,
        'prompt': '''struct Hash {
    size_t operator()(const Point& p) const {
        return std::hash<int>()(p.x) ^ (std::hash<int>()(p.y) << 1);
    }
};
std::________<Point, int, Hash> m;   // 用自定义哈希的哈希表''',
        'answer': ['unordered_map'],
    },
    {
        'id': 51,
        'chapter_id': 7,
        'type': 'blank',
        'title': '填空 2 · 自定义比较器',
        'sort_order': 5,
        'prompt': '''std::________<int, std::greater<int>> s;   // 降序集合''',
        'answer': ['set'],
    },
    {
        'id': 52,
        'chapter_id': 7,
        'type': 'blank',
        'title': '填空 3 · 算法 find_if',
        'sort_order': 6,
        'prompt': '''auto it = std::________(v.begin(), v.end(), [](int x){ return x > 10; });''',
        'question': '请补全代码：用算法查找第一个大于 10 的元素（返回迭代器）。',
        'answer': ['find_if'],
    },
    # ================= C7 新增题（id 155-161）：反判别 + 失效五连 =================
    {
        'id': 155,
        'chapter_id': 7,
        'type': 'choice',
        'title': '选择 4 · 哪个不失效',
        'sort_order': 7,
        'prompt': '''```cpp
// 已有迭代器 it 指向容器中某个元素，下列哪个操作之后 it 仍然有效？
```''',
        'options': [
            {'label': 'A', 'text': 'vector::push_back，且触发了重新分配'},
            {'label': 'B', 'text': 'list::insert(pos, x)，插入点在另一个位置'},
            {'label': 'C', 'text': 'vector::erase(v.begin())'},
            {'label': 'D', 'text': 'unordered_map::insert，触发了 rehash'},
        ],
        'answer': 'B',
    },
    {
        'id': 156,
        'chapter_id': 7,
        'type': 'choice',
        'title': '选择 5 · 引用也会悬垂',
        'sort_order': 8,
        'prompt': '''```cpp
std::vector<int> v{1, 2, 3};
v.reserve(3);
int& r = v[0];
v.push_back(4);
r = 99;
```''',
        'question': '`reserve(3)` 之后容量正好是 3，所以 `push_back(4)` 必然重新分配内存。执行完之后 `v[0]` 是多少？',
        'options': [
            {'label': 'A', 'text': '99 —— r 是 v[0] 的别名，改的就是它'},
            {'label': 'B', 'text': '1 —— 写进了已被释放的旧内存，编译器不报任何错'},
            {'label': 'C', 'text': '编译错误：push_back 之后引用自动失效'},
            {'label': 'D', 'text': '抛出 std::out_of_range'},
        ],
        'answer': 'B',
    },
    {
        'id': 157,
        'chapter_id': 7,
        'type': 'choice',
        'title': '选择 6 · 迭代器死了，元素还活着',
        'sort_order': 9,
        'prompt': '''```cpp
// 哪个操作会让「迭代器失效」，但「指向元素的引用/指针仍然有效」？
```''',
        'options': [
            {'label': 'A', 'text': 'vector::push_back 触发重新分配'},
            {'label': 'B', 'text': 'deque::push_front'},
            {'label': 'C', 'text': 'list::erase(被删的那个元素)'},
            {'label': 'D', 'text': 'vector::erase(中间某个元素)'},
        ],
        'answer': 'B',
    },
    {
        'id': 158,
        'chapter_id': 7,
        'type': 'choice',
        'title': '选择 7 · 换成 list 就安全吗',
        'sort_order': 10,
        'prompt': '''```cpp
std::list<int> c{1, 2, 3};
for (auto it = c.begin(); it != c.end(); ++it) {
    if (*it == 2) c.erase(it);
}
```''',
        'question': '把 `vector` 换成 `list` 之后，这段循环就安全了吗？',
        'options': [
            {'label': 'A', 'text': '安全：list 的 erase 只摘掉这一个节点，别的节点不受影响'},
            {'label': 'B', 'text': '安全：节点容器的迭代器永远不会失效'},
            {'label': 'C', 'text': '不安全：erase 之后 it 已失效，再拿它 ++ 仍是未定义行为；只是节点内存常未被复用，所以"看起来正常"'},
            {'label': 'D', 'text': '编译错误：list::erase 返回 void，不能接返回值'},
        ],
        'answer': 'C',
    },
    {
        'id': 159,
        'chapter_id': 7,
        'type': 'choice',
        'title': '选择 8 · 换容器后静默越界',
        'sort_order': 11,
        'prompt': '''```cpp
void feed(const int* p, std::size_t n);

std::deque<int> d{1, 2, 3};
feed(&d[0], d.size());   // 会怎样？
```''',
        'question': '`feed` 约定 `p` 指向连续存放的 `n` 个 `int`。这段代码会怎样？',
        'options': [
            {'label': 'A', 'text': '编译失败：deque 没有 data()，拿不到首元素地址'},
            {'label': 'B', 'text': '编译通过、运行正常，结果正确'},
            {'label': 'C', 'text': '编译通过，但 deque 的内存不保证连续，feed 会越界读取'},
            {'label': 'D', 'text': '编译通过，运行时抛出异常'},
        ],
        'answer': 'C',
    },
    {
        'id': 160,
        'chapter_id': 7,
        'type': 'choice',
        'title': '选择 9 · 跑一千次都没崩',
        'sort_order': 12,
        'prompt': '''```cpp
// 一段含未定义行为的代码在 CI 上连续跑了 1000 次、全部通过：可以据此认为它是安全的吗？
```''',
        'options': [
            {'label': 'A', 'text': '可以：1000 次全过，出错概率可以忽略'},
            {'label': 'B', 'text': '不可以：它的表现依赖内存布局、分配器状态与优化等级，要用 ASan/UBSan 这类工具才算验证'},
            {'label': 'C', 'text': '不可以：把编译优化关掉，再跑 1000 次就行'},
            {'label': 'D', 'text': '可以：只要 Debug 和 Release 都跑过'},
        ],
        'answer': 'B',
    },
    {
        'id': 161,
        'chapter_id': 7,
        'type': 'blank',
        'title': '填空 4 · 循环里删元素',
        'sort_order': 13,
        'prompt': '''std::vector<int> v{1, 2, 3, 4};
for (auto it = v.begin(); it != v.end(); ) {
    if (*it % 2 == 0) it = v.______(it);
    else ++it;
}''',
        'question': '补全代码：删除所有偶数，并让迭代器安全地续接到下一个元素。',
        'answer': ['erase'],
    },
    # ========== C7 源码阅读题（id 162-166）：keep_notes=1，注释属于代码本体 ==========
    {
        'id': 162,
        'chapter_id': 7,
        'type': 'blank',
        'title': '阅读 1 · vector 扩容的三件事',
        'sort_order': 14,
        'keep_notes': True,
        'question': '补全 ① ② ③ 三处关键调用。想清楚：① 为什么故意不用 `std::move`？',
        'prompt': r'''// 简化版 vector 的扩容：只看「搬家」这一段
template <class T>
void mini_vector<T>::grow(std::size_t need) {
    std::size_t cap = cap_ ? cap_ * 2 : 1;     // 按 2 倍增长（摊还 O(1)）
    while (cap < need) cap *= 2;

    T* fresh = static_cast<T*>(::operator new(cap * sizeof(T)));

    // ① 在「原始内存」上逐个构造新对象
    for (std::size_t i = 0; i < size_; ++i)
        new (fresh + i) T(std::______(data_[i]));

    // ② 旧对象必须被亲手销毁：原始内存不会替你调用析构
    for (std::size_t i = 0; i < size_; ++i)
        data_[i].______();

    // ③ 只归还内存，不再调析构（②已经做过了）
    ::operator ______(data_);

    data_ = fresh;
    cap_  = cap;
}''',
        'answer': [['move_if_noexcept'], ['~T', '~T()'], ['delete']],
    },
    {
        'id': 167,
        'chapter_id': 7,
        'type': 'short',
        'title': '实现 1 · mini_vector：扩容四步',
        'sort_order': 15,
        'prompt': '实现简化版动态数组 `mini_vector<T>`（**不许借用任何标准容器**，内存自己管）：\n\n'
                  '- `size()` / `capacity()` / `empty()`\n'
                  '- `void reserve(std::size_t n)`：容量不足才重新分配，并把已有元素**搬移**过去\n'
                  '- `void push_back(const T& v)`：满了先扩容，容量翻倍（起点按 1 算）\n'
                  '- `operator[]` 的 const / 非 const 两个版本；`begin()` / `end()` 返回 `T*`\n'
                  '- 析构：**逐个**销毁元素，再放掉原始内存\n\n'
                  '> 收口：阅读 1 里那四步——新开一块、搬元素、销毁旧元素、放掉旧内存——本次由你自己写。\n'
                  '> 写对之后你会亲眼看到：**扩容后 `&v[0]` 变了**，这就是迭代器失效的物理原因。',
        'starter_easy': r'''#include <cstddef>
#include <new>
#include <utility>

template <class T>
class mini_vector {
    T*          data_ = nullptr;
    std::size_t size_ = 0;
    std::size_t cap_  = 0;

public:
    mini_vector() = default;

    ~mini_vector() {
        // TODO: 逐个调用元素析构，再放掉原始内存
    }

    std::size_t size() const     { return size_; }
    std::size_t capacity() const { return cap_; }
    bool        empty() const    { return size_ == 0; }

    void reserve(std::size_t n) {
        if (n <= cap_) return;

        // 第一步：申请原始内存。不要用 new T[n] —— 那会构造 n 个元素，
        //         size 与 capacity 就分不开了。
        //   T* fresh = static_cast<T*>(::operator new(n * sizeof(T)));

        // 第二步：把旧元素搬过去（这是构造，不是赋值）

        // 第三步：逐个销毁旧元素

        // 第四步：只归还内存，然后更新 data_ 与 cap_
    }

    void push_back(const T& v) {
        // TODO: size_ == cap_ 时先 reserve(cap_ ? cap_ * 2 : 1)；
        //       再在 data_ + size_ 的位置构造 v，然后 ++size_
    }

    T&       operator[](std::size_t i)       { return data_[i]; }
    const T& operator[](std::size_t i) const { return data_[i]; }

    T* begin() { return data_; }
    T* end()   { return data_ + size_; }

    mini_vector(const mini_vector&) = delete;
    mini_vector& operator=(const mini_vector&) = delete;
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <cstddef>
#include <new>
#include <utility>

// 实现 mini_vector<T>：reserve / push_back / operator[] / begin / end / 析构。
// 要点：原始内存 + placement new；扩容时搬移完元素必须销毁旧元素；
//       析构函数要逐个销毁元素后再归还内存。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <cstddef>
#include <new>

// 需求：手写动态数组（自动翻倍扩容、随机访问、析构不泄漏）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <cstddef>

struct Tracked {   // 能数清「当前有多少个对象活着」
    static int alive;
    int v;
    Tracked() : v(0) { ++alive; }
    explicit Tracked(int x) : v(x) { ++alive; }
    Tracked(const Tracked& o) : v(o.v) { ++alive; }
    Tracked(Tracked&& o) noexcept : v(o.v) { ++alive; }
    Tracked& operator=(const Tracked& o) { v = o.v; return *this; }
    Tracked& operator=(Tracked&& o) noexcept { v = o.v; return *this; }
    ~Tracked() { --alive; }
};
int Tracked::alive = 0;

int main() {
    int fail = 0;

    {   // 1 起点：空容器
        mini_vector<int> v;
        if (v.size() != 0 || v.capacity() != 0 || !v.empty()) {
            std::printf("FAIL: 空容器应为 size=0 / capacity=0 / empty()=true\n"); ++fail;
        }
    }

    {   // 2 反复扩容后元素不丢、不错位
        mini_vector<int> v;
        for (int i = 0; i < 50; ++i) v.push_back(i * 3);
        if (v.size() != 50) { std::printf("FAIL: push_back 50 次后 size 应为 50\n"); ++fail; }
        if (v.capacity() < v.size()) { std::printf("FAIL: capacity 不能小于 size\n"); ++fail; }
        int bad = 0;
        for (int i = 0; i < 50; ++i) if (v[i] != i * 3) { bad = i + 1; break; }
        if (bad) { std::printf("FAIL: 第 %d 个元素在扩容后错位，旧元素没搬过去\n", bad); ++fail; }
        int seen = 0;
        for (auto it = v.begin(); it != v.end(); ++it) ++seen;
        if (seen != 50) { std::printf("FAIL: begin()..end() 应能遍历 50 个元素\n"); ++fail; }
    }

    {   // 3 容量满了必须重新分配 —— 迭代器失效的物理原因
        mini_vector<int> v;
        v.reserve(2);
        v.push_back(7);
        v.push_back(8);
        const int* p0 = &v[0];
        v.push_back(9);
        if (&v[0] == p0) { std::printf("FAIL: 容量满后 push_back 必须重新分配，&v[0] 应该变\n"); ++fail; }
        if (v[0] != 7 || v[2] != 9) { std::printf("FAIL: 扩容后元素顺序错了\n"); ++fail; }
    }

    {   // 4 reserve 只借地，不造元素
        mini_vector<int> v;
        v.reserve(8);
        if (v.capacity() < 8) { std::printf("FAIL: reserve(8) 后 capacity 应 >= 8\n"); ++fail; }
        if (v.size() != 0) { std::printf("FAIL: reserve 不应改变 size\n"); ++fail; }
        v.push_back(1);
        const int* p0 = &v[0];
        for (int i = 0; i < 7; ++i) v.push_back(i);
        if (&v[0] != p0) { std::printf("FAIL: reserve(8) 之内再 push 7 次不应重新分配\n"); ++fail; }
    }

    {   // 5 构造与析构配平
        Tracked::alive = 0;
        {
            mini_vector<Tracked> v;
            for (int i = 0; i < 20; ++i) v.push_back(Tracked(i));
            if (Tracked::alive != 20) {
                std::printf("FAIL: 容器内应恰好有 20 个存活元素，实际 %d（旧元素没销毁？空槽也构造了对象？）\n",
                            Tracked::alive); ++fail;
            }
            if (v[19].v != 19) { std::printf("FAIL: 元素搬移后值错了\n"); ++fail; }
        }
        if (Tracked::alive != 0) {
            std::printf("FAIL: 析构后仍有 %d 个元素存活，说明没逐个销毁\n", Tracked::alive); ++fail;
        }
    }

    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 13,
        'time_limit_ms': 2000,
    },
    {
        'id': 163,
        'chapter_id': 7,
        'type': 'blank',
        'title': '阅读 2 · list 只改指针',
        'sort_order': 16,
        'keep_notes': True,
        'question': '补全 ① ②。想清楚：为什么 `insert` 之后，原本指向**其他节点**的迭代器一个都没失效？',
        'prompt': r'''// 简化版 list：带哨兵的双向链表
template <class T>
class mini_list {
    struct node { node* prev; node* next; T value; };
    node        head_;          // 哨兵：head_.next 是首元素，head_.prev 是尾元素
    std::size_t size_ = 0;

public:
    // 在 pos 之前插入：只分配一个新节点、改 4 个指针
    node* insert(node* pos, const T& v) {
        node* n = new node{______, pos, v};   // ① 新节点的前驱是谁

        pos->prev->next = n;
        pos->prev       = n;

        ++size_;
        return n;                             // 老节点地址一个都没变
    }

    // erase：摘链 + 归还内存，然后告诉调用方「下一个」在哪
    node* erase(node* pos) {
        node* after = pos->next;

        pos->prev->next = pos->next;
        pos->next->prev = pos->prev;
        delete pos;

        --size_;
        return ______;                        // ② 循环要靠它续接
    }
};''',
        'answer': [['pos->prev'], ['after']],
    },
    {
        'id': 168,
        'chapter_id': 7,
        'type': 'short',
        'title': '实现 2 · mini_list：只改指针',
        'sort_order': 17,
        'prompt': '用**哨兵节点**实现简化版双向链表 `mini_list<T>`（不许借用任何标准容器）：\n\n'
                  '- `size()` / `empty()`\n'
                  '- `void push_back(const T& v)` / `void push_front(const T& v)`\n'
                  '- 迭代器：`begin()`（首元素）、`end()`（哨兵），支持 `*it` / `++it` / `==` `!=`\n'
                  '- `iterator insert(iterator pos, const T& v)`：在 pos **之前**插入，返回新元素的迭代器\n'
                  '- `iterator erase(iterator pos)`：删除 pos，返回**下一个**元素的迭代器\n'
                  '- 析构：释放所有节点\n\n'
                  '> 收口：`insert` / `erase` 只改指针，**节点地址不变** ⇒ 指向其他节点的迭代器与引用全部继续有效。\n'
                  '> 阅读 2 里那句「list 上换成 erase 也还是 UB」，这一关你会明白 UB 只是「用了失效的迭代器」，'
                  '而**没用到的迭代器一个都没坏**。',
        'starter_easy': r'''#include <cstddef>

template <class T>
class mini_list {
    struct node {
        T     value;
        node* prev;
        node* next;
        node() : value(), prev(this), next(this) {}
        explicit node(const T& v) : value(v), prev(nullptr), next(nullptr) {}
    };

    node        head_;   // 哨兵：head_.next 是首元素，head_.prev 是尾元素
    std::size_t size_ = 0;

public:
    class iterator {
    public:
        // ⚠️ p_ 只能是 public：C++ 里内嵌类能访问外层类的私有成员，反过来不行。
        //    insert / erase 要用到 pos 里的指针，所以这里必须放开。
        node* p_;
        explicit iterator(node* p) : p_(p) {}
        T& operator*() const { return p_->value; }
        iterator& operator++() { p_ = p_->next; return *this; }
        bool operator!=(const iterator& o) const { return p_ != o.p_; }
        bool operator==(const iterator& o) const { return p_ == o.p_; }
    };

    mini_list() = default;

    ~mini_list() {
        // TODO: 从 head_.next 开始逐个 delete，直到转回 &head_
    }

    std::size_t size() const { return size_; }
    bool        empty() const { return size_ == 0; }
    iterator begin() { return iterator(head_.next); }
    iterator end()   { return iterator(&head_); }

    // 在 pos 之前插入，返回新节点；只改 4 个指针
    iterator insert(iterator pos, const T& v) {
        // TODO: node* cur = pos.p_; 新节点挂在 cur->prev 与 cur 之间
        //       别忘了 ++size_
        return pos;
    }

    // 删除 pos，返回下一个（这就是「边遍历边删」能成立的原因）
    iterator erase(iterator pos) {
        // TODO: 摘链、delete、--size_；注意不能 delete 哨兵
        return pos;
    }

    void push_back(const T& v)  { insert(end(), v); }
    void push_front(const T& v) { insert(begin(), v); }

    mini_list(const mini_list&) = delete;
    mini_list& operator=(const mini_list&) = delete;
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <cstddef>

// 实现 mini_list<T>（哨兵双向链表）：push_back / push_front / insert / erase /
// begin / end / size / 析构。
// 要点：insert 在 pos 之前插入，只改指针（旧节点地址不变）；
//       erase 必须返回下一个迭代器；析构要 delete 掉每个节点。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <cstddef>

// 需求：手写双向链表（两端插入、任意位置插入与删除、迭代器遍历、析构不泄漏）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <cstddef>

struct Tracked {   // 能数清「当前有多少个对象活着」
    static int alive;
    int v;
    Tracked() : v(0) { ++alive; }
    explicit Tracked(int x) : v(x) { ++alive; }
    Tracked(const Tracked& o) : v(o.v) { ++alive; }
    Tracked(Tracked&& o) noexcept : v(o.v) { ++alive; }
    Tracked& operator=(const Tracked& o) { v = o.v; return *this; }
    Tracked& operator=(Tracked&& o) noexcept { v = o.v; return *this; }
    ~Tracked() { --alive; }
};
int Tracked::alive = 0;

static int collect(mini_list<int>& l, int* out, int cap) {
    int n = 0;
    for (auto it = l.begin(); it != l.end(); ++it) {
        if (n < cap) out[n] = *it;
        ++n;
    }
    return n;
}

int main() {
    int fail = 0;

    {   // 1 空链表
        mini_list<int> l;
        if (l.size() != 0 || !l.empty()) {
            std::printf("FAIL: 空链表应 size=0 且 empty()=true\n"); ++fail;
        }
        if (l.begin() != l.end()) { std::printf("FAIL: 空链表的 begin() 应等于 end()\n"); ++fail; }
    }

    {   // 2 尾插 + 遍历
        mini_list<int> l;
        for (int i = 1; i <= 4; ++i) l.push_back(i);
        int buf[8];
        int n = collect(l, buf, 8);
        if (n != 4) { std::printf("FAIL: push_back 4 次后应能遍历到 4 个元素\n"); ++fail; }
        if (n == 4 && (buf[0] != 1 || buf[3] != 4)) { std::printf("FAIL: 尾插顺序错了\n"); ++fail; }
        if (l.size() != 4) { std::printf("FAIL: push_back 4 次后 size 应为 4\n"); ++fail; }
    }

    {   // 3 两端插
        mini_list<int> l;
        l.push_back(2);
        l.push_front(1);
        l.push_back(3);
        int buf[8];
        int n = collect(l, buf, 8);
        if (!(n == 3 && buf[0] == 1 && buf[1] == 2 && buf[2] == 3)) {
            std::printf("FAIL: push_front / push_back 之后顺序应为 1 2 3\n"); ++fail;
        }
    }

    {   // 4 中间插入只改指针：原迭代器必须继续有效
        mini_list<int> l;
        l.push_back(1);
        l.push_back(3);
        auto it = l.begin();
        ++it;                       // 指向 3
        int* p = &*it;
        l.insert(it, 2);            // 在 3 之前插入 2
        if (&*it != p) { std::printf("FAIL: insert 之后原迭代器失效了，节点被搬走了\n"); ++fail; }
        int buf[8];
        int n = collect(l, buf, 8);
        if (!(n == 3 && buf[0] == 1 && buf[1] == 2 && buf[2] == 3)) {
            std::printf("FAIL: 中间插入后顺序应为 1 2 3\n"); ++fail;
        }
    }

    {   // 5 insert(end(), v) 等价于尾插
        mini_list<int> l;
        l.push_back(1);
        l.insert(l.end(), 2);
        int buf[8];
        int n = collect(l, buf, 8);
        if (!(n == 2 && buf[0] == 1 && buf[1] == 2)) {
            std::printf("FAIL: insert(end(), v) 应插到尾部\n"); ++fail;
        }
    }

    {   // 6 erase 返回下一个：边遍历边删才成立
        mini_list<int> l;
        for (int i = 1; i <= 6; ++i) l.push_back(i);
        for (auto it = l.begin(); it != l.end(); ) {
            if (*it % 2 == 0) it = l.erase(it);
            else              ++it;
        }
        int buf[8];
        int n = collect(l, buf, 8);
        if (!(n == 3 && buf[0] == 1 && buf[1] == 3 && buf[2] == 5)) {
            std::printf("FAIL: 删掉偶数后应剩 1 3 5，erase 必须返回下一个迭代器\n"); ++fail;
        }
        if (l.size() != 3) { std::printf("FAIL: 删除后 size 应为 3\n"); ++fail; }
    }

    {   // 7 析构：节点里的元素要被销毁
        Tracked::alive = 0;
        {
            mini_list<Tracked> l;
            for (int i = 0; i < 5; ++i) l.push_back(Tracked(i));
            if (l.size() != 5) { std::printf("FAIL: 5 次 push_back 后 size 应为 5\n"); ++fail; }
        }
        if (Tracked::alive != 0) {
            std::printf("FAIL: 析构后仍有 %d 个元素存活，节点没 delete 完\n", Tracked::alive); ++fail;
        }
    }

    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 13,
        'time_limit_ms': 2000,
    },
    {
        'id': 164,
        'chapter_id': 7,
        'type': 'blank',
        'title': '阅读 3 · unordered_map 的桶',
        'sort_order': 18,
        'keep_notes': True,
        'question': '补全 ① ②。注意 `rehash` 里到底换掉了什么：为什么它能让迭代器全失效，却一个节点都不搬？',
        'prompt': r'''// 简化版 unordered_map：链地址法（数组 + 单链表）
template <class K, class V>
class mini_umap {
    struct node { K key; V value; node* next; };

    std::vector<node*> buckets_;    // 每个桶是一条单链表
    std::size_t        size_ = 0;

    // ① 同一个 key 永远落到同一个桶
    std::size_t bucket_of(const K& key) const {
        return std::hash<K>{}(key) % ______;
    }

public:
    node* find(const K& key) {
        std::size_t b = bucket_of(key);
        for (node* p = buckets_[b]; p; p = p->______) {   // ② 顺着链走
            if (p->key == key) return p;
        }
        return nullptr;                                   // 桶空了 = 没找到
    }

    void rehash(std::size_t newCap) {
        std::vector<node*> fresh(newCap, nullptr);

        for (node* head : buckets_) {
            while (head) {
                node* nxt = head->next;
                std::size_t b = std::hash<K>{}(head->key) % newCap;

                head->next = fresh[b];   // 头插
                fresh[b]   = head;
                head       = nxt;
            }
        }

        buckets_.swap(fresh);   // ③ 只换桶数组，节点还留在原来的地址上
    }
};''',
        'answer': [['buckets_.size()', 'bucket_count()'], ['next']],
    },
    {
        'id': 169,
        'chapter_id': 7,
        'type': 'short',
        'title': '实现 3 · mini_unordered_map：链地址法',
        'sort_order': 19,
        'prompt': '用**链地址法**实现简化版哈希表 `mini_unordered_map<K, V>`'
                  '（每个桶挂一条单向链表，不许借用任何标准容器）：\n\n'
                  '- `size()` / `bucket_count()` / `load_factor()`\n'
                  '- `V& operator[](const K& key)`：不存在则插入 `V{}`\n'
                  '- `void insert(const K& key, const V& val)`：已存在则**覆盖**，不新增\n'
                  '- `V* find(const K& key)`：找不到返回 `nullptr`\n'
                  '- `bool erase(const K& key)`：删掉返回 true，没找到返回 false\n'
                  '- 扩容规则：`size() > bucket_count()` 时桶数**翻倍**，'
                  '且**只把已有节点重新挂到新桶上，不重新创建节点**\n\n'
                  '> 收口：阅读 3 里 `rehash` 换掉的只是「桶数组」，节点一个都没搬——\n'
                  '> 所以迭代器（记着桶位置）全废，而引用/指针（指着节点）全都还活着。这一关你自己验证一遍。',
        'starter_easy': r'''#include <cstddef>
#include <functional>

template <class K, class V>
class mini_unordered_map {
    struct node {
        K     key;
        V     value;
        node* next;
        node(const K& k, const V& v) : key(k), value(v), next(nullptr) {}
    };

    node**      buckets_ = nullptr;   // buckets_[i] 是第 i 个桶的链表头
    std::size_t bucketCount_ = 8;
    std::size_t size_ = 0;

    std::size_t bucket_of(const K& key) const {
        return std::hash<K>{}(key) % bucketCount_;
    }

public:
    mini_unordered_map() {
        // TODO: 分配 bucketCount_ 个 node*，全部置 nullptr
    }

    ~mini_unordered_map() {
        // TODO: 每个桶的链表逐个 delete，最后 delete[] buckets_
    }

    std::size_t size() const         { return size_; }
    std::size_t bucket_count() const { return bucketCount_; }
    double      load_factor() const {
        return static_cast<double>(size_) / static_cast<double>(bucketCount_);
    }

    V& operator[](const K& key) {
        // TODO: 桶里找到就返回 value；找不到就 new 一个 node(key, V{}) 头插进桶，再返回
    }

    void insert(const K& key, const V& val) {
        // TODO: 已存在则只覆盖 value；否则头插进 bucket_of(key) 这个桶，++size_，
        //       然后若 size_ > bucketCount_ 就 rehash（桶数翻倍、只重挂指针）
    }

    V* find(const K& key) {
        // TODO: 遍历 bucket_of(key) 那条链
        return nullptr;
    }

    bool erase(const K& key) {
        // TODO: 从链上摘掉；注意要删的可能正好是链表头
        return false;
    }

    mini_unordered_map(const mini_unordered_map&) = delete;
    mini_unordered_map& operator=(const mini_unordered_map&) = delete;
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <cstddef>
#include <functional>

// 实现 mini_unordered_map<K, V>（链地址法）：operator[] / insert / find / erase /
// size / bucket_count / load_factor / 析构。
// 要点：冲突用链表串；size 超过桶数就翻倍扩容；
//       扩容时只把已有节点重新挂到新桶，不要重建节点（否则引用会失效）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <cstddef>
#include <functional>

// 需求：手写哈希表（链地址法、自动扩容、增删查、析构不泄漏）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <cstddef>

int main() {
    int fail = 0;

    {   // 1 空表
        mini_unordered_map<int, int> m;
        if (m.size() != 0) { std::printf("FAIL: 空表 size 应为 0\n"); ++fail; }
        if (m.bucket_count() < 1) { std::printf("FAIL: 桶数至少应为 1\n"); ++fail; }
        if (m.find(1) != nullptr) { std::printf("FAIL: 空表 find 应返回 nullptr\n"); ++fail; }
    }

    {   // 2 insert / find / 覆盖
        mini_unordered_map<int, int> m;
        m.insert(1, 10);
        m.insert(2, 20);
        m.insert(1, 11);
        if (m.size() != 2) { std::printf("FAIL: 重复 insert 同一个 key 不应增加 size\n"); ++fail; }
        int* p = m.find(1);
        if (p == nullptr || *p != 11) { std::printf("FAIL: 重复 insert 应覆盖旧值\n"); ++fail; }
        if (m.find(99) != nullptr) { std::printf("FAIL: 不存在的 key 应返回 nullptr\n"); ++fail; }
    }

    {   // 3 operator[] 不存在则插入默认值
        mini_unordered_map<int, int> m;
        m[5] = 50;
        if (m.size() != 1) { std::printf("FAIL: operator[] 写入后 size 应为 1\n"); ++fail; }
        if (m[5] != 50) { std::printf("FAIL: operator[] 读回的值不对\n"); ++fail; }
        int v = m[6];
        if (v != 0) { std::printf("FAIL: operator[] 遇到缺失的 key 应插入默认值 V{}\n"); ++fail; }
        if (m.size() != 2) { std::printf("FAIL: operator[] 读缺失的 key 也应把它插进去\n"); ++fail; }
    }

    {   // 4 500 个键必然挤进同一个桶 —— 冲突链必须串对
        mini_unordered_map<int, int> m;
        for (int i = 0; i < 500; ++i) m.insert(i, i * 2);
        if (m.size() != 500) { std::printf("FAIL: 插入 500 个不同 key 后 size 应为 500\n"); ++fail; }
        int badKey = -1;
        for (int i = 0; i < 500; ++i) {
            int* p = m.find(i);
            if (p == nullptr || *p != i * 2) { badKey = i; break; }
        }
        if (badKey >= 0) { std::printf("FAIL: key=%d 查不回来，冲突链没串好\n", badKey); ++fail; }
        if (m.load_factor() > 1.0) {
            std::printf("FAIL: 装填因子超过 1，size > bucket_count 时应翻倍扩容\n"); ++fail;
        }
    }

    {   // 5 rehash 只重挂桶里的指针，节点不许搬家
        mini_unordered_map<int, int> m;
        m.insert(7, 70);
        int* p = m.find(7);
        std::size_t before = m.bucket_count();
        for (int i = 0; i < 200; ++i) m.insert(1000 + i, i);
        if (m.bucket_count() <= before) { std::printf("FAIL: 插入 200 个键后桶数应增长\n"); ++fail; }
        if (m.find(7) != p) { std::printf("FAIL: rehash 后节点地址变了，应只重挂指针不重建节点\n"); ++fail; }
        if (p == nullptr || *p != 70) { std::printf("FAIL: rehash 之后旧值丢了\n"); ++fail; }
    }

    {   // 6 erase：存在的、不存在的
        mini_unordered_map<int, int> m;
        for (int i = 0; i < 40; ++i) m.insert(i, i);
        if (!m.erase(20)) { std::printf("FAIL: erase 存在的 key 应返回 true\n"); ++fail; }
        if (m.find(20) != nullptr) { std::printf("FAIL: erase 之后不应再找到该 key\n"); ++fail; }
        if (m.size() != 39) { std::printf("FAIL: erase 之后 size 应减 1\n"); ++fail; }
        if (m.erase(20)) { std::printf("FAIL: erase 不存在的 key 应返回 false\n"); ++fail; }
        if (m.size() != 39) { std::printf("FAIL: 删除失败不应改变 size\n"); ++fail; }
    }

    {   // 7 逐个删空（覆盖「删的正好是链表头」），删空后还能继续用
        mini_unordered_map<int, int> m;
        for (int i = 0; i < 60; ++i) m.insert(i, i);
        int badKey = -1;
        for (int i = 0; i < 60; ++i) if (!m.erase(i)) { badKey = i; break; }
        if (badKey >= 0) { std::printf("FAIL: 逐个删除时 key=%d 删不掉\n", badKey); ++fail; }
        if (m.size() != 0) { std::printf("FAIL: 全部删除后 size 应为 0\n"); ++fail; }
        m.insert(1, 1);
        if (m.size() != 1 || m.find(1) == nullptr) {
            std::printf("FAIL: 删空之后应还能继续插入查找\n"); ++fail;
        }
    }

    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 24,
        'time_limit_ms': 2000,
    },
    {
        'id': 165,
        'chapter_id': 7,
        'type': 'blank',
        'title': '阅读 4 · 红黑树旋转与 ++it',
        'sort_order': 20,
        'keep_notes': True,
        'question': '补全 ① ② ③。想清楚：左旋之后，x 与 y 的父子关系是怎么换过来的？',
        'prompt': r'''// 简化版红黑树（map 的底层）：只看左旋与中序后继
// 左旋：把 x 的右孩子 y 提上来，x 降为 y 的左孩子
void rotate_left(node* x) {
    node* y = x->right;

    x->right = y->left;                 // y 的左子树改挂到 x 的右边
    if (y->left) y->left->parent = x;

    y->parent = x->parent;              // y 顶替 x 原来的位置
    if (!x->parent)                root_ = y;
    else if (x == x->parent->left) x->parent->left  = y;
    else                           x->parent->right = y;

    y->______ = x;                      // ① x 挂到 y 的哪一侧
    x->parent = ______;                 // ② x 的新父亲是谁
}

// 中序后继：二叉搜索树「迭代器 ++」的实现
node* next_node(node* n) {
    if (n->______) {                    // ③ 有哪棵子树，才需要往下钻
        n = n->right;                   //    然后一直走到底
        while (n->left) n = n->left;
        return n;
    }
    // 没有右子树：往上找「第一个把我当左孩子的祖先」
    while (n->parent && n == n->parent->right) n = n->parent;
    return n->parent;
}''',
        'answer': [['left'], ['y'], ['right']],
    },
    {
        'id': 166,
        'chapter_id': 7,
        'type': 'blank',
        'title': '阅读 5 · deque 的分段连续',
        'sort_order': 21,
        'keep_notes': True,
        'question': '补全 ① ②。想清楚：为什么拿 `&d[0]` 当「连续数组」的首地址用会出事？',
        'prompt': r'''// 简化版 deque：中控器 + 定长块
// 注：块大小按 512 字节切，是某个具体实现（libstdc++）的取舍，不是标准要求
template <class T>
class mini_deque {
    // ① 每块能放多少个元素
    static constexpr std::size_t kBlock = 512 / ______ > 1 ? 512 / sizeof(T) : 1;

    T**         map_;       // 中控器：一张「块指针数组」
    std::size_t mapSize_;   // 中控器容量
    std::size_t head_;      // 首元素在第几块
    std::size_t offset_;    // 首元素在块内第几个

    // ② 随机访问：先算块号，再算块内偏移
    T& operator[](std::size_t i) {
        std::size_t pos = offset_ + i;
        return map_[head_ + pos / ______][pos % kBlock];
    }
};''',
        'answer': [['sizeof(T)'], ['kBlock']],
    },
    # ================= C8 客观题（id 53-58） =================
    {
        'id': 53,
        'chapter_id': 8,
        'type': 'choice',
        'title': '选择 1 · 流状态检查',
        'sort_order': 1,
        'prompt': '''```cpp
ifstream f("a.txt");
if (f) { /* 打开成功 */ }
// if (f) 检查的是什么？
```''',
        'options': [
            {'label': 'A', 'text': '文件是否为空'},
            {'label': 'B', 'text': '流状态是否 good（无 fail/bad）'},
            {'label': 'C', 'text': 'eof 是否到达'},
            {'label': 'D', 'text': '文件是否存在'},
        ],
        'answer': 'B',
    },
    {
        'id': 54,
        'chapter_id': 8,
        'type': 'choice',
        'title': '选择 2 · 二进制 vs 文本',
        'sort_order': 2,
        'prompt': '''```cpp
// 写 int 到文件，要避免平台差异和截断，应该用？
```''',
        'options': [
            {'label': 'A', 'text': '文本模式 <<'},
            {'label': 'B', 'text': '二进制模式 write'},
            {'label': 'C', 'text': '都行'},
            {'label': 'D', 'text': '无中生有'},
        ],
        'answer': 'B',
    },
    {
        'id': 55,
        'chapter_id': 8,
        'type': 'choice',
        'title': '选择 3 · 读取循环惯用法',
        'sort_order': 3,
        'prompt': '''```cpp
while (f >> x) { /* ... */ }
// 这个循环什么时候结束？
```''',
        'options': [
            {'label': 'A', 'text': '读到 eof 或格式失败'},
            {'label': 'B', 'text': '读到换行'},
            {'label': 'C', 'text': '死循环'},
            {'label': 'D', 'text': '读满 buffer'},
        ],
        'answer': 'A',
    },
    {
        'id': 56,
        'chapter_id': 8,
        'type': 'blank',
        'title': '填空 1 · 追加模式',
        'sort_order': 4,
        'prompt': '''std::ofstream f("a.txt", std::ios::________);   // 追加模式''',
        'answer': ['app'],
    },
    {
        'id': 57,
        'chapter_id': 8,
        'type': 'blank',
        'title': '填空 2 · 逐行读取',
        'sort_order': 5,
        'prompt': '''std::ifstream f("a.txt");
std::string line;
while (std::________(f, line)) { /* 逐行读 */ }''',
        'question': '请补全代码：用 std::getline 从文件流逐行读取到 line。',
        'answer': ['getline'],
    },
    {
        'id': 58,
        'chapter_id': 8,
        'type': 'blank',
        'title': '填空 3 · filesystem 命名空间',
        'sort_order': 6,
        'prompt': '''namespace fs = std::________;   // C++17 文件系统''',
        'answer': ['filesystem'],
    },
    # ================= C9 客观题（id 59-64） =================
    {
        'id': 59,
        'chapter_id': 9,
        'type': 'choice',
        'title': '选择 1 · 数据竞争',
        'sort_order': 1,
        'prompt': '''```cpp
int counter = 0;
// 多线程同时 counter++，会发生什么？
```''',
        'options': [
            {'label': 'A', 'text': '结果一定正确'},
            {'label': 'B', 'text': '数据竞争，结果未定义'},
            {'label': 'C', 'text': '编译错误'},
            {'label': 'D', 'text': '线程安全'},
        ],
        'answer': 'B',
    },
    {
        'id': 60,
        'chapter_id': 9,
        'type': 'choice',
        'title': '选择 2 · 锁顺序死锁',
        'sort_order': 2,
        'prompt': '''```cpp
// 线程1: lock(a); lock(b);
// 线程2: lock(b); lock(a);
// 会发生什么？
```''',
        'options': [
            {'label': 'A', 'text': '正常运行'},
            {'label': 'B', 'text': '可能死锁（锁顺序不一致）'},
            {'label': 'C', 'text': '一定死锁'},
            {'label': 'D', 'text': '编译错误'},
        ],
        'answer': 'B',
    },
    {
        'id': 61,
        'chapter_id': 9,
        'type': 'choice',
        'title': '选择 3 · atomic vs mutex',
        'sort_order': 3,
        'prompt': '''```cpp
// 单变量的简单自增，用哪个最轻量？
```''',
        'options': [
            {'label': 'A', 'text': 'mutex'},
            {'label': 'B', 'text': 'std::atomic'},
            {'label': 'C', 'text': '无锁裸变量'},
            {'label': 'D', 'text': '都行'},
        ],
        'answer': 'B',
    },
    {
        'id': 62,
        'chapter_id': 9,
        'type': 'blank',
        'title': '填空 1 · 锁守卫',
        'sort_order': 4,
        'prompt': '''std::mutex m;
{
    std::________<std::mutex> lock(m);   // RAII 自动加解锁
}''',
        'answer': ['lock_guard'],
    },
    {
        'id': 63,
        'chapter_id': 9,
        'type': 'blank',
        'title': '填空 2 · condition_variable 谓词等待',
        'sort_order': 5,
        'prompt': '''std::unique_lock<std::mutex> lock(m);
cv.________(lock, []{ return ready; });   // 带谓词，防虚假唤醒''',
        'answer': ['wait'],
    },
    {
        'id': 64,
        'chapter_id': 9,
        'type': 'blank',
        'title': '填空 3 · 原子计数器',
        'sort_order': 6,
        'prompt': '''std::________<int> counter{0};   // 原子计数器''',
        'answer': ['atomic'],
    },
    # ================= C10 客观题（id 65-70） =================
    {
        'id': 65,
        'chapter_id': 10,
        'type': 'choice',
        'title': '选择 1 · TCP vs UDP',
        'sort_order': 1,
        'prompt': '''```cpp
// 需要可靠有序传输，选哪个？
```''',
        'options': [
            {'label': 'A', 'text': 'UDP'},
            {'label': 'B', 'text': 'TCP'},
            {'label': 'C', 'text': '都行'},
            {'label': 'D', 'text': '无中生有'},
        ],
        'answer': 'B',
    },
    {
        'id': 66,
        'chapter_id': 10,
        'type': 'choice',
        'title': '选择 2 · TCP 粘包',
        'sort_order': 2,
        'prompt': '''```cpp
// 期望接收 100 字节，一次 recv 可能返回？
```''',
        'options': [
            {'label': 'A', 'text': '一定 100 字节'},
            {'label': 'B', 'text': '任意 1-100 字节（TCP 是字节流）'},
            {'label': 'C', 'text': '一定 0 字节'},
            {'label': 'D', 'text': '超过 100 字节'},
        ],
        'answer': 'B',
    },
    {
        'id': 67,
        'chapter_id': 10,
        'type': 'choice',
        'title': '选择 3 · 字节序',
        'sort_order': 3,
        'prompt': '''```cpp
// 网络传输多字节整数，要解决什么问题？
```''',
        'options': [
            {'label': 'A', 'text': '大小端字节序转换'},
            {'label': 'B', 'text': '字符编码'},
            {'label': 'C', 'text': '数据压缩'},
            {'label': 'D', 'text': '数据加密'},
        ],
        'answer': 'A',
    },
    {
        'id': 68,
        'chapter_id': 10,
        'type': 'blank',
        'title': '填空 1 · 创建 socket',
        'sort_order': 4,
        'prompt': '''int fd = ________(AF_INET, SOCK_STREAM, 0);   // TCP socket''',
        'answer': ['socket'],
    },
    {
        'id': 69,
        'chapter_id': 10,
        'type': 'blank',
        'title': '填空 2 · 字节序转换',
        'sort_order': 5,
        'prompt': '''uint16_t p = ________(port);   // 主机序转网络序（端口）''',
        'answer': ['htons'],
    },
    {
        'id': 70,
        'chapter_id': 10,
        'type': 'blank',
        'title': '填空 3 · 开始监听',
        'sort_order': 6,
        'prompt': '''________(fd, 128);   // 开始监听''',
        'answer': ['listen'],
    },
    # ================= C11 客观题（id 71-76） =================
    {
        'id': 71,
        'chapter_id': 11,
        'type': 'choice',
        'title': '选择 1 · SQL 注入',
        'sort_order': 1,
        'prompt': '''```cpp
// 拼接 SQL 字符串构造查询，主要风险是？
```''',
        'options': [
            {'label': 'A', 'text': '性能差'},
            {'label': 'B', 'text': 'SQL 注入'},
            {'label': 'C', 'text': '语法错误'},
            {'label': 'D', 'text': '连接泄漏'},
        ],
        'answer': 'B',
    },
    {
        'id': 72,
        'chapter_id': 11,
        'type': 'choice',
        'title': '选择 2 · 事务',
        'sort_order': 2,
        'prompt': '''```cpp
// 一组操作要么全成功要么全回滚，用什么保证？
```''',
        'options': [
            {'label': 'A', 'text': '事务'},
            {'label': 'B', 'text': '索引'},
            {'label': 'C', 'text': '连接池'},
            {'label': 'D', 'text': '缓存'},
        ],
        'answer': 'A',
    },
    {
        'id': 73,
        'chapter_id': 11,
        'type': 'choice',
        'title': '选择 3 · 连接池',
        'sort_order': 3,
        'prompt': '''```cpp
// 连接池主要解决什么问题？
```''',
        'options': [
            {'label': 'A', 'text': '频繁建立/销毁连接的开销'},
            {'label': 'B', 'text': 'SQL 优化'},
            {'label': 'C', 'text': '数据安全'},
            {'label': 'D', 'text': '索引维护'},
        ],
        'answer': 'A',
    },
    {
        'id': 74,
        'chapter_id': 11,
        'type': 'blank',
        'title': '填空 1 · 预处理占位符',
        'sort_order': 4,
        'prompt': '''std::string sql = "SELECT * FROM t WHERE id = ________";   // 用预处理语句防注入，占位符写在这里''',
        'answer': ['?'],
    },
    {
        'id': 75,
        'chapter_id': 11,
        'type': 'blank',
        'title': '填空 2 · 提交事务',
        'sort_order': 5,
        'prompt': '''conn.________();   // 提交事务''',
        'answer': ['commit'],
    },
    {
        'id': 76,
        'chapter_id': 11,
        'type': 'blank',
        'title': '填空 3 · 回滚事务',
        'sort_order': 6,
        'prompt': '''conn.________();   // 回滚事务''',
        'answer': ['rollback'],
    },
    # ================= C12 客观题（id 77-82） =================
    {
        'id': 77,
        'chapter_id': 12,
        'type': 'choice',
        'title': '选择 1 · constexpr 函数编译期求值',
        'sort_order': 1,
        'prompt': '''```cpp
constexpr int square(int x) { return x * x; }
int arr[square(3)];   // 数组大小是？
```''',
        'options': [
            {'label': 'A', 'text': '9'},
            {'label': 'B', 'text': '编译错误'},
            {'label': 'C', 'text': '运行时求值'},
            {'label': 'D', 'text': '未定义'},
        ],
        'answer': 'A',
    },
    {
        'id': 78,
        'chapter_id': 12,
        'type': 'choice',
        'title': '选择 2 · consteval 强制编译期',
        'sort_order': 2,
        'prompt': '''```cpp
consteval int f(int x) { return x; }
int y = 5;
int z = f(y);   // 这行？
```''',
        'options': [
            {'label': 'A', 'text': '编译错误（consteval 必须编译期调用）'},
            {'label': 'B', 'text': '正常，运行时调用'},
            {'label': 'C', 'text': '未定义'},
            {'label': 'D', 'text': '返回 5'},
        ],
        'answer': 'A',
    },
    {
        'id': 79,
        'chapter_id': 12,
        'type': 'choice',
        'title': '选择 3 · constinit',
        'sort_order': 3,
        'prompt': '''```cpp
// constinit 的作用是？
```''',
        'options': [
            {'label': 'A', 'text': '保证编译期初始化，避免静态初始化顺序问题'},
            {'label': 'B', 'text': '让变量不可变'},
            {'label': 'C', 'text': '让变量线程安全'},
            {'label': 'D', 'text': '让变量堆分配'},
        ],
        'answer': 'A',
    },
    {
        'id': 80,
        'chapter_id': 12,
        'type': 'blank',
        'title': '填空 1 · constexpr',
        'sort_order': 4,
        'prompt': '''________ int square(int x) { return x * x; }   // 编译期可求值的函数''',
        'answer': ['constexpr'],
    },
    {
        'id': 81,
        'chapter_id': 12,
        'type': 'blank',
        'title': '填空 2 · consteval',
        'sort_order': 5,
        'prompt': '''________ int f(int x) { return x * 2; }   // 只能在编译期调用''',
        'answer': ['consteval'],
    },
    {
        'id': 82,
        'chapter_id': 12,
        'type': 'blank',
        'title': '填空 3 · constinit',
        'sort_order': 6,
        'prompt': '''________ int g = 42;   // 保证编译期初始化''',
        'answer': ['constinit'],
    },
    # ================= C13 客观题（id 83-88） =================
    {
        'id': 83,
        'chapter_id': 13,
        'type': 'choice',
        'title': '选择 1 · concepts 约束',
        'sort_order': 1,
        'prompt': '''```cpp
template <typename T>
concept Numeric = std::is_arithmetic_v<T>;

template <Numeric T>
T add(T a, T b) { return a + b; }

add("a", "b");   // 传入字符串会？
```''',
        'options': [
            {'label': 'A', 'text': '编译错误（不满足 Numeric 约束）'},
            {'label': 'B', 'text': '运行时错误'},
            {'label': 'C', 'text': '正常返回 "ab"'},
            {'label': 'D', 'text': '未定义'},
        ],
        'answer': 'A',
    },
    {
        'id': 84,
        'chapter_id': 13,
        'type': 'choice',
        'title': '选择 2 · ranges 惰性求值',
        'sort_order': 2,
        'prompt': '''```cpp
auto r = v | std::views::filter(f) | std::views::transform(g);
// 这行会立即执行 filter/transform 吗？
```''',
        'options': [
            {'label': 'A', 'text': '会立即执行'},
            {'label': 'B', 'text': '不会，惰性求值，遍历时才计算'},
            {'label': 'C', 'text': '取决于编译器'},
            {'label': 'D', 'text': '编译错误'},
        ],
        'answer': 'B',
    },
    {
        'id': 85,
        'chapter_id': 13,
        'type': 'choice',
        'title': '选择 3 · 协程三关键字',
        'sort_order': 3,
        'prompt': '''```cpp
// co_yield 的作用是？
```''',
        'options': [
            {'label': 'A', 'text': '挂起并产出一个值，之后可恢复'},
            {'label': 'B', 'text': '终止协程'},
            {'label': 'C', 'text': '等待异步操作'},
            {'label': 'D', 'text': '无中生有'},
        ],
        'answer': 'A',
    },
    {
        'id': 86,
        'chapter_id': 13,
        'type': 'blank',
        'title': '填空 1 · concept 定义',
        'sort_order': 4,
        'prompt': '''template <typename T>
________ Numeric = std::is_arithmetic_v<T>;   // 定义一个约束''',
        'answer': ['concept'],
    },
    {
        'id': 87,
        'chapter_id': 13,
        'type': 'blank',
        'title': '填空 2 · requires 子句',
        'sort_order': 5,
        'prompt': '''template <typename T>
________ std::integral<T>   // 约束 T 是整数类型
void f(T t);''',
        'answer': ['requires'],
    },
    {
        'id': 88,
        'chapter_id': 13,
        'type': 'blank',
        'title': '填空 3 · co_yield',
        'sort_order': 6,
        'prompt': '''generator<int> gen() {
    for (int i = 0; i < 3; ++i)
        ________ i;   // 协程生成器里产出值的关键字
}''',
        'answer': ['co_yield'],
    },
    # ================= C14 客观题（id 89-94） =================
    {
        'id': 89,
        'chapter_id': 14,
        'type': 'choice',
        'title': '选择 1 · module vs include',
        'sort_order': 1,
        'prompt': '''```cpp
// module 相比 #include 的优势是？
```''',
        'options': [
            {'label': 'A', 'text': '编译隔离，避免宏污染和重复解析'},
            {'label': 'B', 'text': '运行更快'},
            {'label': 'C', 'text': '无需编译'},
            {'label': 'D', 'text': '无中生有'},
        ],
        'answer': 'A',
    },
    {
        'id': 90,
        'chapter_id': 14,
        'type': 'choice',
        'title': '选择 2 · ODR 单一定义规则',
        'sort_order': 2,
        'prompt': '''```cpp
// 同一个非 inline 函数在多个编译单元被定义，会导致？
```''',
        'options': [
            {'label': 'A', 'text': '链接错误（多重定义）'},
            {'label': 'B', 'text': '自动去重'},
            {'label': 'C', 'text': '运行时错误'},
            {'label': 'D', 'text': '无影响'},
        ],
        'answer': 'A',
    },
    {
        'id': 91,
        'chapter_id': 14,
        'type': 'choice',
        'title': '选择 3 · 头文件保护',
        'sort_order': 3,
        'prompt': '''```cpp
// 防止头文件重复包含的惯用法？
```''',
        'options': [
            {'label': 'A', 'text': 'include guard 或 #pragma once'},
            {'label': 'B', 'text': 'extern'},
            {'label': 'C', 'text': 'static'},
            {'label': 'D', 'text': 'inline'},
        ],
        'answer': 'A',
    },
    {
        'id': 92,
        'chapter_id': 14,
        'type': 'blank',
        'title': '填空 1 · 导出模块',
        'sort_order': 4,
        'prompt': '''________ module math;   // 声明模块接口''',
        'answer': ['export'],
    },
    {
        'id': 93,
        'chapter_id': 14,
        'type': 'blank',
        'title': '填空 2 · 导入模块',
        'sort_order': 5,
        'prompt': '''________ math;   // 导入模块''',
        'answer': ['import'],
    },
    {
        'id': 94,
        'chapter_id': 14,
        'type': 'blank',
        'title': '填空 3 · include guard 结尾',
        'sort_order': 6,
        'prompt': '''#ifndef FOO_H
#define FOO_H
// ...
________   // 结尾''',
        'answer': ['#endif'],
    },
    # ================= C3 写代码题（id 95-99） =================
    {
        'id': 95,
        'chapter_id': 3,
        'type': 'short',
        'title': '短题 1 · unique_ptr 所有权转移',
        'sort_order': 7,
        'prompt': '实现两个函数，练习 `unique_ptr` 的独占所有权与移动语义：\n\n'
                  '1. `std::unique_ptr<int> make_int(int v)`：创建并返回拥有 `v` 的 unique_ptr\n'
                  '2. `int take_ownership(std::unique_ptr<int> p)`：按值接管所有权，返回 `*p`\n\n'
                  '> 考点：unique_ptr 不可拷贝、只能移动；move 后源指针变空。',
        'starter_easy': r'''#include <memory>

// TODO: 创建并返回拥有 v 的 unique_ptr
std::unique_ptr<int> make_int(int v) {
    // TODO
}

// TODO: 按值接管所有权，返回 *p
int take_ownership(std::unique_ptr<int> p) {
    // TODO
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <memory>

// 实现接口：
//   std::unique_ptr<int> make_int(int v);
//   int take_ownership(std::unique_ptr<int> p);
// 用 std::make_unique 创建；take_ownership 按值接收（移动语义），返回 *p。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <memory>

// 需求：练习 unique_ptr 独占所有权
//   1. make_int(v) 返回拥有 v 的 unique_ptr
//   2. take_ownership(p) 按值接收（移动），返回 *p
//   隐藏测试验证：创建值正确、move 后源为空、按值接管正确。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <memory>

int main() {
    int fail = 0;
    // 用例1：make_int 创建正确值
    std::unique_ptr<int> p = make_int(42);
    if (!p || *p != 42) { std::printf("FAIL: make_int 应返回拥有 42 的 unique_ptr\n"); ++fail; }
    // 用例2：move 后源为空
    std::unique_ptr<int> q = std::move(p);
    if (p != nullptr) { std::printf("FAIL: move 后源 unique_ptr 应为空\n"); ++fail; }
    if (!q || *q != 42) { std::printf("FAIL: move 后目标应拥有 42\n"); ++fail; }
    // 用例3：take_ownership 按值接管
    if (take_ownership(std::move(q)) != 42) { std::printf("FAIL: take_ownership 应返回 42\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 4,
        'time_limit_ms': 2000,
    },
    {
        'id': 96,
        'chapter_id': 3,
        'type': 'short',
        'title': '短题 2 · weak_ptr 打破循环引用',
        'sort_order': 8,
        'prompt': '下面的 `Node` 用 `shared_ptr` 存 `next`，形成循环引用会导致内存泄漏。修复它：\n\n'
                  '约定接口（隐藏测试依赖）：\n'
                  '- `struct Node { std::weak_ptr<Node> next; int value; Node(int v); }`（next 改 weak_ptr）\n'
                  '- `Node` 有静态成员 `static int alive`：构造 +1、析构 -1\n'
                  '- `bool has_next(const std::shared_ptr<Node>& n)`：n 的 next 是否有效（lock 成功）\n\n'
                  '> 考点：shared_ptr 循环引用泄漏；weak_ptr 打破循环；lock() 检查有效性。',
        'starter_easy': r'''#include <memory>

struct Node {
    std::shared_ptr<Node> next;   // BUG: 应改为 weak_ptr 打破循环引用
    int value;
    static int alive;
    Node(int v) : value(v) { ++alive; }
    ~Node() { --alive; }
};
int Node::alive = 0;

// TODO: has_next —— n 的 next 是否有效（用 lock() 检查）
bool has_next(const std::shared_ptr<Node>& n) {
    // TODO
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <memory>

// 实现：
//   struct Node { std::weak_ptr<Node> next; int value; Node(int v); static int alive; };
//   Node::alive 构造 +1、析构 -1（静态成员需类外定义）
//   bool has_next(const std::shared_ptr<Node>& n)：next.lock() 是否成功

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <memory>

// 需求：用 weak_ptr 打破 shared_ptr 循环引用
//   Node 用 weak_ptr 存 next；静态 alive 计数（构造+1 析构-1）；
//   has_next(n) 判断 n 的 next 是否有效。
//   隐藏测试：循环引用后离开作用域应释放（alive 归零）；has_next 判断有效/无效。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <memory>

int main() {
    int fail = 0;
    {
        std::shared_ptr<Node> a = std::make_shared<Node>(1);
        std::shared_ptr<Node> b = std::make_shared<Node>(2);
        a->next = b;
        b->next = a;
        if (Node::alive != 2) { std::printf("FAIL: 应创建 2 个 Node\n"); ++fail; }
    }
    // 离开作用域：next 用 weak_ptr 则释放，alive 归零；用 shared_ptr 则泄漏
    if (Node::alive != 0) {
        std::printf("FAIL: 循环引用导致泄漏，应把 next 改为 weak_ptr\n");
        ++fail;
    }
    // has_next 验证
    std::shared_ptr<Node> c = std::make_shared<Node>(3);
    std::shared_ptr<Node> d = std::make_shared<Node>(4);
    c->next = d;
    if (!has_next(c)) { std::printf("FAIL: c 的 next 应有效\n"); ++fail; }
    if (has_next(d)) { std::printf("FAIL: d 无 next，应返回 false\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 4,
        'time_limit_ms': 2000,
    },
    {
        'id': 97,
        'chapter_id': 3,
        'type': 'short',
        'title': '短题 3 · 自定义 deleter 数组守卫',
        'sort_order': 9,
        'prompt': '用 `unique_ptr` + 自定义 deleter 管理一个动态分配的 int 数组：\n\n'
                  '- 自定义 deleter `ArrayDeleter`：用 `delete[]` 释放（不是 `delete`）\n'
                  '- `std::unique_ptr<int[], ArrayDeleter> make_array(int n, int v)`：创建 n 个元素、全部初始化为 v\n\n'
                  '> 考点：unique_ptr 自定义 deleter；数组版本用 `int[]` 与 `delete[]`。',
        'starter_easy': r'''#include <memory>

// TODO: 自定义 deleter，用 delete[] 释放
struct ArrayDeleter {
    void operator()(int* p) const {
        // TODO
    }
};

// TODO: 创建 n 个元素、全部初始化为 v 的数组守卫
std::unique_ptr<int[], ArrayDeleter> make_array(int n, int v) {
    // TODO
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <memory>

// 实现：
//   struct ArrayDeleter { void operator()(int* p) const; };  // delete[] p
//   std::unique_ptr<int[], ArrayDeleter> make_array(int n, int v);
//   用 new int[n] 分配，std::fill 初始化，返回 unique_ptr<int[], ArrayDeleter>。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <memory>

// 需求：unique_ptr + 自定义 deleter 管理 int 数组
//   ArrayDeleter 用 delete[] 释放；make_array(n, v) 创建 n 个 v。
//   隐藏测试验证：数组大小正确、元素全部初始化为 v、元素可修改。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <memory>

int main() {
    int fail = 0;
    // 用例1：创建 5 个元素，全部为 7
    auto arr = make_array(5, 7);
    if (!arr) { std::printf("FAIL: make_array 应返回非空\n"); ++fail; }
    bool all7 = true;
    for (int i = 0; i < 5; ++i) if (arr[i] != 7) all7 = false;
    if (!all7) { std::printf("FAIL: 所有元素应初始化为 7\n"); ++fail; }
    // 用例2：元素可独立修改
    arr[0] = 99;
    if (arr[0] != 99 || arr[1] != 7) { std::printf("FAIL: 元素修改异常\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 3,
        'time_limit_ms': 2000,
    },
    {
        'id': 98,
        'chapter_id': 3,
        'type': 'short',
        'title': '短题 4 · 手写简易 shared_ptr',
        'sort_order': 10,
        'prompt': '手写一个简易的引用计数智能指针 `SimpleSharedPtr<T>`：\n\n'
                  '- 构造：`explicit SimpleSharedPtr(T* p)`，引用计数 = 1\n'
                  '- 拷贝构造：引用计数 +1\n'
                  '- 析构：引用计数 -1，归零则释放指针\n'
                  '- `T* get() const`、`T& operator*() const`、`int use_count() const`\n'
                  '- 工厂 `template <typename T> SimpleSharedPtr<T> make_simple(T v)`\n\n'
                  '> 考点：引用计数、拷贝控制、工厂函数。',
        'starter_easy': r'''#include <cstddef>

template <typename T>
class SimpleSharedPtr {
    T* ptr_;
    std::size_t* refcount_;
public:
    explicit SimpleSharedPtr(T* p) {
        // TODO: ptr_ = p; refcount_ = new size_t(1);
    }
    SimpleSharedPtr(const SimpleSharedPtr& o) {
        // TODO: 共享指针与控制块，计数 +1
    }
    ~SimpleSharedPtr() {
        // TODO: 计数 -1，归零则 delete ptr_ 和 refcount_
    }
    T* get() const { return ptr_; }
    T& operator*() const { return *ptr_; }
    int use_count() const { return refcount_ ? (int)*refcount_ : 0; }
};

template <typename T>
SimpleSharedPtr<T> make_simple(T v) {
    return SimpleSharedPtr<T>(new T(v));
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <cstddef>

// 实现 SimpleSharedPtr<T>：
//   explicit SimpleSharedPtr(T* p)：ptr_ + refcount_(new size_t(1))
//   拷贝构造：共享 ptr_/refcount_，计数 +1
//   析构：计数 -1，归零释放 ptr_ 和 refcount_
//   get()/operator*()/use_count()
//   template <typename T> SimpleSharedPtr<T> make_simple(T v)

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <cstddef>

// 需求：手写简易引用计数智能指针 SimpleSharedPtr<T>
//   拷贝共享控制块、计数 +1；析构 -1，归零释放；
//   提供 get/operator*/use_count；工厂 make_simple(v)。
//   隐藏测试验证：引用计数正确增减、归零释放（alive 计数）、make_simple 基本使用。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>

int main() {
    int fail = 0;
    {
        SimpleSharedPtr<int> a(new int(10));
        if (a.use_count() != 1) { std::printf("FAIL: 初始 use_count 应为 1\n"); ++fail; }
        if (*a != 10) { std::printf("FAIL: operator* 应返回 10\n"); ++fail; }
        {
            SimpleSharedPtr<int> b = a;   // 拷贝
            if (a.use_count() != 2 || b.use_count() != 2) {
                std::printf("FAIL: 拷贝后 use_count 应为 2\n"); ++fail;
            }
            *b = 20;
        }
        // b 析构，use_count 回到 1
        if (a.use_count() != 1) { std::printf("FAIL: b 析构后 use_count 应为 1\n"); ++fail; }
        if (*a != 20) { std::printf("FAIL: 共享对象值应为 20\n"); ++fail; }
    }
    // a 析构，归零释放（无泄漏可观察，这里只验证不崩）
    auto s = make_simple(42);
    if (*s != 42 || s.use_count() != 1) { std::printf("FAIL: make_simple 异常\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 6,
        'time_limit_ms': 2000,
    },
    {
        'id': 99,
        'chapter_id': 3,
        'type': 'boss',
        'title': 'Boss · RAII 资源守卫',
        'sort_order': 11,
        'prompt': '实现一个不可拷贝、可移动的 RAII 资源守卫 `ResourceGuard`：\n\n'
                  '- 构造时接管一个 `int*` 资源（`explicit ResourceGuard(int* p)`）\n'
                  '- 析构时释放资源（`delete`）\n'
                  '- 拷贝构造 / 拷贝赋值 `= delete`\n'
                  '- 移动构造 / 移动赋值：转移所有权，源守卫置空\n'
                  '- `int* get() const`、`bool owns() const`（是否持有资源）、`int* release()`（交出资源并置空）\n\n'
                  '> 收口：=delete 禁拷贝 + 移动语义 + 析构自动释放（异常安全）。',
        'starter_easy': r'''class ResourceGuard {
    int* p_;
public:
    explicit ResourceGuard(int* p) : p_(p) {}
    ResourceGuard(const ResourceGuard&) = delete;
    ResourceGuard& operator=(const ResourceGuard&) = delete;

    // TODO: 移动构造 —— 转移 p_，源置空
    ResourceGuard(ResourceGuard&& other) {
        // TODO
    }
    // TODO: 移动赋值 —— 先释放自己的，再转移
    ResourceGuard& operator=(ResourceGuard&& other) {
        // TODO
        return *this;
    }
    ~ResourceGuard() {
        // TODO: 释放 p_
    }
    int* get() const { return p_; }
    bool owns() const { return p_ != nullptr; }
    int* release() {
        // TODO: 交出资源并置空
    }
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''// 实现 ResourceGuard：
//   explicit ResourceGuard(int* p)
//   =delete 拷贝构造/拷贝赋值
//   移动构造/移动赋值：转移 p_，源置空（移动赋值先释放自己的）
//   析构 delete p_
//   get()/owns()/release()

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''// 需求：不可拷贝、可移动的 RAII 资源守卫
//   接管 int*；析构释放；=delete 拷贝；移动转移所有权（源置空）；
//   get/owns/release。
//   隐藏测试验证：析构释放（alive 计数）、移动后源 owns()==false、
//   移动赋值不泄漏、release 交出所有权。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>

static int g_alive = 0;
struct Tracked {
    int v;
    Tracked(int x) : v(x) { ++g_alive; }
    ~Tracked() { --g_alive; }
};

int main() {
    int fail = 0;
    {
        Tracked* t = new Tracked(1);
        if (g_alive != 1) { std::printf("FAIL: 应创建一个 Tracked\n"); ++fail; }
        {
            ResourceGuard g(t);
            if (!g.owns() || g.get() != t) { std::printf("FAIL: 守卫应持有资源\n"); ++fail; }
        }
        // g 析构，释放 t
        if (g_alive != 0) { std::printf("FAIL: 析构应释放资源\n"); ++fail; }
    }
    // 移动语义
    {
        ResourceGuard a(new Tracked(2));
        if (g_alive != 1) { std::printf("FAIL: 移动测试应创建 1 个\n"); ++fail; }
        ResourceGuard b(std::move(a));
        if (a.owns()) { std::printf("FAIL: 移动后源应不再持有\n"); ++fail; }
        if (!b.owns()) { std::printf("FAIL: 移动后目标应持有\n"); ++fail; }
        // release
        Tracked* raw = (Tracked*)b.release();
        if (b.owns()) { std::printf("FAIL: release 后应置空\n"); ++fail; }
        delete raw;
        if (g_alive != 0) { std::printf("FAIL: release 后手动释放应归零\n"); ++fail; }
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 8,
        'time_limit_ms': 2000,
    },
    # ================= C4 写代码题（id 100-104） =================
    {
        'id': 100,
        'chapter_id': 4,
        'type': 'short',
        'title': '短题 1 · lambda 捕获',
        'sort_order': 7,
        'prompt': '实现 `std::function<int(int)> make_adder(int n)`：返回一个 lambda，把参数加上 n。\n\n'
                  '> 考点：lambda 按值捕获（[n] 或 [=]），捕获的是 n 的拷贝。',
        'starter_easy': r'''#include <functional>

// TODO: 返回一个 lambda，把参数加上 n（按值捕获 n）
std::function<int(int)> make_adder(int n) {
    return [____](int x) {
        // TODO
    };
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <functional>

// 实现 std::function<int(int)> make_adder(int n)：返回 lambda 把参数加 n。
// 按值捕获 n（[n] 或 [=]），保证 lambda 在 n 销毁后仍有效。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <functional>

// 需求：make_adder(n) 返回把参数加 n 的 lambda。
//   隐藏测试验证：不同 n 独立、按值捕获（n 销毁后 lambda 仍正确）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <functional>

int main() {
    int fail = 0;
    auto add10 = make_adder(10);
    if (add10(5) != 15) { std::printf("FAIL: add10(5) 应为 15\n"); ++fail; }
    auto add0 = make_adder(0);
    if (add0(42) != 42) { std::printf("FAIL: add0(42) 应为 42\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 101,
        'chapter_id': 4,
        'type': 'short',
        'title': '短题 2 · 捕获悬垂引用',
        'sort_order': 8,
        'prompt': '下面的 lambda 按引用捕获局部变量，函数返回后引用悬垂，调用是未定义行为。\n'
                  '修复为按值捕获 + `mutable`，让计数器状态保留在 lambda 内部。\n\n'
                  '> 考点：捕获引用悬垂；按值捕获 + mutable 保存可变状态。',
        'starter_easy': r'''#include <functional>

// BUG: [&] 捕获引用，count 销毁后悬垂。改为按值捕获 + mutable。
std::function<int()> make_counter() {
    int count = 0;
    return [____]() ________ {   // 空1：按值捕获；空2：mutable
        return ++count;
    };
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <functional>

// 实现 make_counter()：返回自增计数器 lambda。
// 不能按引用捕获局部变量（悬垂）；用按值捕获 [count] + mutable。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <functional>

// 需求：make_counter() 返回每次调用递增的 lambda。
//   隐藏测试验证：返回后调用不悬垂、状态在 lambda 内保持。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <functional>

int main() {
    int fail = 0;
    auto f = make_counter();
    if (f() != 1) { std::printf("FAIL: 第一次调用应为 1\n"); ++fail; }
    if (f() != 2) { std::printf("FAIL: 第二次调用应为 2（状态保持）\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 102,
        'chapter_id': 4,
        'type': 'short',
        'title': '短题 3 · std::function 回调',
        'sort_order': 9,
        'prompt': '用 `std::function` 实现一个可设置、可调用的回调封装 `Callback`：\n\n'
                  '- `void set(std::function<void(int)> fn)`：设置回调\n'
                  '- `void call(int v)`：若已设置则调用 `fn_(v)`，未设置则无操作\n\n'
                  '> 考点：std::function 存储任意可调用对象；空 std::function 的判断。',
        'starter_easy': r'''#include <functional>

class Callback {
    std::function<void(int)> fn_;
public:
    void set(std::function<void(int)> fn) {
        // TODO
    }
    void call(int v) {
        // TODO: 若 fn_ 非空则调用
    }
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <functional>

// 实现 Callback：set(std::function<void(int)>) 存储；call(int) 非空则调用。
// 用 if (fn_) 判断是否已设置。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <functional>

// 需求：可设置、可调用的回调封装。
//   隐藏测试验证：set 后 call 触发、未 set 时 call 不崩。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <functional>

int main() {
    int fail = 0;
    Callback cb;
    int called = 0;
    cb.call(1);  // 未设置，无操作，不崩
    cb.set([&](int v){ called = v; });
    cb.call(42);
    if (called != 42) { std::printf("FAIL: 设置后 call(42) 应触发回调\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 1,
        'time_limit_ms': 2000,
    },
    {
        'id': 103,
        'chapter_id': 4,
        'type': 'short',
        'title': '短题 4 · lambda + 算法流水线',
        'sort_order': 10,
        'prompt': '用标准算法 + lambda 实现两个函数：\n\n'
                  '- `int count_positive(const std::vector<int>& v)`：用 `std::count_if` 统计正数个数\n'
                  '- `std::vector<int> double_all(const std::vector<int>& v)`：用 `std::transform` 把每个元素翻倍\n\n'
                  '> 考点：lambda 作为谓词/变换传给算法。',
        'starter_easy': r'''#include <vector>
#include <algorithm>

// TODO: 用 std::count_if + lambda 统计正数
int count_positive(const std::vector<int>& v) {
    // TODO
}

// TODO: 用 std::transform + lambda 翻倍
std::vector<int> double_all(const std::vector<int>& v) {
    // TODO
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <vector>
#include <algorithm>

// 实现 count_positive（std::count_if）和 double_all（std::transform）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <vector>
#include <algorithm>

// 需求：用算法 + lambda 实现 count_positive 和 double_all。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <vector>

int main() {
    int fail = 0;
    std::vector<int> a{-1, 0, 1, 2};
    if (count_positive(a) != 2) { std::printf("FAIL: 正数个数应为 2\n"); ++fail; }
    std::vector<int> b{1, 2, 3};
    std::vector<int> r = double_all(b);
    if (r.size() != 3 || r[0] != 2 || r[1] != 4 || r[2] != 6) {
        std::printf("FAIL: double_all 应返回 {2,4,6}\n"); ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 104,
        'chapter_id': 4,
        'type': 'boss',
        'title': 'Boss · 回调事件系统',
        'sort_order': 11,
        'prompt': '用 `std::function` + lambda 实现一个事件系统 `EventSystem`：\n\n'
                  '- `int subscribe(std::function<void(int)> fn)`：注册回调，返回 handler id（从 0 递增）\n'
                  '- `void unsubscribe(int id)`：注销指定 handler（注销后不再触发）\n'
                  '- `void emit(int v)`：触发所有已注册的 handler\n\n'
                  '> 收口：std::function 存储 + 注册/注销生命周期 + lambda。',
        'starter_easy': r'''#include <functional>
#include <vector>

class EventSystem {
    std::vector<std::function<void(int)>> handlers_;
    int next_id_ = 0;
public:
    // TODO: 注册回调，返回 id
    int subscribe(std::function<void(int)> fn) {
        // TODO
    }
    // TODO: 注销指定 id（把对应 handler 置空）
    void unsubscribe(int id) {
        // TODO
    }
    // TODO: 触发所有非空 handler
    void emit(int v) {
        // TODO
    }
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <functional>
#include <vector>

// 实现 EventSystem：
//   subscribe(fn) 追加到 handlers_，返回递增 id
//   unsubscribe(id) 把 handlers_[id] 置空
//   emit(v) 遍历，非空 handler 调用 fn(v)

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <functional>
#include <vector>

// 需求：回调事件系统（注册/注销/触发）。
//   隐藏测试验证：注册后触发、注销后不触发、多 handler 都触发、注销后 emit 不崩。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <functional>

int main() {
    int fail = 0;
    EventSystem es;
    int a = 0, b = 0;
    int ida = es.subscribe([&](int v){ a = v; });
    int idb = es.subscribe([&](int v){ b = v; });
    es.emit(5);
    if (a != 5 || b != 5) { std::printf("FAIL: emit 应触发所有 handler\n"); ++fail; }
    es.unsubscribe(ida);
    es.emit(9);
    if (a != 5) { std::printf("FAIL: 注销后 a 不应再变\n"); ++fail; }
    if (b != 9) { std::printf("FAIL: 未注销的 b 应更新\n"); ++fail; }
    es.unsubscribe(idb);
    es.emit(1);  // 全部注销，不崩
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 3,
        'time_limit_ms': 2000,
    },
    # ================= C5 写代码题（id 105-109） =================
    {
        'id': 105,
        'chapter_id': 5,
        'type': 'short',
        'title': '短题 1 · 变参模板求和',
        'sort_order': 7,
        'prompt': '实现变参模板求和函数 `sum`，支持任意个同类型参数：\n\n'
                  '可用递归展开（单参数出口 + 递归），或用折叠表达式（C++17）。\n\n'
                  '> 考点：变参模板、递归展开 / 折叠表达式。',
        'starter_easy': r'''// TODO: 单参数出口
template <typename T>
T sum(T t) {
    // TODO
}

// TODO: 递归展开：t + sum(args...)
template <typename T, typename... Args>
T sum(T t, Args... args) {
    // TODO
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''// 实现变参模板 sum：
//   单参数出口 sum(t) = t；递归 sum(t, args...) = t + sum(args...)
//   或用 C++17 折叠表达式 (args + ...)。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''// 需求：变参模板求和 sum，支持任意个同类型参数。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>

int main() {
    int fail = 0;
    if (sum(1, 2, 3, 4) != 10) { std::printf("FAIL: sum(1,2,3,4) 应为 10\n"); ++fail; }
    if (sum(5) != 5) { std::printf("FAIL: sum(5) 应为 5\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 106,
        'chapter_id': 5,
        'type': 'short',
        'title': '短题 2 · 模板特化 type_name',
        'sort_order': 8,
        'prompt': '实现 `type_name<T>()`：对 `int` 返回 `"int"`、`double` 返回 `"double"`、其他类型返回 `"other"`。\n\n'
                  '> 考点：模板特化（全特化）、通用版本作为兜底。',
        'starter_easy': r'''// 通用版本：兜底
template <typename T>
const char* type_name() {
    return "other";
}

// TODO: 为 int 写全特化
template <>
const char* type_name<int>() {
    // TODO
}

// TODO: 为 double 写全特化
template <>
const char* type_name<double>() {
    // TODO
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''// 实现 type_name<T>()：int -> "int"，double -> "double"，其他 -> "other"。
// 用全特化 template <> const char* type_name<int>() {...}。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''// 需求：type_name<T>() 返回类型名字符串（int/double/其他）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <cstring>

int main() {
    int fail = 0;
    if (std::strcmp(type_name<int>(), "int") != 0) { std::printf("FAIL: int 应返回 \"int\"\n"); ++fail; }
    if (std::strcmp(type_name<double>(), "double") != 0) { std::printf("FAIL: double 应返回 \"double\"\n"); ++fail; }
    if (std::strcmp(type_name<float>(), "other") != 0) { std::printf("FAIL: float 应返回 \"other\"\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 3,
        'time_limit_ms': 2000,
    },
    {
        'id': 107,
        'chapter_id': 5,
        'type': 'short',
        'title': '短题 3 · 类型萃取 is_integral_type',
        'sort_order': 9,
        'prompt': '实现类型萃取 `is_integral_type<T>`，判断 T 是否是整数类型：\n\n'
                  '- `int`、`long`、`long long`、`short` 等为 true\n'
                  '- `double`、`float`、指针等为 false\n\n'
                  '> 考点：std::true_type / std::false_type 继承实现类型萃取。',
        'starter_easy': r'''#include <type_traits>

// 通用版本：默认不是整数
template <typename T>
struct is_integral_type : std::false_type {};

// TODO: 为 int 特化（继承 std::true_type）
template <>
struct is_integral_type<int> : std::true_type {};

// TODO: 为 long long 特化
template <>
struct is_integral_type<long long> : std::true_type {};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <type_traits>

// 实现 is_integral_type<T>：整数类型 true，其他 false。
// 通用继承 std::false_type；int/long/long long/short 特化继承 std::true_type。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <type_traits>

// 需求：is_integral_type<T> 判断整数类型。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>

int main() {
    int fail = 0;
    if (!is_integral_type<int>::value) { std::printf("FAIL: int 应是整数类型\n"); ++fail; }
    if (!is_integral_type<long long>::value) { std::printf("FAIL: long long 应是整数类型\n"); ++fail; }
    if (is_integral_type<double>::value) { std::printf("FAIL: double 不应是整数类型\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 3,
        'time_limit_ms': 2000,
    },
    {
        'id': 108,
        'chapter_id': 5,
        'type': 'short',
        'title': '短题 4 · 编译期类型列表长度',
        'sort_order': 10,
        'prompt': '实现编译期类型列表 `typelist<Ts...>` 和长度计算 `length<List>`：\n\n'
                  '- `length<typelist<int, double, char>>::value` 应为 3\n'
                  '- `length<typelist<>>::value` 应为 0\n\n'
                  '> 考点：变参模板 + sizeof... 编译期计算。',
        'starter_easy': r'''// 类型列表：包装一组类型
template <typename... Ts>
struct typelist {};

// TODO: length —— 计算 typelist 的类型数量
template <typename List>
struct length;

template <typename... Ts>
struct length<typelist<Ts...>> {
    // TODO: static const int value = sizeof...(Ts);
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''// 实现 typelist<Ts...> 和 length<List>：
//   length<typelist<Ts...>>::value == sizeof...(Ts)

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''// 需求：编译期类型列表 + 长度计算。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>

int main() {
    int fail = 0;
    if (length<typelist<int, double, char>>::value != 3) { std::printf("FAIL: 三类型列表长度应为 3\n"); ++fail; }
    if (length<typelist<>>::value != 0) { std::printf("FAIL: 空列表长度应为 0\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 109,
        'chapter_id': 5,
        'type': 'boss',
        'title': 'Boss · 类型列表操作（Length + Contains）',
        'sort_order': 11,
        'prompt': '实现编译期类型列表操作：\n\n'
                  '- `TypeList<Ts...>`：包装一组类型\n'
                  '- `Length<List>`：类型数量（`sizeof...`）\n'
                  '- `Contains<T, List>`：判断 T 是否在列表中（可用折叠表达式 `(std::is_same_v<T, Ts> || ...)`）\n\n'
                  '> 收口：变参模板 + 类型萃取 + 折叠表达式。',
        'starter_easy': r'''#include <type_traits>

template <typename... Ts>
struct TypeList {};

// TODO: Length
template <typename List>
struct Length;

template <typename... Ts>
struct Length<TypeList<Ts...>> {
    // TODO: sizeof...(Ts)
};

// TODO: Contains —— T 是否在 TypeList 中
template <typename T, typename List>
struct Contains;

template <typename T, typename... Ts>
struct Contains<T, TypeList<Ts...>> {
    // TODO: static const bool value = (std::is_same_v<T, Ts> || ...);
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <type_traits>

// 实现 TypeList / Length / Contains。
// Contains 用折叠表达式 (std::is_same_v<T, Ts> || ...)。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <type_traits>

// 需求：编译期类型列表操作（长度 + 包含判断）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>

int main() {
    int fail = 0;
    if (Length<TypeList<int, double>>::value != 2) { std::printf("FAIL: 长度应为 2\n"); ++fail; }
    if (!Contains<int, TypeList<int, double>>::value) { std::printf("FAIL: 应包含 int\n"); ++fail; }
    if (Contains<char, TypeList<int, double>>::value) { std::printf("FAIL: 不应包含 char\n"); ++fail; }
    if (Contains<int, TypeList<>>::value) { std::printf("FAIL: 空列表不应包含任何类型\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 4,
        'time_limit_ms': 2000,
    },
    # ================= C6 写代码题（id 110-114） =================
    {
        'id': 110,
        'chapter_id': 6,
        'type': 'short',
        'title': '短题 1 · optional 返回',
        'sort_order': 7,
        'prompt': '实现 `std::optional<int> find_first_even(const std::vector<int>& v)`：\n'
                  '返回第一个偶数；没有偶数则返回 `std::nullopt`。\n\n'
                  '> 考点：optional 表示"可能有值"，nullopt 表示无值。',
        'starter_easy': r'''#include <optional>
#include <vector>

// TODO: 返回第一个偶数；无则返回 std::nullopt
std::optional<int> find_first_even(const std::vector<int>& v) {
    // TODO
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <optional>
#include <vector>

// 实现 find_first_even：返回第一个偶数（optional），无则 std::nullopt。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <optional>
#include <vector>

// 需求：find_first_even 返回第一个偶数或 nullopt。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <optional>
#include <vector>

int main() {
    int fail = 0;
    std::vector<int> a{1, 3, 5};
    if (find_first_even(a).has_value()) { std::printf("FAIL: 全奇数应返回无值\n"); ++fail; }
    std::vector<int> b{1, 2, 5};
    auto r = find_first_even(b);
    if (!r.has_value() || r.value() != 2) { std::printf("FAIL: 应返回 2\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 111,
        'chapter_id': 6,
        'type': 'short',
        'title': '短题 2 · string_view 悬垂修复',
        'sort_order': 8,
        'prompt': '下面的函数返回局部 `std::string` 的 `string_view`，对象销毁后视图悬垂。\n'
                  '修复它：返回字符串字面量的 view（静态存储期，不悬垂）。\n\n'
                  '> 考点：string_view 不拥有内存，指向的对象须在其生命周期内。',
        'starter_easy': r'''#include <string_view>

// BUG: 返回局部 string 的 view，悬垂。改为返回字面量。
std::string_view get_view() {
    std::string s = "hello";
    return s;   // BUG: s 销毁后悬垂
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <string_view>

// 修复 get_view()：返回不悬垂的 string_view（字符串字面量有静态存储期）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <string_view>

// 需求：get_view() 返回安全的 string_view（不悬垂）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <string_view>
#include <cstring>

int main() {
    int fail = 0;
    std::string_view v = get_view();
    if (v != "hello") { std::printf("FAIL: get_view 应返回 \"hello\"\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 1,
        'time_limit_ms': 2000,
    },
    {
        'id': 112,
        'chapter_id': 6,
        'type': 'short',
        'title': '短题 3 · variant 类型安全访问',
        'sort_order': 9,
        'prompt': '实现 `std::string describe(const std::variant<int, std::string>& v)`：\n'
                  '用 `std::visit` 访问，int 返回 `"int:42"` 形式，string 返回 `"str:hi"` 形式。\n\n'
                  '> 考点：std::visit + 泛型 lambda + if constexpr 区分类型。',
        'starter_easy': r'''#include <variant>
#include <string>

// TODO: 用 std::visit 实现 describe
std::string describe(const std::variant<int, std::string>& v) {
    return std::visit([](auto&& arg) -> std::string {
        using T = std::decay_t<decltype(arg)>;
        // TODO: if constexpr 区分 int 和 string
        if constexpr (std::is_same_v<T, int>) {
            // TODO: 返回 "int:" + 数字
        } else {
            // TODO: 返回 "str:" + 字符串
        }
    }, v);
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <variant>
#include <string>

// 实现 describe：std::visit + 泛型 lambda，if constexpr 区分 int/string。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <variant>
#include <string>

// 需求：describe(variant<int,string>) 返回类型化描述字符串。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <variant>
#include <string>

int main() {
    int fail = 0;
    std::variant<int, std::string> a = 42;
    if (describe(a) != "int:42") { std::printf("FAIL: describe(42) 应为 int:42\n"); ++fail; }
    std::variant<int, std::string> b = std::string("hi");
    if (describe(b) != "str:hi") { std::printf("FAIL: describe(\"hi\") 应为 str:hi\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 113,
        'chapter_id': 6,
        'type': 'short',
        'title': '短题 4 · optional 重构错误处理',
        'sort_order': 10,
        'prompt': '用 `optional` 替代"错误码"：实现 `std::optional<int> find_divisible(const std::vector<int>& v, int d)`，\n'
                  '返回第一个能被 d 整除的数；没有则返回 `std::nullopt`。\n\n'
                  '> 考点：optional 表达"可能失败"，替代魔法值 / 错误码。',
        'starter_easy': r'''#include <optional>
#include <vector>

// TODO: 返回第一个能被 d 整除的数；无则 std::nullopt
std::optional<int> find_divisible(const std::vector<int>& v, int d) {
    // TODO
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <optional>
#include <vector>

// 实现 find_divisible(v, d)：第一个能被 d 整除的数或 nullopt。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <optional>
#include <vector>

// 需求：find_divisible 返回第一个整除的数或 nullopt。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <optional>
#include <vector>

int main() {
    int fail = 0;
    std::vector<int> a{1, 2, 3, 4};
    auto r = find_divisible(a, 2);
    if (!r.has_value() || r.value() != 2) { std::printf("FAIL: 应返回 2\n"); ++fail; }
    std::vector<int> b{1, 3, 5};
    if (find_divisible(b, 2).has_value()) { std::printf("FAIL: 无可整除应返回无值\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 114,
        'chapter_id': 6,
        'type': 'boss',
        'title': 'Boss · 类型安全配置解析器',
        'sort_order': 11,
        'prompt': '实现一个简单的类型安全配置类 `Config`：\n\n'
                  '- `void set(const std::string& key, const std::string& val)`：存配置\n'
                  '- `std::optional<std::string> get_str(const std::string& key)`：存在则返回值，否则 nullopt\n'
                  '- `std::optional<int> get_int(const std::string& key)`：值能转 int 则返回，否则 nullopt\n\n'
                  '> 收口：optional（无值语义）+ 类型转换失败处理。',
        'starter_easy': r'''#include <optional>
#include <string>
#include <map>

class Config {
    std::map<std::string, std::string> kv_;
public:
    void set(const std::string& key, const std::string& val) {
        // TODO
    }
    std::optional<std::string> get_str(const std::string& key) {
        // TODO: 存在则返回值，否则 nullopt
    }
    std::optional<int> get_int(const std::string& key) {
        // TODO: 存在且能转 int 则返回，否则 nullopt（用 std::stoi + try/catch）
    }
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <optional>
#include <string>
#include <map>

// 实现 Config：set/get_str/get_int。
// get_int 用 std::stoi 转，转换失败（异常）返回 nullopt。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <optional>
#include <string>
#include <map>

// 需求：类型安全配置类（set + get_str + get_int，类型转换失败返回 nullopt）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <optional>
#include <string>

int main() {
    int fail = 0;
    Config c;
    c.set("port", "8080");
    c.set("host", "localhost");
    auto p = c.get_int("port");
    if (!p.has_value() || p.value() != 8080) { std::printf("FAIL: port 应返回 8080\n"); ++fail; }
    auto h = c.get_str("host");
    if (!h.has_value() || h.value() != "localhost") { std::printf("FAIL: host 应返回 localhost\n"); ++fail; }
    if (c.get_int("host").has_value()) { std::printf("FAIL: host 转 int 应失败\n"); ++fail; }
    if (c.get_str("missing").has_value()) { std::printf("FAIL: 不存在的 key 应返回无值\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 4,
        'time_limit_ms': 2000,
    },
    # ================= C7 写代码题（id 115-119） =================
    {
        'id': 115,
        'chapter_id': 7,
        'type': 'short',
        'title': '短题 1 · 容器选型：set 去重排序',
        'sort_order': 22,
        'prompt': '实现 `std::vector<int> unique_sorted(const std::vector<int>& v)`：\n'
                  '用 `std::set` 去重并按升序排序。\n\n'
                  '> 考点：容器选型——set 自带去重 + 有序。',
        'starter_easy': r'''#include <vector>
#include <set>

// TODO: 用 set 去重 + 排序
std::vector<int> unique_sorted(const std::vector<int>& v) {
    // TODO
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <vector>
#include <set>

// 实现 unique_sorted：用 std::set 去重排序，再转回 vector。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <vector>
#include <set>

// 需求：unique_sorted 去重并升序。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <vector>

int main() {
    int fail = 0;
    std::vector<int> v{3, 1, 2, 1, 3};
    std::vector<int> r = unique_sorted(v);
    if (r.size() != 3 || r[0] != 1 || r[1] != 2 || r[2] != 3) {
        std::printf("FAIL: 应返回 {1,2,3}\n"); ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 1,
        'time_limit_ms': 2000,
    },
    {
        'id': 116,
        'chapter_id': 7,
        'type': 'short',
        'title': '短题 2 · 迭代器失效修复',
        'sort_order': 23,
        'prompt': '`remove_even` 要删除 `v` 中所有偶数。下面的实现能编译、多数情况下也"看起来对"，'
                  '但它有 bug。找出问题并修复（提示：注意循环体里容器本身发生了变化）。\n\n'
                  '> 考点：遍历过程中修改容器 ⇒ 迭代器失效。',
        'starter_easy': r'''#include <vector>
#include <algorithm>

// TODO: 这段代码能编译、看起来也能跑，但有隐蔽的 bug —— 自己找出来并修好。
void remove_even(std::vector<int>& v) {
    for (auto it = v.begin(); it != v.end(); ++it) {
        if (*it % 2 == 0) v.erase(it);
    }
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <vector>
#include <algorithm>

// 修复 remove_even：删除所有偶数。
// 想清楚：为什么在循环里直接 erase 是不安全的？

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <vector>
#include <algorithm>

// 需求：remove_even 删除所有偶数。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <vector>

int main() {
    int fail = 0;
    std::vector<int> v{1, 2, 3, 4, 5, 6};
    remove_even(v);
    if (v.size() != 3 || v[0] != 1 || v[1] != 3 || v[2] != 5) {
        std::printf("FAIL: 应删除所有偶数，剩 {1,3,5}\n"); ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 1,
        'time_limit_ms': 2000,
    },
    {
        'id': 117,
        'chapter_id': 7,
        'type': 'short',
        'title': '短题 3 · 自定义比较器：降序 set',
        'sort_order': 24,
        'prompt': '实现 `std::set<int, std::greater<int>> make_desc_set(const std::vector<int>& v)`：\n'
                  '返回一个降序排列的 set。\n\n'
                  '> 考点：自定义比较器（std::greater）改变容器排序。',
        'starter_easy': r'''#include <vector>
#include <set>
#include <functional>

// TODO: 返回降序 set
std::set<int, std::greater<int>> make_desc_set(const std::vector<int>& v) {
    // TODO
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <vector>
#include <set>
#include <functional>

// 实现 make_desc_set：用 std::greater<int> 作比较器，降序 set。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <vector>
#include <set>
#include <functional>

// 需求：make_desc_set 返回降序 set。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <vector>
#include <set>

int main() {
    int fail = 0;
    std::vector<int> v{1, 3, 2};
    auto s = make_desc_set(v);
    if (s.size() != 3) { std::printf("FAIL: 应有 3 个元素\n"); ++fail; }
    auto it = s.begin();
    if (*it != 3) { std::printf("FAIL: 降序首个应为 3\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 118,
        'chapter_id': 7,
        'type': 'short',
        'title': '短题 4 · 算法组合：过滤 + 变换',
        'sort_order': 25,
        'prompt': '实现 `std::vector<int> filter_and_double(const std::vector<int>& v)`：\n'
                  '先过滤出正数，再把每个正数翻倍。可用 `std::copy_if` + `std::transform`，或手写。\n\n'
                  '> 考点：算法组合完成数据流水线。',
        'starter_easy': r'''#include <vector>
#include <algorithm>

// TODO: 过滤正数 + 翻倍
std::vector<int> filter_and_double(const std::vector<int>& v) {
    // TODO
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <vector>
#include <algorithm>

// 实现 filter_and_double：过滤正数，再翻倍。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <vector>
#include <algorithm>

// 需求：filter_and_double 过滤正数并翻倍。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <vector>

int main() {
    int fail = 0;
    std::vector<int> v{-1, 2, 3, -4};
    std::vector<int> r = filter_and_double(v);
    if (r.size() != 2 || r[0] != 4 || r[1] != 6) {
        std::printf("FAIL: 应返回 {4,6}\n"); ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 1,
        'time_limit_ms': 2000,
    },
    {
        'id': 119,
        'chapter_id': 7,
        'type': 'boss',
        'title': 'Boss · LRU 缓存',
        'sort_order': 26,
        'prompt': '实现一个 LRU（最近最少使用）缓存 `LRUCache`：\n\n'
                  '- `LRUCache(int capacity)`：构造，容量 capacity\n'
                  '- `int get(int key)`：存在则返回值并标记为最近使用，否则返回 -1\n'
                  '- `void put(int key, int value)`：插入/更新；容量满时淘汰最久未使用的\n\n'
                  '> 收口：list（有序）+ unordered_map（O(1) 查找），跨容器组合。',
        'starter_easy': r'''#include <list>
#include <unordered_map>

class LRUCache {
    int capacity_;
    std::list<std::pair<int, int>> items_;
    std::unordered_map<int, std::list<std::pair<int, int>>::iterator> map_;
public:
    LRUCache(int capacity) : capacity_(capacity) {}
    int get(int key) {
        // TODO: 找到则移到最前并返回值；否则 -1
    }
    void put(int key, int value) {
        // TODO: 存在则更新并移到最前；不存在则插入，满则淘汰末尾
    }
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <list>
#include <unordered_map>

// 实现 LRUCache：list 维护顺序（front=最近，back=最久），unordered_map 存迭代器。
// get：命中则 splice 到 front；put：更新或插入，满则 pop_back 淘汰。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <list>
#include <unordered_map>

// 需求：LRU 缓存（get/put，容量淘汰最久未用）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>

int main() {
    int fail = 0;
    LRUCache c(2);
    c.put(1, 1);
    c.put(2, 2);
    if (c.get(1) != 1) { std::printf("FAIL: get(1) 应为 1\n"); ++fail; }
    c.put(3, 3);  // 淘汰 key=2
    if (c.get(2) != -1) { std::printf("FAIL: get(2) 应返回 -1（已淘汰）\n"); ++fail; }
    if (c.get(3) != 3) { std::printf("FAIL: get(3) 应为 3\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 3,
        'time_limit_ms': 2000,
    },
    # ================= C9 写代码题（id 120-124） =================
    {
        'id': 120,
        'chapter_id': 9,
        'type': 'short',
        'title': '短题 1 · mutex 保护计数器',
        'sort_order': 7,
        'prompt': '实现线程安全计数器 `Counter`：\n\n'
                  '- `void increment()`：自增，线程安全\n'
                  '- `int get() const`：读取，线程安全\n\n'
                  '> 考点：std::mutex + lock_guard 保护临界区。',
        'starter_easy': r'''#include <mutex>

class Counter {
    int value_ = 0;
    mutable std::mutex m_;
public:
    void increment() {
        // TODO: 加锁后 ++value_
    }
    int get() const {
        // TODO: 加锁后返回 value_
    }
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <mutex>

// 实现 Counter：increment/get 用 lock_guard 保护。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <mutex>

// 需求：线程安全计数器（increment/get 加锁）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <thread>
#include <vector>

int main() {
    int fail = 0;
    Counter c;
    std::vector<std::thread> ts;
    for (int t = 0; t < 4; ++t) {
        ts.emplace_back([&c](){ for (int i = 0; i < 1000; ++i) c.increment(); });
    }
    for (auto& t : ts) t.join();
    if (c.get() != 4000) { std::printf("FAIL: 4 线程各 1000 次应为 4000\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 1,
        'time_limit_ms': 3000,
    },
    {
        'id': 121,
        'chapter_id': 9,
        'type': 'short',
        'title': '短题 2 · 数据竞争修复',
        'sort_order': 8,
        'prompt': '下面的全局计数器 `counter++` 未加锁，多线程自增是数据竞争（未定义行为）。\n'
                  '修复：用 `std::atomic<int>` 替代裸 int。\n\n'
                  '> 考点：数据竞争；atomic 无锁自增。',
        'starter_easy': r'''#include <atomic>

// BUG: 裸 int 数据竞争。改为 std::atomic<int>。
int counter = 0;

void increment() {
    ++counter;   // BUG: 数据竞争
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <atomic>

// 修复：用 std::atomic<int> counter，increment 用 ++counter（原子）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <atomic>

// 需求：线程安全自增（用 atomic 修复数据竞争）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <thread>
#include <vector>

int main() {
    int fail = 0;
    std::vector<std::thread> ts;
    for (int t = 0; t < 4; ++t) {
        ts.emplace_back([](){ for (int i = 0; i < 1000; ++i) increment(); });
    }
    for (auto& t : ts) t.join();
    if (counter != 4000) { std::printf("FAIL: 应为 4000（原子自增）\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 1,
        'time_limit_ms': 3000,
    },
    {
        'id': 122,
        'chapter_id': 9,
        'type': 'short',
        'title': '短题 3 · condition_variable 生产者消费者',
        'sort_order': 9,
        'prompt': '实现一个带条件变量的简单队列 `BlockingQueue`（容量 1）：\n\n'
                  '- `void push(int v)`：有空间则放入并通知，否则等待\n'
                  '- `int pop()`：有值则取出并通知，否则等待\n\n'
                  '> 考点：condition_variable + 谓词等待（防虚假唤醒）。',
        'starter_easy': r'''#include <mutex>
#include <condition_variable>

class BlockingQueue {
    int value_ = 0;
    bool has_ = false;
    std::mutex m_;
    std::condition_variable cv_;
public:
    void push(int v) {
        std::unique_lock<std::mutex> lock(m_);
        // TODO: 等待 !has_（有空间），放入并置 has_，通知
        cv_.notify_one();
    }
    int pop() {
        std::unique_lock<std::mutex> lock(m_);
        // TODO: 等待 has_（有值），取出并置 !has_，通知
        cv_.notify_one();
        return value_;
    }
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <mutex>
#include <condition_variable>

// 实现 BlockingQueue（容量1）：push/pop 用 cv.wait(lock, 谓词) 防虚假唤醒。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <mutex>
#include <condition_variable>

// 需求：容量1的阻塞队列（push/pop 条件变量同步）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <thread>

int main() {
    int fail = 0;
    BlockingQueue q;
    int result = 0;
    std::thread producer([&q](){ q.push(42); });
    std::thread consumer([&q, &result](){ result = q.pop(); });
    producer.join();
    consumer.join();
    if (result != 42) { std::printf("FAIL: 生产者消费者应传递 42\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 1,
        'time_limit_ms': 3000,
    },
    {
        'id': 123,
        'chapter_id': 9,
        'type': 'short',
        'title': '短题 4 · 线程安全队列',
        'sort_order': 10,
        'prompt': '实现线程安全队列 `SafeQueue`：\n\n'
                  '- `void push(int v)`：入队\n'
                  '- `bool try_pop(int& out)`：有值则取出并返回 true，空则返回 false\n'
                  '- `size_t size() const`：当前元素数\n\n'
                  '> 考点：mutex 保护队列，非阻塞取出。',
        'starter_easy': r'''#include <mutex>
#include <deque>

class SafeQueue {
    std::deque<int> q_;
    mutable std::mutex m_;
public:
    void push(int v) {
        // TODO: 加锁 push_back
    }
    bool try_pop(int& out) {
        // TODO: 加锁，非空则取出到 out 并返回 true，空返回 false
    }
    size_t size() const {
        // TODO: 加锁返回 q_.size()
    }
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <mutex>
#include <deque>

// 实现 SafeQueue：push/try_pop/size 均加锁保护。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <mutex>
#include <deque>

// 需求：线程安全队列（push/try_pop/size）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>

int main() {
    int fail = 0;
    SafeQueue q;
    q.push(1);
    q.push(2);
    if (q.size() != 2) { std::printf("FAIL: size 应为 2\n"); ++fail; }
    int x;
    if (!q.try_pop(x) || x != 1) { std::printf("FAIL: 第一次取出应为 1\n"); ++fail; }
    if (!q.try_pop(x) || x != 2) { std::printf("FAIL: 第二次取出应为 2\n"); ++fail; }
    if (q.try_pop(x)) { std::printf("FAIL: 空队列应返回 false\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 4,
        'time_limit_ms': 2000,
    },
    {
        'id': 124,
        'chapter_id': 9,
        'type': 'boss',
        'title': 'Boss · 线程安全日志缓冲',
        'sort_order': 11,
        'prompt': '实现线程安全日志缓冲 `LogBuffer`：\n\n'
                  '- `void append(const std::string& line)`：追加日志行，线程安全\n'
                  '- `std::vector<std::string> drain()`：取出并清空所有日志，线程安全\n'
                  '- `size_t size() const`：当前缓冲行数\n\n'
                  '> 收口：mutex + 容器，跨 C9（并发）+ C7（容器）。',
        'starter_easy': r'''#include <mutex>
#include <vector>
#include <string>

class LogBuffer {
    std::vector<std::string> lines_;
    mutable std::mutex m_;
public:
    void append(const std::string& line) {
        // TODO: 加锁 push_back
    }
    std::vector<std::string> drain() {
        // TODO: 加锁，取出所有并清空
    }
    size_t size() const {
        // TODO: 加锁返回 lines_.size()
    }
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <mutex>
#include <vector>
#include <string>

// 实现 LogBuffer：append/drain/size 加锁；drain 用 std::move 交出数据。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <mutex>
#include <vector>
#include <string>

// 需求：线程安全日志缓冲（append/drain/size）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <string>
#include <vector>
#include <thread>

int main() {
    int fail = 0;
    LogBuffer lb;
    std::vector<std::thread> ts;
    for (int t = 0; t < 4; ++t) {
        ts.emplace_back([&lb, t](){ for (int i = 0; i < 100; ++i) lb.append("t" + std::to_string(t)); });
    }
    for (auto& t : ts) t.join();
    if (lb.size() != 400) { std::printf("FAIL: 4 线程各 100 条应为 400\n"); ++fail; }
    auto all = lb.drain();
    if (all.size() != 400 || lb.size() != 0) { std::printf("FAIL: drain 应取走全部并清空\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 3000,
    },
    # ================= C12 写代码题（id 125-129） =================
    {
        'id': 125,
        'chapter_id': 12,
        'type': 'short',
        'title': '短题 1 · constexpr 阶乘',
        'sort_order': 7,
        'prompt': '实现编译期可求值的阶乘函数 `constexpr int factorial(int n)`。\n\n'
                  '> 考点：constexpr 函数（递归），编译期 / 运行期都能调用。',
        'starter_easy': r'''// TODO: 实现 constexpr 阶乘（递归，n<=1 返回 1）
constexpr int factorial(int n) {
    // TODO
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''// 实现 constexpr int factorial(int n)：n<=1 返回 1，否则 n * factorial(n-1)。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''// 需求：constexpr 阶乘。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>

static_assert(factorial(5) == 120, "factorial(5) 应为 120");

int main() {
    int fail = 0;
    if (factorial(5) != 120) { std::printf("FAIL: factorial(5) 应为 120\n"); ++fail; }
    if (factorial(0) != 1) { std::printf("FAIL: factorial(0) 应为 1\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 126,
        'chapter_id': 12,
        'type': 'short',
        'title': '短题 2 · constexpr 斐波那契',
        'sort_order': 8,
        'prompt': '实现 `constexpr int fib(int n)` 计算第 n 个斐波那契数（fib(0)=0, fib(1)=1）。\n\n'
                  '> 考点：constexpr 递归的编译期求值。',
        'starter_easy': r'''// TODO: constexpr 斐波那契
constexpr int fib(int n) {
    // TODO: n<=1 返回 n，否则 fib(n-1)+fib(n-2)
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''// 实现 constexpr int fib(int n)：n<=1 返回 n，否则 fib(n-1)+fib(n-2)。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''// 需求：constexpr 斐波那契。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>

static_assert(fib(10) == 55, "fib(10) 应为 55");

int main() {
    int fail = 0;
    if (fib(10) != 55) { std::printf("FAIL: fib(10) 应为 55\n"); ++fail; }
    if (fib(0) != 0) { std::printf("FAIL: fib(0) 应为 0\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 127,
        'chapter_id': 12,
        'type': 'short',
        'title': '短题 3 · constexpr 平方 + 编译期数组',
        'sort_order': 9,
        'prompt': '实现 `constexpr int square(int x)`，并验证其能用于编译期数组大小：\n'
                  '`int arr[square(3)]` 大小应为 9。\n\n'
                  '> 考点：constexpr 函数的结果可用于编译期上下文（数组大小）。',
        'starter_easy': r'''// TODO: constexpr 平方
constexpr int square(int x) {
    // TODO
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''// 实现 constexpr int square(int x) { return x * x; }

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''// 需求：constexpr 平方。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>

int arr[square(3)];   // 编译期求值，数组大小 9

int main() {
    int fail = 0;
    if (square(3) != 9) { std::printf("FAIL: square(3) 应为 9\n"); ++fail; }
    if (sizeof(arr) / sizeof(int) != 9) { std::printf("FAIL: 数组大小应为 9\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 128,
        'chapter_id': 12,
        'type': 'short',
        'title': '短题 4 · 编译期平方查找表',
        'sort_order': 10,
        'prompt': '实现 `constexpr std::array<int, 10> make_square_table()`：\n'
                  '返回平方表（第 i 项 = i*i）。\n\n'
                  '> 考点：constexpr 函数生成 std::array（C++14 constexpr 循环）。',
        'starter_easy': r'''#include <array>

// TODO: 生成平方表
constexpr std::array<int, 10> make_square_table() {
    std::array<int, 10> a{};
    // TODO: for 循环填 a[i] = i * i
    return a;
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <array>

// 实现 constexpr make_square_table：std::array<int,10>，a[i]=i*i。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <array>

// 需求：编译期平方查找表。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>

static_assert(make_square_table()[5] == 25, "第5项应为25");

int main() {
    int fail = 0;
    auto t = make_square_table();
    if (t[5] != 25) { std::printf("FAIL: 第5项应为 25\n"); ++fail; }
    if (t[9] != 81) { std::printf("FAIL: 第9项应为 81\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 129,
        'chapter_id': 12,
        'type': 'boss',
        'title': 'Boss · 编译期阶乘查找表',
        'sort_order': 11,
        'prompt': '实现编译期生成的阶乘查找表：\n\n'
                  '- `constexpr int factorial(int n)`：阶乘\n'
                  '- `constexpr std::array<int, 10> make_factorial_table()`：第 i 项 = i 的阶乘\n\n'
                  '> 收口：constexpr 函数 + constexpr 数组生成 + static_assert 编译期验证。',
        'starter_easy': r'''#include <array>

// TODO: constexpr 阶乘
constexpr int factorial(int n) {
    // TODO
}

// TODO: 生成阶乘表
constexpr std::array<int, 10> make_factorial_table() {
    std::array<int, 10> a{};
    // TODO: 填 a[i] = factorial(i)
    return a;
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <array>

// 实现 factorial + make_factorial_table（a[i]=factorial(i)）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <array>

// 需求：编译期阶乘查找表。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>

static_assert(make_factorial_table()[5] == 120, "第5项应为120");

int main() {
    int fail = 0;
    auto t = make_factorial_table();
    if (t[5] != 120) { std::printf("FAIL: 第5项应为 120\n"); ++fail; }
    if (t[0] != 1) { std::printf("FAIL: 第0项应为 1\n"); ++fail; }
    if (t[9] != 362880) { std::printf("FAIL: 第9项应为 362880\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 3,
        'time_limit_ms': 2000,
    },
    # ================= C8 写代码题（id 130-134，文件操作与流） =================
    {
        'id': 130,
        'chapter_id': 8,
        'type': 'short',
        'title': '短题 1 · 文本文件写入与读取',
        'sort_order': 7,
        'prompt': '实现两个函数：\n\n'
                  '- `void write_numbers(const std::string& path, const std::vector<int>& nums)`：把每个数字写成一行\n'
                  '- `std::vector<int> read_numbers(const std::string& path)`：从文件读回所有数字\n\n'
                  '> 考点：ofstream/ifstream 基础读写。',
        'starter_easy': r'''#include <fstream>
#include <vector>
#include <string>

// TODO: 每个数字写成一行
void write_numbers(const std::string& path, const std::vector<int>& nums) {
    std::ofstream out(path);
    // TODO: 循环写入，每个数字一行
}

// TODO: 读回所有数字
std::vector<int> read_numbers(const std::string& path) {
    std::vector<int> result;
    std::ifstream in(path);
    // TODO: 循环读取直到 EOF
    return result;
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <fstream>
#include <vector>
#include <string>

// 实现 write_numbers（ofstream 逐行写）与 read_numbers（ifstream 逐行读）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <fstream>
#include <vector>
#include <string>

// 需求：文本文件的整数逐行写入与读取。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <cstdlib>

int main() {
    int fail = 0;
    write_numbers("nums.txt", {1, 2, 3, 42});
    auto got = read_numbers("nums.txt");
    if (got.size() != 4) {
        std::printf("FAIL: 应读出 4 个数字\n"); ++fail;
    } else if (got[0] != 1 || got[1] != 2 || got[2] != 3 || got[3] != 42) {
        std::printf("FAIL: 读出的数字不符\n"); ++fail;
    }
    std::remove("nums.txt");
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 131,
        'chapter_id': 8,
        'type': 'short',
        'title': '短题 2 · 二进制读写',
        'sort_order': 8,
        'prompt': '实现二进制读写：\n\n'
                  '- `void save_binary(const std::string& path, const std::vector<int>& data)`：以二进制模式写入（每个 int 的原始字节）\n'
                  '- `std::vector<int> load_binary(const std::string& path)`：以二进制模式读回\n\n'
                  '> 考点：`std::ios::binary` + `write`/`read` 原始字节。',
        'starter_easy': r'''#include <fstream>
#include <vector>
#include <string>

void save_binary(const std::string& path, const std::vector<int>& data) {
    std::ofstream out(path, std::ios::binary);
    // TODO: out.write(reinterpret_cast<const char*>(data.data()), data.size() * sizeof(int))
}

std::vector<int> load_binary(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    std::vector<int> result;
    // TODO: seekg 到末尾求字节数，再 resize 后 read 回 result
    return result;
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <fstream>
#include <vector>
#include <string>

// 实现 save_binary（binary + write）与 load_binary（先求长度再 read）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <fstream>
#include <vector>
#include <string>

// 需求：int 数组的二进制序列化/反序列化。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <cstdlib>

int main() {
    int fail = 0;
    save_binary("bin.dat", {10, 20, 30});
    auto got = load_binary("bin.dat");
    if (got.size() != 3) {
        std::printf("FAIL: 应读出 3 个 int\n"); ++fail;
    } else if (got[0] != 10 || got[1] != 20 || got[2] != 30) {
        std::printf("FAIL: 二进制读回的值不符\n"); ++fail;
    }
    std::remove("bin.dat");
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 132,
        'chapter_id': 8,
        'type': 'short',
        'title': '短题 3 · 分块读取',
        'sort_order': 9,
        'prompt': '实现 `std::string read_all_chunks(const std::string& path, size_t chunk_size)`：\n'
                  '按 `chunk_size` 字节分块读，拼接全部内容（最后一块可能不足 `chunk_size`）。\n\n'
                  '> 考点：分块读取处理 EOF 与不足块。',
        'starter_easy': r'''#include <fstream>
#include <vector>
#include <string>

std::string read_all_chunks(const std::string& path, size_t chunk_size) {
    std::ifstream in(path, std::ios::binary);
    std::string result;
    // TODO: 用缓冲区循环 read chunk_size 字节，按 gcount() 取实际读数
    return result;
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <fstream>
#include <vector>
#include <string>

// 实现 read_all_chunks：循环 read 固定块，gcount 取实际字节，直到 EOF。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <fstream>
#include <vector>
#include <string>

// 需求：按固定大小分块读完整文件。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>

int main() {
    int fail = 0;
    {
        std::ofstream out("chunk.txt");
        out << "0123456789";
    }
    auto got = read_all_chunks("chunk.txt", 3);
    if (got != "0123456789") {
        std::printf("FAIL: 分块读回的内容应完整一致\n"); ++fail;
    }
    auto empty = read_all_chunks("chunk.txt", 100);
    if (empty != "0123456789") {
        std::printf("FAIL: 块大于文件时也应读完整\n"); ++fail;
    }
    std::remove("chunk.txt");
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 133,
        'chapter_id': 8,
        'type': 'short',
        'title': '短题 4 · CSV 序列化',
        'sort_order': 10,
        'prompt': '实现简单 CSV：\n\n'
                  '- `std::string to_csv(const std::vector<std::vector<int>>& rows)`：每行用逗号连接，行间换行\n'
                  '- `std::vector<std::vector<int>> from_csv(const std::string& text)`：解析回二维数组\n\n'
                  '> 考点：字符串/流处理，分隔符序列化与反序列化。',
        'starter_easy': r'''#include <string>
#include <vector>
#include <sstream>

std::string to_csv(const std::vector<std::vector<int>>& rows) {
    std::ostringstream out;
    // TODO: 逐行拼接，逗号分隔，行间换行
    return out.str();
}

std::vector<std::vector<int>> from_csv(const std::string& text) {
    std::vector<std::vector<int>> result;
    // TODO: 按行拆，再按逗号拆，转 int
    return result;
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <string>
#include <vector>
#include <sstream>

// 实现 to_csv / from_csv 往返：逗号分隔、换行分行。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <string>
#include <vector>
#include <sstream>

// 需求：二维 int 数组的 CSV 序列化与解析。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <vector>

int main() {
    int fail = 0;
    auto csv = to_csv({{1, 2, 3}, {4, 5}, {6}});
    if (csv != "1,2,3\n4,5\n6\n") {
        std::printf("FAIL: CSV 输出不符\n"); ++fail;
    }
    auto back = from_csv("1,2,3\n4,5\n6\n");
    if (back.size() != 3) {
        std::printf("FAIL: 应解析出 3 行\n"); ++fail;
    } else if (back[0].size() != 3 || back[0][2] != 3 || back[1][1] != 5 || back[2][0] != 6) {
        std::printf("FAIL: 解析出的值不符\n"); ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 3,
        'time_limit_ms': 2000,
    },
    {
        'id': 134,
        'chapter_id': 8,
        'type': 'boss',
        'title': 'Boss · 日志滚动',
        'sort_order': 11,
        'prompt': '实现日志滚动 `LogRoller`：\n\n'
                  '- 构造 `LogRoller(const std::string& base, size_t max_lines)`\n'
                  '- `void append(const std::string& line)`：追加一行；当行数达到 `max_lines` 时，把当前文件重命名为 `base + ".1"`，清空重新开始\n'
                  '- `size_t count() const`：当前文件行数\n\n'
                  '> 收口：文件追加 + 重命名滚动 + 状态管理，收口 C8。',
        'starter_easy': r'''#include <fstream>
#include <string>
#include <cstdio>

class LogRoller {
    std::string base_;
    size_t max_lines_;
    size_t count_ = 0;
public:
    LogRoller(const std::string& base, size_t max_lines)
        : base_(base), max_lines_(max_lines) {}

    void append(const std::string& line) {
        // TODO: 达到 max_lines_ 时 rename 当前文件为 base+".1"，重置 count_
        std::ofstream out(base_, std::ios::app);
        out << line << "\n";
        ++count_;
    }

    size_t count() const { return count_; }
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <fstream>
#include <string>
#include <cstdio>

// 实现 LogRoller：append 达到 max_lines 时 std::rename 到 .1 并重置计数。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <fstream>
#include <string>
#include <cstdio>

// 需求：日志滚动（满行数重命名旧文件，重新开始）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>

static int count_lines(const std::string& path) {
    std::ifstream in(path);
    std::string line;
    int n = 0;
    while (std::getline(in, line)) ++n;
    return n;
}

int main() {
    int fail = 0;
    std::remove("app.log");
    std::remove("app.log.1");
    LogRoller r("app.log", 3);
    for (int i = 1; i <= 5; ++i) r.append("line" + std::to_string(i));
    if (r.count() != 2) {
        std::printf("FAIL: 滚动后当前文件应剩 2 行\n"); ++fail;
    }
    if (count_lines("app.log") != 2) {
        std::printf("FAIL: app.log 应含 2 行\n"); ++fail;
    }
    if (count_lines("app.log.1") != 3) {
        std::printf("FAIL: app.log.1 应含滚走的 3 行\n"); ++fail;
    }
    std::remove("app.log");
    std::remove("app.log.1");
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 3,
        'time_limit_ms': 2000,
    },
    # ================= C10 写代码题（id 135-139，网络编程） =================
    {
        'id': 135,
        'chapter_id': 10,
        'type': 'short',
        'title': '短题 1 · 长度前缀帧编解码',
        'sort_order': 7,
        'prompt': '实现长度前缀帧协议（TCP 粘包处理核心）：\n\n'
                  '- `std::string encode_frame(const std::string& payload)`：返回 4 字节大端长度 + payload\n'
                  '- `std::vector<std::string> parse_frames(const std::string& buffer)`：从字节流解析出所有完整帧（不足一帧的部分忽略）\n\n'
                  '> 考点：TCP 粘包/拆包，长度前缀协议。',
        'starter_easy': r'''#include <string>
#include <vector>

// 4 字节大端长度 + payload
std::string encode_frame(const std::string& payload) {
    std::string frame;
    // TODO: 写 4 字节大端长度（用 static_cast<char> 截断），再写 payload
    return frame;
}

std::vector<std::string> parse_frames(const std::string& buffer) {
    std::vector<std::string> frames;
    // TODO: 循环：先读 4 字节长度，再取对应 payload；不足则停止
    return frames;
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <string>
#include <vector>

// 实现 encode_frame（4 字节大端长度前缀）与 parse_frames（按长度切完整帧）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <string>
#include <vector>

// 需求：长度前缀帧的编码与解码（处理粘包/半包）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <string>
#include <vector>

int main() {
    int fail = 0;
    auto f = encode_frame("hello");
    if (f.size() != 9) {
        std::printf("FAIL: 帧长应为 9（4 头 + 5 体）\n"); ++fail;
    } else {
        unsigned len = (unsigned char)f[0] << 24 | (unsigned char)f[1] << 16
                     | (unsigned char)f[2] << 8 | (unsigned char)f[3];
        if (len != 5) { std::printf("FAIL: 长度头应为 5\n"); ++fail; }
    }
    auto frames = parse_frames(encode_frame("ab") + encode_frame("cde"));
    if (frames.size() != 2) {
        std::printf("FAIL: 应解析出 2 帧\n"); ++fail;
    } else if (frames[0] != "ab" || frames[1] != "cde") {
        std::printf("FAIL: 帧内容不符\n"); ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 4,
        'time_limit_ms': 2000,
    },
    {
        'id': 136,
        'chapter_id': 10,
        'type': 'short',
        'title': '短题 2 · 文本协议解析',
        'sort_order': 8,
        'prompt': '实现 `std::pair<std::string, std::string> parse_line(const std::string& line)`：\n'
                  '解析 `"key: value"`，返回 `{key, value}`（key 与 value 均去掉首尾空白）。\n\n'
                  '> 考点：文本协议（HTTP 头风格）解析。',
        'starter_easy': r'''#include <string>
#include <utility>

// 解析 "key: value"，返回 {key, value}（去掉首尾空白）
std::pair<std::string, std::string> parse_line(const std::string& line) {
    // TODO: 找第一个 ':' 切分；实现一个 trim 去首尾空白
    return {};
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <string>
#include <utility>

// 实现 parse_line：按第一个 ':' 切分，key/value 各 trim 首尾空白。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <string>
#include <utility>

// 需求：解析 "key: value" 文本协议行。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <string>

int main() {
    int fail = 0;
    auto a = parse_line("name:  张三 ");
    if (a.first != "name" || a.second != "张三") {
        std::printf("FAIL: 应解析出 name/张三\n"); ++fail;
    }
    auto b = parse_line("  port : 8080");
    if (b.first != "port" || b.second != "8080") {
        std::printf("FAIL: 应解析出 port/8080\n"); ++fail;
    }
    auto c = parse_line("empty:");
    if (c.first != "empty" || !c.second.empty()) {
        std::printf("FAIL: 空值应解析为空串\n"); ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 3,
        'time_limit_ms': 2000,
    },
    {
        'id': 137,
        'chapter_id': 10,
        'type': 'short',
        'title': '短题 3 · fd 回显',
        'sort_order': 9,
        'prompt': '实现 `bool echo_once(int fd)`：从 fd 读入直到一个换行，把相同内容写回；读到 EOF 返回 false。\n\n'
                  '> 考点：socket read/write 循环，处理短读。',
        'starter_easy': r'''#include <unistd.h>
#include <string>

// 从 fd 读一行（到 '\n'），原样写回；读到 EOF 返回 false
bool echo_once(int fd) {
    // TODO: 循环 read 1 字节直到 '\n' 或 EOF，边读边 write 回
    return true;
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <unistd.h>
#include <string>

// 实现 echo_once：循环 read 到 '\n'（EOF 返回 false），把读到的字节写回。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <unistd.h>
#include <string>

// 需求：从 fd 读一行并原样回写。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <cstring>
#include <sys/socket.h>
#include <unistd.h>

int main() {
    int fail = 0;
    int sv[2];
    socketpair(AF_UNIX, SOCK_STREAM, 0, sv);
    const char* msg = "hello\n";
    write(sv[0], msg, std::strlen(msg));
    bool ok = echo_once(sv[1]);
    char buf[64] = {0};
    read(sv[0], buf, sizeof(buf));
    if (!ok) {
        std::printf("FAIL: echo_once 应返回 true\n"); ++fail;
    }
    if (std::strcmp(buf, "hello\n") != 0) {
        std::printf("FAIL: 回显内容不符\n"); ++fail;
    }
    close(sv[0]); close(sv[1]);
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 138,
        'chapter_id': 10,
        'type': 'short',
        'title': '短题 4 · 响应封装与状态解析',
        'sort_order': 10,
        'prompt': '实现简单响应协议：\n\n'
                  '- `std::string make_response(int status, const std::string& body)`：构造 `"STATUS <status>\\n\\n<body>"`\n'
                  '- `int parse_status(const std::string& response)`：解析首行 `STATUS <n>` 里的状态码\n\n'
                  '> 考点：协议封装与解析。',
        'starter_easy': r'''#include <string>

std::string make_response(int status, const std::string& body) {
    // TODO: "STATUS <status>\n\n" + body
    return "";
}

int parse_status(const std::string& response) {
    // TODO: 从 "STATUS 200" 里解析出数字
    return 0;
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <string>

// 实现 make_response（STATUS 行 + 空行 + body）与 parse_status（解析状态码）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <string>

// 需求：状态行协议的构造与解析。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <string>

int main() {
    int fail = 0;
    auto r = make_response(200, "OK");
    if (r != "STATUS 200\n\nOK") {
        std::printf("FAIL: 响应格式不符\n"); ++fail;
    }
    if (parse_status("STATUS 404\n\nNot Found") != 404) {
        std::printf("FAIL: 应解析出 404\n"); ++fail;
    }
    if (parse_status(make_response(500, "err")) != 500) {
        std::printf("FAIL: 应解析出 500\n"); ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 3,
        'time_limit_ms': 2000,
    },
    {
        'id': 139,
        'chapter_id': 10,
        'type': 'boss',
        'title': 'Boss · 帧回显连接处理',
        'sort_order': 11,
        'prompt': '实现 `void handle_connection(int fd)`：循环从 fd 读长度前缀帧（4 字节大端长度 + payload），\n'
                  '把每帧原样写回，直到 EOF。\n\n'
                  '> 收口：帧协议 + socket 读写循环，收口 C10。',
        'starter_easy': r'''#include <unistd.h>
#include <vector>
#include <string>

// 循环：读 4 字节长度，再读 payload，原样写回；EOF 退出
void handle_connection(int fd) {
    // TODO: 读长度头；读 payload；写回长度头+payload
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <unistd.h>
#include <vector>
#include <string>

// 实现 handle_connection：读 4 字节大端长度 -> 读 payload -> 原样写回，EOF 结束。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <unistd.h>
#include <vector>
#include <string>

// 需求：连接级长度前缀帧回显。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <cstring>
#include <sys/socket.h>
#include <unistd.h>

static void write_frame(int fd, const char* p, unsigned len) {
    unsigned char hdr[4] = {
        (unsigned char)((len >> 24) & 0xff),
        (unsigned char)((len >> 16) & 0xff),
        (unsigned char)((len >> 8) & 0xff),
        (unsigned char)(len & 0xff)
    };
    write(fd, hdr, 4);
    write(fd, p, len);
}

int main() {
    int fail = 0;
    int sv[2];
    socketpair(AF_UNIX, SOCK_STREAM, 0, sv);
    write_frame(sv[0], "hi", 2);
    write_frame(sv[0], "world", 5);
    shutdown(sv[0], SHUT_WR);
    handle_connection(sv[1]);
    unsigned char hdr[4];
    char body[64] = {0};
    read(sv[0], hdr, 4);
    read(sv[0], body, sizeof(body));
    if (body[0] != 'h' || body[1] != 'i') {
        std::printf("FAIL: 第一帧应回显 hi\n"); ++fail;
    }
    read(sv[0], hdr, 4);
    read(sv[0], body, sizeof(body));
    if (std::strcmp(body, "world") != 0) {
        std::printf("FAIL: 第二帧应回显 world\n"); ++fail;
    }
    close(sv[0]); close(sv[1]);
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 3000,
    },
    # ================= C11 写代码题（id 140-144，数据库交互·纯内存模拟） =================
    {
        'id': 140,
        'chapter_id': 11,
        'type': 'short',
        'title': '短题 1 · SQL 转义',
        'sort_order': 7,
        'prompt': '实现 `std::string sql_escape(const std::string& s)`：\n'
                  '把单引号 `\'` 转义成 `\'\'`，反斜杠 `\\` 转义成 `\\\\`。\n\n'
                  '> 考点：SQL 注入原理与参数转义。',
        'starter_easy': r'''#include <string>

// 单引号 ' -> ''，反斜杠 \ -> \\
std::string sql_escape(const std::string& s) {
    std::string out;
    // TODO: 遍历 s，遇 ' 追加 ''，遇 \ 追加 \\
    return out;
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <string>

// 实现 sql_escape：' -> ''，\ -> \\。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <string>

// 需求：SQL 字符串转义（防注入）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <string>

int main() {
    int fail = 0;
    if (sql_escape("O'Brien") != "O''Brien") {
        std::printf("FAIL: 单引号应转义成两个单引号\n"); ++fail;
    }
    if (sql_escape("a\\b") != "a\\\\b") {
        std::printf("FAIL: 反斜杠应转义成两个反斜杠\n"); ++fail;
    }
    if (sql_escape("plain") != "plain") {
        std::printf("FAIL: 无特殊字符应原样返回\n"); ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 3,
        'time_limit_ms': 2000,
    },
    {
        'id': 141,
        'chapter_id': 11,
        'type': 'short',
        'title': '短题 2 · 参数化占位符绑定',
        'sort_order': 8,
        'prompt': '实现 `std::string bind_sql(const std::string& tmpl, const std::vector<std::string>& params)`：\n'
                  '把模板里的每个 `?` 依次替换成 `\'<转义后的值>\'`（值先做 SQL 转义，再用单引号包起来）。\n\n'
                  '> 考点：预处理语句（prepared statement）的占位符绑定思想。',
        'starter_easy': r'''#include <string>
#include <vector>

// 把 tmpl 里每个 '?' 替换成 '<转义后的参数值>'（值内部 ' -> ''）
std::string bind_sql(const std::string& tmpl, const std::vector<std::string>& params) {
    std::string out;
    // TODO: 遍历 tmpl，遇 '?' 取下一个参数，转义后加单引号
    return out;
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <string>
#include <vector>

// 实现 bind_sql：'?' 替换为转义后的参数（单引号包裹，内部 ' -> ''）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <string>
#include <vector>

// 需求：SQL 模板占位符参数绑定。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <string>
#include <vector>

int main() {
    int fail = 0;
    auto q = bind_sql("SELECT * FROM t WHERE name = ? AND id = ?", {"O'Brien", "7"});
    if (q != "SELECT * FROM t WHERE name = 'O''Brien' AND id = '7'") {
        std::printf("FAIL: 绑定结果不符\n"); ++fail;
    }
    auto q2 = bind_sql("no placeholder", {});
    if (q2 != "no placeholder") {
        std::printf("FAIL: 无占位符应原样返回\n"); ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 142,
        'chapter_id': 11,
        'type': 'short',
        'title': '短题 3 · 连接池',
        'sort_order': 9,
        'prompt': '实现 `ConnectionPool`：\n\n'
                  '- 构造 `ConnectionPool(int size)`：size 个可用连接（编号 0..size-1）\n'
                  '- `int acquire()`：取出一个连接编号，无可用返回 -1\n'
                  '- `void release(int id)`：归还连接\n\n'
                  '> 考点：连接池对象管理（mutex + 可用队列）。',
        'starter_easy': r'''#include <vector>
#include <mutex>

class ConnectionPool {
    std::vector<int> free_;
    std::mutex m_;
public:
    ConnectionPool(int size) {
        // TODO: 初始化 free_ = 0..size-1
    }
    int acquire() {
        // TODO: 加锁，有则取出一个返回，无则 -1
    }
    void release(int id) {
        // TODO: 加锁归还
    }
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <vector>
#include <mutex>

// 实现 ConnectionPool：acquire/release 加锁操作 free_ 队列。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <vector>
#include <mutex>

// 需求：固定大小的连接池（获取/归还）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>

int main() {
    int fail = 0;
    ConnectionPool pool(2);
    int a = pool.acquire();
    int b = pool.acquire();
    if (a < 0 || b < 0 || a == b) {
        std::printf("FAIL: 应能取到两个不同连接\n"); ++fail;
    }
    if (pool.acquire() != -1) {
        std::printf("FAIL: 池空应返回 -1\n"); ++fail;
    }
    pool.release(a);
    if (pool.acquire() != a) {
        std::printf("FAIL: 归还后应能再次取到\n"); ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 3,
        'time_limit_ms': 2000,
    },
    {
        'id': 143,
        'chapter_id': 11,
        'type': 'short',
        'title': '短题 4 · 事务回滚模拟',
        'sort_order': 10,
        'prompt': '实现内存 KV + undo 日志的 `Transaction`：\n\n'
                  '- `void begin()`：开始事务（清空 undo 日志）\n'
                  '- `void set(const std::string& k, const std::string& v)`：记录旧值到 undo，写入新值\n'
                  '- `void commit()`：提交（清空 undo）\n'
                  '- `void rollback()`：回滚到 begin 时的状态\n\n'
                  '> 考点：事务原子性 + undo 日志。',
        'starter_easy': r'''#include <map>
#include <string>
#include <vector>

class Transaction {
    std::map<std::string, std::string> store_;
    std::vector<std::pair<std::string, std::string>> undo_;
    bool in_tx_ = false;
public:
    void begin() {
        // TODO: 标记 in_tx_ = true，清空 undo_
    }
    void set(const std::string& k, const std::string& v) {
        // TODO: 事务中记录旧值到 undo_，写入新值
    }
    void commit() {
        // TODO: 清空 undo_，in_tx_ = false
    }
    void rollback() {
        // TODO: 倒序恢复 undo_ 里的旧值
    }
    std::string get(const std::string& k) const {
        auto it = store_.find(k);
        return it == store_.end() ? "" : it->second;
    }
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <map>
#include <string>
#include <vector>

// 实现 Transaction：set 记录 undo，rollback 倒序恢复，commit 清空 undo。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <map>
#include <string>
#include <vector>

// 需求：带 undo 日志的内存事务（begin/commit/rollback）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <string>

int main() {
    int fail = 0;
    Transaction tx;
    tx.begin();
    tx.set("a", "1");
    tx.commit();
    tx.begin();
    tx.set("a", "2");
    tx.rollback();
    if (tx.get("a") != "1") {
        std::printf("FAIL: 回滚后 a 应为 1\n"); ++fail;
    }
    tx.begin();
    tx.set("b", "x");
    tx.commit();
    if (tx.get("b") != "x") {
        std::printf("FAIL: 提交后 b 应为 x\n"); ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 144,
        'chapter_id': 11,
        'type': 'boss',
        'title': 'Boss · 内存 DAO',
        'sort_order': 11,
        'prompt': '实现内存用户表 `UserDao`（DAO 模式 + 事务）：\n\n'
                  '- `bool insert(int id, const std::string& name)`：插入，id 已存在返回 false\n'
                  '- `std::string find(int id)`：查找，不存在返回 ""\n'
                  '- `bool update(int id, const std::string& name)`：更新，不存在返回 false\n'
                  '- `bool remove(int id)`：删除，不存在返回 false\n'
                  '- `void begin()` / `void commit()` / `void rollback()`：事务（rollback 恢复 begin 时状态）\n\n'
                  '> 收口：DAO 模式 + 事务，收口 C11。',
        'starter_easy': r'''#include <map>
#include <string>
#include <vector>

class UserDao {
    std::map<int, std::string> store_;
    std::vector<std::pair<int, std::string>> undo_;
    bool in_tx_ = false;
public:
    bool insert(int id, const std::string& name) {
        // TODO: id 已存在返回 false；事务中记录 undo 以便回滚删除
    }
    std::string find(int id) {
        // TODO: 返回名字，不存在返回 ""
    }
    bool update(int id, const std::string& name) {
        // TODO: 不存在返回 false；事务中记录旧值
    }
    bool remove(int id) {
        // TODO: 不存在返回 false；事务中记录旧值
    }
    void begin() {
        // TODO: 清空 undo_，标记 in_tx_
    }
    void commit() {
        // TODO: 清空 undo_
    }
    void rollback() {
        // TODO: 倒序恢复 undo_
    }
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <map>
#include <string>
#include <vector>

// 实现 UserDao：CRUD + 事务（undo 用「空串=原来不存在」作哨兵）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <map>
#include <string>
#include <vector>

// 需求：内存用户表 DAO，支持 CRUD 与事务回滚。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <string>

int main() {
    int fail = 0;
    UserDao dao;
    if (!dao.insert(1, "alice")) { std::printf("FAIL: 插入应成功\n"); ++fail; }
    if (dao.insert(1, "bob")) { std::printf("FAIL: 重复 id 应失败\n"); ++fail; }
    if (dao.find(1) != "alice") { std::printf("FAIL: 应查到 alice\n"); ++fail; }
    if (!dao.update(1, "alice2")) { std::printf("FAIL: 更新应成功\n"); ++fail; }
    if (dao.find(1) != "alice2") { std::printf("FAIL: 更新后应查到 alice2\n"); ++fail; }
    if (dao.update(99, "x")) { std::printf("FAIL: 更新不存在应失败\n"); ++fail; }
    if (!dao.remove(1)) { std::printf("FAIL: 删除应成功\n"); ++fail; }
    if (dao.find(1) != "") { std::printf("FAIL: 删除后应查不到\n"); ++fail; }
    dao.begin();
    dao.insert(2, "carol");
    dao.rollback();
    if (dao.find(2) != "") { std::printf("FAIL: 回滚后应查不到\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 9,
        'time_limit_ms': 2000,
    },
    # ================= C13 写代码题（id 145-149，C++20 高级特性） =================
    {
        'id': 145,
        'chapter_id': 13,
        'type': 'short',
        'title': '短题 1 · concept 约束加法',
        'sort_order': 7,
        'prompt': '定义 concept `Addable`（要求 `a + b` 合法），并用它约束模板函数 `add`。\n\n'
                  '> 考点：C++20 concept + requires 表达式。',
        'starter_easy': r'''#include <concepts>

// TODO: 定义 concept Addable，要求 T 支持 a + b
template <typename T>
concept Addable = requires(T a, T b) {
    // TODO: a + b
};

// TODO: 用 Addable 约束下面这个 add
template <typename T>
T add(T a, T b) {
    return a + b;
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <concepts>

// 定义 concept Addable（requires { a + b; }），并用它约束 add(T a, T b)。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <concepts>

// 需求：用 concept 约束一个加法模板函数。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <string>

static_assert(Addable<int>, "int 应满足 Addable");
static_assert(Addable<std::string>, "string 应满足 Addable");

int main() {
    int fail = 0;
    if (add(2, 3) != 5) { std::printf("FAIL: add(2,3) 应为 5\n"); ++fail; }
    if (add(std::string("a"), std::string("b")) != "ab") { std::printf("FAIL: add(a,b) 应为 ab\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 146,
        'chapter_id': 13,
        'type': 'short',
        'title': '短题 2 · 三路比较 spaceship',
        'sort_order': 8,
        'prompt': '实现 `struct Version`（int major/minor/patch），用 `auto operator<=>(const Version&) const = default;`\n'
                  '提供完整比较（== != < <= > >=）。\n\n'
                  '> 考点：C++20 三路比较运算符 `<=>`。',
        'starter_easy': r'''#include <compare>

struct Version {
    int major = 0;
    int minor = 0;
    int patch = 0;

    // TODO: 用 = default 提供三路比较（C++20）
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <compare>

// 实现 struct Version，加 auto operator<=>(const Version&) const = default。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <compare>

// 需求：版本号结构体，支持全部比较运算符（用 <=> 默认实现）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>

int main() {
    int fail = 0;
    Version a{1, 2, 3};
    Version b{1, 2, 4};
    Version c{1, 2, 3};
    if (!(a < b)) { std::printf("FAIL: a 应小于 b\n"); ++fail; }
    if (!(a == c)) { std::printf("FAIL: a 应等于 c\n"); ++fail; }
    if (a > b) { std::printf("FAIL: a 不应大于 b\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 3,
        'time_limit_ms': 2000,
    },
    {
        'id': 147,
        'chapter_id': 13,
        'type': 'short',
        'title': '短题 3 · ranges 管道',
        'sort_order': 9,
        'prompt': '实现 `std::vector<int> even_doubled(const std::vector<int>& in)`：\n'
                  '用 `std::views::filter` 过滤偶数，`std::views::transform` 翻倍，返回结果。\n\n'
                  '> 考点：C++20 ranges 管道（filter | transform）。',
        'starter_easy': r'''#include <vector>
#include <ranges>

std::vector<int> even_doubled(const std::vector<int>& in) {
    // TODO: in | filter(偶数) | transform(翻倍)
    auto view = in
        | std::views::filter(/* TODO */)
        | std::views::transform(/* TODO */);
    // TODO: 用 view.begin()/view.end() 构造返回 vector
    return {};
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <vector>
#include <ranges>

// 实现 even_doubled：filter 偶数 + transform 翻倍，用 begin/end 构造 vector。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <vector>
#include <ranges>

// 需求：用 ranges 管道过滤偶数并翻倍。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <vector>

int main() {
    int fail = 0;
    auto r = even_doubled({1, 2, 3, 4, 5, 6});
    if (r.size() != 3) {
        std::printf("FAIL: 应有 3 个结果\n"); ++fail;
    } else if (r[0] != 4 || r[1] != 8 || r[2] != 12) {
        std::printf("FAIL: 结果应为 4,8,12\n"); ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 148,
        'chapter_id': 13,
        'type': 'short',
        'title': '短题 4 · ranges 累加 + concept',
        'sort_order': 10,
        'prompt': '实现 `sum_of_squares`：\n\n'
                  '- 定义 concept `Arithmetic = std::is_arithmetic_v<T>`\n'
                  '- `template<std::ranges::input_range R> requires Arithmetic<range_value_t<R>> auto sum_of_squares(const R& r)`\n'
                  '- 对 range 每个元素平方求和（元素类型做零值，避免 int/double 精度丢失）\n\n'
                  '> 考点：concept 约束 + ranges 变换 + accumulate。',
        'starter_easy': r'''#include <type_traits>
#include <ranges>
#include <numeric>
#include <vector>

// TODO: 定义 concept Arithmetic = std::is_arithmetic_v<T>
template <typename T>
concept Arithmetic = std::is_arithmetic_v<T>;

// TODO: 实现 sum_of_squares：平方后 accumulate 求和
// template <std::ranges::input_range R>
//     requires Arithmetic<std::ranges::range_value_t<R>>
// auto sum_of_squares(const R& r) {
//     auto sq = std::views::transform(r, [](auto x) { return x * x; });
//     using T = std::ranges::range_value_t<R>;
//     return std::accumulate(sq.begin(), sq.end(), T{0});
// }

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <type_traits>
#include <ranges>
#include <numeric>
#include <vector>

// 实现 concept Arithmetic + sum_of_squares（transform 平方 + accumulate 求和）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <type_traits>
#include <ranges>
#include <numeric>
#include <vector>

// 需求：用 concept 约束 + ranges 累加的平方和函数。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <vector>

int main() {
    int fail = 0;
    std::vector<int> a{1, 2, 3};
    if (sum_of_squares(a) != 14) { std::printf("FAIL: sum_of_squares(1,2,3) 应为 14\n"); ++fail; }
    std::vector<double> b{2.0, 3.0};
    if (sum_of_squares(b) != 13.0) { std::printf("FAIL: sum_of_squares(2,3) 应为 13\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 149,
        'chapter_id': 13,
        'type': 'boss',
        'title': 'Boss · ranges 数据管道',
        'sort_order': 11,
        'prompt': '实现 `positive_squares`：\n\n'
                  '- `template<std::ranges::input_range R> requires std::integral<range_value_t<R>>`\n'
                  '- `std::vector<long long> positive_squares(const R& r, std::size_t n)`\n'
                  '- 过滤正数 -> 平方 -> 取前 n 个，返回 vector\n\n'
                  '> 收口：filter | transform | take 完整管道，收口 C13。',
        'starter_easy': r'''#include <vector>
#include <ranges>
#include <concepts>

// 过滤正数 -> 平方 -> 取前 n 个，返回 vector<long long>
template <std::ranges::input_range R>
    requires std::integral<std::ranges::range_value_t<R>>
std::vector<long long> positive_squares(const R& r, std::size_t n) {
    // TODO: filter(x>0) | transform(x*x) | take(n)，再构造 vector
    return {};
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <vector>
#include <ranges>
#include <concepts>

// 实现 positive_squares：filter 正数 + transform 平方 + take(n)，构造 vector。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <vector>
#include <ranges>
#include <concepts>

// 需求：ranges 数据管道（过滤正数、平方、截取前 n）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <vector>

int main() {
    int fail = 0;
    std::vector<int> in{-3, -1, 1, 2, 3, 4, 5};
    auto r = positive_squares(in, 3);
    if (r.size() != 3) {
        std::printf("FAIL: 应取前 3 个\n"); ++fail;
    } else if (r[0] != 1 || r[1] != 4 || r[2] != 9) {
        std::printf("FAIL: 结果应为 1,4,9\n"); ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    # ================= C14 写代码题（id 150-154，模块与工程实践） =================
    {
        'id': 150,
        'chapter_id': 14,
        'type': 'short',
        'title': '短题 1 · 命名空间组织',
        'sort_order': 7,
        'prompt': '用命名空间 `config` 组织一组常量，避免污染全局命名空间：\n\n'
                  '- `constexpr int kMaxConnections = 100;`\n'
                  '- `constexpr const char* kAppName = "crow-blog";`\n'
                  '- `constexpr bool kDebug = false;`\n\n'
                  '> 考点：命名空间隔离。',
        'starter_easy': r'''// TODO: 在命名空间 config 里定义三个常量
namespace config {
    // kMaxConnections = 100
    // kAppName = "crow-blog"
    // kDebug = false
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''// 在命名空间 config 定义 kMaxConnections / kAppName / kDebug 三个 constexpr 常量。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''// 需求：用命名空间隔离一组配置常量。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <cstring>

int main() {
    int fail = 0;
    if (config::kMaxConnections != 100) { std::printf("FAIL: kMaxConnections 应为 100\n"); ++fail; }
    if (std::strcmp(config::kAppName, "crow-blog") != 0) { std::printf("FAIL: kAppName 不符\n"); ++fail; }
    if (config::kDebug) { std::printf("FAIL: kDebug 应为 false\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 3,
        'time_limit_ms': 2000,
    },
    {
        'id': 151,
        'chapter_id': 14,
        'type': 'short',
        'title': '短题 2 · 单例（Meyers）',
        'sort_order': 8,
        'prompt': '实现 `Config& get_config()`：返回函数内 static 局部单例，保证全局唯一 + 线程安全初始化。\n\n'
                  '> 考点：Meyers 单例（C++11 起 static 局部变量线程安全初始化）。',
        'starter_easy': r'''#include <string>

class Config {
    std::string host_ = "localhost";
    int port_ = 8080;
public:
    void set_port(int p) { port_ = p; }
    int port() const { return port_; }
};

// TODO: 返回 static 局部 Config 单例
Config& get_config() {
    // TODO: static Config instance; return instance;
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <string>

// 实现 Config + get_config()：函数内 static 局部单例。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <string>

// 需求：线程安全的 Meyers 单例。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>

int main() {
    int fail = 0;
    Config& a = get_config();
    Config& b = get_config();
    if (&a != &b) { std::printf("FAIL: 应为同一实例\n"); ++fail; }
    a.set_port(9090);
    if (b.port() != 9090) { std::printf("FAIL: 修改应共享\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 152,
        'chapter_id': 14,
        'type': 'short',
        'title': '短题 3 · 抽象接口 + 工厂',
        'sort_order': 9,
        'prompt': '实现多态形状：\n\n'
                  '- `struct Shape { virtual double area() const = 0; virtual ~Shape() = default; };`\n'
                  '- `Circle`（半径 r）：area = πr²\n'
                  '- `Square`（边长 s）：area = s²\n'
                  '- `std::unique_ptr<Shape> make_shape(const std::string& kind, double x)`：工厂\n\n'
                  '> 考点：抽象接口 + 工厂模式 + 智能指针。',
        'starter_easy': r'''#include <memory>
#include <string>
#include <cmath>

struct Shape {
    virtual double area() const = 0;
    virtual ~Shape() = default;
};

// TODO: Circle（area = pi*r*r）
// TODO: Square（area = side*side）
// TODO: make_shape("circle", x) / make_shape("square", x) 工厂

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <memory>
#include <string>
#include <cmath>

// 实现 Circle/Square（继承 Shape 实现 area）+ make_shape 工厂返回 unique_ptr<Shape>。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <memory>
#include <string>
#include <cmath>

// 需求：多态形状 + 工厂（圆/方）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <cmath>

int main() {
    int fail = 0;
    auto c = make_shape("circle", 2.0);
    auto s = make_shape("square", 3.0);
    if (!c || std::abs(c->area() - 12.566) > 0.01) { std::printf("FAIL: 圆面积应约 12.57\n"); ++fail; }
    if (!s || s->area() != 9.0) { std::printf("FAIL: 方面积应为 9\n"); ++fail; }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 153,
        'chapter_id': 14,
        'type': 'short',
        'title': '短题 4 · 依赖注入 + 接口',
        'sort_order': 10,
        'prompt': '实现可插拔日志接口：\n\n'
                  '- `struct Logger { virtual void log(const std::string& msg) = 0; virtual ~Logger() = default; };`\n'
                  '- `ConsoleLogger`：打印到 stdout\n'
                  '- `BufferedLogger`：收集到 vector，`const std::vector<std::string>& lines() const` 返回\n'
                  '- `void do_work(Logger& logger)`：依次调用 `logger.log("start")` 和 `logger.log("done")`\n\n'
                  '> 考点：依赖注入 + 接口抽象。',
        'starter_easy': r'''#include <string>
#include <vector>
#include <cstdio>

struct Logger {
    virtual void log(const std::string& msg) = 0;
    virtual ~Logger() = default;
};

// TODO: ConsoleLogger（log 打印到 stdout）
// TODO: BufferedLogger（收集到 vector，提供 lines()）
// TODO: do_work(Logger&)：依次 log "start"、"done"

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <string>
#include <vector>
#include <cstdio>

// 实现 ConsoleLogger / BufferedLogger / do_work（依赖注入接口）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <string>
#include <vector>
#include <cstdio>

// 需求：可插拔日志接口 + 依赖注入。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <vector>
#include <string>

int main() {
    int fail = 0;
    BufferedLogger logger;
    do_work(logger);
    auto lines = logger.lines();
    if (lines.size() != 2) {
        std::printf("FAIL: 应记录 2 条日志\n"); ++fail;
    } else if (lines[0] != "start" || lines[1] != "done") {
        std::printf("FAIL: 日志内容应为 start/done\n"); ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 2,
        'time_limit_ms': 2000,
    },
    {
        'id': 154,
        'chapter_id': 14,
        'type': 'boss',
        'title': 'Boss · 迷你库组织',
        'sort_order': 11,
        'prompt': '综合 C14，实现一个迷你配置库：\n\n'
                  '- 命名空间 `app` 内 `constexpr int kVersion = 3;`\n'
                  '- 接口 `Reporter`（`virtual void report(int value) = 0;`）+ `ConsoleReporter` / `CaptureReporter`\n'
                  '- 单例 `Counter& counter()`（含 `increment()` / `value()`）\n'
                  '- 工厂 `std::unique_ptr<Reporter> make_reporter(bool capture)`\n'
                  '- `void run_once(Reporter& r)`：`counter().increment()` 后 `r.report(counter().value())`\n\n'
                  '> 收口：命名空间 + 接口抽象 + 单例 + 工厂 + 依赖注入，收口 C14。',
        'starter_easy': r'''#include <memory>
#include <string>
#include <vector>
#include <cstdio>

namespace app {
    // TODO: constexpr int kVersion = 3;
}

struct Reporter {
    virtual void report(int value) = 0;
    virtual ~Reporter() = default;
};

// TODO: ConsoleReporter（report 打印 "value=%d\n"）
class ConsoleReporter : public Reporter {
public:
    void report(int value) override {
        // TODO
    }
};

// TODO: CaptureReporter（收集到 vector，提供 values()）
class CaptureReporter : public Reporter {
    std::vector<int> values_;
public:
    void report(int value) override {
        // TODO
    }
    const std::vector<int>& values() const { return values_; }
};

// TODO: 单例 Counter + counter()
class Counter {
    int n_ = 0;
public:
    void increment() {
        // TODO
    }
    int value() const {
        // TODO
    }
};
Counter& counter() {
    // TODO: static Counter c; return c;
}

// TODO: 工厂 make_reporter(bool capture)
std::unique_ptr<Reporter> make_reporter(bool capture) {
    // TODO
}

// TODO: run_once(Reporter&)：counter().increment() + report
void run_once(Reporter& r) {
    // TODO
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <memory>
#include <string>
#include <vector>
#include <cstdio>

// 实现：命名空间 app + Reporter 接口 + 单例 counter + 工厂 make_reporter + run_once。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <memory>
#include <string>
#include <vector>
#include <cstdio>

// 需求：迷你配置库（命名空间/接口/单例/工厂/依赖注入）。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <memory>

int main() {
    int fail = 0;
    if (app::kVersion != 3) { std::printf("FAIL: kVersion 应为 3\n"); ++fail; }
    auto cap = make_reporter(true);
    run_once(*cap);
    run_once(*cap);
    if (counter().value() != 2) { std::printf("FAIL: counter 应为 2\n"); ++fail; }
    auto cv = static_cast<CaptureReporter*>(cap.get());
    if (cv->values().size() != 2 || cv->values()[0] != 1 || cv->values()[1] != 2) {
        std::printf("FAIL: 报告序列应为 1,2\n"); ++fail;
    }
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 3,
        'time_limit_ms': 2000,
    },
    # ================= C1 扩充（id 170-177，2026-10-20） =================
    # 主线：同一个知识点穿三关 —— ① 入门选择题（会不会/是不是）→
    #       ② 源码阅读填空（为什么，看标准细节）→ ③ 自己实现（写错当场崩）。
    #   推导线：11（auto 衰减）→ 175（decltype(auto) + 只读零拷贝绑定）→ 1（自己写）
    #   类关键字线：172（没有 override 就静默不覆盖）→ 15（补 override 让编译期报错）→ 3（自己写）
    #   初始化线：173（花括号抢走重载）→ 174（initializer_list 存成员 = 悬垂）→ 4/177（自己写）
    #   枚举线：171（enum class 哪行编译不过）→ 176（自己重载位运算 + constexpr）
    {
        'id': 170,
        'chapter_id': 1,
        'type': 'choice',
        'title': '选择 4 · 结构化绑定绑了个啥',
        'sort_order': 4,
        'question': '循环结束后，`m` 里的 value 是多少？',
        'prompt': '''```cpp
std::map<std::string, int> m{{"a", 1}, {"b", 2}};

for (auto [k, v] : m) {
    v = 99;
}
```''',
        'options': [
            {'label': 'A', 'text': '全是 99 —— v 就是 value 的引用'},
            {'label': 'B', 'text': '还是 1 和 2 —— v 是 value 的拷贝'},
            {'label': 'C', 'text': '1 和 99 —— 只有最后一轮才生效'},
            {'label': 'D', 'text': '编译错误 —— std::map 的元素不能结构化绑定'},
        ],
        'answer': 'B',
    },
    {
        'id': 171,
        'chapter_id': 1,
        'type': 'choice',
        'title': '选择 5 · enum class 的四行代码',
        'sort_order': 5,
        'question': '这四行里只有一行编译不过，是哪个标号？',
        'prompt': '''```cpp
enum class Color : unsigned char { Red = 1, Green = 2, Blue = 4 };

Color c = Color::Red;

bool          a = (c == Color::Red);             /* ① */
Color         b = static_cast<Color>(3);         /* ② */
unsigned char u = static_cast<unsigned char>(c); /* ③ */
Color         d = Color::Red | Color::Blue;      /* ④ */
```''',
        'options': [
            {'label': 'A', 'text': '① 比较两个 enum class'},
            {'label': 'B', 'text': '② 从整数造一个 enum class'},
            {'label': 'C', 'text': '③ 取出它的底层整数值'},
            {'label': 'D', 'text': '④ 直接按位或'},
        ],
        'answer': 'D',
    },
    {
        'id': 172,
        'chapter_id': 1,
        'type': 'choice',
        'title': '选择 7 · 能编译、能运行、结果是错的',
        'sort_order': 7,
        'question': '这段程序能编译、能运行。它的输出是？',
        'prompt': '''```cpp
struct Base {
    virtual void draw() const { std::puts("Base"); }
    virtual ~Base() = default;
};

struct Derived : Base {
    void draw() { std::puts("Derived"); }
};

int main() {
    Derived d;
    Base& b = d;
    b.draw();
}
```''',
        'options': [
            {'label': 'A', 'text': 'Base —— Derived::draw 少了 const，是另一个函数'},
            {'label': 'B', 'text': 'Derived —— 虚函数总会调到派生类的版本'},
            {'label': 'C', 'text': '先 Base 一行、再 Derived 一行'},
            {'label': 'D', 'text': '编译错误 —— 派生类签名与基类不一致'},
        ],
        'answer': 'A',
    },
    {
        'id': 173,
        'chapter_id': 1,
        'type': 'choice',
        'title': '选择 8 · 花括号把重载抢走了',
        'sort_order': 8,
        'question': '`p.tag` 的值是？',
        'prompt': '''```cpp
struct Point {
    Point(int x, int y) : x(x), y(y), tag(1) {}
    Point(std::initializer_list<int>) : x(0), y(0), tag(2) {}
    int x, y, tag;
};

Point p{1, 2};
```''',
        'options': [
            {'label': 'A', 'text': '1 —— 走 Point(int, int)'},
            {'label': 'B', 'text': '2 —— 花括号初始化优先选 initializer_list 构造'},
            {'label': 'C', 'text': '编译错误 —— 两个构造都匹配，产生歧义'},
            {'label': 'D', 'text': '不确定 —— 由实现自行选择'},
        ],
        'answer': 'B',
    },
    {
        'id': 174,
        'chapter_id': 1,
        'type': 'blank',
        'title': '阅读 1 · 存下来的 initializer_list',
        'sort_order': 15,
        'keep_notes': True,
        'question': '空 1、空 2 填什么，才能让 `Args` 真正**拥有**元素，而不是只记住一块临时数组的地址？',
        'prompt': r'''// 危险示范：把 initializer_list 当成"容器"存进了成员
class Args {
public:
    Args(std::initializer_list<int> init) : list_(______) {}   /* 空1 */
    std::size_t size() const { return list_.size(); }
private:
    std::______<int> list_;                                    /* 空2 */
};

Args make() {
    return Args{1, 2, 3};    // 底层数组的生存期到这一行结束
}

int main() {
    Args a = make();
    std::printf("%zu\n", a.size());   // 旧写法在这里读到的是已销毁的数组
}''',
        'answer': [['init'], ['vector']],
    },
    {
        'id': 175,
        'chapter_id': 1,
        'type': 'blank',
        'title': '阅读 2 · 返回类型与只读绑定',
        'sort_order': 16,
        'keep_notes': True,
        'question': '空 1 要让 `front(v) = 99;` 能改到容器里的元素；空 2 要只读遍历且**不拷贝**元素。',
        'prompt': r'''// 泛型访问器：返回值要"原样保留"表达式的类型
template <class Container>
______ front(Container& c) {          /* 空1 */
    return c[0];
}

void dump(const std::vector<int>& v) {
    for (______ x : v) {              /* 空2 */
        std::printf("%d\n", x);
    }
}

int main() {
    std::vector<int> v{1, 2, 3};
    front(v) = 99;    // 必须能改到 v[0]
    dump(v);          // 只读遍历，且不许拷贝元素
}''',
        'answer': [
            ['decltype(auto)', 'auto&', 'auto &'],
            ['const auto&', 'const auto &', 'const int&', 'const int &'],
        ],
    },
    {
        'id': 176,
        'chapter_id': 1,
        'type': 'short',
        'title': '短题 5 · enum class 权限位',
        'sort_order': 22,
        'prompt': (
            '用 `enum class` 做一套**类型安全的权限位**（不许退化成裸 `int`）：\n\n'
            '1. `enum class Perm : unsigned char { None = 0, Read = 1, Write = 2, Exec = 4 };`（已提供）\n'
            '2. `operator|` / `operator&`：都返回 `Perm`，且必须是 `constexpr`\n'
            '3. `bool has(Perm set, Perm flag)`：`set` 是否**完全包含** `flag`（也要 `constexpr`）\n'
            '4. `std::string perm_to_string(Perm p)`：按 `rwx` 顺序输出三位，缺位写 `-`'
            '（`Read|Exec` → `"r-x"`，`None` → `"---"`）\n\n'
            '> 考点：`enum class` 不参与隐式整型运算，位运算只能自己重载；返回值坚持 `Perm`，'
            '调用方就拼不出非法值（比如 `1 | 8`）。\n'
            '> 隐藏测试里有一行 `static_assert`：`operator|` 与 `has` 少写 `constexpr` 会直接编译失败。\n'
        ),
        'starter_easy': r'''#include <string>

// 权限位（已提供，请勿修改）
enum class Perm : unsigned char { None = 0, Read = 1, Write = 2, Exec = 4 };

// TODO: 位或 —— 返回 Perm，必须 constexpr
constexpr Perm operator|(Perm a, Perm b) {
    // 提示：先转成 unsigned char 做位运算，再用 static_cast<Perm> 转回来
}

// TODO: 位与 —— 返回 Perm，必须 constexpr
constexpr Perm operator&(Perm a, Perm b) {
    // 提示：同上
}

// TODO: set 是否「完全包含」flag
constexpr bool has(Perm set, Perm flag) {
    // 提示：(set & flag) == flag
}

// TODO: 三位权限串：有该位输出字母，没有输出 '-'
std::string perm_to_string(Perm p) {
    // 提示：按 r / w / x 的顺序，依次判断 Perm::Read / Write / Exec
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <string>

// TODO: 定义 enum class Perm : unsigned char { None = 0, Read = 1, Write = 2, Exec = 4 }
// 并实现（签名必须一致，隐藏测试会直接调用）：
//   constexpr Perm operator|(Perm a, Perm b);
//   constexpr Perm operator&(Perm a, Perm b);
//   constexpr bool has(Perm set, Perm flag);
//   std::string perm_to_string(Perm p);      // "rwx" 风格，缺位 '-'

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <string>

// 需求：给权限做一套类型安全的位运算
//   - enum class Perm，底层类型 unsigned char，取值 None/Read/Write/Exec（1/2/4）
//   - operator| 与 operator& 都返回 Perm，且能在编译期求值
//   - has(set, flag) 判断「完全包含」，也能在编译期求值
//   - perm_to_string 输出三位 rwx 串，缺位写 '-'
//   - 隐藏测试会：static_assert 编译期求值、检查 has 语义、检查 "rwx"/"r-x"/"---"

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <string>

int main() {
    int fail = 0;

    // 用例1：位或后两位都在
    constexpr Perm rw = Perm::Read | Perm::Write;
    if (!has(rw, Perm::Read) || !has(rw, Perm::Write)) {
        std::printf("FAIL: Read|Write 应同时包含 Read 与 Write\n");
        ++fail;
    }
    // 用例2：不含的位必须判 false
    if (has(Perm::Read, Perm::Write)) {
        std::printf("FAIL: has(Read, Write) 应为 false\n");
        ++fail;
    }
    // 用例3：None 什么都不含
    if (has(Perm::None, Perm::Read)) {
        std::printf("FAIL: None 不该包含任何权限位\n");
        ++fail;
    }
    // 用例4：部分包含不算包含（只有 Read 时不能算含 Read|Exec）
    if (has(Perm::Read | Perm::Write, Perm::Read | Perm::Exec)) {
        std::printf("FAIL: 只含 Read 不该被判为包含 Read|Exec\n");
        ++fail;
    }
    // 用例5：编译期求值（少写 constexpr 这一步就过不去）
    static_assert(has(Perm::Read | Perm::Exec, Perm::Exec), "operator| 与 has 必须是 constexpr");

    // 用例6：位与返回 Perm，而不是退化成整数
    if ((Perm::Read & Perm::Write) != Perm::None) {
        std::printf("FAIL: Read & Write 应为 None\n");
        ++fail;
    }
    // 用例7：三位全开
    if (perm_to_string(Perm::Read | Perm::Write | Perm::Exec) != "rwx") {
        std::printf("FAIL: 三个权限都打开时应输出 rwx\n");
        ++fail;
    }
    // 用例8：缺位补 '-'
    if (perm_to_string(Perm::Read | Perm::Exec) != "r-x") {
        std::printf("FAIL: Read|Exec 应输出 r-x\n");
        ++fail;
    }
    // 用例9：None
    if (perm_to_string(Perm::None) != "---") {
        std::printf("FAIL: None 应输出 ---\n");
        ++fail;
    }

    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 8,
        'time_limit_ms': 2000,
    },
    {
        'id': 177,
        'chapter_id': 1,
        'type': 'short',
        'title': '短题 6 · 结构化绑定零拷贝遍历',
        'sort_order': 23,
        'prompt': (
            '用**结构化绑定 + 范围 for** 实现两个小函数，并且做到「遍历零拷贝」：\n\n'
            '1. `int total_qty(const std::vector<Row>& rows)`：所有行 `qty` 之和\n'
            '2. `bool restock(std::vector<Row>& rows, int id, int delta)`：把指定 `id` 的那行 '
            '`qty += delta`，找到返回 `true`，找不到返回 `false`\n\n'
            '`Row` 结构已提供（请勿修改），它带一个 `copies` 计数器。**隐藏测试会在遍历前后对比它**：\n'
            '- 两个函数遍历时都不许产生任何 `Row` 拷贝，否则直接判失败\n'
            '- `restock` 还必须能真正改到容器里的元素\n\n'
            '> 考点：范围 for 的绑定方式决定「拷贝 / 只读引用 / 可写引用」三档语义；'
            '结构化绑定只是解包语法糖，值类别还是要靠 `&` 决定。\n'
        ),
        'starter_easy': r'''#include <vector>
#include <cstddef>

// 行数据（已提供，请勿修改）——copies 记录拷贝次数，隐藏测试会检查它
struct Row {
    static int copies;
    int id;
    int qty;
    Row(int i, int q) : id(i), qty(q) {}
    Row(const Row& o) : id(o.id), qty(o.qty) { ++copies; }
    Row& operator=(const Row&) = default;
};

// TODO: 所有行 qty 之和（遍历时不许拷贝元素）
int total_qty(const std::vector<Row>& rows) {
    int sum = 0;
    for (______ [id, qty] : rows) {     // 提示：只读，用引用绑定
        sum += qty;
    }
    return sum;
}

// TODO: 给指定 id 的行 qty 加 delta，找到返回 true
bool restock(std::vector<Row>& rows, int id, int delta) {
    for (______ [rid, qty] : rows) {    // 提示：要能改到容器里的元素
        if (rid == id) { qty += delta; return true; }
    }
    return false;
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <vector>
#include <cstddef>

struct Row {
    static int copies;
    int id;
    int qty;
    Row(int i, int q) : id(i), qty(q) {}
    Row(const Row& o) : id(o.id), qty(o.qty) { ++copies; }
    Row& operator=(const Row&) = default;
};

// 实现（签名必须一致）：
//   int  total_qty(const std::vector<Row>& rows);
//   bool restock(std::vector<Row>& rows, int id, int delta);
// 要求：两个函数遍历时都零拷贝；restock 要改到容器里的元素。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <vector>
#include <cstddef>

struct Row {
    static int copies;
    int id;
    int qty;
    Row(int i, int q) : id(i), qty(q) {}
    Row(const Row& o) : id(o.id), qty(o.qty) { ++copies; }
    Row& operator=(const Row&) = default;
};

// 需求：
//   - 求所有行 qty 之和
//   - 给指定 id 的行加 delta，找到返回 true
//   - 遍历零拷贝（测试会数 Row 的拷贝次数）
//   - 隐藏测试会调用 total_qty / restock 并检查拷贝计数、目标行改动、非目标行不变

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>
#include <vector>

int Row::copies = 0;

int main() {
    int fail = 0;

    std::vector<Row> rows;
    rows.reserve(3);
    rows.emplace_back(1, 2);
    rows.emplace_back(2, 3);
    rows.emplace_back(3, 4);

    // 用例1：求和
    if (total_qty(rows) != 9) {
        std::printf("FAIL: total_qty 应为 9，实际 %d\n", total_qty(rows));
        ++fail;
    }
    // 用例2：只读遍历零拷贝
    Row::copies = 0;
    (void)total_qty(rows);
    if (Row::copies != 0) {
        std::printf("FAIL: total_qty 遍历时拷贝了 Row，应零拷贝\n");
        ++fail;
    }
    // 用例3：restock 找到目标
    if (!restock(rows, 2, 10)) {
        std::printf("FAIL: restock(2) 应找到并返回 true\n");
        ++fail;
    }
    // 用例4：目标行被改到
    if (rows[1].qty != 13) {
        std::printf("FAIL: id=2 的 qty 应变成 13，实际 %d\n", rows[1].qty);
        ++fail;
    }
    // 用例5：非目标行不受影响
    if (rows[0].qty != 2 || rows[2].qty != 4) {
        std::printf("FAIL: restock 不应动到其它行\n");
        ++fail;
    }
    // 用例6：可写遍历也零拷贝
    Row::copies = 0;
    (void)restock(rows, 1, 5);
    if (Row::copies != 0) {
        std::printf("FAIL: restock 遍历时拷贝了 Row，应零拷贝\n");
        ++fail;
    }
    // 用例7：找不到返回 false
    if (restock(rows, 99, 1)) {
        std::printf("FAIL: restock(99) 找不到时应返回 false\n");
        ++fail;
    }

    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 7,
        'time_limit_ms': 2000,
    },

    # ================= C1 扩充（id 178-183，2026-10-25）：枚举收尾 + union 从零补 =================
    # 枚举线补最后一环：171（类型系统不让它当 int）→ 178（switch 漏值靠 -Wswitch 兜）→ 176（自己造位运算）
    # union 线（全库此前 0 题）三关：
    #   179（读非活跃成员是 UB，编译器只是"容忍"）→ 180（大小/对齐怎么算）→
    #   181（非平凡成员 ⇒ 默认构造被删）→ 182（布局算到字节）→ 183（自己写 tagged variant，动手管生死）
    {
        'id': 178,
        'chapter_id': 1,
        'type': 'choice',
        'title': '选择 6 · 少写一个分支会怎样',
        'sort_order': 6,
        'question': '后来有人往 `Level` 里加了 `Error`，`to_string` 没跟着改。用 `g++ -Wall` 编译，结果是？',
        'prompt': r'''```cpp
enum class Level { Debug, Info, Warn, Error };

const char* to_string(Level lv) {
    switch (lv) {
        case Level::Debug: return "Debug";
        case Level::Info:  return "Info";
        case Level::Warn:  return "Warn";
    }
    return "Unknown";
}
```''',
        'options': [
            {'label': 'A', 'text': '编译报错：enum class 的 switch 必须覆盖全部枚举值'},
            {'label': 'B', 'text': '编译通过，-Wswitch 给出「枚举值 Error 未处理」的警告'},
            {'label': 'C', 'text': '编译通过，静默返回 "Unknown"，没有任何提示'},
            {'label': 'D', 'text': '编译报错：switch 缺少 default 分支'},
        ],
        'answer': 'B',
    },
    {
        'id': 179,
        'chapter_id': 1,
        'type': 'choice',
        'title': '选择 9 · 换个身份读同一块内存',
        'sort_order': 9,
        'question': '`x.f = 1.0f;` 之后读 `x.u`，C++ 标准对这个结果是怎么规定的？',
        'prompt': r'''```cpp
union U {
    float    f;
    unsigned u;
};

U x;
x.f = 1.0f;

std::printf("%08x\n", x.u);   // 换一个成员，读同一块内存
```''',
        'options': [
            {'label': 'A', 'text': '打印 3f800000 —— 标准保证就是这样'},
            {'label': 'B', 'text': '未定义行为 —— 同一时刻只有一个成员活着，读另一个不算合法'},
            {'label': 'C', 'text': '编译错误 —— union 的成员之间不能跨类型访问'},
            {'label': 'D', 'text': '实现定义 —— 标准要求必须等于 A，只是写法不推荐'},
        ],
        'answer': 'B',
    },
    {
        'id': 180,
        'chapter_id': 1,
        'type': 'choice',
        'title': '选择 10 · 一个 union 有多大',
        'sort_order': 10,
        'question': '按 x86-64 常见 ABI（`double` 对齐 8 字节），`sizeof(U)` 与 `sizeof(P)` 分别是？',
        'prompt': r'''```cpp
union U {
    char   a[5];
    int    b;
    double c;
};

struct P {
    char tag;
    U    body;
};
```''',
        'options': [
            {'label': 'A', 'text': '5 和 6 —— union 取最大成员，结构体把成员直接接上'},
            {'label': 'B', 'text': '8 和 9 —— union 按最大对齐补齐，结构体不补'},
            {'label': 'C', 'text': '8 和 16 —— 两者都按各自的最大对齐取整'},
            {'label': 'D', 'text': '17 和 18 —— union 也要把所有成员都占住'},
        ],
        'answer': 'C',
    },
    {
        'id': 181,
        'chapter_id': 1,
        'type': 'choice',
        'title': '选择 11 · Msg 能不能直接声明',
        'sort_order': 11,
        'question': '`Msg m;` 这一行会怎样？',
        'prompt': r'''```cpp
struct Msg {
    int kind;
    union {
        int         num;
        std::string text;
    };
};
```''',
        'options': [
            {'label': 'A', 'text': '编译通过，num 与 text 都处于未初始化状态'},
            {'label': 'B', 'text': '编译通过，text 被默认构造成空串'},
            {'label': 'C', 'text': '编译报错 —— 匿名 union 里有非平凡成员，Msg 的默认构造函数被删除了'},
            {'label': 'D', 'text': '编译通过，但 text 从未构造，用它就是未定义行为'},
        ],
        'answer': 'C',
    },
    {
        'id': 182,
        'chapter_id': 1,
        'type': 'blank',
        'title': '阅读 3 · 头结构的真实大小',
        'sort_order': 17,
        'keep_notes': True,
        'question': '空 1 填 `sizeof(Body)`，空 2 填 `body` 在 `Packet` 里的字节偏移。两个空都只填**十进制数字**（按 x86-64 常见 ABI）。',
        'prompt': r'''#include <cstddef>
#include <cstdint>

union Body {
    struct { uint32_t seq; uint16_t len; } hdr;
    uint8_t  raw[8];
};

struct Packet {
    uint8_t kind;
    Body    body;
};

static_assert(sizeof(Body)           == ______, "Body 多大？");      /* 空1 */
static_assert(offsetof(Packet, body) == ______, "body 从哪开始？");  /* 空2 */''',
        'answer': [['8'], ['4']],
    },
    {
        'id': 183,
        'chapter_id': 1,
        'type': 'short',
        'title': '短题 7 · 亲手管一个 union',
        'sort_order': 24,
        'prompt': (
            '用 `enum class` + `union` 实现一个**带标签的联合体**（tagged union），把三种值塞进同一块内存：\n\n'
            '1. `enum class Kind { Int, Real, Obj };`\n'
            '2. `class Value` 的四个构造 + 析构：\n'
            '   - `Value()` → `Kind::Int`，整数 0\n'
            '   - `Value(int)` → `Kind::Int`\n'
            '   - `Value(double)` → `Kind::Real`\n'
            '   - `Value(const Tracked&)` → `Kind::Obj`，**必须在 union 成员上 placement new**\n'
            '   - `~Value()` → **只析构活跃的那个成员**（只有 `Kind::Obj` 才去析构 `Tracked`）\n'
            '3. **显式禁止拷贝**（`= delete`）：union 里有非平凡成员时，编译器本来就会删掉隐式拷贝，'
            '写出来是为了让意图明确、报错落在改动点\n'
            '4. 四个访问器：`kind()` / `as_int()` / `as_real()` / `as_tracked()`，类型不对时分别返回 '
            '`0` / `0.0` / `nullptr`，**不许 reinterpret**\n\n'
            '`Tracked` 已提供（请勿修改），它带一个**存活计数**：隐藏测试会在构造/析构前后对比 '
            '`Tracked::alive()` —— 漏写析构、或者不管 `kind` 见谁都析构，都会当场露出来。\n\n'
            '> 考点：union 只负责「放」，不负责「造」和「销毁」。活跃成员靠 placement new 出生，'
            '靠显式调用析构函数死亡 —— 这一套正是 `std::variant` 内部干的事。\n'
        ),
        'starter_easy': r'''#include <cstddef>
#include <new>

// 带存活计数的被管理类型（已提供，请勿修改）
struct Tracked {
    int v;
    explicit Tracked(int x) : v(x) { ++alive(); }
    Tracked(const Tracked& o) : v(o.v) { ++alive(); }
    ~Tracked() { --alive(); }
    static int& alive() { static int n = 0; return n; }
};

enum class Kind { Int, Real, Obj };

class Value {
public:
    Value() : kind_(Kind::Int) { i_ = 0; }
    explicit Value(int v) : kind_(Kind::Int) { i_ = v; }
    explicit Value(double v) : kind_(Kind::Real) { d_ = v; }

    // TODO: 在 t_ 上 placement new 一份 Tracked 副本
    explicit Value(const Tracked& t) : kind_(Kind::Obj) {
        // 提示：new (&t_) Tracked(t);
    }

    // TODO: 只析构活跃成员
    ~Value() {
        // 提示：if (kind_ == Kind::Obj) t_.~Tracked();
    }

    Value(const Value&) = delete;
    Value& operator=(const Value&) = delete;

    Kind   kind() const    { return kind_; }
    int    as_int() const  { return kind_ == Kind::Int  ? i_ : 0; }
    double as_real() const { return kind_ == Kind::Real ? d_ : 0.0; }

    // TODO: 不是 Obj 时返回 nullptr
    const Tracked* as_tracked() const { return nullptr; }

private:
    Kind kind_;
    union { int i_; double d_; Tracked t_; };
};

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <cstddef>
#include <new>

// 带存活计数的被管理类型（已提供，请勿修改）
struct Tracked {
    int v;
    explicit Tracked(int x) : v(x) { ++alive(); }
    Tracked(const Tracked& o) : v(o.v) { ++alive(); }
    ~Tracked() { --alive(); }
    static int& alive() { static int n = 0; return n; }
};

// 实现（签名必须一致，隐藏测试会直接调用）：
//   enum class Kind { Int, Real, Obj };
//   class Value {
//   public:
//       Value();                          // Kind::Int，整数 0
//       explicit Value(int v);            // Kind::Int
//       explicit Value(double v);         // Kind::Real
//       explicit Value(const Tracked& t); // Kind::Obj，placement new 构造
//       ~Value();                         // 只析构活跃成员
//       Value(const Value&) = delete;
//       Value& operator=(const Value&) = delete;
//       Kind kind() const;
//       int  as_int() const;                  // 非 Int 返回 0
//       double as_real() const;               // 非 Real 返回 0.0
//       const Tracked* as_tracked() const;    // 非 Obj 返回 nullptr
//   private:
//       Kind kind_;
//       union { int i_; double d_; Tracked t_; };
//   };

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <cstddef>
#include <new>

// 带存活计数的被管理类型（已提供，请勿修改）
struct Tracked {
    int v;
    explicit Tracked(int x) : v(x) { ++alive(); }
    Tracked(const Tracked& o) : v(o.v) { ++alive(); }
    ~Tracked() { --alive(); }
    static int& alive() { static int n = 0; return n; }
};

// 需求：自己实现一个带标签的联合体（tagged union）
//   - enum class Kind { Int, Real, Obj }，三种值共用一块内存
//   - 构造：Value() / Value(int) / Value(double) / Value(const Tracked&)
//   - 析构：只析构活跃成员，绝不许对非 Obj 的值调 Tracked 的析构
//   - 禁止拷贝（拷贝后必然双重销毁）
//   - 访问器：kind() / as_int() / as_real() / as_tracked()，类型不符返回 0 / 0.0 / nullptr
//   - 隐藏测试会用 Tracked::alive() 检查构造与析构是否配平

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>

int main() {
    int fail = 0;
    Tracked::alive() = 0;

    // 用例1：Int 的 kind
    {
        Value v(42);
        if (v.kind() != Kind::Int) {
            std::printf("FAIL: Value(42).kind() 应为 Int\n");
            ++fail;
        }
    }
    // 用例2：Int 的值
    {
        Value v(42);
        if (v.as_int() != 42) {
            std::printf("FAIL: Value(42).as_int() 应为 42\n");
            ++fail;
        }
    }
    // 用例3：Real 的 kind 与值
    {
        Value v(3.5);
        if (v.kind() != Kind::Real || v.as_real() != 3.5) {
            std::printf("FAIL: Value(3.5) 应为 Real / 3.5\n");
            ++fail;
        }
    }
    // 用例4：Int 值的 as_tracked 必须给 nullptr
    {
        Value v(7);
        if (v.as_tracked() != nullptr) {
            std::printf("FAIL: Int 值的 as_tracked() 应返回 nullptr\n");
            ++fail;
        }
    }
    // 用例5：装一个 Obj 后 alive 恰为 1（多了说明没配平临时量或重复构造）
    {
        Value v(Tracked(9));
        if (Tracked::alive() != 1) {
            std::printf("FAIL: 装一个 Obj 后 alive 应为 1，实际 %d\n", Tracked::alive());
            ++fail;
        }
    }
    // 用例6：Obj 取值正确
    {
        Value v(Tracked(9));
        const Tracked* p = v.as_tracked();
        if (p == nullptr || p->v != 9) {
            std::printf("FAIL: as_tracked() 应指向值为 9 的对象\n");
            ++fail;
        }
    }
    // 用例7：Obj 值的 as_int 不能瞎读内存
    {
        Value v(Tracked(9));
        if (v.as_int() != 0) {
            std::printf("FAIL: Obj 值的 as_int() 应返回 0\n");
            ++fail;
        }
    }
    // 用例8：离开作用域后 alive 归零（漏写析构就挂在这里）
    if (Tracked::alive() != 0) {
        std::printf("FAIL: Obj 析构后 alive 应回到 0，实际 %d\n", Tracked::alive());
        ++fail;
    }
    // 用例9：混合类型混着析构，alive 仍归零（不判 kind 就析构会在这里露出来）
    {
        Value a(1);
        Value b(2.5);
        Value c(Tracked(3));
        Value d(4);
    }
    if (Tracked::alive() != 0) {
        std::printf("FAIL: 混合析构后 alive 应回到 0，实际 %d\n", Tracked::alive());
        ++fail;
    }
    // 用例10：默认构造必须是 Int / 0
    {
        Value v;
        if (v.kind() != Kind::Int || v.as_int() != 0) {
            std::printf("FAIL: 默认构造应为 Int / 0\n");
            ++fail;
        }
    }
    // 用例11：Obj 值的 as_real 也不能瞎读内存
    {
        Value v(Tracked(9));
        if (v.as_real() != 0.0) {
            std::printf("FAIL: Obj 值的 as_real() 应返回 0.0\n");
            ++fail;
        }
    }

    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 11,
        'time_limit_ms': 2000,
    },

]

# ---------- 题解表（id -> markdown 题解：思路 + 参考实现 + 要点）----------
# 与 EXERCISES 分离存放，便于集中维护与增补；build() 按 id 关联下发。
# 缺失时 solution 记 NULL（前端不显示题解块）。
SOLUTIONS = {
    # ================= C1 · 现代语法糖 =================
    1: '''**思路**：`auto` 按值推导、丢掉引用与顶层 const；要返回引用必须显式写 `int&`。

**参考实现**
```cpp
int& get_ref()   { return g_value; }   // 返回引用，可改 g_value
int  get_value() { return g_value; }   // 返回值拷贝
```

**要点**
- `auto x = get();`（`get` 返回 `const int&`）推导出的 `x` 是 `int`——引用被丢弃。
- 想保留引用：`auto& x = ...`，或 `decltype(auto) x = ...`。''',

    2: '''**思路**：`enum class` 是强类型，映射到字符串用 `switch`；反向解析用一张小表逐个 `strcmp`。

**参考实现**
```cpp
const char* level_to_string(LogLevel level) {
    switch (level) {
        case LogLevel::Debug: return "Debug";
        case LogLevel::Info:  return "Info";
        case LogLevel::Warn:  return "Warn";
        case LogLevel::Error: return "Error";
    }
    return "Unknown";
}

bool level_from_string(const char* s, LogLevel& out) {
    struct Pair { const char* name; LogLevel level; };
    static const Pair table[] = {
        {"Debug", LogLevel::Debug}, {"Info", LogLevel::Info},
        {"Warn", LogLevel::Warn},   {"Error", LogLevel::Error},
    };
    for (const Pair& p : table)
        if (std::strcmp(s, p.name) == 0) { out = p.level; return true; }
    return false;
}
```

**要点**
- `enum class` 不隐式转 `int`，`switch` 里必须写全 `LogLevel::Xxx`。
- 解析失败要返回 `false`（且别写坏 `out`），序列化要覆盖「未知」。''',

    3: '''**思路**：`override` 让编译器校验「确实重写了基类虚函数」；`final` 禁止再继承；`=delete` 显式禁用拷贝。

**参考实现**
```cpp
class Circle : public Shape {
public:
    explicit Circle(double radius) : radius_(radius) {}
    double area() const override { return 3.141592653589793 * radius_ * radius_; }
private:
    double radius_;
};

class Square final : public Shape {          // final 禁止再被继承
public:
    explicit Square(double side) : side_(side) {}
    double area() const override { return side_ * side_; }
private:
    double side_;
};

class NonCopyable {
public:
    NonCopyable() = default;
    NonCopyable(const NonCopyable&) = delete;
    NonCopyable& operator=(const NonCopyable&) = delete;
};
```

**要点**
- 漏写 `override` 且签名不匹配时，会「静默不重写」——`override` 把它变成编译错误。
- `final` 放类名后禁止继承，放虚函数后禁止再重写。''',

    4: '''**思路**：用 `std::initializer_list` 初始化，`begin/end` 返回裸指针即可支持范围 for；`operator[]` 返回引用才能就地修改。

**参考实现**
```cpp
IntArray(std::initializer_list<int> init)
    : data_(new int[init.size()]), size_(static_cast<int>(init.size())) {
    int i = 0;
    for (int v : init) data_[i++] = v;
}
~IntArray() { delete[] data_; }
int size() const { return size_; }
int& operator[](int i) { return data_[i]; }
int* begin() { return data_; }
int* end()   { return data_ + size_; }
```

**要点**
- 范围 for 只要求有 `begin()`/`end()`，返回指针即可。
- `operator[]` 返回 `int&`（引用），`for (int& x : arr) x *= 2;` 才能改到原数组。
- 自己管内存的类必须封住拷贝：`IntArray(const IntArray&) = delete;` + `operator=` 同理。否则 `IntArray b = a;` 会让两个对象持有同一个 `data_`，析构时 `double free`（本题隐藏用例直接查 `is_copy_constructible`）。''',

    5: '''**思路**：合法转移是一条单向链加一个回环（`TimeWait → Closed`）。用 `switch` 表达转移表；`=delete` 拷贝让状态机成为只移动类型。

**参考实现**
```cpp
bool can_transition(TcpState from, TcpState to) {
    switch (from) {
        case TcpState::Closed:      return to == TcpState::Listen;
        case TcpState::Listen:      return to == TcpState::Established;
        case TcpState::Established: return to == TcpState::FinWait1;
        case TcpState::FinWait1:    return to == TcpState::FinWait2;
        case TcpState::FinWait2:    return to == TcpState::TimeWait;
        case TcpState::TimeWait:    return to == TcpState::Closed;
    }
    return false;
}

const char* state_to_string(TcpState s) {
    switch (s) {
        case TcpState::Closed:      return "Closed";
        case TcpState::Listen:      return "Listen";
        case TcpState::Established: return "Established";
        case TcpState::FinWait1:    return "FinWait1";
        case TcpState::FinWait2:    return "FinWait2";
        case TcpState::TimeWait:    return "TimeWait";
    }
    return "Unknown";
}

bool state_from_string(const char* s, TcpState& out) {
    struct Pair { const char* name; TcpState st; };
    static const Pair table[] = {
        {"Closed", TcpState::Closed}, {"Listen", TcpState::Listen},
        {"Established", TcpState::Established}, {"FinWait1", TcpState::FinWait1},
        {"FinWait2", TcpState::FinWait2}, {"TimeWait", TcpState::TimeWait},
    };
    for (const Pair& p : table)
        if (std::strcmp(s, p.name) == 0) { out = p.st; return true; }
    return false;
}

class TcpStateMachine {
public:
    TcpStateMachine() : state_(TcpState::Closed) {}
    TcpStateMachine(const TcpStateMachine&) = delete;
    TcpStateMachine& operator=(const TcpStateMachine&) = delete;

    bool transition(TcpState to) {
        if (!can_transition(state_, to)) return false;
        state_ = to;
        return true;
    }
    TcpState state() const { return state_; }
private:
    TcpState state_;
};
```

**要点**
- 非法转移必须**返回 false 且保持状态不变**（别先赋值再校验）。
- 序列化用「表驱动」比一串 `if` 更难漏项。
- 收口本章三件事：`enum class`（强类型）+ `=delete`（只移动）+ 序列化 round-trip。''',

    11: '''**正确答案：A（`a` 是 `int`，`b` 是 `const int&`）**。

- `auto` 按**值**推导：丢掉引用，也丢掉**顶层** const ⇒ `a` 是 `int`。
- `auto&` 保留引用语义：`get()` 返回 `const int&`，推导出 `b` 是 `const int&`（这里的 const 不是顶层限定，不会被丢）。

**要点**
- 推论：`auto a = get(); a = 1;` 改不到 `g_value`；而 `auto& b = get(); b = 1;` 直接编译不过（`b` 是 const 引用）。
- 想把值类别一起继承下来，用 `decltype(auto)`（见 阅读 2）。''',

    12: '''**正确答案：B（`const int&`）**。

`decltype` 有两条规则：
- `decltype(名字)` → 取变量**声明的类型**：`decltype(cx)` 是 `const int`（顶层 const 保留）。
- `decltype(表达式)` → 由**值类别**决定：`(cx)` 是「带括号的 const 左值」，左值 ⇒ 结果是 `const int&`。

**要点**
- 括号是值类别开关：`decltype(x)` 和 `decltype((x))` 是两个世界。
- 同一机制解释了 `decltype(auto)` 里写 `return (x);` 会返回引用——括号把表达式变成了左值。''',

    13: '''**正确答案：A（`{2, 3, 4}`）**。

- ① `for (auto x : v)`：`x` 是**副本**，`x *= 2` 只改副本，容器纹丝不动。
- ② `for (auto& x : v)`：`x` 绑定到元素本身，`+1` 生效 ⇒ `{2, 3, 4}`。

**要点**
- 范围 for 的 `auto` 与普通 `auto` 一致，都是值拷贝；要改元素必须 `auto&`。
- 只读又不想拷贝：`const auto&`（见 阅读 2 空 2）。''',

    14: '''**两个空依次是：`0`、`nullptr`**。

- `f(0)`：`0` 的类型就是 `int`，`f(int)` 是**精确匹配**；`f(void*)` 还要走一次「空指针转换」 ⇒ 选 `f(int)`。
- `f(nullptr)`：`nullptr` 的类型是 `std::nullptr_t`，它**不是整数**，转不成 `int`，只能转成指针 ⇒ 选 `f(void*)`。

**要点**
- 这就是 `nullptr` 存在的意义：`f(0)` / `f(NULL)` 在指针场景下会静默选错重载。
- 别把 `NULL` 当"类型安全的空指针"：它多数实现就是 `0`（或 `0L`），本质还是整数常量。''',

    15: '''**应填：`override`**。

基类是 `void draw() const`，派生类写成 `void draw() override;` —— 签名对不上，带 `override` 时编译器立刻报
`marked 'override', but does not override`。

**要点**
- 不带 `override` 时这段代码**编译得过**：`Derived::draw()` 只是把基类的名字**隐藏**了（重载而非覆盖），多态悄悄失效。
- `override` 的价值不是"写清楚"，而是把「静默不覆盖」变成编译错误（对照 选择 6）。''',

    16: '''**三个空依次填：`= default`、`= delete`、`= delete`**。

```cpp
class Handle {
public:
    Handle() = default;                            // 要默认行为，但显式声明
    Handle(const Handle&) = delete;                // 禁止拷贝构造
    Handle& operator=(const Handle&) = delete;     // 禁止拷贝赋值
};
```

**要点**
- `= default`：显式要编译器生成（同时保住「平凡 / 可平凡复制」等性质，写空实现 `{}` 会丢）。
- `= delete`：仍然参与重载决议，一旦被选中就报错，比 `private` 未定义更早、更明确。''',

    170: '''**正确答案：B（还是 1 和 2）**。

`for (auto [k, v] : m)` 里的 `v` 绑定的是**解包出来的副本**：`auto` 只剥一层，`*it` 被拷贝进一个隐藏变量，`k` / `v` 再绑到副本的成员上。改 `v` 不会写回容器。

**要点**
- 要改 value：`for (auto& [k, v] : m) v = 99;`（`k` 仍是 `const std::string&`，map 的 key 本来就只读）。
- 只读遍历：`for (const auto& [k, v] : m)`，零拷贝。
- 性能陷阱：`auto` 版本每轮都拷一份 key，`std::string` 就是一次堆分配。''',

    171: '''**正确答案：D（④）**。

- ① `enum class` 之间可以 `==` 比较 ✅
- ② `static_cast<Color>(3)` 是**显式**转换，合法 ✅
- ③ `static_cast<unsigned char>(c)` 取出底层整数值，合法 ✅
- ④ `Color::Red | Color::Blue` —— `enum class` **不参与隐式整型转换**，也没有内置 `operator|` ⇒ 编译错误 ✅

**要点**
- 想按位组合必须自己重载 `operator|` / `operator&`（见 短题 5）。
- 这正是 `enum class` 的价值：别人写不出 `Color::Red + 1` 这种无意义表达式。''',

    172: '''**正确答案：A（输出 `Base`）**。

`Derived::draw()` 少了 `const`，和 `Base::draw() const` **不是同一个函数** —— 它没有覆盖，只是把基类名字隐藏了。`b` 的静态类型是 `Base&`，虚表里 `draw` 仍指向 `Base::draw`。

**要点**
- 这是 C++ 最阴的一类 bug：**能编译、能运行、结果错**，而且只有走基类指针/引用时才暴露。
- 修法：写 `void draw() const override;`，签名不符时编译器当场报错（见 填空 2）。''',

    173: '''**正确答案：B（`tag == 2`）**。

列表初始化（花括号）在重载决议里**先挑 `std::initializer_list` 构造**：只要它可行就直接选它，完全不去比较 `Point(int, int)` 是否更"贴"。

**要点**
- 这是 `std::vector<int> v{3}`（1 个元素，值为 3）与 `v(3)`（3 个 0）的同一张坑。
- 想让 `{1,2}` 走普通构造，只能去掉 `initializer_list` 重载，或改用圆括号。
- 警示：类里同时存在 `initializer_list` 构造和普通构造时，`{}` 的含义会被悄悄改写。''',

    174: '''**两个空：`init`、`vector`**。

```cpp
class Args {
public:
    Args(std::initializer_list<int> init) : list_(init) {}
private:
    std::vector<int> list_;      // 真正持有元素
};
```

**要点**
- `std::initializer_list` 是**指向编译器生成的临时数组的「指针 + 长度」**，不是容器：拷贝它只拷这两个字段。
- `Args{1,2,3}` 里那个临时数组活到**完整表达式结束**；把 `initializer_list` 存进成员，事后再读就是访问已销毁的数组（悬垂，UB）。
- 规则：`initializer_list` 只当**参数**用，要留下就从它构造一个真正拥有元素的容器（`vector` / `array` / `string`）。''',

    175: '''**空 1：`decltype(auto)`（`auto&` 也对）；空 2：`const auto&`。**

```cpp
template <class Container>
decltype(auto) front(Container& c) { return c[0]; }   // decltype((c[0])) ⇒ T&

void dump(const std::vector<int>& v) {
    for (const auto& x : v) { /* 只读 + 零拷贝 */ }
}
```

**要点**
- `auto` 返回值会**衰减**（丢引用），`decltype(auto)` 按表达式原样推导；`c[0]` 是左值 ⇒ `int&`。
- 只读遍历一律 `const auto&`：`auto` 会拷元素，`std::string` 就是一次堆分配。
- 别在 `decltype(auto)` 里写 `return (c[0]);` —— 括号强制成引用，返回局部变量时直接悬垂。''',

    176: '''**思路**：`enum class` 没有内置位运算，把 `operator|` / `operator&` 重载成 `constexpr`，编译期和运行期就都能用。

**参考实现**
```cpp
constexpr Perm operator|(Perm a, Perm b) {
    return static_cast<Perm>(static_cast<unsigned char>(a) | static_cast<unsigned char>(b));
}
constexpr Perm operator&(Perm a, Perm b) {
    return static_cast<Perm>(static_cast<unsigned char>(a) & static_cast<unsigned char>(b));
}
constexpr bool has(Perm set, Perm flag) { return (set & flag) == flag; }

std::string perm_to_string(Perm p) {
    std::string s;
    s += has(p, Perm::Read)  ? 'r' : '-';
    s += has(p, Perm::Write) ? 'w' : '-';
    s += has(p, Perm::Exec)  ? 'x' : '-';
    return s;
}
```

**要点**
- 必须 `static_cast<unsigned char>` 转出来再转回 `Perm`：`enum class` 不参与隐式整型运算，`a | b` 本身编不过。
- 返回 `Perm` 而不是整数：调用方就拼不出 `Perm | 8` 这种越界值。
- `has` 写成 `(set & flag) == flag` 而不是 `!= None`，否则「只含 Read」也会被判成包含 `Read|Write`。
- 少写 `constexpr`，隐藏测试里的 `static_assert` 直接编译失败——这不是风格问题，是可测的能力。''',

    177: '''**思路**：结构化绑定本身不决定值类别，`&` 才决定。

**参考实现**
```cpp
int total_qty(const std::vector<Row>& rows) {
    int sum = 0;
    for (const auto& [id, qty] : rows) sum += qty;   // 零拷贝 + 只读
    return sum;
}

bool restock(std::vector<Row>& rows, int id, int delta) {
    for (auto& [rid, qty] : rows) {                  // 零拷贝 + 可写
        if (rid == id) { qty += delta; return true; }
    }
    return false;
}
```

**要点**
- `for (auto [id, qty] : rows)` 每轮拷一份元素，测试里的 `copies` 计数直接爆掉；成员是 `std::string` 时这就是每轮一次堆分配。
- `const auto&` vs `auto&`：只读用前者（连误改都被禁止），要写用后者。
- 结构化绑定拿到的 `qty` 是**成员本身的引用**（绑定到 `Row::qty`），所以 `qty += delta` 直接改到容器里的对象。''',

    178: '''**思路**：`switch` 不写 `default` 时，编译器才能替你查漏 —— `-Wswitch` 会点名没处理的枚举值。

**要点**
- 标准不要求 `switch` 穷尽枚举值，多出来的值直接跳过整条 `switch`，落到后面的 `return "Unknown"`。
- 一旦写了 `default:`，编译器认为"兜底已经有了"，新加的枚举值被静默吞掉；要连 `default` 一起查漏，得开 `-Wswitch-enum`。
- 所以推荐写法是：**枚举值全部列出来、不写 `default`**，函数末尾留一行兜底 `return`。
- 实测（g++ 13 加 `-Wall`）：漏 `Error` 时给出 1 条 `enumeration value 'Error' not handled in switch [-Wswitch]`；补上 `default` 后 0 条。''',

    179: '''**思路**：C 允许 union 类型双关，C++ 不允许 —— 同一时刻只有一个成员是"活的"，读别的成员是未定义行为。

**正确写法**
```cpp
unsigned u;
std::memcpy(&u, &x.f, sizeof u);              // C++11 起标准保证，编译器会优化成一条 mov
// 或者 C++20
unsigned u2 = std::bit_cast<unsigned>(x.f);   // 要求源与目标同大小、都可平凡复制
```

**要点**
- 你在 g++ / clang 上真的会打印 `3f800000` —— 但那是编译器"容忍"，不是标准保证。变量一旦是 `constexpr`、或整个 union 被常量传播，`-O2` 下的结果可能和直觉不一致。
- 真实事故来源：`union { float f; int i; }` 读非活跃成员做浮点判等，换个编译器或优化级别结果就漂。
- 需要"按位重解释"就用 `memcpy` / `bit_cast`，它们语义明确、且在现代编译器上零开销。''',

    180: '''**思路**：`sizeof(union)` = 最大成员的字节数，再向上取整到**最大对齐**；`struct` 里每个成员按自己的对齐摆放，缝隙补 padding。

- `char[5]` 大 5 / 对齐 1，`int` 大 4 / 对齐 4，`double` 大 8 / 对齐 8 ⇒ `sizeof(U) = 8`。
- `P`：`tag` 占 1 字节，`body` 要求 8 字节对齐 ⇒ 补 7 字节，`1 + 7 + 8 = 16`。

**要点**
- 对齐取的是**成员里最大的那个对齐**，不是"最大成员的类型"本身。
- 别用"成员大小相加"验算布局：`offsetof` + `static_assert` 才是可信的核对方式。
- x86-64 的 Linux/Windows 通常一致；某些 32 位 ARM ABI 里 `double` 只要求 4 字节对齐，`sizeof` 会变——这也是跨平台不能直接 `fwrite` 结构体的原因。''',

    181: '''**思路**：C++11 起，union 成员只要有非平凡的特殊成员函数，union 对应的那些函数就被**删除**。

**正确写法**
```cpp
struct Msg {
    Kind kind;
    union { int num; std::string text; };

    Msg() : kind(Kind::Num) { num = 0; }
    explicit Msg(const char* s) : kind(Kind::Text) { new (&text) std::string(s); }
    ~Msg() { if (kind == Kind::Text) text.~basic_string(); }
};
```

**要点**
- `std::string` 有非平凡的默认构造与析构 ⇒ 匿名 union 的默认构造、析构都被删 ⇒ 外层 `Msg` 的默认构造跟着被删。
- 报错是 `use of deleted function 'Msg::Msg()'`，很容易被误读成"union 不能放 string"——能放，但不能不管它。
- `= default` 救不了：默认化一个被删除的函数，结果还是删除。''',

    182: '''**思路**：`Body` 取最大成员（8 字节）并按最大对齐（4）取整 ⇒ 8；`Packet` 里 `kind` 占 1 字节，`body` 要求 4 字节对齐 ⇒ 偏移 4。

**要点**
- 匿名 `struct { uint32_t seq; uint16_t len; }` **不是 6 字节**，是 8 —— 尾部补 2 字节，保证数组里每个元素都对齐。
- 所以 `Packet` 是 12 而不是 10。"文档写 10 字节、抓包算出 12 字节"的经典对不上号，差的就是这 2 字节。
- 要跨编译器稳定：用 `static_assert` 把大小钉死，或按字段逐字节序列化（`std::endian` + `memcpy`），别直接 `fwrite` 整个结构体。''',

    183: '''**思路**：`enum class` 记标签，`union` 共用内存，构造靠 placement new、析构靠显式调用 —— 这就是 `std::variant` 的最小骨架。

**参考实现**
```cpp
class Value {
public:
    Value() : kind_(Kind::Int) { i_ = 0; }
    explicit Value(int v) : kind_(Kind::Int) { i_ = v; }
    explicit Value(double v) : kind_(Kind::Real) { d_ = v; }
    explicit Value(const Tracked& t) : kind_(Kind::Obj) { new (&t_) Tracked(t); }
    ~Value() { if (kind_ == Kind::Obj) t_.~Tracked(); }

    Value(const Value&) = delete;
    Value& operator=(const Value&) = delete;

    Kind kind() const { return kind_; }
    int  as_int() const { return kind_ == Kind::Int ? i_ : 0; }
    double as_real() const { return kind_ == Kind::Real ? d_ : 0.0; }
    const Tracked* as_tracked() const { return kind_ == Kind::Obj ? &t_ : nullptr; }

private:
    Kind kind_;
    union { int i_; double d_; Tracked t_; };
};
```

**要点**
- 直接 `t_ = t;` 是给一个**还没出生**的对象赋值 ⇒ 未定义行为；必须先 `new (&t_) Tracked(t)`。
- 析构必须判 `kind_`：对 `int` 值去调 `Tracked` 的析构，`alive()` 会变成负数（测试第 9 条专抓这个）。
- `= delete` 这条是**显式冗余**：只要 union 里有非平凡成员，隐式拷贝构造/赋值本来就被删了。写出来是为了把意图钉在代码里——真要能拷贝，得自己写深拷贝（`std::variant` 替你做完了）。
- 真实项目别手写：`std::variant<Tracked, int, double>` 就是这套东西的工业版，还带 `visit`。''',

    # ================= C2 · 移动语义与完美转发 =================
    6: '''**思路**：移动构造「偷」资源并置空源对象；移动赋值先释放旧资源、再转移，并处理自移动。

**参考实现**
```cpp
Buffer(Buffer&& other) noexcept : data_(other.data_), size_(other.size_) {
    other.data_ = nullptr;    // 源对象置空，防 double free
    other.size_ = 0;
}

Buffer& operator=(Buffer&& other) noexcept {
    if (this == &other) return *this;   // 自移动保护
    delete[] data_;                     // 先释放自己的旧资源
    data_ = other.data_;
    size_ = other.size_;
    other.data_ = nullptr;
    other.size_ = 0;
    return *this;
}
```

**要点**
- 移动后源对象必须可安全析构（置空）。
- 移动赋值：先判断自移动，再释放旧资源，顺序不能反。''',

    7: '''**思路**：三个 bug 都围绕「所有权」——移动构造忘了置空源、移动赋值忘了释放旧资源、忘了自移动保护。

**参考实现**
```cpp
// BUG #1 修复：移动构造里清空源指针
Wrapper(Wrapper&& other) noexcept : ptr_(other.ptr_) {
    other.ptr_ = nullptr;
}

// BUG #2 & #3 修复：先判自移动，再释放旧资源，最后转移
Wrapper& operator=(Wrapper&& other) noexcept {
    if (this == &other) return *this;   // 自移动
    delete ptr_;                        // 释放自己的旧资源
    ptr_ = other.ptr_;
    other.ptr_ = nullptr;
    return *this;
}
```

**要点**
- 忘置空源 → 两对象指向同一块内存 → `double free`。
- 忘释放旧资源 → 移动赋值时自己原来的指针无人 `delete` → 内存泄漏。
- 自移动若先 `delete ptr_` 再 `ptr_ = other.ptr_`，而 `other` 就是 `this`，会把刚释放的指针又赋回来 → 悬空。''',

    8: '''**思路**：`id=0` 表示「空」。移动即把 `id_` 拿走、源置 0；移动赋值先处理自移动再转移。

**参考实现**
```cpp
Resource(Resource&& other) noexcept : id_(other.id_) {
    other.id_ = 0;
}

Resource& operator=(Resource&& other) noexcept {
    if (this == &other) return *this;
    id_ = other.id_;
    other.id_ = 0;
    return *this;
}
```

**要点**
- 用「哨兵值 0」表示空资源，比指针版更直观，且移动后源对象仍可安全复用。
- `=delete` 拷贝后，`Resource` 只能移动——正好表达「独占所有权」。''',

    9: '''**思路**：`T&&` 是**转发引用**，`std::forward<T>(v)` 借助引用折叠还原实参的左右值类别。

**参考实现**
```cpp
template <typename T>
Thing make_thing(T&& v) {
    return Thing(std::forward<T>(v));
}
```

**要点**
- 传入左值 `int a; make_thing(a);` → `T` = `int&` → 转发为左值 → 命中 `Thing(int&)`。
- 传入右值 `make_thing(5);` → `T` = `int` → 转发为右值 → 命中 `Thing(int&&)`。
- **别用 `std::move(v)`**——它会把左值也强行转成右值，破坏转发。''',

    10: '''**思路**：综合三件事——移动语义（转移+置空）、异常安全（`noexcept`）、RVO（按值返回）。

**参考实现**
```cpp
Buffer(Buffer&& other) noexcept : data_(other.data_), size_(other.size_) {
    other.data_ = nullptr;
    other.size_ = 0;
}

Buffer& operator=(Buffer&& other) noexcept {
    if (this == &other) return *this;
    delete[] data_;
    data_ = other.data_;
    size_ = other.size_;
    other.data_ = nullptr;
    other.size_ = 0;
    return *this;
}
```

**要点**
- 两个移动操作都标 `noexcept`：`std::vector` 扩容才敢用移动，否则退化为拷贝。
- `create()` 按值返回局部对象，触发 RVO/拷贝省略，理论上零次拷贝。
- 移动赋值「先自检、再释放、后转移」，一步都不能少。''',

    17: '''**正确答案：B**。

`std::move` 只是**类型转换**（转成右值引用），本身不搬任何东西；真正搬资源的是随后的移动构造。移动后源对象处于**「有效但未指定」**状态——对 `vector`/`string` 通常是空的，但你**不能假设**它一定是某个值。

可以安全地「赋新值或析构」源对象，但别读它原来的内容。''',

    18: '''**正确答案：B（移动构造）**。

`std::string t = std::move(s);` 是**初始化**，不是赋值——`t` 是新对象，所以调用**移动构造函数**（形参 `std::string&&`）。

判别口诀：等号左边是不是「新对象」——是新对象就是构造；若 `t` 已存在再写 `t = std::move(s);`，那才是移动赋值。''',

    19: '''**正确答案：C（零次，拷贝省略）**。

`return w;` 返回局部对象，是 **NRVO（具名返回值优化）**的典型场景；再到 `Widget x = make_widget();` 的初始化，编译器可全程在目标内存里就地构造，理论上是零次拷贝/移动。

C++17 起，**纯右值**（如 `return Widget{};`）的拷贝省略是**强制**的；NRVO 虽非强制，但 `-O2` 下现代编译器基本都做。''',

    20: '''**应填：`std::move`**。

`std::vector<int> b = std::move(a);` 把 `a` 转成右值引用，触发 `vector` 的**移动构造**——直接接管 `a` 的堆缓冲，不逐元素深拷贝，复杂度 O(1)。

移动后 `a` 通常变空，但属「有效但未指定」，别依赖其内容。''',

    21: '''**应填：`std::forward`**。

`wrapper(T&& arg)` 里 `arg` 是**左值**（具名变量都是左值），直接传会丢右值属性。`std::forward<T>(arg)` 用引用折叠还原实参类别：

- 实参左值 → `T` = `int&` → 转发为左值；
- 实参右值 → `T` = `int` → 转发为右值。

别写成 `std::move(arg)`——那会把左值也强行变成右值。''',

    22: '''**应填：`noexcept`**。

`Buffer(Buffer&& other) noexcept;` 声明移动构造**不抛异常**。

为什么关键：`std::vector` 扩容时要在「移动」和「拷贝」间选——只有元素的移动构造是 `noexcept`，`vector` 才敢用移动（否则中途抛异常无法回滚）；否则退回拷贝，白白损失性能。''',
    # ================= C3 · 智能指针与 RAII =================
    95: '''**思路**：`unique_ptr` 独占所有权、不可拷贝，只能靠 `std::move` 转移。

**参考实现**
```cpp
std::unique_ptr<int> make_int(int v) {
    return std::make_unique<int>(v);
}

int take_ownership(std::unique_ptr<int> p) {
    return *p;   // 按值接管，函数返回时 p 析构、资源释放
}
```

**要点**
- 转移所有权必须 `std::move(p)` 或按值传入；写 `p2 = p1` 会编译错误。
- `make_unique` 比 `unique_ptr<int>(new int(v))` 更安全，也更简洁。''',

    96: '''**思路**：把 `next` 从 `shared_ptr` 改成 `weak_ptr`，打断「互相持有」的环；用 `lock()` 提升为 `shared_ptr` 再判有效性。

**参考实现**
```cpp
struct Node {
    std::weak_ptr<Node> next;    // 改 weak_ptr 打破循环
    int value;
    static int alive;
    Node(int v) : value(v) { ++alive; }
    ~Node() { --alive; }
};
int Node::alive = 0;

bool has_next(const std::shared_ptr<Node>& n) {
    return static_cast<bool>(n->next.lock());
}
```

**要点**
- `weak_ptr` 不增加引用计数，因此不阻止对象析构——环被打断。
- `lock()` 返回 `shared_ptr`（对象已死则为空），是访问 weak 指向对象的唯一安全方式；等价写法 `!n->next.expired()`。''',

    97: '''**思路**：数组必须用 `delete[]` 释放，所以给 `unique_ptr` 指定自定义 deleter；数组版本用 `int[]` 特化。

**参考实现**
```cpp
struct ArrayDeleter {
    void operator()(int* p) const { delete[] p; }
};

std::unique_ptr<int[], ArrayDeleter> make_array(int n, int v) {
    std::unique_ptr<int[], ArrayDeleter> arr(new int[n]);
    for (int i = 0; i < n; ++i) arr[i] = v;
    return arr;
}
```

**要点**
- `unique_ptr<int[], Del>` 提供 `operator[]`；用 `delete` 释放 `new[]` 分配的内存是未定义行为，deleter 必须匹配分配方式。
- deleter 是类型的一部分，不能只传值——`unique_ptr` 的第二个模板参数决定 deleter 类型。''',

    98: '''**思路**：控制块（引用计数）与资源指针一起共享；拷贝时计数 +1，析构时 -1，归零才释放。

**参考实现**
```cpp
explicit SimpleSharedPtr(T* p) : ptr_(p), refcount_(new std::size_t(1)) {}

SimpleSharedPtr(const SimpleSharedPtr& o)
    : ptr_(o.ptr_), refcount_(o.refcount_) {
    if (refcount_) ++*refcount_;
}

~SimpleSharedPtr() {
    if (refcount_ && --*refcount_ == 0) {
        delete ptr_;
        delete refcount_;
    }
}
```

**要点**
- 计数是「共享」的——所有副本指向同一块 `size_t`，所以拷贝构造**不能**重新 `new` 计数。
- 只有归零时才释放资源与控制块，先删资源再删计数。''',

    99: '''**思路**：RAII —— 构造接管、析构释放；禁拷贝、只移动，保证资源唯一归属、异常安全。

**参考实现**
```cpp
ResourceGuard(ResourceGuard&& other) : p_(other.p_) {
    other.p_ = nullptr;
}
ResourceGuard& operator=(ResourceGuard&& other) {
    if (this == &other) return *this;
    delete p_;                  // 先释放自己的
    p_ = other.p_;
    other.p_ = nullptr;
    return *this;
}
~ResourceGuard() { delete p_; }

int* release() { int* t = p_; p_ = nullptr; return t; }
```

**要点**
- 析构自动释放 ⇒ 中途抛异常也不泄漏（异常安全的核心）。
- `release()` 交出所有权后必须置空，否则析构会重复释放。
- 移动赋值「先自检、再释放、后转移」。''',

    23: '''**正确答案：B**。

`a->next = b; b->next = a;` 让两个 `shared_ptr` 互相持有，引用计数各为 2。离开作用域时计数只降到 1（对方还持有），谁都到不了 0 ⇒ 两个对象**永不释放，内存泄漏**。

修复：把其中一个（或两个）改成 `weak_ptr`，打破环。''',

    24: '''**正确答案：B（编译错误）**。

`unique_ptr` 删除了拷贝构造/拷贝赋值——它表达**独占**所有权，不允许两个 `unique_ptr` 指向同一资源。

要转移必须显式移动：`std::unique_ptr<int> p2 = std::move(p1);`（此后 `p1` 为空）。''',

    25: '''**正确答案：B（B 更好）**。

`std::make_shared<Widget>()` 把「对象」和「控制块（引用计数）」**一次分配**在连续内存里；而 `shared_ptr<Widget>(new Widget)` 要分配两次。

更关键是**异常安全**：`f(shared_ptr<Widget>(new Widget), g())` 中若 `new Widget` 成功而 `g()` 抛异常，`shared_ptr` 尚未构造 ⇒ 对象泄漏；`make_shared` 没有这个窗口。''',

    26: '''**应填：`make_shared`**。

`auto sp = std::make_shared<Widget>(args...);` 是创建 `shared_ptr` 的推荐写法——一次分配（对象 + 控制块）+ 异常安全。''',

    27: '''**应填：`weak_ptr`**。

`std::weak_ptr<Node> next;` 是**非拥有**的弱引用，不增加引用计数。父子/前后节点这类「回指」用 `weak_ptr` 即可打破循环引用，避免内存泄漏。''',

    28: '''**应填：`lock`**。

`wp.lock()` 把 `weak_ptr` **临时提升**为 `shared_ptr`：对象仍存活则返回有效 `shared_ptr`（计数 +1），否则返回空。

这是访问 `weak_ptr` 所指对象的唯一安全方式（不允许直接解引用）；`if (auto p = wp.lock())` 能在持有期间保证对象不被释放。''',

    # ================= C4 · Lambda 与函数式 =================
    100: '''**思路**：lambda 按值捕获 `n`，用 `std::function` 包装返回。

**参考实现**
```cpp
std::function<int(int)> make_adder(int n) {
    return [n](int x) { return x + n; };
}
```

**要点**
- `n` 按值捕获，lambda 持有的是它的**拷贝**——`make_adder` 返回后依然有效。
- 若用 `[&]`，`n` 是形参、返回即销毁 ⇒ 悬垂（正是下一题的反面教材）。''',

    101: '''**思路**：把 `[&]` 改成按值捕获 `[count]`，并用 `mutable` 允许修改内部副本。

**参考实现**
```cpp
std::function<int()> make_counter() {
    int count = 0;
    return [count]() mutable { return ++count; };
}
```

**要点**
- 按值捕获的变量在 lambda 内默认是 `const`，要改必须加 `mutable`。
- 状态保存在 lambda 内部副本里，函数返回后仍有效——避免悬垂。
- 每个 lambda 对象持有**自己**的一份 count 副本。''',

    102: '''**思路**：用 `std::function` 存回调；调用前判空。

**参考实现**
```cpp
void set(std::function<void(int)> fn) { fn_ = std::move(fn); }
void call(int v) { if (fn_) fn_(v); }
```

**要点**
- 空 `std::function` 转 `bool` 为 `false`，可直接 `if (fn_)` 判断。
- `set` 里用 `std::move(fn)` 避免多一次拷贝。''',

    103: '''**思路**：把 lambda 作为谓词/变换传给标准算法。

**参考实现**
```cpp
int count_positive(const std::vector<int>& v) {
    return static_cast<int>(std::count_if(v.begin(), v.end(),
        [](int x) { return x > 0; }));
}

std::vector<int> double_all(const std::vector<int>& v) {
    std::vector<int> out;
    out.reserve(v.size());
    std::transform(v.begin(), v.end(), std::back_inserter(out),
        [](int x) { return x * 2; });
    return out;
}
```

**要点**
- `std::count_if` 返回 `difference_type`，转 `int` 更贴合签名。
- `std::transform` 写入目标用 `std::back_inserter`，无需预先 `resize`。''',

    104: '''**思路**：handler 存在 `vector` 里，按注册顺序即 id；注销把槽位置空（不删，保持 id 稳定）；触发时跳过空槽。

**参考实现**
```cpp
int subscribe(std::function<void(int)> fn) {
    handlers_.push_back(std::move(fn));
    return next_id_++;
}

void unsubscribe(int id) {
    if (id >= 0 && id < static_cast<int>(handlers_.size()))
        handlers_[id] = nullptr;
}

void emit(int v) {
    for (auto& h : handlers_) if (h) h(v);
}
```

**要点**
- 注销用「置空」而非 `erase`——保证已发出的 id 与新 id 不冲突（`next_id_` 只增）。
- `if (h)` 判空，避免调用空 `std::function` 抛 `bad_function_call`。''',

    29: '''**正确答案：B（未定义行为）**。

`[&]` 捕获的是 `count` 的**引用**，而 `count` 是局部变量，`make_counter` 返回后即销毁 ⇒ 引用悬垂。之后再调用 `f()` 访问的是已失效内存，属**未定义行为**。

修复：按值捕获 + `mutable` —— `[count]() mutable { return ++count; }`。''',

    30: '''**正确答案：B（模板化的函数对象）**。

`[](auto a, auto b){...}` 是**泛型 lambda**（C++14）：编译器把它编译成一个函数对象，其 `operator()` 是**模板**——每个具体参数类型都会实例化出对应版本。

因此 `add(1, 2)` 和 `add(1.5, 2.5)` 都能用，甚至可混用不同类型。''',

    31: '''**正确答案：B（捕获 this 指针）**。

成员函数里写 `[=]`，编译器捕获的是 **`this` 指针**（按值），而非逐个拷贝成员；lambda 体里的 `v` 实际是 `this->v`。

⚠️ 因此若对象已析构，lambda 里的 `this` 就是悬垂的——异步/延迟回调要格外小心（C++20 可用 `[*this]` 按值拷贝整个对象）。''',

    32: '''**应填：`&`**。

`[&]` 按引用捕获所有用到的外部变量；`[&threshold]` 只按引用捕获 `threshold`。语义是「共享、可改」。

注意：按引用捕获要求被捕获对象在 lambda **调用**时仍然存活。''',

    33: '''**应填：`mutable`**。

按值捕获的变量在 lambda 内默认是 **const**，要修改必须加 `mutable`。它让 lambda 的 `operator()` 变成非 const 版本，可修改自己持有的副本。

⚠️ 改的是**副本**，不影响外部的 `n`。''',

    34: '''**应填：`auto`**。

`[](auto x){...}` 是泛型 lambda——参数 `auto` 让 `operator()` 成为模板，可接受任意类型（`int`/`double`…）。

比写死 `int` 更通用，本质是「按调用处实例化出多个版本」。''',

    # ================= C5 · 模板与元编程基础 =================
    105: '''**思路**：变参模板求和——单参数出口 + 递归展开（也可用 C++17 折叠表达式）。

**参考实现**
```cpp
template <typename T>
T sum(T t) { return t; }                       // 出口

template <typename T, typename... Args>
T sum(T t, Args... args) { return t + sum(args...); }
```

**要点**
- 递归版必须有**单参数出口**，否则无限递归。
- 折叠表达式等价写法：`template <typename... A> auto sum(A... a) { return (a + ...); }`。''',

    106: '''**思路**：通用模板返回 `"other"` 作兜底，为 `int`/`double` 写全特化。

**参考实现**
```cpp
template <typename T>
const char* type_name() { return "other"; }

template <> const char* type_name<int>()    { return "int"; }
template <> const char* type_name<double>() { return "double"; }
```

**要点**
- 全特化用 `template <>` 起头，且签名完全匹配。
- 通用版本是兜底；特化优先匹配。通用模板需在特化之前声明/定义（可见性）。''',

    107: '''**思路**：类型萃取靠「继承 `std::true_type`/`std::false_type`」实现，从而自带 `::value` 与 `::type`。

**参考实现**
```cpp
template <typename T> struct is_integral_type : std::false_type {};
template <> struct is_integral_type<int>       : std::true_type {};
template <> struct is_integral_type<long long> : std::true_type {};
```

**要点**
- `std::true_type` 即 `std::integral_constant<bool, true>`，继承它即获得 `::value`。
- 未列出的类型落入通用版本（false）。''',

    108: '''**思路**：用 `sizeof...(Ts)` 在编译期得到包中类型个数。

**参考实现**
```cpp
template <typename... Ts> struct typelist {};

template <typename List> struct length;
template <typename... Ts>
struct length<typelist<Ts...>> {
    static constexpr int value = sizeof...(Ts);
};
```

**要点**
- 用**部分特化** `length<typelist<Ts...>>` 把包拆开，才能对 `Ts...` 用 `sizeof...`。
- `sizeof...` 是编译期常量，`value` 可作模板参数。''',

    109: '''**思路**：`Length` 用 `sizeof...`；`Contains` 用折叠表达式对每个 `Ts` 做 `is_same` 的或运算。

**参考实现**
```cpp
template <typename... Ts> struct TypeList {};

template <typename List> struct Length;
template <typename... Ts>
struct Length<TypeList<Ts...>> { static constexpr int value = sizeof...(Ts); };

template <typename T, typename List> struct Contains;
template <typename T, typename... Ts>
struct Contains<T, TypeList<Ts...>> {
    static constexpr bool value = (std::is_same_v<T, Ts> || ...);
};
```

**要点**
- `(std::is_same_v<T, Ts> || ...)` 是折叠表达式，空包对 `||` 退化为 `false`——语义正好正确。
- 两个萃取都是 `constexpr` 成员，可直接当模板参数或 `if constexpr` 条件。''',

    35: '''**正确答案：A（10）**。

递归展开：`sum(1,2,3,4) = 1 + sum(2,3,4) = 1+2+sum(3,4) = 1+2+3+sum(4) = 1+2+3+4 = 10`。

`sum` 的返回类型是 `T`（首个参数的类型 `int`），所有参数会被统一到该类型参与运算。''',

    36: '''**正确答案：B（编译期丢弃）**。

`if constexpr` 的条件在**编译期**求值，为假的分支**不会被实例化/编译**——它直接从生成的代码里消失。

这是它和普通 `if` 的关键区别：普通 `if` 两个分支都要能编译通过，`if constexpr` 只编「命中」的那支。这正让「按类型走不同代码路径」的模板成为可能。''',

    37: '''**正确答案：A**。

`T::value_type` 是**依赖类型**（取决于模板参数 `T`）。在没有 `typename` 时，编译器无法判断 `T::value_type` 是「类型」还是「静态成员」，于是默认当成非类型 ⇒ 语法报错。

`typename` 就是明确告诉编译器：`T::value_type` 是一个**类型名**。''',

    38: '''**应填：`...`**。

`return (args + ...);` 是 C++17 **折叠表达式**（一元右折叠），把包中所有 `args` 用 `+` 串起来。

对 `+` 而言空包退化为 `0`；若想显式指定初始值可写 `(0 + ... + args)`。''',

    39: '''**应填：`typename`**。

`typename T::value_type x = c.front();` —— `T::value_type` 是依赖类型，必须用 `typename` 消歧，声明「这是个类型」。

漏写会报「dependent name is not a type」类的编译错误。''',

    40: '''**应填：`constexpr`**。

`if constexpr (std::is_integral_v<T>) { ... } else { ... }` —— 条件在编译期求值，只有命中的分支会被编译，另一支被丢弃。

这样即使「另一支」对当前 `T` 根本不合法（例如对非指针类型解引用），也不会报错。''',
    # ================= C6 · 现代工具类型 =================
    110: '''**思路**：找到就 `return x;`（`optional<int>` 可由 `int` 隐式构造），没找到 `return std::nullopt;`。

**参考实现**
```cpp
std::optional<int> find_first_even(const std::vector<int>& v) {
    for (int x : v) if (x % 2 == 0) return x;
    return std::nullopt;
}
```

**要点**
- `optional<T>` 可用 `T` 或 `std::nullopt` 构造，表达「有值 / 无值」。
- 调用方：`if (auto r = f(v)) { ... *r ... }`，或用 `r.value_or(默认值)`。''',

    111: '''**思路**：`string_view` 不拥有内存——返回局部 `string` 的视图会悬垂。改成返回**字符串字面量**（静态存储期，全程有效）。

**参考实现**
```cpp
std::string_view get_view() {
    return "hello";   // 字面量静态存储期，安全
}
```

**要点**
- `string_view` = 「指针 + 长度」，绝不拥有数据；被指向对象的生命周期必须覆盖使用期。
- 需要返回「自建字符串」时，返回 `std::string`（拥有）而不是 `string_view`。''',

    112: '''**思路**：`std::visit` 按当前持有类型分派；lambda 里用 `if constexpr` 按类型走分支。

**参考实现**
```cpp
std::string describe(const std::variant<int, std::string>& v) {
    return std::visit([](auto&& arg) -> std::string {
        using T = std::decay_t<decltype(arg)>;
        if constexpr (std::is_same_v<T, int>) {
            return "int:" + std::to_string(arg);
        } else {
            return "str:" + arg;
        }
    }, v);
}
```

**要点**
- `std::visit` 是访问 `variant` 的**类型安全**方式（不必手动查 `index()`）。
- `decltype(arg)` 带引用，用 `std::decay_t` 去掉修饰再比较。''',

    113: '''**思路**：同 optional 模式——找到返回，找不到 `nullopt`。

**参考实现**
```cpp
std::optional<int> find_divisible(const std::vector<int>& v, int d) {
    if (d == 0) return std::nullopt;
    for (int x : v) if (x % d == 0) return x;
    return std::nullopt;
}
```

**要点**
- 用 `optional` 取代「返回 -1 表示失败」这类**魔法值**——调用方无法忽略「可能失败」。
- 顺手防御 `d == 0`（除零）。''',

    114: '''**思路**：`map` 存键值；`get_str` 查不到返回 nullopt；`get_int` 在 `stoi` 失败时 catch 返回 nullopt。

**参考实现**
```cpp
void set(const std::string& key, const std::string& val) { kv_[key] = val; }

std::optional<std::string> get_str(const std::string& key) {
    auto it = kv_.find(key);
    if (it == kv_.end()) return std::nullopt;
    return it->second;
}

std::optional<int> get_int(const std::string& key) {
    auto it = kv_.find(key);
    if (it == kv_.end()) return std::nullopt;
    try { return std::stoi(it->second); }
    catch (...) { return std::nullopt; }
}
```

**要点**
- `std::stoi` 遇非法输入抛 `std::invalid_argument`（溢出抛 `out_of_range`），catch 后转 nullopt。
- 两个 `get_*` 都不抛异常，统一用返回值表达失败——这就是 `optional` 的价值。''',

    41: '''**正确答案：B（`std::nullopt`）**。

`{1,3,5}` 没有偶数，循环走完后执行 `return std::nullopt;`——`optional<int>` 的「无值」状态。

调用方应这样用：`if (auto r = find_even(v)) { 用 *r } else { 处理没找到 }`。注意**别**用 `*r` 直接解引用空 optional（未定义行为）。''',

    42: '''**正确答案：B（类型安全联合）**。

`std::variant` 与裸 `union` 不同：它**记得自己当前持有哪个类型**，访问时通过 `std::visit` 或 `std::get` 做类型检查——访问到错误类型会抛 `std::bad_variant_access`，而不是像 `union` 那样静默读到垃圾。

它**同一时刻只持有一种值**（不是三种并存）。''',

    43: '''**正确答案：B（悬垂，未定义行为）**。

`get_view` 里 `s` 是**局部** `std::string`，函数返回即销毁；返回的 `string_view` 仍指向那块已释放内存 ⇒ 悬垂。之后 `std::cout << v` 读的是失效内存，未定义行为。

修复：返回 `std::string`（拥有），或返回指向**静态存储期**字面量的 view。''',

    44: '''**应填：`value_or`**。

`o.value_or(42)`：`o` 有值则返回其值，无值则返回传入的默认值 `42`。

它比 `o ? *o : 42` 更简洁，且不会在无值时抛异常（区别于 `*o` 和 `o.value()`）。''',

    45: '''**应填：`visit`**。

`std::visit(回调, v)` 按 `variant` **当前持有的类型**调用回调（通常配合泛型 lambda）。这是访问 `variant` 的类型安全入口。

相比手动 `if (v.index() == 0)` 再 `get<0>`，`visit` 不会漏掉某个类型分支。''',

    46: '''**应填：`substr`**。

`view.substr(0, 5)` 返回 `"hello"` 的 `string_view`——只调整「指针 + 长度」，**零拷贝**。

这正是 `string_view` 的用途：字符串切片/解析时避免频繁分配。前提是被切的原字符串在使用期内一直有效。''',

    # ================= C7 · STL 容器与算法 =================
    115: '''**思路**：`std::set` 自动去重 + 升序，构造后拷回 `vector`。

**参考实现**
```cpp
std::vector<int> unique_sorted(const std::vector<int>& v) {
    std::set<int> s(v.begin(), v.end());          // 去重 + 排序
    return std::vector<int>(s.begin(), s.end());
}
```

**要点**
- `set` 底层红黑树：插入即去重、遍历即有序——「去重 + 排序」的最省事选型。
- 只需去重、不需排序时，`unordered_set` 更快（均摊 O(n)）。''',

    116: '''**思路**：`std::remove_if` 把要保留的元素前移、返回新的逻辑末尾，再 `erase` 掉尾部。别在循环里逐个 erase。

**参考实现**
```cpp
void remove_even(std::vector<int>& v) {
    v.erase(std::remove_if(v.begin(), v.end(),
                           [](int x) { return x % 2 == 0; }),
            v.end());
}
```

**要点**
- `erase` 会让「被删位置及之后」的迭代器**全部失效**；循环里 erase 必须用其返回值续接。
- erase-remove 惯用法：一趟扫描 + 一次批量删除，既安全又高效。''',

    117: '''**思路**：`std::set<int, std::greater<int>>` 用 `greater` 当比较器，遍历即为降序。

**参考实现**
```cpp
std::set<int, std::greater<int>> make_desc_set(const std::vector<int>& v) {
    return std::set<int, std::greater<int>>(v.begin(), v.end());
}
```

**要点**
- 比较器是**容器类型的一部分**，必须写进模板参数。
- `std::greater<int>` 让「大者在前」，从而降序；默认 `std::less<int>` 是升序。''',

    118: '''**思路**：先 `copy_if` 保留正数，再 `transform` 翻倍。

**参考实现**
```cpp
std::vector<int> filter_and_double(const std::vector<int>& v) {
    std::vector<int> tmp;
    std::copy_if(v.begin(), v.end(), std::back_inserter(tmp),
                 [](int x) { return x > 0; });
    std::transform(tmp.begin(), tmp.end(), tmp.begin(),
                   [](int x) { return x * 2; });
    return tmp;
}
```

**要点**
- 两步流水线：`copy_if` 过滤 → `transform` 变换。
- `transform` 可就地写回同一容器（输入、输出迭代器相同）。''',

    119: '''**思路**：`list` 维护使用顺序（头最新、尾最旧），`unordered_map` 记录 key → list 迭代器，实现 O(1) 查找与移动。

**参考实现**
```cpp
int get(int key) {
    auto it = map_.find(key);
    if (it == map_.end()) return -1;
    items_.splice(items_.begin(), items_, it->second);   // 移到最前
    return it->second->second;
}

void put(int key, int value) {
    auto it = map_.find(key);
    if (it != map_.end()) {                 // 已存在：更新 + 提前
        it->second->second = value;
        items_.splice(items_.begin(), items_, it->second);
        return;
    }
    if (static_cast<int>(items_.size()) >= capacity_) {
        map_.erase(items_.back().first);    // 淘汰最久未用（尾部）
        items_.pop_back();
    }
    items_.push_front({key, value});
    map_[key] = items_.begin();
}
```

**要点**
- `list::splice` 把节点在链内「搬」到头部：**不拷贝**、**迭代器不失效**——所以 `map_` 里的迭代器始终有效。
- 容量满时**先淘汰尾部再插入**，顺序别反。''',

    47: '''**正确答案：D（无法确定）**。

`vector::erase` 会让被删位置**及其之后**的所有迭代器失效；循环随后又执行 `++it`，操作的是已失效的迭代器 ⇒ **未定义行为**。UB 既不许诺"崩溃"，也不许诺"结果正确"，所以 A/B/C 都可能出现，也可能直接段错误。

选 B 的常见推理是：`erase` 后长度变 2，`++it` 就跳到末尾，循环结束。问题在于——`erase` 之后的 `it` 已不指向容器中任何有效位置，`++it` **不保证**"跳到下一个元素"。

修复用 erase-remove 惯用法：`v.erase(std::remove_if(v.begin(), v.end(), pred), v.end())`。''',

    48: '''**正确答案：B（`map`）**。

`map` 底层红黑树，**按键有序**，遍历即升序——需要「按 key 排序遍历」时选它。

`unordered_map` 是哈希表，均摊 O(1) 查找更快，但**遍历顺序无定义**（与插入顺序、哈希都无关）。''',

    49: '''**正确答案：B**。

`v.erase(std::remove(v.begin(), v.end(), 2), v.end())` —— `std::remove` 把**不为 2** 的元素前移、返回新逻辑末尾，`erase` 再删掉尾部的「残留」。

循环里逐个 erase 会触发迭代器失效（见第 1 题）；`remove` 本身不改变容器大小，必须配合 `erase`。''',

    50: '''**应填：`unordered_map`**。

`std::unordered_map<Point, int, Hash> m;` —— 第三个模板参数是**自定义哈希**；`Point` 作 key 时标准库没有它的哈希，必须自己提供。

注意 `unordered_map` 的 key 还需支持 `==` 比较（用于哈希冲突时的相等判断）。''',

    51: '''**应填：`set`**。

`std::set<int, std::greater<int>>` —— 第二个模板参数是**比较器**，`greater<int>` 让元素按降序排列。

`set` 自动去重且有序；换个比较器就能改成降序，容器类型本身不变。''',

    52: '''**应填：`find_if`**。

`std::find_if(v.begin(), v.end(), 谓词)` 返回**第一个**满足谓词的元素迭代器；都满足则返回 `end()`。

用前一定判 `it != v.end()` 再解引用，否则是未定义行为。要找「所有」满足的用 `copy_if`，找「个数」用 `count_if`。''',

    # ================= C8 · 文件操作与流 =================
    130: '''**思路**：`ofstream` 写、`ifstream` 读，逐行/逐个处理。

**参考实现**
```cpp
void write_numbers(const std::string& path, const std::vector<int>& nums) {
    std::ofstream out(path);
    for (int n : nums) out << n << "\\n";
}

std::vector<int> read_numbers(const std::string& path) {
    std::vector<int> result;
    std::ifstream in(path);
    int n;
    while (in >> n) result.push_back(n);   // 读到 EOF/失败自动停
    return result;
}
```

**要点**
- `while (in >> n)` 是标准读取惯用法：EOF 或格式不符时表达式为 false。
- 写文本用 `<<`（会做格式化），读用 `>>`（自动按空白切分）。''',

    131: '''**思路**：二进制模式用 `write`/`read` 原始字节；读回先定位文件大小再 `resize`。

**参考实现**
```cpp
void save_binary(const std::string& path, const std::vector<int>& data) {
    std::ofstream out(path, std::ios::binary);
    out.write(reinterpret_cast<const char*>(data.data()),
              static_cast<std::streamsize>(data.size() * sizeof(int)));
}

std::vector<int> load_binary(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    in.seekg(0, std::ios::end);
    std::streamsize bytes = in.tellg();
    in.seekg(0, std::ios::beg);
    std::vector<int> result(static_cast<std::size_t>(bytes) / sizeof(int));
    in.read(reinterpret_cast<char*>(result.data()), bytes);
    return result;
}
```

**要点**
- 必须开 `std::ios::binary`，否则 Windows 上 `\\n` 的换行翻译会破坏字节流。
- 读回：`seekg(末尾) → tellg()` 求字节数，再 `resize` 后 `read`。''',

    132: '''**思路**：定长缓冲循环 `read`，按 `gcount()` 取实际读数拼接。

**参考实现**
```cpp
std::string read_all_chunks(const std::string& path, size_t chunk_size) {
    std::ifstream in(path, std::ios::binary);
    std::string result;
    std::vector<char> buf(chunk_size);
    while (in.read(buf.data(), static_cast<std::streamsize>(chunk_size))
           || in.gcount() > 0) {
        result.append(buf.data(), static_cast<std::size_t>(in.gcount()));
    }
    return result;
}
```

**要点**
- 循环条件带 `|| in.gcount() > 0`，才能处理「最后一块不足 chunk_size」的收尾。
- 必须按 `gcount()` **实际读数**追加，不能直接用 `chunk_size`（否则尾部拼进垃圾）。''',

    133: '''**思路**：`ostringstream` 拼行；解析时先按行、再按逗号切。

**参考实现**
```cpp
std::string to_csv(const std::vector<std::vector<int>>& rows) {
    std::ostringstream out;
    for (std::size_t r = 0; r < rows.size(); ++r) {
        for (std::size_t c = 0; c < rows[r].size(); ++c) {
            if (c) out << ',';
            out << rows[r][c];
        }
        out << '\\n';
    }
    return out.str();
}

std::vector<std::vector<int>> from_csv(const std::string& text) {
    std::vector<std::vector<int>> result;
    std::istringstream lines(text);
    std::string line;
    while (std::getline(lines, line)) {
        if (line.empty()) continue;
        std::vector<int> row;
        std::istringstream cells(line);
        std::string cell;
        while (std::getline(cells, cell, ',')) row.push_back(std::stoi(cell));
        result.push_back(row);
    }
    return result;
}
```

**要点**
- 写：行内逗号分隔、行间换行；读：两级 `getline`（先整行、再逗号）。
- `std::getline(stream, s, ',')` 指定分隔符即可按逗号切分。''',

    134: '''**思路**：写入前判断行数，达到上限就把文件 `rename` 成 `.1` 并重置计数。

**参考实现**
```cpp
void append(const std::string& line) {
    if (count_ >= max_lines_) {
        std::rename(base_.c_str(), (base_ + ".1").c_str());
        count_ = 0;
    }
    std::ofstream out(base_, std::ios::app);
    out << line << "\\n";
    ++count_;
}
```

**要点**
- 滚动判断放在**写入前**，保证单文件不超过 `max_lines_` 行。
- `std::rename` 会覆盖同名旧文件（POSIX 语义），比「先删再建」更简洁。
- 生产环境还要处理多级滚动/按大小滚动，这里是最小实现。''',

    53: '''**正确答案：B（流状态 good）**。

`ifstream` 对象在布尔上下文里被转换为「流状态是否正常」——即 `!fail() && !bad()`。打开失败时流进入 fail 状态，`if (f)` 为假。

注意：它检查的是**流状态**，不是「文件是否为空」「是否到 EOF」「文件是否存在」（后三者是流状态的**结果**，但 `if(f)` 本身只测状态）。''',

    54: '''**正确答案：B（二进制模式 write）**。

文本模式的 `<<` 会做格式化，且平台相关的换行翻译（Windows 把 `\\n` 变 `\\r\\n`）会让字节数与预期不符，读回时错位。

要「按内存原样」存取 `int`，用 `std::ios::binary` + `write`/`read` 原始字节。跨平台严谨做法还要固定字节序（大小端），这里是同一平台读写。''',

    55: '''**正确答案：A（读到 eof 或格式失败）**。

`while (f >> x) { ... }` 里 `f >> x` 返回流引用，其布尔值反映**本次提取是否成功**：到达 EOF 或遇到不符合目标类型的字符时，流进入 fail 状态 ⇒ 循环结束。

这是 C++ 读取循环的标准写法——把「读取」和「判断成败」合成一个表达式，避免读完才判 EOF 导致多读一次。''',

    56: '''**应填：`app`**。

`std::ofstream f("a.txt", std::ios::app);` —— `app`（append）模式在文件末尾追加，**不截断**原内容。默认的 `out` 模式会清空文件。

（若文件不存在，`app` 会创建它。）''',

    57: '''**应填：`getline`**。

`while (std::getline(f, line)) { ... }` 每次读一整行（不含行尾换行）到 `line`，读到 EOF 时返回流进入 fail 状态、循环结束。

`std::getline` 是「按行读取」的标准方式，比 `>>` 更适合含空格的整行文本。''',

    58: '''**应填：`filesystem`**。

`namespace fs = std::filesystem;` —— C++17 引入的文件系统库，提供路径拼接、遍历目录、判断存在、创建/删除目录、文件大小等能力。

有时还需链接 `-lstdc++fs`（老编译器），较新的 GCC/Clang 已并入标准库。''',
    # ================= C9 · 多线程与并发 =================
    120: '''**思路**：用 `std::mutex` + `lock_guard` 把读/写包进临界区。

**参考实现**
```cpp
void increment() {
    std::lock_guard<std::mutex> lock(m_);
    ++value_;
}
int get() const {
    std::lock_guard<std::mutex> lock(m_);
    return value_;
}
```

**要点**
- `lock_guard` 构造即加锁、析构即解锁（RAII）——即使中途抛异常也会解锁。
- `m_` 必须声明为 `mutable`，否则 `get() const` 里无法加锁。''',

    121: '''**思路**：把裸 `int` 换成 `std::atomic<int>`，自增即为原子的读-改-写。

**参考实现**
```cpp
#include <atomic>
std::atomic<int> counter{0};

void increment() {
    ++counter;          // 原子自增
}
```

**要点**
- `atomic` 对单个变量的自增/取值无需锁，性能优于 `mutex`。
- 别写 `counter = counter + 1;`——那是「读 + 写」两步，整体不再是原子的。''',

    122: '''**思路**：用带谓词的 `wait` 等待条件成立；改变条件后 `notify_one` 唤醒对端。

**参考实现**
```cpp
void push(int v) {
    std::unique_lock<std::mutex> lock(m_);
    cv_.wait(lock, [this] { return !has_; });   // 有空间才继续
    value_ = v;
    has_ = true;
    cv_.notify_one();
}
int pop() {
    std::unique_lock<std::mutex> lock(m_);
    cv_.wait(lock, [this] { return has_; });    // 有值才继续
    has_ = false;
    cv_.notify_one();
    return value_;
}
```

**要点**
- 带谓词的 `wait` 等价于「while(!谓词) wait;」——能防**虚假唤醒**（spurious wakeup）。
- 条件变量必须配 `unique_lock`（`wait` 内部要临时解锁/重锁）；普通 `lock_guard` 不够。''',

    123: '''**思路**：`mutex` 保护 `deque`，`try_pop` 空队列返回 false（非阻塞）。

**参考实现**
```cpp
void push(int v) {
    std::lock_guard<std::mutex> lock(m_);
    q_.push_back(v);
}
bool try_pop(int& out) {
    std::lock_guard<std::mutex> lock(m_);
    if (q_.empty()) return false;
    out = q_.front();
    q_.pop_front();
    return true;
}
size_t size() const {
    std::lock_guard<std::mutex> lock(m_);
    return q_.size();
}
```

**要点**
- 用 `deque` 而非 `vector`：头部 `pop_front` 是 O(1)，`vector` 要搬元素。
- `size()` 常量方法里也要加锁 ⇒ `m_` 需 `mutable`。''',

    124: '''**思路**：`mutex` + `vector`；`drain` 用 `swap` 把整块缓冲「换走」，O(1) 清空。

**参考实现**
```cpp
void append(const std::string& line) {
    std::lock_guard<std::mutex> lock(m_);
    lines_.push_back(line);
}
std::vector<std::string> drain() {
    std::lock_guard<std::mutex> lock(m_);
    std::vector<std::string> out;
    out.swap(lines_);       // 交换指针，O(1) 清空原缓冲
    return out;
}
size_t size() const {
    std::lock_guard<std::mutex> lock(m_);
    return lines_.size();
}
```

**要点**
- `swap` 比「拷贝出来再 `clear`」高效得多（只换内部指针）。
- 收集日志的典型模式：多线程 `append`，单线程定时 `drain` 落盘。''',

    59: '''**正确答案：B（数据竞争，结果未定义）**。

`counter++` 不是原子操作——它被拆成「读 → 加 1 → 写回」三步。两个线程交错执行时可能互相覆盖，最终值**小于**期望，甚至行为未定义。

修复：用 `std::atomic<int>` 或 `std::mutex` 保护。''',

    60: '''**正确答案：B（可能死锁）**。

线程 1 拿 `a` 等 `b`，线程 2 拿 `b` 等 `a` —— 若两边刚好各持一把再申请另一把，就形成**循环等待**，互相卡死。

修复：**所有线程按同一顺序加锁**（如都用 `a`→`b`），或用 `std::lock` 一次锁住多把。这是死锁四条件里的「循环等待」，打破其一即可。''',

    61: '''**正确答案：B（`std::atomic`）**。

对单个变量的简单自增，`std::atomic<int>` 用硬件原子指令实现，无需加锁、无上下文切换开销——比 `mutex` 轻量得多。

裸 `int` 会数据竞争。选型原则：单变量原子操作用 `atomic`；要保护「多步不变量」再用 `mutex`。''',

    62: '''**应填：`lock_guard`**。

`std::lock_guard<std::mutex> lock(m);` 构造时加锁、离开作用域时自动解锁（RAII）。即使临界区里抛异常也能正确解锁。

需要手动 `unlock`/`lock` 或用条件变量时，改用 `std::unique_lock`。''',

    63: '''**应填：`wait`**。

`cv.wait(lock, 谓词)` 先检查谓词，为假才阻塞；被唤醒后**再次检查谓词**。这种「带谓词的等待」能防止**虚假唤醒**导致的错误。

醒来时保证谓词为真、且持有锁。''',

    64: '''**应填：`atomic`**。

`std::atomic<int> counter{0};` 的读、写、自增都是原子操作，多线程下无需加锁。

相比 `mutex`，`atomic` 更轻（无系统调用），适合计数器、标志位等单变量场景。''',

    # ================= C10 · 网络编程 =================
    135: '''**思路**：帧 = 4 字节**大端**长度前缀 + payload。解析时先读长度头，再按长度取 payload，不足一帧的留在缓冲里。

**参考实现**
```cpp
std::string encode_frame(const std::string& payload) {
    std::string frame;
    uint32_t len = static_cast<uint32_t>(payload.size());
    frame.push_back(static_cast<char>((len >> 24) & 0xFF));
    frame.push_back(static_cast<char>((len >> 16) & 0xFF));
    frame.push_back(static_cast<char>((len >> 8) & 0xFF));
    frame.push_back(static_cast<char>(len & 0xFF));
    frame += payload;
    return frame;
}

std::vector<std::string> parse_frames(const std::string& buffer) {
    std::vector<std::string> frames;
    std::size_t pos = 0;
    while (buffer.size() - pos >= 4) {
        uint32_t len = (static_cast<uint8_t>(buffer[pos])     << 24) |
                       (static_cast<uint8_t>(buffer[pos + 1]) << 16) |
                       (static_cast<uint8_t>(buffer[pos + 2]) << 8)  |
                        static_cast<uint8_t>(buffer[pos + 3]);
        if (buffer.size() - pos - 4 < len) break;   // 不足一帧，等下次
        frames.push_back(buffer.substr(pos + 4, len));
        pos += 4 + len;
    }
    return frames;
}
```

**要点**
- 大端 = 高位字节在前；解析时务必用 `uint8_t` 转换，避免 `char` 有符号导致的**符号扩展**。
- 「粘包/拆包」靠长度前缀解决：一次 recv 可能拿到半帧或多帧，靠缓冲累积 + 长度切分。''',

    136: '''**思路**：找第一个 `:` 切分 key/value，两边各做 `trim`。

**参考实现**
```cpp
static std::string trim(const std::string& s) {
    std::size_t b = s.find_first_not_of(" \\t\\r\\n");
    if (b == std::string::npos) return "";
    std::size_t e = s.find_last_not_of(" \\t\\r\\n");
    return s.substr(b, e - b + 1);
}

std::pair<std::string, std::string> parse_line(const std::string& line) {
    std::size_t pos = line.find(':');
    if (pos == std::string::npos) return { trim(line), "" };
    return { trim(line.substr(0, pos)), trim(line.substr(pos + 1)) };
}
```

**要点**
- 只按**第一个** `:` 切分（value 里可能还有冒号）。
- `trim` 用 `find_first_not_of` / `find_last_not_of` 定位有效字符区间，比手写循环简洁。''',

    137: '''**思路**：逐字节 `read` 直到 `\\n`；边读边写回；`read` 返回 ≤0 视为 EOF/出错。

**参考实现**
```cpp
bool echo_once(int fd) {
    char c;
    while (true) {
        ssize_t n = read(fd, &c, 1);
        if (n <= 0) return false;          // EOF 或出错
        if (write(fd, &c, 1) != 1) return false;
        if (c == '\\n') return true;
    }
}
```

**要点**
- `read` 返回 0 = 对端关闭（EOF），返回 -1 = 出错。
- 逐字节读能天然处理「短读」；真实代码可用缓冲批量读 + 自己按 `\\n` 切。''',

    138: '''**思路**：`make_response` 按约定拼串；`parse_status` 从首行 `STATUS <n>` 里解析数字。

**参考实现**
```cpp
std::string make_response(int status, const std::string& body) {
    return "STATUS " + std::to_string(status) + "\\n\\n" + body;
}

int parse_status(const std::string& response) {
    const std::string prefix = "STATUS ";
    if (response.compare(0, prefix.size(), prefix) != 0) return -1;
    std::size_t i = prefix.size();
    int n = 0;
    while (i < response.size() && response[i] >= '0' && response[i] <= '9')
        n = n * 10 + (response[i++] - '0');
    return n;
}
```

**要点**
- 手写数字解析避免依赖 `stoi` 的异常；也可用 `std::stoi(response.substr(7))`。
- 协议里「状态码 + 空行 + 正文」是 HTTP 的简化版：空行 `\\n\\n` 分隔头与体。''',

    139: '''**思路**：循环读「4 字节长度头 → payload」，原样写回。读/写都要循环补满，EOF 退出。

**参考实现**
```cpp
static bool read_full(int fd, char* buf, std::size_t n) {
    std::size_t got = 0;
    while (got < n) {
        ssize_t r = read(fd, buf + got, n - got);
        if (r <= 0) return false;
        got += static_cast<std::size_t>(r);
    }
    return true;
}

void handle_connection(int fd) {
    char header[4];
    while (read_full(fd, header, 4)) {
        uint32_t len = (static_cast<uint8_t>(header[0]) << 24) |
                       (static_cast<uint8_t>(header[1]) << 16) |
                       (static_cast<uint8_t>(header[2]) << 8)  |
                        static_cast<uint8_t>(header[3]);
        std::string payload(len, '\\0');
        if (len && !read_full(fd, &payload[0], len)) break;

        std::string out = std::string(header, 4) + payload;
        std::size_t sent = 0;
        while (sent < out.size()) {
            ssize_t w = write(fd, out.data() + sent, out.size() - sent);
            if (w <= 0) return;
            sent += static_cast<std::size_t>(w);
        }
    }
}
```

**要点**
- `read`/`write` 都可能**短读/短写**：必须循环到读满/写满，别假设一次调用就完成。
- 长度头先收全 4 字节，再按 `len` 收 payload——这是所有长度前缀协议的核心循环。''',

    65: '''**正确答案：B（TCP）**。

TCP 提供**可靠、有序、面向连接**的字节流：丢包重传、乱序重排、拥塞控制都由协议栈保证。

UDP 是「发出去就不管」的数据报，快但不可靠、不保证顺序。要「可靠有序」选 TCP；要低延迟、可容忍丢包（如音视频、游戏帧同步）才考虑 UDP。''',

    66: '''**正确答案：B（任意 1–100 字节）**。

TCP 是**字节流**，没有消息边界。`recv(fd, buf, 100)` 可能只返回 1 字节、也可能返回 100 字节——取决于内核缓冲和对端发送节奏。

这就是「**粘包/拆包**」的根源。应用层必须自己定协议（如长度前缀）来切分消息，不能假设「一次 recv = 一条消息」。''',

    67: '''**正确答案：A（大小端字节序转换）**。

不同 CPU 存储多字节整数的字节序不同（x86 是小端，网络协议约定是**大端**）。直接发 `int` 的原始字节，对端可能解析出错误的数。

用 `htons`/`htonl`（主机→网络）与 `ntohs`/`ntohl`（网络→主机）做转换，保证跨平台一致。''',

    68: '''**应填：`socket`**。

`int fd = socket(AF_INET, SOCK_STREAM, 0);` —— `AF_INET` 是 IPv4，`SOCK_STREAM` 是 TCP（面向字节流），返回文件描述符 `fd`。

失败返回 -1。UDP 用 `SOCK_DGRAM`。''',

    69: '''**应填：`htons`**。

`uint16_t p = htons(port);` —— 「host to network short」：把 16 位端口从主机字节序转成网络字节序（大端）。

`htons` 用于 16 位（端口），`htonl` 用于 32 位（IPv4 地址）。''',

    70: '''**应填：`listen`**。

`listen(fd, 128);` —— 把 socket 转为被动监听状态，第二个参数是**连接队列（backlog）**上限。

之后用 `accept` 取出已建立的连接。顺序：`socket → bind → listen → accept`。''',

    # ================= C11 · 数据库交互 =================
    140: '''**思路**：逐字符扫描，遇单引号补成两个、遇反斜杠补成两个。

**参考实现**
```cpp
std::string sql_escape(const std::string& s) {
    std::string out;
    out.reserve(s.size());
    for (char c : s) {
        if (c == '\\'') out += "''";
        else if (c == '\\\\') out += "\\\\\\\\";
        else out.push_back(c);
    }
    return out;
}
```

**要点**
- 「单引号转义成两个单引号」是 SQL 标准写法；反斜杠转义是 MySQL 的额外规则。
- **手写转义容易漏**（还有 `\\0`、`\\n`、注释符等）——生产环境务必用**参数化查询**（见 binder 那题）而不是自己拼。''',

    141: '''**思路**：遍历模板，遇 `?` 就取下一个参数，先转义再用单引号包起来。

**参考实现**
```cpp
static std::string esc(const std::string& s) {
    std::string o;
    for (char c : s) { if (c == '\\'') o += "''"; else o.push_back(c); }
    return o;
}

std::string bind_sql(const std::string& tmpl, const std::vector<std::string>& params) {
    std::string out;
    std::size_t pi = 0;
    for (char c : tmpl) {
        if (c == '?' && pi < params.size()) {
            out += '\\'';
            out += esc(params[pi++]);
            out += '\\'';
        } else {
            out.push_back(c);
        }
    }
    return out;
}
```

**要点**
- 真实数据库的预处理语句是「SQL 结构与数据分离」：`?` 由驱动绑定，**数据永远不被当成 SQL 解析**——比手工转义更安全。
- 本题演示的是「绑定的思想」；参数用尽或多余都要有约定（这里多余的 `?` 原样保留）。''',

    142: '''**思路**：用 `vector` 存空闲连接编号，加锁实现 acquire/release。

**参考实现**
```cpp
ConnectionPool(int size) {
    for (int i = 0; i < size; ++i) free_.push_back(i);
}
int acquire() {
    std::lock_guard<std::mutex> lock(m_);
    if (free_.empty()) return -1;
    int id = free_.back();
    free_.pop_back();
    return id;
}
void release(int id) {
    std::lock_guard<std::mutex> lock(m_);
    free_.push_back(id);
}
```

**要点**
- 连接池把「建立/销毁连接」的昂贵开销摊到多次复用上，是服务端必备。
- 生产实现还要处理：连接超时、坏连接剔除、最大等待（`acquire` 阻塞而非返回 -1）。''',

    143: '''**思路**：`set` 前把旧值记进 undo 日志；`rollback` 倒序恢复。

**参考实现**
```cpp
void begin() { in_tx_ = true; undo_.clear(); }
void set(const std::string& k, const std::string& v) {
    if (in_tx_) {
        auto it = store_.find(k);
        undo_.push_back({ k, it == store_.end() ? std::string() : it->second });
    }
    store_[k] = v;
}
void commit() { undo_.clear(); in_tx_ = false; }
void rollback() {
    for (auto it = undo_.rbegin(); it != undo_.rend(); ++it) {
        if (it->second.empty()) store_.erase(it->first);   // 原本不存在
        else store_[it->first] = it->second;
    }
    undo_.clear();
    in_tx_ = false;
}
```

**要点**
- undo 日志记录「旧值」，回滚时**倒序**重放，才能正确撤销同一 key 的多次修改。
- 用空串表示「原本不存在」是个简化（真实系统会用「存在标志位」区分空值）；这里以最小实现表达事务原子性。''',

    144: '''**思路**：DAO 用 `map` 存数据；事务期把「被改动的旧状态」记进 undo，`rollback` 倒序恢复。

**参考实现**
```cpp
bool insert(int id, const std::string& name) {
    if (store_.count(id)) return false;
    if (in_tx_) undo_.push_back({ id, "" });   // "" 表示「原本不存在」
    store_[id] = name;
    return true;
}
std::string find(int id) {
    auto it = store_.find(id);
    return it == store_.end() ? "" : it->second;
}
bool update(int id, const std::string& name) {
    auto it = store_.find(id);
    if (it == store_.end()) return false;
    if (in_tx_) undo_.push_back({ id, it->second });
    it->second = name;
    return true;
}
bool remove(int id) {
    auto it = store_.find(id);
    if (it == store_.end()) return false;
    if (in_tx_) undo_.push_back({ id, it->second });
    store_.erase(it);
    return true;
}
void begin() { in_tx_ = true; undo_.clear(); }
void commit() { undo_.clear(); in_tx_ = false; }
void rollback() {
    for (auto it = undo_.rbegin(); it != undo_.rend(); ++it) {
        if (it->second.empty()) store_.erase(it->first);  // insert 的撤销
        else store_[it->first] = it->second;              // update/remove 的撤销
    }
    undo_.clear();
    in_tx_ = false;
}
```

**要点**
- DAO 模式：把「数据访问」封装在类里，业务层只管调 `insert/find/update/remove`。
- 三种改动的撤销统一成「旧值空串 ⇒ 删除，否则恢复」——又一次用倒序 undo 日志实现原子回滚。
- 生产版应把 `map` 换成真实连接 + 预处理语句（见 C11 前几题）。''',

    71: '''**正确答案：B（SQL 注入）**。

把用户输入直接拼进 SQL 字符串，攻击者可构造 `' OR '1'='1`、`'; DROP TABLE ...` 之类输入，篡改查询语义、窃取或破坏数据。

防御：**参数化查询**（预处理语句，`?` 占位符）——让数据与 SQL 结构分离，输入永远不被当代码执行。''',

    72: '''**正确答案：A（事务）**。

事务提供 **ACID**：一组操作要么全部成功（commit）、要么全部回滚（rollback），保证原子性。

典型场景：转账——扣款与加款必须同生共死；只用普通语句写，中途失败会留下「半边账」。''',

    73: '''**正确答案：A（频繁建立/销毁连接的开销）**。

建立数据库连接要 TCP 握手 + 认证，开销大且耗时。连接池预先建好一批连接**复用**，用完归还而非关闭，显著提升吞吐、降低延迟。

它同时能限制并发连接数，起到保护数据库的作用。''',

    74: '''**应填：`?`**。

`?` 是预处理语句的**位置占位符**。`prepare("... WHERE id = ?")` 只编译一次 SQL 结构，再用 `bind`/`execute` 传入参数——数据不参与 SQL 解析，从根本上杜绝注入。

（不同驱动也有 `:name` 命名占位符，但 `?` 最通用。）''',

    75: '''**应填：`commit`**。

`conn.commit();` 提交当前事务——把本次事务内的所有改动**永久写入**数据库。

提交前若出错则用 `rollback` 撤销，二者是事务的两种终局。''',

    76: '''**应填：`rollback`**。

`conn.rollback();` 回滚当前事务——把本次事务内的所有改动**全部撤销**，回到事务开始前的状态。

典型用法：捕获异常后 rollback，保证不留下「半完成」的脏数据。''',
    # ================= C12 · constexpr 与编译期计算 =================
    125: '''**思路**：`constexpr` 递归阶乘，`n <= 1` 作出口。

**参考实现**
```cpp
constexpr int factorial(int n) {
    return n <= 1 ? 1 : n * factorial(n - 1);
}
```

**要点**
- `constexpr` 函数既可在编译期求值（作数组大小、`static_assert`），也可运行期调用。
- C++14 起 constexpr 函数体内允许局部变量、循环、多返回。''',

    126: '''**思路**：`constexpr` 斐波那契，直接按定义递归。

**参考实现**
```cpp
constexpr int fib(int n) {
    return n <= 1 ? n : fib(n - 1) + fib(n - 2);
}
```

**要点**
- 编译期求值有**步数上限**（编译器限制 constexpr 求值步数），大 `n` 会超限报错。
- 生产场景的快速 Fibonacci 应用迭代或编译期查表（见本章 Boss）。''',

    127: '''**思路**：`constexpr` 平方；结果直接用于编译期上下文。

**参考实现**
```cpp
constexpr int square(int x) { return x * x; }

// 使用：int arr[square(3)];  // 大小为 9
```

**要点**
- 只有 `constexpr` 函数在「常量表达式」上下文里才会**编译期求值**；否则可能退化为运行期调用。
- 编译期求值的证明：能通过 `static_assert(square(3) == 9);`。''',

    128: '''**思路**：C++14 起 constexpr 函数可用循环，逐项填充 `std::array`。

**参考实现**
```cpp
constexpr std::array<int, 10> make_square_table() {
    std::array<int, 10> a{};
    for (int i = 0; i < 10; ++i) a[i] = i * i;
    return a;
}
```

**要点**
- 返回 `std::array` 可整体作编译期常量（`constexpr auto t = make_square_table();`）。
- C++14 起 constexpr 支持 `for`/`if`/局部变量——不再需要 C++11 的「单表达式」限制。''',

    129: '''**思路**：constexpr 阶乘 + constexpr 循环生成表，可再用 `static_assert` 校验。

**参考实现**
```cpp
constexpr int factorial(int n) {
    return n <= 1 ? 1 : n * factorial(n - 1);
}

constexpr std::array<int, 10> make_factorial_table() {
    std::array<int, 10> a{};
    for (int i = 0; i < 10; ++i) a[i] = factorial(i);
    return a;
}

// 编译期验证
static_assert(make_factorial_table()[5] == 120);
```

**要点**
- 整张表在编译期算好，运行期零开销查表。
- 注意 `9! = 362880`，仍在 `int` 范围内（`13!` 才会溢出）。''',

    77: '''**正确答案：A（9）**。

`constexpr int square(int)` 在**常量表达式上下文**里编译期求值，所以 `square(3)` 就是编译期常量 `9`，可直接当数组大小。

可见 constexpr 函数让「编译期计算」变成写普通函数即可，无需模板元编程那套。''',

    78: '''**正确答案：A（编译错误）**。

`consteval`（C++20）声明的是「**立即函数**」：**每一次调用都必须在编译期求值**。`f(y)` 里的 `y` 是运行时变量，无法编译期取值 ⇒ 编译错误。

对比 `constexpr`：后者「能编译期就编译期，否则运行期」；`consteval` 强制编译期，不满足即报错。''',

    79: '''**正确答案：A**。

`constinit`（C++20）要求变量**在编译期完成初始化**，否则编译报错。它用来消除「**静态初始化顺序问题**」（SIOF）：不同编译单元的全局对象初始化顺序不确定，constinit 能让关键全局量提前、确定地初始化好。

注意：`constinit` 只约束**初始化时机**，不表示变量不可变（那是 `const`）。''',

    80: '''**应填：`constexpr`**。

`constexpr int square(int x) { return x * x; }` 声明函数**可用于常量表达式**——既能在编译期求值，也能运行期调用。

它是 C++11 起的核心编译期计算工具。''',

    81: '''**应填：`consteval`**。

`consteval int f(int x) { return x * 2; }`（C++20）声明**立即函数**：每次调用都必须在编译期求值，否则编译错误。

适合「只能编译期用」的场景（如生成编译期常量、模板参数）。''',

    82: '''**应填：`constinit`**。

`constinit int g = 42;`（C++20）保证 `g` 在**编译期完成初始化**，从而避免运行时初始化顺序问题；但 `g` 仍可变。

`constinit` ≠ `const`：前者管「何时初始化」，后者管「能不能改」。''',

    # ================= C13 · C++20 高级特性 =================
    145: '''**思路**：`requires` 表达式列出「必须合法的表达式」；用 concept 约束模板参数。

**参考实现**
```cpp
template <typename T>
concept Addable = requires(T a, T b) {
    a + b;                              // 要求 a + b 合法
};

template <Addable T>
T add(T a, T b) { return a + b; }
```

**要点**
- `requires(T a, T b){ a + b; }` 是「要求某个表达式能编译」；不满足时模板**不参与**重载、并给出可读错误。
- `template <Addable T>` 是「约束模板参数」的简写，等价于 `template <typename T> requires Addable<T>`。
- 想再约束返回类型可写 `{ a + b } -> std::convertible_to<T>;`。''',

    146: '''**思路**：C++20 的三路比较可**一行 `= default`** 搞定全部比较运算符。

**参考实现**
```cpp
#include <compare>

struct Version {
    int major = 0;
    int minor = 0;
    int patch = 0;

    auto operator<=>(const Version&) const = default;
};
```

**要点**
- `= default` 的三路比较按成员**字典序**（先 `major`、再 `minor`、后 `patch`）生成 `< <= > >=`；同时隐式生成 `==`/`!=`。
- 一个 `<=>` 顶替了过去要手写的 6 个比较运算符。''',

    147: '''**思路**：用 `views::filter` + `views::transform` 组成惰性管道，物化成 `vector`。

**参考实现**
```cpp
std::vector<int> even_doubled(const std::vector<int>& in) {
    auto view = in
        | std::views::filter([](int x) { return x % 2 == 0; })
        | std::views::transform([](int x) { return x * 2; });
    return std::vector<int>(view.begin(), view.end());
}
```

**要点**
- views **惰性**：`|` 只是搭管道，真正计算发生在遍历（构造 vector）时。
- 好处：不产生中间容器、可组合；`filter` 只在需要时对元素求值。''',

    148: '''**思路**：concept 约束元素类型；`views::transform` 平方后 `accumulate` 求和，初始值用元素类型。

**参考实现**
```cpp
template <typename T>
concept Arithmetic = std::is_arithmetic_v<T>;

template <std::ranges::input_range R>
    requires Arithmetic<std::ranges::range_value_t<R>>
auto sum_of_squares(const R& r) {
    auto sq = std::views::transform(r, [](auto x) { return x * x; });
    using T = std::ranges::range_value_t<R>;
    return std::accumulate(sq.begin(), sq.end(), T{0});
}
```

**要点**
- 用 `std::ranges::range_value_t<R>` 拿到元素类型，并用 `T{0}` 作累加初值——避免对 `double` 范围误用 `int(0)` 丢精度。
- `requires` 子句让「不满足条件的类型」直接编译报错，而不是给出天书般的模板错误。''',

    149: '''**思路**：`filter | transform | take` 三段管道，最后物化为 `vector<long long>`。

**参考实现**
```cpp
template <std::ranges::input_range R>
    requires std::integral<std::ranges::range_value_t<R>>
std::vector<long long> positive_squares(const R& r, std::size_t n) {
    auto view = r
        | std::views::filter([](auto x) { return x > 0; })
        | std::views::transform([](auto x) { return static_cast<long long>(x) * x; })
        | std::views::take(n);
    return std::vector<long long>(view.begin(), view.end());
}
```

**要点**
- `take(n)` 只取前 n 个——得益于惰性求值，不会先算完整个 range。
- 用 `long long` 存平方，降低溢出风险；`std::integral` 约束保证元素是可比较的整数。''',

    83: '''**正确答案：A（编译错误）**。

`add` 被 concept `Numeric`（要求 `std::is_arithmetic_v<T>`）约束，而 `const char*` 不是算术类型 ⇒ 不满足约束 ⇒ `add("a","b")` 无法实例化，**编译错误**。

这正是 concept 的价值：把「类型不合适」的错误提前、并给出可读提示，而不是长篇模板报错。''',

    84: '''**正确答案：B（惰性求值）**。

`v | views::filter(f) | views::transform(g)` 只是**构建视图（view）**，不立即计算；只有真正**遍历**它（如构造 `vector`、`for` 循环）时，元素才逐个经过 filter/transform 计算。

好处：零中间容器、可组合、可在 `take` 等短路操作下提前结束。''',

    85: '''**正确答案：A**。

`co_yield` 在协程里**产出一个值并挂起**，把控制权交回调用方；下次恢复时从挂起点继续。它是「生成器（generator）」的核心——可按需惰性产出序列，而不是一次算完。

同族关键字：`co_await`（等待异步操作）、`co_return`（结束协程并返回）。''',

    86: '''**应填：`concept`**。

`template <typename T> concept Numeric = std::is_arithmetic_v<T>;` 定义一个命名约束，之后可写 `template <Numeric T>` 或 `requires Numeric<T>` 来使用。

concept 让模板约束可复用、可组合、可读，替代了以往 `enable_if` 那套晦涩写法。''',

    87: '''**应填：`requires`**。

`template <typename T> requires std::integral<T> void f(T t);` —— `requires` 子句给模板加约束，只有满足 `std::integral<T>` 的类型才能实例化 `f`。

也可写成简写形式 `template <std::integral T> void f(T t);`，语义等价。''',

    88: '''**应填：`co_yield`**。

协程生成器里用 `co_yield value;` **产出一个值并挂起**，调用方取到值后可再次恢复执行。

它是三种协程关键字之一（`co_await` / `co_yield` / `co_return`），常用于惰性序列、异步流。''',

    # ================= C14 · 模块与工程实践 =================
    150: '''**思路**：把相关常量放进命名空间，用 `config::` 前缀访问。

**参考实现**
```cpp
namespace config {
    constexpr int kMaxConnections = 100;
    constexpr const char* kAppName = "crow-blog";
    constexpr bool kDebug = false;
}
```

**要点**
- 命名空间隔离避免全局污染；调用处写 `config::kMaxConnections`。
- C++11 起 `constexpr` 变量隐含 `const`，且可作编译期常量；`k` 前缀是常见的常量命名约定。''',

    151: '''**思路**：Meyers 单例——函数内 `static` 局部对象，首次调用时初始化，天然线程安全。

**参考实现**
```cpp
Config& get_config() {
    static Config instance;
    return instance;
}
```

**要点**
- C++11 起，函数内 `static` 局部变量的初始化是**线程安全**的（编译器加锁保证只初始化一次）。
- 返回引用保证「全局唯一」；相比全局对象，还具备**按需初始化**、无静态初始化顺序问题。''',

    152: '''**思路**：抽象基类 + 派生类重写 `area`；工厂返回 `unique_ptr<Shape>`。

**参考实现**
```cpp
struct Circle : Shape {
    double r_;
    explicit Circle(double r) : r_(r) {}
    double area() const override { return 3.141592653589793 * r_ * r_; }
};

struct Square : Shape {
    double s_;
    explicit Square(double s) : s_(s) {}
    double area() const override { return s_ * s_; }
};

std::unique_ptr<Shape> make_shape(const std::string& kind, double x) {
    if (kind == "circle") return std::make_unique<Circle>(x);
    if (kind == "square") return std::make_unique<Square>(x);
    return nullptr;
}
```

**要点**
- 工厂返回**基类**智能指针：调用方只依赖 `Shape` 接口，新增形状不必改调用代码。
- `virtual ~Shape() = default;` 保证经基类指针删除时正确析构（避免 UB）。''',

    153: '''**思路**：`Logger` 接口 + 两种实现；`do_work` 只依赖抽象（依赖注入）。

**参考实现**
```cpp
struct ConsoleLogger : Logger {
    void log(const std::string& msg) override {
        std::printf("%s\\n", msg.c_str());
    }
};

struct BufferedLogger : Logger {
    std::vector<std::string> lines_;
    void log(const std::string& msg) override { lines_.push_back(msg); }
    const std::vector<std::string>& lines() const { return lines_; }
};

void do_work(Logger& logger) {
    logger.log("start");
    logger.log("done");
}
```

**要点**
- `do_work` 依赖抽象的 `Logger&`（**依赖注入**），实现可互换：生产用 `ConsoleLogger`，测试注入 `BufferedLogger` 后断言 `lines()`。
- 让「业务逻辑」与「具体输出方式」解耦——这是可测试性与可扩展性的关键。''',

    154: '''**思路**：把本章五种手法拼起来——命名空间、接口、单例、工厂、依赖注入。

**参考实现**
```cpp
namespace app { constexpr int kVersion = 3; }

class ConsoleReporter : public Reporter {
public:
    void report(int value) override { std::printf("value=%d\\n", value); }
};

class CaptureReporter : public Reporter {
    std::vector<int> values_;
public:
    void report(int value) override { values_.push_back(value); }
    const std::vector<int>& values() const { return values_; }
};

class Counter {
    int n_ = 0;
public:
    void increment() { ++n_; }
    int value() const { return n_; }
};
Counter& counter() { static Counter c; return c; }

std::unique_ptr<Reporter> make_reporter(bool capture) {
    if (capture) return std::make_unique<CaptureReporter>();
    return std::make_unique<ConsoleReporter>();
}

void run_once(Reporter& r) {
    counter().increment();
    r.report(counter().value());
}
```

**要点**
- 命名空间 `app` 隔离常量；`Reporter` 抽象 + 两实现 + 工厂 + 单例 `counter()` 组合成一个「迷你库」。
- `run_once` 通过注入的 `Reporter&` 上报——测试里注入 `CaptureReporter` 即可断言上报序列（`1,2`）。''',

    89: '''**正确答案：A（编译隔离）**。

`module`（C++20）把接口与实现分离、只在导入处**编译一次**并缓存，带来：避免头文件被反复解析、**宏不泄漏**（模块不传播宏）、符号可见性明确。

它主要解决的是**编译期问题**（编译速度、隔离性），而非运行速度。''',

    90: '''**正确答案：A（链接错误：多重定义）**。

C++ 的 **ODR（单一定义规则）** 要求：同一非 `inline` 函数在**整个程序**中只能有一个定义。若多个编译单元各自定义了同名非 inline 函数，链接器会报「multiple definition」。

修复：把定义放到**一个** `.cpp`，其余用声明；或加 `inline`；或（C++17）用 `inline` 变量 / 匿名命名空间限制作用域。''',

    91: '''**正确答案：A（include guard 或 #pragma once）**。

经典做法是 **include guard**：`#ifndef FOO_H / #define FOO_H / ... / #endif`；现代编译器普遍支持更简洁的 **`#pragma once`**。

两者都防止**同一编译单元内**头文件被重复展开导致的重定义错误。''',

    92: '''**应填：`export`**。

`export module math;` 声明模块 `math` 的**接口**；想导出的实体写 `export int add(int,int);`，未 `export` 的默认只在模块内部可见。

这是 C++20 模块的关键字（注意与旧标准里被废弃的 `export` 模板用法无关）。''',

    93: '''**应填：`import`**。

`import math;` 导入模块，即可使用其导出实体。相比 `#include`，导入不展开源码、不传播宏、编译更快。

`import` 也是「消费」模块的唯一方式——模块之间同样用 `import` 组合。''',

    94: '''**应填：`#endif`**。

include guard 以 `#endif` 收尾：

```cpp
#ifndef FOO_H
#define FOO_H
// 内容
#endif   // FOO_H
```

`#endif` 后建议加注释标出对应的宏名，便于阅读。等价替代是现代编译器广泛支持的 `#pragma once`。''',

    155: '''**正确答案：B（`list::insert` 到别处）。**

四个选项逐个拆开：

| 操作 | 迭代器 | 引用/指针 | 原因 |
|---|---|---|---|
| `vector::push_back` 触发重新分配 | 全失效 | 也失效 | 元素被搬到新内存，旧对象已销毁 |
| `list::insert` 到别的位置 | **不受影响** | 不受影响 | 只改链表指针，节点地址不变 |
| `vector::erase(v.begin())` | 被删位置及之后全失效 | 失效 | 后面的元素整体前移 |
| `unordered_map` 触发 rehash | 全失效 | 仍有效 | 桶数组重建，节点本身没动 |

**可迁移规则**：`list` / `map` / `set` 这类**节点容器**，插入不动已有节点；`vector` / `deque` / `unordered_*` 这类**连续或按桶组织**的容器，结构一变就要重新获取句柄。''',

    156: '''**正确答案：B —— `v[0]` 是 1，而且这是未定义行为。**

题目里的 `reserve(3)` 是为了把条件钉死：容量正好 3，`push_back(4)` **必然**重新分配。（不写 `reserve` 的话，`v{1, 2, 3}` 的初始容量由实现决定，可能本来就够用，这题的前提就不成立了。）

`push_back` 触发重新分配时，`vector` 会把元素**搬**到新内存，再销毁旧内存上的对象。`r` 仍然指着旧内存那块地址——它已经归还给分配器了。

`r = 99` 往这块死内存里写：**不报错、不崩溃**，因为它只是一次普通的内存写。这是最难抓的一类 bug：

- 跑一万次都"正常"，因为那块内存还没被别的对象复用；
- 上线后换个分配器、加行日志、改个优化等级，就变成随机的数据错乱或崩溃。

**可迁移规则**：只要容器可能重新分配（`push_back` / `resize` / `reserve` / `insert`），跨越该操作保存的**任何**句柄——迭代器、引用、指针——都必须在操作之后重新获取。

顺带一句：标准规定 `vector` 扩容会让所有引用、指针、迭代器失效，而 `deque::push_front` 和 `unordered_map` 的 rehash **不**失效引用——见下一题。''',

    157: '''**正确答案：B（`deque::push_front`）。**

标准其实区分了两种"失效"：**句柄失效**（迭代器不能用了）和**元素失效**（对象被销毁或搬家了）。大多数人默认两者同步，实际不是。

| 操作 | 迭代器 | 引用/指针 | 原因 |
|---|---|---|---|
| `vector` 扩容 | 全失效 | **也失效** | 元素被 move 到新内存，旧对象销毁 |
| `deque::push_front` | **全失效** | **仍有效** | 两端插入不动已有元素，只重建内部段表 |
| `unordered_map` rehash | 全失效 | **仍有效** | 只重建桶数组，节点地址不变 |
| `list::erase(e)` | 只有被删的那个 | 该元素真没了 | 元素本身被销毁 |

关键一句：**迭代器失效 ≠ 元素失效**。失效的是"指向元素的方式"，不是元素本身。

**可迁移规则**：判断危险时先问"对象搬家了没 / 被销毁了没"，再问"迭代器还能不能用"。`deque` 和 `unordered_map` 就是"句柄死了、对象还活着"的两个经典反例。''',

    158: '''**正确答案：C —— 仍然不安全，只是"看起来正常"。**

`list::erase(it)` 之后 `it` 已经失效，循环再执行 `++it` 就是对失效迭代器做自增，按标准依然是**未定义行为**。换成 `list` 并不能豁免。

那为什么很多人觉得 list 上这么写"没问题"？因为 `erase` 只是把那一个节点归还给分配器，节点里的 `next` 指针常常还留着原值、内存也常没被复用，所以 `++it` **恰好**能走到下一个节点。这是运气，不是保证。

这正是这类 bug 最难抓的地方：**能跑通 ≠ 合法**。同样的写法在 debug 版、ASan 版，或者内存压力大时会立刻现原形。

**可迁移规则**：任何容器里，`erase` 之后都要用返回值续接：

```cpp
for (auto it = c.begin(); it != c.end(); ) {
    if (pred(*it)) it = c.erase(it);   // 用返回值
    else ++it;
}
```

`list` / `map` / `set` 的 `erase` 从 C++11 起都返回下一个迭代器。''',

    159: '''**正确答案：C —— 能编译，但会越界读。**

先破一个常见误解：`deque` 确实没有 `data()`，但 `&d[0]` 是**完全合法**的——`operator[]` 返回引用，取地址自然合法。所以**编译期一点警告都没有**。

问题在于 `deque` 的内存是**分段连续**的：若干定长块，块与块之间靠一张"段表"串起来。`&d[0]` 拿到的是第一块里的地址，`d.size()` 是 3，`feed` 却按"连续 3 个 int"去读——一旦跨块，读到的就是块尾之外的无关内存。

**可迁移规则**：**"支持随机访问"不等于"内存连续"。**

- 随机访问 `O(1)`：`vector`、`deque`、`array`
- 内存连续（能安全 `data()` / `&c[0]` 交给 C API）：只有 `vector`、`array`、`string`

要把 `deque` 喂给 C 接口，只能先拷进一个 `vector`。''',

    160: '''**正确答案：B —— 不能用"跑过多少次"来验证。**

未定义行为不是"随机崩溃"，而是**标准不作任何承诺**。同一段代码的表现取决于：

- 内存布局与分配器状态（那块内存有没有被别人复用）
- 编译优化等级（优化器可能把整个循环删掉，也可能把读操作重排）
- 栈/堆初始内容、地址随机化、线程调度

所以"跑了 1000 次全过"只证明**这 1000 次的内存布局恰好没暴露问题**，跟代码是否正确没有关系。真实项目里最常见的剧本是：本地全绿、CI 全绿，上线换了个容器大小或并发度立刻出事。

**可迁移规则**：验证 UB 靠工具，不靠次数。

| 手段 | 抓什么 |
|---|---|
| `-fsanitize=address`（ASan） | 越界、use-after-free、悬垂引用 |
| `-fsanitize=undefined`（UBSan） | 有符号溢出、非法移位、空指针解引用 |
| `-D_GLIBCXX_DEBUG` | 标准库迭代器越界、失效迭代器使用 |

关掉优化重跑（C）没用——UB 的暴露与环境相关，不是"优化开关"这一个变量能控制的。''',

    161: '''**正确答案：`erase`。**

`vector::erase` 从 C++11 起**返回被删元素的下一个位置**，用它续接就能安全遍历：

```cpp
for (auto it = v.begin(); it != v.end(); ) {
    if (*it % 2 == 0) it = v.erase(it);   // 删掉，it 自动指向下一个
    else ++it;                            // 没删，才手动前进
}
```

三个易错点：

1. **删的分支不能再 `++it`** —— `erase` 已经把 `it` 移到下一个了，再自增会跳过元素；
2. **循环头不写 `++it`** —— 前进只能放在 `else` 分支里，这是这个惯用法的骨架；
3. `map` / `set` / `list` 同理，`erase` 都返回下一个迭代器。

**可迁移规则**：`erase` 的返回值就是"续接点"，永远别在 `erase` 之后手动自增。''',

    162: '''**答案**：① `move_if_noexcept` ② `~T` ③ `delete`。

**① 为什么故意不用 `std::move`？**
扩容过程中一旦某个元素的移动构造抛异常，已经搬过去的那批就变成"新内存一半、旧内存一半"的烂摊子，没法回滚。`move_if_noexcept` 的语义是：**只有当移动构造声明了 `noexcept` 才 move，否则退回拷贝**——拷贝失败的话原容器还完好无损。这是"强异常安全保证"的代价。

**② 为什么必须手写析构？**
`fresh` 那块内存来自 `::operator new`，是**原始内存**，上面只有 placement new 构造出来的对象。而 `::operator delete` 只归还内存、**不调析构**。所以必须先亲手把每个元素的析构跑一遍，否则元素持有的资源（`std::string` 的堆缓冲、`unique_ptr` 的对象……）全泄漏。

**③ 与 ② 的分工**：析构负责"对象死亡"，`::operator delete` 负责"内存归还"。标准库把这两件事拆开，才可能复用那块内存。

**这段代码就是「迭代器失效」的物理原因**
旧内存被 `::operator delete` 归还之后，之前保存的迭代器 / 引用 / 指针指向的是一块**已经不属于你的内存**。「选择 8」「选择 9」问的"为什么失效"，答案就在这三行里。

**可迁移规则**：写自己的容器时，「构造 / 析构 / 释放内存」是三件独立的事，漏掉任何一件都是 UB，而且通常不会立刻报错。''',

    163: '''**答案**：① `pos->prev` ② `after`。

**① 新节点的前驱是谁？**
`new node{prev, next, value}` 按声明顺序初始化，第一个字段就是 `prev`。新节点要插在 `pos` 之前，它的前驱自然是 `pos->prev`。

注意后面两行赋值的**顺序**：先 `pos->prev->next = n`，再 `pos->prev = n`。反过来的话，先把 `pos->prev` 覆盖成 `n`，原来的前驱就再也找不到了，链当场断掉。

**② 为什么 erase 要返回 after？**
`delete pos` 之后 `pos` 本身已经失效，调用方继续 `++pos` 就是 UB。返回删除前就存好的 `after`，循环才能安全续接——和「填空 4」（`it = c.erase(it)`）是同一个约定。

**关键：为什么 list 插入后老迭代器全都不失效？**
`insert` 只在堆上 `new` 了一个**新节点**，然后把 4 个指针改指向它，**所有既有节点的地址一个都没变**。list 的迭代器本质上就是"节点指针"，指针没变 ⇒ 迭代器继续有效。

对比 vector：扩容把元素搬到新内存、旧对象销毁 ⇒ 地址变了、对象也没了，所以全废。

**可迁移规则**：节点容器的"稳"来自**地址稳定**，连续容器的"脆"来自**会搬家**。判断失效时先问一句"这次操作会不会搬动已有元素"。''',

    164: '''**答案**：① `buckets_.size()`（写 `bucket_count()` 也对）② `next`。

**① 桶下标的本质**是 `hash(key) % 桶数`。取模保证结果落在 `[0, 桶数)`，这就是"桶"。同一个 key 每次算出来必须一样，否则 `insert` 存进去、`find` 就找不回来了——自定义哈希写成依赖时间/随机数，就是这种事故。

**② 链地址法**：一个桶里塞了多个 key 时，用单链表串起来，`find` 顺着 `next` 走到底。平均 O(1) 的前提是**桶数够多、分布够均匀**，否则退化成一条长链表（O(n)）。

**③ rehash 到底换掉了什么？**
只换掉 `buckets_` 这个**桶指针数组**：新建更大的数组，把每个节点按新桶数重新挂一遍，旧数组丢掉。

注意 `head->next = fresh[b]` 改的是 node 内部的 `next` 指针，**node 自身的地址一动没动**。于是：

- 迭代器失效：迭代器的实现依赖"当前在哪个桶、桶内到哪了"，桶数一变这套记录全作废；
- 引用/指针仍有效：它们指向 node 对象本身，node 还在原地。

这正是「选择 9」那条反直觉规则的源码级解释。

**可迁移规则**：`unordered_map` 的 rehash 是"重排索引、不搬对象"，`vector` 的扩容是"搬对象、换地址"。失效范围不同，根子就在这里。''',

    165: '''**答案**：① `left` ② `y` ③ `right`。

**左旋三步**（拿张纸画一遍最快）：

1. `x->right = y->left` —— y 的左子树"过继"给 x（它比 x 大、比 y 小，正好挂在 x 右边）；
2. `y` 顶替 `x` 的位置（父亲指针、祖父的左/右孩子指针全部改指向 y）；
3. `y->left = x; x->parent = y;` —— x 降为 y 的左孩子。

旋转之后**中序顺序必须不变**（`x` 依然在 `y` 前面），这是判断"转对了没"的唯一标准。

**③ 中序后继**：`++it` 的语义是"下一个更大的元素"。

- 有右子树 → 右子树里的**最小**节点（一路往左到底）；
- 没有右子树 → 往上爬，直到"我是我父亲的左孩子"，那个父亲就是后继。

**为什么均摊 O(1)**：单次 `++it` 最坏要爬 O(log n) 层，但在一次完整遍历里，**每条边最多被向上爬一次、向下走一次**。n 个节点的总爬升步数合计 O(n)，摊还到每次 `++` 就是 O(1)。这是摊还分析的经典例子，和 vector 倍增是同一套思路。

**可迁移规则**：看到"单次最坏 O(log n)、整体遍历却是 O(n)"，八成是每条边只被访问常数次——算复杂度要看**总步数**，别只盯单次。''',

    166: '''**答案**：① `sizeof(T)` ② `kBlock`。

**① 块大小按什么切**：按字节数切，`512 / sizeof(T)` 个元素。`T` 大块里就少放几个，`T` 小块里多放几个。⚠️ 这个 512 是 libstdc++ 的选择，**不是标准要求**，MSVC 和 libc++ 取值都不同——所以这一空答 `sizeof(T)` 才是唯一稳妥的（问的是"按什么切"，不是"切多少字节"）。

**② 两段式定位**：`pos / kBlock` 得块号，`pos % kBlock` 得块内偏移。这也是 deque 随机访问 O(1) 的原因——一次除法加一次取模，不用遍历。

**③ 为什么 `&d[0]` 不能当连续数组用？**
`map_[head_]` 给出的是一个块的起始地址，但 `d[0]` 的下一个元素可能在同一块里，也可能在**下一块**——而下一块跟这一块在内存里毫无关系。`feed(&d[0], n)` 按"连续 n 个元素"去读，跨块那一刻就开始读别人的内存。

**四种能力，三种容器，差别很大**：

| 能力 | vector | deque | list |
|---|---|---|---|
| 随机访问 O(1) | 是 | 是 | 否 |
| 内存连续（可传 C API） | 是 | 否 | 否 |
| 两端插入均摊 O(1) | 仅尾部 | 是 | 是 |
| 插入后老迭代器仍有效 | 否 | 否 | 是 |

**可迁移规则**：需要"连续内存"时只有 `vector` / `array` / `string` 三个选项。deque 的 `operator[]` 返回引用，取地址当然合法——**合法不等于连续**，这个坑编译期查不出来。''',

    167: '''**核心只有一句话**：`::operator new` 借来的是**字节**，不是**对象**。构造和析构都得你自己点名。

**扩容四步**（少一步就出问题）：

```cpp
void reserve(std::size_t n) {
    if (n <= cap_) return;
    T* fresh = static_cast<T*>(::operator new(n * sizeof(T)));   // ① 原始内存

    for (std::size_t i = 0; i < size_; ++i)                      // ② 搬过去（构造）
        new (fresh + i) T(std::move_if_noexcept(data_[i]));

    for (std::size_t i = 0; i < size_; ++i) data_[i].~T();        // ③ 销毁旧元素
    ::operator delete(data_);                                    // ④ 只归还字节

    data_ = fresh;
    cap_  = n;
}
```

**三个最容易错的地方**：

1. **用 `new T[n]` 拿内存**：它会构造 n 个元素，于是"容量"里全是活对象——测试里 `Tracked::alive` 会等于 capacity 而不是 size。这就是 `size` 与 `capacity` 在实现层面为什么必须分开：一个数"活了几个"，一个数"能放几个"。
2. **只 `delete[]` 不逐个析构**：`::operator delete` 不调析构函数，元素里持有的资源（`string` 的堆内存、文件句柄）全部泄漏。
3. **搬运用赋值而不是构造**：目标位置上是未初始化的字节，只能 placement new，不能 `fresh[i] = data_[i]`。

**`move_if_noexcept` 是干什么的**：T 的移动构造是 `noexcept` 时才真移动，否则退化成拷贝。理由很硬——移动途中抛异常，源对象已经被改了一半又没搬成功，原容器就废了；拷贝失败则源对象完好，可以直接把异常抛给调用者。`vector` 因此能给出**强异常保证**。

**这一关真正想让你记住的**：`&v[0]` 在扩容后变了。所有指向旧 buffer 的迭代器、指针、引用，从 `::operator delete` 那一行起就全部指向已释放内存——入门那几道「迭代器失效」的选择题，失效的**物理原因就是你刚刚亲手写下的这四步**。''',

    168: '''**核心只有一句话**：节点地址从生到死不变，变的只是谁指向谁。

**insert 只改 4 个指针**（`pos` 指向的节点叫 `cur`）：

```cpp
node* n = new node(v);
n->prev = cur->prev;         // ① 新节点接上前驱
n->next = cur;               // ② 新节点接上后继
cur->prev->next = n;         // ③ 前驱改指向新节点
cur->prev = n;               // ④ 后继改指向新节点
++size_;
return iterator(n);
```

因为只改指针，**其他节点的地址一个字节都没动** ⇒ 指向它们的迭代器、指针、引用继续有效。这就是阅读 2 那道题的实测版。

**哨兵节点的价值**：把「空表插入」「头部插入」「尾部插入」「末尾删除」四种边界统一成一种——所有位置都有一个合法的前驱和后继，`insert` 再也不用写 `if (pos == head)` 的特判。真实实现（libstdc++）用「基类节点 + 派生节点」来避免给哨兵构造一个 `T`；这里的教学版直接在哨兵里放了个默认构造的 `T`，所以测试里 `Tracked` 的存活数会多 1 个，出了作用域又归 0。

**erase 为什么必须返回下一个**：`erase(pos)` 里那个节点已经被 `delete` 了，`pos` 自己就是野指针。除了返回 `next`，没有别的办法安全地继续遍历——这就是「边遍历边删」在 list 上唯一正确的写法。反过来，`vector::erase` 返回的也是下一个，但**它同时让后面所有迭代器失效**，所以同样的写法在 vector 上照样是 UB。

**顺便回答阅读 2 留下的疑问**：为什么这题在 list 上"能跑"？因为删掉的节点内存还没被复用，`it->next` 读到的还是旧值。换一次分配器、加一层 ASan，或者让别的代码先占那块内存，立刻就炸。**能跑通是运气，不是正确性。**''',

    169: '''**核心只有一句话**：`rehash` 换的是「桶数组」，不是「节点」。

**桶与链**：

```cpp
node**      buckets_;                 // 桶数组：每个槽存一个链表头
std::size_t bucketCount_, size_;

std::size_t bucket_of(const K& k) const {
    return std::hash<K>{}(k) % bucketCount_;   // 取模落到某个桶
}
```

500 个键塞进 512 个桶，按鸽巢原理**冲突是必然的**，不是"偶尔发生"。冲突了就挂到同一个桶的链上，查找时先算桶号、再在链上顺序比——所以最坏情况是 O(链长)，这也解释了为什么装填因子一旦超过 1 就必须扩容：链变长，查找就退化成链表。

**rehash 只重挂指针**（这是本题的重点）：

```cpp
void rehash(std::size_t newCount) {
    node** fresh = new node*[newCount]();      // 新桶数组，全空
    for (std::size_t i = 0; i < bucketCount_; ++i) {
        node* p = buckets_[i];
        while (p) {
            node* next = p->next;              // 先存住，下面要改 p->next
            std::size_t b = std::hash<K>{}(p->key) % newCount;
            p->next = fresh[b];                // 头插到新桶
            fresh[b] = p;
            p = next;
        }
    }
    delete[] buckets_;                         // 只删桶数组，节点一个都不动
    buckets_ = fresh;
    bucketCount_ = newCount;
}
```

**于是「迭代器失效、引用不失效」这个反直觉结论就有了物理依据**：

| 东西 | 里面存的是什么 | rehash 之后 |
|---|---|---|
| 引用 / 指针 / `V*` | 直接指向**节点** | 节点没搬 ⇒ **仍然有效** |
| 迭代器 | 指向**节点** + 记着**属于哪个桶** | 桶号全变了 ⇒ **失效** |

标准库的迭代器还要靠"桶号"做 `++`（走到链尾要跳到下一个非空桶），所以桶一变它就废了；引用只认节点地址，自然毫发无伤。**入门那道「迭代器死了、元素还活着」的选择题，答案就写在你刚写的这个 while 循环里。**

**erase 的坑**：要删的节点可能正好是链表头，此时必须改 `buckets_[b]` 而不是改前驱的 `next`。漏掉这个分支，链头就永远删不掉。''',
}

# ---------- 三张表 DDL（与 src/database.cpp initTable 保持一致） ----------
DDL = """CREATE TABLE IF NOT EXISTS practice_chapters(
    id INT AUTO_INCREMENT PRIMARY KEY,
    semester VARCHAR(50) NOT NULL DEFAULT '' COMMENT '章节分组',
    title VARCHAR(128) NOT NULL COMMENT '章节标题',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '0草稿/1发布'
)ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS practice_exercises(
    id INT AUTO_INCREMENT PRIMARY KEY,
    chapter_id INT NOT NULL COMMENT '所属章节',
    type VARCHAR(10) NOT NULL DEFAULT 'short' COMMENT 'choice/blank/short/boss',
    title VARCHAR(256) NOT NULL COMMENT '题目标题',
    prompt TEXT NOT NULL COMMENT '题干：写代码=需求(markdown)；选择=纯代码(markdown)；填空=代码骨架(含______)',
    question TEXT NULL COMMENT '题目问题/说明(选择题=问题；填空题=说明；代码框外展示)',
    keep_notes TINYINT NOT NULL DEFAULT 0 COMMENT '1=prompt 里的注释属于代码本体(源码阅读题)，前端不抽成描述',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '章内排序',
    options TEXT NULL COMMENT '选择题选项JSON(非选择题为NULL)',
    answer TEXT NULL COMMENT '选择=正确label(JSON字符串)；填空=答案数组(JSON)；写代码=NULL',
    solution TEXT NULL COMMENT '题解(思路+参考实现+要点，markdown)',
    starter_easy TEXT COMMENT '入门脚手架(写代码题)',
    starter_medium TEXT COMMENT '进阶脚手架(写代码题)',
    starter_hard TEXT COMMENT '挑战脚手架(写代码题)',
    test_driver TEXT NULL COMMENT '隐藏测试驱动(写代码题,含main)',
    total_cases INT NOT NULL DEFAULT 0 COMMENT '用例数(写代码题)',
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


def sql_or_null(s):
    """字符串转 SQL 字面量；None/空串转 NULL（客观题无 test_driver/options 时用）。"""
    if s is None or s == '':
        return 'NULL'
    return sql_literal(s)


# ---------- 固化题面：把「问题/说明」从 // 注释抽到 question 字段 ----------
import re as _re

def _strip_comment(line):
    """去掉一行开头的 // 注释符，返回纯文字（用于把问题/说明从代码框里抽出来）。"""
    return _re.sub(r'^\s*//\s?', '', line).strip()

def _extract_blank_notes(src):
    """抽所有 // 注释（整行与行内），代码保留（用于固化 choice/blank 的「问题/说明」）。"""
    notes = []
    code = []
    for line in (src or '').split('\n'):
        t = line.strip()
        if t.startswith('//'):
            n = _strip_comment(line)
            if n:
                notes.append(n)
            continue
        ci = line.find('//')
        if ci != -1:
            before = line[:ci].rstrip()
            after = line[ci + 2:].strip()
            if after:
                notes.append(after)
            if before.strip():
                code.append(before)
        else:
            code.append(line)
    return [n for n in notes if n], code

def split_exercise_prompt(prompt, typ):
    """固化题面：把 choice/blank 的「问题/说明」从 // 注释抽到 question 字段，prompt 只剩纯代码。
    返回 (question, cleaned_prompt)。
    - choice：去 ```cpp 围栏 -> 抽所有 // 注释（开头/行内）→ 重新包围栏（无代码则清空 prompt）。
    - blank：抽所有 // 注释，prompt 保留纯代码（含 ______）。
    - short/boss：原样返回（question 由调用方置 None）。
    """
    if typ == 'choice':
        raw = (prompt or '').strip()
        m = _re.match(r'^```[A-Za-z0-9]*\n([\s\S]*?)\n?```$', raw)
        inner = m.group(1).rstrip('\n') if m else raw
        notes, code = _extract_blank_notes(inner)
        if not notes:
            return '', prompt
        code_text = '\n'.join(code).rstrip()
        cleaned = ('```cpp\n' + code_text + '\n```') if code_text.strip() else ''
        return ' '.join(notes), cleaned
    if typ == 'blank':
        notes, code = _extract_blank_notes(prompt)
        if not notes:
            return '', prompt
        return ' '.join(notes), '\n'.join(code).rstrip()
    return '', prompt


# 旧表补列迁移：CREATE TABLE IF NOT EXISTS 只对「不存在的表」建表，**无法给已有表加列**；
# 所以表结构新增列时，必须在这里补一条幂等迁移（与 src/database.cpp 的 columnExists 迁移对应）。
COLUMN_MIGRATIONS = [
    ('practice_exercises', 'solution',
     "TEXT NULL COMMENT '题解(思路+参考实现+要点，markdown)' AFTER answer"),
    ('practice_exercises', 'question',
     "TEXT NULL COMMENT '题目问题/说明(选择题=问题,填空题=说明)' AFTER prompt"),
    ('practice_exercises', 'keep_notes',
     "TINYINT NOT NULL DEFAULT 0 COMMENT '1=prompt 里的注释属于代码本体(源码阅读题)，前端不抽成描述' AFTER question"),
]


def add_column_if_missing(table, column, definition):
    """生成幂等的「缺列则补」SQL 片段。

    MySQL 没有 ADD COLUMN IF NOT EXISTS（那是 MariaDB 语法），因此用
    information_schema 判断列是否存在、再 PREPARE 动态执行 ALTER，兼容 MySQL 5.7/8.x。
    老库缺列时自动补上，避免后续 INSERT 报 `1054 Unknown column`。
    """
    ddl = 'ALTER TABLE %s ADD COLUMN %s %s' % (table, column, definition)
    ddl_lit = ddl.replace("'", "''")
    return '\n'.join([
        'SET @ddl := (',
        '    SELECT IF(COUNT(*) = 0,',
        "        '%s'," % ddl_lit,
        "        'SELECT 1'",
        '    )',
        '    FROM information_schema.COLUMNS',
        '    WHERE TABLE_SCHEMA = DATABASE()',
        "      AND TABLE_NAME = '%s'" % table,
        "      AND COLUMN_NAME = '%s'" % column,
        ');',
        'PREPARE stmt_mig FROM @ddl;',
        'EXECUTE stmt_mig;',
        'DEALLOCATE PREPARE stmt_mig;',
    ])


def validate_sql(sql):
    """字符串感知扫描生成结果：引号/注释闭合 + 语句终止符齐全。

    起因：曾漏掉语句结尾分号导致导入报 1064（客户端把下一条语句一起发过去）。
    朴素字符扫描会被题干/答案里的引号、分号误判，必须按 MySQL 字面量规则
    跳过 '' 与 \\ 转义、'' 形式的转义引号、-- 与 /* */ 注释。
    返回扫描到的语句（分号）条数。
    """
    n = len(sql)
    i = 0
    stmts = 0
    while i < n:
        c = sql[i]
        if c in "'\"`":
            quote = c
            i += 1
            while True:
                if i >= n:
                    raise SystemExit('SQL 中存在未闭合的 %s 字符串' % quote)
                if sql[i] == '\\' and quote != '`':
                    i += 2
                    continue
                if sql[i] == quote:
                    if i + 1 < n and sql[i + 1] == quote:   # '' / "" / `` 转义，不算结束
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            continue
        if sql.startswith('--', i) and (i + 2 >= n or sql[i + 2] in ' \t\r\n'):
            j = sql.find('\n', i)
            i = n if j < 0 else j
            continue
        if sql.startswith('/*', i):
            j = sql.find('*/', i + 2)
            if j < 0:
                raise SystemExit('SQL 中存在未闭合的 /* 注释')
            i = j + 2
            continue
        if c == ';':
            stmts += 1
        i += 1

    if not sql.rstrip().endswith(';'):
        raise SystemExit('生成结果未以分号收尾，末条语句可能未终止')
    return stmts


def build():
    out = []
    out.append('-- ============================================================')
    out.append('-- 练习闯关 · seed 题库（14 章节 + 写代码题，由 gen_practice_seed.py 生成）')
    out.append('-- 用法：mysql -u root -p blogdb < tools/seed_practice.sql')
    out.append('-- 幂等：固定 id + upsert（ON DUPLICATE KEY UPDATE），重导会更新已有行。')
    out.append('-- 注意：本文件是 UTF-8，先 SET NAMES utf8mb4 避免中文乱码。')
    out.append('-- ============================================================')
    out.append('')
    out.append('SET NAMES utf8mb4;')
    out.append('')
    out.append('-- ---------- 第 1 步：确保三张表存在 ----------')
    out.append(DDL.rstrip())
    out.append('')
    out.append('-- ---------- 第 1.5 步：旧表补列（幂等迁移） ----------')
    out.append('-- 说明：CREATE TABLE IF NOT EXISTS 只对「不存在的表」生效，无法给已有表加列；')
    out.append('--       这里对老库缺失的列做幂等补列，避免第 3 步 INSERT 报 1054 Unknown column。')
    for tbl, col, definition in COLUMN_MIGRATIONS:
        out.append(add_column_if_missing(tbl, col, definition))
    out.append('')
    out.append('-- ---------- 第 2 步：插入 14 个章节 ----------')
    for cid, sem, title, sort in CHAPTERS:
        out.append(
            'INSERT INTO practice_chapters (id, semester, title, sort_order, status) VALUES '
            f'({cid}, {sql_literal(sem)}, {sql_literal(title)}, {sort}, 1) '
            'ON DUPLICATE KEY UPDATE semester=VALUES(semester), title=VALUES(title), '
            'sort_order=VALUES(sort_order), status=VALUES(status);'
        )
    out.append('')
    out.append('-- ---------- 第 3 步：插入题目 ----------')
    for e in EXERCISES:
        typ = e['type']
        # —— 固化题面：choice/blank 把「问题/说明」抽到 question 字段（独立展示用）；
        #    prompt 始终保留原始代码（含 // 注释）作为兜底——避免旧后端未下发 question 时描述消失 ——
        # 优先用题目自带的显式 question（用于 prompt 本就无 // 注释说明的题）。
        if typ in ('choice', 'blank'):
            explicit_q = e.get('question')
            if explicit_q and explicit_q.strip():
                question_val = explicit_q.strip()
            else:
                question_val, _ = split_exercise_prompt(e['prompt'], typ)   # 仅取 question，prompt 用原始值
            prompt_val = e['prompt']
        else:
            question_val = None          # 写代码题无独立问题字段
            prompt_val = e['prompt']
        # 1 = prompt 里的注释属于代码本体（源码阅读题），前端不抽成描述
        keep_notes = 1 if e.get('keep_notes') else 0
        # options / answer 序列化为 JSON；None -> NULL
        options_val = json.dumps(e['options'], ensure_ascii=False) if e.get('options') else None
        answer_val = e.get('answer')
        if answer_val is not None:
            answer_val = json.dumps(answer_val, ensure_ascii=False)
        # 写代码题字段：客观题为空
        starter_easy = e.get('starter_easy') or ''
        starter_medium = e.get('starter_medium') or ''
        starter_hard = e.get('starter_hard') or ''
        test_driver = e.get('test_driver') or ''
        total_cases = e.get('total_cases', 0)
        time_limit_ms = e.get('time_limit_ms', 2000)
        # 题解：优先取 EXERCISES 内联字段，否则查 SOLUTIONS 表
        solution_val = e.get('solution') or SOLUTIONS.get(e['id'])

        out.append(
            'INSERT INTO practice_exercises '
            '(id, chapter_id, type, title, prompt, question, keep_notes, sort_order, options, answer, solution, '
            'starter_easy, starter_medium, starter_hard, test_driver, total_cases, time_limit_ms, status) VALUES ('
            f'{e["id"]}, {e["chapter_id"]}, {sql_literal(typ)}, {sql_literal(e["title"])}, '
            f'{sql_literal(prompt_val)}, {sql_or_null(question_val)}, {keep_notes}, {e["sort_order"]}, '
            f'{sql_or_null(options_val)}, {sql_or_null(answer_val)}, {sql_or_null(solution_val)}, '
            f'{sql_literal(starter_easy)}, {sql_literal(starter_medium)}, '
            f'{sql_literal(starter_hard)}, {sql_or_null(test_driver)}, '
            f'{total_cases}, {time_limit_ms}, 1) '
            'ON DUPLICATE KEY UPDATE chapter_id=VALUES(chapter_id), type=VALUES(type), '
            'title=VALUES(title), prompt=VALUES(prompt), question=VALUES(question), '
            'keep_notes=VALUES(keep_notes), sort_order=VALUES(sort_order), '
            'options=VALUES(options), answer=VALUES(answer), solution=VALUES(solution), '
            'starter_easy=VALUES(starter_easy), '
            'starter_medium=VALUES(starter_medium), starter_hard=VALUES(starter_hard), '
            'test_driver=VALUES(test_driver), total_cases=VALUES(total_cases), '
            'time_limit_ms=VALUES(time_limit_ms), status=VALUES(status);'
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
    n_chapters = content.count('INSERT INTO practice_chapters')
    n_exercises = content.count('INSERT INTO practice_exercises')
    assert n_chapters == len(CHAPTERS), f'章节 INSERT 数不符：{n_chapters} != {len(CHAPTERS)}'
    assert n_exercises == len(EXERCISES), f'题目 INSERT 数不符：{n_exercises} != {len(EXERCISES)}'
    assert 'practice_progress' in content, '缺 practice_progress 表'
    # 题解覆盖：每题都必须有题解（SOLUTIONS 或内联 solution）
    missing = [e['id'] for e in EXERCISES if not (e.get('solution') or SOLUTIONS.get(e['id']))]
    assert not missing, f'以下题目缺题解，请补 SOLUTIONS：{missing}'
    n_sol = content.count('solution=VALUES(solution)')
    assert n_sol == len(EXERCISES), f'题解 upsert 数不符：{n_sol} != {len(EXERCISES)}'
    # 旧表补列迁移必须存在（否则老库导入会报 1054 Unknown column）
    n_mig = content.count('PREPARE stmt_mig FROM @ddl')
    assert n_mig == len(COLUMN_MIGRATIONS), f'补列迁移数不符：{n_mig} != {len(COLUMN_MIGRATIONS)}'
    for _, col, _def in COLUMN_MIGRATIONS:
        assert f'ADD COLUMN {col} ' in content, f'缺列迁移缺失：{col}'
    # 语句终止符校验（字符串感知）：DDL 建表 + SET NAMES 1 句 + 每条迁移 4 句 + 章节 + 题目
    expected_stmts = (validate_sql(DDL) + 1 + 4 * len(COLUMN_MIGRATIONS)
                      + len(CHAPTERS) + len(EXERCISES))
    n_stmts = validate_sql(content)
    assert n_stmts == expected_stmts, f'语句数不符：{n_stmts} != {expected_stmts}（可能有语句未终止）'
    print(f'OK: 生成 {target}（{len(CHAPTERS)} 章节 / {len(EXERCISES)} 题，题解 {len(SOLUTIONS)} 条，'
          f'语句 {n_stmts} 条）')


if __name__ == '__main__':
    main()
