import polars as pl

from trail_edgar import convert


def test_fiscal_year_parsing():
    assert convert.fiscal_year("FY 2024") == 2024
    assert convert.fiscal_year("FY2019") == 2019
    assert convert.fiscal_year("label") is None


def test_concepts_from_statements(income_df):
    concepts = convert.concepts_from_statements([income_df])
    assert concepts["Revenues"] == {2024: 1000.0, 2023: 900.0}
    assert "label" not in concepts  # the label column is not a concept


def test_to_panel_shape_and_dtypes(statements):
    per_security = [("AAA", convert.concepts_from_statements(statements), {"meta.sector": "Tech"})]
    fields = {"income.revenue", "income.gross_profit", "meta.sector"}
    panel = convert.to_panel(per_security, fields)
    assert set(panel.columns) == {"security", "period", "income.revenue", "income.gross_profit", "meta.sector"}
    assert panel.schema["period"] == pl.Int32
    assert panel.schema["income.revenue"] == pl.Float64
    assert panel.schema["meta.sector"] == pl.Utf8
    assert panel.height == 2  # FY2024 and FY2023


def test_to_panel_empty_is_still_typed():
    panel = convert.to_panel([], {"income.revenue"})
    assert panel.height == 0
    assert panel.schema["income.revenue"] == pl.Float64
    assert {"security", "period"} <= set(panel.columns)


def test_to_panel_ignores_unavailable_fields(statements):
    per_security = [("AAA", convert.concepts_from_statements(statements), {})]
    panel = convert.to_panel(per_security, {"income.revenue", "price.adj_close"})
    assert "price.adj_close" not in panel.columns
