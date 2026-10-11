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
import json
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
        'sort_order': 7,
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
        'sort_order': 8,
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
        'sort_order': 9,
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
        'sort_order': 10,
        'prompt': (
            '实现 `IntArray` 类，验证列表初始化与范围 for：\n\n'
            '1. 支持列表初始化：`IntArray a{1, 2, 3, 4};`\n'
            '2. `size()` 返回元素个数\n'
            '3. `operator[]` 访问元素\n'
            '4. 支持范围 for 遍历（`int* begin()` / `int* end()`），含引用遍历修改元素\n\n'
            '> 考点：`std::initializer_list`、统一初始化、范围 for 的引用语义。\n'
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
// 需自行设计成员变量（如 int* data_; int size_;）

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <initializer_list>

// 需求：实现 IntArray 类
//   - 支持列表初始化：IntArray a{1,2,3,4};
//   - 支持 operator[] 访问元素
//   - 支持范围 for 遍历（含引用遍历修改元素）
//   - size() 返回元素个数
//   - 隐藏测试会：构造 {1,2,3,4}、检查 size、范围 for 累加、
//     范围 for 引用修改元素、空列表构造

// 只实现，不要写 main（隐藏测试会提供）
''',
        'test_driver': r'''#include <cstdio>

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
    if (fail == 0) std::printf("PASS\n");
    return fail;
}
''',
        'total_cases': 5,
        'time_limit_ms': 2000,
    },
    {
        'id': 5,
        'chapter_id': 1,
        'type': 'boss',
        'title': 'Boss · 类型安全的枚举状态机',
        'sort_order': 11,
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
    {
        'id': 11,
        'chapter_id': 1,
        'type': 'choice',
        'title': '选择 1 · auto 的引用衰减',
        'sort_order': 1,
        'prompt': '''```cpp
const int& get() {
    static int x = 42;
    return x;
}
auto a = get();   // a 的类型是？
```''',
        'options': [
            {'label': 'A', 'text': 'const int&'},
            {'label': 'B', 'text': 'int&'},
            {'label': 'C', 'text': 'int'},
            {'label': 'D', 'text': 'const int'},
        ],
        'answer': 'C',
    },
    {
        'id': 12,
        'chapter_id': 1,
        'type': 'choice',
        'title': '选择 2 · decltype 的括号陷阱',
        'sort_order': 2,
        'prompt': '''```cpp
int x = 0;
decltype((x)) y = x;   // y 的类型是？
```''',
        'options': [
            {'label': 'A', 'text': 'int'},
            {'label': 'B', 'text': 'int&'},
            {'label': 'C', 'text': 'int&&'},
            {'label': 'D', 'text': 'const int&'},
        ],
        'answer': 'B',
    },
    {
        'id': 13,
        'chapter_id': 1,
        'type': 'choice',
        'title': '选择 3 · 范围 for 的值语义',
        'sort_order': 3,
        'prompt': '''```cpp
std::vector<int> v{1, 2, 3};
for (auto x : v) { x *= 2; }
// 此时 v 的内容是？
```''',
        'options': [
            {'label': 'A', 'text': '{2, 4, 6}'},
            {'label': 'B', 'text': '{1, 2, 3}'},
            {'label': 'C', 'text': '编译错误'},
            {'label': 'D', 'text': '未定义行为'},
        ],
        'answer': 'B',
    },
    {
        'id': 14,
        'chapter_id': 1,
        'type': 'blank',
        'title': '填空 1 · nullptr 的类型安全',
        'sort_order': 4,
        'prompt': '''void f(int)   { /* 版本1 */ }
void f(void*) { /* 版本2 */ }

f(______);   // 想调用 void* 版本''',
        'answer': ['nullptr'],
    },
    {
        'id': 15,
        'chapter_id': 1,
        'type': 'blank',
        'title': '填空 2 · override 防误写',
        'sort_order': 5,
        'prompt': '''class Base { public: virtual void draw() const; };
class Derived : public Base {
public:
    void draw() const ______;   // 填一个关键字
};''',
        'answer': ['override'],
    },
    {
        'id': 16,
        'chapter_id': 1,
        'type': 'blank',
        'title': '填空 3 · =default / =delete',
        'sort_order': 6,
        'prompt': '''class Handle {
public:
    Handle() ________;                          // 空1：显式默认构造
    Handle(const Handle&) ________;             // 空2：禁止拷贝构造
    Handle& operator=(const Handle&) ________;  // 空3：禁止拷贝赋值
};''',
        'answer': ['= default', '= delete', '= delete'],
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
    if (*it == 2) v.erase(it);   // 会发生什么？
}
```''',
        'options': [
            {'label': 'A', 'text': '正常删除 2'},
            {'label': 'B', 'text': '未定义行为（迭代器失效）'},
            {'label': 'C', 'text': '编译错误'},
            {'label': 'D', 'text': '删除所有元素'},
        ],
        'answer': 'B',
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
        'answer': ['find_if'],
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
        'prompt': '''// 用预处理语句防注入，占位符是 ________
// stmt = conn.prepare("SELECT * FROM t WHERE id = ?");''',
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
        'prompt': '''// 协程生成器里产出值的关键字是 ________''',
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
        'sort_order': 7,
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
        'sort_order': 8,
        'prompt': '下面的循环在 `erase` 后继续 `++it`，迭代器已失效，是未定义行为。\n'
                  '用 erase-remove 惯用法修复 `remove_even`（删除所有偶数）。\n\n'
                  '> 考点：vector erase 使迭代器失效；erase-remove 惯用法。',
        'starter_easy': r'''#include <vector>
#include <algorithm>

// BUG: erase 后 it 失效。用 erase-remove 惯用法修复。
void remove_even(std::vector<int>& v) {
    for (auto it = v.begin(); it != v.end(); ++it) {
        if (*it % 2 == 0) v.erase(it);   // BUG: it 失效
    }
}

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_medium': r'''#include <vector>
#include <algorithm>

// 修复 remove_even：用 v.erase(std::remove_if(...), v.end()) 删除所有偶数。

// 只实现，不要写 main（隐藏测试会提供）
''',
        'starter_hard': r'''#include <vector>
#include <algorithm>

// 需求：remove_even 删除所有偶数，避免迭代器失效。

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
        'sort_order': 9,
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
        'sort_order': 10,
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
        'sort_order': 11,
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
    type VARCHAR(10) NOT NULL DEFAULT 'short' COMMENT 'choice/blank/short/boss',
    title VARCHAR(256) NOT NULL COMMENT '题目标题',
    prompt TEXT NOT NULL COMMENT '题干：写代码=需求(markdown)；选择=题干(markdown)；填空=代码骨架(含______)',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '章内排序',
    options TEXT NULL COMMENT '选择题选项JSON(非选择题为NULL)',
    answer TEXT NULL COMMENT '选择=正确label(JSON字符串)；填空=答案数组(JSON)；写代码=NULL',
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
        typ = e['type']
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

        out.append(
            'INSERT IGNORE INTO practice_exercises '
            '(id, chapter_id, type, title, prompt, sort_order, options, answer, '
            'starter_easy, starter_medium, starter_hard, test_driver, total_cases, time_limit_ms, status) VALUES ('
            f'{e["id"]}, {e["chapter_id"]}, {sql_literal(typ)}, {sql_literal(e["title"])}, '
            f'{sql_literal(e["prompt"])}, {e["sort_order"]}, '
            f'{sql_or_null(options_val)}, {sql_or_null(answer_val)}, '
            f'{sql_literal(starter_easy)}, {sql_literal(starter_medium)}, '
            f'{sql_literal(starter_hard)}, {sql_or_null(test_driver)}, '
            f'{total_cases}, {time_limit_ms}, 1);'
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
