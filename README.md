# Relic Frontier v0.7.0

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

Read **UPDATE_v0.7.0.txt** for the full update guide, editable balance values,
new commands and intentional limitations. **CHANGELOG.md** records the release
and verification. Older UPDATE files in docs/history describe earlier releases.

## Play

- Move with N, S, E, W, UP, DOWN. LOOK inspects the current room; LOOK NORTH 2
  attempts a distant view. Descriptions contain discovery clues.
- ATTACK [creature] or KILL [creature] begins automatic combat. TARGET [distinct description]
  changes opponents. Inject skills, spells, potions or FLEE between pulses.
- SKILLS shows eligibility and unlocks. CAST [skill name], BASH, KNOCKOUT,
  FIREBALL, LIGHTNING and CHARGE are supported.
- INVENTORY, EQUIPMENT, BUY, SELL, GET, DROP, EQUIP and UNEQUIP manage items.
  EQUIP [weapon] LEFT/RIGHT and UNEQUIP LEFT/RIGHT manage hands.
- QUAFF POTION retains the old healing behavior. EAT [food], HARVEST [remains],
  COOK [recipe], SHARPEN, ENCHANT [item] and RECALL access the new systems.
  Enchant a held weapon or worn/held armor; HOLD [armor] holds it in your left
  hand. Enchantments temporarily boost damage/protection, shown as a separate
  (+bonus) with a glow cue. SKILLS shows the slowly trained enchanting level.
- LOOK [object], UNLOCK [container], PUT [item] IN CHEST [number],
  GET [item] FROM CHEST [number], PUT [creature] IN CAGE [number], RELEASE CAGE
  [number], and SAY [phrase] TO [creature/cage/NPC] retain exploration/storage.
- REST at the inn heals. SAVE is optional: progress saves automatically.

Combat continues while the server runs, including with the browser closed.
Ctrl+C in the launcher stops and saves. No account or external service is used.

## Edit and preserve

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
handles temporary item enchantments and slow crafting progression. `revision_rules.py`
provides the validation/authoring schema used by the editor. `adventure.py`,
`frontier.py`, and `abilities.py` retain discoveries, containers and eligibility.
`server.py` is the existing loopback-only transport. The browser interface is
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
