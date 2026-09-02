"use client";

import { useEffect, useState } from "react";
import { supabase } from "../../supabaseClient";

const API_BASE = "http://localhost:8000";

type Doc = { id: string; title: string; status: string; created_at: string };

export default function DocumentsPage() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [file, setFile] = useState<File | null>(null);

  async function loadDocs() {
    setLoading(true);
    try {
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      const orgId = localStorage.getItem("selected_org_id");
      const res = await fetch(`${API_BASE}/documents`, {
        headers: { Authorization: `Bearer ${token}`, "X-Organization-Id": orgId ?? "" },
      });
      if (!res.ok) throw new Error(await res.text());
      setDocs(await res.json());
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDocs();
  }, []);

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      const orgId = localStorage.getItem("selected_org_id");
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_BASE}/documents/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "X-Organization-Id": orgId ?? "" },
        body: formData,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "فشل الرفع");
      }
      setFile(null);
      await loadDocs();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold mb-1">مستندات قاعدة المعرفة</h1>
          <p className="text-sm opacity-60">PDF, DOCX, TXT, MD, CSV, JSON — حتى 25 ميجابايت</p>
        </div>

        <div className="flex flex-col gap-2 items-end">
          <label className="text-sm text-[var(--color-ink)] cursor-pointer">
            <span className="opacity-70">• اختر ملفًا</span>
            <input
              type="file"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="hidden"
            />
          </label>
          {file && (
            <p className="text-xs text-[var(--color-moss)]">تم اختيار: {file.name}</p>
          )}
          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="bg-[var(--color-ink)] text-[var(--color-paper)] px-4 py-2 rounded-md text-sm disabled:opacity-50"
          >
            {uploading ? "جاري الرفع..." : "+ رفع مستند"}
          </button>
        </div>
      </div>

      {error && <p className="text-sm text-[var(--color-brick)] mb-4">{error}</p>}
      {loading && <p className="text-sm opacity-60">جاري التحميل...</p>}
      {!loading && docs.length === 0 && !error && (
        <p className="text-sm opacity-40">لا توجد مستندات بعد.</p>
      )}

      <div className="flex flex-col gap-2">
        {docs.map((d) => (
          <div key={d.id} className="bg-white rounded-lg border border-black/10 p-4 flex items-center justify-between">
            <p className="text-sm font-medium">{d.title}</p>
            <div className="flex items-center gap-3">
              <span className="text-xs bg-[var(--color-moss)]/15 text-[var(--color-moss)] px-2 py-0.5 rounded">
                {d.status === "READY" ? "جاهز" : d.status}
              </span>
              <span className="text-xs opacity-50">{new Date(d.created_at).toLocaleDateString("ar")}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}