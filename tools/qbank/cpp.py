# -*- coding: utf-8 -*-
"""C++ 面试题（新增 90 道，叠加 existing.py 中的 10 道后合计 100）。

字段：(category, tags, difficulty, question, answer)
difficulty: 1 基础 / 2 进阶 / 3 困难
"""

QUESTIONS = [

    # ---------- 语言基础 ----------
    (
        "C++",
        "指针,引用",
        1,
        r"""指针和引用有什么区别？""",
        r"""| 维度 | 指针 | 引用 |
|---|---|---|
| 是否可空 | 可以为 `nullptr` | 必须绑定对象，不可为空 |
| 是否可改绑 | 可以指向别的对象 | 一经绑定不可改绑 |
| 是否占内存 | 是，本身是一个对象（有地址、有大小） | 通常被实现为指针，但语言层面不占"独立对象"的地位 |
| 能否取地址 | `&p` 得到指针的地址 | `&r` 得到被引用对象的地址 |
| 能否算术运算 | 可以 `p++` | 不可以 |
| 数组 | 可以有指针数组、指向数组的指针 | 没有引用的数组 |

关键点：
- 引用**必须初始化**，所以不存在"空引用"（但可以通过悬垂引用制造 UB）。
- 传参时 `const T&` 既避免拷贝，又不像指针那样需要判空，是"只读大对象"的首选。
- 编译器通常用指针实现引用，但会把"引用不可改绑"作为优化依据（如别名分析）。

```cpp
int a = 1, b = 2;
int& r = a;
r = b;      // 这是赋值！a 变成 2，而不是让 r 改绑到 b
```""",
    ),
    (
        "C++",
        "宏,const,inline",
        1,
        r"""`#define` 和 `const`、`inline` 有什么区别？宏有哪些坑？""",
        r"""宏是**预处理期的文本替换**，不参与编译期的类型检查与作用域。

坑：
1. **无类型检查**：`#define MAX 100` 与 `int` 相加不会报错。
2. **多次求值**：`#define SQ(x) ((x)*(x))`，`SQ(i++)` 中 `i++` 会执行两次。
3. **运算符优先级**：`#define ADD(a,b) a+b`，`ADD(1,2)*3` 变成 `1+2*3 = 7` 而非 9。所以宏体要整体加括号，参数也要加。
4. **无作用域**：宏是全局的，`#undef` 才能撤销；命名冲突难排查。
5. **调试困难**：调试器看不到宏符号，编译错误定位到展开后的代码。

替代方案：

| 宏用途 | 现代替代 |
|---|---|
| 常量 | `constexpr` / `const` |
| 小函数 | `inline` 函数 / `constexpr` 函数 |
| 类型别名 | `using` / `typedef` |
| 条件编译 | 仍然只能用宏（`#ifdef`） |
| 日志、断言 | 宏仍是常见选择（要 `__FILE__` / `__LINE__`） |

注意：`inline` 的本意是"允许在多个翻译单元中重复定义（ODR 例外）"，**是否真的内联由编译器决定**，不是强制的。""",
    ),
    (
        "C++",
        "static,生命周期",
        2,
        r"""`static` 关键字在 C++ 中有哪几种用法？""",
        r"""按作用位置分五种：

1. **全局/命名空间作用域的 static**：内部链接（internal linkage），符号只在当前翻译单元可见，避免重名冲突。
2. **函数内的 static 局部变量**：静态存储期，**首次执行到声明处时初始化一次**（C++11 起保证线程安全，编译器插入 `__cxa_guard_acquire` 之类的守卫），程序结束时析构。
3. **类的 static 数据成员**：属于类而非对象，所有实例共享；必须在**类外定义**（C++17 起可用 `inline static` 在类内定义）。
4. **类的 static 成员函数**：没有 `this`，不能访问非静态成员，不能是 `virtual`/`const`。
5. **匿名命名空间**：C++ 中替代文件级 static 的更现代做法。

```cpp
void f() {
    static int cnt = 0;   // 只初始化一次，多线程安全
    ++cnt;
}
```

坑：函数内静态局部变量的初始化存在**线程安全的性能开销**（每次进入都要检查守卫），热路径上要留意。""",
    ),
    (
        "C++",
        "extern C,链接",
        2,
        r"""`extern "C"` 是做什么的？为什么 C++ 调用 C 库要加它？""",
        r"""C++ 为了支持**函数重载**，会对函数名做**名字修饰（name mangling）**，例如
`void foo(int)` 在 GCC 下变成 `_Z3fooi`。而 C 语言不做修饰，符号名就是 `foo`。

`extern "C"` 告诉编译器：括号内的声明**按 C 的方式生成符号名**，不做修饰。

用途：
1. **C++ 调用 C 库**：C 库导出的符号是未修饰的，C++ 若不声明 `extern "C"`，链接时会找不到符号。
2. **C 调用 C++**：C 编译器不认识 C++ 的修饰，所以 C++ 侧要导出未修饰符号。
3. **给 C 用的头文件**要写成双兼容形式：

```cpp
#ifdef __cplusplus
extern "C" {
#endif

void c_api(int x);

#ifdef __cplusplus
}
#endif
```

注意：
- `extern "C"` 对**函数和全局变量**有效；C++ 的类、模板、重载函数不能放进 `extern "C"` 块（重载函数名会冲突）。
- 它只影响链接名，不影响调用约定（调用约定是 `__cdecl`/`__stdcall` 等另一套）。""",
    ),
    (
        "C++",
        "struct,class",
        1,
        r"""C++ 里 `struct` 和 `class` 有什么区别？""",
        r"""语言层面**只有两个区别**：

| 维度 | struct | class |
|---|---|---|
| 默认访问权限 | `public` | `private` |
| 默认继承方式 | `public` 继承 | `private` 继承 |

其它（能否有成员函数、构造析构、虚函数、继承、模板）都完全一样。

实践约定：
- `struct` 用于**纯数据聚合**、POD、简单的小对象（成员全 public，无复杂不变量）。
- `class` 用于**有封装、有不变量需要维护**的抽象类型。

还有一个容易被忽视的点：**C 兼容性**。`struct` 在 C 和 C++ 中都能用，是跨语言数据交换的常见选择；但含 C++ 特性的 struct（虚函数、非平凡构造）就不再是 C 兼容的了。""",
    ),
    (
        "C++",
        "POD,平凡类型",
        3,
        r"""什么是 POD？平凡类型（trivial）、标准布局（standard-layout）和 POD 的关系是什么？""",
        r"""这三个概念在 C++11 后被拆开了：

- **平凡类型（trivial）**：满足
  - 有平凡的默认构造/拷贝构造/移动构造/拷贝赋值/移动赋值/析构（全部 `= default` 且非虚）
  - 这样的类型可以**按字节 memcpy**，生命周期不用显式管理。
- **标准布局（standard-layout）**：布局与 C 兼容，要求
  - 无虚函数、无虚基类
  - 所有非静态成员同访问控制
  - 无两个基类含同类型非静态成员等
  - 这样的类型可以安全地在 C 与 C++ 之间传递、可以用 `offsetof`。
- **POD（Plain Old Data）**：C++11 之前 = 平凡 + 标准布局；**C++20 起 POD 概念已被弃用**，因为它其实是两个独立需求的合并，混在一起反而不精确。

用途：
- 需要 `memcpy` / 二进制序列化 → 要 **trivial**。
- 需要与 C 结构体互操作 / `offsetof` → 要 **standard-layout**。

```cpp
struct A { int x; double y; };          // trivial + standard-layout
struct B { virtual void f(); int x; };  // 都不是
struct C { A a; private: int z; };      // trivial 但不是 standard-layout（访问控制不统一）
```""",
    ),
    (
        "C++",
        "sizeof,对齐",
        2,
        r"""`sizeof` 有哪些常见陷阱？空类的大小是多少？""",
        r"""常见陷阱：

1. **空类不是 0**：`sizeof(Empty) == 1`。因为每个对象必须有唯一地址，标准强制至少 1 字节。
2. **空基类优化（EBO）**：作为基类时空类可以占 0 字节，`sizeof(Derived) == sizeof(Derived)` 不含空基类。
3. **虚函数引入 vptr**：64 位下 `sizeof` 会比成员总和多 8 字节（vptr）。
4. **成员对齐填充**：`struct { char a; int b; }` 大小是 8 而不是 5。
5. **数组与指针**：`sizeof(arr)` 是数组总字节；函数参数里的数组已退化为指针，`sizeof` 得到指针大小。
6. **`sizeof` 不求值**：`sizeof(f())` 不会真正调用 `f()`（C++ 中 `f` 返回类型已知即可）。
7. **变长数组**：C99 的 VLA 在 C++ 标准里不存在（GCC 作扩展支持），`sizeof` 在运行期才能算。

示例：

```cpp
struct A { };                       // 1
struct B { virtual ~B(); };         // 8（vptr）
struct C { char c; int i; };        // 8（填充 3 字节）
struct D { virtual ~D(); int i; };  // 16（vptr 8 + int 4 + 填充 4）
```

面试延伸：把成员按**从大到小排列**可以减少填充，但要注意可读性，通常靠编译器 `-Wpadded` 提示。""",
    ),
    (
        "C++",
        "内存对齐",
        2,
        r"""为什么要做内存对齐？对齐规则是什么？""",
        r"""**原因**：
1. **硬件要求**：多数 CPU 访问未对齐地址会触发异常或性能惩罚（x86 容忍但慢，ARM 某些指令直接 SIGBUS）。
2. **原子性**：跨缓存行的读写在硬件上不是原子的。
3. **缓存效率**：对齐访问能更好地利用 cache line。

**规则**（以结构体为例）：
1. 每个成员的偏移必须是该成员对齐要求的整数倍，不足则填充。
2. 结构体总大小必须是**最大成员对齐要求**的整数倍（尾部填充），这样数组里每个元素都对齐。
3. `#pragma pack(n)` 或 `__attribute__((packed))` 可强制减小对齐，代价是可能产生未对齐访问。

```cpp
struct S1 { char a; int b; char c; };  // 偏移 0,4,8 → 大小 12
struct S2 { int b; char a; char c; };  // 偏移 0,4,5 → 大小 8
```

**优化技巧**：
- 把大对齐成员放前面。
- 用 `alignas` 显式指定（如 SIMD 需要 16/32 字节对齐）。
- 用 `offsetof` 验证布局。
- 需要网络传输时用 `packed` 或手动序列化，不要直接 `memcpy` 结构体。""",
    ),
    (
        "C++",
        "volatile",
        2,
        r"""`volatile` 的作用是什么？它能保证线程安全吗？""",
        r"""`volatile` 告诉编译器：**这个变量的值可能被程序之外的因素改变，不要优化掉对它的读写**。

它保证：
- 每次访问都真实地从内存读写，不缓存在寄存器里。
- 编译器不会重排两个 volatile 访问之间的顺序（相对顺序）。

它**不保证**：
- **原子性**：`volatile int` 的 `++` 依然不是原子的。
- **线程安全**：没有内存屏障语义，不能替代 `std::atomic` 或互斥量。
- **可见性/顺序**：多核下 CPU 仍可能乱序、缓存不一致。

正确用途：
1. **内存映射 I/O**（`volatile uint32_t* reg`）。
2. **信号处理程序**中的 `volatile sig_atomic_t` 标志。
3. 与 `setjmp/longjmp` 配合的局部变量。

```cpp
volatile int flag = 0;   // ❌ 不能拿来当线程间标志

std::atomic<bool> flag;  // ✅ 线程间通信应该用这个
```

面试常见陷阱：拿 `volatile` 当"轻量级锁"是错的，它解决的是"编译器优化"，不是"并发"。""",
    ),
    (
        "C++",
        "野指针,悬垂指针",
        1,
        r"""什么是野指针和悬垂指针？怎么避免？""",
        r"""**野指针（wild pointer）**：未初始化的指针，指向随机地址。
```cpp
int* p;      // p 是野指针
*p = 1;      // ❌ UB
```
**悬垂指针（dangling pointer）**：指向的对象已销毁（`delete` 后、栈对象离开作用域后）。
```cpp
int* p = new int(3);
delete p;    // p 变成悬垂指针，但地址还"看着像"有效
*p = 5;      // ❌ UB，可能"看起来正常"最危险
```

**避免手段**：
1. **初始化**：指针定义时就置 `nullptr`。
2. **delete 后置空**：`delete p; p = nullptr;`。
3. **优先智能指针**：`unique_ptr` / `shared_ptr` 自动管理生命周期。
4. **不要返回局部变量的地址**。
5. **容器扩容/删除后旧迭代器会失效**，不要继续用。
6. **`shared_ptr` 用 `weak_ptr` 打破循环引用**。

检测工具：ASan（`-fsanitize=address`）、Valgrind、`-D_GLIBCXX_DEBUG`（检查迭代器误用）。""",
    ),
    (
        "C++",
        "nullptr,NULL",
        1,
        r"""`nullptr` 和 `NULL` 有什么区别？""",
        r"""`NULL` 通常是 `0` 或 `0L`（`#define NULL 0`），本质是**整数**。
`nullptr` 是 C++11 引入的 `std::nullptr_t` 类型的字面量，**不是整数**。

问题在于重载决议：

```cpp
void f(int);
void f(char*);

f(NULL);     // ❌ 二义性：0 能被当作整数，也能当作空指针常量
f(nullptr);  // ✅ 一定匹配 f(char*)
```

此外：
- `NULL` 在模板参数推导中会推出 `int`。
- `nullptr` 可以隐式转换成任意指针类型和 `bool`，但不能隐式转成整数（需要显式 `reinterpret_cast`）。
- `sizeof(nullptr) == sizeof(void*)`，`sizeof(NULL)` 取决于平台（可能是 4 或 8）。

**结论**：现代 C++ 一律用 `nullptr`；`NULL` 只在维护 C 兼容代码时出现。""",
    ),
    (
        "C++",
        "override,重载,隐藏",
        2,
        r"""重载（overload）、重写（override）、隐藏（hide）有什么区别？""",
        r"""| 概念 | 发生位置 | 条件 |
|---|---|---|
| **重载** | 同一作用域 | 函数名相同、参数列表不同；返回值不参与 |
| **重写** | 派生类覆盖基类虚函数 | 签名完全相同（含 const、引用限定符），基类函数是 `virtual` |
| **隐藏** | 派生类同名函数遮蔽基类所有同名重载 | 只要名字相同，哪怕参数不同也隐藏 |

隐藏是最容易踩的坑：

```cpp
struct Base {
    void f(int);
    virtual void g();
};
struct Derived : Base {
    void f(double);            // 隐藏了 Base::f(int)
    void g() override;         // 重写
};

Derived d;
d.f(1);          // 调用 Derived::f(double)，Base::f(int) 被隐藏
d.Base::f(1);    // 显式调用基类版本
```

**解决隐藏**：`using Base::f;` 把基类名字引进来。

**防止"假重写"**：给重写函数加 `override`，签名不匹配时编译报错；`final` 禁止进一步重写。

C++23 起还有 `override`/`final` 之外的多重继承同名歧义问题，需要显式限定。""",
    ),
    (
        "C++",
        "名字修饰,mangling",
        2,
        r"""什么是名字修饰（name mangling）？为什么需要它？""",
        r"""为实现**函数重载**和**命名空间/类作用域**，编译器把 C++ 函数名编码成唯一的链接符号，这就是 name mangling。

例如 GCC（Itanium ABI）下：

| 源码 | 符号 |
|---|---|
| `void f()` | `_Z1fv` |
| `void f(int)` | `_Z1fi` |
| `void N::f(int,double)` | `_ZN1N1fEid` |
| `int g<int>(int)`（模板实例） | `_Z1gIiEiT_` |

规则要点：
- 前缀 `_Z`，然后是名字长度+名字，再是参数类型编码。
- **返回类型通常不参与**（C++ 允许仅返回类型不同的重载吗？不允许——所以不需要编码返回类型；但函数模板的返回类型参与推导）。

**实践影响**：
1. `nm -C` / `c++filt` 可以把符号还原成可读形式。
2. 跨编译器/跨版本 ABI 不兼容，部分原因就是 mangling 规则不同。
3. 需要跨语言调用时，用 `extern "C"` 或导出 C 接口。
4. 链接报 "undefined reference to `_ZN...`" 时，用 `nm`/`c++filt` 解出真实函数名能快速定位。""",
    ),
    (
        "C++",
        "默认参数,虚函数",
        3,
        r"""虚函数可以有默认参数吗？会有什么问题？""",
        r"""可以，但**默认参数是静态绑定的**，虚函数是**动态绑定**的 —— 两者混用会产生反直觉行为：

```cpp
struct Base {
    virtual void f(int x = 1) { std::cout << "Base " << x; }
};
struct Derived : Base {
    void f(int x = 2) override { std::cout << "Derived " << x; }
};

Base* p = new Derived;
p->f();   // 输出 "Derived 1" 而不是 "Derived 2"
```

原因：默认参数在**编译期**按 `p` 的静态类型 `Base*` 取（得到 1），函数体在**运行期**按动态类型 `Derived` 取。

其它注意点：
- 默认参数只能写在**声明或定义之一**，不能两处都写。
- 默认参数在虚函数里不可作为重载区分依据。
- **不要**用默认参数实现"可选参数"的多态接口，改用重载或 `std::optional`。

**结论**：虚函数与默认参数不要混用；如果必须，保证基类和派生类默认值一致并注释说明。""",
    ),
    (
        "C++",
        "RVO,NRVO,移动语义",
        3,
        r"""什么是 RVO/NRVO？它和移动语义是什么关系？""",
        r"""**RVO（Return Value Optimization）**：返回临时对象时，编译器直接在调用者的空间构造，省略拷贝。
**NRVO（Named RVO）**：返回**具名局部变量**时的同类优化。

```cpp
std::string make() {
    return std::string("hi");   // RVO：直接在返回值处构造
}
std::string make2() {
    std::string s = "hi";
    return s;                    // NRVO：s 就地构造在返回值处
}
```

标准规定了两种层次的保证：
1. **C++17 起，返回纯右值（prvalue）时的拷贝省略是强制的**（guaranteed copy elision），`make()` 中的拷贝**一定不会发生**。
2. NRVO 仍是**可选优化**（几乎所有编译器都做，但不是标准保证）。

与移动语义的关系：
- 如果没有 RVO/NRVO，C++11 之前会调用拷贝构造；C++11 之后会**优先调用移动构造**（因为返回的局部变量是"将亡值"）。
- 所以"返回大对象"在有移动语义后开销大幅下降，但仍可能有一次移动；RVO 能把它变成零拷贝。
- 这就是"不要 `return std::move(local)`"的原因：`std::move` 会把返回值变成右值引用，**反而阻止 NRVO**，强制多一次移动。

```cpp
std::vector<int> f() {
    std::vector<int> v;
    return std::move(v);   // ❌ 错误：破坏 NRVO
}
```""",
    ),
    (
        "C++",
        "explicit,隐式转换",
        2,
        r"""`explicit` 的作用是什么？什么时候必须用？""",
        r"""`explicit` 禁止**单参数构造函数**（或转换运算符）参与**隐式转换**，只允许显式构造。

```cpp
struct A {
    A(int);            // 允许 A a = 1; 这种隐式转换
    explicit A(double); // 禁止 A a = 1.0;
};

void f(A);
f(1);      // 若 A(int) 非 explicit，这里会隐式构造 A
f(A(1));   // 显式构造，总是可以
```

需要 `explicit` 的典型场景：
1. **数值包装类**：`explicit Duration(int ms)` —— 否则 `Duration d = 5;` 会让人误以为 5 是秒还是毫秒。
2. **智能指针**：`explicit shared_ptr(T*)` —— 防止裸指针隐式转成智能指针导致双重释放。
3. **`vector<int> v = 5;`** 这类初始化其实是 `vector(size_type)`，`explicit` 能拦住误写。
4. **C++11 起，`explicit` 也可以加在转换运算符上**；C++20 起支持条件 `explicit(bool)`：

```cpp
template <class T>
struct Wrapper {
    explicit(cond) operator T();   // 按条件决定是否 explicit
};
```

实践中：**除"转换语义就是本意"的少数情况（如 `std::string_view` 从 `const char*`）外，单参数构造函数都该加 `explicit`**。""",
    ),
    (
        "C++",
        "EBO,空基类优化",
        3,
        r"""什么是空基类优化（EBO）？`std::tuple` 为什么需要它？""",
        r"""**EBO（Empty Base Optimization）**：空类作为**基类**时，派生类中不为其分配额外空间。

```cpp
struct Empty {};
struct A { Empty e; int i; };   // sizeof = 8（Empty 占 1 字节 + 3 填充）
struct B : Empty { int i; };    // sizeof = 4（EBO 生效）
```

标准只**允许**不**强制**（除 `[[no_unique_address]]` 的语义外），但主流编译器都实现。

**为什么重要**：
- 标准库大量用"空基类 + 模板"来携带**类型信息**或**标签**而不占内存。
- `std::allocator` 通常是空类，容器继承它以避免对象变大。
- `std::tuple` 用递归继承 + EBO 实现"零开销存储各类型"：每个元素存为一个基类，空类型元素不占空间。

```cpp
// C++20 的 [[no_unique_address]] 是给"成员"而非"基类"的 EBO
struct C {
    [[no_unique_address]] Empty e;
    int i;
};   // sizeof 可以是 4
```

注意：EBO 只对**不同的**空基类生效；两个同类型的空基类仍需要各自可区分的地址。""",
    ),
    (
        "C++",
        "虚函数表,对象模型",
        3,
        r"""C++ 的对象模型是什么？虚函数表（vtable）是怎么工作的？""",
        r"""**核心机制**：
- 含虚函数的类，编译器生成一张**虚函数表（vtable）**，存该类所有虚函数的地址。
- 每个对象里有一个隐藏指针 **vptr**，指向所属类的 vtable（通常放在对象起始处）。
- 调用 `p->f()` 时：从 `p` 取 vptr → 找到 vtable → 按槽位取函数地址 → 调用。这就是**动态绑定**。

```cpp
struct Base { virtual void f(); virtual ~Base(); int a; };
// 64 位下的布局：
// [ vptr (8) ][ a (4) ][ padding (4) ]  => sizeof = 16
```

**派生类重写时**：派生类有自己的 vtable，被重写的函数槽位替换为派生类版本，未重写的沿用基类版本。

**多重继承**：派生类对象含**多个 vptr**（每个含虚函数的基类一个），因此有"指针调整"（调整 `this` 偏移），这是多继承转换指针时地址会变的原因。

**关键性质与代价**：
1. 每个对象多一个指针的空间开销。
2. 一次间接跳转，无法内联（除非 `final` 或 devirtualization）。
3. vptr 在构造/析构期间会变化：**构造期间 vptr 指向当前类的 vtable**，所以在基类构造函数里调用虚函数只会调到基类版本（派生部分还没构造）。
4. vtable 通常放在只读数据段，无额外运行期开销。

**如何验证**：`g++ -fdump-class-hierarchy`（旧）或 `-fdump-lang-class`（新）可打印布局。""",
    ),
    (
        "C++",
        "多重继承,虚继承,菱形继承",
        3,
        r"""多重继承和菱形继承（钻石继承）有什么问题？虚继承是怎么解决的？""",
        r"""**菱形继承**：

```cpp
struct A { int x; };
struct B : A {};
struct C : A {};
struct D : B, C {};      // D 里有两份 A::x —— 二义性
```

```cpp
D d;
d.x = 1;        // ❌ 二义性：是 B::A::x 还是 C::A::x？
d.B::x = 2;     // 必须显式限定
```

**问题**：
1. 数据冗余（两份 `A`）。
2. 二义性。
3. 若 `A` 有虚函数，`D` 会有两个 vptr。

**虚继承**：让 `B`、`C` 虚继承 `A`，使 `D` 只保留**一份** `A` 子对象。

```cpp
struct B : virtual A {};
struct C : virtual A {};
struct D : B, C {};      // 只有一份 A
D d;
d.x = 1;                 // ✅ 唯一的 A::x
```

**代价**：
- 虚基类的偏移**不能在编译期确定**，需要运行期通过 **vbtable（虚基类表）** 查找，访问虚基类成员多一次间接。
- 更复杂的对象布局与指针调整，跨虚基类转换指针代价更高。
- 构造函数中，**只有最派生类负责构造虚基类**，中间类的初始化列表里对虚基类的调用会被忽略。

**实践建议**：虚继承是"接口继承"（无数据）时常用；带数据的菱形继承通常说明设计有问题，优先考虑组合或纯接口多继承。""",
    ),
    (
        "C++",
        "静态成员,定义",
        2,
        r"""为什么类的静态成员变量必须在类外定义？C++17 有什么变化？""",
        r"""类内的 `static int count;` 只是**声明**，不分配存储。**定义**（分配存储）必须放在类外，且不能重复加 `static`：

```cpp
struct A {
    static int count;        // 声明
};
int A::count = 0;            // 定义（在某个 .cpp 中，只能一次）
```

原因：类定义通常放在头文件里、被多个翻译单元包含；如果类内就分配存储，会**违反 ODR**（多次定义）。

**例外**：
- **`static constexpr` 整型**在 C++17 前可以在类内初始化（但 ODR-使用仍需类外定义）；C++17 起 `static constexpr` 成员**隐式 inline**，无需类外定义。
- C++17 起可用 **`inline static`** 直接在类内定义：

```cpp
struct A {
    inline static int count = 0;   // C++17，无需类外定义
};
```

这也是 C++17 后**头文件-only 库里单例计数器**的标准写法。

补充：`static const int N = 10;` 在类内初始化后，若只是当编译期常量用（如数组大小），不需要类外定义；一旦取地址（`&A::N`）就需要定义。""",
    ),
    (
        "C++",
        "友元",
        1,
        r"""`friend` 是做什么的？什么时候该用？""",
        r"""`friend` 授予某个函数或类**访问本类私有/保护成员**的权限。

三种形式：

```cpp
class A {
    int secret = 0;
    friend void f(A&);              // 友元函数
    friend class B;                 // 友元类
    friend std::ostream& operator<<(std::ostream&, const A&);
};
```

**特点**：
- 友元关系**不是双向的**（B 是 A 的友元，不代表 A 是 B 的友元）。
- 友元**不被继承**。
- 友元破坏了封装，但**用对了是好事**：它把"需要访问私有数据"的紧耦合关系**显式声明出来**，比用公有 getter 暴露内部结构更好。

**合理用途**：
1. **运算符重载**（`operator<<`、`operator+` 需要访问私有成员）。
2. **两个紧密协作的类**（如迭代器访问容器、`std::vector` 与它的迭代器）。
3. **测试代码**访问内部状态。

**替代方案**：把需要共享的实现放到 `detail` 命名空间，或用公有接口；现代设计更倾向"用公有接口而非友元"。

注意：`friend` 声明可以在类内任意位置（不受 public/private 影响），因为友元声明本身不是成员。""",
    ),
    (
        "C++",
        "运算符重载",
        2,
        r"""运算符重载有哪些规则和常见的坑？""",
        r"""**不能重载的运算符**：`.`、`::`、`?:`、`sizeof`、`typeid`、`.*`。**不能发明新运算符**，也不能改变运算符的元数（arity）与优先级。

**成员 vs 非成员**：
- **必须是非成员**：`operator<<`/`>>`（左操作数是 `ostream`）、需要隐式转换左操作数时。
- **通常是成员**：`+=`、`[]`、`()`、`->`、一元 `-`。

**常见坑**：

1. **`operator=` 要处理自赋值**：
```cpp
A& operator=(const A& o) {
    if (this == &o) return *this;   // 自赋值保护
    ...
}
```

2. **`operator<<` 返回 `ostream&` 以支持链式调用**，且要 `const&` 参数。
3. **不要重载 `&&`、`||`、`,`** —— 会丢失短路求值。
4. **`operator[]` 不检查越界**，`at()` 才检查；`const` 版本要返回 `const` 引用。
5. **`operator+` 用非成员 + 返回值**，避免修改自身：
```cpp
A operator+(const A& a, const A& b) { A r = a; r += b; return r; }
```
6. **`operator bool` 要 `explicit`**，否则 `if (obj)` 之外还会参与算术转换。
7. **`operator->` 返回指针**，支持 `ptr->member` 的链式穿透；`operator->*` 罕见。
8. **后置 `++` 用一个 `int` 哑参数区分**：
```cpp
T& operator++();        // 前置
T  operator++(int);     // 后置
```
9. 三/五法则：定义了拷贝构造、拷贝赋值、析构中任一个，通常都要定义全部（或 `= delete`/`= default`）。

**原则**：运算符重载要**符合直觉**（`+` 就该是"相加"），不要滥用 `operator,` 或给无意义类型重载算术。""",
    ),
    (
        "C++",
        "三五法则,拷贝控制",
        2,
        r"""什么是三法则、五法则、零法则？""",
        r"""**三法则（Rule of Three）**：如果类需要自定义**析构函数、拷贝构造函数、拷贝赋值运算符**中的任何一个，通常三个都需要（因为都要管理同一份资源）。

```cpp
class Buffer {
    int* data_; size_t n_;
public:
    ~Buffer();                            // 释放
    Buffer(const Buffer&);                // 深拷贝
    Buffer& operator=(const Buffer&);     // 深拷贝 + 自赋值保护
};
```

**五法则（Rule of Five）**：C++11 引入移动语义后，再加上**移动构造**和**移动赋值**：

```cpp
Buffer(Buffer&&) noexcept;             // 偷走资源
Buffer& operator=(Buffer&&) noexcept;
```
移动操作要标 `noexcept`，否则 `std::vector` 扩容时会退回拷贝（因为要强异常安全保证）。

**零法则（Rule of Zero）**：**更好的做法**是不写任何这些函数，让编译器生成的版本正确工作 —— 手段是把资源交给**智能指针或容器**管理：

```cpp
class Buffer {
    std::vector<int> data_;   // 自带正确的拷贝/移动/析构
};
```

**为什么零法则最好**：手写拷贝控制是错误高发区（自赋值、异常安全、移动后状态），而标准库已验证过的组件不会出错。

**特例**：定义了析构或拷贝操作，编译器**不再隐式生成移动操作**（会退化成拷贝），这也常是"对象没有移动"的原因。""",
    ),
    (
        "C++",
        "拷贝构造,const引用",
        2,
        r"""拷贝构造函数为什么参数必须是 `const T&`？不这样会怎样？""",
        r"""因为**按值传参本身就会调用拷贝构造**，形成无限递归：

```cpp
class A {
    A(A o);   // ❌ 编译错误：按值传参需要拷贝，而拷贝又需要先构造参数 → 无限递归
};
```

标准直接规定拷贝构造的第一个参数必须是 `T&`、`const T&`、`volatile T&` 或 `const volatile T&`。

**为什么要 `const`**：
- 允许从 `const` 对象拷贝（`const A a; A b = a;`）。
- 允许从临时量（右值）拷贝。

**为什么要引用**：
- 避免递归。
- 避免无谓拷贝。

补充：
- 若同时有 `A(const A&)` 和 `A(A&&)`，右值优先匹配移动版本。
- **`A(A&)`（非 const）是合法的**，但会拒绝从 `const` 对象拷贝，通常不是想要的。
- 拷贝构造**可以有其它带默认值的参数**，但那会变成普通构造函数。
- 传参时的隐式转换可能触发拷贝构造，所以"拷贝构造"经常在初始化、传参、返回时被隐式调用；C++17 后返回 prvalue 时会被省略。""",
    ),
    (
        "C++",
        "深拷贝,浅拷贝",
        1,
        r"""什么是浅拷贝和深拷贝？""",
        r"""**浅拷贝**：逐位复制成员，指针成员只复制**指针值**（两个对象指向同一块内存）。
**深拷贝**：指针成员指向的内容也复制一份，两个对象互不影响。

编译器生成的拷贝构造/赋值是**浅拷贝**：

```cpp
class S {
    char* buf_;
public:
    S(const S&) = default;   // 浅拷贝：两个对象的 buf_ 指向同一块
};
```

若类管理资源（堆内存、文件句柄、锁），浅拷贝会导致：
1. **双重释放**：两个对象析构时都 `delete buf_` → 崩溃。
2. **悬垂**：一个对象改了内存，另一个"莫名其妙"也变了。

**解决**：
- **深拷贝**：手动 `new` + `memcpy`，但要处理异常安全与自赋值。
- **移动语义**：转移所有权，源对象置空。
- **`std::shared_ptr`**：共享所有权，引用计数管理。
- **`= delete` 禁止拷贝**：只允许移动（`unique_ptr` 风格）。

```cpp
class S {
    std::unique_ptr<char[]> buf_;   // 零法则：不可拷贝，可移动
};
```""",
    ),
    (
        "C++",
        "default,delete",
        1,
        r"""`= default` 和 `= delete` 分别有什么用？""",
        r"""**`= default`**：显式要求编译器生成默认实现。
- 用途1：写了自定义构造/析构后，想恢复编译器版本。
- 用途2：改变访问级别或虚特性（如 `virtual ~A() = default;`）。
- 用途3：在类外定义以打破头文件依赖：
```cpp
// A.h
class A { public: ~A(); };
// A.cpp
A::~A() = default;   // 让析构在 .cpp 里生成，头文件不暴露实现
```

**`= delete`**：显式禁用某个函数。
```cpp
class NonCopyable {
    NonCopyable(const NonCopyable&) = delete;
    NonCopyable& operator=(const NonCopyable&) = delete;
};
```
比放到 `private` 里不实现更好：**错误在编译期以清晰信息报出**，而不是链接期。

**其它用途**：
- 禁用不想要的隐式转换：
```cpp
void f(int);
void f(double) = delete;   // 禁止 f(3.14) 的隐式转换
```
- **模板禁用特定实例化**：
```cpp
template <class T> void f(T) = delete;   // 禁止所有 T，需特化才能用
```

注意：`= delete` 的函数仍参与重载决议（选中后报错），这正是它能"精准拦截"的原因；而 `private` 未定义版本是链接期才报错。""",
    ),
    (
        "C++",
        "模板特化,偏特化",
        2,
        r"""什么是模板全特化和偏特化？函数模板能偏特化吗？""",
        r"""**全特化（explicit specialization）**：为特定类型提供完全独立的实现。

```cpp
template <class T> struct Traits { static const char* name(); };
template <> struct Traits<int> { static const char* name() { return "int"; } };
```

**偏特化（partial specialization）**：只固定部分模板参数，仍保留泛型部分。

```cpp
template <class T, class U> struct Pair { };          // 主模板
template <class T> struct Pair<T, int> { };            // 偏特化：第二个固定为 int
template <class T> struct Pair<T*, T*> { };            // 偏特化：两个都是指针
```

偏特化也是 `std::vector<T*>`、`std::is_pointer` 等的实现基础。

**关键限制：函数模板不能偏特化**，只能全特化。

```cpp
template <class T> void f(T);            // 主模板
template <> void f<int>(int);            // ✅ 全特化
template <class T> void f<T*>(T*);       // ❌ 编译错误：函数模板不支持偏特化
```

**替代方案**：用**重载**或**委托到类模板**（tag dispatch / class template partial specialization）：

```cpp
template <class T> struct helper { static void f(T); };
template <class T> struct helper<T*> { static void f(T*); };   // 偏特化放在类模板里

template <class T> void f(T x) { helper<T>::f(x); }
```

**顺序要求**：特化必须出现在**首次使用之前**，否则是 `ill-formed, no diagnostic required`（实际上往往静默走主模板，非常难查）。""",
    ),
    (
        "C++",
        "SFINAE,enable_if",
        3,
        r"""什么是 SFINAE？`std::enable_if` 是怎么用的？""",
        r"""**SFINAE = Substitution Failure Is Not An Error**：模板实参替换失败时，**不报错，只是把该候选从重载集中移除**。

```cpp
template <class T>
typename T::value_type f(T);     // 若 T 没有 value_type，替换失败 → 静默丢弃

template <class T>
void f(T);                        // 兜底
```
（但这个例子会二义性；实际要配合 enable_if 约束。）

**`std::enable_if`**：

```cpp
template <bool B, class T = void>
struct enable_if {};                 // B == false：无 type 成员 → 替换失败
template <class T>
struct enable_if<true, T> { using type = T; };
```

三种常见写法：

```cpp
// 1) 返回类型
template <class T>
typename std::enable_if<std::is_integral<T>::value, int>::type
f(T);

// 2) 模板参数默认值（推荐，不污染签名）
template <class T, class = std::enable_if_t<std::is_integral<T>::value>>
int f(T);

// 3) 模板非类型参数
template <class T, std::enable_if_t<std::is_integral<T>::value, int> = 0>
int f(T);
```

**C++17 起**，优先用 **`if constexpr`** 替代部分场景；**C++20 起**用 **concepts/requires**，可读性远好于 SFINAE：

```cpp
template <std::integral T> int f(T);
template <class T> requires std::integral<T> int f(T);
```

**注意**：SFINAE 只适用于"模板参数替换阶段"的失败；函数体里的错误、硬错误（如 `static_assert` 失败）不适用。""",
    ),
    (
        "C++",
        "可变参数模板,折叠表达式",
        3,
        r"""可变参数模板（variadic template）怎么用？折叠表达式是什么？""",
        r"""**可变参数模板**用 `...` 接受任意数量、任意类型的参数：

```cpp
template <class... Ts>
void f(Ts... args) {          // 值接收
    g(args...);               // 展开
    sizeof...(args)           // 参数个数
}

template <class... Ts>
void f(const Ts&... args) {   // 完美转发时用 Ts&&... + std::forward
}
```

**C++11/14 的展开方式**（递归 + 递归终止）：

```cpp
void print() {}                        // 终止
template <class T, class... Rest>
void print(const T& first, const Rest&... rest) {
    std::cout << first;
    print(rest...);
}
```

**C++17 折叠表达式**（fold expression）把它变成一行：

```cpp
template <class... Ts>
void print(const Ts&... ts) {
    ((std::cout << ts << ' '), ...);    // 一元右折叠
}

template <class... Ts>
auto sum(const Ts&... ts) {
    return (ts + ...);                   // (0 + ...) 是二元折叠，空参数时给初值
}
```

四种形式：

| 形式 | 展开 |
|---|---|
| `(pack op ...)` | 一元右折叠 |
| `(... op pack)` | 一元左折叠 |
| `(init op ... op pack)` | 二元右折叠 |
| `(pack op ... op init)` | 二元左折叠 |

**典型应用**：`std::make_unique` 转发、日志、`std::tuple` 构造、类型列表遍历。

一个坑：空参数包时，一元折叠的运算符决定了结果（`&&` → true，`+` → 编译错误需用二元折叠给初值）。""",
    ),
    (
        "C++",
        "CRTP",
        3,
        r"""什么是 CRTP？它能解决什么问题？""",
        r"""**CRTP（Curiously Recurring Template Pattern）**：派生类把自己作为模板参数传给基类。

```cpp
template <class Derived>
struct Base {
    void interface() {
        static_cast<Derived*>(this)->implementation();   // 静态多态
    }
};

struct D : Base<D> {
    void implementation();
};
```

**核心价值：编译期多态**（static polymorphism）
- 无需虚函数、无 vptr 开销、可内联。
- 适合：运算符的"统一实现"、`enable_shared_from_this`、Mixin。

**典型用途**：

1. **统一提供 `operator!=`/`operator>` 等**（只需派生类实现 `==`、`<`）。
2. **`std::enable_shared_from_this<T>`** 就是 CRTP 实现。
3. **计数器 Mixin**：每个派生类各自一份静态计数。
```cpp
template <class T> struct Counter {
    static int count;
    Counter() { ++count; }
};
struct A : Counter<A> {};
struct B : Counter<B> {};   // A 和 B 各有独立的 count
```
4. **策略注入 / 编译期接口**。

**注意**：
- `Base` 里访问派生类成员要靠 `static_cast<Derived*>(this)`，因为此时 `Derived` 还不完整。
- 不要在基类构造/析构里调用 `static_cast<Derived*>(this)->...`，此时派生部分未构造，是 UB。
- 这也是"Mixin"和"策略模式零开销实现"的常见手法。

**与虚函数的取舍**：类型在编译期已知、追求性能 → CRTP；需要运行期多态（异构容器、插件） → 虚函数。""",
    ),
    (
        "C++",
        "type_traits",
        2,
        r"""`<type_traits>` 里常用的工具有哪些？举几个实际用法。""",
        r"""**分类**：

| 类别 | 例子 |
|---|---|
| 类型判断 | `is_integral`, `is_pointer`, `is_same`, `is_base_of`, `is_convertible` |
| 类型变换 | `remove_reference`, `add_const`, `decay`, `common_type`, `conditional` |
| 属性判断 | `is_trivial`, `is_trivially_copyable`, `is_nothrow_move_constructible` |
| `_v` / `_t` 简写 | `is_integral_v<T>`, `remove_reference_t<T>`（C++17） |

**实际用法**：

1. **完美转发**：
```cpp
template <class T>
void f(T&& x) { g(std::forward<T>(x)); }
```
`std::forward` 内部就用 `remove_reference` + `conditional`。

2. **返回类型推导**：
```cpp
template <class A, class B>
auto add(A a, B b) -> decltype(a + b);
// 或 C++14: auto add(A a, B b) { return a + b; }
```

3. **按类型选择实现**（tag dispatch / if constexpr）：
```cpp
template <class T>
void serialize(T& v) {
    if constexpr (std::is_arithmetic_v<T>) { raw_write(v); }
    else { v.serialize(); }
}
```

4. **`std::declval<T>()`**：在 `decltype` 里"假装"有一个 `T` 对象，用于探测表达式是否合法（SFINAE 检测惯用法）：
```cpp
template <class T, class = void>
struct has_size : std::false_type {};
template <class T>
struct has_size<T, std::void_t<decltype(std::declval<T>().size())>>
    : std::true_type {};
```

5. **`std::void_t`**（C++17）：把任意类型列表"吃掉"变成 `void`，专用于 SFINAE 探测。""",
    ),
    (
        "C++",
        "编译期多态,运行期多态",
        2,
        r"""编译期多态和运行期多态有什么区别？怎么选？""",
        r"""| 维度 | 编译期多态 | 运行期多态 |
|---|---|---|
| 实现手段 | 模板、重载、CRTP、`if constexpr`、concepts | 虚函数、函数指针、`std::function` |
| 决议时机 | 编译期 | 运行期 |
| 开销 | 零运行时开销，可内联 | vptr + 一次间接跳转，通常不能内联 |
| 代码体积 | 每种实例化一份代码（可能膨胀） | 一份代码 |
| 能否异构容器 | 不能（类型必须在编译期确定） | 能（`vector<unique_ptr<Base>>`） |
| 是否需要重编译 | 改类型要重编译 | 可动态加载（插件） |
| 错误信息 | 模板错误较难读 | 较直观 |

**选择依据**：
- **类型在编译期已知、追求性能** → 编译期多态（如数值库、容器、`std::sort` 的比较器模板）。
- **需要运行时决定行为、跨模块扩展** → 运行期多态（插件系统、GUI 事件、异构集合）。
- 混合：**类型擦除**（type erasure）——用虚函数包住模板，对外暴露统一接口。`std::function`、`std::any`、`std::shared_ptr<void>` 都是这个思路：

```cpp
class AnyCallable {
    struct Concept { virtual void call() = 0; };
    template <class F> struct Model : Concept {
        F f; void call() override { f(); }
    };
    std::unique_ptr<Concept> p_;
public:
    template <class F> AnyCallable(F f) : p_(new Model<F>{std::move(f)}) {}
    void operator()() { p_->call(); }
};
```

**性能对比**：虚函数调用的间接跳转在有大量分支时可能成为瓶颈（分支预测失败）；热路径上常考虑去虚化（`final`、devirtualization）或改回模板。""",
    ),
    (
        "C++",
        "constexpr,consteval",
        2,
        r"""`constexpr`、`const`、`consteval`、`constinit` 有什么区别？""",
        r"""| 关键字 | 含义 | 求值时机 |
|---|---|---|
| `const` | 只读；**可能**是运行期确定 | 不限定 |
| `constexpr` | **可以**在编译期求值（若上下文需要） | 编译期或运行期均可 |
| `consteval`（C++20） | **必须**在编译期求值（immediate function） | 只能编译期 |
| `constinit`（C++20） | 变量必须**静态初始化**（避免静态初始化顺序问题） | 编译期 |

```cpp
const int a = f();          // 运行期初始化也行
constexpr int b = f();      // ❌ f 必须能被编译期求值
```

**C++14 起 `constexpr` 函数可以含循环、局部变量、if**；C++17 起支持 `constexpr` lambda；C++20 起支持 `constexpr` 动态分配、`constexpr` 虚函数、`std::vector`/`std::string` 的 constexpr 用法。

```cpp
constexpr int fib(int n) {
    int a = 0, b = 1;
    for (int i = 0; i < n; ++i) { int t = a + b; a = b; b = t; }
    return a;
}
static_assert(fib(10) == 55);   // 编译期求值
```

**为什么关心**：
- 编译期求值 = **零运行时开销**，且可用于 `static_assert`、数组大小、模板参数。
- `consteval` 用于"必须编译期算完"的场景（编译期解析、格式串校验）。
- `constinit` 解决**静态初始化顺序问题**（跨编译单元的全局对象在 `main` 之前初始化的顺序未定义）：
```cpp
constinit int x = compute();   // 保证静态初始化，不会在运行期"迟到"
```

注意：`constexpr` 变量是隐式 `const`；`constexpr` 成员函数在类里也是隐式 `const`（C++14 前）；C++23 起可以用 `constexpr` 做更多编译期计算。""",
    ),
    (
        "C++",
        "auto,decltype,推导规则",
        2,
        r"""`auto` 的推导规则是什么？它和 `decltype` 有什么不同？""",
        r"""**`auto` 用模板实参推导规则**（丢弃顶层 `const`、引用，数组/函数退化为指针）：

```cpp
const int  ci = 0;
auto a = ci;        // int（顶层 const 被丢弃）
auto& b = ci;       // const int&（引用会保留 const）
auto c = {1, 2};    // std::initializer_list<int>

int arr[3];
auto d = arr;       // int*（退化为指针）
```

**特例**：`auto&&` 是**万能引用**（转发引用），配合 `std::forward` 做完美转发：
```cpp
template <class T> void f(T&& x);   // T&& 是万能引用（有类型推导时）
```

**`decltype` 精确得多**：
- `decltype(expr)`：expr 是**名字**时得到其声明类型（含 const/引用）；否则按值类别推导。
- `decltype((expr))`：**多加一层括号**，总是得到引用类型（左值 → `T&`）。

```cpp
int x = 0; const int& r = x;
decltype(x)  a;   // int
decltype(r)  b;   // const int&
decltype((x)) c;  // int&（因为 (x) 是左值表达式）
```

**`decltype(auto)`**（C++14）：用 `decltype` 规则推导返回类型，保留引用，常用于转发函数：
```cpp
template <class F, class... A>
decltype(auto) call(F&& f, A&&... a) {
    return std::forward<F>(f)(std::forward<A>(a)...);
}
```

**返回值推导对比**：
| 写法 | 结果 |
|---|---|
| `auto` | 按值，丢引用和顶层 const |
| `auto&` | 左值引用（可加 const） |
| `decltype(auto)` | 完全按 decltype 规则（保留引用与 const） |

工具：`-std=c++17` + 编译器错误信息，或 `typeid(x).name()`（注意不精确）；调试模板类型常用 `static_assert(std::is_same_v<decltype(x), T>)` 或经典的 incomplete template trick。""",
    ),
    (
        "C++",
        "结构化绑定",
        2,
        r"""什么是结构化绑定？它有哪些限制？""",
        r"""**结构化绑定**（C++17）把聚合类型"拆开"到多个名字：

```cpp
std::pair<int,std::string> p{1, "a"};
auto [id, name] = p;                        // 拷贝
auto& [rid, rname] = p;                     // 引用，可修改 p
const auto& [cid, cname] = p;               // 只读引用

std::map<int,int> m;
for (const auto& [k, v] : m) { ... }

struct Point { int x, y; };
Point pt{1, 2};
auto [x, y] = pt;
```

**支持的类型**：
1. **数组**（C 风格数组）。
2. **聚合/平凡结构体**（公开非静态成员）。
3. **实现 tuple 协议的类型**：`std::tuple_size`、`std::tuple_element`、`get<I>`（`std::pair`、`std::tuple`、`std::array`）。

**常见坑**：
- 绑定的是**隐藏对象的成员**，不是原对象的引用（除非用引用形式），所以值绑定是拷贝。
- **不能显式指定类型**（`auto [int x, int y]` 非法）。
- 结构体**成员顺序必须与绑定顺序一致**，否则静默错位。
- 结构化绑定**不能用作 lambda 捕获**（C++17），C++20 起可以。
- 变量**不是独立的变量**，是"绑定名"，`decltype` 行为略特殊（C++20 明确）。

**实用技巧**：解构 `insert` 返回值：
```cpp
if (auto [it, ok] = m.insert({1, 2}); ok) { ... }
```""",
    ),
    (
        "C++",
        "完美转发,引用折叠",
        3,
        r"""什么是完美转发？引用折叠规则是什么？""",
        r"""**完美转发**指把参数**原样**（保留左/右值和 const）转给下层函数，是工厂函数、`emplace` 的基础。

```cpp
template <class T, class... Args>
std::unique_ptr<T> make_unique(Args&&... args) {
    return std::unique_ptr<T>(new T(std::forward<Args>(args)...));
}
```

**引用折叠规则**（只在类型推导/别名中出现）：

| 组合 | 结果 |
|---|---|
| `T& &` | `T&` |
| `T& &&` | `T&` |
| `T&& &` | `T&` |
| `T&& &&` | `T&&` |

口诀：**只要有一个是左值引用，结果就是左值引用**。

**`T&&` 什么时候是万能引用**：
- 有**类型推导**（模板参数 `T` 需要被推导）时，`T&&` 是万能引用。
- 若类型已确定（`int&&`、`std::vector<int>&&`），就是普通右值引用。
- `const T&&` **不是**万能引用。

**推导细节**：`f(x)` 中 x 是左值 → `T` 推导为 `T&`，`T&&` 折叠成 `T&`；x 是右值 → `T` 推导为 `T`，形参为 `T&&`。

**`std::forward<T>(x)`** 做的就是按 `T` 决定再转成左值还是右值：
```cpp
// 简化实现
template <class T>
constexpr T&& forward(std::remove_reference_t<T>& x) noexcept {
    return static_cast<T&&>(x);
}
```

**常见坑**：
- 转发后**不要再用**被转发的对象（可能已被移动）。
- 构造函数里转发时，若构造函数是 `explicit`，转发会丢失 `explicit`（C++17 前的已知问题，`std::make_unique` 因此不能完美转发初始化列表）。
- `std::forward` 只能用于**模板推导出的** `T`，不能手写错。""",
    ),
    (
        "C++",
        "move,forward",
        2,
        r"""`std::move` 和 `std::forward` 有什么区别？""",
        r"""**`std::move`：无条件地把实参转成右值**（本质是一次 `static_cast<T&&>`），表示"我不再需要这个对象了"。
**`std::forward`：有条件地转发**，按模板推导出的 `T` 决定保持左值还是转成右值。

```cpp
// std::move 的简化实现
template <class T>
constexpr std::remove_reference_t<T>&& move(T&& x) noexcept {
    return static_cast<std::remove_reference_t<T>&&>(x);
}

// std::forward 的简化实现
template <class T>
constexpr T&& forward(std::remove_reference_t<T>& x) noexcept {
    return static_cast<T&&>(x);
}
```

**语义区别**：
- `std::move`：**我确定要放弃它** —— 用于把局部变量/成员移交给别人。
- `std::forward`：**我不确定调用者给的是左值还是右值** —— 用于转发。

**常见错误**：
1. **`return std::move(local);`** —— 破坏 NRVO，反而可能多一次移动。
2. **对 `const` 对象 `std::move`** —— 得到 `const T&&`，移动构造接受 `T&&` 所以不匹配，**会静默退回拷贝**：
```cpp
const std::string s = "x";
std::string t = std::move(s);   // 实际是拷贝！
```
3. **在转发后继续使用参数**。
4. **对已经 `std::move` 过的对象做除赋值/析构外的操作** —— 处于"有效但未指定"状态。

**一句话总结**：`move` 是"转成右值"，`forward` 是"保持原样转下去"。""",
    ),
    (
        "C++",
        "lambda,捕获",
        2,
        r"""lambda 是什么？捕获列表有哪些坑？""",
        r"""lambda 是**编译器生成的匿名函数对象**（闭包），捕获的变量成为其成员。

```cpp
int x = 1;
auto f = [x](int y) { return x + y; };       // 按值捕获（拷贝）
auto g = [&x](int y) { return x + y; };      // 按引用捕获
auto h = [=] { return x; };                  // 全部按值
auto k = [&] { return x; };                  // 全部按引用
auto m = [p = std::make_unique<int>(1)] { return *p; };  // 初始化捕获（C++14）
```

**坑**：

1. **`[&]` 捕获局部变量的引用，若 lambda 活得比变量长 → 悬垂**：
```cpp
std::function<void()> f;
{
    int x = 1;
    f = [&x]{ std::cout << x; };   // ❌ x 已销毁
}
f();   // UB
```

2. **`[=]` 在成员函数里捕获的是 `this` 指针（按值），不是成员副本** —— 对象销毁后调用同样 UB。C++20 起 `[=]` 捕获 `this` 已弃用，要显式 `[*this]` 或 `[this]`（并注意生命周期）。

3. **`mutable`**：按值捕获的变量在 lambda 内默认是 `const`，要改需 `mutable`（改动的是 lambda 内部的副本）：
```cpp
int c = 0;
auto f = [c]() mutable { return ++c; };
f(); f();   // 返回 1, 2 —— 但外部的 c 仍是 0
```

4. **`std::function` 会为 lambda 分配堆内存**（大闭包），热路径上优先用 `auto` 存 lambda 或模板参数，避免类型擦除的开销。

5. **lambda 的大小 = 捕获的变量大小（+ 对齐）**，捕获大对象要当心；`[&]`/`[=]` 只捕获**用到的**变量（未用的是 ODR-use 才捕获）。

6. **泛型 lambda**（C++14）：`[](auto x){...}` 等价于模板 `operator()`；C++20 起可写 `[]<class T>(T x){}`。

**存储与线程**：lambda 若被拷贝到其他线程，注意捕获的对象是否线程安全；捕获引用跨线程尤其危险。""",
    ),
    (
        "C++",
        "std::function",
        2,
        r"""`std::function` 是怎么实现的？开销在哪？""",
        r"""`std::function<Sig>` 是**类型擦除**容器：可存任意可调用对象（函数指针、lambda、仿函数、成员函数绑定）只要签名兼容。

**实现原理**（简化）：
```cpp
template <class Sig> class function;   // 主模板
template <class R, class... A>
class function<R(A...)> {
    struct Base { virtual R call(A...) = 0; virtual ~Base() = default; };
    template <class F> struct Model : Base {
        F f;
        R call(A... a) override { return f(std::forward<A>(a)...); }
    };
    std::unique_ptr<Base> p_;    // 或 SBO 的小缓冲
public:
    template <class F> function(F f) : p_(new Model<F>{std::move(f)}) {}
    R operator()(A... a) const { return p_->call(...); }
};
```

**开销**：
1. **一次虚函数调用**（间接跳转），不能跨类型内联。
2. **可能堆分配**：闭包超过 SBO（small buffer optimization，典型 16~32 字节）时 heap alloc。libstdc++/libc++ 都做了 SBO。
3. **大小固定**：`sizeof(std::function)` 通常 32 字节（含 SBO 缓冲），捕获大对象会触发分配。

**优化建议**：
- 泛型上下文里**优先用模板参数或 `auto`** 接 lambda，零开销：
```cpp
template <class F> void run(F f) { f(); }   // 可内联
void run(std::function<void()> f);          // 有间接调用
```
- 需要存储异构可调用对象时才用 `std::function`。
- C++23 有 `std::move_only_function`（支持只移类型，且不要求可拷贝）。

**与函数指针对比**：

| | 函数指针 | std::function |
|---|---|---|
| 能否存有状态 lambda | ❌ | ✅ |
| 开销 | 无 | 间接调用 + 可能分配 |
| 大小 | 8 字节 | 通常 32 字节 |

**注意**：`std::function` 若为空时调用 `operator()` 会抛 `std::bad_function_call`；`std::function<...> == nullptr` 可用于判空。""",
    ),
    (
        "C++",
        "std::bind",
        2,
        r"""`std::bind` 有什么问题？为什么现在推荐用 lambda？""",
        r"""`std::bind`（C++11）可以绑定参数、重排参数、绑定成员函数：

```cpp
using namespace std::placeholders;
void f(int a, int b);
auto g = std::bind(f, 1, _1);
g(2);        // f(1, 2)

struct S { void m(int); };
S s;
auto h = std::bind(&S::m, &s, _1);
h(3);        // s.m(3)
```

**问题**：

1. **可读性差**：`std::bind(f, 1, _2, _1)` 需要对照占位符数位次，容易错。
2. **类型推导不直观**：返回类型是实现定义的（`std::_Bind<...>`），错误信息极长，调试器里是 `_Bind_helper<...>` 这样的名字。
3. **完美转发的坑**：`std::bind` 默认**按值存储**实参并**移动**到调用点 —— 对引用语义不友好；想把左值按引用传需要 `std::ref`：
```cpp
int x = 1;
auto f = std::bind(g, x);          // ❌ 拷贝 x
auto h = std::bind(g, std::ref(x)); // ✅ 引用
```
4. **与重载函数/模板配合困难**：`std::bind(f, ...)` 无法推导重载函数到底选哪个，需要 `static_cast` 消歧义。
5. **不能完美转发**：`bind` 的 `operator()` 内部有 `decay` 语义，转发能力不如 lambda。

**lambda 的等价写法**（C++14 起，且支持泛型参数与捕获）：
```cpp
auto g = [](int b) { return f(1, b); };       // 清晰、可内联、类型明确
auto h = [&s](int x) { s.m(x); };
```

**结论**：除少数历史代码或需要"占位符重排"的场景，一律用 lambda。`std::bind` 已被视为过时（C++ 社区共识，如 Scott Meyers 的 Effective Modern C++ Item 34 标题就是"Prefer lambdas to std::bind"）。""",
    ),
    (
        "C++",
        "容器选择",
        2,
        r"""`vector`、`list`、`deque`、`map`、`unordered_map` 分别适合什么场景？""",
        r"""| 容器 | 底层 | 随机访问 | 中间插删 | 查找 | 内存 |
|---|---|---|---|---|---|
| `vector` | 连续数组 | O(1) | O(n) | O(n) 线性 | 紧凑，缓存友好 |
| `deque` | 分段连续（map of blocks） | O(1) | 头尾 O(1) | O(n) | 略大，头尾扩张不搬移 |
| `list` | 双向链表 | O(n) | O(1)（有迭代器） | O(n) | 每节点两个指针 + 分配开销 |
| `forward_list` | 单向链表 | O(n) | O(1)（有前置） | O(n) | 更省 |
| `map`/`set` | 红黑树 | O(log n) | O(log n) | O(log n) 有序 | 每节点指针开销 |
| `unordered_map`/`set` | 哈希表 | 平均 O(1) | 平均 O(1) | 平均 O(1)，最坏 O(n) | 桶 + 节点 |
| `array` | 定长数组 | O(1) | 不支持 | O(n) | 无额外开销 |

**选择原则**：

1. **默认用 `vector`** —— 连续内存带来的缓存局部性通常碾压"复杂度更优"的链表。现代 CPU 上 `vector` 的线性查找常常快于 `list` 的遍历。
2. **需要有序、范围查询、有序遍历** → `map`/`set`。
3. **只需快速查找、不要求顺序** → `unordered_map`/`unordered_set`。
4. **频繁在头部插删** → `deque`（比 `vector` 的头部插入 O(n) 好）。
5. **需要稳定引用/迭代器**（插入不影响其它元素地址） → `list`/`map`。
6. **元素极大且拷贝昂贵** → 考虑存 `unique_ptr`（`vector<unique_ptr<T>>`）避免扩容搬移。
7. **范围确定且定长** → `std::array`。

**实践的反直觉点**：
- `list` 在现代 CPU 上往往**不如** `vector`，因为链表遍历是随机内存访问、缓存命中率极低，通常被称为"几乎不要用 list"。
- `unordered_map` 的哈希计算与冲突链在缓存上也不友好；元素少时（< 几十）`vector` 线性查找反而更快。
- `map` 的迭代器与引用**稳定**（节点不会因插删而移动），这是它相对 `vector` 的重要优势。""",
    ),
    (
        "C++",
        "哈希表",
        2,
        r"""`std::unordered_map` 的哈希冲突怎么解决？负载因子和 rehash 是什么？""",
        r"""**实现**：标准只要求"平均 O(1)"，主流实现（libstdc++、libc++、MSVC）都是**链地址法（separate chaining）**：
- 一个桶数组（bucket array）。
- 每个桶挂一条**单链表**（libstdc++ 实现为节点里带 `next` 指针，全表一条大链表 + 桶索引，迭代器是 `const_iterator`）。

**冲突解决**：链地址法。插入时算哈希 → 对桶数取模 → 挂到对应链表头/尾。

**负载因子（load factor）** = `元素数 / 桶数`。
- 默认 `max_load_factor() == 1.0`。
- 插入后若 `size / bucket_count > max_load_factor`，触发 **rehash**：把桶数扩到下一个质数/2 的幂，**重新插入所有元素**。
- **rehash 会使所有迭代器失效**（但引用/指针不失效，因为节点没动，只改链）。

```cpp
std::unordered_map<int,int> m;
m.reserve(1000);          // 预分配桶，避免多次 rehash
m.max_load_factor(0.7);   // 调低负载因子换查找速度
```

**注意点**：

1. **rehash 会让迭代器失效**，遍历中不能插入。
2. **迭代顺序不确定**（与插入顺序无关）。
3. **自定义类型要提供 `std::hash` 特化和 `operator==`**：
```cpp
struct P { int x, y; bool operator==(const P&) const; };
struct PHash { size_t operator()(const P& p) const { return std::hash<int>{}(p.x) ^ (std::hash<int>{}(p.y) << 1); } };
std::unordered_map<P, int, PHash> m;
```
4. **哈希质量差会导致最坏 O(n)**；需要防哈希洪水攻击时可用 `std::hash` 的随机种子变体（libstdc++ 有 `std::__hash` 的随机化）。
5. **`std::map` 的最坏 O(log n) 是稳定保证**，实时系统更看重确定性时选 `map`。

**C++20 起**有 `contains()`、`try_emplace`、`insert_or_assign`；`try_emplace` 避免无谓的构造（`insert` 可能先构造再丢弃）。""",
    ),
    (
        "C++",
        "vector,reserve,realloc",
        2,
        r"""`vector` 的 `size` 和 `capacity` 有什么区别？`reserve` 有什么用？""",
        r"""**`size`**：已有元素个数。**`capacity`**：当前分配的内存能装多少个元素（不重新分配的前提下）。

```cpp
std::vector<int> v;
v.size();      // 0
v.capacity();  // 0（实现相关）
v.push_back(1);
// 典型按 2 倍扩容：capacity 变 1 → 2 → 4 → 8 ...
```

**扩容过程**：申请新内存（通常 2 倍或 1.5 倍）→ 移动/拷贝旧元素 → 释放旧内存。因此 `push_back` **均摊** O(1)，但单次扩容 O(n)，且**所有迭代器/指针/引用失效**。

**`reserve(n)`**：预分配至少 n 个元素的空间，把多次扩容变成一次：

```cpp
std::vector<int> v;
v.reserve(10000);            // 只改 capacity，不改 size
for (int i = 0; i < 10000; ++i) v.push_back(i);   // 不再扩容
```

**`resize(n)`** 则改 `size`（多出来的元素值初始化）：
```cpp
v.resize(5);      // size = 5，新增元素为 0
v.resize(2);      // size = 2，尾部元素被销毁（capacity 不变）
```

**`shrink_to_fit()`** 请求释放多余容量（非强制，实现可忽略）；C++11 前用 `swap` 技巧：
```cpp
std::vector<int>(v).swap(v);   // 老写法
```

**实践建议**：
1. 已知元素个数时**先 `reserve`**，避免重复分配与搬移。
2. 用 `emplace_back(args...)` 就地构造，避免临时对象 + 移动。
3. 扩容会让**引用/指针/迭代器全部失效**；如果外部持有元素指针（如 `vector<Foo>` 里 `Foo*`），要改用 `deque`/`list` 或存 `unique_ptr`。
4. 扩容时的元素搬移在元素类型有 `noexcept` 移动构造时用移动，否则**退回拷贝**（强异常安全保证要求）。

**扩容倍数为什么常见是 1.5 或 2**：2 倍导致"永远无法复用之前释放的内存块"（新块总比所有旧块之和还大）；1.5 倍可以更好地复用。""",
    ),
    (
        "C++",
        "vector bool 特化",
        3,
        r"""`std::vector<bool>` 有什么特殊之处？为什么说它是"坑"？""",
        r"""`std::vector<bool>` 是一个**特化**，为节省空间把每个 bool 压成 **1 bit**（不是 1 字节）。

```cpp
std::vector<bool> v(8);
sizeof(v[0]);        // ❌ 编译错误：v[0] 是代理对象，不是一个 bool 左值
auto x = v[0];       // ✅ 可以隐式转换为 bool（proxy）
bool& r = v[0];      // ❌ 不能绑定引用
```

**问题清单**：

1. **`operator[]` 返回代理对象（`std::vector<bool>::reference`）**，不是 `bool&`。
   - 不能用 `bool*`、不能取地址、不能绑定 `bool&`。
   - 模板代码里 `auto&& x = v[0];` 得到的是代理的引用，行为怪异。
2. **不能与 C 风格接口互操作**：没有 `data()` 返回 `bool*`（C++17 前完全没有 `data()`）。
3. **线程不安全**：多个 bit 共享同一字节，并发写不同 bit 会数据竞争。
4. **性能可能更差**：位运算 + 读改写，比直接操作字节慢。
5. **泛型代码里破坏假设**：`std::vector<T>` 的通用算法遇到 `T = bool` 会编译失败（如 `&v[0]`）。

**替代方案**：
- 需要真正的 `bool` 数组 → `std::vector<char>` 或 `std::vector<uint8_t>`（明确 1 字节）。
- C++20 起可以用 `std::vector<bool>` 的替代品：boost 的 `dynamic_bitset`、或自己的位集包装。
- 需要位集但长度固定 → `std::bitset<N>`（专门为此设计，接口清晰）。

**标准委员会的态度**：`std::vector<bool>` 被公认是设计失误，但**不能改**（破坏 ABI 兼容）。新的提案（如 `std::bitset` 的动态版本）在推进中。

面试回答要点：**明确指出"代理引用"和"不能取地址"这两个核心差异**，并给出替代方案。""",
    ),
    (
        "C++",
        "string,SSO",
        3,
        r"""`std::string` 的 SSO（小字符串优化）是什么？""",
        r"""**SSO（Short String Optimization）**：短字符串直接存在 `std::string` 对象内部的缓冲区里，**不分配堆内存**。

`std::string` 通常 32 字节（libstdc++/libc++/MSVC 略有差异），典型布局：

```
[ 指针(8) ][ 长度(8) ][ 容量或 SSO 缓冲(16) ]
                                  ↑ 短串(<=15 字符)就存这里
```

- **libstdc++**：SSO 容量 15 字符（16 字节缓冲去掉 1 个存长度/标志）。
- **libc++**：SSO 容量 22 字符（利用指针的最高位做标志，布局更紧凑）。
- **MSVC**：SSO 容量 15 字符。

```cpp
std::string s1 = "short";                 // 无堆分配
std::string s2 = "this is a long string over 15 chars";  // 堆分配
```

**为什么重要**：
1. 绝大多数标识符、键名都是短串，SSO 让常见路径**零分配**，性能提升显著。
2. `sizeof(std::string)` 因此较大（32 字节）—— 这是拿对象大小换分配次数。
3. **移动短字符串仍要拷贝缓冲内容**（不能像长串那样只挪指针），所以短串的"移动"并不比拷贝便宜。

**相关坑**：
- **`c_str()` 返回的指针在字符串修改后失效**（含 SSO 的情况下，缓冲在对象内部，对象移动就失效）。
- `std::string_view` 指向 `string` 内部时，`string` 的修改/移动会让 view 悬垂。
- C++11 起 `std::string` 保证**连续存储**，C++11 前不保证。
- `resize`/`reserve` 的语义与 `vector` 类似，但 `clear()` **不释放容量**。

**面试延伸**：`std::string` 的 `capacity` 在 SSO 状态下通常返回 15（libstdc++），这时 `reserve(16)` 才会真正分配。""",
    ),
    (
        "C++",
        "迭代器失效",
        2,
        r"""各类容器的迭代器失效规则是什么？""",
        r"""**这是高频面试题，按容器背**：

| 容器 | 插入 | 删除 |
|---|---|---|
| `vector` | **全部失效**（扩容时）；不扩容时插入点之后失效 | 删除点之后全部失效 |
| `deque` | 两端插入：迭代器失效但引用不失效；中间插入：全部失效 | 中间删除全部失效；两端删除只影响被删元素 |
| `list` | 不失效（节点独立） | 只影响被删元素的迭代器 |
| `forward_list` | 不失效 | 同 list |
| `map`/`set` | 不失效 | 只影响被删元素 |
| `unordered_map`/`set` | **rehash 时全部失效**；否则不失效 | 只影响被删元素（引用/指针不失效） |

**`vector` 的细节**：
```cpp
std::vector<int> v{1,2,3,4};
auto it = v.begin();
v.push_back(5);        // 可能扩容 → it 失效（UB）
v.erase(v.begin());    // it 之后的都失效
```

**正确的删除姿势**：
```cpp
// 遍历中删除：用 erase 的返回值
for (auto it = v.begin(); it != v.end(); ) {
    if (pred(*it)) it = v.erase(it);
    else ++it;
}
// C++20 起更方便
std::erase_if(v, pred);
```

**`map`/`list` 的优势**：节点不会因插入/删除而移动，所以迭代器、引用、指针都稳定，只有被删元素本身失效。这是它们相对 `vector` 的核心价值。

**`unordered_map` 的 rehash 会让迭代器全失效**，所以遍历时不能插入新元素；若要边遍历边插入，先 `reserve`。

**调试工具**：`-D_GLIBCXX_DEBUG` 会让 libstdc++ 检测迭代器误用（越界、失效后用）并报错；ASan 也能抓到部分悬垂访问。""",
    ),
    (
        "C++",
        "sort,introsort",
        3,
        r"""`std::sort` 的底层实现是什么？为什么不用纯快排？""",
        r"""`std::sort` 用 **introsort（内省排序）**，是三种算法的混合：

1. **快速排序**为主。
2. **递归深度超过 `2 * log2(n)`** 时切换到**堆排序**（防止快排 O(n²) 最坏情况）。
3. **子区间长度小于阈值（典型 16）** 时切换到**插入排序**（对小数组更快，常数小）。

```
introsort:
  quicksort + 深度超限则 heapsort + 小区间用 insertionsort
```

**为什么不全用快排**：快排最坏 O(n²)（已排序输入 + 首元素作 pivot 时），而 introsort 通过深度限制把最坏压到 **O(n log n)**。

**pivot 选法**：三数取中（median-of-three）或 median-of-nine，避免有序输入退化。

**复杂度与稳定性**：
- 时间复杂度：O(n log n)（最好/平均/最坏）。
- **不稳定**（相等元素顺序不保证）。需要稳定用 `std::stable_sort`（归并排序，额外 O(n) 空间）。

**相关函数**：

| 函数 | 用途 | 复杂度 |
|---|---|---|
| `sort` | 全排序 | O(n log n) |
| `stable_sort` | 稳定排序 | O(n log² n) 或 O(n log n) 带额外空间 |
| `partial_sort` | 只排前 k 个 | O(n log k) |
| `nth_element` | 找第 n 名（快速选择） | 平均 O(n) |
| `partition` | 按谓词分组 | O(n) |

**实现细节**：libstdc++/libc++ 的 `sort` 在**移动代价低**时用移动，`is_trivially_copyable` 时可能用 `memmove` 加速。

**面试延伸**：
- `nth_element` 求中位数/TopK 是 O(n) 平均；
- `stable_sort` 的额外空间可以通过 `partial_sort` 或"索引排序"规避；
- 需要自定义比较器时注意**严格弱序**：`a < b` 必须满足 irreflexive、asymmetric、transitive，否则 UB（常见错误是 `<=`）。""",
    ),
    (
        "C++",
        "array,C数组",
        1,
        r"""`std::array` 和 C 风格数组有什么区别？""",
        r"""| 维度 | C 数组 `T a[N]` | `std::array<T,N>` |
|---|---|---|
| 拷贝赋值 | ❌ 不能整体赋值/传参 | ✅ 可拷贝、可赋值、可传值 |
| 大小 | 需要单独传长度 | `size()` 编译期常量 |
| 边界检查 | 无 | `at()` 有，`operator[]` 无 |
| 迭代器 | 退化为指针 | 有 `begin/end` |
| 与算法配合 | 需 `begin(a), end(a)` | 直接可用 |
| 零开销 | — | 是（`sizeof == N*sizeof(T)`，无额外成员） |
| 结构化绑定 | 支持 | 支持 |

```cpp
std::array<int, 3> a{1,2,3};
a.size();      // 3
a.at(5);       // 抛 std::out_of_range
std::sort(a.begin(), a.end());
auto b = a;    // ✅ 整体拷贝（C 数组做不到）
```

**注意**：
- `std::array` **不退化**为指针，所以 `sizeof(a)` 是数组大小，不是指针大小。
- `std::array<T,0>` 是合法的（大小为 1，因为对象必须有地址）。
- 作为函数参数时，`std::array` 按值传参是真正的值传递；C 数组会退化为指针。
- 需要与 C 接口互操作时用 `a.data()`。

**选择**：新代码优先 `std::array`；需要与 C API 交互或聚合初始化的 POD 数组时用 C 数组。C++20 起还有 `std::span` 用于"引用一段连续内存"，是传参的首选替代。""",
    ),
    (
        "C++",
        "智能指针",
        2,
        r"""C++ 有哪几种智能指针？各自的使用场景是什么？""",
        r"""| 智能指针 | 所有权 | 开销 | 场景 |
|---|---|---|---|
| `unique_ptr` | 独占 | 零开销（可空） | 默认选择，替代裸指针 |
| `shared_ptr` | 共享（引用计数） | 控制块 + 原子操作 | 多方共享生命周期 |
| `weak_ptr` | 不增加计数 | 与 shared 配套 | 打破循环引用、观测 |
| `auto_ptr`（已废弃） | — | — | 不要用（C++17 移除） |

**`unique_ptr`**：
```cpp
auto p = std::make_unique<Foo>(args);   // C++14
p->method();
auto q = std::move(p);                  // 所有权转移，p 变 nullptr
```
- 不可拷贝，只可移动。
- 支持下放自定义删除器：`unique_ptr<FILE, decltype(&fclose)>`。
- 用于数组：`std::unique_ptr<int[]>`（C++17 起 `make_unique<int[]>`）。

**`shared_ptr`**：
```cpp
auto a = std::make_shared<Foo>();   // 推荐：一次分配（对象 + 控制块）
auto b = a;                          // 引用计数 +1
```
- 引用计数归零时释放对象。
- **控制块里有两个计数**：`shared_count`（决定释放对象）和 `weak_count`（决定释放控制块）。
- `make_shared` 比 `shared_ptr<T>(new T)` 好：**一次分配**（减少一次 malloc 和更好的缓存局部性），且异常安全。

**`weak_ptr`**：
```cpp
std::weak_ptr<Foo> w = a;
if (auto s = w.lock()) { s->method(); }   // 提升为 shared_ptr，可能失败
```
- 不增加引用计数，不阻止对象销毁。
- 用途：**打破循环引用**、**缓存**（观测对象是否还活着）、观察者模式。

**选择原则**：
1. **默认 `unique_ptr`**。
2. 确实需要共享所有权才用 `shared_ptr`（它的原子引用计数是有成本的）。
3. 需要"观测但不拥有"用 `weak_ptr` 或裸指针/引用。
4. **不要**从同一个裸指针构造两个 `shared_ptr`（双重释放）。

**注意**：`shared_ptr<int>` 不是"指向 int 的智能指针"，而是"共享拥有一个 int"，`sizeof(shared_ptr) == 2 * sizeof(void*)`（有指针 + 控制块指针）。""",
    ),
    (
        "C++",
        "unique_ptr",
        2,
        r"""`unique_ptr` 是怎么做到"零开销 + 不可拷贝"的？删除器怎么用？""",
        r"""**实现要点**（简化）：

```cpp
template <class T, class D = std::default_delete<T>>
class unique_ptr {
    T* ptr_ = nullptr;
    // 无删除器状态时：[[no_unique_address]] D d_;
public:
    unique_ptr(const unique_ptr&) = delete;              // 不可拷贝
    unique_ptr(unique_ptr&& o) noexcept : ptr_(o.ptr_) { o.ptr_ = nullptr; }  // 可移动
    ~unique_ptr() { if (ptr_) D{}(ptr_); }
    T* release() noexcept { T* p = ptr_; ptr_ = nullptr; return p; }
    void reset(T* p = nullptr) noexcept { if (ptr_) D{}(ptr_); ptr_ = p; }
};
```

**为什么零开销**：
- 无状态删除器（`default_delete`）是**空类**，配合 `[[no_unique_address]]` / EBO **不占空间** → `sizeof(unique_ptr<T>) == sizeof(T*)`。
- 全部操作可内联，没有虚函数、没有引用计数。

**与裸指针的差别**：只是"析构时自动 delete"，编译期保证，运行期零成本。

**自定义删除器**：

```cpp
// 1) 函数指针形式（占 8 字节）
auto closer = [](FILE* f){ if (f) fclose(f); };
std::unique_ptr<FILE, decltype(closer)> fp(fopen("f.txt","r"), closer);

// 2) 无状态函数对象（不占空间）
struct FileCloser { void operator()(FILE* f) const { if (f) fclose(f); } };
std::unique_ptr<FILE, FileCloser> fp(fopen("f.txt","r"));

// 3) 作为类型别名封装
template <class T> using Unique = std::unique_ptr<T, ...>;
```

**注意点**：
- 删除器是**类型的一部分**：`unique_ptr<T, D1>` 和 `unique_ptr<T, D2>` 是不同类型，不能互相赋值。
- 删除器的**有状态部分**会占空间（比如持有 allocator 引用）。
- `unique_ptr<T[]>` 用 `delete[]`，但**不支持自定义删除器时的数组推导**要小心。
- 转换为 `shared_ptr`：`std::shared_ptr<T> sp = std::move(up);` 是允许的（移动所有权）。

**为什么 `unique_ptr` 比 `shared_ptr` 更适合做成员**：独占语义清晰、零开销；只有当确实需要共享时才升级为 `shared_ptr`。""",
    ),
    (
        "C++",
        "make_shared,控制块",
        3,
        r"""`std::make_shared` 和 `shared_ptr<T>(new T)` 有什么区别？""",
        r"""**关键差异：内存分配次数与控制块布局**。

```cpp
std::shared_ptr<Foo> a(new Foo);            // 两次分配
std::shared_ptr<Foo> b = std::make_shared<Foo>();  // 一次分配（通常）
```

| 维度 | `shared_ptr<T>(new T)` | `make_shared<T>()` |
|---|---|---|
| 分配次数 | 2（对象 + 控制块） | 1（合并为一块） |
| 缓存局部性 | 对象与控制块分离 | 相邻，更好 |
| 异常安全 | 若控制块分配失败，`new T` 已分配 → 会泄漏？实际上标准保证 delete，但顺序不理想 | 天然安全 |
| 弱引用寿命 | 对象释放后，控制块随 weak 计数归零释放 | **对象和控制块同一块内存**，weak 计数未归零时**整块都不释放** |
| 支持 `weak_ptr` 长持有时 | 对象内存可先释放 | 对象内存要等 weak 也归零 |
| 自定义删除器 | ✅ | ❌（`make_shared` 不支持） |
| 私有构造函数 | ❌ 无法访问 | ✅（`make_shared` 可访问） |

**最后两条是选型关键**：
- 需要**自定义删除器**（如 `fclose`、`munmap`）→ 只能用 `shared_ptr<T>(ptr, deleter)`。
- 构造函数是 `private`/`protected` → 用 `make_shared`（它作为友元？不，是因为标准规定 `make_shared` 内部 `::new T(...)` 不受访问限制？实际上是通过 `allocator_traits::construct`，能在派生场景工作。实践上常见做法是给 `make_shared` 加友元或提供静态工厂）。

**`weak_ptr` 与内存滞留**（重要陷阱）：

```cpp
auto sp = std::make_shared<BigObject>();  // 对象 + 控制块在一整块内存
std::weak_ptr<BigObject> w = sp;
sp.reset();          // 对象析构，但**整块内存**要等 w 也释放
```
若有大对象 + 长生命周期的 `weak_ptr`，`make_shared` 会让内存滞留 → 此时应**用 `shared_ptr<T>(new T)`**，让对象内存可以先行释放。

**`allocate_shared`**：`std::allocate_shared` 支持自定义 allocator，是 `make_shared` 的泛化版本，用于内存池场景。

**结论**：默认用 `make_shared`；需要自定义删除器、或有大对象 + 长持有 `weak_ptr` 时用显式构造。""",
    ),
    (
        "C++",
        "裸指针,智能指针",
        1,
        r"""为什么推荐用智能指针而不是裸指针？什么情况下裸指针仍然合适？""",
        r"""**裸指针的语义模糊**：无法从 `T*` 看出这是"拥有"还是"借用"。

```cpp
void f(Foo* p);        // 谁负责 delete？调用者？函数内？
```
这导致：内存泄漏、双重释放、悬垂、所有权不清。

**智能指针表达所有权**：
- `unique_ptr<T>`：独占拥有，离开作用域即释放。
- `shared_ptr<T>`：共享拥有，最后一个释放。
- `T*` / `T&`：**不拥有，只是借用**（更清晰的约定）。

**裸指针仍然合适的场景**：
1. **非拥有的形参**：`void render(const Foo&)` 或 `void render(const Foo* p)`（可空时用指针）。
2. **观察者/缓存**，生命周期由别处保证（配合注释或 `weak_ptr`）。
3. **实现容器/数据结构的内部节点链接**（`list` 的 `next`）。
4. **C 接口互操作**（不能传智能指针，用 `.get()` / `.release()`）。
5. **性能极端的场景**：`unique_ptr` 已经是零开销，通常不需要退回裸指针。

**注意点**：
- 传参时**不要**传 `shared_ptr` 值（会原子增删引用计数）；传 `const T&` 或 `T*` 更合适，除非函数需要**延长生命周期**（那就传 `shared_ptr` 值）。
- `.get()` 得到的裸指针**不拥有**，不能 delete。
- `shared_ptr` 参数传递是"可能共享所有权"的信号，传递方式本身就是文档。

**判断标准**：问自己"这块内存谁负责释放？" —— 有明确答案就用智能指针；"别人负责"就用裸指针/引用并注释清楚。""",
    ),
    (
        "C++",
        "atomic,内存序",
        3,
        r"""`std::atomic` 是什么？六种内存序分别是什么含义？""",
        r"""`std::atomic<T>` 提供**原子的读改写**与**内存序**控制，是 C++ 并发的基础设施。

```cpp
std::atomic<int> cnt{0};
cnt.fetch_add(1, std::memory_order_relaxed);   // 原子自增
int v = cnt.load(std::memory_order_acquire);
cnt.store(1, std::memory_order_release);

auto expected = 0;
bool ok = cnt.compare_exchange_strong(expected, 1);   // CAS
```

**六种内存序**（从弱到强）：

| 内存序 | 语义 |
|---|---|
| `relaxed` | 只保证该操作的原子性，**不保证任何顺序**（同一变量的修改仍有 total order） |
| `consume` | 依赖顺序（data dependency），实践中被当作 `acquire`，**不推荐使用** |
| `acquire` | 读操作：**之后的**读写不能重排到它之前 |
| `release` | 写操作：**之前的**读写不能重排到它之后 |
| `acq_rel` | 读改写的双面（`fetch_add` 等） |
| `seq_cst` | **默认**，全局单一顺序（sequential consistency），最易推理也最慢 |

**acquire-release 配对**是核心模式（发布-订阅）：

```cpp
// 线程 A
data = 42;                                   // 非原子写
flag.store(true, std::memory_order_release); // 保证 data 的写在 flag 之前可见

// 线程 B
while (!flag.load(std::memory_order_acquire));  // 保证之后能看到 data = 42
assert(data == 42);                              // 一定成立
```

**要点**：
1. 默认 `seq_cst` 最安全，性能敏感时再降级。
2. `relaxed` 用于**纯计数**（如统计），但**不能**用来同步数据。
3. **CAS 有 ABA 问题**（见下一题）。
4. `std::atomic` 对**非平凡类型**（如 `shared_ptr` 的实现）需要特殊处理，标准只保证对 trivially copyable 类型的无锁性。
5. **不是所有类型都无锁**：`is_lock_free()` 可检测；大对象可能退化为内部加锁。
6. 注意**不要用 volatile 替代 atomic**（见 volatile 题）。

**x86 的实际情况**：load/store 天然有 acquire/release 语义（强内存模型），所以 `relaxed` 和 `acquire` 在 x86 上编译结果常常一样；但在 ARM/PowerPC 上差异巨大（需要显式屏障指令）。写可移植代码必须用正确的内存序，不能因为"x86 上跑得对"就降级。""",
    ),
    (
        "C++",
        "内存屏障",
        2,
        r"""内存屏障（fence）是什么？`std::atomic_thread_fence` 怎么用？""",
        r"""**为什么需要屏障**：编译器和 CPU 都会重排指令（编译器优化 + 乱序执行 + store buffer / 缓存一致性协议），在单线程内保持"as-if"语义，但多线程下可能观察到违反直觉的顺序。

**两类屏障**：

1. **编译器屏障**：阻止编译器重排。
   - `asm volatile("" ::: "memory");`（GCC 常用）。
   - `std::atomic_signal_fence(std::memory_order_acq_rel);`（标准库提供）。
2. **CPU 内存屏障**：阻止硬件重排，如 x86 的 `mfence`/`lfence`/`sfence`，ARM 的 `dmb`。

**标准库接口**：
```cpp
std::atomic_thread_fence(std::memory_order_release);
std::atomic_thread_fence(std::memory_order_acquire);
```

**独立屏障的用法**（不依赖某个原子变量）：

```cpp
// 生产者
data[0] = 1; data[1] = 2;
std::atomic_thread_fence(std::memory_order_release);
flag.store(true, std::memory_order_relaxed);

// 消费者
while (!flag.load(std::memory_order_relaxed));
std::atomic_thread_fence(std::memory_order_acquire);
assert(data[0] == 1);
```

**语义细则**（容易搞错）：
- `release` fence 与之前的所有写建立顺序，与**之后的**原子 store 结合表现如同 release store。
- `acquire` fence 与**之前的**原子 load 结合，之后的所有读看到对应 release 的写。
- `seq_cst` fence 最强，全局顺序。

**实践建议**：
1. **优先用 `acquire`/`release` 的原子操作**，而不是独立 fence —— 更好理解，编译器也更容易优化。
2. `std::atomic_thread_fence` 只有在"一个 fence 需要覆盖多个原子操作"时才更方便（如批量发布）。
3. 调试并发 bug 极难，**优先用 mutex + 简单模型**；只有确证性能瓶颈才下探到内存序。

**参考**：Herb Sutter 的 "atomic<> Weapons" 演讲是理解内存序的最佳材料。""",
    ),
    (
        "C++",
        "CAS,ABA",
        3,
        r"""什么是 CAS？ABA 问题是什么？怎么解决？""",
        r"""**CAS（Compare-And-Swap）**：原子地"比较再交换"，是无锁数据结构的基石。

```cpp
bool compare_exchange_weak(T& expected, T desired);   // 可能伪失败，需循环
bool compare_exchange_strong(T& expected, T desired); // 不会伪失败，但可能更慢
```

语义：若当前值 == `expected`，则写入 `desired` 并返回 true；否则把**当前值写回 `expected`** 并返回 false。

```cpp
int expected = 0;
while (!cnt.compare_exchange_weak(expected, expected + 1)) {
    // 失败时 expected 已被更新为最新值，重试即可
}
```

`weak` 版本在 LL/SC 架构（ARM、PowerPC）上可能"伪失败"（无理由返回 false），所以必须放在循环里；在 x86 上和 strong 等价。

**ABA 问题**：

线程 1 读到值 A，准备 CAS 成 C；期间线程 2 把 A 改成 B 又改回 A。线程 1 的 CAS 成功，但它以为"值没变"，实际上中间发生过变化 —— 对**指针/带关联状态**的算法会导致严重错误（如无锁栈的节点已被释放又复用）。

```
T1: 读到 head = A
T2: pop A（head = B），free(A)，malloc 又返回同一地址赋给新节点
T2: push 新节点（head = A，地址相同）
T1: CAS(head, A → C) 成功，但 C 的 next 指向已释放的 A  → 崩溃
```

**解决手段**：
1. **带版本号的指针**（tagged pointer）：`(ptr, version)` 一起 CAS，用 `std::atomic<struct{void* p; uint64_t v;}>` 或把版本塞进 64 位的高位。
2. **`std::shared_ptr` 的 `atomic_load/atomic_store` 自由函数**（C++20 起 `std::atomic<std::shared_ptr<T>>`）：避免节点被过早释放。
3. **Hazard Pointer / RCU**：延迟回收。
4. **双字 CAS**：x86_64 的 `cmpxchg16b`。
5. **放弃无锁**：用锁，通常更简单更可靠。

**实践建议**：**无锁编程极难写对**，先用锁；确有需求时用现成库（`folly`、`boost.lockfree`）并做压力测试 + ThreadSanitizer。""",
    ),
    (
        "C++",
        "锁,自旋锁,读写锁",
        2,
        r"""自旋锁、互斥锁、读写锁有什么区别？怎么选？""",
        r"""| 锁 | 等待方式 | 适用场景 | 缺点 |
|---|---|---|---|
| 自旋锁 | 忙等（CPU 空转） | 临界区极短、多核 | 浪费 CPU；单核无意义 |
| 互斥锁（mutex） | 睡眠等待（futex） | 一般场景 | 上下文切换开销 |
| 读写锁（shared_mutex） | 读共享、写独占 | **读多写少** | 写饥饿、实现复杂，读锁也有开销 |
| 递归锁 | 可重入 | 递归调用同一锁 | 设计缺陷信号，通常应重构 |

**自旋锁**：
```cpp
std::atomic_flag lock = ATOMIC_FLAG_INIT;
while (lock.test_and_set(std::memory_order_acquire)) { /* spin */ }
// critical section
lock.clear(std::memory_order_release);
```
- 好处：无系统调用、延迟低。
- 坏处：持锁时间长会浪费 CPU；单核上只会白等。
- 现代实现（如 `pthread_spinlock`、`folly::SpinLock`）常做**自适应自旋**：先自旋几次，再退化为睡眠。

**互斥锁**：
```cpp
std::mutex m;
{ std::lock_guard<std::mutex> g(m); /* ... */ }
```
- Linux 上基于 **futex**：无竞争时全是用户态操作（快），有竞争才进内核睡眠。
- **不要手写 `lock()/unlock()`**，用 RAII 守卫（`lock_guard`、`unique_lock`、`scoped_lock`）。

**读写锁（`std::shared_mutex`，C++17）**：
```cpp
std::shared_mutex sm;
{ std::shared_lock g(sm);  read(); }     // 多个读者并行
{ std::unique_lock g(sm);  write(); }    // 写独占
```
- **注意**：读锁不是免费的（原子操作 + 可能的缓存行争用）；**读多写少到极致时**才划算（一般读:写 > 10:1 才考虑）。
- 存在**写饥饿**风险（读者源源不断）。

**选择原则**：
1. **默认用 `mutex`** —— 简单、正确、无竞争时很快。
2. 临界区只有几条指令且多核 → 考虑自旋/自适应锁。
3. 读远多于写、且读操作不短 → 考虑 `shared_mutex`，但先测性能。
4. **减少锁竞争**比换锁更重要：缩小临界区、分片（sharding）、无锁数据结构、线程本地存储。
5. 多把锁时用 `std::scoped_lock(a, b)`（C++17）做**死锁避免**（内部用 `std::lock` 的一致顺序算法）。""",
    ),
    (
        "C++",
        "条件变量,虚假唤醒",
        2,
        r"""条件变量怎么用？什么是虚假唤醒？""",
        r"""条件变量用于**线程间等待某个条件成立**，必须与互斥量配合。

**标准用法**：

```cpp
std::mutex m;
std::condition_variable cv;
std::queue<int> q;

// 消费者
{
    std::unique_lock<std::mutex> lk(m);
    cv.wait(lk, [] { return !q.empty(); });   // ✅ 带谓词的版本
    int v = q.front(); q.pop();
}

// 生产者
{
    std::lock_guard<std::mutex> lk(m);
    q.push(1);
}                     // 先解锁
cv.notify_one();      // 再通知（也可以解锁前通知，但解锁后通知通常更好）
```

**为什么要带谓词**：`cv.wait(lk, pred)` 等价于：
```cpp
while (!pred()) cv.wait(lk);
```
这个 `while` 循环用于抵御**虚假唤醒**和**通知丢失**。

**虚假唤醒（spurious wakeup）**：`wait` 可能在**没有任何 `notify`** 的情况下返回。POSIX 和 C++ 标准都明确允许。所以：
- ❌ **错误写法**：`cv.wait(lk); /* 直接假设条件成立 */`
- ✅ **正确写法**：永远用谓词，或手写 `while (!pred) cv.wait(lk);`

**其它要点**：

1. **通知必须在持有锁时修改条件之后**（否则可能丢通知）：
```cpp
// ❌ 危险：notify 可能在消费者检查条件之后、wait 之前发生 → 丢通知
q.push(1);
cv.notify_one();
```
2. `notify_one` 唤醒一个等待者；`notify_all` 唤醒全部（多消费者共享条件时常用 all 避免饿死）。
3. **`wait` 会释放锁**（这是它必须接收 `unique_lock` 的原因），被唤醒后重新获取锁。
4. 不要在 `notify` 时持锁太久，会造成"惊群"式争用。
5. C++20 起有 `std::atomic::wait/notify`，某些场景可替代条件变量。

**经典陷阱**：谓词访问的共享数据必须在**同一把锁**下修改和读取，否则数据竞争。""",
    ),
    (
        "C++",
        "线程池",
        3,
        r"""线程池怎么实现？核心组件有哪些？""",
        r"""**核心组成**：

1. **任务队列**（`std::queue<std::function<void()>>`）+ 互斥量 + 条件变量。
2. **工作线程**：循环取任务执行。
3. **停止标志**：让 `join` 时线程能退出。
4. **返回值机制**：`std::future` / `std::packaged_task`。

**简化实现**：

```cpp
class ThreadPool {
public:
    explicit ThreadPool(size_t n) {
        for (size_t i = 0; i < n; ++i) {
            workers_.emplace_back([this] {
                for (;;) {
                    std::function<void()> task;
                    {
                        std::unique_lock<std::mutex> lk(m_);
                        cv_.wait(lk, [this] { return stop_ || !tasks_.empty(); });
                        if (stop_ && tasks_.empty()) return;
                        task = std::move(tasks_.front());
                        tasks_.pop();
                    }
                    task();                       // 在锁外执行，避免串行化
                }
            });
        }
    }

    template <class F, class... Args>
    auto submit(F&& f, Args&&... args)
        -> std::future<std::invoke_result_t<F, Args...>> {
        using R = std::invoke_result_t<F, Args...>;
        auto task = std::make_shared<std::packaged_task<R()>>(
            std::bind(std::forward<F>(f), std::forward<Args>(args)...));
        std::future<R> fut = task->get_future();
        {
            std::lock_guard<std::mutex> lk(m_);
            if (stop_) throw std::runtime_error("pool stopped");
            tasks_.emplace([task] { (*task)(); });
        }
        cv_.notify_one();
        return fut;
    }

    ~ThreadPool() {
        { std::lock_guard<std::mutex> lk(m_); stop_ = true; }
        cv_.notify_all();
        for (auto& t : workers_) t.join();
    }
private:
    std::vector<std::thread> workers_;
    std::queue<std::function<void()>> tasks_;
    std::mutex m_;
    std::condition_variable cv_;
    bool stop_ = false;
};
```

**关键设计点**：

1. **任务在锁外执行**，否则退化成串行。
2. **`packaged_task` 要 `shared_ptr` 包起来**（`std::function` 要求可拷贝，而 `packaged_task` 只可移动）。
3. **析构顺序**：设 stop → notify_all → join，保证队列里剩余任务跑完（或按需丢弃）。
4. **线程数**：CPU 密集 ≈ 核数；IO 密集可更多（`核数 / (1 - 阻塞系数)`）。
5. **无界队列会导致内存爆炸**，生产环境要限流或拒绝策略。
6. **异常处理**：工作线程里的异常必须捕获，否则 `std::terminate`；用 `packaged_task` 会自动把异常存到 future。
7. 更精细的设计：**work-stealing**（每线程一个队列 + 窃取）减少锁竞争。

**常见面试追问**：
- 如何优雅关闭？（stop 标志 + 队列排空）
- 如何处理任务抛异常？（catch 后存 future 或日志）
- 如何避免惊群？（notify_one 而非 all；或按条件唤醒）
- 任务优先级？（多队列 + 优先级比较）""",
    ),
    (
        "C++",
        "无锁队列",
        3,
        r"""无锁队列（lock-free queue）的原理是什么？难点在哪？""",
        r"""**单生产者单消费者（SPSC）无锁队列**最简单，也最实用：

```cpp
template <class T, size_t N>
class SpscQueue {                     // N 必须是 2 的幂
    std::array<T, N> buf_;
    std::atomic<size_t> head_{0}, tail_{0};   // 只用两个原子变量
public:
    bool push(const T& v) {
        const size_t t = tail_.load(std::memory_order_relaxed);
        const size_t next = (t + 1) & (N - 1);
        if (next == head_.load(std::memory_order_acquire)) return false;  // 满
        buf_[t] = v;
        tail_.store(next, std::memory_order_release);   // 发布
        return true;
    }
    bool pop(T& out) {
        const size_t h = head_.load(std::memory_order_relaxed);
        if (h == tail_.load(std::memory_order_acquire)) return false;     // 空
        out = std::move(buf_[h]);
        head_.store((h + 1) & (N - 1), std::memory_order_release);
        return true;
    }
};
```

**核心思想**：
- 用**伪共享隔离**（`alignas(64)` 把 head/tail 分到不同缓存行）+ **acquire/release 配对**保证可见性。
- 生产者只写 `tail_`，消费者只写 `head_`，**没有写冲突**，所以不需要 CAS。

**MPMC（多生产者多消费者）**：必须用 CAS 循环，难度陡增：

```cpp
// Michael-Scott 队列：基于 CAS 的链表
// 需要解决 ABA、内存回收（hazard pointer / epoch-based reclamation）
```

**难点**：
1. **ABA 问题**（见前一题）。
2. **内存回收**：节点何时可以 free？其他线程可能还持着指针 → 需要 **Hazard Pointer**、**Epoch-Based Reclamation（EBR）**、**引用计数**。
3. **内存序正确性**：写错内存序会表现为"偶发崩溃"，极难调试。
4. **伪共享**：头和尾在同一缓存行会导致性能崩塌。
5. **内存分配**：`new/delete` 本身可能加锁，破坏"无锁"承诺 → 需预分配环形缓冲。

**实践建议**：
1. **优先 SPSC 环形缓冲**（够用且简单），生产环境大量使用（如日志、网络收发包）。
2. MPMC 用成熟库（`boost::lockfree::queue`、`moodycamel::ConcurrentQueue`、`folly::MPMCQueue`），不要手写。
3. **测试**：`-fsanitize=thread`（TSan）能发现数据竞争；压力测试 + 断言。
4. 性能对比：无锁并不总是更快 —— 低竞争时 mutex 已经很快，高竞争时无锁的 CAS 重试也很贵。**先 profile**。

**经典参考**：Herb Sutter 的 "Writing a Generalized Concurrent Queue"、Dmitry Vyukov 的 1024cores.net。""",
    ),
    (
        "C++",
        "async,future,promise",
        2,
        r"""`std::async`、`future`、`promise`、`packaged_task` 分别是什么？""",
        r"""它们构成 C++11 的**异步任务框架**：

| 组件 | 作用 |
|---|---|
| `std::future<T>` | **消费者**：等待并取回结果（`get()`），`get` 只能调一次 |
| `std::promise<T>` | **生产者**：`set_value` / `set_exception` 设置结果 |
| `std::packaged_task<F>` | 把可调用对象包装成任务，调用时自动把结果存进 future |
| `std::async` | 高层封装：提交任务，返回 `future` |

**`std::async`**：
```cpp
auto fut = std::async(std::launch::async, [] { return 42; });
//               ^^^^^^^^^^^^^^^^^^ 必须显式指定策略！
int v = fut.get();
```

**⚠️ 最重要的坑**：`std::async` 的默认策略是 `async | deferred`，**由实现决定**。若选择 `deferred`，任务根本不会在新线程执行，而是在 `get()`/`wait()` 时**在当前线程惰性执行**。这会导致：
- "并发"没有发生（性能 bug）。
- **`fut` 析构会阻塞**（deferred 的 future 析构时会同步执行任务）。

**所以永远显式写 `std::launch::async`。**

**`promise`/`future` 手动配对**：
```cpp
std::promise<int> prom;
std::future<int> fut = prom.get_future();
std::thread t([&prom] {
    try { prom.set_value(compute()); }
    catch (...) { prom.set_exception(std::current_exception()); }
});
int v = fut.get();   // 若 set_exception，get() 会重新抛出
t.join();
```

**`packaged_task`**（可放进容器/队列，用于线程池）：
```cpp
std::packaged_task<int()> task([]{ return 1; });
auto fut = task.get_future();
std::thread(std::move(task)).detach();
fut.get();
```

**`future` 的 `get()` 语义**：
- 阻塞直到结果可用。
- **只能调用一次**（之后 `valid() == false`，再调 `get()` 是 UB）。
- 若任务抛异常，`get()` 重新抛出该异常。

**其它注意**：
- `std::async` 返回的 future 若被丢弃（未取结果），对 `launch::async` 会**阻塞等待任务完成**（因为 future 析构要求同步），所以"即发即忘"不能用 `std::async`。
- 需要链式 `.then()` 得用 `std::future` 之外的东西（C++20 有 `std::execution`，或 `boost::future`、folly `SemiFuture`）。
- `std::shared_future` 可以多次 `get()`、可拷贝，用于多消费者。""",
    ),
    (
        "C++",
        "shared_ptr 线程安全",
        3,
        r"""多线程下 `shared_ptr` 的引用计数是原子的，那它完全线程安全吗？""",
        r"""**部分安全，关键点要分清**：

✅ **安全的**：
- **引用计数的增减是原子的**。多个线程可以各自持有/释放 `shared_ptr` 副本（拷贝、析构、赋值）而不会把计数搞乱。
- 不同 `shared_ptr` 实例（指向同一对象）的并发操作是安全的。

❌ **不安全的**：
1. **同一个 `shared_ptr` 实例的并发读写**：
```cpp
std::shared_ptr<Foo> sp = ...;
// 线程A
sp = other;                    // ❌ 与线程B竞争同一个 sp
// 线程B
auto copy = sp;                // ❌ 数据竞争！
```
因为 `shared_ptr` 有**两个指针**（对象指针 + 控制块指针），赋值/读取不是单个原子操作，可能读到"新对象指针 + 旧控制块指针"的撕裂状态。
- 解决：**加锁**，或用 C++20 的 `std::atomic<std::shared_ptr<T>>`（`atomic_load/atomic_store` 自由函数在 C++11 起也有，但已弃用）。

2. **被管理对象本身的并发访问**：
```cpp
auto sp = std::make_shared<int>(0);
std::thread([sp]{ ++*sp; });   // ❌ 不是原子的（除非 int 本身是 atomic）
```
`shared_ptr` 只保证计数原子，**不保证 `*sp` 的访问安全**。

3. **`weak_ptr::lock()`**：是线程安全的（原子地提升），但提升失败说明对象已销毁。

**实现细节**：控制块里有 `shared_count`（原子）和 `weak_count`（原子）。当 `shared_count == 0` 时销毁对象；`shared_count == 0 && weak_count == 0` 时销毁控制块。

**为什么有两个指针**（`sizeof == 16`）：支持**别名构造**（aliasing constructor），让 `shared_ptr` 指向对象的某部分/派生类，但共享同一控制块：
```cpp
struct S { int a; int b; };
auto sp = std::make_shared<S>();
std::shared_ptr<int> pa(sp, &sp->a);   // 指向成员，但控制块是同一个
```

**实践总结**：
- 只在**线程间共享所有权**（各自持有副本）时用 `shared_ptr`。
- 需要**共享修改同一个 shared_ptr 变量**时，加锁或原子化。
- 高频读写的热点用 `unique_ptr` + 转移，或干脆把数据放在同一个线程。""",
    ),
    (
        "C++",
        "伪共享",
        3,
        r"""什么是伪共享（false sharing）？怎么避免？""",
        r"""**伪共享**：多个线程修改**不同变量**，但这些变量落在**同一个 cache line**（通常 64 字节）上，导致缓存行在核间反复失效、乒乓（cache line ping-pong），性能急剧下降。

```cpp
struct Counters {
    std::atomic<long> a;   // 相邻
    std::atomic<long> b;   // 同一 cache line
};
// 线程1 频繁写 a，线程2 频繁写 b → 互相把对方的 cache line 打失效
```

**为什么会这样**：缓存一致性协议（MESI）以 **cache line** 为最小同步单位。修改一个字节也要独占整条 line。

**解决办法**：

1. **对齐填充（padding）到 cache line 边界**：

```cpp
struct alignas(64) Padded {
    std::atomic<long> v;
    char pad[64 - sizeof(std::atomic<long>)];   // 补满 64 字节
};
```

2. **`alignas(std::hardware_destructive_interference_size)`**（C++17）：
```cpp
struct alignas(std::hardware_destructive_interference_size) Counter {
    std::atomic<long> v;
};
```
注意这个常量在实际编译器上可能仍是 64（x86）或 128（部分 ARM），且 C++ 标准备注它可能不等于真实值。

3. **`[[no_unique_address]]` 与布局设计**：把热点变量分散到不同结构体，或按线程分片。

4. **每线程独立累加，最后汇总**（避免共享写）：
```cpp
struct alignas(64) ThreadLocal { long count = 0; };
std::array<ThreadLocal, N> stats;   // 每线程写自己的
// 结束后 reduce
```

**检测工具**：`perf c2c`（Linux）专门定位 cache line 竞争；`perf stat` 观察 `cache-misses` 暴涨。

**真实案例**：
- 高性能队列的 head/tail 指针（前面 SPSC 队列题就是靠 `alignas` 隔离）。
- 线程池的每线程统计、`std::atomic` 标志。
- 分配器的 arena 结构。

**注意**：伪共享和"真共享"（同时读写同一变量）不同 —— 真共享需要同步，伪共享只需**布局隔离**。

**反例警示**：不要盲目加 padding（浪费内存、影响缓存命中率），**先 profile 确认热点**再优化。""",
    ),
    (
        "C++",
        "happens-before,内存模型",
        3,
        r"""C++ 的内存模型是什么？happens-before 关系怎么建立？""",
        r"""**C++ 内存模型**（C++11 引入）规定了多线程程序的**可见性**与**顺序**语义，让编译器优化和硬件乱序都有明确边界。

**几个基础关系**：

1. **sequenced-before**：同一线程内，按程序的求值顺序。
2. **synchronizes-with**：跨线程的同步关系，由原子操作的 acquire/release 配对建立。
   - 若 A 是 release 写、B 是读到 A 写的值的 acquire 读，则 A **synchronizes-with** B。
3. **happens-before** = sequenced-before 的传递闭包 ∪ synchronizes-with。
   - 若 A happens-before B，则 A 的所有副作用对 B 可见。
4. **data race（数据竞争）**：两个线程访问同一内存位置、至少一个是写、且没有 happens-before 关系 → **UB（未定义行为）**。这是最重要的规则：**有 data race 的程序，编译器可以假设它不存在并做任意优化**。

**建立 happens-before 的手段**：

| 手段 | 说明 |
|---|---|
| `mutex` 的 unlock → lock | 同一 mutex，先解锁的线程的所有写在加锁者看来可见 |
| `atomic` store(release) → load(acquire) | 配对同步 |
| `atomic` seq_cst 操作 | 全局单一顺序，更强 |
| `thread::join()` | join 返回后能看到被 join 线程的所有写 |
| `condition_variable` | 配合 mutex 传递 |
| `promise::set_value` → `future::get` | 同样建立同步 |

```cpp
int data = 0;
std::atomic<bool> ready{false};

// 线程 A
data = 42;
ready.store(true, std::memory_order_release);   // 发布

// 线程 B
while (!ready.load(std::memory_order_acquire));  // 订阅
assert(data == 42);   // 一定成立（happens-before 建立）
```

**为什么需要它**：
- 没有内存模型时，编译器可以把 `data = 42` 重排到 store 之后，硬件也可以（store buffer）→ 线程 B 看到 `ready == true` 但 `data == 0`。
- C++ 内存模型让"哪些重排是允许的"有精确定义。

**关键概念补充**：
- **UB 的定义**：data race 是 UB，所以"看起来能跑"不代表正确 —— 编译器可能在优化后彻底改变行为。
- **`std::atomic` 默认 `seq_cst`**：最易推理，全局一致顺序，代价是可能插入额外屏障。
- **`relaxed` 原子**：仍是原子的，但**不建立** happens-before（除同变量的修改顺序外）。

**实践建议**：初学者用 `mutex` + `seq_cst` 就够；只有在确证瓶颈时才降级内存序，并配合 TSan 验证。""",
    ),
    (
        "C++",
        "异常安全",
        3,
        r"""异常安全有哪几个级别？怎么写强异常安全的代码？""",
        r"""**异常安全保证的四个级别**（从弱到强）：

| 级别 | 保证 | 说明 |
|---|---|---|
| **no-throw / nothrow** | 不抛异常 | 如 `swap`、移动构造、析构 |
| **strong**（强保证） | 提交或回滚 | 操作要么完全成功，要么对象状态不变（原子性） |
| **basic**（基本保证） | 不泄漏、不破坏不变量 | 对象仍可用但可能处于合法但未指定状态 |
| **no guarantee** | 无保证 | 出了问题对象可能损坏 —— 不该出现在库代码里 |

**怎么写强异常安全**：

1. **Copy-and-swap 惯用法**：
```cpp
class A {
public:
    A& operator=(const A& o) {
        A tmp(o);              // 先拷贝（可能抛，但原对象未动）
        swap(*this, tmp);      // swap 是 noexcept 的
        return *this;
    }                          // tmp 析构时释放旧资源
private:
    friend void swap(A& a, A& b) noexcept { std::swap(a.p_, b.p_); }
};
```
优点：自动处理自赋值；异常发生在拷贝阶段时原对象完全不变。

2. **RAII 管理所有资源**：资源析构函数必须不抛异常。栈展开时会调用析构，若析构抛异常 → `terminate`。

3. **把副作用放到最后**（"先做可能失败的事，再做不可逆的事"）。

4. **`noexcept` 标记不该抛的函数**：析构、移动构造/赋值、`swap`。

**为什么移动操作要 `noexcept`**：
`std::vector` 扩容时要提供强异常安全 —— 它会**把旧元素移动到新缓冲区**，若移动可能抛异常且中途失败，就无法回滚（旧元素已被改）。因此 `vector` 用 `std::move_if_noexcept`：只有当移动是 `noexcept` 时才用移动，否则**退回拷贝**。

```cpp
A(A&&) noexcept;   // ✅ 标上，vector 才会用你的移动
```

**析构函数与异常**：
- 析构默认隐式 `noexcept`；若内部可能抛异常，**必须捕获**，否则栈展开时再抛 → `std::terminate`。
- `throw` 在 `noexcept` 函数里会立刻 `terminate`。

**实践清单**：
- 用智能指针/容器管理资源（零法则）。
- 赋值用 copy-and-swap。
- 移动操作标 `noexcept`。
- 析构不抛。
- 只在真正异常的场景用异常，不要用异常做控制流。""",
    ),
    (
        "C++",
        "noexcept",
        2,
        r"""`noexcept` 有什么用？什么时候该加？""",
        r"""`noexcept` 声明"这个函数不抛异常"，编译器可以据此优化，且**抛异常时直接 `std::terminate`**（不会展开栈）。

**语法**：
```cpp
void f() noexcept;                     // 不抛
void g() noexcept(true);               // 同上
void h() noexcept(false);              // 可能抛（默认）
template <class T>
void foo() noexcept(noexcept(T{}));    // 条件 noexcept（依赖 T）
void operator delete(void*) noexcept;  // 标准库里的例子
```

**三个影响**：

1. **优化**：调用方无需生成栈展开代码，代码更小更快；编译器可做更强的优化。
2. **容器行为（最重要）**：`std::vector` 扩容时用 `std::move_if_noexcept` —— **移动构造不是 `noexcept` 时会退回拷贝**，性能大降。
```cpp
class A {
    A(A&&) noexcept;                       // ✅ vector 扩容会用移动
    A(A&&);                                // ❌ vector 退化为拷贝
};
```
3. **接口契约**：告诉调用者"这里不会失败"。

**该加 `noexcept` 的地方**：
- **移动构造/移动赋值**（关键！）
- **析构函数**（本来就隐式 `noexcept`）
- **`swap`**
- 简单的 getter、`size()`、`empty()` 等无失败可能的函数
- 内存释放、`clear()`

**不该加的地方**：
- 可能抛的函数（如会分配内存的容器操作、会 `stoi` 的解析）—— 加了会在异常时直接 `terminate`，比抛异常更难排查。
- **不要**为了性能给不确定的函数加 `noexcept`。

**注意**：
- `noexcept` 是**声明**而非检查：若函数内部真的抛了，行为是 `terminate` 而不是"编译错误"。
- `noexcept(expr)` 的形式可以按模板参数条件化，例如：
```cpp
template <class T>
class Wrapper {
    T t_;
public:
    Wrapper(Wrapper&&) noexcept(std::is_nothrow_move_constructible_v<T>) = default;
};
```
- `noexcept` 参与**重载决议**（自 C++17 起，函数指针类型含 noexcept，但重载决议不区分）。
- **`noexcept` 不是异常规范（`throw()`，已废弃）**。""",
    ),
    (
        "C++",
        "栈展开",
        2,
        r"""什么是栈展开（stack unwinding）？""",
        r"""当异常被抛出后，控制权从抛出点向**最近的匹配 catch** 传递，沿途**已构造完整的局部对象逐一析构**，这个过程就是栈展开。

```cpp
void f() {
    std::string s = "hello";       // ① 构造
    Resource r;                    // ② 构造
    throw std::runtime_error("x"); // ③ 抛出 → s、r 依次析构（逆序）
}
```

**关键点**：

1. **析构顺序**：与构造相反（后构造的先析构）。
2. **只有"构造完成"的对象会被析构**：若构造函数中途抛异常，**已构造的成员和基类会被析构**，但**该对象自身的析构函数不会被调用**。
```cpp
class A {
    std::string a_, b_;
public:
    A() : a_("x"), b_(throwing()) {}   // b_ 构造抛异常
    // a_ 会被析构；~A() 不会被调用
};
```
3. **`noexcept` 函数内抛异常 → 不展开，直接 `terminate`**。
4. **析构函数抛异常会 `terminate`**（若在展开过程中抛出第二个异常，C++11 起直接 terminate）。
5. **栈展开有成本**：需要编译器生成"异常表"/"着陆垫"（landing pad）信息，这也是为什么有些项目（如 Google 风格指南的部分子集、游戏引擎）**禁用异常**（`-fno-exceptions`）—— 但要同时放弃 `std::vector::at` 等会抛的标准库设施。

**与 RAII 的关系**：栈展开是 RAII 能工作的机制 —— 只要资源由局部对象的析构管理，无论正常返回还是异常退出都会被释放。这是 C++ 相比手动 `free` 的核心优势。

**在构造函数中抛异常的后果**：
- 对象不完整（部分成员已构造、部分未构造）。
- **对象的析构函数不会调用**，所以构造函数中"已经获取的资源"必须由**成员的析构**（RAII 成员）负责，或提前在构造函数里 catch 后释放。

**性能提示**：异常的**抛出开销大**（查找 handler、可能涉及 unwinding table），但**不抛时几乎零成本**（"zero-cost exceptions" 指的就是正常路径无开销）。因此异常适合"真正的异常"，不适合高频控制流。""",
    ),
    (
        "C++",
        "构造函数抛异常",
        3,
        r"""构造函数抛异常会发生什么？析构函数能抛异常吗？""",
        r"""**构造函数抛异常**：

1. **对象自身的析构函数不会被调用**（因为对象从未构造完成）。
2. **已经构造完成的成员和基类会被析构**（逆序）。
3. **已经获取的裸资源会泄漏**（如果有的话）。

```cpp
class Bad {
    int* p_;
    std::string s_;
public:
    Bad() : p_(new int(1)), s_(throwing()) {}
    // 抛异常时：s_ 若已构造则析构；p_ 不会被 delete → 泄漏！
    ~Bad() { delete p_; }   // 不会被调用
};
```

**正确写法（RAII 成员）**：
```cpp
class Good {
    std::unique_ptr<int> p_;     // 成员自己管理
    std::string s_;
public:
    Good() : p_(std::make_unique<int>(1)), s_(throwing()) {}
    // 抛异常时 p_ 的析构函数会自动 delete —— 无泄漏
};
```

**函数式 try 块**（处理成员初始化列表里的异常）：
```cpp
class A {
    Member m_;
public:
    A() try : m_(init()) {
        // 构造函数体
    } catch (const std::exception& e) {
        // 这里：m_ 及已构造的基类/成员已被析构
        throw;   // 通常要重新抛出（或转换异常类型）
    }
};
```

**析构函数抛异常**：

- 析构默认隐式 `noexcept`。
- 若析构在**栈展开过程中**抛出第二个异常 → **`std::terminate`**（C++11 起；C++98 是 UB）。
- 即析构**不是**在展开过程中被调用，抛异常也可能因 `noexcept` 而 terminate。

**结论：析构函数不应该抛异常。** 若内部操作可能失败（如 `fclose`、`commit`）：
1. **在析构里 `try/catch` 并吞掉/记录**。
2. 提供显式的 `close()` / `commit()` 方法让调用者处理失败，析构只做"尽力而为的清理"。

```cpp
~Connection() {
    try { if (open_) doClose(); }
    catch (...) { /* 记录日志，绝不外抛 */ }
}
```

**设计原则**：
- **构造函数要么成功构造完整对象，要么抛异常**（不要"半初始化"）。
- 复杂初始化用"两段式"或工厂函数返回 `std::optional` / `expected`（C++23）。
- 资源都交给 RAII 成员，构造失败时自动回收。""",
    ),
    (
        "C++",
        "内存泄漏,工具",
        2,
        r"""怎么排查和避免内存泄漏？有哪些工具？""",
        r"""**避免（设计层面最重要）**：
1. **RAII**：所有资源由对象生命周期管理（`unique_ptr`/`shared_ptr`/容器/`lock_guard`）。
2. **零法则**：不手写拷贝/析构，交给标准库组件。
3. **避免循环引用**：`shared_ptr` 互相持有 → 用 `weak_ptr` 打破。
4. **异常安全**：用 RAII 保证异常路径也释放。
5. **注意 `new[]`/`delete[]` 配对**，优先用 `vector`/`string`。
6. **容器存指针时**用 `unique_ptr` 而非裸指针。

**常见泄漏原因**：
- `new` 之后忘记 `delete`（尤其提前 `return` 或异常路径）。
- `shared_ptr` 循环引用。
- 容器里存裸指针，`clear()` 只删指针不删对象。
- 资源句柄（fd、socket、锁）未释放 —— 广义泄漏。
- `setjmp/longjmp` 跳过了析构。

**检测工具**：

| 工具 | 特点 |
|---|---|
| **AddressSanitizer（ASan）** | `-fsanitize=address -g`，编译期插桩，运行时报告泄漏/越界/UAF；**首选**，快且准 |
| **LeakSanitizer（LSan）** | 通常随 ASan 一起启用；`ASAN_OPTIONS=detect_leaks=1` |
| **Valgrind（memcheck）** | 无需重新编译，但慢 10~50 倍；适合测试环境 |
| **`-D_GLIBCXX_DEBUG`** | 检测 STL 迭代器误用 |
| **`mtrace`/`mallinfo`** | glibc 自带，粗粒度 |
| **静态分析** | clang-tidy、Coverity、PVS-Studio |
| **`heaptrack`/`massif`** | 内存增长分析（找"泄漏点"而非"泄漏事实"） |
| **`/proc/<pid>/status` 的 VmRSS** | 线上粗查内存增长 |
| **tcmalloc/jemalloc 的统计接口** | 生产环境采样 |

**ASan 用法**：
```bash
g++ -fsanitize=address -fno-omit-frame-pointer -g main.cpp
./a.out
# 报告 "Direct leak of N byte(s) ... allocated by ... "
```

**排查流程（线上泄漏）**：
1. 确认是真泄漏还是缓存/碎片（观察 RSS 是否单调增长且在压力后不回落）。
2. 用 `pmap`/`massif` 看是哪类分配（堆、mmap、线程栈）。
3. 在测试环境用 ASan/LSan 复现。
4. 若无法复现，用**采样分析**（tcmalloc 的 heap profiler、`gperftools`）。
5. 检查是否有不断增长的容器/缓存（业务层面"泄漏"）。

**注意**：Linux 上"内存不还给 OS"不一定是泄漏（glibc arena、jemalloc 的缓存策略）；用 `malloc_trim` 或换分配器可以改善。""",
    ),
    (
        "C++",
        "内存池,分配器",
        3,
        r"""什么是内存池？为什么需要它？怎么实现一个简单的对象池？""",
        r"""**动机**：

1. **`malloc`/`new` 有开销**：加锁（多线程）、查找空闲块、元数据、系统调用。
2. **内存碎片**：频繁分配/释放不同大小会造成外部碎片。
3. **缓存局部性**：通用分配器把对象散落各处。
4. **确定性**：实时系统不能接受不可预测的分配延迟。

**内存池的思路**：**一次性申请一大块**，自己切分管理，避免频繁进通用分配器。

**最简单的定长对象池（free list）**：

```cpp
template <class T, size_t N>
class ObjectPool {
    union Slot { T obj; Slot* next; };      // 未使用时复用存储存 next
    std::array<Slot, N> slots_;
    Slot* free_ = nullptr;
public:
    ObjectPool() { for (size_t i = 0; i + 1 < N; ++i) slots_[i].next = &slots_[i+1];
                   free_ = N ? &slots_[0] : nullptr; }

    template <class... Args>
    T* create(Args&&... a) {
        if (!free_) return nullptr;
        Slot* s = free_; free_ = s->next;
        return new (&s->obj) T(std::forward<Args>(a)...);   // placement new
    }
    void destroy(T* p) {
        p->~T();
        Slot* s = reinterpret_cast<Slot*>(p);
        s->next = free_; free_ = s;
    }
};
```

**要点**：
- **`union` 复用存储**：空闲时存 `next` 指针，使用时存对象 —— 零额外开销。
- **placement new / 显式析构**：手动管理对象生命周期。
- **线程安全**：多线程需加锁，或做**线程本地池**（TLS）避免竞争。
- **对齐**：`alignof(T)` 要考虑（`std::aligned_storage` 或 `alignas`）。

**更完善的池**：

| 类型 | 适用 |
|---|---|
| 定长对象池（free list） | 同类型对象频繁创建销毁（连接、消息） |
| slab 分配器 | 按大小分类的多档池 |
| arena / bump allocator | 批量申请、批量释放（编译器、解析器） |
| `std::pmr` 内存资源 | C++17 标准化的多态分配器 |

**C++17 的 `std::pmr`**：
```cpp
#include <memory_resource>
std::pmr::monotonic_buffer_resource pool(buf, sizeof buf);   // 单调递增，不单独释放
std::pmr::vector<int> v(&pool);
```
- `monotonic_buffer_resource`：只增不减，析构时整体释放 —— 极快。
- `unsynchronized_pool_resource`：按大小分档的池。
- 适合"生命周期一致的批量对象"（如一次请求的临时数据）。

**经典案例**：`boost::pool`、tcmalloc/jemalloc（通用分配器内部的 thread cache + size class，本质是精细化的池）。

**注意**：池会**延长内存占用时间**（不还给 OS），且**误用会导致更难查的 bug**（对象生命周期手工管理）。**先用 profile 确认分配是瓶颈**再引入。""",
    ),
    (
        "C++",
        "operator new,分配过程",
        3,
        r"""`new` 表达式的完整过程是怎样的？`operator new` 怎么重载？""",
        r"""**`new T(args)` 分两步**：

1. **分配内存**：调用 `operator new(sizeof(T))`（可重载），返回未初始化的内存。
2. **构造对象**：在这块内存上调用 `T::T(args)`。

```cpp
T* p = new T(args);
// 等价于：
void* mem = ::operator new(sizeof(T));      // ① 可能抛 std::bad_alloc
T* p;
try {
    p = ::new (mem) T(args);                 // ② placement new 构造
} catch (...) {
    ::operator delete(mem);                  // 构造失败要释放内存
    throw;
}
```

**`delete p` 也是两步**：先调 `~T()`，再调 `operator delete(p)`。

**可重载的形式**：

```cpp
// 全局重载（影响所有 new）
void* operator new(std::size_t n);
void* operator new[](std::size_t n);
void operator delete(void* p) noexcept;
void operator delete[](void* p) noexcept;
// C++17 起还有对齐版本
void* operator new(std::size_t n, std::align_val_t al);
```

**类内重载（只影响该类型）**：
```cpp
struct Small {
    static void* operator new(std::size_t n) { return pool.alloc(n); }
    static void operator delete(void* p) { pool.free(p); }
};
Small* s = new Small();   // 用类内版本
```

**placement new**（在指定地址构造，不分配）：
```cpp
alignas(T) unsigned char buf[sizeof(T)];
T* p = new (buf) T(args);     // 不分配内存
p->~T();                      // 必须手动析构
```
用途：容器实现（`vector` 的缓冲区）、对象池、内存映射 I/O。

**nothrow 版本**：
```cpp
T* p = new (std::nothrow) T;   // 失败返回 nullptr 而不是抛 bad_alloc
```

**注意点**：
1. **`new` 和 `delete` 必须配对**；`new[]`/`delete[]` 必须配对（用错是 UB，实践中会漏析构或堆损坏）。
2. **重载 `operator new` 后必须重载 `operator delete`**（构造抛异常时要能释放）。
3. **`operator new` 返回的指针必须满足 `alignof(std::max_align_t)` 或指定对齐**。
4. **不要重载全局 `new`** 除非有充分理由（会影响所有代码、第三方库）。
5. **`operator new(0)` 必须返回一个合法的非空指针**。
6. C++17 起 `operator new` 有 **aligned 重载**，需要对齐的类型（如 SIMD）会用它。
7. **`malloc` 与 `new` 不能混用**（`free` 不知道构造/析构，且分配器不同）。

**实践**：需要控制分配行为时，优先用**自定义 `std::allocator` + `std::pmr`**，而不是重载全局 `new`。""",
    ),
    (
        "C++",
        "placement new",
        2,
        r"""什么是 placement new？什么时候用？""",
        r"""**placement new**：**在指定内存地址上构造对象，不分配内存**。

```cpp
#include <new>
alignas(T) unsigned char buf[sizeof(T)];
T* p = new (buf) T(args);   // 在 buf 上构造
// ...
p->~T();                     // 必须手动析构
```

**标准形式**：
```cpp
void* operator new(std::size_t, void* p) noexcept { return p; }   // 不做任何事
```

**用途**：

1. **容器实现**：`std::vector` 预分配裸内存，按需 placement new 构造元素。
```cpp
Alloc a;
T* p = a.allocate(n);            // 裸内存
a.construct(p, args...);         // placement new（C++17 后被 traits 取代）
```
2. **对象池**：从池里取一块内存构造对象。
```cpp
T* obj = new (pool.alloc()) T(args);
```
3. **`std::optional`/`std::variant`**：内部是 union + 手动生命周期管理。
4. **内存映射寄存器/共享内存**：在固定地址构造对象。
5. **避免异常时的部分构造**（如实现 `make_shared` 的一次分配）。

**注意点**：
1. **必须手动调用析构**（`p->~T()`），placement new 不会自动析构。
2. **内存必须正确对齐**（`alignas(T)` 或 `alignof`），否则 UB（ARM 上直接崩）。
3. **必须保证 `buf` 的生命周期覆盖对象**，否则悬垂。
4. **不要对已有对象 placement new**（会覆盖而不析构，资源泄漏）；除非是有意"复用"。
5. **`delete p` 对 placement new 的对象是 UB**（内存不是 `operator new` 分配的）—— 只能显式析构 + 手动交还内存。
6. **C++17 起 `std::launder`**：某些场景（const 成员、union 复用）需要用 `std::launder` 才合法地拿到新对象的指针。

**与 `std::construct_at`（C++20）的关系**：
```cpp
std::construct_at(p, args...);   // 等价于 placement new，但可用于 constexpr
```
这是实现容器时更现代的选择。

**反模式**：把 placement new 当作"性能优化"随便用 —— 手工生命周期管理是 bug 高发区，**优先用容器和智能指针**。""",
    ),
    (
        "C++",
        "生命周期,UB",
        3,
        r"""什么是对象生命周期？有哪些常见的未定义行为（UB）？""",
        r"""**对象生命周期**：从对象**构造完成**（构造函数返回）到**析构开始**。期间对象"存在"，可以访问；之外访问就是 UB。

```cpp
struct A { int x; };
A a;                  // 生命周期：构造完 → 离开作用域
new (buf) A;          // 生命周期开始
((A*)buf)->~A();      // 生命周期结束
// 之后访问 ((A*)buf)->x 是 UB
```

**常见 UB 清单**（面试高频）：

1. **有符号整数溢出**：`INT_MAX + 1`（无符号是有定义的环绕）。
2. **空指针解引用 / 越界访问**：
```cpp
int a[3]; a[3] = 0;      // UB
```
3. **悬垂指针/引用的使用**（对象已销毁）。
4. **未初始化的读**：`int x; std::cout << x;`
5. **`delete` 非 `new` 分配的指针**、`free` 非 `malloc` 的指针、双重释放。
6. **`new[]` 配 `delete`**（应配 `delete[]`）。
7. **有符号左移溢出**、`<<` 负数是 UB；右移负数实现定义。
8. **除零**（整数除零是 UB）。
9. **修改字符串字面量**：
```cpp
char* s = "abc"; s[0] = 'x';   // UB（C++11 起是编译错误）
```
10. **违反严格弱序的比较器**（`sort` 传 `<=`）。
11. **数据竞争**（两个线程无同步访问同一内存，至少一个写）。
12. **对象生命周期外访问**（placement new 后未构造就访问）。
13. **`vptr` 调用时机错误**（构造/析构期间调用虚函数）。
14. **`reinterpret_cast` 后非法解引用**（类型别名违反 strict aliasing）。
15. **`std::vector` 扩容后用旧迭代器**。
16. **`union` 里读非活跃成员**（除公共初始序列）。
17. **缺少 `return` 的非 void 函数**（除 main）。
18. **`std::memcpy` 非平凡类型**。

**为什么 UB 危险**：编译器**假设 UB 不会发生**来优化。所以"在本地能跑"不代表正确 —— 换编译器/优化等级就可能崩。

**检测工具**：
- **UBSan**：`-fsanitize=undefined`，捕获有符号溢出、空指针、对齐等。
- **ASan**：越界、UAF、泄漏。
- **TSan**：数据竞争。
- **MSan**：未初始化读（需要所有依赖都插桩）。
- **静态分析**：clang-tidy、`-Wall -Wextra -Wpedantic`。

**工程建议**：把 `-fsanitize=address,undefined` 加进 CI 的测试构建 —— 成本低、收益极高。""",
    ),
    (
        "C++",
        "optional,variant,any",
        2,
        r"""`std::optional`、`std::variant`、`std::any` 分别解决什么问题？""",
        r"""三者都是 C++17 引入的**词汇类型**（vocabulary types），用于表达"可能没有值"和"多类型"。

**`std::optional<T>`**：表示"可能有，也可能没有 T"。

```cpp
std::optional<int> parse(const std::string&);
if (auto v = parse(s)) { std::cout << *v; }
int x = parse(s).value_or(0);
```
- 用于替代"返回 `-1` 表示失败"、"返回裸指针判空"。
- **不是**为了表达错误原因（那用 `expected`/异常/error code）。C++23 的 `std::expected<T,E>` 才是"值或错误"。
- 大小：`sizeof(optional<T>) >= sizeof(T)`（需要存标志位，可能 padding）。

**`std::variant<Ts...>`**：**类型安全的 union**，同一时刻只存其中一个类型。

```cpp
std::variant<int, std::string> v;
v = 42;
v = "hi";
std::visit([](auto&& x) { std::cout << x; }, v);   // 访问需要 visit
if (auto p = std::get_if<int>(&v)) { /* 是 int */ }
```
- 用于替代"带 tag 的 union"、"基类 + dynamic_cast 的有限集合"。
- `std::visit` 会对所有可能类型生成代码（代码膨胀）；也可以用 `if (holds_alternative<T>)`。
- 若 `variant` 处于 `valueless_by_exception` 状态（某类型构造抛异常），访问会抛 `bad_variant_access`。
- **大小 = 最大成员大小 + tag**（可能有 padding）。

**`std::any`**：可以装**任意**类型（类型擦除）。

```cpp
std::any a = 42;
a = std::string("x");
if (auto p = std::any_cast<int>(&a)) { /* ... */ }
```
- 用于"属性字典"、动态配置、脚本绑定。
- **代价**：可能堆分配（大类型）、每次访问有类型检查、`any_cast` 失败抛异常。
- **性能敏感的热路径避免 `any`**（和 `std::function` 类似的开销）。
- C++17 的 `any` 要求类型可拷贝；**C++26 有 `std::move_only_function`，但 `any` 不能存只移类型**（可用 `unique_ptr<Base>` 或自己实现）。

**对比总结**：

| 类型 | 表达能力 | 大小 | 典型用途 |
|---|---|---|---|
| `optional<T>` | 有/无 T | max(sizeof(T), 1) + 标志 | 可选返回值 |
| `variant<Ts...>` | 是其一 | 最大成员 + tag | 状态机、JSON 值 |
| `any` | 任意类型 | 指针 + SBO | 动态属性 |

**实践建议**：优先 `optional`（语义单一、开销小）；有限类型集合用 `variant`；`any` 只在真正"无法预知类型"时用。""",
    ),
    (
        "C++",
        "string_view",
        2,
        r"""`std::string_view` 是什么？有哪些坑？""",
        r"""`std::string_view` 是**对一段字符序列的只读视图**（指针 + 长度），**不拥有**数据。

```cpp
void f(std::string_view sv);      // 接受 string、const char*、字面量，无需构造 string
f("hello");                       // 零拷贝
std::string s = "world";
f(s);                             // 零拷贝
```

**优点**：
1. **零拷贝**：传参不再需要 `const std::string&` 或临时构造。
2. **统一的字符串参数类型**。
3. 支持 `substr`（O(1)，返回 view 而非新串）、`remove_prefix/suffix`。

**核心坑：不拥有数据，容易悬垂**。

```cpp
// ❌ 1) 绑定临时 string
std::string_view sv = std::string("temp") + "x";   // 临时 string 已销毁 → 悬垂

// ❌ 2) 返回局部 string 的 view
std::string_view bad() {
    std::string s = "hi";
    return s;                       // 悬垂
}

// ❌ 3) 存进容器/成员，原串销毁后仍使用
struct Holder { std::string_view sv; };
Holder h{ std::string("x")};        // 悬垂

// ❌ 4) 指向 string 的 view，string 扩容/移动后失效
auto sv = std::string_view(s);      // 注意：s 修改后 sv 可能失效
```

**其它注意点**：
1. **没有 `c_str()`** —— 不保证以 `\0` 结尾！传给 C API 前必须转成 `std::string`。
2. **不是 `const` 的**：`string_view` 的数据实际可写（如果原对象非 const），但标准不鼓励借它修改。
3. **不能保证 Null-terminated**，`std::string_view(sub.begin(), sub.end())` 得到的 view 无 `\0`。
4. **比较是按内容**（不是按指针），所以可直接 `==`。
5. **`std::string_view` 的 `data()` 可以为 nullptr（默认构造）**，此时 `size() == 0`。
6. C++20 起有 `sv.contains()`、`starts_with()`、`ends_with()`。

**使用建议**：
- **只用它做函数参数**（"借用一段字符"），不要长期持有。
- **不要**作为成员变量或返回值（除非生命周期明确）。
- 需要长期持有 → `std::string`；需要零拷贝 → `string_view` 但保证生命周期。
- 与 C API 交互前 `std::string(sv)`。

**同类问题**：`std::span<T>`（C++20）对数组有相同的"视图"语义与生命周期风险；`std::function_ref`（C++26 提案）类似。""",
    ),
    (
        "C++",
        "TLS,线程局部存储",
        2,
        r"""线程局部存储（TLS）是什么？`thread_local` 有什么开销？""",
        r"""**TLS** 让每个线程拥有**独立的变量副本**，互相不干扰。

```cpp
thread_local int counter = 0;      // 每线程一份

// 每线程一个缓冲区，避免加锁
thread_local std::vector<char> buf;
buf.clear();                        // 只属于当前线程，无需同步
```

**用途**：
1. **避免锁**：每线程的缓冲/统计/缓存（真实世界的 allocator thread cache 就是 TLS）。
2. **线程上下文**：当前请求 ID、日志上下文、事务状态。
3. **errno 的实现**（POSIX 的 `errno` 就是 TLS）。
4. **单例的线程版本**。

**三种存储期**：
```cpp
thread_local int a;                    // 全局 thread_local
void f() { static thread_local int b; } // 局部 static thread_local
struct S { static thread_local int c; };
```

**开销**：
1. **访问需要查表**：实现上用 **TLS 索引 + 运行期查找**（`__tls_get_addr`），比访问普通全局变量慢（一次函数调用或特殊的段寄存器偏移）。
   - 动态库里的 TLS 甚至更慢（需要调用 `__tls_get_addr`）。
2. **初始化开销**：函数内 `static thread_local` 有**首次初始化的守卫**（每线程都要检查），热路径要留意。
3. **每个线程都要分配一块 TLS 空间**：线程多时内存开销可观（TLS 块 ~ 几百字节到几 KB）。
4. **线程析构**：`thread_local` 对象的析构在**线程结束时**执行，顺序与构造相反；主线程结束时才析构。
5. **不能跨线程共享** —— 这不是缺点，但要注意"以为共享了"的逻辑错误。

**使用模式**：

```cpp
// 每线程缓存（无锁）
struct Cache {
    thread_local static std::unordered_map<int,int> m;
};

// 或单例（C++11 起函数内 static 是线程安全的）
Cache& cache() { static thread_local Cache c; return c; }
```

**注意事项**：
1. **不要用 TLS 存"应该在主线程/其他线程"的东西**，会导致数据不一致。
2. **运行时创建大量线程 + TLS 会占用可观内存**（如线程池的每线程缓冲）。
3. **不要在 TLS 析构里访问其他 TLS 变量**（析构顺序问题）。
4. **TLS 会影响 `fork()`**：子进程只保留调用线程的 TLS，其他线程的 TLS 丢失。
5. **协程（C++20）与 TLS 不兼容**：协程可能在不同线程上恢复 —— 这是 TLS 在异步框架里的主要痛点，所以异步代码更倾向显式传 context。

**性能对比**：`thread_local` 通常比加锁快（特别是竞争激烈时），但比直接访问成员变量慢。**先 profile**。""",
    ),
    (
        "C++",
        "协程,C++20",
        3,
        r"""C++20 协程是什么？它和线程有什么区别？""",
        r"""**协程（coroutine）**是**可暂停、可恢复**的函数。C++20 引入三个关键字：

- **`co_await`**：等待一个 awaitable，暂停当前协程。
- **`co_yield`**：产出一个值并暂停（生成器）。
- **`co_return`**：返回值并结束。

**最简生成器示例**：
```cpp
Generator<int> range(int n) {
    for (int i = 0; i < n; ++i)
        co_yield i;
}

for (int v : range(5)) std::cout << v;   // 0 1 2 3 4
```

**与线程的本质区别**：

| 维度 | 协程 | 线程 |
|---|---|---|
| 调度 | **用户态**协作式（显式挂起） | 内核态抢占式 |
| 切换开销 | 极小（约几十纳秒，只保存少量寄存器/帧） | 大（微秒级，涉及内核、TLB、缓存） |
| 数量 | 可以几十万个 | 几千个就是极限 |
| 并发 | 单线程内可并发（无需锁） | 真并行（需同步原语） |
| 阻塞 | 阻塞会阻塞整个线程 | 只阻塞该线程 |
| 内存 | 每个协程一个帧（可放堆上） | 每线程 MB 级栈 |

**关键点**：
1. **协程是"单线程内的并发"** —— 适合 **I/O 密集**（大量并发连接），不适合 CPU 密集（不能利用多核）。
2. **协程标准库不完整**：C++20 只提供了**语言机制**（`coroutine_handle`、`promise_type`、awaiter 协议），**没有提供 `task`、`generator`、调度器** —— 需要自己写或用库（cppcoro、asio、folly、libunifex）。
3. **`promise_type` 协议**：编译器为每个协程生成一个"协程帧"和一个 promise 对象，控制 `initial_suspend`、`final_suspend`、`return_value`、`yield_value`、`await_transform`、`unhandled_exception` 等定制点。**写一个能用的 `Task` 需要几十行样板**。
4. **`co_await` 的 awaitable 需要实现** `await_ready`、`await_suspend`、`await_resume`。
5. **无栈协程 vs 有栈协程**：C++20 是**无栈协程**（状态存在堆上的协程帧），省内存但不能随意在任意函数里挂起（只能在协程体内）。
6. **与 TLS 冲突**：协程可在不同线程恢复，TLS 语义不成立 → 异步框架用显式 context。
7. **`std::generator<T>`（C++23）** 终于提供了标准生成器；**`std::execution`/`std::task`（C++26）** 在推进中。

**为什么性能好**：切换只涉及保存/恢复少量寄存器和栈帧指针，且无系统调用、无内核态切换、缓存友好。

**实践建议**：
- **I/O 密集、超高并发**（百万连接、游戏服务器）→ 协程/async 框架。
- **CPU 密集** → 线程池。
- **想用现成方案** → C++23 的 `std::generator`、Boost.Asio 的协程支持、或者干脆用 Go/Rust 的异步生态。
- **不要在协程里做阻塞调用**（会阻塞整个线程）。""",
    ),
    (
        "C++",
        "concepts,C++20",
        2,
        r"""C++20 的 concepts 是什么？它比 SFINAE 好在哪？""",
        r"""**concepts** 是对模板参数**施加具名约束**的机制，把"SFINAE 的隐晦错误"变成"清晰的编译期检查"。

```cpp
// 定义 concept
template <class T>
concept Addable = requires(T a, T b) {
    { a + b } -> std::convertible_to<T>;    // 要求表达式合法且返回类型可转换
    sizeof(T) > 0;                          // 要求为真
};
```

**三种约束写法**：
```cpp
// 1) 简写形式
template <Addable T> T sum(T a, T b);

// 2) requires 子句
template <class T> requires Addable<T>
T sum(T a, T b);

// 3) 尾随 requires
template <class T> T sum(T a, T b) requires Addable<T>;
```

**标准库的 concepts**（`<concepts>`）：`std::integral`、`std::floating_point`、`std::same_as`、`std::convertible_to`、`std::derived_from`、`std::invocable`、`std::regular`、`std::totally_ordered`、`std::ranges` 里的一大堆。

**比 SFINAE 好在哪**：

| 维度 | SFINAE / enable_if | concepts |
|---|---|---|
| 可读性 | 难懂（`enable_if_t<is_integral_v<T>, int> = 0`） | 直白（`requires std::integral<T>`） |
| 错误信息 | 几十行模板展开噪声 | "constraint not satisfied: T doesn't satisfy integral" |
| 重载顺序 | 无偏序，容易二义性 | **有约束偏序**：更严格的约束优先 |
| 组合 | 手写逻辑与 | `requires (A<T> && B<T>)` 或 `concept C = A && B` |
| 简写用法 | 无 | `void f(std::integral auto x)` |

**约束偏序（subsumption）**——这是 concepts 独有的能力：
```cpp
template <class T> void f(T);                          // 最弱
template <std::integral T> void f(T);                  // 更严格 → 优先匹配
template <std::integral T> requires (sizeof(T) > 2) void f(T);  // 更严格
```
调用 `f(42)` 会选最严格的那个。SFINAE 时代这需要手动设计重载。

**`requires` 表达式**的四种要求：
```cpp
template <class T>
concept C = requires(T a) {
    a.size();                   // 简单要求：表达式合法
    typename T::value_type;     // 类型要求
    { a.begin() } -> std::input_iterator;   // 复合要求（含返回值约束）
    requires std::copyable<T>;  // 嵌套要求
};
```

**注意**：
- concepts **不改变**模板实例化语义，只是把约束前置。
- concepts 可以有**语义要求**（文档性的，编译器不检查，如 `std::regular` 要求等价性）。
- C++20 的 concepts 让**模板错误信息**质量大幅提升，这是它最大的实用价值（编译期"报错可读性"）。

**实践建议**：新代码一律用 concepts 替代 `enable_if`；`std::ranges` 就是 concepts 的最大规模应用。""",
    ),
    (
        "C++",
        "ranges,C++20",
        2,
        r"""C++20 的 ranges 是什么？有什么好处？""",
        r"""**ranges** 把算法与**范围（range）** 结合，支持**惰性视图**和**管道组合**。

```cpp
#include <ranges>
namespace rv = std::views;

std::vector<int> v{1,2,3,4,5,6,7,8};

// 旧写法
std::vector<int> r;
std::copy_if(v.begin(), v.end(), std::back_inserter(r),
             [](int x){ return x % 2 == 0; });

// ranges 写法
auto even = v | rv::filter([](int x){ return x % 2 == 0; })
              | rv::transform([](int x){ return x * x; })
              | rv::take(3);
for (int x : even) std::cout << x << ' ';   // 4 16 36
```

**核心改进**：

1. **不用写 `begin()`/`end()`**：`std::ranges::sort(v)` 直接接受容器。
2. **视图（views）是惰性的**：`filter`/`transform` **不立即计算**，遍历时才求值 → **零中间容器**，也不产生临时拷贝。
3. **可组合**：`|` 管道串联，形成"处理流水线"。
4. **借用检查（borrowed range）**：能检测出"返回 dangling 视图"的问题。
5. **投影（projection）**：`std::ranges::sort(v, {}, &Person::age);` 直接按成员排序。
6. **concepts 约束**：`std::ranges::input_range`、`random_access_range` 等让错误信息清晰。

**常用 views**：
```cpp
rv::filter(pred)         // 过滤
rv::transform(f)         // 映射
rv::take(n), rv::drop(n) // 取/跳过前 n
rv::take_while / drop_while
rv::reverse
rv::join                  // 扁平化
rv::split(delim)          // 按分隔符切（C++20）
rv::elements<N>           // 取 tuple 第 N 个
rv::keys / rv::values     // map 的键/值
rv::iota(a, b)            // 生成序列
rv::common / rv::counted
```

**注意点**：
1. **视图持有引用**：`auto ev = v | rv::filter(...);` 中 `ev` 引用 `v`；若 `v` 销毁则悬垂。
   - 典型坑：函数返回视图（`return v | rv::filter(...)` 若 v 是局部变量 → 悬垂）。C++20 的 borrowed_range 检查能捕获一部分。
2. **`std::views::filter` 的迭代器是 forward 而非 random access**，某些算法用不了。
3. **性能**：多个视图链在遍历时**每层都有函数调用**，编译器通常能内联（等价于手写循环），但复杂链可能有开销；**先写清晰版，再 profile**。
4. **`std::ranges::to`（C++23）** 填补了"视图转容器"的缺口：
```cpp
auto v = std::views::iota(1, 10) | std::ranges::to<std::vector>();
```
5. **C++20 缺 `zip`**（C++23 才有 `views::zip`）。

**实践建议**：ranges 让"数据转换流水线"非常易读，**新代码优先用**；注意视图的**生命周期**是最大的坑。""",
    ),
    (
        "C++",
        "快排优化,性能",
        3,
        r"""`std::vector` 遍历为什么比 `std::list` 快？性能优化的一般方法论是什么？""",
        r"""**缓存友好性是现代性能的第一原则。**

`vector` 遍历 vs `list` 遍历：

| 维度 | vector | list |
|---|---|---|
| 内存布局 | 连续 | 每节点一次堆分配，地址随机 |
| cache line 利用率 | 一个 64B line 装 16 个 int | 每个节点只用到部分 line |
| 预取（prefetcher） | 顺序访问，硬件预取命中 | 随机跳转，预取失效 |
| 实测 | 快 5~50 倍（常见） | — |

即使链表"插入是 O(1)"，在现代 CPU 上遍历的开销也让它常常输给 `vector`。

**性能优化的一般方法论**：

1. **先测量，不要猜**
   - `perf stat` / `perf record`：找热点函数、cache miss、分支预测失败。
   - **不要**凭直觉优化。
2. **优化算法与数据结构**
   - 复杂度降阶（O(n²) → O(n log n)）是最大的收益。
   - 选择缓存友好的容器（默认 `vector`）。
3. **减少内存分配**
   - `reserve`、对象池、`std::pmr`、移动而非拷贝。
4. **提高缓存局部性**
   - 数据紧凑（`struct of arrays` 而非 `array of structs`，若只访问部分字段）。
   - 热点数据放一起；伪共享隔离。
5. **减少分支**
   - 把常见路径放前面；避免热循环里的虚函数/间接调用；用查表替代分支。
6. **编译器友好**
   - `const`/`constexpr`/`noexcept`/`inline`；`[[likely]]`/`[[unlikely]]`（C++20）。
   - 检查编译器是否真的矢量化了（`-fopt-info-vec`、`-Rpass=loop-vectorize`）。
7. **并行化**
   - 多线程、SIMD 向量化（`std::simd` C++26，或编译器自动向量化）。
8. **权衡与验证**
   - 每次改动后**重新 benchmark**；防止"优化了一个不是瓶颈的地方"。
   - 注意 benchmark 的方法论（避免被优化掉、多次取中位数、`-O2` 且模拟真实负载）。

**常见的反直觉结论**：
1. **链表往往不如 vector**（缓存）。
2. **`unordered_map` 常不如排序的 `vector` + 二分**（元素少时）。
3. **虚函数在热循环里可能是瓶颈**（分支预测）。
4. **`shared_ptr` 的原子引用计数在多核下是缓存行争用源**。
5. **多线程不一定更快**（同步开销、伪共享、Amdahl 定律）。
6. **`-O3` 不总是比 `-O2` 快**（代码膨胀/icache miss）。

**工具清单**：`perf`、`valgrind --tool=callgrind`、`VTune`、`gprof`（旧）、`google benchmark`、`hyperfine`、`compiler explorer`（godbolt.org）看汇编。""",
    ),
    (
        "C++",
        "cout,编译期陷阱",
        2,
        r"""`std::cout` 为什么比 `printf` 慢？怎么加速？""",
        r"""**原因：C++ 流需要与 C 的 stdio 保持同步**。

默认情况下，`std::ios_base::sync_with_stdio(true)` 使得每次 `std::cout` 操作都要与 `printf`/`stdout` 协调（保证混用 `printf` 和 `cout` 时输出顺序一致），这带来锁与虚函数调用的开销。

**加速方法**：

```cpp
int main() {
    std::ios::sync_with_stdio(false);   // 解除与 C stdio 的同步
    std::cin.tie(nullptr);              // 解除 cin/cout 的绑定（避免每次 cin 前 flush cout）
    // ...
}
```

- `sync_with_stdio(false)`：**最大收益**，通常能让 `cin`/`cout` 快 2~5 倍，接近甚至超过 `scanf`/`printf`。
- `cin.tie(nullptr)`：避免每次 `cin >> x` 前自动 `cout.flush()`。

**注意**：
1. 关闭同步后**不要混用 `printf` 与 `cout`**（顺序不再保证）。
2. 关闭后 `stdout` 的缓冲行为可能与预期不同，交互式程序要注意。
3. 多线程下 `cout` 的 `operator<<` 之间**不是原子的**（一个 `<<` 是原子的，但 `cout << a << b` 不是），并发输出需要自己加锁。

**其它性能考虑**：
- **`std::endl` 会 flush**，而 `'\n'` 不会 —— 循环输出时用 `'\n'`，否则每次 flush 是系统调用。
```cpp
for (int i = 0; i < 1e6; ++i)
    std::cout << i << '\n';    // ✅
    // std::cout << i << std::endl;  // ❌ 慢 10~100 倍
```
- **格式化**：`std::format`（C++20）比 `ostream` 快且安全（类型安全、无 `%d` 不匹配），也比 `printf` 快。
```cpp
std::cout << std::format("{} {}\n", 1, "x");
```
- **输出量大时**自己拼缓冲再一次性输出。

**面试延伸**：为什么 `printf` 快？因为它直接走 `vfprintf`，没有 `ostream` 的虚函数、locale、sentry 等开销。而 `C++20 std::format` 走的是**编译期格式串解析 + 更少的间接调用**，兼顾了性能与安全。""",
    ),
    (
        "C++",
        "编译器优化,内联",
        2,
        r"""`inline` 一定会内联吗？编译器在什么情况下内联？""",
        r"""**`inline` 不强制内联**。它的**本意**是允许在多个翻译单元中重复定义同一函数（ODR 例外），链接器会合并。是否真正内联由编译器决定。

**编译器倾向于内联的情况**：
1. 函数体小（如 getter/setter）。
2. 调用点少（只有一两个调用者）。
3. 能带来明显收益（消除调用开销、暴露更多优化机会）。
4. `-O2`/`-O3` 下的热函数。
5. LTO（链接期优化）可以跨翻译单元内联。
6. 函数带 `__attribute__((always_inline))` / `__forceinline`（强制，但可能被忽略）。

**编译器**不**内联的情况**：
1. 函数体大（有启发式阈值，如 GCC 的 `-finline-limit`）。
2. 递归（深度不确定）。
3. 通过函数指针/虚函数调用（除非去虚化）。
4. 取函数地址（仍然可以，但会生成一份 out-of-line 版本）。
5. `-O0`（不优化）。
6. 函数体包含 `setjmp`、可变参数等。
7. `__attribute__((noinline))`。

**内联的收益与代价**：

| 收益 | 代价 |
|---|---|
| 消除调用开销 | **代码膨胀** → icache miss |
| 暴露常量传播、死代码消除 | 编译时间增加 |
| 更好的寄存器分配 | 调试信息更难（栈帧丢失） |
| 使更多优化成为可能 | 可能让"热函数"被冷代码挤走 |

**关键提示**：
1. **不要手写 `inline` 来"优化性能"**（现代编译器自己会判断）。
2. `inline` 用于**头文件里的函数定义**（避免 ODR 冲突）。
3. 类内定义的成员函数**隐式 inline**。
4. **虚函数可以内联**（如果能静态确定类型，或去虚化）：
```cpp
struct Base { virtual void f(); };
Base b; b.f();         // 可能内联（静态确定是 Base）
Base* p = get(); p->f(); // 通常不能
```
5. **`final` 有助于去虚化**：
```cpp
struct D final : Base {};
D* d = get(); d->f();   // 编译器知道 D 不会再被继承 → 可内联
```
6. **PGO（Profile-Guided Optimization）**：用真实负载的 profile 指导内联与分支布局，收益常优于手动调优。
7. 关注**内联决策**：`-Winline`（GCC）、`-Rpass=inline`（Clang）可以看编译器是否如你所愿。""",
    ),
    (
        "C++",
        "去虚化,devirtualization",
        3,
        r"""什么是去虚化？有哪些手段？""",
        r"""**去虚化（devirtualization）** 把虚函数调用变成**直接调用**，从而可以内联、消除 vptr 解引用。

**编译器自动做的**：

1. **静态类型已知**：
```cpp
Derived d;            // 栈对象，类型确定
d.f();                // 直接调用（若 f 是虚函数，也能知道就是 Derived::f）
```

2. **`final` 类/函数**：
```cpp
struct D final : Base {};
D* p = ...; p->f();   // 知道不会有更派生的重写 → 可去虚化
```

3. **构造/析构期间**：vptr 已知。
4. **同一次调用后的类型收窄**（speculative devirtualization）：编译器可以插入"类型检查 + 直接调用 + fallback"。
5. **LTO** 能看到更多上下文。

**手工手段**：

1. **`final`**：语义清晰、零成本，是最简单的优化。
```cpp
struct Handler final { virtual void handle(); };
```

2. **CRTP / 模板**：编译期多态，从根本上没有虚调用（见前文 CRTP 题）。

3. **类型擦除 + 内联**：把"小对象优化"放进 `std::function` 风格的封装，减少分配但仍有间接调用。

4. **分支替代虚函数**（**谨慎**）：
```cpp
// 用枚举 + switch 替代虚函数，可能更快（分支预测友好）
enum class Kind { A, B, C };
switch (k) { case Kind::A: a.f(); break; ... }
```
优点：可内联、无间接跳转、代码在一处（icache 友好）。缺点：不开放（新增类型要改 switch）、可能代码膨胀。

5. **把虚函数调用移出热循环**：
```cpp
// ❌ 每次循环都虚调用
for (auto& s : shapes) s->area();
// ✅ 先算出函数指针/结果
```

6. **值语义 + `variant` + `std::visit`**：`variant` 的 `visit` 通常被编译器优化成 switch，可比虚函数快，且无堆分配（但类型集合封闭）。

**代价与权衡**：

| 手段 | 收益 | 代价 |
|---|---|---|
| `final` | 高（零成本） | 限制继承 |
| 模板/CRTP | 最高（可完全内联） | 代码膨胀、类型封闭 |
| switch/variant | 高 | 类型集合封闭、难扩展 |
| 手工类型检查 | 中 | 脆弱、易错 |

**如何验证**：看汇编（`objdump -d`）里是否还有 `call *rax` 这类间接调用；或 `-Rpass=devirt`（Clang）。

**实践建议**：
1. **先 profile**，只在确认虚调用是热点时优化。
2. **优先用 `final`**（成本最低）。
3. **接口设计上"类型集合封闭"的场景**（渲染、状态机）可以用 `variant` 替代继承。
4. 记住：**多态是设计工具**，不要为了性能牺牲可维护性 —— 大部分程序中虚调用开销可以忽略。""",
    ),
    (
        "C++",
        "C++11 新特性",
        1,
        r"""列举 C++11 引入的重要特性。""",
        r"""**C++11 是 C++ 的分水岭**，从"带类的 C"变成现代语言。

**语言核心**：
1. **`auto`** 类型推导、**`decltype`**。
2. **右值引用 `&&` + 移动语义 + 完美转发**（`std::move`/`std::forward`）。
3. **lambda 表达式**（闭包）。
4. **可变参数模板**。
5. **`nullptr`**（替代 `NULL`）。
6. **统一初始化 `{}`**（initializer_list）。
7. **`enum class`**（强类型枚举，不隐式转 int）。
8. **`override` / `final`**。
9. **`= default` / `= delete`**。
10. **`static_assert`**（编译期断言）。
11. **`constexpr`**（编译期求值，C++11 限制多）。
12. **`alignas` / `alignof`**、`thread_local`。
13. **`using` 别名模板**（`template<class T> using Vec = std::vector<T>;`）。
14. **`noexcept`**。
15. **委托构造、继承构造**。
16. **强类型空指针、`char16_t`/`char32_t`、UTF-8 字面量**。
17. **范围 for**（`for (auto& x : c)`）。
18. **原始字符串字面量 `R"(...)"`**、用户自定义字面量。
19. **属性 `[[noreturn]]` 等**。

**标准库**：
1. **`<thread>`、`<mutex>`、`<atomic>`、`<condition_variable>`、`<future>`** —— 内存模型与并发。
2. **`<chrono>`** 时间库。
3. **`<random>`** 随机数。
4. **`<unordered_map>` / `<unordered_set>`**（哈希容器）。
5. **智能指针** `unique_ptr`/`shared_ptr`/`weak_ptr`。
6. **`std::array`、`std::tuple`、`std::function`、`std::bind`、`std::initializer_list`**。
7. **`std::regex`**（性能一般，实践中少用）。
8. **`std::ratio`、`std::enable_if`、`<type_traits>`**。

**最重要的影响**：**移动语义 + 智能指针 + lambda + 并发库**，这四者让 C++ 从"手动管理资源"转向"RAII + 值语义 + 表达性代码"。

**面试延伸**：C++11 之后各版本的关键增量：
- **C++14**：泛型 lambda、`decltype(auto)`、变量模板、`make_unique`、`constexpr` 放宽。
- **C++17**：结构化绑定、`if constexpr`、`std::optional/variant/any/string_view`、`std::filesystem`、折叠表达式、`inline` 变量、并行算法、**保证的拷贝消除**。
- **C++20**：concepts、ranges、协程、modules、`std::format`、`std::span`、三路比较 `<=>`、`std::atomic` 等待/通知、日历时区。
- **C++23**：`std::expected`、`std::print`、`std::generator`、`std::mdspan`、`std::flat_map`、`if consteval`。
- **C++26**（进行中）**：`std::execution`（sender/receiver）、反射、契约、`std::simd`、静态分析。""",),
    (
        "C++",
        "三路比较,C++20",
        2,
        r"""C++20 的 `<=>`（三路比较）和 `std::strong_ordering` 是什么？""",
        r"""> 三路比较运算符 `<=>`（俗称 **spaceship operator**）一次定义，编译器自动合成 `<`、`<=`、`>`、`>=`。

```cpp
struct Point {
    int x, y;
    auto operator<=>(const Point&) const = default;   // 自动生成全部比较
};
Point a{1,2}, b{3,4};
if (a < b) ...;      // 自动可用
if (a == b) ...;     // == 需要单独 default（默认不合成 ==）
```

**注意**：`operator<=>` 默认**不**生成 `==`，需要 `bool operator==(const Point&) const = default;`（或 C++20 起可写 `= default` 于两者）。

**三类比较结果类型**：

| 类型 | 语义 | 例子 |
|---|---|---|
| `std::strong_ordering` | 完全排序，`a == b` 表示**可互换** | `int`、`std::string` |
| `std::weak_ordering` | 有序但 `a == b` 不意味可互换 | 忽略大小写的字符串 |
| `std::partial_ordering` | 存在"不可比"（unordered） | `double`（有 NaN） |
| `std::strong_equality` / `weak_equality` | 只比较相等（C++20 中一般用 `bool operator==`） | — |

```cpp
double a = 0.0/0.0;   // NaN
if (auto r = (a <=> a); r == std::partial_ordering::unordered) ...
```

**返回类型可以不同**：`<=>` 的返回类型决定能合成哪些运算符：
- 返回 `strong_ordering` → 全部六个比较可用。
- 返回 `bool`（如 `std::optional` 的场景）→ 只生成 `==`/`!=`。
- 返回 `std::partial_ordering` → 生成全部但含 unordered。

**与 `==` 的关系**：`a != b` 现在可以由 `a == b` 自动合成（C++20 起 `operator!=` 不再需要），这修复了 C++17 中"定义了 `==` 但忘记 `!=`"的常见 bug。

**实践建议**：
1. **值类型（聚合）默认加 `= default` 的两个比较**，一行顶六个函数。
2. 手写 `<=>` 时返回 `std::strong_ordering`，用 `std::tie` 或 `std::cmp_*` 组合：
```cpp
auto operator<=>(const T& o) const {
    if (auto c = a <=> o.a; c != 0) return c;
    return b <=> o.b;
}
```
3. **浮点**：`std::partial_ordering`（NaN 存在）；需要"总序"用 `std::strong_order`。
4. 显式写 `<` 仍然可以（比如需要与旧代码兼容），但建议统一到 `<=>`。
5. `= default` 的比较要求**所有成员都可比较**，且顺序按**声明顺序**。""",
    ),
    (
        "C++",
        "std::format",
        2,
        r"""`std::format` 是什么？比 `printf` 和 `ostream` 好在哪？""",
        r"""`std::format`（C++20，`<format>`）是**类型安全、高效、可扩展**的格式化库，源自 `{fmt}` 库。

```cpp
#include <format>
std::string s = std::format("{} + {} = {}", 1, 2, 3);       // 1 + 2 = 3
std::format("{:>10}", "hi");                                // 右对齐宽度 10
std::format("{:08.3f}", 3.14159);                           // 0003.142
std::format("{0} {1} {0}", "a", "b");                       // a b a
std::format("{{}}");                                        // 字面量 {} 
```

**对比**：

| 维度 | `printf` | `ostream` | `std::format` |
|---|---|---|---|
| 类型安全 | ❌（`%d` 传 `double` 是 UB） | ✅ | ✅ |
| 位置无关参数 | ❌（顺序必须匹配） | ✅ | ✅ |
| 性能 | 快 | 慢（虚函数、locale、同步） | **快**（编译期解析格式串） |
| 可读性 | 差（格式串与参数分离） | 中（链式 `<<`） | **好** |
| 扩展自定义类型 | ❌ | 需要 `operator<<` | ✅（`std::formatter` 特化） |
| 国际化/本地化 | 有限 | 依赖 locale | 有 `std::format_localized` |

**性能**：`std::format` 在编译期解析格式串并生成直接的格式化代码，避免了 `printf` 的运行时格式解析和 `ostream` 的多次虚调用。基准测试中通常**显著快于 `ostream`**，与 `printf` 相当或更快。

**相关**：
- **`std::print`（C++23）**：直接输出，比 `std::cout << std::format(...)` 更快更简洁：
```cpp
std::print("{} {}", 1, 2);
std::println("hello {}", name);
```
- **`std::format_to`**：输出到迭代器，避免中间 `string`：
```cpp
std::format_to(std::back_inserter(buf), "{}", x);
```
- **编译期检查**：C++23 起 `std::format` 的格式串是 `consteval` 检查的，`"{:d}"` 传字符串会在**编译期**报错。C++26 有 `std::format_string` 的编译期验证。

**自定义类型的格式化**：
```cpp
struct Point { int x, y; };
template <>
struct std::formatter<Point> {
    constexpr auto parse(auto& ctx) { return ctx.begin(); }
    auto format(const Point& p, auto& ctx) const {
        return std::format_to(ctx.out(), "({}, {})", p.x, p.y);
    }
};
std::format("{}", Point{1,2});   // (1, 2)
```

**注意**：
1. **不建议用 `to_string`**（不灵活、精度不可控）。
2. `std::format` 用 `{}` 而非 `%`；要输出字面 `{}` 用 `{{`/`}}`。
3. 对**浮点**的默认格式与 `printf` 的 `%g` 类似。
4. **运行时格式串**（如用户输入）用 `std::vformat`（性能较低的路径）—— 正常路径都是编译期格式串。

**实践建议**：新代码一律 `std::format`/`std::print`；老的 `printf` 只有在跨语言边界（如 C API 的 `printf` 族）时才保留。""",
    ),
    (
        "C++",
        "span,C++20",
        2,
        r"""`std::span` 是什么？什么时候用它替代指针+长度？""",
        r"""`std::span<T>`（C++20）是**对连续内存序列的非拥有视图**：一个指针 + 一个长度。

```cpp
void process(std::span<const int> data);

std::vector<int> v{1,2,3};
int arr[5] = {};
std::array<int,3> a{};

process(v);        // 容器
process(arr);      // C 数组
process(a);        // std::array
process({v.data() + 1, 3});   // 指针 + 长度（显式）
```

**解决的问题**：函数参数需要"一段连续数据"，旧写法要么：
- `void f(const int* p, size_t n)` —— 容易忘记传 n、可能不一致。
- `void f(const std::vector<int>& v)` —— 强制调用者用 `vector`（不能用数组、`array`、子区间）。
- 模板 `template<size_t N> void f(const int (&a)[N])` —— 只接受数组。

`std::span` 是**统一、安全**的接口。

**特性**：
1. **轻量**：`sizeof(span) == 16`（指针 + 大小），可平凡拷贝。
2. **支持动态与静态长度**：`std::span<int>`（运行期长度）与 `std::span<int, 3>`（编译期长度）。
3. **`subspan` / `first` / `last`**：O(1) 取子区间（返回 span）。
4. **可写**：`std::span<int>` 可修改元素；`std::span<const int>` 只读。
5. **`as_bytes()` / `as_writable_bytes()`**：转换为字节视图。

```cpp
void parse(std::span<const std::byte> buf);
```

**坑（和 `string_view` 一样是视图）**：
1. **不拥有数据** → 悬垂风险：
```cpp
std::span<const int> bad() {
    std::vector<int> v{1,2,3};
    return v;            // ❌ v 已销毁
}
```
2. **构造自临时容器**同样危险：`process(std::vector<int>{1,2,3})` 在**完整表达式结束**后临时对象销毁 —— 如果函数只在该表达式内用完是安全的，跨语句保存则 UB。
3. **不能改变大小**（不像 vector）。
4. **`span` 不能从 `std::initializer_list` 安全构造为长期成员**（初始化列表底层数组的生命周期短）。
5. **`std::span` 的 `extent` 是 `dynamic_extent` 时大小为运行期**。

**实践建议**：
- **函数参数**需要"连续数据"：用 `std::span<const T>` 替代 `(T*, n)` 和 `const vector<T>&`。
- **不要**作为成员或返回值长期持有（除非生命周期明确）。
- C++20 前用 `gsl::span`（Guidelines Support Library）或自己写。
- 与 `string_view` 的关系：`string_view` 是"字符 span 的特化"，但有自己的字符串接口。

**相关**：`std::mdspan`（C++23）是**多维**版本，用于矩阵/张量视图。""",),
    (
        "C++",
        "多线程,线程创建",
        1,
        r"""`std::thread` 怎么用？有哪些注意事项？""",
        r"""```cpp
#include <thread>
void work(int id) { /* ... */ }

int main() {
    std::thread t(work, 1);        // 启动
    t.join();                      // 等待结束
    // 或 t.detach();              // 分离（慎用）
}
```

**传参**：
```cpp
std::thread t(f, 1, std::ref(x));   // 默认拷贝；要引用必须 std::ref
```
**注意**：`std::thread` 的构造函数会**拷贝/移动**参数到线程内部存储，再传给函数 —— 所以形参是**右值**。要传引用必须 `std::ref`，否则改的是副本。

**生命周期风险（最大的坑）**：
```cpp
std::thread t([]{ std::this_thread::sleep_for(1s); });
// t 析构时若仍 joinable → std::terminate！
```
`std::thread` 析构时若**仍可 join（joinable）**，会直接调用 `std::terminate`。所以必须保证：
- 每条路径都 `join()` 或 `detach()`。
- **RAII 包装**是标准做法：
```cpp
class ThreadGuard {
    std::thread t_;
public:
    explicit ThreadGuard(std::thread t) : t_(std::move(t)) {}
    ~ThreadGuard() { if (t_.joinable()) t_.join(); }
};
```

**局部变量引用问题**：
```cpp
void bad() {
    int x = 0;
    std::thread t([&x]{ /* 用 x */ });
    t.detach();          // ❌ x 已销毁，悬垂
}
```

**其它**：
1. **`detach` 后线程仍在跑**，但 `main` 结束时进程退出会**杀掉所有线程**，且不保证资源清理。
2. **无法线程安全地获取返回值** → 用 `std::async`/`future`/`promise`。
3. **`std::thread` 不可拷贝、只可移动** → 放进容器要 `std::move`。
4. **`hardware_concurrency()`** 获取逻辑核数（可能为 0）。
5. **线程局部存储**：`thread_local`。
6. **不要在线程函数里跨线程抛异常**：未捕获的异常 → `std::terminate`；必须在线程函数内 `try/catch`。
7. **线程 id**：`t.get_id()`、`std::this_thread::get_id()`；C++20 起可 `std::format("{}", id)`。
8. **`std::jthread`（C++20）**：`join` 语义 + **停止令牌（stop_token）**，是更好的默认选择：
```cpp
std::jthread jt([](std::stop_token st) {
    while (!st.stop_requested()) { /* work */ }
});
// 析构时自动请求停止并 join
```

**实践建议**：**优先用线程池**（`std::jthread` 或框架的池），避免手工 `thread` 的生命周期问题；确实需要手工管理时**一定用 RAII 守卫**。""",),


    (
        "C++",
        "编译流程,预处理,链接",
        1,
        r"""C++ 从源码到可执行文件经历了哪些阶段？""",
        r"""**四个阶段**：

```
源码.cpp ──预处理──▶ 展开后的 .i ──编译──▶ 汇编 .s ──汇编──▶ 目标 .o ──链接──▶ 可执行文件
```

**1. 预处理（Preprocessing）**：`g++ -E`
- 展开 `#include`（文本插入）、替换 `#define` 宏。
- 处理条件编译 `#if/#ifdef`、`#pragma`，去掉注释。
- 输出仍是**纯文本 C++ 代码**，此时还没有任何类型检查。

**2. 编译（Compilation）**：`g++ -S`
- 词法分析 → 语法分析（AST）→ 语义分析（类型检查、重载解析、模板实例化、`constexpr` 求值）。
- 生成中间表示并优化（内联、常量传播、循环优化、向量化）。
- 生成目标平台的汇编代码。**这是最耗时的阶段**。

**3. 汇编（Assembly）**：`g++ -c`
- 汇编器把 `.s` 翻成机器码，产出**目标文件 `.o`**（ELF/PE/Mach-O）。
- 里面有代码段 `.text`、数据段、**符号表**、**重定位表**。

**4. 链接（Linking）**
- **符号解析**：把各 `.o` 与静态库中的符号引用和定义对上。
- **重定位**：填好相对地址与外部符号地址。
- 动态库（`.so`/`.dll`）在**运行时**由动态链接器加载。报 `undefined reference to ...` 就是这一步失败。

```bash
g++ -E main.cpp -o main.i   # 只看预处理
g++ -S main.cpp -o main.s   # 生成汇编
g++ -c main.cpp -o main.o   # 生成目标文件
g++ main.o -o main          # 链接
```

**相关概念**：
- **翻译单元（TU）**：一个 `.cpp` 加上它包含的所有头文件，是编译的基本单位。
- **ODR（单一定义规则）**：同一实体在程序中只能有一个定义（`inline` 是例外）。
- **静态链接 vs 动态链接**：前者把库代码拷进可执行文件（体积大、无外部依赖），后者运行时加载（体积小、可共享、需目标机有对应库）。
- 排查工具：`nm`（看符号）、`objdump`/`readelf`（看目标文件）、`c++filt`（还原修饰名）。

**编译慢的对策**：前置声明/PIMPL 减少头文件依赖、`extern template` 抑制模板重复实例化、ccache/distcc、预编译头（PCH）、C++20 modules。""",
    ),
    (
        "C++",
        "前置声明,编译依赖",
        2,
        r"""什么是前置声明？它和 `#include` 该怎么选？""",
        r"""**前置声明**只声明类型存在，不给完整定义：

```cpp
class Foo;          // 前置声明（不完整类型）
void f(Foo* p);     // ✅ 指针/引用可以
```

**能用不完整类型的场景**：声明指针/引用类型的形参、返回值、成员；函数原型；类型别名；模板参数。
**必须完整定义的场景**：按值传参/返回、定义对象或值成员、继承、访问成员或调用方法、`sizeof`。

```cpp
class Foo;
class Bar {
    Foo* p_;      // ✅ 指针成员
    // Foo f_;    // ❌ 值成员需要完整定义
};
```

**好处**：
1. **减少编译依赖**：改 `Foo` 的定义不会导致只有指针的 `Bar` 重编译。
2. **加快编译**：少解析一个头文件（含其递归包含）。
3. **打破循环依赖**。

**风险（为什么现代实践更倾向直接 `#include`）**：
1. **脆弱且会静默出错**：
```cpp
// 若 Foo 实际是 typedef、别名模板、或在命名空间里
namespace a { class Foo; }
class Foo;   // 实际是 a::Foo，这里声明了全局 ::Foo，静默不一致！
```
2. **标准库类型一律不能前置声明** —— `std::string` 是 `basic_string<char>` 的 typedef，`std::iostream` 是模板实例，前置声明是 UB。要前向声明用 `<iosfwd>`。
3. **重构不友好**：把 class 改 struct、加命名空间后，前置声明处会静默失配。
4. include-what-you-use（IWYU）的实践倾向"宁可多包含"。

**实践建议**：
- **普通代码直接 `#include`**（正确性优先）。
- **大型项目的公共头文件**里，对第三方/重量级类型用前置声明或 PIMPL 优化编译时间。
- **绝对不要前置声明 `std::` 类型**（除 `<iosfwd>` 提供的）。
- 只需要 `std::ostream&` 形参时，`#include <iosfwd>` 而非 `<iostream>` —— 这是标准库专门为前置声明准备的。""",
    ),
    (
        "C++",
        "modules,C++20",
        3,
        r"""C++20 modules 是什么？它解决了什么问题？""",
        r"""**modules** 用**导入模块**替代 `#include` 的文本包含，是 C++ 编译模型几十年来最大的变革。

```cpp
// math.cppm
export module math;                 // 声明并导出模块
export int add(int a, int b) { return a + b; }
int helper() { return 1; }          // 不导出 → 外部不可见

// main.cpp
import math;
int main() { return add(1, 2); }
```

**解决的问题**：

| 维度 | `#include` | modules |
|---|---|---|
| 重复解析 | 头文件在每个 TU 里重新解析（主要编译开销） | 模块编译一次成 BMI，导入即用 |
| 宏污染 | 宏会泄漏给包含者 | 模块默认不导出宏 |
| 包含顺序 | 顺序会影响结果 | 无顺序依赖 |
| 重编译范围 | 头文件改一点，所有包含者重编译 | 只有模块接口变更才影响导入者 |
| 循环包含 | 需 include guard + 前置声明 | 模块依赖图，可处理 |
| 隐藏实现 | 靠匿名命名空间/PIMPL | 不导出即不可见 |

对大型项目（Chromium/LLVM 量级），编译时间常有数倍改善。

**语法要点**：
```cpp
export module m;                       // 主模块接口单元
export { int g(); class D {}; }        // 导出块
export import other;                   // 重导出（类似头文件的聚合）
import :part;                          // 导入模块分区

// 实现单元：module m;  （无 export）
```

**模块分区（partitions）**：把大模块拆成多个文件（`export module m:part;`）再由主单元聚合，利于并行编译与组织。

**现状与注意**：
1. **编译器支持**：MSVC 较完整；Clang 16+、GCC 13+ 基本可用；**CMake 3.28+** 有官方支持。
2. **标准库模块**（`import std;`）在 C++23 才落地，多数第三方库仍是头文件 —— **混用是常态**（模块里可以 `#include`）。
3. **构建系统适配**（依赖扫描、BMI 缓存）是落地的主要障碍。
4. **宏仍无法导出**，涉及宏的接口（`assert`、日志、平台检测）还要走头文件。
5. **IDE/调试支持**相对滞后。
6. **与 PCH 的区别**：modules 有语言级语义、依赖精确、隔离性好；PCH 只是编译器层面的加速技巧。

**实践建议**：新项目可以尝试（收益主要在大项目）；存量项目迁移成本高，通常先从新代码用起、逐步演进；**不要为了用 modules 而用**。""",
    ),
]
