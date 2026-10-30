"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import HourlyBars from "@/components/HourlyBars";
import { api, hour12, pct, rupee } from "@/lib/api";
import { useApp } from "@/lib/state";
import type { Hourly, Summary } from "@/lib/types";

export default function Home() {
  const { merchant } = useApp();
  const [s, setS] = useState<Summary | null>(null);
  const [h, setH] = useState<Hourly | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    setS(null); setH(null); setErr("");
    Promise.all([api.summary(merchant), api.hourly(merchant)]).then(([a, b]) => { setS(a); setH(b); }).catch((e) => setErr(e.message));
  }, [merchant]);
  if (err) return <div className="p-4 text-sm text-drop">Backend se data nahi aaya: {err}</div>;
  if (!s || !h) return <div className="p-4 text-sm text-gray-400">Loading…</div>;
  const q = "Bhai, aaj sales itni kam kyun hai?";
  const day = new Date(s.date).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short" });
  return (
    <div className="p-4 space-y-4">
      <div>
        <div className="text-xs text-gray-500">Aaj ki sales · {day}</div>
        <div className="flex items-end gap-2">
          <div className="text-3xl font-bold">{rupee(s.revenue_today)}</div>
          {s.change_pct != null && <div className={`pb-1 text-sm font-semibold ${s.change_pct < 0 ? "text-drop" : "text-ok"}`}>{pct(s.change_pct)}</div>}
        </div>
        <div className="text-xs text-gray-500">{s.revenue_normal != null ? `Normal ${day.split(",")[0]} isi waqt tak: ${rupee(s.revenue_normal)}` : "Abhi normal banane ke liye data kam hai"}</div>
      </div>
      {s.alert && (
        <div className="border border-drop/30 bg-red-50 rounded-xl p-3 flex items-center justify-between gap-2">
          <div className="text-sm"><span className="font-semibold text-drop">Shaam {hour12(s.alert.window.start_hour)} ke baad sales {Math.abs(s.alert.change_pct)}% kam</span>
            <div className="text-xs text-gray-600">normal se neeche</div></div>
          <Link href={`/chat?q=${encodeURIComponent(q)}`} className="bg-act text-white text-sm font-semibold rounded-lg px-3 py-1.5">Kyun?</Link>
        </div>
      )}
      <div className="border rounded-xl p-3">
        <div className="text-xs font-semibold mb-2">Har ghante ki sales</div>
        <HourlyBars hours={h.hours} alertFrom={s.alert?.window.start_hour} />
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="border rounded-xl p-3"><div className="text-gray-500">Bills</div><div className="text-lg font-semibold">{s.bills}</div>
          <div className="text-gray-500">{pct(s.bills_change_pct)} vs normal</div></div>
        <div className="border rounded-xl p-3"><div className="text-gray-500">Regular customers</div>
          <div className="text-lg font-semibold">{s.regular_share != null ? `${Math.round(100 * s.regular_share)}%` : "–"}</div>
          <div className="text-gray-500">usually {s.regular_share_usual != null ? `${Math.round(100 * s.regular_share_usual)}%` : "–"}</div></div>
      </div>
      <Link href={`/chat${s.alert ? "" : `?q=${encodeURIComponent(q)}`}`} className="block text-center border rounded-lg py-2 text-sm text-act">VyaparSaathi se poochho</Link>
    </div>
  );
}
