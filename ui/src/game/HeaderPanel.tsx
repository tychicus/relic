import type { ReactNode } from 'react'
import { Heading, Rule, TerminalBox, TextMeter } from '@/components/Terminal'
import { ActionButton, ItemRow, countItems, type Send } from './ItemRow'
import type { Snapshot } from './types'

// A helmeted warrior with shield and sword, drawn in half-blocks (two pixels per character).
// Every row is the same width so the figure stays aligned when centred.
const WARRIOR = [
  '      ▄█▄    ▄ ',
  '     █▀▀▀█   █ ',
  '     ▀███▀   █ ',
  ' ▄▄█▀█████▀█ █ ',
  '████ █████ ▀▀█▀',
  ' ▀▀  ██▀██     ',
  '    ▄██ ██▄    ',
].join('\n')

export function Emblem() {
  return (
    <pre aria-hidden className="my-2 text-center text-xs leading-[1.05] text-primary">
      {WARRIOR}
    </pre>
  )
}

function Line({ children }: { children: ReactNode }) {
  return <div className="my-1.5 flex flex-wrap items-center gap-2">{children}</div>
}

function CharacterSummary({ data }: { data: Snapshot }) {
  const p = data.player!
  const xpSpan = p.next_xp ? p.next_xp - p.level_start_xp : 1
  const xpInto = p.next_xp ? p.xp - p.level_start_xp : 1
  return (
    <div className="flex flex-col items-center text-center">
      <p className="font-bold break-all">Welcome back, {p.name}!</p>
      <Emblem />
      <p className="text-muted-foreground">
        {p.race_name} {p.class_name} · Level {p.level}
      </p>
      <div className="mt-2 grid w-full max-w-72 gap-1 text-left text-sm">
        <TextMeter label="HP" value={p.hp} max={p.max_hp} text={`${p.hp}/${p.max_hp}`} tone={p.hp <= p.max_hp / 4 ? 'text-destructive' : 'text-primary'} />
        {!!p.max_mana && <TextMeter label="MP" value={p.mana || 0} max={p.max_mana} text={`${Math.floor(p.mana || 0)}/${p.max_mana}`} tone="text-story" />}
        <TextMeter label="XP" value={xpInto} max={xpSpan} text={p.next_xp ? `${p.xp}/${p.next_xp}` : `${p.xp} max`} tone="text-gold" />
        <div className="flex gap-2">
          <span className="w-6 text-muted-foreground">GP</span>
          <span className="text-gold">{p.gold} gold</span>
        </div>
      </div>
    </div>
  )
}

function Here({ data, send }: { data: Snapshot; send: Send }) {
  const { room, enemy } = data
  const effectName = (id: string) => data.status_effects[id]?.name || id
  const rows: ReactNode[] = []

  if (enemy) {
    rows.push(
      <div key="enemy" className="my-2 text-sm">
        <div className="flex flex-wrap justify-between gap-2">
          <span className="font-bold text-destructive">{enemy.name}</span>
          <span className="text-muted-foreground">{enemy.aggressive ? 'hostile · attacks on sight' : 'neutral · attacks if provoked'}</span>
        </div>
        <TextMeter label="HP" value={enemy.hp} max={enemy.max_hp} text={`${enemy.hp}/${enemy.max_hp}`} tone="text-destructive" cells={20} />
      </div>,
    )
  }
  for (const e of data.enemies ?? []) {
    rows.push(
      <Line key={`enemy-${e.id}`}>
        <span className="flex-[1_1_12rem]">
          <span className={e.target ? 'text-destructive' : ''}>{e.target ? '▸ ' : '· '}{e.name}</span>
          <span className="text-muted-foreground"> · Level {e.level || 1} · {e.hp}/{e.max_hp} HP</span>
          <span className="text-muted-foreground"> · {e.engaged ? 'fighting' : e.aggressive ? 'hostile' : 'neutral'}</span>
          {(e.effects ?? []).map((effect, index) => (
            <span key={index} className="text-gold"> [{effectName(effect.id)} {effect.remaining}]</span>
          ))}
        </span>
        <ActionButton send={send} command={`target ${e.id}`}>target</ActionButton>
        <ActionButton send={send} command={`attack ${e.id}`}>attack</ActionButton>
      </Line>,
    )
  }
  for (const e of data.unconscious_creatures ?? []) {
    rows.push(
      <Line key={`out-${e.id}`}>
        <span className="flex-1">· {e.name} <span className="text-muted-foreground">(unconscious)</span></span>
        <ActionButton send={send} command={`get ${e.id}`}>pick up</ActionButton>
      </Line>,
    )
  }
  for (const [index, effect] of (data.player?.effects ?? []).entries()) {
    rows.push(<p key={`fx-${index}`} className="text-sm text-destructive">! You: {effectName(effect.id)} · {effect.remaining} pulses</p>)
  }
  for (const [index, n] of (data.npcs ?? []).entries()) {
    rows.push(<p key={`npc-${index}`} className="my-1.5">· <span className="text-story">{n.name}</span> <span className="text-muted-foreground">— {n.appearance}</span></p>)
  }
  for (const player of data.players_here ?? []) {
    rows.push(<p key={`player-${player.name}`} className="my-1.5">· <span className="text-primary">{player.name}</span> <span className="text-muted-foreground">· Level {player.level} · player</span></p>)
  }
  for (const c of data.corpses ?? []) {
    rows.push(
      <Line key={`corpse-${c.id}`}>
        <span className="flex-1">· {c.description}</span>
        {c.harvestable && <ActionButton send={send} command={`harvest ${c.id}`}>harvest</ActionButton>}
      </Line>,
    )
  }
  for (const body of data.player_bodies ?? []) {
    rows.push(
      <Line key={body.id}>
        <span className="flex-1">· {body.name}<small className="block text-muted-foreground">{body.items} items · {body.gold} gold · disappears in {Math.max(0, Math.ceil(body.expires - data.time))}s</small></span>
        <ActionButton send={send} command={`look ${body.id}`}>inspect</ActionButton>
        {body.owned && <ActionButton send={send} command={`get all from ${body.id}`}>recover items</ActionButton>}
      </Line>,
    )
  }
  for (const box of data.containers ?? []) {
    rows.push(
      <Line key={`box-${box.id}`}>
        <span className="flex-1">· {box.name} <span className="text-muted-foreground">({box.opened ? 'open' : 'locked'})</span></span>
        <ActionButton send={send} command={`look ${box.id}`}>inspect</ActionButton>
        {!box.opened && <ActionButton send={send} command={`unlock ${box.id}`}>unlock</ActionButton>}
      </Line>,
    )
  }
  if (data.unconscious) {
    rows.push(
      <Line key="legacy-out">
        <span className="flex-1">· unconscious {data.unconscious}</span>
        <ActionButton send={send} command={`get ${data.unconscious}`}>pick up creature</ActionButton>
      </Line>,
    )
  }
  if (room.creature_buyer) {
    rows.push(
      <Line key="buyer">
        <span className="flex-1 text-muted-foreground">Jake buys occupied cages. The offer includes every creature; the cage is sold too.</span>
        <ActionButton send={send} command="sell">show offers</ActionButton>
      </Line>,
    )
  }

  if (room.repair_service) {
    rows.push(<Line key="repairs"><span className="flex-1 text-muted-foreground">Equipment repairs are available here.</span><ActionButton send={send} command="repair" disabled={!!data.player?.combat}>Repair prices</ActionButton></Line>)
  }
  if (room.bank_service) {
    rows.push(<Line key="bank"><span className="flex-1 text-muted-foreground">Your bank: {data.player?.bank_gold || 0} gold. DEPOSIT or WITHDRAW an amount.</span><ActionButton send={send} command="balance">balance</ActionButton><ActionButton send={send} command="deposit all">deposit all</ActionButton><ActionButton send={send} command="withdraw all">withdraw all</ActionButton></Line>)
  }

  return (
    <>
      {rows.length > 0 && (
        <>
          <Rule />
          <Heading>Here</Heading>
          {rows}
        </>
      )}
      {data.ground.length > 0 && (
        <>
          <Rule />
          <Heading>On the ground</Heading>
          {countItems(data.ground).map(([id, n]) => (
            <ItemRow key={id} id={id} count={n} mode="ground" data={data} send={send} />
          ))}
        </>
      )}
      {room.shop.length > 0 && (
        <>
          <Rule />
          <Heading>On the counter</Heading>
          {countItems(room.shop).map(([id, n]) => (
            <ItemRow key={id} id={id} count={n} mode="shop" data={data} send={send} />
          ))}
        </>
      )}
    </>
  )
}

export function HeaderPanel({ data, send }: { data: Snapshot; send: Send }) {
  const { room } = data
  const area = [room.code, room.region].filter(Boolean).join(' · ') || (room.safe ? 'Within the town walls' : 'Beyond the walls')
  return (
    <TerminalBox title="Relic Frontier v0.9.1">
      <div className="grid gap-4 md:grid-cols-[minmax(240px,1fr)_minmax(0,2fr)]">
        <CharacterSummary data={data} />
        <div className="min-w-0 border-t border-primary pt-4 md:border-t-0 md:border-l md:pt-0 md:pl-4">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3">
            <h1 className="text-base font-bold text-primary">{room.name}</h1>
            <span className="text-sm text-muted-foreground">{area}</span>
          </div>
          <p className="mt-1 leading-relaxed text-story">{room.description}</p>
          <p className="mt-2 text-sm text-muted-foreground">Weather: {room.weather || 'clear'}{room.fog ? ` · visibility penalty ${room.fog}%` : ''}</p>
          <p className="mt-2 text-sm text-muted-foreground">exits: {room.exits.join(', ') || 'none'}</p>
          <Here data={data} send={send} />
        </div>
      </div>
    </TerminalBox>
  )
}
