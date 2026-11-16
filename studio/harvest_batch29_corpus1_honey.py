#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Apiculture & Cliff Honey Gathering
import os
import sys
import json
import uuid
import psycopg2
import requests

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
MOOLAM_KNOWLEDGE = "/mnt/h/DevTools/Projects/learn-ai/moolam-chronicles"

DOSSIERS = [
    {
        "file": "knowledge/texts/text-kurinjipattu-wild-honey-harvesting-and-mountain-foraging-poetry.md",
        "slug": "text-kurinjipattu-wild-honey-harvesting-and-mountain-foraging-poetry",
        "category": "text",
        "name_en": "Kurinjipattu: Classical Sangam Verses on Mountain Honey Gathering & Forest Foraging",
        "name_ta": "குறிஞ்சிப்பாட்டு - மலைத்தேன் எடுத்தல் மற்றும் காட்டுணவு சேகரிப்புப் பாடல்கள்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 200,
        "thinai": "kurinji",
        "summary_en": "Kapilar's celebrated Sangam anthology detailing ninety-nine mountain flowers, highland cliff honey gathering protocols, and the subsistence foraging of Kurinji hunter-gatherer clans.",
        "summary_ta": "கபிலர் இயற்றிய குறிஞ்சிப்பாட்டில் குறிஞ்சி நிலத்தின் 99 மலர்கள், செங்குத்துப் பாறைகளில் மலைத்தேன் எடுக்கும் முறைமை மற்றும் கானவர்களின் உணவு சேகரிப்பு வளம் விவரிக்கப்படுகிறது.",
        "sources": [
            "Kurinjipattu lines 150-185",
            "Pathupattu Commentary by Nachinarkiniyar"
        ],
        "content": "# Kurinjipattu: Classical Sangam Verses on Mountain Honey Gathering\n\nKurinjipattu composed by Kapilar stands as the foremost botanical and ethnobiological compendium of ancient Tamilakam. Within its panoramic verses on the montane rainforests of Kurinji, Kapilar meticulously details the hazardous practice of wild cliff honey gathering (malai-thaen eduthal).\n\nSangam verses capture the sensory ecology of high-altitude bee colonies built by the giant Asian rock bee (Apis dorsata) upon precipitous granite escarpments. The text highlights how hunter-gatherers constructed vine-ropes and suspended platforms to access inaccessible hives, using smoke torches to disperse aggressive swarms without contaminating the delicate floral nectar collected across wild strobilanthes blooms (neelakurinji).\n\nThe poem records the ninety-nine indigenous flowers whose nectar enriched mountain honey, creating multi-floral medicinal unguents prized for longevity, pediatric rejuvenation, and wound care throughout classical South India."
    },
    {
        "file": "knowledge/concepts/concept-precipice-rock-honey-gathering-with-smoked-torches-malai-thaen.md",
        "slug": "concept-precipice-rock-honey-gathering-with-smoked-torches-malai-thaen",
        "category": "concept",
        "name_en": "Precipice Rock Honey Gathering with Smoked Torches & Mountain Climbers (Malai Thaen & Theevatti)",
        "name_ta": "மலைத்தேன் எடுத்தல் - புகை மூட்டும் தீவட்டிகள் மற்றும் பாறைத் தேன் சேகரிப்பு",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "kurinji",
        "summary_en": "Highland cliff-harvesting technique employing green leaf smoke torches (theevatti) and descent rigs to harvest giant rock bee (Apis dorsata) honeycombs from sheer mountain walls.",
        "summary_ta": "செங்குத்துப் பாறைகளில் கட்டப்பட்ட பெருந்தேனீ கூடுகளைப் பச்சை இலை புகை மூட்டும் தீவட்டிகள் கொண்டு அமைதிப்படுத்தி, தேனை அறுவடை செய்யும் பாரம்பரிய மலைவாழ் முறைமை.",
        "sources": [
            "Akananuru 2",
            "Natrinai 168",
            "Tribal Ethnobotany of Eastern Ghats"
        ],
        "content": "# Precipice Rock Honey Gathering with Smoked Torches (Malai Thaen)\n\nThe gathering of wild rock honey (malai thaen or kombu thaen) from sheer montane cliffs represents one of the oldest specialized harvesting arts in Tamilakam. Colonies of Apis dorsata nest under overhanging rock ledges at heights exceeding 200 feet, safe from terrestrial predators.\n\nThe harvester descended in the dead of night or predawn twilight suspended by rope ladders woven from forest creepers. A crucial instrument was the smoldering torch (theevatti or pugaipandham), prepared from green aromatic leaves such as neem, tulsi, and forest vitex. The thick, cool smoke temporarily stupefied the rock bees, inducing them to gorge on honey and withdraw into rock crevices without inflicting deadly stings.\n\nUsing crescent-shaped bamboo knives, harvesters severed only the honey-bearing storage segment of the comb, deliberately leaving the brood comb intact to ensure rapid colony regeneration and seasonal sustainability."
    },
    {
        "file": "knowledge/concepts/concept-clay-pot-apiculture-and-medicinal-honey-infusions-thaen-koodu.md",
        "slug": "concept-clay-pot-apiculture-and-medicinal-honey-infusions-thaen-koodu",
        "category": "concept",
        "name_en": "Clay Pot Apiculture, Domestic Hives & Medicinal Honey Infusions (Thaen Koodu & Thaen Ooral)",
        "name_ta": "மண்பானைத் தேனீ வளர்ப்பு மற்றும் மூலிகைத் தேன் ஊரல் நுட்பங்கள்",
        "era": "Sangam to Medieval Era",
        "year_start": -200,
        "year_end": 1600,
        "thinai": "kurinji",
        "summary_en": "Ancient Tamil apicultural traditions using perforated earthenware pots smeared with beeswax for domestic beekeeping, and the preparation of fermented medicinal honey elixirs (thaen-ooral).",
        "summary_ta": "மண்பானைகளில் துளையிட்டு தேன்மெழுகு பூசி தேனீக்களைக் கவரும் வளர்ப்பு முறை மற்றும் இஞ்சி, நெல்லிக்காய் உள்ளிட்ட மூலிகைகளைத் தேனில் பதப்படுத்தும் ஊரல் முறைமை.",
        "sources": [
            "Pathinenkilkanakku Botanical Verses",
            "Siddha Materia Medica (Agathiyar Gunavagadam)"
        ],
        "content": "# Clay Pot Apiculture & Medicinal Honey Infusions (Thaen Koodu)\n\nParallel to wild cliff gathering, ancient Tamil settlements in sub-montane forest margins pioneered domestic apiculture using modified terracotta vessels (thaen koodu or thaen paanai). Unglazed clay pots were punctured with entry holes calibrated to bee thorax dimensions and treated internally with melted beeswax, crushed cardamom, and palmyrah jaggery syrup to attract migrating swarms of the Indian honey bee (Apis cerana indica).\n\nThese domestic hives provided a continuous supply of virgin honey. Siddha physicians capitalized on honey's natural osmotic and antimicrobial properties to formulate thaen-ooral (fermented honey preserves). Fresh amla (gooseberries), ginger rhizomes, pepper corns, and terminalia fruits were steeped in sealed terracotta jars of raw honey buried in grain pits for 48 days.\n\nThe resulting elixir served as a potent bio-enhancer (anupanam), dramatically boosting bioavailability and shelf life of delicate herbal phytochemicals."
    },
    {
        "file": "knowledge/concepts/concept-bamboo-rope-ladder-cliff-scaling-acrobatics-aani-eani.md",
        "slug": "concept-bamboo-rope-ladder-cliff-scaling-acrobatics-aani-eani",
        "category": "concept",
        "name_en": "Bamboo Rope Ladder Cliff-Scaling Engineering & Alpine Rigging (Aani Eani & Kodi Vazhi)",
        "name_ta": "ஆணி ஏணி - மூங்கில் கயிறேணி பாறை இறங்கு நுட்பம் மற்றும் செங்குத்து கயிறு கட்டமைப்பு",
        "era": "Prehistoric to Modern Era",
        "year_start": -400,
        "year_end": 1700,
        "thinai": "kurinji",
        "summary_en": "Indigenous mountaineering rigging employing bamboo rung rope ladders (aani-eani) and iron spike anchors to negotiate 300-foot vertical escarpments during night honey expeditions.",
        "summary_ta": "காட்டுக் கொடிகள் மற்றும் மூங்கில் படிகளைக் கொண்டு உருவாக்கப்பட்ட ஆணி ஏணி மூலமாக 300 அடி செங்குத்துப் பாறைகளில் இறங்கி தேனெடுக்கும் மலைவாழ் பொறியியல் கலை.",
        "sources": [
            "Purananuru 109",
            "Malaipadukadam lines 300-330"
        ],
        "content": "# Bamboo Rope Ladder Cliff Scaling Engineering (Aani Eani)\n\nThe technical backbone of high-altitude rock honey harvesting in the Western and Eastern Ghats was the specialized cliff-rigging system known in Sangam literature as aani-eani. To access subterranean honey ledges overhanging dizzying gorges, harvesters engineered flexible rope ladders spanning several hundred feet.\n\nThe side cables were braided from the fibrous stems of wild forest climbers (choorai kodi and pirambu). Horizontal rungs were fashioned from seasoned rock bamboo (kal-mungil), fire-hardened and notched to prevent slippage under moist mountain conditions. Iron spikes or wooden pegs (aani) were driven into natural fissures along the cliff summit to moor the primary tension ropes.\n\nMalaipadukadam portrays the breathtaking courage of the harvesters who maneuvered along these swinging aerial ropes in darkness, carrying collection baskets lined with leakproof wax-coated leaves."
    },
    {
        "file": "knowledge/concepts/concept-kurinji-kaanavar-forest-honey-guilds-and-wax-trade-thaen-vanigam.md",
        "slug": "concept-kurinji-kaanavar-forest-honey-guilds-and-wax-trade-thaen-vanigam",
        "category": "concept",
        "name_en": "Kaanavar Highland Forest Honey Guilds & Pure Beeswax Barter Commerce (Thaen Vanigam & Mezhugu)",
        "name_ta": "கானவர் தேன் சேகரிப்புக் குழுக்கள் மற்றும் தூய தேன்மெழுகு பண்டமாற்று வணிகம்",
        "era": "Sangam to Chola Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "kurinji",
        "summary_en": "Organized trade guilds of forest dwellers (Kaanavar) who bartered mountain honey and purified beeswax (mezhugu) for lowland coastal salt, paddy, and iron tools across ancient Tamilakam.",
        "summary_ta": "குறிஞ்சி நிலக் கானவர்கள் காட்டுத் தேன் மற்றும் தூய தேன்மெழுகினை மருத நில நெல்லுக்கும் நெய்தல் நில உப்புக்கும் பண்டமாற்று செய்த சமூகப் பொருளாதார வர்த்தக அமைப்பு.",
        "sources": [
            "Pattinappalai lines 185-210",
            "Silappadikaram Kadukankathai"
        ],
        "content": "# Kaanavar Forest Honey Guilds & Beeswax Trade (Thaen Vanigam)\n\nIn ancient Tamil economic geography, the mountain inhabitants known as Kaanavar or Kuravar maintained autonomous harvesting territories governed by traditional clan councils. Forest honey and beeswax represented their premier commercial assets, establishing vital inter-thinai barter connections with Marutham plains and Neithal coastal ports.\n\nBeeswax (mezhugu) was refined by melting combs in boiling water and straining through porous cotton cloths to extract residual bee silk and debris. Purified beeswax was indispensable for South Indian lost-wax bronze casting (madhuchishtavidhana), cire-perdue sculpture, weapon waterproofing, and temple nanda-vilakku perpetual lamps.\n\nPattinappalai records that caravans of highland honey and solid wax cakes arrived continuously at the great international emporium of Poompuhar to be exchanged for pearl necklaces, Mediterranean wine, and salt."
    },
    {
        "file": "knowledge/inscriptions/insc-javvadhumalai-kaanavar-forest-honey-and-wax-tribute-inscriptions.md",
        "slug": "insc-javvadhumalai-kaanavar-forest-honey-and-wax-tribute-inscriptions",
        "category": "inscription",
        "name_en": "Javvadhu Hills Forest Epigraphs on Mountain Tribe Honey & Temple Wax Tributes",
        "name_ta": "ஜவ்வாது மலை கல்வெட்டுகள் - மலைவாழ் கானவர் தேன் மற்றும் நந்தாவிளக்கு மெழுகு காணிக்கை",
        "era": "Medieval Chola Era",
        "year_start": 950,
        "year_end": 1200,
        "thinai": "kurinji",
        "summary_en": "Granite epigraphs from the Javvadhu highland forests recording agreements between local Kaanavar honey-gathering clans and Chola temple endowments for daily honey and perpetual wax offerings.",
        "summary_ta": "ஜவ்வாது மலைப் பகுதிகளில் உள்ள சோழர் கால கல்வெட்டுகள், கானவர் கூட்டங்கள் திருக்கோயில்களுக்குத் தினசரி தூய தேன் மற்றும் நந்தாவிளக்கு மெழுகு வழங்கிய ஒப்பந்தங்களைப் பதிவு செய்கின்றன.",
        "sources": [
            "South Indian Inscriptions Vol XVII",
            "Javvadi Hills Epigraphical Survey"
        ],
        "content": "# Javvadhu Hills Forest Honey & Wax Tribute Epigraphs\n\nDiscovered on natural rock shelters and temple granite bases across the northern Javvadhu mountain range, these Medieval Chola epigraphs document the formalization of tribal forest produce tithes.\n\nThe inscriptions stipulate that the local forest-dwelling Kaanavar clans were guaranteed hereditary rights over specified rock cliffs and wild swarms. In return, the guild delivered fixed annual quantities of refined rock honey (thaen-kollai) for temple anointing rituals (abhishekam) and pure beeswax cakes (mezhugu-kattigal) to fuel perpetual sanctum lamps.\n\nThe epigraphs specifically mention tax exemptions (iraiyili) granted to master climbers, recognizing the perilous nature of alpine cliff harvesting."
    },
    {
        "file": "knowledge/inscriptions/insc-pachaimalai-hill-tribe-apiculture-and-medicinal-resin-endowments.md",
        "slug": "insc-pachaimalai-hill-tribe-apiculture-and-medicinal-resin-endowments",
        "category": "inscription",
        "name_en": "Pachaimalai Highland Inscriptions on Forest Honey Guilds & Aromatic Resin Grants",
        "name_ta": "பச்சைமலை கல்வெட்டுகள் - மலைவாழ் தேன் வணிகக் குழு மற்றும் நறுமணப் பிசின் கொடை",
        "era": "Later Pandya Era",
        "year_start": 1150,
        "year_end": 1350,
        "thinai": "kurinji",
        "summary_en": "Thirteenth-century Pandya inscriptions from Pachaimalai documenting chartered forest territories where honey gathers supplied medicinal wild honey and dammar resins to regional dispensaries.",
        "summary_ta": "பச்சைமலை பாறை கல்வெட்டுகள் கானவர் குழுக்கள் மூலிகைத் தேன் மற்றும் சாம்பிராணி பிசின்களை மருத்துவ சாலைகளுக்கு வழங்கிய தானங்களையும் அரச பாதுகாப்பையும் விவரிக்கின்றன.",
        "sources": [
            "Pandya Epigraphical Records Vol VI",
            "Archaeological Survey of Tamil Nadu (Tiruchirappalli District)"
        ],
        "content": "# Pachaimalai Highland Forest Honey Guild Inscriptions\n\nSituated in the rugged Pachaimalai hills northwest of Tiruchirappalli, these later Pandya records shed light on the integration of tribal foraging economies into medieval state pharmacology.\n\nThe inscriptions detail how royal edicts protected highland bee habitats against reckless clearing or timber logging. Honey gatherers were organized under a designated leader (thaen mooppan) who negotiated produce prices with visiting itinerant merchant corporations such as the Ainnurruvar (Five Hundred of Ayyavole).\n\nThe epigraph emphasizes the high medicinal grade of Pachaimalai honey, harvested primarily from blooms of wild medicinal trees including neem, wild myrobalan, and terminalia."
    },
    {
        "file": "knowledge/characters/char-pachaimalai-master-cliff-honey-harvester-thaen-eduppon.md",
        "slug": "char-pachaimalai-master-cliff-honey-harvester-thaen-eduppon",
        "category": "character",
        "name_en": "Pachaimalai Master Cliff Honey Harvester & Alpine Climber (Thaen Eduppon)",
        "name_ta": "பச்சைமலை செங்குத்துப் பாறைத் தேனெடுக்கும் கானவத் தலைவன்",
        "era": "Sangam Era",
        "year_start": -100,
        "year_end": 150,
        "thinai": "kurinji",
        "summary_en": "Legendary Kurinji alpine harvester celebrated in bardic verse for intrepid nighttime descents down misty granite precipices using hand-spun vine ladders to gather prized rock honeycombs.",
        "summary_ta": "பனிமூடிய செங்குத்துப் பாறைகளில் காட்டுக் கொடி ஏணி வழியே நள்ளிரவில் இறங்கி, கூரிய மூங்கில் கத்தி கொண்டு பெரும் பாறைத் தேன் கூடுகளை அறுவடை செய்யும் வீரக் கானவன்.",
        "sources": [
            "Kuruntogai 267",
            "Akananuru 112"
        ],
        "content": "# Pachaimalai Master Cliff Honey Harvester (Thaen Eduppon)\n\nThe figure of the Thaen Eduppon embodies the pinnacle of highland physical endurance, botanical wisdom, and cliff acrobatics celebrated throughout Sangam love and war poetry. In the Kurinji landscape, a youth's bravery was often measured by his ability to harvest cliff honey from dizzying escarpments unguarded by handrails.\n\nThe master harvester possessed an innate understanding of bee behavior, climatic shifts, and wind currents along the mountain faces. Before descending, he performed sacred rites to the mountain deity Murugan, honoring the spirits of the cliff and praying for sure-footedness.\n\nSupported only by a single partner manning the anchor post at the summit, the harvester descended into bottomless ravines with a burning smoking brand in one hand and a broad leather sack in the other, extracting golden nectar under star-lit skies."
    },
    {
        "file": "knowledge/characters/char-kurinji-kaanavar-honey-and-beeswax-guild-elder-thaen-mooppan.md",
        "slug": "char-kurinji-kaanavar-honey-and-beeswax-guild-elder-thaen-mooppan",
        "category": "character",
        "name_en": "Kurinji Kaanavar Honey & Beeswax Guild Elder (Thaen Mooppan)",
        "name_ta": "குறிஞ்சிக் கானவர் தேன் மற்றும் மெழுகு வணிகக் கூட்ட மூப்பன்",
        "era": "Medieval Chola Era",
        "year_start": 1050,
        "year_end": 1150,
        "thinai": "kurinji",
        "summary_en": "Chieftain and guild elder of highland forest clans responsible for demarcating cliff-harvest territories, settling inter-clan harvesting disputes, and bartering honey and wax with royal merchant envoys.",
        "summary_ta": "மலைவாழ் கானவர் குலங்களின் தலைவர்; பாறைத் தேன் எல்லைகளை நிர்ணயித்து, சோழ நாட்டுப் பெருவணிகர்களிடம் தேன் மற்றும் மெழுகு விலையை ஒப்பந்தம் செய்த முதிய தலைமை மூப்பன்.",
        "sources": [
            "Chola Forest Boundary Charters",
            "Kulothunga Chola Epigraphs"
        ],
        "content": "# Kurinji Kaanavar Honey Guild Elder (Thaen Mooppan)\n\nThe Thaen Mooppan served as the socio-political bridge between sovereign forest clans and the imperial agrarian state during the Medieval Chola era. Residing in upland fortified hamlets (kurunji kuruchi), the elder possessed ancestral knowledge of seasonal flowering cycles and forest territorial boundaries.\n\nHe regulated the annual harvesting calendar, prohibiting premature comb destruction and ensuring that bee colonies had sufficient stores during monsoon droughts. Under his supervision, younger apprentices were trained in the delicate arts of smoke management, rope knotting, and sting extraction using Siddha herbal poultices.\n\nThe elder represented the forest collective in negotiations with imperial revenue officers, securing silver coinage, iron arrowheads, and fine coastal textiles in exchange for pristine mountain honey and temple wax supplies."
    },
    {
        "file": "knowledge/places/place-pachaimalai-ancient-kurinji-cliff-honey-and-forest-haven.md",
        "slug": "place-pachaimalai-ancient-kurinji-cliff-honey-and-forest-haven",
        "category": "place",
        "name_en": "Pachaimalai: Ancient Kurinji Cliff Honey Sanctuary & Highland Foraging Haven",
        "name_ta": "பச்சைமலை - பண்டைய குறிஞ்சிப் பாறைத் தேன் புகலிடம் மற்றும் கானக சேகரிப்புத் தளம்",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "kurinji",
        "summary_en": "Verdant granite massif in the Eastern Ghats revered since Sangam antiquity for its mist-shrouded vertical cliffs, dense flowering canopy, and ancient traditions of giant rock bee honey harvesting.",
        "summary_ta": "கிழக்குத் தொடர்ச்சி மலையின் பசுமைப் பள்ளத்தாக்குகள் மற்றும் செங்குத்துப் பாறைகளைக் கொண்ட தளம்; சங்க காலம் தொட்டே மலைத்தேன் சேகரிப்பு மற்றும் கானவர் வாழ்வியலின் முக்கிய மையமாகத் திகழ்கிறது.",
        "sources": [
            "Akananuru 278",
            "Gazetteer of Tiruchirappalli District"
        ],
        "content": "# Pachaimalai: Ancient Kurinji Cliff Honey Sanctuary\n\nRising abruptly from the central Tamil plains in modern Tiruchirappalli and Salem districts, the Pachaimalai massif represents a quintessential Kurinji ecological redoubt. Its deep quartzite gorges, perennial mountain torrents, and dense evergreen foliage provide an ideal micro-climate for diverse bee species.\n\nThe sheer rocky scarps of Pachaimalai, known locally as Thaen-Paarai (Honey Cliffs), boast hundreds of perennial Apis dorsata nesting sites. For millennia, indigenous tribes have practiced sustainable cliff foraging along these slopes, protected by the steep topography from lowland incursions.\n\nArchaeological excavations on the hills have unearthed prehistoric stone scrapers alongside Sangam-period terracotta storage vessels, demonstrating continuous human habitation and apicultural exploitation over three thousand years."
    }
]
EDGES = [
    [
        "text-kurinjipattu-wild-honey-harvesting-and-mountain-foraging-poetry",
        "documents_technique",
        "concept-precipice-rock-honey-gathering-with-smoked-torches-malai-thaen",
        "historical_proof",
        "Sangam Era",
        "Kurinjipattu provides vivid poetic documentation of high-altitude cliff honey gathering using smoke torches.",
        "Kurinjipattu lines 150-185"
    ],
    [
        "concept-precipice-rock-honey-gathering-with-smoked-torches-malai-thaen",
        "requires_equipment",
        "concept-bamboo-rope-ladder-cliff-scaling-acrobatics-aani-eani",
        "historical_proof",
        "Prehistoric to Modern Era",
        "Cliff honey harvesting strictly required long flexible bamboo rope ladders (aani-eani) to access sheer rock faces.",
        "Malaipadukadam lines 300-330"
    ],
    [
        "concept-precipice-rock-honey-gathering-with-smoked-torches-malai-thaen",
        "produces_commodity",
        "concept-kurinji-kaanavar-forest-honey-guilds-and-wax-trade-thaen-vanigam",
        "historical_proof",
        "Sangam to Chola Era",
        "Harvested combs were refined into golden honey and pure beeswax cakes for inter-thinai barter trade.",
        "Pattinappalai lines 185-210"
    ],
    [
        "concept-clay-pot-apiculture-and-medicinal-honey-infusions-thaen-koodu",
        "preserves_medicinal",
        "concept-kurinji-kaanavar-forest-honey-guilds-and-wax-trade-thaen-vanigam",
        "historical_proof",
        "Sangam to Medieval Era",
        "Domestic and wild honey were preserved as medicinal infusions (thaen-ooral) traded to urban dispensaries.",
        "Agathiyar Gunavagadam"
    ],
    [
        "char-pachaimalai-master-cliff-honey-harvester-thaen-eduppon",
        "operates_in",
        "place-pachaimalai-ancient-kurinji-cliff-honey-and-forest-haven",
        "historical_proof",
        "Sangam Era",
        "Master cliff harvesters executed perilous nocturnal honey raids along the quartzite escarpments of Pachaimalai.",
        "Kuruntogai 267"
    ],
    [
        "char-pachaimalai-master-cliff-honey-harvester-thaen-eduppon",
        "masters_technique",
        "concept-bamboo-rope-ladder-cliff-scaling-acrobatics-aani-eani",
        "historical_proof",
        "Sangam Era",
        "Master climbers engineered and descended flexible vine ladders anchored by iron spikes over sheer abysses.",
        "Purananuru 109"
    ],
    [
        "char-kurinji-kaanavar-honey-and-beeswax-guild-elder-thaen-mooppan",
        "regulates_guild",
        "concept-kurinji-kaanavar-forest-honey-guilds-and-wax-trade-thaen-vanigam",
        "historical_proof",
        "Medieval Chola Era",
        "The guild elder governed tribal harvesting boundaries and fixed commercial prices for raw beeswax and honey.",
        "Chola Forest Boundary Charters"
    ],
    [
        "insc-javvadhumalai-kaanavar-forest-honey-and-wax-tribute-inscriptions",
        "records_tribute",
        "concept-kurinji-kaanavar-forest-honey-guilds-and-wax-trade-thaen-vanigam",
        "historical_proof",
        "Medieval Chola Era",
        "Javvadhu inscriptions record royal charters granting forest tribes tax-free status in exchange for temple honey and wax tributes.",
        "South Indian Inscriptions Vol XVII"
    ],
    [
        "insc-pachaimalai-hill-tribe-apiculture-and-medicinal-resin-endowments",
        "attests_place",
        "place-pachaimalai-ancient-kurinji-cliff-honey-and-forest-haven",
        "historical_proof",
        "Later Pandya Era",
        "Pandya inscriptions on Pachaimalai substantiate chartered forest territories where honey gatherers operated under royal protection.",
        "Pandya Epigraphical Records Vol VI"
    ],
    [
        "place-pachaimalai-ancient-kurinji-cliff-honey-and-forest-haven",
        "preserves_lore",
        "text-kurinjipattu-wild-honey-harvesting-and-mountain-foraging-poetry",
        "historical_proof",
        "Sangam to Modern Era",
        "The botanical and cultural traditions of Pachaimalai preserve the classical floristic and foraging ecology immortalized in Kurinjipattu.",
        "Akananuru 278"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Ancient Tamil Apiculture & Cliff Honey Gathering into Moolam Chronicles & Life Graph...")

    # Phase 1: Write Markdown Files
    print("\n[Phase 1] Writing 10 Markdown Knowledge Dossiers...")
    for d in DOSSIERS:
        full_path = os.path.join(MOOLAM_KNOWLEDGE, d["file"])
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(d["content"].strip() + "\n")
        print(f"  ✓ Wrote: {d['file']}")

    # Phase 2: PostgreSQL Lore Nodes Upsert
    print(f"\n[Phase 2] Connecting to PostgreSQL at {DB_URL}...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    nodes_upserted = 0
    for d in DOSSIERS:
        slug = d["slug"]
        props = json.dumps({"category": d["category"], "canonical_file": d["file"]})
        cur.execute("""
            INSERT INTO lore_nodes (
                id, slug, node_type, name_en, name_ta, era, year_start, year_end,
                thinai, summary_en, summary_ta, sources, layer, properties, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, NOW()
            )
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
                properties = EXCLUDED.properties,
                created_at = NOW();
        """, (
            str(uuid.uuid4()),
            slug,
            d["category"],
            d["name_en"],
            d["name_ta"],
            d["era"],
            d["year_start"],
            d["year_end"],
            d["thinai"],
            d["summary_en"],
            d["summary_ta"],
            d["sources"],
            "historical_proof",
            props
        ))
        nodes_upserted += 1
        print(f"  ✓ Upserted node: {slug}")

    conn.commit()
    print(f"Phase 2 complete: {nodes_upserted} lore nodes upserted.")

    # Phase 3: Relational Cross-Domain Edges
    print(f"\n[Phase 3] Inserting {len(EDGES)} Relational Cross-Domain Edges...")
    edges_inserted = 0
    for edge in EDGES:
        src, rel, tgt, layer, era, desc, evidence = edge
        cur.execute("""
            DELETE FROM lore_edges 
            WHERE source_slug = %s AND target_slug = %s AND relation_type = %s;
        """, (src, tgt, rel))

        cur.execute("""
            INSERT INTO lore_edges (
                id, source_slug, relation_type, target_slug,
                layer, era, description, evidence_source
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            );
        """, (
            str(uuid.uuid4()), src, rel, tgt, layer, era, desc, evidence
        ))
        edges_inserted += 1
        print(f"  ✓ Linked: ({src}) --[{rel}]--> ({tgt})")

    conn.commit()
    print(f"Phase 3 complete: {edges_inserted} edges processed.")

    # Phase 4: Vector Embeddings
    print("\n[Phase 4] Generating 1024-dim BGE-M3 Embeddings via Ollama...")
    total_chunks = 0
    for d in DOSSIERS:
        slug = d["slug"]
        cur.execute("DELETE FROM rag_chunks WHERE node_slug = %s;", (slug,))

        chunks = [
            {
                "language": "en",
                "title": d["name_en"],
                "content": f"{d['name_en']}\n\nSummary:\n{d['summary_en']}\n\nKey Concepts:\n{d['content'][:1500]}"
            },
            {
                "language": "ta",
                "title": d["name_ta"],
                "content": f"{d['name_ta']}\n\nசுருக்கம்:\n{d['summary_ta']}\n\nமுக்கிய நுட்பங்கள்:\n{d['content'][:1500]}"
            }
        ]

        for ch in chunks:
            emb = get_bge_embedding(ch["content"])
            emb_str = "[" + ",".join(str(x) for x in emb) + "]"
            cur.execute("""
                INSERT INTO rag_chunks (
                    id, node_slug, shelf, language, title, content,
                    source_ref, embedding, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                );
            """, (
                str(uuid.uuid4()),
                slug,
                f"shelf-{d['category']}s",
                ch["language"],
                ch["title"],
                ch["content"],
                d["file"],
                emb_str
            ))
            total_chunks += 1
        print(f"  ✓ Embedded 2 chunks for: {slug}")

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n🎉 Ancient Tamil Apiculture & Cliff Honey Gathering Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
