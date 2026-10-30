import type { ActionLive as A } from "@/lib/types";
import { hour12, rupee } from "@/lib/api";

export default function ActionLive({ data, onSay }: { data: A; onSay?: (t: string) => void }) {
  const end = new Date(data.ends_at);
  return (
    <div className="border border-ok rounded-xl p-3 bg-white space-y-2">
      <div className="flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-ok animate-pulse" />
        <span className="text-sm font-semibold text-ok">{data.status === "live" ? "Offer chalu hai" : data.status}</span>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div><div className="text-gray-500">Bheja</div><div className="font-semibold">{data.n_treat} customers</div></div>
        <div><div className="text-gray-500">Naapne ke liye roka</div><div className="font-semibold">{data.n_holdout} customers</div></div>
        <div><div className="text-gray-500">Budget cap</div><div className="font-semibold">{rupee(data.budget_cap)}</div></div>
        <div><div className="text-gray-500">Band hoga</div><div className="font-semibold">{hour12(end.getHours())}</div></div>
      </div>
      {onSay && data.status === "live" && (
        <button onClick={() => onSay("Offer band karo")} className="w-full border border-drop text-drop rounded-lg py-1.5 text-sm">Undo: offer band karo</button>
      )}
    </div>
  );
}
