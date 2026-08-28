// Shared presentational parts for the mobile screens. Pure (no hooks), so they
// work in both server and client components.
//
// These carry Orbit's composition rules so the screens don't have to restate
// them. Two of those rules do most of the work:
//
//   Spacing is 9 / 13 / 16, not a 4dp grid. OrbitSpace says why: "rows read
//   tighter than blocks — don't round these to 8s." A list of rows breathes at
//   9px; two unrelated sections need 13px; the screen edge is 16px. The screens
//   used to pick from 4/6/7/8/11/12/13/14/18 by feel, which is why nothing
//   quite lined up.
//
//   Depth comes from surface colour, not shadow. A row sits on --surface above
//   a --bg page; a sheet goes to --surface-3. Nothing here casts a shadow.
import type { ComponentPropsWithoutRef, CSSProperties, ReactNode } from "react";
import { TONE, type TaskMock } from "@/lib/mobile-mock";

/* ----------------------------------------------------------------- layout -- */

/** Vertical rhythm. `row` for items in a list, `block` for unrelated sections. */
export function Stack({
  gap = "row",
  children,
  style,
}: {
  gap?: "row" | "block" | "gutter";
  children: ReactNode;
  style?: CSSProperties;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: `var(--space-${gap})`, ...style }}>
      {children}
    </div>
  );
}

/** A titled section: eyebrow, optional trailing action, then content. */
export function Section({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section>
      <div style={{ display: "flex", alignItems: "baseline", gap: "8px", marginBottom: "var(--space-row)" }}>
        <Eyebrow>{title}</Eyebrow>
        {action ? <span style={{ marginInlineStart: "auto" }}>{action}</span> : null}
      </div>
      {children}
    </section>
  );
}

/* ------------------------------------------------------------- containers -- */

const cardBase: CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-card)",
  padding: "var(--o-lg)",
};

const rowBase: CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-row)",
  padding: "var(--o-md) var(--o-lg)",
  minHeight: "44px",
  boxSizing: "border-box",
};

/** A block-level container — the thing a section is made of. */
export function Card({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return <div style={{ ...cardBase, ...style }}>{children}</div>;
}

/**
 * One item in a list. Tighter radius and padding than a Card, by design.
 *
 * `as="button"` exists because several rows are the tap target rather than
 * containing one; rendering those as a <div> with an onClick would take them
 * out of the tab order.
 */
export function Row({
  as = "div",
  children,
  style,
  ...rest
}: { as?: "div" | "button"; children: ReactNode; style?: CSSProperties } & Omit<
  ComponentPropsWithoutRef<"button">,
  "style" | "children"
>) {
  const Tag = as as "button";
  return (
    <Tag style={{ ...rowBase, display: "flex", alignItems: "center", gap: "11px", ...style }} {...rest}>
      {children}
    </Tag>
  );
}

/* ------------------------------------------------------------------- type -- */

/** OrbitType.eyebrow — 10.5px, +0.08em, uppercase. Section labels only. */
export function Eyebrow({ children }: { children: ReactNode }) {
  return <span className="type-eyebrow">{children}</span>;
}

/**
 * OrbitType.meta — the second line of a row: timestamps, tags, counts.
 * Deliberately not monospace. The screens reached for --font-mono here, which
 * made every timestamp read like a log line; Orbit has no mono role at all,
 * and Instrument's own tabular figures already stop numbers from jittering.
 */
export function Meta({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <span className="type-meta" style={{ fontVariantNumeric: "tabular-nums", ...style }}>
      {children}
    </span>
  );
}

/** A status/tag pill. Tone comes from TONE, which is already token-driven. */
export function Pill({
  tone = "neutral",
  children,
}: {
  tone?: keyof typeof TONE;
  children: ReactNode;
}) {
  const [bg, fg] = TONE[tone];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        height: "20px",
        paddingInline: "9px",
        borderRadius: "var(--radius-pill)",
        background: bg,
        color: fg,
        fontSize: "var(--size-eyebrow)",
        fontWeight: 600,
        letterSpacing: "0.01em",
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </span>
  );
}

/* ----------------------------------------------------------------- states -- */

const stateCard: CSSProperties = {
  ...cardBase,
  padding: "26px var(--o-lg)",
  textAlign: "center",
  fontSize: "var(--size-body)",
  lineHeight: 1.45,
};

export function LoadingCard({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="animate-pulse" style={{ ...stateCard, color: "var(--text-subtle)" }}>
      {label}
    </div>
  );
}

export function MemoryCardSkeleton() {
  const bar = (w: string, h = 12): CSSProperties => ({
    width: w,
    height: h,
    borderRadius: "var(--radius-xs)",
    background: "var(--surface-3)",
  });
  return (
    <div className="animate-pulse" style={{ ...rowBase, display: "flex", flexDirection: "column", gap: "8px" }}>
      <div style={bar("85%")} />
      <div style={bar("60%")} />
      <div style={{ display: "flex", gap: "6px", marginTop: "2px" }}>
        <div style={bar("52px", 19)} />
        <div style={bar("44px", 19)} />
      </div>
    </div>
  );
}

export function SkeletonList({ count = 4 }: { count?: number }) {
  return (
    <Stack>
      {Array.from({ length: count }, (_, i) => (
        <MemoryCardSkeleton key={i} />
      ))}
    </Stack>
  );
}

/**
 * The empty state. `children` is the one line that says what's missing; `hint`
 * is the thing the reader can do about it, which is the half that was usually
 * absent — "No memories yet" tells you nothing you didn't already know from
 * looking at the blank screen.
 */
export function EmptyCard({ children, hint }: { children: ReactNode; hint?: ReactNode }) {
  return (
    // Both lines stay legible on purpose. --text-subtle is 38% alpha, which is
    // fine for a decorative mark and not fine for the only sentence on an
    // otherwise blank screen — in light mode it washed out almost entirely.
    // Hierarchy comes from size instead.
    <div style={{ ...stateCard, color: "var(--text)" }}>
      <div>{children}</div>
      {hint ? (
        <div style={{ marginTop: "6px", fontSize: "var(--size-meta)", color: "var(--text-muted)" }}>{hint}</div>
      ) : null}
    </div>
  );
}

export function ErrorCard({ children }: { children: ReactNode }) {
  return (
    <div
      role="alert"
      style={{
        ...stateCard,
        background: "var(--danger-soft)",
        border: "1px solid var(--danger)",
        color: "var(--danger)",
        fontWeight: 600,
      }}
    >
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------- rows -- */

export function TaskRow({ task, showStatus = false }: { task: TaskMock; showStatus?: boolean }) {
  const [, fg] = TONE[task.tone];
  return (
    <Row>
      <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: fg, flexShrink: 0 }} />
      <span style={{ minWidth: 0, flex: 1 }}>
        <span
          style={{
            display: "block",
            fontSize: "var(--size-body)",
            fontWeight: 600,
            letterSpacing: "var(--tracking-snug)",
            ...(showStatus ? { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" } : null),
          }}
        >
          {task.title}
        </span>
        <Meta style={{ display: "block", marginTop: "1px" }}>{task.meta}</Meta>
      </span>
      {showStatus && <Pill tone={task.tone}>{task.status}</Pill>}
    </Row>
  );
}

/** Kept for the section-label call sites that predate <Section>. */
export const SectionEyebrow = Eyebrow;
