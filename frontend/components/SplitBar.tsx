import { pct } from "@/lib/api";

/** Total change split into market-wide (grey) and shop-specific (red) parts. */
export default function SplitBar({ market, shop }: { market: number; shop: number }) {
  const total = Math.abs(market) + Math.abs(shop) || 1;
  return (
    <div>
      <div className="flex h-5 rounded overflow-hidden text-[10px] text-white font-semibold">
        <div className="bg-gray-400 flex items-center justify-center" style={{ width: `${(100 * Math.abs(market)) / total}%` }}>{pct(market)}</div>
        <div className={`${shop < 0 ? "bg-drop" : "bg-ok"} flex items-center justify-center`} style={{ width: `${(100 * Math.abs(shop)) / total}%` }}>{pct(shop)}</div>
      </div>
      <div className="flex justify-between text-[10px] text-gray-500 mt-1">
        <span>Poora area (market)</span><span>Sirf aapki dukaan</span>
      </div>
    </div>
  );
}
