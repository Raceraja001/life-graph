import { describe, expect, it } from "vitest";
import { MODEL_OPTIONS } from "@/lib/model-options";

// The picker is grouped by cost so a cost-conscious choice is visible at a
// glance. A model landing in the wrong group is a silent way to spend money.

describe("MODEL_OPTIONS", () => {
  it("has both groups populated", () => {
    expect(MODEL_OPTIONS.Free.length).toBeGreaterThan(0);
    expect(MODEL_OPTIONS.Paid.length).toBeGreaterThan(0);
  });

  it("every Free entry is actually flagged :free", () => {
    for (const model of MODEL_OPTIONS.Free) {
      expect(model, `${model} is in Free but not marked :free`).toMatch(/:free$/);
    }
  });

  it("no Paid entry is marked :free", () => {
    for (const model of MODEL_OPTIONS.Paid) {
      expect(model, `${model} is in Paid but marked :free`).not.toMatch(/:free$/);
    }
  });

  it("contains no duplicates within or across groups", () => {
    const all = [...MODEL_OPTIONS.Free, ...MODEL_OPTIONS.Paid];
    expect(new Set(all).size).toBe(all.length);
  });

  it("has no blank or untrimmed entries", () => {
    for (const model of [...MODEL_OPTIONS.Free, ...MODEL_OPTIONS.Paid]) {
      expect(model).toBe(model.trim());
      expect(model.length).toBeGreaterThan(0);
    }
  });
});
