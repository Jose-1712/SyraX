# AI Energy Management — Backend

Predicts an industrial plant's electricity demand, forecasts cost, and
schedules a battery (charge during low-price/low-demand hours, discharge
during peak) using a reinforcement-learning agent that also respects the
battery's real-time health (state of health, remaining useful life, faults).

## What this solves

1. **Forecast demand** — XGBoost model predicts electricity demand (kW) for
   the next N hours from production, weather, shift, and historical usage
   patterns. (`data/raw_energy_data.csv`)
2. **Estimate cost & savings** — compares a "no battery" baseline cost
   against an RL-optimized cost.
3. **Battery-aware scheduling** — a PPO reinforcement-learning agent decides
   when to charge/discharge the battery, constrained by the battery's
   predicted health so it isn't pushed past safe limits.
   (`data/battery_health_data.xlsx`)

## Project structure

```
AI-Energy-Management/
├── data/
│   ├── raw_energy_data.csv          # hourly plant demand + weather + production
│   └── battery_health_data.xlsx     # battery cycle telemetry (SoH/RUL/fault)
├── preprocessing/
│   ├── preprocess.py                # demand feature engineering (lags, rolling stats, time features)
│   └── battery_preprocess.py        # battery feature engineering + usable-capacity logic
├── models/
│   ├── train_xgboost.py             # trains the demand forecast model
│   ├── train_battery_health.py      # trains SoH / RUL / fault-type models
│   ├── battery_health.py            # inference wrapper for battery health
│   ├── rl_agent.py                  # BatteryEnv (Gymnasium) + PPO train/backtest/recommend
│   ├── predict.py                   # unified inference used by the API
│   ├── xgb_demand_model.json        # trained demand model (regenerate via train_xgboost.py)
│   ├── ppo_battery_agent.zip        # trained RL agent (regenerate via rl_agent.py --train)
│   ├── battery_health_models.pkl    # trained battery-health models
│   ├── feature_columns.pkl / norm_stats.pkl / xgb_metrics.pkl
├── database/
│   ├── schema.sql                   # MySQL schema
│   └── mysql_connection.py          # connection pool + insert/fetch helpers
├── api/
│   └── app.py                       # Flask REST API + serves the dashboard
├── frontend/
│   ├── templates/index.html
│   └── static/{style.css, app.js}
├── reports/                          # EDA / evaluation charts from the original analysis
└── requirements.txt
```

### Database (optional but recommended)

```bash
mysql -u root -p < database/schema.sql
```

Set connection details via environment variables (or edit the defaults in
`database/mysql_connection.py`):

```bash
export DB_HOST=localhost
export DB_PORT=3306
export DB_USER=root
export DB_PASSWORD=yourpassword
export DB_NAME=ai_energy_management
```

> The API works fine without MySQL running — it just skips persistence and
> logs a warning. This is intentional so you can demo the models/API first
> and wire up the database later.

## Training the models

The repo ships with pretrained artifacts, so this is optional unless you
want to retrain on new data:

```bash
python preprocessing/preprocess.py          # optional: writes data/processed_energy_data.csv
python models/train_xgboost.py              # trains the demand model (~1 min)
python models/train_battery_health.py       # trains SoH/RUL/fault models (~10s)
python models/rl_agent.py --train --timesteps 200000   # trains the PPO battery agent
python models/rl_agent.py --backtest        # reports baseline vs. optimized cost
```

`--timesteps 200000` takes several minutes on CPU. For a quick smoke test,
use a smaller value (e.g. `--timesteps 20000`); for production-quality
scheduling, train longer (500k–1M timesteps) and validate the backtest
savings before deploying.

## Running the API + dashboard

```bash
python api/app.py
```

Open http://localhost:5000 for the dashboard, or call the API directly:

| Method | Endpoint                    | Description                              |
|--------|------------------------------|-------------------------------------------|
| GET    | `/api/health`                | liveness check                            |
| GET    | `/api/predict/demand?hours=24` | iterative demand forecast                |
| GET    | `/api/battery/status`        | latest battery health snapshot            |
| POST   | `/api/battery/recommend`     | `{demand_kw, price_per_kwh, soc}` -> charge/discharge action |
| GET    | `/api/dashboard/summary`     | KPIs for the dashboard                    |
| GET    | `/api/alerts`                | open battery-fault alerts                 |
| POST   | `/api/data/ingest`           | ingest a new hourly meter reading         |

## Notes on the two datasets

- `raw_energy_data.csv` — hourly plant-level demand, production, weather,
  shift and price data. Drives the **demand forecast** (XGBoost) and the
  **RL battery scheduler**'s price/demand signal.
- `battery_health_data.xlsx` — per-cycle battery telemetry (11 packs) with
  SoH, RUL, and fault labels, plus site weather/consumption. Drives the
  **battery health models**, whose output (a 0–1 "usable capacity
  fraction") is fed into the RL agent so it never schedules a charge/
  discharge cycle that would push an already-degraded or faulted battery
  further.

## Gemini AI insights

`POST /api/ai/insights` asks Gemini to turn the real model output (demand
forecast, battery health, cost savings) into plain-language recommendations.
The API key lives **only** on the server:

```bash
cp .env.example .env
# edit .env and set GEMINI_API_KEY (get one at https://aistudio.google.com/apikey)
pip install -r requirements.txt
python api/app.py
```

```bash
curl -X POST http://localhost:5000/api/ai/insights \
  -H "Content-Type: application/json" \
  -d '{"context": "dashboard"}'
```

Never put the key in frontend JavaScript or commit `.env` — `.gitignore`
already excludes it.

## Running on Google Colab (connected to GitHub)

`colab_run.ipynb` clones this repo from GitHub, installs dependencies, loads
`GEMINI_API_KEY` from **Colab's Secrets panel** (key icon in the left
sidebar — not typed into a cell), and serves the app through an ngrok
tunnel so you get a public URL to open in a browser.

1. Push this project to a GitHub repo.
2. Open `colab_run.ipynb` in Colab, edit `REPO_URL` at the top to your repo.
3. Add secrets in Colab: `GEMINI_API_KEY` (required), `NGROK_AUTHTOKEN`
   (optional, for the public tunnel — free at https://ngrok.com).
4. Run all cells. The last cell pushes any changes back to GitHub using a
   Personal Access Token entered via `getpass` (never saved in the notebook).

## Security notes

- If you ever paste an API key into a chat, notebook cell, or commit —
  treat it as compromised and rotate it immediately.
- `.env` is git-ignored. Only `.env.example` (with placeholder values) is
  committed.
- The Gemini key is read from `os.environ` server-side only; the browser
  never sees it.

## Extending

- Swap `BATTERY_CAPACITY_KWH` / `MAX_CHARGE_RATE_KW` in `models/rl_agent.py`
  to match your real installed battery.
- `api/app.py`'s `/api/data/ingest` endpoint is the hook for a live
  SCADA/meter feed — point your data-collection service at it.
- The dashboard (`frontend/`) is plain HTML/CSS/JS (Chart.js via CDN) so it
  can be embedded in Power BI/other tools or replaced entirely; the API is
  the real integration surface.
## final summary
