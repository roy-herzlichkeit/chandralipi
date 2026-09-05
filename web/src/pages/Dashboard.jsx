import { useEffect, useMemo, useState } from 'react'
import Reveal from '../components/Reveal'

const SORTS = [
  { key: 'id', label: 'Pair', numeric: false },
  { key: 'sourceSensor', label: 'Source', numeric: false },
  { key: 'referenceSensor', label: 'Reference', numeric: false },
  { key: 'matcher', label: 'Matcher', numeric: false },
  { key: 'sunAzimuthDelta', label: 'Δ sun az', numeric: true, unit: '°', digits: 0 },
  { key: 'nInliers', label: 'Inliers', numeric: true, digits: 0 },
  { key: 'inlierRatio', label: 'Ratio', numeric: true, digits: 2 },
  { key: 'rmseSelf', label: 'RMSE self', numeric: true, digits: 3 },
  { key: 'rmseTruth', label: 'RMSE truth', numeric: true, digits: 4 },
  { key: 'uniformity', label: 'Uniformity', numeric: true, digits: 3 },
  { key: 'extrapolationP95', label: 'Extrap. p95', numeric: true, digits: 2 },
]

const VIEWS = [
  { key: 'matches', label: 'Correspondences' },
  { key: 'checkerboard', label: 'Checkerboard' },
  { key: 'conditioning', label: 'Trust map' },
]

function fmt(value, digits = 3) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return Number(value).toFixed(digits)
}

function Figure({ label, value, unit, note, emphasis = false }) {
  return (
    <div className="stat">
      <span className="label">{label}</span>
      <div
        className="stat-figure"
        style={{ margin: '10px 0 8px', color: emphasis ? 'var(--ink)' : undefined }}
      >
        {value}{unit && <span className="stat-unit">{unit}</span>}
      </div>
      {note && <p className="marginal" style={{ marginBottom: 0 }}>{note}</p>}
    </div>
  )
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [view, setView] = useState('matches')
  const [sort, setSort] = useState({ key: 'id', dir: 1 })
  const [filters, setFilters] = useState({ sensor: 'all', matcher: 'all', trustedOnly: false })

  useEffect(() => {
    fetch('./data/results.json')
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json()
      })
      .then((payload) => {
        setData(payload)
        setSelectedId(payload.pairs[0]?.id ?? null)
      })
      .catch((cause) => setError(cause.message))
  }, [])

  const rows = useMemo(() => {
    if (!data) return []
    const filtered = data.pairs.filter((pair) => (
      (filters.sensor === 'all' || pair.sourceSensor === filters.sensor)
      && (filters.matcher === 'all' || pair.matcher === filters.matcher)
      && (!filters.trustedOnly
        || (pair.extrapolationP95 !== null && pair.extrapolationP95 <= data.extrapolationGatePx))
    ))
    const column = SORTS.find((entry) => entry.key === sort.key)
    return [...filtered].sort((a, b) => {
      const left = a[sort.key]
      const right = b[sort.key]
      if (left === null) return 1
      if (right === null) return -1
      const comparison = column?.numeric ? left - right : String(left).localeCompare(String(right))
      return comparison * sort.dir
    })
  }, [data, filters, sort])

  const selected = useMemo(
    () => data?.pairs.find((pair) => pair.id === selectedId) ?? null,
    [data, selectedId],
  )

  if (error) {
    return (
      <div className="section shell">
        <h1 style={{ marginBottom: 22 }}>Results</h1>
        <div className="note" style={{ maxWidth: '62ch' }}>
          <p><strong>No exported results found</strong> ({error}). Generate them from the repository root:</p>
          <pre className="num" style={{ fontSize: '0.8rem', margin: 0, whiteSpace: 'pre-wrap' }}>
{`python scripts/build_demo_results.py
python scripts/export_web_data.py`}
          </pre>
        </div>
      </div>
    )
  }

  if (!data) return <div className="loading">loading results</div>

  const sensors = ['all', ...new Set(data.pairs.map((pair) => pair.sourceSensor))]
  const matchers = ['all', ...new Set(data.pairs.map((pair) => pair.matcher))]
  const gate = data.extrapolationGatePx
  const trusted = selected && selected.extrapolationP95 !== null && selected.extrapolationP95 <= gate
  const ratio = selected && selected.rmseTruth && selected.rmseSelf
    ? selected.rmseSelf / selected.rmseTruth : null

  return (
    <>
      <header className="section" style={{ paddingBottom: 'clamp(24px, 3vw, 40px)' }}>
        <div className="shell spread">
          <div className="rail">
            <Reveal><span className="section-no">§ 00</span></Reveal>
          </div>
          <div>
            <div className="results-head">
              <div>
                <Reveal>
                  <h1 style={{ marginBottom: 20, maxWidth: '16ch' }}>
                    Every registered pair
                  </h1>
                </Reveal>
                <Reveal delay={0.05}>
                  <p className="lede" style={{ marginBottom: 0 }}>
                    {data.nPairs} pairs across sensor pairings, matchers and illumination cases,
                    read from a real pipeline run.
                  </p>
                </Reveal>
              </div>
              <Reveal delay={0.1}>
                <a href="http://localhost:8501" target="_blank" rel="noreferrer noopener" className="btn">
                  Live Streamlit tool ↗
                </a>
              </Reveal>
            </div>

            {data.allSynthetic && (
              <Reveal delay={0.12}>
                <div className="note" style={{ marginTop: 28, maxWidth: '74ch' }}>
                  <p style={{ marginBottom: 0 }}>
                    <strong>All {data.nPairs} results were computed on generated scenes, not
                    Chandrayaan-2 products.</strong> Archive access has not cleared, so the imagery
                    is a height field rendered under controlled sun angles. That is also why a
                    ground-truth column exists at all — on real data it is not measurable.
                  </p>
                </div>
              </Reveal>
            )}
          </div>
        </div>
      </header>

      <section className="section band" style={{ paddingTop: 'clamp(30px, 4vw, 48px)' }}>
        <div className="shell">
          <div className="filters">
            <select
              className="btn" value={filters.sensor} aria-label="Filter by source sensor"
              onChange={(event) => setFilters({ ...filters, sensor: event.target.value })}
            >
              {sensors.map((sensor) => (
                <option key={sensor} value={sensor}>{sensor === 'all' ? 'All sensors' : sensor}</option>
              ))}
            </select>
            <select
              className="btn" value={filters.matcher} aria-label="Filter by matcher"
              onChange={(event) => setFilters({ ...filters, matcher: event.target.value })}
            >
              {matchers.map((matcher) => (
                <option key={matcher} value={matcher}>{matcher === 'all' ? 'All matchers' : matcher}</option>
              ))}
            </select>
            <label className="btn">
              <input
                type="checkbox" checked={filters.trustedOnly}
                onChange={(event) => setFilters({ ...filters, trustedOnly: event.target.checked })}
                style={{ accentColor: 'var(--ink)', marginRight: 8 }}
              />
              Well-conditioned only
            </label>
            <span className="label" style={{ alignSelf: 'center' }}>{rows.length} of {data.nPairs}</span>
          </div>

          <div className="scroll-x" style={{ maxHeight: 380, overflowY: 'auto', background: 'var(--paper)' }}>
            <table className="tabular" style={{ minWidth: 940 }}>
              <thead>
                <tr>
                  {SORTS.map((column) => (
                    <th
                      key={column.key}
                      onClick={() => setSort((previous) => ({
                        key: column.key,
                        dir: previous.key === column.key ? -previous.dir : 1,
                      }))}
                    >
                      {column.label}{sort.key === column.key && (sort.dir === 1 ? ' ↑' : ' ↓')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((pair) => (
                  <tr
                    key={pair.id}
                    data-selected={pair.id === selectedId}
                    onClick={() => setSelectedId(pair.id)}
                  >
                    <td style={{ color: 'var(--ink)', fontWeight: 500 }}>{pair.id.replace(/_/g, ' ')}</td>
                    <td>{pair.sourceSensor}</td>
                    <td>{pair.referenceSensor}</td>
                    <td>{pair.matcher}</td>
                    <td className="num">{fmt(pair.sunAzimuthDelta, 0)}°</td>
                    <td className="num">{pair.nInliers}</td>
                    <td className="num">{fmt(pair.inlierRatio, 2)}</td>
                    <td className="num">{fmt(pair.rmseSelf, 3)}</td>
                    <td className="num" style={{ color: 'var(--ink)', fontWeight: 500 }}>
                      {fmt(pair.rmseTruth, 4)}
                    </td>
                    <td className="num">{fmt(pair.uniformity, 3)}</td>
                    <td>
                      <span className={`state ${
                        pair.extrapolationP95 !== null && pair.extrapolationP95 <= gate
                          ? 'state-ok' : 'state-no'}`}
                      >
                        {fmt(pair.extrapolationP95, 2)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {selected && (
        <section className="section">
          <div className="shell spread">
            <div className="rail">
              <span className="section-no">§ 01</span>
              <p className="marginal" style={{ marginTop: 14 }}>
                {selected.sourceSensor} → {selected.referenceSensor} · {selected.matcher}
                {selected.synthetic && ' · synthetic scene'}
              </p>
            </div>

            <div>
              <h2 style={{ marginBottom: 10, maxWidth: '22ch' }}>{selected.id.replace(/_/g, ' ')}</h2>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 30 }}>
                <span className="tag tag-solid">{selected.sourceSensor} → {selected.referenceSensor}</span>
                <span className="tag">{selected.matcher}</span>
                {selected.synthetic && <span className="tag tag-gold">synthetic</span>}
                <span className="tag">{trusted ? 'well conditioned' : 'under-constrained'}</span>
              </div>

              <div className="stat-row" style={{ marginBottom: 34 }}>
                <Figure
                  label="Inliers" value={selected.nInliers}
                  note={`of ${selected.nMatches} matches · ratio ${fmt(selected.inlierRatio, 2)}`}
                />
                <Figure
                  label="RMSE, self-residual" value={fmt(selected.rmseSelf, 3)} unit="px"
                  note="the conventional metric — the fit’s residual on its own points"
                />
                <Figure
                  label="RMSE, vs truth" value={fmt(selected.rmseTruth, 4)} unit="px" emphasis
                  note={ratio ? `the conventional figure is ${ratio.toFixed(0)}× larger` : 'known only because the scene is synthetic'}
                />
                <Figure
                  label="Extrapolation p95" value={fmt(selected.extrapolationP95, 2)} unit="px"
                  note={`gate ${gate} px · uniformity U ${fmt(selected.uniformity, 3)}`}
                />
              </div>

              <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
                {VIEWS.filter((option) => selected.images[option.key]).map((option) => (
                  <button
                    key={option.key}
                    className={`btn${view === option.key ? ' btn-fill' : ''}`}
                    onClick={() => setView(option.key)}
                  >
                    {option.label}
                  </button>
                ))}
              </div>

              <figure>
                <div className="figure">
                  <img
                    src={`./data/pairs/${selected.images[view] ?? selected.images.matches}`}
                    alt={`${view} view of ${selected.id}`}
                    loading="lazy"
                  />
                </div>
                <figcaption>
                  {view === 'matches' && 'Ink links are RANSAC inliers, hollow marks were rejected. Both frames show the same terrain under different sun positions — the lit crater walls swap sides.'}
                  {view === 'checkerboard' && 'Alternating tiles of warped source and reference. A crater rim crossing a tile boundary either continues or steps; a one-pixel error is visible here where a blend would smear it into softness.'}
                  {view === 'conditioning' && `Bootstrap resampling of the correspondences, refit each time. Cool means the matches pin the transform down there; hot means it is extrapolating. Colour is scaled against the ${gate} px gate, so two pairs can be compared by eye.`}
                </figcaption>
              </figure>
            </div>
          </div>
        </section>
      )}

      <div className="shell" style={{ paddingBottom: 60 }}>
        <p className="marginal" style={{ maxWidth: '80ch' }}>
          Snapshot exported {new Date(data.generatedUtc).toLocaleString()} from {data.sourceDirectory}.
          This page is static; the Streamlit tool reads the result store live.
        </p>
      </div>
    </>
  )
}
