#!/usr/bin/env python3
import sys

path = '/mnt/h/DevTools/Projects/life-graph-ui-prod/src/data/loreCoordinates.ts'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

target = """    {
        slug: 'place-vembakottai-archaeological-site',
        name_en: 'Vembakottai Weapons Manufacturing Citadel',
        name_ta: 'வேம்பக்கோட்டை போர்க்கருவிகள் தொழிற்கூடம் மற்றும் அகழாய்வுத் தளம்',
        lat: 9.3361,
        lng: 77.7719,
        category: 'monument',
        thinai: 'mullai',
        era: 'Iron Age to Sangam Era',
        description: 'Pre-historic martial citadel and weapons manufacturing center excavated along the Vaippar river, yielding hundreds of iron arrowheads, spears, and lapidary artifacts.',
    },"""

addition = """    {
        slug: 'place-vembakottai-archaeological-site',
        name_en: 'Vembakottai Weapons Manufacturing Citadel',
        name_ta: 'வேம்பக்கோட்டை போர்க்கருவிகள் தொழிற்கூடம் மற்றும் அகழாய்வுத் தளம்',
        lat: 9.3361,
        lng: 77.7719,
        category: 'monument',
        thinai: 'mullai',
        era: 'Iron Age to Sangam Era',
        description: 'Pre-historic martial citadel and weapons manufacturing center excavated along the Vaippar river, yielding hundreds of iron arrowheads, spears, and lapidary artifacts.',
    },
    {
        slug: 'place-madurai-aruvai-veethi',
        name_en: 'Madurai Aruvai Veethi: Ancient Textile Merchant Avenue',
        name_ta: 'மதுரை அறுவை வீதி - தொன்மையான துகில் வணிகப் பெருவீதி',
        lat: 9.9195,
        lng: 78.1198,
        category: 'monument',
        thinai: 'marutham',
        era: 'Sangam Early Historic Era',
        description: 'The legendary textile avenue and wholesale fabric bazaar of ancient Madurai, documented in Maduraikkanchi and Silappadikaram, where merchants displayed thousands of bundles of pure white muslins and dyed silks.',
    },"""

if target not in content:
    print("Error: Target not found in loreCoordinates.ts")
    sys.exit(1)

new_content = content.replace(target, addition, 1)
with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Successfully added place-madurai-aruvai-veethi to loreCoordinates.ts (Reached 101 historical sites!)")
