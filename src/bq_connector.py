"""
bq_connector.py — BigQuery data layer for Namshi Campaign Planner

Fetches category/subcategory/gender/country 3-week performance pulse from:
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

METRIC_SELECT = """
  CAST(SUM(IFNULL(total_impressions,      0)) AS INT64) AS impressions,
  CAST(SUM(IFNULL(non_search_impressions, 0)) AS INT64) AS merch_impressions,
  CAST(SUM(IFNULL(namshi_units,           0)) AS INT64) AS units
"""


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


def _flag_for(imp_wow, units_wow):
    """SPIKE / DIP classification — impressions are the primary signal."""
    if imp_wow is not None:
        if imp_wow > 30:
            return "SPIKE"
        if imp_wow < -20:
            return "DIP"
    elif units_wow is not None:
        if units_wow > 30:
            return "SPIKE"
        if units_wow < -20:
            return "DIP"
    return ""


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


def _pivot_weekly(raw: list[dict], key_fields: list[str], weeks: list[str]) -> list[dict]:
    """
    Pivot a list of {week_start, <key_fields...>, impressions, merch_impressions, units}
    rows into one entry per unique key, with 3-week series + WoW + flag.

    key_fields may be an empty list, in which case a single overall summary
    entry is produced (used for platform-level totals).
    """
    pivot: dict = {}
    for r in raw:
        key = tuple(r[f] for f in key_fields)
        pivot.setdefault(key, {})[r["week_start"]] = {
            "impressions":       int(r["impressions"]       or 0),
            "merch_impressions": int(r["merch_impressions"] or 0),
            "units":             int(r["units"]             or 0),
        }

    out = []
    for key, week_data in pivot.items():
        imp_s   = [week_data.get(w, {}).get("impressions",       0) for w in weeks]
        merch_s = [week_data.get(w, {}).get("merch_impressions", 0) for w in weeks]
        units_s = [week_data.get(w, {}).get("units",             0) for w in weeks]

        imp_wow   = _wow(imp_s[2],   imp_s[1])
        merch_wow = _wow(merch_s[2], merch_s[1])
        units_wow = _wow(units_s[2], units_s[1])

        entry = dict(zip(key_fields, key))
        entry.update({
            "impressions":       imp_s,
            "merch_impressions": merch_s,
            "units":             units_s,
            "imp_wow":           imp_wow,
            "merch_wow":         merch_wow,
            "units_wow":         units_wow,
            "flag":              _flag_for(imp_wow, units_wow),
        })
        out.append(entry)
    return out


# ── public API ─────────────────────────────────────────────────────────────────

def get_category_pulse() -> dict:
    """
    Return platform / merch-team / category-level 3-week performance trend.

    Strategy:
      1. Find the latest DATE available in core_metrics (within last 60 days).
      2. Compute the 3 most-recent complete ISO weeks ending at that date.
      3. Run 3 aggregation queries against the same DATE window:
           a) platform totals (no grouping)
           b) merch_team totals
           c) full detail: category + sub_category + merch_team + gender + country
      4. Pivot each into 3-week series + WoW % + SPIKE/DIP flags.

    Returns
    -------
    {
      "success":     True,
      "data_as_of":  "YYYY-MM-DD",
      "weeks":       ["YYYY-MM-DD", "YYYY-MM-DD", "YYYY-MM-DD"],
      "week_labels": ["Oct 6–12", "Oct 13–19", "Oct 20–26"],
      "platform_summary": {
          "impressions": [w1,w2,w3], "merch_impressions": [...], "units": [...],
          "imp_wow": float|None, "merch_wow": float|None, "units_wow": float|None,
          "flag": "SPIKE"|"DIP"|""
      },
      "merch_team_summary": [
          { "merch_team": str, "impressions":[...], "merch_impressions":[...],
            "units":[...], "imp_wow":..., "merch_wow":..., "units_wow":..., "flag":... }, ...
      ],
      "rows": [
          { "category":str, "sub_category":str, "merch_team":str, "gender":str, "country":str,
            "impressions":[...], "merch_impressions":[...], "units":[...],
            "imp_wow":..., "merch_wow":..., "units_wow":..., "flag":... }, ...
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
        days_since_monday = max_date.weekday()   # 0 = Monday, 6 = Sunday
        if days_since_monday == 6:
            latest_monday = max_date - timedelta(days=6)
        else:
            latest_monday = max_date - timedelta(days=days_since_monday) - timedelta(weeks=1)

        week3_start = latest_monday - timedelta(weeks=2)   # oldest week
        window_end  = latest_monday + timedelta(weeks=1)   # exclusive upper bound

        weeks = [
            str(week3_start),
            str(week3_start + timedelta(weeks=1)),
            str(week3_start + timedelta(weeks=2)),
        ]

        date_filter = f"""
          WHERE DATE >= '{week3_start}'
            AND DATE <  '{window_end}'
            AND country IN ('AE','SA','KW')
        """

        # ── Step 3a: platform totals (no grouping) ──────────────────────────
        sql_platform = f"""
        SELECT
          FORMAT_DATE('%Y-%m-%d', DATE_TRUNC(DATE, WEEK(MONDAY))) AS week_start,
          {METRIC_SELECT}
        FROM {FULL_TBL}
        {date_filter}
        GROUP BY 1
        """
        raw_platform = _run(client, sql_platform)

        # ── Step 3b: merch team totals ───────────────────────────────────
        sql_merch = f"""
        SELECT
          FORMAT_DATE('%Y-%m-%d', DATE_TRUNC(DATE, WEEK(MONDAY))) AS week_start,
          IFNULL(merch_team, '(unclassified)') AS merch_team,
          {METRIC_SELECT}
        FROM {FULL_TBL}
        {date_filter}
        GROUP BY 1, 2
        """
        raw_merch = _run(client, sql_merch)

        # ── Step 3c: full detail — category/sub/merch/gender/country ───────
        sql_detail = f"""
        SELECT
          FORMAT_DATE('%Y-%m-%d', DATE_TRUNC(DATE, WEEK(MONDAY))) AS week_start,
          IFNULL(category,     '(unclassified)') AS category,
          IFNULL(sub_category, '(unclassified)') AS sub_category,
          IFNULL(merch_team,   '(unclassified)') AS merch_team,
          IFNULL(gender,       '(unclassified)') AS gender,
          UPPER(IFNULL(country,'(unclassified)')) AS country,
          {METRIC_SELECT}
        FROM {FULL_TBL}
        {date_filter}
        GROUP BY 1, 2, 3, 4, 5, 6
        ORDER BY impressions DESC
        LIMIT 20000
        """
        raw_detail = _run(client, sql_detail)

        if not raw_detail:
            return {"error": f"No data between {week3_start} and {window_end}."}

        # ── Step 4: pivot each into 3-week series + WoW + flags ────────────
        platform_list = _pivot_weekly(raw_platform, [], weeks)
        platform_summary = platform_list[0] if platform_list else {
            "impressions": [0,0,0], "merch_impressions": [0,0,0], "units": [0,0,0],
            "imp_wow": None, "merch_wow": None, "units_wow": None, "flag": "",
        }

        merch_team_summary = _pivot_weekly(raw_merch, ["merch_team"], weeks)
        merch_team_summary.sort(key=lambda x: -sum(x["impressions"]))

        result_rows = _pivot_weekly(
            raw_detail, ["category", "sub_category", "merch_team", "gender", "country"], weeks
        )
        flag_order = {"SPIKE": 0, "DIP": 1, "": 2}
        result_rows.sort(key=lambda x: (flag_order[x["flag"]], -sum(x["impressions"])))

        return {
            "success":            True,
            "data_as_of":         str(max_date),
            "weeks":              weeks,
            "week_labels":        [_fmt_week_label(w) for w in weeks],
            "platform_summary":   platform_summary,
            "merch_team_summary": merch_team_summary,
            "rows":               result_rows,
        }

    except Exception as e:
        log.error("BQ category pulse failed: %s", e)
        return {"error": str(e)}
