import { Checkbox } from '@/components/ui/checkbox'
import { sortedEntries, useEditor } from '../context'
import {
  AddButton, BoolField, CheckList, FormField, Group, LinesField, ListInput, Note, NumberField,
  RangeField, SelectField, TextField, type Option,
} from '../fields'

type Obj = Record<string, any>

export function EnemyEditor({ enemy }: { enemy: Obj }) {
  const { world } = useEditor()
  const items: Option[] = [['', 'No item'], ...sortedEntries(world.items).map(([id, v]): Option => [id, v.name])]
  return (
    <>
      <TextField obj={enemy} k="description" label="Description" multiline />
      <NumberField obj={enemy} k="hp" label="Maximum HP" />
      <NumberField obj={enemy} k="dodge" label="Dodge chance (%)" fallback={0} blank="null" min={0} max={100} />
      <NumberField obj={enemy} k="xp" label="XP reward" />
      <RangeField obj={enemy} k="damage" label="Damage" />
      <RangeField obj={enemy} k="gold" label="Gold reward" />
      <BoolField obj={enemy} k="aggressive" label="Attacks on sight" />
      <NumberField obj={enemy} k="respawn" label="Respawn delay (seconds)" />

      <Note>
        <strong className="text-foreground">Weighted loot outcomes.</strong> One entry is chosen per victory.
      </Note>
      {enemy.loot.map((l: Obj, index: number) => (
        <Group key={index} legend={`Loot outcome ${index + 1}`} onRemove={() => enemy.loot.splice(index, 1)}>
          <SelectField label="Item" value={l.item || ''} options={items} onChange={(v) => (l.item = v || null)} />
          <NumberField obj={l} k="weight" label="Loot weight" min={0.001} />
        </Group>
      ))}
      <AddButton onClick={() => enemy.loot.push({ item: null, weight: 1 })}>Add loot outcome</AddButton>

      <Note>
        <strong className="text-foreground">Creature dialogue.</strong> One line is chosen at random. Battle lines roll before
        each enemy attack; defeat lines play only on a kill. Captive lines play when looking into an occupied cage.
      </Note>
      <NumberField obj={enemy} k="battle_cry_chance" label="Chance of battle line per attack (%)" />
      <LinesField obj={enemy} k="battle_cries" label="Battle cries / actions" />
      <LinesField obj={enemy} k="defeat_messages" label="Defeat words / actions" />
      <BoolField obj={enemy} k="capturable" label="Can be knocked out and captured" />
      <NumberField obj={enemy} k="capture_health" label="Must be at or below this HP percentage" fallback={35} min={0} max={100} />
      <NumberField obj={enemy} k="capture_resistance" label="Capture resistance (%)" fallback={0} min={0} max={100} />
      <TextField obj={enemy} k="captive_description" label="Description when looking into its cage" multiline />
      <LinesField obj={enemy} k="captive_actions" label="Possible captive words / actions" />

      <NumberField obj={enemy} k="captive_value" label="Sale value per captured creature (gold; 0 = not bought)" />
      <Note>
        <strong className="text-foreground">Hidden conversation triggers.</strong> Players use SAY &lt;phrase&gt; TO &lt;creature
        or cage number&gt;. Matching ignores capitalization and repeated spaces, but otherwise needs the complete phrase. Rules
        are not listed to players. Caged creatures can respond but cannot attack.
      </Note>
      {(enemy.conversations || []).map((rule: Obj, index: number) => (
        <Group key={index} legend={`Secret phrase ${index + 1}`} removeLabel="Remove phrase" onRemove={() => enemy.conversations.splice(index, 1)}>
          <TextField obj={rule} k="phrase" label="Phrase" />
          <BoolField obj={rule} k="attack" label="Start attacking after this response" />
          <TextField obj={rule} k="response" label="Response / action" multiline />
        </Group>
      ))}
      <AddButton
        onClick={() => {
          enemy.conversations = enemy.conversations || []
          enemy.conversations.push({ phrase: '', response: '', attack: false })
        }}
      >
        Add secret phrase
      </AddButton>
      <TextField obj={enemy} k="conversation_default" label="Default response for unknown phrases (optional)" multiline />
    </>
  )
}

const itemKinds = ['weapon', 'armor', 'consumable', 'light', 'loot', 'key', 'cage', 'chest']
const itemStats = ['damage', 'armor', 'heal', 'capacity']

export function ItemEditor({ item }: { item: Obj }) {
  return (
    <>
      <SelectField
        label="Item type"
        value={item.kind}
        options={itemKinds.map((v): Option => [v, v])}
        onChange={(v) => {
          item.kind = v
          for (const k of itemStats) delete item[k]
          const key = ({ weapon: 'damage', armor: 'armor', consumable: 'heal', cage: 'capacity', chest: 'capacity' } as Record<string, string>)[v]
          if (key) item[key] = v === 'chest' ? 30 : v === 'cage' ? 5 : 1
        }}
      />
      <NumberField obj={item} k="price" label="Shop price (gold)" />
      <TextField obj={item} k="description" label="Description" multiline />
      {itemStats.filter((k) => k in item).map((k) => (
        <NumberField key={k} obj={item} k={k} label={k[0].toUpperCase() + k.slice(1)} />
      ))}
      <BoolField obj={item} k="protected" label="Protected from death item loss" />
      <SelectField
        label="Rarity"
        value={item.rarity || ''}
        options={[['', 'Normal'], ['uncommon', 'Uncommon']]}
        onChange={(v) => { if (v) item.rarity = v; else delete item.rarity }}
      />
    </>
  )
}

const settingNames: Record<string, string> = {
  attack_interval: 'Seconds between attacks',
  hit_chance: 'Chance to hit',
  flee_chance: 'Chance to flee',
  gold_loss: 'Gold fraction lost on death',
  item_loss_chance: 'Chance to lose one bag item on death',
  bag_capacity: 'Bag capacity',
  hp_per_level: 'HP gained per level',
  damage_per_level: 'Damage gained per level',
}

export function SettingsEditor({ settings }: { settings: Obj }) {
  return (
    <>
      {Object.entries(settingNames).map(([k, label]) => (
        <NumberField key={k} obj={settings} k={k} label={label} />
      ))}
      <ListInput obj={settings} k="level_xp" label="Total XP thresholds for each level (start with 0)" />
    </>
  )
}

export function RaceEditor({ race }: { race: Obj }) {
  return <NumberField obj={race} k="hp_bonus" label="Bonus HP" />
}

export function ClassEditor({ cls }: { cls: Obj }) {
  return (
    <>
      <NumberField obj={cls} k="hp" label="Base maximum HP" />
      <RangeField obj={cls} k="damage" label="Base damage" />
      <Note>Skills: choose this class in each skill’s eligibility settings under Skills. New characters can select this class.</Note>
    </>
  )
}

function Eligibility({ skill, k, label, group }: { skill: Obj; k: string; label: string; group: 'classes' | 'races' }) {
  const { world, touch } = useEditor()
  const anyone = skill[k] === null
  return (
    <FormField label={label} wide>
      <label className="flex items-center gap-2 text-sm">
        <Checkbox checked={anyone} onCheckedChange={(checked) => { skill[k] = checked === true ? null : []; touch() }} />
        Any {group === 'classes' ? 'class' : 'race'}
      </label>
      {!anyone && (
        <CheckList
          label={label}
          hideLabel
          choices={sortedEntries(world[group]).map(([id, v]): Option => [id, v.name])}
          isChecked={(id) => (skill[k] || []).includes(id)}
          onToggle={(id, checked) => {
            skill[k] = checked ? [...(skill[k] || []), id] : (skill[k] || []).filter((x: string) => x !== id)
          }}
        />
      )}
    </FormField>
  )
}

export function SkillEditor({ skill, id }: { skill: Obj; id: string }) {
  const effect = skill.effect || 'damage'
  return (
    <>
      <TextField obj={skill} k="description" label="Description" multiline />
      <SelectField
        label="Effect type"
        value={effect}
        options={[['damage', 'Damage attack'], ['heal', 'Healing'], ['knockout', 'Knockout / capture'], ['enchant', 'Enchanting (trainable)'], ['sharpen', 'Sharpening']]}
        onChange={(v) => {
          skill.effect = v
          if (v === 'heal') skill.heal = skill.heal || 20
          if (v === 'knockout') skill.chance = skill.chance ?? 70
        }}
      />
      <NumberField obj={skill} k="unlock_level" label="Unlock level" />
      <NumberField obj={skill} k="cooldown" label="Cooldown (seconds)" />
      {effect === 'heal' && <NumberField obj={skill} k="heal" label="HP restored" />}
      {effect === 'knockout' && <NumberField obj={skill} k="chance" label="Base success chance (%)" />}
      {!['heal', 'knockout', 'enchant', 'sharpen'].includes(effect) && <NumberField obj={skill} k="multiplier" label="Damage multiplier" />}
      <Eligibility skill={skill} k="allowed_classes" label="Classes allowed to unlock this skill" group="classes" />
      <Eligibility skill={skill} k="allowed_races" label="Races allowed to unlock this skill" group="races" />
      <Note>
        <strong className="text-foreground">Player command:</strong> CAST {skill.name} (or CAST {id}). Damage skills need a fight
        unless May initiate combat is enabled. Enchanting and Sharpening use the right-hand weapon outside combat; their balance
        controls are in Crafting &amp; balance. Healing also works outside combat.
      </Note>
    </>
  )
}
