# charts/plots.py
# ------------------------------------------------------------
# Minimal plotting utilities for stability-style charts.
#
# Design principles
# -----------------
# - No imports from your core app → no circular deps.
# - Pure matplotlib; caller supplies data (spacings, FoS/util).
# - Functions return a matplotlib Figure for UI layers to render
#   (e.g., Streamlit st.pyplot(fig)).
#
# Usage (example in Streamlit)
# ----------------------------
#   from charts.plots import plot_governing_vs_spacing, plot_per_mode_vs_spacing
#   fig = plot_governing_vs_spacing(s_vals, y_vals, design_mode="FOS")
#   st.pyplot(fig)
#
from __future__ import annotations

from typing import Dict, Iterable, List, Mapping, Sequence, Tuple, Union

import matplotlib.pyplot as plt


Number = Union[int, float]


def _validate_xy(x: Sequence[Number], y: Sequence[Number], name: str = "") -> None:
    if x is None or y is None:
        raise ValueError(f"{name}: x and y must be provided.")
    if len(x) != len(y):
        raise ValueError(f"{name}: x and y must be the same length (got {len(x)} vs {len(y)}).")
    if len(x) < 2:
        raise ValueError(f"{name}: need at least 2 points to plot (got {len(x)}).")


def plot_governing_vs_spacing(
    spacings_m: Sequence[Number],
    governing_values: Sequence[Number],
    *,
    design_mode: str = "FOS",
    title: str = "Governing check vs bolt spacing",
) -> plt.Figure:
    """
    Plot a single curve of the governing metric (FoS or Utilisation) vs spacing.

    Parameters
    ----------
    spacings_m      : list/array of s values [m]
    governing_values: list/array of FoS (≥1 OK) or Utilisation (≤1 OK)
    design_mode     : "FOS" or "LRFD" (only affects axis label)
    title           : figure title

    Returns
    -------
    matplotlib.figure.Figure
    """
    _validate_xy(spacings_m, governing_values, "plot_governing_vs_spacing")

    fig, ax = plt.subplots()
    ax.plot(spacings_m, governing_values, linewidth=2, marker=None)
    ax.set_xlabel("Bolt spacing s (m)")
    if (design_mode or "").upper() == "LRFD":
        ax.set_ylabel("Utilisation (≤ 1.0 is OK)")
        ax.axhline(1.0, linestyle="--", linewidth=1)
    else:
        ax.set_ylabel("Factor of Safety (≥ 1.0 is OK)")
        ax.axhline(1.0, linestyle="--", linewidth=1)

    ax.grid(True, which="both", alpha=0.35)
    ax.set_title(title)
    fig.tight_layout()
    return fig


def plot_per_mode_vs_spacing(
    spacings_m: Sequence[Number],
    per_mode_values: Mapping[str, Sequence[Number]],
    *,
    design_mode: str = "FOS",
    title: str = "Per-mode checks vs bolt spacing",
) -> plt.Figure:
    """
    Plot multiple curves (one per failure mode) vs spacing.

    Parameters
    ----------
    spacings_m    : list/array of s values [m]
    per_mode_values : mapping like:
        {
          "Adhesion": [FoS or Util at each s],
          "Flexure":  [...],
          "Punching": [...],
          "DirectShear": [...],
        }
      All series must match the length of spacings_m.
    design_mode   : "FOS" or "LRFD" (axis label only)
    title         : figure title

    Returns
    -------
    matplotlib.figure.Figure
    """
    if not per_mode_values:
        raise ValueError("per_mode_values is empty.")

    # Validate each series
    for mode_name, series in per_mode_values.items():
        _validate_xy(spacings_m, series, f"plot_per_mode_vs_spacing[{mode_name}]")

    fig, ax = plt.subplots()
    for mode_name, series in per_mode_values.items():
        ax.plot(spacings_m, series, linewidth=2, label=mode_name)

    ax.set_xlabel("Bolt spacing s (m)")
    if (design_mode or "").upper() == "LRFD":
        ax.set_ylabel("Utilisation (≤ 1.0 is OK)")
        ax.axhline(1.0, linestyle="--", linewidth=1)
    else:
        ax.set_ylabel("Factor of Safety (≥ 1.0 is OK)")
        ax.axhline(1.0, linestyle="--", linewidth=1)

    ax.grid(True, which="both", alpha=0.35)
    ax.legend(title="Failure mode")
    ax.set_title(title)
    fig.tight_layout()
    return fig


def plot_dual_governing_and_mode(
    spacings_m: Sequence[Number],
    governing_values: Sequence[Number],
    per_mode_values: Mapping[str, Sequence[Number]],
    *,
    design_mode: str = "FOS",
    title: str = "Stability overview",
) -> plt.Figure:
    """
    Convenience plot: governing curve plus faint per-mode curves beneath it.

    Parameters
    ----------
    spacings_m      : array of s values [m]
    governing_values: array of FoS or Util values
    per_mode_values : mapping of mode name -> array of values
    design_mode     : "FOS" or "LRFD"
    title           : figure title

    Returns
    -------
    matplotlib.figure.Figure
    """
    _validate_xy(spacings_m, governing_values, "plot_dual_governing_and_mode")
    for mode_name, series in per_mode_values.items():
        _validate_xy(spacings_m, series, f"plot_dual_governing_and_mode[{mode_name}]")

    fig, ax = plt.subplots()

    # Per-mode in background
    for mode_name, series in per_mode_values.items():
        ax.plot(spacings_m, series, linewidth=1.5, alpha=0.5, label=mode_name)

    # Governing on top (thicker line)
    ax.plot(spacings_m, governing_values, linewidth=2.5, label="Governing", zorder=5)

    ax.set_xlabel("Bolt spacing s (m)")
    if (design_mode or "").upper() == "LRFD":
        ax.set_ylabel("Utilisation (≤ 1.0 is OK)")
        ax.axhline(1.0, linestyle="--", linewidth=1)
    else:
        ax.set_ylabel("Factor of Safety (≥ 1.0 is OK)")
        ax.axhline(1.0, linestyle="--", linewidth=1)

    ax.grid(True, which="both", alpha=0.35)
    ax.legend(title="Curves")
    ax.set_title(title)
    fig.tight_layout()
    return fig


__all__ = [
    "plot_governing_vs_spacing",
    "plot_per_mode_vs_spacing",
    "plot_dual_governing_and_mode",
]
