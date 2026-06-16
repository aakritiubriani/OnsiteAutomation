"""
wireframe.py — Phase 1: campaign wireframe export.

Reads the tile catalog (config/wireframe_tiles.yaml) and the reviewed
campaign rows from the Campaign Planning tab, and writes one Excel sheet
per month with a simple block-mockup per campaign: one row per tile,
merged across columns proportional to the tile's declared width, labeled
with the tile name. SKU and copy selection (Phase 2) and rendered tile
images (Phase 3) are not part of this export — those slots are left as
labeled placeholders.
"""

from pathlib import Path

import openpyxl
import yaml
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

BASE        = Path(__file__).resolve().parent.parent
TILES_FILE  = BASE / "config" / "wireframe_tiles.yaml"
GRID_COLS   = 4  # mockup width in grid units (matches tile "width" field)

HEADER_FILL  = PatternFill("solid", fgColor="FF000000")
HEADER_FONT  = Font(name="Calibri", bold=True, size=13, color="FF00FF00")
CAMPAIGN_FILL = PatternFill("solid", fgColor="FF1A1A1A")
CAMPAIGN_FONT = Font(name="Calibri", bold=True, size=11, color="FFFFFFFF")
META_FONT     = Font(name="Calibri", size=9, color="FFAAAAAA")
TILE_FILL     = PatternFill("solid", fgColor="FFEFEFEF")
TILE_FONT     = Font(name="Calibri", bold=True, size=10)
PLACEHOLDER_FONT = Font(name="Calibri", italic=True, size=9, color="FF999999")
THIN  = Side(style="thin", color="FFCCCCCC")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def load_tile_catalog() -> list[dict]:
    """Return the tile catalog as a list of dicts (id, label, width, height, notes)."""
    if not TILES_FILE.exists():
        return []
    with open(TILES_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("tiles", [])


def tile_catalog_map() -> dict:
    """id -> tile dict, for quick lookup."""
    return {t["id"]: t for t in load_tile_catalog()}


def build_wireframe_summary(tile_ids: list[str]) -> str:
    """Human-readable summary string for the legacy 'wireframes' text column."""
    catalog = tile_catalog_map()
    parts = []
    for i, tid in enumerate(tile_ids, start=1):
        label = catalog.get(tid, {}).get("label", tid)
        parts.append(f"{i}. {label}")
    return "  ".join(parts) if parts else "TBD"


def write_wireframe_xlsx(campaigns: list[dict], filepath, month: int, year: int):
    """
    campaigns: list of campaign dicts, each with at least:
        campaign_name, tier, geography, start_date, end_date,
        category_focus, wireframe_tiles (list of tile-id strings)
    """
    import calendar as cal_mod
    month_name = cal_mod.month_name[month]
    catalog = tile_catalog_map()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{month_name[:3]} {year} Wireframes"

    last_col = GRID_COLS
    last_col_letter = openpyxl.utils.get_column_letter(last_col)

    ws.merge_cells(f"A1:{last_col_letter}1")
    title_cell = ws["A1"]
    title_cell.value = f"Campaign Wireframes — {month_name} {year}"
    title_cell.font = HEADER_FONT
    title_cell.fill = HEADER_FILL
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 24

    ws.merge_cells(f"A2:{last_col_letter}2")
    sub_cell = ws["A2"]
    sub_cell.value = "DRAFT wireframe — tile placement only. SKU/copy selection is Phase 2; tile images are Phase 3."
    sub_cell.font = META_FONT
    sub_cell.fill = CAMPAIGN_FILL
    sub_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 14

    row = 4
    for camp in campaigns:
        tiles = camp.get("wireframe_tiles") or []

        # Campaign header block
        ws.merge_cells(f"A{row}:{last_col_letter}{row}")
        cell = ws.cell(row=row, column=1)
        meta_bits = [camp.get("tier", ""), camp.get("geography", ""),
                     camp.get("start_date", ""), camp.get("category_focus", "")]
        meta_bits = [b for b in meta_bits if b]
        cell.value = f"{camp.get('campaign_name', '(untitled)')}  —  {' | '.join(meta_bits)}"
        cell.font = CAMPAIGN_FONT
        cell.fill = CAMPAIGN_FILL
        cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws.row_dimensions[row].height = 20
        row += 1

        if not tiles:
            ws.merge_cells(f"A{row}:{last_col_letter}{row}")
            cell = ws.cell(row=row, column=1, value="No tiles assigned yet — add tiles in the planner before exporting.")
            cell.font = PLACEHOLDER_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[row].height = 18
            row += 1
        else:
            for entry in tiles:
                # entry is either a legacy tile-id string, or a dict
                # {tile_id, copy_en, copy_en_refined, copy_ar} once copy has been added.
                if isinstance(entry, dict):
                    tid = entry.get("tile_id", "")
                    copy_en_refined = (entry.get("copy_en_refined") or "").strip()
                    copy_ar = (entry.get("copy_ar") or "").strip()
                else:
                    tid = entry
                    copy_en_refined = copy_ar = ""

                tile = catalog.get(tid, {"label": tid, "width": GRID_COLS, "height": 1})
                width = max(1, min(GRID_COLS, int(tile.get("width", GRID_COLS))))
                height = max(1, int(tile.get("height", 1)))

                start_col = 1
                end_col = width
                if end_col > start_col:
                    ws.merge_cells(start_row=row, start_column=start_col,
                                   end_row=row + height - 1, end_column=end_col)
                cell = ws.cell(row=row, column=start_col)
                if copy_en_refined or copy_ar:
                    copy_block = "\n".join(b for b in (copy_en_refined, copy_ar) if b)
                    cell.value = f"{tile.get('label', tid)}\n{copy_block}\n[SKU: TBD]"
                else:
                    cell.value = f"{tile.get('label', tid)}\n[SKU + copy: TBD]"
                cell.font = TILE_FONT
                cell.fill = TILE_FILL
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.border = BORDER

                # Border the remaining (non-merged) cells in the row for a clean grid look
                for c in range(start_col, end_col + 1):
                    for r in range(row, row + height):
                        ws.cell(row=r, column=c).border = BORDER

                for r in range(row, row + height):
                    ws.row_dimensions[r].height = 24

                row += height

        row += 1  # spacer between campaigns

    for col_idx in range(1, last_col + 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = 28

    wb.save(filepath)
