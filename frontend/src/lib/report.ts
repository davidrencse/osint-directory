import type { SweepState } from './sweep'

/** Save a blob as a file. The URL is revoked later: revoking right after click() can cancel the
 *  download in Firefox and Safari, which start it asynchronously. */
export function saveBlob(name: string, blob: Blob) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 30_000)
}

function download(name: string, content: string, type: string) {
  saveBlob(name, new Blob([content], { type }))
}

function fileStem(state: SweepState) {
  const v = (state.target?.value ?? 'target').replace(/[^a-z0-9.-]+/gi, '_').slice(0, 60)
  return `recon_${v}_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}`
}

export function exportJson(state: SweepState) {
  const report = {
    generated_at: new Date().toISOString(),
    target: state.target,
    pipelines: state.plan.map((p) => state.results[p.name] ?? { name: p.name, status: p.status, error: p.error }),
  }
  download(`${fileStem(state)}.json`, JSON.stringify(report, null, 2), 'application/json')
}

function mdValue(v: unknown): string {
  if (v === null || v === undefined || v === '') return 'none'
  if (Array.isArray(v)) return v.length ? v.map(mdValue).join(', ') : 'none'
  if (typeof v === 'object') return Object.entries(v as object).map(([k, x]) => `${k}: ${mdValue(x)}`).join('; ')
  return String(v).replace(/\|/g, '\\|').replace(/\n/g, ' ')
}

export function exportMarkdown(state: SweepState) {
  const t = state.target
  const lines = [
    `# Recon report: ${t?.value ?? ''}`,
    '',
    `- Type: ${t?.type}`,
    `- Generated: ${new Date().toISOString()}`,
    '',
  ]
  for (const p of state.plan) {
    const r = state.results[p.name]
    lines.push(`## ${p.label}`, '')
    if (!r) {
      lines.push(`_${p.status === 'skipped' ? `Skipped: ${p.error ?? ''}` : 'No result'}_`, '')
      continue
    }
    if (r.status !== 'ok') {
      lines.push(`_${r.status}: ${r.error ?? ''}_`, '')
      continue
    }
    lines.push('| Field | Value |', '| --- | --- |')
    for (const [k, v] of Object.entries(r.summary ?? {})) lines.push(`| ${k} | ${mdValue(v)} |`)
    if (r.source_url) lines.push('', `Source: ${r.source_url}`)
    lines.push('')
  }
  download(`${fileStem(state)}.md`, lines.join('\n'), 'text/markdown')
}
