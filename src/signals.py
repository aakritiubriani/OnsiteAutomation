"""
signals.py — Layer 2 hook (stub only — do NOT connect to any DB here)

This module defines the interface for enriching a draft calendar with
commercial signals once Layer 2 is approved and built.

Current behaviour: all functions are no-ops that return the draft unchanged.

─────────────────────────────────────────────────────────────────────────────
EXPECTED SIGNALS SHAPE (for Layer 2 implementation)
─────────────────────────────────────────────────────────────────────────────
signals: dict with any/all of these keys:

    trending_keywords: dict[canonical_key → list[str]]
        e.g. {"eoss": ["maxi dress", "linen set"], "bts": ["backpack"]}

    stock_flags: dict[canonical_key → str]
        e.g. {"bts": "LOW", "eoss": "OK"}
        Values: "OK" | "LOW" | "CRITICAL" | ""

    brand_performance_flags: dict[canonical_key → str]
        e.g. {"ramadan": "OVERPERFORMING"}
        Values: "OVERPERFORMING" | "UNDERPERFORMING" | "OK" | ""

    struggling_category_flags: dict[canonical_key → list[str]]
        e.g. {"eoss": ["footwear", "denim"]}

    new_activation_flags: dict[canonical_key → list[str]]
        e.g. {"payday": ["Brand X launch"]}

    outlier_flags: dict[canonical_key → str]
        e.g. {"world_cup": "OUTLIER_HIGH_DEMAND"}

    csv_path: str (optional)
        Path to a CSV file with columns:
            canonical_key, trending_keywords, stock_flag,
            brand_performance_flag, struggling_category_flag,
            new_activation_flag, outlier_flag
        Takes precedence over the dict fields above if provided.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations
from pathlib import Path
from typing import Union

import pandas as pd


LAYER2_COLS = [
    "trending_keywords",
    "stock_flag",
    "brand_performance_flag",
    "struggling_category_flag",
    "new_activation_flag",
    "outlier_flag",
]


def enrich_with_commercial_signals(
    draft_df: pd.DataFrame,
    signals: Union[dict, None] = None,
    csv_path: Union[str, Path, None] = None,
) -> pd.DataFrame:
    """
    Enrich draft_df with commercial signals.

    Currently a no-op stub: returns draft_df unchanged with Layer 2 columns
    set to empty strings (placeholders for the specialist's manual input).

    Parameters
    ----------
    draft_df  : DataFrame in the Standard Schema (output of generate.py)
    signals   : dict matching the shape described above, or None
    csv_path  : path to a signals CSV, or None

    Returns
    -------
    draft_df with LAYER2_COLS populated (currently all empty).
    """
    df = draft_df.copy()

    # Ensure Layer 2 columns exist
    for col in LAYER2_COLS:
        if col not in df.columns:
            df[col] = ""

    # ── TODO (Layer 2): implement below once DB access is approved ──────────
    # if csv_path:
    #     sig_df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    #     for col in LAYER2_COLS:
    #         if col in sig_df.columns:
    #             sig_map = sig_df.set_index("canonical_key")[col].to_dict()
    #             df[col] = df["canonical_key"].map(sig_map).fillna("")
    #
    # if signals:
    #     for col in LAYER2_COLS:
    #         key_in_signals = col + "s" if not col.endswith("s") else col
    #         signal_map = signals.get(col, signals.get(key_in_signals, {}))
    #         if signal_map:
    #             df[col] = df["canonical_key"].map(signal_map).fillna("")
    # ─────────────────────────────────────────────────────────────────────────

    return df
