// Mirrors SPEC.md section 15 (and 8.6, 12.4, 16.3). Do not rename fields.
export type Merchant = { id: string; name: string; category: string; locality: string; history_days: number };

export type Summary = {
  date: string; revenue_today: number; revenue_normal: number | null; change_pct: number | null; bills: number;
  bills_change_pct: number | null; regular_share: number | null; regular_share_usual: number | null;
  alert: { window: { start_hour: number; end_hour: number }; change_pct: number } | null; data_label: string;
};

export type HourRow = { hour: number; today: number | null; normal_p50: number | null; normal_p10: number | null; normal_p90: number | null };
export type Hourly = { hours: HourRow[] };

export type Factor = {
  id: string; label_hi: string; evidence: string; status: "explains_market" | "partial" | "none";
  effect_range_pct?: [number, number]; basis?: { shop_n: number; peer_n: number };
};
export type Driver = { id: string; usual: number; actual: number; contribution_pts: number };
export type WhyCard = {
  merchant_id: string; date: string; window: { start_hour: number; end_hour: number }; actual: number;
  expected: { p10: number; p50: number; p90: number } | null; baseline_model: string; shop_change_pct: number | null;
  peer: { n: number; radius_km: number; median_change_pct: number | null; iqr_pct: [number, number] | null };
  split: { market_pct: number; shop_pct: number } | null; factors: Factor[]; shop_drivers: Driver[];
  confidence: { state: "ok" | "wide" | "thin_history" | "no_peers"; note: string | null }; data_label: string;
};

export type Check = { id: string; passed: boolean; detail_hi: string };
export type Policy = { passed: boolean; checks: Check[]; shrunk?: boolean; blocked?: boolean };
export type StrategyOption = {
  id: string; title_hi: string; description_hi: string; expected_profit: number; expected_cost: number;
  n_target: number; assumptions: Record<string, number | string>; policy: Policy;
};
export type Strategies = { options: StrategyOption[]; recommended_id: string | null; draft_action_id: string | null };

export type ActionLive = { id: string; status: string; n_treat: number; n_holdout: number; budget_cap: number; ends_at: string; policy: Policy };

export type Measure = {
  n_treat: number; returned_treat: number; rate_treat: number; rate_treat_ci: [number, number];
  n_holdout: number; returned_holdout: number; rate_holdout: number; rate_holdout_ci: [number, number];
  incremental_bills: number; incremental_profit: number; offer_cost: number; note_hi: string;
};

export type Brief = {
  date: string; yesterday: Summary; last_action_result: (Measure & { title_hi?: string }) | null;
  today: { weather_note_hi: string | null; festival_note_hi: string | null }; suggestion: StrategyOption | null;
};

export type TraceItem = { tool: string; ms: number; summary: string };
export type Card =
  | { type: "why_card"; data: WhyCard }
  | { type: "strategy_card"; data: Strategies }
  | { type: "action_live"; data: ActionLive }
  | { type: "result_card"; data: Measure }
  | { type: "brief_card"; data: Brief }
  | { type: "idk_card"; data: { message: string } };

export type AgentResponse = {
  reply_text: string; lang: string; intent: string; cards: Card[];
  pending_action: { id: string; kind: string; title_hi?: string } | null;
  trace: TraceItem[]; audio_b64: string | null; data_label: string;
};

export type VoiceTurn = { transcript: string; stt_lang: string | null; fallback?: boolean; response: AgentResponse | null; audio_b64: string | null };

type Metrics = {
  forecast: { wape_p50: number; wql: number; coverage_p10_p90: number; holiday_wape: number | null; latency_ms_p50: number | null; latency_ms_p95: number | null };
  engine: { detection_rate: number; cause_accuracy: number; split_mae_pts: number | null; range_coverage: number | null;
            false_alarm_rate: number; idk_rate: number | null; by_kind: Record<string, { n: number; detection_rate: number; cause_accuracy: number | null }> };
  model_id?: string;
};
export type Benchmark = { seed: number; n_shock_windows: number; n_clean_windows: number; app_baseline: string; baselines: Record<string, Metrics>; caveat: string };

export type ApiError = { error: { code: string; message_hi: string; message_en: string } };
