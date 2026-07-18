"""Shared fixtures: synthetic edgartools-shaped statement frames and a wired EdgarSource.

The synthetic frames mirror the shape edgartools returns from
``income_statement/balance_sheet/cashflow_statement(as_dataframe=True)``: the us-gaap
concept on the index, a ``label`` column, and fiscal-year columns labelled ``FY 20xx``.
Monkeypatching ``EdgarSource._fetch_statements`` keeps the whole suite offline.
"""
import datetime as dt

import pandas as pd
import pytest

from trail_edgar.source import EdgarSource

# filing dates for the synthetic FY2024/FY2023 and Q3/Q2 2024 periods below - distinct from
# any period-end so PIT tests can tell "filing date" apart from "naive period-end" placement.
FILING_DATE_FY2024 = dt.date(2025, 2, 3)
FILING_DATE_FY2023 = dt.date(2024, 2, 5)
FILING_DATE_Q3_2024 = dt.date(2024, 10, 30)
FILING_DATE_Q2_2024 = dt.date(2024, 7, 31)


class _FakeFact:
    """Minimal stand-in for ``edgar.entity.models.FinancialFact`` - only the attributes
    ``trail_edgar.source._filing_dates`` reads."""

    def __init__(self, fiscal_year, fiscal_period, statement_type, filing_date, form_type="10-K"):
        self.fiscal_year = fiscal_year
        self.fiscal_period = fiscal_period
        self.statement_type = statement_type
        self.filing_date = filing_date
        self.form_type = form_type


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
            "DepreciationDepletionAndAmortization": ("D&A", 40.0, 36.0),
            "SellingGeneralAndAdministrativeExpense": ("SG&A", 100.0, 90.0),
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
            "PropertyPlantAndEquipmentNet": ("Net PP&E", 900.0, 850.0),
            "CashAndCashEquivalentsAtCarryingValue": ("Cash", 250.0, 220.0),
            "Goodwill": ("Goodwill", 400.0, 400.0),
            "MinorityInterest": ("Minority Interest", 40.0, 38.0),
            "CommonStockValue": ("Common Stock", 100.0, 100.0),
        }
    )


@pytest.fixture
def cashflow_df() -> pd.DataFrame:
    return _stmt(
        {
            "NetCashProvidedByUsedInOperatingActivities": ("CFO", 300.0, 270.0),
            "PaymentsToAcquirePropertyPlantAndEquipment": ("CapEx", 50.0, 45.0),
            "ProceedsFromIssuanceOfCommonStock": ("Stock Issued", 10.0, 9.0),
            "NetCashProvidedByUsedInInvestingActivities": ("CFI", -120.0, -100.0),
            "NetCashProvidedByUsedInFinancingActivities": ("CFF", -80.0, -70.0),
            "CashAndCashEquivalentsPeriodIncreaseDecrease": ("Net Change", 100.0, 100.0),
            "PaymentsOfDividends": ("Dividends Paid", -60.0, -55.0),
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
    # stand-in for the cached_property `edgar.Company.facts` - annual and quarterly statement
    # facts for the periods the fixtures below cover, so `_filing_dates` has something to read
    # without a network call.
    facts = [
        _FakeFact(2024, "FY", "IncomeStatement", FILING_DATE_FY2024),
        _FakeFact(2024, "FY", "BalanceSheet", FILING_DATE_FY2024),
        _FakeFact(2024, "FY", "CashFlowStatement", FILING_DATE_FY2024),
        _FakeFact(2023, "FY", "IncomeStatement", FILING_DATE_FY2023),
        _FakeFact(2023, "FY", "BalanceSheet", FILING_DATE_FY2023),
        _FakeFact(2023, "FY", "CashFlowStatement", FILING_DATE_FY2023),
        _FakeFact(2024, "Q3", "IncomeStatement", FILING_DATE_Q3_2024, form_type="10-Q"),
        _FakeFact(2024, "Q3", "BalanceSheet", FILING_DATE_Q3_2024, form_type="10-Q"),
        _FakeFact(2024, "Q3", "CashFlowStatement", FILING_DATE_Q3_2024, form_type="10-Q"),
        _FakeFact(2024, "Q2", "IncomeStatement", FILING_DATE_Q2_2024, form_type="10-Q"),
        _FakeFact(2024, "Q2", "BalanceSheet", FILING_DATE_Q2_2024, form_type="10-Q"),
        _FakeFact(2024, "Q2", "CashFlowStatement", FILING_DATE_Q2_2024, form_type="10-Q"),
    ]

    def get_exchanges(self):
        return ["NASDAQ"]


@pytest.fixture
def edgar_source(monkeypatch, statements):
    src = EdgarSource({"identity": "Trail Test test@example.com", "tickers": ["AAA", "BBB"]})
    monkeypatch.setattr(
        EdgarSource,
        "_fetch_statements",
        lambda self, ticker, n, period="annual": (FakeCompany(), statements),
    )
    return src


def _qstmt(rows: dict) -> pd.DataFrame:
    """Quarterly-shaped frame: edgartools labels fiscal quarters like ``Q3 2024``."""
    index = list(rows)
    data = {
        "label": [rows[c][0] for c in index],
        "Q3 2024": [rows[c][1] for c in index],
        "Q2 2024": [rows[c][2] for c in index],
    }
    return pd.DataFrame(data, index=index)


@pytest.fixture
def quarterly_statements():
    income = _qstmt({
        "Revenues": ("Total Revenue", 260.0, 250.0),
        "NetIncomeLoss": ("Net Income", 31.0, 30.0),
    })
    balance = _qstmt({"Assets": ("Total Assets", 1950.0, 1900.0)})
    cash = _qstmt({"NetCashProvidedByUsedInOperatingActivities": ("CFO", 80.0, 75.0)})
    return [income, balance, cash]
