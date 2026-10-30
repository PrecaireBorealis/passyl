# Demo script (≈ 4 min) — presenter copy

Open `http://localhost:3000/?demo=1`. Click **Reset demo** first.

1. **Home** — "Friday 30 Oct, 8:05 PM. Raju's sales since 6 pm are well below a normal Friday." Point at the red evening bars. Click **Kyun?**
2. **Ask** — (or hold the mic: "Bhai, aaj sales itni kam kyun hai?"). Point at the trace on the right: normal Friday → 13 nearby restaurants → weather → calendar → regulars. Every line is a real tool call with its time.
3. **Why** — grey = the whole area (rain; peers fell the same hours), red = Raju's own part: his Friday regulars didn't come. "We never claim the cause for certain: we show the peers and the historical rain range."
4. **Recommend** — type/say "Kya karun?". Family combo for lapsed regulars, positive expected profit; flat 20% off loses money and fails the budget guardrail. Show the checks.
5. **Approve** — click **Kar do**. Live: N customers got it, M held back to measure, budget cap, end time, Undo.
6. **Result** — demo controls → **Simulate evening** → Morning Brief for Sat 31 Oct: treated vs holdout return rate, extra profit after offer cost, next suggestion.
7. **Honesty** — switch merchant to **Nayi Dukaan Café**, Poochho → "Aaj sales kam kyun hai?": "not enough history yet", peer range instead.
8. **Proof** — Proof tab: Shock-Injection Benchmark on held-out seed 42, LightGBM vs Chronos-Bolt, with the caveat line.

If the network is down: demo controls → **Offline speech**; replies already fall back to templates.
