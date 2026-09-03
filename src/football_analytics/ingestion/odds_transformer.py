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

    odds = _transform_market_odds(
        row,
        mapping,
        market="OVER_UNDER",
        phase="PRE_CLOSING",
        line=2.5,
    )

    closing_mapping = {}

    for code, bookmaker in OVER_UNDER_SOURCES.items():
        closing_mapping[f"{code}C>2.5"] = (bookmaker, "OVER")
        closing_mapping[f"{code}C<2.5"] = (bookmaker, "UNDER")

    closing_mapping.update(
        {
            "MaxC>2.5": ("Market Max", "OVER"),
            "MaxC<2.5": ("Market Max", "UNDER"),
            "AvgC>2.5": ("Market Average", "OVER"),
            "AvgC<2.5": ("Market Average", "UNDER"),
        }
    )

    odds.extend(
        _transform_market_odds(
            row,
            closing_mapping,
            market="OVER_UNDER",
            phase="CLOSING",
            line=2.5,
        )
    )

    return odds


def transform_asian_handicap_odds(
    row: pd.Series,
) -> list[dict[str, Any]]:
    odds = []

    handicap = row.get("AHh")

    if pd.notna(handicap):
        mapping = {}

        for code, bookmaker in ASIAN_HANDICAP_SOURCES.items():
            mapping[f"{code}AHH"] = (bookmaker, "HOME")
            mapping[f"{code}AHA"] = (bookmaker, "AWAY")

        mapping.update(
            {
                "MaxAHH": ("Market Max", "HOME"),
                "MaxAHA": ("Market Max", "AWAY"),
                "AvgAHH": ("Market Average", "HOME"),
                "AvgAHA": ("Market Average", "AWAY"),
            }
        )

        odds.extend(
            _transform_market_odds(
                row,
                mapping,
                market="ASIAN_HANDICAP",
                phase="PRE_CLOSING",
                line=float(handicap),
            )
        )

    closing_handicap = row.get("AHCh")

    if pd.notna(closing_handicap):
        closing_mapping = {}

        for code, bookmaker in ASIAN_HANDICAP_SOURCES.items():
            closing_mapping[f"{code}CAHH"] = (bookmaker, "HOME")
            closing_mapping[f"{code}CAHA"] = (bookmaker, "AWAY")

        closing_mapping.update(
            {
                "MaxCAHH": ("Market Max", "HOME"),
                "MaxCAHA": ("Market Max", "AWAY"),
                "AvgCAHH": ("Market Average", "HOME"),
                "AvgCAHA": ("Market Average", "AWAY"),
            }
        )

        odds.extend(
            _transform_market_odds(
                row,
                closing_mapping,
                market="ASIAN_HANDICAP",
                phase="CLOSING",
                line=float(closing_handicap),
            )
        )

    return odds


def transform_odds(row: pd.Series) -> list[dict[str, Any]]:
    odds = []

    odds.extend(transform_1x2_odds(row))
    odds.extend(transform_over_under_odds(row))
    odds.extend(transform_asian_handicap_odds(row))

    return odds
