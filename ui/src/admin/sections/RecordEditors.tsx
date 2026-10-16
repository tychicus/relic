import { Checkbox } from '@/components/ui/checkbox'
import { Button } from '@/components/ui/button'
import { sortedEntries, useEditor } from '../context'
import { MagicProgressionEditor } from '../MagicProgressionEditor'
import {
  AddButton, BoolField, CheckList, Disclosure, FormField, Group, LinesField, Note, NumberField, NumberInput,
  RangeField, SelectField, TextField, type Option,
} from '../fields'

type Obj = Record<string, any>

export function EmoteEditor({ emote }: { emote: Obj }) {
  const preview = (message: string) => (message || '').replace(/\{(actor|target)\}/g, (_, key) => key === 'actor' ? 'Traveler' : 'Tamsin')
  return (
    <>
      <BoolField obj={emote} k="enabled" label="Enabled for players" />
      <TextField obj={emote} k="command" label="Command (one lowercase word)" maxLength={40} />
      <LinesField obj={emote} k="aliases" label="Aliases (one lowercase word per line; up to 10)" />
      <Note>Commands and aliases must be unique and cannot replace game commands, skills or help topics. New entries begin with a gesture_ command you can rename.</Note>
      <TextField obj={emote} k="description" label="Description shown in HELP EMOTES" maxLength={600} multiline />
      <TextField obj={emote} k="message" label="Message without a target" maxLength={600} multiline />
      <TextField obj={emote} k="target_message" label="Message with a target (optional)" maxLength={600} multiline />
      <Note>Use {'{actor}'} for the character’s name and {'{target}'} for a visible target’s name. Leave the targeted message blank to disallow targets. Disable an entry to remove it from player commands and help.</Note>
      <Note>
        <strong className="text-foreground">Message preview</strong>
        <span className="mt-1 block break-words whitespace-pre-line">{preview(emote.message)}</span>
        {emote.target_message && <span className="mt-1 block break-words whitespace-pre-line">{preview(emote.target_message)}</span>}
      </Note>
    </>
  )
}

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
          if (!['weapon', 'armor'].includes(v)) { item.magic = false; delete item.magic_levels }
          for (const k of itemStats) delete item[k]
          const key = ({ weapon: 'damage', armor: 'armor', consumable: 'heal', cage: 'capacity', chest: 'capacity' } as Record<string, string>)[v]
          if (key) item[key] = v === 'chest' ? 30 : v === 'cage' ? 5 : 1
        }}
      />
      <NumberField obj={item} k="price" label="Shop price (gold)" />
      <TextField obj={item} k="description" label="Description" multiline />
      {itemStats.filter((k) => k in item).map((k) => (
        <NumberField key={k} obj={item} k={k} label={k[0].toUpperCase() + k.slice(1) + (item.magic && ['damage', 'armor'].includes(k) ? ' when magic progression is off' : '')} />
      ))}
      <BoolField obj={item} k="protected" label="Protected from death item loss" />
      {['weapon', 'armor'].includes(item.kind) && <MagicProgressionEditor spec={item} equipment />}
      <SelectField
        label="Rarity"
        value={item.rarity || ''}
        options={[['', 'Normal'], ['uncommon', 'Uncommon'], ['legendary', 'Legendary']]}
        onChange={(v) => { if (v) item.rarity = v; else delete item.rarity }}
      />
    </>
  )
}

const settingNames: Record<string, string> = {
  attack_interval: 'Seconds between shared combat pulses (each fighter recovers for two pulses)',
  hit_chance: 'Chance to hit',
  flee_chance: 'Chance to flee',
  gold_loss: 'Legacy gold loss (only when recoverable player bodies are disabled)',
  item_loss_chance: 'Legacy bag item loss chance (only when recoverable player bodies are disabled)',
  bag_capacity: 'Bag capacity',
  hp_per_level: 'HP gained per level',
  damage_per_level: 'Damage gained per level',
}

export function SettingsEditor({ settings }: { settings: Obj }) {
  const { world, touch } = useEditor()
  const xp: number[] = settings.level_xp
  const unreachable = sortedEntries(world.skills).filter(([, s]) => (s.unlock_level ?? 1) > xp.length)
  return (
    <>
      {Object.entries(settingNames).map(([k, label]) => (
        <NumberField key={k} obj={settings} k={k} label={label} />
      ))}
      <NumberField obj={world.revision} k="action_recovery" label="Recovery between manual combat skills (seconds; 0 disables)" fallback={2} min={0} max={60} />
      <NumberField obj={world.revision} k="potion_recovery" label="Recovery between healing potions (seconds; 0 disables)" fallback={10} min={0} max={3600} />
      <BoolField obj={world.revision} k="player_bodies" label="Leave recoverable player bodies on death" />
      <NumberField obj={world.revision} k="player_body_seconds" label="Player body lifetime (seconds; 900 = 15 minutes)" fallback={900} min={1} max={86400} />
      <Note>Bodies hold carried gold and all carried or equipped items, including containers. Their deadlines continue while the game is closed. Banked gold stays safe. Changing this duration affects future deaths.</Note>
      <Note>Skills keep their own cooldowns too. Automatic attacks continue during manual skill recovery. New timing settings apply to the next use; current timers finish normally.</Note>
      <BoolField obj={world.revision} k="enemy_heal_enabled" label="Wounded enemies heal outside combat" />
      <NumberField obj={world.revision} k="enemy_heal_delay" label="Enemy healing delay after combat (seconds)" fallback={20} min={0} max={86400} />
      <NumberField obj={world.revision} k="enemy_heal_interval" label="Seconds between enemy healing installments" fallback={5} min={1} max={3600} />
      <NumberField obj={world.revision} k="enemy_heal_percent" label="Enemy maximum HP recovered per installment (%)" fallback={2} min={0} max={100} />
      <Note>Healing pauses for all engaged or unconscious creatures, never revives defeated enemies and grants no offline recovery. Creatures can override these global settings in their own configuration.</Note>
      <Disclosure title={`Character progression · ${xp.length} levels`} defaultOpen>
        <p className="mb-2 text-sm text-muted-foreground">Total lifetime XP required for each character level. Thresholds must increase. Supports up to 100 levels.</p>
        {!!unreachable.length && <p role="alert" className="mb-2 text-sm text-destructive">Unreachable skills: {unreachable.map(([, s]) => `${s.name} (level ${s.unlock_level})`).join(', ')}. Add levels or lower their unlock requirements before saving.</p>}
        <div className="max-h-96 overflow-y-auto rounded border p-3">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {xp.map((value, index) => <FormField key={index} label={`Level ${index + 1} total XP`}>
              <NumberInput aria-label={`Character level ${index + 1} total XP`} value={value} min={0} max={10000000} step={1} disabled={index === 0} onValue={(v) => { xp[index] = v ?? 0; touch() }} />
            </FormField>)}
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button type="button" variant="outline" disabled={xp.length >= 100 || xp[xp.length - 1] >= 10000000} onClick={() => {
            const last = xp[xp.length - 1]
            xp.push(Math.min(10000000, last + Math.max(30, last - (xp[xp.length - 2] ?? 0))))
            touch()
          }}>Add level</Button>
          <Button type="button" variant="outline" disabled={xp.length <= 1} onClick={() => { xp.pop(); touch() }}>Remove last level</Button>
        </div>
      </Disclosure>
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
  const { world } = useEditor()
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
          if (v !== effect) { skill.magic = false; delete skill.magic_levels }
          if (v === 'heal') skill.heal = skill.heal || 20
          if (v === 'knockout') skill.chance = skill.chance ?? 70
        }}
      />
      <NumberField obj={skill} k="unlock_level" label="Unlock level" />
      {(skill.unlock_level ?? 1) > world.settings.level_xp.length && <Note>This skill cannot unlock: character progression currently ends at level {world.settings.level_xp.length}. Extend the XP table in Combat &amp; progression or lower this requirement.</Note>}
      <NumberField obj={skill} k="cooldown" label="Cooldown (seconds)" />
      {!skill.magic && effect === 'heal' && <NumberField obj={skill} k="heal" label="HP restored" />}
      {!skill.magic && effect === 'knockout' && <NumberField obj={skill} k="chance" label="Base success chance (%)" />}
      {!skill.magic && effect === 'damage' && <NumberField obj={skill} k="multiplier" label="Damage multiplier" />}
      {['damage', 'heal', 'knockout'].includes(effect) && <MagicProgressionEditor spec={skill} />}
      <Eligibility skill={skill} k="allowed_classes" label="Classes allowed to unlock this skill" group="classes" />
      <Eligibility skill={skill} k="allowed_races" label="Races allowed to unlock this skill" group="races" />
      <Note>
        <strong className="text-foreground">Player command:</strong> CAST {skill.name} [creature] (or CAST {id} [creature]). Damage skills need a fight
        unless May initiate combat is enabled. Enchanting targets held weapons or worn/held armor; Sharpening uses the right-hand
        weapon. Their balance controls are in Crafting &amp; balance. Healing also works outside combat.
      </Note>
    </>
  )
}
