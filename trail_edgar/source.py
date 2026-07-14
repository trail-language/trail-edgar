"""EdgarSource: a Trail data source backed by SEC EDGAR via edgartools.

Implements the full extended-tier contract (:class:`trail.source.ExtendedDataSource`):
loads normalized annual (10-K) income, balance-sheet, and cash-flow figures for a
configured set of tickers, reports which canonical fields it can supply, enumerates its
universe, and describes its capabilities. Market price and market cap are declared
unavailable, since SEC filings do not carry a price.
"""
from __future__ import annotations

import os

import polars as pl

from trail.config import ConfigError
from trail.source import Capabilities, ExtendedDataSource, FieldInfo

from trail_edgar import convert, mapping
from trail_edgar import periods as period_util
from trail_edgar import universe as universe_util

_FIELD_NOTES = {
    "income.gross_profit": "GrossProfit tag, else revenue - cogs",
    "cash.free_cash_flow": "derived: cfo - abs(capex)",
    "balance.total_debt": "derived: long_term_debt + short_term_debt",
    "cash.capex": "reported magnitude, normalized with abs()",
    "cash.stock_issued": "ProceedsFromIssuanceOfCommonStock; often null for buyback-heavy issuers",
    "income.weighted_average_shares_diluted": "raw WeightedAverageNumberOfDilutedSharesOutstanding",
}


def _first_exchange(company) -> str | None:
    try:
        exchanges = company.get_exchanges()
    except Exception:
        return None
    return str(exchanges[0]) if exchanges else None


def _sector_of(company) -> str | None:
    for attr in ("sic_description", "industry", "sector"):
        value = getattr(company, attr, None)
        if value:
            return str(value)
    return None


class EdgarSource(ExtendedDataSource):
    """SEC EDGAR annual financial statements as a Trail panel."""

    name = "edgar"

    def __init__(self, options: dict | None = None) -> None:
        super().__init__(options)
        identity = self.options.get("identity") or os.environ.get("EDGAR_IDENTITY")
        if not identity:
            raise ConfigError(
                "E-EDGAR-IDENTITY SEC fair-access requires an identity; set "
                "options.identity ('Your Name your.email@example.com') or EDGAR_IDENTITY"
            )
        cache_dir = self.options.get("cache_dir")
        if cache_dir:
            os.environ["EDGAR_LOCAL_DATA_DIR"] = str(cache_dir)
        from edgar import set_identity

        set_identity(identity)
        self._tickers = [str(t).upper() for t in (self.options.get("tickers") or [])]
        self._universe = self.options.get("universe")

    # --- core tier ---
    def load(self, fields: set[str], *, periods: tuple[int, int] | None = None) -> pl.DataFrame:
        requested = {f for f in fields if f in mapping.PROVIDED_FIELDS}
        n_periods, bounds = period_util.year_bounds(self.options, periods)
        per_entity = []
        for ticker in self.securities():
            company, statements = self._fetch_statements(ticker, n_periods)
            concepts = convert.concepts_from_statements(statements)
            meta = self._meta_for(company, requested)
            per_entity.append((ticker, concepts, meta))
        panel = convert.to_panel(per_entity, requested)
        if bounds is not None and panel.height:
            lo, hi = bounds
            panel = panel.filter((pl.col("period") >= lo) & (pl.col("period") <= hi))
        return panel

    def _fetch_statements(self, ticker: str, n_periods: int):
        """Fetch the three annual statements for a ticker (the network seam)."""
        from edgar import Company

        company = Company(ticker)
        income = company.income_statement(periods=n_periods, period="annual", as_dataframe=True)
        balance = company.balance_sheet(periods=n_periods, period="annual", as_dataframe=True)
        cashflow = company.cashflow_statement(periods=n_periods, period="annual", as_dataframe=True)
        return company, [income, balance, cashflow]

    def _meta_for(self, company, fields: set[str]) -> dict:
        meta: dict = {}
        if "meta.is_active" in fields:
            meta["meta.is_active"] = True
        if "meta.exchange" in fields:
            meta["meta.exchange"] = _first_exchange(company)
        if "meta.sector" in fields:
            meta["meta.sector"] = _sector_of(company)
        return meta

    # --- extended tier ---
    def available_fields(self) -> set[str]:
        return set(mapping.PROVIDED_FIELDS)

    def describe_field(self, field: str) -> FieldInfo | None:
        if field in mapping.PROVIDED_FIELDS:
            return FieldInfo(field, True, mapping.strategy_of(field), _FIELD_NOTES.get(field, ""))
        if field in mapping.UNAVAILABLE_FIELDS:
            return FieldInfo(field, False, "unavailable", "SEC filings do not carry market price")
        return None

    def securities(self, universe: str | None = None) -> list[str]:
        if self._tickers:
            return list(self._tickers)
        name = universe or self._universe
        return universe_util.named_universe(name) if name else []

    def capabilities(self) -> Capabilities:
        return Capabilities(
            frequency="annual",
            forms=("10-K",),
            provides_meta=True,
            provenance="SEC EDGAR via edgartools",
        )

    def close(self) -> None:
        pass
