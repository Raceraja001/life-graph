import { describe, expect, it } from "vitest";
import { isLive, statusLabel } from "@/lib/memory-status";

// The memory list returns archived rows too; on 2026-10-26 Overview's "Recent
// Memories" showed an archived test memory as if it were live.

describe("memory status", () => {
  it("treats active and pending as in use", () => {
    expect(isLive("active")).toBe(true);
    expect(isLive("pending")).toBe(true);
    expect(isLive(undefined)).toBe(true);
    expect(isLive("archived")).toBe(false);
    expect(isLive("superseded")).toBe(false);
  });

  it("labels every status but active", () => {
    expect(statusLabel("active")).toBeNull();
    expect(statusLabel(null)).toBeNull();
    expect(statusLabel("archived")).toBe("archived");
    expect(statusLabel("retired")).toBe("retired");
  });
});
