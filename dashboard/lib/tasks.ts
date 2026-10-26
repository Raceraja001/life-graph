// Kernel tasks (GET /kernel/tasks rows: id, task_name, agent_name, status, ...)
// as the desktop board and the mobile list show them. One place, so the two
// surfaces cannot disagree on a task's name or where it belongs.

/* eslint-disable @typescript-eslint/no-explicit-any -- rows are the API's loosely-typed payloads. */

export type BoardColumn = "queued" | "running" | "verifying" | "landed" | "failed";

const COLUMN_OF: Record<string, BoardColumn> = {
  queued: "queued",
  running: "running",
  verifying: "verifying",
  completed: "landed",
  landed: "landed",
  done: "landed",
  failed: "failed",
  error: "failed",
  timeout: "failed",
};

/** The board column for a status; null for one the board does not show (cancelled). */
export function boardColumn(status: unknown): BoardColumn | null {
  const s = String(status ?? "queued").toLowerCase();
  if (s === "cancelled") return null;
  return COLUMN_OF[s] ?? "running";
}

/** A chat reply's own run ("chat:jarvis"): real work for the kernel, noise on a task board. */
export function isChatRun(t: any): boolean {
  return typeof t?.task_name === "string" && t.task_name.startsWith("chat:");
}

/** What the task is: the API sends task_name; older payloads used description/intent/title. */
export function taskTitle(t: any): string {
  return t?.description || t?.intent || t?.title || t?.task_name || String(t?.id ?? "task");
}

/** Who runs it: persona when sent, else the agent's name. */
export function taskAgent(t: any): string {
  return t?.persona || t?.agent_name || "system";
}

/** A count from one page of a list: "50+" when the API says there is more. */
export function countLabel(shown: number, hasMore: boolean): string {
  return hasMore ? `${shown}+` : String(shown);
}
