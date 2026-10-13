"""Configurable skills, eligibility, unlocks, and character choices."""
import math
from frontier import Frontier


def validate_abilities(w):
    def require(ok,message):
        if not ok:raise ValueError(message)
    for sid,skill in w['skills'].items():
        effect=skill.get('effect','knockout' if sid=='knockout' else 'damage')
        require(effect in ('damage','heal','knockout','enchant','sharpen'),'Choose a supported skill effect.')
        level=skill.get('unlock_level',1)
        require(type(level) is int and 1<=level<=100,'Skill unlock level must be a whole number from 1 to 100.')
        for key,group in [('allowed_classes','classes'),('allowed_races','races')]:
            if key not in skill or skill[key] is None:continue
            values=skill[key]
            require(isinstance(values,list) and all(isinstance(x,str) and x in w[group] for x in values),f'{key} must list existing choices, or be null for Any.')
            require(len(values)==len(set(values)),f'{key} cannot contain duplicates.')
        if effect=='heal':
            amount=skill.get('heal',20)
            require(type(amount) is int and 1<=amount<=10000,'Skill healing must be 1–10000 whole HP.')
        if effect=='knockout':
            chance=skill.get('chance',70)
            require(type(chance) in (int,float) and math.isfinite(chance) and 0<=chance<=100,'Knockout success chance must be 0–100 percent.')
    return w


class Abilities(Frontier):
    def skill_eligible(self,sid):
        skill=self.w['skills'][sid]
        # Old content retains class memberships until migrated or edited.
        classes=skill.get('allowed_classes',[cid for cid,c in self.w['classes'].items() if sid in c.get('skills',[])])
        races=skill.get('allowed_races')
        return (classes is None or self.p['class'] in classes) and (races is None or self.p['race'] in races)

    def require_skill(self,sid):
        if sid not in self.w['skills']:raise ValueError('That skill does not exist.')
        skill=self.w['skills'][sid]
        if not self.skill_eligible(sid):raise ValueError(f'{skill["name"]} is not available to your class and race.')
        if self.p['level']<skill.get('unlock_level',1):raise ValueError(f'{skill["name"]} unlocks at level {skill.get("unlock_level",1)}.')
        return skill

    def available_skill_ids(self):
        return [sid for sid,k in self.w['skills'].items() if self.skill_eligible(sid) and self.p['level']>=k.get('unlock_level',1)]

    def announce_skills(self,initial=False):
        if not self.p:return
        available=self.available_skill_ids()
        if initial and 'announced_skills' not in self.state:
            self.state['announced_skills']=available;return
        old=self.state.setdefault('announced_skills',[])
        for sid in available:
            if sid not in old:self.log('New skill unlocked: '+self.w['skills'][sid]['name']+'. Type SKILLS for details.','reward')
        # Eligibility can be changed by the owner. Re-unlocks should be announced.
        self.state['announced_skills']=available

    def match_skill(self,name):
        name=name.lower().strip()
        if not name:raise ValueError('Use CAST <skill name>, or SKILLS to see your abilities.')
        ids=list(self.w['skills'])
        exact=[sid for sid in ids if name in (sid.lower(),self.w['skills'][sid]['name'].lower())]
        found=exact or [sid for sid in ids if name in self.w['skills'][sid]['name'].lower()]
        if len(found)!=1:raise ValueError('Use a unique full skill name or its ID. Type SKILLS to see available skills.')
        return found[0]

    def activate_skill(self,sid,target=''):
        skill=self.require_skill(sid);effect=skill.get('effect','knockout' if sid=='knockout' else 'damage')
        if effect=='knockout':self.knockout(target,sid);return
        if effect=='damage':
            if not self.visible():raise ValueError('It is too dark to choose a target. Carry a light.')
            if not self.p['combat'] or not self.enemy():raise ValueError(skill['name']+' needs an active fight. ATTACK first.')
        elif self.p['hp']>=self.max_hp():raise ValueError('You already have full health. The skill is not spent.')
        left=self.p['cooldowns'].get(sid,0)-self.clock()
        if left>0:raise ValueError(f'{skill["name"]} is ready in {math.ceil(left)} seconds.')
        self.p['cooldowns'][sid]=self.clock()+skill['cooldown']
        if effect=='damage':self.strike(skill.get('multiplier',1),attack_name=skill['name'])
        else:
            amount=min(skill.get('heal',20),self.max_hp()-self.p['hp']);self.p['hp']+=amount
            self.log(f'{skill["name"]}: you recover {amount} HP.','reward')

    def skill_command(self,verb,target):
        if verb in ('skills','abilities'):
            rows=[]
            for sid,k in sorted(self.w['skills'].items(),key=lambda x:x[1]['name'].casefold()):
                if not self.skill_eligible(sid):continue
                level=k.get('unlock_level',1);status='available' if self.p['level']>=level else 'locked'
                rows.append(f'{k["name"]} — level {level}, {status}; cooldown {k["cooldown"]:g}s. CAST {sid}\n'+k.get('description',''))
            self.log('Skills:\n'+('\n'.join(rows) or 'No skills are available for your race and class.'));return True
        if verb in ('cast','skill'):
            self.activate_skill(self.match_skill(target));return True
        if verb in ('bash','knockout'):
            self.activate_skill(verb,target);return True
        return False

    def extra_snapshot(self,result):
        result=super().extra_snapshot(result)
        if self.p:
            result['player']['race_name']=self.w['races'][self.p['race']]['name']
            result['player']['class_name']=self.w['classes'][self.p['class']]['name']
            result['player_skills']=[dict(k,id=sid,effect=k.get('effect','knockout' if sid=='knockout' else 'damage'),unlocked=self.p['level']>=k.get('unlock_level',1)) for sid,k in sorted(self.w['skills'].items(),key=lambda x:x[1]['name'].casefold()) if self.skill_eligible(sid)]
        return result
