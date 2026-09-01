export default function CasesPage() {
  const cases = [
    { id: "1", subject: "لا يوجد اتصال بالإنترنت", customer: "أحمد علي", status: "OPEN", updated: "منذ ساعتين" },
    { id: "2", subject: "مشكلة في الفاتورة", customer: "سارة محمد", status: "IN_PROGRESS", updated: "أمس" },
  ];

  const statusLabel: Record<string, string> = {
    OPEN: "مفتوحة",
    IN_PROGRESS: "قيد المعالجة",
  };

  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold mb-1">الحالات المفتوحة</h1>
      <p className="text-sm opacity-60 mb-6">الحالات النشطة في مؤسستك</p>

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
            {cases.map((c) => (
              <tr key={c.id} className="border-t border-black/5">
                <td className="p-3">{c.subject}</td>
                <td className="p-3">{c.customer}</td>
                <td className="p-3">
                  <span className="inline-block px-2 py-0.5 rounded text-xs bg-[var(--color-amber)]/20 text-[var(--color-amber)]">
                    {statusLabel[c.status]}
                  </span>
                </td>
                <td className="p-3 opacity-60">{c.updated}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}