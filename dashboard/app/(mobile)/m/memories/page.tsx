"use client";
import { useEffect, useState } from "react";
import { MEMS, impLabel, type MemoryMock } from "@/lib/mobile-mock";

export default function MobileMemories() {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<MemoryMock | null>(null);

  const q = query.trim().toLowerCase();
  const rows = MEMS.filter(
    (m) => !q || m.content.toLowerCase().includes(q) || m.tags.some((t) => t.includes(q)),
  );

  // Close the sheet on Escape.
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

      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {rows.length === 0 ? (
          <p style={{ fontSize: "var(--text-sm)", color: "var(--text-subtle)", textAlign: "center", padding: "24px 0" }}>
            No memories match “{query}”.
          </p>
        ) : (
          rows.map((m) => (
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
          ))
        )}
      </div>

      {selected && <MemorySheet mem={selected} onClose={() => setSelected(null)} />}
    </>
  );
}

function MemorySheet({ mem, onClose }: { mem: MemoryMock; onClose: () => void }) {
  const [source, created = ""] = mem.meta.split(" · ");
  const prov = [
    `Captured via ${source}`,
    "Extracted · embedded bge-m3 1024-d",
    "Re-consolidated in nightly sleep cycle",
  ];

  return (
    <>
      <div
        onClick={onClose}
        style={{ position: "fixed", inset: 0, background: "var(--overlay)", zIndex: 30 }}
      />
      <aside
        role="dialog"
        aria-modal="true"
        style={{
          position: "fixed",
          insetInline: 0,
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

        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
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
          <SheetTile label="Source" value={source} />
          <SheetTile label="Captured" value={created} />
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
      <div style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)", fontWeight: "var(--fw-semibold)" }}>{value}</div>
    </div>
  );
}
