# core/models.py
# ------------------------------------------------------------
# Core data models for the shotcrete design tool.
# This file contains NO imports from other local modules
# to avoid circular-import issues.
#
# Units convention (consistent across the codebase):
# - Lengths: metres (m)
# - Forces: kN
# - Densities: kN/m^3  (e.g., rock unit weight γ_rock)
# - Stresses/Strengths: MPa (i.e., N/mm^2)
# - Angles: degrees
#
# Notes:
# - Adhesion (tau_b), residual flexural strength (f_r),
#   shear strength (tau_v), and punching/diagonal tension (v_rd)
#   are all treated as STRESSES in MPa.
# - Thickness durability deduction (t_dur_deduction) is in metres.
# - Effective thickness t_eff = max(0, t - t_dur_deduction).
#
# This file is purely data containers + tiny helpers.
# All calculations live in loads.py / capacities.py / design.py.

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


# -----------------------------
# Enumerations
# -----------------------------
class DesignMode(str, Enum):
    FOS = "FOS"    # Factor-of-Safety design
    LRFD = "LRFD"  # Load & Resistance Factor Design


class LoadModel(str, Enum):
    PYRAMID_60 = "Pyramid60"   # Barrett & McCreath (1995) conservative pyramid (~60°)
    FLAT_BLOCK = "FlatBlock"   # 2017: geology-specific flat block (e.g., Hawkesbury)
    SHALE_WEDGE = "ShaleWedge" # 2017: shale wedges with 45–60° sides


class GeologyPreset(str, Enum):
    GENERIC = "Generic"
    HAWKESBURY = "HawkesburySandstone"
    ASHFIELD = "AshfieldShale"


# -----------------------------
# Materials & Code Factors
# -----------------------------
@dataclass
class MaterialProps:
    """
    Material properties for shotcrete and interface, at the selected design age.
    All stresses in MPa.

    Attributes
    ----------
    f_c   : float
        Compressive strength of shotcrete at the design age (MPa).
        (Used indirectly for some code-derived properties if needed.)
    tau_b : float
        Adhesion (bond) strength rock↔shotcrete (MPa).
    f_r   : float
        Residual flexural tensile strength for SFRS/mesh design (MPa),
        compatible with EN 14651 / ASTM C1609 style residuals.
    tau_v : float
        In-plane shear strength of the shotcrete panel (MPa).
    v_rd  : float
        Design diagonal tension / punching shear stress (MPa)
        (may include fibre contribution if derived via codes.py).
    """
    f_c: float
    tau_b: float
    f_r: float
    tau_v: float
    v_rd: float


@dataclass
class CodeFactors:
    """
    Design factors and durability allowances.

    Attributes
    ----------
    mode           : DesignMode
        FOS or LRFD. Drives result presentation and pass/fail logic.
    phi_flexure    : float
        Strength reduction factor for flexure (LRFD). Ignored in FOS mode.
    phi_shear      : float
        Strength reduction factor for in-plane shear (LRFD).
    phi_punching   : float
        Strength reduction factor for punching/diagonal tension (LRFD).
    gamma_load     : float
        Load factor (LRFD). Ignored in FOS mode.
    t_dur_deduction: float
        Thickness deduction for durability/corrosion (m). 2017 paper recommends
        considering long-term allowances; 0.0 if not applicable.
    """
    mode: DesignMode = DesignMode.FOS
    phi_flexure: float = 0.6
    phi_shear: float = 0.6
    phi_punching: float = 0.6
    gamma_load: float = 1.5
    t_dur_deduction: float = 0.0


# -----------------------------
# Design Inputs
# -----------------------------
@dataclass
class DesignInput:
    """
    All user-selectable inputs needed to execute the design checks.

    Geometry & Materials
    --------------------
    s                 : Bolt spacing (clear span along x & y assumed equal), m.
    t                 : Nominal shotcrete thickness, m.
    c                 : Effective bearing/plate width around bolt (drop panel), m.
    gamma_rock        : Rock unit weight (kN/m^3) used for block load models.

    Load & Geology
    --------------
    load_model        : Selects the wedge/block model.
    geology_preset    : Geology preset to inform default angles/heights (UI-level).

    Wedge Parameters (used depending on load_model)
    ------------------------------------------------
    theta_deg         : Side angle for pyramid/shale wedges (degrees).
    h_block           : Flat block height for Hawkesbury-style model (m).

    Materials & Factors
    -------------------
    materials         : MaterialProps (MPa-based strengths).
    factors           : CodeFactors (LRFD/FOS factors and durability).

    Meta
    ----
    age_label         : Descriptive label for age (e.g., "Early", "7d", "28d").
    notes             : Free-form string captured into exports for traceability.
    """
    # Geometry
    s: float
    t: float
    c: float
    gamma_rock: float

    # Load modelling
    load_model: LoadModel = LoadModel.PYRAMID_60
    geology_preset: GeologyPreset = GeologyPreset.GENERIC

    # Wedge params (used by certain models)
    theta_deg: float = 60.0   # Used by Pyramid60 and ShaleWedge
    h_block: float = 0.5      # Used by FlatBlock (typical 0.3–2.0 m per 2017 guidance)

    # Materials & factors
    materials: MaterialProps = field(default_factory=lambda: MaterialProps(
        f_c=30.0, tau_b=1.0, f_r=1.0, tau_v=1.0, v_rd=1.0
    ))
    factors: CodeFactors = field(default_factory=CodeFactors)

    # Meta
    age_label: str = "28d"
    notes: str = ""

    # Adhesive (bond) length parameter (1995 concept; tune with 2017 practice)
    a_bond: float = 0.05  # m; use 0.03–0.05 cautiously per 2017 remarks

    def t_effective(self) -> float:
        """Effective thickness after durability deduction (never negative)."""
        teff = self.t - max(0.0, self.factors.t_dur_deduction)
        return teff if teff > 0.0 else 0.0


# -----------------------------
# Per-mode & overall results
# -----------------------------
@dataclass
class ModeResult:
    """
    Demand vs capacity for a single failure mode.

    demand     : float — typically force (kN), moment (kN·m), or stress (MPa)
                 depending on the check. We will document per-mode in design.py.
    capacity   : float — same dimension system as 'demand' for comparison.
    fos        : float | None — Capacity / Demand when in FOS mode.
    utilization: float | None — (γ*Demand) / (φ*Capacity) when in LRFD mode.
    passes     : bool | None — Result of the governing criterion for the selected mode.
    """
    demand: float
    capacity: float
    fos: Optional[float] = None
    utilization: Optional[float] = None
    passes: Optional[bool] = None
    detail: str = ""  # free text (e.g., equations used, spans, moments)


@dataclass
class DesignResult:
    """
    Container for all per-mode results and overall governing outcome.

    modes: mapping from mode name → ModeResult, e.g.:
           {
             "Adhesion": ModeResult(...),
             "Flexure":  ModeResult(...),
             "Punching": ModeResult(...),
             "DirectShear": ModeResult(...)
           }

    governing_mode : which mode controls (min FoS or max utilization).
    governing_value: the controlling value (FoS or utilization).
    ok             : overall pass/fail per chosen design mode.

    derived        : convenience numbers (e.g., effective thickness).
    """
    modes: Dict[str, ModeResult] = field(default_factory=dict)
    governing_mode: str = ""
    governing_value: float = 0.0
    ok: bool = False
    derived: Dict[str, float] = field(default_factory=dict)

    def summary(self) -> str:
        """One-line human-readable summary."""
        if not self.modes:
            return "No results."
        gm = self.governing_mode or "N/A"
        val = self.governing_value
        status = "OK" if self.ok else "NOT OK"
        return f"Governing: {gm} → {val:.3f} ({status})"


# Friendly export list
__all__ = [
    "DesignMode",
    "LoadModel",
    "GeologyPreset",
    "MaterialProps",
    "CodeFactors",
    "DesignInput",
    "ModeResult",
    "DesignResult",
]
