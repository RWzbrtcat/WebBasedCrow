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
    // anonToken：当前访客的匿名标识（可为空），用于计算每条评论的 mine / can_edit，token 本身不下发
    crow::json::wvalue getComments(int postId, bool includeHidden, const std::string& anonToken);
    // ownerToken：匿名作者标识，为空表示该评论无主
    crow::json::wvalue addComment(int postId, int parentId, const std::string& nickname,
                                  const std::string& content, const std::string& ownerToken);
    crow::json::wvalue setCommentHidden(int id, int hidden);
    // isAdmin 为 true 时无条件操作；否则校验 ownerToken 归属（修改还受 30 分钟时间窗限制）
    crow::json::wvalue deleteComment(int id, const std::string& ownerToken, bool isAdmin);
    crow::json::wvalue updateCommentContent(int id, const std::string& content,
                                            const std::string& ownerToken, bool isAdmin);

    // ===== 每日一题 =====
    // 取今天的题目：不存在时按「日期索引 + 分类轮转」懒生成并落库（无需定时任务）。
    // anonToken 非空时附带该访客是否已看答案与连续打卡天数；答案不在此接口返回。
    crow::json::wvalue getDailyQuestion(const std::string& anonToken);
    // 取某题的答案；anonToken 非空时记录「今天看过答案」
    crow::json::wvalue getDailyAnswer(int questionId, const std::string& anonToken);
    // 历史排期（按日期倒序分页），不含答案
    crow::json::wvalue getDailyHistory(int page, int pageSize);
    // 随机换一题（category 为空表示不限分类），不含答案
    crow::json::wvalue getRandomQuestion(const std::string& category);
    // 题库浏览（可按分类分页），不含答案，附各分类数量统计；includeDrafts 为 true 时含草稿（仅站长）
    crow::json::wvalue getQuestions(const std::string& category, int page, int pageSize, bool includeDrafts);
    // 单题详情（含答案，供站长编辑时回填）
    crow::json::wvalue getQuestionById(int id);
    // 题目增删改（权限由路由层校验：仅主管理员）
    crow::json::wvalue addQuestion(const std::string& category, const std::string& tags, int difficulty,
                                    const std::string& question, const std::string& answer, int status);
    crow::json::wvalue updateQuestion(int id, const std::string& category, const std::string& tags, int difficulty,
                                      const std::string& question, const std::string& answer, int status);
    crow::json::wvalue deleteQuestion(int id);

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
    bool changePassword(int adminId, const std::string& oldPassword, const std::string& newPassword, std::string& errMsg);

private:
    // 判断表中某列是否存在
    bool columnExists(const std::string& table, const std::string& column);
    // 判断表中某索引是否存在（MySQL 不支持 CREATE INDEX IF NOT EXISTS，需先查询）
    bool indexExists(const std::string& table, const std::string& index);
    // 确保表的字符集为 utf8mb4；非 utf8mb4 时自动 CONVERT（防中文被写成 '?'）
    void ensureTableCharset(const std::string& table);
    // 插入管理员记录（不主动加锁，调用方需已持有 mtx_）
    bool insertAdmin(const std::string& email, const std::string& password, int isMain, std::string& errMsg, int& outId);
    // 首次初始化时创建主管理员账号
    void seedMainAdmin();
    // 获取主管理员（is_main=1）的 id 与昵称
    bool getMainAdmin(int& outId, std::string& outNickname);
    // 历史文章（author_id=0）归到主管理员
    void backfillLegacyPosts();
    // 确保某天的题目已生成，返回题目 ID（0 表示题库中没有已发布的题目）
    int ensureDailyQuestion(const std::string& date);
    // 连续打卡天数（今天已答则含今天，否则从昨天往前算）
    int getDailyStreak(const std::string& ownerToken);
};
