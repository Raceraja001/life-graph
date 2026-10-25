import { describe, expect, it } from "vitest";
import {
  autoMergeState,
  brief,
  duration,
  pct,
  stepFailed,
  toEntries,
  usd,
  type RunStep,
} from "@/lib/observe";

const step = (kind: string, over: Partial<RunStep> = {}): RunStep => ({
  attempt: 1,
  seq: 0,
  driver: "local",
  kind,
  content: "",
  properties: {},
  ...over,
});

describe("toEntries pairs tool calls with their results", () => {
  it("matches by ref when the driver sets one", () => {
    const entries = toEntries([
      step("tool_call", { tool: "code_read", content: '{"path":"a.py"}', properties: { ref: "r1" } }),
      step("tool_call", { tool: "code_read", content: '{"path":"b.py"}', properties: { ref: "r2" } }),
      step("tool_result", { content: "B", properties: { ref: "r2" } }),
      step("tool_result", { content: "A", properties: { ref: "r1" } }),
    ]);
    expect(entries).toHaveLength(2);
    expect(entries[0]).toMatchObject({ type: "tool", result: { content: "A" } });
    expect(entries[1]).toMatchObject({ type: "tool", result: { content: "B" } });
  });

  it("falls back to the last open call when there is no ref", () => {
    const entries = toEntries([
      step("tool_call", { tool: "run_tests", content: "{}" }),
      step("tool_result", { content: "ok" }),
      step("text", { content: "done" }),
    ]);
    expect(entries.map((e) => e.type)).toEqual(["tool", "say"]);
    expect(entries[0]).toMatchObject({ result: { content: "ok" } });
  });

  it("keeps an orphan result and classifies thinking and errors", () => {
    const entries = toEntries([
      step("tool_result", { content: "late" }),
      step("thinking", { content: "hmm" }),
      step("error", { content: "boom" }),
    ]);
    expect(entries.map((e) => e.type)).toEqual(["tool", "think", "error"]);
  });
});

describe("stepFailed", () => {
  it("reads the is_error flag or an error JSON body", () => {
    expect(stepFailed(step("tool_result", { properties: { is_error: true } }))).toBe(true);
    expect(stepFailed(step("tool_result", { content: ' {"error": "no such file"}' }))).toBe(true);
    expect(stepFailed(step("tool_result", { content: "fine" }))).toBe(false);
    expect(stepFailed(undefined)).toBe(false);
  });
});

describe("formatters", () => {
  it("brief shows the first argument, clipped", () => {
    expect(brief('{"path":"life_graph/x.py","start":1}')).toBe("life_graph/x.py");
    expect(brief('{"n": 3}')).toBe("3");
    expect(brief("x".repeat(100))).toBe("x".repeat(90));
    expect(brief(undefined)).toBe("");
  });

  it("usd keeps four decimals for sub-cent amounts", () => {
    expect(usd(0.0042)).toBe("$0.0042");
    expect(usd(1.5)).toBe("$1.50");
    expect(usd(null)).toBe("—");
  });

  it("pct and duration", () => {
    expect(pct(0.756)).toBe("76%");
    expect(pct(undefined)).toBe("—");
    expect(duration(42_000)).toBe("42s");
    expect(duration(125_000)).toBe("2m 5s");
    expect(duration(2 * 3_600_000 + 60_000)).toBe("2h 1m");
    expect(duration(0)).toBe("—");
  });
});

describe("autoMergeState needs both the opt-in and the earned bar", () => {
  const base = {
    persona: "p",
    driver: "local",
    project_name: "x",
    merged: 4,
    failed: 1,
    total: 5,
    merge_rate: 0.8,
    established: true,
    threshold: 0.8,
  };
  it.each([
    [true, true, "active"],
    [true, false, "opted in — bar not met"],
    [false, true, "bar met — project not opted in"],
    [false, false, "off"],
  ])("auto_merge=%s earning=%s → %s", (autoMerge, earning, label) => {
    expect(autoMergeState({ ...base, auto_merge: autoMerge, earning_auto_merge: earning }).label).toBe(label);
  });
});
