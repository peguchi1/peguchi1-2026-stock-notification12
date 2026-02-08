from __future__ import annotations

import pandas as pd

from src.indicators import compute_indicators
from src.triggers import breakout_20d, pullback_25_bounce, pullback_50_bounce


def _build_df(close: list[float], low: list[float], high: list[float], volume: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=len(close), freq="D"),
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def test_pullback_25_bounce() -> None:
    close = [10.0] * 30
    low = [9.9] * 30
    high = [10.1] * 30
    volume = [100.0] * 30
    df = _build_df(close, low, high, volume)
    indicators = compute_indicators(df)
    result = pullback_25_bounce(df, indicators, tol=0.005)
    assert bool(result.fired) is True


def test_pullback_50_bounce() -> None:
    close = [10.0] * 60
    low = [9.9] * 60
    high = [10.2] * 60
    volume = [100.0] * 60
    df = _build_df(close, low, high, volume)
    indicators = compute_indicators(df)
    result = pullback_50_bounce(df, indicators, tol=0.005, drawdown_20d_max=0.15)
    assert bool(result.fired) is True


def test_breakout_20d() -> None:
    close = [10.0] * 25 + [10.5]
    low = [9.8] * 26
    high = [10.0] * 25 + [10.4]
    volume = [100.0] * 25 + [200.0]
    df = _build_df(close, low, high, volume)
    indicators = compute_indicators(df)
    result = breakout_20d(df, indicators, volume_mult=1.2, dd_window=5, dd_max=0.5, symbol="TEST")
    assert bool(result.fired) is True
