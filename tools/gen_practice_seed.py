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
    {
        'id': 3,
        'chapter_id': 1,
        'type': 'short',
        'title': '短题 3 · override/final/=delete',
        'sort_order': 3,
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
        'sort_order': 4,
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
        'sort_order': 5,
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
        'total_cases': 7,
        'time_limit_ms': 2000,
    },
    {
        'id': 6,
        'chapter_id': 2,
        'type': 'short',
        'title': '短题 1 · 移动构造与移动赋值',
        'sort_order': 1,
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
        'sort_order': 2,
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
        'total_cases': 4,
        'time_limit_ms': 2000,
    },
    {
        'id': 8,
        'chapter_id': 2,
        'type': 'short',
        'title': '短题 3 · 只移动类（=delete 拷贝）',
        'sort_order': 3,
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
        'total_cases': 5,
        'time_limit_ms': 2000,
    },
    {
        'id': 9,
        'chapter_id': 2,
        'type': 'short',
        'title': '短题 4 · 完美转发工厂',
        'sort_order': 4,
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
        'sort_order': 5,
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
        'total_cases': 6,
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
