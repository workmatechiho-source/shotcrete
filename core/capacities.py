# core/capacities.py
# ------------------------------------------------------------
# Capacities (resistances) and basic demand models for:
#  1) Adhesion (bond) failure
#  2) Flexure (two-way slab idealisation)
#  3) Punching shear near bolt face plates
#  4) Direct (in-plane) shear of the panel
#
# Units convention
# ----------------
# - Lengths: metres (m)
# - Thickness: metres (m)
# - Stresses/strengths: MPa  (1 MPa = 1000 kN/m^2)
# - Uniform loads/pressures: kN/m^2
# - Forces (shear, punching, adhesion resultants): kN
# - Moments (flexure): kN·m per metre width  (strip method)
#
# Theory mapping (short version)
# ------------------------------
# - Adhesion (1995): bond controls peak; early debonding → flexural control.
#   We model capacity as τ_b * (effective bond area). Here we adopt a
#   perimeter-based ring with width a_bond: A_eff = perimeter * a_bond.
#
# - Flexure (1995 + 2017): two-way spanning between bolts. We use a
#   strip-based demand (1D) reduced for two-way action and compare to
#   residual flexural capacity from fibres (2017 alignment).
#
# - Punching (1995 + 2017): shear around plate; capacity v_rd * (u * d),
#   where u is a control perimeter, d ≈ 0.9 t_eff. This mirrors code-style
#   punch checks and the 2017 corrections.
#
# - Direct shear (1995): usually non-governing; we include τ_v times a
#   shear area around the panel perimeter ~ 4*s*t_eff.
#
# Notes on simplifications (safe starters)
# ----------------------------------------
# - Flexure demand uses a simple strip model with a two-way reduction factor.
#   Replace with code coefficients (AS/Eurocode) if you prefer plate tables.
# - Punching uses a pragmatic perimeter u = 4*(c + 0.5 d). Adjust to match
#   your preferred code detail (critical perimeter offsets).
# - Adhesion uses a perimeter ring; if you want full-area bond, set a_bond=s/2.
#
from __future__ import annotations
from math import isfinite
from typing import Tuple

MPA_TO_KN_M2 = 1000.0  # 1 MPa = 1000 kN/m^2


# ------------------------------------------------------------
# 1) ADHESION (BOND) FAILURE
# ------------------------------------------------------------
def capacity_adhesion(s: float, a_bond: float, tau_b_MPa: float) -> float:
    """
    Adhesion (bond) capacity as a resultant force [kN] that can be compared
    directly with a block weight [kN].

    Model
    -----
      A_eff = perimeter * a_bond = 4 * s * a_bond       [m^2]
      C_adh = τ_b * A_eff                                [MPa * m^2]
            = τ_b(MPa) * 1000 (kN/m^2 per MPa) * A_eff  [kN]

    Parameters
    ----------
    s         : bolt spacing (panel side) [m]
    a_bond    : adhesive (bond) length [m] (1995 concept; tune per 2017 practice)
    tau_b_MPa : bond shear strength [MPa]

    Returns
    -------
    kN : adhesion capacity as a resultant force.

    Remarks
    -------
    - 1995 often discussed 30–50 mm adhesive length; 2017 cautions this can be
      outdated. Treat 'a_bond' as a calibrated parameter from site practice.
    """
    if s <= 0 or a_bond < 0 or tau_b_MPa < 0:
        return 0.0
    A_eff = 4.0 * s * a_bond  # m^2
    return tau_b_MPa * MPA_TO_KN_M2 * A_eff


# ------------------------------------------------------------
# 2) FLEXURE (TWO-WAY SLAB IDEALISATION)
# ------------------------------------------------------------
def flexure_demands_uniform_load(
    w_kNpm2: float,
    s: float,
    two_way_factor: float = 0.6,
) -> float:
    """
    Design bending moment demand per metre width [kN·m/m] for a square panel
    under a uniform load w [kN/m^2], using a strip method with a two-way reduction.

    Base 1D simply supported strip:
        M_1D = w * s^2 / 8     [kN·m/m]

    Two-way action reduction:
        M = two_way_factor * M_1D

    Parameters
    ----------
    w_kNpm2      : uniform panel load [kN/m^2] (from loads.py)
    s            : panel side [m]
    two_way_factor: 0.6 default (ballpark two-way reduction). Use code tables
                    for fixed/continuous edges if you want more precision.

    Returns
    -------
    M_kNpm : float
        Design moment demand per metre width [kN·m/m]
    """
    if s <= 0 or w_kNpm2 < 0:
        return 0.0
    M_1D = w_kNpm2 * (s ** 2) / 8.0
    return two_way_factor * M_1D


def capacity_flexure_two_way(
    t_eff: float,
    f_r_MPa: float,
) -> float:
    """
    Residual flexural capacity per metre width [kN·m/m] using residual flexural
    tensile strength f_r (2017: EN 14651 / ASTM C1609 compatible).

    Section modulus per metre width:
        Z = b * t^2 / 6, with b = 1 m → Z = t_eff^2 / 6   [m^3/m]

    Nominal moment capacity:
        M_rd = f_r(MPa) * (1000 kN/m^2 per MPa) * Z       [kN·m/m]

    Parameters
    ----------
    t_eff   : effective shotcrete thickness [m] (after durability deduction)
    f_r_MPa : residual flexural tensile strength [MPa]

    Returns
    -------
    M_rd_kNpm : float
        Flexural capacity per metre width [kN·m/m].
    """
    if t_eff <= 0 or f_r_MPa <= 0:
        return 0.0
    Z = (t_eff ** 2) / 6.0  # m^3 per m width
    return f_r_MPa * MPA_TO_KN_M2 * Z


# ------------------------------------------------------------
# 3) PUNCHING SHEAR NEAR BOLT/PLATE
# ------------------------------------------------------------
def punching_demand(
    w_kNpm2: float,
    s: float,
) -> float:
    """
    Punching shear demand [kN] attributed to a single bolt/plate location.

    Model (simple tributary assumption)
    -----------------------------------
    Each bolt is idealised to carry ~1/4 of a square panel's load:
        V_dem ≈ w * (s^2) / 4

    Parameters
    ----------
    w_kNpm2 : uniform panel load [kN/m^2]
    s       : panel side [m]

    Returns
    -------
    V_dem_kN : float
        Punching shear demand at one bolt/plate [kN].

    Notes
    -----
    - This is a pragmatic starting point consistent with a grid of bolts
      supporting the panel. Adjust the tributary fraction if your layout differs.
    """
    if s <= 0 or w_kNpm2 < 0:
        return 0.0
    return w_kNpm2 * (s ** 2) / 4.0


def capacity_punching(
    t_eff: float,
    c_plate: float,
    v_rd_MPa: float,
) -> float:
    """
    Punching shear capacity [kN] around a bolt face plate.

    Model
    -----
      Effective depth: d ≈ 0.9 * t_eff
      Control perimeter: u = 4 * (c_plate + 0.5 * d)
      Capacity: V_rd = v_rd(MPa) * 1000 (kN/m^2) * u * d

    Parameters
    ----------
    t_eff    : effective thickness [m]
    c_plate  : effective bearing/plate width around bolt (drop-panel) [m]
    v_rd_MPa : design diagonal tension/punching stress [MPa]

    Returns
    -------
    V_rd_kN : float
        Punching capacity [kN].

    Notes
    -----
    - This mirrors code-style punching checks with a simplified perimeter.
      Adjust u and d rules to match AS/Eurocode details as needed.
    """
    if t_eff <= 0 or c_plate < 0 or v_rd_MPa <= 0:
        return 0.0
    d = 0.9 * t_eff
    u = 4.0 * (c_plate + 0.5 * d)
    return v_rd_MPa * MPA_TO_KN_M2 * u * d


# ------------------------------------------------------------
# 4) DIRECT (IN-PLANE) SHEAR OF THE PANEL
# ------------------------------------------------------------
def capacity_direct_shear(
    s: float,
    t_eff: float,
    tau_v_MPa: float,
) -> float:
    """
    In-plane shear capacity (resultant) [kN] along the panel boundary.

    Model
    -----
      Shear area along the perimeter: A_v ≈ 4 * s * t_eff
      V_rd = τ_v(MPa) * 1000 (kN/m^2) * A_v

    Parameters
    ----------
    s          : panel side [m]
    t_eff      : effective thickness [m]
    tau_v_MPa  : in-plane shear strength [MPa]

    Returns
    -------
    V_rd_kN : float
        Direct shear capacity [kN].

    Notes
    -----
    - 1995 observed direct shear rarely governs; included here for completeness.
    """
    if s <= 0 or t_eff <= 0 or tau_v_MPa <= 0:
        return 0.0
    A_v = 4.0 * s * t_eff
    return tau_v_MPa * MPA_TO_KN_M2 * A_v


# ------------------------------------------------------------
# Utility: evaluate pass/fail in FOS or LRFD
# ------------------------------------------------------------
def evaluate_fos(capacity: float, demand: float) -> Tuple[float, bool]:
    """
    Factor of Safety and pass/fail.
    """
    if demand <= 0:
        return float("inf"), True
    if capacity <= 0:
        return 0.0, False
    fos = capacity / demand
    return fos, fos >= 1.0


def evaluate_lrfd(capacity: float, demand: float, phi: float, gamma: float) -> Tuple[float, bool]:
    """
    LRFD utilisation and pass/fail.

      Check: φ * Capacity >= γ * Demand
      Utilisation U = (γ * Demand) / (φ * Capacity)

    Returns
    -------
    (U, passes)
      U     : utilisation (<= 1.0 is OK)
      passes: bool
    """
    if capacity <= 0 or phi <= 0:
        return float("inf"), False
    if demand < 0:
        demand = 0.0
    numerator = gamma * demand
    denominator = phi * capacity
    if denominator <= 0:
        return float("inf"), False
    U = numerator / denominator
    return U, U <= 1.0


__all__ = [
    "capacity_adhesion",
    "flexure_demands_uniform_load",
    "capacity_flexure_two_way",
    "punching_demand",
    "capacity_punching",
    "capacity_direct_shear",
    "evaluate_fos",
    "evaluate_lrfd",
]
