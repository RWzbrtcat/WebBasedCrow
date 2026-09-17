#include "utils.h"

#include <unistd.h>
#include <limits.h>
#include <sys/stat.h>

#include <algorithm>
#include <cctype>
#include <chrono>
#include <fstream>
#include <random>
#include <sstream>

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
