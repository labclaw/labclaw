"""Programmatic generation of all LabClaw demo and fixture datasets.

All datasets use numpy seed=42 for full reproducibility.  Run directly:

    python -m labclaw.demo.generate

This overwrites:
  src/labclaw/demo/data/neuroscience_behavior.csv   (200 rows)
  src/labclaw/demo/data/chemistry_reactions.csv     (150 rows)
  src/labclaw/demo/data/generic_experiment.csv      (100 rows)
  tests/fixtures/sample_lab/behavioral_session_001.csv (50 rows)
  tests/fixtures/sample_lab/behavioral_session_002.csv (50 rows)
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Output paths (absolute from package root)
# ---------------------------------------------------------------------------

_PKG_ROOT = Path(__file__).parent.parent.parent.parent  # repo root
_DEMO_DATA = Path(__file__).parent / "data"
_FIXTURES = _PKG_ROOT / "tests" / "fixtures" / "sample_lab"

SEED = 42


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Wrote {len(rows):>4} rows  ->  {path}")


# ---------------------------------------------------------------------------
# 1. Neuroscience behavior dataset  (200 rows)
# ---------------------------------------------------------------------------

# Embedded patterns
#  - stimulus_hz -> response_latency_ms  (r > 0.6, negative)
#  - 3 behavioral clusters: active / freezing / grooming
#  - Learning curve: accuracy improves over trials
#  - M003: genetic variant — lower baseline latency, higher velocity
#  - Zone effect: center -> higher velocity; periphery -> more freezing


def _generate_neuroscience() -> list[dict[str, Any]]:
    rng = np.random.default_rng(SEED)

    animals = ["M001", "M002", "M003", "M004"]
    n_trials = 50  # per animal  -> 200 total rows

    # Animal-level baseline offsets (M003 is the variant)
    baselines: dict[str, dict[str, float]] = {
        "M001": {"latency_base": 260.0, "velocity_base": 13.0, "freeze_base": 7.0},
        "M002": {"latency_base": 300.0, "velocity_base": 10.0, "freeze_base": 11.0},
        "M003": {"latency_base": 170.0, "velocity_base": 19.0, "freeze_base": 2.0},  # variant
        "M004": {"latency_base": 280.0, "velocity_base": 11.0, "freeze_base": 9.0},
    }

    hz_options = [4000, 8000, 12000, 16000]
    zones = ["center", "periphery", "corner"]
    zone_weights = [0.50, 0.35, 0.15]

    # Stimulus types cycle deterministically
    stim_types = ["tone", "light", "tone_light"]

    rows: list[dict[str, Any]] = []
    session_counter = 1

    for animal_id in animals:
        bl = baselines[animal_id]
        for trial in range(1, n_trials + 1):
            hz = hz_options[(trial - 1) % len(hz_options)]

            # --- stimulus effect on latency (strong negative correlation) ---
            # latency = base - 0.01 * hz + noise  => r > 0.6
            hz_effect = (hz - 4000) / 1000.0  # 0 .. 12
            latency = bl["latency_base"] - 10.0 * hz_effect + rng.normal(0, 12)
            latency = float(np.clip(latency, 80, 480))

            # --- learning curve: accuracy improves over trials ---
            # logistic growth from ~60% at trial 1 to ~90% at trial 50
            p_correct = 0.60 + 0.30 * (1 - math.exp(-0.07 * trial))
            correct = int(rng.random() < p_correct)

            # --- zone assignment ---
            zone = rng.choice(zones, p=zone_weights)

            # --- velocity (higher in center, lower in corner) ---
            zone_vel_mod = {"center": 1.15, "periphery": 1.0, "corner": 0.65}[zone]
            velocity = float(
                np.clip(
                    bl["velocity_base"] * zone_vel_mod + rng.normal(0, 1.5),
                    1.0,
                    35.0,
                )
            )
            distance = float(np.clip(velocity * rng.uniform(8, 18), 10, 500))

            # --- freezing (higher in periphery and corner) ---
            zone_freeze_mod = {"center": 0.7, "periphery": 1.0, "corner": 1.5}[zone]
            freezing = float(
                np.clip(
                    bl["freeze_base"] * zone_freeze_mod + rng.normal(0, 2),
                    0.0,
                    60.0,
                )
            )

            # --- rearing / grooming (anti-correlated with velocity) ---
            rearing = int(np.clip(rng.poisson(max(0.5, 20 - velocity)), 0, 35))
            grooming = float(np.clip(rng.exponential(max(1, 30 - velocity)), 0, 60))

            stim_type = stim_types[(trial - 1) % len(stim_types)]
            timestamp = f"2026-01-{(session_counter % 28) + 1:02d}T09:{trial % 60:02d}:00"

            rows.append(
                {
                    "session_id": session_counter,
                    "animal_id": animal_id,
                    "trial_num": trial,
                    "timestamp": timestamp,
                    "stimulus_type": stim_type,
                    "stimulus_hz": hz,
                    "response_latency_ms": round(latency, 1),
                    "correct": correct,
                    "velocity_cm_s": round(velocity, 2),
                    "distance_cm": round(distance, 1),
                    "freezing_pct": round(freezing, 1),
                    "rearing_count": rearing,
                    "grooming_s": round(grooming, 1),
                    "zone": zone,
                }
            )
            session_counter += 1

    return rows


# ---------------------------------------------------------------------------
# 2. Chemistry reactions dataset  (150 rows)
# ---------------------------------------------------------------------------

# Embedded patterns
#  - yield peaks at temperature=65, pressure=200, catalyst=50 (Gaussian surface)
#  - catalyst_mg positively correlates with yield; negatively with purity
#  - solvent "ethanol" > "water" > "dmso"
#  - pH < 4.0 -> byproduct_pct spikes
#  - temperature x pressure interaction effect


def _gaussian_yield(temp: float, pres: float, cat: float) -> float:
    """3-D Gaussian yield surface peaking at T=65, P=200, cat=50."""
    t_term = ((temp - 65) / 20) ** 2
    p_term = ((pres - 200) / 80) ** 2
    c_term = ((cat - 50) / 25) ** 2
    return 90.0 * math.exp(-0.5 * (t_term + p_term + c_term))


def _generate_chemistry() -> list[dict[str, Any]]:
    rng = np.random.default_rng(SEED)

    solvents = ["ethanol", "water", "dmso"]
    solvent_bonus = {"ethanol": 8.0, "water": 0.0, "dmso": -5.0}

    rows: list[dict[str, Any]] = []

    # Grid exploration + random exploration
    temps = list(range(40, 100, 10))      # 6 levels
    pressures = [100, 150, 200, 250, 300]  # 5 levels

    exp_id = 1

    # -- Structured grid (first 90 rows: temp x pressure x 3 solvents) --
    # Catalyst is kept in 5–60 range so that more catalyst monotonically
    # increases yield (positive correlation), while still hurting purity.
    for temp in temps:
        for pres in pressures:
            for solvent in solvents:
                cat = float(rng.integers(5, 61))
                base_yield = _gaussian_yield(float(temp), float(pres), cat)
                bonus = solvent_bonus[solvent]

                # temperature x pressure interaction
                interaction = 0.05 * (temp - 65) * (pres - 200) / 1000.0

                yield_pct = float(
                    np.clip(base_yield + bonus + interaction + rng.normal(0, 3), 5, 98)
                )

                # purity negatively correlated with catalyst
                purity_pct = float(
                    np.clip(98.0 - 0.25 * cat + rng.normal(0, 1.5), 50, 99)
                )

                # pH determined by conditions
                ph_base = 6.5 + rng.normal(0, 0.3)
                if pres > 220 and temp > 70:
                    ph_base -= rng.uniform(2.5, 3.5)  # drives pH below 4
                ph_final = float(np.clip(ph_base, 1.5, 9.0))

                # byproduct spikes below pH 4
                if ph_final < 4.0:
                    byproduct_pct = float(np.clip(rng.uniform(15, 45), 0, 50))
                else:
                    byproduct_pct = float(np.clip(rng.exponential(2.0), 0, 15))

                reaction_time = float(rng.integers(30, 120))
                color_index = float(
                    np.clip(0.9 - 0.003 * (temp - 40) + rng.normal(0, 0.03), 0.1, 1.0)
                )

                rows.append(
                    {
                        "experiment_id": exp_id,
                        "temperature_c": float(temp),
                        "pressure_kpa": float(pres),
                        "catalyst_mg": round(cat, 1),
                        "solvent": solvent,
                        "reaction_time_min": round(reaction_time, 0),
                        "yield_pct": round(yield_pct, 1),
                        "purity_pct": round(purity_pct, 1),
                        "byproduct_pct": round(byproduct_pct, 1),
                        "pH_final": round(ph_final, 2),
                        "color_index": round(color_index, 3),
                    }
                )
                exp_id += 1

    # -- Random exploration (remaining rows to reach 150) --
    remaining = 150 - len(rows)
    for _ in range(remaining):
        temp = float(rng.integers(35, 100))
        pres = float(rng.choice([100, 150, 200, 250, 300]))
        cat = float(rng.integers(5, 61))
        solvent = str(rng.choice(solvents))

        base_yield = _gaussian_yield(temp, pres, cat)
        bonus = solvent_bonus[solvent]
        interaction = 0.05 * (temp - 65) * (pres - 200) / 1000.0
        yield_pct = float(np.clip(base_yield + bonus + interaction + rng.normal(0, 4), 5, 98))
        purity_pct = float(np.clip(98.0 - 0.25 * cat + rng.normal(0, 2), 50, 99))
        ph_base = 6.5 + rng.normal(0, 0.4)
        if pres > 220 and temp > 70:
            ph_base -= rng.uniform(2.0, 3.5)
        ph_final = float(np.clip(ph_base, 1.5, 9.0))
        if ph_final < 4.0:
            byproduct_pct = float(np.clip(rng.uniform(12, 45), 0, 50))
        else:
            byproduct_pct = float(np.clip(rng.exponential(2.0), 0, 15))
        reaction_time = float(rng.integers(20, 150))
        color_index = float(np.clip(0.9 - 0.003 * (temp - 40) + rng.normal(0, 0.04), 0.1, 1.0))

        rows.append(
            {
                "experiment_id": exp_id,
                "temperature_c": temp,
                "pressure_kpa": pres,
                "catalyst_mg": round(cat, 1),
                "solvent": solvent,
                "reaction_time_min": round(reaction_time, 0),
                "yield_pct": round(yield_pct, 1),
                "purity_pct": round(purity_pct, 1),
                "byproduct_pct": round(byproduct_pct, 1),
                "pH_final": round(ph_final, 2),
                "color_index": round(color_index, 3),
            }
        )
        exp_id += 1

    return rows


# ---------------------------------------------------------------------------
# 3. Generic experiment dataset  (100 rows)
# ---------------------------------------------------------------------------

# Embedded patterns
#  - treatment_A > control > treatment_B for measurement_1
#  - measurement_2 increases over time_points (linear trend)
#  - measurement_1 and measurement_3 correlated (r~0.7)


def _generate_generic() -> list[dict[str, Any]]:
    rng = np.random.default_rng(SEED)

    groups = ["control", "treatment_A", "treatment_B"]
    group_means: dict[str, float] = {
        "control": 50.0,
        "treatment_A": 65.0,
        "treatment_B": 38.0,
    }
    n_replicates = 4
    n_time_points = 8  # per group per replicate -> 4 * 3 * 8 = 96; pad to 100

    rows: list[dict[str, Any]] = []
    sample_counter = 1

    for group in groups:
        mu1 = group_means[group]
        for rep in range(1, n_replicates + 1):
            for tp in range(1, n_time_points + 1):
                # measurement_1: group effect + noise
                m1 = float(np.clip(mu1 + rng.normal(0, 5), 10, 100))

                # measurement_2: time trend (global, all groups)
                m2 = float(np.clip(20.0 + 4.0 * tp + rng.normal(0, 3), 0, 100))

                # measurement_3: correlated with m1 (r ~ 0.7)
                shared = rng.normal(0, 1)
                m3 = float(
                    np.clip(0.7 * (m1 - mu1) + 5 * shared + mu1 * 0.8 + rng.normal(0, 4), 5, 100)
                )

                quality = float(np.clip(rng.beta(8, 2) * 100, 50, 100))

                rows.append(
                    {
                        "sample_id": f"S{sample_counter:03d}",
                        "group": group,
                        "replicate": rep,
                        "measurement_1": round(m1, 2),
                        "measurement_2": round(m2, 2),
                        "measurement_3": round(m3, 2),
                        "time_point": tp,
                        "quality_score": round(quality, 1),
                    }
                )
                sample_counter += 1

    # Pad to exactly 100 rows with 4 extra control/treatment_A rows
    extras = [
        ("control", 1, 9),
        ("treatment_A", 1, 9),
        ("control", 2, 9),
        ("treatment_A", 2, 9),
    ]
    for group, rep, tp in extras:
        mu1 = group_means[group]
        m1 = float(np.clip(mu1 + rng.normal(0, 5), 10, 100))
        m2 = float(np.clip(20.0 + 4.0 * tp + rng.normal(0, 3), 0, 100))
        shared = rng.normal(0, 1)
        m3 = float(np.clip(0.7 * (m1 - mu1) + 5 * shared + mu1 * 0.8 + rng.normal(0, 4), 5, 100))
        quality = float(np.clip(rng.beta(8, 2) * 100, 50, 100))
        rows.append(
            {
                "sample_id": f"S{sample_counter:03d}",
                "group": group,
                "replicate": rep,
                "measurement_1": round(m1, 2),
                "measurement_2": round(m2, 2),
                "measurement_3": round(m3, 2),
                "time_point": tp,
                "quality_score": round(quality, 1),
            }
        )
        sample_counter += 1

    return rows


# ---------------------------------------------------------------------------
# 4. Fixture: behavioral_session_001.csv  (50 rows)
# ---------------------------------------------------------------------------

# Schema: timestamp, x, y, speed, angle, zone, animal_id
# Patterns:
#  - speed-distance correlation r > 0.3
#  - 2 anomaly rows (speed=999.0) for anomaly detection tests
#  - zone assignment matches position (center / periphery / corner)


def _zone_from_xy(x: float, y: float) -> str:
    """Determine zone from arena coordinates (300x300 arena, center 150,200)."""
    cx, cy = 150.0, 200.0
    dx, dy = abs(x - cx), abs(y - cy)
    dist = math.sqrt(dx**2 + dy**2)
    if x < 60 or x > 240 or y < 60 or y > 285:
        return "corner"
    if dist < 55:
        return "center"
    return "periphery"


def _generate_fixture_session(
    animal_id: str,
    date: str,
    rng: np.random.Generator,
    n_rows: int = 50,
) -> list[dict[str, Any]]:
    """Generate one behavioral session fixture CSV with embedded speed-distance signal.

    Speed is positively correlated with distance from arena center (r > 0.3):
    animals explore faster when they are further from the home base.
    """
    rows: list[dict[str, Any]] = []

    # Arena size 300x300; center of arena
    cx, cy = 150.0, 200.0
    x, y = cx + rng.normal(0, 10), cy + rng.normal(0, 10)

    # Two fixed anomaly indices
    anomaly_indices = {10, 24}

    for i in range(n_rows):
        if i in anomaly_indices:
            # Anomaly: speed sensor glitch
            rows.append(
                {
                    "timestamp": f"{date}T10:00:{i:02d}",
                    "x": round(x, 3),
                    "y": round(y, 3),
                    "speed": 999.0,
                    "angle": round(rng.uniform(0, 360), 3),
                    "zone": _zone_from_xy(x, y),
                    "animal_id": animal_id,
                }
            )
            continue

        # Distance from center drives speed (embedded positive correlation)
        dist_from_center = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        # speed = 5 + 0.18 * dist + noise  => r > 0.3 with n=48 clean rows
        speed = float(np.clip(5.0 + 0.18 * dist_from_center + rng.normal(0, 2.5), 1.0, 30.0))

        angle = rng.uniform(0, 360)
        dx = speed * 0.9 * math.cos(math.radians(angle))
        dy = speed * 0.9 * math.sin(math.radians(angle))
        x = float(np.clip(x + dx, 50.0, 250.0))
        y = float(np.clip(y + dy, 50.0, 300.0))

        rows.append(
            {
                "timestamp": f"{date}T10:00:{i:02d}",
                "x": round(x, 3),
                "y": round(y, 3),
                "speed": round(speed, 3),
                "angle": round(angle, 3),
                "zone": _zone_from_xy(x, y),
                "animal_id": animal_id,
            }
        )

    return rows


def _generate_fixtures() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rng = np.random.default_rng(SEED)
    session_001 = _generate_fixture_session("mouse_01", "2026-01-15", rng, n_rows=50)
    session_002 = _generate_fixture_session("mouse_02", "2026-01-16", rng, n_rows=50)
    return session_001, session_002


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def generate_all() -> None:
    """Generate all demo datasets and fixture files."""
    print("Generating LabClaw demo datasets (seed=42) ...")

    neuro = _generate_neuroscience()
    _write_csv(_DEMO_DATA / "neuroscience_behavior.csv", neuro)

    chem = _generate_chemistry()
    _write_csv(_DEMO_DATA / "chemistry_reactions.csv", chem)

    generic = _generate_generic()
    _write_csv(_DEMO_DATA / "generic_experiment.csv", generic)

    fix001, fix002 = _generate_fixtures()
    _write_csv(_FIXTURES / "behavioral_session_001.csv", fix001)
    _write_csv(_FIXTURES / "behavioral_session_002.csv", fix002)

    print("Done.")


if __name__ == "__main__":
    generate_all()
