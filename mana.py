"""Mana reserves, slow practice, and recovery on the active game clock."""
import math


class Mana:
    def mana_progress(self):
        rules=self.rules();xp=self.p.get('mana_xp',0) if self.p else 0
        level,start=1,0
        while level<rules['mana_level_cap']:
            needed=rules['mana_xp_first']+(level-1)*rules['mana_xp_step']
            if xp<start+needed:break
            start+=needed;level+=1
        needed=None if level==rules['mana_level_cap'] else rules['mana_xp_first']+(level-1)*rules['mana_xp_step']
        return dict(level=level,max_level=rules['mana_level_cap'],level_xp=xp-start,next_xp=needed)

    def max_mana(self):
        if not self.p:return 0
        cls=self.w['classes'][self.p['class']]
        return cls.get('mana',0)+(self.p['level']-1)*cls.get('mana_per_level',0)+(self.mana_progress()['level']-1)*self.rules()['mana_per_practice_level']

    def init_mana(self):
        self._mana_tick=self.clock()
        self._mana_in_combat=bool(self.p and self.p.get('combat'))
        if self.p:
            self.p.setdefault('mana_xp',0)
            self.p['mana']=max(0,min(self.p.get('mana',self.max_mana()),self.max_mana()))

    def mana_cost(self,sid):
        if not self.rules()['mana_enabled']:return 0
        spec=self.w['skills'][sid];progress=self.spell_progress(sid)
        row=spec['magic_levels'][progress['level']-1] if progress else {}
        return math.ceil(row.get('mana_cost',spec.get('mana_cost',0))*self.affinity(sid)['mana'])

    def require_mana(self,sid):
        cost=self.mana_cost(sid)
        if self.p.get('mana',0)<cost:
            raise ValueError(f'{self.w["skills"][sid]["name"]} needs {cost} mana; you have {math.floor(self.p.get("mana",0))}. Recover outside combat or REST at an inn.')
        return cost

    def spend_mana(self,cost,practice):
        if not cost:return
        before=self.mana_progress();old_max=self.max_mana()
        self.p['mana']=max(0,self.p['mana']-cost)
        if before['next_xp'] is not None:
            self.p['mana_xp']+=self.rules()['mana_xp_per_use']*practice
        after=self.mana_progress()
        if after['level']>before['level']:
            self.p['mana']+=max(0,self.max_mana()-old_max)
            self.log(f'Your mana mastery reaches level {after["level"]}. Maximum mana: {self.max_mana():g}.','reward')

    def recover_mana(self):
        now=self.clock();elapsed=math.floor(max(0,now-getattr(self,'_mana_tick',now)))
        if not elapsed:return
        self._mana_tick=now
        rules=self.rules()
        in_combat=bool(self.p['combat'])
        rate=rules['mana_combat_regen'] if in_combat or self._mana_in_combat else rules['mana_regen']
        self._mana_in_combat=in_combat
        self.p['mana']=min(self.max_mana(),self.p['mana']+elapsed*rate*self.w['classes'][self.p['class']].get('mana_recovery_scale',1))

    def victory(self,e):
        old_level=self.p['level']
        super().victory(e)
        if self.p['level']>old_level:self.p['mana']=self.max_mana()

    def death(self):
        super().death()
        self.p['mana']=self.max_mana()

    def extra_command(self,verb,target):
        if verb in ('mana','meditate'):
            progress=self.mana_progress()
            scale=self.w['classes'][self.p['class']].get('mana_recovery_scale',1)
            self.log(f'Mana: {math.floor(self.p["mana"])}/{self.max_mana():g}. Mana mastery level {progress["level"]}. Recovery: {self.rules()["mana_regen"]*scale:g}/second outside combat, {self.rules()["mana_combat_regen"]*scale:g}/second in combat. REST at an inn restores health and mana. Valid mana-consuming casts slowly train your reserve.')
            return True
        return super().extra_command(verb,target)

    def extra_snapshot(self,result):
        result=super().extra_snapshot(result)
        if self.p:
            result['player'].update(mana=self.p['mana'],max_mana=self.max_mana(),mana_progress=self.mana_progress())
            for skill in result.get('player_skills',[]):skill['mana_cost']=self.mana_cost(skill['id'])
        return result
