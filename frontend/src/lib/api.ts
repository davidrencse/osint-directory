export type IndicatorType = 'domain' | 'ip' | 'cidr' | 'asn' | 'url' | 'hash'

export interface Target {
  raw: string
  type: IndicatorType
  value: string
  host: string | null
  hash_algo: string | null
  in_scope?: boolean
}

export interface PipelineInfo {
  name: string
  label: string
  category: string
  accepts: IndicatorType[]
  requires_key: boolean
  optional_key: boolean
  key_fields: string[]
  enabled: boolean
  homepage: string
  status?: PipelineStatus
  error?: string
}

export type PipelineStatus = 'pending' | 'ok' | 'error' | 'skipped'

export interface Pivot {
  type: IndicatorType
  value: string
  label: string
}

export interface PipelineResult {
  name: string
  label: string
  category: string
  homepage: string
  status: PipelineStatus
  summary?: Record<string, unknown>
  data?: unknown
  source_url?: string | null
  pivots?: Pivot[]
  error?: string
  took_ms: number
  cached: boolean
}

export interface LayerInfo {
  id: string
  label: string
  group: string
  refresh_s: number
  uses_bbox: boolean
  description: string
  enabled: boolean
  key_field: string | null
}

export interface FeatureCollection {
  type: 'FeatureCollection'
  features: GeoJSON.Feature[]
  meta: {
    source?: string
    source_url?: string
    count?: number
    fetched_at?: string
    disabled?: boolean
    reason?: string
  }
}

export interface MetadataResult {
  filename: string
  size: number
  detected_type: string
  hashes: Record<'md5' | 'sha1' | 'sha256', string>
  extractor: 'exiftool' | 'builtin'
  groups: Record<string, Record<string, unknown>>
  gps: { lat: number; lon: number; alt: number | null } | null
  highlights: { group: string; tag: string; value: string; reason: string }[]
  strippable: boolean
  errors: string[]
}

export interface Tool {
  id: number
  name: string
  url: string
  category: string
  path: string[]
  description: string
  pricing: string
  input?: string | null
  output?: string | null
  opsec?: string | null
  opsec_note?: string | null
  local_install?: boolean
  google_dork?: boolean
  registration?: boolean
  manual_url_edit?: boolean
  api?: boolean
  deprecated?: boolean
  sources: string[]
  also_in?: string[]
}

export interface Catalog {
  generated_at: string
  sources: Record<string, { url: string; count: number; license?: string }>
  tools: Tool[]
}

export interface KeyStatus {
  field: string
  env: string
  set: boolean
  used_by: string[]
  signup: string
}

export interface AuditRow {
  ts: number
  kind: string
  target: string
  detail: Record<string, unknown>
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  get: <T>(path: string, init?: RequestInit) => fetch(path, init).then((r) => parse<T>(r)),
  send: <T>(path: string, method: string, body?: unknown) =>
    fetch(path, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    }).then((r) => parse<T>(r)),
  upload: (path: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return fetch(path, { method: 'POST', body: form })
  },
  parse,
}

export const TYPE_LABEL: Record<IndicatorType, string> = {
  domain: 'Domain',
  ip: 'IP address',
  cidr: 'Network (CIDR)',
  asn: 'Autonomous system',
  url: 'URL',
  hash: 'File hash',
}
