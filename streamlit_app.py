# streamlit_app.py
# ------------------------------------------------------------
# Minimal Streamlit UI for the shotcrete design tool (MVP).
# - Collects inputs
# - Calls core.design.check_design()
# - Shows per-mode results + governing mode
# - Optional: spacing sweep plot (stability-style chart)
#
# Run:
#   streamlit run streamlit_app.py
#
from __future__ import annotations

import math
from dataclasses import asdict

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Local imports (no circular refs; core/* never imports streamlit_app)
from core.models import (
    DesignInput, MaterialProps, CodeFactors,
    DesignMode, LoadModel, GeologyPreset
)
from core.design import check_design


# -----------------------------
# UI Helpers
# -----------------------------
def _design_mode_radio() -> DesignMode:
    pick = st.radio("Design mode", ["FoS", "LRFD"], horizontal=True, index=0)
    return DesignMode.FOS if pick == "FoS" else DesignMode.LRFD


def _load_model_select() -> LoadModel:
    label = st.selectbox(
        "Load model (block/wedge)",
        ["Pyramid60 (1995)", "FlatBlock (2017)", "ShaleWedge (2017)"],
        index=0,
    )
    if "Pyramid" in label:
        return LoadModel.PYRAMID_60
    if "FlatBlock" in label:
        return LoadModel.FLAT_BLOCK
    return LoadModel.SHALE_WEDGE


def _geology_select() -> GeologyPreset:
    label = st.selectbox(
        "Geology preset (affects only your interpretation; loads set below)",
        ["Generic", "HawkesburySandstone", "AshfieldShale"],
        index=0,
    )
    if "Hawkesbury" in label:
        return GeologyPreset.HAWKESBURY
    if "Ashfield" in label:
        return GeologyPreset.ASHFIELD
    return GeologyPreset.GENERIC


def _default_materials() -> MaterialProps:
    # Conservative starting points; tune per project/testing
    return MaterialProps(
        f_c=30.0,     # MPa
        tau_b=1.0,   # MPa (adhesion)
        f_r=1.2,     # MPa (residual flexural strength for SFRS)
        tau_v=1.5,   # MPa (in-plane shear)
        v_rd=1.2,    # MPa (punching/diagonal tension)
    )


def _default_factors(mode: DesignMode) -> CodeFactors:
    if mode == DesignMode.LRFD:
        return CodeFactors(
            mode=mode,
            phi_flexure=0.6,
            phi_shear=0.6,
            phi_punching=0.6,
            gamma_load=1.5,
            t_dur_deduction=0.0,
        )
    else:
        return CodeFactors(
            mode=mode,
            phi_flexure=0.6,
            phi_shear=0.6,
            phi_punching=0.6,
            gamma_load=1.0,  # ignored in FoS
            t_dur_deduction=0.0,
        )


# -----------------------------
# Sidebar inputs
# -----------------------------
st.set_page_config(page_title="Shotcrete Support Designer (MVP)", layout="wide")
st.title("Shotcrete Support Design in Blocky Ground — MVP")

with st.sidebar:
    st.header("Geometry & Materials")

    s = st.number_input("Bolt spacing s (m)", min_value=0.5, max_value=5.0, value=1.5, step=0.1)
    t = st.number_input("Shotcrete thickness t (m)", min_value=0.03, max_value=0.25, value=0.10, step=0.005, format="%.3f")
    c = st.number_input("Effective plate/drop-panel width c (m)", min_value=0.10, max_value=0.60, value=0.25, step=0.01)
    gamma_rock = st.number_input("Rock unit weight γ (kN/m³)", min_value=15.0, max_value=30.0, value=25.0, step=0.5)

    st.divider()
    st.header("Load model & geology")
    load_model = _load_model_select()
    geology = _geology_select()

    # Wedge params
    theta = st.slider("θ (deg) for Pyramid/Shale models", min_value=30, max_value=75, value=60, step=1)
    h_block = st.slider("h_block (m) for FlatBlock model", min_value=0.2, max_value=2.0, value=0.6, step=0.1)

    st.divider()
    st.header("Materials (MPa)")
    mats = _default_materials()
    tau_b = st.number_input("Adhesion τ_b (MPa)", min_value=0.05, max_value=2.5, value=mats.tau_b, step=0.05, format="%.2f")
    f_r = st.number_input("Residual flexural strength f_r (MPa)", min_value=0.20, max_value=4.0, value=mats.f_r, step=0.05, format="%.2f")
    tau_v = st.number_input("Panel shear strength τ_v (MPa)", min_value=0.20, max_value=4.0, value=mats.tau_v, step=0.05, format="%.2f")
    v_rd = st.number_input("Punching/diag. tension v_rd (MPa)", min_value=0.20, max_value=4.0, value=mats.v_rd, step=0.05, format="%.2f")

    st.divider()
    st.header("Factors & Durability")
    mode = _design_mode_radio()
    phi_flex = st.number_input("φ_flexure (LRFD)", min_value=0.3, max_value=0.9, value=0.6, step=0.05, format="%.2f")
    phi_shear = st.number_input("φ_shear (LRFD)", min_value=0.3, max_value=0.9, value=0.6, step=0.05, format="%.2f")
    phi_punch = st.number_input("φ_punching (LRFD)", min_value=0.3, max_value=0.9, value=0.6, step=0.05, format="%.2f")
    gamma_load = st.number_input("γ_load (LRFD)", min_value=1.0, max_value=2.0, value=1.5, step=0.1, format="%.2f")
    t_dur = st.number_input("Durability deduction (m)", min_value=0.0, max_value=0.05, value=0.0, step=0.005, format="%.3f")

    st.divider()
    st.header("Adhesion ring parameter")
    a_bond = st.number_input("Adhesive length a_bond (m)", min_value=0.00, max_value=0.10, value=0.05, step=0.005, format="%.3f")

    st.divider()
    run_calc = st.button("Calculate", type="primary")


# -----------------------------
# Build input object & run
# -----------------------------
materials = MaterialProps(
    f_c=30.0,  # not used directly in MVP; placeholder for future mappings
    tau_b=float(tau_b),
    f_r=float(f_r),
    tau_v=float(tau_v),
    v_rd=float(v_rd),
)

factors = CodeFactors(
    mode=mode,
    phi_flexure=float(phi_flex),
    phi_shear=float(phi_shear),
    phi_punching=float(phi_punch),
    gamma_load=float(gamma_load),
    t_dur_deduction=float(t_dur),
)

inp = DesignInput(
    s=float(s),
    t=float(t),
    c=float(c),
    gamma_rock=float(gamma_rock),
    load_model=load_model,
    geology_preset=geology,
    theta_deg=float(theta),
    h_block=float(h_block),
    materials=materials,
    factors=factors,
    age_label="User-set",
    notes="MVP run",
    a_bond=float(a_bond),
)

if run_calc:
    result = check_design(inp)

    col1, col2 = st.columns((1, 1), gap="large")

    with col1:
        st.subheader("Per-mode checks")
        rows = []
        for name, mr in result.modes.items():
            rows.append({
                "Mode": name,
                "Demand": mr.demand,
                "Capacity": mr.capacity,
                "FoS": mr.fos if mr.fos is not None else "",
                "Utilisation": mr.utilization if mr.utilization is not None else "",
                "Pass": "Yes" if (mr.passes is True) else ("No" if (mr.passes is False) else ""),
                "Detail": mr.detail,
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)

        st.caption(
            f"Derived: t_eff = {result.derived.get('t_eff', float('nan')):.3f} m, "
            f"W_total = {result.derived.get('W_total_kN', float('nan')):.2f} kN, "
            f"w = {result.derived.get('w_kNpm2', float('nan')):.2f} kN/m²"
        )

    with col2:
        st.subheader("Governing outcome")
        if mode == DesignMode.FOS:
            st.metric(
                label=f"Governing mode (FoS ≥ 1.0): {result.governing_mode}",
                value=f"{result.governing_value:.3f}",
                delta="OK" if result.ok else "NOT OK",
                delta_color="normal" if result.ok else "inverse",
            )
        else:
            st.metric(
                label=f"Governing mode (Utilisation ≤ 1.0): {result.governing_mode}",
                value=f"{result.governing_value:.3f}",
                delta="OK" if result.ok else "NOT OK",
                delta_color="normal" if result.ok else "inverse",
            )

        # Optional spacing sweep
        st.markdown("### Spacing sweep (quick stability chart)")
        sweep = st.checkbox("Enable spacing sweep")
        if sweep:
            s_min = st.number_input("s_min (m)", min_value=0.5, max_value=float(s), value=0.8, step=0.1)
            s_max = st.number_input("s_max (m)", min_value=float(s), max_value=5.0, value=max(float(s), 3.0), step=0.1)
            npts = st.slider("Points", min_value=5, max_value=50, value=20, step=1)

            s_vals = np.linspace(float(s_min), float(s_max), int(npts))
            y_vals = []
            labels = []

            for s_try in s_vals:
                inp_s = DesignInput(**{**asdict(inp), "s": float(s_try)})
                res_s = check_design(inp_s)
                # Plot governing value: FoS (want ≥1) or Utilisation (want ≤1)
                y = res_s.governing_value
                y_vals.append(y)

            fig, ax = plt.subplots()
            ax.plot(s_vals, y_vals, linewidth=2)
            ax.set_xlabel("Bolt spacing s (m)")
            ax.set_ylabel("FoS (if FoS mode)  or  Utilisation (if LRFD)")
            ax.grid(True, which="both")
            st.pyplot(fig, clear_figure=True)

    st.divider()
    st.caption("This MVP uses simple plate-strip flexure with a two-way factor and pragmatic punching/adhesion models. Refine coefficients per project codes/tests.")
else:
    st.info("Set your inputs in the sidebar and click **Calculate** to see results.")
