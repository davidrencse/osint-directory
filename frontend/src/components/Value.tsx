import { useState } from 'react'
import { humanKey } from '../lib/format'

const INDICATOR_RE =
  /^([a-z0-9-]+\.)+[a-z]{2,}$|^\d{1,3}(\.\d{1,3}){3}(\/\d+)?$|^[0-9a-f:]+:[0-9a-f:]*$|^AS\d+|^[a-f0-9]{32,128}$/i

function Scalar({ v }: { v: unknown }) {
  if (v === null || v === undefined || v === '') return <span className="text-fg-3">none</span>
  if (typeof v === 'boolean') return <span className="font-semibold">{v ? 'Yes' : 'No'}</span>
  if (typeof v === 'number') return <span className="ind">{v.toLocaleString()}</span>
  const s = String(v)
  if (/^https?:\/\//.test(s))
    return (
      <a href={s} target="_blank" rel="noreferrer" className="ind break-all text-link underline">
        {s}
      </a>
    )
  return <span className={INDICATOR_RE.test(s) ? 'ind break-all' : 'break-words'}>{s}</span>
}

export function Value({ v }: { v: unknown }) {
  const [all, setAll] = useState(false)
  if (Array.isArray(v)) {
    if (v.length === 0) return <span className="text-fg-3">none</span>
    const shown = all ? v : v.slice(0, 8)
    return (
      <span className="flex flex-wrap gap-x-3 gap-y-0.5">
        {shown.map((x, i) => (
          <span key={i}>
            <Value v={x} />
          </span>
        ))}
        {v.length > 8 && (
          <button className="text-link underline" onClick={() => setAll(!all)}>
            {all ? 'Show fewer' : `${v.length - 8} more`}
          </button>
        )}
      </span>
    )
  }
  if (v && typeof v === 'object') {
    const entries = Object.entries(v as Record<string, unknown>)
    if (entries.length === 0) return <span className="text-fg-3">none</span>
    return (
      <span className="flex flex-col">
        {entries.map(([k, x]) => (
          <span key={k}>
            <span className="text-fg-2">{k}</span> <Value v={x} />
          </span>
        ))}
      </span>
    )
  }
  return <Scalar v={v} />
}

export function KeyValueGrid({ data }: { data: Record<string, unknown> }) {
  return (
    <dl className="grid grid-cols-[minmax(7rem,auto)_1fr] gap-x-6 gap-y-1.5 text-sm">
      {Object.entries(data).map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-fg-2">{humanKey(k)}</dt>
          <dd className="min-w-0">
            <Value v={v} />
          </dd>
        </div>
      ))}
    </dl>
  )
}

export function JsonBlock({ data }: { data: unknown }) {
  return (
    <pre className="font-mono max-h-96 overflow-auto rounded-md bg-ground p-3 text-xs leading-relaxed text-console-2">
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}
