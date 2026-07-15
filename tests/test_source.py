import polars as pl
import pytest

from trail.config import ConfigError
from trail.testing import assert_source_conforms

from trail_edgar.source import EdgarSource


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
        {
            "income.revenue", "income.gross_profit", "cash.free_cash_flow",
            "balance.total_debt", "cash.capex", "meta.sector",
        }
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


def test_capabilities(edgar_source):
    caps = edgar_source.capabilities()
    assert caps.frequency == "annual" and caps.forms == ("10-K",)


def test_period_bounds_filter(monkeypatch, statements):
    src = EdgarSource(
        {"identity": "Trail Test test@example.com", "tickers": ["AAA"], "years": [2024, 2024]}
    )
    monkeypatch.setattr(
        EdgarSource, "_fetch_statements", lambda self, t, n: (object(), statements)
    )
    panel = src.load({"income.revenue"})
    assert panel["time"].dt.year().unique().to_list() == [2024]


def test_identity_is_required(monkeypatch):
    monkeypatch.delenv("EDGAR_IDENTITY", raising=False)
    with pytest.raises(ConfigError, match="E-EDGAR-IDENTITY"):
        EdgarSource({"tickers": ["AAA"]})
