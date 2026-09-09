"""Interactive browser for the registration pipeline's outputs.

Reads ``data/processed/results`` as written by :mod:`lunar_reg.results`. Nothing
here computes a match or invents a number: every value on screen was produced by
a real pipeline run and read back from disk. Where a result came from generated
imagery rather than a Chandrayaan-2 product, the page says so rather than
letting a viewer assume otherwise.

Run with::

    streamlit run dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lunar_reg.eval.conditioning import EXTRAPOLATION_GATE_PX  # noqa: E402
from lunar_reg.results import load_index, load_pair  # noqa: E402
from lunar_reg.viz.figures import (  # noqa: E402
    anaglyph,
    blend,
    checkerboard,
    coverage_heatmap,
    overlay_heatmap,
    side_by_side_matches,
    to_rgb,
)

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "data" / "processed" / "results"

st.set_page_config(page_title="Lunar Registration - SIH26166", layout="wide")

STYLE = """
<style>
  .block-container {padding-top: 2.2rem; max-width: 1500px;}
  div[data-testid="stMetricValue"] {font-size: 1.45rem;}
  .pill {display:inline-block; padding:2px 10px; border-radius:11px;
         font-size:0.74rem; font-weight:600; margin-right:6px;
         border:1px solid rgba(128,128,128,0.35);}
  .ok   {background:rgba(60,200,120,0.16);}
  .warn {background:rgba(240,170,60,0.18);}
  .bad  {background:rgba(235,80,70,0.18);}
</style>
"""
st.markdown(STYLE, unsafe_allow_html=True)


def pill(text: str, kind: str = "") -> str:
    return f'<span class="pill {kind}">{text}</span>'


@st.cache_data(show_spinner=False)
def _index(root: str):
    return load_index(root)


@st.cache_data(show_spinner=False)
def _pair(pair_id: str, root: str):
    return load_pair(pair_id, root)


def _fmt(value, digits: int = 3) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "n/a"
    return f"{value:.{digits}f}"


# --------------------------------------------------------------------------
# Sidebar: source of data and filters
# --------------------------------------------------------------------------
st.sidebar.title("Filters")
root = st.sidebar.text_input("Results directory", str(DEFAULT_ROOT))
frame = _index(root)

if not len(frame):
    st.title("Lunar Image Registration")
    st.error(
        f"No results found under `{root}`.\n\n"
        "If `.npz` files exist under `pairs/` but the index is empty or stale, "
        "rebuild it from disk:\n\n"
        "```\npython scripts/reindex_results.py\n```\n\n"
        "To generate the synthetic scene set instead:\n\n"
        "```\npython scripts/build_demo_results.py\n"
        "# then point this box at data/processed/results_ch2_synthetic_backup\n```"
    )
    st.stop()

sensors = sorted(frame["source_sensor"].dropna().unique())
matchers = sorted(frame["matcher"].dropna().unique())
references = sorted(frame["reference_sensor"].dropna().unique())

chosen_sensors = st.sidebar.multiselect("Source sensor", sensors, default=sensors)
chosen_references = st.sidebar.multiselect("Reference", references, default=references)
chosen_matchers = st.sidebar.multiselect("Matcher", matchers, default=matchers)

st.sidebar.markdown("---")
max_rmse = st.sidebar.slider("Max self-residual RMSE (px)", 0.0, 10.0, 10.0, 0.1)
min_inliers = st.sidebar.number_input("Min inliers", 0, 100_000, 0, step=10)
min_uniformity = st.sidebar.slider("Min uniformity score", 0.0, 1.0, 0.0, 0.05)
only_trusted = st.sidebar.checkbox(
    f"Only well-conditioned (p95 <= {EXTRAPOLATION_GATE_PX} px)", value=False
)

view = frame[
    frame["source_sensor"].isin(chosen_sensors)
    & frame["reference_sensor"].isin(chosen_references)
    & frame["matcher"].isin(chosen_matchers)
    & (frame.get("n_inliers", 0) >= min_inliers)
]
if "m_rmse_px" in view.columns:
    view = view[view["m_rmse_px"].fillna(np.inf) <= max_rmse]
if "u_score" in view.columns:
    view = view[view["u_score"].fillna(0) >= min_uniformity]
if only_trusted and "c_p95_px" in view.columns:
    view = view[view["c_p95_px"].fillna(np.inf) <= EXTRAPOLATION_GATE_PX]

sort_options = [c for c in (
    "pair_id", "m_rmse_px", "x_true_rms_px", "u_score", "c_p95_px", "n_inliers",
    "m_inlier_ratio",
) if c in view.columns]
sort_by = st.sidebar.selectbox("Sort by", sort_options, index=0)
ascending = st.sidebar.checkbox("Ascending", value=True)
view = view.sort_values(sort_by, ascending=ascending)

# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------
st.title("Lunar Image Registration - SIH26166")
st.caption(
    "Multi-modal, sun-angle and scale invariant correspondence for Chandrayaan-2 "
    "optical imagery. Every figure below is read from a stored pipeline run."
)

if bool(frame.get("synthetic", False).any()):
    n_synth = int(frame["synthetic"].sum())
    st.warning(
        f"**{n_synth} of {len(frame)} stored results were computed on generated "
        "scenes, not Chandrayaan-2 products.** No PDS4 product has been available "
        "to this project, so the imagery comes from a height field rendered under "
        "controlled sun angles. The pipeline, metrics and this dashboard are real; "
        "the lunar surface is not. Results marked SYNTHETIC below carry a known "
        "ground-truth transform, which is what makes the accuracy column possible."
    )

top = st.columns(4)
top[0].metric("Pairs stored", len(frame))
top[1].metric("Shown by filter", len(view))
top[2].metric("Sensors", len(sensors))
top[3].metric("Matchers", len(matchers))

# --------------------------------------------------------------------------
# (a) Browse
# --------------------------------------------------------------------------
st.subheader("Registered pairs")

display_columns = [c for c in (
    "pair_id", "source_sensor", "reference_sensor", "matcher", "n_matches",
    "n_inliers", "m_inlier_ratio", "m_rmse_px", "x_true_rms_px", "u_score",
    "c_p95_px", "x_ecc_prefilter",
) if c in view.columns]
renames = {
    "pair_id": "pair", "source_sensor": "source", "reference_sensor": "reference",
    "m_inlier_ratio": "inlier ratio", "m_rmse_px": "RMSE self (px)",
    "x_true_rms_px": "RMSE vs truth (px)", "u_score": "uniformity U",
    "c_p95_px": "extrapolation p95 (px)", "x_ecc_prefilter": "ECC prefilter",
}
st.dataframe(
    view[display_columns].rename(columns=renames),
    use_container_width=True, hide_index=True, height=300,
)

if not len(view):
    st.info("No pairs match the current filters.")
    st.stop()

# --------------------------------------------------------------------------
# (b) Selected pair
# --------------------------------------------------------------------------
st.markdown("---")
selected = st.selectbox("Inspect a pair", view["pair_id"].tolist())
row = view[view["pair_id"] == selected].iloc[0]
result = _pair(selected, root)

badges = [
    pill(f"{result.source_sensor} &rarr; {result.reference_sensor}"),
    pill(result.matcher),
]
if result.synthetic:
    badges.append(pill("SYNTHETIC", "warn"))
conditioned = row.get("c_p95_px")
if conditioned is not None and np.isfinite(conditioned):
    badges.append(
        pill(
            f"extrapolation {conditioned:.2f} px",
            "ok" if conditioned <= EXTRAPOLATION_GATE_PX else "bad",
        )
    )
st.markdown(" ".join(badges), unsafe_allow_html=True)
if result.notes:
    st.caption(result.notes)

# --- (c) metrics ----------------------------------------------------------
cols = st.columns(5)
cols[0].metric("Matches", result.n_matches)
cols[1].metric("Inliers", result.n_inliers, f"{row.get('m_inlier_ratio', 0):.0%} ratio")
cols[2].metric("RMSE, self-residual", f"{_fmt(row.get('m_rmse_px'))} px")
true_rms = row.get("x_true_rms_px")
cols[3].metric(
    "RMSE vs ground truth",
    f"{_fmt(true_rms)} px" if true_rms is not None else "n/a",
    help="Available only where a truth transform is known, i.e. synthetic scenes.",
)
cols[4].metric("Uniformity U", _fmt(row.get("u_score")))

if true_rms is not None and np.isfinite(true_rms) and row.get("m_rmse_px"):
    ratio = row["m_rmse_px"] / max(true_rms, 1e-9)
    st.caption(
        f"The self-residual is **{ratio:.0f}x** the true error on this pair. "
        "Makharia et al. (arXiv:2509.04775) report the self-residual only; the two "
        "columns are different measurements and are not comparable."
    )

# --- (b) side by side -----------------------------------------------------
st.markdown("### Correspondences")
controls = st.columns([1, 1, 2])
max_lines = controls[0].slider("Lines drawn", 10, 400, 120, 10)
show_outliers = controls[1].checkbox("Show outliers", value=True)
controls[2].markdown(
    f"{pill('inliers', 'ok')} {pill('rejected by RANSAC', 'bad')}", unsafe_allow_html=True
)

scale = float(result.extra.get("source_scale", 1.0))
st.image(
    side_by_side_matches(
        result.source_image, result.reference_image,
        result.src_pts, result.dst_pts, result.inlier_mask,
        max_lines=max_lines, scale=scale, draw_outliers=show_outliers,
    ),
    use_container_width=True,
    caption=f"{result.n_inliers} inliers of {result.n_matches} matches "
            f"({min(max_lines, result.n_matches)} drawn)",
)

# --- (d) overlay ----------------------------------------------------------
st.markdown("### Alignment check")
left, right = st.columns([1, 3])
mode = left.radio(
    "Overlay", ["Checkerboard", "Blend", "Red/cyan anaglyph", "Warped only"], index=0
)
tile = left.slider("Checker tile (px)", 16, 160, 64, 8) if mode == "Checkerboard" else 64
alpha = left.slider("Blend weight", 0.0, 1.0, 0.5, 0.05) if mode == "Blend" else 0.5
left.caption(
    "Checkerboard is the strictest check: a crater rim crossing a tile edge either "
    "continues or steps. A blend hides a one-pixel error as softness."
)

source, reference = result.source_image, result.reference_image
transform = result.transform
if mode == "Checkerboard":
    overlay = checkerboard(source, reference, transform, tile=tile)
elif mode == "Blend":
    overlay = blend(source, reference, transform, alpha=alpha)
elif mode == "Red/cyan anaglyph":
    overlay = anaglyph(source, reference, transform)
else:
    from lunar_reg.viz.figures import warp_source

    overlay = to_rgb(warp_source(source, transform, reference.shape[:2]))
right.image(overlay, use_container_width=True)

# --- where the answer is trustworthy --------------------------------------
st.markdown("### Where the registration is trustworthy")
st.caption(
    "Bootstrap resampling of the correspondences, refitting each time, and measuring "
    "how far the predictions wander. Cool means the correspondences pin the transform "
    "down there; hot means it is extrapolating. Colour is scaled against the "
    f"{EXTRAPOLATION_GATE_PX} px gate, so two pairs can be compared by eye. This is "
    "the part a single RMSE cannot show."
)
heat_left, heat_right = st.columns(2)
inliers = result.inlier_mask if result.inlier_mask is not None else np.ones(
    result.n_matches, dtype=bool
)
if inliers.sum() >= 8:
    from lunar_reg.eval.conditioning import conditioning_map

    spread = conditioning_map(
        result.src_pts[inliers], result.dst_pts[inliers], result.source_image.shape[:2]
    )
    heat = coverage_heatmap(spread, result.source_image.shape[:2])
    heat_left.image(
        overlay_heatmap(result.source_image, heat),
        use_container_width=True, caption="cool = constrained, hot = extrapolated",
    )
    scatter = to_rgb(result.source_image).copy()
    import cv2

    for x, y in (result.src_pts[inliers] * scale):
        cv2.circle(scatter, (int(x), int(y)), 2, (60, 220, 120), -1, cv2.LINE_AA)
    heat_right.image(
        scatter, use_container_width=True,
        caption=f"{int(inliers.sum())} inlier keypoints on the source",
    )
else:
    st.info("Too few inliers to estimate conditioning for this pair.")

with st.expander("Full stored record"):
    st.json({
        "metrics": result.metrics,
        "uniformity": result.uniformity,
        "conditioning": result.conditioning,
        "extra": result.extra,
        "transform": np.asarray(result.transform).tolist(),
    })
