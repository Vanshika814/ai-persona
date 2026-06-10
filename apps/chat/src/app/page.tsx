"use client";

import { useState, useRef, useEffect, useCallback, type FormEvent, type KeyboardEvent } from "react";
import ReactMarkdown from "react-markdown";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}
const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

const WELCOME_MESSAGE: Message = {
  id: "welcome",
  role: "assistant",
  content:
    "Hi! I'm Vanshika's AI representative. Ask me about her background, projects, or schedule an interview.",
};

function AiAvatar({ animate }: { animate?: boolean }) {
  return (
    <div
      className={`flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full bg-accent-soft text-accent text-sm font-bold select-none ${animate ? "avatar-glow" : ""
        }`}
    >
      V
    </div>
  );
}
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



interface Slot {
  display: string;
  id: string;
}

function parseSlots(content: string): { cleanContent: string; slots: Slot[] } {
  const slots: Slot[] = [];
  const lines = content.split("\n");
  const cleanLines: string[] = [];

  const slotRegex = /^[-*•]\s*(.*?)\s*\[id:\s*(.*?)\]$/;

  for (const line of lines) {
    const match = line.trim().match(slotRegex);
    if (match) {
      slots.push({
        display: match[1].trim(),
        id: match[2].trim(),
      });
    } else {
      cleanLines.push(line);
    }
  }

  let cleanContent = cleanLines.join("\n").trim();
  cleanContent = cleanContent.replace(/\n{3,}/g, "\n\n");

  return {
    cleanContent,
    slots,
  };
}

function formatSlotDisplay(display: string): string {
  try {
    const parts = display.split(",");
    if (parts.length >= 2) {
      const datePart = parts[0].trim();
      const timeMatch = parts[1].match(/at\s+(.*?)\s*(?:IST|$)/i);
      if (timeMatch) {
        const timePart = timeMatch[1].trim();
        return `${datePart} • ${timePart}`;
      }
    }
  } catch (e) {
    // fallback
  }
  return display;
}

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
  async function submitMessage(contentToSend: string) {
    if (isStreaming) return;

    setError(null);

    // Add user message
    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: contentToSend,
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
          message: contentToSend,
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
        console.log("RAW BUFFER:");
        console.log(buffer);
        // Process complete SSE lines
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? ""; // keep incomplete event

        for (const event of events) {
          const payload = event
            .split("\n")
            .map((line) =>
              line.startsWith("data: ")
                ? line.slice(6)
                : line
            )
            .join("\n");

          if (!payload) continue;

          if (payload === "[DONE]") {
            continue;
          }

          if (payload.startsWith("[ERROR]")) {
            setError(payload.slice(8));
            continue;
          }
          console.log("PAYLOAD:");
          console.log(payload);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiId
                ? {
                  ...m, content: m.content.length === 0
                    ? payload
                    : m.content + "\n\n" + payload
                }
                : m
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

  async function handleSend() {
    const text = input.trim();
    if (!text || isStreaming) return;
    setInput("");
    await submitMessage(text);
  }

  async function handleSelectSlot(slot: Slot) {
    const content = `Confirming slot: ${slot.display} [id: ${slot.id}]`;
    await submitMessage(content);
  }

  function isLastAssistantMessage(msgId: string): boolean {
    const assistantMsgs = messages.filter((m) => m.role === "assistant");
    return assistantMsgs.length > 0 && assistantMsgs[assistantMsgs.length - 1].id === msgId;
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
              className={`flex animate-fade-in ${msg.role === "user" ? "justify-end" : "items-end gap-3"
                }`}
            >
              {/* AI avatar */}
              {msg.role === "assistant" && <AiAvatar />}

              {/* Bubble container to hold text bubble */}
              <div className="flex flex-col max-w-[80%] sm:max-w-[70%]">
                {msg.content && (
                  <>
                    <div
                      className={`px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words shadow-sm ${msg.role === "user"
                        ? "bg-user-bubble text-user-bubble-text rounded-2xl rounded-br-none"
                        : "bg-ai-bubble text-ai-bubble-text rounded-2xl rounded-bl-none border border-border-light"
                        }`}
                    >
                      {msg.role === "assistant" ? (
                        <ReactMarkdown
                          components={{
                            p: ({ children }) => <p style={{ margin: '0 0 6px 0' }}>{children}</p>,
                            ul: ({ children }) => <ul style={{ margin: '4px 0', paddingLeft: '16px' }}>{children}</ul>,
                            li: ({ children }) => <li style={{ marginBottom: '2px' }}>{children}</li>,
                            strong: ({ children }) => <strong style={{ fontWeight: 500 }}>{children}</strong>,
                          }}
                        >
                          {parseSlots(msg.content).cleanContent}
                        </ReactMarkdown>
                      ) : (
                        msg.content.replace(/^Confirming slot:\s*/, "").replace(/\s*\[id:\s*.*?\]$/, "")
                      )}
                    </div>

                    {/* Render slot buttons if it's an assistant message with slots */}
                    {msg.role === "assistant" && (() => {
                      const { slots } = parseSlots(msg.content);
                      if (slots.length === 0) return null;
                      return (
                        <div className="mt-3 flex flex-col gap-2 w-full">
                          {slots.map((slot) => (
                            <button
                              key={slot.id}
                              disabled={isStreaming || !isLastAssistantMessage(msg.id)}
                              onClick={() => handleSelectSlot(slot)}
                              className="w-full text-center px-4 py-2.5 rounded-xl border border-accent/20 bg-accent-soft text-accent hover:bg-accent hover:text-white transition-all text-sm font-semibold shadow-sm disabled:opacity-50 disabled:pointer-events-none"
                            >
                              [ {formatSlotDisplay(slot.display)} ]
                            </button>
                          ))}
                        </div>
                      );
                    })()}
                  </>
                )}
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
