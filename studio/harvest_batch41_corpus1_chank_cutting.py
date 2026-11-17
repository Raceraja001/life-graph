#!/usr/bin/env python3
"""
Harvester: Batch 41 - Ancient Tamil Chank Cutting, Bangle Sawing & Marine Mollusc Shell Craft
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
        "slug": "text-nattrinai-and-ahananuru-on-conch-shell-cutters",
        "category": "text",
        "file": "text-nattrinai-and-ahananuru-on-conch-shell-cutters.md",
        "name_en": "Nattrinai & Ahananuru Verses on Conch Shell Cutters and Bangle Sawing",
        "name_ta": "நற்றிணை மற்றும் அகநானூற்று சங்கு அறுப்போர் மற்றும் சங்கு வளையல் பாடல் குறிப்புகள்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "neithal",
        "summary_en": "Classical Sangam anthologies describing specialized coastal artisans ('Sangu-Aruppor') sawing sacred chanks into brilliant white bangles with curved iron saws, the sound of sawing echoing through port workshops of Korkai and Alagankulam.",
        "summary_ta": "சங்க இலக்கியத்தில் கொற்கை மற்றும் அழகன்குளத் துறைமுகங்களில் வளைந்த இரும்புக் கொண்டு வெண்சங்கு அறுத்து வளையல் செய்த சங்கு அறுப்போர் பற்றிய நற்றிணை மற்றும் அகநானூற்றுப் பாடல்கள்.",
        "sources": [
            "Nattrinai 94",
            "Ahananuru 24",
            "Korkai Archaeological Reports"
        ],
        "content": "# Nattrinai & Ahananuru Verses on Conch Shell Cutters\n\nThe Sangam poetic canon contains explicit documentary evidence for industrial-scale conch shell sawing and bangle manufacturing in southern Tamil ports:\n\n**Literary Testimonies:**\n- **Nattrinai (Verse 94)**: Describes the sharp-toothed curved iron saw (*kudhirai-vaai aruval*) grating against dense conch shell whorls, producing heaps of snow-white shell dust (*sangu-thool*) like crushed pearls.\n- **Ahananuru (Verse 24)**: Celebrates the pure white shell bangles (*vellivalai*) worn by littoral women, engraved with delicate chevron grooves and polished until glistening.\n- **Maduraikanchi (lines 510-515)**: Portrays the artisan quarters of Korkai where conch shells gathered by Parathavar divers are sorted into *Valampuri* (sinistral) and *Idampuri* (dextral) forms, then methodically bisected for ornaments."
    },
    {
        "slug": "concept-turbinella-pyrum-shell-anatomy-and-columella-density",
        "category": "concept",
        "file": "concept-turbinella-pyrum-shell-anatomy-and-columella-density.md",
        "name_en": "Turbinella Pyrum Shell Anatomy, Aragonite Columella Density & Fracture Mechanics",
        "name_ta": "வெண்சங்கு உடற்கூறியல், அரகோனைட் சுழல் அடர்த்தி மற்றும் வெட்டுப் பிளவு இயக்கவியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -1000,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Biological and mineralogical morphology of the Indian sacred chank (Turbinella pyrum): its high-density aragonite-calcite crystalline matrix, thick central columella, spiral suturing, and exceptional fracture toughness against saw cutting.",
        "summary_ta": "இந்திய புனித வெண்சங்கின் உடற்கூறியல் மற்றும் கனிமக் கட்டமைப்பு: அடர்ந்த அரகோனைட் படிக அடுக்கு, திடமான நடு அச்சுத் தண்டு (கொலுமெல்லா) மற்றும் பிளவு முறிவுப் பண்புகள்.",
        "sources": [
            "Marine Molluscan Biology Studies",
            "CSIR Shell Mineralogy Reports",
            "Gulf of Mannar Chank Surveys"
        ],
        "content": "# Turbinella Pyrum Shell Anatomy & Fracture Mechanics\n\nThe Indian sacred chank (*Turbinella pyrum*) belongs to the family Turbinellidae, thriving in sandy substrates of the Gulf of Mannar and Palk Strait:\n\n**Skeletal Mineralogy:**\n- The shell wall consists of cross-lamellar microcrystalline aragonite embedded in an organic conchiolin protein framework, yielding a Mohs hardness of 3.5 to 4.0 and exceptional compressive strength (>120 MPa).\n- The central axis (*columella*) features solid, spiraling folds that provide immense rigid structural resistance, requiring continuous water-cooled sawing to prevent thermal embrittlement.\n- Dextral (right-handed whorl) shells form 99.9% of wild populations, while the extremely rare sinistral (*Valampuri*) form was venerated as a sacred royal talisman."
    },
    {
        "slug": "technology-conch-shell-semicircular-saw-slicing-and-mandrel-grinding",
        "category": "technology",
        "file": "technology-conch-shell-semicircular-saw-slicing-and-mandrel-grinding.md",
        "name_en": "Conch Shell Semicircular Saw Slicing, Mandrel Turning & Water-Cooled Grinding",
        "name_ta": "அரைவட்ட இரும்புக் கதிர்வாள் அறுப்பு, மர உருளை சுழல் கடைசல் மற்றும் நீர் குளிர்விப்பு முறை",
        "era": "Sangam to Medieval Era",
        "year_start": -400,
        "year_end": 1300,
        "thinai": "neithal",
        "summary_en": "The mechanical sequence of Tamil shell bangle fabrication: apex shearing, columella extraction using iron drifts, parallel slicing with toothless crescent saws fed with quartz sand slurry, and cylindrical mandrel grinding.",
        "summary_ta": "பண்டைய சங்கு வளையல் அறுக்கும் தொழில்நுட்ப வரிசை: சங்கு உச்சி உடைப்பு, நடு அச்சு நீக்கம், மணல் கலவை கொண்ட அரைவட்ட இரும்புக் கதிர்வாள் கொண்டு வளையத் துண்டுகள் அறுத்தல் மற்றும் கடைசல்.",
        "sources": [
            "Archaeology of Ancient Indian Shell Technology",
            "Korkai Excavation Memoirs",
            "Tamil Nadu State Archaeology Department"
        ],
        "content": "# Conch Shell Semicircular Saw Slicing & Mandrel Turning\n\nThe transformation of raw *Turbinella pyrum* into calibrated bangles represents one of ancient India's most exacting lapidary pyrotechnologies:\n\n**Fabrication Process:**\n1. **Apex & Lip Removal**: The apical spire and dorsal lip are detached using light hammer taps on an iron chisel, opening the internal spiral chamber.\n2. **Columella Core Extraction**: An iron punch is driven through the aperture to shatter and extract the dense columella without fracturing outer shell whorls.\n3. **Crescent Saw Slicing**: The hollow shell cylinder is clamped in a wooden vise and sliced into rings using a broad, toothless semicircular iron blade (*kudhirai-vaai saw*), continuously lubricated with wet quartz abrasive sand.\n4. **Mandrel Smoothing**: Sliced shell hoops are mounted on tapered wooden mandrels and burnished with fine river silt and sesame oil to achieve glass-smooth edges."
    },
    {
        "slug": "artifact-sangu-valaiyal-engraved-bangles-beads-and-conch-horns",
        "category": "artifact",
        "file": "artifact-sangu-valaiyal-engraved-bangles-beads-and-conch-horns.md",
        "name_en": "Sangu Valaiyal Engraved Bangles, Shell Beads & Ceremonial Conch Trumpets",
        "name_ta": "சங்கு வளையல்கள், மணிகள் மற்றும் மங்கல வெண்சங்கு ஊதுகுழல்கள்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Material repertoire of ancient Tamil chank craftsmanship: polished concentric shell bangles with geometric chevron incisions, drilled shell beads, columella ear spools, and liturgical conch trumpets (valampuri and idampuri).",
        "summary_ta": "பண்டைய தமிழ்ச் சங்கு கலைப்பொருட்கள்: செவ்வரக்கு நிரப்பப்பட்ட வேலைப்பாடுடைய சங்கு வளையல்கள், சங்குப் பாசிகள், காதணிகள் மற்றும் வழிபாட்டு மங்கல ஊது சங்குகள்.",
        "sources": [
            "Keezhadi Archaeological Excavation Reports",
            "Adichanallur Shell Artefact Catalog",
            "Madras Government Museum Shell Collection"
        ],
        "content": "# Sangu Valaiyal Engraved Bangles & Ceremonial Horns\n\nArchaeological excavations at Keezhadi, Korkai, Alagankulam, and Kodumanal demonstrate the prolific material culture of conch craftsmanship:\n\n**Artefact Typology:**\n- **Calibrated Shell Bangles**: Ranging in inner diameter from 45 mm to 65 mm, featuring meticulously incised chevron, dot-in-circle, and rope-twist patterns filled with red vermilion or mineral lac.\n- **Columella Discs & Beads**: Cylindrical and barrel beads shaped from dense core waste, drilled longitudinally with micro-perforators.\n- **Trumpet Conchs (*Valampuri & Sangoli*)**: Intact shells with the apex perforated and polished for ceremonial signalling in warfare, maritime navigation, and temple rituals."
    },
    {
        "slug": "concept-chank-cutting-waste-stratigraphy-in-korkai-and-alagankulam",
        "category": "concept",
        "file": "concept-chank-cutting-waste-stratigraphy-in-korkai-and-alagankulam.md",
        "name_en": "Chank Cutting Industrial Debris Stratigraphy in Korkai, Alagankulam & Arikamedu",
        "name_ta": "கொற்கை, அழகன்குளம் மற்றும் அரிக்கமேடு சங்கு தொழிற்கூட அடுக்குப்படிவச் சான்றுகள்",
        "era": "Sangam Era to Early Medieval",
        "year_start": -400,
        "year_end": 800,
        "thinai": "neithal",
        "summary_en": "Stratigraphic archaeological evidence of massive conch shell workshops across Tamil ports: thousands of discarded columella cores, sawn apexes, unfinished bangle rough-outs, and iron saw blade fragments.",
        "summary_ta": "பண்டைய துறைமுகங்களில் கண்டெடுக்கப்பட்ட பெரும் சங்குத் தொழிற்கூட எச்சங்கள்: ஆயிரக்கணக்கான வெட்டப்பட்ட சங்குத் தண்டுகள், உச்சி பாகங்கள், முடிவுறாத வளையல்கள் மற்றும் அறுப்புப் படிவுகள்.",
        "sources": [
            "Archaeological Survey of India: Alagankulam Excavations",
            "Tamil Nadu State Archaeology Department Korkai Reports",
            "Arikamedu Excavation Monographs"
        ],
        "content": "# Chank Cutting Industrial Debris Stratigraphy\n\nExcavations at ancient Tamil coastal and inland transit centers provide unassailable stratigraphic proof of specialized conch processing workshops:\n\n**Stratigraphic Features:**\n- **Columella Core Dumps**: At Korkai and Alagankulam, deep stratified layers contain tens of thousands of severed columellae with uniform saw marks, testifying to standardized mass production.\n- **Micro-Blade Wear**: Associated layers yield curved iron blades exhibiting abrasive edge-rounding consistent with quartz-sand slurried shell sawing.\n- **Distribution Networks**: Sawn columella cores from the Gulf of Mannar were traded upstream along the Vaigai to Keezhadi and across the Palakkad Gap to Kerala coastal emporia."
    },
    {
        "slug": "institution-sangu-aruppor-guild-of-hereditary-chank-cutters-and-traders",
        "category": "institution",
        "file": "institution-sangu-aruppor-guild-of-hereditary-chank-cutters-and-traders.md",
        "name_en": "Sangu Aruppor Guild: Hereditary Conch Shell Cutters, Inlayers & Maritime Traders",
        "name_ta": "சங்கு அறுப்போர் வணிகக் குழு: மரபுவழி சங்கு வினைஞர் மற்றும் கடல்சார் வர்த்தக சங்கம்",
        "era": "Sangam to Vijayanagara Era",
        "year_start": -300,
        "year_end": 1600,
        "thinai": "neithal",
        "summary_en": "The corporate artisan guild of Tamil chank carvers: regulating raw shell quotas from Parathavar divers, maintaining blade standards, enforcing apprenticeships, and trading shell bangles across India and Southeast Asia.",
        "summary_ta": "சங்கு அறுக்கும் கைவினைஞர்கள் மற்றும் வணிகர்களின் தன்னாட்சி சங்கம்: மூலப்பொருள் ஒதுக்கீடு, தொழில்நுட்பத் தரம், வர்த்தக விலை நிர்ணயம் மற்றும் ஏற்றுமதி ஒழுங்குமுறை.",
        "sources": [
            "Epigraphia Indica: Gulf of Mannar Guild Inscriptions",
            "Sangam Corporate Guild Studies",
            "South Indian Inscriptions"
        ],
        "content": "# Sangu Aruppor Guild: Hereditary Conch Cutters\n\nThe manufacturing of shell ornaments was organized through tightly knit corporate artisan bodies operating in harmony with maritime divers:\n\n**Guild Functions:**\n- **Raw Material Allocation**: Contracted directly with Parathavar diving syndicates and royal Pandyan officials to acquire seasonal catches from pearl and chank banks (*chanku-padukal*).\n- **Quality Control**: Enforced strict standards for wall thickness, fracture-free cuts, and smooth inner circumferences to prevent wrist abrasions.\n- **Long-Distance Export**: Collaborated with Ainnurruvar and Manigramam trading corporations to export finished shell bangles to Bengal, Malacca, and inland Deccan kingdoms."
    },
    {
        "slug": "technology-shell-groove-incising-vermilion-insetting-and-lac-polishing",
        "category": "technology",
        "file": "technology-shell-groove-incising-vermilion-insetting-and-lac-polishing.md",
        "name_en": "Shell Groove Incising, Vermilion Mineral Insetting & Natural Lac Burnishing",
        "name_ta": "சங்கு வளையல் நுண்ணிய கோட்டோவியக் கீறல், செவ்வரக்கு நிரப்புதல் மற்றும் அரக்கு பளபளப்பாக்கல்",
        "era": "Iron Age to Medieval Era",
        "year_start": -400,
        "year_end": 1400,
        "thinai": "neithal",
        "summary_en": "Micro-lapidary embellishment of conch shell bangles: engraving microscopic chevron grooves with steel gravers, insetting bright red cinnabar/lac mastic, and final friction buffing with agate burnishers.",
        "summary_ta": "சங்கு வளையல்களில் நுண்ணிய இரும்பு உளி கொண்டு வடிவங்கள் செதுக்கி, சிவப்பு அரக்கு மற்றும் சாதிலிங்கம் நிரப்பி, அகேட் கற்கள் கொண்டு மெருகேற்றும் தொழில்நுட்பம்.",
        "sources": [
            "Keezhadi Lapidary Analysis Reports",
            "Ancient Indian Jewellery Craft Monographs",
            "Archaeological Science Journal"
        ],
        "content": "# Shell Groove Incising & Vermilion Lac Insetting\n\nThe aesthetic hallmark of ancient Tamil shell bangles was the stark contrast between glistening ivory-white calcium carbonate and vibrant red geometric inlays:\n\n**Ornamentation Techniques:**\n1. **Steel Graver Incising**: Craftsmen used fine-pointed hardened steel scorpers to score shallow channels (0.5–1.0 mm depth) along the outer perimeter in hatching, zigzag, and floral motifs.\n2. **Hot Lac Insetting**: Natural sticklac mixed with crushed cinnabar (*sadhilingam*) was heated and pressed into the carved grooves while molten.\n3. **Surface Planing & Agate Buffing**: Excess lac was shaved level with a scraper, followed by friction burnishing using smooth agate pebbles and coconut oil, leaving crisp, luminous red designs embedded permanently in the shell wall."
    },
    {
        "slug": "place-alagankulam-ancient-pandya-chank-cutting-haven",
        "category": "place",
        "file": "place-alagankulam-ancient-pandya-chank-cutting-haven.md",
        "name_en": "Alagankulam: Ancient Pandyan Chank Cutting Haven, Vaigai Estuary & Greco-Roman Shell Port",
        "name_ta": "அழகன்குளம் - பண்டைய பாண்டியர் சங்கு அறுப்புத் தளம், வைகைக் கழிமுக சங்கு தொழிற்கூடம் மற்றும் துறைமுகம்",
        "era": "Iron Age to Early Medieval",
        "year_start": -400,
        "year_end": 600,
        "thinai": "neithal",
        "summary_en": "Major historic port city at the mouth of the Vaigai River in Ramanathapuram district, celebrated as the largest excavated industrial chank workshop in Tamil Nadu, yielding thousands of sawn conch cores, Mediterranean amphorae, and Roman coins.",
        "summary_ta": "இராமநாதபுரம் மாவட்டத்தில் வைகை ஆற்று முகத்துவாரத்தில் அமைந்த சங்க காலப் பெருந்துறைமுகம்: தமிழகத்தின் மிகப்பெரிய சங்கு அறுப்புத் தொழிற்கூடம், உரோமானிய வணிகத் தளம் மற்றும் சங்கு வளையல் உற்பத்தி மையம்.",
        "sources": [
            "Alagankulam Excavation Reports (TNSDA)",
            "Palk Bay Maritime Trade Studies",
            "Roman Trade in the Indian Ocean"
        ],
        "content": "# Alagankulam: Ancient Pandyan Chank Cutting Haven\n\nLocated on the northern shores of the Gulf of Mannar near Mandapam, Alagankulam served as a paramount industrial harbor for maritime chank artisanship:\n\n**Archaeological Prominence:**\n- Extensive trenching by the Tamil Nadu State Department of Archaeology unearthed massive concentrations of cut *Turbinella pyrum* shells, broken bangles, waste columellae, and shell beads.\n- Co-occurrence with Rouletted ware, Arretine sherds, and Roman imperial bronze coins demonstrates that Alagankulam's shell workshops operated at the heart of trans-oceanic luxury commerce.\n- Its sheltered lagoon provided safe anchorage for catamaran diving fleets returning with fresh chank loads dredged from coral shoals."
    },
    {
        "slug": "concept-valampuri-sinistral-conch-rarity-fluid-dynamics-and-sacred-symbolism",
        "category": "concept",
        "file": "concept-valampuri-sinistral-conch-rarity-fluid-dynamics-and-sacred-symbolism.md",
        "name_en": "Valampuri Sinistral Conch Rarity, Hydrodynamics & Sacred Royal Symbolism",
        "name_ta": "வலம்புரிச் சங்கு உருவவியல், இடஞ்சுழிப் பிறழ்வு, நீரியக்கவியல் மற்றும் அரச மங்கல அடையாளம்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Morphological, statistical and acoustic principles of the sinistral (left-coiling) Valampuri conch: genetic developmental chirality, rarity (1 in 100,000 specimens), resonant cavity acoustics, and imperial Tamil ritual regalia.",
        "summary_ta": "வலம்புரிச் சங்கின் உடற்கூறியல் மற்றும் ஒலி அதிர்வெண் பண்புகள்: மரபணு சுழற்சி முறை, அரிய தோற்றம், ஒலி எதிரொலிப்பு மற்றும் பாண்டிய-சோழ அரசர்களின் முடிசூட்டு மங்கலப் பொருள்.",
        "sources": [
            "Malacological Society Transactions",
            "Journal of Archaeological Science",
            "Tolkappiyam & Silappadikaram Commentaries"
        ],
        "content": "# Valampuri Sinistral Conch Rarity & Sacred Symbolism\n\nWhile standard dextral (*Idampuri*) conchs coil clockwise, the rare sinistral (*Valampuri*) shell exhibits left-handed developmental chirality:\n\n**Morphology & Acoustic Resonance:**\n- Genetic mutation in embryonic cleavage causes the internal spire to rotate counter-clockwise, occurring in roughly one out of every 100,000 wild *Turbinella pyrum* individuals.\n- The altered internal logarithmic spiral chamber creates distinct standing sound waves when blown as a ritual horn, generating low-frequency acoustic harmonics ($220-440\\\\text{ Hz}$) that carry across kilometers of sea and land.\n- In ancient Tamil royal liturgy, the Valampuri was the supreme royal emblem, mounted in repousse gold and used exclusively for monarchical abhisheka consecrations."
    },
    {
        "slug": "artifact-korkai-sawn-columella-hoards-and-iron-chank-saws",
        "category": "artifact",
        "file": "artifact-korkai-sawn-columella-hoards-and-iron-chank-saws.md",
        "name_en": "Korkai Sawn Columella Hoards, Unfinished Bangles & Crescent Iron Saws",
        "name_ta": "கொற்கை சங்கு அச்சுப் படிவுகள், முடிவுறா வளையல்கள் மற்றும் வளைந்த இரும்புக் கதிர்வாள்கள்",
        "era": "Sangam Era",
        "year_start": -500,
        "year_end": 200,
        "thinai": "neithal",
        "summary_en": "Iconic archaeological assemblages excavated at Korkai: caches of discarded central columella cores exhibiting precision parallel saw kerfs, half-cut shell cylinders, and crescent-shaped iron cutting tools.",
        "summary_ta": "கொற்கை அகழ்வாய்வில் வெளிக்கொணரப்பட்ட தொழிற்கூடத் தொல்பொருட்கள்: துல்லியமான வாள் கீறல்கள் கொண்ட சங்கு நடு அச்சுக்கள், அரைகுறை வளையல்கள் மற்றும் இரும்பு அறுப்பு வாள்கள்.",
        "sources": [
            "Korkai Excavation Report (ASI & TNSDA)",
            "Indian Historical Quarterly",
            "Bulletin of the Madras Museum"
        ],
        "content": "# Korkai Sawn Columella Hoards & Crescent Iron Saws\n\nKorkai, the celebrated Sangam Pandyan maritime capital, yielded foundational material evidence for organized shell cutting:\n\n**Diagnostic Assemblages:**\n- **Kerf Analysis**: High-magnification optical microscopy on sawn columellae reveals straight, clean kerfs with uniform stroke striations, indicating rigid saw framing and continuous sand-slurry lubrication.\n- **Bangle Preforms**: Multiple concentric rough-out rings found nested together prove that master cutters extracted up to four usable bangles from a single adult conch.\n- **Corroded Tool Remains**: Fragments of curved, thin-profile wrought-iron saw bands with hardened cutting perimeters reflect high-metallurgical competence tailored for mineral cutting."
    }
]

EDGES = [
    [
        "text-nattrinai-and-ahananuru-on-conch-shell-cutters",
        "evidences",
        "technology-conch-shell-semicircular-saw-slicing-and-mandrel-grinding",
        "material_culture",
        "Sangam Era",
        "Sangam verses directly describe the sound and mechanical operation of curved iron saws cutting conchs.",
        "Nattrinai 94 & Ahananuru 24"
    ],
    [
        "concept-turbinella-pyrum-shell-anatomy-and-columella-density",
        "enables",
        "technology-conch-shell-semicircular-saw-slicing-and-mandrel-grinding",
        "material_culture",
        "Iron Age to Modern Era",
        "Dense aragonite crystalline matrix dictates the use of water-cooled abrasive sand and crescent iron saws.",
        "CSIR Shell Mineralogy"
    ],
    [
        "technology-conch-shell-semicircular-saw-slicing-and-mandrel-grinding",
        "produces",
        "artifact-sangu-valaiyal-engraved-bangles-beads-and-conch-horns",
        "material_culture",
        "Sangam to Medieval Era",
        "Slicing, coring, and turning processes yield polished shell bangles, beads, and horn artifacts.",
        "Korkai Memoirs"
    ],
    [
        "concept-chank-cutting-waste-stratigraphy-in-korkai-and-alagankulam",
        "proves",
        "institution-sangu-aruppor-guild-of-hereditary-chank-cutters-and-traders",
        "material_culture",
        "Sangam Era to Early Medieval",
        "Massive stratified dumps of discarded sawn cores prove organized, permanent corporate shell artisan guilds.",
        "TNSDA Excavations"
    ],
    [
        "technology-shell-groove-incising-vermilion-insetting-and-lac-polishing",
        "decorates",
        "artifact-sangu-valaiyal-engraved-bangles-beads-and-conch-horns",
        "material_culture",
        "Iron Age to Medieval Era",
        "Groove incising and hot vermilion lac insetting create contrasting decorative bangles.",
        "Keezhadi Reports"
    ],
    [
        "place-alagankulam-ancient-pandya-chank-cutting-haven",
        "hosts",
        "concept-chank-cutting-waste-stratigraphy-in-korkai-and-alagankulam",
        "material_culture",
        "Iron Age to Early Medieval",
        "Alagankulam estuary harbor housed major shell processing quarters yielding stratified industrial debris.",
        "Alagankulam Excavations"
    ],
    [
        "institution-sangu-aruppor-guild-of-hereditary-chank-cutters-and-traders",
        "operates_in",
        "place-alagankulam-ancient-pandya-chank-cutting-haven",
        "material_culture",
        "Sangam to Vijayanagara Era",
        "Guild corporations managed shell procurement, workshops, and international export at Alagankulam.",
        "Epigraphia Indica"
    ],
    [
        "concept-valampuri-sinistral-conch-rarity-fluid-dynamics-and-sacred-symbolism",
        "elevates",
        "artifact-sangu-valaiyal-engraved-bangles-beads-and-conch-horns",
        "material_culture",
        "Iron Age to Modern Era",
        "Rarity and acoustic harmonics elevate sinistral Valampuri shells into sacred royal consecration regalia.",
        "Malacological Studies"
    ],
    [
        "artifact-korkai-sawn-columella-hoards-and-iron-chank-saws",
        "documents",
        "technology-conch-shell-semicircular-saw-slicing-and-mandrel-grinding",
        "material_culture",
        "Sangam Era",
        "Excavated sawn columellae and iron saw fragments verify the crescent saw manufacturing sequence.",
        "ASI Korkai Reports"
    ],
    [
        "text-nattrinai-and-ahananuru-on-conch-shell-cutters",
        "celebrates",
        "place-alagankulam-ancient-pandya-chank-cutting-haven",
        "material_culture",
        "Sangam Era",
        "Sangam poets laud the coastal emporia and busy shell-cutting artisan quarters along the Pandya coast.",
        "Nattrinai 94"
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
            emb = get_embedding(ch["content"])
            cur.execute("""
                INSERT INTO rag_chunks (node_slug, shelf, language, title, content, source_ref, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                slug,
                f"shelf-{d['category']}s",
                ch["language"],
                ch["title"],
                ch["content"],
                d["sources"][0] if d["sources"] else "Oral Tradition",
                emb,
            ))
        print(f"Embedded 2 chunks for: {slug}")
    conn.commit()

    cur.close()
    conn.close()
    print("=== Harvester Complete! ===")

if __name__ == "__main__":
    main()
