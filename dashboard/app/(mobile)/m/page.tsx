"use client";
import Link from "next/link";
import { ChevronRight, Inbox } from "lucide-react";
import { MobileCapture } from "@/components/mobile/mobile-capture";
import { SectionEyebrow, TaskRow, LoadingCard, EmptyCard, ErrorCard } from "@/components/mobile/parts";
import { useApprovals, useMobileMemories, useMobileTasks } from "@/lib/mobile-api";
import { impLabel } from "@/lib/mobile-mock";

export default function MobileHome() {
  const openApprovalsCount = useApprovals().data?.length ?? 0;
  const tasks = useMobileTasks();
  const memories = useMobileMemories(20);

  const todayTasks = (tasks.data ?? []).filter((t) => t.group === "inflight");
  const recent = (memories.data ?? []).slice(0, 3);

  return (
    <>
      <MobileCapture />

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
