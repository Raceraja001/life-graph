"use client";
import type { CSSProperties } from "react";
import { useMobileState } from "@/components/mobile/mobile-state";
import { APPROVALS } from "@/lib/mobile-mock";

const actionBtn: CSSProperties = {
  flex: 1,
  height: "40px",
  borderRadius: "var(--radius-md)",
  fontFamily: "inherit",
  fontSize: "var(--text-sm)",
  cursor: "pointer",
};

const resolvedPill = (approved: boolean): CSSProperties => ({
  display: "inline-flex",
  alignItems: "center",
  height: "20px",
  paddingInline: "8px",
  borderRadius: "var(--radius-pill)",
  background: approved ? "var(--success-soft)" : "var(--surface-3)",
  color: approved ? "var(--success)" : "var(--text-muted)",
  fontSize: "var(--text-2xs)",
  fontWeight: "var(--fw-bold)",
});

export default function MobileApprovals() {
  const { approvalsDone, resolveApproval } = useMobileState();

  return (
    <>
      {APPROVALS.map((ap) => {
        const verdict = approvalsDone[ap.id];
        return (
          <section
            key={ap.id}
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-lg)",
              boxShadow: "var(--shadow-xs)",
              padding: "14px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
              <span style={{ fontSize: "var(--ui-text)", fontWeight: "var(--fw-bold)" }}>{ap.title}</span>
            </div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", marginTop: "4px", lineHeight: 1.5 }}>
              {ap.detail}
            </div>

            {!verdict && (
              <div style={{ display: "flex", gap: "8px", marginTop: "11px" }}>
                <button
                  onClick={() => resolveApproval(ap.id, "approved")}
                  style={{ ...actionBtn, border: 0, background: "var(--accent)", color: "var(--accent-fg)", fontWeight: "var(--fw-bold)" }}
                >
                  Approve
                </button>
                <button
                  onClick={() => resolveApproval(ap.id, "rejected")}
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
            )}

            {verdict && (
              <div style={{ marginTop: "11px" }}>
                <span style={resolvedPill(verdict === "approved")}>
                  {verdict === "approved" ? "Approved — queued for execution" : "Rejected — logged"}
                </span>
              </div>
            )}
          </section>
        );
      })}
    </>
  );
}
