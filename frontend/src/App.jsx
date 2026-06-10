import {
  Bot,
  Database,
  Loader2,
  RefreshCcw,
  Send,
  Upload,
  UserRound,
  Waves
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const SESSION_KEY = "deepseek-chatbot-session-id";

const starterMessages = [
  {
    id: "welcome",
    role: "assistant",
    content: "你好，我是 DeepSeek Chatbot。"
  }
];

function createMessage(role, content, sources = []) {
  return {
    id: crypto.randomUUID(),
    role,
    content,
    sources
  };
}

function buildApiUrl(path) {
  return `${API_BASE_URL}${path}`;
}

async function parseSseStream(response, handlers) {
  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("当前浏览器不支持流式读取。");
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";

    for (const rawEvent of events) {
      const lines = rawEvent.split("\n");
      const eventName = lines.find((line) => line.startsWith("event:"))?.slice(6).trim();
      const dataLine = lines.find((line) => line.startsWith("data:"))?.slice(5).trim();
      if (!eventName || !dataLine) {
        continue;
      }

      const payload = JSON.parse(dataLine);
      handlers[eventName]?.(payload);
    }
  }
}

export default function App() {
  const [messages, setMessages] = useState(starterMessages);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(SESSION_KEY) || "");
  const [systemPrompt, setSystemPrompt] = useState(
    "You are a helpful, concise chatbot. Answer in the user's language."
  );
  const [isStreaming, setIsStreaming] = useState(true);
  const [useKnowledgeBase, setUseKnowledgeBase] = useState(false);
  const [knowledgeBaseId, setKnowledgeBaseId] = useState("default");
  const [uploadFile, setUploadFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const messagesRef = useRef(null);

  const canSend = useMemo(() => input.trim().length > 0 && !isLoading, [input, isLoading]);
  const canUpload = useMemo(
    () => Boolean(uploadFile) && knowledgeBaseId.trim().length > 0 && !isUploading,
    [uploadFile, knowledgeBaseId, isUploading]
  );

  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    if (sessionId) {
      localStorage.setItem(SESSION_KEY, sessionId);
    }
  }, [sessionId]);

  async function sendMessage(event) {
    event.preventDefault();
    const content = input.trim();
    if (!content || isLoading) {
      return;
    }

    if (useKnowledgeBase && !knowledgeBaseId.trim()) {
      setError("请先输入 Knowledge Base ID。");
      return;
    }

    setError("");
    setInput("");
    setIsLoading(true);

    const assistantMessage = createMessage("assistant", "");
    setMessages((current) => [...current, createMessage("user", content), assistantMessage]);

    try {
      if (isStreaming) {
        await sendStreamingMessage(content, assistantMessage.id);
      } else {
        await sendRegularMessage(content, assistantMessage.id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "请求失败。");
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantMessage.id
            ? { ...message, content: "这次请求没有成功。" }
            : message
        )
      );
    } finally {
      setIsLoading(false);
    }
  }

  function buildChatPayload(content) {
    return {
      message: content,
      session_id: sessionId || undefined,
      system_prompt: systemPrompt || undefined,
      use_knowledge_base: useKnowledgeBase,
      knowledge_base_id: useKnowledgeBase ? knowledgeBaseId.trim() : undefined
    };
  }

  async function sendRegularMessage(content, assistantId) {
    const response = await fetch(buildApiUrl("/api/chat"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildChatPayload(content))
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || "聊天接口返回错误。");
    }

    const data = await response.json();
    setSessionId(data.session_id);
    setMessages((current) =>
      current.map((message) =>
        message.id === assistantId
          ? { ...message, content: data.message, sources: data.sources || [] }
          : message
      )
    );
  }

  async function sendStreamingMessage(content, assistantId) {
    const response = await fetch(buildApiUrl("/api/chat/stream"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildChatPayload(content))
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || "流式接口返回错误。");
    }

    await parseSseStream(response, {
      session: (payload) => {
        setSessionId(payload.session_id);
      },
      sources: (payload) => {
        setMessages((current) =>
          current.map((message) =>
            message.id === assistantId
              ? { ...message, sources: payload.sources || [] }
              : message
          )
        );
      },
      token: (payload) => {
        setMessages((current) =>
          current.map((message) =>
            message.id === assistantId
              ? { ...message, content: `${message.content}${payload.content}` }
              : message
          )
        );
      },
      error: (payload) => {
        throw new Error(payload.message || "流式接口返回错误。");
      }
    });
  }

  async function uploadDocument(event) {
    event.preventDefault();

    const kbId = knowledgeBaseId.trim();
    if (!kbId) {
      setUploadStatus("请先输入 Knowledge Base ID。");
      return;
    }

    if (!uploadFile) {
      setUploadStatus("请选择 .txt 或 .md 文件。");
      return;
    }

    const filename = uploadFile.name.toLowerCase();
    if (!filename.endsWith(".txt") && !filename.endsWith(".md")) {
      setUploadStatus("当前只支持 .txt 和 .md 文件。");
      return;
    }

    setIsUploading(true);
    setUploadStatus("");

    try {
      const formData = new FormData();
      formData.append("file", uploadFile);

      const response = await fetch(
        buildApiUrl(`/api/knowledge-bases/${encodeURIComponent(kbId)}/documents`),
        {
          method: "POST",
          body: formData
        }
      );

      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "上传失败。");
      }

      const data = await response.json();
      setUseKnowledgeBase(true);
      setUploadFile(null);
      setUploadStatus(`已上传 ${data.filename}，切分为 ${data.chunks} 个片段。`);
    } catch (err) {
      setUploadStatus(err instanceof Error ? err.message : "上传失败。");
    } finally {
      setIsUploading(false);
    }
  }

  async function resetSession() {
    const previousSessionId = sessionId;
    setSessionId("");
    localStorage.removeItem(SESSION_KEY);
    setMessages(starterMessages);
    setError("");

    if (previousSessionId) {
      await fetch(buildApiUrl(`/api/sessions/${previousSessionId}`), { method: "DELETE" }).catch(
        () => undefined
      );
    }
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <Bot size={24} />
          </span>
          <div>
            <h1>DeepSeek Chatbot</h1>
            <p>FastAPI · LangChain · React</p>
          </div>
        </div>

        <label className="field">
          <span>System Prompt</span>
          <textarea
            value={systemPrompt}
            onChange={(event) => setSystemPrompt(event.target.value)}
            rows={7}
          />
        </label>

        <div className="toggle-row">
          <span>Stream</span>
          <button
            type="button"
            className={`switch ${isStreaming ? "is-on" : ""}`}
            onClick={() => setIsStreaming((value) => !value)}
            aria-pressed={isStreaming}
          >
            <span />
          </button>
        </div>

        <div className="toggle-row">
          <span>Knowledge Base</span>
          <button
            type="button"
            className={`switch ${useKnowledgeBase ? "is-on" : ""}`}
            onClick={() => setUseKnowledgeBase((value) => !value)}
            aria-pressed={useKnowledgeBase}
          >
            <span />
          </button>
        </div>

        <label className="field">
          <span>Knowledge Base ID</span>
          <input
            value={knowledgeBaseId}
            onChange={(event) => setKnowledgeBaseId(event.target.value)}
            placeholder="default"
          />
        </label>

        <form className="upload-box" onSubmit={uploadDocument}>
          <label className="file-picker">
            <Database size={17} />
            <span>{uploadFile ? uploadFile.name : "选择 .txt / .md"}</span>
            <input
              type="file"
              accept=".txt,.md,text/plain,text/markdown"
              onChange={(event) => setUploadFile(event.target.files?.[0] || null)}
            />
          </label>

          <button type="submit" disabled={!canUpload}>
            {isUploading ? <Loader2 className="spin" size={17} /> : <Upload size={17} />}
            Upload
          </button>

          {uploadStatus ? <p className="upload-status">{uploadStatus}</p> : null}
        </form>

        <div className="session-box">
          <span>Session</span>
          <code>{sessionId || "new"}</code>
        </div>

        <button type="button" className="secondary-button" onClick={resetSession}>
          <RefreshCcw size={17} />
          New Session
        </button>
      </aside>

      <section className="chat-panel">
        <header className="chat-header">
          <div>
            <span className="eyebrow">MVP Chat</span>
            <h2>DeepSeek API Assistant</h2>
          </div>
          <div className="status-pill">
            <Waves size={16} />
            {isStreaming ? "Streaming" : "Standard"}
          </div>
        </header>

        <div className="messages" aria-live="polite" ref={messagesRef}>
          {messages.map((message) => (
            <article className={`message ${message.role}`} key={message.id}>
              <span className="avatar">
                {message.role === "user" ? <UserRound size={18} /> : <Bot size={18} />}
              </span>
              <div className="bubble">
                <div>
                  {message.content || (isLoading ? <Loader2 className="spin" size={18} /> : null)}
                </div>
                {message.sources?.length ? (
                  <div className="sources">
                    <span>Sources</span>
                    {message.sources.map((source) => (
                      <details key={source.chunk_id || `${source.filename}-${source.content}`}>
                        <summary>{source.filename || "Knowledge chunk"}</summary>
                        <p>{source.content}</p>
                      </details>
                    ))}
                  </div>
                ) : null}
              </div>
            </article>
          ))}
        </div>

        {error ? <div className="error-banner">{error}</div> : null}

        <form className="composer" onSubmit={sendMessage}>
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="输入消息..."
            rows={1}
            disabled={isLoading}
          />
          <button type="submit" disabled={!canSend} aria-label="发送">
            {isLoading ? <Loader2 className="spin" size={20} /> : <Send size={20} />}
          </button>
        </form>
      </section>
    </main>
  );
}
