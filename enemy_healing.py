"""Gradual recovery on the active clock, without offline healing bursts."""
import math


class EnemyHealing:
    def enemy_heal_setting(self,spec,key):
        fallback=self.rules()['enemy_'+key]
        return spec.get(key,fallback) if spec.get('healing_override',False) else fallback

    def reset_enemy_healing(self,e):
        spec=self.w['enemies'][e['type']]
        self._enemy_heal_at[e['uid']]=self.clock()+self.enemy_heal_setting(spec,'heal_delay')

    def heal_enemies(self):
        rules=self.rules();now=self.clock()
        if not rules['enemy_heal_enabled']:
            self._enemy_heal_at.clear();return
        engaged=self.engaged_creature_ids()
        creatures={e['uid']:e for rid in self.w['rooms'] for e in self.creatures(rid,True,False)}
        for uid in list(self._enemy_heal_at):
            if uid not in creatures:self._enemy_heal_at.pop(uid)
        for uid,e in creatures.items():
            spec=self.w['enemies'][e['type']];maximum=spec['hp']
            percent=self.enemy_heal_setting(spec,'heal_percent')
            if e['hp']<=0 or e['hp']>=maximum or percent<=0:
                self._enemy_heal_at.pop(uid,None);continue
            if uid in engaged or e.get('unconscious'):
                self.reset_enemy_healing(e);continue
            if uid not in self._enemy_heal_at:self.reset_enemy_healing(e)
            if now<self._enemy_heal_at[uid]:continue
            gain=min(maximum-e['hp'],max(1,math.ceil(maximum*percent/100)))
            e['hp']+=gain
            # A delayed clock tick restores only one installment, not missed ones.
            self._enemy_heal_at[uid]=now+self.enemy_heal_setting(spec,'heal_interval')
            if e['location']==self.p['room'] and self.visible():
                self.log(f'{self.creature_name(e)} recovers {gain} HP.','notice')
