#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Scent Distillation, Attar Extraction & Temple Aromatics
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
        "file": "knowledge/texts/text-silappadikaram-verses-on-perfume-bazaars-fragrant-pastes-and-aromatics.md",
        "slug": "text-silappadikaram-verses-on-perfume-bazaars-fragrant-pastes-and-aromatics",
        "category": "text",
        "name_en": "Silappadikaram: Epic Verses on Ancient Perfume Bazaars, Fragrant Pastes & Royal Attars",
        "name_ta": "சிலப்பதிகாரம் - நறுமணப் பொருள் அங்காடி, சந்தனக் குழம்பு, வாசனைக் கூட்டுகள் மற்றும் வாசனைப் பாடல்",
        "era": "Post-Sangam Era",
        "year_start": 200,
        "year_end": 500,
        "thinai": "marutham",
        "summary_en": "Ilango Adigal's classical descriptions in Silappadikaram (Puhar and Madurai Kandams) detailing bustling aromatic bazaars selling red sandalwood pastes, crushed camphor, and distilled floral extracts.",
        "summary_ta": "இளங்கோவடிகள் சிலப்பதிகாரத்தில் விவரிக்கும் நறுமண அங்காடித் தெருக்கள், செஞ்சந்தனம், கத்தூரி, அகில் மற்றும் பன்னீர் வாசனைத் திரவியங்களின் சிறப்புகள்.",
        "sources": [
            "Silappadikaram 5:15-30",
            "Silappadikaram 14:75-95",
            "Manimekalai 3"
        ],
        "content": "# Silappadikaram: Perfume Bazaars & Royal Aromatics\n\nIn *Silappadikaram* (Canto 5 and Canto 14), Ilango Adigal opens a sensory window into the aromatic luxuries of ancient Tamil urban life:\n\n> \"In the bustling street of the perfumers (*narum-chuvai-seri*), traders weighed out cooling white sandalwood (*ven-santhanam*) brought from the southern Podhigai hills, aromatic eaglewood (*akil*) gathered from western cliffs, fine camphor (*karpooram*), and fragrant floral oils distilled in copper vessels... Noble citizens anointed their bodies with spiced unguents (*kootu-kalavai*) that filled the morning air with divine fragrance.\"\n\nThis epic testimony confirms that scent manufacturing and perfumery was an advanced bio-chemical trade operating alongside textile, metallurgical, and maritime guild institutions."
    },
    {
        "file": "knowledge/concepts/concept-vasanai-thailam-hydro-distillation-and-essential-oil-volatilization-physics.md",
        "slug": "concept-vasanai-thailam-hydro-distillation-and-essential-oil-volatilization-physics",
        "category": "concept",
        "name_en": "Vasanai-Thailam: Steam Hydro-Distillation, Volatilization Kinetics & Essential Oil Extraction",
        "name_ta": "வாசனைத் தைலம் - நீராவிக் காய்ச்சி வடித்தல், நறுமண மூலக்கூறு ஆவியாதல் மற்றும் அத்தியாவசிய எண்ணெய் பிரித்தெடுத்தல்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "mullai",
        "summary_en": "Thermodynamics and physical chemistry of water-steam hydro-distillation of floral petals and aromatic woods, capturing delicate volatile monoterpenes and sesquiterpenes into cool condensed fractions.",
        "summary_ta": "பூவிதழ்கள் மற்றும் நறுமண மரங்களை நீராவியால் காய்ச்சி வடித்து, வாசனைக் கூறுகளைக் குளிர்ந்த நீரில் படியவைத்து அத்தர் மற்றும் தைலம் பிரித்தெடுக்கும் வெப்ப வேதியியல்.",
        "sources": [
            "Indian Perfumery and Essential Oil Monographs",
            "Siddha Pharmacopoeia on Thailams",
            "Traditional Attar Manufacture in South India"
        ],
        "content": "# Vasanai-Thailam: Hydro-Distillation & Essential Oils\n\nAncient Tamil perfumers (*sugandha-kaara*) harnessed principles of vapor pressure and steam co-distillation:\n\n- **Steam Volatilization**: Many delicate floral scent molecules (such as linalool, geraniol, and phenylethyl alcohol) decompose if heated directly past 100°C. By boiling aromatic plant material submerged in water, steam vapors carry volatile organic aromatics at temperatures below their individual boiling points.\n- **Condensation Immiscibility**: As the steam-vapor mixture traveled through bamboo or copper conduits immersed in cold water baths, the essential oils condensed alongside water. Because essential oils are hydrophobic and less dense than water, they floated to the surface as an oily film (*thailam*).\n- **Separation**: Master perfumers skimmed the concentrated fragrant oil layer using goose feathers or silver ladles, yielding pure attar essences."
    },
    {
        "file": "knowledge/technologies/technology-dega-and-bapka-terracotta-retort-steam-distillation-pyrotechnics.md",
        "slug": "technology-dega-and-bapka-terracotta-retort-steam-distillation-pyrotechnics",
        "category": "technology",
        "name_en": "Dega & Bapka: Terracotta Retort Distillation Stills, Bamboo Conduits & Water Condensers",
        "name_ta": "தேகா மற்றும் பாப்கா - சுடுமண் காய்ச்சி வடிக்கும் உலை, மூங்கில் நீராவிக்குழாய் மற்றும் குளிர்விப்புத் தொட்டி",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "mullai",
        "summary_en": "Pyrotechnic setup consisting of heavy terracotta distillation cauldrons (dega), angled bamboo delivery pipes (chonga), and copper receiving receivers (bapka) submerged in circulating cold water tanks.",
        "summary_ta": "சுடுமண் பானையில் பூக்களை வேகவைத்து, மூங்கில் குழாய் வழியே நீராவியைச் செலுத்தி, குளிர்ந்த நீர் தொட்டியில் வைக்கப்பட்ட செப்புப் பாத்திரத்தில் அத்தரைச் சேர்க்கும் வடி உலை.",
        "sources": [
            "Archaeometallurgy and Ceramic Retorts at Kodumanal",
            "Ancient Indian Distillation Equipment Catalogs",
            "Forbes: A Short History of the Art of Distillation"
        ],
        "content": "# Dega & Bapka: Terracotta Retort Distillation Apparatus\n\nThe traditional distillation still comprised three harmonized components:\n\n- **The Still Cauldrons (*Dega*)**: Large, globular earthenware or copper pots were charged with fresh fragrant blossoms (jasmine, screw pine, rose) and spring water. The rim was sealed airtight with an inverted pottery lid plastered with wet clay and cotton strips (*sandhi-bandhana*).\n- **The Transfer Conduit (*Chonga*)**: A hollow bamboo pipe wrapped in wet twine linked the still head to the receiver, inclined at an angle to direct vapors smoothly downward.\n- **The Receiver Receiver (*Bapka*)**: A long-necked copper flask containing pure sandalwood oil as a base was submerged inside an open water trough. The incoming hot vapors condensed into the cool oil, which greedily absorbed and chemically fixed the floral aromatics."
    },
    {
        "file": "knowledge/artifacts/artifact-chandana-kallu-and-urundai-sandalwood-grinding-slabs-and-perfume-flacons.md",
        "slug": "artifact-chandana-kallu-and-urundai-sandalwood-grinding-slabs-and-perfume-flacons",
        "category": "artifact",
        "name_en": "Chandana-Kallu & Chimizh: Granite Sandalwood Grinding Slabs, Perfume Flacons & Unguent Mortars",
        "name_ta": "சந்தனக் கல் மற்றும் குமிழி - கருங்கல் சந்தன உரைப்புப் பலகை, வாசனைத் தைலக் குப்பி மற்றும் களிம்புச் சிமிழ்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 1800,
        "thinai": "kurinji",
        "summary_en": "Circular fine-grained granite grinding slabs (chandana-kallu) used to friction-abrade fragrant heartwood sticks with rosewater, accompanied by carved steatite and ivory perfume containers (chimizh).",
        "summary_ta": "சந்தன மரக்கட்டையைத் தண்ணீருடன் உரைத்து பசையாக்கும் நுண்ணிய கருங்கல் பலகை மற்றும் மூலிகைத் தைலங்களை அடைத்து வைக்கும் தந்தம் மற்றும் கல் சிமிழ்கள்.",
        "sources": [
            "Nedunalvadai 50-65",
            "Keezhadi Soapstone and Ivory Artifacts",
            "Government Museum Chennai Stone Collections"
        ],
        "content": "# Chandana-Kallu & Chimizh: Grinding Slabs & Perfume Flacons\n\nPreparing fragrant body unguents required precision stone friction implements:\n\n- **The Sandalwood Slab (*Chandana-Kallu*)**: Circular, disk-shaped slabs sculpted from fine-grained black granite or porphyritic gneiss, featuring a gently convex upper surface and a perimeter drainage trough (*neer-vazhi*). Seasoned heartwood billets of *Santalum album* were moistened and rubbed in circular motions, producing an ultra-fine, silky aromatic paste (*sandhana-kuzhambu*).\n- **Unguent Mortars (*Kalvam*)**: Boat-shaped hardstone mortars used by apothecaries to triturate camphor, civet, and saffron threads into homogeneous cosmetic pomades.\n- **Perfume Flacons (*Chimizh*)**: Sealed flasks carved from steatite (soapstone), rock crystal, and ivory, preserving volatile aromatic essences from evaporating in tropical heat."
    },
    {
        "file": "knowledge/concepts/concept-sugandha-thiraviyam-sesame-oil-enfleurage-and-lipid-aroma-fixation.md",
        "slug": "concept-sugandha-thiraviyam-sesame-oil-enfleurage-and-lipid-aroma-fixation",
        "category": "concept",
        "name_en": "Enfleurage: Lipid Aroma Absorption, Cold Sesame Oil Maceration & Fixative Fixation",
        "name_ta": "நறுமணத் தைல ஊறல் - கொழுப்பு வாசனை ஈர்ப்பு, எள்ளெண்ணெய் மலர் ஊறல் மற்றும் நிலைப்படுத்துதல்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 1800,
        "thinai": "mullai",
        "summary_en": "Ancient biochemical extraction method layering fragrant blossoms between beds of de-hulled sesame seeds or cold-pressed gingelly oil, capturing delicate floral perfumes through lipid solubility.",
        "summary_ta": "மல்லிகை, செண்பகப் பூக்களை எள்ளின் மீது அடுக்கி வைத்து, பூக்களின் வாசனையை எள்ளிலுள்ள கொழுப்பு ஈர்த்துக் கொள்ளும் வண்ணம் செய்யப்படும் பண்டைய வாசனை எண்ணெய் முறை.",
        "sources": [
            "Purananuru 329",
            "Brihat Samhita Gandhayukti Chapter",
            "Journal of Ethnopharmacology and Traditional Perfumery"
        ],
        "content": "# Enfleurage: Lipid Absorption & Cold Maceration\n\nLong before solvent extraction existed, Tamil apothecaries harnessed the powerful solvent capacity of natural lipids:\n\n- **The Sesame Seed Bed Technique**: Freshly harvested night-blooming jasmine (*mullai* or *malligai*) was spread in alternating layers with clean, husked sesame seeds (*ellu*). The lipid-rich oil bodies of the seeds absorbed the volatile fragrance exuded by the dying flowers overnight.\n- **Repeated Re-Charging**: Every dawn, spent blossoms were shaken off and replaced with fresh flowers. This process was repeated for 15 to 20 consecutive days until the seeds were utterly saturated with floral essential oils.\n- **Cold-Press Expelling**: The fragrant seeds were then gently crushed in stone oil-presses (*chekku*), yielding intensely perfumed sesame oil (*vasanai-ennai*) used as the foundation for royal hair oils and sacred temple anointments."
    },
    {
        "file": "knowledge/institutions/institution-vasanai-thattar-and-sugantha-vanigar-guild-of-perfumers-and-apothecaries.md",
        "slug": "institution-vasanai-thattar-and-sugantha-vanigar-guild-of-perfumers-and-apothecaries",
        "category": "institution",
        "name_en": "Sugantha-Vanigar: Guild of Master Perfumers, Royal Apothecaries & Spice Merchants",
        "name_ta": "சுகந்த வணிகர் மற்றும் வாசனைத் தட்டார் - நறுமணப் பொருள் வணிகர் சங்கம், அரண்மனை வாசனை மருத்துவர்கள்",
        "era": "Iron Age to Medieval Era",
        "year_start": -400,
        "year_end": 1500,
        "thinai": "marutham",
        "summary_en": "Commercial and technical guild of specialized perfumers, incense blenders, and cosmetic apothecaries managing trans-oceanic trade in frankincense, sandalwood, camphor, and temple consecration oils.",
        "summary_ta": "கோயில் திருக்குடமுழுக்கு தைலங்கள், அரச வாசனைத் திரவியங்கள் மற்றும் அத்தர் தயாரிப்பை நிர்வகித்த அதிகாரப்பூர்வ வாசனை வணிகர் மற்றும் தட்டார் சங்கம்.",
        "sources": [
            "Silappadikaram 14",
            "South Indian Inscriptions on Merchant Guilds",
            "Inscriptions of Rajendra Chola I at Gangaikondacholapuram"
        ],
        "content": "# Sugantha-Vanigar: Royal Perfumers & Merchant Guilds\n\nThe production and distribution of prestige aromatics were strictly organized by specialized commercial bodies:\n\n- **Guild Composition**: The *Sugantha-Vanigar* (aromatic merchants) coordinated procurement of high-altitude forest barks (sandalwood from the Western Ghats, cinnamon, eaglewood), coastal ambergris, and imported Arabian myrrh and frankincense.\n- **Sacred Royal Charters**: Inscriptions record temple endowments commissioning guild perfumers to deliver specified weights of pulverized camphor, rosewater, and twelve-ingredient fragrant pastes (*ashtagandha*) daily for ritual deity anointment (*thirumanjanam*).\n- **Hallmarking Purity**: Guild inspectors verified that expensive imported musk (*kasturi*) and saffron (*kumkumappoo*) were free from adulteration with powdered seeds or dye compounds."
    },
    {
        "file": "knowledge/technologies/technology-javvadu-and-punugu-civet-musk-and-herbal-resin-maceration.md",
        "slug": "technology-javvadu-and-punugu-civet-musk-and-herbal-resin-maceration",
        "category": "technology",
        "name_en": "Javvadu & Punugu: Civet Musk Secretion, Herbal Resin Maceration & Powder Compounding",
        "name_ta": "சவ்வாது மற்றும் புனுகு - புனுகுப் பூனை சுரப்பு சேகரிப்பு, மூலிகைப் பிசின் ஊறல் மற்றும் வாசனைப் பொடி தயாரிப்பு",
        "era": "Classical Antiquity to Modern Era",
        "year_start": -300,
        "year_end": 1800,
        "thinai": "kurinji",
        "summary_en": "Technological formulation of traditional dry perfume powders (javvadu) and animal musk fixatives (punugu) harvested ethically from small Indian civets, compounded with pulverized benzoin, vetiver, and sandalwood.",
        "summary_ta": "புனுகுப் பூனைகளின் நறுமணச் சுரப்பு, சாம்பிராணி, வெட்டிவேர் மற்றும் சந்தனப் பொடிகளை இணைத்து, நீண்ட காலம் நறுமணம் வீசும் சவ்வாதுப் பொடி தயாரிக்கும் கலை.",
        "sources": [
            "Siddha Materia Medica on Punugu",
            "Madurai Temple Ritual Catalogs",
            "Ethno-Zoological Studies of South Indian Aromatics"
        ],
        "content": "# Javvadu & Punugu: Civet Musk & Aromatic Formulations\n\nAnimal-derived musks and tree resins acted as indispensable organic fixatives in ancient perfumery:\n\n- **Civet Musk Collection (*Punugu*)**: The glandular perineal secretion of the small Indian civet (*punugu-poonai* / *Viverricula indica*) was harvested by brushing wooden collection cages without harming the creature. The rich macrocyclic ketone (civetone) provided an intoxicating, base-note fixative that anchored fleeting floral perfumes.\n- **Compounding Javvadu Powder**: Pure civet paste was triturated with micro-pulverized white sandalwood, crushed benzoin resin (*sambrani*), dried vetiver root powder (*vettiver*), and nutmeg.\n- **Micro-Encapsulated Fragrance**: The resinous components bound the volatile fragrance molecules, creating a shelf-stable dry cosmetic powder (*javvadu*) that reactivated its intense scent when warmed by human body heat."
    },
    {
        "file": "knowledge/artifacts/artifact-kunkuma-chimizh-and-thazhambu-perfumed-salve-vessels-and-screw-pine-extractors.md",
        "slug": "artifact-kunkuma-chimizh-and-thazhambu-perfumed-salve-vessels-and-screw-pine-extractors",
        "category": "artifact",
        "name_en": "Thazhambu & Chimizh: Screw-Pine Flower Pressings, Gold Vermilion Flasks & Spiced Pastes",
        "name_ta": "தாழம்பூ மற்றும் குங்குமச் சிமிழ் - தாழம்பூ மடல் பிழிதல், பொன் சிமிழ் மற்றும் நறுமணக் குழம்புப் பாண்டம்",
        "era": "Iron Age to Modern Era",
        "year_start": -400,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Fragrant extraction from coastal screw-pine male bracts (thazhambu / Pandanus odorifer) preserved in chased bronze and gold salve boxes (chimizh) for royal cosmetic and wedding rituals.",
        "summary_ta": "நெய்தல் நிலத்து தாழம்பூவின் நறுமணக் கூறுகளைப் பிழிந்தெடுத்து, தங்க மற்றும் வெண்கலக் குங்குமச் சிமிழ்களில் அடைத்துப் பாதுகாக்கும் முறை.",
        "sources": [
            "Natrinai 83",
            "Akananuru 20",
            "Archaeological Metal Vessels from Kaveripoompattinam"
        ],
        "content": "# Thazhambu & Chimizh: Screw-Pine Fragrance & Salve Vessels\n\nThe coastal dunes yielded one of the most intoxicating perfumes in the ancient Tamil olfactory lexicon:\n\n- **The Fragrant Screw-Pine (*Thazhambu*)**: The male inflorescence of the wild coastal pandanus shrub (*Pandanus odorifer*) emits a piercing, exotic honey-sweet scent. Artisans gathered the unopened yellow spathes at night, shredding and pressing them to extract aromatic water (*thazhai-neer*).\n- **Chased Gold Salve Vessels (*Kunkuma-Chimizh*)**: High-status noblewomen kept perfumed saffron and sandalwood unguents in ornate, spherical containers fitted with tight-fitting threaded or friction-latched lids, exquisitely chased with peacocks and lotus motifs.\n- **Cooling Skin Cosmetics**: Applied to the throat and bosom, the paste delivered both cooling thermal relief from coastal heat and long-lasting floral sillage."
    },
    {
        "file": "knowledge/concepts/concept-phyto-terpene-chemistry-of-sandalwood-vetiver-and-champaka.md",
        "slug": "concept-phyto-terpene-chemistry-of-sandalwood-vetiver-and-champaka",
        "category": "concept",
        "name_en": "Terpene Biogenesis: Santalol, Khusimol & Champaka Sesquiterpenes in Tamil Aromatherapy",
        "name_ta": "தாவர வேதியியல் - சாண்டலால், குசிமால், செண்பக மூலக்கூறுகள் மற்றும் சித்த நறுமணவியல்",
        "era": "Prehistoric to Modern Era",
        "year_start": -1000,
        "year_end": 1800,
        "thinai": "kurinji",
        "summary_en": "Phytochemical characterization of alpha-santalol in Podhigai sandalwood, khusimol in wetland vetiver, and aromatic lactones in champaka blossoms, explaining their enduring antimicrobial and relaxing neural properties.",
        "summary_ta": "சந்தனத்திலுள்ள சாண்டலால், வெட்டிவேரிலுள்ள குசிமால் போன்ற மூலக்கூறுகள் தரும் நீடித்த நறுமணம் மற்றும் சித்த மருத்துவ நரம்பு அமைதிப்படுத்தும் நன்மைகள்.",
        "sources": [
            "Phytochemistry of Indian Sandalwood and Vetiver",
            "Siddha Toxicology and Aromatherapy Treatises",
            "Natural Product Radiance Reviews"
        ],
        "content": "# Terpene Biogenesis: Sandalwood, Vetiver & Champaka\n\nThe therapeutic and persistent qualities of traditional Tamil fragrances stem from their complex sesquiterpene chemistry:\n\n- **Alpha- and Beta-Santalol**: Heartwood of *Santalum album* contains up to 90% santalol isomers. These heavy sesquiterpene alcohols have extremely low evaporation rates, functioning as natural fixatives that retard the evaporation of lighter floral top-notes.\n- **Khusimol in Vetiver (*Vettiver*)**: Harvested from the spongy roots of *Chrysopogon zizanioides*, vetiver essential oil contains tricyclic sesquiterpenes (khusimol and vetivone) that impart an earthy, wood-smoke aroma with proven cooling and insect-repelling properties.\n- **Neurological & Antimicrobial Efficacy**: Modern analytical pharmacology confirms what ancient Sangam apothecaries observed: inhaling these sesquiterpenes crosses the blood-brain barrier, triggering GABAergic neural inhibition, soothing mental distress and cleansing atmospheric pathogens."
    },
    {
        "file": "knowledge/places/place-kanniyakumari-ancient-ay-sandalwood-and-perfumery-haven.md",
        "slug": "place-kanniyakumari-ancient-ay-sandalwood-and-perfumery-haven",
        "category": "place",
        "name_en": "Kanniyakumari: Ancient Ay Sandalwood Hills, Fragrant Podhigai Slopes & Perfumery Haven",
        "name_ta": "கன்னியாகுமரி - பண்டைய ஆய் மன்னர் பொதிகை சந்தனக் காடுகள், நறுமணப் பள்ளத்தாக்கு மற்றும் வாசனைத் தளம்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 1800,
        "thinai": "kurinji",
        "summary_en": "The southern tip of peninsular India flanking the sacred Podhigai and Mahendragiri peaks of the ancient Ay kingdom, celebrated for pristine natural sandalwood forests and botanical distillation shrines.",
        "summary_ta": "பொதிகை மலைச்சாரலில் ஆய் மன்னர்கள் ஆண்ட இயற்கை சந்தனக் காடுகள், வாசனை மூலிகைத் தோட்டங்கள் மற்றும் தொன்மையான நறுமணக் கலைத் தளம்.",
        "sources": [
            "Purananuru 127-135 on King Ay Andiran",
            "Silappadikaram Vanchi Kandam",
            "Forest Department Surveys of Podhigai Biosphere"
        ],
        "content": "# Kanniyakumari: Ancient Ay Sandalwood & Perfumery Haven\n\nNestled at the land's end where the Western and Eastern Ghats meet the Indian Ocean, the forested mountains of the Kanniyakumari-Tirunelveli border was the mythical and historical fountainhead of Tamil aromatic culture:\n\n- **The Podhigai Mountain Sanctuary**: Ruled in the Sangam epoch by the philanthropic chieftain *Ay Andiran*, the cloud-draped slopes of Mount Podhigai (*Ay-Kudi*) yielded the world's most fragrant, oil-dense red and white sandalwood (*Podhigai-Chanthanam*), nurtured by the southwest monsoon.\n- **Trans-Oceanic Botanical Haven**: Ancient mariners navigating around Cape Comorin stopped at coastal anchorages to reprovision with prized aromatic resins, vetiver roots, and medicinal spices collected by hill clans (*Kaanikkarar*).\n- **Unbroken Herbal Heritage**: The pristine rainforests of the Mahendragiri and Ashambu ranges remain the premier living gene-bank for classical Siddha aromatic and medicinal flora."
    }
]

EDGES = [
    [
        "text-silappadikaram-verses-on-perfume-bazaars-fragrant-pastes-and-aromatics",
        "DESCRIBES",
        "concept-vasanai-thailam-hydro-distillation-and-essential-oil-volatilization-physics",
        "core",
        "Post-Sangam Era",
        "Silappadikaram verses celebrate fragrant distillations and vibrant perfume bazaars.",
        "Silappadikaram 14:75-95"
    ],
    [
        "concept-vasanai-thailam-hydro-distillation-and-essential-oil-volatilization-physics",
        "OPERATED_VIA",
        "technology-dega-and-bapka-terracotta-retort-steam-distillation-pyrotechnics",
        "core",
        "Iron Age to Modern Era",
        "Hydro-distillation was executed in sealed terracotta retorts with bamboo pipes.",
        "Archaeometallurgy and Ceramic Retorts at Kodumanal"
    ],
    [
        "concept-vasanai-thailam-hydro-distillation-and-essential-oil-volatilization-physics",
        "GROUND_ON",
        "artifact-chandana-kallu-and-urundai-sandalwood-grinding-slabs-and-perfume-flacons",
        "core",
        "Iron Age to Modern Era",
        "Sandalwood billets were ground on granite slabs to blend with distilled essences.",
        "Nedunalvadai 50-65"
    ],
    [
        "concept-sugandha-thiraviyam-sesame-oil-enfleurage-and-lipid-aroma-fixation",
        "COMPLEMENTED",
        "concept-vasanai-thailam-hydro-distillation-and-essential-oil-volatilization-physics",
        "core",
        "Iron Age to Modern Era",
        "Cold lipid enfleurage extracted fragile top-notes that steam distillation destroyed.",
        "Purananuru 329"
    ],
    [
        "concept-vasanai-thailam-hydro-distillation-and-essential-oil-volatilization-physics",
        "COMMERCIALIZED_BY",
        "institution-vasanai-thattar-and-sugantha-vanigar-guild-of-perfumers-and-apothecaries",
        "core",
        "Iron Age to Medieval Era",
        "Sugantha-Vanigar guilds governed procurement, formulation, and quality hallmarking.",
        "Silappadikaram 14"
    ],
    [
        "institution-vasanai-thattar-and-sugantha-vanigar-guild-of-perfumers-and-apothecaries",
        "FORMULATED",
        "technology-javvadu-and-punugu-civet-musk-and-herbal-resin-maceration",
        "core",
        "Classical Antiquity to Modern Era",
        "Guild apothecaries formulated civet-musk fixatives and aromatic javvadu powders.",
        "Siddha Materia Medica on Punugu"
    ],
    [
        "technology-javvadu-and-punugu-civet-musk-and-herbal-resin-maceration",
        "PRESERVED_IN",
        "artifact-kunkuma-chimizh-and-thazhambu-perfumed-salve-vessels-and-screw-pine-extractors",
        "core",
        "Iron Age to Modern Era",
        "Chased gold, bronze, and stone flacons preserved volatile attars and salves.",
        "Natrinai 83"
    ],
    [
        "concept-vasanai-thailam-hydro-distillation-and-essential-oil-volatilization-physics",
        "ANCHORED_IN",
        "concept-phyto-terpene-chemistry-of-sandalwood-vetiver-and-champaka",
        "core",
        "Prehistoric to Modern Era",
        "Sesquiterpene alcohols in sandalwood provided enduring fixative stability.",
        "Phytochemistry of Indian Sandalwood and Vetiver"
    ],
    [
        "institution-vasanai-thattar-and-sugantha-vanigar-guild-of-perfumers-and-apothecaries",
        "HARVESTED_AT",
        "place-kanniyakumari-ancient-ay-sandalwood-and-perfumery-haven",
        "core",
        "Iron Age to Modern Era",
        "Podhigai mountain slopes around Kanniyakumari supplied premier wild sandalwood.",
        "Purananuru 127-135 on King Ay Andiran"
    ],
    [
        "artifact-chandana-kallu-and-urundai-sandalwood-grinding-slabs-and-perfume-flacons",
        "SOURCED_FROM",
        "place-kanniyakumari-ancient-ay-sandalwood-and-perfumery-haven",
        "core",
        "Iron Age to Modern Era",
        "Aromatic heartwoods from Kanniyakumari slopes were processed across temple ateliers.",
        "Forest Department Surveys of Podhigai Biosphere"
    ]
]

def get_bge_embedding(text):
    res = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text})
    if res.status_code != 200:
        raise RuntimeError(f"Embedding failed: {res.text}")
    return res.json()["embedding"]

def main():
    print("Starting Ingestion Batch 37: Ancient Tamil Scent Distillation, Attar Extraction & Temple Aromatics...")
    
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

    print(f"Ingestion Complete for Batch 37 Corpus! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
