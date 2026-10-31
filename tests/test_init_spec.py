"""The `trail init edgar` template: renders with the placeholder values and parses as a
valid Trail config (config-validity check only - no network)."""
from trail.config import load_config

from trail_edgar.init_spec import EDGAR_INIT


def test_template_renders_and_parses(tmp_path):
    text = EDGAR_INIT.template.format(identity="Jane J j@x.com", tickers="AAPL, MSFT",
                                      years="2020, 2024")
    cfg_file = tmp_path / "trail.yaml"
    cfg_file.write_text(text)
    cfg = load_config(str(cfg_file))
    src = cfg.sources["edgar"]
    assert src.driver == "edgar"
    assert src.options["identity"] == "Jane J j@x.com"
    assert src.options["tickers"] == ["AAPL", "MSFT"]
    assert src.options["years"] == [2020, 2024]
    assert src.options["cache_dir"] == ".edgar-cache"
    assert cfg.precedence["default"] == ["edgar"]
    assert cfg.periods == (2020, 2024)
    assert cfg.pit == "auto" and cfg.strict is False
