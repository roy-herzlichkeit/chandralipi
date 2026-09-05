# assets/ — logo sources

All logos are available as `.png` (512×512, transparent background — use these for the PPTX) alongside the original `.svg` where one was fetched. `chandrayaan2.png` was only ever available as PNG (500×63 wordmark).

Fetched for the P26166 tech-stack / references slides. Direct downloads from official-brand icon sets or Wikimedia Commons (public domain / CC-licensed government and open-source project marks). Re-check each org's brand guidelines before using in anything beyond an internal/academic slide deck.

| File | Represents | Source |
|---|---|---|
| `python.svg` | Python | Simple Icons (cdn.simpleicons.org) |
| `opencv.svg` | OpenCV | Simple Icons |
| `pytorch.svg` | PyTorch | Simple Icons |
| `numpy.svg` | NumPy | Simple Icons |
| `streamlit.svg` | Streamlit (demo UI) | Simple Icons |
| `gdal.svg` | GDAL | Simple Icons |
| `nvidia.svg` | NVIDIA (for RTX 4060 / RTX 3060 GPU chips — no separate per-model logo exists) | Simple Icons |
| `cuda.png` | CUDA (GPU compute) | Wikimedia Commons — *Nvidia CUDA Logo.jpg*, background keyed to transparent. Native res is 406×246 — small but a clean vector-style badge, so it holds up fine at typical logo-chip sizes. |
| `isro.svg` | ISRO | Wikimedia Commons — *Indian Space Research Organisation Logo.svg* |
| `chandrayaan2.png` | Chandrayaan-2 mission | Wikimedia Commons — *Chandrayaan-2 logo.png* |
| `nasa.svg` | NASA (for LRO NAC reference data) | Wikimedia Commons — *NASA logo.svg* (public domain, US federal work) |
| `jaxa.svg` | JAXA (for SELENE/Kaguya reference data) | Wikimedia Commons — *Jaxa logo.svg* |

## Sample data image

- `ohrc_vikram.png` (5410×3567) — a real OHRC-captured image: the Chandrayaan-3 Vikram lander on the lunar surface (69.373°S, 32.319°E), taken by Chandrayaan-2's Orbiter High Resolution Camera on 2023-08-23. Source: Wikimedia Commons, credited to ISRO (isro.gov.in/chandrayaan3_gallery.html). **Licensed under GODL-India (Government Open Data License – India) — attribution required if used publicly:** *"Indian Space Research Organisation (GODL-India)"*. Good for a "what OHRC actually resolves" visual on the Technical Approach or dataset slide — it carries ISRO's own watermark and scale bar (35 m), so it reads as authentic rather than a stock photo.

## The orbiter itself

- `chandrayaan2_orbiter.jpg` (6016×4016) — a real pre-launch photo of the Chandrayaan-2 orbiter spacecraft in the clean room (gold thermal blanketing visible, engineers for scale), not a render. Source: Wikimedia Commons, credited to PRL (prl.res.in/ch2xsm/gallery). **GODL-India licensed — attribution required for public use:** *"Indian Space Research Organisation (GODL-India)"*.

## Not fetched — no official logo exists

- **rasterio** — checked the project's GitHub repo directly; a community-proposed logo (PR #2797) was never merged, so there is no official mark. Use `gdal.svg` to represent the "rasterio/GDAL" chip, or leave it as text.
- **LoFTR**, **SuperPoint + SuperGlue**, **Phase-congruency / RIFT-style matching**, **OpenCV RANSAC** — these are algorithms/research papers, not branded products, so no logo exists. `opencv.svg` already covers the RANSAC chip (it's an OpenCV function). For LoFTR/SuperGlue/RIFT you'd need each paper's GitHub repo avatar if you want *something* visual, but that's a repo icon, not a logo — flagging rather than fabricating one.
