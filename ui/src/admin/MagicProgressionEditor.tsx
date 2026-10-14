import { Button } from '@/components/ui/button'
import { useEditor } from './context'
import { Disclosure, Note, NumberField, NumberInput, SelectField } from './fields'

type Obj = Record<string, any>

export function MagicProgressionEditor({ spec, equipment = false }: { spec: Obj; equipment?: boolean }) {
  const { world, touch } = useEditor()
  const effect = equipment ? spec.kind : spec.effect || 'damage'
  const powerLabel = effect === 'armor' ? 'Armor' : effect === 'heal' ? 'Healing HP' : effect === 'knockout' ? 'Success chance (%)' : 'Damage'
  const dot = !equipment && effect === 'damage' && (spec.status_effects || []).some((s: Obj) => world.status_effects?.[s.effect]?.kind === 'damage')
  const levels: Obj[] = spec.magic_levels || []
  return (
    <Disclosure title={equipment ? 'Magic item levels' : 'Spell levels'} defaultOpen={!!spec.magic}>
      <div className="grid gap-4 md:grid-cols-2">
        <SelectField
          label={equipment ? 'Magical equipment progression' : 'Spell progression'}
          value={spec.magic ? 'on' : 'off'}
          options={[["off", "Off"], ["on", equipment ? "Each individual item earns XP" : "This spell earns its own XP"]]}
          onChange={(value) => {
            spec.magic = value === 'on'
            if (spec.magic && !levels.length) {
              const base = equipment ? Math.max(1, Math.round((spec[spec.kind === 'weapon' ? 'damage' : 'armor'] || 2) / 2)) : effect === 'heal' ? Math.max(1, Math.round((spec.heal || 20) / 2)) : effect === 'knockout' ? Math.round((spec.chance ?? 70) / 2) : 6
              const step = equipment ? 1 : 2
              let xp = 0
              spec.magic_levels = Array.from({ length: 100 }, (_, index) => {
                const row: Obj = { xp, power: Math.min(effect === 'knockout' ? 100 : 10000, base + index * step) }
                if (dot) row.effect_damage = 1 + Math.floor(index / 5)
                xp += 100 + index * 50
                return row
              })
              spec.magic_xp_per_use = 1
            }
          }}
        />
        {spec.magic && <>
          <NumberField obj={spec} k="magic_xp_per_use" label="XP earned per valid use" fallback={1} min={1} max={10000} step={1} />
          <Note>
            {equipment ? 'Each copy keeps its own level when equipped, dropped or stored. Weapons practice on attacks, including misses; armor practices when worn or used as a shield and struck.' : 'Each spell starts at level 1 and learns separately. Valid casts earn XP even when the target dodges; blocked commands and cooldown retries earn none.'}
            {' '}Total XP is the lifetime threshold for reaching that level. Defaults require 100 practice XP for level 2 and 252,450 for level 100. Meaningful challenges award extra practice, controlled in Mana &amp; mastery.
            {!equipment && effect === 'damage' && ' Damage below is the base spell damage before class penalties and chosen-rank bonuses; weapon damage is not added.'}
          </Note>
          <div className="max-h-[32rem] overflow-auto md:col-span-2">
            <table className="w-full min-w-[340px] text-left text-sm">
              <thead><tr className="border-b"><th className="p-2">Level</th><th className="p-2">Total XP to reach</th><th className="p-2">{powerLabel}</th>{!equipment && <th className="p-2">Mana cost</th>}{dot && <th className="p-2">Effect damage / pulse</th>}</tr></thead>
              <tbody>{levels.map((row, index) => (
                <tr key={index} className="border-b">
                  <th className="p-2 font-medium">{index + 1}</th>
                  <td className="p-2"><NumberInput aria-label={`Level ${index + 1} total XP`} value={row.xp} min={0} max={1000000000} step={1} disabled={index === 0} onValue={(v) => { row.xp = v ?? 0; touch() }} /></td>
                  <td className="p-2"><NumberInput aria-label={`Level ${index + 1} ${powerLabel}`} value={row.power} min={effect === 'heal' ? 1 : 0} max={effect === 'knockout' ? 100 : 10000} step={1} onValue={(v) => { row.power = v ?? 0; touch() }} /></td>
                  {!equipment && <td className="p-2"><NumberInput aria-label={`Level ${index + 1} mana cost`} value={row.mana_cost} fallback={spec.mana_cost || 0} min={0} max={10000} step={1} onValue={(v) => { row.mana_cost = v ?? 0; touch() }} /></td>}
                  {dot && <td className="p-2"><NumberInput aria-label={`Level ${index + 1} effect damage per pulse`} value={row.effect_damage} blank="delete" placeholder="Effect default" min={0} max={1000} step={1} onValue={(v) => { if (v === undefined) delete row.effect_damage; else row.effect_damage = v; touch() }} /></td>}
                </tr>
              ))}</tbody>
            </table>
          </div>
          <div className="flex flex-wrap gap-2 md:col-span-2">
            <Button type="button" variant="outline" disabled={levels.length >= 100} onClick={() => {
              const last = levels[levels.length - 1]
              levels.push({ ...last, xp: Math.min(1000000000, last.xp + 100 + (levels.length - 1) * 50) })
              touch()
            }}>Add level</Button>
            <Button type="button" variant="outline" disabled={levels.length <= 1} onClick={() => { levels.pop(); touch() }}>Remove last level</Button>
          </div>
          <Note>Changes apply after Save world changes. Existing XP is preserved; changing thresholds can change an existing spell’s or item’s level.</Note>
        </>}
      </div>
    </Disclosure>
  )
}
