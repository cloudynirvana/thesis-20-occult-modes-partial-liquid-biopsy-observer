#!/usr/bin/env python3
"""Hybrid occult-mode switches under full versus sparse delayed observers.

Thesis #20. The mode names are the hybrid locations of Thesis #4. They are
not re-derived here. The question is observer design: which of those switches
a full state schedule can still separate once the map is replaced by a sparse,
delayed, thresholded scalar. The scalar is a liquid-biopsy-style partial
observer. It is not a ctDNA assay and not a clinical limit of detection.

Seed 20260921. Research only.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from numpy.random import Generator, SeedSequence

ROOT = Path(__file__).resolve().parent
FIG = ROOT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

SEED = 20260921
DT = 0.05
T_END = 140.0
TAU_TRUE = 30.0
X0 = np.array([0.08, 0.55, 0.40], dtype=float)  # burden, cycling class, vascular class
N_REP = 400
TAU_GRID = np.arange(12.0, 48.0 + 1e-9, 2.0)
TAU_STEP = 0.5
CHI2_95_HALF = 1.920729  # 0.5 * chi^2_1 (0.95)

# Predeclared calls. Fixed before the Monte Carlo is read as a result.
ERR_TOL = 0.15
TAU_SD_TOL = 8.0
PSI_SD_TOL = 0.25

MODES = ("P", "Q", "A", "I")
MODE_INDEX = {m: i for i, m in enumerate(MODES)}
PAIRS = (("P", "Q"), ("P", "A"), ("P", "I"), ("Q", "A"), ("Q", "I"), ("A", "I"))

# Primary burden balance for immune-held latency. Angiogenic pause sits at 0.20.
# A matched arm sets this equal to 0.20 so the burden laws coincide.
B_I_PRIMARY = 0.15
B_A = 0.20


def targets(
    mode: str,
    b_I: float,
    match_burden: bool = False,
) -> tuple[float, float, float, float, float, float]:
    """Return (r_b, b_star, decay, c_star, v_star, relax).

    decay > 0 replaces the logistic with db = -decay * b (quiescence).
    Rates are dimensionless toy constants, not fitted biological constants.
    match_burden copies the angiogenic burden law onto the immune-held mode
    and leaves the cycling and vascular targets alone.
    """
    if mode == "P":
        return 0.045, 1.00, 0.0, 0.80, 0.65, 0.18
    if mode == "Q":
        return 0.0, 0.0, 0.018, 0.06, 0.65, 0.22
    if mode == "A":
        return 0.06, B_A, 0.0, 0.78, 0.07, 0.18
    if mode == "I":
        if match_burden:
            return 0.06, B_A, 0.0, 0.42, 0.58, 0.18
        return 0.05, b_I, 0.0, 0.42, 0.58, 0.18
    raise KeyError(mode)


def field(
    x: np.ndarray,
    mode: str,
    b_I: float,
    psi: float | None = None,
    match_burden: bool = False,
) -> np.ndarray:
    """Continuous vector field. psi interpolates A toward I after the switch."""
    b, c, v = x
    if psi is None or mode not in ("A", "I"):
        r_b, b_star, decay, c_star, v_star, relax = targets(mode, b_I, match_burden)
        if decay > 0.0:
            db = -decay * b
        else:
            db = r_b * b * (1.0 - b / b_star)
        dc = relax * (c_star - c)
        dv = relax * (v_star - v)
        return np.array([db, dc, dv], dtype=float)

    # Convex combination of the two pause fields. Used only for the local
    # contrast parameter. It is not a sixth biological mode.
    fA = field(x, "A", b_I, None, match_burden)
    fI = field(x, "I", b_I, None, match_burden)
    return (1.0 - psi) * fA + psi * fI


def simulate(
    tau: float,
    mode: str,
    b_I: float,
    lag: float,
    psi: float | None = None,
    match_burden: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """Integrate from 0 to T_END. Mode P until tau, then `mode`.

    Returns times and state rows (b, c, v, f). f is a linear lag of b when
    lag > 0, and a copy of b when lag == 0.
    """
    n = int(round(T_END / DT))
    traj = np.empty((n + 1, 4), dtype=float)
    x = X0.copy()
    f = float(X0[0])
    traj[0, :3] = x
    traj[0, 3] = f
    post = mode
    for k in range(n):
        t = k * DT

        def rhs(z: np.ndarray, tt: float) -> np.ndarray:
            active = "P" if tt < tau else post
            use_psi = None if tt < tau else psi
            return field(z, active, b_I, use_psi, match_burden)

        k1 = rhs(x, t)
        k2 = rhs(x + 0.5 * DT * k1, t + 0.5 * DT)
        k3 = rhs(x + 0.5 * DT * k2, t + 0.5 * DT)
        k4 = rhs(x + DT * k3, t + DT)
        x = x + (DT / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
        x[0] = max(x[0], 1e-12)
        if lag <= 0.0:
            f = float(x[0])
        else:
            # Exact step for f' = (b_new - f) / lag, b held at the new value.
            # A one-step lag, not a clearance half-life and not a dose.
            decay = np.exp(-DT / lag)
            f = float(x[0]) + (f - float(x[0])) * decay
        traj[k + 1, :3] = x
        traj[k + 1, 3] = f
    times = np.linspace(0.0, T_END, n + 1)
    return times, traj


def sample_rows(traj: np.ndarray, times_obs: np.ndarray, cols: tuple[int, ...]) -> np.ndarray:
    idx = np.rint(times_obs / DT).astype(int)
    return traj[idx][:, cols]


OBSERVERS = {
    "full": {
        "label": "Full state schedule",
        "dt_obs": 2.0,
        "cols": (0, 1, 2),
        "sigma": np.array([0.02, 0.025, 0.025]),
        "lag": 0.0,
        "floor": None,
    },
    "burden": {
        "label": "Dense burden-only",
        "dt_obs": 2.0,
        "cols": (0,),
        "sigma": np.array([0.02]),
        "lag": 0.0,
        "floor": None,
    },
    "liquid": {
        "label": "Sparse delayed scalar",
        "dt_obs": 20.0,
        "cols": (3,),
        "sigma": np.array([0.03]),
        "lag": 14.0,
        "floor": 0.10,
    },
}


def obs_times(spec: dict) -> np.ndarray:
    return np.arange(0.0, T_END + 1e-9, spec["dt_obs"])


def log_phi_stable(z: np.ndarray) -> np.ndarray:
    return -0.5 * z * z - 0.5 * np.log(2.0 * np.pi)


def log_Phi(z: np.ndarray) -> np.ndarray:
    """Log of the standard normal cdf, stable enough for a censored likelihood."""
    z = np.asarray(z, dtype=float)
    out = np.empty(z.shape, dtype=float)
    flat = z.ravel()
    dest = out.ravel()
    for i, val in enumerate(flat):
        if val >= 8.0:
            dest[i] = 0.0
        elif val <= -18.0:
            dest[i] = log_phi_stable(np.array(val)) - np.log(-val)
        else:
            # 0.5 * erfc(-z / sqrt(2))
            from math import erfc, log, sqrt

            p = 0.5 * erfc(-val / sqrt(2.0))
            dest[i] = -700.0 if p <= 0.0 else log(p)
    return out


def gaussian_ll(y: np.ndarray, mu: np.ndarray, sigma: np.ndarray) -> float:
    r = (y - mu) / sigma
    return float(np.sum(-0.5 * r * r - np.log(sigma) - 0.5 * np.log(2.0 * np.pi)))


def tobit_ll(y: np.ndarray, mu: np.ndarray, sigma: np.ndarray, floor: float) -> float:
    cens = y < floor
    total = 0.0
    if np.any(~cens):
        total += gaussian_ll(y[~cens], mu[~cens], sigma[~cens])
    if np.any(cens):
        alpha = (floor - mu[cens]) / sigma[cens]
        total += float(np.sum(log_Phi(alpha)))
    return total


def tobit_info_factor(mu: float, sigma: float, floor: float) -> float:
    """Fisher information for the mean of one left-censored Gaussian draw."""
    alpha = (floor - mu) / sigma
    logphi = float(log_phi_stable(np.array(alpha)))
    phi = float(np.exp(logphi))
    p_cens = float(np.exp(log_Phi(np.array(alpha))))
    p_obs = float(np.exp(log_Phi(np.array(-alpha))))
    extra = 0.0 if p_cens < 1e-14 else (phi * phi) / p_cens
    return (p_obs + extra) / (sigma * sigma)


def cache_means(
    b_I: float,
    lag: float,
    spec: dict,
    match_burden: bool = False,
) -> dict[str, dict[float, np.ndarray]]:
    times = obs_times(spec)
    cols = spec["cols"]
    out: dict[str, dict[float, np.ndarray]] = {}
    for mode in MODES:
        out[mode] = {}
        for tau in TAU_GRID:
            _, traj = simulate(float(tau), mode, b_I, lag, match_burden=match_burden)
            out[mode][float(tau)] = sample_rows(traj, times, cols)
    return out


def nearest_tau(tau: float) -> float:
    return float(TAU_GRID[np.argmin(np.abs(TAU_GRID - tau))])


def classify(
    rng: Generator,
    means: dict[str, dict[float, np.ndarray]],
    spec: dict,
    known_tau: bool,
) -> dict:
    sigma = spec["sigma"]
    floor = spec["floor"]
    n_t = next(iter(means["P"].values())).shape[0]
    sig = np.broadcast_to(sigma, (n_t, sigma.size))
    labels = list(MODES)
    conf = np.zeros((4, 4), dtype=int)
    ties = 0
    tau_hat = {m: [] for m in MODES}
    pair_wrong = {f"{a}|{b}": [0, 0] for a, b in PAIRS}  # wrong, total

    for truth in labels:
        mu_true = means[truth][nearest_tau(TAU_TRUE)]
        noise = rng.normal(0.0, 1.0, size=(N_REP, mu_true.shape[0], mu_true.shape[1]))
        draws = mu_true[None, :, :] + noise * sigma[None, None, :]
        for r in range(N_REP):
            y = draws[r]
            scores = []
            hats = []
            grid = [nearest_tau(TAU_TRUE)] if known_tau else [float(t) for t in TAU_GRID]
            for mode in labels:
                best = -1e300
                best_tau = grid[0]
                for tau in grid:
                    mu = means[mode][tau]
                    if floor is None:
                        ll = gaussian_ll(y, mu, sig)
                    else:
                        ll = tobit_ll(y, mu, sig, floor)
                    if ll > best:
                        best = ll
                        best_tau = tau
                scores.append(best)
                hats.append(best_tau)
            scores_a = np.array(scores)
            order = np.argsort(scores_a)
            top = int(order[-1])
            second = int(order[-2])
            if abs(scores_a[top] - scores_a[second]) < 1e-8:
                ties += 1
                pred = -1
            else:
                pred = top
            ti = MODE_INDEX[truth]
            if pred < 0:
                # Unresolved tie counts against the truth, not as a fifth class.
                conf[ti, ti] += 0
            else:
                conf[ti, pred] += 1
            # Switch-time estimate conditional on the true mode.
            tau_hat[truth].append(hats[MODE_INDEX[truth]])

            for a, b in PAIRS:
                if truth not in (a, b):
                    continue
                ia, ib = MODE_INDEX[a], MODE_INDEX[b]
                pair_wrong[f"{a}|{b}"][1] += 1
                if abs(scores_a[ia] - scores_a[ib]) < 1e-8 or scores_a[ia] == scores_a[ib]:
                    pair_wrong[f"{a}|{b}"][0] += 1
                else:
                    chosen = a if scores_a[ia] > scores_a[ib] else b
                    if chosen != truth:
                        pair_wrong[f"{a}|{b}"][0] += 1

    # 4-way error: off-diagonal plus ties (ties were not added to the diagonal).
    correct = int(np.trace(conf))
    total = N_REP * 4
    err = 1.0 - correct / total
    pair_err = {}
    for key, (wrong, tot) in pair_wrong.items():
        pair_err[key] = wrong / tot
    tau_stats = {}
    for mode, hats in tau_hat.items():
        arr = np.array(hats, dtype=float)
        tau_stats[mode] = {
            "mean": float(arr.mean()),
            "sd": float(arr.std(ddof=1)),
            "within_tol": float(np.mean(np.abs(arr - TAU_TRUE) <= TAU_SD_TOL)),
        }
    return {
        "confusion": conf.tolist(),
        "four_way_error": err,
        "ties": ties,
        "pairwise_error": pair_err,
        "tau_hat": tau_stats,
        "n_rep": N_REP,
    }


def fisher_tau(mode: str, b_I: float, spec: dict, match_burden: bool = False) -> dict:
    lag = spec["lag"]
    times = obs_times(spec)
    cols = spec["cols"]
    sigma = spec["sigma"]
    floor = spec["floor"]
    _, traj0 = simulate(TAU_TRUE, mode, b_I, lag, match_burden=match_burden)
    _, traj_p = simulate(TAU_TRUE + TAU_STEP, mode, b_I, lag, match_burden=match_burden)
    _, traj_m = simulate(TAU_TRUE - TAU_STEP, mode, b_I, lag, match_burden=match_burden)
    mu = sample_rows(traj0, times, cols)
    dp = sample_rows(traj_p, times, cols)
    dm = sample_rows(traj_m, times, cols)
    sens = (dp - dm) / (2.0 * TAU_STEP)
    info = 0.0
    for i in range(mu.shape[0]):
        for j in range(mu.shape[1]):
            if floor is None:
                factor = 1.0 / float(sigma[j] ** 2)
            else:
                factor = tobit_info_factor(float(mu[i, j]), float(sigma[j]), floor)
            info += factor * float(sens[i, j] ** 2)
    sd = float("inf") if info <= 0.0 else float(1.0 / np.sqrt(info))
    return {"information": info, "cr_sd": sd, "mode": mode}


def fisher_psi(b_I: float, spec: dict, psi0: float = 0.0, match_burden: bool = False) -> dict:
    """Local information for the A→I contrast at psi0, switch time fixed."""
    lag = spec["lag"]
    times = obs_times(spec)
    cols = spec["cols"]
    sigma = spec["sigma"]
    floor = spec["floor"]
    h = 0.02

    def mean_at(psi: float) -> np.ndarray:
        _, traj = simulate(TAU_TRUE, "A", b_I, lag, psi=psi, match_burden=match_burden)
        return sample_rows(traj, times, cols)

    mu = mean_at(psi0)
    sens = (mean_at(psi0 + h) - mean_at(psi0 - h)) / (2.0 * h)
    info = 0.0
    for i in range(mu.shape[0]):
        for j in range(mu.shape[1]):
            if floor is None:
                factor = 1.0 / float(sigma[j] ** 2)
            else:
                factor = tobit_info_factor(float(mu[i, j]), float(sigma[j]), floor)
            info += factor * float(sens[i, j] ** 2)
    sd = float("inf") if info <= 0.0 else float(1.0 / np.sqrt(info))
    return {"information": info, "cr_sd": sd, "psi0": psi0}


def noise_free_profile(mode: str, means: dict, spec: dict) -> dict:
    """Plug-in profile of tau. Sub-floor latent means are entered as censored."""
    mu_true = means[mode][nearest_tau(TAU_TRUE)]
    sigma = spec["sigma"]
    floor = spec["floor"]
    n_t = mu_true.shape[0]
    sig = np.broadcast_to(sigma, (n_t, sigma.size))
    if floor is None:
        y = mu_true.copy()
        ll_true = gaussian_ll(y, mu_true, sig)
    else:
        y = mu_true.copy()
        y[mu_true < floor] = floor - 1.0  # mark censored; value unused
        ll_true = tobit_ll(y, mu_true, sig, floor)
    inside = []
    for tau in TAU_GRID:
        mu = means[mode][float(tau)]
        if floor is None:
            ll = gaussian_ll(y, mu, sig)
        else:
            ll = tobit_ll(y, mu, sig, floor)
        if ll_true - ll <= CHI2_95_HALF + 1e-8:
            inside.append(float(tau))
    if not inside:
        width = None
    else:
        width = float(max(abs(t - TAU_TRUE) for t in inside))
    return {
        "grid_points_inside": inside,
        "halfwidth": width,
        "whole_grid": len(inside) == len(TAU_GRID),
    }


def terminal_table(b_I: float) -> dict:
    rows = {}
    for mode in MODES:
        _, traj = simulate(TAU_TRUE, mode, b_I, lag=14.0)
        # state at switch and at horizon
        i_tau = int(round(TAU_TRUE / DT))
        rows[mode] = {
            "before_switch": [float(v) for v in traj[i_tau - 1, :3]],
            "at_horizon": [float(v) for v in traj[-1]],
        }
    return rows


def lag_sweep(b_I: float, rng: Generator) -> list[dict]:
    rows = []
    for lag in (0.0, 7.0, 14.0, 28.0):
        spec = dict(OBSERVERS["liquid"])
        spec["lag"] = lag
        means = cache_means(b_I, lag, spec)
        classified = classify(rng, means, spec, known_tau=False)
        fish = fisher_tau("A", b_I, spec)
        rows.append(
            {
                "lag": lag,
                "pairwise_error": classified["pairwise_error"],
                "four_way_error": classified["four_way_error"],
                "tau_cr_sd_A": fish["cr_sd"],
                "tau_hat_sd_A": classified["tau_hat"]["A"]["sd"],
            }
        )
    return rows


def json_ready(obj):
    if isinstance(obj, dict):
        return {k: json_ready(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_ready(v) for v in obj]
    if isinstance(obj, float):
        if np.isinf(obj):
            return None
        return obj
    if isinstance(obj, (np.floating,)):
        val = float(obj)
        return None if np.isinf(val) else val
    if isinstance(obj, (np.integer,)):
        return int(obj)
    return obj


def plot_trajectories(b_I: float) -> None:
    colors = {"P": "#0072B2", "Q": "#E69F00", "A": "#009E73", "I": "#CC79A7"}
    fig, axes = plt.subplots(2, 2, figsize=(8.4, 6.2), sharex=True)
    series = {}
    for mode in MODES:
        _, traj = simulate(TAU_TRUE, mode, b_I, lag=14.0)
        series[mode] = traj
    times = np.linspace(0.0, T_END, traj.shape[0])
    names = [(0, "Burden b"), (1, "Cycling class c"), (2, "Vascular class v"), (3, "Lagged scalar f")]
    for ax, (col, title) in zip(axes.ravel(), names):
        for mode in MODES:
            ax.plot(times, series[mode][:, col], color=colors[mode], lw=1.6, label=mode)
        ax.axvline(TAU_TRUE, color="#666666", lw=0.7, ls="--")
        ax.set_title(title)
        ax.set_xlim(0, T_END)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    axes[1, 0].axhline(0.10, color="#999999", lw=0.7, ls=":")
    axes[1, 1].axhline(0.10, color="#999999", lw=0.7, ls=":")
    axes[1, 0].set_xlabel("Toy time")
    axes[1, 1].set_xlabel("Toy time")
    axes[0, 0].legend(frameon=False, ncol=4, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "fig_4_1_trajectories.png", dpi=160)
    plt.close(fig)


def plot_confusion(results_by_obs: dict) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(9.2, 3.3))
    for ax, key in zip(axes, ("full", "burden", "liquid")):
        conf = np.array(results_by_obs[key]["profiled"]["confusion"], dtype=float)
        # ties are missing from the row sum; show counts as stored
        im = ax.imshow(conf, cmap="Blues", vmin=0, vmax=N_REP)
        ax.set_xticks(range(4), MODES)
        ax.set_yticks(range(4), MODES)
        ax.set_xlabel("Called")
        ax.set_title(OBSERVERS[key]["label"])
        for i in range(4):
            for j in range(4):
                ax.text(j, i, f"{int(conf[i, j])}", ha="center", va="center", fontsize=8, color="#111111")
    axes[0].set_ylabel("Truth")
    fig.tight_layout()
    fig.savefig(FIG / "fig_4_2_confusion.png", dpi=160)
    plt.close(fig)


def plot_pairwise(results_by_obs: dict) -> None:
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    labels = [f"{a} vs {b}" for a, b in PAIRS]
    x = np.arange(len(PAIRS))
    width = 0.25
    colors = {"full": "#0072B2", "burden": "#E69F00", "liquid": "#D55E00"}
    for k, key in enumerate(("full", "burden", "liquid")):
        vals = [results_by_obs[key]["profiled"]["pairwise_error"][f"{a}|{b}"] for a, b in PAIRS]
        ax.bar(x + (k - 1) * width, vals, width, color=colors[key], label=OBSERVERS[key]["label"])
    ax.axhline(ERR_TOL, color="#333333", lw=0.8, ls="--", label=f"tolerance {ERR_TOL:.2f}")
    ax.axhline(0.5, color="#999999", lw=0.6, ls=":")
    ax.set_xticks(x, labels, rotation=20, ha="right")
    ax.set_ylabel("Pairwise misclassification")
    ax.set_ylim(0, 0.65)
    ax.legend(frameon=False, fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIG / "fig_4_3_pairwise.png", dpi=160)
    plt.close(fig)


def plot_fisher(fisher: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.6))
    keys = ("full", "burden", "liquid")
    labels = [OBSERVERS[k]["label"] for k in keys]
    colors = ["#0072B2", "#E69F00", "#D55E00"]
    tau_sd = [fisher[k]["tau_A"]["cr_sd"] for k in keys]
    psi_sd = [fisher[k]["psi"]["cr_sd"] for k in keys]
    axes[0].bar(labels, tau_sd, color=colors)
    axes[0].axhline(TAU_SD_TOL, color="#333333", lw=0.8, ls="--")
    axes[0].set_ylabel("Cramér–Rao sd of switch time")
    axes[0].tick_params(axis="x", labelrotation=15)
    axes[1].bar(labels, [0 if v is None or np.isinf(v) else v for v in psi_sd], color=colors)
    axes[1].axhline(PSI_SD_TOL, color="#333333", lw=0.8, ls="--")
    axes[1].set_ylabel("Cramér–Rao sd of A–I contrast")
    axes[1].tick_params(axis="x", labelrotation=15)
    for ax in axes:
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIG / "fig_4_4_fisher.png", dpi=160)
    plt.close(fig)


def censor_rates(b_I: float) -> dict:
    spec = OBSERVERS["liquid"]
    times = obs_times(spec)
    floor = spec["floor"]
    out = {}
    for mode in MODES:
        _, traj = simulate(TAU_TRUE, mode, b_I, spec["lag"])
        mu = sample_rows(traj, times, spec["cols"])
        below = mu[:, 0] < floor
        out[mode] = {
            "n_times": int(times.size),
            "n_below_floor": int(np.sum(below)),
            "means": [float(v) for v in mu[:, 0]],
        }
    return out


def plot_matched(matched: dict) -> None:
    fig, ax = plt.subplots(figsize=(7.6, 3.8))
    labels = [f"{a} vs {b}" for a, b in PAIRS]
    x = np.arange(len(PAIRS))
    width = 0.25
    colors = {"full": "#0072B2", "burden": "#E69F00", "liquid": "#D55E00"}
    for k, key in enumerate(("full", "burden", "liquid")):
        vals = [matched[key]["pairwise_error"][f"{a}|{b}"] for a, b in PAIRS]
        ax.bar(x + (k - 1) * width, vals, width, color=colors[key], label=OBSERVERS[key]["label"])
    ax.axhline(ERR_TOL, color="#333333", lw=0.8, ls="--")
    ax.set_xticks(x, labels, rotation=20, ha="right")
    ax.set_ylabel("Pairwise misclassification")
    ax.set_ylim(0, 1.05)
    ax.set_title("Matched burden laws")
    ax.legend(frameon=False, fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIG / "fig_4_6_matched.png", dpi=160)
    plt.close(fig)


def plot_lag(rows: list[dict]) -> None:
    fig, ax1 = plt.subplots(figsize=(6.4, 3.8))
    lags = [r["lag"] for r in rows]
    err = [r["pairwise_error"]["A|I"] for r in rows]
    qerr = [r["pairwise_error"]["Q|A"] for r in rows]
    perr = [r["pairwise_error"]["P|Q"] for r in rows]
    ax1.plot(lags, err, "o-", color="#CC79A7", label="A vs I error")
    ax1.plot(lags, qerr, "s-", color="#009E73", label="Q vs A error")
    ax1.plot(lags, perr, "^-", color="#0072B2", label="P vs Q error")
    ax1.axhline(ERR_TOL, color="#333333", lw=0.8, ls="--")
    ax1.set_xlabel("Observer lag")
    ax1.set_ylabel("Pairwise misclassification")
    ax1.set_ylim(0, 0.7)
    ax2 = ax1.twinx()
    ax2.plot(lags, [r["tau_cr_sd_A"] for r in rows], "d--", color="#D55E00", label="CR sd of τ | A")
    ax2.set_ylabel("Cramér–Rao sd of τ")
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "fig_4_5_lag.png", dpi=160)
    plt.close(fig)


def call_flag(ok: bool) -> str:
    return "remains" if ok else "fails"


def main() -> None:
    ss = SeedSequence(SEED)
    streams = [Generator(np.random.PCG64(s)) for s in ss.spawn(8)]

    terminals = terminal_table(B_I_PRIMARY)
    plot_trajectories(B_I_PRIMARY)

    results_by_obs = {}
    fisher = {}
    profiles = {}
    for i, key in enumerate(("full", "burden", "liquid")):
        spec = OBSERVERS[key]
        means = cache_means(B_I_PRIMARY, spec["lag"], spec)
        known = classify(streams[i], means, spec, known_tau=True)
        # fresh stream so the profiled draw is not a continuation accident
        profiled = classify(streams[i + 3], means, spec, known_tau=False)
        results_by_obs[key] = {"known_tau": known, "profiled": profiled}
        fisher[key] = {
            "tau_A": fisher_tau("A", B_I_PRIMARY, spec),
            "tau_Q": fisher_tau("Q", B_I_PRIMARY, spec),
            "tau_P": fisher_tau("P", B_I_PRIMARY, spec),
            "psi": fisher_psi(B_I_PRIMARY, spec, 0.0),
        }
        profiles[key] = {mode: noise_free_profile(mode, means, spec) for mode in MODES}

    # Matched burden law: I uses A's burden vector field and keeps its own
    # cycling and vascular targets. This is the structural control.
    matched = {}
    matched_streams = [Generator(np.random.PCG64(s)) for s in SeedSequence(SEED + 1).spawn(3)]
    for i, key in enumerate(("full", "burden", "liquid")):
        spec = OBSERVERS[key]
        means = cache_means(B_I_PRIMARY, spec["lag"], spec, match_burden=True)
        classified = classify(matched_streams[i], means, spec, known_tau=False)
        matched[key] = {
            "pairwise_error": classified["pairwise_error"],
            "four_way_error": classified["four_way_error"],
            "confusion": classified["confusion"],
            "ties": classified["ties"],
            "psi": fisher_psi(B_I_PRIMARY, spec, 0.0, match_burden=True),
            "tau_A": fisher_tau("A", B_I_PRIMARY, spec, match_burden=True),
        }

    sweep = lag_sweep(B_I_PRIMARY, streams[6])

    cens = censor_rates(B_I_PRIMARY)
    plot_confusion(results_by_obs)
    plot_pairwise(results_by_obs)
    plot_fisher(fisher)
    plot_lag(sweep)
    plot_matched(matched)

    calls = {}
    for key in ("full", "burden", "liquid"):
        pe = results_by_obs[key]["profiled"]["pairwise_error"]
        calls[key] = {
            pair: call_flag(pe[f"{a}|{b}"] <= ERR_TOL) for pair, (a, b) in zip(
                [f"{a}|{b}" for a, b in PAIRS], PAIRS
            )
        }
        calls[key]["tau_A"] = call_flag(fisher[key]["tau_A"]["cr_sd"] <= TAU_SD_TOL)
        calls[key]["psi"] = call_flag(fisher[key]["psi"]["cr_sd"] <= PSI_SD_TOL)

    # Invariants used as a self-check, not as a biological claim.
    b_switch = terminals["A"]["before_switch"][0]
    assert abs(terminals["P"]["before_switch"][0] - b_switch) < 1e-9
    assert abs(terminals["Q"]["before_switch"][0] - b_switch) < 1e-9
    assert terminals["P"]["at_horizon"][0] > terminals["A"]["at_horizon"][0]
    assert terminals["Q"]["at_horizon"][1] < 0.2
    assert terminals["A"]["at_horizon"][1] > 0.6
    assert terminals["A"]["at_horizon"][2] < 0.2
    assert terminals["I"]["at_horizon"][2] > 0.4

    payload = {
        "seed": SEED,
        "n_rep": N_REP,
        "tau_true": TAU_TRUE,
        "t_end": T_END,
        "b_I_primary": B_I_PRIMARY,
        "b_A": B_A,
        "tolerances": {"pairwise_error": ERR_TOL, "tau_sd": TAU_SD_TOL, "psi_sd": PSI_SD_TOL},
        "observers": {
            k: {
                "label": v["label"],
                "dt_obs": v["dt_obs"],
                "n_times": int(obs_times(v).size),
                "sigma": [float(s) for s in v["sigma"]],
                "lag": v["lag"],
                "floor": v["floor"],
                "channels": ["b", "c", "v", "f"][c] if False else [["b", "c", "v", "f"][i] for i in v["cols"]],
            }
            for k, v in OBSERVERS.items()
        },
        "terminals": terminals,
        "classification": results_by_obs,
        "fisher": fisher,
        "profiles": profiles,
        "matched_burden": matched,
        "lag_sweep": sweep,
        "censor_rates": cens,
        "calls": calls,
    }
    text = json.dumps(json_ready(payload), indent=2)
    (ROOT / "results.json").write_text(text + "\n", encoding="utf-8")
    print(f"wrote {ROOT / 'results.json'} ({len(text)} bytes)")
    for key in ("full", "burden", "liquid"):
        pe = results_by_obs[key]["profiled"]["pairwise_error"]
        print(
            key,
            "4way",
            round(results_by_obs[key]["profiled"]["four_way_error"], 3),
            "AI",
            round(pe["A|I"], 3),
            "QA",
            round(pe["Q|A"], 3),
            "PQ",
            round(pe["P|Q"], 3),
            "tau",
            round(fisher[key]["tau_A"]["cr_sd"], 3),
            "psi",
            fisher[key]["psi"]["cr_sd"],
        )


if __name__ == "__main__":
    main()
