#include "database.h"

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <iostream>
#include <stdexcept>

#include "utils.h"

namespace
{
// 当前本地日期，格式 YYYY-MM-DD
std::string todayStr()
{
    std::time_t t = std::time(nullptr);
    std::tm tm{};
#if defined(_WIN32)
    localtime_s(&tm, &t);
#else
    localtime_r(&t, &tm);
#endif
    char buf[16];
    std::snprintf(buf, sizeof(buf), "%04d-%02d-%02d", tm.tm_year + 1900, tm.tm_mon + 1, tm.tm_mday);
    return std::string(buf);
}

// 把 YYYY-MM-DD 转成「自公元 0 年起的第几天」，用于算连续天数。
// 采用 Howard Hinnant 的 days_from_civil 算法，纯整数运算，不受时区影响。
long daysFromDate(const std::string& date)
{
    int y = 0, m = 0, d = 0;
    if (std::sscanf(date.c_str(), "%d-%d-%d", &y, &m, &d) != 3) return 0;
    if (m <= 2) y -= 1;
    long era = (y >= 0 ? y : y - 399) / 400;
    unsigned yoe = static_cast<unsigned>(y - era * 400);
    unsigned doy = static_cast<unsigned>((153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1);
    unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return era * 146097L + static_cast<long>(doe);
}

// SQL 字符串字面量转义（用于拼接内部生成的日期、分类等）
std::string sqlQuote(MYSQL* conn, const std::string& s)
{
    std::vector<char> buf(s.length() * 2 + 1);
    mysql_real_escape_string(conn, buf.data(), s.c_str(), static_cast<unsigned long>(s.length()));
    return "'" + std::string(buf.data()) + "'";
}
} // namespace

// ===== 连接管理 =====

DataBase::DataBase(const std::string& host, const std::string& user, const std::string& pass,
                   const std::string db, unsigned int port)
    : host_(host), user_(user), pass_(pass), db_(db), port_(port)
{
    connect();   // 建立连接
    initTable(); // 创建表（如果表不存在）
}

DataBase::~DataBase()
{
    if (conn_)
    {
        mysql_close(conn_);
    }
}

// 建立 MySQL 连接
void DataBase::connect()
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
void DataBase::checkConnection()
{
    if (mysql_ping(conn_) != 0)
    {
        std::cerr << "[DB] 连接断开，正在重连..." << std::endl;
        mysql_close(conn_);
        connect();
    }
}

// 初始化数据表
void DataBase::initTable()
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
            hidden TINYINT NOT NULL DEFAULT 0 COMMENT '是否隐藏（0 显示 / 1 隐藏）',
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

    // 匿名作者标识：未登录访客发评论时由服务端下发 HttpOnly Cookie（blog_anon），
    // 据此识别「自己的评论」以便自助删除/修改。历史评论为 NULL，视为无主，仅管理员可操作。
    if (!columnExists("comments", "owner_token"))
    {
        const char* alterSql = "ALTER TABLE comments ADD COLUMN owner_token VARCHAR(64) NULL DEFAULT NULL "
                               "COMMENT '匿名作者标识' AFTER nickname";
        if (mysql_query(conn_, alterSql) != 0)
        {
            throw std::runtime_error(std::string("补充 owner_token 列失败：") + mysql_error(conn_));
        }
    }
    if (!indexExists("comments", "idx_comments_owner"))
    {
        if (mysql_query(conn_, "CREATE INDEX idx_comments_owner ON comments(owner_token)") != 0)
        {
            throw std::runtime_error(std::string("创建 owner_token 索引失败：") + mysql_error(conn_));
        }
    }

    // 面试题库：题目与答案分开存，答案走单独接口下发，避免列表接口直接剧透
    const char* questionsSql = R"(
        CREATE TABLE IF NOT EXISTS questions(
            id INT AUTO_INCREMENT PRIMARY KEY,
            category VARCHAR(50) NOT NULL COMMENT '分类：C++ / MySQL / 网络 / 操作系统 / 算法',
            tags VARCHAR(200) NOT NULL DEFAULT '' COMMENT '标签，逗号分隔',
            difficulty TINYINT NOT NULL DEFAULT 2 COMMENT '难度：1 基础 / 2 进阶 / 3 困难',
            question TEXT NOT NULL COMMENT '题干（Markdown）',
            answer TEXT NOT NULL COMMENT '答案（Markdown，支持代码块与 mermaid）',
            status TINYINT NOT NULL DEFAULT 0 COMMENT '状态：0 草稿 / 1 已发布',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
            KEY idx_questions_cat (category, status)
        )ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    )";
    if (mysql_query(conn_, questionsSql) != 0)
    {
        throw std::runtime_error(std::string("创建题库表失败：") + mysql_error(conn_));
    }

    // 每日排期：某天用哪道题。与题库分离，题库增删改不会让历史题目跳变
    const char* dailySql = R"(
        CREATE TABLE IF NOT EXISTS daily_questions(
            d DATE PRIMARY KEY COMMENT '当天日期',
            question_id INT NOT NULL COMMENT '题目 ID',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '生成时间'
        )ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    )";
    if (mysql_query(conn_, dailySql) != 0)
    {
        throw std::runtime_error(std::string("创建每日一题表失败：") + mysql_error(conn_));
    }

    // 答题记录：匿名访客凭 blog_anon Cookie 认领，用于「连续打卡 N 天」
    const char* dailySeenSql = R"(
        CREATE TABLE IF NOT EXISTS daily_seen(
            d DATE NOT NULL COMMENT '日期',
            owner_token VARCHAR(64) NOT NULL COMMENT '匿名访客标识',
            question_id INT NOT NULL COMMENT '题目 ID',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '首次查看答案时间',
            PRIMARY KEY (d, owner_token)
        )ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    )";
    if (mysql_query(conn_, dailySeenSql) != 0)
    {
        throw std::runtime_error(std::string("创建答题记录表失败：") + mysql_error(conn_));
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

    // 管理员表：邮箱账号 + 密码哈希（SHA2(salt+password,256)）+ 昵称 + 头像
    const char* adminsSql = R"(
        CREATE TABLE IF NOT EXISTS admins(
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(255) NOT NULL UNIQUE COMMENT '管理员邮箱',
            nickname VARCHAR(100) NOT NULL DEFAULT '' COMMENT '昵称（默认等于邮箱）',
            avatar VARCHAR(500) NOT NULL DEFAULT '' COMMENT '头像 URL',
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

    // 兼容旧表：若缺少 nickname 列，则补充
    if (!columnExists("admins", "nickname"))
    {
        const char* alterSql = "ALTER TABLE admins ADD COLUMN nickname VARCHAR(100) NOT NULL DEFAULT '' COMMENT '昵称' AFTER email";
        if (mysql_query(conn_, alterSql) != 0)
        {
            throw std::runtime_error(std::string("补充 nickname 列失败：") + mysql_error(conn_));
        }
    }

    // 兼容旧表：若缺少 avatar 列，则补充
    if (!columnExists("admins", "avatar"))
    {
        const char* alterSql = "ALTER TABLE admins ADD COLUMN avatar VARCHAR(500) NOT NULL DEFAULT '' COMMENT '头像 URL' AFTER nickname";
        if (mysql_query(conn_, alterSql) != 0)
        {
            throw std::runtime_error(std::string("补充 avatar 列失败：") + mysql_error(conn_));
        }
    }

    // 昵称兜底：未设置昵称的账号默认用邮箱作为昵称
    if (mysql_query(conn_, "UPDATE admins SET nickname = email WHERE nickname = ''") != 0)
    {
        throw std::runtime_error(std::string("初始化管理员昵称失败：") + mysql_error(conn_));
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

    // 兼容旧表：若 posts 缺少 author_id 列，则补充（记录文章归属的管理员）
    if (!columnExists("posts", "author_id"))
    {
        const char* alterSql = "ALTER TABLE posts ADD COLUMN author_id INT NOT NULL DEFAULT 0 COMMENT '作者管理员 ID' AFTER author";
        if (mysql_query(conn_, alterSql) != 0)
        {
            throw std::runtime_error(std::string("补充 author_id 列失败：") + mysql_error(conn_));
        }
    }

    // 兼容旧表：若 posts 缺少 hidden 列，则补充（用于管理员隐藏文章）
    if (!columnExists("posts", "hidden"))
    {
        const char* alterSql = "ALTER TABLE posts ADD COLUMN hidden TINYINT NOT NULL DEFAULT 0 COMMENT '是否隐藏（0 显示 / 1 隐藏）' AFTER likes";
        if (mysql_query(conn_, alterSql) != 0)
        {
            throw std::runtime_error(std::string("补充 hidden 列失败：") + mysql_error(conn_));
        }
    }

    // 历史文章（author_id=0）一律归到主管理员，作者显示名同步为主管理员昵称
    backfillLegacyPosts();
}

// 判断表中某列是否存在
bool DataBase::columnExists(const std::string& table, const std::string& column)
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

bool DataBase::indexExists(const std::string& table, const std::string& index)
{
    std::string sql =
        "SELECT COUNT(*) FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '" + table +
        "' AND INDEX_NAME = '" + index + "'";

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
crow::json::wvalue DataBase::getPosts(const std::string& status)
{
    std::lock_guard<std::mutex> lock(mtx_);
    checkConnection();

    crow::json::wvalue result;
    std::vector<crow::json::wvalue> posts;

    std::string sql = "SELECT p.id, p.title, p.content, p.summary, p.author, p.author_id, p.topic, p.theme, p.status, p.likes, p.created_at, p.updated_at, "
        "(SELECT COUNT(*) FROM comments c WHERE c.post_id=p.id AND c.hidden=0) AS comment_count "
        "FROM posts p WHERE p.status='" + status + "' AND p.hidden=0 ORDER BY p.updated_at DESC";

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
            post["author_id"] = row[5] ? std::stoi(row[5]) : 0;
            post["topic"] = row[6] ? row[6] : "";
            post["theme"] = row[7] ? row[7] : "";
            post["status"] = row[8] ? row[8] : "";
            post["likes"] = row[9] ? std::stoi(row[9]) : 0;
            post["created_at"] = row[10] ? row[10] : "";
            post["updated_at"] = row[11] ? row[11] : "";
            post["comment_count"] = row[12] ? std::stoi(row[12]) : 0;
            posts.push_back(std::move(post));
        }
        mysql_free_result(res);
    }

    result["posts"] = std::move(posts);
    result["success"] = true;
    return result;
}

// 获取已隐藏文章列表（主管理员看全部，普通管理员只看自己的）
crow::json::wvalue DataBase::getHiddenPosts(bool isMain, int adminId)
{
    std::lock_guard<std::mutex> lock(mtx_);
    checkConnection();

    crow::json::wvalue result;
    std::vector<crow::json::wvalue> posts;

    std::string sql = "SELECT id, title, content, summary, author, author_id, topic, theme, status, likes, hidden, created_at, updated_at "
        "FROM posts WHERE hidden=1";
    if (!isMain)
    {
        sql += " AND author_id=" + std::to_string(adminId);
    }
    sql += " ORDER BY updated_at DESC";

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
            post["author_id"] = row[5] ? std::stoi(row[5]) : 0;
            post["topic"] = row[6] ? row[6] : "";
            post["theme"] = row[7] ? row[7] : "";
            post["status"] = row[8] ? row[8] : "";
            post["likes"] = row[9] ? std::stoi(row[9]) : 0;
            post["hidden"] = (row[10] && std::stoi(row[10]) != 0);
            post["created_at"] = row[11] ? row[11] : "";
            post["updated_at"] = row[12] ? row[12] : "";
            posts.push_back(std::move(post));
        }
        mysql_free_result(res);
    }

    result["posts"] = std::move(posts);
    result["success"] = true;
    return result;
}

// 获取单篇文章（隐藏文章仅作者本人或主管理员可见，其余视为不存在）
crow::json::wvalue DataBase::getPostById(int id, bool isMain, int adminId)
{
    std::lock_guard<std::mutex> lock(mtx_);
    checkConnection();

    crow::json::wvalue result;
    std::string sql = "SELECT id, title, content, summary, author, author_id, topic, theme, status, likes, hidden, created_at, updated_at FROM posts WHERE id=" + std::to_string(id);

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
    int authorId = row[5] ? std::stoi(row[5]) : 0;
    bool hidden = row[10] && std::stoi(row[10]) != 0;

    // 隐藏的文章，仅作者本人或主管理员可见
    if (hidden && !(isMain || (adminId > 0 && adminId == authorId)))
    {
        mysql_free_result(res);
        result["success"] = false;
        result["message"] = "文章不存在";
        return result;
    }

    crow::json::wvalue post;
    post["id"] = std::stoi(row[0]);
    post["title"] = row[1] ? row[1] : "";
    post["content"] = row[2] ? row[2] : "";
    post["summary"] = row[3] ? row[3] : "";
    post["author"] = row[4] ? row[4] : "";
    post["author_id"] = authorId;
    post["topic"] = row[6] ? row[6] : "";
    post["theme"] = row[7] ? row[7] : "";
    post["status"] = row[8] ? row[8] : "";
    post["likes"] = row[9] ? std::stoi(row[9]) : 0;
    post["hidden"] = hidden;
    post["created_at"] = row[11] ? row[11] : "";
    post["updated_at"] = row[12] ? row[12] : "";
    mysql_free_result(res);

    result["post"] = std::move(post);
    result["success"] = true;
    return result;
}

// 发布文章（使用预处理语句防止 SQL 注入）
crow::json::wvalue DataBase::addPost(const std::string& title, const std::string& content, const std::string& summary, const std::string& author, const std::string& topic, const std::string& theme, const std::string& status, int authorId)
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

    const char* sql = "INSERT INTO posts (title, content, summary, author, topic, theme, status, author_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)";
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
    bind[7].buffer = (void*)&authorId;

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

// 更新文章（作者与归属保持不变，由调用方先做归属校验）
crow::json::wvalue DataBase::updatePost(int id, const std::string& title, const std::string& content, const std::string& summary, const std::string& topic, const std::string& theme, const std::string& status)
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

    const char* sql = "UPDATE posts SET title=?, content=?, summary=?, topic=?, theme=?, status=? WHERE id=?";
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
    bind[3].buffer = (void*)topic.c_str();
    bind[3].buffer_length = topic.length();

    bind[4].buffer_type = MYSQL_TYPE_STRING;
    bind[4].buffer = (void*)theme.c_str();
    bind[4].buffer_length = theme.length();

    bind[5].buffer_type = MYSQL_TYPE_STRING;
    bind[5].buffer = (void*)status.c_str();
    bind[5].buffer_length = status.length();

    bind[6].buffer_type = MYSQL_TYPE_LONG;
    bind[6].buffer = (void*)&id;

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
crow::json::wvalue DataBase::deletePost(int id)
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

// 隐藏 / 取消隐藏文章（作者本人或主管理员，由调用方先做归属校验）
crow::json::wvalue DataBase::setPostHidden(int id, int hidden)
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

    const char* sql = "UPDATE posts SET hidden=? WHERE id=?";
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
        // 幂等操作：即使目标状态与当前一致（affected=0）也视为成功
        result["success"] = true;
        result["hidden"] = (hidden != 0);
        result["message"] = "操作成功";
    }
    mysql_stmt_close(stmt);
    return result;
}

// 点赞/取消点赞：likes 计数增减（delta 为 +1/-1），返回最新点赞数
crow::json::wvalue DataBase::changeLikes(int id, int delta)
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

// 获取文章归属（author_id 与作者显示名），不存在返回 false
bool DataBase::getPostAuthor(int id, int& outAuthorId, std::string& outAuthor)
{
    std::lock_guard<std::mutex> lock(mtx_);
    checkConnection();

    std::string sql = "SELECT author_id, author FROM posts WHERE id=" + std::to_string(id);
    if (mysql_query(conn_, sql.c_str()) != 0)
    {
        return false;
    }
    MYSQL_RES* res = mysql_store_result(conn_);
    if (!res) return false;
    MYSQL_ROW row = mysql_fetch_row(res);
    bool ok = (row != nullptr);
    if (ok)
    {
        outAuthorId = row[0] ? std::stoi(row[0]) : 0;
        outAuthor = row[1] ? row[1] : "";
    }
    mysql_free_result(res);
    return ok;
}

// ===== 评论 =====

// 获取某篇文章的所有评论（按时间正序；includeHidden 为 true 时包含被隐藏的评论，仅供站长）
// anonToken 为当前访客的匿名标识（可为空）：用于计算每条评论的 mine / can_edit，
// 但 owner_token 本身绝不返回给客户端，避免被他人拿来冒充作者。
crow::json::wvalue DataBase::getComments(int postId, bool includeHidden, const std::string& anonToken)
{
    std::lock_guard<std::mutex> lock(mtx_);
    checkConnection();

    crow::json::wvalue result;
    std::vector<crow::json::wvalue> comments;

    // can_edit 由 SQL 直接算：仅创建 30 分钟内允许匿名作者修改
    std::string sql = "SELECT id, post_id, parent_id, nickname, content, hidden, created_at, owner_token, "
                      "(created_at >= DATE_SUB(NOW(), INTERVAL 30 MINUTE)) AS can_edit "
                      "FROM comments WHERE post_id=" + std::to_string(postId);
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

            // row[7] 是 owner_token：只在服务端比对，不输出给客户端
            const char* owner = row[7];
            bool mine = !anonToken.empty() && owner && anonToken == owner;
            c["mine"] = mine;
            // 修改权限：自己的评论且在可编辑时间窗内；管理员走 isAdmin 判断，不受此限制
            bool canEdit = mine && row[8] && std::stoi(row[8]) != 0;
            c["can_edit"] = canEdit;

            comments.push_back(std::move(c));
        }
        mysql_free_result(res);
    }

    result["comments"] = std::move(comments);
    result["success"] = true;
    return result;
}

// 新增评论（parentId 为 0 表示顶层评论，否则为回复某条评论）
// ownerToken 为匿名作者标识（服务端下发的 HttpOnly Cookie），为空则存 NULL（无主评论）
crow::json::wvalue DataBase::addComment(int postId, int parentId, const std::string& nickname,
                                        const std::string& content, const std::string& ownerToken)
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

    // ownerToken 为空时不写该列（落库为默认 NULL，表示无主评论），
    // 这样避免使用 MYSQL_BIND::is_null 的 my_bool 类型（MySQL 8.0 已移除该类型，兼容性差）
    const char* sql = ownerToken.empty()
        ? "INSERT INTO comments (post_id, parent_id, nickname, content) VALUES (?, ?, ?, ?)"
        : "INSERT INTO comments (post_id, parent_id, nickname, content, owner_token) VALUES (?, ?, ?, ?, ?)";
    if (mysql_stmt_prepare(stmt, sql, std::strlen(sql)) != 0)
    {
        result["success"] = false;
        result["message"] = mysql_stmt_error(stmt);
        mysql_stmt_close(stmt);
        return result;
    }

    MYSQL_BIND bind[5];
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

    // 占位符只有 4 个时，mysql_stmt_bind_param 按 param_count 只读前 4 个，多传无害
    bind[4].buffer_type = MYSQL_TYPE_STRING;
    bind[4].buffer = (void*)ownerToken.c_str();
    bind[4].buffer_length = ownerToken.length();

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
crow::json::wvalue DataBase::setCommentHidden(int id, int hidden)
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

// 删除某条评论及其所有回复。
// isAdmin 为 true 时无条件删除；否则必须 ownerToken 与该评论的 owner_token 一致。
crow::json::wvalue DataBase::deleteComment(int id, const std::string& ownerToken, bool isAdmin)
{
    std::lock_guard<std::mutex> lock(mtx_);
    checkConnection();

    crow::json::wvalue result;

    if (!isAdmin)
    {
        // 匿名作者：先校验归属，避免误删他人评论
        if (ownerToken.empty())
        {
            result["success"] = false;
            result["message"] = "无法确认评论归属";
            return result;
        }

        std::string q = "SELECT owner_token FROM comments WHERE id=" + std::to_string(id);
        if (mysql_query(conn_, q.c_str()) != 0)
        {
            result["success"] = false;
            result["message"] = mysql_error(conn_);
            return result;
        }
        MYSQL_RES* res = mysql_store_result(conn_);
        if (!res)
        {
            result["success"] = false;
            result["message"] = "评论不存在";
            return result;
        }
        MYSQL_ROW row = mysql_fetch_row(res);
        if (!row)
        {
            mysql_free_result(res);
            result["success"] = false;
            result["message"] = "评论不存在";
            return result;
        }
        const char* owner = row[0];
        bool matched = owner && ownerToken == owner;
        mysql_free_result(res);

        if (!matched)
        {
            result["success"] = false;
            result["message"] = "无权删除他人评论";
            return result;
        }
    }

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

// 修改评论内容。
// isAdmin 为 true 时无条件修改；否则必须是作者本人，且限于创建后 30 分钟内（防止事后篡改历史）。
crow::json::wvalue DataBase::updateCommentContent(int id, const std::string& content,
                                                  const std::string& ownerToken, bool isAdmin)
{
    std::lock_guard<std::mutex> lock(mtx_);
    checkConnection();

    crow::json::wvalue result;

    if (!isAdmin && ownerToken.empty())
    {
        result["success"] = false;
        result["message"] = "无法确认评论归属";
        return result;
    }

    MYSQL_STMT* stmt = mysql_stmt_init(conn_);
    if (!stmt)
    {
        result["success"] = false;
        result["message"] = "mysql_stmt_init 失败";
        return result;
    }

    const char* sql = isAdmin
        ? "UPDATE comments SET content=? WHERE id=?"
        : "UPDATE comments SET content=? WHERE id=? AND owner_token=? "
          "AND created_at >= DATE_SUB(NOW(), INTERVAL 30 MINUTE)";

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
    bind[0].buffer = (void*)content.c_str();
    bind[0].buffer_length = content.length();

    bind[1].buffer_type = MYSQL_TYPE_LONG;
    bind[1].buffer = (void*)&id;

    bind[2].buffer_type = MYSQL_TYPE_STRING;
    bind[2].buffer = (void*)ownerToken.c_str();
    bind[2].buffer_length = ownerToken.length();

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
        // 影响行数为 0 有几种可能：内容没改、不是本人发的、或超过 30 分钟窗口
        result["message"] = (affected > 0) ? "修改成功" : "修改未生效：内容未变化、无权修改或已超过可修改时间";
    }
    mysql_stmt_close(stmt);
    return result;
}

// ===== 配置 =====

// 读取配置项（不存在时返回空字符串）
std::string DataBase::getSetting(const std::string& key)
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
crow::json::wvalue DataBase::setSetting(const std::string& key, const std::string& value)
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

// ===== 专栏 =====

// 获取专栏列表
crow::json::wvalue DataBase::getTopics()
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
crow::json::wvalue DataBase::addTopic(const std::string& name)
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
crow::json::wvalue DataBase::deleteTopic(int id)
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
// 注意：本方法不主动加锁，调用方需已持有 mtx_
bool DataBase::insertAdmin(const std::string& email, const std::string& password, int isMain, std::string& errMsg, int& outId)
{
    MYSQL_STMT* stmt = mysql_stmt_init(conn_);
    if (!stmt)
    {
        errMsg = "mysql_stmt_init 失败";
        return false;
    }

    std::string salt = randomHex(16);
    const char* sql = "INSERT INTO admins (email, nickname, salt, password_hash, is_main) VALUES (?, ?, ?, SHA2(CONCAT(?, ':', ?), 256), ?)";
    if (mysql_stmt_prepare(stmt, sql, std::strlen(sql)) != 0)
    {
        errMsg = mysql_stmt_error(stmt);
        mysql_stmt_close(stmt);
        return false;
    }

    MYSQL_BIND bind[6];
    std::memset(bind, 0, sizeof(bind));
    bind[0].buffer_type = MYSQL_TYPE_STRING;
    bind[0].buffer = (void*)email.c_str();
    bind[0].buffer_length = email.length();
    bind[1].buffer_type = MYSQL_TYPE_STRING;
    bind[1].buffer = (void*)email.c_str();
    bind[1].buffer_length = email.length();
    bind[2].buffer_type = MYSQL_TYPE_STRING;
    bind[2].buffer = (void*)salt.c_str();
    bind[2].buffer_length = salt.length();
    bind[3].buffer_type = MYSQL_TYPE_STRING;
    bind[3].buffer = (void*)salt.c_str();
    bind[3].buffer_length = salt.length();
    bind[4].buffer_type = MYSQL_TYPE_STRING;
    bind[4].buffer = (void*)password.c_str();
    bind[4].buffer_length = password.length();
    bind[5].buffer_type = MYSQL_TYPE_LONG;
    bind[5].buffer = (void*)&isMain;
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

// 首次初始化时创建主管理员账号：随机生成密码并打印一次
void DataBase::seedMainAdmin()
{
    const std::string email = "admin@localhost";
    std::string password = randomHex(12);
    std::string err;
    int id = 0;
    if (!insertAdmin(email, password, 1, err, id))
    {
        throw std::runtime_error("创建主管理员失败：" + err);
    }
    std::cout << std::endl;
    std::cout << "========================================" << std::endl;
    std::cout << "  已创建初始管理员账号（仅显示这一次）" << std::endl;
    std::cout << "  邮箱: " << email << std::endl;
    std::cout << "  密码: " << password << std::endl;
    std::cout << "========================================" << std::endl;
    std::cout << std::endl;
}

// 获取主管理员（is_main=1）的 id 与昵称，不存在返回 false
// 说明：仅在 initTable（单线程构造）或已持有 mtx_ 锁的调用中执行，不加锁
bool DataBase::getMainAdmin(int& outId, std::string& outNickname)
{
    if (mysql_query(conn_, "SELECT id, nickname FROM admins WHERE is_main=1 ORDER BY id ASC LIMIT 1") != 0)
    {
        return false;
    }
    MYSQL_RES* res = mysql_store_result(conn_);
    if (!res) return false;
    MYSQL_ROW row = mysql_fetch_row(res);
    bool ok = (row != nullptr);
    if (ok)
    {
        outId = std::stoi(row[0]);
        outNickname = row[1] ? row[1] : "";
    }
    mysql_free_result(res);
    return ok;
}

// 历史文章（author_id=0）归到主管理员，并把作者显示名同步为主管理员昵称
void DataBase::backfillLegacyPosts()
{
    int mainId = 0;
    std::string mainNick;
    if (!getMainAdmin(mainId, mainNick))
    {
        return;
    }

    std::vector<char> nickEsc(mainNick.length() * 2 + 1);
    mysql_real_escape_string(conn_, nickEsc.data(), mainNick.c_str(), static_cast<unsigned long>(mainNick.length()));
    std::string sql = "UPDATE posts SET author_id=" + std::to_string(mainId) +
        ", author='" + std::string(nickEsc.data()) + "' WHERE author_id=0";
    if (mysql_query(conn_, sql.c_str()) != 0)
    {
        throw std::runtime_error(std::string("历史文章归属主管理员失败：") + mysql_error(conn_));
    }
}

// 新增普通管理员
crow::json::wvalue DataBase::addAdmin(const std::string& email, const std::string& password)
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
crow::json::wvalue DataBase::getAdmins()
{
    std::lock_guard<std::mutex> lock(mtx_);
    checkConnection();

    crow::json::wvalue result;
    std::vector<crow::json::wvalue> admins;

    const char* sql = "SELECT id, email, nickname, avatar, is_main, created_at FROM admins ORDER BY is_main DESC, id ASC";
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
            a["nickname"] = row[2] ? row[2] : "";
            a["avatar"] = row[3] ? row[3] : "";
            a["is_main"] = (row[4] && std::stoi(row[4]) != 0);
            a["created_at"] = row[5] ? row[5] : "";
            admins.push_back(std::move(a));
        }
        mysql_free_result(res);
    }

    result["admins"] = std::move(admins);
    result["success"] = true;
    return result;
}

// 删除管理员（主管理员 is_main=1 不可删除，SQL 层再兜底）
crow::json::wvalue DataBase::deleteAdmin(int id)
{
    std::lock_guard<std::mutex> lock(mtx_);
    checkConnection();

    crow::json::wvalue result;

    // 删除前把其名下文章转给主管理员，避免出现无主文章
    {
        int mainId = 0;
        std::string mainNick;
        if (getMainAdmin(mainId, mainNick) && mainId != id)
        {
            std::vector<char> nickEsc(mainNick.length() * 2 + 1);
            mysql_real_escape_string(conn_, nickEsc.data(), mainNick.c_str(), static_cast<unsigned long>(mainNick.length()));
            std::string upd = "UPDATE posts SET author_id=" + std::to_string(mainId) +
                ", author='" + std::string(nickEsc.data()) + "' WHERE author_id=" + std::to_string(id);
            mysql_query(conn_, upd.c_str());
        }
    }

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

// 获取管理员昵称（昵称为空时回退到邮箱）
std::string DataBase::getAdminNickname(int id)
{
    std::lock_guard<std::mutex> lock(mtx_);
    checkConnection();

    std::string sql = "SELECT nickname, email FROM admins WHERE id=" + std::to_string(id);
    if (mysql_query(conn_, sql.c_str()) != 0)
    {
        return "";
    }
    std::string nick;
    MYSQL_RES* res = mysql_store_result(conn_);
    if (res)
    {
        MYSQL_ROW row = mysql_fetch_row(res);
        if (row)
        {
            nick = (row[0] && row[0][0]) ? row[0] : (row[1] ? row[1] : "");
        }
        mysql_free_result(res);
    }
    return nick;
}

// 获取单个管理员的资料（邮箱、昵称、头像、是否主管理员）
bool DataBase::getAdminProfile(int id, std::string& outEmail, std::string& outNickname, std::string& outAvatar, bool& outIsMain)
{
    std::lock_guard<std::mutex> lock(mtx_);
    checkConnection();

    std::string sql = "SELECT email, nickname, avatar, is_main FROM admins WHERE id=" + std::to_string(id);
    if (mysql_query(conn_, sql.c_str()) != 0)
    {
        return false;
    }
    MYSQL_RES* res = mysql_store_result(conn_);
    if (!res) return false;
    MYSQL_ROW row = mysql_fetch_row(res);
    bool ok = (row != nullptr);
    if (ok)
    {
        outEmail = row[0] ? row[0] : "";
        outNickname = row[1] ? row[1] : "";
        outAvatar = row[2] ? row[2] : "";
        outIsMain = (row[3] && std::stoi(row[3]) != 0);
    }
    mysql_free_result(res);
    return ok;
}

// 更新管理员自己的昵称与头像，并把其名下文章的作者名同步为新昵称
crow::json::wvalue DataBase::updateProfile(int adminId, const std::string& nickname, const std::string& avatar)
{
    std::lock_guard<std::mutex> lock(mtx_);
    checkConnection();

    crow::json::wvalue result;
    std::string nick = trim(nickname);
    if (nick.empty())
    {
        result["success"] = false;
        result["message"] = "昵称不能为空";
        return result;
    }
    if (nick.length() > 100) nick = nick.substr(0, 100);

    std::string av = trim(avatar);
    if (av.length() > 500) av = av.substr(0, 500);
    if (!av.empty() && av.rfind("/uploads/", 0) != 0 &&
        av.rfind("http://", 0) != 0 && av.rfind("https://", 0) != 0)
    {
        result["success"] = false;
        result["message"] = "头像地址无效";
        return result;
    }

    MYSQL_STMT* stmt = mysql_stmt_init(conn_);
    if (!stmt)
    {
        result["success"] = false;
        result["message"] = "mysql_stmt_init 失败";
        return result;
    }
    const char* sql = "UPDATE admins SET nickname=?, avatar=? WHERE id=?";
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
    bind[0].buffer = (void*)nick.c_str();
    bind[0].buffer_length = nick.length();
    bind[1].buffer_type = MYSQL_TYPE_STRING;
    bind[1].buffer = (void*)av.c_str();
    bind[1].buffer_length = av.length();
    bind[2].buffer_type = MYSQL_TYPE_LONG;
    bind[2].buffer = (void*)&adminId;
    mysql_stmt_bind_param(stmt, bind);

    if (mysql_stmt_execute(stmt) != 0)
    {
        result["success"] = false;
        result["message"] = mysql_stmt_error(stmt);
        mysql_stmt_close(stmt);
        return result;
    }
    mysql_stmt_close(stmt);

    // 同步该管理员名下所有文章的作者名
    MYSQL_STMT* stmt2 = mysql_stmt_init(conn_);
    if (stmt2)
    {
        const char* sql2 = "UPDATE posts SET author=? WHERE author_id=?";
        if (mysql_stmt_prepare(stmt2, sql2, std::strlen(sql2)) == 0)
        {
            MYSQL_BIND b2[2];
            std::memset(b2, 0, sizeof(b2));
            b2[0].buffer_type = MYSQL_TYPE_STRING;
            b2[0].buffer = (void*)nick.c_str();
            b2[0].buffer_length = nick.length();
            b2[1].buffer_type = MYSQL_TYPE_LONG;
            b2[1].buffer = (void*)&adminId;
            mysql_stmt_bind_param(stmt2, b2);
            mysql_stmt_execute(stmt2);
        }
        mysql_stmt_close(stmt2);
    }

    result["success"] = true;
    result["nickname"] = nick;
    result["message"] = "资料已更新";
    return result;
}

// 登录校验：邮箱 + 密码匹配则返回 true，并通过出参返回 id / is_main
bool DataBase::loginAdmin(const std::string& email, const std::string& password, int& outId, bool& outIsMain, std::string& errMsg)
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

// 修改管理员密码：校验旧密码正确后，重新生成盐并更新哈希
bool DataBase::changePassword(int adminId, const std::string& oldPassword, const std::string& newPassword, std::string& errMsg)
{
    std::lock_guard<std::mutex> lock(mtx_);
    checkConnection();

    if (oldPassword.empty())
    {
        errMsg = "请输入旧密码";
        return false;
    }
    if (newPassword.length() < 6)
    {
        errMsg = "新密码至少 6 位";
        return false;
    }

    std::string salt = randomHex(16);

    MYSQL_STMT* stmt = mysql_stmt_init(conn_);
    if (!stmt)
    {
        errMsg = "mysql_stmt_init 失败";
        return false;
    }

    // 仅当旧密码匹配时才更新（WHERE 里校验 SHA2(salt:旧密码, 256)）
    const char* sql = "UPDATE admins SET salt=?, password_hash=SHA2(CONCAT(?, ':', ?), 256) "
                      "WHERE id=? AND password_hash=SHA2(CONCAT(salt, ':', ?), 256)";
    if (mysql_stmt_prepare(stmt, sql, std::strlen(sql)) != 0)
    {
        errMsg = mysql_stmt_error(stmt);
        mysql_stmt_close(stmt);
        return false;
    }

    MYSQL_BIND bind[5];
    std::memset(bind, 0, sizeof(bind));
    bind[0].buffer_type = MYSQL_TYPE_STRING;
    bind[0].buffer = (void*)salt.c_str();
    bind[0].buffer_length = salt.length();
    bind[1].buffer_type = MYSQL_TYPE_STRING;
    bind[1].buffer = (void*)salt.c_str();
    bind[1].buffer_length = salt.length();
    bind[2].buffer_type = MYSQL_TYPE_STRING;
    bind[2].buffer = (void*)newPassword.c_str();
    bind[2].buffer_length = newPassword.length();
    bind[3].buffer_type = MYSQL_TYPE_LONG;
    bind[3].buffer = (void*)&adminId;
    bind[4].buffer_type = MYSQL_TYPE_STRING;
    bind[4].buffer = (void*)oldPassword.c_str();
    bind[4].buffer_length = oldPassword.length();
    mysql_stmt_bind_param(stmt, bind);

    if (mysql_stmt_execute(stmt) != 0)
    {
        errMsg = mysql_stmt_error(stmt);
        mysql_stmt_close(stmt);
        return false;
    }

    my_ulonglong affected = mysql_stmt_affected_rows(stmt);
    mysql_stmt_close(stmt);

    if (affected == 0)
    {
        errMsg = "旧密码错误";
        return false;
    }

    return true;
}

// ===== 每日一题 =====

// 确保某天的题目已生成，返回题目 ID（0 表示题库中没有已发布的题目）。
// 调用方必须已持有 mtx_：本函数不再加锁，也不调用会加锁的 getSetting/setSetting。
int DataBase::ensureDailyQuestion(const std::string& date)
{
    // 1. 当天已有排期，直接用
    {
        std::string sql = "SELECT question_id FROM daily_questions WHERE d=" + sqlQuote(conn_, date) + " LIMIT 1";
        if (mysql_query(conn_, sql.c_str()) == 0)
        {
            MYSQL_RES* res = mysql_store_result(conn_);
            if (res)
            {
                MYSQL_ROW row = mysql_fetch_row(res);
                int id = (row && row[0]) ? std::atoi(row[0]) : 0;
                mysql_free_result(res);
                if (id > 0) return id;
            }
        }
    }

    // 2. 取「有已发布题目的分类」，按名称排序保证顺序稳定
    std::vector<std::string> categories;
    if (mysql_query(conn_, "SELECT DISTINCT category FROM questions WHERE status=1 ORDER BY category") == 0)
    {
        MYSQL_RES* res = mysql_store_result(conn_);
        if (res)
        {
            MYSQL_ROW row;
            while ((row = mysql_fetch_row(res)))
            {
                if (row[0] && row[0][0]) categories.push_back(row[0]);
            }
            mysql_free_result(res);
        }
    }
    if (categories.empty()) return 0;

    // 3. 基准日：首次运行以当天为基准。之后用「日期差」而不是行数来算序号，
    //    这样即使某天没人访问，顺序也不会错位（行数法会因为缺天而少前进）。
    std::string base;
    if (mysql_query(conn_, "SELECT v FROM settings WHERE k='daily_base_date'") == 0)
    {
        MYSQL_RES* res = mysql_store_result(conn_);
        if (res)
        {
            MYSQL_ROW row = mysql_fetch_row(res);
            if (row && row[0]) base = row[0];
            mysql_free_result(res);
        }
    }
    if (base.empty())
    {
        base = date;
        std::string ins = "INSERT INTO settings (k, v) VALUES ('daily_base_date', " + sqlQuote(conn_, base) +
                          ") ON DUPLICATE KEY UPDATE v=VALUES(v)";
        mysql_query(conn_, ins.c_str());
    }

    long dayIndex = daysFromDate(date) - daysFromDate(base);
    if (dayIndex < 0) dayIndex = 0;

    // 4. 分类轮转 + 类内轮转：dayIndex 决定用哪个分类，dayIndex/n 决定该类里的第几题
    const long n = static_cast<long>(categories.size());
    const std::string category = categories[static_cast<size_t>(dayIndex % n)];

    std::vector<int> pool;
    {
        std::string sql = "SELECT id FROM questions WHERE status=1 AND category=" + sqlQuote(conn_, category) +
                          " ORDER BY id";
        if (mysql_query(conn_, sql.c_str()) == 0)
        {
            MYSQL_RES* res = mysql_store_result(conn_);
            if (res)
            {
                MYSQL_ROW row;
                while ((row = mysql_fetch_row(res)))
                {
                    if (row[0]) pool.push_back(std::atoi(row[0]));
                }
                mysql_free_result(res);
            }
        }
    }
    if (pool.empty()) return 0;

    const int picked = pool[static_cast<size_t>((dayIndex / n) % static_cast<long>(pool.size()))];

    // 5. INSERT IGNORE：app 是多线程的，同一秒可能有两个请求同时进来，只让先到的写入生效
    std::string ins = "INSERT IGNORE INTO daily_questions (d, question_id) VALUES (" + sqlQuote(conn_, date) + ", " +
                      std::to_string(picked) + ")";
    mysql_query(conn_, ins.c_str());

    // 6. 重新读一次：并发时以先写入的那条为准，保证所有客户端看到同一题
    std::string back = "SELECT question_id FROM daily_questions WHERE d=" + sqlQuote(conn_, date) + " LIMIT 1";
    if (mysql_query(conn_, back.c_str()) == 0)
    {
        MYSQL_RES* res = mysql_store_result(conn_);
        if (res)
        {
            MYSQL_ROW row = mysql_fetch_row(res);
            int id = (row && row[0]) ? std::atoi(row[0]) : picked;
            mysql_free_result(res);
            return id;
        }
    }
    return picked;
}

// 连续打卡天数：今天已答则从今天往前数，今天没答则从昨天往前数（今天还没结束，不算断）
int DataBase::getDailyStreak(const std::string& ownerToken)
{
    if (ownerToken.empty()) return 0;

    std::vector<std::string> dates;
    std::string sql = "SELECT d FROM daily_seen WHERE owner_token=" + sqlQuote(conn_, ownerToken) +
                      " ORDER BY d DESC LIMIT 400";
    if (mysql_query(conn_, sql.c_str()) != 0) return 0;

    MYSQL_RES* res = mysql_store_result(conn_);
    if (!res) return 0;
    MYSQL_ROW row;
    while ((row = mysql_fetch_row(res)))
    {
        if (row[0]) dates.push_back(row[0]);
    }
    mysql_free_result(res);
    if (dates.empty()) return 0;

    const long todayNum = daysFromDate(todayStr());
    long expected = 0;
    if (daysFromDate(dates[0]) == todayNum)
    {
        expected = todayNum;
    }
    else if (daysFromDate(dates[0]) == todayNum - 1)
    {
        expected = todayNum - 1;
    }
    else
    {
        return 0; // 已经断档
    }

    int streak = 0;
    for (size_t i = 0; i < dates.size(); ++i)
    {
        if (daysFromDate(dates[i]) != expected - static_cast<long>(i)) break;
        ++streak;
    }
    return streak;
}

// 取今天的题目（不含答案）
crow::json::wvalue DataBase::getDailyQuestion(const std::string& anonToken)
{
    std::lock_guard<std::mutex> lock(mtx_);
    checkConnection();

    const std::string date = todayStr();
    crow::json::wvalue result;
    result["success"] = true;
    result["available"] = false;
    result["answered"] = false;
    result["streak"] = 0;
    result["date"] = date;

    const int qid = ensureDailyQuestion(date);
    if (qid <= 0)
    {
        result["message"] = "题库里还没有已发布的题目";
        return result;
    }

    std::string sql = "SELECT id, category, tags, difficulty, question FROM questions WHERE id=" + std::to_string(qid);
    if (mysql_query(conn_, sql.c_str()) != 0) return result;

    MYSQL_RES* res = mysql_store_result(conn_);
    if (!res) return result;
    MYSQL_ROW row = mysql_fetch_row(res);
    if (!row)
    {
        mysql_free_result(res);
        return result;
    }
    result["id"] = row[0] ? std::atoi(row[0]) : 0;
    result["category"] = row[1] ? row[1] : "";
    result["tags"] = row[2] ? row[2] : "";
    result["difficulty"] = row[3] ? std::atoi(row[3]) : 2;
    result["question"] = row[4] ? row[4] : "";
    result["available"] = true;
    mysql_free_result(res);

    if (!anonToken.empty())
    {
        std::string seen = "SELECT 1 FROM daily_seen WHERE d=" + sqlQuote(conn_, date) +
                           " AND owner_token=" + sqlQuote(conn_, anonToken) + " LIMIT 1";
        if (mysql_query(conn_, seen.c_str()) == 0)
        {
            MYSQL_RES* r2 = mysql_store_result(conn_);
            if (r2)
            {
                MYSQL_ROW r = mysql_fetch_row(r2);
                result["answered"] = (r != nullptr);
                mysql_free_result(r2);
            }
        }
        result["streak"] = getDailyStreak(anonToken);
    }
    return result;
}

// 取题目答案；anonToken 非空时顺带记录「今天看过答案」
crow::json::wvalue DataBase::getDailyAnswer(int questionId, const std::string& anonToken)
{
    std::lock_guard<std::mutex> lock(mtx_);
    checkConnection();

    crow::json::wvalue result;
    result["success"] = false;
    result["streak"] = 0;

    std::string sql = "SELECT id, category, tags, difficulty, question, answer FROM questions WHERE id=" +
                      std::to_string(questionId) + " AND status=1";
    if (mysql_query(conn_, sql.c_str()) != 0)
    {
        result["message"] = "查询失败";
        return result;
    }

    MYSQL_RES* res = mysql_store_result(conn_);
    if (!res)
    {
        result["message"] = "查询失败";
        return result;
    }
    MYSQL_ROW row = mysql_fetch_row(res);
    if (!row)
    {
        mysql_free_result(res);
        result["message"] = "题目不存在或尚未发布";
        return result;
    }
    result["success"] = true;
    result["id"] = row[0] ? std::atoi(row[0]) : 0;
    result["category"] = row[1] ? row[1] : "";
    result["tags"] = row[2] ? row[2] : "";
    result["difficulty"] = row[3] ? std::atoi(row[3]) : 2;
    result["question"] = row[4] ? row[4] : "";
    result["answer"] = row[5] ? row[5] : "";
    mysql_free_result(res);

    if (!anonToken.empty())
    {
        const std::string date = todayStr();
        std::string ins = "INSERT IGNORE INTO daily_seen (d, owner_token, question_id) VALUES (" +
                          sqlQuote(conn_, date) + ", " + sqlQuote(conn_, anonToken) + ", " +
                          std::to_string(questionId) + ")";
        mysql_query(conn_, ins.c_str());
        result["streak"] = getDailyStreak(anonToken);
    }
    return result;
}

// 历史排期（按日期倒序分页），不含答案
crow::json::wvalue DataBase::getDailyHistory(int page, int pageSize)
{
    std::lock_guard<std::mutex> lock(mtx_);
    checkConnection();

    if (page < 1) page = 1;
    if (pageSize < 1) pageSize = 10;
    if (pageSize > 50) pageSize = 50;
    const int offset = (page - 1) * pageSize;

    crow::json::wvalue result;
    std::vector<crow::json::wvalue> items;

    std::string sql = "SELECT dq.d, dq.question_id, q.category, q.difficulty, q.question "
                      "FROM daily_questions dq LEFT JOIN questions q ON q.id=dq.question_id "
                      "ORDER BY dq.d DESC LIMIT " + std::to_string(pageSize) + " OFFSET " + std::to_string(offset);
    if (mysql_query(conn_, sql.c_str()) == 0)
    {
        MYSQL_RES* res = mysql_store_result(conn_);
        if (res)
        {
            MYSQL_ROW row;
            while ((row = mysql_fetch_row(res)))
            {
                crow::json::wvalue item;
                item["date"] = row[0] ? row[0] : "";
                item["id"] = (row[1] && row[1][0]) ? std::atoi(row[1]) : 0;
                item["category"] = row[2] ? row[2] : "";
                item["difficulty"] = row[3] ? std::atoi(row[3]) : 2;
                item["question"] = row[4] ? row[4] : "";
                items.push_back(std::move(item));
            }
            mysql_free_result(res);
        }
    }

    long total = 0;
    if (mysql_query(conn_, "SELECT COUNT(*) FROM daily_questions") == 0)
    {
        MYSQL_RES* res = mysql_store_result(conn_);
        if (res)
        {
            MYSQL_ROW row = mysql_fetch_row(res);
            if (row && row[0]) total = std::strtol(row[0], nullptr, 10);
            mysql_free_result(res);
        }
    }

    const bool hasMore = (static_cast<int>(items.size()) == pageSize);
    result["questions"] = std::move(items);
    result["total"] = static_cast<int>(total);
    result["page"] = page;
    result["hasMore"] = hasMore;
    result["success"] = true;
    return result;
}

// 随机换一题（category 为空表示不限分类），不含答案
crow::json::wvalue DataBase::getRandomQuestion(const std::string& category)
{
    std::lock_guard<std::mutex> lock(mtx_);
    checkConnection();

    crow::json::wvalue result;
    result["success"] = false;

    std::string sql = "SELECT id, category, tags, difficulty, question FROM questions WHERE status=1";
    if (!category.empty()) sql += " AND category=" + sqlQuote(conn_, category);
    sql += " ORDER BY RAND() LIMIT 1";

    if (mysql_query(conn_, sql.c_str()) != 0)
    {
        result["message"] = "查询失败";
        return result;
    }
    MYSQL_RES* res = mysql_store_result(conn_);
    if (!res)
    {
        result["message"] = "查询失败";
        return result;
    }
    MYSQL_ROW row = mysql_fetch_row(res);
    if (!row)
    {
        mysql_free_result(res);
        result["message"] = "题库里还没有已发布的题目";
        return result;
    }
    result["success"] = true;
    result["id"] = row[0] ? std::atoi(row[0]) : 0;
    result["category"] = row[1] ? row[1] : "";
    result["tags"] = row[2] ? row[2] : "";
    result["difficulty"] = row[3] ? std::atoi(row[3]) : 2;
    result["question"] = row[4] ? row[4] : "";
    mysql_free_result(res);
    return result;
}

// 题库浏览（不含答案），附各分类数量；includeDrafts 为 true 时含草稿（仅站长）
crow::json::wvalue DataBase::getQuestions(const std::string& category, int page, int pageSize, bool includeDrafts)
{
    std::lock_guard<std::mutex> lock(mtx_);
    checkConnection();

    if (page < 1) page = 1;
    if (pageSize < 1) pageSize = 10;
    if (pageSize > 50) pageSize = 50;
    const int offset = (page - 1) * pageSize;

    const std::string statusWhere = includeDrafts ? "1=1" : "status=1";

    crow::json::wvalue result;
    std::vector<crow::json::wvalue> items;

    std::string sql = "SELECT id, category, tags, difficulty, question, status FROM questions WHERE " + statusWhere;
    if (!category.empty()) sql += " AND category=" + sqlQuote(conn_, category);
    sql += " ORDER BY id DESC LIMIT " + std::to_string(pageSize) + " OFFSET " + std::to_string(offset);

    if (mysql_query(conn_, sql.c_str()) == 0)
    {
        MYSQL_RES* res = mysql_store_result(conn_);
        if (res)
        {
            MYSQL_ROW row;
            while ((row = mysql_fetch_row(res)))
            {
                crow::json::wvalue item;
                item["id"] = row[0] ? std::atoi(row[0]) : 0;
                item["category"] = row[1] ? row[1] : "";
                item["tags"] = row[2] ? row[2] : "";
                item["difficulty"] = row[3] ? std::atoi(row[3]) : 2;
                item["question"] = row[4] ? row[4] : "";
                item["status"] = row[5] ? std::atoi(row[5]) : 0;
                items.push_back(std::move(item));
            }
            mysql_free_result(res);
        }
    }

    // 各分类数量（只统计已发布，供前端筛选条使用）
    std::vector<crow::json::wvalue> categories;
    if (mysql_query(conn_, "SELECT category, COUNT(*) FROM questions WHERE status=1 GROUP BY category ORDER BY category") == 0)
    {
        MYSQL_RES* res = mysql_store_result(conn_);
        if (res)
        {
            MYSQL_ROW row;
            while ((row = mysql_fetch_row(res)))
            {
                crow::json::wvalue c;
                c["name"] = row[0] ? row[0] : "";
                c["count"] = (row[1]) ? std::atoi(row[1]) : 0;
                categories.push_back(std::move(c));
            }
            mysql_free_result(res);
        }
    }

    long total = 0;
    std::string countSql = "SELECT COUNT(*) FROM questions WHERE " + statusWhere;
    if (!category.empty()) countSql += " AND category=" + sqlQuote(conn_, category);
    if (mysql_query(conn_, countSql.c_str()) == 0)
    {
        MYSQL_RES* res = mysql_store_result(conn_);
        if (res)
        {
            MYSQL_ROW row = mysql_fetch_row(res);
            if (row && row[0]) total = std::strtol(row[0], nullptr, 10);
            mysql_free_result(res);
        }
    }

    const bool hasMore = (static_cast<int>(items.size()) == pageSize);
    result["questions"] = std::move(items);
    result["categories"] = std::move(categories);
    result["total"] = static_cast<int>(total);
    result["page"] = page;
    result["hasMore"] = hasMore;
    result["success"] = true;
    return result;
}

// 单题详情（含答案，供站长编辑时回填）
crow::json::wvalue DataBase::getQuestionById(int id)
{
    std::lock_guard<std::mutex> lock(mtx_);
    checkConnection();

    crow::json::wvalue result;
    result["success"] = false;

    std::string sql = "SELECT id, category, tags, difficulty, question, answer, status FROM questions WHERE id=" +
                      std::to_string(id);
    if (mysql_query(conn_, sql.c_str()) != 0)
    {
        result["message"] = "查询失败";
        return result;
    }
    MYSQL_RES* res = mysql_store_result(conn_);
    if (!res)
    {
        result["message"] = "查询失败";
        return result;
    }
    MYSQL_ROW row = mysql_fetch_row(res);
    if (!row)
    {
        mysql_free_result(res);
        result["message"] = "题目不存在";
        return result;
    }
    result["success"] = true;
    result["id"] = row[0] ? std::atoi(row[0]) : 0;
    result["category"] = row[1] ? row[1] : "";
    result["tags"] = row[2] ? row[2] : "";
    result["difficulty"] = row[3] ? std::atoi(row[3]) : 2;
    result["question"] = row[4] ? row[4] : "";
    result["answer"] = row[5] ? row[5] : "";
    result["status"] = row[6] ? std::atoi(row[6]) : 0;
    mysql_free_result(res);
    return result;
}

// 新增题目（仅主管理员，权限由路由层校验）
crow::json::wvalue DataBase::addQuestion(const std::string& category, const std::string& tags, int difficulty,
                                         const std::string& question, const std::string& answer, int status)
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

    const char* sql = "INSERT INTO questions (category, tags, difficulty, question, answer, status) VALUES (?, ?, ?, ?, ?, ?)";
    if (mysql_stmt_prepare(stmt, sql, std::strlen(sql)) != 0)
    {
        result["success"] = false;
        result["message"] = mysql_stmt_error(stmt);
        mysql_stmt_close(stmt);
        return result;
    }

    int diff = difficulty;
    int st = status;
    MYSQL_BIND bind[6];
    std::memset(bind, 0, sizeof(bind));
    bind[0].buffer_type = MYSQL_TYPE_STRING;
    bind[0].buffer = (void*)category.c_str();
    bind[0].buffer_length = category.length();
    bind[1].buffer_type = MYSQL_TYPE_STRING;
    bind[1].buffer = (void*)tags.c_str();
    bind[1].buffer_length = tags.length();
    bind[2].buffer_type = MYSQL_TYPE_LONG;
    bind[2].buffer = (void*)&diff;
    bind[3].buffer_type = MYSQL_TYPE_STRING;
    bind[3].buffer = (void*)question.c_str();
    bind[3].buffer_length = question.length();
    bind[4].buffer_type = MYSQL_TYPE_STRING;
    bind[4].buffer = (void*)answer.c_str();
    bind[4].buffer_length = answer.length();
    bind[5].buffer_type = MYSQL_TYPE_LONG;
    bind[5].buffer = (void*)&st;
    mysql_stmt_bind_param(stmt, bind);

    if (mysql_stmt_execute(stmt) == 0)
    {
        result["success"] = true;
        result["id"] = static_cast<int>(mysql_stmt_insert_id(stmt));
        result["message"] = "已添加";
    }
    else
    {
        result["success"] = false;
        result["message"] = mysql_stmt_error(stmt);
    }
    mysql_stmt_close(stmt);
    return result;
}

// 修改题目（仅主管理员）
crow::json::wvalue DataBase::updateQuestion(int id, const std::string& category, const std::string& tags,
                                            int difficulty, const std::string& question,
                                            const std::string& answer, int status)
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

    const char* sql = "UPDATE questions SET category=?, tags=?, difficulty=?, question=?, answer=?, status=? WHERE id=?";
    if (mysql_stmt_prepare(stmt, sql, std::strlen(sql)) != 0)
    {
        result["success"] = false;
        result["message"] = mysql_stmt_error(stmt);
        mysql_stmt_close(stmt);
        return result;
    }

    int diff = difficulty;
    int st = status;
    int qid = id;
    MYSQL_BIND bind[7];
    std::memset(bind, 0, sizeof(bind));
    bind[0].buffer_type = MYSQL_TYPE_STRING;
    bind[0].buffer = (void*)category.c_str();
    bind[0].buffer_length = category.length();
    bind[1].buffer_type = MYSQL_TYPE_STRING;
    bind[1].buffer = (void*)tags.c_str();
    bind[1].buffer_length = tags.length();
    bind[2].buffer_type = MYSQL_TYPE_LONG;
    bind[2].buffer = (void*)&diff;
    bind[3].buffer_type = MYSQL_TYPE_STRING;
    bind[3].buffer = (void*)question.c_str();
    bind[3].buffer_length = question.length();
    bind[4].buffer_type = MYSQL_TYPE_STRING;
    bind[4].buffer = (void*)answer.c_str();
    bind[4].buffer_length = answer.length();
    bind[5].buffer_type = MYSQL_TYPE_LONG;
    bind[5].buffer = (void*)&st;
    bind[6].buffer_type = MYSQL_TYPE_LONG;
    bind[6].buffer = (void*)&qid;
    mysql_stmt_bind_param(stmt, bind);

    if (mysql_stmt_execute(stmt) == 0)
    {
        result["success"] = true;
        result["message"] = "已保存";
    }
    else
    {
        result["success"] = false;
        result["message"] = mysql_stmt_error(stmt);
    }
    mysql_stmt_close(stmt);
    return result;
}

// 删除题目（仅主管理员）。已在每日排期里的记录会保留日期，题目内容回退为空
crow::json::wvalue DataBase::deleteQuestion(int id)
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

    const char* sql = "DELETE FROM questions WHERE id=?";
    if (mysql_stmt_prepare(stmt, sql, std::strlen(sql)) != 0)
    {
        result["success"] = false;
        result["message"] = mysql_stmt_error(stmt);
        mysql_stmt_close(stmt);
        return result;
    }

    int qid = id;
    MYSQL_BIND bind[1];
    std::memset(bind, 0, sizeof(bind));
    bind[0].buffer_type = MYSQL_TYPE_LONG;
    bind[0].buffer = (void*)&qid;
    mysql_stmt_bind_param(stmt, bind);

    if (mysql_stmt_execute(stmt) == 0)
    {
        result["success"] = true;
        result["message"] = "已删除";
    }
    else
    {
        result["success"] = false;
        result["message"] = mysql_stmt_error(stmt);
    }
    mysql_stmt_close(stmt);
    return result;
}
