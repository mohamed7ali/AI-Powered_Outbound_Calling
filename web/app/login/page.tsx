"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../supabaseClient";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setLoading(false);
    if (error) {
      setError(error.message);
    } else {
      router.push("/dashboard");
    }
  }

  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      <div className="md:w-2/5 bg-[var(--color-ink)] text-[var(--color-paper)] flex flex-col justify-between p-10">
        <div>
          <p className="text-sm tracking-wide opacity-70">منصة المتابعة الذكية</p>
          <h1 className="text-3xl font-semibold mt-4 leading-relaxed">
            متابعة العملاء ومساعد المعرفة، في مكان واحد
          </h1>
        </div>
        <p className="text-sm opacity-60 leading-relaxed">
          نظام متابعة المكالمات الصادرة ومساعد الذكاء الاصطناعي للوكلاء
        </p>
      </div>

      <div className="flex-1 flex items-center justify-center p-8">
        <form onSubmit={handleSubmit} className="w-full max-w-sm flex flex-col gap-4">
          <h2 className="text-2xl font-semibold mb-2">تسجيل الدخول</h2>

          <div className="flex flex-col gap-1">
            <label className="text-sm opacity-70">البريد الإلكتروني</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="border border-black/15 rounded-md px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-[var(--color-amber)]"
              required
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-sm opacity-70">كلمة المرور</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="border border-black/15 rounded-md px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-[var(--color-amber)]"
              required
            />
          </div>

          {error && <p className="text-sm text-[var(--color-brick)]">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="mt-2 bg-[var(--color-amber)] text-[var(--color-ink)] font-medium rounded-md py-2 hover:opacity-90 transition disabled:opacity-50"
          >
            {loading ? "جاري الدخول..." : "دخول"}
          </button>
        </form>
      </div>
    </div>
  );
}