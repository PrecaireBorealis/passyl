# VyaparSaathi AI: Final Build Spec (Paytm Build for India, Offline Final, 31 Oct 2026)

**Team VyaparSaathi, RGIPT Jais:** Ishaan Saxena (lead), Aditya Kumar, Chinmay Bhardwaj
**Version:** 1.1, 31 Oct 2026. This file is the single source of truth. Put it at `docs/SPEC.md` in the repo.

**Changes in 1.1:** two interchangeable baselines, LightGBM and Chronos-Bolt, behind one interface, compared head to head in the benchmark (sections 1.2, 4.1, 5, 6, 8.1, 8.6, 12.4, 16, 17, 19, 20, 21). API change is additive only: `baseline_model` field in the Why card and a `baselines` block in the benchmark JSON.

---

## 0. How to use this document

**For teammates:** read sections 1 to 4 fully (about 15 minutes). Then read only the sections for your workstream (section 18 lists who owns what).

**For AI coding assistants (Claude, ChatGPT, Cursor, etc.):** paste this whole file as context, then paste the matching prompt from section 20. Rules for any AI working on this repo:

1. Do not change anything in section 15 (API contract) or section 7.4 (database schema) without the team lead agreeing. Other people are building against them in parallel.
2. Every number shown to the merchant must come from the engine (Python code), never from the LLM. See the Number Guard in section 12.6.
3. Everything must run on a laptop without internet, except the LLM and Sarvam calls, and those have offline fallbacks (section 19).
4. All data is synthetic or public. Label it as such in the UI.

**Words used in this doc**

| Term | Meaning (one line) |
|---|---|
| Window | A block of hours on one date, e.g. Friday 30 Oct, 18:00 to 22:00 |
| Baseline / expected | What this shop normally sells in that window on that weekday |
| Peer group | Anonymised group of 10+ shops of the same category near the merchant |
| Peer-Shock Test | Splits a sales change into "market-wide" (peers changed too) and "shop-specific" |
| Partial pooling | Blend a shop's own estimate with its peer group's average, trusting the shop more as its history grows |
| Holdout | Customers randomly not sent the offer, so we can measure the real effect |
| Shock-Injection Benchmark | We plant known causes in synthetic data and score whether the engine finds them |
| L1 / L2 / L3 | Autonomy levels: recommend / approve-and-execute / auto within policy |

---

## 1. What we are building

VyaparSaathi is an AI growth partner for Paytm merchants. A merchant asks, by voice or chat, in Hindi, Hinglish or English: **"Aaj sales kam kyun hai?"** The agent:

1. **Understands**: compares tonight with this shop's normal Friday evening.
2. **Explains**: runs the Peer-Shock Test. Similar restaurants within 2 km fell about 12% (rain), so about 12 points are market-wide and about 6 points are the shop's own. It then finds the shop-specific cause (regular customers didn't come).
3. **Recommends**: ranks actions by expected incremental profit. A 7 to 10 PM family combo for lapsed regulars beats a flat 20% off.
4. **Executes**: when the merchant says "kar do", the agent runs the action through a simulated Paytm action API, inside guardrails (never above MRP, within budget, opted-in customers only).
5. **Measures**: compares customers who got the offer with a random holdout group, then reports the result in the next morning's brief.

### 1.1 The demo story (this is our acceptance test)

Merchant: **Raju Family Restaurant, Koramangala, Bengaluru**. Demo date: **Friday 30 Oct 2026**, 8:05 PM. Morning brief: **Saturday 31 Oct 2026** (event day).

The demo must run end to end, live, on a laptop. If every step in section 3 works, we are done. Everything else is optional.

### 1.2 Decisions made since the Round 1 deck

| Topic | Final decision | Why |
|---|---|---|
| Data | Synthetic transactions, driven by **real** Bengaluru/Pune/Jaipur hourly weather (Open-Meteo archive) and the **real** Indian festival calendar (`holidays` library) | No public dataset has merchant-level, hourly, payer-level Indian payments with nearby peers. That gap is exactly Paytm's moat. Real weather and calendar make the shocks realistic. |
| Data window | 1 Oct 2025 to 30 Oct 2026 (395 days) | Includes Diwali 2025 (20 Oct), Holi, Eid, Ganesh Chaturthi, Dussehra 2026 |
| Database | PostgreSQL 16 (Docker). Raw transactions also saved as Parquet. | Matches the deck; Parquet keeps generation fast |
| Speech | Sarvam AI: **Saaras v4** (speech-to-text), **Bulbul v3** (text-to-speech). Saarika is deprecated. | Current Sarvam models (checked 29 Oct 2026) |
| LLM | Provider-agnostic wrapper (Claude / OpenAI / Gemini / Sarvam chat), chosen by env var | Use whichever key we have; swap if one fails |
| Agent style | **Deterministic pipeline for the 5 core intents**, LLM for understanding and writing replies only, LLM tool-calling only for open questions | A demo must not go off-script. Judges see a real agent trace either way. |
| n8n | Optional. Action executor calls an n8n webhook if `N8N_WEBHOOK_URL` is set, else runs in-process | Saves setup time; still shows the workflow on screen if ready |
| Baseline | **Two models behind one interface:** LightGBM quantile regression (trained per category) and **Chronos-Bolt** (`amazon/chronos-bolt-small`, pretrained, zero-shot). Selected by `BASELINE_MODEL`. Both are scored in the benchmark; the app default is picked on dev seed 7 only | A trained model vs a time-series foundation model, measured on the same windows. Bolt needs no training, so rolling evaluation is cheap |
| Execution | Simulated Paytm action API (`/mock-paytm/*`) plus a seeded simulation of customer response | We have no Paytm sandbox; this is honest and swappable |

---

## 2. Scope for 31 Oct

**P0, must work live (the demo):**
1. Synthetic dataset with injected shocks, loaded in Postgres
2. Baseline + drop detection
3. Why-Engine: Peer-Shock split, weather, festival and disruption checks, shop-driver breakdown, ranges, "not enough history" state
4. Strategy ranker (expected profit) + policy checks
5. Approve → execute (mock Paytm) → simulate → measure vs holdout
6. Chat with Hinglish replies; agent trace visible
7. Voice in/out (Sarvam, with browser fallback)
8. Morning Brief
9. Shock-Injection Benchmark run on a held-out seed, with real numbers on one screen

**P1, if time allows:** n8n workflow visible, L3 auto-policy toggle, a second demo merchant (kirana), English/Hindi toggle.

**Not building:** real Paytm integration, real messaging (SMS/WhatsApp), item-level (Tier 2) pricing beyond the combo item, competitor detection from public listings, multi-outlet.

---

## 3. Demo script (acceptance test, about 4 minutes)

| # | Screen | What happens | Pass when |
|---|---|---|---|
| 1 | Home | Raju's dashboard for Fri 30 Oct. Today's sales vs normal Friday, hourly bars (evening red), alert "Shaam 6 baje ke baad sales X% kam" | Numbers come from `/summary` and `/hourly`; evening drop between 15% and 21% |
| 2 | Ask | Presenter clicks mic, says "Bhai, aaj sales itni kam kyun hai?" Transcript appears. Agent trace ticks: normal Friday → nearby shops → weather → festival calendar → regular customers | Real STT transcript (or fallback); each trace line is a real tool call with timing |
| 3 | Why | Split bar: market part (grey) + shop part (red). Factor rows with ranges and basis. One-line Hinglish summary, spoken back | Split comes from `/why`; ranges shown; voice reply plays |
| 4 | Recommend | Two options ranked by expected profit: family combo for lapsed regulars (positive) vs flat 20% off (lower or negative). Four guardrail checks shown passing | Profit numbers from `/strategies`; policy results from engine |
| 5 | Approve | Presenter says "Haan, kar do". Action goes live: sent to N opted-in regulars, M held back, budget cap, end time, undo button | `/actions/{id}/approve` returns live; audit log row written |
| 6 | Result | Click "Simulate evening" (demo control). Morning Brief for Sat 31 Oct: treated vs holdout return rate, incremental profit after offer cost, a small-sample note, and the next suggestion | Numbers from `/measure` and `/brief` |
| 7 | Honesty | Switch to "Nayi Dukaan Café" (3 weeks of history). Ask the same question. Agent says "not enough history yet" and shows the peer range instead | `confidence.state = "thin_history"` |
| 8 | Proof | Open `/benchmark`: Shock-Injection Benchmark table on the test seed | Numbers are real outputs of `benchmark/run.py` |

Never hardcode demo numbers in the UI. If the numbers look off, tune the scenario config (section 7.5) and regenerate.

---

## 4. Architecture

### 4.1 System diagram

```
 CHANNELS              ┌──────────────────────┐  ┌────────────────────────┐  ┌─────────────────────┐
                       │ Voice (mic in browser)│  │ Chat (web app)         │  │ Morning Brief       │
                       └──────────┬───────────┘  └───────────┬────────────┘  └──────────┬──────────┘
                                  │ audio                    │ text                     │ scheduled / button
 SPEECH                ┌──────────▼───────────────────────────▼──────────────────────────▼──────────┐
                       │ Sarvam Saaras v4 (STT)  ·  Bulbul v3 (TTS)  ·  fallback: browser Web Speech │
                       └──────────────────────────────────┬──────────────────────────────────────────┘
                                                          │ text + lang
 AGENT CORE (FastAPI)  ┌──────────────────────────────────▼──────────────────────────────────────────┐
                       │ Orchestrator: intent → fixed pipeline → Number Guard → reply writer (LLM)   │
                       │ Merchant memory  ·  Conversation state  ·  Agent trace (every tool call)    │
                       └───────┬──────────────────────────┬───────────────────────────┬──────────────┘
                               │                          │                           │
 TOOLS          ┌──────────────▼─────────┐  ┌─────────────▼────────────┐  ┌───────────▼─────────────┐
                │ Intelligence           │  │ Context                  │  │ Action                  │
                │ baseline: LGBM | Bolt  │  │ weather (Open-Meteo)     │  │ strategy ranker         │
                │ Peer-Shock Test        │  │ festival calendar        │  │ policy engine           │
                │ attribution + pooling  │  │ disruption events        │  │ executor → mock Paytm   │
                │ shop-driver breakdown  │  │ peer radius (geo)        │  │ simulator · measurement │
                └──────────────┬─────────┘  └─────────────┬────────────┘  │ (n8n webhook optional)  │
                               │                          │               └───────────┬─────────────┘
 DATA           ┌──────────────▼──────────────────────────▼───────────────────────────▼─────────────┐
                │ Data adapter (one interface: get_transactions, get_hourly, get_peers, ...)        │
                │      ├── SyntheticAdapter (Postgres + Parquet)   ← today                           │
                │      └── PaytmAdapter (stub, same methods)       ← later, if Paytm gives a sandbox │
                └───────────────────────────────────────────────────────────────────────────────────┘
                 Hidden from the engine: shock_labels table (only the benchmark reads it)
```

### 4.2 Request flow: "Aaj sales kam kyun hai?"

```
Browser ──audio──▶ POST /api/voice/turn
                    ├─ sarvam.stt(audio) → "bhai aaj sales itni kam kyun hai"   (trace: stt, ms)
                    ├─ orchestrator.handle(text, merchant_id, date)
                    │    ├─ classify_intent → WHY                               (keyword first, LLM if unsure)
                    │    ├─ tools.get_summary(...)                              (trace)
                    │    ├─ tools.explain_change(window=18–22)                  (trace: baseline, peer_shock,
                    │    │                                                       weather, calendar, drivers)
                    │    ├─ writer.reply(intent, tool_json, lang="hi-en")       (LLM, ≤ 60 words)
                    │    └─ number_guard(reply, tool_json) → ok / fallback to template
                    ├─ sarvam.tts(reply) → base64 wav                           (trace)
                    └─ return AgentResponse {reply_text, cards:[why_card], trace, audio_b64}
```

### 4.3 Design rules

- **The LLM talks and plans; every number comes from a tool.** Enforced by the Number Guard (section 12.6).
- **One interface for data.** The engine imports only `adapters.base.DataAdapter`. It never runs raw SQL on `shock_labels`.
- **Everything is logged.** Every tool call goes into the agent trace (shown in UI) and every action into `audit_log`.
- **Same date everywhere.** The app runs on a fixed "demo clock" (`DEMO_NOW=2026-10-30T20:05:00+05:30`), not the real clock.

---

## 5. Repo structure

```
vyaparsaathi/
├── README.md                      # 10-line quickstart
├── docs/
│   ├── SPEC.md                    # this file
│   └── demo-script.md             # section 3, printed for presenter
├── .env.example
├── docker-compose.yml             # postgres (+ optional n8n)
├── Makefile                       # make data | make api | make web | make bench | make demo-reset
├── contracts/
│   ├── openapi.yaml               # generated from FastAPI later; section 15 is the source
│   └── fixtures/                  # example JSON for every endpoint (frontend builds against these first)
│       ├── summary.json  hourly.json  why.json  why_thin.json  strategies.json
│       ├── action_live.json  measure.json  brief.json  agent_response.json  benchmark.json
├── data/
│   ├── reference/                 # COMMITTED to git (small, real public data)
│   │   ├── localities.csv
│   │   ├── weather_hourly.csv     # Open-Meteo archive, cached once
│   │   ├── festivals.csv          # from `holidays` lib + category effect map
│   │   └── disruptions.csv        # synthetic bandh/strike days (labelled synthetic)
│   └── generated/                 # NOT committed (.gitignore): parquet + labels
├── generator/                     # Workstream A (Chinmay)
│   ├── config/
│   │   ├── world.yaml             # localities, merchant counts, date range, seeds
│   │   ├── effects.yaml           # demand assumptions (hour/day profiles, rain, festival effects)
│   │   └── scenarios/raju_demo.yaml
│   ├── fetch_weather.py           # Open-Meteo → data/reference/weather_hourly.csv
│   ├── build_calendar.py          # holidays → data/reference/festivals.csv
│   ├── merchants.py  customers.py  demand.py  shocks.py  campaigns.py
│   ├── build_dataset.py           # main entry: python -m generator.build_dataset --seed 42
│   └── load_db.py                 # parquet → postgres (COPY), builds hourly aggregates
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py  config.py  db.py  clock.py
│   │   ├── models.py              # SQLAlchemy tables (section 7.4)
│   │   ├── adapters/
│   │   │   ├── base.py            # DataAdapter protocol
│   │   │   ├── synthetic.py       # Postgres implementation
│   │   │   └── paytm_stub.py      # same methods, raises NotImplemented with a clear message
│   │   ├── engine/                # Workstream B (Ishaan)
│   │   │   ├── baseline.py        # Baseline protocol + get_baseline(name) factory + fallback chain
│   │   │   ├── baseline_lgbm.py   # LightGBM quantile models (trained, cached in models/)
│   │   │   ├── baseline_bolt.py   # Chronos-Bolt zero-shot (weights cached locally)
│   │   │   ├── baseline_median.py # 8-week same-weekday median (last-resort fallback)
│   │   │   ├── peer_shock.py
│   │   │   ├── context.py         # weather / festival / disruption flags
│   │   │   ├── pooling.py         # partial pooling + ranges
│   │   │   ├── drivers.py         # shop-specific breakdown (regulars, new, ticket, failures)
│   │   │   ├── why.py             # assembles the Why card
│   │   │   ├── strategy.py        # playbook + expected profit
│   │   │   ├── policy.py          # guardrails
│   │   │   ├── simulate.py        # seeded customer response for a live action
│   │   │   └── measure.py         # treated vs holdout
│   │   ├── agent/                 # Workstream B2 (Ishaan, after engine)
│   │   │   ├── orchestrator.py  intents.py  tools.py  memory.py  trace.py
│   │   │   ├── llm.py             # provider-agnostic client
│   │   │   ├── number_guard.py
│   │   │   ├── templates.py       # offline reply templates (Hinglish/English)
│   │   │   └── prompts/           # system.md  classify.md  write_reply.md  brief.md  open_qa.md
│   │   ├── voice/sarvam.py        # Workstream C (Aditya)
│   │   ├── actions/
│   │   │   ├── executor.py  mock_paytm.py  n8n.py
│   │   └── api/
│   │       ├── routes_merchant.py  routes_agent.py  routes_voice.py
│   │       ├── routes_actions.py  routes_demo.py  routes_benchmark.py
│   └── tests/                     # test_peer_shock.py, test_policy.py, test_number_guard.py, ...
├── benchmark/                     # Workstream A2 (Chinmay)
│   ├── run.py                     # python -m benchmark.run --seed 42 --out benchmark/results/
│   ├── metrics.py
│   └── results/                   # benchmark.json + report.md (committed after final run)
├── frontend/                      # Workstream C (Aditya)
│   ├── package.json  next.config.js
│   ├── app/
│   │   ├── page.tsx               # Home (screen 1)
│   │   ├── chat/page.tsx          # Ask + Why + Recommend + Live (screens 2–5, one conversation)
│   │   ├── brief/page.tsx         # Morning Brief (screen 6)
│   │   └── benchmark/page.tsx     # Proof (screen 8)
│   ├── components/
│   │   ├── PhoneFrame.tsx  HourlyBars.tsx  SplitBar.tsx  WhyCard.tsx  StrategyCard.tsx
│   │   ├── PolicyChecks.tsx  ActionLive.tsx  ResultCard.tsx  AgentTrace.tsx  MicButton.tsx
│   ├── lib/api.ts  lib/types.ts   # types mirror section 15 exactly
│   └── public/
└── n8n/workflows/send_campaign.json   # optional
```

---

## 6. Tech stack and setup

| Layer | Choice | Version |
|---|---|---|
| Backend | Python 3.11+, FastAPI, Uvicorn, SQLAlchemy 2, Pydantic 2 | latest |
| Data / ML | pandas, numpy, pyarrow, LightGBM, scipy, statsmodels | latest |
| Foundation model | `chronos-forecasting` (2.3.x; pulls `torch` ≥ 2.2 and `transformers`), CPU torch wheel, model `amazon/chronos-bolt-small` (48M params) | pin the version you test |
| Calendar | `holidays` (≥ 0.107) with `categories=("public","optional")`, `subdiv="KA"` | |
| DB | PostgreSQL 16 in Docker | |
| Frontend | Next.js 14+ (app router), TypeScript, Tailwind CSS | |
| Speech | Sarvam AI REST: `POST https://api.sarvam.ai/speech-to-text` (model `saaras:v4`), `POST https://api.sarvam.ai/text-to-speech` (model `bulbul:v3`), header `api-subscription-key` | |
| LLM | One of: Anthropic, OpenAI, Gemini, Sarvam chat. Chosen by `LLM_PROVIDER` | |
| Workflow | n8n (optional, Docker) | |

**.env.example**
```
DATABASE_URL=postgresql+psycopg://vs:vs@localhost:5432/vyaparsaathi
DEMO_NOW=2026-10-30T20:05:00+05:30
DEMO_MERCHANT_ID=M_KOR_RES_001
DATA_SEED=42
LLM_PROVIDER=anthropic            # anthropic | openai | gemini | sarvam | none
LLM_MODEL=                        # e.g. the model your key supports
LLM_API_KEY=
SARVAM_API_KEY=
SARVAM_STT_MODEL=saaras:v4
SARVAM_TTS_MODEL=bulbul:v3
SARVAM_TTS_SPEAKER=priya          # try a few: shubh, priya, neha, rahul; pick the most natural Hindi
BASELINE_MODEL=lgbm               # lgbm | chronos_bolt | median ; set from the seed-7 comparison (section 16)
CHRONOS_MODEL=amazon/chronos-bolt-small   # or a local path; chronos-bolt-tiny if CPU latency is too high
CHRONOS_DEVICE=cpu
HF_HUB_OFFLINE=1                  # after the weights are downloaded once; no network at runtime
N8N_WEBHOOK_URL=                  # empty = in-process executor
OFFLINE_MODE=0                    # 1 = no external calls; templates + browser speech
```

**Quickstart (README)**
```
docker compose up -d db
python -m generator.fetch_weather        # once; output is committed, skip if file exists
python -m generator.build_calendar       # once; committed
python -m generator.build_dataset --seed 42
python -m generator.load_db
python -m app.engine.baseline --prefetch-bolt  # once, online: downloads Chronos-Bolt weights to the HF cache (from backend/)
python -m app.engine.baseline --train-lgbm     # trains + caches LightGBM models (from backend/)
uvicorn app.main:app --reload --port 8000      (from backend/)
npm run dev                                     (from frontend/, port 3000)
python -m benchmark.run --seed 42
```

---

## 7. Data

### 7.1 Real public data we use

| Source | What we take | How |
|---|---|---|
| **Open-Meteo Historical Weather API** | Hourly precipitation (mm) and temperature for each locality, 1 Oct 2025 to 30 Oct 2026 | `https://archive-api.open-meteo.com/v1/archive?latitude=..&longitude=..&start_date=2025-10-01&end_date=2026-10-30&hourly=precipitation,temperature_2m&timezone=Asia%2FKolkata`. The archive lags a few days; fill the last days with `https://api.open-meteo.com/v1/forecast?...&past_days=7`. Fetch **once** and commit the CSV (the free API has daily limits). |
| **`holidays` Python library** | Indian public + optional holidays, plus Karnataka-specific (Ugadi, Ganesh Chaturthi, Makar Sankranti) | `holidays.country_holidays("IN", subdiv="KA", years=[2025,2026], categories=("public","optional"))`. Also add Valentine's Day (14 Feb) and Dhanteras manually; mark them `source=manual`. |
| **GDELT** (optional, stretch) | Live news check for "bandh / strike / curfew" in a city | Not needed for the demo. Disruption days in our data are synthetic and labelled. |

**What we say to judges about data:** "No public dataset has merchant-level, hourly, payer-level Indian payments with nearby peers. That is exactly what only Paytm has, and it's why the Peer-Shock Test is a Paytm-only feature. So we built a synthetic world driven by real Bengaluru weather and the real festival calendar, and we prove the engine on it with planted shocks. The data adapter swaps to a Paytm sandbox without changing the engine."

### 7.2 Synthetic world (`generator/config/world.yaml`)

```yaml
date_start: 2025-10-01
date_end:   2026-10-30          # Friday; demo day
timezone: Asia/Kolkata
seeds: {dev: 7, test: 42}        # tune on 7, report benchmark on 42
localities:
  - {id: KOR, city: Bengaluru, name: Koramangala,   lat: 12.9352, lon: 77.6245, txn_level: true}   # demo cluster
  - {id: IND, city: Bengaluru, name: Indiranagar,   lat: 12.9784, lon: 77.6408, txn_level: false}
  - {id: JAY, city: Bengaluru, name: Jayanagar,     lat: 12.9308, lon: 77.5838, txn_level: false}
  - {id: KOT, city: Pune,      name: Kothrud,       lat: 18.5074, lon: 73.8077, txn_level: false}
  - {id: MAL, city: Jaipur,    name: Malviya Nagar, lat: 26.8549, lon: 75.8243, txn_level: false}
merchants_per_locality:          # 70 per locality, 350 total
  restaurant: 14
  kirana: 12
  cafe: 10
  sweet_shop: 8
  pharmacy: 8
  salon: 6
  apparel: 6
  electronics: 6
placement_radius_km: 1.5          # random points around locality centre
```

`txn_level: true` means we generate individual transactions with payer IDs (needed for regular-customer analysis). For the other localities we generate the same demand model, but store only hourly aggregates (needed for peers and benchmark). This keeps the dataset at about 2.6M transactions plus 2.2M hourly rows. A `--full` flag generates transactions everywhere if laptops can handle it.

### 7.3 Demand model (`generator/demand.py`, numbers in `effects.yaml`)

For merchant m, date d, hour h:

```
λ(m,d,h) = base_m × hour_profile[type][h] × dow[type][weekday(d)] × season[type][month(d)]
           × trend_m(d) × festival_mult(type, d) × rain_mult_m(type, h, precip(d,h))
           × shock_mult(m, d, h) × noise,   noise ~ Gamma(shape=20, scale=1/20)

transactions ~ Poisson(λ)
ticket ~ LogNormal(μ_type, σ_type), rounded to ₹1 (₹5 for restaurants/cafés)
payment_status: success with p = 0.985 (failure shocks lower this)
```

- `rain_mult_m = exp(β_m × min(precip_mm, 10) / 10)` only when `precip ≥ 1 mm/h`. β_m varies by merchant: `β_m = β_type × LogNormal(0, 0.35)`. This heterogeneity is what makes partial pooling useful.
- Rain also lifts delivery-style demand for restaurants and cafés late evening. Keep it simple: restaurants get a smaller rain penalty after 21:00.

**`effects.yaml` (assumptions; these are inputs the engine must recover, not facts)**

```yaml
open_hours:      {restaurant: [11,23], kirana: [7,22], cafe: [8,23], sweet_shop: [9,22],
                  pharmacy: [8,23], salon: [10,21], apparel: [11,22], electronics: [11,21]}
daily_txn_base:  {restaurant: 110, kirana: 160, cafe: 140, sweet_shop: 80, pharmacy: 90,
                  salon: 20, apparel: 25, electronics: 8}
ticket_lognorm:  {restaurant: [5.70, 0.45], kirana: [5.10, 0.70], cafe: [5.30, 0.40],
                  sweet_shop: [5.60, 0.60], pharmacy: [5.40, 0.70], salon: [6.20, 0.50],
                  apparel: [7.20, 0.60], electronics: [8.30, 0.80]}   # exp(5.7) ≈ ₹300
rain_beta_type:  {restaurant: -0.30, kirana: -0.08, cafe: -0.35, sweet_shop: -0.20, pharmacy: 0.0,
                  salon: -0.45, apparel: -0.40, electronics: -0.30}  # at 10 mm/h; ≈ -26% for restaurant
dow_profile:     # Mon..Sun multipliers; Friday/Saturday evenings strong for restaurants
  restaurant: [0.85, 0.85, 0.90, 0.95, 1.20, 1.35, 1.25]
  # ... fill the rest with sensible values (AI may propose; keep within 0.7–1.4)
festival_effects:   # multiplier and day offsets around the festival date (0 = festival day)
  sweet_shop: {Diwali: {mult: 2.6, days: [-3, 0]}, Raksha Bandhan: {mult: 2.0, days: [-2, 0]},
               Holi: {mult: 1.6, days: [-2, 0]}, Ganesh Chaturthi: {mult: 1.5, days: [-1, 0]}}
  restaurant: {Diwali: {mult: 0.7, days: [0, 0]}, New Year's Day: {mult: 1.5, days: [-1, -1]},
               Dussehra: {mult: 1.2, days: [0, 0]}}
  apparel:    {Diwali: {mult: 1.8, days: [-10, -1]}, Id-ul-Fitr: {mult: 1.5, days: [-5, -1]}}
  electronics: {Diwali: {mult: 1.7, days: [-10, -1]}, Dhanteras: {mult: 2.0, days: [0, 0]}}
  flower_like: {}                # not in our 8 types; ignore
customers:
  pool_size:      {restaurant: 1800, kirana: 1500, cafe: 2000, sweet_shop: 1500, pharmacy: 1400,
                   salon: 400, apparel: 900, electronics: 500}
  regular_share_of_txns: {restaurant: 0.35, kirana: 0.55, cafe: 0.40, sweet_shop: 0.30,
                          pharmacy: 0.45, salon: 0.50, apparel: 0.20, electronics: 0.10}
  regulars_fraction_of_pool: 0.05     # 5% of customers are regulars
  opt_in_rate: 0.6                    # consent flag for offers/messages
```

**Customers** (`generator/customers.py`, transaction-level localities only): each merchant has a pool of hashed payer IDs (`P_<merchant>_<n>`, then SHA-1 truncated). Regulars have a preferred weekday and hour band and visit with high probability on it. Each hour, the regular-share of transactions is filled by regulars due that day; the rest is sampled from non-regulars weighted by a Zipf-like propensity.

### 7.4 Database schema (Postgres)

```sql
-- reference
localities(id text pk, city text, name text, lat float, lon float)
merchants(id text pk, name text, category text, locality_id text, lat float, lon float,
          opened_on date, language text default 'hi-en')
merchant_policy(merchant_id text pk, price_band_pct float default 10, margin_floor_pct float default 20,
                daily_offer_budget int default 300, quiet_after_hour int default 22,
                autonomy_level text default 'L2', allow_price_changes bool default true)
products(id text pk, merchant_id text, name text, category text, mrp int, price int, cost int,
         is_combo bool default false)                -- Tier 2, only demo merchants need rows
customers(payer_hash text, merchant_id text, first_seen date, is_regular bool,
          opted_in bool, primary key(payer_hash, merchant_id))

-- facts
transactions(txn_id text pk, merchant_id text, ts timestamptz, amount int, payer_hash text,
             status text, product_id text null)       -- only txn-level localities
hourly(merchant_id text, date date, hour int, revenue int, txns int, success_txns int,
       regular_txns int, new_txns int, unique_payers int, primary key(merchant_id, date, hour))

-- context (real + synthetic)
weather_hourly(locality_id text, ts timestamptz, precip_mm float, temp_c float, source text)
festivals(date date, name text, scope text, source text)        -- source: holidays | manual
disruptions(city text, date date, kind text, severity float, source text default 'synthetic')

-- app state
actions(id text pk, merchant_id text, kind text, params jsonb, status text,  -- draft|live|ended|undone|blocked
        created_at timestamptz, window_start timestamptz, window_end timestamptz,
        expected jsonb, policy jsonb)
action_targets(action_id text, payer_hash text, arm text, returned bool null, spend int null)  -- arm: treat|holdout
audit_log(id serial pk, ts timestamptz, merchant_id text, actor text, event text, payload jsonb)
merchant_memory(merchant_id text, key text, value jsonb, updated_at timestamptz,
                primary key(merchant_id, key))
past_campaigns(id text pk, merchant_id text, kind text, category text, n_treat int, n_hold int,
               treat_rate float, hold_rate float, date date)   -- synthetic history for uplift priors

-- hidden from the engine (benchmark only)
shock_labels(id text pk, merchant_id text null, city text null, date date, start_hour int, end_hour int,
             kind text, true_effect_pct float, scope text)  -- scope: merchant|locality|city
```

### 7.5 Demo scenario (`generator/config/scenarios/raju_demo.yaml`)

```yaml
demo_date: 2026-10-30                    # Friday
merchant:
  id: M_KOR_RES_001
  name: Raju Family Restaurant
  category: restaurant
  locality: KOR
  base_daily_revenue_target: 45000       # tune base_m so a normal Friday ≈ ₹45,000
weather_override:                         # demo-day rain is scripted (real archive won't have it yet)
  locality: KOR
  date: 2026-10-30
  hours: {17: 6.0, 18: 9.0, 19: 8.0, 20: 7.0, 21: 4.0}   # mm/h
  label: scripted
lapsed_regulars:
  merchant: M_KOR_RES_001
  friday_evening_regulars: 30            # usual count in 18–22 window
  lapse_start: 2026-10-09                # 3 weeks before; a group stops coming
  lapse_count: 16                        # Friday-evening regulars who stop visiting (30 → ~14)
  # The offer segment (lapsed customers, definition in 8.5) also includes natural churn,
  # so expect roughly 60–100 opted-in lapsed customers, split 50/50 into treat / holdout.
products:
  - {id: P_RAJU_COMBO, name: Family combo, mrp: 699, price: 649, cost: 290, is_combo: true}
campaign_truth:                          # used only by simulate.py, never by strategy.py
  family_combo_lapsed: {treat_return_p: 0.40, holdout_return_p: 0.15, avg_ticket: 650}
thin_history_merchant:
  id: M_KOR_CAF_NEW
  name: Nayi Dukaan Café
  category: cafe
  opened_on: 2026-10-09                  # 3 weeks of history
targets_check:                           # build_dataset prints these; tune until within range
  evening_drop_pct: [-21, -15]
  peer_drop_pct: [-15, -9]
```

### 7.6 Shocks for the benchmark (`generator/shocks.py`)

All shocks write a row to `shock_labels` with the true effect.

| Kind | Scope | How many (per seed) | Effect |
|---|---|---|---|
| rain | locality | all real rain windows (precip ≥ 1 mm/h for ≥ 2 h in window) | from `rain_beta` model |
| festival | category | all relevant festivals in `festival_effects` | from multipliers |
| bandh | city | 2 per city (random weekdays), whole day | −40% to −70% for all categories (pharmacy −10%) |
| competitor_open | merchant | 10 restaurants/cafés | step change −8% to −15% in evenings from a date onwards |
| lapsed_regulars | merchant | 15 merchants (txn-level only) | a group of regulars stops visiting for 2 to 6 weeks |
| payment_outage | merchant | 8 merchants | success rate falls to 0.6 for 2 to 4 hours |
| none | – | 300 random clean windows | – (false-alarm test) |

`past_campaigns`: generate about 200 historical campaigns across merchants with true uplift drawn from `priors` (section 9.2). The strategy ranker learns uplift from this table.

---

## 8. Why-Engine (Workstream B)

### 8.1 Baseline (`engine/baseline*.py`)

**One interface, two models.** The rest of the engine never knows which model ran.

```python
class Baseline(Protocol):
    name: str                                    # "lgbm" | "chronos_bolt" | "median"
    def hourly(self, merchant_ids: list[str], date: date) -> dict[str, np.ndarray]: ...
        # per merchant: array shape (24, 3) = hourly revenue quantiles [p10, p50, p90] for `date`
    def expected(self, merchant_id, date, h1, h2) -> dict:   # {p10, p50, p90, model}
        # implemented once in baseline.py on top of hourly(); identical for every model
get_baseline(name=BASELINE_MODEL) -> Baseline    # fallback chain: chronos_bolt → lgbm → median
```

`hourly()` takes a **list** of merchants so the shop and all its peers are forecast in one call (one batch for Bolt). Results are cached per `(model, merchant_id, date)`.

**Shared rules (both models, so the comparison is fair):**
- **Cut-off:** only data up to 23:59 of the day before `date` is used. Same-day hours are never input. For the demo, the cut-off is 2026-10-29 23:59.
- **Target:** `hourly.revenue` on a full 24-hour grid; closed hours are 0, not missing.
- **No weather, festival or shock inputs.** The baseline is "a normal day", so the engine can explain deviations. (LightGBM keeps the `is_public_holiday` calendar flag, public category only, not optional holidays. Bolt has no covariates, see below.)
- **Window aggregation:** `expected(m, date, h1, h2)` returns the sum of hourly p10, p50 and p90 over the window. Summing quantiles is not the true window quantile (it assumes the hours move together, so the band is too wide); this applies equally to both models, and the benchmark measures the actual p10–p90 coverage of each.
- The `model` name is returned with every result and shown in the trace.

**A. LightGBM (`baseline_lgbm.py`)**
- LightGBM quantile regression (α = 0.1, 0.5, 0.9), one model set per category.
- Features: `merchant_id` (categorical), `hour`, `weekday`, `week_index`, `month`, `is_public_holiday`.
- Trained on data before the cut-off. Demo: train on everything up to 2026-10-29. Benchmark: monthly rolling origins (section 16.1). Models cached to `backend/models/lgbm/<cutoff>/<category>.txt`.
- Sort the three predictions per hour so p10 ≤ p50 ≤ p90 (separately trained quantiles can cross).

**B. Chronos-Bolt (`baseline_bolt.py`)**
- Package `chronos-forecasting`; load once at startup:
  `BaseChronosPipeline.from_pretrained(CHRONOS_MODEL, device_map=CHRONOS_DEVICE, torch_dtype=torch.float32)`.
- Context per merchant: the last **2,048 hourly values** before the cut-off (about 85 days; that is Bolt's maximum context, and longer input is truncated anyway). Shorter history is passed as is.
- Call `pipeline.predict_quantiles(inputs=[ctx_1, …, ctx_n], prediction_length=24, quantile_levels=[0.1, 0.5, 0.9])` → quantiles of shape `(n, 24, 3)`. These three levels are among Bolt's trained levels, so no interpolation happens. 24 is within Bolt's 64-step limit.
- Clip negatives to 0 and force 0 for the merchant's closed hours (`open_hours`).
- Zero-shot: no training, no per-category models. Weights must be in the local HF cache before going offline (`--prefetch-bolt`, `HF_HUB_OFFLINE=1`).

**Known differences to expect (the benchmark checks them; do not hide them):**
| | LightGBM | Chronos-Bolt |
|---|---|---|
| Holidays | `is_public_holiday` feature | not used (univariate); expect worse fits on holidays |
| Recent level shifts (e.g. a lapse that started 3 weeks ago, a competitor opening) | `week_index` is a weak trend signal; trees extrapolate flat | reads the recent context directly, so it is likely to absorb part of a recent drop into "normal"; that shrinks `shop_part` |
| Past shocks in the history | in the training data | in the context window |
| Cost | training per category (and per cut-off in the benchmark) | none; inference only, CPU |
| Latency target | < 50 ms per call (cached models) | < 1.5 s per batch of shop + peers on the demo laptop; if slower, use `chronos-bolt-tiny` or pre-compute the demo date at startup |

- **Fallback** (`baseline_median.py`, used if the chosen model fails to load or errors): median of the same weekday and hours over the last 8 weeks, excluding public holidays. Quantiles: p10/p90 of the same 8 values. The trace shows `baseline: median (fallback)`.

**Drop detection:** a window is flagged if `actual < sum(p10)` or `shop_change ≤ −8%`, where `shop_change = actual / p50 − 1`. Default window for evening questions: 18:00 to 22:00. If the question names hours, use those. If the date is today, use hours up to `DEMO_NOW`.

### 8.2 Peer-Shock Test (`engine/peer_shock.py`)

```
peers(m) = merchants with same category, excluding m and merchants opened < 8 weeks ago,
           within radius r; start r = 2 km, grow by 1 km up to 5 km until |peers| ≥ 10.
If |peers| < 10 at 5 km → state "no_peers" (do not show a split; say so).

For each peer p: change_p = actual_p(window) / expected_p50(window) − 1    # same baseline model as the shop
peer_change  = median(change_p)            # robust to one weird shop
peer_iqr     = [Q1, Q3] of change_p
market_part  = peer_change
shop_part    = shop_change − peer_change
```

Show peers only as an aggregate ("14 similar restaurants within 2 km"). Never return peer names or IDs to the frontend.

### 8.3 Context flags (`engine/context.py`)

| Flag | Rule |
|---|---|
| rain | precip ≥ 1.0 mm/h in at least 2 hours of the window (or the hour before it) at the merchant's locality |
| festival | a festival within `days` offsets of `festival_effects[category]` (falls back to "public holiday" flag) |
| disruption | row in `disruptions` for the merchant's city and date |
| none of the above | "unexplained market-wide change" if `abs(market_part) ≥ 5%` |

### 8.4 Effect ranges with partial pooling (`engine/pooling.py`)

For a factor f (e.g. rain), find **comparable windows** in the past: same weekday group (Mon–Thu, Fri–Sun), same hour band, f flagged, no other flag.

```
shop samples    S = {change_m(w)} over comparable windows of this shop          n_s = |S|
peer samples    P = {change_p(w)} over comparable windows of peers              n_p = |P|
k = 8                                                     # pooling strength
w = n_s / (n_s + k)
mean = w × mean(S) + (1 − w) × mean(P)      (if n_s = 0, mean = mean(P))
sd   = sqrt(w × var(S) + (1 − w) × var(P))  (if n_s < 2, use var(P))
range = [mean − 1.28 × sd, mean + 1.28 × sd]   # ~80% range, shown as "usually −9% to −15%"
basis = {shop_n: n_s, peer_n: n_p}
```

**Confidence states:**
- `ok`: n_s + n_p ≥ 8 and range width ≤ 20 points
- `wide`: enough samples but range width > 20 points → show the range, say "andaaza kam pakka hai"
- `thin_history`: shop has < 6 weeks of data → do not compute shop-level baseline; say "not enough history yet", show the peer range instead
- `no_peers`: fewer than 10 peers within 5 km

**Matching market part to causes:** if the rain flag is on and `market_part` falls inside the rain range (±3 points), the status is `explains_market`. If it's outside, the status is `partial`, and we add "something else also affected the whole area". The same applies to festival and disruption.

### 8.5 Shop-specific drivers (`engine/drivers.py`)

Only for txn-level merchants. Decompose the window's revenue change vs the same window over the last 8 same weekdays (median):

```
revenue = (regular_txns + other_txns) × avg_ticket
contrib_regulars = (regular_txns_now − regular_txns_usual) × usual_ticket
contrib_others   = (other_txns_now − other_txns_usual)     × usual_ticket
contrib_ticket   = (avg_ticket_now − usual_ticket)          × txns_now
contrib_failures = failed_txns_now × usual_ticket  (only if failure rate > 2× usual)
```

Report each driver as a share of `shop_part` (in % points). The top driver is the headline ("regular customers nahi aaye: usually ~30, aaj 14").

**Definitions:** a *regular* has ≥ 4 visits to this merchant in the previous 56 days. A *Friday-evening regular* has ≥ 2 visits in the same window over the last 8 same weekdays. A *lapsed customer* (the offer segment) has ≥ 3 visits in the 90 days before the last 21 days, and no visit in the last 21 days.

### 8.6 Why card output (`engine/why.py`)

```json
{
  "merchant_id": "M_KOR_RES_001",
  "date": "2026-10-30",
  "window": {"start_hour": 18, "end_hour": 22},
  "actual": 16550,
  "expected": {"p10": 17800, "p50": 20200, "p90": 22600},
  "baseline_model": "lgbm",
  "shop_change_pct": -18.1,
  "peer": {"n": 14, "radius_km": 2, "median_change_pct": -12.3, "iqr_pct": [-15.0, -9.8]},
  "split": {"market_pct": -12.3, "shop_pct": -5.8},
  "factors": [
    {"id": "rain", "label_hi": "Baarish (5 baje se)", "evidence": "Peers within 2 km −12% same hours",
     "effect_range_pct": [-15.2, -8.9], "basis": {"shop_n": 6, "peer_n": 84}, "status": "explains_market"},
    {"id": "festival", "label_hi": "Tyohaar", "evidence": "Aaj koi tyohaar nahi", "status": "none"},
    {"id": "disruption", "label_hi": "Bandh / strike", "evidence": "Koi khabar nahi", "status": "none"}
  ],
  "shop_drivers": [
    {"id": "regulars_missing", "usual": 30, "actual": 14, "contribution_pts": -4.9},
    {"id": "ticket_size", "usual": 312, "actual": 309, "contribution_pts": -0.4}
  ],
  "confidence": {"state": "ok", "note": null},
  "data_label": "synthetic"
}
```

(Example values. Real values come from the engine.)

---

## 9. Strategy engine (`engine/strategy.py`)

### 9.1 Playbook (P0 implements the first three)

| id | Action | Target | Applies when |
|---|---|---|---|
| `combo_lapsed` | Time-boxed combo offer to lapsed regulars | opted-in lapsed customers (8.5) | top driver = regulars_missing |
| `flat_discount` | Flat X% off all bills in the window | everyone (walk-ins) | always (shown as comparison) |
| `delivery_combo_rain` | Delivery combo during expected rain | opted-in regulars | rain forecast for today/tomorrow |
| `price_nudge_up` | Raise price by 3–5% on a high-demand item | item | demand ≥ p90 for 3 h and price < MRP (P1) |
| `stock_up` | Stock up note before festival/rain | merchant only | festival in next 3 days (P1) |
| `winback_message` | Message only, no discount | opted-in lapsed | cheap fallback |

### 9.2 Expected incremental profit

```
Targeted offer (combo_lapsed, delivery_combo_rain):
  n      = size of opted-in target segment (after holdout split: n_treat)
  p_c    = return rate without offer   (from past_campaigns hold_rate, pooled by kind×category)
  p_t    = return rate with offer      (from past_campaigns treat_rate, pooled)
  T      = avg ticket of the offer item, g = gross margin = (price − cost)/price, c = discount per redemption
  E[profit] = n_treat × [ (p_t − p_c) × (T×g − c)  −  p_c × c ]      # second term: people who'd come anyway still use the offer
  E[cost]   = n_treat × p_t × c                                        # must be ≤ daily_offer_budget

Flat discount d on all bills in window:
  B = expected bills in window (from baseline), e = extra-bill uplift for discount d (prior: e = 0.6 × d)
  E[profit] = B × e × T × (g − d)  −  B × T × d
```

Partial pooling for uplift: same formula as 8.4, with k = 5, over `past_campaigns` of the same kind (merchant's own → category in city → global). If fewer than 5 campaigns exist, use the priors below.

**Priors (assumptions, `effects.yaml: priors`):** `combo_lapsed: p_t 0.35, p_c 0.15`, `winback_message: p_t 0.22, p_c 0.15`, `delivery_combo_rain: p_t 0.25, p_c 0.12`, restaurant gross margin 0.55.

Output: options sorted by `expected_profit`, each with `expected_profit`, `expected_cost`, `n_target`, `assumptions` (p_t, p_c, source = "your past campaigns" | "similar shops" | "default"), and a policy result.

---

## 10. Policy engine (`engine/policy.py`)

A pure function `check(action, merchant_policy, context) → {passed: bool, checks: [{id, passed, detail_hi}]}`.

| id | Rule |
|---|---|
| `mrp_cap` | No resulting price above the product's MRP |
| `price_band` | Any price change within ±`price_band_pct` |
| `margin_floor` | Offer price leaves margin ≥ `margin_floor_pct` |
| `budget` | `expected_cost` ≤ `daily_offer_budget` (also hard cap at execution: stop redemptions when spent) |
| `consent` | Targets only `customers.opted_in = true` |
| `quiet_hours` | No messages after `quiet_after_hour` or before 9:00 |
| `autonomy` | L1: never execute; L2: needs explicit approval; L3: auto only if all checks pass and cost ≤ 50% of budget |
| `escalate` | Disputes, refunds, fraud flags → never auto; hand to human with a case summary |

If a check fails: try to **shrink** (smaller segment or shorter window) once, re-check; if still failing → status `blocked`, explain why in Hinglish.

---

## 11. Execution, simulation, measurement

### 11.1 Executor (`actions/executor.py`)

1. On approve: freeze the target list, randomly split 50/50 into `treat` and `holdout` (seeded by `action_id`). Write `action_targets`.
2. Call `mock_paytm.create_offer(...)` and `mock_paytm.send_message(...)` for treat customers (logs only). If `N8N_WEBHOOK_URL` is set, POST the action JSON there instead and let n8n call the mock endpoints.
3. Write `audit_log` events: `approved`, `offer_created`, `messages_sent`.
4. Undo: status `undone`, `mock_paytm.cancel_offer`, audit row.

### 11.2 Simulator (`engine/simulate.py`, demo control)

`POST /api/demo/simulate/{action_id}` plays the window forward: each target returns with probability `campaign_truth.treat_return_p` (treat) or `holdout_return_p` (holdout), spend ~ LogNormal around `avg_ticket`. Seeded, so the demo is repeatable. This is the only place that reads `campaign_truth`.

### 11.3 Measurement (`engine/measure.py`)

```
rate_t = returned_t / n_t ,  rate_h = returned_h / n_h
incremental_bills  = n_t × (rate_t − rate_h)
incremental_profit = incremental_bills × T × g − (returned_t × c)
Wilson 80% intervals for both rates; if they overlap → note "chhota sample, abhi early signal hai"
```

Also store the result in `merchant_memory` under `last_results.combo_lapsed` (used next time by the strategy ranker).

---

## 12. Agent (Workstream B2)

### 12.1 Intents (`agent/intents.py`)

| Intent | Examples | Pipeline |
|---|---|---|
| `WHY` | "sales kam kyun", "why are sales down", "kya hua aaj" | summary → explain_change → reply (+ why_card) |
| `RECOMMEND` | "kya karun", "kya karna chahiye", "suggest karo" | explain_change (cached) → rank_strategies → check_policy → reply (+ strategy_card, pending_action) |
| `APPROVE` | "haan", "kar do", "chalu karo", "ok", "yes" | only if a `pending_action` exists → execute → reply (+ action_live) |
| `MODIFY` | "budget 200 karo", "sirf 9 baje tak" | update params → re-check policy → reply |
| `UNDO` | "band karo", "ruko", "cancel" | undo → reply |
| `BRIEF` | "aaj ka report", "morning brief" | brief → reply (+ brief_card) |
| `OTHER` | anything else | LLM tool-calling with read-only tools (section 12.3), max 3 tool calls |

**Classification:** run the keyword rules first (a fast regex over Hinglish/English synonyms). If no rule matches, or more than one does, call the LLM with `prompts/classify.md` (JSON output). In `OFFLINE_MODE`, if the keywords don't decide, reply with a clarifying question.

### 12.2 Conversation state (`agent/memory.py`)

Per merchant session: `{lang, last_why (card), pending_action_id, last_intent, history (last 6 turns)}`. Merchant memory table holds durable facts: `prefers_language`, `dislikes_heavy_discounts`, `top_margin_item`, `quiet_after_hour`, `last_results.*`.

### 12.3 Tools (`agent/tools.py`)

Every tool returns JSON and is wrapped by `trace.record(name, args, ms, summary)`.

```json
[
 {"name": "get_summary", "description": "Today's sales vs a normal same weekday for the merchant",
  "input_schema": {"type":"object","properties":{"merchant_id":{"type":"string"},"date":{"type":"string"}},"required":["merchant_id","date"]}},
 {"name": "explain_change", "description": "Why-Engine: split a sales change into market-wide vs shop-specific, with causes and ranges",
  "input_schema": {"type":"object","properties":{"merchant_id":{"type":"string"},"date":{"type":"string"},
   "start_hour":{"type":"integer"},"end_hour":{"type":"integer"}},"required":["merchant_id","date"]}},
 {"name": "rank_strategies", "description": "Rank possible actions by expected incremental profit; includes policy checks",
  "input_schema": {"type":"object","properties":{"merchant_id":{"type":"string"},"date":{"type":"string"}},"required":["merchant_id","date"]}},
 {"name": "get_weather", "description": "Hourly rain and temperature for the merchant's area (past or forecast)",
  "input_schema": {"type":"object","properties":{"merchant_id":{"type":"string"},"date":{"type":"string"}},"required":["merchant_id","date"]}},
 {"name": "get_calendar", "description": "Festivals and holidays near a date, with expected effect for this category",
  "input_schema": {"type":"object","properties":{"merchant_id":{"type":"string"},"date":{"type":"string"},"days_ahead":{"type":"integer"}},"required":["merchant_id","date"]}},
 {"name": "get_customer_stats", "description": "Regular / new / lapsed customer counts for a window",
  "input_schema": {"type":"object","properties":{"merchant_id":{"type":"string"},"date":{"type":"string"},"start_hour":{"type":"integer"},"end_hour":{"type":"integer"}},"required":["merchant_id","date"]}}
]
```

Write tools (`execute_action`, `undo_action`) are **never** exposed to the LLM. Only the deterministic pipeline calls them, and only after explicit approval.

### 12.4 Agent response (returned by `/api/agent/message` and `/api/voice/turn`)

```json
{
  "reply_text": "Shaam ki sales normal Friday se 18% kam hain. Aas-paas ke 14 restaurants bhi lagbhag 12% gire, baarish ki wajah se. Wo hissa aapki galti nahi. Baaki 6% aapki dukaan ka hai: aapke Friday ke regular customers kam aaye.",
  "lang": "hi-en",
  "intent": "WHY",
  "cards": [{"type": "why_card", "data": { "...": "section 8.6" }}],
  "pending_action": null,
  "trace": [
    {"tool": "get_summary", "ms": 38, "summary": "₹41,120 vs normal ₹45,300"},
    {"tool": "baseline", "ms": 61, "summary": "lgbm: expected ₹20,200 for 18–22"},
    {"tool": "peer_shock", "ms": 54, "summary": "14 peers, median −12.3%"},
    {"tool": "weather", "ms": 12, "summary": "rain 17:00–21:00, up to 9 mm/h"},
    {"tool": "calendar", "ms": 5, "summary": "no festival"},
    {"tool": "drivers", "ms": 40, "summary": "regulars 14 vs usual 30"},
    {"tool": "llm_write", "ms": 900, "summary": "reply written, number guard ok"}
  ],
  "audio_b64": null,
  "data_label": "synthetic"
}
```

Card types: `why_card`, `strategy_card`, `action_live`, `result_card`, `brief_card`, `idk_card`.

### 12.5 Reply writing

The LLM gets: intent, merchant language, merchant memory, and the tool JSON. Use `prompts/write_reply.md`. Limit: 60 words for voice, 90 for chat. If the LLM fails or the Number Guard fails, use `templates.py` (string templates filled from the tool JSON). Templates must exist for every intent, in Hinglish and English.

### 12.6 Number Guard (`agent/number_guard.py`)

Extract every number in the reply (regex for digits, %, ₹, and number words like "das", "baarah" if easy). Each must match a number in the tool JSON after rounding (exact integer, or a percentage within ±0.6 points, or a rupee value within ±1%). If any number doesn't match, reject the reply, log it in the trace, and use the template. Unit-test this.

---

## 13. Voice (Workstream C)

**Backend `voice/sarvam.py`:**
- STT: `POST https://api.sarvam.ai/speech-to-text`, header `api-subscription-key`, multipart fields `file` (wav/webm→wav), `model=saaras:v4`, `language_code=unknown` (auto-detect; Hinglish works) or `hi-IN`. Response field: `transcript`, `language_code`.
- TTS: `POST https://api.sarvam.ai/text-to-speech`, JSON `{text, language_code: "hi-IN", model: "bulbul:v3", speaker: SARVAM_TTS_SPEAKER, pace: 1.05, speech_sample_rate: 22050}`. Response: `audios[0]` is base64 WAV.
- Keep TTS text ≤ 60 words (voice reply), and send the full card to the screen.
- Check the latest field names at docs.sarvam.ai before final wiring; they changed recently.

**Frontend:** record with `MediaRecorder` (push-to-talk), send to `/api/voice/turn`. Convert webm to wav on the backend with `ffmpeg` if Sarvam rejects webm.

**Fallback (OFFLINE_MODE or Sarvam down):** browser `webkitSpeechRecognition` with `lang="hi-IN"` for input, `speechSynthesis` with a Hindi voice for output. The text path through the agent is identical.

Measure and show latency per stage in the trace (STT, engine, LLM, TTS). Target: under 4 s end to end for the WHY turn.

---

## 14. Frontend (Workstream C)

**Reference design:** `VyaparSaathi_demo_wireframe.html` (shared earlier). Six phone screens: Home, Ask, Why, Recommend, Live, Morning report. Keep the plain look: white screens, one blue for actions, red only for drops, green only for success, system font, no gradients, no emoji. Update dates to **Friday 30 Oct** and **Saturday 31 Oct**.

**Layout for the demo laptop:** phone frame (360×740) on the left; on the right an **Agent trace** panel listing each tool call with timing as it happens (judges love seeing this). A small "Synthetic data" tag stays visible on every screen.

**Pages:**
- `/` Home: `GET /summary`, `GET /hourly`; alert row with "Kyun?" button → `/chat` with prefilled question.
- `/chat`: one conversation thread. Renders `cards` by type. Mic button (push-to-talk). Buttons on cards send the same text as voice ("Kar do", "Badlo", "Offer band karo").
- `/brief`: `GET /brief`. Shows result_card and the next suggestion.
- `/benchmark`: `GET /api/benchmark/latest`, a simple table of metrics with a one-line caveat.
- Demo controls (hidden behind `?demo=1`): Reset demo, Simulate evening, Switch merchant (Raju / Nayi Dukaan Café), Offline mode toggle.

**Build order:** first against `contracts/fixtures/*.json` (mock mode `NEXT_PUBLIC_MOCK=1`), then switch to the live API.

---

## 15. API contract (FastAPI, base `http://localhost:8000`)

All dates are `YYYY-MM-DD`; all money in integer rupees; all percentages are numbers like `-18.1`.

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/api/merchants` | – | `[{id, name, category, locality, history_days}]` |
| GET | `/api/merchants/{id}/summary?date=` | – | `{date, revenue_today, revenue_normal, change_pct, bills, bills_change_pct, regular_share, regular_share_usual, alert: {window:{start_hour,end_hour}, change_pct} or null, data_label}` |
| GET | `/api/merchants/{id}/hourly?date=` | – | `{hours: [{hour, today, normal_p50, normal_p10, normal_p90}]}` (today only up to DEMO_NOW) |
| GET | `/api/merchants/{id}/why?date=&start_hour=&end_hour=` | – | Why card (section 8.6) |
| GET | `/api/merchants/{id}/strategies?date=` | – | `{options: [{id, title_hi, description_hi, expected_profit, expected_cost, n_target, assumptions, policy: {passed, checks:[{id, passed, detail_hi}]}}], recommended_id, draft_action_id}` |
| POST | `/api/agent/message` | `{merchant_id, text, lang?, channel: "chat" or "voice"}` | AgentResponse (12.4) |
| POST | `/api/voice/turn` | multipart: `audio`, `merchant_id` | `{transcript, stt_lang, response: AgentResponse, audio_b64}` |
| POST | `/api/actions/{id}/approve` | `{actor: "merchant"}` | `{id, status: "live", n_treat, n_holdout, budget_cap, ends_at, policy}` |
| POST | `/api/actions/{id}/undo` | – | `{id, status: "undone"}` |
| GET | `/api/actions/{id}` | – | full action + targets counts + status |
| GET | `/api/actions/{id}/measure` | – | `{n_treat, returned_treat, rate_treat, rate_treat_ci, n_holdout, returned_holdout, rate_holdout, rate_holdout_ci, incremental_bills, incremental_profit, offer_cost, note_hi}` |
| GET | `/api/merchants/{id}/brief?date=` | – | `{date, yesterday: {...summary}, last_action_result: measure or null, today: {weather_note_hi, festival_note_hi}, suggestion: strategy option or null}` |
| GET | `/api/benchmark/latest` | – | section 16.3 JSON |
| POST | `/api/demo/reset` | – | clears actions, memory, sessions for demo merchants |
| POST | `/api/demo/simulate/{action_id}` | – | runs simulator, returns measure |
| POST | `/mock-paytm/offers` | `{merchant_id, product_id, discount, valid_from, valid_to}` | `{offer_id, status: "created"}` |
| POST | `/mock-paytm/messages` | `{merchant_id, payer_hashes:[], template_id, text}` | `{queued: n}` |
| DELETE | `/mock-paytm/offers/{offer_id}` | – | `{status: "cancelled"}` |

Errors: `{"error": {"code", "message_hi", "message_en"}}` where code is one of THIN_HISTORY, NO_PEERS, NO_PENDING_ACTION, POLICY_BLOCKED, NOT_FOUND, with HTTP 4xx. The frontend shows `message_hi`.

---

## 16. Shock-Injection Benchmark (Workstream A2)

### 16.1 Procedure

1. Generate the world with **test seed 42** (we tune only on dev seed 7; never tune on 42).
2. **Evaluation period:** windows dated 2026-01-01 to 2026-10-30, so every merchant has at least 3 months of history for both models.
3. **Baselines, same cut-off rule for both (8.1):**
   - LightGBM: **monthly rolling origins.** Train one model set per month with cut-off = last day of the previous month; evaluate that month's windows with it. (Retraining before every single window is not feasible in the time we have; the monthly model never sees the evaluated month.)
   - Chronos-Bolt: zero-shot; the context ends at 23:59 the day before each window (exact cut-off, no retraining needed).
4. For every labelled shock window (section 7.6) and 300 clean windows: run `explain_change` through the **same adapter the app uses**, **once per baseline** (`--baselines lgbm,chronos_bolt`). Same windows, same seed, same peers; only the baseline changes. The engine never sees `shock_labels`.
5. Score against `shock_labels`.
6. **Choosing the app default:** run the comparison on **dev seed 7**, pick `BASELINE_MODEL` by lowest mean weighted quantile loss on clean windows (tie-break: higher cause accuracy, then latency), and freeze it. Then run seed 42 and report **both** models, whichever wins there.

### 16.2 Metrics (`benchmark/metrics.py`)

All metrics are computed **per baseline model**.

**Forecast quality (clean windows only, since shock windows have planted effects):**

| Metric | Definition |
|---|---|
| WAPE (p50) | Σ\|actual − p50\| / Σ actual, over clean windows |
| Weighted quantile loss | mean pinball loss at 0.1, 0.5, 0.9, divided by Σ actual (the Chronos/GIFT-Eval style WQL) |
| p10–p90 coverage | % of clean windows with p10 ≤ actual ≤ p90 (nominal 80%; summed hourly quantiles will likely over-cover) |
| Holiday WAPE | WAPE on clean windows that fall on public holidays (Bolt has no holiday input) |
| Latency | median and p95 ms of one `hourly()` call for shop + peers, on the demo laptop |

**Engine quality (same as before, per baseline):**

| Metric | Definition |
|---|---|
| Detection rate | % of shock windows flagged as a drop/spike |
| Cause accuracy (top-1) | % of detected shocks where the top factor/driver = true kind (map: rain→rain, festival→festival, bandh→disruption, lapsed_regulars→regulars_missing, competitor_open→"shop-specific, unexplained", payment_outage→failures) |
| Market vs shop split error | Mean absolute error (points) between `split.market_pct` and the true market-wide effect, for locality/city shocks |
| Range coverage | % of times the true effect falls inside the stated range (target near 80% since ranges are ~80%) |
| False alarm rate | % of clean windows where the engine blamed a cause |
| "I don't know" rate | % of thin-history windows that correctly returned `thin_history` |

### 16.3 Output (`benchmark/results/benchmark.json`)

```json
{"seed": 42, "n_shock_windows": 0, "n_clean_windows": 300,
 "app_baseline": "lgbm",
 "baselines": {
   "lgbm": {
     "forecast": {"wape_p50": 0.0, "wql": 0.0, "coverage_p10_p90": 0.0, "holiday_wape": 0.0,
                  "latency_ms_p50": 0, "latency_ms_p95": 0},
     "engine":   {"detection_rate": 0.0, "cause_accuracy": 0.0, "split_mae_pts": 0.0, "range_coverage": 0.0,
                  "false_alarm_rate": 0.0, "idk_rate": 0.0,
                  "by_kind": {"rain": {"n": 0, "cause_accuracy": 0.0}, "...": {}}}
   },
   "chronos_bolt": { "forecast": {"...": "same fields"}, "engine": {"...": "same fields"},
                     "model_id": "amazon/chronos-bolt-small" }
 },
 "caveat": "Synthetic data with planted causes. Tests the engine's logic, not real-world accuracy."}
```

The top-level engine fields of version 1.0 (`detection_rate`, ...) are dropped in favour of `baselines.<model>.engine`. The `/benchmark` page shows one table with a column per model and highlights `app_baseline`. `report.md` has the same table plus one line per model on where it lost (for example "Bolt: worse on holidays", "LightGBM: slower to adapt after level shifts") taken from `by_kind` and holiday WAPE.

Report whatever the numbers are. If a number is weak, say so and say why; judges trust that more than a perfect score.

---

## 17. Tests and acceptance checks

- `test_baseline.py`: for each of `lgbm`, `chronos_bolt`, `median`: `hourly()` returns shape (24, 3) per merchant, p10 ≤ p50 ≤ p90, no negatives, zero in closed hours, and **no data on or after `date` is read** (feed a series with a spike on `date` and check the forecast is unchanged). Bolt test is skipped with a clear message if weights are not cached.
- `test_baseline_fallback.py`: with `CHRONOS_MODEL` pointing to a missing path, `get_baseline("chronos_bolt")` falls back to lgbm and the trace says so.
- `test_peer_shock.py`: a toy world where all peers drop 10% and the shop drops 15% → market −10, shop −5.
- `test_pooling.py`: n_s = 0 → equals peer mean; n_s large → close to shop mean.
- `test_policy.py`: price above MRP blocked; budget overflow shrinks then blocks; non-opted-in never targeted.
- `test_number_guard.py`: reply with an invented number is rejected.
- `test_strategy.py`: the flat discount has lower expected profit than combo_lapsed under the default priors.
- `test_e2e_demo.py`: reset → WHY → RECOMMEND → APPROVE → simulate → BRIEF, all 200 OK, no hardcoded numbers (compare to engine outputs).
- `make demo-check`: runs `test_e2e_demo.py` plus prints the scenario's `targets_check`.

---

## 18. Team split and timeline (IST)

| Workstream | Owner | Delivers |
|---|---|---|
| A. Data: generator, weather/calendar fetch, DB load, adapter | **Chinmay** | `data/reference/*`, `generator/*`, `load_db.py`, `adapters/synthetic.py` |
| A2. Benchmark | **Chinmay** | `benchmark/*`, final numbers |
| B. Engine: baselines (LightGBM + Chronos-Bolt), peer-shock, pooling, drivers, why, strategy, policy, simulate, measure | **Ishaan** | `backend/app/engine/*` + tests |
| B2. Agent + API: orchestrator, intents, Number Guard, prompts, routes | **Ishaan** (Aditya helps with routes) | `backend/app/agent/*`, `api/*` |
| C. Frontend + voice + demo video | **Aditya** | `frontend/*`, `voice/sarvam.py`, backup video |
| Pitch + Q&A | **Ishaan** (all rehearse) | final 4-minute script |

**Thu 29 Oct**
- 19:00 kickoff (30 min): everyone reads sections 1 to 4, agrees on section 15, creates the repo with the section 5 structure (Ishaan).
- 19:30–23:00: A: fetch weather + calendar, generator v1 for KOR only. B: baseline + peer_shock on a small sample. C: Next.js shell + phone frame + screens 1–3 against fixtures.
- 23:00 checkpoint: dataset for KOR loads into Postgres; `/summary` and `/hourly` live.
- Overnight (optional): A runs the full generation for all localities.

**Fri 30 Oct**
- 09:00–13:00: B: pooling, drivers, why card, strategy, policy. B2: orchestrator + templates. C: screens 4–6, mic + Sarvam STT/TTS. A2: benchmark harness on dev seed 7.
- **13:00 integration checkpoint**: the full Raju flow works in chat (text) end to end.
- 13:00–18:00: simulate + measure + brief; voice end to end; Nayi Dukaan Café thin-history case; benchmark on test seed 42; numbers into pitch.
- **18:00 feature freeze.** After this, only bug fixes.
- 18:00–22:00: offline mode test (Wi-Fi off), record the backup video (full demo, 3–4 min), three full rehearsals, write answers to judge questions.

**Sat 31 Oct**: event. Bring the laptop fully set up, the Docker image pulled, the dataset loaded, a phone hotspot, and the backup video on the desktop and on a USB stick.

If anyone is travelling on 30 Oct, move their P0 items earlier and hand over the rest at 13:00.

**Ask the organisers today:** demo length, whether we present on our laptop, whether there's Wi-Fi, whether Paytm will share any sandbox or sample data at the event, and whether there is on-site building time.

---

## 19. Demo-day safety

| Risk | Fallback |
|---|---|
| No internet | `OFFLINE_MODE=1`: engine is local, replies from templates, browser speech for voice |
| Sarvam slow or down | Browser speech fallback (same agent path); trace shows "fallback" |
| Chronos-Bolt weights missing, torch import fails, or too slow on the laptop | `get_baseline` falls back to LightGBM, then median; trace shows the model actually used. Download weights and run `test_baseline.py` with Wi-Fi off the night before |
| LLM down or rate-limited | Templates (Number Guard always passes); trace shows "template" |
| Data looks wrong on the day | `make demo-reset`, regenerate with seed 42 (about 10 minutes, so do it the night before) |
| Laptop dies | Backup video + second laptop with the same setup (Aditya's) |
| Judge asks a free-form question | `OTHER` intent uses read-only tools; if unsure, the agent says what it can answer |

---

## 20. Prompts

### 20.1 Master prompt for any coding assistant (paste first, with SPEC.md)

```
You are a senior engineer joining Team VyaparSaathi for a hackathon final in 36 hours.
The attached SPEC.md is the single source of truth. Read it fully before writing code.

Rules:
1. Follow the repo structure in section 5 and the API contract in section 15 exactly.
   Never rename fields, endpoints or tables. If you think the contract is wrong, stop
   and write the proposed change as a short note instead of changing it.
2. Every number shown to a merchant must come from engine code. The LLM only phrases.
3. Code must run offline on a laptop (Python 3.11, Postgres 16 in Docker, Next.js 14).
   External calls (LLM, Sarvam, Open-Meteo) must have timeouts and fallbacks.
4. Prefer simple, readable code over clever code. Type hints everywhere. No new heavy
   dependencies without a reason.
5. Write the unit tests listed in section 17 for anything you build.
6. When done, print: files changed, how to run, how to test, and anything left undone.

My workstream is: <PASTE WORKSTREAM NAME FROM SECTION 18>.
Start by listing the files you will create, then build them one by one.
```

### 20.2 Workstream prompts (paste after the master prompt)

**A. Data generator (Chinmay)**
```
Build the synthetic data world described in SPEC.md sections 7.1–7.6.
1. generator/fetch_weather.py: fetch Open-Meteo hourly precipitation and temperature for the
   5 localities in world.yaml, 2025-10-01 to 2026-10-30, timezone Asia/Kolkata; fill the last
   days from the forecast API with past_days; save data/reference/weather_hourly.csv. Retry
   with backoff; skip fetching if the file already exists.
2. generator/build_calendar.py: use holidays.country_holidays("IN", subdiv="KA",
   years=[2025,2026], categories=("public","optional")) plus manual Valentine's Day and
   Dhanteras; save data/reference/festivals.csv with columns date,name,scope,source.
3. merchants.py, customers.py, demand.py, shocks.py, campaigns.py and build_dataset.py
   implementing the demand model in 7.3 with effects.yaml, transaction-level data for KOR and
   hourly aggregates elsewhere, the shocks table in 7.6 (written to shock_labels), ~200
   past_campaigns, and the raju_demo.yaml scenario (7.5) including the scripted demo-day rain,
   the lapsed regulars, the family combo product and the thin-history café.
   Vectorise with numpy; one seed controls everything; must finish in under 10 minutes.
4. build_dataset.py prints the scenario targets_check (evening drop %, peer drop %) so we can
   tune base values until they fall in range.
5. load_db.py: create the schema from section 7.4 and load with COPY; build the hourly table
   for KOR from transactions.
6. backend/app/adapters/base.py (Protocol) and synthetic.py with: get_merchant, list_peers
   (category, lat/lon, radius_km), get_hourly(merchant_id, date_from, date_to),
   get_transactions(merchant_id, start, end), get_customers(merchant_id), get_weather(locality,
   date), get_festivals(date_from, date_to), get_disruptions(city, date), get_products,
   get_past_campaigns. The adapter must NOT expose shock_labels.
```

**A2. Benchmark (Chinmay)**
```
Build benchmark/run.py and benchmark/metrics.py per SPEC.md section 16. It must call the
engine only through the same functions the API uses (app.engine.why.explain_change), read
shock_labels directly from the DB for scoring only, support --seed and
--baselines lgbm,chronos_bolt, and run every window once per baseline (same windows, same
peers). LightGBM uses monthly rolling cut-offs; Chronos-Bolt uses the day-before cut-off.
Compute the forecast metrics (WAPE, WQL, p10–p90 coverage, holiday WAPE, latency) on clean
windows and the engine metrics per baseline. Write benchmark/results/benchmark.json in the
16.3 shape and report.md (one table, a column per model, plus the caveat line).
Pick the app baseline on seed 7 only, then report both models on seed 42.
```

**B. Engine (Ishaan)**
```
Implement backend/app/engine/* per SPEC.md sections 8–11: baseline.py (Baseline protocol,
get_baseline factory with fallback chain chronos_bolt → lgbm → median, window sums, caching),
baseline_lgbm.py (LightGBM quantile 0.1/0.5/0.9 per category, features listed in 8.1, no
weather/festival features, sorted quantiles), baseline_bolt.py (chronos-forecasting
BaseChronosPipeline, chronos-bolt-small on CPU, 2048-hour context ending the day before,
predict_quantiles with prediction_length=24 and quantile_levels [0.1, 0.5, 0.9], one batch
for shop + peers, clip to 0 and closed hours), baseline_median.py, peer_shock.py (8.2), context.py (8.3), pooling.py (8.4 with k=8 and the
confidence states), drivers.py (8.5), why.py (returns exactly the JSON in 8.6), strategy.py
(9.1–9.2, pooling over past_campaigns with k=5, priors fallback), policy.py (section 10,
including shrink-then-block), simulate.py (11.2) and measure.py (11.3 with Wilson intervals).
All functions take a DataAdapter; no raw SQL in the engine. Never hardcode demo numbers.
Write the tests in section 17. Cache trained baseline models to disk.
```

**B2. Agent + API (Ishaan / Aditya)**
```
Implement backend/app/agent/* and backend/app/api/* per SPEC.md sections 12 and 15.
- intents.py: keyword rules for WHY/RECOMMEND/APPROVE/MODIFY/UNDO/BRIEF in Hinglish and
  English, LLM classify fallback using prompts/classify.md (strict JSON).
- orchestrator.py: deterministic pipelines per intent (12.1), conversation state (12.2),
  trace of every tool call with ms (12.4), pending_action handling.
- llm.py: one function chat(messages, tools=None, json=False, timeout=8) supporting
  LLM_PROVIDER = anthropic | openai | gemini | sarvam | none. On any error, raise
  LLMUnavailable so the caller uses templates.
- number_guard.py (12.6) and templates.py (Hinglish + English for every intent).
- OTHER intent: LLM tool calling with only the read-only tools in 12.3, max 3 calls.
- All routes in section 15 with Pydantic models matching the JSON exactly; CORS for
  localhost:3000; /api/demo/reset and /api/demo/simulate.
```

**C. Frontend + voice (Aditya)**
```
Build the Next.js 14 (app router, TypeScript, Tailwind) frontend in SPEC.md section 14, using
the attached VyaparSaathi_demo_wireframe.html as the visual reference (plain, real-app look:
white screens, system font, one blue accent, red only for drops, green only for success, no
gradients, no emoji). Pages: /, /chat, /brief, /benchmark, demo controls behind ?demo=1.
Components: PhoneFrame, HourlyBars, SplitBar, WhyCard, StrategyCard, PolicyChecks,
ActionLive, ResultCard, AgentTrace (right-side panel showing each trace item with ms as it
arrives), MicButton (push-to-talk with MediaRecorder → POST /api/voice/turn; fallback to
webkitSpeechRecognition hi-IN and speechSynthesis when the backend says fallback or
OFFLINE_MODE). lib/types.ts must mirror section 15 exactly. First build against
contracts/fixtures/*.json with NEXT_PUBLIC_MOCK=1, then switch to the live API.
Also implement backend/app/voice/sarvam.py per section 13 (Saaras v4 STT, Bulbul v3 TTS,
header api-subscription-key, 6 s timeout, ffmpeg webm→wav conversion).
```

**Fixtures (anyone, first hour)**
```
Create contracts/fixtures/*.json for every endpoint in SPEC.md section 15, using the Raju
demo story (section 1.1) and the example in 8.6 and 12.4. Values must be internally
consistent (e.g. split.market_pct + split.shop_pct = shop_change_pct). Include why_thin.json
for the thin-history café with confidence.state = "thin_history".
```

### 20.3 Runtime prompts (save in `backend/app/agent/prompts/`)

**`system.md`**
```
You are VyaparSaathi, a business partner for a small Indian shop owner who uses Paytm.
You speak like a sharp, friendly bhai who runs a shop himself: short, plain, respectful.

Language: reply in the merchant's language. Default is Hinglish written in Roman script
(e.g. "Shaam ki sales 18% kam hain"). If the merchant writes in English, reply in English.
No Devanagari unless the merchant uses it.

Hard rules:
- Use ONLY numbers that appear in the TOOL_RESULTS JSON. Never compute, round differently,
  estimate or invent a number. If a number you want is not there, leave it out.
- Never claim a cause for certain. Say "lagta hai", "zyada tar", or give the range.
- If confidence.state is "thin_history" or "no_peers", say clearly that there isn't enough
  history yet and give the peer range if present.
- Never name or describe other shops. Only say "aas-paas ke similar restaurants".
- Never say an action is done unless TOOL_RESULTS shows status "live".
- No emojis, no markdown, no lists in voice replies.
```

**`classify.md`**
```
Classify the merchant's message into one intent. Return strict JSON only:
{"intent": "WHY|RECOMMEND|APPROVE|MODIFY|UNDO|BRIEF|OTHER", "hours": [start,end] | null,
 "modify": {"budget": int | null, "end_hour": int | null} | null}

Context: pending_action_exists = {pending}. Last intent = {last_intent}.
- APPROVE only if pending_action_exists is true and the message agrees ("haan", "kar do",
  "theek hai", "chalu karo", "ok", "yes"). Otherwise OTHER.
- "kyun", "why", "kya hua", "kam kyun" → WHY. "kya karun", "kya karein", "suggest",
  "what should I do" → RECOMMEND. "band karo", "ruko", "cancel", "undo" → UNDO.
- Extract hours if mentioned ("shaam 6 se 10" → [18,22]).
Message: "{text}"
```

**`write_reply.md`**
```
Write the reply for intent {intent} in {lang}. Max {max_words} words. One short paragraph.

Order for WHY: total change for the window → how much is market-wide and why (peers + cause)
→ "wo hissa aapki galti nahi" → the shop-specific part and its top driver.
Order for RECOMMEND: the recommended action and who it targets → expected extra profit
(only if present) → why it beats the flat discount in one line → guardrails passed in one
line → end with the question "Chalu karun?".
Order for APPROVE: confirm it is live, how many customers got it, how many held back to
measure, when it ends, and that the result comes in the morning brief.
Order for BRIEF: yesterday vs normal → result of the last action vs holdout (mention small
sample if note present) → today's outlook → the ready suggestion as a question.

MERCHANT_MEMORY: {memory_json}
TOOL_RESULTS: {tool_json}
```

**`open_qa.md` (OTHER intent)**
```
Answer the merchant's question using the read-only tools if needed (max 3 calls).
If the question is outside the shop's sales, customers, weather, festivals or offers, say
politely what you can help with. Follow all rules in system.md. If after using tools you
still don't know, say so in one sentence.
```

---

## 21. Judge questions to prepare

| Question | Answer |
|---|---|
| "Is this real data?" | "Transactions are synthetic; weather and festivals are real. No public dataset has hourly, payer-level merchant payments with nearby peers; only Paytm has that, which is why the Peer-Shock Test is a Paytm-only feature. The adapter swaps to a sandbox without changing the engine." |
| "How accurate is the Why-Engine?" | Show `/benchmark`: numbers on a held-out seed we never tuned on, plus the caveat that it tests logic, not real-world accuracy. Real accuracy comes from a pilot with holdouts. |
| "What if rain wasn't the reason?" | "We never claim cause. We show peers fell by the same amount in the same hours, and the historical rain range. If peers didn't fall, the engine says the drop is the shop's own." |
| "Isn't peer data a privacy issue?" | "Only aggregates of 10+ shops; no shop is ever named; customers are hashed; messages only to opted-in customers, as DPDP requires." |
| "What stops the agent from doing something stupid?" | Show policy checks: MRP cap, band, margin floor, budget, consent, quiet hours, one-tap undo, audit log. L3 is opt-in. |
| "How does this plug into Paytm?" | "Three adapter calls: transactions, catalogue, peer aggregates; plus the offer and message APIs Paytm already runs for merchants." |
| "Why two baselines? Why not just a foundation model?" | "We didn't want to assume a foundation model wins. LightGBM is trained on our data and uses the holiday calendar; Chronos-Bolt is pretrained and zero-shot. Same windows, same engine: the benchmark shows where each one wins, and we picked the app default on a dev seed before looking at the test seed." Then show the two columns. |
| "LLM cost / latency?" | "Stats run in Python; the LLM only writes 60-word replies. Show the trace with ms per step." |
| "Paytm's AI Soundbox already talks. What's new?" | "It answers what happened. We add why (Peer-Shock), what to do (profit-ranked), doing it (guardrails) and proof (holdout)." |

---

## Appendix A: `localities.csv`

```
id,city,name,lat,lon
KOR,Bengaluru,Koramangala,12.9352,77.6245
IND,Bengaluru,Indiranagar,12.9784,77.6408
JAY,Bengaluru,Jayanagar,12.9308,77.5838
KOT,Pune,Kothrud,18.5074,73.8077
MAL,Jaipur,Malviya Nagar,26.8549,75.8243
```

## Appendix B: Festival dates in our window (from the `holidays` library, checked 29 Oct 2026)

Diwali 2025-10-20 · Guru Nanak Jayanti 2025-11-05 · Christmas 2025-12-25 · New Year 2026-01-01 · Makar Sankranti 2026-01-14 · Republic Day 2026-01-26 · Maha Shivaratri 2026-02-15 · Holi 2026-03-04 · Ugadi 2026-03-19 · Id-ul-Fitr 2026-03-21 · Ram Navami 2026-03-26 · Good Friday 2026-04-03 · Bakrid 2026-05-27 · Muharram 2026-06-26 · Independence Day 2026-08-15 · Onam 2026-08-26 · Raksha Bandhan 2026-08-28 · Janmashtami 2026-09-04 · Ganesh Chaturthi 2026-09-14 · Gandhi Jayanti 2026-10-02 · Dussehra 2026-10-20. Generate the full list with the code in 7.1 rather than typing it.

## Appendix C: Hinglish keyword starter list (`intents.py`)

- WHY: `kyun, kyu, why, kya hua, kam kaise, gir, down kyun, low kyun`
- RECOMMEND: `kya karu, kya karun, kya karein, kya karna, suggest, what should, idea do`
- APPROVE: `haan, ha, kar do, karo, chalu, theek hai, thik hai, ok, okay, yes, done`
- UNDO: `band karo, ruko, cancel, undo, mat karo, hatao`
- BRIEF: `report, brief, aaj ka, subah, summary`
- MODIFY: `budget, sirf, tak, kam karo, zyada karo, baje`
