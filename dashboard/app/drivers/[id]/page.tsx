"use client";
// Run replay: every recorded step of one dev task's driver run, as a timeline,
// with the verifier verdicts and the review trail beside it.
import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  AlertTriangle,
  Brain,
  CheckCircle2,
  ChevronRight,
  ExternalLink,
  MessageSquare,
  ShieldCheck,
  Wrench,
  XCircle,
} from "lucide-react";
import {
  brief,
  duration,
  pretty,
  STAGE_TONE,
  stepFailed,
  toEntries,
  usd,
  useDevTask,
  useRunSteps,
  when,
  type RunStep,
  type VerificationAttempt,
} from "@/lib/observe";
import { Card, Empty, ErrorBox, Loading, Pill } from "@/components/observe-ui";

function Clipped({ text, cut }: { text: string; cut?: number }) {
  return (
    <>
      <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-surface-2 p-3 font-mono text-[11px] leading-relaxed text-ink-mid">
        {text}
      </pre>
      {cut && (
        <p className="mt-1 text-[11px] text-ink-low">
          Stored {text.length.toLocaleString()} of {cut.toLocaleString()} characters.
        </p>
      )}
    </>
  );
}

function ToolEntry({ call, result }: { call?: RunStep; result?: RunStep }) {
  const [open, setOpen] = useState(false);
  const bad = stepFailed(result);
  const empty = call && ["{}", "null", ""].includes(call.content.trim());
  return (
    <li className={`rounded-lg border p-3 ${bad ? "border-danger/40 bg-danger-soft" : "border-line bg-surface"}`}>
      <button
        type="button"
        className="flex w-full items-start gap-2 text-left"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <ChevronRight className={`mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-low transition-transform ${open ? "rotate-90" : ""}`} />
        <Wrench className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />
        <span className="min-w-0 flex-1">
          <span className="font-mono text-xs font-semibold text-ink">{call?.tool ?? result?.tool ?? "tool"}</span>
          <span className="ml-2 break-all text-xs text-ink-mid">{brief(call?.content)}</span>
          {empty && <Pill tone="danger">no arguments</Pill>}
        </span>
        {result &&
          (bad ? (
            <XCircle className="h-4 w-4 shrink-0 text-danger" aria-label="failed" />
          ) : (
            <CheckCircle2 className="h-4 w-4 shrink-0 text-success" aria-label="ok" />
          ))}
      </button>
      {(open || bad) && (
        <div className="pl-6">
          {call && open && <Clipped text={pretty(call.content)} />}
          {result && <Clipped text={result.content} cut={result.properties.original_chars} />}
        </div>
      )}
    </li>
  );
}

function Thinking({ step }: { step: RunStep }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="rounded-lg border border-dashed border-line p-3">
      <button
        type="button"
        className="flex w-full items-center gap-2 text-left text-xs text-ink-mid"
        onClick={() => setOpen((o) => !o)}
      >
        <Brain className="h-3.5 w-3.5" /> Reasoning
        <ChevronRight className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-90" : ""}`} />
      </button>
      {open && <p className="mt-2 whitespace-pre-wrap break-words text-xs italic text-ink-mid">{step.content}</p>}
    </li>
  );
}

function Verdicts({ attempt }: { attempt?: VerificationAttempt }) {
  if (!attempt) return null;
  return (
    <Card className="mt-3">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
        <ShieldCheck className="h-4 w-4" /> Verifiers — attempt {attempt.attempt}{" "}
        <Pill tone={attempt.passed ? "success" : "danger"}>{attempt.passed ? "passed" : "failed"}</Pill>
      </h3>
      <ul className="mt-2 space-y-1">
        {attempt.results.map((r) => (
          <li key={r.verifier} className="flex flex-wrap items-center gap-2 text-xs text-ink-mid">
            {r.inconclusive ? (
              <Pill>inconclusive</Pill>
            ) : r.passed ? (
              <CheckCircle2 className="h-3.5 w-3.5 text-success" />
            ) : (
              <XCircle className="h-3.5 w-3.5 text-danger" />
            )}
            <span className="font-mono">{r.verifier}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export default function RunReplayPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";
  const task = useDevTask(id);
  const t = task.data;
  const live = t?.status === "running" || t?.status === "queued";
  const steps = useRunSteps(id, live);
  const attempts = useMemo(
    () => [...new Set((steps.data?.steps ?? []).map((s) => s.attempt))].sort((a, b) => a - b),
    [steps.data],
  );
  const [pick, setPick] = useState<number | null>(null);
  const attempt = pick ?? attempts[0] ?? 1;
  const entries = useMemo(
    () => toEntries((steps.data?.steps ?? []).filter((s) => s.attempt === attempt)),
    [steps.data, attempt],
  );
  const toolCount = entries.filter((e) => e.type === "tool").length;
  const failures = entries.filter((e) => (e.type === "tool" && stepFailed(e.result)) || e.type === "error").length;

  return (
    <div className="space-y-4">
      <div>
        <Link href="/drivers" className="text-xs text-accent-text hover:underline">
          ← Dev tasks
        </Link>
        <h2 className="text-lg font-semibold text-ink">Run replay</h2>
      </div>
      <ErrorBox error={task.error ?? steps.error} />
      {!t && task.isLoading && <Loading />}

      {t && (
        <Card>
          <p className="text-sm font-medium text-ink break-words">{t.title || t.instruction}</p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-ink-mid">
            <Pill tone={STAGE_TONE[t.stage ?? ""] ?? "neutral"}>{t.stage ?? t.status}</Pill>
            {t.task_type === "plan" && <Pill>plan</Pill>}
            {t.driver && <span>{t.driver}</span>}
            {t.model && <span className="font-mono">· {t.model}</span>}
            <span>· {t.persona}</span>
            <span>· {duration(t.duration_ms)}</span>
            <span>· {usd(t.cost_usd)}</span>
            {t.num_turns != null && <span>· {t.num_turns} turns</span>}
            <span>· {when(t.created_at)}</span>
          </div>
          {(t.plan_task_id || t.pr_url) && (
            <div className="mt-2 flex flex-wrap gap-3 text-xs">
              {t.plan_task_id && (
                <span className="text-ink-mid">
                  Plan task {t.plan_task_index} of {t.plan_task_count}
                </span>
              )}
              {t.pr_url && (
                <a
                  className="inline-flex items-center gap-1 text-accent-text hover:underline"
                  href={t.pr_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Pull request <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
          )}
          {t.error && (
            <p className="mt-3 flex items-start gap-2 rounded-lg bg-danger-soft p-2.5 text-xs text-danger break-words">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {t.error}
            </p>
          )}
        </Card>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <section aria-label="Run timeline">
          {attempts.length > 1 && (
            <div className="mb-3 flex gap-2" role="tablist">
              {attempts.map((a) => (
                <button
                  key={a}
                  type="button"
                  role="tab"
                  aria-selected={a === attempt}
                  onClick={() => setPick(a)}
                  className={`rounded-lg border px-3 py-1.5 text-xs ${
                    a === attempt ? "border-accent bg-accent-soft text-accent-soft-fg" : "border-line text-ink-mid"
                  }`}
                >
                  {a === 1 ? "Attempt 1" : `Attempt ${a} (after bounce)`}
                </button>
              ))}
            </div>
          )}

          {steps.data && steps.data.count === 0 ? (
            <Empty icon={<MessageSquare className="h-5 w-5" />} title="No recorded steps">
              Steps are recorded for runs from 13 Oct 2026 on. Earlier runs kept only their final summary
              {t?.output ? ", shown below" : ""}.
            </Empty>
          ) : (
            <>
              <p className="mb-2 text-xs text-ink-low tabular-nums">
                {entries.length} steps · {toolCount} tool calls · {failures} failed
                {live && " · live, refreshing"}
              </p>
              <ol className="space-y-2">
                {entries.map((e, i) =>
                  e.type === "tool" ? (
                    <ToolEntry key={i} call={e.call} result={e.result} />
                  ) : e.type === "think" ? (
                    <Thinking key={i} step={e.step} />
                  ) : e.type === "error" ? (
                    <li key={i} className="flex items-start gap-2 rounded-lg bg-danger-soft p-3 text-xs text-danger break-words">
                      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {e.step.content}
                    </li>
                  ) : (
                    <li key={i} className="rounded-lg bg-surface-2 p-3 text-sm text-ink whitespace-pre-wrap break-words">
                      {e.step.content}
                    </li>
                  ),
                )}
              </ol>
            </>
          )}

          <Verdicts attempt={t?.verification?.find((v) => v.attempt === attempt)} />

          {t?.output && (steps.data?.count === 0 || attempt === attempts[attempts.length - 1]) && (
            <Card className="mt-3">
              <h3 className="text-sm font-semibold text-ink">Final summary</h3>
              <p className="mt-2 whitespace-pre-wrap break-words text-xs text-ink-mid">{t.output}</p>
            </Card>
          )}
        </section>

        <aside aria-label="Review trail">
          <Card>
            <h3 className="text-sm font-semibold text-ink">Review trail</h3>
            {(t?.approvals ?? []).length === 0 && (
              <p className="mt-2 text-xs text-ink-low">No approvals filed for this task.</p>
            )}
            <ol className="mt-2 space-y-3">
              {(t?.approvals ?? []).map((a) => (
                <li key={a.id} className="text-xs">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="font-mono text-ink">{a.kind}</span>
                    <Pill tone={a.status === "approved" ? "success" : a.status === "rejected" ? "danger" : "warning"}>
                      {a.status}
                    </Pill>
                  </div>
                  {a.note && <p className="mt-1 break-words text-ink-mid">{a.note}</p>}
                  {a.resolved_at && (
                    <p className="mt-0.5 text-[11px] text-ink-low">
                      {when(a.resolved_at)}
                      {a.resolved_by ? ` · ${a.resolved_by}` : ""}
                    </p>
                  )}
                </li>
              ))}
            </ol>
          </Card>
        </aside>
      </div>
    </div>
  );
}
