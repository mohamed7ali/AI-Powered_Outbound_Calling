"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../apiClient";

type Case = {
  id: string;
  subject: string;
  status: string;
  customer_name: string;
  updated_at: string;
};

export default function CasesPage() {
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function fetchCases() {
      try {
        const data = await apiFetch("/campaign/cases");
        setCases(data || []);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    fetchCases();
  }, []);

  const statusLabel: Record<string, string> = {
    OPEN: "مفتوحة",
    IN_PROGRESS: "قيد المعالجة",
  };

  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold mb-1">الحالات المفتوحة</h1>
      <p className="text-sm opacity-60 mb-6">الحالات النشطة في مؤسستك</p>

      {loading && <p className="text-sm opacity-60">جاري التحميل...</p>}
      {error && <p className="text-sm text-[var(--color-brick)]">{error}</p>}

      {!loading && !error && (
        <div className="bg-white rounded-lg border border-black/10 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-black/5 text-right">
              <tr>
                <th className="p-3 font-medium">الموضوع</th>
                <th className="p-3 font-medium">العميل</th>
                <th className="p-3 font-medium">الحالة</th>
                <th className="p-3 font-medium">آخر تحديث</th>
              </tr>
            </thead>
            <tbody>
              {cases.length === 0 && (
                <tr>
                  <td colSpan={4} className="p-6 text-center opacity-40">
                    لا توجد حالات مفتوحة.
                  </td>
                </tr>
              )}
              {cases.map((c) => (
                <tr key={c.id} className="border-t border-black/5">
                  <td className="p-3">{c.subject}</td>
                  <td className="p-3">{c.customer_name}</td>
                  <td className="p-3">
                    <span className="inline-block px-2 py-0.5 rounded text-xs bg-[var(--color-amber)]/20 text-[var(--color-amber)]">
                      {statusLabel[c.status] ?? c.status}
                    </span>
                  </td>
                  <td className="p-3 opacity-60">{new Date(c.updated_at).toLocaleDateString("ar")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}