import { useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { useTexture } from '@react-three/drei'
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

function useReducedMotionFlag() {
  const [reduced, setReduced] = useState(false)
  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => setReduced(query.matches)
    update()
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])
  return reduced
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

/**
 * An instrument swath drawn on the sphere.
 *
 * Illustrative, not a real product footprint. Deliberately thin: an OHRC strip
 * is 3 km against a 3474 km body, so a proportionate footprint would be
 * invisible and a wide rectangle would misrepresent the instrument.
 */
function Swath({ lat, from, to, colour, radius = 2.015, width = 0.011 }) {
  const geometry = useMemo(() => {
    const points = []
    for (let i = 0; i <= 40; i++) {
      const lon = THREE.MathUtils.lerp(from, to, i / 40)
      const phi = THREE.MathUtils.degToRad(90 - lat)
      const theta = THREE.MathUtils.degToRad(lon)
      points.push(new THREE.Vector3(
        radius * Math.sin(phi) * Math.cos(theta),
        radius * Math.cos(phi),
        radius * Math.sin(phi) * Math.sin(theta),
      ))
    }
    return new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points), 52, width, 6, false)
  }, [lat, from, to, radius, width])

  useEffect(() => () => geometry.dispose(), [geometry])

  return (
    <mesh geometry={geometry}>
      <meshBasicMaterial color={colour} />
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
        <Swath lat={5} from={-54} to={40} colour="#1A1F71" />
        <Swath lat={-15} from={-26} to={58} colour="#F7B600" />
      </group>
    </>
  )
}

export default function Moon({ className = '' }) {
  const coarse = useIsCoarse()
  const reduced = useReducedMotionFlag()

  // Fewer segments and no rotation on phones: it costs battery for no benefit
  // at that size, and a coarse pointer has no parallax to respond to anyway.
  const segments = coarse ? 64 : 128
  const spin = reduced || coarse ? 0 : 0.016

  return (
    <Canvas
      className={className}
      camera={{ position: [0, 0, 6.9], fov: 40 }}
      dpr={[1, coarse ? 1.5 : 2]}
      gl={{ antialias: true, alpha: true }}
      style={{ pointerEvents: 'none' }}
    >
      <Scene segments={segments} spin={spin} parallax={!coarse && !reduced} />
    </Canvas>
  )
}
