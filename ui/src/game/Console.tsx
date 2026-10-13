import { useRef, useState, type RefObject } from 'react'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { ActionButton, type Send } from './ItemRow'
import type { LogLine, Snapshot } from './types'

// Rewards and dangers get a coloured bar, like console notices.
const lineStyles: Record<string, string> = {
  command: 'mt-4 text-muted-foreground',
  reward: 'border-l-2 border-gold pl-3 text-gold',
  danger: 'border-l-2 border-destructive pl-3 text-destructive',
  notice: 'text-muted-foreground italic',
  story: 'text-story',
  combat: 'text-combat',
}

interface Props {
  data: Snapshot
  log: LogLine[]
  send: Send
  logRef: RefObject<HTMLDivElement | null>
  commandRef: RefObject<HTMLInputElement | null>
}

export function Console({ data, log, send, logRef, commandRef }: Props) {
  const p = data.player!
  const [command, setCommand] = useState('')
  const history = useRef<string[]>([])
  const historyIndex = useRef(0)

  const skills = (data.player_skills ?? [])
    .filter((s) => s.unlocked)
    .map((s) => ({ ...s, remaining: Math.max(0, Math.ceil((p.cooldowns[s.id] || 0) - data.time)) }))

  const status = p.combat
    ? `in combat · next ${p.combat.turn} pulse in ${Math.max(0, Math.ceil(p.combat.next_at - data.time))}s`
    : 'exploring'

  function submit(event: React.FormEvent) {
    event.preventDefault()
    const value = command.trim()
    if (!value) return
    history.current.push(value)
    historyIndex.current = history.current.length
    setCommand('')
    send(value)
  }

  function browseHistory(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return
    event.preventDefault()
    const step = event.key === 'ArrowUp' ? -1 : 1
    historyIndex.current = Math.max(0, Math.min(history.current.length, historyIndex.current + step))
    setCommand(history.current[historyIndex.current] || '')
  }

  return (
    <section aria-label="Adventure console" className="min-w-0">
      <div
        ref={logRef}
        tabIndex={0}
        role="log"
        aria-label="Adventure log"
        aria-live="polite"
        aria-relevant="additions"
        className="h-[min(440px,55vh)] overflow-y-auto py-2 pr-2 [scrollbar-color:#3a3a3a_transparent] focus-visible:outline-1 focus-visible:outline-border"
      >
        {log.map((line) => (
          <p key={line.id} className={cn('mb-2 leading-relaxed break-words whitespace-pre-line', lineStyles[line.kind ?? ''])}>
            {line.kind === 'command' ? `❯ ${line.text.replace(/^>\s*/, '')}` : line.text}
          </p>
        ))}
      </div>

      <form onSubmit={submit} className="mt-2 flex items-center gap-2 border-y border-border py-1.5 focus-within:border-muted-foreground">
        <label htmlFor="command" className="text-foreground select-none">❯</label>
        <Input
          id="command"
          ref={commandRef}
          value={command}
          onChange={(event) => setCommand(event.target.value)}
          onKeyDown={browseHistory}
          placeholder='Try "look north" or "help"'
          aria-label="Game command"
          maxLength={160}
          autoComplete="off"
          spellCheck={false}
          className="h-8 flex-1 rounded-none border-0 bg-transparent px-0 shadow-none focus-visible:ring-0 dark:bg-transparent"
        />
      </form>

      <div className="mt-1.5 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-sm">
        <span className={p.combat ? 'text-destructive' : 'text-gold'}>⏵⏵ {status}</span>
        <span className="text-muted-foreground">↑↓ for history · enter to send</span>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <ActionButton send={send} command="attack">attack</ActionButton>
        {skills.map((s) => (
          <ActionButton
            key={s.id}
            send={send}
            command={`cast ${s.id}`}
            title={s.description || ''}
            disabled={
              s.remaining > 0 ||
              (s.effect === 'damage' && !s.initiates && !p.combat) ||
              (s.effect === 'knockout' && !data.enemy) ||
              (s.effect === 'heal' && p.hp >= p.max_hp)
            }
          >
            {s.name.toLowerCase()}
            {s.remaining > 0 && ` ${s.remaining}s`}
          </ActionButton>
        ))}
        <ActionButton send={send} command="quaff potion">quaff potion</ActionButton>
        <ActionButton send={send} command="flee">flee</ActionButton>
        {data.room.rest && <ActionButton send={send} command="rest">rest</ActionButton>}
        <ActionButton send={send} command="help">help</ActionButton>
      </div>
    </section>
  )
}
