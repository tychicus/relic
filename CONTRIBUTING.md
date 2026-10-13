# Working on Relic Frontier together

The shared repository is https://github.com/tychicus/relic. Keep `main` as
the version you both consider ready to use, and propose work on a separate
branch so it can be reviewed before joining `main`.

## Get a development copy

After accepting a collaborator invitation, clone this repository using
GitHub Desktop or Git:

```sh
git clone https://github.com/tychicus/relic.git
cd relic
```

Python 3.11+ is enough to play. On Windows, double-click `Start_Game.cmd`.
On Mac/Linux, use `python3 server.py`. The browser interface is already
built and included in `static/`; you do not need Node just to play.

## Make and share a change

1. Fetch and pull the latest `main` before starting new work.
2. Create a short, descriptive branch, such as `add-forest-rooms`.
3. Make one focused change and run the checks relevant to it.
4. Review the changed files and commit only the work you intend to share.
5. Push your branch and open a pull request into `main`, explaining what
   changed and how you checked it.
6. Review the pull request together and merge it when ready. Both developers
   should then update their local `main`.

This follows [GitHub flow](https://docs.github.com/en/get-started/using-github/github-flow).

## Files to work on

- `content/world.json`: authored world, rooms, descriptions, and balance.
- Python files in the root: game behavior and the local server.
- `ui/src/`: game and owner-editor interface source.
- `tests/`: automated checks.
- `static/`: built interface; rebuild it after changing `ui/` source and
  include the resulting files in the same pull request.

Coordinate edits to `content/world.json` before both changing it. The owner
editor writes that shared file, so inspect its changes before committing.

## Check a change

```sh
python -X utf8 -m unittest discover -s tests -q
node tests/test_map_tools.js
node tests/test_editor_helpers.js
```

Use `python3` instead of `python` where required. The Node helper tests need
Node installed. One optional personal-save migration test is skipped when
no local save exists; it runs against a temporary copy when a save is present.
To change and rebuild the interface, install Node and npm,
then run:

```sh
cd ui
npm ci
npm run build
```

The build updates `static/`. Follow the development-server instructions in
README.md for live interface editing.

## Keep progress local

Each developer has their own `saves/game.sqlite3`. Saves, `content/history/`,
dependency folders, and local environment files are ignored by Git. Do not
force-add them. Keep credentials and personal backups outside the shared
repository, which is public.

Stop the game with Ctrl+C before backing up a working copy. Test changes on
a separate copy when they could affect an existing character or authored
world. Do not copy another developer's save over your own.
