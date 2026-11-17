#!/usr/bin/env python3
"""
Harvester: Batch 47 - Ancient Tamil Tamarind Orchard Agroforestry, Tartaric Acid Preservation, Seed Starch Sizing & Culinary-Metallurgical Chemistry
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
        "slug": "text-sangam-literature-on-puli-tamarind-broths-puli-choru-and-arid-zone-cuisine",
        "category": "text",
        "file": "text-sangam-literature-on-puli-tamarind-broths-puli-choru-and-arid-zone-cuisine.md",
        "name_en": "Sangam Poetic References to Puli (Tamarindus indica), Puli-Kuzhambu Stews & Travel Rations",
        "name_ta": "சங்க இலக்கியங்களில் புளி (Tamarindus indica), புளிக்குழம்பு, புளிச்சோறு மற்றும் பாலை-முல்லை உணவுக் குறிப்புகள்",
        "era": "Sangam Era",
        "year_start": -300,
        "year_end": 300,
        "thinai": "mullai",
        "summary_en": "Classical Tamil literary accounts in Purananuru, Akananuru, Perumpanarruppadai, Kuruntokai, and Natrinai describing sour tamarind pulp (puli) used to acidify millet, fish, meat, and greens stews (puli-ulavai, puli-kuzhambu), tender tamarind leaf-bud curries (ochu-puli), and shelf-stable tamarind rice (puli-choru) carried across arid Palai trails.",
        "summary_ta": "புறநானூறு, அகநானூறு, பெரும்பாணாற்றுப்படை, குறுந்தொகை மற்றும் நற்றிணை ஆகிய சங்க நூல்களில் புளியங்காய், புளியம்பழக் குழம்பு, புளிச்சோறு மற்றும் முல்லை-பாலை நில உணவுப் பதப்படுத்துதல் குறித்த இலக்கியச் சான்றுகள்.",
        "sources": [
            "Purananuru",
            "Akananuru",
            "Perumpanarruppadai",
            "Kuruntokai",
            "Natrinai"
        ],
        "content": "# Sangam Literature on Puli (Tamarind) Broths, Puli-Choru & Arid-Zone Cuisine\n\nAcross the Sangam anthologies, *puli* (*Tamarindus indica*) stands as the foundational acidulant, flavour balancer, and food preservative of ancient Tamil kitchens across *Mullai*, *Palai*, *Marutham*, and *Neythal* landscapes:\n\n**Poetic & Culinary Attestations (Cited by Title):**\n- **Acidified Stews & Curries**: *Purananuru* and *Akananuru* describe pastoral and dryland housewives squeezing clarify-strained tamarind extract (*puli-neer*) into earthen pots simmering with cured venison, dried fish (*karuvadu*), field beans (*avarai*), or wild greens (*keerai*) seasoned with roasted black pepper (*milagu*) and mustard.\n- **Perumpanarruppadai & Kuruntokai**: Poems celebrate the tart aroma of green unripe tamarind pods (*puliyankai*) and tender pinkish-green spring leaf shoots (*புளியந்தளிர்* / *puliyanthalir*) ground with buttermilk and millet gruel to relieve summer heat.\n- **Puli-Choru Caravan Rations**: In *Natrinai* and *Akananuru*, wayfarers and salt merchants (*umanar*) crossing scorched *Palai* scrublands carry leaf-wrapped parcels of tamarind-infused rice (*puli-choru*), whose high tartaric acidity prevents bacterial spoilage for days without refrigeration."
    },
    {
        "slug": "concept-tamarind-d-tartaric-acid-biochemistry-and-pazhampuli-maillard-aging",
        "category": "concept",
        "file": "concept-tamarind-d-tartaric-acid-biochemistry-and-pazhampuli-maillard-aging.md",
        "name_en": "D-Tartaric Acid Biochemistry in Tamarind Pulp & Maillard Chemistry of Aged Pazhampuli",
        "name_ta": "புளியின் டார்டாரிக் அமில வேதியியலும் பழம்புளி (Pazhampuli) பதப்படுத்தலின் மெயில்லார்டு வினையும்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Organic food chemistry of Tamarindus indica fruit pulp: exceptionally high natural concentration of d-(+)-tartaric acid (12–18%), malic acid, reducing hexose sugars (30–40%), and pectin, and the thermodynamic/chemical transformation of newly harvested red tamarind (puthupuli) into jet-black aged tamarind (pazhampuli) via salt-cured Maillard browning.",
        "summary_ta": "புளியம்பழத்தில் உள்ள இயற்கை டி-டார்டாரிக் அமிலம் (12–18%), மாலிக் அமிலம் மற்றும் பெக்டின் வேதியியலும், கல் உப்பு சேர்த்து மண்பானையில் மூன்றாண்டுகள் வைத்த பழம்புளி கருமை நிறமாகிப் பித்தம் தணிக்கும் அறிவியலும்.",
        "sources": [
            "Phytochemistry and Organic Acids of Tamarindus indica",
            "Siddha Materia Medica (Gunapadam: Mooligai Vaguppu)",
            "Food Chemistry of Non-Enzymatic Browning in Aged Tamarind"
        ],
        "content": "# D-Tartaric Acid Biochemistry & Pazhampuli Maillard Aging\n\nUnlike citrus fruits acidified by citric acid, the fruit pod of *Tamarindus indica* is one of the richest plant sources in nature of dextrorotatory **$(2R,3R)$-tartaric acid** ($d$-tartaric acid):\n\n**1. Organic Acid & Sugar Matrix:**\n- **Chemical Profile**: Deseeded ripe tamarind pulp contains $12\\text{--}18\\%$ free and potassium-bound $d$-tartaric acid ($\\text{p}K_{a1} = 2.98, \\text{p}K_{a2} = 4.34$), $1\\text{--}2\\%$ $l$-malic acid, $30\\text{--}40\\%$ invert sugars (glucose and fructose), and $3\\text{--}4\\%$ soluble galacturonan pectin.\n- **Antimicrobial Buffering**: Adding tamarind extract lowers the pH of Tamil *kuzhambu* and *rasam* below $4.2$, inhibiting *Clostridium* and *Bacillus* spore germination in humid tropical ambient storage while chelating pro-oxidant trace iron.\n\n**2. Transformation of Puthupuli into Pazhampuli (1–3 Year Curing):**\n- Siddha medical treatises (*Gunapadam*) warn that freshly harvested golden-red tamarind (*puthupuli*) provokes acidic *pitham* and inflammation, whereas 1-to-3-year earthenware-cured black tamarind (*pazhampuli*) becomes medicinally benign and rounded in flavor.\n- **Chemical Mechanism**: Packing deseeded pulp with $8\\text{--}10\\%$ coarse rock salt (*kalluppu*) reduces water activity ($a_w < 0.70$). Over months, slow non-enzymatic **Maillard condensation** between amino acids and reducing sugars alongside acid-catalyzed hexose dehydration yields dark melanoidin polymers, 5-hydroxymethylfurfural (HMF), and partial esterification of free tartaric acid—mellowing sharp proton bite into deep umami-caramel complexity."
    },
    {
        "slug": "concept-puliyankottai-xyloglucan-seed-polysaccharide-rheology-and-binding-chemistry",
        "category": "concept",
        "file": "concept-puliyankottai-xyloglucan-seed-polysaccharide-rheology-and-binding-chemistry.md",
        "name_en": "Puliyankottai Seed Xyloglucan Polysaccharide Rheology, Warp-Sizing & Mural Gesso Binding",
        "name_ta": "புளியங்கொட்டை சைலோகுளூகன் (Xyloglucan) கூட்டுச்சர்க்கரைப் பசையின் நெசவுப் பாவும் சுதை ஓவியப் பிணைப்பு வேதியியலும்",
        "era": "Early Medieval to Modern Era",
        "year_start": 500,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Polymer chemistry of decorticated tamarind kernel powder (puliyankottai-podi): a branched beta-(1->4)-D-glucan backbone substituted with alpha-D-xylose and beta-D-galactose side chains that swells in boiling water into a tenacious, shear-stable hydrogel used for cotton handloom warp sizing, doll gesso, and temple mural binders.",
        "summary_ta": "வறுத்துத் தோல் நீக்கிய புளியங்கொட்டை மாவில் உள்ள சைலோகுளூகன் பாலிசாக்கரைடு, வெந்நீரில் கூழாகிப் பருத்தி நெசவுப் பாவுக்கும், பொம்மை வெள்ளை அடிப்பூச்சுக்கும், கோயில் சுதை ஓவியங்களுக்கும் உறுதியான பசையாகச் செயல்படும் வேதியியல்.",
        "sources": [
            "Chemistry and Rheology of Tamarind Kernel Polysaccharide (Jute & Cotton Textile Research)",
            "Traditional South Indian Mural & Kalamkari Binders",
            "Handloom Warp Sizing Practices of Tamil Nadu"
        ],
        "content": "# Puliyankottai Xyloglucan Polysaccharide Rheology & Binding Chemistry\n\nThe dense, dicotyledonous endosperm of the tamarind seed (*puliyankottai*) stores energy not as ordinary amylose starch, but as $60\\text{--}65\\%$ **tamarind kernel xyloglucan (TKP)**—an extraordinary structural biopolymer exploited by Tamil weavers, painters, and doll-makers:\n\n**1. Molecular Architecture & Hydrogel Rheology:**\n- **Branched Cellulosic Backbone**: TKP consists of a cellulose-like $\\beta\\text{-(1}\\rightarrow\\text{4)-D-glucan}$ main chain heavily substituted at $O\\text{-6}$ with $\\alpha\\text{-D-xylopyranose}$ and $\\beta\\text{-D-galactopyranosyl-(1}\\rightarrow\\text{2)-}\\alpha\\text{-D-xylopyranose}$ side units.\n- **Film Strength & Hydrogen Bonding**: Because its main chain mirrors cotton cellulose, boiled *puliyankottai* paste forms intimate intermolecular hydrogen bonds with cotton fibers without retrograding or cracking into brittle flakes under dry loom tension.\n\n**2. Craft & Industrial Applications:**\n- **Handloom Warp Sizing (*Paavu-Kanji*)**: Brushed onto stretched cotton warps, it encapsulates protruding fibrils to resist reed-beating abrasion.\n- **Architectural & Terracotta Gesso**: Mixed with washed kaolin (*vellai-mann*) or lime (*sunnambu*), tamarind-seed mucilage forms the base ground for *Kalamkari* cloth painting, Panruti/Thanjavur clay dolls, and traditional *sudhai* stucco sculptures."
    },
    {
        "slug": "concept-tamarind-tartrate-copper-oxide-chelation-and-bronze-icon-acid-pickling",
        "category": "concept",
        "file": "concept-tamarind-tartrate-copper-oxide-chelation-and-bronze-icon-acid-pickling.md",
        "name_en": "Tamarind-Salt Copper Oxide Chelation Chemistry & Panchaloha Bronze Acid-Pickling",
        "name_ta": "புளியும் உப்பும் கொண்டு செம்பு, பித்தளை மற்றும் பஞ்சலோகத் திருமேனிகளின் களிம்பு நீக்கும் அணைவு வேதியியல்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Coordination chemistry behind the traditional Tamil practice of scrubbing tarnished copper, brass (pithalai), bell-metal (vengalam), and panchaloha alloys with sour tamarind pulp and rock salt: protonation of basic copper carbonate and cuprous/cupric oxides coupled with bidentate tartrate-chloride chelation of Cu(II) ions.",
        "summary_ta": "செம்பு, பித்தளை மற்றும் வெண்கலப் பாத்திரங்களின் மீது படியும் பச்சைக் களிம்பு மற்றும் ஆக்சைடு படலங்களைப் புளியும் உப்பும் சேர்த்துத் தேய்க்கும்போது, டார்டாரேட் அயனிகள் தாமிர அயனிகளைக் கரைத்துப் பளபளப்பாக்கும் வேதியியல் வினை.",
        "sources": [
            "Coordination Chemistry of Tartrate-Metal Complexes",
            "South Indian Bronze Casting & Temple Vessel Maintenance Traditions",
            "Archaeometallurgy of Tamil Copper and Brass Ware"
        ],
        "content": "# Tamarind-Salt Copper Oxide Chelation & Bronze Acid-Pickling\n\nIn every Tamil household and temple kitchen (*madappalli*), tarnished copper pots (*sembu*), brass oil lamps (*kuthuvilakku*), and bronze vessels (*vengala-panai*) are restored to mirror brilliance without abrasive metal loss by rubbing with wet tamarind pulp (*puli*) dipped in common salt (*uppu*) and fine wood ash:\n\n**Coordination & Surface Chemistry:**\n1. **Nature of the Tarnish Layer**: Exposure to humid air, $\\text{CO}_2$, and sesame-oil combustion coats copper alloys with a dull brown film of cuprous/cupric oxide ($\\text{Cu}_2\\text{O}, \\text{CuO}$) and greenish basic copper(II) carbonate ($\\text{Cu}_2(\\text{OH})_2\\text{CO}_3$, *kalimbu*), which are insoluble in plain water or soap.\n2. **Synergistic Acid-Halide Dissolution**:\n   $$\\text{CuO (s)} + \\text{H}_2\\text{Tartrate (aq)} \\longrightarrow [\\text{Cu(Tartrate)}\\text{]}^0\\text{ (aq)} + \\text{H}_2\\text{O}$$\n   While $d$-tartaric acid donates protons ($\\text{H}^+$) to break the metal-oxygen lattice, chloride ions ($\\text{Cl}^-$) from the added salt penetrate the cuprous oxide layer to form transient chloro-cuprate intermediates.\n3. **Bidentate Tartrate Chelation**: The $\\alpha$-hydroxycarboxylate groups of the tartrate anion act as bidentate chelating ligands, locking dissolved $\\text{Cu}^{2+}$ ions into stable, water-soluble blue-green copper(II) tartrate complexes that rinse away cleanly in water while leaving the underlying unoxidized $\\text{Cu}^0/\\text{Sn}/\\text{Zn}$ alloy untouched."
    },
    {
        "slug": "technology-puli-ulaithal-harvesting-shell-cracking-and-stone-anvil-seed-decortication",
        "category": "technology",
        "file": "technology-puli-ulaithal-harvesting-shell-cracking-and-stone-anvil-seed-decortication.md",
        "name_en": "Puli-Ulaithal Canopy Shaking, Mallet Shell-Cracking & Stone-Anvil Seed Removal Workflow",
        "name_ta": "புளி உலுப்புதல், ஓடு தட்டுதல், நார் உரித்தல் மற்றும் கற்களில் கொட்டை தட்டும் பாரம்பரியத் தொழில்நுட்பம்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Multi-stage post-harvest processing engineering of ripe tamarind in the Masi–Panguni dry season: shaking high branches with hooked bamboo poles (puli-ulaithal), sun-curing pods on hard threshing floors, cracking brittle shells with wooden beaters (odu-thattuthal), stripping vascular strands (naar-eduthal), and ejecting seeds on granite anvils (kottai-thattuthal).",
        "summary_ta": "மாசி-பங்குனி மாதங்களில் முற்றிய புளியங்காய்களை மூங்கில் கொக்கியால் உலுப்பி, வெயிலில் காயவைத்து, மரக்கட்டையால் ஓடு தட்டி, நார் நீக்கி, கருங்கல் மீது வைத்துக் கொட்டை தட்டிப் புளி அடை தட்டும் தொழில்நுட்பம்.",
        "sources": [
            "Agricultural & Horticultural Practices of Madras Presidency",
            "Madurai & Dindigul District Gazetteers (Tamarind Processing)",
            "Ethnography of Rural Post-Harvest Crafts in Tamil Nadu"
        ],
        "content": "# Puli-Ulaithal Canopy Harvesting, Shell Cracking & Stone-Anvil Seed Removal\n\nBetween *Masi* and *Panguni* (February–April), when the moisture content of hanging tamarind pods drops below $20\\%$ and the cinnamon-brown exocarp detaches from the sticky mesocarp, rural processing teams execute a five-step mechanical sequence:\n\n**1. Canopy Harvesting (*Puli-Ulaithal*):**\n- Climbers ascend the massive fissured trunk carrying a long bamboo pole fitted with an iron or forked hardwood hook (*thuratti*). By rhythmically shaking secondary branches (*kombu-ulaithal*), only fully abscised ripe pods rain down onto spread coir mats, sparing immature pods.\n\n**2. Sun-Drying & Exocarp Shell Cracking (*Odu-Thattuthal*):**\n- Harvested pods are sun-dried for 2–3 days on cow-dung-plastered threshing floors (*kalam*) until the outer shell becomes crisp. Workers gently rap the pods with light curved wooden sticks (*odu-thattum-kattai*) and winnow away the shattered shell fragments (*puli-odu*).\n\n**3. Vascular Fiber Stripping (*Naar-Eduthal*) & Seed Ejection (*Kottai-Thattuthal*):**\n- Longitudinal woody vascular bundles (*puli-naar*) are peeled off by hand. Each sticky pod is then laid across a rough-dressed granite block (*puli-kottai-kallu*) lightly oiled with castor or sesame oil to prevent sticking; a single calibrated blow from a heavy tamarind-wood mallet pops the hard glossy seed (*puliyankottai*) cleanly out of the endocarp pocket without crushing the seed coat."
    },
    {
        "slug": "technology-puliyankottai-roasting-wet-milling-warp-sizing-and-famine-flour-leaching",
        "category": "technology",
        "file": "technology-puliyankottai-roasting-wet-milling-warp-sizing-and-famine-flour-leaching.md",
        "name_en": "Puliyankottai Sand-Roasting, Testa Decortication, Warp-Sizing Preparation & Famine-Flour Leaching",
        "name_ta": "புளியங்கொட்டை மணல் வறுவல், தோல் நீக்குதல், நெசவுப் பசை காய்ச்சுதல் மற்றும் பஞ்சகால உணவுப் பதப்படுத்துதல்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "palai",
        "summary_en": "Thermal and aqueous processing of hard tamarind seeds (puliyankottai): roasting in hot river sand to exfoliate the astringent condensed-tannin seed coat (testa), stone-grinding the white cotyledons into sizing flour, and prolonged water-and-wood-ash leaching to detoxify seeds into high-protein famine cakes during monsoon failures.",
        "summary_ta": "புளியங்கொட்டையை ஆற்று மணலில் வறுத்துத் துவர்ப்புத் தோலை நீக்கி, மாவாக்கி நெசவுப் பசை தயாரிக்கும் முறையும், வறட்சிக் காலங்களில் சாம்பல் நீரில் ஊறவைத்துத் துவர்ப்பு நீக்கிப் புளியங்கொட்டை அடையாகச் சமைக்கும் நுட்பமும்.",
        "sources": [
            "Famine Foods and Wild Edible Plants of South India",
            "Traditional Textile Sizing & Finishing Manuals of Tamil Nadu",
            "Economic Products of India (Watt: Tamarindus indica)"
        ],
        "content": "# Puliyankottai Sand-Roasting, Testa Decortication & Famine-Flour Leaching\n\nThe glossy dark-brown seed coat (*testa*) of *Tamarindus indica* comprises $30\\%$ of the seed weight and is saturated with astringent proanthocyanidin tannins and phlobaphenes that must be completely separated from the creamy white endosperm before craft or dietary use:\n\n**1. Thermal Sand-Roasting & Decortication (*Tholi-Neekkuthal*):**\n- Seeds are agitated in wide earthen or iron pans (*vaanali*) filled with hot quartz river sand at $140\\text{--}160^\\circ\\text{C}$. Differential thermal expansion between the moisture-retaining cotyledon and the dry outer testa causes the brown shell to blister and crack with a sharp popping sound.\n- Poured onto a stone floor and pounded lightly in a wooden mortar (*ural*) followed by winnowing (*muram*), the brittle brown husks fly off, yielding clean ivory split kernels (*paruppu*).\n\n**2. Wet Milling for Loom Sizing & Craft Paste:**\n- Split kernels are pulverized in rotary stone querns (*thiruvai*) and simmered with water and trace copper sulfate or neem leaf extract into a translucent, stringy sizing gel (*kanji*).\n\n**3. Drought Famine Detoxification (*Panjakala Unavu*):**\n- During historical *Palai* droughts and monsoon failures, rural families soaked roasted split kernels in changes of running stream water and mild wood-ash water for 48 hours to leach residual tannins, then wet-ground the mash with millet flour and palm jaggery into nutritious *puliyankottai-adai* cakes ($18\\text{--}20\\%$ protein)."
    },
    {
        "slug": "artifact-puli-thattum-kattai-mallets-granite-kottai-kallu-anvils-and-pazhampuli-jaadi",
        "category": "artifact",
        "file": "artifact-puli-thattum-kattai-mallets-granite-kottai-kallu-anvils-and-pazhampuli-jaadi.md",
        "name_en": "Puli-Thattum-Kattai Wooden Mallets, Granite Kottai-Kallu Anvils & Pazhampuli Earthenware Vats",
        "name_ta": "புளி தட்டும் மரக்கட்டைகள், கொட்டை தட்டும் கருங்கல் பட்டறைகள் மற்றும் பழம்புளிச் சால்கள்",
        "era": "Early Medieval to Modern Era",
        "year_start": 600,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Material culture and specialized implement typology of Tamil tamarind processing and multi-year storage: dense cross-grained tamarind-wood mallets (kottai-thattum-kattai), oil-seasoned granite deseeding blocks (kottai-kallu), palmyra leaf storage baskets (puli-koodai), and thick-walled terracotta curing jars (pazhampuli-sal / jaadi).",
        "summary_ta": "புளி பதப்படுத்தும் களத்தில் பயன்படும் வைரம்பாய்ந்த புளியமரக் குழவிகள், எண்ணெய் தடவிய கருங்கல் பட்டறைகள், பனையோலைக் கூடைகள் மற்றும் பல ஆண்டுகள் புளியைப் பாதுகாக்கும் தடித்த மண் சால்கள்.",
        "sources": [
            "Material Culture of Rural Tamil Households",
            "Traditional Pottery and Storage Vessels of Madurai & Kongu",
            "Agricultural Implements of South India"
        ],
        "content": "# Puli-Thattum-Kattai Mallets, Granite Kottai-Kallu Anvils & Pazhampuli Vats\n\nEvery stage of transforming raw tamarind pods into long-keeping culinary cakes relies on purpose-built wooden, stone, and ceramic implements:\n\n**Implement & Vessel Inventory:**\n- **Odu-Thattum-Kattai & Kottai-Thattum-Kuzhavi**: Two distinct wooden beaters are used in tandem—a lightweight, flat-faced paddle of *veppamaram* (neem) for shattering the fragile outer shell without bruising the pulp, and a short, heavy, cylindrical club carved from seasoned interlocking-grain *puliyamaram* (tamarind heartwood) or *karuvelam* (*Acacia nilotica*) for striking out the seeds.\n- **Puli-Kottai-Kallu (Granite Deseeding Anvil)**: A flat-topped, dress-chiseled charnockite or granite block ($30 \\times 30 \\times 15\\text{ cm}$) set flush into the courtyard floor. Seasoned repeatedly with castor oil (*amanakku-ennai*), its micro-pitted surface grips the sticky pod while allowing the flattened pulp to peel off intact after the seed is ejected.\n- **Pazhampuli-Sal & Mann-Panai (Curing Vats)**: Because $d$-tartaric acid corrodes copper, brass, and unglazed iron, aged *pazhampuli* is packed strictly in thick-walled, low-porosity fired terracotta urns (*sal* or *ப்பானை*) or stoneware jars (*jaadi*) sealed at the neck with salt-impregnated cotton cloth and clay lute."
    },
    {
        "slug": "artifact-puli-adai-compressed-cakes-puliyankottai-sizing-cakes-and-pallanguzhi-counters",
        "category": "artifact",
        "file": "artifact-puli-adai-compressed-cakes-puliyankottai-sizing-cakes-and-pallanguzhi-counters.md",
        "name_en": "Puli-Adai Compressed Cakes, Puliyankottai Sizing Blocks, Blacksmith Charcoal & Seed Counters",
        "name_ta": "புளி அடை வட்டுகள், புளியங்கொட்டை மாவுக் கட்டிகள், கொல்லுலைப் புளியந்தழல் மற்றும் பல்லாங்குழி விதைகள்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Multi-product commodity outputs of the Tamil tamarind economy: sun-cured ring-shaped salted tamarind cakes (puli-adai / chakkai), high-calorific tamarind heartwood smithing charcoal (puliyanthazhal), decorticated seed-starch blocks, and metrologically uniform glossy seeds used as Pallanguzhi game counters.",
        "summary_ta": "புளியமரத்திலிருந்து பெறப்படும் வணிகப் பொருட்கள்: உப்பிட்டுத் தட்டிய வட்டப் புளி அடைகள், அதிக வெப்பம் தரும் கொல்லுலைப் புளியங்கரி (புளியந்தழல்), நெசவுப் பசைக் கட்டிகள் மற்றும் பல்லாங்குழி ஆட்டக் காய்கள்.",
        "sources": [
            "Commercial Products of Madras Presidency",
            "Traditional Metallurgy & Forge Fuels of Tamil Nadu",
            "Ethnobotany of Tamarindus indica in South India"
        ],
        "content": "# Puli-Adai Compressed Cakes, Blacksmith Charcoal & Seed Counters\n\nIn traditional Tamil material culture, zero waste leaves the tamarind processing yard—every fraction of fruit, seed, shell, and timber yields a standardized trade artifact:\n\n**Commodity Typology:**\n1. **Puli-Adai / Chakkai (Compressed Salted Discs)**: Deseeded, fiber-free pulp is kneaded with $5\\text{--}8\\%$ sea salt, hand-compacted with wooden paddles into circular flat cakes or hollow-centered rings (often weighed in traditional *vissai* and *thookku* units), sun-glazed to seal the surface, and stacked inside palmyra-leaf crates (*olai-ப்பாய்*) for wholesale transport.\n2. **Puliyanthazhal (High-Density Forge Charcoal)**: Senescent tamarind trees possess ultra-dense, silica-rich heartwood ($\\rho \\approx 950\\text{--}1100\\text{ kg/m}^3$). Carbonized in earth-covered pit kilns, *puliyankari* burns with intense, spark-free radiant heat (*puliyanthazhal*) prized by Tamil blacksmiths (*kollan*) and goldsmiths (*thattan*) for crucible smelting and forging steel edges.\n3. **Pallanguzhi Counters & Metrological Seeds**: Whole, uncracked glossy brown *puliyankottai* seeds—impervious to insects and smooth to the touch—serve across Tamil Nadu as the canonical counting seeds for the 14-cup *Pallanguzhi* board game and elementary arithmetic drills."
    },
    {
        "slug": "institution-saalai-puli-maram-avenue-endowments-and-marap-puli-vari-tree-tax-tenures",
        "category": "institution",
        "file": "institution-saalai-puli-maram-avenue-endowments-and-marap-puli-vari-tree-tax-tenures.md",
        "name_en": "Saalai-Puli-Maram Highway Shade Endowments, Puli-Vari Tree Taxes & Village Kuthagai Auctions",
        "name_ta": "சாலைப் புளியமர தர்ம அறக்கட்டளைகள், புளிவரி மர வரி மற்றும் ஊர்ப் பொது ஏலக் குத்தகை முறை",
        "era": "Medieval to Modern Era",
        "year_start": 800,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Agrarian and civic institutions governing tamarind trees in Tamil Nadu: medieval stone inscriptions recording marap-padai and puli-vari tree taxes, charitable planting of wayside tamarind avenues (saalai-puli-maram) by rulers and chathiram endowments, and annual village assembly auctions of usufruct harvest rights (puli-kuthagai).",
        "summary_ta": "சோழர், பாண்டியர் மற்றும் நாயக்கர் காலக் கல்வெட்டுகளில் குறிப்பிடப்படும் புளிவரி (மர வரி), நெடுஞ்சாலைகளில் நிழலுக்காக நடப்பட்ட சாலைப் புளியமர அறக்கட்டளைகள் மற்றும் ஊர் ஏரி பராமரிப்புக்கான புளி ஏலக் குத்தகை முறை.",
        "sources": [
            "South Indian Inscriptions (Epigraphia Indica: Tree Tax & Avenue Grants)",
            "Thanjavur Maratha & Nayak Chathiram Endowment Records",
            "Customary Commons Tenure in Tamil Villages"
        ],
        "content": "# Saalai-Puli-Maram Avenue Endowments & Puli-Vari Tree-Tax Tenures\n\nBecause a single *Tamarindus indica* tree thrives in semi-arid soil without irrigation and yields $150\\text{--}400\\text{ kg}$ of pods annually for over two centuries, Tamil fiscal and civic institutions treated mature tamarind trees as permanent revenue-bearing real estate (*marak-kani*):\n\n**1. Epigraphic Tree-Tax Tenures (*Puli-Vari / Marap-Padai*):**\n- Chola, Pandya, and Vijayanagara-Nayak copper plates and temple inscriptions distinguish ownership of soil (*nilam*) from usufruct rights over fruit trees (*maram*). Specific imposts such as *puli-vari* (tamarind tree tax) and *marap-padai* were assessed per bearing tree and frequently gifted (*devadana* / *brahmadeya*) to fund temple perpetual lamps or feeding halls.\n\n**2. Charitable Highway Avenues (*Saalai-Puli-Maram*):**\n- Planting continuous double rows of wide-canopied tamarind trees along trunk trade routes was revered as one of the seven permanent charitable works (*saptha-santhanam*). Queen Mangammal's avenues across the Madurai–Tirunelveli highways and the Thanjavur *Chathiram* roads cooled foot travelers and bullock carts while buffering monsoon winds.\n\n**3. Communal Harvest Auctions (*Puli-Kuthagai*):**\n- In *ur* and *panchayat* commons along tank bunds (*eri-karai*) and roadsides, trees are numbered and auctioned annually in *Thai–Masi*; proceeds directly finance tank desilting (*kudimaramathu*) and village festivals."
    },
    {
        "slug": "place-usilampatti-ancient-madurai-tamarind-grove-and-puli-processing-haven",
        "category": "place",
        "file": "place-usilampatti-ancient-madurai-tamarind-grove-and-puli-processing-haven.md",
        "name_en": "Usilampatti: Ancient Madurai Dryland Tamarind Grove Belt & Puli Processing Haven",
        "name_ta": "உசிலம்பட்டி - மதுரை மேற்குக் கணவாய் வறட்சித் தாங்கும் புளியந்தோப்புகள் மற்றும் புளி பதப்படுத்தும் தளம்",
        "era": "Early Medieval to Modern Era",
        "year_start": 700,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Historic agroforestry and dryland trade hub in the rain-shadow valley west of Madurai (lat 9.9650, lng 77.7880, thinai: mullai), renowned for its extensive centuries-old tamarind groves (puliyanthoppu), acid-rich deep-crimson pulp cultivars, household granite-anvil deseeding yards, and regional tamarind wholesale markets.",
        "summary_ta": "மதுரை மாவட்டத்தின் மேற்குப் பகுதியில் அமைந்துள்ள உசிலம்பட்டி (lat 9.9650, lng 77.7880, முல்லைத் திணை): நூற்றாண்டுகள் பழமையான புளியந்தோப்புகள், அடர் சிவப்புப் புளி இரகங்கள் மற்றும் கொட்டை தட்டும் களங்கள் நிறைந்த வரலாற்றுத் தளம்.",
        "sources": [
            "Madurai District Gazetteer (W. Francis)",
            "Agroforestry Systems of Southern Tamil Nadu Drylands",
            "Agricultural Marketing Survey of Madurai & Theni Tamarind Belt"
        ],
        "content": "# Usilampatti: Ancient Madurai Dryland Tamarind Grove & Puli Processing Haven\n\nLocated at `lat 9.9650, lng 77.7880` in the rain-shadow *Mullai–Palai* ecotone west of the Nagamalai hills in Madurai district (flanked by the Andipatti pass and Sedapatti drylands), Usilampatti is one of southern Tamil Nadu's premier historical centers for tamarind orchard agroforestry and artisanal pod processing:\n\n**Ecological & Craft Distinction:**\n- **Calcareous Red-Loam Terroir**: The semi-arid gravelly red and black calcareous soils around Usilampatti, Elumalai, and Sedapatti—receiving warm dry winds funneling through the Cumbum–Andipatti gap during *Masi–Panguni*—produce thick-fleshed tamarind pods with high $d$-tartaric acid concentration ($>15\\%$), low moisture content, and rich reddish-brown anthocyanin pigmentation (*Nattu-Puli*).\n- **Household Deseeding Yards (*Puli-Kalam*)**: Across Usilampatti and its surrounding *patti* hamlets, thousands of rural women operate seasonal courtyard processing lines fitted with oil-seasoned granite anvils (*kottai-kallu*) and wooden mallets, grading fiber-free *poovarasu-ilai* and ring-shaped *puli-adai* cakes as well as clean *puliyankottai* seed kernels for textile and culinary markets across Tamil Nadu and Kerala."
    }
]

EDGES = [
    [
        "text-sangam-literature-on-puli-tamarind-broths-puli-choru-and-arid-zone-cuisine",
        "describes",
        "artifact-puli-adai-compressed-cakes-puliyankottai-sizing-cakes-and-pallanguzhi-counters",
        "material_culture",
        "Sangam to Modern Era",
        "Purananuru, Akananuru, and Perumpanarruppadai document the culinary preservation of cured tamarind pulp for stews and travel rations.",
        "Purananuru & Akananuru"
    ],
    [
        "concept-tamarind-d-tartaric-acid-biochemistry-and-pazhampuli-maillard-aging",
        "explains",
        "artifact-puli-thattum-kattai-mallets-granite-kottai-kallu-anvils-and-pazhampuli-jaadi",
        "material_culture",
        "Sangam to Modern Era",
        "High d-tartaric acid concentration and Maillard browning during 1-to-3-year salt curing necessitate non-reactive terracotta pazhampuli-jaadi vats.",
        "Siddha Gunapadam"
    ],
    [
        "concept-puliyankottai-xyloglucan-seed-polysaccharide-rheology-and-binding-chemistry",
        "underpins",
        "technology-puliyankottai-roasting-wet-milling-warp-sizing-and-famine-flour-leaching",
        "material_culture",
        "Early Medieval to Modern Era",
        "The branched xyloglucan biopolymer inside tamarind cotyledons governs sand-roasting decortication and boiling into handloom warp-sizing paste.",
        "Textile Research Monographs"
    ],
    [
        "concept-tamarind-tartrate-copper-oxide-chelation-and-bronze-icon-acid-pickling",
        "utilizes",
        "artifact-puli-adai-compressed-cakes-puliyankottai-sizing-cakes-and-pallanguzhi-counters",
        "material_culture",
        "Sangam to Modern Era",
        "Salted tamarind pulp cakes provide the tartaric acid and chloride ligands needed to chelate copper oxide tarnish from bronze icons and vessels.",
        "Archaeometallurgy Studies"
    ],
    [
        "technology-puli-ulaithal-harvesting-shell-cracking-and-stone-anvil-seed-decortication",
        "employs",
        "artifact-puli-thattum-kattai-mallets-granite-kottai-kallu-anvils-and-pazhampuli-jaadi",
        "material_culture",
        "Early Medieval to Modern Era",
        "Post-harvest shell cracking and seed ejection rely on wooden beaters (odu-thattum-kattai) and oiled granite anvils (puli-kottai-kallu).",
        "Madurai District Gazetteer"
    ],
    [
        "technology-puli-ulaithal-harvesting-shell-cracking-and-stone-anvil-seed-decortication",
        "produces",
        "artifact-puli-adai-compressed-cakes-puliyankottai-sizing-cakes-and-pallanguzhi-counters",
        "material_culture",
        "Sangam to Modern Era",
        "Deseeding and fiber stripping yield both compressed salted puli-adai cakes and whole glossy puliyankottai seeds.",
        "Madras Presidency Manuals"
    ],
    [
        "technology-puliyankottai-roasting-wet-milling-warp-sizing-and-famine-flour-leaching",
        "processes",
        "artifact-puli-adai-compressed-cakes-puliyankottai-sizing-cakes-and-pallanguzhi-counters",
        "material_culture",
        "Sangam to Modern Era",
        "Sand-roasting and stone-milling convert raw tamarind seeds into textile sizing blocks and leached drought-famine flour.",
        "Economic Products of India"
    ],
    [
        "institution-saalai-puli-maram-avenue-endowments-and-marap-puli-vari-tree-tax-tenures",
        "governs",
        "technology-puli-ulaithal-harvesting-shell-cracking-and-stone-anvil-seed-decortication",
        "material_culture",
        "Medieval to Modern Era",
        "Annual village puli-kuthagai auctions and tree-tax charters regulate seasonal canopy harvesting along wayside avenues and tank bunds.",
        "South Indian Inscriptions"
    ],
    [
        "institution-saalai-puli-maram-avenue-endowments-and-marap-puli-vari-tree-tax-tenures",
        "operates_in",
        "place-usilampatti-ancient-madurai-tamarind-grove-and-puli-processing-haven",
        "material_culture",
        "Early Medieval to Modern Era",
        "Dryland orchard tenures and highway tamarind avenues anchor the seasonal harvesting economy of the Usilampatti–Madurai belt.",
        "Madurai District Gazetteer"
    ],
    [
        "place-usilampatti-ancient-madurai-tamarind-grove-and-puli-processing-haven",
        "supplies",
        "artifact-puli-adai-compressed-cakes-puliyankottai-sizing-cakes-and-pallanguzhi-counters",
        "material_culture",
        "Early Medieval to Modern Era",
        "Usilampatti processing yards export graded puli-adai cakes, decorticated seed kernels, and tamarind charcoal across South India.",
        "Agricultural Marketing Survey"
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
