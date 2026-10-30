"""Number Guard: every number in a reply must come from the tool JSON (spec 12.6)."""
import re

NUM = re.compile(r"(₹\s?)?(-?\d[\d,]*(?:\.\d+)?)\s*(%|percent|pct|pratishat)?", re.I)
WORDS = {"ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6, "saat": 7, "aath": 8,
         "nau": 9, "das": 10, "gyarah": 11, "baarah": 12, "barah": 12, "pandrah": 15, "bees": 20, "pachaas": 50, "sau": 100}
WORD_RE = re.compile(r"\b(" + "|".join(WORDS) + r")\b", re.I)


def tool_numbers(obj, key: str = "") -> list[float]:
    """Every number in the tool JSON, including numbers inside strings and 12-hour forms of hours."""
    out: list[float] = []
    if isinstance(obj, bool) or obj is None:
        return out
    if isinstance(obj, (int, float)):
        out.append(float(obj))
        if "hour" in key and 0 <= obj <= 24:
            out.append(float(int(obj) % 12 or 12))
        if 0 < abs(obj) <= 1 and isinstance(obj, float):
            out.append(round(100 * obj, 1))  # rates like 0.40 → 40%
    elif isinstance(obj, str):
        for m in NUM.finditer(obj):
            out.append(float(m.group(2).replace(",", "")))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out += tool_numbers(v, k)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out += tool_numbers(v, key)
    return out


def reply_numbers(text: str) -> list[tuple[float, str]]:
    found = []
    for m in NUM.finditer(text):
        kind = "pct" if m.group(3) else "rupee" if m.group(1) else "int"
        found.append((abs(float(m.group(2).replace(",", ""))), kind))
    return found


def matches(value: float, kind: str, pool: list[float]) -> bool:
    absp = [abs(p) for p in pool]
    if kind == "pct":
        return any(abs(value - p) <= 0.6 for p in absp)
    if kind == "rupee":
        return any(abs(value - p) <= 0.01 * max(p, 1) for p in absp)
    # plain numbers: an exact integer from the tools, or the rounding of a non-integer one
    return any(value == p for p in absp) or any(abs(value - p) <= 0.6 for p in absp if p != int(p))


def check(reply: str, tool_json) -> dict:
    pool = tool_numbers(tool_json)
    bad = [f"{v:g}" for v, k in reply_numbers(reply) if not matches(v, k, pool)]
    return {"ok": not bad, "unmatched": bad}
