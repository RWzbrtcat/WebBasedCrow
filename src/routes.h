#pragma once

#include <string>

#include "crow.h"

#include "database.h"

// 注册所有 HTTP 路由（API + 静态页面）
void setupRoutes(crow::SimpleApp& app, DataBase& db, const std::string& staticDir);
