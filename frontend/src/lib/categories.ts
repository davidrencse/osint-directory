// Source categories as strip holders: a three-letter code, a holder colour and plain words.
export interface Category {
  id: string
  code: string
  label: string
  holder: string // CSS colour value
  checks: string
}

export const CATEGORIES: Category[] = [
  {
    id: 'registration',
    code: 'REG',
    label: 'Registration',
    holder: 'var(--color-h-reg)',
    checks: 'Who holds the domain, network or ASN, and since when',
  },
  {
    id: 'dns',
    code: 'DNS',
    label: 'DNS and certificates',
    holder: 'var(--color-h-dns)',
    checks: 'Records, mail security, zone transfers and every certificate ever issued',
  },
  {
    id: 'network',
    code: 'NET',
    label: 'Routing and location',
    holder: 'var(--color-h-net)',
    checks: 'Which network announces it, where it sits, who handles abuse',
  },
  {
    id: 'web',
    code: 'WEB',
    label: 'Web surface',
    holder: 'var(--color-h-web)',
    checks: 'The live certificate, server fingerprint and security headers',
  },
  {
    id: 'history',
    code: 'HIS',
    label: 'History',
    holder: 'var(--color-h-his)',
    checks: 'What the Wayback Machine captured, and when',
  },
  {
    id: 'threat-intel',
    code: 'INT',
    label: 'Threat intelligence',
    holder: 'var(--color-h-int)',
    checks: 'Reputation, scanning activity, open ports and malware reports',
  },
]

export const CATEGORY_BY_ID: Record<string, Category> = Object.fromEntries(CATEGORIES.map((c) => [c.id, c]))

export function categoryOf(id: string): Category {
  return (
    CATEGORY_BY_ID[id] ?? { id, code: id.slice(0, 3).toUpperCase(), label: id, holder: 'var(--color-h-none)', checks: '' }
  )
}
