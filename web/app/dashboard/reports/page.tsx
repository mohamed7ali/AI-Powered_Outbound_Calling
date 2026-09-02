"use client";

import { useState } from "react";
import { apiFetch } from "../../apiClient";

type FcrReport = {
  total_calls: number;
  resolved_on_first_follow_up: number;
  escalated_calls: number;
  answer_rate: number;
  fcr_rate: number;
  average_duration_seconds: number;
  report_text: string;
  headline: string;
  recommendations: string[];
};

export default function ReportsPage() {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [report, setReport] = useState<FcrReport | null>(null);

  async function handleGenerate() {
    if (!start || !end) return;
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch("/reports/fcr", {
        method: "POST",
        body: JSON.stringify({ period_start: start, period_end: end }),
      });
      setReport(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold mb-1">تقرير حل المشكلة من أول اتصال</h1>
      <p className="text-sm opacity-60 mb-6">اختر فترة زمنية لإنشاء التقرير</p>

      <div className="bg-white rounded-lg border border-black/10 p-6 max-w-md mb-6">
        <div className="flex gap-3 mb-4">
          <div className="flex-1">
            <label className="text-xs opacity-60 block mb-1">من تاريخ</label>
            <input
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="w-full border border-black/15 rounded-md px-3 py-2"
            />
          </div>
          <div className="flex-1">
            <label className="text-xs opacity-60 block mb-1">إلى تاريخ</label>
            <input
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              className="w-full border border-black/15 rounded-md px-3 py-2"
            />
          </div>
        </div>
        {error && <p className="text-sm text-[var(--color-brick)] mb-3">{error}</p>}
        <button
          onClick={handleGenerate}
          disabled={loading || !start || !end}
          className="w-full bg-[var(--color-amber)] text-[var(--color-ink)] py-2 rounded-md font-medium disabled:opacity-50"
        >
          {loading ? "جاري الإنشاء..." : "إنشاء التقرير"}
        </button>
      </div>

      {report && (
        <div className="max-w-2xl flex flex-col gap-4">
          <div className="bg-[var(--color-ink)] text-[var(--color-paper)] rounded-lg p-5">
            <p className="text-sm opacity-70 mb-1">{report.headline}</p>
            <p className="text-sm leading-relaxed">{report.report_text}</p>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="bg-white rounded-lg border border-black/10 p-4">
              <p className="text-xs opacity-60">إجمالي المكالمات</p>
              <p className="text-2xl font-semibold mt-1">{report.total_calls}</p>
            </div>
            <div className="bg-white rounded-lg border border-black/10 p-4">
              <p className="text-xs opacity-60">نسبة الحل من أول اتصال</p>
              <p className="text-2xl font-semibold mt-1">{(report.fcr_rate * 100).toFixed(0)}%</p>
            </div>
            <div className="bg-white rounded-lg border border-black/10 p-4">
              <p className="text-xs opacity-60">المكالمات المصعدة</p>
              <p className="text-2xl font-semibold mt-1">{report.escalated_calls}</p>
            </div>
          </div>

          {report.recommendations?.length > 0 && (
            <div className="bg-white rounded-lg border border-black/10 p-5">
              <p className="text-sm font-medium mb-3">توصيات</p>
              <ul className="flex flex-col gap-2">
                {report.recommendations.map((r, i) => (
                  <li key={i} className="text-sm opacity-80 flex gap-2">
                    <span className="text-[var(--color-amber)]">•</span>
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}