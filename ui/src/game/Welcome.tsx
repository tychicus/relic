import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Callout, Heading, Rule, TerminalBox } from '@/components/Terminal'
import { Emblem } from './HeaderPanel'
import type { Choice } from './types'

interface Props {
  choices?: { races: Choice[]; classes: Choice[] }
  onCreate: (name: string, race: string, cls: string) => void
}

// Keep the player's pick while it is still offered; otherwise prefer the classic default.
function pick(current: string, options: Choice[], preferred: string) {
  if (options.some((o) => o.id === current)) return current
  if (options.some((o) => o.id === preferred)) return preferred
  return options[0]?.id ?? ''
}

export function Welcome({ choices, onCreate }: Props) {
  const [name, setName] = useState('')
  const [race, setRace] = useState('human')
  const [cls, setCls] = useState('warrior')
  const races = choices?.races ?? []
  const classes = choices?.classes ?? []

  useEffect(() => {
    setRace((current) => pick(current, races, 'human'))
    setCls((current) => pick(current, classes, 'warrior'))
  }, [JSON.stringify(choices)])

  return (
    <div className="mx-auto grid max-w-4xl gap-5 py-6">
      <TerminalBox title="Relic Frontier v0.9.0">
        <div className="grid gap-4 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <div className="flex flex-col items-center justify-center text-center">
            <p className="font-bold">Welcome, traveler!</p>
            <Emblem />
            <p className="text-sm text-muted-foreground">A frontier of steel, spellwork &amp; forgotten machines</p>
          </div>
          <div className="min-w-0 border-t border-primary pt-4 md:border-t-0 md:border-l md:pt-0 md:pl-4">
            <Heading>Create your character</Heading>
            <form
              className="mt-3 grid gap-3"
              onSubmit={(event) => {
                event.preventDefault()
                onCreate(name, race, cls)
              }}
            >
              <div className="grid gap-3 sm:grid-cols-2">
                <Field>
                  <FieldLabel htmlFor="race-choice">Race</FieldLabel>
                  <NativeSelect id="race-choice" className="w-full" value={race} onChange={(e) => setRace(e.target.value)}>
                    {races.map((r) => <NativeSelectOption key={r.id} value={r.id}>{r.name}</NativeSelectOption>)}
                  </NativeSelect>
                </Field>
                <Field>
                  <FieldLabel htmlFor="class-choice">Class</FieldLabel>
                  <NativeSelect id="class-choice" className="w-full" value={cls} onChange={(e) => setCls(e.target.value)}>
                    {classes.map((c) => <NativeSelectOption key={c.id} value={c.id}>{c.name}</NativeSelectOption>)}
                  </NativeSelect>
                </Field>
              </div>
              {classes.find(c => c.id === cls)?.description && <p className="text-sm text-muted-foreground">{classes.find(c => c.id === cls)?.description}</p>}
              <Field>
                <FieldLabel htmlFor="name">Character name</FieldLabel>
                <div className="flex flex-col gap-2 sm:flex-row">
                  <Input id="name" value={name} onChange={(e) => setName(e.target.value)} maxLength={32} placeholder="Name your adventurer" autoComplete="off" required className="flex-1" />
                  <Button type="submit">Enter the square</Button>
                </div>
              </Field>
            </form>
            <Rule className="my-4" />
            <Heading>Tips for getting started</Heading>
            <p className="mt-1 text-sm">Move with N, S, E, W, UP and DOWN. LOOK around; descriptions hide clues.</p>
            <p className="text-sm">ATTACK starts automatic combat. Type HELP for every command.</p>
          </div>
        </div>
      </TerminalBox>
      <Callout>
        <p className="font-bold">Your story starts at the fountain.</p>
        <p className="text-sm text-muted-foreground">One local character · keyboard-first · no account needed. Progress saves on this computer automatically.</p>
      </Callout>
    </div>
  )
}
