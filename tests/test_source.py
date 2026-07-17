import datetime as dt

import polars as pl
import pytest

from trail.config import ConfigError
from trail.source import LoadRequest, date_col
from trail.testing import assert_source_conforms

from trail_edgar.source import EdgarSource, _filing_dates


def test_conforms_to_contract(edgar_source):
    fields = {
        "income.revenue", "income.gross_profit", "cash.free_cash_flow",
        "balance.total_debt", "cash.capex", "meta.sector", "meta.exchange",
    }
    assert_source_conforms(edgar_source, fields)


def test_available_fields_excludes_price_and_market_cap(edgar_source):
    avail = edgar_source.available_fields()
    assert "income.revenue" in avail
    assert "price.adj_close" not in avail
    assert "meta.market_cap" not in avail


def test_describe_unavailable_field(edgar_source):
    info = edgar_source.describe_field("price.adj_close")
    assert info is not None and info.available is False and info.strategy == "unavailable"


def test_values_and_derivations(edgar_source):
    panel = edgar_source.load(
        LoadRequest(fields=frozenset({
            "income.revenue", "income.gross_profit", "cash.free_cash_flow",
            "balance.total_debt", "cash.capex", "meta.sector",
        }))
    )
    row = panel.filter(
        (pl.col("entity") == "AAA") & (pl.col("time").dt.year() == 2024)
    ).to_dicts()[0]
    assert row["income.revenue"] == 1000.0
    assert row["income.gross_profit"] == 400.0  # revenue - cogs
    assert row["cash.free_cash_flow"] == 250.0  # cfo - abs(capex)
    assert row["balance.total_debt"] == 700.0  # long + short term
    assert row["cash.capex"] == 50.0  # abs
    assert row["meta.sector"] == "Technology"


def test_securities_from_tickers(edgar_source):
    assert edgar_source.entities() == ["AAA", "BBB"]


def test_entities_kwarg_overrides_configured_tickers(edgar_source):
    panel = edgar_source.load(LoadRequest(fields=frozenset({"income.revenue"}), entities=("ccc",)))
    assert panel["entity"].unique().to_list() == ["CCC"]  # caller universe wins, normalized upper


def test_load_without_entities_uses_configured_tickers(edgar_source):
    panel = edgar_source.load(LoadRequest(fields=frozenset({"income.revenue"})))
    assert set(panel["entity"].unique().to_list()) == {"AAA", "BBB"}


def test_meta_country_normalizes_us_state_to_iso3(edgar_source):
    panel = edgar_source.load(LoadRequest(fields=frozenset({"income.revenue", "meta.country"})))
    assert panel["meta.country"].unique().to_list() == ["USA"]  # address "CA" -> USA


def test_meta_country_available_and_described(edgar_source):
    assert "meta.country" in edgar_source.available_fields()
    info = edgar_source.describe_field("meta.country")
    assert info is not None and info.available is True


def test_capabilities(edgar_source):
    caps = edgar_source.capabilities()
    assert caps.frequency == "annual" and caps.forms == ("10-K", "10-Q")
    assert caps.frequencies == ("annual", "quarterly")


def test_period_bounds_filter(monkeypatch, statements):
    src = EdgarSource(
        {"identity": "Trail Test test@example.com", "tickers": ["AAA"], "years": [2024, 2024]}
    )
    monkeypatch.setattr(
        EdgarSource, "_fetch_statements", lambda self, t, n, period="annual": (object(), statements)
    )
    panel = src.load(LoadRequest(fields=frozenset({"income.revenue"})))
    assert panel["time"].dt.year().unique().to_list() == [2024]


def test_new_field_mappings(edgar_source):
    panel = edgar_source.load(LoadRequest(fields=frozenset({
        "income.ebitda", "income.depreciation_amortization", "income.sga",
        "balance.net_fixed_assets", "balance.goodwill", "balance.minority_interest",
        "cash.cfi", "cash.net_change_in_cash", "cash.dividends_paid",
    })))
    row = panel.filter(
        (pl.col("entity") == "AAA") & (pl.col("time").dt.year() == 2024)
    ).to_dicts()[0]
    assert row["income.depreciation_amortization"] == 40.0
    assert row["income.ebitda"] == 240.0            # derived: operating income 200 + d&a 40
    assert row["income.sga"] == 100.0
    assert row["balance.net_fixed_assets"] == 900.0
    assert row["balance.goodwill"] == 400.0
    assert row["cash.cfi"] == -120.0                # signed flow
    assert row["cash.net_change_in_cash"] == 100.0
    assert row["cash.dividends_paid"] == 60.0       # abs of -60


def test_quarterly_load(monkeypatch, quarterly_statements):
    import conftest

    src = EdgarSource({"identity": "Trail Test test@example.com", "tickers": ["AAA"]})
    monkeypatch.setattr(
        EdgarSource, "_fetch_statements",
        lambda self, t, n, period="annual": (conftest.FakeCompany(), quarterly_statements),
    )
    panel = src.load(
        LoadRequest(fields=frozenset({"income.revenue", "income.net_income"}), frequency="quarterly")
    ).sort("time")
    assert panel.height == 2
    # Q2 2024 -> 2024-06-30, Q3 2024 -> 2024-09-30 (calendar quarter-ends of the label year)
    assert [t.month for t in panel["time"].to_list()] == [6, 9]
    assert panel["income.revenue"].to_list() == [250.0, 260.0]


def test_identity_is_required(monkeypatch):
    monkeypatch.delenv("EDGAR_IDENTITY", raising=False)
    with pytest.raises(ConfigError, match="E-EDGAR-IDENTITY"):
        EdgarSource({"tickers": ["AAA"]})


def test_capabilities_declares_pit(edgar_source):
    assert edgar_source.capabilities().pit is True


def test_statement_fields_align_on_filing_date_meta_is_naive(edgar_source):
    for field in ("income.revenue", "balance.total_assets", "cash.cfo", "income.gross_profit"):
        info = edgar_source.describe_field(field)
        assert info is not None and info.aligns_on == "filing_date"
    for field in ("meta.sector", "meta.exchange", "meta.country", "meta.is_active"):
        info = edgar_source.describe_field(field)
        assert info is not None and info.aligns_on is None


def test_panel_carries_filing_date_coordinate(edgar_source):
    import conftest

    panel = edgar_source.load(LoadRequest(fields=frozenset({"income.revenue", "meta.sector"})))
    coord = date_col("filing_date")
    assert coord in panel.columns
    assert isinstance(panel.schema[coord], pl.Datetime)
    row = panel.filter(
        (pl.col("entity") == "AAA") & (pl.col("time").dt.year() == 2024)
    ).to_dicts()[0]
    assert row[coord] == dt.datetime.combine(conftest.FILING_DATE_FY2024, dt.time())


def test_filing_dates_takes_earliest_and_filters_form_and_statement_type():
    import conftest

    # two facts for the same annual period: an original 10-K disclosure and a later 10-K's
    # comparative re-disclosure with a later filing_date - the earliest (original) must win.
    original = conftest._FakeFact(2024, "FY", "IncomeStatement", dt.date(2025, 2, 1))
    comparative = conftest._FakeFact(2024, "FY", "IncomeStatement", dt.date(2026, 2, 1))
    non_periodic_form = conftest._FakeFact(2024, "FY", "IncomeStatement", dt.date(2025, 1, 1), form_type="8-K")
    non_statement = conftest._FakeFact(2024, "FY", "CoverPage", dt.date(2025, 1, 1))

    class _Company:
        facts = [original, comparative, non_periodic_form, non_statement]

    dates = _filing_dates(_Company())
    assert dates == {(2024, 0): dt.datetime(2025, 2, 1)}


def test_filing_dates_handles_missing_facts():
    assert _filing_dates(object()) == {}
