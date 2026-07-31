const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/api/v1";

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

// Multipart upload — mirrors request()'s auth headers but lets the browser
// set the multipart boundary (no explicit Content-Type).
async function uploadRequest<T>(path: string, file: Blob, filename: string): Promise<T> {
  const url = new URL(`${API_BASE}${path}`);
  const form = new FormData();
  form.append("file", file, filename);
  const headers: Record<string, string> = {};
  if (typeof window !== "undefined") {
    const tenantId = localStorage.getItem("lg_tenant_id") || process.env.NEXT_PUBLIC_TENANT_ID || "default";
    const apiKey = localStorage.getItem("lg_api_key") || "";
    headers["X-Tenant-ID"] = tenantId;
    if (apiKey) headers["Authorization"] = `Bearer ${apiKey}`;
  }
  const res = await fetch(url.toString(), { method: "POST", headers, body: form });
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
  // ── Conversations (ask-your-memories chat) ──────
  /* eslint-disable @typescript-eslint/no-explicit-any -- payload shapes match the rest of this file's untyped API surface. */
  conversations: {
    create: () => POST<any>("/conversations", {}),
    list: () => listRequest<any>("/conversations"),
    get: (id: string) => GET<any>(`/conversations/${id}`),
    ask: (id: string, content: string) => POST<any>(`/conversations/${id}/messages`, { content }),
    remove: (id: string) => request<any>("DELETE", `/conversations/${id}`),
  },
  /* eslint-enable @typescript-eslint/no-explicit-any */

  // ── Memories ──────────────────────────────
  memories: {
    list: (params?: { limit?: string; offset?: string }) =>
      listRequest<any>("/memories/", params),
    create: (content: string) => POST<any>("/memories/", { content }),
    get: (id: string) => GET<any>(`/memories/${id}`),
    search: (query: string) =>
      // include_pending: the dashboard is allowed to see pending (badged) —
      // agent/automation callers (e.g. the MCP search tool) must NOT set this.
      POST<any>("/search/", { query, limit: 50, include_pending: true }).then((r: any) =>
        Array.isArray(r?.data) ? r.data : Array.isArray(r) ? r : []
      ),
    approve: (id: string) => POST(`/memories/${id}/approve`, {}),
    reject: (id: string) => POST(`/memories/${id}/reject`, {}),
    pendingCount: () => GET<{ data?: { count?: number } }>(`/memories/pending/count`),
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

  // ── Approvals (unified human-in-the-loop feed) ──
  approvals: {
    list: (status: string = "pending") =>
      listRequest<any>("/approvals", { status }),
    approve: (id: string, body?: { note?: string; resolved_by?: string }) =>
      POST<any>(`/approvals/${id}/approve`, body ?? {}),
    reject: (id: string, body?: { note?: string; resolved_by?: string }) =>
      POST<any>(`/approvals/${id}/reject`, body ?? {}),
  },

  // ── Multi-modal ingest ──────────────────────────
  ingest: {
    voice: (blob: Blob, filename: string) => uploadRequest<any>("/ingest/voice", blob, filename),
    image: (file: File) => uploadRequest<any>("/ingest/image", file, file.name),
    document: (file: File) => uploadRequest<any>("/ingest/document", file, file.name),
  },

  // ── Push notifications ──────────────────────────
  /* eslint-disable @typescript-eslint/no-explicit-any -- payload shapes match the rest of this file's untyped API surface. */
  push: {
    subscribe: (sub: any) => POST<any>("/push/subscriptions", sub),
    unsubscribe: (endpoint: string) => request<any>("DELETE", "/push/subscriptions", { endpoint }),
    test: () => POST<any>("/push/test", {}),
    vapidKey: () => GET<any>("/push/vapid-key"),
  },
  /* eslint-enable @typescript-eslint/no-explicit-any */
};
