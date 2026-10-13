# Relic Frontier working rules

Read this file at the start of every session before changing this repository.
These rules apply throughout `tychicus/relic`. Read any more specific
`AGENTS.md` files too. The user's current instructions take precedence.

## Get current files before making changes

- Before editing, inspect the current branch, remotes, working tree, and any
  existing local commits. Preserve the user's and collaborators' work.
- Fetch fresh repository state from GitHub at the start of each change task,
  and again before resuming edits after another person may have changed the
  repository. Do not rely on an earlier chat, cached remote references, or an
  old download as the current version of the game.
- For a clean checkout of `main`, fetch `origin` and fast-forward to
  `origin/main` before editing. For an existing feature branch, fetch and
  integrate the latest relevant upstream and target-branch changes first.
  Start a new branch from the updated base for new work unless the user asks
  to work on a particular branch.
- A fresh copy means the latest shared code plus safely preserved local work.
  Do not download a ZIP over an edited folder, reset away local changes, run
  destructive cleanup, overwrite saves, or discard local commits to refresh.
  When local work exists, preserve it and integrate incoming changes safely;
  use a separate checkout if that is the clearest way to avoid overwriting it.
- Resolve straightforward conflicts without discarding either person's work.
  If a conflict requires choosing between incompatible intentions, explain the
  conflict and ask the user which behavior to keep.
- If GitHub cannot be reached or the latest files cannot be obtained, report
  that limitation before editing. Do not claim the checkout is current.

## Review and approval before committing or publishing

- Implement and test changes locally first. Give the user a usable game
  preview or reviewable file, a concise description of the changes, and the
  relevant check results and limitations.
- Wait for explicit user approval before committing and pushing the reviewed
  changes. A request to create or edit files does not by itself authorize a
  commit or an upload to GitHub.
- Approval applies to the reviewed changes. New substantive revisions require
  another review. If the user already explicitly approved both committing and
  pushing those changes, proceed without asking for the same approval again.
- Before committing, inspect the diff and include only the approved files.
  Keep unrelated changes out of the commit.
- These rules also apply to GitHub connector/API writes, remote commits,
  pull-request publication, merges, and deployment. Do not use a different
  publishing method to bypass review or approval.
- Use Conventional Commits: `type(scope): concise description`. Choose a
  useful scope such as `game`, `world`, `ui`, `tests`, or `repo`; for example,
  `fix(game): preserve inventory on reload` or
  `docs(repo): document the shared workflow`.

## Refresh again immediately before pushing

- Fetch GitHub's current branches again immediately before every push,
  publication, or merge, even if the checkout was updated earlier in the task.
  Check both the branch being published and its target branch where relevant.
- Compare the refreshed remote state with the local work. Integrate any new
  collaborator changes safely, inspect the combined diff, and rerun checks
  affected by that integration before uploading.
- If integration materially changes the approved result, show the revised
  result and obtain approval for that change. Do not treat old approval as
  approval to overwrite newer work.
- Use normal pushes. Never force-push, delete branches, or rewrite shared
  history without explicit user authorization.
- When publishing through the GitHub API, read the current branch SHA, use
  its current tree and commit as the base, and use a conditional, non-forced
  branch update. If the branch advances, fetch and reconcile it; do not simply
  retry with force or a new expected SHA while keeping stale content.
- Verify the remote branch after publishing and confirm that the intended
  commit and files are present. Clearly distinguish local edits, local
  commits, and verified GitHub updates in the final report.
- If authentication or environment restrictions prevent a push, preserve the
  completed work and explain the actual blocker. Do not ask for passwords or
  claim a push succeeded without checking GitHub.

## Preserve the game and personal progress

- Preserve authored rooms, names, descriptions, balance, and existing game
  behavior unless the requested change requires otherwise.
- `content/world.json` is the shared authored world. Coordinate overlapping
  edits and review changes from the owner editor before committing them.
- Personal saves in `saves/`, local world history in `content/history/`, old
  game archives, credentials, dependency folders, and temporary testing files
  stay out of commits. Respect `.gitignore`; do not force-add them.
- Test save-affecting changes with disposable copies or generated test data.
  Never test by modifying the user's original character save. Stop a running
  game cleanly before copying a save or backing up its working folder.
- Keep balance and gameplay settings adjustable through the existing owner
  editor when extending those systems. Preserve the visual room map.

## Checks appropriate to the change

- For game, world, or test changes, run the relevant automated checks and
  manually exercise the changed behavior when useful. The Python suite is
  `python -X utf8 -m unittest discover -s tests -q`.
- Interface helper checks are `node tests/test_map_tools.js` and
  `node tests/test_editor_helpers.js`.
- For interface source changes, rebuild from `ui/` with `npm ci` when needed
  and `npm run build`, then include the resulting `static/` files in the same
  approved change. Do not edit the generated interface by hand.
- For visible interface changes, provide a usable preview and check the
  affected controls and layouts. Do not claim browser testing without doing it.
- A documentation-only edit normally needs a diff, wording, and link review,
  not a complete game test run. State any skipped checks and their reasons.
