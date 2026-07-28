"""
preprocess.py
--------------
Feature engineering pipeline for the industrial electricity-demand dataset
(data/raw_energy_data.csv).

This module is used in two places:
  1. models/train_xgboost.py  -> builds the training matrix (drops warm-up NaNs)
  2. models/predict.py        -> builds a single feature row for live inference
                                  (keeps NaNs where history is missing, caller
                                  must supply enough history for lag features)

The output feature order MUST match models/feature_columns.pkl exactly, since
the shipped xgb_demand_model.json was trained on that column order.
"""

import numpy as np
import pandas as pd

RAW_DATA_PATH = "data/raw_energy_data.csv"

TARGET_COL = "electricity_demand_kw"

# Exact column order the shipped model expects (models/feature_columns.pkl)
FEATURE_COLUMNS = [
    "production_volume", "ambient_temperature", "humidity", "machine_load_pct",
    "shift", "is_weekend", "price_per_kwh",
    "hour", "dayofweek", "month",
    "hour_sin", "hour_cos", "dow_sin", "dow_cos", "month_sin", "month_cos",
    "demand_lag_1h", "demand_lag_2h", "demand_lag_3h",
    "demand_lag_24h", "demand_lag_48h", "demand_lag_168h",
    "demand_roll_mean_6h", "demand_roll_std_6h",
    "demand_roll_mean_24h", "demand_roll_std_24h",
    "demand_roll_mean_168h", "demand_roll_std_168h",
]

LAG_HOURS = [1, 2, 3, 24, 48, 168]
ROLL_WINDOWS = [6, 24, 168]


def load_raw_data(path: str = RAW_DATA_PATH) -> pd.DataFrame:
    """Load the raw CSV and parse the timestamp column."""
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add calendar + cyclical encodings derived from the timestamp."""
    df = df.copy()
    df["hour"] = df["timestamp"].dt.hour
    df["dayofweek"] = df["timestamp"].dt.dayofweek
    df["month"] = df["timestamp"].dt.month

    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["dow_sin"] = np.sin(2 * np.pi * df["dayofweek"] / 7)
    df["dow_cos"] = np.cos(2 * np.pi * df["dayofweek"] / 7)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    return df


def add_lag_features(df: pd.DataFrame, target_col: str = TARGET_COL) -> pd.DataFrame:
    """Add lagged demand values. Requires df sorted ascending by timestamp."""
    df = df.copy()
    for lag in LAG_HOURS:
        df[f"demand_lag_{lag}h"] = df[target_col].shift(lag)
    return df


def add_rolling_features(df: pd.DataFrame, target_col: str = TARGET_COL) -> pd.DataFrame:
    """Add rolling mean/std of demand, computed on lag-1 data to avoid leakage."""
    df = df.copy()
    shifted = df[target_col].shift(1)
    for window in ROLL_WINDOWS:
        df[f"demand_roll_mean_{window}h"] = shifted.rolling(window, min_periods=1).mean()
        df[f"demand_roll_std_{window}h"] = shifted.rolling(window, min_periods=1).std()
    return df


def build_features(df: pd.DataFrame, dropna: bool = True) -> pd.DataFrame:
    """
    Full feature-engineering pipeline.

    Parameters
    ----------
    df : DataFrame with at least the raw columns from raw_energy_data.csv
    dropna : if True, drops warm-up rows that don't have full lag history
             (use True for training, False for a single live-inference row
             where the caller has already provided the necessary lag values)

    Returns
    -------
    DataFrame with columns = [FEATURE_COLUMNS] + [TARGET_COL, 'timestamp']
    """
    df = add_time_features(df)
    df = add_lag_features(df)
    df = add_rolling_features(df)

    keep_cols = ["timestamp"] + FEATURE_COLUMNS + (
        [TARGET_COL] if TARGET_COL in df.columns else []
    )
    df = df[keep_cols]

    if dropna:
        df = df.dropna().reset_index(drop=True)

    return df


def train_test_split_by_time(df: pd.DataFrame, test_size: float = 0.2):
    """Chronological split (no shuffling) so the test set is strictly future data."""
    split_idx = int(len(df) * (1 - test_size))
    train_df = df.iloc[:split_idx].reset_index(drop=True)
    test_df = df.iloc[split_idx:].reset_index(drop=True)
    return train_df, test_df


if __name__ == "__main__":
    raw = load_raw_data()
    features = build_features(raw, dropna=True)
    out_path = "data/processed_energy_data.csv"
    features.to_csv(out_path, index=False)
    print(f"Loaded {len(raw)} raw rows -> {len(features)} feature rows "
          f"({len(FEATURE_COLUMNS)} features).")
    print(f"Saved processed dataset to {out_path}")
