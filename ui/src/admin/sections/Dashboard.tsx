import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { firstKey, useEditor } from '../context'

export function Dashboard() {
  const { world, open } = useEditor()
  const cards: [group: string, title: string, description: string][] = [
    ['map', 'Visual world map', 'Select rooms, connect new places and export your map.'],
    ['regions', 'Regions & weather', 'Enemy banks, population caps, wandering, weather and fog.'],
    ['rooms', 'World locations', `${Object.keys(world.rooms).length} rooms · exits, shops, spawning and visibility.`],
    ['enemies', 'Creatures', `${Object.keys(world.enemies).length} creature types · combat, capture and harvest yields.`],
    ['npcs', 'People & dialogue', 'Place people and write their available conversations.'],
    ['skills', 'Skills & spells', 'Set eligibility, unlock levels, cooldowns and attached effects.'],
    ['status_effects', 'Status effects', 'Create reusable damage, stun and slow effects.'],
    ['items', 'Items & equipment', 'Weapons, shields, food, scrolls and containers.'],
    ['recipes', 'Cooking recipes', 'Ingredients, output, fires, tools and success chances.'],
    ['revision', 'Crafting & balance', 'Enchanting levels, duration, bonuses, risks, dual wielding, food and perception.'],
    ['settings', 'Combat & progression', 'Attack pulses, hit chances, XP and death penalties.'],
    ['learning', 'Abilities & learning', 'Learning points, rank bonuses and level requirements.'],
    ['mana', 'Mana & mastery', 'Mana recovery, long-term reserve growth and challenge practice bonuses.'],
  ]
  return (
    <div className="grid gap-4">
      <div className="grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(240px,1fr))]">
        {cards.map(([group, title, description]) => (
          <Card key={group} size="sm" className="bg-secondary/60">
            <CardHeader>
              <CardTitle>{title}</CardTitle>
              <CardDescription>{description}</CardDescription>
            </CardHeader>
            <CardFooter className="mt-auto bg-transparent">
              <Button variant="outline" size="sm" onClick={() => open(group, firstKey(world[group]))}>
                Open {title.toLowerCase()}
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>
      <CardContent className="px-0 text-sm text-muted-foreground">
        Quest chains, networked multiplayer, advanced NPC shops and the Moon expansion remain future work.
      </CardContent>
    </div>
  )
}
