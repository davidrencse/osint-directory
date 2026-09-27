import { useQuery } from '@tanstack/react-query'
import Fuse from 'fuse.js'
import { useDeferredValue, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Strip } from '../components/Strip'
import { api, type Catalog, type Tool } from '../lib/api'

const PAGE = 120

type Filters = {
  free: boolean
  noSignup: boolean
  passive: boolean
  local: boolean
  showDead: boolean
}

const FILTER_LABEL: Record<keyof Filters, string> = {
  free: 'Free or freemium',
  noSignup: 'No sign-up',
  passive: 'Passive only',
  local: 'Runs locally',
  showDead: 'Include offline tools',
}

// The holder says how the tool touches the target: passive, active, or not recorded.
const OPSEC = {
  passive: { code: 'PAS', holder: 'var(--color-h-dns)', label: 'Passive: the target is not contacted' },
  active: { code: 'ACT', holder: 'var(--color-h-web)', label: 'Active: the tool contacts the target' },
  unknown: { code: '—', holder: 'var(--color-h-none)', label: 'Not recorded' },
}

function matches(t: Tool, f: Filters) {
  if (!f.showDead && t.deprecated) return false
  if (f.free && !/free/.test(t.pricing)) return false
  if (f.noSignup && t.registration) return false
  if (f.passive && t.opsec !== 'passive') return false
  if (f.local && !t.local_install) return false
  return true
}

export default function ToolsPage() {
  const [params, setParams] = useSearchParams()
  const [query, setQuery] = useState(params.get('q') ?? '')
  const deferred = useDeferredValue(query)
  const category = params.get('c')
  const [filters, setFilters] = useState<Filters>({ free: false, noSignup: false, passive: false, local: false, showDead: false })
  const [limit, setLimit] = useState(PAGE)

  const catalog = useQuery({
    queryKey: ['catalog'],
    queryFn: () => api.get<Catalog>('/api/tools/catalog'),
    staleTime: Infinity,
  })

  const fuse = useMemo(
    () =>
      new Fuse(catalog.data?.tools ?? [], {
        keys: [
          { name: 'name', weight: 3 },
          { name: 'category', weight: 1.5 },
          { name: 'path', weight: 1 },
          { name: 'description', weight: 1 },
          { name: 'input', weight: 1 },
          { name: 'url', weight: 0.5 },
        ],
        threshold: 0.3,
        ignoreLocation: true,
      }),
    [catalog.data],
  )

  const filtered = useMemo(() => {
    const base = deferred.trim() ? fuse.search(deferred.trim()).map((r) => r.item) : (catalog.data?.tools ?? [])
    return base.filter((t) => matches(t, filters))
  }, [deferred, fuse, catalog.data, filters])

  const categories = useMemo(() => {
    const m = new Map<string, number>()
    for (const t of filtered) m.set(t.category, (m.get(t.category) ?? 0) + 1)
    return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0]))
  }, [filtered])

  const visible = category ? filtered.filter((t) => t.category === category || t.also_in?.includes(category)) : filtered

  const setCategory = (c: string | null) => {
    const next = new URLSearchParams(params)
    if (c) next.set('c', c)
    else next.delete('c')
    setParams(next, { replace: true })
    setLimit(PAGE)
  }

  return (
    <div className="mx-auto max-w-[1440px] px-4 pt-4 pb-12 md:px-6 md:pt-5">
      <h1 className="page-title text-2xl font-semibold">Tool library</h1>
      <p className="mt-1 max-w-[68ch] text-sm text-console-2">
        {catalog.data ? catalog.data.tools.length.toLocaleString() : 'Every'} tools from OSINT Framework and OSINT
        Directory. Each entry opens the tool itself; nothing is looked up on your behalf.
      </p>

      <Strip holder="var(--color-h-tgt)" code="FND" className="strip-hero mt-4" bodyClassName="flex flex-col justify-center px-3 py-2">
        <label htmlFor="tool-q" className="strip-label">
          Find a tool
        </label>
        <input
          id="tool-q"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setLimit(PAGE)
          }}
          placeholder="By name, purpose or input: subdomains, exif, ASN, certificate"
          className="w-full bg-transparent py-0.5 text-lg text-ink placeholder:text-sm placeholder:text-ink-2 focus:outline-none"
        />
      </Strip>
      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 pl-1">
        {(Object.keys(FILTER_LABEL) as (keyof Filters)[]).map((k) => (
          <label key={k} className="flex cursor-pointer items-center gap-2 text-sm text-console-2">
            <input
              type="checkbox"
              className="check"
              checked={filters[k]}
              onChange={(e) => setFilters((f) => ({ ...f, [k]: e.target.checked }))}
            />
            {FILTER_LABEL[k]}
          </label>
        ))}
      </div>

      {catalog.isError && (
        <Strip holder="var(--color-h-int)" code="ERR" className="mt-6">
          <p className="px-4 py-3">{(catalog.error as Error).message}</p>
        </Strip>
      )}

      <div className="mt-8 grid gap-8 md:grid-cols-[250px_minmax(0,1fr)]">
        <nav aria-label="Categories" className="md:sticky md:top-4 md:max-h-[calc(100vh-2rem)] md:self-start md:overflow-y-auto">
          <select
            className="field w-full px-2 py-2 md:hidden"
            value={category ?? ''}
            onChange={(e) => setCategory(e.target.value || null)}
            aria-label="Category"
          >
            <option value="">All categories ({filtered.length})</option>
            {categories.map(([c, n]) => (
              <option key={c} value={c}>
                {c} ({n})
              </option>
            ))}
          </select>
          <ul className="hidden space-y-0.5 text-sm md:block">
            {[[null, filtered.length] as const, ...categories].map(([c, n]) => {
              const on = category === c
              return (
                <li key={c ?? 'all'}>
                  <button
                    onClick={() => setCategory(c)}
                    aria-current={on ? 'true' : undefined}
                    className={`flex w-full justify-between gap-2 rounded-md px-2.5 py-1 text-left ${
                      on ? 'nav-active font-semibold text-console' : 'text-console-2 hover:bg-bay-2 hover:text-console'
                    }`}
                  >
                    <span className="truncate">{c ?? 'All categories'}</span>
                    <span className="ind">{n}</span>
                  </button>
                </li>
              )
            })}
          </ul>
          <dl className="mt-6 hidden space-y-1.5 text-xs text-console-2 md:block">
            {Object.values(OPSEC).map((o) => (
              <div key={o.code} className="flex items-center gap-2">
                <dt className="w-9 shrink-0 text-center font-semibold" style={{ color: o.holder }}>
                  {o.code}
                </dt>
                <dd>{o.label}</dd>
              </div>
            ))}
          </dl>
        </nav>

        <section aria-label="Tools" aria-live="polite">
          {catalog.isPending && <p className="text-console-2">Loading the catalog…</p>}
          {catalog.data && visible.length === 0 && (
            <p className="text-console-2">No tools match. Clear a filter or try a broader word.</p>
          )}
          <ul className="space-y-1">
            {visible.slice(0, limit).map((t) => (
              <ToolRow key={t.id} t={t} />
            ))}
          </ul>
          {visible.length > limit && (
            <button
              onClick={() => setLimit(limit + PAGE)}
              className="mt-4 rounded-md border border-rail px-4 py-2 text-sm hover:border-scope hover:text-scope"
            >
              Show {Math.min(PAGE, visible.length - limit)} more of {visible.length - limit}
            </button>
          )}
          {catalog.data && (
            <p className="mt-8 text-xs text-console-2">
              Sources:{' '}
              {Object.entries(catalog.data.sources).map(([k, s], i) => (
                <span key={k}>
                  {i > 0 && ', '}
                  <a href={s.url} target="_blank" rel="noreferrer" className="underline hover:text-console">
                    {k}
                  </a>{' '}
                  ({s.count}
                  {s.license ? `, ${s.license}` : ''})
                </span>
              ))}
              . Catalog built {new Date(catalog.data.generated_at).toLocaleDateString()}.
            </p>
          )}
        </section>
      </div>
    </div>
  )
}

function ToolRow({ t }: { t: Tool }) {
  const op = t.opsec === 'passive' ? OPSEC.passive : t.opsec ? OPSEC.active : OPSEC.unknown
  const facts = [
    t.pricing !== 'unknown' ? t.pricing : null,
    t.registration ? 'sign-up' : null,
    t.local_install ? 'install locally' : null,
    t.google_dork ? 'search dork' : null,
    t.manual_url_edit ? 'edit the URL by hand' : null,
    t.deprecated ? 'offline' : null,
  ].filter(Boolean)
  let host = ''
  try {
    host = new URL(t.url).hostname.replace(/^www\./, '')
  } catch {
    /* malformed catalog URL */
  }
  return (
    <li className={`grid grid-cols-[3.5rem_minmax(0,1fr)] overflow-hidden rounded-[10px] border border-white/[0.07] bg-gradient-to-b from-white/[0.04] to-white/[0.01] transition-colors hover:border-white/[0.16] ${t.deprecated ? 'opacity-60' : ''}`}>
      <span className="grid place-content-center border-r border-rail text-2xs font-semibold tracking-wider" style={{ color: op.holder }} title={op.label}>
        {op.code}
      </span>
      <div className="min-w-0 px-3.5 py-2">
        <div className="flex flex-wrap items-baseline gap-x-3">
          <a
            href={t.url}
            target="_blank"
            rel="noreferrer"
            className={`font-semibold text-console underline decoration-rail underline-offset-4 hover:text-scope hover:decoration-scope ${t.deprecated ? 'line-through' : ''}`}
          >
            {t.name}
          </a>
          <span className="ind text-xs text-console-2">{host}</span>
        </div>
        <div className="mt-0.5 text-xs text-console-2">{t.path.join(' / ')}</div>
        {t.description && <p className="mt-1 max-w-[75ch] text-sm leading-snug text-console-2">{t.description}</p>}
        {(facts.length > 0 || t.input) && (
          <p className="mt-1.5 text-xs text-console-2">
            {t.input && <>Takes {t.input.toLowerCase()}. </>}
            {facts.join(', ')}
          </p>
        )}
      </div>
    </li>
  )
}
