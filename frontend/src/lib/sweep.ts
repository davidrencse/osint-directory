import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError, type PipelineInfo, type PipelineResult, type Target } from './api'

export interface SweepState {
  target: Target | null
  plan: PipelineInfo[]
  results: Record<string, PipelineResult>
  startedAt: number | null
  finishedAt: number | null
  running: boolean
  error: string | null
}

const EMPTY: SweepState = {
  target: null,
  plan: [],
  results: {},
  startedAt: null,
  finishedAt: null,
  running: false,
  error: null,
}

/** Parse a text/event-stream body. fetch (not EventSource) so HTTP errors keep their message. */
async function* readEvents(body: ReadableStream<Uint8Array>) {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      let event = 'message'
      let data = ''
      for (const line of block.split('\n')) {
        if (line.startsWith('event: ')) event = line.slice(7)
        else if (line.startsWith('data: ')) data += line.slice(6)
      }
      if (data) yield { event, data: JSON.parse(data) }
    }
  }
}

export function useSweep() {
  const [state, setState] = useState<SweepState>(EMPTY)
  const abortRef = useRef<AbortController | null>(null)

  // Leaving the page must close the stream, or the backend keeps querying every source.
  useEffect(() => () => abortRef.current?.abort(), [])

  const start = useCallback(async (target: string, opts: { fresh?: boolean; pipelines?: string[] } = {}) => {
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setState({ ...EMPTY, running: true, startedAt: Date.now() })

    const params = new URLSearchParams({ target, authorized: 'true' })
    if (opts.fresh) params.set('fresh', 'true')
    if (opts.pipelines?.length) params.set('pipelines', opts.pipelines.join(','))

    try {
      const res = await fetch(`/api/recon/stream?${params}`, { signal: ctrl.signal })
      if (!res.ok || !res.body) await api.parse(res)
      for await (const ev of readEvents(res.body!)) {
        if (ev.event === 'plan') {
          setState((s) => ({ ...s, target: ev.data.target, plan: ev.data.pipelines }))
        } else if (ev.event === 'result') {
          const r = ev.data as PipelineResult
          setState((s) => ({ ...s, results: { ...s.results, [r.name]: r } }))
        } else if (ev.event === 'done') {
          setState((s) => ({ ...s, running: false, finishedAt: Date.now() }))
        }
      }
      setState((s) => (s.running ? { ...s, running: false, finishedAt: Date.now() } : s))
    } catch (err) {
      if (ctrl.signal.aborted) return
      const message = err instanceof ApiError ? err.message : `Connection to the backend failed: ${String(err)}`
      setState((s) => ({ ...s, running: false, finishedAt: Date.now(), error: message }))
    }
  }, [])

  const stop = useCallback(() => {
    abortRef.current?.abort()
    setState((s) => ({ ...s, running: false, finishedAt: Date.now() }))
  }, [])

  return { state, start, stop }
}
