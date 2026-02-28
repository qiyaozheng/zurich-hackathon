import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HAVOC — Document Execution Engine",
  description: "Document-Driven Factory Intelligence",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)] font-[var(--font-mono)]">
        {children}
      </body>
    </html>
  );
}
