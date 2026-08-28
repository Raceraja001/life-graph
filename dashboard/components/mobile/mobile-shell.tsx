"use client";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { Settings, Wifi, WifiOff, X } from "lucide-react";
import { MobileTabBar } from "./mobile-tabbar";
import { useMobileState } from "./mobile-state";
import { useWebSocket } from "@/lib/use-websocket";

const TITLES: Record<string, string> = {
  "/m": "Life Graph",
  "/m/memories": "Memories",
  "/m/chat": "Ask",
  "/m/tasks": "Tasks",
  "/m/approvals": "Approvals",
  "/m/schedules": "Ambient roles",
  "/m/shadow": "Shadow log",
  "/m/settings": "Settings",
  "/m/personas": "Personas",
};

function titleFor(pathname: string) {
  if (pathname.startsWith("/m/memories")) return TITLES["/m/memories"];
  if (pathname.startsWith("/m/chat")) return TITLES["/m/chat"];
  if (pathname.startsWith("/m/tasks")) return TITLES["/m/tasks"];
  if (pathname.startsWith("/m/approvals")) return TITLES["/m/approvals"];
  if (pathname.startsWith("/m/schedules")) return TITLES["/m/schedules"];
  if (pathname.startsWith("/m/shadow")) return TITLES["/m/shadow"];
  if (pathname.startsWith("/m/settings")) return TITLES["/m/settings"];
  if (pathname.startsWith("/m/personas")) return TITLES["/m/personas"];
  return TITLES["/m"];
}

/** The event Chromium fires when the app is installable. Not in lib.dom. */
interface InstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

const DISMISS_KEY = "lg_install_dismissed";

/**
 * The install prompt, wired to the browser instead of faked.
 *
 * It used to render unconditionally on every screen and its "Install" button
 * only dismissed itself — a permanent ~100px advertisement above the fold for
 * something it couldn't actually do. Now it waits for `beforeinstallprompt`,
 * shows only where there's room for it, calls the real prompt, and remembers a
 * dismissal. Browsers that never fire the event (Safari, or an already-
 * installed PWA) simply never see it.
 */
function useInstallPrompt(enabled: boolean) {
  const [deferred, setDeferred] = useState<InstallPromptEvent | null>(null);

  useEffect(() => {
    const onPrompt = (e: Event) => {
      e.preventDefault(); // keep it out of the browser's own mini-infobar so we can place it
      let dismissed = false;
      try {
        dismissed = localStorage.getItem(DISMISS_KEY) === "1";
      } catch {
        /* private mode: no memory of a past dismissal, so show it */
      }
      if (!dismissed) setDeferred(e as InstallPromptEvent);
    };
    const onInstalled = () => setDeferred(null);
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  const dismiss = () => {
    setDeferred(null);
    try {
      localStorage.setItem(DISMISS_KEY, "1");
    } catch {
      /* private mode — the prompt comes back next session, which is acceptable */
    }
  };

  const install = async () => {
    if (!deferred) return;
    await deferred.prompt();
    await deferred.userChoice;
    setDeferred(null); // the event is single-use either way
  };

  return { show: enabled && deferred !== null, install, dismiss };
}

export function MobileShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { online, toggleOnline, queued } = useMobileState();
  const ws = useWebSocket(); // opens the live connection + refreshes query cache on events

  // Home is the only screen with room to spare, and the only one a first-run
  // user reliably lands on.
  const install = useInstallPrompt(online && pathname === "/m");

  const title = titleFor(pathname);
  const statusLine = !online
    ? `Offline · ${queued} queued`
    : ws === "connected"
      ? "All systems green"
      : ws === "connecting"
        ? "Connecting…"
        : "Reconnecting…";

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
      <header
        style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          padding: "calc(var(--o-lg) + env(safe-area-inset-top)) var(--space-gutter) var(--o-md)",
        }}
      >
        <span
          aria-hidden
          style={{
            width: "30px",
            height: "30px",
            borderRadius: "var(--radius-sm)",
            background: "var(--accent)",
            color: "var(--accent-fg)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: "var(--font-display)",
            fontWeight: "var(--display-weight)",
            fontSize: "15px",
            flexShrink: 0,
          }}
        >
          L
        </span>
        <span style={{ minWidth: 0 }}>
          <span
            className="type-title"
            style={{ display: "block", fontSize: "17px", lineHeight: 1.15 }}
          >
            {title}
          </span>
          {/* The status line is an eyebrow, not a log line — it used to render in
              JetBrains Mono, which made a health indicator look like stack output. */}
          <span className="type-eyebrow" style={{ display: "block", marginTop: "2px" }}>
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
            flexShrink: 0,
          }}
        >
          {online ? <Wifi width={15} height={15} /> : <WifiOff width={15} height={15} />}
        </button>
        <Link
          href="/m/settings"
          aria-label="Settings"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "30px",
            height: "30px",
            color: "var(--text-subtle)",
            flexShrink: 0,
          }}
        >
          <Settings width={15} height={15} />
        </Link>
      </header>

      {/* Offline banner */}
      {!online && (
        <div
          role="status"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "9px",
            margin: "0 var(--space-gutter) var(--space-row)",
            padding: "var(--o-sm) var(--o-md)",
            borderRadius: "var(--radius-row)",
            background: "var(--warning-soft)",
            color: "var(--warning)",
          }}
        >
          <WifiOff width={15} height={15} style={{ flexShrink: 0 }} />
          <span style={{ fontSize: "var(--size-meta)", fontWeight: 600 }}>
            Offline — {queued} captures queued, will sync on reconnect
          </span>
        </div>
      )}

      {/* Install banner */}
      {install.show && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "11px",
            margin: "0 var(--space-gutter) var(--space-row)",
            padding: "var(--o-sm) var(--o-md)",
            borderRadius: "var(--radius-row)",
            background: "var(--accent-soft)",
            border: "1px solid var(--accent-border)",
          }}
        >
          <span style={{ minWidth: 0, flex: 1 }}>
            <span style={{ display: "block", fontSize: "var(--size-body)", fontWeight: 600, color: "var(--accent-soft-fg)" }}>
              Add to your home screen
            </span>
            <span className="type-meta" style={{ display: "block", marginTop: "1px" }}>
              Capture from anywhere · works offline
            </span>
          </span>
          <button
            onClick={install.install}
            style={{
              height: "30px",
              paddingInline: "14px",
              border: 0,
              borderRadius: "var(--radius-pill)",
              background: "var(--accent)",
              color: "var(--accent-fg)",
              fontFamily: "inherit",
              fontSize: "var(--size-meta)",
              fontWeight: 600,
              cursor: "pointer",
              flexShrink: 0,
            }}
          >
            Install
          </button>
          <button
            onClick={install.dismiss}
            aria-label="Dismiss install prompt"
            style={{ border: 0, background: "transparent", color: "var(--text-subtle)", cursor: "pointer", display: "flex", padding: "4px", flexShrink: 0 }}
          >
            <X width={14} height={14} />
          </button>
        </div>
      )}

      {/* Content */}
      <main
        data-scroll-root
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "var(--space-row) var(--space-gutter) var(--o-xl)",
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-block)",
        }}
      >
        {children}
      </main>

      <MobileTabBar />
    </div>
  );
}
