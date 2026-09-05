/**
 * Inline SVG diagram primitives.
 *
 * Hand-built rather than pulled from a diagramming library. These are the
 * project's actual architecture, so every box carries a real module name and
 * every edge carries the real payload that travels along it. A generic
 * flowchart widget encourages generic boxes, which is what makes most
 * architecture diagrams say nothing.
 */

/* Ink on paper. Fills are tints of the one blue rather than separate hues, so
   the diagram stays legible in greyscale and survives being printed into a
   report — which is where an architecture diagram usually ends up. */
/* Driven from the theme tokens rather than fixed hex, so the diagram inverts
   with the rest of the page. Fills stay tints of the one ink hue rather than
   separate colours, which keeps the figure legible in greyscale and survives
   being printed into a report — where architecture diagrams usually end up. */
const TONES = {
  default: { fill: 'var(--paper)',      stroke: 'var(--ink)',    text: 'var(--ink)' },
  accent:  { fill: 'var(--paper-deep)', stroke: 'var(--ink)',    text: 'var(--ink)' },
  warm:    { fill: 'var(--gold-soft)',  stroke: 'var(--gold)',   text: 'var(--ink)' },
  good:    { fill: 'var(--ink)',        stroke: 'var(--ink)',    text: 'var(--paper)' },
  muted:   { fill: 'var(--paper-warm)', stroke: 'var(--ink-25)', text: 'var(--ink-70)' },
}

export function Box({ x, y, w = 176, h = 62, title, sub, tone = 'default', dashed = false }) {
  const { fill, stroke, text } = TONES[tone] ?? TONES.default
  return (
    <g>
      <rect
        x={x} y={y} width={w} height={h} rx="9"
        fill={fill} stroke={stroke} strokeWidth="1.1"
        strokeDasharray={dashed ? '5 4' : undefined}
      />
      <text
        x={x + w / 2} y={sub ? y + h / 2 - 5 : y + h / 2 + 4}
        textAnchor="middle" fill={text} fontSize="12.5" fontWeight="600"
        fontFamily="'IBM Plex Sans', system-ui, sans-serif"
      >
        {title}
      </text>
      {sub && (
        <text
          x={x + w / 2} y={y + h / 2 + 13} textAnchor="middle"
          fill={tone === 'good' ? 'var(--paper-deep)' : 'var(--ink-45)'} fontSize="10"
          fontFamily="'IBM Plex Mono', ui-monospace, monospace"
        >
          {sub}
        </text>
      )}
    </g>
  )
}

export function Arrow({ from, to, label, dashed = false, colour = 'var(--ink-45)', curve = 0 }) {
  const [x1, y1] = from
  const [x2, y2] = to
  const midX = (x1 + x2) / 2
  const midY = (y1 + y2) / 2
  const d = curve
    ? `M ${x1} ${y1} Q ${midX + curve} ${midY} ${x2} ${y2}`
    : `M ${x1} ${y1} L ${x2} ${y2}`

  return (
    <g>
      <path
        d={d} fill="none" stroke={colour} strokeWidth="1.3"
        strokeDasharray={dashed ? '4 4' : undefined}
        markerEnd="url(#arrowhead)"
      />
      {label && (
        <text
          x={midX + curve * 0.5} y={midY - 7} textAnchor="middle"
          fill="var(--ink-45)" fontSize="9.6"
          fontFamily="'IBM Plex Mono', ui-monospace, monospace"
        >
          {label}
        </text>
      )}
    </g>
  )
}

export function Lane({ x, y, w, h, label }) {
  return (
    <g>
      <rect
        x={x} y={y} width={w} height={h} rx="12"
        fill="var(--paper-warm)" stroke="var(--rule-soft)" strokeWidth="1"
        strokeDasharray="0"
      />
      {/* Right-aligned: the vertical connectors between lanes run down the
          left-hand column, and a left-aligned label collides with them. */}
      <text
        x={x + w - 14} y={y + 20} textAnchor="end" fill="var(--ink-45)" fontSize="9.6"
        letterSpacing="1.5" fontFamily="'IBM Plex Mono', ui-monospace, monospace"
      >
        {label.toUpperCase()}
      </text>
    </g>
  )
}

export function Defs() {
  return (
    <defs>
      <marker
        id="arrowhead" markerWidth="9" markerHeight="7"
        refX="8.4" refY="3.5" orient="auto"
      >
        <polygon points="0 0, 9 3.5, 0 7" fill="var(--ink-45)" />
      </marker>
    </defs>
  )
}

/** Scrollable, responsive wrapper. Wide diagrams must scroll inside their own
 *  box rather than making the whole page scroll sideways. */
export function DiagramFrame({ viewBox, children, caption, height = 'auto' }) {
  return (
    <figure style={{ margin: 0 }}>
      <div
        className="scroll-x"
        style={{
          border: '1px solid var(--rule)', borderRadius: 4,
          background: 'var(--paper)', padding: 'clamp(12px, 2vw, 20px)',
        }}
      >
        <svg viewBox={viewBox} style={{ width: '100%', minWidth: 660, height, display: 'block' }}>
          <Defs />
          {children}
        </svg>
      </div>
      {caption && <figcaption>{caption}</figcaption>}
    </figure>
  )
}
