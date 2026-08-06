"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { Tone } from "./mobile-mock";

// View-models the mobile screens render. Mappers below translate the backend's
// loosely-typed payloads into these, so the screens stay clean and defensive.

export interface MemoryVM {
  id: string;
  content: string;
  imp: number; // 0..1 importance
  tags: string[];
  source: string;
  created: string; // "Jul 10"
  meta: string; // "source · Jul 10"
  properties?: Record<string, unknown>;
  status: string; // "pending" | "active" | ...
  _optimistic?: boolean; // true = local optimistic card, not yet persisted
}

export type TaskGroup = "inflight" | "queued" | "done";

export interface TaskVM {
  id: string;
  title: string;
  meta: string;
  status: string; // display label
  tone: Tone;
  group: TaskGroup;
}

function shortDate(iso?: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "" : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function mapMemory(raw: any): MemoryVM {
  const source = raw?.source || "capture";
  const created = shortDate(raw?.created_at);
  return {
    id: String(raw?.id ?? ""),
    content: raw?.content ?? "",
    imp: typeof raw?.importance === "number" ? raw.importance : 0.5,
    tags: Array.isArray(raw?.tags) ? raw.tags : [],
    source,
    created,
    meta: created ? `${source} · ${created}` : source,
    properties: raw?.properties,
    status: raw?.status ?? "active",
    _optimistic: raw?._optimistic === true,
  };
}

// Kernel task status → mobile tone + board group + display label.
const STATUS_MAP: Record<string, { tone: Tone; group: TaskGroup; label: string }> = {
  queued: { tone: "neutral", group: "queued", label: "queued" },
  running: { tone: "info", group: "inflight", label: "running" },
  verifying: { tone: "warning", group: "inflight", label: "verifying" },
  completed: { tone: "success", group: "done", label: "done" },
  landed: { tone: "success", group: "done", label: "done" },
  done: { tone: "success", group: "done", label: "done" },
  failed: { tone: "danger", group: "inflight", label: "failed" },
  error: { tone: "danger", group: "inflight", label: "failed" },
  cancelled: { tone: "neutral", group: "done", label: "cancelled" },
};

export function mapTask(raw: any): TaskVM {
  const status = String(raw?.status ?? "queued").toLowerCase();
  const m = STATUS_MAP[status] ?? { tone: "neutral" as Tone, group: "inflight" as TaskGroup, label: status };
  return {
    id: String(raw?.id ?? ""),
    title: raw?.description || raw?.intent || raw?.title || String(raw?.id ?? "task"),
    meta: raw?.persona || "system",
    status: m.label,
    tone: m.tone,
    group: m.group,
  };
}

export const TASK_GROUPS: Array<{ id: TaskGroup; title: string }> = [
  { id: "inflight", title: "In flight" },
  { id: "queued", title: "Queued" },
  { id: "done", title: "Done today" },
];

// ── Hooks (share query keys with the desktop hooks so WebSocket
//    cache-invalidation refreshes both surfaces) ──────────────────
export function useMobileMemories(limit = 50) {
  return useQuery({
    queryKey: ["memories", { limit: String(limit) }],
    queryFn: () => api.memories.list({ limit: String(limit) }),
    select: (rows: any[]) => rows.map(mapMemory),
  });
}

export function useMobileMemorySearch(query: string) {
  return useQuery({
    queryKey: ["memory-search", query],
    queryFn: () => api.memories.search(query),
    enabled: query.trim().length > 2,
    select: (rows: any[]) => rows.map(mapMemory),
  });
}

export function useMobileTasks() {
  return useQuery({
    queryKey: ["tasks", { limit: "100" }],
    queryFn: () => api.kernel.tasks.list({ limit: "100" }),
    select: (rows: any[]) => rows.map(mapTask),
  });
}

// ── Approvals ─────────────────────────────────────────────────
export interface ApprovalVM {
  id: string;
  kind: string;
  title: string;
  detail: string;
  status: string;
  source: string;
  // Populated for kind==="autonomous_action" rows from the AutonomousApprovalProducer's
  // Approval.payload (Task 6/9) — null for every other producer's rows.
  riskLevel: string | null;
}

export function mapApproval(raw: any): ApprovalVM {
  return {
    id: String(raw?.id ?? ""),
    kind: raw?.kind ?? "",
    title: raw?.title ?? "",
    detail: raw?.detail ?? "",
    status: raw?.status ?? "pending",
    source: raw?.source ?? "",
    riskLevel: typeof raw?.payload?.risk_level === "string" ? raw.payload.risk_level : null,
  };
}

export function useApprovals(status = "pending") {
  return useQuery({
    queryKey: ["approvals", { status }],
    queryFn: () => api.approvals.list(status),
    select: (rows: any[]) => rows.map(mapApproval),
  });
}

export function useResolveApproval() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "approve" | "reject" }) =>
      decision === "approve" ? api.approvals.approve(id) : api.approvals.reject(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["approvals"] }),
  });
}

// ── Pending memories ──────────────────────────────────────────
export function usePendingMemoryCount() {
  return useQuery({
    queryKey: ["memories", "pending-count"],
    queryFn: () => api.memories.pendingCount().then((r) => r.data?.count ?? 0),
    refetchInterval: 60_000,
  });
}

export function useResolveMemory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: "approve" | "reject" }) =>
      action === "approve" ? api.memories.approve(id) : api.memories.reject(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["memories"] });
      qc.invalidateQueries({ queryKey: ["memory-search"] });
    },
  });
}

export function useUpdateMemory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, content, tags }: { id: string; content?: string; tags?: string[] }) =>
      api.memories.update(id, { content, tags }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["memories"] });
      qc.invalidateQueries({ queryKey: ["memory-search"] });
    },
  });
}

// ── Conversations (ask-your-memories chat) ────────────────────
export function useConversations() {
  return useQuery({
    queryKey: ["conversations"],
    queryFn: () => api.conversations.list(),
  });
}

export function useConversation(id: string | null) {
  return useQuery({
    queryKey: ["conversation", id],
    queryFn: () => api.conversations.get(id as string).then((r) => r.data),
    enabled: !!id,
  });
}

export function useSendMessage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, content }: { id: string; content: string }) =>
      api.conversations.ask(id, content).then((r) => r.data),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["conversation", vars.id] });
      qc.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
}

export function useDistillConversation() {
  return useMutation({
    mutationFn: (id: string) => api.conversations.distill(id),
  });
}

// ── Model health (LLM resilience) ─────────────────────────────
export type ModelHealthState = "up" | "cooling" | "down" | "unknown";

export interface ModelHealthVM {
  model: string;
  shortName: string;
  state: ModelHealthState;
  lastSuccessAt: number | null;
  lastFailureAt: number | null;
  lastError: string | null;
  avgLatencyMs: number | null;
  cooldownUntil: number | null;
}

const KNOWN_STATES: ModelHealthState[] = ["up", "cooling", "down", "unknown"];

// Loosely-typed shape of one row from GET /health/models — mirrors the
// backend contract without pulling `any` into this file (mapped to
// ModelHealthVM below, same pattern as mapMemory/mapTask).
interface RawModelHealth {
  model?: string;
  state?: string;
  last_success_at?: number | null;
  last_failure_at?: number | null;
  last_error?: string | null;
  avg_latency_ms?: number | null;
  cooldown_until?: number | null;
}

export function mapModelHealth(raw: RawModelHealth): ModelHealthVM {
  const model = String(raw?.model ?? "");
  const segments = model.split("/");
  const state = KNOWN_STATES.includes(raw?.state as ModelHealthState) ? (raw.state as ModelHealthState) : "unknown";
  return {
    model,
    shortName: segments[segments.length - 1] || model,
    state,
    lastSuccessAt: typeof raw?.last_success_at === "number" ? raw.last_success_at : null,
    lastFailureAt: typeof raw?.last_failure_at === "number" ? raw.last_failure_at : null,
    lastError: raw?.last_error ?? null,
    avgLatencyMs: typeof raw?.avg_latency_ms === "number" ? raw.avg_latency_ms : null,
    cooldownUntil: typeof raw?.cooldown_until === "number" ? raw.cooldown_until : null,
  };
}

export function useModelHealth() {
  return useQuery({
    queryKey: ["model-health"],
    queryFn: () => api.health.models().then((r) => r.data ?? []),
    refetchInterval: 30_000,
    select: (rows: RawModelHealth[]) => rows.map(mapModelHealth),
  });
}

// ── Ambient advisory roles (scout/admin/tutor) ─────────────────
// These personas run on a schedule and only report — never act without the
// user. This surface lets the user enable/disable each role, edit scout's
// watch-list topics, and see what they've recently found.
export const AMBIENT_AGENTS = ["scout", "admin", "tutor"] as const;
export type AmbientAgent = (typeof AMBIENT_AGENTS)[number];

function isAmbientAgent(name: unknown): name is AmbientAgent {
  return (AMBIENT_AGENTS as readonly string[]).includes(name as string);
}

export interface AmbientJobVM {
  id: string;
  name: string;
  agentName: string;
  description: string;
  cronExpression: string;
  isActive: boolean;
  topics: string[];
}

export function mapAmbientJob(raw: any): AmbientJobVM {
  const input = raw?.input && typeof raw.input === "object" ? raw.input : {};
  const topics = Array.isArray(input.topics) ? input.topics.filter((t: unknown) => typeof t === "string") : [];
  return {
    id: String(raw?.id ?? ""),
    name: raw?.name ?? "",
    agentName: raw?.agent_name ?? "",
    description: raw?.description ?? "",
    cronExpression: raw?.cron_expression ?? "",
    isActive: raw?.is_active !== false,
    topics,
  };
}

// Schedules are UTC-only on the backend; this renders the cron's hour/minute
// alongside the browser's local-time equivalent, for DISPLAY only — the
// underlying cron_expression sent to the API is never touched here.
export function describeCron(cron: string): string {
  const parts = cron.trim().split(/\s+/);
  if (parts.length < 5) return cron;
  const minute = Number(parts[0]);
  const hour = Number(parts[1]);
  if (!Number.isInteger(minute) || !Number.isInteger(hour) || hour < 0 || hour > 23 || minute < 0 || minute > 59) {
    return cron; // step/range/wildcard cron — not a single fixed time, show raw
  }
  const utcLabel = `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")} UTC`;
  const local = new Date();
  local.setUTCHours(hour, minute, 0, 0);
  const localLabel = local.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  return `Daily ${utcLabel} · ${localLabel} local`;
}

// `list()` returns data = {schedules, total} (a dict, not an array — see api.ts),
// so unwrap it here rather than via the generic listRequest() helper.
export function useAmbientSchedules() {
  return useQuery({
    queryKey: ["schedules"],
    queryFn: () => api.kernel.schedules.list().then((r: any) => r?.data?.schedules ?? []),
    select: (rows: any[]) => rows.filter((r) => isAmbientAgent(r?.agent_name)).map(mapAmbientJob),
  });
}

export function useUpdateAmbientSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api.kernel.schedules.update(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedules"] }),
  });
}

export interface AmbientFindingVM {
  id: string;
  title: string;
  body: string;
  priority: string;
  sourceType: string;
  createdAt: string;
}

export function mapAmbientFinding(raw: any): AmbientFindingVM {
  return {
    id: String(raw?.id ?? ""),
    title: raw?.title ?? "",
    body: raw?.body ?? "",
    priority: raw?.priority ?? "info",
    sourceType: raw?.source_type ?? "",
    createdAt: raw?.created_at ?? "",
  };
}

// Same query key shape as the desktop `useNotifications` hook (lib/hooks.ts)
// so a `notification` WebSocket event invalidates both surfaces at once.
export function useAmbientFindings() {
  return useQuery({
    queryKey: ["notifications", { limit: "20" }],
    queryFn: () => api.kernel.notifications({ limit: "20" }),
    select: (rows: any[]) => rows.filter((r) => isAmbientAgent(r?.source_type)).map(mapAmbientFinding),
    // Worker-created notifications (from ambient advisory jobs) don't publish to the
    // dashboard WebSocket relay, so poll to keep "Recent findings" from going stale.
    refetchInterval: 60_000,
  });
}

// ── Shadow mode (would-have-done grading queue) ────────────────────────
// A newly-graduating autonomous actor runs "in shadow": every action it would
// have taken is recorded, not executed, until the user has graded enough of
// them well. This surface lets the user watch the shadow log and one-tap
// grade good/bad — grading feeds trust and drives graduation off shadow mode.
export interface ShadowRunVM {
  id: string;
  agentId: string;
  actionType: string;
  command: string;
  riskLevel: string | null;
  projectId: string | null;
  wouldHaveRouted: string;
  grade: string | null;
  createdAt: string;
}

export function mapShadowRun(raw: any): ShadowRunVM {
  return {
    id: String(raw?.id ?? ""),
    agentId: raw?.agent_id ?? "",
    actionType: raw?.action_type ?? "",
    command: raw?.command ?? "",
    riskLevel: raw?.risk_level ?? null,
    projectId: raw?.project_id ?? null,
    wouldHaveRouted: raw?.would_have_routed ?? "",
    grade: raw?.grade ?? null,
    createdAt: raw?.created_at ?? "",
  };
}

// Shadow runs don't publish WebSocket events (the ops-ambient job runs on a
// schedule, like ambient findings), so poll to keep the grading queue fresh.
export function useShadowRuns(ungradedOnly = true) {
  return useQuery({
    queryKey: ["shadow-runs", { ungradedOnly }],
    queryFn: () => api.autonomy.shadowRuns(ungradedOnly),
    select: (rows: any[]) => rows.map(mapShadowRun),
    refetchInterval: 60_000,
  });
}

export function useGradeShadowRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, grade }: { id: string; grade: "good" | "bad" }) =>
      api.autonomy.gradeShadow(id, grade),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["shadow-runs"] }),
  });
}
