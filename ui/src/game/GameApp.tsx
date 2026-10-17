import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Masthead } from '@/components/Masthead'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { Callout, TerminalBox } from '@/components/Terminal'
import { Button } from '@/components/ui/button'
import { Console } from './Console'
import { HeaderPanel } from './HeaderPanel'
import { SidePanels } from './SidePanels'
import { Welcome } from './Welcome'
import { PlayerMap } from './PlayerMap'
import type { LogLine, Snapshot } from './types'

const POLL_MS = 750
const LOG_LIMIT = 180

export function GameApp() {
  const [data, setData] = useState<Snapshot | null>(null)
  const [connected, setConnected] = useState<boolean | null>(null)
  const [error, setError] = useState('')
  const [characterError, setCharacterError] = useState('')
  const [mapOpen, setMapOpen] = useState(false)
  const [quit, setQuit] = useState<Snapshot['quit']>()
  const hasQuit = useRef(false)
  const [log, setLog] = useState<LogLine[]>([])
  const lastLog = useRef(0)
  const lastPlayer = useRef<string | null>(null)
  // One request at a time: polling and commands share the server's game lock.
  const busy = useRef(false)
  const logRef = useRef<HTMLDivElement>(null)
  const stickToBottom = useRef(true)
  const commandRef = useRef<HTMLInputElement>(null)
  const focusAfterCreate = useRef(false)

  const apply = useCallback((next: Snapshot) => {
    hasQuit.current = !!next.quit
    setQuit(next.quit)
    const identity = next.player?.id ?? null
    if (identity !== lastPlayer.current) {
      lastLog.current = 0
      lastPlayer.current = identity
      setLog([])
      setMapOpen(false)
      setCharacterError('')
    }
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
      if (hasQuit.current) return
      busy.current = true
      try {
        const next = await api<Snapshot>('/api/command', { command })
        apply(next)
        if (next.ui_action === 'show_map') setMapOpen(true)
        else commandRef.current?.focus({ preventScroll: true })
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
      while (busy.current) await new Promise((resolve) => setTimeout(resolve, 60))
      busy.current = true
      setCharacterError('')
      try {
        apply(await api<Snapshot>('/api/create', { name, race, class: cls }))
        focusAfterCreate.current = true
      } catch (e) {
        setCharacterError((e as Error).message)
      } finally {
        busy.current = false
      }
    },
    [apply],
  )

  const chooseCharacter = useCallback(async (path: string, body?: unknown) => {
    while (busy.current) await new Promise((resolve) => setTimeout(resolve, 60))
    busy.current = true
    setCharacterError('')
    try {
      apply(await api<Snapshot>(path, body))
      focusAfterCreate.current = true
    } catch (e) {
      setCharacterError((e as Error).message)
    } finally {
      busy.current = false
    }
  }, [apply])

  useEffect(() => {
    let alive = true
    let timer: ReturnType<typeof setTimeout>
    async function poll() {
      if (!busy.current && !hasQuit.current) {
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
    <div className={cn('min-h-screen', data?.player && 'game-shell')}>
      <Masthead>
        <span role="status" className={cn(connected === false ? 'text-destructive' : 'text-muted-foreground')}>
          {quit ? '✓ progress saved' : connected === null ? '○ connecting…' : connected ? '● connected · autosaving' : '✕ disconnected · reopen launcher'}
        </span>
        {!quit && (!data?.multiplayer || data.session?.owner) && <a href="/admin" target="_blank" rel="noopener" className="text-primary underline-offset-4 hover:underline">
          owner editor ↗
        </a>}
        {data?.multiplayer && data.player && <button type="button" className="text-primary hover:underline" onClick={() => chooseCharacter('/api/leave', {})}>switch character</button>}
        {!quit && data && (data.player || data.session?.owner) && <button type="button" className="text-primary hover:underline" onClick={() => chooseCharacter('/api/quit', {})}>save &amp; quit</button>}
      </Masthead>
      <main className="game-main mx-auto w-full max-w-[1760px] px-4 pt-4 pb-3 sm:px-6">
        {quit && <div className="mx-auto max-w-2xl py-8">
          <TerminalBox title="Progress saved">
            <p role="status" className="text-story">{quit.server_stopped ? 'The game has stopped. You can close this tab.' : 'You have left the game. Your character is saved and out of play. You can close this tab.'}</p>
            <p className="mt-3 text-sm text-muted-foreground">{quit.server_stopped ? 'Open your game launcher when you want to play again.' : 'The shared game is still running. Other players can keep playing.'}</p>
            {!quit.server_stopped && <div className="mt-4 flex flex-wrap gap-2">
              <Button onClick={() => chooseCharacter('/api/state')}>Return to character selection</Button>
              {data?.session?.owner && <Button variant="outline" onClick={() => chooseCharacter('/api/quit', {})}>Stop game when everyone has left</Button>}
            </div>}
          </TerminalBox>
        </div>}
        {!quit && data && !data.player && <Welcome choices={data.creation} recallRules={data.recall_rules} multiplayer={data.multiplayer} characters={data.characters} onCreate={create} onJoin={(player_id) => chooseCharacter('/api/join', {player_id})} />}
        {data?.player && (
          <div className="game-layout grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_clamp(320px,25%,400px)]">
            <div className="game-play grid min-w-0 gap-3">
              <div key={data.room.code ?? data.room.name} className="game-scene" role="region" aria-label="Character and current room" tabIndex={0}>
                <HeaderPanel data={data} send={send} />
              </div>
              <Console key={data.player.id} data={data} log={log} send={send} logRef={logRef} commandRef={commandRef} />
            </div>
            <aside className="game-sidebar min-w-0" aria-label="Equipment, inventory and skills" tabIndex={0}>
              <SidePanels data={data} send={send} />
            </aside>
          </div>
        )}
        {(error || characterError) && (
          <Callout tone="border-destructive" className="mt-4">
            <p role="alert" className="text-destructive">{error || characterError}</p>
          </Callout>
        )}
      </main>
      {mapOpen && data?.player && data.exploration_map && <PlayerMap map={data.exploration_map} inCombat={!!data.player.combat} onClose={() => setMapOpen(false)} returnFocus={() => commandRef.current?.focus({ preventScroll: true })} />}
      <footer className="game-footer px-4 pt-1 pb-3 text-sm text-muted-foreground sm:text-center">
        {quit ? 'See you at the fountain.' : 'Progress saves automatically. SAVE keeps you playing; QUIT saves and leaves. Combat continues if you only close the browser.'}
      </footer>
    </div>
  )
}
