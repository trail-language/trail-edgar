# trail-edgar

SEC EDGAR (10-K/10-Q) data source for [Trail](https://github.com/trail-language), via
[edgartools](https://github.com/dgunning/edgartools).

## Provides

- **Statements** (annual 10-K + quarterly 10-Q): `income.*`, `balance.*`, `cash.*` - revenue,
  cogs, operating/net income, interest, tax, EPS, balance-sheet lines (assets, liabilities,
  equity, receivables, inventory, payables, debt, goodwill, ...), and cash-flow lines (CFO, CFI,
  CFF, capex, dividends, ...).
- **Meta**: `meta.sector`, `meta.exchange`, `meta.is_active`, `meta.country` (normalized to
  ISO3). Entity dimension is the default `entity` (no bridge field).
- **Derived** fields, computed when no single us-gaap tag is reliable:

  | Field | Derivation |
  | --- | --- |
  | `income.gross_profit` | `GrossProfit` tag, else `revenue - cogs` |
  | `income.ebitda` | `operating_income + depreciation_amortization` (no us-gaap tag) |
  | `cash.free_cash_flow` | `cfo - abs(capex)` |
  | `balance.total_debt` | `long_term_debt + short_term_debt` |

- **Not provided** (declared unavailable, not fabricated): `price.adj_close`,
  `price.dividends`, `meta.market_cap` - SEC filings carry no market price.
  `income.weighted_average_shares_diluted` is provided, so a market cap can still be computed
  downstream once a price source is joined in.

## Configure

```yaml
# trail.yaml
sources:
  sec:
    driver: edgar
    options:
      identity: "Your Name your.email@example.com"   # or set the EDGAR_IDENTITY env var
      tickers: [AAPL, MSFT, NVDA]      # or use `universe:` instead
      years: [2017, 2024]
      cache_dir: ".edgar-cache"
precedence:
  default: [sec]
panel:
  strict: true
```

Then:

```bash
trail catalog sec                                  # coverage: fields this source provides
trail run model.trail --model m --config trail.yaml
```

## Options

| Option | Type | Default | Notes |
| --- | --- | --- | --- |
| `identity` | `str` | - (required) | SEC fair-access identity, e.g. `"Your Name your.email@example.com"`. Falls back to the `EDGAR_IDENTITY` env var. Neither set -> `E-EDGAR-IDENTITY`. |
| `tickers` | `list[str]` | `[]` | Explicit fetch universe. Takes precedence over `universe`; a caller-supplied entity list (e.g. a model's own universe) overrides both at load time. |
| `universe` | `str` | `None` | Named universe, resolved via edgartools' curated helpers, used only when `tickers` is empty: `faang`, `tech_giants`, `dow`. Unknown name -> `E-EDGAR-UNIVERSE`. There is no live index-membership feed, so broader index coverage (e.g. the full S&P 500) needs an explicit `tickers` list. |
| `years` | `[lo, hi]` | `None` | Inclusive fiscal-year bound to fetch. A model's own `periods(...)` range, when present, overrides this. |
| `periods` | `int` | `8` | Fallback count of most-recent annual periods to fetch when neither `years` nor a model `periods(...)` range narrows the fetch. |
| `cache_dir` | `str` | `None` | Sets `EDGAR_LOCAL_DATA_DIR` (via `setdefault`, so the first `EdgarSource` constructed in a process wins) for edgartools' local filing cache. |
| `pit` | `str` | unset | `pit: naive` disables point-in-time for this source only - a per-source override of the global `panel.pit` setting, read by Trail's runtime rather than by `EdgarSource` itself. |

For quarterly loads (`frequency: quarterly`), whichever annual period count is resolved above is
fetched in quarters instead (4x).

SEC fair access requires `identity` on every request; edgartools throttles to the SEC rate limit
and caches filings locally (under `cache_dir` when set).

## Point-in-time

Statement fields (`income.*`, `balance.*`, `cash.*`) carry a `__date:filing_date` coordinate: the
earliest 10-K/10-Q filing date for each fiscal period, read from `company.facts` (already fetched
by the statement calls, so this costs no extra network round-trip). A fiscal period can appear in
more than one filing - a later 10-K's comparative column repeats a prior period under a later
filing date - so the earliest date is kept, recovering the period's original disclosure rather
than a restatement/comparative date.

`meta.*` fields (sector, exchange, country, is_active) are naive - current attributes broadcast
onto every period, not filing-dated.

`options.pit: naive` (or a global `panel.pit: naive`) disables the coordinate for this source;
every field then places at its period-end instead.

## Notes

- Non-December fiscal years are approximated: period `time` values snap to calendar
  quarter/year ends (Mar 31 / Jun 30 / Sep 30 / Dec 31), not a company's actual fiscal
  period end - canonical fiscal-calendar alignment is a later phase.
- The earliest-filing heuristic depends on the raw `FinancialFact.fiscal_year`/`fiscal_period`
  matching the period keys parsed from the statement frames' column labels - two independent
  reads of the same edgartools data - so a period only gets a filing date when both agree on the
  key; otherwise alignment falls back to period-end.
- Structurally absent lines (e.g. inventory for a bank) come through as null rather than errors.
- `capex` and `dividends_paid` are reported as positive outflow magnitudes in some filings; both
  are normalized with `abs()`.
- `meta.is_active` is a constant `True` for any company the source can fetch - there is no
  delisted/inactive detection; it exists for schema parity with other sources.
- Concept resolution takes the first us-gaap tag present from an ordered priority list per field
  (see `trail_edgar/mapping.py`), verified against live filings; a niche tag not on the list
  surfaces as null.

## License

MIT.
