"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

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

// ── Stubs for unbuilt features ──────────────────
export function usePredictions(_params?: any) {
  return useQuery({ queryKey: ["predictions-stub"], queryFn: async () => [], enabled: false });
}
export function useCalibration() {
  return useQuery({ queryKey: ["calibration-stub"], queryFn: async () => ({}), enabled: false });
}
export function useCalibrationCurve(_domain?: string) {
  return useQuery({ queryKey: ["calibration-curve-stub"], queryFn: async () => ({}), enabled: false });
}
export function useJudgmentStats() {
  return useQuery({ queryKey: ["judgment-stats-stub"], queryFn: async () => ({}), enabled: false });
}
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
