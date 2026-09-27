import type { CSSProperties, ReactNode } from 'react'

/** A paper strip in a coloured plastic holder. The tab carries the holder's code. */
export function Strip({
  holder,
  code,
  sub,
  className = '',
  bodyClassName = '',
  children,
}: {
  holder: string
  code: ReactNode
  sub?: ReactNode
  className?: string
  bodyClassName?: string
  children: ReactNode
}) {
  return (
    <div className={`strip ${className}`} style={{ '--holder': holder } as CSSProperties}>
      <div className="strip-tab">
        <span>{code}</span>
        {sub}
      </div>
      <div className={`strip-body paper ${bodyClassName}`}>{children}</div>
    </div>
  )
}

/** Grease-pencil tick, drawn when a strip lands with an answer. */
export function GreaseTick({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={`size-5 shrink-0 ${className}`} aria-hidden>
      <path
        d="M3.5 12.5 L9.5 18 L20.5 5.5"
        fill="none"
        stroke="var(--color-grease-blue)"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="grease"
        style={{ '--len': 30 } as CSSProperties}
      />
    </svg>
  )
}

/** Grease-pencil cross, drawn when a source is unable to answer. */
export function GreaseCross({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={`size-5 shrink-0 ${className}`} aria-hidden>
      <path
        d="M5 5 L19 19 M19 5 L5 19"
        fill="none"
        stroke="var(--color-grease-red)"
        strokeWidth="3"
        strokeLinecap="round"
        className="grease"
        style={{ '--len': 42 } as CSSProperties}
      />
    </svg>
  )
}
