"use client";
import { useEffect, useState } from "react";
import ResultCard from "@/components/ResultCard";
import { api, pct, rupee } from "@/lib/api";
import { useApp } from "@/lib/state";
import type { Brief } from "@/lib/types";

export default function BriefPage() {
  const app = useApp();
  const [b, setB] = useState<Brief | null>(null);
  const [err, setErr] = useState("");
  const [asked, setAsked] = useState("");
  useEffect(() => { api.brief(app.merchant).then(setB).catch((e) => setErr(e.message)); }, [app.merchant]);
  if (err) return <div className="p-4 text-sm text-drop">{err}</div>;
  if (!b) return <div className="p-4 text-sm text-gray-400">Loading…</div>;
  const y = b.yesterday;
  const day = new Date(b.date).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short" });
  const ask = async () => {
    const r = await api.message(app.merchant, "aaj ka report");
    app.pushTrace("aaj ka report", r.trace);
    setAsked(r.reply_text);
  };
  return (
    <div className="p-4 space-y-3">
      <div>
        <div className="text-xs text-gray-500">Subah ka brief</div>
        <div className="text-lg font-semibold">{day}</div>
      </div>
      <div className="border rounded-xl p-3 text-sm">
        <div className="text-xs text-gray-500">Kal ki sales</div>
        <div className="flex items-end gap-2"><span className="text-xl font-bold">{rupee(y.revenue_today)}</span>
          {y.change_pct != null && <span className={`pb-0.5 font-semibold ${y.change_pct < 0 ? "text-drop" : "text-ok"}`}>{pct(y.change_pct)} vs normal</span>}</div>
        <div className="text-xs text-gray-500">{y.bills} bills</div>
      </div>
      {b.last_action_result ? <ResultCard m={b.last_action_result} /> :
        <div className="border rounded-xl p-3 text-xs text-gray-500">Kal koi offer nahi chala (ya abhi result nahi aaya).</div>}
      {(b.today.weather_note_hi || b.today.festival_note_hi) && (
        <div className="border rounded-xl p-3 text-xs space-y-1">
          <div className="font-semibold">Aaj</div>
          {b.today.weather_note_hi && <div>{b.today.weather_note_hi}</div>}
          {b.today.festival_note_hi && <div>{b.today.festival_note_hi}</div>}
        </div>
      )}
      {b.suggestion && (
        <div className="border border-act rounded-xl p-3 text-xs space-y-1">
          <div className="font-semibold text-act">Aaj ki salah</div>
          <div className="text-sm font-semibold">{b.suggestion.title_hi}</div>
          <div className="text-gray-600">{b.suggestion.description_hi}</div>
          <div>Andaazan munafa <b className="text-ok">{rupee(b.suggestion.expected_profit)}</b></div>
        </div>
      )}
      <button onClick={ask} className="w-full border rounded-lg py-2 text-sm text-act">Brief sunao</button>
      {asked && <div className="bg-gray-100 text-sm rounded-xl px-3 py-2">{asked}</div>}
    </div>
  );
}
