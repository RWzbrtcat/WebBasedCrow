# C++ 后端练习闯关游戏 · 题库设计文档

> 版本 v0.1 草稿 · 本内容为设计草稿参考，正式落地前需经团队评审与合规审核。

## 0. 文档说明

**游戏定位**：在现有博客网站上做的 C++ 练习闯关游戏，帮后端程序员"巩固知识 + 考验项目编写能力"。

**四个已定决策**：
1. 判定机制：单测驱动（隐藏测试用例），不是 stdout 比对、不是人工评审
2. 难度：玩家自选档位（入门/进阶/挑战三档），同知识点三档并存，可随时降档不死档
3. 单局时长：短题打底（2-5 分钟）+ 章末 Boss 关（20-40 分钟综合项目）
4. 执行环境：后端沙箱（服务器编译运行玩家代码）

**Fun Hypothesis（一句话）**：让玩家在短题里刷出「这块我会了」的即时确定感，再在章末 Boss 关里亲手把几个知识点拼成一个能跑的小组件，获得「原来我真的能写出来」的项目胜任感——两档成就感交替，支撑长期练习。

**Design Pillars（5 条不可妥协）**：
- P1 即时判定：提交后 ≤5 秒必回「过/没过 + 挂在哪条用例」
- P2 可迭代失败：失败必给下一步（哪个用例、输入是啥、期望 vs 实际）
- P3 脚手架递减：难度递增 = 脚手架递减（填空→修bug→补模块→从零写）
- P4 难度自选：三档并存，随时降档不死档
- P5 项目收口：每章必以综合 Boss 关收口，强制拼起本章（+前几章）知识点

**交付粒度说明（重要）**：
- 客观题（选择题 / 填空题）给到**完整题面**：题干、选项、答案、考点。
- 写代码题（短题 + Boss）给到**设计规格**：知识点定位、三档脚手架、隐藏用例。起始代码文件与测试驱动代码属 seed 阶段产物，不塞进本设计文档。
- 所有数值（时限、内存上限、星级阈值）未压测的一律标 [PLACEHOLDER]，不拍脑袋。

**题型三阶梯（每章固定结构）**：

| 阶梯 | 题型 | 每章题量 | 考什么 | 判定 |
|---|---|---|---|---|
| 1. 识别 | 选择题 | 3 道 | 概念辨析 + 代码阅读预测 | 对答案（轻） |
| 2. 回忆 | 填空题 | 3 道 | 关键语法 token 的记忆 | 补进骨架编译通过（轻） |
| 3. 创造 | 写代码 | 5 道（4 短 + 1 Boss） | 综合运用 + 项目能力 | 沙箱编译运行（重） |

**写代码题的脚手架四阶段**（对应 4 道短题）：填空 → 修 bug → 补模块 → 从零写。

---

## 1. 章节总览（3 学期 14 章）

每章 3 选择 + 3 填空 + 5 写代码 = 11 题；14 章共 154 题，每道写代码题三档。

### 第一学期 · 现代 C++ 语言地基

| 章 | 主题 | 覆盖特性 |
|---|---|---|
| C1 | 现代语法糖 | auto/decltype、nullptr、enum class、override/final、=default/=delete、统一初始化、范围 for |
| C2 | 移动语义与完美转发 | 右值引用、std::move、std::forward、移动构造/赋值、copy elision、RVO |
| C3 | 智能指针与 RAII | unique_ptr/shared_ptr/weak_ptr、make_shared、自定义 deleter、异常安全 |
| C4 | Lambda 与函数式 | 捕获、泛型 lambda(C++14)、std::function、std::bind |
| C5 | 模板与元编程基础 | 变参模板、折叠表达式(C++17)、类型萃取、if constexpr(C++17) |
| C6 | 现代工具类型 | optional/variant/any、string_view、结构化绑定(C++17)、span、std::format(C++20) |

### 第二学期 · 后端应用

| 章 | 主题 | 覆盖特性 |
|---|---|---|
| C7 | STL 容器与算法 | 容器选型、迭代器失效、自定义哈希、并行算法(C++17) |
| C8 | 文件操作与流 | fstream、二进制、std::filesystem(C++17)、序列化 |
| C9 | 多线程与并发 | thread/mutex/cv/atomic、async/future/promise、jthread(C++20) |
| C10 | 网络编程 | socket、粘包、epoll、异步 IO |
| C11 | 数据库交互 | 连接、预处理防注入、事务、连接池 |

### 第三学期 · 进阶与工程

| 章 | 主题 | 覆盖特性 |
|---|---|---|
| C12 | constexpr 与编译期计算 | constexpr、consteval/constinit(C++20)、编译期容器 |
| C13 | C++20 高级特性 | concepts、ranges/views、协程 coroutine |
| C14 | 模块与工程实践 | modules(C++20)、多文件组织、CMake、代码规范 |

**前置依赖**：C2 依赖 C1，C3 依赖 C1/C2，C7 依赖 C3/C4，C8 依赖 C3，C9 依赖 C3，C10 依赖 C9，C11 依赖 C9，C12 依赖 C5，C13 依赖 C4/C5，C14 依赖全部。解锁下一章需前置章累计星数达阈值（阈值 [PLACEHOLDER]）。

---

## 2. 第一学期 · 现代 C++ 语言地基

### C1 · 现代语法糖

> 本章定位：不是从零教语法，是考老手容易翻车的细节——auto 的引用衰减、decltype 的括号陷阱、enum class 的序列化。

#### 选择题 ×3

**选 1 · auto 的引用衰减**
```cpp
const int& get() {
    static int x = 42;
    return x;
}
auto a = get();   // a 的类型是？
```
| 选项 | 结果 |
|---|---|
| A. `const int&` | ✗ 以为 auto 原样保留引用和 const |
| B. `int&` | ✗ 以为保留引用、只丢 const |
| C. `int` | ✓ auto 值拷贝，引用和顶层 const 都被丢弃 |
| D. `const int` | ✗ 以为保留 const、只丢引用 |

**选 2 · decltype 的括号陷阱**
```cpp
int x = 0;
decltype((x)) y = x;   // y 的类型是？
```
| 选项 | 结果 |
|---|---|
| A. `int` | ✗ 混淆 decltype(x) 和 decltype((x)) |
| B. `int&` | ✓ 括号表达式是左值，decltype 得引用 |
| C. `int&&` | ✗ 把左值括号当成右值 |
| D. `const int&` | ✗ 无中生有 const |

**选 3 · 范围 for 的值语义**
```cpp
std::vector<int> v{1, 2, 3};
for (auto x : v) { x *= 2; }
// 此时 v 的内容是？
```
| 选项 | 结果 |
|---|---|
| A. `{2, 4, 6}` | ✗ 以为 auto 是引用 |
| B. `{1, 2, 3}` | ✓ auto 值拷贝，修改不作用到容器 |
| C. 编译错误 | ✗ 范围 for 不要求引用 |
| D. 未定义行为 | ✗ 无中生有 |

#### 填空题 ×3

**填 1 · nullptr 的类型安全**
```cpp
void f(int)   { /* 版本1 */ }
void f(void*) { /* 版本2 */ }
f(______);   // 想调用 void* 版本
```
答案 `nullptr`。坑点：填 `0` 或 `NULL` 会静默走 int 版本——这正是 nullptr 存在的意义。

**填 2 · override 防误写**
```cpp
class Base { public: virtual void draw() const; };
class Derived : public Base {
public:
    void draw() const ______;   // 填一个关键字
};
```
答案 `override`。考点：签名写错（漏 const）时，加了 override 会在编译期报错，而非静默变成"没重写"。

**填 3 · =default / =delete**
```cpp
class Handle {
public:
    Handle() ________;                          // 空1：显式默认构造
    Handle(const Handle&) ________;             // 空2：禁止拷贝构造
    Handle& operator=(const Handle&) ________;  // 空3：禁止拷贝赋值
};
```
答案 `= default` / `= delete` / `= delete`。判定：补入后能编译，同时拷贝路径被删导致编译失败。

#### 写代码 ×4

| 题 | 知识点 | 入门（给骨架） | 进阶（给签名） | 挑战（只给需求） |
|---|---|---|---|---|
| 短1 | auto/decltype 推导 | 补声明过 static_assert | 写 get_ref/get_value | decltype(auto) 完美转发 |
| 短2 | enum class 类型安全 | 错误已标注，改枚举 | 自己找隐式转换 bug | 加序列化 round-trip |
| 短3 | override/final/=default/=delete | 补派生类 | 自设计派生 + final | 不可拷贝资源句柄 |
| 短4 | 统一初始化 + 范围 for | 补实现 | 自写接口 + 实现 | initializer_list 小容器 |

#### Boss · 类型安全的枚举状态机

需求：TCP 状态用 enum class，非法转移检测 + 序列化 round-trip + =delete 禁拷贝。

| 档 | 起始代码 | 隐藏用例 |
|---|---|---|
| 入门 | 状态枚举 + 转移表骨架已给 | 合法转移链走通 |
| 进阶 | 只给需求 + 测试描述 | 自设计状态枚举和转移 |
| 挑战 | 加多态状态处理器 + 序列化 | 非法转移被拒 / round-trip / =delete 禁拷贝 |

---

### C2 · 移动语义与完美转发

> 本章定位：考移动语义的三个经典误区——move 后源对象状态、构造 vs 赋值、RVO 是否必然发生。

#### 选择题 ×3

**选 1 · move 之后源对象的状态**
```cpp
std::vector<int> a{1, 2, 3};
std::vector<int> b = std::move(a);
// 关于 a，正确的说法是？
```
| 选项 | 结果 |
|---|---|
| A. a 仍是 {1,2,3}，b 是它的拷贝 | ✗ 以为 move 是浅拷贝 |
| B. a 资源被转移，处于"有效但未指定"状态（通常空） | ✓ 标准语义 |
| C. 访问 a 是未定义行为 | ✗ "有效但未指定"≠UB |
| D. 编译错误 | ✗ |

**选 2 · 移动构造的触发（构造 vs 赋值）**
```cpp
std::string s = "hello";
std::string t = std::move(s);   // 这行调用的是？
```
| 选项 | 结果 |
|---|---|
| A. 拷贝构造 | ✗ |
| B. 移动构造 | ✓ std::move 返回右值，t 是新建对象 |
| C. 拷贝赋值 | ✗ 混淆"构造"和"赋值" |
| D. 移动赋值 | ✗ 同上，t 是初始化不是赋值 |

**选 3 · RVO / 拷贝省略**
```cpp
Widget make_widget() {
    Widget w;
    return w;              // 按值返回局部对象
}
Widget x = make_widget();
// 从 w 到 x，调用几次拷贝/移动构造？
```
| 选项 | 结果 |
|---|---|
| A. 至少一次拷贝 | ✗ |
| B. 至少一次移动 | ✗ |
| C. 零次（拷贝省略） | ✓ C++17 起强制 |
| D. 取决于编译器 | ✗ 过时认知，C++17 后强制 |

#### 填空题 ×3

**填 1 · std::move**
```cpp
std::vector<int> a{1, 2, 3};
std::vector<int> b = ________(a);   // 转移 a 的资源，避免深拷贝
```
答案 `std::move`。

**填 2 · std::forward（完美转发）**
```cpp
template <typename T>
void wrapper(T&& arg) {
    target(________<T>(arg));   // 保持 arg 的左值/右值类别
}
```
答案 `std::forward`。

**填 3 · 移动构造的 noexcept**
```cpp
class Buffer {
public:
    Buffer(Buffer&& other) ________;   // 声明不抛异常
};
```
答案 `noexcept`。考点：不加 noexcept，vector 扩容时会退化成拷贝（拷贝才有异常安全保证）。

#### 写代码 ×4

| 题 | 知识点 | 入门（给骨架） | 进阶（给签名） | 挑战（只给需求） |
|---|---|---|---|---|
| 短1 | 移动构造/移动赋值 | 补资源指针交换实现 | 自写移动 + 交换 | 带自移动保护 |
| 短2 | 移动后源对象/自移动 bug | 错误已标注 | 自己定位移动后误用 | 加自移动赋值安全 |
| 短3 | 只移动类（=delete 拷贝） | 补移动构造/赋值 | 自设计接口 | unique_ptr 简化版 |
| 短4 | 完美转发工厂 | 补 forward 调用 | 自写可变参转发 | make_unique 风格工厂 |

#### Boss · 只移动的 Buffer 类

隐藏用例（挑战档）：

| # | 用例 | 失败信号 |
|---|---|---|
| 1 | 移动后源对象仍可安全析构/重新赋值 | 崩溃/泄漏 |
| 2 | 移动自赋值 b = std::move(b) | 崩溃/资源被清空 |
| 3 | vector<Buffer> 扩容走移动构造 | 若 noexcept 缺失会退化成拷贝 |
| 4 | 拷贝构造被 =delete 禁止 | 拷贝路径编译失败 |
| 5 | 按值返回 Buffer | RVO 零构造 |

---

### C3 · 智能指针与 RAII

> 本章定位：考智能指针的三个经典陷阱——循环引用、unique_ptr 独占、make_shared 的异常安全。

#### 选择题 ×3

**选 1 · shared_ptr 循环引用**
```cpp
struct Node {
    std::shared_ptr<Node> next;
};
auto a = std::make_shared<Node>();
auto b = std::make_shared<Node>();
a->next = b;
b->next = a;   // a、b 互相引用，会发生什么？
```
| 选项 | 结果 |
|---|---|
| A. 离开作用域后自动释放 | ✗ 引用计数永不为 0 |
| B. a、b 永远无法释放，内存泄漏 | ✓ 循环引用 |
| C. 编译错误 | ✗ |
| D. 运行时崩溃 | ✗ 不会崩，只是泄漏 |

**选 2 · unique_ptr 独占所有权**
```cpp
std::unique_ptr<int> p1 = std::make_unique<int>(42);
std::unique_ptr<int> p2 = p1;   // 这行？
```
| 选项 | 结果 |
|---|---|
| A. 编译通过，共享所有权 | ✗ unique_ptr 独占 |
| B. 编译错误，unique_ptr 不可拷贝 | ✓ 只能移动 |
| C. 编译通过，p2 拥有、p1 悬空 | ✗ |
| D. 运行时错误 | ✗ |

**选 3 · make_shared 的异常安全**
```cpp
// 哪种写法更好？
auto p1 = std::shared_ptr<Widget>(new Widget);  // A
auto p2 = std::make_shared<Widget>();           // B
```
| 选项 | 结果 |
|---|---|
| A. A 更好 | ✗ |
| B. B 更好，单次分配 + 异常安全 | ✓ |
| C. 两者完全等价 | ✗ |
| D. A 有异常安全保证 | ✗ A 在"new 成功但构造前抛异常"会泄漏 |

#### 填空题 ×3

**填 1 · make_shared**
```cpp
auto sp = std::________<Widget>(/* 构造参数 */);
```
答案 `make_shared`。

**填 2 · weak_ptr 打破循环引用**
```cpp
struct Node {
    std::________<Node> next;   // 用弱引用打破循环引用
};
```
答案 `weak_ptr`。

**填 3 · weak_ptr.lock()**
```cpp
std::weak_ptr<int> wp = sp;   // sp 是 shared_ptr
if (auto p = wp.________()) { /* 安全使用 p */ }
```
答案 `lock`。考点：lock() 返回临时 shared_ptr，防止"检查时有效、使用时已释放"的竞态。

#### 写代码 ×4

| 题 | 知识点 | 入门（给骨架） | 进阶（给签名） | 挑战（只给需求） |
|---|---|---|---|---|
| 短1 | unique_ptr 所有权转移 | 补 move 转移 | 自写转移语义 | 转移后源指针为空 |
| 短2 | shared_ptr 循环引用 | 错误已标注，改 weak_ptr | 自己定位循环引用 | 加资源释放验证 |
| 短3 | 自定义 deleter + RAII | 补 deleter | 自设计 RAII 资源类 | 文件句柄守卫 |
| 短4 | 手写简易 shared_ptr | 补引用计数 | 自写控制块 | 线程安全引用计数 |

#### Boss · RAII 资源守卫

需求：实现一个不可拷贝、可移动的资源守卫（锁守卫或文件守卫），析构自动释放。

| 档 | 起始代码 | 隐藏用例 |
|---|---|---|
| 入门 | 接口 + 析构骨架已给 | 析构自动释放 |
| 进阶 | 只给需求 | 自设计释放 + 移动语义 |
| 挑战 | 加 =delete 拷贝 + 移动 | 拷贝编译失败 / 移动后源守卫失效 / 异常时也释放 |

---

### C4 · Lambda 与函数式

> 本章定位：考 lambda 的三个高频坑——捕获引用悬垂、泛型 lambda 本质、[=] 捕获 this 的真相。

#### 选择题 ×3

**选 1 · 捕获引用悬垂**
```cpp
std::function<int()> make_counter() {
    int count = 0;
    return [&]() { return ++count; };   // 返回捕获引用的 lambda
}
auto f = make_counter();
f();   // 会发生什么？
```
| 选项 | 结果 |
|---|---|
| A. 返回 1 | ✗ |
| B. 未定义行为（悬垂引用） | ✓ count 已随函数返回销毁 |
| C. 编译错误 | ✗ 能编译 |
| D. 返回 0 | ✗ |

**选 2 · 泛型 lambda（C++14）**
```cpp
auto add = [](auto a, auto b) { return a + b; };
// 这个 lambda 的实质是？
```
| 选项 | 结果 |
|---|---|
| A. 编译错误，参数不能是 auto | ✗ C++14 起可以 |
| B. 模板化的函数对象（operator() 是模板） | ✓ |
| C. 只能处理 int | ✗ |
| D. 只能处理同类型 | ✗ |

**选 3 · [=] 捕获 this 的真相**
```cpp
class A {
    int v = 0;
public:
    auto get() { return [=]() { return v; }; }   // [=] 捕获了什么？
};
```
| 选项 | 结果 |
|---|---|
| A. 拷贝了 v 的值 | ✗ C++11 的 [=] 捕获 this 指针 |
| B. 捕获了 this 指针，经 this 访问 v | ✓ |
| C. 编译错误 | ✗ |
| D. 未定义行为 | ✗ |

#### 填空题 ×3

**填 1 · 按引用捕获**
```cpp
int threshold = 10;
auto pred = [____](int x) { return x > threshold; };   // 按引用捕获 threshold
```
答案 `&`。

**填 2 · mutable**
```cpp
int n = 0;
auto inc = [n]() ________ { return ++n; };   // 让 lambda 能修改按值捕获的 n
```
答案 `mutable`。考点：lambda 默认 operator() 是 const，按值捕获的变量不可改，加 mutable 才行。

**填 3 · 泛型 lambda 参数**
```cpp
auto twice = [](________ x) { return x * 2; };   // 接受任意算术类型
```
答案 `auto`。

#### 写代码 ×4

| 题 | 知识点 | 入门（给骨架） | 进阶（给签名） | 挑战（只给需求） |
|---|---|---|---|---|
| 短1 | lambda 捕获 | 补捕获列表 | 自写捕获语义 | 按值/引用混用 |
| 短2 | 捕获悬垂引用 | 错误已标注 | 自己定位悬垂 | 生命周期管理 |
| 短3 | std::function 回调注册 | 补回调存储 | 自设计事件注册 | 回调生命周期 |
| 短4 | lambda + 算法流水线 | 补算法组合 | 自写 transform/filter | ranges 风格链式 |

#### Boss · 回调事件系统

需求：用 std::function + lambda 实现一个事件系统，支持注册、注销、触发。

| 档 | 起始代码 | 隐藏用例 |
|---|---|---|
| 入门 | 接口 + 注册骨架已给 | 注册后触发回调 |
| 进阶 | 只给需求 | 自设计注销 + 触发顺序 |
| 挑战 | 加移动语义 + 悬垂防护 | 回调对象移动后仍有效 / 注销后再触发不崩 |

---

### C5 · 模板与元编程基础

> 本章定位：考模板的三个进阶点——变参展开、if constexpr 编译期分支、typename 依赖类型。

#### 选择题 ×3

**选 1 · 变参模板递归展开**
```cpp
template <typename T>
T sum(T t) { return t; }
template <typename T, typename... Args>
T sum(T t, Args... args) { return t + sum(args...); }
// sum(1, 2, 3, 4) 的结果是？
```
| 选项 | 结果 |
|---|---|
| A. 10 | ✓ 递归展开 |
| B. 编译错误 | ✗ |
| C. 只算前两个 | ✗ |
| D. 未定义行为 | ✗ |

**选 2 · if constexpr 编译期分支**
```cpp
template <typename T>
auto get_value(T t) {
    if constexpr (std::is_pointer_v<T>)
        return *t;
    else
        return t;
}
// 传入 int* 时，else 分支会被编译吗？
```
| 选项 | 结果 |
|---|---|
| A. 会，运行时跳过 | ✗ 那是普通 if |
| B. 不会，编译期丢弃 | ✓ if constexpr |
| C. 编译错误 | ✗ |
| D. 取决于优化 | ✗ |

**选 3 · typename 依赖类型**
```cpp
template <typename T>
void f(T t) {
    typename T::value_type x;   // 为什么需要 typename？
}
```
| 选项 | 结果 |
|---|---|
| A. 告诉编译器 T::value_type 是类型 | ✓ 依赖类型必须显式 |
| B. 可选，去掉也能编译 | ✗ |
| C. 表示运行时多态 | ✗ |
| D. 无中生有 | ✗ |

#### 填空题 ×3

**填 1 · 折叠表达式**
```cpp
template <typename... Args>
auto sum(Args... args) {
    return (args + ________);   // 用折叠表达式求和
}
```
答案 `...`（即 `(args + ...)`）。

**填 2 · typename**
```cpp
template <typename T>
void print_first(const T& c) {
    ________ T::value_type x = c.front();   // 声明依赖类型变量
}
```
答案 `typename`。

**填 3 · if constexpr**
```cpp
template <typename T>
void f(T t) {
    if ________ (std::is_integral_v<T>) { /* 整数路径 */ }
    else { /* 其他路径 */ }
}
```
答案 `constexpr`。

#### 写代码 ×4

| 题 | 知识点 | 入门（给骨架） | 进阶（给签名） | 挑战（只给需求） |
|---|---|---|---|---|
| 短1 | 变参模板求和 | 补递归出口 | 自写变参展开 | 折叠表达式 |
| 短2 | 模板重载/特化 bug | 错误已标注 | 自己定位重载歧义 | 特化优先级 |
| 短3 | 类型萃取工具 | 补 type_traits | 自写 is_integral | enable_if 约束 |
| 短4 | 编译期类型列表 | 补类型递归 | 自写 typelist | 编译期计算长度 |

#### Boss · 类型安全的变参注册器

需求：用变参模板 + 类型萃取实现一个类型安全的注册器，能按类型注册/取回。

| 档 | 起始代码 | 隐藏用例 |
|---|---|---|
| 入门 | 接口 + 变参骨架已给 | 注册后按类型取回 |
| 进阶 | 只给需求 | 自设计类型映射 |
| 挑战 | 加 enable_if 约束 | 类型不匹配编译失败 / 编译期类型列表 |

---

### C6 · 现代工具类型

> 本章定位：考 optional/variant/string_view 的三个坑——无值默认、union 区别、string_view 悬垂。

#### 选择题 ×3

**选 1 · optional 无值**
```cpp
std::optional<int> find_even(const std::vector<int>& v) {
    for (int x : v) if (x % 2 == 0) return x;
    return std::nullopt;
}
// find_even({1, 3, 5}) 返回什么？
```
| 选项 | 结果 |
|---|---|
| A. 0 | ✗ 有值和无值混为一谈 |
| B. std::nullopt（无值） | ✓ |
| C. 抛异常 | ✗ |
| D. 未定义行为 | ✗ |

**选 2 · variant vs union**
```cpp
std::variant<int, double, std::string> v = 42;
```
| 选项 | 结果 |
|---|---|
| A. v 是裸 union，同内存存三种 | ✗ variant 是类型安全封装 |
| B. v 是类型安全联合，当前持有 int | ✓ |
| C. v 同时持有三种值 | ✗ |
| D. 编译错误 | ✗ |

**选 3 · string_view 悬垂**
```cpp
std::string_view get_view() {
    std::string s = "hello";
    return s;   // 返回 s 的 string_view
}
auto v = get_view();
std::cout << v;   // 会发生什么？
```
| 选项 | 结果 |
|---|---|
| A. 输出 hello | ✗ |
| B. 悬垂引用，未定义行为 | ✓ s 已销毁，view 指向已释放内存 |
| C. 输出空 | ✗ |
| D. 编译错误 | ✗ |

#### 填空题 ×3

**填 1 · optional value_or**
```cpp
std::optional<int> o;
int x = o.________(42);   // 无值时给默认值
```
答案 `value_or`。

**填 2 · variant 访问**
```cpp
std::variant<int, std::string> v = "hi";
std::________([](auto&& arg){ /* 访问 */ }, v);
```
答案 `visit`。

**填 3 · string_view 零拷贝切片**
```cpp
std::string_view view = "hello world";
auto sub = view.________(0, 5);   // 取前5个字符，不拷贝
```
答案 `substr`。考点：string_view::substr 是 O(1) 零拷贝，string::substr 是拷贝。

#### 写代码 ×4

| 题 | 知识点 | 入门（给骨架） | 进阶（给签名） | 挑战（只给需求） |
|---|---|---|---|---|
| 短1 | optional 使用 | 补 has_value/value | 自写返回 optional | 无值路径处理 |
| 短2 | string_view 悬垂 | 错误已标注 | 自己定位悬垂 | 生命周期边界 |
| 短3 | variant 类型安全访问 | 补 std::visit | 自设计 variant 访问 | 非法类型访问防护 |
| 短4 | optional 重构错误处理 | 补返回类型改造 | 自写错误码 → optional | 异常 → 结果类型 |

#### Boss · 类型安全配置解析器

需求：用 optional/variant/string_view + 结构化绑定实现一个配置解析器，能解析不同类型的配置值。

| 档 | 起始代码 | 隐藏用例 |
|---|---|---|
| 入门 | 接口 + 解析骨架已给 | 解析整型/字符串配置 |
| 进阶 | 只给需求 | 自设计类型分发 |
| 挑战 | 加 variant 多类型 + 缺省值 | 缺失配置给默认 / 类型不匹配报错 / 零拷贝切片 |

---

## 3. 第二学期 · 后端应用

### C7 · STL 容器与算法

> 本章定位：考 STL 的三个高频坑——迭代器失效、容器选型、erase-remove 惯用法。

#### 选择题 ×3

**选 1 · 迭代器失效**
```cpp
std::vector<int> v{1, 2, 3};
for (auto it = v.begin(); it != v.end(); ++it) {
    if (*it == 2) v.erase(it);   // 会发生什么？
}
```
| 选项 | 结果 |
|---|---|
| A. 正常删除 2 | ✗ erase 后 it 失效，++it 是 UB |
| B. 未定义行为（迭代器失效） | ✓ |
| C. 编译错误 | ✗ |
| D. 删除所有元素 | ✗ |

**选 2 · map vs unordered_map**
```cpp
// 需要按键有序遍历的场景，选哪个？
```
| 选项 | 结果 |
|---|---|
| A. unordered_map | ✗ 哈希无序 |
| B. map | ✓ 红黑树，键有序 |
| C. vector | ✗ 无序键值对 |
| D. list | ✗ |

**选 3 · erase-remove 惯用法**
```cpp
// 删除 vector 中所有值为 2 的元素，正确写法是？
```
| 选项 | 结果 |
|---|---|
| A. 循环里逐个 erase | ✗ 迭代器失效风险 |
| B. v.erase(std::remove(begin, end, 2), end) | ✓ 惯用法 |
| C. std::remove 直接删 | ✗ remove 不真正删除，只前移 |
| D. v.clear() | ✗ 全删了 |

#### 填空题 ×3

**填 1 · 自定义哈希**
```cpp
struct Hash {
    size_t operator()(const Point& p) const {
        return std::hash<int>()(p.x) ^ (std::hash<int>()(p.y) << 1);
    }
};
std::________<Point, int, Hash> m;   // 用自定义哈希的哈希表
```
答案 `unordered_map`。

**填 2 · 自定义比较器**
```cpp
std::________<int, std::greater<int>> s;   // 降序集合
```
答案 `set`。

**填 3 · 算法 find_if**
```cpp
auto it = std::________(v.begin(), v.end(), [](int x){ return x > 10; });
```
答案 `find_if`。

#### 写代码 ×4

| 题 | 知识点 | 入门（给骨架） | 进阶（给签名） | 挑战（只给需求） |
|---|---|---|---|---|
| 短1 | 容器选型 | 补容器声明 | 自写选型理由 | 性能对比 |
| 短2 | 迭代器失效 | 错误已标注 | 自己定位失效点 | erase-remove 重构 |
| 短3 | 自定义哈希/比较器 | 补 hash 函数 | 自写比较器 | 自定义键类型 |
| 短4 | 算法组合 | 补算法链 | 自写 transform/filter | 并行算法(C++17) |

#### Boss · LRU 缓存

需求：实现一个线程安全的 LRU 缓存，跨 C7（容器）+ C3（智能指针）+ C4（lambda）。

| 档 | 起始代码 | 隐藏用例 |
|---|---|---|
| 入门 | 接口 + 哈希表骨架已给 | get/put 基本行为 |
| 进阶 | 只给需求 | 自设计淘汰策略 + 有序性 |
| 挑战 | 加线程安全 + 容量边界 | 并发 get/put 一致 / 满容量淘汰最久未用 |

---

### C8 · 文件操作与流

> 本章定位：考流处理的三个坑——流状态检查、二进制 vs 文本、读取循环惯用法。

#### 选择题 ×3

**选 1 · 流状态检查**
```cpp
ifstream f("a.txt");
if (f) { /* 打开成功 */ }
// if (f) 检查的是什么？
```
| 选项 | 结果 |
|---|---|
| A. 文件是否为空 | ✗ |
| B. 流状态是否 good（无 fail/bad） | ✓ 状态位 |
| C. eof 是否到达 | ✗ |
| D. 文件是否存在 | ✗ 间接判断，本质是状态位 |

**选 2 · 二进制 vs 文本**
```cpp
// 写 int 到文件，要避免平台差异和截断，应该用？
```
| 选项 | 结果 |
|---|---|
| A. 文本模式 << | ✗ 格式化，有平台差异 |
| B. 二进制模式 write | ✓ 按字节写 |
| C. 都行 | ✗ |
| D. 无中生有 | ✗ |

**选 3 · 读取循环惯用法**
```cpp
while (f >> x) { /* ... */ }
// 这个循环什么时候结束？
```
| 选项 | 结果 |
|---|---|
| A. 读到 eof 或格式失败 | ✓ >> 失败即停 |
| B. 读到换行 | ✗ |
| C. 死循环 | ✗ |
| D. 读满 buffer | ✗ |

#### 填空题 ×3

**填 1 · 追加模式**
```cpp
std::ofstream f("a.txt", std::ios::________);   // 追加模式
```
答案 `app`。

**填 2 · 逐行读取**
```cpp
std::ifstream f("a.txt");
std::string line;
while (std::________(f, line)) { /* 逐行读 */ }
```
答案 `getline`。

**填 3 · filesystem 命名空间**
```cpp
namespace fs = std::________;   // C++17 文件系统
```
答案 `filesystem`。

#### 写代码 ×4

| 题 | 知识点 | 入门（给骨架） | 进阶（给签名） | 挑战（只给需求） |
|---|---|---|---|---|
| 短1 | 流读写 | 补读写循环 | 自写状态检查 | 错误恢复 |
| 短2 | 二进制读写 | 错误已标注 | 自己定位二进制 bug | 字节序处理 |
| 短3 | 分块读大文件 | 补分块逻辑 | 自写缓冲策略 | 大文件不爆内存 |
| 短4 | 序列化器 | 补序列化函数 | 自写类型序列化 | 版本兼容 |

#### Boss · 日志文件滚动系统

需求：实现日志写入 + 文件按大小/时间滚动，跨 C8（文件）+ C3（RAII）+ C2（移动）。

| 档 | 起始代码 | 隐藏用例 |
|---|---|---|
| 入门 | 接口 + 写入骨架已给 | 写日志到文件 |
| 进阶 | 只给需求 | 自设计滚动策略 |
| 挑战 | 加大小阈值 + 归档 | 达阈值滚动 / 归档命名 / 资源不泄漏 |

---

### C9 · 多线程与并发

> 本章定位：考并发的三个致命坑——数据竞争、锁顺序死锁、原子 vs 锁的选择。

#### 选择题 ×3

**选 1 · 数据竞争**
```cpp
int counter = 0;
// 多线程同时 counter++，会发生什么？
```
| 选项 | 结果 |
|---|---|
| A. 结果一定正确 | ✗ |
| B. 数据竞争，结果未定义 | ✓ i++ 非原子 |
| C. 编译错误 | ✗ |
| D. 线程安全 | ✗ |

**选 2 · 锁顺序死锁**
```cpp
// 线程1: lock(a); lock(b);
// 线程2: lock(b); lock(a);
// 会发生什么？
```
| 选项 | 结果 |
|---|---|
| A. 正常运行 | ✗ |
| B. 可能死锁（锁顺序不一致） | ✓ |
| C. 一定死锁 | ✗ 取决于时序 |
| D. 编译错误 | ✗ |

**选 3 · atomic vs mutex**
```cpp
// 单变量的简单自增，用哪个最轻量？
```
| 选项 | 结果 |
|---|---|
| A. mutex | ✗ 重量级 |
| B. std::atomic | ✓ 无锁自增 |
| C. 无锁裸变量 | ✗ 数据竞争 |
| D. 都行 | ✗ |

#### 填空题 ×3

**填 1 · 锁守卫**
```cpp
std::mutex m;
{
    std::________<std::mutex> lock(m);   // RAII 自动加解锁
}
```
答案 `lock_guard`。

**填 2 · condition_variable 谓词等待**
```cpp
std::unique_lock<std::mutex> lock(m);
cv.________(lock, []{ return ready; });   // 带谓词，防虚假唤醒
```
答案 `wait`。

**填 3 · 原子计数器**
```cpp
std::________<int> counter{0};   // 原子计数器
```
答案 `atomic`。

#### 写代码 ×4

| 题 | 知识点 | 入门（给骨架） | 进阶（给签名） | 挑战（只给需求） |
|---|---|---|---|---|
| 短1 | mutex 基本用法 | 补加解锁 | 自写临界区 | 锁粒度优化 |
| 短2 | 数据竞争 | 错误已标注 | 自己定位竞争点 | 内存序分析 |
| 短3 | cv 生产者消费者 | 补等待/通知 | 自写谓词 | 多消费者 |
| 短4 | 线程安全队列 | 补锁保护 | 自写阻塞/非阻塞 | 无锁边界 |

#### Boss · 线程安全日志缓冲

需求：多线程写日志行到内存缓冲，满或超时批量刷文件，不丢日志、无竞争。跨 C9 + C8 + C3。

| 档 | 起始代码 | 隐藏用例 |
|---|---|---|
| 入门 | 接口 + mutex 骨架已给 | 基本写入不丢 |
| 进阶 | 只给需求 | 自设计缓冲/刷新 |
| 挑战 | 高并发 + 满缓冲时机 + 析构 flush | 8 线程写 100 万条不丢 / 满即刷 / 析构刷剩余 / 死锁超时 |

---

### C10 · 网络编程

> 本章定位：考网络编程的三个基础——TCP 可靠性、粘包、字节序。

#### 选择题 ×3

**选 1 · TCP vs UDP**
```cpp
// 需要可靠有序传输，选哪个？
```
| 选项 | 结果 |
|---|---|
| A. UDP | ✗ 不可靠 |
| B. TCP | ✓ 可靠有序 |
| C. 都行 | ✗ |
| D. 无中生有 | ✗ |

**选 2 · TCP 粘包**
```cpp
// 期望接收 100 字节，一次 recv 可能返回？
```
| 选项 | 结果 |
|---|---|
| A. 一定 100 字节 | ✗ |
| B. 任意 1-100 字节（TCP 是字节流） | ✓ |
| C. 一定 0 字节 | ✗ |
| D. 超过 100 字节 | ✗ |

**选 3 · 字节序**
```cpp
// 网络传输多字节整数，要解决什么问题？
```
| 选项 | 结果 |
|---|---|
| A. 大小端字节序转换 | ✓ |
| B. 字符编码 | ✗ |
| C. 数据压缩 | ✗ |
| D. 数据加密 | ✗ |

#### 填空题 ×3

**填 1 · 创建 socket**
```cpp
int fd = ________(AF_INET, SOCK_STREAM, 0);   // TCP socket
```
答案 `socket`。

**填 2 · 字节序转换**
```cpp
uint16_t p = ________(port);   // 主机序转网络序（端口）
```
答案 `htons`。

**填 3 · 开始监听**
```cpp
________(fd, 128);   // 开始监听
```
答案 `listen`。

#### 写代码 ×4

| 题 | 知识点 | 入门（给骨架） | 进阶（给签名） | 挑战（只给需求） |
|---|---|---|---|---|
| 短1 | socket 基础 | 补创建/连接 | 自写收发循环 | 错误处理 |
| 短2 | 粘包拆包 | 错误已标注 | 自己定位粘包 | 自定义长度头协议 |
| 短3 | epoll 非阻塞 | 补事件循环 | 自写非阻塞 IO | 多路复用 |
| 短4 | 半双工协议 | 补协议帧 | 自写编解码 | 定长+变长帧 |

#### Boss · echo TCP 服务器

需求：实现多客户端 echo 服务器，跨 C10 + C9（多线程）+ C4（lambda 回调）。

| 档 | 起始代码 | 隐藏用例 |
|---|---|---|
| 入门 | 接口 + 单连接骨架已给 | 单客户端 echo |
| 进阶 | 只给需求 | 自设计多客户端 |
| 挑战 | 加线程池 + 优雅关闭 | 多客户端并发 echo / 关闭不丢连接 / 资源回收 |

---

### C11 · 数据库交互

> 本章定位：考数据库的三个核心——SQL 注入、事务、连接池。

#### 选择题 ×3

**选 1 · SQL 注入**
```cpp
// 拼接 SQL 字符串构造查询，主要风险是？
```
| 选项 | 结果 |
|---|---|
| A. 性能差 | ✗ |
| B. SQL 注入 | ✓ 用户输入拼进 SQL |
| C. 语法错误 | ✗ |
| D. 连接泄漏 | ✗ |

**选 2 · 事务**
```cpp
// 一组操作要么全成功要么全回滚，用什么保证？
```
| 选项 | 结果 |
|---|---|
| A. 事务 | ✓ 原子性 |
| B. 索引 | ✗ |
| C. 连接池 | ✗ |
| D. 缓存 | ✗ |

**选 3 · 连接池**
```cpp
// 连接池主要解决什么问题？
```
| 选项 | 结果 |
|---|---|
| A. 频繁建立/销毁连接的开销 | ✓ |
| B. SQL 优化 | ✗ |
| C. 数据安全 | ✗ |
| D. 索引维护 | ✗ |

#### 填空题 ×3

**填 1 · 预处理占位符**
```cpp
// 用预处理语句防注入，占位符是 ________
// stmt = conn.prepare("SELECT * FROM t WHERE id = ?");
```
答案 `?`。

**填 2 · 提交事务**
```cpp
conn.________();   // 提交事务
```
答案 `commit`。

**填 3 · 回滚事务**
```cpp
conn.________();   // 回滚事务
```
答案 `rollback`。

#### 写代码 ×4

| 题 | 知识点 | 入门（给骨架） | 进阶（给签名） | 挑战（只给需求） |
|---|---|---|---|---|
| 短1 | 连接与查询 | 补连接/查询 | 自写结果处理 | 错误处理 |
| 短2 | SQL 注入 | 错误已标注 | 自己定位注入点 | 预处理重构 |
| 短3 | 事务回滚 | 补 commit/rollback | 自写事务边界 | 异常回滚 |
| 短4 | 连接池 | 补借还逻辑 | 自写池管理 | 并发借还 + 超时 |

#### Boss · 带连接池的 DAO 层

需求：实现带连接池的数据访问层，跨 C11 + C9（线程安全）+ C3（RAII）。

| 档 | 起始代码 | 隐藏用例 |
|---|---|---|
| 入门 | 接口 + DAO 骨架已给 | 基本 CRUD |
| 进阶 | 只给需求 | 自设计连接池 + DAO |
| 挑战 | 加并发 + 连接归还 | 并发查询连接复用 / 连接不泄漏 / 池满等待 |

---

## 4. 第三学期 · 进阶与工程

### C12 · constexpr 与编译期计算

> 本章定位：考编译期计算的三个点——constexpr 求值、consteval 强制编译期、constinit 初始化。

#### 选择题 ×3

**选 1 · constexpr 函数编译期求值**
```cpp
constexpr int square(int x) { return x * x; }
int arr[square(3)];   // 数组大小是？
```
| 选项 | 结果 |
|---|---|
| A. 9 | ✓ 编译期求值 |
| B. 编译错误 | ✗ |
| C. 运行时求值 | ✗ |
| D. 未定义 | ✗ |

**选 2 · consteval 强制编译期**
```cpp
consteval int f(int x) { return x; }
int y = 5;
int z = f(y);   // 这行？
```
| 选项 | 结果 |
|---|---|
| A. 编译错误（consteval 必须编译期调用） | ✓ |
| B. 正常，运行时调用 | ✗ 那是 constexpr |
| C. 未定义 | ✗ |
| D. 返回 5 | ✗ |

**选 3 · constinit**
```cpp
// constinit 的作用是？
```
| 选项 | 结果 |
|---|---|
| A. 保证编译期初始化，避免静态初始化顺序问题 | ✓ |
| B. 让变量不可变 | ✗ 那是 const |
| C. 让变量线程安全 | ✗ |
| D. 让变量堆分配 | ✗ |

#### 填空题 ×3

**填 1 · constexpr**
```cpp
________ int square(int x) { return x * x; }   // 编译期可求值的函数
```
答案 `constexpr`。

**填 2 · consteval**
```cpp
________ int f(int x) { return x * 2; }   // 只能在编译期调用
```
答案 `consteval`。

**填 3 · constinit**
```cpp
________ int g = 42;   // 保证编译期初始化
```
答案 `constinit`。

#### 写代码 ×4

| 题 | 知识点 | 入门（给骨架） | 进阶（给签名） | 挑战（只给需求） |
|---|---|---|---|---|
| 短1 | constexpr 函数 | 补 constexpr 声明 | 自写编译期函数 | 编译期递归 |
| 短2 | 编译期错误 | 错误已标注 | 自己定位非编译期调用 | consteval 边界 |
| 短3 | constexpr 容器 | 补编译期容器 | 自写 constexpr vector | 编译期遍历 |
| 短4 | 编译期计算 | 补模板元编程 | 自写编译期阶乘/斐波那契 | 编译期查找表 |

#### Boss · 编译期查找表

需求：用 constexpr 实现一个编译期生成的查找表（如三角函数表或状态转移表）。

| 档 | 起始代码 | 隐藏用例 |
|---|---|---|
| 入门 | 接口 + constexpr 骨架已给 | 编译期生成表 |
| 进阶 | 只给需求 | 自设计表结构与填充 |
| 挑战 | 加编译期断言 | 表值编译期验证 / 越界访问编译失败 |

---

### C13 · C++20 高级特性

> 本章定位：考 C++20 的三大特性——concepts 约束、ranges 惰性、协程。

#### 选择题 ×3

**选 1 · concepts 约束**
```cpp
template <typename T>
concept Numeric = std::is_arithmetic_v<T>;

template <Numeric T>
T add(T a, T b) { return a + b; }

add("a", "b");   // 传入字符串会？
```
| 选项 | 结果 |
|---|---|
| A. 编译错误（不满足 Numeric 约束） | ✓ |
| B. 运行时错误 | ✗ |
| C. 正常返回 "ab" | ✗ |
| D. 未定义 | ✗ |

**选 2 · ranges 惰性求值**
```cpp
auto r = v | std::views::filter(f) | std::views::transform(g);
// 这行会立即执行 filter/transform 吗？
```
| 选项 | 结果 |
|---|---|
| A. 会立即执行 | ✗ |
| B. 不会，惰性求值，遍历时才计算 | ✓ |
| C. 取决于编译器 | ✗ |
| D. 编译错误 | ✗ |

**选 3 · 协程三关键字**
```cpp
// co_yield 的作用是？
```
| 选项 | 结果 |
|---|---|
| A. 挂起并产出一个值，之后可恢复 | ✓ |
| B. 终止协程 | ✗ 那是 co_return |
| C. 等待异步操作 | ✗ 那是 co_await |
| D. 无中生有 | ✗ |

#### 填空题 ×3

**填 1 · concept 定义**
```cpp
template <typename T>
________ Numeric = std::is_arithmetic_v<T>;   // 定义一个约束
```
答案 `concept`。

**填 2 · requires 子句**
```cpp
template <typename T>
________ std::integral<T>   // 约束 T 是整数类型
void f(T t);
```
答案 `requires`。

**填 3 · co_yield**
```cpp
// 协程生成器里产出值的关键字是 ________
```
答案 `co_yield`。

#### 写代码 ×4

| 题 | 知识点 | 入门（给骨架） | 进阶（给签名） | 挑战（只给需求） |
|---|---|---|---|---|
| 短1 | concept 约束 | 补 concept 定义 | 自写约束 | 约束组合(&&/||) |
| 短2 | ranges 组合 | 错误已标注 | 自己定位管道 bug | 惰性求值验证 |
| 短3 | 协程生成器 | 补 co_yield | 自写生成器 | co_return 收尾 |
| 短4 | ranges 流水线 | 补视图组合 | 自写 filter/transform | 惰性 + 物化 |

#### Boss · 协程生成器 + ranges 组合

需求：用协程生成器产出序列，再用 ranges 视图做惰性过滤/变换，跨 C13 + C4（lambda）。

| 档 | 起始代码 | 隐藏用例 |
|---|---|---|
| 入门 | 接口 + 生成器骨架已给 | 生成序列 |
| 进阶 | 只给需求 | 自设计生成器 + 视图链 |
| 挑战 | 加惰性验证 | 不物化中间结果 / 无限序列惰性取前 N / 组合正确性 |

---

### C14 · 模块与工程实践

> 本章定位：考工程化的三个点——module 隔离、ODR 单一定义、头文件保护。

#### 选择题 ×3

**选 1 · module vs include**
```cpp
// module 相比 #include 的优势是？
```
| 选项 | 结果 |
|---|---|
| A. 编译隔离，避免宏污染和重复解析 | ✓ |
| B. 运行更快 | ✗ |
| C. 无需编译 | ✗ |
| D. 无中生有 | ✗ |

**选 2 · ODR 单一定义规则**
```cpp
// 同一个非 inline 函数在多个编译单元被定义，会导致？
```
| 选项 | 结果 |
|---|---|
| A. 链接错误（多重定义） | ✓ |
| B. 自动去重 | ✗ |
| C. 运行时错误 | ✗ |
| D. 无影响 | ✗ |

**选 3 · 头文件保护**
```cpp
// 防止头文件重复包含的惯用法？
```
| 选项 | 结果 |
|---|---|
| A. include guard 或 #pragma once | ✓ |
| B. extern | ✗ |
| C. static | ✗ |
| D. inline | ✗ |

#### 填空题 ×3

**填 1 · 导出模块**
```cpp
________ module math;   // 声明模块接口
```
答案 `export`。

**填 2 · 导入模块**
```cpp
________ math;   // 导入模块
```
答案 `import`。

**填 3 · include guard 结尾**
```cpp
#ifndef FOO_H
#define FOO_H
// ...
________   // 结尾
```
答案 `#endif`。

#### 写代码 ×4

| 题 | 知识点 | 入门（给骨架） | 进阶（给签名） | 挑战（只给需求） |
|---|---|---|---|---|
| 短1 | 多文件组织 | 补头文件/实现分离 | 自写模块划分 | 依赖方向 |
| 短2 | ODR 违反 | 错误已标注 | 自己定位多重定义 | inline/static 修复 |
| 短3 | 模块接口单元 | 补 export | 自写模块接口 | 模块分区 |
| 短4 | 小型库组织 | 补 CMake 结构 | 自写库分层 | 接口/实现隔离 |

#### Boss · 小型 C++ 库的模块化组织

需求：把一个工具库按 module 组织，接口与实现分离，跨 C14（模块）+ 工程实践。

| 档 | 起始代码 | 隐藏用例 |
|---|---|---|
| 入门 | 接口 + 模块骨架已给 | 模块导出/导入 |
| 进阶 | 只给需求 | 自设计模块划分 |
| 挑战 | 加接口隔离 | 内部实现不暴露 / 依赖单向 / 可独立编译 |

---

## 5. 附录 A · 判定协议（单测驱动）

```
玩家提交代码
   ↓
编译隔离  g++ -std=c++17 -O2 -Wall  编译超时 → 返回编译错误(翻译成人话)
   ↓
注入测试驱动  (隐藏 main + 断言，回合间隔离)
   ↓
运行隔离  rlimit/cgroup: CPU + 内存 + 文件数 + 进程数上限
   ↓
收集断言结果 → 返回: 通过 n/m + 首个失败用例(输入/期望/实际)
```

**沙箱四道闸**：

| 闸 | 目的 | 手段 |
|---|---|---|
| 编译隔离 | 防编译期资源耗尽 | -std -O2 -Wall + 编译超时 + 不接用户头文件 |
| 运行隔离 | 防 CPU/内存炸弹 | rlimit + cgroup（CPU、内存、fork 数） |
| 系统隔离 | 防读写宿主机 | 只读文件系统 + 禁外网 + 禁 setuid，仅给题目临时目录 |
| 数据库隔离 | 防污染真实库 | 每回合临时 schema/库，用完即毁 |

**客观题判定**：选择题 = 对答案；填空题 = 补进带 static_assert 的骨架编译通过即对（防多解）。

**错误翻译层**（待设计，第 3 步展开）：把 segmentation fault / terminate called / 编译报错翻译成人话。

**待定项（[PLACEHOLDER]）**：time_limit_ms / mem_limit_mb（待压测）、解锁星级阈值（待章节定稿后算）、玩家代码跑在 docker 还是裸机 namespace。

## 6. 附录 B · 数据库表结构（4 张新表）

```sql
-- 章节
CREATE TABLE practice_chapters (
  id INT PRIMARY KEY AUTO_INCREMENT,
  slug VARCHAR(64) NOT NULL UNIQUE,
  title VARCHAR(128) NOT NULL,
  sort_order INT NOT NULL,
  prereq_chapter_id INT NULL,           -- 前置依赖，NULL=第一章
  description TEXT,
  status TINYINT DEFAULT 0              -- 0草稿/1发布
);

-- 题目（短题 + Boss）
CREATE TABLE practice_exercises (
  id INT PRIMARY KEY AUTO_INCREMENT,
  chapter_id INT NOT NULL,
  type ENUM('short','boss') NOT NULL DEFAULT 'short',
  title VARCHAR(256) NOT NULL,
  prompt TEXT NOT NULL,                 -- 题目需求，markdown
  sort_order INT NOT NULL,
  starter_easy TEXT,                    -- 入门脚手架
  starter_medium TEXT,                  -- 进阶脚手架
  starter_hard TEXT,                    -- 挑战脚手架
  compile_flags VARCHAR(256) DEFAULT '-std=c++17 -O2 -Wall',
  time_limit_ms INT DEFAULT 2000,       -- [PLACEHOLDER]
  mem_limit_mb INT DEFAULT 128,         -- [PLACEHOLDER]
  status TINYINT DEFAULT 0
);

-- 测试用例（隐藏）
CREATE TABLE practice_test_cases (
  id INT PRIMARY KEY AUTO_INCREMENT,
  exercise_id INT NOT NULL,
  tier ENUM('easy','medium','hard') NOT NULL,  -- 进阶含 easy+medium，挑战含全部
  visible TINYINT DEFAULT 0,                   -- 0隐藏/1对玩家可见
  test_code TEXT NOT NULL,                     -- 测试驱动代码片段
  weight INT DEFAULT 1,
  sort_order INT NOT NULL
);

-- 玩家进度（匿名 Cookie，复用 blog_anon 的 owner_token）
CREATE TABLE practice_progress (
  owner_token VARCHAR(64) NOT NULL,
  exercise_id INT NOT NULL,
  tier ENUM('easy','medium','hard') NOT NULL,
  best_stars TINYINT DEFAULT 0,
  attempts INT DEFAULT 0,
  passed TINYINT DEFAULT 0,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (owner_token, exercise_id, tier)
);
```

**进度机制**：匿名 Cookie（复用 blog_anon），清 Cookie 即重置。星级 = 难度档（入门 1 星/进阶 2 星/挑战 3 星），同题三档独立。解锁下章需前置章累计星数达阈值（[PLACEHOLDER]）。

---

## 7. 待办与决策点

- [ ] 玩家代码沙箱选型：docker vs 裸机 namespace（影响 C8/C11 的文件与 DB 隔离方案）
- [ ] 错误翻译层设计（把编译/运行错误翻译成人话）
- [ ] 客观题（选择/填空）的存储与判题实现
- [ ] 间隔重复复习机制的复习周期表（艾宾浩斯曲线）
- [ ] 代码审查玩法的判定协议
- [ ] 进度是否要登录制（当前按匿名 Cookie 走）
- [ ] time_limit_ms / mem_limit_mb 压测定值







