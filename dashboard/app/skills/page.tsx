"use client";
import { useEffect, useState } from "react";
import { Archive, Check, Loader2, Search, Sparkles, X } from "lucide-react";
import { useApproveSkill, useArchiveSkill, useSkill, useSkills } from "@/lib/hooks";

/* eslint-disable @typescript-eslint/no-explicit-any -- the skills payload is
   untyped here, as in lib/api.ts. */

// The tabs, in review order: everything, what the agents are actually using,
// what is waiting on a decision, what was thrown out.
const TABS = [
  { label: "All", status: undefined },
  { label: "Active", status: "active" },
  { label: "Needs Review", status: "needs_review" },
  { label: "Archived", status: "archived" },
] as const;

const STATUS_BADGE: Record<string, string> = {
  active: "bg-success-soft text-success",
  pending: "bg-warning-soft text-warning",
  needs_review: "bg-warning-soft text-warning",
  archived: "bg-surface-3 text-ink-mid",
};

function StatusBadge({ status }: { status?: string }) {
  if (!status) return null;
  return (
    <span
      className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
        STATUS_BADGE[status] ?? "bg-surface-3 text-ink-mid"
      }`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}

/** The distiller's fixed shape (`## Context & Symptoms`, `## Reusable Workflow`,
 *  `## Pitfalls`) plus the `### Learned <date>` notes a patch appends. Enough
 *  markdown for that, and no dependency: command blocks keep their newlines,
 *  which is the whole point of reading a recipe. */
function SkillMarkdown({ content }: { content: string }) {
  const lines = (content || "").split("\n");
  const blocks: { heading?: string; level: number; body: string[] }[] = [];
  for (const line of lines) {
    const match = /^(#{2,3})\s+(.*)$/.exec(line);
    if (match) {
      blocks.push({ heading: match[2], level: match[1].length, body: [] });
    } else if (!/^#\s/.test(line)) {
      // The `# Title` line is already the drawer's own heading.
      if (blocks.length === 0) blocks.push({ level: 0, body: [] });
      blocks[blocks.length - 1].body.push(line);
    }
  }
  return (
    <div className="space-y-4">
      {blocks.map((block, i) => (
        <div key={i}>
          {block.heading && (
            <h4
              className={
                block.level === 2
                  ? "text-[10px] font-medium text-ink-low uppercase tracking-wider mb-1.5"
                  : "text-xs font-semibold text-ink-mid mb-1.5"
              }
            >
              {block.heading}
            </h4>
          )}
          {block.body.join("\n").trim() && (
            <pre className="text-xs text-ink whitespace-pre-wrap break-words font-mono leading-relaxed bg-surface-2 border border-line rounded-lg p-3">
              {block.body.join("\n").trim()}
            </pre>
          )}
        </div>
      ))}
    </div>
  );
}

function SkillDrawer({ skill, onClose }: { skill: any; onClose: () => void }) {
  // The row the list already has, refreshed in the background: the drawer
  // stays open across an approve, and must not show the pre-approval status.
  const detail = useSkill(skill.id);
  const s = detail.data ?? skill;
  const approve = useApproveSkill();
  const archive = useArchiveSkill();
  const busy = approve.isPending || archive.isPending;

  return (
    <div className="fixed inset-0 z-40">
      <div className="absolute inset-0 bg-scrim" onClick={onClose} />
      <div className="absolute right-0 top-0 bottom-0 w-full sm:w-[520px] bg-surface border-l border-line shadow-2xl shadow-ink/10 overflow-y-auto">
        <div className="sticky top-0 bg-surface/90 backdrop-blur-sm border-b border-line px-6 py-4 flex items-start justify-between gap-3 z-10">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-ink break-words">{s.title}</h3>
            <div className="flex flex-wrap items-center gap-2 mt-1.5">
              <StatusBadge status={s.status} />
              {s.origin_agent && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-info-soft text-info font-medium">
                  {String(s.origin_agent).replace(/_/g, " ")}
                </span>
              )}
              {s.project && (
                <span className="text-[10px] px-1.5 py-0.5 bg-surface-3 text-ink-mid rounded">{s.project}</span>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-surface-3 text-ink-low hover:text-ink-mid transition-colors shrink-0"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          <SkillMarkdown content={s.content ?? ""} />

          {s.reasoning && (
            <div>
              <h4 className="text-[10px] font-medium text-ink-low uppercase tracking-wider mb-1.5">
                Why it was distilled
              </h4>
              <p className="text-xs text-ink-mid leading-relaxed">{s.reasoning}</p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <span className="block text-[10px] text-ink-low uppercase tracking-wider">Distilled</span>
              <span className="text-ink-mid">
                {s.created_at ? new Date(s.created_at).toLocaleString() : "—"}
              </span>
            </div>
            <div>
              <span className="block text-[10px] text-ink-low uppercase tracking-wider">Reinforced</span>
              <span className="text-ink-mid">{s.patch_count ? `${s.patch_count}×` : "never"}</span>
            </div>
            {s.session_id && (
              <div className="col-span-2 min-w-0">
                <span className="block text-[10px] text-ink-low uppercase tracking-wider">Session</span>
                <span className="text-ink-mid font-mono break-all">{s.session_id}</span>
              </div>
            )}
          </div>

          {(s.tags ?? []).length > 0 && (
            <div className="flex flex-wrap gap-1">
              {(s.tags as string[]).map((t) => (
                <span key={t} className="text-[10px] px-1.5 py-0.5 bg-surface-3 text-ink-mid rounded">
                  {t}
                </span>
              ))}
            </div>
          )}

          <div className="flex items-center gap-2 pt-2 border-t border-line">
            {s.status !== "active" && (
              <button
                onClick={() => approve.mutate(s.id)}
                disabled={busy}
                className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-lg bg-accent text-accent-fg hover:bg-accent-hover disabled:opacity-50"
              >
                {approve.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                {s.status === "archived" ? "Restore" : "Approve"}
              </button>
            )}
            {s.status !== "archived" && (
              <button
                onClick={() => archive.mutate(s.id, { onSuccess: onClose })}
                disabled={busy}
                className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg bg-surface-3 text-ink-mid hover:text-danger disabled:opacity-50"
              >
                {archive.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Archive className="w-3.5 h-3.5" />}
                Archive
              </button>
            )}
          </div>
          {(approve.isError || archive.isError) && (
            <p className="text-xs text-danger break-words">
              {String(((approve.error ?? archive.error) as Error)?.message ?? "")}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export default function SkillsPage() {
  const [term, setTerm] = useState("");
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState(0);
  const [selected, setSelected] = useState<any>(null);

  // Typing shouldn't be one request per keystroke.
  useEffect(() => {
    const timer = setTimeout(() => setSearch(term.trim()), 300);
    return () => clearTimeout(timer);
  }, [term]);

  const skills = useSkills({
    status: TABS[tab].status,
    search: search || undefined,
    limit: "100",
  });
  const approve = useApproveSkill();
  const archive = useArchiveSkill();
  const items: any[] = skills.data?.items ?? [];
  const pending = approve.variables ?? archive.variables;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ink">Procedural Skills</h2>
          <p className="text-sm text-ink-mid">
            Automated patterns and recipes distilled from agent sessions
          </p>
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-low" />
          <input
            type="text"
            value={term}
            onChange={(e) => setTerm(e.target.value)}
            placeholder="Search recipes..."
            className="bg-surface border border-line rounded-xl pl-10 pr-4 py-2 text-sm text-ink placeholder-ink-low focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft w-72"
          />
        </div>
      </div>

      <div className="flex items-center gap-1 border-b border-line">
        {TABS.map((t, i) => (
          <button
            key={t.label}
            onClick={() => setTab(i)}
            className={`px-3 py-2 text-sm -mb-px border-b-2 transition-colors ${
              i === tab
                ? "border-accent text-ink font-medium"
                : "border-transparent text-ink-mid hover:text-ink"
            }`}
          >
            {t.label}
            {i === tab && skills.data ? (
              <span className="ml-1.5 text-xs text-ink-low">{skills.data.total ?? items.length}</span>
            ) : null}
          </button>
        ))}
      </div>

      {skills.isError ? (
        <div className="bg-danger-soft border border-danger/30 rounded-xl p-5 text-sm text-danger">
          Cannot load skills — check API connection
        </div>
      ) : skills.isLoading ? (
        <div className="bg-surface border border-line rounded-xl p-12 text-center">
          <div className="animate-pulse text-ink-low text-sm">Loading skills...</div>
        </div>
      ) : items.length > 0 ? (
        <div className="bg-surface border border-line rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-line">
                <th className="text-left px-5 py-3 text-xs font-medium text-ink-low uppercase tracking-wider">Skill</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-ink-low uppercase tracking-wider w-36">Origin</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-ink-low uppercase tracking-wider w-32">Project</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-ink-low uppercase tracking-wider w-28">Status</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-ink-low uppercase tracking-wider w-28">Distilled</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-ink-low uppercase tracking-wider w-24">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((s) => (
                <tr
                  key={s.id}
                  onClick={() => setSelected(s)}
                  className="border-b border-line last:border-0 hover:bg-accent-soft/30 transition-colors cursor-pointer"
                >
                  <td className="px-5 py-3.5">
                    <p className="text-sm font-medium text-ink line-clamp-1">{s.title}</p>
                    <p className="text-xs text-ink-low line-clamp-1 mt-0.5">
                      {(s.body ?? "").replace(/^##.*$/gm, "").replace(/\s+/g, " ").trim()}
                    </p>
                  </td>
                  <td className="px-5 py-3.5">
                    {s.origin_agent && (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-info-soft text-info font-medium">
                        {String(s.origin_agent).replace(/_/g, " ")}
                      </span>
                    )}
                  </td>
                  <td className="px-5 py-3.5">
                    {s.project && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-surface-3 text-ink-mid rounded">{s.project}</span>
                    )}
                  </td>
                  <td className="px-5 py-3.5">
                    <StatusBadge status={s.status} />
                  </td>
                  <td className="px-5 py-3.5 text-xs text-ink-low">
                    {s.created_at ? new Date(s.created_at).toLocaleDateString() : ""}
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                      {s.reviewable && (
                        <button
                          onClick={() => approve.mutate(s.id)}
                          disabled={pending === s.id}
                          className="w-6 h-6 flex items-center justify-center rounded-md bg-accent-soft text-accent hover:bg-accent-soft disabled:opacity-50"
                          aria-label="Approve"
                          title="Approve into active recall"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                      )}
                      {s.status !== "archived" && (
                        <button
                          onClick={() => archive.mutate(s.id)}
                          disabled={pending === s.id}
                          className="w-6 h-6 flex items-center justify-center rounded-md bg-surface-3 text-ink-low hover:text-danger disabled:opacity-50"
                          aria-label="Archive"
                          title="Archive — stops being injected into agent prompts"
                        >
                          <Archive className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="bg-surface border border-line rounded-xl p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-xl bg-accent-soft flex items-center justify-center mx-auto">
            <Sparkles className="w-6 h-6 text-accent" />
          </div>
          <p className="text-sm text-ink-mid">
            {search
              ? `No skills match "${search}".`
              : "No skills distilled yet. They appear here once the transcript harvester finds a session worth a recipe."}
          </p>
        </div>
      )}

      {selected && <SkillDrawer key={selected.id} skill={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
