import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Masthead } from '@/components/Masthead'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { Callout } from '@/components/Terminal'
import { Console } from './Console'
import { HeaderPanel } from './HeaderPanel'
import { SidePanels } from './SidePanels'
import { Welcome } from './Welcome'
import type { LogLine, Snapshot } from './types'

const POLL_MS = 750
const LOG_LIMIT = 180

export function GameApp() {
  const [data, setData] = useState<Snapshot | null>(null)
  const [connected, setConnected] = useState<boolean | null>(null)
  const [error, setError] = useState('')
  const [log, setLog] = useState<LogLine[]>([])
  const lastLog = useRef(0)
  // One request at a time: polling and commands share the server's game lock.
  const busy = useRef(false)
  const logRef = useRef<HTMLDivElement>(null)
  const stickToBottom = useRef(true)
  const commandRef = useRef<HTMLInputElement>(null)
  const focusAfterCreate = useRef(false)

  const apply = useCallback((next: Snapshot) => {
    const el = logRef.current
    stickToBottom.current = !el || el.scrollHeight - el.scrollTop - el.clientHeight < 70
    const fresh = next.log.filter((line) => line.id > lastLog.current)
    if (fresh.length) {
      lastLog.current = fresh[fresh.length - 1].id
      setLog((previous) => [...previous, ...fresh].slice(-LOG_LIMIT))
    }
    setData(next)
    setConnected(true)
    setError('')
    document.title = next.title
  }, [])

  useLayoutEffect(() => {
    const el = logRef.current
    if (el && stickToBottom.current) el.scrollTop = el.scrollHeight
    // The command box only exists once the new character's game view has rendered.
    if (focusAfterCreate.current && commandRef.current) {
      focusAfterCreate.current = false
      commandRef.current.focus()
    }
  }, [log, data?.player != null])

  const send = useCallback(
    async (command: string) => {
      while (busy.current) await new Promise((resolve) => setTimeout(resolve, 60))
      busy.current = true
      try {
        apply(await api<Snapshot>('/api/command', { command }))
        commandRef.current?.focus({ preventScroll: true })
      } catch (e) {
        setError((e as Error).message)
        setConnected(false)
      } finally {
        busy.current = false
      }
    },
    [apply],
  )

  const create = useCallback(
    async (name: string, race: string, cls: string) => {
      if (busy.current) return
      busy.current = true
      try {
        apply(await api<Snapshot>('/api/create', { name, race, class: cls }))
        focusAfterCreate.current = true
      } catch (e) {
        setError((e as Error).message)
      } finally {
        busy.current = false
      }
    },
    [apply],
  )

  useEffect(() => {
    let alive = true
    let timer: ReturnType<typeof setTimeout>
    async function poll() {
      if (!busy.current) {
        busy.current = true
        try {
          apply(await api<Snapshot>('/api/state'))
        } catch {
          setConnected(false)
          setError('The game server is unavailable. Reopen Start_Game.cmd to reconnect.')
        } finally {
          busy.current = false
        }
      }
      if (alive) timer = setTimeout(poll, POLL_MS)
    }
    poll()
    return () => {
      alive = false
      clearTimeout(timer)
    }
  }, [apply])

  return (
    <div className="min-h-screen">
      <Masthead>
        <span role="status" className={cn(connected === false ? 'text-destructive' : 'text-muted-foreground')}>
          {connected === null ? '○ connecting…' : connected ? '● connected · autosaving' : '✕ disconnected · reopen launcher'}
        </span>
        <a href="/admin" target="_blank" rel="noopener" className="text-primary underline-offset-4 hover:underline">
          owner editor ↗
        </a>
      </Masthead>
      <main className="mx-auto max-w-[1400px] px-4 pt-6 pb-4 sm:px-[3vw]">
        {data && !data.player && <Welcome choices={data.creation} onCreate={create} />}
        {data?.player && (
          <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
            <div className="grid min-w-0 gap-4">
              <HeaderPanel data={data} send={send} />
              <Console data={data} log={log} send={send} logRef={logRef} commandRef={commandRef} />
            </div>
            <SidePanels data={data} send={send} />
          </div>
        )}
        {error && (
          <Callout tone="border-destructive" className="mt-4">
            <p role="alert" className="text-destructive">{error}</p>
          </Callout>
        )}
      </main>
      <footer className="px-[3vw] pt-2 pb-6 text-sm text-muted-foreground sm:text-center">
        Progress saves automatically. Combat continues while the game server is running.
      </footer>
    </div>
  )
}
