#include "crow.h"
#include <mysql/mysql.h>
#include <string>
#include <vector>
#include <mutex>
#include <fstream>
#include <sstream>
#include <iostream>
#include <cstring>
#include <unistd.h>
#include <limits.h>


// DataBase 类：封装所有 MySQL 操作
// 使用 RAII 管理连接，使用 mutex 保证线程安全
class DataBase
{
	MYSQL* conn_ = nullptr; // MySQL 连接句柄
	std::mutex mtx_;        // 互斥锁，保证多线程访问
	std::string host_, user_, pass_, db_;
	unsigned int port_;

public:
	// 构造函数 - 建立连接并初始化表
	DataBase(const std::string& host, const std::string& user, const std::string& pass,
			 const std::string db, unsigned int port = 3306)
		: host_(host), user_(user), pass_(pass), db_(db), port_(port)
	{
		connect();   // 建立连接
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

		// 设置字符集为 utf8mb4，支持中文和 emoji
		mysql_options(conn_, MYSQL_SET_CHARSET_NAME, "utf8mb4");

		// 建立连接
		if (!mysql_real_connect(conn_, host_.c_str(), user_.c_str(), pass_.c_str(), db_.c_str(), port_, nullptr, 0))
		{
			std::string err = "MySQL 连接失败! ";
			err += mysql_error(conn_);
			mysql_close(conn_);
			conn_ = nullptr;
			throw std::runtime_error(err);
		}

		std::cout << "[DB] 已连接到 Mysql: " << host_ << ":" << port_ << std::endl;
	}

	// 检查连接是否存活，如果断开则重连
	void checkConnection()
	{
		if (mysql_ping(conn_) != 0)
		{
			std::cerr << "[DB] 连接断开，正在重连..." << std::endl;
			mysql_close(conn_);
			connect();
		}
	}

	// 初始化数据表
	void initTable()
	{
		const char* sql = R"(
			CREATE TABLE IF NOT EXISTS posts(
				id INT AUTO_INCREMENT PRIMARY KEY,
				title VARCHAR(255) NOT NULL COMMENT '文章标题',
				content TEXT COMMENT '文章正文',
				author VARCHAR(100) DEFAULT '匿名' COMMENT '作者',
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
				updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
			)ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
		)";

		if (mysql_query(conn_, sql) != 0)
		{
			throw std::runtime_error(std::string("创建表失败：") + mysql_error(conn_));
		}
	}

	// 获取所有文章
	crow::json::wvalue getAllPosts()
	{
		std::lock_guard<std::mutex> lock(mtx_);
		checkConnection();

		crow::json::wvalue result;
		std::vector<crow::json::wvalue> posts;

		const char* sql = R"(
			SELECT id, title, content, author, created_at, updated_at
			FROM posts
			ORDER BY id DESC
		)";

		if (mysql_query(conn_, sql) != 0)
		{
			result["success"] = false;
			result["message"] = mysql_error(conn_);
			return result;
		}

		MYSQL_RES* res = mysql_store_result(conn_);
		if (res)
		{
			MYSQL_ROW row;
			while ((row = mysql_fetch_row(res)))
			{
				crow::json::wvalue post;
				post["id"] = std::stoi(row[0]);
				post["title"] = row[1] ? row[1] : "";
				post["content"] = row[2] ? row[2] : "";
				post["author"] = row[3] ? row[3] : "";
				post["created_at"] = row[4] ? row[4] : "";
				post["updated_at"] = row[5] ? row[5] : "";
				posts.push_back(std::move(post));
			}
			mysql_free_result(res);
		}

		result["posts"] = std::move(posts);
		result["success"] = true;
		return result;
	}

	// 获取单篇文章
	crow::json::wvalue getPostById(int id)
	{
		std::lock_guard<std::mutex> lock(mtx_);
		checkConnection();

		crow::json::wvalue result;
		std::string sql = "SELECT id, title, content, author, created_at, updated_at FROM posts WHERE id=" + std::to_string(id);

		if (mysql_query(conn_, sql.c_str()) != 0)
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
			result["message"] = "文章不存在";
			return result;
		}

		MYSQL_ROW row = mysql_fetch_row(res);
		crow::json::wvalue post;
		post["id"] = std::stoi(row[0]);
		post["title"] = row[1] ? row[1] : "";
		post["content"] = row[2] ? row[2] : "";
		post["author"] = row[3] ? row[3] : "";
		post["created_at"] = row[4] ? row[4] : "";
		post["updated_at"] = row[5] ? row[5] : "";
		mysql_free_result(res);

		result["post"] = std::move(post);
		result["success"] = true;
		return result;
	}

	// 发布文章（使用预处理语句防止 SQL 注入）
	crow::json::wvalue addPost(const std::string& title, const std::string& content, const std::string& author)
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

		const char* sql = "INSERT INTO posts (title, content, author) VALUES (?, ?, ?)";
		if (mysql_stmt_prepare(stmt, sql, std::strlen(sql)) != 0)
		{
			result["success"] = false;
			result["message"] = mysql_stmt_error(stmt);
			mysql_stmt_close(stmt);
			return result;
		}

		MYSQL_BIND bind[3];
		std::memset(bind, 0, sizeof(bind));

		bind[0].buffer_type = MYSQL_TYPE_STRING;
		bind[0].buffer = (void*)title.c_str();
		bind[0].buffer_length = title.length();

		bind[1].buffer_type = MYSQL_TYPE_STRING;
		bind[1].buffer = (void*)content.c_str();
		bind[1].buffer_length = content.length();

		bind[2].buffer_type = MYSQL_TYPE_STRING;
		bind[2].buffer = (void*)author.c_str();
		bind[2].buffer_length = author.length();

		mysql_stmt_bind_param(stmt, bind);

		if (mysql_stmt_execute(stmt) == 0)
		{
			int newID = static_cast<int>(mysql_stmt_insert_id(stmt));
			result["success"] = true;
			result["id"] = newID;
			result["message"] = "文章发布成功";
		}
		else
		{
			result["success"] = false;
			result["message"] = mysql_stmt_error(stmt);
		}
		mysql_stmt_close(stmt);
		return result;
	}

	// 更新文章
	crow::json::wvalue updatePost(int id, const std::string& title, const std::string& content, const std::string& author)
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

		const char* sql = "UPDATE posts SET title=?, content=?, author=? WHERE id=?";
		if (mysql_stmt_prepare(stmt, sql, std::strlen(sql)) != 0)
		{
			result["success"] = false;
			result["message"] = mysql_stmt_error(stmt);
			mysql_stmt_close(stmt);
			return result;
		}

		MYSQL_BIND bind[4];
		std::memset(bind, 0, sizeof(bind));

		bind[0].buffer_type = MYSQL_TYPE_STRING;
		bind[0].buffer = (void*)title.c_str();
		bind[0].buffer_length = title.length();

		bind[1].buffer_type = MYSQL_TYPE_STRING;
		bind[1].buffer = (void*)content.c_str();
		bind[1].buffer_length = content.length();

		bind[2].buffer_type = MYSQL_TYPE_STRING;
		bind[2].buffer = (void*)author.c_str();
		bind[2].buffer_length = author.length();

		bind[3].buffer_type = MYSQL_TYPE_LONG;
		bind[3].buffer = (void*)&id;

		mysql_stmt_bind_param(stmt, bind);

		if (mysql_stmt_execute(stmt) != 0)
		{
			result["success"] = false;
			result["message"] = mysql_stmt_error(stmt);
		}
		else
		{
			my_ulonglong affected = mysql_stmt_affected_rows(stmt);
			result["success"] = (affected > 0);
			result["message"] = (affected > 0) ? "更新成功" : "文章不存在";
		}
		mysql_stmt_close(stmt);
		return result;
	}

	// 删除文章
	crow::json::wvalue deletePost(int id)
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

		const char* sql = "DELETE FROM posts WHERE id=?";
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
			result["message"] = (affected > 0) ? "删除成功" : "文章不存在";
		}
		else
		{
			result["success"] = false;
			result["message"] = mysql_stmt_error(stmt);
		}
		mysql_stmt_close(stmt);
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

// 获取 static 目录的绝对路径（基于可执行文件位置，避免依赖启动目录）
std::string getStaticDir()
{
	char buf[PATH_MAX];
	ssize_t len = readlink("/proc/self/exe", buf, sizeof(buf) - 1);
	if (len == -1)
	{
		return "static";
	}
	buf[len] = '\0';
	std::string exe(buf);
	size_t pos = exe.find_last_of('/');
	std::string binDir = (pos == std::string::npos) ? "." : exe.substr(0, pos);
	// 可执行文件位于 <root>/bin/，static 目录位于 <root>/static
	return binDir + "/../static";
}


// 辅助函数：给 response 添加 CORS 头（旧版 Crow 没有中间件）
void addCorsHeaders(crow::response& res)
{
	res.add_header("Access-Control-Allow-Origin", "*");
	res.add_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
	res.add_header("Access-Control-Allow-Headers", "Content-Type");
}

// 返回一个 HTML 页面的响应
crow::response htmlResponse(const std::string& content)
{
	crow::response res(content);
	res.add_header("Content-Type", "text/html; charset=utf-8");
	return res;
}


int main()
{
	try
	{
		// 数据库配置
		// 生产环境使用配置文件或环境变量传入
		DataBase db("localhost", "root", "123456", "blogdb", 3306);

		crow::SimpleApp app;

		// 处理浏览器的 OPTIONS 预检请求
		CROW_ROUTE(app, "/api/<path>").methods("OPTIONS"_method)([](const crow::request& req, std::string path){
			crow::response res(200);
			addCorsHeaders(res);
			return res;
		});

		// ========== REST API 路由 ==========

		// GET /api/posts - 获取所有文章
		CROW_ROUTE(app, "/api/posts").methods("GET"_method)([&db](){
			crow::response res(db.getAllPosts());
			addCorsHeaders(res);
			return res;
		});

		// POST /api/posts - 发布文章
		CROW_ROUTE(app, "/api/posts").methods("POST"_method)([&db](const crow::request& req){
			auto body = crow::json::load(req.body);
			if (!body)
			{
				crow::json::wvalue err;
				err["success"] = false;
				err["message"] = "无效的 JSON 数据";
				return crow::response(400, err);
			}

			std::string title = body["title"].s();
			std::string content = body.has("content") ? std::string(body["content"].s()) : std::string("");
			std::string author = body.has("author") ? std::string(body["author"].s()) : std::string("匿名");
			crow::response res(db.addPost(title, content, author));
			addCorsHeaders(res);
			return res;
		});

		// GET /api/posts/<id> - 获取单篇文章
		CROW_ROUTE(app, "/api/posts/<int>").methods("GET"_method)([&db](int id){
			crow::response res(db.getPostById(id));
			addCorsHeaders(res);
			return res;
		});

		// PUT /api/posts/<id> - 更新文章
		CROW_ROUTE(app, "/api/posts/<int>").methods("PUT"_method)([&db](const crow::request& req, int id){
			auto body = crow::json::load(req.body);
			if (!body)
			{
				crow::json::wvalue err;
				err["success"] = false;
				err["message"] = "无效的 JSON 数据";
				return crow::response(400, err);
			}

			std::string title = body["title"].s();
			std::string content = body.has("content") ? std::string(body["content"].s()) : std::string("");
			std::string author = body.has("author") ? std::string(body["author"].s()) : std::string("匿名");
			crow::response res(db.updatePost(id, title, content, author));
			addCorsHeaders(res);
			return res;
		});

		// DELETE /api/posts/<id> - 删除文章
		CROW_ROUTE(app, "/api/posts/<int>").methods("DELETE"_method)([&db](int id){
			crow::response res(db.deletePost(id));
			addCorsHeaders(res);
			return res;
		});

		// ========== 静态文件服务 ==========

		std::string staticDir = getStaticDir();
		std::cout << "[Static] 静态文件目录: " << staticDir << std::endl;

		// 根路径返回首页（文章列表）
		CROW_ROUTE(app, "/")([staticDir](){
			return htmlResponse(readFile(staticDir + "/index.html"));
		});

		// 文章详情页
		CROW_ROUTE(app, "/post")([staticDir](){
			return htmlResponse(readFile(staticDir + "/post.html"));
		});

		// 编辑器页（新建 / 编辑）
		CROW_ROUTE(app, "/editor")([staticDir](){
			return htmlResponse(readFile(staticDir + "/editor.html"));
		});

		// CSS 文件
		CROW_ROUTE(app, "/css/<string>")([staticDir](std::string filename){
			auto content = readFile(staticDir + "/css/" + filename);
			crow::response res(content);
			res.add_header("Content-Type", "text/css; charset=utf-8");
			return res;
		});

		// JS 文件
		CROW_ROUTE(app, "/js/<string>")([staticDir](std::string filename){
			auto content = readFile(staticDir + "/js/" + filename);
			crow::response res(content);
			res.add_header("Content-Type", "application/javascript; charset=utf-8");
			return res;
		});

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
