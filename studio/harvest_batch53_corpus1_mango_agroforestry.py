#!/usr/bin/env python3
"""
Harvester: Batch 53 - Ancient Tamil Mango Cultivar Biodiversity, Maavadu Brine Osmosis, Maavilai-Toranam Hygiene & Mukkani Orchard Lore
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
        "slug": "text-sangam-corpus-on-thema-pulima-mango-groves-and-maavadu-pickles",
        "category": "text",
        "file": "text-sangam-corpus-on-thema-pulima-mango-groves-and-maavadu-pickles.md",
        "name_en": "Kuruntokai, Ainkurunuru & Perumpanarruppadai on Thema, Pulima & Maavadu Mango Lore",
        "name_ta": "குறுந்தொகை, ஐங்குறுநூறு மற்றும் பெரும்பாணாற்றுப்படையில் தேமா, புளிமா மற்றும் மாவடு இலக்கிய மரபு",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "Classical Tamil poetic accounts in Kuruntokai, Ainkurunuru, Perumpanarruppadai, and Purananuru celebrating sweet honey-mangoes (thema), tart culinary mangoes (pulima), copper-red spring mango shoots (maanthalir), and crisp tender baby mangoes (maavadu).",
        "summary_ta": "குறுந்தொகை, ஐங்குறுநூறு, பெரும்பாணாற்றுப்படை மற்றும் புறநானூறு ஆகிய சங்க இலக்கியங்களில் தேமா, புளிமா, மாந்தளிர், குயில் பாடும் மாந்தோப்புகள் மற்றும் மாவடு ஊறுகாய் பற்றிய பதிவுகள்.",
        "sources": [
            "Kuruntokai",
            "Ainkurunuru",
            "Perumpanarruppadai",
            "Purananuru"
        ],
        "content": "# Sangam Corpus on Thema, Pulima & Maavadu Mango Lore\n\nAs the first and foremost member of the sacred **Mukkani** triad (*Maa, Pala, Vazhai*), the mango tree (*maa* / *chutham*, *Mangifera indica*) pervades classical Tamil poetry and aesthetics:\n\n**Literary Attestations:**\n- **Kuruntokai & Ainkurunuru on *Thema* and *Pulima***: Sangam poets classify mango trees into two sensory archetypes—**Thema** (honey-sweet dessert mango whose wind-fallen ripe fruits perfume canal banks) and **Pulima** (tart, green-fleshed mango prized for tangy curries and pregnant women's cravings *masakkai*).\n- **Perumpanarruppadai & Purananuru on *Maavadu***: The poems describe slicing tender green baby mangoes (*vadu* / *maavadu*, compared to a dark-lashed eye split down the middle) and steeping them in earthen jars to serve with rice gruel (*kanji*) and buttermilk, while copper-tinted young mango leaves (*maanthalir*) serve as the canonical simile for a heroine's glowing complexion."
    },
    {
        "slug": "concept-mangifera-indica-myrcene-ocimene-aroma-mangiferin-xanthones-and-thema-pulima-prosody",
        "category": "concept",
        "file": "concept-mangifera-indica-myrcene-ocimene-aroma-mangiferin-xanthones-and-thema-pulima-prosody.md",
        "name_en": "Mangifera indica Terpene Aroma Chemistry, Mangiferin Xanthones & Thema-Pulima Prosody",
        "name_ta": "மாவின் டெர்பீன் நறுமண வேதியியல், மாங்கிஃபெரின் சத்து மற்றும் யாப்பிலக்கணத் தேமா-புளிமா வாய்பாடு",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "mullai",
        "summary_en": "Phytochemistry and linguistic legacy of Tamil mango biodiversity: cultivar-specific monoterpene hydrocarbons (beta-myrcene, beta-ocimene, carene) in resin canals, bioactive C-glucosyl xanthone mangiferin in leaves/bark, and the Thema/Pulima metrical mnemonic in Tamil Yappilakkanam prosody.",
        "summary_ta": "தமிழ்நாட்டு மாம்பழ ரகங்களின் மைர்சீன்-ஆசிமீன் நறுமண வேதியியல், மாவிலையிலுள்ள மாங்கிஃபெரின் (Mangiferin) நோய் எதிர்ப்புப் பொருள் மற்றும் தமிழ் யாப்பிலக்கணத்தின் நேரசை-நிரையசை வாய்பாடான தேமா-புளிமா தத்துவம்.",
        "sources": [
            "Tolkappiyam Seyyuliyal & Yapparungala Karigai",
            "Phytochemistry of Mangifera indica Volatiles and Mangiferin",
            "South Indian Mango Germplasm Descriptors"
        ],
        "content": "# Mangifera indica Terpene Chemistry, Mangiferin & Prosodic Mnemonics\n\nIn Tamil civilization, the mango tree uniquely bridges organic phytochemistry and the mathematical architecture of classical verse (*Yappilakkanam*):\n\n**Biochemical & Prosodic Principles:**\n- **Resin-Duct Terpenes (*Vadusap / Paal*)**: The distinctive piney-floral aroma of South Indian cultivars (*Imam Pasand*, *Banganapalli*, *Sendura*, *Malgova*, *Nadusalai*, and aromatic *Kili-Mooku* / *Totapuri*) arises from volatile monoterpenes—chiefly **$\\beta$-myrcene**, **$(E)$-$\\beta$-ocimene**, and **$\\delta$-3-carene**—concentrated in the anastomosing laticifer ducts of the peel and pedicel sap.\n- **Mangiferin Xanthone Pharmacology**: Mango bark, tender leaves (*maanthalir*), and dried seed kernels (*maangottai*) are rich in **mangiferin** (a heat-stable C-glucosyl xanthone) and gallotannins with potent antioxidant, anti-diarrheal, and alpha-glucosidase-inhibiting properties.\n- **Thema & Pulima in Tamil Prosody (*Asai* & *Seer*)**: So foundational were sweet (*thema*) and sour (*pulima*) mangoes to Tamil cognition that grammarians codified them as the primary metrical formulas (*vaippadu*) for two-syllable feet (*Eerasai Seer*): **The-Ma** (`நேர் + நேர்`) and **Puli-Ma** (`நிரை + நேர்`)."
    },
    {
        "slug": "concept-maavadu-pre-lignified-endocarp-physiology-and-hypertonic-brine-osmosis",
        "category": "concept",
        "file": "concept-maavadu-pre-lignified-endocarp-physiology-and-hypertonic-brine-osmosis.md",
        "name_en": "Maavadu Pre-Lignified Endocarp Physiology, Pedicel Sap-Plug Sealing & Hypertonic Brine Osmosis",
        "name_ta": "மாவடுவின் முற்றாத விதையோடு உயிரியலும் காம்புப் பால் அடைப்பு மற்றும் உப்புநீர் சவ்வூடுபரவல் அறிவியலும்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "marutham",
        "summary_en": "Food science of whole pickled baby mangoes (maavadu): harvesting aromatic riverine/hill landraces 25–35 days after fruit-set before stone endocarp lignification, retaining a 5 mm pedicel stub to prevent brine waterlogging, and plasmolyzing tissue via hypertonic salt-castor-oil osmosis.",
        "summary_ta": "மாவடு ஊறுகாய் அறிவியல்: உள்ளிருக்கும் கொட்டை (Endocarp) கடினமாவதற்கு முன் காம்புடன் பறித்து, ஆமணக்கு எண்ணெய் மற்றும் கல் உப்பு மூலம் சவ்வூடுபரவல் (Osmosis) வழியாகச் சுருங்கச் செய்து ஓராண்டு கெடாமல் காக்கும் நுட்பம்.",
        "sources": [
            "Traditional Tamil Pickling & Preservation Science",
            "Developmental Anatomy of Mangifera indica Fruit",
            "Siddha Culinary Dietetics (Oorugai Gunam)"
        ],
        "content": "# Maavadu Pre-Lignified Physiology & Hypertonic Brine Osmosis\n\nTransforming crisp, resinous baby green mangoes (**Maavadu**) into wrinkled, spice-infused morsels that stay crunchy for a full year without vinegar or refrigeration relies on precise plant anatomy and osmotic physics:\n\n**Anatomical & Osmotic Mechanics:**\n- **The Pre-Lignification Window**: During the first 25 to 35 days after pollination (in *Panguni–Chithirai*), the mango fruit consists of a turgid green mesocarp enclosing a tender white cotyledon (*paruppu*) before the stony endocarp (*odu*) deposits lignin sclereids. Once the stone hardens, the fruit becomes *maangai* rather than *maavadu*.\n- **Why the 5 mm Stem Stub (*Kambu*) Must Remain**: If the pedicel is plucked flush, the exposed vascular bundle canal floods the soft seed cavity with water, causing internal rot. Leaving a short stem stub sealed by its own coagulated terpene latex (*paal*) forces all salt and spice transport to occur strictly by **trans-epidermal osmosis**.\n- **Hypertonic Plasmolysis & Castor-Oil Film**: Tossing fresh *maavadu* first in a thin film of cold-pressed castor oil (*amanakku-ennai*) and coarse crystal sea-salt (*kal-uppu*) creates a hypertonic exterior ($\\sim 18\\text{--}22\\%\\ \\text{NaCl}$). Cellular water diffuses outward through the semi-permeable skin—forming the aromatic golden brine **maavadu-neer**—while salt, mustard, and red chilli antimicrobials diffuse inward, dropping water activity ($a_w$) below microbial survival thresholds."
    },
    {
        "slug": "technology-naattu-maa-rootstock-inarching-approach-grafting-and-orchard-smudge-smoking",
        "category": "technology",
        "file": "technology-naattu-maa-rootstock-inarching-approach-grafting-and-orchard-smudge-smoking.md",
        "name_en": "Naattu-Maa Rootstock Approach-Grafting (Ottu-Kattuthal) & Orchard Smudge-Smoking (Pugai-Mooduthal)",
        "name_ta": "நாட்டு மா ஒட்டுக்கட்டுதல் (இணை ஒட்டு) மற்றும் மாந்தோப்புப் புகைமூட்டிப் பூக்கவைக்கும் தொழில்நுட்பம்",
        "era": "Medieval to Modern Era",
        "year_start": 1000,
        "year_end": 2025,
        "thinai": "mullai",
        "summary_en": "Horticultural technologies of Tamil mango orchardists: propagating true-to-type elite cultivars by approach-grafting (ottu-kattuthal) onto drought-hardy deep-taproot wild seedling stocks (naattu-maa), and burning damp leaf-litter smudge fires beneath canopies in Margazhi to trigger synchronized flowering.",
        "summary_ta": "மாந்தோப்புச் சாகுபடித் தொழில்நுட்பம்: ஆணிவேர் கொண்ட நாட்டு மாங்கன்றுகளில் உயர்தர ரகங்களை இணை ஒட்டுக் (Approach Grafting) கட்டுதல் மற்றும் மார்கழி-தை மாதங்களில் புகைமூட்டி ஒரே நேரத்தில் பூக்க வைத்தல்.",
        "sources": [
            "Krishnagiri and Salem Mango Nursery Traditions",
            "South Indian Horticultural Grafting Manuals",
            "Plant Physiology of Ethylene Smudge-Smoking in Mango"
        ],
        "content": "# Approach-Grafting (Ottu-Kattuthal) & Orchard Smudge-Smoking\n\nBecause monoembryonic South Indian table mangoes (*Imam Pasand*, *Alphonso*, *Banganapalli*, *Sendura*) do not breed true from seed, Tamil nursery masters (*Ottu-Kattuvor*) perfected vegetative grafting and floral induction:\n\n**Orchard Propagation & Management:**\n1. **Naattu-Maa Taproot Stock & Approach-Grafting (*Inarching*)**: Stones of hardy, polyembryonic local wild mangoes (*naattu-maa* or *kuruvi-maa*) are germinated in earthen pots or nursery beds to establish a deep, drought-resistant taproot system. The potted one-year seedling is raised on a bamboo platform beside a low branch of the mother scion tree; matching 6 cm bark-and-cambium slices are pared from both stems, bound tightly together with *vazhai-naar* and cow-dung clay plaster (*mann-kattu*) for 60 days until vascular cambium union occurs, and then severed into an independent *ottu-maa* sapling.\n2. **Canopy Smudge-Smoking (*Pugai-Mooduthal*)**: In *Margazhi–Thai* (December–January), orchardists rake dry mango leaves and damp straw into slow-smouldering heaps upwind beneath the canopy for several dawns. The warm smoke contains **ethylene gas** (which stimulates uniform floral bud break across the crown) while aromatic leaf tars fumigate and drive off destructive mango hoppers (*Idioscopus* spp.)."
    },
    {
        "slug": "technology-chithirai-maavadu-bharani-brine-curing-and-sun-dried-maa-vathal-preservation",
        "category": "technology",
        "file": "technology-chithirai-maavadu-bharani-brine-curing-and-sun-dried-maa-vathal-preservation.md",
        "name_en": "Chithirai Maavadu Bharani Brine Curing, Maa-Vathal Sun Dehydration & Thiraattai Fruit Leather",
        "name_ta": "சித்திரை மாவடு ஜாடிப் பதப்படுத்துதல், மாவத்தல் வெயில் உலர்த்தல் மற்றும் மாம்பழத் திரட்டை தயாரிப்பு",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "marutham",
        "summary_en": "Post-harvest preservation technologies converting seasonal summer mango gluts into year-round pantry staples: layering castor-oiled whole maavadu in glazed stoneware bharani jars with dry-ground mustard-chilli-turmeric paste, curing salted green slices into maa-vathal, and sun-drying ripe pulp sheets.",
        "summary_ta": "கோடைக்கால மா விளைச்சலை ஆண்டு முழுவதும் சேமிக்கும் தொழில்நுட்பம்: பீங்கான் ஜாடியில் (பரணி) மாவடு ஊறுகாய் போடுதல், பச்சை மாங்காயை உப்பிட்டு உலர்த்தி மாவத்தல் ஆக்குதல் மற்றும் மாம்பழச் சாற்றைப் பாயில் ஊற்றி உலர்த்தும் மாம்பழத் திரட்டை.",
        "sources": [
            "Traditional Tamil Household Pantry (Ugranam) Manuals",
            "Chettinad and Tanjore Culinary Preservation Records",
            "Post-Harvest Processing of Mango in Tamil Nadu"
        ],
        "content": "# Maavadu Bharani Curing, Maa-Vathal Drying & Thiraattai Leather\n\nBecause the mango harvest peaks sharply between *Chithirai* and *Aani* (April–June), Tamil households engineered three distinct preservation pathways for the three maturity stages of the fruit:\n\n**Three-Stage Preservation Workflow:**\n1. **Bharani Curing of *Maavadu* (Tender Baby Stage)**: Cleaned, dry *vadu* mangoes with 5 mm stems are rubbed with castor oil, turmeric, and sea salt in a ceramic *bharani* jar and tossed daily for 4 days until half-shrunken in their own exuded brine (*vadu-neer*). Raw mustard seeds (*kadugu*) and sun-dried red chillies are dry-pounded without water, mixed into the brine, and sealed under a clean cotton cloth tied around the jar neck.\n2. **Salted *Maa-Vathal* (Hard Green *Maangai* Stage)**: Tart *pulima* green mangoes are pared into longitudinal wedges, steeped overnight in concentrated salt brine with turmeric, and sun-dried on palmyra mats for 5 days until bone-dry and leathery—stored to sour monsoon *vathakuzhambu* and fish curries.\n3. **Maambazha-Thiraattai (Ripe *Maambazham* Stage)**: Strained golden pulp of ripe mangoes is spread in thin layers over oiled palmyra mats or brass plates day after day under blazing sun, building up translucent, chewy sheets of natural mango fruit leather."
    },
    {
        "slug": "artifact-bharani-cured-maavadu-salted-maa-vathal-and-maambazha-thiraattai-fruit-leather",
        "category": "artifact",
        "file": "artifact-bharani-cured-maavadu-salted-maa-vathal-and-maambazha-thiraattai-fruit-leather.md",
        "name_en": "Bharani-Cured Maavadu, Salted Maa-Vathal Wedges, Maangottai Kernel Flour & Manga-Inji",
        "name_ta": "பரணி மாவடு, உப்புக் கண்ட மாவத்தல், மாங்கொட்டைப் பருப்பு மாவு மற்றும் மாங்காய்-வெல்லப் பச்சடி",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "marutham",
        "summary_en": "Culinary and medicinal artifacts derived from the mango fruit: porcelain bharani jars of wrinkled aromatic maavadu in mustard-chilli brine, sun-cured maa-vathal wedges, astringent decorticated mango-seed kernel powder (maangottai chooranam), and Tamil New Year Maangai-Pachadi.",
        "summary_ta": "மாங்காய் மற்றும் மாம்பழத்திலிருந்து உருவாக்கப்படும் உணவு மற்றும் மருந்துப் பொருட்கள்: பரணி மாவடு, மாவத்தல், வயிற்றுப்போக்கை நிறுத்தும் மாங்கொட்டைப் பருப்புச் சூரணம் மற்றும் சித்திரைப் புத்தாண்டு மாங்காய்-வேப்பம்பூ பச்சடி.",
        "sources": [
            "Perumpanarruppadai",
            "Agathiyar Gunavagadam (Maangottai Paruppu)",
            "Tamil Culinary Heritage Inventories"
        ],
        "content": "# Bharani Maavadu, Maa-Vathal, Maangottai Flour & Maangai-Pachadi\n\nEvery anatomical layer of the mango fruit—from skin to stony seed kernel—is transformed into a functional culinary or therapeutic artifact in Tamil material culture:\n\n**Culinary & Apothecary Artifacts:**\n- **Wrinkled *Maavadu* & *Vadu-Neer* Brine**: Prized for its piney-resinous crunch (*kuru-kuru*) alongside cooling buttermilk rice (*thayir-sadham*); even after the fruits are eaten, the remaining spiced brine (*vadu-thannir*) is mixed into steamed rice or used to season *arisi-upma*.\n- **Chithirai Puthandu *Maangai-Pachadi***: Prepared on Tamil New Year's Day by boiling tart green mango slices with sweet jaggery, bitter neem flowers (*veppampoo*), pungent green chilli, salt, and astringent mustard—uniting all **six tastes (*Arusuvai*)** as a philosophical emblem of equanimity through life's joys and trials.\n- **Maangottai-Paruppu (Decorticated Mango Seed Kernel)**: Stones left over from summer feasts are sun-dried, cracked open, leached in water, and roasted or ground into an astringent, mangiferin-rich flour (*maangottai chooranam*) prescribed in Siddha medicine for chronic dysentery, intestinal worms, and bleeding piles."
    },
    {
        "slug": "artifact-maavilai-toranam-doorway-festoons-poorna-kumbham-crowns-and-mango-wood-planks",
        "category": "artifact",
        "file": "artifact-maavilai-toranam-doorway-festoons-poorna-kumbham-crowns-and-mango-wood-planks.md",
        "name_en": "Maavilai-Toranam Doorway Festoons, Poorna-Kumbham Ritual Pot Crowns & Maa-Palagai Woodwork",
        "name_ta": "மாவிலைத் தோரணம், பூர்ணகும்பக் கலச மாவிலைக் கொத்து மற்றும் மாமரப் பலகைப் பொருட்கள்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "marutham",
        "summary_en": "Architectural and liturgical artifacts crafted from mango foliage and timber: turmeric-cord doorway festoons of glossy green mango leaves (maavilai-toranam), five-leaf crowns encircling sacred water pots (kalasam / poorna-kumbham), sacrificial homam fuel twigs (samithu), and water-resistant mango planks.",
        "summary_ta": "மாவிலை மற்றும் மாமரப் பொருட்கள்: மஞ்சள் கயிற்றில் கட்டப்படும் வாசல் மாவிலைத் தோரணம், கும்பக் கலசத்தில் வைக்கப்படும் மாவிலைக் கொத்து, வேள்விச் சமித்து மற்றும் நீரில் உளையாத மாமரப் பலகைகள்.",
        "sources": [
            "Agamic Kalasa Sthapana Manuals",
            "Traditional Tamil Architecture & Carpentry (Manaiyadi Sastram)",
            "Ethnobotany of Mangifera indica in South India"
        ],
        "content": "# Maavilai-Toranam Doorway Festoons, Kalasam Crowns & Maa-Palagai\n\nBeyond its fruit, the evergreen foliage and cross-grained timber of the mango tree occupy a central place in Tamil domestic architecture and ritual:\n\n**Ritual & Structural Artifacts:**\n- **Maavilai-Toranam (Threshold Leaf Festoon)**: Fresh, unblemished dark-green mango leaves are folded at the petiole neck around a turmeric-rubbed cotton string (*manjal-kayiru*) in odd counts (5, 7, 9, or 11 leaves) alternating with neem sprigs and marigold flowers, strung across the main lintel (*nilai-padi*) of homes and temple mandapas.\n- **Poorna-Kumbham / Kalasam Five-Leaf Crown**: In every Vedic and Agamic consecration (*kumbhabhishekam*) and wedding ritual, a cluster of five mango leaves (*pancha-pallava*) is arranged radially inside the neck of a water-filled brass or copper pot (*kumbham*) to cradle the husked coconut representing divine presence.\n- **Water-Resistant *Maa-Palagai* Timber**: Because seasoned mango wood resists underwater rot when submerged, traditional Tamil carpenters used thick *maa-palagai* planks for well-curb rings (*urai-kinaru* base frames), masula boat hull planking, and low dining stools (*manai-palagai*)."
    },
    {
        "slug": "concept-maavilai-toranam-mangiferin-antimicrobial-hygiene-and-poorna-kumbham-symbolism",
        "category": "concept",
        "file": "concept-maavilai-toranam-mangiferin-antimicrobial-hygiene-and-poorna-kumbham-symbolism.md",
        "name_en": "Maavilai-Toranam Antimicrobial Volatile Hygiene, Prolonged Photosynthesis & Auspicious Symbolism",
        "name_ta": "மாவிலைத் தோரணத்தின் நுண்ணுயிர் எதிர்ப்பு அறிவியலும் வாடிய பின்பும் ஒளிச்சேர்க்கை செய்யும் பண்பும்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "marutham",
        "summary_en": "Biophysical and higienic rationale behind hanging mango leaves (maavilai-toranam) at crowded festival thresholds and using them to sprinkle consecrated water: thick coriaceous cuticle retaining stomatal gas exchange after plucking, volatile terpene/mangiferin phytoncides, and evergreen fertility symbolism.",
        "summary_ta": "திருவிழா மற்றும் சுபநிகழ்ச்சிகளில் மக்கள் கூடும் வாசலில் மாவிலைத் தோரணம் கட்டுவதன் அறிவியல்: பறித்த பின்பும் பல நாட்கள் வாடாமல் ஆக்சிஜன் வெளியிடும் தடித்த இலை அமைப்பும், மாங்கிஃபெரின்-டெர்பீன் நுண்ணுயிர் எதிர்ப்பு ஆற்றலும்.",
        "sources": [
            "Siddha Environmental Hygiene & Dinacharya",
            "Antimicrobial Activity of Mangifera indica Leaf Volatiles",
            "Agamic Symbolism of Pancha-Pallava"
        ],
        "content": "# Maavilai-Toranam Hygiene, Leaf Physiology & Auspicious Symbolism\n\nWhy did ancient Tamil ritual custom mandate hanging *maavilai-toranam* across every doorway where large crowds gather for weddings and temple festivals?\n\n**Biophysical & Hygienic Principles:**\n- **Thick Coriaceous Cuticle & Prolonged Viability**: Unlike tender herb leaves that wilt within an hour of plucking, mature mango leaves possess a thick, leathery (coriaceous) epidermis and high internal turgor. Strung across a shaded doorway, detached mango leaves remain green, metabolically active, and capable of residual photosynthetic gas exchange for several days.\n- **Phytoncide & Mangiferin Sanitizing Action**: When brushed by entering guests or warmed by threshold oil lamps, the resin ducts in the petiole and leaf lamina release volatile monoterpenes ($\\alpha$-pinene, myrcene, caryophyllene) while the leaf surface carries antimicrobial **mangiferin** and **gallic acid**. Dipping a mango leaf into a copper *kalasam* to sprinkle *punyahavachanam* water transfers trace polyphenols into the droplets.\n- **Acoustic & Visual Crowd Calming**: The glossy emerald row across the lintel signals an auspicious (*mangala*) household in contrast to dry leaves hung during mourning."
    },
    {
        "slug": "institution-thoppu-kaani-mango-orchard-endowments-and-baramahal-grafting-nursery-guilds",
        "category": "institution",
        "file": "institution-thoppu-kaani-mango-orchard-endowments-and-baramahal-grafting-nursery-guilds.md",
        "name_en": "Thoppu-Kaani Royal Orchard Endowments, Maavadu-Mandi Brokers & Baramahal Grafting Guilds",
        "name_ta": "தோப்புக் காணி மானியங்கள், மாவடு மண்டி வணிகர்கள் மற்றும் பாரமஹால் ஒட்டு மாங்கன்றுப் பண்ணைக்குழுக்கள்",
        "era": "Chola to Modern Era",
        "year_start": 900,
        "year_end": 2025,
        "thinai": "mullai",
        "summary_en": "Institutional history of Tamil mango arboriculture: Chola, Nayak, and Tipu/Baramahal royal orchard tenures (thoppu-kaani / maniyam), specialized spring maavadu collectors sorting riverine vadu varieties, and hereditary grafting nursery guilds in Krishnagiri and Salem.",
        "summary_ta": "சோழர் மற்றும் நாயக்கர் கால மாந்தோப்புக் காணி மானியங்கள், கோடைக்கால மாவடு மண்டி வணிகர்கள் மற்றும் கிருஷ்ணகிரி-சேலம் பாரமஹால் பகுதியின் பாரம்பரிய ஒட்டு மாங்கன்றுப் பண்ணையாளர்கள்.",
        "sources": [
            "South Indian Inscriptions (Thoppu-Manyam & Nandavanam Grants)",
            "Salem and Baramahal Records (Mango Orchard Revenue & Tipu Graft Introductions)",
            "Krishnagiri Horticultural Guild Histories"
        ],
        "content": "# Thoppu-Kaani Orchard Endowments & Baramahal Grafting Guilds\n\nThe conservation and commercial distribution of dozens of specialized mango varieties across Tamilakam relied on long-term orchard tenures and nursery guilds:\n\n**Institutional & Commercial Framework:**\n- **Temple & Wayside *Thoppu-Kaani* Endowments**: Medieval Tamil inscriptions record tax-free *thoppu-manyam* grants to cultivators who planted and irrigated mango and iluppai avenues along pilgrim highways (providing deep shade for travellers and pack-bullocks) and supplied ripe *thema* mangoes for temple *Mukkani* offerings and summer *annadhanam*.\n- **Baramahal Royal Graft Collections**: During the 17th–18th centuries across the Salem–Krishnagiri *Baramahal* plateau and Vellore, royal horticulturists and local *ottu* nursery masters assembled elite scion mother-blocks (*Imam Pasand / Himayuddin*, *Malgova*, *Alphonso / Gundu*, *Bangalora / Totapuri*, *Nadusalai / Peter*), training generations of approach-grafters who shipped potted *ottu-maa* saplings across the Madras Presidency.\n- **Seasonal *Maavadu* Collectors**: In *Chithirai*, specialized women sorters and *mandi* brokers harvest specific small-seeded, high-latex riverine *vadu-maa* trees (*Kaveri-karai vadu* and *Salem vadu*), grading baby fruits by size within 12 hours of picking before the stems dry."
    },
    {
        "slug": "place-krishnagiri-ancient-baramahal-maa-mango-orchard-and-grafting-haven",
        "category": "place",
        "file": "place-krishnagiri-ancient-baramahal-maa-mango-orchard-and-grafting-haven.md",
        "name_en": "Krishnagiri: Ancient Baramahal Mango Orchard Belt, Approach-Grafting & Maavadu Haven",
        "name_ta": "கிருஷ்ணகிரி - பண்டைய பாரமஹால் மாந்தோப்புப் பீடபூமி, ஒட்டு மாங்கன்று மற்றும் மாவடுத் தளம்",
        "era": "Medieval to Modern Era",
        "year_start": 900,
        "year_end": 2025,
        "thinai": "mullai",
        "summary_en": "Historic granite-hill plateau in northern Kongu/Baramahal watered by the Thenpennaiyar river (12.5180° N, 78.2130° E), renowned as Tamil Nadu's foremost mango cultivating, approach-grafting (Santoshpuram/Kaveripattinam nurseries), and mango-processing heartland.",
        "summary_ta": "தென்பெண்ணையாற்றுப் படுகையில் பாறைக் குன்றுகளால் சூழப்பட்ட கிருஷ்ணகிரி பாரமஹால் பீடபூமி (12.5180° N, 78.2130° E): தமிழ்நாட்டின் முதன்மையான மாம்பழச் சாகுபடி, ஒட்டு மாங்கன்றுப் பண்ணைகள் மற்றும் மாவடு-மாவத்தல் பதப்படுத்தும் வரலாற்றுத் தளம்.",
        "sources": [
            "Baramahal Records (1792–1799)",
            "Salem and Krishnagiri District Gazetteers (Mango Horticulture)",
            "Horticultural Atlas of Tamil Nadu"
        ],
        "content": "# Krishnagiri: Ancient Baramahal Mango Orchard & Grafting Haven\n\nSituated at 480–650 metres elevation on the sun-drenched *Mullai* granite-gneiss plateau of the **Thenpennaiyar (Ponnaiyar) river basin** (12.5180° N, 78.2130° E), **Krishnagiri** (with Kaveripattinam, Pochampalli, and Bargur in the historic *Baramahal* tract) is the undisputed mango capital of Tamil Nadu:\n\n**Pedological & Horticultural Significance:**\n- **Ideal Red-Gravel *Mullai* Terroir**: Well-drained ferruginous red gravelly loams (*செம்மண் சரளை*), dry chilly *Margazhi* nights ($14^\\circ\\text{C}-16^\\circ\\text{C}$) that trigger profuse panicle differentiation without fungal anthracnose, and bright rainless *Chithirai* sunshine concentrate sugars and terpene volatiles in the fruit.\n- **Heirloom Cultivar & Grafting Hub**: Over 300 square kilometres of orchards around Krishnagiri, Kaveripattinam, and Santoshpuram conserve premier table and pickling cultivars (*Alphonso*, *Totapuri / Kili-Mooku*, *Banganapalli*, *Sendura*, *Malgova*, *Imam Pasand*, and aromatic *Vadu-Maa*), supported by hundreds of traditional approach-grafting nurseries and sun-curing yards."
    }
]

EDGES = [
    [
        "text-sangam-corpus-on-thema-pulima-mango-groves-and-maavadu-pickles",
        "describes",
        "concept-mangifera-indica-myrcene-ocimene-aroma-mangiferin-xanthones-and-thema-pulima-prosody",
        "material_culture",
        "Sangam Era",
        "Kuruntokai, Ainkurunuru, and Perumpanarruppadai establish the classical distinction between sweet Thema and tart Pulima mangoes that became the metrical feet of Tamil prosody.",
        "Kuruntokai & Ainkurunuru"
    ],
    [
        "text-sangam-corpus-on-thema-pulima-mango-groves-and-maavadu-pickles",
        "documents",
        "artifact-bharani-cured-maavadu-salted-maa-vathal-and-maambazha-thiraattai-fruit-leather",
        "material_culture",
        "Sangam Era",
        "Perumpanarruppadai and Purananuru document the pickling of tender green maavadu mangoes in earthen jars to serve with rice gruel.",
        "Perumpanarruppadai"
    ],
    [
        "concept-maavadu-pre-lignified-endocarp-physiology-and-hypertonic-brine-osmosis",
        "underpins",
        "technology-chithirai-maavadu-bharani-brine-curing-and-sun-dried-maa-vathal-preservation",
        "material_culture",
        "Sangam to Modern Era",
        "Pre-lignified endocarp harvesting, 5 mm latex-sealed stem stubs, and hypertonic salt-castor-oil osmosis govern bharani curing of maavadu.",
        "Tamil Pickling Science"
    ],
    [
        "technology-chithirai-maavadu-bharani-brine-curing-and-sun-dried-maa-vathal-preservation",
        "produces",
        "artifact-bharani-cured-maavadu-salted-maa-vathal-and-maambazha-thiraattai-fruit-leather",
        "material_culture",
        "Sangam to Modern Era",
        "Stoneware bharani brining and palmyra-mat sun dehydration produce year-round maavadu pickles, salted maa-vathal wedges, and maambazha-thiraattai fruit leather.",
        "Chettinad & Tanjore Pantry Records"
    ],
    [
        "concept-mangifera-indica-myrcene-ocimene-aroma-mangiferin-xanthones-and-thema-pulima-prosody",
        "guides",
        "technology-naattu-maa-rootstock-inarching-approach-grafting-and-orchard-smudge-smoking",
        "material_culture",
        "Medieval to Modern Era",
        "Preserving cultivar-specific myrcene/ocimene aroma profiles requires vegetative approach-grafting onto hardy naattu-maa seedling rootstocks.",
        "South Indian Horticultural Manuals"
    ],
    [
        "concept-maavilai-toranam-mangiferin-antimicrobial-hygiene-and-poorna-kumbham-symbolism",
        "explains",
        "artifact-maavilai-toranam-doorway-festoons-poorna-kumbham-crowns-and-mango-wood-planks",
        "material_culture",
        "Sangam to Modern Era",
        "Coriaceous leaf longevity and antimicrobial mangiferin/terpene phytoncides explain the hanging of maavilai-toranam doorway festoons and poorna-kumbham pot crowns.",
        "Siddha Dinacharya & Agamic Manuals"
    ],
    [
        "institution-thoppu-kaani-mango-orchard-endowments-and-baramahal-grafting-nursery-guilds",
        "practices",
        "technology-naattu-maa-rootstock-inarching-approach-grafting-and-orchard-smudge-smoking",
        "material_culture",
        "Medieval to Modern Era",
        "Hereditary nursery masters in the Baramahal belt practice approach-grafting (ottu-kattuthal) and winter canopy smudge-smoking.",
        "Baramahal Records"
    ],
    [
        "institution-thoppu-kaani-mango-orchard-endowments-and-baramahal-grafting-nursery-guilds",
        "supplies",
        "artifact-bharani-cured-maavadu-salted-maa-vathal-and-maambazha-thiraattai-fruit-leather",
        "material_culture",
        "Chola to Modern Era",
        "Orchard stewards and seasonal maavadu mandis supply graded baby vadu mangoes, table fruits, and dried kernels across Tamil Nadu.",
        "South Indian Inscriptions"
    ],
    [
        "institution-thoppu-kaani-mango-orchard-endowments-and-baramahal-grafting-nursery-guilds",
        "operates_in",
        "place-krishnagiri-ancient-baramahal-maa-mango-orchard-and-grafting-haven",
        "material_culture",
        "Medieval to Modern Era",
        "Grafting nursery guilds and mango orchardists operate across the Thenpennaiyar basin around Krishnagiri and Kaveripattinam.",
        "Salem & Krishnagiri Gazetteers"
    ],
    [
        "concept-mangifera-indica-myrcene-ocimene-aroma-mangiferin-xanthones-and-thema-pulima-prosody",
        "flourishes_in",
        "place-krishnagiri-ancient-baramahal-maa-mango-orchard-and-grafting-haven",
        "material_culture",
        "Medieval to Modern Era",
        "Well-drained red gravelly soils and crisp winter nights on the Krishnagiri plateau maximize terpene aroma and panicle flowering across Tamil mango cultivars.",
        "Horticultural Atlas of Tamil Nadu"
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
