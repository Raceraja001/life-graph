import { describe, expect, it } from "vitest";
import { boardColumn, countLabel, isChatRun, taskAgent, taskTitle } from "@/lib/tasks";
import { currentError, type ModelHealthVM } from "@/lib/mobile-api";
import { topbarTitle } from "@/components/app-topbar";

// Found by opening every page against the live PC (2026-10-26): titles were
// task ids, failed tasks had no column, chat replies filled "Landed", tiles
// stopped at the page size, and a model showed a green dot beside "error".

describe("the task board", () => {
  it.each([
    ["queued", "queued"],
    ["running", "running"],
    ["verifying", "verifying"],
    ["completed", "landed"],
    ["failed", "failed"],
    ["timeout", "failed"],
    ["FAILED", "failed"],
  ])("puts %s in %s", (status, column) => {
    expect(boardColumn(status)).toBe(column);
  });

  it("leaves cancelled off the board and shows an unknown status as running", () => {
    expect(boardColumn("cancelled")).toBeNull();
    expect(boardColumn("reticulating")).toBe("running");
  });

  it("names a task by task_name and its agent by agent_name", () => {
    const row = { id: "f5e0a074", task_name: "Write unit tests for due_row", agent_name: "dev_task" };
    expect(taskTitle(row)).toBe("Write unit tests for due_row");
    expect(taskAgent(row)).toBe("dev_task");
    expect(taskTitle({ id: "f5e0a074" })).toBe("f5e0a074");
    expect(taskAgent({})).toBe("system");
  });

  it("tells chat replies from work", () => {
    expect(isChatRun({ task_name: "chat:jarvis" })).toBe(true);
    expect(isChatRun({ task_name: "Page monitors: parse_price" })).toBe(false);
    expect(isChatRun(null)).toBe(false);
  });
});

describe("counts from one page", () => {
  it("says 50+ when the API has more", () => {
    expect(countLabel(50, true)).toBe("50+");
    expect(countLabel(21, false)).toBe("21");
  });
});

describe("model health", () => {
  const base: ModelHealthVM = {
    model: "openrouter/cohere/north-mini-code:free",
    shortName: "north-mini-code:free",
    state: "up",
    lastSuccessAt: 200,
    lastFailureAt: 100,
    lastError: "error",
    avgLatencyMs: null,
    cooldownUntil: null,
  };

  it("hides an error the model has since recovered from", () => {
    expect(currentError(base)).toBeNull();
  });

  it("shows the error when the failure is the latest thing", () => {
    expect(currentError({ ...base, lastSuccessAt: 50 })).toBe("error");
    expect(currentError({ ...base, lastSuccessAt: null })).toBe("error");
    expect(currentError({ ...base, lastError: null })).toBeNull();
  });
});

describe("the top bar", () => {
  it("names a sub-page by its section", () => {
    expect(topbarTitle("/agents")).toBe("Agents");
    expect(topbarTitle("/agents/scorecards")).toBe("Agents");
    expect(topbarTitle("/drivers/123")).toBe("Dev tasks");
    expect(topbarTitle("/")).toBe("Overview");
    expect(topbarTitle("/nowhere")).toBe("Life Graph");
  });
});
