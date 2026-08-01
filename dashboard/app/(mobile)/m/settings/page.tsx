"use client";
import { LoadingCard, EmptyCard, ErrorCard } from "@/components/mobile/parts";
import { useModelHealth, type ModelHealthVM, type ModelHealthState } from "@/lib/mobile-api";

const DOT_COLOR: Record<ModelHealthState, string> = {
  up: "var(--success)",
  cooling: "var(--warning)",
  down: "var(--danger)",
  unknown: "var(--text-subtle)",
};

function relativeTime(epochSeconds: number | null): string | null {
  if (epochSeconds == null) return null;
  const deltaMs = Date.now() - epochSeconds * 1000;
  if (deltaMs < 0) return "just now";
  const seconds = Math.floor(deltaMs / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function ModelHealthRow({ item }: { item: ModelHealthVM }) {
  const lastSeen = relativeTime(item.lastSuccessAt);
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: "11px",
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        padding: "12px 14px",
        minHeight: "44px",
        boxSizing: "border-box",
      }}
    >
      <span
        aria-hidden
        style={{
          width: "9px",
          height: "9px",
          borderRadius: "50%",
          background: DOT_COLOR[item.state],
          flexShrink: 0,
          marginTop: "5px",
        }}
      />
      <span style={{ minWidth: 0, flex: 1 }}>
        <span style={{ display: "flex", alignItems: "baseline", gap: "8px", flexWrap: "wrap" }}>
          <span style={{ fontSize: "var(--ui-text)", fontWeight: "var(--fw-semibold)" }}>{item.shortName}</span>
          {lastSeen && (
            <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-2xs)", color: "var(--text-subtle)" }}>
              {lastSeen}
            </span>
          )}
        </span>
        {item.lastError && (
          <span
            style={{
              display: "block",
              fontSize: "var(--text-2xs)",
              color: "var(--danger)",
              marginTop: "3px",
              lineHeight: 1.4,
            }}
          >
            {item.lastError}
          </span>
        )}
      </span>
    </div>
  );
}

export default function MobileSettings() {
  const modelHealth = useModelHealth();
  const items = modelHealth.data ?? [];

  return (
    <>
      <h1
        style={{
          fontFamily: "var(--font-display)",
          fontWeight: 800,
          fontSize: "var(--text-md)",
          letterSpacing: "var(--tracking-tight)",
          margin: "4px 0 0",
        }}
      >
        Model health
      </h1>

      {modelHealth.isLoading && <LoadingCard label="Loading model health…" />}
      {modelHealth.isError && <ErrorCard>Can&rsquo;t reach model health — is the backend running?</ErrorCard>}
      {!modelHealth.isLoading && !modelHealth.isError && items.length === 0 && (
        <EmptyCard>No model activity recorded yet.</EmptyCard>
      )}
      {!modelHealth.isLoading &&
        !modelHealth.isError &&
        items.length > 0 &&
        items.map((item) => <ModelHealthRow key={item.model} item={item} />)}
    </>
  );
}
