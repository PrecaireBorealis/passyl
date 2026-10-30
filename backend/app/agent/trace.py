"""Agent trace: every tool call with its timing, shown in the UI (spec 4.3)."""
import time


class Trace:
    def __init__(self):
        self.items: list[dict] = []

    def record(self, tool: str, ms: int, summary: str) -> None:
        self.items.append({"tool": tool, "ms": int(ms), "summary": summary})

    __call__ = record

    def timed(self, tool: str, fn, summarise=lambda r: ""):
        t0 = time.perf_counter()
        r = fn()
        self.record(tool, (time.perf_counter() - t0) * 1000, summarise(r))
        return r
