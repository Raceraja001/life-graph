#!/usr/bin/env python3
"""
Harvester: Batch 52 - Ancient Tamil Jackfruit Agroforestry, Pala-Maram Acoustic Timber Luthiery, Latex Adhesives & Mukkani Preservation
Generated automatically.
"""

import os
import json
import psycopg2
import requests

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL_NAME = "bge-m3:latest"
DOSSIER_DIR = "/mnt/h/DevTools/Projects/learn-ai/moolam-chronicles/knowledge"

# The knowledge tree uses real English plurals ("technologies", not "technologys").
CATEGORY_DIRS = {
    "technology": "technologies",
    "archaeology": "archaeology",
    "history": "history",
    "science": "science",
}


def category_dir(category: str) -> str:
    return CATEGORY_DIRS.get(category, category + "s")


DOSSIERS = [
    {
        "slug": "text-sangam-literature-on-ver-pala-cauliflorous-jackfruits-aasini-pala-and-mukkani-hospitality",
        "category": "text",
        "file": "text-sangam-literature-on-ver-pala-cauliflorous-jackfruits-aasini-pala-and-mukkani-hospitality.md",
        "name_en": "Sangam Poetic Accounts of Ver-Pala Root-Borne Jackfruits, Wild Aasini-Pala & Mukkani Feasts",
        "name_ta": "சங்க இலக்கியங்களில் வேர்ப்பலா, ஆசினிப் பலா மற்றும் முக்கனி விருந்தோம்பல் குறிப்புகள்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "kurinji",
        "summary_en": "Classical Tamil poetic accounts in Kurinjippattu, Akananuru, Natrinai, Purananuru, and Malaipadukadam celebrating gigantic cauliflorous jackfruits growing from exposed roots (ver-pala), main trunks (kaya-kan-pala), and high boughs (kombu-pala), wild mountain Artocarpus hirsutus (aasini-pala), and drum-like fruit resonance.",
        "summary_ta": "குறிஞ்சிப்பாட்டு, அகநானூறு, நற்றிணை, புறநானூறு மற்றும் மலைபடுகடாம் ஆகிய சங்க நூல்களில் வேர்ப்பலா, காய்க்கண் பலா, காட்டு ஆசினிப் பலா மற்றும் முழவு போல் தொங்கும் பலாப்பழங்கள் பற்றிய இலக்கியச் சான்றுகள்.",
        "sources": [
            "Kurinjippattu",
            "Akananuru",
            "Natrinai",
            "Purananuru",
            "Malaipadukadam"
        ],
        "content": "# Sangam Literature on Ver-Pala Cauliflorous Jackfruits, Aasini-Pala & Mukkani Hospitality\n\nIn the Sangam poetic landscape, *pala* (*Artocarpus heterophyllus*) is celebrated as the monumental centerpiece of *Kurinji* mountain slopes and *Marutham* orchard belts, as well as the middle member of the royal Tamil fruit trinity (**Mukkani**: *Maa, Pala, Vazhai*):\n\n**Poetic & Botanical Attestations (Cited by Title):**\n- **Three-Tier Cauliflory (*Ver-Pala, Kaya-Pala, Kombu-Pala*)**: Poems in *Akananuru*, *Natrinai*, and *Kurinjippattu* classify jackfruits by the anatomical locus of fruiting: massive fruits bursting directly from surface lateral roots resting in earth clefts (**வேர்ப்பலா** / *ver-pala*), medium syncarps hanging like barrel drums (*muzhavu*) along the main trunk, and smaller fruits borne on upper branches.\n- **Purananuru & Malaipadukadam (Muzhavu Simile & Aasini-Pala)**: Poets repeatedly compare the heavy, cylindrical jackfruit slung across a hillman's shoulder pole to a *Panar* percussionist's *muzhavu* drum—an uncanny foreshadowing of the jackfruit tree's role in carving *Mridangam* and *Thavil* shells. *Malaipadukadam* also distinguishes cultivated *perum-pala* from wild mountain *aasini-pala* (*Artocarpus hirsutus*), whose sweet arils feed wandering bards."
    },
    {
        "slug": "concept-artocarpus-heterophyllus-pala-heartwood-acoustic-impedance-and-luthiery-resonance",
        "category": "concept",
        "file": "concept-artocarpus-heterophyllus-pala-heartwood-acoustic-impedance-and-luthiery-resonance.md",
        "name_en": "Pala-Maram Heartwood Acoustic Impedance, Dimensional Stability & Flavone Oxidation in Luthiery",
        "name_ta": "பலா மர வைரக்கட்டையின் ஒலி அதிர்வு இயற்பியல் (Acoustic Impedance), பரிமாண நிலைப்புத்தன்மை மற்றும் வீணை-மிருதங்க இசைக்கருவியியல்",
        "era": "Early Medieval to Modern Era",
        "year_start": 600,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Wood physics and acoustic mechanics of seasoned Artocarpus heterophyllus heartwood (pala-maram): medium specific gravity (0.58–0.64), low tangential-to-radial shrinkage ratio (<1.5), high longitudinal sound velocity (~4800 m/s), and oxidative polymerization of artocarpin/morin flavones that stabilize resonant Veena, Mridangam, and Thavil shells.",
        "summary_ta": "பலா மரத்தின் வைரப்பகுதி சுருங்கி விரியாத தன்மையும், குறைந்த அடர்த்தியில் அதிக ஒலி வேகத்தைக் கடத்தும் இயற்பியல் பண்பும் கொண்டதால் தஞ்சாவூர் ஏகாந்த வீணை, மிருதங்கம் மற்றும் தவில் செய்யத் தேர்ந்தெடுக்கப்படும் அறிவியல்.",
        "sources": [
            "Acoustics of Indian Musical Instruments (C.V. Raman & S. Kumar)",
            "Wood Anatomy and Mechanical Properties of Artocarpus heterophyllus",
            "Thanjavur Veena Geographical Indication Technical Dossier"
        ],
        "content": "# Pala-Maram Heartwood Acoustic Impedance & Luthiery Resonance\n\nAcross South Indian organology, no timber rivals aged **pala-maram** (*Artocarpus heterophyllus*) heartwood for carving both chordophone resonators (*Thanjavur Veena*) and membranophone shells (*Mridangam*, *Thavil*, *Kanjira*, and *Udukkai*):\n\n**1. Vibro-Acoustic Parameters:**\n- **Acoustic Radiation Coefficient ($R = \\sqrt{E / \\rho^3}$)**: Seasoned jackfruit heartwood combines a moderate air-dry density ($\\rho \\approx 580\\text{--}640\\text{ kg/m}^3$) with a high longitudinal Young's modulus ($E_L \\approx 12\\text{--}14\\text{ GPa}$), yielding a longitudinal sound speed $c_L \\approx 4700\\text{--}4900\\text{ m/s}$ and low internal friction ($\\tan\\delta$). This allows a thin-walled ($8\\text{ mm}$) *Veena kudam* to radiate rich low-mid harmonics without metallic ring.\n- **Tyloses-Filled Vessels & Isotropic Stability**: The diffuse-porous heartwood vessels are plugged with natural **tyloses** and yellow phenolic resins. Its tangential-to-radial shrinkage ratio ($T/R \\approx 1.4$) is remarkably low, enabling a hollowed one-piece (*Ekanda*) log to survive extreme humidity swings without radial cracking.\n\n**2. Photochemical Flavone Aging (*Artocarpin & Morin*):**\n- Freshly cut *pala* heartwood is bright canary yellow due to **morin, artocarpin, and cyanomaclurin** prenylated flavones. Upon exposure to air and light, these polyphenols oxidatively cross-link into a deep golden-mahogany matrix that stiffens cell walls and repels wood-boring termites."
    },
    {
        "slug": "concept-pala-thatti-parthal-acoustic-ripeness-testing-and-varikka-vs-koozha-pectin-chemistry",
        "category": "concept",
        "file": "concept-pala-thatti-parthal-acoustic-ripeness-testing-and-varikka-vs-koozha-pectin-chemistry.md",
        "name_en": "Thatti-Parthal Impulse-Acoustic Ripeness Testing & Varikka vs Koozha Pectin Biochemistry",
        "name_ta": "பலாப்பழம் தட்டிப் பார்த்தல் ஒலி அதிர்வுப் பரிசோதனையும் வரிக்கை-கூழப்பலா பெக்டின் வேதியியலும்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Biophysics of non-destructive jackfruit maturity evaluation (thatti-parthal) and cultivar texture chemistry: how starch-to-sugar conversion and internal air-gap expansion shift percussion resonance from a high-frequency solid knock to a low-frequency hollow thud, alongside calcium-pectate cross-linking in firm Varikka vs soft Koozha arils.",
        "summary_ta": "பலாப்பழத்தைக் கத்திப் பிடியால் தட்டிப் பார்க்கும்போது ஏற்படும் வெற்று ஒலி அதிர்வைக் கொண்டு முதிர்ச்சியைக் கணிக்கும் இயற்பியலும், உறுதியான வரிக்கை மற்றும் மென்மையான கூழப்பலாச் சுளைகளின் பெக்டின் வேதியியலும்.",
        "sources": [
            "Non-Destructive Acoustic Impulse Testing of Tropical Syncarps",
            "Post-Harvest Biochemistry of Artocarpus heterophyllus (Varikka vs Koozha)",
            "Horticultural Monographs on Panruti Jackfruit Ecotypes"
        ],
        "content": "# Thatti-Parthal Acoustic Ripeness Testing & Varikka vs Koozha Pectin Chemistry\n\nBecause a $15\\text{--}40\\text{ kg}$ jackfruit syncarp is encased in a thick, spiny green-yellow perianth rind, Tamil orchardists assess physiological maturity prior to harvesting using non-destructive acoustic modal analysis (**thatti-parthal** — *தட்டிப் பார்த்தல்*) paired with spine-spacing inspection:\n\n**1. Impulse-Response Physics of *Thatti-Parthal*:**\n- Striking the equator of the fruit with a wooden knife handle excites the fundamental spherical shell-cavity mode ($f_0 \\propto \\sqrt{S / m}$, where $S$ is dynamic stiffness).\n- **Immature Fruit**: Tightly packed starchy perianth bulbs (*chulai*), turgid latex ducts, and rigid unyielding spines (*முள்*) transmit a fast compressive wave, producing a sharp, high-pitched metallic knock ($>350\\text{ Hz}$).\n- **Mature Harvest-Ready Fruit**: As amylases hydrolyze starch into sucrose/fructose ($20\\text{--}26^\\circ\\text{Brix}$), water migrates into the swelling arils, spines flatten and widen (*முள் விரிதல்*), and micro-air cavities open around the central core (*kaan*). Acoustic impedance drops sharply, shifting the percussion response to a deep, resonant hollow *dhup* ($130\\text{--}180\\text{ Hz}$) accompanied by volatile **ethyl 3-methylbutanoate** aroma.\n\n**2. Varikka vs Koozha Textural Biochemistry:**\n- **Varikka-Pala (*Muthandam*)**: High calcium-bridged insoluble protopectin and low polygalacturonase activity preserve crisp, non-mushy golden arils.\n- **Koozha-Pala**: Rapid enzymatic depolymerization of middle-lamella pectin yields soft, fibrous, juice-rich arils ideal for batters and *payasam*."
    },
    {
        "slug": "concept-pala-paal-cis-polyisoprene-latex-hydrophobicity-oil-solvation-and-palakottai-starch",
        "category": "concept",
        "file": "concept-pala-paal-cis-polyisoprene-latex-hydrophobicity-oil-solvation-and-palakottai-starch.md",
        "name_en": "Pala-Paal Polyisoprene Latex Hydrophobicity, Triglyceride Solvation & Palakottai Resistant Starch",
        "name_ta": "பலாப்பால் (பாலிஐசோபிரீன்) ஒட்டும் வேதியியல், நல்லெண்ணெய்க் கரைப்பானும் பலாக்கொட்டை மாவுச்சத்து உயிர்வேதியியலும்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Polymer chemistry of sticky white jackfruit latex (pala-paal) and seed nutrition: why water cannot wash off cis-1,4-polyisoprene and triterpene resin coagulum whereas non-polar sesame/coconut oil triglycerides plasticize and dissolve it via 'like dissolves like' solvation, alongside the high-amylose resistant starch of palakottai.",
        "summary_ta": "தண்ணீரில் கரையாத பலாப்பால் (cis-1,4-polyisoprene) பிசுக்கைத் தேங்காய் எண்ணெய் அல்லது நல்லெண்ணெய் தடவி எளிதில் நீக்கும் கரைப்பான் வேதியியலும், பலாக்கொட்டையின் உயர் அமிலோஸ் மாவுச்சத்து மற்றும் ஜாக்கலின் புரதச் சத்தும்.",
        "sources": [
            "Phytochemical Composition of Artocarpus heterophyllus Latex and Resins",
            "Starch Structure and Jacalin Lectin Biochemistry of Jackfruit Seeds",
            "Siddha Nutritional Classification of Palakottai"
        ],
        "content": "# Pala-Paal Polyisoprene Latex Chemistry & Palakottai Resistant Starch\n\nCutting a fresh jackfruit releases copious white latex (**pala-paal**) from severed laticifer vessels in the rind and central axis (*kaan*), governed by hydrophobic elastomer chemistry:\n\n**1. Hydrophobic Latex Coagulation & Oil Solvation (*எண்ணெய் தடவி அரிதல்*):**\n- **Chemical Composition**: *Pala-paal* is an aqueous emulsion of **$cis\\text{-1,4-polyisoprene}$** rubber chains ($8\\text{--}12\\%$), sticky **triterpene alcohol esters** ($\\alpha$-artostenone and cycloartenol, $60\\text{--}70\\%$ of dry resin), wax, and the galactose-binding lectin **jacalin**.\n- **Why Oil Prevents Adhesion**: When *pala-paal* contacts skin or steel, water evaporates and the non-polar polyisoprene-resin globules coalesce into a tenacious pressure-sensitive adhesive insoluble in water or soap. Coating the palms and knife blade with **gingelly oil (*nallenai*)** or **coconut oil** creates a low-energy non-polar triglyceride film ($\\delta_{H} \\approx 16.5\\text{ MPa}^{1/2}$, matching polyisoprene) that both prevents rubber wetting on steel and dissolves coagulated resin micelles for effortless wiping.\n\n**2. Palakottai (Jackfruit Seed) Nutritional Biochemistry:**\n- Each aril encloses a smooth, oblong seed coated in a parchment-like white spermoderm (*வெள்ளைத் தோல்*) and a brown phenolic testa. Rich in $25\\text{--}30\\%$ **Type-2 resistant amylose starch** and $13\\text{--}18\\%$ protein, roasted or boiled *palakottai* provides slow-release glycemic energy."
    },
    {
        "slug": "technology-pala-maram-kudam-hollowing-water-seasoning-and-pala-paal-wood-caulking",
        "category": "technology",
        "file": "technology-pala-maram-kudam-hollowing-water-seasoning-and-pala-paal-wood-caulking.md",
        "name_en": "Pala-Maram Log Water-Seasoning, Monolithic Kudam Adze-Gouging & Pala-Paal Latex Caulking",
        "name_ta": "பலா மரக் கட்டை நீர்ப்பதப்படுத்துதல், குடம்-மிருதங்கக் குடைசல் மற்றும் பலாப்பால் மெழுகுப் பூச்சுத் தொழில்நுட்பம்",
        "era": "Early Medieval to Modern Era",
        "year_start": 600,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Master woodworking and luthiery craft of Artocarpus heterophyllus timber: selecting senescent village-grown trees, water- and shade-seasoning green billets, lathe-turning exterior profiles and gouging thin-walled Veena kudam bowls and Thavil shells with curved adzes (vaachi), and sealing micro-pores with boiled pala-paal latex putty.",
        "summary_ta": "முதிர்ந்த பலா மரங்களைத் தேர்ந்தெடுத்து நிழலில் உலர்த்தி, வளைந்த வாச்சியால் குடைந்து தஞ்சாவூர் வீணைக் குடம் மற்றும் தவில் கட்டை உருவாக்கும் நுட்பமும், பலாப்பால் காய்ச்சி மரத்துளை அடைக்கும் மெழுகு முறையும்.",
        "sources": [
            "Craft Documentation of Thanjavur Veena & Valangaiman Thavil Makers",
            "Traditional Musical Instrument Woodworking of Tamil Nadu",
            "Indigenous Wood Adhesives and Caulking Compounds of South India"
        ],
        "content": "# Pala-Maram Log Seasoning, Monolithic Kudam Gouging & Pala-Paal Caulking\n\nTransforming a massive green jackfruit trunk into a feather-light, crack-free *Thanjavur Veena* or *Valangaiman Thavil* shell requires a multi-year seasoning and subtractive carving workflow:\n\n**1. Tree Selection & Shade-Cure Seasoning:**\n- Luthiers prefer 60-to-100-year-old *pala-maram* trees grown in village homesteads or tank bunds (where slow growth produces tight, interlocked grain and deep orange heartwood) over fast-grown forest trees.\n- After felling, outer pale sapwood (*வெள்ளை மரம்*) is hewn away immediately. Rough-roughed billets are sealed at both end-grains with cow dung and mud to prevent rapid end-checking, then cured in shaded, ventilated lofts for $1\\text{--}3\\text{ years}$.\n\n**2. Monolithic Adze & Gouge Excavation (*Kudam-Kudaithal*):**\n- For an **Ekanda Veena**, a single $1.5\\text{ m}$ block is carved into bowl (*kudam*), neck (*dandi*), and dragon scroll (*yali*). Using curved hollowing adzes (**உள் வாச்சி**) and long-handled spoon gouges (*வளைவு உளி*), the artisan scoops out the interior through the top opening, checking wall thickness ($8\\text{--}10\\text{ mm}$) by holding the bowl against sunlight and tapping with knuckles for uniform pitch across quadrants.\n- For **Thavil** and **Mridangam** shells, a solid cylinder is bored longitudinally and turned on a heavy axle lathe.\n\n**3. Boiled Pala-Paal Latex Putty (*Pala-Mezhugu*):**\n- Raw *pala-paal* latex boiled over a low fire with a drop of sesame oil and fine brick dust or *jathikkai* powder polymerizes into a waterproof, elastic putty used to seal pin-knots in wooden resonators and bird-trapping twigs."
    },
    {
        "slug": "technology-oil-anointed-pala-butchery-chulai-preserve-drying-and-sand-bed-palakottai-storage",
        "category": "technology",
        "file": "technology-oil-anointed-pala-butchery-chulai-preserve-drying-and-sand-bed-palakottai-storage.md",
        "name_en": "Oil-Anointed Jackfruit Butchery, Pala-Vathal Sun-Dehydration & Sand-Bed Palakottai Storage",
        "name_ta": "எண்ணெய் தடவிப் பலா அரிதல், பலா வத்தல் உலர்த்தல், பலாச்சுளை வரட்டி மற்றும் மணலில் பலாக்கொட்டை சேமிக்கும் நுட்பம்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Post-harvest culinary engineering and seasonal preservation of jackfruit: oil-lubricated sectioning and latex-core excision (kaan-neekkuthal), sun-drying brined unripe arils into crisp pala-vathal, cooking ripe arils with palm jaggery into shelf-stable chulai-varatti, and stratifying palakottai seeds in dry river sand.",
        "summary_ta": "நல்லெண்ணெய் தடவிப் பலாப்பழத்தை அரிந்து நடுத்தண்டை நீக்கும் முறையும், பலா வத்தல், கருப்பட்டி சேர்ந்த பலாச்சுளை வரட்டி தயாரிப்பும், உலர்ந்த ஆற்று மணலில் பலாக்கொட்டைகளைப் புதைத்துப் பல மாதங்கள் சேமிக்கும் தொழில்நுட்பமும்.",
        "sources": [
            "Traditional Food Preservation Systems of Tamil Nadu",
            "Culinary Ethnobotany of the Gadilam & Kaveri Basins",
            "Post-Harvest Management of Jackfruit in South India"
        ],
        "content": "# Oil-Anointed Jackfruit Butchery, Pala-Vathal Drying & Sand-Bed Seed Storage\n\nBecause the main *Vaikasi–Aani* (May–July) jackfruit harvest produces a massive glut of perishable syncarps within eight weeks, Tamil households developed specialized butchery and multi-month preservation technologies:\n\n**1. Oil-Lubricated Sectioning & Core Excision (*Kaan-Eduthal*):**\n- Before cutting, the butcher rubs *nallenai* or coconut oil over hands, forearms, and the broad blade of the **pala-kathi**, and spreads dried plantain leaves or waste paper beneath the fruit.\n- The syncarp is halved lengthwise, and the latex-gorged central pith axis (**kaan** / *நடுத்தண்டு*) is sliced out along a V-trench and wiped with a dry paddy-straw wisp (*வைக்கோல் திரி*) that absorbs exuding *pala-paal* instantly. Ripe golden *chulai* bulbs are then popped free from the fibrous sterile perianth ribbons (*சக்கை*) and seeded.\n\n**2. Pulp Preservation (*Pala-Vathal & Chulai-Varatti*):**\n- **Pala-Vathal**: Mature unripe green *Varikka* bulbs are sliced into strips, steam-blanched for 3 minutes with turmeric and rock salt, and sun-dried on bamboo *thatti* mats until horn-hard for year-round frying.\n- **Pala-Chulai-Varatti (Halwa/Preserve)**: Ripe *chulai* pulp is slow-simmered in a heavy *uruli* with palm jaggery (*karuppatti*), ghee, dry ginger (*chukku*), and cardamom until water activity drops below $0.65$, keeping for 6–12 months.\n\n**3. Dry Sand-Bed Seed Stratification (*Manalil-Puthaitthal*):**\n- Fresh *palakottai* seeds lose moisture and shrivel within 10 days if left in open air, or sprout/rot if sealed wet. Washed, surface-dried seeds are layered alternatingly with bone-dry quartz river sand inside a corner floor bay or earthen pot (*மண்பானை*)—maintaining dormantly cool, breathable humidity so seeds remain plump for roasting and *சாம்பார் / பொரியல்* curries through the *Karthigai* monsoon."
    },
    {
        "slug": "artifact-monolithic-pala-maram-veena-kudam-thavil-barrels-and-carved-manai-planks",
        "category": "artifact",
        "file": "artifact-monolithic-pala-maram-veena-kudam-thavil-barrels-and-carved-manai-planks.md",
        "name_en": "Monolithic Pala-Maram Veena Kudams, Thavil & Mridangam Shells, Kanjira Frames & Manai-Palagai",
        "name_ta": "பலா மர ஏகாந்த வீணைக் குடம், தவில் மற்றும் மிருதங்கக் கட்டை, கஞ்சிரா வட்டம் மற்றும் மங்கலப் பலாப் பலகை",
        "era": "Early Medieval to Modern Era",
        "year_start": 600,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Classical musical instruments and auspicious domestic woodwork crafted exclusively from seasoned Artocarpus heterophyllus heartwood: one-piece Ekanda Thanjavur Veena resonators, thin-walled Valangaiman Thavil and Thanjavur Mridangam barrels, Kanjira frame hoops, and sacred wedding seats (manai-palagai).",
        "summary_ta": "பலா மர வைரக்கட்டையால் செய்யப்படும் இசை மற்றும் மங்கலப் பொருட்கள்: தஞ்சாவூர் ஏகாந்த வீணை, வலங்கைமான் தவில், மிருதங்கம், கஞ்சிரா சட்டம் மற்றும் திருமண சடங்குகளில் மணமக்கள் அமரும் பலாப் பலகை (மணை).",
        "sources": [
            "Musical Instruments of South India (S. Krishnaswami)",
            "Geographical Indication Registry: Thanjavur Veena & Bobbili/Tanjore Percussion",
            "Ritual Woodwork of Tamil Households"
        ],
        "content": "# Pala-Maram Veena Kudams, Thavil Barrels, Kanjira Frames & Manai-Palagai\n\nSeasoned golden-mahogany *pala-maram* heartwood is embodied in four iconic classes of Tamil cultural artifacts:\n\n**Artifact Typology:**\n1. **Thanjavur Ekanda & Ottu Veena Resonators**: In the **Ekanda Veena**, the hemispherical resonator bowl (*kudam*, $35\\text{ cm}$ diameter), hollow bridge-table (*palagai*), tapering neck (*dandi*), and *yali* headstock are sculpted from a single seamless log of Panruti/Thanjavur jackwood, prized for its warm sustain and floral chip-carved relief.\n2. **Valangaiman Thavil & Thanjavur Mridangam Shells**:\n   - **Thavil-Kattai**: A barrel-shaped jackwood shell turned to a remarkably thin $6\\text{--}8\\text{ mm}$ wall with raised central reinforcing bands, enduring extreme hoop tension from the hemp/leather *vaar* straps when struck with both a hardwood stick (*குச்சி*) and thimbled fingers.\n   - **Mridangam-Kattai**: A heavier asymmetric biconical jackwood cylinder whose internal throat (*உள் வாய்*) is scraped to tune air-cavity Helmholtz resonance with the *karanai* black-paste heads.\n3. **Kanjira & Udukkai Frames**: Bent or turned single-piece jackwood rings ($18\\text{ cm}$ diameter) fitted with bronze jingles.\n4. **Manai-Palagai (Auspicious Low Ritual Seats)**: Because the latex-bearing jackfruit tree is revered as a *Yajna-Vriksha* of fertility and purity, low rectangular seats (*மணைப் பலகை*) used by brides, grooms, and daily worshippers are planed from knot-free *pala* heartwood without iron nails."
    },
    {
        "slug": "artifact-pala-kathi-harvesting-knives-kombu-vadi-slings-pala-vathal-and-roasted-palakottai",
        "category": "artifact",
        "file": "artifact-pala-kathi-harvesting-knives-kombu-vadi-slings-pala-vathal-and-roasted-palakottai.md",
        "name_en": "Pala-Kathi Splitting Knives, Coir Lowering Slings, Crisp Pala-Vathal & Roasted Palakottai",
        "name_ta": "பலா அரிவாள், கயிற்றுத் தூக்கு வலை, பலா வத்தல், பலாச்சுளை வரட்டி மற்றும் சுட்ட பலாக்கொட்டைகள்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Orchard harvesting gear, butchery cutlery, and preserved food artifacts of the Tamil jackfruit tradition: long-handled stalk-cutting billhooks (thuratti-aruval), braided coir lowering cradles (thookku-vadi) for descending 30 kg ripe fruits intact, broad straight-edged splitting knives (pala-kathi), and dried pala-vathal.",
        "summary_ta": "பலா அறுவடை மற்றும் உணவுப் பொருட்கள்: காம்பு அறுக்கும் துரட்டி அரிவாள், பழம் உடையாமல் இறக்கும் கயிற்று வலை (தூக்கு வடி), அகன்ற பலாக் கத்தி, வெயிலில் உலர்த்திய பலா வத்தல் மற்றும் தணலில் சுட்ட பலாக்கொட்டை.",
        "sources": [
            "Horticultural Tools of Cuddalore & Kanyakumari Districts",
            "Traditional Culinary Artifacts of Tamil Nadu",
            "Geographical Indication Dossier: Panruti Jackfruit"
        ],
        "content": "# Pala-Kathi Splitting Knives, Coir Lowering Slings, Pala-Vathal & Palakottai\n\nHarvesting and processing heavy, latex-rich jackfruits without bruising the delicate internal *chulai* relies on specialized orchard tackle and culinary artifacts:\n\n**1. Orchard Harvesting & Butchery Implements:**\n- **Thookku-Vadi / Kombu-Koodai (Coir Lowering Sling)**: If a ripe $20\\text{--}35\\text{ kg}$ jackfruit drops from a $10\\text{ m}$ branch onto the ground, it splits open and ferments within hours. Climbers slip a braided 3-strand coir rope net (**தூக்கு வலை / வடி**) under the fruit's base, pass the rope over an upper fork pulley, sever the woody peduncle (*காம்பு*) with a sharp **pala-aruval**, and lower the fruit gently into waiting hands.\n- **Pala-Kathi (Broad Splitting Knife)**: A long ($35\\text{--}45\\text{ cm}$), thin-spined, straight-edged steel blade with minimal belly and a long tang set in a turned hardwood handle—designed to slice cleanly through a $40\\text{ cm}$ syncarp in a single two-handed downward stroke once lubricated with gingelly oil.\n\n**2. Preserved Culinary Artifacts:**\n- **Pala-Vathal & Kottai-Vadam**: Ivory-yellow sun-cured strips of mature unripe *chulai* and spiced *palakottai* mash wafers stored in terracotta jars.\n- **Thanalil-Sutta Palakottai (Ember-Roasted Seeds)**: Whole seeds buried in hot wood-ash embers (*அடுப்புத் தணல்*) after cooking until the outer husk chars and pops, revealing a chestnut-like, smoky yellow kernel."
    },
    {
        "slug": "institution-gadilam-pala-thoppu-orchard-tenures-thavil-timber-suppliers-and-panruti-mundis",
        "category": "institution",
        "file": "institution-gadilam-pala-thoppu-orchard-tenures-thavil-timber-suppliers-and-panruti-mundis.md",
        "name_en": "Gadilam Pala-Thoppu Orchard Tenures, Fruit-Thinning Norms, Luthier Timber Supply & Panruti Mundis",
        "name_ta": "கெடிலம் பலாத்தோப்பு சாகுபடி மரபுகள், காய் கலைத்தல் விதி, இசைக்கருவி மர வணிகம் மற்றும் பண்ருட்டி பலா மண்டிகள்",
        "era": "Medieval to Modern Era",
        "year_start": 800,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Agrarian and commercial institutions governing the Tamil jackfruit economy: hereditary Pala-Thoppu orchard management including young-syncarp thinning (kaai-kalaithal) and protective basket-wrapping, seasonal tree-yield lease auctions (pala-kuthagai), Panruti wholesale commission mundis, and luthier timber supply networks.",
        "summary_ta": "பலாத்தோப்புப் பராமரிப்பு முறைகள்: தரமான பெரிய பழங்களைப் பெறக் காய் கலைத்தல், பனையோலைக் கூடை கொண்டு பழம் மூடுதல், மரக் குத்தகை ஏலம், பண்ருட்டி பலா மண்டிகள் மற்றும் தஞ்சாவூர் வீணை-தவில் கலைஞர்களுக்கு மரம் வழங்கும் வணிக வலைப்பின்னல்.",
        "sources": [
            "South Arcot / Cuddalore District Gazetteer (Horticulture & Trade)",
            "Panruti Jackfruit Farmers & Commission Agents Association Records",
            "Supply Chain of Traditional Musical Instrument Timber in Tamil Nadu"
        ],
        "content": "# Gadilam Pala-Thoppu Orchard Tenures, Luthier Timber Supply & Panruti Mundis\n\nThe Cuddalore–Panruti jackfruit belt operates through a specialized agro-commercial ecosystem linking orchard agronomists, seasonal fruit graders, and classical musical instrument workshops:\n\n**1. Orchard Agronomy & *Kaai-Kalaithal* (Selective Fruit Thinning):**\n- A mature *pala-maram* in the Gadilam belt initiates $80\\text{--}150$ female inflorescences (*பிஞ்சு*) in *Thai–Masi*. Experienced orchardists practice rigorous **kaai-kalaithal** (pruning away deformed, branch-tip, and overcrowded young syncarps sold as culinary *முசு / பலாப் பிஞ்சு* vegetable), leaving only $10\\text{--}20$ well-spaced main-trunk and root fruits per tree so each swells into a prized $25\\text{--}45\\text{ kg}$ exhibition-grade fruit.\n- Developing root-borne fruits (*வேர்ப்பலா*) are cradled in woven palmyra-leaf baskets or gunny sacks dusted with ash to shield them from jackals, wild boars, and sun-scald.\n\n**2. Pala-Mundi Commission Yards & Acoustic Timber Guilds:**\n- During the * சித்திரை–ஆனி* peak season, hundreds of bullock carts and lorries converge on the **Panruti and Melpattambakkam Pala-Mundis**, where expert acoustic graders (*தட்டிப் பார்ப்பவர்*) sort *Varikka* vs *Koozha* loads within seconds.\n- When senescent 70-year-old orchard trees cease fruiting, specialized timber brokers (*மர வியாபாரிகள்*) fell and rough-season the trunks specifically for dispatch to the *Veena* workshops of Thanjavur and the *Thavil* lathe-turners of Valangaiman and Narasingapettai."
    },
    {
        "slug": "place-melpattambakkam-ancient-gadilam-jackfruit-grove-and-pala-timber-haven",
        "category": "place",
        "file": "place-melpattambakkam-ancient-gadilam-jackfruit-grove-and-pala-timber-haven.md",
        "name_en": "Melpattambakkam–Panruti: Ancient Gadilam Red-Loam Jackfruit Grove & Pala Timber Haven",
        "name_ta": "மேல்பட்டாம்பாக்கம்-பண்ருட்டி - கெடிலம் செம்மண் பலாத்தோப்புகள் மற்றும் இசைக்கருவிப் பலா மரத் தளம்",
        "era": "Early Medieval to Modern Era",
        "year_start": 700,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Historic orchard town on the Gadilam River plain near Panruti in Cuddalore district (lat 11.7780, lng 79.6220, thinai: marutham), celebrated with a Geographical Indication (GI) tag for its deep Cuddalore-sandstone red lateritic loam soils that yield Tamil Nadu's sweetest Varikka jackfruits and finest acoustic pala-maram timber.",
        "summary_ta": "கடலூர் மாவட்டம் பண்ருட்டி அருகே கெடிலம் ஆற்றுப் படுகையில் அமைந்துள்ள மேல்பட்டாம்பாக்கம் (lat 11.7780, lng 79.6220, மருதத் திணை): செம்மண் வளத்தால் விளையும் புவிசார் குறியீடு பெற்ற சுவையான வரிக்கைப் பலாப்பழங்களுக்கும், வீணை-மிருதங்கம் செய்யும் பலா மரங்களுக்கும் புகழ்பெற்ற வரலாற்றுத் தளம்.",
        "sources": [
            "Geographical Indication Registry: Panruti Jackfruit (Melpattambakkam–Panruti Belt)",
            "South Arcot District Manual (J.H. Garstin)",
            "Geology of the Tertiary Cuddalore Sandstone & Red Loam Formations"
        ],
        "content": "# Melpattambakkam–Panruti: Ancient Gadilam Jackfruit Grove & Pala Timber Haven\n\nSituated at `lat 11.7780, lng 79.6220` along the northern terrace of the **Gadilam River** between Panruti and Nellikuppam in Cuddalore district (historic *Thiruvathigai–Nadunadu* agrarian core), **Melpattambakkam** and its surrounding villages (*Kattandi, மாளிகைமேடு, Kadampuliyur*) form the heart of the GI-tagged **Panruti Jackfruit** agroforestry zone:\n\n**Geological & Pomological Distinction:**\n- **Cuddalore Sandstone Red Lateritic Loam (*செம்மண் வண்டல்*)**: Because *Artocarpus heterophyllus* is highly sensitive to root-zone waterlogging (which suffocates feeder roots within 48 hours), the deep, porous, iron-oxide-rich **Mio-Pliocene Cuddalore Sandstone red sandy-loam** spanning Melpattambakkam and Panruti provides rapid vertical drainage during Northeast monsoon cloudbursts while allowing taproots to reach sweet sub-artesian Gadilam groundwater at $6\\text{--}10\\text{ m}$ depth.\n- **Honey-Sweet *Panruti Varikka* & Acoustic Heartwood**: This unique soil-water chemistry produces giant $20\\text{--}50\\text{ kg}$ syncarps packed with up to 150 thick, golden-orange, low-latex *Varikka chulai* bulbs ($24\\text{--}28^\\circ\\text{Brix}$) celebrated across Tamil proverbs (*'பண்ருட்டி பலா'*), while its century-old orchard trunks supply the dense, resonant golden heartwood carved by Thanjavur *Veena* and *Mridangam* luthiers."
    }
]

EDGES = [
    [
        "text-sangam-literature-on-ver-pala-cauliflorous-jackfruits-aasini-pala-and-mukkani-hospitality",
        "describes",
        "concept-pala-thatti-parthal-acoustic-ripeness-testing-and-varikka-vs-koozha-pectin-chemistry",
        "material_culture",
        "Sangam to Modern Era",
        "Akananuru, Natrinai, and Purananuru celebrate root-borne ver-pala and trunk-borne jackfruits resonating like muzhavu drums.",
        "Purananuru & Akananuru"
    ],
    [
        "text-sangam-literature-on-ver-pala-cauliflorous-jackfruits-aasini-pala-and-mukkani-hospitality",
        "foreshadows",
        "artifact-monolithic-pala-maram-veena-kudam-thavil-barrels-and-carved-manai-planks",
        "material_culture",
        "Sangam to Modern Era",
        "Sangam poetic comparisons between hanging jackfruits and muzhavu drums mirror the carving of Mridangam and Thavil shells from pala heartwood.",
        "Malaipadukadam"
    ],
    [
        "concept-artocarpus-heterophyllus-pala-heartwood-acoustic-impedance-and-luthiery-resonance",
        "underpins",
        "technology-pala-maram-kudam-hollowing-water-seasoning-and-pala-paal-wood-caulking",
        "material_culture",
        "Early Medieval to Modern Era",
        "Low radial-to-tangential shrinkage and tyloses-plugged vessels enable luthiers to hollow one-piece Veena kudams and Thavil shells without cracking.",
        "Thanjavur Veena GI Dossier"
    ],
    [
        "concept-pala-thatti-parthal-acoustic-ripeness-testing-and-varikka-vs-koozha-pectin-chemistry",
        "guides",
        "institution-gadilam-pala-thoppu-orchard-tenures-thavil-timber-suppliers-and-panruti-mundis",
        "material_culture",
        "Medieval to Modern Era",
        "Impulse-acoustic ripeness testing (thatti-parthal) and Varikka vs Koozha grading govern wholesale transactions at Panruti Pala-Mundis.",
        "Panruti GI Dossier"
    ],
    [
        "concept-pala-paal-cis-polyisoprene-latex-hydrophobicity-oil-solvation-and-palakottai-starch",
        "explains",
        "technology-oil-anointed-pala-butchery-chulai-preserve-drying-and-sand-bed-palakottai-storage",
        "material_culture",
        "Sangam to Modern Era",
        "Non-polar triglyceride solvation of cis-1,4-polyisoprene latex explains why gingelly or coconut oil is rubbed on hands and pala-kathi knives before cutting.",
        "Phytochemistry Studies"
    ],
    [
        "technology-pala-maram-kudam-hollowing-water-seasoning-and-pala-paal-wood-caulking",
        "produces",
        "artifact-monolithic-pala-maram-veena-kudam-thavil-barrels-and-carved-manai-planks",
        "material_culture",
        "Early Medieval to Modern Era",
        "Shade-seasoning, curved-adze gouging, and lathe turning of mature jackwood logs produce Ekanda Veena resonators, Thavil barrels, and manai seats.",
        "Musical Instruments of South India"
    ],
    [
        "technology-oil-anointed-pala-butchery-chulai-preserve-drying-and-sand-bed-palakottai-storage",
        "utilizes",
        "artifact-pala-kathi-harvesting-knives-kombu-vadi-slings-pala-vathal-and-roasted-palakottai",
        "material_culture",
        "Sangam to Modern Era",
        "Harvesting and preserving jackfruits rely on coir thookku-vadi lowering slings, broad oil-coated pala-kathi blades, and sun-dried pala-vathal.",
        "Traditional Food Preservation"
    ],
    [
        "institution-gadilam-pala-thoppu-orchard-tenures-thavil-timber-suppliers-and-panruti-mundis",
        "supplies_timber_for",
        "artifact-monolithic-pala-maram-veena-kudam-thavil-barrels-and-carved-manai-planks",
        "material_culture",
        "Medieval to Modern Era",
        "Orchard timber guilds supply seasoned 70-year-old fruit-spent jackwood trunks to Thanjavur Veena and Valangaiman Thavil makers.",
        "Cuddalore District Gazetteer"
    ],
    [
        "institution-gadilam-pala-thoppu-orchard-tenures-thavil-timber-suppliers-and-panruti-mundis",
        "operates_in",
        "place-melpattambakkam-ancient-gadilam-jackfruit-grove-and-pala-timber-haven",
        "material_culture",
        "Early Medieval to Modern Era",
        "Hereditary Pala-Thoppu orchardists and wholesale Pala-Mundi yards anchor the economy of Melpattambakkam and Panruti along the Gadilam River.",
        "South Arcot District Manual"
    ],
    [
        "place-melpattambakkam-ancient-gadilam-jackfruit-grove-and-pala-timber-haven",
        "yields",
        "artifact-pala-kathi-harvesting-knives-kombu-vadi-slings-pala-vathal-and-roasted-palakottai",
        "material_culture",
        "Early Medieval to Modern Era",
        "The red lateritic sandy-loam orchards of Melpattambakkam and Panruti yield honey-sweet Varikka syncarps, pala-vathal, and starchy palakottai seeds.",
        "Panruti Jackfruit GI Registry"
    ]
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=== Phase 1: Markdown Dossiers ===")
    for d in DOSSIERS:
        cat_dir = os.path.join(DOSSIER_DIR, category_dir(d["category"]))
        os.makedirs(cat_dir, exist_ok=True)
        filepath = os.path.join(cat_dir, d["file"])
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(d["content"].strip() + "\n")
        print(f"Wrote dossier: {filepath}")

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("=== Phase 2: Lore Nodes Upsert ===")
    for d in DOSSIERS:
        props = json.dumps({"category": d["category"], "canonical_file": d["file"]})
        cur.execute("""
            INSERT INTO lore_nodes (slug, node_type, name_en, name_ta, era, year_start, year_end, thinai, summary_en, summary_ta, sources, layer, properties)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (slug) DO UPDATE SET
                node_type = EXCLUDED.node_type,
                name_en = EXCLUDED.name_en,
                name_ta = EXCLUDED.name_ta,
                era = EXCLUDED.era,
                year_start = EXCLUDED.year_start,
                year_end = EXCLUDED.year_end,
                thinai = EXCLUDED.thinai,
                summary_en = EXCLUDED.summary_en,
                summary_ta = EXCLUDED.summary_ta,
                sources = EXCLUDED.sources,
                layer = EXCLUDED.layer,
                properties = EXCLUDED.properties;
        """, (
            d["slug"], d["category"], d["name_en"], d["name_ta"], d["era"],
            d["year_start"], d["year_end"], d["thinai"], d["summary_en"],
            d["summary_ta"], d["sources"], "material_culture", props
        ))
        print(f"Upserted node: {d['slug']}")
    conn.commit()

    print("=== Phase 3: Lore Edges Insert ===")
    for edge in EDGES:
        src, rel, tgt, layer, era, desc, ev = edge
        cur.execute("""
            SELECT 1 FROM lore_edges
            WHERE source_slug = %s AND relation_type = %s AND target_slug = %s
        """, (src, rel, tgt))
        if cur.fetchone() is None:
            cur.execute("""
                INSERT INTO lore_edges (source_slug, relation_type, target_slug, layer, era, description, evidence_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (src, rel, tgt, layer, era, desc, ev))
            print(f"Inserted edge: {src} -> {tgt} ({rel})")
        else:
            print(f"Edge exists: {src} -> {tgt} ({rel})")
    conn.commit()

    print("=== Phase 4: RAG Chunks Embedding ===")
    for d in DOSSIERS:
        title = d["name_en"]
        slug = d["slug"]
        cur.execute("DELETE FROM rag_chunks WHERE node_slug = %s", (slug,))
        text_en = d["summary_en"] + " " + d["content"][:800]
        emb_en = get_embedding(text_en)
        cur.execute("""
            INSERT INTO rag_chunks (node_slug, shelf, language, title, content, source_ref, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (slug, d["category"], "en", title + " (Overview)", text_en, d["sources"][0] if d["sources"] else "Oral Tradition", emb_en))

        text_ta = d["summary_ta"] + " " + d["name_ta"]
        emb_ta = get_embedding(text_ta)
        cur.execute("""
            INSERT INTO rag_chunks (node_slug, shelf, language, title, content, source_ref, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (slug, d["category"], "ta", d["name_ta"] + " (கண்ணோட்டம்)", text_ta, d["sources"][0] if d["sources"] else "Oral Tradition", emb_ta))
        print(f"Embedded 2 chunks for: {slug}")
    conn.commit()

    cur.close()
    conn.close()
    print("=== Harvester Complete! ===")

if __name__ == "__main__":
    main()
