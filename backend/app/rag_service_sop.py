from __future__ import annotations
from typing import Optional
from app.config import Settings
from chromadb import PersistentClient
from openai import OpenAI

MOCK_SOP_DOCS = [
    "TikTok跨境小店政策：因质量问题退货，商家承担跨境运费；非质量问题（不想要了），买家自理运费。",
    "Ozon平台海关包裹拦截规则：包裹一旦进入海外仓或进入海关清关阶段，无法进行物理拦截，只能等投递失败后自动退回。",
    "深圳仓发货规范：每日16:00前生成的订单，必须在当晚22:00前完成打包并扫描进仓。",
]

class SopRagService:
    """ 模拟的 SOP 知识库 RAG 服务 """

    def __init__(self,settings:Settings) -> None:
        self._settings = settings;
        self._embedding_client = OpenAI(
            api_key=settings.zhipu_api_key,
            base_url=settings.zhipu_base_url
        )

    def init_mock_sop_data(self) -> None:
        """ 首次启动时注入 mock SOP 数据 """
        print("Succeeded in initialzing SOP Knowledge Base embedding!");

    def query_knowledge_base(self,query_text:str) -> str:
        """ 检索最相关的 SOP 规则  """
        return "test";

    def embed(self,text:str)->list[float]:
        """ 将文本转换为向量 """
        response = self._embedding_client.embeddings.create(
            input=text,
            model=self._settings.rag_embedding_model
        )
        return response.data[0].embedding;

_sop_rag_service:Optional[SopRagService] = None;

def get_sop_rag_service(settings:Settings)->SopRagService:
    global _sop_rag_service
    if _sop_rag_service is None:
        _sop_rag_service = SopRagService(settings);
    return _sop_rag_service;