# Relic Frontier v0.9.1

A local, editable, keyboard-driven fantasy RPG with relic technology.
Python 3.11+ and the standard library are the only game requirements.

This repository contains the game source, current authored world, and built
browser interface. Personal character saves, local content backups, and
downloaded development dependencies are excluded. A fresh copy starts with
no saved character; each developer keeps their own local progress.

Download this repository with **Code > Download ZIP** and extract it, or clone
`https://github.com/tychicus/relic.git`. See [CONTRIBUTING.md](CONTRIBUTING.md)
for the shared development workflow.

## Start

Stop any old game with **Ctrl+C** in its launcher. On Windows, open
`Start_Game.cmd` in this folder. On Mac/Linux, run `python3 server.py`.
Play at http://127.0.0.1:8765 and edit at http://127.0.0.1:8765/admin.
Check the displayed version; refresh with Ctrl+F5 if the browser is stale.

Read **UPDATE_v0.9.1.txt** for the wider layout and screen controls.
Read **UPDATE_v0.9.0.txt** for the full mechanics guide, editable balance values,
new commands and intentional limitations. **CHANGELOG.md** records the release
and verification. Older UPDATE files in docs/history describe earlier releases.

## Help, syntax and emotes

HELP is a short topic index. HELP COMBAT, HELP CAPTURE and HELP BANK explain
those systems; HELP FIREBALL (or any skill name/ID) shows live mana costs,
cooldowns, shared recovery, damage/healing, status effects, targets and combat-start rules. Values include class, race, equipped gear, learned rank and mastery. SYNTAX CAST, SYNTAX GET
and SYNTAX TALK give command formats and examples. Use HELP <skill> for more
information about a skill. Mistakes suggest useful commands; suggestions never execute actions.

TALK TAMSIN and TALK TO TAMSIN say hello. TALK TAMSIN ABOUT COOKING or
ASK TAMSIN ABOUT COOKING uses the existing conversation. SAY COOKING TO TAMSIN
still works. Useful aliases include GO N, MOVE NORTH, INSPECT, INV, WEAR,
WIELD, TAKE and DRINK. Full skill names work directly, such as QUICK STRIKE.

HELP EMOTES lists enabled actions. Try WAVE TAMSIN, SMILE, BOW or
ME brushes dust from a coat. Emotes are cosmetic: they do not trigger NPC
conversations, change combat targets, spend resources or award practice.
Combat time still passes normally while reading help or using emotes.

In the owner workshop, open **Emotes & socials** to edit names, commands,
aliases, descriptions and messages, with a sample message preview. To add one,
choose **Emote / social** under Create and edit. New entries start with an
editable gesture_ command. Use {actor} in messages and {target} in the optional
targeted message; leave the targeted message blank to disallow targets.
Disable an entry to remove it from player commands and help, then save world
changes. Existing game commands, skill names and help topics cannot be reused.
Older world files without an emotes section still load; ME remains available.

## Skill rules and rank comparisons

Skill cards, HELP <skill>, SKILLS and cast-button tooltips use calculated rules.
Physical attacks show a damage range with current gear; spells show their current
power and actual mana cost. Effects include class/race-adjusted chances, duration,
stacking and per-pulse damage. Authored skill descriptions remain owner notes;
they cannot override the player-facing rules. Skill notes are edited under Skills & spells.

Before buying a rank, open the learning choices, HELP <skill>, or LEARN without an
argument. They show the next rank's point cost, required character level and exact
rounded improvement at the **current** level, gear and mastery. Unchanged costs
and timing are stated explicitly. A rank that currently adds no numeric benefit
says so. LEARN <skill> still purchases directly; no additional confirmation is added.
Spell/crafting mastery is earned through practice, separately from purchased ranks.

## Race and class balance

Human class baselines at level 1 (before race modifiers or mana mastery):

| Class | HP | HP per level | Mana | Mana per level | Role |
| --- | ---: | ---: | ---: | ---: | --- |
| Warrior | 65 | 12 | 12 | 1 | Health and weapon techniques |
| Rogue | 60 | 10 | 18 | 1 | Physical damage, dodge and escape |
| Mage | 50 | 8 | 40 | 3 | Offensive spells and enchanting |
| Cleric | 40 | 6 | 55 | 4 | Healing and defensive wards |

- Humans use the class baselines without racial bonuses or penalties.
- Elves have 15% less total HP, 15% more mana and magic power, and 25% faster
  spell/mana practice. Character XP and learning-point schedules do not change.
- Orcs gain +5 base HP and 10% more total HP. Their existing no-magic restriction
  remains, with recall scrolls as the exception; they choose Warrior or Rogue.
  If the owner enables magic, their default magic power/mana multipliers are 0.25,
  and magic practice is 0.5. These penalties are editable.

Clerics start with Healing Light (human: up to 21 HP for 4 mana, 8s cooldown).
At level 5 they can learn Holy Ward (human: 26% incoming attack reduction for
12s, 8 mana, 20s cooldown). Both use the shared manual-skill recovery and are
self-only for now. Wards reduce attack damage after armor, leave at least 1 HP
damage per hit, do not reduce status damage, do not stack, and end on death.
An equal or stronger active ward blocks recasting without spending resources.
The default final ward cap is 60%, adjustable under Crafting & balance.

Divine abilities use a separate class affinity: Clerics get 1.3× power, 0.8× mana
cost and 1.25× practice; Mages retain stronger offensive magic. Mana recovery
multipliers are Cleric 1.2, Mage 1, Rogue 0.5, Warrior 0.35. Race modifiers combine
with the class, and final HP/mana totals are rounded. Class health growth and race
multipliers are editable under Characters. Old worlds lacking these fields keep
their previous defaults. Existing saves keep their levels, learned ranks, practice,
inventory and points; health/mana are capped to the new maximum when loaded.

The class ordering is checked through level 100. This is an initial balance pass;
encounter difficulty still depends on enemy damage, defenses, groups and rewards.
New rooms and enemy XP remain owner-authored and are unchanged by this update.

## Play

- Move with N, S, E, W, UP, DOWN. LOOK inspects the current room; LOOK NORTH 2
  attempts a distant view. Descriptions contain discovery clues.
- ATTACK [creature] or KILL [creature] begins automatic combat. TARGET [distinct description]
  changes opponents. Inject skills, spells, potions or FLEE between pulses.
  Generic names such as KILL BEETLE, TARGET BEETLE or CAST FIREBALL BEETLE work
  when all matches are the same creature type. They keep your matching current
  target, otherwise choose the first match. If different types match, specify
  the type or a description such as SCARRED COPPER BEETLE to choose an individual.
  Ready players and enemies attack in the same shared pulse, with individual recovery
  timers. Enemies focus the player who starts a fight; enemies starting a fight choose
  a random present player independently. They keep that target until it becomes invalid.
- New characters start with one learned ability. LEARN lists choices; LEARN KICK
  spends earned points to learn or improve it. One point is earned at levels 5, 10,
  15 and every fifth level through 100. SKILLS lists learned abilities; CAST [skill] uses one.
  Existing learned abilities remain; available points use the new allowance minus points spent.
  Orcs have +5 base HP and a 1.1× total HP multiplier; they cannot use spells, enchanting or magical equipment.
  Recall scrolls are their one magic-item exception, usable at levels 1–29 outside
  combat and rooms that block recall. They can choose Warrior or Rogue; their HP
  bonus, magic restriction and recall exception are editable under Races.
  The point interval is editable under Learning.
  Warriors can study ordinary magic at a strong penalty; enchanting is mage-only.
  Mages face strong penalties with martial techniques. Stronger skills unlock later.
- Character, spell, magical-equipment and mana progression reach level 100.
  Every valid use trains slow mastery; suitable challenges award extra practice.
  MANA shows your reserve. Spells spend mana, which recovers between fights.
- SHOW MAP or DISPLAY MAP opens a map pop-up only when requested. It charts only
  rooms your character has entered and connections between visited rooms, using
  the creator map layout. It never shows enemies, NPCs, loot, unknown rooms, or
  connections to unvisited rooms. Your location is highlighted; select a visited
  elevation, zoom, fit the floor, or center on yourself. Selecting a room does not
  move you. Close or Escape returns to commands; combat continues while open.
  Exploration saves per character and survives death. Older saves start with their
  current room because previous travel was not recorded. Dark rooms remain unnamed
  until seen with light. HELP MAP explains the controls.
- INVENTORY, EQUIPMENT, BUY, SELL, GET, DROP, EQUIP and UNEQUIP manage items.
  LOOK SELF (or EQUIPMENT) lists every hand and armor slot, including empty slots.
  Enchanted item names appear violet, with their glow description and separate bonus.
  EQUIP [weapon] LEFT/RIGHT and UNEQUIP LEFT/RIGHT manage hands. A two-handed
  weapon reserves both hands; a one-handed weapon permits a shield. Helmet,
  chest, pants and arms have separate armor slots. Worn armor and shields add defense.
  Items have no carrying weight, and your bag has no item-count limit. Chests and
  cages retain their own storage capacities. REPAIR [item] repairs damaged gear
  at a repair service; Anthony's shop offers repairs.
- QUAFF POTION retains the old healing behavior. EAT [food], HARVEST [remains],
  COOK [recipe], SHARPEN, ENCHANT [item] and RECALL access the new systems.
  Enchant a held weapon or worn/held armor; HOLD [armor] holds it in your left
  hand. Enchantments temporarily boost damage/protection, shown as a separate
  (+bonus) with a glow cue. SKILLS shows the slowly trained enchanting level.
  Individual magical equipment also earns permanent XP: weapons through attacks
  and armor through hits received while protecting you. Inspect an item to see
  its level and progress.
- New characters start with one recall scroll. At levels 1–2 it can be reused
  without being consumed. From level 3 through 29, each successful recall uses
  one scroll, including the starter scroll; buy or find replacements. At level
  30 and above, recall scrolls cannot be used and an attempt does not consume
  one. These rules apply to every race, including Orcs. Combat and recall-disabled
  rooms still block recall. Reusable scrolls survive all blocked attempts.
  Both level thresholds and consumption on combat/room failure are adjustable
  under Crafting & balance. Existing characters keep their current inventory.
- LOOK [object], UNLOCK [container], PUT [item] IN CHEST [number],
  GET [item] FROM CHEST [number], PUT [creature] IN CAGE [number], RELEASE CAGE
  [number], and SAY [phrase] TO [creature/cage/NPC] retain exploration/storage.
- Regions have editable wandering enemy populations, caps, weather and fog. Multiple
  enemies may share a square and participate in a fight. Wounded enemies gradually
  recover outside combat; rates and delays are editable.
- REST at the inn restores health and mana. SAVE is optional: progress saves automatically.
- Death returns you to the fountain. Your body keeps all carried gold, inventory and
  worn gear for 15 minutes, including time with the game closed. Return and LOOK BODY,
  GET ALL FROM BODY, or GET <item> FROM BODY. If several bodies remain, use BODY <number>.
  Recovered gear goes into your bag; equip it again. All belongings can be recovered at once.
- From the fountain, go SOUTH then WEST to the Brass Badger Bank. Osric Tallywick
  handles BALANCE, DEPOSIT <amount or ALL> and WITHDRAW <amount or ALL>. Accounts belong
  to the character's permanent identity. Banked gold remains safe after death.

Combat continues while the server runs, including with the browser closed.
Ctrl+C in the launcher stops and saves. No account or external service is used.

## Edit and preserve

Rare equipment is a separate bonus drop: each defeated enemy of level 10 or higher
has a 0.1% chance to drop one of eight legendary weapons or armor pieces. That is
about one special item per 1,000 eligible kills on average, not a guaranteed drop.
Dark Vampires and Cave Trolls currently qualify. Normal loot is still awarded.
Captures and released creatures never grant a special drop. Each eligible defeat
is checked once; reloading cannot reroll a checked corpse.

These items cannot be purchased. Weapons and armor exceed ordinary gear in their
matching slots; Starwake's damage exceeds the Elven sword at every equal mastery
level. Seven rewards are nonmagical and usable by Orcs. Both ordinary and rare
loot go straight into your bag. Each copy has its own identity, so storage, repairs,
enchantments, saving and death recovery preserve the individual item.

Use **Rare equipment drops** in the owner editor to change the chance, enemy-level
threshold, item pool, selection weights and each item's minimum enemy level.
Edit reward stats under **Items & equipment**. The enemy-drop-only flag prevents
shop purchases; selling a recovered reward does not add it to shop stock.

Use the owner dashboard, visual block map, record forms and **Save world
changes**. New skills, status effects, NPCs, recipes and spawning rules use
ordinary controls; raw JSON is an optional advanced view. Numeric chances,
durations, restrictions, prices, risks and progression are configurable.

`content/world.json` contains authored content. `saves/game.sqlite3` contains
progress and individual objects/creatures. Keep them together, and stop the
game before copying or archiving. `content/history` is authored-world history,
not a full character backup. Keep backups of your own working game folder
outside this repository. The owner's original release folders and saves are
not part of this download.

An updated save must stay with the updated code. To start a separate character,
copy the full folder and remove `saves` only inside the separate stopped copy.

## Development and checks

`engine.py` keeps the established game behavior. `expedition.py` extends it
with instance-based encounters, effects, hands and crafting. `enchanting.py`
handles temporary item enchantments and slow crafting progression.
`magic_progression.py` handles separate spell and individual equipment XP and
validates their per-level power tables. `revision_rules.py` provides the other
validation/authoring schemas used by the editor. `adventure.py`,
`frontier.py`, and `abilities.py` retain discoveries, containers and eligibility.
`learning.py`, `mana.py` and `equipment.py` handle learning, reserves and equipment
slots. `player_map.py` tracks per-character exploration and filters map data. `regions.py` manages regional populations; `encounters.py` tracks multiple
participants and individual targets. `server.py` is the existing loopback-only transport. The browser interface is
a React + shadcn/ui app in `ui/`; its built files live in `static/` and are
all the game needs, so playing never requires Node. New state separates
player effects/proficiency/targets from world creatures/home slots/remains;
there is no networked multiplayer or account system.

Run `Run_Tests.cmd` on Windows, or:

```
python -X utf8 -m unittest discover -s tests -q
node tests/test_map_tools.js
node tests/test_editor_helpers.js
```

Node is optional and only used for development tests and interface changes.
Tests create temporary databases and never play against the bundled save. See
the changelog for browser checks and known limitations.

## Changing the interface

The game page and owner editor are built from `ui/` (React, TypeScript,
Tailwind CSS and shadcn/ui components in `ui/src/components/ui`). With Node
installed:

```
cd ui
npm ci
npm run dev     # live-reloading UI at http://localhost:5173; keep server.py running
npm run build   # rewrites ../static; commit or copy the result with the game
```

`npm run dev` forwards game requests to http://127.0.0.1:8765. For another
port, set `GAME_SERVER`, e.g. `GAME_SERVER=http://127.0.0.1:8877 npm run dev`.
Do not edit `static/` by hand: every build replaces it.

On Windows, Build_UI.cmd rebuilds both pages. Node 24 LTS was used for this release.
Run `npm test` inside ui/ for the map and editor helper tests.
In PowerShell, an alternate development backend is configured with:

```powershell
$env:GAME_SERVER="http://127.0.0.1:8877"
npm run dev
```

See UPDATE_v0.6.0.txt for historical release details and START_HERE.txt for
this repository's quick-start instructions. Older release notes refer to
the original packaged game's Archive folder and bundled character; those
personal files are not included here.
