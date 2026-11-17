#!/usr/bin/env python3
"""
Harvester: Batch 48 - Ancient Tamil Herbal Saponin Cleansers, Ennai-Kuzhial Oil-Bath Thermoregulation & Temple Thirumanjanam Aromatics
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
        "slug": "text-paripadal-silappadikaram-and-tiruppavai-on-aromatic-hair-washing-and-river-bathing",
        "category": "text",
        "file": "text-paripadal-silappadikaram-and-tiruppavai-on-aromatic-hair-washing-and-river-bathing.md",
        "name_en": "Paripadal, Silappadikaram & Tiruppavai on Aromatic Hair-Washing, Bath Pastes & River Snanam",
        "name_ta": "பரிபாடல், சிலப்பதிகாரம் மற்றும் திருப்பாவையில் நறுமண நீராடல், ஐம்பால் கூந்தல் மற்றும் சுண்ணப் பொடிக் குறிப்புகள்",
        "era": "Sangam to Bhakti Era",
        "year_start": -300,
        "year_end": 900,
        "thinai": "marutham",
        "summary_en": "Classical Tamil poetic accounts in Paripadal, Silappadikaram, Tiruppavai, Nedunalvadai, and Kurinjippattu describing communal river bathing (neeradal) in the Vaigai and Kaveri, washing five-plaited hair (aimpal-koonthal) with herbal saponin pastes, perfuming tresses with akil (agarwood) smoke, and anointing the body with aromatic sunnam powders.",
        "summary_ta": "பரிபாடல், சிலப்பதிகாரம், திருப்பாவை, நெடுநல்வாடை மற்றும் குறிஞ்சிப்பாட்டு ஆகிய நூல்களில் வைகை மற்றும் காவிரி நீராடல், மூலிகைத் தைலக் குளியல், ஐம்பால் கூந்தல் பராமரிப்பு மற்றும் அகில் புகை ஊட்டுதல் பற்றிய இலக்கியச் சான்றுகள்.",
        "sources": [
            "Paripadal",
            "Silappadikaram",
            "Tiruppavai",
            "Nedunalvadai",
            "Kurinjippattu"
        ],
        "content": "# Paripadal, Silappadikaram & Tiruppavai on Aromatic Hair-Washing & River Bathing\n\nSangam and Bhakti literature documents a sophisticated hydrological and botanical bathing culture (*neeradal*) integrating therapeutic oil massage, plant-saponin cleansing, and resin fumigation:\n\n**Literary & Poetic Attestations (Cited by Title):**\n- **Paripadal (Vaigai Neeradal Hymns)**: Multiple hymns celebrate festive monsoon bathing in the Vaigai river, where bathers apply sandalwood pastes (*chandanam*), turmeric (*manjal*), and multi-herb aromatic powders (*vasanai-sunnam*) that turn the river currents fragrant.\n- **Silappadikaram & Kurinjippattu (Aimpal-Koonthal Care)**: In *Silappadikaram*, Madhavi's attendants bathe her long tresses (*aimpal*) in a decocted infusion of ten astringent and aromatic herbs (*pathu-thuvar*), rinse the hair with herbal mucilage, anoint it with *thagara* ointment, and dry it over perfumed *akil* (agarwood) and *sambirani* smoke.\n- **Tiruppavai (Margazhi Neeradal)**: Andal's hymns codify the pre-dawn winter river bath (*Margazhi-neeradal*) and the ritual abstention from cosmetic *ennai-kuzhial* hair oils until the completion of the sacred vow."
    },
    {
        "slug": "concept-seekakai-arappu-and-manipungan-triterpenoid-saponin-micelle-emulsification",
        "category": "concept",
        "file": "concept-seekakai-arappu-and-manipungan-triterpenoid-saponin-micelle-emulsification.md",
        "name_en": "Seekakai, Usilai-Arappu & Manipungan Triterpenoid Saponin Micelles & Acid-Mantle pH Balance",
        "name_ta": "சீயக்காய், உசிலை அரப்பு மற்றும் பூவந்திக்காயின் சப்போனின் (Saponin) கூழ்ம வேதியியலும் சரும pH சமநிலையும்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Colloid and surface chemistry of Tamil botanical hair and skin cleansers—Acacia concinna (seekakai pods), Albizia amara (usilai / arappu leaves), and Sapindus emarginatus (manipungan / soapnut): non-ionic triterpenoid saponin glycosides that lower water surface tension and emulsify heavy gingelly oil at skin-isoelectric pH (4.5–5.5).",
        "summary_ta": "சீயக்காய் (Acacia concinna), உசிலை அரப்பு (Albizia amara) மற்றும் பூவந்திக்காய் (Sapindus emarginatus) ஆகியவற்றில் உள்ள இயற்கை சப்போனின் மூலக்கூறுகள், சருமத்தின் இயற்கையான அமிலத்தன்மையை (pH 4.5–5.5) மாற்றாமல் நல்லெண்ணெய்ப் பிசுக்கை நீக்கும் வேதியியல்.",
        "sources": [
            "Phytochemistry of Triterpenoid Saponins in Acacia concinna and Sapindus emarginatus",
            "Ethnobotany of Albizia amara (Usilai Arappu) in Tamil Nadu",
            "Dermatological Chemistry of Natural Surfactants"
        ],
        "content": "# Seekakai, Arappu & Manipungan Triterpenoid Saponin Micelle Chemistry\n\nLong before caustic alkali-fat soaps ($\\text{pH } 9.5\\text{--}11.0$), Tamil hygiene relied on three complementary forest botanical surfactants that cleanse heavy sesame oil without disrupting the acid mantle of the scalp and epidermis:\n\n**1. Amphiphilic Triterpenoid Glycosides:**\n- **Seekakai (*Acacia concinna* Pods)**: The dried pod pericarp contains $10\\text{--}12\\%$ **acacic acid lactone saponins** (kinmoonosides and acaciasides), where a lipophilic pentacyclic triterpene aglycone (*sapogenin*) is linked to hydrophilic arabinose, xylose, and glucose chains.\n- **Manipungan / Poovarasankottai (*Sapindus emarginatus* Pericarp)**: Contains up to $18\\%$ oleanane-type **sapindosides A–D**, providing rapid foam nucleation and low critical micelle concentration (CMC).\n- **Usilai Arappu (*Albizia amara* Leaf Flour)**: Combines mild echinocystic-acid saponins with pectic plant mucilage, acting simultaneously as an oil emulsifier and a cationic-like slip conditioner that detangles wet hair.\n\n**2. Isoelectric Cuticle Preservation ($\\text{pH } 4.5\\text{--}5.5$):**\n- Aqueous *seekakai* and *arappu* dispersions naturally buffer between $\\text{pH } 4.6$ and $5.4$—matching the isoelectric point of human hair keratin ($\\text{pI} \\approx 3.7\\text{--}5.0$). Consequently, hair cuticle scales lie flat and sealed while spherical saponin micelles solubilize excess *nallenai* triglycerides without stripping intercellular ceramides."
    },
    {
        "slug": "concept-siddha-ennai-kuzhial-gingelly-oil-bath-pitta-thermoregulation-and-vagus-toning",
        "category": "concept",
        "file": "concept-siddha-ennai-kuzhial-gingelly-oil-bath-pitta-thermoregulation-and-vagus-toning.md",
        "name_en": "Siddha Ennai-Kuzhial Medicated Gingelly Oil-Bath, Pitta Thermoregulation & Cranial Cooling",
        "name_ta": "சித்த மருத்துவ எண்ணெய்க் குளியல் (புதன்-சனி நீராடல்), பித்தத் தணிப்பு மற்றும் உடல் வெப்பச் சமநிலை அறிவியல்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Siddha preventive medicine and thermal physiology of the twice-weekly head-to-toe sesame oil bath (Ennai-Kuzhial on Wednesdays and Saturdays): applying herb-infused Sesamum indicum oil over the vertex (brahmarandhra), ears, and plantar soles to induce cutaneous vasodilation, dissipate internal pitta heat, and protect lipid-rich sesamol antioxidants.",
        "summary_ta": "தித்திக்கும் செக்கு நல்லெண்ணெயில் மிளகு, சீரகம், பூண்டு இட்டுக் காய்ச்சி வாரந்தோறும் புதன் மற்றும் சனிக்கிழமைகளில் உச்சந்தலை முதல் உள்ளங்கால் வரை தேய்த்துக் குளிக்கும் எண்ணெய்க் குளியலின் பித்தத் தணிப்பு மற்றும் வெப்பச் சமநிலை அறிவியல்.",
        "sources": [
            "Therayar Pathartha Guna Chintamani (Ennai-Kuzhial Vidhi)",
            "Agathiyar Gunavagadam",
            "Physiological Effects of Traditional Abhyanga & Sesame Oil Bathing"
        ],
        "content": "# Siddha Ennai-Kuzhial Medicated Gingelly Oil-Bath & Pitta Thermoregulation\n\nIn the Siddha preventive health canon (*Noi Naadal / Noi Mudhal Naadal*), the twice-weekly head oil-bath (**Ennai-Kuzhial**—prescribed on Wednesdays and Saturdays for men, Tuesdays and Fridays for women) is the primary homeostatic intervention against tropical ambient heat:\n\n**1. Biophysical Thermoregulation & *Pitta* Dissipation:**\n- **Cranial & Plantar Application**: Warmed medicated *nallenai* (*Sesamum indicum* oil) is applied first to the crown of the head (*uchchi*), instilled as two drops into the external auditory canals and nostrils, and massaged into the five sense organs (*aimpori*) and plantar foot soles (*ullankal*).\n- **Cutaneous Vasodilation & Conductive Heat Transfer**: Vigorous dermal massage stimulates mechanoreceptors and nitric-oxide-mediated arteriolar vasodilation in the scalp and skin plexus. Because sesame oil has a high specific heat capacity and low surface tension, it draws metabolic core heat outward from the cranial vault and optic nerve, preventing dry-eye syndromes, epistaxis, and *pitta* insomnia.\n\n**2. Sesamin & Sesamolin Transdermal Protection:**\n- Cold-pressed gingelly oil contains unique lignans (**sesamin, sesamolin, and sesamol**) and $\\gamma$-tocopherol that scavenge UV-induced lipid peroxides in the stratum corneum while maintaining synovial joint lubrication."
    },
    {
        "slug": "concept-nalangu-maa-and-thirumanjana-podi-antimicrobial-phytochemistry-and-icon-de-greasing",
        "category": "concept",
        "file": "concept-nalangu-maa-and-thirumanjana-podi-antimicrobial-phytochemistry-and-icon-de-greasing.md",
        "name_en": "Nalangu-Maa Herbal Ubtan & Temple Thirumanjana-Podi Antimicrobial Phytochemistry",
        "name_ta": "நலங்கு மாவு மற்றும் கோயில் திருமஞ்சனப் பொடியின் நுண்ணுயிர் எதிர்ப்பு வேதியியலும் திருமேனித் தூய்மையும்",
        "era": "Early Medieval to Modern Era",
        "year_start": 600,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Phytochemical formulation and surface-cleaning science of Tamil Nalangu-Maa bridal/pediatric bath powders and sacred temple Thirumanjana-Podi: combining green gram proteins with sesquiterpene-rich Curcuma aromatica (kasturi-manjal), Curcuma zedoaria (poolankizhangu), Cyperus rotundus (korai-kizhangu), and borneol camphor for antimicrobial deodorization and icon degreasing.",
        "summary_ta": "பயத்தம் மாவு, கஸ்தூரி மஞ்சள், பூலாங்கிழங்கு, கோரைக்கிழங்கு, வெட்டிவேர் மற்றும் பச்சைக் கற்பூரம் கலந்த நலங்கு மாவு மற்றும் கோயில் திருமஞ்சனப் பொடியின் நுண்ணுயிர் எதிர்ப்பு மற்றும் நெய்-எண்ணெய்ப் பிசுக்கு நீக்கும் வேதியியல்.",
        "sources": [
            "Pharmacognosy of Curcuma aromatica and Curcuma zedoaria",
            "Agama & Pancharatra Thirumanjanam Manuals",
            "Siddha Pediatric & Bridal Nalangu Formulations"
        ],
        "content": "# Nalangu-Maa & Temple Thirumanjana-Podi Antimicrobial Phytochemistry\n\nBoth domestic celebratory bath scrubs (*Nalangu-Maa*) and sacred temple lustration powders (*Thirumanjana-Podi*) share a rationalized phytochemical architecture pairing proteinaceous grain flours with volatile rhizome terpenes:\n\n**1. Bioactive Rhizome & Root Matrix:**\n- **Kasturi-Manjal (*Curcuma aromatica*) & Poolankizhangu (*Curcuma zedoaria*)**: Unlike culinary *Curcuma longa*, these wild aromatic rhizomes are low in yellow-staining curcuminoids but rich in volatile **germacrone, curzerenone, and $\\alpha$-turmerone** sesquiterpenes that inhibit *Staphylococcus epidermidis* and *Corynebacterium* sweat odor without staining skin or vestments yellow.\n- **Korai-Kizhangu (*Cyperus rotundus*) & Vetiver (*Chrysopogon zizanioides*)**: Cyperene and khusimol essential oils act as natural astringents and evaporative cooling fixatives that anchor fragrance on skin for hours after rinsing.\n\n**2. Temple Icon Degreasing (*Thirumanjanam / Abhishekam*):**\n- During daily or festival *Abhishekam*, granite (*moolavar*) and bronze (*utsavar*) icons are anointed with ghee, sesame oil, milk, and honey. Scrubbing with *Thirumanjana-Podi* (sifted green gram *payatham-maa*, *poolankizhangu*, cardamom, saffron, and *pachai-karpooram* borneol) absorbs hydrophobic butterfat into legume starch-protein matrices while borneol prevents fungal biofilm growth inside porous stone crevices."
    },
    {
        "slug": "technology-kuzhambu-ennai-decoction-boiling-and-21-herb-seekakai-arappu-milling",
        "category": "technology",
        "file": "technology-kuzhambu-ennai-decoction-boiling-and-21-herb-seekakai-arappu-milling.md",
        "name_en": "Kaaychiya Ennai Herbal Oil Decoction Boiling & 21-Ingredient Seekakai-Arappu Stone Milling",
        "name_ta": "மூலிகை எண்ணெய் காய்ச்சும் பக்குவமும் (மெழுகு பதம்) 21-மூலிகைச் சீயக்காய்-அரப்பு இடிக்கும் தொழில்நுட்பமும்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Pharmaceutical and household processing technology for Tamil oil-bath preparations: clarifying cold-pressed gingelly oil (chekku-nallenai) by boiling with black pepper, cumin, fenugreek, garlic, and Eclipta/Alternanthera leaf juices to the anhydrous mezhugu-patham endpoint, alongside sun-crisping and pounding 21-herb seekakai powders.",
        "summary_ta": "செக்கு நல்லெண்ணெயில் மிளகு, சீரகம், வெந்தயம், கரிசலாங்கண்ணி, பொன்னாங்கண்ணிச் சாறு சேர்த்து மெழுகு பதத்தில் தைலம் காய்ச்சும் நுட்பமும், 21 மூலிகைகளை வெயிலில் உலர்த்தி உரலில் இடித்துச் சீயக்காய்த் தூள் தயாரிக்கும் முறையும்.",
        "sources": [
            "Siddha Vaithiya Thirattu (Thaila Vaguppu)",
            "Traditional Household Medicine of Tamil Nadu",
            "Herbal Processing & Milling Practices of South India"
        ],
        "content": "# Kaaychiya Ennai Decoction Boiling & 21-Herb Seekakai-Arappu Milling\n\nPreparing non-rancid medicated bath oils (*thailam*) and non-gritty herbal cleansing flours requires precise thermal dehydration and multi-stage particle size reduction:\n\n**1. Anhydrous Oil Decoction (*Thaila-Paagam / Mezhugu-Patham*):**\n- **Botanical Infusion**: Wood-pressed gingelly oil (*marachekku nallenai*) is heated in a heavy soapstone or brass cauldron with crushed black pepper (*milagu*), cumin (*seeragam*), dry ginger (*chukku*), garlic cloves, fenugreek (*vendhayam*), and fresh leaf juices of *karisalanganni* (*Eclipta prostrata*) and *ponnanganni* (*Alternanthera sessilis*).\n- **Endpoint Determination**: Simmering continues at $100\\text{--}105^\\circ\\text{C}$ until all aqueous plant sap evaporates, bubbling subsides, and the herbal sediment rolls between the fingers like soft beeswax (**mezhugu-patham**). Removing the vessel at this exact stage transfers fat-soluble phytosterols, piperine, and wedelolactone into the oil while eliminating free water that would cause hydrolytic rancidity.\n\n**2. 21-Ingredient Seekakai Milling (*Seekakai-Podi*):**\n- Dried *seekakai* pods are fibrous and resinous; to prevent gumming during grinding, artisans sun-bake the pods with *manipungan* pericarps, fenugreek, green gram, dried hibiscus petals (*chembaruthi*), curry leaves, *avaram-poo* (*Senna auriculata*), *vetiver*, and dried lemon peel, pound the brittle mix in granite mortars (*ural-ulakkai*), and sieve through fine muslin (*vasthira-kayam*)."
    },
    {
        "slug": "technology-akil-sambirani-hair-fumigation-and-temple-thirumanjanam-abhishekam-compounding",
        "category": "technology",
        "file": "technology-akil-sambirani-hair-fumigation-and-temple-thirumanjanam-abhishekam-compounding.md",
        "name_en": "Akil-Sambirani Wicker-Cone Hair Fumigation & Temple Thirumanjanam Abhishekam Compounding",
        "name_ta": "அகில்-சாம்பிராணி கூந்தல் புகையூட்டும் நுட்பமும் கோயில் திருமஞ்சன அபிஷேகக் கலவைத் தயாரிப்பும்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Post-bath thermal drying and aromatic fumigation engineering (koonthal-pugai) using inverted wicker baskets over smoldering Aquilaria agallocha (akil) and Styrax benzoin (sambirani) embers to sterilize and dry thick wet hair, paired with liturgical Thirumanjanam hydro-distillation and spice-paste compounding in temple kitchens.",
        "summary_ta": "ஈரக் கூந்தலை உலர்த்தவும் தலைநீர் கோர்க்காமல் தடுக்கவும் அகில் மற்றும் பால் சாம்பிராணிப் புகையை மூங்கில் கூடை வழியே செலுத்தும் தொழில்நுட்பமும், கோயில் மடப்பள்ளியில் திருமஞ்சன வாசனைத் திரவியம் கூட்டும் முறையும்.",
        "sources": [
            "Silappadikaram Commentary (Adiyarkkunallar on Koonthal Pugai)",
            "Srirangam Koil Olugu (Thirumanjanam Protocols)",
            "Traditional Fumigation & Aromatherapy in Siddha Practice"
        ],
        "content": "# Akil-Sambirani Wicker-Cone Hair Fumigation & Temple Thirumanjanam Compounding\n\nTwo specialized aromatic technologies complete the Tamil bathing cycle—thermal-antiseptic hair fumigation in the home and sacred hydro-aromatic compounding in the temple sanctum:\n\n**1. Wicker-Cone Hair Fumigation (*Koonthal-Pugaiyoothuthal*):**\n- **Apparatus & Thermodynamics**: After an *Ennai-Kuzhial* wash, leaving dense, waist-length hair damp invites sinus congestion (*neer-korthal*) and scalp dermatophytes. Red-hot coconut-shell charcoal embers are placed in a terracotta censer (*dhupakkal*), sprinkled with powdered *paal-sambirani* (*Styrax benzoin* resin), *akil* (*Aquilaria agallocha* heartwood chips), and *vilamichai* roots, and covered with a tall, inverted bell-shaped bamboo wicker cage (*pugai-koodai*).\n- **Convective Sublimation**: Damp tresses are spread across the cool exterior lattice of the wicker cone. Rising warm air ($45\\text{--}55^\\circ\\text{C}$) gently evaporates capillary moisture while sublimated **benzoic acid, cinnamic esters, and agarospirol** condense onto the keratin shaft, imparting lasting fragrance and antifungal protection.\n\n**2. Temple Thirumanjanam Compounding:**\n- In temple *madappalli* rooms, *Thirumanjanam* attendants steep crushed *vetiver*, *vilamichai*, nutmeg (*jathikkai*), mace (*jathipathiri*), cloves (*kirambu*), and *pachai-karpooram* in muslin bags inside copper *kalasam* urns alongside freshly milled *thirumanjana-podi* pastes."
    },
    {
        "slug": "artifact-ennai-kinnam-oil-bowls-perforated-koonthal-pugai-koodai-and-vetiver-scrubbers",
        "category": "artifact",
        "file": "artifact-ennai-kinnam-oil-bowls-perforated-koonthal-pugai-koodai-and-vetiver-scrubbers.md",
        "name_en": "Ennai-Kinnam Brass Oil Bowls, Wicker Pugai-Koodai Fumigators, Manjal-Kallu & Vetiver Scrubbers",
        "name_ta": "எண்ணெய்க் கிண்ணம், கூந்தல் புகைக்கூடை, மஞ்சள் உரைகல் மற்றும் வெட்டிவேர்-பீர்க்கங்காய் நார் தேய்ப்பான்கள்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Material artifact assemblage of traditional Tamil bathing and grooming: heavy cast-brass and bell-metal oil cups (ennai-kinnam / ennai-chatti), open-weave bamboo hair-drying cones (koonthal-pugai-koodai), circular pitted sandstone turmeric grinding stones (manjal-kallu), and woven vetiver and ridge-gourd fiber scrubbers.",
        "summary_ta": "தமிழர் நீராடல் பண்பாட்டின் பயன்பாட்டுப் பொருட்கள்: வெண்கல மற்றும் பித்தளை எண்ணெய்க் கிண்ணங்கள், மூங்கில் புகைக்கூடைகள், கஸ்தூரி மஞ்சள் இழைக்கும் சொரசொரப்பான மஞ்சள் கல் மற்றும் வெட்டிவேர், பீர்க்கங்காய் நார் தேய்ப்பான்கள்.",
        "sources": [
            "Ethnographic Catalog of Tamil Household Brassware & Basketry",
            "Government Museum Chennai Anthropology Collection",
            "Material Culture of South Indian Domestic Rituals"
        ],
        "content": "# Ennai-Kinnam Oil Bowls, Pugai-Koodai Fumigators, Manjal-Kallu & Scrubbers\n\nTraditional Tamil bathhouses (*kuzhial-arai*) and riverside bathing kits feature a dedicated suite of metallurgical, lithic, and plant-fiber implements:\n\n**Artifact Typology:**\n1. **Ennai-Kinnam & Ennai-Chatti (Oil-Warming Bowls)**: Thick-bottomed hemispherical bowls cast in high-tin bell-metal (*vengalam*) or brass (*pithalai*), often mounted on a flared pedestal foot or fitted with central compartments for holding warm medicated gingelly oil in one well and *seekakai-arappu* paste in the other.\n2. **Manjal-Kallu (Turmeric & Sandalwood Rubbing Stone)**: A circular, flat-topped disc ($12\\text{--}20\\text{ cm}$ diameter) of fine-grained rough sandstone or granite kept beside the water trough. Wetting the stone and rubbing whole *kasturi-manjal* rhizomes or sandalwood billets in circular strokes yields a micro-fine, silky fresh emulsion unattainable with dry-milled powders.\n3. **Koonthal-Pugai-Koodai & Dhupakkal**: Conical open-lattice baskets woven from split bamboo or *pirambu* (rattan) paired with handled terracotta or brass incense braziers.\n4. **Vetiver & Peerkangai-Naar Scrubbers**: Braided pads of aromatic *vetiver* roots and sun-retted fibrous vascular skeletons of ripe ridge gourds (*Luffa acutangula* / *peerkangai-naar*) used for gentle epidermal exfoliation."
    },
    {
        "slug": "artifact-arappu-seekakai-bundles-kasturi-manjal-rhizomes-and-temple-thirumanjana-kalasam",
        "category": "artifact",
        "file": "artifact-arappu-seekakai-bundles-kasturi-manjal-rhizomes-and-temple-thirumanjana-kalasam.md",
        "name_en": "Seekakai Pod Bundles, Usilai-Arappu Leaf Flour, Kasturi-Manjal Rhizomes & Sahasradhara Kalasams",
        "name_ta": "சீயக்காய்க் கட்டுகள், உசிலை அரப்புத் தூள், கஸ்தூரி மஞ்சள் கிழங்குகள் மற்றும் சஹஸ்ரதாரா திருமஞ்சனக் கலசங்கள்",
        "era": "Early Medieval to Modern Era",
        "year_start": 500,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Botanical trade goods and liturgical lustration vessels of the Tamil bathing tradition: dried dark-brown Acacia concinna pod bundles, vibrant green Albizia amara leaf powder packets, cured Curcuma aromatica and Curcuma zedoaria rhizomes, and perforated 1008-hole copper/silver Sahasradhara Thirumanjana plates.",
        "summary_ta": "நாட்டு மருந்துக் கடைகளில் விற்பனையாகும் உலர்ந்த சீயக்காய்க் கட்டுகள், பச்சை நிற உசிலை அரப்புப் பொடி, கஸ்தூரி மஞ்சள் மற்றும் பூலாங்கிழங்கு வகைகள் மற்றும் கோயில் திருமஞ்சனத்திற்குப் பயன்படும் ஆயிரம் கண் சஹஸ்ரதாரா தட்டுகள்.",
        "sources": [
            "Materia Medica of South Indian Raw Drug Markets",
            "South Indian Temple Bronzes & Ritual Vessels Catalog",
            "Forest Minor Produce Trade of Tamil Nadu"
        ],
        "content": "# Seekakai Bundles, Arappu Flour, Kasturi-Manjal & Sahasradhara Kalasams\n\nBoth the domestic bath shelf and the temple *Thirumanjanam* treasury maintain standardized botanical commodities and hydrodynamic pouring vessels:\n\n**Botanical & Liturgical Artifacts:**\n1. **Dried Seekakai & Manipungan Bundles**: Harvested from thorny forest climbers (*Acacia concinna*) in late winter, mature flat pods are sun-cured until wrinkly and dark mahogany-brown, then tied with palmyra fiber into weighed market bundles alongside glossy, amber-translucent *manipungan* soapnut pericarps.\n2. **Usilai-Arappu Leaf Flour**: Fine, olive-green powder milled from shade-dried pinnate leaflets of *Albizia amara* harvested from dry deciduous *Mullai/Kurinji* slopes—prized across Kongu, Madurai, and Kaveri districts for its cooling, non-eye-stinging lather.\n3. **Kasturi-Manjal & Poolankizhangu Cured Fingers**: Boiled and sun-dried aromatic rhizome fingers sold whole to preserve volatile sesquiterpenes against oxidation until rubbed on a *manjal-kallu*.\n4. **Thirumanjana-Kalasam & Sahasradhara Thattu**: Broad-bellied copper, silver, or gold-plated sacred water pots (*kalasam*) paired with a concave sieve-plate (*Sahasradhara*) pierced with 108 or 1,008 calibrated pinholes that divide herbal *Thirumanjanam* infusions into a gentle, uniform shower over the deity."
    },
    {
        "slug": "institution-temple-thirumanjanam-paricharakar-guilds-and-nattu-marunthu-kadai-apothecaries",
        "category": "institution",
        "file": "institution-temple-thirumanjanam-paricharakar-guilds-and-nattu-marunthu-kadai-apothecaries.md",
        "name_en": "Temple Thirumanjanam Paricharakar Service Endowments & Nattu-Marunthu-Kadai Apothecary Guilds",
        "name_ta": "கோயில் திருமஞ்சனப் பரிசாரகர் கட்டளைகளும் நாட்டு மருந்துக் கடை மூலிகை வணிகர் மரபுகளும்",
        "era": "Medieval to Modern Era",
        "year_start": 800,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Institutional and commercial networks governing sacred lustration and herbal hygiene: temple inscriptions endowing Thirumanjanam water-bearers, flower-garland gardens (nandavanam), and spice-compounding shares (kattalai), alongside hereditary Nattu-Marunthu-Kadai (raw-drug apothecary) guilds linking forest gatherers with urban households.",
        "summary_ta": "காவிரியிலிருந்து திருமஞ்சன நீர் கொணரும் பரிசாரகர் மரபுகள், நந்தவன மற்றும் வாசனைத் திரவியக் கட்டளைகள் (கல்வெட்டுக் கொடைகள்) மற்றும் மலைவாழ் மக்கள் சேகரிக்கும் சீயக்காய், அரப்பு, மூலிகைகளை விநியோகிக்கும் நாட்டு மருந்துக் கடை வணிக அமைப்புகள்.",
        "sources": [
            "South Indian Inscriptions (Srirangam, Chidambaram & Thanjavur Thirumanjanam Grants)",
            "Srirangam Koil Olugu Chronicles",
            "Traditional Raw Drug Trade & Siddha Apothecary Guilds of Tamil Nadu"
        ],
        "content": "# Temple Thirumanjanam Service Endowments & Nattu-Marunthu-Kadai Apothecaries\n\nThe continuity of Tamil herbal bathing and sacred lustration across twelve centuries rests on two interlocking institutions—temple *Thirumanjanam Kattalai* endowments and urban *Nattu-Marunthu-Kadai* apothecary guilds:\n\n**1. Epigraphic Thirumanjanam Kattalai Endowments:**\n- Chola, Pandya, Hoysala, and Vijayanagara stone inscriptions at Srirangam, Thanjavur, and Kanchipuram record dedicated land and gold grants (*Thirumanjana-Kattalai*) financing hereditary attendants (*paricharakar* / *theerthakarar*) who fetch fresh river water in sealed *kalasams* accompanied by temple elephants and *nagaswaram* music.\n- Temple *Koil Olugu* codes specify exact weight rations (*paditharam*) of *kasturi* (musk), *pachai-karpooram* (borneol), saffron, *vetiver*, sandalwood billets, *seekakai*, and green gram issued from the temple storehouse (*ukranam*) for daily and festive *snapanam* baths.\n\n**2. Nattu-Marunthu-Kadai (Botanical Apothecary Guilds):**\n- Operating in dedicated bazaar streets around major temples, hereditary raw-drug merchants procure wild *seekakai* pods, *usilai* leaves, and *manipungan* nuts from hill forest cooperatives (*Malai-Vazh Makkal*) in the Pachamalai, Kolli, and Javadi hills, grading and compounding seasonal *Deepavali Ennai-Kuzhial* and bridal *Nalangu* kits."
    },
    {
        "slug": "place-srirangam-ancient-kaveri-thirumanjanam-aromatics-and-herbal-snana-haven",
        "category": "place",
        "file": "place-srirangam-ancient-kaveri-thirumanjanam-aromatics-and-herbal-snana-haven.md",
        "name_en": "Srirangam: Ancient Kaveri Island Thirumanjanam Aromatics & Herbal Snana Haven",
        "name_ta": "ஸ்ரீரங்கம் (திருவரங்கம்) - காவிரித் திருமஞ்சன நறுமணக் கலவை மற்றும் மூலிகை நீராடல் மரபின் தாயகத் தளம்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Sacred river island (lat 10.8620, lng 78.6900, thinai: marutham) embraced by the Kaveri and Kollidam rivers in Tiruchirappalli district, celebrated in Tamil literature and temple chronicles for its daily elephant-borne Kaveri Thirumanjanam processions, aromatic herbal compounding chambers, and centuries-old Amma Mandapam ghat oil-bathing traditions.",
        "summary_ta": "காவிரி மற்றும் கொள்ளிடம் ஆறுகளால் சூழப்பட்ட திருவரங்கம் (ஸ்ரீரங்கம், lat 10.8620, lng 78.6900, மருதத் திணை): கோயில் யானை மீது காவிரித் தீர்த்தம் கொணரும் திருமஞ்சன மரபும், அம்மா மண்டபம் படித்துறை எண்ணெய்க் குளியல் மற்றும் மூலிகைச் சுண்ணப் பொடித் தயாரிப்பும் தழைத்த வரலாற்றுத் தளம்.",
        "sources": [
            "Srirangam Koil Olugu",
            "Silappadikaram & Divya Prabandham (SrirangamPasurams)",
            "Tiruchirappalli District Gazetteer"
        ],
        "content": "# Srirangam: Ancient Kaveri Island Thirumanjanam Aromatics & Herbal Snana Haven\n\nSituated at `lat 10.8620, lng 78.6900` on the fertile alluvial island formed by the bifurcation of the Kaveri and Kollidam rivers in Tiruchirappalli district, Srirangam (*Thiruvarangam*) is the preeminent living citadel of Tamil ritual hydro-aromatics (*Thirumanjanam*) and riverine herbal bathing:\n\n**Sacred Hydro-Aromatic & Bathing Heritage:**\n- **Daily Kaveri Thirumanjanam Procession**: Every morning since the medieval era, silver and gold vessels filled from the flowing Kaveri at the southern *Amma Mandapam* ghats are carried in ceremonial procession atop the temple elephant through the seven concentric *prakarams* (*chitthirai* to *utthara* streets) of Sri Ranganathaswamy Temple for the sanctum lustration.\n- **Herbal Compounding & Nellalavu Measures**: The temple's historic spice and herbal chambers (*parimala-arai*) compound traditional *thirumanjana-podi* (green gram, *poolankizhangu*, cardamom, saffron, and borneol camphor), sandalwood paste (*chandanam*), and boiled herb decoctions (*kashayam*) administered during *Jyeshtabhishekam* (when the 18-herb protective coat *thailakappu* is applied to the stucco *Moolavar* icon).\n- **Kaveri Ghat Ennai-Kuzhial Culture**: Along the stepped stone ghats of the Kaveri, pilgrims and island residents practice traditional Saturday and *Tula-Masam* (*Aippasi*) river bathing using *marachekku nallenai*, Pachamalai-sourced *usilai-arappu*, and 21-herb *seekakai* pastes."
    }
]

EDGES = [
    [
        "text-paripadal-silappadikaram-and-tiruppavai-on-aromatic-hair-washing-and-river-bathing",
        "describes",
        "technology-akil-sambirani-hair-fumigation-and-temple-thirumanjanam-abhishekam-compounding",
        "material_culture",
        "Sangam to Bhakti Era",
        "Paripadal and Silappadikaram document washing five-plaited hair with herbal infusions and drying damp tresses over akil and sambirani smoke.",
        "Silappadikaram & Paripadal"
    ],
    [
        "text-paripadal-silappadikaram-and-tiruppavai-on-aromatic-hair-washing-and-river-bathing",
        "celebrates",
        "place-srirangam-ancient-kaveri-thirumanjanam-aromatics-and-herbal-snana-haven",
        "material_culture",
        "Sangam to Modern Era",
        "Classical Tamil hymns celebrate sacred bathing in the fragrant currents of the Kaveri river embracing Srirangam island.",
        "Silappadikaram & Divya Prabandham"
    ],
    [
        "concept-seekakai-arappu-and-manipungan-triterpenoid-saponin-micelle-emulsification",
        "explains",
        "artifact-arappu-seekakai-bundles-kasturi-manjal-rhizomes-and-temple-thirumanjana-kalasam",
        "material_culture",
        "Sangam to Modern Era",
        "Triterpenoid saponin glycosides in Acacia concinna pods and Albizia amara leaves emulsify heavy sesame oil at skin-friendly acidic pH.",
        "Phytochemistry Studies"
    ],
    [
        "concept-siddha-ennai-kuzhial-gingelly-oil-bath-pitta-thermoregulation-and-vagus-toning",
        "governs",
        "technology-kuzhambu-ennai-decoction-boiling-and-21-herb-seekakai-arappu-milling",
        "material_culture",
        "Sangam to Modern Era",
        "Siddha thermoregulatory principles for dissipating cranial pitta heat direct the boiling of pepper, cumin, and karisalanganni into gingelly bath oil.",
        "Pathartha Guna Chintamani"
    ],
    [
        "concept-nalangu-maa-and-thirumanjana-podi-antimicrobial-phytochemistry-and-icon-de-greasing",
        "informs",
        "technology-akil-sambirani-hair-fumigation-and-temple-thirumanjanam-abhishekam-compounding",
        "material_culture",
        "Early Medieval to Modern Era",
        "Antimicrobial sesquiterpenes in kasturi-manjal and poolankizhangu coupled with green-gram lipid absorption guide temple Thirumanjanam compounding.",
        "Agama Manuals"
    ],
    [
        "technology-kuzhambu-ennai-decoction-boiling-and-21-herb-seekakai-arappu-milling",
        "utilizes",
        "artifact-ennai-kinnam-oil-bowls-perforated-koonthal-pugai-koodai-and-vetiver-scrubbers",
        "material_culture",
        "Sangam to Modern Era",
        "Medicated bath oils and freshly rubbed turmeric emulsions are prepared and applied using brass ennai-kinnam bowls and sandstone manjal-kallu discs.",
        "Household Material Culture"
    ],
    [
        "technology-akil-sambirani-hair-fumigation-and-temple-thirumanjanam-abhishekam-compounding",
        "employs",
        "artifact-ennai-kinnam-oil-bowls-perforated-koonthal-pugai-koodai-and-vetiver-scrubbers",
        "material_culture",
        "Sangam to Modern Era",
        "Post-bath hair fumigation relies on inverted bamboo wicker pugai-koodai cones placed over terracotta benzoin and agarwood censers.",
        "Silappadikaram Commentary"
    ],
    [
        "technology-akil-sambirani-hair-fumigation-and-temple-thirumanjanam-abhishekam-compounding",
        "dispenses_through",
        "artifact-arappu-seekakai-bundles-kasturi-manjal-rhizomes-and-temple-thirumanjana-kalasam",
        "material_culture",
        "Early Medieval to Modern Era",
        "Compounded herbal Thirumanjanam infusions are poured through 1008-hole Sahasradhara plates and silver kalasams during temple abhishekam.",
        "Srirangam Koil Olugu"
    ],
    [
        "institution-temple-thirumanjanam-paricharakar-guilds-and-nattu-marunthu-kadai-apothecaries",
        "supplies",
        "artifact-arappu-seekakai-bundles-kasturi-manjal-rhizomes-and-temple-thirumanjana-kalasam",
        "material_culture",
        "Medieval to Modern Era",
        "Nattu-Marunthu-Kadai apothecary guilds and temple kattalai endowments procure forest seekakai pods, usilai-arappu, and aromatic rhizomes.",
        "South Indian Inscriptions"
    ],
    [
        "institution-temple-thirumanjanam-paricharakar-guilds-and-nattu-marunthu-kadai-apothecaries",
        "operates_in",
        "place-srirangam-ancient-kaveri-thirumanjanam-aromatics-and-herbal-snana-haven",
        "material_culture",
        "Medieval to Modern Era",
        "Hereditary Thirumanjanam attendants and herbal compounders serve the daily Kaveri lustration rites of Sri Ranganathaswamy Temple at Srirangam.",
        "Srirangam Koil Olugu"
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
