import { TerminalBox } from '@/components/Terminal'
import { ActionButton, ItemRow, countItems, type Send } from './ItemRow'
import type { Skill, Snapshot } from './types'

const slotNames: Record<string, string> = { helmet: 'Helmet', armor: 'Chest', pants: 'Pants', arms: 'Arms', weapon: 'Right hand', left_hand: 'Left hand / shield' }


function SkillFacts({ skill, expanded = false }: { skill: Skill; expanded?: boolean }) {
  if (!skill.details) return null
  return <div className="my-1 text-xs text-muted-foreground">
    <p className="text-story">{skill.details.summary}</p>
    <p>{skill.details.lines[1]}</p>
    <details open={expanded || undefined}>
      <summary className="cursor-pointer text-gold">Timing, targets &amp; effects</summary>
      <div className="mt-1 grid gap-1">{skill.details.lines.slice(2).map((line, i) => <p key={i}>{line}</p>)}</div>
    </details>
    {skill.recovery_lines?.map(line => <p key={line}>{line}</p>)}
  </div>
}

export function SidePanels({ data, send }: { data: Snapshot; send: Send }) {
  const p = data.player!
  const skills = data.player_skills ?? []
  return (
    <div className="grid min-w-0 content-start gap-6">
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

      <TerminalBox title={`Inventory · ${p.inventory.length} items`} muted>
        {countItems(p.inventory).map(([id, n]) => (
          <ItemRow key={id} id={id} count={n} mode="bag" data={data} send={send} />
        ))}
        {!p.inventory.length && <p className="text-sm text-muted-foreground">Your bag is empty.</p>}
      </TerminalBox>

      <details className="min-w-0 rounded-md border border-border">
        <summary className="cursor-pointer rounded-md px-4 py-3 text-sm text-primary hover:bg-primary/5 focus-visible:outline-2 focus-visible:outline-primary">Skills</summary>
        <div className="px-4 pb-4">
          {p.ward && <p className="mb-2 text-sm text-story" role="status">Ward active: {p.ward.power}% less incoming attack damage · {p.ward.remaining}s remaining. Status damage is unaffected.</p>}
          {!!p.max_mana && <p className="mb-3 text-sm text-story">Mana mastery {p.mana_progress?.level || 1} · {p.mana_progress?.next_xp === null ? 'Maximum level' : `${p.mana_progress?.level_xp || 0}/${p.mana_progress?.next_xp || 100} XP to next level`}<br />Recover mana between fights; rest at an inn to refill it.</p>}
          {skills.filter(s => !data.learning_enabled || s.unlocked).map((s) => (
            <div key={s.id} className="my-2 border-b border-border pb-2 text-sm">
              <span className={s.unlocked ? 'text-foreground' : 'text-muted-foreground'}>{s.unlocked ? '✓' : '·'} {s.name}</span>
              {data.learning_enabled && <span className="text-muted-foreground"> · rank {s.rank}/{s.max_rank}{s.passive ? ' · automatic attacks' : ''}</span>}
              <SkillFacts skill={s} />
              {s.magic_progress && <span className="block text-xs text-muted-foreground">
                Spell mastery {s.magic_progress.level} · {s.magic_progress.next_xp === null ? 'Maximum level' : `${s.magic_progress.level_xp}/${s.magic_progress.next_xp} XP to next level`}
              </span>}
              {s.effect === 'enchant' && p.enchanting?.[s.id] && <span className="block text-xs text-muted-foreground">
                Crafting mastery {p.enchanting[s.id].level} · {p.enchanting[s.id].next_xp === null ? 'Maximum level' : `${p.enchanting[s.id].level_xp}/${p.enchanting[s.id].next_xp} XP to next level`}
              </span>}
              {!s.unlocked && <span className="text-muted-foreground"> (level {s.unlock_level ?? 1})</span>}
            </div>
          ))}
          {!skills.length && <p className="text-sm text-muted-foreground">No skills assigned.</p>}
        </div>
      </details>

      {data.learning_enabled && <TerminalBox title={`Learn abilities · ${p.ability_points || 0} points`} muted>
        <p className="mb-3 text-sm text-story">Choose new abilities or improve their ranks. Earn {data.learning_schedule || 'points by gaining character levels.'} Save them for later unlocks. Spell mastery also grows through practice.</p>
        <details>
          <summary className="cursor-pointer text-sm text-gold">View learning choices</summary>
          <div className="mt-3 grid gap-3">
            {[...skills].sort((a,b) => (a.learn_level || 1) - (b.learn_level || 1)).map(s => {
              const capped = (s.rank || 0) >= (s.max_rank || 5)
              const locked = p.level < (s.learn_level || 1)
              return <div key={s.id} data-skill={s.id} className="border-t border-border pt-2 text-sm">
                <p>{s.name} · rank {s.rank || 0}/{s.max_rank || 5}</p>
                <SkillFacts skill={s} />
                <p className="my-1 text-xs text-muted-foreground">Class/race power {Math.round((s.affinity?.power ?? 1) * 100)}% · mana cost ×{s.affinity?.mana ?? 1} · spell/mana XP ×{s.affinity?.practice ?? 1}</p>
                {s.next_rank && <div className="my-2 grid gap-1 border-l-2 border-gold pl-2 text-xs" aria-label={`Next rank for ${s.name}`}>
                  <p className="text-gold">Rank {s.next_rank.rank} · {s.next_rank.cost} point(s) · character level {s.next_rank.required_level}</p>
                  {s.next_rank.lines.map((line, i) => <p key={i}>{line}</p>)}
                </div>}
                <ActionButton send={send} command={`learn ${s.id}`} disabled={!!p.combat || capped || locked || (p.ability_points || 0) < (s.learn_cost || 1)}>
                  {capped ? 'Maximum rank' : `${s.rank ? 'Improve' : 'Learn'} · ${s.learn_cost || 1} point(s)${locked ? ` · level ${s.learn_level}` : ''}`}
                </ActionButton>
              </div>
            })}
          </div>
        </details>
        {!!p.combat && <p className="mt-2 text-sm text-muted-foreground">Finish combat before learning.</p>}
      </TerminalBox>}

    </div>
  )
}
