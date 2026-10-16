"""Pure combat calculations and player-facing ability facts from those rules.

Rank previews never equip items, roll dice, award practice or mutate a save.
The same damage/effect helpers are used when an attack actually resolves.
"""
import math


def amount(value):
    if isinstance(value, list):
        return f'{value[0]:g}' if value[0] == value[1] else f'{value[0]:g}–{value[1]:g}'
    return f'{value:g}'


class SkillDetails:
    def attack_weapons(self):
        equipment = self.p['equipment']
        main = self.item(equipment['weapon']) if equipment.get('weapon') else {}
        off = self.item(equipment['left_hand']) if equipment.get('left_hand') else {}
        dual = main.get('kind') == 'weapon' and off.get('kind') == 'weapon'
        weapon = main if main.get('kind') == 'weapon' else off if off.get('kind') == 'weapon' else {}
        return weapon, off, dual

    def passive_power(self, sid, rank=None):
        rank = self.ability_rank(sid) if rank is None else rank
        return max(0, rank - 1) * self.rules()['learning_rank_bonus'] * self.affinity(sid)['power'] if self.rules()['learning_enabled'] else 0

    def attack_damage(self, roll, multiplier=1, sid=None, rank=None, passive_preview=None):
        progress = self.spell_progress(sid) if sid else None
        if progress:
            return self.skill_power(sid, progress['power'], rank)
        weapon, off, dual = self.attack_weapons()
        factor = self.ability_power(sid, rank) if sid else 1
        if not sid and self.rules()['learning_enabled']:
            for known in self.available_skill_ids():
                if self.w['skills'][known].get('passive'):
                    projected = rank if known == passive_preview else None
                    factor += self.passive_power(known, projected)
            if passive_preview and passive_preview not in self.available_skill_ids():
                factor += self.passive_power(passive_preview, rank)
        base = roll + weapon.get('damage', 0)
        base += off.get('damage', 0) * self.rules()['offhand_scale'] if dual else 0
        base += (self.p['level'] - 1) * self.w['settings']['damage_per_level']
        return max(1, round(base * multiplier * factor))

    def attack_effects(self, sid=None):
        weapon, off, dual = self.attack_weapons()
        spell = self.spell_progress(sid) if sid else None
        attachments = [] if spell else [dict(a, source='weapon') for a in weapon.get('status_effects', [])]
        if dual and not spell:
            attachments += [dict(a, source='off-hand weapon') for a in off.get('status_effects', [])]
        if sid:
            attachments += [dict(a, source='skill', chance=a.get('chance', 100) * min(1, self.affinity(sid)['power']))
                            for a in self.w['skills'][sid].get('status_effects', [])]
        return attachments

    def skill_effect_damage(self, sid, rank=None):
        progress = self.spell_progress(sid) if sid else None
        damage = progress['effect_damage'] if progress else None
        return max(0, round(damage * self.ability_power(sid, rank))) if damage is not None else None

    def skill_profile(self, sid, rank=None):
        """Numeric facts at the current character level, gear and mastery."""
        skill, rules = self.w['skills'][sid], self.rules()
        kind = skill.get('effect', 'damage')
        passive = bool(skill.get('passive') and rules['learning_enabled'])
        profile = dict(passive=passive, mana=0 if passive else self.mana_cost(sid),
                       cooldown=0 if passive else skill['cooldown'],
                       recovery=rules['action_recovery'] if not passive and kind in ('damage', 'heal', 'knockout', 'ward') else 0,
                       effects=[])
        if passive or kind == 'damage':
            profile['damage'] = [self.attack_damage(roll, 1 if passive else skill.get('multiplier', 1),
                                                   None if passive else sid, rank, sid if passive else None)
                                 for roll in self.w['classes'][self.p['class']]['damage']]
            if passive:
                profile['passive_bonus'] = self.passive_power(sid, rank) * 100
            override = None if passive else self.skill_effect_damage(sid, rank)
            for attachment in self.attack_effects(None if passive else sid):
                status = self.w['status_effects'][attachment['effect']]
                entry = dict(id=attachment['effect'], name=status['name'], kind=status['kind'],
                             source=attachment['source'], chance=attachment.get('chance', 100),
                             duration=attachment.get('duration') or status.get('duration', 3),
                             stacking=status.get('stacking', 'refresh'), max_stacks=status.get('max_stacks', 3))
                if status['kind'] == 'damage': entry['damage'] = status.get('damage', 0) if override is None else override
                if status['kind'] == 'slow': entry['slow'] = status.get('slow', 1.5)
                profile['effects'].append(entry)
        elif kind == 'heal':
            profile['healing'] = self.skill_power(sid, skill.get('heal', 20), rank)
        elif kind == 'knockout':
            profile['chance'] = self.skill_power(sid, skill.get('chance', 70), rank)
        elif kind == 'ward':
            profile.update(reduction=self.skill_power(sid, skill.get('ward', 20), rank), duration=skill.get('duration', 12))
        elif kind == 'sharpen':
            profile.update(bonus=rules['sharpen_bonus'], duration=rules['sharpen_seconds'])
        elif kind == 'enchant':
            progress = self.enchant_progress(sid)
            profile.update(chance=progress['chance'], bonus=progress['bonus'], duration=progress['duration'], gold=rules['enchant_cost'])
        return profile

    def skill_facts(self, sid, rank=None):
        skill, rules = self.w['skills'][sid], self.rules()
        profile = self.skill_profile(sid, rank)
        kind = skill.get('effect', 'damage')
        passive = profile['passive']
        if passive:
            summary = f'Current automatic-attack damage: {amount(profile["damage"])} on a hit; this skill contributes +{profile["passive_bonus"]:g}%.'
            target = 'Automatic attacks against your selected enemy. This passive cannot be cast.'
            combat = 'Does not start combat by itself. Use ATTACK <enemy>.'
        elif kind == 'damage':
            summary = f'Damage on a hit: {amount(profile["damage"])} before status effects.'
            target = 'A visible, conscious creature in this room, outside safe areas; omit the target to use your selected enemy.'
            combat = 'Can start combat.' if skill.get('initiates') else 'Requires an active fight. ATTACK first; cannot start combat.'
        elif kind == 'heal':
            summary = f'Restores up to {profile["healing"]:g} HP, limited by your missing health.'
            target = 'Self only; omit the target. Usable inside or outside combat. Full health does not spend the skill.'
            combat = 'Cannot start combat.'
        elif kind == 'knockout':
            summary = f'Knockout success: {profile["chance"]:g}% before creature capture resistance; no damage.'
            target = 'A visible, conscious, capturable creature at or below its capture-health threshold (see LOOK <enemy>).'
            combat = 'Can begin combat on failure. Success makes the creature unconscious; other opponents may keep fighting.'
        elif kind == 'ward':
            summary = f'Reduces incoming attack damage by {profile["reduction"]:g}% after armor for {profile["duration"]:g}s (minimum 1 damage per hit).'
            target = 'Self only; omit the target. Usable inside or outside combat. An equal or stronger active ward blocks recasting without spending mana.'
            combat = 'Cannot start combat.'
        elif kind == 'sharpen':
            summary = f'+{profile["bonus"]:g} weapon damage for {profile["duration"]:g}s.'
            target = 'A weapon equipped in your right hand; outside combat only.'
            combat = 'Cannot start combat.'
        else:
            summary = f'{profile["chance"]:g}% enchantment success; +{profile["bonus"]:g} damage/armor for {profile["duration"]:g}s; {profile["gold"]:g} gold per attempt.'
            target = 'A held weapon or worn/held armor; outside combat only.'
            combat = 'Cannot start combat.'
        rows = [summary]
        if passive:
            rows.append('Passive: 0 mana; no cooldown or shared recovery.')
        else:
            rows.append(f'Mana: {profile["mana"]:g} per use after class modifiers. Cooldown: {profile["cooldown"]:g}s.')
            rows.append(f'Shared manual-skill recovery: {profile["recovery"]:g}s.' + (' Automatic attacks continue.' if kind in ('damage', 'heal', 'knockout', 'ward') else ' Does not use or wait for shared recovery.'))
        rows += ['Target: ' + target, combat]
        if passive or kind == 'damage':
            rows.append('Damage uses your current character level, equipment, class, race and rank. Hits can miss or be dodged.' if not self.spell_progress(sid) or passive else 'Damage uses your current spell mastery, class, race and rank. Hits can miss or be dodged.')
        if kind == 'enchant' and not passive:
            rows.append(f'On weapon failure: {rules["enchant_destroy"]:g}% destruction chance; otherwise up to {rules["enchant_damage"]:g} damage penalty. Failed armor enchantments leave the armor unchanged.')
        for effect in profile['effects']:
            detail = 'prevents attacks and skill use' if effect['kind'] == 'stun' else f'{effect["slow"]:g}× basic-attack recovery' if effect['kind'] == 'slow' else f'{effect["damage"]:g} damage per pulse per stack'
            stacking = f'stacks up to {effect["max_stacks"]}' if effect['stacking'] == 'stack' else 'refreshes duration' if effect['stacking'] == 'refresh' else 'does not replace an active effect'
            rows.append(f'{effect["name"]} ({effect["source"]}): {effect["chance"]:g}% chance after a hit on a surviving target, before resistance; {effect["duration"]:g} pulses; {detail}; {stacking}.')
        if not profile['effects']:
            rows.append('Status effects: unconscious on success.' if kind == 'knockout' and not passive else 'Status effects: temporary ward; does not stack or reduce status damage; ends on death.' if kind == 'ward' else 'Status effects: none.')
        if not passive: rows.append('Cannot be used while stunned.')
        return dict(summary=summary, lines=rows, profile=profile)

    def next_skill_rank(self, sid):
        skill, rules = self.w['skills'][sid], self.rules()
        rank = self.ability_rank(sid)
        if not rules['learning_enabled'] or not self.skill_eligible(sid) or rank >= skill.get('max_rank', 5): return None
        current, projected = self.skill_profile(sid), self.skill_profile(sid, rank + 1)
        changes = []
        if rank == 0:
            changes.append('Unlock: ' + self.skill_facts(sid, 1)['summary'])
        else:
            for key, label, suffix in [('damage', 'Damage on a hit', ''), ('healing', 'Healing', ' HP'),
                                       ('chance', 'Success before resistance' if skill.get('effect') == 'knockout' else 'Success', '%'),
                                       ('reduction', 'Incoming attack damage reduction', '%'), ('passive_bonus', 'Automatic-attack bonus', '%')]:
                if key in current and current[key] != projected[key]:
                    changes.append(f'{label}: {amount(current[key])}{suffix} → {amount(projected[key])}{suffix}.')
            for before, after in zip(current['effects'], projected['effects']):
                if before.get('damage') != after.get('damage'):
                    changes.append(f'{after["name"]}: {before["damage"]:g} → {after["damage"]:g} damage per pulse per stack.')
            if not changes: changes.append('No numeric benefit at your current level, equipment and mastery under these rules.')
        if rank == 0:
            changes.append(f'Mana: {projected["mana"]:g}; cooldown: {projected["cooldown"]:g}s; shared recovery: {projected["recovery"]:g}s.')
        else:
            changes.append(f'Unchanged: {projected["mana"]:g} mana, {projected["cooldown"]:g}s cooldown, {projected["recovery"]:g}s shared recovery, targeting and effect chances/durations.')
        changes.append('Compared at your current character level, equipment and mastery; practice mastery is separate from purchased ranks.')
        return dict(rank=rank + 1, cost=skill.get('learn_cost', 1),
                    required_level=skill.get('unlock_level', 1) + rank * rules['learning_rank_level_gap'], lines=changes)

    def skill_recovery_lines(self, sid):
        if self.skill_profile(sid)['passive']: return []
        remaining = max(0, math.ceil(self.p['cooldowns'].get(sid, 0) - self.clock()))
        shared = max(0, math.ceil(self.p.get('action_ready', 0) - self.clock()))
        rows = [f'Currently recovering: {remaining}s remaining.'] if remaining else []
        if shared and self.w['skills'][sid].get('effect', 'damage') in ('damage', 'heal', 'knockout', 'ward'): rows.append(f'Shared recovery remaining: {shared}s.')
        return rows
