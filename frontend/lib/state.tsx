"use client";
import { createContext, useContext, useEffect, useState } from "react";
import type { AgentResponse, TraceItem } from "./types";

export const DEMO_MERCHANTS = [
  { id: "M_KOR_RES_001", name: "Raju Family Restaurant" },
  { id: "M_KOR_CAF_NEW", name: "Nayi Dukaan Café" },
];

export type Msg = { from: "me" | "bot"; text: string; resp?: AgentResponse; spokenVia?: string };

type S = {
  merchant: string; setMerchant: (m: string) => void;
  trace: { turn: string; items: TraceItem[] }[]; pushTrace: (turn: string, items: TraceItem[]) => void; clearTrace: () => void;
  messages: Msg[]; setMessages: (f: (m: Msg[]) => Msg[]) => void;
  offline: boolean; setOffline: (b: boolean) => void;
  liveActionId: string | null; setLiveActionId: (s: string | null) => void;
};
const Ctx = createContext<S | null>(null);

export function AppState({ children }: { children: React.ReactNode }) {
  const [merchant, setM] = useState(DEMO_MERCHANTS[0].id);
  const [trace, setTrace] = useState<S["trace"]>([]);
  const [messages, setMsgs] = useState<Msg[]>([]);
  const [offline, setOffline] = useState(false);
  const [liveActionId, setLive] = useState<string | null>(null);
  useEffect(() => {
    const m = localStorage.getItem("vs_merchant");
    if (m) setM(m);
    setLive(localStorage.getItem("vs_live"));
    // no Sarvam key (or backend offline) → push-to-talk goes straight to the browser's speech
    import("./api").then(({ api }) => api.health().then((h) => { if (!h.sarvam) setOffline(true); }).catch(() => setOffline(true)));
  }, []);
  const v: S = {
    merchant,
    setMerchant: (m) => { setM(m); localStorage.setItem("vs_merchant", m); setMsgs(() => []); setTrace([]); },
    trace, pushTrace: (turn, items) => setTrace((t) => [...t, { turn, items }]), clearTrace: () => setTrace([]),
    messages, setMessages: (f) => setMsgs(f),
    offline, setOffline,
    liveActionId, setLiveActionId: (s) => { setLive(s); s ? localStorage.setItem("vs_live", s) : localStorage.removeItem("vs_live"); },
  };
  return <Ctx.Provider value={v}>{children}</Ctx.Provider>;
}

export const useApp = () => {
  const c = useContext(Ctx);
  if (!c) throw new Error("AppState missing");
  return c;
};
