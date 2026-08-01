"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronRight, Inbox } from "lucide-react";
import { MobileCapture } from "@/components/mobile/mobile-capture";
import { SectionEyebrow, TaskRow, LoadingCard, EmptyCard, ErrorCard } from "@/components/mobile/parts";
import { useApprovals, useMobileMemories, useMobileTasks } from "@/lib/mobile-api";
import { impLabel } from "@/lib/mobile-mock";
import { api } from "@/lib/api";
import { enablePush, disablePush, getPushState, type PushState } from "@/lib/push";

// Small pill/banner button styling shared by the two non-idle states —
// mirrors the approvals banner's card look (surface + border + radius-lg).
const pushCard: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "10px",
  padding: "11px 14px",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-lg)",
  background: "var(--surface)",
  fontFamily: "inherit",
};

function PushControl() {
  // null while we haven't yet checked permission/subscription on the client.
  const [state, setState] = useState<PushState | null>(null);
  const [busy, setBusy] = useState(false);
  const [testMsg, setTestMsg] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    getPushState()
      .then(setState)
      .catch(() => setState("unsupported"));
  }, []);

  if (state === null || state === "unsupported") return null;

  const onEnable = async () => {
    setBusy(true);
    try {
      setState(await enablePush());
    } catch {
      setTestMsg("Couldn't enable notifications");
    } finally {
      setBusy(false);
    }
  };

  const onDisable = async () => {
    setBusy(true);
    try {
      setState(await disablePush());
      setTestMsg(null);
    } catch {
      setTestMsg("Couldn't disable notifications");
    } finally {
      setBusy(false);
    }
  };

  const onTest = async () => {
    setBusy(true);
    setTestMsg(null);
    try {
      const res = await api.push.test();
      setTestMsg(res?.data?.delivered ? "Test sent" : "Couldn't send test");
    } catch {
      setTestMsg("Couldn't send test");
    } finally {
      setBusy(false);
    }
  };

  if (state === "denied") {
    return (
      <div style={{ ...pushCard, color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>
        <span aria-hidden>🔔</span>
        Blocked — enable notifications in your browser settings
      </div>
    );
  }

  if (state === "subscribed") {
    return (
      <div style={pushCard}>
        <span aria-hidden>🔔</span>
        <span style={{ fontSize: "var(--ui-text)", fontWeight: "var(--fw-semibold)" }}>Notifications</span>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            height: "20px",
            paddingInline: "8px",
            borderRadius: "var(--radius-pill)",
            background: "var(--success-soft)",
            color: "var(--success)",
            fontSize: "var(--text-2xs)",
            fontWeight: "var(--fw-bold)",
          }}
        >
          On
        </span>
        <span style={{ marginInlineStart: "auto", display: "flex", gap: "8px", alignItems: "center" }}>
          {testMsg && <span style={{ fontSize: "var(--text-2xs)", color: "var(--text-subtle)" }}>{testMsg}</span>}
          <button
            type="button"
            onClick={onTest}
            disabled={busy}
            style={{
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-pill)",
              background: "var(--surface-2)",
              color: "var(--text-muted)",
              fontFamily: "inherit",
              fontSize: "var(--text-2xs)",
              fontWeight: "var(--fw-semibold)",
              padding: "5px 10px",
              cursor: "pointer",
            }}
          >
            Send test
          </button>
          <button
            type="button"
            onClick={onDisable}
            disabled={busy}
            style={{
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-pill)",
              background: "transparent",
              color: "var(--text-subtle)",
              fontFamily: "inherit",
              fontSize: "var(--text-2xs)",
              fontWeight: "var(--fw-semibold)",
              padding: "5px 10px",
              cursor: "pointer",
            }}
          >
            Turn off
          </button>
        </span>
      </div>
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={onEnable}
        disabled={busy}
        style={{
          ...pushCard,
          width: "100%",
          textAlign: "start",
          color: "var(--text)",
          fontSize: "var(--ui-text)",
          fontWeight: "var(--fw-semibold)",
          cursor: "pointer",
        }}
      >
        <span aria-hidden>🔔</span>
        Enable notifications
      </button>
      {testMsg && (
        <p style={{ fontSize: "var(--text-2xs)", color: "var(--text-subtle)", margin: "4px 0 0" }}>{testMsg}</p>
      )}
    </>
  );
}

export default function MobileHome() {
  const openApprovalsCount = useApprovals().data?.length ?? 0;
  const tasks = useMobileTasks();
  const memories = useMobileMemories(20);

  const todayTasks = (tasks.data ?? []).filter((t) => t.group === "inflight");
  const recent = (memories.data ?? []).slice(0, 3);

  return (
    <>
      <MobileCapture />

      <PushControl />

      {openApprovalsCount > 0 && (
        <Link
          href="/m/approvals"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "12px",
            padding: "13px 14px",
            border: "1px solid var(--warning)",
            borderRadius: "var(--radius-lg)",
            background: "var(--warning-soft)",
            textAlign: "start",
            color: "var(--text)",
            textDecoration: "none",
          }}
        >
          <span
            aria-hidden
            style={{
              width: "34px",
              height: "34px",
              borderRadius: "var(--radius-md)",
              background: "var(--warning)",
              color: "#fff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <Inbox width={16} height={16} />
          </span>
          <span style={{ minWidth: 0, flex: 1 }}>
            <span style={{ display: "block", fontSize: "var(--ui-text)", fontWeight: "var(--fw-bold)" }}>
              {openApprovalsCount} approvals waiting
            </span>
            <span style={{ display: "block", fontSize: "var(--text-xs)", color: "var(--text-muted)", marginTop: "1px" }}>
              Merges, contradictions, a prompt promotion
            </span>
          </span>
          <ChevronRight width={15} height={15} style={{ color: "var(--text-subtle)", flexShrink: 0 }} />
        </Link>
      )}

      <section>
        <div style={{ display: "flex", alignItems: "baseline", margin: "4px 0 8px" }}>
          <SectionEyebrow>Today</SectionEyebrow>
          <Link
            href="/m/tasks"
            style={{
              marginInlineStart: "auto",
              color: "var(--accent-text)",
              fontSize: "var(--text-xs)",
              fontWeight: "var(--fw-semibold)",
              textDecoration: "none",
            }}
          >
            All tasks →
          </Link>
        </div>
        {tasks.isLoading ? (
          <LoadingCard label="Loading tasks…" />
        ) : tasks.isError ? (
          <ErrorCard>Can’t reach the task board — is the backend running?</ErrorCard>
        ) : todayTasks.length === 0 ? (
          <EmptyCard>Nothing in flight right now.</EmptyCard>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {todayTasks.map((t) => (
              <TaskRow key={t.id} task={t} showStatus />
            ))}
          </div>
        )}
      </section>

      <section>
        <div style={{ margin: "4px 0 8px" }}>
          <SectionEyebrow>Remembered today</SectionEyebrow>
        </div>
        {memories.isLoading ? (
          <LoadingCard label="Loading memories…" />
        ) : memories.isError ? (
          <ErrorCard>Can’t reach memories.</ErrorCard>
        ) : recent.length === 0 ? (
          <EmptyCard>No memories yet — capture a thought above.</EmptyCard>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {recent.map((m) => (
              <div
                key={m.id}
                style={{
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-lg)",
                  padding: "12px 14px",
                }}
              >
                <div style={{ fontSize: "var(--ui-text)", lineHeight: 1.5 }}>{m.content}</div>
                <div style={{ display: "flex", gap: "6px", marginTop: "7px", alignItems: "center" }}>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-2xs)", color: "var(--text-subtle)" }}>
                    {m.meta}
                  </span>
                  <span
                    style={{
                      marginInlineStart: "auto",
                      fontFamily: "var(--font-mono)",
                      fontSize: "var(--text-2xs)",
                      fontWeight: "var(--fw-bold)",
                      color: "var(--accent-text)",
                    }}
                  >
                    {impLabel(m.imp)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
