"""Persistent regional populations. Looking never creates or moves creatures."""
class Regions:
    def update_world(self, new):
        # Publish content and migrate its populations under one world lock.
        with self.lock:
            super().update_world(new)

    def region_for(self, rid, spawning=False, world=None):
        world = self.w if world is None else world
        key = 'spawn_rooms' if spawning else 'rooms'
        return next(((ident, r) for ident, r in world.get('regions', {}).items() if rid in r.get(key, [])), (None, {}))

    def region_creatures(self):
        return [e for area in self.state.get('regional_populations', {}).values() for e in area['creatures'] if e['hp'] > 0]

    def fog_at(self, rid):
        return max(self.w['rooms'][rid].get('fog', 0), self.region_for(rid)[1].get('fog', 0))

    def prepare_regions(self):
        populations = self.state.setdefault('regional_populations', {})
        for ident, region in self.w.get('regions', {}).items():
            fresh = ident not in populations
            area = populations.setdefault(ident, dict(creatures=[], next_at=self.clock()+region.get('spawn_seconds', 60)))
            # Adopt existing residents intact, including wounds, targets and unconsciousness.
            # Old room rules remain authored but are overridden in managed spawn squares.
            migrated = False
            for rid in region.get('spawn_rooms', []):
                old = self.state['spawns'].pop(rid, None)
                slots = self.state['populations'].pop(rid, {})
                migrants = ([old] if old else []) + [s['creature'] for s in slots.values() if s.get('creature')]
                migrated = migrated or bool(migrants)
                for e in migrants:
                    if e['hp'] <= 0: continue
                    self.tag_creature(e, rid)
                    e['region'] = ident
                    area['creatures'].append(e)
            for e in area['creatures']:
                if e['hp'] > 0:
                    e['hp'] = min(e['hp'], self.w['enemies'][e['type']]['hp'])
            if fresh and not migrated:
                for _ in range(region.get('max_population', 0)):
                    if not self.spawn_regional(ident): break

    def regional_destinations(self, ident):
        region = self.w.get('regions', {}).get(ident, {})
        limit = region.get('max_per_room', 3)
        return [rid for rid in region.get('spawn_rooms', [])
                if not self.w['rooms'][rid].get('safe')
                and len(self.creatures(rid, True, False)) < limit]

    def spawn_regional(self, ident):
        region = self.w['regions'][ident]
        area = self.state['regional_populations'][ident]
        if sum(e['hp'] > 0 for e in area['creatures']) >= region.get('max_population', 0): return False
        rooms = self.regional_destinations(ident)
        pool = region.get('pool', [])
        if not rooms or not pool: return False
        chance = region.get('spawn_chance', 100)
        if chance < 100 and self.rng.random() >= chance/100: return False
        rid = self.rng.choice(rooms)
        eid = self.rng.choices(pool, weights=[p['weight'] for p in pool], k=1)[0]['enemy']
        e = self.spawn_creature(eid, rid)
        e.update(region=ident, roam_at=self.clock()+region.get('roam_seconds', 30))
        area['creatures'].append(e)
        if self.p and self.p['room'] == rid and self.visible(): self.log(self.creature_name(e)+' appears nearby.')
        return True

    def tick_regions(self):
        for ident, area in self.state.get('regional_populations', {}).items():
            region = self.w.get('regions', {}).get(ident)
            if not region: continue
            # Keep dead entries until their replacement delay expires; no offline burst.
            area['creatures'] = [e for e in area['creatures'] if e['hp'] > 0 or e.get('respawn_at', 0) > self.clock()]
            if self.clock() < area['next_at']: continue
            area['next_at'] = self.clock()+region.get('spawn_seconds', 60)
            if len(area['creatures']) < region.get('max_population', 0): self.spawn_regional(ident)

    def check_region_references(self, world):
        for ident, area in self.state.get('regional_populations', {}).items():
            alive = [e for e in area['creatures'] if e['hp'] > 0]
            region = world.get('regions', {}).get(ident, {})
            if alive and not region: raise ValueError('Cannot remove a region with living creatures.')
            for e in alive:
                if e['location'] not in region.get('spawn_rooms', []):
                    raise ValueError('Cannot remove an occupied regional spawn square.')
        for ident, region in world.get('regions', {}).items():
            alive=[e for e in self.region_creatures() if e.get('region')==ident]
            # Include room residents that will be adopted by a newly managed square.
            for rid in region.get('spawn_rooms', []):
                e=self.state['spawns'].get(rid)
                if e and e['hp']>0:alive.append(e)
                alive.extend(s['creature'] for s in self.state['populations'].get(rid,{}).values() if s.get('creature') and s['creature']['hp']>0)
            if len(alive)>region.get('max_population',0):
                raise ValueError('Regional population limit is below its living population. Defeat or capture creatures first.')
            for rid in region.get('spawn_rooms', []):
                if len(self.creatures(rid, True, False)) > region.get('max_per_room', 3):
                    raise ValueError('Per-square population limit is below its current population.')
