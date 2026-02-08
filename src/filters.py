from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .indicators import Indicators


@dataclass
class EligibilityResult:
    eligible: bool
    reasons: list[str]


def check_eligibility(
    df: pd.DataFrame,
    indicators: Indicators,
    drawdown_max: float,
    high_52w_max_multiple: float,
    sma50_tolerance: float,
) -> EligibilityResult:
    if df.empty:
        return EligibilityResult(False, ["no_data"])
    latest = df.iloc[-1]
    idx = df.index[-1]
    reasons: list[str] = []

    close = latest["close"]
    sma50 = indicators.sma50.loc[idx]
    sma200 = indicators.sma200.loc[idx]
    high_52w = indicators.high_52w.loc[idx]
    drawdown_20d = indicators.drawdown_20d.loc[idx]

    if pd.isna(sma50) or pd.isna(sma200) or pd.isna(high_52w):
        return EligibilityResult(False, ["insufficient_history"])

    if close < sma50 * (1 - sma50_tolerance):
        reasons.append("close_below_sma50")
    if sma50 < sma200 * 0.98:
        reasons.append("sma50_below_sma200")
    if close > high_52w * high_52w_max_multiple:
        reasons.append("too_extended_52w")
    if drawdown_20d > drawdown_max:
        reasons.append("drawdown_too_large")

    return EligibilityResult(len(reasons) == 0, reasons)
