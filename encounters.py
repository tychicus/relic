"""Actor-independent encounter targeting and scheduling for one or many players.

The local game supplies one player today. A future server supplies its room roster
to the same functions, resolves actions once under its world lock, and distributes
results. Network sessions, parties and shared rewards are outside this module.
"""

def actor_id(actor):
    return actor.get('uid') or actor['id']


def sync_encounter(encounter, players, enemies):
    """Prune absent/dead actors and preserve each participant's chosen target."""
    room = encounter['room']
    sides = {
        'players': [p for p in players if p['hp'] > 0 and p['room'] == room],
        'enemies': [e for e in enemies if e['hp'] > 0 and not e.get('unconscious') and e['location'] == room],
    }
    roster = {actor_id(a): a for rows in sides.values() for a in rows}
    previous = encounter.get('targets', {})
    targets = {}
    for side, rows in sides.items():
        opponents = {actor_id(a): a for a in sides['enemies' if side == 'players' else 'players']}
        for actor in rows:
            ident = actor_id(actor)
            selected = actor.get('target') if side == 'players' else previous.get(ident)
            targets[ident] = selected if selected in opponents else next(iter(opponents), None)
    encounter['participants'] = {side: [actor_id(a) for a in rows] for side, rows in sides.items()}
    encounter['targets'] = targets
    return roster


def ready_actions(encounter, roster, side, now):
    """Return due actor/target pairs; cooldowns belong to actors, not a player slot.

    The resolver must revalidate targets after each hit (a previous action may
    kill one), and advance attack_ready after resolving each action.
    """
    actions = []
    for ident in encounter.get('participants', {}).get(side, []):
        actor = roster.get(ident)
        target = roster.get(encounter['targets'].get(ident))
        if actor and target and actor['hp'] > 0 and target['hp'] > 0 and now >= actor.get('attack_ready', 0):
            actions.append((actor, target))
    return actions
