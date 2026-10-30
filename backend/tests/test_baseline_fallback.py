from datetime import date

from app.engine import baseline, baseline_bolt


def test_missing_bolt_falls_back_to_lgbm(monkeypatch):
    monkeypatch.setattr(baseline_bolt, "CHRONOS_MODEL", "/nonexistent/chronos-model")
    monkeypatch.setattr(baseline_bolt, "_PIPE", None)
    bl = baseline.Fallback(["chronos_bolt", "lgbm", "median"])
    assert bl.hourly(["M_KOR_RES_001"], date(2026, 10, 30))["M_KOR_RES_001"].shape == (24, 3)
    assert bl.name == "lgbm (fallback)"
