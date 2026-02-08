from __future__ import annotations

import math

import pandas as pd

from src.triggers import compute_dd_peak, breakout_20d
from src.indicators import compute_indicators


def _build_df(close: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=len(close), freq="B"),
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": [100.0] * len(close),
        }
    )


def test_dd_peak_constant() -> None:
    close = [100.0] * 10
    dd = compute_dd_peak(pd.Series(close), window=5)
    assert math.isclose(float(dd.iloc[-1]), 0.0, rel_tol=1e-6)


def test_dd_peak_shift_excludes_today() -> None:
    close = [100.0] * 9 + [120.0]
    dd = compute_dd_peak(pd.Series(close), window=5)
    # rolling max excludes today, so dd uses 100 as peak: 1 - 120/100 = -0.2
    assert math.isclose(float(dd.iloc[-1]), -0.2, rel_tol=1e-6)


def test_dd_peak_nan_close() -> None:
    close = [100.0, float("nan"), 100.0, 100.0, 100.0, 100.0]
    dd = compute_dd_peak(pd.Series(close), window=3)
    assert math.isnan(float(dd.iloc[1]))


def test_dd_peak_zero_max() -> None:
    close = [0.0] * 6
    dd = compute_dd_peak(pd.Series(close), window=3)
    assert math.isnan(float(dd.iloc[-1]))


def test_dd_filter_excludes_when_over_max() -> None:
    close = [100.0] * 25 + [60.0]
    df = _build_df(close)
    indicators = compute_indicators(df)
    res = breakout_20d(df, indicators, volume_mult=0.0, dd_window=5, dd_max=0.2, symbol="TEST")
    assert res.fired is False
    assert res.reason == "drawdown_too_large"


def test_dd_filter_allows_when_within_max() -> None:
    close = [100.0] * 25 + [95.0]
    df = _build_df(close)
    indicators = compute_indicators(df)
    res = breakout_20d(df, indicators, volume_mult=0.0, dd_window=5, dd_max=0.2, symbol="TEST")
    assert res.reason != "drawdown_too_large"
