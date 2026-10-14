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
  weight?: number
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
  carried_weight?: number
  carry_capacity?: number
  weight_enabled?: boolean
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
  inventory: string[]
  bag_capacity: number
  equipment: Record<string, string>
  combat: { turn: string; next_at: number } | null
  cooldowns: Record<string, number>
  action_ready?: number
  potion_ready?: number
  proficiencies?: Record<string, number>
  proficiency_limit?: number
  enchanting?: Record<string, { level: number; max_level: number; level_xp: number; next_xp: number | null; chance: number; bonus: number; duration: number }>
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
  repair_service?: boolean
  weather?: string
  fog?: number
}

export interface Skill {
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
}

export interface Snapshot {
  learning_enabled?: boolean
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
