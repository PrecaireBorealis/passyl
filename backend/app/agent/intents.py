"""Keyword rules first; the LLM only when the rules don't decide (spec 12.1, Appendix C)."""
import json
import re
from pathlib import Path

from .llm import LLMUnavailable, chat

PROMPTS = Path(__file__).parent / "prompts"
# "karo" alone is not an APPROVE word: it collides with "band karo" / "kam karo".
RULES = {
    "UNDO": r"band karo|band kar do|ruko|cancel|undo|mat karo|hatao|\bstop\b",
    "MODIFY": r"budget\s*\d+|budget .*karo|\d+\s*baje tak|sirf\s*\d+|kam karo|zyada karo|badlo|change it",
    "APPROVE": r"\b(haan|haa|han|ha|kar do|kardo|chalu|chalu karo|theek hai|thik hai|ok|okay|yes|done|go ahead|start it)\b",
    "RECOMMEND": r"kya kar[uū]n?|kya karein|kya kare|kya karna|suggest|what should|idea do|kya karoon",
    "WHY": r"kyun|kyu|kyon|\bwhy\b|kya hua|kam kaise|\bgir|down kyun|low kyun|what happened",
    "BRIEF": r"report|brief|subah|summary|hisaab",
}
PRIORITY = ["UNDO", "MODIFY", "APPROVE", "RECOMMEND", "WHY", "BRIEF"]
HINGLISH = re.compile(r"\b(hai|hain|kyun|kyu|kya|karo|karun|aaj|nahi|bhai|haan|kar|do|kam|sales kam|batao|chalu|ruko)\b", re.I)


def language(text: str, previous: str = "hi-en") -> str:
    if re.search(r"[ऀ-ॿ]", text):
        return "hi"
    if HINGLISH.search(text):
        return "hi-en"
    if len(text.split()) <= 3:  # "ok", "morning brief": too short to switch language
        return previous
    return "en" if re.search(r"[a-zA-Z]{3,}", text) else previous


def hours(text: str) -> list[int] | None:
    m = re.search(r"(\d{1,2})\s*(?:baje)?\s*(?:se|to|-|–)\s*(\d{1,2})", text)
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    evening = re.search(r"shaam|sham|evening|raat|night|pm", text, re.I)
    if evening or (a < 11 and b <= 11 and a >= 4):
        a, b = (a + 12 if a < 12 else a), (b + 12 if b < 12 else b)
    return [a, b] if 0 <= a < b <= 24 else None


def modify_params(text: str) -> dict | None:
    out = {}
    if m := re.search(r"budget\s*(?:₹|rs\.?)?\s*(\d+)", text, re.I):
        out["budget"] = int(m.group(1))
    if m := re.search(r"(\d{1,2})\s*baje tak", text, re.I):
        h = int(m.group(1))
        out["end_hour"] = h + 12 if h < 12 else h
    return out or None


def keyword_intents(text: str) -> list[str]:
    t = text.lower()
    return [i for i in PRIORITY if re.search(RULES[i], t)]


def classify(text: str, pending: bool, last_intent: str | None) -> dict:
    found = keyword_intents(text)
    if not pending and "APPROVE" in found:
        found.remove("APPROVE")
    base = {"hours": hours(text), "modify": modify_params(text), "via": "keywords"}
    if len(found) == 1:
        return {**base, "intent": found[0]}
    try:
        prompt = (PROMPTS / "classify.md").read_text().replace("{pending}", str(pending).lower()) \
            .replace("{last_intent}", str(last_intent)).replace("{text}", text)
        r = chat([{"role": "user", "content": prompt}], json_mode=True, timeout=6, max_tokens=120)
        js = json.loads(re.search(r"\{.*\}", r["text"], re.S).group(0))
        intent = js.get("intent", "OTHER")
        if intent == "APPROVE" and not pending:
            intent = "OTHER"
        return {"intent": intent, "hours": js.get("hours") or base["hours"], "modify": js.get("modify") or base["modify"],
                "via": "llm"}
    except (LLMUnavailable, AttributeError, ValueError, KeyError):
        if found:  # several rules matched: the most specific one wins
            return {**base, "intent": found[0]}
        return {**base, "intent": "CLARIFY"}
