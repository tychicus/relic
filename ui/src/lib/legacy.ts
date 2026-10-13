// map-tools.cjs and editor-helpers.cjs are shared with the Node tests in ../tests.
// Production builds wrap them as CommonJS (module.exports becomes the default export);
// the dev server runs them as plain scripts, where they register on globalThis instead.
import * as mapToolsModule from './map-tools.cjs'
import * as editorHelpersModule from './editor-helpers.cjs'

type World = Record<string, any>
type Direction = 'north' | 'south' | 'east' | 'west' | 'up' | 'down'

export interface MapToolsApi {
  directions: Record<Direction, [number, number, number]>
  opposite: Record<Direction, Direction>
  nextCode(world: World, region: string): string
  ensureMetadata(world: World): void
  addConnected(world: World, sourceId: string, direction: string, name: string, description: string): string
}

export interface EditorHelpersApi {
  uniqueId(name: string, entries: Record<string, unknown>): string
  makeEntry(world: World, kind: string, rawName: string): { group: string; id: string; entry: any }
}

const root = globalThis as unknown as { MapTools?: MapToolsApi; EditorHelpers?: EditorHelpersApi }
const exported = (module: object) => (module as { default?: unknown }).default

export const MapTools = (exported(mapToolsModule) ?? root.MapTools) as MapToolsApi
export const EditorHelpers = (exported(editorHelpersModule) ?? root.EditorHelpers) as EditorHelpersApi
