import { describe, expect, it } from "vitest";
import {
  describeCron,
  mapAmbientJob,
  mapApproval,
  mapMemory,
  mapModelHealth,
  mapTask,
  TASK_GROUPS,
} from "@/lib/mobile-api";

// These mappers are the boundary between loosely-typed backend payloads and
// the mobile screens. Their whole job is to be defensive, so the cases worth
// pinning are the malformed ones: null, missing keys, wrong types. A mapper
// that throws takes the entire screen down with it.

describe("mapMemory", () => {
  it("maps a well-formed row", () => {
    const vm = mapMemory({
      id: "m-1",
      content: "hello",
      importance: 0.9,
      tags: ["a", "b"],
      source: "capture",
      created_at: "2026-07-10T12:00:00Z",
      status: "active",
    });

    expect(vm.id).toBe("m-1");
    expect(vm.content).toBe("hello");
    expect(vm.imp).toBe(0.9);
    expect(vm.tags).toEqual(["a", "b"]);
    expect(vm.created).toBeTruthy();
    expect(vm.meta).toBe(`capture · ${vm.created}`);
  });

  it("survives null", () => {
    const vm = mapMemory(null);
    expect(vm.id).toBe("");
    expect(vm.content).toBe("");
    expect(vm.status).toBe("active");
  });

  it("survives an empty object", () => {
    expect(() => mapMemory({})).not.toThrow();
  });

  it("defaults importance to 0.5 when absent or non-numeric", () => {
    expect(mapMemory({}).imp).toBe(0.5);
    expect(mapMemory({ importance: "high" }).imp).toBe(0.5);
    expect(mapMemory({ importance: null }).imp).toBe(0.5);
  });

  it("keeps importance 0 rather than falling back to 0.5", () => {
    expect(mapMemory({ importance: 0 }).imp).toBe(0);
  });

  it("coerces non-array tags to an empty array", () => {
    expect(mapMemory({ tags: "not-an-array" }).tags).toEqual([]);
    expect(mapMemory({ tags: null }).tags).toEqual([]);
  });

  it("falls back to source-only meta when the date is unparseable", () => {
    const vm = mapMemory({ source: "voice", created_at: "not a date" });
    expect(vm.created).toBe("");
    expect(vm.meta).toBe("voice");
  });

  it("defaults source to 'capture'", () => {
    expect(mapMemory({}).source).toBe("capture");
  });

  it("flags optimistic cards only on an exact true", () => {
    expect(mapMemory({ _optimistic: true })._optimistic).toBe(true);
    expect(mapMemory({ _optimistic: "yes" })._optimistic).toBe(false);
    expect(mapMemory({})._optimistic).toBe(false);
  });

  it("stringifies a numeric id", () => {
    expect(mapMemory({ id: 42 }).id).toBe("42");
  });
});

describe("mapTask", () => {
  it.each([
    ["queued", "queued", "neutral"],
    ["running", "inflight", "info"],
    ["verifying", "inflight", "warning"],
    ["completed", "done", "success"],
    ["landed", "done", "success"],
    ["done", "done", "success"],
    ["cancelled", "done", "neutral"],
  ])("maps %s to the %s group", (status, group, tone) => {
    const vm = mapTask({ id: "t", status });
    expect(vm.group).toBe(group);
    expect(vm.tone).toBe(tone);
  });

  it.each(["failed", "error"])("keeps %s in flight so it stays visible", (status) => {
    const vm = mapTask({ id: "t", status });
    expect(vm.group).toBe("inflight");
    expect(vm.tone).toBe("danger");
    expect(vm.status).toBe("failed");
  });

  it("is case-insensitive on status", () => {
    expect(mapTask({ status: "RUNNING" }).group).toBe("inflight");
  });

  it("shows an unknown status verbatim rather than hiding the task", () => {
    const vm = mapTask({ id: "t", status: "reticulating" });
    expect(vm.status).toBe("reticulating");
    expect(vm.group).toBe("inflight");
  });

  it("defaults a missing status to queued", () => {
    expect(mapTask({ id: "t" }).group).toBe("queued");
  });

  it("prefers description, then intent, then title, then id for the label", () => {
    expect(mapTask({ id: "x", description: "d", intent: "i", title: "t" }).title).toBe("d");
    expect(mapTask({ id: "x", intent: "i", title: "t" }).title).toBe("i");
    expect(mapTask({ id: "x", title: "t" }).title).toBe("t");
    expect(mapTask({ id: "x" }).title).toBe("x");
  });

  it("falls back to 'task' with no id at all", () => {
    expect(mapTask({}).title).toBe("task");
  });

  it("defaults the persona to 'system'", () => {
    expect(mapTask({}).meta).toBe("system");
  });

  it("survives null", () => {
    expect(() => mapTask(null)).not.toThrow();
  });

  it("every mapped group has a board column", () => {
    const columns = new Set(TASK_GROUPS.map((g) => g.id));
    for (const status of ["queued", "running", "completed", "failed", "weird"]) {
      expect(columns.has(mapTask({ status }).group)).toBe(true);
    }
  });
});

describe("mapApproval", () => {
  it("lifts risk_level, kind and instruction out of payload", () => {
    const vm = mapApproval({
      id: "a-1",
      kind: "auto_action",
      title: "Run migration",
      payload: { risk_level: "high", kind: "command", instruction: "do the thing" },
    });

    expect(vm.riskLevel).toBe("high");
    expect(vm.actionKind).toBe("command");
    expect(vm.instruction).toBe("do the thing");
  });

  it("nulls the payload fields for pre-B2 rows that lack them", () => {
    const vm = mapApproval({ id: "a-2", payload: {} });
    expect(vm.riskLevel).toBeNull();
    expect(vm.actionKind).toBeNull();
    expect(vm.instruction).toBeNull();
  });

  it("survives a missing payload entirely", () => {
    expect(() => mapApproval({ id: "a-3" })).not.toThrow();
    expect(mapApproval({ id: "a-3" }).riskLevel).toBeNull();
  });

  it("rejects non-string payload values rather than passing them through", () => {
    const vm = mapApproval({ payload: { risk_level: 3, kind: [], instruction: {} } });
    expect(vm.riskLevel).toBeNull();
    expect(vm.actionKind).toBeNull();
    expect(vm.instruction).toBeNull();
  });

  it("defaults status to pending", () => {
    expect(mapApproval({}).status).toBe("pending");
  });
});

describe("mapModelHealth", () => {
  it.each(["up", "cooling", "down", "unknown"])("accepts the known state %s", (state) => {
    expect(mapModelHealth({ model: "m", state }).state).toBe(state);
  });

  it("maps an unrecognised state to 'unknown' rather than rendering it raw", () => {
    expect(mapModelHealth({ model: "m", state: "on fire" }).state).toBe("unknown");
    expect(mapModelHealth({ model: "m" }).state).toBe("unknown");
  });

  it("shortens a slash-separated model id to its last segment", () => {
    expect(mapModelHealth({ model: "openrouter/google/gemma-4-31b-it:free" }).shortName).toBe(
      "gemma-4-31b-it:free",
    );
  });

  it("leaves an unslashed model id alone", () => {
    expect(mapModelHealth({ model: "claude-cli" }).shortName).toBe("claude-cli");
  });

  it("falls back to the full model id when the last segment is empty", () => {
    expect(mapModelHealth({ model: "trailing/" }).shortName).toBe("trailing/");
  });

  it("nulls non-numeric timestamps and latencies", () => {
    const vm = mapModelHealth({
      model: "m",
      last_success_at: "recently" as unknown as number,
      avg_latency_ms: null,
    });
    expect(vm.lastSuccessAt).toBeNull();
    expect(vm.avgLatencyMs).toBeNull();
  });

  it("keeps a zero latency rather than nulling it", () => {
    expect(mapModelHealth({ model: "m", avg_latency_ms: 0 }).avgLatencyMs).toBe(0);
  });
});

describe("mapAmbientJob", () => {
  it("maps a well-formed schedule", () => {
    const vm = mapAmbientJob({
      id: "s-1",
      name: "Tech radar",
      agent_name: "researcher",
      cron_expression: "0 6 * * *",
      is_active: true,
      input: { topics: ["rust", "postgres"] },
    });

    expect(vm.agentName).toBe("researcher");
    expect(vm.topics).toEqual(["rust", "postgres"]);
    expect(vm.isActive).toBe(true);
  });

  it("treats a missing is_active as active", () => {
    expect(mapAmbientJob({}).isActive).toBe(true);
    expect(mapAmbientJob({ is_active: false }).isActive).toBe(false);
  });

  it("drops non-string topics", () => {
    expect(mapAmbientJob({ input: { topics: ["ok", 3, null, "fine"] } }).topics).toEqual([
      "ok",
      "fine",
    ]);
  });

  it("survives a non-object input", () => {
    expect(mapAmbientJob({ input: "nope" }).topics).toEqual([]);
    expect(mapAmbientJob({ input: null }).topics).toEqual([]);
  });

  it("survives null", () => {
    expect(() => mapAmbientJob(null)).not.toThrow();
  });
});

describe("describeCron", () => {
  it("renders a fixed daily time with both UTC and local", () => {
    const out = describeCron("30 6 * * *");
    expect(out).toContain("06:30 UTC");
    expect(out).toContain("local");
    expect(out.startsWith("Daily ")).toBe(true);
  });

  it("zero-pads the UTC label", () => {
    expect(describeCron("5 3 * * *")).toContain("03:05 UTC");
  });

  it("shows midnight as 00:00", () => {
    expect(describeCron("0 0 * * *")).toContain("00:00 UTC");
  });

  it.each([
    ["*/15 * * * *", "step minutes"],
    ["0 */4 * * *", "step hours"],
    ["0 9-17 * * *", "an hour range"],
    ["* * * * *", "every minute"],
  ])("shows %s raw (%s is not a single fixed time)", (cron) => {
    expect(describeCron(cron)).toBe(cron);
  });

  it("shows a too-short expression raw", () => {
    expect(describeCron("0 6")).toBe("0 6");
    expect(describeCron("")).toBe("");
  });

  it("rejects out-of-range values rather than rendering nonsense", () => {
    expect(describeCron("0 24 * * *")).toBe("0 24 * * *");
    expect(describeCron("60 6 * * *")).toBe("60 6 * * *");
    expect(describeCron("-1 6 * * *")).toBe("-1 6 * * *");
  });

  it("tolerates extra whitespace", () => {
    expect(describeCron("  30   6 * * *  ")).toContain("06:30 UTC");
  });
});
