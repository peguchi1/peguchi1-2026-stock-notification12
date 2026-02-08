from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests

from .cache import FileCache


@dataclass
class DataProviderConfig:
    provider_primary: str
    provider_fallback: str
    twelvedata: dict[str, Any]
    alphavantage: dict[str, Any]
    cache_enabled: bool
    cache_ttl_seconds: int
    retry_max_attempts: int
    retry_base_delay_seconds: float
    retry_max_delay_seconds: float
    rate_limit_enabled: bool
    rate_limit_min_interval_seconds: float


class MarketDataFetcher:
    def __init__(self, config: DataProviderConfig, cache: FileCache | None = None) -> None:
        self.config = config
        self.cache = cache
        self.session = requests.Session()
        self._last_call_ts = 0.0

    def fetch_daily(self, symbol: str) -> pd.DataFrame:
        self._throttle()
        providers = [self.config.provider_primary, self.config.provider_fallback]
        last_error: Exception | None = None
        for provider in providers:
            try:
                if provider == "twelvedata":
                    return self._fetch_twelvedata(symbol)
                if provider == "alphavantage":
                    return self._fetch_alphavantage(symbol)
                raise ValueError(f"Unsupported provider: {provider}")
            except Exception as exc:
                last_error = exc
        if last_error:
            raise last_error
        raise RuntimeError("No data provider available")

    def _fetch_twelvedata(self, symbol: str) -> pd.DataFrame:
        api_key = os.getenv("TWELVE_DATA_API_KEY")
        if not api_key:
            raise RuntimeError("TWELVE_DATA_API_KEY not set")
        params = {
            "symbol": symbol,
            "interval": self.config.twelvedata.get("interval", "1day"),
            "outputsize": self.config.twelvedata.get("outputsize", 300),
            "apikey": api_key,
        }
        url = self.config.twelvedata.get("base_url")
        payload = self._get_json_with_cache("twelvedata", symbol, url, params)
        if "values" not in payload:
            raise RuntimeError(f"Unexpected Twelve Data response for {symbol}")
        values = payload["values"]
        df = pd.DataFrame(values)
        df.rename(
            columns={
                "datetime": "date",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
            },
            inplace=True,
        )
        df["date"] = pd.to_datetime(df["date"])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.sort_values("date").reset_index(drop=True)
        return df

    def _fetch_alphavantage(self, symbol: str) -> pd.DataFrame:
        api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        if not api_key:
            raise RuntimeError("ALPHA_VANTAGE_API_KEY not set")
        params = {
            "function": self.config.alphavantage.get("function", "TIME_SERIES_DAILY_ADJUSTED"),
            "symbol": symbol,
            "outputsize": self.config.alphavantage.get("outputsize", "full"),
            "apikey": api_key,
        }
        url = self.config.alphavantage.get("base_url")
        payload = self._get_json_with_cache("alphavantage", symbol, url, params)
        series = payload.get("Time Series (Daily)")
        if not isinstance(series, dict):
            raise RuntimeError(f"Unexpected Alpha Vantage response for {symbol}")
        rows = []
        for date_str, row in series.items():
            rows.append(
                {
                    "date": date_str,
                    "open": row.get("1. open"),
                    "high": row.get("2. high"),
                    "low": row.get("3. low"),
                    "close": row.get("4. close"),
                    "volume": row.get("6. volume") or row.get("5. volume"),
                }
            )
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.sort_values("date").reset_index(drop=True)
        return df

    def _get_json_with_cache(self, provider: str, symbol: str, url: str, params: dict[str, Any]) -> dict[str, Any]:
        cache_key = f"{provider}_{symbol}"
        if self.cache and self.config.cache_enabled:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        last_error: Exception | None = None
        for attempt in range(self.config.retry_max_attempts):
            try:
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                payload = response.json()
                if "Note" in payload or "Information" in payload:
                    raise RuntimeError(payload.get("Note") or payload.get("Information"))
                if "Error Message" in payload or "code" in payload and payload.get("code") == 400:
                    raise RuntimeError(json.dumps(payload)[:200])
                if self.cache and self.config.cache_enabled:
                    self.cache.set(cache_key, payload)
                return payload
            except Exception as exc:
                last_error = exc
                delay = min(
                    self.config.retry_max_delay_seconds,
                    self.config.retry_base_delay_seconds * (2**attempt) + random.uniform(0, 0.5),
                )
                if self.config.rate_limit_enabled:
                    delay = max(delay, self.config.rate_limit_min_interval_seconds)
                time.sleep(delay)
        if last_error:
            raise last_error
        raise RuntimeError("Failed to fetch data")

    def _throttle(self) -> None:
        if not self.config.rate_limit_enabled:
            return
        now = time.time()
        elapsed = now - self._last_call_ts
        min_interval = self.config.rate_limit_min_interval_seconds
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_call_ts = time.time()
