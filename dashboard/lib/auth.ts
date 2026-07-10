/**
 * Client-side auth helpers.
 *
 * Credentials are stored in localStorage for API calls.
 * A `lg_authed=1` cookie is set so middleware (server-side)
 * can gate protected routes without needing localStorage.
 */

export function getCredentials(): { apiKey: string; tenantId: string } | null {
  if (typeof window === "undefined") return null;
  const apiKey = localStorage.getItem("lg_api_key");
  const tenantId = localStorage.getItem("lg_tenant_id");
  if (!apiKey) return null;
  return { apiKey, tenantId: tenantId || "default" };
}

export function isAuthenticated(): boolean {
  return getCredentials() !== null;
}

export function saveCredentials(apiKey: string, tenantId: string): void {
  localStorage.setItem("lg_api_key", apiKey);
  localStorage.setItem("lg_tenant_id", tenantId);
  // Set cookie so middleware can gate routes (max-age 30 days)
  document.cookie = `lg_authed=1; path=/; max-age=${60 * 60 * 24 * 30}; SameSite=Strict`;
}

export function logout(): void {
  localStorage.removeItem("lg_api_key");
  localStorage.removeItem("lg_tenant_id");
  // Clear the auth cookie
  document.cookie = "lg_authed=; path=/; max-age=0; SameSite=Strict";
  window.location.href = "/login";
}
