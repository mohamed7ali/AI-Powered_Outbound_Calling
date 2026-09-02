"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../supabaseClient";

type Membership = { id: string; name: string; slug: string; role: string };

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [selectedOrgId, setSelectedOrgId] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    async function loadSession() {
      const { data: sessionData } = await supabase.auth.getSession();
      const token = sessionData.session?.access_token;
      if (!token) {
        router.push("/login");
        return;
      }
      const res = await fetch("http://localhost:8000/auth/session", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        router.push("/login");
        return;
      }
      const data = await res.json();
      setMemberships(data.memberships || []);
      if (data.memberships?.length > 0) {
        const saved = localStorage.getItem("selected_org_id");
        const validSaved = data.memberships.find((m: Membership) => m.id === saved);
        setSelectedOrgId(validSaved ? saved! : data.memberships[0].id);
      }
      setLoading(false);
    }
    loadSession();
  }, [router]);

  function handleOrgChange(orgId: string) {
    setSelectedOrgId(orgId);
    localStorage.setItem("selected_org_id", orgId);
  }

  async function handleLogout() {
    await supabase.auth.signOut();
    router.push("/login");
  }

  const links = [
    { href: "/dashboard", label: "الحالات" },
    { href: "/dashboard/followups", label: "المتابعات" },
    { href: "/dashboard/agent-desk", label: "مساعد المعرفة" },
    { href: "/dashboard/documents", label: "المستندات" },
    { href: "/dashboard/reports", label: "التقارير" },
    { href: "/dashboard/members", label: "الأعضاء" },
  ];

  if (loading) return null;

  return (
    <div className="min-h-screen flex">
      <nav className="w-60 bg-[var(--color-ink)] text-[var(--color-paper)] flex flex-col p-5 gap-1">
        <div className="mb-6">
          <p className="text-xs opacity-60 mb-1">المؤسسة الحالية</p>
          {memberships.length > 1 ? (
            <select
              value={selectedOrgId}
              onChange={(e) => handleOrgChange(e.target.value)}
              className="w-full bg-white/10 text-sm rounded-md px-2 py-1.5"
            >
              {memberships.map((m) => (
                <option key={m.id} value={m.id} className="text-black">
                  {m.name}
                </option>
              ))}
            </select>
          ) : (
            <p className="text-sm font-medium">{memberships[0]?.name ?? "—"}</p>
          )}
        </div>
        {links.map((link) => (
          <Link key={link.href} href={link.href} className="px-3 py-2 rounded-md text-sm hover:bg-white/10 transition">
            {link.label}
          </Link>
        ))}
        <button onClick={handleLogout} className="mt-auto text-xs opacity-60 text-right hover:opacity-100">
          تسجيل الخروج
        </button>
      </nav>
      <div className="flex-1 bg-[var(--color-paper)]">{children}</div>
    </div>
  );
}