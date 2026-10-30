"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Benchmark } from "@/lib/types";

const F = (v: number | null | undefined, p = true, digits = 1) => (v == null ? "–" : p ? `${(100 * v).toFixed(1)}%` : v.toFixed(digits));
const ROWS: [string, "forecast" | "engine", string, boolean][] = [
  ["Detection rate", "engine", "detection_rate", true], ["Cause accuracy", "engine", "cause_accuracy", true],
  ["Split error (pts)", "engine", "split_mae_pts", false], ["Range coverage", "engine", "range_coverage", true],
  ["False alarms", "engine", "false_alarm_rate", true], ["\"Don't know\" when thin", "engine", "idk_rate", true],
  ["WAPE (clean)", "forecast", "wape_p50", true], ["Quantile loss", "forecast", "wql", false],
  ["80% range coverage (target 80%)", "forecast", "coverage_p10_p90", true], ["Holiday WAPE", "forecast", "holiday_wape", true],
];

export default function BenchmarkPage() {
  const [b, setB] = useState<Benchmark | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api.benchmark().then(setB).catch((e) => setErr(e.message)); }, []);
  if (err) return <div className="p-4 text-sm text-drop">{err}</div>;
  if (!b) return <div className="p-4 text-sm text-gray-400">Loading…</div>;
  const names = Object.keys(b.baselines);
  return (
    <div className="p-3 space-y-3">
      <div>
        <div className="text-sm font-semibold">Shock-Injection Benchmark</div>
        <div className="text-[11px] text-gray-500">Held-out seed {b.seed}, never tuned on. {b.n_shock_windows} planted shocks, {b.n_clean_windows} clean windows.</div>
      </div>
      <table className="w-full text-[11px]">
        <thead><tr className="border-b"><th className="text-left py-1">Metric</th>
          {names.map((n) => <th key={n} className={`text-right ${n === b.app_baseline ? "text-act" : ""}`}>{({ chronos_bolt: "Bolt", chronos2: "Chronos-2", lgbm: "LightGBM" } as Record<string, string>)[n] ?? n}{n === b.app_baseline ? " ★" : ""}</th>)}</tr></thead>
        <tbody>
          {ROWS.map(([label, sec, key, p]) => (
            <tr key={key} className="border-b border-gray-100"><td className="py-1">{label}</td>
              {names.map((n) => <td key={n} className="text-right">{F((b.baselines[n][sec] as Record<string, number | null>)[key], p, key === "wql" ? 3 : 1)}</td>)}</tr>
          ))}
          <tr><td className="py-1">Latency p50</td>{names.map((n) => <td key={n} className="text-right">{b.baselines[n].forecast.latency_ms_p50} ms</td>)}</tr>
        </tbody>
      </table>
      <div>
        <div className="text-xs font-semibold mb-1">By shock (detected / right cause)</div>
        <table className="w-full text-[11px]"><tbody>
          {Object.keys(b.baselines[names[0]].engine.by_kind).map((k) => (
            <tr key={k} className="border-b border-gray-100"><td className="py-1">{k}</td>
              {names.map((n) => { const x = b.baselines[n].engine.by_kind[k];
                return <td key={n} className="text-right">{x ? `${F(x.detection_rate)} / ${F(x.cause_accuracy)}` : "–"}</td>; })}</tr>
          ))}
        </tbody></table>
      </div>
      <div className="text-[11px] text-gray-500">★ app default, chosen on dev seed 7 before seeing this seed. {b.caveat}</div>
    </div>
  );
}
