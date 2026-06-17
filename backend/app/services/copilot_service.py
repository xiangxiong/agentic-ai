import json;
from collections.abc import AsyncIterator;
from typing import Any, Optional;
from openai import OpenAI;

from app.config import Settings;
from app.rag_service_sop import SopRagService, get_sop_rag_service;

ROUTING_SYSTEM_PROMPT = (
    "你是一个严谨的客服后台 Copilot。请根据用户的话语判断是否需要调用工具。"
    "如果是普通闲聊或无法用工具解决的问题，请直接礼貌回复。"
)

RAG_SYSTEM_PROMPT_TEMPLATE = (
    "你是一个客服话术专家。请根据公司官方SOP规范回答客服的问题。"
    "规范内容如下：\n{context}"
)

REFUND_LIMIT = 100

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "fetch_order_status",
            "description": "当用户查询订单物流、发货状态、快递进度时调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "订单号，通常是一串纯数字"
                    }
                },
                "required": ["order_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_refund",
            "description": "当客户由于质量、不想要等原因要求退款，且人工客服同意触发退款流程时调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "订单号"},
                    "amount": {"type": "number", "description": "退款金额，单位为元"}
                },
                "required": ["order_id", "amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_sop_knowledge",
            "description": "当用户询问平台政策、退货规则、海关拦截、发货规范等合规/流程问题时调用此工具，从客服 SOP 知识库检索标准答案。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "需要检索的政策或流程问题，尽量保留用户原意"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "call_shadowbot_fetch_logistics",
            "description": "当客服需要查询Ozon/TikTok电商后台的订单最新物流、需要穿透系统查数据时调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "订单号"}
                },
                "required": ["order_id"]
            }
        }
    }
]

class CopilotService:
    """ Copilot 编排: 工具路由 + 反思风控 + SOP RAG """

    def __init__(self,settings:Settings,sop_rag:SopRagService)->None:
        self._settings = settings;
        self._sop_rag = sop_rag;
        self._client = OpenAI(
            api_key=settings.zhipu_api_key,
            base_url=settings.zhipu_base_url,
        )

    def chat(self,user_input:str)->dict[str,Any]:
        """ 主执行链路: 路由与工具决策 -> 触发反思层 -> 执行工具 """

    # Step 1: LLM 工具路由.
    def route_with_tools(self,user_input:str)->list[Any] | None:
        return None;
    
    def parse_tool_call(self,tool_calls:list[Any])->tuple[str,dict[str,Any]]:
        return None;

    # Step 2: 反思层 / 风控.
    def check_refund_guard():
        return None;

    # Step 3: 工具执行.
    def execute_tool():
        return None;

    # SOP + RAG 回复.
    def reply_with_sop_rag():
        return None;

    def stream_sop_rag_reply():
        return None;

    # 响应构造
    def build_tool_response():
        return None;

_copilot_service:Optional[CopilotService] = None;

def get_copilot_service(settings:Settings)->CopilotService:
    global _copilot_service;
    if _copilot_service is None:
        _copilot_service = CopilotService(settings,get_copilot_service(settings))
    return _copilot_service;