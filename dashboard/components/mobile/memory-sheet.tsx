"use client";
import type { MemoryVM, useResolveMemory } from "@/lib/mobile-api";
import { impLabel } from "@/lib/mobile-mock";

export function MemorySheet({
  mem,
  onClose,
  resolve,
}: {
  mem: MemoryVM;
  onClose: () => void;
  resolve: ReturnType<typeof useResolveMemory>;
}) {
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
          {mem.status === "pending" && (
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
              pending
            </span>
          )}
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

        {mem.status === "pending" && (
          <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
            <button
              onClick={() => resolve.mutate({ id: mem.id, action: "approve" }, { onSuccess: onClose })}
              disabled={resolve.isPending}
              style={{
                flex: 1,
                background: "var(--success-soft)",
                color: "var(--success)",
                border: "none",
                borderRadius: "var(--radius-md)",
                padding: "8px 0",
                fontSize: "var(--text-sm)",
                fontWeight: "var(--fw-bold)",
                cursor: resolve.isPending ? "default" : "pointer",
                opacity: resolve.isPending ? 0.6 : 1,
              }}
            >
              ✓ Approve
            </button>
            <button
              onClick={() => resolve.mutate({ id: mem.id, action: "reject" }, { onSuccess: onClose })}
              disabled={resolve.isPending}
              style={{
                flex: 1,
                background: "var(--danger-soft)",
                color: "var(--danger)",
                border: "none",
                borderRadius: "var(--radius-md)",
                padding: "8px 0",
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
