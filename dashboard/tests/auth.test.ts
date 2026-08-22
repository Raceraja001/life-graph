import { beforeEach, describe, expect, it, vi } from "vitest";
import { getCredentials, isAuthenticated, logout, saveCredentials } from "@/lib/auth";

describe("auth", () => {
  beforeEach(() => {
    localStorage.clear();
    document.cookie = "lg_authed=; path=/; max-age=0";
  });

  it("returns null when no key is stored", () => {
    expect(getCredentials()).toBeNull();
    expect(isAuthenticated()).toBe(false);
  });

  it("returns null when only a tenant is stored", () => {
    localStorage.setItem("lg_tenant_id", "acme");
    expect(getCredentials()).toBeNull();
  });

  it("defaults the tenant when only a key is stored", () => {
    localStorage.setItem("lg_api_key", "sk-test");
    expect(getCredentials()).toEqual({ apiKey: "sk-test", tenantId: "default" });
  });

  it("round-trips saved credentials", () => {
    saveCredentials("sk-abc", "acme");
    expect(getCredentials()).toEqual({ apiKey: "sk-abc", tenantId: "acme" });
    expect(isAuthenticated()).toBe(true);
  });

  it("sets the lg_authed cookie so middleware can gate routes", () => {
    saveCredentials("sk-abc", "acme");
    expect(document.cookie).toContain("lg_authed=1");
  });

  it("an empty api key is treated as unauthenticated", () => {
    localStorage.setItem("lg_api_key", "");
    expect(getCredentials()).toBeNull();
  });

  it("logout clears both keys and the cookie", () => {
    saveCredentials("sk-abc", "acme");
    const href = vi.fn();
    Object.defineProperty(window, "location", {
      value: { ...window.location, set href(v: string) { href(v); } },
      writable: true,
    });

    logout();

    expect(localStorage.getItem("lg_api_key")).toBeNull();
    expect(localStorage.getItem("lg_tenant_id")).toBeNull();
    expect(document.cookie).not.toContain("lg_authed=1");
    expect(href).toHaveBeenCalledWith("/login");
  });
});
