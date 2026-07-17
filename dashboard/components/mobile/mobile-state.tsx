"use client";
import { createContext, useContext, useMemo, useState } from "react";
import { APPROVALS } from "@/lib/mobile-mock";

type Verdict = "approved" | "rejected";

interface MobileStateValue {
  online: boolean;
  toggleOnline: () => void;
  queued: number;
  addToQueue: () => void;
  approvalsDone: Record<string, Verdict>;
  resolveApproval: (id: string, verdict: Verdict) => void;
  openApprovalsCount: number;
}

const Ctx = createContext<MobileStateValue | null>(null);

export function MobileStateProvider({ children }: { children: React.ReactNode }) {
  const [online, setOnline] = useState(true);
  const [queued, setQueued] = useState(0);
  const [approvalsDone, setApprovalsDone] = useState<Record<string, Verdict>>({});

  const value = useMemo<MobileStateValue>(
    () => ({
      online,
      // Reconnecting flushes the queue (mock sync); going offline keeps it.
      toggleOnline: () => {
        setOnline((prev) => !prev);
        setQueued((prev) => (online ? prev : 0));
      },
      queued,
      addToQueue: () => setQueued((q) => q + 1),
      approvalsDone,
      resolveApproval: (id, verdict) => setApprovalsDone((d) => ({ ...d, [id]: verdict })),
      openApprovalsCount: APPROVALS.length - Object.keys(approvalsDone).length,
    }),
    [online, queued, approvalsDone],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useMobileState() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useMobileState must be used within MobileStateProvider");
  return v;
}
