import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Instrument_Sans, Anek_Tamil, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { RootShell } from "@/components/root-shell";

// Orbit type roles — display / body / tamil / mono. Self-hosted via next/font (no
// runtime Google Fonts calls); all four are variable fonts, so the full weight range
// is available from a single file and OrbitType's weights (600 display, 500 label,
// 400 body) need no separate downloads.
//
// Bricolage carries the optical-size axis so `font-optical-sizing: auto` can adapt it
// across the 10.5px eyebrow → 31px display span; without opsz it would be frozen at
// its 14px default and look thin at display size.
const bricolage = Bricolage_Grotesque({
  variable: "--font-bricolage",
  subsets: ["latin"],
  axes: ["opsz"],
  display: "swap",
});
const instrument = Instrument_Sans({ variable: "--font-instrument", subsets: ["latin"], display: "swap" });
// Tamil is a first-class body face, not a fallback — it sits in the --font-sans stack
// so mixed Tamil/Latin text (OrbitType.bodyBilingual) renders in one voice.
// preload:false — Anek is a fallback in the --font-sans stack, so on an all-Latin
// page the browser never pulls it. Preloading it shipped an unused Tamil face on
// every route (the browser says so out loud in the console).
const anekTamil = Anek_Tamil({ variable: "--font-anek", subsets: ["latin", "tamil"], display: "swap", preload: false });
// Same for mono: only code blocks and IDs use it, none of them above the fold.
const jetbrainsMono = JetBrains_Mono({ variable: "--font-jetbrains", subsets: ["latin"], display: "swap", preload: false });

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
  themeColor: "#000000",
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
      data-theme="dark"
      data-accent="orbit"
      data-density="comfortable"
      className={`${bricolage.variable} ${instrument.variable} ${anekTamil.variable} ${jetbrainsMono.variable} h-full`}
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
                let refreshing = false;
                navigator.serviceWorker.addEventListener('controllerchange', () => {
                  if (refreshing) return;
                  refreshing = true;
                  window.location.reload();
                });
                window.addEventListener('load', () => {
                  navigator.serviceWorker.register('/sw.js').then((reg) => {
                    reg.addEventListener('updatefound', () => {
                      const nw = reg.installing;
                      if (nw) nw.addEventListener('statechange', () => {
                        // new SW installed while an old one controls the page → it will
                        // skipWaiting + claim, firing controllerchange above → reload.
                      });
                    });
                    // Poll for updates when the tab regains focus.
                    document.addEventListener('visibilitychange', () => {
                      if (document.visibilityState === 'visible') reg.update();
                    });
                  });
                });
              }
            `,
          }}
        />
      </body>
    </html>
  );
}
