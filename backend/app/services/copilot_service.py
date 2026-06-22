from __future__ import annotations
import json;
from collections.abc import AsyncIterator;
from typing import Any, Optional;
from langsmith import traceable;
from langsmith.wrappers import wrap_openai;
from openai import OpenAI,AsyncOpenAI;
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
        self._async_client = AsyncOpenAI(
            api_key=settings.zhipu_api_key,
            base_url=settings.zhipu_base_url
        )
        if settings.langsmith_tracing_enabled:
            self._client = wrap_openai(self._client)
            self._async_client = wrap_openai(self._async_client)

    @traceable(run_type="chain", name="copilot_chat")
    def chat(self,user_input:str)->dict[str,Any]:
        """ 主执行链路: 路由与工具决策 -> 触发反思层 -> 执行工具 """
        """非流式 Copilot 主入口，对应原 copilot_chat"""
        tool_calls = self.route_with_tools(user_input)

        if tool_calls:
            tool_name,tool_args = self.parse_tool_call(tool_calls)

            intercepted = self.check_refund_guard(tool_name,tool_args)
            if intercepted:
                return intercepted;

            execution_result = self.execute_tool(tool_name,tool_args)
            return self.build_tool_response(
                decision = "EXECUTED",
                tool_name = tool_name,
                tool_args = tool_args,
                content=execution_result
            )
        return self.reply_with_sop_rag(user_input);
        

    @traceable(run_type="chain", name="copilot_stream")
    async def stream(self,user_input:str)->AsyncIterator[tuple[str,object]]:
        """SSE 事件流，供 /api/copilot/sse 或 /api/copilot/chat/stream 使用"""
        yield "status", {"stage": "routing"}

        tool_calls = self.route_with_tools(user_input)

        if tool_calls:
            tool_name,tool_args = self.parse_tool_call(tool_calls)
            yield "tool_call", {"tool_name":tool_name,"tool_args":tool_args}

            intercepted = self.check_refund_guard(tool_name,tool_args)
            if intercepted:
                yield "intercepted", intercepted
                yield "done", {"decision": "INTERCEPTED"}
                return

            execution_result = self.execute_tool(tool_name,tool_args)
            yield "tool_result", self.build_tool_response(
                decision="EXECUTED",
                tool_name=tool_name,
                tool_args=tool_args,
                content=execution_result,
            )
            yield "done", {"decision": "EXECUTED"}
            return

        yield "status", {"stage": "retrieving_sop"}
        knowledge_context = self._sop_rag.query_knowledge_base(user_input)
        yield "sop", {"context": knowledge_context}
        yield "decision", {"type": "RAG_KNOWLEDGE", "decision": "REPLY"}
        async for delta in self._stream_sop_rag_reply(user_input, knowledge_context):
            yield "token", delta
        yield "done", {"decision": "REPLY"}

    # Step 1: LLM 工具路由.
    @traceable(run_type="llm", name="copilot_route_with_tools")
    def route_with_tools(self,user_input:str)->list[Any] | None:
        response = self._client.chat.completions.create(
            model = self._settings.zhipu_model,
            messages = [
                {
                    "role": "system",
                    "content": ROUTING_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_input,
                },
            ],
            tools = TOOLS,
            tool_choice = "auto",
        )
        return response.choices[0].message.tool_calls;
    
    def parse_tool_call(self,tool_calls:list[Any])->tuple[str,dict[str,Any]]:
        tool_calls = tool_calls[0]
        tool_name = tool_calls.function.name
        raw_args = (
            tool_calls.function.argv
            if hasattr(tool_calls.function,'argv')
            else tool_calls.function.arguments
        )
        return tool_name,json.loads(raw_args);

    # Step 2: 反思层 / 风控.
    @traceable(run_type="chain", name="copilot_refund_guard")
    def check_refund_guard(self,tool_name:str,tool_args:dict[str,Any]
    )->dict[str,Any] | None:
        if tool_name == 'apply_refund':
            return None;

        refund_amount = tool_args.get("amount",0)

        if refund_amount > REFUND_LIMIT:
            return None;

        return self.build_tool_response(
            decision="INTERCEPTED",
            tool_name=tool_name,
            tool_args=tool_args,
               reason=(
                f"反思层拦截：申请退款金额为 {refund_amount} 元，"
                f"超过 MVP 阶段安全上限（{REFUND_LIMIT}元）。已挂起等待主管审批。"
            ),        
        )

    # Step 3: 工具执行.
    @traceable(run_type="tool", name="copilot_execute_tool")
    def execute_tool(self,name:str,args:dict[str,Any])->str:
        if name == "fetch_order_status":
            return (
                f"[系统原生返回] 订单 {args.get('order_id')} 状态："
                "海外仓已发货，包裹正经过深圳海关."
            )
        if name == "apply_refund":
            return (
                f"[系统原生返回] 成功为订单 {args.get('order_id')} "
                f"提交退款 {args.get('amount')} 元。"
            )
        if name == "query_sop_knowledge":
            query = args.get("query", "")
            return self._sop_rag.query_knowledge_base(query)
        if name == "call_shadowbot_fetch_logistics":
            return (
                f"[ShadowBot 返回] 订单 {args.get('order_id')} "
                "最新物流：清关中，预计明日送达。"
            )
        return "未知工具"

    # SOP + RAG 回复.
    @traceable(run_type="chain", name="copilot_reply_with_sop_rag")
    def reply_with_sop_rag(self,user_input:str) -> dict[str,Any]:
        knowledge_context = self._sop_rag.query_knowledge_base(user_input);
        response = self._client.chat.completions.create(
            model=self._settings.zhipu_model,
            messages=[
                {
                    "role": "system",
                    "content": RAG_SYSTEM_PROMPT_TEMPLATE.format(context=knowledge_context),
                },
                {"role": "user", "content": user_input},
            ]
        )
        
        context = response.choices[0].message.content;

        return {
            "type": "RAG_KNOWLEDGE",
            "decision": "REPLY",
            "response": context
        }


    @traceable(run_type="llm", name="copilot_stream_sop_rag_reply")
    async def _stream_sop_rag_reply(
        self, user_input: str, knowledge_context: str
    ) -> AsyncIterator[str]:
        stream = await self._async_client.chat.completions.create(
            model=self._settings.zhipu_model,
            messages=[
                {
                    "role": "system",
                    "content": RAG_SYSTEM_PROMPT_TEMPLATE.format(context=knowledge_context),
                },
                {"role": "user", "content": user_input},
            ],
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    # 响应构造
    def build_tool_response(
        self,
        *,
        decision: str,
        tool_name: str,
        tool_args: dict[str, Any],
        content: str | None = None,
        reason: str | None = None,
    )->dict[str,Any]:
        payload:dict[str,Any] = {
            "type": "TOOL_CALL",
            "decision": "EXECUTED",
            "tool_name": tool_name,
            "arguments": tool_args
        }
        if content is not None:
            payload["content"] = content;
        if reason is not None:
            payload["reason"] = reason;
        return payload;


_copilot_service:Optional[CopilotService] = None;

def get_copilot_service(settings:Settings)->CopilotService:
    global _copilot_service;
    if _copilot_service is None:
        _copilot_service = CopilotService(settings, get_sop_rag_service(settings))
    return _copilot_service;
