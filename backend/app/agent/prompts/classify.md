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
