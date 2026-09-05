# Roadmap — how to understand this project

You know software engineering. You do not know geodesy, remote sensing, or
planetary data formats. These notes assume exactly that, and **every term is
defined in plain English at the point it is first used** — if a sentence here
needs background you do not have, that is a bug in the doc, not in you.

Nothing here is required by the pipeline. It is gitignored and written for one
reader. Read in the order below; each doc assumes only the ones before it.

```mermaid
flowchart TD
    A["<b>01 · What &amp; why</b><br/>the ISRO problem<br/><i>~10 min</i>"] --> B["<b>13 · Sensors</b><br/>what a pushbroom camera is<br/><i>~10 min</i>"]
    B --> C["<b>31 · Instruments</b><br/>OHRC, TMC-2, IIRS, LRO<br/><i>~10 min</i>"]
    C --> D["<b>10 · Geodesy</b><br/>lat/lon is not x/y<br/><i>~15 min</i>"]
    D --> E["<b>11 · Projections</b><br/>flattening a sphere<br/><i>~10 min</i>"]
    D --> F["<b>12 · Footprints</b><br/>polygons and area<br/><i>~10 min</i>"]
    E --> G["<b>30 · PDS4 &amp; PRADAN</b><br/>how the data arrives<br/><i>~15 min</i>"]
    F --> G
    G --> H["<b>20 · Transforms</b><br/>affine vs homography<br/><i>~15 min</i>"]
    H --> I["<b>21 · Matching</b><br/>SIFT to LoFTR<br/><i>~15 min</i>"]
    I --> J["<b>22 · Robust fitting</b><br/>RANSAC and ECC<br/><i>~15 min</i>"]
    J --> K["<b>23 · Metrics</b><br/>why RMSE lies<br/><i>~20 min</i>"]
    K --> L["<b>40 · The pipeline</b><br/>code walkthrough<br/><i>~15 min</i>"]
    L --> M["<b>50 · Findings</b><br/>what we measured<br/><i>~15 min</i>"]

    K --> N60["<b>60 · The maths</b><br/>every formula, derived<br/><i>~40 min · reference</i>"]
    M --> N61["<b>61 · ML &amp; AI</b><br/>what is used, what could be<br/><i>~15 min</i>"]
    M --> N70["<b>70 · Distributed GPU</b><br/>system design<br/><i>~20 min</i>"]

    M --> Z["<b>90 · Glossary</b><br/>keep open throughout"]

    style A fill:#1A1F71,color:#ffffff
    style M fill:#F7B600,color:#1A1F71
    style N60 fill:#eceef7,color:#1A1F71
    style N61 fill:#eceef7,color:#1A1F71
    style N70 fill:#eceef7,color:#1A1F71
    style Z fill:#F7F5F0,color:#1A1F71
```

## The reading tracks

**If you only have an hour.** 01 → 13 → 20 → 23 → 50. The problem, the hardware,
the maths that turned out to matter most, why our metrics are unusual, and what
we actually learned.

**If you are presenting to a panel.** 01 → 23 → 50, then skim 61. Everything a
judge is likely to probe: what was asked, why the obvious metric is
insufficient, what we measured that others did not, and a straight answer to
"where is the AI in this".

**If you are about to write code.** 40 → 60 → the module you are touching.

**If someone asks how this scales.** 70. It is explicitly a design, not a
description — nothing in it has been built, and it says so on line one.

## The full index

| # | doc | what it is |
|---|---|---|
| 00 | this file | the map |
| 01 | What & why | the ISRO problem statement, decoded |
| 10 | Geodesy | latitude and longitude are angles, not distances |
| 11 | Projections | flattening a sphere, and what it costs |
| 12 | Footprints | where an image actually is, as a polygon |
| 13 | Sensors | how a pushbroom camera takes a picture |
| 20 | Transforms | affine, homography, and the 639 m error |
| 21 | Matching | SIFT through LoFTR, classical and neural |
| 22 | Robust fitting | RANSAC, ECC, and fitting through bad data |
| 23 | Metrics | why RMSE lies, and the metrics we propose |
| 30 | PDS4 & PRADAN | how the data arrives, and how not to misread it |
| 31 | Instruments | OHRC, TMC-2, IIRS, and the LRO reference |
| 40 | The pipeline | a walk through the code |
| 50 | Findings | every number we measured, and every gap |
| 60 | The maths | every formula this project uses, derived from scratch |
| 61 | ML & AI | what learning is used, and what would genuinely help |
| 70 | Distributed GPU | system design for scaling out. **A design, not built.** |
| 90 | Glossary | every term, with the doc that introduces it |

## The four ideas that carry the whole project

If you retain nothing else:

| # | idea | doc |
|---|---|---|
| 1 | Latitude and longitude are **angles**, not distances. Longitude lines converge; near a pole everything Cartesian breaks. Our data is at −85°. | 10 |
| 2 | A **pushbroom** sensor has no single viewpoint, so no single perspective transform describes it. Assuming one costs **639 m**. | 13, 20 |
| 3 | **Illumination inverts features.** Move the sun and the lit crater wall becomes the dark one — descriptors key on exactly what changed. SIFT: 228 matches → 0. | 01, 21 |
| 4 | RMSE measured on the points you fitted to is **not accuracy**. It barely notices *where* those points are — we measured a **51×** gap. | 23 |

## Conventions in these notes

- **Measured** means a number this project produced from a run. It names the module.
- **Documented** means it comes from a paper or standard we read.
- **Unverified** means nobody has checked it. Said explicitly, never smoothed over.
- Where a run has not happened, the cell says so. There are no plausible-looking
  placeholder numbers anywhere in these docs.
