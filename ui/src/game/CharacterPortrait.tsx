import portraits from '@/assets/character-portraits.png'
import type { Gender } from './types'

// Windows into the exact approved 1145 x 1374 sheet. The grid and labels stay
// outside each window; Vite ships one cached image shared by all 20 portraits.
const columns: Record<string, number> = { warrior: 164, rogue: 406, mage: 652, cleric: 899 }
const rows: Record<string, [number, number]> = { human: [120, 311], elf: [509, 710], orc: [910, 1110] }
const WARRIOR = [
  '      ▄█▄    ▄ ',
  '     █▀▀▀█   █ ',
  '     ▀███▀   █ ',
  ' ▄▄█▀█████▀█ █ ',
  '████ █████ ▀▀█▀',
  ' ▀▀  ██▀██     ',
  '    ▄██ ██▄    ',
].join('\n')

interface Props {
  race?: string
  characterClass?: string
  gender?: Gender
  label?: string
}

export function CharacterPortrait({ race = 'human', characterClass = 'warrior', gender = 'male', label }: Props) {
  const row = rows[race]
  const x = columns[characterClass]
  // Owner-created races/classes and owner-enabled Orc spellcasters keep a
  // generic emblem until artwork is supplied for those additional choices.
  if (!row || x === undefined || (race === 'orc' && !['warrior', 'rogue'].includes(characterClass))) {
    return <pre role="img" aria-label="Adventurer portrait" className="my-2 text-center text-xs leading-[1.05] text-primary">{WARRIOR}</pre>
  }
  const y = row[gender === 'female' ? 1 : 0]
  return (
    <svg
      role="img"
      aria-label={label ?? `${gender === 'female' ? 'Female' : 'Male'} ${race} ${characterClass} portrait`}
      viewBox={`${x} ${y} 210 180`}
      width="117"
      height="100"
      className="my-2 block shrink-0 overflow-hidden"
    >
      <image href={portraits} width="1145" height="1374" style={{ imageRendering: 'pixelated' }} />
    </svg>
  )
}
