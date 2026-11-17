#!/usr/bin/env python3
"""
Harvester: Batch 43 - Ancient Tamil Saltpan Hydraulic Canals, Solar Halite Crystallization & Umanar Caravans
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

DOSSIERS = [
    {
        "slug": "text-ahananuru-and-narrinai-on-umanar-salt-caravans-and-salterns",
        "category": "text",
        "file": "text-ahananuru-and-narrinai-on-umanar-salt-caravans-and-salterns.md",
        "name_en": "Ahananuru & Narrinai Verses on Umanar Salt Caravans, White Halite Crystals & Barter Trade",
        "name_ta": "அகநானூறு மற்றும் நற்றிணை உமணர் உப்பு வணிகக் சாத்து மற்றும் வெண் உப்பு பாடல் குறிப்புகள்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "neithal",
        "summary_en": "Classical Sangam poems celebrating the nomadic salt merchants (Umanar) traveling across coastal highways with heavily laden pack-bullock carts, crying out in agrarian villages to barter pure white solar salt for golden paddy and hill pepper.",
        "summary_ta": "நெல் தந்து உப்புப் பெற வாரீரோ என ஊர் தோறும் மாட்டு வண்டிகளில் சென்று வெண் உப்பை நெல்லுக்கும் மிளகுக்கும் பண்டமாற்று செய்த உமணர் சாத்து பற்றிய அகநானூறு மற்றும் நற்றிணைப் பாடல்கள்.",
        "sources": [
            "Ahananuru 140",
            "Ahananuru 390",
            "Narrinai 183",
            "Kuruntokai 269",
            "Purananuru 386"
        ],
        "content": "# Ahananuru & Narrinai on Umanar Salt Caravans\n\nThe salt economy of ancient Tamil Nadu was a foundational engine of trans-thinai commercial exchange:\n\n**Literary Testimonies:**\n- **Ahananuru 140 & 390**: Depicts long caravans (*Umanar-Saathu*) of wooden-wheeled bullock carts creaking over sandy coastal tracks, guarded by fierce archers as they carried mountains of solar halite crystals from seaside pans (*alam*) to inland river hamlets.\n- **Narrinai 183**: Portrays the Umanar woman (*Umatthi*) walking through the streets of an agricultural village, her melodious cry ringing out: *\"Nel-thandu uppu kollum!\"* (Exchange your paddy for my salt!).\n- **Kuruntokai 269**: Compares the brilliant white mounds of crystallized salt drying along coastal lagoons to heaps of sparkling moonlight."
    },
    {
        "slug": "concept-seawater-evaporation-salinity-gradients-and-halite-crystallization",
        "category": "concept",
        "file": "concept-seawater-evaporation-salinity-gradients-and-halite-crystallization.md",
        "name_en": "Seawater Solar Evaporation, Baumé Density Gradients & Halite Precipitation Kinetics",
        "name_ta": "கடல்நீர் சூரிய ஆவியாதல், போமே அடர்த்தி சாய்வு மற்றும் உப்புக் படிகமாதல் இயக்கவியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -1000,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Chemical thermodynamics of coastal solar salt production: concentration of ambient seawater (3.5° Baumé) through staged reservoir ponds, calcium carbonate precipitation at 14° Bé, gypsum deposition at 25° Bé, and pure sodium chloride (halite) crystallization between 25.5° and 29.5° Bé.",
        "summary_ta": "சூரிய வெப்பத்தால் கடல்நீரிலிருந்து தூய சோடியம் குளோரைடு (உப்பு) பிரிக்கும் வேதியியல்: படிப்படியான நீர்நிலைகளில் உப்பின் அடர்த்தி அதிகரித்தல், கால்சியம் படிவுகள் நீக்கம் மற்றும் படிகமாதல்.",
        "sources": [
            "Industrial and Engineering Chemistry: Solar Salt Crystallization",
            "CSIR Central Salt and Marine Chemicals Research Institute",
            "Oceanographic Chemistry Studies"
        ],
        "content": "# Seawater Evaporation & Halite Precipitation Kinetics\n\nFractional crystallization of sea salt requires precise hydrometric management of solar evaporation ponds:\n\n**Thermodynamic Precipitation Stages:**\n- **Initial Concentration ($3.5^\\circ-14^\\circ\\\\text{ Baumé}$)**: Raw seawater admitted into shallow primary reservoirs (*peraalam*) evaporates under sun and coastal wind, concentrating dissolved salts while precipitating ferric oxide and calcium carbonate ($\\text{CaCO}_3$).\n- **Sulfate Separation ($14^\\circ-25^\\circ\\\\text{ Bé}$)**: In intermediate condenser pans, calcium sulfate dihydrate (gypsum, $\\text{CaSO}_4\\cdot 2\\text{H}_2\\text{O}$) precipitates out completely, preventing bitter chalky contamination of the final table salt.\n- **Halite Crystallization ($25.5^\\circ-29.5^\\circ\\\\text{ Bé}$)**: The saturated brine (*uppu-neer*) is transferred into flat, clay-tamped crystallizer pans (*alam*). Sodium chloride ($\\text{NaCl}$) precipitates in dense hopper-shaped cubic crystals. Brine is drained before reaching $30^\\circ\\text{ Bé}$ to exclude toxic magnesium and potassium salts (*bitterns*)."
    },
    {
        "slug": "technology-tidal-feeder-canals-tamped-clay-pans-and-wooden-salt-scrapers",
        "category": "technology",
        "file": "technology-tidal-feeder-canals-tamped-clay-pans-and-wooden-salt-scrapers.md",
        "name_en": "Tidal Sluice Feeder Canals, Compacted Impermeable Clay Pans & Wooden Salt Scrapers",
        "name_ta": "கடல் அலை நீர்வரத்துக் கால்வாய்கள், கெட்டிப்படுத்திய களிமண் தளம் மற்றும் மர உப்புக் கீறல் பலகைகள்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "The physical layout and operational technology of Tamil salterns (alam): high-tide intake sluices, stepped evaporation reservoirs, clay crystallizers rammed impermeable with wooden rammers, and broad teakwood scrapers (mara-vaari) harvesting salt crusts.",
        "summary_ta": "பாரம்பரிய உப்பள கட்டமைப்பு: அலை ஏற்றத்தின் போது கடல்நீரை உள்வாங்கும் மதகுகள், கசியாதவாறு அடித்து கெட்டிப்படுத்திய களிமண் பாத்திகள் மற்றும் மர வாரிகள் கொண்டு உப்பைச் சேகரிக்கும் முறை.",
        "sources": [
            "Ethnoarchaeology of Tamil Salt Making",
            "Traditional Marine Salt Technologies",
            "Madras District Gazetteers: Salt Revenue"
        ],
        "content": "# Tidal Feeder Canals & Compacted Clay Salterns\n\nEngineering productive solar saltworks along the Coromandel lagoons required strict hydraulic and soil manipulation:\n\n**Saltern Architecture:**\n1. **Tidal Inlets (*Neer-Paaychuvai*)**: Sluice gates situated at high-water tidal lines captured seawater during spring tides, directing brine through network of gravity canals into expansive reservoir basins without mechanical pumping.\n2. **Floor Compaction (*Palam-Seydhal*)**: Crystallizer pan bottoms were lined with marine black clay, repeatedly trampled by water buffaloes and beaten with flat wooden tampers until forming an impermeable, rock-hard hydraulic floor that prevented brine seepage into sandy subsoil.\n3. **Wooden Harvesting Scrapers (*Mara-Vaari*)**: Artisans utilized broad, flat-edged teak or vaagai wooden scrapers to skim crystallized salt crusts into conical heaps along pan ridges without disturbing the underlying clay bed."
    },
    {
        "slug": "artifact-umanar-bullock-carts-palm-leaf-salt-sacks-and-measuring-marakkals",
        "category": "artifact",
        "file": "artifact-umanar-bullock-carts-palm-leaf-salt-sacks-and-measuring-marakkals.md",
        "name_en": "Heavy Wooden-Wheeled Salt Carts, Palmyra Woven Salt Baskets & Volumetric Marakkals",
        "name_ta": "கனத்த மரச்சக்கர உமணர் மாட்டு வண்டிகள், பனை ஓலை உப்புக் கூடைகள் மற்றும் மர மரக்கால்கள்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Material culture of ancient Tamil salt transport and barter: spoke-less solid and spoked wooden bullock carts with rawhide wheel rims, multi-layered woven palmyra leaf sacks (kottan), calibrated volumetric wooden grain-salt measures (marakkal, padi), and iron balance beams.",
        "summary_ta": "உப்பு வர்த்தக சாதனங்கள்: மணல் பரப்பில் ஓடும் கனத்த மரச்சக்கர மாட்டு வண்டிகள், உப்புக் கூடைகள், சம அளவு பண்டமாற்றுக்குப் பயன்பட்ட முத்திரை பொறித்த மர மரக்கால்கள் மற்றும் தராசுகள்.",
        "sources": [
            "Government Museum Chennai Agrarian Artifacts",
            "Sangam Material Culture Studies",
            "Epigraphia Indica: Salt Measure Standards"
        ],
        "content": "# Umanar Salt Carts & Volumetric Marakkals\n\nThe infrastructure of overland salt distribution required specialized rolling stock and standardized metrological tools:\n\n**Material Assemblage:**\n- **Umanar Bullock Carts (*Perum-Vandi*)**: Rugged wooden carts equipped with broad, leather-clad wheels designed to traverse soft coastal dunes and rocky Deccan ghat passes without sinking or splitting.\n- **Woven Salt Kottans**: Tightly braided containers of palmyra leaf treated with sea brine that allowed residual bittern liquor to drain freely while retaining dry sodium chloride crystals.\n- **Volumetric Grain-Salt Measures (*Marakkal & Ambana*)**: Standardized turned wooden cylinders bearing royal seal stamps, used for the universal Sangam 1:1 barter ratio (*Oppu-Nel*) where one measure of white salt was exchanged for one measure of hulled paddy."
    },
    {
        "slug": "concept-ancient-tamil-salt-barter-economics-and-oppu-nel-parity",
        "category": "concept",
        "file": "concept-ancient-tamil-salt-barter-economics-and-oppu-nel-parity.md",
        "name_en": "Ancient Tamil Salt Barter Economics, Oppu-Nel Parity & Trans-Thinai Trade Networks",
        "name_ta": "பண்டைய தமிழரின் உப்புப் பொருளாதார பண்டமாற்று முறை, உப்பு-நெல் சமமதிப்பு மற்றும் திணைசார் வணிகம்",
        "era": "Iron Age to Sangam Era",
        "year_start": -500,
        "year_end": 300,
        "thinai": "neithal",
        "summary_en": "Economic mechanics of the foundational Sangam barter system: strict value equivalence between coastal white salt and inland wetland paddy (Oppu-Nel), establishing inter-regional market equilibrium across Neithal, Marutham, and Kurinji ecological zones.",
        "summary_ta": "சங்க காலப் பொருளாதாரத்தின் அடிப்படை விதி: உப்புக்கு நெல் சமம் (ஒப்பு-நெல்) என்ற பண்டமாற்று விகிதம், நெய்தல் உப்பளங்களையும் மருத வயல்களையும் குறிஞ்சி மலைகளையும் இணைத்த வர்த்தக சங்கிலி.",
        "sources": [
            "Economic History of Early Tamil Nadu",
            "Studies in Sangam Internal Trade",
            "Journal of the Economic and Social History of the Orient"
        ],
        "content": "# Salt Barter Economics & Oppu-Nel Parity\n\nSalt was the universal biological necessity that bound the disparate ecological landscapes (*ainthinai*) of Tamilakam together:\n\n**Economic Dynamics:**\n- **The 1:1 Parity Rule (*Oppu-Nel*)**: Sangam poems explicitly state: *\"Uvavum nellum oppa kollum\"* (Accepting salt and paddy as equal in value). A farmer poured a basket of freshly harvested grain directly into the Umanar cart in return for the identical volume of white salt.\n- **Trans-Peninsular Supply Chains**: Salt produced on the Coromandel lagoons traveled westward across the Kongu plateau and through the Palakkad Gap to the spice-growing mountains of Kerala, where salt was exchanged for black pepper, wild cardamom, and ivory.\n- **State Toll Exemptions & Royal Taxes**: Early Tamil kings protected Umanar caravans on royal highways (*Peru-Vazhi*), levying minimal salt tolls (*Uppaayam*) in return for armed escorts against highwaymen."
    },
    {
        "slug": "institution-umanar-kudi-corporation-of-salt-makers-and-caravan-traders",
        "category": "institution",
        "file": "institution-umanar-kudi-corporation-of-salt-makers-and-caravan-traders.md",
        "name_en": "Umanar-Kudi Corporation: Hereditary Saltern Masters, Salt Boilers & Caravan Guilds",
        "name_ta": "உமணர் குடி சபை: மரபுவழி உப்பளத் தயாரிப்பாளர்கள், சாத்துத் தலைவர்கள் மற்றும் உப்பு வணிகர் சங்கம்",
        "era": "Iron Age to Chola Era",
        "year_start": -500,
        "year_end": 1300,
        "thinai": "neithal",
        "summary_en": "The corporate mercantile community of Tamil salt manufacturers and trans-regional traders (Umanar / Uppu-Vaanigar): operating coastal salt settlements (Umar-Cheri), organizing armed merchant caravans, maintaining pan territories, and negotiating royal tax charters.",
        "summary_ta": "கடற்கரை உப்பளங்களை நிர்வகித்த உமணர் சமூகத்தின் தன்னாட்சி அமைப்பு: உப்பள குடியிருப்புகள் (உமர்சேரி), ஆயுதம் தாங்கிய வணிகக் கூட்டங்கள் மற்றும் அரச வரி ஒப்பந்தங்கள்.",
        "sources": [
            "South Indian Inscriptions: Saltpan Charters",
            "Castes and Tribes of Southern India: Umanar",
            "Sangam Corporate Anthropology"
        ],
        "content": "# Umanar-Kudi Corporation: Hereditary Saltmakers\n\nThe extraction and carriage of salt was sustained by an endogamous, self-governing artisan-mercantile corporation:\n\n**Guild Functions:**\n- **Saltern Commons Allocation**: Divided coastal tidal flats (*uppala-parappu*) among hereditary family lineages, regulating pan boundaries and maintenance of communal sea-water feeder channels.\n- **Caravan Logistics (*Saathu*)**: Organized hundreds of cart drivers into unified convoys led by a caravan chieftain (*Saathuvagan*), traveling together for mutual protection across barren arid wildernesses (*Palai*).\n- **Settlement Quarters (*Umar-Cheri*)**: Maintained distinct coastal settlements adjacent to salterns, celebrated in Sangam poems for their white-washed mud cottages, nets, and mounds of dried salt."
    },
    {
        "slug": "technology-solar-wind-drying-mound-stacking-and-bittern-drainage",
        "category": "technology",
        "file": "technology-solar-wind-drying-mound-stacking-and-bittern-drainage.md",
        "name_en": "Solar-Wind Desiccation Kinetics, Conical Mound Stacking & Bittern Liquor Drainage",
        "name_ta": "சூரிய-காற்று உலர்த்தல் இயக்கவியல், கூம்பு வடிவ உப்புக் குவித்தல் மற்றும் கசப்பு நீர் வடித்தல்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Post-harvest purification techniques for raw solar salt: raking crystals into conical heaps along earthen bunds, draining hygroscopic magnesium chloride and magnesium sulfate mother liquor (bitterns) by gravity, and curing crystals under sun and maritime wind.",
        "summary_ta": "அறுவடை செய்யப்பட்ட உப்பைப் பதப்படுத்தும் முறை: பாத்திகளின் வரப்புகளில் கூம்பு வடிவில் குவித்து வைத்தல், மெக்னீசியம் கலந்த கசப்பு நீர் தானாக வடிந்து வெளியேறுதல் மற்றும் தூய வெண் படிகங்கள் உருவாதல்.",
        "sources": [
            "Chemical Technology of Solar Salt Manufacture",
            "CSIR Salt Purification Bulletins",
            "Indian Journal of Chemical Technology"
        ],
        "content": "# Solar Desiccation Kinetics & Bittern Drainage\n\nFreshly harvested solar salt is coated with a residual film of mother liquor containing bitter, deliquescent magnesium salts:\n\n**Purification Kinetics:**\n1. **Conical Mound Stacking (*Uppu-Kuvayal*)**: Harvesters raked damp halite crystals into steep conical mounds (height 1.5–2.0 m) along narrow earthen dividing ridges.\n2. **Gravity Bittern Weeping**: Due to higher hygroscopicity, magnesium chloride ($\\text{MgCl}_2$) and magnesium sulfate ($\\text{MgSO}_4$) absorb atmospheric moisture and drain away downward as dense oily brine (*kasappu-neer*), leaving pure, non-sticky sodium chloride behind.\n3. **Solar Calcination**: Exposure to strong sun and continuous sea winds for 5 to 7 days hardened the exterior crust of the mounds, protecting the interior white crystals against sudden coastal rains."
    },
    {
        "slug": "place-kovalam-ancient-thondai-saltern-haven",
        "category": "place",
        "file": "place-kovalam-ancient-thondai-saltern-haven.md",
        "name_en": "Kovalam: Ancient Thondai Saltern Haven, Buckingham Estuarine Pans & Umanar Coastal Emporium",
        "name_ta": "கோவளம் - பண்டைய தொண்டை நாட்டு உப்பளத் தளம், கடலோர உப்பங்கழி மற்றும் உமணர் பெருந்துறை",
        "era": "Iron Age to Modern Era",
        "year_start": -400,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Historic estuarine port and tidal saltern citadel on the Coromandel coast in Chengalpattu district south of Chennai, celebrated across two millennia for extensive solar saltpans, tidal sea feeder channels, and inland distribution networks supplying Kanchipuram.",
        "summary_ta": "செங்கல்பட்டு மாவட்டத்தில் அமைந்துள்ள புகழ்பெற்ற வரலாற்றுச் சிறப்புமிக்க உப்பளத் தளம்: தொண்டை மண்டலத் தலைநகர் காஞ்சிபுரத்திற்கு உப்பு வழங்கிய பிரதான உப்பளங்கள் மற்றும் கடற்கரை உமணர் வர்த்தக மையம்.",
        "sources": [
            "Chengalpattu District Gazetteer",
            "South Indian Inscriptions: Thondai Saltern Grants",
            "Maritime History of the Coromandel Coast"
        ],
        "content": "# Kovalam: Ancient Thondai Saltern Haven\n\nKovalam, situated at the mouth of an expansive estuarine lagoon south of Chennai, served as the premier salt-producing citadel of Thondai Nadu:\n\n**Historical Prominence:**\n- Its shallow, mud-bottomed lagoons protected from violent sea swells provided the ideal geographic setting for constructing miles of interconnected solar evaporation and crystallizer pans.\n- Inscriptional records from the Pallava and Chola eras document perpetual royal salt endowments (*uppala-kaani*) granted to temples and monasteries across Kanchipuram and Mahabalipuram.\n- Umanar caravans set out from Kovalam along ancient trade routes (*Peru-Vazhi*), transporting salt blocks deep into the northern Eastern Ghats and Mysore plateau."
    },
    {
        "slug": "concept-halite-cubic-cleavage-taste-physics-and-meat-preservation",
        "category": "concept",
        "file": "concept-halite-cubic-cleavage-taste-physics-and-meat-preservation.md",
        "name_en": "Halite Cubic Crystal Cleavage, Osmotic Food Preservation & Electrolyte Physiology",
        "name_ta": "சோடியம் குளோரைடு கனசதுர படிகப் பிளவு, சவ்வூடு பரவல் உணவு பதப்படுத்தல் மற்றும் உடலியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -1000,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Biochemical and physical functions of solar halite (NaCl): face-centered cubic crystal cleavage, cellular osmotic dehydration inhibiting bacterial spoil enzymes, curing fish and meats for oceanic voyages, and vital human electrolyte balance.",
        "summary_ta": "சோடியம் குளோரைடின் படிகவியல் மற்றும் பயன்பாடு: கனசதுர படிக அமைப்பு, சவ்வூடு பரவல் மூலம் பாக்டீரியாக்களை அழித்து கருவாடு மற்றும் இறைச்சியைப் பாதுகாக்கும் முறை மற்றும் மனித உடலியல் பங்கு.",
        "sources": [
            "Food Microbiology and Preservation",
            "Crystal Chemistry of Halite",
            "Journal of Ethnobiology and Ethnomedicine"
        ],
        "content": "# Halite Cubic Cleavage & Osmotic Preservation\n\nPure solar salt (*Vellai-Kal*) is fundamentally a biological life-support mineral:\n\n**Biophysical Mechanics:**\n- **Cubic Crystal Cleavage**: Sodium and chloride ions form a face-centered cubic lattice ($Fm\\bar{3}m$) exhibiting perfect three-directional cleavage $\\{100\\}$, allowing salt blocks to fracture into uniform granulates.\n- **Microbial Plasmolysis**: In high ambient salt concentrations ($>15\\%$), water is drawn out from bacterial cells via osmotic pressure, causing cellular plasmolysis and destroying putrefactive microorganisms.\n- **Marine Fish Curing (*Karuvadu*)**: Coastal Parathavar fishermen salted fresh catches of mackerel and seer fish in wooden troughs, drying them on hot beach sands to produce shelf-stable rations essential for military campaigns and long-distance sea voyages."
    },
    {
        "slug": "artifact-terracotta-brine-pitchers-wooden-spades-and-salt-crystals",
        "category": "artifact",
        "file": "artifact-terracotta-brine-pitchers-wooden-spades-and-salt-crystals.md",
        "name_en": "Terracotta Brine-Pouring Pitchers, Hardwood Saltern Spades & Coarse Salt Crystals",
        "name_ta": "சுடுமண் உவர்நீர் ஊற்றும் பாண்டங்கள், மர மண்வெட்டிகள் மற்றும் தூய வெண் உப்புப் படிகங்கள்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Material repertoire of traditional Tamil saltpan labor: flared earthenware jars for ladling dense brine between crystallizer pans, lightweight broad-bladed hardwood shovels (marak-kai), woven bamboo head-baskets, and coarse hopper salt crystals.",
        "summary_ta": "உப்பள தொழிலாளர்களின் கருவிகள்: உவர்நீரை முகந்து ஊற்றும் அகன்ற சுடுமண் பானைகள், களிமண் தளத்தைச் சேதப்படுத்தாத மர மண்வெட்டிகள், மூங்கில் கூடைகள் மற்றும் பெருங்கற்கள்.",
        "sources": [
            "Ethnographic Museum of Tamil Nadu Collections",
            "Madras Salt Department Historical Survey",
            "Bulletin of the Madras Museum"
        ],
        "content": "# Terracotta Brine Pitchers & Saltern Tools\n\nHarvesting mineral salt from tidal pans demanded non-corrosive, non-destructive implements:\n\n**Equipment Typology:**\n- **Brine Pitchers (*Neer-Kudam*)**: Wide-mouthed, coarse earthenware jars designed with balance spouts used to transfer concentrated brine from condenser ponds into crystallizer beds without splashing or breaking soil seals.\n- **Hardwood Spades (*Marak-Kalappai*)**: Hand-carved from dense, water-resistant Palmyra wood or *Vaagai*, featuring wide, bevelled blades that scraped salt crusts cleanly without gouging the compacted clay pond floor.\n- **Hopper Halite Crystals**: Coarse, pyramid-shaped stepped cubic hopper crystals measuring 5–15 mm across, displaying high optical transparency and rapid dissolution."
    }
]

EDGES = [
    [
        "text-ahananuru-and-narrinai-on-umanar-salt-caravans-and-salterns",
        "celebrates",
        "technology-tidal-feeder-canals-tamped-clay-pans-and-wooden-salt-scrapers",
        "material_culture",
        "Sangam Era",
        "Sangam poetry celebrates the white saltpans, wooden scrapers, and bullock caravans of the Umanar.",
        "Ahananuru 140 & 390"
    ],
    [
        "concept-seawater-evaporation-salinity-gradients-and-halite-crystallization",
        "governs",
        "technology-tidal-feeder-canals-tamped-clay-pans-and-wooden-salt-scrapers",
        "material_culture",
        "Iron Age to Modern Era",
        "Baumé density gradients and fractional crystallization dictate the stepped layout of tidal saltpans.",
        "CSIR Salt Research"
    ],
    [
        "technology-tidal-feeder-canals-tamped-clay-pans-and-wooden-salt-scrapers",
        "harvests",
        "artifact-umanar-bullock-carts-palm-leaf-salt-sacks-and-measuring-marakkals",
        "material_culture",
        "Iron Age to Modern Era",
        "Clay salterns and wooden scrapers harvest pure salt loaded into palmyra kottans and bullock carts.",
        "Ethnoarchaeology of Salt"
    ],
    [
        "concept-ancient-tamil-salt-barter-economics-and-oppu-nel-parity",
        "regulates",
        "institution-umanar-kudi-corporation-of-salt-makers-and-caravan-traders",
        "material_culture",
        "Iron Age to Sangam Era",
        "The 1:1 Oppu-Nel barter parity governed Umanar commercial transactions across agrarian villages.",
        "Economic History of Tamil Nadu"
    ],
    [
        "institution-umanar-kudi-corporation-of-salt-makers-and-caravan-traders",
        "operates_in",
        "place-kovalam-ancient-thondai-saltern-haven",
        "material_culture",
        "Iron Age to Chola Era",
        "Umanar guilds managed tidal salterns and inland supply caravans based out of Kovalam.",
        "Chengalpattu Gazetteer"
    ],
    [
        "place-kovalam-ancient-thondai-saltern-haven",
        "hosts",
        "technology-tidal-feeder-canals-tamped-clay-pans-and-wooden-salt-scrapers",
        "material_culture",
        "Iron Age to Modern Era",
        "Kovalam estuarine backwaters hosted expansive solar saltpans and tidal feeder channels.",
        "Thondai Saltern Grants"
    ],
    [
        "technology-solar-wind-drying-mound-stacking-and-bittern-drainage",
        "purifies",
        "artifact-umanar-bullock-carts-palm-leaf-salt-sacks-and-measuring-marakkals",
        "material_culture",
        "Iron Age to Modern Era",
        "Conical mound stacking drains bitter magnesium liquor to yield pure white salt for caravan transport.",
        "Chemical Technology of Salt"
    ],
    [
        "concept-halite-cubic-cleavage-taste-physics-and-meat-preservation",
        "utilizes",
        "artifact-umanar-bullock-carts-palm-leaf-salt-sacks-and-measuring-marakkals",
        "material_culture",
        "Iron Age to Modern Era",
        "Halite crystal cleavage and osmotic properties make harvested salt the premier preservative for fish and meats.",
        "Food Microbiology"
    ],
    [
        "technology-tidal-feeder-canals-tamped-clay-pans-and-wooden-salt-scrapers",
        "employs",
        "artifact-terracotta-brine-pitchers-wooden-spades-and-salt-crystals",
        "material_culture",
        "Iron Age to Modern Era",
        "Saltern operators utilized earthenware brine pitchers and non-corrosive hardwood spades.",
        "Ethnographic Museum Collections"
    ],
    [
        "text-ahananuru-and-narrinai-on-umanar-salt-caravans-and-salterns",
        "documents",
        "place-kovalam-ancient-thondai-saltern-haven",
        "material_culture",
        "Sangam Era",
        "Sangam verses document the vast coastal salterns and booming Umanar trade along northern Thondai ports.",
        "Narrinai 183"
    ]
]

def get_embedding(text: str) -> list:
    resp = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("=== Phase 1: Markdown Dossiers ===")
    for d in DOSSIERS:
        cat_dir = os.path.join(DOSSIER_DIR, d["category"] + "s")
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
