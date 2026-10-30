import type { WhyCard as W } from "@/lib/types";
import { hour12, pct, rupee } from "@/lib/api";
import SplitBar from "./SplitBar";

const DRIVER: Record<string, string> = {
  regulars_missing: "Regular customers nahi aaye", regulars_up: "Regular customers zyada aaye",
  other_customers: "Baaki customers", ticket_size: "Bill ka size", payment_failures: "Payment fail",
};
const STATUS: Record<string, string> = { explains_market: "market ka hissa samjhata hai", partial: "aadha samjhata hai", none: "" };

export default function WhyCard({ card }: { card: W }) {
  const thin = card.confidence.state === "thin_history";
  return (
    <div className="border rounded-xl p-3 space-y-3 bg-white">
      <div className="flex justify-between items-baseline">
        <div className="text-xs text-gray-500">{hour12(card.window.start_hour)}–{hour12(card.window.end_hour)} · {card.date}</div>
        <div className="text-[10px] text-gray-400">baseline: {card.baseline_model}</div>
      </div>
      {thin ? (
        <div className="text-sm bg-amber-50 border border-amber-200 rounded p-2">
          <div className="font-semibold">Abhi itna data nahi hai</div>
          <div className="text-xs text-gray-600">{card.confidence.note}</div>
          {card.peer.median_change_pct != null && (
            <div className="text-xs mt-1">Aas-paas ki {card.peer.n} similar dukaanein: {pct(card.peer.median_change_pct)}
              {card.peer.iqr_pct && <> (zyada tar {pct(card.peer.iqr_pct[0])} se {pct(card.peer.iqr_pct[1])})</>}</div>
          )}
        </div>
      ) : (
        <div className="flex items-end gap-2">
          <div className={`text-2xl font-bold ${(card.shop_change_pct ?? 0) < 0 ? "text-drop" : "text-ok"}`}>{pct(card.shop_change_pct)}</div>
          <div className="text-xs text-gray-500 pb-1">{rupee(card.actual)} vs normal {rupee(card.expected?.p50)}</div>
        </div>
      )}
      {card.split && <SplitBar market={card.split.market_pct} shop={card.split.shop_pct} />}
      {!thin && card.peer.median_change_pct != null && (
        <div className="text-xs text-gray-600">{card.peer.n} similar dukaanein {card.peer.radius_km} km ke andar: {pct(card.peer.median_change_pct)}</div>
      )}
      <div className="divide-y">
        {card.factors.map((f) => (
          <div key={f.id} className="py-1.5 text-xs flex justify-between gap-2">
            <div>
              <div className={f.status === "none" ? "text-gray-400" : "font-semibold"}>{f.label_hi}</div>
              <div className="text-gray-500">{f.evidence}{STATUS[f.status] ? ` · ${STATUS[f.status]}` : ""}</div>
            </div>
            {f.effect_range_pct && (
              <div className="text-right shrink-0">
                <div>usually {pct(f.effect_range_pct[0])} to {pct(f.effect_range_pct[1])}</div>
                <div className="text-gray-400">{f.basis?.shop_n} apne + {f.basis?.peer_n} market din</div>
              </div>
            )}
          </div>
        ))}
      </div>
      {card.shop_drivers.length > 0 && (
        <div>
          <div className="text-xs font-semibold mb-1">Aapki dukaan ka hissa</div>
          {card.shop_drivers.map((d) => (
            <div key={d.id} className="flex justify-between text-xs py-0.5">
              <span>{DRIVER[d.id] ?? d.id}: {d.id === "ticket_size" ? `${rupee(d.actual)} vs ${rupee(d.usual)}` : `${d.actual} vs usual ${d.usual}`}</span>
              <span className={d.contribution_pts < 0 ? "text-drop" : "text-ok"}>{d.contribution_pts > 0 ? "+" : ""}{d.contribution_pts} pts</span>
            </div>
          ))}
        </div>
      )}
      {card.confidence.state === "wide" && <div className="text-[11px] text-amber-700">{card.confidence.note}</div>}
      {card.confidence.state === "no_peers" && <div className="text-[11px] text-amber-700">{card.confidence.note}</div>}
    </div>
  );
}
