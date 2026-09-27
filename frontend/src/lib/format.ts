// Turning API field names and values into words people read.

const ACRONYMS: Record<string, string> = {
  asns: 'ASNs',
  cidrs: 'CIDRs',
  asn: 'ASN',
  mx: 'MX',
  ns: 'NS',
  txt: 'TXT',
  caa: 'CAA',
  spf: 'SPF',
  dmarc: 'DMARC',
  ptr: 'PTR',
  cn: 'CN',
  san: 'SAN',
  os: 'OS',
  url: 'URL',
  ip: 'IP',
  ips: 'IPs',
  tls: 'TLS',
  dnssec: 'DNSSEC',
  v4: 'v4',
  '90d': '(90 days)',
}

export function humanKey(key: string) {
  if (/^[A-Z0-9]+$/.test(key)) return key
  const words = key
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .split(/[_\s]+/)
    .map((w) => ACRONYMS[w.toLowerCase()] ?? w.toLowerCase())
  const s = words.join(' ')
  return s.charAt(0).toUpperCase() + s.slice(1)
}

/** Compact one-line rendering for strip cells. */
export function brief(v: unknown): string {
  if (v === null || v === undefined || v === '') return 'none'
  if (typeof v === 'boolean') return v ? 'Yes' : 'No'
  if (typeof v === 'number') return v.toLocaleString()
  if (Array.isArray(v)) {
    if (!v.length) return 'none'
    const head = v.slice(0, 2).map(brief).join(', ')
    return v.length > 2 ? `${head} +${v.length - 2}` : head
  }
  if (typeof v === 'object') return `${Object.keys(v as object).length} fields`
  return String(v)
}

export function ms(n: number) {
  return n < 1000 ? `${n} ms` : `${(n / 1000).toFixed(n < 10000 ? 1 : 0)} s`
}
