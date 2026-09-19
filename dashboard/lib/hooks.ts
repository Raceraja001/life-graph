"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type NewPrediction, type PredictionOutcome } from "./api";

// No polling — WebSocket handles real-time updates via cache invalidation

// ── Memory hooks ──────────────────────────────
export function useMemories(params?: { limit?: string; offset?: string }) {
  return useQuery({ queryKey: ["memories", params], queryFn: () => api.memories.list(params) });
}
export function useMemory(id: string) {
  return useQuery({ queryKey: ["memories", id], queryFn: () => api.memories.get(id), enabled: !!id });
}
export function useMemorySearch(query: string) {
  return useQuery({ queryKey: ["memory-search", query], queryFn: () => api.memories.search(query), enabled: query.length > 2 });
}

// ── Preferences ──────────────────────────────
export function usePreferences(params?: { limit?: string }) {
  return useQuery({ queryKey: ["preferences", params], queryFn: () => api.preferences.list(params) });
}
export const useDecisions = usePreferences;

// ── Identity / Beliefs ──────────────────────
export function useBeliefs() {
  return useQuery({ queryKey: ["beliefs"], queryFn: () => api.identity.beliefs() });
}
export function useChallenge() {
  return useMutation({ mutationFn: (belief: string) => api.identity.challenge(belief) });
}

// ── Evidence ──────────────────────────────
export function useEvidence(params?: { limit?: string }) {
  return useQuery({ queryKey: ["evidence", params], queryFn: () => api.evidence.list(params) });
}

// ── Kernel hooks ──────────────────────────────
export function useTasks(params?: { status?: string; limit?: string }) {
  return useQuery({ queryKey: ["tasks", params], queryFn: () => api.kernel.tasks.list(params) });
}
export function useRoute() {
  return useMutation({ mutationFn: (message: string) => api.kernel.route(message) });
}
export function useCreateMemory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (content: string) => api.memories.create(content),
    onMutate: async (content: string) => {
      // Instant optimistic card: prepend to every cached memories list.
      await qc.cancelQueries({ queryKey: ["memories"] });
      const snapshots = qc.getQueriesData<unknown>({ queryKey: ["memories"] });
      const optimistic = {
        id: "optimistic-" + Date.now(),
        content,
        tags: [],
        status: "pending",
        importance: 0.5,
        source: "capture",
        created_at: new Date().toISOString(),
        _optimistic: true,
      };
      // Only touch list caches (arrays); leave single-memory objects and
      // the pending-count number untouched.
      qc.setQueriesData<unknown>({ queryKey: ["memories"] }, (old: unknown) =>
        Array.isArray(old) ? [optimistic, ...old] : old
      );
      return { snapshots };
    },
    onError: (_err, _content, ctx) => {
      // Roll every list back to its pre-mutation snapshot.
      ctx?.snapshots?.forEach(([key, data]: [readonly unknown[], unknown]) =>
        qc.setQueryData(key, data)
      );
    },
    onSettled: () => {
      // Belt-and-suspenders: strip any lingering optimistic ghost from every
      // list cache (covers inactive lists that refetchOnMount:false won't refetch,
      // and the un-guarded desktop memories page), then refetch server truth.
      qc.setQueriesData<unknown>({ queryKey: ["memories"] }, (old: unknown) =>
        Array.isArray(old) ? old.filter((m) => !(m as { _optimistic?: boolean })?._optimistic) : old
      );
      qc.invalidateQueries({ queryKey: ["memories"], refetchType: "all" });
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
  });
}
export function useNotifications(params?: { limit?: string }) {
  return useQuery({ queryKey: ["notifications", params], queryFn: () => api.kernel.notifications(params) });
}

// ── Agent Tasks ──────────────────────────────
export function useAgentTasks(params?: { limit?: string }) {
  return useQuery({ queryKey: ["agent-tasks", params], queryFn: () => api.agentTasks.list(params) });
}

// ── Watchers ──────────────────────────────
export function useWatcherEvents(params?: { limit?: string }) {
  return useQuery({ queryKey: ["watcher-events", params], queryFn: () => api.watchers.events(params) });
}
export function useWatcherSummary() {
  return useQuery({ queryKey: ["watcher-summary"], queryFn: () => api.watchers.summary() });
}

// ── Capture (uses advisor.ask) ──────────────────
export function useCapture() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { surface: string; content: string }) =>
      api.advisor.ask(data.content),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["memories"] });
    },
  });
}

// ── Procedures ──────────────────────────────
export function useProcedures() {
  return useQuery({ queryKey: ["procedures"], queryFn: () => api.procedures.list() });
}

// ── Judgment: predictions + calibration ──────────
export function usePredictions(status: "suggested" | "pending" | "resolved") {
  return useQuery({
    queryKey: ["predictions", status],
    queryFn: async () => {
      if (status !== "resolved") return api.judgment.predictions({ status, limit: "200" });
      // "Resolved" spans three outcomes; the API filters one at a time.
      const lists = await Promise.all(
        (["correct", "incorrect", "ambiguous"] as const).map((s) =>
          api.judgment.predictions({ status: s, limit: "30" })
        )
      );
      return lists
        .flat()
        .sort((a, b) => (b.resolved_at ?? "").localeCompare(a.resolved_at ?? ""))
        .slice(0, 30);
    },
  });
}
export function useCalibration(domain?: string) {
  return useQuery({ queryKey: ["calibration", domain], queryFn: () => api.judgment.calibration(domain) });
}

/** Any prediction change can move every list and the curve, so refresh all of them. */
function usePredictionMutation<A>(fn: (args: A) => Promise<unknown>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["predictions"] });
      qc.invalidateQueries({ queryKey: ["calibration"] });
    },
  });
}
export function useCreatePrediction() {
  return usePredictionMutation((body: NewPrediction) => api.judgment.createPrediction(body));
}
export function useResolvePrediction() {
  return usePredictionMutation(({ id, outcome }: { id: string; outcome: PredictionOutcome }) =>
    api.judgment.resolve(id, outcome)
  );
}
export function useAcceptPrediction() {
  return usePredictionMutation(({ id, body }: { id: string; body?: Partial<NewPrediction> }) =>
    api.judgment.accept(id, body)
  );
}
export function useDismissPrediction() {
  return usePredictionMutation((id: string) => api.judgment.dismiss(id));
}

// ── Stubs for unbuilt features ──────────────────
export function useCaptures(_params?: any) {
  return useWatcherEvents(_params);
}
export function useDrivers() {
  return useQuery({ queryKey: ["drivers-stub"], queryFn: async () => [], enabled: false });
}
export function useDriverStats(_window?: string) {
  return useQuery({ queryKey: ["driver-stats-stub"], queryFn: async () => ({}), enabled: false });
}
export function useCreateDecision() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: async (_data: any) => ({}), onSuccess: () => qc.invalidateQueries({ queryKey: ["preferences"] }) });
}
export function useDecision(_id: string) {
  return useQuery({ queryKey: ["decision-stub"], queryFn: async () => null, enabled: false });
}

// ── Dev tasks ──────────────────────────────
// Polls only while something is queued/running or awaiting a decision: those
// changes happen in the background (agent run) or on another page (approvals),
// and nothing pushes them over the WebSocket.
const ACTIVE_STAGES = new Set(["queued", "running", "awaiting_pr", "awaiting_merge"]);
export function useDevTasks() {
  return useQuery({
    queryKey: ["dev-tasks"],
    queryFn: () => api.devTasks.list(),
    refetchInterval: (query) =>
      ((query.state.data as any[]) ?? []).some((t) => ACTIVE_STAGES.has(t.stage)) ? 4000 : false,
  });
}
export function useCreateDevTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.devTasks.create,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dev-tasks"] }),
  });
}
export function useProjects() {
  return useQuery({ queryKey: ["projects"], queryFn: () => api.kernel.projects() });
}
export function useDriverPersonas() {
  return useQuery({
    queryKey: ["personas", "with-driver"],
    queryFn: () =>
      api.kernel.personas
        .list()
        .then((r: any) => ((r?.data?.personas ?? []) as any[]).filter((p) => p.driver && p.is_active !== false)),
  });
}
