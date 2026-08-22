import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";

function mockFetch(impl: (url: string, init: RequestInit) => Response) {
  const spy = vi.fn(async (u: unknown, i: unknown) =>
    impl(String(u), (i ?? {}) as RequestInit),
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

describe("api request plumbing", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it("sends the tenant header from localStorage", async () => {
    localStorage.setItem("lg_tenant_id", "acme");
    const spy = mockFetch(() => json({ data: [] }));

    await api.memories.list();

    const headers = spy.mock.calls[0][1].headers as Record<string, string>;
    expect(headers["X-Tenant-ID"]).toBe("acme");
  });

  it("defaults the tenant header when nothing is stored", async () => {
    const spy = mockFetch(() => json({ data: [] }));
    await api.memories.list();
    const headers = spy.mock.calls[0][1].headers as Record<string, string>;
    expect(headers["X-Tenant-ID"]).toBe("default");
  });

  it("sends a bearer token when an api key is stored", async () => {
    localStorage.setItem("lg_api_key", "sk-xyz");
    const spy = mockFetch(() => json({ data: [] }));

    await api.memories.list();

    const headers = spy.mock.calls[0][1].headers as Record<string, string>;
    expect(headers["Authorization"]).toBe("Bearer sk-xyz");
  });

  it("omits Authorization entirely when there is no key", async () => {
    const spy = mockFetch(() => json({ data: [] }));
    await api.memories.list();
    const headers = spy.mock.calls[0][1].headers as Record<string, string>;
    expect(headers).not.toHaveProperty("Authorization");
  });

  it("unwraps a paginated {data: [...]} envelope", async () => {
    mockFetch(() => json({ data: [{ id: "1" }, { id: "2" }], meta: { total: 2 } }));
    await expect(api.memories.list()).resolves.toEqual([{ id: "1" }, { id: "2" }]);
  });

  it("passes a bare array through unchanged", async () => {
    mockFetch(() => json([{ id: "1" }]));
    await expect(api.memories.list()).resolves.toEqual([{ id: "1" }]);
  });

  it("returns [] for a response that is neither shape", async () => {
    mockFetch(() => json({ unexpected: true }));
    await expect(api.memories.list()).resolves.toEqual([]);
  });

  it("returns [] rather than throwing on a null body", async () => {
    mockFetch(() => json(null));
    await expect(api.memories.list()).resolves.toEqual([]);
  });

  it("drops falsy query params instead of sending empty values", async () => {
    const spy = mockFetch(() => json({ data: [] }));

    await api.memories.list({ limit: "10", offset: "" });

    const url = new URL(String(spy.mock.calls[0][0]));
    expect(url.searchParams.get("limit")).toBe("10");
    expect(url.searchParams.has("offset")).toBe(false);
  });

  it("surfaces the status and body on a non-ok response", async () => {
    mockFetch(() => new Response("boom", { status: 500 }));
    await expect(api.memories.list()).rejects.toThrow("API 500: boom");
  });

  it("propagates a 422 with its body", async () => {
    mockFetch(() => new Response("invalid cursor", { status: 422 }));
    await expect(api.memories.list()).rejects.toThrow("API 422: invalid cursor");
  });

  it("serializes a JSON body on POST", async () => {
    const spy = mockFetch(() => json({ id: "m1" }));

    await api.memories.create("remember this");

    const init = spy.mock.calls[0][1];
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ content: "remember this" });
  });

  it("sends no body when there is nothing to send", async () => {
    const spy = mockFetch(() => json({ data: [] }));
    await api.memories.list();
    expect(spy.mock.calls[0][1].body).toBeUndefined();
  });
});

describe("401 handling", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it("redirects to /login on 401", async () => {
    const replace = vi.fn();
    Object.defineProperty(window, "location", {
      value: { pathname: "/memories", replace },
      writable: true,
    });
    mockFetch(() => new Response("nope", { status: 401 }));

    await expect(api.memories.list()).rejects.toThrow("Unauthorized");
    expect(replace).toHaveBeenCalledWith("/login");
  });

  it("does not redirect when already on /login", async () => {
    const replace = vi.fn();
    Object.defineProperty(window, "location", {
      value: { pathname: "/login", replace },
      writable: true,
    });
    mockFetch(() => new Response("nope", { status: 401 }));

    await expect(api.memories.list()).rejects.toThrow("API 401: nope");
    expect(replace).not.toHaveBeenCalled();
  });
});
