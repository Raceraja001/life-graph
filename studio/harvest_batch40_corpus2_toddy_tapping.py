#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Palmyra Palm Wine Toddy Tapping, Fermentation Pyrotechnics & Madu-Maram Hydraulics
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
        "file": "knowledge/texts/text-porunararruppadai-and-kuruntokai-verses-on-fermented-sweet-palm-wine.md",
        "slug": "text-porunararruppadai-and-kuruntokai-verses-on-fermented-sweet-palm-wine",
        "category": "text",
        "name_en": "Porunararruppadai & Kuruntokai: Sangam Verses on Fragrant Panang-Kallu, Toddy Bazaars & Banquets",
        "name_ta": "பொருநராற்றுப்படை மற்றும் குறுந்தொகை - பனங்கள், கள்ளுக்கடை மற்றும் சங்க கால விருந்துப் பாடல்கள்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "palai",
        "summary_en": "Sangam literary verses in Porunararruppadai, Kuruntokai, and Malaipadukadam detailing the sweet and fermented palm wines (panang-kallu, thenkallu, and matta-kallu) drawn from palmyra trees, describing village wayside taverns, buffalo-horn drinking cups, and royal feasts.",
        "summary_ta": "பொருநராற்றுப்படை, குறுந்தொகை மற்றும் மலைபடுகடாம் பாடல்களில் நுரைத்த பனங்கள், கள்ளுக்கடைகள், மாட்டுக்கொம்பு கிண்ணங்கள் மற்றும் மன்னர்களின் போர் விருந்துகள் பற்றிய வரலாற்றுப் பதிவுகள்.",
        "sources": [
            "Porunararruppadai 84-93",
            "Kuruntokai 113",
            "Malaipadukadam 170-175",
            "Purananuru 24"
        ],
        "content": "# Porunararruppadai & Kuruntokai: Sangam Palm Wine\n\nThe Sangam anthologies preserve abundant cultural and technical descriptions of palm sap and wine (*kallu*):\n\n> *\"In the cool shade of spreading palmyra palms, travelers rest and drink the foaming, sweet fermented liquor (thentoddy) poured from bamboo jars, smelling of wild honey and white flowers...\"* (Porunararruppadai 84–90)\n\n> *\"Like the clear sap oozing drop by drop into the clay pot tied to the trimmed crown of the tall palm tree in the dry wasteland...\"* (Kuruntokai 113)\n\nThe classical texts distinguish multiple stages of palm sap:\n- **Padhaneer / Thelivu**: Fresh, unfermented sweet sap gathered at dawn, clear as distilled water.\n- **Kallu / Mattu**: Wild-fermented, effervescent, mildly alcoholic wine (4–6% ABV) consumed in community taverns (*kallu-kadai*).\n- **Ariyal**: Matured, clarified vintage palm wine reserved for royal bards and victorious chieftains."
    },
    {
        "file": "knowledge/concepts/concept-borassus-spadix-inflorescence-sap-phloem-translocation-and-sucrose-osmosis.md",
        "slug": "concept-borassus-spadix-inflorescence-sap-phloem-translocation-and-sucrose-osmosis",
        "category": "concept",
        "name_en": "Borassus Spadix Inflorescence Physiology: Phloem Sap Translocation, Sucrose Flux and Hydraulic Pressure",
        "name_ta": "பனை பாளை உடற்கூறியல்: சாறு பாய்ம இயற்பியல், சுக்ரோஸ் சவ்வூடுபரவல் மற்றும் பாளை அழுத்தம்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "palai",
        "summary_en": "The botanical physiology of the palmyra palm (Borassus flabellifer) spadix inflorescence: vascular phloem transport mechanics under hydrostatic pressure gradients, daily sucrose flux (10-15% sugar concentration), and the hormonal stimulation of sap flow through controlled mechanical bruising.",
        "summary_ta": "பனை மரத்தின் பூம்பாளை உடற்கூறியல்: புளோயம் நாளக் குழாய்களில் சுக்ரோஸ் சாறு கடத்தல், நீரியல் அழுத்த வேறுபாடுகள் மற்றும் பாளையை நசுக்குவதன் மூலம் சாறு சுரப்பைத் தூண்டும் உயிரியல் முறை.",
        "sources": [
            "Indian Journal of Plant Physiology",
            "Phloem Sap Translocation in Arecaceae",
            "Palmyra Palm Botanical Monograph"
        ],
        "content": "# Palmyra Spadix Physiology & Phloem Flux\n\nThe extraordinary sap yield of the palmyra palm (*Borassus flabellifer*) relies on specialized vascular architecture:\n\n**Vascular Phloem Dynamics:**\nDuring the flowering season (January to June), the palm mobilizes vast reserves of starch stored in its trunk xylem rays. This starch is converted to sucrose and translocated through sieve-tube elements of the inflorescence stalk (*spadix* or *paalai*) at high turgor pressures exceeding 1.5 MPa.\n\n**Sap Composition:**\nFreshly tapped palmyra sap (*padhaneer*) is a rich biological fluid:\n- **Sucrose**: 10.5% – 14.8% by weight\n- **Reducing Sugars (Glucose & Fructose)**: 0.8% – 1.5%\n- **Proteins & Amino Acids**: 0.35% (rich in glutamic acid and aspartate)\n- **Minerals**: High in potassium ($120\\text{ mg/100ml}$), calcium, and phosphorus\n- **pH**: Neutral to slightly alkaline (7.2 – 7.6) when tapped fresh with lime.\n\n**Bruising Response:**\nControlled mechanical bruising of the spadix stimulates plant wound hormones (ethylene and traumatin), preventing premature callose deposition and keeping sieve plates permanently open for continuous exudation (up to 4–6 liters per day per tree)."
    },
    {
        "file": "knowledge/technologies/technology-panang-kallu-spadix-bruising-lime-coating-and-earthen-pot-tapping.md",
        "slug": "technology-panang-kallu-spadix-bruising-lime-coating-and-earthen-pot-tapping",
        "category": "technology",
        "name_en": "Spadix Bruising Technology: Wooden Pincer Crushing, Slit Slicing and Terracotta Sap Collection",
        "name_ta": "பாளை நசுக்கல் நுட்பம்: மர இடுக்கிக் கவ்வுதல், மெல்லிய சீவல் மற்றும் மண்பானை சாறு சேகரிப்பு",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "palai",
        "summary_en": "The operational sequence of traditional Tamil palm sap tapping: crushing the immature inflorescence spadix with wooden bone-pincers (kattai) twice daily for a week, fine transverse razor-slicing of the tip to sever phloem conduits, and attaching earthen collection pots (muttai) to capture continuous exudation.",
        "summary_ta": "மரபு பனை ஏறும் நுட்பம்: இளம் பூம்பாளையை மர இடுக்கியால் ஏழு நாட்கள் காலை மாலை நசுக்கி, நுனியை மெல்லியதாக சீவி, மண்பானைகளைக் கட்டி சொட்டு சொட்டாக சாறு சேகரிக்கும் முறை.",
        "sources": [
            "State Palm Products Cooperative Federation Manuals",
            "Ethnobiology of Traditional Palm Tappers",
            "Tamil Rural Technologies"
        ],
        "content": "# Spadix Bruising & Sap Harvesting Technology\n\nPalmyra sap extraction requires extraordinary surgical skill from master tappers (*saanar*):\n\n**1. Conditioning the Spadix (*Paalai Nasingudhal*):**\nThe tapper ascends the 25-meter trunk twice daily. Grasping the young, unexpanded spadix (male or female), he gently crushes the tissues from base to tip using a pair of notched hardwood or bone pincers (*paalai-kattai*). This mechanical massage stimulates hormonal exudation without tearing the exterior protective sheath.\n\n**2. Tip Slicing (*Paalai Seevudhal*):**\nAfter 7 days of daily bruising, the tip of the spadix is sliced transversely with an ultra-sharp, curved tapping knife (*seevuk-kathi*). A paper-thin sliver (1 mm) is shaved off twice daily (dawn and dusk) to slice through clotted latex and expose fresh open ends of vascular sieve tubes.\n\n**3. Sap Collection Vessel (*Kallu-Muttai*):**\nThe bruised, sliced spadix is bent downward into the neck of an unglazed terracotta pot or dried bottle gourd (*sorai-kudakkai*) suspended from the petiole with coir twine.\n- For **fermented toddy (*kallu*)**: The interior of the pot is left uncoated; wild yeasts residing in the clay pores trigger immediate fermentation.\n- For **sweet unfermented sap (*padhaneer*)**: The interior is thoroughly lined with wet slaked lime (*chunnambu*)."
    },
    {
        "file": "knowledge/artifacts/artifact-kallu-muttai-chunnambu-coated-clay-pots-bone-bruisers-and-climbing-loops.md",
        "slug": "artifact-kallu-muttai-chunnambu-coated-clay-pots-bone-bruisers-and-climbing-loops",
        "category": "artifact",
        "name_en": "Kallu-Muttai Terracotta Pots, Bone Spadix Pincers, Palmyra Sheath Knives and Coir Climbing Foot-Loops",
        "name_ta": "கள்ளு முட்டை மண்பானைகள், எலும்பு இடுக்கிகள், பனை நறுக்குக் கத்திகள் மற்றும் தளை நார்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "palai",
        "summary_en": "The functional toolkit of the classical Tamil palm climber and tapper: spherical narrow-necked earthen pots (kallu-muttai), hardwood/bone spadix pincers (paalai-kattai), curved high-carbon steel shaving knives housed in horn sheaths, and braided palmyra fiber climbing foot-loops (thalai).",
        "summary_ta": "பனை ஏறும் கலைஞரின் பாரம்பரிய உபகரணங்கள்: குறுகிய கழுத்துடைய மண்பானைகள், பாளை இடுக்கி கட்டைகள், மாட்டுக்கொம்பு உறையிலுள்ள சீவு கத்திகள் மற்றும் கால்களை இணைக்கும் தளை நார் கயிறு.",
        "sources": [
            "Government Museum Chennai: Ethnographic Collections",
            "Tirunelveli District Archaeological Survey",
            "Traditional Crafts of Southern Tamil Nadu"
        ],
        "content": "# Palmyra Tapper's Toolkit: Material Culture\n\nThe material equipment of the traditional climber represents centuries of ergonomic refinement:\n\n**1. Thalai / Thalai-Kayiru (Foot Climbing Loop):**\nA figure-eight loop braided from tough, sun-cured palmyra leaflet fibers (*panai-naaru*). Placed across the insteps of both feet, it binds them at a fixed distance (20 cm), allowing the diver to grip the rough corrugated trunk leaf-bases securely without slipping.\n\n**2. Paalai-Kattai (Spadix Pincer):**\nTwo shaped sticks of dense tamarind or vaagai hardwood joined by a pivot cord, or carved from water buffalo rib-bone. The interior gripping faces are notched to gently compress inflorescence stalks without shearing external fibrous rind.\n\n**3. Seevuk-Kathi (Slicing Knife):**\nA short, broad-bladed knife forged from wrought iron or tempered crucible steel (*ukku*), razor-honed on a fine sandstone river pebble. Carried in a wooden or buffalo-horn scabbard (*kathi-koodu*) strapped to the tapper's waist.\n\n**4. Kallu-Muttai (Terracotta Tapping Pot):**\nSpherical terracotta pot (2 to 3 liters capacity) with a flared lip designed to slide snugly under the dripping spadix. Porous low-fired earthenware facilitates evaporative cooling, preventing sap spoilage in sweltering 40°C afternoon sun."
    },
    {
        "file": "knowledge/concepts/concept-spontaneous-yeast-fermentation-saccharomyces-and-zymomonas-bio-kinetics.md",
        "slug": "concept-spontaneous-yeast-fermentation-saccharomyces-and-zymomonas-bio-kinetics",
        "category": "concept",
        "name_en": "Spontaneous Palm Sap Fermentation: Saccharomyces Cerevisiae, Zymomonas Mobilis & Ethanol Bio-Kinetics",
        "name_ta": "பனைச்சாறு இயற்கை நொதித்தல்: ஈஸ்ட் மற்றும் பாக்டீரியா எத்தனால் வேதியியல் மற்றும் நுரைப்பு இயற்பியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "palai",
        "summary_en": "Microbiology and biochemistry of spontaneous palm sap fermentation: wild yeast strains (Saccharomyces cerevisiae, Pichia, and Candida) alongside ethanol-producing bacterium Zymomonas mobilis converting 12% sucrose into 4.5-6% ethanol, carbon dioxide effervescence, and lactic/acetic acid flavoring compounds within 12 hours.",
        "summary_ta": "பனை மரச் சாற்றில் இயல்பாக நிகழும் நொதித்தல் வேதியியல்: சாற்றிலுள்ள சுக்ரோஸை 12 மணி நேரத்தில் 5% எத்தனாலாக மாற்றும் ஈஸ்ட் மற்றும் சைகோமோனாஸ் பாக்டீரியாக்களின் உயிரியல் வினைகள்.",
        "sources": [
            "Applied Microbiology and Biotechnology: Palm Wine Fermentation",
            "Food Chemistry: Bio-kinetics of Toddy",
            "Journal of Ethnobiology and Ethnomedicine"
        ],
        "content": "# Spontaneous Palm Sap Fermentation Biochemistry\n\nUntreated palmyra sap represents an ideal culture medium that undergoes rapid multi-species fermentation:\n\n**Microbial Consortium:**\n- **Yeasts**: *Saccharomyces cerevisiae* dominates the alcoholic fermentation, converting sugars to ethanol. Non-Saccharomyces species (*Pichia*, *Hanseniaspora*) contribute complex esters (banana, apple, floral aromatics).\n- **Bacteria**: *Zymomonas mobilis* (fast-acting bacterium utilizing the Entner-Doudoroff pathway to produce ethanol twice as fast as yeast) and lactic acid bacteria (*Leuconostoc mesenteroides*) which impart pleasant refreshing tartness.\n\n**Fermentation Phases & Kinetics:**\n1. **0 to 6 Hours (Sweet Effervescence)**: Rapid sugar consumption. Sucrose drops from 12% to 6%; ethanol reaches 1.5–2.5%. High CO2 evolution creates the white, frothy head celebrated in Sangam poems.\n2. **6 to 18 Hours (Peak Toddy / Kallu)**: Maximum ethanol concentration (4.8% to 6.2% ABV). Balanced sweet-sour profile, pH drops from 7.0 to 4.2.\n3. **> 24 Hours (Acetification)**: *Acetobacter* bacteria oxidize ethanol into acetic acid, turning the beverage into palm vinegar (*panam-kaadi*)."
    },
    {
        "file": "knowledge/institutions/institution-saanar-and-panai-yerigal-guild-of-master-palmyra-climbers-and-tappers.md",
        "slug": "institution-saanar-and-panai-yerigal-guild-of-master-palmyra-climbers-and-tappers",
        "category": "institution",
        "name_en": "Saanar & Panai-Yerigal Corporation of Hereditary Palm Climbers, Tapping Guilds & Toll Inscriptions",
        "name_ta": "சாணார் மற்றும் பனை ஏரிகள் தொழிற்கழகம், மரபு பனை ஏறும் கலைஞர்கள் மற்றும் வரி ஆவணங்கள்",
        "era": "Sangam Era to Medieval Era",
        "year_start": -300,
        "year_end": 1400,
        "thinai": "palai",
        "summary_en": "The social history and corporate status of ancient Tamil palm tappers (Saanar, Sandar, and Panai-Yerigal): specialized guilds managing communal groves, royal palm tree taxes (panai-vari and tharikku-irai) recorded in Chola and Pandya epigraphs, and their vital contribution to drought-zone rural survival.",
        "summary_ta": "பண்டைய தமிழ் பனைத் தொழிலாளர்களின் சமூக வரலாறு மற்றும் கழகங்கள்: சோழ மற்றும் பாண்டியர் கல்வெட்டுகளில் பதிவான பனை வரி, தறிக்கு இறை, மற்றும் வறண்ட நிலத்தின் பஞ்ச நிவாரணிகளாக விளங்கிய பனை ஏறும் சமூகங்களின் முக்கியத்துவம்.",
        "sources": [
            "South Indian Inscriptions Vol. XIV (Pandya Inscriptions)",
            "Chola Revenue Administration: Tree Taxes",
            "Castes and Tribes of Southern India: Shanar"
        ],
        "content": "# Saanar & Panai-Yerigal Guilds\n\nPalmyra tapping communities formed a crucial agrarian constituency across the arid and coastal tracts (*Palai* and *Neithal*) of southern Tamil Nadu:\n\n**Guild Autonomy & Collective Tree Rights:**\nHereditary tapper clans maintained cooperative rights over vast wild palmyra groves (*panang-kaadu*). Inscriptions from Tirunelveli and Ramanathapuram record collective lease agreements granted by village assemblies (*Sabha* and *Ur*) allocating exclusive seasonal harvesting rights to named tapper associations.\n\n**Inscriptional Revenue Records:**\nMedieval epigraphs document specific royal levies on palmyra tapping:\n- *Panai-vari*: Tax levied per productive palm tree yielding sap.\n- *Ezhupun-panai*: Exemption granted for newly planted trees during the 15-year gestation period before first spadix production.\n- *Kallu-irai*: Royal excise duty levied on commercial distribution of fermented palm wine in urban market squares.\n\n**Arid Ecology Guardians:**\nBecause palmyra palms survive severe droughts that wipe out rice and millet crops, tapper guilds were the primary providers of famine calories—supplying high-energy sweet sap (*padhaneer*), palm jaggery, edible root sprouts (*panang-kizhangu*), and edible kernel meat (*nongu*)."
    },
    {
        "file": "knowledge/technologies/technology-padhaneer-sweet-sap-thermal-concentration-and-anti-fermentation-lime.md",
        "slug": "technology-padhaneer-sweet-sap-thermal-concentration-and-anti-fermentation-lime",
        "category": "technology",
        "name_en": "Padhaneer Sweet Sap Stabilization: Calcium Hydroxide (Lime) Anti-Fermentation Coating & Preservation",
        "name_ta": "பதநீர் காரப் பாதுகாப்பு: சுண்ணாம்பு பூசி நொதித்தல் தடுத்தல் மற்றும் இனிப்புச் சாறு பாதுகாப்பு",
        "era": "Iron Age to Modern Era",
        "year_start": -400,
        "year_end": 2000,
        "thinai": "palai",
        "summary_en": "The chemical preservation technology converting perishable palm sap into sweet, non-alcoholic Padhaneer: coating collection pots with slaked lime (calcium hydroxide, Ca(OH)2) to elevate pH above 10.5, inhibiting yeast zymase enzymes and bacteria, enabling raw consumption or boiling down into palm candy.",
        "summary_ta": "பனைசாறு நொதித்து கள்ளாக மாறுவதைத் தடுக்கும் வேதியியல் முறை: சேகரிக்கும் பானைகளில் நீற்றுச் சுண்ணாம்பு (கால்சியம் ஹைட்ராக்சைடு) பூசி pH அளவை 10.5க்கு உயர்த்தி, ஈஸ்ட் வளர்ச்சியை முடக்கி இனிப்புப் பதநீராக பாதுகாக்கும் முறை.",
        "sources": [
            "Biochemical Studies on Palm Sap Stabilization",
            "Journal of Food Processing and Preservation",
            "Traditional Jaggery Making in Tamil Nadu"
        ],
        "content": "# Padhaneer Stabilization Chemistry\n\nWithout chemical intervention, fresh palmyra sap ferments into acidic toddy within 3 hours under tropical temperatures. Ancient Tamils resolved this using an elegant mineral anti-microbial barrier:\n\n**Slaked Lime Anti-Microbial Mechanism:**\nBefore hanging the collection pot on the tree, the tapper smears its interior walls with slaked lime paste (*chunnambu* – calcium hydroxide, $\\text{Ca(OH)}_2$).\n- **Alkaline Shock**: As sap drops into the pot, dissolving lime raises the liquid pH to 10.5 – 11.5.\n- **Enzymatic Inhibition**: This alkaline shift immediately denatures the zymase and invertase enzymes of wild yeasts, rendering them completely inactive.\n- **Bactericidal Action**: Bacterial cell membranes are disrupted by the high hydroxyl ion concentration ($\\text{OH}^-$), preventing souring.\n\n**Nutritional & Culinary Value:**\nLime-stabilized sap (*padhaneer*) remains completely alcohol-free, sweet, and enriched with bioavailable calcium. It can be drunk fresh as a coolant or boiled down over open biomass furnaces in copper caldrons to crystallize into medicinal palm candy (*panang-kalkandu*) and dark jaggery (*karupatti*)."
    },
    {
        "file": "knowledge/places/place-udangudi-ancient-pandya-palmyra-toddy-haven.md",
        "slug": "place-udangudi-ancient-pandya-palmyra-toddy-haven",
        "category": "place",
        "name_en": "Udangudi: Ancient Pandyan Palmyra Basin Haven, Teri Dune Sand Aquifers & Tapping Sanctuary",
        "name_ta": "உடன்குடி - பண்டைய பாண்டியர் பனைவளத் தளம், தேரி மணல் நீரூற்று மற்றும் பதநீர் பெருநகரம்",
        "era": "Iron Age to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "palai",
        "summary_en": "Historic palmyra forest and toddy-tapping sanctuary located in the red sand dune (Teri) country of Thoothukudi district, renowned across Tamil history as the supreme center of palmyra cultivation, sweet sap harvesting, GI-tagged palm jaggery, and unbroken hereditary palm culture.",
        "summary_ta": "தூத்துக்குடி மாவட்டத்தில் தேரி செம்மணல் குன்றுகளுக்கு மத்தியில் அமைந்துள்ள புகழ்பெற்ற பனைவளத் தளம்: அடர்ந்த பனை மரக் காடுகள், சிறந்த பதநீர் மற்றும் புவிசார் குறியீடு பெற்ற உடன்குடிக் கருப்பட்டி உற்பத்தியின் வரலாற்று மையம்.",
        "sources": [
            "Thoothukudi District Historical Gazette",
            "Geographical Indications Registry: Udangudi Panangkarupatti",
            "Teri Dunes Archaeological & Ecological Survey"
        ],
        "content": "# Udangudi: Pandyan Palmyra Haven\n\nNestled amidst the crimson dunes of the *Teri* country in southeastern Tamil Nadu, Udangudi represents the quintessential palmyra civilization:\n\n**Geographic & Ecological Uniqueness:**\nUdangudi sits over a massive coastal aeolian sand aquifer. While the surface appears as arid, red sand dunes (*teri*), the porous sand absorbs 100% of monsoonal rainfall without surface runoff, storing sweet groundwater within reach of deep-rooted palmyra taproots (*panai-aaniver*). Over five million palmyra trees flourish here without artificial irrigation.\n\n**The Capital of Palm Products:**\nFor over two millennia, Udangudi has been the epicenter of palm sap economics:\n- During the tapping season (March to August), thousands of master climbers scale 40–50 trees twice daily.\n- The sap harvested here possesses exceptionally high brix (14–16% sugar), attributed to the mineral-rich red dune soils.\n- The town is celebrated globally for *Udangudi Panangkarupatti* (Geographical Indication registered), renowned for its dark mahogany color and absence of synthetic additives.\n\n**Cultural Resilience:**\nThe region preserves ancient terminology, festivals dedicated to the palmyra tree (*Thala-Vilakku*), and artisanal metal knife forging guilds dedicated exclusively to palm culture."
    },
    {
        "file": "knowledge/concepts/concept-teri-red-sand-dune-aquifer-hydrology-and-palmyra-drought-resilience.md",
        "slug": "concept-teri-red-sand-dune-aquifer-hydrology-and-palmyra-drought-resilience",
        "category": "concept",
        "name_en": "Teri Red Sand Dune Aquifer Hydrology, Sub-Surface Moisture Storage & Deep Palmyra Taproot Dynamics",
        "name_ta": "தேரி செம்மணல் குன்று நீரியல், நிலத்தடி ஈரப்பதம் மற்றும் பனை ஆணிவேர் வறட்சி எதிர்ப்பு இயற்பியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "palai",
        "summary_en": "Hydrogeology of the southern Tamil Nadu Pleistocene Teri red sand formations: high-permeability aeolian sands capturing monsoon precipitation without evaporation loss, creating perched freshwater lenses tapped by the extensive 15-20 meter fibrous taproot network of Borassus flabellifer.",
        "summary_ta": "தென் தமிழக தேரி செம்மணல் அமைப்புகளின் நீரியல் இயற்பியல்: மழைநீரை ஆவியாகாமல் உள்வாங்கி நிலத்தடி நீர் வில்லைகளை உருவாக்கும் மணல் குன்றுகள் மற்றும் 20 மீட்டர் ஆழம் பாயும் பனை வேர்களின் வறட்சி எதிர்ப்பு இயல்பு.",
        "sources": [
            "Geological Survey of India: Teri Formations",
            "Hydrogeology Journal: Coastal Aquifers of Tamil Nadu",
            "Ecological Studies in Arid Zones"
        ],
        "content": "# Teri Dune Hydrology & Palmyra Root Mechanics\n\nThe survival and sap abundance of palmyra trees in semi-arid southern Tamil Nadu are explained by unique hydrogeology:\n\n**Teri Dune Geology:**\nThe *Teri* dunes consist of deep, iron-coated quartz sands formed during the late Pleistocene. Their hydraulic conductivity is exceptionally high ($> 15\\text{ m/day}$). When episodic northeast monsoon rains hit the dunes, water infiltrates downward instantaneously, avoiding surface evaporation. The sand retains capillary moisture at depths between 3 and 12 meters even during 10-month droughts.\n\n**Palmyra Taproot Architecture:**\n- **Vertical Penetration**: *Borassus flabellifer* germinates with an aggressive geotropic hypocotyl, driving a primary root down to 15–20 meters depth to anchor in permanent sub-dune water tables.\n- **Fibrous Root Netting**: Thousands of secondary fibrous adventitious roots branch radially through the upper sand strata, binding the loose dunes and preventing desertification.\n- **Osmotic Adaptation**: The tree maintains low root xylem osmotic potential ($-2.5\\text{ MPa}$), enabling continuous hydraulic pull of moisture to the crown even under extreme arid ambient conditions."
    },
    {
        "file": "knowledge/artifacts/artifact-thari-panai-maram-leather-climbing-straps-tapping-knives-and-gourd-flacons.md",
        "slug": "artifact-thari-panai-maram-leather-climbing-straps-tapping-knives-and-gourd-flacons",
        "category": "artifact",
        "name_en": "Thari Leather Climbing Belts, Horn Tapping Knives, Bamboo Spouts and Dried Gourd Toddy Flacons",
        "name_ta": "தறி தோல் ஏறுவார் பட்டை, மாட்டுக்கொம்பு கத்திகள், மூங்கில் புனல்கள் மற்றும் சுரைக்குடுக்கைகள்",
        "era": "Iron Age to Modern Era",
        "year_start": -400,
        "year_end": 2000,
        "thinai": "palai",
        "summary_en": "The traditional secondary climbing and tapping material assemblage: buffalo-hide body harness belts (thari), horn-mounted trimming knives, split-bamboo sap guides (ottu), and hollowed bottle gourd containers (kudakkai) used to transport fresh toddy from crowns to village bazaars.",
        "summary_ta": "பனைத் தொழிலாளர்களின் துணை உபகரணங்கள்: எருமைத் தோல் இடுப்புப் பட்டை, மூங்கில் சாறு வடிகால்கள் மற்றும் மரத்தாலான சுரைக்குடுக்கை குடுவைகள்.",
        "sources": [
            "Ethnographic Museum Collections: Tamil University",
            "Traditional Hunting and Foraging Technologies",
            "Field Documentation of Tirunelveli Crafts"
        ],
        "content": "# Thari Belts, Horn Knives & Gourd Vessels\n\nThe secondary gear supporting daily tree ascents represents specialized vernacular engineering:\n\n**1. Thari (Buffalo-Leather Climbing Belt):**\nA wide, supple belt (12 cm wide, 1.8 m long) made from vegetable-tanned, oil-cured water buffalo hide. Looped around the tree trunk and the climber's lower back, it supports the climber's entire body weight, leaving both hands free to slice the spadix and handle pots.\n\n**2. Kombu-Kathi (Horn-Handled Knife):**\nForged with a razor-thin crescent tip. The handle is carved from seasoned cattle horn which provides a non-slip, tacky grip even when soaked in sticky palm sap.\n\n**3. Ottu (Split-Bamboo Conduits):**\nA 10 cm segment of thin reed or bamboo sliced into a half-pipe trough. Wedged beneath the freshly cut spadix, it channels dripping sap cleanly into the collecting pot, preventing drops from blowing away in high coastal winds.\n\n**4. Sorai-Kudakkai (Bottle Gourd Flacon):**\nDried, hollowed shells of the bottle gourd (*Lagenaria siceraria*), smoked over hearth fires to harden the cellulose rind. Used as lightweight, unbreakable canteens to carry sap down the tree."
    }
]

EDGES = [
    [
        "text-porunararruppadai-and-kuruntokai-verses-on-fermented-sweet-palm-wine",
        "DOCUMENTS",
        "institution-saanar-and-panai-yerigal-guild-of-master-palmyra-climbers-and-tappers",
        "core",
        "Sangam Era",
        "Porunararruppadai documents palm wine feasts and traditional tapping culture",
        "Porunararruppadai 84-93"
    ],
    [
        "technology-panang-kallu-spadix-bruising-lime-coating-and-earthen-pot-tapping",
        "HARVESTS",
        "concept-borassus-spadix-inflorescence-sap-phloem-translocation-and-sucrose-osmosis",
        "core",
        "Iron Age to Modern Era",
        "Bruising and slicing techniques tapped into pressurized phloem sap streams",
        "Palmyra Palm Botanical Monograph"
    ],
    [
        "artifact-kallu-muttai-chunnambu-coated-clay-pots-bone-bruisers-and-climbing-loops",
        "IMPLEMENTS",
        "technology-panang-kallu-spadix-bruising-lime-coating-and-earthen-pot-tapping",
        "core",
        "Iron Age to Modern Era",
        "Clay pots and bone bruisers formed the indispensable material kit of tappers",
        "Government Museum Ethnographic Catalog"
    ],
    [
        "technology-panang-kallu-spadix-bruising-lime-coating-and-earthen-pot-tapping",
        "TRIGGERS",
        "concept-spontaneous-yeast-fermentation-saccharomyces-and-zymomonas-bio-kinetics",
        "core",
        "Iron Age to Modern Era",
        "Raw sap in uncoated pots underwent spontaneous fermentation into alcoholic toddy",
        "Applied Microbiology Biotechnology"
    ],
    [
        "technology-padhaneer-sweet-sap-thermal-concentration-and-anti-fermentation-lime",
        "INHIBITS",
        "concept-spontaneous-yeast-fermentation-saccharomyces-and-zymomonas-bio-kinetics",
        "core",
        "Iron Age to Modern Era",
        "Slaked lime coating inhibited wild yeasts, preserving sap as sweet padhaneer",
        "Food Processing Preservation"
    ],
    [
        "institution-saanar-and-panai-yerigal-guild-of-master-palmyra-climbers-and-tappers",
        "CONCENTRATED_AT",
        "place-udangudi-ancient-pandya-palmyra-toddy-haven",
        "core",
        "Iron Age to Modern Era",
        "Hereditary tapping guilds were heavily concentrated in the Udangudi palmyra basin",
        "Thoothukudi District Historical Gazette"
    ],
    [
        "concept-teri-red-sand-dune-aquifer-hydrology-and-palmyra-drought-resilience",
        "SUSTAINS",
        "place-udangudi-ancient-pandya-palmyra-toddy-haven",
        "core",
        "Iron Age to Modern Era",
        "Sub-dune aquifers provided moisture sustaining millions of palmyra trees in Udangudi",
        "Geological Survey of India Teri Formations"
    ],
    [
        "artifact-thari-panai-maram-leather-climbing-straps-tapping-knives-and-gourd-flacons",
        "USED_BY",
        "institution-saanar-and-panai-yerigal-guild-of-master-palmyra-climbers-and-tappers",
        "core",
        "Iron Age to Modern Era",
        "Climbing belts and gourd flacons were the specialized gear of hereditary tappers",
        "Tamil University Ethnographic Collections"
    ],
    [
        "technology-padhaneer-sweet-sap-thermal-concentration-and-anti-fermentation-lime",
        "PRODUCES_AT",
        "place-udangudi-ancient-pandya-palmyra-toddy-haven",
        "core",
        "Iron Age to Modern Era",
        "Udangudi became famous worldwide for lime-stabilized sap and palm jaggery",
        "GI Registry Udangudi Panangkarupatti"
    ],
    [
        "text-porunararruppadai-and-kuruntokai-verses-on-fermented-sweet-palm-wine",
        "PRAISES",
        "technology-panang-kallu-spadix-bruising-lime-coating-and-earthen-pot-tapping",
        "core",
        "Sangam Era",
        "Kuruntokai explicitly describes sap oozing into clay pots hung from palm trees",
        "Kuruntokai 113"
    ]
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Embedding failed: {res.text}")
    return res.json()["embedding"]

def main():
    print("Starting Ingestion Batch 40: Ancient Tamil Palmyra Palm Wine Toddy Tapping, Fermentation Pyrotechnics & Madu-Maram Hydraulics...")
    
    # Phase 1: Write Dossiers
    print("Phase 1: Writing Markdown Dossiers...")
    for d in DOSSIERS:
        fpath = os.path.join(MOOLAM_KNOWLEDGE, d["file"])
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(d["content"].strip() + "\n")
        print(f"  ✓ Written: {d['file']}")

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Phase 2: Upsert Lore Nodes
    print("Phase 2: Upserting Lore Nodes...")
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
                properties = EXCLUDED.properties;
        """, (
            str(uuid.uuid4()), slug, d["category"], d["name_en"], d["name_ta"],
            d["era"], d["year_start"], d["year_end"], d.get("thinai"),
            d["summary_en"], d["summary_ta"], d["sources"], "core", props
        ))
        nodes_upserted += 1
        print(f"  ✓ Upserted node: {slug}")
    conn.commit()

    # Phase 3: Insert Lore Edges
    print("Phase 3: Inserting Lore Edges...")
    edges_inserted = 0
    for edge in EDGES:
        src, rel, tgt, layer, era, desc, evidence = edge
        cur.execute("""
            DELETE FROM lore_edges
            WHERE source_slug = %s AND relation_type = %s AND target_slug = %s;
        """, (src, rel, tgt))
        cur.execute("""
            INSERT INTO lore_edges (
                id, source_slug, relation_type, target_slug, layer, era,
                description, evidence_source
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            );
        """, (
            str(uuid.uuid4()), src, rel, tgt, layer, era, desc, evidence
        ))
        edges_inserted += 1
        print(f"  ✓ Linked: ({src}) --[{rel}]-> ({tgt})")
    conn.commit()

    # Phase 4: Embed & Insert RAG Chunks
    print("Phase 4: Embedding RAG Chunks with bge-m3:latest...")
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

    print(f"Ingestion Complete for Batch 40 Corpus! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
