"""Canonical Trail field <- SEC us-gaap concept resolution.

Each Trail field is resolved from a company's XBRL facts by one of three strategies:

- direct: the first us-gaap tag present in a priority list wins.
- derived: computed from other resolved fields (gross_profit, free_cash_flow, total_debt).
- raw: a single-purpose tag with no standardized synonym group.

The input `concepts` is a mapping ``{us_gaap_tag: {fiscal_year: value}}`` built by
:mod:`trail_edgar.convert` from edgartools statement frames; resolution returns
``{fiscal_year: value}`` per field. Tag priority lists follow edgartools' own synonym
registry, verified against live filings.
"""
from __future__ import annotations

# canonical field -> ordered us-gaap tags (first present wins)
DIRECT_TAGS: dict[str, list[str]] = {
    "income.revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "Revenues", "Revenue", "SalesRevenueNet", "SalesRevenueGoodsNet",
        "TotalRevenues", "NetSales", "OperatingRevenue",
    ],
    "income.cogs": [
        "CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold", "CostOfSales",
    ],
    "income.operating_income": [
        "OperatingIncomeLoss", "OperatingIncome",
        "IncomeLossFromContinuingOperationsBeforeInterestAndTaxes",
        "ProfitLossFromOperatingActivities",
    ],
    "income.net_income": [
        "NetIncomeLoss", "ProfitLoss", "NetIncome", "NetEarnings",
        "NetIncomeLossAttributableToParent", "IncomeLossFromContinuingOperations",
        "ProfitLossAttributableToOwnersOfParent",
    ],
    "income.interest_expense": [
        "InterestExpense", "InterestAndDebtExpense", "InterestIncomeExpenseNet",
        "InterestExpenseOperating", "InterestExpenseNonoperating",
    ],
    "income.income_tax_expense": [
        "IncomeTaxExpenseBenefit", "IncomeTaxesPaidNet",
        "IncomeTaxExpenseContinuingOperations",
    ],
    "income.income_before_tax": [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxes",
        "IncomeLossBeforeIncomeTaxes", "ProfitLossBeforeTax",
    ],
    "income.eps_diluted": ["EarningsPerShareDiluted", "DilutedEarningsLossPerShare"],
    "balance.total_assets": ["Assets", "AssetsTotal"],
    "balance.current_assets": ["AssetsCurrent"],
    "balance.other_current_assets": ["OtherAssetsCurrent"],
    "balance.current_liabilities": ["LiabilitiesCurrent"],
    "balance.total_liabilities": ["Liabilities", "LiabilitiesTotal"],
    "balance.long_term_debt": [
        "LongTermDebtNoncurrent", "LongTermDebt", "LongTermDebtAndCapitalLeaseObligations",
        "LongTermBorrowings", "LongTermNotesAndLoans",
    ],
    "balance.total_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "StockholdersEquityAttributableToParent", "EquityAttributableToParent",
        "ShareholdersEquity", "TotalEquity", "PartnersCapital", "MembersEquity",
        "EquityAttributableToOwnersOfParent",
    ],
    "balance.retained_earnings": ["RetainedEarningsAccumulatedDeficit", "RetainedEarnings"],
    "balance.accounts_receivable": [
        "AccountsReceivableNetCurrent", "AccountsReceivableNet",
        "ReceivablesNetCurrent", "AccountsReceivableGross",
    ],
    "balance.inventory": ["InventoryNet", "InventoryGross", "InventoryFinishedGoods"],
    "balance.accounts_payable": [
        "AccountsPayableCurrent", "AccountsPayableTradeCurrent", "AccountsPayable",
    ],
    "cash.cfo": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "cash.capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment", "CapitalExpenditures",
        "PurchaseOfPropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets",
    ],
    "income.depreciation_amortization": [
        "DepreciationDepletionAndAmortization", "DepreciationAndAmortization",
        "DepreciationAmortizationAndAccretionNet", "Depreciation",
    ],
    "income.sga": [
        "SellingGeneralAndAdministrativeExpense", "GeneralAndAdministrativeExpense",
    ],
    "balance.net_fixed_assets": ["PropertyPlantAndEquipmentNet"],
    "balance.cash_and_equivalents": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "balance.cash_and_short_term_investments": ["CashCashEquivalentsAndShortTermInvestments"],
    "balance.minority_interest": ["MinorityInterest"],
    "balance.common_stock": ["CommonStockValue", "CommonStocksIncludingAdditionalPaidInCapital"],
    "balance.goodwill": ["Goodwill"],
    "cash.cfi": [
        "NetCashProvidedByUsedInInvestingActivities",
        "NetCashProvidedByUsedInInvestingActivitiesContinuingOperations",
    ],
    "cash.cff": [
        "NetCashProvidedByUsedInFinancingActivities",
        "NetCashProvidedByUsedInFinancingActivitiesContinuingOperations",
    ],
    "cash.net_change_in_cash": [
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
        "CashAndCashEquivalentsPeriodIncreaseDecrease",
    ],
    "cash.dividends_paid": [
        "PaymentsOfDividends", "PaymentsOfDividendsCommonStock",
    ],
}

# fields reported as a positive cash-outflow magnitude, normalized with abs()
ABS_FIELDS = {"cash.capex", "cash.dividends_paid"}

# single-purpose tags with no standardized synonym group
RAW_TAGS: dict[str, list[str]] = {
    "income.weighted_average_shares_diluted": [
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        "WeightedAverageNumberOfSharesOutstandingDiluted",
    ],
    "income.weighted_average_shares": [
        "WeightedAverageNumberOfSharesOutstandingBasic",
        "WeightedAverageNumberOfSharesOutstanding",
    ],
    "cash.stock_issued": ["ProceedsFromIssuanceOfCommonStock"],
}

# components summed into balance.total_debt alongside long_term_debt
SHORT_TERM_DEBT_TAGS = [
    "DebtCurrent", "ShortTermBorrowings", "LongTermDebtCurrent", "NotesPayableCurrent",
]

DERIVED_FIELDS = {"income.gross_profit", "cash.free_cash_flow", "balance.total_debt",
                  "income.ebitda"}

# per-entity constants, resolved outside the concept series (in EdgarSource)
META_FIELDS = {"meta.sector", "meta.exchange", "meta.is_active", "meta.country"}

# SEC filings do not carry market data, so these are declared unavailable.
UNAVAILABLE_FIELDS = {"price.adj_close", "price.dividends", "meta.market_cap"}

# every canonical field this source can supply
PROVIDED_FIELDS = set(DIRECT_TAGS) | set(RAW_TAGS) | DERIVED_FIELDS | META_FIELDS

Period = tuple[int, int]  # (year, quarter); quarter 0 = full fiscal year
Series = dict[Period, float]
Concepts = dict[str, dict[Period, float]]


def strategy_of(field: str) -> str:
    if field in DIRECT_TAGS or field in RAW_TAGS:
        return "direct" if field in DIRECT_TAGS else "raw"
    if field in DERIVED_FIELDS:
        return "derived"
    if field in META_FIELDS:
        return "meta"
    if field in UNAVAILABLE_FIELDS:
        return "unavailable"
    return "unknown"


def _series_for_tags(concepts: Concepts, tags: list[str]) -> Series | None:
    for tag in tags:
        series = concepts.get(tag)
        if series:
            return dict(series)
    return None


def _sum_series(serieses: list[Series | None]) -> Series:
    out: Series = {}
    for s in serieses:
        if not s:
            continue
        for year, value in s.items():
            if value is None:
                continue
            out[year] = out.get(year, 0.0) + value
    return out


def resolve_field(field: str, concepts: Concepts) -> Series:
    """Return ``{fiscal_year: value}`` for a non-meta field, or ``{}`` if unresolved."""
    if field in DIRECT_TAGS:
        series = _series_for_tags(concepts, DIRECT_TAGS[field])
        if series is None:
            return {}
        if field in ABS_FIELDS:
            return {y: abs(v) for y, v in series.items() if v is not None}
        return series
    if field in RAW_TAGS:
        return _series_for_tags(concepts, RAW_TAGS[field]) or {}
    if field == "income.gross_profit":
        filed = _series_for_tags(concepts, ["GrossProfit"])
        if filed is not None:
            return filed
        rev = resolve_field("income.revenue", concepts)
        cogs = resolve_field("income.cogs", concepts)
        return {y: rev[y] - cogs[y] for y in rev.keys() & cogs.keys()}
    if field == "cash.free_cash_flow":
        cfo = resolve_field("cash.cfo", concepts)
        capex = resolve_field("cash.capex", concepts)  # already abs
        return {y: cfo[y] - capex[y] for y in cfo.keys() & capex.keys()}
    if field == "income.ebitda":  # not a us-gaap tag: derive from operating income + d&a
        oi = resolve_field("income.operating_income", concepts)
        da = resolve_field("income.depreciation_amortization", concepts)
        return {y: oi[y] + da[y] for y in oi.keys() & da.keys()}
    if field == "balance.total_debt":
        ltd = resolve_field("balance.long_term_debt", concepts)
        std = _sum_series([_series_for_tags(concepts, [t]) for t in SHORT_TERM_DEBT_TAGS])
        years = set(ltd) | set(std)
        return {y: ltd.get(y, 0.0) + std.get(y, 0.0) for y in years}
    return {}


# --- source namespace (Approach X) --------------------------------------------------------------
# Domain data (income/balance/cash) is owned by the `edgar` namespace; `meta.*` stays shared because
# it carries the cross-source bridge key `meta.country`. The XBRL resolution above keeps the internal
# canonical names; these translate only at the source boundary (available_fields / load / describe).
NS = "edgar"


def external(field: str) -> str:
    """Boundary name: `income.revenue` -> `edgar.revenue`; `meta.*` unchanged (shared coordination)."""
    if field.startswith("meta."):
        return field
    return f"{NS}.{field.split('.', 1)[1]}"


_EXT_TO_INT: dict[str, str] = {external(f): f for f in PROVIDED_FIELDS}


def to_internal(field: str) -> str | None:
    """Internal canonical name for an external field, or None if this source does not provide it."""
    return _EXT_TO_INT.get(field)


def kind_of(field: str) -> str:
    """Kind for a provided (internal) field. Under Approach X the source declares its own kinds -
    the language ships no vocabulary. income->flow (eps per_share, share-counts stock); balance->stock;
    cash->flow."""
    domain, leaf = field.split(".", 1)
    if domain == "balance":
        return "stock"
    if domain == "cash":
        return "flow"
    if domain == "income":
        if leaf == "eps_diluted":
            return "per_share"
        if leaf.startswith("weighted_average_shares"):
            return "stock"
        return "flow"
    return "meta"
