import type { Strategies } from "@/lib/types";
import { rupee } from "@/lib/api";
import PolicyChecks from "./PolicyChecks";

export default function StrategyCard({ data, onSay }: { data: Strategies; onSay?: (t: string) => void }) {
  return (
    <div className="space-y-2">
      {data.options.map((o, i) => {
        const rec = o.id === data.recommended_id;
        return (
          <div key={o.id} className={`border rounded-xl p-3 bg-white ${rec ? "border-act ring-1 ring-act" : ""}`}>
            <div className="flex justify-between gap-2">
              <div className="text-sm font-semibold">{i + 1}. {o.title_hi}</div>
              {rec && <span className="text-[10px] text-act font-semibold shrink-0">SALAH</span>}
            </div>
            <div className="text-xs text-gray-600 mt-0.5">{o.description_hi}</div>
            <div className="flex gap-4 mt-2 text-xs">
              <div><div className="text-gray-500">Andaazan munafa</div>
                <div className={`font-bold ${o.expected_profit < 0 ? "text-drop" : "text-ok"}`}>{o.expected_profit < 0 ? "−" : "+"}{rupee(Math.abs(o.expected_profit))}</div></div>
              <div><div className="text-gray-500">Kharcha</div><div className="font-semibold">{rupee(o.expected_cost)}</div></div>
              <div><div className="text-gray-500">Customers</div><div className="font-semibold">{o.n_target}</div></div>
            </div>
            {"p_profit_positive" in o.assumptions && (
              <div className="text-[11px] mt-1">
                <b>{Math.round(100 * Number(o.assumptions.p_profit_positive))}%</b> chance munafa hoga · zyada tar{" "}
                {rupee(Number(o.assumptions.profit_p10))} se {rupee(Number(o.assumptions.profit_p90))}
              </div>
            )}
            {"p_t" in o.assumptions && (
              <div className="text-[10px] text-gray-400 mt-1">
                Wapas aane ka andaaza: offer se {Math.round(100 * Number(o.assumptions.p_t))}%, bina offer {Math.round(100 * Number(o.assumptions.p_c))}% ({String(o.assumptions.source)})
              </div>
            )}
            {rec && <div className="mt-2"><PolicyChecks policy={o.policy} /></div>}
            {!rec && !o.policy.passed && <div className="text-[11px] text-drop mt-1">Guardrail fail: {o.policy.checks.filter((c) => !c.passed).map((c) => c.detail_hi).join("; ")}</div>}
          </div>
        );
      })}
      {data.recommended_id && onSay && (
        <div className="flex gap-2">
          <button onClick={() => onSay("Haan, kar do")} className="flex-1 bg-act text-white rounded-lg py-2 text-sm font-semibold">Kar do</button>
          <button onClick={() => onSay("Budget 1500 karo")} className="flex-1 border rounded-lg py-2 text-sm">Badlo</button>
        </div>
      )}
    </div>
  );
}
