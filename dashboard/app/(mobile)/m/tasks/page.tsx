"use client";
import { SectionEyebrow, TaskRow, LoadingCard, EmptyCard, ErrorCard } from "@/components/mobile/parts";
import { useMobileTasks, TASK_GROUPS } from "@/lib/mobile-api";

export default function MobileTasks() {
  const tasks = useMobileTasks();

  if (tasks.isLoading) return <LoadingCard label="Loading tasks…" />;
  if (tasks.isError) return <ErrorCard>Can’t reach the task board — is the backend running?</ErrorCard>;

  const all = tasks.data ?? [];
  if (all.length === 0) return <EmptyCard>No tasks yet.</EmptyCard>;

  const groups = TASK_GROUPS.map((g) => ({ ...g, items: all.filter((t) => t.group === g.id) }));

  return (
    <>
      {groups.map((g) => (
        <section key={g.id}>
          <div style={{ display: "flex", alignItems: "center", gap: "7px", margin: "4px 0 8px" }}>
            <SectionEyebrow>{g.title}</SectionEyebrow>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-2xs)", color: "var(--text-subtle)" }}>
              {g.items.length}
            </span>
          </div>
          {g.items.length === 0 ? (
            <p style={{ fontSize: "var(--text-xs)", color: "var(--text-subtle)", padding: "2px 2px 6px" }}>None</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {g.items.map((t) => (
                <TaskRow key={t.id} task={t} />
              ))}
            </div>
          )}
        </section>
      ))}
    </>
  );
}
