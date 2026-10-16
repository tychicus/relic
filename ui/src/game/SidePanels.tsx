import { TerminalBox } from '@/components/Terminal'
import { ActionButton, ItemRow, countItems, type Send } from './ItemRow'
import type { Snapshot } from './types'

const slotNames: Record<string, string> = { helmet: 'Helmet', armor: 'Chest', pants: 'Pants', arms: 'Arms', weapon: 'Right hand', left_hand: 'Left hand / shield' }

export function SidePanels({ data, send }: { data: Snapshot; send: Send }) {
  const p = data.player!
  const skills = data.player_skills ?? []
  return (
    <div className="grid min-w-0 content-start gap-6">
      <TerminalBox title="Skills" muted>
        {!!p.max_mana && <p className="mb-3 text-sm text-story">Mana mastery {p.mana_progress?.level || 1} · {p.mana_progress?.next_xp === null ? 'Maximum level' : `${p.mana_progress?.level_xp || 0}/${p.mana_progress?.next_xp || 100} XP to next level`}<br />Recover mana between fights; rest at an inn to refill it.</p>}
        {skills.filter(s => !data.learning_enabled || s.unlocked).map((s) => (
          <p key={s.id} className="my-0.5 text-sm" title={s.description || ''}>
            <span className={s.unlocked ? 'text-foreground' : 'text-muted-foreground'}>{s.unlocked ? '✓' : '·'} {s.name}</span>
            {data.learning_enabled && <span className="text-muted-foreground"> · rank {s.rank}/{s.max_rank}{s.passive ? ' · automatic attacks' : ''}</span>}
            {!!s.mana_cost && <span className="text-muted-foreground"> · {s.mana_cost} mana</span>}
            {s.magic_progress && <span className="block text-xs text-muted-foreground">
              Spell level {s.magic_progress.level} · {s.magic_progress.next_xp === null ? 'Maximum level' : `${s.magic_progress.level_xp}/${s.magic_progress.next_xp} XP to next level`}
              <br />{s.magic_progress.power} {s.effect === 'heal' ? 'healing HP' : s.effect === 'knockout' ? '% success chance' : 'damage'}
              {s.magic_progress.effect_damage !== null && ` · ${s.magic_progress.effect_damage} effect damage/pulse`}
            </span>}
            {s.effect === 'enchant' && p.enchanting?.[s.id] && <span className="block text-xs text-muted-foreground">
              Skill level {p.enchanting[s.id].level} · {p.enchanting[s.id].next_xp === null ? 'Maximum level' : `${p.enchanting[s.id].level_xp}/${p.enchanting[s.id].next_xp} XP to next level`}
              <br />{p.enchanting[s.id].chance}% success · +{p.enchanting[s.id].bonus} damage/armor · {Math.round(p.enchanting[s.id].duration / 60 * 10) / 10} minutes
            </span>}
            <ActionButton send={send} command={`help ${s.id}`} aria-label={`Help for ${s.name}`} className="ml-1">Help</ActionButton>
            {!s.unlocked && <span className="text-muted-foreground"> (level {s.unlock_level ?? 1})</span>}
          </p>
        ))}
        {!skills.length && <p className="text-sm text-muted-foreground">No skills assigned.</p>}
      </TerminalBox>

      {data.learning_enabled && <TerminalBox title={`Learn abilities · ${p.ability_points || 0} points`} muted>
        <p className="mb-3 text-sm text-story">Choose new abilities or improve their ranks. Earn {data.learning_schedule || 'points by gaining character levels.'} Save them for later unlocks. Spell mastery also grows through practice.</p>
        <details>
          <summary className="cursor-pointer text-sm text-gold">View learning choices</summary>
          <div className="mt-3 grid gap-3">
            {[...skills].sort((a,b) => (a.learn_level || 1) - (b.learn_level || 1)).map(s => {
              const capped = (s.rank || 0) >= (s.max_rank || 5)
              const locked = p.level < (s.learn_level || 1)
              return <div key={s.id} className="border-t border-border pt-2 text-sm">
                <p>{s.name} · rank {s.rank || 0}/{s.max_rank || 5}</p>
                <p className="text-xs text-muted-foreground">{s.description}</p>
                <p className="my-1 text-xs text-muted-foreground">Class power {Math.round((s.affinity?.power || 1) * 100)}% · mana cost ×{s.affinity?.mana || 1} · practice ×{s.affinity?.practice || 1}</p>
                <ActionButton send={send} command={`help ${s.id}`} aria-label={`Learn about ${s.name}`} className="mr-1">Help</ActionButton>
                <ActionButton send={send} command={`learn ${s.id}`} disabled={!!p.combat || capped || locked || (p.ability_points || 0) < (s.learn_cost || 1)}>
                  {capped ? 'Maximum rank' : `${s.rank ? 'Improve' : 'Learn'} · ${s.learn_cost || 1} point(s)${locked ? ` · level ${s.learn_level}` : ''}`}
                </ActionButton>
              </div>
            })}
          </div>
        </details>
        {!!p.combat && <p className="mt-2 text-sm text-muted-foreground">Finish combat before learning.</p>}
      </TerminalBox>}

      <TerminalBox title="Equipment" muted>
        <p className="text-sm text-story">Total protection: {p.defense || 0}</p>
        {Object.entries(p.equipment).map(([slot, id]) => (
          <ItemRow key={slot} id={id} count={1} mode="equipment" data={data} send={send} slot={slotNames[slot] || slot}>
            <ActionButton send={send} command={`unequip ${slot}`}>Remove</ActionButton>
          </ItemRow>
        ))}
        {Object.keys(slotNames)
          .filter((slot) => !p.equipment[slot])
          .map((slot) => (
              <p key={slot} className="text-sm text-muted-foreground">{slotNames[slot]}: {slot === 'left_hand' && (data.items[p.equipment.weapon]?.hands || 1) === 2 ? 'occupied by two-handed weapon' : slot === 'pants' ? 'boxers' : 'nothing'}</p>
          ))}
      </TerminalBox>

      <TerminalBox title={`Inventory ${p.inventory.length}/${p.bag_capacity}`} muted>
        <p className="mb-2 text-sm text-story">Weight: {(p.carried_weight || 0).toFixed(1)} / {p.carry_capacity || 0} lb{p.weight_enabled ? '' : ' · limit disabled'}<br /><span className="text-xs">Includes worn equipment and container contents. Capacity grows with character level.</span></p>
        {countItems(p.inventory).map(([id, n]) => (
          <ItemRow key={id} id={id} count={n} mode="bag" data={data} send={send} />
        ))}
        {!p.inventory.length && <p className="text-sm text-muted-foreground">Your bag is empty.</p>}
      </TerminalBox>
    </div>
  )
}
