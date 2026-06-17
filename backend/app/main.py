from __future__ import annotations
from collections.abc import AsyncIterator
import json
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from app.chat_service import ChatService, MissingApiKeyError, sse_event
from app.config import get_settings
from app.rag_service import RagService
from app.rag_service_sop import get_sop_rag_service
from app.schemas import ChatRequest, ChatResponse, DocumentUploadResponse, HealthResponse
from typing import Any
from pydantic import BaseModel, Field
from openai import OpenAI

settings = get_settings()
rag_service = RagService(settings)
chat_service = ChatService(settings, rag_service)

app = FastAPI(title="DeepSeek LangChain Chatbot", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", model=settings.deepseek_model)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        return await chat_service.chat(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MissingApiKeyError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    session_id = request.session_id or chat_service.create_session_id()

    async def event_stream() -> AsyncIterator[str]:
        yield sse_event("session", {"session_id": session_id})
        try:
            async for event, payload in chat_service.stream(request, session_id):
                if event == "sources":
                    yield sse_event("sources", {"sources": payload})
                else:
                    yield sse_event("token", {"content": payload})
            yield sse_event("done", {"session_id": session_id})
        except ValueError as exc:
            yield sse_event("error", {"message": str(exc)})
        except MissingApiKeyError as exc:
            yield sse_event("error", {"message": str(exc)})
        except Exception:
            yield sse_event("error", {"message": "Chat completion failed."})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/knowledge-bases/{kb_id}/documents", response_model=DocumentUploadResponse)
async def upload_knowledge_document(
    kb_id: str,
    file: UploadFile = File(...),
) -> DocumentUploadResponse:
    try:
        document_id, chunks = await rag_service.upload_document(kb_id, file)
        return DocumentUploadResponse(
            knowledge_base_id=kb_id,
            document_id=document_id,
            filename=file.filename or "",
            chunks=chunks,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/sessions/{session_id}", status_code=204)
async def clear_session(session_id: str) -> None:
    await chat_service.clear(session_id)

# ==========================================
# 1. 定义大模型可见的工具声明 (Tools Definition)
# ==========================================
TOOLS = [
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

# ==========================================
# 2. 模拟底层业务执行
# ==========================================
def execute_system_tool(name:str,args:dict)->str:
    if name == "fetch_order_status":
        return f"[系统原生返回] 订单 {args.get('order_id')} 状态：海外仓已发货，包裹正经过深圳海关."
    if name == "apply_refund":
        return f"[系统原生返回] 成功为订单 {args.get('order_id')} 提交退款 {args.get('amount')} 元。"
    return "未知工具"


# ==========================================
# 3. 核心路由与请求结构
# ==========================================
client = OpenAI(
    api_key=settings.zhipu_api_key,
    base_url=settings.zhipu_base_url,
)

class ChatRequest(BaseModel):
    user_input:str = Field(...,description="人工客服或前端用户的输入内容")

@app.post("/api/copilot/chat")
async def copilot_chat(request:ChatRequest):
    user_msg = request.user_input

    try:
        # Step 1: 让大模型进行推理，决定是否调用工具 (Module 3: Tool Use)
        response = client.chat.completions.create(
            model=settings.zhipu_model,
            messages=[
                {"role":"system","content":"你是一个严谨的客服后台 Copilot。请根据用户的话语判断是否需要调用工具。如果是普通闲聊或无法用工具解决的问题，请直接礼貌回复。"},
                {"role":"user","content":user_msg}
            ],
            tools=TOOLS,
            tool_choice="auto",
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        print(f"Tool Calls: {tool_calls}")

        # 场景 B: LLM 决定调用工具
        if tool_calls:
            tool_calls = tool_calls[0]
            tool_name = tool_calls.function.name
            tool_args = json.loads(tool_calls.function.argv if hasattr(tool_calls.function, 'argv') else tool_calls.function.arguments);

            # Step 2: 引入反思层 (Module 2: Reflection / 风控卡点)
            if tool_name == "apply_refund":
                refund_amount = tool_args.get("amount",0)

                if refund_amount > 100:
                    return {
                        "type": "TOOL_CALL",
                        "decision": "INTERCEPTED",
                        "reason": f"反思层拦截：申请退款金额为 {refund_amount} 元，超过 MVP 阶段安全上限（100元）。已挂起等待主管审批。",
                        "tool_name": tool_name,
                        "arguments": tool_args
                    }

            # Step 3: 安全检查通过，执行工具并返回
            execution_result = execute_system_tool(tool_name, tool_args)

            return {
                "type": "TOOL_CALL",
                "decision": "EXECUTED",
                "tool_name": tool_name,
                "arguments": tool_args,
                "content": execution_result
            }

        # 场景 A: LLM 认为不需要调工具，直接回复了文本（比如 RAG 话术建议或闲聊）
        knowledge_context = get_sop_rag_service(settings).query_knowledge_base(user_msg)

        rag_response = client.chat.completions.create(
            model=settings.zhipu_model,
            messages=[  
                {"role":"system","content":f"你是一个客服话术专家。请根据公司官方SOP规范回答客服的问题。规范内容如下：\n{knowledge_context}"},
                {"role":"user","content":user_msg}
            ]
        )

        rag_response_message = rag_response.choices[0].message
        rag_response_content = rag_response_message.content

        return {
            "type": "RAG_KNOWLEDGE",
            "decision": "REPLY",
            "response": rag_response_content,
        }

    except Exception as e:
        raise HTTPException(status_code=500,detail=str(e))

class SopQueryRequest(BaseModel):
    query:str = Field(...,description="SOP 检索问题")

@app.post("/api/sop/query")
async def query_sop(request:SopQueryRequest) -> dict[str,str]:
    try:
        print(f"Query{request.query}");
        result = get_sop_rag_service(settings).query_knowledge_base(request.query);
        return {"result":result}
    except Exception as e:
        raise HTTPException(status_code=500,detail=str(e))

class GenerateRequest(BaseModel):
    query:str = Field(...,description="SOP 生成问题")

@app.post("/api/sop/generate")
async def generate(request:GenerateRequest) -> dict[str, Any]:
    try:
        get_sop_rag_service(settings).init_mock_sop_data();
        result = get_sop_rag_service(settings).embed(request.query);
        return {"result":result}
    except Exception as e:
        raise HTTPException(status_code=500,detail=str(e))