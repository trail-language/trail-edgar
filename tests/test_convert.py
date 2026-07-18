import datetime as dt

import polars as pl

from trail_edgar import convert


def test_fiscal_year_parsing():
    assert convert.fiscal_year("FY 2024") == 2024
    assert convert.fiscal_year("FY2019") == 2019
    assert convert.fiscal_year("label") is None


def test_concepts_from_statements(income_df):
    concepts = convert.concepts_from_statements([income_df])
    assert concepts["Revenues"] == {(2024, 0): 1000.0, (2023, 0): 900.0}  # (year, quarter=0=FY)
    assert "label" not in concepts  # the label column is not a concept


def test_to_panel_shape_and_dtypes(statements):
    filing_dates = {(2024, 0): dt.datetime(2025, 2, 1), (2023, 0): dt.datetime(2024, 2, 1)}
    per_entity = [
        ("AAA", convert.concepts_from_statements(statements), {"meta.sector": "Tech"}, filing_dates)
    ]
    fields = {"income.revenue", "income.gross_profit", "meta.sector"}
    panel = convert.to_panel(per_entity, fields)
    assert set(panel.columns) == {
        "entity", "time", "income.revenue", "income.gross_profit", "meta.sector",
        convert.FILING_DATE_COL,
    }
    assert isinstance(panel.schema["time"], pl.Datetime)
    assert panel.schema["income.revenue"] == pl.Float64
    assert panel.schema["meta.sector"] == pl.Utf8
    assert isinstance(panel.schema[convert.FILING_DATE_COL], pl.Datetime)
    assert panel.height == 2  # FY2024 and FY2023
    row = panel.filter(pl.col("time").dt.year() == 2024).to_dicts()[0]
    assert row[convert.FILING_DATE_COL] == dt.datetime(2025, 2, 1)


def test_to_panel_empty_is_still_typed():
    panel = convert.to_panel([], {"income.revenue"})
    assert panel.height == 0
    assert panel.schema["income.revenue"] == pl.Float64
    assert {"entity", "time"} <= set(panel.columns)


def test_to_panel_ignores_unavailable_fields(statements):
    per_entity = [("AAA", convert.concepts_from_statements(statements), {}, {})]
    panel = convert.to_panel(per_entity, {"income.revenue", "price.adj_close"})
    assert "price.adj_close" not in panel.columns


def test_to_panel_meta_only_has_no_filing_date_column(statements):
    per_entity = [("AAA", convert.concepts_from_statements(statements), {"meta.sector": "Tech"}, {})]
    panel = convert.to_panel(per_entity, {"meta.sector"})
    assert convert.FILING_DATE_COL not in panel.columns
