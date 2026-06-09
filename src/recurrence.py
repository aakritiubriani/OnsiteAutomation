"""
recurrence.py — Step 2: Build a recurrence knowledge base from standardized history.

Can be imported by generate.py or run standalone to inspect the KB.

Usage:
    python src/recurrence.py
"""

from datetime import date
from pathlib import Path
from statistics import median

import pandas as pd

BASE     = Path(__file__).resolve().parent.parent
CSV_FILE = BASE / "data" / "standardized_history.csv"


def _sheet_sort_key(sheet_name: str) -> int:
    """Convert 'june2026' / 'may 2025' → yyyymm integer for chronological sorting."""
    import re
    MONTHS = {
        "jan": 1, "january": 1, "feb": 2, "february": 2,
        "mar": 3, "march": 3,  "apr": 4, "april": 4,
        "may": 5, "jun": 6, "june": 6,  "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "september": 9,
        "oct": 10, "october": 10, "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }
    name = str(sheet_name).lower().strip()
    yr_m = re.search(r"(20\d{2})", name)
    if not yr_m:
        return 0
    yr = int(yr_m.group(1))
    nm = name.replace(yr_m.group(1), "").strip()
    mo = next((v for k, v in MONTHS.items() if k in nm), 0)
    return yr * 100 + mo


def build_kb(df: pd.DataFrame | None = None) -> dict:
    """
    Build the recurrence knowledge base from standardized_history.csv.

    Returns dict:
        canonical_key → {
            "most_recent_tier"               : str,
            "most_recent_geography"          : str,
            "most_recent_category_focus"     : str,
            "most_recent_onsite_deliverables": str,
            "most_recent_start"              : str | None,   # ISO date of most recent start
            "most_recent_end"                : str | None,   # ISO date of most recent end
            "typical_months"                 : list[int],
            "typical_start_day"              : int | None,
            "typical_duration_days"          : int | None,
            "history_count"                  : int,
            "last_seen_sheet"                : str,
        }
    """
    if df is None:
        df = pd.read_csv(CSV_FILE, dtype=str, keep_default_na=False)

    # Attach numeric sort key for "most recent" logic
    df = df.copy()
    df["_sort"] = df["sheet_name"].apply(_sheet_sort_key)

    # Only primary table rows for most attribute inference
    primary = df[df["table_type"] == "primary"].copy()

    kb = {}
    for ck, grp in primary.groupby("canonical_key"):
        if ck in ("", "unknown"):
            continue

        grp_sorted = grp.sort_values("_sort", ascending=False)  # most recent first

        # ── most-recent values ──
        most_recent_row = grp_sorted.iloc[0]

        def _mv(col):
            """Most-recent non-empty value for a column."""
            for _, row in grp_sorted.iterrows():
                v = row.get(col, "")
                if v and v not in ("nan", "None", "TBD", "-", ""):
                    return v
            return ""

        tier    = _mv("tier")
        geo     = _mv("geography")
        cat     = _mv("category_focus")
        deliv   = _mv("onsite_deliverables")

        # ── typical months ──
        months = []
        for sd in grp_sorted["start_date"]:
            if sd and sd not in ("TBD", "", "nan", "None"):
                try:
                    months.append(date.fromisoformat(sd).month)
                except Exception:
                    pass

        # ── typical start day ──
        start_days = []
        for sd in grp_sorted["start_date"]:
            if sd and sd not in ("TBD", "", "nan", "None"):
                try:
                    start_days.append(date.fromisoformat(sd).day)
                except Exception:
                    pass

        # ── typical duration ──
        durations = []
        for d in grp_sorted["duration_days"]:
            try:
                v = int(float(d))
                if 1 <= v <= 60:
                    durations.append(v)
            except Exception:
                pass

        # ── most recent concrete dates ──
        mr_start = _mv("start_date") or None
        mr_end   = _mv("end_date")   or None
        if mr_start in ("TBD", "nan", "None", ""):
            mr_start = None
        if mr_end   in ("TBD", "nan", "None", ""):
            mr_end = None

        kb[ck] = {
            "most_recent_tier":               tier,
            "most_recent_geography":          geo,
            "most_recent_category_focus":     cat,
            "most_recent_onsite_deliverables": deliv,
            "most_recent_start":              mr_start,
            "most_recent_end":                mr_end,
            "typical_months":                 sorted(set(months)),
            "typical_start_day":              round(median(start_days)) if start_days else None,
            "typical_duration_days":          round(median(durations)) if durations else None,
            "history_count":                  len(grp),
            "last_seen_sheet":                most_recent_row["sheet_name"],
        }

    return kb


def main():
    kb = build_kb()
    print(f"Recurrence KB — {len(kb)} canonical campaigns\n")
    for ck, info in sorted(kb.items()):
        print(f"  {ck:<25} count={info['history_count']:<3} "
              f"months={info['typical_months']} "
              f"tier={info['most_recent_tier']!r} "
              f"dur={info['typical_duration_days']}")


if __name__ == "__main__":
    main()
