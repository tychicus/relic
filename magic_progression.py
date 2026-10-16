"""Independent spell practice and persistent experience on individual magic gear."""
import copy
import math


def default_magic_levels(power, step=1, count=100):
    levels, xp = [], 0
    for index in range(count):
        levels.append(dict(xp=xp, power=power + index * step))
        xp += 100 + index * 50
    return levels


def validate_magic(w):
    for group in ('skills', 'items'):
        for spec in w[group].values():
            label = spec['name']
            if type(spec.get('magic', False)) is not bool:
                raise ValueError(label + ': magic progression must be Yes or No.')
            gain = spec.get('magic_xp_per_use', 1)
            if type(gain) is not int or not 1 <= gain <= 10000:
                raise ValueError(label + ': XP per use must be a whole number from 1 to 10000.')
            if spec.get('magic'):
                allowed = spec.get('effect', 'damage') in ('damage', 'heal', 'knockout', 'ward') if group == 'skills' else spec['kind'] in ('weapon', 'armor')
                if not allowed:
                    raise ValueError(label + ': use magic progression for damage, healing, ward or knockout spells, or weapons and armor. Enchanting has its own progression.')
            levels = spec.get('magic_levels')
            if levels is None and not spec.get('magic'):
                continue
            if not isinstance(levels, list) or not 1 <= len(levels) <= 100:
                raise ValueError(label + ': provide 1–100 magic levels.')
            previous = -1
            for index, row in enumerate(levels):
                if not isinstance(row, dict):
                    raise ValueError(label + ': each magic level must be a record.')
                xp, power = row.get('xp'), row.get('power')
                if type(xp) is not int or not 0 <= xp <= 1000000000 or xp <= previous or (index == 0 and xp != 0):
                    raise ValueError(label + ': total XP must start at 0 and increase at every level.')
                limit = (90 if spec.get('effect') == 'ward' else 100 if spec.get('effect') == 'knockout' else 10000) if group == 'skills' else 10000
                minimum = 1 if group == 'skills' and spec.get('effect') == 'heal' else 0
                if type(power) is not int or not minimum <= power <= limit:
                    raise ValueError(label + f': level power must be a whole number from {minimum} to {limit}.')
                if 'effect_damage' in row and (type(row['effect_damage']) is not int or not 0 <= row['effect_damage'] <= 1000):
                    raise ValueError(label + ': effect damage per pulse must be a whole number from 0 to 1000.')
                if 'mana_cost' in row and (type(row['mana_cost']) is not int or not 0<=row['mana_cost']<=10000):
                    raise ValueError(label + ': level mana cost must be a whole number from 0 to 10000.')
                previous = xp
    return w


def magic_progress(spec, xp=0):
    if not spec.get('magic'):
        return None
    levels = spec['magic_levels']
    xp = max(0, xp) if type(xp) in (int, float) and math.isfinite(xp) else 0
    index = 0
    while index + 1 < len(levels) and xp >= levels[index + 1]['xp']:
        index += 1
    row = levels[index]
    return dict(level=index + 1, max_level=len(levels), xp=xp, level_xp=xp - row['xp'],
                next_xp=levels[index + 1]['xp'] - row['xp'] if index + 1 < len(levels) else None,
                power=row['power'], effect_damage=row.get('effect_damage'))


def progress_text(progress):
    suffix = 'maximum level' if progress['next_xp'] is None else f'{progress["level_xp"]:g}/{progress["next_xp"]:g} XP to next level'
    return f'Level {progress["level"]} · {suffix}'


class MagicProgression:
    def skill_practice(self,sid,target=''):
        kind=self.w['skills'][sid].get('effect','damage')
        enemy=self.find_creature(target) if kind=='knockout' and target else self.enemy() if self.p['combat'] or kind=='knockout' else None
        return self.practice_multiplier(enemy)*self.affinity(sid)['practice']

    def practice_multiplier(self,enemy=None):
        if not enemy or enemy.get('released'):return 1
        gap=self.w['enemies'][enemy['type']].get('level',1)-self.p['level']
        rules=self.rules()
        return 1+(rules['practice_challenge_bonus'] if gap>=0 else 0)+(rules['practice_harder_bonus'] if gap>=rules['practice_harder_gap'] else 0)

    def spell_progress(self, sid):
        return magic_progress(self.w['skills'][sid], self.p.get('spell_xp', {}).get(sid, 0) if self.p else 0)

    def skill_power(self, sid, fallback):
        progress = self.spell_progress(sid)
        return progress['power'] if progress else fallback

    def item_magic_progress(self, inst):
        return magic_progress(self.w['items'][inst['item']], inst.get('magic_xp', 0))

    def magic_template(self, spec):
        progress = magic_progress(spec)
        if not progress:
            return spec
        item = copy.deepcopy(spec)
        stat = 'damage' if spec['kind'] == 'weapon' else 'armor'
        item[stat] = item['base_' + stat] = progress['power']
        item['magic_progress'] = progress
        item['description'] += '\n' + self.gear_stats(item) + '\nMagic ' + progress_text(progress)
        return item

    def grant(self, iid):
        spec = self.w['items'][iid]
        if spec.get('magic') or spec.get('drop_only'):
            return self.new_instance(dict(kind=spec['kind'], item=iid, bonus=0, magic_xp=0))
        return super().grant(iid)

    def ensure_magic_slot(self, slot):
        iid = self.p['equipment'].get(slot)
        if iid in self.w['items'] and self.w['items'][iid].get('magic'):
            iid = self.p['equipment'][slot] = self.grant(iid)
        return iid

    def init_magic_items(self):
        # Assign identities once to old copies, including stored and dropped gear.
        piles = [(pile, self.state.get('drop_timers', {}).get(rid, [])) for rid, pile in self.state['ground'].items()]
        if self.p:
            piles.append((self.p['inventory'], []))
            for slot in self.p['equipment']:
                self.ensure_magic_slot(slot)
        piles += [(inst['contents'], []) for inst in list(self.state['instances'].values()) if inst['kind'] == 'chest']
        for pile, timers in piles:
            for index, iid in enumerate(pile):
                if iid in self.w['items'] and self.w['items'][iid].get('magic'):
                    replacement = pile[index] = self.grant(iid)
                    timer = next((t for t in timers if t['item'] == iid), None)
                    if timer:
                        timer['item'] = replacement

    def train_magic_items(self, ids, practice=1):
        for iid in dict.fromkeys(ids):
            inst = self.state['instances'].get(iid)
            if not inst:
                continue
            before = self.item_magic_progress(inst)
            if not before or before['next_xp'] is None:
                continue
            spec = self.w['items'][inst['item']]
            inst['magic_xp'] = before['xp'] + spec.get('magic_xp_per_use', 1)*practice
            after = self.item_magic_progress(inst)
            if after['level'] > before['level']:
                self.log(f'{spec["name"]} [{inst["number"]}] reaches magic level {after["level"]}!', 'reward')

    def activate_skill(self, sid, target=''):
        before = self.spell_progress(sid)
        practice=self.skill_practice(sid,target)
        super().activate_skill(sid, target)
        # Exceptions mean the command was rejected, so no practice is awarded.
        if before and before['next_xp'] is not None:
            spec = self.w['skills'][sid]
            self.p.setdefault('spell_xp', {})[sid] = before['xp'] + spec.get('magic_xp_per_use', 1)*practice
            after = self.spell_progress(sid)
            if after['level'] > before['level']:
                self.log(f'Your {spec["name"]} reaches spell level {after["level"]}!', 'reward')

    def skill_command(self, verb, target):
        handled = super().skill_command(verb, target)
        if verb in ('skills', 'abilities'):
            for sid, spec in self.w['skills'].items():
                progress = self.spell_progress(sid)
                if progress and self.skill_eligible(sid):
                    label = {'heal': 'healing', 'knockout': 'success chance (%)'}.get(spec.get('effect'), 'damage')
                    dot = f'; effect damage {progress["effect_damage"]} per pulse' if progress['effect_damage'] is not None else ''
                    self.log(f'{spec["name"]}: {progress_text(progress)}; {label} {progress["power"]}{dot}.')
        return handled

    def extra_snapshot(self, result):
        result = super().extra_snapshot(result)
        for iid, spec in self.w['items'].items():
            if spec.get('magic'):
                result['items'][iid] = self.item(iid)
        for skill in result.get('player_skills', []):
            progress = self.spell_progress(skill['id'])
            if progress:
                skill['magic_progress'] = progress
        return result

    def update_world(self, new):
        super().update_world(new)
        with self.lock:
            self.init_magic_items()
            self.init_mana()
            self.prepare_residents()
            self.prepare_regions()
            self.save()
