"use client";

import { useState, useRef } from "react";
import { apiFetch } from "../../apiClient";

type Message = { role: "user" | "assistant"; content: string; citations?: string[] };

export default function AgentDeskPage() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState("");
  const recognitionRef = useRef<any>(null);

  function startRecording() {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setError("المتصفح لا يدعم التسجيل الصوتي — جرّب Chrome أو Edge.");
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = "ar-SA";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      setInput((prev) => (prev ? prev + " " + transcript : transcript));
    };
    recognition.onerror = () => {
      setError("تعذر التعرف على الصوت، حاول مرة أخرى.");
      setRecording(false);
    };
    recognition.onend = () => setRecording(false);

    recognitionRef.current = recognition;
    recognition.start();
    setRecording(true);
    setError("");
  }

  function stopRecording() {
    recognitionRef.current?.stop();
    setRecording(false);
  }

  async function handleSend() {
    if (!input.trim()) return;
    const question = input;
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setInput("");
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch("/agent/query", {
        method: "POST",
        body: JSON.stringify({ question }),
      });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer ?? JSON.stringify(data),
          citations: data.citations?.map((c: any) => c.source ?? c.title ?? "مصدر"),
        },
      ]);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-8 flex flex-col h-screen">
      <h1 className="text-2xl font-semibold mb-1">مساعد المعرفة</h1>
      <p className="text-sm opacity-60 mb-6">اسأل بالكتابة أو بتسجيل ملاحظة صوتية</p>

      <div className="flex-1 bg-white rounded-lg border border-black/10 p-4 mb-4 overflow-y-auto flex flex-col gap-3">
        {messages.length === 0 && <p className="text-sm opacity-40">اكتب سؤالك أو سجّل صوتك بالأسفل...</p>}
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
            {m.citations && m.citations.length > 0 && (
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
        {loading && <p className="text-sm opacity-40">جاري التفكير...</p>}
        {error && <p className="text-sm text-[var(--color-brick)]">{error}</p>}
      </div>

      <div className="flex gap-2 items-center">
        <button
          onClick={recording ? stopRecording : startRecording}
          className={`px-4 py-2 rounded-md text-sm font-medium transition ${
            recording
              ? "bg-[var(--color-brick)] text-white animate-pulse"
              : "bg-[var(--color-moss)] text-white"
          }`}
        >
          {recording ? "⏹ إيقاف" : "🎙 تسجيل"}
        </button>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="اكتب سؤالك أو استخدم التسجيل..."
          className="flex-1 border border-black/15 rounded-md px-3 py-2 bg-white"
        />
        <button onClick={handleSend} className="bg-[var(--color-amber)] text-[var(--color-ink)] px-4 py-2 rounded-md font-medium">
          إرسال
        </button>
      </div>
    </div>
  );
}