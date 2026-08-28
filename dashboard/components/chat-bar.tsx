"use client";
import { useState, useRef, useEffect } from "react";
import { Send, Loader2, MessageSquare, X, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { useSendMessage } from "@/lib/mobile-api";

interface Citation {
  id: string;
  content: string;
  source?: string;
  created_at?: string;
}

interface Message {
  role: "user" | "assistant" | "system";
  content: string;
  citations?: Citation[];
  timestamp: Date;
}

type ContentPart = { type: "text"; value: string } | { type: "cite"; n: number };

const CITATION_RE = /\[Memory (\d+)\]/g;

function splitCitations(content: string): ContentPart[] {
  const parts: ContentPart[] = [];
  let last = 0;
  for (const m of content.matchAll(CITATION_RE)) {
    const idx = m.index ?? 0;
    if (idx > last) parts.push({ type: "text", value: content.slice(last, idx) });
    parts.push({ type: "cite", n: Number(m[1]) });
    last = idx + m[0].length;
  }
  if (last < content.length) parts.push({ type: "text", value: content.slice(last) });
  return parts;
}

export function ChatBar() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [openCitation, setOpenCitation] = useState<{ msgIndex: number; n: number } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const sendMessage = useSendMessage();
  const isLoading = submitting || sendMessage.isPending;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        setExpanded(true);
      }
      if (e.key === "Escape" && expanded) setExpanded(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [expanded]);

  const handleSubmit = async () => {
    if (!input.trim() || isLoading) return;
    const content = input.trim();
    setInput("");
    setExpanded(true);
    setOpenCitation(null);
    setMessages(prev => [...prev, { role: "user", content, timestamp: new Date() }]);
    setSubmitting(true);
    try {
      // Lazily create a session-scoped conversation on the first submit; reuse
      // its id for every subsequent submit so the thread stays grounded.
      let id = conversationId;
      if (!id) {
        const created = await api.conversations.create();
        id = created?.data?.id;
        if (!id) throw new Error("Could not start a conversation.");
        setConversationId(id);
      }
      const res = await sendMessage.mutateAsync({ id, content });
      setMessages(prev => [...prev, {
        role: "assistant",
        content: res?.message?.content || "(no answer)",
        citations: res?.citations ?? [],
        timestamp: new Date(),
      }]);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Something went wrong — check your connection and try again.";
      setMessages(prev => [...prev, { role: "system", content: message, timestamp: new Date() }]);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="border-t border-line bg-surface">
      {expanded && messages.length > 0 && (
        <div className="max-h-72 overflow-y-auto px-6 py-3 space-y-3 border-b border-line">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-accent" />
              <span className="text-xs text-ink-low font-medium">Conversation</span>
            </div>
            <button onClick={() => setExpanded(false)} className="text-ink-low hover:text-ink-mid p-0.5 rounded hover:bg-surface-3">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          {messages.map((m, i) => (
            <div key={i} className={`flex gap-2.5 ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              {m.role !== "user" && (
                <div className="w-6 h-6 rounded-full bg-accent-soft flex items-center justify-center shrink-0 mt-0.5">
                  <MessageSquare className="w-3 h-3 text-accent" />
                </div>
              )}
              <div className="flex flex-col gap-1.5 max-w-[70%]">
                <div className={`rounded-xl px-3.5 py-2 text-sm leading-relaxed ${
                  m.role === "user"
                    ? "bg-accent text-accent-fg"
                    : m.role === "system"
                    ? "bg-danger-soft text-danger border border-danger/30"
                    : "bg-surface-3 text-ink"
                }`}>
                  {m.role === "assistant"
                    ? splitCitations(m.content).map((p, pi) =>
                        p.type === "text" ? (
                          <span key={pi}>{p.value}</span>
                        ) : (
                          <button
                            key={pi}
                            onClick={() =>
                              setOpenCitation(prev =>
                                prev?.msgIndex === i && prev.n === p.n ? null : { msgIndex: i, n: p.n }
                              )
                            }
                            title={m.citations?.[p.n - 1]?.content?.slice(0, 160)}
                            className={`inline-flex items-center justify-center min-w-[18px] h-[18px] px-1.5 mx-0.5 rounded-full border text-[10px] font-semibold align-super transition-colors ${
                              openCitation?.msgIndex === i && openCitation.n === p.n
                                ? "bg-accent text-accent-fg border-accent"
                                : "bg-accent-soft text-accent-text border-accent-border hover:bg-accent-soft"
                            }`}
                          >
                            {p.n}
                          </button>
                        ),
                      )
                    : m.content}
                </div>
                {openCitation?.msgIndex === i && (
                  <div className="rounded-lg border border-accent-border bg-accent-soft/60 px-3 py-2 text-xs text-ink-mid leading-relaxed">
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="text-[10px] font-medium text-accent-text uppercase tracking-wide">
                        Memory {openCitation.n}
                      </span>
                      <button onClick={() => setOpenCitation(null)} className="text-ink-low hover:text-ink-mid">
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                    <p className="whitespace-pre-wrap">
                      {m.citations?.[openCitation.n - 1]?.content || "Memory unavailable."}
                    </p>
                  </div>
                )}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex gap-2.5 justify-start">
              <div className="w-6 h-6 rounded-full bg-accent-soft flex items-center justify-center shrink-0 mt-0.5">
                <MessageSquare className="w-3 h-3 text-accent" />
              </div>
              <div className="rounded-xl px-3.5 py-2 text-sm leading-relaxed bg-surface-3 text-ink-low animate-pulse">
                Thinking…
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      )}
      <div className="flex items-center gap-3 px-6 py-3">
        <div className="flex-1 relative">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleSubmit()}
            onFocus={() => messages.length > 0 && setExpanded(true)}
            placeholder="Ask about your memories..."
            disabled={isLoading}
            className="w-full bg-surface-2 border border-line rounded-xl px-4 py-2.5 text-sm text-ink placeholder-ink-low focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft transition-all disabled:opacity-50"
          />
          {!input && (
            <kbd className="absolute right-3 top-1/2 -translate-y-1/2 px-1.5 py-0.5 rounded bg-surface border border-line text-[10px] text-ink-low font-mono">⌘K</kbd>
          )}
        </div>
        <button
          onClick={handleSubmit}
          disabled={!input.trim() || isLoading}
          className="p-2.5 rounded-xl bg-accent text-accent-fg hover:bg-accent-hover shadow-sm disabled:opacity-30 disabled:cursor-not-allowed transition-all hover:shadow"
        >
          {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );
}
