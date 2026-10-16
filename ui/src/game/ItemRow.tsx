import type { ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { Item, Snapshot } from './types'

export type Send = (command: string) => void

function detail(i: Item, data: Snapshot) {
  if (i.kind === 'weapon' || i.kind === 'armor') {
    const base = i.kind === 'weapon' ? `Damage ${i.base_damage ?? i.damage}` : `Armor ${i.base_armor ?? i.armor}`
    return base + (i.enchanted ? ` (+${i.enchantment_bonus})` : '') + (i.sharpen_bonus ? ` · Sharpened +${i.sharpen_bonus}` : '')
  }
  if (i.recall) {
    const rules = data.recall_rules
    const level = data.player?.level ?? 1
    if (!rules) return 'Returns to town outside combat'
    if (level >= rules.disabled_from) return `Unusable at level ${rules.disabled_from} or above`
    const usage = level < rules.reusable_below ? `Reusable until level ${rules.reusable_below}` : 'Single-use'
    return `${usage} · Returns to town · Stops at level ${rules.disabled_from}`
  }
  if (i.kind === 'consumable') return `Restores ${i.heal} HP`
  if (i.kind === 'light') return 'Lights dark rooms'
  if (i.kind === 'chest') return `Storage ${i.stored_count ?? 0} / ${i.capacity ?? 30}`
  if (i.kind === 'cage') return `Capacity ${i.capacity ?? 5} · one creature type`
  if (i.kind === 'captive') return 'PUT this creature IN CAGE <number>'
  if (i.kind === 'key') return 'Consumed by its matching lock'
  return `Sell for ${Math.floor(i.price / 2)} gold`
}

export function ActionButton({ command, send, children, className, ...rest }: { command: string; send: Send; children: ReactNode } & React.ComponentProps<typeof Button>) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="xs"
      onClick={() => send(command)}
      className={cn('rounded-sm border border-border font-normal hover:border-primary hover:bg-transparent hover:text-primary', className)}
      {...rest}
    >
      {children}
    </Button>
  )
}

export function countItems(ids: string[]) {
  const counts: Record<string, number> = {}
  for (const id of ids) counts[id] = (counts[id] || 0) + 1
  return Object.entries(counts)
}

interface Props {
  id: string
  count: number
  mode: 'shop' | 'ground' | 'equipment' | 'bag'
  data: Snapshot
  send: Send
  slot?: string
  children?: ReactNode
}

export function ItemRow({ id, count, mode, data, send, slot, children }: Props) {
  const i = data.items[id]
  const gear = ['weapon', 'armor'].includes(i.kind)
  const label = i.name + (count > 1 ? ` (x${count})` : '')
  let actions: ReactNode
  if (mode === 'shop') actions = <ActionButton send={send} command={`buy ${id}`}>{i.price} gold</ActionButton>
  else if (mode === 'ground') actions = <ActionButton send={send} command={`get ${id}`}>Get</ActionButton>
  else if (mode === 'equipment') actions = <ActionButton send={send} command={`look ${id}`}>Inspect</ActionButton>
  else {
    const action = i.recall ? 'Use' : i.food ? 'Eat' : i.kind === 'consumable' ? 'Quaff' : gear ? 'Equip' : 'Look'
    const sellCage = data.room.creature_buyer && i.kind === 'cage' && i.occupied
    const sell = !sellCage && data.room.shop.length > 0 && !['key', 'captive'].includes(i.kind) && !i.occupied
    actions = (
      <>
        <ActionButton send={send} command={`${action.toLowerCase()} ${id}`} disabled={(action === 'Quaff' && (data.player?.potion_ready || 0) > data.time) || (!!i.recall && !!data.recall_rules && (data.player?.level ?? 1) >= data.recall_rules.disabled_from)}>{action}</ActionButton>
        {(i.kind === 'armor' || (i.kind === 'weapon' && (i.hands ?? 1) === 1)) && (
          <ActionButton send={send} command={`equip ${id} left`}>{i.kind === 'armor' ? 'Hold left' : 'Equip left'}</ActionButton>
        )}
        <ActionButton send={send} command={`drop ${id}`}>Drop</ActionButton>
        {sellCage && (
          <ActionButton send={send} command={`sell ${id}`}>Sell cage · {i.creature_sale_value ?? 0} gold</ActionButton>
        )}
        {sell && <ActionButton send={send} command={`sell ${id}`}>Sell</ActionButton>}
      </>
    )
  }
  return (
    <div className="my-2 flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
      {slot && <small className="basis-full text-xs text-muted-foreground">{slot}:</small>}
      <div className={cn('min-w-0 break-words', i.rarity && 'text-gold')}>
        <span className={i.enchanted ? 'text-enchanted' : i.drop_only ? 'text-gold' : undefined}>{label}</span>
        {i.drop_only && <small className="block text-xs text-gold">{i.rarity === 'legendary' ? 'Legendary find' : 'Rare find'} · Enemy drop only</small>}
        <small className="block text-xs text-muted-foreground">{detail(i, data)} · {i.weight ?? 0} lb{ i.kind === 'weapon' ? ` · ${i.hands || 1}-handed` : i.shield ? ' · shield' : i.kind === 'armor' ? ` · ${i.armor_slot === 'armor' || !i.armor_slot ? 'chest' : i.armor_slot}` : ''}</small>
        {!!i.damage_penalty && <small className="block text-xs text-destructive">Damage penalty −{i.damage_penalty} · Repair {i.repair_cost} gold</small>}
        {i.magic_progress && <small className="block text-xs text-gold">
          Magic level {i.magic_progress.level} · {i.magic_progress.next_xp === null ? 'Maximum level' : `${i.magic_progress.level_xp}/${i.magic_progress.next_xp} XP to next level`}
        </small>}
        {i.enchanted && <small className="block text-xs text-enchanted">{i.enchantment_description}</small>}
      </div>
      <div className="flex flex-wrap justify-end gap-1">
        {actions}
        {['bag', 'equipment'].includes(mode) && !!i.damage_penalty && data.room.repair_service && <ActionButton send={send} command={`repair ${id}`} disabled={!!data.player?.combat || (data.player?.gold ?? 0) < (i.repair_cost ?? 0)}>Repair · {i.repair_cost} gold</ActionButton>}
        {children}
      </div>
    </div>
  )
}
