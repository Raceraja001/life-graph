"use client";
import { useState, type CSSProperties } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useRoute } from "@/lib/hooks";
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

type Result = { kind: "captured"; routedTo: string } | { kind: "queued" } | { kind: "error" } | null;

function routedTarget(res: any, fallback: string): string {
  return res?.route?.target || res?.target || res?.kind || res?.classification || fallback;
}

export function MobileCapture() {
  const { online, enqueueCapture } = useMobileState();
  const route = useRoute();
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [kind, setKind] = useState("auto");
  const [result, setResult] = useState<Result>(null);

  const submit = async () => {
    const content = text.trim();
    if (!content || route.isPending) return;
    const fallbackKind = kind === "auto" ? "memory" : kind;
    setText("");

    // Offline: persist to the IndexedDB queue; the provider flushes on reconnect.
    if (!online) {
      await enqueueCapture(content);
      setResult({ kind: "queued" });
      return;
    }

    try {
      const res = await route.mutateAsync(content);
      setResult({ kind: "captured", routedTo: routedTarget(res, fallbackKind) });
      qc.invalidateQueries({ queryKey: ["memories"] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
    } catch {
      setResult({ kind: "error" });
      setText(content); // let the user retry without retyping
    }
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
          setResult(null);
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
      <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: "6px", rowGap: "8px", marginTop: "8px" }}>
        {KINDS.map(([id, label]) => (
          <button key={id} onClick={() => setKind(id)} style={kind === id ? chipOn : chipBase}>
            {label}
          </button>
        ))}
        <button
          onClick={submit}
          disabled={!text.trim() || route.isPending}
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
            cursor: text.trim() && !route.isPending ? "pointer" : "not-allowed",
            opacity: text.trim() && !route.isPending ? 1 : 0.5,
          }}
        >
          {route.isPending ? "Routing…" : "Capture"}
        </button>
      </div>

      {result?.kind === "captured" && (
        <Toast bg="var(--success-soft)" fg="var(--success)">
          Captured — routed to {result.routedTo} · extraction queued
        </Toast>
      )}
      {result?.kind === "queued" && (
        <Toast bg="var(--warning-soft)" fg="var(--warning)">
          Saved offline — will sync when you reconnect
        </Toast>
      )}
      {result?.kind === "error" && (
        <Toast bg="var(--danger-soft)" fg="var(--danger)">
          Couldn’t reach the server — your text is kept, try again
        </Toast>
      )}
    </section>
  );
}

function Toast({ bg, fg, children }: { bg: string; fg: string; children: React.ReactNode }) {
  return (
    <div
      role="status"
      style={{
        marginTop: "10px",
        padding: "9px 12px",
        borderRadius: "var(--radius-md)",
        background: bg,
        color: fg,
        fontSize: "var(--text-xs)",
        fontWeight: "var(--fw-semibold)",
      }}
    >
      {children}
    </div>
  );
}
