"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../../apiClient";

type Member = {
  user_id: string;
  full_name: string | null;
  phone: string | null;
  role: string;
  is_active: boolean;
};

export default function MembersPage() {
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function fetchMembers() {
      try {
        const orgId = localStorage.getItem("selected_org_id");
        const data = await apiFetch(`/admin/${orgId}/members`);
        setMembers(data || []);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    fetchMembers();
  }, []);

  const roleLabel: Record<string, string> = { ORG_ADMIN: "مدير المؤسسة", AGENT: "وكيل" };

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold mb-1">أعضاء المؤسسة</h1>
          <p className="text-sm opacity-60">إدارة الوكلاء والمشرفين</p>
        </div>
      </div>

      {loading && <p className="text-sm opacity-60">جاري التحميل...</p>}
      {error && <p className="text-sm text-[var(--color-brick)]">{error}</p>}

      {!loading && !error && (
        <div className="bg-white rounded-lg border border-black/10 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-black/5 text-right">
              <tr>
                <th className="p-3 font-medium">الاسم</th>
                <th className="p-3 font-medium">الدور</th>
                <th className="p-3 font-medium">الحالة</th>
              </tr>
            </thead>
            <tbody>
              {members.length === 0 && (
                <tr>
                  <td colSpan={3} className="p-6 text-center opacity-40">
                    لا يوجد أعضاء.
                  </td>
                </tr>
              )}
              {members.map((m) => (
                <tr key={m.user_id} className="border-t border-black/5">
                  <td className="p-3">{m.full_name ?? "—"}</td>
                  <td className="p-3">{roleLabel[m.role] ?? m.role}</td>
                  <td className="p-3">
                    <span className={`text-xs px-2 py-0.5 rounded ${m.is_active ? "bg-[var(--color-moss)]/15 text-[var(--color-moss)]" : "bg-black/10 opacity-60"}`}>
                      {m.is_active ? "نشط" : "غير نشط"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}