// Temporary Phase-1 placeholder. Phase 2 replaces each mobile route body with
// the pixel-perfect screen from the design.
export function MobilePlaceholder({ label }: { label: string }) {
  return (
    <section
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-sm)",
        padding: "16px 18px",
      }}
    >
      <div
        style={{
          fontSize: "var(--text-2xs)",
          fontWeight: "var(--fw-bold)",
          letterSpacing: "var(--tracking-caps)",
          textTransform: "uppercase",
          color: "var(--text-subtle)",
          marginBottom: "6px",
        }}
      >
        {label}
      </div>
      <p style={{ fontSize: "var(--ui-text)", color: "var(--text-muted)", lineHeight: 1.5 }}>
        Screen shell is live. Pixel-perfect content lands in Phase 2.
      </p>
    </section>
  );
}
