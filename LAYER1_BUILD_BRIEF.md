# Build Brief — Stage 1 / Layer 1: Campaign Generation Engine

> **For:** Claude Code (or an engineer using it)
> **Owner:** Onsite Strategy Specialist, Namshi
> **Status:** Ready to build. No internal-DB dependency. No org approvals required.
> **This document is the source of truth.** If anything here is ambiguous, ask before assuming.

---

## 1. Context (read this first)

Namshi runs monthly onsite campaigns. ~15 days before a month starts, the onsite team plans that month's campaign slate. Planning today is manual, driven by a single Excel file of historical campaigns.

The full vision ("Stage 1") has **three layers**:
- **Layer 1 — Generation engine** (THIS BRIEF): from campaign history + a fixed regional calendar, draft next month's *recurring/predictable* slate.
- **Layer 2 — Live signal layer** (OUT OF SCOPE HERE): trending keywords, stock, brand performance, struggling categories, new activations, outliers. Needs internal DB access + approvals. Do **not** build this yet.
- **Layer 3 — Delivery** (OUT OF SCOPE HERE): scheduled email / dashboard.

Build **only Layer 1**. But design it so Layer 2 can plug in later (see §7).

**The decision always stays with a human.** This engine produces a *draft* the specialist edits. It does not auto-publish anything.

---

## 2. Objective

Given a **target month + year** (e.g. `July 2026`), output a **draft campaign calendar** in Namshi's standard schema, populated with the recurring, calendar-predictable campaigns for that month, using:

1. the historical campaign repository (what Namshi actually ran in past years), and
2. a regional/retail calendar of known events (fixed-date, lunar, seasonal, sports).

---

## 3. Inputs

### 3.1 Historical repository (provided)
- **File:** `Master_Campaign_Calendr.xlsx` (15 monthly sheets, ~Mar 2025 → Jun 2026).
- **KNOWN DATA-QUALITY ISSUES — your code must handle these:**
  - **Inconsistent schema across sheets.** Column count/order/headers differ by month (e.g. `april 2025` has 6 cols; `november 2025` has 13; the stable schema appears ~mid-2025). Do not assume a fixed header row.
  - **Dates stored as Excel serial numbers** (e.g. `46178.0` = a real date). Convert with the 1899-12-30 epoch. Some cells are free text (`"Jun 5 (TBC)"`, `"17th - 21st October"`) — parse what you can, flag the rest.
  - **Some sheets contain a second table lower down** (a "Trends" / style-edit table with a different header). Detect and capture both.
  - **Geography values vary:** `KSA + UAE`, `KSA`, `UAE`, `All`, `AE + GCC`. Normalize to a controlled vocabulary.
  - **Tier values vary:** `Tier 1` / `T1` / `Tier 1 on Men Tier 2 Women` etc. Normalize where unambiguous; preserve original in a raw field where not.

**First task: write a standardizer** that reads all sheets and emits one tidy table (the Standard Schema, §5). This is the foundation — everything else reads the standardized table, never the raw sheets.

### 3.2 Regional calendar (you build this as a config file)
A maintainable config (`calendar_config.yaml` or `.json`) the specialist owns. It holds event definitions the engine maps onto the target month. See §6 for the seed content — populate it from there. Lunar/variable dates are **config-driven, not computed** (see §6.1).

### 3.3 Runtime parameter
- `target_month`, `target_year` (e.g. `7`, `2026`).

---

## 4. Processing logic

```
STEP 1  Standardize history
        - Read every sheet of the xlsx.
        - For each, locate header row(s), map columns to Standard Schema, capture both primary + trend tables.
        - Convert serial dates -> ISO dates; keep unparseable dates as a raw string + flag.
        - Normalize Geography + Tier vocabularies.
        - Output: standardized_history.csv (one row per historical campaign).

STEP 2  Build recurrence knowledge base
        - Group standardized history by a normalized campaign key (e.g. "EOSS", "Payday",
          "Ramadan", "Back to School"). Use the §6 taxonomy to map name variants -> canonical key.
        - For each canonical campaign, derive typical attributes from history:
          typical month(s), typical tier, typical geography, typical category focus,
          typical onsite deliverables, typical duration (days).

STEP 3  Resolve the target month's events
        - From calendar_config, list every event whose date/window falls in target_month/year
          (fixed-date, lunar-from-config, seasonal-window, sports-from-config).
        - Add monthly-recurring anchors that always appear (Payday, Feed Monthly Refresh, and
          any EOSS/sale cycle active that month).

STEP 4  Generate draft rows
        - For each resolved event, create a draft campaign row in the Standard Schema, pre-filled
          from the recurrence knowledge base (Step 2) + calendar_config dates (Step 3).
        - Where history disagrees or is sparse, fill best-guess and set needs_review = TRUE.
        - Leave commercial-signal fields (see §7) blank with a clear placeholder.

STEP 5  Emit output
        - Write draft_calendar_<month>_<year>.xlsx in the Standard Schema, matching the
          existing file's column style so it's drop-in familiar.
        - Also emit a short draft_notes.md: assumptions made, rows flagged needs_review,
          events found in config but with no historical precedent, and history with no
          matching config event (possible gaps).
```

---

## 5. Standard Schema (the canonical output columns)

Use exactly these, in this order, for both `standardized_history.csv` and the generated calendar:

| Column | Type | Notes |
|---|---|---|
| `campaign_name` | string | As written |
| `canonical_key` | string | Normalized key for grouping (e.g. `eoss`, `payday`, `ramadan`) |
| `tier` | enum | `Tier 1` / `Tier 2` / `Tier 3` / `-` |
| `geography` | enum | `KSA + UAE` / `KSA` / `UAE` / `All` |
| `start_date` | ISO date or `TBD` | |
| `end_date` | ISO date or `TBD` | |
| `duration_days` | int or null | derived |
| `promos_coupons` | string | free text; `NA` allowed |
| `category_focus` | string | |
| `onsite_deliverables` | string | e.g. "Hero banner + feed module" |
| `wireframes` | string | reference / link / `TBD` |
| `event_type` | enum | `monthly_anchor` / `sale` / `seasonal` / `cultural` / `national` / `sports` / `beauty` / `trend_edit` |
| `source` | enum | `history` / `config` / `both` |
| `needs_review` | bool | TRUE when generated value is a best-guess |
| `raw_notes` | string | anything unparsed, preserved for the human |

---

## 6. Calendar config — seed content

Derived from the actual repository. Populate `calendar_config` with these. **Verify every date before a real run** — this is a seed, not gospel.

### 6.1 Lunar / variable (DATES ARE CONFIG-DRIVEN — DO NOT COMPUTE)
Islamic and Hindu calendar events shift yearly and depend on moon sighting. The specialist enters confirmed dates each cycle. Approximate windows for orientation only:
- **Ramadan** — ~Feb–Mar (2026 ≈ Feb 18–Mar 19; 2027 ≈ Feb 8–Mar 9). Drives: Get Ready for Ramadan, Ramadan takeover, Ramadan Sale. Tier 1. Arabian/modest wear, beauty, FAB, gifting.
- **Eid al-Fitr** — end of Ramadan (2026 ≈ Mar 20). Eid Sale, Tier 1, platform-wide.
- **Eid al-Adha** — ~2.5 months after Fitr (2026 ≈ May 27). Get Ready for Eid (Adha) + Eid Sale.
- **Diwali** — Oct/Nov, UAE, Indian-national targeted. Tier 1 (Indian nationals).
- **Holi** — Mar, UAE, Indian-national targeted. Tier 2.

### 6.2 Fixed-date events
| Event | Date | Geo | Tier | Category focus |
|---|---|---|---|---|
| Pantone Colour of the Year | early Jan | KSA + UAE | Tier 1 | platform-wide, themed shade |
| Dubai Shopping Festival | late Dec–Jan | UAE | Tier 2 | platform-wide |
| Valentine's / Love Edit | ~Feb 14 | UAE | Tier 2 | fashion, beauty, gifting |
| International Women's Day | Mar 8 | KSA + UAE | Tier 2 | women's fashion, beauty |
| Mother's Day (Middle East) | Mar 21 | KSA + UAE | Tier 2 | gifting |
| Father's Day | 3rd Sun June | KSA + UAE | Tier 2 | gifting (FAB, grooming) |
| Int'l Yoga Day / Wellness | Jun 21 | KSA + UAE | Tier 2 | athleisure, yoga |
| Int'l Coffee Day | Oct 1 | KSA + UAE | Tier 2 | shades-of-brown fashion/beauty |
| Halloween | Oct 31 | UAE | Tier 2 | beauty, kids |
| KSA National Day | Sep 23 | KSA | Tier 1/2 | arabian wear, local brands, beauty |
| UAE National Day | Dec 2 | UAE | Tier 1 | flag-colour fashion, modestwear |
| Saudi Vision 2030 anniversary | Apr (PIF-linked) | KSA | Tier 2 | local brands, arabian wear, streetwear |

### 6.3 Seasonal windows
| Event | Typical window | Notes |
|---|---|---|
| Spring/Summer trends | Apr–Jun | dresses, swimwear, sets, suncare |
| Summer Store / rerun | May–Jul | extension/refresh |
| EOSS (summer) | Jun–Jul | platform-wide sale |
| EOSS (winter) | Dec–Jan | platform-wide sale |
| Back to School (BTS) | Jul–Sep (phased: soft launch → takeover → last chance) | kidswear, bags, stationery |
| AW (Autumn/Winter) | Sep | fashion |
| Travel Edit | recurring (summer + winter variants) | luggage, comfort wear, beauty minis |
| Holiday / Gifting | Dec | FAB, beauty giftsets, kids, home |
| Party Edit | Dec | occasionwear, beauty |

### 6.4 Monthly anchors (appear (almost) every month)
| Event | Timing | Notes |
|---|---|---|
| Payday | ~25th → early next month | platform-wide, Tier 1, cashback coupon |
| Feed Monthly Refresh | once/month | M/W/K/B feed refresh |
| Beauty Week | recurs several times/yr | beauty feed + entry points |

### 6.5 Sports (EVENT-DRIVEN — CONFIG-DRIVEN DATES)
The specialist enters fixtures each cycle. Recurring ones seen in history:
- **F1** (Abu Dhabi GP ~Dec; other GPs) — sports + fashion (athleisure).
- **FIFA World Cup 2026** (Jun–Jul 2026 — *highly relevant near-term*) — jerseys, apparel, footwear; Tier 1 on sports feed.
- **Marathons** (Dubai ~Jan, Riyadh) — running apparel/shoes.
- **Dubai Fitness / Dubai Active** (Oct–Nov) — sports, athleisure.

### 6.6 Trend edits (the second-table style edits)
History shows gender-split style edits (e.g. "Soft Girl Summer (W)", "Coastal Core (M)", "90's Off Duty (W)", "Preppy (M)"), usually Hero Banner deliverables on a weekly rotation. Generate these as `event_type = trend_edit` with `needs_review = TRUE` — they are the most human-judgment-heavy and the specialist will likely rewrite them. Surface 3–5 historical examples for the target season as suggestions rather than firm picks.

---

## 7. Layer 2 hook (build the seam, not the feature)

Do **not** connect to any internal database. But leave a clean, documented interface so Layer 2 can populate these later without refactoring:

- Add (and leave blank) commercial fields the generator can later enrich: `trending_keywords`, `stock_flag`, `brand_performance_flag`, `struggling_category_flag`, `new_activation_flag`, `outlier_flag`.
- Define an ingestion function signature, e.g. `enrich_with_commercial_signals(draft_df, signals: dict) -> draft_df`, that currently no-ops. Document the expected `signals` shape (per-category / per-brand / per-keyword) as a TODO.
- The specialist will, for now, supply these manually via CSV; the function should accept that path too.

---

## 8. Tech notes

- **Language:** Python. **Libs:** `pandas`, `openpyxl` (read/write + match existing styling), `pyyaml` (config), `python-dateutil` (date parsing).
- **Excel serial dates:** epoch `1899-12-30`; `date = epoch + timedelta(days=serial)`.
- **Output styling:** match the existing file's look (Arial, the existing column widths/headers) so it feels native to the team.
- **Idempotent + re-runnable:** same inputs → same output. No hidden state.
- **Config over hardcoding:** all dates, tiers, geos live in `calendar_config`, never inline in code.
- **Repo layout (suggested):**
  ```
  /data/raw/Master_Campaign_Calendr.xlsx
  /data/standardized_history.csv        # generated
  /config/calendar_config.yaml
  /src/standardize.py                   # Step 1
  /src/recurrence.py                    # Step 2
  /src/generate.py                      # Steps 3–5
  /output/draft_calendar_<m>_<y>.xlsx
  /output/draft_notes.md
  README.md
  ```

---

## 9. Acceptance criteria

Layer 1 is done when:
1. `standardize.py` ingests all 15 sheets (including second/trend tables) into one clean `standardized_history.csv` with zero crashes and a logged list of any rows it couldn't fully parse.
2. All serial dates convert correctly (spot-check: serial `46178` → `2026-06-08`).
3. Running `generate.py --month 7 --year 2026` produces a `draft_calendar_7_2026.xlsx` that:
   - includes the July monthly anchors (Payday, Feed Refresh) and any active sale cycle,
   - includes EOSS and World Cup 2026 (config-driven) for that window,
   - matches the Standard Schema (§5) exactly,
   - flags best-guesses with `needs_review = TRUE`,
   - leaves Layer-2 fields blank with placeholders.
4. `draft_notes.md` lists assumptions, flagged rows, and any config↔history mismatches.
5. A human can open the output and edit it directly — it is a draft, never auto-published.

---

## 10. Explicitly OUT of scope for this build
- Any connection to internal databases, dashboards, or APIs.
- Trending keywords, stock, brand performance, outlier detection (Layer 2).
- Email or dashboard delivery (Layer 3).
- Global/MENA trend web-scanning (handled separately, interactively, for now).
- Auto-publishing or any write-back to live systems.
