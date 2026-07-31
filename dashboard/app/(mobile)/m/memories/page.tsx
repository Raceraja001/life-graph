"use client";
import { useEffect, useState } from "react";
import { EmptyCard, ErrorCard, SkeletonList } from "@/components/mobile/parts";
import { usePullToRefresh } from "@/lib/use-pull-to-refresh";
import { MemorySheet } from "@/components/mobile/memory-sheet";
import { useMobileMemories, useMobileMemorySearch, useResolveMemory, type MemoryVM } from "@/lib/mobile-api";
import { impLabel } from "@/lib/mobile-mock";

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
            fontSize: "var(--text-2xs)",
            overflow: "hidden",
            transition: refreshing ? "height 0.15s" : undefined,
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
          paddingInline: "14px",
          border: "1px solid var(--border-strong)",
          borderRadius: "var(--radius-pill)",
          background: "var(--surface)",
          color: "var(--text)",
          fontFamily: "inherit",
          fontSize: "var(--ui-text)",
          outline: "none",
          boxSizing: "border-box",
        }}
      />

      {active.isLoading ? (
        <SkeletonList count={5} />
      ) : active.isError ? (
        <ErrorCard>Can’t reach memories — is the backend running?</ErrorCard>
      ) : rows.length === 0 ? (
        <EmptyCard>{searching ? `No memories match “${query.trim()}”.` : "No memories yet."}</EmptyCard>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {rows.map((m) => (
            <div key={m.id}>
              <button
                onClick={() => { if (!m._optimistic) setSelected(m); }}
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "start",
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-lg)",
                  padding: "12px 14px",
                  cursor: m._optimistic ? "default" : "pointer",
                  opacity: m._optimistic ? 0.7 : 1,
                  fontFamily: "inherit",
                  color: "var(--text)",
                }}
              >
                <div style={{ fontSize: "var(--ui-text)", lineHeight: 1.5 }}>{m.content}</div>
                <div style={{ display: "flex", gap: "6px", marginTop: "7px", alignItems: "center", flexWrap: "wrap" }}>
                  {(m._optimistic || m.status === "pending") && (
                    <span
                      style={{
                        background: "var(--warning-soft, #fef3c7)",
                        color: "var(--warning, #b45309)",
                        borderRadius: 999,
                        padding: "1px 8px",
                        fontSize: 11,
                        fontWeight: 600,
                      }}
                    >
                      {m._optimistic ? "saving…" : "pending"}
                    </span>
                  )}
                  {m.tags.map((t) => (
                    <span
                      key={t}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        height: "19px",
                        paddingInline: "8px",
                        borderRadius: "var(--radius-pill)",
                        background: "var(--surface-3)",
                        color: "var(--text-muted)",
                        fontSize: "var(--text-2xs)",
                        fontWeight: "var(--fw-semibold)",
                      }}
                    >
                      {t}
                    </span>
                  ))}
                  <span
                    style={{
                      marginInlineStart: "auto",
                      fontFamily: "var(--font-mono)",
                      fontSize: "var(--text-2xs)",
                      fontWeight: "var(--fw-bold)",
                      color: "var(--accent-text)",
                    }}
                  >
                    {impLabel(m.imp)}
                  </span>
                </div>
              </button>
              {m.status === "pending" && !m._optimistic && (
                <div style={{ display: "flex", gap: "6px", marginTop: "6px" }}>
                  <button
                    onClick={() => resolve.mutate({ id: m.id, action: "approve" })}
                    disabled={resolve.isPending}
                    style={{
                      flex: 1,
                      background: "var(--success-soft)",
                      color: "var(--success)",
                      border: "none",
                      borderRadius: "var(--radius-md)",
                      padding: "6px 0",
                      fontSize: "var(--text-sm)",
                      fontWeight: "var(--fw-bold)",
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
                      flex: 1,
                      background: "var(--danger-soft)",
                      color: "var(--danger)",
                      border: "none",
                      borderRadius: "var(--radius-md)",
                      padding: "6px 0",
                      fontSize: "var(--text-sm)",
                      fontWeight: "var(--fw-bold)",
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
        </div>
      )}

      {selected && (
        <MemorySheet
          mem={selected}
          onClose={() => setSelected(null)}
          resolve={resolve}
        />
      )}
    </>
  );
}
