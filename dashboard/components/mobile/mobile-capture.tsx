"use client";
import { useState, type CSSProperties } from "react";
import { useMobileState } from "./mobile-state";

const KINDS: Array<[string, string]> = [
  ["auto", "Auto"],
  ["memory", "Memory"],
  ["task", "Task"],
  ["intention", "Intention"],
];

const chipBase: CSSProperties = {
  height: "30px",
  paddingInline: "11px",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-pill)",
  background: "var(--surface-2)",
  color: "var(--text-muted)",
  fontFamily: "inherit",
  fontSize: "var(--text-xs)",
  fontWeight: "var(--fw-semibold)",
  cursor: "pointer",
};
const chipOn: CSSProperties = {
  ...chipBase,
  background: "var(--accent-soft)",
  borderColor: "var(--accent)",
  color: "var(--accent-soft-fg)",
};

export function MobileCapture() {
  const { online, addToQueue } = useMobileState();
  const [text, setText] = useState("");
  const [kind, setKind] = useState("auto");
  const [captured, setCaptured] = useState(false);
  const [capturedKind, setCapturedKind] = useState("memory");

  const submit = () => {
    if (!text.trim()) return;
    setCapturedKind(kind === "auto" ? "memory" : kind);
    setCaptured(true);
    setText("");
    if (!online) addToQueue();
  };

  return (
    <section
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-sm)",
        padding: "14px",
      }}
    >
      <textarea
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setCaptured(false);
        }}
        rows={3}
        placeholder="Capture a thought… it becomes a memory, task or intention."
        style={{
          width: "100%",
          border: 0,
          outline: "none",
          resize: "none",
          background: "transparent",
          color: "var(--text)",
          fontFamily: "inherit",
          fontSize: "var(--ui-text)",
          lineHeight: 1.55,
          boxSizing: "border-box",
        }}
      />
      <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "8px" }}>
        {KINDS.map(([id, label]) => (
          <button key={id} onClick={() => setKind(id)} style={kind === id ? chipOn : chipBase}>
            {label}
          </button>
        ))}
        <button
          onClick={submit}
          disabled={!text.trim()}
          style={{
            marginInlineStart: "auto",
            height: "34px",
            paddingInline: "16px",
            border: 0,
            borderRadius: "var(--radius-pill)",
            background: "var(--accent)",
            color: "var(--accent-fg)",
            fontFamily: "inherit",
            fontSize: "var(--text-sm)",
            fontWeight: "var(--fw-bold)",
            cursor: text.trim() ? "pointer" : "not-allowed",
            opacity: text.trim() ? 1 : 0.5,
          }}
        >
          Capture
        </button>
      </div>
      {captured && (
        <div
          role="status"
          style={{
            marginTop: "10px",
            padding: "9px 12px",
            borderRadius: "var(--radius-md)",
            background: "var(--success-soft)",
            color: "var(--success)",
            fontSize: "var(--text-xs)",
            fontWeight: "var(--fw-semibold)",
          }}
        >
          Captured — routed to {capturedKind} · extraction queued
        </div>
      )}
    </section>
  );
}
