import type { ReactNode } from "react";
import { AgentsTabs } from "@/components/observe-ui";

export default function AgentsLayout({ children }: { children: ReactNode }) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-ink">Agents</h2>
        <p className="text-sm text-ink-mid">
          What each agent can do, how the drivers perform, and why runs fail.
        </p>
      </div>
      <AgentsTabs />
      {children}
    </div>
  );
}
