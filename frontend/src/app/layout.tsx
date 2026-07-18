import type { Metadata, Viewport } from "next";
import { Toaster } from "sonner";
import "./globals.css";

export const metadata: Metadata = {
  title: "SmartCycle · 金仕达·智循 — Advisor Copilot",
  description:
    "AI-Native Financial Intelligence & Wealth Management Platform — B2B2C multi-agent system for advisors and investors.",
  keywords: [
    "fintech", "AI", "wealth management", "financial advisor",
    "LangGraph", "RAG", "compliance", "SmartCycle", "金仕达",
  ],
};

export const viewport: Viewport = {
  themeColor: "#06060c",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className="dark" suppressHydrationWarning>
      <head>
        {/* Preload Inter + JetBrains Mono for instant rendering */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&family=Noto+Sans+SC:wght@300;400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen bg-[#06060c] font-sans antialiased">
        {children}
        <Toaster
          richColors
          position="top-right"
          toastOptions={{
            style: {
              background: "#141428",
              color: "#e2e8f0",
              border: "1px solid #1e2948",
            },
          }}
        />
      </body>
    </html>
  );
}
