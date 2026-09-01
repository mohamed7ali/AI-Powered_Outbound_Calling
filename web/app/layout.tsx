import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "منصة المتابعة الذكية",
  description: "Arabic outbound calls & RAG assistant console",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}