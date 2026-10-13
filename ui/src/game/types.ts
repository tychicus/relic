// Shape of GET /api/state and POST /api/command replies (engine.snapshot()).
// Only the fields the UI reads are listed.

export interface Item {
  name: string
  kind: string
  price: number
  damage?: number
  armor?: number
  heal?: number
  hands?: number
  rarity?: string
  recall?: boolean
  food?: boolean
  capacity?: number
  stored_count?: number
  occupied?: boolean
  creature_sale_value?: number
}

export interface Effect {
  id: string
  remaining: number
}

export interface Player {
  name: string
  race_name: string
  class_name: string
  level: number
  hp: number
  max_hp: number
  xp: number
  next_xp: number | null
  level_start_xp: number
  gold: number
  inventory: string[]
  bag_capacity: number
  equipment: Record<string, string>
  combat: { turn: string; next_at: number } | null
  cooldowns: Record<string, number>
  proficiencies?: Record<string, number>
  proficiency_limit?: number
  effects?: Effect[]
}

export interface Room {
  name: string
  description: string
  exits: string[]
  safe: boolean
  shop: string[]
  rest: boolean
  code?: string
  region?: string
  creature_buyer?: boolean
}

export interface Skill {
  id: string
  name: string
  description?: string
  effect?: string
  unlocked: boolean
  unlock_level?: number
  initiates?: boolean
}

export interface Creature {
  id: string
  name: string
  hp: number
  max_hp: number
  target?: boolean
  effects?: Effect[]
}

export interface LogLine {
  id: number
  text: string
  kind?: string
}

export interface Choice {
  id: string
  name: string
}

export interface Snapshot {
  title: string
  time: number
  player: Player | null
  creation?: { races: Choice[]; classes: Choice[] }
  room: Room
  items: Record<string, Item>
  ground: string[]
  enemy: { name: string; hp: number; max_hp: number; aggressive: boolean } | null
  log: LogLine[]
  player_skills?: Skill[]
  containers?: { id: string; name: string; opened: boolean }[]
  unconscious?: string | null
  enemies?: Creature[]
  unconscious_creatures?: { id: string; name: string }[]
  npcs?: { name: string; appearance: string }[]
  corpses?: { id: string; name: string }[]
  status_effects: Record<string, { name: string }>
}
