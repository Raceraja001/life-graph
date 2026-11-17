#!/usr/bin/env python3
"""
Harvester: Batch 54 - Ancient Tamil Neem Agroforestry, Veppennai Sekku Cold-Pressing, Azadirachtin Antifeedant Phytochemistry & Mariamman Prophylactic Ecology
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
        "slug": "technology-veppam-seed-depulping-sun-drying-and-vagai-wood-sekku-cold-pressing",
        "category": "technology",
        "file": "technology-veppam-seed-depulping-sun-drying-and-vagai-wood-sekku-cold-pressing.md",
        "name_en": "Veppam Seed Depulping, Sun-Drying & Vagai Wood Sekku Cold-Pressing",
        "name_ta": "வேப்பங்கொட்டை சதைநீக்கம், வெயிலில் உலர்த்தல் மற்றும் வாகை மரச் செக்குக் குளிர்பிழிதல்",
        "era": "Classical to Contemporary Tamil Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "marutham",
        "summary_en": "Traditional post-harvest processing of neem (Azadirachta indica) seeds across Tamilakam: collection of fallen yellow drupes in Vaikasi-Aani, anaerobic water-soaking depulping, open-air drying to below 8 percent moisture, and slow bullock-drawn cold pressing in dense Albizia lebbeck (vagai) timber mortar-and-pestle sekku mills below 45°C.",
        "summary_ta": "தமிழகத்தில் பாரம்பரிய வேப்பங்கொட்டை அறுவடைக்குப் பிந்தைய பதப்படுத்துதல்: வைகாசி-ஆனி மாதங்களில் உதிர்ந்த பழங்களைச் சேகரித்தல், நீரில் ஊறவைத்துச் சதைநீக்குதல், 8% ஈரப்பதத்திற்குக் கீழ் உலர்த்துதல் மற்றும் வாகை மரச் செக்கில் 45°C-க்கு மிகாமல் எருதுகொண்டு குளிர்பிழிதல் முறை.",
        "sources": [
            "Tamil Traditional Oil Pressing & Sekku Manuals",
            "Azadirachta indica Post-Harvest Technology Studies",
            "Siddha Materia Medica (Thylavargam)"
        ],
        "content": "# Veppam Seed Depulping, Sun-Drying & Vagai Wood Sekku Cold-Pressing\n\nThe extraction of unrefined, bioactive-rich neem oil (*veppennai*) from the drupes of the sacred margosa tree (*Azadirachta indica*, Tamil: *வேம்பு / வேப்பமரம்*) forms an ancient agro-industrial technology perfected across Tamilakam:\n\n**1. Phenology & Drupe Harvesting:**\nIn the dry pre-monsoon heat of *Vaikasi* and *Aani* (May–July), mature neem trees shed hundreds of kilograms of yellow, fleshy, single-seeded oval drupes (*veppam-pazham*). Gathering is conducted on cleaned ground beneath the canopy at dawn to prevent microbial decomposition and early fermentation.\n\n**2. Wet Depulping & Fermentation (*Sathai Neekkam*):**\nThe gathered fruits undergo immediate processing to remove the sweetish-bitter mucilaginous sarcocarp (mesocarp). The fruits are steeped in masonry cisterns or earthenware vats filled with fresh water for 24 to 48 hours to soften the pulp. The mass is then trampled underfoot on coarse coir mats (*pirambu/kayiru paai*) or scrubbed in wicker baskets (*panai-koodai*) with sharp river sand (*aattumanal*). This abrasive washing shears away the moist pulp, leaving behind cleanly decorticated, cream-colored endocarp-enclosed seeds (*veppam-kottai*). Complete pulp removal is critical to inhibit infestation by *Aspergillus flavus* and prevent aflatoxin contamination.\n\n**3. Solar Dehydration (*Kalam Ularthuthal*):**\nCleaned seeds are spread across tamped, cow-dung-washed open-air threshing floors (*kalam*) in thin 3–5 cm layers under direct tropical sunlight for 5 to 7 days. The seeds are raked twice daily using wooden rakes (*marak-kambambu*) until internal kernel moisture drops strictly below $8\\%$. Maintaining this threshold arrests endogenous lipase enzyme activation, preserving triacylglycerol integrity and preventing hydrolytic rancidity during subsequent storage.\n\n**4. *Vagai* (Albizia lebbeck) *Sekku* Cold Pressing:**\nThe dried kernels are transferred to the traditional bullock-drawn rotary wooden mortar and pestle press (*mara-sekku*):\n- **Mortar (*Ural*)**: Sculpted from a single monumental trunk of black siris (*Albizia lebbeck*, Tamil: *வாகை மரம்*). *Vagai* heartwood possess high density, interlaced grain, and high mechanical shock absorption, remaining cool under immense compressive stresses.\n- **Pestle (*Ulakkai*)**: Carved from heavy *vagai* or seasoned tamarind (*puliyamaram*) heartwood, weighted by a cantilever beam tethered to a pair of Kangayam draught bullocks trotting in concentric circles.\n- **Low-Temperature Thermodynamics**: Operating at 4 to 6 revolutions per minute, friction shear inside the *vagai* mortar gently fractures kernel cell walls without allowing temperatures to exceed $40^\\circ\\text{C}-45^\\circ\\text{C}$. This low-temperature threshold preserves thermal-sensitive tetranortriterpenoids, including azadirachtin A, salannin, and nimbin, which degrade rapidly above $55^\\circ\\text{C}$.\n\n**5. Clarification & Separation:**\nThe thick, emerald-brown bitter oil flows through a base spigot into glazed terracotta settling vessels (*mankaala jaadi*), where particulate suspended matter settles naturally over 72 hours, yielding pure unrefined *veppennai* alongside dense compressed cake slabs (*veppam pinnakku*)."
    },
    {
        "slug": "technology-veppilai-herbal-fumigation-crude-water-extract-spray-and-grain-protection",
        "category": "technology",
        "file": "technology-veppilai-herbal-fumigation-crude-water-extract-spray-and-grain-protection.md",
        "name_en": "Veppilai Herbal Smoke Fumigation, Crude Aqueous Foliar Extract Spray & Granary Pest Defense",
        "name_ta": "வேப்பிலை மூலிகைப் புகையூட்டம், கசப்பு இலைச்சாறு தெளிப்பு மற்றும் தானியக் களஞ்சிய பூச்சித் தடுப்பு",
        "era": "Sangam to Contemporary Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "marutham",
        "summary_en": "Indigenous botanical pest management technologies in Tamil agriculture: smoldering neem foliage fumigation (veppilai-pugai) against winged insect vectors, 5 percent crude aqueous neem kernel suspension (NSKE) spray against foliage-feeding caterpillars, and layering dried leaves in earthen granaries (kuthir) against coleopteran storage pests.",
        "summary_ta": "தமிழக உழவியல் மரபின் தாவரப் பூச்சி மேலாண்மைத் தொழில்நுட்பங்கள்: கொசு மற்றும் பறக்கும் பூச்சிகளை விரட்டும் வேப்பிலைப் புகையூட்டம், கம்பளிப்புழுக்களுக்கு எதிரான 5% வேப்பங்கொட்டைக் கரைசல் தெளிப்பு மற்றும் தானியக் குதிர்களில் உலர்வேப்பிலை அடுக்குமுறை தானியப் பாதுகாப்பு.",
        "sources": [
            "Uzhavu Nool & Indigenous Agricultural Practices of Tamil Nadu",
            "Journal of Economic Entomology (Neem Formulations)",
            "Siddha Herbal Toxicology & Pest Management"
        ],
        "content": "# Veppilai Herbal Smoke Fumigation, Crude Aqueous Foliar Extract Spray & Granary Pest Defense\n\nThe agronomic defense systems of ancient and traditional Tamil cultivators relied on the multiphasic application of fresh, smoldered, and water-extracted *Azadirachta indica* biomass:\n\n**1. Herbal Smoke Fumigation (*Veppilai-Pugai*):**\nAt twilight during the humid post-monsoon months, farmers and pastoralists gather semi-wilted neem foliage, dry coconut husks (*thengai-mattai*), and dried cow-dung cakes (*varatti*) into terracotta brazier pots (*pugai-chatti*). When ignited into a slow, smoldering ember, the dense smoke volatilizes low-molecular-weight sulfur compounds, bicyclic monoterpenes, and phytol derivatives. Carried through cattle pens (*maattu-thozhuvam*) and homesteads, the aromatic aerosol disorients and repels haematophagous dipteran vectors (*Culex quinquefasciatus*, *Anopheles stephensi*, and stable flies *Stomoxys calcitrans*), eliminating biting stress without toxic chemical residues.\n\n**2. Crude Aqueous Foliar & Kernel Extract Spray (NSKE 5% Formulation):**\nTo defend standing crops of wet paddy (*nell*), millets (*chirudhaaniyangal*), and cotton (*paruthi*) against defoliating lepidopteran larvae (such as the tobacco cutworm *Spodoptera litura* and yellow stem borer *Scirpophaga incertulas*), traditional farmers prepare a crude aqueous neem kernel extract (*veppam-kottai-karaisal*):\n- **Preparation**: Dried neem seeds are pounded into a coarse grit, enclosed in a loosely woven unbleached cotton bag (*khadi thuni*), and suspended in a barrel of clean water (50 g pounded seed per liter of water, yielding a $5\\%$ crude suspension) for 12 to 16 hours.\n- **Extraction Dynamics**: Water-soluble limonoids, particularly azadirachtin, deacetylazadirachtinol, and salannin, leach into the aqueous solvent.\n- **Surfactant & Synergy**: Traditional farmers add a small quantity of crushed soapnut (*poovanthikottai*) or fresh cow urine (*komiyam*) as an organic surfactant and wetting agent.\n- **Application**: The filtered bitter extract is sprayed over the vegetative canopy using brass or wicker spray brooms. Upon contact, feeding caterpillars experience immediate gustatory deterrence followed by irreversible ecdysis failure.\n\n**3. Granary Storage Pest Protection (*Kuthir Thaania Paadhukaappu*):**\nFor post-harvest grain preservation in underground silos (*pathayam*) and cylindrical bamboo-and-mud granaries (*kuthir*), a sophisticated multi-layering method is practiced:\n- **Canopy Shade-Drying**: Fresh mature neem leaves are shade-dried on palm-leaf mats (*panai-paai*) to preserve their volatile terpenes while expelling cellular water.\n- **Layering Stratigraphy**: A foundational 5–10 cm bed of crisp dried neem leaves is placed at the base of the *kuthir*, followed by a 30 cm layer of thoroughly sun-dried paddy or pulses, repeated sequentially until full.\n- **Bio-Repellency**: The constant evaporation of volatile terpenoids and repellent limonoid vapors inside the sealed dark granary suppresses the oviposition, larval hatching, and feeding boredam of major storage beetles, notably the rice weevil (*Sitophilus oryzae*), lesser grain borer (*Rhyzopertha dominica*), and pulse beetle (*Callosobruchus chinensis*), preserving viability for up to two full seasons."
    },
    {
        "slug": "artifact-cold-pressed-bitter-veppennai-seed-cake-fertilizer-and-earthen-storage-jars",
        "category": "artifact",
        "file": "artifact-cold-pressed-bitter-veppennai-seed-cake-fertilizer-and-earthen-storage-jars.md",
        "name_en": "Cold-Pressed Veppennai (Neem Oil), Veppam Pinnakku (Seed Cake) & Glazed Earthen Storage Jars",
        "name_ta": "மரச்செக்குக் கசப்பு வேப்பெண்ணெய், வேப்பம் பிண்ணாக்கு உரம் மற்றும் மண்பாண்டச் சேமிப்புக் கலயங்கள்",
        "era": "Classical to Modern Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "marutham",
        "summary_en": "Physical artifacts of traditional neem processing: unrefined greenish-brown bitter veppennai oil containing volatile organic sulfur compounds and triterpenes, nutrient-rich de-oiled veppam pinnakku seed cake functioning as an organic fertilizer and nitrification inhibitor, and lead-free glazed earthenware jars (marakkaal / jaadi) for lipid stabilization.",
        "summary_ta": "மரச்செக்கில் பிழியப்படும் கந்தக நெடியுடைய பச்சை-பழுப்பு நிற வேப்பெண்ணெய், நைட்ரஜனை மெல்ல வெளியிடும் யூரியா தடுப்பானாகச் செயல்படும் வேப்பம் பிண்ணாக்கு உரம் மற்றும் எண்ணெயின் தரத்தை நிலைநிறுத்தும் பழங்கால மண்பாண்டச் சேமிப்புக் கலயங்கள்.",
        "sources": [
            "South Indian Agricultural By-products & Soil Science Records",
            "Siddha Materia Medica (Thailam Archives)",
            "Tamil Ethnobotany & Material Culture Collections"
        ],
        "content": "# Cold-Pressed Veppennai (Neem Oil), Veppam Pinnakku (Seed Cake) & Glazed Earthen Storage Jars\n\nThe tangible outputs of the village *sekku* processing line consist of two indispensable agricultural-medicinal commodities and their specialized preserving containers:\n\n**1. Unrefined Cold-Pressed *Veppennai* (Neem Oil):**\n- **Physical Characteristics**: A dense, dark greenish-brown to deep amber liquid possessing a pronounced alliaceous-garlicky odor and an overpowering persistent bitterness (*kaippu*). It exhibits a specific gravity of 0.908–0.934 at $30^\\circ\\text{C}$ and a refractive index of 1.470–1.472.\n- **Lipid & Triterpene Composition**: Composed predominantly of triglycerides rich in oleic acid ($50\\%-60\\%$), stearic acid ($14\\%-19\\%$), palmitic acid ($13\\%-15\\%$), and linoleic acid ($8\\%-16\\%$). Held in colloidal solution within this lipid matrix are potent biological limonoids: nimbin, nimbidin, salannin, gedunin, and volatile organic disulfides (notably di-n-propyl disulfide).\n- **Functional Use**: Primary non-edible illumination oil for temple oil-lamps, veterinary wound dressing for bullocks (*maattu-pun*), and external unguent in Siddha pharmacopeia.\n\n**2. *Veppam Pinnakku* (Neem Seed Cake):**\n- **Physical Form**: Compressed, rigid hexagonal or trapezoidal fibrous cakes expelled from the *sekku* mortar after mechanical compression.\n- **Nutritional Profile**: Contains $5.2\\%-5.6\\%$ organic nitrogen ($N$), $1.0\\%-1.3\\%$ phosphorus pentoxide ($P_2O_5$), and $1.4\\%-1.6\\%$ potassium oxide ($K_2O$), alongside $5\\%-8\\%$ residual bitter lipids.\n- **Nitrification Inhibition**: Applied to flooded paddy soils (*marutham vayal*), *veppam pinnakku* functions as a potent natural nitrification inhibitor. The residual triterpenes suppress the soil bacterium *Nitrosomonas*, retarding the conversion of ammonium ions ($NH_4^+$) into mobile nitrate ($NO_3^-$). This dramatically reduces nitrogen leaching into groundwater and gaseous denitrification losses, optimizing nutrient availability for deep rice roots. Concurrently, it releases volatile nematicidal aldehydes that control soil nematodes (*Meloidogyne incognita*).\n\n**3. Glazed Earthen Storage Jars (*Mankaala Jaadi / Bharani*):**\n- **Material Construction**: High-fire terracotta vessels turned on potter's wheels from river silt and fine red clay (*sengal-man*), coated internally with lead-free natural feldspathic/clay slips and wood-ash glaze.\n- **Preservation Functionality**: Azadirachtin and other triterpene limonoids undergo rapid photolytic degradation when exposed to ultraviolet radiation in clear glass or translucent plastics. The thick, opaque walls of the earthenware *jaadi* maintain a stable internal temperature ($<28^\\circ\\text{C}$) and complete darkness, preventing photo-isomerization and maintaining therapeutic and pesticidal efficacy across multiple agricultural seasons."
    },
    {
        "slug": "artifact-veppilai-leafy-garlands-ritual-foliage-fans-and-chewed-margosa-toothsticks",
        "category": "artifact",
        "file": "artifact-veppilai-leafy-garlands-ritual-foliage-fans-and-chewed-margosa-toothsticks.md",
        "name_en": "Veppilai Foliage Garlands, Ritual Margosa Fans, Pandyan Veppam Flower Chaplets & Chewed Toothsticks",
        "name_ta": "வேப்பிலை மாலைகள், விசிறிகள், பாண்டியர் வேப்பம்பூக் கண்ணி மற்றும் வேப்பங்குச்சி பல் துலக்கு தடி",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2025,
        "thinai": "marutham",
        "summary_en": "Somatic, martial, and ceremonial artifacts crafted from Azadirachta indica foliage and wood: Pandyan dynastic neem blossom battle chaplets (veppam-pum-kanni), ritual veppilai foliage garlands and soothing fans (veppilai-visiri) waved over fever patients, and green margosa toothsticks (veppam-kuchi) chewed into fibrous oral cleansing brushes.",
        "summary_ta": "வேப்ப மரத்தின் இலை, பூ, குச்சிகளிலிருந்து உருவான பயன்பாட்டுப் பொருட்கள்: பாண்டிய மன்னர்களின் அடையாளமான வேப்பம்பூக் கண்ணி, மாரியம்மன் வழிபாட்டு வேப்பிலை மாலைகள் மற்றும் நோய்த்தணிப்பு விசிறிகள், மற்றும் வாய் சுகாதாரத்தை உறுதிசெய்யும் வேப்பங்குச்சி பல் துலக்கு தடி.",
        "sources": [
            "Purananuru & Tolkappiyam Porulatikaram",
            "Tamil Folk Ritual Implements & Ethnomedicine",
            "Oral Hygiene in Indian Systems of Medicine"
        ],
        "content": "# Veppilai Foliage Garlands, Ritual Margosa Fans, Pandyan Veppam Flower Chaplets & Chewed Toothsticks\n\nFrom royal regalia in Sangam warfare to village domestic hygiene, tangible artifacts shaped from fresh neem vegetative tissues occupy an exalted station in Tamil material culture:\n\n**1. Pandyan Dynastic Battle Chaplet (*Veppam-Pum-Kanni*):**\n- **Royal Signet**: In classical Sangam poetics, each of the three crowned monarchies (*Muventhar*) bore a botanical emblem: the Cheras wore palmyra (*panampoo*), the Cholas wore mountain ebony (*aathipoo*), and the Pandyas wore the fragrant white blossom of the margosa tree (*veppampoo*).\n- **Structure**: Woven as a tight circular headband (*kanni*) or neck garland (*thaar*) incorporating delicate white cruciform neem blossoms alternating with tender serrated leaflets. Worn by the Pandyan monarch and his commanders into the frontline of battle, the chaplet projected righteous coolness, royal endurance, and fearlessness.\n\n**2. Ritual Foliar Fans (*Veppilai-Visiri*) & Therapeutic Garlands:**\n- **Fabrication**: Stems bearing fresh, bright green, imparipinnate neem leaflets are bound radially around a split bamboo handle using shredded plantain bark fibers (*vazhai-naar*).\n- **Folk Epidemiological Practice**: In village shrines dedicated to Goddess Mariamman and domestic sickrooms during outbreaks of eruptive fevers (*ammai*, smallpox, varicella), the ritual practitioner (*poosari*) or household elder waves the *veppilai-visiri* in rhythmic strokes over the patient's prone body. This action serves a threefold clinical-material purpose:\n  - Generates gentle evaporative air currents that relieve burning febrile cutaneous discomfort;\n  - Dispenses aerosolized antimicrobial volatile terpenoids over the patient's lesions;\n  - Dislodges biting flies without touching or tearing delicate pustular blisters.\n- **Threshold Garlands (*Veppilai-Thoranangal*)**: Dense garlands of fresh neem foliage suspended across door lintels during village festivals, purifying indoor air and providing visual notification of sanctified domestic space.\n\n**3. Masticated Margosa Toothsticks (*Veppam-Kuchi*):**\n- **Artifact Specifications**: Straight, pencil-thick twigs ($15-20\\text{ cm}$ in length, $8-12\\text{ mm}$ in diameter) freshly pruned from the mature tree before sunrise.\n- **Mechanical & Chemical Action**: The user chews the distal 1.5 cm of the twig with molars until the fibrous xylem separates into an array of soft, bristly cellulose fibers, creating a custom single-use toothbrush. Chewing liberates bitter sap containing nimbidin, margosine, tannins, and organic fluorides directly into the oral cavity. These compounds lyse cariogenic bacteria (*Streptococcus mutans* and *Porphyromonas gingivalis*), prevent plaque biofilm formation, stimulate salivary flow, and tighten periodontal gingival tissue, fulfilling the ancient proverb: *\"ஆலும் வேலும் பல்லுக்குறுதி\"* (Banyan and Neem bestow strength to the teeth)."
    },
    {
        "slug": "concept-azadirachtin-tetranortriterpenoid-limonoid-eclosion-inhibition-and-antifeedant-action",
        "category": "concept",
        "file": "concept-azadirachtin-tetranortriterpenoid-limonoid-eclosion-inhibition-and-antifeedant-action.md",
        "name_en": "Azadirachtin B, Seco-Tetranortriterpenoid Limonoids, Ecdysone Eclosion Inhibition & Antifeedant Action",
        "name_ta": "அசாடிராக்டின் செகோ-டெட்ராநார்ட்ரைடெர்பினாய்டுகள், எக்டிசோன் முதிர்ச்சித் தடுப்பு மற்றும் பூச்சி உண்ணாமைக் கொள்கை",
        "era": "Contemporary Phytochemical Era",
        "year_start": 1960,
        "year_end": 2025,
        "thinai": "marutham",
        "summary_en": "The phytochemical mechanism of neem seed limonoids: Azadirachtin (C35H44O16) as a seco-tetranortriterpenoid that disrupts insect endocrine systems by antagonizing ecdysone release from the prothoracic gland, inhibiting eclosion and pupation, while firing deterrent gustatory chemoreceptors to induce complete antifeedant starvation.",
        "summary_ta": "வேப்பங்கொட்டையின் மூலக்கூறு உயிரியல்: அசாடிராக்டின் (C35H44O16) எனும் செகோ-டெட்ராநார்ட்ரைடெர்பினாய்டு பூச்சிகளின் எக்டிசோன் ஹார்மோனைத் தடுத்துத் தோலுரித்தல் மற்றும் கூட்டுப்புழு உருவாக்கத்தை முடக்குவதுடன், சுவை நரம்புகளில் கசப்புத் தூண்டலை ஏற்படுத்தி உண்ணாமல் பட்டினி கிடந்து இறக்கச் செய்யும் உயிரியல் தத்துவம்.",
        "sources": [
            "Phytochemistry & Limonoid Structure of Azadirachta indica",
            "Annual Review of Entomology (Modes of Action of Neem Limonoids)",
            "Butterworth & Morgan (Azadirachtin Isolation Studies)"
        ],
        "content": "# Azadirachtin B, Seco-Tetranortriterpenoid Limonoids, Ecdysone Eclosion Inhibition & Antifeedant Action\n\nThe biochemical foundation of *Azadirachta indica*'s universal entomological defense resides in a complex family of secondary metabolites known as limonoids or tetranortriterpenoids:\n\n**1. Molecular Architecture of Azadirachtin:**\n- **Formula & Core Scaffold**: Azadirachtin A ($C_{35}H_{44}O_{16}$, molar mass 720.71 g/mol) is a highly oxidized C-seco-tetranortriterpenoid possessing a decalin system linked to a dihydrofuran-furan fragment, an enol ether, an allylic epoxide, and multiple ester moieties.\n- **Related Congeners**: Neem seeds concurrently express Azadirachtin B, D, H, and I, along with salannin, nimbin, and deacetylgedunin, creating a multifaceted defensive cocktail that prevents insect pests from developing single-site metabolic resistance.\n\n**2. Endocrine Disruption & Ecdysteroid Inhibition:**\nUnlike synthetic neurotoxic pesticides (organophosphates, synthetic pyrethroids), azadirachtin acts as an insect growth regulator (IGR) via the neuroendocrine system:\n- **Disruption of Corpus Cardiacum**: Azadirachtin binds with high affinity to neurosecretory cells in the brain, inhibiting the synthesis and release of prothoracicotropic hormone (PTTH).\n- **Suppression of Ecdysone Titre**: In the absence of PTTH, the prothoracic glands fail to synthesize ecdysone, causing an acute drop in hemolymph titers of the active molting hormone **20-hydroxyecdysone**.\n- **Eclosion & Pupation Arrest**: Nymphs and larvae fail to undergo apolysis and ecdysis. Developing insects are either unable to shed their sclerotized exuviae (dying trapped within their cuticle) or emerge with fatal wing malformations, twisted genitalia, and sterility.\n\n**3. Primary Gustatory Antifeedant Mechanism:**\nBeyond endocrine disruption, azadirachtin exhibits potent behavioural deterrence across over 400 phytophagous insect species:\n- **Chemosensory Firing**: At concentrations as low as $0.1-1.0\\text{ ppm}$, azadirachtin molecules stimulate specialized deterrent gustatory receptor neurons located on the maxillae, labrum, and epipharynx of chewing insects.\n- **Sugar/Amino-Acid Receptor Silencing**: Simultaneously, it suppresses the firing of sugar- and inositol-sensing neurons that normally stimulate feeding behavior.\n- **Starvation Cascade**: The insect perceives host plants treated with neem as toxic or unpalatable, ceasing feeding immediately. Without digestive nutrition, the insect dies of physiological starvation within 48 to 72 hours, leaving the crop foliage intact."
    },
    {
        "slug": "concept-veppam-bitter-triterpenes-gedunin-nimbidin-and-dermatological-antimicrobial-pharmacology",
        "category": "concept",
        "file": "concept-veppam-bitter-triterpenes-gedunin-nimbidin-and-dermatological-antimicrobial-pharmacology.md",
        "name_en": "Gedunin, Nimbidin, Nimbin Triterpenes & Dermatological Antimicrobial Siddha Pharmacology",
        "name_ta": "கெடுனின், நிம்பிதின், நிம்பின் கசப்பு ட்ரைடெர்பீன்கள் மற்றும் தோல்நோய் நீக்கும் சித்த மருத்துவ மருந்தியல்",
        "era": "Siddha to Modern Pharmacological Era",
        "year_start": 500,
        "year_end": 2025,
        "thinai": "marutham",
        "summary_en": "Pharmacological science and Siddha therapeutic principles of neem triterpenes: bitter limonoids including gedunin, nimbidin, nimbin, and nimbolide that inhibit dermatophytic fungi, disrupt bacterial cell membrane permeability, downregulate inflammatory prostaglandin E2, and promote re-epithelialization in stubborn skin lesions (padai, karuppan, namai).",
        "summary_ta": "வேப்ப மரத்தின் கெடுனின், நிம்பிதின், நிம்பின் மற்றும் நிம்போலைடு கசப்பு ட்ரைடெர்பீன்களின் மருந்தியல் தத்துவம்: பூஞ்சைக்காளான்கள் மற்றும் பாக்டீரியாவை அழித்தல், அழற்சித் தூண்டல்களை மட்டுப்படுத்துதல் மற்றும் சித்த மருத்துவத்தில் படை, கரப்பான், அரிப்பு போன்ற தோல்நோய்களைக் குணப்படுத்தும் திறன்.",
        "sources": [
            "Agathiyar Gunavagadam & Siddha Materia Medica",
            "Phytomedicine & Antimicrobial Screening of Meliaceae Triterpenoids",
            "Indian Journal of Dermatology (Neem Formulations)"
        ],
        "content": "# Gedunin, Nimbidin, Nimbin Triterpenes & Dermatological Antimicrobial Siddha Pharmacology\n\nIn classical Siddha medicine (*Siddha Maruthuvam*), the neem tree is venerated as the supreme vegetal purifier of the blood (*Uthira-thooimai*) and the ultimate antidote for cutaneous afflictions:\n\n**1. Siddha Energetic Principles (*Gunavagadam*):**\n- **Taste (*Suvai*)**: Dominant *Kaippu* (intense bitterness) with secondary *Thuvarppu* (astringency).\n- **Potency (*Veeriyam*)**: *Thann-veeriyam* (cooling energy), neutralizing excessive internal systemic heat.\n- **Post-Digestive Transformation (*Pirivu*)**: *Kaarpu* (pungent), drying out excessive bodily moisture.\n- **Tridoshic Impact**: Specifically pacifies morbidly elevated *Pitham* (metabolic fire manifesting as dermatological inflammation, ulceration, and fever) and *Kapham* (phlegm, suppurative exudation).\n\n**2. Pharmacological Dynamics of Non-Azadirachtin Triterpenoids:**\nWhile azadirachtin dominates insecticidal action, neem's clinical dermatological efficacy stems from its distinctive matrix of secondary triterpenes:\n- **Gedunin**: A pentacyclic limonoid that demonstrates remarkable antifungal efficacy against human dermatophytes, notably *Trichophyton rubrum*, *Trichophyton mentagrophytes*, and *Epidermophyton floccosum*, inhibiting fungal mycelial growth through disruption of chitin wall synthesis.\n- **Nimbidin**: A sulfur-containing tetranortriterpene complex that exhibits pronounced anti-inflammatory, antipyretic, and analgesic activity. It downregulates inducible cyclooxygenase-2 (COX-2) and suppresses the biosynthesis of pro-inflammatory prostaglandin E2 ($PGE_2$), alleviating swelling and erythema in active eczema.\n- **Nimbin & Nimbolide**: Display potent bactericidal activity against Gram-positive skin pathogens, including multi-drug-resistant *Staphylococcus aureus* (MRSA) and *Streptococcus pyogenes*, by disrupting bacterial cell membrane permeability and inhibiting biofilm formation.\n\n**3. Sarcoptic & Wound-Healing Therapeutics:**\nIn the Siddha treatment of scabies (*karuppan / namai*) caused by the burrowing itch-mite *Sarcoptes scabiei*, a topical paste of fresh neem leaves ground with fresh wild turmeric rhizome (*Curcuma aromatica / Curcuma longa*, Tamil: *kasturi manjal*) is applied over the body. The triterpenes paralyze the mites while the curcuminoids accelerate collagen cross-linking and fibroblast proliferation, bringing about rapid re-epithelialization of excoriated skin without scar tissue formation."
    },
    {
        "slug": "concept-mariamman-shrine-cooling-foliar-prophylaxis-epidemic-quarantine-and-ritual-ecology",
        "category": "concept",
        "file": "concept-mariamman-shrine-cooling-foliar-prophylaxis-epidemic-quarantine-and-ritual-ecology.md",
        "name_en": "Mariamman Shrine Cooling Foliar Prophylaxis, Variola Epidemic Quarantine & Ritual Hygiene Ecology",
        "name_ta": "மாரியம்மன் திருத்தலக் குளிர்ச்சி வேப்பிலை முறை, வைசூரித் தொற்றுத் தனிமைப்படுத்தல் மற்றும் வழிபாட்டுச் சூழலியல்",
        "era": "Medieval to Contemporary Era",
        "year_start": 600,
        "year_end": 2025,
        "thinai": "marutham",
        "summary_en": "Cultural epidemiology and public hygiene encoded in Tamil village Mariamman rituals: the attribution of eruptive viral fevers (Variola major / smallpox / ammai) to goddess thermal energy, enforcement of strict household quarantine marked by doorway veppilai-kothu sprays, cooling dietary regimens (fermented koozh, tender coconut), and patient isolation on beds of fresh margosa foliage.",
        "summary_ta": "தமிழ்நாட்டு மாரியம்மன் வழிபாட்டு மரபில் பொதிந்துள்ள பாரம்பரியத் தொற்றுநோயியல் நெறிமுறைகள்: வைசூரி/அம்மை நோயைத் தெய்வக் குளிர்ச்சி வழிபாடாகக் கருதி வீட்டு வாயிலில் வேப்பிலை கொத்துக் கட்டித் தனிமைப்படுத்துதல், நோயாளியை வேப்பிலைப் படுக்கையில் கிடத்துதல் மற்றும் புளித்த கேழ்வரகுக் கூழ் உணவுமுறை.",
        "sources": [
            "Tamil Village Ritual & Epidemic History Studies",
            "Folk Epidemiology & Goddess Cults in South India",
            "Imperial Gazetteer of India (Madras Presidency Medical Observations)"
        ],
        "content": "# Mariamman Shrine Cooling Foliar Prophylaxis, Variola Epidemic Quarantine & Ritual Hygiene Ecology\n\nThe veneration of Goddess Mariamman (*மாரியம்மன்*) across rural Tamil Nadu represents one of civilization's most sophisticated syntheses of sacred ritual, community epidemiology, and botanical prophylaxis:\n\n**1. Folk Nosology of Thermal Eruption (*Muthu Kuthal / Ammai*):**\nIn traditional Tamil village medicine, severe eruptive epidemics—principally smallpox (*Variola major*, designated *பெரியம்மை*), chickenpox (*Varicella-zoster*, *சின்னம்மை*), and measles (*தட்டம்மை*)—were conceptualized not as profane infections, but as the fiery bodily descent (*aagamanam*) of the Goddess herself. Pustular vesicles erupting upon the skin were reverently named *muthu* (sacred pearls). Because the Goddess represented uncontained cosmic heat (*anal / agni*), treatment focused on cooling pacification (*kulirthal*) rather than adversarial expulsion.\n\n**2. Household Quarantine & Signposting (*Veppilai-Kothu*):**\nThe epidemiological protocol mandated by Mariamman tradition enforced quarantine with civic precision:\n- **Doorway Signage**: The moment pox lesions were confirmed, the family hung a lush branch of fresh neem leaves (*veppilai-kothu*) across the front door lintel. This served as an unmistakable public notice warning neighbors, relatives, and traveling strangers not to enter the infected dwelling.\n- **Spatial Separation**: The patient was isolated in an inner sanctified room. Family members abstained from traveling beyond the village boundary and avoided preparing tempering spices (*thaalithal*) with hot mustard and chili oil, whose vapors could trigger agonizing bronchospasm in febrile pox sufferers.\n- **Ablution Protocols**: Caregivers washed their feet and hands in turmeric-and-neem water kept in a stone trough at the doorway before touching the patient.\n\n**3. The Foliar Bedding Microclimate (*Veppilai-Padukai*):**\nThe infected individual was laid upon a thick mattress woven entirely of fresh neem leaves (*veppilai-padukai*):\n- **Mechanical Non-Adherence**: Unlike woven cotton sheets or coir mats, the smooth, waxy cuticles of fresh neem leaflets do not adhere to weeping pox vesicles, preventing painful skin tearing when the patient shifts position.\n- **Continuous Terpene Diffusion**: Body heat stimulates the gentle, continuous vaporization of volatile antimicrobial monoterpenes and triterpenes from the crushed leaves, creating a sanitized micro-troposphere that suppresses opportunistic secondary bacterial superinfections (*Staphylococcus* and *Pseudomonas*).\n- **Desquamation Management**: As pox pustules dry into infectious crusts (scabs), the scabs flake off into the neem foliage, which is gathered daily and incinerated in a sanitary pit.\n\n**4. Nutritional Therapeutics:**\nThe patient was sustained on a diet designed to restore hydration and gut microflora: chilled, sour fermented finger millet porridge (*chuzhal koozh*), tender coconut water (*elaneer*), and fresh buttermilk churned with crushed shallots, replenishing electrolytes and cooling the metabolic core."
    },
    {
        "slug": "institution-village-neem-commons-sacred-grove-trusts-and-traditional-sekku-crushers",
        "category": "institution",
        "file": "institution-village-neem-commons-sacred-grove-trusts-and-traditional-sekku-crushers.md",
        "name_en": "Village Neem Commons, Oor-Mandhai Sacred Grove Trusts & Vaniya Chettiar Sekku Oil Crushers",
        "name_ta": "ஊர் மந்தை வேப்ப மரப் பொதுவெளிகள், கோயில் நந்தவன அறக்கட்டளைகள் மற்றும் வாணியச் செட்டியார் செக்கு ஆலைகள்",
        "era": "Medieval to Modern Era",
        "year_start": 800,
        "year_end": 2025,
        "thinai": "marutham",
        "summary_en": "Agrarian institutions governing neem resources across Tamil settlements: communal usufruct rights over village-green (oor-mandhai) neem trees, temple grove (nandavanam) endowments protecting seed collection for eternal sanctuary lamps, and hereditary Vaniya Chettiar oil-pressing guilds operating communal ox-driven stone-and-timber sekkus.",
        "summary_ta": "தமிழக ஊரக அமைப்புகளில் வேப்ப மரப் பொதுவள மேலாண்மை: ஊர் மந்தைப் பொது வேப்ப மரங்களின் உரிமைகள், திருக்கோயில் நந்தவன அறக்கட்டளைகளின் விளக்கெண்ணெய் மானியங்கள் மற்றும் வாணியச் செட்டியார் மரச்செக்கு ஆலைகளின் எண்ணெய்ப் பகிர்வு மரபு.",
        "sources": [
            "South Indian Inscriptions (Epigraphia Carnatica & Chola Epigraphy)",
            "Tamil Village Common Property Resources (CPR) Studies",
            "Castes and Tribes of Southern India (Vaniyan / Sekku Guilds)"
        ],
        "content": "# Village Neem Commons, Oor-Mandhai Sacred Grove Trusts & Vaniya Chettiar Sekku Oil Crushers\n\nThe sustainable management, processing, and equitable distribution of neem products across medieval and early modern Tamil country were anchored by enduring civic and caste-based institutions:\n\n**1. Communal Common Property Commons (*Oor-Mandhai Veppamaram*):**\nIn rural agrarian villages (*oor*), centenary neem trees were established as inalienable communal property along critical civic corridors:\n- **Threshing Greens (*Kalam*) & Assembly Grounds (*Mandhai*)**: Mature neem avenues provided cooling microclimates for council meetings (*panchayat*), cattle resting stations, and children's open-air schooling (*thinnai palli*).\n- **Prohibition of Felling**: Customary village law strictly prohibited the felling (*maram-vettal*) of shade-giving and temple-affiliated neem trees. Timber could only be salvaged if a tree fell naturally during cyclonic storms, in which case the dense *vagai* or neem heartwood was reserved for village agricultural implements or temple doors.\n\n**2. Seed Collection Auctions & Usufruct Rights (*Kothu-Elam*):**\n- **Public Bidding**: Annually during the *Chithirai–Vaikasi* fruiting season, the village assembly (*oorar*) auctioned the usufruct rights (*kothu-elam*) to collect fallen neem drupes beneath communal trees.\n- **Irrigation Fund (*Kudimaramathu*)**: The revenue generated from these seed collection auctions was deposited directly into the village water treasury (*eri-variyam* / *kudimaramathu*) to finance the desilting of irrigation canals and repair of sluice gates before the arrival of the Northeast monsoon.\n- **Subsistence Gathering**: Landless agricultural laborers, widows, and children retained gathering rights in fringe commons, bartering gathered seeds at village shops for rice, salt, and coarse cloth.\n\n**3. Temple Sacred Grove Trusts (*Nandavanam & Nandavilakku* Endowments):**\nInscriptions from the Chola, Pandya, and Vijayanagara periods record extensive land and tree grants (*thoppu-manyam*) to temples for maintaining sacred groves (*nandavanam*):\n- **Perpetual Sanctuary Lamps**: Stone inscriptions at Samayapuram, Thanjavur, and Madurai detail endowments established by royalty and merchant guilds requiring local crushers to supply specified monthly measures (*ulakku*, *azhakku*) of non-edible oils—specifically *veppennai* and *iluppai-ennai*—to fuel perpetual lamps (*nandavilakku*) burning night and day in inner temple sanctums.\n- **Insecticidal Conservation**: The pungent smoke of pure *veppennai* burned in bronze lamps functioned as a natural continuous fumigant, protecting temple timber rafters, palm-leaf library manuscripts (*suvadi*), and stone bas-reliefs from wood-boring beetles and fungal degradation.\n\n**4. *Vaniya Chettiar* (Sekku Crushing Guilds):**\nThe mechanical transformation of neem seeds into oil was monopolized by the hereditary oil-pressing guild (*Vaniya Chettiar* / *Sekkar*):\n- **Guild Guild Regulations**: The guild maintained standard weights, measures, and bullock welfare guidelines, rotating pressing shifts between families.\n- **Barter Ratios**: Farmers delivered dried neem seeds to the *sekku* and received back a fixed volumetric proportion of clarified oil ($25\\%-30\\%$ by weight) while the oil-crusher retained the high-protein *veppam pinnakku* cake as remuneration for labor, which was then sold to paddy farmers as organic fertilizer."
    },
    {
        "slug": "place-samayapuram-ancient-kaveri-veppam-agroforestry-and-veppennai-haven",
        "category": "place",
        "file": "place-samayapuram-ancient-kaveri-veppam-agroforestry-and-veppennai-haven.md",
        "name_en": "Samayapuram: Ancient Kaveri Basin Mariamman Neem Agroforestry & Veppennai Haven",
        "name_ta": "சமயபுரம் - பண்டைய காவிரிப் படுகை மாரியம்மன் வேப்பிலை வேளாண்மை மற்றும் வேப்பெண்ணெய்த் தளம்",
        "era": "Medieval to Modern Era",
        "year_start": 700,
        "year_end": 2025,
        "thinai": "marutham",
        "summary_en": "The paramount regional center of Tamil neem ecology and Mariamman pilgrimage situated on the fertile northern alluvial banks of the Kaveri River near Tiruchirappalli (10.9280° N, 78.7420° E): world-famous for its sacred margosa temple groves, annual Poo-Chorithal flower-and-leaf festivals, and extensive network of artisanal sekku neem oil pressers.",
        "summary_ta": "திருச்சிராப்பள்ளிக்கு வடக்கே வளமான காவிரிப் படுகையில் அமைந்துள்ள சமயபுரம் (10.9280° N, 78.7420° E): உலகப் புகழ்பெற்ற மாரியம்மன் திருத்தலம், ஆண்டுதோறும் நடைபெறும் பூச்சொரிதல் வேப்பிலை விழா, பல்லாயிரக்கணக்கான வேப்ப மரங்கள் மற்றும் மரச்செக்கு வேப்பெண்ணெய் வர்த்தகத்தின் வரலாற்றுத் தளம்.",
        "sources": [
            "Trichinopoly District Gazetteer (Temple & Agro-Economy)",
            "Imperial Gazetteer of India (Samayapuram & Kaveri Basin)",
            "Historical Topography of the Kaveri Delta Shrines"
        ],
        "content": "# Samayapuram: Ancient Kaveri Basin Mariamman Neem Agroforestry & Veppennai Haven\n\nSituated 15 kilometres north of Tiruchirappalli along the ancient trade and pilgrimage highway crossing the Kaveri-Kollidam river system (10.9280° N, 78.7420° E), **Samayapuram** (historically known as *Kannanur* under the Hoysalas and Cholas) stands as the epicentral sanctuary of Tamil neem agroforestry and foliar prophylactic culture:\n\n**1. Geographic Setting & Ecotonal Terroir:**\n- **Coordinates & Hydrology**: Located at an elevation of 75 metres on the fertile northern alluvial fringe of the Kaveri Delta, where canal-irrigated paddy wetlands (*marutham*) interface with well-drained red ferruginous gravelly plains (*mullai/palai* border).\n- **Arboricultural Haven**: This ecotone provides ideal deep, aerated subsoil conditions for *Azadirachta indica*, which sends taproots deep into subterranean water tables while flourishing under intense solar radiation ($38^\\circ\\text{C}-43^\\circ\\text{C}$ in summer), yielding exceptionally high concentrations of seed limonoids.\n\n**2. Spiritual & Cultural Capital of Neem:**\n- **The Sacred Neem Grove of Kannanur Mariamman**: The famous Samayapuram Mariamman Temple is inextricably intertwined with the margosa tree. Unlike orthodox Agamic temples dominated by stone sanctums, the sacred presence (*sanctorum*) here is historically rooted in an ancient neem tree (*sthala vriksham*).\n- **Iconography of Foliar Sovereignty**: The deity's processional icon is perpetually adorned with fresh sprays of neem leaves, her golden spear (*soolam*) wrapped in veppilai, and her sanctum scented with burning *veppennai* lamps.\n\n**3. *Poo-Chorithal* & *Panguni* Foliar Pilgrimage:**\n- **The Festival of Flowers & Leaves**: Annually in the Tamil month of *Masi–Panguni* (March–April), the temple observes the monumental 28-day *Poo-Chorithal* festival. Tens of thousands of baskets overflowing with fragrant white neem blossoms (*veppampoo*), fresh green veppilai garlands, and jasmine are offered directly into the sanctum, piling over two metres high around the deity to signify the metaphorical cooling of her cosmic heat.\n- **Mass Prophylactic Gathering**: Over two million pilgrims travel to Samayapuram each spring, carrying handheld neem fans (*veppilai-visiri*), tonsuring their heads, and bathing in the holy *Periyakulam* sacred tank, whose waters are steeped in millions of dissolved neem leaves, functioning as a mass public dermatological sanitation bath.\n\n**4. Regional *Sekku* Crushing & Oil Distribution Hub:**\nSurrounding Samayapuram, Manachanallur, and neighboring rural settlements lies the densest concentration of traditional wood-and-stone oil pressers (*mara-sekku*) in central Tamil Nadu. Processing hundreds of tons of wild-harvested and avenue neem seeds collected across the delta, Samayapuram remains the premier commercial supply center for pure, unadulterated cold-pressed *veppennai* and neem seed cake, distributing botanical biopesticides and medicinal oils across India and overseas."
    },
    {
        "slug": "text-sangam-corpus-purananuru-and-marutham-poems-on-veppam-garlands-and-medicinal-bitterness",
        "category": "text",
        "file": "text-sangam-corpus-purananuru-and-marutham-poems-on-veppam-garlands-and-medicinal-bitterness.md",
        "name_en": "Purananuru, Kuruntokai, Akananuru & Marutham Verses on Pandya Veppam Garlands & Bitter Margosa Cure",
        "name_ta": "புறநானூறு, குறுந்தொகை, அகநானூறு மற்றும் மருதத் திணைப் பாடல்களில் பாண்டியர் வேப்ப மாலை மற்றும் கைப்பு மருந்து மரபு",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "marutham",
        "summary_en": "Classical Sangam literary testimonies celebrating the neem tree: Purananuru verses lauding the Pandya kings' martial veppam-pum-kanni garlands, Kuruntokai and Akananuru descriptions of riverbank neem groves offering cooling shade to travellers, and early poetic acknowledgments of margosa's unpalatable yet life-saving medicinal bitterness.",
        "summary_ta": "சங்க இலக்கியத்தில் வேப்ப மரத்தின் வரலாற்றுப் பதிவுகள்: புறநானூற்றில் பாண்டிய மன்னர்களின் வெற்றிச் சின்னமான வேப்பம்பூ மாலை, குறுந்தொகை மற்றும் அகநானூற்றில் வழிப்போக்கர்களுக்கு நிழல் தரும் வேப்பமர மருத நிலக் காட்சிகள் மற்றும் வேம்பின் கசப்பும் மருத்துவக் குணமும் குறித்த செவ்விலக்கியக் குறிப்புகள்.",
        "sources": [
            "Purananuru (Verses 45, 76, 77, 100, 396)",
            "Kuruntokai (Verses 67, 196, 248)",
            "Akananuru (Verses 24, 309, 387)",
            "Tolkappiyam Porulatikaram (Vanchi & Vakai Thinaigal)"
        ],
        "content": "# Purananuru, Kuruntokai, Akananuru & Marutham Verses on Pandya Veppam Garlands & Bitter Margosa Cure\n\nThe margosa tree (*Azadirachta indica*, Tamil: *வேம்பு / வேப்பமரம்*) occupies a foundational place across both the martial (*Puram*) and intimate (*Agam*) genres of classical Sangam Tamil poetry:\n\n**1. The Pandyan Dynastic Garland in *Purananuru*:**\nThe *Purananuru* establishes the fresh neem flower chaplet as the royal military signet of the Pandyan dynasty:\n- **Verse 76 by Idaikkunrur Kilar**: Celebrates the youthful Pandya monarch Talaiyalanganathu Seruvendra Nedunchezhiyan entering the catastrophic battle against seven confederated kings:\n  > *\"கருங்கால் வேம்பின் ஒண்குழை யாரமொடு / பொலந்தார் மார்பின் நெடியோன்...\"*\n  *(Adorned with the bright garland of dark-trunked neem foliage and gleaming white blossoms upon his golden chest, the great King advanced...)*\n- **Verse 45 by Kovur Kilar**: Recounts the sacred botanical emblems of Tamil kingship, contrasting the golden bauhinia (*aathi*) of the Cholas with the bitter, sharp-toothed white neem flowers (*veppam-pum-kanni*) worn by the Pandya monarchs as a crown of austere justice, invincibility, and moral virtue.\n\n**2. Domestic & Arboreal Realism in *Kuruntokai* & *Akananuru*:**\nIn the interior landscapes of *Agam* poetry, the neem tree provides vivid sensory markers of the riverine agricultural (*Marutham*) and arid transit (*Palai*) landscapes:\n- **Kuruntokai 196 by Milaipperunkantan**: Describes the ripe yellow neem fruit (*veppam-pazham*) fallen along the sandy riverbanks, picked at by green parakeets and dove flocks, contrasting the astringent bitterness of its pulp with the deep, maternal shade cast by its widespread branches over sunburnt travelers.\n- **Akananuru 24 & 309**: Portray dense avenues of wayside neem trees planted by village elders, their foliage murmuring in the hot summer wind (*kothai*), filtering dust and providing shelter to weary bullock caravans halting by the village watering trough (*kallural*).\n\n**3. The Philosophical Metaphor of Bitterness (*Kaippu*):**\nSangam and post-Sangam Tamil literature systematically deploy the intense taste of the neem leaf as a philosophical touchstone:\n- **Beneficent Bitterness**: Just as the bitter leaves and oil of the neem tree are harsh to the tongue yet banish festering diseases from the body, truthful counsel (*kadum-sol*) spoken by loyal ministers and elders may taste bitter to a king's ego, yet preserves the state from ruin.\n- **Wound Prophylaxis**: Early poetic allusions describe battlefield surgeons washing iron spear wounds with boiling neem leaf decoctions and strapping fresh leaves over lacerations to ward off putrefaction (*pun-aarthal*), demonstrating that empirical phytochemical awareness was already deeply embedded in ancient Tamil material culture."
    }
]

EDGES = [
    [
        "text-sangam-corpus-purananuru-and-marutham-poems-on-veppam-garlands-and-medicinal-bitterness",
        "describes",
        "artifact-veppilai-leafy-garlands-ritual-foliage-fans-and-chewed-margosa-toothsticks",
        "material_culture",
        "Sangam Era",
        "Purananuru and Akananuru document the Pandya monarchs wearing neem flower garlands (veppam-pum-kanni) into battle and commoners chewing margosa toothsticks.",
        "Purananuru 76 & Akananuru 24"
    ],
    [
        "text-sangam-corpus-purananuru-and-marutham-poems-on-veppam-garlands-and-medicinal-bitterness",
        "attests",
        "concept-veppam-bitter-triterpenes-gedunin-nimbidin-and-dermatological-antimicrobial-pharmacology",
        "material_culture",
        "Sangam Era",
        "Sangam verses attest to the intense medicinal bitterness (kaippu) of neem leaves applied to battlefield wounds and skin afflictions.",
        "Kuruntokai 196 & Purananuru 396"
    ],
    [
        "concept-azadirachtin-tetranortriterpenoid-limonoid-eclosion-inhibition-and-antifeedant-action",
        "underpins",
        "technology-veppilai-herbal-fumigation-crude-water-extract-spray-and-grain-protection",
        "material_culture",
        "Sangam to Modern Era",
        "The eclosion inhibition, gut disruption, and sensory antifeedant action of azadirachtin provide the biochemical mechanism for veppilai foliar sprays and granary fumigation.",
        "Entomological Studies on Meliaceae Limonoids"
    ],
    [
        "technology-veppam-seed-depulping-sun-drying-and-vagai-wood-sekku-cold-pressing",
        "produces",
        "artifact-cold-pressed-bitter-veppennai-seed-cake-fertilizer-and-earthen-storage-jars",
        "material_culture",
        "Classical to Modern Era",
        "Ox-driven cold pressing of dried neem kernels in vagai-wood sekku crushers yields unrefined bitter veppennai oil and high-nitrogen veppam pinnakku seed cake.",
        "Tamil Sekku Manuals & Siddha Pharmacy"
    ],
    [
        "concept-veppam-bitter-triterpenes-gedunin-nimbidin-and-dermatological-antimicrobial-pharmacology",
        "informs",
        "concept-mariamman-shrine-cooling-foliar-prophylaxis-epidemic-quarantine-and-ritual-ecology",
        "material_culture",
        "Medieval to Modern Era",
        "The antimicrobial and antiviral properties of gedunin, nimbidin, and nimbolide inform the folk epidemiological practice of bedding variola and measles patients on fresh veppilai.",
        "Agathiyar Gunavagadam & Folk Epidemiology"
    ],
    [
        "concept-mariamman-shrine-cooling-foliar-prophylaxis-epidemic-quarantine-and-ritual-ecology",
        "utilizes",
        "artifact-veppilai-leafy-garlands-ritual-foliage-fans-and-chewed-margosa-toothsticks",
        "material_culture",
        "Medieval to Modern Era",
        "Foliar cooling quarantine rituals employ dense veppilai sprays, handheld ritual fans, and margosa doorway festoons to shield against epidemic pestilence.",
        "South Indian Village Ritual Practices"
    ],
    [
        "institution-village-neem-commons-sacred-grove-trusts-and-traditional-sekku-crushers",
        "manages",
        "technology-veppam-seed-depulping-sun-drying-and-vagai-wood-sekku-cold-pressing",
        "material_culture",
        "Medieval to Modern Era",
        "Village neem tree usufruct trusts and hereditary Vaniya Chettiar guilds regulate the communal harvesting, depulping, and rotational sekku crushing of fallen seeds.",
        "Inscriptions of the Tamil Country"
    ],
    [
        "institution-village-neem-commons-sacred-grove-trusts-and-traditional-sekku-crushers",
        "distributes",
        "artifact-cold-pressed-bitter-veppennai-seed-cake-fertilizer-and-earthen-storage-jars",
        "material_culture",
        "Chola to Modern Era",
        "Village temple trusts and crushing guilds distribute cold-pressed veppennai for lighting sanctum lamps and residual seed cake as soil nematicide.",
        "Chola Epigraphical Records & Temple Accounts"
    ],
    [
        "place-samayapuram-ancient-kaveri-veppam-agroforestry-and-veppennai-haven",
        "fosters",
        "concept-mariamman-shrine-cooling-foliar-prophylaxis-epidemic-quarantine-and-ritual-ecology",
        "material_culture",
        "Medieval to Modern Era",
        "The sacred Mariamman complex at Samayapuram in the Kaveri delta developed institutionalized neem foliar cooling and pestilence quarantine traditions.",
        "Trichinopoly District Gazetteer"
    ],
    [
        "technology-veppam-seed-depulping-sun-drying-and-vagai-wood-sekku-cold-pressing",
        "flourishes_in",
        "place-samayapuram-ancient-kaveri-veppam-agroforestry-and-veppennai-haven",
        "material_culture",
        "Medieval to Modern Era",
        "The fertile alluvial Kaveri delta surrounding Samayapuram hosts extensive neem tree agroforestry avenues and traditional bullock-drawn sekku oil crushers.",
        "Historical Topography of Kaveri Basin"
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
