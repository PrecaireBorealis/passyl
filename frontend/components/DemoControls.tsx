"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { DEMO_MERCHANTS, useApp } from "@/lib/state";

/** Presenter controls, visible only with ?demo=1 (remembered for the session). */
export default function DemoControls() {
  const q = useSearchParams();
  const router = useRouter();
  const app = useApp();
  const [msg, setMsg] = useState("");
  const on = q.get("demo") === "1" || (typeof window !== "undefined" && sessionStorage.getItem("vs_demo") === "1");
  if (q.get("demo") === "1" && typeof window !== "undefined") sessionStorage.setItem("vs_demo", "1");
  if (!on) return null;
  const run = async (label: string, f: () => Promise<void>) => {
    setMsg(`${label}…`);
    try { await f(); setMsg(`${label}: done`); } catch (e) { setMsg(`${label}: ${(e as Error).message}`); }
  };
  return (
    <div className="w-[360px] bg-white border rounded-xl p-3 text-xs space-y-2">
      <div className="font-semibold">Demo controls</div>
      <div className="flex flex-wrap gap-2">
        <button className="border rounded px-2 py-1" onClick={() => run("Reset", async () => {
          await api.reset(); app.setMessages(() => []); app.clearTrace(); app.setLiveActionId(null); router.push("/");
        })}>Reset demo</button>
        <button className="border rounded px-2 py-1 disabled:opacity-40" disabled={!app.liveActionId}
                onClick={() => run("Simulate", async () => { await api.simulate(app.liveActionId!); router.push("/brief"); })}>Simulate evening</button>
        <select className="border rounded px-1 py-1" value={app.merchant} onChange={(e) => { app.setMerchant(e.target.value); router.push("/"); }}>
          {DEMO_MERCHANTS.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
        </select>
        <label className="flex items-center gap-1"><input type="checkbox" checked={app.offline} onChange={(e) => app.setOffline(e.target.checked)} />Offline speech</label>
      </div>
      {msg && <div className="text-gray-500">{msg}</div>}
    </div>
  );
}
