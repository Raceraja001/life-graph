#!/usr/bin/env python3
"""
Harvester: Batch 53 - Ancient Tamil Oil Lamp Luminaires, Capillary Wick Combustion, Pavai-Vilakku Self-Regulating Reservoirs & Karthigai Deepam Pyrotechnics
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
        "slug": "text-sangam-and-bhakti-literature-on-pavai-vilakku-agal-lamps-and-karthigai-deepam",
        "category": "text",
        "file": "text-sangam-and-bhakti-literature-on-pavai-vilakku-agal-lamps-and-karthigai-deepam.md",
        "name_en": "Sangam & Bhakti Literary References to Pavai-Vilakku, Agal Lamps & Karthigai Deepam",
        "name_ta": "சங்க மற்றும் பக்தி இலக்கியங்களில் பாவை விளக்கு, அகல் விளக்கு மற்றும் கார்த்திகைத் தீபக் குறிப்புகள்",
        "era": "Sangam to Bhakti Era",
        "year_start": -300,
        "year_end": 900,
        "thinai": "marutham",
        "summary_en": "Classical Tamil poetic accounts in Nedunalvadai, Mullaippattu, Perumpanarruppadai, Akananuru, Kalavali Narpathu, and Thevaram describing figural bronze Pavai-Vilakku lamps, tall standing nedun-vilakku pillars, rows of terracotta agal lamps lit during the Karthigai pleiades full moon, and hillside beacons.",
        "summary_ta": "நெடுநல்வாடை, முல்லைப்பாட்டு, பெரும்பாணாற்றுப்படை, அகநானூறு, களவழி நாற்பது மற்றும் தேவாரம் ஆகிய நூல்களில் பாவை விளக்கு, நெடுவிளக்கு, அகல் விளக்கு வரிசைகள் மற்றும் கார்த்திகைத் திருநாள் விளக்கீடு பற்றிய இலக்கியச் சான்றுகள்.",
        "sources": [
            "Nedunalvadai",
            "Mullaippattu",
            "Perumpanarruppadai",
            "Akananuru",
            "Thevaram"
        ],
        "content": "# Sangam & Bhakti Literature on Pavai-Vilakku, Agal Lamps & Karthigai Deepam\n\nAcross the Sangam Ten Idyls (*Pattuppattu*), Eight Anthologies (*Ettuthokai*), and Shaiva/Vaishnava Bhakti hymns, oil lamps (**vilakku** / **deepam**) illuminate both royal bedchambers and village thresholds:\n\n**Poetic & Textual Attestations (Cited by Title):**\n- **Nedunalvadai & Mullaippattu (Pavai-Vilakku)**: Both poems describe exquisitely cast bronze female-figurine lamps (**பாவை விளக்கு** / *pavai-vilakku*) crafted by master artisans (*யவனர் / கம்மியர்*), holding cupped oil bowls (*thagalhi*) in their outstretched palms where thick cotton wicks (*பருத்திப் பஞ்சுத் திரி*) soaked in fragrant ghee or oil burn through the rainy *Koothir* night, attended by palace maids who trim the charred wick tip (*சுடர் தூண்டுதல்*).\n- **Perumpanarruppadai & Akananuru (Karthigai Festival of Lights)**: Poems celebrate the ancient pan-Tamil festival of **Karthigai** (*அறுமீன் பயந்த ஆலமர் செல்வன்*), when on the full-moon evening of the Pleiades (*ஆரல் / கார்த்திகை நாள்*) every street, verandah (*thinnai*), and temple is garlanded with rows of glowing terracotta saucers (*agal-vilakku*).\n- **Thevaram**: Sambandar's *Mylapore Padhigam* (*'கார்த்திகை விளக்கீடு காணாதே போதியோ பூம்பாவாய்'*) immortalizes the grand public illumination of *Karthigai Deepam*."
    },
    {
        "slug": "concept-capillary-wick-washburn-transport-and-laminar-diffusion-flame-fuel-chemistry",
        "category": "concept",
        "file": "concept-capillary-wick-washburn-transport-and-laminar-diffusion-flame-fuel-chemistry.md",
        "name_en": "Capillary Wick Washburn Transport & Laminar Diffusion Flame Chemistry of Pancha-Deepa Oils",
        "name_ta": "திரியின் நுண்புழை ஏற்ற இயற்பியலும் (Capillary Action) பஞ்சதீப எண்ணெய்களின் சுடர் எரிப்பு வேதியியலும்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Fluid mechanics and combustion chemistry of Tamil oil lamps: Lucas-Washburn capillary flow through twisted cellulose fibers (cotton, lotus stem, banana pith, calotropis floss) and the viscosity, flash point, and soot-free laminar diffusion flame kinetics of the five canonical fuels (iluppai, gingelly, castor, neem, and cow ghee).",
        "summary_ta": "பஞ்சு, தாமரைத் தண்டு, வாழைத்தண்டு மற்றும் வெள்ளெருக்குத் திரிகளின் நுண்புழை எண்ணெய் ஈர்ப்பு விசையும், இலுப்பை, நல்லெண்ணெய், ஆமணக்கு, வேப்பெண்ணெய் மற்றும் பசு நெய் ஆகிய பஞ்சதீப எண்ணெய்களின் சுடர் ஒளி வேதியியலும்.",
        "sources": [
            "Combustion Physics of Vegetable Oil Laminar Diffusion Flames",
            "Siddha & Agama Specifications of Pancha-Deepa Ennai and Wicks",
            "Ethnobotany of Madhuca longifolia (Iluppai) in Tamil Temple Economy"
        ],
        "content": "# Capillary Wick Washburn Transport & Pancha-Deepa Fuel Chemistry\n\nAn open-reservoir Tamil oil lamp (*agal* or *kuthuvilakku*) operates as a self-sustaining **capillary-fed laminar diffusion burner** where liquid triglycerides must climb the angled wick against gravity before thermal pyrolysis at $300\\text{--}450^\\circ\\text{C}$ vaporizes the fuel:\n\n**1. Lucas-Washburn Capillary Flow in Botanical Wicks:**\n- The volumetric flow rate $Q$ through a porous twisted fiber bundle of effective pore radius $r$, porosity $\\epsilon$, and inclination $\\alpha$ obeys:\n  $$Q \\propto \\frac{\\pi R_w^2 \\epsilon r}{8 \\mu L} (\\frac{2\\gamma \\cos\\theta}{r} - \\rho g L \\sin\\alpha)$$\n- Because vegetable oils have high dynamic viscosity ($\\mu \\approx 35\\text{--}250\\text{ mPa}\\cdot\\text{s}$, $40\\times$ higher than kerosene), the exposed wick height $L$ above the oil meniscus must be kept short ($5\\text{--}10\\text{ mm}$).\n- **Specialty Botanical Wicks**: Beyond raw cotton (*பஞ்சுத் திரி*), Tamil tradition employs dried **lotus-petiole vascular fibers (*தாமரைத் தண்டுத் திரி*)** whose parallel xylem micro-tubules provide low-tortuosity capillary conduits, **banana-pseudostem pith (*வாழைத்தண்டுத் திரி*)**, and silky hollow **white calotropis seed floss (*வெள்ளெருக்குத் திரி*)**.\n\n**2. Pancha-Deepa Ennai (Five-Oil Blend) Combustion:**\n- Blending **cow ghee (*பசு நெய்*)**, **mahua seed oil (*இலுப்பை எண்ணெய்*, *Madhuca longifolia*)**, **sesame oil (*நல்லெண்ணெய்*)**, **castor oil (*ஆமணக்கு எண்ணெய்*)**, and **neem oil (*வேப்பெண்ணெய்*)** balances viscosity and polyunsaturated-to-saturated fatty acid ratios: viscous ricinoleic castor oil slows burn rate for all-night longevity, while saturated stearic/palmitic *iluppai* and ghee produce a bright, low-soot incandescent yellow flame."
    },
    {
        "slug": "concept-hydrostatic-mariotte-siphon-physics-of-self-regulating-pavai-and-thookku-vilakku",
        "category": "concept",
        "file": "concept-hydrostatic-mariotte-siphon-physics-of-self-regulating-pavai-and-thookku-vilakku.md",
        "name_en": "Hydrostatic Mariotte-Bottle Physics in Self-Regulating Pavai-Vilakku & Thookku-Vilakku Lamps",
        "name_ta": "தானியங்கி எண்ணெய் ஊட்டும் பாவை விளக்கு மற்றும் தூக்கு விளக்குகளின் நீர்மநிலையியல் (Hydrostatic) காற்று அழுத்த இயற்பியல்",
        "era": "Early Medieval to Modern Era",
        "year_start": 700,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Pneumatic and hydrostatic pressure-equilibrium engineering in hollow-cast Tamil bronze lamps (Self-Feeding Pavai-Vilakku, Gajalakshmi Vilakku, and Rishabha-Kunjaram Thookku-Vilakku): using an airtight internal reservoir and a submerged basal feed port to maintain a constant oil meniscus at the wick without spilling.",
        "summary_ta": "உள்ளீடற்ற வெண்கலப் பாவை விளக்கு மற்றும் கஜலட்சுமி தூக்கு விளக்குகளின் உடற்பகுதிக்குள் சேமிக்கப்பட்ட எண்ணெய், திரி எரிய எரியக் காற்றுக் குமிழி வழியே தானாகவே தகழிக்குச் சுரக்கும் வளிமண்டல அழுத்தச் சமநிலை இயற்பியல்.",
        "sources": [
            "Fluid Mechanics of Ancient Self-Regulating Oil Lamps",
            "South Indian Bronzes & Folk Metalwork (V.N. Srinivasa Desikan)",
            "Government Museum Chennai Metal Lamps Collection Catalog"
        ],
        "content": "# Hydrostatic Mariotte-Bottle Physics of Self-Regulating Pavai & Thookku-Vilakku\n\nMaster bronze casters (*Kammalar / Sthapathis*) of the Chola, Pandya, and Nayak eras engineered ingenious **automatic constant-level oil lamps**—where a large reserve of oil is concealed inside the hollow torso of a standing maiden (*Pavai-Vilakku*), an elephant (*Gajalakshmi-Vilakku*), or a composite bull-elephant (*Rishabha-Kunjaram Thookku-Vilakku*):\n\n**1. Barometric Seal & Constant-Head Equilibrium:**\n- The figurine's hollow torso acts as an **airtight Mariotte reservoir**. To fill it, the lamp is inverted (or a threaded crown plug on the figurine's head is unscrewed and then hermetically resealed with beeswax/leather washer).\n- At the base of the torso, a narrow feed channel (*உள் துளை*) opens into the shallow exterior wick pan (**thagalhi**) at a precise height $h_0$ below the rim.\n- So long as the oil meniscus in the open wick pan covers the upper lip of this feed port, outside air cannot enter the torso. A partial vacuum ($P_{gas} = P_{atm} - \\rho_{oil} g H$) forms in the headspace above the internal oil column of height $H$, holding the oil suspended against gravity.\n\n**2. Intermittent Bubble-Regulated Replenishment:**\n- As capillary combustion at the wick consumes oil in the pan and lowers the meniscus by $<1\\text{ mm}$ below the orifice lip, surface tension breaks: a single bubble of atmospheric air gulps upward into the torso, displacing an equal volume of oil into the pan until the orifice is submerged again—maintaining a constant capillary lift distance $L$ and steady flame brightness for 12–18 hours."
    },
    {
        "slug": "concept-chokkapanai-palmyra-bonfire-potash-ash-agronomy-and-maavilakku-edible-lamp-symbolism",
        "category": "concept",
        "file": "concept-chokkapanai-palmyra-bonfire-potash-ash-agronomy-and-maavilakku-edible-lamp-symbolism.md",
        "name_en": "Chokkapanai Palmyra Bonfire Potash Agronomy, Phototactic Pest Control & Maavilakku Bio-Calorics",
        "name_ta": "கார்த்திகைச் சொக்கப்பனை சாம்பல் உர அறிவியல், பூச்சி கட்டுப்பாடு மற்றும் மாவிளக்கு ஊட்டச்சத்துத் தத்துவம்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Agro-ecological science of the Karthigai Chokkapanai palmyra bonfire and domestic Maavilakku edible lamp: how burning conical Borassus flabellifer towers during the Samba paddy tillering phase traps nocturnal stem-borer moths and yields soluble potassium carbonate (K2CO3) field ash, alongside the ritual nutrition of rice-jaggery-ghee lamps.",
        "summary_ta": "கார்த்திகை மாதத்தில் எரிக்கப்படும் சொக்கப்பனைச் சுடர் சம்பா நெற்பயிரைத் தாக்கும் பூச்சிகளை அழிப்பதோடு, அதன் பொட்டாஷ் சாம்பல் வயலுக்கு உரமாகும் வேளாண் அறிவியலும், பச்சரிசி-வெல்லம்-நெய் மாவிளக்கின் உணவுத் தத்துவமும்.",
        "sources": [
            "Indigenous Agro-Ecology of Tamil Festivals (Karthigai & Chokkapanai)",
            "Soil Chemistry of Palmyra Frond Ash (Potassium & Silica Availability)",
            "Ritual Food Offerings (Naivedyam) of Tamil Nadu"
        ],
        "content": "# Chokkapanai Palmyra Bonfire Agronomy & Maavilakku Edible Lamp Symbolism\n\nBoth the monumental village bonfire (**Chokkapanai**) of *Karthigai Deepam* and the domestic **Maavilakku** (rice-dough lamp) integrate liturgical symbolism with practical agronomy and nutrition:\n\n**1. Agro-Ecological Science of the *Chokkapanai* Bonfire:**\n- Timed precisely to the full moon of *Karthigai* (mid-November to mid-December), when Northeast monsoon clouds begin clearing and the main **Samba paddy crop** enters its vulnerable boot-leaf and panicle-initiation stage, every temple erected a $15\\text{--}30\\text{ foot}$ conical tower of dried palmyra palm fronds (*பனையோலை*) around a green palmyra or areca trunk.\n- **Phototactic Pest Trapping**: Igniting thousands of *agal* lamps and towering *Chokkapanai* bonfires across the delta at dusk creates intense ultraviolet-yellow thermal plumes that attract and incinerate swarms of nocturnal rice stem-borer moths (*Scirpophaga incertulas*), leaf-folders, and green leafhoppers.\n- **Potash & Silica Field Amendment**: The next morning, farmers collect handfuls of the sterile black-gray palmyra ash (*சொக்கப்பனைச் சாம்பல்*—rich in $12\\text{--}18\\% \\text{ K}_2\\text{O}$ as soluble $\\text{K}_2\\text{CO}_3$, $\\text{SiO}_2$, and trace $\\text{P}_2\\text{O}_5$) and broadcast it across their paddy plots and vegetable beds to stiffen rice culms against fungal blast (*குலைநோய்*).\n\n**2. Maavilakku (Zero-Waste Edible Luminaire):**\n- Pounding soaked raw rice (*பச்சரிசி*) with palm/cane jaggery, cardamom, and edibles into a hemispherical lamp cup fueled with pure cow ghee ensures that once the cotton wick burns down, the caramelized, ghee-soaked dough is shared as high-energy *prasadam*."
    },
    {
        "slug": "technology-kuthuvilakku-modular-lost-wax-and-sand-casting-lathe-threading-and-spout-chasing",
        "category": "technology",
        "file": "technology-kuthuvilakku-modular-lost-wax-and-sand-casting-lathe-threading-and-spout-chasing.md",
        "name_en": "Kuthuvilakku Modular Sand-Casting, Integral Screw-Thread Molding & Oil-Return Spout Chasing",
        "name_ta": "குத்துவிளக்குப் பாகங்கள் வார்ப்பு, மரைத் திருகு இணைப்பு, கடைசல் மெருகேற்றம் மற்றும் எண்ணெய் வடியா முகப்பு நுட்பம்",
        "era": "Early Medieval to Modern Era",
        "year_start": 800,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Foundry and machining engineering of the multi-part Tamil brass/bronze Kuthuvilakku (as practiced in Nachiarkoil and Swamimalai): green-sand and cire-perdue casting of the base, stem, 5-spouted oil pan, and annam finial with integral male-female screw threads (marai), horizontal lathe Skimming, and capillary drip-lip filing.",
        "summary_ta": "நாச்சியார்கோவில் மற்றும் சுவாமிமலையில் குத்துவிளக்கின் பாதம், தண்டு, ஐந்து முகத் தகழி மற்றும் அன்னக் குமிழ் ஆகிய நான்கு பாகங்களை மரைத் திருகுடன் வார்த்து, கடைசலில் இழைத்து, எண்ணெய் வடியாதவாறு முகப்பு அமைக்கும் தொழில்நுட்பம்.",
        "sources": [
            "Nachiarkoil Kuthuvilakku Geographical Indication Technical Dossier",
            "Traditional Brass and Bell-Metal Foundry Practices of Thanjavur District",
            "Metal Casting Technology in South India"
        ],
        "content": "# Kuthuvilakku Modular Casting, Integral Screw-Thread Molding & Spout Chasing\n\nThe tall standing **Kuthuvilakku** ($1.5\\text{ to }6\\text{ feet}$ high) is engineered as a portable, disassemblable four- or five-piece brass/bell-metal column produced by hereditary *Pathar / Kammalar* metal-casters (most famously at **Nachiarkoil** using fine Kaveri riverbed *vandal-mann* molding sand):\n\n**1. Four-Part Modular Casting & Integral Screw Threads (*Marai*):**\n- A complete *Kuthuvilakku* comprises: (a) the weighted lotus base (** கீழ்ப்பாகம் / பாதம்**), (b) the baluster-ringed central shaft (**தண்டு**), (c) the five- or seven-spouted star-shaped oil bowl (**தகழி / அகல்**), and (d) the crown finial (**குமிழ்**—shaped as a *Hamsa/Annam* swan, peacock, *Kalasam*, or *Silுவை*).\n- Rather than cutting threads on a modern machine lathe, artisans cast coarse, heavy-duty square or rounded **male and female helical threads (*மரை*)** directly into the molten brass ($70\\%\\text{ Cu}, 30\\%\\text{ Zn}$) or bell-metal using threaded wax/metal core plugs embedded in the two-part molding box (*அச்சுப் பெட்டி*).\n\n**2. Box-Lathe Skimming (*Kadaisal*) & Anti-Drip Spout Geometry:**\n- Each rough casting is mounted on a horizontal bow- or treadle-lathe and skimmed with high-carbon steel chisels (*சீவுளி*) to mirror concentricity.\n- The five wick spouts (*முகம்*) of the *thagalhi* are hand-filed with a slight **inward-sloping V-groove** and an undercut outer lip so any excess capillary oil drawn up by the wick flows back into the central bowl rather than weeping down the polished pillar."
    },
    {
        "slug": "technology-wheel-thrown-terracotta-agal-pinching-and-giant-karthigai-mahadeepam-cauldron-rigging",
        "category": "technology",
        "file": "technology-wheel-thrown-terracotta-agal-pinching-and-giant-karthigai-mahadeepam-cauldron-rigging.md",
        "name_en": "On-the-Hump Terracotta Agal Throwing, Red-Slip Sealing & Karthigai Mahadeepam Cauldron Rigging",
        "name_ta": "சக்கரத்தில் அகல் விளக்கு வனைதல், செங்காவிப் பூச்சு மற்றும் திருவண்ணாமலை மகா தீபக் கொப்பரை அமைக்கும் தொழில்நுட்பம்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Ceramic and pyrotechnical scale extremes of Tamil lamp craft: rapid 'throwing off the hump' of miniature pinched-spout terracotta agal-vilakku saucers coated with iron-rich red ochre slip (sengavi) to prevent oil seepage, contrasted with rigging the 5.5-foot copper-iron Mahadeepam cauldron with 3,500 kg of ghee and 1,000 m of khadi wick.",
        "summary_ta": "குயவர் சக்கரத்தில் ஒரே மண் உருண்டையிலிருந்து நூற்றுக்கணக்கான அகல் விளக்குகளை வனைந்து செங்காவி பூசிச் சுடும் நுட்பமும், திருவண்ணாமலை உச்சியில் 3,500 கிலோ நெய்யும் 1,000 மீட்டர் காடாத் துணித் திரியும் கொண்ட மகா தீபக் கொப்பரை அமைக்கும் முறையும்.",
        "sources": [
            "Traditional Pottery Techniques of Tamil Nadu (Agal Vilakku Production)",
            "Tiruvannamalai Arunachaleswarar Temple Karthigai Deepam Manual",
            "Pyrotechnics and Large-Scale Beacon Engineering in South Indian Temples"
        ],
        "content": "# Terracotta Agal Throwing & Karthigai Mahadeepam Cauldron Engineering\n\nTamil lamp technology spans from thumb-sized clay saucers thrown at 6 pieces per minute to a colossal mountain-summit beacon visible $30\\text{ km}$ away:\n\n**1. High-Speed 'Off-the-Hump' Terracotta Agal Production:**\n- Ahead of *Karthigai*, *Kuyavar* potters center a $15\\text{ kg}$ cone of levigated tank clay on the flywheel potter's wheel (*திருவை*). Forming only the top $100\\text{ g}$ of the cone with thumb and forefinger, the potter opens a shallow concave cup, pinches a narrow capillary wick spout (**மூக்கு**) between wet index finger and thumb in a single second, slices the *agal* off the spinning hump with a taut cotton thread (*நூல்*), and repeats 50 times before re-centering.\n- **Sengavi Slip Sealing**: Uncoated low-fired earthenware is porous and sweats oil onto the floor. Before clamp-kiln firing at $700^\\circ\\text{C}$, leather-hard *agals* are dipped in a colloidal suspension of iron-rich **red ochre (*செங்காவி*)**, whose sub-micron hematite platelets vitrify into a tight, oil-impermeable surface skin.\n\n**2. Rigging the Tiruvannamalai Mahadeepam Kopparai:**\n- Carried up the steep $2,668\\text{-foot}$ Arunachala peak on shoulders, the **Mahadeepam Kopparai** is a riveted copper-and-wrought-iron truncated conical cauldron ($5.5\\text{ feet}$ high, $5\\text{ feet}$ top diameter).\n- Inside, $1,000\\text{ meters}$ of unbleached, starch-free handspun cotton *khadi* cloth (**காடாத் துணி**) is pleated into a massive central wick column, packed with $20\\text{ kg}$ of pure camphor (*கற்பூரம்*), and saturated with $3,500\\text{ kg}$ of clarified cow ghee (*பசு நெய்*) donated by devotees—sustaining a $15\\text{-foot}$ turbulent diffusion flame for 11 consecutive nights."
    },
    {
        "slug": "artifact-kuthuvilakku-pillars-pavai-vilakku-figurines-and-alankara-thookku-vilakku-lamps",
        "category": "artifact",
        "file": "artifact-kuthuvilakku-pillars-pavai-vilakku-figurines-and-alankara-thookku-vilakku-lamps.md",
        "name_en": "Kuthuvilakku Standing Pillars, Pavai-Vilakku Figurines, Thookku-Vilakku & Ritual Aarathi Lamps",
        "name_ta": "குத்துவிளக்கு, பாவை விளக்கு, தூக்கு விளக்கு, காமாட்சி விளக்கு மற்றும் ஆரத்தித் தீப வகைகளின் தொகுப்பு",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Comprehensive artifact classification of Tamil cast-bronze, bell-metal, and brass oil lamps: five-spouted Kuthuvilakku columns, sculptural Pavai-Vilakku and Gajalakshmi Kamatchi-Vilakku lamps, chain-hung Thookku-Vilakku, multi-tier temple Asthadhatu/tree lamps (Aal-Vilakku), and liturgical Sodasa-Upachara Aarathi deepams.",
        "summary_ta": "தமிழர் உலோக விளக்குகளின் வகைப்பாடு: ஐந்து முகக் குத்துவிளக்கு, பாவை விளக்கு, கஜலட்சுமி காமாட்சி விளக்கு, சங்கிலித் தூக்கு விளக்கு, கிளை விரிந்த ஆல்-விளக்கு மற்றும் கோயில் சோடச உபசார ஆரத்தி விளக்குகள்.",
        "sources": [
            "Bronzes of South India (P.R. Srinivasan)",
            "Nachiarkoil & Thanjavur Metal Lamp Catalogs",
            "Agama Liturgical Implements of Tamil Temples"
        ],
        "content": "# Kuthuvilakku Pillars, Pavai-Vilakku Figurines, Thookku-Vilakku & Aarathi Lamps\n\nTamil metallurgical luminaire design classifies oil lamps by their structural mounting, number of wick spouts (*முகம்*), and iconographic finial:\n\n**Artifact Typology:**\n1. **Kuthuvilakku (Standing Pillar Lamps)**: Featuring a 5-spouted *thagalhi* where the five wicks symbolize the five elements (*பஞ்ச பூதம்*) and five cognitive senses (*ஐம்பொறி*). Crowned with an **Annam** (swan, emblem of discernment), **Mayil** (peacock), or **Kalasam**.\n2. **Pavai-Vilakku (Dipa-Lakshmi / Figural Votive Lamps)**: Cast in solid or hollow bronze as a standing royal donor or *chauri*-bearer holding an oval oil pan before her waist—famous historical examples include Chola royal portrait lamps and Nayak courtier lamps.\n3. **Kamatchi-Vilakku**: The ubiquitous single-spout pedestal lamp featuring an arched repoussé or cast backplate (*திருவாசி*) embossed with **Gajalakshmi** flanked by two elephants pouring water from *kalasams*, passed down as a bride's primary heirloom.\n4. **Thookku-Vilakku & Changili-Vilakku**: Suspended from temple mandapa ceilings by heavy brass link chains cast with protective *Yali*, parrot, or acrobat links and an inline rat-baffle disc (*எலித்தட்டு*) that blocks climbing rodents from drinking the lamp oil.\n5. **Liturgical Aarathi Deepams**: Handled ceremonial lamps including the tiered pyramid **Meru/Kumbha-Deepam**, five-hooded cobra **Naga-Deepam**, **Vrishabha-Deepam**, and **Purusha-Mriga Deepam**."
    },
    {
        "slug": "artifact-terracotta-agal-saucers-soapstone-maavukkal-lamps-maavilakku-and-thiri-tweezers",
        "category": "artifact",
        "file": "artifact-terracotta-agal-saucers-soapstone-maavukkal-lamps-maavilakku-and-thiri-tweezers.md",
        "name_en": "Terracotta Agal Saucers, Soapstone Maavukkal-Vilakku, Edible Maavilakku & Thiri-Thoondu-Kambi",
        "name_ta": "மண் அகல் விளக்குகள், மாவுக்கல் விளக்கு, மாவிளக்கு, தாமரைத் தண்டுத் திரிகள் மற்றும் சுடர் தூண்டும் நெய்க்குச்சி",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Material typology of non-metallic Tamil lamps and wick-tending instruments: excavated Iron Age and historical terracotta agal saucers, multi-spouted Panjami-agal and Adukku-agal tiers, carved steatite lamps (maavukkal-vilakku), sweetened rice-flour maavilakku cups, botanical wicks, and brass wick-prodders (thiri-kambi).",
        "summary_ta": "உலோகம் அல்லாத விளக்குகளும் துணைக் கருவிகளும்: சுடுமண் அகல் விளக்குகள், அடுக்கு அகல், வெப்பம் தாங்கும் மாவுக்கல் விளக்கு, உண்ணக்கூடிய மாவிளக்கு, மூலிகைத் திரிகள் மற்றும் சுடர் தூண்டும் பித்தளை நெய்க்குச்சி.",
        "sources": [
            "Archaeological Terracotta Lamps of Tamil Nadu (Keeladi, Korkai & Arikamedu)",
            "Folk Terracotta and Steatite Crafts of Tamil Nadu",
            "Domestic Ritual Artifacts of South India"
        ],
        "content": "# Terracotta Agal Saucers, Soapstone Lamps, Maavilakku & Wick Accessories\n\nAlongside prestige bronzes, everyday Tamil domestic and votive illumination relies on ceramic, lithic, and botanical artifacts:\n\n**1. Terracotta & Steatite Luminaires:**\n- **Agal-Vilakku (Pinched Terracotta Saucers)**: Continuously attested from Iron Age/Sangam strata at Keeladi, Korkai, Uraiyur, and Arikamedu down to modern *Karthigai* stalls. Variants include the simple single-beak **Sada-Agal**, the five-beaked **Panjami-Agal**, the pedestal-mounted **Kodi-Agal**, and the covered windproof **Koodu-Agal** placed inside exterior wall niches (**மாடக்குழி** — brick alcoves built beside the front door of every traditional Tamil house to shelter the evening street lamp).\n- **Maavukkal-Vilakku (Carved Soapstone Lamps)**: Turned or chiseled from grey-green steatite (*மாவுக்கல்*); because soapstone has low thermal conductivity, the lamp body stays cool during prolonged burning of viscous neem or *iluppai* oil.\n\n**2. Edible Maavilakku & Wick-Tending Tools:**\n- **Maavilakku**: Hand-molded raw-rice and jaggery dough cups offered to *Mariamman* and *Perumal* during *Aadi* and *Purattasi*.\n- **Thiri-Thoondu-Kambi / Nei-Kuchi (Wick-Tending Pin)**: A slender brass or silver rod (often with a tiny spoon at one end for scooping solidified ghee and a pointed tip at the other for advancing the burning wick by $2\\text{ mm}$ without extinguishing the flame)."
    },
    {
        "slug": "institution-chola-nandavilakku-perpetual-lamp-cattle-endowments-and-manradis-shepherd-trusts",
        "category": "institution",
        "file": "institution-chola-nandavilakku-perpetual-lamp-cattle-endowments-and-manradis-shepherd-trusts.md",
        "name_en": "Chola Nandavilakku Perpetual-Lamp Livestock Endowments, Sava-Moova Herds & Manradi Trusts",
        "name_ta": "சோழர் கால நந்தாவிளக்கு அறக்கட்டளைகள், சாவா மூவாப் பேராடு மந்தைகள் மற்றும் மன்றாடி ஆயர் பொறுப்பு முறை",
        "era": "Early Medieval to Late Medieval Era",
        "year_start": 600,
        "year_end": 1600,
        "thinai": "mullai",
        "summary_en": "Epigraphic and pastoral-financial system of ancient Tamil temple illumination: thousands of stone inscriptions recording Nandavilakku (perpetual 24-hour lamp) and Sandhi-Vilakku endowments backed by 'undying, non-aging' herds of 90 ewes or 32 cows entrusted to hereditary Manradi / Kone shepherd guilds to supply one uzhakku of ghee daily.",
        "summary_ta": "பல்லவர், சோழர் மற்றும் பாண்டியர் கல்வெட்டுகளில் பொறிக்கப்பட்ட நந்தாவிளக்கு மற்றும் சந்தி விளக்குக் கொடைகள்: நித்தமும் ஓர் உழக்கு நெய் அளக்க 'சாவா மூவாப் பேராடு 90' அல்லது 'பசு 32' வழங்கி மன்றாடி ஆயர் குழுக்களிடம் ஒப்படைத்த அறக்கட்டளை முறை.",
        "sources": [
            "South Indian Inscriptions (Vol. II: Thanjavur Brihadisvara Temple Shepherd Grants)",
            "Epigraphia Indica: Nandavilakku & Sava-Moova Peradu Legal Formulae",
            "Pastoral Economy and Temple Finance in Medieval Tamil Nadu"
        ],
        "content": "# Chola Nandavilakku Livestock Endowments & Manradi Shepherd Trusts\n\nMore than $60\\%$ of all surviving Pallava, Chola, and Pandya stone inscriptions record endowments for temple illumination—distinguishing between the **Sandhi-Vilakku** (lit at dawn, noon, and dusk) and the sacred **Nandavilakku** (*நந்தா விளக்கு* — the 'unextinguished' perpetual lamp burning 24 hours a day inside the sanctum):\n\n**1. The *Sava-Moova Peradu* Actuarial Endowment Model:**\n- Rather than donating consumable oil that would quickly run out, royal and commoner donors endowed self-reproducing pastoral capital governed by the legal formula **'சாவா மூவாப் பேராடு'** (*sava-moova peradu* — 'immortal, non-senescent livestock').\n- **Standardized Epigraphic Conversion Rates**: To sustain **one perpetual Nandavilakku** (requiring **1 *uzhakku*** $\\approx 336\\text{ mL}$ of clarified butterfat *நெய்* per day, or $122\\text{ liters/year}$), Chola inscriptions specify an endowment of:\n  - **90 ewes (*ஆடு 90*)**, OR\n  - **32 milking cows (*பசு 32*)**, OR\n  - **10 she-buffaloes (*எருமை 10*)**.\n\n**2. Hereditary *Manradi / Kone* Shepherd Custodianship:**\n- The temple treasury (*பண்டாரம்*) entrusted each herd to a named pastoralist (**Manradi** or **Kone**) recorded on the temple wall (as in Rajaraja I's great inscription at Thanjavur listing hundreds of shepherds and their villages). The *Manradi* kept all male calves/lambs, wool, manure, and surplus milk as his profit, on condition that he replaced aging or dead animals from young offspring—keeping the principal herd at exactly 90 ewes or 32 cows forever—and delivered the daily *uzhakku* of pure ghee to the sanctum."
    },
    {
        "slug": "place-tiruvannamalai-ancient-karthigai-mahadeepam-and-agal-lamp-haven",
        "category": "place",
        "file": "place-tiruvannamalai-ancient-karthigai-mahadeepam-and-agal-lamp-haven.md",
        "name_en": "Tiruvannamalai: Ancient Arunachala Hill Karthigai Mahadeepam Beacon & Agal Lamp Haven",
        "name_ta": "திருவண்ணாமலை - அண்ணாமலைக் குன்றின் கார்த்திகை மகா தீபப் பெருஞ்சுடர் மற்றும் அகல் விளக்குத் தளம்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Ancient sacred hill and temple city in Tiruvannamalai district (lat 12.2350, lng 79.0670, thinai: kurinji), where the 2,668-foot charnockite cone of Arunachala is worshiped as a column of cosmic fire (Agni-Stambha) and crowned every Karthigai Pournami dusk with the colossal Mahadeepam ghee-and-camphor beacon.",
        "summary_ta": "திருவண்ணாமலை மாவட்டத்தில் 2,668 அடி உயர அண்ணாமலைக் குன்றின் அடிவாரத்தில் அமைந்துள்ள திருவண்ணாமலை (lat 12.2350, lng 79.0670, குறிஞ்சித் திணை): பஞ்சபூதத் தலங்களில் அக்னித் தலமாகவும், கார்த்திகை பரணி தீபம் மற்றும் மகா தீபப் பெருஞ்சுடரின் தாயகமாகவும் விளங்கும் வரலாற்றுத் தளம்.",
        "sources": [
            "Arunachala Puranam & Saiva Ellappa Navalar Texts",
            "South Indian Inscriptions (Tiruvannamalai Temple Lamp Endowments)",
            "North Arcot / Tiruvannamalai District Gazetteer"
        ],
        "content": "# Tiruvannamalai: Ancient Arunachala Hill Karthigai Mahadeepam & Agal Lamp Haven\n\nSituated at `lat 12.2350, lng 79.0670` around the isolated $2,668\\text{-foot}$ Precambrian charnockite-gneiss peak of **Annamalai / Arunachala** in Tiruvannamalai district, **Tiruvannamalai** is revered across Tamil civilization as the **Agni-Sthalam** (Citadel of Fire) among the five elemental *Pancha-Bhoota* shrines and the epicenter of the **Karthigai Deepam** festival:\n\n**Liturgical & Pyrotechnical Heritage:**\n- **Bharani Deepam & Summit Mahadeepam**: On the pre-dawn morning of *Karthigai Pournami*, five giant terracotta *agal* flames (**Bharani Deepam**) are kindled from a single flame inside the Arunachaleswarar sanctum to represent the fivefold cosmic functions (*Pancha-Kritya*). At exactly $6:00\\text{ PM}$—as the full moon rises in conjunction with the *Krittika* (Pleiades) star cluster and the golden flagstaff torch is raised—hereditary **Parvatharajakula** fishermen-climbers ignite the $3,500\\text{ kg}$ ghee-and-camphor **Mahadeepam cauldron** atop the mountain summit.\n- **Agal & Iluppai-Thoppu Economy**: Surrounding villages across the Cheyyar and Pennaiyar watershed maintain centuries-old *iluppai* (*Madhuca longifolia*) groves for lamp oil and dozens of *Kuyavar* pottery kilns that fire millions of red-slipped *agal-vilakku* saucers carried home by pilgrims circumambulating the $14\\text{ km}$ **Girivalam** path."
    }
]

EDGES = [
    [
        "text-sangam-and-bhakti-literature-on-pavai-vilakku-agal-lamps-and-karthigai-deepam",
        "describes",
        "artifact-kuthuvilakku-pillars-pavai-vilakku-figurines-and-alankara-thookku-vilakku-lamps",
        "material_culture",
        "Sangam to Bhakti Era",
        "Nedunalvadai and Mullaippattu celebrate cast-bronze Pavai-Vilakku figurine lamps and tall standing nedun-vilakku columns.",
        "Nedunalvadai & Mullaippattu"
    ],
    [
        "text-sangam-and-bhakti-literature-on-pavai-vilakku-agal-lamps-and-karthigai-deepam",
        "celebrates",
        "place-tiruvannamalai-ancient-karthigai-mahadeepam-and-agal-lamp-haven",
        "material_culture",
        "Sangam to Modern Era",
        "Sangam poems on the Pleiades Karthigai illumination and Bhakti hymns culminate in the summit Mahadeepam beacon at Tiruvannamalai.",
        "Akananuru & Thevaram"
    ],
    [
        "concept-capillary-wick-washburn-transport-and-laminar-diffusion-flame-fuel-chemistry",
        "governs",
        "artifact-terracotta-agal-saucers-soapstone-maavukkal-lamps-maavilakku-and-thiri-tweezers",
        "material_culture",
        "Sangam to Modern Era",
        "Lucas-Washburn capillary rise and laminar flame kinetics govern the pairing of Pancha-Deepa oils with cotton, lotus-stem, and calotropis wicks.",
        "Combustion Physics Studies"
    ],
    [
        "concept-hydrostatic-mariotte-siphon-physics-of-self-regulating-pavai-and-thookku-vilakku",
        "underpins",
        "artifact-kuthuvilakku-pillars-pavai-vilakku-figurines-and-alankara-thookku-vilakku-lamps",
        "material_culture",
        "Early Medieval to Modern Era",
        "Barometric Mariotte-bottle pressure equilibrium regulates automatic oil replenishment in hollow-cast Pavai-Vilakku and Thookku-Vilakku lamps.",
        "Chennai Museum Lamp Catalog"
    ],
    [
        "concept-chokkapanai-palmyra-bonfire-potash-ash-agronomy-and-maavilakku-edible-lamp-symbolism",
        "explains",
        "artifact-terracotta-agal-saucers-soapstone-maavukkal-lamps-maavilakku-and-thiri-tweezers",
        "material_culture",
        "Sangam to Modern Era",
        "Karthigai Chokkapanai bonfires trap paddy pests and yield potash ash while Maavilakku rice-jaggery lamps serve as zero-waste edible offerings.",
        "Agro-Ecology Studies"
    ],
    [
        "technology-kuthuvilakku-modular-lost-wax-and-sand-casting-lathe-threading-and-spout-chasing",
        "fabricates",
        "artifact-kuthuvilakku-pillars-pavai-vilakku-figurines-and-alankara-thookku-vilakku-lamps",
        "material_culture",
        "Early Medieval to Modern Era",
        "Four-part sand casting with integral marai screw threads, lathe skimming, and anti-drip spout filing produce the five-wick Kuthuvilakku.",
        "Nachiarkoil GI Dossier"
    ],
    [
        "technology-wheel-thrown-terracotta-agal-pinching-and-giant-karthigai-mahadeepam-cauldron-rigging",
        "produces",
        "artifact-terracotta-agal-saucers-soapstone-maavukkal-lamps-maavilakku-and-thiri-tweezers",
        "material_culture",
        "Sangam to Modern Era",
        "Rapid off-the-hump wheel throwing and red-ochre sengavi slip coating produce leak-proof terracotta agal-vilakku saucers.",
        "Pottery Crafts of Tamil Nadu"
    ],
    [
        "technology-wheel-thrown-terracotta-agal-pinching-and-giant-karthigai-mahadeepam-cauldron-rigging",
        "powers",
        "place-tiruvannamalai-ancient-karthigai-mahadeepam-and-agal-lamp-haven",
        "material_culture",
        "Early Medieval to Modern Era",
        "Rigging the 5.5-foot copper-iron cauldron with 3,500 kg of ghee and 1,000 meters of khadi wick powers the 11-day Arunachala summit beacon.",
        "Tiruvannamalai Temple Manual"
    ],
    [
        "institution-chola-nandavilakku-perpetual-lamp-cattle-endowments-and-manradis-shepherd-trusts",
        "fuels",
        "artifact-kuthuvilakku-pillars-pavai-vilakku-figurines-and-alankara-thookku-vilakku-lamps",
        "material_culture",
        "Early Medieval to Late Medieval Era",
        "Sava-moova endowments of 90 ewes or 32 cows managed by Manradi shepherds supplied the daily uzhakku of ghee for sanctum Nandavilakku lamps.",
        "South Indian Inscriptions"
    ],
    [
        "institution-chola-nandavilakku-perpetual-lamp-cattle-endowments-and-manradis-shepherd-trusts",
        "endows",
        "place-tiruvannamalai-ancient-karthigai-mahadeepam-and-agal-lamp-haven",
        "material_culture",
        "Early Medieval to Modern Era",
        "Hundreds of Chola, Hoysala, and Vijayanagara stone inscriptions on the walls of Tiruvannamalai temple record perpetual cattle and ghee lamp grants.",
        "South Indian Inscriptions Vol. VIII"
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
