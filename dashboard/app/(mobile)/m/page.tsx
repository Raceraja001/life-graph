"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronRight, Inbox } from "lucide-react";
import { MobileCapture } from "@/components/mobile/mobile-capture";
import { Card, EmptyCard, ErrorCard, Meta, Row, Section, SkeletonList, Stack, TaskRow } from "@/components/mobile/parts";
import { useApprovals, useMobileMemories, useMobileTasks } from "@/lib/mobile-api";
import { impLabel } from "@/lib/mobile-mock";
import { api } from "@/lib/api";
import { enablePush, disablePush, getPushState, type PushState } from "@/lib/push";
import { usePullToRefresh } from "@/lib/use-pull-to-refresh";

// A small inline button — the two states of the push control both need one, and
// neither is important enough to be a filled accent button.
const quietButton: React.CSSProperties = {
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-pill)",
  background: "var(--surface-2)",
  color: "var(--text-muted)",
  fontFamily: "inherit",
  fontSize: "var(--size-meta)",
  fontWeight: 600,
  padding: "5px 10px",
  cursor: "pointer",
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
      <Row style={{ color: "var(--text-muted)", fontSize: "var(--size-meta)" }}>
        <span aria-hidden>🔔</span>
        Blocked — enable notifications in your browser settings
      </Row>
    );
  }

  if (state === "subscribed") {
    return (
      <Row>
        <span aria-hidden>🔔</span>
        <span style={{ fontSize: "var(--size-body)", fontWeight: 600 }}>Notifications</span>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            height: "20px",
            paddingInline: "9px",
            borderRadius: "var(--radius-pill)",
            background: "var(--success-soft)",
            color: "var(--success)",
            fontSize: "var(--size-eyebrow)",
            fontWeight: 600,
          }}
        >
          On
        </span>
        <span style={{ marginInlineStart: "auto", display: "flex", gap: "8px", alignItems: "center" }}>
          {testMsg && <Meta>{testMsg}</Meta>}
          <button type="button" onClick={onTest} disabled={busy} style={quietButton}>
            Send test
          </button>
          <button
            type="button"
            onClick={onDisable}
            disabled={busy}
            style={{ ...quietButton, background: "transparent", color: "var(--text-subtle)" }}
          >
            Turn off
          </button>
        </span>
      </Row>
    );
  }

  return (
    <>
      <Row
        as="button"
        onClick={onEnable}
        disabled={busy}
        style={{
          width: "100%",
          textAlign: "start",
          color: "var(--text)",
          fontFamily: "inherit",
          fontSize: "var(--size-body)",
          fontWeight: 600,
          cursor: "pointer",
        }}
      >
        <span aria-hidden>🔔</span>
        Enable notifications
      </Row>
      {testMsg && <Meta style={{ marginTop: "2px" }}>{testMsg}</Meta>}
    </>
  );
}

export default function MobileHome() {
  const openApprovalsCount = useApprovals().data?.length ?? 0;
  const tasks = useMobileTasks();
  const memories = useMobileMemories(20);

  const { refreshing, distance } = usePullToRefresh({
    onRefresh: async () => {
      await Promise.all([tasks.refetch(), memories.refetch()]);
    },
  });

  const todayTasks = (tasks.data ?? []).filter((t) => t.group === "inflight");
  const recent = (memories.data ?? []).slice(0, 3);

  return (
    <>
      {(distance > 0 || refreshing) && (
        <div
          role="status"
          style={{
            height: refreshing ? 28 : distance,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--text-subtle)",
            fontSize: "var(--size-meta)",
            overflow: "hidden",
            transition: refreshing ? "height var(--dur-fast) var(--ease-settle)" : undefined,
          }}
        >
          {refreshing ? "Refreshing…" : distance >= 64 ? "Release to refresh" : "Pull to refresh"}
        </div>
      )}
      <MobileCapture />

      <PushControl />

      {openApprovalsCount > 0 && (
        <Link
          href="/m/approvals"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--o-md)",
            padding: "var(--o-md) var(--o-lg)",
            border: "1px solid var(--warning)",
            borderRadius: "var(--radius-card)",
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
              borderRadius: "var(--radius-sm)",
              background: "var(--warning)",
              color: "var(--warning-fg)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <Inbox width={16} height={16} />
          </span>
          <span style={{ minWidth: 0, flex: 1 }}>
            <span style={{ display: "block", fontSize: "var(--size-body)", fontWeight: 600, letterSpacing: "var(--tracking-snug)" }}>
              {openApprovalsCount} approvals waiting
            </span>
            <Meta style={{ display: "block", marginTop: "1px" }}>Merges, contradictions, a prompt promotion</Meta>
          </span>
          <ChevronRight width={15} height={15} style={{ color: "var(--text-subtle)", flexShrink: 0 }} />
        </Link>
      )}

      <Section
        title="Today"
        action={
          <Link
            href="/m/tasks"
            style={{
              color: "var(--accent-text)",
              fontSize: "var(--size-meta)",
              fontWeight: 600,
              textDecoration: "none",
            }}
          >
            All tasks →
          </Link>
        }
      >
        {tasks.isLoading ? (
          <SkeletonList count={2} />
        ) : tasks.isError ? (
          <ErrorCard>Can’t reach the task board — is the backend running?</ErrorCard>
        ) : todayTasks.length === 0 ? (
          <EmptyCard hint="Anything you start from Tasks or a chat shows up here while it runs.">
            Nothing in flight right now.
          </EmptyCard>
        ) : (
          <Stack>
            {todayTasks.map((t) => (
              <TaskRow key={t.id} task={t} showStatus />
            ))}
          </Stack>
        )}
      </Section>

      <Section title="Remembered today">
        {memories.isLoading ? (
          <SkeletonList count={3} />
        ) : memories.isError ? (
          <ErrorCard>Can’t reach memories.</ErrorCard>
        ) : recent.length === 0 ? (
          <EmptyCard hint="Type a thought into the box above — a sentence is enough.">
            Nothing captured today.
          </EmptyCard>
        ) : (
          <Stack>
            {recent.map((m) => (
              <Card key={m.id} style={{ padding: "var(--o-md) var(--o-lg)" }}>
                <div style={{ fontSize: "var(--size-body)", lineHeight: 1.5 }}>{m.content}</div>
                <div style={{ display: "flex", gap: "6px", marginTop: "var(--o-xs)", alignItems: "center" }}>
                  <Meta>{m.meta}</Meta>
                  <Meta style={{ marginInlineStart: "auto", color: "var(--accent-text)", fontWeight: 600 }}>
                    {impLabel(m.imp)}
                  </Meta>
                </div>
              </Card>
            ))}
          </Stack>
        )}
      </Section>
    </>
  );
}
