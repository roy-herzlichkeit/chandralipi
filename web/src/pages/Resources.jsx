import Reveal, { Section } from '../components/Reveal'

const HEADLINE_STATS = [
  { label: 'Tests passing', value: '378', note: 'across ingest, geodesy, preprocessing, matching, alignment and evaluation' },
  { label: 'Pairs registered', value: '26', unit: '/ 36', note: '10 classified failures, each with a named cause — none silently dropped' },
  { label: 'Self-residual vs truth', value: '12.7–58.6', unit: '×', note: 'how far the conventional RMSE sits from the real error' },
  { label: 'Best true RMSE', value: '0.0115', unit: 'px', note: 'same-illumination pair, ASIFT, 11,040 inliers' },
]

const MEASUREMENTS = [
  {
    title: 'Where dense matching runs out of memory',
    finding: 'LoFTR fp32 breaks between 1024 and 1152 px; LightGlue between 1536 and 2048 px.',
    detail: 'The failing allocation at 1152 px is 1,719,926,784 bytes, and ((1152/8)²)² × 4 is 1,719,926,784 exactly — the coarse score matrix, confirmed rather than assumed. Cost is two terms, 3203 B/px × S² plus 4 × (S/8)⁴, so the local exponent climbs from side^1.83 to side^3.69. An earlier pure-S⁴ model underestimated 1024 px by about 4× and would have handed out tile sizes that OOM.',
    caveat: 'Host RSS, not VRAM. This machine’s NVIDIA kernel module is not loaded and PyTorch is a CPU-only build, so absolute headroom on an RTX 4060 remains unmeasured.',
  },
  {
    title: 'The illumination cliff is in azimuth',
    finding: 'SIFT recovers 228 correct matches at 15° of azimuth change, 4 at 30°, and 0 at 60°.',
    detail: 'Shadow fraction moves independently and does not predict the collapse. Adding illumination-invariant albedo texture did not rescue it either: at grazing sun the shadowed fraction is multiplicative and destroys that texture too.',
  },
  {
    title: 'Refinement sets the accuracy floor, not the matcher',
    finding: 'Four matchers on one pair converge to an identical final error — 0.011 px at 0°, 0.092 px at 15°, 0.304 px at 30°.',
    detail: 'They start from RANSAC fits differing by an order of magnitude and still land on the same answer, so the matcher only has to get close enough for intensity refinement to lock on. Acting on that, normalising local contrast before the ECC stage cuts the error 4.8× at 30°, winning in 100% of runs over 6 seeds and 2 matchers.',
    caveat: 'Selecting that prefilter automatically from image statistics failed: normalised cross-correlation falls both for illumination change and for sensor noise, and the correct response is opposite in each case. The auto-mode ships disabled and documented as defective.',
  },
  {
    title: 'The uniformity metric was measuring the wrong thing',
    finding: 'Coverage-based uniformity correlates with true error at −0.52; bootstrap conditioning at +0.78.',
    detail: 'Stress testing found failures in both directions. Border-only and hollow-ring layouts score 0.590 and 0.621 and fail the gate while being among the best-conditioned tested (0.109 and 0.213 px). A sparse lattice scores a perfect 1.000 with no diagnostic flag while being 3–5× less precise than a dense grid. A grid histogram counts occupancy when the question is conditioning, so it was demoted to a diagnostic and the bootstrap became the gate.',
  },
  {
    title: 'Pseudo ground truth, with the confidence refused',
    finding: 'Quantisation alone puts IIRS-derived correspondences at 23.09 m — 92 OHRC pixels.',
    detail: 'Correspondences can be generated from georeferencing alone for any overlapping pair, uniformly distributed by construction. But absolute pointing accuracy, the corner-homography model error and the corner ordering are all unestablished, so the error budget returns no total at all — only a labelled floor. Loop closure through lat/lon is tautologically zero and there is a test asserting it stays zero with both footprints displaced 5 km, so it can never be read as validation.',
  },
]

const PAPERS = [
  {
    tag: 'Benchmark',
    title: 'Comparative Evaluation of Traditional and Deep Learning Feature Matching Algorithms using Chandrayaan-2 Lunar Data',
    authors: 'Makharia et al., 2025',
    href: 'https://arxiv.org/abs/2509.04775',
    use: 'The closest published work on this exact dataset. Read in full. Their RMSE is the fit’s residual on its own points, so our numbers are deliberately not placed beside theirs. Their IIRS→WAC pairing at 1.25× changed our cross-modal architecture.',
  },
  {
    tag: 'Cross-spectral',
    title: 'XoFTR: Cross-modal Feature Matching Transformer',
    authors: 'Tuzcuoğlu et al., 2024',
    href: 'https://arxiv.org/abs/2404.09692',
    use: 'Architecture template for the IIRS thermal arm — ResNet 1/8–1/4–1/2, LoFTR attention, sub-pixel head. Reaches AUC@5° of 22.03 against LoFTR’s 2.63 on visible↔thermal. Its fine-tune used 8×A100 for 24 h, which is why we plan adapter tuning instead. Dataset is CC BY-NC-SA.',
  },
  {
    tag: 'Training data',
    title: 'MINIMA: Modality Invariant Image Matching',
    authors: 'Ren et al., CVPR 2025',
    href: 'https://arxiv.org/abs/2412.19412',
    use: 'The synthetic-pair idea we adapt: generate the hard modality from data whose correspondences are known. Ours substitutes a physical forward model — PSF, resampling, spectral transform — for their generative one, because for IIRS the degradation can be written down rather than learned.',
  },
  {
    tag: 'Remote sensing',
    title: 'MapGlue: Multimodal Remote Sensing Image Matching',
    authors: 'Wu et al., 2025',
    href: 'https://arxiv.org/abs/2503.16185',
    use: 'Zero-shot baseline. 121,781 aligned pairs, generalises to unseen modalities without retraining — but its trained gap is map↔visible, which is semantic where ours is radiometric.',
  },
  {
    tag: 'Lunar',
    title: 'Robust Feature Matching of Multi-Illumination Lunar Orbiter Images Based on Crater Neighborhood Structure',
    authors: 'Remote Sensing 17(13), 2302, 2025',
    href: 'https://doi.org/10.3390/rs17132302',
    use: 'Crater rims are landmarks with a physical diameter, so they survive both illumination inversion and a scale change. Evaluated on 321 multi-illumination pairs. Note it is not training-free — the crater detector is a trained network; only the matching stage is.',
  },
  {
    tag: 'Foundation',
    title: 'RIFT: Multi-modal Image Matching Based on Radiation-variation Insensitive Feature Transform',
    authors: 'Li, Hu, Ai · IEEE TIP 2020',
    href: 'https://doi.org/10.1109/TIP.2019.2959244',
    use: 'Phase congruency plus a log-Gabor maximum index map. Reimplemented clean-room from the papers — no reference implementation carries a usable licence.',
  },
]

const DATA = [
  { name: 'Chandrayaan-2 PRADAN', detail: 'OHRC, TMC-2, IIRS PDS4 archive', status: 'access not cleared', href: 'https://pradan.issdc.gov.in/ch2/' },
  { name: 'LRO NAC / WAC', detail: 'Public PDS archive, ~105,828 products', status: 'open, no login', href: 'https://pds.lroc.im-ldi.com/' },
  { name: 'SELENE / Kaguya TC', detail: 'Secondary reference set', status: 'open via AWS mirror', href: 'https://registry.opendata.aws/jaxa-usgs-nasa-kaguya-tc/' },
  { name: 'NASA CGI Moon Kit', detail: 'LROC colour mosaic + LOLA elevation — the textures on this site', status: 'public domain', href: 'https://svs.gsfc.nasa.gov/4720/' },
]

function Stat({ label, value, unit, note }) {
  return (
    <div className="stat">
      <span className="label">{label}</span>
      <div className="stat-figure" style={{ margin: '10px 0 8px' }}>
        {value}{unit && <span className="stat-unit">{unit}</span>}
      </div>
      <p className="marginal" style={{ marginBottom: 0 }}>{note}</p>
    </div>
  )
}

export default function Resources() {
  return (
    <>
      <header className="section" style={{ paddingBottom: 'clamp(30px, 4vw, 56px)' }}>
        <div className="shell spread">
          <div className="rail">
            <Reveal><span className="section-no">§ 00</span></Reveal>
          </div>
          <div>
            <Reveal>
              <h1 style={{ marginBottom: 22, maxWidth: '19ch' }}>
                What we measured, and what we read.
              </h1>
            </Reveal>
            <Reveal delay={0.05}>
              <p className="lede" style={{ marginBottom: 40 }}>
                Every number here came from a run in the repository. Where something could
                not be measured on this hardware, it says so rather than carrying an estimate.
              </p>
            </Reveal>
            <Reveal delay={0.1}>
              <div className="stat-row">
                {HEADLINE_STATS.map((stat) => <Stat key={stat.label} {...stat} />)}
              </div>
            </Reveal>
          </div>
        </div>
      </header>

      <Section
        number="01"
        title="Five things measurement changed"
        rail="Each of these started as an assumption and was overturned by a run. The caveats are attached rather than omitted."
      >
        <div className="rows">
          {MEASUREMENTS.map((item, index) => (
            <Reveal key={item.title} delay={index * 0.04}>
              <article className="finding">
                <div>
                  <h3 style={{ marginBottom: 10 }}>{item.title}</h3>
                  <p className="finding-headline">{item.finding}</p>
                </div>
                <div>
                  <p className="prose" style={{ fontSize: '0.92rem', marginBottom: item.caveat ? 14 : 0 }}>
                    {item.detail}
                  </p>
                  {item.caveat && (
                    <div className="note">
                      <p><strong>Caveat.</strong> {item.caveat}</p>
                    </div>
                  )}
                </div>
              </article>
            </Reveal>
          ))}
        </div>
      </Section>

      <Section
        number="02"
        title="Papers, and what each is actually used for"
        band
        rail="Every one read from source rather than recalled. Where a paper demonstrates something and where we extrapolate from it are marked separately in the repository docs."
      >
        <div className="rows">
          {PAPERS.map((paper, index) => (
            <Reveal key={paper.href} delay={index * 0.03}>
              <a className="paper" href={paper.href} target="_blank" rel="noreferrer noopener">
                <div>
                  <span className="tag tag-gold">{paper.tag}</span>
                  <h3 style={{ margin: '12px 0 6px', fontSize: '1rem', maxWidth: '34ch' }}>
                    {paper.title}
                  </h3>
                  <span className="label" style={{ letterSpacing: '0.08em' }}>{paper.authors}</span>
                </div>
                <p className="prose" style={{ fontSize: '0.9rem', marginBottom: 0 }}>{paper.use}</p>
              </a>
            </Reveal>
          ))}
        </div>
      </Section>

      <Section number="03" title="Archives" rail="Access status as of the last check. The one that matters most is the one still closed.">
        <Reveal>
          <div className="scroll-x">
            <table className="tabular" style={{ minWidth: 620 }}>
              <thead>
                <tr><th style={{ width: '26%' }}>Source</th><th style={{ width: '48%' }}>What it is</th><th>Status</th></tr>
              </thead>
              <tbody>
                {DATA.map((source) => (
                  <tr key={source.name} onClick={() => window.open(source.href, '_blank', 'noopener')}>
                    <td style={{ color: 'var(--ink)', fontWeight: 600 }}>{source.name}</td>
                    <td>{source.detail}</td>
                    <td>
                      <span className={`state ${source.status.includes('not') ? 'state-no' : 'state-ok'}`}>
                        {source.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Reveal>
      </Section>
    </>
  )
}
