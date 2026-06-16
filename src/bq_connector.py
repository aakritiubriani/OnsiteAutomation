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


# ── New Activations (new_activations_shine) ─────────────────────────────────────

ACT_TBL          = "`noonbinmlook.looker.new_activations_shine`"
NEW_BRAND_GAP_DAYS = 180   # a brand counts as "new on Namshi" if it had 0 SKUs
                           # go live in the NEW_BRAND_GAP_DAYS before its first
                           # activation in a given month (or this is its very
                           # first activation in the whole dataset).


def _fmt_month_label(month_start_str: str) -> str:
    """'2026-05-01' → 'May 2026'"""
    try:
        d = date.fromisoformat(month_start_str)
        months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        return f"{months[d.month]} {d.year}"
    except Exception:
        return month_start_str


def get_new_activations(num_months: int = 6) -> dict:
    """
    Return monthly new-SKU-activation activity from `new_activations_shine`:
    which brands went live with new SKUs, in which category / gender / country,
    and which of those brands are "new on Namshi" (had zero SKUs go live in the
    NEW_BRAND_GAP_DAYS / 180 days before this activation, or this is their very
    first activation ever observed in the table).

    Returns
    -------
    {
      "success":     True,
      "data_as_of":  "YYYY-MM-DD",
      "months":       ["YYYY-MM-01", ...]   (oldest → newest, up to num_months),
      "month_labels": ["Jan 2026", ...],
      "monthly_summary": [
          { "month": "YYYY-MM-01", "new_skus": int, "active_brands": int,
            "new_brand_count": int, "skus_mom": float|None }, ...
      ],
      "rows": [
          { "month": "YYYY-MM-01", "brand": str, "country": str,
            "new_skus": int (sum across all categories/genders),
            "is_new_brand": bool, "is_top_brand": bool,
            "categories": [ { "category": str, "gender": str, "new_skus": int }, ... ]
              (sorted by new_skus desc — one brand x country x month row,
               with the category/gender split rolled up instead of being
               its own row) }, ...
      ]
    }
    """
    if not _BQ_AVAILABLE:
        return {"error": "google-cloud-bigquery not installed"}

    try:
        client = _client()

        # ── Step 1: latest "live" activation date (exclude future-dated/planned) ──
        max_rows = _run(client, f"""
            SELECT MAX(activated_at) AS max_date
            FROM {ACT_TBL}
            WHERE activated_at <= CURRENT_DATE()
        """)
        max_date = max_rows[0]["max_date"] if max_rows else None
        if not max_date:
            return {"error": "No activation data found (activated_at <= today)."}

        # ── Step 2: trailing N-month window (current partial month included) ──
        month_end_start = date(max_date.year, max_date.month, 1)
        # step back (num_months - 1) months to get the window start
        y, m = month_end_start.year, month_end_start.month
        m -= (num_months - 1)
        while m <= 0:
            m += 12
            y -= 1
        window_start = date(y, m, 1)

        ny, nm = month_end_start.year, month_end_start.month + 1
        if nm > 12:
            nm -= 12
            ny += 1
        window_end_excl = date(ny, nm, 1)  # exclusive upper bound

        months = []
        cy, cm = window_start.year, window_start.month
        while date(cy, cm, 1) < window_end_excl:
            months.append(f"{cy:04d}-{cm:02d}-01")
            cm += 1
            if cm > 12:
                cm = 1
                cy += 1

        # ── Step 3: monthly platform totals ──────────────────────────────
        sql_monthly = f"""
        SELECT
          FORMAT_DATE('%Y-%m-01', DATE_TRUNC(activated_at, MONTH)) AS month,
          COUNT(DISTINCT sku_config) AS new_skus,
          COUNT(DISTINCT brand)      AS active_brands
        FROM {ACT_TBL}
        WHERE activated_at >= '{window_start}'
          AND activated_at <  '{window_end_excl}'
          AND activated_at <= CURRENT_DATE()
        GROUP BY 1
        """
        raw_monthly = _run(client, sql_monthly)
        monthly_map = {r["month"]: r for r in raw_monthly}

        # ── Step 4: detail — brand x category x gender x country x month ──
        sql_detail = f"""
        SELECT
          FORMAT_DATE('%Y-%m-01', DATE_TRUNC(activated_at, MONTH)) AS month,
          brand,
          IFNULL(category, '(unclassified)')      AS category,
          IFNULL(gender,   '(unclassified)')       AS gender,
          UPPER(IFNULL(country, '(unclassified)')) AS country,
          COUNT(DISTINCT sku_config) AS new_skus
        FROM {ACT_TBL}
        WHERE activated_at >= '{window_start}'
          AND activated_at <  '{window_end_excl}'
          AND activated_at <= CURRENT_DATE()
          AND brand IS NOT NULL
        GROUP BY 1, 2, 3, 4, 5
        ORDER BY new_skus DESC
        LIMIT 50000
        """
        raw_detail = _run(client, sql_detail)

        # ── Step 5: brand-level reactivation detection (full history, not just
        #            the display window) — flags (brand, month) where the brand
        #            had a gap of >= NEW_BRAND_GAP_DAYS since its previous
        #            activation, or this is its first-ever activation on record.
        sql_reactivation = f"""
        WITH brand_dates AS (
          SELECT DISTINCT brand, activated_at
          FROM {ACT_TBL}
          WHERE brand IS NOT NULL AND activated_at <= CURRENT_DATE()
        ),
        gapped AS (
          SELECT
            brand, activated_at,
            DATE_DIFF(
              activated_at,
              LAG(activated_at) OVER (PARTITION BY brand ORDER BY activated_at),
              DAY
            ) AS gap_days
          FROM brand_dates
        )
        SELECT DISTINCT
          brand,
          FORMAT_DATE('%Y-%m-01', DATE_TRUNC(activated_at, MONTH)) AS month
        FROM gapped
        WHERE (gap_days IS NULL OR gap_days >= {NEW_BRAND_GAP_DAYS})
          AND activated_at >= '{window_start}'
          AND activated_at <  '{window_end_excl}'
        """
        raw_reactivation = _run(client, sql_reactivation)
        new_brand_months = {(r["brand"], r["month"]) for r in raw_reactivation}

        # ── Step 5b: brand "platform size" ranking per country ──────────────
        # Top-tier brand = total lifetime GMV (across ALL its SKUs, not just
        # this window's new ones) is at/above the 80th percentile (top 20%)
        # of all brands in that country. Nulls in gmv_inc_vat are treated as
        # 0 (no recorded sales) rather than excluded.
        sql_brand_rank = f"""
        WITH brand_totals AS (
          SELECT
            brand,
            UPPER(IFNULL(country, '(unclassified)')) AS country,
            SUM(IFNULL(gmv_inc_vat, 0)) AS total_gmv
          FROM {ACT_TBL}
          WHERE brand IS NOT NULL
          GROUP BY 1, 2
        ),
        thresholds AS (
          SELECT country, APPROX_QUANTILES(total_gmv, 100)[OFFSET(80)] AS p80_gmv
          FROM brand_totals
          GROUP BY country
        )
        SELECT
          bt.brand, bt.country, bt.total_gmv, th.p80_gmv,
          (bt.total_gmv >= th.p80_gmv) AS is_top_brand
        FROM brand_totals bt
        JOIN thresholds th USING (country)
        """
        raw_brand_rank = _run(client, sql_brand_rank)
        top_brand_map = {(r["brand"], r["country"]): bool(r["is_top_brand"]) for r in raw_brand_rank}
        country_thresholds = {r["country"]: float(r["p80_gmv"] or 0) for r in raw_brand_rank}

        # ── Step 6: collapse to one row per brand x country x month, with the
        #            category/gender breakdown rolled up into a single
        #            "assortment" list on that row (e.g. "Apparel - Women (45)")
        #            instead of a separate row per category/gender combo.
        grouped: dict = {}
        for r in raw_detail:
            key = (r["month"], r["brand"], r["country"])
            grp = grouped.setdefault(key, {
                "month":        r["month"],
                "brand":        r["brand"],
                "country":      r["country"],
                "new_skus":     0,
                "is_new_brand": (r["brand"], r["month"]) in new_brand_months,
                "is_top_brand": top_brand_map.get((r["brand"], r["country"]), False),
                "categories":   [],
            })
            n = int(r["new_skus"] or 0)
            grp["new_skus"] += n
            grp["categories"].append({
                "category": r["category"],
                "gender":   r["gender"],
                "new_skus": n,
            })

        result_rows = list(grouped.values())
        for grp in result_rows:
            grp["categories"].sort(key=lambda c: -c["new_skus"])

        # within month, surface top-tier brands first, then new-brand rows,
        # then by sku volume desc; months themselves newest-first (stable
        # multi-pass sort)
        result_rows.sort(key=lambda x: (
            0 if x["is_top_brand"] else 1,
            0 if x["is_new_brand"] else 1,
            -x["new_skus"],
        ))
        result_rows.sort(key=lambda x: x["month"], reverse=True)

        # ── Step 7: monthly summary with new-brand counts + MoM% ───────────
        new_brand_counts_by_month: dict = {}
        for brand, month in new_brand_months:
            new_brand_counts_by_month[month] = new_brand_counts_by_month.get(month, 0) + 1

        monthly_summary = []
        prev_skus = None
        for month in months:
            row = monthly_map.get(month, {})
            new_skus = int(row.get("new_skus") or 0)
            active_brands = int(row.get("active_brands") or 0)
            mom = _wow(new_skus, prev_skus) if prev_skus is not None else None
            monthly_summary.append({
                "month":           month,
                "new_skus":        new_skus,
                "active_brands":   active_brands,
                "new_brand_count": new_brand_counts_by_month.get(month, 0),
                "skus_mom":        mom,
            })
            prev_skus = new_skus

        return {
            "success":               True,
            "data_as_of":            str(max_date),
            "months":                months,
            "month_labels":          [_fmt_month_label(m) for m in months],
            "monthly_summary":       monthly_summary,
            "rows":                  result_rows,
            "top_brand_thresholds":  country_thresholds,  # {"AE": 22600.96, "SA": 22352.59, ...}
        }

    except Exception as e:
        log.error("BQ new activations failed: %s", e)
        return {"error": str(e)}
