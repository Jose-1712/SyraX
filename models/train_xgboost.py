"""
train_xgboost.py
-----------------
Trains the electricity-demand forecasting model (XGBoost regressor).

Run:
    python models/train_xgboost.py

Produces (all under models/):
    xgb_demand_model.json   - the trained booster
    feature_columns.pkl     - ordered feature list the model expects
    norm_stats.pkl          - mean/std of demand & price (used for reporting)
    xgb_metrics.pkl         - evaluation metrics on the held-out test split

The hyperparameters below reproduce the metrics already shipped in
reports/final_summary.csv (MAE ~23 kW, R2 ~0.987). Set --tune to re-run a
randomized hyperparameter search instead of using the fixed params.
"""

import argparse
import os
import pickle
import sys

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import RandomizedSearchCV

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from preprocessing.preprocess import (
    FEATURE_COLUMNS, TARGET_COL, load_raw_data, build_features,
    train_test_split_by_time,
)

MODELS_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_PARAMS = {
    "n_estimators": 1000,
    "max_depth": 3,
    "learning_rate": 0.08422524892255821,
    "subsample": 0.6656860065814046,
    "colsample_bytree": 0.8068867165617402,
    "min_child_weight": 5,
    "reg_alpha": 0.041368999427323486,
    "reg_lambda": 0.27128344627943257,
    "objective": "reg:squarederror",
    "random_state": 42,
    "n_jobs": -1,
}

SEARCH_SPACE = {
    "n_estimators": [300, 500, 800, 1000],
    "max_depth": [3, 4, 5, 6],
    "learning_rate": np.linspace(0.01, 0.2, 20),
    "subsample": np.linspace(0.5, 1.0, 10),
    "colsample_bytree": np.linspace(0.5, 1.0, 10),
    "min_child_weight": [1, 3, 5, 7],
    "reg_alpha": np.linspace(0, 1, 20),
    "reg_lambda": np.linspace(0, 1, 20),
}


def evaluate(y_true, y_pred) -> dict:
    mae = mean_absolute_error(y_true, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mape = float(np.mean(np.abs((y_true - y_pred) / np.clip(y_true, 1e-6, None))) * 100)
    r2 = r2_score(y_true, y_pred)
    return {"mae": mae, "rmse": rmse, "mape": mape, "r2": r2}


def main(tune: bool = False, data_path: str = None):
    raw = load_raw_data(data_path) if data_path else load_raw_data()
    features_df = build_features(raw, dropna=True)

    train_df, test_df = train_test_split_by_time(features_df, test_size=0.2)

    X_train, y_train = train_df[FEATURE_COLUMNS], train_df[TARGET_COL]
    X_test, y_test = test_df[FEATURE_COLUMNS], test_df[TARGET_COL]

    if tune:
        print("Running randomized hyperparameter search (this may take a while)...")
        base = xgb.XGBRegressor(objective="reg:squarederror", random_state=42, n_jobs=-1)
        search = RandomizedSearchCV(
            base, SEARCH_SPACE, n_iter=25, cv=3,
            scoring="neg_mean_absolute_error", random_state=42, n_jobs=-1, verbose=1,
        )
        search.fit(X_train, y_train)
        model = search.best_estimator_
        best_params = search.best_params_
        print("Best params:", best_params)
    else:
        best_params = DEFAULT_PARAMS
        model = xgb.XGBRegressor(**best_params)
        model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    metrics = evaluate(y_test.values, y_pred)
    metrics["best_params"] = best_params
    print("Test metrics:", {k: v for k, v in metrics.items() if k != "best_params"})

    # Save artifacts
    model.save_model(os.path.join(MODELS_DIR, "xgb_demand_model.json"))

    with open(os.path.join(MODELS_DIR, "feature_columns.pkl"), "wb") as f:
        pickle.dump(FEATURE_COLUMNS, f)

    norm_stats = {
        "demand_mean": float(features_df[TARGET_COL].mean()),
        "demand_std": float(features_df[TARGET_COL].std()),
        "price_mean": float(features_df["price_per_kwh"].mean()),
        "price_std": float(features_df["price_per_kwh"].std()),
    }
    with open(os.path.join(MODELS_DIR, "norm_stats.pkl"), "wb") as f:
        pickle.dump(norm_stats, f)

    with open(os.path.join(MODELS_DIR, "xgb_metrics.pkl"), "wb") as f:
        pickle.dump(metrics, f)

    print(f"Saved model + metadata to {MODELS_DIR}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tune", action="store_true", help="run hyperparameter search")
    parser.add_argument("--data", type=str, default=None, help="override path to raw CSV")
    args = parser.parse_args()
    main(tune=args.tune, data_path=args.data)
