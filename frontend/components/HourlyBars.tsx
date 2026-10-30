import type { HourRow } from "@/lib/types";
import { rupee } from "@/lib/api";

/** Today's hourly sales as bars, the normal p10–p90 band behind them, red where below normal p10. */
export default function HourlyBars({ hours, alertFrom }: { hours: HourRow[]; alertFrom?: number }) {
  const max = Math.max(1, ...hours.map((h) => Math.max(h.today ?? 0, h.normal_p90 ?? 0)));
  return (
    <div>
      <div className="flex items-end gap-[3px] h-32">
        {hours.map((h) => {
          const low = h.today != null && h.normal_p50 != null && h.today < h.normal_p50 * 0.92 && (alertFrom == null || h.hour >= alertFrom);
          return (
            <div key={h.hour} className="flex-1 relative h-full" title={`${h.hour}:00 today ${rupee(h.today)} · normal ${rupee(h.normal_p50)}`}>
              {h.normal_p90 != null && (
                <div className="absolute bottom-0 w-full bg-gray-100 rounded-sm" style={{ height: `${(100 * h.normal_p90) / max}%` }} />
              )}
              {h.normal_p50 != null && (
                <div className="absolute w-full border-t-2 border-gray-400" style={{ bottom: `${(100 * h.normal_p50) / max}%` }} />
              )}
              {h.today != null && (
                <div className={`absolute bottom-0 left-[20%] w-[60%] rounded-sm ${low ? "bg-drop" : "bg-act"}`}
                     style={{ height: `${(100 * h.today) / max}%` }} />
              )}
            </div>
          );
        })}
      </div>
      <div className="flex gap-[3px] text-[9px] text-gray-400 mt-1">
        {hours.map((h) => <div key={h.hour} className="flex-1 text-center">{h.hour % 3 === 0 ? h.hour : ""}</div>)}
      </div>
      <div className="flex gap-3 text-[10px] text-gray-500 mt-1">
        <span><span className="inline-block w-2 h-2 bg-act mr-1" />Aaj</span>
        <span><span className="inline-block w-3 border-t-2 border-gray-400 mr-1 align-middle" />Normal</span>
        <span><span className="inline-block w-2 h-2 bg-gray-100 border mr-1" />Normal range</span>
      </div>
    </div>
  );
}
