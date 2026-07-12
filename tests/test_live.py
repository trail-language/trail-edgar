"""Live SEC EDGAR smoke test. Skipped by default (marker 'live').

Run with: uv run pytest -m live   (needs network and a valid identity)
"""
import os

import pytest

from trail_edgar import EdgarSource


@pytest.mark.live
def test_live_apple_annual_revenue():
    identity = os.environ.get("EDGAR_IDENTITY", "Trail Test test@example.com")
    src = EdgarSource({"identity": identity, "tickers": ["AAPL"], "periods": 3})
    panel = src.load({"income.revenue", "balance.total_assets", "meta.exchange"})
    assert panel.height > 0
    latest = panel.sort("period").tail(1).to_dicts()[0]
    assert latest["income.revenue"] and latest["income.revenue"] > 0
    assert latest["balance.total_assets"] and latest["balance.total_assets"] > 0
