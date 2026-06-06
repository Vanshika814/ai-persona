"use client";

import { useState, useRef, useEffect, useCallback, type FormEvent, type KeyboardEvent } from "react";

/* ──────────────────────────────────────────────
   Types
   ────────────────────────────────────────────── */

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

/* ──────────────────────────────────────────────
   Constants
   ────────────────────────────────────────────── */

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

const WELCOME_MESSAGE: Message = {
  id: "welcome",
  role: "assistant",
  content:
    "Hi! I'm Vanshika's AI representative. Ask me about her background, projects, or schedule an interview.",
};

/* ──────────────────────────────────────────────
   Avatar component
   ────────────────────────────────────────────── */

function AiAvatar({ animate }: { animate?: boolean }) {
  return (
    <div
      className={`flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full bg-accent-soft text-accent text-sm font-bold select-none ${
        animate ? "avatar-glow" : ""
      }`}
    >
      V
    </div>
  );
}

/* ──────────────────────────────────────────────
   Typing indicator
   ────────────────────────────────────────────── */

function TypingIndicator() {
  return (
    <div className="flex items-end gap-3 animate-fade-in">
      <AiAvatar animate />
      <div className="flex items-center gap-1.5 px-4 py-3 rounded-2xl bg-ai-bubble rounded-bl-md">
        <span className="typing-dot w-2 h-2 rounded-full bg-muted inline-block" />
        <span className="typing-dot w-2 h-2 rounded-full bg-muted inline-block" />
        <span className="typing-dot w-2 h-2 rounded-full bg-muted inline-block" />
      </div>
    </div>
  );
}

/* ──────────────────────────────────────────────
   Send icon
   ────────────────────────────────────────────── */

function SendIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="currentColor"
      className="w-5 h-5"
    >
      <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
    </svg>
  );
}

/* ──────────────────────────────────────────────
   Main chat page
   ────────────────────────────────────────────── */

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  /* ── Auto-scroll ── */
  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isStreaming, scrollToBottom]);

  /* ── Build conversation history (excluding welcome) ── */
  function buildHistory(): { role: string; content: string }[] {
    return messages
      .filter((m) => m.id !== "welcome")
      .map((m) => ({ role: m.role, content: m.content }));
  }

  /* ── Send message via SSE ── */
  async function handleSend() {
    const text = input.trim();
    if (!text || isStreaming) return;

    setError(null);
    setInput("");

    // Add user message
    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
    };
    const history = buildHistory();
    setMessages((prev) => [...prev, userMsg]);

    // Add placeholder AI message
    const aiId = `ai-${Date.now()}`;
    const aiMsg: Message = { id: aiId, role: "assistant", content: "" };
    setMessages((prev) => [...prev, aiMsg]);
    setIsStreaming(true);

    try {
      const res = await fetch(`${BACKEND_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          conversation_history: history,
        }),
      });

      if (!res.ok) {
        throw new Error(`Server responded with ${res.status}`);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE lines
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? ""; // keep incomplete line in buffer

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6); // strip "data: "

          if (payload === "[DONE]") {
            break;
          }

          if (payload.startsWith("[ERROR]")) {
            setError(payload.slice(8));
            break;
          }

          // Append chunk to the AI message
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiId ? { ...m, content: m.content + payload } : m
            )
          );
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Connection failed";
      setError(msg);
      // Remove empty AI placeholder on total failure
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.id === aiId && last.content === "") {
          return prev.slice(0, -1);
        }
        return prev;
      });
    } finally {
      setIsStreaming(false);
      inputRef.current?.focus();
    }
  }

  /* ── Form / keyboard handlers ── */
  function onSubmit(e: FormEvent) {
    e.preventDefault();
    handleSend();
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  /* ── Auto-resize textarea ── */
  function onInputChange(value: string) {
    setInput(value);
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 160)}px`;
    }
  }

  /* ──────────────────────────────────────────────
     Render
     ────────────────────────────────────────────── */

  return (
    <div className="min-h-screen w-full bg-background py-12 px-4 sm:px-6 md:px-8 overflow-y-auto flex flex-col justify-start items-center">
      {/* ── Top Badge / Capsule ── */}
      <div className="inline-flex items-center justify-center bg-[#E5E7EB] border border-border px-5 py-1.5 rounded-full text-sm font-semibold text-[#374151] mb-6 shadow-sm select-none">
        Hi, I'm Vanshika
      </div>

      {/* ── Main Heading ── */}
      <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold text-[#1E1B4B] text-center mb-4 tracking-tight leading-tight">
        Meet ME, Through AI
      </h1>

      {/* ── Description ── */}
      <p className="text-center text-[#4B5563] max-w-xl text-base sm:text-lg mb-10 leading-relaxed">
        Ask my AI anything about my projects, skills, experience, and how I solve problems.
      </p>

      {/* ── Chat Box Container (Grey Box) ── */}
      <div className="w-full max-w-3xl rounded-3xl bg-surface border border-border shadow-xl overflow-hidden flex flex-col h-[580px] transition-all">
        {/* ── Header inside Chat Box ── */}
        <header className="flex items-center gap-3 px-6 py-4 border-b border-border bg-surface/50 backdrop-blur-sm flex-shrink-0">
          <AiAvatar />
          <div>
            <h2 className="text-sm font-bold text-[#1E1B4B] leading-tight">
              Vanshika Agarwal
            </h2>
            <p className="text-[11px] text-muted">AI Persona · Online</p>
          </div>
          <div className="ml-auto flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
            <span className="text-xs text-muted">Connected</span>
          </div>
        </header>

        {/* ── Scrollable Messages Area ── */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto px-6 py-6 space-y-4 bg-white/40"
        >
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex animate-fade-in ${
                msg.role === "user" ? "justify-end" : "items-end gap-3"
              }`}
            >
              {/* AI avatar */}
              {msg.role === "assistant" && <AiAvatar />}

              {/* Bubble */}
              <div
                className={`max-w-[80%] sm:max-w-[70%] px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words shadow-sm ${
                  msg.role === "user"
                    ? "bg-user-bubble text-user-bubble-text rounded-2xl rounded-br-none"
                    : "bg-ai-bubble text-ai-bubble-text rounded-2xl rounded-bl-none border border-border-light"
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}

          {/* Typing indicator */}
          {isStreaming &&
            messages[messages.length - 1]?.content === "" && (
              <TypingIndicator />
            )}

          {/* Error banner */}
          {error && (
            <div className="flex justify-center animate-fade-in">
              <div className="text-xs text-error bg-error/10 border border-error/20 rounded-lg px-4 py-2">
                {error}
              </div>
            </div>
          )}
        </div>

        {/* ── Input Bar inside Chat Box ── */}
        <div className="border-t border-border bg-surface/50 backdrop-blur-sm px-6 py-4 flex-shrink-0">
          <form
            onSubmit={onSubmit}
            className="flex items-end gap-3"
          >
            <textarea
              ref={inputRef}
              id="chat-input"
              value={input}
              onChange={(e) => onInputChange(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Ask about Vanshika's experience…"
              disabled={isStreaming}
              rows={1}
              className="flex-1 resize-none rounded-xl border border-border bg-white px-4 py-3 text-sm text-[#1f2937] placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent disabled:opacity-50 transition-all shadow-sm"
            />
            <button
              type="submit"
              disabled={isStreaming || !input.trim()}
              id="send-button"
              className="flex items-center justify-center w-11 h-11 rounded-xl bg-accent text-white hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-all active:scale-95 shadow-md"
            >
              <SendIcon />
            </button>
          </form>
          <p className="text-center text-[10px] text-muted mt-2 tracking-wide uppercase font-semibold">
            AI-powered · Answers from Vanshika&apos;s resume &amp; GitHub
          </p>
        </div>
      </div>
    </div>
  );
}
