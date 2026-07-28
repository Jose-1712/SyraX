"""
train_battery_health.py
------------------------
Trains three models from the battery telemetry dataset
(data/battery_health_data.xlsx):

    1. SoH regressor        (RandomForestRegressor)
    2. RUL regressor        (RandomForestRegressor)
    3. Fault classifier     (RandomForestClassifier)

These feed models/battery_health.py at inference time, which converts
predicted SoH/RUL/fault into a safe "usable capacity fraction" consumed
by the RL battery-scheduling agent (models/rl_agent.py).

Run:
    python models/train_battery_health.py
"""

import os
import pickle
import sys

from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from preprocessing.battery_preprocess import (
    NUMERIC_FEATURES, load_battery_data, build_battery_features,
)

MODELS_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    df = load_battery_data()
    X, y_soh, y_rul, y_fault, fault_encoder = build_battery_features(df)

    X_train, X_test, ysoh_train, ysoh_test, yrul_train, yrul_test, yf_train, yf_test = (
        train_test_split(X, y_soh, y_rul, y_fault, test_size=0.2, random_state=42)
    )

    soh_model = RandomForestRegressor(n_estimators=300, max_depth=8, random_state=42, n_jobs=-1)
    soh_model.fit(X_train, ysoh_train)
    soh_pred = soh_model.predict(X_test)
    print(f"SoH  -> MAE: {mean_absolute_error(ysoh_test, soh_pred):.4f}  "
          f"R2: {r2_score(ysoh_test, soh_pred):.4f}")

    rul_model = RandomForestRegressor(n_estimators=300, max_depth=8, random_state=42, n_jobs=-1)
    rul_model.fit(X_train, yrul_train)
    rul_pred = rul_model.predict(X_test)
    print(f"RUL  -> MAE: {mean_absolute_error(yrul_test, rul_pred):.4f}  "
          f"R2: {r2_score(yrul_test, rul_pred):.4f}")

    fault_model = RandomForestClassifier(n_estimators=300, max_depth=10, random_state=42, n_jobs=-1)
    fault_model.fit(X_train, yf_train)
    fault_pred = fault_model.predict(X_test)
    print(f"Fault-> Accuracy: {accuracy_score(yf_test, fault_pred):.4f}")

    artifacts = {
        "soh_model": soh_model,
        "rul_model": rul_model,
        "fault_model": fault_model,
        "fault_encoder": fault_encoder,
        "feature_columns": NUMERIC_FEATURES,
    }
    out_path = os.path.join(MODELS_DIR, "battery_health_models.pkl")
    with open(out_path, "wb") as f:
        pickle.dump(artifacts, f)

    print(f"Saved battery-health models to {out_path}")


if __name__ == "__main__":
    main()
