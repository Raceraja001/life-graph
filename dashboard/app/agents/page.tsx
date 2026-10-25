"use client";
// Agents console: every persona, the tools it lists against the tools that
// exist, and a live probe that sends one prompt and shows each tool call.
import { useRef, useState } from "react";
import { AlertTriangle, Bot, Play, Square, Wrench } from "lucide-react";
import { api } from "@/lib/api";
import { useAgents, type AgentView } from "@/lib/observe";
import { Card, ErrorBox, Loading, Pill } from "@/components/observe-ui";

type ProbeLine = { kind: "text" | "tool" | "result" | "error"; text: string; name?: string };

function Probe({ agent }: { agent: AgentView }) {
  const [prompt, setPrompt] = useState("");
  const [lines, setLines] = useState<ProbeLine[]>([]);
  const [running, setRunning] = useState(false);
  const abort = useRef<AbortController | null>(null);

  async function run() {
    if (!prompt.trim()) return;
    const ctl = new AbortController();
    abort.current = ctl;
    setLines([]);
    setRunning(true);
    const push = (l: ProbeLine) =>
      setLines((prev) => {
        const last = prev[prev.length - 1];
        // Stream deltas into one paragraph rather than one line per token.
        if (l.kind === "text" && last?.kind === "text") return [...prev.slice(0, -1), { ...last, text: last.text + l.text }];
        return [...prev, l];
      });
    try {
      await api.kernel.chatStream(
        prompt,
        agent.name,
        (ev: { type?: string; text?: string; name?: string; arguments?: string; result?: string; message?: string }) => {
          if (ev.type === "assistant_delta" && ev.text) push({ kind: "text", text: ev.text });
          else if (ev.type === "tool_call") push({ kind: "tool", name: ev.name, text: ev.arguments ?? "" });
          else if (ev.type === "tool_result") push({ kind: "result", name: ev.name, text: ev.result ?? "" });
          else if (ev.type === "error") push({ kind: "error", text: ev.message ?? "error" });
        },
        ctl.signal,
      );
    } catch (err) {
      if (!ctl.signal.aborted) push({ kind: "error", text: (err as Error).message });
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="mt-3 border-t border-line pt-3">
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void run();
        }}
      >
        <input
          aria-label={`Test prompt for ${agent.name}`}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Ask it something it should be able to do…"
          className="min-w-0 flex-1 rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-xs text-ink"
        />
        {running ? (
          <button
            type="button"
            onClick={() => abort.current?.abort()}
            className="inline-flex items-center gap-1 rounded-lg border border-line px-3 py-1.5 text-xs text-ink-mid"
          >
            <Square className="h-3.5 w-3.5" /> Stop
          </button>
        ) : (
          <button
            type="submit"
            disabled={!prompt.trim()}
            className={`inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-semibold ${
              prompt.trim() ? "bg-accent text-accent-fg hover:bg-accent-hover" : "bg-surface-3 text-ink-low"
            }`}
          >
            <Play className="h-3.5 w-3.5" /> Test
          </button>
        )}
      </form>
      {lines.length > 0 && (
        <ol className="mt-2 space-y-1.5" aria-live="polite">
          {lines.map((l, i) => (
            <li
              key={i}
              className={`rounded-md p-2 text-xs whitespace-pre-wrap break-words ${
                l.kind === "text"
                  ? "bg-surface-2 text-ink"
                  : l.kind === "tool"
                    ? "border border-accent-border font-mono text-ink"
                    : l.kind === "result"
                      ? "max-h-40 overflow-auto bg-surface-2 font-mono text-[11px] text-ink-mid"
                      : "bg-danger-soft text-danger"
              }`}
            >
              {l.kind === "tool" && (
                <span className="mr-1 inline-flex items-center gap-1 font-semibold">
                  <Wrench className="h-3 w-3" /> {l.name}
                </span>
              )}
              {l.text}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function AgentCard({ a }: { a: AgentView }) {
  const [open, setOpen] = useState(false);
  return (
    <li>
      <Card className={a.missing_tools.length > 0 ? "border-danger/40" : ""}>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ink">
              {a.icon} {a.display_name ?? a.name}{" "}
              <span className="font-mono text-xs font-normal text-ink-low">{a.name}</span>
            </p>
            {a.description && <p className="mt-0.5 text-xs text-ink-mid">{a.description}</p>}
            <p className="mt-1 break-all font-mono text-[11px] text-ink-low">
              {a.model}
              {a.driver ? ` · driver ${a.driver}` : ""}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            className={`rounded-lg px-3 py-1.5 text-xs ${
              open ? "bg-accent-soft text-accent-soft-fg" : "border border-line text-ink-mid hover:bg-surface-2"
            }`}
          >
            {open ? "Close test" : "Test this agent"}
          </button>
        </div>
        <div className="mt-2 flex flex-wrap gap-1">
          {a.unscoped && <Pill>all tools (unscoped)</Pill>}
          {a.tools.map((t) => (
            <Pill key={t.name} tone={t.registered ? "neutral" : "danger"}>
              {t.name}
              {!t.registered && " · missing"}
            </Pill>
          ))}
        </div>
        {a.missing_tools.length > 0 && (
          <p className="mt-2 flex items-start gap-1.5 text-xs text-danger">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            {a.missing_tools.length} listed tool{a.missing_tools.length > 1 ? "s are" : " is"} not registered, so this
            persona silently runs without {a.missing_tools.length > 1 ? "them" : "it"}.
          </p>
        )}
        {a.notes.map((n) => (
          <p key={n} className="mt-1 text-xs text-warning">
            {n}
          </p>
        ))}
        {open && <Probe agent={a} />}
      </Card>
    </li>
  );
}

export default function AgentsConsolePage() {
  const agents = useAgents();
  const list = agents.data ?? [];
  const missing = list.filter((a) => a.missing_tools.length > 0).length;
  return (
    <div className="space-y-3">
      <ErrorBox error={agents.error} />
      {agents.isLoading && !agents.data && <Loading />}
      {agents.data && (
        <p className="flex items-center gap-2 text-xs text-ink-mid">
          <Bot className="h-4 w-4" /> {list.length} personas ·{" "}
          {missing === 0 ? "every listed tool is registered" : `${missing} with tools that do not exist`}
        </p>
      )}
      <ul className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        {list.map((a) => (
          <AgentCard key={a.name} a={a} />
        ))}
      </ul>
    </div>
  );
}
