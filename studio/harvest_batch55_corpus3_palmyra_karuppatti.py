#!/usr/bin/env python3
"""
Harvester: Batch 55 - Ancient Tamil Palmyra Karuppatti, Padaneer Liming & Panang Kalkandu Crystallization
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
        "slug": "technology-padaneer-seashell-lime-inhibition-open-iron-pan-boiling-and-scum-skimming",
        "file": "technology-padaneer-seashell-lime-inhibition-open-iron-pan-boiling-and-scum-skimming.md",
        "category": "technology",
        "name_en": "Padaneer Seashell-Lime Inhibition, Open Iron-Pan Boiling & Scum Skimming Technology",
        "name_ta": "பதநீர் கிளிஞ்சல் சுண்ணாம்புத் தடுப்பு, திறந்த இரும்புக் கொப்பரைக் காய்ச்சல் மற்றும் அழுக்கு நுரை அகற்றும் தொழில்நுட்பம்",
        "era": "Sangam Era to Modern Era",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "palai",
        "summary_en": "Coastal Pandya-country process of dusting palmyra tapping pots with burnt cockle-shell (kilinjal) lime, pooling the alkaline padaneer at dawn, filtering it through palm-fibre sieves, and boiling it in wide open iron koparai over palm-frond and dried-spathe fires while ladling off the grey proteinaceous scum (azhukku nurai) with perforated coconut-shell skimmers until the syrup reaches the thread stage.",
        "summary_ta": "பனை முட்டிகளில் சுட்ட கிளிஞ்சல் சிப்பிச் சுண்ணாம்பைத் தடவி, விடியற்காலையில் இறக்கிய காரப் பதநீரைப் பனைநார் வடிகட்டியில் வடித்து, பனையோலை மற்றும் பாளைத் தீயில் அகன்ற இரும்புக் கொப்பரையில் காய்ச்சி, துளையிட்ட சிரட்டைக் கரண்டியால் சாம்பல் நிற அழுக்கு நுரையை அகற்றி, கம்பிப் பதம் வரும் வரை பாகாக்கும் பாண்டிய நாட்டுக் கடற்கரைத் தொழில்நுட்பம்.",
        "sources": [
            "Perumpanarruppadai 275-282",
            "Thoothukudi District Gazetteer (1917)",
            "KVIC Palm Products Technical Bulletin"
        ],
        "content": "# Padaneer Seashell-Lime Inhibition, Open Iron-Pan Boiling & Scum Skimming Technology\n\nSweet palmyra sap (**பதநீர் / padaneer**) collected from the bruised spadix of *Borassus flabellifer* begins to ferment within two hours of tropical heat. The Teri-country boilers of the Pandya coast solved this with **burnt cockle-shell lime** (*கிளிஞ்சல் சுண்ணாம்பு*, kilinjal chunnambu) calcined from Gulf of Mannar bivalve middens, then concentrated the stabilized sap in wide open iron pans while skimming its scum by hand.\n\n### 1. Seashell Lime Preparation (*கிளிஞ்சல் நீற்றல்*)\n- Cockle and oyster shells (calcium carbonate, CaCO3) are calcined in palm-trunk pit kilns at 850-900 °C into quicklime (CaO), then slaked with sea-breeze-cooled well water into a fine white paste of calcium hydroxide, Ca(OH)2.\n- Shell lime is preferred over kankar stone lime because it carries almost no iron or clay, so the finished karuppatti does not darken to a muddy black.\n\n### 2. Pot Dusting & Dose Control (*முட்டி சுண்ணாம்பு தடவல்*)\n- Before each evening ascent, the tapper smears roughly 1-2 g of wet shell lime inside every earthen *muttai* pot. This lifts sap pH from a natural 6.8-7.2 to about 8.0-8.5 and keeps wild yeasts and *Zymomonas* dormant overnight.\n- Over-liming produces a bitter, chalky padaneer; master tappers judge the dose by the faint milky cloud the paste makes on the pot wall.\n\n### 3. Filtration & Open Iron-Pan Boiling (*கொப்பரை காய்ச்சல்*)\n- At dawn, 80-120 litres of pooled sap are strained through a loosely woven palm-fibre sieve (*நார் வடிகட்டி*) into a shallow cast-iron *koparai* about 1.2 m across, set over an earthen trench furnace (*அடுப்புக் குழி*) fed with dried fronds, leaf-stalks and spent spadices.\n- A vigorous rolling boil drives off about 85% of the water in 3-4 hours, taking the liquid from 12-15 °Brix to 78-80 °Brix.\n\n### 4. Scum Skimming (*அழுக்கு நுரை அகற்றல்*)\n- As the sap heats, the calcium coagulates soluble proteins, gums and suspended pollen into a grey-brown floating scum.\n- The boiler lifts it off with a perforated coconut-shell skimmer on a long areca handle (*துளைச் சிரட்டை அகப்பை*); a few drops of castor oil or crushed *vendai* (okra) mucilage are sometimes added to make the scum gather in a single raft.\n\n### 5. Endpoint Judgment (*பதம் பார்த்தல்*)\n- The *paagu* (syrup) is ready when a drop dripped into a coconut shell of cold water sets into a brittle ball, or when a stretched drop forms a glassy thread (*கம்பிப் பதம்*) at about 115-118 °C. The pan is then lifted off the fire straight away for molding.\n"
    },
    {
        "slug": "technology-karuppatti-chirattai-molding-and-clay-pot-panang-kalkandu-slow-crystallization",
        "file": "technology-karuppatti-chirattai-molding-and-clay-pot-panang-kalkandu-slow-crystallization.md",
        "category": "technology",
        "name_en": "Karuppatti Chirattai Half-Shell Molding & Clay-Pot Panang Kalkandu Slow Crystallization Technology",
        "name_ta": "கருப்பட்டி சிரட்டை அச்சு வார்ப்பு மற்றும் மண்பானைப் பனங்கற்கண்டு மெதுப் படிகமாக்கல் தொழில்நுட்பம்",
        "era": "Sangam Era to Modern Era",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "palai",
        "summary_en": "Two divergent finishing routes for boiled palmyra syrup: beating thread-stage paagu on a sand bed and pouring it into wetted coconut half-shell (chirattai) molds to set dome-shaped karuppatti cakes, versus seeding a thinner, lower-temperature syrup into porous unglazed earthen pots strung with cotton or palm-fibre threads and burying them in paddy husk for 40-60 days to grow translucent panang kalkandu rock-candy crystals.",
        "summary_ta": "கம்பிப் பதப் பனம்பாகை மணல் படுகையில் கிண்டி, நனைத்த சிரட்டை அச்சுகளில் ஊற்றிக் குவிமாடக் கருப்பட்டியாக்குவதும், அதைவிட நீர்த்த பாகைப் பருத்தி அல்லது பனைநார் இழைகள் கட்டிய மெருகிடாத மண்பானைகளில் ஊற்றி நெல் உமியில் 40-60 நாட்கள் புதைத்து ஒளிபுகும் பனங்கற்கண்டுப் படிகங்களை வளர்ப்பதும் ஆகிய இரு வழிமுறைகள்.",
        "sources": [
            "Siddha Materia Medica (Gunapadam Thathu Jeevam)",
            "KVIC Palm Gur Manual",
            "Udangudi Karuppatti GI Application (2023)"
        ],
        "content": "# Karuppatti Chirattai Half-Shell Molding & Clay-Pot Panang Kalkandu Slow Crystallization Technology\n\nOnce palmyra syrup reaches its endpoint, the Teri boilers send it down one of two very different paths: fast **chirattai molding** into solid *karuppatti* (கருப்பட்டி), or weeks of slow **clay-pot crystallization** into the clear, glassy *panang kalkandu* (பனங்கற்கண்டு) prized by Siddha physicians.\n\n### 1. Sand-Bed Beating (*மணல் படுகை கிண்டல்*)\n- The hot koparai is set on a ring of damp river sand and the syrup is stirred hard with a flat wooden oar for 8-12 minutes. Beating brings in air and sets off mass micro-nucleation, so the paagu turns opaque, pale and plastic.\n\n### 2. Chirattai Half-Shell Molds (*சிரட்டை அச்சு*)\n- Hundreds of cleaned coconut **half-shells** (*சிரட்டை*), 9-11 cm across, are wetted in brine and laid mouth-up in rows on a palm-leaf mat or a bed of sand.\n- The thickened syrup is ladled into each shell. In 15-25 minutes it sets into the classic **dome-shaped karuppatti cake** of about 250-350 g, bearing the fine fibre ridges of the shell on its curved face.\n- The cakes pop out after a sharp tap and are cured in the shade for 2-3 days before stacking.\n\n### 3. Panang Kalkandu Syrup Preparation (*கற்கண்டுப் பாகு*)\n- For rock candy, the sap is boiled to a lower point of 105-108 °C (about 70-72 °Brix) and cleared with a second skimming. It is never beaten, so that no micro-crystals form early.\n\n### 4. Threaded Porous Earthen Pots (*நூல் கட்டிய மண்பானை*)\n- Unglazed, low-fired terracotta pots are strung inside with a lattice of cotton or split palm-fibre threads (*நூல் வலை*) tied across the mouth and sides.\n- The warm syrup is poured in, the mouth is sealed with a clay-plastered palm-leaf lid, and the pots are buried in **paddy husk** (*நெல் உமி*) or a sand pit so they cool very slowly.\n\n### 5. Forty-to-Sixty-Day Crystal Growth & Harvest\n- Over 40-60 days, water seeps out through the pot walls and the syrup becomes supersaturated. Large faceted sucrose crystals grow along the threads and the inner wall.\n- The pot is broken open (*பானை உடைத்தல்*), the leftover dark molasses (*கழிவுப் பாகு*) is drained off to go back into the karuppatti pans, and the crystal clusters are sun-dried and graded by clarity.\n"
    },
    {
        "slug": "artifact-udangudi-karuppatti-coconut-shell-blocks-and-crystalline-panang-kalkandu-clusters",
        "file": "artifact-udangudi-karuppatti-coconut-shell-blocks-and-crystalline-panang-kalkandu-clusters.md",
        "category": "artifact",
        "name_en": "Udangudi Karuppatti Coconut-Shell Dome Blocks & Crystalline Panang Kalkandu Clusters",
        "name_ta": "உடன்குடி கருப்பட்டி சிரட்டைக் குவிமாடக் கட்டிகள் மற்றும் படிகப் பனங்கற்கண்டுக் கொத்துகள்",
        "era": "Medieval Pandya Era to Modern Era",
        "year_start": 600,
        "year_end": 2026,
        "thinai": "palai",
        "summary_en": "Finished trade goods of the Udangudi Teri belt: dense dark-brown hemispherical karuppatti domes bearing coconut-fibre ridges, stacked twenty to a palm-leaf kottan and sold by the kalam, alongside amber-to-water-clear panang kalkandu crystal druses still threaded on cotton strings and graded as mudhal-tharam, irandam-tharam and thool fragments.",
        "summary_ta": "உடன்குடி தேரிப் பகுதியின் விற்பனைப் பொருட்கள்: தேங்காய் நார்க் கோடுகள் பதிந்த அடர் பழுப்பு அரைக்கோளக் கருப்பட்டிக் குவிமாடங்கள், பனையோலைக் கொட்டானில் இருபது இருபதாக அடுக்கி விற்கப்படுபவை; பருத்தி நூலில் கோர்த்த தேன்நிறம் முதல் நீர்த்தெளிவு வரையிலான பனங்கற்கண்டுப் படிகக் கொத்துகள், முதல் தரம், இரண்டாம் தரம், தூள் எனப் பிரிக்கப்பட்டவை.",
        "sources": [
            "Udangudi Karuppatti Geographical Indication Registry",
            "Madras Presidency Trade Returns (1880-1900)",
            "Field Ethnography of Teri Palm Boilers"
        ],
        "content": "# Udangudi Karuppatti Coconut-Shell Dome Blocks & Crystalline Panang Kalkandu Clusters\n\nThe material output of the Udangudi Teri belt comes in two forms that are instantly recognisable in any Tamil bazaar: the matte, dark **chirattai-dome karuppatti** and the glittering **panang kalkandu crystal cluster**.\n\n### 1. Karuppatti Dome Blocks (*சிரட்டைக் கருப்பட்டி*)\n- **Form**: Hemispherical domes 9-11 cm wide and 4-5 cm high, flat on top where the syrup surface met the air and ridged below by the fibrous lining of the coconut shell.\n- **Colour & Fracture**: Deep chocolate to reddish-black. A good block breaks with a crisp, slightly crystalline face that smells of smoke and caramel; a sticky, glossy break means it was under-boiled or over-limed.\n- **Packing**: Twenty domes are stacked in a woven palmyra-leaf basket (*கொட்டான்* / *kudai*), lined with dried palm leaf to soak up moisture, and traded by the *kalam* and *thulam* weights in coastal markets.\n\n### 2. Panang Kalkandu Crystal Clusters (*பனங்கற்கண்டுக் கொத்து*)\n- **Habit**: Interlocking monoclinic sucrose crystals 5-25 mm long, grown as druses along the cotton or palm-fibre threads. Pieces often still have the thread running through the middle.\n- **Grading**: *Mudhal-tharam* (first grade, water-clear to pale amber, large facets), *irandam-tharam* (second grade, honey-coloured, smaller crystals) and *thool* (powdered fragments for Siddha decoctions).\n- **Medicinal Packaging**: Siddha vaidyas kept kalkandu in glazed jars or sealed palm-leaf packets as the carrier sweetener for *lehyam* electuaries, throat lozenges and *kashayam* decoctions.\n\n### 3. Archaeological & Mercantile Traces\n- Broken thread-scarred terracotta crystallizing pots and charred coconut-shell mold dumps are common in the upper layers of Teri dune middens around Udangudi, Kulasekarapattinam and Tiruchendur.\n"
    },
    {
        "slug": "artifact-heavy-cast-iron-boiling-koparai-wooden-stirring-oars-and-palm-leaf-kudai-baskets",
        "file": "artifact-heavy-cast-iron-boiling-koparai-wooden-stirring-oars-and-palm-leaf-kudai-baskets.md",
        "category": "artifact",
        "name_en": "Heavy Cast-Iron Boiling Koparai, Wooden Stirring Oars & Palm-Leaf Kudai Baskets",
        "name_ta": "கனமான வார்ப்பிரும்புக் காய்ச்சும் கொப்பரை, மரத் துடுப்புக் கிண்டிகள் மற்றும் பனையோலைக் குடை கூடைகள்",
        "era": "Medieval Pandya Era to Modern Era",
        "year_start": 600,
        "year_end": 2026,
        "thinai": "palai",
        "summary_en": "The boiling-shed toolkit of a Teri palm-sugar household: a wide shallow cast-iron koparai of 1.0-1.4 m diameter with forged ring handles, set on a clay-lined trench hearth; long paddle-shaped stirring oars (thuduppu) carved from tamarind or palmyra heartwood; perforated coconut-shell scum ladles; and conical palm-leaf kudai baskets used as sap carriers, filter cones and karuppatti storage hampers.",
        "summary_ta": "தேரிப் பனைவெல்லக் குடும்பத்தின் காய்ச்சுக்கூடக் கருவிகள்: களிமண் பூசிய அடுப்புக் குழியின் மீது வைக்கப்படும், அடித்த வளையக் கைப்பிடிகளுடன் 1.0-1.4 மீ விட்டமுள்ள அகன்ற ஆழமற்ற வார்ப்பிரும்புக் கொப்பரை; புளி அல்லது பனை வைரமரத்தில் செதுக்கிய நீண்ட துடுப்புக் கிண்டிகள்; துளையிட்ட சிரட்டை நுரை அகப்பைகள்; பதநீர் சுமக்கவும், வடிகட்டவும், கருப்பட்டி சேமிக்கவும் பயன்படும் கூம்பு வடிவப் பனையோலைக் குடைகள்.",
        "sources": [
            "Thoothukudi District Gazetteer (1917)",
            "Ethnoarchaeology of South Indian Palm Sugar Sheds",
            "Tamil Nadu Palm Products Development Board Records"
        ],
        "content": "# Heavy Cast-Iron Boiling Koparai, Wooden Stirring Oars & Palm-Leaf Kudai Baskets\n\nEach palm-sugar household in the Teri country keeps a thatched boiling shed (*கொட்டகை*). Its heart is the heavy iron pan, with a set of wooden and woven palm-leaf tools gathered around it.\n\n### 1. The Cast-Iron Koparai (*இரும்புக் கொப்பரை*)\n- **Dimensions**: A wide, shallow dish 1.0-1.4 m across and only 18-25 cm deep, cast 8-12 mm thick and weighing 60-110 kg. Its large surface-to-volume ratio is what makes fast evaporation possible.\n- **Ring Handles**: Two to four forged wrought-iron rings (*வளையம்*) riveted to the rim let two men lift the pan off the fire with a pole the moment the syrup reaches its endpoint.\n- **Seasoning**: New pans are seasoned with sesame oil and repeated boils of lime water, which build up a dark iron-calcium film that stops rust from colouring the jaggery.\n\n### 2. Trench Hearth (*அடுப்புக் குழி*)\n- A long trench is dug into the red Teri sand and lined with puddled clay mixed with palm fibre, with a fuel mouth at one end and a chimney slot at the other. Dried fronds, leaf-stalks and spent spadices are the only fuel, so the palm supplies its own fire.\n\n### 3. Wooden Stirring Oars (*மரத் துடுப்பு*)\n- Paddle-shaped oars 1.5-1.8 m long with broad blades, carved from dense **tamarind** (*புளி*) or blackened **palmyra heartwood** (*பனை வைரம்*). They do not scorch or splinter in syrup at 118 °C and are used both for the endless stirring during the boil and for the hard sand-bed beating before molding.\n\n### 4. Perforated Coconut-Shell Skimmers (*துளைச் சிரட்டை அகப்பை*)\n- Half-shells drilled with 20-40 small holes and lashed to areca-stem handles, used to lift the grey calcium-protein scum off the boiling sap.\n\n### 5. Palm-Leaf Kudai Baskets (*பனையோலைக் குடை*)\n- Conical and bowl-shaped containers plaited from young palmyra leaflets. Narrow *kudai* carry padaneer down from the crown and double as filter cones lined with fibre, while larger lidded *kottan* hampers store and ship karuppatti domes and kalkandu clusters.\n"
    },
    {
        "slug": "concept-sucrose-inversion-prevention-by-calcium-hydroxide-and-caramelization-kinetics",
        "file": "concept-sucrose-inversion-prevention-by-calcium-hydroxide-and-caramelization-kinetics.md",
        "category": "concept",
        "name_en": "Sucrose Inversion Prevention by Calcium Hydroxide & Open-Pan Maillard Caramelization Kinetics",
        "name_ta": "கால்சியம் ஹைட்ராக்சைடு மூலம் சுக்ரோஸ் தலைகீழ் மாற்றத் தடுப்பு மற்றும் திறந்த கொப்பரை மையார்ட் கேரமலாக்க இயக்கவியல்",
        "era": "Timeless Scientific Principle",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "palai",
        "summary_en": "Physical chemistry of why limed padaneer crystallizes into karuppatti: alkaline Ca(OH)2 suppresses acid- and invertase-catalysed hydrolysis of sucrose into glucose and fructose, keeping invert sugar below about 5% so the syrup can set, while prolonged open-pan heating above 110 °C drives Amadori rearrangement, Maillard browning between amino acids and reducing sugars, and caramelization into melanoidins, furans and maltol.",
        "summary_ta": "சுண்ணாம்பு சேர்த்த பதநீர் ஏன் கருப்பட்டியாகக் கெட்டிப்படுகிறது என்பதற்கான இயற்பியல் வேதியியல்: காரத்தன்மையுடைய கால்சியம் ஹைட்ராக்சைடு, அமிலம் மற்றும் இன்வர்டேஸ் நொதியால் சுக்ரோஸ் குளுக்கோஸ்-ப்ரக்டோஸாகப் பிரிவதைத் தடுத்து, தலைகீழ்ச் சர்க்கரையை 5%க்குக் கீழ் வைக்கிறது; 110 °Cக்கு மேல் நீண்ட நேரம் திறந்த கொப்பரையில் காய்ச்சுவதால் மையார்ட் பழுப்பாக்கமும் கேரமலாக்கமும் நிகழ்ந்து மெலனாய்டின்கள் உருவாகின்றன.",
        "sources": [
            "Journal of Food Science and Technology: Palm Sap Chemistry",
            "Food Chemistry: Non-Centrifugal Sugar Maillard Profiles",
            "KVIC Palm Gur Manual"
        ],
        "content": "# Sucrose Inversion Prevention by Calcium Hydroxide & Open-Pan Maillard Caramelization Kinetics\n\nFresh palmyra padaneer is a 10-15% sucrose solution full of microbes and enzymes. Whether it turns into a hard karuppatti dome or a runny, unsettable treacle comes down to two competing reactions: **sucrose inversion** and **thermal browning**.\n\n### 1. The Inversion Hazard\n- Sucrose (C12H22O11) is hydrolysed into equal parts glucose and fructose (*invert sugar*) by the yeast enzyme **invertase** (beta-fructofuranosidase) and by hydrogen-ion catalysis once fermentation acids push the pH below about 5.5.\n- Invert sugar is hygroscopic and strongly hinders sucrose crystallization. Sap with more than about 8-10% invert sugar boils down into a sticky treacle that never sets in the chirattai.\n\n### 2. Calcium Hydroxide Alkaline Arrest\n- Shell-lime Ca(OH)2 raises sap pH to 8.0-8.5. In that range acid-catalysed hydrolysis effectively stops, invertase works at under 10% of its optimum, and the acid-tolerant fermenting yeasts and *Zymomonas mobilis* cannot multiply.\n- Calcium ions also bridge pectins and proteins into insoluble flocs. Those flocs are the grey scum skimmed off in the koparai, which clarifies the syrup.\n- With invert sugar kept below about 5% of solids, the syrup can reach the supersaturation needed to crystallize.\n\n### 3. Open-Pan Maillard Browning (*மையார்ட் வினை*)\n- From roughly 100-118 °C, the small amounts of free amino acids in the sap (asparagine, glutamine, GABA) react with whatever reducing sugars are present to form Schiff bases, which go through **Amadori rearrangement** and then polymerize into brown **melanoidins**.\n- The mild alkalinity left by the lime *speeds up* the Maillard reaction while blocking inversion. That is why limed karuppatti comes out darker and more roasted-smelling than unlimed palm syrup.\n\n### 4. Caramelization Kinetics\n- Above about 110 °C, sucrose itself starts to pyrolyse into caramelans, caramelens and caramelins, along with volatile furans, 5-hydroxymethylfurfural (HMF), maltol and diacetyl. Browning follows roughly first-order Arrhenius kinetics, and the rate about doubles for every 10 °C rise.\n- The wide shallow koparai keeps the hottest contact time short, which limits bitter over-caramelization and HMF build-up while still giving the smoky, toffee-like aroma.\n"
    },
    {
        "slug": "concept-polyphenolic-antioxidant-dense-mineral-matrix-and-low-glycemic-nutritional-biochemistry",
        "file": "concept-polyphenolic-antioxidant-dense-mineral-matrix-and-low-glycemic-nutritional-biochemistry.md",
        "category": "concept",
        "name_en": "Polyphenolic Antioxidant-Dense Mineral Matrix & Low-Glycemic Nutritional Biochemistry of Karuppatti",
        "name_ta": "கருப்பட்டியின் பாலிஃபீனால் ஆக்ஸிஜனேற்ற எதிர்ப்பு அடர்த்தியான கனிமச் சேர்க்கை மற்றும் குறைந்த கிளைசெமிக் ஊட்டச்சத்து உயிர்வேதியியல்",
        "era": "Timeless Scientific Principle",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "palai",
        "summary_en": "Nutritional biochemistry of unrefined, non-centrifugal palmyra sugar: because the molasses is never spun off, karuppatti retains phenolic acids (gallic, ferulic, p-coumaric), flavonoids and Maillard melanoidins with measurable DPPH and FRAP antioxidant activity, a mineral matrix rich in potassium, calcium, magnesium, iron and phosphorus, B-group vitamins, and a lower glycemic index (about 35-45) than refined white cane sugar.",
        "summary_ta": "மையவிலக்குச் செய்யப்படாத பனைவெல்லத்தின் ஊட்டச்சத்து உயிர்வேதியியல்: கழிவுப் பாகு பிரிக்கப்படாததால் கருப்பட்டியில் கேலிக், ஃபெருலிக் அமிலங்கள், ஃபிளேவனாய்டுகள், மெலனாய்டின்கள் போன்ற ஆக்ஸிஜனேற்ற எதிர்ப்பிகள், பொட்டாசியம், கால்சியம், மெக்னீசியம், இரும்பு, பாஸ்பரஸ் நிறைந்த கனிமச் சேர்க்கை, பி வைட்டமின்கள் ஆகியவை தங்குகின்றன; வெள்ளைச் சர்க்கரையை விடக் குறைந்த கிளைசெமிக் குறியீடு கொண்டது.",
        "sources": [
            "Siddha Gunapadam: Panai Vellam and Panang Kalkandu",
            "International Journal of Food Properties: Borassus Palm Sugar Composition",
            "National Institute of Nutrition Food Composition Tables"
        ],
        "content": "# Polyphenolic Antioxidant-Dense Mineral Matrix & Low-Glycemic Nutritional Biochemistry of Karuppatti\n\nKaruppatti is a **non-centrifugal sugar (NCS)**. The whole boiled sap sets in the mold, and nothing is spun off in a centrifuge. Everything in the sap except water stays in the block, which is why Siddha *Gunapadam* texts rank *panai vellam* as a medicine rather than just a sweetener.\n\n### 1. Mineral Matrix (*கனிமச் சத்து*)\n- Typical per-100 g values reported for Teri karuppatti: **potassium** 800-1,100 mg, **calcium** 80-160 mg (part of it from the shell-lime dose), **magnesium** 60-110 mg, **phosphorus** 30-60 mg and **iron** 3-11 mg, much of it picked up from the cast-iron koparai.\n- The deep-rooted palmyra pulls these minerals up from the Teri sand aquifers, and they end up as an ash content of 2-3.5%, against below 0.05% in refined white sugar.\n\n### 2. Polyphenolic Antioxidants (*ஆக்ஸிஜனேற்ற எதிர்ப்பிகள்*)\n- Phenolic acids (gallic, protocatechuic, ferulic, p-coumaric), flavonoids such as quercetin and catechin derivatives, and the high-molecular-weight **melanoidins** formed by Maillard browning together give total phenolic contents of 150-450 mg GAE per 100 g.\n- In DPPH radical-scavenging and FRAP ferric-reducing assays, these compounds give karuppatti several times the antioxidant capacity of refined sugar.\n\n### 3. Low-Glycemic Response (*குறைந்த கிளைசெமிக் குறியீடு*)\n- Reported glycemic index values of about 35-45, against 65-68 for refined sucrose, are put down to the polyphenol-mineral matrix slowing intestinal alpha-glucosidase, the presence of soluble fibres and oligosaccharides, and the slow dissolution of a dense crystalline block.\n- Siddha physicians prescribe karuppatti coffee (*கருப்பட்டி காப்பி*) and *panang kalkandu* milk for *pitham* imbalance, postpartum recovery (*பிரசவ லேகியம்*), anaemia and sore throat.\n\n### 4. B-Vitamins & Amino Acids\n- Thiamine, riboflavin, nicotinic acid and pyridoxine survive in trace amounts, along with free amino acids and GABA that carry over from the phloem sap.\n"
    },
    {
        "slug": "concept-supersaturated-pan-cooling-nucleation-and-crystal-lattice-growth-in-porous-earthenware",
        "file": "concept-supersaturated-pan-cooling-nucleation-and-crystal-lattice-growth-in-porous-earthenware.md",
        "category": "concept",
        "name_en": "Supersaturated Syrup Cooling, Heterogeneous Nucleation & Sucrose Crystal Lattice Growth in Porous Earthenware",
        "name_ta": "மிகைச்செறிவுப் பாகு குளிர்வு, பன்முகக் கருவாக்கம் மற்றும் நுண்துளை மண்பானையில் சுக்ரோஸ் படிக அணிக்கோவை வளர்ச்சி",
        "era": "Timeless Scientific Principle",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "palai",
        "summary_en": "Crystallization physics separating karuppatti from panang kalkandu: agitated rapid cooling of highly supersaturated syrup triggers dense primary nucleation and a fine microcrystalline solid, whereas still, slow cooling of moderately supersaturated syrup inside capillary-porous terracotta, with cotton threads as heterogeneous nucleation sites and pot-wall water loss as the supersaturation driver, holds the syrup in the metastable zone where few nuclei grow into large monoclinic sucrose crystals.",
        "summary_ta": "கருப்பட்டியையும் பனங்கற்கண்டையும் வேறுபடுத்தும் படிகமாக்கல் இயற்பியல்: அதிக மிகைச்செறிவுப் பாகைக் கிண்டி விரைவாகக் குளிர்வித்தால் அடர்த்தியான முதன்மைக் கருவாக்கம் நிகழ்ந்து நுண்படிகத் திண்மம் உருவாகிறது; நுண்துளை மண்பானையில் பருத்தி நூல்களைக் கருவாக்கத் தளங்களாகக் கொண்டு அசைவின்றி மெதுவாகக் குளிர்வித்தால், பானைச் சுவர் வழி நீர் இழப்பால் நிலைமாறு மண்டலத்தில் நிற்கும் பாகில் சில கருக்களே பெரிய ஒற்றைச்சாய்வுச் சுக்ரோஸ் படிகங்களாக வளர்கின்றன.",
        "sources": [
            "Mullin: Crystallization (Butterworth-Heinemann)",
            "Journal of Crystal Growth: Sucrose Growth Kinetics",
            "Ethnoarchaeology of Terracotta Crystallizing Vessels"
        ],
        "content": "# Supersaturated Syrup Cooling, Heterogeneous Nucleation & Sucrose Crystal Lattice Growth in Porous Earthenware\n\nThe same palmyra syrup can give an opaque, crumbly karuppatti dome or a glass-clear kalkandu crystal. The difference lies in how its **supersaturation** is handled as it cools.\n\n### 1. Solubility Curve & the Metastable Zone\n- Sucrose solubility drops from about 4.9 g/g water at 100 °C to about 2.0 g/g at 25 °C. Cooling a saturated syrup therefore builds supersaturation (S = C / C*).\n- Between S of about 1.0 and 1.2-1.3 lies the **metastable zone**: crystals that already exist keep growing, but almost no new nuclei form. Above it, the **labile zone** produces sudden, runaway primary nucleation.\n\n### 2. Karuppatti: Labile-Zone Shock Nucleation\n- Thread-stage syrup at 78-80 °Brix is beaten on the sand bed while it cools. The violent shearing pushes it deep into the labile zone and seeds millions of micro-nuclei.\n- Growth gets split among so many crystals that each stays at 10-50 micrometres. The trapped molasses fills the spaces between them, giving the opaque, fine-grained structure of a chirattai dome.\n\n### 3. Kalkandu: Metastable-Zone Slow Growth (*மெதுப் படிகமாக்கல்*)\n- The thinner syrup (70-72 °Brix) is poured without stirring into **porous unglazed terracotta**. A paddy-husk burial slows cooling to well under 1 °C per hour, which keeps the syrup in the metastable zone for weeks.\n- **Heterogeneous nucleation**: Cotton or palm-fibre threads and the rough clay wall lower the free-energy barrier for forming a nucleus. Crystals start only on those surfaces and not throughout the liquid, which is why the finished clusters hang on the threads.\n- **Capillary dehydration**: Water slowly wicks through the open pores of the pot (15-25% porosity) and evaporates from the outer surface. This keeps supersaturation gently topped up as sucrose leaves the solution for the crystals.\n\n### 4. Lattice Growth & Purity\n- Sucrose crystallizes in the **monoclinic P2(1)** space group. Slow, layer-by-layer growth from step edges and screw dislocations pushes impurities (salts, polyphenols, invert sugar) out into the mother liquor, which is why kalkandu is much purer and clearer than karuppatti.\n- Growth rates of only 0.1-0.5 mm per day give the 5-25 mm faceted crystals harvested when the pot is broken at 40-60 days.\n"
    },
    {
        "slug": "institution-teri-sand-dune-nadar-palm-tappers-guilds-and-coastal-karuppatti-mercantile-trusts",
        "file": "institution-teri-sand-dune-nadar-palm-tappers-guilds-and-coastal-karuppatti-mercantile-trusts.md",
        "category": "institution",
        "name_en": "Teri Sand-Dune Nadar Palm Tappers' Guilds & Coastal Karuppatti Mercantile Trusts (Mahimai Pettai)",
        "name_ta": "தேரி மணற்குன்று நாடார் பனையேறிச் சங்கங்கள் மற்றும் கடற்கரைக் கருப்பட்டி வணிக அறக்கட்டளைகள் (மகிமைப் பேட்டை)",
        "era": "Medieval Pandya Era to Modern Era",
        "year_start": 900,
        "year_end": 2026,
        "thinai": "palai",
        "summary_en": "Social and economic institutions of the southern Teri palm country: hereditary Nadar (Shanar) climbing households holding seasonal palm leases, village boiling-shed cooperatives sharing koparai and fuel, and the mercantile pettai trading towns where karuppatti brokers levied a voluntary mahimai cess on every bag of palm sugar to endow schools, wells, choultries and temple festivals, shipping cargoes from Kulasekarapattinam and Tuticorin to Ceylon, Burma and Malaya.",
        "summary_ta": "தென் தேரிப் பனை நாட்டின் சமூக-பொருளாதார அமைப்புகள்: பருவக் குத்தகையில் பனைகளை ஏறும் பரம்பரை நாடார் (சாணார்) குடும்பங்கள், கொப்பரையும் எரிபொருளும் பகிரும் கிராமக் காய்ச்சுக்கூடக் கூட்டுறவுகள், ஒவ்வொரு கருப்பட்டி மூட்டைக்கும் மகிமை என்ற தன்னார்வ வரியை வசூலித்துப் பள்ளிகள், கிணறுகள், சத்திரங்கள், கோயில் திருவிழாக்களுக்கு நிதியளித்த பேட்டை வணிக நகரங்கள்; குலசேகரப்பட்டினம், தூத்துக்குடியிலிருந்து இலங்கை, பர்மா, மலாயாவுக்குக் கப்பலேற்றம்.",
        "sources": [
            "Hardgrave: The Nadars of Tamilnad (1969)",
            "Pandya Inscriptions on Panai-Eruvar Tenure (SII Vol. XIV)",
            "Tirunelveli District Gazetteer"
        ],
        "content": "# Teri Sand-Dune Nadar Palm Tappers' Guilds & Coastal Karuppatti Mercantile Trusts (Mahimai Pettai)\n\nTurning the Teri palm forests into an export economy took more than skill in the trees. It took a layered system of **climbing households**, **boiling cooperatives** and **mercantile trusts**, run mainly by the Nadar (historically Shanar or Chanar) community of the southern Pandya country.\n\n### 1. Hereditary Climbing Households (*பனையேறிக் குடும்பங்கள்*)\n- A climber works 30-50 palms through the tapping season (*பதநீர்ப் பருவம்*, roughly March to July), climbing each tree twice a day with an ankle loop and back strap.\n- Palms belong to landholding families or temples and are leased to climbers for the season. The climber keeps the sap and pays a share in karuppatti, a custom that Pandya-era palm dues (*panai-irai*) had already formalized.\n\n### 2. Boiling-Shed Cooperatives (*காய்ச்சுக்கூடம்*)\n- Neighbouring households pool their sap at a shared shed. They rotate the use of a single heavy iron koparai and gather frond fuel together, and the women of the household take charge of boiling, skimming and chirattai molding.\n\n### 3. Pettai Trading Towns & the Mahimai Trust (*மகிமை*)\n- Nadar merchants set up fortified trading compounds (*pettai*) at Sivakasi, Virudhunagar, Tiruchendur, Udangudi and Kulasekarapattinam, where they bought karuppatti in bulk from the Teri villages.\n- Every bag weighed at the pettai was charged a small voluntary **mahimai** contribution. This pooled fund paid for community schools, drinking-water wells, travellers' choultries (*சத்திரம்*), relief in bad years and temple festivals, which made it an early form of community trust financed through trade.\n- Councils of elders (*ஊர்ப் பெரியவர்கள்*) set standard weights, settled quality disputes over adulterated or over-limed karuppatti, and enforced repayment of credit.\n\n### 4. Maritime Export\n- From the 18th to the early 20th century, coastal brokers shipped karuppatti and panang kalkandu from Kulasekarapattinam and Tuticorin to Jaffna, Colombo, Rangoon, Penang and Singapore, where it sold to Tamil communities overseas.\n"
    },
    {
        "slug": "place-udangudi-ancient-teri-panai-karuppatti-and-panang-kalkandu-haven",
        "file": "place-udangudi-ancient-teri-panai-karuppatti-and-panang-kalkandu-haven.md",
        "category": "place",
        "name_en": "Udangudi: Ancient Teri Panai Karuppatti & Panang Kalkandu Haven",
        "name_ta": "உடன்குடி: பண்டைய தேரிப் பனை கருப்பட்டி மற்றும் பனங்கற்கண்டு உறைவிடம்",
        "era": "Sangam Era to Modern Era",
        "year_start": -300,
        "year_end": 2026,
        "thinai": "palai",
        "summary_en": "Udangudi in Thoothukudi district, set amid the Kudiraimozhi and Kayamozhi red Teri dunes between Tiruchendur and Kulasekarapattinam, as the hub of GI-registered karuppatti: clusters of thatched boiling sheds, thread-scarred kalkandu pot dumps, the weekly karuppatti santhai market, and palm-sugar caravans feeding the Kulasekarapattinam and Manapad sea-lanes.",
        "summary_ta": "திருச்செந்தூருக்கும் குலசேகரப்பட்டினத்துக்கும் இடையே குதிரைமொழி, காயாமொழி செந்தேரிக் குன்றுகளுக்கு நடுவே அமைந்த தூத்துக்குடி மாவட்ட உடன்குடி, புவிசார் குறியீடு பெற்ற கருப்பட்டியின் மையம்: ஓலைக் கூரைக் காய்ச்சுக்கூடங்கள், நூல் தடம் பதிந்த கற்கண்டுப் பானைக் குவியல்கள், வாராந்திரக் கருப்பட்டிச் சந்தை, குலசேகரப்பட்டினம் மற்றும் மணப்பாடு கடல்வழிகளுக்குச் செல்லும் பனைவெல்ல வண்டித் தொடர்கள்.",
        "sources": [
            "Udangudi Karuppatti GI Registration (Geographical Indications Registry, Chennai)",
            "Thoothukudi District Gazetteer (1917)",
            "Geological Survey of India: Teri Sands of Tirunelveli Coast"
        ],
        "content": "# Udangudi: Ancient Teri Panai Karuppatti & Panang Kalkandu Haven\n\n**Udangudi** (*உடன்குடி*, about lat 8.43, lng 78.06) in Thoothukudi district stands where the deep-red **Teri** dune fields of Kudiraimozhi and Kayamozhi meet the coast between the temple town of **Tiruchendur** and the old port of **Kulasekarapattinam**. Its name is a byword across the Tamil world for the finest palm sugar.\n\n### 1. Teri Landscape & the Palmyra Forest\n- The red Teri sands are iron-oxide-stained Pleistocene aeolian dunes, standing up to 60 m high. They hold perched freshwater lenses that let hundreds of thousands of *Borassus flabellifer* palms flourish without irrigation.\n- The groundwater is low in salt and high in potassium and iron, which is what gives Udangudi karuppatti its particular dark colour, crisp break and slightly mineral taste. This was a key argument in its **Geographical Indication** registration.\n\n### 2. Boiling-Shed Villages & Kalkandu Pot Dumps\n- Hamlets such as Pillaiyarpuram, Thandupathu, Meyyur and Kulasekaranpatti each run dozens of thatched boiling sheds through the tapping season. At dawn the smoke from their frond-fuelled koparai fires hangs over the Teri.\n- Heaps of broken, thread-scarred terracotta kalkandu pots and charred chirattai molds lie around the older sheds, the debris of centuries of panang kalkandu making.\n\n### 3. The Karuppatti Santhai & Sea Lanes\n- Udangudi's weekly **karuppatti santhai** brings in brokers from Tirunelveli, Madurai and Kerala. Domes and kalkandu clusters change hands by the palm-leaf *kottan*.\n- Historically, bullock-cart trains hauled palm sugar to the surf ports of Kulasekarapattinam and **Manapad**, where country craft loaded it for Ceylon and Southeast Asia.\n\n### 4. Sacred Geography\n- Palm-sugar offerings go to the Murugan temple at Tiruchendur and to the Mutharamman temple at Kulasekarapattinam during the Dasara festival, linking the palm harvest to the regional ritual calendar.\n"
    },
    {
        "slug": "text-sangam-and-medieval-pandya-epigraphs-on-panai-padaneer-and-karuppatti-tributes",
        "file": "text-sangam-and-medieval-pandya-epigraphs-on-panai-padaneer-and-karuppatti-tributes.md",
        "category": "text",
        "name_en": "Sangam Verses & Medieval Pandya Epigraphs on Panai, Padaneer & Karuppatti Tributes",
        "name_ta": "பனை, பதநீர் மற்றும் கருப்பட்டிக் காணிக்கைகள் குறித்த சங்கப் பாடல்களும் இடைக்காலப் பாண்டியக் கல்வெட்டுகளும்",
        "era": "Sangam Era to Late Pandya Era",
        "year_start": -300,
        "year_end": 1350,
        "thinai": "palai",
        "summary_en": "Textual record of the palmyra economy: Sangam references to the panai (Borassus) in Purananuru, Perumpanarruppadai and Kuruntokai, including its leaves, toddy and sweetness, alongside medieval Pandya stone inscriptions at Tiruchendur, Kalugumalai and Tirunelveli that record panai-irai palm dues, grants of karuppatti and padaneer for temple naivedya and perpetual lamps, and rights of palm-climbing communities.",
        "summary_ta": "பனைப் பொருளாதாரத்தின் எழுத்துப் பதிவுகள்: புறநானூறு, பெரும்பாணாற்றுப்படை, குறுந்தொகை ஆகியவற்றில் பனை மரம், ஓலை, கள், இனிமை பற்றிய சங்கக் குறிப்புகள்; திருச்செந்தூர், கழுகுமலை, திருநெல்வேலி இடைக்காலப் பாண்டியக் கல்வெட்டுகளில் பனையிறை வரி, கோயில் நைவேத்தியம் மற்றும் நந்தா விளக்குக்கான கருப்பட்டி, பதநீர்க் கொடைகள், பனையேறிச் சமூக உரிமைகள் பற்றிய பதிவுகள்.",
        "sources": [
            "Purananuru 22, 375",
            "Perumpanarruppadai 275-282",
            "South Indian Inscriptions Vol. XIV (Pandyas)",
            "Annual Report on Indian Epigraphy: Tiruchendur and Kalugumalai Records"
        ],
        "content": "# Sangam Verses & Medieval Pandya Epigraphs on Panai, Padaneer & Karuppatti Tributes\n\nThe palmyra (*பனை*) appears in Tamil writing more than two thousand years ago. It moves from the images of Sangam poetry to the dry fiscal language of medieval Pandya stone records.\n\n### 1. The Palmyra in Sangam Poetry (*சங்க இலக்கியத்தில் பனை*)\n- **The Chera Emblem**: The *panam-poo* (palmyra flower garland) is named as the emblem of the Chera kings in **Purananuru** and **Pathitruppathu**, showing how highly the tree was regarded early on.\n- **Perumpanarruppadai**: The bardic guide-poem describes settlements fenced with palmyra and travellers offered sweet palm drinks and solid sweets, an early literary trace of palm-sap hospitality.\n- **Kuruntokai & Narrinai**: Palai-landscape poems use the lone, unbending palmyra in the burning wasteland as an image of patience and endurance, and they speak of the tall black trunk and the rustling fan-leaves sounding in the night wind.\n\n### 2. Medieval Pandya Epigraphs (*பாண்டியக் கல்வெட்டுகள்*)\n- **Panai-Irai (*பனையிறை*)**: Pandya inscriptions of the 9th-13th centuries list *panai-irai* or *panai-maram-irai*, a tax on each palm or each tapping season, among the village dues collected by the royal treasury or handed over to temples.\n- **Karuppatti for Temple Naivedya**: Grants at the Tiruchendur Subrahmanya temple and the Kalugumalai Vettuvan Koil precinct set aside fixed measures of *karuppatti* and *padaneer* each day for the god's sweet offerings (*அமுதுபடி*) and for festival *panakam* drinks.\n- **Lamp & Feeding Endowments**: Some records direct palm-sugar revenue from named groves to keep perpetual lamps (*நந்தா விளக்கு*) burning or to feed pilgrims, showing that karuppatti worked as a store of value much as paddy did.\n- **Climbers' Rights**: Inscriptions name the *panai-eruvar* (palm climbers) as a recognised group with set tenure and obligations to pay, which corresponds to the later hereditary guild system of the Teri country.\n\n### 3. Reading the Record\n- Taken together, the poems and the inscriptions show a continuous palm-sugar economy: Sangam sweetness turns into Pandya tribute, which in turn foreshadows the mahimai trade of the colonial-era pettai towns.\n"
    }
]

EDGES = [
    [
        "technology-padaneer-seashell-lime-inhibition-open-iron-pan-boiling-and-scum-skimming",
        "explained_by",
        "concept-sucrose-inversion-prevention-by-calcium-hydroxide-and-caramelization-kinetics",
        "material_culture",
        "Sangam Era to Modern Era",
        "Shell-lime dusting and open-pan boiling depend on alkaline arrest of sucrose inversion and controlled Maillard browning",
        "Chemical Analysis"
    ],
    [
        "technology-padaneer-seashell-lime-inhibition-open-iron-pan-boiling-and-scum-skimming",
        "utilizes",
        "artifact-heavy-cast-iron-boiling-koparai-wooden-stirring-oars-and-palm-leaf-kudai-baskets",
        "material_culture",
        "Medieval Pandya Era to Modern Era",
        "Sap concentration is carried out in the cast-iron koparai with wooden oars, coconut-shell skimmers and kudai filter cones",
        "Ethnoarchaeology"
    ],
    [
        "technology-padaneer-seashell-lime-inhibition-open-iron-pan-boiling-and-scum-skimming",
        "feeds_into",
        "technology-karuppatti-chirattai-molding-and-clay-pot-panang-kalkandu-slow-crystallization",
        "material_culture",
        "Sangam Era to Modern Era",
        "Thread-stage syrup from the koparai is either beaten and chirattai-molded or diverted into threaded clay pots for kalkandu",
        "Craft Observation"
    ],
    [
        "technology-karuppatti-chirattai-molding-and-clay-pot-panang-kalkandu-slow-crystallization",
        "produces",
        "artifact-udangudi-karuppatti-coconut-shell-blocks-and-crystalline-panang-kalkandu-clusters",
        "material_culture",
        "Medieval Pandya Era to Modern Era",
        "Chirattai molding yields dome karuppatti blocks while buried porous pots yield threaded kalkandu crystal clusters",
        "Craft Observation"
    ],
    [
        "technology-karuppatti-chirattai-molding-and-clay-pot-panang-kalkandu-slow-crystallization",
        "derives_from",
        "concept-supersaturated-pan-cooling-nucleation-and-crystal-lattice-growth-in-porous-earthenware",
        "material_culture",
        "Sangam Era to Modern Era",
        "Shock nucleation by sand-bed beating versus metastable-zone growth in porous terracotta governs the two product forms",
        "Crystallization Physics"
    ],
    [
        "artifact-udangudi-karuppatti-coconut-shell-blocks-and-crystalline-panang-kalkandu-clusters",
        "embodies",
        "concept-polyphenolic-antioxidant-dense-mineral-matrix-and-low-glycemic-nutritional-biochemistry",
        "material_culture",
        "Medieval Pandya Era to Modern Era",
        "Non-centrifugal karuppatti retains polyphenols, melanoidins and a potassium-iron mineral matrix with low glycemic response",
        "Nutritional Analysis"
    ],
    [
        "institution-teri-sand-dune-nadar-palm-tappers-guilds-and-coastal-karuppatti-mercantile-trusts",
        "administers",
        "technology-padaneer-seashell-lime-inhibition-open-iron-pan-boiling-and-scum-skimming",
        "material_culture",
        "Medieval Pandya Era to Modern Era",
        "Nadar climbing households and boiling-shed cooperatives organized seasonal tapping, liming and boiling",
        "Historical Ethnography"
    ],
    [
        "institution-teri-sand-dune-nadar-palm-tappers-guilds-and-coastal-karuppatti-mercantile-trusts",
        "operates_in",
        "place-udangudi-ancient-teri-panai-karuppatti-and-panang-kalkandu-haven",
        "material_culture",
        "Medieval Pandya Era to Modern Era",
        "Pettai brokers and mahimai trusts traded Udangudi karuppatti through the weekly santhai and coastal ports",
        "Historical Geography"
    ],
    [
        "place-udangudi-ancient-teri-panai-karuppatti-and-panang-kalkandu-haven",
        "cultivates",
        "artifact-udangudi-karuppatti-coconut-shell-blocks-and-crystalline-panang-kalkandu-clusters",
        "material_culture",
        "Sangam Era to Modern Era",
        "Teri dune palm forests and boiling-shed hamlets of Udangudi produce GI-registered karuppatti and kalkandu",
        "Geographical Indication Registry"
    ],
    [
        "text-sangam-and-medieval-pandya-epigraphs-on-panai-padaneer-and-karuppatti-tributes",
        "documents",
        "institution-teri-sand-dune-nadar-palm-tappers-guilds-and-coastal-karuppatti-mercantile-trusts",
        "material_culture",
        "Sangam Era to Late Pandya Era",
        "Pandya inscriptions record panai-irai palm dues, karuppatti temple grants and the tenure of panai-eruvar climbers",
        "Epigraphical Records"
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
