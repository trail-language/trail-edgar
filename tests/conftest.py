"""Shared fixtures: synthetic edgartools-shaped statement frames and a wired EdgarSource.

The synthetic frames mirror the shape edgartools returns from
``income_statement/balance_sheet/cashflow_statement(as_dataframe=True)``: the us-gaap
concept on the index, a ``label`` column, and fiscal-year columns labelled ``FY 20xx``.
Monkeypatching ``EdgarSource._fetch_statements`` keeps the whole suite offline.
"""
import pandas as pd
import pytest

from trail_edgar.source import EdgarSource


def _stmt(rows: dict) -> pd.DataFrame:
    index = list(rows)
    data = {
        "label": [rows[c][0] for c in index],
        "FY 2024": [rows[c][1] for c in index],
        "FY 2023": [rows[c][2] for c in index],
    }
    return pd.DataFrame(data, index=index)


@pytest.fixture
def income_df() -> pd.DataFrame:
    return _stmt(
        {
            "Revenues": ("Total Revenue", 1000.0, 900.0),
            "CostOfRevenue": ("Cost of Revenue", 600.0, 540.0),
            "OperatingIncomeLoss": ("Operating Income", 200.0, 180.0),
            "NetIncomeLoss": ("Net Income", 120.0, 108.0),
            "InterestExpense": ("Interest Expense", 20.0, 18.0),
            "IncomeTaxExpenseBenefit": ("Income Tax", 30.0, 27.0),
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxes": ("Pretax", 150.0, 135.0),
            "EarningsPerShareDiluted": ("EPS Diluted", 5.0, 4.5),
            "WeightedAverageNumberOfDilutedSharesOutstanding": ("Diluted Shares", 24.0, 24.0),
        }
    )


@pytest.fixture
def balance_df() -> pd.DataFrame:
    return _stmt(
        {
            "Assets": ("Total Assets", 2000.0, 1800.0),
            "AssetsCurrent": ("Current Assets", 800.0, 720.0),
            "LiabilitiesCurrent": ("Current Liabilities", 500.0, 450.0),
            "Liabilities": ("Total Liabilities", 1200.0, 1080.0),
            "LongTermDebtNoncurrent": ("Long-term Debt", 600.0, 540.0),
            "LongTermDebtCurrent": ("Current Portion LT Debt", 100.0, 90.0),
            "StockholdersEquity": ("Equity", 800.0, 720.0),
            "RetainedEarningsAccumulatedDeficit": ("Retained Earnings", 400.0, 360.0),
            "AccountsReceivableNetCurrent": ("Accounts Receivable", 150.0, 135.0),
            "InventoryNet": ("Inventory", 100.0, 90.0),
            "AccountsPayableCurrent": ("Accounts Payable", 120.0, 108.0),
        }
    )


@pytest.fixture
def cashflow_df() -> pd.DataFrame:
    return _stmt(
        {
            "NetCashProvidedByUsedInOperatingActivities": ("CFO", 300.0, 270.0),
            "PaymentsToAcquirePropertyPlantAndEquipment": ("CapEx", 50.0, 45.0),
            "ProceedsFromIssuanceOfCommonStock": ("Stock Issued", 10.0, 9.0),
        }
    )


@pytest.fixture
def statements(income_df, balance_df, cashflow_df):
    return [income_df, balance_df, cashflow_df]


class _FakeAddress:
    state_or_country = "CA"  # a US state code -> should normalize to USA, not California-as-country


class FakeCompany:
    sic_description = "Technology"
    business_address = _FakeAddress()

    def get_exchanges(self):
        return ["NASDAQ"]


@pytest.fixture
def edgar_source(monkeypatch, statements):
    src = EdgarSource({"identity": "Trail Test test@example.com", "tickers": ["AAA", "BBB"]})
    monkeypatch.setattr(
        EdgarSource,
        "_fetch_statements",
        lambda self, ticker, n: (FakeCompany(), statements),
    )
    return src
