# tests/test_smoke.py
# ------------------------------------------------------------
# Minimal smoke tests for the shotcrete design engine.
# Run:  pytest -q
#
from __future__ import annotations

import math

from core.models import (
    DesignInput, MaterialProps, CodeFactors,
    DesignMode, LoadModel, GeologyPreset
)
from core.design import check_design


def _default_input(
    s: float = 1.5,
    t: float = 0.10,
    c: float = 0.25,
    gamma_rock: float = 25.0,
    load_model: LoadModel = LoadModel.PYRAMID_60,
) -> DesignInput:
    mats = MaterialProps(
        f_c=30.0,
        tau_b=1.0,  # MPa
        f_r=1.2,   # MPa
        tau_v=1.5, # MPa
        v_rd=1.2,  # MPa
    )
    fac = CodeFactors(
        mode=DesignMode.FOS,  # default FoS for intuitive testing
        phi_flexure=0.6,
        phi_shear=0.6,
        phi_punching=0.6,
        gamma_load=1.5,
        t_dur_deduction=0.0,
    )
    return DesignInput(
        s=s,
        t=t,
        c=c,
        gamma_rock=gamma_rock,
        load_model=load_model,
        geology_preset=GeologyPreset.GENERIC,
        theta_deg=60.0,
        h_block=0.6,
        materials=mats,
        factors=fac,
        age_label="28d",
        notes="test",
        a_bond=0.05,
    )


def test_design_runs_and_has_modes():
    """Basic: engine returns four modes with sensible numbers."""
    inp = _default_input()
    res = check_design(inp)
    assert res.modes, "No modes returned"
    for key in ("Adhesion", "Flexure", "Punching", "DirectShear"):
        assert key in res.modes, f"Missing mode {key}"
        mr = res.modes[key]
        assert mr.capacity >= 0.0
        assert mr.demand >= 0.0


def test_spacing_increase_reduces_margins_fos():
    """
    As spacing increases, demands rise faster than capacities for most modes,
    so the governing FoS should not increase.
    """
    inp1 = _default_input(s=1.2)
    inp2 = _default_input(s=2.4)
    res1 = check_design(inp1)
    res2 = check_design(inp2)

    # In FOS mode, governing FoS should generally drop with larger spacing
    assert res1.governing_value >= res2.governing_value or math.isclose(
        res1.governing_value, res2.governing_value, rel_tol=1e-6
    )


def test_thicker_shotcrete_increases_flexural_capacity():
    """Flexural capacity should increase with thickness (t_eff^2)."""
    inp_thin = _default_input(t=0.08)
    inp_thick = _default_input(t=0.14)
    res_thin = check_design(inp_thin)
    res_thick = check_design(inp_thick)

    M_thin = res_thin.modes["Flexure"].capacity
    M_thick = res_thick.modes["Flexure"].capacity
    assert M_thick > M_thin


def test_lrfd_utilisation_switch():
    """Switching to LRFD should populate utilisation and still produce a governing value."""
    inp = _default_input()
    inp.factors.mode = DesignMode.LRFD
    res = check_design(inp)

    # At least one mode must have a utilisation value
    assert any(mr.utilization is not None for mr in res.modes.values())
    # Governing value should be > 0
    assert res.governing_value > 0.0


def test_durability_deduction_reduces_capacity():
    """Durability deduction lowers effective thickness and hence flexural capacity."""
    inp0 = _default_input(t=0.12)
    res0 = check_design(inp0)

    inp1 = _default_input(t=0.12)
    inp1.factors.t_dur_deduction = 0.02  # 20 mm off
    res1 = check_design(inp1)

    M0 = res0.modes["Flexure"].capacity
    M1 = res1.modes["Flexure"].capacity
    assert M1 < M0
