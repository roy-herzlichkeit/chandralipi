# Roadmap — how to understand this project

You know software engineering. You do not know geodesy, remote sensing, or
planetary data formats. These notes assume exactly that.

Nothing here is required by the pipeline. It is gitignored and written for one
reader. Read in the order below; each doc assumes only the ones before it.

```mermaid
flowchart TD
    A["<b>01 · What & why</b><br/>the ISRO problem<br/><i>~10 min</i>"] --> B["<b>13 · Sensors</b><br/>what a pushbroom camera is<br/><i>~10 min</i>"]
    B --> C["<b>31 · Instruments</b><br/>OHRC, TMC-2, IIRS, LRO<br/><i>~5 min</i>"]
    C --> D["<b>10 · Geodesy</b><br/>lat/lon is not x/y<br/><i>~15 min</i>"]
    D --> E["<b>11 · Projections</b><br/>flattening a sphere<br/><i>~10 min</i>"]
    D --> F["<b>12 · Footprints</b><br/>polygons and area<br/><i>~10 min</i>"]
    E --> G["<b>30 · PDS4 & PRADAN</b><br/>how the data arrives<br/><i>~10 min</i>"]
    F --> G
    G --> H["<b>20 · Transforms</b><br/>affine vs homography<br/><i>~15 min</i>"]
    H --> I["<b>21 · Matching</b><br/>SIFT to LoFTR<br/><i>~15 min</i>"]
    I --> J["<b>22 · Robust fitting</b><br/>RANSAC and ECC<br/><i>~10 min</i>"]
    J --> K["<b>23 · Metrics</b><br/>why RMSE lies<br/><i>~15 min</i>"]
    K --> L["<b>40 · The pipeline</b><br/>code walkthrough<br/><i>~15 min</i>"]
    L --> M["<b>50 · Findings</b><br/>what we measured<br/><i>~10 min</i>"]
    M --> N["<b>90 · Glossary</b><br/>keep open throughout"]

    style A fill:#1A1F71,color:#ffffff
    style M fill:#F7B600,color:#1A1F71
    style N fill:#F7F5F0,color:#1A1F71
```

## If you only have an hour

**01 → 13 → 20 → 23 → 50.** The problem, the hardware, the maths that turned out
to matter most, why our metrics are unusual, and what we actually learned.

## If you are presenting this to a panel

**01 → 23 → 50.** Everything a judge is likely to probe: what was asked, why the
obvious metric is insufficient, and what we measured that others did not.

## The four ideas that carry the whole project

If you retain nothing else:

| # | Idea | Doc |
|---|---|---|
| 1 | Latitude/longitude are **angles**, not distances. Longitude lines converge; near a pole everything Cartesian breaks | 10 |
| 2 | A **pushbroom** sensor has no single viewpoint, so no single perspective transform describes it | 13, 20 |
| 3 | **Illumination inverts features.** Move the sun and the lit crater wall becomes the dark one — descriptors key on exactly what changed | 01, 21 |
| 4 | RMSE measured on the points you fitted to is **not accuracy**. It barely notices *where* those points are | 23 |

## Conventions in these notes

- **Measured** means a number this project produced from a run. It names the module.
- **Documented** means it comes from a paper or standard we read.
- **Unverified** means nobody has checked it. Said explicitly, never smoothed over.
