from agent import CopilotAgent;
import time;

# ==========================================
# 1. 构建黄金数据集 (Golden Dataset)
# ==========================================
GOLDEN_DATASET = [
    {
        "id": 1,
        "input": "帮我看看订单号 987654 现在的物流到哪了？",
        "expected_tool": "fetch_order_status",
        "expected_params": {"order_id": "987654"}
    },
    {
        "id": 2,
        "input": "客户不想要了，帮我把订单 987654 退款 200 元",
        "expected_tool": "apply_refund",
        "expected_params": {"order_id": "987654", "amount": 200.0}
    }
]
# ==========================================
# 2. 评估流水线引擎(Evaluation Pipeline Engine)
# ==========================================

def run_evaluation():
    agent = CopilotAgent()
    passed_cases = 0
    total_cases = len(GOLDEN_DATASET)

    print("🚀 开始执行 Agentic AI 自动化评估流水线...\n" + "="*50)
    start_time = time.time()

    error_analysis_matrix = [] # 记录错误分析矩阵

    for case in GOLDEN_DATASET:
        print(f"\n🧪 评估案例 {case['id']}: {case['input']}")

        # 运行 Agent 得到路由结果
        actual_intent = agent.route_and_execute(case["input"])
        tool_match = actual_intent["tool_name"] == case["expected_tool"]
        params_match = actual_intent["tool_params"] == case["expected_params"]

        if tool_match and params_match:
            passed_cases += 1
            print(" 结果: PASSED")
        else:
            print(" 结果: FAILED")
            # Module 4: 记录错误类型以便后续进行 Error Analysis
            error_type = "Reasoning Error" if not tool_match else "Extraction Error (参数提取错误)"
            error_analysis_matrix.append({
                "case_id":case["id"],
                "input":case["input"],
                "error_type":error_type,
                "expected":{"tool":case["expected_tool"],"params":case["expected_params"]},
                "actual":actual_intent
            })
        print("-" * 50)

    # ==========================================
    # 3. 输出评估指标 (Metrics Output)
    # ==========================================
    accuracy = (passed_cases / total_cases) * 100
    elapsed_time = time.time() - start_time

    print("\n" + "="*50)
    print("📊 最终评估报告 (Evaluation Report)")
    print("Short-term Metrics:")
    print(f"   - 总测试用例数: {total_cases}")
    print(f"   - 成功通过件数: {passed_cases}")
    print(f"   - 【核心指标】工具调用准确率: {accuracy:.2f}%")
    print(f"   - 评估总耗时: {elapsed_time:.2f} 秒")
    print("="*50)

    # 如果有失败的，打印错误分析矩阵
    if error_analysis_matrix:
        print("\n🔍 错误分析矩阵 (Error Analysis Matrix) - 优化 Prompt 的绝对依据:")
        for err in error_analysis_matrix:
            print(f" 🚨 [用例 {err['case_id']}] 错误类型: {err['error_type']}")
            print(f"    - 期望结果: {err['expected']}")
            print(f"    - 实际输出: {err['actual']}")
    else:
        print("\n🎉 完美！所有用例全部通过，系统达到上线标准！")

if __name__ == "__main__":
    run_evaluation()