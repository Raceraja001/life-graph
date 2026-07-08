"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Brain, Scale, BarChart3, ClipboardList, Bot, Activity, Settings, Zap, Menu, X } from "lucide-react";
import { useState, useEffect } from "react";

const NAV = [
  { label: "Overview", href: "/", icon: Zap },
  { label: "Memories", href: "/memories", icon: Brain },
  { label: "Decisions", href: "/decisions", icon: Scale },
  { label: "Calibration", href: "/calibration", icon: BarChart3 },
  { label: "Tasks", href: "/tasks", icon: ClipboardList },
  { label: "Drivers", href: "/drivers", icon: Bot },
  { label: "Activity", href: "/activity", icon: Activity },
];

const BOTTOM = [
  { label: "Settings", href: "/settings", icon: Settings },
];

export function AppSidebar({ wsStatus = "disconnected" }: { wsStatus?: string }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  // Close sidebar on route change (mobile)
  useEffect(() => { setOpen(false); }, [pathname]);

  return (
    <>
      {/* Mobile hamburger */}
      <button
        onClick={() => setOpen(true)}
        className="fixed top-3.5 left-4 z-50 p-2 rounded-lg bg-white border border-zinc-200 shadow-sm lg:hidden"
      >
        <Menu className="w-4 h-4 text-zinc-600" />
      </button>

      {/* Backdrop (mobile) */}
      {open && (
        <div className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40 lg:hidden" onClick={() => setOpen(false)} />
      )}

      {/* Sidebar */}
      <aside className={`fixed lg:relative inset-y-0 left-0 z-50 w-56 h-screen bg-white border-r border-zinc-200 flex flex-col py-4 shrink-0 transition-transform duration-200 ${
        open ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
      }`}>
        <div className="px-5 mb-8 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-100 flex items-center justify-center relative">
              <Brain className="w-4.5 h-4.5 text-emerald-600" />
              <div className={`absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-white ${
                wsStatus === "connected" ? "bg-emerald-400" :
                wsStatus === "connecting" ? "bg-amber-400 animate-pulse" :
                "bg-zinc-300"
              }`} title={`WebSocket: ${wsStatus}`} />
            </div>
            <span className="text-sm font-semibold text-zinc-900 tracking-tight">Life Graph</span>
          </Link>
          <button onClick={() => setOpen(false)} className="p-1 rounded-md hover:bg-zinc-100 lg:hidden">
            <X className="w-4 h-4 text-zinc-400" />
          </button>
        </div>
        <nav className="flex-1 px-3 space-y-0.5">
          {NAV.map(({ label, href, icon: Icon }) => {
            const active = pathname === href || (href !== "/" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-2.5 px-2.5 py-2 rounded-md text-sm transition-colors ${
                  active
                    ? "bg-emerald-50 text-emerald-700 font-medium"
                    : "text-zinc-500 hover:text-zinc-800 hover:bg-zinc-50"
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="px-3 pt-2 border-t border-zinc-100 mt-2">
          {BOTTOM.map(({ label, href, icon: Icon }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-2.5 px-2.5 py-2 rounded-md text-sm transition-colors ${
                  active ? "bg-emerald-50 text-emerald-700" : "text-zinc-500 hover:text-zinc-800 hover:bg-zinc-50"
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                {label}
              </Link>
            );
          })}
        </div>
      </aside>
    </>
  );
}
