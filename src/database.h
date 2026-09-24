#pragma once

#include <mutex>
#include <string>
#include <vector>

#include <mysql/mysql.h>

#include "crow.h"

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
             const std::string db, unsigned int port = 3306);

    // 析构函数 - 释放连接
    ~DataBase();

    // 建立 MySQL 连接
    void connect();

    // 检查连接是否存活，如果断开则重连
    void checkConnection();

    // 初始化数据表
    void initTable();

    // ===== 文章 =====
    crow::json::wvalue getPosts(const std::string& status);
    crow::json::wvalue getHiddenPosts(bool isMain, int adminId);
    crow::json::wvalue getPostById(int id, bool isMain, int adminId);
    crow::json::wvalue addPost(const std::string& title, const std::string& content, const std::string& summary, const std::string& author, const std::string& topic, const std::string& theme, const std::string& status, int authorId);
    crow::json::wvalue updatePost(int id, const std::string& title, const std::string& content, const std::string& summary, const std::string& topic, const std::string& theme, const std::string& status);
    crow::json::wvalue deletePost(int id);
    crow::json::wvalue setPostHidden(int id, int hidden);
    crow::json::wvalue changeLikes(int id, int delta);
    bool getPostAuthor(int id, int& outAuthorId, std::string& outAuthor);

    // ===== 评论 =====
    crow::json::wvalue getComments(int postId, bool includeHidden);
    crow::json::wvalue addComment(int postId, int parentId, const std::string& nickname, const std::string& content);
    crow::json::wvalue setCommentHidden(int id, int hidden);
    crow::json::wvalue deleteComment(int id);

    // ===== 配置 =====
    std::string getSetting(const std::string& key);
    crow::json::wvalue setSetting(const std::string& key, const std::string& value);

    // ===== 专栏 =====
    crow::json::wvalue getTopics();
    crow::json::wvalue addTopic(const std::string& name);
    crow::json::wvalue deleteTopic(int id);

    // ===== 管理员账号 =====
    crow::json::wvalue addAdmin(const std::string& email, const std::string& password);
    crow::json::wvalue getAdmins();
    crow::json::wvalue deleteAdmin(int id);
    crow::json::wvalue updateProfile(int adminId, const std::string& nickname, const std::string& avatar);
    std::string getAdminNickname(int id);
    bool getAdminProfile(int id, std::string& outEmail, std::string& outNickname, std::string& outAvatar, bool& outIsMain);
    bool loginAdmin(const std::string& email, const std::string& password, int& outId, bool& outIsMain, std::string& errMsg);

private:
    // 判断表中某列是否存在
    bool columnExists(const std::string& table, const std::string& column);
    // 插入管理员记录（不主动加锁，调用方需已持有 mtx_）
    bool insertAdmin(const std::string& email, const std::string& password, int isMain, std::string& errMsg, int& outId);
    // 首次初始化时创建主管理员账号
    void seedMainAdmin();
    // 获取主管理员（is_main=1）的 id 与昵称
    bool getMainAdmin(int& outId, std::string& outNickname);
    // 历史文章（author_id=0）归到主管理员
    void backfillLegacyPosts();
};
