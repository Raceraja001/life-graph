import type { Metadata } from "next";
import { MobileShell } from "@/components/mobile/mobile-shell";
import { MobileStateProvider } from "@/components/mobile/mobile-state";

export const metadata: Metadata = {
  title: "Life Graph Mobile",
};

export default function MobileLayout({ children }: { children: React.ReactNode }) {
  return (
    <MobileStateProvider>
      <MobileShell>{children}</MobileShell>
    </MobileStateProvider>
  );
}
