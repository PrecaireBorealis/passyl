"""Provider-agnostic LLM client. Any failure raises LLMUnavailable so callers fall back to templates."""
import json
import os

import httpx

from ..config import OFFLINE_MODE, env


class LLMUnavailable(Exception):
    pass


def provider() -> str:
    return "none" if OFFLINE_MODE else env("LLM_PROVIDER", "none")


def _openai_tools(tools):
    return [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                              "parameters": t["input_schema"]}} for t in tools]


def _post(url: str, headers: dict, body: dict, timeout: float) -> dict:
    try:
        r = httpx.post(url, headers=headers, json=body, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError) as e:
        raise LLMUnavailable(f"{provider()}: {e}") from e


def chat(messages: list[dict], system: str | None = None, tools: list[dict] | None = None, json_mode: bool = False,
         timeout: float = 8, max_tokens: int = 400) -> dict:
    """messages: [{role: user|assistant|tool, content, ...}] → {"text", "tool_calls": [{id, name, args}], "raw"}."""
    p, key, model = provider(), env("LLM_API_KEY"), env("LLM_MODEL")
    if p == "none":
        raise LLMUnavailable("LLM_PROVIDER=none or OFFLINE_MODE=1")
    if p in ("openai", "sarvam"):
        base = env("LLM_BASE_URL") or ("https://api.sarvam.ai/v1" if p == "sarvam" else "https://api.openai.com/v1")
        headers = {"api-subscription-key": key or env("SARVAM_API_KEY")} if p == "sarvam" else \
            ({"Authorization": f"Bearer {key}"} if key else {})
        msgs = ([{"role": "system", "content": system}] if system else []) + messages
        body = {"model": model or ("sarvam-m" if p == "sarvam" else "gpt-4o-mini"), "messages": msgs,
                "max_tokens": max_tokens, "temperature": 0.3}
        if tools:
            body["tools"] = _openai_tools(tools)
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        js = _post(f"{base.rstrip('/')}/chat/completions", headers, body, timeout)
        msg = js["choices"][0]["message"]
        calls = [{"id": c["id"], "name": c["function"]["name"], "args": json.loads(c["function"]["arguments"] or "{}")}
                 for c in msg.get("tool_calls") or []]
        return {"text": (msg.get("content") or "").strip(), "tool_calls": calls, "raw": msg}
    if p == "anthropic":
        body = {"model": model or "claude-haiku-5-5", "max_tokens": max_tokens, "messages": messages}
        if system:
            body["system"] = system
        if tools:
            body["tools"] = tools
        js = _post("https://api.anthropic.com/v1/messages",
                   {"x-api-key": key, "anthropic-version": "2023-06-01"}, body, timeout)
        text = "".join(b.get("text", "") for b in js["content"] if b["type"] == "text").strip()
        calls = [{"id": b["id"], "name": b["name"], "args": b["input"]} for b in js["content"] if b["type"] == "tool_use"]
        return {"text": text, "tool_calls": calls, "raw": js["content"]}
    if p == "gemini":
        contents = [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": str(m["content"])}]}
                    for m in messages]
        body = {"contents": contents, "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.3}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        js = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{model or 'gemini-2.5-flash'}:generateContent"
                   f"?key={key}", {}, body, timeout)
        return {"text": js["candidates"][0]["content"]["parts"][0]["text"].strip(), "tool_calls": [], "raw": js}
    raise LLMUnavailable(f"unknown LLM_PROVIDER {p}")


def tool_loop(system: str, user: str, tools: list[dict], run_tool, max_calls: int = 3, timeout: float = 8) -> str:
    """Read-only tool calling for open questions (OpenAI-compatible and Anthropic only)."""
    p = provider()
    if p not in ("openai", "anthropic"):
        raise LLMUnavailable(f"tool calling not wired for {p}")
    messages: list[dict] = [{"role": "user", "content": user}]
    for _ in range(max_calls + 1):
        r = chat(messages, system=system, tools=tools, timeout=timeout)
        if not r["tool_calls"]:
            return r["text"]
        if p == "openai":
            messages.append(r["raw"])
            for c in r["tool_calls"]:
                messages.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(run_tool(c["name"], c["args"]), default=str)})
        else:
            messages.append({"role": "assistant", "content": r["raw"]})
            messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": c["id"],
                                                          "content": json.dumps(run_tool(c["name"], c["args"]), default=str)}
                                                         for c in r["tool_calls"]]})
        max_calls -= len(r["tool_calls"])
        if max_calls <= 0:
            break
    r = chat(messages + [{"role": "user", "content": "Answer now in one or two sentences."}], system=system, timeout=timeout)
    return r["text"]
