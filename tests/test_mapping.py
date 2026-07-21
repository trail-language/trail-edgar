from trail.schema import SCHEMA

from trail_edgar import mapping
from trail_edgar.schema_fields import SCHEMA as EDGAR_SCHEMA


def test_declared_edgar_namespace_matches_provided_domain_fields():
    """Approach X: the source owns its vocabulary. What edgar DECLARES under `edgar.*` must be exactly
    the domain fields it provides - `meta.*` stays language-owned (shared), price is unavailable."""
    assert set(EDGAR_SCHEMA) == {
        mapping.external(f) for f in mapping.PROVIDED_FIELDS - mapping.META_FIELDS
    }


def test_shared_meta_fields_are_language_owned():
    """The `meta.*` fields edgar serves come from the language's shared coordination vocabulary
    (the only namespace trail-lang still ships), not from edgar's own declaration."""
    assert mapping.META_FIELDS <= set(SCHEMA)
    assert not any(f.startswith("meta.") for f in EDGAR_SCHEMA)


def test_direct_tag_priority():
    concepts = {"Revenues": {2024: 100.0}, "NetSales": {2024: 999.0}}
    assert mapping.resolve_field("income.revenue", concepts) == {2024: 100.0}


def test_capex_is_absolute():
    assert mapping.resolve_field(
        "cash.capex", {"PaymentsToAcquirePropertyPlantAndEquipment": {2024: 50.0}}
    ) == {2024: 50.0}
    assert mapping.resolve_field(
        "cash.capex", {"PaymentsToAcquirePropertyPlantAndEquipment": {2024: -50.0}}
    ) == {2024: 50.0}


def test_gross_profit_falls_back_to_revenue_minus_cogs():
    concepts = {"Revenues": {2024: 100.0}, "CostOfRevenue": {2024: 60.0}}
    assert mapping.resolve_field("income.gross_profit", concepts) == {2024: 40.0}


def test_gross_profit_prefers_filed_tag():
    concepts = {"GrossProfit": {2024: 42.0}, "Revenues": {2024: 100.0}, "CostOfRevenue": {2024: 60.0}}
    assert mapping.resolve_field("income.gross_profit", concepts) == {2024: 42.0}


def test_free_cash_flow_is_cfo_minus_abs_capex():
    concepts = {
        "NetCashProvidedByUsedInOperatingActivities": {2024: 300.0},
        "PaymentsToAcquirePropertyPlantAndEquipment": {2024: -50.0},
    }
    assert mapping.resolve_field("cash.free_cash_flow", concepts) == {2024: 250.0}


def test_total_debt_sums_long_and_short_term():
    concepts = {"LongTermDebtNoncurrent": {2024: 600.0}, "LongTermDebtCurrent": {2024: 100.0}}
    assert mapping.resolve_field("balance.total_debt", concepts) == {2024: 700.0}


def test_raw_tag_resolution():
    concepts = {"ProceedsFromIssuanceOfCommonStock": {2024: 10.0}}
    assert mapping.resolve_field("cash.stock_issued", concepts) == {2024: 10.0}


def test_unresolved_returns_empty():
    assert mapping.resolve_field("income.revenue", {}) == {}


def test_strategy_of():
    assert mapping.strategy_of("income.revenue") == "direct"
    assert mapping.strategy_of("cash.stock_issued") == "raw"
    assert mapping.strategy_of("income.gross_profit") == "derived"
    assert mapping.strategy_of("meta.sector") == "meta"
    assert mapping.strategy_of("price.adj_close") == "unavailable"
