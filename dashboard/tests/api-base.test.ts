import { afterEach, describe, expect, it, vi } from "vitest";
import { apiBase, wsBase } from "@/lib/api-base";

// Opened from another machine, "localhost:8080" in the page means that
// machine: requests must go through this page's origin instead (2026-10-26).

const here = { hostname: "localhost", protocol: "http:", host: "localhost:3001" };
const tailnet = {
  hostname: "race-home-pc.tailcdbd87.ts.net",
  protocol: "https:",
  host: "race-home-pc.tailcdbd87.ts.net:10445",
};

describe("where requests go", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("calls the API directly on this machine and during server rendering", () => {
    expect(apiBase(here)).toBe("http://localhost:8080/api/v1");
    expect(apiBase(undefined)).toBe("http://localhost:8080/api/v1");
    expect(apiBase({ ...here, hostname: "127.0.0.1" })).toBe("http://localhost:8080/api/v1");
  });

  it("goes through the page's own origin from another machine", () => {
    expect(apiBase(tailnet)).toBe("/api/v1");
  });

  it("opens the live socket on the API's own address", () => {
    expect(wsBase(here)).toBe("ws://localhost:8080/ws");
    vi.stubEnv("NEXT_PUBLIC_REMOTE_WS_URL", "wss://race-home-pc.tailcdbd87.ts.net:10443/ws");
    expect(wsBase(tailnet)).toBe("wss://race-home-pc.tailcdbd87.ts.net:10443/ws");
  });

  it("falls back to the page origin's /ws, secure when the page is", () => {
    vi.stubEnv("NEXT_PUBLIC_REMOTE_WS_URL", "");
    expect(wsBase(tailnet)).toBe("wss://race-home-pc.tailcdbd87.ts.net:10445/ws");
  });
});
