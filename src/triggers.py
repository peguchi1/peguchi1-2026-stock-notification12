from __future__ import annotations

from dataclasses import dataclass
import logging

import pandas as pd

from .indicators import Indicators


@dataclass
class TriggerResult:
    fired: bool
    reason: str


def pullback_25_bounce(df: pd.DataFrame, indicators: Indicators, tol: float) -> TriggerResult:
    if df.empty:
        return TriggerResult(False, "no_data")
    latest = df.iloc[-1]
    idx = df.index[-1]
    sma25 = indicators.sma25.loc[idx]
    vol_ma20 = indicators.vol_ma20.loc[idx]
    if pd.isna(sma25) or pd.isna(vol_ma20):
        return TriggerResult(False, "insufficient_history")
    cond = (
        latest["low"] <= sma25 * (1 + tol)
        and latest["close"] >= sma25
        and latest["volume"] <= vol_ma20
    )
    return TriggerResult(cond, "PULLBACK_25_BOUNCE")


def pullback_50_bounce(
    df: pd.DataFrame,
    indicators: Indicators,
    tol: float,
    drawdown_20d_max: float,
) -> TriggerResult:
    if df.empty:
        return TriggerResult(False, "no_data")
    latest = df.iloc[-1]
    idx = df.index[-1]
    sma50 = indicators.sma50.loc[idx]
    drawdown_20d = indicators.drawdown_20d.loc[idx]
    if pd.isna(sma50) or pd.isna(drawdown_20d):
        return TriggerResult(False, "insufficient_history")
    cond = (
        latest["low"] <= sma50 * (1 + tol)
        and latest["close"] >= sma50
        and drawdown_20d <= drawdown_20d_max
    )
    return TriggerResult(cond, "PULLBACK_50_BOUNCE")


def breakout_20d(
    df: pd.DataFrame,
    indicators: Indicators,
    volume_mult: float,
    dd_window: int,
    dd_max: float,
    symbol: str,
) -> TriggerResult:
    if df.empty:
        return TriggerResult(False, "no_data")
    latest = df.iloc[-1]
    idx = df.index[-1]
    high_20d = indicators.high_20d.loc[idx]
    vol_ma20 = indicators.vol_ma20.loc[idx]
    dd_value = compute_dd_peak(df["close"], dd_window).loc[idx]
    logging.info(
        "DD_METRIC symbol=%s dd_metric=peak_N dd_window=%s dd_value=%s",
        symbol,
        dd_window,
        "nan" if pd.isna(dd_value) else f"{float(dd_value):.6f}",
    )
    if pd.isna(high_20d) or pd.isna(vol_ma20):
        return TriggerResult(False, "insufficient_history")
    if not pd.isna(dd_value) and dd_value > dd_max:
        logging.info(
            "EXCLUDE symbol=%s exclude_reason_rule_id=FILTER_DD_002 dd_metric=peak_N dd_window=%s dd_value=%.6f dd_max=%.6f",
            symbol,
            dd_window,
            float(dd_value),
            dd_max,
        )
        return TriggerResult(False, "drawdown_too_large")
    cond = (
        latest["close"] > high_20d
        and latest["close"] <= high_20d * 1.05
        and latest["volume"] >= vol_ma20 * volume_mult
    )
    return TriggerResult(cond, "BREAKOUT_20D")


def compute_dd_peak(close: pd.Series, window: int) -> pd.Series:
    rolling_max = close.rolling(window).max().shift(1)
    dd = pd.Series(index=close.index, dtype="float64")
    dd[:] = pd.NA
    valid = (~close.isna()) & (~rolling_max.isna()) & (rolling_max != 0)
    dd.loc[valid] = 1 - (close.loc[valid] / rolling_max.loc[valid])
    return dd
