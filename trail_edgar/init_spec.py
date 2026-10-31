"""The `trail init edgar` registration: prompt fields + the canonical trail.yaml template.

The engine's generic `trail init <driver>` (trail-lang) resolves this spec through the
`trail.init` entry point and does the prompting and the file write; the values land in the
``{identity}`` / ``{tickers}`` / ``{years}`` placeholders (the CLI normalizes comma-separated
inputs to canonical ``", "``-joined flow-list content).
"""
from __future__ import annotations

from trail.init import InitField, InitSpec

TEMPLATE = """\
# Minimal Trail config: SEC EDGAR source, 2-ticker universe, annual 2020-2024.
sources:
  edgar:
    driver: edgar                      # source driver name (entry point provided by trail-edgar)
    options:
      identity: "{identity}"           # SEC fair-access 'Your Name your.email@example.com'
      tickers: [{tickers}]             # tickers to fetch
      years: [{years}]                 # the N most-recent fiscal years the driver fetches
      cache_dir: .edgar-cache          # local cache dir (relative paths are fine)
precedence:
  default: [edgar]                     # field-namespace -> source resolution order
panel:
  periods: [{years}]                   # requested panel window
  pit: auto                            # as-of filing-date placement
  strict: false
"""

EDGAR_INIT = InitSpec(
    driver="edgar",
    package="trail-edgar",
    install_hint="pipx inject trail-lang trail-edgar",
    fields=(
        InitField("identity", 'SEC fair-access identity ("Your Name your.email@example.com")'),
        InitField("tickers", "Tickers (comma-separated)", default="AAPL,MSFT"),
        InitField("years", "Years (start,end)", default="2020,2024"),
    ),
    template=TEMPLATE,
)
