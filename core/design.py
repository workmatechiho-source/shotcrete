# core/design.py
# ------------------------------------------------------------
# Orchestration of the design check:
# - Builds the panel load from the selected wedge/block model
# - Evaluates capacities and demands for each failure mode
# - Applies FOS or LRFD logic per CodeFactors
# - Returns a DesignResult with per-mode details and governing outcome
#
# Dependencies
# ------------
# - imports ONLY from core.* modules that do NOT import this file, to avoid
#   circular imports.
#
from __future__ import annotations
from typing import Tuple, Dict

# When imported as part of the ``core`` package the relative imports below work
# as intended.  However, running ``design.py`` as a standalone script (or from
# interactive environments where ``core`` isn't a recognised package) raises
# ``ImportError: attempted relative import with no known parent package``.
#
# To keep the module convenient for both package and script usage we try the
# relative imports first and fall back to plain imports if they fail.  This
# mirrors the layout of the repository where ``design.py`` lives alongside the
# sibling modules it depends on.
try:  # pragma: no cover - exercised only when run as a script
    from .models import (
        DesignInput,
        DesignResult,
        ModeResult,
        DesignMode,
        LoadModel,
    )
    from .loads import (
        block_weight_pyramid,
        block_weight_flat,
        block_weight_shale,
        uniform_load_from_block,
    )
    from .capacities import (
        capacity_adhesion,
        flexure_demands_uniform_load,
        capacity_flexure_two_way,
        punching_demand,
        capacity_punching,
        capacity_direct_shear,
        evaluate_fos,
        evaluate_lrfd,
    )
except ImportError:  # pragma: no cover - fallback for script execution
    from models import (
        DesignInput,
        DesignResult,
        ModeResult,
        DesignMode,
        LoadModel,
    )
    from loads import (
        block_weight_pyramid,
        block_weight_flat,
        block_weight_shale,
        uniform_load_from_block,
    )
    from capacities import (
        capacity_adhesion,
        flexure_demands_uniform_load,
        capacity_flexure_two_way,
        punching_demand,
        capacity_punching,
        capacity_direct_shear,
        evaluate_fos,
        evaluate_lrfd,
    )


# -----------------------------
# Internal: compute (W, w) for the chosen model
# -----------------------------
def _panel_load_from_input(inp: DesignInput) -> Tuple[float, float]:
    """
    Returns (W_total_kN, w_uniform_kNpm2) for the input geometry/materials.
    By default we do NOT include shotcrete self-weight; toggle below if desired.
    """
    include_sc = False  # keep load from ground dominant and comparable to papers
    if inp.load_model == LoadModel.PYRAMID_60:
        return block_weight_pyramid(
            s=inp.s,
            gamma_rock=inp.gamma_rock,
            theta_deg=inp.theta_deg,
            surcharge_uniform=0.0,
            include_shotcrete_self_weight=include_sc,
            t_shotcrete=inp.t,
        )
    elif inp.load_model == LoadModel.FLAT_BLOCK:
        return block_weight_flat(
            s=inp.s,
            gamma_rock=inp.gamma_rock,
            h_block=inp.h_block,
            surcharge_uniform=0.0,
            include_shotcrete_self_weight=include_sc,
            t_shotcrete=inp.t,
        )
    elif inp.load_model == LoadModel.SHALE_WEDGE:
        return block_weight_shale(
            s=inp.s,
            gamma_rock=inp.gamma_rock,
            theta_deg=inp.theta_deg,
            surcharge_uniform=0.0,
            include_shotcrete_self_weight=include_sc,
            t_shotcrete=inp.t,
        )
    else:
        # Fallback to pyramid if unknown
        return block_weight_pyramid(
            s=inp.s,
            gamma_rock=inp.gamma_rock,
            theta_deg=inp.theta_deg,
            surcharge_uniform=0.0,
            include_shotcrete_self_weight=include_sc,
            t_shotcrete=inp.t,
        )


# -----------------------------
# Public API: main design checks
# -----------------------------
def check_design(inp: DesignInput) -> DesignResult:
    """
    Master entry point. Runs all four failure mode checks and returns a DesignResult.
    This function is agnostic to whether you're doing FoS or LRFD; it reads inp.factors.mode.

    Per-mode conventions:
    - Adhesion:    demand = W_total [kN]; capacity from bond ring [kN]
    - Flexure:     demand = M_demand [kN·m/m]; capacity = M_rd [kN·m/m]
    - Punching:    demand = V_dem [kN] at a bolt; capacity = V_rd [kN]
    - DirectShear: demand = W_total [kN] (panel resultant); capacity = V_rd [kN]

    Returns
    -------
    DesignResult
    """
    mat = inp.materials
    f   = inp.factors
    teff = inp.t_effective()

    W_total_kN, w_uniform = _panel_load_from_input(inp)

    # -------------------------
    # 1) Adhesion
    # -------------------------
    C_adh_kN = capacity_adhesion(s=inp.s, a_bond=inp.a_bond, tau_b_MPa=mat.tau_b)
    D_adh_kN = W_total_kN  # compare resultant-to-resultant
    res_adh = _evaluate_mode(
        name="Adhesion",
        demand=D_adh_kN,
        capacity=C_adh_kN,
        mode=f.mode,
        phi=f.phi_shear,  # conservative pick (no explicit phi_adh; use shear)
        gamma=f.gamma_load,
        detail=f"Ring area 4*s*a_bond; tau_b={mat.tau_b:.3f} MPa, a_bond={inp.a_bond:.3f} m",
    )

    # -------------------------
    # 2) Flexure (two-way slab idealisation)
    # -------------------------
    M_dem = flexure_demands_uniform_load(
        w_kNpm2=w_uniform,
        s=inp.s,
        two_way_factor=0.6,  # starter coefficient; refine via codes as needed
    )
    M_cap = capacity_flexure_two_way(
        t_eff=teff,
        f_r_MPa=mat.f_r,
    )
    res_flex = _evaluate_mode(
        name="Flexure",
        demand=M_dem,
        capacity=M_cap,
        mode=f.mode,
        phi=f.phi_flexure,
        gamma=f.gamma_load,
        detail=f"M_1D=w*s^2/8; two-way=0.6; f_r={mat.f_r:.3f} MPa; t_eff={teff:.3f} m",
    )

    # -------------------------
    # 3) Punching shear (around plate)
    # -------------------------
    V_dem = punching_demand(w_kNpm2=w_uniform, s=inp.s)
    V_cap = capacity_punching(t_eff=teff, c_plate=inp.c, v_rd_MPa=mat.v_rd)
    res_punch = _evaluate_mode(
        name="Punching",
        demand=V_dem,
        capacity=V_cap,
        mode=f.mode,
        phi=f.phi_punching,
        gamma=f.gamma_load,
        detail=f"u=4*(c+0.5d); d≈0.9*t_eff; v_rd={mat.v_rd:.3f} MPa; c={inp.c:.3f} m",
    )

    # -------------------------
    # 4) Direct in-plane shear (panel)
    # -------------------------
    D_shear = W_total_kN  # resultant shear equivalent from panel load
    Vrd_shear = capacity_direct_shear(s=inp.s, t_eff=teff, tau_v_MPa=mat.tau_v)
    res_shear = _evaluate_mode(
        name="DirectShear",
        demand=D_shear,
        capacity=Vrd_shear,
        mode=f.mode,
        phi=f.phi_shear,
        gamma=f.gamma_load,
        detail=f"A_v≈4*s*t_eff; tau_v={mat.tau_v:.3f} MPa; t_eff={teff:.3f} m",
    )

    # -------------------------
    # Collate + governing
    # -------------------------
    result = DesignResult(derived={"t_eff": teff, "W_total_kN": W_total_kN, "w_kNpm2": w_uniform})
    result.modes = {
        "Adhesion":    res_adh,
        "Flexure":     res_flex,
        "Punching":    res_punch,
        "DirectShear": res_shear,
    }

    if f.mode == DesignMode.FOS:
        # governing = MIN FoS
        gov_mode, gov_val = _min_fos_mode(result.modes)
        ok = gov_val >= 1.0
    else:
        # governing = MAX Utilisation
        gov_mode, gov_val = _max_util_mode(result.modes)
        ok = gov_val <= 1.0

    result.governing_mode = gov_mode
    result.governing_value = gov_val
    result.ok = ok
    return result


# -----------------------------
# Helpers
# -----------------------------
def _evaluate_mode(
    name: str,
    demand: float,
    capacity: float,
    mode: DesignMode,
    phi: float,
    gamma: float,
    detail: str,
) -> ModeResult:
    """
    Build a ModeResult with either FoS or LRFD utilisation filled in.
    """
    mr = ModeResult(demand=demand, capacity=capacity, detail=detail)
    if mode == DesignMode.FOS:
        fos, passes = evaluate_fos(capacity, demand)
        mr.fos = fos
        mr.passes = passes
    else:
        util, passes = evaluate_lrfd(capacity, demand, phi=phi, gamma=gamma)
        mr.utilization = util
        mr.passes = passes
    return mr


def _min_fos_mode(modes: Dict[str, ModeResult]) -> Tuple[str, float]:
    """
    Find the mode with the smallest FoS (FOS design).
    Returns ('ModeName', min_fos_value). If no FoS values exist, returns ('', 0).
    """
    min_name, min_val = "", 0.0
    first = True
    for name, mr in modes.items():
        if mr.fos is None:
            continue
        if first or (mr.fos < min_val):
            min_name, min_val = name, mr.fos
            first = False
    return min_name, min_val


def _max_util_mode(modes: Dict[str, ModeResult]) -> Tuple[str, float]:
    """
    Find the mode with the largest utilisation (LRFD design).
    Returns ('ModeName', max_util_value). If no utilisation values exist, returns ('', 0).
    """
    max_name, max_val = "", 0.0
    first = True
    for name, mr in modes.items():
        if mr.utilization is None:
            continue
        if first or (mr.utilization > max_val):
            max_name, max_val = name, mr.utilization
            first = False
    return max_name, max_val


__all__ = ["check_design"]
