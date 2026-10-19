"""Temporary item enchantments and slow, player-specific crafting progression."""
import copy
import math
from equipment import SLOT_ALIASES
from magic_progression import progress_text


class Enchanting:
    def repair_available(self):
        rules=self.rules()
        return bool(rules['repair_enabled'] and (rules['repair_anywhere'] or self.w['rooms'][self.p['room']].get('repair_service',False)))

    def repair_price(self,inst):
        points=max(0,-inst.get('bonus',0))
        rules=self.rules()
        return rules['repair_base_cost']+points*rules['repair_cost_per_point'] if points else 0

    def repair_item(self,target):
        if not self.rules()['repair_enabled']:raise ValueError('Equipment repair is disabled in this world.')
        if self.p['combat']:raise ValueError('Finish combat before repairing equipment.')
        if not self.repair_available():raise ValueError('Visit a shop offering equipment repairs. Look for a repair service in the room.')
        carried=list(dict.fromkeys(self.p['inventory']+list(self.p['equipment'].values())))
        if not target:
            damaged=[i for i in carried if self.item(i)['kind'] in ('weapon','armor') and self.state['instances'].get(i,{}).get('bonus',0)<0]
            self.log('Equipment repairs:\n'+('\n'.join(f'{self.item(i)["name"]}: {self.repair_price(self.state["instances"][i])} gold. REPAIR {i}' for i in damaged) if damaged else 'Your carried and equipped gear needs no repairs.'))
            return
        aliases={**SLOT_ALIASES,**{slot:slot for slot in self.p['equipment']}}
        if target in aliases:
            iid=self.p['equipment'].get(aliases[target])
            if not iid:raise ValueError('That equipment slot is empty.')
        else:iid=self.match(target,carried)
        spec=self.item(iid);inst=self.state['instances'].get(iid,{})
        if spec['kind'] not in ('weapon','armor'):raise ValueError('Only weapons and armor can be repaired.')
        if inst.get('bonus',0)>=0:raise ValueError('That item is undamaged. No gold was spent.')
        cost=self.repair_price(inst)
        if self.p['gold']<cost:raise ValueError(f'Repairing {spec["name"]} costs {cost} gold. You do not have enough gold.')
        self.p['gold']-=cost
        inst['bonus']=0
        self.log(f'Repaired {self.item(iid)["name"]} for {cost} gold. Its damage penalty is removed; magic experience and active enchantments are preserved.','reward')

    def extra_command(self,verb,target):
        if verb=='repair':self.repair_item(target);return True
        return super().extra_command(verb,target)

    def extra_snapshot(self,result):
        result=super().extra_snapshot(result)
        if self.p:result['room']['repair_service']=self.repair_available()
        return result

    def skill_command(self, verb, target):
        if verb in ('cast', 'skill'):
            matches = [(alias, sid) for sid,s in self.w['skills'].items() if s.get('effect') == 'enchant'
                       for alias in (sid.casefold(), s['name'].casefold(), 'enchant' if sid == 'enchanting' else sid.casefold())
                       if target.startswith(alias+' ')]
            if matches:
                alias, sid = max(matches, key=lambda x:len(x[0]))
                self.activate_skill(sid, target[len(alias)+1:])
                return True
        handled = super().skill_command(verb, target)
        if verb in ('skills', 'abilities'):
            for sid,skill in self.w['skills'].items():
                if skill.get('effect') == 'enchant' and self.skill_eligible(sid):
                    p = self.enchant_progress(sid)
                    progress = 'maximum level' if p['next_xp'] is None else f'{p["level_xp"]:g}/{p["next_xp"]:g} XP toward next level'
                    self.log(f'{skill["name"]} skill level {p["level"]}: {progress}; success {p["chance"]:g}%; bonus +{p["bonus"]}; duration {p["duration"]:g}s. ENCHANT <item>; weapons must be held, armor worn or held.')
        return handled

    def enchant_progress(self, sid='enchanting'):
        rules = self.rules()
        xp = self.p.get('proficiencies', {}).get(sid, 0) if self.p else 0
        level, start = 1, 0
        cap = rules['enchant_level_cap']
        while level < cap:
            needed = rules['enchant_xp_first'] + (level - 1) * rules['enchant_xp_step']
            if xp < start + needed:
                break
            start += needed
            level += 1
        needed = None if level == cap else rules['enchant_xp_first'] + (level - 1) * rules['enchant_xp_step']
        return dict(level=level, max_level=cap, xp=xp, level_xp=xp-start, next_xp=needed,
                    chance=min(100, max(0, rules['enchant_base'] + (level-1)*rules['enchant_level_gain'])),
                    bonus=rules['enchant_bonus'] + (level-1)//rules['enchant_bonus_levels'],
                    duration=rules['enchant_seconds'] + (level-1)*rules['enchant_seconds_per_level'])

    def migrate_enchantments(self):
        # Old positive bonuses become one temporary enchantment on first load.
        # Existing XP and physical weapon damage remain intact.
        for inst in self.state.get('instances', {}).values():
            if inst.get('kind') == 'weapon' and inst.get('bonus', 0) > 0:
                inst['enchantment'] = dict(bonus=inst['bonus'], until=self.clock()+self.enchant_progress()['duration'])
                inst['bonus'] = 0
                inst.pop('rank', None)

    def expire_enchantments(self):
        for iid, inst in self.state['instances'].items():
            effect = inst.get('enchantment')
            if effect and effect['until'] <= self.clock():
                inst.pop('enchantment')
                for player in self.all_players():
                    if iid in player['inventory'] or iid in player['equipment'].values():
                        self.player_event(player['id'], f'The enchantment on {self.w["items"][inst["item"]]["name"]} fades. Its magical glow is gone.')

    def modified_item(self, inst):
        item = copy.deepcopy(self.w['items'][inst['item']])
        stat = 'damage' if item['kind'] == 'weapon' else 'armor'
        progress = self.item_magic_progress(inst)
        base = max(0, (progress['power'] if progress else item.get(stat, 0)) + inst.get('bonus', 0))
        sharpen = inst.get('sharpen_bonus', 0) if inst.get('sharpen_until', 0) > self.clock() else 0
        effect = inst.get('enchantment', {})
        active = effect.get('until', 0) > self.clock()
        magic = effect.get('bonus', 0) if active else 0
        glow = ''
        if active:
            glow = ('Enchanted: it shimmers with a faint magical glow.' if magic <= 2 else
                    'Enchanted: luminous threads of magic ripple across its surface.' if magic <= 4 else
                    'Enchanted: it shines with a brilliant, pulsing magical aura.')
        item[stat] = base + magic + sharpen
        item['base_'+stat] = base
        item.update(instance=True, enchantment_bonus=magic, enchanted=active,
                    enchantment_remaining=max(0, effect.get('until', 0)-self.clock()),
                    enchantment_description=glow, sharpen_bonus=sharpen)
        item.update(damage_penalty=max(0,-inst.get('bonus',0)),repair_cost=self.repair_price(inst))
        item['name'] += f' [{inst["number"]}]' + (' (enchanted)' if active else '')
        if inst.get('bonus', 0) < 0:
            item['name'] += ' (damaged)'
        if sharpen:
            item['name'] += ' (sharpened)'
        item['description'] += '\n' + self.gear_stats(item)
        if item['damage_penalty']:
            item['description'] += f'\nDamage penalty: -{item["damage_penalty"]}. Repair price: {item["repair_cost"]} gold at a repair service.'
        if progress:
            item['magic_progress'] = progress
            item['description'] += '\nMagic ' + progress_text(progress)
        if glow:
            item['description'] += '\n' + glow + f' The enchantment lasts another {math.ceil(item["enchantment_remaining"])} seconds.'
        return item

    @staticmethod
    def gear_stats(item):
        if item['kind'] not in ('weapon', 'armor'):
            return ''
        stat = 'damage' if item['kind'] == 'weapon' else 'armor'
        text = f'{stat.title()} {item.get("base_"+stat, item.get(stat, 0))}'
        if item.get('enchanted'):
            text += f' (+{item["enchantment_bonus"]})'
        if item.get('sharpen_bonus'):
            text += f' · Sharpened +{item["sharpen_bonus"]}'
        return text

    def enchanting_slot(self, target):
        eq = self.p['equipment']
        slots = {slot:iid for slot,iid in eq.items()
                 if self.item(iid)['kind'] == 'armor' or
                 (slot in ('weapon', 'left_hand') and self.item(iid)['kind'] == 'weapon')}
        aliases = {**SLOT_ALIASES, **{slot:slot for slot in eq}}
        if target in aliases:
            slot = aliases[target]
            if slot in slots:
                return slot
        elif not target:
            for slot in ('weapon', 'left_hand', 'armor'):
                if slot in slots:
                    return slot
        else:
            try:
                iid = self.match(target, list(slots.values()))
            except ValueError as exc:
                raise ValueError('Enchant a weapon you are holding or armor you are wearing or holding. '+str(exc)) from exc
            found = [s for s,i in slots.items() if i == iid]
            if len(found) == 1:
                return found[0]
            raise ValueError('Specify ENCHANT LEFT or ENCHANT RIGHT to choose between those items.')
        raise ValueError('Enchant a weapon you are holding or armor you are wearing or holding.')

    def enchant_item(self, sid, target):
        if self.p['combat']:
            raise ValueError('Finish combat before enchanting equipment.')
        slot = self.enchanting_slot(target)
        skill, rules = self.require_skill(sid), self.rules()
        remaining = self.p['cooldowns'].get(sid, 0)-self.clock()
        if remaining > 0:
            raise ValueError(f'{skill["name"]} is ready in {math.ceil(remaining)} seconds.')
        if self.p['gold'] < rules['enchant_cost']:
            raise ValueError(f'Enchanting costs {rules["enchant_cost"]} gold per attempt.')
        iid = self.p['equipment'][slot]
        spec = self.item(iid)
        if iid not in self.state['instances']:
            iid = self.new_instance(dict(kind=spec['kind'], item=iid, bonus=0))
            self.p['equipment'][slot] = iid
        inst = self.state['instances'][iid]
        before = self.enchant_progress(sid)
        self.p['gold'] -= rules['enchant_cost']
        self.p['cooldowns'][sid] = self.clock()+skill['cooldown']
        if before['level'] < before['max_level']:
            self.p.setdefault('proficiencies', {})[sid] = before['xp']+rules['enchant_xp_per_attempt']
        if self.rng.random() < before['chance']/100:
            inst['enchantment'] = dict(bonus=before['bonus'], until=self.clock()+before['duration'])
            label = 'damage' if spec['kind'] == 'weapon' else 'armor'
            self.log(f'Enchantment succeeds! {spec["name"]} shimmers and glows: +{before["bonus"]} {label} for {before["duration"]:g} seconds.', 'reward')
        elif spec['kind'] == 'weapon' and self.rng.random() < rules['enchant_destroy']/100:
            self.p['equipment'].pop(slot)
            self.state['instances'].pop(iid)
            self.log('The enchantment fails catastrophically. Your weapon is destroyed!', 'danger')
        elif spec['kind'] == 'weapon' and rules['enchant_damage']:
            inst['bonus'] = max(-self.w['items'][inst['item']]['damage'], inst.get('bonus', 0)-rules['enchant_damage'])
            self.log('The enchantment fails and damages your weapon.', 'danger')
        else:
            self.log('The enchantment fails. The item is unchanged.', 'danger')
        after = self.enchant_progress(sid)
        if after['level'] > before['level']:
            self.log(f'Your {skill["name"]} skill reaches level {after["level"]}!', 'reward')
        progress = 'maximum level' if after['next_xp'] is None else f'{after["level_xp"]:g}/{after["next_xp"]:g} XP toward the next level'
        self.log(f'{skill["name"]} level {after["level"]}: {progress}. Attempt success chance was {before["chance"]:g}%.')
