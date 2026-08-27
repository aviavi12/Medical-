import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LipSight",
  description: "Open-vocabulary English visual speech recognition — analyze visible speech in video.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-bg text-[#e6edf3] antialiased">{children}</body>
    </html>
  );
}
