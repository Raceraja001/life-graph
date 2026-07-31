"use client";
import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Plus, Send, Sparkles } from "lucide-react";
import { LoadingCard, EmptyCard, ErrorCard } from "@/components/mobile/parts";
import { MemorySheet } from "@/components/mobile/memory-sheet";
import { useMobileState } from "@/components/mobile/mobile-state";
import { api } from "@/lib/api";
import { onDistillComplete } from "@/lib/distill-events";
import {
  mapMemory,
  useConversations,
  useConversation,
  useSendMessage,
  useResolveMemory,
  useDistillConversation,
  type MemoryVM,
} from "@/lib/mobile-api";

interface ConversationSummary {
  id: string;
  title: string;
  updated_at: string;
}

interface ChatMessage {
  id: string;
  role: string;
  content: string;
  cited_memory_ids: string[];
  model?: string | null;
  created_at: string;
}

type ContentPart = { type: "text"; value: string } | { type: "cite"; n: number };

const CITATION_RE = /\[Memory (\d+)\]/g;

function splitContent(content: string): ContentPart[] {
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

function fmtDate(iso?: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "" : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function MobileChat() {
  const { online } = useMobileState();
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState(false);
  const [draft, setDraft] = useState("");
  const [selectedMem, setSelectedMem] = useState<MemoryVM | null>(null);
  const [lastSent, setLastSent] = useState<{ messageId: string; citations: MemoryVM[] } | null>(null);
  const [resolvingKey, setResolvingKey] = useState<string | null>(null);

  const conversations = useConversations();
  const thread = useConversation(conversationId);
  const sendMessage = useSendMessage();
  const resolveMemory = useResolveMemory();
  const distill = useDistillConversation();
  const [distillMsg, setDistillMsg] = useState<string | null>(null);

  // Live pointer to the open conversation, for the once-mounted WS subscription.
  const currentConvRef = useRef<string | null>(conversationId);
  useEffect(() => {
    currentConvRef.current = conversationId;
  }, [conversationId]);

  useEffect(() => {
    return onDistillComplete(({ conversationId: eventConvId, newFacts }) => {
      if (!eventConvId || eventConvId !== currentConvRef.current) return;
      setDistillMsg(
        newFacts > 0
          ? `→ ${newFacts} new ${newFacts === 1 ? "fact" : "facts"} pending your approval`
          : "Nothing new to distill",
      );
    });
  }, []);

  const onDistill = async () => {
    if (!conversationId || distill.isPending || !online) return;
    setDistillMsg("Distilling…");
    try {
      await distill.mutateAsync(conversationId);
    } catch {
      setDistillMsg("Couldn’t distill — try again");
    }
  };

  const bottomRef = useRef<HTMLDivElement>(null);
  const msgs: ChatMessage[] = thread.data?.messages ?? [];

  // Reset per-conversation state during render (not in an effect) when the
  // selected conversation changes — see "Adjusting state on a prop change"
  // in the React docs.
  const [renderedConversationId, setRenderedConversationId] = useState(conversationId);
  if (conversationId !== renderedConversationId) {
    setRenderedConversationId(conversationId);
    setLastSent(null);
    setDraft("");
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [msgs.length, sendMessage.isPending]);

  const startNewChat = async () => {
    if (creating || !online) return;
    setCreating(true);
    setCreateError(false);
    try {
      const res = await api.conversations.create();
      const id = res?.data?.id;
      if (id) setConversationId(id);
      else setCreateError(true);
    } catch {
      setCreateError(true);
    } finally {
      setCreating(false);
    }
  };

  const openCitation = async (message: ChatMessage, n: number) => {
    if (lastSent && lastSent.messageId === message.id) {
      const mem = lastSent.citations[n - 1];
      if (mem) setSelectedMem(mem);
      return;
    }
    const memId = message.cited_memory_ids[n - 1];
    if (!memId) return;
    const key = `${message.id}:${n}`;
    setResolvingKey(key);
    try {
      const res = await api.memories.get(memId);
      setSelectedMem(mapMemory(res?.data));
    } catch {
      // couldn't resolve this citation — leave the chip tappable, nothing to show
    } finally {
      setResolvingKey((k) => (k === key ? null : k));
    }
  };

  const submit = async () => {
    const content = draft.trim();
    if (!content || !conversationId || sendMessage.isPending) return;
    setDraft("");
    try {
      const res = await sendMessage.mutateAsync({ id: conversationId, content });
      setLastSent({
        messageId: res.message.id,
        citations: (res.citations ?? []).map(mapMemory),
      });
    } catch {
      setDraft(content); // let the user retry without retyping
    }
  };

  // ── No conversation selected: recent conversations + "New chat" ──────
  if (!conversationId) {
    const rows: ConversationSummary[] = conversations.data ?? [];
    return (
      <>
        <button
          onClick={() => void startNewChat()}
          disabled={creating || !online}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "8px",
            height: "44px",
            border: 0,
            borderRadius: "var(--radius-lg)",
            background: "var(--accent)",
            color: "var(--accent-fg)",
            fontFamily: "inherit",
            fontSize: "var(--ui-text)",
            fontWeight: "var(--fw-bold)",
            cursor: creating || !online ? "default" : "pointer",
            opacity: creating || !online ? 0.6 : 1,
          }}
        >
          <Plus width={16} height={16} /> {creating ? "Starting…" : "New chat"}
        </button>
        {!online && (
          <p style={{ fontSize: "var(--text-2xs)", color: "var(--text-subtle)", textAlign: "center", margin: 0 }}>
            You’re offline — starting a chat needs a connection.
          </p>
        )}
        {createError && (
          <p style={{ fontSize: "var(--text-2xs)", color: "var(--danger, #d33)", textAlign: "center", margin: 0 }}>
            Couldn’t start a new chat — try again.
          </p>
        )}

        {conversations.isLoading ? (
          <LoadingCard label="Loading conversations…" />
        ) : conversations.isError ? (
          <ErrorCard>Can’t reach conversations — is the backend running?</ErrorCard>
        ) : rows.length === 0 ? (
          <EmptyCard>No conversations yet — ask something about your memories.</EmptyCard>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {rows.map((c) => (
              <button
                key={c.id}
                onClick={() => setConversationId(c.id)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  width: "100%",
                  textAlign: "start",
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-lg)",
                  padding: "12px 14px",
                  cursor: "pointer",
                  fontFamily: "inherit",
                  color: "var(--text)",
                }}
              >
                <span style={{ minWidth: 0, flex: 1 }}>
                  <span
                    style={{
                      display: "block",
                      fontSize: "var(--ui-text)",
                      fontWeight: "var(--fw-semibold)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {c.title || "New conversation"}
                  </span>
                  <span
                    style={{
                      display: "block",
                      fontFamily: "var(--font-mono)",
                      fontSize: "var(--text-2xs)",
                      color: "var(--text-subtle)",
                      marginTop: "2px",
                    }}
                  >
                    {fmtDate(c.updated_at)}
                  </span>
                </span>
                <ChevronRight width={15} height={15} style={{ color: "var(--text-subtle)", flexShrink: 0 }} />
              </button>
            ))}
          </div>
        )}
      </>
    );
  }

  // ── Selected conversation: threaded messages + input ──────────────────
  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: "8px", flexShrink: 0, paddingBottom: "4px" }}>
        <button
          onClick={() => setConversationId(null)}
          aria-label="Back to conversations"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "32px",
            height: "32px",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            background: "var(--surface)",
            color: "var(--text)",
            cursor: "pointer",
            flexShrink: 0,
          }}
        >
          <ChevronLeft width={16} height={16} />
        </button>
        <span
          style={{
            minWidth: 0,
            flex: 1,
            fontSize: "var(--ui-text)",
            fontWeight: "var(--fw-bold)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {thread.data?.title || "Conversation"}
        </span>
        <button
          onClick={() => void onDistill()}
          disabled={distill.isPending || !online}
          aria-label="Distill this chat into memories"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            flexShrink: 0,
            height: "30px",
            paddingInline: "11px",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-pill)",
            background: "var(--surface-2)",
            color: "var(--text-muted)",
            fontFamily: "inherit",
            fontSize: "var(--text-xs)",
            fontWeight: "var(--fw-semibold)",
            cursor: distill.isPending || !online ? "default" : "pointer",
            opacity: distill.isPending || !online ? 0.5 : 1,
          }}
        >
          <Sparkles width={13} height={13} /> {distill.isPending ? "Distilling…" : "Distill"}
        </button>
      </div>

      {distillMsg && (
        <div
          role="status"
          onClick={() => setDistillMsg(null)}
          style={{
            flexShrink: 0,
            margin: "2px 0 4px",
            padding: "8px 11px",
            borderRadius: "var(--radius-md)",
            background: "var(--success-soft)",
            color: "var(--success)",
            fontSize: "var(--text-xs)",
            fontWeight: "var(--fw-semibold)",
          }}
        >
          {distillMsg}
        </div>
      )}

      <div style={{ flex: 1, minHeight: 0, overflowY: "auto", display: "flex", flexDirection: "column", gap: "10px", padding: "4px 2px" }}>
        {thread.isLoading ? (
          <LoadingCard label="Loading conversation…" />
        ) : thread.isError ? (
          <ErrorCard>Can’t load this conversation.</ErrorCard>
        ) : msgs.length === 0 ? (
          <EmptyCard>Ask a question about your memories to get started.</EmptyCard>
        ) : (
          msgs.map((m) => (
            <MessageBubble key={m.id} message={m} onCiteTap={(n) => void openCitation(m, n)} resolvingKey={resolvingKey} />
          ))
        )}
        {sendMessage.isPending && <ThinkingBubble />}
        <div ref={bottomRef} />
      </div>

      <div style={{ flexShrink: 0, display: "flex", alignItems: "flex-end", gap: "8px", paddingTop: "8px" }}>
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void submit();
            }
          }}
          rows={1}
          disabled={!online || sendMessage.isPending}
          placeholder={online ? "Ask about your memories…" : "Reconnect to ask a question"}
          style={{
            flex: 1,
            resize: "none",
            border: "1px solid var(--border-strong)",
            borderRadius: "var(--radius-lg)",
            background: "var(--surface)",
            color: "var(--text)",
            fontFamily: "inherit",
            fontSize: "var(--ui-text)",
            padding: "10px 13px",
            outline: "none",
            lineHeight: 1.4,
            maxHeight: "96px",
            boxSizing: "border-box",
            opacity: !online ? 0.6 : 1,
          }}
        />
        <button
          onClick={() => void submit()}
          disabled={!draft.trim() || !online || sendMessage.isPending}
          aria-label="Send message"
          style={{
            flexShrink: 0,
            width: "42px",
            height: "42px",
            border: 0,
            borderRadius: "50%",
            background: "var(--accent)",
            color: "var(--accent-fg)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: draft.trim() && online && !sendMessage.isPending ? "pointer" : "not-allowed",
            opacity: draft.trim() && online && !sendMessage.isPending ? 1 : 0.5,
          }}
        >
          <Send width={17} height={17} />
        </button>
      </div>
      {!online && (
        <p style={{ fontSize: "var(--text-2xs)", color: "var(--text-subtle)", textAlign: "center", margin: "6px 0 0" }}>
          You’re offline — chat needs a connection.
        </p>
      )}

      {selectedMem && <MemorySheet mem={selectedMem} onClose={() => setSelectedMem(null)} resolve={resolveMemory} />}
    </div>
  );
}

function MessageBubble({
  message,
  onCiteTap,
  resolvingKey,
}: {
  message: ChatMessage;
  onCiteTap: (n: number) => void;
  resolvingKey: string | null;
}) {
  const isUser = message.role === "user";
  const parts = isUser ? null : splitContent(message.content);

  return (
    <div style={{ display: "flex", justifyContent: isUser ? "flex-end" : "flex-start" }}>
      <div
        style={{
          maxWidth: "82%",
          background: isUser ? "var(--accent)" : "var(--surface)",
          color: isUser ? "var(--accent-fg)" : "var(--text)",
          border: isUser ? "none" : "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
          padding: "10px 13px",
          fontSize: "var(--ui-text)",
          lineHeight: 1.5,
          boxShadow: isUser ? "none" : "var(--shadow-xs)",
          whiteSpace: "pre-wrap",
        }}
      >
        {isUser
          ? message.content
          : parts!.map((p, i) =>
              p.type === "text" ? (
                <span key={i}>{p.value}</span>
              ) : (
                <button
                  key={i}
                  onClick={() => onCiteTap(p.n)}
                  disabled={resolvingKey === `${message.id}:${p.n}`}
                  aria-label={`Open cited memory ${p.n}`}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    minWidth: "18px",
                    height: "18px",
                    paddingInline: "5px",
                    margin: "0 2px",
                    border: "1px solid var(--accent)",
                    borderRadius: "var(--radius-pill)",
                    background: "var(--accent-soft)",
                    color: "var(--accent-soft-fg)",
                    fontSize: "10px",
                    fontWeight: "var(--fw-bold)",
                    verticalAlign: "super",
                    cursor: "pointer",
                    fontFamily: "inherit",
                  }}
                >
                  {resolvingKey === `${message.id}:${p.n}` ? "…" : p.n}
                </button>
              ),
            )}
      </div>
    </div>
  );
}

function ThinkingBubble() {
  return (
    <div style={{ display: "flex", justifyContent: "flex-start" }}>
      <div
        className="animate-pulse"
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
          padding: "10px 13px",
          color: "var(--text-subtle)",
          fontSize: "var(--ui-text)",
        }}
      >
        Thinking…
      </div>
    </div>
  );
}
