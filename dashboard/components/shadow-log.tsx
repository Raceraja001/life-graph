"use client";
// Shadow-log grading queue: while an autonomous actor is "in shadow", every
// action it would have taken is recorded here instead of executed. The user
// watches the log and one-taps good/bad — grading feeds trust and is what
// lets the actor graduate to acting for real (see core/shadow.py). Mirrors
// the mobile card conventions used by ambient-roles.tsx and m/approvals.
import type { CSSProperties } from "react";
import { LoadingCard, EmptyCard, ErrorCard, SectionEyebrow } from "@/components/mobile/parts";
import { useShadowRuns, useGradeShadowRun, type ShadowRunVM } from "@/lib/mobile-api";

const cardStyle: CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-card)",
  padding: "14px",
};

const RISK_BADGE: Record<string, { bg: string; fg: string; label: string }> = {
  safe: { bg: "var(--success-soft)", fg: "var(--success)", label: "safe" },
  low: { bg: "var(--success-soft)", fg: "var(--success)", label: "low" },
  moderate: { bg: "var(--warning-soft)", fg: "var(--warning)", label: "moderate" },
  medium: { bg: "var(--warning-soft)", fg: "var(--warning)", label: "medium" },
  dangerous: { bg: "var(--danger-soft)", fg: "var(--danger)", label: "dangerous" },
  high: { bg: "var(--danger-soft)", fg: "var(--danger)", label: "high" },
};

export function RiskBadge({ risk }: { risk: string | null | undefined }) {
  if (!risk) return null;
  const style = RISK_BADGE[risk.toLowerCase()] ?? { bg: "var(--surface-3)", fg: "var(--text-subtle)", label: risk };
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        height: "20px",
        paddingInline: "8px",
        borderRadius: "var(--radius-pill)",
        background: style.bg,
        color: style.fg,
        fontSize: "var(--size-eyebrow)",
        fontWeight: 600,
        textTransform: "uppercase",
        letterSpacing: "var(--tracking-caps)",
        flexShrink: 0,
      }}
    >
      {style.label}
    </span>
  );
}

export default function ShadowLog() {
  const runs = useShadowRuns();
  const grade = useGradeShadowRun();
  const items = runs.data ?? [];
  const busyId = grade.isPending ? grade.variables?.id : undefined;

  return (
    <>
      <p style={{ fontSize: "var(--size-meta)", color: "var(--text-muted)", margin: "0 0 var(--space-row)", lineHeight: 1.5 }}>
        What autonomous actions WOULD have run. Grade them — enough good grades and the actor
        graduates to acting for real.
      </p>

      <SectionEyebrow>Ungraded runs</SectionEyebrow>
      {runs.isLoading && <LoadingCard label="Loading shadow log…" />}
      {runs.isError && <ErrorCard>Can&rsquo;t reach the shadow log — is the backend running?</ErrorCard>}
      {!runs.isLoading && !runs.isError && items.length === 0 && (
        <EmptyCard hint="Actions an agent would have taken land here for you to grade before it earns the right to act.">
          Nothing waiting on a grade.
        </EmptyCard>
      )}
      {!runs.isLoading &&
        !runs.isError &&
        items.map((run) => (
          <ShadowRunCard
            key={run.id}
            run={run}
            busy={busyId === run.id}
            onGrade={(g) => grade.mutate({ id: run.id, grade: g })}
          />
        ))}
    </>
  );
}

function ShadowRunCard({
  run,
  busy,
  onGrade,
}: {
  run: ShadowRunVM;
  busy: boolean;
  onGrade: (grade: "good" | "bad") => void;
}) {
  return (
    <section style={{ ...cardStyle, opacity: busy ? 0.6 : 1 }}>
      <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
        <span style={{ fontSize: "var(--size-body)", fontWeight: 600, flex: 1, minWidth: 0 }}>
          {run.actionType}
        </span>
        <RiskBadge risk={run.riskLevel} />
      </div>
      <div
        style={{
          fontVariantNumeric: "tabular-nums",
          fontSize: "var(--size-meta)",
          color: "var(--text-muted)",
          marginTop: "6px",
          lineHeight: 1.5,
          wordBreak: "break-word",
        }}
      >
        {run.command}
      </div>
      <div style={{ fontSize: "var(--size-meta)", color: "var(--text-subtle)", marginTop: "6px" }}>
        would have {run.wouldHaveRouted.replace(/_/g, " ")} · agent {run.agentId}
        {run.projectId ? ` · ${run.projectId}` : ""}
      </div>

      <div style={{ display: "flex", gap: "8px", marginTop: "11px" }}>
        <button
          onClick={() => onGrade("good")}
          disabled={busy}
          style={{
            flex: 1,
            height: "40px",
            border: 0,
            borderRadius: "var(--radius-control)",
            background: "var(--accent)",
            color: "var(--accent-fg)",
            fontFamily: "inherit",
            fontSize: "var(--size-body)",
            fontWeight: 600,
            cursor: busy ? "default" : "pointer",
          }}
        >
          {busy ? "…" : "Good"}
        </button>
        <button
          onClick={() => onGrade("bad")}
          disabled={busy}
          style={{
            flex: 1,
            height: "40px",
            border: "1px solid var(--border-strong)",
            borderRadius: "var(--radius-control)",
            background: "var(--surface)",
            color: "var(--text)",
            fontFamily: "inherit",
            fontSize: "var(--size-body)",
            fontWeight: 600,
            cursor: busy ? "default" : "pointer",
          }}
        >
          Bad
        </button>
      </div>
    </section>
  );
}
