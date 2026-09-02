"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../../apiClient";

type Followup = {
  id: string;
  subject: string;
  customer_name: string;
  scheduled_for: string;
  status: string;
  attempt_number: number;
};

export default function FollowupsPage() {
  const [followups, setFollowups] = useState<Followup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function fetchFollowups() {
      try {
        const data = await apiFetch("/campaign/followups");
        setFollowups(data || []);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    fetchFollowups();
  }, []);

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold mb-1">المتابعات المجدولة</h1>
          <p className="text-sm opacity-60">مكالمات متابعة تلقائية للتأكد من حل المشكلة</p>
        </div>
      </div>

      {loading && <p className="text-sm opacity-60">جاري التحميل...</p>}
      {error && <p className="text-sm text-[var(--color-brick)]">{error}</p>}
      {!loading && !error && followups.length === 0 && (
        <p className="text-sm opacity-40">لا توجد متابعات مجدولة.</p>
      )}

      <div className="flex flex-col gap-3">
        {followups.map((f) => (
          <div key={f.id} className="bg-white rounded-lg border border-black/10 p-4 flex items-center justify-between">
            <div>
              <p className="font-medium">{f.subject}</p>
              <p className="text-sm opacity-60 mt-1">{f.customer_name} · محاولة رقم {f.attempt_number}</p>
            </div>
            <div className="text-left">
              <p className="text-sm">{new Date(f.scheduled_for).toLocaleString("ar")}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}