import { useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { MapTools } from '@/lib/legacy'
import { useEditor, type World } from '../context'
import { SelectInput, type Option } from '../fields'

type Room = Record<string, any>
type Entry = [string, Room]

// Colors are baked into the exported SVG, so they stay literal here.
const COLORS = ['#71dace', '#e9bb72', '#aaadff', '#f39491', '#a0d083', '#82b9f5']
const FONT = 'sans-serif'

// Remember filters for the session, as the previous editor did.
const filters = { search: '', region: '' }

function download(name: string, body: string, type: string) {
  const url = URL.createObjectURL(new Blob([body], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.append(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function MapSvg({ world, entries, onOpen, svgRef }: { world: World; entries: Entry[]; onOpen: (id: string) => void; svgRef: React.Ref<SVGSVGElement> }) {
  const floors = [...new Set(entries.map(([, r]) => r.map_position[2]))].sort((a, b) => b - a)
  const points: Record<string, [number, number]> = {}
  const panels: { floor: number; y: number }[] = []
  let offset = 60
  let maxWidth = 800
  for (const floor of floors) {
    const rows = entries.filter(([, r]) => r.map_position[2] === floor)
    const xs = rows.map(([, r]) => r.map_position[0])
    const ys = rows.map(([, r]) => r.map_position[1])
    const minX = Math.min(...xs)
    const minY = Math.min(...ys)
    const width = (Math.max(...xs) - minX + 1) * 240 + 100
    const height = (Math.max(...ys) - minY + 1) * 140 + 100
    panels.push({ floor, y: offset })
    maxWidth = Math.max(maxWidth, width)
    for (const [id, r] of rows) points[id] = [(r.map_position[0] - minX) * 240 + 50, (r.map_position[1] - minY) * 140 + offset + 60]
    offset += height + 50
  }

  const lines: React.ReactNode[] = []
  const drawn = new Set<string>()
  for (const [id, r] of entries) {
    for (const [d, dest] of Object.entries(r.exits) as [keyof typeof MapTools.opposite, string][]) {
      if (!points[dest]) continue
      const reciprocal = world.rooms[dest].exits[MapTools.opposite[d]] === id
      const pair = [id, dest].sort().join('|')
      if (reciprocal && drawn.has(pair)) continue
      drawn.add(pair)
      const a = points[id]
      const b = points[dest]
      const dx = b[0] - a[0]
      const dy = b[1] - a[1]
      let [x1, y1, x2, y2] = [a[0] + 100, a[1] + 42, b[0] + 100, b[1] + 42]
      if (Math.abs(dx) >= Math.abs(dy)) {
        x1 += Math.sign(dx) * 102
        x2 -= Math.sign(dx) * 102
      } else {
        y1 += Math.sign(dy) * 45
        y2 -= Math.sign(dy) * 45
      }
      lines.push(
        <line
          key={`${id}-${d}`}
          x1={x1} y1={y1} x2={x2} y2={y2}
          stroke="#819daa"
          strokeWidth={2}
          markerEnd="url(#exit-arrow)"
          markerStart={reciprocal ? 'url(#exit-arrow)' : undefined}
          strokeDasharray={r.map_position[2] !== world.rooms[dest].map_position[2] ? '7 5' : undefined}
        />,
      )
    }
  }

  const regions = [...new Set((Object.values(world.rooms) as Room[]).map((r) => r.region))].sort()
  return (
    <svg ref={svgRef} xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Owner map, including hidden rooms" viewBox={`0 0 ${maxWidth} ${offset}`} width={maxWidth} height={offset} className="block max-w-none">
      <rect width={maxWidth} height={offset} fill="#0a1016" />
      <text x={24} y={30} fill="#e5edf0" fontFamily={FONT} fontSize={20}>Relic Frontier — owner map (includes hidden rooms)</text>
      <defs>
        <marker id="exit-arrow" viewBox="0 0 10 10" refX={9} refY={5} markerWidth={6} markerHeight={6} orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#819daa" />
        </marker>
      </defs>
      {panels.map((p) => (
        <text key={p.floor} x={24} y={p.y + 22} fill="#71dace" fontFamily={FONT} fontSize={16}>Elevation {p.floor} · North ↑</text>
      ))}
      {lines}
      {entries.map(([id, r]) => {
        const [x, y] = points[id]
        const words: string[] = r.name.match(/.{1,24}(?:\s|$)|.{1,24}/g) || [r.name]
        return (
          <g
            key={id}
            tabIndex={0}
            role="button"
            aria-label={`${r.code}: ${r.name}, ${r.region}`}
            data-room={id}
            className="cursor-pointer [&:focus>rect]:stroke-white [&:focus>rect]:stroke-4 focus:outline-none"
            onClick={() => onOpen(id)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onOpen(id)
              }
            }}
          >
            <title>{`${r.code} — ${r.name}\n${r.region}\n${Object.entries(r.exits).map(([d, to]) => `${d}: ${world.rooms[to as string].code}`).join('\n')}`}</title>
            <rect x={x} y={y} width={200} height={86} rx={8} fill="#172631" stroke={COLORS[regions.indexOf(r.region) % COLORS.length]} strokeWidth={2} />
            <text x={x + 10} y={y + 20} fill="#71dace" fontSize={13} fontFamily={FONT}>{r.code + (r.obscured_from_outside ? ' · hidden view' : '')}</text>
            {words.slice(0, 2).map((line, n) => (
              <text key={n} x={x + 10} y={y + 42 + n * 17} fill="#e5edf0" fontSize={14} fontFamily={FONT}>{line.trim()}</text>
            ))}
            <text x={x + 10} y={y + 78} fill="#a0b1bc" fontSize={11} fontFamily={FONT}>{r.region.slice(0, 30)}</text>
          </g>
        )
      })}
    </svg>
  )
}

export function OwnerMap() {
  const { world, open } = useEditor()
  const [search, setSearch] = useState(filters.search)
  const [region, setRegion] = useState(filters.region)
  const svgRef = useRef<SVGSVGElement>(null)
  filters.search = search
  filters.region = region

  const regions = [...new Set((Object.values(world.rooms) as Room[]).map((r) => r.region as string))].sort()
  const query = search.trim().toLowerCase()
  const entries = (Object.entries(world.rooms) as Entry[]).filter(
    ([, r]) => (!region || r.region === region) && (!query || [r.code, r.name, r.region].join(' ').toLowerCase().includes(query)),
  )
  const openRoom = (id: string) => open('rooms', id)

  return (
    <div className="min-w-0">
      <h2 className="text-xl font-semibold">World map</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Click a room to edit it or add a connected room. Arrows show travel directions; dashed lines join elevations. Hidden rooms
        are included. Save world changes to apply your draft.
      </p>
      <div className="my-4 flex flex-wrap gap-2">
        <Input className="min-w-[220px] flex-1" placeholder="Search room name, code, or region" aria-label="Search owner map" value={search} onChange={(e) => setSearch(e.target.value)} />
        <SelectInput
          className="w-auto"
          aria-label="Filter map region"
          value={region}
          options={[['', 'All regions'], ...regions.map((r): Option => [r, r])]}
          onChange={setRegion}
        />
        <Button
          type="button"
          variant="outline"
          onClick={() => svgRef.current && download('Relic_Frontier_Owner_Map.svg', new XMLSerializer().serializeToString(svgRef.current), 'image/svg+xml')}
        >
          Export labeled map (SVG)
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() =>
            download(
              'Relic_Frontier_Room_Directory.json',
              JSON.stringify(
                (Object.entries(world.rooms) as Entry[]).map(([id, r]) => ({
                  id, code: r.code, name: r.name, region: r.region, position: r.map_position,
                  exits: Object.fromEntries(Object.entries(r.exits).map(([d, to]) => [d, world.rooms[to as string].code])),
                })),
                null,
                2,
              ),
              'application/json',
            )
          }
        >
          Export room directory (JSON)
        </Button>
      </div>
      <p className="mb-2 text-sm">{entries.length} matching rooms</p>
      <div className="mb-4 flex max-h-[150px] flex-wrap gap-1.5 overflow-auto">
        {entries.map(([id, r]) => (
          <Button key={id} type="button" variant="secondary" size="xs" onClick={() => openRoom(id)}>
            {r.code} — {r.name}
          </Button>
        ))}
      </div>
      <div className="max-h-[650px] overflow-auto rounded-lg border">
        {entries.length ? <MapSvg world={world} entries={entries} onOpen={openRoom} svgRef={svgRef} /> : <p className="p-4">No rooms match.</p>}
      </div>
    </div>
  )
}
