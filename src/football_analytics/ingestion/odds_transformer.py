from typing import Any

import pandas as pd


BOOKMAKER_CODES = {
    "B365": "Bet365",
    "BFD": "Betfred",
    "BMGM": "BetMGM",
    "BV": "BetVictor",
    "BW": "Bet&Win",
    "CL": "Coral",
    "LB": "Ladbrokes",
    "PS": "Pinnacle",
    "BFE": "Betfair Exchange",
}


def transform_1x2_odds(row: pd.Series) -> list[dict[str, Any]]:
    odds = []

    for code, bookmaker in BOOKMAKER_CODES.items():
        columns = {
            "HOME": f"{code}H",
            "DRAW": f"{code}D",
            "AWAY": f"{code}A",
        }

        for selection, column in columns.items():
            if column not in row.index:
                continue

            price = row[column]

            if pd.isna(price):
                continue

            odds.append(
                {
                    "bookmaker": bookmaker,
                    "market": "1X2",
                    "selection": selection,
                    "line": None,
                    "phase": "PRE_CLOSING",
                    "price": float(price),
                }
            )

    return odds