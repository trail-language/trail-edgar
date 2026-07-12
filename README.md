# trail-edgar

SEC EDGAR data source for [Trail](https://github.com/trail-language/trail-py). It exposes
normalized annual (10-K) financial statements - income statement, balance sheet, and
cash-flow statement - as a Trail `(security x period)` panel, using
[edgartools](https://github.com/dgunning/edgartools) under the hood.

## Install

```bash
pip install trail-edgar
```

## Configure

Reference the source by name in `trail.yaml` (installing this package registers the
`edgar` driver):

```yaml
sources:
  sec:
    driver: edgar
    options:
      identity: "Your Name your.email@example.com"   # or set the EDGAR_IDENTITY env var
      tickers: [AAPL, MSFT, NVDA]
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

## Fields

Provided: all `income.*`, `balance.*`, `cash.*`, and `meta.sector` / `meta.exchange` /
`meta.is_active`. Three fields are derived where the SEC has no single reliable tag:

| Field | Derivation |
| --- | --- |
| `income.gross_profit` | `GrossProfit` tag, else `revenue - cogs` |
| `cash.free_cash_flow` | `cfo - abs(capex)` |
| `balance.total_debt` | `long_term_debt + short_term_debt` |

Not provided: `price.adj_close` and `meta.market_cap`. SEC filings do not carry a market
price, so the source declares these unavailable rather than fabricating them.
`income.weighted_average_shares_diluted` is provided, so a market cap can be computed
downstream once a dedicated price source is added.

## SEC fair-access

The SEC requires a User-Agent identity on every request. Set `options.identity` or the
`EDGAR_IDENTITY` environment variable to something like `"Your Name you@example.com"`.
edgartools throttles to the SEC rate limit and caches filings locally (under `cache_dir`
when set).

## Scope

Annual (10-K) only in this release; quarterly (10-Q) is deferred. Values are as-reported
us-gaap facts. Structurally absent lines (for example inventory for a bank) come through
as null rather than as errors. `capex` is normalized to a positive magnitude before it is
used in `free_cash_flow`.

## License

MIT.
