# Shotcrete Support Design Tool (MVP)

This is a Streamlit-based tool to check shotcrete support in blocky ground.
It implements the deterministic framework from Barrett & McCreath (1995),
updated with corrections from Christine et al. (2017).

---

## Features
- **Four failure modes**: Adhesion, Flexure, Punching shear, Direct shear.
- **Load models**:
  - Pyramid wedge (~60° sides, 1995).
  - Flat block (Hawkesbury-style, 2017).
  - Shale wedge (variable side angles, 2017).
- **Design modes**: Factor of Safety (FoS) and LRFD (φ–γ format).
- **UI**: Streamlit web interface with sidebar inputs and results table.
- **Charts**: Stability-style plots (spacing sweep).
- **Exports**: Download results as Excel `.xlsx` with summary, inputs, results, and derived values.
- **Tests**: Simple pytest smoke tests to verify behaviour.

---

## Repo structure
```text
shotcrete-tool/
├─ streamlit_app.py           # Streamlit entry point (UI)
├─ core/
│  ├─ models.py               # Dataclasses for inputs, materials, results
│  ├─ loads.py                # Block/wedge load models (1995 vs 2017)
│  ├─ capacities.py           # Adhesion, flexure, punching, shear formulas
│  ├─ design.py               # Orchestrates load + capacity → DesignResult
│  └─ codes.py                # Placeholder for code-based factors (φ, γ, fibres)
├─ charts/
│  └─ plots.py                # Stability chart plotting helpers
├─ export/
│  └─ excel.py                # Excel export utilities
├─ tests/
│  └─ test_smoke.py           # Pytest smoke checks
├─ requirements.txt
└─ README.md