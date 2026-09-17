#pragma once

#include <cstddef>
#include <string>

#include "crow.h"

// 生成指定字节数的随机十六进制字符串（用作密码盐值）
std::string randomHex(size_t bytes);

// 字符串转小写
std::string toLower(std::string s);

// 去除字符串首尾空白
std::string trim(const std::string& s);

// 读取静态文件（失败返回空字符串）
std::string readFile(const std::string& path);

// 获取 static 目录的绝对路径（基于可执行文件位置）
std::string getStaticDir();

// 确保目录存在（不存在则创建）
void ensureDir(const std::string& path);

// 校验是否为合法的十六进制颜色（#RRGGBB）
bool isValidHexColor(const std::string& c);

// 根据文件名返回 MIME 类型
std::string mimeTypeFromFilename(const std::string& filename);

// 校验扩展名是否为允许上传的图片格式
bool isAllowedImageExt(const std::string& filename);

// 生成唯一文件名：时间戳 + 原始扩展名
std::string generateImageName(const std::string& originalName);

// 从 multipart part 中提取原始文件名（来自 Content-Disposition）
std::string getUploadFilename(const crow::multipart::part& p);

// 给 response 添加 CORS 头（旧版 Crow 没有中间件）
void addCorsHeaders(crow::response& res);

// 返回一个 HTML 页面的响应
crow::response htmlResponse(const std::string& content);
