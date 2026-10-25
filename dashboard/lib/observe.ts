"use client";
// Agent observability: run replays, scorecards, failures and the agents
// console. Ported from life-graph-ui (src/lib/observe.ts) on 2026-10-25 so the
// repo dashboard is the one UI. Backend: docs/specs/agent-observability.md.
import { useQuery } from "@tanstack/react-query";
import { GET } from "./api";

// ── Types ──────────────────────────────────────────────────────────────

export interface ApprovalRef {
  id: string;
  kind: string;
  status: string;
  title?: string;
  note?: string | null;
  resolved_by?: string | null;
  resolved_at?: string | null;
}

export interface VerifierVerdict {
  verifier: string;
  passed: boolean;
  inconclusive?: boolean;
  evidence?: Record<string, unknown>;
}

export interface VerificationAttempt {
  attempt: number;
  passed: boolean;
  results: VerifierVerdict[];
}

export interface FailureCause {
  cause: string;
  label: string;
  detail?: string | null;
  signals?: string[];
}

export interface DevTaskDetail {
  id: string;
  title?: string;
  instruction?: string;
  task_type?: string;
  project_name?: string;
  persona?: string;
  driver?: string | null;
  model?: string | null;
  num_turns?: number | null;
  origin?: string;
  plan_task_id?: string | null;
  plan_task_index?: number | null;
  plan_task_count?: number | null;
  status?: string;
  stage?: string;
  error?: string | null;
  output?: string | null;
  cost_usd?: number | null;
  duration_ms?: number | null;
  branch?: string | null;
  pr_url?: string | null;
  merge_commit?: string | null;
  approvals: ApprovalRef[];
  verification?: VerificationAttempt[];
  created_at?: string;
}

export interface RunStep {
  attempt: number;
  seq: number;
  driver: string;
  /** text · thinking · tool_call · tool_result · error (open set) */
  kind: string;
  tool?: string | null;
  content: string;
  properties: { ref?: string; is_error?: boolean; original_chars?: number };
  at?: string | null;
}

export interface Scorecard {
  driver: string;
  models: string[];
  personas: string[];
  runs: number;
  succeeded: number;
  failed: number;
  bounced: number;
  merged: number;
  plan_runs: number;
  cost_usd: number;
  success_rate: number;
  bounce_rate: number;
  cost_per_merged: number | null;
  top_causes: { cause: string; label: string; count: number }[];
}

export interface AutoMergeStatus {
  persona: string;
  driver: string;
  project_name: string;
  merged: number;
  failed: number;
  total: number;
  merge_rate: number;
  established: boolean;
  threshold: number;
  auto_merge: boolean;
  earning_auto_merge?: boolean;
}

export interface FailureRow extends FailureCause {
  id: string;
  title?: string;
  status: string;
  error?: string | null;
  persona?: string;
  driver?: string | null;
  task_type?: string;
  created_at?: string;
  has_steps: boolean;
}

export interface AgentView {
  name: string;
  display_name?: string;
  icon?: string;
  description?: string;
  model: string;
  driver?: string | null;
  tools: { name: string; registered: boolean }[];
  missing_tools: string[];
  unscoped: boolean;
  notes: string[];
}

// ── Calls ──────────────────────────────────────────────────────────────

const data = <T>(p: Promise<{ data: T }>) => p.then((r) => r.data);

export const observe = {
  task: (id: string) => data(GET<{ data: DevTaskDetail }>(`/kernel/drivers/tasks/${id}`)),
  steps: (id: string) =>
    data(
      GET<{ data: { task_id: string; count: number; steps: RunStep[] } }>(
        `/kernel/drivers/tasks/${id}/steps`,
      ),
    ),
  scorecards: (days: number) =>
    data(
      GET<{ data: { days: number; cards: Scorecard[]; auto_merge: AutoMergeStatus[] } }>(
        "/kernel/drivers/scorecards",
        { days: String(days) },
      ),
    ),
  failures: (days: number) =>
    data(
      GET<{
        data: {
          days: number;
          total: number;
          groups: { cause: string; label: string; count: number }[];
          failures: FailureRow[];
        };
      }>("/kernel/drivers/failures", { days: String(days) }),
    ),
  agents: () => data(GET<{ data: AgentView[] }>("/kernel/observability/agents")),
};

// ── Hooks ──────────────────────────────────────────────────────────────

export function useDevTask(id: string) {
  return useQuery({ queryKey: ["dev-tasks", id], queryFn: () => observe.task(id), enabled: !!id });
}
/** Steps of one run; polls while the task is still running. */
export function useRunSteps(id: string, live: boolean) {
  return useQuery({
    queryKey: ["dev-task-steps", id],
    queryFn: () => observe.steps(id),
    enabled: !!id,
    refetchInterval: live ? 5000 : false,
  });
}
export function useScorecards(days: number) {
  return useQuery({ queryKey: ["scorecards", days], queryFn: () => observe.scorecards(days) });
}
export function useFailures(days: number) {
  return useQuery({ queryKey: ["failures", days], queryFn: () => observe.failures(days) });
}
export function useAgents() {
  return useQuery({ queryKey: ["observability-agents"], queryFn: () => observe.agents() });
}

// ── Pure helpers (unit-tested in tests/observe.test.ts) ────────────────

export type Entry =
  | { type: "say"; step: RunStep }
  | { type: "think"; step: RunStep }
  | { type: "tool"; call?: RunStep; result?: RunStep }
  | { type: "error"; step: RunStep };

/** Pair each tool call with its result: by `ref` when the driver sets one,
 *  else the next result after the last open call. */
export function toEntries(steps: RunStep[]): Entry[] {
  const out: Entry[] = [];
  const open = new Map<string, Extract<Entry, { type: "tool" }>>();
  let lastOpen: Extract<Entry, { type: "tool" }> | undefined;
  for (const s of steps) {
    if (s.kind === "tool_call") {
      const e: Extract<Entry, { type: "tool" }> = { type: "tool", call: s };
      out.push(e);
      if (s.properties.ref) open.set(s.properties.ref, e);
      lastOpen = e;
    } else if (s.kind === "tool_result") {
      const e =
        (s.properties.ref && open.get(s.properties.ref)) ||
        (lastOpen && !lastOpen.result ? lastOpen : undefined);
      if (e) e.result = s;
      else out.push({ type: "tool", result: s });
    } else if (s.kind === "thinking") out.push({ type: "think", step: s });
    else if (s.kind === "error") out.push({ type: "error", step: s });
    else out.push({ type: "say", step: s });
  }
  return out;
}

export const stepFailed = (s?: RunStep) =>
  Boolean(s && (s.properties.is_error || /^\s*\{\s*"error"/.test(s.content)));

export function pretty(json: string): string {
  try {
    return JSON.stringify(JSON.parse(json), null, 2);
  } catch {
    return json;
  }
}

/** One-line summary of a tool call's input: its first argument value. */
export function brief(json?: string): string {
  if (!json) return "";
  try {
    const v = JSON.parse(json);
    if (v && typeof v === "object") {
      const first = Object.values(v)[0];
      const text = typeof first === "string" ? first : JSON.stringify(first ?? v);
      return text.length > 90 ? `${text.slice(0, 90)}…` : text;
    }
    return String(v);
  } catch {
    return json.slice(0, 90);
  }
}

export function when(iso?: string | null): string {
  return iso ? new Date(iso).toLocaleString() : "—";
}

export function usd(n?: number | null, digits = 2): string {
  if (n == null) return "—";
  return `$${n.toFixed(n !== 0 && Math.abs(n) < 0.01 ? 4 : digits)}`;
}

export function pct(n?: number | null): string {
  return n == null ? "—" : `${Math.round(n * 100)}%`;
}

export function duration(ms?: number | null): string {
  if (!ms) return "—";
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return m < 60 ? `${m}m ${s % 60}s` : `${Math.floor(m / 60)}h ${m % 60}m`;
}

export type Tone = "success" | "warning" | "danger" | "info" | "neutral";

/** Badge classes per tone, in the dashboard's tokens. */
export const TONE_CLS: Record<Tone, string> = {
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning",
  danger: "bg-danger-soft text-danger",
  info: "bg-info-soft text-info",
  neutral: "bg-surface-3 text-ink-mid",
};

export const STAGE_TONE: Record<string, Tone> = {
  merged: "success",
  completed: "success",
  landed: "info",
  pr_open: "info",
  awaiting_pr: "warning",
  awaiting_merge: "warning",
  needs_review: "warning",
  queued: "neutral",
  running: "info",
  failed: "danger",
  pr_rejected: "danger",
  closed: "neutral",
  cancelled: "neutral",
};

export function autoMergeState(a: AutoMergeStatus): { label: string; tone: Tone } {
  if (a.auto_merge && a.earning_auto_merge) return { label: "active", tone: "success" };
  if (a.auto_merge) return { label: "opted in — bar not met", tone: "warning" };
  if (a.earning_auto_merge) return { label: "bar met — project not opted in", tone: "info" };
  return { label: "off", tone: "neutral" };
}
