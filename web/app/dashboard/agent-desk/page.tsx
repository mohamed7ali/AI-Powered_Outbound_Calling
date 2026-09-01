"use client";

import { useState } from "react";

type Message = { role: "user" | "assistant"; content: string; citations?: string[] };

export default function AgentDeskPage() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);

  function handleSend() {
    if (!input.trim()) return;
    setMessages((prev) => [
      ...prev,
      { role: "user", content: input },
      {
        role: "assistant",
        content: "سيتم ربط هذا الرد ببيانات حقيقية بعد توصيل الخادم.",
        citations: ["دليل_المستخدم.pdf"],
      },
    ]);
    setInput("");
  }

  return (
    <div className="p-8 flex flex-col h-screen">
      <h1 className="text-2xl font-semibold mb-1">مساعد المعرفة</h1>
      <p className="text-sm opacity-60 mb-6">اسأل عن أي شيء من مستندات المؤسسة</p>

      <div className="flex-1 bg-white rounded-lg border border-black/10 p-4 mb-4 overflow-y-auto flex flex-col gap-3">
        {messages.length === 0 && (
          <p className="text-sm opacity-40">اكتب سؤالك بالأسفل...</p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`max-w-[75%] p-3 rounded-lg text-sm ${
              m.role === "user"
                ? "self-end bg-[var(--color-ink)] text-[var(--color-paper)]"
                : "self-start bg-black/5"
            }`}
          >
            <p>{m.content}</p>
            {m.citations && (
              <div className="mt-2 flex gap-1 flex-wrap">
                {m.citations.map((c, ci) => (
                  <span key={ci} className="text-xs bg-[var(--color-amber)]/20 text-[var(--color-amber)] px-2 py-0.5 rounded">
                    {c}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="اكتب سؤالك..."
          className="flex-1 border border-black/15 rounded-md px-3 py-2 bg-white"
        />
        <button onClick={handleSend} className="bg-[var(--color-amber)] text-[var(--color-ink)] px-4 py-2 rounded-md font-medium">
          إرسال
        </button>
      </div>
    </div>
  );
}