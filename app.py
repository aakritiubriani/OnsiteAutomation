"""
app.py — Namshi Campaign Planner  (web interface for the Layer 1 Engine)

Run:   python app.py
Then open:  http://localhost:5000
"""

import calendar as cal_mod
import io
import json
import logging
import sys
import traceback
import urllib.parse
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

import time

import pandas as pd
import openpyxl
import yaml

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / "src"))

from flask import Flask, jsonify, render_template, request, send_file

from recurrence import build_kb
from signals import LAYER2_COLS, enrich_with_commercial_signals
import generate as gen_mod

# ── Flask setup ────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────
CFG_FILE    = BASE / "config" / "calendar_config.yaml"
EVENTS_FILE = BASE / "config" / "global_events.yaml"
CSV_FILE    = BASE / "data"   / "standardized_history.csv"
OUT_DIR     = BASE / "output"

# ── In-memory cache (invalidated on config save) ───────────────────────────────
_cfg = None
_df  = None
_kb  = None

# ── BQ cache: { "pulse": {"data": {...}, "ts": float} } ───────────────────────
_bq_cache: dict = {}


def _load_cfg():
    global _cfg
    if _cfg is None:
        with open(CFG_FILE, encoding="utf-8") as f:
            _cfg = yaml.safe_load(f)
    return _cfg


def _reload_cfg():
    global _cfg, _kb
    _cfg = _kb = None
    return _load_cfg()


def _load_df():
    global _df
    if _df is None and CSV_FILE.exists():
        _df = pd.read_csv(CSV_FILE, dtype=str, keep_default_na=False)
    return _df


def _load_kb():
    global _kb
    if _kb is None:
        df = _load_df()
        _kb = build_kb(df) if df is not None else {}
    return _kb


def _load_global_events():
    if EVENTS_FILE.exists():
        with open(EVENTS_FILE, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/generate", methods=["POST"])
def api_generate():
    try:
        body  = request.get_json(force=True)
        month = int(body.get("month", 7))
        year  = int(body.get("year",  2026))

        cfg = _load_cfg()
        kb  = _load_kb()

        # ── Pipeline rows ──────────────────────────────────────────────────────
        resolved = gen_mod.resolve_events(cfg, year, month)
        pipe_rows = []
        seen_ck   = set()

        for ev in resolved:
            ck = ev["canonical_key"]

            if ck == "bts":
                if "bts" not in seen_ck:
                    for r in gen_mod.build_bts_rows(ev, kb, year, month):
                        r.update({"id": f"pipe_{len(pipe_rows)}", "status": "pending",
                                  "history_count": kb.get("bts", {}).get("history_count", 0),
                                  "source_type": "pipeline"})
                        pipe_rows.append(r)
                    seen_ck.add("bts")
                continue

            dedup = f"{ck}__{ev['name']}"
            if dedup in seen_ck:
                continue
            seen_ck.add(dedup)

            r = gen_mod.build_row(ev, kb, year, month)
            r.update({"id": f"pipe_{len(pipe_rows)}", "status": "pending",
                      "history_count": kb.get(ck, {}).get("history_count", 0),
                      "source_type": "pipeline"})
            # Convert bool needs_review to bool (may be Python bool or string)
            r["needs_review"] = bool(r.get("needs_review", False))
            pipe_rows.append(r)

        # Trend edits
        for i, r in enumerate(gen_mod.build_trend_edit_rows(cfg, year, month, kb)):
            r.update({"id": f"trend_{i}", "status": "pending",
                      "history_count": 0, "source_type": "pipeline"})
            r["needs_review"] = True
            pipe_rows.append(r)

        # ── Global calendar events for this month ──────────────────────────────
        global_rows = []
        global_data = _load_global_events()

        # Check if canonical key already covered by pipeline
        pipe_cks = {r["canonical_key"] for r in pipe_rows}

        for ev in global_data.get("events", []):
            if ev.get("month") != month:
                continue
            ck = ev.get("canonical_key", ev["name"].lower().replace(" ", "_").replace("'", ""))
            if ck in pipe_cks:
                continue  # already suggested by pipeline
            day = ev.get("day")
            start_iso = f"{year}-{month:02d}-{day:02d}" if day else "TBD"
            global_rows.append({
                "id":                  f"global_{len(global_rows)}",
                "campaign_name":       ev["name"],
                "canonical_key":       ck,
                "tier":                f"Tier {ev.get('tier', 2)}",
                "geography":           ev.get("geo", "KSA + UAE"),
                "start_date":          start_iso,
                "end_date":            start_iso,
                "duration_days":       1,
                "promos_coupons":      "NA",
                "category_focus":      ev.get("category_focus", ""),
                "onsite_deliverables": ev.get("suggested_deliverable", "Feed Module"),
                "wireframes":          "TBD",
                "event_type":          ev.get("event_type", "cultural"),
                "source":              "global_calendar",
                "needs_review":        True,
                "raw_notes":           ev.get("campaign_angle", ev.get("notes", "")),
                "status":              "pending",
                "history_count":       0,
                "source_type":         "global_calendar",
            })

        return jsonify({
            "success":      True,
            "month":        month,
            "year":         year,
            "month_name":   cal_mod.month_name[month],
            "campaigns":    pipe_rows,
            "global_events": global_rows,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/history/<canonical_key>")
def api_history(canonical_key):
    df = _load_df()
    if df is None:
        return jsonify({"canonical_key": canonical_key, "history": []})

    sub = df[df["canonical_key"] == canonical_key].copy()
    if sub.empty:
        return jsonify({"canonical_key": canonical_key, "history": []})

    cols = ["sheet_name", "campaign_name", "start_date", "end_date",
            "tier", "geography", "category_focus", "onsite_deliverables",
            "promos_coupons", "raw_notes"]
    cols = [c for c in cols if c in sub.columns]
    records = sub[cols].head(6).to_dict("records")
    return jsonify({"canonical_key": canonical_key, "history": records})


@app.route("/api/export", methods=["POST"])
def api_export():
    try:
        body  = request.get_json(force=True)
        rows  = body.get("rows", [])
        month = int(body.get("month", 7))
        year  = int(body.get("year",  2026))

        if not rows:
            return jsonify({"error": "No rows supplied"}), 400

        df = pd.DataFrame(rows)

        # Ensure all schema cols exist
        for col in gen_mod.SCHEMA_COLS:
            if col not in df.columns:
                df[col] = ""

        df = df[gen_mod.SCHEMA_COLS]

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUT_DIR / f"draft_calendar_{month}_{year}.xlsx"
        gen_mod.write_xlsx(df, out_path, month, year)

        return send_file(
            str(out_path),
            as_attachment=True,
            download_name=f"draft_calendar_{month}_{year}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/wireframe-tiles")
def api_wireframe_tiles():
    """Return the tile catalog (config/wireframe_tiles.yaml) for the planner's tile picker."""
    try:
        from wireframe import load_tile_catalog
        return jsonify({"tiles": load_tile_catalog()})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/export-wireframe", methods=["POST"])
def api_export_wireframe():
    """Export the reviewed campaigns' wireframe tile layout to an xlsx, one row-block per campaign."""
    try:
        from wireframe import write_wireframe_xlsx
        body  = request.get_json(force=True)
        rows  = body.get("rows", [])
        month = int(body.get("month", 7))
        year  = int(body.get("year", 2026))

        if not rows:
            return jsonify({"error": "No rows supplied"}), 400

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUT_DIR / f"wireframe_{month}_{year}.xlsx"
        write_wireframe_xlsx(rows, out_path, month, year)

        return send_file(
            str(out_path),
            as_attachment=True,
            download_name=f"wireframe_{month}_{year}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/search")
def api_search():
    month    = int(request.args.get("month", 7))
    year     = int(request.args.get("year",  2026))
    month_nm = cal_mod.month_name[month]
    results  = []

    try:
        import requests as req_lib
        queries = [
            f"fashion events {month_nm} {year} UAE Dubai MENA",
            f"fashion awareness days {month_nm} {year}",
        ]
        seen_titles = set()
        for query in queries:
            enc = urllib.parse.quote(query)
            url = f"https://news.google.com/rss/search?q={enc}&hl=en&gl=AE&ceid=AE:en"
            resp = req_lib.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            root = ET.fromstring(resp.content)
            for item in root.findall(".//item")[:5]:
                t = item.find("title")
                lnk = item.find("link")
                pub = item.find("pubDate")
                if t is not None and t.text and t.text not in seen_titles:
                    seen_titles.add(t.text)
                    results.append({
                        "title": t.text,
                        "link":  lnk.text if lnk is not None else "",
                        "date":  pub.text if pub is not None else "",
                    })
        results = results[:10]
    except Exception as e:
        log.warning(f"Web search error: {e}")

    return jsonify({"results": results, "month": month, "year": year})


@app.route("/api/config/dates", methods=["GET"])
def api_get_config():
    cfg = _load_cfg()
    out = {}
    for section in ("lunar_events", "sports_events"):
        for ev in cfg.get(section, []):
            ck = ev["canonical_key"]
            out[ck] = {
                "name":  ev["name"],
                "dates": {str(k): v for k, v in (ev.get("dates") or {}).items()},
                "needs_date_confirmation": ev.get("needs_date_confirmation", True),
            }
    return jsonify(out)


@app.route("/api/config/dates", methods=["POST"])
def api_save_config():
    try:
        incoming = request.get_json(force=True)
        with open(CFG_FILE, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        for section in ("lunar_events", "sports_events"):
            for ev in cfg.get(section, []):
                ck = ev["canonical_key"]
                if ck not in incoming:
                    continue
                if "dates" not in ev or ev["dates"] is None:
                    ev["dates"] = {}
                for yr_str, yr_dates in incoming[ck].items():
                    ev["dates"][int(yr_str)] = yr_dates

        with open(CFG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        _reload_cfg()
        return jsonify({"success": True})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/bq/category-pulse")
def api_category_pulse():
    """
    Return 3-week category/subcategory pulse from BigQuery core_metrics.
    Results are cached for 30 minutes to avoid repeated BQ charges.
    """
    try:
        from bq_connector import get_category_pulse
        bust   = request.args.get("bust")  # cache-bust from UI refresh button
        cached = _bq_cache.get("pulse")
        if cached and not bust and (time.time() - cached["ts"] < 1800):
            log.info("BQ pulse: serving from cache")
            return jsonify(cached["data"])
        log.info("BQ pulse: fetching from BigQuery…")
        data = get_category_pulse()
        _bq_cache["pulse"] = {"data": data, "ts": time.time()}
        return jsonify(data)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/bq/new-activations")
def api_new_activations():
    """
    Return monthly new-SKU activation activity from new_activations_shine
    (brand x category x gender x country), with new-on-Namshi brand detection.
    Results are cached for 30 minutes to avoid repeated BQ charges.
    """
    try:
        from bq_connector import get_new_activations
        bust   = request.args.get("bust")
        cached = _bq_cache.get("activations")
        if cached and not bust and (time.time() - cached["ts"] < 1800):
            log.info("BQ activations: serving from cache")
            return jsonify(cached["data"])
        log.info("BQ activations: fetching from BigQuery…")
        data = get_new_activations()
        _bq_cache["activations"] = {"data": data, "ts": time.time()}
        return jsonify(data)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/refresh-data", methods=["POST"])
def api_refresh_data():
    """Re-run standardize.py to pick up xlsx changes, then rebuild KB."""
    global _df, _kb
    try:
        import standardize
        import importlib
        importlib.reload(standardize)
        standardize.main()
        _df = _kb = None   # bust cache so next generate re-reads the CSV
        return jsonify({"success": True, "message": "History re-standardized."})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print()
    print("=" * 55)
    print("  Namshi Campaign Planner — Layer 1 Engine")
    print("  Open http://localhost:5000 in your browser")
    print("=" * 55)
    print()
    app.run(debug=False, port=5000)
