from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class RegimeScoreResult:
    date: str
    nfci_L: float
    s_1w: float
    s_4w: float
    price_close: float
    ma50: float
    ma200: float
    price_score: float
    level_score: float
    trend_score: float
    abs_penalty: float
    total_score: float
    risk_off_trigger: bool
    risk_on_trigger: bool
    state: str
    max_exposure: float
    allow_new_entries: bool
    notes: str


def _clip_0_1(value: float) -> float:
    return max(0.0, min(1.0, value))


def _price_score(price: float, ma50: float, ma200: float) -> int:
    if price > ma50 and ma50 > ma200:
        return 30
    if price > ma50 and ma50 <= ma200:
        return 15
    if price <= ma50 and price > ma200:
        return 5
    return 0


def _state_from_score(score: float) -> tuple[str, float, bool]:
    if score >= 80:
        return ("RISK_ON_STRONG", 1.00, True)
    if score >= 60:
        return ("RISK_ON", 0.70, True)
    if score >= 40:
        return ("NEUTRAL", 0.40, False)
    if score >= 20:
        return ("RISK_OFF", 0.15, False)
    return ("RISK_OFF_STRONG", 0.05, False)


def _lower_exposure(current: float) -> float:
    ladder = [1.00, 0.70, 0.40, 0.15, 0.05]
    if current not in ladder:
        return current
    idx = ladder.index(current)
    return ladder[min(idx + 1, len(ladder) - 1)]


def classify_regime(
    nfci_series: pd.Series,
    qqq_df: pd.DataFrame,
    as_of_date: pd.Timestamp,
) -> RegimeScoreResult:
    if qqq_df.empty:
        raise RuntimeError("QQQ data missing")

    qqq = qqq_df.copy()
    qqq["date"] = pd.to_datetime(qqq["date"]).dt.date
    qqq = qqq.sort_values("date")
    qqq.set_index("date", inplace=True)

    if as_of_date.date() not in qqq.index:
        eligible = qqq.index[qqq.index <= as_of_date.date()]
        if len(eligible) == 0:
            raise RuntimeError("No QQQ trading day on or before today")
        as_of = eligible[-1]
    else:
        as_of = as_of_date.date()

    close = qqq["close"]
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()

    nfci_daily = nfci_series.reindex(qqq.index).ffill()

    if as_of not in nfci_daily.index:
        raise RuntimeError("NFCI alignment failed")

    l = nfci_daily
    s_1w = l - l.shift(5)
    s_4w = l - l.shift(20)
    s_1w_prev = s_1w.shift(5)

    required = [l, s_1w, s_4w, s_1w_prev, ma50, ma200]
    if any(pd.isna(series.loc[as_of]) for series in required):
        raise RuntimeError("Insufficient history for regime score calculation")

    l_t = float(l.loc[as_of])
    s_1w_t = float(s_1w.loc[as_of])
    s_4w_t = float(s_4w.loc[as_of])
    s_1w_prev_t = float(s_1w_prev.loc[as_of])

    risk_off_trigger = (s_1w_t > 0.05 and s_1w_prev_t > 0.05) or (s_4w_t > 0.10)
    risk_on_trigger = (s_1w_t < -0.05 and s_1w_prev_t < -0.05) or (s_4w_t < -0.10)

    price = float(close.loc[as_of])
    ma50_t = float(ma50.loc[as_of])
    ma200_t = float(ma200.loc[as_of])
    price_score = _price_score(price, ma50_t, ma200_t)

    level_score = 35.0 * _clip_0_1((-l_t + 0.5) / 1.2)
    trend_raw = 0.6 * s_1w_t + 0.4 * (s_4w_t / 4.0)
    trend_score = 35.0 * _clip_0_1((-trend_raw + 0.03) / 0.10)
    abs_penalty = 15.0 * _clip_0_1((abs(l_t) - 0.3) / 0.7)

    total = level_score + trend_score + price_score - abs_penalty
    total_score = max(0.0, min(100.0, total))

    state, max_exposure, allow_new_entries = _state_from_score(total_score)
    notes = ""
    if risk_off_trigger:
        allow_new_entries = False
        max_exposure = _lower_exposure(max_exposure)
        notes = "risk_off_trigger: max_exposure lowered"
    elif risk_on_trigger:
        notes = "risk_on_trigger: no exposure boost"

    return RegimeScoreResult(
        date=str(as_of_date.date()),
        nfci_L=l_t,
        s_1w=s_1w_t,
        s_4w=s_4w_t,
        price_close=price,
        ma50=ma50_t,
        ma200=ma200_t,
        price_score=price_score,
        level_score=level_score,
        trend_score=trend_score,
        abs_penalty=abs_penalty,
        total_score=total_score,
        risk_off_trigger=risk_off_trigger,
        risk_on_trigger=risk_on_trigger,
        state=state,
        max_exposure=max_exposure,
        allow_new_entries=allow_new_entries,
        notes=notes,
    )


def regime_allows(regime: str, trigger_name: str, config: dict[str, Any]) -> bool:
    if regime in {"RISK_ON_STRONG", "RISK_ON"}:
        return True
    if trigger_name == "BREAKOUT_20D":
        return True
    return False
