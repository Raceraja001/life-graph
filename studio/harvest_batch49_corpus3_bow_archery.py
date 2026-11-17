#!/usr/bin/env python3
"""
Harvester: Batch 49 - Ancient Tamil Bowyer Craft, Bamboo-Sinew Archery Mechanics, Arrowsmithing & Valvil Ori Kurinji Tradition
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
        "slug": "text-purananuru-and-sirupanarruppadai-on-valvil-ori-and-chera-vil-kodi-archery",
        "category": "text",
        "file": "text-purananuru-and-sirupanarruppadai-on-valvil-ori-and-chera-vil-kodi-archery.md",
        "name_en": "Purananuru & Sirupanarruppadai on Valvil Ori's Five-Quarry Shot & Chera Vil-Kodi Archery",
        "name_ta": "புறநானூறு மற்றும் சிறுபாணாற்றுப்படையில் வல்வில் ஓரியின் வில்லாற்றலும் சேரர் விற்கொடி மரபும்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "kurinji",
        "summary_en": "Classical Sangam poetic accounts in Purananuru (152), Sirupanarruppadai, Narrinai, and Ahananuru celebrating the Kolli Hills chieftain Valvil Ori—whose single iron-tipped pagazhi arrow pierced an elephant, tiger, deer, wild boar, and monitor lizard in succession—alongside the Chera royal bow banner (Vil-Kodi).",
        "summary_ta": "புறநானூறு (152), சிறுபாணாற்றுப்படை, நற்றிணை மற்றும் அகநானூற்றில் போற்றப்படும் கொல்லிமலை வள்ளல் வல்வில் ஓரியின் ஒரே கணையால் ஐந்து விலங்குகளை வீழ்த்திய வில்லாற்றலும் சேரரின் விற்கொடி மரபும்.",
        "sources": [
            "Purananuru (Poem 152 by Vanparanar)",
            "Sirupanarruppadai",
            "Narrinai",
            "Ahananuru",
            "Silappadikaram"
        ],
        "content": "# Purananuru & Sirupanarruppadai on Valvil Ori & Sangam Archery\n\nIn the Sangam poetic corpus, mastery of the curved bow (*kodun-cil* or *vaangu-vil*) epitomized both *Kurinji* montane hunting prowess and sovereign warfare:\n\n**Poetic Attestations:**\n- **Valvil Ori's Five-Beast Shot (*Purananuru* 152)**: The bard Vanparanar immortalizes `Valvil Ori` (\"Ori of the Mighty Bow\"), lord of Kolli Hills, recounting how a single loosed iron-headed shaft (*kollan azhal-mugam thiruthiya pagazhi*) tore through the head of a tusker elephant, transfixed a open-jawed tiger, felled a horned stag, pierced a bristling wild boar, and pinned an *udumbu* (monitor lizard) inside its burrow.\n- **Chera Vil-Kodi & Desert Highway Bowmen**: *Ahananuru* and *Silappadikaram* celebrate the Chera monarchs bearing the golden bow emblem (*Vil-Kodi*) and describe *Eyinar* and *Mazhavar* archers drawing taut hemp-strung bows."
    },
    {
        "slug": "concept-kal-moongil-bamboo-flexural-strain-energy-and-kodun-cil-stave-mechanics",
        "category": "concept",
        "file": "concept-kal-moongil-bamboo-flexural-strain-energy-and-kodun-cil-stave-mechanics.md",
        "name_en": "Kal-Moongil Bamboo Flexural Strain-Energy Storage & Kodun-Cil Stave Tillering Mechanics",
        "name_ta": "கல்மூங்கில் வில்லின் மீட்சித் திறன் சேமிப்பும் கொடுஞ்சில் வளைவுச் சமநிலை இயற்பியலும்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "kurinji",
        "summary_en": "Solid mechanics of traditional Tamil self and laminated bows (kodun-cil / maram-vil): functionally graded vascular fibers of solid hill bamboo (Dendrocalamus strictus, kal-moongil) and vengai heartwood storing elastic strain energy under high tensile-compressive stress, limb taper tillering, and brace-height geometry.",
        "summary_ta": "மலைக் கல்மூங்கில் மற்றும் வேங்கை மர விற்களின் (கொடுஞ்சில்) வெளிப்புறச் சிலிக்கா இழுவிசை, உட்புற நார் அழுத்தத் தாங்குதிறன் மற்றும் நாண் ஏற்றும்போது சமச்சீராக வளையும் பொறியியல்.",
        "sources": [
            "Biomechanics of Bamboo Self-Bows (Dendrocalamus strictus)",
            "Grayson Traditional Asian Archery",
            "South Indian Ethnographic Weapons Studies (Egerton & Hornell)"
        ],
        "content": "# Kal-Moongil Bamboo Strain-Energy & Kodun-Cil Stave Mechanics\n\nAncient Tamil bowyers engineered longbows and reflexed staves (*kodun-cil* or *nedun-cil*, $1.5-1.8\\text{ m}$ long) predominantly from solid montane bamboo (*Kal-Moongil*, *Dendrocalamus strictus*) and dense *Vengai* (*Pterocarpus marsupium*) heartwood:\n\n**Structural & Elastic Mechanics:**\n- **Functionally Graded Bamboo Stave**: The outer siliceous cortex of *kal-moongil* has a tensile strength exceeding $300\\text{ MPa}$, forming the back of the bow (facing the target) to resist splintering under extreme convex bending, while the inner lignified culm wall absorbs belly compression.\n- **Parabolic Limb Tillering**: By progressively scraping the inner nodes from the thick rigid grip (*pidi*) toward the tapered nock tips (*kuthu*), the bowyer equalizes bending stress $\\sigma = My/I$ along both limbs, achieving high strain-energy storage efficiency with minimal hand-shock (*adhirvu*) upon release."
    },
    {
        "slug": "concept-pagazhi-arrow-spine-paradox-and-helical-feather-fletching-aerodynamics",
        "category": "concept",
        "file": "concept-pagazhi-arrow-spine-paradox-and-helical-feather-fletching-aerodynamics.md",
        "name_en": "Pagazhi Arrow Dynamic Spine Oscillation, Front-of-Center Balance & Helical Fletching Aerodynamics",
        "name_ta": "பகழி (அம்பு) தண்டின் அதிர்வு நெகிழ்வும் கழுகுச் சிறகுச் சுழல் காற்றியக்கவியலும்",
        "era": "Iron Age to Medieval Era",
        "year_start": -500,
        "year_end": 1600,
        "thinai": "kurinji",
        "summary_en": "Internal and external ballistics of Tamil war and hunting arrows (pagazhi, kanai, ambu): matching shaft flexural spine stiffness to bow draw weight to clear the stave via the archer's paradox, front-of-center mass distribution from heavy steel heads, and three-vane eagle/vulture feather fletching (oozhi) inducing stabilizing axial spin.",
        "summary_ta": "வில்லின் இழுவிசைக்கு ஏற்ப அம்புக் கோலின் (பகழி, கணை) வளைவு அதிர்வைச் சமன் செய்தல், இரும்பு முனையின் ஈர்ப்பு மையம் மற்றும் கழுகு இறகுகள் (ஊழி) தரும் சுழல் நிலைப்புத்தன்மை.",
        "sources": [
            "Aerodynamics and Ballistics of Traditional Arrows",
            "Purananuru & Kalithogai Commentaries on Pagazhi and Kanai",
            "Iron Age Megalithic Projectile Studies in Tamil Nadu"
        ],
        "content": "# Pagazhi Arrow Dynamic Spine & Helical Fletching Aerodynamics\n\nSangam poets distinguish between light reed darts (*ambu*), heavy iron-shod armor-piercers (*pagazhi*), and whistling/fire arrows (*kanai*), each governed by precise aero-ballistic ratios:\n\n**Ballistic & Aero-Structural Principles:**\n- **Dynamic Spine & Archer's Paradox**: When the bowstring accelerates the nock (*kuthai*) from rest at $>50\\text{ m/s}$, the shaft buckles laterally in its fundamental flexural mode, flexing around the thick wooden bow-handle without deflecting off-target, provided the reed/bamboo shaft's flexural stiffness (*spine*) matches the bow's peak draw force.\n- **Front-of-Center Balance & Helical Fletching (*Oozhi*)**: A heavy forged steel head shifts the center of mass $10-15\\%$ ahead of the geometric midpoint, while three split primary wing feathers from a same-side eagle or vulture (*kazhugu-iragu*) bound at a slight helical offset behind the nock generate aerodynamic torque, spinning the arrow like a rifle bullet."
    },
    {
        "slug": "concept-sabda-vedhi-acoustic-target-ranging-and-thumb-draw-release-kinematics",
        "category": "concept",
        "file": "concept-sabda-vedhi-acoustic-target-ranging-and-thumb-draw-release-kinematics.md",
        "name_en": "Viral-Seri Thumb-Draw Release Kinematics, Back-Tension Alignment & Acoustic Target Ranging",
        "name_ta": "விரல்செறி நாண் இழுப்பு இயக்கவியலும் ஓசை அறிந்து எய்யும் செவிப்புல இலக்குக் கோட்பாடும்",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1500,
        "thinai": "kurinji",
        "summary_en": "Neuromuscular and sensory biomechanics of ancient Tamil archery: drawing the bowstring to the ear or shoulder anchor using a thumb-ring (viral-seri) or deep finger lock, engaging rhomboid dorsal back-tension for a clean lateral release, and binaural acoustic localization for shooting through dense mountain foliage.",
        "summary_ta": "விரல்செறி அணிந்து காது வரை நாணினை இழுத்துத் தோள்பட்டை விசையால் அம்பு விடுக்கும் உடலியக்க நுட்பமும், அடர்ந்த குறிஞ்சிக் காட்டில் ஓசை மட்டுமே கொண்டு இலக்கை வீழ்த்தும் பயிற்சியும்.",
        "sources": [
            "Dhanurveda & South Indian Martial treatises",
            "Purananuru & Ahananuru Hunting Accounts",
            "Biomechanics of Traditional Thumb and Finger Draw Archery"
        ],
        "content": "# Thumb-Draw Release Kinematics & Acoustic Target Ranging\n\nClassical Tamil war and hunting treatises emphasize postural stillness, full-draw bone alignment, and multi-sensory target acquisition:\n\n**Biomechanical & Sensory Principles:**\n- **Full-Draw Anchor & Dorsal Release**: Archers stood in an oblique stance, extending the bow-arm locked against the deltoid while drawing the string back to the earlobe or collarbone (*chevi-ura வாங்குதல்*). Using a horn or iron thumb-ring (*viral-seri*) or a reinforced two-finger pinch against the nock, releasing the string cleanly with zero lateral pluck minimizes initial yaw oscillation.\n- **Binaural Acoustic Ranging in Montane Canopy**: In the mist-shrouded *Kurinji* forests of Kolli and Podhigai hills where visual line-of-sight is blocked by bamboo thickets, master hunters trained in *Oasai-Arithal* (*Sabda-Vedhi*)—triangulating range and elevation solely from the snap of a twig or intake of an animal's breath."
    },
    {
        "slug": "technology-bamboo-stave-heat-tillering-and-marul-hemp-sinew-bowstring-twisting",
        "category": "technology",
        "file": "technology-bamboo-stave-heat-tillering-and-marul-hemp-sinew-bowstring-twisting.md",
        "name_en": "Bamboo Stave Heat-Reflexing, Sinew-Bark Wrapping & Marul Hemp Bowstring Spinning",
        "name_ta": "மூங்கில் வில் தழல் பதப்படுத்துதல், நரம்புக் கட்டு மற்றும் மருள் நார் நாண் முறுக்கும் தொழில்நுட்பம்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "kurinji",
        "summary_en": "Bowyer manufacturing and string-making craft: seasoning winter-cut kal-moongil bamboo over hearth smoke, heat-tempering and reflexing limb tips over glowing charcoal with castor oil, binding intervals with wet rawhide/sinew (vil-kattu), and reverse-twisting non-stretch bowstrings (naan) from Sansevieria roxburghiana (marul) fiber and deer sinew.",
        "summary_ta": "கல்மூங்கிலைப் புகையில் உலர்த்தி ஆமணக்கு எண்ணெய் தடவித் தழலில் வளைத்து வில் செய்யும் நுட்பமும், மருள் (பெருங்குரும்பை) நாரும் மான் நரம்பும் சேர்த்து உறுதியான நாண் முறுக்கும் முறையும்.",
        "sources": [
            "Ethnobotany of Sansevieria roxburghiana (Bowstring Hemp) in South India",
            "Thurston Castes and Tribes of Southern India (Kuravar & Vedar Bowcraft)",
            "Traditional Indian Bowmaking Technology"
        ],
        "content": "# Bamboo Stave Heat-Tillering & Marul Hemp Bowstring Craft\n\nFabricating a moisture-resistant, high-velocity bow suited to the humid tropical hills of Tamil Nadu required specialized botanical processing and cordage engineering:\n\n**Bowyer & String-Maker Processes:**\n- **Smoke Seasoning & Thermal Tempering**: Mature *kal-moongil* culms harvested in the dry *Margazhi-Thai* season are split into staves and suspended above kitchen hearths for months so wood-smoke tars polymerize the lignin. The stave belly is rubbed with castor or *iluppai* oil and passed over glowing tamarind charcoal to heat-temper the cellulose fibers and set recurved nock tips, then bound at intervals with wet tendon collars (*kattu*).\n- **Marul Hemp & Sinew Bowstrings (*Vil-Naan*)**: True bowstring hemp (*Marul* or *Perunkurumbai*, *Sansevieria roxburghiana*) leaves are retted and scraped to extract long, low-creep sclerenchyma fibers. Three strands are reverse-plied (*puri-murukkal*) with shredded deer dorsal sinew (*maan-narambu*) and sealed with beeswax and pine/dammar resin (*kungiliyam*)."
    },
    {
        "slug": "technology-wootz-arrowhead-forging-charcoal-shaft-straightening-and-fletching",
        "category": "technology",
        "file": "technology-wootz-arrowhead-forging-charcoal-shaft-straightening-and-fletching.md",
        "name_en": "Wootz Steel Arrowhead Forging (Kollan-Azhal-Mugam), Reed Straightening & Sinew Fletching",
        "name_ta": "எஃகு அம்பு முனை கொல்லுலை வார்ப்பு, நாணல் தண்டு நிமிர்த்துதல் மற்றும் இறகுக் கட்டு நுட்பம்",
        "era": "Iron Age to Medieval Era",
        "year_start": -600,
        "year_end": 1600,
        "thinai": "kurinji",
        "summary_en": "Arrowsmithing technology combining metallurgy and woodworking: forging high-carbon steel warheads (barbed leaf-blades, crescent ardhachandra cutters, and four-sided armor-piercing bodkins) quenched in oil/water, heat-straightening nanal reed and bamboo shafts in grooved soapstone blocks, and cementing tangs with lac resin (arakku).",
        "summary_ta": "கொல்லன் உலையில் எஃகு இரும்பினால் இலை வடிவ, பிறை வடிவ மற்றும் கவசம் துளைக்கும் அம்பு முனைகளை அடித்துத் தண்ணீரில் தோய்த்துக் காய்ச்சும் நுட்பமும், அரக்குக் கொண்டு கணையில் பொருத்தும் முறையும்.",
        "sources": [
            "Adichanallur & Kodumanal Iron Age Arrowhead Metallurgy",
            "Purananuru 152 (Kollan Azhal-Mugam Thiruthiya Pagazhi)",
            "South Indian Armoury Collections (Government Museum Chennai)"
        ],
        "content": "# Wootz Arrowhead Forging & Shaft Fletching Technology\n\nIn *Purananuru* 152, Vanparanar specifically praises the blacksmith who forged Valvil Ori's arrowhead in the roaring furnace (*\"கொல்லன் அழல்முகம் திருத்திய பகழி\"*):\n\n**Metallurgical & Assembly Craft:**\n- **Specialized Warhead Geometries**: Iron Age and medieval Tamil blacksmiths (*Kollan*) forged both tanged (*ஆணி முனை*) and hollow-socketed (*குழாய் முனை*) arrowheads from high-carbon steel: barbed broadleaf heads (*ilai-ambu*) causing hemorrhage in big game, wide crescent blades (*pirai-ambu* / *ardhachandra*) for severing ropes and tendons, and heavy square-sectioned pyramidal bodkins (*konai-pagazhi*) differentially quenched to punch through elephant hides and mail coats.\n- **Shaft Straightening & Lac Hafting**: Seasoned *nanal* reed or thin bamboo shafts are heated over embers, trued inside grooved steatite straightening stones, notched at the rear, and hafted to the iron tang using melted shellac resin (*arakku*) reinforced with fine wet sinew wrapping."
    },
    {
        "slug": "artifact-ambaraa-thooni-cylindrical-quivers-viral-seri-thumb-rings-and-kai-kavacham-bracers",
        "category": "artifact",
        "file": "artifact-ambaraa-thooni-cylindrical-quivers-viral-seri-thumb-rings-and-kai-kavacham-bracers.md",
        "name_en": "Ambaraa-Thooni Cylindrical Quivers, Viral-Seri Thumb-Rings, Kai-Kavacham Bracers & Megalithic Points",
        "name_ta": "அம்பறாத்தூணி அம்புக் கூடுகள், விரல்செறி மோதிரம், கைக்கவசம் மற்றும் பெருங்கற்கால இரும்பு அம்பு முனைகள்",
        "era": "Iron Age to Nayak Era",
        "year_start": -800,
        "year_end": 1700,
        "thinai": "kurinji",
        "summary_en": "Archaeological and historical archery artifacts of Tamil Nadu: Iron Age tanged and barbed arrowheads excavated at Adichanallur, Kodumanal, and Porunthal, cylindrical leather-and-bamboo back quivers (thooni / ambaraa-thooni), horn and iron thumb-draw rings (viral-seri), and quilted leather wrist-guards (kai-kavacham).",
        "summary_ta": "ஆதிச்சநல்லூர், கொடுமணல் அகழாய்வுகளில் கிடைத்த இரும்பு அம்பு முனைகள், தோல் மற்றும் மூங்கிலால் ஆன அம்பறாத்தூணி, நாண் இழுக்கும் விரல்செறி மற்றும் மணிக்கட்டுக் கைக்கவசம்.",
        "sources": [
            "Archaeological Survey of India: Adichanallur & Kodumanal Excavations",
            "Hero-Stone (Nadukal) Iconography of Chengam & Dharmapuri",
            "Government Museum Chennai Arms & Armour Gallery"
        ],
        "content": "# Ambaraa-Thooni Quivers, Thumb-Rings, Bracers & Megalithic Points\n\nMaterial evidence of ancient Tamil archery spans over two millennia of megalithic burials, sculpted hero-stones (*nadukal*), and temple armouries:\n\n**Archaeological & Historical Artifacts:**\n- **Megalithic Iron Arrowheads**: Excavations at Adichanallur, Kodumanal, and Porunthal have yielded hundreds of wrought-iron and high-carbon steel arrowheads ($6-14\\text{ cm}$ long) with long tangs and flared barbs buried beside warrior urns and cists dating from $800\\text{ BCE}$ to $200\\text{ CE}$.\n- **Ambaraa-Thooni Quivers & Protective Gear**: Chengam and Dharmapuri *nadukal* hero-stones depict archers wearing a cylindrical bamboo-core, hide-sheathed quiver (*thooni* or *ambaraa-thooni*) slung diagonally across the right shoulder holding $30-40$ arrows fletch-up, paired with a thick rawhide forearm bracer (*kai-kavacham*) strapped to the left wrist and a bevelled horn thumb-ring (*viral-seri*)."
    },
    {
        "slug": "artifact-kurinji-unda-vil-double-stringed-pellet-bows-and-clay-sling-bullets",
        "category": "artifact",
        "file": "artifact-kurinji-unda-vil-double-stringed-pellet-bows-and-clay-sling-bullets.md",
        "name_en": "Kurinji Unda-Vil Double-Stringed Pellet-Bows, Spacer Blocks & Baked-Clay Millet-Guard Bullets",
        "name_ta": "குறிஞ்சி உண்டை வில் (இரட்டை நாண் கவண் வில்), சுடுமண் உண்டைகள் மற்றும் தினைப்புனக் காவல் கருவிகள்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 1950,
        "thinai": "kurinji",
        "summary_en": "Specialized non-arrow projectile bow of the Tamil hills and farmlands: the double-stringed bamboo pellet-bow (unda-vil / undai-vil) fitted with a wooden string-spacer bridge and woven mid-string pouch for launching sun-baked clay balls (mann-undai) or pebbles to ward off parrots from ripening thinai millet fields.",
        "summary_ta": "தினைப்புனம் காக்கும் குறிஞ்சி நிலப் பெண்களும் வேடர்களும் கிளிகளை விரட்டப் பயன்படுத்திய இரட்டை நாண் கொண்ட மூங்கில் உண்டை வில் மற்றும் சுடுமண் உருண்டைகள்.",
        "sources": [
            "Kurinji-Pattu & Narrinai Commentaries on Thinai-Punam Guarding",
            "Henry Balfour The Origin and Distribution of the Pellet-Bow",
            "Madras Government Museum Ethnographic Collection"
        ],
        "content": "# Kurinji Unda-Vil Double-Stringed Pellet-Bows & Clay Bullets\n\nAlongside war bows shooting feathered shafts, rural and montane Tamil communities extensively used the ingenious double-stringed pellet-bow (*Unda-Vil* or *Undai-Vil*):\n\n**Mechanical Design & Agrarian Role:**\n- **Twin-String & Spacer-Block Architecture**: A flexible split-bamboo stave is strung with two parallel hemp cords held $3-4\\text{ cm}$ apart by a small rectangular wooden strut (*kattai*) tied near the upper nock. At the center of the twin strings, a small diamond-shaped net pouch (*thottil* / *தொட்டில்*) is woven to cradle a spherical projectile.\n- **Thumb-Twist Clearance & Thinai-Punam Guarding**: Upon release, the archer imparts a slight wrist twist so the clay pellet passes cleanly between the twin strings without striking the wooden bow-handle. In *Kurinji* poetry, young women perched on high bamboo platforms (*paran* / *idhan*) used pellet-bows and slings (*kavan*) with baked clay balls (*mann-undai*) to startle flocks of parrots raiding golden *thinai* (foxtail millet) ears."
    },
    {
        "slug": "institution-kuravar-hill-archer-clans-vil-pallikoodam-academies-and-valvil-ori-vizha",
        "category": "institution",
        "file": "institution-kuravar-hill-archer-clans-vil-pallikoodam-academies-and-valvil-ori-vizha.md",
        "name_en": "Kuravar Hill-Archer Clans, Chola Villalar Regiments, Vil-Pallikoodam Schools & Valvil Ori Vizha",
        "name_ta": "குறவர்-வேடர் வில்லாளர் குலங்கள், சோழர் வில்லிகள் படைப்பிரிவு, வில் பள்ளிக்கூடம் மற்றும் வல்வில் ஓரி விழா",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Institutional history of Tamil archery: indigenous Kuravar, Vedar, and Malayali hill-archer clans, organized Villalar / Villigal bow-infantry regiments and Vil-Pallikoodam training grounds endowed in Chola and Pandya inscriptions, and the annual Aadi Valvil Ori Vizha festival in Kolli Hills.",
        "summary_ta": "குறிஞ்சி நிலக் குறவர் மற்றும் மலையாளி வில்லாளர் மரபு, சோழர்-பாண்டியர் காலத்து 'வில்லிகள்' படைப்பிரிவு, வில் பயிற்றுவித்த வில் பள்ளிக்கூடங்கள் மற்றும் ஆடி மாத வல்வில் ஓரி விழா.",
        "sources": [
            "South Indian Inscriptions (Chola Villigal Regiments & Silambam/Archery Grants)",
            "Salem & Namakkal District Gazetteers (Kolli Hills Malayali Traditions)",
            "Tamil Nadu Tourism & Cultural Department Valvil Ori Festival Archives"
        ],
        "content": "# Kuravar Hill-Archer Clans, Villalar Regiments & Valvil Ori Vizha\n\nAcross two millennia, Tamil archery was sustained by both highland tribal brotherhoods and state-endowed military academies:\n\n**Military & Cultural Institutions:**\n- **Villigal Regiments & Vil-Pallikoodam**: Chola and Pandya inscriptions record specialized archer corps (*Villigal* or *Perun-Villalar*) within the standing army (*Kakkai-Padai* and *Moonru-Kai Mahasenai*), trained at village martial grounds (*Vil-Pallikoodam* or *Ilakku-Mandapam*) supported by tax-free *virabhoga* land grants.\n- **Kurinji Clans & Aadi Valvil Ori Vizha**: In the Kolli, Kalrayan, and Pachamalai hills, hereditary *Kuravar* and *Malayali* hunters preserved bamboo bowyer craft for forest defense and ritual hunts (*Pari-Vettai*). Every year on the 17th and 18th days of the Tamil month of *Aadi* (early August), the historic *Valvil Ori Vizha* is celebrated at Semmedu in the Kolli Hills with traditional archery competitions and bardic commemorations."
    },
    {
        "slug": "place-kolli-hills-valvil-ori-ancient-kurinji-archery-and-bowyer-haven",
        "category": "place",
        "file": "place-kolli-hills-valvil-ori-ancient-kurinji-archery-and-bowyer-haven.md",
        "name_en": "Kolli Hills (Kollimalai): Valvil Ori's Ancient Kurinji Stronghold, Bamboo Bowyer & Archery Haven",
        "name_ta": "கொல்லிமலை - வல்வில் ஓரியின் பண்டைய குறிஞ்சித் தளம், கல்மூங்கில் வில் மற்றும் வில்வித்தை மரபு மையம்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Highland massif of Kolli Hills (Kollimalai, lat 11.2480, lng 78.3380, thinai: kurinji) in Namakkal district of the Eastern Ghats, the celebrated Sangam domain of the archer-philanthropist chieftain Valvil Ori, renowned for its dense kal-moongil bamboo forests, Arapaleeswarar shrine, and living hill-archery heritage.",
        "summary_ta": "நாமக்கல் மாவட்டத்தின் கிழக்குத் தொடர்ச்சி மலையில் அமைந்த கொல்லிமலை (அட்சரேகை 11.2480, தீர்க்கரேகை 78.3380): கடையேழு வள்ளல்களில் ஒருவரான வல்வில் ஓரியின் குறிஞ்சி நிலக் கோட்டை மற்றும் வில்வித்தைத் தளம்.",
        "sources": [
            "Purananuru & Kuruntokai (Kolli Hills & Valvil Ori Poems)",
            "Salem District Manual (Le Fanu 1883: Kollimalai)",
            "Botanical & Ethnographic Survey of Kolli Hills, Namakkal"
        ],
        "content": "# Kolli Hills (Kollimalai): Valvil Ori's Kurinji Archery Haven\n\nRising abruptly to $1300\\text{ m}$ elevation at latitude $11.2480^\\circ\\text{ N}$, longitude $78.3380^\\circ\\text{ E}$ in Namakkal district, the *Kolli Hills* (*Kollimalai*) massif is the most celebrated *Kurinji* archery landscape in classical Tamil literature:\n\n**Ecological & Historical Significance:**\n- **Stronghold of Valvil Ori & Kari**: Guarded by seventy hairpin bends, precipitous charnockite scarps, and the roaring *Agaya Gangai* waterfall beside the ancient *Arapaleeswarar* temple, Kollimalai was ruled in the Sangam age by `Valvil Ori`, one of the Seven Last Great Patrons (*Kadai-Ezhu Vallal*), who gifted its fertile mountain valleys to the *Koothar* and *Panar* bards before the territory passed to the Cheras and Malayaman Tirumudikkari.\n- **Botanical Bowyer Sanctuary**: The mist-fed shola slopes of Kollimalai abound in solid *Dendrocalamus strictus* (*kal-moongil*), *Pterocarpus marsupium* (*vengai*), and wild *Sansevieria* bowstring hemp, providing every raw material for indigenous *kodun-cil* and *unda-vil* bowcraft."
    }
]

EDGES = [
    [
        "text-purananuru-and-sirupanarruppadai-on-valvil-ori-and-chera-vil-kodi-archery",
        "documents",
        "technology-wootz-arrowhead-forging-charcoal-shaft-straightening-and-fletching",
        "material_culture",
        "Sangam Era",
        "Purananuru 152 documents blacksmith-forged iron pagazhi arrowheads capable of piercing five forest beasts in a single shot.",
        "Purananuru 152"
    ],
    [
        "concept-kal-moongil-bamboo-flexural-strain-energy-and-kodun-cil-stave-mechanics",
        "governs",
        "technology-bamboo-stave-heat-tillering-and-marul-hemp-sinew-bowstring-twisting",
        "material_culture",
        "Iron Age to Modern Era",
        "Flexural strain-energy storage in functionally graded solid bamboo governs stave heat-tillering and limb taper geometry.",
        "Bamboo Self-Bow Mechanics"
    ],
    [
        "concept-pagazhi-arrow-spine-paradox-and-helical-feather-fletching-aerodynamics",
        "guides",
        "technology-wootz-arrowhead-forging-charcoal-shaft-straightening-and-fletching",
        "material_culture",
        "Iron Age to Medieval Era",
        "Dynamic spine matching and front-of-center aerodynamic stability guide arrow shaft straightening and helical three-vane eagle fletching.",
        "Arrow Ballistics Studies"
    ],
    [
        "concept-sabda-vedhi-acoustic-target-ranging-and-thumb-draw-release-kinematics",
        "utilizes",
        "artifact-ambaraa-thooni-cylindrical-quivers-viral-seri-thumb-rings-and-kai-kavacham-bracers",
        "material_culture",
        "Sangam to Medieval Era",
        "Full-draw dorsal release kinematics utilize horn/iron viral-seri thumb rings and rawhide kai-kavacham wrist bracers.",
        "Chengam Hero-Stone Iconography"
    ],
    [
        "technology-bamboo-stave-heat-tillering-and-marul-hemp-sinew-bowstring-twisting",
        "fabricates",
        "artifact-kurinji-unda-vil-double-stringed-pellet-bows-and-clay-sling-bullets",
        "material_culture",
        "Sangam to Modern Era",
        "Split kal-moongil stave shaping and twin marul-hemp stringing fabricate the double-stringed Kurinji unda-vil pellet-bow.",
        "Balfour Pellet-Bow Studies"
    ],
    [
        "technology-wootz-arrowhead-forging-charcoal-shaft-straightening-and-fletching",
        "produces",
        "artifact-ambaraa-thooni-cylindrical-quivers-viral-seri-thumb-rings-and-kai-kavacham-bracers",
        "material_culture",
        "Iron Age to Nayak Era",
        "Iron Age and medieval Tamil arrowsmiths produced the tanged and barbed steel arrowheads stored in cylindrical ambaraa-thooni quivers.",
        "Adichanallur & Kodumanal Excavations"
    ],
    [
        "institution-kuravar-hill-archer-clans-vil-pallikoodam-academies-and-valvil-ori-vizha",
        "transmits",
        "concept-sabda-vedhi-acoustic-target-ranging-and-thumb-draw-release-kinematics",
        "material_culture",
        "Sangam to Modern Era",
        "Kuravar hill-archer clans and royal Vil-Pallikoodam academies transmit full-draw release biomechanics and forest acoustic target ranging.",
        "South Indian Inscriptions"
    ],
    [
        "institution-kuravar-hill-archer-clans-vil-pallikoodam-academies-and-valvil-ori-vizha",
        "deploys",
        "artifact-kurinji-unda-vil-double-stringed-pellet-bows-and-clay-sling-bullets",
        "material_culture",
        "Sangam to Modern Era",
        "Kurinji highland communities deploy double-stringed unda-vil pellet-bows on elevated paran watchtowers to protect thinai millet harvests.",
        "Kurinji-Pattu & Narrinai"
    ],
    [
        "place-kolli-hills-valvil-ori-ancient-kurinji-archery-and-bowyer-haven",
        "hosts",
        "institution-kuravar-hill-archer-clans-vil-pallikoodam-academies-and-valvil-ori-vizha",
        "material_culture",
        "Sangam to Modern Era",
        "Kolli Hills in Namakkal district hosts indigenous hill-archery traditions and the annual Aadi Valvil Ori Vizha festival.",
        "Salem District Manual"
    ],
    [
        "text-purananuru-and-sirupanarruppadai-on-valvil-ori-and-chera-vil-kodi-archery",
        "celebrates",
        "place-kolli-hills-valvil-ori-ancient-kurinji-archery-and-bowyer-haven",
        "material_culture",
        "Sangam Era",
        "Sangam poems in Purananuru and Sirupanarruppadai celebrate Kolli Hills as the sovereign domain of the master-archer patron Valvil Ori.",
        "Purananuru & Sirupanarruppadai"
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
