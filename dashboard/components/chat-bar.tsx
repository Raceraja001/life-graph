"use client";
import { useState, useRef, useEffect } from "react";
import { Send, Loader2, MessageSquare, X, Sparkles } from "lucide-react";
import { useCapture, useRoute } from "@/lib/hooks";

interface Message {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
}

export function ChatBar() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [expanded, setExpanded] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const capture = useCapture();
  const route = useRoute();
  const isLoading = capture.isPending || route.isPending;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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
    const msg = input.trim();
    setInput("");
    setExpanded(true);
    setMessages(prev => [...prev, { role: "user", content: msg, timestamp: new Date() }]);
    try {
      capture.mutate({ surface: "dashboard", content: msg });
      const response = await route.mutateAsync(msg);
      setMessages(prev => [...prev, {
        role: "assistant",
        content: response?.response || response?.result || JSON.stringify(response),
        timestamp: new Date(),
      }]);
    } catch (err: any) {
      setMessages(prev => [...prev, { role: "system", content: `Error: ${err.message}`, timestamp: new Date() }]);
    }
  };

  return (
    <div className="border-t border-zinc-200 bg-white">
      {expanded && messages.length > 0 && (
        <div className="max-h-72 overflow-y-auto px-6 py-3 space-y-3 border-b border-zinc-100">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-emerald-500" />
              <span className="text-xs text-zinc-400 font-medium">Conversation</span>
            </div>
            <button onClick={() => setExpanded(false)} className="text-zinc-400 hover:text-zinc-600 p-0.5 rounded hover:bg-zinc-100">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          {messages.map((m, i) => (
            <div key={i} className={`flex gap-2.5 ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              {m.role !== "user" && (
                <div className="w-6 h-6 rounded-full bg-emerald-100 flex items-center justify-center shrink-0 mt-0.5">
                  <MessageSquare className="w-3 h-3 text-emerald-600" />
                </div>
              )}
              <div className={`max-w-[70%] rounded-xl px-3.5 py-2 text-sm leading-relaxed ${
                m.role === "user"
                  ? "bg-emerald-600 text-white"
                  : m.role === "system"
                  ? "bg-red-50 text-red-700 border border-red-100"
                  : "bg-zinc-100 text-zinc-700"
              }`}>
                {m.content}
              </div>
            </div>
          ))}
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
            placeholder="Type a thought, question, or decision..."
            disabled={isLoading}
            className="w-full bg-zinc-50 border border-zinc-200 rounded-xl px-4 py-2.5 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100 transition-all disabled:opacity-50"
          />
          {!input && (
            <kbd className="absolute right-3 top-1/2 -translate-y-1/2 px-1.5 py-0.5 rounded bg-white border border-zinc-200 text-[10px] text-zinc-400 font-mono">⌘K</kbd>
          )}
        </div>
        <button
          onClick={handleSubmit}
          disabled={!input.trim() || isLoading}
          className="p-2.5 rounded-xl bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm disabled:opacity-30 disabled:cursor-not-allowed transition-all hover:shadow"
        >
          {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );
}
