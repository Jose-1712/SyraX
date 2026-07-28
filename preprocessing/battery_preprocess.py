"""
battery_preprocess.py
----------------------
Feature engineering for the battery-health dataset
(data/battery_health_data.xlsx).

This dataset carries per-cycle battery telemetry (voltage, capacity, SoH,
RUL, fault_type) for 11 battery packs, merged with ambient weather and
site electricity-consumption readings. It is used to train models that
estimate:
    - State of Health (SoH)              -> regression
    - Remaining Useful Life (RUL, cycles) -> regression
    - Fault type                          -> classification

These outputs let the RL battery-scheduling agent know how much of the
battery's rated capacity can be safely used right now (see
models/battery_health.py and models/rl_agent.py).
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

BATTERY_DATA_PATH = "data/battery_health_data.xlsx"

NUMERIC_FEATURES = [
    "voltage", "capacity", "dT_dt", "dV_dt", "capacity_fade_pct",
    "temp_roll_avg", "volt_roll_avg", "Pressure", "global_radiation",
    "temp_mean(c)", "Wind_Speed", "Electricity_Consumed", "Temperature",
    "Humidity", "Avg_Past_Consumption", "cycle",
]

SOH_TARGET = "soh"
RUL_TARGET = "rul"
FAULT_TARGET = "fault_type"


def load_battery_data(path: str = BATTERY_DATA_PATH) -> pd.DataFrame:
    df = pd.read_excel(path)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df = df.sort_values(["battery_id", "cycle"]).reset_index(drop=True)
    return df


def build_battery_features(df: pd.DataFrame, fault_encoder: LabelEncoder = None):
    """
    Returns (X, y_soh, y_rul, y_fault_encoded, fault_encoder)
    Fit a new LabelEncoder if one isn't supplied (training time);
    reuse the supplied encoder at inference time.
    """
    df = df.copy()
    X = df[NUMERIC_FEATURES].copy()

    if fault_encoder is None:
        fault_encoder = LabelEncoder()
        y_fault = fault_encoder.fit_transform(df[FAULT_TARGET])
    else:
        y_fault = fault_encoder.transform(df[FAULT_TARGET])

    y_soh = df[SOH_TARGET].values
    y_rul = df[RUL_TARGET].values

    return X, y_soh, y_rul, y_fault, fault_encoder


def usable_capacity_fraction(soh: float, rul: float, fault_type: str,
                              min_soh: float = 0.6, min_rul: float = 5) -> float:
    """
    Translate predicted battery health into a safe usable-capacity fraction
    (0-1) that the RL agent should respect when deciding how much energy it
    can charge/discharge in the current cycle.

    - Below min_soh or min_rul, or under an active fault (other than Normal),
      usable capacity is heavily de-rated to protect the battery.
    """
    if fault_type != "Normal":
        derate = {"Overheating": 0.4, "Aging": 0.7, "Voltage Fluctuation": 0.5}.get(fault_type, 0.5)
    else:
        derate = 1.0

    if soh < min_soh or rul < min_rul:
        derate = min(derate, 0.3)

    fraction = np.clip(soh * derate, 0.0, 1.0)
    return float(fraction)


if __name__ == "__main__":
    df = load_battery_data()
    X, y_soh, y_rul, y_fault, enc = build_battery_features(df)
    print(f"Loaded {len(df)} battery records across {df['battery_id'].nunique()} packs.")
    print(f"Features: {list(X.columns)}")
    print(f"Fault classes: {list(enc.classes_)}")
