from fastapi import APIRouter, File, Form, UploadFile

from ..agent.orchestrator import handle
from ..voice import sarvam

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post("/turn")
async def turn(audio: UploadFile = File(...), merchant_id: str = Form(...)):
    import time
    raw = await audio.read()
    t0 = time.perf_counter()
    stt = sarvam.stt(raw, audio.content_type or "audio/webm")
    stt_ms = int((time.perf_counter() - t0) * 1000)
    if not stt.get("transcript"):
        return {"transcript": "", "stt_lang": None, "fallback": True, "error": stt.get("error"),
                "response": None, "audio_b64": None}
    resp = handle(stt["transcript"], merchant_id, None, "voice")
    resp["trace"].insert(0, {"tool": "stt", "ms": stt_ms, "summary": f"{stt.get('model')}: {stt['transcript'][:40]}"})
    t0 = time.perf_counter()
    tts = sarvam.tts(resp["reply_text"], resp["lang"])
    resp["trace"].append({"tool": "tts", "ms": int((time.perf_counter() - t0) * 1000),
                          "summary": "bulbul ok" if tts.get("audio_b64") else f"fallback: {tts.get('error', '')[:40]}"})
    resp["audio_b64"] = tts.get("audio_b64")
    return {"transcript": stt["transcript"], "stt_lang": stt.get("language_code"), "fallback": False,
            "response": resp, "audio_b64": resp["audio_b64"]}


@router.post("/tts")
def tts_only(body: dict):
    """Speak an already-written reply (used when the text arrived via the browser-speech fallback)."""
    return sarvam.tts(body.get("text", ""), body.get("lang", "hi-en"))
