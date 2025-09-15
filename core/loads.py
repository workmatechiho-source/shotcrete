# core/loads.py
# ------------------------------------------------------------
# Load models for shotcrete support design in blocky ground.
#
# What this file provides
# -----------------------
# - Pyramidal wedge (1995 Barrett & McCreath conservative model)
# - Flat block (2017 Hawkesbury-style geology-realistic model)
# - Shale wedge with variable side angles (2017 update)
# - A helper to convert block weight (kN) to uniform pressure (kN/m^2)
#
# Units convention
# ----------------
# - Lengths: metres (m)
# - Density (unit weight): kN/m^3  (e.g., rock unit weight γ_rock)
# - Forces/weights: kN
# - Pressures/loads on slab: kN/m^2  (use as "w" for two-way slab demands)
#
# Geometry conventions
# --------------------
# - Bolt spacing 's' defines a square tributary panel s x s [m].
# - For wedges, the apex is above the panel center; faces are planar.
#
# Side-angle convention for wedges (IMPORTANT)
# --------------------------------------------
# - theta_deg is measured from the HORIZONTAL base plane to the wedge FACE
#   along the panel midline (i.e., 0° = flat, 90° = vertical).
# - With this convention, the pyramid height is:
#       h = (s / 2) * tan(theta_deg)
# - The volume of a square pyramid with base s^2 and height h is:
#       V = (1/3) * s^2 * h
#
# Notes
# -----
# - If you prefer to treat theta as a friction angle surrogate or use
#   different face kinematics, you can change only the height function
#   and keep the rest intact.
# - Optional surcharge terms can be passed to include water/equipment loads.
#
from __future__ import annotations
from math import tan, radians
from typing import Tuple, Optional


# -----------------------------
# Helpers (public)
# -----------------------------
def uniform_load_from_block(W_kN: float, s: float) -> float:
    """
    Convert a discrete block weight W [kN] sitting on a square panel (s x s) [m]
    into an equivalent uniform pressure w [kN/m^2].

        w = W / (s^2)

    Parameters
    ----------
    W_kN : float
        Block weight in kN.
    s : float
        Bolt spacing (panel side length) in metres.

    Returns
    -------
    float
        Equivalent uniform pressure in kN/m^2.
    """
    if s <= 0.0:
        raise ValueError("Bolt spacing 's' must be > 0.")
    return W_kN / (s * s)


# -----------------------------
# Barrett & McCreath (1995): Pyramidal wedge (≈ 60° sides)
# -----------------------------
def block_weight_pyramid(
    s: float,
    gamma_rock: float,
    theta_deg: float = 60.0,
    surcharge_uniform: float = 0.0,
    include_shotcrete_self_weight: bool = False,
    t_shotcrete: float = 0.0,
    gamma_shotcrete: float = 24.0,
) -> Tuple[float, float]:
    """
    Compute the weight of a square pyramidal wedge with side angle 'theta_deg'
    measured from the horizontal base plane to the face along the panel midline.

    Height:
        h = (s/2) * tan(theta)

    Volume:
        V = (1/3) * s^2 * h

    Weight of rock wedge:
        W_rock = V * gamma_rock

    Optional surcharges:
        - 'surcharge_uniform' [kN/m^2] is integrated over panel area s^2.
        - shotcrete self-weight (if include_shotcrete_self_weight=True):
              W_sc = (t_shotcrete * s^2) * gamma_shotcrete

    Returns
    -------
    (W_total_kN, w_uniform_kNpm2)
        W_total_kN: total weight in kN (rock + surcharges)
        w_uniform_kNpm2: equivalent uniform pressure in kN/m^2

    Notes
    -----
    - This is the classic conservative model from 1995 (often with theta≈60°).
    - Treat 'surcharge_uniform' for water/equipment/etc.
    - 'gamma_shotcrete' default ~24 kN/m^3; set t_shotcrete (m) if including.
    """
    if s <= 0.0:
        raise ValueError("Bolt spacing 's' must be > 0.")
    if gamma_rock <= 0.0:
        raise ValueError("gamma_rock must be > 0.")

    h = 0.5 * s * tan(radians(theta_deg))
    V = (1.0 / 3.0) * (s ** 2) * h  # m^3
    W_rock = V * gamma_rock         # kN

    # Uniform surcharge over the panel (kN/m^2 * m^2 = kN)
    W_surcharge = surcharge_uniform * (s ** 2) if surcharge_uniform > 0.0 else 0.0

    # Optional shotcrete self-weight on the panel area
    W_sc = 0.0
    if include_shotcrete_self_weight and t_shotcrete > 0.0:
        V_sc = t_shotcrete * (s ** 2)
        W_sc = V_sc * gamma_shotcrete

    W_total = W_rock + W_surcharge + W_sc
    w_uniform = uniform_load_from_block(W_total, s)
    return W_total, w_uniform


# -----------------------------
# 2017 “Revisited”: Geology-realistic flat block (Hawkesbury)
# -----------------------------
def block_weight_flat(
    s: float,
    gamma_rock: float,
    h_block: float,
    surcharge_uniform: float = 0.0,
    include_shotcrete_self_weight: bool = False,
    t_shotcrete: float = 0.0,
    gamma_shotcrete: float = 24.0,
) -> Tuple[float, float]:
    """
    Flat rectangular block representing bedded/flat-lying strata (e.g., Hawkesbury).
    Volume:
        V = s^2 * h_block

    Weight:
        W_rock = V * gamma_rock

    Optional surcharges:
        as per 'block_weight_pyramid'.

    Parameters
    ----------
    s : float
        Bolt spacing (panel side length) in metres.
    gamma_rock : float
        Rock unit weight kN/m^3.
    h_block : float
        Assumed flat block thickness/height (m). Typical 0.3–2.0 m ranges per 2017.

    Returns
    -------
    (W_total_kN, w_uniform_kNpm2)
    """
    if s <= 0.0:
        raise ValueError("Bolt spacing 's' must be > 0.")
    if gamma_rock <= 0.0:
        raise ValueError("gamma_rock must be > 0.")
    if h_block <= 0.0:
        raise ValueError("h_block must be > 0.")

    V = (s ** 2) * h_block
    W_rock = V * gamma_rock

    W_surcharge = surcharge_uniform * (s ** 2) if surcharge_uniform > 0.0 else 0.0

    W_sc = 0.0
    if include_shotcrete_self_weight and t_shotcrete > 0.0:
        V_sc = t_shotcrete * (s ** 2)
        W_sc = V_sc * gamma_shotcrete

    W_total = W_rock + W_surcharge + W_sc
    w_uniform = uniform_load_from_block(W_total, s)
    return W_total, w_uniform


# -----------------------------
# 2017 “Revisited”: Shale wedges with variable side angle
# -----------------------------
def block_weight_shale(
    s: float,
    gamma_rock: float,
    theta_deg: float,
    surcharge_uniform: float = 0.0,
    include_shotcrete_self_weight: bool = False,
    t_shotcrete: float = 0.0,
    gamma_shotcrete: float = 24.0,
) -> Tuple[float, float]:
    """
    Shale wedge model with specified side angle theta (e.g., 45/50/60°).
    Same geometry as the pyramid function but theta is explicitly a parameter.

    Returns
    -------
    (W_total_kN, w_uniform_kNpm2)
    """
    # Delegate to the pyramid function (same geometry math)
    return block_weight_pyramid(
        s=s,
        gamma_rock=gamma_rock,
        theta_deg=theta_deg,
        surcharge_uniform=surcharge_uniform,
        include_shotcrete_self_weight=include_shotcrete_self_weight,
        t_shotcrete=t_shotcrete,
        gamma_shotcrete=gamma_shotcrete,
    )


# -----------------------------
# Optional convenience API (pure parameters, no model imports)
# -----------------------------
def compute_panel_load(
    model: str,
    s: float,
    gamma_rock: float,
    theta_deg: Optional[float] = None,
    h_block: Optional[float] = None,
    surcharge_uniform: float = 0.0,
    include_shotcrete_self_weight: bool = False,
    t_shotcrete: float = 0.0,
    gamma_shotcrete: float = 24.0,
) -> Tuple[float, float]:
    """
    Thin wrapper to compute (W, w) without importing enums from models.py.
    Useful for tests or quick scripts.

    Parameters
    ----------
    model : str
        One of: "Pyramid60", "FlatBlock", "ShaleWedge" (case-insensitive accepted).
    s, gamma_rock, theta_deg, h_block, surcharge_uniform, include_shotcrete_self_weight,
    t_shotcrete, gamma_shotcrete : see individual functions above.

    Returns
    -------
    (W_total_kN, w_uniform_kNpm2)
    """
    key = (model or "").strip().lower()
    if key in ("pyramid60", "pyramid", "bm1995", "barrett"):
        th = 60.0 if theta_deg is None else float(theta_deg)
        return block_weight_pyramid(
            s, gamma_rock, th, surcharge_uniform,
            include_shotcrete_self_weight, t_shotcrete, gamma_shotcrete
        )
    elif key in ("flatblock", "flat", "hawkesbury"):
        if h_block is None:
            raise ValueError("FlatBlock requires h_block (m).")
        return block_weight_flat(
            s, gamma_rock, float(h_block), surcharge_uniform,
            include_shotcrete_self_weight, t_shotcrete, gamma_shotcrete
        )
    elif key in ("shalewedge", "shale"):
        if theta_deg is None:
            raise ValueError("ShaleWedge requires theta_deg (degrees).")
        return block_weight_shale(
            s, gamma_rock, float(theta_deg), surcharge_uniform,
            include_shotcrete_self_weight, t_shotcrete, gamma_shotcrete
        )
    else:
        raise ValueError(f"Unknown load model '{model}'. Expected Pyramid60 | FlatBlock | ShaleWedge.")


__all__ = [
    "uniform_load_from_block",
    "block_weight_pyramid",
    "block_weight_flat",
    "block_weight_shale",
    "compute_panel_load",
]
