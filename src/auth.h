#pragma once

#include <string>

#include "crow.h"

// 会话信息（内存会话，服务重启后需重新登录）
struct Session
{
    int adminId = 0;
    bool isMain = false;
};

// 会话 Cookie 名
extern const std::string SESSION_COOKIE;

// 生成会话 token 并写入会话表，返回 token（用于设置 Set-Cookie）
std::string createSession(int adminId, bool isMain);

// 销毁指定 token 的会话
void destroySession(const std::string& token);

// 从 Cookie 请求头中解析指定名称的值
std::string getCookie(const crow::request& req, const std::string& name);

// 判断请求是否已登录
bool isLoggedIn(const crow::request& req);

// 判断请求是否为已登录的主管理员
bool isMainAdmin(const crow::request& req);

// 读取当前会话（未登录返回 false）
bool getSession(const crow::request& req, Session& out);

// 未登录时返回的 401 响应
crow::response unauthorizedResponse();

// 非主管理员访问时的 403 响应
crow::response forbiddenResponse();
