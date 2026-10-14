import type { ReactNode } from 'react'

export function Masthead({ children }: { children?: ReactNode }) {
  return (
    <header className="flex flex-col items-start justify-between gap-2 border-b px-4 py-3 text-sm sm:flex-row sm:items-center sm:px-[3vw]">
      <a href="/" className="font-bold text-foreground no-underline">
        <span className="text-muted-foreground">~/</span>relic-<span className="text-primary">frontier</span> <span className="text-muted-foreground">v0.7.0</span>
      </a>
      <div className="flex flex-wrap items-center gap-4">{children}</div>
    </header>
  )
}

export function Eyebrow({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`text-sm font-bold text-primary ${className}`}>{children}</div>
}
