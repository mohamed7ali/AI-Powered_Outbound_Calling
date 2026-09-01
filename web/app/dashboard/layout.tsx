"use client";

import Link from "next/link";
import { useState } from "react";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [org] = useState("جاري التحديد..."); // placeholder until Supabase wired

  const links = [
    { href: "/dashboard", label: "الحالات" },
    { href: "/dashboard/followups", label: "المتابعات" },
    { href: "/dashboard/agent-desk", label: "مساعد المعرفة" },
    { href: "/dashboard/documents", label: "المستندات" },
    { href: "/dashboard/reports", label: "التقارير" },
    { href: "/dashboard/members", label: "الأعضاء" },
  ];

  return (
    <div className="min-h-screen flex">
      <nav className="w-60 bg-[var(--color-ink)] text-[var(--color-paper)] flex flex-col p-5 gap-1">
        <div className="mb-6">
          <p className="text-xs opacity-60">المؤسسة الحالية</p>
          <p className="text-sm font-medium mt-1">{org}</p>
        </div>
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="px-3 py-2 rounded-md text-sm hover:bg-white/10 transition"
          >
            {link.label}
          </Link>
        ))}
      </nav>
      <div className="flex-1 bg-[var(--color-paper)]">{children}</div>
    </div>
  );
}