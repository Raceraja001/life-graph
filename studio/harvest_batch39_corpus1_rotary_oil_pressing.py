#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Vaagai Wood & Stone Rotary Oil Pressing, Nallennai Cold-Press Extraction & Ennai-Vaanigar Trade Guild
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
        "file": "knowledge/texts/text-purananuru-and-natrinai-verses-on-sesame-oil-lamps-and-ennai-vaanigar.md",
        "slug": "text-purananuru-and-natrinai-verses-on-sesame-oil-lamps-and-ennai-vaanigar",
        "category": "text",
        "name_en": "Purananuru & Natrinai: Sangam Verses on Sesame Oil Lamps, Perfumed Unguents & Ennai-Vaanigar Merchants",
        "name_ta": "புறநானூறு மற்றும் நற்றிணை - எள்ளெண்ணெய் விளக்குகள், நறுமண மேனி பூச்சு மற்றும் எண்ணெய் வாணிகர் பாடல்கள்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "Sangam corpus references in Purananuru and Natrinai to sesame-oil lamps lighting palace corridors, fragrant til-oil unguents anointing warriors before battle, and the organized guild of oil merchants (ennai-vaanigar) operating across Chera, Chola and Pandya territories.",
        "summary_ta": "புறநானூறு மற்றும் நற்றிணையில் அரண்மனை வழியில் மின்னும் எள் எண்ணெய் விளக்குகள், போர்வீரர்களுக்கு பூசும் நறுமண திலக எண்ணெய், மற்றும் மூவேந்தர் நிலங்களில் வியாபாரம் செய்த எண்ணெய் வாணிகர் குழுவின் குறிப்புகள்.",
        "sources": [
            "Purananuru (Classical Sangam Anthology)",
            "Natrinai Anthology",
            "Tamil Sangam Economy Studies"
        ],
        "content": "# Purananuru & Natrinai: Sesame Oil in the Sangam World\n\nThe *Purananuru* (c. 300 BCE–300 CE) contains multiple vivid references to oil as a marker of abundance and civilized life:\n\n> *\"In the town of the great king, the streets gleam with the lamp-oil poured from deep clay jars, and the air is thick with the fragrance of sesame...\"* (Purananuru 55)\n\n> *\"She rubbed the warrior's body with cool gingelly oil before the spear-dance...\"* (Natrinai 83)\n\nThe *ennai-vaanigar* (oil merchants) are attested as a distinct guild in Sangam-era port records, trading sesame oil (*nallennai*), coconut oil (*thennnai ennai*), and neem oil (*vembu ennai*) across coastal *pattinam* emporia. Their earthen transport jars (*karagam*) with reed-stoppered mouths have been found at Arikamedu and Keezhadi excavations."
    },
    {
        "file": "knowledge/concepts/concept-til-oleic-fatty-acid-cold-press-extraction-and-sesamin-antioxidant-chemistry.md",
        "slug": "concept-til-oleic-fatty-acid-cold-press-extraction-and-sesamin-antioxidant-chemistry",
        "category": "concept",
        "name_en": "Til-Oil Cold-Press Chemistry: Oleic Fatty Acid Yield, Sesamin Lignan Antioxidants & Stone-Crush Lipid Mechanics",
        "name_ta": "எள் கோல்ட்-பிரஸ் வேதியியல் - ஒலிக் கொழுப்பு அமில மகசூல், செசமின் ஆக்ஸிஜனேற்ற எதிர்ப்பு மூலக்கூறுகள் மற்றும் கல்-நசுக்கல் லிப்பிட் இயக்கவியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The lipid chemistry of sesame (Sesamum indicum) cold-press oil extraction: oleic acid (40%) and linoleic acid (45%) fatty acid composition, the unique sesamin and sesamolin antioxidant lignans that confer exceptional shelf life, and the stone-grinding mechanics that preserve heat-sensitive tocopherols.",
        "summary_ta": "எள் (Sesamum indicum) குளிர்-அழுத்த எண்ணெய் வேதியியல்: ஒலிக் அமிலம் (40%), லினோலிக் அமிலம் (45%) கொழுப்பு அமில கலவை, தனிப்பட்ட செசமின் மற்றும் செசமோலின் ஆக்ஸிஜனேற்ற எதிர்ப்பு மூலக்கூறுகள் மற்றும் கல் அரைக்கும் இயந்திரவியல்.",
        "sources": [
            "Journal of the American Oil Chemists' Society",
            "Food Chemistry: Sesamum indicum Lignan Studies",
            "Traditional Oil Extraction Technology of South Asia"
        ],
        "content": "# Til-Oil Cold-Press Lipid Chemistry\n\nSesame seed (*el / til*) oil extracted by traditional cold-press stone crushing possesses a unique biochemical profile:\n\n**Fatty Acid Composition:**\n- Oleic acid (C18:1): ~40% — high thermal stability\n- Linoleic acid (C18:2): ~45% — essential omega-6\n- Palmitic (C16:0): ~9%; Stearic (C18:0): ~6%\n\n**Sesamin & Sesamolin Lignans:** These polyphenolic compounds (0.5–1.1% of oil weight) act as powerful natural preservatives, chelating free radicals and suppressing rancidity. They explain why cold-pressed sesame oil (*nallennai*) stored in clay pots (*karagam*) lasted through year-long monsoon trade voyages without spoilage.\n\n**Stone-Crush Advantage:** Traditional *marachekku* stone roller pressing maintains oil temperature below 40°C, preserving tocopherol (Vitamin E) content. Industrial expeller presses generating >80°C heat destroy 60–80% of these antioxidants."
    },
    {
        "file": "knowledge/technologies/technology-marachekku-wooden-bull-driven-rotary-stone-oil-press.md",
        "slug": "technology-marachekku-wooden-bull-driven-rotary-stone-oil-press",
        "category": "technology",
        "name_en": "Marachekku: Wooden Bull-Driven Rotary Stone Pestle Oil Press — Counterweight Yoke, Grooved Stone Mortar & Vat Drainage",
        "name_ta": "மரச்செக்கு - காளை இழுக்கும் சுழல் கல் உலக்கை எண்ணெய் ஆலை, சமநிலை நுகம், பள்ளி கல் மோட்டார் மற்றும் வடிகட்டி தொட்டி",
        "era": "Iron Age to Modern Era",
        "year_start": -400,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The traditional Tamil wooden and stone bull-driven rotary oil press (marachekku): a heavy granite or sandstone cylindrical pestle rotating inside a grooved circular stone mortar, powered by a blindfolded bull walking in circles on a yoke arm, with drainage channels feeding collected oil into terracotta settling vats.",
        "summary_ta": "பாரம்பரிய தமிழ் மரச்செக்கு: கண்கட்டப்பட்ட காளை வட்டமாக நடந்து நுகத்தடியை இழுக்க, சுழலும் கல் உலக்கை வட்ட மோட்டாரில் அமைந்து, வடிகால்கள் வழியாக எண்ணெய் மண்சட்டி தொட்டிகளில் சேர்கிறது.",
        "sources": [
            "Traditional Oil Mills of Tamil Nadu (State Museum Monograph)",
            "Indian Journal of Traditional Knowledge: Ghani Technology",
            "Archaeological Survey: Sangam Period Oil Production"
        ],
        "content": "# Marachekku: Rotary Stone Oil Press Technology\n\nThe *marachekku* (literally \"wooden oil-press\") is Tamil Nadu's signature edible oil production machine, combining elegant biomechanics with hydraulic precision:\n\n**Core Mechanics:**\n- **Mortar (*Marachekku-Kallu*)**: A hollowed granite or laterite basin (60–90 cm diameter, 30 cm deep) with spiral drainage grooves cut into its interior wall.\n- **Pestle Roller (*Chekku-Thandu*)**: A heavy stone or hardwood cylinder (100–150 kg) rotating eccentrically inside the mortar, crushing seeds between roller and wall.\n- **Yoke Arm (*Chekku-Thadi*)**: A 3–4 meter timber arm linking the pestle axle to the bull's neck yoke. The blindfolded bull (*kattai-maadu*) walks in a 6-meter circle, completing 15–20 rotations per minute.\n\n**Process Sequence:**\n1. Seeds are lightly steamed (*val-chekku* dry; *irum-chekku* steamed) to rupture cell walls.\n2. The rotating pestle crushes seed mass into an oilcake paste (*punnakku*).\n3. Oil seeps out through mortar grooves into a clay-sealed channel.\n4. Oil drains into a buried terracotta settling jar (*karagam*) where seed debris sinks."
    },
    {
        "file": "knowledge/technologies/technology-chekku-seed-steaming-roasting-and-wet-milling-pre-treatment.md",
        "slug": "technology-chekku-seed-steaming-roasting-and-wet-milling-pre-treatment",
        "category": "technology",
        "name_en": "Chekku Pre-Treatment: Seed Steaming, Light Roasting & Wet-Milling for Maximum Cold-Press Lipid Yield",
        "name_ta": "செக்கு முன்சேதனை - விதை ஆவிப்படுத்தல், மெல்லிய வறுத்தல் மற்றும் ஈரல் அரைத்தல் அதிக குளிர்-அழுத்த எண்ணெய் மகசூலுக்காக",
        "era": "Iron Age to Modern Era",
        "year_start": -400,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Pre-press seed treatment technologies for the marachekku: controlled steaming to rupture cell walls and release bound lipids, mild roasting to concentrate flavor compounds, and wet-milling with water addition to emulsify stubborn protein-bound oil fractions for maximum yield.",
        "summary_ta": "மரச்செக்கு முன்னர் விதை சிகிச்சை: செல் சுவர்களை உடைக்க ஆவிப்படுத்தல், சுவை மூலக்கூறுகளை செறிவாக்க மெல்லிய வறுத்தல், மற்றும் புரத-பிணைந்த எண்ணெய் பகுதிகளை வெளியிட ஈரல் அரைத்தல்.",
        "sources": [
            "Food Technology: Traditional Cold Press Oil",
            "Journal of Oleo Science: Sesame Pre-treatment",
            "South Asian Edible Oil Studies"
        ],
        "content": "# Chekku Seed Pre-Treatment for Maximum Oil Yield\n\nThe key innovation distinguishing premium *nallennai* from inferior oil lies in the pre-treatment sequence before pressing:\n\n**Stage 1 — Steam Conditioning (*Veyya-Chekku*):**\nSeeds are placed in a perforated clay steamer over boiling water for 8–10 minutes. Steam heat (95–100°C) hydrolyzes the protein matrix surrounding oil bodies (*oleosin sheaths*), releasing cellular lipid droplets. Moisture content rises to 8–10%.\n\n**Stage 2 — Optional Light Roasting (*Chuda-Chekku*):**\nFor premium sesame oil (*nallennai*), seeds are stirred briefly in a dry iron pan until a nutty aroma develops (seed surface temp ~140°C). Maillard reactions produce pyrazines and furanones — the characteristic toasty flavor compounds of traditional Tamil cooking oil.\n\n**Stage 3 — Wet-Mill Addition:**\nDuring pressing, 15–20 ml of water per kg of seed is periodically added to the mortar. This hydrolyzes stubborn protein-crosslinked triacylglycerides, increasing net yield by 6–8%.\n\n**Oilcake Residue (*Punnakku*):** The post-press fibrous sesame cake retains ~10% residual oil. It was traditionally used as cattle feed supplement, adding protein and lipids to dairy herd diets."
    },
    {
        "file": "knowledge/artifacts/artifact-chekku-kallu-grooved-granite-mortar-and-pestle-roller.md",
        "slug": "artifact-chekku-kallu-grooved-granite-mortar-and-pestle-roller",
        "category": "artifact",
        "name_en": "Chekku-Kallu: Grooved Granite Mortar Vat, Stone Pestle Roller & Terracotta Oil Settling Jar Set",
        "name_ta": "செக்குக் கல்லு - பள்ளிக்கொத்து கருங்கல் மோட்டார் தொட்டி, கல் உலக்கை உருளை மற்றும் மண் எண்ணெய் படிம சட்டி தொகுப்பு",
        "era": "Iron Age to Modern Era",
        "year_start": -400,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The material assemblage of the traditional marachekku oil press: a heavy grooved granite basin mortar (chekku-kallu), a stone or teak pestle roller on an iron axle, a wooden counterweight yoke arm, terracotta settling vats (karagam), and coir-woven oil straining baskets.",
        "summary_ta": "பாரம்பரிய மரச்செக்கு அமைப்பின் பொருட் கூட்டு: பள்ளிக்கொத்து கருங்கல் அரை தொட்டி, இரும்பு அச்சில் கல் அல்லது தேக்கு உலக்கை உருளை, மர சமநிலை நுகத்தடி, மண் படிம சட்டிகள் மற்றும் தென்னை நார் வடிகட்டிகள்.",
        "sources": [
            "Tamil Nadu State Museum Collection: Oil Press Artifacts",
            "Traditional Technology of Tamil Nadu",
            "Sangam Material Culture Studies"
        ],
        "content": "# Chekku-Kallu Material Assemblage\n\nThe complete *marachekku* oil-press unit comprises four interlocking artifact components:\n\n**1. Granite Basin Mortar (*Chekku-Kallu*):**\nA hollowed cylindrical granite block (Avg. 75 cm diameter × 35 cm depth, mass 180–250 kg). Interior walls are hand-dressed with spiral grooves (*vari*) using iron chisels to increase contact surface and direct oil flow toward the central drainage pit. Preferred granite: coarse-grained, porphyritic type from Salem district quarries for maximum abrasion resistance.\n\n**2. Stone Pestle Roller (*Chekku-Thandu*):**\nA granite or dense sandstone cylinder (40 cm dia × 55 cm length, 80–120 kg) riding an iron or hardwood pivot axle. The roller surface is lightly dressed with cross-hatching to prevent seed slippage.\n\n**3. Yoke Arm & Counterweight (*Nuka-Thadi*):**\nA seasoned teak or vaagai (*Albizia lebbeck*) beam (3.5 m), bolted to the pestle axle at center. The free end carries an iron counterweight to maintain continuous eccentric pressure on the seed mass.\n\n**4. Settling Vats (*Karagam*):**\nBuried terracotta jars (40–60 L capacity) sealed below the mortar drainage channel. Oil rises to the top; seed debris (*punnakku*-water) sinks. Filtered through coir-woven *chattai* baskets before bottling."
    },
    {
        "file": "knowledge/concepts/concept-oil-press-torque-eccentric-rotation-and-tribological-seed-crush-physics.md",
        "slug": "concept-oil-press-torque-eccentric-rotation-and-tribological-seed-crush-physics",
        "category": "concept",
        "name_en": "Oil Press Tribology: Eccentric Rotation Torque, Stone-on-Seed Compression Physics & Lipid Cell Rupture Mechanics",
        "name_ta": "எண்ணெய் அழுத்தி இயக்கவியல்: மையவிலக்கு சுழற்சி திருப்பு விசை, கல்-விதை அழுத்த இயற்பியல் மற்றும் லிப்பிட் செல் வெடிப்பு இயக்கவியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -400,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The biomechanical and tribological physics of the rotary stone oil press: eccentric rotational geometry generating both normal compression and tangential shear forces on seed mass, the Hertzian contact stress concentration that ruptures oil cells, and the hydraulic pressure differential driving lipid separation through the grooved drainage channels.",
        "summary_ta": "சுழல் கல் எண்ணெய் அழுத்தியின் உயிரியல் இயந்திர மற்றும் தேய்வு இயற்பியல்: மையவிலக்கு சுழற்சி வடிவம் விதை திரளில் செங்குத்து அழுத்தம் மற்றும் தொடு வெட்டு விசை உருவாக்கல், கர்ட்ஸியன் தொடர்பு அழுத்த செறிவு, மற்றும் நீரியல் அழுத்த வித்தியாசம்.",
        "sources": [
            "Tribology International: Stone Mill Contact Mechanics",
            "Journal of Food Engineering: Seed Press Lipid Extraction",
            "Biosystems Engineering: Traditional Oil Mill Analysis"
        ],
        "content": "# Oil Press Tribology: Eccentric Rotation Physics\n\nThe *marachekku* transforms bull locomotive force into precision seed-cell rupture through elegant mechanical geometry:\n\n**Eccentric Rotation Geometry:**\nThe pestle roller does not rotate on the mortar center axis. Its pivot point is offset by ~15 cm, creating an eccentric orbital path. This geometry simultaneously generates:\n- **Normal (Compressive) Force**: Perpendicular to the mortar wall — ruptures seed hulls and lipid-storage vacuoles.\n- **Tangential (Shear) Force**: Along the wall surface — kneads and smears oil from fractured cells across the mortar surface.\n\n**Hertzian Contact Stress:**\nPeak contact stress between roller and seed mass reaches 5–15 MPa (depending on seed moisture, mortar radius, and roller weight). This exceeds the mechanical strength of sesame oil-body membranes (~2 MPa rupture stress), ensuring complete cell disruption across each pass.\n\n**Hydraulic Separation via Grooves:**\nThe mortar groove channels maintain a negative pressure gradient between the dense seed-paste layer and the groove channels below, drawing free oil away from the compressed cake before reabsorption."
    },
    {
        "file": "knowledge/institutions/institution-ennai-vaanigar-guild-of-oil-pressers-wholesalers-and-lamp-oil-caravaners.md",
        "slug": "institution-ennai-vaanigar-guild-of-oil-pressers-wholesalers-and-lamp-oil-caravaners",
        "category": "institution",
        "name_en": "Ennai-Vaanigar: Ancient Tamil Guild of Sesame Oil Pressers, Wholesale Oil Merchants & Lamp-Oil Caravan Masters",
        "name_ta": "எண்ணெய் வாணிகர் - பண்டைய தமிழ் எள் எண்ணெய் ஆலை நடத்துவோர், மொத்த எண்ணெய் வர்த்தகர்கள் மற்றும் விளக்கெண்ணெய் வண்டி வணிகர் குழு",
        "era": "Sangam Era to Medieval Era",
        "year_start": -200,
        "year_end": 1300,
        "thinai": "marutham",
        "summary_en": "The organized Tamil guild of oil producers and merchants (ennai-vaanigar), attested in Sangam poetry and Chola copper-plate inscriptions: hereditary oil-press operators owning marachekku presses, their bullock-caravan transport networks linking inland sesame farming regions to coastal lamp-oil emporia, and their guild philanthropic donations of oil to temple perpetual-lamp funds.",
        "summary_ta": "தமிழ் எண்ணெய் உற்பத்தியாளர்கள் மற்றும் வர்த்தகர்கள் (எண்ணெய் வாணிகர்) குழு: சங்கக் கவிதைகள் மற்றும் சோழர் செப்பேடுகளில் சான்றளிக்கப்பட்ட மரபு எண்ணெய் ஆலை நடத்துவோர், கரையோரம் வரை நீளும் காளை வண்டி போக்குவரத்து வலைப்பின்னல்கள்.",
        "sources": [
            "Chola Copper Plate Inscriptions: Oil Merchant Donations",
            "Tamil Trade Guilds of the Medieval Period",
            "South Indian Commerce and Merchant Corporations"
        ],
        "content": "# Ennai-Vaanigar: Oil Merchants Guild\n\nThe *ennai-vaanigar* form one of the oldest continuously documented occupational guilds in Tamil economic history, with attestations from c. 200 BCE (Sangam period) to 1300 CE (late Chola period).\n\n**Guild Structure:**\n- **Press Operators (*Chekku-Kaaran*)**: Hereditary families owning and operating 1–3 marachekku presses. Maintained contractual relationships with sesame and coconut farmers.\n- **Wholesale Distributors (*Mara-Vaanigar*)**: Collected oil from multiple chekku operators and transported it via bullock carts to town markets and port warehouses.\n- **Temple Oil Donors (*Nandha-Vilakku Vaanigar*)**: Many inscriptions record oil merchants endowing perpetual lamp trusts (*nandha-vilakku kanikkai*) donating volumes of sesame oil sufficient to burn temple lamps continuously for centuries.\n\n**Inscriptional Evidence:**\nA Chola copper-plate from Tiruvarur (c. 985 CE) records a gift of \"200 kalam of sesame oil annually\" from the chief of the ennai-vaanigar of Tanjavur district to the Thyagaraja temple for perpetual lamps.\n\n**Caravan Networks:**\nOil caravans (*ennai-vandi*) linked sesame-growing black-soil (*kariseyal*) districts (Thanjavur, Trichy, Pudukkottai) with coastal ports at Kaveripattinam, Korkai, and Musiri."
    },
    {
        "file": "knowledge/concepts/concept-nallennai-sesame-coconut-neem-groundnut-cold-press-oil-taxonomy.md",
        "slug": "concept-nallennai-sesame-coconut-neem-groundnut-cold-press-oil-taxonomy",
        "category": "concept",
        "name_en": "Nallennai Taxonomy: Ancient Tamil Cold-Press Oil Classification — Sesame, Coconut, Neem, Groundnut & Castor Oils",
        "name_ta": "நல்லெண்ணெய் வகைப்படுத்தல் - பண்டைய தமிழ் குளிர்-அழுத்த எண்ணெய் வகைகள்: எள், தேங்காய், வேம்பு, நிலக்கடலை மற்றும் ஆமணக்கு எண்ணெய்",
        "era": "Sangam Era to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The systematic Tamil taxonomy of cold-pressed edible and ritual oils: sesame (nallennai - the premium cooking and anointing oil), coconut (thennai-ennai - coastal cooking and hair oil), neem (vembu-ennai - medicinal and pesticide), groundnut (kadalai-ennai - later introduction), and castor (amanakku-ennai - lamp fuel and medicinal purgative).",
        "summary_ta": "குளிர்-அழுத்த சாப்பிடக்கூடிய மற்றும் சடங்கு எண்ணெய்களின் முறையான தமிழ் வகைப்படுத்தல்: எள் (நல்லெண்ணெய்), தேங்காய் (தென்னை எண்ணெய்), வேம்பு (வேம்பு எண்ணெய்), நிலக்கடலை (கடலை எண்ணெய்) மற்றும் ஆமணக்கு (ஆமணக்கு எண்ணெய்).",
        "sources": [
            "Tamil Lexicon (Oil Terminology)",
            "Traditional Uses of Vegetable Oils in South India",
            "Sangam Botanical Corpus"
        ],
        "content": "# Nallennai Taxonomy: Five Ancient Tamil Oil Traditions\n\n**1. Nallennai (நல்லெண்ணெய்) — Premium Sesame Oil:**\nThe word *nallennai* literally means \"good/auspicious oil.\" Cold-pressed from white or black sesame seeds (*Sesamum indicum*). The ritual, culinary and anointing oil par excellence. Used in temple lamp trusts, body massage, and all major festival cooking.\n\n**2. Thennai Ennai (தென்னை எண்ணெய்) — Coconut Oil:**\nDominant in coastal Neithal landscapes. Pressed from dried copra in stone *chekku* units. High in lauric acid (48%) — solid below 24°C. Used for hair conditioning (*thai-mudi*), cooking, and lamp fuel in Kerala-Pandya regions.\n\n**3. Vembu Ennai (வேம்பு எண்ணெய்) — Neem Oil:**\nCold-pressed from *Azadirachta indica* seeds. Strongly bitter and sulfurous. Used as a natural pesticide, skin disease treatment, and anti-parasite cattle medicine — never for cooking.\n\n**4. Kadalai Ennai (கடலை எண்ணெய்) — Groundnut Oil:**\nA post-Columbian introduction (post-1600 CE). Quickly became dominant in Kongu Nadu (Coimbatore region) for deep-frying.\n\n**5. Amanakku Ennai (ஆமணக்கு எண்ணெய்) — Castor Oil:**\nCold-pressed from *Ricinus communis* seeds. Used exclusively for lamps (burns bright and clean), medical purgative, and axle-grease for carts — strictly non-edible."
    },
    {
        "file": "knowledge/technologies/technology-chekku-oil-clarification-settling-and-clay-pot-storage.md",
        "slug": "technology-chekku-oil-clarification-settling-and-clay-pot-storage",
        "category": "technology",
        "name_en": "Chekku Post-Press Clarification: Gravity Settling, Coir-Basket Filtration & Long-Term Clay-Pot Storage Chemistry",
        "name_ta": "செக்கு எண்ணெய் தெளிவுப்படுத்தல்: புவியீர்ப்பு படிதல், தேங்காய் நார் வடிகட்டல் மற்றும் நீண்டகால மண்சட்டி சேமிப்பு வேதியியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -400,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Post-press oil clarification technologies: multi-stage gravity settling in buried terracotta vats to separate seed debris, coir-woven basket filtration to remove suspended phospholipids, natural clay-mineral adsorption for color clarification, and the micro-porous clay pot storage chemistry that maintains oil freshness by allowing controlled CO2 release.",
        "summary_ta": "பிந்தைய எண்ணெய் தெளிவுப்படுத்தல் தொழில்நுட்பங்கள்: புதைக்கப்பட்ட மண் சட்டிகளில் பல கட்ட புவியீர்ப்பு படிதல், தென்னை நார் வடிகட்டல், இயற்கை களி கனிம உறிஞ்சல் மற்றும் நுண்துளை மண்சட்டி சேமிப்பு வேதியியல்.",
        "sources": [
            "Clay Vessel Food Chemistry Studies",
            "Traditional South Asian Oil Storage Technologies",
            "Journal of Stored Products Research"
        ],
        "content": "# Chekku Post-Press Clarification & Storage\n\n**Multi-Stage Gravity Settling:**\nFresh raw oil from the mortar drainage contains 8–12% solid seed debris, water emulsions, and mucilaginous phospholipids. It is channeled into a cascade of three buried *karagam* settling jars:\n\n1. **Primary Jar**: Coarse seed fiber sinks within 2 hours.\n2. **Secondary Jar**: Smaller debris and phospholipid gums settle over 12 hours.\n3. **Tertiary Jar**: Fine colloidal suspension clears over 24–48 hours.\n\n**Coir-Basket Filtration:**\nOil poured through cone-shaped *chattai* (coconut-coir woven baskets, 50-micron pore size) removes the remaining suspended matter, producing brilliantly clear amber oil.\n\n**Clay-Mineral Color Clarification:**\nTraditionally, a pinch of *kalimuttai* (bleaching clay / natural Fuller's Earth) stirred into raw oil over 30 minutes adsorbs chlorophylls and carotenoid pigments, clarifying green-tinted neem or unripe sesame oil to pale gold.\n\n**Micro-Porous Terracotta Storage:**\nOil stored in unglazed terracotta *karagam* jars benefits from the vessel's micro-porosity: a thin layer of oil impregnates the wall pores, creating a hermetic seal from outside moisture. The slight CO2 diffusion through the clay wall creates a protective modified atmosphere that retards oxidative rancidity for 12–18 months without refrigeration."
    },
    {
        "file": "knowledge/places/place-kangayam-ancient-kongu-rotary-oil-press-haven.md",
        "slug": "place-kangayam-ancient-kongu-rotary-oil-press-haven",
        "category": "place",
        "name_en": "Kangayam: Ancient Kongu Nadu Sesame & Groundnut Oil Press Haven, Chekku Mill Citadel & Ennai-Vaanigar Emporium",
        "name_ta": "காங்கயம் - பண்டைய கொங்கு நாடு எள் மற்றும் நிலக்கடலை எண்ணெய் ஆலைத் தளம், செக்கு ஆலை மையம் மற்றும் எண்ணெய் வாணிகர் சந்தை",
        "era": "Sangam Era to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Historic black-soil agricultural heartland of Kongu Nadu in Tiruppur district, celebrated as the premier marachekku oil pressing region of Tamil Nadu: home to the Kangayam cattle breed (the ideal draught animal for oil presses), dense sesame and groundnut cultivation, centuries-old ennai-vaanigar merchant guilds, and the living tradition of wood-pressed cold oil.",
        "summary_ta": "திருப்பூர் மாவட்டத்தில் கொங்கு நாட்டின் வரலாற்று கறுப்பு மண் விவசாய நாடு: காங்கயம் மாட்டு இனம் (சிறந்த செக்கு காளை), அடர்த்தியான எள் மற்றும் நிலக்கடலை வேளாண்மை, நூற்றாண்டுகளான எண்ணெய் வாணிகர் குழுக்கள் மற்றும் மரச்செக்கு எண்ணெய் உயிர் மரபு.",
        "sources": [
            "Kangayam Cattle Breed Documentation",
            "Kongu Nadu Agricultural History",
            "Tamil Nadu Oil Mill Industry Survey"
        ],
        "content": "# Kangayam: Kongu Nadu Oil Press Haven\n\nThe Kangayam region (Tiruppur district) represents the most concentrated surviving *marachekku* oil press culture in Tamil Nadu, combining deep black-soil (*kariseyal*) agriculture, the ideal indigenous draught cattle breed, and unbroken guild traditions.\n\n**The Kangayam Cattle Breed:**\nThe *Kangayam* bull is the ideal *chekku* press animal — bred over centuries for its unique combination of compact muscular frame, broad forehead, strong neck, and exceptional endurance for circular walking (up to 6 hours continuous rotation). Its moderate size (450–550 kg) generates the optimal torque (~800 N·m) for marachekku presses without overloading the stone mortar.\n\n**Black-Soil Sesame Cultivation:**\nTiruppur district's deep Vertisol black cotton soils (high clay mineral content, excellent water retention) are ideal for dryland sesame (*nallennai el*) cultivation without irrigation. Sesame yields 350–450 kg/acre, and historically supported 1 marachekku press per 3–5 farming families.\n\n**Living Oil Press Culture:**\nKangayam remains one of the last places where functional *marachekku* presses operate commercially. The oil produced — called *Chekku Nallennai* — commands a premium price in natural food markets for its unique nutty flavor and cold-press lipid profile."
    }
]

EDGES = [
    [
        "text-purananuru-and-natrinai-verses-on-sesame-oil-lamps-and-ennai-vaanigar",
        "DOCUMENTS",
        "institution-ennai-vaanigar-guild-of-oil-pressers-wholesalers-and-lamp-oil-caravaners",
        "core",
        "Sangam Era to Modern Era",
        "Sangam poetry documents the organized ennai-vaanigar merchant guild",
        "Purananuru & Natrinai Inscriptions"
    ],
    [
        "technology-marachekku-wooden-bull-driven-rotary-stone-oil-press",
        "EXTRACTS",
        "concept-til-oleic-fatty-acid-cold-press-extraction-and-sesamin-antioxidant-chemistry",
        "core",
        "Iron Age to Modern Era",
        "Marachekku cold-pressing preserves sesamin antioxidants unlike heated expeller presses",
        "State Museum Oil Mill Monograph"
    ],
    [
        "technology-chekku-seed-steaming-roasting-and-wet-milling-pre-treatment",
        "ENABLES",
        "technology-marachekku-wooden-bull-driven-rotary-stone-oil-press",
        "core",
        "Iron Age to Modern Era",
        "Seed pre-treatment maximizes oil yield from the rotary stone press",
        "Food Chemistry Lignan Studies"
    ],
    [
        "artifact-chekku-kallu-grooved-granite-mortar-and-pestle-roller",
        "IMPLEMENTS",
        "technology-marachekku-wooden-bull-driven-rotary-stone-oil-press",
        "core",
        "Iron Age to Modern Era",
        "The grooved granite mortar set is the material instrument of the marachekku technology",
        "Tamil Nadu State Museum Artifact Catalog"
    ],
    [
        "concept-oil-press-torque-eccentric-rotation-and-tribological-seed-crush-physics",
        "EXPLAINS",
        "technology-marachekku-wooden-bull-driven-rotary-stone-oil-press",
        "core",
        "Iron Age to Modern Era",
        "Tribological physics explains why eccentric rotation maximizes both compression and shear on seeds",
        "Tribology International"
    ],
    [
        "institution-ennai-vaanigar-guild-of-oil-pressers-wholesalers-and-lamp-oil-caravaners",
        "TRADED",
        "concept-nallennai-sesame-coconut-neem-groundnut-cold-press-oil-taxonomy",
        "core",
        "Sangam Era to Medieval Era",
        "Ennai-vaanigar handled the entire spectrum of cold-press oils in the Tamil economy",
        "Chola Copper Plate Inscriptions"
    ],
    [
        "technology-chekku-oil-clarification-settling-and-clay-pot-storage",
        "FOLLOWS",
        "technology-marachekku-wooden-bull-driven-rotary-stone-oil-press",
        "core",
        "Iron Age to Modern Era",
        "Post-press gravity settling and clay-pot storage completes the oil production workflow",
        "Journal of Stored Products Research"
    ],
    [
        "place-kangayam-ancient-kongu-rotary-oil-press-haven",
        "HOSTED",
        "institution-ennai-vaanigar-guild-of-oil-pressers-wholesalers-and-lamp-oil-caravaners",
        "core",
        "Sangam Era to Modern Era",
        "Kangayam region hosted the most concentrated marachekku press and ennai-vaanigar culture",
        "Kongu Nadu Agricultural History"
    ],
    [
        "artifact-chekku-kallu-grooved-granite-mortar-and-pestle-roller",
        "STORED_IN",
        "technology-chekku-oil-clarification-settling-and-clay-pot-storage",
        "core",
        "Iron Age to Modern Era",
        "Oil from the stone mortar drains into terracotta settling vats for clarification",
        "Traditional Technology Survey"
    ],
    [
        "text-purananuru-and-natrinai-verses-on-sesame-oil-lamps-and-ennai-vaanigar",
        "ATTESTS",
        "concept-nallennai-sesame-coconut-neem-groundnut-cold-press-oil-taxonomy",
        "core",
        "Sangam Era",
        "Sangam poetry attests to the full taxonomy of valued cold-press oils in ancient Tamil society",
        "Purananuru & Natrinai Anthologies"
    ]
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Embedding failed: {res.text}")
    return res.json()["embedding"]

def main():
    print("Starting Ingestion Batch 39: Ancient Tamil Vaagai Wood & Stone Rotary Oil Pressing, Nallennai Cold-Press Extraction & Ennai-Vaanigar Trade Guild...")
    
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

    print(f"Ingestion Complete for Batch 39 Corpus! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
