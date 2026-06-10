import { Bot, Loader2, RefreshCcw, Send, UserRound, Waves } from "lucide-react";
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

function createMessage(role, content) {
  return {
    id: crypto.randomUUID(),
    role,
    content
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
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef(null);

  const canSend = useMemo(() => input.trim().length > 0 && !isLoading, [input, isLoading]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
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

  async function sendRegularMessage(content, assistantId) {
    const response = await fetch(buildApiUrl("/api/chat"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: content,
        session_id: sessionId || undefined,
        system_prompt: systemPrompt || undefined
      })
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || "聊天接口返回错误。");
    }

    const data = await response.json();
    setSessionId(data.session_id);
    setMessages((current) =>
      current.map((message) =>
        message.id === assistantId ? { ...message, content: data.message } : message
      )
    );
  }

  async function sendStreamingMessage(content, assistantId) {
    const response = await fetch(buildApiUrl("/api/chat/stream"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: content,
        session_id: sessionId || undefined,
        system_prompt: systemPrompt || undefined
      })
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || "流式接口返回错误。");
    }

    await parseSseStream(response, {
      session: (payload) => {
        setSessionId(payload.session_id);
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

        <div className="messages" aria-live="polite">
          {messages.map((message) => (
            <article className={`message ${message.role}`} key={message.id}>
              <span className="avatar">
                {message.role === "user" ? <UserRound size={18} /> : <Bot size={18} />}
              </span>
              <div className="bubble">
                {message.content || (isLoading ? <Loader2 className="spin" size={18} /> : null)}
              </div>
            </article>
          ))}
          <div ref={scrollRef} />
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
