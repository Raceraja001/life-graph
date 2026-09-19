"use client";
import { useState } from "react";
import { BarChart3, Check, CircleHelp, Plus, Sparkles, X } from "lucide-react";
import {
  useAcceptPrediction,
  useCalibration,
  useCreatePrediction,
  useDismissPrediction,
  usePredictions,
  useResolvePrediction,
} from "@/lib/hooks";
import type { BiasFinding, CalibrationBucket, CalibrationReport, Prediction, PredictionOutcome } from "@/lib/api";

const pct = (x: number) => `${Math.round(x * 100)}%`;

/** A yyyy-mm-dd from a date input → the end of that local day, as ISO. */
function endOfDayIso(date: string): string | null {
  return date ? new Date(`${date}T23:59:59`).toISOString() : null;
}

function toDateInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

function dueLabel(iso: string | null, now: number): string {
  if (!iso) return "no deadline";
  const days = Math.ceil((new Date(iso).getTime() - now) / 86_400_000);
  if (days < 0) return `due ${-days}d ago`;
  if (days === 0) return "due today";
  return `in ${days}d`;
}

export default function CalibrationPage() {
  const calibration = useCalibration();
  const suggested = usePredictions("suggested");
  const pending = usePredictions("pending");
  const resolved = usePredictions("resolved");
  // One clock per mount keeps "due" and "upcoming" consistent with each other.
  const [now] = useState(() => Date.now());

  const open = pending.data ?? [];
  const due = open.filter((p) => p.resolve_by && new Date(p.resolve_by).getTime() <= now);
  const upcoming = open
    .filter((p) => !due.includes(p))
    .sort((a, b) => (a.resolve_by ?? "9999").localeCompare(b.resolve_by ?? "9999"));

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-ink">Calibration</h2>
        <p className="text-sm text-ink-mid">
          How often your “80% sure” turns out right. Log predictions, resolve them when you know, and the
          curve shows where your confidence runs high or low.
        </p>
      </div>

      {calibration.isError ? (
        <div className="bg-danger-soft border border-danger/30 rounded-xl p-5 text-sm text-danger">
          Cannot load calibration — check API connection
        </div>
      ) : calibration.data ? (
        calibration.data.status === "ok" ? (
          <CalibrationSummary report={calibration.data} />
        ) : (
          <Progress report={calibration.data} />
        )
      ) : (
        <div className="bg-surface border border-line rounded-xl p-8 text-center text-sm text-ink-low animate-pulse">
          Loading calibration...
        </div>
      )}

      <NewPredictionForm />

      {(suggested.data?.length ?? 0) > 0 && (
        <Section
          title="Suggested from your captures"
          hint="Claims you made with a number attached. Track the ones that are real predictions."
        >
          {suggested.data!.map((p) => (
            <SuggestionRow key={p.id} p={p} />
          ))}
        </Section>
      )}

      {due.length > 0 && (
        <Section title={`Due for resolution (${due.length})`} hint="Did these come true?">
          {due.map((p) => (
            <PredictionRow key={p.id} p={p} now={now} />
          ))}
        </Section>
      )}

      <Section title={`Pending (${upcoming.length})`} hint="You can resolve early once you know.">
        {upcoming.length > 0 ? (
          upcoming.map((p) => <PredictionRow key={p.id} p={p} now={now} />)
        ) : (
          <p className="px-5 py-4 text-sm text-ink-low">No open predictions. Add one above.</p>
        )}
      </Section>

      {(resolved.data?.length ?? 0) > 0 && (
        <Section title="Recently resolved">
          {resolved.data!.map((p) => (
            <ResolvedRow key={p.id} p={p} />
          ))}
        </Section>
      )}
    </div>
  );
}

// ── Summary ─────────────────────────────────────────────

function Progress({ report }: { report: CalibrationReport }) {
  const done = Math.min(report.resolved_count, report.required);
  return (
    <div className="bg-surface border border-line rounded-xl p-6 space-y-4">
      <div className="flex items-start gap-4">
        <div className="w-12 h-12 rounded-xl bg-accent-soft flex items-center justify-center shrink-0">
          <BarChart3 className="w-6 h-6 text-accent" />
        </div>
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-ink">
            {done} of {report.required} resolved predictions
          </h3>
          <p className="text-sm text-ink-mid">
            Your curve and Brier score appear at {report.required}. With fewer, the numbers would be noise.
            {report.pending_count > 0 && ` ${report.pending_count} still open.`}
          </p>
        </div>
      </div>
      <div className="h-2 bg-surface-3 rounded-full overflow-hidden">
        <div className="h-full bg-accent rounded-full" style={{ width: `${(done / report.required) * 100}%` }} />
      </div>
    </div>
  );
}

function CalibrationSummary({ report }: { report: CalibrationReport }) {
  const brier = report.brier_score ?? 0;
  const trend = report.trend?.delta_pct;
  return (
    <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
      <div className="bg-surface border border-line rounded-xl p-6 space-y-4">
        <div>
          <p className="text-xs font-medium text-ink-low uppercase tracking-wider">Brier score</p>
          <p className="text-3xl font-semibold text-ink tabular-nums">{brier.toFixed(3)}</p>
          <p className="text-xs text-ink-mid">
            0 is perfect; always saying 50% scores 0.25. Last {report.window_days} days.
          </p>
          {trend != null && (
            <p className={`text-sm font-medium mt-1 ${trend <= 0 ? "text-success" : "text-danger"}`}>
              {trend <= 0 ? `Improved ${Math.abs(trend)}%` : `Worse by ${trend}%`} vs the previous{" "}
              {report.window_days} days
            </p>
          )}
        </div>
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <Stat label="Resolved" value={report.resolved_count} />
          <Stat label="Open" value={report.pending_count} />
          <Stat label="Unclear" value={report.unresolved_rate == null ? "—" : pct(report.unresolved_rate)} />
        </dl>
        {report.bias_findings.length > 0 && (
          <ul className="space-y-2">
            {report.bias_findings.map((f, i) => (
              <li key={i} className="text-sm bg-warning-soft text-ink rounded-lg px-3 py-2">
                {describeFinding(f)}
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="bg-surface border border-line rounded-xl p-6">
        <p className="text-xs font-medium text-ink-low uppercase tracking-wider mb-2">Claimed vs actual</p>
        <CalibrationCurve buckets={report.buckets} />
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <dt className="text-xs text-ink-low">{label}</dt>
      <dd className="font-semibold text-ink tabular-nums">{value}</dd>
    </div>
  );
}

function describeFinding(f: BiasFinding): string {
  if (f.kind === "bucket" && f.claimed != null && f.actual != null) {
    return `When you say about ${pct(f.claimed)}, you're right ${pct(f.actual)} of the time (${f.n} predictions): ${f.direction}.`;
  }
  const conf = f.avg_confidence != null ? pct(f.avg_confidence) : "?";
  const hit = f.hit_rate != null ? pct(f.hit_rate) : "?";
  return `Overall you're ${f.direction}: average confidence ${conf}, right ${hit} of the time.`;
}

/** Claimed confidence (x) against hit rate (y); the dashed diagonal is perfect calibration. */
function CalibrationCurve({ buckets }: { buckets: CalibrationBucket[] }) {
  const W = 320;
  const H = 240;
  const pad = { l: 36, r: 12, t: 10, b: 30 };
  const x = (v: number) => pad.l + ((v - 0.5) / 0.5) * (W - pad.l - pad.r);
  const y = (v: number) => H - pad.b - v * (H - pad.t - pad.b);
  const filled = buckets.filter((b) => b.count > 0);
  const maxN = Math.max(1, ...filled.map((b) => b.count));
  const path = filled.map((b, i) => `${i ? "L" : "M"}${x(b.avg_confidence)},${y(b.hit_rate)}`).join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="Calibration curve">
      {[0, 0.25, 0.5, 0.75, 1].map((v) => (
        <g key={`y${v}`}>
          <line x1={pad.l} x2={W - pad.r} y1={y(v)} y2={y(v)} stroke="var(--color-line)" />
          <text x={pad.l - 6} y={y(v) + 4} textAnchor="end" fontSize="10" fill="var(--color-ink-low)">
            {pct(v)}
          </text>
        </g>
      ))}
      {[0.5, 0.6, 0.7, 0.8, 0.9, 1].map((v) => (
        <text key={`x${v}`} x={x(v)} y={H - pad.b + 14} textAnchor="middle" fontSize="10" fill="var(--color-ink-low)">
          {pct(v)}
        </text>
      ))}
      <text x={(W + pad.l) / 2} y={H - 2} textAnchor="middle" fontSize="10" fill="var(--color-ink-mid)">
        how sure you said you were
      </text>
      <line x1={x(0.5)} y1={y(0.5)} x2={x(1)} y2={y(1)} stroke="var(--color-ink-low)" strokeDasharray="4 4" />
      {path && <path d={path} fill="none" stroke="var(--color-accent)" strokeWidth="2" />}
      {filled.map((b) => (
        <circle
          key={b.range_label}
          cx={x(b.avg_confidence)}
          cy={y(b.hit_rate)}
          r={4 + (b.count / maxN) * 6}
          fill="var(--color-accent)"
          fillOpacity="0.85"
        >
          <title>{`${b.range_label}: said ${pct(b.avg_confidence)}, right ${pct(b.hit_rate)} (${b.count})`}</title>
        </circle>
      ))}
    </svg>
  );
}

// ── Lists ───────────────────────────────────────────────

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="bg-surface border border-line rounded-xl overflow-hidden">
      <div className="px-5 py-3 border-b border-line">
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        {hint && <p className="text-xs text-ink-mid">{hint}</p>}
      </div>
      <div className="divide-y divide-line">{children}</div>
    </section>
  );
}

function Confidence({ value }: { value: number }) {
  return (
    <span className="text-[11px] px-2 py-0.5 rounded-full bg-accent-soft text-accent-text font-medium tabular-nums">
      {pct(value)}
    </span>
  );
}

function PredictionRow({ p, now }: { p: Prediction; now: number }) {
  const resolve = useResolvePrediction();
  const busy = resolve.isPending;
  const act = (outcome: PredictionOutcome) => resolve.mutate({ id: p.id, outcome });
  return (
    <div className="px-5 py-3 flex flex-wrap items-center gap-3">
      <div className="flex-1 min-w-[12rem]">
        <p className="text-sm text-ink">{p.statement}</p>
        <p className="text-xs text-ink-low mt-0.5">
          {dueLabel(p.resolve_by, now)}
          {p.domain_tags.length > 0 && ` · ${p.domain_tags.join(", ")}`}
        </p>
      </div>
      <Confidence value={p.confidence} />
      <div className="flex items-center gap-1.5">
        <ActionButton onClick={() => act("correct")} disabled={busy} tone="success" label="It happened">
          <Check className="w-3.5 h-3.5" />
        </ActionButton>
        <ActionButton onClick={() => act("incorrect")} disabled={busy} tone="danger" label="It didn't">
          <X className="w-3.5 h-3.5" />
        </ActionButton>
        <ActionButton onClick={() => act("ambiguous")} disabled={busy} tone="neutral" label="Unclear">
          <CircleHelp className="w-3.5 h-3.5" />
        </ActionButton>
      </div>
      {resolve.isError && <p className="basis-full text-xs text-danger">{String(resolve.error)}</p>}
    </div>
  );
}

function SuggestionRow({ p }: { p: Prediction }) {
  const accept = useAcceptPrediction();
  const dismiss = useDismissPrediction();
  const [date, setDate] = useState(toDateInput(p.resolve_by));
  const busy = accept.isPending || dismiss.isPending;
  return (
    <div className="px-5 py-3 flex flex-wrap items-center gap-3">
      <div className="flex-1 min-w-[12rem]">
        <p className="text-sm text-ink flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-accent shrink-0" />
          {p.statement}
        </p>
        {p.resolution_criteria.quote && (
          <p className="text-xs text-ink-low mt-0.5 italic line-clamp-2">“{p.resolution_criteria.quote}”</p>
        )}
      </div>
      <Confidence value={p.confidence} />
      <input
        type="date"
        value={date}
        onChange={(e) => setDate(e.target.value)}
        aria-label="Resolve by"
        className="bg-surface border border-line rounded-lg px-2 py-1 text-xs text-ink focus:outline-none focus:border-accent"
      />
      <div className="flex items-center gap-1.5">
        <button
          onClick={() => accept.mutate({ id: p.id, body: { resolve_by: endOfDayIso(date) } })}
          disabled={busy}
          className="text-xs px-3 py-1.5 rounded-lg bg-accent text-accent-fg hover:bg-accent-hover disabled:opacity-50"
        >
          Track it
        </button>
        <button
          onClick={() => dismiss.mutate(p.id)}
          disabled={busy}
          className="text-xs px-3 py-1.5 rounded-lg text-ink-mid hover:bg-surface-3 disabled:opacity-50"
        >
          Dismiss
        </button>
      </div>
      {(accept.isError || dismiss.isError) && (
        <p className="basis-full text-xs text-danger">{String(accept.error ?? dismiss.error)}</p>
      )}
    </div>
  );
}

const OUTCOME_STYLE: Record<string, { label: string; cls: string }> = {
  correct: { label: "Happened", cls: "bg-success-soft text-success" },
  incorrect: { label: "Didn't", cls: "bg-danger-soft text-danger" },
  ambiguous: { label: "Unclear", cls: "bg-surface-3 text-ink-mid" },
};

function ResolvedRow({ p }: { p: Prediction }) {
  const style = OUTCOME_STYLE[p.outcome] ?? OUTCOME_STYLE.ambiguous;
  return (
    <div className="px-5 py-3 flex flex-wrap items-center gap-3">
      <p className="flex-1 min-w-[12rem] text-sm text-ink-mid">{p.statement}</p>
      <Confidence value={p.confidence} />
      <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${style.cls}`}>{style.label}</span>
    </div>
  );
}

function ActionButton({
  onClick,
  disabled,
  tone,
  label,
  children,
}: {
  onClick: () => void;
  disabled: boolean;
  tone: "success" | "danger" | "neutral";
  label: string;
  children: React.ReactNode;
}) {
  const cls = {
    success: "bg-success-soft text-success",
    danger: "bg-danger-soft text-danger",
    neutral: "bg-surface-3 text-ink-mid",
  }[tone];
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className={`w-8 h-8 flex items-center justify-center rounded-lg ${cls} hover:opacity-80 disabled:opacity-50`}
    >
      {children}
    </button>
  );
}

// ── New prediction ──────────────────────────────────────

function NewPredictionForm() {
  const create = useCreatePrediction();
  const [statement, setStatement] = useState("");
  const [confidence, setConfidence] = useState(70);
  const [date, setDate] = useState("");
  const [domain, setDomain] = useState("");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!statement.trim()) return;
    create.mutate(
      {
        statement: statement.trim(),
        confidence: confidence / 100,
        resolve_by: endOfDayIso(date),
        domain_tags: domain.trim() ? [domain.trim().toLowerCase()] : [],
      },
      {
        onSuccess: () => {
          setStatement("");
          setDate("");
        },
      }
    );
  };

  const field =
    "bg-surface border border-line rounded-lg px-3 py-2 text-sm text-ink placeholder-ink-low focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft";

  return (
    <form onSubmit={submit} className="bg-surface border border-line rounded-xl p-5 space-y-3">
      <h3 className="text-sm font-semibold text-ink">New prediction</h3>
      <input
        value={statement}
        onChange={(e) => setStatement(e.target.value)}
        placeholder="Something you can check later, e.g. “The migration is done by Friday”"
        className={`${field} w-full`}
      />
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-ink-mid">
          How sure
          <input
            type="range"
            min={50}
            max={99}
            value={confidence}
            onChange={(e) => setConfidence(Number(e.target.value))}
            className="w-32 accent-[var(--color-accent)]"
          />
          <span className="w-10 font-semibold text-ink tabular-nums">{confidence}%</span>
        </label>
        <label className="flex items-center gap-2 text-sm text-ink-mid">
          By
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={field} />
        </label>
        <input
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          placeholder="Area (optional), e.g. work"
          className={`${field} w-44`}
        />
        <button
          type="submit"
          disabled={!statement.trim() || create.isPending}
          className="ml-auto flex items-center gap-1.5 text-sm px-4 py-2 rounded-lg bg-accent text-accent-fg hover:bg-accent-hover disabled:opacity-50"
        >
          <Plus className="w-4 h-4" />
          Add
        </button>
      </div>
      {create.isError && <p className="text-xs text-danger">{String(create.error)}</p>}
    </form>
  );
}
