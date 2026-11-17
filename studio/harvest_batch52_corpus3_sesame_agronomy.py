#!/usr/bin/env python3
"""
Harvester: Batch 52 - Ancient Tamil Sesame Seed Agronomy, Ellu-Kai-Pidi Shatter-Proof Harvesting, Sesamin Antioxidant Chemistry & Pitru-Tharpanam Rituals
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
        "slug": "text-sangam-purananuru-and-malaipadukadam-on-ellu-sesame-capsules-and-el-nei-etymology",
        "category": "text",
        "file": "text-sangam-purananuru-and-malaipadukadam-on-ellu-sesame-capsules-and-el-nei-etymology.md",
        "name_en": "Sangam Purananuru, Malaipadukadam & Kuruntokai on Ellu Sesame Pods and El-Nei Etymology",
        "name_ta": "புறநானூறு, மலைபடுகடாம் மற்றும் குறுந்தொகையில் எள் சாகுபடி, எள்ளுக்காய் மற்றும் 'எள்+நெய்' சொற்பிறப்பியல்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "mullai",
        "summary_en": "Classical Sangam poetic attestations in Malaipadukadam, Purananuru, Kuruntokai, and Natrinai describing dryland black sesame (ellu / en) intercropped with millets, seven plump capsules on a single stem, and the linguistic root of Tamil ennai (el + nei, 'sesame ghee') as the generic term for all oils.",
        "summary_ta": "மலைபடுகடாம், புறநானூறு, குறுந்தொகை மற்றும் நற்றிணையில் விவரிக்கப்படும் புன்செய்ப் பயிரான எள் (எண்), ஒரு செடியில் ஏழு காய்கள் பிடிக்கும் வளம் மற்றும் 'எள் + நெய் = எண்ணெய்' என்ற தமிழ்ச் சொற்பிறப்பியல்.",
        "sources": [
            "Malaipadukadam",
            "Purananuru",
            "Kuruntokai",
            "Natrinai",
            "Tolkappiyam (Punariyal)"
        ],
        "content": "# Sangam Literature on Ellu Sesame Agronomy & El-Nei Etymology\n\nIn classical Tamil grammatical and poetic texts, sesame (*Sesamum indicum*, called *Ellu* or *En*) is the archetypal oilseed of the *Mullai* and *Kurinji* drylands:\n\n**Poetic & Linguistic Attestations:**\n- **Tolkappiyam & El-Nei Etymology**: *Tolkappiyam* codifies the morphophonemic sandhi rule whereby *El* (sesame) + *Nei* (clarified lipid/ghee) assimilates into *Ennai* (*எள் + நெய் = எண்ணெய்*). Because sesame was the earliest and supreme culinary and lamp oil of ancient Tamilakam, *ennai* became the universal Tamil noun for all liquid oils, requiring sesame oil itself to be retronymed *Nallennai* (\"the good/true oil\").\n- **Malaipadukadam & Purananuru**: *Malaipadukadam* praises upland fields where dark-seeded *ellu* grows thick enough for a single handful (*kai-pidi*) to contain seven fat four-sided pods (*ellu-kaai*), while *Purananuru* records roasted sesame and rice balls offered to bards."
    },
    {
        "slug": "concept-sesamum-indicum-thai-pattam-residual-moisture-agronomy-and-sand-broadcast-sowing",
        "category": "concept",
        "file": "concept-sesamum-indicum-thai-pattam-residual-moisture-agronomy-and-sand-broadcast-sowing.md",
        "name_en": "Sesamum indicum Residual-Moisture Agronomy (Thai-Pattam) & Sand-Diluted Broadcast Sowing",
        "name_ta": "தைப்பட்ட ஈரப்பத எள் சாகுபடி அறிவியலும் மணல் கலந்து தூவும் நுண்ணிய விதைப்பு முறையும்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Physiological agronomy of Sesamum indicum in Tamil drylands (punsei) and rice-fallow fields: deep taproot extraction of residual post-monsoon subsoil moisture during Thai-Pattam and Chithirai-Pattam without irrigation, acute hypoxia sensitivity to waterlogging, and diluting tiny seeds with dry river sand for uniform broadcast density.",
        "summary_ta": "வடகிழக்குப் பருவமழைக்குப் பின் எஞ்சியுள்ள நில ஈரப்பதத்தை மட்டுமே கொண்டு விளையும் தைப்பட்ட எள் பயிரின் ஆணிவேர் அமைப்பும், மிகச் சிறிய எள் விதைகளை ஆற்று மணலுடன் கலந்து சீராகத் தூவும் உழவியல் நுட்பமும்.",
        "sources": [
            "ICAR Sesame Agronomy & Physiology Monograph",
            "Tamil Nadu Agricultural University (TNAU) Traditional Dryland Farming Practices",
            "Watt Dictionary of the Economic Products of India (Sesamum indicum)"
        ],
        "content": "# Sesamum indicum Residual-Moisture Agronomy & Sand-Broadcast Sowing\n\nTraditional Tamil farmers cultivate sesame (*Ellu*) across three seasonal windows—*Karthigai/Margazhi* (rainfed *punsei*), *Thai/Maasi* (post-paddy rice-fallow *nanjai-tharisu*), and *Chithirai* (summer irrigated)—relying on the plant's specialized root physiology:\n\n**Agronomic & Sowing Principles:**\n- **Deep Taproot & Residual Dew Utilization**: Once germinated in damp soil after the January paddy harvest (*Thai-Pattam*), *Sesamum indicum* drives a rapid vertical taproot down $90-120\\text{ cm}$, maturing in $80-85\\text{ days}$ solely on capillary subsoil moisture and morning dew (*pani-neer*) while tolerating $40^\\circ\\text{C}$ canopy heat, yet dying within $48\\text{ hours}$ if standing water starves its roots of oxygen.\n- **Sand-Diluted Broadcast Calibration (*Manal-Kalanthu-Vithaithal*)**: Because a thousand sesame seeds weigh barely $2.8-3.2\\text{ g}$, sowing pure seed by hand causes severe clumping. Farmers blend one measure of seed with four measures of dry sieved river sand or hearth ash to achieve an even plant spacing of $15 \\times 15\\text{ cm}$, followed by dragging a thorny *karuvelam* bush (*mul-parambu*) to cover the seeds lightly ($1-2\\text{ cm}$)."
    },
    {
        "slug": "concept-loculicidal-capsule-dehiscence-biomechanics-and-indeterminate-acropetal-ripening",
        "category": "concept",
        "file": "concept-loculicidal-capsule-dehiscence-biomechanics-and-indeterminate-acropetal-ripening.md",
        "name_en": "Ellu-Kaai Loculicidal Capsule Dehiscence Biomechanics & Acropetal Ripening Window",
        "name_ta": "எள்ளுக்காய் வெடிப்பு உயிரியக்கவியலும் அடிமுதல் நுனிவரை முதிர்ச்சியடையும் அறுவடைப் பருவமும்",
        "era": "Ancient to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Botanical fracture mechanics of the four-chambered sesame capsule (ellu-kaai): indeterminate bottom-to-top flowering causing basal pods to dry and split along longitudinal sutures while apical buds are still green, and differential hygroscopic contraction of bilayered pericarp sclerenchyma driving explosive seed shattering.",
        "summary_ta": "எள் செடியின் அடிப்பகுதிக் காய்கள் முதலில் முற்றி மேல்நோக்கிப் பழுக்கும் தன்மையும், நான்கு அறைகள் கொண்ட எள்ளுக்காய் உலரும்போது நார் அடுக்குகளின் சுருக்க வேறுபாட்டால் தானாக வெடித்துச் சிதறும் இயற்பியலும்.",
        "sources": [
            "Anatomy and Biomechanics of Capsule Dehiscence in Sesamum indicum",
            "Bedigian Sesame: The Genus Sesamum",
            "Traditional Tamil Proverbs on Sesame Harvest Timing"
        ],
        "content": "# Ellu-Kaai Capsule Dehiscence Biomechanics & Ripening Window\n\nA folk proverb of the Tamil drylands warns: *\"எள் காய்க்கு முன் வெட்டு, கொள் காய்ந்த பின் வெட்டு\"* (\"Cut sesame before it dries completely; cut horsegram after it dries completely\"). This maxim encodes the fracture mechanics of the sesame fruit capsule (*ellu-kaai*):\n\n**Biomechanical Shattering Mechanism:**\n- **Acropetal Maturation Gradient**: Because *Sesamum indicum* flowers indeterminately from the lower leaf axils upward, the lowest capsules reach physiological maturity $10-14\\text{ days}$ before the top capsules.\n- **Bilayered Suture Tension**: Each oblong capsule consists of two carpels subdivided by false septa into four vertical seed locules. As moisture drops below $18\\%$, the outer parenchymatous exocarp shrinks far more than the inner lignified endocarp sclerenchyma, building bending stress that rips open the apical loculicidal suture (*வாய் பிளத்தல்*) and spills up to $50\\%$ of the crop if left standing in the wind."
    },
    {
        "slug": "concept-sesamin-sesamolin-lignan-antioxidant-chemistry-and-calcium-oxalate-hull-nutrition",
        "category": "concept",
        "file": "concept-sesamin-sesamolin-lignan-antioxidant-chemistry-and-calcium-oxalate-hull-nutrition.md",
        "name_en": "Sesamin-Sesamolin Lignan Antioxidant Chemistry & Black-vs-White Testa Hull Biochemistry",
        "name_ta": "செசமின்-செசமோலின் ஆன்டிஆக்ஸிடன்ட் வேதியியலும் கருப்பு-வெள்ளை எள் தோலின் சத்து வேறுபாடும்",
        "era": "Ancient to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Biochemical basis of sesame's oxidative stability and Siddha nutritional pharmacology: oil-soluble furofuran lignans (sesamin and sesamolin converting to phenolic sesamol upon roasting) preventing lipid peroxidation in ellurundai confections, alongside calcium oxalate concentration in the dark seed coat (umi) versus bioavailable calcium and iron in the kernel.",
        "summary_ta": "எள்ளில் உள்ள செசமின், செசமோலின் மற்றும் வறுக்கும்போது உருவாகும் செசமோல் ஆகியவை எள்ளுருண்டை சிக்குப் பிடிக்காமல் மாதக்கணக்கில் பாதுகாக்கும் வேதியியலும், கருப்புத் தோல் (உமி) மற்றும் வெள்ளைப் பருப்பின் சத்துக்களும்.",
        "sources": [
            "Food Chemistry of Sesame Lignans (Sesamin, Sesamolin, Sesamol)",
            "Siddha Materia Medica: Gunapadam Mooligai Vaguppu (Ellu)",
            "CSIR-CFTRI Studies on Dehulling of Black Sesame"
        ],
        "content": "# Sesamin-Sesamolin Lignan Chemistry & Testa Hull Nutrition\n\nAlthough sesame seed contains $\\approx 50\\%$ polyunsaturated and monounsaturated oil ($40\\%$ oleic, $45\\%$ linoleic acid), roasted Tamil sesame preparations (*ellurundai* and *ellu-podi*) resist rancidity at room temperature for months:\n\n**Phytochemical & Nutritional Mechanisms:**\n- **Thermal Conversion of Sesamolin to Sesamol**: Raw sesame seeds contain two unique furofuran lignans—*sesamin* ($0.4-0.6\\%$) and *sesamolin* ($0.2-0.4\\%$)—alongside $\\gamma$-tocopherol. When seeds are dry-roasted in an iron pan until they crackle ($160-180^\\circ\\text{C}$), trace moisture and heat hydrolyze *sesamolin* into free phenolic *sesamol* and *sesaminol*, potent radical scavengers that halt lipid autoxidation chains.\n- **Testa Hull (*Umi*) vs. Cotyledon Kernel**: The pigmented outer seed coat of black sesame (*karuppu-ellu*) concentrates $80\\%$ of the total calcium (largely bound as bitter calcium oxalate crystals) and iron, whereas wet-friction hulling removes the oxalates to yield sweet, digestible white kernels (*vellai-ellu*) rich in sulfur-bearing methionine and tryptophan."
    },
    {
        "slug": "technology-ellu-por-conical-stook-curing-and-inverted-cloth-bamboo-tap-threshing",
        "category": "technology",
        "file": "technology-ellu-por-conical-stook-curing-and-inverted-cloth-bamboo-tap-threshing.md",
        "name_en": "Ellu-Por Conical Stook Curing & Three-Stage Inverted Bamboo-Tap Threshing (Ellu-Thattuthal)",
        "name_ta": "எள்ளுப் போர் கூம்பு அடுக்கு முதிர்வும் தலைகீழாகக் கவிழ்த்து மூங்கில் குச்சியால் தட்டும் (எள் தட்டுதல்) நுட்பமும்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Zero-loss traditional Tamil harvesting and threshing workflow for shattering sesame: cutting plants at yellowing physiological maturity, piling bundles into covered conical stooks (ellu-por) to induce uniform capsule opening via sweat-curing, and inverting dried sheaves over a cloth sheet to tap out seeds in three graded beatings.",
        "summary_ta": "காய்கள் வெடித்துச் சிதறுவதற்கு முன் செடிகளை அறுத்து வட்ட வடிவ 'எள்ளுப் போர்' அடுக்கிப் புழுங்க வைத்து, பின்னர் விரிப்பின் மேல் தலைகீழாகப் பிடித்து மூங்கில் குச்சியால் மூன்று முறை தட்டி எள் பிரிக்கும் தொழில்நுட்பம்.",
        "sources": [
            "Traditional Post-Harvest Technology of Oilseeds in Tamil Nadu",
            "Tirunelveli & Madurai District Agricultural Manuals",
            "Ethnography of Dryland Threshing Floor (Kalathu-Medu) Practices"
        ],
        "content": "# Ellu-Por Conical Stook Curing & Inverted Tap-Threshing\n\nTo harvest $100\\%$ of the capsules on an indeterminate sesame stalk without losing the bottom pods to field shattering, Tamil farmers execute a two-phase curing and inverted shaking protocol:\n\n**Harvesting & Threshing Protocol:**\n- **Ellu-Por Sweat-Curing**: As soon as the stem leaves turn yellow and beaked basal pods show a hairline split while upper pods remain green, plants are uprooted at dawn when morning dew keeps capsules tough. Bundles (*kattu*) are stacked vertically or radially in a circular heap (*ellu-por*) covered with palmyra fronds for $4-5\\text{ days}$. Mild internal fermentation heat causes all upper capsules to ripen uniformly from stem nutrients without dropping seeds.\n- **Three-Stage Inverted Tapping (*Ellu-Thattuthal*)**: Bundles are stood upright in conical teepee stooks (*koodaram*) in the sun for two days until every capsule gapes open upward like a cup. Workers then invert each bundle over a white cloth (*thuni*) and tap the stems gently with a light bamboo rod (*mudhal-thattu* yielding $75\\%$ plumper prime seed), followed by two more sun-dryings and tap cycles (*irandaam* and *moondraam-thattu*)."
    },
    {
        "slug": "technology-karuppu-ellu-wet-friction-hulling-and-ural-pestle-ellurundai-pounding",
        "category": "technology",
        "file": "technology-karuppu-ellu-wet-friction-hulling-and-ural-pestle-ellurundai-pounding.md",
        "name_en": "Karuppu-Ellu Wet-Friction Dehulling (Umi-Neekkuthal) & Stone-Ural Ellurundai Pounding",
        "name_ta": "கருப்பு எள் ஊறவைத்துத் தோல் உமி நீக்கும் நுட்பமும் கல் உரலில் கருப்பட்டி சேர்த்து எள்ளுருண்டை இடிக்கும் முறையும்",
        "era": "Ancient to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Traditional seed processing and confectionery craft: soaking black sesame in water to swell the epidermal testa, rubbing against a rough stone mortar or coarse cotton sack to strip the bitter black hull (umi-neekkuthal), and dry-roasting seeds before pounding with palm jaggery in a granite ural so expressed oil binds ellurundai spheres.",
        "summary_ta": "கருப்பு எள்ளை நீரில் ஊறவைத்து உரலில் அல்லது கோணிப்பையில் தேய்த்து மேல் தோலை (உமி) நீக்கி வெள்ளை எள்ளாக்கும் நுட்பமும், வறுத்த எள்ளுடன் பனைக் கருப்பட்டி சேர்த்து உரலில் இடித்து எள்ளுருண்டை பிடிக்கும் கலையும்.",
        "sources": [
            "Traditional Tamil Culinary & Grain Processing Techniques",
            "CSIR Traditional Food Processing of South India",
            "Siddha Dietary Preparations (Pathiya Unavu)"
        ],
        "content": "# Karuppu-Ellu Wet-Friction Dehulling & Ural Ellurundai Pounding\n\nTransforming raw harvested *karuppu-ellu* into sweet white confectionary kernels or iron-rich *ellurundai* balls relies on precise hydration, shear-friction, and impact-milling techniques:\n\n**Processing & Confectionery Techniques:**\n- **Wet-Friction Dehulling (*Ellu-Theithal* / *Umi-Neekkuthal*)**: Cleaned black sesame is soaked in warm water for $45-60\\text{ minutes}$ until the thin outer seed coat (*umi*) absorbs moisture and loosens from the hydrophobic oil-rich endosperm. The drained damp seeds are bundled inside a coarse handloom cloth or placed in a granite mortar (*ural*) and rubbed vigorously with a wooden pestle or underfoot on a rough stone slab; rinsing in water floats away the detached black skins, leaving ivory-white *vellai-ellu*.\n- **Stone-Ural Ellurundai Pounding**: Unhulled black sesame is dry-roasted in a heavy clay or iron pan (*vaanali*) until the seeds swell and pop with a nutty aroma. While warm, they are pounded in a stone *ural* with an iron-ferruled *ulakkai* pestle alongside scraped palm jaggery (*panai-karuppatti*) and cardamom; the impact ruptures just enough oil bodies to bind the mass into glossy, non-sticky spheres without a single drop of added water or ghee."
    },
    {
        "slug": "artifact-ellurundai-sesame-jaggery-spheres-ellu-podi-condiments-and-puliyodharai-spice-pastes",
        "category": "artifact",
        "file": "artifact-ellurundai-sesame-jaggery-spheres-ellu-podi-condiments-and-puliyodharai-spice-pastes.md",
        "name_en": "Ellurundai Sesame-Jaggery Balls, Roasted Ellu-Podi Condiments & Temple Puliyodharai Mixes",
        "name_ta": "பனை வெல்ல எள்ளுருண்டை, வறுத்த எள்ளுப் பொடி மற்றும் கோவில் புளியோதரை எள் மசாலா",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Enduring culinary and therapeutic food artifacts of Tamil sesame culture: nutrient-dense Ellurundai (pounded black sesame and palm jaggery balls prescribed for adolescent menarche and bone strength), dry-roasted Ellu-Idli-Podi travel condiments, and roasted black sesame finishing powder essential to Vaishnava temple Puliyodharai.",
        "summary_ta": "வளரும் இளம் பெண்களுக்கும் தாய்மார்களுக்கும் இரும்புச்சத்து அளிக்க வழங்கப்படும் கருப்பு எள்ளுருண்டை, நீண்ட பயணங்களுக்கு ஏற்ற எள்ளுப் பொடி மற்றும் பெருமாள் கோவில் புளியோதரையின் மணமூட்டும் எள் பொடி.",
        "sources": [
            "Siddha Reproductive & Pediatric Nutrition Texts",
            "Temple Prasadam Traditions of Tamil Nadu (Srirangam & Tiruvallikkeni)",
            "Sangam Purananuru References to Sesame Rice"
        ],
        "content": "# Ellurundai Spheres, Ellu-Podi Condiments & Temple Puliyodharai\n\nAcross two millennia of Tamil domestic and temple gastronomy, roasted whole sesame seeds form the basis of shelf-stable, high-calorie functional foods:\n\n**Culinary & Therapeutic Artifacts:**\n- **Ellurundai (Sesame-Jaggery Energy Spheres)**: Combining the non-heme iron, copper, and calcium of black sesame with the mineral-rich molasses of *panai-karuppatti* (palm jaggery), *ellurundai* is traditionally prepared during *Navaratri*, *Karthigai Deepam*, and life-cycle puberty rites (*Manjal-Neerattu*) to replenish hemoglobin and strengthen pelvic bones.\n- **Ellu-Podi & Temple Puliyodharai**: Dry-roasting black sesame with *urad dal*, dried red chillies, asafoetida (*perungayam*), and curry leaves yields *Ellu-Podi*, carried by merchant caravans for weeks without spoilage. In Vaishnava temple kitchens (*Madapalli*), freshly roasted and coarsely ground black sesame powder is folded into tangy tamarind rice (*Puliyodharai*) to balance acidity with warm, nutty lipid aromatics."
    },
    {
        "slug": "artifact-ellu-kizhi-black-sesame-cloth-pouches-sani-deepam-lamps-and-darbha-tharpanam-rings",
        "category": "artifact",
        "file": "artifact-ellu-kizhi-black-sesame-cloth-pouches-sani-deepam-lamps-and-darbha-tharpanam-rings.md",
        "name_en": "Ellu-Kizhi Black-Cloth Sesame Wicks, Sani-Bhagavan Lamps & Darbha Thila-Tharpanam Vessels",
        "name_ta": "எள்ளுக் கிழி நல்லெண்ணெய் தீபம், சனி பகவான் வழிபாட்டு உருப்படிகள் மற்றும் தில தர்ப்பணக் கருவிகள்",
        "era": "Pallava to Modern Era",
        "year_start": 600,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Ritual material artifacts deploying unhulled black sesame (karuppu-ellu) in Tamil temple and ancestral liturgy: miniature black-cotton cloth pouches filled with black sesame seeds (ellu-kizhi) burned in sesame oil before Saneeswarar (Saturn) at Tirunallar and Kuchanur, and darbha-grass rings with copper plates for ancestral ellu-thanneer libations.",
        "summary_ta": "திருநள்ளாறு, குச்சனூர் சனி பகவான் ஆலயங்களில் கருப்புத் துணியில் எள் முடிந்து நல்லெண்ணெயில் ஏற்றப்படும் எள்ளுக் கிழி தீபமும், அமாவாசை முன்னோர் வழிபாட்டில் எள்ளும் நீரும் இறைக்கும் தில தர்ப்பணக் கருவிகளும்.",
        "sources": [
            "Tirunallar Dharbaranyeswarar & Kuchanur Saneeswarar Temple Ritual Manuals",
            "Dharmashastra & Tamil Pitru-Tharpanam Vidhi",
            "Symbolism of Black Sesame (Tila) in South Indian Ritual"
        ],
        "content": "# Ellu-Kizhi Sesame Wicks, Sani-Deepam Lamps & Thila-Tharpanam Vessels\n\nIn Tamil ritual cosmology, white sesame (*vellai-ellu*) belongs to auspicious festival kitchens (*Deva-Karyam*), whereas unhulled black sesame (*karuppu-ellu*) is the sacred medium of karmic purification, planetary propitiation (*Graha-Shanti*), and ancestral remembrance (*Pitru-Karyam*):\n\n**Ritual Artifact Assemblages:**\n- **Ellu-Kizhi & Ellu-Deepam for Saneeswarar**: On Saturdays and during *Sani-Peyarchi* transits at shrines such as Tirunallar and Kuchanur, devotees tie a spoonful of black sesame seeds inside a small square of black cotton cloth to form a bulbous pouch-wick (*ellu-kizhi*). Immersed in pure *nallennai* inside a shallow unglazed clay saucer (*agal-vilakku*) or iron bowl, the capillary oil rises through the sesame seeds to burn with a steady, soot-free flame.\n- **Thila-Tharpanam (*Ellu-Thanneer*) Libation Set**: Wearing a knotted *darbha* grass ring (*pavitram*) on the right ring finger, mourners hold black sesame seeds in their palm and pour water across the thumb crease (*Pitru-Theertham*) onto a copper platter, symbolizing the dissolution of ancestral debts."
    },
    {
        "slug": "institution-punsei-oilseed-rotation-guilds-amavasai-tharpanam-ghats-and-ellu-mandi-commission-pettais",
        "category": "institution",
        "file": "institution-punsei-oilseed-rotation-guilds-amavasai-tharpanam-ghats-and-ellu-mandi-commission-pettais.md",
        "name_en": "Punsei Crop-Rotation Customs, Ellu-Mandi Oilseed Brokerages & Amavasai Tharpanam Ghats",
        "name_ta": "புன்செய் மாற்றுப் பயிர் முறைமை, எள்ளு மண்டி வணிகப் பேட்டைகள் மற்றும் அமாவாசைத் தர்ப்பணப் படித்துறைகள்",
        "era": "Medieval to Modern Era",
        "year_start": 800,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Agrarian, mercantile, and religious institutions governing sesame in Tamil Nadu: village crop-rotation norms pairing deep-rooted sesame with shallow-rooted pulses, wholesale Ellu-Mandi commission markets grading seed oil content by volume-weight (padu), and sacred Amavasai river/sea ghats organizing mass ancestral sesame libations.",
        "summary_ta": "பயறு வகைகளுக்குப் பின் எள் விதைக்கும் புன்செய் மாற்றுப் பயிர் மரபு, எள்ளின் எண்ணெய் சத்தை எடை போட்டு வாணிகம் செய்யும் எள்ளு மண்டிகள் மற்றும் ஆடி, தை அமாவாசைத் தர்ப்பணத் தீர்த்தக் கட்டங்கள்.",
        "sources": [
            "South Indian Inscriptions (Ennai-Vaniyar & Oilseed Cess Records)",
            "Madras Presidency Marketing Survey on Gingelly (Sesame) Seed",
            "Pilgrimage Records of Rameswaram Agni-Theertham & Tamiraparani Ghats"
        ],
        "content": "# Punsei Rotation Customs, Ellu-Mandi Brokerages & Tharpanam Ghats\n\nThe production, grading, and ritual consumption of sesame across Tamil Nadu are coordinated by three interlocking rural and urban institutions:\n\n**Institutional Frameworks:**\n- **Punsei Rotation & Weed Suppression**: Village farming customs place *ellu* immediately after *ulundu* (blackgram) or *kollu* (horsegram) in the annual rotation; sesame's dense canopy and root exudates naturally suppress *Cyperus* (*korai*) sedge weeds and loosen compact subsoil for the following cereal crop.\n- **Ellu-Mandi Wholesale Brokerages**: In market towns such as Vallioor, Virudhunagar, Villupuram, and Erode, specialized *Ellu-Mandi* merchants grade farmers' sacks using brass *marakkal* volume measures and thumb-crush testing—distinguishing high-oil thin-skinned *Rasi-Ellu* ($>50\\%$ oil yield per *chekku* charge) from thick-skinned varieties.\n- **Amavasai Tharpanam Ghats**: Every *Adi-Amavasai*, *Thai-Amavasai*, and *Mahalaya*, hereditary *Purohit* guilds along the Tamiraparani, Kaveri, and Rameswaram seashore administer hundreds of thousands of black-sesame *tharpanam* rites."
    },
    {
        "slug": "place-vallioor-ancient-pandya-ellu-sesame-agronomy-and-dryland-haven",
        "category": "place",
        "file": "place-vallioor-ancient-pandya-ellu-sesame-agronomy-and-dryland-haven.md",
        "name_en": "Vallioor: Ancient Pandya Dryland Ellu Sesame Agronomy, Stook-Curing & Oilseed Market Haven",
        "name_ta": "வள்ளியூர் - பாண்டிய நாட்டுப் புன்செய் எள் சாகுபடி, எள்ளுப் போர் களம் மற்றும் எண்ணெய் வித்து வணிகத் தளம்",
        "era": "Pandya to Modern Era",
        "year_start": 600,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Historic southern Pandya agricultural and market town of Vallioor (lat 8.3840, lng 77.6160, thinai: mullai) in Tirunelveli district between the Western Ghats foothills and the Nambiyar river, celebrated for its post-monsoon Thai-Pattam black and red sesame fields, traditional ellu-por curing floors, and regional oilseed trade.",
        "summary_ta": "திருநெல்வேலி மாவட்டத்தின் தென்பகுதியில் மேற்குத் தொடர்ச்சி மலை அடிவாரத்திற்கும் நம்பியாற்றுக்கும் இடையே அமைந்த வள்ளியூர் (அட்சரேகை 8.3840, தீர்க்கரேகை 77.6160): பாரம்பரியத் தைப்பட்ட எள் சாகுபடி மற்றும் எண்ணெய் வித்துச் சந்தையின் மையம்.",
        "sources": [
            "Tinnevelly District Gazetteer (Pate 1917: Nanguneri & Vallioor)",
            "Historical Inscriptions of Vallioor Subramaniya Swami Rock-Cut Temple",
            "Southern Tamil Nadu Oilseed & Dryland Agronomy Survey"
        ],
        "content": "# Vallioor: Ancient Pandya Ellu Sesame Agronomy & Dryland Haven\n\nSituated at latitude $8.3840^\\circ\\text{ N}$, longitude $77.6160^\\circ\\text{ E}$ in the southern *mullai* red-loam and sandy-clay tract of Tirunelveli district (framed by the ancient rock-cut hill shrine of *Poongavanathu Amman* and *Subramaniya Swami* and fed by the Nambiyar tank cascade), Vallioor is a premier historical stronghold of southern Pandya sesame (*Ellu*) agronomy:\n\n**Agro-Ecological & Commercial Prominence:**\n- **Post-Pishanam Rice-Fallow & Red-Loam Sesame**: Following the northeast monsoon (*Pishanam*) harvest in *Thai* (January–February), thousands of acres of well-drained sandy-loam fields around Vallioor, Radhapuram, and Nanguneri are broadcast-sown with drought-hardy dark brown (*sem-ellu*) and jet-black (*karuppu-ellu*) landraces that mature on warm sea breezes and morning dew.\n- **Threshing-Floor & Mandi Hub**: Across March and April, the outskirts of Vallioor are dotted with conical *ellu-por* stooks and white threshing cloths, supplying high-lignan sesame seed to traditional *chekku* oil mills and *ellurundai* confectioners throughout Tirunelveli and Kanyakumari."
    }
]

EDGES = [
    [
        "text-sangam-purananuru-and-malaipadukadam-on-ellu-sesame-capsules-and-el-nei-etymology",
        "documents",
        "concept-sesamum-indicum-thai-pattam-residual-moisture-agronomy-and-sand-broadcast-sowing",
        "material_culture",
        "Sangam Era",
        "Malaipadukadam and Purananuru document dryland sesame cultivation, seven-pod stems, and the el+nei etymology of oil.",
        "Malaipadukadam & Tolkappiyam"
    ],
    [
        "concept-sesamum-indicum-thai-pattam-residual-moisture-agronomy-and-sand-broadcast-sowing",
        "governs",
        "institution-punsei-oilseed-rotation-guilds-amavasai-tharpanam-ghats-and-ellu-mandi-commission-pettais",
        "material_culture",
        "Iron Age to Modern Era",
        "Deep taproot residual-moisture extraction governs post-monsoon Thai-Pattam crop rotations and dryland punsei farming schedules.",
        "TNAU Dryland Agronomy"
    ],
    [
        "concept-loculicidal-capsule-dehiscence-biomechanics-and-indeterminate-acropetal-ripening",
        "necessitates",
        "technology-ellu-por-conical-stook-curing-and-inverted-cloth-bamboo-tap-threshing",
        "material_culture",
        "Iron Age to Modern Era",
        "Acropetal pod maturation and explosive loculicidal suture splitting necessitate pre-shatter harvesting and conical ellu-por sweat-curing.",
        "Sesame Dehiscence Biomechanics"
    ],
    [
        "concept-sesamin-sesamolin-lignan-antioxidant-chemistry-and-calcium-oxalate-hull-nutrition",
        "guides",
        "technology-karuppu-ellu-wet-friction-hulling-and-ural-pestle-ellurundai-pounding",
        "material_culture",
        "Ancient to Modern Era",
        "Calcium oxalate localization in the black seed coat and thermal sesamol generation guide wet-friction dehulling and warm roasting.",
        "CSIR-CFTRI Sesame Studies"
    ],
    [
        "technology-ellu-por-conical-stook-curing-and-inverted-cloth-bamboo-tap-threshing",
        "supplies",
        "technology-karuppu-ellu-wet-friction-hulling-and-ural-pestle-ellurundai-pounding",
        "material_culture",
        "Ancient to Modern Era",
        "Three-stage inverted bamboo-tap threshing supplies clean, uncrushed prime black sesame seeds for wet hulling and stone-ural pounding.",
        "Post-Harvest Oilseed Technology"
    ],
    [
        "technology-karuppu-ellu-wet-friction-hulling-and-ural-pestle-ellurundai-pounding",
        "produces",
        "artifact-ellurundai-sesame-jaggery-spheres-ellu-podi-condiments-and-puliyodharai-spice-pastes",
        "material_culture",
        "Sangam to Modern Era",
        "Dry-roasting and stone-ural pestle pounding with palm jaggery produce shelf-stable ellurundai spheres and temple puliyodharai spice powders.",
        "Siddha Pathiya Unavu"
    ],
    [
        "concept-sesamin-sesamolin-lignan-antioxidant-chemistry-and-calcium-oxalate-hull-nutrition",
        "preserves",
        "artifact-ellurundai-sesame-jaggery-spheres-ellu-podi-condiments-and-puliyodharai-spice-pastes",
        "material_culture",
        "Sangam to Modern Era",
        "Endogenous sesamin, sesamolin, and roast-derived sesamol preserve ellurundai and ellu-podi against lipid rancidity for months.",
        "Food Chemistry of Sesame Lignans"
    ],
    [
        "institution-punsei-oilseed-rotation-guilds-amavasai-tharpanam-ghats-and-ellu-mandi-commission-pettais",
        "deploys",
        "artifact-ellu-kizhi-black-sesame-cloth-pouches-sani-deepam-lamps-and-darbha-tharpanam-rings",
        "material_culture",
        "Pallava to Modern Era",
        "Amavasai tharpanam ghats and Saturday Saneeswarar shrines deploy unhulled black sesame in ellu-thanneer libations and ellu-kizhi oil lamps.",
        "Tirunallar & Tharpanam Manuals"
    ],
    [
        "place-vallioor-ancient-pandya-ellu-sesame-agronomy-and-dryland-haven",
        "hosts",
        "technology-ellu-por-conical-stook-curing-and-inverted-cloth-bamboo-tap-threshing",
        "material_culture",
        "Pandya to Modern Era",
        "Vallioor in southern Tirunelveli hosts extensive Thai-Pattam sesame fields, ellu-por curing floors, and regional oilseed mandis.",
        "Tinnevelly District Gazetteer"
    ],
    [
        "text-sangam-purananuru-and-malaipadukadam-on-ellu-sesame-capsules-and-el-nei-etymology",
        "celebrates",
        "place-vallioor-ancient-pandya-ellu-sesame-agronomy-and-dryland-haven",
        "material_culture",
        "Sangam Era",
        "Sangam poetic descriptions of fertile southern dryland sesame harvests celebrate the agrarian ecology of the Pandya mullai plains around Vallioor.",
        "Purananuru & Tinnevelly Gazetteer"
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
