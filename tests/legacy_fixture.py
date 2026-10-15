"""Retain room-based encounter fixtures for pre-region regression tests."""
import json

def disable_regions(path):
    world=json.loads(path.read_text(encoding="utf-8"))
    world.pop("regions",None)
    # Isolate older mechanics tests from the new resource and challenge systems.
    world.setdefault("revision",{}).update(weight_enabled=False,learning_enabled=False,mana_enabled=False,player_bodies=False,practice_challenge_bonus=0,practice_harder_bonus=0)
    # Exercise the prior editable-world rules independently of new learning gates.
    for cls in world['classes'].values():cls.pop('starting_ability',None)
    for sid in ['swordplay','kick','power_strike','shattering_strike','executioner','cutthroat','nerve_strike','assassinate','frostbolt','arcane_lance','meteor']:
        world['skills'].pop(sid,None)
    for sid,level in dict(bash=1,charge=2,knockout=1,mend=2,lightning=4,hamstring=4,quickstrike=2,sharpening=2).items():
        world['skills'][sid]['unlock_level']=level
    for sid in ['fireball','lightning']:world['skills'][sid]['allowed_classes']=['mage']
    world['skills']['bash']['allowed_classes']=['warrior']
    world['skills']['charge']['allowed_classes']=['warrior']
    path.write_text(json.dumps(world),encoding="utf-8")
