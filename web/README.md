# Chandralipi — showcase site

Front end for SIH26166. Separate from the Python package: nothing under
`src/lunar_reg/` imports from here, and the pipeline, its tests and the
Streamlit tool all run without Node installed.

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # static bundle in dist/
```

Read **`DESIGN.md`** before changing anything visual. It records why each rule
exists, including the things it deliberately rules out.

## Pages

| Route | What it is |
|---|---|
| `/` | The Moon, the problem, the team |
| `/architecture` | HLD system flow and LLD of the matching path, as inline SVG |
| `/resources` | Measured findings, the papers behind each choice, the archives |
| `/dashboard` | Every registered pair, its metrics, its figures |

## The results page is a snapshot, and says so

The Streamlit app in `../dashboard/app.py` is the live tool — it reads the
`.npz` result store directly and is what gets demonstrated. This page reads a
static export so the site deploys anywhere without a Python process, and it
links out to Streamlit for anyone running it locally.

```bash
python scripts/build_demo_results.py    # run the pipeline
python scripts/export_web_data.py       # → web/public/data/
```

The export stamps a UTC timestamp and source directory into the JSON and the
page prints both, because a snapshot that can go stale should say how old it is.

## Theme

Light by default, dark by choice, and *unset* by default-default — an untouched
control follows the operating system. Only an explicit choice writes to
`localStorage`. The initial value is applied by an inline script in
`index.html` before first paint; reading it from React flashes the light theme
at anyone who asked for dark.

Dark is derived, not a second design: the same navy hue inverted in lightness,
so `#0B0E24` is the ink taken down rather than a neutral black.

## The background

Faint iso-elevation contours traced from NASA's LOLA lunar elevation model — the
same raster the 3D Moon uses as its bump map — so the lines behind the page are
the Moon's real hypsometry rather than a decorative topographic pattern.
Regenerate with:

```bash
python scripts/make_contour_background.py --levels 14 --min-points 70 --epsilon 2.2
```

Applied as a CSS **mask** over a solid `--ink` fill, not a background image: a
background image is an isolated document and cannot inherit `currentColor`, so
it could not follow the theme. Masking an ink fill can, and one 109 kB file
serves both.

## Stack, and why

**React Three Fiber** for the Moon and **Motion** (`motion/react`) for
everything else. One animation library, not two: an earlier build used GSAP
ScrollTrigger, and mixing runtimes invites two libraries writing the same
property. Motion covers scroll, gesture and spring in the API React already
speaks, and `anime.js` was considered and left out for the same reason — it
would duplicate jobs Motion already does.

**No Tailwind, no component library.** The visual language here is specific
enough (see `DESIGN.md`) that a utility framework or a prebuilt kit would be
fought rather than used.

**Fonts are all Google-hosted and freely licensable.** Two things asked for could
not be shipped and are substituted, with the reasoning in `DESIGN.md`: the Dune
title lettering is bespoke and its community recreation has no verifiable
licence, so the register is rebuilt from Archivo's variable width axis; and
Anthropic's Copernicus and Styrene B are licensed to Anthropic, so the site uses
the substitutes their own published design document names.

## Notes for whoever picks this up

**Routing is hash-based.** `HashRouter`, not `BrowserRouter`, because a static
build on GitHub Pages or opened from a file path cannot serve a rewrite rule.

**Content is visible by default; animation is an enhancement.** `Reveal` never
leaves an element at `opacity: 0` when the animation does not run — an earlier
build hid the entire hero that way, and it took a screenshot to notice.

**The hero needs both siblings on their own compositing layer.** A WebGL canvas
is promoted to its own layer, and in some compositors that layer paints above
sibling content with a higher `z-index` but no layer of its own. If the hero
text disappears, that is the first thing to check.

**`max-width` in `ch` belongs on the element it constrains.** `ch` resolves
against the element's own font size, so `30ch` on a 16px wrapper squeezed a
4.6rem headline into a 274px column.

**Diagrams are hand-built SVG.** Every box carries a real module name and every
edge a real payload. Fills are tints of the one blue rather than separate hues,
so a diagram stays legible in greyscale and survives being printed into a report
— which is where architecture diagrams usually end up.

**Verify visually, not by build success.** Both compositing bugs above compiled
cleanly and threw no console errors. `npx playwright` against the dev server at
1440px and 390px, checking `document.documentElement.scrollWidth` for horizontal
overflow, is what actually catches them.

## Credits

Lunar colour and elevation maps: NASA Scientific Visualization Studio,
[CGI Moon Kit](https://svs.gsfc.nasa.gov/4720/) — LROC colour mosaic and LOLA
elevation model. Public domain; credit requested and given in the site footer.
