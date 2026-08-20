import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SilentSpeak Lab",
  description: "Analyze visible speech in English video.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-bg text-[#e6edf3] antialiased">{children}</body>
    </html>
  );
}
