import { useLayoutEffect, useRef, useState } from 'react'
import { Dialog } from 'radix-ui'
import { Button } from '@/components/ui/button'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import type { ExplorationMap } from './types'

const OPPOSITE: Record<string, string> = { north: 'south', south: 'north', east: 'west', west: 'east', up: 'down', down: 'up' }
const floorName = (floor: number) => floor === 0 ? 'Ground level' : `Elevation ${floor}`

export function PlayerMap({ map, inCombat, onClose, returnFocus }: {
  map: ExplorationMap
  inCombat: boolean
  onClose: () => void
  returnFocus: () => void
}) {
  const current = map.rooms.find(r => r.id === map.current)
  const [floor, setFloor] = useState(current?.position[2] ?? 0)
  const [selected, setSelected] = useState(map.current)
  const [zoom, setZoom] = useState(1)
  const [centerRequest, setCenterRequest] = useState(0)
  const viewport = useRef<HTMLDivElement>(null)
  const floors = [...new Set(map.rooms.map(r => r.position[2]))].sort((a, b) => b - a)
  const activeFloor = floors.includes(floor) ? floor : current?.position[2] ?? floors[0]
  const rooms = map.rooms.filter(r => r.position[2] === activeFloor)
  const minX = Math.min(...rooms.map(r => r.position[0]))
  const minY = Math.min(...rooms.map(r => r.position[1]))
  const width = Math.max(260, (Math.max(...rooms.map(r => r.position[0])) - minX) * 240 + 260)
  const height = Math.max(160, (Math.max(...rooms.map(r => r.position[1])) - minY) * 140 + 160)
  const points = Object.fromEntries(rooms.map(r => [r.id, [(r.position[0] - minX) * 240 + 30, (r.position[1] - minY) * 140 + 35]]))
  const detail = map.rooms.find(r => r.id === selected) ?? current
  const byId = Object.fromEntries(map.rooms.map(r => [r.id, r]))
  const fit = () => {
    const el = viewport.current
    if (el) { setZoom(Math.min(1, (el.clientWidth - 16) / width, (el.clientHeight - 16) / height)); el.scrollTo(0, 0) }
  }
  useLayoutEffect(fit, [activeFloor])
  useLayoutEffect(() => {
    if (!centerRequest) return
    const el = viewport.current
    const point = points[selected]
    if (el && point) el.scrollTo({ left: (point[0] + 100) * zoom - el.clientWidth / 2, top: (point[1] + 43) * zoom - el.clientHeight / 2 })
  }, [centerRequest, activeFloor, zoom])

  const paths: React.ReactNode[] = []
  const drawn = new Set<string>()
  for (const room of rooms) {
    for (const [direction, dest] of Object.entries(room.exits)) {
      if (!points[dest]) continue
      const reciprocal = byId[dest].exits[OPPOSITE[direction]] === room.id
      const pair = [room.id, dest].sort().join('|')
      if (reciprocal && drawn.has(pair)) continue
      drawn.add(pair)
      const a = points[room.id], b = points[dest]
      const dx = b[0] - a[0], dy = b[1] - a[1]
      let [x1, y1, x2, y2] = [a[0] + 100, a[1] + 43, b[0] + 100, b[1] + 43]
      if (Math.abs(dx) >= Math.abs(dy)) { x1 += Math.sign(dx) * 103; x2 -= Math.sign(dx) * 103 }
      else { y1 += Math.sign(dy) * 46; y2 -= Math.sign(dy) * 46 }
      paths.push(<line key={`${room.id}-${direction}`} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#819daa" strokeWidth={2} markerEnd="url(#player-map-arrow)" markerStart={reciprocal ? 'url(#player-map-arrow)' : undefined} />)
    }
  }

  return <Dialog.Root open onOpenChange={open => { if (!open) onClose() }}>
    <Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-50 bg-black/75" />
      <Dialog.Content
        className="fixed top-1/2 left-1/2 z-50 flex h-[90dvh] max-h-[900px] w-[96vw] max-w-6xl -translate-x-1/2 -translate-y-1/2 flex-col gap-3 rounded-lg border border-primary bg-background p-3 text-foreground shadow-xl outline-none sm:p-5"
        onCloseAutoFocus={event => { event.preventDefault(); returnFocus() }}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <Dialog.Title className="text-lg font-semibold text-gold">Your explored map</Dialog.Title>
            <Dialog.Description className="text-xs text-muted-foreground sm:text-sm">Only places you have visited. No enemy locations. Scroll or swipe to pan.</Dialog.Description>
          </div>
          <Dialog.Close asChild><Button variant="outline" size="sm">Close map</Button></Dialog.Close>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <NativeSelect aria-label="Map elevation" value={activeFloor} onChange={event => setFloor(Number(event.target.value))}>
            {floors.map(value => <NativeSelectOption key={value} value={value}>{floorName(value)}</NativeSelectOption>)}
          </NativeSelect>
          <Button variant="outline" size="sm" aria-label="Zoom map out" disabled={zoom <= .02} onClick={() => setZoom(Math.max(.02, zoom / 1.25))}>−</Button>
          <span className="min-w-10 text-center" aria-label="Map zoom">{Math.round(zoom * 100)}%</span>
          <Button variant="outline" size="sm" aria-label="Zoom map in" disabled={zoom >= 2} onClick={() => setZoom(Math.min(2, zoom * 1.25))}>+</Button>
          <Button variant="outline" size="sm" onClick={fit}>Fit floor</Button>
          <Button variant="outline" size="sm" onClick={() => {
            if (current) { setFloor(current.position[2]); setSelected(current.id); setZoom(1); setCenterRequest(value => value + 1) }
          }}>Center on me</Button>
          <span className="text-xs text-muted-foreground">North ↑ · {map.rooms.length} visited · gold = you</span>
        </div>
        <div ref={viewport} tabIndex={0} role="region" aria-label="Explored map canvas" className="min-h-40 flex-1 overflow-auto overscroll-contain rounded border border-border bg-[#0a1016] focus-visible:ring-2 focus-visible:ring-primary">
          <svg role="img" aria-label="Visited rooms and connections" viewBox={`0 0 ${width} ${height}`} width={width * zoom} height={height * zoom} className="block max-w-none">
            <defs><marker id="player-map-arrow" viewBox="0 0 10 10" refX={9} refY={5} markerWidth={6} markerHeight={6} orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#819daa" /></marker></defs>
            {paths}
            {rooms.map(room => {
              const [x, y] = points[room.id]
              const here = room.id === map.current
              const picked = room.id === detail?.id
              const lines = room.name.match(/.{1,24}(?:\s|$)|.{1,24}/g) || [room.name]
              const stairs = Object.entries(room.exits).filter(([, dest]) => byId[dest].position[2] !== activeFloor).map(([direction]) => direction).join(' / ')
              return <g key={room.id} data-map-room={room.id} tabIndex={0} role="button" aria-label={`${room.name}${here ? ', your current location' : ''}`} aria-pressed={picked}
                className="cursor-pointer focus:outline-none [&:focus>rect]:stroke-white [&:focus>rect]:stroke-4"
                onClick={() => setSelected(room.id)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelected(room.id) } }}>
                <title>{room.name}{here ? ' — You are here' : ''}</title>
                <rect x={x} y={y} width={200} height={86} rx={8} fill={here ? '#352d19' : '#172631'} stroke={here ? '#e9bb72' : '#71dace'} strokeWidth={picked ? 4 : 2} />
                <text x={x + 10} y={y + 18} fill={here ? '#e9bb72' : '#71dace'} fontSize={11}>{here ? 'YOU ARE HERE' : 'VISITED'}{stairs ? ` · ${stairs}` : ''}</text>
                {lines.slice(0, 2).map((line, i) => <text key={i} x={x + 10} y={y + 39 + i * 17} fill="#e5edf0" fontSize={13}>{line.trim()}</text>)}
                <text x={x + 10} y={y + 76} fill="#a0b1bc" fontSize={11}>{room.region.slice(0, 27)}</text>
              </g>
            })}
          </svg>
        </div>
        <div className="max-h-28 overflow-auto text-xs sm:text-sm" aria-label="Selected map room">
          <p className="font-semibold text-story">{detail?.name}{detail?.id === map.current && ' · You are here'}</p>
          <p className="text-muted-foreground">{detail && Object.keys(detail.exits).length
            ? Object.entries(detail.exits).map(([direction, dest]) => `${direction}: ${byId[dest].name}${byId[dest].position[2] !== activeFloor ? ` (${floorName(byId[dest].position[2])})` : ''}`).join(' · ')
            : 'No connections to other visited rooms yet.'}</p>
        </div>
        <p className={`text-xs ${inCombat ? 'text-destructive' : 'text-muted-foreground'}`}>{inCombat ? 'You are in combat. Fighting continues while this map is open.' : 'This map does not pause the game.'} Press Escape or Close map to return.</p>
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>
}
