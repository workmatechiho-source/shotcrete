# export/excel.py
# ------------------------------------------------------------
# Excel export utilities for the shotcrete design tool.
#
# What this file provides
# -----------------------
# - build_input_table(inp)           → pandas.DataFrame of inputs
# - build_results_table(result)      → pandas.DataFrame of per-mode checks
# - build_derived_table(result)      → pandas.DataFrame of derived values
# - export_to_excel_bytes(inp, res)  → bytes of an .xlsx workbook with:
#       * "Summary" sheet (governing outcome)
#       * "Inputs"  sheet
#       * "Results" sheet (per-mode)
#       * "Derived" sheet (t_eff, W_total, w)
#   Optional: include an extra sheet with a spacing sweep if you pass it in.
#
# Dependencies: pandas, numpy, xlsxwriter (pandas uses it as engine)
#
from __future__ import annotations

from io import BytesIO
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple

import pandas as pd
import numpy as np

# Import dataclasses for typing & dict access (no heavy logic here)
from core.models import DesignInput, DesignResult, ModeResult, DesignMode


# -----------------------------
# Table builders (pandas)
# -----------------------------
def build_input_table(inp: DesignInput) -> pd.DataFrame:
    """
    Flatten DesignInput into a tidy one-column table for Excel.
    """
    data = {
        "Parameter": [
            "Design mode",
            "Bolt spacing s (m)",
            "Thickness t (m)",
            "Effective plate width c (m)",
            "Rock unit weight γ (kN/m³)",
            "Load model",
            "Geology preset",
            "θ (deg) (pyramid/shale)",
            "h_block (m) (flat)",
            "Adhesive length a_bond (m)",
            "f_c (MPa)",
            "τ_b (MPa)",
            "f_r (MPa)",
            "τ_v (MPa)",
            "v_rd (MPa)",
            "φ_flexure",
            "φ_shear",
            "φ_punching",
            "γ_load",
            "Durability deduction (m)",
            "Age label",
            "Notes",
        ],
        "Value": [
            inp.factors.mode.value,
            inp.s,
            inp.t,
            inp.c,
            inp.gamma_rock,
            inp.load_model.value,
            inp.geology_preset.value,
            inp.theta_deg,
            inp.h_block,
            inp.a_bond,
            inp.materials.f_c,
            inp.materials.tau_b,
            inp.materials.f_r,
            inp.materials.tau_v,
            inp.materials.v_rd,
            inp.factors.phi_flexure,
            inp.factors.phi_shear,
            inp.factors.phi_punching,
            inp.factors.gamma_load,
            inp.factors.t_dur_deduction,
            inp.age_label,
            inp.notes,
        ],
    }
    return pd.DataFrame(data)


def build_results_table(result: DesignResult, mode: DesignMode) -> pd.DataFrame:
    """
    Build a per-mode results table suitable for Excel.
    """
    rows = []
    for name, mr in result.modes.items():
        rows.append({
            "Mode": name,
            "Demand": mr.demand,
            "Capacity": mr.capacity,
            "FoS": (mr.fos if mr.fos is not None else np.nan),
            "Utilisation": (mr.utilization if mr.utilization is not None else np.nan),
            "Pass": mr.passes,
            "Detail": mr.detail,
        })
    df = pd.DataFrame(rows)
    # Order columns for clarity
    if mode == DesignMode.FOS:
        df = df[["Mode", "Demand", "Capacity", "FoS", "Pass", "Detail"]]
    else:
        df = df[["Mode", "Demand", "Capacity", "Utilisation", "Pass", "Detail"]]
    return df


def build_derived_table(result: DesignResult) -> pd.DataFrame:
    """
    Collect derived scalars (effective thickness, loads, etc.).
    """
    d = {
        "Quantity": [],
        "Value": [],
        "Unit": [],
    }
    teff = result.derived.get("t_eff", np.nan)
    Wtot = result.derived.get("W_total_kN", np.nan)
    wuni = result.derived.get("w_kNpm2", np.nan)

    d["Quantity"] += ["Effective thickness t_eff", "Total panel load W_total", "Uniform load w"]
    d["Value"] += [teff, Wtot, wuni]
    d["Unit"] += ["m", "kN", "kN/m²"]

    return pd.DataFrame(d)


# -----------------------------
# Excel writer
# -----------------------------
def export_to_excel_bytes(
    inp: DesignInput,
    result: DesignResult,
    *,
    spacing_sweep: Optional[Tuple[Sequence[float], Sequence[float]]] = None,
    design_mode: Optional[DesignMode] = None,
) -> bytes:
    """
    Create an in-memory .xlsx workbook with summary, inputs, results, and derived.
    Optionally include a SpacingSweep sheet with (s, governing metric).

    Parameters
    ----------
    inp           : DesignInput
    result        : DesignResult
    spacing_sweep : optional tuple (s_vals, y_vals)
                    where s_vals are spacings [m] and y_vals are FoS or Utilisation.
    design_mode   : override result mode label on the chart axes, if provided.

    Returns
    -------
    bytes
        The content of the .xlsx file, ready for download or saving.
    """
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as writer:
        # Sheets
        # 1) Summary
        _write_summary_sheet(writer, inp, result, design_mode)

        # 2) Inputs
        build_input_table(inp).to_excel(writer, sheet_name="Inputs", index=False)

        # 3) Results
        build_results_table(result, mode=inp.factors.mode).to_excel(writer, sheet_name="Results", index=False)

        # 4) Derived
        build_derived_table(result).to_excel(writer, sheet_name="Derived", index=False)

        # 5) Optional spacing sweep
        if spacing_sweep is not None:
            s_vals, y_vals = spacing_sweep
            _write_spacing_sweep_sheet(writer, s_vals, y_vals, design_mode or inp.factors.mode)

        # Post-format tweaks (set column widths for first few sheets)
        _autofit_columns(writer, "Inputs")
        _autofit_columns(writer, "Results")
        _autofit_columns(writer, "Derived")

    return bio.getvalue()


# -----------------------------
# Helpers (xlsxwriter formatting)
# -----------------------------
def _write_summary_sheet(
    writer: pd.ExcelWriter,
    inp: DesignInput,
    result: DesignResult,
    design_mode: Optional[DesignMode] = None,
) -> None:
    ws = writer.book.add_worksheet("Summary")
    writer.sheets["Summary"] = ws

    # Formats
    h1 = writer.book.add_format({"bold": True, "font_size": 14})
    h2 = writer.book.add_format({"bold": True, "font_size": 12})
    lab = writer.book.add_format({"bold": True})
    okf = writer.book.add_format({"bold": True, "font_color": "#007700"})
    nof = writer.book.add_format({"bold": True, "font_color": "#AA0000"})

    # Title
    ws.write(0, 0, "Shotcrete Support Design — Summary", h1)

    # Governing
    ws.write(2, 0, "Design mode:", lab)
    ws.write(2, 1, (design_mode or inp.factors.mode).value)

    ws.write(3, 0, "Governing mode:", lab)
    ws.write(3, 1, result.governing_mode)

    ws.write(4, 0, "Governing value:", lab)
    ws.write_number(4, 1, float(result.governing_value))

    ws.write(5, 0, "Overall status:", lab)
    ws.write(5, 1, "OK" if result.ok else "NOT OK", okf if result.ok else nof)

    # Key inputs (short list)
    ws.write(7, 0, "Key inputs", h2)
    key_inputs = [
        ("Bolt spacing s (m)", inp.s),
        ("Thickness t (m)", inp.t),
        ("Effective plate width c (m)", inp.c),
        ("Rock unit weight γ (kN/m³)", inp.gamma_rock),
        ("Load model", inp.load_model.value),
        ("Geology preset", inp.geology_preset.value),
        ("θ (deg)", inp.theta_deg),
        ("h_block (m)", inp.h_block),
        ("Adhesive length a_bond (m)", inp.a_bond),
        ("Durability deduction (m)", inp.factors.t_dur_deduction),
    ]
    row = 8
    for label, val in key_inputs:
        ws.write(row, 0, label)
        if isinstance(val, (int, float)):
            ws.write_number(row, 1, float(val))
        else:
            ws.write(row, 1, str(val))
        row += 1

    # Per-mode compact view
    ws.write(row + 1, 0, "Per-mode checks", h2)
    row += 2
    headers = ["Mode", "Demand", "Capacity", "FoS", "Utilisation", "Pass", "Detail"]
    for j, h in enumerate(headers):
        ws.write(row, j, h, lab)
    row += 1
    for name, mr in result.modes.items():
        ws.write(row, 0, name)
        ws.write_number(row, 1, float(mr.demand))
        ws.write_number(row, 2, float(mr.capacity))
        ws.write(row, 3, "" if mr.fos is None else float(mr.fos))
        ws.write(row, 4, "" if mr.utilization is None else float(mr.utilization))
        ws.write(row, 5, "Yes" if (mr.passes is True) else ("No" if (mr.passes is False) else ""))
        ws.write(row, 6, mr.detail or "")
        row += 1

    # Column widths
    ws.set_column(0, 0, 28)  # labels
    ws.set_column(1, 2, 16)
    ws.set_column(3, 5, 14)
    ws.set_column(6, 6, 60)


def _write_spacing_sweep_sheet(
    writer: pd.ExcelWriter,
    s_vals: Sequence[float],
    y_vals: Sequence[float],
    design_mode: DesignMode,
) -> None:
    """
    Writes a sheet "SpacingSweep" with two columns (s, y) and a simple line chart.
    """
    df = pd.DataFrame({"s (m)": list(s_vals), ("FoS" if design_mode == DesignMode.FOS else "Utilisation"): list(y_vals)})
    df.to_excel(writer, sheet_name="SpacingSweep", index=False)
    ws = writer.sheets["SpacingSweep"]

    # Add a chart
    chart = writer.book.add_chart({"type": "line"})
    # Data range (xlsxwriter is 0-indexed rows, but Excel A1 ranges below use 1-based headers)
    n = len(df)
    chart.add_series({
        "name":       [ "SpacingSweep", 0, 1 ],
        "categories": [ "SpacingSweep", 1, 0, n, 0 ],
        "values":     [ "SpacingSweep", 1, 1, n, 1 ],
        "line":       {"width": 2.25},
    })
    chart.set_title({"name": "Governing vs Spacing"})
    chart.set_x_axis({"name": "Bolt spacing s (m)"})
    chart.set_y_axis({"name": "FoS (≥1 OK)" if design_mode == DesignMode.FOS else "Utilisation (≤1 OK)"})
    chart.set_legend({"position": "bottom"})
    ws.insert_chart("D2", chart, {"x_scale": 1.3, "y_scale": 1.2})


def _autofit_columns(writer: pd.ExcelWriter, sheet_name: str) -> None:
    """
    Best-effort column auto-fit for a given sheet (works on already-written DataFrame).
    """
    ws = writer.sheets.get(sheet_name)
    if ws is None:
        return
    # We don't have direct text measurement; use simple heuristics
    # Find the DataFrame back via the workbook? Not available; so set some defaults
    if sheet_name == "Inputs":
        ws.set_column(0, 0, 34)  # Parameter
        ws.set_column(1, 1, 40)  # Value
    elif sheet_name == "Results":
        ws.set_column(0, 0, 16)  # Mode
        ws.set_column(1, 2, 18)  # Demand/Capacity
        ws.set_column(3, 4, 16)  # FoS/Utilisation
        ws.set_column(5, 5, 10)  # Pass
        ws.set_column(6, 6, 60)  # Detail
    elif sheet_name == "Derived":
        ws.set_column(0, 0, 28)
        ws.set_column(1, 1, 18)
        ws.set_column(2, 2, 12)
