"""Equipment locations and carrying weight, including container contents."""
BODY_SLOTS=('helmet','armor','pants','arms')
SLOT_NAMES=dict(weapon='right hand',left_hand='left hand',helmet='helmet',armor='chest',pants='pants',arms='arms')
SLOT_ALIASES={'right':'weapon','right hand':'weapon','left':'left_hand','left hand':'left_hand','body':'armor','chest':'armor','head':'helmet','bracers':'arms','legs':'pants','shield':'left_hand'}


class Equipment:
    def show_equipment(self):
        equipped=self.p['equipment']
        right=self.item(equipped['weapon']) if equipped.get('weapon') else None
        lines=[]
        for slot,label in SLOT_NAMES.items():
            iid=equipped.get(slot)
            if iid:
                item=self.item(iid)
                text=item['name']+' — '+self.gear_stats(item)
                if item.get('hands',1)==2:text+=' · two-handed'
                if item.get('enchantment_description'):text+='\n  '+item['enchantment_description']
            elif slot=='left_hand' and right and right.get('hands',1)==2:
                text='occupied by '+right['name']+' · two-handed'
            else:
                text='boxers' if slot=='pants' else 'nothing'
            lines.append(label.capitalize()+': '+text)
        self.log('Equipment:\n'+'\n'.join(lines))
        self.log(f'Carrying {self.carried_weight():g}/{self.carry_capacity():g} lb, including worn equipment and container contents.')

    def item_weight(self,iid):
        inst=self.state.get('instances',{}).get(iid,{})
        if inst.get('kind')=='captive':return self.w['enemies'][inst['enemy']].get('weight',10)
        spec=self.w['items'][inst.get('item',iid)]
        weight=spec.get('weight',0)
        if inst.get('kind')=='chest':weight+=sum(self.item_weight(i) for i in inst['contents'])
        if inst.get('kind')=='cage' and inst.get('count'):weight+=inst['count']*self.w['enemies'][inst['enemy']].get('weight',10)
        return weight

    def carried_weight(self):
        return sum(self.item_weight(i) for i in self.p['inventory']+list(self.p['equipment'].values()))

    def carry_capacity(self):
        cls=self.w['classes'][self.p['class']]
        return cls.get('carry_capacity',60)+(self.p['level']-1)*cls.get('carry_per_level',2)

    def can_carry_weight(self,extra):
        # Existing over-limit saves remain playable; reducing or moving gear is allowed.
        return not self.rules()['weight_enabled'] or extra<=0 or self.carried_weight()+extra<=self.carry_capacity()+1e-9

    def can_carry(self,iid):return self.can_carry_weight(self.item_weight(iid))

    def require_carry_weight(self,extra):
        if not self.can_carry_weight(extra):
            raise ValueError(f'Too much weight. Carrying {self.carried_weight():g}/{self.carry_capacity():g} lb; this adds {extra:g} lb. Drop or store something first.')

    def require_carry(self,iid):self.require_carry_weight(self.item_weight(iid))

    def extra_command(self,verb,target):
        if verb=='equipment':
            self.show_equipment();return True
        if verb in ('weight','capacity'):
            self.log(f'Carrying {self.carried_weight():g}/{self.carry_capacity():g} lb, including worn gear and container contents. Capacity grows with character level.');return True
        return super().extra_command(verb,target)

    def extra_snapshot(self,result):
        result=super().extra_snapshot(result)
        if self.p:
            result['player'].update(carried_weight=self.carried_weight(),carry_capacity=self.carry_capacity(),weight_enabled=self.rules()['weight_enabled'])
            for iid,spec in list(result['items'].items()):result['items'][iid]=dict(spec,weight=self.item_weight(iid))
            result['player']['defense']=sum(self.item(i).get('armor',0) for slot,i in self.p['equipment'].items() if slot in BODY_SLOTS or self.item(i).get('shield'))
        return result
