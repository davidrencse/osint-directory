import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Strip } from '../components/Strip'
import { api, type AuditRow, type KeyStatus } from '../lib/api'

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-[1100px] px-4 pt-4 pb-12 md:px-6 md:pt-5">
      <h1 className="page-title text-2xl font-semibold">Settings</h1>
      <div className="mt-8 space-y-10">
        <Keys />
        <Scope />
        <Cache />
        <Audit />
      </div>
    </div>
  )
}

function Keys() {
  const keys = useQuery({ queryKey: ['keys'], queryFn: () => api.get<KeyStatus[]>('/api/settings/keys') })
  const set = keys.data?.filter((k) => k.set) ?? []
  const missing = keys.data?.filter((k) => !k.set) ?? []
  return (
    <section aria-labelledby="keys-h">
      <div className="bay-head">
        <h2 id="keys-h">API keys</h2>
        {keys.data && (
          <span className="ind font-normal text-console-2">
            {set.length} of {keys.data.length} set
          </span>
        )}
      </div>
      <p className="mt-3 max-w-[70ch] text-sm text-console-2">
        Keys live in <code className="ind text-console">backend/.env</code> and never reach the browser. Add a line such
        as <code className="ind text-console">SHODAN_API_KEY=…</code> and restart the backend. Every key is optional,
        and the free tiers are enough.
      </p>
      {keys.isError && <p className="mt-3 text-sm text-alert">The backend isn't answering.</p>}
      <ul className="mt-3 space-y-1.5">
        {set.map((k) => (
          <li key={k.field}>
            <Strip holder="var(--color-h-dns)" code="KEY" bodyClassName="grid md:grid-cols-[17rem_minmax(0,1fr)_6rem]">
              <span className="strip-cell">
                <span className="ind block truncate font-semibold">{k.env}</span>
              </span>
              <span className="strip-cell text-sm">{k.used_by.join(', ')}</span>
              <span className="strip-cell text-sm font-semibold">Set</span>
            </Strip>
          </li>
        ))}
        {missing.map((k) => (
          <li key={k.field} className="strip-empty">
            <span className="grid place-content-center text-xs font-semibold text-console-3">KEY</span>
            <span className="grid min-w-0 border-l border-dashed border-rail md:grid-cols-[17rem_minmax(0,1fr)_6rem]">
              <span className="ind truncate px-3 py-2 text-console">{k.env}</span>
              <span className="px-3 py-2 text-sm">{k.used_by.join(', ')}</span>
              <a href={k.signup} target="_blank" rel="noreferrer" className="px-3 py-2 text-sm text-scope underline">
                Get a key
              </a>
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Scope() {
  const qc = useQueryClient()
  const scope = useQuery({ queryKey: ['scope'], queryFn: () => api.get<{ entries: string[] }>('/api/settings/scope') })
  // null = show what the server has; a string = the user's unsaved edit
  const [draft, setDraft] = useState<string | null>(null)
  const saved = scope.data?.entries.join('\n') ?? ''
  const text = draft ?? saved
  const save = useMutation({
    mutationFn: () => api.send<{ entries: string[] }>('/api/settings/scope', 'PUT', { entries: text.split(/[\n,]/) }),
    onSuccess: (d) => {
      qc.setQueryData(['scope'], d)
      setDraft(null)
      qc.invalidateQueries({ queryKey: ['classify'] })
    },
  })
  const dirty = draft !== null && draft.trim() !== saved
  const count = scope.data?.entries.length ?? 0
  return (
    <section aria-labelledby="scope-h">
      <div className="bay-head">
        <h2 id="scope-h">Engagement scope</h2>
        <span className="font-normal text-console-2">{count ? `${count} entries` : 'Not restricted'}</span>
      </div>
      <p className="mt-3 max-w-[70ch] text-sm text-console-2">
        List the domains, networks and ASNs you're authorized to test, one per line. While the list has entries, sweeps
        against anything outside it are refused. A domain includes its subdomains.
      </p>
      <textarea
        value={text}
        onChange={(e) => setDraft(e.target.value)}
        rows={6}
        spellCheck={false}
        placeholder={'example.com\n203.0.113.0/24\nAS64500'}
        aria-label="Scope allowlist"
        className="field ind mt-4 w-full max-w-xl p-3 text-sm"
      />
      <div className="mt-3 flex items-center gap-4">
        <button onClick={() => save.mutate()} disabled={!dirty || save.isPending} className="btn-primary px-4 py-1.5 text-sm">
          Save scope
        </button>
        <span className="text-sm text-console-2" aria-live="polite">
          {save.isError
            ? (save.error as Error).message
            : save.isSuccess && !dirty
              ? `Saved. ${save.data.entries.length ? `${save.data.entries.length} entries in scope.` : 'Any target is allowed.'}`
              : dirty
                ? 'Unsaved changes'
                : ''}
        </span>
      </div>
    </section>
  )
}

function Cache() {
  const clear = useMutation({ mutationFn: () => api.send<{ deleted: number }>('/api/settings/cache', 'DELETE') })
  return (
    <section aria-labelledby="cache-h">
      <div className="bay-head">
        <h2 id="cache-h">Answer cache</h2>
      </div>
      <p className="mt-3 max-w-[70ch] text-sm text-console-2">
        Answers are kept for an hour so repeat sweeps don't spend your API quota. Clear it to make every source answer
        afresh.
      </p>
      <div className="mt-4 flex items-center gap-4">
        <button onClick={() => clear.mutate()} className="rounded-md border border-rail px-5 py-2 hover:border-alert hover:text-alert">
          Clear the cache
        </button>
        {clear.isSuccess && <span className="text-sm text-console-2">Cleared {clear.data.deleted} cached answers.</span>}
      </div>
    </section>
  )
}

function Audit() {
  const audit = useQuery({
    queryKey: ['audit'],
    queryFn: () => api.get<AuditRow[]>('/api/settings/audit?limit=100'),
    refetchInterval: 15000,
  })
  const kindLabel: Record<string, string> = { recon: 'Sweep', metadata: 'File read', scope: 'Scope saved' }
  return (
    <section aria-labelledby="audit-h">
      <div className="bay-head">
        <h2 id="audit-h">Activity log</h2>
        {audit.data && <span className="ind font-normal text-console-2">{audit.data.length}</span>}
      </div>
      <p className="mt-3 max-w-[70ch] text-sm text-console-2">
        Every sweep, file read and scope change, newest first, for your engagement notes.
      </p>
      {audit.data?.length === 0 && <p className="mt-3 text-sm text-console-2">Nothing yet. Run a sweep and it appears here.</p>}
      {!!audit.data?.length && (
        <table className="mt-4 w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-console-2">
              <th className="py-1.5 pr-4 font-normal">When</th>
              <th className="py-1.5 pr-4 font-normal">What</th>
              <th className="py-1.5 font-normal">Target</th>
            </tr>
          </thead>
          <tbody>
            {audit.data.map((a, i) => (
              <tr key={i} className="border-t border-rail/60">
                <td className="ind py-1.5 pr-4 whitespace-nowrap text-console-2">{new Date(a.ts * 1000).toLocaleString()}</td>
                <td className="py-1.5 pr-4">{kindLabel[a.kind] ?? a.kind}</td>
                <td className="ind py-1.5 break-all">{a.target}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
