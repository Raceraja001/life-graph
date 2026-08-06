"use client";
// Ambient advisory roles settings surface: scout/admin/tutor run on a schedule
// and only report — this lets the user enable/disable each role, curate
// scout's watch-list topics, see their cadence in local time, and review
// what they've recently found. Mirrors the mobile card/chip conventions used
// by memory-sheet.tsx and the m/approvals, m/settings pages.
import { useState, type CSSProperties } from "react";
import { LoadingCard, EmptyCard, ErrorCard, SectionEyebrow } from "@/components/mobile/parts";
import {
  useAmbientSchedules,
  useUpdateAmbientSchedule,
  useAmbientFindings,
  describeCron,
  type AmbientJobVM,
  type AmbientFindingVM,
} from "@/lib/mobile-api";

const ROLE_LABEL: Record<string, string> = { scout: "Scout", admin: "Admin", tutor: "Tutor" };
const ROLE_ORDER = ["scout", "admin", "tutor"];

const cardStyle: CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-lg)",
  boxShadow: "var(--shadow-xs)",
  padding: "14px",
};

export default function AmbientRoles() {
  const schedules = useAmbientSchedules();
  const findings = useAmbientFindings();
  const update = useUpdateAmbientSchedule();

  const jobs = schedules.data ?? [];
  const byAgent = new Map(jobs.map((j) => [j.agentName, j]));
  const busyId = update.isPending ? update.variables?.id : undefined;

  return (
    <>
      <h1
        style={{
          fontFamily: "var(--font-display)",
          fontWeight: 800,
          fontSize: "var(--text-md)",
          letterSpacing: "var(--tracking-tight)",
          margin: "4px 0 0",
        }}
      >
        Ambient roles
      </h1>
      <p style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", margin: "2px 0 4px", lineHeight: 1.5 }}>
        Background personas that watch, then report — they never act without you.
      </p>

      {schedules.isLoading && <LoadingCard label="Loading ambient roles…" />}
      {schedules.isError && <ErrorCard>Can&rsquo;t reach schedules — is the backend running?</ErrorCard>}
      {!schedules.isLoading && !schedules.isError && jobs.length === 0 && (
        <EmptyCard>No ambient roles configured yet.</EmptyCard>
      )}
      {!schedules.isLoading &&
        !schedules.isError &&
        jobs.length > 0 &&
        ROLE_ORDER.map((agent) => {
          const job = byAgent.get(agent);
          if (!job) return null;
          return (
            <RoleCard
              key={job.id}
              job={job}
              busy={busyId === job.id}
              onToggle={(isActive) => update.mutate({ id: job.id, body: { is_active: isActive } })}
              onTopicsChange={(topics) => update.mutate({ id: job.id, body: { input: { topics } } })}
            />
          );
        })}

      <SectionEyebrow>Recent findings</SectionEyebrow>
      {findings.isLoading && <LoadingCard label="Loading findings…" />}
      {findings.isError && <ErrorCard>Can&rsquo;t reach findings — is the backend running?</ErrorCard>}
      {!findings.isLoading && !findings.isError && (findings.data ?? []).length === 0 && (
        <EmptyCard>No findings yet — check back after the next scheduled run.</EmptyCard>
      )}
      {!findings.isLoading &&
        !findings.isError &&
        (findings.data ?? []).map((f) => <FindingRow key={f.id} finding={f} />)}
    </>
  );
}

function RoleCard({
  job,
  busy,
  onToggle,
  onTopicsChange,
}: {
  job: AmbientJobVM;
  busy: boolean;
  onToggle: (isActive: boolean) => void;
  onTopicsChange: (topics: string[]) => void;
}) {
  const label = ROLE_LABEL[job.agentName] ?? job.agentName;
  return (
    <section style={{ ...cardStyle, opacity: busy ? 0.7 : 1 }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
        <span style={{ minWidth: 0, flex: 1 }}>
          <span style={{ display: "block", fontSize: "var(--ui-text)", fontWeight: "var(--fw-bold)" }}>{label}</span>
          {job.description && (
            <span
              style={{
                display: "block",
                fontSize: "var(--text-xs)",
                color: "var(--text-muted)",
                marginTop: "2px",
                lineHeight: 1.5,
              }}
            >
              {job.description}
            </span>
          )}
        </span>
        <ToggleSwitch checked={job.isActive} disabled={busy} onChange={onToggle} label={`${label} enabled`} />
      </div>

      {job.cronExpression && (
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "var(--text-2xs)",
            color: "var(--text-subtle)",
            marginTop: "10px",
          }}
        >
          {describeCron(job.cronExpression)}
        </div>
      )}

      {job.agentName === "scout" && (
        <TopicsEditor topics={job.topics} onChange={onTopicsChange} disabled={busy} />
      )}
    </section>
  );
}

function ToggleSwitch({
  checked,
  disabled,
  onChange,
  label,
}: {
  checked: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      style={{
        position: "relative",
        width: "42px",
        height: "24px",
        borderRadius: "var(--radius-pill)",
        border: `1px solid ${checked ? "var(--accent)" : "var(--border-strong)"}`,
        background: checked ? "var(--accent)" : "var(--surface-3)",
        cursor: disabled ? "default" : "pointer",
        padding: 0,
        flexShrink: 0,
      }}
    >
      <span
        aria-hidden
        style={{
          position: "absolute",
          top: "2px",
          left: checked ? "20px" : "2px",
          width: "18px",
          height: "18px",
          borderRadius: "50%",
          background: "#fff",
          boxShadow: "var(--shadow-xs)",
          transition: "left var(--dur-fast) var(--ease-out)",
        }}
      />
    </button>
  );
}

function TopicsEditor({
  topics,
  onChange,
  disabled,
}: {
  topics: string[];
  onChange: (topics: string[]) => void;
  disabled?: boolean;
}) {
  const [draft, setDraft] = useState("");

  const addTopic = () => {
    const t = draft.trim();
    if (!t || topics.includes(t)) {
      setDraft("");
      return;
    }
    onChange([...topics, t]);
    setDraft("");
  };
  const removeTopic = (t: string) => onChange(topics.filter((x) => x !== t));

  return (
    <div style={{ marginTop: "12px" }}>
      <div
        style={{
          fontSize: "var(--text-2xs)",
          fontWeight: "var(--fw-bold)",
          letterSpacing: "var(--tracking-caps)",
          textTransform: "uppercase",
          color: "var(--text-subtle)",
          marginBottom: "6px",
        }}
      >
        Watch-list
      </div>

      {topics.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "8px" }}>
          {topics.map((t) => (
            <span
              key={t}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                height: "24px",
                paddingInline: "10px 6px",
                borderRadius: "var(--radius-pill)",
                background: "var(--accent-soft)",
                color: "var(--accent-soft-fg)",
                fontSize: "var(--text-2xs)",
                fontWeight: "var(--fw-bold)",
              }}
            >
              {t}
              <button
                type="button"
                aria-label={`Remove ${t}`}
                onClick={() => removeTopic(t)}
                disabled={disabled}
                style={{
                  border: 0,
                  background: "transparent",
                  color: "inherit",
                  cursor: disabled ? "default" : "pointer",
                  fontSize: "14px",
                  lineHeight: 1,
                  padding: "0 2px",
                }}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      <div style={{ display: "flex", gap: "6px" }}>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addTopic();
            }
          }}
          placeholder="Add a topic…"
          disabled={disabled}
          style={{
            flex: 1,
            minWidth: 0,
            boxSizing: "border-box",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            background: "var(--surface-2)",
            color: "var(--text)",
            fontFamily: "inherit",
            fontSize: "var(--text-sm)",
            padding: "8px 10px",
          }}
        />
        <button
          type="button"
          onClick={addTopic}
          disabled={disabled || !draft.trim()}
          style={{
            border: 0,
            borderRadius: "var(--radius-md)",
            background: "var(--accent)",
            color: "var(--accent-fg)",
            fontFamily: "inherit",
            fontSize: "var(--text-xs)",
            fontWeight: "var(--fw-bold)",
            padding: "0 14px",
            cursor: disabled || !draft.trim() ? "default" : "pointer",
            opacity: disabled || !draft.trim() ? 0.6 : 1,
          }}
        >
          Add
        </button>
      </div>
    </div>
  );
}

const PRIORITY_DOT: Record<string, string> = {
  critical: "var(--danger)",
  important: "var(--danger)",
  info: "var(--info)",
};

function FindingRow({ finding }: { finding: AmbientFindingVM }) {
  return (
    <div style={cardStyle}>
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <span
          aria-hidden
          style={{
            width: "8px",
            height: "8px",
            borderRadius: "50%",
            background: PRIORITY_DOT[finding.priority] ?? "var(--text-subtle)",
            flexShrink: 0,
          }}
        />
        <span style={{ fontSize: "var(--ui-text)", fontWeight: "var(--fw-semibold)", flex: 1, minWidth: 0 }}>
          {finding.title}
        </span>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-2xs)", color: "var(--text-subtle)" }}>
          {ROLE_LABEL[finding.sourceType] ?? finding.sourceType}
        </span>
      </div>
      {finding.body && (
        <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", marginTop: "4px", lineHeight: 1.5 }}>
          {finding.body}
        </div>
      )}
    </div>
  );
}
