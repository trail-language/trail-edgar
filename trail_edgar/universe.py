"""Universe / ticker resolution for the edgar source.

Securities come primarily from an explicit ``tickers`` list in trail.yaml options. A few
named universes are also supported through edgartools' curated helpers. There is no live
S&P 500 membership feed, so index coverage requires an explicit ticker list.
"""
from __future__ import annotations

from trail.config import ConfigError

# named universe -> edgartools company_subsets helper function
_NAMED = {
    "faang": "get_faang_companies",
    "tech_giants": "get_tech_giants",
    "dow": "get_dow_jones_sample",
}


def _tickers_from(df) -> list[str]:
    for col in ("ticker", "tickers", "symbol"):
        if col in getattr(df, "columns", []):
            return [str(t).upper() for t in df[col].tolist()]
    raise ConfigError("E-EDGAR-UNIVERSE could not extract tickers from the named subset")


def named_universe(name: str) -> list[str]:
    """Resolve a named universe to a ticker list, or raise ConfigError if unknown."""
    helper = _NAMED.get(name)
    if helper is None:
        raise ConfigError(
            f"E-EDGAR-UNIVERSE unknown universe '{name}'; known: {sorted(_NAMED)} "
            f"or pass an explicit 'tickers' list"
        )
    from edgar.reference import company_subsets

    return _tickers_from(getattr(company_subsets, helper)())
