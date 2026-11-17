#!/usr/bin/env python3
"""
Harvester: Batch 50 - Ancient Tamil Stick-Lac & Shellac Resin Harvesting, Kerria Lacca Host Ecology, Wax-Sealing & Turned Wood Lacquerware
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
        "slug": "text-silappadikaram-kalittokai-and-chola-charters-on-cevv-arakku-lac-and-seals",
        "category": "text",
        "file": "text-silappadikaram-kalittokai-and-chola-charters-on-cevv-arakku-lac-and-seals.md",
        "name_en": "Silappadikaram, Kalittokai & Chola Charters on Cevv-Arakku Lac, Alathagam Dye & Royal Seals",
        "name_ta": "சிலப்பதிகாரம், கலித்தொகை மற்றும் சோழர் சாசனங்களில் செவ்வரக்கு, ஆலத்தகம் மற்றும் அரக்கு முத்திரை",
        "era": "Sangam to Chola Imperial Era",
        "year_start": -300,
        "year_end": 1250,
        "thinai": "kurinji",
        "summary_en": "Classical Tamil literary and epigraphical attestations in Silappadikaram, Kalittokai, and Chola inscriptions documenting stick-lac resin (kombarakku / cevv-arakku), crimson foot-cosmetic dye (alathagam / sempanju), jeweler's setting pitch, and lac-impressed royal signet seals (arakku-muddirai).",
        "summary_ta": "சிலப்பதிகாரம், கலித்தொகை மற்றும் சோழர் காலக் கல்வெட்டுகளில் குறிப்பிடப்படும் கொம்பரக்கு, செவ்வரக்கு, மகளிர் பாதங்களில் பூசும் செம்பஞ்சுக் குழம்பு (ஆலத்தகம்) மற்றும் அரச ஓலைகளின் அரக்கு முத்திரை.",
        "sources": [
            "Silappadikaram",
            "Kalittokai",
            "South Indian Inscriptions"
        ],
        "content": "# Silappadikaram, Kalittokai & Chola Charters on Cevv-Arakku Lac\n\nClassical Tamil poetry and medieval royal diplomacy record three distinct uses of the insect resin *arakku* (stick-lac and shellac):\n\n**Literary & Epigraphical Attestations:**\n- **Kalittokai & Silappadikaram on *Cevv-Arakku* and *Alathagam***: Classical verses describe *cevv-arakku* (crimson lac resin) softening effortlessly near fire, and celebrate *alathagam* (or *sempanju-kuzhambu*)—cotton pads saturated with the water-soluble crimson dye extracted from raw stick-lac—used by dancers (such as Madhavi in *Silappadikaram*) and brides to paint auspicious red borders along their soles and palms.\n- **Royal *Arakku-Muddirai* (Lac Signet Impressions)**: In *Silappadikaram* (where Madhavi seals her palm-leaf epistle to Kovalan with a scented clay-and-lac impression) and Chola administrative practice, tied bundles of palm-leaf charters (*olai*) and treasury chests were sealed with molten red *arakku* stamped with the royal tiger, fish, or bow signet ring (*ilatchinai*)."
    },
    {
        "slug": "concept-kerria-lacca-entomology-puvam-host-ecology-and-aleuritic-shellolic-polyester-chemistry",
        "category": "concept",
        "file": "concept-kerria-lacca-entomology-puvam-host-ecology-and-aleuritic-shellolic-polyester-chemistry.md",
        "name_en": "Kerria lacca Scale-Insect Entomology, Puvam Host Ecology & Aleuritic-Shellolic Polyester Chemistry",
        "name_ta": "கெரியா லக்கா (அரக்குப் பூச்சி) உயிரியல், பூவம்-புரசு விருந்தோம்பி மரங்கள் மற்றும் பாலியெஸ்டர் பிசின் வேதியியல்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Entomology and natural polymer chemistry of stick-lac: female Kerria lacca scale insects piercing the phloem of Schleichera oleosa (puvam / kumbadiri), Butea monosperma (purasu), and Ziziphus mauritiana (ilanthai) to secrete a cross-linked polyester of aleuritic and shellolic acids plus laccaic acid dye.",
        "summary_ta": "பூவம் (கும்பாதிரி), புரசு மற்றும் இலந்தை மரங்களின் சாற்றை உறிஞ்சி வாழும் 'கெரியா லக்கா' அரக்குப் பூச்சியின் உயிரியலும், அது சுரக்கும் அலியூரிட்டிக்-ஷெல்லோலிக் அமில இயற்கை பாலியெஸ்டர் பிசின் மற்றும் செம்பஞ்சுச் சாய வேதியியலும்.",
        "sources": [
            "Indian Lac Research Institute Monographs",
            "Forest Flora of South India (Schleichera oleosa & Butea monosperma)",
            "Chemistry of Natural Resins and Shellac"
        ],
        "content": "# Kerria lacca Entomology, Host Trees & Polyester Resin Chemistry\n\nUnlike plant gums or pine rosins, *arakku* (lac) is the only commercial resin of **animal origin**, secreted as a protective armoured test by the scale insect *Kerria lacca* (family Kerriidae):\n\n**Ecological & Chemical Foundations:**\n- **Three Premier Tamil Forest Host Trees**:\n  1. *Puvam / Kumbadiri* (*Schleichera oleosa*, Kusum tree): Growing in the moist deciduous foothills of the Western Ghats, it yields the palest, hardest, highest-grade *Kusumi* stick-lac.\n  2. *Purasu / Palasu* (*Butea monosperma*, Flame of the Forest) and *Ilanthai* (*Ziziphus mauritiana*, Indian jujube): Dry-zone hosts across Mullai and Kurinji tracts yielding rich crimson *Rangeeni* lac.\n- **Natural Thermoplastic Polyester**: Raw stick-lac consists of ~68% resin (an ester oligomer of hydroxy fatty acids—chiefly **aleuritic acid**—and sesquiterpenic **shellolic/jalaric acids**), ~10% water-soluble anthraquinone crimson pigment (**laccaic acids A–E**), and ~6% natural **lac wax**. When heated above $75^\\circ\\text{C}-80^\\circ\\text{C}$, the polyester softens into a tenacious, glossy film former."
    },
    {
        "slug": "technology-kombarakku-twig-scraping-stone-vat-laccaic-dye-washing-and-cloth-bag-shellac-melting",
        "category": "technology",
        "file": "technology-kombarakku-twig-scraping-stone-vat-laccaic-dye-washing-and-cloth-bag-shellac-melting.md",
        "name_en": "Kombarakku Twig Scraping, Stone-Vat Crimson Dye Extraction & Cloth-Tube Shellac Drawing",
        "name_ta": "கொம்பரக்கு சிதைத்தல், கல்தொட்டி செம்பஞ்சுச் சாயப் பிரிப்பு மற்றும் துணிப்பை உருக்கித் தகர அரக்கு வார்த்தல்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 1950,
        "thinai": "kurinji",
        "summary_en": "Refining workflow of forest lac: harvesting brood-free encrusted twigs (kombarakku), crushing and trampling in ribbed stone vats to leach out crimson laccaic dye (arakku-neer), drying golden granular seedlac (mani-arakku), and twisting long canvas tubes over charcoal hearths to extrude shellac.",
        "summary_ta": "காட்டில் சேகரித்த கொம்பரக்கை உடைத்து, கல்தொட்டியில் நீரூற்றி மிதித்துச் சிவப்புச் சாயத்தைப் (அரக்கு நீர்) பிரித்து, மணி அரக்கை உலர்த்தி, நீண்ட துணிப்பையில் இட்டுத் தழலில் உருக்கித் தகர அரக்காக இழுக்கும் தொழில்நுட்பம்.",
        "sources": [
            "Traditional Lac Refining and Dyeing in South India",
            "Watt's Dictionary of the Economic Products of India (Lac)",
            "Siddha Purification of Kombarakku (Arakku Suddhi)"
        ],
        "content": "# Kombarakku Scraping, Vat Dye Washing & Cloth-Bag Shellac Melting\n\nConverting woody encrusted twigs (*kombarakku*) gathered from the forest into pure translucent shellac (*thagara-arakku*) and crimson textile dye required a four-stage separation process:\n\n**Refining Sequence:**\n1. **Brood-Safe Pruning & Scraping**: Harvesters cut encrusted branches just after larval swarming (*phunki* lac) or reserve uncut brood twigs tied to fresh *puvam* branches to inoculate the next generation. The resinous crust is scraped from the twigs with curved sickles and crushed under stone rollers.\n2. **Stone-Vat Washing (*Arakku-Neer* Extraction)**: Crushed lac is steeped in rough-chiseled hemispherical stone vats (*kal-thotti*) with water and mild fuller's earth (*uzha-mann*). A worker treads the granules against the ribbed stone walls to rupture insect cells, leaching out deep crimson **laccaic acid** water. The red liquor is strained and evaporated into *alathagam* dye cakes for silk dyeing, leaving golden resin granules called **seedlac (*mani-arakku*)**.\n3. **Charcoal-Hearth Cloth-Tube Filtration**: Dry seedlac (sometimes blended with a trace of yellow orpiment or pine rosin for fluidity) is packed into a 30-foot-long narrow cotton sausage bag held before a curved charcoal hearth. As one artisan twists the bag with a windlass, molten resin squeezes through the cloth weave, is scraped off with an iron spatula, and stretched over a wet palm-frond or ceramic cylinder into thin amber **shellac sheets** or rolled into cylindrical **lac sticks (*arakku-kuchi*)**."
    },
    {
        "slug": "concept-kadaisal-arakku-friction-heat-plastification-and-veppalai-wood-turnery-tribology",
        "category": "concept",
        "file": "concept-kadaisal-arakku-friction-heat-plastification-and-veppalai-wood-turnery-tribology.md",
        "name_en": "Kadaisal-Arakku Friction-Heat Plastification & Veppalai (Wrightia tinctoria) Turnery Tribology",
        "name_ta": "கடைசல் அரக்கு உராய்வு வெப்பப் பூச்சு இயற்பியலும் வெப்பாலை மரக் கடைசல் நுட்பமும்",
        "era": "Medieval to Modern Era",
        "year_start": 800,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Thermomechanical physics of dry-lacquering turned wood on a lathe (kadaisal-arakku): pressing a solid pigmented shellac stick against rapidly spinning fine-grained Wrightia tinctoria (veppalai) timber generates localized frictional flash-heating (~85°C) that melts, bonds, and burnishes a solvent-free coat.",
        "summary_ta": "மரக் கடைசல் பொறியில் வேகமாகச் சுழலும் வெப்பாலை (Wrightia tinctoria) மரத்தின் மீது திட அரக்குக் குச்சியை அழுத்தும்போது ஏற்படும் உராய்வு வெப்பத்தால் (~85°C) கரைப்பான் இன்றி அரக்கு உருகிப் பளபளப்பாக ஒட்டும் இயற்பியல்.",
        "sources": [
            "Lac-Turnery Traditions of South India",
            "Wood Anatomy of Wrightia tinctoria (Veppalai)",
            "Tribology of Thermoplastic Resin Coatings"
        ],
        "content": "# Kadaisal-Arakku Friction-Heat Plastification & Veppalai Tribology\n\nUnlike East Asian *urushi* sap (which cures slowly by enzymatic humidity oxidation) or European spirit varnish (which relies on alcohol evaporation), traditional South Indian lathe lacquerware (*kadaisal-arakku*) is a **100% solvent-free, instantaneous friction-melt process**:\n\n**Tribological & Botanical Mechanics:**\n- **Why *Veppalai* (*Wrightia tinctoria*) Timber?**: Known in Tamil as *veppalai* or *paalai-maram*, this ivory-white deciduous wood possesses an ultra-fine, interlocking, diffuse-porous grain completely free of open resin ducts or coarse vessels. When turned on a lathe, it shears to a satin-smooth surface that neither drinks up molten shellac unevenly nor splinters.\n- **Frictional Flash-Melting ($80^\\circ\\text{C}-95^\\circ\\text{C}$)**: When the turner presses a solid pigmented *arakku-kuchi* stick against the spinning *veppalai* workpiece, sliding friction at the contact line instantaneously raises the interface temperature above shellac's glass-transition and flow point (~80°C), depositing a thin, coalesced thermoplastic film.\n- **Screw-Pine Leaf Burnishing (*Taazhai-Madal*)**: Pressing the fibrous, slightly waxy edge of a cured screw-pine leaf (*Pandanus odorifer* / *taazhai*) with a drop of sesame oil against the spinning lac coat redistributes the molten film and polishes it to a mirror-like, waterproof gloss in seconds."
    },
    {
        "slug": "technology-bow-lathe-veppalai-turning-mineral-pigmented-lac-stick-application-and-taazhai-buffing",
        "category": "technology",
        "file": "technology-bow-lathe-veppalai-turning-mineral-pigmented-lac-stick-application-and-taazhai-buffing.md",
        "name_en": "Bow-Lathe Veppalai Turning, Mineral-Pigmented Arakku-Kuchi Compounding & Multi-Layer Sgraffito",
        "name_ta": "விற்கடைசல் வெப்பாலை மர வேலை, கனிம வண்ண அரக்குக் குச்சி தயாரிப்பு மற்றும் பலவண்ணச் செதுக்கு வேலை",
        "era": "Medieval to Modern Era",
        "year_start": 900,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Workshop craft of compounding colored lacquer sticks (arakku-kuchi) by kneading softened shellac with vermilion, turmeric/orpiment, indigo, and white clay, turning veppalai wood on a two-point lathe, and incising superimposed contrasting color layers (nakshi / sgraffito).",
        "summary_ta": "உருகிய அரக்குடன் சாதிலிங்கம், அரிதாரம், நீலம், வெண்களிமண் சேர்த்து இடித்து வண்ண அரக்குக் குச்சிகள் தயாரித்து, கடைசலில் சுழலும் வெப்பாலை மரத்தின் மீது பல அடுக்குப் பூசிச் செதுக்கும் பட்டறைத் தொழில்நுட்பம்.",
        "sources": [
            "Artisans of Madurai, Cumbum, and Tirupati-Channapatna Belt",
            "Traditional Indian Lacquerware Craft Manuals",
            "Natural Pigments of South Indian Crafts"
        ],
        "content": "# Bow-Lathe Turning, Mineral Lac-Stick Compounding & Sgraffito\n\nMaster lacquer-turners (*Kadaisalkarar*) prepare their own palette of solid thermoplastic colour crayons (*arakku-kuchi*) before mounting seasoned *veppalai* billets between lathe centres:\n\n**Pigment Compounding & Turning Workflow:**\n1. **Kneading Coloured *Arakku-Kuchi***: Golden shellac is softened before a charcoal pan on a wooden paddle and repeatedly hammered and stretched like taffy with finely levigated mineral and vegetal pigments:\n   - *Red*: Cinnabar/vermilion (*saadhilingam*) or madder/lac lake.\n   - *Yellow*: Orpiment (*aritharam*) or turmeric (*manjal*).\n   - *Green*: Indigo (*avuri*) blended with yellow turmeric/orpiment.\n   - *Black*: Lampblack (*kari*) collected from gingelly-oil lamps.\n   - *Opaque Pastel Base*: Calcined conch-shell lime or white kaolin clay (*ven-kaliman*).\n2. **Turning & Banding**: Using skew chisels (*சீவு உளி*) and gouges on a two-point dead-centre lathe (*kadaisal*), the artisan hollows interlocking box lids and bases, scores decorative V-grooves, and applies sequential bands of contrasting *arakku-kuchi*, buffing each with a *taazhai* (screw-pine) leaf strip.\n3. **Multi-Layer Sgraffito**: By laying yellow over red over black lac and lightly touching a fine steel stylus to the spinning piece, the turner carves through upper layers to reveal intricate multi-coloured floral and geometric rings."
    },
    {
        "slug": "concept-arakku-mettuthal-goldsmith-chasing-pitch-and-royal-arakku-muddirai-sigillography",
        "category": "concept",
        "file": "concept-arakku-mettuthal-goldsmith-chasing-pitch-and-royal-arakku-muddirai-sigillography.md",
        "name_en": "Arakku-Mettuthal Goldsmith Chasing Pitch, Kundala Wax-Core Setting & Royal Sigillography",
        "name_ta": "பொற்கொல்லர் அரக்கு மெட்டுதல் (நகை அரக்கு), கல் பதிப்பு மற்றும் அரச அரக்கு முத்திரை அறிவியல்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Metallurgical and diplomatic applications of compounded lac resin: blending shellac with finely sieved brick-dust and gingelly oil to form shock-absorbing goldsmith's chasing pitch (arakku-mettuthal) that supports thin gold sheet during repousse and gem-setting, plus tamper-evident royal seals.",
        "summary_ta": "ஆபரணத் தொழிலில் மெல்லிய தங்கத் தகடுகள் நெளியாமல் தாங்கிப் பிடிக்கவும் நவரத்தினக் கற்களைப் பதிக்கவும் பயன்படும் 'நகை அரக்கு' (அரக்கு + செங்கல் தூள் + எண்ணெய்) மற்றும் அரச ஆவணங்களின் அரக்கு முத்திரை அறிவியல்.",
        "sources": [
            "Silappadikaram",
            "Traditional Thanjavur and Coachella/Coimbatore Goldsmithing Manuals",
            "Chola Administrative Sigillography"
        ],
        "content": "# Arakku-Mettuthal Goldsmith Chasing Pitch & Royal Sigillography\n\nIn Tamil temple jewellery (*Kemp* / *Vadasery* goldsmithing) and royal chancelleries, compounded *arakku* performs critical structural and security functions:\n\n**Metallurgical & Sigillographic Principles:**\n- **Goldsmith's Chasing Pitch (*Pattarai-Arakku* / *Arakku-Mettuthal*)**: Pure shellac is brittle at room temperature, so Tamil *Thattar* (goldsmiths) melt stick-lac with finely levigated roasted brick-dust (*sengal-thool*), a few drops of sesame oil, and dammar/beeswax. This viscoelastic pitch is poured hot inside hollow 22-karat gold *thali* pendants, *oddiyanam* belts, and *vanki* armlets:\n  1. When cooled, it forms a rigid, non-compressible core that prevents paper-thin gold sheet (*thanga-rekku*) from collapsing under the chasing punches (*nagasi* work) or during daily wear.\n  2. In *Kemp* and *Kundan* gem-setting, the warm *arakku* bed inside the gold bezel (*kuzhi*) grips foil-backed cabochon rubies and emeralds firmly while cushioning them against impact.\n- **Tamper-Evident *Arakku-Muddirai***: Compounded with cinnabar for deep red opacity, sealing lac bonds tightly to palm-leaf cords and cloth wrappers but fractures cleanly with a conchoidal snap if pried, providing unmistakable proof of tampering."
    },
    {
        "slug": "artifact-kombarakku-stick-lac-arakku-kuchi-sealing-wax-and-alathagam-crimson-dye-cakes",
        "category": "artifact",
        "file": "artifact-kombarakku-stick-lac-arakku-kuchi-sealing-wax-and-alathagam-crimson-dye-cakes.md",
        "name_en": "Kombarakku Encrusted Twigs, Arakku-Kuchi Sealing & Lathe Sticks & Alathagam Crimson Dye Cakes",
        "name_ta": "கொம்பரக்குக் குச்சிகள், முத்திரை மற்றும் கடைசல் அரக்குக் கட்டிகள் மற்றும் ஆலத்தகம் செம்பஞ்சுச் சாய வில்லைகள்",
        "era": "Sangam to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Primary and refined lac commodities in Tamil trade and Siddha medicine: raw resin-encrusted forest twigs (kombarakku), golden seedlac granules (mani-arakku), pigmented lathe and sealing sticks (arakku-kuchi),crimson dye pads (alathagam), and Siddha Arakku Thailam medicated oil.",
        "summary_ta": "அரக்கு சார்ந்த வணிக மற்றும் மருத்துவப் பொருட்கள்: காட்டு மரக் கிளைகளில் படிந்த கொம்பரக்கு, மணி அரக்கு, வண்ண அரக்குக் குச்சிகள், மகளிர் பாதச் சாயமான ஆலத்தகம் மற்றும் சித்த மருத்துவ 'அரக்குத் தைலம்'.",
        "sources": [
            "Silappadikaram",
            "Agathiyar Paripooranam & Siddha Formulary (Arakku Thailam)",
            "Madurai and Cumbum Forest Produce Inventories"
        ],
        "content": "# Kombarakku Stick-Lac, Arakku-Kuchi Sticks & Alathagam Dye Cakes\n\nFrom the montane forest floor to royal treasuries and Siddha pharmacies, lac circulated in five specialized material forms:\n\n**Commodity & Medicinal Artifacts:**\n- **Kombarakku (Crude Stick-Lac)**: Twigs of *puvam* or *ilanthai* encased in a 3–8 mm amber-red bubbly crust of *Kerria lacca* resin tunnels.\n- **Alathagam / Sempanju Pads**: Cotton wool rounds steeped repeatedly in concentrated crimson *arakku-neer* (laccaic acid liquor) and sun-dried; moistened with water, they yielded instant ruby dye for classical dancers' feet and marriage rituals, while the liquid vat dyed Kanchipuram and Madurai silk yarns a fast crimson-purple with alum mordant.\n- **Arakku-Kuchi (Sealing & Turnery Sticks)**: Molded rectangular or cylindrical sticks of refined shellac compounded with cinnabar or mineral pigments.\n- **Siddha *Arakku Thailam***: A renowned Siddha medicated sesame-oil decoction prepared by boiling purified *kombarakku* (*arakku suddhi* in cow's milk/herbal juice) with *kostam*, *manjistha*, and *ashwagandha*, prescribed for chronic fevers, bone-ache (*स्थि சுரம் / asthi suram*), and sinus headaches."
    },
    {
        "slug": "artifact-lacquered-veppalai-anjaraipetti-spice-boxes-marapachi-wooden-toys-and-choppu-ware",
        "category": "artifact",
        "file": "artifact-lacquered-veppalai-anjaraipetti-spice-boxes-marapachi-wooden-toys-and-choppu-ware.md",
        "name_en": "Lacquered Veppalai Anjaraipetti Spice Boxes, Choppu-Samaan Miniature Play-Sets & Kumkumam Caskets",
        "name_ta": "அரக்கு பூசிய வெப்பாலை மர அஞ்சறைப்பெட்டி, சொப்புச் சாமான் பொம்மைகள் மற்றும் குங்குமச் சிமிழ்கள்",
        "era": "Medieval to Modern Era",
        "year_start": 900,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Domestic and ritual wooden artifacts finished with friction-applied shellac lacquer (kadaisal-arakku): multi-tiered cylindrical spice towers (maravai / anjaraipetti), auspicious bridal vermilion jars (kumkumam-chimizh), baby rattles (kilukiluppai), and miniature kitchen play-sets (choppu-samaan).",
        "summary_ta": "கடைசல் அரக்கு பூசப்பட்ட வீட்டு மற்றும் சடங்குப் பொருட்கள்: அடுக்கடுக்கான மர அஞ்சறைப்பெட்டி, மணமகள் குங்குமச் சிமிழ், குழந்தைகளின் கிலுகிலுப்பை மற்றும் வண்ணமயமான சொப்புச் சாமான் விளையாட்டுப் பொருட்கள்.",
        "sources": [
            "South Indian Domestic Utensil & Toy Collections",
            "Ethnography of Tamil Bridal Trousseau (Seer-Varisai)",
            "Traditional Wooden Toys of Tamil Nadu"
        ],
        "content": "# Lacquered Veppalai Spice Boxes, Kumkumam Jars & Choppu-Samaan Toys\n\nBecause insect shellac is completely **non-toxic, food-safe, and impervious to moisture and spice oils**, lacquered *veppalai* wood turnery formed the backbone of traditional Tamil kitchenware and children's playthings:\n\n**Domestic & Ritual Artifacts:**\n- **Tiered *Maravai* & *Anjaraipetti* Spice Towers**: Interlocking cylindrical wooden jars turned on the lathe with precision rabbeted rims, banded in concentric rings of vermilion, saffron-yellow, and emerald-green *arakku* to store mustard, fenugreek, cumin, pepper, and turmeric without metallic taint.\n- **Bridal *Kumkumam-Chimizh* & *Manjal* Caskets**: Pear- and lotus-bud-shaped miniature jars presented in every Tamil bride's *seer-varisai* trousseau and during *Navaratri Golu* gifts (*thamboolam*).\n- **Choppu-Samaan & *Kilukiluppai* Rattles**: Miniature turned wooden stoves, *idli* steamers, rolling pins, and pebble-filled hollow rattles (*kilukiluppai*); the food-grade *arakku* coating allowed teething infants to mouth the toys safely while the medicinal *veppalai* wood beneath remained hygienic."
    },
    {
        "slug": "institution-forest-kombarakku-collectors-and-kadaisalkarar-lacquer-turnery-guilds",
        "category": "institution",
        "file": "institution-forest-kombarakku-collectors-and-kadaisalkarar-lacquer-turnery-guilds.md",
        "name_en": "Kurinji Kombarakku Forest Harvesters, Minor Forest Produce Pettais & Kadaisalkarar Turner Guilds",
        "name_ta": "குறிஞ்சி கொம்பரக்குச் சேகரிப்போர், மலைப்பொருள் பேட்டைகள் மற்றும் கடைசல்காரர் மர வினைஞர் குழாம்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Socio-economic network linking Western and Eastern Ghats tribal lac-collectors (Paliyar, Kuravar, Malayali) who manage brood-lac cycles on forest puvam trees with foothill Pettai refiners, silk-dyers, goldsmiths, and hereditary Kadaisalkarar wood-turner guilds.",
        "summary_ta": "மேற்கு மற்றும் கிழக்குத் தொடர்ச்சி மலைகளில் பூவம் மரங்களில் விதை அரக்குப் பெருக்கிச் சேகரிக்கும் பழங்குடியினர், அடிவாரப் பேட்டை வணிகர்கள், பட்டுச் சாயக் கலைஞர்கள் மற்றும் கடைசல்காரர் மரத் தச்சர் குழுக்கள்.",
        "sources": [
            "Madurai and Salem District Forest Manuals (Minor Forest Produce)",
            "Ethnography of Paliyar and Malayali Hill Communities",
            "Artisan Guild Records of Southern Tamil Nadu"
        ],
        "content": "# Forest Kombarakku Collectors & Kadaisalkarar Turner Guilds\n\nThe Tamil lac economy linked montane forest entomology with urban craft guilds across three ecological zones:\n\n**Guild & Supply-Chain Structure:**\n- **Tribal Brood-Lac Stewards (*Paliyar, Kuravar & Malayali*)**: In the Suruli–Cumbum hills, Sirumalai, and Javadi/Kollimalai ranges, indigenous forest collectors tracked the biannual life-cycle (*Kartiki* and *Baisakhi* / *Ani* crops) of *Kerria lacca*, leaving uncut brood-lac (*vithai-arakku*) on sheltered *puvam* (*Schleichera oleosa*) branches so monsoon storms would not extinguish the colony.\n- **Minor Forest Produce *Pettai* Refineries**: At foothill market towns (*pettai*), licensed contractors and merchant guilds bought baskets of raw *kombarakku*, operated stone washing vats, sold crimson *alathagam* dye liquor to *Saurashtra* and *Kaikolar* silk-dyers in Madurai and Kumbakonam, and supplied *mani-arakku* to goldsmiths.\n- **Kadaisalkarar (Lacquer-Turner) Workshops**: Hereditary wood-turner families established workshops near irrigated *marutham* temple towns and dryland *veppalai* groves, turning and lacquering *choppu* toys, cradle spindles (*thottil-kambu*), and temple palanquin struts."
    },
    {
        "slug": "place-cumbum-ancient-suruli-forest-kombarakku-lac-and-turnery-haven",
        "category": "place",
        "file": "place-cumbum-ancient-suruli-forest-kombarakku-lac-and-turnery-haven.md",
        "name_en": "Cumbum (Kambam): Ancient Suruli Forest Kombarakku Lac, Puvam Groves & Wood-Turnery Haven",
        "name_ta": "கம்பம் - சுருளி மலைக் கொம்பரக்கு, பூவம் காடுகள் மற்றும் கடைசல் அரக்கு மரக்கலைத் தளம்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "kurinji",
        "summary_en": "Historic valley market town in Theni district flanked by the Suruli, Vannathiparai, and High Wavys forest ranges (9.7360° N, 77.2840° E), long celebrated as a primary South Indian gathering and trading center for wild Schleichera oleosa (puvam / kumbadiri) stick-lac (kombarakku), forest wax, and turned woodenware.",
        "summary_ta": "தேனி மாவட்டத்தில் சுருளி மலை மற்றும் வண்ணாத்திப்பாறைக் காடுகளால் சூழப்பட்ட கம்பம் பள்ளத்தாக்கு (9.7360° N, 77.2840° E): பூவம் (கும்பாதிரி) மரக் கொம்பரக்கு, காட்டு மெழுகு மற்றும் கடைசல் அரக்கு மரப் பொருட்களுக்குப் புகழ்பெற்ற வரலாற்றுத் தளம்.",
        "sources": [
            "Madurai District Gazetteer (Cumbum Valley & Suruli Forest Range)",
            "Working Plans of the Madurai South Forest Division (Minor Forest Produce: Lac)",
            "Theni District Historical & Craft Survey"
        ],
        "content": "# Cumbum (Kambam): Ancient Suruli Forest Kombarakku Lac & Turnery Haven\n\nNestled in the fertile structural trough between the Varusanadu–Andipatti hills and the towering High Wavys / Suruli escarpment of the Western Ghats in Theni district (9.7360° N, 77.2840° E), **Cumbum (Kambam)** and the adjoining **Suruli–Vannathiparai** forest belt form a classic *Kurinji-Marutham* ecotone for South Indian lac and woodcraft:\n\n**Ecological & Craft Significance:**\n- **Rich *Puvam* (*Schleichera oleosa*) & *Veppalai* Forests**: The moist deciduous slopes around Suruli Falls, Vannathiparai, and Kumuli support dense natural stands of *puvam* (*kumbadiri*), *purasu*, and *veppalai* (*Wrightia tinctoria*)—providing both the premier host tree for high-grade *Kusumi kombarakku* stick-lac and the ideal ivory-grained timber for lathe turnery.\n- **Historic Minor Forest Produce Entrepot**: For centuries, *Paliyar* and *Kuravar* forest gatherers brought head-loads of *kombarakku* stick-lac, wild beeswax, dammar resin (*kungiliyam*), and honey down the Suruli gorge to Cumbum's *pettai* markets, supplying Madurai's silk dyers, temple goldsmiths, and *kadaisal* lacquer-turners."
    }
]

EDGES = [
    [
        "text-silappadikaram-kalittokai-and-chola-charters-on-cevv-arakku-lac-and-seals",
        "describes",
        "artifact-kombarakku-stick-lac-arakku-kuchi-sealing-wax-and-alathagam-crimson-dye-cakes",
        "material_culture",
        "Sangam to Chola Imperial Era",
        "Silappadikaram, Kalittokai, and Chola inscriptions document cevv-arakku resin, crimson alathagam foot-dye pads, and royal signet sealing sticks.",
        "Silappadikaram & Kalittokai"
    ],
    [
        "concept-kerria-lacca-entomology-puvam-host-ecology-and-aleuritic-shellolic-polyester-chemistry",
        "underpins",
        "technology-kombarakku-twig-scraping-stone-vat-laccaic-dye-washing-and-cloth-bag-shellac-melting",
        "material_culture",
        "Iron Age to Modern Era",
        "The separation of water-soluble laccaic acid pigment from thermoplastic aleuritic-shellolic polyester resin governs stone-vat washing and cloth-tube shellac melting.",
        "Indian Lac Research Monographs"
    ],
    [
        "technology-kombarakku-twig-scraping-stone-vat-laccaic-dye-washing-and-cloth-bag-shellac-melting",
        "produces",
        "artifact-kombarakku-stick-lac-arakku-kuchi-sealing-wax-and-alathagam-crimson-dye-cakes",
        "material_culture",
        "Sangam to Modern Era",
        "Vat washing and charcoal-hearth cloth-bag filtration transform raw kombarakku twigs into alathagam dye cakes, mani-arakku seedlac, and arakku-kuchi sticks.",
        "Traditional Lac Refining"
    ],
    [
        "artifact-kombarakku-stick-lac-arakku-kuchi-sealing-wax-and-alathagam-crimson-dye-cakes",
        "enables",
        "concept-arakku-mettuthal-goldsmith-chasing-pitch-and-royal-arakku-muddirai-sigillography",
        "material_culture",
        "Sangam to Modern Era",
        "Refined stick-lac compounded with brick-dust or cinnabar forms goldsmith chasing pitch (arakku-mettuthal) and tamper-evident royal signet seals (arakku-muddirai).",
        "South Indian Inscriptions & Goldsmith Manuals"
    ],
    [
        "concept-kadaisal-arakku-friction-heat-plastification-and-veppalai-wood-turnery-tribology",
        "governs",
        "technology-bow-lathe-veppalai-turning-mineral-pigmented-lac-stick-application-and-taazhai-buffing",
        "material_culture",
        "Medieval to Modern Era",
        "Frictional flash-heating (~85°C) against fine-grained spinning veppalai wood governs dry arakku-kuchi coating and taazhai screw-pine leaf burnishing.",
        "Lac-Turnery Tribology"
    ],
    [
        "technology-bow-lathe-veppalai-turning-mineral-pigmented-lac-stick-application-and-taazhai-buffing",
        "fashions",
        "artifact-lacquered-veppalai-anjaraipetti-spice-boxes-marapachi-wooden-toys-and-choppu-ware",
        "material_culture",
        "Medieval to Modern Era",
        "Lathe turning and mineral-pigmented lac banding produce waterproof anjaraipetti spice towers, bridal kumkumam jars, and choppu-samaan play-sets.",
        "South Indian Toy & Utensil Collections"
    ],
    [
        "institution-forest-kombarakku-collectors-and-kadaisalkarar-lacquer-turnery-guilds",
        "harvests",
        "artifact-kombarakku-stick-lac-arakku-kuchi-sealing-wax-and-alathagam-crimson-dye-cakes",
        "material_culture",
        "Sangam to Modern Era",
        "Indigenous forest collectors manage brood-lac cycles on puvam trees and supply raw kombarakku to foothill Pettai dye and shellac refineries.",
        "Madurai Forest Manuals"
    ],
    [
        "institution-forest-kombarakku-collectors-and-kadaisalkarar-lacquer-turnery-guilds",
        "crafts",
        "artifact-lacquered-veppalai-anjaraipetti-spice-boxes-marapachi-wooden-toys-and-choppu-ware",
        "material_culture",
        "Medieval to Modern Era",
        "Hereditary Kadaisalkarar turner guilds craft lacquered veppalai spice boxes, rattles, and bridal caskets.",
        "Artisan Guild Records"
    ],
    [
        "institution-forest-kombarakku-collectors-and-kadaisalkarar-lacquer-turnery-guilds",
        "operates_in",
        "place-cumbum-ancient-suruli-forest-kombarakku-lac-and-turnery-haven",
        "material_culture",
        "Sangam to Modern Era",
        "Tribal lac-gatherers and Pettai merchants operated across the Suruli-Vannathiparai forest slopes and Cumbum valley market.",
        "Madurai District Gazetteer"
    ],
    [
        "concept-kerria-lacca-entomology-puvam-host-ecology-and-aleuritic-shellolic-polyester-chemistry",
        "flourishes_in",
        "place-cumbum-ancient-suruli-forest-kombarakku-lac-and-turnery-haven",
        "material_culture",
        "Iron Age to Modern Era",
        "Natural stands of Schleichera oleosa (puvam) and Wrightia tinctoria (veppalai) in the Cumbum-Suruli forest belt sustain Kerria lacca colonies and turnery.",
        "Madurai South Forest Working Plans"
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
