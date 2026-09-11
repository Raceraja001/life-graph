"use client";
import type { CSSProperties } from "react";
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

  if (approvals.isLoading) return <LoadingCard label="Loading approvals…" />;
  if (approvals.isError) return <ErrorCard>Can’t reach approvals — is the backend running?</ErrorCard>;
  if (items.length === 0)
    return (
      <EmptyCard hint="Anything the system judges risky waits here instead of running on its own.">
        Nothing waiting on you. Inbox zero.
      </EmptyCard>
    );

  const pendingId = resolve.isPending ? resolve.variables?.id : undefined;

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

            <div style={{ display: "flex", gap: "8px", marginTop: "var(--space-block)" }}>
              <button
                onClick={() => resolve.mutate({ id: ap.id, decision: "approve" })}
                disabled={busy}
                style={{ ...actionBtn, border: 0, background: "var(--accent)", color: "var(--accent-fg)" }}
              >
                {busy ? "…" : "Approve"}
              </button>
              <button
                onClick={() => resolve.mutate({ id: ap.id, decision: "reject" })}
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
