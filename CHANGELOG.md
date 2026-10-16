# Unreleased — Generic creature targeting

- Commands such as KILL BEETLE now accept several matching individuals of the
  same creature type. A matching current target is retained; otherwise the first
  matching creature is chosen. Descriptions and exact creature IDs still select
  individuals. Different matching creature types still require clarification.
- The shared matching rule also applies to ATTACK, TARGET, targeted spells and
  other commands that select a creature. Visibility and target eligibility remain.
- Validation: 285 Python tests passed; the optional personal-save migration test
  was skipped because the owner's game was running. Both JavaScript helper suites
  passed. Disposable browser checks verified KILL BEETLE with two Copper beetles,
  clarification when an Iron beetle is also present, and a spell aimed at that type.

# Unreleased — Starter recall scrolls and level limits

- New characters receive one recall scroll. Scrolls are reusable at levels 1–2,
  single-use at levels 3–29, and unusable from level 30. The starter scroll becomes
  single-use at level 3; replacements must be bought or found. Existing characters
  retain their inventory, with no extra scroll granted on load.
- Orcs can use recall scrolls as their only magic-item exception, subject to the
  same level limits. Spells, enchanting and other magic items remain blocked.
- Combat and room restrictions remain. Reusable scrolls are never consumed by
  a blocked attempt, even if failure consumption is enabled. Level-limit denials
  also preserve the scroll. Regular scrolls follow the existing failure setting.
- Added a separate race option in the owner editor for the recall exception and
  editable recall level thresholds under Crafting & balance. Updated character
  creation, inventory guidance, HELP and the scroll description; Use is disabled
  once a character reaches the configured cutoff.
- Validation: all 280 Python tests, both JavaScript helper suites and the UI
  production build passed. Disposable browser characters verified repeated
  level-1 recall, level-3 consumption, level-30 command rejection and disabled
  Use, continued Orc magic-equipment restrictions, and the owner level fields.

# Relic Frontier v0.9.1 — 2026-10-15

- Widened the game view to a maximum of 1760 pixels, reduced outer spacing,
  and made the character emblem more compact to leave more room for text.
- Desktop command entry and action buttons stay visible while the adventure
  log, long room/shop lists and character sidebar scroll independently.
- Room panels return to the top on entering a different room. Narrow or short
  windows retain ordinary page scrolling.
- Updated game, editor, launcher and package version labels to v0.9.1.
  Gameplay rules, authored content and the save format are unchanged.
- Validation: all 268 Python tests (including copied-save migration), both
  JavaScript helper suites and the production UI build passed. Browser checks
  covered desktop and narrow layouts, command entry, learning expansion,
  equipment actions, long shop lists and resetting the room panel on movement,
  using a disposable preview character.

# Mechanics follow-up — equipment, shared combat, death recovery and banking

- LOOK SELF and EQUIPMENT show all six slots, including empty and two-handed slots.
  Item lists use plain names; active enchanted names are violet with their bonus and glow.
- Shared combat pulses consider all ready participants together. Enemies retain the
  initiating player's target priority or independently choose a player when they initiate.
- Death returns the character to the fountain with the requested disorientation message.
  All carried possessions and gold stay in a recoverable body for 15 minutes. Nested
  containers and individual item progress survive recovery; unrecovered contents expire.
- Added the Brass Badger Bank and Osric Tallywick, south then west of the fountain.
  Deposits persist by character ID, remain private to that character and survive death.
- Body lifetime and bank room availability are editable; shared combat uses the existing
  owner-controlled pulse interval. Prepared on the update branch for review before merging.
- Validation: 242 Python tests, both JavaScript helper suites and the production UI build
  passed. A headless browser exercised the actual engine through a local test bridge,
  including equipment colors, responsive layout, banking, body recovery and expiration.
  Direct browser access to the preview server timed out in this environment.

# Relic Frontier v0.9.0 — 2026-10-14

- Character levels now reach 100. New characters start with one learned ability;
  level gains award points to choose abilities and improve ranks at gated levels.
- Added the rogue, cross-class ability study with persistent class penalties,
  higher-level techniques, and mage-only enchanting. Existing known abilities
  and progression survive save migration.
- Added spell mana costs, class reserves, recovery and slow use-based mana growth.
  Spell and individual equipment mastery now have 100 default levels, with
  challenge-based practice bonuses and per-level editable damage/costs.
- Added helmet, chest, pants and arm slots, shield defense and hand restrictions.
  Items and container contents have weight; class carrying capacity grows by level.
  Overweight acquisitions are rejected without loss; excess loot stays on the ground.
- Fixed unreachable skill gates, named spell targeting and scouting fixed enemies.
  Added shared skill/potion recovery and shop equipment repairs preserving magic XP.
- Added editable regional enemy banks, population caps, adjacent wandering, weather
  and fog. Multiple enemies fight together, with shared encounter structures tested
  for multiple players; networked multiplayer remains future work.
- Enemies heal gradually outside combat, with adjustable global and creature-level
  delay, interval and rate. Fighting, unconscious and defeated creatures never heal.
- Added owner controls and player displays for the new systems. Existing authored
  rooms and personal saves were preserved; tests use disposable data.
- Validation: 225 Python tests, both JavaScript helper suites, TypeScript and Vite
  build; 1,500 controlled early/mid-level fights; copied-save migration and local
  HTTP checks. Browser visual verification could not complete because the available
  browser could not connect to the preview. A separate preview launcher is provided.
- Prepared on the update branch for review before merging into main.

# Relic Frontier v0.8.0 — 2026-10-14

- Fireball and Lightning now start weak and gain separate spell experience.
  Each individual magical weapon or armor item also keeps its own experience.
- Added slow 20-level defaults: 1 XP per valid use, 100 XP to level 2 and
  10,450 total XP to level 20. The owner can edit each level's XP and power.
- Spell damage is independent of weapons and character-level multipliers.
  Healing, knockout chance and spell effect damage can also use level tables.
- Added per-level tables to the spell and equipment editor, plus level and
  progress displays in SKILLS, item inspection and the game panels.
- Old magical equipment gains an individual identity on loading. Experience
  survives storage, dropping, saving and temporary enchantment expiration.
  Recall scrolls remain single-use. Existing owner eligibility is preserved.
- Validation: 147 Python tests, both JavaScript helper suites and the
  TypeScript/Vite production build passed. Browser visual verification could
  not complete because the browser could not connect to the local preview.

# Relic Frontier v0.7.0 — 2026-10-13

- Added KILL as a complete ATTACK alias, including named and ambiguous targets.
- Added named enchanting targets for either hand, worn armor and held armor.
  HOLD and explicit hand equipment support holding body armor for enchanting;
  it grants protection only while worn (shields protect while held).
- Enchanting has its own slow XP/level curve. Valid successes and failures
  award practice. Chance, strength and duration scale with enchanting level;
  all progression and balance controls are available in Crafting & balance.
- Enchantments affect individual items, expire in real time (including offline),
  and refresh instead of stacking. Sharpening remains independent. Existing
  weapon failure risks, cost, cooldown and eligibility are preserved.
- Added separate base/bonus displays such as Armor 10 (+3), active glow prose,
  expiration messages and enchanting level/progress in SKILLS and the sidebar.
- Existing proficiency becomes the same numeric amount of XP. Legacy positive
  permanent bonuses become timed enchantments once on first load. Physical
  weapon damage is retained. Individual enchanted armor requires this version.
- Preserved the save snapshot and all authored data except the enchanting
  skill's outdated description. The local release includes a separate
  updated folder/ZIP and original backup; personal saves and backup archives
  remain excluded from this shared repository.
- Validation: 133 Python tests, map and editor helper suites, TypeScript and
  production UI build passed; actual saved character and preservation checks
  passed. Browser visual QA was attempted but the preview connection timed out.
- No multiplayer, area, story or unrelated editor changes.

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
