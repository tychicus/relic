import { TerminalBox } from '@/components/Terminal'
import { ActionButton, ItemRow, countItems, type Send } from './ItemRow'
import type { Snapshot } from './types'

const slotNames: Record<string, string> = { weapon: 'Right hand', left_hand: 'Left hand', armor: 'Body' }

export function SidePanels({ data, send }: { data: Snapshot; send: Send }) {
  const p = data.player!
  const skills = data.player_skills ?? []
  return (
    <div className="grid min-w-0 content-start gap-6">
      <TerminalBox title="Skills" muted>
        {skills.map((s) => (
          <p key={s.id} className="my-0.5 text-sm" title={s.description || ''}>
            <span className={s.unlocked ? 'text-foreground' : 'text-muted-foreground'}>{s.unlocked ? '✓' : '·'} {s.name}</span>
            {s.effect === 'enchant' && p.enchanting?.[s.id] && <span className="block text-xs text-muted-foreground">
              Skill level {p.enchanting[s.id].level} · {p.enchanting[s.id].next_xp === null ? 'Maximum level' : `${p.enchanting[s.id].level_xp}/${p.enchanting[s.id].next_xp} XP to next level`}
              <br />{p.enchanting[s.id].chance}% success · +{p.enchanting[s.id].bonus} damage/armor · {Math.round(p.enchanting[s.id].duration / 60 * 10) / 10} minutes
            </span>}
            {!s.unlocked && <span className="text-muted-foreground"> (level {s.unlock_level ?? 1})</span>}
          </p>
        ))}
        {!skills.length && <p className="text-sm text-muted-foreground">No skills assigned.</p>}
      </TerminalBox>

      <TerminalBox title="Equipment" muted>
        {Object.entries(p.equipment).map(([slot, id]) => (
          <ItemRow key={slot} id={id} count={1} mode="equipment" data={data} send={send} slot={slotNames[slot] || slot}>
            <ActionButton send={send} command={`unequip ${slot}`}>Remove</ActionButton>
          </ItemRow>
        ))}
        {(['weapon', 'left_hand'] as const)
          .filter((slot) => !p.equipment[slot])
          .map((slot) => (
            <p key={slot} className="text-sm text-muted-foreground">{slotNames[slot]}: empty</p>
          ))}
      </TerminalBox>

      <TerminalBox title={`Inventory ${p.inventory.length}/${p.bag_capacity}`} muted>
        {countItems(p.inventory).map(([id, n]) => (
          <ItemRow key={id} id={id} count={n} mode="bag" data={data} send={send} />
        ))}
        {!p.inventory.length && <p className="text-sm text-muted-foreground">Your bag is empty.</p>}
      </TerminalBox>
    </div>
  )
}
