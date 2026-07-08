"use client";
import { useEffect, useRef, useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

type WSStatus = "connecting" | "connected" | "disconnected";

/**
 * WebSocket hook that connects to the Life Graph event stream.
 * On any event, invalidates the relevant React Query cache so
 * pages update in real-time without polling.
 */
export function useWebSocket() {
  const qc = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const [status, setStatus] = useState<WSStatus>("disconnected");
  const [lastEvent, setLastEvent] = useState<any>(null);

  const connect = useCallback(() => {
    if (typeof window === "undefined") return;

    const apiKey = localStorage.getItem("lg_api_key") || "dev";
    const tenantId = localStorage.getItem("lg_tenant_id") || "default";
    const wsUrl = `${(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
      .replace("http://", "ws://")
      .replace("https://", "wss://")
      .replace("/api/v1", "")}/ws?api_key=${apiKey}&tenant_id=${tenantId}`;

    setStatus("connecting");
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("connected");
      console.log("[ws] connected");
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setLastEvent(data);

        // Invalidate relevant queries based on event type
        const type: string = data.type || "";
        if (type.startsWith("memory")) {
          qc.invalidateQueries({ queryKey: ["memories"] });
        }
        if (type.startsWith("preference")) {
          qc.invalidateQueries({ queryKey: ["preferences"] });
        }
        if (type.startsWith("task") || type.startsWith("kernel")) {
          qc.invalidateQueries({ queryKey: ["tasks"] });
        }
        if (type.startsWith("watcher") || type.startsWith("event")) {
          qc.invalidateQueries({ queryKey: ["watcher-events"] });
        }
        if (type.startsWith("notification")) {
          qc.invalidateQueries({ queryKey: ["notifications"] });
        }
        if (type.startsWith("evidence")) {
          qc.invalidateQueries({ queryKey: ["evidence"] });
        }
        if (type.startsWith("agent")) {
          qc.invalidateQueries({ queryKey: ["agent-tasks"] });
        }
        // Catch-all for any event: refresh beliefs, procedures
        if (type.startsWith("identity") || type.startsWith("belief")) {
          qc.invalidateQueries({ queryKey: ["beliefs"] });
        }
      } catch {
        // Not JSON, ignore
      }
    };

    ws.onclose = () => {
      setStatus("disconnected");
      console.log("[ws] disconnected, reconnecting in 5s...");
      reconnectTimer.current = setTimeout(connect, 5000);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [qc]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
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

  return { status, lastEvent };
}
