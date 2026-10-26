import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { proxy } from "@/proxy";

// The page gate (cookie lg_authed) guards pages, not the API proxy: from another
// machine the login page verifies the key through /api/v1 before the cookie is
// set, and got a redirect to /login instead (2026-10-26).

const req = (path: string, signedIn = false) => {
  const r = new NextRequest(new URL(path, "https://race-home-pc.tailcdbd87.ts.net:10445"));
  if (signedIn) r.cookies.set("lg_authed", "1");
  return r;
};

describe("the page gate", () => {
  it("passes API proxy calls through without the cookie", () => {
    const res = proxy(req("/api/v1/memories/pending/count"));
    expect(res.headers.get("location")).toBeNull();
  });

  it("still sends a page to /login without the cookie", () => {
    const res = proxy(req("/memories"));
    expect(res.headers.get("location")).toContain("/login?from=%2Fmemories");
  });

  it("lets a signed-in page through", () => {
    expect(proxy(req("/memories", true)).headers.get("location")).toBeNull();
  });
});
