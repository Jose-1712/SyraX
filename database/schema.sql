-- schema.sql
-- Schema for the AI Energy Management System
-- Run:  mysql -u <user> -p < database/schema.sql

CREATE DATABASE IF NOT EXISTS ai_energy_management
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE ai_energy_management;

-- Raw hourly readings ingested from the plant's meters / SCADA feed
CREATE TABLE IF NOT EXISTS energy_readings (
    id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
    reading_time        DATETIME NOT NULL,
    electricity_demand_kw DECIMAL(10,2) NOT NULL,
    production_volume   DECIMAL(10,2),
    ambient_temperature DECIMAL(6,2),
    humidity             DECIMAL(6,2),
    machine_load_pct     DECIMAL(6,2),
    shift                TINYINT,
    is_weekend           TINYINT,
    price_per_kwh         DECIMAL(8,4),
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_reading_time (reading_time)
) ENGINE=InnoDB;

-- Model output: forecast demand for future hours
CREATE TABLE IF NOT EXISTS demand_predictions (
    id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
    forecast_for         DATETIME NOT NULL,
    predicted_demand_kw  DECIMAL(10,2) NOT NULL,
    generated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model_version         VARCHAR(50) DEFAULT 'xgb_v1'
) ENGINE=InnoDB;

-- Battery telemetry + predicted health (SoH / RUL / fault)
CREATE TABLE IF NOT EXISTS battery_status (
    id                    BIGINT AUTO_INCREMENT PRIMARY KEY,
    battery_id             VARCHAR(20) NOT NULL,
    reading_time            DATETIME NOT NULL,
    voltage                 DECIMAL(6,3),
    capacity                DECIMAL(6,3),
    soc                      DECIMAL(5,4) COMMENT 'current state of charge, 0-1',
    soh                      DECIMAL(5,4) COMMENT 'predicted state of health, 0-1',
    rul_cycles               DECIMAL(8,2) COMMENT 'predicted remaining useful life',
    fault_type               VARCHAR(30) DEFAULT 'Normal',
    usable_capacity_fraction DECIMAL(5,4),
    created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- RL agent's charge / discharge decisions and the resulting grid cost
CREATE TABLE IF NOT EXISTS battery_actions (
    id                BIGINT AUTO_INCREMENT PRIMARY KEY,
    action_time         DATETIME NOT NULL,
    mode                 ENUM('charge', 'discharge', 'idle') NOT NULL,
    power_kw              DECIMAL(8,2) NOT NULL,
    grid_demand_kw         DECIMAL(10,2),
    price_per_kwh           DECIMAL(8,4),
    grid_cost                DECIMAL(12,2),
    baseline_cost             DECIMAL(12,2),
    created_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Rolling summary of cost savings (populated by a periodic job / API call)
CREATE TABLE IF NOT EXISTS cost_savings_log (
    id                        BIGINT AUTO_INCREMENT PRIMARY KEY,
    period_start                DATETIME NOT NULL,
    period_end                   DATETIME NOT NULL,
    baseline_electricity_cost      DECIMAL(14,2) NOT NULL,
    rl_optimized_cost                DECIMAL(14,2) NOT NULL,
    absolute_savings                  DECIMAL(14,2) NOT NULL,
    percentage_savings                 DECIMAL(6,3) NOT NULL,
    created_at                          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Alerts raised when the battery health model detects a non-normal fault
CREATE TABLE IF NOT EXISTS alerts (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    battery_id      VARCHAR(20) NOT NULL,
    alert_time        DATETIME NOT NULL,
    fault_type          VARCHAR(30) NOT NULL,
    message                VARCHAR(255),
    resolved                 TINYINT DEFAULT 0,
    created_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE INDEX idx_readings_time ON energy_readings (reading_time);
CREATE INDEX idx_predictions_time ON demand_predictions (forecast_for);
CREATE INDEX idx_battery_status_time ON battery_status (battery_id, reading_time);
CREATE INDEX idx_battery_actions_time ON battery_actions (action_time);
