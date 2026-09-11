"use client";
import { useEffect, useState } from "react";
import { EmptyCard, ErrorCard, Meta, Pill, SkeletonList, Stack } from "@/components/mobile/parts";
import { usePullToRefresh } from "@/lib/use-pull-to-refresh";
import { MemorySheet } from "@/components/mobile/memory-sheet";
import { useMobileMemories, useMobileMemorySearch, useResolveMemory, type MemoryVM } from "@/lib/mobile-api";
import { impLabel } from "@/lib/mobile-mock";

const resolveBtn: React.CSSProperties = {
  flex: 1,
  border: "none",
  borderRadius: "var(--radius-control)",
  padding: "7px 0",
  fontFamily: "inherit",
  fontSize: "var(--size-meta)",
  fontWeight: 600,
};

export default function MobileMemories() {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<MemoryVM | null>(null);

  const searching = query.trim().length > 2;
  const list = useMobileMemories(50);
  const search = useMobileMemorySearch(query);
  const resolve = useResolveMemory();

  const { refreshing, distance } = usePullToRefresh({
    onRefresh: () => (searching ? search.refetch() : list.refetch()),
  });

  const active = searching ? search : list;
  const rows = active.data ?? [];

  useEffect(() => {
    if (!selected) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setSelected(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected]);

  return (
    <>
      {(distance > 0 || refreshing) && (
        <div
          role="status"
          style={{
            height: refreshing ? 28 : distance,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--text-subtle)",
            fontSize: "var(--size-meta)",
            overflow: "hidden",
            transition: refreshing ? "height var(--dur-fast) var(--ease-settle)" : undefined,
          }}
        >
          {refreshing ? "Refreshing…" : distance >= 64 ? "Release to refresh" : "Pull to refresh"}
        </div>
      )}
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search memories…"
        style={{
          height: "42px",
          paddingInline: "var(--o-lg)",
          border: "1px solid var(--border-strong)",
          borderRadius: "var(--radius-pill)",
          background: "var(--surface)",
          color: "var(--text)",
          fontFamily: "inherit",
          fontSize: "var(--size-body)",
          outline: "none",
          boxSizing: "border-box",
        }}
      />

      {active.isLoading ? (
        <SkeletonList count={5} />
      ) : active.isError ? (
        <ErrorCard>Can’t reach memories — is the backend running?</ErrorCard>
      ) : rows.length === 0 ? (
        <EmptyCard
          hint={
            searching
              ? "Search matches meaning, not just words — try describing it another way."
              : "Capture anything from Home; it gets tagged and linked for you."
          }
        >
          {searching ? `No memories match “${query.trim()}”.` : "No memories yet."}
        </EmptyCard>
      ) : (
        <Stack>
          {rows.map((m) => (
            <div key={m.id}>
              <button
                onClick={() => {
                  if (!m._optimistic) setSelected(m);
                }}
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "start",
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-row)",
                  padding: "var(--o-md) var(--o-lg)",
                  cursor: m._optimistic ? "default" : "pointer",
                  opacity: m._optimistic ? 0.7 : 1,
                  fontFamily: "inherit",
                  color: "var(--text)",
                }}
              >
                <div style={{ fontSize: "var(--size-body)", lineHeight: 1.5 }}>{m.content}</div>
                <div style={{ display: "flex", gap: "6px", marginTop: "var(--o-xs)", alignItems: "center", flexWrap: "wrap" }}>
                  {(m._optimistic || m.status === "pending") && (
                    <Pill tone="warning">{m._optimistic ? "saving…" : "pending"}</Pill>
                  )}
                  {m.tags.map((t) => (
                    <Pill key={t} tone="neutral">
                      {t}
                    </Pill>
                  ))}
                  <Meta style={{ marginInlineStart: "auto", color: "var(--accent-text)", fontWeight: 600 }}>
                    {impLabel(m.imp)}
                  </Meta>
                </div>
              </button>
              {m.status === "pending" && !m._optimistic && (
                <div style={{ display: "flex", gap: "6px", marginTop: "6px" }}>
                  <button
                    onClick={() => resolve.mutate({ id: m.id, action: "approve" })}
                    disabled={resolve.isPending}
                    style={{
                      ...resolveBtn,
                      background: "var(--success-soft)",
                      color: "var(--success)",
                      cursor: resolve.isPending ? "default" : "pointer",
                      opacity: resolve.isPending ? 0.6 : 1,
                    }}
                  >
                    ✓ Approve
                  </button>
                  <button
                    onClick={() => resolve.mutate({ id: m.id, action: "reject" })}
                    disabled={resolve.isPending}
                    style={{
                      ...resolveBtn,
                      background: "var(--danger-soft)",
                      color: "var(--danger)",
                      cursor: resolve.isPending ? "default" : "pointer",
                      opacity: resolve.isPending ? 0.6 : 1,
                    }}
                  >
                    ✕ Reject
                  </button>
                </div>
              )}
            </div>
          ))}
        </Stack>
      )}

      {selected && (
        <MemorySheet key={selected.id} mem={selected} onClose={() => setSelected(null)} resolve={resolve} />
      )}
    </>
  );
}
