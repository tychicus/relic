"""One independent, very rare equipment roll per eligible defeated creature."""


class RareDrops:
    def award_rare_drop(self,enemy):
        # Captures and released creatures cannot be farmed; a corpse gets one roll.
        if enemy.get('hp',1)>0 or enemy.get('unconscious') or enemy.get('released') or enemy.get('rare_drop_checked'):
            return None
        enemy['rare_drop_checked']=True
        rules=self.rules();level=self.w['enemies'][enemy['type']].get('level',1)
        if not rules['rare_drops_enabled'] or level<rules['rare_drop_min_level'] or rules['rare_drop_chance']<=0:
            return None
        pool=[row for row in rules['rare_drop_pool'] if level>=row.get('min_level',1)]
        if not pool or self.rng.random()>=rules['rare_drop_chance']/100:
            return None
        template=self.rng.choices(pool,weights=[row['weight'] for row in pool],k=1)[0]['item']
        iid=self.grant(template);item=self.item(iid)
        self.log('RARE FIND! '+item['name']+' — '+self.gear_stats(item)+'. This equipment cannot be bought in shops.','reward')
        self.p['inventory'].append(iid)
        self.log('Your rare find is safely in your bag.','reward')
        return iid

    def extra_snapshot(self,result):
        result=super().extra_snapshot(result)
        if result.get('room'):
            result['room']['shop']=[i for i in result['room'].get('shop',[]) if not self.w['items'][i].get('drop_only')]
        return result
