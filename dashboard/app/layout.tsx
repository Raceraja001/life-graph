import type { Metadata, Viewport } from "next";
import { Sora, Plus_Jakarta_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { RootShell } from "@/components/root-shell";

// uzhavu type roles — display / body / mono. Self-hosted via next/font (no
// runtime Google Fonts calls); variable fonts, so the full weight range is available.
const sora = Sora({ variable: "--font-sora", subsets: ["latin"], display: "swap" });
const jakarta = Plus_Jakarta_Sans({ variable: "--font-jakarta", subsets: ["latin"], display: "swap" });
const jetbrainsMono = JetBrains_Mono({ variable: "--font-jetbrains", subsets: ["latin"], display: "swap" });

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
  themeColor: "#0e8a4d",
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
    <html
      lang="en"
      data-theme="light"
      data-accent="emerald"
      data-density="comfortable"
      className={`${sora.variable} ${jakarta.variable} ${jetbrainsMono.variable} h-full`}
    >
      <head>
        <link rel="apple-touch-icon" href="/icons/icon-192.png" />
      </head>
      <body className="min-h-full antialiased">
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
