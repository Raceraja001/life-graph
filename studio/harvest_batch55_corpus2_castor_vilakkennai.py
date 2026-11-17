#!/usr/bin/env python3
"""
Harvester: Batch 55 - Ancient Tamil Amanakku Castor Seed Rendering, Vilakkennai Lamp Oil & Chariot Axle Lubrication
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
        "slug": "technology-amanakku-seed-dehulling-earthen-pot-roasting-and-hot-water-float-rendering",
        "file": "technology-amanakku-seed-dehulling-earthen-pot-roasting-and-hot-water-float-rendering.md",
        "category": "technology",
        "name_en": "Amanakku Castor Seed Dehulling, Earthen Pot Roasting & Hot-Water Float Rendering Technology",
        "name_ta": "ஆமணக்கு விதை தோலுரித்தல், மண்சட்டி வறுத்தல் மற்றும் கொதிநீர் மிதப்பு எண்ணெய் பிரித்தல் தொழில்நுட்பம்",
        "era": "Sangam Era to Modern Era",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "mullai",
        "summary_en": "Traditional dryland Tamil process for extracting castor oil (vilakkennai) from Ricinus communis (amanakku) seeds: sun-drying the spiny capsules until they shatter, threshing and winnowing the mottled seeds, gently roasting them in unglazed earthen pots (mansatti), pounding them in a stone ural mortar, then boiling the mash in water so that the oil floats up as a golden layer that is skimmed with a coconut-shell ladle and clarified by slow evaporation of residual moisture.",
        "summary_ta": "ஆமணக்கு முள் காய்களை வெயிலில் உலர்த்தி வெடிக்கச் செய்து, விதைகளை அடித்துப் புடைத்து, மண்சட்டியில் மிதமாக வறுத்து, கல் உரலில் இடித்து, அந்த மாவை நீரில் கொதிக்க வைத்து மேலே மிதக்கும் பொன்னிற எண்ணெயைச் சிரட்டை அகப்பையால் வழித்தெடுத்து, ஈரம் போகக் காய்ச்சித் தெளிய வைக்கும் பாரம்பரிய விளக்கெண்ணெய் தயாரிப்பு முறை.",
        "sources": [
            "Tamil Lexicon (University of Madras), entries ஆமணக்கு and விளக்கெண்ணெய்",
            "Siddha Materia Medica (Gunapadam) on Amanakku",
            "Ethnographic Studies of Village Oil Rendering in Tamil Nadu"
        ],
        "content": "# Amanakku Castor Seed Dehulling, Earthen Pot Roasting & Hot-Water Float Rendering Technology\n\nThe castor plant (**Ricinus communis**, Tamil: **ஆமணக்கு / Amanakku**) is a hardy shrub of the red-soil dry tracts of the Tamil country. Long before the hydraulic expeller, Tamil households produced **Vilakkennai** (விளக்கெண்ணெய், literally \"lamp oil\") with nothing more than sun, fire, clay pots, stone mortars and boiling water. The household method is called *kaaychi-edutthal* (காய்ச்சி எடுத்தல்), boil-extraction, and it differs from the bullock-driven *chekku* press used for sesame.\n\n### 1. Capsule Harvest & Sun Shattering (*காய் உலர்த்தல்*)\n- Castor carries its seeds in spiny, three-chambered capsules (*முள் காய்*). Pickers cut the racemes once the lowest capsules turn from green to straw-brown, *before* the capsules shatter by themselves. A spontaneously exploding capsule can throw its seed several metres.\n- The racemes are spread on a cow-dung-plastered threshing yard (*களம்*) for 4–7 days. Thermal cycling dries the woody pericarp until it splits along its three sutures. The yard is then beaten with bamboo flails (*தடி அடித்தல்*).\n\n### 2. Dehulling & Winnowing (*தோலுரித்தல், புடைத்தல்*)\n- Seeds still in their hulls are rolled gently under a flat stone or wooden plank. This cracks off the remaining capsule fragments without crushing the brittle, mottled, glossy seed coat.\n- Winnowing in a bamboo *muram* (முறம்) sorts the dense seed (bulk density roughly 0.55–0.65 g/cm³) from the light hull chaff. Cleaned seed holds about **45–55% oil** by mass.\n- **Safety note**: the seed endosperm contains **ricin**, a highly toxic ribosome-inactivating protein. Village practice keeps children away from raw seed, and the rendering steps that follow, prolonged heat and boiling in water, are what make the final oil safe. Ricin is a water-soluble protein, it does not dissolve in the oil phase, and heat denatures it.\n\n### 3. Earthen Pot Roasting (*மண்சட்டி வறுத்தல்*)\n- The seeds are dry-roasted in a wide, unglazed earthen pan (*மண்சட்டி*) over a slow fire of dried cow-dung cakes (*வறட்டி*). They are stirred constantly with a wooden paddle until the seed coat crackles and the kernel turns pale tan, usually 10–20 minutes.\n- Why roast at all:\n  - **Cell rupture**: heat expands the moisture inside the oil-bearing cells (the oil sits in *oleosome* bodies). The cell walls rupture, so the later boiling releases far more oil.\n  - **Protein coagulation**: roasting starts denaturing the seed's storage proteins and the toxic ricin lectin before any water is added.\n  - **Even heating**: porous terracotta passes heat to the seeds gently and evenly, so the kernel does not scorch. Scorched kernels darken the oil and give it an acrid smell.\n\n### 4. Pounding (*உரலில் இடித்தல்*)\n- The warm seeds are pounded in a granite **ural** (உரல்) with a long wooden pestle (*உலக்கை*) to make a coarse, oily paste (*அரைப்பு*). The paste has to be coarse enough that the fibrous hull fragments still drain freely when it is boiled.\n\n### 5. Hot-Water Float Rendering (*கொதிநீர் மிதப்பு முறை*)\n- The paste goes into a large pot of water, about 3–4 parts water to 1 part paste by volume, and is brought to a sustained rolling boil for 1–2 hours.\n- **The physics of the float**:\n  - Castor oil (density about **0.956–0.963 g/cm³ at 20 °C**) is lighter than water (0.998 g/cm³). Once released from the ruptured cells, the droplets coalesce and rise in obedience to Stokes' law: their rise velocity grows with the density difference and with the square of the droplet radius.\n  - The boiling turbulence strips oil films from the solid particles. Heat lowers the oil's very high viscosity, so the droplets merge faster.\n  - Water-soluble proteins, including denatured ricin, mucilage and sugars, stay in the aqueous phase. Meanwhile the spent meal sinks.\n- A golden oil layer collects on the surface. The renderer skims it off repeatedly with a coconut-shell ladle (*சிரட்டை அகப்பை*) into a second clean pot.\n\n### 6. Moisture Clarification (*ஈரம் காய்ச்சுதல்*)\n- The skimmed oil still carries emulsified water. It is heated slowly in a clean pot until the faint crackle of escaping steam stops. The renderer judges the end point by sound and by the oil's clarity.\n- The oil is cooled, left to settle for 1–3 days, and decanted off any sediment. The result is a pale-amber, mildly scented oil prized as lamp fuel, an axle lubricant and a household purgative.\n- **Yield**: boil-extraction typically recovers 30–40% of seed mass as oil. That is less than a modern expeller but enough for household and temple needs.\n"
    },
    {
        "slug": "technology-temple-chariot-wooden-axle-vilakkennai-lubrication-and-pediatric-purgative-dosing",
        "file": "technology-temple-chariot-wooden-axle-vilakkennai-lubrication-and-pediatric-purgative-dosing.md",
        "category": "technology",
        "name_en": "Temple Chariot Wooden Axle Vilakkennai Lubrication & Traditional Purgative Dosing Practice",
        "name_ta": "கோவில் தேர் மர அச்சு விளக்கெண்ணெய் உயவு மற்றும் பாரம்பரிய பேதி மருந்தளவு முறை",
        "era": "Medieval Era to Modern Era",
        "year_start": 600,
        "year_end": 2026,
        "thinai": "marutham",
        "summary_en": "Two applied castor-oil technologies of Tamil temple towns: (1) greasing the massive hardwood axles and iron-banded hubs of temple chariots (ther) with thick vilakkennai, sometimes mixed with tallow or graphite-rich soot, so that they survive the slow, heavily loaded, high-friction festival procession (therottam); and (2) the household and Siddha practice of a measured purgative dose of castor oil (vilakkennai kudithal), given by bodyweight with ginger or milk, with strict caution for infants and young children.",
        "summary_ta": "(1) கோவில் தேர்த் திருவிழாவில் பல நூறு டன் எடையுடன் மெதுவாக நகரும் தேரின் பெரிய மர அச்சு மற்றும் இரும்புப் பட்டை சக்கரக் குடத்தில் அடர்த்தியான விளக்கெண்ணெய் பூசும் உயவு முறை; (2) உடல் எடைக்கேற்ப அளவிட்டு, இஞ்சி அல்லது பாலுடன் விளக்கெண்ணெய் பேதி மருந்து கொடுக்கும் வீட்டு மற்றும் சித்த மருத்துவ வழக்கம், குழந்தைகளுக்குக் கடும் எச்சரிக்கையுடன்.",
        "sources": [
            "Temple Ther Construction Manuals (Ther Sthapathi tradition)",
            "Siddha Gunapadam: Amanakku Ennai",
            "Agastyar Vaidya Tradition Texts (attributed)"
        ],
        "content": "# Temple Chariot Wooden Axle Vilakkennai Lubrication & Traditional Purgative Dosing Practice\n\n## Part A: Lubricating the Temple Chariot Axle (*தேர் அச்சுக்கு எண்ணெய் இடுதல்*)\n\nSouth Indian temple chariots (**தேர் / Ther**) are among the largest wooden vehicles ever built. The Thiruvarur Aazhi Ther is often cited at roughly 300 tonnes when fully dressed. Their running gear consists of:\n- **Axle (*அச்சு*)**: a single baulk of dense hardwood, traditionally *vengai* (Pterocarpus marsupium), *iluppai* (Madhuca longifolia) or teak, roughly squared in section and turned to a circular journal at each end.\n- **Wheel hub (*குடம்*)**: a solid timber nave bored to receive the journal. Later chariots lined the bore with wrought-iron bands or bushes.\n- **Wheels (*சக்கரம்*)**: solid or spoked, often 2–3 m in diameter.\n\n### 1. The Lubrication Regime\n- In the procession (*தேரோட்டம்*) the chariot moves at walking pace or slower, often stopping and starting as thousands of devotees haul on its ropes (*வடம்*). The rubbing speed at the journal is therefore tiny, a few centimetres per second, while the load is enormous.\n- In tribology terms, the **Stribeck curve** says that low speed, high load and high viscosity give a small Sommerfeld/Hersey number. The joint therefore runs in the **boundary and mixed lubrication regime**: no full hydrodynamic oil wedge separates the surfaces, and friction depends on the chemistry of the film stuck to the wood and iron.\n- Castor oil suits this regime unusually well (see the ricinoleic-acid concept dossier):\n  - Its **12-hydroxyl group** makes it polar. It adsorbs onto cellulose-rich wood and oxidised iron and forms a tenacious boundary film.\n  - Its **very high viscosity** (about 0.6–1.0 Pa·s at 25 °C, roughly ten times that of sesame oil) means it is not squeezed out under load and does not run off the journal in the heat of the day.\n  - Wherever the axle turns fast enough, as when the chariot rolls freely on a gentle downhill, the thick oil builds a partial **hydrodynamic wedge** that briefly lifts the load.\n\n### 2. Application Practice\n- Before the festival, the *ther* carpenters (*தச்சர்*) jack the chariot body. They clean the journal of old, gummed oil and grit, then pour warm *vilakkennai* into the hub bore and over the journal.\n- Using wide wooden greasing paddles (see the paddle artifact dossier), they work in a heavy grease of castor oil thickened with **tallow** or **lamp soot (*கரி*)**. Soot adds fine carbon particles that act as a solid lubricant once the oil film fails.\n- During long processions, attendants walk beside the wheels carrying oil pots and re-dose the hubs wherever the timber squeals or smokes.\n\n## Part B: Measured Purgative Dosing (*விளக்கெண்ணெய் பேதி*)\n\nCastor oil has a long history as a stimulant laxative in Siddha and household Tamil medicine.\n\n### 1. Traditional Practice\n- Families traditionally gave adults a purge of castor oil on a set morning, often with warm milk, ginger juice (*இஞ்சிச் சாறு*) or tamarind water to mask the oily taste, then a light *kanji* (rice gruel) diet.\n- In some families a very small, measured amount was rubbed on the navel or given to children by mouth during *pathiya* (dietary regimen) practices.\n\n### 2. Dose and Modern Safety Caution\n- In modern medicine castor oil is a strong **stimulant laxative**: the adult dose is about 15–60 mL, and it works within 2–6 hours. For children, current guidance strongly discourages self-medication. Castor oil is **not recommended for infants**, and for children it should only be given under a doctor's direction.\n- Risks include severe cramping, dehydration, electrolyte loss, and danger to the airway: aspirating an oily liquid can cause lipoid pneumonia. It is also not used in pregnancy except under medical supervision, because the same smooth-muscle action can stimulate the uterus.\n- The mechanism, ricinoleic acid activating **EP3 prostanoid receptors** on intestinal smooth muscle, is described in the EP3 concept dossier.\n"
    },
    {
        "slug": "artifact-cold-drawn-and-rendered-vilakkennai-terracotta-oil-measures-and-palmyra-funnels",
        "file": "artifact-cold-drawn-and-rendered-vilakkennai-terracotta-oil-measures-and-palmyra-funnels.md",
        "category": "artifact",
        "name_en": "Cold-Drawn & Rendered Vilakkennai, Terracotta Oil Measures & Palmyra-Leaf Funnels",
        "name_ta": "குளிர் பிழி மற்றும் காய்ச்சு விளக்கெண்ணெய், சுடுமண் எண்ணெய் அளவைகள் மற்றும் பனையோலைப் புனல்கள்",
        "era": "Sangam Era to Modern Era",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "mullai",
        "summary_en": "The material culture of castor oil: two grades of vilakkennai, pale cold-drawn chekku oil and amber hot-water rendered oil; graduated terracotta and brass oil measures (nazhi, uzhakku, aazhakku) used in temple lamp-oil accounting; tall-necked oil pots (ennai kudam); and disposable conical palmyra-leaf funnels (panai olai pookuzhal) folded to pour the viscous oil into narrow lamp wells without spillage.",
        "summary_ta": "விளக்கெண்ணெய்யின் பொருள் பண்பாடு: செக்கில் குளிராகப் பிழிந்த வெளிர் எண்ணெய் மற்றும் கொதிநீரில் காய்ச்சிய பொன்னிற எண்ணெய் என இரு தரங்கள்; கோவில் விளக்கு எண்ணெய் கணக்கில் பயன்பட்ட நாழி, உழக்கு, ஆழாக்கு போன்ற சுடுமண் மற்றும் பித்தளை அளவைகள்; நீண்ட கழுத்து எண்ணெய்க் குடங்கள்; அடர்த்தியான எண்ணெயைச் சிந்தாமல் குறுகிய விளக்குக் குழிகளில் ஊற்ற மடித்த பனையோலைக் கூம்புப் புனல்கள்.",
        "sources": [
            "Chola Temple Inscriptions on Lamp Oil Measures (South Indian Inscriptions series)",
            "Tamil Lexicon: நாழி, உழக்கு, ஆழாக்கு",
            "Ethnographic Collections of Tamil Village Oil Vessels"
        ],
        "content": "# Cold-Drawn & Rendered Vilakkennai, Terracotta Oil Measures & Palmyra-Leaf Funnels\n\n### 1. Two Grades of Vilakkennai\n- **Cold-drawn *chekku* oil (*செக்கு விளக்கெண்ணெய்*)**: pressed in the bullock-driven wooden mortar-and-pestle mill (*செக்கு / marachekku*) with no added heat. The oil is pale straw-coloured, nearly odourless, and holds the most unoxidised ricinoleic acid. It was prized for medicine, eye applications and hair care.\n- **Hot-water rendered oil (*காய்ச்சு எண்ணெய்*)**: made by the household boil-and-skim method (see the rendering technology dossier). It is amber to golden, smells faintly roasted and is slightly more acidic. It was the workhorse grade for lamps and axles.\n- Quality tests used by oil-sellers (*வாணியர்*):\n  - **String test**: a drop pulled between finger and thumb should stretch into a thread without breaking. That is a direct measure of castor oil's exceptional viscosity.\n  - **Clarity in sunlight**: water haze or sediment meant the moisture clarification had been done badly.\n  - **Wick test**: a good lamp oil burns with a steady, smokeless flame.\n\n### 2. Graduated Oil Measures (*அளவைகள்*)\n- Temple inscriptions record lamp-oil endowments in volumetric units. The traditional Tamil series runs **ஆழாக்கு (aazhakku) → உழக்கு (uzhakku) → உரி (uri) → நாழி (nazhi) → குறுணி (kuruni)**, each step roughly doubling or a fixed multiple in local practice.\n- Measures were turned in **terracotta** for everyday trade and cast in **brass or bronze** for temple storerooms (*பண்டாரம்*), where they were sometimes stamped with the temple's mark to prevent fraud.\n- Because castor oil is so viscous, measure-makers gave the vessels wide mouths and smooth, burnished interiors so that the oil drained fully and the \"dead volume\" left clinging to the walls stayed small.\n\n### 3. Oil Storage Pots (*எண்ணெய்க் குடம்*)\n- Long-necked, narrow-mouthed terracotta pots, often slipped and burnished inside to reduce seepage through the porous clay. Their necks were sealed with a palm-leaf disc and clay or beeswax to keep out dust and moisture.\n- Castor oil keeps unusually well, resisting rancidity for many months. Its dominant hydroxy fatty acid has a single double bond and oxidises more slowly than the polyunsaturated oils such as gingelly.\n\n### 4. Palmyra-Leaf Funnels (*பனையோலைப் புனல்*)\n- To fill the small oil wells of *agal* lamps and multi-wicked *kuthuvilakku* lamps, attendants folded a single **palmyra (Borassus flabellifer) leaflet** into a cone. They pinned it with a thorn or a twist of fibre and snipped the tip to set the flow rate.\n- The waxy cuticle of the palmyra leaf sheds oil, so the viscous oil slides down without soaking in. The funnel was disposable and could be burned in the hearth after the day's lamp service.\n"
    },
    {
        "slug": "artifact-castor-seed-pinnakku-fertilizer-and-massive-temple-axle-greasing-paddles",
        "file": "artifact-castor-seed-pinnakku-fertilizer-and-massive-temple-axle-greasing-paddles.md",
        "category": "artifact",
        "name_en": "Castor Seed Pinnakku Oil-Cake Fertilizer & Massive Temple Axle Greasing Paddles",
        "name_ta": "ஆமணக்குப் பிண்ணாக்கு உரம் மற்றும் கோவில் தேர் அச்சு எண்ணெய் பூசும் பெரிய மரத் துடுப்புகள்",
        "era": "Medieval Era to Modern Era",
        "year_start": 600,
        "year_end": 2026,
        "thinai": "marutham",
        "summary_en": "Two by-product and tool artifacts of the castor economy: (1) amanakku pinnakku, the toxic, ricin-bearing pressed seed cake that is never fed to cattle but is composted into paddy and betel-vine fields as a nitrogen-rich (about 4-6% N) organic manure with nematicidal and termite-deterrent action; and (2) the long-handled hardwood greasing paddles (ennai thuduppu) and coconut-fibre swabs used by ther carpenters to pack thick castor grease into chariot hub bores.",
        "summary_ta": "(1) ரிசின் நச்சு இருப்பதால் கால்நடைகளுக்குக் கொடுக்காமல், நெல் மற்றும் வெற்றிலைக் கொடிக்கால் வயல்களில் நைட்ரஜன் நிறைந்த இயற்கை உரமாகவும் நூற்புழு, கரையான் தடுப்பாகவும் இடப்படும் ஆமணக்குப் பிண்ணாக்கு; (2) தேர் தச்சர்கள் சக்கரக் குடத்தினுள் அடர்த்தியான எண்ணெய்க் கலவையைத் திணிக்கப் பயன்படுத்தும் நீண்ட கைப்பிடி கொண்ட வைரமரத் துடுப்புகள் மற்றும் தேங்காய் நார்த் துடைப்பான்கள்.",
        "sources": [
            "Tamil Nadu Agricultural University Organic Manure Notes on Castor Cake",
            "Temple Ther Maintenance Records",
            "Ethnographic Studies of Tamil Agrarian Manuring"
        ],
        "content": "# Castor Seed Pinnakku Oil-Cake Fertilizer & Massive Temple Axle Greasing Paddles\n\n## Part A: Amanakku Pinnakku (*ஆமணக்குப் பிண்ணாக்கு*)\n\n### 1. Origin and Composition\n- **Pinnakku** (பிண்ணாக்கு) is the press cake left after oil extraction. Gingelly and groundnut cakes are prized cattle feed. **Castor cake is a strict exception**: it keeps the toxic ricin protein and the allergenic CB-1A protein, so village tradition firmly forbids feeding it to livestock.\n- Typical composition: about **4–6% nitrogen**, 1.5–2% P₂O₅ and 1–1.5% K₂O, plus leftover oil and fibre.\n\n### 2. Agronomic Use\n- Farmers pound the cake, soak it, and broadcast or furrow-place it in **paddy nurseries, sugarcane and betel-vine gardens (*கொடிக்கால்*)**. It releases nitrogen slowly as soil microbes break it down.\n- **Nematicidal and pest-deterrent action**: decomposing castor cake suppresses root-knot nematodes (*Meloidogyne*) and deters termites. This is attributed to ricin and other bioactive breakdown products, and it is why the cake is especially valued in light, sandy, nematode-prone soils.\n- Applied fresh, the cake can scorch seedlings because its decay releases ammonia, so it is composted or applied 2–3 weeks before planting.\n\n## Part B: Temple Axle Greasing Paddles (*எண்ணெய்த் துடுப்பு*)\n\n### 1. Form\n- A **long-handled flat paddle**, 1–1.5 m long, carved from one piece of close-grained hardwood such as *vengai* or tamarind. Its blade is spoon-shaped, 10–15 cm wide.\n- The blade edge is kept thin and slightly flexible so that it can be worked into the narrow annular gap between the axle journal and the hub bore (*குடம்*) without gouging either surface.\n\n### 2. Use in Chariot Maintenance\n- With the chariot body jacked up, the *ther* carpenters ladle warm castor oil, or a castor–tallow–soot grease, onto the paddle. They push the grease into the hub bore with a twisting, packing stroke so that the whole bearing surface is coated.\n- **Coconut-fibre swabs (*தேங்காய் நார்*)** on sticks scrub out old, oxidised, gummy residue and road grit. Grit left in the bore acts as an abrasive and scores the journal.\n- Paddles were often blackened and oil-soaked from generations of use. In some temples they were kept with the chariot's other ritual tools and blessed before the *therottam* season.\n"
    },
    {
        "slug": "concept-ricinoleic-acid-monounsaturated-hydroxy-fatty-acid-viscosity-and-lubrication-mechanics",
        "file": "concept-ricinoleic-acid-monounsaturated-hydroxy-fatty-acid-viscosity-and-lubrication-mechanics.md",
        "category": "concept",
        "name_en": "Ricinoleic Acid: Monounsaturated Hydroxy Fatty Acid Viscosity & Lubrication Mechanics",
        "name_ta": "ரிசினோலிக் அமிலம்: ஒற்றை நிறைவுறா ஹைட்ராக்சி கொழுப்பமில பாகுத்தன்மை மற்றும் உயவு இயக்கவியல்",
        "era": "Modern Scientific Analysis",
        "year_start": 1900,
        "year_end": 2026,
        "thinai": "mullai",
        "summary_en": "Castor oil is about 85-90% ricinoleic acid (12-hydroxy-cis-9-octadecenoic acid), a C18 monounsaturated fatty acid with a hydroxyl group on carbon 12. Hydrogen bonding between these hydroxyl groups gives castor oil its anomalously high dynamic viscosity (about 600-1000 mPa.s at 25 C) and its solubility in ethanol, while the polar OH adsorbs strongly to metal and wood surfaces, giving superior boundary lubrication, high film strength and a wide viscosity-temperature tolerance for slow, heavy-load bearings.",
        "summary_ta": "ஆமணக்கு எண்ணெயில் 85-90% ரிசினோலிக் அமிலம் (12-ஹைட்ராக்சி-சிஸ்-9-ஆக்டடெசினோயிக் அமிலம்) உள்ளது. 12-ஆம் கரியணுவில் உள்ள ஹைட்ராக்சில் குழுக்களின் ஹைட்ரஜன் பிணைப்பால் மிக அதிக பாகுத்தன்மையும், உலோகம் மற்றும் மரப் பரப்பில் வலுவாக ஒட்டும் துருவத் தன்மையால் சிறந்த எல்லை உயவுப் படலமும் உருவாகி, மெதுவாக நகரும் அதிக சுமை அச்சுகளுக்கு ஏற்றதாகிறது.",
        "sources": [
            "Ogunniyi DS (2006), Castor oil: a vital industrial raw material, Bioresource Technology",
            "Mutlu H, Meier MAR (2010), Castor oil as a renewable resource, Eur J Lipid Sci Technol",
            "Hamrock BJ, Fundamentals of Fluid Film Lubrication"
        ],
        "content": "# Ricinoleic Acid: Monounsaturated Hydroxy Fatty Acid Viscosity & Lubrication Mechanics\n\n### 1. Molecular Identity\n- **Ricinoleic acid**: (9Z,12R)-12-hydroxyoctadec-9-enoic acid, C₁₈H₃₄O₃, molar mass 298.5 g/mol.\n- It is a C18 chain with:\n  - a **cis double bond between C9 and C10**, which makes it monounsaturated, like oleic acid;\n  - a **secondary hydroxyl group on C12**, which is rare among natural fatty acids. Castor is the only commercial oil dominated by a hydroxy fatty acid.\n- Castor oil triglycerides are about **85–90% ricinoleate**. The rest is oleic (2–6%), linoleic (1–5%), stearic and palmitic acids, and a trace of dihydroxystearic acid. Roughly 70% of the triglyceride molecules are tri-ricinolein.\n\n### 2. Why Castor Oil Is So Viscous\n- **Hydrogen bonding**: each ricinoleate chain carries an –OH group, so a tri-ricinolein molecule has three. They form a transient intermolecular hydrogen-bond network, which ordinary vegetable oils cannot.\n- **Measured values**:\n  - dynamic viscosity about **600–1000 mPa·s at 25 °C**, against about 50–60 mPa·s for sesame or groundnut oil;\n  - kinematic viscosity about 250–300 cSt at 40 °C and about 18–20 cSt at 100 °C;\n  - viscosity index about 80–90;\n  - density about 0.96 g/cm³;\n  - hydroxyl value 160–168 mg KOH/g;\n  - iodine value 82–90.\n- **Solvent behaviour**: the polar OH groups make castor oil **miscible with ethanol** but poorly soluble in petroleum hydrocarbons, the reverse of most fats.\n\n### 3. Lubrication Mechanics\n- **The Stribeck framework**: the friction coefficient of a lubricated contact depends on the Hersey number ηN/P (viscosity × speed / load).\n  - **Boundary regime** (low ηN/P): the asperities of the two surfaces touch. Friction depends on the adsorbed molecular layers.\n  - **Mixed regime**: the load is partly carried by fluid pressure and partly by asperity contact.\n  - **Hydrodynamic regime** (high ηN/P): a converging oil wedge, described by the Reynolds equation, generates enough pressure to fully separate the surfaces.\n- **Castor oil in the boundary regime**:\n  - The polar C12–OH and the carboxyl ester groups **chemisorb and physisorb** onto metal oxides and onto the hydroxyl-rich cellulose surfaces of wood. They form a densely packed, oriented monolayer that resists being squeezed out.\n  - The result is high film strength and anti-wear behaviour. Castor oil was the lubricant of choice for early aircraft rotary engines (Castrol takes its name from it) because petroleum oils of the day failed under high load.\n- **Castor oil in the hydrodynamic regime**:\n  - Its high viscosity η raises the Sommerfeld number S = (r/c)² · ηN/P. In a slow, heavily loaded wooden journal (the temple chariot axle), this extra viscosity pushes the operating point toward the mixed and hydrodynamic side of the Stribeck curve at a lower speed than a thin oil would need.\n- **Thermal and oxidative stability**: having one double bond per chain, castor oil oxidises more slowly than polyunsaturated oils. Its flash point of about **229 °C or higher** and its low volatility mean it does not readily evaporate or catch fire from frictional heat.\n"
    },
    {
        "slug": "concept-smooth-muscle-ep3-prostanoid-receptor-activation-and-pediatric-laxative-safety",
        "file": "concept-smooth-muscle-ep3-prostanoid-receptor-activation-and-pediatric-laxative-safety.md",
        "category": "concept",
        "name_en": "Smooth Muscle EP3 Prostanoid Receptor Activation by Ricinoleic Acid & Pediatric Laxative Safety",
        "name_ta": "ரிசினோலிக் அமிலத்தால் மென்தசை EP3 புரோஸ்டனாய்டு ஏற்பி தூண்டல் மற்றும் குழந்தை பேதி மருந்து பாதுகாப்பு",
        "era": "Modern Scientific Analysis",
        "year_start": 1950,
        "year_end": 2026,
        "thinai": "marutham",
        "summary_en": "The pharmacology of castor oil as a laxative: pancreatic lipase in the small intestine hydrolyzes castor triglycerides to release free ricinoleic acid, which (as shown by Tunaru et al., PNAS 2012) binds and activates the prostaglandin E2 receptor subtype EP3 on intestinal and uterine smooth muscle cells, causing contraction, increased motility and fluid secretion. The same mechanism explains labour-induction folklore, and it underpins the modern safety stance that castor oil should not be given to infants or young children without medical supervision.",
        "summary_ta": "சிறுகுடலில் கணைய லைப்பேஸ் நொதி ஆமணக்கு டிரைகிளிசரைடுகளைச் சிதைத்து விடுவிக்கும் ரிசினோலிக் அமிலம், குடல் மற்றும் கருப்பை மென்தசைச் செல்களில் உள்ள புரோஸ்டாகிளாண்டின் E2 ஏற்பியின் EP3 துணை வகையைத் தூண்டி தசைச் சுருக்கம், குடல் இயக்கம் மற்றும் நீர்ச் சுரப்பை அதிகரிக்கிறது; இதனாலேயே குழந்தைகளுக்கு மருத்துவர் மேற்பார்வையின்றிக் கொடுக்கக் கூடாது என்ற நவீன பாதுகாப்பு நிலைப்பாடு.",
        "sources": [
            "Tunaru S et al. (2012), Castor oil induces laxation and uterus contraction via ricinoleic acid activating prostaglandin EP3 receptors, PNAS 109(23)",
            "WHO / national pediatric formularies on stimulant laxatives",
            "Siddha Gunapadam on Amanakku Ennai"
        ],
        "content": "# Smooth Muscle EP3 Prostanoid Receptor Activation by Ricinoleic Acid & Pediatric Laxative Safety\n\n### 1. From Triglyceride to Active Molecule\n- Castor oil as swallowed is largely **inactive**. In the duodenum, **pancreatic lipase**, helped by bile-salt emulsification, hydrolyses the ester bonds of tri-ricinolein and releases **free ricinoleic acid** together with mono- and diglycerides.\n- This explains the lag of 2–6 hours before the purgative effect, the time needed for lipolysis and transit.\n\n### 2. The EP3 Receptor Mechanism\n- For decades the action was explained vaguely as \"irritation\" of the gut lining or a detergent-like effect. In 2012 **Tunaru, Althoff, Nüsing, Diener and Offermanns (PNAS)** identified the true molecular target:\n  - Ricinoleic acid **binds and activates the EP3 receptor**, a G-protein-coupled receptor (GPCR) normally activated by **prostaglandin E₂ (PGE₂)**.\n  - In mice lacking EP3 receptors (EP3⁻/⁻), castor oil produced **neither diarrhoea nor uterine contraction**. Knockouts of the other EP subtypes did not abolish the effect.\n  - Specifically, **EP3 on smooth muscle cells**, not on epithelial cells, was required. Mice with smooth-muscle-specific EP3 deletion were resistant.\n- **Signalling**: EP3 couples mainly to **Gαi**, which lowers cyclic AMP, and also to Gα12/13–Rho pathways. Smooth muscle tone and contractility rise, together with propulsive intestinal motility. Secondary effects on mucosal fluid and electrolyte secretion add to the laxative action.\n- **Uterine action**: myometrial smooth muscle expresses EP3 as well. This is the molecular basis for the old folk use of castor oil to \"bring on\" labour. Clinical evidence for that use is mixed, and it carries real risks, so it is done only under obstetric supervision.\n\n### 3. Pediatric Laxative Safety\n- Traditional households across the Tamil country sometimes gave small purgative doses of *vilakkennai* to children. Modern pharmacology gives several clear reasons for caution:\n  - **Dose sensitivity**: children have a small body mass and little fluid reserve, so a strong stimulant purge can quickly cause **dehydration and electrolyte imbalance** (hypokalaemia, hyponatraemia).\n  - **Aspiration risk**: a struggling infant can inhale an oily, viscous liquid. Inhaled oil causes **lipoid (exogenous lipid) pneumonia**.\n  - **Cramping and masking**: severe abdominal colic can hide the signs of a surgical emergency such as appendicitis or intestinal obstruction, where any laxative is dangerous.\n- **Current guidance**: castor oil is generally **not recommended for infants**. For children it should be used only on a qualified clinician's advice and dose. Gentler, osmotic laxatives are preferred for childhood constipation.\n- **External use** of castor oil, such as warm packs, is a separate matter, with low systemic absorption and a different risk profile.\n"
    },
    {
        "slug": "concept-vilakkennai-low-smoke-high-flashpoint-wick-luminescence-and-eye-cooling-physiology",
        "file": "concept-vilakkennai-low-smoke-high-flashpoint-wick-luminescence-and-eye-cooling-physiology.md",
        "category": "concept",
        "name_en": "Vilakkennai Low-Smoke High-Flashpoint Wick Luminescence & Eye-Cooling Physiology",
        "name_ta": "விளக்கெண்ணெய்: குறைந்த புகை, உயர் தீப்பற்றுநிலை திரி ஒளிர்வு மற்றும் கண் குளிர்ச்சி உடலியல்",
        "era": "Sangam Era to Modern Era",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "mullai",
        "summary_en": "Why castor oil was the prized Tamil lamp oil: its high flash point (about 229 C or more) and low volatility make it safe and slow-burning in open terracotta agal lamps; capillary wicking through cotton wicks (thiri) is slow but steady because of its high viscosity, and its oxygen-rich hydroxy chains burn with a calm, low-soot flame; and in Siddha and household practice a drop of cold-drawn vilakkennai on the eyelids or soles was used for its demulcent, cooling (kulirchi) effect on the eyes and body heat.",
        "summary_ta": "விளக்கெண்ணெய் சிறந்த விளக்கு எண்ணெயாகக் கருதப்பட்டதன் காரணம்: அதிக தீப்பற்றுநிலை மற்றும் குறைந்த ஆவியாதல் காரணமாகத் திறந்த அகல் விளக்கில் பாதுகாப்பாக மெதுவாக எரிதல்; பருத்தித் திரியில் மெதுவான ஆனால் சீரான நுண்துளை ஏற்றம்; ஆக்சிஜன் நிறைந்த சங்கிலிகளால் குறைந்த கரிப்புகை கொண்ட அமைதியான சுடர்; மேலும் கண் இமைகள் மற்றும் உள்ளங்கால்களில் இடப்படும் குளிர்ச்சி தரும் வழக்கம்.",
        "sources": [
            "Siddha Gunapadam: Amanakku Ennai (cooling, kulirchi property)",
            "Combustion Studies of Vegetable Oil Lamps",
            "Castor Oil Physical Property Data (flash point, viscosity)"
        ],
        "content": "# Vilakkennai Low-Smoke High-Flashpoint Wick Luminescence & Eye-Cooling Physiology\n\n### 1. The Name Itself\n- **விளக்கெண்ணெய் (Vilakku + Ennai)** means \"lamp oil\". Tamil names this oil for what it is used for, which shows how central castor oil was to domestic and temple lighting, alongside ghee (*நெய்*) and gingelly oil (*நல்லெண்ணெய்*).\n\n### 2. Flash Point and Fire Safety\n- Castor oil's **flash point is about 229 °C or higher** (closed cup values are often quoted near 230–260 °C), and its fire point is higher still. Its vapour pressure at room temperature is negligible.\n- In an open terracotta **agal** lamp (*அகல் விளக்கு*), the bulk oil therefore never gets hot enough to give off flammable vapour. Only the small amount of oil drawn to the wick tip is vaporised and burned. A tipped-over lamp does not flash into a pool fire as easily as a lamp filled with a volatile fuel.\n\n### 3. Wick Capillarity (*திரி ஏற்றம்*)\n- Oil climbs the cotton wick (*பஞ்சுத் திரி*) by **capillary action**. By the Lucas–Washburn relation, the penetration rate is proportional to surface tension × pore radius ÷ viscosity. Castor oil's very high viscosity makes this wicking **slow**, but the flame never starves as long as the wick is kept short and the oil well is kept full.\n- Practical consequences:\n  - Lamp keepers used **thicker, loosely twisted wicks** for castor oil than for thinner oils, to widen the capillary channels.\n  - The **slow wicking means slow consumption**, so one filling lasts through the night. This mattered for *nondha vilakku* (perpetual lamps).\n\n### 4. Low-Smoke Combustion and Luminescence\n- The flame's light comes mainly from **incandescent soot particles** glowing at about 1,200–1,400 °C. Too little soot gives a dim flame. Too much escapes as black smoke.\n- Ricinoleate chains carry **extra oxygen** in their hydroxyl groups (the oil is about 15% oxygen by mass, against about 11% for typical vegetable oils). That built-in oxygen improves combustion inside the flame and reduces the soot that escapes as smoke, while keeping enough glowing particles for a warm yellow light.\n- Because wicking is controlled by viscosity, the flame stays small and steady, with little flicker. Lamp keepers described it as a calm, \"golden\" flame suited to the dim sanctum (*கருவறை*).\n\n### 5. Eye-Cooling and Body-Cooling Physiology (*குளிர்ச்சி*)\n- **Siddha classification**: Siddha *gunapadam* describes *amanakku ennai* as having a **cooling (குளிர்ச்சி)** quality. It was used to counter excess body heat (*உடல் சூடு*).\n- **Traditional eye practice**: a drop of **cold-drawn** castor oil was rubbed along the eyelid margins or onto the soles of the feet at bedtime. People reported a soothing, cooling feeling in tired, irritated eyes.\n- **Physiological basis**:\n  - Castor oil is a **demulcent and emollient**. A thin film over the lid margin and tear film slows evaporation from the tear layer, much as modern castor-oil-containing lubricant eye drops are designed to support the tear film's lipid layer.\n  - Ricinoleic acid has also been studied for **anti-inflammatory and analgesic** effects when applied to the skin.\n  - The feeling of \"coolness\" is consistent with less evaporative dryness and irritation.\n- **Caution**: only sterile, pharmaceutical-grade preparations should ever go *into* the eye. Household oil can carry microbes and particles.\n"
    },
    {
        "slug": "institution-dryland-rainfed-amanakku-grower-guilds-and-temple-vilakkennai-endowment-trusts",
        "file": "institution-dryland-rainfed-amanakku-grower-guilds-and-temple-vilakkennai-endowment-trusts.md",
        "category": "institution",
        "name_en": "Dryland Rainfed Amanakku Grower Communities, Vaniyar Oil-Pressers & Temple Vilakkennai Endowment Trusts",
        "name_ta": "மானாவாரி ஆமணக்கு விவசாயக் குழுக்கள், வாணியர் எண்ணெய்ச் செக்காளர்கள் மற்றும் கோவில் விளக்கெண்ணெய் அறக்கட்டளைகள்",
        "era": "Medieval Era to Modern Era",
        "year_start": 800,
        "year_end": 2026,
        "thinai": "mullai",
        "summary_en": "The social institutions that sustained the castor oil economy: rainfed (manavari) dryland farmers growing amanakku as a border and intercrop in red-soil millet fields; Vaniyar / Chekkar oil-presser communities who ran the chekku mills and supplied lamp oil; and medieval temple endowment trusts (nibandha) whose inscriptions specify land, cattle, gold or interest-bearing deposits granted so that a fixed measure of oil would feed a perpetual lamp (nondha vilakku) daily for as long as the sun and moon endure.",
        "summary_ta": "ஆமணக்கு எண்ணெய்ப் பொருளாதாரத்தைத் தாங்கிய சமூக அமைப்புகள்: செம்மண் சிறுதானிய வயல்களில் வரப்பு மற்றும் ஊடுபயிராக ஆமணக்கு விதைக்கும் மானாவாரி விவசாயிகள்; செக்கு இயக்கி விளக்கெண்ணெய் வழங்கிய வாணியர், செக்கார் சமூகங்கள்; சந்திராதித்தவரை நந்தா விளக்கு எரிய நிலம், பசுக்கள், பொன் அல்லது வட்டித் தொகையை அளித்த இடைக்காலக் கோவில் அறக்கட்டளைக் கல்வெட்டுகள்.",
        "sources": [
            "South Indian Inscriptions (Archaeological Survey of India) — Chola lamp endowments",
            "Noboru Karashima, South Indian History and Society: Studies from Inscriptions",
            "Ethnographic Studies of Tamil Rainfed Agriculture"
        ],
        "content": "# Dryland Rainfed Amanakku Grower Communities, Vaniyar Oil-Pressers & Temple Vilakkennai Endowment Trusts\n\n### 1. Rainfed Amanakku Growers (*மானாவாரி விவசாயிகள்*)\n- Castor is a classic **manavari** (மானாவாரி, rainfed) crop. Its deep taproot (often more than 2 m) and drought hardiness suit the shallow red soils (*செம்மண்*) of the Dharmapuri, Salem and Krishnagiri uplands, which depend on the northeast and southwest monsoons.\n- Traditional cropping:\n  - **Border rows (*வரப்புப் பயிர்*)**: tall castor bushes planted along field edges acted as windbreaks and live fences for millet fields (*கேழ்வரகு* finger millet, *சாமை*, *கம்பு*). Their ricin-laden leaves deterred grazing cattle.\n  - **Intercropping**: castor was sown in wide-spaced rows between groundnut or pulse rows. Its staggered maturity spread the harvest across months.\n  - **Trap crop**: castor leaves attract the tobacco caterpillar (*Spodoptera litura*), which pulls the pest off neighbouring crops, a practice still promoted in integrated pest management.\n- Village farmer bodies handled seed saving, shared threshing yards and the rotation of oil-pressing turns.\n\n### 2. Vaniyar / Chekkar Oil-Pressers (*வாணியர்*)\n- The **Vaniyar** (வாணியர்) community, the \"oil-mongers\" of inscriptions and literature, along with related Chekkar groups, ran the bullock-driven **chekku** mills of village and temple town.\n- Medieval inscriptions record oil-mill taxes (*செக்கிறை*, *chekkirai*) and grants in which oil-pressers undertook to supply a fixed daily measure of oil to a temple, sometimes in return for tax remission or a share of temple land.\n\n### 3. Temple Lamp Endowment Trusts (*நந்தா விளக்கு அறக்கட்டளை*)\n- The richest records of lamp oil come from **Pallava, Chola and Pandya temple inscriptions** (roughly 8th–13th centuries). Thousands of them record gifts made \"so that a perpetual lamp shall burn **as long as the sun and moon endure** (*சந்திராதித்தவரை*)\".\n- Endowment forms:\n  - **Livestock**: herds of sheep or cows (commonly 90 or 96 sheep, or 32 cows, per perpetual lamp) entrusted to shepherds (*மன்றாடிகள்*), who had to deliver a fixed daily measure of **ghee**. These are the famous *sava-moova-perada* (\"undying, unaging\") sheep.\n  - **Land**: plots whose produce paid for lamp oil.\n  - **Gold or money** deposited with the village assembly (*சபை* / *ஊர்*), with the interest earmarked for the lamp.\n- **Oil vs. ghee**: many Chola lamp grants name ghee as the fuel for the main sanctum lamp. Oil, including vegetable lamp oils such as *vilakkennai* and gingelly oil, fuelled lesser lamps, street and hall lighting, festival torches and the chariot procession. Some inscriptions specify oil in place of ghee where livestock endowments were impractical.\n- The trusts were **audited institutions**: temple accountants (*கணக்கர்*) and the village assembly answered for the daily measure, and the inscriptions themselves served as public legal contracts carved in stone.\n"
    },
    {
        "slug": "place-dharmapuri-ancient-adhigaman-amanakku-castor-and-vilakkennai-haven",
        "file": "place-dharmapuri-ancient-adhigaman-amanakku-castor-and-vilakkennai-haven.md",
        "category": "place",
        "name_en": "Dharmapuri (Ancient Tagadur): Adhigaman Country & Red-Soil Amanakku Castor Haven",
        "name_ta": "தருமபுரி (பண்டைய தகடூர்): அதியமான் நாடு மற்றும் செம்மண் ஆமணக்கு விளக்கெண்ணெய் மையம்",
        "era": "Sangam Era to Modern Era",
        "year_start": -200,
        "year_end": 2026,
        "thinai": "kurinji",
        "summary_en": "Dharmapuri, the ancient Tagadur, capital of the Sangam-era Adhiyaman (Adhigaman) chieftains celebrated by the poet Avvaiyar in the Purananuru, sits on the semi-arid red-soil Deccan plateau margin of northwestern Tamil Nadu. Its rainfed upland fields, with shallow red loams, low rainfall (about 800-900 mm) and hot dry summers, made it, together with neighbouring Salem and Krishnagiri, one of Tamil Nadu's leading castor (amanakku) growing tracts, a heartland of rainfed oilseed and vilakkennai production.",
        "summary_ta": "ஔவையாரால் புறநானூற்றில் போற்றப்பட்ட சங்ககால அதியமான் மன்னர்களின் தலைநகரான பண்டைய தகடூர், இன்றைய தருமபுரி; வடமேற்குத் தமிழ்நாட்டின் அரைவறண்ட செம்மண் மேட்டுநிலத்தில் அமைந்த இப்பகுதி, குறைந்த மழை மற்றும் ஆழமற்ற செம்மண் வயல்களால் சேலம், கிருஷ்ணகிரியுடன் சேர்ந்து தமிழ்நாட்டின் முக்கிய மானாவாரி ஆமணக்கு மற்றும் விளக்கெண்ணெய் உற்பத்தி மையமாக விளங்குகிறது.",
        "sources": [
            "Purananuru (Avvaiyar's poems on Adhiyaman Neduman Anji, e.g. Puram 87-104)",
            "Tagadur Yaathirai (lost Sangam-era work, cited in commentaries)",
            "Tamil Nadu Agricultural Statistics on Castor Area by District"
        ],
        "content": "# Dharmapuri (Ancient Tagadur): Adhigaman Country & Red-Soil Amanakku Castor Haven\n\n### 1. Tagadur, Seat of the Adhiyaman Chiefs\n- Modern **Dharmapuri** is identified with ancient **Tagadur (தகடூர்)**, capital of the **Adhiyaman (அதியமான்)** chieftains, one of the celebrated *velir* lineages of the Sangam age.\n- **Adhiyaman Neduman Anji** is immortalised in the **Purananuru** by the poetess **Avvaiyar**, his friend and envoy. A famous tradition says he gave her a rare **nelli (Indian gooseberry)** fruit that would grant long life, choosing her life over his own.\n- The siege of Tagadur by the Chera king Perum Cheral Irumporai was the subject of a lost work, the *Tagadur Yaathirai*. Fragments survive only as quotations in later commentaries.\n\n### 2. A Red-Soil Rainfed Landscape\n- **Geology and soils**: Dharmapuri lies on the edge of the Deccan granite–gneiss plateau, roughly 450–700 m above sea level. Its soils are mostly **shallow, well-drained red loams and sandy loams (*செம்மண்*)**.\n- **Climate**: semi-arid, with roughly 800–900 mm of erratic annual rainfall split between the southwest and northeast monsoons, and long, hot, dry spells.\n- **Fit for castor**: those are exactly the conditions where **Ricinus communis** does well. It tolerates drought, needs no irrigation, roots deeply into fractured red subsoil, and stands up to the poor-fertility soils where water-hungry crops fail.\n\n### 3. Amanakku Country\n- In modern agricultural statistics, the northwestern districts of **Dharmapuri, Krishnagiri and Salem** account for much of Tamil Nadu's castor acreage. Castor is grown there as a rainfed sole crop, a border crop and an intercrop with finger millet (*ராகி / கேழ்வரகு*), groundnut and pulses.\n- **The village oil economy**: traditional villages in the area kept their own threshing yards, household rendering pots and *chekku* mills. They supplied *vilakkennai* for village lamps, bullock-cart axles, local temple festivals and household medicine. Surplus castor seed moved to markets on the plains and the coast.\n- **Temple linkage**: the temples of the Dharmapuri region, from the Adhiyaman-era settlements to the later Hoysala and Vijayanagara-period shrines, kept up chariot festivals and lamp services that drew on local oil supply.\n\n### 4. A Note on Evidence\n- The Adhiyaman–Tagadur identification and the poetic record are well established. The *specific* claim that Sangam-age Tagadur was a castor centre is an **inference** from its landscape and its modern cropping pattern, not a statement in the Sangam texts themselves.\n"
    },
    {
        "slug": "text-sangam-and-medieval-inscriptions-on-amanakku-fields-and-vilakkennai-lamp-supplies",
        "file": "text-sangam-and-medieval-inscriptions-on-amanakku-fields-and-vilakkennai-lamp-supplies.md",
        "category": "text",
        "name_en": "Sangam Literature & Medieval Inscriptions on Amanakku Fields and Lamp-Oil Supplies",
        "name_ta": "சங்க இலக்கியம் மற்றும் இடைக்காலக் கல்வெட்டுகளில் ஆமணக்கு வயல்கள் மற்றும் விளக்கு எண்ணெய் வழங்கல்",
        "era": "Sangam Era to Medieval Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "mullai",
        "summary_en": "A guide to the textual record of castor and lamp oil in the Tamil country: Sangam poetry's lamp imagery (agal vilakku, oil-fed lamps in homes, streets and harbours) and agrarian landscapes; the Tamil lexicographic tradition (Nigandu dictionaries) recording amanakku and its synonyms; Siddha medical verse on amanakku ennai; and the epigraphic corpus of Pallava, Chola and Pandya temple inscriptions recording oil-mill taxes (chekkirai), oil-presser obligations, and endowments for perpetual and twilight lamps (nondha vilakku, sandhi vilakku), with notes on which claims are documented and which are inferred.",
        "summary_ta": "தமிழ்நாட்டில் ஆமணக்கு மற்றும் விளக்கெண்ணெய் பற்றிய எழுத்துப் பதிவுகளின் வழிகாட்டி: சங்கப் பாடல்களில் அகல் விளக்கு மற்றும் எண்ணெய் விளக்கு உவமைகள்; நிகண்டுகளில் ஆமணக்கு மற்றும் அதன் பெயர்கள்; சித்த மருத்துவப் பாடல்களில் ஆமணக்கு எண்ணெய்; பல்லவ, சோழ, பாண்டியக் கோவில் கல்வெட்டுகளில் செக்கிறை, வாணியர் கடமைகள், நந்தா விளக்கு மற்றும் சந்தி விளக்கு அறக்கட்டளைகள்.",
        "sources": [
            "South Indian Inscriptions (ASI), Vols. II, III, XIII et seq.",
            "Pingala Nigandu and Divakara Nigandu (Tamil lexicons)",
            "Purananuru and Ahananuru (lamp imagery)",
            "Siddha Gunapadam texts"
        ],
        "content": "# Sangam Literature & Medieval Inscriptions on Amanakku Fields and Lamp-Oil Supplies\n\n### 1. Sangam Poetry: Lamps and Oil\n- Sangam anthologies such as the *Purananuru*, *Ahananuru* and *Pattuppattu* are full of **lamp imagery**:\n  - lamps lit at dusk in homes;\n  - lamps in temple shrines and festival streets, as in the *Madurai Kanchi*'s descriptions of the night city;\n  - harbour beacons guiding ships, as in the *Perumpanarruppadai*.\n- These texts usually name **ghee (நெய்)** or simply **oil (எண்ணெய்)** as the lamp fuel. They do not explicitly name castor as the oil. Any identification of a particular Sangam lamp oil as *vilakkennai* is therefore an **interpretation** and should be marked as such.\n- Even so, the agrarian landscapes of the *mullai* (pastoral forest-edge) and dryland *palai* margins described in the poems match the rainfed, red-soil country where castor grows.\n\n### 2. Lexical Tradition (*நிகண்டுகள்*)\n- The medieval Tamil thesauri (*Divakara Nigandu*, *Pingala Nigandu*, *Chudamani Nigandu*) and, much later, the **Tamil Lexicon** of the University of Madras record **ஆமணக்கு (amanakku)** with synonyms and plant varieties. Examples are **சிற்றாமணக்கு** (*chittramanakku*, small-seeded castor, prized for medicinal oil) and **பேராமணக்கு** (*peramanakku*, large-seeded castor).\n- The compound **விளக்கெண்ணெய் (vilakkennai)**, \"lamp oil\", fixes castor oil's main cultural identity in the language itself.\n\n### 3. Siddha Medical Verse\n- Siddha *gunapadam* (materia medica) verses, attributed to the Siddhar tradition, list the qualities of **ஆமணக்கு எண்ணெய்**: cooling (*குளிர்ச்சி*), purgative (*பேதி*), useful for joint pain and for counteracting body heat. They also describe the leaf as a warm poultice for swellings.\n\n### 4. The Epigraphic Corpus\n- The **South Indian Inscriptions** volumes and annual epigraphy reports hold thousands of Pallava, Chola and Pandya temple inscriptions concerning lamps:\n  - **Perpetual lamp (நந்தா விளக்கு, *nondha vilakku*)**: endowed to burn day and night \"as long as the sun and moon endure (*சந்திராதித்தவரை*)\".\n  - **Twilight lamp (சந்தி விளக்கு, *sandhi vilakku*)**: lit at the evening and morning junctions of the day.\n  - **Oil-mill tax (செக்கிறை, *chekkirai*)**: levied on presses, sometimes remitted in return for a temple oil supply.\n  - **Oil-presser obligations**: grants in which a group of *vaniyar* (oil-mongers) agree to deliver a fixed daily measure (*nazhi*, *uzhakku*) of oil to the temple.\n- **Fuel specified**: in most lamp endowments the fuel is **ghee**, supplied by herds of sheep or cows held by shepherds. Some records name oil (*ennai*), and the type of oil is often not stated. Records that explicitly name castor oil should be cited individually. The general picture is that ghee fed the most sacred lamps, while vegetable oils, castor among them, fed secondary and utilitarian lighting.\n\n### 5. Reading the Record Responsibly\n- **Documented**: lamp endowments, oil-presser communities, oil-mill taxes, the oil measures, and castor's lexical and medical identity.\n- **Inferred**: the specific scale of castor (as distinct from gingelly or *iluppai*) oil in temple lamp supply at any given period.\n"
    }
]

EDGES = [
    [
        "technology-amanakku-seed-dehulling-earthen-pot-roasting-and-hot-water-float-rendering",
        "produces",
        "artifact-cold-drawn-and-rendered-vilakkennai-terracotta-oil-measures-and-palmyra-funnels",
        "material_culture",
        "Sangam Era to Modern Era",
        "Roasting, pounding and hot-water float rendering yield the amber rendered grade of vilakkennai stored in terracotta pots and measured in nazhi and uzhakku",
        "Ethnographic Observation"
    ],
    [
        "technology-amanakku-seed-dehulling-earthen-pot-roasting-and-hot-water-float-rendering",
        "produces",
        "artifact-castor-seed-pinnakku-fertilizer-and-massive-temple-axle-greasing-paddles",
        "material_culture",
        "Sangam Era to Modern Era",
        "Spent castor seed meal from oil extraction becomes the ricin-bearing pinnakku manure used in paddy and betel-vine fields",
        "Agronomic Practice"
    ],
    [
        "technology-temple-chariot-wooden-axle-vilakkennai-lubrication-and-pediatric-purgative-dosing",
        "utilizes",
        "artifact-castor-seed-pinnakku-fertilizer-and-massive-temple-axle-greasing-paddles",
        "material_culture",
        "Medieval Era to Modern Era",
        "Ther carpenters pack castor-tallow-soot grease into chariot hub bores with long hardwood greasing paddles",
        "Temple Maintenance Practice"
    ],
    [
        "technology-temple-chariot-wooden-axle-vilakkennai-lubrication-and-pediatric-purgative-dosing",
        "derives_from",
        "concept-ricinoleic-acid-monounsaturated-hydroxy-fatty-acid-viscosity-and-lubrication-mechanics",
        "material_culture",
        "Medieval Era to Modern Era",
        "Chariot axle lubrication relies on ricinoleic acid's hydroxyl-driven viscosity and polar boundary-film adsorption under slow, heavy loads",
        "Tribological Analysis"
    ],
    [
        "technology-temple-chariot-wooden-axle-vilakkennai-lubrication-and-pediatric-purgative-dosing",
        "explained_by",
        "concept-smooth-muscle-ep3-prostanoid-receptor-activation-and-pediatric-laxative-safety",
        "material_culture",
        "Medieval Era to Modern Era",
        "The traditional castor purge works through lipase-released ricinoleic acid activating smooth-muscle EP3 receptors, which also defines pediatric dosing caution",
        "Pharmacological Research (Tunaru et al. 2012)"
    ],
    [
        "artifact-cold-drawn-and-rendered-vilakkennai-terracotta-oil-measures-and-palmyra-funnels",
        "embodies",
        "concept-vilakkennai-low-smoke-high-flashpoint-wick-luminescence-and-eye-cooling-physiology",
        "material_culture",
        "Sangam Era to Modern Era",
        "Vilakkennai poured through palmyra funnels into agal lamps burns with a steady low-smoke flame owing to its high flash point and slow wick capillarity",
        "Combustion Analysis"
    ],
    [
        "place-dharmapuri-ancient-adhigaman-amanakku-castor-and-vilakkennai-haven",
        "cultivates",
        "technology-amanakku-seed-dehulling-earthen-pot-roasting-and-hot-water-float-rendering",
        "material_culture",
        "Sangam Era to Modern Era",
        "The rainfed red-soil uplands of Dharmapuri supply abundant amanakku seed for household roasting and float rendering",
        "Geographical and Agricultural Survey"
    ],
    [
        "institution-dryland-rainfed-amanakku-grower-guilds-and-temple-vilakkennai-endowment-trusts",
        "operates_in",
        "place-dharmapuri-ancient-adhigaman-amanakku-castor-and-vilakkennai-haven",
        "material_culture",
        "Medieval Era to Modern Era",
        "Manavari castor growers and Vaniyar oil-pressers form the rural oil economy of the Dharmapuri-Salem-Krishnagiri tract",
        "Historical Geography"
    ],
    [
        "institution-dryland-rainfed-amanakku-grower-guilds-and-temple-vilakkennai-endowment-trusts",
        "administers",
        "artifact-cold-drawn-and-rendered-vilakkennai-terracotta-oil-measures-and-palmyra-funnels",
        "material_culture",
        "Medieval Era to Modern Era",
        "Temple endowment trusts and oil-presser obligations were accounted in standardized nazhi and uzhakku oil measures",
        "Epigraphical Records"
    ],
    [
        "text-sangam-and-medieval-inscriptions-on-amanakku-fields-and-vilakkennai-lamp-supplies",
        "documents",
        "institution-dryland-rainfed-amanakku-grower-guilds-and-temple-vilakkennai-endowment-trusts",
        "material_culture",
        "Sangam Era to Medieval Era",
        "Pallava, Chola and Pandya inscriptions record nondha vilakku endowments, chekkirai oil-mill taxes and vaniyar oil-supply obligations",
        "Epigraphical Analysis"
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
