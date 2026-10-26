// Where the dashboard's requests go, chosen by where the page was opened.
//
// On this machine (localhost) the browser calls the API directly, at
// NEXT_PUBLIC_API_URL. Opened from another machine (the tailnet name), the
// browser's "localhost" is that machine, so requests go to the page's own
// origin at /api/v1, which next.config.ts rewrites to the API on the server:
// no CORS, and the API stays bound to loopback. The live-updates socket is
// not proxied by the rewrite; it goes to NEXT_PUBLIC_REMOTE_WS_URL (the API's
// own tailnet address), else the page origin's /ws.

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);

const localApi = () => process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/api/v1";

export interface PageLocation {
  hostname: string;
  protocol: string;
  host: string;
}

function isLocal(loc?: PageLocation): boolean {
  return !loc || LOCAL_HOSTS.has(loc.hostname);
}

/** The API base URL for requests from a page at *loc* (none: on the server). */
export function apiBase(loc?: PageLocation): string {
  return isLocal(loc) ? localApi() : "/api/v1";
}

/** The WebSocket base (…/ws) for a page at *loc*. */
export function wsBase(loc?: PageLocation): string {
  if (isLocal(loc)) {
    return `${localApi().replace("http://", "ws://").replace("https://", "wss://").replace("/api/v1", "")}/ws`;
  }
  const remote = process.env.NEXT_PUBLIC_REMOTE_WS_URL;
  if (remote) return remote;
  return `${loc!.protocol === "https:" ? "wss" : "ws"}://${loc!.host}/ws`;
}

/** This page's location, or none during server rendering. */
export function pageLocation(): PageLocation | undefined {
  return typeof window === "undefined" ? undefined : window.location;
}
