import { createContext, useContext } from 'react'

export type World = Record<string, any>
export type Schema = Record<string, Record<string, SchemaField>>

export interface SchemaField {
  type: 'number' | 'text' | 'boolean' | 'choice' | 'ref' | 'rows' | 'refs'
  label: string
  default?: any
  min?: number
  max?: number
  integer?: boolean
  choices?: (string | number)[]
  group?: string
  optional?: boolean
  fields?: Record<string, SchemaField>
}

export interface Editor {
  /** The draft world. Forms mutate it in place, then call touch(). */
  world: World
  schema: Schema
  section: string
  current: string
  /** Mark the draft as changed and re-render. */
  touch(): void
  open(group: string, id?: string): void
  setMessage(text: string, error?: boolean): void
}

export const EditorContext = createContext<Editor | null>(null)

export function useEditor() {
  const editor = useContext(EditorContext)
  if (!editor) throw new Error('useEditor must be used inside the owner editor.')
  return editor
}

export function sortedEntries(entries: Record<string, any> = {}): [string, any][] {
  return Object.entries(entries).sort(
    (a, b) => a[1].name.localeCompare(b[1].name, undefined, { sensitivity: 'base', numeric: true }) || a[0].localeCompare(b[0]),
  )
}

export function firstKey(entries: Record<string, unknown> = {}) {
  return Object.keys(entries)[0] ?? ''
}
