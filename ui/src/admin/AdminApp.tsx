import { useCallback, useEffect, useId, useRef, useState } from 'react'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { TerminalBox } from '@/components/Terminal'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Eyebrow, Masthead } from '@/components/Masthead'
import { api } from '@/lib/api'
import { EditorHelpers, MapTools } from '@/lib/legacy'
import { cn } from '@/lib/utils'
import { EditorContext, firstKey, sortedEntries, type Editor, type Schema, type World } from './context'
import { Disclosure, FieldGrid, SelectInput, TextField, type Option } from './fields'
import { SchemaForm } from './SchemaForm'
import { Dashboard } from './sections/Dashboard'
import { OwnerMap } from './sections/OwnerMap'
import { ClassEditor, EnemyEditor, ItemEditor, RaceEditor, SettingsEditor, SkillEditor } from './sections/RecordEditors'
import { RoomEditor } from './sections/RoomEditor'

const categories: Record<string, string> = {
  dashboard: 'Dashboard',
  map: 'Visual world map',
  rooms: 'World · Rooms',
  regions: 'Regions & weather',
  enemies: 'Creatures',
  npcs: 'NPCs & dialogue',
  races: 'Characters · Races',
  classes: 'Characters · Classes',
  items: 'Items & equipment',
  settings: 'Combat & progression',
  mana: 'Mana & mastery',
  learning: 'Abilities & learning',
  skills: 'Skills & spells',
  status_effects: 'Status effects',
  recipes: 'Cooking recipes',
  revision: 'Crafting & balance',
  raw: 'Advanced data',
}
const SPECIAL = ['settings', 'raw', 'map', 'dashboard', 'revision', 'mana', 'learning']

const placementHelp: Record<string, string> = {
  rooms: 'Use Open owner map or Add connected room to grow the map. Connected creation makes both exits automatically. Manual exit fields connect existing rooms.',
  items: 'To make this item obtainable: go to Rooms, choose a shop, and check it under Shop stock; go to Enemies and add it as loot; or go to Rooms and add a discoverable item or locked container below.',
  enemies: 'To place this enemy: go to Rooms, select a location, and choose its Starting enemy or weighted respawn pool.',
}

const sectionHelp: Record<string, string> = {
  learning: 'Characters start with one ability and earn points when they level up. Set each class starting ability and power, mana-cost and practice multipliers in Classes. Set ability categories, learning costs and maximum ranks in Skills & spells. Enchanting remains restricted to mages in its class eligibility.',
  mana: 'Valid paid casts train mana capacity. Damage and healing spells and magical equipment also earn their own practice. Enemies at or above character level award extra practice, with a further bonus for harder enemies. Lower-level enemies still give base practice. Set starting mana and growth in Characters · Classes, spell costs in Skills & spells, and enemy levels in Creatures.',
  regions: 'Choose the squares in this region, then its enemy spawning squares. The regional bank replaces room spawn rules only in those spawning squares. Safe squares cannot spawn enemies. Several creatures can share a square; aggressive creatures join the fight. Population limits include unconscious creatures. Lower limits cannot discard living creatures. Weather is descriptive; the visibility penalty controls how fog and weather affect scouting.',
  dashboard: 'Choose a workshop below. Your draft stays intact as you move between categories.',
  rooms: 'Block looking in hides this room’s name and contents from adjacent rooms, even with a lantern. Exits remain visible and movement still works. Once inside, normal darkness rules apply. Exits are directional. To connect a new room both ways, edit the return exit in the neighboring room too.',
  enemies: 'Dodge chance is a percentage: 20 means a 20% chance to avoid a successful basic attack or Bash. A dodge prevents all damage. Missing values mean 0%. Loot weights are relative: a weight of 3 is three times as likely as a weight of 1. One entry is chosen per victory. Saving preserves current enemy health (capped to any lower maximum) and respawn times. Capture requires low health; resistance reduces the skill’s success chance.',
  items: 'Weapon damage is added to a character’s base attack. Worn armor pieces and a held shield add protection against each incoming hit. Weight includes equipped gear and container contents; class carrying capacity grows by level. Shop purchase price is shown; resale pays half.',
  settings: 'Probabilities run from 0 to 1: 0.10 means 10%. Attack interval is the time between alternating player and enemy pulses. All engaged enemies may attack on an enemy pulse.',
  races: 'Every race listed here is available when creating a new character. Race HP bonus is added to class health.',
  classes: 'Every class listed here is playable. Set its base HP and damage; assign skills in the Skills section.',
  skills: 'Create working damage, healing, or knockout skills. Eligibility requires the selected class and race. The unlock level is the earliest level when players can spend points to learn it. Any includes future choices. Empty restricted lists allow nobody.',
  raw: 'Advanced editor for the complete world, including starting equipment and the working title. Prefer the forms for everyday changes.',
}

const schemaTitles: Record<string, string> = {
  classes: 'Starting ability, class strengths, mana & carrying capacity',
  rooms: 'Spawning, roaming, visibility & crafting',
  enemies: 'Status effects, resistance & harvesting',
  items: 'Weight, equipment slots, hands & effects',
  skills: 'Learning costs, ranks, category & combat effects',
  races: 'Perception & resistance',
}

const createKinds: Option[] = [
  ['region', 'Region'],
  ['room', 'Room / place'], ['weapon', 'Weapon'], ['armor', 'Armor'], ['consumable', 'Healing potion'],
  ['light', 'Light / lantern'], ['key', 'Key'], ['chest', 'Storage chest'], ['cage', 'Creature cage'],
  ['loot', 'Other item / treasure'], ['enemy', 'Enemy'], ['race', 'Race'], ['class', 'Class'], ['skill', 'Skill'],
  ['npc', 'NPC / person'], ['status_effect', 'Status effect'], ['recipe', 'Cooking recipe'],
]

function CoreFields({ section, current, obj }: { section: string; current: string; obj: Record<string, any> }) {
  switch (section) {
    case 'rooms': return <RoomEditor room={obj} />
    case 'enemies': return <EnemyEditor enemy={obj} />
    case 'items': return <ItemEditor item={obj} />
    case 'settings': return <SettingsEditor settings={obj} />
    case 'races': return <RaceEditor race={obj} />
    case 'classes': return <ClassEditor cls={obj} />
    case 'skills': return <SkillEditor skill={obj} id={current} />
    default: return null
  }
}

function RecordForm({ section, current, world, schema }: { section: string; current: string; world: World; schema: Schema }) {
  const obj = section === 'settings' ? world.settings : ['revision', 'mana', 'learning'].includes(section) ? world.revision : world[section]?.[current]
  if (!obj) return null
  const core = (
    <>
      {!['settings', 'revision', 'mana', 'learning'].includes(section) && <TextField obj={obj} k="name" label="Display name" />}
      <CoreFields section={section} current={current} obj={obj} />
    </>
  )
  const mastery = (key: string) => key.startsWith('mana_') || key.startsWith('practice_')
  const fields = section === 'learning' ? Object.fromEntries(Object.entries(schema.revision || {}).filter(([key]) => key.startsWith('learning_'))) : section === 'mana' ? Object.fromEntries(Object.entries(schema.revision || {}).filter(([key]) => mastery(key))) : section === 'revision' ? Object.fromEntries(Object.entries(schema[section] || {}).filter(([key]) => !['action_recovery', 'potion_recovery'].includes(key) && !mastery(key) && !key.startsWith('learning_') && !key.startsWith('enemy_heal_'))) : schema[section]
  if (!fields) return <FieldGrid>{core}</FieldGrid>
  const wrapCore = ['rooms', 'enemies', 'items', 'skills'].includes(section)
  return (
    <div className="grid gap-3">
      {section === 'revision' && (
        <p className="text-sm text-muted-foreground">
          All values below are live game rules. Changes apply after Save world changes. Chance fields marked % use 0–100;
          fractions use 0–1. Existing cooldown deadlines and spawn timers keep their scheduled time.
        </p>
      )}
      {section !== 'revision' &&
        (wrapCore ? (
          <Disclosure title="Core settings & existing content" defaultOpen>
            <FieldGrid>{core}</FieldGrid>
          </Disclosure>
        ) : (
          <FieldGrid>{core}</FieldGrid>
        ))}
      <Disclosure title={schemaTitles[section] || 'Configuration'} defaultOpen={['learning', 'mana', 'classes', 'regions', 'revision', 'npcs', 'status_effects', 'recipes'].includes(section)}>
        <SchemaForm obj={obj} fields={fields} />
      </Disclosure>
    </div>
  )
}

export function AdminApp() {
  const world = useRef<World | null>(null)
  const schema = useRef<Schema>({})
  const [, setVersion] = useState(0)
  const redraw = useCallback(() => setVersion((v) => v + 1), [])
  const [section, setSection] = useState('dashboard')
  const [current, setCurrent] = useState('square')
  const [dirty, setDirty] = useState(false)
  const [message, setMessageState] = useState({ text: '', error: false })
  const [createMessage, setCreateMessage] = useState('')
  const [createKind, setCreateKind] = useState('room')
  const [createName, setCreateName] = useState('')
  const [raw, setRaw] = useState('')
  const [entryFilter, setEntryFilter] = useState('')
  const [confirmDiscard, setConfirmDiscard] = useState(false)
  const [saving, setSaving] = useState(false)
  const createNameRef = useRef<HTMLInputElement>(null)
  const fieldsRef = useRef<HTMLDivElement>(null)
  const ids = { kind: useId(), name: useId(), entry: useId(), raw: useId() }

  const setMessage = useCallback((text: string, error = false) => setMessageState({ text, error }), [])
  const touch = useCallback(() => {
    setDirty(true)
    redraw()
  }, [redraw])

  const load = useCallback(async () => {
    try {
      await api('/api/state') // issues the token needed to save
      const [w, s] = await Promise.all([api<World>('/api/world'), api<Schema>('/api/editor-schema')])
      for (const group of ['regions', 'status_effects', 'npcs', 'recipes', 'revision']) w[group] ??= {}
      MapTools.ensureMetadata(w)
      world.current = w
      schema.current = s
      setDirty(false)
      setRaw(JSON.stringify(w, null, 2))
      redraw()
    } catch (e) {
      setMessage('Could not load the editor: ' + (e as Error).message, true)
    }
  }, [redraw, setMessage])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault()
        e.returnValue = ''
      }
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  /** Apply the Advanced data text to the draft. Returns false if it is not valid JSON. */
  const commitRaw = useCallback(() => {
    if (section !== 'raw') return true
    try {
      world.current = JSON.parse(raw)
      return true
    } catch {
      return false
    }
  }, [section, raw])

  const open = useCallback(
    (group: string, id?: string) => {
      if (!commitRaw()) {
        setMessage('Correct the JSON before switching sections.', true)
        return
      }
      if (group === 'raw') setRaw(JSON.stringify(world.current, null, 2))
      setSection(group)
      setCurrent(id ?? firstKey(world.current?.[group]))
      setEntryFilter('')
      window.scrollTo({ top: fieldsRef.current?.offsetTop ?? 0, behavior: 'smooth' })
    },
    [commitRaw, setMessage],
  )

  // Rebuilt every render: forms mutate the draft in place and rely on touch() re-rendering the tree.
  const editor: Editor | null = world.current && {
    world: world.current,
    schema: schema.current,
    section,
    current,
    touch,
    open,
    setMessage,
  }

  async function save() {
    setSaving(true)
    try {
      if (!commitRaw()) throw new Error('Correct the JSON before saving.')
      await api('/api/world', world.current)
      setDirty(false)
      setMessage('Saved. Changes are live, and the previous world settings were backed up.')
    } catch (e) {
      setMessage((e as Error).message, true)
    } finally {
      setSaving(false)
    }
  }

  function discard() {
    load()
    setMessage('')
  }

  function create(event: React.FormEvent) {
    event.preventDefault()
    try {
      if (!world.current) throw new Error('Wait for the world to finish loading.')
      if (!commitRaw()) throw new Error('Correct the JSON before adding content.')
      const w = world.current
      const result = EditorHelpers.makeEntry(w, createKind, createName)
      w[result.group][result.id] = result.entry
      MapTools.ensureMetadata(w)
      setSection(result.group)
      setCurrent(result.id)
      touch()
      setCreateName('')
      setCreateMessage(`${result.entry.name} added to your draft. Edit its details below, then Save world changes.`)
      setMessage('')
      setTimeout(() => fieldsRef.current?.querySelector('input')?.focus())
    } catch (e) {
      setCreateMessage((e as Error).message)
    }
  }

  const w = world.current
  const special = SPECIAL.includes(section)
  const records = w && !special ? sortedEntries(w[section]) : []
  const shownCurrent = w && !special && !w[section]?.[current] ? firstKey(w[section]) : current
  const entryOptions: Option[] = records
    .filter(([id, v]) => id === shownCurrent || v.name.toLowerCase().includes(entryFilter.toLowerCase()))
    .map(([id, v]) => [id, v.name])

  return (
    <div className="min-h-screen">
      <Masthead>
        <a href="/" className="text-primary underline-offset-4 hover:underline">Return to adventure</a>
      </Masthead>
      <main className="mx-auto max-w-[1500px] px-4 pt-5 pb-4 sm:px-[3vw] sm:pt-8">
        <Eyebrow>World workshop</Eyebrow>
        <h1 className="mt-2 mb-3 text-3xl font-bold">Make the frontier your own.</h1>
        <p className="max-w-[78ch] text-muted-foreground">
          Edit rooms, creatures, items, and game balance. Changes apply when you save. Finish any active fight first. Every save
          keeps a copy of the previous world settings.
        </p>

        <TerminalBox title="Add something to your world" className="my-6">
          <div className="grid gap-4">
            <div className="flex flex-wrap gap-2">
              {([['room', 'Add room / place'], ['weapon', 'Add weapon'], ['loot', 'Add item'], ['enemy', 'Add enemy']] as const).map(([kind, label]) => (
                <Button
                  key={kind}
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setCreateKind(kind)
                    createNameRef.current?.focus()
                  }}
                >
                  {label}
                </Button>
              ))}
            </div>
            <form onSubmit={create} className="flex flex-wrap items-end gap-4">
              <Field className="flex-[1_1_220px]">
                <FieldLabel htmlFor={ids.kind}>What are you adding?</FieldLabel>
                <SelectInput id={ids.kind} value={createKind} options={createKinds} onChange={setCreateKind} />
              </Field>
              <Field className="flex-[1_1_220px]">
                <FieldLabel htmlFor={ids.name}>Name</FieldLabel>
                <Input id={ids.name} ref={createNameRef} value={createName} onChange={(e) => setCreateName(e.target.value)} placeholder="e.g. Silver Sword or Misty Forest" maxLength={120} required />
              </Field>
              <Button type="submit">Create and edit</Button>
            </form>
            <p className="text-sm text-muted-foreground">
              Use normal names, including spaces and capital letters. Internal IDs are handled automatically. New content stays in
              your draft until you save.
            </p>
            {createMessage && <p role="status" className="text-sm text-gold">{createMessage}</p>}
          </div>
        </TerminalBox>

        <div className="grid gap-6 md:grid-cols-[200px_minmax(0,1fr)]">
          <nav aria-label="Editor sections" className="flex flex-wrap gap-2 self-start md:sticky md:top-4 md:max-h-[90vh] md:flex-col md:flex-nowrap md:overflow-auto">
            {Object.entries(categories).map(([key, label]) => (
              <Button
                key={key}
                type="button"
                variant={key === section ? 'secondary' : 'ghost'}
                aria-current={key === section ? 'page' : undefined}
                className={cn('flex-[1_1_140px] justify-start md:flex-none', key === section && 'text-primary ring-1 ring-primary')}
                onClick={() => open(key)}
              >
                {label}
              </Button>
            ))}
          </nav>

          <TerminalBox title={categories[section]} className="pb-0">
            <div ref={fieldsRef} className="grid min-w-0 gap-4 break-words">
              {!special && (
                <div className="flex flex-wrap items-center gap-2.5">
                  <FieldLabel htmlFor={ids.entry}>Edit existing: {categories[section]}</FieldLabel>
                  <Input placeholder="Filter records by name" aria-label="Filter records" className="w-auto min-w-48 flex-1" value={entryFilter} onChange={(e) => setEntryFilter(e.target.value)} />
                  <SelectInput id={ids.entry} className="w-auto min-w-48" value={shownCurrent} options={entryOptions} onChange={(id) => { setCurrent(id); setEntryFilter('') }} />
                </div>
              )}
              {sectionHelp[section] && section !== 'map' && <p className="text-sm text-muted-foreground">{sectionHelp[section]}</p>}
              {placementHelp[section] && (
                <p className="border-l-3 border-primary bg-accent/40 px-4 py-3 text-sm">{placementHelp[section]}</p>
              )}

              {editor && (
                <EditorContext.Provider value={editor}>
                  {section === 'dashboard' && <Dashboard />}
                  {section === 'map' && <OwnerMap />}
                  {section === 'raw' && (
                    <Textarea
                      id={ids.raw}
                      aria-label="Complete world JSON"
                      spellCheck={false}
                      className="h-[480px] font-mono text-sm"
                      value={raw}
                      onChange={(e) => { setRaw(e.target.value); setDirty(true) }}
                    />
                  )}
                  {!['dashboard', 'map', 'raw'].includes(section) && (
                    <RecordForm key={`${section}:${shownCurrent}`} section={section} current={shownCurrent} world={editor.world} schema={editor.schema} />
                  )}
                </EditorContext.Provider>
              )}

              <div className="sticky bottom-0 -mx-4 flex flex-wrap items-center gap-3 rounded-b-md border-t bg-background px-4 py-3">
                <Button onClick={save} disabled={saving || !w}>Save world changes</Button>
                <Button variant="outline" onClick={() => (dirty ? setConfirmDiscard(true) : discard())}>
                  Discard unsaved changes
                </Button>
                <span className={cn('text-sm', dirty ? 'text-gold' : 'text-muted-foreground')}>
                  {dirty ? 'Unsaved changes' : 'No unsaved changes'}
                </span>
                {message.text && (
                  <p role="status" className={cn('basis-full text-sm whitespace-pre-wrap', message.error && 'text-destructive')}>
                    {message.text}
                  </p>
                )}
              </div>
            </div>
          </TerminalBox>
        </div>
      </main>
      <footer className="px-[3vw] py-8 text-center text-sm text-muted-foreground">Local owner access · Available only on this computer</footer>

      <AlertDialog open={confirmDiscard} onOpenChange={setConfirmDiscard}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Discard unsaved world changes?</AlertDialogTitle>
            <AlertDialogDescription>Your draft returns to the last saved world. This cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep editing</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={discard}>Discard changes</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
