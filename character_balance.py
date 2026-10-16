"""Race/class trade-offs and temporary self-defense spells."""
import math


class CharacterBalance:
    def character_stats(self, race, cid, level=1, mana_mastery=1):
        race, cls = self.w['races'][race], self.w['classes'][cid]
        hp_growth = cls.get('hp_per_level', self.w['settings']['hp_per_level'])
        hp = max(1, round((cls['hp'] + race['hp_bonus'] + (level - 1) * hp_growth) * race.get('hp_scale', 1)))
        mana = cls.get('mana', 0) + (level - 1) * cls.get('mana_per_level', 0)
        mana += (mana_mastery - 1) * self.rules()['mana_per_practice_level']
        mana = max(0, round(mana * race.get('mana_scale', 1))) if race.get('magic_allowed', True) else 0
        return dict(hp=hp, mana=mana, hp_per_level=hp_growth * race.get('hp_scale', 1),
                    mana_per_level=cls.get('mana_per_level', 0) * race.get('mana_scale', 1) if race.get('magic_allowed', True) else 0)

    def max_hp(self):
        return self.character_stats(self.p['race'], self.p['class'], self.p['level'])['hp']

    def active_ward(self):
        ward = self.p.get('ward') if self.p else None
        if not ward or ward['until'] <= self.clock(): return None
        return dict(skill=ward['skill'], power=ward['power'], remaining=math.ceil(ward['until'] - self.clock()))

    def cast_ward(self, sid, target=''):
        if target: raise ValueError('Defense spells affect you. Use CAST ' + sid + ' without a target.')
        skill = self.w['skills'][sid]
        power = self.skill_power(sid, skill.get('ward', 20))
        current = self.active_ward()
        if current and current['power'] >= power:
            raise ValueError('An equal or stronger ward is already active. Wait for it to expire; no mana was spent.')
        self.p['ward'] = dict(skill=sid, power=power, until=self.clock() + skill.get('duration', 12))
        self.p['cooldowns'][sid] = self.clock() + skill['cooldown']
        self.log(f'{skill["name"]}: incoming attack damage reduced by {power:g}% for {skill.get("duration", 12):g}s. Wards do not stack; status damage is unaffected.', 'reward')

    def warded_damage(self, damage):
        ward = self.active_ward()
        return max(1, round(damage * (1 - ward['power'] / 100))) if ward else damage
