"use client";
import { Bot } from "lucide-react";

export default function DriversPage() {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-zinc-900">Drivers</h2>
        <p className="text-sm text-zinc-500">Agent driver performance — verified tasks per ₹</p>
      </div>

      <div className="bg-white border border-zinc-200 rounded-xl p-12 text-center space-y-3">
        <div className="w-12 h-12 rounded-xl bg-emerald-50 flex items-center justify-center mx-auto">
          <Bot className="w-6 h-6 text-emerald-500" />
        </div>
        <h3 className="text-lg font-semibold text-zinc-800">Coming Soon</h3>
        <p className="text-sm text-zinc-500 max-w-md mx-auto">
          Driver stats will appear here once the Agent Drivers spec is built. Track cost, accuracy, and throughput per agent driver.
        </p>
      </div>
    </div>
  );
}
