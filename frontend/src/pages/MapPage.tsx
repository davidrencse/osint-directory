import { useQueries, useQuery } from '@tanstack/react-query'
import { maplibregl } from '../lib/maplibre'
import type { GeoJSONSource, LayerSpecification, Map as MlMap } from 'maplibre-gl'
import { Layers, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, type FeatureCollection, type LayerInfo } from '../lib/api'
import { humanKey } from '../lib/format'
import { arrowImage, LAYER_CODE, LAYER_STYLE, SWATCH } from '../lib/mapStyles'
import { nightPolygon } from '../lib/terminator'

const BASEMAP = 'https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json'
const DEFAULT_LAYERS = ['earthquakes', 'disasters', 'cables', 'incidents', 'daynight']
const GROUP_LABEL: Record<string, string> = {
  hazards: 'Hazards',
  transport: 'Air, sea and space',
  infrastructure: 'Infrastructure',
  intel: 'News and events',
  sky: 'Sky',
}
// Draw order, bottom to top.
const Z_ORDER = ['daynight', 'cables', 'landings', 'fires', 'news', 'incidents', 'disasters', 'earthquakes', 'ships', 'aircraft', 'iss']

const DAYNIGHT: LayerInfo = {
  id: 'daynight',
  label: 'Day and night',
  group: 'sky',
  refresh_s: 60,
  uses_bbox: false,
  description: 'Night side of the terminator, computed in your browser',
  enabled: true,
  key_field: null,
}

function escapeHtml(s: string) {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!)
}

function popupHtml(layer: LayerInfo, props: Record<string, unknown>) {
  const rows = Object.entries(props)
    .filter(([k, v]) => k !== 'url' && k !== 'color' && v !== null && v !== '' && v !== undefined)
    .slice(0, 14)
    .map(([k, v]) => {
      let val = String(v)
      if (k === 'time' && typeof v === 'number') val = new Date(v).toUTCString()
      return `<tr><td style="color:var(--color-console-2);padding:1px 14px 1px 0;vertical-align:top;white-space:nowrap">${escapeHtml(
        humanKey(k),
      )}</td><td style="font-family:var(--font-mono);word-break:break-word">${escapeHtml(val)}</td></tr>`
    })
    .join('')
  const url = typeof props.url === 'string' && /^https?:\/\//.test(props.url) ? props.url : null
  const colour = SWATCH[layer.id] ?? '#888'
  return `<div style="max-width:320px;font-size:13px">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
      <span style="background:${colour};color:var(--color-holder-ink);font-weight:700;font-size:11px;padding:1px 6px;border-radius:2px">${LAYER_CODE[layer.id] ?? ''}</span>
      <span style="font-weight:700">${escapeHtml(layer.label)}</span>
    </div>
    <table style="line-height:1.4">${rows}</table>
    ${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer" style="display:inline-block;margin-top:8px;color:var(--color-scope);text-decoration:underline">Open at the source</a>` : ''}
  </div>`
}

function boundsParam(map: MlMap) {
  const b = map.getBounds()
  return [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].map((n) => n.toFixed(2)).join(',')
}

export default function MapPage() {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MlMap | null>(null)
  const [ready, setReady] = useState(false)
  const [bbox, setBbox] = useState<string | null>(null)
  const [globe, setGlobe] = useState(true)
  const [panelOpen, setPanelOpen] = useState(() => window.matchMedia('(min-width: 768px)').matches)
  const [params, setParams] = useSearchParams()

  const active = useMemo(
    () => new Set((params.get('layers') ?? DEFAULT_LAYERS.join(',')).split(',').filter(Boolean)),
    [params],
  )
  const toggle = (id: string) => {
    const next = new Set(active)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setParams({ layers: [...next].join(',') }, { replace: true })
  }

  const layerList = useQuery({ queryKey: ['geo-layers'], queryFn: () => api.get<LayerInfo[]>('/api/geo/layers') })
  const layers = useMemo(() => [...(layerList.data ?? []), DAYNIGHT], [layerList.data])
  const byId = useMemo(() => Object.fromEntries(layers.map((l) => [l.id, l])), [layers])

  const remote = layers.filter((l) => l.id !== 'daynight' && active.has(l.id) && l.enabled)
  const queries = useQueries({
    queries: remote.map((l) => ({
      queryKey: ['geo', l.id, l.uses_bbox ? bbox : null],
      queryFn: () =>
        api.get<FeatureCollection>(`/api/geo/${l.id}${l.uses_bbox && bbox ? `?bbox=${bbox}` : ''}`),
      refetchInterval: l.refresh_s ? l.refresh_s * 1000 : false,
      enabled: ready && (!l.uses_bbox || bbox !== null),
      placeholderData: (prev: FeatureCollection | undefined) => prev,
    })),
  })
  const status = Object.fromEntries(remote.map((l, i) => [l.id, queries[i]]))

  // --- map lifecycle ---------------------------------------------------------------------
  useEffect(() => {
    if (!container.current) return
    const map = new maplibregl.Map({
      container: container.current,
      style: BASEMAP,
      center: [15, 25],
      zoom: container.current.clientWidth < 640 ? 0.9 : 1.6,
      attributionControl: { compact: true },
    })
    mapRef.current = map
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right')
    map.on('load', () => {
      map.addImage('arrow', arrowImage(), { sdf: true })
      setBbox(boundsParam(map))
      setReady(true)
    })
    let t: ReturnType<typeof setTimeout>
    map.on('moveend', () => {
      clearTimeout(t)
      t = setTimeout(() => setBbox(boundsParam(map)), 400)
    })
    return () => {
      clearTimeout(t)
      map.remove()
      mapRef.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    map.setProjection({ type: globe ? 'globe' : 'mercator' })
  }, [globe, ready])

  const ensureLayer = useCallback(
    (id: string, data: GeoJSON.FeatureCollection | GeoJSON.Feature) => {
      const map = mapRef.current
      if (!map) return
      const src = map.getSource(id) as GeoJSONSource | undefined
      if (src) {
        src.setData(data)
        return
      }
      map.addSource(id, { type: 'geojson', data })
      const before = Z_ORDER.slice(Z_ORDER.indexOf(id) + 1).find((z) => map.getLayer(z))
      for (const spec of LAYER_STYLE[id] ?? []) {
        const { idSuffix, ...rest } = spec
        const layerId = idSuffix ? `${id}-${idSuffix}` : id
        map.addLayer({ ...rest, id: layerId, source: id } as LayerSpecification, before)
        const info = byId[id]
        if (id !== 'daynight' && info) {
          map.on('click', layerId, (e) => {
            const f = e.features?.[0]
            if (!f) return
            new maplibregl.Popup({ maxWidth: '320px' })
              .setLngLat(e.lngLat)
              .setHTML(popupHtml(info, f.properties as Record<string, unknown>))
              .addTo(map)
          })
          map.on('mouseenter', layerId, () => (map.getCanvas().style.cursor = 'pointer'))
          map.on('mouseleave', layerId, () => (map.getCanvas().style.cursor = ''))
        }
      }
    },
    [byId],
  )

  const setVisible = useCallback((id: string, visible: boolean) => {
    const map = mapRef.current
    if (!map) return
    for (const spec of LAYER_STYLE[id] ?? []) {
      const layerId = spec.idSuffix ? `${id}-${spec.idSuffix}` : id
      if (map.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', visible ? 'visible' : 'none')
    }
  }, [])

  // Push fetched data into the map and sync visibility. Only layers whose data changed are pushed:
  // setData re-parses the whole GeoJSON in the worker, and cables alone is several MB.
  const pushed = useRef(new Map<string, FeatureCollection>())
  const dataStamp = queries.map((q) => q.dataUpdatedAt).join(',')
  useEffect(() => {
    if (!ready) return
    remote.forEach((l, i) => {
      const d = queries[i].data
      if (!d || pushed.current.get(l.id) === d) return
      ensureLayer(l.id, d)
      pushed.current.set(l.id, d)
    })
    for (const l of layers) setVisible(l.id, active.has(l.id))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, dataStamp, active, layers, ensureLayer, setVisible])

  // Day/night overlay, recomputed each minute.
  useEffect(() => {
    if (!ready || !active.has('daynight')) return
    const draw = () => ensureLayer('daynight', nightPolygon())
    draw()
    setVisible('daynight', true)
    const id = setInterval(draw, 60_000)
    return () => clearInterval(id)
  }, [ready, active, ensureLayer, setVisible])

  const groups = useMemo(() => {
    const m = new Map<string, LayerInfo[]>()
    for (const l of layers) m.set(l.group, [...(m.get(l.group) ?? []), l])
    return [...m.entries()]
  }, [layers])

  return (
    <div className="relative h-full min-h-[480px]">
      <div className="absolute inset-0">
        <div ref={container} className="h-full w-full" role="region" aria-label="World map" />
      </div>

      <div className="absolute top-3 left-3 z-10 flex max-h-[calc(100%-1.5rem)] flex-col">
        {!panelOpen ? (
          <button
            onClick={() => setPanelOpen(true)}
            className="flex items-center gap-2 glass rounded-lg px-3 py-2 text-sm"
          >
            <Layers className="size-4 text-scope" aria-hidden /> Layers
            <span className="ind text-console-2">{active.size}</span>
          </button>
        ) : (
          <div className="flex w-80 max-w-[calc(100vw-1.5rem)] flex-col overflow-hidden glass rounded-xl">
            <div className="flex items-center gap-2 border-b border-rail px-3 py-2.5">
              <span className="font-semibold">Layers</span>
              <div role="group" aria-label="Projection" className="ml-auto flex overflow-hidden rounded-md border border-rail text-xs">
                {[
                  { v: true, label: 'Globe' },
                  { v: false, label: 'Flat' },
                ].map((o) => (
                  <button
                    key={o.label}
                    aria-pressed={globe === o.v}
                    onClick={() => setGlobe(o.v)}
                    className={`px-2.5 py-1 ${globe === o.v ? 'btn-primary rounded-none! font-semibold' : 'text-console-2 hover:bg-bay-2'}`}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
              <button onClick={() => setPanelOpen(false)} aria-label="Hide layers" className="btn-quiet p-1">
                <X className="size-4" aria-hidden />
              </button>
            </div>
            <div className="overflow-y-auto px-3 pb-3">
              {layerList.isError && (
                <p className="mt-3 text-sm text-alert">The backend is not answering, so only day and night is available.</p>
              )}
              {groups.map(([group, list]) => (
                <fieldset key={group} className="mt-3">
                  <legend className="mb-1.5 text-xs text-console-2">{GROUP_LABEL[group] ?? group}</legend>
                  <div className="space-y-1.5">
                    {list.map((l) => {
                      const q = status[l.id]
                      const meta = q?.data?.meta
                      const on = active.has(l.id) && l.enabled
                      const count =
                        on && q?.isFetching && !meta ? 'loading' : on && meta?.count != null ? meta.count.toLocaleString() : ''
                      return (
                        <label
                          key={l.id}
                          title={l.description}
                          className={`grid grid-cols-[2.75rem_minmax(0,1fr)] overflow-hidden rounded-lg has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-scope ${
                            on
                              ? 'cursor-pointer border border-white/[0.1] bg-gradient-to-b from-white/[0.05] to-white/[0.01] hover:border-white/[0.2]'
                              : l.enabled
                                ? 'cursor-pointer border border-dashed border-rail hover:border-console-3'
                                : 'cursor-not-allowed border border-dashed border-rail opacity-60'
                          }`}
                        >
                          <input
                            type="checkbox"
                            className="sr-only"
                            checked={on}
                            disabled={!l.enabled}
                            onChange={() => toggle(l.id)}
                          />
                          <span
                            className="grid place-content-center text-2xs font-semibold"
                            style={{ color: on ? SWATCH[l.id] : 'var(--color-console-3)' }}
                          >
                            {LAYER_CODE[l.id]}
                          </span>
                          <span
                            className={`flex min-w-0 items-center gap-2 px-2.5 py-1 text-sm ${on ? 'text-console' : 'text-console-2'}`}
                          >
                            <span className="min-w-0 flex-1">
                              <span className="block truncate">{l.label}</span>
                              {!l.enabled && (
                                <span className="ind block truncate text-2xs">Needs {l.key_field?.toUpperCase()}</span>
                              )}
                              {on && q?.isError && (
                                <span className="block text-2xs text-alert">No answer. Retrying on the next refresh.</span>
                              )}
                            </span>
                            <span className="ind shrink-0 text-xs">{count}</span>
                          </span>
                        </label>
                      )
                    })}
                  </div>
                </fieldset>
              ))}
              <p className="mt-3 text-xs leading-snug text-console-2">
                Printed strips are on the map. Aircraft and vessels load for the area in view. Select any point for its
                details and source.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
