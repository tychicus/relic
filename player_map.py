"""Per-character exploration memory and a deliberately small player-map payload."""


class PlayerMap:
    def remember_room(self):
        if not self.p or self.p['room'] not in self.w['rooms']:
            return
        visited = self.p.setdefault('explored_rooms', {})
        room = self.p['room']
        # Entering darkness records a square, but does not reveal its name.
        visited[room] = bool(visited.get(room) or self.visible(room))

    def player_map(self):
        if not self.p:
            return None
        visited = self.p.get('explored_rooms', {})
        ids = [rid for rid in visited if rid in self.w['rooms']]
        known = set(ids)
        rooms = []
        occupied = {tuple(self.w['rooms'][rid]['map_position']) for rid in ids if 'map_position' in self.w['rooms'][rid]}
        fallback_x = 0
        for rid in ids:
            room = self.w['rooms'][rid]
            position = room.get('map_position')
            if position is None:
                # Compatibility with old worlds: lay out only visited rooms.
                while (fallback_x, 3, 0) in occupied:
                    fallback_x += 1
                position = [fallback_x, 3, 0]
                occupied.add(tuple(position))
            rooms.append(dict(id=rid, name=room['name'] if visited[rid] else 'Unlit room',
                              region=room.get('region', '') if visited[rid] else '',
                              position=list(position),
                              exits={direction: dest for direction, dest in room['exits'].items() if dest in known}))
        # Never send enemy/NPC positions, room objects, loot, hidden exits to
        # unvisited rooms, or full-world bounds/counts to the map renderer.
        return dict(current=self.p['room'], rooms=rooms)

    def extra_snapshot(self, result):
        result = super().extra_snapshot(result)
        if self.p:
            result['exploration_map'] = self.player_map()
            # Exploration memory belongs to the save; expose only the filtered
            # map DTO in player responses, including when authored rooms vanish.
            result['player'].pop('explored_rooms', None)
        return result
