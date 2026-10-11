#pragma once

#include <string>

// ============================================================
// 练习闯关：代码沙箱判定（模块头）
// 实现见 practice.cpp。此处只暴露判定入口与结果结构。
// ============================================================

// 单次判定的结果，直接映射为 /api/practice/submit 的 JSON 返回体
struct PracticeJudge
{
    bool ok = false;             // 沙箱流程本身是否成功（编译 + 运行都执行到位）
    std::string status;          // passed / failed / compile_error / runtime_error / timeout / internal_error
    int passed = 0;              // 通过用例数
    int total = 0;               // 总用例数
    std::string message;         // 翻译后的人话反馈
    std::string compileOutput;   // 编译器原文（仅编译失败时非空）
    std::string runtimeOutput;   // 运行期 stdout + stderr（诊断用）
};

// 编译并运行玩家代码，返回判定结果。
// 最小版：exerciseId 仅支持 1（内置示例题），tier 暂不影响判定（将来按档取不同隐藏用例）。
// 安全边界：裸机 fork/exec + rlimit，未 chroot —— 详见 practice.cpp 顶部说明。
PracticeJudge judgeSubmission(int exerciseId, const std::string& tier, const std::string& code);
