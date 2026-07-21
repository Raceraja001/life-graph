"use client";
import { useState } from "react";
import { usePathname } from "next/navigation";
import { Wifi, WifiOff, X } from "lucide-react";
import { MobileTabBar } from "./mobile-tabbar";
import { useMobileState } from "./mobile-state";
import { useWebSocket } from "@/lib/use-websocket";

const TITLES: Record<string, string> = {
  "/m": "Life Graph",
  "/m/memories": "Memories",
  "/m/tasks": "Tasks",
  "/m/approvals": "Approvals",
};

function titleFor(pathname: string) {
  if (pathname.startsWith("/m/memories")) return TITLES["/m/memories"];
  if (pathname.startsWith("/m/tasks")) return TITLES["/m/tasks"];
  if (pathname.startsWith("/m/approvals")) return TITLES["/m/approvals"];
  return TITLES["/m"];
}

export function MobileShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { online, toggleOnline, queued } = useMobileState();
  const [installDismissed, setInstallDismissed] = useState(false);
  const ws = useWebSocket(); // opens the live connection + refreshes query cache on events

  const title = titleFor(pathname);
  const statusLine = !online
    ? `Offline mode · ${queued} queued`
    : ws === "connected"
      ? "All systems green"
      : ws === "connecting"
        ? "Connecting…"
        : "Reconnecting…";
  const showInstall = online && !installDismissed;

  return (
    <div
      style={{
        position: "relative",
        display: "flex",
        flexDirection: "column",
        height: "100dvh",
        maxWidth: "430px",
        margin: "0 auto",
        background: "var(--bg)",
        color: "var(--text)",
        borderInline: "1px solid var(--border)",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <header style={{ display: "flex", alignItems: "center", gap: "10px", padding: "14px 18px 10px" }}>
        <span
          aria-hidden
          style={{
            width: "30px",
            height: "30px",
            borderRadius: "var(--radius-md)",
            background: "var(--accent)",
            color: "var(--accent-fg)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: "var(--font-display)",
            fontWeight: 800,
            fontSize: "15px",
          }}
        >
          L
        </span>
        <span style={{ minWidth: 0 }}>
          <span
            style={{
              display: "block",
              fontFamily: "var(--font-display)",
              fontWeight: 800,
              fontSize: "var(--text-md)",
              letterSpacing: "var(--tracking-tight)",
            }}
          >
            {title}
          </span>
          <span style={{ display: "block", fontFamily: "var(--font-mono)", fontSize: "var(--text-2xs)", color: "var(--text-subtle)" }}>
            {statusLine}
          </span>
        </span>
        <button
          onClick={toggleOnline}
          title="Toggle connectivity (demo)"
          aria-label={online ? "Simulate going offline" : "Simulate reconnecting"}
          style={{
            marginInlineStart: "auto",
            width: "30px",
            height: "30px",
            borderRadius: "50%",
            background: online ? "var(--info-soft)" : "var(--warning-soft)",
            color: online ? "var(--info)" : "var(--warning)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            border: 0,
            cursor: "pointer",
          }}
        >
          {online ? <Wifi width={15} height={15} /> : <WifiOff width={15} height={15} />}
        </button>
      </header>

      {/* Offline banner */}
      {!online && (
        <div
          role="status"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "9px",
            margin: "0 18px 4px",
            padding: "9px 12px",
            borderRadius: "var(--radius-md)",
            background: "var(--warning-soft)",
            color: "var(--warning)",
          }}
        >
          <WifiOff width={15} height={15} style={{ flexShrink: 0 }} />
          <span style={{ fontSize: "var(--text-xs)", fontWeight: "var(--fw-semibold)" }}>
            Offline — {queued} captures queued, will sync on reconnect
          </span>
        </div>
      )}

      {/* Install banner */}
      {showInstall && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "11px",
            margin: "0 18px 4px",
            padding: "11px 13px",
            borderRadius: "var(--radius-lg)",
            background: "var(--accent-soft)",
            border: "1px solid var(--accent)",
          }}
        >
          <span
            aria-hidden
            style={{
              width: "32px",
              height: "32px",
              borderRadius: "var(--radius-md)",
              background: "var(--accent)",
              color: "var(--accent-fg)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: "var(--font-display)",
              fontWeight: 800,
              flexShrink: 0,
            }}
          >
            L
          </span>
          <span style={{ minWidth: 0, flex: 1 }}>
            <span style={{ display: "block", fontSize: "var(--text-sm)", fontWeight: "var(--fw-bold)", color: "var(--accent-soft-fg)" }}>
              Add Life Graph to your home screen
            </span>
            <span style={{ display: "block", fontSize: "var(--text-2xs)", color: "var(--text-muted)", marginTop: "1px" }}>
              Capture from anywhere · works offline
            </span>
          </span>
          <button
            onClick={() => setInstallDismissed(true)}
            style={{
              height: "32px",
              paddingInline: "13px",
              border: 0,
              borderRadius: "var(--radius-md)",
              background: "var(--accent)",
              color: "var(--accent-fg)",
              fontFamily: "inherit",
              fontSize: "var(--text-xs)",
              fontWeight: "var(--fw-bold)",
              cursor: "pointer",
              flexShrink: 0,
            }}
          >
            Install
          </button>
          <button
            onClick={() => setInstallDismissed(true)}
            aria-label="Dismiss install prompt"
            style={{ border: 0, background: "transparent", color: "var(--text-subtle)", cursor: "pointer", display: "flex", padding: "4px", flexShrink: 0 }}
          >
            <X width={14} height={14} />
          </button>
        </div>
      )}

      {/* Content */}
      <main
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "8px 18px 16px",
          display: "flex",
          flexDirection: "column",
          gap: "12px",
        }}
      >
        {children}
      </main>

      <MobileTabBar />
    </div>
  );
}
