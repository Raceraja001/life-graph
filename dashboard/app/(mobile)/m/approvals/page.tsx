"use client";
import { useState, type CSSProperties } from "react";
import { Card, EmptyCard, ErrorCard, LoadingCard, Meta, Stack } from "@/components/mobile/parts";
import { useApprovals, useResolveApproval } from "@/lib/mobile-api";
import { RiskBadge } from "@/components/shadow-log";

const actionBtn: CSSProperties = {
  flex: 1,
  height: "40px",
  borderRadius: "var(--radius-control)",
  fontFamily: "inherit",
  fontSize: "var(--size-body)",
  fontWeight: 600,
  cursor: "pointer",
};

export default function MobileApprovals() {
  const approvals = useApprovals();
  const resolve = useResolveApproval();
  const items = approvals.data ?? [];
  // Keyed by approval id: the side-effect (open a PR, run a merge) can fail
  // for a reason worth reading — CI not green yet, the PR moved, a merge
  // conflict — and that message already comes back from the API. It used
  // to just vanish: the button went idle again with nothing to show for it,
  // so clicking Approve again looked identical to the first click failing
  // silently, again.
  const [failed, setFailed] = useState<Record<string, string>>({});

  if (approvals.isLoading) return <LoadingCard label="Loading approvals…" />;
  if (approvals.isError) return <ErrorCard>Can’t reach approvals — is the backend running?</ErrorCard>;
  if (items.length === 0)
    return (
      <EmptyCard hint="Anything the system judges risky waits here instead of running on its own.">
        Nothing waiting on you. Inbox zero.
      </EmptyCard>
    );

  const pendingId = resolve.isPending ? resolve.variables?.id : undefined;

  function act(id: string, decision: "approve" | "reject") {
    setFailed((f) => {
      if (!(id in f)) return f;
      const { [id]: _drop, ...rest } = f;
      return rest;
    });
    resolve.mutate(
      { id, decision },
      {
        onError: (err) => {
          const message = err instanceof Error ? err.message : "Failed — try again.";
          setFailed((f) => ({ ...f, [id]: message }));
        },
      },
    );
  }

  return (
    <Stack gap="row">
      {items.map((ap) => {
        const busy = pendingId === ap.id;
        return (
          <Card
            key={ap.id}
            style={{
              opacity: busy ? 0.6 : 1,
              transition: "opacity var(--dur-fast) var(--ease-settle)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
              <span
                style={{
                  fontSize: "var(--size-body)",
                  fontWeight: 600,
                  letterSpacing: "var(--tracking-snug)",
                  flex: 1,
                  minWidth: 0,
                }}
              >
                {ap.title}
              </span>
              {ap.kind === "autonomous_action" && <RiskBadge risk={ap.riskLevel} />}
            </div>
            {ap.actionKind === "agent_task" ? (
              <>
                <div style={{ fontSize: "var(--size-meta)", color: "var(--text-muted)", marginTop: "5px", lineHeight: 1.5 }}>
                  {ap.instruction || ap.detail || "Agent task (no instruction provided)"}
                </div>
                <Meta style={{ display: "block", marginTop: "4px" }}>runs cody · build_ok, lint_clean</Meta>
              </>
            ) : (
              <div style={{ fontSize: "var(--size-meta)", color: "var(--text-muted)", marginTop: "5px", lineHeight: 1.5 }}>
                {ap.detail}
              </div>
            )}

            {failed[ap.id] && (
              <div
                role="alert"
                style={{
                  marginTop: "var(--space-block)",
                  padding: "8px 10px",
                  borderRadius: "var(--radius-control)",
                  background: "var(--danger-soft)",
                  color: "var(--danger)",
                  fontSize: "var(--size-meta)",
                  lineHeight: 1.5,
                }}
              >
                {failed[ap.id]}
              </div>
            )}

            <div style={{ display: "flex", gap: "8px", marginTop: "var(--space-block)" }}>
              <button
                onClick={() => act(ap.id, "approve")}
                disabled={busy}
                style={{ ...actionBtn, border: 0, background: "var(--accent)", color: "var(--accent-fg)" }}
              >
                {busy ? "…" : failed[ap.id] ? "Retry" : "Approve"}
              </button>
              <button
                onClick={() => act(ap.id, "reject")}
                disabled={busy}
                style={{
                  ...actionBtn,
                  border: "1px solid var(--border-strong)",
                  background: "var(--surface)",
                  color: "var(--text)",
                }}
              >
                Reject
              </button>
            </div>
          </Card>
        );
      })}
    </Stack>
  );
}
