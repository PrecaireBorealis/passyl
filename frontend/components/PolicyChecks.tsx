import type { Policy } from "@/lib/types";

const NAME: Record<string, string> = {
  mrp_cap: "MRP se upar nahi", price_band: "Daam band", margin_floor: "Margin", budget: "Budget", consent: "Sirf opt-in",
  quiet_hours: "Raat ko message nahi", autonomy: "Aapki manzoori", escalate: "Insaan dekhega",
};

export default function PolicyChecks({ policy }: { policy: Policy }) {
  return (
    <ul className="space-y-0.5">
      {policy.checks.map((c) => (
        <li key={c.id} className="text-[11px] flex gap-1.5">
          <span className={c.passed ? "text-ok" : "text-drop"}>{c.passed ? "✓" : "✗"}</span>
          <span className="font-semibold">{NAME[c.id] ?? c.id}:</span>
          <span className="text-gray-600">{c.detail_hi}</span>
        </li>
      ))}
      {policy.shrunk && <li className="text-[11px] text-amber-700">Budget ke liye segment chhota kiya.</li>}
    </ul>
  );
}
