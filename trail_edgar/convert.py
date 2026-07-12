"""Turn edgartools statement frames into a Trail panel.

edgartools returns one pandas DataFrame per statement (income, balance, cash flow) with
the us-gaap concept on the index and fiscal-year columns labelled like ``FY 2024``. We
melt those into a ``{concept: {fiscal_year: value}}`` mapping (:func:`concepts_from_statements`),
resolve each requested Trail field via :mod:`trail_edgar.mapping`, and pivot the result
to a ``(security x period)`` polars panel (:func:`to_panel`). Pandas is only ever touched
through the passed-in frames; the output is pure polars.
"""
from __future__ import annotations

import math
import re

import polars as pl

from trail_edgar import mapping

_FY_RE = re.compile(r"FY\s*(\d{4})")


def fiscal_year(column_label: object) -> int | None:
    """Parse an int fiscal year from an edgartools column label, or None."""
    m = _FY_RE.search(str(column_label))
    return int(m.group(1)) if m else None


def concepts_from_statements(statements) -> mapping.Concepts:
    """Build ``{concept: {fiscal_year: value}}`` from pandas statement frames.

    Non-fiscal-year columns (label, confidence, ...) are ignored. When a concept
    appears in more than one statement, the first value seen for a year is kept.
    """
    concepts: mapping.Concepts = {}
    for df in statements:
        if df is None or getattr(df, "empty", False):
            continue
        year_cols = [(c, fiscal_year(c)) for c in df.columns]
        year_cols = [(c, y) for c, y in year_cols if y is not None]
        if not year_cols:
            continue
        for concept, row in df.iterrows():
            series = concepts.setdefault(str(concept), {})
            for col, year in year_cols:
                value = row[col]
                if value is None:
                    continue
                try:
                    fval = float(value)
                except (TypeError, ValueError):
                    continue
                if math.isnan(fval):
                    continue
                series.setdefault(year, fval)
    return concepts


def _panel_schema(numeric_fields: list[str], meta_fields: list[str]) -> dict:
    schema: dict = {"security": pl.Utf8, "period": pl.Int32}
    for f in numeric_fields:
        schema[f] = pl.Float64
    for f in meta_fields:
        schema[f] = pl.Boolean if f == "meta.is_active" else pl.Utf8
    return schema


def to_panel(per_security, fields: set[str]) -> pl.DataFrame:
    """Assemble the panel from resolved per-security data.

    ``per_security`` is an iterable of ``(security, concepts, meta)`` where ``concepts``
    is a :data:`mapping.Concepts` mapping and ``meta`` maps meta fields to per-security
    constants. Returns a ``(security, period)`` panel restricted to ``fields`` (plus the
    two index columns), with an explicit schema so an empty result is still well typed.
    """
    numeric_fields = sorted(f for f in fields if f in mapping.PROVIDED_FIELDS
                            and f not in mapping.META_FIELDS)
    meta_fields = sorted(f for f in fields if f in mapping.META_FIELDS)
    schema = _panel_schema(numeric_fields, meta_fields)
    cols: dict[str, list] = {name: [] for name in schema}

    for security, concepts, meta in per_security:
        series = {f: mapping.resolve_field(f, concepts) for f in numeric_fields}
        years = sorted({y for s in series.values() for y in s})
        for year in years:
            cols["security"].append(security)
            cols["period"].append(year)
            for f in numeric_fields:
                cols[f].append(series[f].get(year))
            for f in meta_fields:
                cols[f].append(meta.get(f))

    df = pl.DataFrame(cols, schema=schema)
    return df.sort(["security", "period"]) if df.height else df
