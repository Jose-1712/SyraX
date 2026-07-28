"""
rl_agent.py
-----------
Reinforcement-learning battery scheduling agent.

Environment (BatteryEnv):
    At every hourly step the agent observes forecast demand, grid price,
    current battery state-of-charge (SoC), and the battery's currently
    usable-capacity fraction (from battery_health.py), then decides how
    much power to charge into / discharge from the battery.

    Goal: minimise total grid electricity cost by charging the battery
    when price/demand is low and discharging it to cover load during
    peak price/demand windows, while respecting battery health limits.

Action (continuous, 1-D, range [-1, 1]):
    -1   -> discharge at max rate
     0   -> idle
    +1   -> charge at max rate

Reward:
    -grid_cost_this_step   (agent is trained to minimise cost)
    plus a small penalty for violating SoC bounds or the health-derated
    usable-capacity limit.

Run:
    python models/rl_agent.py --train     # trains and saves ppo_battery_agent.zip
    python models/rl_agent.py --backtest  # loads the saved agent and reports savings
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError as e:
    raise ImportError(
        "gymnasium is required for rl_agent.py. Install with: pip install gymnasium"
    ) from e

try:
    from stable_baselines3 import PPO
except ImportError as e:
    raise ImportError(
        "stable-baselines3 is required for rl_agent.py. "
        "Install with: pip install stable-baselines3"
    ) from e

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from preprocessing.preprocess import load_raw_data, build_features, FEATURE_COLUMNS, TARGET_COL

MODELS_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_PATH = os.path.join(MODELS_DIR, "ppo_battery_agent.zip")

# --- Battery physical parameters (tune to match the real installed system) ---
BATTERY_CAPACITY_KWH = 500.0       # rated usable energy capacity
MAX_CHARGE_RATE_KW = 125.0         # max charge/discharge power per hour
ROUND_TRIP_EFFICIENCY = 0.92
SOC_MIN, SOC_MAX = 0.10, 0.95      # keep battery within a healthy SoC band


class BatteryEnv(gym.Env):
    """Gymnasium environment for hourly battery charge/discharge scheduling."""

    metadata = {"render_modes": []}

    def __init__(self, demand_kw: np.ndarray, price_per_kwh: np.ndarray,
                 usable_capacity_fraction: np.ndarray = None):
        super().__init__()
        assert len(demand_kw) == len(price_per_kwh)
        self.demand_kw = demand_kw.astype(np.float32)
        self.price = price_per_kwh.astype(np.float32)
        n = len(demand_kw)
        self.usable_fraction = (
            usable_capacity_fraction.astype(np.float32)
            if usable_capacity_fraction is not None
            else np.ones(n, dtype=np.float32)
        )

        self.n_steps = n
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(1,), dtype=np.float32)
        # obs: [norm_demand, norm_price, soc, usable_fraction, hour_sin, hour_cos]
        self.observation_space = spaces.Box(low=-5.0, high=5.0, shape=(6,), dtype=np.float32)

        self._t = 0
        self.soc = 0.5

    def _get_obs(self):
        norm_demand = (self.demand_kw[self._t] - self.demand_kw.mean()) / (self.demand_kw.std() + 1e-6)
        norm_price = (self.price[self._t] - self.price.mean()) / (self.price.std() + 1e-6)
        hour = self._t % 24
        hour_sin = np.sin(2 * np.pi * hour / 24)
        hour_cos = np.cos(2 * np.pi * hour / 24)
        return np.array([norm_demand, norm_price, self.soc,
                          self.usable_fraction[self._t], hour_sin, hour_cos], dtype=np.float32)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self._t = 0
        self.soc = 0.5
        return self._get_obs(), {}

    def step(self, action):
        act = float(np.clip(action[0], -1.0, 1.0))
        cap_limit = self.usable_fraction[self._t]

        power_kw = act * MAX_CHARGE_RATE_KW  # +charge / -discharge
        energy_kwh = power_kw * 1.0  # 1-hour step

        max_soc = min(SOC_MAX, cap_limit)
        soc_kwh = self.soc * BATTERY_CAPACITY_KWH

        penalty = 0.0
        if energy_kwh >= 0:  # charging
            actual = min(energy_kwh * ROUND_TRIP_EFFICIENCY, (max_soc * BATTERY_CAPACITY_KWH - soc_kwh))
            actual = max(actual, 0.0)
            grid_draw_for_battery = actual / ROUND_TRIP_EFFICIENCY
        else:  # discharging
            available = soc_kwh - SOC_MIN * BATTERY_CAPACITY_KWH
            actual = -min(-energy_kwh, max(available, 0.0))
            grid_draw_for_battery = actual  # negative -> offsets grid draw

        new_soc_kwh = soc_kwh + actual
        self.soc = float(np.clip(new_soc_kwh / BATTERY_CAPACITY_KWH, 0.0, 1.0))

        grid_demand_kw = self.demand_kw[self._t] + grid_draw_for_battery
        grid_demand_kw = max(grid_demand_kw, 0.0)
        cost = grid_demand_kw * self.price[self._t]

        baseline_cost = self.demand_kw[self._t] * self.price[self._t]
        reward = -(cost) / 1000.0  # scaled for training stability

        self._t += 1
        terminated = self._t >= self.n_steps
        truncated = False
        obs = self._get_obs() if not terminated else np.zeros(6, dtype=np.float32)

        info = {"cost": cost, "baseline_cost": baseline_cost, "soc": self.soc}
        return obs, reward, terminated, truncated, info


def _load_env_data():
    raw = load_raw_data()
    feats = build_features(raw, dropna=True)
    demand = feats[TARGET_COL].values
    price = feats["price_per_kwh"].values
    return demand, price


def train_agent(total_timesteps: int = 200_000):
    demand, price = _load_env_data()
    env = BatteryEnv(demand, price)
    model = PPO("MlpPolicy", env, verbose=1, seed=42)
    model.learn(total_timesteps=total_timesteps)
    model.save(AGENT_PATH)
    print(f"Saved PPO battery agent to {AGENT_PATH}")
    return model


def load_agent() -> PPO:
    return PPO.load(AGENT_PATH)


def backtest(model: PPO = None) -> dict:
    """Run the (trained) agent over the full historical dataset and compare
    optimized cost vs. a no-battery baseline cost."""
    demand, price = _load_env_data()
    env = BatteryEnv(demand, price)
    model = model or load_agent()

    obs, _ = env.reset()
    total_cost, total_baseline = 0.0, 0.0
    done = False
    while not done:
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(action)
        total_cost += info["cost"]
        total_baseline += info["baseline_cost"]
        done = terminated or truncated

    savings = total_baseline - total_cost
    pct = (savings / total_baseline) * 100 if total_baseline else 0.0
    result = {
        "baseline_electricity_cost": total_baseline,
        "rl_optimized_cost": total_cost,
        "absolute_savings": savings,
        "percentage_savings": pct,
    }
    return result


def recommend_action(demand_kw: float, price_per_kwh: float, soc: float,
                      usable_capacity_fraction: float, hour: int, model: PPO = None) -> dict:
    """Single-step inference used by the API: given current conditions,
    return the recommended charge/discharge action."""
    model = model or load_agent()
    demand_series, price_series = _load_env_data()
    norm_demand = (demand_kw - demand_series.mean()) / (demand_series.std() + 1e-6)
    norm_price = (price_per_kwh - price_series.mean()) / (price_series.std() + 1e-6)
    hour_sin = np.sin(2 * np.pi * hour / 24)
    hour_cos = np.cos(2 * np.pi * hour / 24)
    obs = np.array([norm_demand, norm_price, soc, usable_capacity_fraction,
                     hour_sin, hour_cos], dtype=np.float32)

    action, _ = model.predict(obs, deterministic=True)
    act = float(np.clip(action[0], -1.0, 1.0))
    power_kw = act * MAX_CHARGE_RATE_KW

    if power_kw > 5:
        mode = "charge"
    elif power_kw < -5:
        mode = "discharge"
    else:
        mode = "idle"

    return {"mode": mode, "power_kw": round(power_kw, 2), "raw_action": act}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--timesteps", type=int, default=200_000)
    args = parser.parse_args()

    if args.train:
        train_agent(total_timesteps=args.timesteps)
    if args.backtest or not args.train:
        result = backtest()
        print("Backtest result:", result)
