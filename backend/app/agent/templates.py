"""Offline reply templates for every intent, Hinglish and English, filled only from tool JSON (spec 12.5)."""


def _h(h: int) -> int:
    return h % 12 or 12


def _top_driver(card: dict) -> dict | None:
    d = card.get("shop_drivers") or []
    return d[0] if d and d[0]["contribution_pts"] < 0 else None


DRIVER_HI = {"regulars_missing": "aapke regular customers kam aaye", "other_customers": "naye/baaki customers kam aaye",
             "ticket_size": "bill ka size chhota raha", "payment_failures": "payment fail zyada hue",
             "regulars_up": "regular customers zyada aaye"}
DRIVER_EN = {"regulars_missing": "fewer of your regulars came", "other_customers": "fewer other customers came",
             "ticket_size": "bills were smaller", "payment_failures": "more payments failed",
             "regulars_up": "more regulars came"}


def why(card: dict, lang: str) -> str:
    w = card["window"]
    win = f"{_h(w['start_hour'])} se {_h(w['end_hour'])} baje" if lang != "en" else f"{_h(w['start_hour'])} to {_h(w['end_hour'])} pm"
    conf = card["confidence"]["state"]
    peer = card["peer"]
    if conf == "thin_history":
        if lang == "en":
            s = "Not enough history yet to know your normal."
            if peer.get("median_change_pct") is not None:
                s += f" Similar shops nearby moved {peer['median_change_pct']}% in the same hours."
            return s
        s = "Abhi aapki dukaan ka itna data nahi hai ki normal pata chale."
        if peer.get("median_change_pct") is not None:
            s += f" Aas-paas ki similar dukaanon mein isi waqt {abs(peer['median_change_pct'])}% ka badlav hua."
        return s
    ch = card["shop_change_pct"]
    if lang == "en":
        s = f"Sales from {win} are {abs(ch)}% {'below' if ch < 0 else 'above'} a normal day."
    else:
        s = f"{win} ki sales normal se {abs(ch)}% {'kam' if ch < 0 else 'zyada'} hain."
    sp = card.get("split")
    if sp:
        cause = next((f for f in card["factors"] if f["status"] == "explains_market"), None)
        if lang == "en":
            s += f" {peer['n']} similar shops nearby also moved about {abs(sp['market_pct'])}%"
            s += f" ({cause['id']}); that part is not your fault." if cause else "."
            s += f" The other {abs(sp['shop_pct'])}% is your shop's own"
        else:
            s += f" Aas-paas ki {peer['n']} similar dukaanein bhi lagbhag {abs(sp['market_pct'])}% badli"
            s += f", {cause['label_hi'].split(' (')[0].lower()} ki wajah se. Wo hissa aapki galti nahi." if cause else "."
            s += f" Baaki {abs(sp['shop_pct'])}% aapki dukaan ka hai"
        d = _top_driver(card)
        if d:
            s += (f": {DRIVER_EN[d['id']]} ({d['actual']} vs usual {d['usual']})." if lang == "en"
                  else f": {DRIVER_HI[d['id']]} ({d['actual']}, aam taur par {d['usual']}).")
        else:
            s += "."
    elif conf == "no_peers":
        s += " Not enough similar shops nearby to split market vs shop." if lang == "en" else \
            " Aas-paas itni similar dukaanein nahi ki market aur dukaan ka hissa alag kar sakein."
    if conf == "wide":
        s += " The estimate is rough." if lang == "en" else " Andaaza kam pakka hai."
    return s


def recommend(strat: dict, lang: str) -> str:
    rec = next((o for o in strat["options"] if o["id"] == strat.get("recommended_id")), None)
    if not rec:
        return "No safe offer passes the guardrails right now." if lang == "en" else \
            "Abhi koi offer guardrails pass nahi karta. Kuch naya nahi karte."
    flat = next((o for o in strat["options"] if o["id"] == "flat_discount"), None)
    if lang == "en":
        s = f"Suggestion: {rec['title_hi']}, to {rec['n_target']} customers. Expected extra profit ₹{rec['expected_profit']}."
        if flat:
            fp = flat["expected_profit"]
            s += f" A flat 20% off would {'earn' if fp >= 0 else 'lose'} ₹{abs(fp)}."
        return s + " All guardrails pass. Start it?"
    s = f"Meri salah: {rec['title_hi']}, {rec['n_target']} customers ko. Andaazan ₹{rec['expected_profit']} extra munafa."
    if flat:
        fp = flat["expected_profit"]
        s += f" Sab par 20% off se sirf ₹{fp} banega." if fp >= 0 else f" Sab par 20% off se ulta ₹{abs(fp)} ka nuksaan."
    return s + " Saare guardrails pass hain. Chalu karun?"


def approve(live: dict, lang: str) -> str:
    end = live["ends_at"][11:13]
    if lang == "en":
        return (f"Done, the offer is live for {live['n_treat']} customers; {live['n_holdout']} are held back to measure. "
                f"It ends at {_h(int(end))} pm. The result comes in the morning brief.")
    return (f"Ho gaya, offer {live['n_treat']} customers ko chala gaya. {live['n_holdout']} ko jaan-boojh kar nahi bheja, "
            f"taaki asli asar naap sakein. {_h(int(end))} baje band hoga. Result subah ke brief mein.")


def modify(action: dict, lang: str) -> str:
    e = action["expected"]
    if action["status"] == "blocked":
        return "Even after shrinking, a guardrail still fails, so it is blocked." if lang == "en" else \
            "Chhota karne ke baad bhi guardrail fail hai, isliye block kar diya."
    return (f"Updated: {e['n_target']} customers, expected cost ₹{e['expected_cost']}. Start it?" if lang == "en"
            else f"Badal diya: {e['n_target']} customers, andaazan kharcha ₹{e['expected_cost']}. Chalu karun?")


def undo(lang: str) -> str:
    return "Stopped. The offer is cancelled." if lang == "en" else "Band kar diya. Offer cancel ho gaya."


def brief(b: dict, lang: str) -> str:
    y = b["yesterday"]
    parts = []
    if y.get("change_pct") is not None:
        parts.append(f"Yesterday sales were {abs(y['change_pct'])}% {'below' if y['change_pct'] < 0 else 'above'} normal."
                     if lang == "en" else
                     f"Kal ki sales normal se {abs(y['change_pct'])}% {'kam' if y['change_pct'] < 0 else 'zyada'} rahi.")
    r = b.get("last_action_result")
    if r:
        rt, rh = round(100 * r["rate_treat"]), round(100 * r["rate_holdout"])
        parts.append(f"Offer: {rt}% of offered customers came back vs {rh}% without it; extra profit ₹{r['incremental_profit']}."
                     if lang == "en" else
                     f"Offer ka result: offer wale {rt}% customers laute, bina offer wale sirf {rh}%. "
                     f"Extra munafa ₹{r['incremental_profit']}.")
        if "Chhota" in (r.get("note_hi") or ""):
            parts.append("Small sample, early signal." if lang == "en" else "Chhota sample hai, abhi early signal.")
    t = b.get("today") or {}
    if t.get("festival_note_hi"):
        parts.append(t["festival_note_hi"])
    s = b.get("suggestion")
    if s:
        parts.append(f"Next: {s['title_hi']}?" if lang == "en" else f"Aage: {s['title_hi']}?")
    return " ".join(parts)


def no_pending(lang: str) -> str:
    return "There is nothing pending to approve. Ask me what to do first." if lang == "en" else \
        "Abhi koi offer pending nahi hai. Pehle poochiye 'kya karun?'"


def clarify(lang: str) -> str:
    return ("I can explain today's sales, suggest an offer, run it, or give the morning brief. What do you need?"
            if lang == "en" else
            "Main aaj ki sales samjha sakta hoon, offer suggest kar sakta hoon, chala sakta hoon, ya subah ka brief de sakta hoon. Kya chahiye?")


def error(code: str, msg_hi: str, msg_en: str, lang: str) -> str:
    return msg_en if lang == "en" else msg_hi
