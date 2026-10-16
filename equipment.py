"""Equipment locations and armor totals. Player inventory has no carrying limits."""
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

    def extra_command(self,verb,target):
        if verb=='equipment':
            self.show_equipment();return True
        if verb in ('weight','capacity'):
            self.log('Items have no carrying weight, and your bag has no item limit. Chests and cages retain their own storage capacities.');return True
        return super().extra_command(verb,target)

    def extra_snapshot(self,result):
        result=super().extra_snapshot(result)
        result['items']={iid:{key:value for key,value in item.items() if key!='weight'} for iid,item in result['items'].items()}
        if self.p:
            result['player']['defense']=sum(self.item(i).get('armor',0) for slot,i in self.p['equipment'].items() if slot in BODY_SLOTS or self.item(i).get('shield'))
        return result
