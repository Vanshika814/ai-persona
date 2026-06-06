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

interface Slot {
  date: string;
  time: string;
  datetime: string;
  display: string;
}

function SchedulerWidget() {
  const [slots, setSlots] = useState<Slot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<Slot | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [notes, setNotes] = useState("");
  const [bookingLoading, setBookingLoading] = useState(false);
  const [bookingResult, setBookingResult] = useState<{
    success: boolean;
    meet_link?: string;
    confirmation_message?: string;
    error?: string;
  } | null>(null);

  // Fetch slots on mount
  const fetchSlots = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${BACKEND_URL}/calendar/slots`);
      if (!res.ok) throw new Error("Failed to load slots");
      const data = await res.json();
      setSlots(data.slots || []);
    } catch (err) {
      setError("Unable to retrieve available slots. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSlots();
  }, []);

  const handleBook = async (e: FormEvent) => {
    e.preventDefault();
    if (!selectedSlot || !name || !email) return;

    setBookingLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/calendar/book`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          datetime_str: selectedSlot.datetime,
          attendee_name: name,
          attendee_email: email,
          notes,
        }),
      });
      const data = await res.json();
      setBookingResult(data);
    } catch (err) {
      setBookingResult({
        success: false,
        error: "Booking failed. Please check your internet connection and try again.",
      });
    } finally {
      setBookingLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="mt-3 p-4 bg-white rounded-2xl border border-border-light shadow-sm flex flex-col items-center gap-3 w-full">
        <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        <span className="text-xs text-muted">Checking availability...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mt-3 p-4 bg-white rounded-2xl border border-border-light shadow-sm flex flex-col items-center gap-2 w-full">
        <span className="text-xs text-error text-center">{error}</span>
        <button
          type="button"
          onClick={fetchSlots}
          className="text-xs text-accent font-semibold hover:underline"
        >
          Retry
        </button>
      </div>
    );
  }

  if (bookingResult?.success) {
    return (
      <div className="mt-3 p-5 bg-white rounded-2xl border border-border-light shadow-sm flex flex-col items-center text-center gap-3 animate-fade-in w-full">
        <div className="w-10 h-10 bg-success/10 text-success rounded-full flex items-center justify-center font-bold text-lg">
          ✓
        </div>
        <div className="space-y-1">
          <h4 className="text-sm font-bold text-[#1E1B4B]">Meeting Confirmed!</h4>
          <p className="text-xs text-muted">{bookingResult.confirmation_message}</p>
        </div>
        {bookingResult.meet_link && (
          <a
            href={bookingResult.meet_link}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-accent text-white text-xs font-semibold rounded-xl hover:bg-accent-hover transition-colors shadow-sm"
          >
            Join Google Meet
          </a>
        )}
        <p className="text-[10px] text-muted">A calendar invitation & confirmation email have been sent.</p>
      </div>
    );
  }

  if (selectedSlot) {
    return (
      <div className="mt-3 p-5 bg-white rounded-2xl border border-border-light shadow-sm flex flex-col gap-4 animate-fade-in w-full text-left">
        <div className="flex items-center justify-between border-b border-border-light pb-2">
          <h4 className="text-xs font-bold text-[#1E1B4B]">Enter Booking Details</h4>
          <button
            type="button"
            onClick={() => setSelectedSlot(null)}
            className="text-[11px] text-muted hover:text-foreground font-medium"
          >
            ← Change Time
          </button>
        </div>
        <div className="space-y-1 bg-accent-soft/45 p-2.5 rounded-xl border border-accent/10">
          <span className="text-[10px] uppercase font-bold text-accent tracking-wider block">Selected Slot</span>
          <span className="text-xs font-semibold text-[#1e1b4b]">{selectedSlot.display}</span>
        </div>
        <form onSubmit={handleBook} className="space-y-3">
          <div>
            <label className="block text-[11px] font-semibold text-[#374151] mb-1">Name</label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your Name"
              className="w-full text-xs px-3 py-2 border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent bg-background text-[#1f2937]"
            />
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-[#374151] mb-1">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full text-xs px-3 py-2 border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent bg-background text-[#1f2937]"
            />
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-[#374151] mb-1">Notes (Optional)</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="What would you like to discuss?"
              rows={2}
              className="w-full text-xs px-3 py-2 border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent bg-background resize-none text-[#1f2937]"
            />
          </div>
          {bookingResult?.error && (
            <div className="text-xs text-error font-medium">{bookingResult.error}</div>
          )}
          <button
            type="submit"
            disabled={bookingLoading}
            className="w-full py-2.5 bg-accent hover:bg-accent-hover text-white text-xs font-bold rounded-xl disabled:opacity-50 transition-colors shadow-md flex items-center justify-center gap-1.5"
          >
            {bookingLoading ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Booking...
              </>
            ) : (
              "Confirm Interview"
            )}
          </button>
        </form>
      </div>
    );
  }

  // Group slots by date
  const groupedSlots: { [key: string]: Slot[] } = {};
  slots.forEach((slot) => {
    const dateStr = slot.display.split(" at ")[0];
    if (!groupedSlots[dateStr]) groupedSlots[dateStr] = [];
    groupedSlots[dateStr].push(slot);
  });

  return (
    <div className="mt-3 p-4 bg-white rounded-2xl border border-border-light shadow-sm flex flex-col gap-3 animate-fade-in max-h-[300px] overflow-y-auto w-full text-left">
      <h4 className="text-xs font-bold text-[#1E1B4B] border-b border-border-light pb-2">Select a Time Slot</h4>
      {slots.length === 0 ? (
        <span className="text-xs text-muted text-center py-2">No available slots found on Cal.com.</span>
      ) : (
        <div className="space-y-3">
          {Object.entries(groupedSlots).map(([dateLabel, slotList]) => (
            <div key={dateLabel} className="space-y-1.5">
              <span className="text-[10px] uppercase font-bold text-muted tracking-wider block">{dateLabel}</span>
              <div className="grid grid-cols-2 gap-1.5">
                {slotList.map((slot) => {
                  const timeLabel = slot.display.split(" at ")[1]?.replace(" IST", "") || slot.time;
                  return (
                    <button
                      key={slot.datetime}
                      type="button"
                      onClick={() => setSelectedSlot(slot)}
                      className="px-2.5 py-1.5 text-xs font-medium text-accent bg-accent-soft rounded-lg hover:bg-accent hover:text-white transition-all text-center select-none active:scale-[0.98]"
                    >
                      {timeLabel}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
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
          {messages.map((msg) => {
            const hasWidget = msg.role === "assistant" && msg.content.includes("[SCHEDULER_WIDGET]");
            const cleanContent = hasWidget
              ? msg.content.replace("[SCHEDULER_WIDGET]", "").trim()
              : msg.content;

            return (
              <div
                key={msg.id}
                className={`flex animate-fade-in ${
                  msg.role === "user" ? "justify-end" : "items-end gap-3"
                }`}
              >
                {/* AI avatar */}
                {msg.role === "assistant" && <AiAvatar />}

                {/* Bubble container to hold text bubble and/or widget */}
                <div className="flex flex-col max-w-[80%] sm:max-w-[70%]">
                  {cleanContent && (
                    <div
                      className={`px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words shadow-sm ${
                        msg.role === "user"
                          ? "bg-user-bubble text-user-bubble-text rounded-2xl rounded-br-none"
                          : "bg-ai-bubble text-ai-bubble-text rounded-2xl rounded-bl-none border border-border-light"
                      }`}
                    >
                      {cleanContent}
                    </div>
                  )}

                  {hasWidget && <SchedulerWidget />}
                </div>
              </div>
            );
          })}

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
