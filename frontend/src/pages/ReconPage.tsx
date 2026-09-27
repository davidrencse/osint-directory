import { useQuery } from '@tanstack/react-query'
import { ChevronDown, Download, ExternalLink, Square } from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { RadarScope } from '../components/RadarScope'
import { GreaseCross, GreaseTick, Strip } from '../components/Strip'
import { JsonBlock, KeyValueGrid } from '../components/Value'
import {
  api,
  ApiError,
  TYPE_LABEL,
  type IndicatorType,
  type PipelineInfo,
  type PipelineResult,
  type Pivot,
  type Target,
} from '../lib/api'
import { CATEGORIES, categoryOf } from '../lib/categories'
import { brief, humanKey, ms } from '../lib/format'
import { exportJson, exportMarkdown } from '../lib/report'
import { useSweep, type SweepState } from '../lib/sweep'

const EXAMPLES = ['example.com', '1.1.1.1', 'AS13335', 'https://example.org/login']
const PIVOT_CODE: Record<IndicatorType, string> = { domain: 'DOM', ip: 'IP', cidr: 'NET', asn: 'ASN', url: 'URL', hash: 'HSH' }

function useDebounced<T>(value: T, delay: number) {
  const [v, setV] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setV(value), delay)
    return () => clearTimeout(id)
  }, [value, delay])
  return v
}

/** Ticks on its own so the 100 ms clock re-renders this span, not the whole board. */
function Elapsed({ state }: { state: SweepState }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!state.running) return
    const id = setInterval(() => setNow(Date.now()), 100)
    return () => clearInterval(id)
  }, [state.running])
  const elapsed = state.startedAt ? (state.finishedAt ?? now) - state.startedAt : 0
  return <span className="ind">, {ms(elapsed)}</span>
}

const IP_RE = /^\d{1,3}(\.\d{1,3}){3}$|:/

export default function ReconPage() {
  const [params, setParams] = useSearchParams()
  const [input, setInput] = useState(params.get('q') ?? '')
  const [authorized, setAuthorized] = useState(false)
  const [fresh, setFresh] = useState(false)
  const [hovered, setHovered] = useState<string | null>(null)
  const { state, start, stop } = useSweep()

  const debounced = useDebounced(input.trim(), 250)
  const detect = useQuery({
    queryKey: ['classify', debounced],
    queryFn: () => api.get<Target>(`/api/recon/classify?target=${encodeURIComponent(debounced)}`),
    enabled: debounced.length > 0,
    retry: false,
  })
  const pipelines = useQuery({
    queryKey: ['pipelines'],
    queryFn: () => api.get<PipelineInfo[]>('/api/recon/pipelines'),
  })
  const scope = useQuery({
    queryKey: ['scope'],
    queryFn: () => api.get<{ entries: string[] }>('/api/settings/scope'),
  })

  const run = (value: string) => {
    if (!authorized || !value.trim()) return
    setInput(value)
    setParams({ q: value }, { replace: true })
    start(value.trim(), { fresh })
  }
  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    run(input)
  }

  const detectError = detect.error instanceof ApiError ? detect.error.message : null
  const outOfScope = detect.data?.in_scope === false
  const canRun = authorized && !!detect.data && !outOfScope && !state.running && debounced === input.trim()

  // Before a sweep, the scope previews which sources the typed target would reach.
  const previewPlan = useMemo<PipelineInfo[]>(() => {
    const t = detect.data
    if (!t || !pipelines.data) return []
    // A leading digit alone doesn't mean IP: 1password.com and 163.com are domains.
    const host = t.type === 'url' ? (IP_RE.test(t.host ?? '') ? 'ip' : 'domain') : null
    return pipelines.data
      .filter((p) => p.accepts.includes(t.type) || (host !== null && p.accepts.includes(host as IndicatorType)))
      .map((p) => ({ ...p, status: p.enabled ? 'pending' : 'skipped' }))
  }, [detect.data, pipelines.data])

  const plan = state.target ? state.plan : previewPlan

  return (
    <div className="mx-auto max-w-[1440px] px-4 pt-4 pb-12 md:px-6 md:pt-5">
      <form onSubmit={onSubmit} aria-label="Sweep a target" className="@container">
        <Strip holder="var(--color-h-tgt)" code="TGT" className="strip-hero min-h-[4rem]" bodyClassName="grid grid-cols-2 @4xl:grid-cols-[minmax(0,1fr)_9.5rem_9.5rem_14rem_10rem]">
          <div className="strip-cell col-span-2 flex flex-col justify-center @4xl:col-span-1">
            <label htmlFor="target" className="strip-label">
              Target
            </label>
            <input
              id="target"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Domain, IP, network, ASN, URL or file hash"
              autoComplete="off"
              spellCheck={false}
              className="w-full min-w-0 bg-transparent py-1 text-lg text-ink placeholder:text-sm placeholder:text-ink-2 focus:outline-none md:text-xl"
            />
          </div>
          <div className="strip-cell flex flex-col justify-center border-t border-paper-rule @4xl:border-t-0">
            <span className="strip-label">Detected as</span>
            <span className="font-semibold" aria-live="polite">
              {debounced && detect.data ? TYPE_LABEL[detect.data.type] : debounced && detectError ? 'Not recognised' : 'Waiting for input'}
            </span>
          </div>
          <div className="strip-cell flex flex-col justify-center border-t border-paper-rule @4xl:border-t-0">
            <span className="strip-label">Scope</span>
            <Link
              to="/settings"
              className={`font-semibold underline decoration-paper-rule underline-offset-4 hover:decoration-ink ${outOfScope ? 'text-grease-red' : ''}`}
            >
              {!scope.data?.entries.length
                ? 'No scope set'
                : !debounced || !detect.data
                  ? `${scope.data.entries.length} entries`
                  : outOfScope
                    ? 'Outside scope'
                    : 'In scope'}
            </Link>
          </div>
          <div className="strip-cell col-span-2 flex flex-col justify-center border-t border-paper-rule @4xl:col-span-1 @4xl:border-t-0">
            <span className="strip-label">Authorization</span>
            <label className="flex cursor-pointer items-center gap-2 text-sm leading-tight">
              <input
                type="checkbox"
                className="check text-ink"
                checked={authorized}
                onChange={(e) => setAuthorized(e.target.checked)}
              />
              I'm authorized to test this target
            </label>
          </div>
          <div className="col-span-2 flex border-t border-paper-rule p-1.5 @4xl:col-span-1 @4xl:border-t-0 @4xl:border-l">
            {state.running ? (
              <button
                type="button"
                onClick={stop}
                className="flex w-full items-center justify-center gap-2 rounded-md border border-rail text-base font-semibold text-console hover:border-alert hover:text-alert"
              >
                <Square className="size-4" aria-hidden /> Stop sweep
              </button>
            ) : (
              <button type="submit" disabled={!canRun} className="btn-primary w-full py-2 text-sm">
                Sweep
              </button>
            )}
          </div>
        </Strip>

        <div className="mt-2.5 flex min-h-6 flex-wrap items-center gap-x-6 gap-y-2 pl-1 text-sm">
          <div className="min-w-0 flex-1">
            {debounced && detectError && <span className="text-alert">{detectError}</span>}
            {outOfScope && (
              <span className="text-alert">
                This target is outside your engagement scope.{' '}
                <Link to="/settings" className="underline">
                  Edit the scope in Settings
                </Link>{' '}
                or choose another target.
              </span>
            )}
            {!debounced && (
              <span className="text-console-2">
                Try{' '}
                {EXAMPLES.map((ex, i) => (
                  <span key={ex}>
                    <button type="button" className="ind text-console underline decoration-rail hover:text-scope" onClick={() => setInput(ex)}>
                      {ex}
                    </button>
                    {i < EXAMPLES.length - 1 ? ', ' : ''}
                  </span>
                ))}
              </span>
            )}
            {debounced && detect.data && !outOfScope && !authorized && !state.running && (
              <span className="text-console-2">Tick the authorization box to enable the sweep.</span>
            )}
          </div>
          <label className="flex cursor-pointer items-center gap-2 text-console-2">
            <input type="checkbox" className="check" checked={fresh} onChange={(e) => setFresh(e.target.checked)} />
            Ask every source again (ignore the one-hour cache)
          </label>
        </div>
      </form>

      {state.error && (
        <Strip holder="var(--color-h-int)" code="ERR" className="mt-6">
          <p role="alert" className="px-4 py-3 font-semibold">
            {state.error}
          </p>
        </Strip>
      )}

      <div className="mt-6 grid gap-x-6 gap-y-8 lg:grid-cols-[minmax(0,1fr)_290px]">
        <div className="min-w-0">
          {state.target ? (
            <Board state={state} hovered={hovered} onHover={setHovered} />
          ) : (
            <Legend plan={previewPlan} pipelines={pipelines.data} failed={pipelines.isError} />
          )}
        </div>

        <aside className="space-y-7 lg:sticky lg:top-6 lg:self-start">
          <section aria-label="Radar">
            <RadarScope
              plan={plan}
              results={state.results}
              running={state.running}
              hovered={hovered}
              onHover={setHovered}
              centreLabel={state.target ? PIVOT_CODE[state.target.type] : detect.data ? PIVOT_CODE[detect.data.type] : undefined}
            />
          </section>
          {state.target && (
            <>
              <Pivots state={state} onPivot={(p) => run(p.value)} canPivot={authorized && !state.running} authorized={authorized} />
              <OtherTools target={state.target} />
            </>
          )}
        </aside>
      </div>
    </div>
  )
}

/* --------------------------------------------------------------------------------- */

function Legend({
  plan,
  pipelines,
  failed,
}: {
  plan: PipelineInfo[]
  pipelines?: PipelineInfo[]
  failed: boolean
}) {
  if (failed)
    return (
      <Strip holder="var(--color-h-int)" code="ERR">
        <p className="px-4 py-3">
          The backend isn't answering. Start it with <code className="ind">uv run uvicorn app.main:app</code> in the{' '}
          <code className="ind">backend</code> folder, then reload this page.
        </p>
      </Strip>
    )
  const counting = plan.length ? plan : pipelines ?? []
  return (
    <section aria-labelledby="legend-h">
      <div className="bay-head">
        <h2 id="legend-h">{plan.length ? `${plan.length} sources will check this target` : 'What a sweep checks'}</h2>
      </div>
      <p className="mt-3 max-w-[68ch] text-sm text-console-2">
        A sweep prints one strip per source. Strips land in the order their answers arrive, so a slow source never holds
        up the rest. Hosts, addresses and networks they discover collect as pivots on the right, ready to sweep next.
      </p>
      <ul className="@container mt-3 space-y-1.5">
        {CATEGORIES.map((cat) => {
          const members = counting.filter((p) => p.category === cat.id)
          const ready = members.filter((p) => p.enabled).length
          if (plan.length > 0 && members.length === 0)
            return (
              <li key={cat.id} className="strip-empty">
                <span className="grid place-content-center text-xs font-semibold text-console-3">{cat.code}</span>
                <span className="flex flex-wrap items-baseline gap-x-4 border-l border-dashed border-rail px-3 py-2.5 text-sm">
                  <span className="text-console">{cat.label}</span>
                  <span>Doesn't apply to this kind of target</span>
                </span>
              </li>
            )
          return (
            <li key={cat.id}>
              <Strip holder={cat.holder} code={cat.code} bodyClassName="grid @2xl:grid-cols-[14rem_minmax(0,1fr)_9rem]">
                <div className="strip-cell">
                  <span className="font-semibold">{cat.label}</span>
                </div>
                <div className="strip-cell text-sm">{cat.checks}</div>
                <div className="strip-cell text-sm">
                  {members.length === 0 ? (
                    <span className="text-ink-2">{plan.length ? 'Not for this type' : 'No sources'}</span>
                  ) : (
                    <>
                      <span className="ind font-semibold">{ready}</span> of <span className="ind">{members.length}</span> ready
                    </>
                  )}
                </div>
              </Strip>
            </li>
          )
        })}
      </ul>
      {counting.some((p) => !p.enabled) && (
        <p className="mt-3 text-sm text-console-2">
          Sources that need an API key stay in their holders until you add one.{' '}
          <Link to="/settings" className="text-scope underline">
            See which keys unlock what
          </Link>
          .
        </p>
      )}
    </section>
  )
}

/* --------------------------------------------------------------------------------- */

function Board({
  state,
  hovered,
  onHover,
}: {
  state: SweepState
  hovered: string | null
  onHover: (n: string | null) => void
}) {
  const [open, setOpen] = useState<Record<string, boolean>>({})
  const t = state.target!
  const landed = Object.values(state.results)
  const waiting = state.plan.filter((p) => p.status === 'pending' && !state.results[p.name])
  const notRun = state.plan.filter((p) => p.status === 'skipped')
  const answered = landed.filter((r) => r.status === 'ok').length
  const unable = landed.filter((r) => r.status === 'error').length

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-baseline gap-x-4 gap-y-2">
        <h2 className="ind text-lg font-semibold break-all">{t.value}</h2>
        <p className="text-sm text-console-2" aria-live="polite">
          {TYPE_LABEL[t.type]}, {state.running ? 'sweeping' : 'swept'}:{' '}
          <span className="text-ok">{answered} answered</span>
          {unable > 0 && <span className="text-alert">, {unable} unable</span>}
          {waiting.length > 0 && <span className="text-console">, {waiting.length} waiting</span>}
          <Elapsed state={state} />
        </p>
        {!state.running && landed.length > 0 && (
          <div className="ml-auto flex gap-1">
            <button onClick={() => exportMarkdown(state)} className="btn-quiet flex items-center gap-1.5 px-2.5 py-1 text-sm">
              <Download className="size-4" aria-hidden /> Markdown report
            </button>
            <button onClick={() => exportJson(state)} className="btn-quiet flex items-center gap-1.5 px-2.5 py-1 text-sm">
              <Download className="size-4" aria-hidden /> JSON
            </button>
          </div>
        )}
      </header>

      {waiting.length > 0 && (
        <section aria-labelledby="waiting-h">
          <div className="bay-head">
            <h3 id="waiting-h">Waiting for an answer</h3>
            <span className="ind font-normal text-console-2">{waiting.length}</span>
          </div>
          <ul className="mt-3 flex flex-wrap gap-2">
            {waiting.map((p) => {
              const cat = categoryOf(p.category)
              return (
                <li key={p.name}>
                  <Strip holder={cat.holder} code={cat.code} className="opacity-80" bodyClassName="relative overflow-hidden">
                    <span className="block px-3 py-2 text-sm whitespace-nowrap">{p.label}</span>
                    <span className="absolute inset-x-0 bottom-0 h-0.5 overflow-hidden" aria-hidden>
                      <span className="printing block h-full w-1/3 bg-ink/50" />
                    </span>
                  </Strip>
                </li>
              )
            })}
          </ul>
        </section>
      )}

      <section aria-labelledby="results-h">
        <div className="bay-head">
          <h3 id="results-h">Results</h3>
          <span className="ind font-normal text-console-2">
            {landed.length} of {state.plan.length - notRun.length}
          </span>
          <span className="ml-auto hidden text-xs font-normal text-console-2 md:inline">In the order they arrived</span>
        </div>
        {landed.length === 0 ? (
          <p className="mt-4 text-sm text-console-2">The first answers usually land within a second.</p>
        ) : (
          <ol className="@container mt-2 space-y-1.5">
            {landed.map((r) => (
              <ResultStrip
                key={r.name}
                result={r}
                open={!!open[r.name]}
                onToggle={() => setOpen((o) => ({ ...o, [r.name]: !o[r.name] }))}
                highlighted={hovered === r.name}
                onHover={onHover}
              />
            ))}
          </ol>
        )}
      </section>

      {notRun.length > 0 && (
        <section aria-labelledby="notrun-h">
          <div className="bay-head">
            <h3 id="notrun-h">Not run</h3>
            <span className="ind font-normal text-console-2">{notRun.length}</span>
            <Link to="/settings" className="ml-auto text-xs font-normal text-scope underline">
              Add API keys
            </Link>
          </div>
          <ul className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {notRun.map((p) => (
              <li key={p.name} className="strip-empty">
                <span className="grid place-content-center text-xs font-semibold text-console-3">{categoryOf(p.category).code}</span>
                <span className="min-w-0 border-l border-dashed border-rail px-3 py-2 text-sm">
                  <span className="block truncate text-console">{p.label}</span>
                  <span className="ind block truncate text-xs">Needs {p.key_fields.map((k) => k.toUpperCase()).join(' + ')}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

/** The first three fields worth printing on the face of a strip. */
function fieldsOf(summary: Record<string, unknown> | undefined) {
  return Object.entries(summary ?? {})
    .filter(([, v]) => {
      if (v === null || v === undefined || v === '') return false
      if (Array.isArray(v)) return v.length > 0
      return typeof v !== 'object'
    })
    .slice(0, 3)
}

function hostOf(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return ''
  }
}

function ResultStrip({
  result,
  open,
  onToggle,
  highlighted,
  onHover,
}: {
  result: PipelineResult
  open: boolean
  onToggle: () => void
  highlighted: boolean
  onHover: (n: string | null) => void
}) {
  const cat = categoryOf(result.category)
  const ok = result.status === 'ok'
  const fields = ok ? fieldsOf(result.summary) : []
  const source = hostOf(result.source_url ?? result.homepage ?? '')

  return (
    <li className="strip-land" onMouseEnter={() => onHover(result.name)} onMouseLeave={() => onHover(null)}>
      <Strip
        holder={cat.holder}
        code={cat.code}
        className={highlighted ? 'border-console-3' : ''}
        bodyClassName=""
      >
        <button
          onClick={onToggle}
          disabled={!ok}
          aria-expanded={ok ? open : undefined}
          className="grid w-full grid-cols-[minmax(0,1fr)_auto] text-left @2xl:grid-cols-[12rem_minmax(0,1fr)_auto]"
        >
          <span className="strip-cell">
            <span
              className={`block truncate font-semibold ${ok ? '' : 'line-through decoration-grease-red decoration-2'}`}
            >
              {result.label}
            </span>
            <span className="block truncate text-xs text-ink-2">{source || cat.label}</span>
          </span>

          <span className="col-span-2 col-start-1 row-start-2 flex min-w-0 border-t border-paper-rule @2xl:col-span-1 @2xl:col-start-auto @2xl:row-start-auto @2xl:border-t-0 @2xl:border-l">
            {ok ? (
              fields.map(([k, v], i) => (
                <span key={k} className={`strip-cell min-w-0 flex-1 basis-0 ${i === 1 ? 'hidden @lg:block' : ''} ${i === 2 ? 'hidden @4xl:block' : ''}`}>
                  <span className="strip-label">{humanKey(k)}</span>
                  <span className={`block truncate text-sm ${typeof v === 'number' || Array.isArray(v) ? 'ind' : ''}`}>
                    {brief(v)}
                  </span>
                </span>
              ))
            ) : (
              <span className="strip-cell min-w-0 flex-1">
                <span className="strip-label">{result.status === 'skipped' ? 'Nothing to check' : 'Unable to answer'}</span>
                <span className="block truncate text-sm text-grease-red">{result.error}</span>
              </span>
            )}
          </span>

          <span className="col-start-2 row-start-1 flex items-center gap-2 border-l border-paper-rule px-3 @2xl:col-start-auto @2xl:row-start-auto">
            <span className="ind w-16 text-right text-sm">{result.cached ? 'cached' : ms(result.took_ms)}</span>
            {ok ? <GreaseTick /> : <GreaseCross />}
            <ChevronDown
              className={`size-4 text-ink-2 transition-transform duration-200 ${open ? 'rotate-180' : ''} ${ok ? '' : 'invisible'}`}
              aria-hidden
            />
          </span>
        </button>
      </Strip>
      {open && ok && <StripBack result={result} />}
    </li>
  )
}

/** The back of the strip: every field the source returned. */
function StripBack({ result }: { result: PipelineResult }) {
  const [raw, setRaw] = useState(false)
  return (
    <div className="paper ml-[3.5rem] rounded-b-lg border border-t-0 border-rail px-5 py-4">
      <KeyValueGrid data={result.summary ?? {}} />
      <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
        {result.source_url && (
          <a href={result.source_url} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 text-link underline">
            <ExternalLink className="size-3.5" aria-hidden /> Open at the source
          </a>
        )}
        {result.data != null && (
          <button onClick={() => setRaw(!raw)} className="text-link underline">
            {raw ? 'Hide the raw response' : 'Show the raw response'}
          </button>
        )}
        {(result.pivots?.length ?? 0) > 0 && (
          <span className="text-ink-2">
            Found {result.pivots!.length} pivot{result.pivots!.length === 1 ? '' : 's'}, listed on the right
          </span>
        )}
      </div>
      {raw && (
        <div className="mt-3">
          <JsonBlock data={result.data} />
        </div>
      )}
    </div>
  )
}

/* --------------------------------------------------------------------------------- */

function Pivots({
  state,
  onPivot,
  canPivot,
  authorized,
}: {
  state: SweepState
  onPivot: (p: Pivot) => void
  canPivot: boolean
  authorized: boolean
}) {
  const [showAll, setShowAll] = useState<Record<string, boolean>>({})
  const t = state.target!
  const groups = useMemo(() => {
    const seen = new Map<string, Pivot & { from: string[] }>()
    for (const r of Object.values(state.results))
      for (const p of r.pivots ?? []) {
        if (p.value === t.value || p.value === t.host) continue
        const k = `${p.type}:${p.value}`
        const e = seen.get(k)
        if (e) {
          if (!e.from.includes(r.label)) e.from.push(r.label)
        } else seen.set(k, { ...p, from: [r.label] })
      }
    const m = new Map<IndicatorType, (Pivot & { from: string[] })[]>()
    for (const p of seen.values()) m.set(p.type, [...(m.get(p.type) ?? []), p])
    return [...m.entries()]
  }, [state.results, t.value, t.host])
  const total = groups.reduce((n, [, l]) => n + l.length, 0)

  return (
    <section aria-labelledby="pivots-h">
      <div className="bay-head">
        <h2 id="pivots-h">Pivots</h2>
        <span className="ind font-normal text-console-2">{total}</span>
      </div>
      {total === 0 ? (
        <p className="mt-3 text-sm text-console-2">
          Hosts, addresses and networks found in the answers collect here. Select one to sweep it next.
        </p>
      ) : (
        <>
          {!authorized && <p className="mt-3 text-sm text-console-2">Tick the authorization box to sweep a pivot.</p>}
          {groups.map(([type, list]) => {
            const shown = showAll[type] ? list : list.slice(0, 8)
            return (
              <div key={type} className="mt-4">
                <h3 className="text-sm text-console-2">
                  {TYPE_LABEL[type]} <span className="ind">({list.length})</span>
                </h3>
                <ul className="mt-1 space-y-1">
                  {shown.map((p) => (
                    <li key={p.value}>
                      <button
                        disabled={!canPivot}
                        onClick={() => onPivot(p)}
                        title={`Found by ${p.from.join(', ')}${p.label ? ` (${p.label})` : ''}`}
                        className="group grid w-full grid-cols-[2.5rem_minmax(0,1fr)] items-center overflow-hidden rounded-md border border-white/[0.06] bg-white/[0.03] text-left text-sm enabled:hover:border-scope/40 enabled:hover:bg-scope/10 disabled:cursor-not-allowed"
                      >
                        <span className="self-stretch border-r border-white/[0.06] py-0.5 text-center text-2xs font-semibold leading-5 text-console-2 group-enabled:group-hover:text-scope">
                          {PIVOT_CODE[type]}
                        </span>
                        <span className="ind truncate px-2.5 py-1 text-console">{p.value}</span>
                      </button>
                    </li>
                  ))}
                </ul>
                {list.length > 8 && (
                  <button
                    className="mt-1.5 text-sm text-scope underline"
                    onClick={() => setShowAll((s) => ({ ...s, [type]: !s[type] }))}
                  >
                    {showAll[type] ? 'Show fewer' : `Show all ${list.length}`}
                  </button>
                )}
              </div>
            )
          })}
        </>
      )}
    </section>
  )
}

function OtherTools({ target }: { target: Target }) {
  const links = useQuery({
    queryKey: ['quick-links'],
    queryFn: () => api.get<Record<string, { name: string; template: string }[]>>('/api/tools/quick-links'),
    staleTime: Infinity,
  })
  const list = links.data?.[target.type] ?? []
  if (!list.length) return null
  const v = encodeURIComponent(target.value)
  const n = target.value.replace(/^AS/i, '')
  return (
    <section aria-labelledby="ql-h">
      <div className="bay-head">
        <h2 id="ql-h">Open in other tools</h2>
      </div>
      <ul className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
        {list.map((l) => (
          <li key={l.name}>
            <a
              href={l.template.replace('{v}', v).replace('{n}', n)}
              target="_blank"
              rel="noreferrer"
              className="text-scope underline decoration-scope-deep hover:decoration-scope"
            >
              {l.name}
            </a>
          </li>
        ))}
      </ul>
    </section>
  )
}
