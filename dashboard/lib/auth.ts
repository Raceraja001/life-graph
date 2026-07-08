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

export function logout(): void {
  localStorage.removeItem("lg_api_key");
  localStorage.removeItem("lg_tenant_id");
  window.location.href = "/login";
}
