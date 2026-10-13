import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/** A console frame with its title set into the top border. Frames sit on the page background. */
export function TerminalBox({ title, children, className, muted }: { title?: ReactNode; children: ReactNode; className?: string; muted?: boolean }) {
  return (
    <section className={cn('relative min-w-0 rounded-md border px-4 pt-5 pb-4', muted ? 'border-border' : 'border-primary', className)}>
      {title && (
        <h2 className="absolute -top-2.5 left-3 bg-background px-1.5 text-sm leading-5 font-normal text-primary">{title}</h2>
      )}
      {children}
    </section>
  )
}

/** Accent-coloured section heading, as used inside frames. */
export function Heading({ children, className }: { children: ReactNode; className?: string }) {
  return <h3 className={cn('font-bold text-primary', className)}>{children}</h3>
}

/** A thin rule that separates sections inside a frame. */
export function Rule({ className }: { className?: string }) {
  return <hr className={cn('my-3 border-t border-primary/60', className)} />
}

/** Text-drawn progress meter: █ for filled cells, ░ for empty ones. */
export function TextMeter({ label, value, max, text, tone = 'text-primary', cells = 16 }: { label: string; value: number; max: number; text: ReactNode; tone?: string; cells?: number }) {
  const ratio = max > 0 ? Math.min(1, Math.max(0, value / max)) : 0
  // Any progress shows at least one cell, so a new level never looks empty.
  const filled = ratio > 0 ? Math.max(1, Math.round(ratio * cells)) : 0
  return (
    <div role="meter" aria-label={label} aria-valuenow={value} aria-valuemin={0} aria-valuemax={max} className="flex items-center gap-2 whitespace-nowrap">
      <span className="w-6 shrink-0 text-muted-foreground">{label}</span>
      <span aria-hidden className="leading-none tracking-[-0.05em]">
        <span className={tone}>{'█'.repeat(filled)}</span>
        <span className="text-muted-foreground/40">{'░'.repeat(cells - filled)}</span>
      </span>
      <span className="min-w-0 truncate">{text}</span>
    </div>
  )
}

/** A notice with a coloured bar down its left edge. */
export function Callout({ children, tone = 'border-primary', className }: { children: ReactNode; tone?: string; className?: string }) {
  return <div className={cn('border-l-2 pl-3', tone, className)}>{children}</div>
}
