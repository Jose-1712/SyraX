"""
predict.py
----------
Unified inference layer used by the Flask API (api/app.py).

Exposes:
    forecast_demand(history_df, horizon_hours=24)  -> list of hourly forecasts
    get_battery_recommendation(...)                -> charge/discharge decision
    dashboard_summary()                             -> cost/savings snapshot
"""

import os
import pickle
import sys

import numpy as np
import pandas as pd
import xgboost as xgb

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from preprocessing.preprocess import (
    FEATURE_COLUMNS, TARGET_COL, load_raw_data, build_features, add_time_features,
)
from preprocessing.battery_preprocess import load_battery_data
from models.battery_health import predict_battery_health
from models import rl_agent

MODELS_DIR = os.path.dirname(os.path.abspath(__file__))

_cache = {}


def _load_demand_model() -> xgb.XGBRegressor: # Creates a function to load the trained XGBoost demand forecasting model
    if "demand_model" not in _cache:
        model = xgb.XGBRegressor()
        model.load_model(os.path.join(MODELS_DIR, "xgb_demand_model.json"))
        _cache["demand_model"] = model
    return _cache["demand_model"]


def _load_norm_stats() -> dict:
    if "norm_stats" not in _cache:
        with open(os.path.join(MODELS_DIR, "norm_stats.pkl"), "rb") as f:
            _cache["norm_stats"] = pickle.load(f)
    return _cache["norm_stats"]


def _load_rl_model():
    if "rl_model" not in _cache:
        _cache["rl_model"] = rl_agent.load_agent()
    return _cache["rl_model"]


def _latest_history(n_hours: int = 200) -> pd.DataFrame:
    """Return the most recent n_hours of raw readings (needs >=168 for lag_168h)."""
    raw = load_raw_data()
    return raw.tail(n_hours).reset_index(drop=True)


def forecast_demand(history_df: pd.DataFrame = None, horizon_hours: int = 24) -> list:
    """
    Iteratively forecast the next `horizon_hours` of electricity demand.
    Each step's prediction is fed back in as the newest lag value for the
    next step (standard recursive multi-step forecasting).
    """
    model = _load_demand_model()
    history_df = history_df if history_df is not None else _latest_history()
    history_df = history_df.copy()
    history_df["timestamp"] = pd.to_datetime(history_df["timestamp"])

    forecasts = []
    working = history_df.copy()
    last_row = working.iloc[-1]
    next_ts = last_row["timestamp"] + pd.Timedelta(hours=1)

    for step in range(horizon_hours):
        feats = build_features(working, dropna=True)
        x_row = feats.iloc[[-1]][FEATURE_COLUMNS]
        pred = float(model.predict(x_row)[0])

        forecasts.append({
            "timestamp": str(next_ts),
            "predicted_demand_kw": round(pred, 2),
        })

        # Append a synthetic next row so we can compute lags for the *following* step.
        new_row = last_row.copy()
        new_row["timestamp"] = next_ts
        new_row[TARGET_COL] = pred
        working = pd.concat([working, pd.DataFrame([new_row])], ignore_index=True)
        last_row = new_row
        next_ts = next_ts + pd.Timedelta(hours=1)

    return forecasts


def get_battery_recommendation(demand_kw: float, price_per_kwh: float, soc: float,
                                battery_reading: dict = None, hour: int = None) -> dict:
    """
    battery_reading: latest telemetry dict for the battery health model
                     (see preprocessing.battery_preprocess.NUMERIC_FEATURES).
                     If omitted, the most recent record in the battery
                     dataset is used and the battery is assumed healthy.
    """
    if battery_reading is None:
        df = load_battery_data()
        battery_reading = df.iloc[-1].to_dict()

    health = predict_battery_health(battery_reading)

    if hour is None:
        hour = pd.Timestamp.now().hour

    model = _load_rl_model()
    action = rl_agent.recommend_action(
        demand_kw=demand_kw, price_per_kwh=price_per_kwh, soc=soc,
        usable_capacity_fraction=health["usable_capacity_fraction"],
        hour=hour, model=model,
    )

    return {
        "battery_health": health,
        "recommendation": action,
    }


def dashboard_summary() -> dict:
    """High-level KPIs for the dashboard: latest demand, forecast, battery
    health, and cumulative cost-savings vs. a no-battery baseline."""
    history = _latest_history()
    forecast = forecast_demand(history, horizon_hours=24)

    battery_df = load_battery_data()
    latest_battery = battery_df.iloc[-1].to_dict()
    health = predict_battery_health(latest_battery)

    backtest_result = rl_agent.backtest()

    return {
        "latest_actual_demand_kw": round(float(history[TARGET_COL].iloc[-1]), 2),
        "forecast_next_24h": forecast,
        "battery_health": health,
        "cost_savings": {k: round(float(v), 2) for k, v in backtest_result.items()},
    }


if __name__ == "__main__":
    print("--- 24h demand forecast ---")
    for f in forecast_demand(horizon_hours=6):
        print(f)

    print("\n--- battery recommendation ---")
    print(get_battery_recommendation(demand_kw=650, price_per_kwh=8.5, soc=0.4))
