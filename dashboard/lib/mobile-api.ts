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
  };
}

// Kernel task status → mobile tone + board group + display label.
const STATUS_MAP: Record<string, { tone: Tone; group: TaskGroup; label: string }> = {
  queued: { tone: "neutral", group: "queued", label: "queued" },
  running: { tone: "info", group: "inflight", label: "running" },
  verifying: { tone: "warning", group: "inflight", label: "verifying" },
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
}

export function mapApproval(raw: any): ApprovalVM {
  return {
    id: String(raw?.id ?? ""),
    kind: raw?.kind ?? "",
    title: raw?.title ?? "",
    detail: raw?.detail ?? "",
    status: raw?.status ?? "pending",
    source: raw?.source ?? "",
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
