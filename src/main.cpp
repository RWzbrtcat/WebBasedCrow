#include <exception>
#include <iostream>
#include <string>

#include "database.h"
#include "routes.h"
#include "utils.h"

int main()
{
    try
    {
        // 数据库配置
        // 生产环境使用配置文件或环境变量传入
        DataBase db("localhost", "root", "123456", "blogdb", 3306);

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
