import { describe, expect, it, vi } from "vitest";
import { emitCaptureComplete, onCaptureComplete } from "@/lib/capture-events";
import { emitDistillComplete, onDistillComplete } from "@/lib/distill-events";

// Both modules are module-level pub/sub with a shared Set. The subscription
// contract is what matters: an unsubscribe that does not actually detach
// leaks a listener into every later test *and* every later page view.

describe("capture-events", () => {
  it("delivers to a subscriber", () => {
    const cb = vi.fn();
    const off = onCaptureComplete(cb);

    emitCaptureComplete({ source: "voice", memoriesCreated: 3 });

    expect(cb).toHaveBeenCalledWith({ source: "voice", memoriesCreated: 3 });
    off();
  });

  it("delivers to every subscriber", () => {
    const a = vi.fn();
    const b = vi.fn();
    const offA = onCaptureComplete(a);
    const offB = onCaptureComplete(b);

    emitCaptureComplete({ source: "image", memoriesCreated: 1 });

    expect(a).toHaveBeenCalledOnce();
    expect(b).toHaveBeenCalledOnce();
    offA();
    offB();
  });

  it("stops delivering after unsubscribe", () => {
    const cb = vi.fn();
    onCaptureComplete(cb)();

    emitCaptureComplete({ source: "document", memoriesCreated: 9 });

    expect(cb).not.toHaveBeenCalled();
  });

  it("unsubscribing twice is harmless", () => {
    const cb = vi.fn();
    const off = onCaptureComplete(cb);
    off();
    off();
    emitCaptureComplete({ source: "voice", memoriesCreated: 1 });
    expect(cb).not.toHaveBeenCalled();
  });

  it("emitting with no subscribers does not throw", () => {
    expect(() => emitCaptureComplete({ source: "voice", memoriesCreated: 0 })).not.toThrow();
  });

  it("one subscriber unsubscribing does not detach the others", () => {
    const a = vi.fn();
    const b = vi.fn();
    const offA = onCaptureComplete(a);
    const offB = onCaptureComplete(b);

    offA();
    emitCaptureComplete({ source: "voice", memoriesCreated: 2 });

    expect(a).not.toHaveBeenCalled();
    expect(b).toHaveBeenCalledOnce();
    offB();
  });
});

describe("distill-events", () => {
  it("delivers the conversation id and fact count", () => {
    const cb = vi.fn();
    const off = onDistillComplete(cb);

    emitDistillComplete({ conversationId: "c-1", newFacts: 4 });

    expect(cb).toHaveBeenCalledWith({ conversationId: "c-1", newFacts: 4 });
    off();
  });

  it("stops delivering after unsubscribe", () => {
    const cb = vi.fn();
    onDistillComplete(cb)();
    emitDistillComplete({ conversationId: "c-2", newFacts: 1 });
    expect(cb).not.toHaveBeenCalled();
  });

  it("is a separate channel from capture-events", () => {
    const capture = vi.fn();
    const off = onCaptureComplete(capture);

    emitDistillComplete({ conversationId: "c-3", newFacts: 1 });

    expect(capture).not.toHaveBeenCalled();
    off();
  });
});
