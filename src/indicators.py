from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class Indicators:
    sma25: pd.Series
    sma50: pd.Series
    sma200: pd.Series
    vol_ma20: pd.Series
    high_20d: pd.Series
    high_52w: pd.Series
    drawdown_20d: pd.Series


def compute_indicators(df: pd.DataFrame) -> Indicators:
    close = df["close"]
    high = df["high"]
    volume = df["volume"]

    sma25 = close.rolling(25).mean()
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    vol_ma20 = volume.rolling(20).mean()
    high_20d = high.rolling(20).max().shift(1)
    high_52w = high.rolling(252).max()
    high_20d_max = high.rolling(20).max()
    drawdown_20d = (high_20d_max - close) / high_20d_max

    return Indicators(
        sma25=sma25,
        sma50=sma50,
        sma200=sma200,
        vol_ma20=vol_ma20,
        high_20d=high_20d,
        high_52w=high_52w,
        drawdown_20d=drawdown_20d,
    )
