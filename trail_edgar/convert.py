"""Turn edgartools statement frames into a Trail panel.

edgartools returns one pandas DataFrame per statement (income, balance, cash flow) with
the us-gaap concept on the index and fiscal-year columns labelled like ``FY 2024``. We
melt those into a ``{concept: {fiscal_year: value}}`` mapping (:func:`concepts_from_statements`),
resolve each requested Trail field via :mod:`trail_edgar.mapping`, and pivot the result
to a ``(entity x time)`` polars panel (:func:`to_panel`). Pandas is only ever touched
through the passed-in frames; the output is pure polars.
"""
from __future__ import annotations

import datetime as dt
import math
import re

import polars as pl

from trail.source import date_col

from trail_edgar import mapping

_PERIOD_RE = re.compile(r"(FY|Q[1-4])\s*(\d{4})")

#: physical column for the per-period 10-K/10-Q filing-date alignment coordinate (see
#: trail_edgar.source._filing_dates and EdgarSource.describe_field's aligns_on).
FILING_DATE_COL = date_col("filing_date")


def period_key(column_label: object) -> tuple[int, int] | None:
    """``(year, quarter)`` from an edgartools column label - quarter 0 for a fiscal year
    (``FY 2024``), 1-4 for a fiscal quarter (``Q3 2024``) - or None for non-period columns.
    Tuple keys sort chronologically within one frequency; a load is always one frequency."""
    m = _PERIOD_RE.search(str(column_label))
    if not m:
        return None
    tag, year = m.group(1), int(m.group(2))
    return (year, 0) if tag == "FY" else (year, int(tag[1]))


def fiscal_year(column_label: object) -> int | None:
    """Parse an int fiscal year from an annual column label (``FY 2024``), or None."""
    key = period_key(column_label)
    return key[0] if key is not None and key[1] == 0 else None


def concepts_from_statements(statements) -> mapping.Concepts:
    """Build ``{concept: {period_key: value}}`` from pandas statement frames.

    Non-period columns (label, confidence, ...) are ignored. When a concept
    appears in more than one statement, the first value seen for a period is kept.
    """
    concepts: mapping.Concepts = {}
    for df in statements:
        if df is None or getattr(df, "empty", False):
            continue
        period_cols = [(c, period_key(c)) for c in df.columns]
        period_cols = [(c, k) for c, k in period_cols if k is not None]
        if not period_cols:
            continue
        for concept, row in df.iterrows():
            series = concepts.setdefault(str(concept), {})
            for col, key in period_cols:
                value = row[col]
                if value is None:
                    continue
                try:
                    fval = float(value)
                except (TypeError, ValueError):
                    continue
                if math.isnan(fval):
                    continue
                series.setdefault(key, fval)
    return concepts


# period key -> calendar period-end month/day. Quarter 0 is a full fiscal year. Fiscal
# quarters are mapped to calendar quarter-ends of the label year - the same simplification
# the annual path applies (FY -> Dec 31); canonical fiscal alignment is a later phase.
_Q_END = {0: (12, 31), 1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}


def _period_end(key: tuple[int, int]) -> dt.datetime:
    year, q = key
    month, day = _Q_END[q]
    return dt.datetime(year, month, day)


def _panel_schema(numeric_fields: list[str], meta_fields: list[str], include_filing_date: bool) -> dict:
    schema: dict = {"entity": pl.Utf8, "time": pl.Datetime("us")}
    for f in numeric_fields:
        schema[f] = pl.Float64
    for f in meta_fields:
        schema[f] = pl.Boolean if f == "meta.is_active" else pl.Utf8
    if include_filing_date:
        schema[FILING_DATE_COL] = pl.Datetime("us")
    return schema


def to_panel(per_entity, fields: set[str]) -> pl.DataFrame:
    """Assemble the panel from resolved per-entity data.

    ``per_entity`` is an iterable of ``(entity, concepts, meta, filing_dates)`` where
    ``concepts`` is a :data:`mapping.Concepts` mapping, ``meta`` maps meta fields to
    per-entity constants, and ``filing_dates`` maps a period key to its 10-K/10-Q filing
    date (see :func:`trail_edgar.source._filing_dates`). Returns a ``(entity, time)`` panel
    restricted to ``fields`` (plus the two index columns), with an explicit schema so an
    empty result is still well typed. When any statement-derived field is requested, the
    panel also carries :data:`FILING_DATE_COL`, the alignment coordinate those fields align
    on (null where a period's filing date is unavailable - the align engine coalesces that
    to period-end).
    """
    numeric_fields = sorted(f for f in fields if f in mapping.PROVIDED_FIELDS
                            and f not in mapping.META_FIELDS)
    meta_fields = sorted(f for f in fields if f in mapping.META_FIELDS)
    include_filing_date = bool(numeric_fields)
    schema = _panel_schema(numeric_fields, meta_fields, include_filing_date)
    cols: dict[str, list] = {name: [] for name in schema}

    for entity, concepts, meta, filing_dates in per_entity:
        series = {f: mapping.resolve_field(f, concepts) for f in numeric_fields}
        keys = sorted({k for s in series.values() for k in s})
        for key in keys:
            cols["entity"].append(entity)
            cols["time"].append(_period_end(key))
            for f in numeric_fields:
                cols[f].append(series[f].get(key))
            for f in meta_fields:
                cols[f].append(meta.get(f))
            if include_filing_date:
                cols[FILING_DATE_COL].append(filing_dates.get(key))

    df = pl.DataFrame(cols, schema=schema)
    return df.sort(["entity", "time"]) if df.height else df
