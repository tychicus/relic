# Relic Frontier v0.6.0 — 2026-09-27

- Released from the latest user-edited v0.5.0 source with byte-identical world,
  content history and saves. No save-schema or balance changes.
- Added consistent version labels, build shortcut and organized recovery folders.
- Exposed hide-on-respawn discovery behavior in the owner editor.
- Corrected an NPC-sensitive visibility test; all 115 Python tests pass.
- TypeScript/build, Node helper tests and disposable-copy browser checks pass.

- Rebuilt the game page and owner editor with React, TypeScript, Tailwind CSS
  and shadcn/ui, keeping the same layout, palette, commands and editor
  features. Source is in `ui/`; the built interface ships in `static/`, so
  players still need only Python.
- `map-tools` and `editor-helpers` moved unchanged to `ui/src/lib/*.cjs`,
  shared by the editor and the Node tests.
- `server.py` serves the built pages and `static/assets/*` (plain file names
  only). Its security policy now allows inline styles, which the editor's
  confirmation dialog needs; scripts remain same-origin only.
- The editor's "Discard unsaved changes" confirmation is now an in-page dialog,
  and adding an inspectable object uses an inline name box instead of a browser
  prompt.
- Terminal-style look: monospace text, near-black console, cyan framed
  panels with inset titles, text meters, a `❯` command prompt and a status line.
- The previous interface files are in `../Archive/Before_v0.6.0/UI_Backup_20260926_223022`.

# Relic Frontier v0.5.0

Built from the supplied v0.4.0 folder, including its current authored edits
and saved character. Read `UPDATE_v0.5.0.txt` for controls and balance formulas.

- Added independent creature instances, extra fixed/random/entry spawn groups,
  roaming restrictions, multiple combatants, readable descriptors, manual
  targeting and automatic retargeting. Retained the existing alternating
  pulse cadence and automatic attacks.
- Added reusable damage/stun/slow effects, attachment chances, durations,
  stacking rules, messages and race/creature resistances.
- Added trainable Enchanting with individual weapon changes and destruction
  risk, temporary Sharpening, Fireball, Lightning and Charge.
- Added right/left hand controls, shields, two-handed restrictions and
  configurable dual-wield eligibility and penalties.
- Added placed NPCs with appearance and dialogue, distance/perception looking,
  recall restrictions, food, creature-specific harvesting and cooking.
- Reorganized the editor with a dashboard, categories, filters, collapsible
  forms and cross-links. Preserved the visual room map, connected creation,
  exports and all existing content forms. Fixed narrow-window editor overflow.
- Added player-owned effects/proficiency/target data and world-owned creature
  identities, home spawn slots and remains. Migration is additive. The legacy
  equipment `weapon` key remains the right hand; new `left_hand` is optional.
- Preserved source save bytes and all preexisting authored fields, with only
  the explicitly documented additive room, stock and harvesting additions.
- Added UTF-8 mode to the Windows test launcher for existing Unicode content.

Verification: 113 Python tests pass, including the previous 80 regression
tests; existing Node map and entry-creation checks pass. In-app browser checks
covered character creation, dashboard navigation, saving balance values,
creating/saving effects, attaching an effect to a skill, and selecting a room
from the visual map. Browser console reported no warnings/errors during those
checks. Narrow-window layout was inspected visually. Testing uses disposable
databases/copies, never the supplied character's working save.

Known limits: effect mechanics are damage, stun and slow; additional mechanic
types need code. Effect duration is measured in combat pulses and pauses out
of combat. Spell damage uses the existing weapon/class/level formula; there is
no mana or elemental resistance model. Weather is an authored visibility
penalty. NPC interactions are Look/Talk. Combat remains local and single-player.
The Windows launcher batch file itself was not exercised from File Explorer;
the Python server and browser were exercised on Windows.

Deferred: networked multiplayer/accounts/roles, branching quests/NPC shops,
technology-area expansion and Moon travel/content.

Recovery: the original v0.4.0 folder remains untouched. The sibling
`Relic_Frontier_Recovery` Git repository has a byte-exact `baseline-v0.4.0`
tag; `Relic_Frontier_v0.4.0_recovery.zip` was verified against every original
file. The v0.5.0 development repository contains staged feature checkpoints.
Use the recovery ZIP in a separate folder to roll back, including its old
save. Never put an upgraded save into old game code.
