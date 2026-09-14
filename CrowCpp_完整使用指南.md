# CrowCpp 完整使用指南

> CrowCpp 是一个用现代 C++ 编写的高性能 HTTP/WebSocket 微框架，路由风格类似 Python Flask。
> 本指南基于 Crow v1.2.x，涵盖从安装到部署的完整流程。

---

## 目录

1. [简介与特性](#一简介与特性)
2. [安装与编译](#二安装与编译)
3. [最小可运行示例](#三最小可运行示例)
4. [路由系统](#四路由系统)
5. [请求对象 (request)](#五请求对象-request)
6. [响应对象 (response)](#六响应对象-response)
7. [JSON 处理](#七json-处理)
8. [Mustache 模板引擎](#八mustache-模板引擎)
9. [HTTP 方法与状态码](#九http-方法与状态码)
10. [静态文件服务](#十静态文件服务)
11. [文件上传与下载](#十一文件上传与下载)
12. [中间件 (Middleware)](#十二中间件-middleware)
13. [WebSocket](#十三websocket)
14. [Cookie 与 Session](#十四cookie-与-session)
15. [错误处理](#十五错误处理)
16. [日志系统](#十六日志系统)
17. [应用配置](#十七应用配置)
18. [Blueprints（路由分组）](#十八blueprints路由分组)
19. [常见问题与调试](#十九常见问题与调试)
20. [完整实战项目](#二十完整实战项目)
21. [API 速查表](#二十一api-速查表)

---

## 一、简介与特性

CrowCpp（简称 Crow）的特点：

- **类 Flask 的直观路由**，支持类型安全的 URL 参数
- **Header-only**，提供单头文件版本，零依赖集成
- **内置 JSON**（无需第三方库）
- **内置 Mustache 模板引擎**
- **WebSocket** 支持
- **多线程并发**（io_service 池）
- **Multi-part 请求/响应**（文件上传）
- **中间件机制**（认证、CORS、日志等）
- 极高性能：单进程轻松达到每秒数十万请求

### Crow 与其他 C++ Web 框架对比

| 框架 | 易用性 | 性能 | 功能 | 适合场景 |
|------|--------|------|------|----------|
| Crow | ★★★★★ | ★★★★★ | 中等 | 轻量 API 服务、快速开发 |
| Drogon | ★★★☆ | ★★★★★ | 丰富 | 大型 Web 应用、ORM 需求 |
| oat++ | ★★★★ | ★★★★★ | 丰富 | 微服务、gRPC 风格 API |
| Boost.Beast | ★★☆ | ★★★★★ | 底层 | 需要完全控制的底层开发 |
| cpp-httplib | ★★★★ | ★★★★ | 基础 | 极小嵌入式 HTTP 服务 |

---

## 二、安装与编译

### 2.1 获取 Crow

**方式一：单头文件（推荐入门）**

```bash
# 从 GitHub Releases 下载 crow_all.h（包含所有代码，单文件）
wget https://github.com/CrowCpp/Crow/releases/download/v1.2.0/crow_all.h
# 重命名为 crow.h 使用
mv crow_all.h crow.h
```

**方式二：CMake FetchContent（项目集成推荐）**

```cmake
cmake_minimum_required(VERSION 3.15)
project(myapp CXX)

set(CMAKE_CXX_STANDARD 17)

include(FetchContent)
FetchContent_Declare(
    crow
    GIT_REPOSITORY https://github.com/CrowCpp/Crow.git
    GIT_TAG v1.2.0
)
FetchContent_MakeAvailable(crow)

add_executable(myapp main.cpp)
target_link_libraries(myapp Crow::Crow)
```

**方式三：Conan**

```bash
conan install crow/1.2.0@
```

**方式四：vcpkg**

```bash
vcpkg install crow
```

### 2.2 编译

**单头文件方式：**

```bash
# Linux / macOS
g++ -std=c++17 -O3 -pthread main.cpp -o server
./server
```

```bash
# Windows (MinGW)
g++ -std=c++17 -O3 -pthread main.cpp -lws2_32 -lmswsock -o server.exe
```

**注意点：**
- 必须开启 `-pthread`（多线程必需）
- 生产环境使用 `-O2` 或 `-O3` 优化
- 如果报错 `asio` 相关错误，需安装 Boost.Asio 或 standalone Asio（crow_all.h 已内嵌，无需额外安装）

---

## 三、最小可运行示例

```cpp
#include "crow.h"

int main()
{
    crow::SimpleApp app;  // SimpleApp = 无中间件的 App<>

    CROW_ROUTE(app, "/")([]() {
        return "Hello world!";
    });

    app.port(18080).run();  // 阻塞运行
}
```

编译运行后，浏览器访问 `http://localhost:18080` 即可看到 "Hello world!"。

### 3.1 启动流程解析

```cpp
crow::SimpleApp app;          // 1. 创建应用
CROW_ROUTE(app, "/")(...);    // 2. 注册路由
app.port(18080)               // 3. 设置端口
   .multithreaded()           //    启用多线程（所有 CPU 核心）
   .run();                    // 4. 启动服务器（阻塞）
```

---

## 四、路由系统

### 4.1 基本路由

```cpp
CROW_ROUTE(app, "/about")([] {
    return "About page";
});
```

### 4.2 URL 参数（类型安全）

```cpp
// 字符串参数
CROW_ROUTE(app, "/hello/<string>")([](std::string name) {
    return "Hello, " + name + "!";
});

// 整数参数（自动校验，非整数返回 404）
CROW_ROUTE(app, "/user/<int>")([](int id) {
    return crow::response("User ID: " + std::to_string(id));
});

// 无符号整数
CROW_ROUTE(app, "/item/<uint>")([](unsigned int id) {
    return "";
});

// 浮点数
CROW_ROUTE(app, "/price/<double>")([](double price) {
    return "";
});

// path 类型：匹配包含 / 的剩余路径
CROW_ROUTE(app, "/files/<path>")([](std::string filepath) {
    return "Requested: " + filepath;
});
```

**支持的路由类型一览：**

| 类型 | C++ 类型 | 说明 | 示例匹配 |
|------|----------|------|----------|
| `<int>` | `int64_t` | 有符号整数 | `/user/123` |
| `<uint>` | `uint64_t` | 无符号整数 | `/page/42` |
| `<double>` | `double` | 浮点数 | `/temp/36.5` |
| `<string>` | `std::string` | 不含 `/` 的字符串 | `/hello/world` |
| `<path>` | `std::string` | 含 `/` 的路径 | `/a/b/c` |

### 4.3 多个参数

```cpp
CROW_ROUTE(app, "/user/<int>/post/<int>")([](int user_id, int post_id) {
    return "user " + std::to_string(user_id) +
           ", post " + std::to_string(post_id);
});
```

### 4.4 带 request/response 参数的 handler

handler 参数可以混合使用，顺序不限：

```cpp
// 只读请求
CROW_ROUTE(app, "/info")([](const crow::request& req) {
    return "Method: " + crow::method_name(req.method);
});

// 只写响应（可以完全控制响应，但不读取请求）
CROW_ROUTE(app, "/created")([](crow::response& res) {
    res.code = 201;
    res.set_header("X-Custom", "yes");
    res.body = "done";
    res.end();  // 必须手动调用 end()
});

// 读写都有（完整控制）
CROW_ROUTE(app, "/full")([](const crow::request& req, crow::response& res) {
    res.code = 200;
    res.body = "Hello " + req.get_header_value("User-Agent");
    res.end();
});
```

### 4.5 同名路由冲突

路由按注册顺序匹配，先注册的先匹配。复杂路由建议把更具体的放在前面。

---

## 五、请求对象 (request)

### 5.1 URL 查询参数 (Query String)

```cpp
CROW_ROUTE(app, "/search")([](const crow::request& req) {
    // get() 返回 crow::query_string::value_proxy，可用 .as_integer() 等转换
    auto q     = req.url_params.get("q");              // 可能为 nullptr
    auto page  = req.url_params.get("page");           // 存在则返回，不存在返回空对象
    auto limit = req.url_params.get("limit");

    if (!q) return crow::response(400, "missing 'q'");

    std::string query = q.as_string();
    int page_num  = page ? page.as_integer() : 1;      // 带默认值
    int limit_num = limit ? limit.as_integer() : 20;

    return crow::response("q=" + query +
                          " page=" + std::to_string(page_num) +
                          " limit=" + std::to_string(limit_num));
});
```

**url_params 常用 API：**

```cpp
req.url_params.get("key")                // 获取单个值（可转 as_string/as_integer/as_double/as_bool）
req.url_params.get_list("key")           // 获取同名多值列表
req.url_params.keys()                    // 所有参数名
req.url_params.to_string()               // 原始查询字符串
```

### 5.2 HTTP 头

```cpp
req.get_header_value("Content-Type")     // 获取头（大小写不敏感）
req.headers                              // 所有头的 map
```

### 5.3 请求体

```cpp
req.body           // std::string 类型，原始请求体
req.method         // HTTPMethod 枚举
req.url            // 完整 URL 路径
req.remote_ip      // 客户端 IP 地址
req.raw_url        // 未解码的原始 URL
```

### 5.4 Multi-part 表单数据（文件上传时使用）

```cpp
req.get_body_params().get("field_name")  // 表单字段
req.get_file_params()                    // 上传的文件（见文件上传章节）
```

---

## 六、响应对象 (response)

### 6.1 构造方式

```cpp
crow::response res;                        // 默认 200
crow::response res(404);                   // 指定状态码
crow::response res(200, "body text");      // 状态码 + 字符串 body
crow::response res(json_value);            // 直接返回 JSON
crow::response res(crow::status::NOT_FOUND, "not found");
```

### 6.2 常用操作

```cpp
res.code = 200;                            // 状态码
res.body = "text";                         // 响应体
res.set_header("Content-Type", "application/json");
res.set_header("X-Request-Id", "abc123");
res.add_header("Set-Cookie", "session=xyz; Path=/");  // 同名头可多次添加
res.end();                                 // 手动结束响应（使用 response& 参数时必须调用）
res.is_completed();                        // 是否已结束
```

### 6.3 返回 JSON

```cpp
CROW_ROUTE(app, "/data")([] {
    crow::json::wvalue x;
    x["ok"] = true;
    x["msg"] = "success";
    return crow::response(x);   // 自动设置 Content-Type: application/json
});
```

---

## 七、JSON 处理

### 7.1 写入 JSON（wvalue）

```cpp
crow::json::wvalue x;
x["name"] = "Alice";
x["age"] = 30;
x["score"] = 95.5;
x["active"] = true;
x["nothing"] = nullptr;

// 数组
x["tags"] = crow::json::wvalue::list({"cpp", "web", "api"});

// 嵌套对象
crow::json::wvalue addr;
addr["city"] = "Beijing";
addr["zip"] = "100000";
x["address"] = std::move(addr);

// 数组中的对象
crow::json::wvalue item1;
item1["id"] = 1;
crow::json::wvalue item2;
item2["id"] = 2;
x["items"] = crow::json::wvalue::list({std::move(item1), std::move(item2)});

std::string json_str = x.dump();   // 序列化为字符串
```

### 7.2 读取 JSON（rvalue）

```cpp
auto body = crow::json::load(req.body);
if (!body) {
    return crow::response(400, "invalid JSON");
}

// 按类型取值
std::string name = body["name"].s();       // 字符串
int age          = body["age"].i();        // 整数
double score     = body["score"].d();      // 浮点
bool active      = body["active"].b();     // 布尔
crow::json::rvalue raw = body["anything"];// 原始值

// 类型检查（避免 t() 抛异常）
if (body.has("name") && body["name"].t() == crow::json::type::String) { ... }

// 数组遍历
for (auto& tag : body["tags"]) {
    CROW_LOG_INFO << tag.s();
}

// 对象遍历
for (const auto& [key, val] : body.items()) {
    CROW_LOG_INFO << key << " = " << val.s();
}
```

**取值函数对照表：**

| 函数 | 类型 | 说明 |
|------|------|------|
| `.s()` | String | 字符串 |
| `.i()` | Number (int) | 整数 |
| `.d()` | Number (float) | 浮点 |
| `.b()` | True/False | 布尔 |
| `.l()` | 数组 | 列表 |
| `.keys()` | 对象 | 所有键 |
| `.dump()` | 任意 | 转字符串 |

### 7.3 JSON 读写完整示例

```cpp
// POST /api/users  创建用户
CROW_ROUTE(app, "/api/users").methods(crow::HTTPMethod::POST)
([](const crow::request& req) {
    auto body = crow::json::load(req.body);
    if (!body || !body.has("name")) {
        return crow::response(400, R"({"error": "name is required"})");
    }

    // 模拟存储
    static int next_id = 1;
    crow::json::wvalue res;
    res["id"]   = next_id++;
    res["name"] = body["name"].s();
    res["created_at"] = "2026-09-14";
    return crow::response(201, res);
});
```

---

## 八、Mustache 模板引擎

### 8.1 目录配置

模板默认从可执行文件所在目录的 `templates/` 子目录加载。

```
project/
├── server
└── templates/
    ├── base.html
    └── user.html
```

可通过 `CROW_MUSTACHE_BASE_DIR` 环境变量或编译宏 `CROW_CAN_USE_CPP14` 等修改。

### 8.2 模板语法（Mustache）

`templates/hello.html`：

```html
<!DOCTYPE html>
<html>
<body>
  <h1>Hello, {{name}}!</h1>
  <ul>
  {{#items}}
    <li>{{.}}</li>
  {{/items}}
  </ul>
  {{^items}}<p>No items</p>{{/items}}
</body>
</html>
```

### 8.3 渲染模板

```cpp
CROW_ROUTE(app, "/page")([](const crow::request& req) {
    crow::mustache::context ctx;
    ctx["name"] = req.url_params.get("name").as_string();

    // 列表
    ctx["items"] = crow::mustache::context::list({"apple", "banana", "cherry"});

    // 嵌套对象
    crow::mustache::context user;
    user["id"] = 42;
    user["email"] = "a@b.com";
    ctx["user"] = std::move(user);

    // 加载并渲染（模板文件: templates/hello.html）
    return crow::mustache::load("hello.html").render(ctx);
});
```

### 8.4 预加载模板（提升性能）

```cpp
// 程序启动时把所有模板加载进内存
crow::mustache::set_base("templates");
auto tmpl = crow::mustache::load("hello.html");  // 之后 render 不再读磁盘
```

---

## 九、HTTP 方法与状态码

### 9.1 指定 HTTP 方法

```cpp
CROW_ROUTE(app, "/users").methods(crow::HTTPMethod::GET)([] {
    return "list users";
});

CROW_ROUTE(app, "/users").methods(crow::HTTPMethod::POST)([] {
    return "create user";
});

// 多个方法共用
CROW_ROUTE(app, "/resource")
.methods(crow::HTTPMethod::GET, crow::HTTPMethod::POST)([](const crow::request& req) {
    if (req.method == crow::HTTPMethod::GET)  return "got";
    return "posted";
});

// 也可用字符串（不推荐）
.methods("PUT"_method, "DELETE"_method)
```

**HTTPMethod 枚举值：** Get, Post, Put, Delete, Patch, Head, Options, Connect, Trace 等。

### 9.2 常用状态码

```cpp
crow::response(crow::status::OK);                  // 200
crow::response(crow::status::CREATED);             // 201
crow::response(crow::status::NO_CONTENT);          // 204
crow::response(crow::status::BAD_REQUEST);         // 400
crow::response(crow::status::UNAUTHORIZED);        // 401
crow::response(crow::status::FORBIDDEN);           // 403
crow::response(crow::status::NOT_FOUND);           // 404
crow::response(crow::status::CONFLICT);            // 409
crow::response(crow::status::INTERNAL_SERVER_ERROR); // 500
// 或直接写数字
crow::response(418, "I'm a teapot");
```

---

## 十、静态文件服务

Crow 内置静态文件支持，无需手写路由：

```cpp
app.port(8080)
   .multithreaded()
   .run();
```

静态文件规则：
- 默认提供可执行文件同级目录下的 `static/` 文件夹
- 访问 `http://localhost:8080/static/css/style.css` → 读取 `./static/css/style.css`

**自定义静态目录：**

```cpp
// 通过宏（编译时）
#define CROW_STATIC_DIRECTORY "public/"

// 或通过环境变量（运行时）
setenv("CROW_STATIC_DIRECTORY", "/var/www/assets", 1);

app.run();
```

**自定义静态路由前缀：**

```cpp
#define CROW_STATIC_ENDPOINT "/assets/"
// 访问 http://localhost:8080/assets/css/style.css
```

**注意：** 静态文件服务建议在生产环境用 Nginx 处理，Crow 只负责 API。

---

## 十一、文件上传与下载

### 11.1 文件上传（Multi-part 表单）

HTML 表单：

```html
<form action="/upload" method="post" enctype="multipart/form-data">
  <input type="file" name="file">
  <input type="submit">
</form>
```

Crow 处理：

```cpp
CROW_ROUTE(app, "/upload").methods(crow::HTTPMethod::POST)
([](const crow::request& req) {
    auto& files = req.get_file_params();

    auto it = files.find("file");
    if (it == files.end()) {
        return crow::response(400, "no file uploaded");
    }

    const auto& file = it->second;  // crow::multipart::file_info

    // file 可用属性：
    // file.filename      原始文件名
    // file.filetype      MIME 类型
    // file.filesize      文件大小（字节）
    // file.data          文件内容指针（char*）
    // file.len           数据长度

    // 保存到磁盘
    std::ofstream out("uploads/" + file.filename, std::ios::binary);
    out.write(file.data, file.len);
    out.close();

    crow::json::wvalue res;
    res["saved"]   = file.filename;
    res["size"]    = (int64_t)file.filesize;
    res["type"]    = file.filetype;
    return crow::response(200, res);
});
```

### 11.2 文件下载

```cpp
CROW_ROUTE(app, "/download/<string>")([](std::string filename) {
    std::ifstream ifs("files/" + filename, std::ios::binary);
    if (!ifs) return crow::response(404, "file not found");

    std::stringstream ss;
    ss << ifs.rdbuf();

    crow::response res;
    res.code = 200;
    res.set_header("Content-Type", "application/octet-stream");
    res.set_header("Content-Disposition",
                   "attachment; filename=\"" + filename + "\"");
    res.body = ss.str();
    return res;
});
```

---

## 十二、中间件 (Middleware)

中间件是 Crow 最强大的扩展机制，可在请求处理前后执行逻辑。

### 12.1 中间件基础结构

```cpp
struct MyMiddleware {
    // 每个请求私有的上下文，可跨 before/after/handler 共享
    struct context {
        std::string user_id;
        int64_t start_time;
    };

    // 请求处理前调用
    void before_handle(crow::request& req, crow::response& res, context& ctx) {
        ctx.start_time = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();

        // 认证检查示例：不通过则 res.end() 直接返回
        auto auth = req.get_header_value("Authorization");
        if (auth.empty()) {
            res.code = 401;
            res.body = R"({"error": "unauthorized"})";
            res.end();
        }
    }

    // 请求处理后调用（res.end() 后不会执行）
    void after_handle(crow::request& req, crow::response& res, context& ctx) {
        auto now = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();
        CROW_LOG_INFO << req.url << " took " << (now - ctx.start_time) << "ms";
    }
};
```

### 12.2 注册中间件

```cpp
int main() {
    crow::App<MyMiddleware> app;   // 在模板参数中注册

    CROW_ROUTE(app, "/api/data")([](const crow::request& req) {
        // 通过 req 获取中间件上下文
        auto& ctx = app.get_context<MyMiddleware>(req);
        return "user: " + ctx.user_id;
    });

    app.port(8080).run();
}
```

### 12.3 CORS 中间件（完整示例）

```cpp
struct CORSMiddleware {
    struct context {};

    void before_handle(crow::request& req, crow::response& res, context&) {
        res.set_header("Access-Control-Allow-Origin", "*");
        res.set_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
        res.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization");

        if (req.method == crow::HTTPMethod::Options) {
            res.code = 204;
            res.end();
        }
    }
    void after_handle(crow::request&, crow::response&, context&) {}
};

int main() {
    crow::App<CORSMiddleware> app;
    app.port(8080).multithreaded().run();
}
```

### 12.4 多个中间件

```cpp
crow::App<LoggingMiddleware, AuthMiddleware, CORSMiddleware> app;
// 执行顺序：Logging.before -> Auth.before -> CORS.before
//           -> handler -> CORS.after -> Auth.after -> Logging.after
```

---

## 十三、WebSocket

### 13.1 基础用法

```cpp
CROW_ROUTE(app, "/ws")
.websocket()
.onopen([](crow::websocket::connection& conn) {
    CROW_LOG_INFO << "WebSocket connected: " << conn.get_remote_ip();
})
.onmessage([](crow::websocket::connection& conn,
              const std::string& data, bool is_binary) {
    if (is_binary) {
        conn.send_binary(data);          // 回声（二进制）
    } else {
        conn.send_text("echo: " + data); // 回声（文本）
    }
})
.onclose([](crow::websocket::connection& conn, const std::string& reason) {
    CROW_LOG_INFO << "WebSocket closed: " << reason;
})
.onerror([](crow::websocket::connection& conn, const std::string& error) {
    CROW_LOG_ERROR << "WebSocket error: " << error;
});
```

### 13.2 广播消息（聊天室示例）

```cpp
#include <set>
#include <mutex>

std::set<crow::websocket::connection*> clients;
std::mutex clients_mutex;

CROW_ROUTE(app, "/chat")
.websocket()
.onopen([](crow::websocket::connection& conn) {
    std::lock_guard<std::mutex> lock(clients_mutex);
    clients.insert(&conn);
})
.onmessage([](crow::websocket::connection& conn,
              const std::string& data, bool) {
    std::lock_guard<std::mutex> lock(clients_mutex);
    for (auto* c : clients) {
        if (c != &conn) c->send_text(data);  // 广播给其他人
    }
})
.onclose([](crow::websocket::connection& conn, const std::string&) {
    std::lock_guard<std::mutex> lock(clients_mutex);
    clients.erase(&conn);
});
```

**注意：** WebSocket handler 在多线程下运行，共享数据必须加锁。连接指针 `&conn` 的生命周期由 Crow 管理，onclose 后不可再使用。

---

## 十四、Cookie 与 Session

### 14.1 读写 Cookie

```cpp
// 设置 Cookie（在响应中）
crow::response res;
res.add_header("Set-Cookie",
    "session_id=abc123; Path=/; HttpOnly; Max-Age=3600");

// 读取 Cookie（从请求中）
std::string get_cookie(const crow::request& req, const std::string& name) {
    std::string cookie_header = req.get_header_value("Cookie");
    // 手动解析 "a=1; b=2" 格式
    std::istringstream ss(cookie_header);
    std::string pair;
    while (std::getline(ss, pair, ';')) {
        auto pos = pair.find('=');
        if (pos != std::string::npos) {
            auto key = pair.substr(0, pos);
            // 去除前导空格
            key.erase(0, key.find_first_not_of(" "));
            if (key == name) return pair.substr(pos + 1);
        }
    }
    return "";
}

CROW_ROUTE(app, "/profile")([](const crow::request& req) {
    auto sid = get_cookie(req, "session_id");
    if (sid.empty()) return crow::response(401, "not logged in");
    return "session: " + sid;
});
```

### 14.2 Session 管理思路

Crow 没有内置 Session，常见做法：

1. **内存 Session + 中间件**：用 `std::unordered_map<std::string, SessionData>` + 中间件自动校验
2. **JWT**：用 `cpp-jwt` 或 `jwt-cpp` 库，无状态认证
3. **Redis**：`redis-plus-plus` 库存 Session 数据

示例（简化版内存 Session 中间件）：

```cpp
struct SessionData {
    std::string user_id;
    std::chrono::steady_clock::time_point expires;
};

std::unordered_map<std::string, SessionData> sessions;
std::mutex sessions_mutex;

struct SessionMiddleware {
    struct context {
        SessionData* session = nullptr;
    };

    void before_handle(crow::request& req, crow::response& res, context& ctx) {
        auto sid = get_cookie(req, "session_id");  // 上面的解析函数
        if (sid.empty()) return;  // 未登录，handler 自行处理

        std::lock_guard<std::mutex> lock(sessions_mutex);
        auto it = sessions.find(sid);
        if (it != sessions.end() &&
            it->second.expires > std::chrono::steady_clock::now()) {
            ctx.session = &it->second;
        }
    }
    void after_handle(crow::request&, crow::response&, context&) {}
};
```

---

## 十五、错误处理

### 15.1 默认错误页

Crow 对 404、500 等有默认 HTML 错误页。可以通过以下方式自定义：

```cpp
// 方式一：通配路由兜底 404
CROW_CATCHALL_ROUTE(app)([](const crow::request& req) {
    crow::json::wvalue err;
    err["error"] = "not found";
    err["path"] = req.url;
    return crow::response(404, err);
});
```

### 15.2 捕获异常

Crow 默认会捕获 handler 中抛出的所有异常并返回 500：

```cpp
CROW_ROUTE(app, "/may-fail")([] {
    if (rand() % 2) throw std::runtime_error("random failure");
    return "ok";
});
```

### 15.3 自定义 404/500 响应

```cpp
// 为所有错误返回统一 JSON
app.error_handler([](const crow::request&, crow::response& res, const std::string& msg) {
    res.set_header("Content-Type", "application/json");
    crow::json::wvalue err;
    err["error"] = msg;
    err["code"] = (int)res.code;
    res.body = err.dump();
});
```

---

## 十六、日志系统

### 16.1 日志级别

```cpp
app.loglevel(crow::LogLevel::Debug);    // Debug, Info, Warning, Error, Critical
```

### 16.2 日志宏

```cpp
CROW_LOG_DEBUG   << "debug info";
CROW_LOG_INFO    << "server started";
CROW_LOG_WARNING << "high memory usage";
CROW_LOG_ERROR   << "connection failed";
CROW_LOG_CRITICAL<< "fatal error";
```

### 16.3 自定义日志处理器

```cpp
crow::logger::setHandler([](const std::string& msg, crow::LogLevel level) {
    // 写入文件、发送日志服务等
    std::ofstream log("app.log", std::ios::app);
    log << "[" << (int)level << "] " << msg;
});
```

---

## 十七、应用配置

### 17.1 配置链

```cpp
app.port(8080)              // 监听端口（默认 80）
   .concurrency(4)          // 工作线程数（默认 1，多线程需显式设置）
   .server_name("MyAPI/1.0")
   .loglevel(crow::LogLevel::Info)
   .signal_clear();         // 清除默认信号处理
```

### 17.2 多线程说明

```cpp
app.multithreaded();   // 使用 std::thread::hardware_concurrency() 个线程
app.concurrency(8);    // 指定 8 个线程
// 默认单线程！不调用这两个就是单线程
```

**重要：** 单线程模式下所有 handler 串行执行；多线程下共享数据必须加锁。

### 17.3 优雅关闭

```cpp
#include <csignal>

crow::SimpleApp app;
std::atomic<bool> running{true};

std::signal(SIGINT, [](int) {
    CROW_LOG_INFO << "shutting down...";
    app.stop();  // 停止服务器
});
```

---

## 十八、Blueprints（路由分组）

Blueprints 用于把路由按模块组织（类似 Flask 的 Blueprint）：

```cpp
crow::Blueprint api_bp("api", "v1");  // URL 前缀 /api/v1

CROW_BP_ROUTE(api_bp, "/users")([] {
    return "user list";  // 实际路径: /api/v1/users
});

CROW_BP_ROUTE(api_bp, "/users/<int>")([](int id) {
    return "user " + std::to_string(id);
});

int main() {
    crow::SimpleApp app;
    app.register_blueprint(api_bp);   // 注册 Blueprint
    app.port(8080).run();
}
```

Blueprint 还可以有自己的模板目录和静态目录。

---

## 十九、常见问题与调试

### 19.1 编译问题

| 问题 | 解决方案 |
|------|----------|
| `undefined reference to pthread` | 添加 `-pthread` 编译选项 |
| asio 相关报错 | 使用 `crow_all.h`（内嵌 asio），或安装 Boost |
| Windows 链接错误 | MinGW 加 `-lws2_32 -lmswsock` |
| 模板渲染找不到文件 | 检查工作目录，`templates/` 必须在运行目录下 |

### 19.2 运行时问题

**问题：多线程下数据竞争崩溃**

```cpp
// 错误：多 handler 共享计数器
static int counter = 0;

// 正确：使用原子变量或互斥锁
static std::atomic<int> counter{0};
```

**问题：handler 中 `response&` 忘记 `end()`**

```cpp
// 错误：handler 永远不返回
CROW_ROUTE(app, "/bad")([](crow::response& res) {
    res.body = "hi";
});

// 正确：
CROW_ROUTE(app, "/good")([](crow::response& res) {
    res.body = "hi";
    res.end();   // 必须调用！
});
```

**问题：返回局部变量引用**

```cpp
// 错误：返回悬垂引用
CROW_ROUTE(app, "/bad")([]() -> const std::string& {
    std::string s = "hello";
    return s;  // UB！
});

// 正确：按值返回
CROW_ROUTE(app, "/good")([] {
    return std::string("hello");
});
```

### 19.3 调试技巧

```cpp
// 打印原始请求
CROW_ROUTE(app, "/debug")([](const crow::request& req) {
    CROW_LOG_INFO << "method=" << crow::method_name(req.method)
                  << " url=" << req.raw_url
                  << " body=" << req.body;
    return "";
});
```

---

## 二十、完整实战项目：RESTful 用户 API

一个包含路由、JSON、中间件、错误处理、CRUD 的完整示例：

```cpp
#include "crow.h"
#include <unordered_map>
#include <mutex>
#include <atomic>

// ---------- 数据层 ----------
struct User {
    int64_t id;
    std::string name;
    std::string email;
};

std::unordered_map<int64_t, User> users_db;
std::mutex db_mutex;
std::atomic<int64_t> next_id{1};

// ---------- 中间件 ----------
struct ApiKeyAuth {
    struct context {};
    void before_handle(crow::request& req, crow::response& res, context&) {
        if (req.url != "/health") {  // 健康检查不需要认证
            if (req.get_header_value("X-API-Key") != "secret-key-123") {
                res.code = 401;
                res.body = R"({"error": "invalid API key"})";
                res.end();
            }
        }
    }
    void after_handle(crow::request&, crow::response&, context&) {}
};

// ---------- 主程序 ----------
int main()
{
    crow::App<ApiKeyAuth> app;

    // 统一错误格式
    app.error_handler([](const crow::request&, crow::response& res, const std::string& msg){
        crow::json::wvalue err;
        err["error"] = msg;
        err["status"] = (int)res.code;
        res.body = err.dump();
    });

    // 健康检查
    CROW_ROUTE(app, "/health")([] {
        return crow::json::wvalue{{"status", "ok"}};
    });

    // 创建用户
    CROW_ROUTE(app, "/api/users").methods(crow::HTTPMethod::POST)
    ([](const crow::request& req) {
        auto body = crow::json::load(req.body);
        if (!body || !body.has("name") || !body.has("email")) {
            return crow::response(400, R"({"error": "name and email required"})");
        }

        User u{next_id++, body["name"].s(), body["email"].s()};
        {
            std::lock_guard<std::mutex> lock(db_mutex);
            users_db[u.id] = u;
        }

        crow::json::wvalue res;
        res["id"] = u.id;
        res["name"] = u.name;
        res["email"] = u.email;
        return crow::response(201, res);
    });

    // 用户列表
    CROW_ROUTE(app, "/api/users")
    ([](const crow::request& req) {
        std::lock_guard<std::mutex> lock(db_mutex);

        crow::json::wvalue::list list;
        for (const auto& [id, u] : users_db) {
            crow::json::wvalue item;
            item["id"] = u.id;
            item["name"] = u.name;
            item["email"] = u.email;
            list.push_back(std::move(item));
        }

        crow::json::wvalue res;
        res["users"] = std::move(list);
        res["count"] = (int64_t)users_db.size();
        return crow::response(res);
    });

    // 获取单个用户
    CROW_ROUTE(app, "/api/users/<int>")
    ([](int64_t id) {
        std::lock_guard<std::mutex> lock(db_mutex);
        auto it = users_db.find(id);
        if (it == users_db.end()) {
            return crow::response(404, R"({"error": "user not found"})");
        }
        crow::json::wvalue res;
        res["id"] = it->second.id;
        res["name"] = it->second.name;
        res["email"] = it->second.email;
        return crow::response(res);
    });

    // 更新用户
    CROW_ROUTE(app, "/api/users/<int>").methods(crow::HTTPMethod::PUT)
    ([](const crow::request& req, int64_t id) {
        auto body = crow::json::load(req.body);
        if (!body) return crow::response(400, R"({"error": "invalid JSON"})");

        std::lock_guard<std::mutex> lock(db_mutex);
        auto it = users_db.find(id);
        if (it == users_db.end()) {
            return crow::response(404, R"({"error": "user not found"})");
        }
        if (body.has("name"))  it->second.name = body["name"].s();
        if (body.has("email")) it->second.email = body["email"].s();

        crow::json::wvalue res;
        res["id"] = it->second.id;
        res["name"] = it->second.name;
        res["email"] = it->second.email;
        return crow::response(res);
    });

    // 删除用户
    CROW_ROUTE(app, "/api/users/<int>").methods(crow::HTTPMethod::DELETE)
    ([](int64_t id) {
        std::lock_guard<std::mutex> lock(db_mutex);
        if (!users_db.erase(id)) {
            return crow::response(404, R"({"error": "user not found"})");
        }
        return crow::response(204);
    });

    // 404 兜底
    CROW_CATCHALL_ROUTE(app)([] {
        return crow::response(404, R"({"error": "route not found"})");
    });

    app.port(8080).multithreaded().run();
}
```

**测试：**

```bash
# 编译
g++ -std=c++17 -O2 -pthread server.cpp -o server

# 运行
./server

# 测试（需要 X-API-Key 头）
curl -X POST http://localhost:8080/api/users \
  -H "Content-Type: application/json" \
  -H "X-API-Key: secret-key-123" \
  -d '{"name": "Alice", "email": "alice@example.com"}'

curl http://localhost:8080/api/users -H "X-API-Key: secret-key-123"
curl http://localhost:8080/api/users/1 -H "X-API-Key: secret-key-123"
```

---

## 二十一、API 速查表

### 路由

```cpp
CROW_ROUTE(app, "/path/<int>/<string>")(...)          // 基本路由
CROW_ROUTE(app, "/x").methods(crow::HTTPMethod::POST) // HTTP 方法
CROW_CATCHALL_ROUTE(app)(...)                         // 兜底路由
CROW_BP_ROUTE(bp, "/x")(...)                          // Blueprint 路由
```

### 请求

```cpp
req.url_params.get("key")              // 查询参数
req.get_header_value("X-Custom")       // 请求头
req.body                               // 请求体
req.method                             // 方法
req.remote_ip                          // 客户端 IP
req.get_file_params()                  // 上传文件
```

### 响应

```cpp
crow::response(200, "body")            // 构造响应
res.code = 404                         // 状态码
res.set_header("K", "V")               // 设置头
res.end()                              // 结束响应
return crow::json::wvalue{{"k","v"}};  // 直接返回 JSON
```

### JSON

```cpp
crow::json::load(str)                  // 解析
x["key"] = value                       // 写入
body["key"].s()/.i()/.d()/.b()         // 按类型读取
x.dump()                               // 序列化
crow::json::wvalue::list({...})        // JSON 数组
```

### 模板

```cpp
crow::mustache::load("page.html")      // 加载模板
page.render(ctx)                       // 渲染
ctx["key"] = value                     // 设置上下文
```

### 应用配置

```cpp
app.port(8080)                         // 端口
app.multithreaded()                    // 多线程（全核心）
app.concurrency(N)                     // 指定线程数
app.loglevel(crow::LogLevel::Info)     // 日志级别
app.stop()                             // 停止服务器
```

### 日志

```cpp
CROW_LOG_INFO << "message";            // 信息日志
CROW_LOG_ERROR << "error";             // 错误日志
```

---

## 附录：参考资源

- **官方文档**: https://crowcpp.org
- **GitHub**: https://github.com/CrowCpp/Crow
- **GitHub Releases（单头文件下载）**: https://github.com/CrowCpp/Crow/releases

---

> **提示**：本文档基于 Crow v1.2.x 编写。新版本可能有 API 变化，请以官方文档为准。
