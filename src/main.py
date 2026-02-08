from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from .cache import FileCache
from .config import AppConfig
from .data_provider import DataProviderConfig, MarketDataFetcher
from .filters import check_eligibility
from .indicators import compute_indicators
from .market_regime import classify_regime, regime_allows
from .nfci import NfciFetcher
from .notifications import Notifier
from .rules import RulesConfig
from .sheets_logger import append_regime_log
from .triggers import breakout_20d, pullback_25_bounce, pullback_50_bounce


@dataclass
class Signal:
    symbol: str
    trigger: str
    close: float
    date: str


def build_data_config(config: AppConfig) -> DataProviderConfig:
    return DataProviderConfig(
        provider_primary=config.require("data.provider_primary"),
        provider_fallback=config.require("data.provider_fallback"),
        twelvedata=config.require("data.twelvedata"),
        alphavantage=config.require("data.alphavantage"),
        cache_enabled=bool(config.require("data.cache.enabled")),
        cache_ttl_seconds=int(config.require("data.cache.ttl_seconds")),
        retry_max_attempts=int(config.require("data.retry.max_attempts")),
        retry_base_delay_seconds=float(config.require("data.retry.base_delay_seconds")),
        retry_max_delay_seconds=float(config.require("data.retry.max_delay_seconds")),
        rate_limit_enabled=bool(config.get("data.rate_limit.enabled", True)),
        rate_limit_min_interval_seconds=float(config.get("data.rate_limit.min_interval_seconds", 8.0)),
    )


def evaluate_symbol(
    symbol: str,
    df: pd.DataFrame,
    config: AppConfig,
    dd_window: int,
    dd_max: float,
) -> tuple[list[Signal], list[str]]:
    indicators = compute_indicators(df)
    eligibility = check_eligibility(
        df,
        indicators,
        drawdown_max=float(config.require("filters.drawdown_20d_max")),
        high_52w_max_multiple=float(config.require("filters.high_52w_max_multiple")),
        sma50_tolerance=float(config.get("filters.sma50_tolerance", 0.0)),
    )
    if not eligibility.eligible:
        return [], eligibility.reasons

    tol = float(config.require("filters.tolerance"))
    results = []
    if bool(config.require("triggers.pullback_25.enabled")):
        res = pullback_25_bounce(df, indicators, tol)
        if res.fired:
            results.append(res)
    if bool(config.require("triggers.pullback_50.enabled")):
        res = pullback_50_bounce(
            df,
            indicators,
            tol,
            drawdown_20d_max=float(config.require("filters.drawdown_20d_max")),
        )
        if res.fired:
            results.append(res)
    if bool(config.require("triggers.breakout_20d.enabled")):
        res = breakout_20d(
            df,
            indicators,
            volume_mult=float(config.require("triggers.breakout_volume_mult")),
            dd_window=dd_window,
            dd_max=dd_max,
            symbol=symbol,
        )
        if res.fired:
            results.append(res)

    signals: list[Signal] = []
    latest = df.iloc[-1]
    date = str(latest["date"].date())
    for res in results:
        signals.append(Signal(symbol=symbol, trigger=res.reason, close=float(latest["close"]), date=date))
    return signals, []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    load_dotenv()
    config = AppConfig.load(args.config)
    rules = RulesConfig.load("rules.yaml")
    dd_rule = rules.get_rule("FILTER_DD_002")
    dd_params = dd_rule.get("params", {})
    dd_window = int(dd_params.get("window_days", 90))
    dd_max = float(dd_params.get("dd_max", 0.25))
    logging.basicConfig(level=getattr(logging, str(config.get("app.log_level", "INFO")).upper()))
    data_config = build_data_config(config)

    cache = None
    if bool(config.require("data.cache.enabled")):
        cache = FileCache(Path(".cache"), int(config.require("data.cache.ttl_seconds")))

    fetcher = MarketDataFetcher(data_config, cache=cache)

    nfci_fetcher = NfciFetcher(config.require("nfci.csv_url"))
    nfci_series = nfci_fetcher.fetch_series()

    qqq_df = fetcher.fetch_daily("QQQ")

    tz_name = str(config.get("app.timezone", "UTC"))
    today_local = datetime.now(ZoneInfo(tz_name))
    try:
        regime_result = classify_regime(nfci_series, qqq_df, today_local)
    except Exception as exc:
        logging.error("Regime calculation failed: %s", exc)
        notifier = Notifier(
            slack_enabled=bool(config.require("notifications.slack_enabled")),
            pushover_enabled=bool(config.require("notifications.pushover_enabled")),
            email_enabled=bool(config.get("notifications.email_enabled", True)),
        )
        notifier.notify_batch(
            f"Stock Alerts {datetime.now(timezone.utc).strftime('%Y-%m-%d')} UTC | Regime ERROR",
            [f"Regime calculation failed: {exc}"],
        )
        return 0

    symbols = config.require("symbols")
    all_signals: list[Signal] = []
    eligible_symbols: list[str] = []
    rejected_reasons = Counter()
    skipped: list[str] = []
    for symbol in symbols:
        try:
            df = fetcher.fetch_daily(symbol)
            signals, reasons = evaluate_symbol(symbol, df, config, dd_window=dd_window, dd_max=dd_max)
            if reasons:
                rejected_reasons.update(reasons)
            else:
                eligible_symbols.append(symbol)
            for signal in signals:
                if regime_allows(regime_result.state, signal.trigger, config.raw):
                    all_signals.append(signal)
        except Exception as exc:
            logging.warning("SKIP %s: %s", symbol, exc)
            skipped.append(symbol)

    notifier = Notifier(
        slack_enabled=bool(config.require("notifications.slack_enabled")),
        pushover_enabled=bool(config.require("notifications.pushover_enabled")),
        email_enabled=bool(config.get("notifications.email_enabled", True)),
    )

    def _config_summary(cfg: AppConfig) -> list[str]:
        lines = [
            "条件: eligible_symbols=フィルタ通過銘柄一覧, triggered_symbols=実際にシグナルが出た銘柄一覧",
            f"Filter: close>=SMA50*(1-{float(cfg.get('filters.sma50_tolerance', 0.0)):.2f})",
            f"Filter: SMA50>=SMA200*0.98",
            f"Filter: dd_peak_N<=dd_max (N={dd_window}, dd_max={dd_max})",
            f"Filter: drawdown_20d_max={float(cfg.require('filters.drawdown_20d_max')):.2f}",
            f"Trigger: PULLBACK_25={bool(cfg.require('triggers.pullback_25.enabled'))} (low<=SMA25*(1+tol), close>=SMA25, volume<=vol_ma20)",
            f"Trigger: PULLBACK_50={bool(cfg.require('triggers.pullback_50.enabled'))} (low<=SMA50*(1+tol), close>=SMA50, drawdown_20d<=max)",
            f"Trigger: BREAKOUT_20D={bool(cfg.require('triggers.breakout_20d.enabled'))} (close>high_20d, close<=high_20d*1.05, volume>=vol_ma20*{float(cfg.require('triggers.breakout_volume_mult')):.2f})",
        ]
        return lines

    title = f"Stock Alerts {datetime.now(timezone.utc).strftime('%Y-%m-%d')} UTC | Regime {regime_result.state}"
    header = [
        f"RegimeScore: {json.dumps(regime_result.__dict__, ensure_ascii=True)}",
    ]
    header = _config_summary(config) + header

    hits: list[dict[str, str]] = []
    triggered_symbols: list[str] = []
    top_rejected = ""
    if rejected_reasons:
        top_rejected = ", ".join(f"{k}:{v}" for k, v in rejected_reasons.most_common(5))

    if not regime_result.allow_new_entries:
        summary = [f"New entries stopped. max_exposure={regime_result.max_exposure:.2f}"]
        if eligible_symbols:
            summary.append(f"eligible_symbols: {', '.join(eligible_symbols)}")
        summary.append(f"triggered_symbols: {', '.join(sorted(set(triggered_symbols)))}")
        if top_rejected:
            summary.append(f"top_rejected_reasons: {top_rejected}")
        notifier.notify_batch(title, header + summary)
        append_regime_log(regime_result, hits)
        return 0

    if not all_signals:
        lines = ["No signals."]
        if eligible_symbols:
            lines.append(f"eligible_symbols: {', '.join(eligible_symbols)}")
        lines.append("triggered_symbols: []")
        if top_rejected:
            lines.append(f"top_rejected_reasons: {top_rejected}")
        if skipped:
            lines.append(f"Skipped symbols: {', '.join(skipped)}")
        notifier.notify_batch(title, header + lines)
        append_regime_log(regime_result, hits)
        return 0

    grouped: dict[str, list[Signal]] = {}
    for signal in all_signals:
        grouped.setdefault(signal.trigger, []).append(signal)

    lines: list[str] = []
    for trigger, items in grouped.items():
        lines.append(f"[{trigger}]")
        for item in items:
            lines.append(f"- {item.symbol} close={item.close:.2f} date={item.date}")
            hits.append({"symbol": item.symbol, "close": f"{item.close:.2f}"})
            triggered_symbols.append(item.symbol)
    if eligible_symbols:
        lines.append(f"eligible_symbols: {', '.join(eligible_symbols)}")
    lines.append(f"triggered_symbols: {', '.join(sorted(set(triggered_symbols)))}")
    if top_rejected:
        lines.append(f"top_rejected_reasons: {top_rejected}")
    if skipped:
        lines.append(f"Skipped symbols: {', '.join(skipped)}")

    notifier.notify_batch(title, header + lines)
    append_regime_log(regime_result, hits)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
