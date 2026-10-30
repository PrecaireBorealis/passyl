"use client";
import { useRef, useState } from "react";

type SR = { lang: string; interimResults: boolean; onresult: (e: { results: { 0: { transcript: string } }[] }) => void;
            onerror: () => void; onend: () => void; start: () => void; stop: () => void };

/** Push-to-talk. Records with MediaRecorder for Sarvam; if offline (or Sarvam fails) uses the browser's speech recognition. */
export default function MicButton({ offline, onAudio, onText }: {
  offline: boolean; onAudio: (b: Blob) => Promise<boolean>; onText: (t: string) => void;
}) {
  const [state, setState] = useState<"idle" | "rec" | "busy">("idle");
  const rec = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const sr = useRef<SR | null>(null);

  const browserListen = () => {
    const W = window as unknown as { webkitSpeechRecognition?: new () => SR; SpeechRecognition?: new () => SR };
    const C = W.SpeechRecognition ?? W.webkitSpeechRecognition;
    if (!C) { alert("Is browser mein speech recognition nahi hai. Type karein."); setState("idle"); return; }
    const r = new C();
    r.lang = "hi-IN";
    r.interimResults = false;
    r.onresult = (e) => onText(e.results[0][0].transcript);
    r.onerror = () => setState("idle");
    r.onend = () => setState("idle");
    sr.current = r;
    r.start();
    setState("rec");
  };

  const start = async () => {
    if (offline) return browserListen();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunks.current = [];
      mr.ondataavailable = (e) => chunks.current.push(e.data);
      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setState("busy");
        const ok = await onAudio(new Blob(chunks.current, { type: mr.mimeType }));
        setState("idle");
        if (!ok) browserListen(); // Sarvam unavailable → ask again with browser speech
      };
      rec.current = mr;
      mr.start();
      setState("rec");
    } catch {
      browserListen();
    }
  };
  const stop = () => {
    if (rec.current?.state === "recording") rec.current.stop();
    sr.current?.stop();
  };

  return (
    <button
      onPointerDown={state === "idle" ? start : undefined}
      onPointerUp={state === "rec" ? stop : undefined}
      className={`w-11 h-11 rounded-full flex items-center justify-center text-white shrink-0 ${state === "rec" ? "bg-drop animate-pulse" : state === "busy" ? "bg-gray-400" : "bg-act"}`}
      title="Daba ke boliye"
      aria-label="Push to talk"
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2Z" /></svg>
    </button>
  );
}
