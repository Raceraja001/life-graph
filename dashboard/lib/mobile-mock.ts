// Mock data for the mobile app, mirroring the Claude Design prototype
// (Life Graph Mobile.dc.html). Phase 3 replaces these with live API hooks.

export type Tone = "danger" | "info" | "warning" | "success" | "neutral";

export interface MemoryMock {
  id: string;
  content: string;
  imp: number; // 0..1 importance
  tags: string[];
  meta: string; // "source · date", e.g. "chat · Jul 10"
}

export interface TaskMock {
  id: string;
  title: string;
  meta: string;
  status: string; // display label: urgent | running | verifying | queued | done
  tone: Tone;
  group: "inflight" | "queued" | "done";
}

export interface ApprovalMock {
  id: string;
  title: string;
  detail: string;
}

export const MEMS: MemoryMock[] = [
  { id: "m1", content: "Deploy window: never push to prod on Fridays after 2pm", imp: 0.91, tags: ["rule", "ops"], meta: "chat · Jul 10" },
  { id: "m2", content: "Chose Postgres + pgvector over Pinecone to keep the stack self-hosted", imp: 0.88, tags: ["decision"], meta: "capture · Jul 9" },
  { id: "m3", content: "The embeddings worker OOMs above 8 concurrent jobs — cap at 6", imp: 0.85, tags: ["incident"], meta: "watcher · Jul 8" },
  { id: "m4", content: "Prefers FastAPI over Flask for all new services — async-first, typed", imp: 0.82, tags: ["preference"], meta: "extraction · Jul 7" },
  { id: "m5", content: "Gets deep work done 6–9am; avoid scheduling calls before 10", imp: 0.79, tags: ["pattern"], meta: "extraction · Jul 5" },
  { id: "m6", content: "Rent renewal due Aug 31 — landlord prefers WhatsApp", imp: 0.66, tags: ["admin"], meta: "capture · Jun 30" },
];

export const TASKS: TaskMock[] = [
  { id: "t1", title: "Relink WhatsApp watcher (auth expired)", meta: "watchers · blocking capture", status: "urgent", tone: "danger", group: "inflight" },
  { id: "t2", title: "Backfill embeddings for 2,400 legacy memories", meta: "engineer · 64% done", status: "running", tone: "info", group: "inflight" },
  { id: "t3", title: "Draft weekly review from watcher events", meta: "scribe · needs your approval", status: "verifying", tone: "warning", group: "inflight" },
  { id: "t4", title: "Follow up on rent renewal", meta: "intention · due mid-Aug", status: "queued", tone: "neutral", group: "queued" },
  { id: "t5", title: "Benchmark Apache AGE vs join tables", meta: "engineer · queued behind backfill", status: "queued", tone: "neutral", group: "queued" },
  { id: "t6", title: "Nightly sleep cycle — 112 memories archived", meta: "curator · 03:58 today", status: "done", tone: "success", group: "done" },
  { id: "t7", title: "recall@10 eval sweep (+0.04)", meta: "optimizer · 03:40 today", status: "done", tone: "success", group: "done" },
];

export const APPROVALS: ApprovalMock[] = [
  { id: "ap1", title: "Merge 41 near-duplicate memories", detail: "curator · pairs ≥ 0.94 similarity · reversible for 30 days" },
  { id: "ap2", title: "Resolve contradiction: coffee preference", detail: '"likes filter coffee" (Jul 3) vs "switched to green tea" (May 12)' },
  { id: "ap3", title: "Promote synthesizer v6 to active", detail: "optimizer · +3.1% vs v5 across 48 judged cases · instant rollback" },
  { id: "ap4", title: "Send weekly review draft", detail: "scribe · goes to your inbox only" },
];

// Semantic tone → [soft-bg token, fg token]
export const TONE: Record<Tone, [string, string]> = {
  danger: ["var(--danger-soft)", "var(--danger)"],
  info: ["var(--info-soft)", "var(--info)"],
  warning: ["var(--warning-soft)", "var(--warning)"],
  success: ["var(--success-soft)", "var(--success)"],
  neutral: ["var(--surface-3)", "var(--text-muted)"],
};

export const impLabel = (imp: number) => `${Math.round(imp * 100)}%`;
