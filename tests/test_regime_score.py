from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from src.market_regime import (
    _lower_exposure,
    _price_score,
    _state_from_score,
    classify_regime,
)


def _build_qqq_df(close: list[float], start: str = "2024-01-01") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range(start, periods=len(close), freq="B"),
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": [100.0] * len(close),
        }
    )


def _build_nfci_series(values: list[float], start: str = "2024-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="B").date
    return pd.Series(values, index=idx)


def test_score_bounds() -> None:
    close = [100.0] * 200 + [110.0] * 30
    qqq_df = _build_qqq_df(close)
    nfci = _build_nfci_series([0.0] * len(close))
    as_of = pd.to_datetime(qqq_df["date"].iloc[-1])
    result = classify_regime(nfci, qqq_df, as_of)
    assert 0.0 <= result.total_score <= 100.0


def test_risk_off_forces_no_entries_and_lowers_exposure() -> None:
    close = [100.0] * 220
    qqq_df = _build_qqq_df(close)
    nfci_values = [0.0 + 0.012 * i for i in range(len(close))]
    nfci = _build_nfci_series(nfci_values)
    result = classify_regime(nfci, qqq_df, datetime(2024, 10, 31))
    assert result.risk_off_trigger is True
    assert result.allow_new_entries is False
    base_state, base_exposure, _ = _state_from_score(result.total_score)
    assert result.max_exposure == _lower_exposure(base_exposure)


def test_price_score_branches() -> None:
    assert _price_score(110.0, 100.0, 90.0) == 30
    assert _price_score(110.0, 100.0, 120.0) == 15
    assert _price_score(95.0, 100.0, 90.0) == 5
    assert _price_score(80.0, 100.0, 120.0) == 0
