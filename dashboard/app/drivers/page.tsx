"use client";
import { useState } from "react";
import Link from "next/link";
import { Bot, ExternalLink, GitBranch, GitMerge, GitPullRequest, Loader2, Send } from "lucide-react";
import { useCreateDevTask, useDevTasks, useDriverPersonas, useProjects } from "@/lib/hooks";

// stage (from the API) → label + badge colours. Order follows the pipeline.
const STAGES: Record<string, { label: string; cls: string }> = {
  queued: { label: "Queued", cls: "bg-surface-3 text-ink-mid" },
  running: { label: "Agent working", cls: "bg-info-soft text-info" },
  awaiting_pr: { label: "Approve PR", cls: "bg-warning-soft text-warning" },
  pr_open: { label: "PR open", cls: "bg-info-soft text-info" },
  awaiting_merge: { label: "Approve merge", cls: "bg-warning-soft text-warning" },
  merged: { label: "Merged", cls: "bg-success-soft text-success" },
  landed: { label: "Branch landed", cls: "bg-info-soft text-info" },
  needs_review: { label: "Needs review", cls: "bg-warning-soft text-warning" },
  pr_rejected: { label: "PR rejected", cls: "bg-surface-3 text-ink-mid" },
  completed: { label: "Done, no changes", cls: "bg-surface-3 text-ink-mid" },
  failed: { label: "Failed", cls: "bg-danger-soft text-danger" },
};

function ago(iso?: string | null) {
  if (!iso) return "";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function NewTaskForm() {
  const projects = useProjects();
  const personas = useDriverPersonas();
  const create = useCreateDevTask();
  const [projectId, setProjectId] = useState("");
  const [persona, setPersona] = useState("code-fixer");
  const [instruction, setInstruction] = useState("");

  const projectList: any[] = projects.data ?? [];
  const personaList: any[] = personas.data ?? [];
  const chosenProject = projectId || projectList[0]?.id || "";
  const chosenPersona = personaList.some((p) => p.name === persona) ? persona : personaList[0]?.name ?? "";
  const ready = !!chosenProject && !!chosenPersona && instruction.trim().length >= 5 && !create.isPending;

  const submit = () => {
    if (!ready) return;
    create.mutate(
      { instruction: instruction.trim(), project_id: chosenProject, persona_name: chosenPersona },
      { onSuccess: () => setInstruction("") },
    );
  };

  return (
    <div className="bg-surface border border-line rounded-xl p-4 space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="text-xs font-medium text-ink-mid uppercase tracking-wider">Project</span>
          <select
            value={chosenProject}
            onChange={(e) => setProjectId(e.target.value)}
            className="w-full mt-1 text-sm text-ink bg-surface-2 px-3 py-2 rounded-lg border border-line"
          >
            {projectList.length === 0 && <option value="">No registered projects</option>}
            {projectList.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
                {p.git_branch ? ` (${p.git_branch})` : ""}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-xs font-medium text-ink-mid uppercase tracking-wider">Agent</span>
          <select
            value={chosenPersona}
            onChange={(e) => setPersona(e.target.value)}
            className="w-full mt-1 text-sm text-ink bg-surface-2 px-3 py-2 rounded-lg border border-line"
          >
            {personaList.map((p) => (
              <option key={p.id} value={p.name}>
                {p.icon ? `${p.icon} ` : ""}
                {p.display_name || p.name} · {p.driver}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="block">
        <span className="text-xs font-medium text-ink-mid uppercase tracking-wider">What should change?</span>
        <textarea
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit();
          }}
          rows={4}
          placeholder="e.g. Add a --json flag to the stats CLI command that prints the stats as JSON. Keep the default output unchanged."
          className="w-full mt-1 text-sm text-ink bg-surface-2 px-3 py-2 rounded-lg border border-line resize-y"
        />
      </label>
      {create.isError && (
        <p className="text-xs text-danger break-words">
          Couldn&rsquo;t start the task — {String((create.error as Error)?.message ?? "")}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={!ready}
          onClick={submit}
          className={
            ready
              ? "inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg bg-accent text-accent-fg hover:bg-accent-hover cursor-pointer"
              : "inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg bg-surface-3 text-ink-low cursor-default"
          }
        >
          {create.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          Start task
        </button>
        <p className="text-xs text-ink-low">
          Runs in an isolated worktree, is checked in the sandbox, and comes back as a PR for you to approve.
        </p>
      </div>
    </div>
  );
}

function TaskCard({ t }: { t: any }) {
  const stage = STAGES[t.stage] ?? { label: t.stage, cls: "bg-surface-3 text-ink-mid" };
  const pending = (t.approvals ?? []).find((a: any) => a.status === "pending");
  return (
    <div className="bg-surface border border-line rounded-xl p-4 space-y-2">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-ink break-words">{t.title}</p>
          <p className="text-xs text-ink-low mt-0.5">
            {t.project_name} · {t.persona} · {ago(t.created_at)}
            {typeof t.cost_usd === "number" && t.cost_usd > 0 ? ` · $${t.cost_usd.toFixed(2)}` : ""}
            {t.duration_ms ? ` · ${Math.round(t.duration_ms / 1000)}s` : ""}
          </p>
        </div>
        <span
          className={`shrink-0 inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full ${stage.cls}`}
        >
          {t.stage === "running" && <Loader2 className="w-3 h-3 animate-spin" />}
          {stage.label}
        </span>
      </div>

      {(t.branch || t.pr_url || t.merge_commit || pending) && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
          {t.branch && (
            <span className="inline-flex items-center gap-1 text-ink-mid">
              <GitBranch className="w-3.5 h-3.5" /> {t.branch}
            </span>
          )}
          {t.pr_url && (
            <a
              href={t.pr_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-accent-text hover:underline"
            >
              <GitPullRequest className="w-3.5 h-3.5" /> PR #{t.pr_url.split("/").pop()}
              <ExternalLink className="w-3 h-3" />
            </a>
          )}
          {t.merge_commit && (
            <span className="inline-flex items-center gap-1 text-success">
              <GitMerge className="w-3.5 h-3.5" /> {t.merge_commit.slice(0, 8)}
            </span>
          )}
          {pending && (
            <Link href="/m/approvals" className="inline-flex items-center gap-1 text-warning hover:underline">
              Review in approvals →
            </Link>
          )}
        </div>
      )}

      {t.error && t.status === "failed" && <p className="text-xs text-danger break-words">{t.error}</p>}

      {t.output && (
        <details className="text-xs">
          <summary className="cursor-pointer text-ink-mid">Agent summary</summary>
          <p className="mt-1 whitespace-pre-wrap text-ink-mid break-words">{t.output}</p>
        </details>
      )}
    </div>
  );
}

export default function DevTasksPage() {
  const tasks = useDevTasks();
  const list: any[] = tasks.data ?? [];
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-ink">Dev tasks</h2>
        <p className="text-sm text-ink-mid">Ask an agent to change code in a registered project.</p>
      </div>

      <NewTaskForm />

      {tasks.isError ? (
        <p className="text-sm text-danger">Couldn&rsquo;t load tasks.</p>
      ) : list.length === 0 && !tasks.isLoading ? (
        <div className="bg-surface border border-line rounded-xl p-10 text-center space-y-2">
          <div className="w-10 h-10 rounded-xl bg-accent-soft flex items-center justify-center mx-auto">
            <Bot className="w-5 h-5 text-accent" />
          </div>
          <p className="text-sm text-ink-mid">No dev tasks yet.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {list.map((t) => (
            <TaskCard key={t.id} t={t} />
          ))}
        </div>
      )}
    </div>
  );
}
