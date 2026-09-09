#include "crow.h"
#include <mysql/mysql.h>
#include <string>
#include <vector>
#include <mutex>
#include <fstream>
#include <sstream>
#include <iostream>
#include <cstring>


// DataBase 类：封装所有 MySQL 操作
// 使用 RALL 管理连接，使用 mutex 保证线程安全


class DataBase
{
	MYSQL* conn_ = nullptr; // MySQL 连接句柄
	std::mutex mtx_;  // 互斥锁，保证多线程访问
	std::string host_, user_, pass_, db_;
	unsigned int port_;

public:
	// 构造函数 - 建立连接并初始化表
	DataBase(const std::string& host, const std::string& user, const std::string& pass,
					const std::string db, unsigned int port = 3306) : host_(host), user_(user), pass_(pass), db_(db), port_(port)
	{
		connect(); // 建立连接
		initTable(); // 创建表（如果表不存在）
	}

	// 析构函数 - 释放连接
	~DataBase()
	{
		if (conn_) 
		{
			mysql_close(conn_);
		}
	}

	// 建立 MySQL 连接
	void connect()
	{
		conn_ = mysql_init(nullptr);

		if (!conn_)
		{
			throw std::runtime_error("mysql_init 失败!");
		}

		// 设置字符集为 utf8mb4，支持中文和emoji
		mysql_options(conn_, MYSQL_SET_CHARSET_NAME, "utf8mb4");

		// 建立连接
		if (!mysql_real_connect(conn_, host_.c_str(), user_.c_str(), pass_.c_str(), db_.c_str(), port_, nullptr, 0))
		{
			std::string err = "MySQL 连接失败!";
			err += mysql_error(conn_);
			mysql_close(conn_);
			conn_ = nullptr;
			throw std::runtime_error(err);
		}

		std::cout << "[DB]已连接到 Mysql: " << host_ << ":" << port_ << std::endl;
	}

	// 检查连接是否存活，如果断开则重连
    void checkConnection() {
        if (mysql_ping(conn_) != 0) {
            std::cerr << "[DB] 连接断开，正在重连..." << std::endl;
            mysql_close(conn_);
            connect();
        }
    }

	// 初始化数据表
	void initTable()
	{
		const char* sql = R"(
			CREATE TABLE IF NOT EXISTS tasks(
				id INT AUTO_INCREMENT PRIMARY KEY,
				title VARCHAR(255) NOT NULL COMMENT '任务标题',
				description TEXT COMMENT '任务描述',
				priority INT DEFAULT 2 COMMENT '1=高 2=中 3=低',
				completed TINYINT DEFAULT 0 COMMENT '0=未完成 1=已完成',
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
		)";

		if (mysql_query(conn_, sql) != 0)
		{
			throw std::runtime_error(std::string("创建表失败：") + mysql_error(conn_));
		}
	}


	// 获取所有任务
	crow::json::wvalue getAllTask()
	{
		std::lock_guard<std::mutex> lock(mtx_);
		checkConnection();

		crow::json::wvalue result;
		std::vector<crow::json::wvalue> tasks;

		const char* sql = R"(
			SELECT id, title, description, priority, completed, created_at 
			FROM tasks 
			ORDERED BY id DESC
		)";

		if (mysql_query(conn_, sql) != 0)
		{
			result["success"] = false;
			result["message"] = mysql_error(conn_);
			return result;
		}

		// 获取查询结果
		MYSQL_RES* res = mysql_store_result(conn_);
		if (res)
		{
			MYSQL_ROW row;
			while ((row = mysql_fetch_row(res)))
			{
				crow::json::wvalue task;
				task["id"] = std::stoi(row[0]);
				task["title"] = row[1] ? row[1] : "";
				task["description"] = row[2] ? row[2] : "";
				task["priority"] = std::stoi(row[3]);
				task["completed"] = (std::stoi(row[4]) == 1);
				task["created_at"] = row[5] ? row[5] : "";
				tasks.push_back(std::move(task));
			}
			mysql_free_result(res);
		}

		result["tasks"] = std::move(tasks);
		result["success"] = true;
		return result;
	}
	
	// 添加任务（使用预处理语句防止 SQL 注入攻击）
	crow::json::wvalue addTask(const std::string& title, const std::string& desc, int priority)
	{
		std::lock_guard<std::mutex> lock(mtx_);
		checkConnection();

		crow::json::wvalue result;

		// 1. 初始化预处理语句
		MYSQL_STMT* stmt = mysql_stmt_init(conn_);
		if (!stmt)
		{
			result["success"] = false;
			result["message"] = "mysql_stmt_init 失败";
			return result;
		}

		// 2. SQL 模板  ? - 占位符
		const char* sql = "INSERT INTO tasks (title, description, priority) VALUES (?, ?, ?)";
		if (mysql_stmt_prepare(stmt, sql, std::strlen(sql)) != 0)
		{
			result["success"] = false;
			result["message"] = mysql_stmt_error(stmt);
			mysql_stmt_close(stmt);
			return result;
		}

		// 3. 绑定参数
		MYSQL_BIND bind[3];
		std::memset(bind, 0, sizeof(bind));

		// 参数 1 - title 字符串
		bind[0].buffer_type = MYSQL_TYPE_STRING;
		bind[0].buffer = (void*)title.c_str();
		bind[0].buffer_length = title.length();

		// 参数 2 - decription 字符串
		bind[1].buffer_type = MYSQL_TYPE_STRING;
		bind[1].buffer = (void*)desc.c_str();
		bind[1].buffer_length = title.length();

		// 参数 3 - priority
		bind[2].buffer_type = MYSQL_TYPE_LONG;
		bind[2].buffer = (void*)&priority;
		bind[2].is_unsigned = 0;

		mysql_stmt_bind_param(stmt, bind);

		// 4. 执行
		if (mysql_stmt_execute(stmt) == 0)
		{
			int newID = static_cast<int>(mysql_stmt_insert_id(stmt));
			result["success"] = true;
			result["id"] = newID;
			result["message"] = "任务创建成功";
		} 
		else
		{
			result["success"] = false;
			result["message"] = mysql_stmt_error(stmt);
		}
		mysql_stmt_close(stmt);
		return result;
	}

	// 更新任务
	crow::json::wvalue updateTask(int id, const std::string& title, const std::string& desc,
								int priority, bool completed)
	{
		std::lock_guard<std::mutex> lock(mtx_);
		checkConnection();

		crow::json::wvalue result;
		MYSQL_STMT* stmt = mysql_stmt_init(conn_);
		if (!stmt)
		{
			result["success"] = false;
			result["messgae"] = "mysql_stmt_init 失败";
			return result;
		}

		const char* sql = "UPDATE tasks SET title=?, description=?, priority=?, completed=? WHERE id=?";
		if (mysql_stmt_prepare(stmt, sql, std::strlen(sql)) != 0)
		{
			result["success"] = false;
			result["messgae"] = mysql_stmt_error(stmt);
			mysql_stmt_close(stmt);
			return result;
		}

		int completed_int = completed ? 1 : 0;
		MYSQL_BIND bind[5];
		std::memset(bind, 0, sizeof(bind));

		bind[0].buffer_type = MYSQL_TYPE_STRING;
		bind[0].buffer = (void*)title.c_str();
		bind[0].buffer_length = title.length();

		bind[1].buffer_type = MYSQL_TYPE_STRING;
		bind[1].buffer = (void*)desc.c_str();
		bind[1].buffer_length = desc.length();

		bind[2].buffer_type = MYSQL_TYPE_LONG;
		bind[2].buffer = (void*)&priority;
		
		bind[3].buffer_type = MYSQL_TYPE_LONG;
		bind[3].buffer = (void*)&completed_int;

		bind[4].buffer_type = MYSQL_TYPE_LONG;
		bind[4].buffer = (void*)&id;

		mysql_stmt_bind_param(stmt, bind);
		if (mysql_stmt_execute(stmt) != 0)
		{
			result["success"] = false;
			result["messgae"] = mysql_stmt_error(stmt);
		}
		else
		{
			my_ulonglong affected = mysql_stmt_affected_rows(stmt);
			result["success"] = (affected > 0);
			result["message"] = (affected > 0) ? "更新成功" : "更新失败";
		}

		mysql_stmt_close(stmt);
		return stmt;
	}

	// 删除任务
	crow::json::wvalue deleteTask(int id)
	{
		std::lock_guard<std::mutex> lock(mtx_);
		checkConnection();

		crow::json::wvalue result;
		MYSQL_STMT* stmt = mysql_stmt_init(conn_);
		if (!stmt)
		{
			result["success"] = false;
			result["message"] = "mysql_stmt_init 失败";
			return result;
		}

		const char* sql = "DELETE FROM tasks WHRER id=?";
		if (mysql_stmt_prepare(stmt, sql, std::strlen(sql)) != 0)
		{
			result["success"] = false;
			result["message"] = mysql_stmt_error(stmt);
			mysql_stmt_close(stmt);
			return result;
		}
		
		MYSQL_BIND bind[1];
		std::memset(bind, 0, sizeof(bind));

		bind[0].buffer_type = MYSQL_TYPE_LONG;
		bind[0].buffer = (void*)&id;

		mysql_stmt_bind_param(stmt, bind);

		if (mysql_stmt_execute(stmt) == 0)
		{
			my_ulonglong affected = mysql_stmt_affected_rows(stmt);
			result["success"] = (affected > 0);
			result["message"] = (affected > 0) ? "删除成功" : "任务不存在";
		}
		else
		{
			result["success"] = false;
			result["message"] = mysql_stmt_error(stmt);
		}
		mysql_stmt_close(stmt);
		return result;
	}

	// 切换完成状态（先查后改，避免使用 NOT 运算符）
	crow::json::wvalue toggleTask(int id)
	{
		std::lock_guard<std::mutex> lock(mtx_);
		checkConnection();

		crow::json::wvalue result;
		// 先查询当前状态
		std::string query = "SELECT completed FROM tasks WHERE id=" + std::to_string(id);
		if (mysql_query(conn_, query.c_str()) != 0)
		{
			result["success"] = false;
			result["message"] = mysql_error(conn_);
			return result;
		}
		
		MYSQL_RES* res = mysql_store_result(conn_);
		if (!res || mysql_num_rows(res) == 0)
		{
			if (res)
			{
				mysql_free_result(res);
			}
			result["success"] = false;
			result["messgae"] = "任务不存在";
			return result;
		}

		MYSQL_ROW row = mysql_fetch_row(res);
		int current = std::stoi(row[0]);
		mysql_free_result(res);

		// 取反
		int newstatus = (current == 1) ? 0 : 1;
		std::string update = "UPDATE tasks SET completed=" + std::to_string(newstatus) + "WHERE id=" + std::to_string(id);

		if (mysql_query(conn_, update.c_str()) != 0)
		{
			result["success"] = false;
			result["message"] = mysql_error(conn_);
		} 
		else
		{
			result["success"] = true;
			result["message"] = "状态切换成功";
		}
		return result;
	}
};


// 读取静态文件
std::string readFile(const std::string& path)
{
	std::ifstream file(path, std::ios::binary);
	if (!file.is_open())
	{
		return "";
	}
	std::stringstream buffer;
	buffer << file.rdbuf();
	return buffer.str();
}


// 辅助函数：给 response 添加 CORS 头（旧版 Crow 没有中间件）
void addCorsHeaders(crow::response& res) {
    res.add_header("Access-Control-Allow-Origin", "*");
    res.add_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
    res.add_header("Access-Control-Allow-Headers", "Content-Type");
}



int main()
{

	try
	{
		// 数据库配置
		// 生产环境使用配置文件或环境变量传入
		DataBase db("localhost", "root", "123456", "taskdb", 3306);

		crow::SimpleApp app;

		// // CORS 中间件，允许浏览器跨域访问
		// app.use([](crow::request& req, crow::response& res, crow::context& ctx){
		// 	res.add_header("Access-Control-Allow-Origin", "*");
		// 	res.add_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
		// 	res.add_header("Access-Control-Allow-Headers", "Content-Type");
		// });


		// 处理浏览器的 OPTIONS 预检请求
		CROW_ROUTE(app, "/api/<path>").methods("OPTIONS"_method)([](const crow::request& req, std::string path){
			crow::response res(200);
			addCorsHeaders(res);
			return res;
		});

		// REST API 路由

		// GET /api/tasks - 获取所有任务
		CROW_ROUTE(app, "/api/tasks").methods("GET"_method)([&db](){
			crow::response res(db.getAllTask());
            addCorsHeaders(res);
			return res;
		});

		// POST /api/tasks - 创建任务
		CROW_ROUTE(app, "/api/tasks").methods("POST"_method)([&db](const crow::request& req){
			auto body = crow::json::load(req.body);
			if (!body)
			{
				crow::json::wvalue err;
				err["success"] = false;
				err["message"] = "无效的 JSON 数据";
				return crow::response(400, err);
			}

			std::string title = body["title"].s();
			std::string desc = body.has("description") ? std::string(body["description"].s()) : std::string("");
			int priority = body.has("priority") ? body["priority"].i() : 2;
			crow::response res(db.addTask(title, desc, priority));
			addCorsHeaders(res);
			return res;
		});


		// PUT /api/tasks/<id> 更新任务
		CROW_ROUTE(app, "/api/tasks/<int>").methods("PUT"_method)([&db](const crow::request& req, int id){
			auto body = crow::json::load(req.body);
			if (!body)
			{
				crow::json::wvalue err;
				err["success"] = false;
				err["message"] = "无效的 JSON 信息";
				return crow::response(400, err);
			}

			std::string title = body["title"].s();
			std::string desc = body.has("description") ? std::string(body["description"].s()) : std::string("");
			int priority = body.has("priority") ? body["priority"].i() : 2;
			bool completed = body.has("completed") ? body["completed"].b() : false;

			crow::response res(db.updateTask(id, title, desc, priority, completed));
            addCorsHeaders(res);
            return res;
		});

		// DELETE /api/tasks/<id> 删除任务
		CROW_ROUTE(app, "/api/tasks/<int>").methods("DELETE"_method)([&db](int id){
			crow::response res(db.deleteTask(id));
            addCorsHeaders(res);
            return res;
		});

		// POST /api/tasks/<id>/toggle  - 切换完成状态
		CROW_ROUTE(app, "/api/tasks/<int>/toggle").methods("POST"_method)([&db](int id){
			crow::response res(db.toggleTask(id));
            addCorsHeaders(res);
            return res;
		});


		// 静态文件服务

		// 根路径返回首页
		CROW_ROUTE(app, "/")([](){
			auto content = readFile("static/index.html");
			crow::response res(content);
			res.add_header("Content-Type", "text/html; charset=utf8mb4");
			return res;
		});

		// CSS 文件
		CROW_ROUTE(app, "/css/<string>")([](std::string filename){
			auto content = readFile("static/css/" + filename);
			crow::response res(content);
			res.add_header("Content-Type", "text/css; charset=utf8mb4");
			return res;
		});

		// JS 文件
		CROW_ROUTE(app, "/js/<string>")([](std::string filename){
			auto content = readFile("static/js/" + filename);
			crow::response res(content);
			res.add_header("Content-Type", "application/javascript; charset=utf8mb4");
			return res;
		});


		// ========== 启动服务 ==========
        std::cout << "========================================" << std::endl;
        std::cout << "  🚀 任务管理系统已启动!" << std::endl;
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
