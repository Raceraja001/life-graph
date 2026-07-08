"use client";
import { Search, Bell, LogOut } from "lucide-react";
import { usePathname } from "next/navigation";
import { logout } from "@/lib/auth";

const TITLES: Record<string, string> = {
  "/": "Overview",
  "/memories": "Memories",
  "/decisions": "Decisions",
  "/calibration": "Calibration",
  "/tasks": "Tasks",
  "/drivers": "Drivers",
  "/activity": "Activity",
  "/settings": "Settings",
};

export function AppTopbar({ onOpenCommand }: { onOpenCommand?: () => void }) {
  const pathname = usePathname();
  const title = TITLES[pathname] || "Life Graph";
  return (
    <header className="h-14 bg-white/80 backdrop-blur-sm border-b border-zinc-200 flex items-center justify-between px-6 shrink-0">
      <h1 className="text-sm font-semibold text-zinc-900">{title}</h1>
      <div className="flex items-center gap-2">
        <button
          onClick={onOpenCommand}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-zinc-100 border border-zinc-200 text-zinc-500 text-xs hover:text-zinc-700 hover:border-zinc-300 hover:shadow-sm transition-all"
        >
          <Search className="w-3.5 h-3.5" />
          <span>Search</span>
          <kbd className="ml-2 px-1.5 py-0.5 rounded bg-white border border-zinc-200 text-[10px] font-mono text-zinc-400">⌘K</kbd>
        </button>
        <button className="relative p-2 rounded-lg text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 transition-colors">
          <Bell className="w-4 h-4" />
        </button>
        <button
          onClick={logout}
          className="p-2 rounded-lg text-zinc-400 hover:text-red-500 hover:bg-red-50 transition-colors"
          title="Logout"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
