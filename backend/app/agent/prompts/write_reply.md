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
