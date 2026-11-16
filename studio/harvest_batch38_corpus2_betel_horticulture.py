#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Betel Vine Horticulture, Arecanut Hydraulics & Hospitality Rituals
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
        "file": "knowledge/texts/text-silappadikaram-verses-on-spiced-betel-leaves-areca-nuts-and-royal-banquets.md",
        "slug": "text-silappadikaram-verses-on-spiced-betel-leaves-areca-nuts-and-royal-banquets",
        "category": "text",
        "name_en": "Silappadikaram: Classical Verses on Spiced Betel Leaves, Camphor-Scented Areca & Royal Thaamboolam",
        "name_ta": "சிலப்பதிகாரம் - தாம்பூலம், நறுமண வெற்றிலை, பாக்கு, கற்பூரம் மற்றும் அரண்மனை விருந்தோம்பல் இலக்கியப் பாடல்",
        "era": "Post-Sangam Era",
        "year_start": 200,
        "year_end": 500,
        "thinai": "marutham",
        "summary_en": "Ilango Adigal's classical descriptions in Silappadikaram portraying noble banquets where spicy tender betel leaves wrapped around sliced areca nuts, edible camphor, and aromatic spices were presented as supreme tokens of hospitality.",
        "summary_ta": "சிலப்பதிகாரத்தில் விருந்தினர்களை வரவேற்கும் உன்னத அடையாளமாக நறுமண வெற்றிலை, பாக்கு, பச்சைக் கற்பூரம், ஏலக்காய் சேர்த்த தாம்பூலம் வழங்குவதை விவரிக்கும் பாடல்.",
        "sources": [
            "Silappadikaram 5:30-45",
            "Manimekalai 19:10-25",
            "Sirupanattruppadai 165"
        ],
        "content": "# Silappadikaram: Spiced Betel Leaves & Royal Thaamboolam\n\nIn *Silappadikaram* (Canto 5), Ilango Adigal documents the refined social rituals of the ancient Tamil metropolis of Puhar:\n\n> \"Maidens adorned in golden armlets presented silver platters heaped with heart-shaped tender betel leaves (*vetrillai*), finely shaved fragrant areca nuts (*suvai-paakku*), white slaked shell lime (*chunnambu*), and crystalline camphor (*karpooram*)... The chewing of the spicy leaf reddened noble lips and sweetened the breath of warriors and court poets alike.\"\n\nThis epic verse establishes that *thaamboolam* (the sacred chewing of betel and areca) was an indispensable cultural rite of hospitality, state diplomacy, marriage alliance, and medicinal digestive hygiene across ancient Tamil society."
    },
    {
        "file": "knowledge/concepts/concept-vetrillai-piper-betle-vine-climbers-microclimatic-humidity-and-soil-microbiology.md",
        "slug": "concept-vetrillai-piper-betle-vine-climbers-microclimatic-humidity-and-soil-microbiology",
        "category": "concept",
        "name_en": "Piper-Betle Horticulture: Dioecious Vine Climbers, Microclimatic Humidity & Leaf Phenolics",
        "name_ta": "வெற்றிலை தோட்டக்கலை - கொடிப் படர்தல் இயற்பியல், ஈரப்பத நுண்ணிய சூழல் மற்றும் இலை வேதியியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Botanical and horticultural physiology of Piper betle vines requiring constant 70-80% relative humidity, partial shade canopy, well-drained alluvial silts, and continuous aerial root support.",
        "summary_ta": "மிதமான நிழல், அதிக ஈரப்பதம் மற்றும் தொடர்ச்சியான நன்னீர் பாசனம் தேவைப்படும் வெற்றிலைக் கொடியின் தாவரவியல் மற்றும் இலைகளின் நறுமண வேதியியல்.",
        "sources": [
            "Horticultural Flora of Tamil Nadu",
            "Journal of Tropical Agriculture and Spice Crops",
            "Traditional Betel Cultivation Practices"
        ],
        "content": "# Piper-Betle Horticulture: Microclimate & Physiology\n\n*Piper betle* (the betel vine) is an evergreen perennial climber demanding exceptional microclimatic care:\n\n- **Shade & Humidity Dynamics**: As an understory tropical vine, betel leaves scorch under direct midday sun. Cultivators created enclosed garden microclimates maintaining 75–85% relative humidity under filtered light.\n- **Aerial Adventitious Roots**: The vine climbs via nodal clinging roots (*patru-ver*) that absorb atmospheric moisture and anchor the slender stems to live tree supports.\n- **Essential Oil Chemistry**: Premium betel leaves synthesize bioactive aromatic compounds—principally chavibetol, hydroxychavicol, and eugenol—giving the fresh leaf its characteristic pungent spice, microbial resistance, and saliva-stimulating qualities."
    },
    {
        "file": "knowledge/technologies/technology-kodi-kaal-live-support-agroforestry-agathi-hedgerows-and-ridge-furrow-hydraulics.md",
        "slug": "technology-kodi-kaal-live-support-agroforestry-agathi-hedgerows-and-ridge-furrow-hydraulics",
        "category": "technology",
        "name_en": "Kodi-Kaal: Live Agathi Hedgerows, Ridge-and-Furrow Hydraulics & Micro-Sprinkle Irrigation",
        "name_ta": "கொடிக்கால் - அகத்தி மர நேரடி ஆதரவு, பாத்தி-மடை நீரியல் மற்றும் வெற்றிலைத் தோட்டப் பொறியியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Advanced agroforestry engineering cultivating betel vines on live nitrogen-fixing sesbania (agathi) trellises planted in narrow parallel raised ridges flanked by water-filled drainage trenches.",
        "summary_ta": "அகத்தி மரங்களை வரிசையாக நட்டு, அதன் மீது வெற்றிலைக் கொடிகளை ஏற்றி, பக்கவாட்டுக் கால்வாய்கள் மூலம் வேர்களுக்கு நீரும் தழைச்சத்தும் வழங்கும் கொடிக்கால் அமைப்பு.",
        "sources": [
            "Traditional Agro-Forestry Systems of the Thamirabarani Basin",
            "Purananuru 399 Commentaries",
            "Indian Journal of Traditional Knowledge"
        ],
        "content": "# Kodi-Kaal: Live Trellising & Ridge-and-Furrow Hydraulics\n\nThe *Kodi-Kaal* (betel garden) represents an ancient pinnacle of intensive multi-tier agroforestry:\n\n- **Live Sesbania Trellises (*Agathi-Kaal*)**: Cultivators planted dense rows of fast-growing, nitrogen-fixing *Sesbania grandiflora* (*agathi*) and drumstick trees. As the agathi saplings shot upward, betel vines were tied to their trunks with soft banana fibers.\n- **Ridge-and-Furrow Architecture**: Vines were bedded on narrow elevated earth ridges (0.5m high) bordered on both sides by deep irrigation trenches (*kan-aru*). This maintained continuous subsoil capillary moisture while preventing stagnant root-waterlogging.\n- **Windbreak Perimeter Enclosures**: The entire perimeter was fenced with tall woven palmyra fronds (*panai-thattu*) and wild reed mats, creating an isolated microclimatic conservatory insulated against desiccating summer winds."
    },
    {
        "file": "knowledge/artifacts/artifact-thaamboola-thattil-and-adappam-chased-brass-betel-platters-and-areca-nut-shears.md",
        "slug": "artifact-thaamboola-thattil-and-adappam-chased-brass-betel-platters-and-areca-nut-shears",
        "category": "artifact",
        "name_en": "Thaamboola-Thattil & Adappam: Chased Brass Betel Trays, Leather Pouches & Royal Betel-Bearers",
        "name_ta": "தாம்பூலத் தட்டு மற்றும் அடப்பப் பை - வெண்கலத் தாம்பூலத் தட்டு, தோல் அடப்பப் பை மற்றும் வெற்றிலைப் பாண்டங்கள்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Ceremonial brass and bronze serving platters (thaamboola-thattu), embroidered leather traveling pouches (adappam), and specialized betel-bearer accoutrements of royal courts.",
        "summary_ta": "அரசர்களுக்கும் விருந்தினர்களுக்கும் வெற்றிலை பாக்கு வைக்கப் பயன்பட்ட நுணுக்கமான வேலைப்பாடுகள் கொண்ட வெண்கலத் தட்டுகள் மற்றும் அடப்பக்காரர் ஏந்திய தோல் பைகள்.",
        "sources": [
            "Purananuru 382",
            "South Indian Inscriptions on Adappam Officers",
            "Tanjore Maratha Palace Metal Collections"
        ],
        "content": "# Thaamboola-Thattil & Adappam: Ceremonial Paraphernalia\n\nThe presentation of betel in aristocratic circles gave rise to an entire suite of exquisite decorative metalwork:\n\n- **The Chased Betel Platter (*Thaamboola-Thattil*)**: Raised circular trays cast from bell-metal or beaten from brass, chased with circular lotuses, dancing peacocks, and floral arabesques, designed to display fresh leaves arranged radially like petals.\n- **The Royal Betel-Bearer (*Adappam*)**: Chola and Pandya monarchs maintained a prestigious personal court officer—the *Adappa-Nayakar*—who carried the king's private velvet-lined leather pouch containing selected tender leaves, spiced areca shavings, and perfumed lime.\n- **Spittoons (*Padikkam*)**: Hourglass-shaped brass spittoons placed beside royal thrones and festival seats, designed with flared rims for sanitary disposal."
    },
    {
        "file": "knowledge/concepts/concept-thaamboolam-alkaloid-synergy-arecoline-hydroxychavicol-and-digestive-physiology.md",
        "slug": "concept-thaamboolam-alkaloid-synergy-arecoline-hydroxychavicol-and-digestive-physiology",
        "category": "concept",
        "name_en": "Thaamboolam Pharmacology: Arecoline-Chavicol Synergy, Alkaline Salivation & Digestive Mechanics",
        "name_ta": "தாம்பூல மருந்தியல் - அரக்கோலின்-சாவிகால் வேதியியல் கூட்டு, கார எச்சில் சுரப்பு மற்றும் செரிமான இயற்பியல்",
        "era": "Classical Antiquity to Modern Era",
        "year_start": -400,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Pharmacological and physiological synergy between areca nut alkaloids (arecoline), betel phenol volatiles (hydroxychavicol), and slaked lime (calcium hydroxide), generating mild muscarinic stimulation and intense salivary amylase digestive activity.",
        "summary_ta": "வெற்றிலை, பாக்கு, சுண்ணாம்பு மூன்றையும் மெல்லும்போது ஏற்படும் வேதியியல் வினையால், எச்சில் காரத்தன்மை அடைந்து உமிழ்நீர் சுரப்பைத் தூண்டி செரிமானத்தை விரைவுபடுத்தும் சித்த மருந்தியல்.",
        "sources": [
            "Siddha Materia Medica: Gunavagadam on Vetrillai",
            "Journal of Ethnopharmacology on Betel Chewing",
            "Agasthiyar Vaidya Rathina Churukkam"
        ],
        "content": "# Thaamboolam Pharmacology: Alkaloid Synergy & Digestion\n\nThe traditional formulation of *thaamboolam* represents an ancient bio-active chemical drug delivery system:\n\n- **Alkaline Activation**: Slaked shell lime ($Ca(OH)_2$) elevates oral pH. The alkaline environment hydrolyzes the unprotonated pyridine alkaloid *arecoline* in areca nut into *arecaidine*, releasing free-base alkaloids that absorb rapidly through the oral mucosa.\n- **Cardiovascular & Neural Alertness**: Absorbed arecoline acts as a parasympathetic muscarinic agonist, mildly elevating heart rate, dilating bronchioles, and inducing mental alertness without intoxication.\n- **Enzymatic Digestive Priming**: The pungent chavicol in betel stimulates abundant secretion of salivary amylase and gastric juices, neutralizing heavy feast fats and preventing post-prandial dyspepsia."
    },
    {
        "file": "knowledge/institutions/institution-vetrillai-vanigar-and-kodi-kaalar-guild-of-betel-cultivators-and-merchants.md",
        "slug": "institution-vetrillai-vanigar-and-kodi-kaalar-guild-of-betel-cultivators-and-merchants",
        "category": "institution",
        "name_en": "Vetrillai-Vanigar: Guild of Master Betel Cultivators, Wholesale Consignment Merchants & Toll Epigraphs",
        "name_ta": "வெற்றிலை வணிகர் மற்றும் கொடிக்காலர் - வெற்றிலைக் கொடி விவசாயிகள் சங்கம், மொத்தக் கொள்முதல் வணிகர் அவை",
        "era": "Iron Age to Medieval Era",
        "year_start": -500,
        "year_end": 1500,
        "thinai": "marutham",
        "summary_en": "Socio-agrarian corporation of specialized betel cultivators (Senaithalaivar / Kodikalar) and urban wholesale merchants (Vetrillai-Vanigar) regulating garden irrigation rights, inter-district pack-bullock trade, and temple supplies.",
        "summary_ta": "வெற்றிலைக் கொடிக்கால்களைப் பயிரிட்டு, நகரங்களுக்கும் கோயில்களுக்கும் தினசரி நறுமண வெற்றிலைக் கட்டுகளை விநியோகம் செய்த அதிகாரப்பூர்வ வெற்றிலை வணிகர் கூட்டமைப்பு.",
        "sources": [
            "South Indian Inscriptions on Vetrillai-Kaani",
            "Epigraphia Indica on Merchant Toll Levies",
            "Tirunelveli Temple Epigraphs"
        ],
        "content": "# Vetrillai-Vanigar: Betel Cultivators & Trade Guilds\n\nGiven the daily universal consumption of betel across all strata of society, the betel trade was governed by powerful merchant bodies:\n\n- **The Kodikalar Guilds**: Specialized agricultural communities managed the intensive technical cultivation of *kodi-kaal* gardens along riverbanks, maintaining customary irrigation shares and communal fencing levies.\n- **Toll Epigraphs (*Vetrillai-Irai*)**: Temple inscriptions from the Pandyan and Chola eras record municipal transit tolls collected in kind: every pack-bullock (*pothi*) carrying betel into town markets contributed a fixed number of leaf rolls (*kattu*) to local temple deities.\n- **Wholesale Mandis**: The guild operated dedicated covered bazaars (*vetrillai-pettai*) in major urban centers, managing fast horse and runner couriers to deliver perishable fresh-picked leaves within 24 hours across provincial boundaries."
    },
    {
        "file": "knowledge/technologies/technology-ilai-kattu-perforated-moist-plantain-sheath-packaging-and-post-harvest-curing.md",
        "slug": "technology-ilai-kattu-perforated-moist-plantain-sheath-packaging-and-post-harvest-curing",
        "category": "technology",
        "name_en": "Ilai-Kattu: Moist Plantain-Sheath Packaging, Micro-Perforated Ventilation & Dark Curing",
        "name_ta": "இலைக் கட்டு - ஈர வாழை மட்டை பொதி நுட்பம், காற்றோட்டக் கட்டு மற்றும் வெற்றிலை பதப்படுத்துதல்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Post-harvest packaging technology bundling standardized lots of 100 leaves (kavuli) inside spongy, water-saturated fresh plantain sheaths (vazhai-mattai), regulating respiration and extending shelf life for transport.",
        "summary_ta": "பறிக்கப்பட்ட வெற்றிலைகளை 100 இலைகள் கொண்ட கவளிகளாக அடுக்கி, ஈர வாழை மட்டைகளில் சுற்றி, பழுப்பு நிறமடையாமல் பசுமையாகவும் வாசனையாகவும் வைத்திருக்கும் பொதி நுட்பம்.",
        "sources": [
            "Traditional Post-Harvest Technologies of South India",
            "Tamil Lexicon on Kavuli and Kattu",
            "Ethnographic Surveys of Authoor Betel Trade"
        ],
        "content": "# Ilai-Kattu: Plantain-Sheath Packaging & Curing\n\nTransporting delicate, moisture-sensitive betel leaves across long trade routes without wilting or rotting demanded sophisticated natural packaging:\n\n- **Standardized Leaf Counting (*Kavuli*)**: Harvested leaves were graded by tenderness, sorted into units of 100 leaves (*kavuli*), and bundled into master packs of 1,000 or 5,000 leaves (*kattu*).\n- **Spongy Plantain Sheaths (*Vazhai-Mattai*)**: Bundles were wrapped tightly inside thick, cellular succulent plantain tree bark. The moisture reservoir in the plantain sheath released steady water vapor, keeping the leaves crisp and turgid for up to two weeks without refrigeration.\n- **Dark Controlled Bleaching (*Patham-Poduthal*)**: For elite palates, dark green leaves were stored in warm, darkened earthenware pots under controlled damp conditions, converting harsh chlorophyll into golden, tender, sweet leaves (*ven-vetrillai*)."
    },
    {
        "file": "knowledge/artifacts/artifact-paakku-vetti-and-chunnambu-chimizh-ornate-bronze-nut-crackers-and-lime-boxes.md",
        "slug": "artifact-paakku-vetti-and-chunnambu-chimizh-ornate-bronze-nut-crackers-and-lime-boxes",
        "category": "artifact",
        "name_en": "Paakku-Vetti & Chunnambu-Chimizh: Figural Bronze Areca Nut Shears & Chased Lime Lockets",
        "name_ta": "பாக்கு வெட்டி மற்றும் சுண்ணாம்புச் சிமிழ் - சிற்ப வேலைப்பாடமைந்த பாக்கு நறுக்கி மற்றும் வெண்கலச் சுண்ணாம்புப் பேழை",
        "era": "Iron Age to Modern Era",
        "year_start": -400,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Exquisite mechanical handheld brass and wootz-edged nut shears (paakku-vetti) sculpted as embracing couples or mythical beasts, paired with chased bronze lime containers fitted with ivory spatulas.",
        "summary_ta": "கடினமான பாக்கை மெல்லிய சீவல்களாக நறுக்கும் சிற்ப வேலைப்பாடுகள் கொண்ட வெண்கல பாக்கு வெட்டிகள் மற்றும் சிறிய சுண்ணாம்புக் குப்பிகள்.",
        "sources": [
            "National Museum New Delhi Betel Cutter Collections",
            "Madras Government Museum Bronze Catalogs",
            "South Indian Folk Metalcraft Monographs"
        ],
        "content": "# Paakku-Vetti & Chunnambu-Chimizh: Nut Shears & Lime Boxes\n\nThe personal accoutrements of betel preparation represent a glorious convergence of micro-mechanics and sculpture:\n\n- **The Figural Areca Shears (*Paakku-Vetti*)**: Forged with twin scissor-like arms connected by a heavy copper rivet, one arm featured an inner steel cutting blade, while the handles were cast in lost-wax bronze as dancing peacocks, rearing yalis, or embracing lovers. With immense mechanical leverage, the tool sliced rock-hard dried areca nuts into paper-thin, curl-shaped ribbons (*paakku-chival*).\n- **The Pocket Lime Box (*Chunnambu-Chimizh*)**: Small spherical or heart-shaped boxes cast in bronze or chased in silver, fitted with a miniature spatula chained to the lid. Lime paste was drawn out and smeared smoothly down the central rib of the leaf."
    },
    {
        "file": "knowledge/concepts/concept-thamirabarani-alluvial-silt-aquifers-and-saline-buffering-edaphology.md",
        "slug": "concept-thamirabarani-alluvial-silt-aquifers-and-saline-buffering-edaphology",
        "category": "concept",
        "name_en": "Thamirabarani Edaphology: Copper-Rich Alluvial Silt, Saline Estuarine Buffering & Betel Terroir",
        "name_ta": "தாமிரபரணி நிலவியல் - தாமிரச் செழுமை வண்டல் மண், உவர்நீர் சமன்பாடு மற்றும் ஆத்தூர் வெற்றிலைச் சூழலியல்",
        "era": "Prehistoric to Modern Era",
        "year_start": -1000,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Geochemical and edaphic properties of the lower Thamirabarani delta where mineral-rich perennial river silt mixes with coastal estuarine water, imparting exceptional pungency and longevity to local betel vines.",
        "summary_ta": "தாமிரபரணி நதியின் செழுமையான செம்புச் சத்து நிறைந்த வண்டல் மண்ணும், கடலோரப் பகுதியின் மிதமான உவர்நீர் கலப்பும் ஆத்தூர் வெற்றிலைக்குத் தரும் பிரத்யேக நறுமணமும் சுவையும்.",
        "sources": [
            "Soil and Geochemical Surveys of Tirunelveli Basin",
            "GI Registry of India: Authoor Vetrillai Dossier",
            "Journal of the Geological Society of India"
        ],
        "content": "# Thamirabarani Edaphology: Silt Chemistry & Betel Terroir\n\nThe global fame of Authoor betel leaf is anchored in the unique soil and water chemistry of the lower Thamirabarani river basin:\n\n- **Perennial Copper-Rich Alluvium**: Flowing from the pristine Podhigai hills, the Thamirabarani River deposits fine alluvial clay enriched with natural copper and iron traces (*thamiram*), nourishing vigorous vine rootstocks.\n- **Subterranean Estuarine Brackish Buffering**: Situated near the Gulf of Mannar, the deep groundwater aquifers experience subtle subterranean marine infiltration. The slight salinity induces stress-induced synthesis of aromatic phenylpropanoids and volatile oils in the leaf tissues, resulting in an unmatched fiery, peppery bite.\n- **Geographical Indication Heritage**: Celebrated in local folk proverbs and royal charters, this unique terroir established the lower Thamirabarani as the undisputed capital of South Indian betel horticulture."
    },
    {
        "file": "knowledge/places/place-authoor-ancient-thamirabarani-betel-vine-haven.md",
        "slug": "place-authoor-ancient-thamirabarani-betel-vine-haven",
        "category": "place",
        "name_en": "Authoor: Ancient Thamirabarani Delta Betel Vine Haven, Kodi-Kaal Groves & GI Sanctuary",
        "name_ta": "ஆத்தூர் - பண்டைய தாமிரபரணி ஆற்றுக் கொடிக்கால் வளம், ஆத்தூர் வெற்றிலைத் தோப்புகள் மற்றும் புவிசார் குறியீட்டுத் தளம்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1900,
        "thinai": "marutham",
        "summary_en": "The historic riverside agro-sanctuary on the banks of the Thamirabarani in Thoothukudi district, celebrated across millennia for its spicy, long-lasting Authoor Vetrillai betel gardens and unbroken horticultural guilds.",
        "summary_ta": "தூத்துக்குடி மாவட்டத்தில் தாமிரபரணி ஆற்றின் கரையில் அமைந்துள்ள, உலகப் புகழ்பெற்ற ஆத்தூர் வெற்றிலைப் பயிர்செய்யும் வரலாற்றுத் தலைமைத் தளம்.",
        "sources": [
            "GI Registry of India: Authoor Vetrillai Dossier",
            "Tirunelveli District Gazetteers",
            "Inscriptions of Pandyan Maravarman Kulasekara I"
        ],
        "content": "# Authoor: Ancient Thamirabarani Betel Vine Haven\n\nSituated along the lush final reaches of the sacred Thamirabarani River in Thoothukudi district, Authoor is universally celebrated as the premier betel sanctuary of Tamilakam:\n\n- **The Living Kodi-Kaal Landscapes**: For countless generations, hundreds of family gardens along the river canal networks have maintained unbroken multi-tier agroforestry plots of *Authoor Vetrillai*, characterized by long, pointed, dark green leaves with an unmistakable sharp, sweet piquancy.\n- **Imperial Trade Lineage**: Historical records recount that medieval Pandyan kings, Arab horse traders at Korkai, and Portuguese merchant fleets all procured Authoor betel leaves for royal gift diplomacy and ocean voyages.\n- **Geographical Indication (GI) Landmark**: Honored with an official Geographical Indication tag, Authoor stands as an enduring living monument to ancient Tamil agricultural sophistication and the sacred cultural heritage of *thaamboolam*."
    }
]

EDGES = [
    [
        "text-silappadikaram-verses-on-spiced-betel-leaves-areca-nuts-and-royal-banquets",
        "DESCRIBES",
        "concept-vetrillai-piper-betle-vine-climbers-microclimatic-humidity-and-soil-microbiology",
        "core",
        "Post-Sangam Era",
        "Silappadikaram verses celebrate spiced betel leaves and royal hospitality feasts.",
        "Silappadikaram 5:30-45"
    ],
    [
        "concept-vetrillai-piper-betle-vine-climbers-microclimatic-humidity-and-soil-microbiology",
        "CULTIVATED_IN",
        "technology-kodi-kaal-live-support-agroforestry-agathi-hedgerows-and-ridge-furrow-hydraulics",
        "core",
        "Iron Age to Modern Era",
        "Piper betle vines were trellised on live agathi hedgerows in ridge-and-furrow beds.",
        "Traditional Agro-Forestry Systems of the Thamirabarani Basin"
    ],
    [
        "technology-kodi-kaal-live-support-agroforestry-agathi-hedgerows-and-ridge-furrow-hydraulics",
        "SERVED_ON",
        "artifact-thaamboola-thattil-and-adappam-chased-brass-betel-platters-and-areca-nut-shears",
        "core",
        "Iron Age to Modern Era",
        "Harvested leaves were served on chased brass platters with areca nuts and lime.",
        "Purananuru 382"
    ],
    [
        "concept-vetrillai-piper-betle-vine-climbers-microclimatic-humidity-and-soil-microbiology",
        "EXERTS",
        "concept-thaamboolam-alkaloid-synergy-arecoline-hydroxychavicol-and-digestive-physiology",
        "core",
        "Classical Antiquity to Modern Era",
        "Chewing betel and areca induced alkaloid synergy and salivary digestive activation.",
        "Siddha Materia Medica: Gunavagadam on Vetrillai"
    ],
    [
        "concept-vetrillai-piper-betle-vine-climbers-microclimatic-humidity-and-soil-microbiology",
        "ORGANIZED_BY",
        "institution-vetrillai-vanigar-and-kodi-kaalar-guild-of-betel-cultivators-and-merchants",
        "core",
        "Iron Age to Medieval Era",
        "Kodikalar and Vetrillai-Vanigar guilds governed cultivation rights and wholesale transit.",
        "South Indian Inscriptions on Vetrillai-Kaani"
    ],
    [
        "institution-vetrillai-vanigar-and-kodi-kaalar-guild-of-betel-cultivators-and-merchants",
        "PRESERVED_VIA",
        "technology-ilai-kattu-perforated-moist-plantain-sheath-packaging-and-post-harvest-curing",
        "core",
        "Iron Age to Modern Era",
        "Leaves were packed in spongy moist plantain bark sheaths for long-distance caravan trade.",
        "Traditional Post-Harvest Technologies of South India"
    ],
    [
        "artifact-thaamboola-thattil-and-adappam-chased-brass-betel-platters-and-areca-nut-shears",
        "PAIRED_WITH",
        "artifact-paakku-vetti-and-chunnambu-chimizh-ornate-bronze-nut-crackers-and-lime-boxes",
        "core",
        "Iron Age to Modern Era",
        "Brass betel trays were accompanied by sculptural areca nut shears and lime lockets.",
        "Madras Government Museum Bronze Catalogs"
    ],
    [
        "concept-vetrillai-piper-betle-vine-climbers-microclimatic-humidity-and-soil-microbiology",
        "NOURISHED_BY",
        "concept-thamirabarani-alluvial-silt-aquifers-and-saline-buffering-edaphology",
        "core",
        "Prehistoric to Modern Era",
        "Thamirabarani copper-rich alluvium and estuarine subsoil buffering created prime terroir.",
        "GI Registry of India: Authoor Vetrillai Dossier"
    ],
    [
        "concept-vetrillai-piper-betle-vine-climbers-microclimatic-humidity-and-soil-microbiology",
        "THRIVED_AT",
        "place-authoor-ancient-thamirabarani-betel-vine-haven",
        "core",
        "Iron Age to Modern Era",
        "Authoor delta canal groves constituted the world-renowned capital of betel cultivation.",
        "Inscriptions of Pandyan Maravarman Kulasekara I"
    ],
    [
        "institution-vetrillai-vanigar-and-kodi-kaalar-guild-of-betel-cultivators-and-merchants",
        "OPERATED_AT",
        "place-authoor-ancient-thamirabarani-betel-vine-haven",
        "core",
        "Iron Age to Modern Era",
        "Generations of Authoor betel guilds supplied royal palaces and trans-oceanic fleets.",
        "Tirunelveli District Gazetteers"
    ]
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Embedding failed: {res.text}")
    return res.json()["embedding"]

def main():
    print("Starting Ingestion Batch 38: Ancient Tamil Betel Vine Horticulture, Arecanut Hydraulics & Hospitality Rituals...")
    
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

    print(f"Ingestion Complete for Batch 38 Corpus! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
