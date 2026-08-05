"use client";
// Unified streaming chat surface: a persona picker (default Jarvis) plus a thread
// that renders collapsible delegation "step" chips and a live-streaming synthesis
// bubble, driven entirely by `api.kernel.chatStream`'s SSE event callback. Visual
// target: docs/design/mockups/jarvis-streaming-chat.html.
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Check, ChevronRight, Loader2, Send, Square } from "lucide-react";
import { api } from "@/lib/api";
import { useMobileState } from "@/components/mobile/mobile-state";

type Step = { persona: string; text: string; done: boolean };
type Turn = {
  user: string;
  synthesis: string;
  steps: Record<string, Step>;
  order: string[];
  done: boolean;
  errored: boolean;
};

type ChatEvent =
  | { type: "start" }
  | { type: "assistant_delta"; text: string }
  | { type: "delegation_start"; child_id: string; persona: string }
  | { type: "child_delta"; child_id: string; persona: string; text: string }
  | { type: "child_done"; child_id: string; persona: string }
  | { type: "done" }
  | { type: "error"; message: string };

const PERSONAS = [
  { id: "jarvis", label: "Jarvis · coordinator" },
  { id: "tutor", label: "Tutor" },
  { id: "swe-lead", label: "SWE-Lead" },
  { id: "scout", label: "Scout" },
  { id: "admin", label: "Admin" },
];

const ROLE_COLOR: Record<string, string> = {
  jarvis: "var(--accent-text)",
  tutor: "var(--success)",
  "swe-lead": "var(--info)",
  scout: "var(--warning)",
  admin: "var(--accent-text)",
};

function roleColor(persona: string): string {
  return ROLE_COLOR[persona] ?? "var(--accent-text)";
}

function newTurn(user: string): Turn {
  return { user, synthesis: "", steps: {}, order: [], done: false, errored: false };
}

export function PersonaChat() {
  const { online } = useMobileState();
  const [persona, setPersona] = useState("jarvis");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const abort = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [turns.length, streaming]);

  function patchLast(fn: (t: Turn) => Turn) {
    setTurns((ts) => (ts.length === 0 ? ts : ts.map((t, i) => (i === ts.length - 1 ? fn(t) : t))));
  }

  async function send() {
    const msg = input.trim();
    if (!msg || streaming || !online) return;
    setInput("");
    setTurns((ts) => [...ts, newTurn(msg)]);
    setStreaming(true);
    abort.current = new AbortController();
    try {
      await api.kernel.chatStream(
        msg,
        persona,
        (e: ChatEvent) => {
          if (e.type === "assistant_delta") {
            patchLast((t) => ({ ...t, synthesis: t.synthesis + e.text }));
          } else if (e.type === "delegation_start") {
            patchLast((t) =>
              t.steps[e.child_id]
                ? t
                : {
                    ...t,
                    order: [...t.order, e.child_id],
                    steps: { ...t.steps, [e.child_id]: { persona: e.persona, text: "", done: false } },
                  },
            );
          } else if (e.type === "child_delta") {
            patchLast((t) => {
              const prev = t.steps[e.child_id] ?? { persona: e.persona, text: "", done: false };
              return { ...t, steps: { ...t.steps, [e.child_id]: { ...prev, text: prev.text + e.text } } };
            });
          } else if (e.type === "child_done") {
            patchLast((t) => {
              const prev = t.steps[e.child_id];
              return prev ? { ...t, steps: { ...t.steps, [e.child_id]: { ...prev, done: true } } } : t;
            });
          } else if (e.type === "done") {
            patchLast((t) => ({ ...t, done: true }));
          } else if (e.type === "error") {
            patchLast((t) => ({ ...t, synthesis: t.synthesis + `\n[error: ${e.message}]`, done: true, errored: true }));
          }
        },
        abort.current.signal,
      );
    } catch {
      patchLast((t) => (t.done ? t : { ...t, synthesis: t.synthesis + "\n[connection lost]", done: true, errored: true }));
    } finally {
      setStreaming(false);
    }
  }

  const lastIdx = turns.length - 1;

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: "8px", flexShrink: 0, paddingBottom: "8px" }}>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            fontSize: "var(--text-xs)",
            color: "var(--text-subtle)",
          }}
        >
          <span style={{ width: "7px", height: "7px", borderRadius: "50%", background: roleColor(persona) }} />
          Talking to
        </span>
        <select
          value={persona}
          onChange={(e) => setPersona(e.target.value)}
          disabled={streaming}
          style={{
            background: "var(--surface-2)",
            color: "var(--text)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            padding: "6px 9px",
            fontSize: "var(--text-sm)",
            fontFamily: "inherit",
          }}
        >
          {PERSONAS.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>
      </div>

      <div style={{ flex: 1, minHeight: 0, overflowY: "auto", display: "flex", flexDirection: "column", gap: "18px", padding: "4px 2px" }}>
        {turns.length === 0 ? (
          <div
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-lg)",
              padding: "28px 18px",
              textAlign: "center",
              fontSize: "var(--text-sm)",
              color: "var(--text-muted)",
            }}
          >
            Ask Jarvis anything — it can coordinate Tutor, SWE-Lead, Scout, and Admin for you.
          </div>
        ) : (
          turns.map((t, i) => (
            <TurnView
              key={i}
              turn={t}
              isLast={i === lastIdx}
              streaming={streaming}
              open={open}
              onToggle={(cid) => setOpen((o) => ({ ...o, [cid]: !o[cid] }))}
            />
          ))
        )}
        <div ref={bottomRef} />
      </div>

      <div style={{ flexShrink: 0, display: "flex", alignItems: "flex-end", gap: "8px", paddingTop: "8px" }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void send();
            }
          }}
          disabled={!online || streaming}
          placeholder={online ? `Message ${PERSONAS.find((p) => p.id === persona)?.label ?? persona}…` : "Reconnect to chat"}
          style={{
            flex: 1,
            border: "1px solid var(--border-strong)",
            borderRadius: "var(--radius-lg)",
            background: "var(--surface)",
            color: "var(--text)",
            fontFamily: "inherit",
            fontSize: "var(--ui-text)",
            padding: "10px 13px",
            outline: "none",
            boxSizing: "border-box",
            opacity: !online ? 0.6 : 1,
          }}
        />
        {streaming ? (
          <button
            onClick={() => abort.current?.abort()}
            aria-label="Stop streaming"
            style={{
              flexShrink: 0,
              width: "42px",
              height: "42px",
              border: "1px solid var(--border-strong)",
              borderRadius: "50%",
              background: "var(--surface)",
              color: "var(--text)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
            }}
          >
            <Square width={15} height={15} fill="currentColor" />
          </button>
        ) : (
          <button
            onClick={() => void send()}
            disabled={!input.trim() || !online}
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
              cursor: input.trim() && online ? "pointer" : "not-allowed",
              opacity: input.trim() && online ? 1 : 0.5,
            }}
          >
            <Send width={17} height={17} />
          </button>
        )}
      </div>
      {!online && (
        <p style={{ fontSize: "var(--text-2xs)", color: "var(--text-subtle)", textAlign: "center", margin: "6px 0 0" }}>
          You’re offline — chat needs a connection.
        </p>
      )}
    </div>
  );
}

function TurnView({
  turn,
  isLast,
  streaming,
  open,
  onToggle,
}: {
  turn: Turn;
  isLast: boolean;
  streaming: boolean;
  open: Record<string, boolean>;
  onToggle: (childId: string) => void;
}) {
  const isStreamingThis = isLast && streaming;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <div
          style={{
            maxWidth: "82%",
            background: "var(--accent)",
            color: "var(--accent-fg)",
            borderRadius: "var(--radius-lg)",
            padding: "10px 13px",
            fontSize: "var(--ui-text)",
            lineHeight: 1.5,
            whiteSpace: "pre-wrap",
          }}
        >
          {turn.user}
        </div>
      </div>

      {(turn.order.length > 0 || turn.synthesis || isStreamingThis) && (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {turn.order.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "7px" }}>
              {turn.order.map((cid) => (
                <StepChip key={cid} step={turn.steps[cid]} open={!!open[cid]} onToggle={() => onToggle(cid)} />
              ))}
            </div>
          )}

          {(turn.synthesis || (isStreamingThis && turn.order.length === 0)) && (
            <div
              style={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-lg)",
                padding: "12px 14px",
                fontSize: "var(--ui-text)",
                lineHeight: 1.55,
                whiteSpace: "pre-wrap",
                color: turn.errored ? "var(--danger)" : "var(--text)",
              }}
            >
              {turn.synthesis || (isStreamingThis ? "Jarvis is coordinating…" : "")}
              {isStreamingThis && !turn.done && <Cursor />}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StepChip({ step, open, onToggle }: { step: Step; open: boolean; onToggle: () => void }) {
  const barStyle: CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: "9px",
    padding: "9px 12px",
    cursor: "pointer",
    userSelect: "none",
    background: "none",
    border: 0,
    width: "100%",
    textAlign: "left",
    fontFamily: "inherit",
    color: "var(--text)",
  };
  return (
    <div style={{ border: "1px solid var(--border)", background: "var(--surface-2)", borderRadius: "var(--radius-md)", overflow: "hidden" }}>
      <button onClick={onToggle} style={barStyle} aria-expanded={open}>
        {step.done ? (
          <Check width={13} height={13} style={{ color: "var(--success)", flexShrink: 0 }} />
        ) : (
          <Loader2 width={13} height={13} className="animate-spin" style={{ color: "var(--accent)", flexShrink: 0 }} />
        )}
        <span style={{ fontWeight: "var(--fw-semibold)", fontSize: "var(--text-sm)", color: roleColor(step.persona) }}>
          {step.persona}
          <span style={{ fontSize: "var(--text-2xs)", color: "var(--text-subtle)", fontWeight: "var(--fw-regular)", marginLeft: "6px" }}>
            {step.done ? "· done" : "· working…"}
          </span>
        </span>
        <ChevronRight
          width={13}
          height={13}
          style={{ marginLeft: "auto", color: "var(--text-subtle)", transform: open ? "rotate(90deg)" : "none", transition: "transform 150ms ease" }}
        />
      </button>
      {open && (
        <pre
          style={{
            margin: 0,
            padding: "0 13px 12px",
            borderTop: "1px solid var(--border)",
            paddingTop: "11px",
            color: "var(--text-muted)",
            fontSize: "var(--text-sm)",
            whiteSpace: "pre-wrap",
            fontFamily: "inherit",
          }}
        >
          {step.text || "…"}
        </pre>
      )}
    </div>
  );
}

function Cursor() {
  return (
    <span
      className="animate-pulse"
      style={{
        display: "inline-block",
        width: "8px",
        height: "1em",
        background: "var(--accent)",
        verticalAlign: "-2px",
        marginLeft: "2px",
      }}
    />
  );
}
