// Shared presentational parts for the mobile screens. Pure (no hooks), so they
// work in both server and client components.
import type { CSSProperties } from "react";
import { TONE, type TaskMock } from "@/lib/mobile-mock";

const stateCard: CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-lg)",
  padding: "28px 18px",
  textAlign: "center",
  fontSize: "var(--text-sm)",
};

export function LoadingCard({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="animate-pulse" style={{ ...stateCard, color: "var(--text-subtle)" }}>
      {label}
    </div>
  );
}

export function EmptyCard({ children }: { children: React.ReactNode }) {
  return <div style={{ ...stateCard, color: "var(--text-muted)" }}>{children}</div>;
}

export function ErrorCard({ children }: { children: React.ReactNode }) {
  return (
    <div
      role="alert"
      style={{
        ...stateCard,
        background: "var(--danger-soft)",
        border: "1px solid var(--danger)",
        color: "var(--danger)",
        fontWeight: "var(--fw-semibold)",
      }}
    >
      {children}
    </div>
  );
}

export function SectionEyebrow({ children }: { children: React.ReactNode }) {
  return (
    <span
      style={{
        fontSize: "var(--text-2xs)",
        fontWeight: "var(--fw-bold)",
        letterSpacing: "var(--tracking-caps)",
        textTransform: "uppercase",
        color: "var(--text-subtle)",
      }}
    >
      {children}
    </span>
  );
}

export function TaskRow({ task, showStatus = false }: { task: TaskMock; showStatus?: boolean }) {
  const [pillBg, fg] = TONE[task.tone];
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "11px",
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        padding: "12px 14px",
        minHeight: "44px",
        boxSizing: "border-box",
      }}
    >
      <span style={{ width: "9px", height: "9px", borderRadius: "50%", background: fg, flexShrink: 0 }} />
      <span style={{ minWidth: 0, flex: 1 }}>
        <span
          style={{
            display: "block",
            fontSize: "var(--ui-text)",
            fontWeight: "var(--fw-semibold)",
            ...(showStatus ? { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" } : null),
          }}
        >
          {task.title}
        </span>
        <span
          style={{
            display: "block",
            fontFamily: "var(--font-mono)",
            fontSize: "var(--text-2xs)",
            color: "var(--text-subtle)",
            marginTop: "1px",
          }}
        >
          {task.meta}
        </span>
      </span>
      {showStatus && (
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            height: "20px",
            paddingInline: "8px",
            borderRadius: "var(--radius-pill)",
            background: pillBg,
            color: fg,
            fontSize: "var(--text-2xs)",
            fontWeight: "var(--fw-bold)",
            whiteSpace: "nowrap",
          }}
        >
          {task.status}
        </span>
      )}
    </div>
  );
}
