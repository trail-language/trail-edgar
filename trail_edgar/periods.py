"""Fiscal-year period handling for the edgar source."""
from __future__ import annotations

DEFAULT_PERIODS = 8


def year_bounds(options: dict, periods_arg: tuple[int, int] | None):
    """Return ``(n_periods_to_fetch, (lo, hi) | None)``.

    A caller-supplied ``periods`` range (passed by the runtime) wins over
    ``options['years']``. ``n_periods`` is how many annual periods to request from
    edgartools: when a range is known we fetch one extra for safety, otherwise
    ``options['periods']`` or :data:`DEFAULT_PERIODS`.
    """
    if periods_arg is not None:
        lo, hi = int(periods_arg[0]), int(periods_arg[1])
    else:
        years = options.get("years")
        lo, hi = (int(years[0]), int(years[1])) if years else (None, None)

    if lo is not None and hi is not None:
        n = max(hi - lo + 1, 1) + 1
        bounds = (lo, hi)
    else:
        n = int(options.get("periods", DEFAULT_PERIODS))
        bounds = None
    return n, bounds
