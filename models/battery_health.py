"""
battery_health.py
------------------
Inference-time wrapper around the models trained by train_battery_health.py.
Given the latest battery telemetry reading, returns predicted SoH, RUL,
fault type, and a safe usable-capacity fraction (0-1) for the RL agent.
"""

import os
import pickle
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from preprocessing.battery_preprocess import usable_capacity_fraction

MODELS_DIR = os.path.dirname(os.path.abspath(__file__))
ARTIFACT_PATH = os.path.join(MODELS_DIR, "battery_health_models.pkl")

_cache = {}


def _load_artifacts():
    if "artifacts" not in _cache:
        with open(ARTIFACT_PATH, "rb") as f:
            _cache["artifacts"] = pickle.load(f)
    return _cache["artifacts"]


def predict_battery_health(reading: dict) -> dict:
    """
    reading: dict with keys matching preprocessing.battery_preprocess.NUMERIC_FEATURES
             e.g. {"voltage": 3.9, "capacity": 1.5, "dT_dt": 0.01, ...}

    Returns: {"soh": float, "rul": float, "fault_type": str, "usable_capacity_fraction": float}
    """
    artifacts = _load_artifacts()
    feature_cols = artifacts["feature_columns"]

    row = pd.DataFrame([{col: reading[col] for col in feature_cols}])

    soh = float(artifacts["soh_model"].predict(row)[0])
    rul = float(artifacts["rul_model"].predict(row)[0])
    fault_encoded = artifacts["fault_model"].predict(row)[0]
    fault_type = artifacts["fault_encoder"].inverse_transform([fault_encoded])[0]

    fraction = usable_capacity_fraction(soh, rul, fault_type)

    return {
        "soh": round(soh, 4),
        "rul": round(rul, 1),
        "fault_type": str(fault_type),
        "usable_capacity_fraction": round(fraction, 4),
    }


if __name__ == "__main__":
    from preprocessing.battery_preprocess import load_battery_data

    df = load_battery_data()
    sample = df.iloc[-1].to_dict()
    result = predict_battery_health(sample)
    print("Latest reading health assessment:", result)
