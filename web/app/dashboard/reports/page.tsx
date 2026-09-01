export default function ReportsPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold mb-1">تقرير حل المشكلة من أول اتصال</h1>
      <p className="text-sm opacity-60 mb-6">اختر فترة زمنية لإنشاء التقرير</p>

      <div className="bg-white rounded-lg border border-black/10 p-6 max-w-md mb-6">
        <div className="flex gap-3 mb-4">
          <div className="flex-1">
            <label className="text-xs opacity-60 block mb-1">من تاريخ</label>
            <input type="date" className="w-full border border-black/15 rounded-md px-3 py-2" />
          </div>
          <div className="flex-1">
            <label className="text-xs opacity-60 block mb-1">إلى تاريخ</label>
            <input type="date" className="w-full border border-black/15 rounded-md px-3 py-2" />
          </div>
        </div>
        <button className="w-full bg-[var(--color-amber)] text-[var(--color-ink)] py-2 rounded-md font-medium">
          إنشاء التقرير
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4 max-w-2xl">
        <div className="bg-white rounded-lg border border-black/10 p-5">
          <p className="text-xs opacity-60">إجمالي المكالمات</p>
          <p className="text-3xl font-semibold mt-2">—</p>
        </div>
        <div className="bg-white rounded-lg border border-black/10 p-5">
          <p className="text-xs opacity-60">تم الحل من أول اتصال</p>
          <p className="text-3xl font-semibold mt-2">—</p>
        </div>
        <div className="bg-white rounded-lg border border-black/10 p-5">
          <p className="text-xs opacity-60">تم التصعيد</p>
          <p className="text-3xl font-semibold mt-2">—</p>
        </div>
      </div>
    </div>
  );
}