"""Actor-independent encounter targeting and scheduling for one or many players.

The local engine supplies one player; the multiplayer server supplies its room
roster and resolves each shared pulse once under the world lock. Network sessions,
parties and shared rewards are outside this module.
"""
import random

def actor_id(actor):
    return actor.get('uid') or actor['id']


def sync_encounter(encounter, players, enemies, rng=None):
    """Keep targets; enemies focus the initiator or roll among present players."""
    rng = rng or random
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
            if selected not in opponents:
                if side == 'players':
                    selected = next(iter(opponents), None)
                elif encounter.get('initiator') in opponents:
                    selected = encounter['initiator']
                else:
                    choices = list(opponents)
                    selected = rng.choice(choices) if len(choices) > 1 else next(iter(choices), None)
            targets[ident] = selected
    encounter['participants'] = {side: [actor_id(a) for a in rows] for side, rows in sides.items()}
    encounter['targets'] = targets
    return roster


def ready_actions(encounter, roster, side, now):
    """Return due actor/target pairs; cooldowns belong to actors, not a player slot.

    Use side=None for a shared pulse across every player and enemy. The resolver
    must revalidate targets after each hit (a previous action may
    kill one), and advance attack_ready after resolving each action.
    """
    actions = []
    participants = encounter.get('participants', {})
    ids = participants.get(side, []) if side else [ident for team in ('players', 'enemies') for ident in participants.get(team, [])]
    for ident in ids:
        actor = roster.get(ident)
        target = roster.get(encounter['targets'].get(ident))
        if actor and target and actor['hp'] > 0 and target['hp'] > 0 and not actor.get('unconscious') and not target.get('unconscious') and now >= actor.get('attack_ready', 0):
            actions.append((actor, target))
    return sorted(actions, key=lambda pair: pair[0].get('attack_ready', 0))
