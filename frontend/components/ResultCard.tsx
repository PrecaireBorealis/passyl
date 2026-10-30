import type { Measure } from "@/lib/types";
import { rupee } from "@/lib/api";

const P = (x: number) => `${Math.round(100 * x)}%`;

export default function ResultCard({ m }: { m: Measure }) {
  const rows = [
    { label: "Offer mila", n: m.n_treat, r: m.returned_treat, rate: m.rate_treat, ci: m.rate_treat_ci, cls: "bg-act" },
    { label: "Offer nahi mila (holdout)", n: m.n_holdout, r: m.returned_holdout, rate: m.rate_holdout, ci: m.rate_holdout_ci, cls: "bg-gray-400" },
  ];
  return (
    <div className="border rounded-xl p-3 bg-white space-y-2">
      <div className="text-sm font-semibold">Offer ka asli asar</div>
      {rows.map((x) => (
        <div key={x.label} className="text-xs">
          <div className="flex justify-between"><span>{x.label}</span><span>{x.r}/{x.n} laute · <b>{P(x.rate)}</b></span></div>
          <div className="relative h-2 bg-gray-100 rounded mt-1">
            <div className={`absolute h-2 rounded ${x.cls}`} style={{ width: P(x.rate) }} />
            <div className="absolute h-2 border-x border-gray-700" style={{ left: P(x.ci[0]), width: `${100 * (x.ci[1] - x.ci[0])}%` }} />
          </div>
        </div>
      ))}
      <div className="grid grid-cols-3 gap-2 text-xs pt-1">
        <div><div className="text-gray-500">Extra bills</div><div className="font-semibold">{m.incremental_bills}</div></div>
        <div><div className="text-gray-500">Offer kharcha</div><div className="font-semibold">{rupee(m.offer_cost)}</div></div>
        <div><div className="text-gray-500">Extra munafa</div>
          <div className={`font-bold ${m.incremental_profit < 0 ? "text-drop" : "text-ok"}`}>{rupee(m.incremental_profit)}</div></div>
      </div>
      <div className="text-[11px] text-gray-500">{m.note_hi} Lines = 80% range.</div>
    </div>
  );
}
