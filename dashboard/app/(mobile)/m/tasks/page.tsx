"use client";
import { EmptyCard, ErrorCard, LoadingCard, Meta, Section, Stack, TaskRow } from "@/components/mobile/parts";
import { useMobileTasks, TASK_GROUPS } from "@/lib/mobile-api";

export default function MobileTasks() {
  const tasks = useMobileTasks();

  if (tasks.isLoading) return <LoadingCard label="Loading tasks…" />;
  if (tasks.isError) return <ErrorCard>Can’t reach the task board — is the backend running?</ErrorCard>;

  const all = tasks.data ?? [];
  if (all.length === 0)
    return (
      <EmptyCard hint="Ask for something on the Ask tab, or approve a queued action — both land here.">
        No tasks yet.
      </EmptyCard>
    );

  const groups = TASK_GROUPS.map((g) => ({ ...g, items: all.filter((t) => t.group === g.id) }));

  return (
    <>
      {groups.map((g) => (
        <Section key={g.id} title={g.title} action={<Meta>{g.items.length}</Meta>}>
          {g.items.length === 0 ? (
            <Meta style={{ display: "block", padding: "0 2px" }}>None</Meta>
          ) : (
            <Stack>
              {g.items.map((t) => (
                <TaskRow key={t.id} task={t} />
              ))}
            </Stack>
          )}
        </Section>
      ))}
    </>
  );
}
