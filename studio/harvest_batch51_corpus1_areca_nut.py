#!/usr/bin/env python3
"""
Harvester: Batch 51 - Ancient Tamil Areca Nut Horticulture, Kalipakku Tannin-Boiling Curing, Pakku-Vetti Lever Shears & Tambula Rituals
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
        "slug": "text-sangam-and-silappadikaram-on-kamugu-areca-palms-and-adaikkai-tambulam",
        "category": "text",
        "file": "text-sangam-and-silappadikaram-on-kamugu-areca-palms-and-adaikkai-tambulam.md",
        "name_en": "Silappadikaram, Pattinappalai & Perumpanarruppadai on Kamugu Areca Palms & Adaikkai",
        "name_ta": "சிலப்பதிகாரம், பட்டினப்பாலை மற்றும் பெரும்பாணாற்றுப்படையில் கமுகு மற்றும் அடைக்காய்த் தாம்பூல மரபு",
        "era": "Sangam to Post-Sangam Era",
        "year_start": -300,
        "year_end": 600,
        "thinai": "marutham",
        "summary_en": "Classical Tamil literary accounts in Perumpanarruppadai, Pattinappalai, Maduraikanchi, and Silappadikaram celebrating emerald-ringed areca palms (kamugu / kazhugu), clusters of aromatic areca nuts (pakku / adaikkai), and the ritual offering of betel-nut quids with slaked lime.",
        "summary_ta": "பெரும்பாணாற்றுப்படை, பட்டினப்பாலை, மதுரைக்காஞ்சி மற்றும் சிலப்பதிகாரத்தில் விவரிக்கப்படும் கமுகு (பாக்கு) மரச் சோலைகள், அடைக்காய்க் குலைகள் மற்றும் வெற்றிலை-சுண்ணாம்பு தாம்பூல விருந்தோம்பல்.",
        "sources": [
            "Silappadikaram",
            "Pattinappalai",
            "Perumpanarruppadai",
            "Maduraikanchi"
        ],
        "content": "# Sangam & Silappadikaram Accounts of Kamugu Areca Palms & Adaikkai\n\nIn classical Tamil poetry, the tall, ringed areca-nut palm (*kamugu* or *kazhugu*, *Areca catechu*) and its fruit (*adaikkai* / *pakku*) are emblems of fertile orchard wealth and sacred hospitality:\n\n**Literary Attestations:**\n- **Perumpanarruppadai & Pattinappalai**: The idylls compare the smooth, green, internode-ringed trunk of the *kamugu* palm rising above banana and coconut groves to a bundle of emerald bamboo rods, bearing dense pendulous bunches (*kulai*) of liquid-cored tender nuts, golden ripe fruits, and fragrant spathes (*madal*).\n- **Maduraikanchi & Silappadikaram**: In *Silappadikaram*, Kannagi's final meal presented to Kovalan concludes with the ceremonial offering of *adaikkai* (areca nut) and *vetrilai* (betel leaf) with *chunnambu* (calcined shell lime)—establishing the trinity of *tambulam* as the seal of conjugal affection, courtly honour, and covenant."
    },
    {
        "slug": "concept-areca-catechu-condensed-tannin-arecoline-chemistry-and-alkaline-ortho-quinone-reddening",
        "category": "concept",
        "file": "concept-areca-catechu-condensed-tannin-arecoline-chemistry-and-alkaline-ortho-quinone-reddening.md",
        "name_en": "Areca catechu Ruminate Endosperm Tannins, Arecoline Alkaloids & Alkaline Ortho-Quinone Reddening",
        "name_ta": "பாக்கு விதையின் டானின்-அரிகோலின் வேதியியலும் சுண்ணாம்புக் காரத்தால் சிவப்பு நிறமாகும் வினையும்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Phytochemistry of the Areca catechu kernel: ruminate endosperm rich in condensed proanthocyanidin tannins (catechin, epicatechin, leucocyanidin), gallic acid, and parasympathetic alkaloids (arecoline, guvacine), which oxidize into crimson ortho-quinones at pH > 9 when chewed with slaked lime.",
        "summary_ta": "பாக்கு விதையிலுள்ள கேட்டசின் டானின்கள் மற்றும் அரிகோலின் ஆல்கலாய்டுகளின் வேதியியலும், வெற்றிலையுடன் சுண்ணாம்பு (கார நிலை pH > 9) சேரும்போது ஆர்த்தோ-குயினோன்களாக மாறிச் செந்நிறம் தரும் வினையும்.",
        "sources": [
            "Phytochemistry of Areca catechu",
            "Central Plantation Crops Research Institute Areca Monographs",
            "Biochemistry of Tambula Masticatories"
        ],
        "content": "# Areca catechu Tannin-Arecoline Chemistry & Alkaline Reddening\n\nThe marbled interior (ruminate endosperm) of the *Areca catechu* seed owes its astringency, mild central-nervous-system stimulation, and ruby-red colour reaction to a specific pairing of polyphenols and pyridine alkaloids:\n\n**Phytochemical Mechanics:**\n- **Condensed Tannins (*Areca Catechins*)**: Tender-ripe nuts contain 18–26% polyphenols—principally **(+)-catechin, (-)-epicatechin, and polymeric procyanidins (arecatannins)**—alongside gallic acid and ~14% myristic/lauric seed fats. As the nut over-ripens on the tree (*kottai-pakku*), soluble tannins polymerize into insoluble phlobaphenes, reducing harsh astringency (*thuvarppu*).\n- **Alkaloid Free-Basing & Crimson Chromophore**: In the presence of alkaline slaked shell-lime ($\\text{Ca(OH)}_2$, raising salivary $\\text{pH}$ above $9.5$), two simultaneous reactions occur:\n  1. Protonated **arecoline** and **guvacine** salts are converted into lipid-soluble free bases rapidly absorbed across the buccal mucosa, stimulating salivation and digestive peristalsis.\n  2. Catechins and leucocyanidins undergo base-catalyzed oxidative coupling with oxygen and betel-leaf eugenol/hydroxychavicol to form brilliant crimson **ortho-quinone** pigments (*cevvai*)."
    },
    {
        "slug": "technology-kalipakku-copper-cauldron-tannin-mother-liquor-boiling-and-ruby-glaze-curing",
        "category": "technology",
        "file": "technology-kalipakku-copper-cauldron-tannin-mother-liquor-boiling-and-ruby-glaze-curing.md",
        "name_en": "Kalipakku Copper-Cauldron Boiling, Concentrated Kali-Neer Mother-Liquor Coating & Sun Curing",
        "name_ta": "களிப்பாக்கு செப்புக் கொப்பரை காய்ச்சுதல், களிநீர் (சोगை) அடர் சாறு பூசுதல் மற்றும் வெயில் உலர்த்தல்",
        "era": "Medieval to Modern Era",
        "year_start": 800,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Traditional Tamil post-harvest technology of manufacturing Kalipakku (boiled red-glazed areca nut): harvesting 7-month tender-ripe nuts, husking, cutting into halves/quarters or thin cheeval flakes, boiling in copper cauldrons with aged tannin mother-liquor (kali / chogai) to mellow astringency and deposit a glossy ruby coat.",
        "summary_ta": "தமிழ்நாட்டின் தனித்துவமான 'களிப்பாக்கு' தயாரிப்பு நுட்பம்: இளம்பருவப் பாக்குகளை உரித்து நறுக்கி, செப்புக் கொப்பரையில் முந்தைய ஈடுகளின் அடர்ந்த 'களிநீர்' (சோகை) சேர்த்துக் காய்ச்சிப் பளபளப்பான சிவப்பு நிறமேற்றி வெயிலில் உலர்த்தும் முறை.",
        "sources": [
            "Mettupalayam and Pollachi Kalipakku Curing Traditions",
            "Madras Agricultural Department Bulletins on Arecanut Curing",
            "Traditional Food & Masticatory Processing of Tamil Nadu"
        ],
        "content": "# Kalipakku Copper-Cauldron Boiling & Kali-Neer Ruby Glaze Curing\n\nUnlike whole sun-dried white nut (*kottai-pakku* / *chali*), Tamil Nadu's signature **Kalipakku** (and paper-thin **Cheeval**) is a thermally and chemically mellowed delicacy prized for its tender bite and glossy dark-mahogany sheen:\n\n**Kalipakku Processing Sequence:**\n1. **Tender-Ripe Harvesting (*Vettu-Pakku*)**: Bunches are lowered by rope at 6.5 to 7 months maturity when the fibrous husk is turning greenish-yellow and the kernel can still be fingernail-dented.\n2. **Husking & Slicing**: Women artisans husk the fresh nuts with a curved sickle blade mounted on a floor plank and slice the kernels into quarters (*idi-pakku*), segments (*ottu-vettu*), or wafer-thin shavings (*cheeval*).\n3. **Boiling in Aged *Kali-Neer* (*Chogai*)**: The raw slices are boiled for 60–90 minutes in a tinned copper cauldron (*kopparai*) containing water and a measured ladle of thick, ruby-black **Kali-Neer**—the concentrated tannin mother-liquor saved and thickened from dozens of previous boilings, often enriched with *naval* (*Syzygium cumini*) bark, *karungali* heartwood, a touch of jaggery, and gingelly oil.\n4. **Double & Triple Coating (*Iru-Kali / Mukkan-Kali*)**: Boiling leaches out raw acrid tannins while the viscous *kali* liquor polymerizes onto the surface of each nut. Dried on bamboo mats under the sun for 5–7 days, the nuts shrink into hard, jewel-like ruby-black morsels."
    },
    {
        "slug": "concept-pakku-vetti-second-class-lever-mechanics-and-eccentric-pivot-slicing-geometry",
        "category": "concept",
        "file": "concept-pakku-vetti-second-class-lever-mechanics-and-eccentric-pivot-slicing-geometry.md",
        "name_en": "Pakku-Vetti Second-Class Lever Mechanics, Mechanical Advantage & Draw-Shear Blade Geometry",
        "name_ta": "பாக்குவெட்டியின் இரண்டாம் வகை நெம்புகோல் இயந்திரவியலும் சாய்வு வெட்டு விசைப் பொறியியலும்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Mechanical engineering of the traditional South Indian nutcracker shear (pakku-vetti / adaikkai-kolluthi): operating as a hinged Class-2 lever with a 4:1 to 6:1 mechanical advantage where a convex steel upper blade sweeps across a recessed brass anvil bed in a slicing draw-cut.",
        "summary_ta": "பாரம்பரிய பாக்குவெட்டியின் இயந்திரவியல்: முனையில் சுழல் அச்சு கொண்ட இரண்டாம் வகை நெம்புகோல் (Class-2 Lever) தத்துவத்தில் 4:1 முதல் 6:1 விசைப் பெருக்கத்துடன் கடினமான பாக்கை நொறுக்காமல் சீராக நறுக்கும் பொறியியல்.",
        "sources": [
            "South Indian Bronzes and Domestic Metalwork Catalogues",
            "Kinematics of Traditional Hand Tools",
            "Ethnography of Tambula Implements"
        ],
        "content": "# Pakku-Vetti Second-Class Lever Mechanics & Draw-Shear Geometry\n\nA cured *kottai-pakku* or *kalipakku* kernel has a compressive hardness comparable to seasoned hardwood; crushing it between flat jaws shatters the nut into uneven grit. The Tamil **Pakku-Vetti** solves this through **Class-2 lever shear kinematics**:\n\n**Mechanical Principles:**\n- **Class-2 Lever Amplification**: Unlike scissors (a Class-1 lever with the pivot in the middle), the *pakku-vetti* places the riveted hinge pin (*achani*) at the extreme forward nose, the load (the hard areca nut resting in the cradle) close to the hinge ($d_{\\text{load}} \\approx 2.5\\text{ cm}$), and the user's hand squeezing the long handles at the rear ($d_{\\text{effort}} \\approx 12\\text{--}15\\text{ cm}$). This yields a **mechanical advantage of 5:1 to 6:1**, allowing effortless one-handed slicing.\n- **Arcuate Draw-Slice Action**: As the upper arm rotates downward around the forward pivot, its curved, bevel-ground high-carbon steel blade (*irumbu-alagu*) does not merely press vertically; it sweeps backward radially across the nut while passing into a narrow slot in the lower brass anvil cradle—producing a clean guillotine **slice-shear** rather than brittle crushing."
    },
    {
        "slug": "technology-paakku-mattai-areca-leaf-sheath-retting-and-thermo-mechanical-platter-pressing",
        "category": "technology",
        "file": "technology-paakku-mattai-areca-leaf-sheath-retting-and-thermo-mechanical-platter-pressing.md",
        "name_en": "Paakku-Mattai Areca Leaf-Sheath Retting, Origami Folding & Thermo-Mechanical Platter Pressing",
        "name_ta": "பாக்குமட்டை (கமுக மடல்) ஊறவைத்து மடித்தல் மற்றும் வெப்ப அச்சு உணவுத் தட்டு தயாரிப்புத் தொழில்நுட்பம்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "kurinji",
        "summary_en": "Zero-waste biomaterial technology converting shed areca palm crown-shaft leaf sheaths (kamugu-madal / paakku-mattai) into waterproof food vessels, curd pots, peasant rain hats (thoppi), and hot-pressed biodegradable feast plates.",
        "summary_ta": "மரத்திலிருந்து தானாக உதிரும் கமுக மடல்களை (பாக்குமட்டை) நீரில் நனைத்துப் பதப்படுத்தி, தயிர் மிடா மூடிகள், உழவர் தொப்பிகள் மற்றும் வெப்ப அச்சில் அழுத்திய இயற்கை உணவுத் தட்டுகளாக மாற்றும் பசுமைத் தொழில்நுட்பம்.",
        "sources": [
            "Perumpanarruppadai",
            "Traditional Rural Crafts of Kongu Nadu and Malabar",
            "Biodegradable Areca Sheath Composite Engineering"
        ],
        "content": "# Paakku-Mattai Leaf-Sheath Folding & Thermo-Mechanical Pressing\n\nEach mature *Areca catechu* palm naturally sheds 5 to 7 broad, leathery tubular leaf-sheaths (*kamugu-madal* or *paakku-mattai*, ~80 cm long) per year as new fronds unfurl—providing a tough, waterproof lignocellulosic sheet without cutting a single living branch:\n\n**Traditional & Modern Fabrication:**\n1. **Freshwater Softening & Scraping**: Dry fallen sheaths are scrubbed in running water with coir brushes to remove dust and fungal spores. Soaking for 20 minutes plasticizes the parallel vascular fibre bundles and natural hemicellulose-lignin matrix while the inner waxy cuticle remains completely waterproof.\n2. **Vernacular Pleating & Bamboo-Pin Stitching (*pothi-madal*)**: While damp and pliable, rural artisans fold the ends of the sheath accordion-style and pin them with split bamboo splinters or palmyra fibre to form deep waterproof troughs (*kottan*) for carrying cooked *kuzhambu* rice, wrapping *halwa* and jaggery, or wearing as a rigid sun-and-rain cap (*mattai-thoppi*).\n3. **Thermo-Mechanical Die Pressing ($110^\\circ\\text{C}-130^\\circ\\text{C}$)**: In modern Kongu Nadu and Mettupalayam cottage workshops, dampened sheaths are compressed between heated cast-iron dies, thermally setting the natural lignin into rigid, chemical-free *annadhanam* dining plates and bowls."
    },
    {
        "slug": "artifact-kalipakku-glossy-cured-areca-nuts-cheeval-flakes-and-kottai-pakku-whole-kernels",
        "category": "artifact",
        "file": "artifact-kalipakku-glossy-cured-areca-nuts-cheeval-flakes-and-kottai-pakku-whole-kernels.md",
        "name_en": "Kalipakku Glazed Nut Quarters, Paper-Thin Cheeval Shavings & Kottai-Pakku Whole Kernels",
        "name_ta": "பளபளப்பான களிப்பாக்கு, மெல்லிய சீவல் பாக்கு மற்றும் முழுக் கொட்டைப்பாக்கு வகைப்பாடு",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Commercial and ritual grades of Tamil cured areca nut: double-boiled ruby-glazed Kalipakku (vettu-pakku / ottu-pakku), translucent diamond-shaped Cheeval shavings, sun-dried mature whole Kottai-Pakku presented on marriage trays, and scented Nallapakku.",
        "summary_ta": "தமிழர் தாம்பூலப் பயன்பாட்டில் உள்ள பாக்கு வகைகள்: களிநீரில் காய்ச்சிய பளபளப்பான களிப்பாக்கு, மெல்லிய சீவல், திருமணத் தாம்பூலத்தில் வைக்கப்படும் முழுக் கொட்டைப்பாக்கு மற்றும் வாசனைப் பாக்கு.",
        "sources": [
            "Mettupalayam and Tanjore Areca Trade Grades",
            "Tamil Marriage and Agama Utsava Manuals",
            "Madras Presidency Commercial Products"
        ],
        "content": "# Kalipakku Glazed Quarters, Cheeval Shavings & Kottai-Pakku Kernels\n\nTamil *tambulam* culture distinguishes meticulously between boiled tender grades and sun-cured mature kernels according to ritual occasion and regional palate:\n\n**Commodity & Ritual Grades:**\n- **Kalipakku (*Vettu-Pakku* / *Idi-Pakku*)**: Boiled tender-nut segments coated in glossy dark-red *kali* tannin extract; prized across Coimbatore, Madurai, and Tiruchirappalli for its crisp yet yielding texture.\n- **Cheeval (*Nallapakku* Shavings)**: Tender boiled nuts sliced while still warm with a razor-plane into translucent, curl-edged ruby flakes less than 0.5 mm thick that melt in the mouth alongside *Kumbakonam* or *Sholavandan* betel leaves, cloves, and cardamom.\n- **Kottai-Pakku (Whole Sun-Dried Kernel)**: Fully ripe yellow-orange nuts dried whole in the husk for 40 days and then de-husked; because a whole uncut nut symbolizes unbroken fertility and longevity (*poornathvam*), twin whole *kottai-pakku* nuts are mandatory when placing ceremonial wedding invitations (*lagna-patrikai*) and temple *archanai* trays."
    },
    {
        "slug": "artifact-brass-pakku-vetti-nut-shears-bronze-idiyural-betel-mortars-and-mattai-plates",
        "category": "artifact",
        "file": "artifact-brass-pakku-vetti-nut-shears-bronze-idiyural-betel-mortars-and-mattai-plates.md",
        "name_en": "Ornamental Brass Pakku-Vetti Nut-Shears, Vetrilai-Petti Caskets & Bronze Idiyural Betel-Pounders",
        "name_ta": "பித்தளைப் பாக்குவெட்டிகள், வெற்றிலைப் பெட்டி (செல்லம்) மற்றும் முதியோர் பாக்கு இடியுரல்",
        "era": "Medieval to Modern Era",
        "year_start": 900,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Metalwork and domestic artifacts of the Tamil betel-and-areca ritual: zoomorphic cast-brass pakku-vetti shears (shaped as peacocks, yalis, and celestial couples), compartmented brass tambula boxes (chellam / vetrilai-petti), chunam lime tubes, and tubular bronze betel-mortars (idiyural).",
        "summary_ta": "தாம்பூலப் பயன்பாட்டு உலோகக் கலைப்பொருட்கள்: மயில் மற்றும் யாளி உருவப் பித்தளைப் பாக்குவெட்டிகள், அறைகள் கொண்ட வெற்றிலைப் பெட்டி (செல்லம்), சுண்ணாம்புக் கூடு மற்றும் முதியோருக்கான வெண்கலப் பாக்கு இடியுரல்.",
        "sources": [
            "Kumbakonam and Karaikudi Chettinad Metalwork Collections",
            "Government Museum Chennai Bronze & Brass Catalogues",
            "Domestic Material Culture of Tamil Nadu"
        ],
        "content": "# Brass Pakku-Vetti Shears, Vetrilai-Petti Caskets & Bronze Idiyural\n\nThe daily ceremony of preparing *vetrilai-pakku* inspired some of the finest small-scale lost-wax bronze casting and sheet-brass smithing in Tamil Nadu:\n\n**Metalwork Ensemble:**\n- **Zoomorphic *Pakku-Vetti* Nut-Shears**: Cast in heavy brass or bell-metal around a forged steel cutting blade, the handles and upper arm were sculpted as a preening peacock (*mayil*), a leaping *yazhi*, a parrot (*kili*), or *Rati-Manmatha*, serving also as a protective iron-edged talisman carried by brides and expectant mothers.\n- **Chellam / Vetrilai-Petti (Compartmented Tambula Box)**: Oval or octagonal brass caskets with a ventilated lower tray for moist betel leaves and an upper removable tray divided into compartments for *kalipakku*, *cheeval*, cardamom, cloves, and a chain-linked cylindrical lime container (*chunnambu-koodu*).\n- **Idiyural (Tubular Betel-Pounder for Elders)**: A thick-walled cast bronze cylinder (~12 cm tall) paired with a chisel-tipped iron pestle (*ulakkai*), enabling toothless elders to pound hard *kalipakku*, betel leaf, and lime into a soft, homogeneous paste (*idi-vetrilai*)."
    },
    {
        "slug": "concept-kamugu-intercropped-toppu-microclimate-and-tambula-siddha-digestive-physiology",
        "category": "concept",
        "file": "concept-kamugu-intercropped-toppu-microclimate-and-tambula-siddha-digestive-physiology.md",
        "name_en": "Kamugu-Toppu Multi-Tiered Grove Microclimate & Siddha Tambula Tridosha Digestive Physiology",
        "name_ta": "கமுகந்தோப்புப் பல்லடுக்கு நுண்காலநிலையும் சித்த மருத்துவத் தாம்பூல முத்தோஷச் செரிமான அறிவியலும்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Agronomic ecology of irrigated Tamil areca gardens (kamugu-toppu) intercropped with betel vines, banana, nutmeg, and black pepper to lower ambient temperature by 4–6°C, paired with Siddha Patharthaguna Chinthamani rules on proportioning areca, betel, and lime across the day.",
        "summary_ta": "கமுகந்தோப்பில் வாழை, வெற்றிலைக்கொடி, சாதிக்காய், மிளகு இணைந்த பல்லடுக்குச் சாகுபடி நுண்காலநிலையும், சித்த மருத்துவப் பதார்த்தகுண சிந்தாமணியின்படி பாக்கு-வெற்றிலை-சுண்ணாம்பு விகிதங்களைக் காலத்திற்கேற்ப மாற்றி முத்தோஷம் சமன்படுத்தும் அறிவியலும்.",
        "sources": [
            "Agathiyar Patharthaguna Chinthamani",
            "Siddha Dinacharya (Thamboola Vidhi)",
            "Traditional Multi-Storey Homestead Agroforestry of South India"
        ],
        "content": "# Kamugu-Toppu Microclimate & Siddha Tambula Digestive Physiology\n\nIn Tamil agronomy and Siddha medicine, the *kamugu* palm and its fruit are governed by precise ecological and physiological balances:\n\n**Agro-Ecological & Medical Principles:**\n- **Multi-Storey *Kamugu-Toppu* Microclimate**: Because slender *kamugu* trunks sun-scorch if exposed to hot western winds, Tamil farmers plant dense, channel-irrigated groves (*toppu* / *solai*) bordered by banana (*vaazhai*) and *agathi* shade trees, training black pepper (*milagu*) or betel vines (*vetrilai-kodi*) up the areca trunks and planting shade-loving nutmeg (*jathikkai*) and cocoa/turmeric in the cool, humid understory ($4^\\circ\\text{C}-6^\\circ\\text{C}$ cooler than open fields).\n- **Siddha *Thamboola Vidhi* (Humoral Proportioning)**: According to *Patharthaguna Chinthamani*, the three components balance the three humours (*Mukkutram*):\n  1. **Morning**: A larger proportion of astringent **areca nut (*pakku*)** to stimulate bowel tone and clear sluggish *Pittham*.\n  2. **Midday (Post-Feast)**: A larger measure of **slaked lime (*chunnambu*)** and betel to kindle digestive fire (*Vatham / Anal*).\n  3. **Evening**: Predominantly pungent **betel leaf (*vetrilai*)** with minimal nut to dispel nocturnal phlegm (*Kapham*)."
    },
    {
        "slug": "institution-adaikkai-vaanigar-areca-merchant-guilds-and-temple-adaikkai-amudhu-tenures",
        "category": "institution",
        "file": "institution-adaikkai-vaanigar-areca-merchant-guilds-and-temple-adaikkai-amudhu-tenures.md",
        "name_en": "Adaikkai-Vaanigar Areca Merchant Guilds, Kalipakku Pattarai Curers & Temple Adaikkai-Amudhu Endowments",
        "name_ta": "அடைக்காய் வணிகர் சங்கங்கள், களிப்பாக்குப் பட்டறைகள் மற்றும் கோயில் அடைக்காயமுது மானிய முறை",
        "era": "Chola to Modern Era",
        "year_start": 850,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Institutional organization of the Tamil areca trade: medieval Chola and Pandya inscriptions recording Adaikkai-Vaanigar merchant guilds, tolls on pack-loads of betel and nuts (adaikkai-ayam), temple Adaikkai-Amudhu sacred offerings, and seasonal Kalipakku curing pattarais.",
        "summary_ta": "சோழர் மற்றும் பாண்டியர் கல்வெட்டுகளில் குறிப்பிடப்படும் அடைக்காய் வணிகர் குழுக்கள், பாக்குச் சுங்க வரி (அடைக்காய் ஆயம்), கோயில் பூஜைக்கான 'அடைக்காயமுது' நிவந்தங்கள் மற்றும் களிப்பாக்குக் காய்ச்சும் பட்டறைகள்.",
        "sources": [
            "South Indian Inscriptions (Adaikkai-Amudhu & Vaanigar Grants)",
            "Kongu Nadu and Kaveri Delta Temple Epigraphy",
            "Coimbatore District Commercial History"
        ],
        "content": "# Adaikkai-Vaanigar Guilds, Curing Pattarais & Adaikkai-Amudhu Endowments\n\nBecause every temple ritual, royal court audience, and village life-cycle ceremony required uninterrupted supplies of cured areca nut, its production and taxation were tightly institutionalized:\n\n**Guild, Fiscal & Liturgical Structure:**\n- **Temple *Adaikkai-Amudhu* Endowments**: Hundreds of Chola, Pandya, and Vijayanagara stone inscriptions record dedicated orchard grants (*kamugu-thottam*) and gold endowments funding the daily **Adaikkai-Amudhu** (the liturgical offering of peeled/sliced areca nuts and fresh betel leaves to the presiding deity after every *naivedyam* food offering) and appointing hereditary *Adaikkai-Paruppathiyam* servers.\n- **Adaikkai-Vaanigar & Toll Charters (*Adaikkai-Ayam*)**: Specialized merchant guilds (*Adaikkai-Vaanigar* and *Vetrilai-Vaanigar*) paid fixed market cesses—often one handful of nuts per pack-bullock load (*pothi*)—directly to the local temple treasury to maintain street lamps and water sheds (*thannir-pandal*).\n- **Seasonal *Kalipakku Pattarai* Cooperatives**: During the June–December harvest in the Bhavani and Pollachi valleys, master curers lease orchard blocks (*guthagai*) and set up temporary copper-cauldron boiling sheds (*kalipakku-pattarai*) employing teams of expert women slicers and boiler-masters."
    },
    {
        "slug": "place-mettupalayam-ancient-bhavani-kamugu-areca-grove-and-kalipakku-haven",
        "category": "place",
        "file": "place-mettupalayam-ancient-bhavani-kamugu-areca-grove-and-kalipakku-haven.md",
        "name_en": "Mettupalayam: Ancient Bhavani Foothill Kamugu Areca Groves & Kalipakku Curing Haven",
        "name_ta": "மேட்டுப்பாளையம் - பவானி ஆற்றுப்படுகை கமுகந்தோப்புகள் மற்றும் களிப்பாக்குத் தயாரிப்புத் தளம்",
        "era": "Medieval to Modern Era",
        "year_start": 900,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Foothill river-valley town on the banks of the perennial Bhavani River at the eastern base of the Nilgiri mountains in Coimbatore district (11.3000° N, 76.9400° E), renowned for its cool, mineral-rich irrigated kamugu-toppu areca plantations and traditional Kalipakku / Cheeval curing industry.",
        "summary_ta": "கோயம்புத்தூர் மாவட்டத்தில் நீலகிரி மலை அடிவாரத்தில் பவானி ஆற்றங்கரையில் அமைந்துள்ள மேட்டுப்பாளையம் (11.3000° N, 76.9400° E): குளிர்ந்த கமுகந்தோப்புகள், பளபளப்பான களிப்பாக்கு மற்றும் சீவல் பாக்குத் தயாரிப்பிற்குப் புகழ்பெற்ற வரலாற்றுத் தளம்.",
        "sources": [
            "Coimbatore District Manual (Mettupalayam & Bhavani Valley Areca Gardens)",
            "Madras Agricultural Journal (Mettupalayam Arecanut & Kalipakku)",
            "Kongu Nadu Historical Geography"
        ],
        "content": "# Mettupalayam: Ancient Bhavani Kamugu Grove & Kalipakku Haven\n\nLocated where the perennial snow-and-rain-fed **Bhavani River** emerges from the steep Nilgiri gorge onto the Kongu plain (11.3000° N, 76.9400° E), **Mettupalayam** (alongside Sirumugai and Karamadai) is Tamil Nadu's premier ecological and artisanal heartland for *Areca catechu* cultivation and *Kalipakku* curing:\n\n**Geographic & Craft Significance:**\n- **The Bhavani Foothill Microclimate**: Sheltered from desiccating plains winds by the 2,000-metre Nilgiri escarpment and irrigated year-round by cool, low-salinity Bhavani river channels, Mettupalayam's deep red alluvial-loam soils support thousands of acres of towering *kamugu-toppu* groves intercropped with nutmeg, banana, and black pepper.\n- **Capital of *Kalipakku* & *Cheeval* Curing**: Generations of Mettupalayam curing masters (*pattaraikkarar*) perfected the multi-stage copper-cauldron *kali-neer* boiling and razor-thin *cheeval* slicing craft, leveraging the valley's crisp sunshine and mountain breezes to cure ruby-glazed *Mettupalayam Kalipakku* traded across all of South India."
    }
]

EDGES = [
    [
        "text-sangam-and-silappadikaram-on-kamugu-areca-palms-and-adaikkai-tambulam",
        "describes",
        "concept-kamugu-intercropped-toppu-microclimate-and-tambula-siddha-digestive-physiology",
        "material_culture",
        "Sangam to Post-Sangam Era",
        "Perumpanarruppadai, Pattinappalai, and Silappadikaram celebrate shaded kamugu palm groves and the post-prandial adaikkai-vetrilai-chunnambu tambulam ritual.",
        "Silappadikaram & Perumpanarruppadai"
    ],
    [
        "concept-areca-catechu-condensed-tannin-arecoline-chemistry-and-alkaline-ortho-quinone-reddening",
        "underpins",
        "technology-kalipakku-copper-cauldron-tannin-mother-liquor-boiling-and-ruby-glaze-curing",
        "material_culture",
        "Medieval to Modern Era",
        "Leaching and thermal polymerization of condensed catechin tannins in copper cauldrons govern the mellowing and ruby-glaze coating of Kalipakku.",
        "Arecanut Phytochemistry & Curing Guides"
    ],
    [
        "technology-kalipakku-copper-cauldron-tannin-mother-liquor-boiling-and-ruby-glaze-curing",
        "produces",
        "artifact-kalipakku-glossy-cured-areca-nuts-cheeval-flakes-and-kottai-pakku-whole-kernels",
        "material_culture",
        "Medieval to Modern Era",
        "Boiling tender-ripe areca segments in aged kali-neer mother-liquor and sun-drying produce glossy Kalipakku quarters and paper-thin Cheeval flakes.",
        "Mettupalayam Curing Traditions"
    ],
    [
        "concept-pakku-vetti-second-class-lever-mechanics-and-eccentric-pivot-slicing-geometry",
        "governs",
        "artifact-brass-pakku-vetti-nut-shears-bronze-idiyural-betel-mortars-and-mattai-plates",
        "material_culture",
        "Medieval to Modern Era",
        "Class-2 forward-hinged lever amplification and arcuate draw-shear geometry govern the design of cast-brass pakku-vetti nut-shears.",
        "South Indian Metalwork Catalogues"
    ],
    [
        "artifact-brass-pakku-vetti-nut-shears-bronze-idiyural-betel-mortars-and-mattai-plates",
        "processes",
        "artifact-kalipakku-glossy-cured-areca-nuts-cheeval-flakes-and-kottai-pakku-whole-kernels",
        "material_culture",
        "Medieval to Modern Era",
        "Pakku-vetti lever shears and tubular bronze idiyural mortars slice and pound cured Kalipakku and Kottai-Pakku kernels for tambulam chewing.",
        "Domestic Material Culture"
    ],
    [
        "technology-paakku-mattai-areca-leaf-sheath-retting-and-thermo-mechanical-platter-pressing",
        "fashions",
        "artifact-brass-pakku-vetti-nut-shears-bronze-idiyural-betel-mortars-and-mattai-plates",
        "material_culture",
        "Sangam to Modern Era",
        "Hydro-softening and thermo-mechanical pressing of shed kamugu-madal leaf sheaths fashion waterproof paakku-mattai platters and peasant rain hats.",
        "Kongu Nadu Rural Crafts"
    ],
    [
        "concept-areca-catechu-condensed-tannin-arecoline-chemistry-and-alkaline-ortho-quinone-reddening",
        "explains",
        "concept-kamugu-intercropped-toppu-microclimate-and-tambula-siddha-digestive-physiology",
        "material_culture",
        "Sangam to Modern Era",
        "Alkaline free-basing of arecoline and ortho-quinone formation with slaked lime and betel leaf explain the sialogogue and Tridosha digestive action of tambulam.",
        "Patharthaguna Chinthamani"
    ],
    [
        "institution-adaikkai-vaanigar-areca-merchant-guilds-and-temple-adaikkai-amudhu-tenures",
        "distributes",
        "artifact-kalipakku-glossy-cured-areca-nuts-cheeval-flakes-and-kottai-pakku-whole-kernels",
        "material_culture",
        "Chola to Modern Era",
        "Adaikkai-Vaanigar merchant guilds and Kalipakku pattarai curers grade and distribute cured nuts for bazaars and temple Adaikkai-Amudhu offerings.",
        "South Indian Inscriptions"
    ],
    [
        "institution-adaikkai-vaanigar-areca-merchant-guilds-and-temple-adaikkai-amudhu-tenures",
        "operates_in",
        "place-mettupalayam-ancient-bhavani-kamugu-areca-grove-and-kalipakku-haven",
        "material_culture",
        "Medieval to Modern Era",
        "Areca plantation owners and Kalipakku boiling pattarais operate extensively across the Bhavani river valley around Mettupalayam.",
        "Coimbatore District Manual"
    ],
    [
        "concept-kamugu-intercropped-toppu-microclimate-and-tambula-siddha-digestive-physiology",
        "thrives_in",
        "place-mettupalayam-ancient-bhavani-kamugu-areca-grove-and-kalipakku-haven",
        "material_culture",
        "Medieval to Modern Era",
        "Irrigated multi-storey kamugu-toppu groves intercropped with nutmeg, pepper, and banana flourish in the cool Nilgiri foothill microclimate of Mettupalayam.",
        "Madras Agricultural Journal"
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
