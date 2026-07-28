"""
mysql_connection.py
--------------------
Thin MySQL access layer used by api/app.py.

Configure the connection via environment variables (recommended) or edit
the DEFAULTS below directly:

    DB_HOST=localhost
    DB_PORT=3306
    DB_USER=root
    DB_PASSWORD=yourpassword
    DB_NAME=ai_energy_management

Requires:  pip install mysql-connector-python
"""

import os
from contextlib import contextmanager

import mysql.connector
from mysql.connector import pooling

DEFAULTS = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "ai_energy_management"),
}

_pool = None


def get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="energy_pool", pool_size=5, **DEFAULTS
        )
    return _pool


@contextmanager
def get_connection():
    """Usage: with get_connection() as conn: ..."""
    conn = get_pool().get_connection()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_cursor(dictionary: bool = True, commit: bool = False):
    """Usage: with get_cursor() as cur: cur.execute(...); rows = cur.fetchall()"""
    with get_connection() as conn:
        cur = conn.cursor(dictionary=dictionary)
        try:
            yield cur
            if commit:
                conn.commit()
        finally:
            cur.close()


# ---------------------------------------------------------------------
# Convenience insert / fetch helpers used by api/app.py
# ---------------------------------------------------------------------

def insert_energy_reading(reading: dict):
    sql = """
        INSERT INTO energy_readings
            (reading_time, electricity_demand_kw, production_volume,
             ambient_temperature, humidity, machine_load_pct, shift,
             is_weekend, price_per_kwh)
        VALUES (%(reading_time)s, %(electricity_demand_kw)s, %(production_volume)s,
                %(ambient_temperature)s, %(humidity)s, %(machine_load_pct)s,
                %(shift)s, %(is_weekend)s, %(price_per_kwh)s)
        ON DUPLICATE KEY UPDATE
            electricity_demand_kw = VALUES(electricity_demand_kw)
    """
    with get_cursor(commit=True) as cur:
        cur.execute(sql, reading)


def insert_demand_predictions(predictions: list, model_version: str = "xgb_v1"):
    sql = """
        INSERT INTO demand_predictions (forecast_for, predicted_demand_kw, model_version)
        VALUES (%(forecast_for)s, %(predicted_demand_kw)s, %(model_version)s)
    """
    rows = [
        {"forecast_for": p["timestamp"], "predicted_demand_kw": p["predicted_demand_kw"],
         "model_version": model_version}
        for p in predictions
    ]
    with get_cursor(commit=True) as cur:
        cur.executemany(sql, rows)


def insert_battery_status(battery_id: str, reading_time: str, telemetry: dict, health: dict, soc: float):
    sql = """
        INSERT INTO battery_status
            (battery_id, reading_time, voltage, capacity, soc, soh, rul_cycles,
             fault_type, usable_capacity_fraction)
        VALUES (%(battery_id)s, %(reading_time)s, %(voltage)s, %(capacity)s, %(soc)s,
                %(soh)s, %(rul_cycles)s, %(fault_type)s, %(usable_capacity_fraction)s)
    """
    params = {
        "battery_id": battery_id,
        "reading_time": reading_time,
        "voltage": telemetry.get("voltage"),
        "capacity": telemetry.get("capacity"),
        "soc": soc,
        "soh": health["soh"],
        "rul_cycles": health["rul"],
        "fault_type": health["fault_type"],
        "usable_capacity_fraction": health["usable_capacity_fraction"],
    }
    with get_cursor(commit=True) as cur:
        cur.execute(sql, params)

    if health["fault_type"] != "Normal":
        insert_alert(battery_id, reading_time, health["fault_type"])


def insert_battery_action(action_time: str, mode: str, power_kw: float, grid_demand_kw: float,
                           price_per_kwh: float, grid_cost: float, baseline_cost: float):
    sql = """
        INSERT INTO battery_actions
            (action_time, mode, power_kw, grid_demand_kw, price_per_kwh, grid_cost, baseline_cost)
        VALUES (%(action_time)s, %(mode)s, %(power_kw)s, %(grid_demand_kw)s,
                %(price_per_kwh)s, %(grid_cost)s, %(baseline_cost)s)
    """
    with get_cursor(commit=True) as cur:
        cur.execute(sql, {
            "action_time": action_time, "mode": mode, "power_kw": power_kw,
            "grid_demand_kw": grid_demand_kw, "price_per_kwh": price_per_kwh,
            "grid_cost": grid_cost, "baseline_cost": baseline_cost,
        })


def insert_cost_savings(period_start: str, period_end: str, summary: dict):
    sql = """
        INSERT INTO cost_savings_log
            (period_start, period_end, baseline_electricity_cost, rl_optimized_cost,
             absolute_savings, percentage_savings)
        VALUES (%(period_start)s, %(period_end)s, %(baseline_electricity_cost)s,
                %(rl_optimized_cost)s, %(absolute_savings)s, %(percentage_savings)s)
    """
    params = {"period_start": period_start, "period_end": period_end, **summary}
    with get_cursor(commit=True) as cur:
        cur.execute(sql, params)


def insert_alert(battery_id: str, alert_time: str, fault_type: str):
    sql = """
        INSERT INTO alerts (battery_id, alert_time, fault_type, message)
        VALUES (%(battery_id)s, %(alert_time)s, %(fault_type)s, %(message)s)
    """
    with get_cursor(commit=True) as cur:
        cur.execute(sql, {
            "battery_id": battery_id, "alert_time": alert_time, "fault_type": fault_type,
            "message": f"Battery {battery_id} flagged as {fault_type}",
        })


def fetch_recent_readings(limit: int = 200) -> list:
    sql = "SELECT * FROM energy_readings ORDER BY reading_time DESC LIMIT %s"
    with get_cursor() as cur:
        cur.execute(sql, (limit,))
        return cur.fetchall()


def fetch_open_alerts() -> list:
    sql = "SELECT * FROM alerts WHERE resolved = 0 ORDER BY alert_time DESC"
    with get_cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def fetch_latest_cost_savings() -> dict:
    sql = "SELECT * FROM cost_savings_log ORDER BY created_at DESC LIMIT 1"
    with get_cursor() as cur:
        cur.execute(sql)
        return cur.fetchone()
