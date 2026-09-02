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

OVER_UNDER_SOURCES = {
    "B365": "Bet365",
    "P": "Pinnacle",
}

ASIAN_HANDICAP_SOURCES = {
    "B365": "Bet365",
    "P": "Pinnacle",
    "GB": "Gamebookers",
    "LB": "Ladbrokes",
}


def _transform_market_odds(
    row: pd.Series,
    column_mapping: dict[str, tuple[str, str]],
    market: str,
    phase: str,
    line: float | None = None,
) -> list[dict[str, Any]]:
    odds = []

    for column, (source, selection) in column_mapping.items():
        if column not in row.index:
            continue

        price = row[column]

        if pd.isna(price):
            continue

        odds.append(
            {
                "source": source,
                "market": market,
                "selection": selection,
                "line": line,
                "phase": phase,
                "price": float(price),
            }
        )

    return odds


def transform_1x2_odds(row: pd.Series) -> list[dict[str, Any]]:
    mapping = {}

    for code, bookmaker in BOOKMAKER_CODES.items():
        mapping.update(
            {
                f"{code}H": (bookmaker, "HOME"),
                f"{code}D": (bookmaker, "DRAW"),
                f"{code}A": (bookmaker, "AWAY"),
            }
        )

    odds = _transform_market_odds(
        row,
        mapping,
        market="1X2",
        phase="PRE_CLOSING",
    )

    closing_mapping = {}

    for code, bookmaker in BOOKMAKER_CODES.items():
        closing_mapping.update(
            {
                f"{code}CH": (bookmaker, "HOME"),
                f"{code}CD": (bookmaker, "DRAW"),
                f"{code}CA": (bookmaker, "AWAY"),
            }
        )

    odds.extend(
        _transform_market_odds(
            row,
            closing_mapping,
            market="1X2",
            phase="CLOSING",
        )
    )

    return odds


def transform_over_under_odds(row: pd.Series) -> list[dict[str, Any]]:
    mapping = {}

    for code, bookmaker in OVER_UNDER_SOURCES.items():
        mapping[f"{code}>2.5"] = (bookmaker, "OVER")
        mapping[f"{code}<2.5"] = (bookmaker, "UNDER")

    mapping.update(
        {
            "Max>2.5": ("Market Max", "OVER"),
            "Max<2.5": ("Market Max", "UNDER"),
            "Avg>2.5": ("Market Average", "OVER"),
            "Avg<2.5": ("Market Average", "UNDER"),
        }
    )

    return _transform_market_odds(
        row,
        mapping,
        market="OVER_UNDER",
        phase="PRE_CLOSING",
        line=2.5,
    )


def transform_asian_handicap_odds(
    row: pd.Series,
) -> list[dict[str, Any]]:
    odds = []

    for code, bookmaker in ASIAN_HANDICAP_SOURCES.items():
        handicap_column = f"{code}AH"

        if handicap_column not in row.index:
            continue

        handicap = row[handicap_column]

        if pd.isna(handicap):
            continue

        mapping = {
            f"{code}AHH": (bookmaker, "HOME"),
            f"{code}AHA": (bookmaker, "AWAY"),
        }

        odds.extend(
            _transform_market_odds(
                row,
                mapping,
                market="ASIAN_HANDICAP",
                phase="PRE_CLOSING",
                line=float(handicap),
            )
        )

    return odds


def transform_odds(row: pd.Series) -> list[dict[str, Any]]:
    odds = []

    odds.extend(transform_1x2_odds(row))
    odds.extend(transform_over_under_odds(row))
    odds.extend(transform_asian_handicap_odds(row))

    return odds
