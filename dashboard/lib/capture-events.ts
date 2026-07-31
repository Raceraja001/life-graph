// Tiny module-level pub/sub bridging WebSocket capture-completion events
// (voice:transcribed / image:processed / document:imported) to the capture
// surface, so it can show an honest "→ N memories" toast when the ARQ job
// finishes. Kept separate so useWebSocket stays otherwise invalidation-only.

export type CaptureSource = "voice" | "image" | "document";
export interface CaptureDetail {
  source: CaptureSource;
  memoriesCreated: number;
}

const listeners = new Set<(d: CaptureDetail) => void>();

export function emitCaptureComplete(detail: CaptureDetail): void {
  listeners.forEach((fn) => fn(detail));
}

/** Subscribe to capture-completion events. Returns an unsubscribe function. */
export function onCaptureComplete(cb: (d: CaptureDetail) => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}
