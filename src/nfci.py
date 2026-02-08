from __future__ import annotations

import io
from dataclasses import dataclass

import pandas as pd
import requests


@dataclass
class NfciData:
    nfci: float
    anfci: float | None
    date: str


class NfciFetcher:
    def __init__(
        self,
        csv_url: str,
        fred_nfci_url: str = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=NFCI",
        fred_anfci_url: str = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=ANFCI",
    ) -> None:
        self.csv_url = csv_url
        self.fred_nfci_url = fred_nfci_url
        self.fred_anfci_url = fred_anfci_url

    def fetch_latest(self) -> NfciData:
        try:
            return self._fetch_chicagofed()
        except Exception:
            return self._fetch_fred()

    def fetch_series(self) -> pd.Series:
        df = self._fetch_fred_series(self.fred_nfci_url)
        if df.empty:
            raise RuntimeError("NFCI series empty")
        df = df.sort_values("date")
        series = pd.Series(df["value"].values, index=pd.to_datetime(df["date"]).dt.date)
        return series

    def _fetch_chicagofed(self) -> NfciData:
        response = requests.get(self.csv_url, timeout=30)
        response.raise_for_status()
        df = pd.read_csv(io.StringIO(response.text))
        if df.empty:
            raise RuntimeError("NFCI CSV empty")
        latest = df.iloc[-1]
        date = str(latest.iloc[0])
        nfci = float(latest.iloc[1])
        anfci = None
        if len(latest) >= 3:
            try:
                anfci = float(latest.iloc[2])
            except Exception:
                anfci = None
        return NfciData(nfci=nfci, anfci=anfci, date=date)

    def _fetch_fred(self) -> NfciData:
        nfci_df = self._fetch_fred_series(self.fred_nfci_url)
        anfci_df = self._fetch_fred_series(self.fred_anfci_url)

        merged = nfci_df.merge(anfci_df, on="date", how="outer", suffixes=("_nfci", "_anfci"))
        merged = merged.sort_values("date").reset_index(drop=True)
        merged = merged.dropna(subset=["value_nfci"], how="any")
        if merged.empty:
            raise RuntimeError("FRED NFCI data empty")

        latest = merged.iloc[-1]
        date = str(latest["date"])
        nfci = float(latest["value_nfci"])
        anfci = None
        if pd.notna(latest.get("value_anfci")):
            anfci = float(latest["value_anfci"])
        return NfciData(nfci=nfci, anfci=anfci, date=date)

    @staticmethod
    def _fetch_fred_series(url: str) -> pd.DataFrame:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        df = pd.read_csv(io.StringIO(response.text))
        if df.empty or len(df.columns) < 2:
            raise RuntimeError("FRED CSV empty")
        df = df.rename(columns={df.columns[0]: "date", df.columns[1]: "value"})
        df["date"] = pd.to_datetime(df["date"]).dt.date.astype(str)
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna(subset=["value"])
        return df
