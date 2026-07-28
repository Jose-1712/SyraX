"""
app.py
------
Flask REST API for the AI Energy Management System.

Endpoints:
    GET  /api/health                     - liveness check
    GET  /api/predict/demand?hours=24    - iterative demand forecast
    GET  /api/battery/status             - latest battery health snapshot
    POST /api/battery/recommend          - charge/discharge recommendation
    GET  /api/dashboard/summary          - KPIs for the dashboard
    GET  /api/alerts                     - open battery-fault alerts
    POST /api/data/ingest                - ingest a new hourly reading

Run:
    python api/app.py
    (serves on http://localhost:5000, and also serves frontend/templates/index.html)

Note: database calls are wrapped in try/except so the API keeps working
(model-only mode) even if MySQL isn't configured/running yet.

"""

import os
import sys

from dotenv import load_dotenv
from flask import Flask, jsonify, request, render_template

load_dotenv()  # reads .env if present; no-op if it doesn't exist (e.g. Colab secrets used instead)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import predict as predict_mod
from models import rl_agent
from api import gemini_service

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

app = Flask(
    __name__,
    template_folder=os.path.join(FRONTEND_DIR, "templates"),
    static_folder=os.path.join(FRONTEND_DIR, "static"),
)


def _try_db(fn, *args, **kwargs):
    """Best-effort DB call: log and continue if MySQL isn't reachable."""
    try:
        from database import mysql_connection as db
        return fn(db, *args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        app.logger.warning(f"DB unavailable, skipping persistence: {exc}")
        return None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/predict/demand")
def predict_demand():
    hours = int(request.args.get("hours", 24))
    hours = max(1, min(hours, 168))
    forecast = predict_mod.forecast_demand(horizon_hours=hours)

    _try_db(lambda db: db.insert_demand_predictions(forecast))

    return jsonify({"horizon_hours": hours, "forecast": forecast})


@app.route("/api/battery/status")
def battery_status():
    from preprocessing.battery_preprocess import load_battery_data
    from models.battery_health import predict_battery_health

    df = load_battery_data()
    latest = df.iloc[-1]
    health = predict_battery_health(latest.to_dict())

    result = {
        "battery_id": latest["battery_id"],
        "reading_time": str(latest["Timestamp"]),
        "voltage": float(latest["voltage"]),
        "capacity": float(latest["capacity"]),
        **health,
    }
    return jsonify(result)


@app.route("/api/battery/recommend", methods=["POST"])
def battery_recommend():
    body = request.get_json(force=True, silent=True) or {}
    try:
        demand_kw = float(body["demand_kw"])
        price_per_kwh = float(body["price_per_kwh"])
        soc = float(body.get("soc", 0.5))
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "demand_kw and price_per_kwh are required numeric fields"}), 400

    hour = body.get("hour")
    result = predict_mod.get_battery_recommendation(
        demand_kw=demand_kw, price_per_kwh=price_per_kwh, soc=soc, hour=hour,
    )

    import datetime
    now = datetime.datetime.now().isoformat()
    rec = result["recommendation"]
    _try_db(
        lambda db: db.insert_battery_action(
            action_time=now, mode=rec["mode"], power_kw=rec["power_kw"],
            grid_demand_kw=demand_kw, price_per_kwh=price_per_kwh,
            grid_cost=demand_kw * price_per_kwh, baseline_cost=demand_kw * price_per_kwh,
        )
    )

    return jsonify(result)


@app.route("/api/dashboard/summary")
def dashboard_summary():
    summary = predict_mod.dashboard_summary()
    return jsonify(summary)


@app.route("/api/ai/insights", methods=["POST"])
def ai_insights():
    """
    Gemini-powered recommendations, grounded in real model output.

    body (all optional):
        { "context": "predict" | "battery" | "cost" | "dashboard",
          "question": "free-form question, overrides the default prompt" }

    The API key never leaves the server — the browser only ever calls
    this endpoint, never Gemini directly.
    """
    body = request.get_json(force=True, silent=True) or {}
    context_type = body.get("context", "dashboard")
    question = body.get("question")

    try:
        summary = predict_mod.dashboard_summary()
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"could not build data context: {exc}"}), 500

    forecast = summary["forecast_next_24h"]
    peak = max(forecast, key=lambda f: f["predicted_demand_kw"])
    health = summary["battery_health"]
    savings = summary["cost_savings"]

    context_lines = [
        f"Latest actual demand: {summary['latest_actual_demand_kw']} kW",
        f"Peak forecast (next 24h): {peak['predicted_demand_kw']} kW at {peak['timestamp']}",
        f"Battery SoH: {health['soh']*100:.1f}%, RUL: {health['rul']} cycles, "
        f"fault_type: {health['fault_type']}, usable capacity: {health['usable_capacity_fraction']*100:.1f}%",
        f"Baseline electricity cost: {savings['baseline_electricity_cost']}",
        f"RL-optimized cost: {savings['rl_optimized_cost']}",
        f"Savings: {savings['absolute_savings']} ({savings['percentage_savings']}%)",
    ]
    context = "\n".join(context_lines)

    try:
        insight_text = gemini_service.generate_insights(context, question=question)
    except RuntimeError as exc:
        # GEMINI_API_KEY not configured — fail gracefully, don't crash the dashboard
        return jsonify({"error": str(exc)}), 503
    except Exception as exc:  # noqa: BLE001
        app.logger.warning(f"Gemini call failed: {exc}")
        return jsonify({"error": "AI insight generation failed, see server logs"}), 502

    return jsonify({"context_type": context_type, "insights": insight_text})


@app.route("/api/alerts")
def alerts():
    rows = _try_db(lambda db: db.fetch_open_alerts())
    return jsonify(rows or [])


@app.route("/api/data/ingest", methods=["POST"])
def ingest():
    body = request.get_json(force=True, silent=True) or {}
    required = [
        "reading_time", "electricity_demand_kw", "production_volume",
        "ambient_temperature", "humidity", "machine_load_pct", "shift",
        "is_weekend", "price_per_kwh",
    ]
    missing = [k for k in required if k not in body]
    if missing:
        return jsonify({"error": f"missing fields: {missing}"}), 400

    _try_db(lambda db: db.insert_energy_reading(body))
    return jsonify({"status": "ingested"}), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
