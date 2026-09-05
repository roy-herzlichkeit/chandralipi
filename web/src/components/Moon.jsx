import { useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { useTexture } from '@react-three/drei'
import { motion, useReducedMotion, useScroll, useTransform } from 'motion/react'
import * as THREE from 'three'

/**
 * The Moon, rendered as a plate rather than a hero.
 *
 * On paper rather than on a starfield: a lit sphere against white reads as a
 * figure in an atlas, which is the register this project wants. It also avoids
 * the dark-gradient hero that every generated site arrives at.
 *
 * Textures are NASA SVS's CGI Moon Kit — the LROC colour mosaic and the LOLA
 * elevation model. Elevation is applied as a bump map, not vertex displacement:
 * real lunar relief against the lunar radius is far too subtle to read as
 * geometry, and exaggerating it produces a potato.
 *
 * Nothing is drawn *on* the sphere. An earlier build traced two coloured tubes
 * across it as illustrative instrument swaths; they were the one element on the
 * page that stated something the project has not measured, and at hero scale
 * they read as decoration rather than as data. The plate is left clean.
 */

function useIsCoarse() {
  const [coarse, setCoarse] = useState(false)
  useEffect(() => {
    const query = window.matchMedia('(max-width: 768px), (pointer: coarse)')
    const update = () => setCoarse(query.matches)
    update()
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])
  return coarse
}

function Body({ segments, spin }) {
  const ref = useRef()
  const [colorMap, bumpMap] = useTexture([
    './textures/moon_color_2k.jpg',
    './textures/moon_displacement.jpg',
  ])

  useMemo(() => {
    colorMap.colorSpace = THREE.SRGBColorSpace
    bumpMap.colorSpace = THREE.NoColorSpace
    colorMap.anisotropy = 8
    bumpMap.anisotropy = 8
  }, [colorMap, bumpMap])

  useFrame((_, delta) => {
    if (ref.current && spin) ref.current.rotation.y += delta * spin
  })

  return (
    <mesh ref={ref} rotation={[0.1, 2.35, 0.04]}>
      <sphereGeometry args={[2, segments, segments]} />
      <meshStandardMaterial
        map={colorMap}
        bumpMap={bumpMap}
        bumpScale={2.2}
        roughness={0.95}
        metalness={0}
      />
    </mesh>
  )
}

function Scene({ segments, spin, parallax }) {
  const group = useRef()

  useFrame((state) => {
    if (!group.current || !parallax) return
    const { x, y } = state.pointer
    group.current.rotation.y += (x * 0.1 - group.current.rotation.y) * 0.03
    group.current.rotation.x += (-y * 0.06 - group.current.rotation.x) * 0.03
  })

  return (
    <>
      {/* One hard key light and almost no fill. The Moon has no atmosphere, so
          the terminator really is that abrupt; a three-point rig looks wrong. */}
      <directionalLight position={[4.4, 1.8, 3.6]} intensity={2.9} color="#fffaf0" />
      <ambientLight intensity={0.07} />
      <group ref={group}>
        <Body segments={segments} spin={spin} />
      </group>
    </>
  )
}

export default function Moon({ className = '' }) {
  const host = useRef(null)
  const coarse = useIsCoarse()
  const reduced = useReducedMotion()

  // Fewer segments and no rotation on phones: it costs battery for no benefit
  // at that size, and a coarse pointer has no parallax to respond to anyway.
  const segments = coarse ? 64 : 128
  const spin = reduced || coarse ? 0 : 0.016

  // Scroll drift. The moon leaves to the right as the hero is scrolled past,
  // so the reader is handed the page rather than made to scroll around a
  // fixed object. Driven off the element's own progress through the viewport
  // rather than a pixel threshold, so it behaves the same on a phone and on a
  // 4K display. `end start` — the drift completes as the moon's bottom edge
  // reaches the top of the viewport, which is also the point it stops being
  // visible, so the animation never runs against nothing.
  const { scrollYProgress } = useScroll({
    target: host,
    offset: ['start start', 'end start'],
  })

  // The transform is applied to the wrapping element, not inside the WebGL
  // scene. A composited CSS transform costs nothing per frame; moving the
  // camera or the group would re-render the sphere on every scroll event.
  const x = useTransform(scrollYProgress, [0, 1], ['0%', '42%'])
  const scale = useTransform(scrollYProgress, [0, 1], [1, 0.88])
  const opacity = useTransform(scrollYProgress, [0, 0.75, 1], [1, 0.5, 0])

  const drift = reduced ? undefined : { x, scale, opacity }

  return (
    <motion.div
      ref={host}
      style={{ width: '100%', height: '100%', transformOrigin: '50% 40%', ...drift }}
    >
      <Canvas
        className={className}
        camera={{ position: [0, 0, 6.9], fov: 40 }}
        dpr={[1, coarse ? 1.5 : 2]}
        gl={{ antialias: true, alpha: true }}
        style={{ pointerEvents: 'none' }}
      >
        <Scene segments={segments} spin={spin} parallax={!coarse && !reduced} />
      </Canvas>
    </motion.div>
  )
}
