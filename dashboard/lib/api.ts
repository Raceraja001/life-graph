const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function getHeaders(): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (typeof window !== "undefined") {
    const tenantId = localStorage.getItem("lg_tenant_id") || process.env.NEXT_PUBLIC_TENANT_ID || "default";
    const apiKey = localStorage.getItem("lg_api_key") || "";
    headers["X-Tenant-ID"] = tenantId;
    if (apiKey) headers["Authorization"] = `Bearer ${apiKey}`;
  }
  return headers;
}

async function request<T>(method: string, path: string, body?: unknown, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${API_BASE}${path}`);
  if (params) Object.entries(params).forEach(([k, v]) => { if (v) url.searchParams.set(k, v); });
  const res = await fetch(url.toString(), {
    method,
    headers: getHeaders(),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401 && typeof window !== "undefined") {
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json();
}

const GET = <T>(path: string, params?: Record<string, string>) => request<T>("GET", path, undefined, params);
const POST = <T>(path: string, body?: unknown) => request<T>("POST", path, body);

export const api = {
  memories: {
    list: (params?: { limit?: string; offset?: string }) => GET<any[]>("/memories/", params),
    get: (id: string) => GET<any>(`/memories/${id}`),
    search: (query: string) => POST<any[]>("/search/", { query, limit: 50 }),
  },
  judgment: {
    decisions: {
      list: (params?: { status?: string; limit?: string }) => GET<any[]>("/judgment/decisions", params),
      get: (id: string) => GET<any>(`/judgment/decisions/${id}`),
      create: (data: any) => POST<any>("/judgment/decisions", data),
    },
    predictions: {
      list: (params?: { outcome?: string; limit?: string }) => GET<any[]>("/judgment/predictions", params),
      create: (data: any) => POST<any>("/judgment/predictions", data),
      resolve: (id: string, data: any) => POST<any>(`/judgment/predictions/${id}/resolve`, data),
    },
    calibration: () => GET<any>("/judgment/calibration"),
    curve: (domain?: string) => GET<any>("/judgment/calibration/curve", domain ? { domain } : undefined),
    stats: () => GET<any>("/judgment/stats"),
    challenge: (proposal: string) => POST<any>("/judgment/challenge", { proposal }),
  },
  capture: {
    ingest: (data: { surface: string; content: string; modality?: string }) => POST<any>("/capture/", data),
    list: (params?: { surface?: string; since?: string; limit?: string }) => GET<any[]>("/capture/", params),
  },
  kernel: {
    tasks: { list: (params?: { status?: string; limit?: string }) => GET<any[]>("/kernel/tasks", params) },
    drivers: {
      list: () => GET<any[]>("/kernel/drivers"),
      stats: (window?: string) => GET<any>("/kernel/drivers/stats", window ? { window } : undefined),
    },
    route: (message: string) => POST<any>("/kernel/route", { message }),
  },
};
