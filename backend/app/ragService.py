import os
from chromadb import PersistentClient
from openai import OpenAI

# 初始化本地持久化向量数据库
chroma_client = PersistentClient(path="./chroma_db")
# 创建或获取针对客服 SOP 的集合
collection = chroma_client.get_or_create_collection(name="customer_sop")

llm_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)

def init_mock_sop_data():
    """
    初始化注入一些跨境电商客服 SOP 数据
    """
    if collection.count() == 0:
        docs = [
            "TikTok跨境小店政策：因质量问题退货，商家承担跨境运费；非质量问题（不想要了），买家自理运费。",
            "Ozon平台海关包裹拦截规则：包裹一旦进入海外仓或进入海关清关阶段，无法进行物理拦截，只能等投递失败后自动退回。",
            "深圳仓发货规范：每日16:00前生成的订单，必须在当晚22:00前完成打包并扫描进仓。"
        ]
        # 获取 Embedding 向量
        for i, doc in enumerate(docs):
            response = llm_client.embeddings.create(
                input=doc,
                model="text-embedding-3-small"
            )
            embedding = response.data[0].embedding
            collection.add(
                embeddings=[embedding],
                documents=[doc],
                ids=[f"sop_doc_{i}"]
            )
        print(" Succeeded in initializing SOP Knowledge Base embedding!")

def query_knowledge_base(query_text: str) -> str:
    """
    Module 5: 多智能体协同中的‘知识库 Agent’底层检索逻辑
    """
    # 1. 将客服提问转化为向量
    response = llm_client.embeddings.create(
        input=query_text,
        model="text-embedding-3-small"
    )
    query_embedding = response.data[0].embedding
    
    # 2. 从向量库检索最相关的 top_k 条规则
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=1
    )
    
    if results['documents'] and len(results['documents'][0]) > 0:
        return results['documents'][0][0]
    return "未在知识库中找到相关合规规则。"