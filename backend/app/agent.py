from typing import Dict,Any;

def fetch_order_status(order_id:str)->str:
    """ 查询订单和物流订单. """

    # 实际开发中这里对接ERP 或 影刀RPA Webhook 
    return f" 【订单{order_id}】 当前状态: 海外仓已发货, 物流商: Ozon Logistics"


def apply_refund(order_id:str,amount:float)->str:
    """ 触发退款申请 """

    return f" [成功] 已为订单 {order_id} 提交退款申请, 金额: {amount} 元"

# =======================
# 2. Agent 核心业务流程
# =======================
class CopilotAgent:
    def __init__(self,mock_llm_client=None):
        # 1. 初始化 LLM 客户端,实际生产中传入真正的 LLM Client (如 OpenAI / DeepSeek)
        pass

    def route_and_execute(self,user_input:str)->Dict[str,Any]:
        """ 
        Module 2,3 & 5: 意图识别与工具分发(Router & Tool Use)
        """

        # 模拟大模型理解意图并输出 JSON(Function Calling)
        # 假设用户输入: "帮我查一下一下订单 987689 的物流, 并申请退款 200 元"
        if "订单" in user_input and "退款" in user_input:
            tool_name = "apply_refund"
            tool_params = {"order_id":"987654","amount":200.0}
        elif "查" in user_input or "物流" in user_input:
            tool_name = "fetch_order_status"
            tool_params = {"order_id":"987654"}
        else:
            tool_name = "none"
            tool_params = {}

        return {"tool_name":tool_name,"tool_params":tool_params} # 返回结果和工具调用记录

    def critic_reflection(self,tool_name:str,tool_params:Dict[str,Any])->Dict[str,Any]:
        """
        Module 2: 反思模式(Reflection / 风控卡点)
        """

        if tool_name == "apply_refund":
            amount = tool_params.get("amount",0)
            # 反思规则: 单笔退款超过 100 元, 必须触发人工二次确认, 不能直接自动执行

            if amount > 100:
                return {
                    "status":"INTERCEPTED",
                    "reason": f"反思层拦截: 退款金额 ({amount}元) 超过安全阀值, 需主管审批.",
                    "action_required":"MANUAL_APPROVE"
                }

        return {"status":"PASSED","reason":"合规检查通过."}

    def run(self,user_input:str)->Dict[str,Any]:
        """主执行链路"""
        
        # 1、路由与工具决策
        intent = self.route_and_execute(user_input)

        if intent["tool_name"] == "none":
            return {"output":"未能识别有效指令, 已转交人工客服"}

        # 2、 触发反思层进行审查
        reflection = self.critic_reflection(intent["tool_name"],intent["tool_params"])

        if reflection["status"] == "INTERCEPTED":
            return {
                "decision":"HOLD",
                "tool_intent":intent,
                "msg":reflection["reason"]
            }

        # 3. 执行工具(安全通过的情况下)
        if intent["tool_name"] == "fetch_order_status":
            res = fetch_order_status(intent["tool_params"]["order_id"])
        elif intent["tool_name"] == "apply_refund":
            res = apply_refund(intent["tool_params"]["order_id"],intent["tool_params"]["amount"])

        return {"decision":"EXECUTE","output":res}