import { useEffect, useId, useState, type ReactNode } from 'react'
import { ChevronRightIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Field, FieldLabel, FieldLegend, FieldSet, FieldTitle } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { sortedEntries, useEditor } from './context'

type Obj = Record<string, any>
export type Option = [value: string, label: string]

export function FieldGrid({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('grid gap-4 md:grid-cols-2', className)}>{children}</div>
}

export function FormField({ label, htmlFor, wide, children }: { label?: ReactNode; htmlFor?: string; wide?: boolean; children: ReactNode }) {
  return (
    <Field className={cn('min-w-0', wide && 'md:col-span-2')}>
      {label && (htmlFor ? <FieldLabel htmlFor={htmlFor}>{label}</FieldLabel> : <FieldTitle>{label}</FieldTitle>)}
      {children}
    </Field>
  )
}

export function Note({ children, wide = true }: { children: ReactNode; wide?: boolean }) {
  return <p className={cn('text-sm leading-relaxed text-muted-foreground', wide && 'md:col-span-2')}>{children}</p>
}

/** A bordered group for one repeated record (a loot outcome, a placement, a rule). */
export function Group({ legend, children, onRemove, removeLabel = 'Remove' }: { legend: ReactNode; children: ReactNode; onRemove?: () => void; removeLabel?: string }) {
  const { touch } = useEditor()
  return (
    <FieldSet className="gap-3 rounded-lg border p-4 md:col-span-2">
      <FieldLegend className="px-1 text-gold">{legend}</FieldLegend>
      <FieldGrid>{children}</FieldGrid>
      {onRemove && (
        <Button type="button" variant="destructive" size="sm" className="w-fit" onClick={() => { onRemove(); touch() }}>
          {removeLabel}
        </Button>
      )}
    </FieldSet>
  )
}

// Open/closed state survives re-renders and switching records, keyed by title.
const disclosureState = new Map<string, boolean>()

export function Disclosure({ title, count, defaultOpen = false, children, className }: { title: string; count?: number; defaultOpen?: boolean; children: ReactNode; className?: string }) {
  const [open, setOpen] = useState(() => disclosureState.get(title) ?? defaultOpen)
  const change = (value: boolean) => {
    disclosureState.set(title, value)
    setOpen(value)
  }
  return (
    <Collapsible open={open} onOpenChange={change} className={cn('min-w-0 rounded-lg border p-3 md:col-span-2', className)}>
      <CollapsibleTrigger className="flex w-full items-center gap-2 text-left text-sm font-semibold text-primary">
        <ChevronRightIcon className={cn('size-4 transition-transform', open && 'rotate-90')} />
        {title}
        {count !== undefined && ` (${count})`}
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-4">{children}</CollapsibleContent>
    </Collapsible>
  )
}

export function SelectInput({ id, value, options, onChange, className, ...rest }: { id?: string; value: string; options: Option[]; onChange: (value: string) => void; className?: string; 'aria-label'?: string }) {
  return (
    <NativeSelect id={id} value={value} onChange={(e) => onChange(e.target.value)} className={cn('w-full', className)} {...rest}>
      {options.map(([v, label]) => (
        <NativeSelectOption key={v} value={v}>{label}</NativeSelectOption>
      ))}
    </NativeSelect>
  )
}

export function SelectField({ label, value, options, onChange, wide }: { label: ReactNode; value: string; options: Option[]; onChange: (value: string) => void; wide?: boolean }) {
  const id = useId()
  const { touch } = useEditor()
  return (
    <FormField label={label} htmlFor={id} wide={wide}>
      <SelectInput id={id} value={value} options={options} onChange={(v) => { onChange(v); touch() }} />
    </FormField>
  )
}

export function TextField({ obj, k, label, multiline, placeholder, maxLength, wide }: { obj: Obj; k: string; label: ReactNode; multiline?: boolean; placeholder?: string; maxLength?: number; wide?: boolean }) {
  const id = useId()
  const { touch } = useEditor()
  const props = {
    id,
    value: obj[k] ?? '',
    placeholder,
    maxLength,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      obj[k] = e.target.value
      touch()
    },
  }
  return (
    <FormField label={label} htmlFor={id} wide={wide ?? multiline}>
      {multiline ? <Textarea {...props} className="min-h-28 resize-y" /> : <Input {...props} />}
    </FormField>
  )
}

/**
 * Text drafts for fields whose stored value is parsed (numbers, line lists).
 * Keeps what the owner typed ("0." or a trailing newline) while the parsed
 * value is written to the draft world on every keystroke.
 */
function useDraft(stored: string, same: (text: string) => boolean) {
  const [text, setText] = useState(stored)
  useEffect(() => {
    if (!same(text)) setText(stored)
  }, [stored])
  return [text, setText] as const
}

export function NumberInput({ value, onValue, fallback, blank = 'zero', ...rest }: { value: number | null | undefined; onValue: (value: number | null | undefined) => void; fallback?: number; blank?: 'zero' | 'null' | 'delete' } & Omit<React.ComponentProps<'input'>, 'value'>) {
  const shown = value ?? fallback
  const stored = shown === undefined || shown === null ? '' : String(shown)
  // A cleared box stays cleared while the owner types; records remount on switch.
  const [text, setText] = useDraft(stored, (t) => t === '' || Number(t) === shown)
  return (
    <Input
      type="number"
      step="any"
      value={text}
      onChange={(e) => {
        const v = e.target.value
        setText(v)
        onValue(v === '' ? (blank === 'null' ? null : blank === 'delete' ? undefined : 0) : Number(v))
      }}
      {...rest}
    />
  )
}

export function NumberField({ obj, k, label, fallback, blank, wide, ...rest }: { obj: Obj; k: string | number; label: ReactNode; fallback?: number; blank?: 'zero' | 'null' | 'delete'; wide?: boolean } & Omit<React.ComponentProps<'input'>, 'value'>) {
  const id = useId()
  const { touch } = useEditor()
  return (
    <FormField label={label} htmlFor={id} wide={wide}>
      <NumberInput
        id={id}
        value={obj[k]}
        fallback={fallback}
        blank={blank}
        onValue={(v) => {
          if (v === undefined) delete obj[k]
          else obj[k] = v
          touch()
        }}
        {...rest}
      />
    </FormField>
  )
}

export function BoolField({ obj, k, label }: { obj: Obj; k: string; label: ReactNode }) {
  const id = useId()
  const { touch } = useEditor()
  return (
    <Field orientation="horizontal" className="min-w-0 self-end rounded-lg border px-3 py-2">
      <Switch id={id} checked={!!obj[k]} onCheckedChange={(checked) => { obj[k] = checked; touch() }} />
      <FieldLabel htmlFor={id} className="font-normal">{label}</FieldLabel>
    </Field>
  )
}

export function RangeField({ obj, k, label }: { obj: Obj; k: string; label: string }) {
  return (
    <>
      <NumberField obj={obj[k]} k={0} label={`${label} minimum`} />
      <NumberField obj={obj[k]} k={1} label={`${label} maximum`} />
    </>
  )
}

export function RefField({ obj, k, label, group, optional }: { obj: Obj; k: string; label: ReactNode; group: string; optional?: boolean }) {
  const { world } = useEditor()
  const options: Option[] = sortedEntries(world[group]).map(([id, v]) => [id, v.name])
  if (optional) options.unshift(['', 'None'])
  return (
    <SelectField
      label={label}
      value={obj[k] || ''}
      options={options}
      onChange={(v) => { if (v) obj[k] = v; else delete obj[k] }}
    />
  )
}

export function CheckList({ label, hideLabel, choices, isChecked, onToggle, filter }: { label: string; hideLabel?: boolean; choices: Option[]; isChecked: (id: string) => boolean; onToggle: (id: string, checked: boolean) => void; filter?: boolean }) {
  const { touch } = useEditor()
  const [query, setQuery] = useState('')
  const shown = choices.filter(([, name]) => name.toLowerCase().includes(query.toLowerCase()))
  return (
    <FormField label={hideLabel ? undefined : label} wide>
      {filter && (
        <Input placeholder="Filter choices" aria-label={`Filter ${label}`} value={query} onChange={(e) => setQuery(e.target.value)} className="max-w-sm" />
      )}
      <div className="grid gap-x-4 gap-y-1.5 sm:grid-cols-2 lg:grid-cols-3">
        {shown.map(([id, name]) => (
          <label key={id} className="flex items-center gap-2 text-sm">
            <Checkbox checked={isChecked(id)} onCheckedChange={(checked) => { onToggle(id, checked === true); touch() }} />
            {name}
          </label>
        ))}
      </div>
    </FormField>
  )
}

export function RefsField({ obj, k, label, group, dropWhenEmpty }: { obj: Obj; k: string; label: string; group: string; dropWhenEmpty?: boolean }) {
  const { world } = useEditor()
  return (
    <CheckList
      label={label}
      choices={sortedEntries(world[group]).map(([id, v]) => [id, v.name])}
      isChecked={(id) => (obj[k] || []).includes(id)}
      onToggle={(id, checked) => {
        obj[k] = checked ? [...(obj[k] || []), id] : (obj[k] || []).filter((x: string) => x !== id)
        if (dropWhenEmpty && !obj[k].length) delete obj[k]
      }}
    />
  )
}

export function LinesField({ obj, k, label }: { obj: Obj; k: string; label: ReactNode }) {
  const id = useId()
  const { touch } = useEditor()
  const stored = (obj[k] || []).join('\n')
  const parse = (text: string) => text.split('\n').map((x) => x.trim()).filter(Boolean)
  const [text, setText] = useDraft(stored, (t) => parse(t).join('\n') === stored)
  return (
    <FormField label={label} htmlFor={id} wide>
      <Textarea
        id={id}
        value={text}
        placeholder="One possible line per row. Leave blank for silence."
        className="min-h-28 resize-y"
        onChange={(e) => {
          setText(e.target.value)
          obj[k] = parse(e.target.value)
          touch()
        }}
      />
    </FormField>
  )
}

export function ListInput({ obj, k, label }: { obj: Obj; k: string; label: ReactNode }) {
  const id = useId()
  const { touch } = useEditor()
  const stored = (obj[k] || []).join(', ')
  const parse = (text: string) => text.split(',').map((v) => Number(v.trim()))
  const [text, setText] = useDraft(stored, (t) => parse(t).join(', ') === stored)
  return (
    <FormField label={label} htmlFor={id} wide>
      <Input
        id={id}
        value={text}
        onChange={(e) => {
          setText(e.target.value)
          obj[k] = parse(e.target.value)
          touch()
        }}
      />
    </FormField>
  )
}

export function AddButton({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  const { touch } = useEditor()
  return (
    <Button type="button" variant="outline" size="sm" className="w-fit md:col-span-2" onClick={() => { onClick(); touch() }}>
      {children}
    </Button>
  )
}
