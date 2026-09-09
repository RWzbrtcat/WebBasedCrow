#include "crow.h"
#include <mysql/mysql.h>
#include <string>
#include <vector>
#include <mutex>
#include <fstream>
#include <sstream>
#include <iosteam>
#include <cstring>


// DataBase 类：封装所有 MySQL 操作
// 使用 RALL 管理连接，使用 mutex 保证线程安全


class DataBase
{
	MySQL* conn_ = nullptr; // MySQL 连接句柄
	std::mutex mtx_;  // 互斥锁，保证多线程访问
	std::string host_, user_, pass_, db_;
	unsigned int port_;

public:
	// 构造函数 - 建立连接并初始化表
	DataBase(const std::string& host, const std::string& user, const std::string& pass,
					const std::string db) : host_(host), user_(user), pass_(pass), db_(db)
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
			throw std::runtime_error("mysql_init 失败!")；
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

	// 初始化数据表
	void initTable()
	{
		const char* sql = R"(
			CREATE TABLE IF NOT EXIST tasks(
				id INT AUTO_INCREMENT PRIMARY KEY,
				title VARCHAR(255) NOT NULL COMMENT '任务标题',
				description TEXT COMMENT '任务描述',
				priority INT DEFAULT 2 COMMENT '1=高 2=中 3=低',
				completed TINYINT DEFAULT 0 COMMIT '0=为完成 1=已完成',
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
		)";

		if (mysql_query(conn_, sql) != 0)
		{
			throw std::runtime_error(std::string("创建表失败：") + mysql_error(conn_));
		}
	}


	

};










int main()
{
	crow::SimpleApp app;

	// 定义路由
	CROW_ROUTE(app, "/")([](){
		return "Hello from c++ Web Server!";
	});

	CROW_ROUTE(app, "/user/<string>")([](std::string name){
		return "Hello, " + name;		
	});

	// 监听 0.0.0.0:8080 多线程运行
	app.port(8080).multithreaded().run();

}
