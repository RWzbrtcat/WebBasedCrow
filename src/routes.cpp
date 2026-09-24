#include "routes.h"

#include <fstream>
#include <string>

#include "auth.h"
#include "utils.h"

void setupRoutes(crow::SimpleApp& app, DataBase& db, const std::string& staticDir)
{
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

        std::string token = createSession(adminId, isMain);

        result["success"] = true;
        result["is_main"] = isMain;
        crow::response res(200, result);
        res.add_header("Set-Cookie", SESSION_COOKIE + "=" + token + "; HttpOnly; Path=/; SameSite=Lax; Max-Age=2592000");
        addCorsHeaders(res);
        return res;
    });

    // GET /api/auth - 查询当前登录态（是否登录、是否主管理员、个人资料）
    CROW_ROUTE(app, "/api/auth").methods("GET"_method)([&db](const crow::request& req){
        crow::json::wvalue result;
        result["success"] = true;
        Session s;
        bool authed = getSession(req, s);
        result["authed"] = authed;
        result["is_main"] = authed && s.isMain;
        if (authed)
        {
            std::string email, nickname, avatar;
            bool isMain = false;
            if (db.getAdminProfile(s.adminId, email, nickname, avatar, isMain))
            {
                result["admin_id"] = s.adminId;
                result["email"] = email;
                result["nickname"] = nickname.empty() ? email : nickname;
                result["avatar"] = avatar;
            }
        }
        crow::response res(result);
        addCorsHeaders(res);
        return res;
    });

    // PUT /api/profile - 更新当前登录管理员的昵称与头像（登录后可用）
    CROW_ROUTE(app, "/api/profile").methods("PUT"_method)([&db](const crow::request& req){
        Session s;
        if (!getSession(req, s)) return unauthorizedResponse();

        auto body = crow::json::load(req.body);
        if (!body)
        {
            crow::json::wvalue err;
            err["success"] = false;
            err["message"] = "无效的 JSON 数据";
            return crow::response(400, err);
        }

        std::string nickname = body.has("nickname") ? std::string(body["nickname"].s()) : std::string("");
        std::string avatar = body.has("avatar") ? std::string(body["avatar"].s()) : std::string("");
        crow::response res(db.updateProfile(s.adminId, nickname, avatar));
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

    // GET /api/hidden - 获取已隐藏文章列表（仅登录；主管理员看全部，普通管理员看自己的）
    CROW_ROUTE(app, "/api/hidden").methods("GET"_method)([&db](const crow::request& req){
        Session s;
        if (!getSession(req, s)) return unauthorizedResponse();
        crow::response res(db.getHiddenPosts(s.isMain, s.adminId));
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

    // POST /api/posts - 发布文章（仅登录后可用；作者自动取账号昵称）
    CROW_ROUTE(app, "/api/posts").methods("POST"_method)([&db](const crow::request& req){
        Session s;
        if (!getSession(req, s)) return unauthorizedResponse();
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
        std::string topic = body.has("topic") ? std::string(body["topic"].s()) : std::string("");
        std::string theme = body.has("theme") ? std::string(body["theme"].s()) : std::string("");
        std::string status = body.has("status") ? std::string(body["status"].s()) : std::string("published");

        std::string author = db.getAdminNickname(s.adminId);
        if (author.empty()) author = "匿名";

        crow::response res(db.addPost(title, content, summary, author, topic, theme, status, s.adminId));
        addCorsHeaders(res);
        return res;
    });

    // GET /api/posts/<id> - 获取单篇文章（隐藏文章仅作者本人或主管理员可见）
    CROW_ROUTE(app, "/api/posts/<int>").methods("GET"_method)([&db](const crow::request& req, int id){
        Session s;
        bool authed = getSession(req, s);
        crow::response res(db.getPostById(id, authed && s.isMain, authed ? s.adminId : 0));
        addCorsHeaders(res);
        return res;
    });

    // PUT /api/posts/<id> - 更新文章（仅登录后可用；非主管理员只能改自己的文章）
    CROW_ROUTE(app, "/api/posts/<int>").methods("PUT"_method)([&db](const crow::request& req, int id){
        Session s;
        if (!getSession(req, s)) return unauthorizedResponse();

        int ownerId = 0;
        std::string ownerAuthor;
        if (!db.getPostAuthor(id, ownerId, ownerAuthor))
        {
            crow::json::wvalue err;
            err["success"] = false;
            err["message"] = "文章不存在";
            crow::response res(404, err);
            addCorsHeaders(res);
            return res;
        }
        if (!s.isMain && ownerId != s.adminId)
        {
            crow::json::wvalue err;
            err["success"] = false;
            err["message"] = "不能修改他人的文章";
            crow::response res(403, err);
            addCorsHeaders(res);
            return res;
        }

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
        std::string topic = body.has("topic") ? std::string(body["topic"].s()) : std::string("");
        std::string theme = body.has("theme") ? std::string(body["theme"].s()) : std::string("");
        std::string status = body.has("status") ? std::string(body["status"].s()) : std::string("published");
        crow::response res(db.updatePost(id, title, content, summary, topic, theme, status));
        addCorsHeaders(res);
        return res;
    });

    // DELETE /api/posts/<id> - 删除文章（仅登录后可用；非主管理员只能删自己的文章）
    CROW_ROUTE(app, "/api/posts/<int>").methods("DELETE"_method)([&db](const crow::request& req, int id){
        Session s;
        if (!getSession(req, s)) return unauthorizedResponse();

        int ownerId = 0;
        std::string ownerAuthor;
        if (db.getPostAuthor(id, ownerId, ownerAuthor) && !s.isMain && ownerId != s.adminId)
        {
            crow::json::wvalue err;
            err["success"] = false;
            err["message"] = "不能删除他人的文章";
            crow::response res(403, err);
            addCorsHeaders(res);
            return res;
        }

        crow::response res(db.deletePost(id));
        addCorsHeaders(res);
        return res;
    });

    // PUT /api/posts/<id>/hidden - 隐藏 / 取消隐藏文章（仅作者本人或主管理员）
    CROW_ROUTE(app, "/api/posts/<int>/hidden").methods("PUT"_method)([&db](const crow::request& req, int id){
        Session s;
        if (!getSession(req, s)) return unauthorizedResponse();

        int ownerId = 0;
        std::string ownerAuthor;
        if (!db.getPostAuthor(id, ownerId, ownerAuthor))
        {
            crow::json::wvalue err;
            err["success"] = false;
            err["message"] = "文章不存在";
            crow::response res(404, err);
            addCorsHeaders(res);
            return res;
        }
        if (!s.isMain && ownerId != s.adminId)
        {
            crow::json::wvalue err;
            err["success"] = false;
            err["message"] = "不能操作他人的文章";
            crow::response res(403, err);
            addCorsHeaders(res);
            return res;
        }

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
        crow::response res(db.setPostHidden(id, hidden ? 1 : 0));
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
            destroySession(token);
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

    // 个人资料页（登录后可访问）
    CROW_ROUTE(app, "/profile")([staticDir](const crow::request& req){
        if (!isLoggedIn(req))
        {
            crow::response res;
            res.moved("/login");
            return res;
        }
        return htmlResponse(readFile(staticDir + "/profile.html"));
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
}
