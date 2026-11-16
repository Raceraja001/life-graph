#!/usr/bin/env python3
import sys

path = '/mnt/h/DevTools/Projects/life-graph-ui-prod/src/data/loreCoordinates.ts'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

target = """    {
        slug: 'place-poompuhar-aranga-mandapam',
        name_en: 'Poompuhar Nataka Arangam & Kanalvari Seashore Esplanade',
        name_ta: 'பூம்புகார் நாடக அரங்கம் மற்றும் கானல்வரி நெய்தல் கடற்கரை',
        lat: 11.1512,
        lng: 79.8556,
        category: 'monument',
        thinai: 'neithal',
        era: 'Sangam & Classical Era',
        description: 'The historic performing arts center of imperial Kaveripattinam (Poompuhar), encompassing the royal proscenium dance theatre where Madhavi debuted before the Chola King and the coastal beach esplanade where the historic Kanalvari yazh recital took place.',
    },"""

addition = """    {
        slug: 'place-poompuhar-aranga-mandapam',
        name_en: 'Poompuhar Nataka Arangam & Kanalvari Seashore Esplanade',
        name_ta: 'பூம்புகார் நாடக அரங்கம் மற்றும் கானல்வரி நெய்தல் கடற்கரை',
        lat: 11.1512,
        lng: 79.8556,
        category: 'monument',
        thinai: 'neithal',
        era: 'Sangam & Classical Era',
        description: 'The historic performing arts center of imperial Kaveripattinam (Poompuhar), encompassing the royal proscenium dance theatre where Madhavi debuted before the Chola King and the coastal beach esplanade where the historic Kanalvari yazh recital took place.',
    },
    {
        slug: 'place-thirumayam-rock-fortress',
        name_en: 'Thirumayam Concentric Rock Fortress & Moated Citadel',
        name_ta: 'திருமயம் கருங்கல் கோட்டை மற்றும் பாறை அகழி அரண்',
        lat: 10.2458,
        lng: 78.7533,
        category: 'monument',
        thinai: 'mullai',
        era: 'Early Historic to Poligar Era',
        description: 'Concentric monolithic granite hill fortress in Pudukkottai featuring rock-cut moats, three circular ramparts, bastions, and 8th-century Pandya rock shrines.',
    },
    {
        slug: 'place-vembakottai-archaeological-site',
        name_en: 'Vembakottai Weapons Manufacturing Citadel',
        name_ta: 'வேம்பக்கோட்டை போர்க்கருவிகள் தொழிற்கூடம் மற்றும் அகழாய்வுத் தளம்',
        lat: 9.3361,
        lng: 77.7719,
        category: 'excavation',
        thinai: 'mullai',
        era: 'Iron Age to Sangam Era',
        description: 'Pre-historic martial citadel and weapons manufacturing center excavated along the Vaippar river, yielding hundreds of iron arrowheads, spears, and lapidary artifacts.',
    },"""

if target not in content:
    print("Error: Target not found in loreCoordinates.ts")
    sys.exit(1)

new_content = content.replace(target, addition, 1)
with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Successfully added place-thirumayam-rock-fortress and place-vembakottai-archaeological-site to loreCoordinates.ts (Reached 100 historical sites!)")
