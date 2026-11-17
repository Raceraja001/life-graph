#!/usr/bin/env python3
"""
Harvester: Batch 54 - Ancient Tamil Soapstone Cookware, Talc-Schist Quarrying, Lathe Turnery, Oil-Rice Starch Curing & Thermal Heat Retention
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
        "slug": "technology-steatite-talc-schist-quarrying-lathe-turnery-and-chisel-hollowing",
        "category": "technology",
        "file": "technology-steatite-talc-schist-quarrying-lathe-turnery-and-chisel-hollowing.md",
        "name_en": "Steatite Talc-Schist Quarrying, Lathe Turnery & Chisel Hollowing",
        "name_ta": "மாக்கல் (ஸ்டீயடைட்) சுரங்க வெட்டெடுப்பு, கடைசல் குதிரை திருப்புதல் மற்றும் உளி குடைவு நுட்பம்",
        "era": "Megalithic to Contemporary Era",
        "year_start": -500,
        "year_end": 2025,
        "thinai": "kurinji",
        "summary_en": "Ancient and continuous Tamil craftsmanship of quarrying metamorphic talc-schist (steatite / maakkal) from Shevaroy and Omalur deposits, block dressing along foliation planes, and turning on low horizontal wooden spindle lathes (kudhirai) using bow cords and hand-forged curved steel gouges (valai-uli) for concentric core hollowing.",
        "summary_ta": "சேர்வராயன் மலை மற்றும் ஓமலூர் பாறைப் படுகைகளில் இருந்து மென்மையான மாக்கல்லை (Talc-schist) வெட்டி எடுத்து, கடைசல் குதிரையில் கயிற்றால் சுழற்றி, கைவினை எஃகு வளைவுளிகளால் குடைந்து கல்சட்டிகளாகவும் சமையற்பாத்திரங்களாகவும் உருவாக்கும் தொன்மைத் தமிழ்த் தொழில்நுட்பம்.",
        "sources": [
            "Archaeological Survey of Tamil Nadu Omalur Excavation Reports",
            "Artisanal Guild Records of Salem Kammalar Silpis",
            "Tamil Nadu Handicrafts Development Corporation Kalchatti Monograph",
            "Indian Journal of History of Science - Traditional Stone Lathes"
        ],
        "content": "# Steatite Talc-Schist Quarrying, Lathe Turnery & Chisel Hollowing\n\nSteatite (*maakkal* or *ven-kal*, mineralogically talc-schist) is an ultramafic metamorphic rock composed predominantly of talc ($\\text{Mg}_3\\text{Si}_4\\text{O}_{10}(\\text{OH})_2$) intergrown with chlorite, tremolite, and magnesite. Yielding a Mohs hardness of only 1.0 to 2.5, it exhibits an extraordinary balance of soft workability before curing and high heat capacity after seasoning, forming the material foundation of the legendary Tamil *kalchatti* (கல்சட்டி) cookware.\n\n### Geological Quarrying & Cleavage Splitting\nIn the ancient Kongu geological belt—spanning the foothills of the Shevaroy (Servarayan) hills, Omalur, Mecheri, and parts of Namakkal and Tiruvannamalai—talc-schist occurs as lenses within Archaean greenstone belts. Traditional stone-workers (*kalthachan* or *silpis*) employ non-explosive extraction:\n1. **Foliation Tracing**: Artisans identify the natural metamorphic bedding foliation (*pal-varai*) to avoid transverse fracturing.\n2. **Wedge Cleaving**: Hand-forged steel wedges (*aani*) are driven into natural fissures with sledgehammers (*kanthali*), cleaving clean rectangular or cylindrical quarry blocks (*kal-kattai*) weighing 10 to 50 kilograms.\n3. **Rough Dressing**: Using pointed pickaxes (*kothu-uli*), the quarry block is trimmed into an approximate polygonal cylinder before transport to the village workshop.\n\n### The Low Horizontal Wooden Spindle Lathe (*Kudhirai Mandrel*)\nUnlike vertical potter wheels that utilize centrifugal force on plastic clay, soapstone turning requires high-torque, controlled-speed rotational cutting of solid rock:\n- **The Kudhirai Frame**: A heavy timber bench crafted from seasoned *Vengai* (*Pterocarpus marsupium*) or Neem wood forms a rigid bed resting directly on the earth to absorb mechanical vibrations.\n- **Spindle Mandrel & Center Pivots**: The stone blank is mounted on an iron spindle chuck centered between two greased iron gudgeon bearings (*kudhirai-pidi*). The blank is affixed using a thermoplastic matrix of natural pine resin, tamarind seed gum, and brick powder.\n- **Bow-Drive & Cord Reciprocation**: Rotation is driven by a flexible wooden bow (*villu*) strung with a double-twisted oxhide or jute cord wrapped around the spindle pulley. An apprentice draws the bow in steady reciprocal strokes, generating rotational speeds between 120 and 250 RPM.\n\n### Concentric Chisel Hollowing & Tool Dynamics\nAs the stone rotates on the lathe, the master turner applies specialized hand-forged, high-carbon tempered iron chisels (*urukku-uli*):\n- **Valai-Uli (Curved Gouge)**: Features a deep crescent profile to bore into the core of the rotating block, executing internal hollowing without creating micro-fractures.\n- **Thuruval-Uli (Scraping Chisel)**: A broad flat-edged tool calibrated to smooth the interior cavity to uniform wall thickness (typically 12 to 20 mm).\n- **Kothu-Uli (Exterior Profiling Chisel)**: Shapes the exterior contour, stepping the rim for lid seating and incising concentric decorative ridges (*kal-vari*) that enhance radiant heat dissipation.\n- **Core Recovery**: On large vessels, skilled turners execute nested hollowing (*kodu-eduthal*), extracting an interior solid cone of steatite intact to be turned into a smaller cup or *rasam-chatti*, maximizing material yield with near-zero waste.\n\n### Abrasive Smoothing & Botanical Polishing\nOnce removed from the lathe, the raw grey-white vessel undergoes progressive finishing:\n- **Leaf Scouring**: The rough surfaces are buffed using the rigid, silica-rich dorsal trichomes of Sandpaper Fig leaves (*ottan-ilai*, *Ficus exasperata* / *oda-maram*), which act as a natural 400-grit emery paper.\n- **Oil Slurry Lapping**: Fine quartz powder suspended in castor oil is rubbed with coconut husk fibers, sealing macroscopic surface voids and preparing the vessel for the multi-week ritual of kitchen curing (*pazhakkuthal*)."
    },
    {
        "slug": "technology-kalchatti-mustard-oil-curing-rice-starch-simmering-and-thermal-seasoning",
        "category": "technology",
        "file": "technology-kalchatti-mustard-oil-curing-rice-starch-simmering-and-thermal-seasoning.md",
        "name_en": "Kalchatti Mustard-Sesame Oil Curing, Rice Starch Simmering & Thermal Seasoning",
        "name_ta": "கல்சட்டி கடுகு-நல்லெண்ணெய் பதனிடுதல், கஞ்சித் தண்ணீர் ஊறவைப்பு மற்றும் வெப்பப் பழக்குதல்",
        "era": "Sangam to Contemporary Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "marutham",
        "summary_en": "The rigorous traditional curing protocol (pazhakkuthal) for raw carved steatite kalchatti cookware: consecutive applications of warm castor or mustard/sesame oil blended with turmeric, prolonged immersion in hot fermented rice starch gruel (kanji thanneer) over 10-14 days to seal phyllosilicate micro-porosities, followed by progressive low-temperature thermal ramping to form an indelible, hydrophobic, jet-black carbonized non-stick patina.",
        "summary_ta": "புதிதாகச் செதுக்கப்பட்ட கல்சட்டியின் கனிம நுண்துளைகளை அடைத்து, வெப்ப அதிர்ச்சியைத் தாங்கும் வகையில் சூடான விளக்கெண்ணெய், நல்லெண்ணெய், மஞ்சள் பூசி, தொடர்ந்து 10 முதல் 14 நாட்கள் கொதிக்கும் கஞ்சித் தண்ணீரில் ஊறவைத்து, மெல்லிய தணலில் பழக்கி உருவாக்கப்படும் உறுதியான கரிய பளபளப்பு நுட்பம்.",
        "sources": [
            "Traditional Tamil Culinary Ethno-technological Surveys",
            "Kongu Cookware Seasoning Manuals",
            "Journal of Food Science and Technology - Porous Stone Seasoning Kinetics",
            "Oral Recipes and Seasoning Practices of Salem Stone Potters"
        ],
        "content": "# Kalchatti Mustard-Sesame Oil Curing, Rice Starch Simmering & Thermal Seasoning\n\nA newly turned steatite vessel is in a fragile, uncured state: soft, microporous, greyish-white, and vulnerable to catastrophic fracture under sudden thermal gradients. The traditional Tamil process of *pazhakkuthal* (பழக்குதல் — seasoning or curing) is an empirical bio-chemical transformation that alters the mechanical and thermal surface chemistry of the stone over 15 to 21 days.\n\n### Micro-Porosity & Lipid Impregnation Kinetics\nUncured steatite contains interstitial micro-voids between talc and chlorite phyllosilicate crystals. If heated directly over a hearth fire, trapped air and crystalline water expand unevenly, inducing spalling and structural cracking:\n1. **Turmeric & Lipid Primer**: The dry vessel is thoroughly rubbed inside and out with a warm paste of cold-pressed castor oil (*aamanakku ennai*) or unrefined sesame/mustard oil (*nallellu ennai* / *kadugu ennai*) combined with freshly milled turmeric powder (*manjal thool*).\n2. **Capillary Adsorption**: Castor oil possesses exceptionally high ricinoleic acid content ($\\approx 90\\%$), providing high viscosity and surface tension that deeply penetrates inter-crystalline clefts via capillary action. Turmeric supplies curcuminoids that act as natural polyphenolic antioxidants, preventing premature lipid rancidification while exerting antimicrobial action.\n3. **Sun Desiccation**: The oil-saturated stone sits under direct sunlight for 3 to 4 days, allowing solar heat ($\\approx 40^\\circ\\text{C}-45^\\circ\\text{C}$) to drive triglycerides deep into the mineral matrix.\n\n### Starch Gelatinization & Pore Sealing with *Kanji Thanneer*\nFollowing lipid priming, the vessel enters the aqueous curing phase using fermented rice starch water:\n- **Hot Gruel Baths**: Boiling rice starch water (*kanji thanneer* — drained from simmering parboiled rice) is poured into the vessel daily.\n- **Amylose & Amylopectin Infiltration**: As hot starch enters the micro-pores, the linear amylose and branched amylopectin molecules swell and gelatinize within the talc interstices.\n- **Fermentation Cross-Linking**: Over 10 to 14 days of daily replenishment, mild lactic acid fermentation occurs. The starch matrix cross-links with the impregnated lipids, forming an insoluble organo-mineral plug that seals the stone against moisture leakage and bacterial harboring.\n\n### Progressive Thermal Ramping (*Vemmai Pazhakkuthal*)\nDirect exposure to a vigorous hearth fire will crack even an oil-treated pot. Thermal acclimation proceeds through strict ascending energy stages:\n1. **Stage 1 (Lukewarm Hydration)**: Warm water is held in the vessel without external heat; discarded twice daily for 2 days.\n2. **Stage 2 (Sub-Simmer Water Heating)**: The pot is set over low charcoal embers (*thanal*) with water, slowly raising the temperature to $70^\\circ\\text{C}-80^\\circ\\text{C}$, never allowing a vigorous rolling boil.\n3. **Stage 3 (Acidic Broth Simmering)**: Dilute tamarind water (*puli thanneer*) with a pinch of salt and turmeric is gently brought to a slow simmer. The mild tartaric acid ($\\text{pH} \\approx 3.5$) pacifies surface alkaline minerals and hardens the starch-lipid composite.\n4. **Stage 4 (Full Culinary Induction)**: Used first for seasoned rasam or buttermilk kulambu before heavy frying or long-boiling dishes.\n\n### Emergence of the Jet-Black Patina\nThrough progressive heating, unsaturated fatty acids undergo thermal polymerization and pyrolysis, forming a resilient, cross-linked carbonaceous hydrophobic glaze. The stone transforms permanently from powdery chalk-grey into a lustrous, obsidian jet-black (*karu-mai*). This surface is naturally non-stick, chemically inert, and capable of withstanding repetitive thermal cycles across decades."
    },
    {
        "slug": "artifact-carved-steatite-kalchatti-cooking-pots-vadai-chatti-and-kuzhambu-vessels",
        "category": "artifact",
        "file": "artifact-carved-steatite-kalchatti-cooking-pots-vadai-chatti-and-kuzhambu-vessels.md",
        "name_en": "Carved Steatite Kalchatti Cooking Pots, Vadai-Chatti & Kuzhambu Vessels",
        "name_ta": "செதுக்கப்பட்ட கல்சட்டி, வடைச்சட்டி, குழம்புப் பாண்டங்கள் மற்றும் மாவரைக்கும் கல் பாத்திரங்கள்",
        "era": "Sangam to Contemporary Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "marutham",
        "summary_en": "The classic functional taxonomy of sculpted Tamil steatite cookware: the spherical, narrow-throated *kuzhambu kalchatti* for simmering tamarind and fish broths, flared-rim *rasam-chatti*, shallow heavy-based *vadai-chatti* for deep-frying with high thermal stability, heavy circular *kal-dosai-kal*, and interlocking flat stone lids (*kal-thattu*).",
        "summary_ta": "தமிழர் பாரம்பரிய சமையலறையின் பிரதான மாக்கல் பாண்டங்கள்: குழம்பு கொதிக்கும் உருண்டை வடிவக் கல்சட்டி, நறுமண ரசச் சட்டி, எண்ணெய் வெப்பம் குறையாமல் வடை சுடும் அகன்ற வடைச்சட்டி, தோசைக் கல் மற்றும் கல் தட்டுகள் ஆகியவற்றின் கட்டமைப்பு மற்றும் பயன்பாடுகள்.",
        "sources": [
            "Madras District Gazetteers - Salem Stone Wares",
            "South Indian Material Culture Studies",
            "Kongu Nadu Archaeological & Ethnographic Catalogues",
            "Traditional Kitchen Utensils of Tamilakam"
        ],
        "content": "# Carved Steatite Kalchatti Cooking Pots, Vadai-Chatti & Kuzhambu Vessels\n\nThe traditional Tamil hearth (*aduppu*) relied on an intricate material hierarchy of vessels, with steatite (*kalchatti*) occupying the apex of culinary performance for slow-simmered, acidic, and oil-fried preparations. Each vessel morphology was engineered over centuries for precise thermodynamic and culinary roles.\n\n### Typology of Traditional Steatite Cookware\n1. **Kuzhambu Kalchatti (குழம்பு கல்சட்டி)**:\n   - **Form**: Globular, spherical lower body with thick, convex bottom (18 to 25 mm thick) and slightly constricted neck with a rolled lip.\n   - **Function**: Designed specifically for *Vatha Kuzhambu*, *Meen Kuzhambu* (fish curry), and *Puli Kuzhambu*. The globular shape promotes toroidal convective currents during boiling, ensuring uniform distribution of tamarind, shallots, garlic, and gingelly oil without scorching the base.\n2. **Rasam Chatti (ரசச் சட்டி)**:\n   - **Form**: Wide-mouthed, gently flared conical bowl with medium wall thickness (12 to 15 mm).\n   - **Function**: Engineered for rapid convective roll followed by instantaneous flame shutoff. The moment crushed tomatoes, pepper, cumin, and garlic froth to a foam (*nurrathal*), the pot is taken off the flame; its residual heat completes the extraction without boiling away the aromatic volatile terpenes of coriander and asafoetida.\n3. **Vadai Chatti (வடைச் சட்டி)**:\n   - **Form**: Wide, shallow parabolic wok-like basin with heavily thickened center base (25 to 35 mm).\n   - **Function**: Used for deep-frying lentil fritters (*medu vadai*, *aama vadai*). In metal woks, dropping cold lentil batter causes sudden oil temperature drops, leading to greasy, soggy vadais. In a steatite *vadai-chatti*, the enormous thermal inertia prevents temperature drops, instantly sealing the outer crust into a crisp shell while cooking the interior to a light, airy crumb.\n4. **Kal-Dosai-Kal (கல் தோசைக் கல்)**:\n   - **Form**: Flat circular disc, 25 to 35 cm in diameter, weighing 4 to 8 kg, with shallow bevelled borders and a micro-grooved bottom for heat dispersion.\n   - **Function**: Delivers uniform, radiant conduction for fermented rice-black gram batter, producing thick, spongy *uthappams* or *morumoru dosais* with golden bottoms that never blister or char.\n5. **Kal-Thattu (கல் தட்டு / Stone Lid)**:\n   - **Form**: Circular flat steatite disc with an integral carved center knob.\n   - **Function**: Interlocks closely with the vessel lip. Its significant mass creates a mild pressure-seal (*dum* effect), retaining steam, aromatic vapors, and moisture within the boiling vessel.\n\n### Structural Anatomy & Hand-Carved Ergonomics\nTraditional kalchattis incorporate structural details that reflect centuries of vernacular engineering:\n- **Integrated Lug Handles (*Kadhu*)**: Rather than attached metal handles, the stone is turned with two diametrically opposed, solid stone lugs protruding from the upper rim, eliminating joint fatigue or detachment.\n- **Convex Heat Wells**: The bottom exterior is gently crowned rather than flat, allowing flame tongues from firewood or charcoal to wrap smoothly around the pot's circumference without creating localized thermal hot spots.\n- **Acoustic Integrity Test**: Connoisseurs and buyers tap the vessel rim with a knuckle or bronze coin before purchase; a clear, ringing metallic tone (*kin-endru*) confirms structural continuity and absence of internal hairline fissures (*kal-vedippu*)."
    },
    {
        "slug": "artifact-traditional-soapstone-lathe-mandrels-tempered-steel-gouges-and-polishing-leaves",
        "category": "artifact",
        "file": "artifact-traditional-soapstone-lathe-mandrels-tempered-steel-gouges-and-polishing-leaves.md",
        "name_en": "Traditional Soapstone Lathe Mandrels, Tempered Steel Gouges & Polishing Leaves",
        "name_ta": "பாரம்பரிய மாக்கல் கடைசல் கடைஞு குதிரை, எஃகு வளைவுளிகள் மற்றும் பட்டை தீட்டும் இலைகள்",
        "era": "Early Historic to Modern Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "kurinji",
        "summary_en": "The specialized toolkit of Tamil steatite turners and sculptors: the low-slung wooden mandrel lathe (*kudhirai-pidi*) with iron center pivots, hand-forged high-carbon steel gouges (*valai-uli*, *kothu-uli*, *thuruval-uli*), rope-drive bow thongs, and botanical abrasives including leaves of the sandpaper fig (*ottan-ilai*, *Ficus exasperata*) and oil-schist rubbing stones.",
        "summary_ta": "மாக்கல் கடைசல் கலைஞர்களின் மரபான கருவித் தொகுதி: மரத்தால் ஆன கடைஞு குதிரை, மாக்கல்லை இறுகப் பிடிக்கும் உலோகப் பிடிமானங்கள், வளைந்த எஃகு உளிகள் (வளைவுளி, கொத்துளி, துருவலுளி), வளைசுழற்று கயிறு மற்றும் இயற்கை உராய்வுத் தாள் போன்ற ஒட்டன் இலைகள்.",
        "sources": [
            "Crafts and Artisans of Ancient South India",
            "Salem Viswakarma Tooling Glossaries",
            "Ethnoarchaeology of Southern Indian Stone Turnery",
            "Survey of Traditional Crafts in Kongu Region"
        ],
        "content": "# Traditional Soapstone Lathe Mandrels, Tempered Steel Gouges & Polishing Leaves\n\nThe turning of steatite into delicate, thin-walled cookware (*kalchatti*) relies on a sophisticated toolkit developed by the stone-artisan guilds (*kalthachan* / *Viswakarma Kammalar*) of Kongu Nadu and Northern Tamil Nadu. This array of tools bridges pyrotechnic metallurgy, carpentry, and botanical polishing.\n\n### Anatomical Components of the Kudhirai Lathe\nThe lathe (*kudhirai* — literally 'horse', reflecting its straddled mount) consists of:\n1. **Padi-Maram (Base Beams)**: Two parallel balks of heavy *Albizia lebbeck* (*Vaagai*) or *Tectona grandis* (*Thekku*) wood anchored to stone footings embedded in the earth.\n2. **Kudhirai-Pidi (Tailstock and Headstock Brackets)**: Upright timber posts fitted with forged iron gudgeon sockets (*kinnath-thuli*).\n3. **Mandrel Spindle (*Kadaisal Thandu*)**: A 30 to 45 mm diameter forged iron axle with a threaded or spiked faceplate (*arachchi*) onto which the raw steatite block is bedded.\n4. **Pitch Mounting Matrix (*Kal-Pisin*)**: The stone blank is affixed to the faceplate using a molten paste of dammar resin (*kungiliyam*), beeswax (*then-mezhugu*), and fine brick dust (*sengal thool*). Upon cooling, this matrix yields an ultra-rigid, vibration-dampening mount that releases easily upon heating.\n5. **Bow Drive (*Villu*) & Thong (*Varai*)**: A curved bamboo or tamarind branch (1.2 to 1.5 m long) tensioned with a treated water-buffalo hide thong (*thool-kayiru*).\n\n### Metallurgy of Specialized Turning Gouges (*Urukk-Uli*)\nBecause soft talc is interspersed with hard micro-crystals of quartz, tremolite, and magnesite, ordinary iron quickly blunts. The turning gouges are forged from high-carbon wootz or blister crucible steel (*urukku*):\n- **Valai-Uli (Curved Gouge)**: Forged with an elliptic scoop profile and a $30^\\circ$ single-bevel cutting angle. Used for the initial internal bore; cuts by peeling continuous curling ribbons of talc powder rather than chipping.\n- **Thuruval-Uli (Spoon Scraper)**: Features a hemispherical spade head on an elongated tang, allowing the craftsman to reach into deep round-bellied vessels and finish the inner bottom without chatter marks.\n- **Eettu-Uli (Grooving Chisel)**: A needle-pointed or V-beveled chisel used to incise concentric decorative and functional cooling grooves around the exterior neck and rim.\n- **Tempering Method (*Thannir Payithal*)**: Chisels are heated to cherry-red heat ($\\approx 850^\\circ\\text{C}$) in a charcoal hearth and quenched in a bath of castor oil and neem leaf extract to produce a glass-hard cutting edge (HRC 58–62) backed by a ductile, shock-absorbing shank.\n\n### Natural Abrasive & Polishing Materials\nBefore the advent of silicon carbide sandpapers, surface finishing was strictly botanical and mineral:\n- **Ottan-Ilai (Sandpaper Fig Leaves, *Ficus exasperata*)**: The leaves have stiff trichomes encrusted with amorphous silicon dioxide ($\\text{SiO}_2$). Rubbed wet against green-turned soapstone, they remove lathe ridges with microscopic precision without gouging the soft talc matrix.\n- **Ural-Kal & Theippu-Kal**: Fine-grained silty hematite stones used with water to burnish the vessel surface to silky smoothness.\n- **Polishing Paste**: A final hand-burnishing using castor oil slurry mixed with the finest air-floated talc powder collected from the lathe trough, imparting a gleaming ivory-grey pre-cure finish."
    },
    {
        "slug": "concept-steatite-talc-chlorite-high-volumetric-heat-capacity-and-thermal-shock-resistance",
        "category": "concept",
        "file": "concept-steatite-talc-chlorite-high-volumetric-heat-capacity-and-thermal-shock-resistance.md",
        "name_en": "Steatite Talc-Chlorite High Volumetric Heat Capacity & Thermal Shock Resistance",
        "name_ta": "மாக்கல் டால்க்-குளோரைட் உயர்ந்த பரும வெப்ப ஏற்புத்திறன் மற்றும் வெப்ப அதிர்ச்சி எதிர்ப்பு இயற்பியல்",
        "era": "Ancient to Modern Scientific Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "kurinji",
        "summary_en": "The solid-state physics and thermodynamics of metamorphic steatite (talc-schist): exceptional volumetric heat capacity ($C_v \\approx 2.7 \\times 10^6 \\text{ J}/(\\text{m}^3\\cdot\\text{K})$), moderate thermal conductivity ($k \\approx 3.0 - 4.5 \\text{ W}/(\\text{m}\\cdot\\text{K})$), and macroscopic thermal shock resistance arising from energy dissipation across flexible phyllosilicate sheet slip planes of talc $\\text{Mg}_3\\text{Si}_4\\text{O}_{10}(\\text{OH})_2$ and chlorite minerals.",
        "summary_ta": "மாக்கல்லின் இயற்பியல் மற்றும் வெப்ப இயக்கவியல் பண்புகள்: அதிக பரும வெப்ப ஏற்புத்திறன் ($C_v$), சீரான வெப்பக் கடத்துத்திறன் ($k$) மற்றும் டால்க் கனிமத்தின் அடுக்குக் கட்டமைப்பு (Phyllosilicates) மூலம் வெப்ப அதிர்ச்சியை உள்வாங்கி வெடிப்பைத் தடுக்கும் நுண்-கட்டமைப்பு இயல்பு.",
        "sources": [
            "CRC Handbook of Chemistry and Physics - Thermophysical Properties of Rocks",
            "Journal of Thermal Analysis and Calorimetry - Steatite Minerals",
            "Solid State Mineralogy of South Indian Schist Belts",
            "Thermodynamics of Traditional Cooking Media"
        ],
        "content": "# Steatite Talc-Chlorite High Volumetric Heat Capacity & Thermal Shock Resistance\n\nThe thermal superiority of Tamil *kalchatti* cookware over modern aluminum, stainless steel, and unglazed terracotta is rooted in the unique thermodynamics of talc-chlorite metamorphic rock. Its ability to absorb, store, and smoothly release thermal energy is governed by fundamental solid-state physics.\n\n### Thermophysical Properties Comparison\nThe performance of cookware depends on four interrelated physical properties: density ($\\rho$), specific heat capacity ($c_p$), thermal conductivity ($k$), and volumetric heat capacity ($C_v = \\rho \\cdot c_p$):\n\n| Material | Density $\\rho$ ($\\text{kg/m}^3$) | Specific Heat $c_p$ ($\\text{J/kg}\\cdot\\text{K}$) | Volumetric Heat Capacity $C_v$ ($\\text{MJ/m}^3\\cdot\\text{K}$) | Thermal Conductivity $k$ ($\\text{W/m}\\cdot\\text{K}$) |\n|---|---|---|---|---|\n| **Steatite (Soapstone)** | **2700 – 2850** | **980 – 1050** | **2.65 – 2.99** | **3.0 – 4.5** |\n| Unglazed Terracotta | 1800 – 2000 | 800 – 900 | 1.44 – 1.80 | 0.8 – 1.2 |\n| Cast Iron | 7100 – 7300 | 450 – 490 | 3.20 – 3.55 | 45.0 – 55.0 |\n| Aluminium | 2700 | 900 | 2.43 | 205.0 – 237.0 |\n| Copper | 8960 | 385 | 3.45 | 385.0 – 400.0 |\n\nWhile copper and aluminium have very high thermal conductivity ($k > 200 \\text{ W/m}\\cdot\\text{K}$), they dissipate heat immediately once the flame is lowered. Cast iron has high volumetric heat capacity but its thermal conductivity ($k \\approx 50$) causes violent localized boiling and scorching at the bottom. Terracotta stores little heat ($C_v \\approx 1.6$).\n**Steatite strikes the ideal golden mean**:\n- Volumetric heat capacity of $\\approx 2.8 \\text{ MJ/m}^3\\cdot\\text{K}$ enables massive latent heat storage in a 15–20 mm thick pot wall.\n- Moderate thermal conductivity ($k \\approx 3.5 \\text{ W/m}\\cdot\\text{K}$) is approximately 60 times lower than aluminium, preventing sharp thermal spikes and distributing heat evenly across the entire hemisphere of the pot.\n\n### Phyllosilicate Mineralogy & Thermal Shock Resistance\nPure quartz, porcelain, and coarse earthenware crack when subjected to abrupt thermal gradients ($\\Delta T = T_{\\text{inside}} - T_{\\text{outside}}$) due to brittle tensile stress:\n$$\\sigma = \\frac{E \\cdot \\alpha \\cdot \\Delta T}{1 - \\nu}$$\nwhere $E$ is Young's modulus, $\\alpha$ is thermal expansion coefficient, and $\\nu$ is Poisson's ratio.\nSteatite resists thermal fracture through microscopic stress dissipation:\n1. **Sheet Silicate Slip Planes**: Talc is composed of electrically neutral T-O-T sandwiches (tetrahedral $\\text{Si}_4\\text{O}_{10}$ sheets flanking octahedral $\\text{Mg}_3\\text{O}_4(\\text{OH})_2$ sheets) held together solely by weak van der Waals forces. Under thermal expansion, these sheets slide across basal planes $(001)$ without catastrophic lattice cleavage.\n2. **Interlocking Felted Chlorite**: The presence of fine-grained, randomly oriented chlorite and tremolite needles creates a felt-like micro-texture (*decussate structure*). Micro-fissures generated by thermal stress are blunted and diverted within micrometers, dissipating crack-propagation energy.\n3. **Low Volumetric Thermal Expansion**: Talc exhibits an exceptionally low linear coefficient of thermal expansion ($\\alpha \\approx 6.0 - 7.5 \\times 10^{-6} \\text{ K}^{-1}$), minimizing localized thermal strain across the inner and outer vessel surfaces."
    },
    {
        "slug": "concept-non-reactive-magnesium-silicate-chemistry-and-tamarind-acid-preservation",
        "category": "concept",
        "file": "concept-non-reactive-magnesium-silicate-chemistry-and-tamarind-acid-preservation.md",
        "name_en": "Non-Reactive Magnesium Silicate Chemistry & Tamarind Acid Preservation",
        "name_ta": "வேதி வினையற்ற மெக்னீசியம் சிலிகேட் வேதியியல் மற்றும் புளி அமில உணவுப் பாதுகாப்பு",
        "era": "Sangam to Contemporary Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "marutham",
        "summary_en": "The chemical inertness of magnesium phyllosilicates under acidic culinary conditions: complete resistance to dissociation from tartaric acid (tamarind), citric acid, and lactic acid at pH 2.5–4.5, eliminating metallic ionic leaching and oxidation, while facilitating passive anti-microbial preservation allowing cooked gravies to remain unspoiled for 48 hours without refrigeration.",
        "summary_ta": "புளிக் குழம்பு, மீன் குழம்பு போன்ற அமிலத் தன்மை கொண்ட உணவுகளில் உள்ள டார்டாரிக் அமிலத்துடன் வினையாற்றாத மெக்னீசியம் சிலிகேட் வேதியியல், உலோக நச்சுத்தன்மையைத் தவிர்த்தல் மற்றும் உணவை 48 மணிநேரத்திற்கு மேல் கெடாமல் பாதுகாக்கும் இயற்கை நுட்பம்.",
        "sources": [
            "Food Chemistry - Leaching Kinetics of Cookware Substrates",
            "Siddha Toxicology and Pathartha Guna Chinthamani",
            "International Journal of Gastronomy and Food Science",
            "Kongu Culinary Preservation Records"
        ],
        "content": "# Non-Reactive Magnesium Silicate Chemistry & Tamarind Acid Preservation\n\nThe hallmark of classical Tamil gastronomy is the masterly manipulation of sourness (*pulippu*), achieved primarily through tamarind pulp (*Padi Puli*, *Tamarindus indica*), dried raw mango (*maa-vathal*), kokum (*kudampuli*, *Garcinia cambogia*), and buttermilk. While these acidic matrices decompose and react toxically with metal cookware, steatite (*kalchatti*) provides absolute chemical inertness.\n\n### Acidity Profiles & Metal Cookware Vulnerabilities\nTamil gravies such as *Vatha Kuzhambu*, *Puli Kuzhambu*, *Mor Kuzhambu*, and *Rasam* maintain an operating acidity of $\\text{pH } 2.5 \\text{ to } 4.2$, dominated by:\n- Tartaric acid ($\\text{C}_4\\text{H}_6\\text{O}_6$) from tamarind.\n- Citric and malic acids from tomatoes and raw mango.\n- Lactic acid from sour curd and buttermilk.\n\nWhen these organic acids are boiled in conventional metallic vessels, dangerous galvanic and dissolution reactions occur:\n1. **Copper & Brass (*Pithalai / Chembu*)**: Tartaric and lactic acids dissolve copper and zinc, forming toxic copper tartrate and cupric carbonate verdigris ($\\text{CuCO}_3\\cdot\\text{Cu(OH)}_2$). Cooking acidic broths in untinned brass (*velli-poosaatha pithalai*) induces nausea, severe gastrointestinal irritation, and metallic off-flavors.\n2. **Cast Iron (*Erumbu*)**: Acid strips surface iron, converting it into ionic ferrous tartrate. This alters the vibrant red or golden color of *rasam* and *kuzhambu* into an unappetizing inky grey-black while imparting a harsh metallic aftertaste.\n3. **Aluminium (*Thagara-velli*)**: Readily leaches neurotoxic $\\text{Al}^{3+}$ ions into acidic boiling solutions, forming soluble aluminium citrates and tartrates exceeding safe WHO daily thresholds.\n\n### The Inertness of Magnesium Phyllosilicates\nTalc ($\\text{Mg}_3\\text{Si}_4\\text{O}_{10}(\\text{OH})_2$) is an exceptionally stable magnesium silicate. The divalent magnesium ions ($\\text{Mg}^{2+}$) are locked within octahedral sheets, tightly coordinated between two hydrophobic tetrahedral silicate layers ($\\text{SiO}_4$).\n- Under the dilute organic acid concentrations and cooking temperatures ($100^\\circ\\text{C}-110^\\circ\\text{C}$) of culinary preparation, the octahedral magnesium bonds resist protonation and acid hydrolysis.\n- No heavy metal ions, metallic oxides, or free radicals leach into the food matrix.\n- The organic volatiles, delicate polyphenols, and essential oils of spices (such as curcumin, piperine, cuminaldehyde, and eugenol) retain their pristine chemical structure and natural flavor nuances.\n\n### 48-Hour Room-Temperature Preservation Mechanism\nIn tropical Tamil Nadu, cooked curries kept at ambient room temperature ($30^\\circ\\text{C}-38^\\circ\\text{C}$) normally sour and ferment within 12 to 18 hours due to microbial proliferation (*pulingi-pothal*). However, curries prepared and stored in seasoned *kalchatti* remain fresh, fragrant, and microbiologically safe for 36 to 48 hours without refrigeration:\n1. **Prolonged Natural Pasteurization**: Due to the massive heat retention of the thick steatite walls, once the flame is extinguished, the gravy remains above the bacterial growth danger zone ($>65^\\circ\\text{C}$) for more than 2 to 3 hours, completing extended thermal pasteurization.\n2. **Hermetic Stone Lid Seal**: The heavy *kal-thattu* stone lid prevents airborne fungal spores (*Aspergillus*, *Rhizopus*) and bacterial contaminants (*Bacillus cereus*) from entering during cooling.\n3. **Micro-Alkaline Buffering**: Traces of bio-available magnesium and calcium at the carbonized mineral interface exert a subtle buffering action, preventing the rapid bacterial lactic acidification that causes curries to turn sour and putrefy."
    },
    {
        "slug": "concept-post-fire-heat-retention-eutectic-simmer-and-herbal-nutrient-preservation",
        "category": "concept",
        "file": "concept-post-fire-heat-retention-eutectic-simmer-and-herbal-nutrient-preservation.md",
        "name_en": "Post-Fire Heat Retention, Eutectic Simmer & Herbal Nutrient Preservation",
        "name_ta": "அடுப்பணைத்த பின் நீடிக்கும் தணல் கொதிப்பு, நுண்வெப்பச் சமையல் மற்றும் மூலிகை சத்துப்பாதுகாப்பு",
        "era": "Sangam to Contemporary Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "mullai",
        "summary_en": "The thermo-culinary phenomenon of post-hearth boiling (*aduppanai-pin-kodhippu* or *thenal simmer*): steady latent thermal discharge maintaining vigorous rolling boiling for 5-10 minutes and sustained simmering for 30-45 minutes after fire extinguishment, preventing destructive thermal degradation of volatile spices (piperine, curcumin, allicin) and conserving fuel energy.",
        "summary_ta": "அடுப்பை அணைத்த பிறகும் கல்சட்டியின் தடிமனான சுவர்களில் தேங்கியுள்ள வெப்ப ஆற்றல் மூலம் உணவு மேலும் 30-45 நிமிடங்கள் தணலில் கொதிக்கும் நுட்பம்; இது மஞ்சள், மிளகு போன்ற மூலிகைகளின் வெப்பத்தால் அழியும் நுண்சத்துக்களைச் சிதையாமல் பாதுகாக்கும் விதம்.",
        "sources": [
            "Thermal Physics in Traditional Culinary Systems",
            "Kongu Ethno-Culinary Thermodynamics",
            "Journal of Ethnobiology and Ethnomedicine",
            "Phytochemical Degradation Kinetics in Indian Cookery"
        ],
        "content": "# Post-Fire Heat Retention, Eutectic Simmer & Herbal Nutrient Preservation\n\nOne of the most striking visual and practical aspects of Tamil cooking in *kalchatti* is *aduppanai-pin-kodhippu* (அடுப்பணைத்த பின் கொதிப்பு) — post-fire boiling. Long after the hearth flame has been completely quenched or the pot lifted off the stove onto a straw ring (*pirimanni*), the food inside continues to bubble, roll, and simmer for up to 30 to 45 minutes solely on stored stone thermal inertia.\n\n### Physics of Transient Heat Discharge\nThe thermal energy $Q$ stored within a steatite pot of mass $m \\approx 4 \\text{ kg}$ heated to $130^\\circ\\text{C}$ relative to ambient room temperature ($30^\\circ\\text{C}$) is:\n$$Q = m \\cdot c_p \\cdot \\Delta T = 4 \\text{ kg} \\times 1000 \\text{ J/kg}\\cdot\\text{K} \\times 100 \\text{ K} = 400,000 \\text{ Joules} = 400 \\text{ kJ}$$\nBecause steatite has low thermal conductivity ($k \\approx 3.5 \\text{ W/m}\\cdot\\text{K}$), this stored thermal energy cannot dump rapidly to the ambient air. Instead, heat flows into the liquid boundary layer governed by Fourier's law:\n$$\\frac{dQ}{dt} = -k \\cdot A \\cdot \\frac{dT}{dx}$$\nThis creates a continuous, self-regulating thermal discharge:\n- **Phase 1 (Vigorous Roll, 0 to 8 minutes)**: The surface maintains nucleate boiling ($100^\\circ\\text{C}$), continuing active emulsification of oil and tamarind broth.\n- **Phase 2 (Eutectic Simmer, 8 to 25 minutes)**: Temperature hovers at $85^\\circ\\text{C} - 92^\\circ\\text{C}$, ideal for gelatinizing pectins and tenderizing vegetable cell walls without boiling agitation.\n- **Phase 3 (Warm Maturation, 25 to 60+ minutes)**: The temperature declines gradually at less than $0.5^\\circ\\text{C}$ per minute, keeping the meal hot for direct table service without re-heating.\n\n### Fuel Efficiency & Firewood Conservation in Agrarian Life\nIn the dry scrublands of Kongu Nadu and the Deccan borderlands, firewood (*viragu*) was a hard-won resource. Cooking in steatite served as an ingenious energy conservation technology:\n- Traditional cooks systematically extinguish firewood embers when a curry is only 75% to 80% cooked.\n- The remaining 20% to 25% of cooking time proceeds entirely on internal stone enthalpy (*thenal-il-veguthal*).\n- This achieved a net 30% to 40% reduction in biomass fuel consumption compared to thin clay pots or metal vessels.\n\n### Thermal Protection of Heat-Sensitive Phytochemicals\nHigh-heat boiling in thin metal pots destroys heat-labile medicinal and aromatic compounds found in classical Tamil rasams and herbal gravies (*marundhu kuzhambu*):\n1. **Curcuminoids in Turmeric**: Rapid boiling above $100^\\circ\\text{C}$ causes hydrolytic degradation of curcumin into ferulic acid and vanillin. The gentle post-fire simmer preserves over 85% of active curcumin in micellar suspension.\n2. **Piperine in Black Pepper**: Piperine easily isomerizes into tasteless isochavicine under violent prolonged boiling; gentle kalchatti simmering retains its pungent bio-availability and synergy with curcumin.\n3. **Allicin & Diallyl Disulfide in Garlic**: The sulfurous antibacterial and cardioprotective volatiles of crushed garlic are preserved intact rather than volatilizing away in steam.\n4. **Volatile Monoterpenes in Curry Leaves (*Kariveppilai*)**: Beta-caryophyllene, pinene, and linalool are sustained within the oily emulsion layer, infusing the broth with deep, complex aromatics impossible to replicate in modern cookware."
    },
    {
        "slug": "institution-shevaroy-steatite-quarry-guilds-silpis-and-kongu-culinary-potters",
        "category": "institution",
        "file": "institution-shevaroy-steatite-quarry-guilds-silpis-and-kongu-culinary-potters.md",
        "name_en": "Shevaroy Steatite Quarry Guilds, Silpis & Kongu Culinary Potters",
        "name_ta": "சேர்வராயன் மலை மாக்கல் சுரங்க வணிகக் குழுக்கள், சிற்பாசாரிகள் மற்றும் கொங்கு சமையற் கற்சட்டி ஆசான்கள்",
        "era": "Medieval Chola to Modern Era",
        "year_start": 800,
        "year_end": 2025,
        "thinai": "kurinji",
        "summary_en": "The socio-economic and craft guilds of Tamil stone turners (kalthachan and Kammalar Viswakarma artisan guilds) operating in the Shevaroy and Kongu uplands: hereditary knowledge transmission, quarry extraction rights (*kalthozhil urimai*), division of labor between pit-miners, lathe-carvers, and merchant cartels, and customary supply of kalchattis to Chola temple kitchens (*madapalli*).",
        "summary_ta": "சேர்வராயன் மலை மற்றும் கொங்கு மண்டல மாக்கல் சுரங்கங்களை நிர்வகித்த சிற்பாசாரியர், கல்தச்சன் மற்றும் விஸ்வகர்மா வணிகக் குழுக்கள், தலைமுறை தலைமுறையாகக் கடத்தப்பட்ட கடைசல் நுட்பங்கள் மற்றும் சோழர் திருக்கடைக் கோயில் மடப்பள்ளி விநியோக நெறிமுறைகள்.",
        "sources": [
            "South Indian Inscriptions - Chola Guild Charters",
            "Kongu Mandala Sathakam",
            "Caste, Tribe and Artisan Guilds of Southern India",
            "Epigraphia Indica - Artisan Tax Grants and Mineral Royalties"
        ],
        "content": "# Shevaroy Steatite Quarry Guilds, Silpis & Kongu Culinary Potters\n\nThe production of steatite cookware in Tamil history was never an unorganized cottage craft; it was governed by sophisticated artisan guilds (*kalthachan manram* or *Kammalar Viswakarma srenis*) embedded within regional merchant corporations such as the *Ainnurruvar* (Ayyavole 500) and *Manigramam*.\n\n### Hereditary Guild Division of Labor\nFrom the medieval Chola era through the Vijayanagara and Nayaka periods, the steatite trade along the Shevaroy foothills developed specialized occupational strata:\n1. **Kal-Vettigal (Quarry Extractors)**: Specialized miners drawn from hill communities and local stoneworkers who held customary mineral rights (*kalthozhil kani*). They possessed deep geological lore regarding talc-schist veins, distinguishing between *pal-kal* (soft milk stone ideal for lathe vessels), *karu-marundhu-kal* (dark medicinal stone), and brittle *chari-kal* (defective schist).\n2. **Kadaisal Silpis (Lathe Turners)**: Master artisans belonging to the Viswakarma stone-sculptor sub-castes. Operating workshops in towns like Omalur, Mecheri, and Tharamangalam, they guarded lathe geometry, spindle calibration, and gouge tempering as closely held guild secrets passed exclusively from father to son or master to apprentice (*gurukula vriksham*).\n3. **Pazhakkuvor (Seasoning Practitioners)**: Specialized domestic handlers and merchant agents who acquired rough-turned vessels, conducted bulk oil-gruel curing in dedicated vats, and tested acoustic resonance before marketing.\n4. **Vaniyakkaran & Kaikolar Merchants**: Transported cured kalchattis via pack-bullock caravans (*erudhu-pothi*) along the Kaveri river trade highways to Thanjavur, Madurai, Kanchipuram, and coastal port settlements.\n\n### Royal Charters & Temple Kitchen (*Thirumadapalli*) Endowments\nInscriptions from the great Chola temples (Thanjavur Brihadisvara, Tiruvannamalai Annamalaiyar, and Salem Sukavaneswarar) record regular royal grants and endowments dedicated to temple kitchens:\n- **Purity & Ritual Sanctity**: Temple kitchens (*thirumadapalli*) held stringent ritual purity laws (*aacharam*). Unlike metal pots that could become ritually defiled (*echil*) or leach toxic patinas into consecrated offerings (*prasadam*), stone vessels carved from natural earth were classified as inherently pure (*nithya-suddham*).\n- **Inscriptional Mentions of *Kal-Kalan***: Chola epigraphs record the donation of *kal-kalan* (stone cooking vessels) alongside gold, sheep, and land grants. Endowments specified that temple endowments must purchase and replace *kalchatti* vessels from authorized regional artisan guilds, ensuring a steady, protected economic patronage for Shevaroy carvers.\n\n### Colonial Encounters & Guild Resilience\nDuring the 19th-century British survey of the Salem District, colonial mineralogists and district collectors (notably Francis Buchanan and F.J. Richards) documented the immense output of the Omalur steatite turners:\n- Tens of thousands of kalchattis, platters, and stone cups were exported annually across the Madras Presidency, Ceylon, and the Straits Settlements.\n- Despite the mid-20th-century flooding of the Indian consumer market with cheap factory-pressed aluminium and stainless steel, the Omalur and Shevaroy guilds maintained their hereditary craft, sustained by the enduring conviction of South Indian families that no authentic *vatha kuzhambu* or *meen kuzhambu* can ever achieve true culinary perfection outside a seasoned kalchatti."
    },
    {
        "slug": "place-omalur-ancient-shevaroy-steatite-quarry-and-kalchatti-haven",
        "category": "place",
        "file": "place-omalur-ancient-shevaroy-steatite-quarry-and-kalchatti-haven.md",
        "name_en": "Omalur & Shevaroy Ancient Steatite Quarry and Kalchatti Haven",
        "name_ta": "ஓமலூர் மற்றும் சேர்வராயன் மலை தொன்மை மாக்கல் சுரங்கம் மற்றும் கல்சட்டி உற்பத்தித் தளம்",
        "era": "Megalithic to Contemporary Era",
        "year_start": -500,
        "year_end": 2025,
        "thinai": "kurinji",
        "summary_en": "The historic geographical heartland of South Indian steatite cookware manufacturing centered around Omalur, Mecheri, and the foothills of the Shevaroy (Servarayan) mountain range in Salem (11.7450° N, 78.0420° E), blessed with abundant metamorphosed ultramafic talcose schist deposits worked continuously from Megalithic times to the present day.",
        "summary_ta": "சேலம் மாவட்டத்தின் ஓமலூர், மேச்சேரி மற்றும் சேர்வராயன் மலையடிவாரப் பகுதி (11.7450° N, 78.0420° E), பெருங்கற்காலம் முதல் இன்று வரை உயர்தர மாக்கல் வெட்டி எடுக்கப்பட்டு, உலகப் புகழ்பெற்ற கல்சட்டிகளாக வடிக்கப்படும் முதன்மைப் புவியியல் தளம்.",
        "sources": [
            "Geological Survey of India - Salem Ultramafic Complex",
            "Imperial Gazetteer of India - Omalur Taluk",
            "Tamil Nadu State Archaeology Omalur Survey",
            "Salem District Mineral Resources & Traditional Crafts"
        ],
        "content": "# Omalur & Shevaroy Ancient Steatite Quarry and Kalchatti Haven\n\nLocated in the north-western pocket of Salem district in Kongu Nadu, the Omalur-Mecheri-Shevaroy tract ($11.7450^\\circ\\text{ N}, 78.0420^\\circ\\text{ E}$) represents the premier geological and artisanal epicenter of steatite (*kalchatti*) production in South India. For over two millennia, this region has transformed raw ultramafic mineral riches into the most prized cookware of the Tamil home.\n\n### Geological Landscape & Mineral Endowment\nThe region sits within the Southern Granulite Terrain, where the Shevaroy (Servarayan) hill ranges abut the Cauvery river basin.\n- **Ultramafic Magnesite-Steatite Complex**: The area hosts extensive Archean-aged ultramafic bodies that underwent greenschist-to-amphibolite facies metamorphism. Ultrabasic dunites and peridotites were serpentinized and subsequently altered by hydrothermal fluids rich in $\\text{CO}_2$, transforming olivine into massive talc, magnesite ($\\text{MgCO}_3$), and chlorite schist.\n- **The Omalur Quarry Belt**: Deep surface quarries and hillside exposures around Omalur, Karuppur, Mecheri, Tharamangalam, and Jalakandapuram expose steatite veins characterized by exceptionally uniform, fine-grained talc crystals devoid of abrasive quartz phenocrysts, earning them the traditional artisan title *vennai-kal* ('butter-stone').\n\n### Archaeological Antiquity & Megalithic Foundations\nArchaeological explorations in Salem and along the Amaravathi and Cauvery basins demonstrate that steatite exploitation dates to the Megalithic Iron Age:\n- **Iron Age Cist Burials**: Excavations at Megalithic burial sites around Omalur and Kongu uplands have yielded turned steatite beads, spindle whorls, and miniature steatite cosmetic/ritual pots dated between 500 BCE and 100 CE.\n- **Early Historic Sards**: Steatite vessel sherds with distinctive lathe turning grooves have been recovered from Sangam-era habitation layers, confirming that mechanical lathe turning was established in Tamilakam over two millennia ago.\n\n### The Living Craft Landscape of Omalur\nToday, Omalur and neighboring Mecheri maintain an unbroken living heritage:\n- **Artisan Clusters**: Hundreds of traditional stone carvers continue to work in family workshops along the roadsides and dedicated hamlets (*Silpi Nagar*).\n- **Sustainable Extraction**: Small-scale open pits operate with minimal mechanization, carefully extracting soft boulders using traditional steel wedges to prevent shatter shock within the rock.\n- **GI Geographical Indication Recognition**: Efforts by craft preservation societies and the Government of Tamil Nadu have sought Geographical Indication (GI) status for 'Salem/Omalur Kalchatti', safeguarding the authentic hand-turned, oil-cured cookware against synthetic composite substitutes.\n- **Global Diaspora Demand**: Finished Omalur kalchattis are packed in straw cartons and shipped across the world to the South Indian diaspora in Malaysia, Singapore, Sri Lanka, the United Kingdom, and the United States, sustaining ancient culinary memory through resilient geological stone."
    },
    {
        "slug": "text-sangam-and-medieval-tamil-records-on-kalchatti-stone-cookware-and-steatite-craft",
        "category": "text",
        "file": "text-sangam-and-medieval-tamil-records-on-kalchatti-stone-cookware-and-steatite-craft.md",
        "name_en": "Sangam & Medieval Tamil Records on Kalchatti Cookware and Steatite Craft",
        "name_ta": "சங்க இலக்கியம் மற்றும் இடைக்காலக் கல்வெட்டுகளில் கல்சட்டி, கற்பாத்திரம் மற்றும் மாக்கல் கைவினைப் பதிவுகள்",
        "era": "Sangam to Vijayanagara Era",
        "year_start": -300,
        "year_end": 1600,
        "thinai": "marutham",
        "summary_en": "Textual and epigraphic attestations of stone culinary vessels across classical Tamil literature: Perumpanarruppadai, Malaipadukadam, and Maduraikanchi verses detailing stone cooking hearths and stone vessels (*kallakku*, *kal-pathiram*), medieval Chola temple inscriptions recording gifts of *kalchatti* to sacred kitchens (*madapalli*), and Siddha Materia Medica treatises (*Pathartha Guna Chinthamani*) detailing the therapeutic benefits of cooking in steatite.",
        "summary_ta": "பெரும்பாணாற்றுப்படை, மலைபடுகடாம், மதுரைக் காஞ்சி போன்ற சங்க நூல்களில் கற்சட்டி மற்றும் பாண்டங்கள் பற்றிய குறிப்புகள்; சோழர் கல்வெட்டுகளில் கோயில் மடப்பள்ளிகளுக்குக் கொடையாக அளிக்கப்பட்ட கல்சட்டிகள்; மற்றும் சித்த மருத்துவ நூலான பதார்த்த குண சிந்தாமணியில் கல்சட்டி சமையலின் மருத்துவ நன்மைகள் பற்றிய பதிவுகள்.",
        "sources": [
            "Pathupattu - Perumpanarruppadai & Malaipadukadam",
            "South Indian Inscriptions Vol. II & XXIII (Chola Madapalli Records)",
            "Pathartha Guna Chinthamani - Kalchatti Gunam",
            "Epigraphia Carnatica and Kongu Inscriptions"
        ],
        "content": "# Sangam & Medieval Tamil Records on Kalchatti Cookware and Steatite Craft\n\nThe utilization, spiritual sanctity, and medical efficacy of stone culinary vessels are documented across two millennia of classical Tamil literary, epigraphical, and medical traditions.\n\n### Sangam Literary Evidences (*Pathupattu & Ettuthokai*)\nIn classical Sangam poetry, references to stone vessels appear in descriptions of pastoral (*mullai*), montane (*kurinji*), and agricultural (*marutham*) domestic life:\n- **Perumpanarruppadai (lines 100–105)**: The poet Kadiyalur Uruthirangannanar portrays the hearths of forest folk and traveling bards, describing solid stone hollowed vessels (*kallakku* / *karpattiram*) placed over triple-stone hearths (*kalladuppu*) to boil unpolished forest millets and wild pulses with deer meat and tamarind leaves.\n- **Malaipadukadam (lines 175–182)**: Depicts montane tribal hunters (*kanavar*) carving soft soapstone from mountain boulders to fashion cooking vessels and bowls that retain the heat of wild game stews long after the wood fires die down in mist-covered hill valleys.\n- **Maduraikanchi**: Refers to the bustling bazaars of Madurai where stone vessels, metalwares, and pottery were sold in specialized artisan quarters (*kalthachan theri*).\n\n### Medieval Chola Epigraphical Records\nIn Chola stone inscriptions (*kalvettu*) spanning the 10th to 13th centuries, gifts of cookware to temple dining halls and kitchens (*thirumadapalli*) were cataloged alongside precious temple jewels:\n- **Thanjavur Brihadisvara Inscriptions**: Detail endowments by King Rajaraja Chola I and royal queens specifying the provision of *kal-kalan* (stone cooking pots), *kal-chatti* (soapstone deep pans), and *kal-thali* (stone boiling basins) for boiling rice and pepper-cumin gravies (*kari-amudhu*) offered to Lord Peruvudaiyar.\n- **Purity Ordinances**: Epigraphs from Uttaramerur and Tribhuvani emphasize that temple kitchens must favor stone and earthen vessels over base metals for cooking milk, ghee, and sour curries, explicitly recording the belief that steatite cannot be defiled by acid or previous cookery once washed and fired.\n\n### Siddha Materia Medica & *Pathartha Guna Chinthamani*\nThe traditional Siddha medical canon systematically categorizes the physiological impacts of cooking in different vessel substrates. The classic 16th-century treatise *Pathartha Guna Chinthamani* (பதார்த்த குண சிந்தாமணி) dedicates a specific verse to the therapeutic virtues of stone cookware (*Kalchatti Gunam*):\n\n> *\"கல்சட்டியிற் சமைத்த கறியமுதம் தானுண்ணில்*  \n> *மெல்லப் பித்தமெல்லாம் விட்டுவிலகிப் போகுமே*  \n> *நல்ல பசியுண்டாம் நாவுக்கு ருசியுண்டாம்*  \n> *வல்ல வாதமுந் தீரும் பார்.\"*  \n\n**Translation & Medical Analysis**:\n*\"If one consumes seasoned curry cooked in a steatite kalchatti, excessive Pitta dosha (bile, internal heat, and inflammation) will gently disperse and depart; robust digestive fire (Agni) is kindled, the tongue experiences exquisite taste, and aggravated Vata (dryness, joint and nerve distress) is pacified.\"*\n\nSiddha physicians emphasized that:\n1. Unlike copper or iron which can agitate Pitta dosha through metallic heat, steatite is cooling (*seetha-veeryam*) and balancing.\n2. The slow, unforced simmer extracts the medicinal phytochemicals of herbs and roots without denaturing their vital essence (*ojas*), making kalchatti the mandatory vessel for preparing restorative medicated gruels (*marundhu kanji*) and postnatal tonics (*prasava leghyam*)."
    }
]

EDGES = [
    [
        "technology-steatite-talc-schist-quarrying-lathe-turnery-and-chisel-hollowing",
        "MANUFACTURES",
        "artifact-carved-steatite-kalchatti-cooking-pots-vadai-chatti-and-kuzhambu-vessels",
        "material_culture",
        "Megalithic to Modern Era",
        "Quarrying and lathe turnery produce steatite kalchatti cooking vessels",
        "Archaeological Survey of Tamil Nadu & Ethnographic Records of Omalur Artisans"
    ],
    [
        "technology-steatite-talc-schist-quarrying-lathe-turnery-and-chisel-hollowing",
        "UTILIZES_TOOL",
        "artifact-traditional-soapstone-lathe-mandrels-tempered-steel-gouges-and-polishing-leaves",
        "material_culture",
        "Early Historic to Modern Era",
        "Stone turners rely on wooden spindle mandrels and tempered steel gouges for hollowing",
        "Salem Viswakarma Tooling Glossaries & Ethnographic Surveys"
    ],
    [
        "place-omalur-ancient-shevaroy-steatite-quarry-and-kalchatti-haven",
        "PRACTICES_TECHNOLOGY",
        "technology-steatite-talc-schist-quarrying-lathe-turnery-and-chisel-hollowing",
        "material_culture",
        "Megalithic to Modern Era",
        "Omalur and Shevaroy quarry sites practice traditional lathe turnery and chisel hollowing",
        "Geological Survey of India & Salem District Gazetteers"
    ],
    [
        "institution-shevaroy-steatite-quarry-guilds-silpis-and-kongu-culinary-potters",
        "GOVERNS_PRODUCTION",
        "place-omalur-ancient-shevaroy-steatite-quarry-and-kalchatti-haven",
        "social_structure",
        "Medieval Chola to Modern Era",
        "Artisan guilds and silpis govern quarry extraction and production around Omalur",
        "South Indian Inscriptions - Chola Guild Charters"
    ],
    [
        "artifact-carved-steatite-kalchatti-cooking-pots-vadai-chatti-and-kuzhambu-vessels",
        "REQUIRES_PROCESS",
        "technology-kalchatti-mustard-oil-curing-rice-starch-simmering-and-thermal-seasoning",
        "material_culture",
        "Sangam to Contemporary Era",
        "Carved soapstone cookware requires prolonged oil and rice starch curing before culinary use",
        "Traditional Tamil Culinary Ethno-technological Surveys"
    ],
    [
        "artifact-carved-steatite-kalchatti-cooking-pots-vadai-chatti-and-kuzhambu-vessels",
        "EXHIBITS_PROPERTY",
        "concept-steatite-talc-chlorite-high-volumetric-heat-capacity-and-thermal-shock-resistance",
        "science_mineralogy",
        "Ancient to Modern Era",
        "Carved steatite vessels exhibit high volumetric heat capacity and thermal shock resistance",
        "CRC Handbook of Chemistry and Physics & Material Science of Soapstone"
    ],
    [
        "artifact-carved-steatite-kalchatti-cooking-pots-vadai-chatti-and-kuzhambu-vessels",
        "ENABLES_PRESERVATION",
        "concept-non-reactive-magnesium-silicate-chemistry-and-tamarind-acid-preservation",
        "culinary_science",
        "Sangam to Contemporary Era",
        "Steatite vessels ensure chemical inertness against tamarind acid preventing spoilage",
        "Food Chemistry - Leaching Kinetics of Cookware Substrates"
    ],
    [
        "concept-steatite-talc-chlorite-high-volumetric-heat-capacity-and-thermal-shock-resistance",
        "UNDERLIES_THERMAL_DYNAMIC",
        "concept-post-fire-heat-retention-eutectic-simmer-and-herbal-nutrient-preservation",
        "physics_thermodynamics",
        "Ancient to Modern Era",
        "High volumetric heat capacity enables extended post-fire simmering and nutrient preservation",
        "Journal of Thermal Analysis and Calorimetry"
    ],
    [
        "institution-shevaroy-steatite-quarry-guilds-silpis-and-kongu-culinary-potters",
        "PRESERVES_CRAFT",
        "technology-kalchatti-mustard-oil-curing-rice-starch-simmering-and-thermal-seasoning",
        "cultural_tradition",
        "Medieval Chola to Modern Era",
        "Artisan guilds preserve and transmit the multi-stage seasoning and curing protocol",
        "Kongu Mandala Sathakam & Oral Tradition of Salem Kammalar Silpis"
    ],
    [
        "text-sangam-and-medieval-tamil-records-on-kalchatti-stone-cookware-and-steatite-craft",
        "DOCUMENTS_ARTIFACT",
        "artifact-carved-steatite-kalchatti-cooking-pots-vadai-chatti-and-kuzhambu-vessels",
        "epigraphy_literature",
        "Sangam to Vijayanagara Era",
        "Sangam texts and temple inscriptions document carved stone cookware and temple kitchen vessels",
        "Pathupattu, South Indian Inscriptions Vol. II & XXIII"
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
