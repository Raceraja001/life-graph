"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { Providers } from "@/lib/providers";
import { AppSidebar } from "@/components/app-sidebar";
import { AppTopbar } from "@/components/app-topbar";
import { ChatBar } from "@/components/chat-bar";
import { CommandPalette } from "@/components/command-palette";
import { useWebSocket } from "@/lib/use-websocket";

const STANDALONE_ROUTES = ["/login"];

function AppShell({ children }: { children: React.ReactNode }) {
  const [commandOpen, setCommandOpen] = useState(false);
  const status = useWebSocket();

  return (
    <>
      <div className="flex h-screen overflow-hidden">
        <AppSidebar wsStatus={status} />
        <div className="flex-1 flex flex-col min-w-0">
          <AppTopbar onOpenCommand={() => setCommandOpen(true)} />
          <main className="flex-1 overflow-y-auto p-6">{children}</main>
          <ChatBar />
        </div>
      </div>
      <CommandPalette open={commandOpen} onOpenChange={setCommandOpen} />
    </>
  );
}

export function RootShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  if (STANDALONE_ROUTES.includes(pathname)) {
    return <Providers>{children}</Providers>;
  }

  return (
    <Providers>
      <AppShell>{children}</AppShell>
    </Providers>
  );
}
