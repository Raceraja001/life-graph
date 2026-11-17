import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";
import { topbarTitle } from "@/components/app-topbar";

function mockFetch(body: unknown, status = 200) {
  const spy = vi.fn(
    async () =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

const SKILL = {
  id: "a1",
  title: "pytest cannot import pgvector",
  content: "# pytest cannot import pgvector\n## Context & Symptoms\nModuleNotFoundError\n",
  status: "active",
  reviewable: false,
  origin_agent: "claude_code",
  project: "life-graph",
  tags: ["skill", "dev-agent", "life-graph"],
  created_at: "2026-11-01T00:00:00+00:00",
};

describe("the skills API client", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it("reads the {items, total} envelope rather than a flat array", async () => {
    mockFetch({ data: { items: [SKILL], total: 1, limit: 50, offset: 0 } });

    const page = await api.skills.list();

    expect(page.total).toBe(1);
    expect(page.items[0].title).toBe("pytest cannot import pgvector");
  });

  it("sends the status, search and pagination filters as query parameters", async () => {
    const spy = mockFetch({ data: { items: [], total: 0 } });

    await api.skills.list({ status: "needs_review", search: "pgvector", limit: "100", offset: "0" });

    const calls = spy.mock.calls as any;
    const url = new URL(String(calls[0][0]));
    expect(url.pathname.endsWith("/skills")).toBe(true);
    expect(url.searchParams.get("status")).toBe("needs_review");
    expect(url.searchParams.get("search")).toBe("pgvector");
    expect(url.searchParams.get("limit")).toBe("100");
    // "0" is a non-empty string, so request() keeps it (an offset of 0 is a
    // real page, not an absent filter).
    expect(url.searchParams.get("offset")).toBe("0");
  });

  it("falls back to an empty page when the response carries no data", async () => {
    mockFetch({});
    await expect(api.skills.list()).resolves.toEqual({ items: [], total: 0 });
  });

  it("approves a skill with a POST to its approve route", async () => {
    const spy = mockFetch({ data: { ...SKILL, status: "active" } });

    const approved = await api.skills.approve("a1");

    const calls = spy.mock.calls as any;
    const [url, init] = calls[0];
    expect(String(url).endsWith("/skills/a1/approve")).toBe(true);
    expect(init.method).toBe("POST");
    expect(approved.status).toBe("active");
  });

  it("archives a skill with a DELETE and reads back the new status", async () => {
    const spy = mockFetch({ data: { id: "a1", status: "archived" } });

    const archived = await api.skills.archive("a1");

    const calls = spy.mock.calls as any;
    const [url, init] = calls[0];
    expect(String(url).endsWith("/skills/a1")).toBe(true);
    expect(init.method).toBe("DELETE");
    expect(archived).toEqual({ id: "a1", status: "archived" });
  });

  it("surfaces the API's message when a skill cannot be loaded", async () => {
    mockFetch({ detail: "Skill a1 not found" }, 404);
    await expect(api.skills.get("a1")).rejects.toThrow("Skill a1 not found");
  });

  it("titles the skills page in the top bar", () => {
    expect(topbarTitle("/skills")).toBe("Skills");
  });
});
