"use client";
import { Bot } from "lucide-react";

export default function DriversPage() {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-ink">Drivers</h2>
        <p className="text-sm text-ink-mid">Agent driver performance — verified tasks per ₹</p>
      </div>

      <div className="bg-surface border border-line rounded-xl p-12 text-center space-y-3">
        <div className="w-12 h-12 rounded-xl bg-accent-soft flex items-center justify-center mx-auto">
          <Bot className="w-6 h-6 text-accent" />
        </div>
        <h3 className="text-lg font-semibold text-ink">Coming Soon</h3>
        <p className="text-sm text-ink-mid max-w-md mx-auto">
          Driver stats will appear here once the Agent Drivers spec is built. Track cost, accuracy, and throughput per agent driver.
        </p>
      </div>
    </div>
  );
}
