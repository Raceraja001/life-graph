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
  if (res.status === 401 && typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
    window.location.replace("/login");
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

// Unwrap paginated responses: {data: [...], meta: {...}} → [...]
async function listRequest<T>(path: string, params?: Record<string, string>): Promise<T[]> {
  const result = await request<any>("GET", path, undefined, params);
  // Handle both paginated {data: [...]} and flat array responses
  if (result && Array.isArray(result.data)) return result.data;
  if (Array.isArray(result)) return result;
  return [];
}

const GET = <T>(path: string, params?: Record<string, string>) => request<T>("GET", path, undefined, params);
const POST = <T>(path: string, body?: unknown) => request<T>("POST", path, body);

export const api = {
  // ── Memories ──────────────────────────────
  memories: {
    list: (params?: { limit?: string; offset?: string }) =>
      listRequest<any>("/memories/", params),
    get: (id: string) => GET<any>(`/memories/${id}`),
    search: (query: string) =>
      POST<any>("/search/", { query, limit: 50 }).then((r: any) =>
        Array.isArray(r?.data) ? r.data : Array.isArray(r) ? r : []
      ),
  },

  // ── Preferences (proxy for "decisions" until judgment engine exists) ──
  preferences: {
    list: (params?: { limit?: string }) =>
      listRequest<any>("/preferences/", params),
    get: (id: string) => GET<any>(`/preferences/${id}`),
    search: (query: string) =>
      POST<any>("/preferences/search", { query }).then((r: any) =>
        Array.isArray(r?.data) ? r.data : Array.isArray(r) ? r : []
      ),
  },

  // ── Identity / Beliefs ──────────────────────
  identity: {
    beliefs: () => GET<any>("/identity/beliefs"),
    challenge: (belief: string) => POST<any>("/identity/challenge", { belief }),
    timeline: () => GET<any>("/identity/timeline"),
  },

  // ── Evidence ──────────────────────────────
  evidence: {
    list: (params?: { limit?: string }) =>
      listRequest<any>("/evidence/", params),
    search: (query: string) =>
      POST<any>("/evidence/search", { query }).then((r: any) =>
        Array.isArray(r?.data) ? r.data : Array.isArray(r) ? r : []
      ),
  },

  // ── Kernel ──────────────────────────────
  kernel: {
    tasks: {
      list: (params?: { status?: string; limit?: string }) =>
        listRequest<any>("/kernel/tasks", params),
      get: (id: string) => GET<any>(`/kernel/tasks/${id}`),
    },
    route: (message: string) => POST<any>("/kernel/route", { message }),
    personas: () => GET<any[]>("/kernel/personas"),
    projects: () => listRequest<any>("/kernel/projects"),
    notifications: (params?: { limit?: string }) =>
      listRequest<any>("/kernel/notifications", params),
    sessions: () => listRequest<any>("/kernel/sessions"),
  },

  // ── Agent Tasks ──────────────────────────────
  agentTasks: {
    list: (params?: { limit?: string }) =>
      listRequest<any>("/agent-tasks", params),
    get: (id: string) => GET<any>(`/agent-tasks/${id}`),
  },

  // ── Procedures ──────────────────────────────
  procedures: {
    list: () => listRequest<any>("/procedures/"),
  },

  // ── Watchers ──────────────────────────────
  watchers: {
    events: (params?: { limit?: string }) =>
      listRequest<any>("/watchers/events", params),
    summary: () => GET<any>("/watchers/events/summary"),
    runs: () => listRequest<any>("/watchers/runs"),
  },

  // ── Self-Improving Dashboard ──────────────────
  selfImproving: {
    overview: () => GET<any>("/self-improving/dashboard/overview"),
  },

  // ── Advisor ──────────────────────────────
  advisor: {
    ask: (question: string) => POST<any>("/advisor/ask", { question }),
  },
};
