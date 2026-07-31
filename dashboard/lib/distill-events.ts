// Module-level pub/sub bridging the conversation:distilled WebSocket event to
// the chat surface, so it can show an honest "→ N new facts" toast when the
// background distill job finishes. Keeps useWebSocket otherwise invalidation-only.

export interface DistillDetail {
  conversationId: string;
  newFacts: number;
}

const listeners = new Set<(d: DistillDetail) => void>();

export function emitDistillComplete(detail: DistillDetail): void {
  listeners.forEach((fn) => fn(detail));
}

/** Subscribe to distill-completion events. Returns an unsubscribe function. */
export function onDistillComplete(cb: (d: DistillDetail) => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}
