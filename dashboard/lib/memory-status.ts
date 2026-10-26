// A memory's status as the pages show it. GET /memories/ without a status
// returns every status but rejected (api/memories.py list_memories), so a list
// must say which rows are no longer in use rather than show them as live.

/** Still in use: what recall reads (active) or what waits for review (pending). */
export function isLive(status: unknown): boolean {
  return status === "active" || status === "pending" || status == null;
}

/** The status cell's label, or null for an ordinary active memory. */
export function statusLabel(status: unknown): string | null {
  if (status == null || status === "active") return null;
  return String(status);
}
