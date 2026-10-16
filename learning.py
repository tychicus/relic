"""Player-selected abilities, earned learning points and class affinities."""


from skill_details import SkillDetails
from character_balance import CharacterBalance


class Learning(CharacterBalance, SkillDetails):
    def init_learning(self):
        if not self.p:return
        needs_starter=not self.p.get('learned_skills')
        cls=self.w['classes'][self.p['class']]
        starter=cls.get('starting_ability') or ('swordplay' if 'swordplay' in self.w['skills'] else None)
        if 'learned_skills' not in self.p:
            # Preserve previously available/practiced abilities when importing a save.
            known=set(self.state.get('announced_skills',[])) | set(self.p.get('spell_xp',{})) | set(self.p.get('proficiencies',{})) | set(self.p.get('cooldowns',{}))
            self.p['learned_skills']={sid:1 for sid in known if sid in self.w['skills'] and self.skill_eligible(sid)}
        if starter and needs_starter and self.skill_eligible(starter):self.p['learned_skills'].setdefault(starter,1)
        self.p.setdefault('ability_points_spent',0)

    def ability_points(self):
        interval=self.rules()['learning_point_interval']
        awards=self.p['level']//interval-1//interval
        return max(0,awards*self.rules()['learning_points_per_level']-self.p.get('ability_points_spent',0))

    def learning_schedule(self):
        rules=self.rules();interval=rules['learning_point_interval']
        if interval==1:return f'{rules["learning_points_per_level"]} point(s) each character level after level 1.'
        return f'{rules["learning_points_per_level"]} point(s) every {interval} character levels, starting at level {interval}.'

    def ability_rank(self,sid):
        return self.p.get('learned_skills',{}).get(sid,0)

    def affinity(self,sid):
        skill=self.w['skills'][sid]
        category=skill.get('category','martial')
        row=next((r for r in self.w['classes'][self.p['class']].get('affinities',[]) if r['category']==category),{}) if self.rules()['learning_enabled'] else {}
        result=dict(power=row.get('power',1),mana=row.get('mana',1),practice=row.get('practice',1))
        if self.magical_skill(skill):
            race=self.w['races'][self.p['race']]
            result['power']*=race.get('magic_power',1)
            result['practice']*=race.get('magic_practice',1)
        return result

    def ability_power(self,sid,rank=None):
        rank=max(1,self.ability_rank(sid) if rank is None else rank)
        return self.affinity(sid)['power']*(1+(rank-1)*self.rules()['learning_rank_bonus'])

    def skill_power(self,sid,fallback,rank=None):
        power=super().skill_power(sid,fallback)*self.ability_power(sid,rank)
        if self.w['skills'][sid].get('effect')=='ward':return min(self.rules()['ward_cap'],max(0,round(power)))
        if self.w['skills'][sid].get('effect')=='knockout':return min(100,max(0,power))
        return max(1 if self.w['skills'][sid].get('effect')=='heal' else 0,round(power))

    def require_skill(self,sid):
        if not self.rules()['learning_enabled']:return super().require_skill(sid)
        if sid not in self.w['skills']:raise ValueError('That skill does not exist.')
        skill=self.w['skills'][sid]
        if not self.skill_eligible(sid):raise ValueError(skill['name']+' is not available to your class and race.')
        if not self.ability_rank(sid):raise ValueError('You have not learned '+skill['name']+'. Use LEARN '+sid+'.')
        if skill.get('passive'):raise ValueError(skill['name']+' improves automatic attacks; use ATTACK <enemy>.')
        return skill

    def available_skill_ids(self):
        if not self.rules()['learning_enabled']:return super().available_skill_ids()
        return [sid for sid in self.w['skills'] if self.ability_rank(sid) and self.skill_eligible(sid)]

    def announce_skills(self,initial=False):
        if not self.rules()['learning_enabled']:return super().announce_skills(initial)
        if not self.p:return
        previous=self.state.get('learning_announced_level',0)
        if self.p['level']!=previous:
            self.state['learning_announced_level']=self.p['level']
            self.log(f'Learning points available: {self.ability_points()}. Use LEARN to choose new abilities or improve known ones.','reward')
        self.state['announced_skills']=self.available_skill_ids()

    def learn_ability(self,target):
        if not self.rules()['learning_enabled']:raise ValueError('Ability selection is disabled by the owner.')
        if not target:
            self.log(f'Learning points: {self.ability_points()}. Earn {self.learning_schedule()} LEARN <ability> learns it or improves its rank.')
            for sid,s in sorted(self.w['skills'].items(),key=lambda row:(row[1].get('unlock_level',1),row[1]['name'])):
                if not self.skill_eligible(sid):continue
                preview=self.next_skill_rank(sid)
                if preview:
                    self.log(f'{s["name"]} — next rank {preview["rank"]}: {preview["cost"]} point(s), character level {preview["required_level"]}.\n'+'\n'.join(preview['lines'])+f'\nHELP {sid}; LEARN {sid}')
                else:self.log(s['name']+': maximum rank.')
            return
        if self.p['combat']:raise ValueError('Finish combat before choosing abilities.')
        sid=self.match_skill(target);s=self.w['skills'][sid]
        if not self.skill_eligible(sid):raise ValueError('That ability is not available to your class and race.')
        rank=self.ability_rank(sid);cost=s.get('learn_cost',1)
        if rank>=s.get('max_rank',5):raise ValueError('That ability is already at its maximum rank.')
        if self.p['level']<s.get('unlock_level',1):raise ValueError(s['name']+f' can be learned at character level {s.get("unlock_level",1)}.')
        # Each later rank requires five more character levels by default.
        needed=s.get('unlock_level',1)+rank*self.rules()['learning_rank_level_gap']
        if self.p['level']<needed:raise ValueError(f'{s["name"]} rank {rank+1} requires character level {needed}.')
        if self.ability_points()<cost:raise ValueError(f'You need {cost} learning point(s). Gain character levels to earn more.')
        self.p['ability_points_spent']+=cost
        self.p['learned_skills'][sid]=rank+1
        self.log(f'{s["name"]} learned at rank {rank+1}. {self.ability_points()} learning point(s) remain.','reward')
        self.state['announced_skills']=self.available_skill_ids()

    def extra_command(self,verb,target):
        if verb in ('learn','train'):
            self.learn_ability(target);return True
        return super().extra_command(verb,target)

    def skill_command(self,verb,target):
        if verb in ('skills','abilities'):
            self.log(f'Known abilities — {self.ability_points()} learning point(s) available. Use LEARN for choices.' if self.rules()['learning_enabled'] else 'Available abilities:')
            for sid in self.available_skill_ids():
                self.skill_help(sid)
            return True
        return super().skill_command(verb,target)

    def extra_snapshot(self,result):
        result=super().extra_snapshot(result)
        if self.p:
            enabled=self.rules()['learning_enabled']
            result['player']['ward']=self.active_ward()
            result['player']['ability_points']=self.ability_points()
            result['learning_enabled']=enabled
            result['learning_schedule']=self.learning_schedule()
            for s in result.get('player_skills',[]):
                rank=self.ability_rank(s['id'])
                s.update(rank=rank,learn_cost=s.get('learn_cost',1),max_rank=s.get('max_rank',5),affinity=self.affinity(s['id']))
                s['learn_level']=s.get('unlock_level',1)+rank*self.rules()['learning_rank_level_gap']
                if enabled:s['unlocked']=rank>0
                if s.get('magic_progress'):
                    s['magic_progress']['power']=self.skill_power(s['id'],s['magic_progress']['power'])
                    if s['magic_progress']['effect_damage'] is not None:s['magic_progress']['effect_damage']=max(0,round(s['magic_progress']['effect_damage']*self.ability_power(s['id'])))
                facts=self.skill_facts(s['id'])
                s.update(description='\n'.join(facts['lines']), details=facts,
                         next_rank=self.next_skill_rank(s['id']), recovery_lines=self.skill_recovery_lines(s['id']))
        return result

    def check_live_references(self,w):
        super().check_live_references(w)
        if self.p:
            if not self.class_eligible(self.p['race'],self.p['class'],w):
                raise ValueError('The saved character class requires a race that can use magic.')
            if not self.can_use_magic(w=w):
                for iid in self.p['equipment'].values():
                    inst=self.state.get('instances',{}).get(iid,{})
                    spec=w['items'][inst.get('item',iid)]
                    if self.magical_item(spec) or inst.get('enchantment',{}).get('until',0)>self.clock():
                        raise ValueError('Unequip magical equipment before disabling magic for this race.')
            for sid,rank in self.p.get('learned_skills',{}).items():
                if sid not in w['skills']:raise ValueError('Cannot remove a learned ability.')
                if rank>w['skills'][sid].get('max_rank',5):raise ValueError('Cannot lower an ability rank cap below a learned rank.')
