"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

const POLL_INTERVAL = 10_000; // 10s polling for live data

// Memory hooks
export function useMemories(params?: { limit?: string; offset?: string }) {
  return useQuery({ queryKey: ["memories", params], queryFn: () => api.memories.list(params), refetchInterval: POLL_INTERVAL });
}
export function useMemory(id: string) {
  return useQuery({ queryKey: ["memories", id], queryFn: () => api.memories.get(id), enabled: !!id });
}
export function useMemorySearch(query: string) {
  return useQuery({ queryKey: ["memory-search", query], queryFn: () => api.memories.search(query), enabled: query.length > 2 });
}

// Judgment hooks
export function useDecisions(params?: { status?: string; limit?: string }) {
  return useQuery({ queryKey: ["decisions", params], queryFn: () => api.judgment.decisions.list(params), refetchInterval: POLL_INTERVAL });
}
export function useDecision(id: string) {
  return useQuery({ queryKey: ["decisions", id], queryFn: () => api.judgment.decisions.get(id), enabled: !!id });
}
export function useCreateDecision() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.judgment.decisions.create, onSuccess: () => qc.invalidateQueries({ queryKey: ["decisions"] }) });
}
export function usePredictions(params?: { outcome?: string; limit?: string }) {
  return useQuery({ queryKey: ["predictions", params], queryFn: () => api.judgment.predictions.list(params), refetchInterval: POLL_INTERVAL });
}
export function useCalibration() {
  return useQuery({ queryKey: ["calibration"], queryFn: () => api.judgment.calibration() });
}
export function useCalibrationCurve(domain?: string) {
  return useQuery({ queryKey: ["calibration-curve", domain], queryFn: () => api.judgment.curve(domain), refetchInterval: 30_000 });
}
export function useJudgmentStats() {
  return useQuery({ queryKey: ["judgment-stats"], queryFn: () => api.judgment.stats() });
}
export function useChallenge() {
  return useMutation({ mutationFn: (proposal: string) => api.judgment.challenge(proposal) });
}

// Capture hooks
export function useCapture() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.capture.ingest,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["captures"] });
      qc.invalidateQueries({ queryKey: ["memories"] });
    },
  });
}
export function useCaptures(params?: { surface?: string; limit?: string }) {
  return useQuery({ queryKey: ["captures", params], queryFn: () => api.capture.list(params), refetchInterval: 5_000 });
}

// Kernel hooks
export function useTasks(params?: { status?: string; limit?: string }) {
  return useQuery({ queryKey: ["tasks", params], queryFn: () => api.kernel.tasks.list(params), refetchInterval: POLL_INTERVAL });
}
export function useDrivers() {
  return useQuery({ queryKey: ["drivers"], queryFn: () => api.kernel.drivers.list() });
}
export function useDriverStats(window?: string) {
  return useQuery({ queryKey: ["driver-stats", window], queryFn: () => api.kernel.drivers.stats(window), refetchInterval: 30_000 });
}
export function useRoute() {
  return useMutation({ mutationFn: (message: string) => api.kernel.route(message) });
}
