"""Named preprocessing presets that run inside :func:`lunar_reg.pipeline.register_pair`.

A preset is a radiometric chain applied identically to both images of a pair
just before matching (Phase_1/LLD/preprocess_presets.md §1, CONTRACTS C12):

* ``none`` -- the inputs as they are (non-uint8 input is stretched to uint8);
* ``ohrc_nac`` -- the Makharia et al. OHRC/NAC chain: normalize -> CLAHE ->
  invert -> dilate (paper structure; several parameters are PLACEHOLDERS);
* ``clahe_shadow`` -- normalize -> shadow lift (gamma) -> CLAHE.

No preset runs a geometric step: pair preparation already fixed the GSD, so
pixel coordinates found on the preprocessed images are input coordinates.
Outputs are uint8 with 0 reserved for nodata.

A preset that fails on either side (a FAILED or DEGENERATE_OUTPUT step) is a
classified outcome, not an exception: :class:`PresetOutcome` carries ``ok``,
the first failing step in ``detail``, and every step's status in ``history``.
A non-``none`` preset whose output has fewer than two distinct values over the
valid pixels of a side is also DEGENERATE_OUTPUT (step ``output_check``).
Non-finite pixels of a float input are always nodata.

:func:`choose_default_preset` is the ablation rule P1.19 applies to the P1.18
artefact (LLD §3).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, replace

import numpy as np

from lunar_reg.preprocess.config import PreprocessConfig, ohrc_nac_config
from lunar_reg.preprocess.pipeline import PreprocessContext, StepStatus, run_pipeline
from lunar_reg.preprocess.radiometric import to_uint8

logger = logging.getLogger(__name__)

PRESET_NAMES = ("none", "ohrc_nac", "clahe_shadow")

#: Anchor targets a row must meet to count as a pass (CLARIFY Q18, LLD §3).
ANCHOR_MIN_INLIERS = 20
ANCHOR_MIN_U_SCORE = 0.7


@dataclass
class PresetOutcome:
    """What a preset did to one pair (CONTRACTS C12).

    ``source`` / ``reference`` are uint8, same shape as the inputs, 0 = nodata;
    both are None when ``ok`` is False. ``history`` holds one dict per step and
    side: ``{"side", "step", "status", "reason"}`` with ``status`` a
    :class:`~lunar_reg.preprocess.pipeline.StepStatus` value.
    """

    ok: bool
    source: np.ndarray | None  # uint8, same shape as input
    reference: np.ndarray | None
    detail: str
    history: list[dict]  # per side: {"side", "step", "status", "reason"}
    uses_placeholders: list[str]  # names of PLACEHOLDER params actually used

    def report(self) -> str:
        """One header line, then step outcome counts per side and the first failure."""
        head = "preset: ok" if self.ok else f"preset: FAILED  {self.detail}"
        lines = [head]
        for side in ("source", "reference"):
            counts: dict[str, int] = {}
            for rec in self.history:
                if rec["side"] == side:
                    counts[rec["status"]] = counts.get(rec["status"], 0) + 1
            summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "no steps"
            lines.append(f"  {side}: {summary}")
        if self.uses_placeholders:
            lines.append(f"  placeholders used: {', '.join(self.uses_placeholders)}")
        return "\n".join(lines)


def preset_config(name: str) -> PreprocessConfig | None:
    """The :class:`PreprocessConfig` a preset runs (None for ``none``).

    Raises ``ValueError`` for an unknown name.
    """
    _check_name(name)
    if name == "none":
        return None
    if name == "ohrc_nac":
        # normalize -> clahe -> invert -> dilate; no geometric step (LLD §1).
        return replace(ohrc_nac_config(resample=False, georeference=False), label="preset/ohrc_nac")
    # clahe_shadow: normalize -> shadow (gamma) -> clahe.
    return PreprocessConfig(
        label="preset/clahe_shadow",
        georeference=False,
        band_reduction=False,
        resample=False,
        normalize=True,
        histogram_match=False,
        shadow=True,
        shadow_method="gamma",
        clahe=True,
        invert=False,
        dilate=False,
        log_transform=False,
    )


def _check_name(name: str) -> None:
    if name not in PRESET_NAMES:
        raise ValueError(f"unknown preset {name!r}; choose one of {PRESET_NAMES}")


def _valid_mask(image: np.ndarray, valid, nodata: float | None) -> np.ndarray:
    """Given mask, else ``image != nodata`` when nodata is set, else all True.

    For a floating-point image the result is also ANDed with ``isfinite(image)``
    in every branch (Phase_1/LLD/preprocess_nodata.md §1: effective valid =
    valid & isfinite), so NaN/inf pixels are nodata (0) in the preset output; a
    NaN ``nodata`` therefore means "not NaN".
    """
    if valid is not None:
        mask = np.asarray(valid, dtype=bool)
        if mask.shape != image.shape:
            raise ValueError(f"valid mask shape {mask.shape} != image shape {image.shape}")
        mask = mask.copy()
    elif nodata is not None and not (isinstance(nodata, float) and math.isnan(nodata)):
        mask = np.asarray(image != nodata)
    else:
        mask = np.ones(image.shape, dtype=bool)
    if np.issubdtype(image.dtype, np.inexact):
        mask &= np.isfinite(image)
    return mask


def _constant_output(out: np.ndarray, valid: np.ndarray) -> str | None:
    """Why a preset output is degenerate for matching, or None.

    A side whose valid pixels hold fewer than two distinct values (e.g. an
    all-zero or flat image when ``nodata`` is None, which ``to_uint8`` maps to a
    constant 1) carries no structure; it is classified as ``degenerate_output``
    instead of reaching the matcher as a flat block.
    """
    values = out[valid]
    if values.size == 0:
        return "no valid pixel in the preset output"
    if np.unique(values).size < 2:
        return f"valid pixels of the preset output are constant ({int(values[0])})"
    return None


def apply_preset(
    name: str,
    source,
    reference,
    *,
    source_valid=None,
    reference_valid=None,
    nodata: float | None = 0,
) -> PresetOutcome:
    """Run preset ``name`` on both images of a pair (CONTRACTS C12, LLD §1).

    Never raises for a bad image: a failing or degenerate step on either side
    gives ``ok=False`` with ``detail`` naming the first such step. Raises
    ``ValueError`` for an unknown preset name or a mask whose shape differs from
    its image (caller errors).
    """
    _check_name(name)
    source = np.asarray(source)
    reference = np.asarray(reference)
    src_valid = _valid_mask(source, source_valid, nodata)
    ref_valid = _valid_mask(reference, reference_valid, nodata)

    if name == "none":
        outputs: list[np.ndarray] = []
        history: list[dict] = []
        for side, image, valid in (
            ("source", source, src_valid),
            ("reference", reference, ref_valid),
        ):
            if image.dtype == np.uint8:
                outputs.append(image.copy())
                history.append(
                    {
                        "side": side,
                        "step": "copy",
                        "status": StepStatus.NOOP.value,
                        "reason": "uint8 input passed through unchanged",
                    }
                )
            else:
                outputs.append(to_uint8(image, valid=valid))
                history.append(
                    {
                        "side": side,
                        "step": "normalize",
                        "status": StepStatus.RAN.value,
                        "reason": "",
                    }
                )
        logger.debug("preset 'none': inputs passed through")
        return PresetOutcome(True, outputs[0], outputs[1], "", history, [])

    config = preset_config(name)
    results = {}
    for side, image, valid, other, other_valid in (
        ("source", source, src_valid, reference, ref_valid),
        ("reference", reference, ref_valid, source, src_valid),
    ):
        context = PreprocessContext(reference_image=other, valid=valid, reference_valid=other_valid)
        results[side] = run_pipeline(image, replace(config, side=side), context)

    history = [
        {"side": side, "step": r.name, "status": r.status.value, "reason": r.reason}
        for side, result in results.items()
        for r in result.history
    ]
    placeholders = sorted(
        set(results["source"].uses_placeholders) | set(results["reference"].uses_placeholders)
    )

    failure = next(
        (
            f"{side}: {r.name}: {r.status.value}: {r.reason}"
            for side, result in results.items()
            for r in result.history
            if r.status.is_failure
        ),
        None,
    )
    if failure is None:
        outputs = []
        for side, image, valid in (
            ("source", source, src_valid),
            ("reference", reference, ref_valid),
        ):
            out = results[side].image
            if out.shape != image.shape:
                failure = f"{side}: preset {name!r} changed the shape {image.shape} -> {out.shape}"
                break
            if out.dtype != np.uint8:
                out = to_uint8(out, valid=valid)
            out = np.where(valid, out, 0).astype(np.uint8)
            why = _constant_output(out, valid)
            if why is not None:
                status = StepStatus.DEGENERATE_OUTPUT.value
                history.append(
                    {"side": side, "step": "output_check", "status": status, "reason": why}
                )
                failure = f"{side}: output_check: {status}: {why}"
                break
            outputs.append(out)

    if failure is not None:
        logger.warning("preset %r failed: %s", name, failure)
        return PresetOutcome(False, None, None, failure, history, placeholders)
    logger.debug("preset %r: ok, %d step record(s)", name, len(history))
    return PresetOutcome(True, outputs[0], outputs[1], "", history, placeholders)


# ---------------------------------------------------------------------------
# Ablation rule (LLD §3), applied by P1.19 to the P1.18 ablation.json
# ---------------------------------------------------------------------------


def _anchor_pass(rows: list[dict], preset: str) -> int:
    return sum(
        1
        for r in rows
        if r.get("preset") == preset
        and r.get("status") == "ok"
        and (r.get("n_inliers") or 0) >= ANCHOR_MIN_INLIERS
        and (r.get("u_score") or 0.0) >= ANCHOR_MIN_U_SCORE
    )


def _median_truth_rms(rows: list[dict], preset: str) -> float | None:
    values = [
        float(r["truth_rms_px"])
        for r in rows
        if r.get("preset") == preset
        and r.get("status") == "ok"
        and r.get("truth_rms_px") is not None
        and math.isfinite(float(r["truth_rms_px"]))
    ]
    return float(np.median(values)) if values else None


def choose_default_preset(ablation: dict) -> tuple[str, str]:
    """Pick the default preset from the P1.18 ablation artefact (LLD §3).

    1. ``anchor_pass(p)``: anchor rows of ``p`` with ``status == "ok"``,
       ``n_inliers >= 20`` and ``u_score >= 0.7``.
    2. Candidates: the presets with the most anchor passes.
    3. Tie-break: lowest median ``truth_rms_px`` over OK synthetic rows; a
       preset with no OK synthetic row ranks last.
    4. Still tied: ``none`` if it is a candidate, else the first in
       :data:`PRESET_NAMES` order.
    5. Guard: never a winner with fewer anchor passes than ``none``.

    Returns ``(winner, reason)``; ``reason`` states the numbers used. Raises
    ``ValueError`` when a row names a preset outside :data:`PRESET_NAMES`.
    """
    anchor = list(ablation.get("anchor", []))
    synthetic = list(ablation.get("synthetic", []))
    unknown = sorted({str(r.get("preset")) for r in anchor + synthetic} - set(PRESET_NAMES))
    if unknown:
        raise ValueError(f"ablation rows name unknown preset(s) {unknown}; known: {PRESET_NAMES}")

    passes = {p: _anchor_pass(anchor, p) for p in PRESET_NAMES}
    reason = "anchor passes " + " ".join(f"{p}={passes[p]}" for p in PRESET_NAMES)
    best = max(passes.values())
    candidates = [p for p in PRESET_NAMES if passes[p] == best]

    if len(candidates) == 1:
        winner = candidates[0]
        reason += f"; {winner} wins on anchor"
    else:
        medians = {p: _median_truth_rms(synthetic, p) for p in candidates}
        reason += (
            f"; anchor tie between {', '.join(candidates)}; median synthetic truth_rms_px "
            + (" ".join(f"{p}={'n/a' if m is None else f'{m:.4g}'}" for p, m in medians.items()))
        )
        ranked = [m for m in medians.values() if m is not None]
        if ranked:
            low = min(ranked)
            candidates = [p for p in candidates if medians[p] is not None and medians[p] == low]
        if len(candidates) == 1:
            winner = candidates[0]
            reason += f"; {winner} wins on synthetic"
        else:
            winner = "none" if "none" in candidates else candidates[0]
            reason += f"; still tied ({', '.join(candidates)}) -> {winner}"

    assert passes[winner] >= passes["none"], "step 2 guarantees the winner passes as often as none"
    if passes[winner] < passes["none"]:  # pragma: no cover - guard kept per LLD §3 step 5
        winner = "none"
    return winner, reason


__all__ = [
    "ANCHOR_MIN_INLIERS",
    "ANCHOR_MIN_U_SCORE",
    "PRESET_NAMES",
    "PresetOutcome",
    "apply_preset",
    "choose_default_preset",
    "preset_config",
]
