"use client";
import { useEffect, useRef, useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

type WSStatus = "connecting" | "connected" | "disconnected";

// Events that should trigger a cache refresh
const EVENT_MAP: Record<string, string[]> = {
  "memory":       ["memories"],
  "preference":   ["preferences"],
  "task":         ["tasks"],
  "kernel:task":  ["tasks"],
  "watcher":      ["watcher-events"],
  "notification": ["notifications"],
  "approval":     ["approvals"],
  "evidence":     ["evidence"],
  "agent":        ["agent-tasks"],
  "identity":     ["beliefs"],
  "belief":       ["beliefs"],
};

/**
 * WebSocket hook — connects to ws://backend/ws.
 * Only invalidates React Query cache on actual data events,
 * NOT on pong/heartbeat/unknown messages.
 */
export function useWebSocket() {
  const qc = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const mountedRef = useRef(true);
  const [status, setStatus] = useState<WSStatus>("disconnected");

  const connect = useCallback(() => {
    if (typeof window === "undefined" || !mountedRef.current) return;
    // Don't create a new connection if one is already open/connecting
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) return;

    const apiKey = localStorage.getItem("lg_api_key") || "dev";
    const tenantId = localStorage.getItem("lg_tenant_id") || "default";
    const wsUrl = `${(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080")
      .replace("http://", "ws://")
      .replace("https://", "wss://")
      .replace("/api/v1", "")}/ws?api_key=${apiKey}&tenant_id=${tenantId}`;

    setStatus("connecting");
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (mountedRef.current) setStatus("connected");
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        // Skip pong/heartbeat — these are NOT data events
        if (data.type === "pong" || data.type === "heartbeat") return;

        const type: string = data.type || "";
        // Only invalidate if we recognize the event type
        for (const [prefix, keys] of Object.entries(EVENT_MAP)) {
          if (type.startsWith(prefix)) {
            keys.forEach((key) => qc.invalidateQueries({ queryKey: [key] }));
            return; // matched, done
          }
        }
        // Unknown event type — do nothing (no blanket invalidation)
      } catch {
        // Not JSON — ignore
      }
    };

    ws.onclose = () => {
      if (mountedRef.current) {
        setStatus("disconnected");
        // Reconnect with backoff — only if still mounted
        reconnectTimer.current = setTimeout(connect, 10_000);
      }
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [qc]);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // prevent reconnect on unmount
        wsRef.current.close();
      }
    };
  }, [connect]);

  // Keepalive ping every 30s
  useEffect(() => {
    const interval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send("ping");
      }
    }, 30_000);
    return () => clearInterval(interval);
  }, []);

  return status;
}
