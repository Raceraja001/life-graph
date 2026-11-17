#!/usr/bin/env python3
"""
Harvester: Batch 45 - Ancient Tamil Stringed Harp Luthier Craft, Yazh Organology & Panar Modal Acoustics
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
        "slug": "text-arruppadai-and-silappadikaram-on-yazh-organology-and-panar-bards",
        "category": "text",
        "file": "text-arruppadai-and-silappadikaram-on-yazh-organology-and-panar-bards.md",
        "name_en": "Arruppadai & Silappadikaram Anatomy of the Yazh Harp and Panar Performance",
        "name_ta": "ஆற்றுப்படை மற்றும் சிலப்பதிகார யாழ் உறுப்பு இலக்கணமும் பாணர் இசை மரபும்",
        "era": "Sangam to Post-Sangam Era",
        "year_start": -300,
        "year_end": 500,
        "thinai": "marutham",
        "summary_en": "Classical Tamil poetic accounts in Porunararruppadai, Sirupanarruppadai, Perumpanarruppadai, and Silappadikaram (Arangerrukathai and Kanalvari) describing the anatomical parts, stringing, flaw-testing, and modal tuning of the arched harp (Yazh).",
        "summary_ta": "பொருநராற்றுப்படை, சிறுபாணாற்றுப்படை, பெரும்பாணாற்றுப்படை மற்றும் சிலப்பதிகாரத்தின் அரங்கேற்றுகாதை, கானல்வரியில் விவரிக்கப்படும் யாழின் உறுப்புகள், நரம்புக் கட்டு மற்றும் பண்ணிசை மரபு.",
        "sources": [
            "Porunararruppadai",
            "Sirupanarruppadai",
            "Perumpanarruppadai",
            "Silappadikaram Arangerrukathai",
            "Vipulananda Adigal Yaazh Nool"
        ],
        "content": "# Arruppadai & Silappadikaram on Yazh Organology\n\nThe Sangam *Arruppadai* (guide poems) and *Silappadikaram* preserve the most detailed organological descriptions of the ancient arched harp (*Yazh*) in South Asian literature:\n\n**Poetic & Technical Descriptions:**\n- **Anatomical Similes**: The *Arruppadai* poems compare each structural member of the *Periyazh* and *Seeriyazh* to natural forms: the hollow boat-shaped resonator (*pathar*) to a deer's hoofprint, the stitched skin belly (*porvai*) to the golden-red abdomen of a pregnant woman, the sound-hole (*vattu*) to a crab's eye, the curved neck (*kodu*) to a black serpent, and the leather tuning rings (*thivavu*) to braided bracelets.\n- **Silappadikaram Arangerrukathai & Kanalvari**: The epic details the *Yazh-Asiriyan* (master harpist) testing the 14-string *Sakodayazh* for structural defects (*sempagai*, *arppu*, *koodam*, *adhirvu*) before tuning the seven primary notes (*kural* to *tharam*) and shifting tonic modes (*palai*)."
    },
    {
        "slug": "concept-kumizh-and-vengai-soundwood-seasoning-and-pathar-resonator-acoustics",
        "category": "concept",
        "file": "concept-kumizh-and-vengai-soundwood-seasoning-and-pathar-resonator-acoustics.md",
        "name_en": "Kumizh & Vengai Soundwood Seasoning, Pathar Cavity Resonance & Membrane Coupling",
        "name_ta": "குமிழ் மற்றும் வேங்கை மரப் பதப்படுத்துதல், பத்தர் ஒலிப்பெட்டியின் அதிர்வலை இயற்பியல்",
        "era": "Iron Age to Medieval Era",
        "year_start": -500,
        "year_end": 1200,
        "thinai": "kurinji",
        "summary_en": "Materials science and acoustic mechanics of Yazh luthiery: selecting hillside Gmelina arborea (kumizh) and Pterocarpus marsupium (vengai) timber, shade seasoning to prevent warping, and coupling a stretched hide soundboard (porvai) over the hollowed boat-shaped resonator (pathar).",
        "summary_ta": "யாழ் செய்யப் பயன்படும் குமிழ் மற்றும் வேங்கை மரங்களைத் தேர்ந்தெடுத்து நிழலில் உலர்த்தும் முறை, குடைந்து செய்யப்பட்ட பத்தர் மரப் பெட்டியின் மேல் போர்வைத் தோல் போர்த்தும் ஒலி இயற்பியல்.",
        "sources": [
            "Vipulananda Adigal Yaazh Nool",
            "Abraham Pandithar Karunamirtha Sagaram",
            "Indian Musical Instruments Organology Studies"
        ],
        "content": "# Soundwood Seasoning & Pathar Resonator Acoustics\n\nClassical Tamil treatises specify strict botanical and ecological criteria for selecting timber to carve the *Yazh* resonator (*pathar*) and curved neck (*kodu*):\n\n**Timber & Acoustic Physics:**\n- **Botanical Selection**: Luthiers favored *Kumizh* (*Gmelina arborea*, medium density, uniform grain, low damping coefficient) and *Vengai* (*Pterocarpus marsupium*, dense heartwood for the tensile curved neck). Trees growing on rocky, sun-exposed hill slopes were preferred over waterlogged riverbanks whose spongy wood produced dull, buzzing tones.\n- **Shade Seasoning**: Felled logs were buried in dry sand and cured in shaded lofts for a full year to equalize moisture without radial checking.\n- **Membrane-Cavity Coupling**: Unlike wooden-bellied lutes, the *Yazh* stretched a thin, dehaired goat or deer hide (*porvai*) stitched down the center over the hollow wooden trough, creating high acoustic radiation efficiency for plucked gut strings."
    },
    {
        "slug": "technology-yazh-carving-porvai-parchment-stitching-and-thivavu-tuning-rings",
        "category": "technology",
        "file": "technology-yazh-carving-porvai-parchment-stitching-and-thivavu-tuning-rings.md",
        "name_en": "Hollow Pathar Gouging, Porvai Parchment Stitching & Thivavu Leather Tuning Rings",
        "name_ta": "பத்தர் மரக் குடைவு, போர்வைத் தோல் தையல் மற்றும் திவவு வார்க்கட்டுச் சுருதி நுட்பம்",
        "era": "Sangam to Early Medieval Era",
        "year_start": -300,
        "year_end": 900,
        "thinai": "marutham",
        "summary_en": "The craft sequence of constructing an arched Tamil harp: gouging the thin-walled boat trough (pathar), mortising the curved ebony or vengai stem (kodu), lacing the wet parchment belly (porvai), and winding sliding leather tension collars (thivavu) for fine pitch adjustment.",
        "summary_ta": "யாழ் உருவாக்கும் தொழில்நுட்ப வரிசை: பத்தர் மரக் குடைவு, வளைந்த கோடு பொருத்துதல், போர்வைத் தோல் தைத்தல் மற்றும் சுருதி கூட்டப் பயன்படும் திவவு தோல் வளையங்களைக் கட்டுதல்.",
        "sources": [
            "Vipulananda Adigal Yaazh Nool",
            "Porunararruppadai Commentaries",
            "South Indian Temple Sculpture Iconography"
        ],
        "content": "# Yazh Carving, Parchment Stitching & Thivavu Tuning\n\nConstructing a functional arched harp required precise joinery and tension balancing so the curved neck would not buckle under cumulative string load:\n\n**Luthier Construction Sequence:**\n1. **Pathar Trough Gouging**: Using curved iron adzes and spoon gouges, the luthier hollowed a seasoned *kumizh* block into a thin-walled, boat-shaped shell (*pathar*) with uniform wall thickness.\n2. **Porvai Hide Stretching**: Two matched halves of thin, alum-tanned deer or goat skin (*porvai*) were stretched wet across the trough mouth and stitched down the midline with fine gut or pin-head wooden pegs (*aanikkai*) resembling a line of tiny crab eyes.\n3. **Thivavu Friction Rings**: Each gut or twisted-silk string (*narambu*) rose from the internal string-bar (*ul-karpu*) through the parchment belly to a braided leather collar (*thivavu*) wrapped tightly around the curved neck (*kodu*). Rotating or sliding the *thivavu* adjusted string tension and pitch."
    },
    {
        "slug": "artifact-periyazh-makarayazh-sakodayazh-and-seeriyazh-harp-typology",
        "category": "artifact",
        "file": "artifact-periyazh-makarayazh-sakodayazh-and-seeriyazh-harp-typology.md",
        "name_en": "Periyazh, Makarayazh, Sakodayazh & Seeriyazh Classical Harp Typology",
        "name_ta": "பேரியாழ், மகரயாழ், சகோடயாழ் மற்றும் சீறியாழ் ஆகிய நால்வகை யாழ் கருவிகள்",
        "era": "Sangam to Early Medieval Era",
        "year_start": -300,
        "year_end": 900,
        "thinai": "marutham",
        "summary_en": "The four canonical classes of ancient Tamil arched harps documented in literary commentaries and temple relief sculptures: the 21-string concert Periyazh, the 19-string zoomorphic Makarayazh, the 14-string modal Sakodayazh, and the portable 7-string Seeriyazh.",
        "summary_ta": "தமிழ் இசை வரலாற்றில் குறிப்பிடப்படும் நால்வகை யாழ்கள்: 21 நரம்புடைய பேரியாழ், 19 நரம்புடைய மகரயாழ், 14 நரம்புடைய சகோடயாழ் மற்றும் 7 நரம்புடைய சிறிய சீறியாழ்.",
        "sources": [
            "Silappadikaram Adiyarkkunallar Commentary",
            "Vipulananda Adigal Yaazh Nool",
            "Pallava and Chola Temple Relief Iconography"
        ],
        "content": "# Classical Four-Fold Yazh Typology\n\nClassical Tamil musicological commentaries (*Adiyarkkunallar* on *Silappadikaram*) and sculptural reliefs classify the *Yazh* family into four principal instruments:\n\n**Organological Classification:**\n- **Periyazh (21 Strings)**: The grand three-octave concert harp spanning the low (*melivu*), middle (*samam*), and high (*valivu*) registers, carried by senior *Perumpanar* bards.\n- **Makarayazh (19 Strings)**: An ornate court harp whose resonator or neck terminal was sculpted in the form of a mythical *Makara* sea-creature, noted in Sangam accounts as reflecting Greco-Roman (*Yavana*) and courtly design contacts.\n- **Sakodayazh (14 Strings)**: A two-octave chamber harp specifically favored for modal transpositions (*palai*) and dance accompaniment in *Silappadikaram*.\n- **Seeriyazh (7 Strings)**: A compact, lightweight single-octave traveling harp slung across the shoulder of wandering *Sirupanar* minstrels."
    },
    {
        "slug": "concept-vattappalai-cycle-of-fifths-and-kural-thiribu-modal-transposition",
        "category": "concept",
        "file": "concept-vattappalai-cycle-of-fifths-and-kural-thiribu-modal-transposition.md",
        "name_en": "Vattappalai Cycle of Fifths, Seven Swara Ratios & Kural-Thiribu Modal Shifting",
        "name_ta": "வட்டப்பாலை இளி-குரல் சுழற்சி, ஏழிசை விகிதங்கள் மற்றும் குரல் திரிபுப் பாலைப் பிறப்பு",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1200,
        "thinai": "marutham",
        "summary_en": "Acoustic mathematics of ancient Tamil Pann music: generating the seven foundational pitches (Kural, Thuttam, Kaikkilai, Uzhai, Ili, Vilari, Tharam) through the cycle of consonant fifths and fourths (Kural-Ili samvadam) on the Vattappalai zodiacal circle, and deriving heptatonic modes (Palai) via tonic shift (Kural-Thiribu).",
        "summary_ta": "பண்டைய தமிழிசைக் கணிதம்: குரல்-இளி இயைபு முறையில் வட்டப்பாலையில் ஏழு சுரங்களை உருவாக்குதல் மற்றும் குரல் திரிபு முறையில் பாலைப் பண்களைப் பிறப்பித்தல்.",
        "sources": [
            "Silappadikaram Ay்ச்சியர் குரவை & Arangerrukathai",
            "Abraham Pandithar Karunamirtha Sagaram",
            "Vipulananda Adigal Yaazh Nool"
        ],
        "content": "# Vattappalai Cycle of Fifths & Kural-Thiribu Modal Shifting\n\nBecause the open-stringed *Yazh* had no frets, playing in different scales required a rigorous mathematical system of tuning and modal transposition:\n\n**Mathematical Acoustics:**\n- **The Seven Notes (*Ezhisai*)**: Named *Kural, Thuttam, Kaikkilai, Uzhai, Ili, Vilari,* and *Tharam*, arranged around a 12-division circular diagram (*Vattappalai*).\n- **Consonant Fifths Generation (*Kural-Ili Method*)**: Strings were tuned by ear using pure just-intonation fifths ($3:2$ frequency ratio, *Kural* to *Ili*) and fourths ($4:3$, *Kural* to *Uzhai*), stepping around the twelve positions to establish the primordial scale (*Sempalai*, corresponding to the Harikambhoji interval pattern).\n- **Tonic Shift (*Kural-Thiribu / கிரகபேதம்*)**: Without retuning every string between songs, the harpist shifted the tonal center (*Kural*) to successive strings on the harp, generating the seven major *Palai* modes (*Sempalai, Padumalaippalai, Sevazhippalai, Arumpalai, Kodippalai, Vilarippalai, Merchemppalai*)."
    },
    {
        "slug": "institution-panar-and-viraliyar-bardic-guilds-and-royal-arruppadai-patronage",
        "category": "institution",
        "file": "institution-panar-and-viraliyar-bardic-guilds-and-royal-arruppadai-patronage.md",
        "name_en": "Panar & Viraliyar Bardic Guilds, Touring Troupes & Royal Arruppadai Patronage",
        "name_ta": "பாணர் மற்றும் விறலியர் இசைக் குழுக்கள், ஆற்றுப்படைப் புரவலர் மரபு மற்றும் கோயில் இசை மன்றம்",
        "era": "Sangam to Chola Era",
        "year_start": -300,
        "year_end": 1200,
        "thinai": "marutham",
        "summary_en": "The social and institutional organization of classical Tamil musicians: itinerant family troupes of Panar (harpists and vocalists), Porunar (martial drummers), and Viraliyar (dancers) who transmitted modal Pann repertory across courts, battlefields, and later temple endowments (Thevaram Vinnappam).",
        "summary_ta": "சங்க காலம் முதல் சோழர் காலம் வரை பண்ணிசை மரபைப் பேணிய பாணர், பொருநர் மற்றும் விறலியர் கலைக் குழுக்கள், அரசர்களின் பொற்றாமரைப் பரிசில் மற்றும் கோயில் திருப்பதிகக் காணிகள்.",
        "sources": [
            "Sirupanarruppadai",
            "Perumpanarruppadai",
            "Purananuru",
            "Chola Temple Music Inscriptions"
        ],
        "content": "# Panar & Viraliyar Bardic Guilds\n\nThe preservation of *Yazh* luthiery and *Pann* music rested upon hereditary, mobile performance lineages:\n\n**Guild Structure & Patronage:**\n- **Sub-Specializations**: Sangam literature distinguishes *isaippanar* (vocal-harp accompanists), *yazhppanar* (solo harp virtuosos subdivided into *Perumpanar* and *Sirupanar* by instrument size), and *mandaippanar* (mendicant singers), traveling alongside female *Viraliyar* dancers and percussionists carrying the *tannumai* and *aguli* drums.\n- **Arruppadai Gift Economy**: Returning bards guided impoverished fellow troupes along forest paths to generous chieftains (*Vallals*) and monarchs, who awarded gold lotus emblems (*pon-thamarai*), fine muslins, and land grants.\n- **Bhakti & Temple Transition**: By the Pallava-Chola era, *Panar* lineages (celebrated through Saint Tirunilakanta Yazhppanar, who accompanied Sambandar's *Thevaram* hymns on the *Yazh*) transitioned into endowed temple musicians."
    },
    {
        "slug": "technology-narambu-gut-and-twisted-silk-string-spinning-and-wax-polishing",
        "category": "technology",
        "file": "technology-narambu-gut-and-twisted-silk-string-spinning-and-wax-polishing.md",
        "name_en": "Narambu Gut & Twisted-Silk String Spinning, Gauge Calibration & Beeswax Polishing",
        "name_ta": "நரம்பு முறுக்குதல், தடிமன் அளவுப்படுத்தல் மற்றும் தேன்மெழுகு மெருகேற்றும் நுட்பம்",
        "era": "Sangam to Medieval Era",
        "year_start": -300,
        "year_end": 1200,
        "thinai": "marutham",
        "summary_en": "The craft of manufacturing resonant Yazh harp strings (narambu): cleaning and alkaline-soaking animal sinew/gut or plying multi-filament raw silk and plant fibers, wet-twisting under calibrated stone weights, and burnishing with beeswax and oil to prevent fraying.",
        "summary_ta": "யாழ் நரம்பு தயாரிப்பு முறை: விலங்கு தசைநார் அல்லது முறுக்கிய பட்டு மற்றும் தாவர நார்களைச் சுத்தம் செய்து, சம எடைக் கற்கள் கட்டி முறுக்கி, தேன்மெழுகு தடவிப் பளபளப்பாக்கும் நுட்பம்.",
        "sources": [
            "Silappadikaram Arangerrukathai Commentary",
            "Vipulananda Adigal Yaazh Nool",
            "Traditional South Indian Stringed Instrument Craft"
        ],
        "content": "# Narambu String Spinning & Beeswax Calibration\n\nA harp's tonal purity and intonation stability depend on uniform mass per unit length along every string (*narambu*):\n\n**String Fabrication Process:**\n1. **Fiber & Sinew Preparation**: Historical commentaries mention both animal gut/sinew (*narambu*) and tightly spun silk or vegetal cords (*marul*). Strips were scraped clean of fat, soaked in mild wood-ash lye, washed in running water, and sun-bleached to golden translucency (`பொன்னுருக்கன்ன நரம்பு` — strings resembling molten gold).\n2. **Weighted Wet Twisting**: Multiple strands were twisted together on a hook while suspended under calibrated stone weights so that bass (*melivu*), middle (*samam*), and treble (*valivu*) strings achieved graduated diameters.\n3. **Wax & Oil Burnishing**: Cured strings were rubbed vigorously with purified beeswax and sesame oil using a smooth bone or shell pad, sealing out atmospheric humidity that would otherwise cause pitch drift during performance."
    },
    {
        "slug": "place-avudaiyarkoil-ancient-panar-yazh-and-acoustic-haven",
        "category": "place",
        "file": "place-avudaiyarkoil-ancient-panar-yazh-and-acoustic-haven.md",
        "name_en": "Avudaiyarkoil: Ancient Thirupperunthurai Panar Acoustic Haven & Stone-Carved Musical Citadel",
        "name_ta": "ஆவுடையார்கோயில் - பண்டைய திருப்பெருந்துறை பாணர் யாழிசைத் தளம் மற்றும் ஒலி அதிர்வுக் கற்கோயில்",
        "era": "Early Medieval to Modern Era",
        "year_start": 700,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Historic sacred town (Thirupperunthurai) in Pudukkottai district, celebrated in Shaiva Bhakti literature and architectural acoustics for its monolithic stone-ribbed mandapa eaves, sculptural depictions of Panar harpists and dancers, and unbroken Pann liturgical singing traditions.",
        "summary_ta": "புதுக்கோட்டை மாவட்டத்தில் அமைந்துள்ள திருப்பெருந்துறை (ஆவுடையார்கோயில்): பண்ணிசை மற்றும் யாழிசைச் சிற்பங்கள், ஒலி எதிரொலிக்கும் கொடுங்கை கற்கூரைகள் மற்றும் தேவாரப் பண் மரபு தழைத்த வரலாற்றுத் தளம்.",
        "sources": [
            "Pudukkottai State Manual",
            "Manikkavasagar Tiruvacakam (Thirupperunthurai)",
            "Architectural Acoustics of South Indian Mandapas"
        ],
        "content": "# Avudaiyarkoil (Thirupperunthurai): Panar & Acoustic Haven\n\nLocated in the Vellar river plain of Pudukkottai district, Avudaiyarkoil (classical *Thirupperunthurai*) stands as a preeminent monument to Tamil musical acoustics and liturgical *Pann* performance:\n\n**Musical & Architectural Heritage:**\n- **Liturgical Pann Tradition**: Celebrated as the sacred site where Manikkavasagar composed hymns of the *Tiruvacakam*, the temple maintained endowments for *Oduvar* and *Panar* musicians singing ancient *Pann* modes.\n- **Acoustic Stone Engineering (*Kodungai*)**: The temple's *Panchatchara Mandapam* features paper-thin, doubly curved monolithic granite eaves (*kodungai*) carved to replicate wooden rafters and bronze rivets, engineered to diffuse vocal and stringed acoustic resonance evenly across the hall without slap-back echo.\n- **Iconographic Record**: Pillar reliefs across the Pudukkottai-Chola belt preserve detailed stone carvings of bow-shaped *Yazh* harps held by *Panar* minstrels."
    },
    {
        "slug": "concept-transition-from-open-string-yazh-harp-to-fretted-kinnari-and-veena",
        "category": "concept",
        "file": "concept-transition-from-open-string-yazh-harp-to-fretted-kinnari-and-veena.md",
        "name_en": "Organological Transition from Open-String Yazh Harp to Fretted Neck-Lutes and Veena",
        "name_ta": "திறந்த நரம்பு யாழிலிருந்து மெட்டுக்களையுடைய கின்னரி மற்றும் வீணைக்கு மாறிய இசைக்கருவிப் பரிணாமம்",
        "era": "Early Medieval to Nayak Era",
        "year_start": 600,
        "year_end": 1700,
        "thinai": "marutham",
        "summary_en": "Musicological explanation of why the open-stringed arched Yazh gradually gave way to fretted stick-zithers and lutes (Kinnari, Yazh-Vina, Thanjavur Veena) between the 7th and 14th centuries: the rise of continuous microtonal pitch glides (gamaka / kampita) formed by lateral string deflection over frets.",
        "summary_ta": "ஏழாம் நூற்றாண்டிற்குப் பிறகு திறந்த நரம்புடைய யாழ் வழக்கொழிந்து மெட்டுக்களையுடைய வீணை வளர்ந்ததற்கான இசை அறிவியல் காரணம்: நரம்பை இழுத்து வாசிக்கும் கமக மற்றும் நுண்ணிய சுருதி அசைவுகளின் வளர்ச்சி.",
        "sources": [
            "Thevaram Tirunilakanta Yazhppanar Purana",
            "Vipulananda Adigal Yaazh Nool",
            "Musicological History of the South Indian Veena"
        ],
        "content": "# Transition from Open-String Yazh to Fretted Veena\n\nOne of the central questions of Tamil organology is why the revered *Yazh* gradually vanished from concert practice between the 8th and 13th centuries in favor of fretted necked instruments (*Veena* and *Kinnari*):\n\n**Acoustic & Stylistic Drivers:**\n- **Limits of Open-String Harps**: On an arched harp (*Yazh*), each string sounds a single fixed pitch when plucked. Producing microtonal oscillations (*gamaka* / *asaivu*) or glissandos across intervals required either retuning the *thivavu* leather rings or pressing strings near the belly with limited pitch bend range.\n- **The Tirunilakanta Yazhppanar Episode**: Traditional hagiography (*Periya Puranam*) recalls how Sambandar composed the complex microtonal hymn *Madhar Madappidi* (*Pann Megharagakkurinji*), whose continuous vocal curves exceeded the discrete open-string boundaries of the *Yazh*.\n- **Fretted Lute Advantage**: Setting brass frets in wax beds along a hollow neck allowed a single string to be deflected laterally, yielding seamless *gamaka* inflections and instantaneous modulation across all *ragas*."
    },
    {
        "slug": "artifact-konikkol-plectrum-aanikkai-bridge-pegs-and-embroidered-yazh-wraps",
        "category": "artifact",
        "file": "artifact-konikkol-plectrum-aanikkai-bridge-pegs-and-embroidered-yazh-wraps.md",
        "name_en": "Konikkol Horn Plectrums, Aanikkai Bridge Pins & Embroidered Kalappai Harp Wraps",
        "name_ta": "கோணிக்கோல் சுண்டு கருவி, ஆணிக்கை மர முளைகள் மற்றும் யாழ் பொதிந்த கலப்பைத் தோலுறைகள்",
        "era": "Sangam to Early Medieval Era",
        "year_start": -300,
        "year_end": 900,
        "thinai": "marutham",
        "summary_en": "Accessory toolkit of the classical Tamil harpist: polished horn or ivory plectrums (konikkol), crab-eye wooden bridge pins (aanikkai), internal string-anchor bars (ul-karpu), and padded silk or soft leather carrying cases (kalappai) shielding the Yazh during monsoon travel.",
        "summary_ta": "யாழிசைக் கலைஞரின் துணைக் கருவிகள்: நரம்பைச் சுண்டும் கோணிக்கோல், போர்வைத் தோலைப் பிணைக்கும் நண்டுக்கண் ஆணிக்கைகள், உள்கற்பு சட்டம் மற்றும் மழைக்காலத்தில் யாழைப் பாதுகாக்கும் கலப்பை உறைகள்.",
        "sources": [
            "Porunararruppadai",
            "Perumpanarruppadai",
            "Silappadikaram Arangerrukathai Commentary"
        ],
        "content": "# Konikkol Plectrums, Bridge Pins & Kalappai Harp Wraps\n\nBeyond the wooden body of the harp, classical texts catalog the essential fittings and protective gear carried by *Panar* troupes:\n\n**Accessory Inventory:**\n- **Konikkol & Finger Plucking**: Harpists sounded strings both with bare fingertips (using the eight canonical right- and left-hand plucking strokes listed in *Silappadikaram*, such as *vandhal, varudhal, thudai*) and with a small polished horn or hardwood plectrum (*konikkol*) for brisk rhythmic passages.\n- **Aanikkai Fastening Pegs**: Tiny, smooth-headed pegs of *vengai* wood or bone driven along the rim of the *porvai* hide cover to distribute membrane tension evenly without tearing the parchment.\n- **Kalappai Instrument Bags**: Because damp forest air slackened gut strings and warped the thin *pathar* soundboard, wandering bards wrapped their *Yazh* inside padded cloth and oiled leather pouches (*kalappai*) slung on carrying poles."
    }
]

EDGES = [
    [
        "text-arruppadai-and-silappadikaram-on-yazh-organology-and-panar-bards",
        "describes",
        "artifact-periyazh-makarayazh-sakodayazh-and-seeriyazh-harp-typology",
        "material_culture",
        "Sangam to Post-Sangam Era",
        "Sangam Arruppadai poems and Silappadikaram document the anatomy and string counts of the four classical Yazh harps.",
        "Silappadikaram & Arruppadai"
    ],
    [
        "concept-kumizh-and-vengai-soundwood-seasoning-and-pathar-resonator-acoustics",
        "underpins",
        "technology-yazh-carving-porvai-parchment-stitching-and-thivavu-tuning-rings",
        "material_culture",
        "Iron Age to Medieval Era",
        "Seasoned kumizh and vengai soundwoods provide the acoustic stability required for carving thin-walled pathar resonators.",
        "Yaazh Nool"
    ],
    [
        "technology-yazh-carving-porvai-parchment-stitching-and-thivavu-tuning-rings",
        "constructs",
        "artifact-periyazh-makarayazh-sakodayazh-and-seeriyazh-harp-typology",
        "material_culture",
        "Sangam to Early Medieval Era",
        "Gouging the pathar trough, stitching the porvai hide, and fitting thivavu rings produce the four classes of Yazh.",
        "Porunararruppadai"
    ],
    [
        "technology-narambu-gut-and-twisted-silk-string-spinning-and-wax-polishing",
        "strings",
        "artifact-periyazh-makarayazh-sakodayazh-and-seeriyazh-harp-typology",
        "material_culture",
        "Sangam to Medieval Era",
        "Calibrated gut and twisted-silk narambu strings are mounted across the Yazh from the ul-karpu bar to the thivavu rings.",
        "Silappadikaram Commentary"
    ],
    [
        "concept-vattappalai-cycle-of-fifths-and-kural-thiribu-modal-transposition",
        "tunes",
        "artifact-periyazh-makarayazh-sakodayazh-and-seeriyazh-harp-typology",
        "material_culture",
        "Sangam to Medieval Era",
        "The Vattappalai cycle of fifths and Kural-Thiribu tonic shifting govern modal tuning across open Yazh strings.",
        "Karunamirtha Sagaram"
    ],
    [
        "institution-panar-and-viraliyar-bardic-guilds-and-royal-arruppadai-patronage",
        "performs_with",
        "artifact-periyazh-makarayazh-sakodayazh-and-seeriyazh-harp-typology",
        "material_culture",
        "Sangam to Chola Era",
        "Itinerant Panar and Viraliyar bardic guilds performed courtly and sacred Pann music upon the Periyazh and Seeriyazh.",
        "Sirupanarruppadai"
    ],
    [
        "institution-panar-and-viraliyar-bardic-guilds-and-royal-arruppadai-patronage",
        "operates_in",
        "place-avudaiyarkoil-ancient-panar-yazh-and-acoustic-haven",
        "material_culture",
        "Early Medieval to Modern Era",
        "Panar and Oduvar lineages performed sacred Pann hymns in the acoustically engineered mandapas of Avudaiyarkoil.",
        "Pudukkottai State Manual"
    ],
    [
        "concept-transition-from-open-string-yazh-harp-to-fretted-kinnari-and-veena",
        "transforms",
        "artifact-periyazh-makarayazh-sakodayazh-and-seeriyazh-harp-typology",
        "material_culture",
        "Early Medieval to Nayak Era",
        "Rising demand for continuous microtonal gamaka glides drove the evolution from open-string Yazh harps to fretted Veena lutes.",
        "Periya Puranam & Yaazh Nool"
    ],
    [
        "technology-yazh-carving-porvai-parchment-stitching-and-thivavu-tuning-rings",
        "incorporates",
        "artifact-konikkol-plectrum-aanikkai-bridge-pegs-and-embroidered-yazh-wraps",
        "material_culture",
        "Sangam to Early Medieval Era",
        "Yazh assembly and touring maintenance relied on aanikkai bridge pins, konikkol plectrums, and protective kalappai wraps.",
        "Perumpanarruppadai"
    ],
    [
        "text-arruppadai-and-silappadikaram-on-yazh-organology-and-panar-bards",
        "celebrates",
        "place-avudaiyarkoil-ancient-panar-yazh-and-acoustic-haven",
        "material_culture",
        "Early Medieval to Modern Era",
        "Classical Tamil musical literature and Shaiva Pann traditions find living architectural expression at Thirupperunthurai.",
        "Tiruvacakam"
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
