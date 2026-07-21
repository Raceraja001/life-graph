"use client";
import type { CSSProperties } from "react";
import { LoadingCard, EmptyCard, ErrorCard } from "@/components/mobile/parts";
import { useApprovals, useResolveApproval } from "@/lib/mobile-api";

const actionBtn: CSSProperties = {
  flex: 1,
  height: "40px",
  borderRadius: "var(--radius-md)",
  fontFamily: "inherit",
  fontSize: "var(--text-sm)",
  cursor: "pointer",
};

export default function MobileApprovals() {
  const approvals = useApprovals();
  const resolve = useResolveApproval();
  const items = approvals.data ?? [];

  if (approvals.isLoading) return <LoadingCard label="Loading approvals…" />;
  if (approvals.isError) return <ErrorCard>Can’t reach approvals — is the backend running?</ErrorCard>;
  if (items.length === 0) return <EmptyCard>Nothing waiting on you. Inbox zero.</EmptyCard>;

  const pendingId = resolve.isPending ? resolve.variables?.id : undefined;

  return (
    <>
      {items.map((ap) => {
        const busy = pendingId === ap.id;
        return (
          <section
            key={ap.id}
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-lg)",
              boxShadow: "var(--shadow-xs)",
              padding: "14px",
              opacity: busy ? 0.6 : 1,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
              <span style={{ fontSize: "var(--ui-text)", fontWeight: "var(--fw-bold)" }}>{ap.title}</span>
            </div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", marginTop: "4px", lineHeight: 1.5 }}>
              {ap.detail}
            </div>

            <div style={{ display: "flex", gap: "8px", marginTop: "11px" }}>
              <button
                onClick={() => resolve.mutate({ id: ap.id, decision: "approve" })}
                disabled={busy}
                style={{ ...actionBtn, border: 0, background: "var(--accent)", color: "var(--accent-fg)", fontWeight: "var(--fw-bold)" }}
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
                  fontWeight: "var(--fw-semibold)",
                }}
              >
                Reject
              </button>
            </div>
          </section>
        );
      })}
    </>
  );
}
