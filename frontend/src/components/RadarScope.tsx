import type { PipelineInfo, PipelineResult } from '../lib/api'
import { CATEGORIES } from '../lib/categories'
import { ms as fmtMs } from '../lib/format'

const R_MIN = 20
const R_MAX = 132
const LOG_LO = Math.log10(30)
const LOG_HI = Math.log10(60_000)
const RINGS = [
  { ms: 100, label: '0.1 s' },
  { ms: 1000, label: '1 s' },
  { ms: 10_000, label: '10 s' },
  { ms: 60_000, label: '60 s' },
]

function radius(ms: number) {
  const t = (Math.log10(Math.min(Math.max(ms, 30), 60_000)) - LOG_LO) / (LOG_HI - LOG_LO)
  return R_MIN + t * (R_MAX - R_MIN)
}

function polar(angleDeg: number, r: number): [number, number] {
  const a = ((angleDeg - 90) * Math.PI) / 180
  return [Math.cos(a) * r, Math.sin(a) * r]
}

/**
 * The sweep as a radar picture: each category owns a sector, each answer is a blip
 * whose distance from the centre is how long its source took to reply.
 */
export function RadarScope({
  plan,
  results,
  running,
  hovered,
  onHover,
  centreLabel,
}: {
  plan: PipelineInfo[]
  results: Record<string, PipelineResult>
  running: boolean
  hovered: string | null
  onHover: (name: string | null) => void
  centreLabel?: string
}) {
  const sectorSize = 360 / CATEGORIES.length
  const blips = CATEGORIES.flatMap((cat, ci) => {
    const members = plan.filter((p) => p.category === cat.id)
    return members.map((p, i) => {
      const angle = ci * sectorSize + ((i + 1) / (members.length + 1)) * sectorSize
      return { p, cat, angle, result: results[p.name] }
    })
  })
  const hoveredBlip = blips.find((b) => b.p.name === hovered && b.result)

  return (
    <figure className="relative mx-auto w-full max-w-[280px]">
      <svg viewBox="-160 -160 320 320" className="w-full" role="img" aria-label="Radar view of the sweep: distance from the centre is response time">
        <defs>
          <radialGradient id="scope-bg">
            <stop offset="0" stopColor="#1a0606" />
            <stop offset="1" stopColor="#050505" />
          </radialGradient>
        </defs>
        <circle r={R_MAX + 8} fill="url(#scope-bg)" stroke="rgb(248 113 113 / 0.25)" />
        {RINGS.map((ring) => (
          <g key={ring.ms}>
            <circle r={radius(ring.ms)} fill="none" stroke="#1f1f1f" strokeDasharray={ring.ms === 60_000 ? undefined : '2 3'} />
            <text
              x={3}
              y={-radius(ring.ms) - 3}
              fontSize="8.5"
              fill="var(--color-console-3)"
            >
              {ring.label}
            </text>
          </g>
        ))}
        {CATEGORIES.map((cat, ci) => {
          const [x1, y1] = polar(ci * sectorSize, R_MIN - 6)
          const [x2, y2] = polar(ci * sectorSize, R_MAX + 8)
          const [lx, ly] = polar(ci * sectorSize + sectorSize / 2, R_MAX + 19)
          const active = plan.some((p) => p.category === cat.id)
          return (
            <g key={cat.id}>
              <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#1f1f1f" />
              <text
                x={lx}
                y={ly}
                fontSize="10"
                fontWeight="600"
                textAnchor="middle"
                dominantBaseline="central"
                fill={active ? cat.holder : 'var(--color-console-3)'}
                opacity={active ? 1 : 0.55}
              >
                {cat.code}
              </text>
            </g>
          )
        })}

        {running && (
          <g className="scope-sweep" style={{ transformOrigin: 'center', transformBox: 'fill-box' }}>
            <circle r={R_MAX + 8} fill="none" stroke="none" />
            <defs>
              <linearGradient id="sweep-fade" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0" stopColor="#ef4444" stopOpacity="0" />
                <stop offset="1" stopColor="#ef4444" stopOpacity="0.35" />
              </linearGradient>
            </defs>
            <path d={`M0 0 L${polar(-38, R_MAX + 8).join(' ')} A${R_MAX + 8} ${R_MAX + 8} 0 0 1 0 ${-(R_MAX + 8)} Z`} fill="url(#sweep-fade)" />
            <line x1="0" y1="0" x2="0" y2={-(R_MAX + 8)} stroke="#f87171" strokeOpacity="0.85" strokeWidth="1.25" />
          </g>
        )}

        {blips.map(({ p, cat, angle, result }) => {
          if (!result) {
            const preview = !running && Object.keys(results).length === 0
            if (p.status === 'skipped' || !(running || preview)) return null
            const [x, y] = polar(angle, R_MAX + 4)
            return <circle key={p.name} cx={x} cy={y} r="2" fill={cat.holder} opacity="0.45" />
          }
          const [x, y] = polar(angle, radius(result.took_ms || 30))
          const isHovered = hovered === p.name
          const size = isHovered ? 10 : 7
          return (
            <g
              key={p.name}
              transform={`translate(${x} ${y})`}
              onMouseEnter={() => onHover(p.name)}
              onMouseLeave={() => onHover(null)}
              style={{ cursor: 'default' }}
            >
              <circle r="11" fill="transparent" />
              {result.status === 'ok' ? (
                <rect
                  x={-size / 2}
                  y={-size / 2}
                  width={size}
                  height={size}
                  fill={result.cached ? 'none' : cat.holder}
                  stroke={cat.holder}
                  strokeWidth={result.cached ? 1.75 : 1}
                />
              ) : result.status === 'error' ? (
                <path d="M-4 -4 L4 4 M4 -4 L-4 4" stroke="var(--color-alert)" strokeWidth="2" strokeLinecap="round" />
              ) : (
                <circle r="3" fill="none" stroke="var(--color-console-3)" />
              )}
            </g>
          )
        })}

        {hoveredBlip?.result && (() => {
          const [x, y] = polar(hoveredBlip.angle, radius(hoveredBlip.result.took_ms || 30))
          const right = x < 40
          const tx = x + (right ? 14 : -14)
          return (
            <g pointerEvents="none">
              <line x1={x} y1={y} x2={tx} y2={y - 12} stroke="var(--color-console-2)" strokeWidth="0.75" />
              <text x={tx + (right ? 2 : -2)} y={y - 15} fontSize="10" fontWeight="600" textAnchor={right ? 'start' : 'end'} fill="var(--color-console)">
                {hoveredBlip.p.label}
              </text>
              <text x={tx + (right ? 2 : -2)} y={y - 3} fontSize="9" textAnchor={right ? 'start' : 'end'} fill="var(--color-console-2)">
                {hoveredBlip.result.status === 'ok'
                  ? hoveredBlip.result.cached
                    ? 'cached answer'
                    : fmtMs(hoveredBlip.result.took_ms)
                  : 'unable'}
              </text>
            </g>
          )
        })()}

        <path d="M-5 0 H5 M0 -5 V5" stroke="var(--color-console-3)" />
        {centreLabel && (
          <text y="17" fontSize="9" textAnchor="middle" fill="var(--color-console-2)">
            {centreLabel}
          </text>
        )}
      </svg>
      <figcaption className="mt-1 text-center text-xs text-console-2">
        Each answer is plotted in its category's sector. The further out it sits, the longer the source took.
      </figcaption>
    </figure>
  )
}
