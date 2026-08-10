from pathlib import Path

import pandas as pd


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)