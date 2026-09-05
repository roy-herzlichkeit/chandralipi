import { Arrow, Box, DiagramFrame, Lane } from '../components/Diagram'
import Reveal, { Section } from '../components/Reveal'

const MODULES = [
  {
    name: 'ingest/',
    blurb: 'Opens the PDS4 label, never the .IMG — GDAL maps .img to its ERDAS HFA driver and returns plausible wrong pixels with no error. Every mission-specific field carries a provenance value; 13 of 25 are still UNVERIFIED against a real product.',
    files: ['pds4.py', 'fieldmap.py', 'overlap.py', 'pseudo_gt.py', 'probe.py'],
  },
  {
    name: 'preprocess/',
    blurb: 'The Makharia et al. chain — georeferencing, resampling to a common GSD, normalisation, CLAHE, PCA, shadow correction — with every step independently toggleable for ablation. Parameters the paper does not state are marked PLACEHOLDER, not passed off as paper-matched.',
    files: ['pipeline.py', 'radiometric.py', 'shadow.py', 'resample.py', 'params.py'],
  },
  {
    name: 'match/',
    blurb: 'SIFT, ASIFT, AKAZE, a clean-room RIFT2, LoFTR and LightGlue behind one MatchResult interface. Tiled inference with overlap-aware stitching for images larger than VRAM allows.',
    files: ['classical.py', 'rift2/', 'loftr.py', 'superglue.py', 'tiled.py', 'stitch.py'],
  },
  {
    name: 'align/',
    blurb: 'MAGSAC++ robust fitting, refit on inliers, then ECC intensity refinement. Deliberately does not call cornerSubPix — measured, it made SIFT four times worse, because these detectors are already sub-pixel.',
    files: ['estimate.py', 'refine.py', 'warp.py'],
  },
  {
    name: 'eval/',
    blurb: 'RMSE, inlier count and ratio as the statement requires, plus spatial uniformity as a diagnostic and bootstrap conditioning as the gate. Also the synthetic scene generator that makes error attribution possible at all.',
    files: ['metrics.py', 'uniformity.py', 'conditioning.py', 'error_budget.py', 'scenes.py'],
  },
  {
    name: 'results/ + viz/',
    blurb: 'Per-pair persistence to parquet and npz so runs are browsable afterwards, and shared figure renderers used by the Streamlit tool, the demo script and this site alike.',
    files: ['results.py', 'viz/figures.py', 'pipeline.py'],
  },
]

const DECISIONS = [
  {
    q: 'Why not match IIRS directly to OHRC?',
    a: 'It is a 320× ground-sample ratio, which no feature matcher bridges. Makharia et al. matched IIRS to LRO WAC at 1.25× instead and never attempted a high-resolution camera — and at that ratio plain SIFT lands within 0.13 px of SuperGlue. The difficulty was removed by the choice of reference, not by the matcher.',
  },
  {
    q: 'Why is ECC the last stage rather than the matcher?',
    a: 'Because measurement said so. Four different matchers on the same pair converge to an identical final error despite starting from RANSAC fits that differ by an order of magnitude. The matcher only has to get close enough for intensity refinement to lock on.',
  },
  {
    q: 'Why a second accuracy metric?',
    a: 'RMSE over the matched points is the fit’s residual on its own data. Across 26 registered pairs it disagrees with the true error by 12.7× to 58.6×. Bootstrap conditioning correlates with true error at +0.78 against the coverage score’s −0.52, and it says where in the frame the answer can be trusted.',
  },
  {
    q: 'Why is OpenCV pinned below 5?',
    a: 'OpenCV 5 removed AKAZE, KAZE and BRISK from the main module, and opencv-contrib-python 5.0.0 does not restore them. AKAZE is one of the benchmark paper’s four classical baselines, so it is not optional.',
  },
]

export default function Architecture() {
  return (
    <>
      <header className="section" style={{ paddingBottom: 'clamp(30px, 4vw, 56px)' }}>
        <div className="shell spread">
          <div className="rail">
            <Reveal><span className="section-no">§ 00</span></Reveal>
          </div>
          <div>
            <Reveal>
              <h1 style={{ marginBottom: 22, maxWidth: '17ch' }}>
                High level, then low level.
              </h1>
            </Reveal>
            <Reveal delay={0.05}>
              <p className="lede">
                Two views of the same system. The first is what data does end to end. The
                second is what each stage does to it, and which decisions inside those stages
                were settled by measurement rather than assumption.
              </p>
            </Reveal>
          </div>
        </div>
      </header>

      <Section
        number="01"
        title="End to end"
        rail="Source and reference travel the same path until matching. Everything below the first lane is toggleable, which is what makes the ablation loop possible."
      >
        <Reveal>
          <DiagramFrame
            viewBox="0 0 1120 470"
            caption="The dashed return from evaluation to preprocessing is the ablation loop. Georeferencing also feeds matching directly, because scale bridging is metadata-driven rather than left to a detector’s scale invariance."
          >
            <Lane x={14} y={14} w={1092} h={106} label="Ingest" />
            <Box x={38} y={44} title="PDS4 label" sub="XML + .IMG" tone="accent" />
            <Box x={252} y={44} title="Manifest" sub="parquet · 25 fields" tone="accent" />
            <Box x={466} y={44} title="Footprint overlap" sub="lunar sphere clip" tone="accent" />
            <Box x={680} y={44} title="Crop to overlap" sub="windowed read" tone="accent" />
            <Box x={894} y={44} title="Pseudo ground truth" sub="georeference only" tone="muted" dashed />
            <Arrow from={[214, 75]} to={[252, 75]} />
            <Arrow from={[428, 75]} to={[466, 75]} />
            <Arrow from={[642, 75]} to={[680, 75]} />
            <Arrow from={[856, 75]} to={[894, 75]} dashed />

            <Lane x={14} y={140} w={1092} h={106} label="Preprocess" />
            <Box x={38} y={170} title="Georeference" sub="lunar datum" />
            <Box x={252} y={170} title="Resample" sub="common GSD" />
            <Box x={466} y={170} title="Normalise" sub="8-bit · CLAHE" />
            <Box x={680} y={170} title="Shadow correction" sub="gamma · retinex" />
            <Box x={894} y={170} title="Band reduction" sub="IIRS cube → 1 band" tone="warm" />
            <Arrow from={[126, 106]} to={[126, 170]} label="pixels" />
            <Arrow from={[214, 201]} to={[252, 201]} />
            <Arrow from={[428, 201]} to={[466, 201]} />
            <Arrow from={[642, 201]} to={[680, 201]} />

            <Lane x={14} y={266} w={1092} h={106} label="Match & align" />
            <Box x={38} y={296} title="Matcher" sub="SIFT · RIFT2 · LoFTR" tone="good" />
            <Box x={252} y={296} title="Tiled inference" sub="VRAM-bounded" tone="good" />
            <Box x={466} y={296} title="MAGSAC++" sub="robust fit" tone="good" />
            <Box x={680} y={296} title="ECC refinement" sub="sub-pixel" tone="good" />
            <Box x={894} y={296} title="Warp" sub="registered product" tone="good" />
            <Arrow from={[126, 232]} to={[126, 296]} label="prepared" />
            <Arrow from={[214, 327]} to={[252, 327]} />
            <Arrow from={[428, 327]} to={[466, 327]} />
            <Arrow from={[642, 327]} to={[680, 327]} />
            <Arrow from={[856, 327]} to={[894, 327]} />

            <Lane x={14} y={392} w={1092} h={64} label="Evaluate" />
            <Box x={252} y={404} w={196} h={40} title="RMSE · inliers · ratio" tone="muted" />
            <Box x={466} y={404} w={196} h={40} title="Uniformity U" tone="muted" />
            <Box x={680} y={404} w={196} h={40} title="Conditioning gate" tone="muted" />
            <Arrow from={[778, 358]} to={[778, 404]} />
            <Arrow from={[252, 424]} to={[126, 424]} dashed label="ablation" />
            <Arrow from={[126, 424]} to={[126, 232]} dashed />
          </DiagramFrame>
        </Reveal>
      </Section>

      <Section
        number="02"
        title="Inside match, align and eval"
        band
        rail="Every matcher returns the same result type, which is what lets a 2004 descriptor and a 2021 transformer be compared in one table."
      >
        <Reveal>
          <DiagramFrame
            viewBox="0 0 1120 420"
            caption="Failure is a classified outcome rather than an exception, so a batch run never aborts and never silently drops a pair. The two evaluation branches answer different questions: how good is the fit, and where can it be trusted."
          >
            <Box x={20} y={30} w={150} h={54} title="source array" sub="uint8 H×W" tone="accent" />
            <Box x={20} y={104} w={150} h={54} title="reference array" sub="uint8 H×W" tone="accent" />

            <Box x={228} y={62} w={168} h={66} title="Matcher" sub="build_classical()" tone="good" />
            <Arrow from={[170, 57]} to={[228, 88]} />
            <Arrow from={[170, 131]} to={[228, 100]} />

            <Box x={228} y={166} w={168} h={48} title="TiledMatcher" sub="plan_dense_tile()" tone="muted" dashed />
            <Arrow from={[312, 128]} to={[312, 166]} dashed label="if too large" />
            <Box x={228} y={238} w={168} h={48} title="stitch + dedup" sub="cKDTree · 1.5 px" tone="muted" dashed />
            <Arrow from={[312, 214]} to={[312, 238]} dashed />
            <Arrow from={[396, 262]} to={[470, 262]} dashed curve={-28} />

            <Box x={454} y={62} w={168} h={66} title="MatchResult" sub="src · dst · scores" tone="accent" />
            <Arrow from={[396, 95]} to={[454, 95]} label="N×2 float64" />

            <Box x={680} y={20} w={168} h={54} title="estimate_transform" sub="USAC_MAGSAC" />
            <Box x={680} y={92} w={168} h={54} title="reestimate_on_inliers" sub="tighter threshold" />
            <Box x={680} y={164} w={168} h={54} title="refine_transform_ecc" sub="prefilter from sun angles" tone="warm" />
            <Arrow from={[622, 82]} to={[680, 47]} />
            <Arrow from={[764, 74]} to={[764, 92]} />
            <Arrow from={[764, 146]} to={[764, 164]} />

            <Box x={906} y={92} w={186} h={54} title="Transform" sub="3×3 + inlier mask" tone="accent" />
            <Arrow from={[848, 191]} to={[906, 130]} />

            <Box x={906} y={196} w={186} h={48} title="compute_metrics" sub="RMSE · inliers · ratio" tone="muted" />
            <Box x={906} y={262} w={186} h={48} title="bootstrap_conditioning" sub="40 refits → p95 px" tone="muted" />
            <Box x={906} y={328} w={186} h={48} title="compute_uniformity" sub="√(coverage × entropy)" tone="muted" />
            <Arrow from={[999, 146]} to={[999, 196]} />
            <Arrow from={[999, 244]} to={[999, 262]} />
            <Arrow from={[999, 310]} to={[999, 328]} />

            <Box x={454} y={320} w={168} h={62} tone="warm" title="RunOutcome" sub="OK · TOO_FEW_MATCHES · …" />
            <Arrow from={[538, 128]} to={[538, 320]} dashed label="failure is a result" />
          </DiagramFrame>
        </Reveal>
      </Section>

      <Section number="03" title="What lives where" rail="Six packages. Nothing in the list below imports from the showcase site.">
        <div className="rows">
          {MODULES.map((module, index) => (
            <Reveal key={module.name} delay={index * 0.04}>
              <article className="module">
                <h3 className="num" style={{ fontSize: '0.92rem', color: 'var(--ink)' }}>
                  {module.name}
                </h3>
                <div>
                  <p className="prose" style={{ marginBottom: 12, fontSize: '0.92rem' }}>{module.blurb}</p>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {module.files.map((file) => <span key={file} className="tag">{file}</span>)}
                  </div>
                </div>
              </article>
            </Reveal>
          ))}
        </div>
      </Section>

      <Section
        number="04"
        title="Four choices, and the evidence for them"
        band
        rail="Each of these overturned a default. The evidence is in the repository, not in a preference."
      >
        <div className="rows">
          {DECISIONS.map((item, index) => (
            <Reveal key={item.q} delay={index * 0.04}>
              <article className="qa">
                <h3 style={{ marginBottom: 10, maxWidth: '30ch' }}>{item.q}</h3>
                <p className="prose" style={{ marginBottom: 0, fontSize: '0.93rem' }}>{item.a}</p>
              </article>
            </Reveal>
          ))}
        </div>
      </Section>
    </>
  )
}
