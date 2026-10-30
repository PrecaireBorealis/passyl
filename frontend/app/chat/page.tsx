"use client";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import ActionLive from "@/components/ActionLive";
import MicButton from "@/components/MicButton";
import ResultCard from "@/components/ResultCard";
import StrategyCard from "@/components/StrategyCard";
import WhyCard from "@/components/WhyCard";
import { api } from "@/lib/api";
import { useApp } from "@/lib/state";
import type { AgentResponse, Card } from "@/lib/types";

function speakBrowser(text: string) {
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "hi-IN";
  const v = speechSynthesis.getVoices().find((x) => x.lang.startsWith("hi"));
  if (v) u.voice = v;
  speechSynthesis.cancel();
  speechSynthesis.speak(u);
}

function play(b64: string) {
  new Audio(`data:audio/wav;base64,${b64}`).play().catch(() => {});
}

export default function Chat() {
  const app = useApp();
  const q = useSearchParams();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const asked = useRef(false);

  const handle = (said: string, r: AgentResponse, voice: boolean) => {
    app.setMessages((m) => [...m, { from: "bot", text: r.reply_text, resp: r }]);
    app.pushTrace(said, r.trace);
    const live = r.cards.find((c) => c.type === "action_live");
    if (live) app.setLiveActionId((live.data as { id: string }).id);
    if (r.intent === "UNDO") app.setLiveActionId(null);
    if (voice) r.audio_b64 ? play(r.audio_b64) : speakBrowser(r.reply_text);
  };

  const say = async (t: string, voice = false) => {
    if (!t.trim() || busy) return;
    setText("");
    setBusy(true);
    app.setMessages((m) => [...m, { from: "me", text: t }]);
    try {
      handle(t, await api.message(app.merchant, t, voice ? "voice" : "chat"), voice);
    } catch (e) {
      app.setMessages((m) => [...m, { from: "bot", text: `Error: ${(e as Error).message}` }]);
    }
    setBusy(false);
  };

  const sayAudio = async (b: Blob): Promise<boolean> => {
    setBusy(true);
    try {
      const v = await api.voice(app.merchant, b);
      if (!v.response) { setBusy(false); return false; }
      app.setMessages((m) => [...m, { from: "me", text: v.transcript }]);
      handle(v.transcript, v.response, true);
      setBusy(false);
      return true;
    } catch {
      setBusy(false);
      return false;
    }
  };

  useEffect(() => {
    const pre = q.get("q");
    if (pre && !asked.current) { asked.current = true; say(pre); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [app.messages, busy]);

  const render = (c: Card, i: number, last: boolean) => {
    switch (c.type) {
      case "why_card": return <WhyCard key={i} card={c.data} />;
      case "strategy_card": return <StrategyCard key={i} data={c.data} onSay={last ? (t) => say(t) : undefined} />;
      case "action_live": return <ActionLive key={i} data={c.data} onSay={last ? (t) => say(t) : undefined} />;
      case "result_card": return <ResultCard key={i} m={c.data} />;
      case "brief_card": return c.data.last_action_result ? <ResultCard key={i} m={c.data.last_action_result} /> : null;
      default: return null;
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {app.messages.length === 0 && (
          <div className="text-xs text-gray-400 space-y-2 pt-6 text-center">
            <div>Mic daba ke boliye, ya likhiye.</div>
            {["Aaj sales kam kyun hai?", "Kya karun?"].map((s) => (
              <button key={s} onClick={() => say(s)} className="block mx-auto border rounded-full px-3 py-1 text-gray-600">{s}</button>
            ))}
          </div>
        )}
        {app.messages.map((m, i) => {
          const last = i === app.messages.length - 1;
          return m.from === "me" ? (
            <div key={i} className="flex justify-end"><div className="bg-act text-white text-sm rounded-2xl rounded-br-sm px-3 py-2 max-w-[80%]">{m.text}</div></div>
          ) : (
            <div key={i} className="space-y-2">
              <div className="bg-gray-100 text-sm rounded-2xl rounded-bl-sm px-3 py-2 max-w-[90%]">{m.text}</div>
              {m.resp?.cards.map((c, j) => render(c, j, last))}
            </div>
          );
        })}
        {busy && <div className="text-xs text-gray-400">VyaparSaathi soch raha hai…</div>}
        <div ref={end} />
      </div>
      <form className="border-t p-2 flex gap-2 items-center" onSubmit={(e) => { e.preventDefault(); say(text); }}>
        <MicButton offline={app.offline} onAudio={sayAudio} onText={(t) => say(t, true)} />
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Likhiye…" className="flex-1 border rounded-full px-3 py-2 text-sm outline-none focus:border-act" />
        <button disabled={busy} className="text-act font-semibold text-sm px-2">Bhejo</button>
      </form>
    </div>
  );
}
