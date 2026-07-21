"use client";
import { useEffect, useState } from "react";
import { LoadingCard, EmptyCard, ErrorCard } from "@/components/mobile/parts";
import { useMobileMemories, useMobileMemorySearch, type MemoryVM } from "@/lib/mobile-api";
import { impLabel } from "@/lib/mobile-mock";

export default function MobileMemories() {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<MemoryVM | null>(null);

  const searching = query.trim().length > 2;
  const list = useMobileMemories(50);
  const search = useMobileMemorySearch(query);

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
        <LoadingCard label={searching ? "Searching…" : "Loading memories…"} />
      ) : active.isError ? (
        <ErrorCard>Can’t reach memories — is the backend running?</ErrorCard>
      ) : rows.length === 0 ? (
        <EmptyCard>{searching ? `No memories match “${query.trim()}”.` : "No memories yet."}</EmptyCard>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {rows.map((m) => (
            <button
              key={m.id}
              onClick={() => setSelected(m)}
              style={{
                display: "block",
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
              <div style={{ fontSize: "var(--ui-text)", lineHeight: 1.5 }}>{m.content}</div>
              <div style={{ display: "flex", gap: "6px", marginTop: "7px", alignItems: "center", flexWrap: "wrap" }}>
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
          ))}
        </div>
      )}

      {selected && <MemorySheet mem={selected} onClose={() => setSelected(null)} />}
    </>
  );
}

function MemorySheet({ mem, onClose }: { mem: MemoryVM; onClose: () => void }) {
  const prov = [
    `Captured via ${mem.source}`,
    mem.created ? `First seen ${mem.created}` : null,
    `Importance ${impLabel(mem.imp)} · decays over time`,
  ].filter(Boolean) as string[];

  return (
    <>
      <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "var(--overlay)", zIndex: 30 }} />
      <aside
        role="dialog"
        aria-modal="true"
        style={{
          position: "fixed",
          bottom: 0,
          left: "50%",
          transform: "translateX(-50%)",
          width: "100%",
          maxWidth: "430px",
          zIndex: 40,
          background: "var(--surface)",
          borderTopLeftRadius: "var(--radius-xl)",
          borderTopRightRadius: "var(--radius-xl)",
          boxShadow: "var(--shadow-xl)",
          padding: "8px 20px calc(20px + env(safe-area-inset-bottom))",
          maxHeight: "80%",
          overflowY: "auto",
        }}
      >
        <div style={{ width: "38px", height: "4px", borderRadius: "var(--radius-pill)", background: "var(--border-strong)", margin: "6px auto 14px" }} />

        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px", flexWrap: "wrap" }}>
          {mem.tags.map((t) => (
            <span
              key={t}
              style={{
                display: "inline-flex",
                alignItems: "center",
                height: "20px",
                paddingInline: "9px",
                borderRadius: "var(--radius-pill)",
                background: "var(--accent-soft)",
                color: "var(--accent-soft-fg)",
                fontSize: "var(--text-2xs)",
                fontWeight: "var(--fw-bold)",
              }}
            >
              {t}
            </span>
          ))}
          <span
            style={{
              marginInlineStart: "auto",
              fontFamily: "var(--font-mono)",
              fontSize: "var(--text-sm)",
              fontWeight: "var(--fw-bold)",
              color: "var(--accent-text)",
            }}
          >
            {impLabel(mem.imp)}
          </span>
        </div>

        <p style={{ margin: "0 0 16px", fontSize: "var(--text-md)", lineHeight: 1.55 }}>{mem.content}</p>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginBottom: "16px" }}>
          <SheetTile label="Source" value={mem.source} />
          <SheetTile label="Captured" value={mem.created || "—"} />
        </div>

        <div
          style={{
            fontSize: "var(--text-2xs)",
            fontWeight: "var(--fw-bold)",
            letterSpacing: "var(--tracking-caps)",
            textTransform: "uppercase",
            color: "var(--text-subtle)",
            marginBottom: "8px",
          }}
        >
          Provenance
        </div>
        <div style={{ display: "flex", flexDirection: "column", marginBottom: "4px" }}>
          {prov.map((p) => (
            <div key={p} style={{ display: "flex", gap: "10px", alignItems: "flex-start", padding: "5px 0" }}>
              <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "var(--accent)", marginTop: "5px", flexShrink: 0 }} />
              <span style={{ flex: 1, fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>{p}</span>
            </div>
          ))}
        </div>
      </aside>
    </>
  );
}

function SheetTile({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", padding: "10px 12px" }}>
      <div style={{ fontSize: "var(--text-2xs)", color: "var(--text-subtle)", marginBottom: "3px" }}>{label}</div>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", fontWeight: "var(--fw-semibold)", overflowWrap: "anywhere" }}>{value}</div>
    </div>
  );
}
