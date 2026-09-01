export default function DocumentsPage() {
  const docs = [
    { id: "1", title: "دليل_استكشاف_الأعطال.pdf", status: "READY", updated: "منذ يومين" },
    { id: "2", title: "سياسة_الفواتير.docx", status: "READY", updated: "الأسبوع الماضي" },
  ];

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold mb-1">مستندات قاعدة المعرفة</h1>
          <p className="text-sm opacity-60">PDF, DOCX, TXT, MD, CSV, JSON — حتى 25 ميجابايت</p>
        </div>
        <button className="bg-[var(--color-ink)] text-[var(--color-paper)] px-4 py-2 rounded-md text-sm">
          + رفع مستند
        </button>
      </div>

      <div className="flex flex-col gap-2">
        {docs.map((d) => (
          <div key={d.id} className="bg-white rounded-lg border border-black/10 p-4 flex items-center justify-between">
            <p className="text-sm font-medium">{d.title}</p>
            <div className="flex items-center gap-3">
              <span className="text-xs bg-[var(--color-moss)]/15 text-[var(--color-moss)] px-2 py-0.5 rounded">جاهز</span>
              <span className="text-xs opacity-50">{d.updated}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}