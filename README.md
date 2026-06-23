# DeepSeek Chatbot MVP

一个基于 DeepSeek API 的本地 chatbot MVP：

- 后端：Python + FastAPI
- AI 框架：LangChain
- 模型：DeepSeek API，默认 `deepseek-v4-flash`
- 前端：Vite + React
- 会话：使用 `session_id` 区分多轮对话，历史记录暂存在内存中
- RAG：支持上传 `.txt` / `.md` 到本地 Chroma 知识库并返回引用来源

DeepSeek API 兼容 OpenAI API 格式，官方文档给出的 OpenAI `base_url` 是 `https://api.deepseek.com`。

## 目录结构

```text
backend/
  app/
    main.py          # FastAPI 路由
    chat_service.py  # LangChain + DeepSeek 调用和会话历史
    rag_service.py   # 文档上传、切分、embedding、Chroma 检索
    config.py        # 环境变量配置
    schemas.py       # 请求/响应模型
  storage/           # 本地上传文件和 Chroma 数据，已被 gitignore 忽略
  requirements.txt
  .env.example
frontend/
  src/
    App.jsx
    styles.css
  package.json
  vite.config.js
```

## 1. 配置 DeepSeek API Key

```bash
cp backend/.env.example backend/.env
```

编辑 `backend/.env`：

```bash
DEEPSEEK_API_KEY=你的 DeepSeek API Key
DEEPSEEK_MODEL=deepseek-v4-flash
RAG_EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
```

## 2. 启动后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8010
```

健康检查：

```bash
curl http://localhost:8010/api/health
```

普通聊天接口：

```bash
curl -X POST http://localhost:8010/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"你好，请用一句话介绍你自己。"}'
```

流式聊天接口：

```bash
curl -N -X POST http://localhost:8010/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"写一个三行的产品介绍。"}'
```

多轮对话传入返回的 `session_id`：

```bash
curl -X POST http://localhost:8010/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"上一次返回的 session_id","message":"继续展开第二点。"}'
```

## 3. 使用知识库 RAG

上传 `.txt` 或 `.md` 文档到知识库：

```bash
curl -X POST http://localhost:8010/api/knowledge-bases/default/documents \
  -F "file=@/path/to/demo.md"
```

使用知识库进行普通聊天：

```bash
curl -X POST http://localhost:8010/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "根据知识库总结一下核心内容",
    "use_knowledge_base": true,
    "knowledge_base_id": "default"
  }'
```

使用知识库进行流式聊天：

```bash
curl -N -X POST http://localhost:8010/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "根据知识库列出三个要点",
    "use_knowledge_base": true,
    "knowledge_base_id": "default"
  }'
```

流式接口会发送这些 SSE 事件：

```text
session
sources
token
done
```

第一次使用本地 embedding 模型时，`sentence-transformers` 可能需要下载模型文件。

## 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

打开：

```text
http://localhost:5173
```

Vite 已经配置 `/api` 代理到 `http://localhost:8010`。如果你想显式指定 API 地址，可以复制并编辑：

```bash
cp frontend/.env.example frontend/.env
```

```bash
VITE_API_BASE_URL=http://localhost:8010
```

前端侧边栏支持：

- 输入 `Knowledge Base ID`
- 上传 `.txt` / `.md`
- 打开或关闭知识库检索
- 在 AI 回复下方查看 sources

## 5. 运行测试

```bash
cd backend
source .venv/bin/activate
pytest
```

## 后续可扩展方向

- 用 Redis 或 PostgreSQL 替换内存会话历史
- 增加登录和用户隔离
- 增加文档列表、删除文档、重建索引
- 增加 hybrid search、rerank 和检索评测
- 增加工具调用和模型参数配置


## 评估体系 — LangSmith Datasets + Evaluators

cd backend

# 同步 Dataset 到 LangSmith
python -m app.eval --mode sync

# 跑 LangSmith Experiment（需 LANGCHAIN_API_KEY + ZHIPU_API_KEY）
python -m app.eval --mode langsmith --experiment-prefix copilot-routing

# 本地终端报告
python -m app.eval --mode local

pytest tests/test_evaluators.py tests/test_eval_runner.py -q
# 12 passed
