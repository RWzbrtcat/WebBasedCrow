#include <cstdlib>
#include <exception>
#include <iostream>
#include <string>

#include "database.h"
#include "routes.h"
#include "utils.h"

namespace
{
std::string envStr(const char* name, const std::string& def)
{
    const char* v = std::getenv(name);
    return (v && *v) ? std::string(v) : def;
}

unsigned int envUInt(const char* name, unsigned int def)
{
    const char* v = std::getenv(name);
    if (!v || !*v) return def;
    return static_cast<unsigned int>(std::strtoul(v, nullptr, 10));
}
} // namespace

int main()
{
    try
    {
        // 数据库连接配置：通过环境变量传入，源码中不出现真实密码
        std::string dbHost = envStr("MYSQL_HOST", "localhost");
        std::string dbUser = envStr("MYSQL_USER", "root");
        std::string dbPass = envStr("MYSQL_PASSWORD", "");
        std::string dbName = envStr("MYSQL_DB", "blogdb");
        unsigned int dbPort = envUInt("MYSQL_PORT", 3306);

        DataBase db(dbHost, dbUser, dbPass, dbName, dbPort);

        crow::SimpleApp app;

        std::string staticDir = getStaticDir();
        std::cout << "[Static] 静态文件目录: " << staticDir << std::endl;

        setupRoutes(app, db, staticDir);

        // ========== 启动服务 ==========
        std::cout << "========================================" << std::endl;
        std::cout << "  🚀 博客系统已启动!" << std::endl;
        std::cout << "  📍 访问地址: http://localhost:8080" << std::endl;
        std::cout << "  🛑 按 Ctrl+C 停止服务" << std::endl;
        std::cout << "========================================" << std::endl;

        app.port(8080).multithreaded().run();
    }
    catch (const std::exception& e)
    {
        std::cerr << "致命错误: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
