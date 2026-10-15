import { useId, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { EditorHelpers, MapTools } from '@/lib/legacy'
import { firstKey, sortedEntries, useEditor } from '../context'
import {
  AddButton, BoolField, FormField, Group, Note, NumberField, RefField, RefsField,
  SelectField, SelectInput, TextField, type Option,
} from '../fields'

type Obj = Record<string, any>
const directionNames = ['north', 'south', 'east', 'west', 'up', 'down']
const title = (d: string) => d[0].toUpperCase() + d.slice(1)

function MapToolsFields({ room }: { room: Obj }) {
  const { world, current, open, touch, setMessage } = useEditor()
  const [showForm, setShowForm] = useState(false)
  const [direction, setDirection] = useState('north')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [status, setStatus] = useState('')
  const ids = { direction: useId(), name: useId(), description: useId() }
  const directions: Option[] = Object.keys(MapTools.directions).map((d) => [
    d,
    d + (room.exits[d] ? ` — connected to ${world.rooms[room.exits[d]].name}` : ''),
  ])
  return (
    <>
      <FormField label="Permanent reference">
        <strong className="text-sm">{room.code || 'Assigned on creation'}</strong>
      </FormField>
      <TextField obj={room} k="region" label="Map region label" />
      <FormField label="Regional rules" wide>
        <p className="text-sm text-muted-foreground">Assign squares and edit their enemy bank, weather and fog in Regions &amp; weather. A regional spawn square uses its regional bank instead of the room spawn settings below.</p>
        <Button type="button" variant="outline" onClick={() => open('regions', Object.keys(world.regions || {}).find(id => world.regions[id].rooms?.includes(current)))}>Edit regions &amp; weather</Button>
      </FormField>
      <FormField label="Map tools" wide>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" onClick={() => open('map')}>Open owner map</Button>
          <Button type="button" variant="outline" aria-expanded={showForm} onClick={() => setShowForm(!showForm)}>
            Add connected room
          </Button>
        </div>
      </FormField>
      {showForm && (
        <FormField label="Create an adjacent space" wide>
          <div className="grid gap-3 rounded-lg border p-4">
            <FormField label="Direction" htmlFor={ids.direction}>
              <SelectInput id={ids.direction} value={direction} options={directions} onChange={setDirection} />
            </FormField>
            <FormField label="Room name" htmlFor={ids.name}>
              <Input id={ids.name} placeholder="New room name" maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
            </FormField>
            <FormField label="Description" htmlFor={ids.description}>
              <Textarea id={ids.description} placeholder="Describe the new space" value={description} onChange={(e) => setDescription(e.target.value)} />
            </FormField>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                onClick={() => {
                  try {
                    const id = MapTools.addConnected(world, current, direction, name, description)
                    touch()
                    open('rooms', id)
                    setMessage('Room added to your draft with both exits. Save world changes to make it playable.')
                  } catch (e) {
                    setStatus((e as Error).message)
                  }
                }}
              >
                Create room and both exits
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  if (room.exits[direction]) open('rooms', room.exits[direction])
                  else setStatus('There is no exit in that direction yet.')
                }}
              >
                Open existing exit
              </Button>
            </div>
            {status && <p role="status" className="text-sm text-gold">{status}</p>}
          </div>
        </FormField>
      )}
    </>
  )
}

function SpawnFields({ room }: { room: Obj }) {
  const { world } = useEditor()
  const mode = room.encounter ? 'entry' : Object.prototype.hasOwnProperty.call(room, 'spawn_pool') ? 'pool' : 'fixed'
  const enemies: Option[] = sortedEntries(world.enemies).map(([id, e]) => [id, e.name])
  return (
    <>
      <SelectField
        label="Enemy spawning mode"
        wide
        value={mode}
        options={[['fixed', 'Repeat starting enemy'], ['pool', 'Choose from a respawn pool'], ['entry', 'Rare entry-roll encounter']]}
        onChange={(value) => {
          if (value === 'entry') {
            delete room.spawn_pool
            delete room.enemy
            room.encounter = { enemy: firstKey(world.enemies), chance: 5, cooldown: 300 }
          } else {
            delete room.encounter
            if (value === 'pool') room.spawn_pool = room.spawn_pool || []
            else delete room.spawn_pool
          }
        }}
      />
      {mode !== 'entry' && <RefField obj={room} k="enemy" label="Starting enemy (None starts empty)" group="enemies" optional />}
      <NumberField
        obj={room}
        k="respawn_seconds"
        label="Room respawn delay in seconds (blank uses creature default)"
        blank="delete"
        min={1}
        max={86400}
        placeholder="Use creature default"
        wide
      />
      {mode === 'pool' && (
        <>
          {room.spawn_pool.map((entry: Obj, index: number) => (
            <Group key={index} legend={`Possible next creature ${index + 1}`} onRemove={() => room.spawn_pool.splice(index, 1)}>
              <SelectField label="Creature" value={entry.enemy} options={enemies} onChange={(v) => (entry.enemy = v)} />
              <NumberField obj={entry} k="weight" label="Spawn weight" min={0.001} />
            </Group>
          ))}
          <AddButton onClick={() => room.spawn_pool.push({ enemy: firstKey(world.enemies), weight: 1 })}>Add possible next creature</AddButton>
          <Note>
            The starting enemy appears first. After a kill or capture, the room waits its timer and chooses one outcome. Equal
            weights mean equal chances. An empty pool means no replacements. With no starting enemy, the first roll waits the
            room timer (60 seconds if blank). Existing living creatures stay until defeated unless removed from both the
            starting choice and pool.
          </Note>
        </>
      )}
      <BoolField obj={room} k="creature_buyer" label="Buys occupied cages at creature sale values" />
    </>
  )
}

function InspectableObjects({ room }: { room: Obj }) {
  const { touch } = useEditor()
  const [name, setName] = useState('')
  const newId = useId()
  room.objects = room.objects || {}
  return (
    <FormField label="Inspectable objects" wide>
      <div className="grid gap-3">
        {Object.entries(room.objects).map(([key, text]) => (
          <label key={key} className="grid gap-1.5 text-sm">
            <span className="text-muted-foreground">LOOK {key}</span>
            <Textarea value={text as string} onChange={(e) => { room.objects[key] = e.target.value; touch() }} />
          </label>
        ))}
        <div className="flex flex-wrap items-center gap-2">
          <Input id={newId} className="max-w-xs" aria-label="New object name" placeholder="Object name, for example statue" value={name} onChange={(e) => setName(e.target.value)} />
          <Button
            type="button"
            variant="outline"
            disabled={!name.trim()}
            onClick={() => {
              room.objects[name.trim().toLowerCase()] = 'Describe what the player sees.'
              setName('')
              touch()
            }}
          >
            Add inspectable object
          </Button>
        </div>
      </div>
    </FormField>
  )
}

function Discoveries({ room }: { room: Obj }) {
  const { world } = useEditor()
  const placements: Obj[] = room.discoveries || []
  const roomEnemies = [...new Set([
    room.enemy,
    room.encounter?.enemy,
    ...(room.spawn_pool || []).map((x: Obj) => x.enemy),
    ...(room.population || []).flatMap((g: Obj) => [g.enemy, ...(g.pool || []).map((x: Obj) => x.enemy)]),
  ])].filter(Boolean) as string[]
  const keys: Option[] = sortedEntries(world.items).filter(([, i]) => i.kind === 'key').map(([k, i]) => [k, i.name])
  return (
    <>
      <Note>
        <strong className="text-foreground">Discoverable items and locked containers.</strong> Place items here to make them
        obtainable in this room. They can appear immediately, after LOOK at an object, or after killing its enemy. Each placement
        gives its contents once per saved game. A matching key is consumed when its container opens.
      </Note>
      {placements.map((d, index) => (
        <Group key={d.id ?? index} legend={`Placement ${index + 1} · ${d.name}`} removeLabel="Remove this placement" onRemove={() => room.discoveries.splice(index, 1)}>
          <TextField obj={d} k="name" label="Name players can type" />
          <SelectField
            label="Placement type"
            value={d.kind}
            options={[['item', 'Loose item'], ['container', 'Locked container']]}
            onChange={(v) => {
              d.kind = v
              if (v === 'item') {
                d.item = firstKey(world.items)
                delete d.key
                delete d.contents
              } else {
                d.key = Object.keys(world.items).find((k) => world.items[k].kind === 'key') || ''
                d.contents = [firstKey(world.items)]
                delete d.item
              }
            }}
          />
          <SelectField
            label="Reveal when"
            value={d.trigger || 'visible'}
            options={[['visible', 'Player looks in the room'], ['inspect', 'Player looks at an object'], ['defeat', 'Room enemy is killed']]}
            onChange={(v) => {
              d.trigger = v
              d.target = v === 'inspect' ? firstKey(room.objects) : room.enemy || room.encounter?.enemy || ''
            }}
          />
          {d.trigger === 'inspect' && (
            <SelectField
              label="Object to inspect"
              value={d.target || ''}
              options={[['', 'Choose an object'], ...Object.keys(room.objects || {}).map((k): Option => [k, k])]}
              onChange={(v) => (d.target = v)}
            />
          )}
          {d.trigger === 'defeat' && (
            <SelectField
              label="Hide again when this creature returns"
              value={d.hide_on_respawn === false ? 'no' : 'yes'}
              options={[["yes", "Yes — keep collected items and opened state"], ["no", "No — remain visible once discovered"]]}
              onChange={(v) => (d.hide_on_respawn = v === 'yes')}
            />
          )}
          {d.trigger === 'defeat' && (
            <SelectField
              label="Enemy that must be killed"
              value={d.target || ''}
              options={[['', 'Choose room enemy'], ...roomEnemies.map((k): Option => [k, world.enemies[k]?.name ?? k])]}
              onChange={(v) => (d.target = v)}
            />
          )}
          {d.kind === 'item' ? (
            <RefField obj={d} k="item" label="Item to discover" group="items" />
          ) : (
            <>
              <SelectField label="Required key" value={d.key || ''} options={[['', 'Choose a key'], ...keys]} onChange={(v) => (d.key = v)} />
              <RefsField obj={d} k="contents" label="Treasure inside (choose one or more)" group="items" />
              <TextField obj={d} k="description" label="Container description" multiline />
              <TextField obj={d} k="open_message" label="Message when opened" multiline />
            </>
          )}
          <TextField obj={d} k="message" label="Message when discovered (optional)" multiline />
        </Group>
      ))}
      <AddButton
        onClick={() => {
          room.discoveries = room.discoveries || []
          const ids = Object.fromEntries(room.discoveries.map((d: Obj) => [d.id, d]))
          room.discoveries.push({ id: EditorHelpers.uniqueId('discovery', ids), name: 'New discovery', kind: 'item', item: firstKey(world.items), trigger: 'visible', message: '' })
        }}
      >
        Add discoverable item / container
      </AddButton>
    </>
  )
}

function RandomEncounter({ room }: { room: Obj }) {
  const { world } = useEditor()
  if (!room.encounter) return null
  return (
    <>
      <SelectField
        label="Random enemy on entering this room"
        wide
        value={room.encounter.enemy || ''}
        options={[['', 'No random encounter'], ...sortedEntries(world.enemies).map(([id, e]): Option => [id, e.name])]}
        onChange={(id) => {
          if (id) room.encounter = { enemy: id, chance: 5, cooldown: 300 }
          else delete room.encounter
        }}
      />
      <NumberField obj={room.encounter} k="chance" label="Chance on entry (%)" />
      <NumberField obj={room.encounter} k="cooldown" label="Time between eligible rolls (seconds)" />
      <Note>
        Clear Safe town room when using random encounters. Both successful and unsuccessful rolls start the cooldown. Looking
        and waiting do not roll again. Each room has its own timer.
      </Note>
    </>
  )
}

export function RoomEditor({ room }: { room: Obj }) {
  const { touch } = useEditor()
  const obscuredId = useId()
  return (
    <>
      <MapToolsFields room={room} />
      <TextField obj={room} k="description" label="Room description" multiline />
      <BoolField obj={room} k="safe" label="Safe town room" />
      <BoolField obj={room} k="dark" label="Requires a carried light" />
      <BoolField obj={room} k="obscured_from_outside" label="Block looking in from neighboring rooms" />
      <BoolField obj={room} k="rest" label="Allow free resting" />
      <FormField label="Message shown when looking in (blank uses the default)" htmlFor={obscuredId} wide>
        <Textarea
          id={obscuredId}
          value={room.obscured_message ?? ''}
          placeholder="It is too dark; you cannot see anything."
          maxLength={6000}
          onChange={(e) => { room.obscured_message = e.target.value; touch() }}
        />
      </FormField>
      <SpawnFields room={room} />
      {directionNames.map((d) => (
        <RefField key={d} obj={room.exits} k={d} label={`${title(d)} exit`} group="rooms" optional />
      ))}
      <RefsField obj={room} k="shop" label="Shop stock (none means no shop)" group="items" dropWhenEmpty />
      <InspectableObjects room={room} />
      <RandomEncounter room={room} />
      <Discoveries room={room} />
    </>
  )
}
