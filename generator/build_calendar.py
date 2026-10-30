"""Indian festival calendar from the `holidays` library (+ manual extras) → data/reference/festivals.csv."""
from datetime import date

import holidays
import pandas as pd

from .common import REF

# Not in the library; dates checked by hand (source=manual).
MANUAL = [
    (date(2026, 2, 14), "Valentine's Day"),
    (date(2025, 10, 18), "Dhanteras"),
    (date(2026, 11, 6), "Dhanteras"),
]
# The library's long names → the short names effects.yaml uses.
ALIASES = {"Eid al-Fitr": "Id-ul-Fitr", "Ganesh Chaturthi / Vinayak Chaturthi": "Ganesh Chaturthi"}
KEY = {"Diwali", "Dussehra", "Holi", "Raksha Bandhan", "Ganesh Chaturthi", "Id-ul-Fitr", "New Year's Day", "Dhanteras"}


def short(name: str) -> str:
    return ALIASES.get(name, name)


def main() -> None:
    rows = []
    for cat in ("public", "optional"):
        cal = holidays.country_holidays("IN", subdiv="KA", years=[2025, 2026], categories=(cat,))
        for d, names in cal.items():
            for n in names.split("; "):
                rows.append({"date": d, "name": short(n), "scope": cat, "source": "holidays"})
    rows += [{"date": d, "name": n, "scope": "optional", "source": "manual"} for d, n in MANUAL]
    df = (pd.DataFrame(rows).sort_values(["date", "scope"]).drop_duplicates(["date", "name"])
          .query("'2025-10-01' <= date.astype('str') <= '2026-12-31'"))
    out = REF / "festivals.csv"
    df.to_csv(out, index=False)
    print(f"wrote {out} ({len(df)} rows)")
    print(df[df["name"].isin(KEY)].to_string(index=False))


if __name__ == "__main__":
    main()
