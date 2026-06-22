from __future__ import annotations
from typing import Optional
from langsmith import traceable
from langsmith.wrappers import wrap_openai
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
        if settings.langsmith_tracing_enabled:
            self._embedding_client = wrap_openai(self._embedding_client)
        self._chroma_client = PersistentClient(path="./chroma_db");
        self._collection = self._chroma_client.get_or_create_collection(name="customer_sop");

    def init_mock_sop_data(self) -> None:
        """ 首次启动时注入 mock SOP 数据 """
        for i,doc in enumerate(MOCK_SOP_DOCS):
            embedding = self.embed(doc);
            self._collection.add(
                embeddings=[embedding],
                documents=[doc],
                ids=[f"sop_doc_{i}"]
            )   
        print("Succeeded in initialzing SOP Knowledge Base embedding!");

    @traceable(run_type="retriever", name="sop_query_knowledge_base")
    def query_knowledge_base(self,query_text:str) -> str:
        """ 
        检索最相关的 SOP 规则  
        多智能体协同中的‘知识库 Agent’底层检索逻辑
        """
        # 1、将客服提问转化为向量
        query_embedding = self.embed(query_text);

        # 2、从向量库检索最相关的 top_k 条规则
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=1
        )

        if result["documents"] and len(result["documents"][0]) > 0:
            return result['documents'][0][0];

        return "未在知识库中找到相关合规规则. ";

    @traceable(run_type="embedding", name="sop_embed")
    def embed(self,text:str)->list[float]:
        """ 将文本转换为向量 """
        response = self._embedding_client.embeddings.create(
            input=text,
            model=self._settings.zhipu_embedding_model
        )
        return response.data[0].embedding;


_sop_rag_service:Optional[SopRagService] = None;

def get_sop_rag_service(settings:Settings)->SopRagService:
    global _sop_rag_service
    if _sop_rag_service is None:
        _sop_rag_service = SopRagService(settings);
    return _sop_rag_service;