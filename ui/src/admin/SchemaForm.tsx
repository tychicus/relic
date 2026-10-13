import { useId } from 'react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Field, FieldLabel } from '@/components/ui/field'
import { Textarea } from '@/components/ui/textarea'
import { EditorHelpers } from '@/lib/legacy'
import { firstKey, sortedEntries, useEditor, type SchemaField, type World } from './context'
import { AddButton, CheckList, Disclosure, FieldGrid, FormField, Group, NumberInput, SelectInput, type Option } from './fields'

type Obj = Record<string, any>

function defaultRecord(world: World, fields: Record<string, SchemaField>) {
  const record: Obj = {}
  for (const [key, s] of Object.entries(fields)) {
    if (s.default !== undefined) record[key] = structuredClone(s.default)
    else if (s.type === 'ref') record[key] = s.optional ? '' : firstKey(world[s.group!])
  }
  return record
}

function SchemaInput({ obj, k, s }: { obj: Obj; k: string; s: SchemaField }) {
  const id = useId()
  const { world, touch, open } = useEditor()
  const value = obj[k] ?? s.default

  if (s.type === 'boolean') {
    return (
      <Field orientation="horizontal" className="min-w-0 self-end rounded-lg border px-3 py-2">
        <Checkbox id={id} checked={!!value} onCheckedChange={(checked) => { obj[k] = checked === true; touch() }} />
        <FieldLabel htmlFor={id} className="font-normal">{s.label}</FieldLabel>
      </Field>
    )
  }
  if (s.type === 'ref' || s.type === 'choice') {
    const options: Option[] =
      s.type === 'ref'
        ? [s.optional ? ['', 'None'] : ['', 'Choose…'], ...sortedEntries(world[s.group!]).map(([rid, r]): Option => [rid, r.name])]
        : s.choices!.map((v): Option => [String(v), String(v)])
    return (
      <FormField label={s.label} htmlFor={id}>
        <div className="flex gap-2">
          <SelectInput
            id={id}
            value={String(value ?? '')}
            options={options}
            onChange={(v) => {
              obj[k] = s.type === 'choice' && typeof s.default === 'number' ? Number(v) : v
              touch()
            }}
          />
          {s.type === 'ref' && (
            <Button type="button" variant="outline" disabled={!value} onClick={() => value && open(s.group!, value)}>
              Edit selected
            </Button>
          )}
        </div>
      </FormField>
    )
  }
  if (s.type === 'number') {
    return (
      <FormField label={s.label} htmlFor={id}>
        <NumberInput
          id={id}
          value={obj[k]}
          fallback={s.default}
          min={s.min}
          max={s.max}
          step={s.integer ? 1 : 'any'}
          onValue={(v) => { obj[k] = v ?? 0; touch() }}
        />
      </FormField>
    )
  }
  return (
    <FormField label={s.label} htmlFor={id} wide>
      <Textarea
        id={id}
        rows={2}
        maxLength={6000}
        value={value ?? ''}
        onChange={(e) => { obj[k] = e.target.value; touch() }}
      />
    </FormField>
  )
}

export function SchemaForm({ obj, fields }: { obj: Obj; fields: Record<string, SchemaField> }) {
  const { world } = useEditor()
  return (
    <FieldGrid>
      {Object.entries(fields).map(([key, s]) => {
        if (s.type === 'rows') {
          const rows: Obj[] = obj[key] || []
          return (
            <Disclosure key={key} title={s.label} count={rows.length}>
              <div className="grid gap-3">
                {rows.map((row, index) => (
                  <Group key={index} legend={`${s.label} ${index + 1}`} removeLabel="Remove row" onRemove={() => obj[key].splice(index, 1)}>
                    <div className="md:col-span-2">
                      <SchemaForm obj={row} fields={s.fields!} />
                    </div>
                  </Group>
                ))}
                <AddButton
                  onClick={() => {
                    obj[key] ??= []
                    const row = defaultRecord(world, s.fields!)
                    if (s.fields!.id) row.id = EditorHelpers.uniqueId('group', Object.fromEntries(obj[key].map((r: Obj) => [r.id, r])))
                    obj[key].push(row)
                  }}
                >
                  Add {s.label.toLowerCase()}
                </AddButton>
              </div>
            </Disclosure>
          )
        }
        if (s.type === 'refs') {
          const choices: Option[] =
            s.group === 'npc_interactions'
              ? [['look', 'Look / inspect'], ['talk', 'Talk']]
              : sortedEntries(world[s.group!]).map(([id, r]): Option => [id, r.name])
          const current = (): string[] => obj[key] ?? s.default ?? []
          return (
            <Disclosure key={key} title={s.label}>
              <CheckList
                label={s.label}
                hideLabel
                filter
                choices={choices}
                isChecked={(id) => current().includes(id)}
                onToggle={(id, checked) => {
                  obj[key] = checked ? [...current(), id] : current().filter((v) => v !== id)
                }}
              />
            </Disclosure>
          )
        }
        return <SchemaInput key={key} obj={obj} k={key} s={s} />
      })}
    </FieldGrid>
  )
}
