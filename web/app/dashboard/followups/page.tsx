export default function FollowupsPage() {
  const followups = [
    { id: "1", subject: "لا يوجد اتصال بالإنترنت", customer: "أحمد علي", scheduled: "اليوم 3:00 م", status: "PENDING", attempt: 1 },
    { id: "2", subject: "بطء في الخدمة", customer: "منى حسن", scheduled: "غدًا 10:00 ص", status: "PENDING", attempt: 2 },
  ];

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold mb-1">المتابعات المجدولة</h1>
          <p className="text-sm opacity-60">مكالمات متابعة تلقائية للتأكد من حل المشكلة</p>
        </div>
        <button className="bg-[var(--color-ink)] text-[var(--color-paper)] px-4 py-2 rounded-md text-sm">
          + جدولة متابعة
        </button>
      </div>

      <div className="flex flex-col gap-3">
        {followups.map((f) => (
          <div key={f.id} className="bg-white rounded-lg border border-black/10 p-4 flex items-center justify-between">
            <div>
              <p className="font-medium">{f.subject}</p>
              <p className="text-sm opacity-60 mt-1">{f.customer} · محاولة رقم {f.attempt}</p>
            </div>
            <div className="text-left">
              <p className="text-sm">{f.scheduled}</p>
              <button className="mt-2 text-xs bg-[var(--color-moss)] text-white px-3 py-1.5 rounded-md">
                ابدأ المكالمة الآن
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}