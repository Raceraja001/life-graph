import { SectionEyebrow, TaskRow } from "@/components/mobile/parts";
import { TASKS } from "@/lib/mobile-mock";

const GROUPS: Array<{ id: "inflight" | "queued" | "done"; title: string }> = [
  { id: "inflight", title: "In flight" },
  { id: "queued", title: "Queued" },
  { id: "done", title: "Done today" },
];

export default function MobileTasks() {
  const groups = GROUPS.map((g) => ({ ...g, items: TASKS.filter((t) => t.group === g.id) }));

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
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {g.items.map((t) => (
              <TaskRow key={t.id} task={t} />
            ))}
          </div>
        </section>
      ))}
    </>
  );
}
