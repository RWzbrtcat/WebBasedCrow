// ============================================================
// 练习闯关：代码沙箱判定（最小可跑版）
//
// 安全边界（务必读）：
//   当前用「裸机 fork/exec + rlimit」隔离，未做 chroot / 容器。
//   - 编译隔离：g++ 进程受限 CPU 10s、内存 512MB，独立临时目录
//   - 运行隔离：a.out 进程受限 CPU 2s、内存 256MB、文件 64MB、
//     进程数 32、文件描述符 64，禁 core dump
//   - 缺口 1：玩家代码可读宿主机上「本进程用户可读」的文件（如 /etc/passwd），
//     暂未 chroot。当前站点提交者基本是站长本人，风险可接受；
//     对外公开前必须补 chroot 或 docker。
//   - 缺口 2：数据库题（C11）暂未接真实 DB，待定。
//   - 缺口 3：服务以 root 跑时 RLIMIT_NPROC 对 root 无效（内核不限制 root 的
//     进程数），CPU/AS/FSIZE/NOFILE/CORE 仍生效。
//   代码按「不可信输入」编写，但隔离强度尚不达公开 OJ 标准。
//
// 判定协议 v1：
//   玩家提交「函数实现」代码（不含 main），服务端把它与隐藏测试驱动拼接成一个
//   solution.cpp 编译运行。测试驱动约定：
//     - 每个失败用例打印一行 "FAIL: <描述>"
//     - 全部通过打印一行 "PASS"
//     - main 返回失败用例数（0 = 全过）
//   服务端按退出码 + stdout 中 "FAIL:" 出现次数判定。
// ============================================================

#include "practice.h"

#include <fcntl.h>
#include <signal.h>
#include <sys/resource.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#include <cerrno>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

namespace
{

// ---------- 子进程运行结果 ----------
struct ProcResult
{
    int exitCode = -1;       // 正常退出的退出码（fork/pipe 失败时保持 -1）
    bool timedOut = false;   // 是否超时被杀
    bool signaled = false;   // 是否被信号杀死（段错误等）
    int termSignal = 0;      // 终止信号
    std::string out;         // stdout
    std::string err;         // stderr
};

// ---------- 资源限制 ----------
struct Limits
{
    int cpuSeconds = 2;                  // RLIMIT_CPU：CPU 时间（秒）
    long memBytes = 256L * 1024 * 1024;  // RLIMIT_AS：地址空间
    long fileBytes = 64L * 1024 * 1024;  // RLIMIT_FSIZE：单文件大小
    int nproc = 32;                      // RLIMIT_NPROC：进程数
    int nofile = 64;                     // RLIMIT_NOFILE：打开文件数
};

// 在子进程里应用资源限制（fork 之后、exec 之前调用）
void applyLimits(const Limits& lim)
{
    struct rlimit rl;

    rl.rlim_cur = static_cast<rlim_t>(lim.cpuSeconds);
    rl.rlim_max = static_cast<rlim_t>(lim.cpuSeconds);
    setrlimit(RLIMIT_CPU, &rl);

    rl.rlim_cur = static_cast<rlim_t>(lim.memBytes);
    rl.rlim_max = static_cast<rlim_t>(lim.memBytes);
    setrlimit(RLIMIT_AS, &rl);

    rl.rlim_cur = static_cast<rlim_t>(lim.fileBytes);
    rl.rlim_max = static_cast<rlim_t>(lim.fileBytes);
    setrlimit(RLIMIT_FSIZE, &rl);

    rl.rlim_cur = static_cast<rlim_t>(lim.nproc);
    rl.rlim_max = static_cast<rlim_t>(lim.nproc);
    setrlimit(RLIMIT_NPROC, &rl);

    rl.rlim_cur = static_cast<rlim_t>(lim.nofile);
    rl.rlim_max = static_cast<rlim_t>(lim.nofile);
    setrlimit(RLIMIT_NOFILE, &rl);

    // 禁 core dump（段错误时不往磁盘写大文件）
    rl.rlim_cur = 0;
    rl.rlim_max = 0;
    setrlimit(RLIMIT_CORE, &rl);
}

// 把 vector<string> 转成 execvp 用的 char* 数组（末尾以 nullptr 收尾）
std::vector<char*> buildArgv(const std::vector<std::string>& args)
{
    std::vector<char*> argv;
    argv.reserve(args.size() + 1);
    for (const auto& a : args)
    {
        argv.push_back(const_cast<char*>(a.c_str()));
    }
    argv.push_back(nullptr);
    return argv;
}

// 尽力排空一个管道（在子进程已退出后调用，此时写端已关闭，读到 EOF 为止）
void drainPipe(int fd, std::string& to)
{
    char buf[8192];
    ssize_t n;
    while ((n = read(fd, buf, sizeof(buf))) > 0)
    {
        to.append(buf, static_cast<size_t>(n));
    }
}

// fork + exec + 双管道捕获输出 + waitpid 超时轮询。
// 内部错误（pipe/fork 失败）时返回 exitCode=-1 且 errorOut 非空。
ProcResult runProcess(const std::vector<std::string>& args,
                      const std::string& workDir,
                      int timeoutMs,
                      const Limits& limits,
                      std::string& errorOut)
{
    ProcResult r;
    int outPipe[2];
    int errPipe[2];
    if (pipe(outPipe) != 0 || pipe(errPipe) != 0)
    {
        errorOut = std::string("pipe 失败: ") + std::strerror(errno);
        return r;
    }

    pid_t pid = fork();
    if (pid < 0)
    {
        close(outPipe[0]); close(outPipe[1]);
        close(errPipe[0]); close(errPipe[1]);
        errorOut = std::string("fork 失败: ") + std::strerror(errno);
        return r;
    }

    if (pid == 0)
    {
        // ---------- 子进程 ----------
        dup2(outPipe[1], STDOUT_FILENO);
        dup2(errPipe[1], STDERR_FILENO);
        close(outPipe[0]); close(outPipe[1]);
        close(errPipe[0]); close(errPipe[1]);

        if (!workDir.empty()) chdir(workDir.c_str());

        applyLimits(limits);

        std::vector<char*> argv = buildArgv(args);
        execvp(argv[0], argv.data());

        // execvp 失败才走到这里
        std::fprintf(stderr, "exec 失败: %s\n", std::strerror(errno));
        _exit(127);
    }

    // ---------- 父进程 ----------
    close(outPipe[1]);
    close(errPipe[1]);

    // 非阻塞读，避免子进程输出多时管道写满死锁
    int fl = fcntl(outPipe[0], F_GETFL);
    fcntl(outPipe[0], F_SETFL, fl | O_NONBLOCK);
    fl = fcntl(errPipe[0], F_GETFL);
    fcntl(errPipe[0], F_SETFL, fl | O_NONBLOCK);

    bool outEof = false;
    bool errEof = false;
    bool exited = false;
    int status = 0;
    auto start = std::chrono::steady_clock::now();

    char buf[8192];
    while (!exited)
    {
        // 非阻塞读 stdout
        if (!outEof)
        {
            ssize_t n = read(outPipe[0], buf, sizeof(buf));
            if (n > 0) r.out.append(buf, static_cast<size_t>(n));
            else if (n == 0) outEof = true;
            else if (errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR) outEof = true;
        }
        // 非阻塞读 stderr
        if (!errEof)
        {
            ssize_t n = read(errPipe[0], buf, sizeof(buf));
            if (n > 0) r.err.append(buf, static_cast<size_t>(n));
            else if (n == 0) errEof = true;
            else if (errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR) errEof = true;
        }

        pid_t w = waitpid(pid, &status, WNOHANG);
        if (w == pid)
        {
            exited = true;
        }
        else if (w < 0)
        {
            exited = true;  // waitpid 出错，当作已退出
        }
        else
        {
            auto now = std::chrono::steady_clock::now();
            long long elapsedMs =
                std::chrono::duration_cast<std::chrono::milliseconds>(now - start).count();
            if (elapsedMs >= timeoutMs)
            {
                kill(pid, SIGKILL);
                r.timedOut = true;
                waitpid(pid, &status, 0);  // 收割
                exited = true;
            }
            else
            {
                usleep(10000);  // 10ms 轮询间隔
            }
        }
    }

    // 子进程已退出，写端已关闭，排空管道残留
    drainPipe(outPipe[0], r.out);
    drainPipe(errPipe[0], r.err);

    close(outPipe[0]);
    close(errPipe[0]);

    if (r.timedOut) return r;

    if (WIFEXITED(status))
    {
        r.exitCode = WEXITSTATUS(status);
    }
    else if (WIFSIGNALED(status))
    {
        r.signaled = true;
        r.termSignal = WTERMSIG(status);
    }
    return r;
}

// 编译错误 → 人话翻译（P2 支柱：不让玩家直面 g++ 原文）
std::string translateCompileError(const std::string& raw)
{
    if (raw.find("was not declared in this scope") != std::string::npos)
        return "有名字未声明：检查是否漏了头文件、函数/变量定义，或拼写错误。";
    if (raw.find("expected ';'") != std::string::npos)
        return "语法错误：可能少了分号。";
    if (raw.find("no matching function") != std::string::npos)
        return "函数调用不匹配：参数类型或数量不对。";
    if (raw.find("redefinition of") != std::string::npos)
        return "重复定义：不要写 main（隐藏测试会提供），也不要重复定义已有符号。";
    if (raw.find("expected '}'") != std::string::npos || raw.find("expected ')'") != std::string::npos)
        return "括号不匹配：检查 {} 或 () 是否闭合。";
    if (raw.find("lvalue required as left operand of assignment") != std::string::npos)
        return "赋值目标不是左值：函数返回值不能当赋值目标（应返回引用而非值）。";
    if (raw.find("exec 失败") != std::string::npos)
        return "服务器未找到 g++ 编译器（PATH 配置问题），请联系管理员确认已安装 g++。";
    return "编译未通过，请看下面的编译器输出。";
}

// 运行期错误 → 人话翻译
std::string translateRuntimeError(const ProcResult& r)
{
    if (r.timedOut)
        return "运行超时：可能有死循环、死锁或死等。";
    if (r.signaled)
    {
        if (r.termSignal == SIGSEGV)
            return "段错误：访问了非法内存（空指针、越界、野指针或已释放对象）。";
        if (r.termSignal == SIGABRT)
            return "程序被 abort：断言失败或调用了 std::terminate（异常未捕获）。";
        if (r.termSignal == SIGKILL)
            return "进程被强制终止：可能内存/资源超限。";
        return "运行期异常终止（信号 " + std::to_string(r.termSignal) + "）。";
    }
    return "运行未通过，请看下面的输出。";
}

// 写文件，失败返回 false
bool writeFile(const std::string& path, const std::string& content)
{
    FILE* f = std::fopen(path.c_str(), "wb");
    if (!f) return false;
    std::fwrite(content.data(), 1, content.size(), f);
    std::fclose(f);
    return true;
}

// 删除临时目录（目录内只有我们写的 solution.cpp 与 a.out）
void removeDir(const std::string& dir)
{
    unlink((dir + "/a.out").c_str());
    unlink((dir + "/solution.cpp").c_str());
    rmdir(dir.c_str());
}

} // namespace

PracticeJudge judgeSubmission(const std::string& code, const std::string& testDriver,
                              int totalCases, int timeLimitMs)
{
    PracticeJudge j;

    if (testDriver.empty())
    {
        j.ok = false;
        j.status = "internal_error";
        j.message = "题目测试驱动为空。";
        return j;
    }

    if (code.empty())
    {
        j.ok = false;
        j.status = "internal_error";
        j.message = "提交的代码为空。";
        return j;
    }

    // ---------- 建临时目录 ----------
    char tmpl[] = "/tmp/practiceXXXXXX";
    char* dir = mkdtemp(tmpl);
    if (!dir)
    {
        j.ok = false;
        j.status = "internal_error";
        j.message = std::string("无法创建临时目录: ") + std::strerror(errno);
        return j;
    }
    const std::string tmpDir = dir;

    // 拼接玩家代码 + 隐藏测试驱动
    const std::string source = code + "\n\n" + testDriver;
    const std::string srcPath = tmpDir + "/solution.cpp";
    if (!writeFile(srcPath, source))
    {
        removeDir(tmpDir);
        j.ok = false;
        j.status = "internal_error";
        j.message = "无法写入临时源码文件。";
        return j;
    }

    // ---------- 编译 ----------
    Limits compileLimits;
    compileLimits.cpuSeconds = 10;
    compileLimits.memBytes = 512L * 1024 * 1024;
    compileLimits.fileBytes = 64L * 1024 * 1024;
    compileLimits.nproc = 64;
    compileLimits.nofile = 128;

    // C++20：C13 章节（concept / ranges / 三路比较）需要 C++20；C++20 向后兼容 C++17，
    // 对前面 12 章的 C++17 代码无影响。要求服务器 g++ >= 10（C++20 完整支持）。
    std::vector<std::string> compileArgs = {
        "g++", "-std=c++20", "-O2", "-Wall", "-pthread", "solution.cpp", "-o", "a.out"
    };

    std::string procErr;
    ProcResult compileRes = runProcess(compileArgs, tmpDir, 10000, compileLimits, procErr);
    if (compileRes.exitCode == -1 && !procErr.empty())
    {
        // 内部错误（pipe/fork 失败）
        removeDir(tmpDir);
        j.ok = false;
        j.status = "internal_error";
        j.message = procErr;
        return j;
    }
    if (compileRes.timedOut)
    {
        removeDir(tmpDir);
        j.ok = true;
        j.status = "compile_error";
        j.message = "编译超时：代码过于复杂或包含死循环模板展开。";
        j.compileOutput = "编译超过 10 秒被终止。";
        return j;
    }
    if (compileRes.exitCode != 0)
    {
        removeDir(tmpDir);
        j.ok = true;
        j.status = "compile_error";
        j.compileOutput = compileRes.err.empty() ? compileRes.out : compileRes.err;
        j.message = translateCompileError(j.compileOutput);
        return j;
    }

    // ---------- 运行 ----------
    Limits runLimits;
    runLimits.cpuSeconds = (timeLimitMs + 999) / 1000;  // 毫秒 → 秒，向上取整
    if (runLimits.cpuSeconds < 1) runLimits.cpuSeconds = 1;
    runLimits.memBytes = 256L * 1024 * 1024;
    runLimits.fileBytes = 64L * 1024 * 1024;
    runLimits.nproc = 32;
    runLimits.nofile = 64;

    std::vector<std::string> runArgs = { "./a.out" };

    ProcResult runRes = runProcess(runArgs, tmpDir, timeLimitMs, runLimits, procErr);
    if (runRes.exitCode == -1 && !procErr.empty())
    {
        removeDir(tmpDir);
        j.ok = false;
        j.status = "internal_error";
        j.message = procErr;
        return j;
    }

    // ---------- 判定 ----------
    j.ok = true;
    j.total = totalCases;
    j.runtimeOutput = runRes.out;
    if (!runRes.err.empty()) j.runtimeOutput += "\n[stderr]\n" + runRes.err;

    if (runRes.timedOut)
    {
        j.status = "timeout";
        j.message = translateRuntimeError(runRes);
        removeDir(tmpDir);
        return j;
    }
    if (runRes.signaled)
    {
        j.status = "runtime_error";
        j.message = translateRuntimeError(runRes);
        removeDir(tmpDir);
        return j;
    }

    // 统计 FAIL 数量（测试驱动约定：每个失败用例打印一行 "FAIL:"）
    int failCount = 0;
    size_t pos = 0;
    while ((pos = runRes.out.find("FAIL:", pos)) != std::string::npos)
    {
        ++failCount;
        pos += 5;  // 跳过 "FAIL:"
    }
    if (runRes.exitCode != 0 && failCount == 0) failCount = runRes.exitCode;

    j.passed = totalCases - failCount;
    if (j.passed < 0) j.passed = 0;

    if (failCount == 0 && runRes.exitCode == 0)
    {
        j.status = "passed";
        j.message = "通过全部用例。";
    }
    else
    {
        j.status = "failed";
        j.message = "通过了 " + std::to_string(j.passed) + " / " + std::to_string(totalCases) + " 个用例。";
    }

    removeDir(tmpDir);
    return j;
}
