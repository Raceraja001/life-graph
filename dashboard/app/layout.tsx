import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { RootShell } from "@/components/root-shell";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "Life Graph — Personal AI Operating System",
    template: "%s | Life Graph",
  },
  description: "Your personal AI operating system. Memory, judgment, and autonomous agents in one self-hosted system.",
  manifest: "/manifest.json",
  keywords: ["personal AI", "memory graph", "self-hosted AI", "life OS", "knowledge management"],
  authors: [{ name: "Life Graph" }],
  robots: "noindex, nofollow", // self-hosted — don't index
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Life Graph",
  },
  openGraph: {
    type: "website",
    title: "Life Graph",
    description: "Personal AI Operating System",
    siteName: "Life Graph",
  },
};

export const viewport: Viewport = {
  themeColor: "#059669",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} h-full`}>
      <head>
        <link rel="apple-touch-icon" href="/icons/icon-192.png" />
      </head>
      <body className="min-h-full bg-[#fafafa] text-zinc-900 font-[family-name:var(--font-inter)] antialiased">
        <RootShell>{children}</RootShell>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              if ('serviceWorker' in navigator) {
                window.addEventListener('load', () => {
                  navigator.serviceWorker.register('/sw.js');
                });
              }
            `,
          }}
        />
      </body>
    </html>
  );
}
