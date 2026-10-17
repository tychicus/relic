import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Callout, Heading, Rule, TerminalBox } from '@/components/Terminal'
import { Emblem } from './HeaderPanel'
import type { Choice, Snapshot } from './types'

interface Props {
  choices?: { races: Choice[]; classes: Choice[] }
  recallRules?: Snapshot['recall_rules']
  multiplayer?: boolean
  characters?: Snapshot['characters']
  onCreate: (name: string, race: string, cls: string) => void
  onJoin?: (id: string) => void
}

// Keep the player's pick while it is still offered; otherwise prefer the classic default.
function pick(current: string, options: Choice[], preferred: string) {
  if (options.some((o) => o.id === current)) return current
  if (options.some((o) => o.id === preferred)) return preferred
  return options[0]?.id ?? ''
}

export function Welcome({ choices, recallRules, onCreate, multiplayer, characters = [], onJoin }: Props) {
  const [name, setName] = useState('')
  const [creating, setCreating] = useState(!characters.length)
  const [character, setCharacter] = useState(characters[0]?.id ?? '')
  const choosing = !!multiplayer && characters.length > 0 && !creating
  const selectedCharacter = characters.some(c => c.id === character) ? character : characters[0]?.id ?? ''
  const [race, setRace] = useState('human')
  const [cls, setCls] = useState('warrior')
  const races = choices?.races ?? []
  const selectedRace = races.find(r => r.id === race)
  const classes = (choices?.classes ?? []).filter(c => !selectedRace?.available_classes || selectedRace.available_classes.includes(c.id))
  const selectedClass = pick(cls, classes, 'warrior')
  const stats = selectedRace?.class_stats?.[selectedClass]

  useEffect(() => {
    setRace((current) => pick(current, races, 'human'))
    setCls((current) => pick(current, classes, 'warrior'))
  }, [JSON.stringify(choices), race])

  return (
    <div className="mx-auto grid max-w-4xl gap-5 py-6">
      <TerminalBox title="Relic Frontier v0.9.1">
        <div className="grid gap-4 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <div className="flex flex-col items-center justify-center text-center">
            <p className="font-bold">Welcome, traveler!</p>
            <Emblem />
            <p className="text-sm text-muted-foreground">A frontier of steel, spellwork &amp; forgotten machines</p>
          </div>
          <div className="min-w-0 border-t border-primary pt-4 md:border-t-0 md:border-l md:pt-0 md:pl-4">
            <Heading>{choosing ? 'Choose your character' : 'Create your character'}</Heading>
            {multiplayer && <div className="mt-3 flex gap-2">
              <Button type="button" variant={choosing ? 'default' : 'outline'} disabled={!characters.length} onClick={() => setCreating(false)}>Choose character</Button>
              <Button type="button" variant={!choosing ? 'default' : 'outline'} onClick={() => setCreating(true)}>New character</Button>
            </div>}
            {multiplayer && <p className="mt-3 text-sm text-muted-foreground">No password needed for now. Anyone connected to this test game can choose a saved character.</p>}
            <form
              className="mt-3 grid gap-3"
              onSubmit={(event) => {
                event.preventDefault()
                if (choosing) onJoin?.(selectedCharacter)
                else onCreate(name, race, selectedClass)
              }}
            >
              {choosing ? <Field>
                <FieldLabel htmlFor="character-choice">Saved character</FieldLabel>
                <NativeSelect id="character-choice" className="w-full" value={selectedCharacter} onChange={(e) => setCharacter(e.target.value)}>
                  {characters.map(c => <NativeSelectOption key={c.id} value={c.id}>{c.name} · Level {c.level}</NativeSelectOption>)}
                </NativeSelect>
                <Button type="submit" disabled={!selectedCharacter}>Continue playing</Button>
              </Field> : <><div className="grid gap-3 sm:grid-cols-2">
                <Field>
                  <FieldLabel htmlFor="race-choice">Race</FieldLabel>
                  <NativeSelect id="race-choice" className="w-full" value={race} onChange={(e) => setRace(e.target.value)}>
                    {races.map((r) => <NativeSelectOption key={r.id} value={r.id}>{r.name}</NativeSelectOption>)}
                  </NativeSelect>
                </Field>
                <Field>
                  <FieldLabel htmlFor="class-choice">Class</FieldLabel>
                  <NativeSelect id="class-choice" className="w-full" value={selectedClass} onChange={(e) => setCls(e.target.value)}>
                    {classes.map((c) => <NativeSelectOption key={c.id} value={c.id}>{c.name}</NativeSelectOption>)}
                  </NativeSelect>
                </Field>
              </div>
              {stats && <p className="text-sm text-story" aria-label="Starting character stats">
                Start: {stats.hp} HP · {stats.mana} mana<br />
                Per character level: +{Number(stats.hp_per_level.toFixed(2))} HP · +{Number(stats.mana_per_level.toFixed(2))} mana (totals rounded).
              </p>}
              {selectedRace?.description && <p className="text-sm text-muted-foreground">{selectedRace.description}</p>}
              {selectedRace?.magic_allowed === false && <p className="text-sm text-story">
                {selectedRace.recall_without_magic
                  ? 'Recall scrolls are the only magic item you can use. Spells, enchanting and magical equipment remain unavailable.'
                  : 'Cannot use spells, enchanting, magical equipment or scrolls.'}
                {' '}Choose a class that does not require magic.
              </p>}
              {classes.find(c => c.id === selectedClass)?.description && <p className="text-sm text-muted-foreground">{classes.find(c => c.id === selectedClass)?.description}</p>}
              <Field>
                <FieldLabel htmlFor="name">Character name</FieldLabel>
                <div className="flex flex-col gap-2 sm:flex-row">
                  <Input id="name" value={name} onChange={(e) => setName(e.target.value)} maxLength={32} placeholder="Name your adventurer" autoComplete="off" required className="flex-1" />
                  <Button type="submit" disabled={!selectedClass || !race}>Enter the square</Button>
                </div>
              </Field>
              </>}
            </form>
            <Rule className="my-4" />
            <Heading>Tips for getting started</Heading>
            <p className="mt-1 text-sm">Move with N, S, E, W, UP and DOWN. LOOK around; descriptions hide clues.</p>
            <p className="text-sm">ATTACK starts automatic combat. Type HELP for topics, HELP FIREBALL for skill details, or SYNTAX CAST for a command format.</p>
            {recallRules?.starting_scroll && <p className="mt-2 text-sm text-story">You start with a recall scroll: reusable below level {recallRules.reusable_below}, then single-use. Recall scrolls stop working at level {recallRules.disabled_from}.</p>}
          </div>
        </div>
      </TerminalBox>
      <Callout>
        <p className="font-bold">Your story starts at the fountain.</p>
        <p className="text-sm text-muted-foreground">{multiplayer ? 'A shared world with separate characters. SAY reaches your room; TELL reaches only its recipient and you. Progress saves on the host computer.' : 'One local character · keyboard-first · no account needed. Progress saves on this computer automatically.'}</p>
      </Callout>
    </div>
  )
}
