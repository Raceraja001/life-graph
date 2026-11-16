#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Bell-Metal Metallurgy & Resonant Gongs
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
        "file": "knowledge/texts/text-silappadikaram-temple-bronze-gongs-and-bell-metal-chimes-poetry.md",
        "slug": "text-silappadikaram-temple-bronze-gongs-and-bell-metal-chimes-poetry",
        "category": "text",
        "name_en": "Silappadikaram: Classical Sangam Verses on Temple Bronze Gongs & Bell-Metal Chimes",
        "name_ta": "சிலப்பதிகாரம் - வெண்கல மணி, சேகண்டி மற்றும் முழவு வாத்திய இசைப் பாடல்கள்",
        "era": "Post-Sangam Era",
        "year_start": 200,
        "year_end": 500,
        "thinai": "marutham",
        "summary_en": "Ilango Adigal's classical epic detailing the acoustic majesty of bell-metal temple gongs (chegandi), ringing finger-cymbals (kaithalam), and bronze metallurgical crafts in Poompuhar and Madurai.",
        "summary_ta": "இளங்கோ அடிகள் அருளிய சிலப்பதிகாரத்தில் வெண்கல சேகண்டிகள், கைத்தாளங்கள் மற்றும் மணி வாத்தியங்களின் தூய நாத ஒலி எழுப்பும் நுட்பங்கள் விவரிக்கப்படுகின்றன.",
        "sources": [
            "Silappadikaram Arangetrukathai",
            "Silappadikaram Kanalvari"
        ],
        "content": "# Silappadikaram: Classical Verses on Bell-Metal Gongs\n\nIn the panoramic cultural descriptions of Silappadikaram, Ilango Adigal reveals the profound acoustic sophistication of ancient Tamil bronze metallurgy. In both the bustling maritime capital of Poompuhar and the regal city of Madurai, musical gongs and bells orchestrated civic time and sacred liturgy.\n\nThe epic highlights the distinctive acoustic qualities of bell-metal alloy (venkalam), noting how master smiths tuned flat circular gongs (chegandi and sekkandi) to emit pure, sustaining harmonics that penetrated several leagues through evening mist.\n\nThe text also details the rhythmic accompaniment of bronze finger-cymbals (kaithalam and jalra) in classical Bharatanatyam dance dramas, demonstrating that metallurgy in ancient Tamilakam was fundamentally grounded in the physics of sacred acoustics."
    },
    {
        "file": "knowledge/concepts/concept-high-tin-bell-metal-alloy-metallurgy-and-beta-phase-quenching-venkalam.md",
        "slug": "concept-high-tin-bell-metal-alloy-metallurgy-and-beta-phase-quenching-venkalam",
        "category": "concept",
        "name_en": "High-Tin Bell-Metal Metallurgy & Beta-Phase Acoustic Quenching (Venkalam & Kansa)",
        "name_ta": "வெண்கலம் - உயர்தர வெள்ளீய வெண்கல உலோகவியல் மற்றும் நாத ஒலி பதனிடும் நுட்பம்",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Metallurgical science of high-tin bronze (78% copper, 22% tin) and rapid thermal quenching at 650°C to freeze the resonant beta intermetallic crystal phase for bell-metal acoustics.",
        "summary_ta": "78% செம்பு மற்றும் 22% வெள்ளீயம் கலந்த வெண்கலத்தை 650°C வெப்பத்தில் செஞ்சூடாக்கி, நீரில் விரைவாகக் குளிரவைத்து தூய நாத ஒலியை உருவாக்கும் உலோக நுட்பம்.",
        "sources": [
            "Metallurgical Heritage of South India (Sharada Srinivasan)",
            "Ancient Indian Metallurgy Monographs"
        ],
        "content": "# High-Tin Bell-Metal Metallurgy (Venkalam)\n\nAncient Tamil metallurgists achieved a world-class breakthrough in materials science through the mastery of high-tin bronze, known historically as venkalam or kansa. While standard bronze contains less than twelve percent tin, Tamil bell-metal was formulated with an exact 78:22 copper-to-tin stoichiometric ratio.\n\nAt room temperature, this high tin content produces a brittle, unworkable alloy. However, Tamil artisans discovered that by heating the forged metal into the beta-phase temperature window (between 600°C and 700°C) and rapidly quenching it in water, the ductile beta crystalline phase was frozen in place.\n\nThis metallurgical transformation imparted extraordinary musical resonance: struck plates vibrated with exceptionally low acoustic damping, producing long, pure, shimmering overtones that earned South Indian temple gongs global renown."
    },
    {
        "file": "knowledge/concepts/concept-acoustically-tuned-temple-resonance-gongs-chegandi-and-sekkandi.md",
        "slug": "concept-acoustically-tuned-temple-resonance-gongs-chegandi-and-sekkandi",
        "category": "concept",
        "name_en": "Acoustically Tuned Temple Resonance Gongs (Chegandi, Sekkandi & Mani Architecture)",
        "name_ta": "சேகண்டி மற்றும் செக்கண்டி - கோவில் நாத வெண்கல மணி மற்றும் அலைவரிசை இசைப் பொறியியல்",
        "era": "Sangam to Late Medieval Era",
        "year_start": -300,
        "year_end": 1600,
        "thinai": "marutham",
        "summary_en": "Acoustic engineering of suspended circular bell-metal gongs (chegandi) and flared temple bells, tuned through concentric thickness scraping to generate fundamental liturgical frequencies.",
        "summary_ta": "வட்ட வடிவிலான வெண்கல சேகண்டிகளின் தடிமனை மையத்திலிருந்து விளிம்பு வரை சமச்சீராகச் சீவி, குறிப்பிட்ட இசை அலைவரிசைகளில் ஒலிக்கச் செய்யும் தமிழ் இசைப் பொறியியல்.",
        "sources": [
            "Natya Shastra Musical Instrument Classification",
            "Traditional Acoustic Bronze Instruments of Tamil Nadu"
        ],
        "content": "# Acoustically Tuned Temple Resonance Gongs (Chegandi)\n\nThe chegandi (or sekkandi) is a suspended flat disc gong cast from high-tin bell-metal, struck with a deer-horn mallet or wooden stick during morning and evening temple anointments. It represented a masterpiece of harmonic physics.\n\nThe master tuner (oli aasaan) tuned the gong through manual lathe-turning and concentric scraping. By graduating the metal thickness—thickest at the central striking boss and tapering smoothly toward the raised outer lip—he eliminated jarring discordant dissonances.\n\nWhen struck, the gong vibrates in axisymmetric modal patterns, generating a deep, resonant hum (pranavakara) that lingers in the stone corridors of Dravidian temple mandapams for over twenty seconds without audible flutter."
    },
    {
        "file": "knowledge/concepts/concept-lost-wax-cire-perdue-solid-bronze-iconography-madhuchishta-vidhana.md",
        "slug": "concept-lost-wax-cire-perdue-solid-bronze-iconography-madhuchishta-vidhana",
        "category": "concept",
        "name_en": "Lost-Wax Solid Bronze Iconography & Ceramic Mold Formulation (Madhuchishta-Vidhana)",
        "name_ta": "மதுச்சிஷ்ட விதானம் - மெழுகு உரு உருக்கல் மற்றும் சோழர் வெண்கலச் சிற்ப வார்ப்பு முறைமை",
        "era": "Sangam to Chola Era",
        "year_start": -400,
        "year_end": 1300,
        "thinai": "marutham",
        "summary_en": "Ancient cire-perdue solid casting method using pure bees-wax, dammar resin, and sequential alluvial clay molds (vandimann) to create world-renowned Chola bronzes of Nataraja and sacred deities.",
        "summary_ta": "தேனீ மெழுகு மற்றும் குங்கிலியம் கொண்டு உருவம் செய்து, வண்டல் மண் பூசி, மெழுகை உருக்கி அகற்றிவிட்டு உருக்கிய வெண்கலத்தை ஊற்றும் பாரம்பரிய வார்ப்புக் கலை.",
        "sources": [
            "Silpa Sastra (Kasyapa Silpa)",
            "Chola Bronzes of Tamil Nadu (Douglas Barrett)"
        ],
        "content": "# Lost-Wax Solid Bronze Iconography (Madhuchishta-Vidhana)\n\nThe sacred bronze sculptures of Tamilakam, celebrated worldwide for their anatomical poise and spiritual vitality, were cast using the ancient cire-perdue (lost-wax) technique known as madhuchishta-vidhana.\n\nThe master sthapati first sculpted the deity in solid beeswax mixed with wild tree dammar and groundnut oil. The wax model was enveloped in three successive coats of fine Cauvery alluvial clay: the first slip mixed with charred rice husk for microscopic detail, the second coat with river silt, and the heavy outer layer with coarse clay reinforced with jute fibers.\n\nOnce dried, the mold was heated over a charcoal pit; the molten wax ran out, leaving an inverted cavity. Simultaneously, molten five-metal alloy (panchaloha or high-tin bronze) was poured directly into the red-hot mold, creating a single seamless, solid bronze masterpiece."
    },
    {
        "file": "knowledge/concepts/concept-abrasive-tamarind-and-charcoal-mirror-polishing-venkala-palupu.md",
        "slug": "concept-abrasive-tamarind-and-charcoal-mirror-polishing-venkala-palupu",
        "category": "concept",
        "name_en": "Abrasive Tamarind Acid & Fine Charcoal Mirror Finishing (Venkala-Palupu Metallurgy)",
        "name_ta": "வெண்கலப் பளபளப்பூட்டல் - புளிக்காடி மற்றும் கரித்தூள் கொண்டு கண்ணாடிப் பளபளப்பு செய்யும் முறைமை",
        "era": "Prehistoric to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Traditional chemical and abrasive finishing protocols utilizing steeped tamarind tartaric acid baths and pulverized coconut-shell charcoal to burnish bell-metal to an unoxidized golden luster.",
        "summary_ta": "பழம்புளி அமில ஊறல் மற்றும் தேங்காய் சிரட்டை கரித்தூள் கொண்டு வெண்கலப் பாண்டங்கள் மற்றும் மணிகளைத் தேய்த்து, தங்க நிறக் கண்ணாடிப் பளபளப்பு தரும் பாரம்பரிய முறைமை.",
        "sources": [
            "Tamil Sthapati Oral Metallurgy Canons",
            "Artisanal Metal Finishing Surveys of Thanjavur"
        ],
        "content": "# Abrasive Tamarind & Charcoal Mirror Finishing (Venkala-Palupu)\n\nAfter casting and quenching, rough bell-metal surfaces carry an unsightly dark scale of copper oxide and tin dross. Ancient Tamil artisans developed an organic chemical pickling and abrasive buffing regimen that revealed the dazzling silvery-golden core of the metal.\n\nThe cast vessel or gong was immersed in a boiling bath of aged tamarind pulp (pulin-kuzhambu). The concentrated natural tartaric acid dissolved superficial copper oxides without pitting the underlying tin-rich alloy.\n\nFollowing acid pickling, artisans burnished the surface using wooden blocks coated with a paste of fine coconut-shell charcoal, sesame oil, and river silt. This progressive micro-polishing achieved a mirror-like specular reflection (kannadi-palupu) that effectively sealed the metal pores against atmospheric tarnishing and humidity."
    },
    {
        "file": "knowledge/inscriptions/insc-nachiyarkoil-chola-bell-metal-artisan-guild-and-lamp-endowments.md",
        "slug": "insc-nachiyarkoil-chola-bell-metal-artisan-guild-and-lamp-endowments",
        "category": "inscription",
        "name_en": "Nachiyarkoil Chola Epigraphs on Bell-Metal Artisan Guilds & Brazen Lamp Charters",
        "name_ta": "நாச்சியார்கோவில் சோழர் கல்வெட்டுகள் - வெண்கலக் கைவினைஞர் கம்மாளப் பட்டயங்கள்",
        "era": "Imperial Chola Era",
        "year_start": 980,
        "year_end": 1150,
        "thinai": "marutham",
        "summary_en": "Inscriptions from the Nachiyarkoil temple complex documenting imperial charters granted to the Kammalar metalworking guilds for producing ceremonial bell-metal lamps, bells, and musical gongs.",
        "summary_ta": "நாச்சியார்கோவிலில் உள்ள சோழர் கல்வெட்டுகள்; பித்தளை மற்றும் வெண்கலப் பொருட்கள் செய்யும் கம்மாளர்களுக்கு வரி விலக்கும், விளக்குகள் மற்றும் சேகண்டிகள் செய்யும் உரிமையையும் வழங்குகின்றன.",
        "sources": [
            "South Indian Inscriptions Vol VIII",
            "Nachiyarkoil Brass Heritage Inscriptions"
        ],
        "content": "# Nachiyarkoil Chola Bell-Metal Artisan Inscriptions\n\nSituated near Kumbakonam, Nachiyarkoil has been renowned for a millennium as the epicenter of Tamil brass and bell-metal casting.\n\nThese medieval Chola epigraphs detail the establishment of artisan quarters (kammaranjeri) dedicated to master casters. The imperial court granted the guild tax remissions on furnace charcoal and imported tin ingots, recognizing their indispensable role in producing monumental deepams (ornate multi-tiered standing lamps) and resonant temple chegandi gongs.\n\nThe inscriptions record that the guild held corporate seals and maintained standards of alloy purity, imposing severe fines on any smith who adulterated sacred bell-metal with lead or zinc."
    },
    {
        "file": "knowledge/inscriptions/insc-kumbakonam-brazen-gong-and-temple-chime-consecration-epigraphs.md",
        "slug": "insc-kumbakonam-brazen-gong-and-temple-chime-consecration-epigraphs",
        "category": "inscription",
        "name_en": "Kumbakonam Epigraphs on Brazen Gong Consecration & Liturgical Acoustics",
        "name_ta": "கும்பகோணம் கல்வெட்டுகள் - வெண்கல சேகண்டி பிரதிஷ்டை மற்றும் நாத மணி தான சாசனம்",
        "era": "Later Chola to Pandya Era",
        "year_start": 1050,
        "year_end": 1280,
        "thinai": "marutham",
        "summary_en": "Stone inscriptions across Kumbakonam temple plinths recording the ritual consecration of massive bell-metal gongs, specifying acoustic tuning requirements and perpetual bell-ringer endowments.",
        "summary_ta": "கும்பகோணக் கோயில் கல்வெட்டுகள் வெண்கல சேகண்டிகளைப் பிரதிஷ்டை செய்து, குறிப்பிட்ட நாத சுருதியில் மணி அடிப்பதற்கான நிவந்தங்களை விவரிக்கின்றன.",
        "sources": [
            "Kumbakonam Temple Inscriptions Corpus",
            "Epigraphia Indica Vol VII"
        ],
        "content": "# Kumbakonam Brazen Gong Consecration Epigraphs\n\nCarved on the granite mandapams of historic Kumbakonam temples, these inscriptions provide rare documentary evidence on liturgical acoustics.\n\nThe epigraphs commemorate donations of heavy bell-metal chegandis presented by royal officers and merchant guilds. The records stipulate the exact weight of the bronze alloy (often over fifty palams of refined metal) and identify the specific raga and tonal pitch to which the instrument was tuned.\n\nLand endowments were assigned to provide daily rice and betel allowances for hereditary bell-ringers (mani-kaaran), tasked with sounding the hourly chimes and festival alarms that governed the rhythm of civic life."
    },
    {
        "file": "knowledge/characters/char-nachiyarkoil-master-bell-metal-founder-kansa-sthapati.md",
        "slug": "char-nachiyarkoil-master-bell-metal-founder-kansa-sthapati",
        "category": "character",
        "name_en": "Nachiyarkoil Master Bell-Metal Founder & Icon Caster (Kansa Sthapati)",
        "name_ta": "நாச்சியார்கோவில் தலைமை வெண்கல வார்ப்புச் சிற்பி",
        "era": "Imperial Chola Era",
        "year_start": 1010,
        "year_end": 1080,
        "thinai": "marutham",
        "summary_en": "Chief metallurgical sthapati celebrated for formulating high-tin acoustic alloys, calculating thermal expansion of ceramic molds, and casting monumental bell-metal temple lamps and gongs.",
        "summary_ta": "வெள்ளீய வெண்கலக் கலவை விகிதத்தை முறைப்படுத்தி, பெருங்கோயில் குத்துவிளக்குகள் மற்றும் சேகண்டிகளை வார்ப்பதில் வல்லமை பெற்ற தலைமைச் சிற்பி.",
        "sources": [
            "Chola Sthapati Guild Genealogy",
            "Artisans of the Cauvery Delta"
        ],
        "content": "# Nachiyarkoil Master Bell-Metal Founder (Kansa Sthapati)\n\nThe Kansa Sthapati was a master metallurgist who blended rigorous geometric proportions with empirical furnace chemistry. Operating large foundry hearths at Nachiyarkoil, he supervised the melting of red copper and imported Malacca tin in graphite crucibles.\n\nHe possessed an extraordinary tactile ability to judge the temperature of molten bronze by its color, executing the critical pour in a continuous, unbroken stream to prevent slag entrapment or gas porosity.\n\nUnder his guidance, apprentices mastered the art of beta-phase quenching, plunging glowing red gongs into cold temple tank water at the exact split-second required to lock in crystalline acoustic brilliance without cracking the brittle metal."
    },
    {
        "file": "knowledge/characters/char-swamimalai-sacred-bronze-and-gong-acoustic-tuner-oli-aasaan.md",
        "slug": "char-swamimalai-sacred-bronze-and-gong-acoustic-tuner-oli-aasaan",
        "category": "character",
        "name_en": "Swamimalai Sacred Bronze & Gong Acoustic Tuner (Oli Aasaan)",
        "name_ta": "சுவாமிமலை வெண்கல நாத ஒலி இசைப் பேராசிரியர் மற்றும் சீரமைப்பாளர்",
        "era": "Chola to Nayaka Era",
        "year_start": 1080,
        "year_end": 1160,
        "thinai": "marutham",
        "summary_en": "Legendary acoustic tuner and musical metallurgist who tuned temple bell-metal gongs, cymbals, and carillon chimes to classical Carnatic shrutis through microscopic lathe-scraping.",
        "summary_ta": "வெண்கல சேகண்டிகள், கைத்தாளங்கள் மற்றும் மணிகளை மரக்கடைசல் மீது ஏற்றி, நுண்ணியமாகச் சீவி செவிக்கு இனிய தேவ நாத சுருதியை உருவாக்கும் ஒலி ஆசான்.",
        "sources": [
            "Carnatic Acoustic Treatises",
            "Swamimalai Sthapati Archives"
        ],
        "content": "# Swamimalai Gong Acoustic Tuner (Oli Aasaan)\n\nThe Oli Aasaan was the ultimate master of musical resonance in ancient Tamilakam. Stationed at the bronze-casting center of Swamimalai, he worked on newly cast gongs and cymbals that had undergone thermal quenching.\n\nUsing sensitive iron tuning forks and his trained ear, he struck different nodal points on the gong's rim, listening for stray dissonant overtones. With sharp tempered scrapers (surandi), he gently shaved off fractions of a millimeter of bronze from specific concentric bands along the back of the disc.\n\nThrough this iterative micro-tuning, he aligned the fundamental and harmonic frequencies, transforming a raw piece of cast metal into a sacred acoustic transducer that vibrated with divine sonic clarity."
    },
    {
        "file": "knowledge/places/place-nachiyarkoil-ancient-chola-bell-metal-and-brass-haven.md",
        "slug": "place-nachiyarkoil-ancient-chola-bell-metal-and-brass-haven",
        "category": "place",
        "name_en": "Nachiyarkoil: Ancient Chola Bell-Metal & Resonant Gong Metallurgy Haven",
        "name_ta": "நாச்சியார்கோவில் - பண்டைய சோழர் வெண்கல மணி மற்றும் நாத சேகண்டித் தளம்",
        "era": "Prehistoric to Modern Era",
        "year_start": -300,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "World-famous metallurgy settlement in Thanjavur district, celebrated for over a millennium as the preeminent heartland of Tamil high-tin bell-metal, resonant temple gongs, and ornate brass craft.",
        "summary_ta": "தஞ்சாவூர் காவிரிப் படுகையில் அமைந்துள்ள உலகப் புகழ்பெற்ற வெண்கலத் தளம்; ஆயிரம் ஆண்டுகளுக்கும் மேலாக நாத சேகண்டி மற்றும் பித்தளைக் கைவினைத் தொழிற்துறையின் தலைமை மையம்.",
        "sources": [
            "Imperial Gazetteer of India (Tanjore)",
            "Geographical Indications Registry (Nachiyarkoil Kuthuvilakku)"
        ],
        "content": "# Nachiyarkoil: Ancient Chola Bell-Metal Haven\n\nLocated in the Kaveri delta near Kumbakonam, Nachiyarkoil has enjoyed unbroken global fame as the center of South Indian acoustic bronze and brass craftsmanship. The town's artisanal prominence is anchored in its proximity to the fine river silts of the Cauvery, which provide the ideal molding clay for cire-perdue casting.\n\nFor centuries under the patronage of Chola, Pandya, and Nayaka monarchs, hereditary communities of Pathers and Sthapatis have maintained roaring foundries along its streets. Their signature creations—the massive resonant chegandi gongs and multi-branched ceremonial brass lamps—adorn temple sanctums from Madurai to Southeast Asia.\n\nToday, Nachiyarkoil holds protected Geographical Indication status, preserving the uninterrupted lineage of ancient Tamil pyrotechnic and acoustic metallurgy."
    }
]
EDGES = [
    [
        "text-silappadikaram-temple-bronze-gongs-and-bell-metal-chimes-poetry",
        "documents_acoustics",
        "concept-acoustically-tuned-temple-resonance-gongs-chegandi-and-sekkandi",
        "historical_proof",
        "Post-Sangam Era",
        "Silappadikaram poetically describes the shimmering resonance of temple bell-metal chegandi gongs.",
        "Silappadikaram Arangetrukathai"
    ],
    [
        "concept-high-tin-bell-metal-alloy-metallurgy-and-beta-phase-quenching-venkalam",
        "material_foundation",
        "concept-acoustically-tuned-temple-resonance-gongs-chegandi-and-sekkandi",
        "historical_proof",
        "Prehistoric to Modern Era",
        "High-tin 78:22 bronze alloy and 650°C water quenching provided the low acoustic damping needed for gongs.",
        "Metallurgical Heritage of South India"
    ],
    [
        "concept-high-tin-bell-metal-alloy-metallurgy-and-beta-phase-quenching-venkalam",
        "cast_via",
        "concept-lost-wax-cire-perdue-solid-bronze-iconography-madhuchishta-vidhana",
        "historical_proof",
        "Sangam to Chola Era",
        "High-tin bronze and sacred panchaloha idols were cast using the cire-perdue lost-wax mold process.",
        "Kasyapa Silpa"
    ],
    [
        "concept-acoustically-tuned-temple-resonance-gongs-chegandi-and-sekkandi",
        "finished_with",
        "concept-abrasive-tamarind-and-charcoal-mirror-polishing-venkala-palupu",
        "historical_proof",
        "Prehistoric to Modern Era",
        "Resonant gongs and cymbals were pickled in tamarind acid and mirror-polished with fine charcoal paste.",
        "Traditional Acoustic Bronze Instruments of Tamil Nadu"
    ],
    [
        "char-nachiyarkoil-master-bell-metal-founder-kansa-sthapati",
        "operates_in",
        "place-nachiyarkoil-ancient-chola-bell-metal-and-brass-haven",
        "historical_proof",
        "Imperial Chola Era",
        "Master bell-metal founders directed large furnace foundries and mold yards at Nachiyarkoil.",
        "Chola Sthapati Guild Genealogy"
    ],
    [
        "char-nachiyarkoil-master-bell-metal-founder-kansa-sthapati",
        "perfects_alloy",
        "concept-high-tin-bell-metal-alloy-metallurgy-and-beta-phase-quenching-venkalam",
        "historical_proof",
        "Imperial Chola Era",
        "The master founder calibrated the exact 78:22 copper-tin ratio and executed beta-phase water quenching.",
        "Artisans of the Cauvery Delta"
    ],
    [
        "char-swamimalai-sacred-bronze-and-gong-acoustic-tuner-oli-aasaan",
        "tunes_instrument",
        "concept-acoustically-tuned-temple-resonance-gongs-chegandi-and-sekkandi",
        "historical_proof",
        "Chola to Nayaka Era",
        "The acoustic tuner scraped concentric bands on cast gongs to align fundamental liturgical harmonics.",
        "Carnatic Acoustic Treatises"
    ],
    [
        "insc-nachiyarkoil-chola-bell-metal-artisan-guild-and-lamp-endowments",
        "attests_place",
        "place-nachiyarkoil-ancient-chola-bell-metal-and-brass-haven",
        "historical_proof",
        "Imperial Chola Era",
        "Nachiyarkoil inscriptions confirm Chola imperial charters granted to the bell-metal artisan guilds.",
        "South Indian Inscriptions Vol VIII"
    ],
    [
        "insc-kumbakonam-brazen-gong-and-temple-chime-consecration-epigraphs",
        "records_consecration",
        "concept-acoustically-tuned-temple-resonance-gongs-chegandi-and-sekkandi",
        "historical_proof",
        "Later Chola to Pandya Era",
        "Kumbakonam epigraphs document the consecration of tuned bell-metal gongs and bell-ringer endowments.",
        "Kumbakonam Temple Inscriptions Corpus"
    ],
    [
        "place-nachiyarkoil-ancient-chola-bell-metal-and-brass-haven",
        "preserves_lineage",
        "concept-lost-wax-cire-perdue-solid-bronze-iconography-madhuchishta-vidhana",
        "historical_proof",
        "Prehistoric to Modern Era",
        "Nachiyarkoil preserves the unbroken multi-generational heritage of lost-wax casting and bell-metal metallurgy.",
        "Geographical Indications Registry (Nachiyarkoil Kuthuvilakku)"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Ancient Tamil Bell-Metal Metallurgy & Resonant Gongs into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Ancient Tamil Bell-Metal Metallurgy & Resonant Gongs Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
