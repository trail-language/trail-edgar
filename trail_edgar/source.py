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
from trail.country import to_iso3
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


# SEC 'state_or_country' uses US 2-letter state codes for domestic filers; these must resolve
# to USA, not be read as ISO alpha-2 country codes ("AL" is Alabama, not Albania).
_US_STATES = frozenset({
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
    "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT",
    "VA", "WA", "WV", "WI", "WY", "DC", "PR", "VI", "GU", "AS", "MP",
})


def _country_of(company) -> str | None:
    """Best-effort ISO3 country from the filer's SEC address. US state codes resolve to USA;
    foreign codes are mapped where they align with ISO alpha-2, else None (a null bridge)."""
    addr = getattr(company, "business_address", None) or getattr(company, "mailing_address", None)
    code = getattr(addr, "state_or_country", None) if addr is not None else None
    if not code:
        return None
    code = str(code).strip().upper()
    return "USA" if code in _US_STATES else to_iso3(code)


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
            # set-if-unset: edgartools reads this at its own import/config time, and two
            # sources in one process must not clobber each other's cache location
            os.environ.setdefault("EDGAR_LOCAL_DATA_DIR", str(cache_dir))
        from edgar import set_identity

        set_identity(identity)
        self._tickers = [str(t).upper() for t in (self.options.get("tickers") or [])]
        self._universe = self.options.get("universe")

    # --- core tier ---
    def load(self, fields: set[str], *, periods: tuple[int, int] | None = None,
             entities: list[str] | None = None, frequency: str | None = None) -> pl.DataFrame:
        requested = {f for f in fields if f in mapping.PROVIDED_FIELDS}
        n_periods, bounds = period_util.year_bounds(self.options, periods)
        period = "quarterly" if frequency == "quarterly" else "annual"
        if period == "quarterly":
            n_periods *= 4  # the year bound counts years; 10-Q statements come per quarter
        # a caller-supplied universe (Trail's entities= seam) scopes the fetch, overriding
        # options.tickers / options.universe; otherwise fall back to the configured set.
        tickers = [str(t).upper() for t in entities] if entities else self.entities()
        per_entity = []
        for ticker in tickers:
            company, statements = self._fetch_statements(ticker, n_periods, period)
            concepts = convert.concepts_from_statements(statements)
            meta = self._meta_for(company, requested)
            per_entity.append((ticker, concepts, meta))
        panel = convert.to_panel(per_entity, requested)
        if bounds is not None and panel.height:
            lo, hi = bounds
            yr = pl.col("time").dt.year()
            panel = panel.filter((yr >= lo) & (yr <= hi))
        return panel

    def _fetch_statements(self, ticker: str, n_periods: int, period: str = "annual"):
        """Fetch the three statements for a ticker at `period` (the network seam)."""
        from edgar import Company

        company = Company(ticker)
        income = company.income_statement(periods=n_periods, period=period, as_dataframe=True)
        balance = company.balance_sheet(periods=n_periods, period=period, as_dataframe=True)
        cashflow = company.cashflow_statement(periods=n_periods, period=period, as_dataframe=True)
        return company, [income, balance, cashflow]

    def _meta_for(self, company, fields: set[str]) -> dict:
        meta: dict = {}
        if "meta.is_active" in fields:
            meta["meta.is_active"] = True
        if "meta.exchange" in fields:
            meta["meta.exchange"] = _first_exchange(company)
        if "meta.sector" in fields:
            meta["meta.sector"] = _sector_of(company)
        if "meta.country" in fields:
            meta["meta.country"] = _country_of(company)
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

    def entities(self, universe: str | None = None) -> list[str]:
        if self._tickers:
            return list(self._tickers)
        name = universe or self._universe
        return universe_util.named_universe(name) if name else []

    def capabilities(self) -> Capabilities:
        return Capabilities(
            frequency="annual",
            frequencies=("annual", "quarterly"),
            forms=("10-K", "10-Q"),
            provides_meta=True,
            provenance="SEC EDGAR via edgartools",
        )

    def close(self) -> None:
        pass
