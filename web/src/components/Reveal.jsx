import { motion, useReducedMotion } from 'motion/react'

/**
 * Scroll reveal.
 *
 * Two constraints from DESIGN.md, both learned the hard way. Content is visible
 * by default and the animation is an enhancement — an earlier build animated
 * *from* opacity 0 and the entire hero stayed invisible when the animation did
 * not run. And `once` is set, because re-animating on every scroll-past is
 * restless rather than lively.
 */
export default function Reveal({ children, delay = 0, y = 14, as = 'div', ...rest }) {
  const reduced = useReducedMotion()
  const Tag = motion[as] ?? motion.div

  if (reduced) {
    const Plain = as
    return <Plain {...rest}>{children}</Plain>
  }

  return (
    <Tag
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '0px 0px -12% 0px' }}
      transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1], delay }}
      {...rest}
    >
      {children}
    </Tag>
  )
}

/** A numbered section with the editorial rail. */
export function Section({ number, title, lede, rail, children, id, band = false }) {
  return (
    <section id={id} className={`section${band ? ' band' : ''}`}>
      <div className="shell spread">
        <div className="rail">
          <Reveal>
            <span className="section-no">§ {number}</span>
            {rail && <p className="marginal" style={{ marginTop: 14 }}>{rail}</p>}
          </Reveal>
        </div>
        <div>
          {title && (
            <Reveal>
              <h2 style={{ marginBottom: lede ? 20 : 32, maxWidth: '22ch' }}>{title}</h2>
            </Reveal>
          )}
          {lede && (
            <Reveal delay={0.05}>
              <p className="lede" style={{ marginBottom: 36 }}>{lede}</p>
            </Reveal>
          )}
          {children}
        </div>
      </div>
    </section>
  )
}
