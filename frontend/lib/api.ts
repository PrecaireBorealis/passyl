import type { AgentResponse, ActionLive, Benchmark, Brief, Hourly, Measure, Merchant, Strategies, Summary, VoiceTurn, WhyCard } from "./types";

export const API = process.env.NEXT_PUBLIC_API ?? "http://localhost:8000";
const MOCK = process.env.NEXT_PUBLIC_MOCK === "1";

// Mock mode serves contracts/fixtures (copied to public/fixtures) so the UI can be built without the backend.
const FIXTURE: Record<string, string> = {
  summary: "summary.json", hourly: "hourly.json", why: "why.json", strategies: "strategies.json", brief: "brief.json",
  message: "agent_response.json", approve: "action_live.json", measure: "measure.json", benchmark: "benchmark.json",
};

async function call<T>(path: string, init?: RequestInit, fixture?: string): Promise<T> {
  if (MOCK && fixture) return (await fetch(`/fixtures/${FIXTURE[fixture]}`)).json();
  const r = await fetch(`${API}${path}`, { cache: "no-store", ...init });
  const js = await r.json();
  if (!r.ok) throw new Error(js?.error?.message_hi ?? `HTTP ${r.status}`);
  return js as T;
}

const post = (body?: unknown): RequestInit => ({
  method: "POST", headers: { "content-type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body),
});

export const api = {
  health: () => call<{ ok: boolean; baseline: string; llm: string; offline: boolean; sarvam: boolean }>("/api/health"),
  merchants: () => call<Merchant[]>("/api/merchants"),
  summary: (m: string) => call<Summary>(`/api/merchants/${m}/summary`, undefined, "summary"),
  hourly: (m: string) => call<Hourly>(`/api/merchants/${m}/hourly`, undefined, "hourly"),
  why: (m: string) => call<WhyCard>(`/api/merchants/${m}/why`, undefined, "why"),
  strategies: (m: string) => call<Strategies>(`/api/merchants/${m}/strategies`, undefined, "strategies"),
  brief: (m: string) => call<Brief>(`/api/merchants/${m}/brief`, undefined, "brief"),
  message: (merchant_id: string, text: string, channel: "chat" | "voice" = "chat") =>
    call<AgentResponse>("/api/agent/message", post({ merchant_id, text, channel }), "message"),
  voice: async (merchant_id: string, audio: Blob): Promise<VoiceTurn> => {
    const f = new FormData();
    f.append("audio", audio, "turn.webm");
    f.append("merchant_id", merchant_id);
    return call<VoiceTurn>("/api/voice/turn", { method: "POST", body: f });
  },
  tts: (text: string, lang: string) => call<{ audio_b64: string | null }>("/api/voice/tts", post({ text, lang })),
  approve: (id: string) => call<ActionLive>(`/api/actions/${id}/approve`, post({ actor: "merchant" }), "approve"),
  undo: (id: string) => call<{ id: string; status: string }>(`/api/actions/${id}/undo`, post()),
  measure: (id: string) => call<Measure>(`/api/actions/${id}/measure`, undefined, "measure"),
  reset: () => call<{ status: string }>("/api/demo/reset", post()),
  simulate: (id: string) => call<Measure>(`/api/demo/simulate/${id}`, post(), "measure"),
  benchmark: () => call<Benchmark>("/api/benchmark/latest", undefined, "benchmark"),
};

export const rupee = (n: number | null | undefined) => (n == null ? "–" : `₹${Math.round(n).toLocaleString("en-IN")}`);
export const pct = (n: number | null | undefined, sign = true) => (n == null ? "–" : `${sign && n > 0 ? "+" : ""}${n.toFixed(1)}%`);
export const hour12 = (h: number) => `${h % 12 || 12}${h < 12 ? " am" : " pm"}`;
