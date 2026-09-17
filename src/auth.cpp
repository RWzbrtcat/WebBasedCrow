#include "auth.h"

#include <mutex>
#include <random>
#include <sstream>
#include <unordered_map>

#include "utils.h"

const std::string SESSION_COOKIE = "blog_session";

// 内存会话表（token -> 会话信息）。个人博客用内存会话即可，服务重启后需重新登录
static std::unordered_map<std::string, Session> g_sessions;
static std::mutex g_sessionsMtx;

// 生成随机会话 token（十六进制）
static std::string generateToken()
{
    static thread_local std::mt19937_64 rng(std::random_device{}());
    std::uniform_int_distribution<unsigned long long> dist;
    std::ostringstream oss;
    oss << std::hex << dist(rng) << dist(rng);
    return oss.str();
}

// 生成会话 token 并写入会话表，返回 token
std::string createSession(int adminId, bool isMain)
{
    std::string token = generateToken();
    Session s;
    s.adminId = adminId;
    s.isMain = isMain;
    {
        std::lock_guard<std::mutex> lock(g_sessionsMtx);
        g_sessions[token] = s;
    }
    return token;
}

// 销毁指定 token 的会话
void destroySession(const std::string& token)
{
    std::lock_guard<std::mutex> lock(g_sessionsMtx);
    g_sessions.erase(token);
}

// 从 Cookie 请求头中解析指定名称的值
std::string getCookie(const crow::request& req, const std::string& name)
{
    const std::string& cookie = req.get_header_value("Cookie");
    if (cookie.empty()) return "";
    const std::string key = name + "=";
    size_t pos = 0;
    while ((pos = cookie.find(key, pos)) != std::string::npos)
    {
        bool boundaryOk = (pos == 0 || cookie[pos - 1] == ';' || cookie[pos - 1] == ' ');
        if (boundaryOk)
        {
            pos += key.size();
            size_t end = cookie.find(';', pos);
            if (end == std::string::npos) end = cookie.size();
            return cookie.substr(pos, end - pos);
        }
        pos += key.size();
    }
    return "";
}

// 判断请求是否已登录
bool isLoggedIn(const crow::request& req)
{
    std::string token = getCookie(req, SESSION_COOKIE);
    if (token.empty()) return false;
    std::lock_guard<std::mutex> lock(g_sessionsMtx);
    return g_sessions.count(token) > 0;
}

// 判断请求是否为已登录的主管理员
bool isMainAdmin(const crow::request& req)
{
    std::string token = getCookie(req, SESSION_COOKIE);
    if (token.empty()) return false;
    std::lock_guard<std::mutex> lock(g_sessionsMtx);
    auto it = g_sessions.find(token);
    return it != g_sessions.end() && it->second.isMain;
}

// 读取当前会话（未登录返回 false），供需要管理员身份的接口使用
bool getSession(const crow::request& req, Session& out)
{
    std::string token = getCookie(req, SESSION_COOKIE);
    if (token.empty()) return false;
    std::lock_guard<std::mutex> lock(g_sessionsMtx);
    auto it = g_sessions.find(token);
    if (it == g_sessions.end()) return false;
    out = it->second;
    return true;
}

// 未登录时返回的 401 响应
crow::response unauthorizedResponse()
{
    crow::json::wvalue err;
    err["success"] = false;
    err["message"] = "未登录";
    crow::response res(401, err);
    addCorsHeaders(res);
    return res;
}

// 非主管理员访问时的 403 响应
crow::response forbiddenResponse()
{
    crow::json::wvalue err;
    err["success"] = false;
    err["message"] = "仅主管理员可执行此操作";
    crow::response res(403, err);
    addCorsHeaders(res);
    return res;
}
