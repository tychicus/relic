// Shape of GET /api/state and POST /api/command replies (engine.snapshot()).
// Only the fields the UI reads are listed.

export interface MagicProgress {
  level: number
  max_level: number
  level_xp: number
  next_xp: number | null
  power: number
  effect_damage: number | null
}

export interface Item {
  armor_slot?: string
  shield?: boolean
  name: string
  kind: string
  price: number
  damage?: number
  armor?: number
  base_damage?: number
  base_armor?: number
  enchanted?: boolean
  enchantment_bonus?: number
  enchantment_description?: string
  enchantment_remaining?: number
  sharpen_bonus?: number
  damage_penalty?: number
  repair_cost?: number
  magic_progress?: MagicProgress
  heal?: number
  hands?: number
  rarity?: string
  drop_only?: boolean
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
  id: string
  defense?: number
  name: string
  race_name: string
  class_name: string
  level: number
  hp: number
  max_hp: number
  mana?: number
  ability_points?: number
  max_mana?: number
  mana_progress?: { level: number; max_level: number; level_xp: number; next_xp: number | null }
  xp: number
  next_xp: number | null
  level_start_xp: number
  gold: number
  bank_gold?: number
  inventory: string[]
  equipment: Record<string, string>
  combat: { turn: string; next_at: number } | null
  cooldowns: Record<string, number>
  action_ready?: number
  potion_ready?: number
  proficiencies?: Record<string, number>
  proficiency_limit?: number
  enchanting?: Record<string, { level: number; max_level: number; level_xp: number; next_xp: number | null; chance: number; bonus: number; duration: number }>
  effects?: Effect[]
  ward?: { skill: string; power: number; remaining: number } | null
}

export interface Room {
  bank_service?: boolean
  name: string
  description: string
  exits: string[]
  safe: boolean
  shop: string[]
  rest: boolean
  code?: string
  region?: string
  creature_buyer?: boolean
  repair_service?: boolean
  weather?: string
  fog?: number
}

export interface Skill {
  details?: { summary: string; lines: string[] }
  next_rank?: { rank: number; cost: number; required_level: number; lines: string[] } | null
  recovery_lines?: string[]
  passive?: boolean
  rank?: number
  max_rank?: number
  learn_cost?: number
  learn_level?: number
  affinity?: { power: number; mana: number; practice: number }
  id: string
  name: string
  description?: string
  effect?: string
  unlocked: boolean
  unlock_level?: number
  initiates?: boolean
  mana_cost?: number
  magic_progress?: MagicProgress
}

export interface Creature {
  id: string
  name: string
  hp: number
  max_hp: number
  target?: boolean
  engaged?: boolean
  aggressive?: boolean
  level?: number
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
  description?: string
  hp_bonus?: number
  magic_allowed?: boolean
  recall_without_magic?: boolean
  available_classes?: string[]
  class_stats?: Record<string, { hp: number; mana: number; hp_per_level: number; mana_per_level: number }>
}

export interface ExplorationMap {
  current: string
  rooms: { id: string; name: string; region: string; position: [number, number, number]; exits: Record<string, string> }[]
}

export interface Snapshot {
  multiplayer?: boolean
  session?: { owner: boolean }
  characters?: { id: string; name: string; level: number }[]
  players_here?: { name: string; level: number }[]
  exploration_map?: ExplorationMap
  ui_action?: 'show_map'
  recall_rules?: { reusable_below: number; disabled_from: number; starting_scroll: boolean }
  learning_enabled?: boolean
  learning_schedule?: string
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
  corpses?: { id: string; name: string; description: string; harvestable: boolean }[]
  player_bodies?: { id: string; name: string; expires: number; items: number; gold: number; owned: boolean }[]
  status_effects: Record<string, { name: string }>
}
