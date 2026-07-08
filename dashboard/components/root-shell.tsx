"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { Providers } from "@/lib/providers";
import { AppSidebar } from "@/components/app-sidebar";
import { AppTopbar } from "@/components/app-topbar";
import { ChatBar } from "@/components/chat-bar";
import { CommandPalette } from "@/components/command-palette";

const STANDALONE_ROUTES = ["/login"];

export function RootShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [commandOpen, setCommandOpen] = useState(false);

  // Standalone pages (login) render without the shell
  if (STANDALONE_ROUTES.includes(pathname)) {
    return <Providers>{children}</Providers>;
  }

  return (
    <Providers>
      <div className="flex h-screen overflow-hidden">
        <AppSidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <AppTopbar onOpenCommand={() => setCommandOpen(true)} />
          <main className="flex-1 overflow-y-auto p-6">{children}</main>
          <ChatBar />
        </div>
      </div>
      <CommandPalette
        open={commandOpen}
        onOpenChange={setCommandOpen}
      />
    </Providers>
  );
}
