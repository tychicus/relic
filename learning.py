"""Player-selected abilities, earned learning points and class affinities."""


class Learning:
    def init_learning(self):
        if not self.p:return
        needs_starter=not self.p.get('learned_skills')
        cls=self.w['classes'][self.p['class']]
        starter=cls.get('starting_ability') or ('swordplay' if 'swordplay' in self.w['skills'] else None)
        if 'learned_skills' not in self.p:
            # Preserve previously available/practiced abilities when importing a save.
            known=set(self.state.get('announced_skills',[])) | set(self.p.get('spell_xp',{})) | set(self.p.get('proficiencies',{})) | set(self.p.get('cooldowns',{}))
            self.p['learned_skills']={sid:1 for sid in known if sid in self.w['skills'] and self.skill_eligible(sid)}
        if starter and needs_starter:self.p['learned_skills'].setdefault(starter,1)
        self.p.setdefault('ability_points_spent',0)

    def ability_points(self):
        return max(0,(self.p['level']-1)*self.rules()['learning_points_per_level']-self.p.get('ability_points_spent',0))

    def ability_rank(self,sid):
        return self.p.get('learned_skills',{}).get(sid,0)

    def affinity(self,sid):
        if not self.rules()['learning_enabled']:return dict(power=1,mana=1,practice=1)
        category=self.w['skills'][sid].get('category','martial')
        row=next((r for r in self.w['classes'][self.p['class']].get('affinities',[]) if r['category']==category),{})
        return dict(power=row.get('power',1),mana=row.get('mana',1),practice=row.get('practice',1))

    def ability_power(self,sid):
        rank=max(1,self.ability_rank(sid))
        return self.affinity(sid)['power']*(1+(rank-1)*self.rules()['learning_rank_bonus'])

    def skill_power(self,sid,fallback):
        power=super().skill_power(sid,fallback)*self.ability_power(sid)
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
            self.log(f'Learning points: {self.ability_points()}. Each character level after the first grants {self.rules()["learning_points_per_level"]}. LEARN <ability> learns it or improves its rank.')
            for sid,s in sorted(self.w['skills'].items(),key=lambda row:(row[1].get('unlock_level',1),row[1]['name'])):
                if not self.skill_eligible(sid):continue
                rank=self.ability_rank(sid);cap=s.get('max_rank',5);cost=s.get('learn_cost',1)
                affinity=self.affinity(sid)
                self.log(f'{s["name"]}: learn at character level {s.get("unlock_level",1)}; rank {rank}/{cap}; {cost} point(s) per rank; {affinity["power"]*100:g}% class power, {affinity["mana"]:g}x mana cost. LEARN {sid}')
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
        if self.rules()['learning_enabled'] and verb in ('skills','abilities'):
            self.log(f'Known abilities — {self.ability_points()} learning point(s) available. Use LEARN for choices.')
            for sid in self.available_skill_ids():
                s=self.w['skills'][sid];progress=self.spell_progress(sid)
                action='Improves automatic attacks' if s.get('passive') else f'CAST {sid}; {self.mana_cost(sid)} mana'
                power=f'; mastery {progress["level"]}, power {self.skill_power(sid,progress["power"])}' if progress else ''
                self.log(f'{s["name"]}: rank {self.ability_rank(sid)}/{s.get("max_rank",5)}{power}. {action}.')
            return True
        return super().skill_command(verb,target)

    def extra_snapshot(self,result):
        result=super().extra_snapshot(result)
        if self.p:
            enabled=self.rules()['learning_enabled']
            result['player']['ability_points']=self.ability_points()
            result['learning_enabled']=enabled
            for s in result.get('player_skills',[]):
                rank=self.ability_rank(s['id'])
                s.update(rank=rank,learn_cost=s.get('learn_cost',1),max_rank=s.get('max_rank',5),affinity=self.affinity(s['id']))
                s['learn_level']=s.get('unlock_level',1)+rank*self.rules()['learning_rank_level_gap']
                if enabled:s['unlocked']=rank>0
                if s.get('magic_progress'):
                    s['magic_progress']['power']=self.skill_power(s['id'],s['magic_progress']['power'])
                    if s['magic_progress']['effect_damage'] is not None:s['magic_progress']['effect_damage']=max(0,round(s['magic_progress']['effect_damage']*self.ability_power(s['id'])))
        return result

    def check_live_references(self,w):
        super().check_live_references(w)
        if self.p:
            for sid,rank in self.p.get('learned_skills',{}).items():
                if sid not in w['skills']:raise ValueError('Cannot remove a learned ability.')
                if rank>w['skills'][sid].get('max_rank',5):raise ValueError('Cannot lower an ability rank cap below a learned rank.')
