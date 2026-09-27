import { useMutation, useQuery } from '@tanstack/react-query'
import { ChevronDown, FileUp } from 'lucide-react'
import { useEffect, useRef, useState, type DragEvent } from 'react'
import { Link } from 'react-router-dom'
import { Strip } from '../components/Strip'
import { Value } from '../components/Value'
import { api, type MetadataResult } from '../lib/api'
import { maplibregl } from '../lib/maplibre'
import { saveBlob } from '../lib/report'

// Each kind of revealing field gets its own holder, most sensitive first.
const REASONS: Record<string, { code: string; holder: string; order: number }> = {
  Location: { code: 'LOC', holder: 'var(--color-h-int)', order: 0 },
  Identity: { code: 'WHO', holder: 'var(--color-h-web)', order: 1 },
  'Local file path (may contain a username)': { code: 'PTH', holder: 'var(--color-h-dns)', order: 2 },
  'Device / document ID': { code: 'IDS', holder: 'var(--color-h-his)', order: 3 },
  'Device / software': { code: 'DEV', holder: 'var(--color-h-reg)', order: 4 },
  Timestamp: { code: 'TIM', holder: 'var(--color-h-net)', order: 5 },
}

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 ** 2).toFixed(1)} MB`
}

export default function MetadataPage() {
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const caps = useQuery({
    queryKey: ['meta-caps'],
    queryFn: () => api.get<{ exiftool: boolean; max_upload_mb: number }>('/api/metadata/capabilities'),
  })

  const analyse = useMutation({
    mutationFn: async (f: File) => api.parse<MetadataResult>(await api.upload('/api/metadata', f)),
  })
  const strip = useMutation({
    mutationFn: async (f: File) => {
      const res = await api.upload('/api/metadata/strip', f)
      if (!res.ok) await api.parse(res)
      const name = /filename="([^"]+)"/.exec(res.headers.get('content-disposition') ?? '')?.[1] ?? `clean_${f.name}`
      saveBlob(name, await res.blob())
      return { name }
    },
  })

  const pick = (f: File | undefined) => {
    if (!f) return
    setFile(f)
    strip.reset()
    analyse.mutate(f)
  }
  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    pick(e.dataTransfer.files[0])
  }

  const r = analyse.data
  const reasons = r
    ? [...new Set(r.highlights.map((h) => h.reason))].sort((a, b) => (REASONS[a]?.order ?? 9) - (REASONS[b]?.order ?? 9))
    : []

  return (
    <div className="mx-auto max-w-[1440px] px-4 pt-4 pb-12 md:px-6 md:pt-5">
      <h1 className="page-title text-2xl font-semibold">File metadata</h1>
      <p className="mt-1 max-w-[68ch] text-sm text-console-2">
        See what a photo, PDF or Office document says about where, when and on what it was made, then download a copy
        with that removed. Files are read by your backend and deleted straight after.
      </p>

      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className="mt-4"
      >
        {r && file ? (
          <Strip holder="var(--color-h-tgt)" code="FIL" className="strip-hero" bodyClassName="grid grid-cols-2 md:grid-cols-[minmax(0,1fr)_11rem_7rem_12rem_15rem]">
            <div className="strip-cell col-span-2 md:col-span-1">
              <span className="strip-label">File</span>
              <span className="block truncate text-lg font-semibold">{r.filename}</span>
            </div>
            <div className="strip-cell border-t border-paper-rule md:border-t-0">
              <span className="strip-label">Type</span>
              <span className="ind block truncate text-sm">{r.detected_type}</span>
            </div>
            <div className="strip-cell border-t border-paper-rule md:border-t-0">
              <span className="strip-label">Size</span>
              <span className="ind block text-sm">{formatBytes(r.size)}</span>
            </div>
            <div className="strip-cell col-span-2 border-t border-paper-rule md:col-span-1 md:border-t-0">
              <span className="strip-label">Read with</span>
              <span className="block text-sm">{r.extractor === 'exiftool' ? 'ExifTool' : 'Built-in parsers'}</span>
              <button className="text-xs text-link underline" onClick={() => inputRef.current?.click()}>
                Choose another file
              </button>
            </div>
            <div className="col-span-2 flex flex-col justify-center gap-1 border-t border-paper-rule p-1.5 md:col-span-1 md:border-t-0 md:border-l">
              <button
                disabled={!r.strippable || strip.isPending}
                onClick={() => strip.mutate(file)}
                className="btn-primary w-full py-2 text-sm"
              >
                {strip.isPending ? 'Removing metadata…' : 'Download a clean copy'}
              </button>
              <span className="px-1 text-2xs leading-tight text-ink-2" aria-live="polite">
                {strip.isSuccess
                  ? `Saved as ${strip.data.name}`
                  : strip.isError
                    ? (strip.error as Error).message
                    : r.strippable
                      ? 'JPEG and PNG keep their exact pixels'
                      : `${r.detected_type} needs ExifTool to clean`}
              </span>
            </div>
          </Strip>
        ) : (
          <button
            onClick={() => inputRef.current?.click()}
            className={`strip-empty w-full text-left transition-colors ${dragging ? 'border-scope bg-scope/10' : 'hover:border-console-3'}`}
          >
            <span className="grid place-content-center">
              <FileUp className="size-6 text-console-2" strokeWidth={1.5} aria-hidden />
            </span>
            <span className="border-l border-dashed border-rail px-4 py-4">
              <span className="block text-lg text-console">
                {analyse.isPending ? `Reading ${file?.name}…` : 'Drop a file here, or choose one'}
              </span>
              <span className="mt-1 block text-sm">
                Images, PDFs, Office documents, audio and video up to {caps.data?.max_upload_mb ?? 50} MB.{' '}
                {caps.data &&
                  (caps.data.exiftool
                    ? 'ExifTool is installed, so every format it knows is covered.'
                    : 'Installing ExifTool on the backend covers more formats.')}
              </span>
            </span>
          </button>
        )}
        <input ref={inputRef} type="file" className="sr-only" tabIndex={-1} onChange={(e) => {
            pick(e.target.files?.[0])
            e.target.value = '' // so choosing the same file again still fires onChange
          }}
        />
      </div>

      {analyse.isError && (
        <Strip holder="var(--color-h-int)" code="ERR" className="mt-6">
          <p role="alert" className="px-4 py-3">
            Couldn't read that file: {(analyse.error as Error).message}
          </p>
        </Strip>
      )}

      {r && (
        <div className="mt-6 grid gap-x-6 gap-y-8 lg:grid-cols-[minmax(0,1fr)_340px]">
          <div className="min-w-0 space-y-7">
            <section aria-labelledby="reveals-h">
              <div className="bay-head">
                <h2 id="reveals-h">What this file reveals</h2>
                <span className="ind font-normal text-console-2">{r.highlights.length}</span>
              </div>
              {reasons.length === 0 ? (
                <p className="mt-3 text-sm text-console-2">
                  No location, identity, device or timestamp fields found. Every field the file carries is listed below.
                </p>
              ) : (
                <ul className="mt-2 space-y-1.5">
                  {reasons.map((reason) => {
                    const items = r.highlights.filter((h) => h.reason === reason)
                    const meta = REASONS[reason] ?? { code: '—', holder: 'var(--color-h-none)' }
                    return (
                      <li key={reason} className="strip-land">
                        <Strip holder={meta.holder} code={meta.code} bodyClassName="grid md:grid-cols-[12rem_minmax(0,1fr)]">
                          <div className="strip-cell">
                            <span className="font-semibold">{reason.replace(' (may contain a username)', '')}</span>
                            <span className="block text-xs text-ink-2">
                              {items.length} field{items.length === 1 ? '' : 's'}
                            </span>
                          </div>
                          <dl className="strip-cell grid grid-cols-[minmax(6rem,auto)_minmax(0,1fr)] gap-x-4 gap-y-0.5 border-t border-paper-rule text-sm md:border-t-0">
                            {items.slice(0, 8).map((h) => (
                              <div key={`${h.group}.${h.tag}`} className="contents">
                                <dt className="truncate text-ink-2">{h.tag}</dt>
                                <dd className="min-w-0 break-words">{h.value}</dd>
                              </div>
                            ))}
                            {items.length > 8 && <dd className="col-span-2 text-ink-2">and {items.length - 8} more below</dd>}
                          </dl>
                        </Strip>
                      </li>
                    )
                  })}
                </ul>
              )}
            </section>

            <section aria-labelledby="fields-h">
              <div className="bay-head">
                <h2 id="fields-h">Every field</h2>
                <span className="ind font-normal text-console-2">
                  {Object.values(r.groups).reduce((n, g) => n + Object.keys(g).length, 0)}
                </span>
              </div>
              {Object.keys(r.groups).length === 0 && <p className="mt-3 text-sm text-console-2">No embedded metadata found.</p>}
              {Object.entries(r.groups).map(([g, fields]) => (
                <FieldGroup key={g} name={g} fields={fields} />
              ))}
              {r.errors.length > 0 && <p className="mt-4 text-sm text-alert">{r.errors.join('; ')}</p>}
            </section>
          </div>

          <aside className="space-y-7">
            {r.gps && (
              <section aria-labelledby="loc-h">
                <div className="bay-head">
                  <h2 id="loc-h">Where it was taken</h2>
                </div>
                <p className="ind mt-2 text-sm text-console-2">
                  {r.gps.lat.toFixed(6)}, {r.gps.lon.toFixed(6)}
                  {r.gps.alt != null && `, ${r.gps.alt.toFixed(0)} m`}
                </p>
                <MiniMap lat={r.gps.lat} lon={r.gps.lon} />
              </section>
            )}
            <section aria-labelledby="hash-h">
              <div className="bay-head">
                <h2 id="hash-h">Hashes</h2>
              </div>
              <dl className="mt-3 space-y-2.5 text-sm">
                {Object.entries(r.hashes).map(([algo, h]) => (
                  <div key={algo}>
                    <dt className="text-xs text-console-2">{algo.toUpperCase()}</dt>
                    <dd className="ind break-all">{h}</dd>
                  </div>
                ))}
              </dl>
              <Link to={`/recon?q=${r.hashes.sha256}`} className="mt-4 inline-block text-sm text-scope underline">
                Check this hash against threat intelligence
              </Link>
            </section>
          </aside>
        </div>
      )}
    </div>
  )
}

function FieldGroup({ name, fields }: { name: string; fields: Record<string, unknown> }) {
  const [open, setOpen] = useState(true)
  const entries = Object.entries(fields)
  return (
    <div className="mt-4">
      <button
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 rounded-md border border-white/[0.06] bg-white/[0.03] px-3 py-1 text-left hover:bg-white/[0.06]"
      >
        <ChevronDown className={`size-4 text-console-2 transition-transform duration-200 ${open ? '' : '-rotate-90'}`} aria-hidden />
        <span className="font-semibold">{name}</span>
        <span className="ind text-sm text-console-2">{entries.length}</span>
      </button>
      {open && (
        <dl className="mt-1 grid grid-cols-[minmax(8rem,15rem)_minmax(0,1fr)] text-sm">
          {entries.map(([k, v]) => (
            <div key={k} className="contents [&>*]:border-b [&>*]:border-rail/60 [&>*]:py-1">
              <dt className="truncate pr-4 pl-3 text-console-2" title={k}>
                {k}
              </dt>
              <dd className="min-w-0">
                <Value v={v} />
              </dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  )
}

function MiniMap({ lat, lon }: { lat: number; lon: number }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!ref.current) return
    const map = new maplibregl.Map({
      container: ref.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [lon, lat],
      zoom: 13,
      attributionControl: { compact: true },
    })
    new maplibregl.Marker({ color: '#e3737d' }).setLngLat([lon, lat]).addTo(map)
    return () => map.remove()
  }, [lat, lon])
  return <div ref={ref} className="mt-3 h-60 overflow-hidden rounded-lg border border-rail" />
}
