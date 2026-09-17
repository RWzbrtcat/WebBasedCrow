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
#include <sys/stat.h>
#include <chrono>
#include <algorithm>
#include <cctype>
#include <unordered_set>
#include <random>


// 主管理员账号（首次启动时若 admins 表为空会自动创建；修改后重新编译生效）
const std::string MAIN_ADMIN_EMAIL = "admin@lazycat.com";
const std::string MAIN_ADMIN_PASSWORD = "admin123";

// 生成指定字节数的随机十六进制字符串（用作密码盐值）
std::string randomHex(size_t bytes)
{
    static thread_local std::mt19937_64 rng(std::random_device{}());
    static const char hex[] = "0123456789abcdef";
    std::uniform_int_distribution<unsigned long long> dist;
    std::string out;
    out.reserve(bytes * 2);
    while (out.size() < bytes * 2)
    {
        unsigned long long v = dist(rng);
        for (int i = 0; i < 16 && out.size() < bytes * 2; ++i)
        {
            out.push_back(hex[(v >> (i * 4)) & 0xFULL]);
        }
    }
    return out;
}


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
		if (!mysql_real_connect(conn_, host_.c_str(), user_.c_str(), pass_.c_str(), db_.c_str(), port_, nullptr, CLIENT_FOUND_ROWS))
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
				summary TEXT COMMENT '文章简介',
				author VARCHAR(100) DEFAULT '匿名' COMMENT '作者',
				topic VARCHAR(100) NOT NULL DEFAULT '' COMMENT '文章主题',
				status VARCHAR(20) NOT NULL DEFAULT 'published' COMMENT '文章状态: published/draft',
				likes INT NOT NULL DEFAULT 0 COMMENT '点赞数',
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
				updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
			)ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
		)";

		if (mysql_query(conn_, sql) != 0)
		{
			throw std::runtime_error(std::string("创建表失败：") + mysql_error(conn_));
		}

		// 兼容旧表：若已存在 posts 表但缺少 topic 列，则补充
		if (!columnExists("posts", "topic"))
		{
			const char* alterSql = "ALTER TABLE posts ADD COLUMN topic VARCHAR(100) NOT NULL DEFAULT '' COMMENT '文章主题' AFTER author";
			if (mysql_query(conn_, alterSql) != 0)
			{
				throw std::runtime_error(std::string("补充 topic 列失败：") + mysql_error(conn_));
			}
		}

		// 兼容旧表：若缺少 summary 列，则补充
		if (!columnExists("posts", "summary"))
		{
			const char* alterSql = "ALTER TABLE posts ADD COLUMN summary TEXT COMMENT '文章简介' AFTER content";
			if (mysql_query(conn_, alterSql) != 0)
			{
				throw std::runtime_error(std::string("补充 summary 列失败：") + mysql_error(conn_));
			}
		}

		// 兼容旧表：若缺少 status 列，则补充
		if (!columnExists("posts", "status"))
		{
			const char* alterSql = "ALTER TABLE posts ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'published' COMMENT '文章状态: published/draft' AFTER topic";
			if (mysql_query(conn_, alterSql) != 0)
			{
				throw std::runtime_error(std::string("补充 status 列失败：") + mysql_error(conn_));
			}
		}

		// 兼容旧表：若缺少 likes 列，则补充
		if (!columnExists("posts", "likes"))
		{
			const char* alterSql = "ALTER TABLE posts ADD COLUMN likes INT NOT NULL DEFAULT 0 COMMENT '点赞数' AFTER status";
			if (mysql_query(conn_, alterSql) != 0)
			{
				throw std::runtime_error(std::string("补充 likes 列失败：") + mysql_error(conn_));
			}
		}

		// 专栏表：站长在主页维护的专栏列表
		const char* topicsSql = R"(
			CREATE TABLE IF NOT EXISTS topics(
				id INT AUTO_INCREMENT PRIMARY KEY,
				name VARCHAR(100) NOT NULL UNIQUE COMMENT '专栏名称',
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
			)ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
		)";
		if (mysql_query(conn_, topicsSql) != 0)
		{
			throw std::runtime_error(std::string("创建专栏表失败：") + mysql_error(conn_));
		}

		// 首次初始化：专栏表为空时，用已有文章的 topic 填充专栏列表
		if (mysql_query(conn_, "SELECT COUNT(*) FROM topics") != 0)
		{
			throw std::runtime_error(std::string("查询专栏表失败：") + mysql_error(conn_));
		}
		{
			MYSQL_RES* res = mysql_store_result(conn_);
			if (res)
			{
				MYSQL_ROW row = mysql_fetch_row(res);
				bool empty = !row || !row[0] || std::string(row[0]) == "0";
				mysql_free_result(res);
				if (empty)
				{
					const char* seedSql = "INSERT INTO topics (name) SELECT DISTINCT topic FROM posts WHERE topic <> ''";
					if (mysql_query(conn_, seedSql) != 0)
					{
						throw std::runtime_error(std::string("初始化专栏列表失败：") + mysql_error(conn_));
					}
				}
			}
		}

		// 兼容旧表：若缺少 theme 列，则补充（文章主题，区别于站点配色主题）
		if (!columnExists("posts", "theme"))
		{
			const char* alterSql = "ALTER TABLE posts ADD COLUMN theme VARCHAR(100) NOT NULL DEFAULT '' COMMENT '文章主题' AFTER topic";
			if (mysql_query(conn_, alterSql) != 0)
			{
				throw std::runtime_error(std::string("补充 theme 列失败：") + mysql_error(conn_));
			}
		}

		// 评论表
		const char* commentsSql = R"(
			CREATE TABLE IF NOT EXISTS comments(
				id INT AUTO_INCREMENT PRIMARY KEY,
				post_id INT NOT NULL COMMENT '所属文章 ID',
				parent_id INT NOT NULL DEFAULT 0 COMMENT '父评论 ID（0 表示顶层评论）',
				nickname VARCHAR(100) DEFAULT '匿名' COMMENT '昵称',
				content TEXT NOT NULL COMMENT '评论内容',
				hidden TINYINT NOT NULL DEFAULT 0 COMMENT '是否隐藏（0 显示 / 1 隐藏）',
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '评论时间'
			)ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
		)";
		if (mysql_query(conn_, commentsSql) != 0)
		{
			throw std::runtime_error(std::string("创建评论表失败：") + mysql_error(conn_));
		}

		// 兼容旧表：若缺少 parent_id 列，则补充（用于评论回复）
		if (!columnExists("comments", "parent_id"))
		{
			const char* alterSql = "ALTER TABLE comments ADD COLUMN parent_id INT NOT NULL DEFAULT 0 COMMENT '父评论 ID' AFTER post_id";
			if (mysql_query(conn_, alterSql) != 0)
			{
				throw std::runtime_error(std::string("补充 parent_id 列失败：") + mysql_error(conn_));
			}
		}

		// 兼容旧表：若缺少 hidden 列，则补充（用于站长隐藏评论）
		if (!columnExists("comments", "hidden"))
		{
			const char* alterSql = "ALTER TABLE comments ADD COLUMN hidden TINYINT NOT NULL DEFAULT 0 COMMENT '是否隐藏' AFTER content";
			if (mysql_query(conn_, alterSql) != 0)
			{
				throw std::runtime_error(std::string("补充 hidden 列失败：") + mysql_error(conn_));
			}
		}

		// 配置表（键值对，用于存储站点背景图等全局设置）
		const char* settingsSql = R"(
			CREATE TABLE IF NOT EXISTS settings(
				k VARCHAR(100) PRIMARY KEY COMMENT '配置键',
				v TEXT COMMENT '配置值'
			)ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
		)";
		if (mysql_query(conn_, settingsSql) != 0)
		{
			throw std::runtime_error(std::string("创建配置表失败：") + mysql_error(conn_));
		}

		// 管理员表：邮箱账号 + 密码哈希（SHA2(salt+password,256)）
		const char* adminsSql = R"(
			CREATE TABLE IF NOT EXISTS admins(
				id INT AUTO_INCREMENT PRIMARY KEY,
				email VARCHAR(255) NOT NULL UNIQUE COMMENT '管理员邮箱',
				salt VARCHAR(64) NOT NULL COMMENT '密码盐值',
				password_hash VARCHAR(64) NOT NULL COMMENT 'SHA2(salt+password) 哈希',
				is_main TINYINT NOT NULL DEFAULT 0 COMMENT '是否主管理员',
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
			)ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
		)";
		if (mysql_query(conn_, adminsSql) != 0)
		{
			throw std::runtime_error(std::string("创建管理员表失败：") + mysql_error(conn_));
		}

		// 首次初始化：admins 表为空时，创建默认主管理员账号
		if (mysql_query(conn_, "SELECT COUNT(*) FROM admins") != 0)
		{
			throw std::runtime_error(std::string("查询管理员表失败：") + mysql_error(conn_));
		}
		{
			MYSQL_RES* res = mysql_store_result(conn_);
			if (res)
			{
				MYSQL_ROW row = mysql_fetch_row(res);
				bool empty = !row || !row[0] || std::string(row[0]) == "0";
				mysql_free_result(res);
				if (empty)
				{
					seedMainAdmin();
				}
			}
		}
	}

	// 判断表中某列是否存在
	bool columnExists(const std::string& table, const std::string& column)
	{
		std::string sql =
			"SELECT COUNT(*) FROM information_schema.COLUMNS "
			"WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '" + table +
			"' AND COLUMN_NAME = '" + column + "'";

		if (mysql_query(conn_, sql.c_str()) != 0)
		{
			return false;
		}

		MYSQL_RES* res = mysql_store_result(conn_);
		if (!res)
		{
			return false;
		}

		MYSQL_ROW row = mysql_fetch_row(res);
		bool exists = row && row[0] && std::string(row[0]) != "0";
		mysql_free_result(res);
		return exists;
	}

	// 按状态获取文章列表（published 已发布 / draft 草稿）
	crow::json::wvalue getPosts(const std::string& status)
	{
		std::lock_guard<std::mutex> lock(mtx_);
		checkConnection();

		crow::json::wvalue result;
		std::vector<crow::json::wvalue> posts;

		std::string sql = "SELECT p.id, p.title, p.content, p.summary, p.author, p.topic, p.theme, p.status, p.likes, p.created_at, p.updated_at, "
			"(SELECT COUNT(*) FROM comments c WHERE c.post_id=p.id AND c.hidden=0) AS comment_count "
			"FROM posts p WHERE p.status='" + status + "' ORDER BY p.updated_at DESC";

		if (mysql_query(conn_, sql.c_str()) != 0)
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
				post["summary"] = row[3] ? row[3] : "";
				post["author"] = row[4] ? row[4] : "";
				post["topic"] = row[5] ? row[5] : "";
				post["theme"] = row[6] ? row[6] : "";
				post["status"] = row[7] ? row[7] : "";
				post["likes"] = row[8] ? std::stoi(row[8]) : 0;
				post["created_at"] = row[9] ? row[9] : "";
				post["updated_at"] = row[10] ? row[10] : "";
				post["comment_count"] = row[11] ? std::stoi(row[11]) : 0;
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
		std::string sql = "SELECT id, title, content, summary, author, topic, theme, status, likes, created_at, updated_at FROM posts WHERE id=" + std::to_string(id);

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
		post["summary"] = row[3] ? row[3] : "";
		post["author"] = row[4] ? row[4] : "";
		post["topic"] = row[5] ? row[5] : "";
		post["theme"] = row[6] ? row[6] : "";
		post["status"] = row[7] ? row[7] : "";
		post["likes"] = row[8] ? std::stoi(row[8]) : 0;
		post["created_at"] = row[9] ? row[9] : "";
		post["updated_at"] = row[10] ? row[10] : "";
		mysql_free_result(res);

		result["post"] = std::move(post);
		result["success"] = true;
		return result;
	}

	// 发布文章（使用预处理语句防止 SQL 注入）
	crow::json::wvalue addPost(const std::string& title, const std::string& content, const std::string& summary, const std::string& author, const std::string& topic, const std::string& theme, const std::string& status)
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

		const char* sql = "INSERT INTO posts (title, content, summary, author, topic, theme, status) VALUES (?, ?, ?, ?, ?, ?, ?)";
		if (mysql_stmt_prepare(stmt, sql, std::strlen(sql)) != 0)
		{
			result["success"] = false;
			result["message"] = mysql_stmt_error(stmt);
			mysql_stmt_close(stmt);
			return result;
		}

		MYSQL_BIND bind[7];
		std::memset(bind, 0, sizeof(bind));

		bind[0].buffer_type = MYSQL_TYPE_STRING;
		bind[0].buffer = (void*)title.c_str();
		bind[0].buffer_length = title.length();

		bind[1].buffer_type = MYSQL_TYPE_STRING;
		bind[1].buffer = (void*)content.c_str();
		bind[1].buffer_length = content.length();

		bind[2].buffer_type = MYSQL_TYPE_STRING;
		bind[2].buffer = (void*)summary.c_str();
		bind[2].buffer_length = summary.length();

		bind[3].buffer_type = MYSQL_TYPE_STRING;
		bind[3].buffer = (void*)author.c_str();
		bind[3].buffer_length = author.length();

		bind[4].buffer_type = MYSQL_TYPE_STRING;
		bind[4].buffer = (void*)topic.c_str();
		bind[4].buffer_length = topic.length();

		bind[5].buffer_type = MYSQL_TYPE_STRING;
		bind[5].buffer = (void*)theme.c_str();
		bind[5].buffer_length = theme.length();

		bind[6].buffer_type = MYSQL_TYPE_STRING;
		bind[6].buffer = (void*)status.c_str();
		bind[6].buffer_length = status.length();

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
	crow::json::wvalue updatePost(int id, const std::string& title, const std::string& content, const std::string& summary, const std::string& author, const std::string& topic, const std::string& theme, const std::string& status)
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

		const char* sql = "UPDATE posts SET title=?, content=?, summary=?, author=?, topic=?, theme=?, status=? WHERE id=?";
		if (mysql_stmt_prepare(stmt, sql, std::strlen(sql)) != 0)
		{
			result["success"] = false;
			result["message"] = mysql_stmt_error(stmt);
			mysql_stmt_close(stmt);
			return result;
		}

		MYSQL_BIND bind[8];
		std::memset(bind, 0, sizeof(bind));

		bind[0].buffer_type = MYSQL_TYPE_STRING;
		bind[0].buffer = (void*)title.c_str();
		bind[0].buffer_length = title.length();

		bind[1].buffer_type = MYSQL_TYPE_STRING;
		bind[1].buffer = (void*)content.c_str();
		bind[1].buffer_length = content.length();

		bind[2].buffer_type = MYSQL_TYPE_STRING;
		bind[2].buffer = (void*)summary.c_str();
		bind[2].buffer_length = summary.length();

		bind[3].buffer_type = MYSQL_TYPE_STRING;
		bind[3].buffer = (void*)author.c_str();
		bind[3].buffer_length = author.length();

		bind[4].buffer_type = MYSQL_TYPE_STRING;
		bind[4].buffer = (void*)topic.c_str();
		bind[4].buffer_length = topic.length();

		bind[5].buffer_type = MYSQL_TYPE_STRING;
		bind[5].buffer = (void*)theme.c_str();
		bind[5].buffer_length = theme.length();

		bind[6].buffer_type = MYSQL_TYPE_STRING;
		bind[6].buffer = (void*)status.c_str();
		bind[6].buffer_length = status.length();

		bind[7].buffer_type = MYSQL_TYPE_LONG;
		bind[7].buffer = (void*)&id;

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

	// 点赞/取消点赞：likes 计数增减（delta 为 +1/-1），返回最新点赞数
	crow::json::wvalue changeLikes(int id, int delta)
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

		const char* sql = "UPDATE posts SET likes = GREATEST(likes + ?, 0) WHERE id=?";
		if (mysql_stmt_prepare(stmt, sql, std::strlen(sql)) != 0)
		{
			result["success"] = false;
			result["message"] = mysql_stmt_error(stmt);
			mysql_stmt_close(stmt);
			return result;
		}

		MYSQL_BIND bind[2];
		std::memset(bind, 0, sizeof(bind));

		bind[0].buffer_type = MYSQL_TYPE_LONG;
		bind[0].buffer = (void*)&delta;

		bind[1].buffer_type = MYSQL_TYPE_LONG;
		bind[1].buffer = (void*)&id;

		mysql_stmt_bind_param(stmt, bind);

		if (mysql_stmt_execute(stmt) != 0)
		{
			result["success"] = false;
			result["message"] = mysql_stmt_error(stmt);
		}
		else
		{
			my_ulonglong affected = mysql_stmt_affected_rows(stmt);
			if (affected == 0)
			{
				result["success"] = false;
				result["message"] = "文章不存在";
			}
			else
			{
				// 查询最新点赞数
				std::string sel = "SELECT likes FROM posts WHERE id=" + std::to_string(id);
				if (mysql_query(conn_, sel.c_str()) == 0)
				{
					MYSQL_RES* res = mysql_store_result(conn_);
					if (res)
					{
						MYSQL_ROW row = mysql_fetch_row(res);
						if (row && row[0])
						{
							result["likes"] = std::stoi(row[0]);
						}
						mysql_free_result(res);
					}
				}
				result["success"] = true;
			}
		}
		mysql_stmt_close(stmt);
		return result;
	}

	// 获取某篇文章的所有评论（按时间正序；includeHidden 为 true 时包含被隐藏的评论，仅供站长）
	crow::json::wvalue getComments(int postId, bool includeHidden)
	{
		std::lock_guard<std::mutex> lock(mtx_);
		checkConnection();

		crow::json::wvalue result;
		std::vector<crow::json::wvalue> comments;

		std::string sql = "SELECT id, post_id, parent_id, nickname, content, hidden, created_at FROM comments WHERE post_id=" + std::to_string(postId);
		if (!includeHidden)
		{
			sql += " AND hidden=0";
		}
		sql += " ORDER BY id ASC";

		if (mysql_query(conn_, sql.c_str()) != 0)
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
				crow::json::wvalue c;
				c["id"] = std::stoi(row[0]);
				c["post_id"] = std::stoi(row[1]);
				c["parent_id"] = row[2] ? std::stoi(row[2]) : 0;
				c["nickname"] = row[3] ? row[3] : "";
				c["content"] = row[4] ? row[4] : "";
				c["hidden"] = (row[5] && std::stoi(row[5]) != 0);
				c["created_at"] = row[6] ? row[6] : "";
				comments.push_back(std::move(c));
			}
			mysql_free_result(res);
		}

		result["comments"] = std::move(comments);
		result["success"] = true;
		return result;
	}

	// 新增评论（parentId 为 0 表示顶层评论，否则为回复某条评论）
	crow::json::wvalue addComment(int postId, int parentId, const std::string& nickname, const std::string& content)
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

		const char* sql = "INSERT INTO comments (post_id, parent_id, nickname, content) VALUES (?, ?, ?, ?)";
		if (mysql_stmt_prepare(stmt, sql, std::strlen(sql)) != 0)
		{
			result["success"] = false;
			result["message"] = mysql_stmt_error(stmt);
			mysql_stmt_close(stmt);
			return result;
		}

		MYSQL_BIND bind[4];
		std::memset(bind, 0, sizeof(bind));

		bind[0].buffer_type = MYSQL_TYPE_LONG;
		bind[0].buffer = (void*)&postId;

		bind[1].buffer_type = MYSQL_TYPE_LONG;
		bind[1].buffer = (void*)&parentId;

		bind[2].buffer_type = MYSQL_TYPE_STRING;
		bind[2].buffer = (void*)nickname.c_str();
		bind[2].buffer_length = nickname.length();

		bind[3].buffer_type = MYSQL_TYPE_STRING;
		bind[3].buffer = (void*)content.c_str();
		bind[3].buffer_length = content.length();

		mysql_stmt_bind_param(stmt, bind);

		if (mysql_stmt_execute(stmt) == 0)
		{
			int newID = static_cast<int>(mysql_stmt_insert_id(stmt));
			result["success"] = true;
			result["id"] = newID;
		}
		else
		{
			result["success"] = false;
			result["message"] = mysql_stmt_error(stmt);
		}
		mysql_stmt_close(stmt);
		return result;
	}

	// 隐藏 / 取消隐藏某条评论（站长）
	crow::json::wvalue setCommentHidden(int id, int hidden)
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

		const char* sql = "UPDATE comments SET hidden=? WHERE id=?";
		if (mysql_stmt_prepare(stmt, sql, std::strlen(sql)) != 0)
		{
			result["success"] = false;
			result["message"] = mysql_stmt_error(stmt);
			mysql_stmt_close(stmt);
			return result;
		}

		MYSQL_BIND bind[2];
		std::memset(bind, 0, sizeof(bind));

		bind[0].buffer_type = MYSQL_TYPE_LONG;
		bind[0].buffer = (void*)&hidden;

		bind[1].buffer_type = MYSQL_TYPE_LONG;
		bind[1].buffer = (void*)&id;

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
			result["message"] = (affected > 0) ? "操作成功" : "评论不存在";
		}
		mysql_stmt_close(stmt);
		return result;
	}

	// 删除某条评论及其所有回复（站长）
	crow::json::wvalue deleteComment(int id)
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

		const char* sql = "DELETE FROM comments WHERE id=? OR parent_id=?";
		if (mysql_stmt_prepare(stmt, sql, std::strlen(sql)) != 0)
		{
			result["success"] = false;
			result["message"] = mysql_stmt_error(stmt);
			mysql_stmt_close(stmt);
			return result;
		}

		MYSQL_BIND bind[2];
		std::memset(bind, 0, sizeof(bind));

		bind[0].buffer_type = MYSQL_TYPE_LONG;
		bind[0].buffer = (void*)&id;

		bind[1].buffer_type = MYSQL_TYPE_LONG;
		bind[1].buffer = (void*)&id;

		mysql_stmt_bind_param(stmt, bind);

		if (mysql_stmt_execute(stmt) == 0)
		{
			my_ulonglong affected = mysql_stmt_affected_rows(stmt);
			result["success"] = (affected > 0);
			result["message"] = (affected > 0) ? "删除成功" : "评论不存在";
		}
		else
		{
			result["success"] = false;
			result["message"] = mysql_stmt_error(stmt);
		}
		mysql_stmt_close(stmt);
		return result;
	}

	// 读取配置项（不存在时返回空字符串）
	std::string getSetting(const std::string& key)
	{
		std::lock_guard<std::mutex> lock(mtx_);
		checkConnection();

		std::vector<char> esc(key.length() * 2 + 1);
		mysql_real_escape_string(conn_, esc.data(), key.c_str(), static_cast<unsigned long>(key.length()));
		std::string sql = "SELECT v FROM settings WHERE k='" + std::string(esc.data()) + "'";

		if (mysql_query(conn_, sql.c_str()) != 0)
		{
			return "";
		}

		std::string value;
		MYSQL_RES* res = mysql_store_result(conn_);
		if (res)
		{
			MYSQL_ROW row = mysql_fetch_row(res);
			if (row && row[0]) value = row[0];
			mysql_free_result(res);
		}
		return value;
	}

	// 写入配置项（不存在则插入，存在则更新）
	crow::json::wvalue setSetting(const std::string& key, const std::string& value)
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

		const char* sql = "INSERT INTO settings (k, v) VALUES (?, ?) ON DUPLICATE KEY UPDATE v=VALUES(v)";
		if (mysql_stmt_prepare(stmt, sql, std::strlen(sql)) != 0)
		{
			result["success"] = false;
			result["message"] = mysql_stmt_error(stmt);
			mysql_stmt_close(stmt);
			return result;
		}

		MYSQL_BIND bind[2];
		std::memset(bind, 0, sizeof(bind));

		bind[0].buffer_type = MYSQL_TYPE_STRING;
		bind[0].buffer = (void*)key.c_str();
		bind[0].buffer_length = key.length();

		bind[1].buffer_type = MYSQL_TYPE_STRING;
		bind[1].buffer = (void*)value.c_str();
		bind[1].buffer_length = value.length();

		mysql_stmt_bind_param(stmt, bind);

		if (mysql_stmt_execute(stmt) == 0)
		{
			result["success"] = true;
		}
		else
		{
			result["success"] = false;
			result["message"] = mysql_stmt_error(stmt);
		}
		mysql_stmt_close(stmt);
		return result;
	}

	// 获取专栏列表
	crow::json::wvalue getTopics()
	{
		std::lock_guard<std::mutex> lock(mtx_);
		checkConnection();

		crow::json::wvalue result;
		std::vector<crow::json::wvalue> topics;

		const char* sql = "SELECT id, name FROM topics ORDER BY id ASC";
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
				crow::json::wvalue t;
				t["id"] = std::stoi(row[0]);
				t["name"] = row[1] ? row[1] : "";
				topics.push_back(std::move(t));
			}
			mysql_free_result(res);
		}

		result["topics"] = std::move(topics);
		result["success"] = true;
		return result;
	}

	// 添加专栏（name 唯一）
	crow::json::wvalue addTopic(const std::string& name)
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

		const char* sql = "INSERT INTO topics (name) VALUES (?)";
		if (mysql_stmt_prepare(stmt, sql, std::strlen(sql)) != 0)
		{
			result["success"] = false;
			result["message"] = mysql_stmt_error(stmt);
			mysql_stmt_close(stmt);
			return result;
		}

		MYSQL_BIND bind[1];
		std::memset(bind, 0, sizeof(bind));
		bind[0].buffer_type = MYSQL_TYPE_STRING;
		bind[0].buffer = (void*)name.c_str();
		bind[0].buffer_length = name.length();
		mysql_stmt_bind_param(stmt, bind);

		if (mysql_stmt_execute(stmt) == 0)
		{
			int newID = static_cast<int>(mysql_stmt_insert_id(stmt));
			result["success"] = true;
			result["id"] = newID;
			result["message"] = "专栏添加成功";
		}
		else
		{
			result["success"] = false;
			unsigned int errNo = mysql_stmt_errno(stmt);
			result["message"] = (errNo == 1062) ? "专栏已存在" : mysql_stmt_error(stmt);
		}
		mysql_stmt_close(stmt);
		return result;
	}

	// 删除专栏（仅删除专栏本身，不影响已有文章）
	crow::json::wvalue deleteTopic(int id)
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

		const char* sql = "DELETE FROM topics WHERE id=?";
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
			result["message"] = (affected > 0) ? "专栏已删除" : "专栏不存在";
		}
		else
		{
			result["success"] = false;
			result["message"] = mysql_stmt_error(stmt);
		}
		mysql_stmt_close(stmt);
		return result;
	}

	// ===== 管理员账号 =====

	// 插入管理员记录：密码用 MySQL SHA2(CONCAT(salt, ':', password), 256) 哈希后入库
	bool insertAdmin(const std::string& email, const std::string& password, int isMain, std::string& errMsg, int& outId)
	{
		MYSQL_STMT* stmt = mysql_stmt_init(conn_);
		if (!stmt)
		{
			errMsg = "mysql_stmt_init 失败";
			return false;
		}

		std::string salt = randomHex(16);
		const char* sql = "INSERT INTO admins (email, salt, password_hash, is_main) VALUES (?, ?, SHA2(CONCAT(?, ':', ?), 256), ?)";
		if (mysql_stmt_prepare(stmt, sql, std::strlen(sql)) != 0)
		{
			errMsg = mysql_stmt_error(stmt);
			mysql_stmt_close(stmt);
			return false;
		}

		MYSQL_BIND bind[5];
		std::memset(bind, 0, sizeof(bind));
		bind[0].buffer_type = MYSQL_TYPE_STRING;
		bind[0].buffer = (void*)email.c_str();
		bind[0].buffer_length = email.length();
		bind[1].buffer_type = MYSQL_TYPE_STRING;
		bind[1].buffer = (void*)salt.c_str();
		bind[1].buffer_length = salt.length();
		bind[2].buffer_type = MYSQL_TYPE_STRING;
		bind[2].buffer = (void*)salt.c_str();
		bind[2].buffer_length = salt.length();
		bind[3].buffer_type = MYSQL_TYPE_STRING;
		bind[3].buffer = (void*)password.c_str();
		bind[3].buffer_length = password.length();
		bind[4].buffer_type = MYSQL_TYPE_LONG;
		bind[4].buffer = (void*)&isMain;
		mysql_stmt_bind_param(stmt, bind);

		bool ok = (mysql_stmt_execute(stmt) == 0);
		if (ok)
		{
			outId = static_cast<int>(mysql_stmt_insert_id(stmt));
		}
		else
		{
			unsigned int errNo = mysql_stmt_errno(stmt);
			errMsg = (errNo == 1062) ? "该邮箱已被注册" : mysql_stmt_error(stmt);
		}
		mysql_stmt_close(stmt);
		return ok;
	}

	// 首次初始化时创建主管理员账号
	void seedMainAdmin()
	{
		std::string err;
		int id = 0;
		if (!insertAdmin(MAIN_ADMIN_EMAIL, MAIN_ADMIN_PASSWORD, 1, err, id))
		{
			throw std::runtime_error("创建主管理员失败：" + err);
		}
	}

	// 登录校验：邮箱 + 密码匹配则返回 true，并通过出参返回 id / is_main
	bool loginAdmin(const std::string& email, const std::string& password, int& outId, bool& outIsMain, std::string& errMsg)
	{
		std::lock_guard<std::mutex> lock(mtx_);
		checkConnection();

		std::vector<char> emailEsc(email.length() * 2 + 1);
		std::vector<char> passEsc(password.length() * 2 + 1);
		mysql_real_escape_string(conn_, emailEsc.data(), email.c_str(), static_cast<unsigned long>(email.length()));
		mysql_real_escape_string(conn_, passEsc.data(), password.c_str(), static_cast<unsigned long>(password.length()));

		std::string sql = "SELECT id, is_main FROM admins WHERE email='" + std::string(emailEsc.data()) +
			"' AND password_hash=SHA2(CONCAT(salt, ':', '" + std::string(passEsc.data()) + "'), 256)";

		if (mysql_query(conn_, sql.c_str()) != 0)
		{
			errMsg = mysql_error(conn_);
			return false;
		}

		MYSQL_RES* res = mysql_store_result(conn_);
		if (!res)
		{
			errMsg = "邮箱或密码错误";
			return false;
		}

		MYSQL_ROW row = mysql_fetch_row(res);
		if (!row)
		{
			mysql_free_result(res);
			errMsg = "邮箱或密码错误";
			return false;
		}

		outId = std::stoi(row[0]);
		outIsMain = (row[1] && std::stoi(row[1]) != 0);
		mysql_free_result(res);
		return true;
	}

	// 新增普通管理员
	crow::json::wvalue addAdmin(const std::string& email, const std::string& password)
	{
		std::lock_guard<std::mutex> lock(mtx_);
		checkConnection();

		crow::json::wvalue result;
		std::string err;
		int id = 0;
		if (insertAdmin(email, password, 0, err, id))
		{
			result["success"] = true;
			result["id"] = id;
			result["message"] = "管理员添加成功";
		}
		else
		{
			result["success"] = false;
			result["message"] = err;
		}
		return result;
	}

	// 管理员列表
	crow::json::wvalue getAdmins()
	{
		std::lock_guard<std::mutex> lock(mtx_);
		checkConnection();

		crow::json::wvalue result;
		std::vector<crow::json::wvalue> admins;

		const char* sql = "SELECT id, email, is_main, created_at FROM admins ORDER BY is_main DESC, id ASC";
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
				crow::json::wvalue a;
				a["id"] = std::stoi(row[0]);
				a["email"] = row[1] ? row[1] : "";
				a["is_main"] = (row[2] && std::stoi(row[2]) != 0);
				a["created_at"] = row[3] ? row[3] : "";
				admins.push_back(std::move(a));
			}
			mysql_free_result(res);
		}

		result["admins"] = std::move(admins);
		result["success"] = true;
		return result;
	}

	// 删除管理员（主管理员 is_main=1 不可删除，SQL 层再兜底）
	crow::json::wvalue deleteAdmin(int id)
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

		const char* sql = "DELETE FROM admins WHERE id=? AND is_main=0";
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

		if (mysql_stmt_execute(stmt) != 0)
		{
			result["success"] = false;
			result["message"] = mysql_stmt_error(stmt);
		}
		else
		{
			my_ulonglong affected = mysql_stmt_affected_rows(stmt);
			result["success"] = (affected > 0);
			result["message"] = (affected > 0) ? "管理员已删除" : "管理员不存在或不可删除";
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


// 确保目录存在（不存在则创建）
void ensureDir(const std::string& path)
{
	mkdir(path.c_str(), 0755);
}

// 字符串转小写
std::string toLower(std::string s)
{
	std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c){ return std::tolower(c); });
	return s;
}

// 去除字符串首尾空白
std::string trim(const std::string& s)
{
	size_t first = s.find_first_not_of(" \t\r\n");
	if (first == std::string::npos) return "";
	size_t last = s.find_last_not_of(" \t\r\n");
	return s.substr(first, last - first + 1);
}

// 校验是否为合法的十六进制颜色（#RRGGBB）
bool isValidHexColor(const std::string& c)
{
	if (c.size() != 7 || c[0] != '#') return false;
	for (size_t i = 1; i < c.size(); ++i)
	{
		char ch = c[i];
		bool ok = (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f') || (ch >= 'A' && ch <= 'F');
		if (!ok) return false;
	}
	return true;
}

// 根据文件名返回 MIME 类型
std::string mimeTypeFromFilename(const std::string& filename)
{
	std::string ext;
	size_t dot = filename.find_last_of('.');
	if (dot != std::string::npos)
		ext = toLower(filename.substr(dot));

	if (ext == ".png")  return "image/png";
	if (ext == ".jpg" || ext == ".jpeg") return "image/jpeg";
	if (ext == ".gif")  return "image/gif";
	if (ext == ".webp") return "image/webp";
	if (ext == ".bmp")  return "image/bmp";
	return "application/octet-stream";
}

// 校验扩展名是否为允许上传的图片格式
bool isAllowedImageExt(const std::string& filename)
{
	std::string ext;
	size_t dot = filename.find_last_of('.');
	if (dot == std::string::npos)
		return false;
	ext = toLower(filename.substr(dot));
	return ext == ".png" || ext == ".jpg" || ext == ".jpeg" ||
		   ext == ".gif" || ext == ".webp" || ext == ".bmp";
}

// 生成唯一文件名：时间戳 + 原始扩展名
std::string generateImageName(const std::string& originalName)
{
	std::string ext;
	size_t dot = originalName.find_last_of('.');
	if (dot != std::string::npos)
		ext = toLower(originalName.substr(dot));
	auto now = std::chrono::system_clock::now().time_since_epoch().count();
	return std::to_string(now) + ext;
}

// 从 multipart part 中提取原始文件名（来自 Content-Disposition）
std::string getUploadFilename(const crow::multipart::part& p)
{
	auto it = p.headers.find("Content-Disposition");
	if (it != p.headers.end())
	{
		auto pit = it->second.params.find("filename");
		if (pit != it->second.params.end())
			return pit->second;
	}
	return "";
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


// ===== 管理员登录认证 =====
const std::string SESSION_COOKIE = "blog_session";

// 内存会话表（token -> 会话信息）。个人博客用内存会话即可，服务重启后需重新登录
struct Session
{
    int adminId = 0;
    bool isMain = false;
};
std::unordered_map<std::string, Session> g_sessions;
std::mutex g_sessionsMtx;

// 生成随机会话 token（十六进制）
std::string generateToken()
{
	static thread_local std::mt19937_64 rng(std::random_device{}());
	std::uniform_int_distribution<unsigned long long> dist;
	std::ostringstream oss;
	oss << std::hex << dist(rng) << dist(rng);
	return oss.str();
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

		// 处理浏览器的 OPTIONS 预检请求
		CROW_ROUTE(app, "/api/<path>").methods("OPTIONS"_method)([](const crow::request& req, std::string path){
			crow::response res(200);
			addCorsHeaders(res);
			return res;
		});

		// ========== 登录认证路由 ==========

		// POST /api/login - 管理员登录（邮箱 + 密码），成功后设置会话 Cookie
		CROW_ROUTE(app, "/api/login").methods("POST"_method)([&db](const crow::request& req){
			auto body = crow::json::load(req.body);
			crow::json::wvalue result;
			if (!body)
			{
				result["success"] = false;
				result["message"] = "无效的 JSON 数据";
				return crow::response(400, result);
			}

			std::string email = trim(body.has("email") ? std::string(body["email"].s()) : std::string(""));
			std::string password = body.has("password") ? std::string(body["password"].s()) : std::string("");

			if (email.empty() || password.empty())
			{
				result["success"] = false;
				result["message"] = "请输入邮箱和密码";
				crow::response res(400, result);
				addCorsHeaders(res);
				return res;
			}

			int adminId = 0;
			bool isMain = false;
			std::string errMsg;
			if (!db.loginAdmin(email, password, adminId, isMain, errMsg))
			{
				crow::json::wvalue err;
				err["success"] = false;
				err["message"] = errMsg;
				crow::response res(401, err);
				addCorsHeaders(res);
				return res;
			}

			std::string token = generateToken();
			Session s;
			s.adminId = adminId;
			s.isMain = isMain;
			{
				std::lock_guard<std::mutex> lock(g_sessionsMtx);
				g_sessions[token] = s;
			}

			result["success"] = true;
			result["is_main"] = s.isMain;
			crow::response res(200, result);
			res.add_header("Set-Cookie", SESSION_COOKIE + "=" + token + "; HttpOnly; Path=/; SameSite=Lax; Max-Age=2592000");
			addCorsHeaders(res);
			return res;
		});

		// GET /api/auth - 查询当前登录态（是否登录、是否主管理员）
		CROW_ROUTE(app, "/api/auth").methods("GET"_method)([](const crow::request& req){
			crow::json::wvalue result;
			result["success"] = true;
			result["authed"] = isLoggedIn(req);
			result["is_main"] = isMainAdmin(req);
			crow::response res(result);
			addCorsHeaders(res);
			return res;
		});

		// ========== 管理员管理 API（仅主管理员可用） ==========

		// GET /api/admins - 管理员列表
		CROW_ROUTE(app, "/api/admins").methods("GET"_method)([&db](const crow::request& req){
			if (!isLoggedIn(req)) return unauthorizedResponse();
			if (!isMainAdmin(req)) return forbiddenResponse();
			crow::response res(db.getAdmins());
			addCorsHeaders(res);
			return res;
		});

		// POST /api/admins - 新增管理员
		CROW_ROUTE(app, "/api/admins").methods("POST"_method)([&db](const crow::request& req){
			if (!isLoggedIn(req)) return unauthorizedResponse();
			if (!isMainAdmin(req)) return forbiddenResponse();

			auto body = crow::json::load(req.body);
			if (!body)
			{
				crow::json::wvalue err;
				err["success"] = false;
				err["message"] = "无效的 JSON 数据";
				return crow::response(400, err);
			}

			std::string email = trim(body.has("email") ? std::string(body["email"].s()) : std::string(""));
			std::string password = body.has("password") ? std::string(body["password"].s()) : std::string("");

			if (email.empty() || password.empty())
			{
				crow::json::wvalue err;
				err["success"] = false;
				err["message"] = "邮箱和密码不能为空";
				return crow::response(400, err);
			}
			if (email.length() > 255) email = email.substr(0, 255);

			crow::response res(db.addAdmin(email, password));
			addCorsHeaders(res);
			return res;
		});

		// DELETE /api/admins/<int> - 删除管理员
		CROW_ROUTE(app, "/api/admins/<int>").methods("DELETE"_method)([&db](const crow::request& req, int id){
			if (!isLoggedIn(req)) return unauthorizedResponse();
			if (!isMainAdmin(req)) return forbiddenResponse();
			crow::response res(db.deleteAdmin(id));
			addCorsHeaders(res);
			return res;
		});

		// ========== REST API 路由 ==========

		// GET /api/posts - 获取所有已发布文章
		CROW_ROUTE(app, "/api/posts").methods("GET"_method)([&db](){
			crow::response res(db.getPosts("published"));
			addCorsHeaders(res);
			return res;
		});

		// GET /api/drafts - 获取所有草稿（仅登录后可访问）
		CROW_ROUTE(app, "/api/drafts").methods("GET"_method)([&db](const crow::request& req){
			if (!isLoggedIn(req)) return unauthorizedResponse();
			crow::response res(db.getPosts("draft"));
			addCorsHeaders(res);
			return res;
		});

		// GET /api/topics - 获取专栏列表（公开）
		CROW_ROUTE(app, "/api/topics").methods("GET"_method)([&db](){
			crow::response res(db.getTopics());
			addCorsHeaders(res);
			return res;
		});

		// POST /api/topics - 添加专栏（仅登录后可用）
		CROW_ROUTE(app, "/api/topics").methods("POST"_method)([&db](const crow::request& req){
			if (!isLoggedIn(req)) return unauthorizedResponse();
			auto body = crow::json::load(req.body);
			if (!body)
			{
				crow::json::wvalue err;
				err["success"] = false;
				err["message"] = "无效的 JSON 数据";
				return crow::response(400, err);
			}
			std::string name = trim(body.has("name") ? std::string(body["name"].s()) : std::string(""));
			if (name.empty())
			{
				crow::json::wvalue err;
				err["success"] = false;
				err["message"] = "专栏名称不能为空";
				return crow::response(400, err);
			}
			if (name.length() > 100) name = name.substr(0, 100);
			crow::response res(db.addTopic(name));
			addCorsHeaders(res);
			return res;
		});

		// DELETE /api/topics/<int> - 删除专栏（仅登录后可用）
		CROW_ROUTE(app, "/api/topics/<int>").methods("DELETE"_method)([&db](const crow::request& req, int id){
			if (!isLoggedIn(req)) return unauthorizedResponse();
			crow::response res(db.deleteTopic(id));
			addCorsHeaders(res);
			return res;
		});

		// POST /api/posts - 发布文章（仅登录后可用）
		CROW_ROUTE(app, "/api/posts").methods("POST"_method)([&db](const crow::request& req){
			if (!isLoggedIn(req)) return unauthorizedResponse();
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
			std::string summary = body.has("summary") ? std::string(body["summary"].s()) : std::string("");
			std::string author = body.has("author") ? std::string(body["author"].s()) : std::string("匿名");
			std::string topic = body.has("topic") ? std::string(body["topic"].s()) : std::string("");
			std::string theme = body.has("theme") ? std::string(body["theme"].s()) : std::string("");
			std::string status = body.has("status") ? std::string(body["status"].s()) : std::string("published");
			crow::response res(db.addPost(title, content, summary, author, topic, theme, status));
			addCorsHeaders(res);
			return res;
		});

		// GET /api/posts/<id> - 获取单篇文章
		CROW_ROUTE(app, "/api/posts/<int>").methods("GET"_method)([&db](int id){
			crow::response res(db.getPostById(id));
			addCorsHeaders(res);
			return res;
		});

		// PUT /api/posts/<id> - 更新文章（仅登录后可用）
		CROW_ROUTE(app, "/api/posts/<int>").methods("PUT"_method)([&db](const crow::request& req, int id){
			if (!isLoggedIn(req)) return unauthorizedResponse();
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
			std::string summary = body.has("summary") ? std::string(body["summary"].s()) : std::string("");
			std::string author = body.has("author") ? std::string(body["author"].s()) : std::string("匿名");
			std::string topic = body.has("topic") ? std::string(body["topic"].s()) : std::string("");
			std::string theme = body.has("theme") ? std::string(body["theme"].s()) : std::string("");
			std::string status = body.has("status") ? std::string(body["status"].s()) : std::string("published");
			crow::response res(db.updatePost(id, title, content, summary, author, topic, theme, status));
			addCorsHeaders(res);
			return res;
		});

		// DELETE /api/posts/<id> - 删除文章（仅登录后可用）
		CROW_ROUTE(app, "/api/posts/<int>").methods("DELETE"_method)([&db](const crow::request& req, int id){
			if (!isLoggedIn(req)) return unauthorizedResponse();
			crow::response res(db.deletePost(id));
			addCorsHeaders(res);
			return res;
		});

		// POST /api/posts/<id>/like - 点赞（公开，无需登录）
		CROW_ROUTE(app, "/api/posts/<int>/like").methods("POST"_method)([&db](int id){
			crow::response res(db.changeLikes(id, 1));
			addCorsHeaders(res);
			return res;
		});

		// POST /api/posts/<id>/unlike - 取消点赞（公开，无需登录）
		CROW_ROUTE(app, "/api/posts/<int>/unlike").methods("POST"_method)([&db](int id){
			crow::response res(db.changeLikes(id, -1));
			addCorsHeaders(res);
			return res;
		});

		// GET /api/posts/<id>/comments - 获取评论（公开；站长登录后额外包含被隐藏评论）
		CROW_ROUTE(app, "/api/posts/<int>/comments").methods("GET"_method)([&db](const crow::request& req, int id){
			crow::response res(db.getComments(id, isLoggedIn(req)));
			addCorsHeaders(res);
			return res;
		});

		// POST /api/posts/<id>/comments - 发表评论 / 回复（公开，无需登录）
		CROW_ROUTE(app, "/api/posts/<int>/comments").methods("POST"_method)([&db](const crow::request& req, int id){
			auto body = crow::json::load(req.body);
			if (!body)
			{
				crow::json::wvalue err;
				err["success"] = false;
				err["message"] = "无效的 JSON 数据";
				return crow::response(400, err);
			}

			std::string nickname = body.has("nickname") ? std::string(body["nickname"].s()) : std::string("");
			std::string content = body.has("content") ? std::string(body["content"].s()) : std::string("");
			int parentId = body.has("parent_id") ? static_cast<int>(body["parent_id"].i()) : 0;
			nickname = trim(nickname);
			content = trim(content);

			if (content.empty())
			{
				crow::json::wvalue err;
				err["success"] = false;
				err["message"] = "评论内容不能为空";
				return crow::response(400, err);
			}
			if (parentId < 0) parentId = 0;
			if (nickname.empty()) nickname = "匿名";
			if (nickname.length() > 50) nickname = nickname.substr(0, 50);
			if (content.length() > 2000) content = content.substr(0, 2000);

			crow::response res(db.addComment(id, parentId, nickname, content));
			addCorsHeaders(res);
			return res;
		});

		// PUT /api/comments/<int> - 隐藏 / 取消隐藏评论（仅登录）
		CROW_ROUTE(app, "/api/comments/<int>").methods("PUT"_method)([&db](const crow::request& req, int id){
			if (!isLoggedIn(req)) return unauthorizedResponse();
			auto body = crow::json::load(req.body);
			if (!body || !body.has("hidden"))
			{
				crow::json::wvalue err;
				err["success"] = false;
				err["message"] = "无效的 JSON 数据";
				crow::response res(400, err);
				addCorsHeaders(res);
				return res;
			}
			bool hidden = body["hidden"].b();
			crow::response res(db.setCommentHidden(id, hidden ? 1 : 0));
			addCorsHeaders(res);
			return res;
		});

		// DELETE /api/comments/<int> - 删除评论及其回复（仅登录）
		CROW_ROUTE(app, "/api/comments/<int>").methods("DELETE"_method)([&db](const crow::request& req, int id){
			if (!isLoggedIn(req)) return unauthorizedResponse();
			crow::response res(db.deleteComment(id));
			addCorsHeaders(res);
			return res;
		});

		// POST /api/upload - 上传图片（multipart/form-data，字段名 image，仅登录后可用）
		CROW_ROUTE(app, "/api/upload").methods("POST"_method)([staticDir](const crow::request& req){
			if (!isLoggedIn(req)) return unauthorizedResponse();
			crow::json::wvalue result;
			try
			{
				crow::multipart::message msg(req);
				crow::multipart::part file = msg.get_part_by_name("image");
				if (file.body.empty())
				{
					result["success"] = false;
					result["message"] = "未找到上传的图片";
					crow::response res(400, result);
					addCorsHeaders(res);
					return res;
				}

				std::string originalName = getUploadFilename(file);
				if (originalName.empty() || !isAllowedImageExt(originalName))
				{
					result["success"] = false;
					result["message"] = "仅支持 png / jpg / jpeg / gif / webp / bmp 格式";
					crow::response res(400, result);
					addCorsHeaders(res);
					return res;
				}

				// 限制图片大小不超过 10MB，避免异常上传占用磁盘
				const size_t maxSize = 10 * 1024 * 1024;
				if (file.body.size() > maxSize)
				{
					result["success"] = false;
					result["message"] = "图片大小不能超过 10MB";
					crow::response res(400, result);
					addCorsHeaders(res);
					return res;
				}

				std::string uploadDir = staticDir + "/uploads";
				ensureDir(uploadDir);

				std::string filename = generateImageName(originalName);
				std::ofstream out(uploadDir + "/" + filename, std::ios::binary);
				if (!out.is_open())
				{
					result["success"] = false;
					result["message"] = "无法写入文件，请检查 uploads 目录权限";
					crow::response res(500, result);
					addCorsHeaders(res);
					return res;
				}
				out.write(file.body.data(), static_cast<std::streamsize>(file.body.size()));
				out.close();

				result["success"] = true;
				result["url"] = "/uploads/" + filename;
				crow::response res(result);
				addCorsHeaders(res);
				return res;
			}
			catch (const std::exception& e)
			{
				result["success"] = false;
				result["message"] = std::string("上传失败: ") + e.what();
				crow::response res(500, result);
				addCorsHeaders(res);
				return res;
			}
		});

		// GET /api/settings/background - 获取当前站点背景图（公开）
		CROW_ROUTE(app, "/api/settings/background").methods("GET"_method)([&db](){
			crow::json::wvalue out;
			out["success"] = true;
			out["url"] = db.getSetting("background");
			crow::response res(out);
			addCorsHeaders(res);
			return res;
		});

		// POST /api/settings/background - 设置站点背景图（仅登录后可用）
		CROW_ROUTE(app, "/api/settings/background").methods("POST"_method)([&db](const crow::request& req){
			if (!isLoggedIn(req)) return unauthorizedResponse();

			auto body = crow::json::load(req.body);
			if (!body)
			{
				crow::json::wvalue err;
				err["success"] = false;
				err["message"] = "无效的 JSON 数据";
				crow::response res(400, err);
				addCorsHeaders(res);
				return res;
			}

			std::string url = body.has("url") ? std::string(body["url"].s()) : std::string("");
			url = trim(url);
			if (url.empty() || url.rfind("/uploads/", 0) != 0)
			{
				crow::json::wvalue err;
				err["success"] = false;
				err["message"] = "背景地址无效，仅支持本站上传的图片";
				crow::response res(400, err);
				addCorsHeaders(res);
				return res;
			}

			crow::response res(db.setSetting("background", url));
			addCorsHeaders(res);
			return res;
		});
		// GET /api/settings/theme - 获取当前主题配色（公开）
		CROW_ROUTE(app, "/api/settings/theme").methods("GET"_method)([&db](){
			crow::json::wvalue out;
			out["success"] = true;
			out["theme"] = db.getSetting("theme");
			crow::response res(out);
			addCorsHeaders(res);
			return res;
		});

		// POST /api/settings/theme - 设置主题配色（仅登录后可用）
		CROW_ROUTE(app, "/api/settings/theme").methods("POST"_method)([&db](const crow::request& req){
			if (!isLoggedIn(req)) return unauthorizedResponse();

			auto body = crow::json::load(req.body);
			if (!body)
			{
				crow::json::wvalue err;
				err["success"] = false;
				err["message"] = "无效的 JSON 数据";
				crow::response res(400, err);
				addCorsHeaders(res);
				return res;
			}

			const char* keys[] = {"nav_bg", "card_bg", "card_border", "accent", "accent_dark", "accent_soft"};
			crow::json::wvalue theme;
			for (const char* key : keys)
			{
				if (!body.has(key))
				{
					crow::json::wvalue err;
					err["success"] = false;
					err["message"] = "主题配色字段不完整";
					crow::response res(400, err);
					addCorsHeaders(res);
					return res;
				}
				std::string color = trim(std::string(body[key].s()));
				if (!isValidHexColor(color))
				{
					crow::json::wvalue err;
					err["success"] = false;
					err["message"] = "颜色格式无效，需为 #RRGGBB";
					crow::response res(400, err);
					addCorsHeaders(res);
					return res;
				}
				theme[key] = color;
			}

			crow::response res(db.setSetting("theme", theme.dump()));
			addCorsHeaders(res);
			return res;
		});

		// ========== 静态文件服务 ==========

		// 根路径返回首页（文章列表）
		CROW_ROUTE(app, "/")([staticDir](){
			return htmlResponse(readFile(staticDir + "/index.html"));
		});

		// 文章详情页
		CROW_ROUTE(app, "/post")([staticDir](){
			return htmlResponse(readFile(staticDir + "/post.html"));
		});

		// 登录页
		CROW_ROUTE(app, "/login")([staticDir](){
			return htmlResponse(readFile(staticDir + "/login.html"));
		});

		// 退出登录：清除会话并跳回首页
		CROW_ROUTE(app, "/logout")([](const crow::request& req){
			std::string token = getCookie(req, SESSION_COOKIE);
			if (!token.empty())
			{
				std::lock_guard<std::mutex> lock(g_sessionsMtx);
				g_sessions.erase(token);
			}
			crow::response res;
			res.add_header("Set-Cookie", SESSION_COOKIE + "=; HttpOnly; Path=/; Max-Age=0");
			res.moved("/");
			return res;
		});

		// 草稿页（仅登录后可访问）
		CROW_ROUTE(app, "/drafts")([staticDir](const crow::request& req){
			if (!isLoggedIn(req))
			{
				crow::response res;
				res.moved("/login");
				return res;
			}
			return htmlResponse(readFile(staticDir + "/drafts.html"));
		});

		// 编辑器页（新建 / 编辑，仅登录后可访问）
		CROW_ROUTE(app, "/editor")([staticDir](const crow::request& req){
			if (!isLoggedIn(req))
			{
				crow::response res;
				res.moved("/login");
				return res;
			}
			return htmlResponse(readFile(staticDir + "/editor.html"));
		});

		// 管理员管理页（仅主管理员可访问）
		CROW_ROUTE(app, "/admin")([staticDir](const crow::request& req){
			if (!isLoggedIn(req))
			{
				crow::response res;
				res.moved("/login");
				return res;
			}
			if (!isMainAdmin(req))
			{
				crow::response res;
				res.moved("/");
				return res;
			}
			return htmlResponse(readFile(staticDir + "/admin.html"));
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

		// 上传的图片
		CROW_ROUTE(app, "/uploads/<string>")([staticDir](std::string filename){
			std::string content = readFile(staticDir + "/uploads/" + filename);
			if (content.empty())
			{
				return crow::response(404);
			}
			crow::response res(content);
			res.add_header("Content-Type", mimeTypeFromFilename(filename));
			res.add_header("Cache-Control", "public, max-age=86400");
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
