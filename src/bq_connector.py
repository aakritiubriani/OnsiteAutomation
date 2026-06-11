"""
bq_connector.py — BigQuery data layer for Namshi Campaign Planner

Fetches category/subcategory 3-week performance pulse from:
  noonbinmlook.namshi_analytics_custom.core_metrics
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

log = logging.getLogger(__name__)

try:
    from google.cloud import bigquery
    _BQ_AVAILABLE = True
except ImportError:
    _BQ_AVAILABLE = False

PROJECT  = "noonbinmlook"
FULL_TBL = "`noonbinmlook.namshi_analytics_custom.core_metrics`"


# ── internal helpers ───────────────────────────────────────────────────────────

def _client():
    if not _BQ_AVAILABLE:
        raise RuntimeError("google-cloud-bigquery not installed.")
    return bigquery.Client(project=PROJECT)


def _run(client, sql: str) -> list[dict]:
    rows = list(client.query(sql).result())
    return [dict(r) for r in rows]


def _wow(cur, prev):
    """Week-over-week % change, or None if no baseline."""
    try:
        if prev and prev > 0:
            return round((cur - prev) / prev * 100, 1)
    except Exception:
        pass
    return None


def _fmt_week_label(monday_str: str) -> str:
    """'2025-10-20' → 'Oct 20–26'"""
    try:
        d = date.fromisoformat(monday_str)
        end = d + timedelta(days=6)
        months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        if d.month == end.month:
            return f"{months[d.month]} {d.day}–{end.day}"
        return f"{months[d.month]} {d.day} – {months[end.month]} {end.day}"
    except Exception:
        return monday_str


# ── public API ─────────────────────────────────────────────────────────────────

def get_category_pulse() -> dict:
    """
    Return category / subcategory 3-week performance trend.

    Strategy:
      1. Find the latest DATE available in core_metrics (within last 60 days).
      2. Compute the 3 most-recent complete ISO weeks ending at that date.
      3. Aggregate: total_impressions, non_search_impressions (merch),
         namshi_units — grouped by category + sub_category + merch_team.
      4. Calculate WoW % change and flag SPIKE / DIP rows.

    Returns
    -------
    {
      "success":    True,
      "data_as_of": "YYYY-MM-DD",
      "weeks":      ["YYYY-MM-DD", "YYYY-MM-DD", "YYYY-MM-DD"],   # oldest → newest
      "week_labels":["Oct 6–12", "Oct 13–19", "Oct 20–26"],
      "rows": [
        {
          "category":         str,
          "sub_category":     str,
          "merch_team":       str,
          "impressions":      [w1, w2, w3],       # int, oldest → newest
          "merch_impressions":[w1, w2, w3],
          "units":            [w1, w2, w3],
          "imp_wow":          float | None,        # WoW % latest vs prev
          "units_wow":        float | None,
          "merch_wow":        float | None,
          "flag":             "SPIKE" | "DIP" | ""
        }, ...
      ]
    }
    """
    if not _BQ_AVAILABLE:
        return {"error": "google-cloud-bigquery not installed"}

    try:
        client = _client()

        # ── Step 1: latest available date ──────────────────────────────────
        max_rows = _run(client, f"""
            SELECT MAX(DATE) AS max_date
            FROM {FULL_TBL}
            WHERE DATE >= DATE_SUB(CURRENT_DATE(), INTERVAL 60 DAY)
              AND country = 'AE'
        """)
        max_date = max_rows[0]["max_date"] if max_rows else None
        if not max_date:
            return {"error": "No recent data found in core_metrics (last 60 days)."}

        # ── Step 2: compute 3-week window (complete weeks only) ────────────
        # If max_date falls mid-week, drop the partial current week and use
        # the most-recent fully completed week as the anchor.
        days_since_monday = max_date.weekday()   # 0 = Monday, 6 = Sunday
        if days_since_monday == 6:
            # max_date is a Sunday → that week is complete
            latest_monday = max_date - timedelta(days=6)
        else:
            # Partial week in progress → step back to last full week's Monday
            latest_monday = max_date - timedelta(days=days_since_monday) - timedelta(weeks=1)

        week3_start = latest_monday - timedelta(weeks=2)   # oldest week
        window_end  = latest_monday + timedelta(weeks=1)   # exclusive upper bound

        weeks = [
            str(week3_start),
            str(week3_start + timedelta(weeks=1)),
            str(week3_start + timedelta(weeks=2)),
        ]

        # ── Step 3: pull weekly aggregates ─────────────────────────────────
        sql = f"""
        SELECT
          FORMAT_DATE('%Y-%m-%d', DATE_TRUNC(DATE, WEEK(MONDAY))) AS week_start,
          IFNULL(category,     '(unclassified)') AS category,
          IFNULL(sub_category, '(unclassified)') AS sub_category,
          IFNULL(merch_team,   '(unclassified)') AS merch_team,
          CAST(SUM(IFNULL(total_impressions,      0)) AS INT64) AS impressions,
          CAST(SUM(IFNULL(non_search_impressions, 0)) AS INT64) AS merch_impressions,
          CAST(SUM(IFNULL(namshi_units,           0)) AS INT64) AS units
        FROM {FULL_TBL}
        WHERE DATE >= '{week3_start}'
          AND DATE <  '{window_end}'
          AND country IN ('AE','SA','KW')
        GROUP BY 1, 2, 3, 4
        LIMIT 5000
        """
        raw = _run(client, sql)

        if not raw:
            return {"error": f"No data between {week3_start} and {window_end}."}

        # ── Step 4: pivot by category + sub_category + merch_team ──────────
        pivot: dict = {}
        for r in raw:
            key = (r["category"], r["sub_category"], r["merch_team"])
            pivot.setdefault(key, {})[r["week_start"]] = {
                "impressions":       int(r["impressions"]       or 0),
                "merch_impressions": int(r["merch_impressions"] or 0),
                "units":             int(r["units"]             or 0),
            }

        # ── Step 5: build result rows with WoW + flags ─────────────────────
        result_rows = []
        for (cat, sub, merch), week_data in pivot.items():
            imp_s   = [week_data.get(w, {}).get("impressions",       0) for w in weeks]
            merch_s = [week_data.get(w, {}).get("merch_impressions", 0) for w in weeks]
            units_s = [week_data.get(w, {}).get("units",             0) for w in weeks]

            imp_wow   = _wow(imp_s[2],   imp_s[1])
            merch_wow = _wow(merch_s[2], merch_s[1])
            units_wow = _wow(units_s[2], units_s[1])

            # Flag: impressions are the primary signal (traffic proxy)
            #       units are secondary (only used when imp data is absent)
            flag = ""
            if imp_wow is not None:
                if imp_wow > 30:
                    flag = "SPIKE"
                elif imp_wow < -20:
                    flag = "DIP"
            elif units_wow is not None:
                if units_wow > 30:
                    flag = "SPIKE"
                elif units_wow < -20:
                    flag = "DIP"

            result_rows.append({
                "category":          cat,
                "sub_category":      sub,
                "merch_team":        merch,
                "impressions":       imp_s,
                "merch_impressions": merch_s,
                "units":             units_s,
                "imp_wow":           imp_wow,
                "merch_wow":         merch_wow,
                "units_wow":         units_wow,
                "flag":              flag,
            })

        # Sort: SPIKE first → DIP → rest, then by total impressions desc
        flag_order = {"SPIKE": 0, "DIP": 1, "": 2}
        result_rows.sort(
            key=lambda x: (flag_order[x["flag"]], -sum(x["impressions"]))
        )

        return {
            "success":     True,
            "data_as_of":  str(max_date),
            "weeks":       weeks,
            "week_labels": [_fmt_week_label(w) for w in weeks],
            "rows":        result_rows,
        }

    except Exception as e:
        log.error("BQ category pulse failed: %s", e)
        return {"error": str(e)}
