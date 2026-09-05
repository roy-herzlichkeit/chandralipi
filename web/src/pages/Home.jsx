import { Suspense } from 'react'
import { Link } from 'react-router-dom'
import Reveal, { Section } from '../components/Reveal'
import Moon from '../components/Moon'

const INSTRUMENTS = [
  { name: 'OHRC', full: 'Orbiter High Resolution Camera', gsd: '0.25', band: 'panchromatic' },
  { name: 'TMC-2', full: 'Terrain Mapping Camera 2', gsd: '5', band: 'panchromatic' },
  { name: 'IIRS', full: 'Imaging Infrared Spectrometer', gsd: '80', band: '~256 bands, 0.8–5 µm' },
  { name: 'LRO NAC', full: 'Narrow Angle Camera — reference', gsd: '0.5', band: 'panchromatic' },
]

const CHALLENGES = [
  {
    n: 'i',
    title: 'Illumination',
    body: 'Move the sun and a crater rim inverts — the wall that was lit goes dark. Descriptors built on intensity gradients key on precisely the thing that changed.',
    figure: '0',
    caption: 'correspondences SIFT returns at 60° of sun azimuth change',
  },
  {
    n: 'ii',
    title: 'Scale',
    body: 'OHRC resolves a quarter of a metre per pixel. IIRS resolves eighty. No feature matcher bridges that directly, so the chain has to be built rather than assumed.',
    figure: '320×',
    caption: 'ground sample ratio between IIRS and OHRC',
  },
  {
    n: 'iii',
    title: 'Viewpoint',
    body: 'Different orbits, different look angles, a curved body, a pushbroom sensor. The mapping between two frames is projective at best, and drifts along a strip.',
    figure: '90,000',
    caption: 'lines in a single OHRC strip',
  },
]

export default function Home() {
  return (
    <>
      {/* ---------------------------------------------------------------- */}
      <header style={{ position: 'relative', overflow: 'hidden' }}>
        <div className="shell" style={{ paddingTop: 'clamp(44px, 7vw, 96px)', paddingBottom: 'clamp(40px, 6vw, 80px)' }}>
          <div className="hero-grid">
            <div>
              <Reveal>
                <p className="label" style={{ marginBottom: 22 }}>
                  Smart India Hackathon 2026 · ISRO · Problem SIH26166
                </p>
              </Reveal>

              <Reveal delay={0.05}>
                <h1 style={{ marginBottom: 26, maxWidth: '15ch' }}>
                  Finding the same place twice on the&nbsp;Moon.
                </h1>
              </Reveal>

              <Reveal delay={0.1}>
                <p className="lede" style={{ marginBottom: 30 }}>
                  <em>Chandralipi</em> — moon script. Multi-modal, sun-angle and scale invariant image
                  correspondence across Chandrayaan-2’s optical payloads, registered against
                  LRO reference imagery to sub-pixel accuracy.
                </p>
              </Reveal>

              <Reveal delay={0.15}>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  <Link to="/dashboard" className="btn btn-fill">See the results</Link>
                  <Link to="/architecture" className="btn">How it works</Link>
                </div>
              </Reveal>
            </div>

            <div className="hero-moon" aria-hidden="true">
              <Suspense fallback={null}>
                <Moon />
              </Suspense>
            </div>
          </div>
        </div>

        {/* Instrument table, set as data rather than as feature cards. */}
        <div className="shell">
          <Reveal delay={0.2}>
            <div className="scroll-x" style={{ borderTop: '1px solid var(--ink-25)' }}>
              <table className="tabular" style={{ minWidth: 560 }}>
                <thead>
                  <tr>
                    <th style={{ width: '18%' }}>Instrument</th>
                    <th style={{ width: '46%' }}>Payload</th>
                    <th style={{ width: '14%' }}>GSD</th>
                    <th>Spectral</th>
                  </tr>
                </thead>
                <tbody>
                  {INSTRUMENTS.map((row) => (
                    <tr key={row.name} style={{ cursor: 'default' }}>
                      <td style={{ color: 'var(--ink)', fontWeight: 600 }}>{row.name}</td>
                      <td>{row.full}</td>
                      <td className="num">{row.gsd} m/px</td>
                      <td>{row.band}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Reveal>
        </div>
      </header>

      {/* ---------------------------------------------------------------- */}
      <Section
        number="01"
        title="Three things break registration on the Moon."
        rail="The problem statement names all three. They compound: the illumination case is hardest exactly where the scale case is worst, near the poles."
      >
        <div className="rows">
          {CHALLENGES.map((item, index) => (
            <Reveal key={item.title} delay={index * 0.06}>
              <article className="challenge">
                <div className="challenge-mark">
                  <span className="label" style={{ fontStyle: 'italic', textTransform: 'none', letterSpacing: 0 }}>
                    {item.n}
                  </span>
                </div>
                <div>
                  <h3 style={{ marginBottom: 8 }}>{item.title}</h3>
                  <p className="prose" style={{ marginBottom: 0 }}>{item.body}</p>
                </div>
                <div className="challenge-figure">
                  <div className="stat-figure">{item.figure}</div>
                  <p className="marginal" style={{ marginTop: 6, marginBottom: 0 }}>{item.caption}</p>
                </div>
              </article>
            </Reveal>
          ))}
        </div>
      </Section>

      {/* ---------------------------------------------------------------- */}
      <Section
        number="02"
        title="Who built it"
        band
        rail="Idea submission for the Smart India Hackathon 2026, under the Department of Space."
      >
        <div className="two-col">
          <div>
            <p className="prose">
              <strong>Severed Department</strong>, a team from the International Institute of
              Information Technology, Bhubaneswar, working problem statement SIH26166 for the
              Indian Space Research Organisation.
            </p>
            <p className="prose">
              The pipeline is Python: PDS4 ingest that opens the label rather than the image
              file, footprint overlap computed on the lunar sphere, an ablatable preprocessing
              chain, classical and learned matchers behind one interface, robust fitting with
              sub-pixel refinement, and an evaluation layer that reports <em>where</em> an
              answer can be trusted alongside how good it is.
            </p>
          </div>

          <div>
            <div className="rows">
              {[
                ['Institution', 'IIIT Bhubaneswar'],
                ['Problem', 'SIH26166'],
                ['Organisation', 'ISRO · Department of Space'],
                ['Theme', 'Space Technology'],
                ['Tests passing', '378'],
              ].map(([key, value]) => (
                <div className="row" key={key}>
                  <span className="label" style={{ letterSpacing: '0.1em' }}>{key}</span>
                  <span className="num" style={{ fontSize: '0.86rem' }}>{value}</span>
                </div>
              ))}
            </div>

            <div className="note" style={{ marginTop: 26 }}>
              <p>
                <strong>On the data.</strong> Chandrayaan-2 archive access has not cleared, so
                every figure on this site was produced on generated lunar scenes carrying a
                known ground-truth transform. The pipeline and the numbers are real; the
                surface is not. Each page says so where it matters.
              </p>
            </div>
          </div>
        </div>
      </Section>
    </>
  )
}
