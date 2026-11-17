#!/usr/bin/env python3
"""
Harvester: Batch 52 - Ancient Tamil Banana Cultivar Biodiversity, Vazhai-Naar Pseudostem Fiber Craft, Vazhai-Ilai Dining Science & Mukkani Agroforestry
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
        "slug": "text-sangam-corpus-on-vazhai-plantains-mukkani-trinity-and-kurinji-hill-groves",
        "category": "text",
        "file": "text-sangam-corpus-on-vazhai-plantains-mukkani-trinity-and-kurinji-hill-groves.md",
        "name_en": "Kurinjippattu, Malaipadukadam & Purananuru on Vazhai Plantains & Mukkani Fruit Trinity",
        "name_ta": "குறிஞ்சிப்பாட்டு, மலைபடுகடாம் மற்றும் புறநானூற்றில் வாழை மற்றும் முக்கனி மரபு",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "kurinji",
        "summary_en": "Classical Tamil poetic accounts in Kurinjippattu, Malaipadukadam, Ainkurunuru, and Purananuru celebrating hill and riverine plantains (vazhai), the canonical triad of Tamil fruits (Mukkani: Maa, Pala, Vazhai), and the serving of steaming rice on broad banana leaves.",
        "summary_ta": "குறிஞ்சிப்பாட்டு, மலைபடுகடாம், ஐங்குறுநூறு மற்றும் புறநானூறு ஆகிய சங்க இலக்கியங்களில் மலை வாழை, முக்கனி (மா, பலா, வாழை) மற்றும் தலைவாழை இலையில் விருந்தோம்பும் மரபு.",
        "sources": [
            "Kurinjippattu",
            "Malaipadukadam",
            "Ainkurunuru",
            "Purananuru"
        ],
        "content": "# Sangam Corpus on Vazhai Plantains & the Mukkani Fruit Trinity\n\nAcross the *Sangam* anthologies, the banana plant (*vazhai*) is celebrated both as a wild and orchard treasure of the *Kurinji* hills and *Marutham* river plains and as the third pillar of the sacred **Mukkani** (*Maa* mango, *Pala* jackfruit, *Vazhai* banana):\n\n**Literary Attestations:**\n- **Kurinjippattu, Malaipadukadam & Purananuru**: Poets describe heavy, curved hands (*tharu* / *thaar*) of sweet hill plantains (*malai-vazhai*) ripening beside jackfruit and mango trees on mountain ledges, and compare the unfurling terminal flower bud (*vazhaipoo* / *oombu*) to the tipped spear of a warrior or the tusk of a young elephant.\n- **Ainkurunuru & Hospitality Imagery**: Verses depict broad, emerald *vazhai* leaves fluttering in canal breezes and hosts laying out uncut terminal leaf blades (*thalai-vazhai ilai*) to serve fragrant white rice and clarified ghee to bards and guests."
    },
    {
        "slug": "concept-tamil-musa-cultivar-biodiversity-sirumalai-virupakshi-sevvazhai-and-matti-ecotypes",
        "category": "concept",
        "file": "concept-tamil-musa-cultivar-biodiversity-sirumalai-virupakshi-sevvazhai-and-matti-ecotypes.md",
        "name_en": "Tamil Musa Cultivar Biodiversity: Sirumalai, Virupakshi, Sevvazhai, Matti, Poovan & Monthan",
        "name_ta": "தமிழ்நாட்டு வாழை ரகங்களின் பல்லுயிர் வளம்: சிறுமலை, விருப்பாச்சி, செவ்வாழை, மட்டி, பூவன் மற்றும் மொந்தன்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "kurinji",
        "summary_en": "Genetic and ecological classification of heirloom Tamil banana cultivars (triploid AAA, AAB, and ABB hybrids of Musa acuminata and Musa balbisiana): aromatic high-altitude Sirumalai and Virupakshi hill bananas, carotene-rich Sevvazhai, weaning-food Matti, Poovan, Rasthali, and starchy Monthan.",
        "summary_ta": "தமிழகப் பாரம்பரிய வாழை ரகங்களின் மரபியல் மற்றும் சூழலியல் வகைப்பாடு: மலை வாழைகளான சிறுமலை மற்றும் விருப்பாச்சி, செவ்வாழை, குமரி மட்டி, பூவன், ரஸ்தாளி, நேந்திரன் மற்றும் சமையல் மொந்தன்.",
        "sources": [
            "National Research Centre for Banana (Tiruchirappalli) Germplasm Catalogues",
            "South Indian Banana Ecotypes & GI Registry",
            "Siddha Gunavagadam on Vazhai Varieties"
        ],
        "content": "# Tamil Musa Cultivar Biodiversity: Hill, Riverine & Coastal Ecotypes\n\nLocated at the primary centre of hybridization between sweet *Musa acuminata* (A-genome) and hardy, drought-tolerant *Musa balbisiana* (B-genome), Tamil Nadu evolved a specialized repertoire of triploid landraces tailored to each *thinai* landscape:\n\n**Signature Heirloom Cultivars:**\n- **Kurinji Hill Bananas (*Sirumalai* & *Virupakshi*, AAB-Pome Group)**: Grown rain-fed at 800–1,300 m elevation under forest shade; their low moisture content (65–70%) and high ester volatiles allow them to be mashed with jaggery and honey into non-spoiling *Palani Panchamirtham* without refrigeration.\n- **Kanyakumari *Matti* (AA Diploid) & *Sevvazhai* (Red Banana, AAA)**: The fragrant, curved-tip *Matti* possesses zero acidity and fine digestible starch prized as an infant's first weaning food, while beta-carotene-rich *Sevvazhai* (10-month crop) is prescribed in Siddha for fertility and vigour.\n- **Delta & Leaf Landraces (*Poovan*, *Karpuravalli*, *Rasthali*, *Monthan* ABB)**: While *Poovan* and *Rasthali* dominate dessert offerings, *Vayal-Vazhai* and *Poovan* yield the most Tear-Resistant, supple *thalai-vazhai* dining leaves, and angular *Monthan* supplies starchy green culinary plantains."
    },
    {
        "slug": "concept-thalai-vazhai-ilai-epicuticular-wax-chemistry-and-virundhu-course-geometry",
        "category": "concept",
        "file": "concept-thalai-vazhai-ilai-epicuticular-wax-chemistry-and-virundhu-course-geometry.md",
        "name_en": "Thalai-Vazhai Ilai Epicuticular Wax Chemistry, Polyphenol Transfer & Virundhu Dining Geometry",
        "name_ta": "தலைவாழை இலையின் மெழுகுப் படல வேதியியல், பாலிபினால் சத்து மற்றும் விருந்துப் பரிமாறல் இலக்கணம்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "marutham",
        "summary_en": "Surface science and culinary ergonomics of dining on a fresh banana leaf (thalai-vazhai ilai): hydrophobic epicuticular wax nanostructures softening above 65°C under hot steamed rice to release epigallocatechin gallate (EGCG) and hexenal aroma, paired with codified left-tip spatial layout.",
        "summary_ta": "தலைவாழை இலையில் உண்பதன் அறிவியல்: இலையின் மேற்பரப்பு மெழுகுப் படலம் சூடான சாதம் படும்போது இளகி பாலிபினால் (EGCG) ஆன்டி-ஆக்ஸிடன்ட்களையும் நறுமணத்தையும் உணவில் சேர்ப்பதும், இலை நுனி இடப்பக்கம் அமையும் பரிமாறல் ஒழுங்கும்.",
        "sources": [
            "Tamil Virundombal Culinary Manuals",
            "Surface Chemistry of Musa Epicuticular Waxes",
            "Siddha Patharthaguna Chinthamani (Vazhai Ilai Gunam)"
        ],
        "content": "# Thalai-Vazhai Ilai Wax Chemistry & Virundhu Dining Geometry\n\nServing a multi-course feast (*virundhu*) on the freshly cut terminal blade of a banana leaf (*thalai-vazhai ilai*) combines surface physics with ergonomic choreography:\n\n**Biochemical & Spatial Principles:**\n- **Hydrophobic Epicuticular Wax & Thermal Release**: The upper adaxial surface of the leaf is coated in a crystalline epicuticular wax film (long-chain alkanes and esters) that repels water droplets like a lotus leaf—making it self-cleaning with a sprinkle of water. When piping-hot rice and *paruppu* ($>70^\\circ\\text{C}$) are ladled onto the leaf, the micro-wax softens slightly, releasing **polyphenols (epigallocatechin gallate)**, chlorophyll derivatives, and leafy *(E)-2-hexenal* esters that impart the unmistakable *vazhai-ilai* aroma and aid digestion.\n- **Ergonomic Course Map**: The leaf is always laid with its **narrow tapered tip (*nuni*) pointing to the diner's left** and the thicker midrib running horizontally:\n  1. *Top-Left Corner*: Pinch of salt (*uppu*), pickle (*oorugai*), and sweet (*payasam/kesari* in some regional orders).\n  2. *Upper Half (Far Side)*: Dry and semi-dry vegetable accompaniments (*poriyal, kootu, aviyal, pachadi*) arranged left-to-right.\n  3. *Lower Half (Near the Diner's Right Hand)*: Unobstructed workspace for the mound of steamed rice mixed sequentially with *paruppu-nei*, *sambar*, *vathakuzhambu*, *rasam*, and cooling *thayir* (curd).\n  4. *Closing Fold*: Folding the leaf **inward toward oneself** after eating signifies satisfaction and a wish for the host relationship to endure."
    },
    {
        "slug": "technology-vazhai-naar-pseudostem-sheath-stripping-decortication-and-flower-garland-knotting",
        "category": "technology",
        "file": "technology-vazhai-naar-pseudostem-sheath-stripping-decortication-and-flower-garland-knotting.md",
        "name_en": "Vazhai-Naar Pseudostem Sheath Stripping, Scraper Decortication & Poo-Kattuthal Garland Knotting",
        "name_ta": "வாழைநார் மட்டை உரித்தல், நார் பிரிப்பு மற்றும் பூக்கட்டும் (தொடுத்தல்) தொழில்நுட்பம்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "marutham",
        "summary_en": "Technology of extracting high-tensile cellulose bast fibers (vazhai-naar) from post-harvest banana pseudostem leaf sheaths (vazhai-pattai): separating outer coarse sheaths for mats and inner silky sheaths for wet-knotting delicate jasmine and temple garlands without cutting flower stalks.",
        "summary_ta": "அறுவடை முடிந்த வாழைத் தண்டின் மட்டைகளிலிருந்து (வாழைப்பட்டை) வலிமையான வாழைநாரைப் பிரித்தெடுத்து, மென்மையான மல்லிகை மற்றும் கோயில் பூமாலைகளைக் காம்பு நசுங்காமல் தொடுக்கும் தொழில்நுட்பம்.",
        "sources": [
            "Traditional Temple Garland-Tying (Malai-Kattuthal) Manuals",
            "Cellulose Fiber Mechanics of Musa Pseudostem Sheaths",
            "Rural Fiber Crafts of Tirunelveli and Madurai"
        ],
        "content": "# Vazhai-Naar Pseudostem Extraction & Poo-Kattuthal Garland Knotting\n\nBecause a banana pseudostem fruits only once before being felled, Tamil artisans convert the concentric leaf-sheaths (*vazhai-pattai*) wrapping the trunk into zero-waste botanical cordage (**Vazhai-Naar**):\n\n**Extraction & Floristry Mechanics:**\n1. **Concentric Sheath Grading**: A felled pseudostem contains 14 to 20 overlapping sheaths:\n   - *Outer 6–8 Coarse Sheaths*: Rich in thick lignified vascular bundles; sun-dried into flat strips (*pattai-naar*) for tying temple flower-strands (*thoduthal*) and weaving coarse mats or rope.\n   - *Middle & Inner Translucent Sheaths*: Hand-scraped on a wooden board with a blunt brass or bamboo blade (*vazhi-kathi*) to remove watery parenchyma pulp, yielding lustrous, ivory-white cellulose filaments (*pattu-naar*) suitable for handloom banana-silk weaving.\n2. **Why *Vazhai-Naar* Excels for *Poo-Kattuthal* (Garland Tying)**: Unlike sharp twisted cotton thread (which slices right through tender jasmine *malli* or *kanakambaram* pedicels when pulled taut), damp *vazhai-naar* is a flat, ribbon-like hygroscopic strip. It grips wet flower stems with high friction, holds moisture to keep blossoms fresh for hours, and decomposes completely in temple compost pits."
    },
    {
        "slug": "technology-kandru-sucker-selection-smoke-pit-ripening-and-panchamirtham-fruit-maceration",
        "category": "technology",
        "file": "technology-kandru-sucker-selection-smoke-pit-ripening-and-panchamirtham-fruit-maceration.md",
        "name_en": "Sword-Sucker ( ஈட்டி கன்று ) Clonal Propagation, Earth-Pit Smoke Ripening & Panchamirtham Maceration",
        "name_ta": "ஈட்டிக் கன்றுத் தேர்வு, புகைமூட்டப் பழுக்கவைப்பு மற்றும் பஞ்சாமிர்தப் பதப்படுத்தும் தொழில்நுட்பம்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Horticultural and post-harvest technologies of Tamil plantain farming: selecting vigorous narrow-leaved sword suckers (eetti-kandru) over broad water suckers, triggering natural ethylene ripening in straw-lined earthen smoke chambers (pugai-arai), and waterless Panchamirtham sugar-osmotic preservation.",
        "summary_ta": "வாழைச் சாகுபடி மற்றும் அறுவடைக்குப் பிந்தைய தொழில்நுட்பம்: வீரியமான ஈட்டிக் கன்றுகளைத் தேர்ந்தெடுத்து நடுதல், மண்பானை புகைமூட்டம் மூலம் இயற்கையாகப் பழுக்க வைத்தல் மற்றும் நீர் சேர்க்காத பழனி பஞ்சாமிர்தப் பதப்படுத்துதல்.",
        "sources": [
            "Traditional Tamil Vrikshayurveda & Velanmai Proverbs",
            "Palani Dhandayuthapani Temple Panchamirtham Formulation",
            "Post-Harvest Physiology of Banana Ripening"
        ],
        "content": "# Sword-Sucker Propagation, Smoke-Pit Ripening & Panchamirtham Curing\n\nTraditional Tamil banana growers (*Vazhai-Vivasayigal*) and temple kitchens developed specialized techniques for clonal vigour, uniform ripening, and long-term fruit preservation:\n\n**Agronomic & Post-Harvest Workflow:**\n1. **Sword-Sucker (*Eetti-Kandru*) Selection**: Farmers distinguish sharply between broad-leaved *thannir-kandru* (water suckers with weak shallow corms) and narrow, spear-leaved **eetti-kandru** (sword suckers attached deeply to the mother rhizome *kizhangu*). Sword suckers are pared, dipped in cow-dung and wood-ash slurry (*saani-paal*) to ward off rhizome weevils, and sun-cured for two days before planting.\n2. **Earthen Smoke-Chamber Ripening (*Pugai-Moodam*)**: Green mature bunches (*thaar*) are stacked inside an insulated earthen pit or dark room lined with dry banana leaves and paddy straw. A smouldering clay pot (*kalayam*) of dry cow-dung cake and straw is introduced for a few hours and sealed; trace **ethylene gas** and mild warmth ($28^\\circ\\text{C}-30^\\circ\\text{C}$) trigger uniform starch-to-sugar conversion across every hand (*seeppu*) within 48 hours without chemical calcium carbide.\n3. **Waterless *Panchamirtham* Osmotic Preservation**: Using low-moisture *Virupakshi* or *Sirumalai* hill bananas mashed with country cane sugar (*naattu-sakkarai*), wild honey, cow's ghee, dates, and cardamom—with **zero added water**—creates a high-brix osmotic preserve that resists microbial fermentation for months."
    },
    {
        "slug": "artifact-thalai-vazhai-ilai-feast-leaves-vazhai-naar-garland-cords-and-paththaya-wrappers",
        "category": "artifact",
        "file": "artifact-thalai-vazhai-ilai-feast-leaves-vazhai-naar-garland-cords-and-paththaya-wrappers.md",
        "name_en": "Thalai-Vazhai Ilai Feast Leaves, Vazhai-Naar Garland Spools & Pothi-Choru Leaf Packets",
        "name_ta": "தலைவாழை விருந்து இலைகள், வாழைநார் பூத்தொடுக்கும் சுருள்கள் மற்றும் பொதிச்சோறு உணவுப் பொதிகள்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "marutham",
        "summary_en": "Everyday and ceremonial botanical artifacts harvested from the banana plant: uncut terminal feast leaves (thalai-vazhai ilai), heat-wilted travel food parcels (kattuchoru / pothi-choru), steamed elai-adai wrappers, and bundled hanks of stripped vazhai-naar cordage.",
        "summary_ta": "வாழை மரத்திலிருந்து பெறப்படும் பயன்பாட்டுப் பொருட்கள்: விருந்திற்குரிய தலைவாழை இலை, நெருப்பில் வாட்டி மடித்த கட்டுச்சோறு பொதிகள், இலையடை உறைகள் மற்றும் பூக்கட்டும் வாழைநார்ச் சுருள்கள்.",
        "sources": [
            "Purananuru",
            "Tamil Culinary & Travel Provision Traditions (Kattuchoru)",
            "Handicrafts of Kanyakumari and Tirunelveli Banana Fiber Clusters"
        ],
        "content": "# Thalai-Vazhai Feast Leaves, Pothi-Choru Parcels & Vazhai-Naar Hanks\n\nBeyond the fruit bunch, the leaf blade and pseudostem sheath supply Tamil households and flower markets with biodegradable, aromatic packaging and cordage artifacts:\n\n**Botanical Artifact Forms:**\n- **Thalai-Vazhai Ilai (Uncut Terminal Leaf Blade)**: The rounded, intact tip section of a healthy banana leaf reserved for honoured guests, newlyweds, and *Padayal* offerings to ancestral and village deities (*Kula-Deivam*).\n- **Fire-Wilted *Kattuchoru* / *Pothi-Choru* Travel Packets**: Fresh banana leaf contains turgid cells that crack if folded sharply at room temperature. Passing the leaf briefly over an open flame (*theeyil-vaattuthal*) melts and plasticizes the cuticular wax and cell walls, turning the leaf as supple as oiled silk so tamarind rice (*puliyodharai*) or curd rice can be wrapped tight and tied with a *vazhai-naar* strip for long journeys.\n- **Elai-Adai & *Meen-Polichathu* Steam Wrappers**: Used as a flavour-infusing envelope for steaming rice-flour and jaggery dumplings (*elai-adai*) or roasting spiced fish on a griddle."
    },
    {
        "slug": "artifact-kula-vazhai-fruited-gateway-pillars-vazhaipoo-inflorescence-and-vazhaithandu-cores",
        "category": "artifact",
        "file": "artifact-kula-vazhai-fruited-gateway-pillars-vazhaipoo-inflorescence-and-vazhaithandu-cores.md",
        "name_en": "Kula-Vazhai Fruited Gateway Pillars, Vazhaipoo Crimson Inflorescences & Vazhaithandu Cores",
        "name_ta": "மங்கல வாழைமரத் தோரணத் தூண்கள் (குலைவாழை), வாழைப்பூ மற்றும் வாழைத்தண்டு உணவுப் பொருட்கள்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "marutham",
        "summary_en": "Ritual and culinary anatomical organs of the banana plant: twin full-height fruiting pseudostems with hanging bunches and flowers (kula-vazhai) lashed to wedding pandal gateways, purple-crimson male flower buds (vazhaipoo), and ivory cylindrical inner stem cores (vazhaithandu).",
        "summary_ta": "வாழை மரத்தின் சடங்கு மற்றும் சமையல் உறுப்புகள்: திருமணப் பந்தல் வாசலில் குலையுடனும் பூவுடனும் கட்டப்படும் இரட்டை வாழைமரங்கள் (குலைவாழை), துவர்ப்புச் சுவையுடைய வாழைப்பூ மற்றும் நார்ச்சத்து மிக்க வாழைத்தண்டு.",
        "sources": [
            "Silappadikaram (Manaiyaram Padutha Kathai & Indira Vizha)",
            "Agathiyar Gunavagadam",
            "Tamil Lifecycle Rituals (Mangala Vazhai)"
        ],
        "content": "# Kula-Vazhai Gateway Pillars, Vazhaipoo Buds & Vazhaithandu Cores\n\nNo Tamil wedding, housewarming (*grahapravesam*), or temple festival (*vizha*) is complete without erecting twin full-grown banana trees (**Kula-Vazhai**) at the threshold, while the felled trunk yields two prized medicinal vegetables:\n\n**Ritual & Culinary Anatomy:**\n- **Twin *Kula-Vazhai* Threshold Pillars**: A pair of intact banana pseudostems—complete with root base, broad green leaves, a hanging green fruit bunch (*kulai*), and the terminal purple flower cone (*vazhaipoo*)—are lashed symmetrically to the left and right entrance posts of the *pandal* alongside mango-leaf *thoranam* and coconut fronds.\n- **Vazhaipoo (Terminal Male Inflorescence)**: Once the female hands have set fruit, the hanging purple-bracted male heart (*vazhaipoo*) is cut off so the plant directs sugar into filling the bananas. Each bract (*madal*) shelters two rows of tubular florets whose stiff pistil (*kalan* / *narambu*) and translucent front scale (*maavadu*) are plucked out before chopping into *vazhaipoo vadai* and *usili*.\n- **Vazhaithandu (Inner True Stem Core)**: Stripping away all concentric outer leaf sheaths of the felled trunk reveals the crisp, snow-white cylindrical true floral stalk (*vazhaithandu*) at the centre."
    },
    {
        "slug": "concept-vazhaithandu-lithotriptic-potassium-citrate-and-kula-vazhai-rhizome-lineage-symbolism",
        "category": "concept",
        "file": "concept-vazhaithandu-lithotriptic-potassium-citrate-and-kula-vazhai-rhizome-lineage-symbolism.md",
        "name_en": "Vazhaithandu Lithotriptic Kidney-Stone Dissolution & Vazhaiyadi-Vazhai Lineage Symbolism",
        "name_ta": "வாழைத்தண்டின் சிறுநீரகக் கல் கரைக்கும் மருத்துவ குணமும் 'வாழையடி வாழையாக' வம்ச விருத்தி தத்துவமும்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "marutham",
        "summary_en": "Siddha pharmacology and cultural philosophy of the banana plant: how potassium, magnesium, and citrate ions in raw vazhaithandu juice inhibit and flush calcium-oxalate renal calculi (kalladaippu), and why the perennial underground rhizome generating suckers exemplifies immortal family continuity (vazhaiyadi-vazhai).",
        "summary_ta": "வாழைத்தண்டுச் சாற்றிலுள்ள பொட்டாசியம்-சிட்ரேட் உப்புகள் சிறுநீரகக் கற்களைக் (கல்லடைப்பு) கரைக்கும் சித்த மருத்துவ அறிவியலும், தாய் மரம் சாய்ந்தாலும் அடியிலிருந்து கன்றுகள் தொடர்ந்து தழைப்பது 'வாழையடி வாழையாக' குலம் தழைப்பதைக் குறிக்கும் தத்துவமும்.",
        "sources": [
            "Siddha Gunavagadam & Yugi Vaidya Chinthamani (Kalladaippu)",
            "Urological Pharmacology of Musa Pseudostem Extract",
            "Tamil Cultural Anthropology (Vazhaiyadi-Vazhai)"
        ],
        "content": "# Vazhaithandu Lithotriptic Pharmacology & Vazhaiyadi-Vazhai Philosophy\n\nWhy does Tamil culture bless newlyweds to prosper *\"Vazhaiyadi-Vazhaiyaga\"* (\"like banana unto banana\"), and why do Siddha physicians revere every organ of the felled tree as an antidote to internal toxins?\n\n**Medical & Philosophical Doctrines:**\n- **Lithotriptic Action of *Vazhaithandu-Neer* (Renal Calculi Dissolution)**: In Siddha medicine, fresh juice pressed from the inner *vazhaithandu* core is the premier remedy for **Kalladaippu** (urinary gravel and calcium-oxalate kidney stones) and snakebite/heavy-metal toxicity. Rich in bioavailable **potassium, magnesium, vitamin $\\text{B}_6$, and organic citrates** with potent diuretic activity, *vazhaithandu* juice alkalinizes urine and chelates free calcium into soluble complexes, preventing crystal nucleation and flushing stones through the ureter.\n- **Astringent *Vazhaipoo* for Glycemic & Uterine Health**: The gallic-acid tannins and flavonoids in *vazhaipoo* check menorrhagia (*perumpaadu*), dysentery, and post-prandial blood glucose spikes.\n- **The *Vazhaiyadi-Vazhai* Immortality Metaphor**: Although the individual aerial pseudostem dies immediately after giving its single bunch of fruit, the subterranean corm (*kizhangu*) simultaneously sends up a ring of daughter suckers (*kandru*) that grow from the very base of the mother stem—embodying self-sacrificing generosity and an unbreakable generational chain."
    },
    {
        "slug": "institution-malai-vazhai-hill-orchard-stewards-and-temple-nandavanam-garland-tiers",
        "category": "institution",
        "file": "institution-malai-vazhai-hill-orchard-stewards-and-temple-nandavanam-garland-tiers.md",
        "name_en": "Malai-Vazhai Hill Orchard Stewards, Ilai-Mandi Leaf Wholesalers & Nandavanam Garland Guilds",
        "name_ta": "மலைவாழைத் தோட்டக் குடிகள், வாழை இலை மண்டி வணிகர்கள் மற்றும் நந்தவன மாலை தொடுப்போர் குழாம்",
        "era": "Chola to Modern Era",
        "year_start": 850,
        "year_end": 2025,
        "thinai": "kurinji",
        "summary_en": "Socio-economic institutions sustaining Tamil banana biodiversity and ritual supply chains: hereditary hill-orchard cultivators in Sirumalai and Lower Palani Hills conserving perennial ratoon clumps, urban Ilai-Mandi banana-leaf markets, and temple Nandavanam flower-tiers using vazhai-naar.",
        "summary_ta": "சிறுமலை மற்றும் பழனி மலைகளில் பல ஆண்டுகள் நிலைக்கும் மலைவாழைத் தோட்டங்களைப் பராமரிக்கும் விவசாயிகள், நகரத்து வாழை இலை மண்டிகள் மற்றும் கோயில் நந்தவனங்களில் வாழைநார் கொண்டு மாலை தொடுக்கும் கலைஞர்கள்.",
        "sources": [
            "South Indian Inscriptions (Nandavanam & Vazhai-Thottam Grants)",
            "Dindigul and Madurai Banana Market Records",
            "Geographical Indications Registry (Sirumalai Hill Banana)"
        ],
        "content": "# Malai-Vazhai Orchard Stewards, Ilai-Mandis & Nandavanam Garland Guilds\n\nMaintaining specialized banana cultivars for temple *abhishekam*, daily dining leaves, and floristry cordage relied on three interlocking community institutions:\n\n**Institutional & Market Ecosystem:**\n- **Perennial Hill-Ratoon Stewards (*Malai-Vazhai* Growers)**: Unlike plains bananas replanted every 1–2 years, *Sirumalai* and *Virupakshi* hill growers maintain multi-decade perennial banana clumps (*kattu*) under mixed forest shade on steep terraced slopes for 10 to 15 continuous ratoon generations, carefully pruning excess suckers (* பக்கக் கன்று *) so each clump matures one bunch every four months.\n- **Temple *Nandavanam* & *Vazhai-Thottam* Endowments**: Medieval Chola and Pandya inscriptions record land grants for temple banana gardens (*vazhai-nandavanam*) obligated to supply daily *thalai-vazhai* leaves for *naivedyam*, ripe fruits for *panchamirtham*, and damp *vazhai-naar* strips for the hereditary *Malai-Kattuvor* (garland makers).\n- **Dawn *Vazhai-Ilai Mandis***: Specialized wholesale leaf markets in Madurai, Koyambedu, and Tiruchirappalli grade leaves by width and cultivar (*Poovan* vs *Karpuravalli*) into 100-leaf bundles (*kattu*) wrapped in damp pseudostem sheaths that keep leaves crisp for a week without cold storage."
    },
    {
        "slug": "place-sirumalai-ancient-pandya-hill-plantain-and-vazhai-biodiversity-haven",
        "category": "place",
        "file": "place-sirumalai-ancient-pandya-hill-plantain-and-vazhai-biodiversity-haven.md",
        "name_en": "Sirumalai: Ancient Pandya Hill-Plantain Sanctuary, Kurinji Orchard & Malai-Vazhai Haven",
        "name_ta": "சிறுமலை - பாண்டிய நாட்டு மலைவாழைப் பல்லுயிர்ச் சரணாலயம் மற்றும் குறிஞ்சிப் பழத்தோட்டத் தளம்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "kurinji",
        "summary_en": "Isolated eastern spur of the Western Ghats rising between Dindigul and Madurai (10.1940° N, 77.9960° E), celebrated in Tamil literature and horticulture as the endemic sanctuary of the GI-tagged Sirumalai Malai-Vazhai hill banana, jackfruit, chow-chow, and medicinal Kurinji flora.",
        "summary_ta": "திண்டுக்கல் மற்றும் மதுரைக்கு இடையே அமைந்துள்ள பசுமையான சிறுமலைத் தொடர் (10.1940° N, 77.9960° E): புவிசார் குறியீடு பெற்ற நறுமணமிக்க 'சிறுமலை மலைவாழை', பலா மற்றும் மூலிகை வளம் நிறைந்த வரலாற்றுத் தளம்.",
        "sources": [
            "Silappadikaram (Madurai Route Descriptions of Sirumalai)",
            "Madurai and Dindigul District Gazetteers (Sirumalai Hills)",
            "GI Journal on Sirumalai Hill Banana"
        ],
        "content": "# Sirumalai: Ancient Pandya Hill-Plantain & Vazhai Biodiversity Haven\n\nRising abruptly to 1,200–1,350 metres between the Vaigai basin of Madurai and the Dindigul plain (10.1940° N, 77.9960° E), **Sirumalai** is a classic *Kurinji* forest massif directly described in *Silappadikaram* (where the ascetic describes the right-hand mountain route to Madurai overflowing with hill bananas, jackfruit, ginger, and turmeric):\n\n**Ecological & Horticultural Uniqueness:**\n- **The Endemic *Sirumalai Malai-Vazhai* (GI-Tagged)**: Cultivated across the mist-cooled slopes of Pudur, பழையூர் (Pazhaiyur), and Vellimalai at 900–1,200 m altitude in slightly acidic, humus-rich red loamy soil, the *Sirumalai* hill banana develops a thick yellow-black skin, firm non-mushy ivory pulp, and a complex honey-apple ester bouquet that cannot be replicated when the same sucker is planted on the plains below.\n- **Living *Mukkani* Agroforest**: Traditional Sirumalai orchards grow hill bananas beneath a multi-tier canopy of silver oak, jackfruit (*pala*), mango (*maa*), lemon, and pepper vines—preserving the exact *Mukkani* montane polyculture celebrated in Sangam poetry."
    }
]

EDGES = [
    [
        "text-sangam-corpus-on-vazhai-plantains-mukkani-trinity-and-kurinji-hill-groves",
        "describes",
        "concept-tamil-musa-cultivar-biodiversity-sirumalai-virupakshi-sevvazhai-and-matti-ecotypes",
        "material_culture",
        "Sangam Era",
        "Kurinjippattu, Malaipadukadam, and Purananuru celebrate mountain and riverine vazhai cultivars alongside mango and jackfruit as the Mukkani trinity.",
        "Kurinjippattu & Purananuru"
    ],
    [
        "concept-tamil-musa-cultivar-biodiversity-sirumalai-virupakshi-sevvazhai-and-matti-ecotypes",
        "underpins",
        "technology-kandru-sucker-selection-smoke-pit-ripening-and-panchamirtham-fruit-maceration",
        "material_culture",
        "Sangam to Modern Era",
        "Low-moisture Sirumalai and Virupakshi hill banana ecotypes enable waterless osmotic preservation in Palani Panchamirtham and sword-sucker clonal propagation.",
        "NRCB & Palani Temple Records"
    ],
    [
        "concept-thalai-vazhai-ilai-epicuticular-wax-chemistry-and-virundhu-course-geometry",
        "governs",
        "artifact-thalai-vazhai-ilai-feast-leaves-vazhai-naar-garland-cords-and-paththaya-wrappers",
        "material_culture",
        "Sangam to Modern Era",
        "Hydrophobic epicuticular wax softening above 65°C and left-tip course geometry govern the use of thalai-vazhai ilai feast leaves and flame-wilted pothi-choru wrappers.",
        "Tamil Virundombal Manuals"
    ],
    [
        "technology-vazhai-naar-pseudostem-sheath-stripping-decortication-and-flower-garland-knotting",
        "produces",
        "artifact-thalai-vazhai-ilai-feast-leaves-vazhai-naar-garland-cords-and-paththaya-wrappers",
        "material_culture",
        "Sangam to Modern Era",
        "Stripping and scraping concentric pseudostem leaf sheaths produce high-tensile vazhai-naar hanks for bruised-free jasmine garland tying and banana-silk weaving.",
        "Temple Floristry Manuals"
    ],
    [
        "concept-vazhaithandu-lithotriptic-potassium-citrate-and-kula-vazhai-rhizome-lineage-symbolism",
        "explains",
        "artifact-kula-vazhai-fruited-gateway-pillars-vazhaipoo-inflorescence-and-vazhaithandu-cores",
        "material_culture",
        "Sangam to Modern Era",
        "Perennial underground rhizome suckering explains why twin fruited kula-vazhai trees symbolize unbroken lineage at weddings, while potassium-citrate explains vazhaithandu's kidney-stone action.",
        "Siddha Gunavagadam"
    ],
    [
        "technology-kandru-sucker-selection-smoke-pit-ripening-and-panchamirtham-fruit-maceration",
        "yields",
        "artifact-kula-vazhai-fruited-gateway-pillars-vazhaipoo-inflorescence-and-vazhaithandu-cores",
        "material_culture",
        "Sangam to Modern Era",
        "Clonal sword-sucker cultivation and post-bunch felling yield ritual kula-vazhai trees, astringent vazhaipoo buds, and inner vazhaithandu cores.",
        "Tamil Velanmai Traditions"
    ],
    [
        "institution-malai-vazhai-hill-orchard-stewards-and-temple-nandavanam-garland-tiers",
        "supplies",
        "artifact-thalai-vazhai-ilai-feast-leaves-vazhai-naar-garland-cords-and-paththaya-wrappers",
        "material_culture",
        "Chola to Modern Era",
        "Dawn Ilai-Mandi wholesalers and temple Nandavanam gardeners supply graded thalai-vazhai leaves and damp vazhai-naar tying strips.",
        "South Indian Inscriptions"
    ],
    [
        "institution-malai-vazhai-hill-orchard-stewards-and-temple-nandavanam-garland-tiers",
        "conserves",
        "concept-tamil-musa-cultivar-biodiversity-sirumalai-virupakshi-sevvazhai-and-matti-ecotypes",
        "material_culture",
        "Sangam to Modern Era",
        "Hereditary hill-orchard farmers conserve multi-decade perennial ratoon clumps of Sirumalai, Virupakshi, Matti, and Sevvazhai landraces.",
        "GI Registry"
    ],
    [
        "institution-malai-vazhai-hill-orchard-stewards-and-temple-nandavanam-garland-tiers",
        "operates_in",
        "place-sirumalai-ancient-pandya-hill-plantain-and-vazhai-biodiversity-haven",
        "material_culture",
        "Sangam to Modern Era",
        "Hill-banana orchard stewards cultivate perennial Mukkani polycultures across the mist-cooled slopes of Sirumalai.",
        "Madurai District Gazetteer"
    ],
    [
        "text-sangam-corpus-on-vazhai-plantains-mukkani-trinity-and-kurinji-hill-groves",
        "celebrates",
        "place-sirumalai-ancient-pandya-hill-plantain-and-vazhai-biodiversity-haven",
        "material_culture",
        "Sangam to Modern Era",
        "Classical Tamil descriptions of Kurinji mountain plantain, jackfruit, and mango groves find living expression on the Sirumalai hills outside Madurai.",
        "Kurinjippattu & Silappadikaram"
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
