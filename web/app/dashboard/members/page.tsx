export default function MembersPage() {
  const members = [
    { id: "1", name: "أحمد سالم", role: "ORG_ADMIN", active: true },
    { id: "2", name: "منى فتحي", role: "AGENT", active: true },
  ];

  const roleLabel: Record<string, string> = { ORG_ADMIN: "مدير المؤسسة", AGENT: "وكيل" };

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold mb-1">أعضاء المؤسسة</h1>
          <p className="text-sm opacity-60">إدارة الوكلاء والمشرفين</p>
        </div>
        <button className="bg-[var(--color-ink)] text-[var(--color-paper)] px-4 py-2 rounded-md text-sm">
          + دعوة عضو
        </button>
      </div>

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
            {members.map((m) => (
              <tr key={m.id} className="border-t border-black/5">
                <td className="p-3">{m.name}</td>
                <td className="p-3">{roleLabel[m.role]}</td>
                <td className="p-3">
                  <span className="text-xs bg-[var(--color-moss)]/15 text-[var(--color-moss)] px-2 py-0.5 rounded">نشط</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}