from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from .market_regime import RegimeScoreResult


def append_regime_log(
    regime: RegimeScoreResult,
    hits: list[dict[str, Any]],
) -> None:
    sheet_url = os.getenv("GOOGLE_SHEET_URL")
    cred_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    cred_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sheet_url or (not cred_file and not cred_json):
        return

    if cred_json:
        creds_info = json.loads(cred_json)
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
        client = gspread.authorize(creds)
    else:
        client = gspread.service_account(filename=cred_file)
    worksheet = client.open_by_url(sheet_url).sheet1

    header = [
        "date",
        "state",
        "total_score",
        "nfci_L",
        "s_1w",
        "s_4w",
        "price_close",
        "ma50",
        "ma200",
        "price_score",
        "level_score",
        "trend_score",
        "abs_penalty",
        "max_exposure",
        "allow_new_entries",
        "risk_off_trigger",
        "risk_on_trigger",
        "notes",
        "regime_json",
        "hits_json",
    ]

    regime_dict = asdict(regime)
    row = [
        regime.date,
        regime.state,
        f"{regime.total_score:.6f}",
        f"{regime.nfci_L:.6f}",
        f"{regime.s_1w:.6f}",
        f"{regime.s_4w:.6f}",
        f"{regime.price_close:.6f}",
        f"{regime.ma50:.6f}",
        f"{regime.ma200:.6f}",
        str(regime.price_score),
        f"{regime.level_score:.6f}",
        f"{regime.trend_score:.6f}",
        f"{regime.abs_penalty:.6f}",
        f"{regime.max_exposure:.2f}",
        str(regime.allow_new_entries),
        str(regime.risk_off_trigger),
        str(regime.risk_on_trigger),
        regime.notes,
        json.dumps(regime_dict, ensure_ascii=True),
        json.dumps(hits, ensure_ascii=True),
    ]

    worksheet.update("A1", [header], value_input_option="RAW")
    worksheet.append_row(row, value_input_option="RAW")
