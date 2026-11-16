#!/usr/bin/env python3
import os
import sys
import json
import uuid
import psycopg2
import requests

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "bge-m3:latest"
MOOLAM_KNOWLEDGE = "/mnt/h/DevTools/Projects/learn-ai/moolam-chronicles/knowledge"

DOSSIERS = [
  {
    "file": "knowledge/texts/text-perumpanarruppadai-lacquered-woodwork-and-turnery-poetry.md",
    "slug": "text-perumpanarruppadai-lacquered-woodwork-and-turnery-poetry",
    "category": "text",
    "name_en": "Perumpanarruppadai Sangam Verses on Lacquered Turning, Royal Chariots & Polished Woodwork",
    "name_ta": "பெரும்பாணாற்றுப்படை அரக்கு மரக் குடைவு மற்றும் தேர் வண்ணப்பூச்சுப் பாடல்கள்",
    "era": "Sangam Classical Era",
    "year_start": -200,
    "year_end": 100,
    "thinai": "mullai",
    "summary_en": "Perumpanarruppadai and Malaipadukadam verses describing the lustrous crimson and vermilion lac-varnished wooden spokes of royal war chariots, turned wooden cosmetic vessels, and lacquer-sealed weapon shafts crafted by skilled carpenters.",
    "summary_ta": "அரசத் தேர்களின் ஆரக்கால்கள், குடையப்பட்ட மரக் கிண்ணங்கள் மற்றும் படைக்கலக் கைப்பிடிகள் மீது சிவந்த அரக்குக் குழம்பைப் பூசி பளபளப்பாக்கிய மரக் குடைவுத் தொழிலைப் போற்றும் பெரும்பாணாற்றுப்படை மற்றும் மலைபடுகடாம் பாடல்கள்.",
    "sources": [
      "Perumpanarruppadai 45-60, 485-492",
      "Malaipadukadam 100-115",
      "Subrahmanian: Pre-Pallava Tamil Index"
    ],
    "content": "---\nid: text-perumpanarruppadai-lacquered-woodwork-and-turnery-poetry\ntitle: Perumpanarruppadai Sangam Verses on Lacquered Turning, Royal Chariots & Polished Woodwork\ntype: text\nera: Sangam Classical Era (c. 200 BCE - 100 CE)\nthinai: mullai (Artisanal Woodcraft & Royal Chariots)\nstatus: canonical\n---\n\n# Perumpanarruppadai Sangam Verses on Lacquered Turning, Royal Chariots & Polished Woodwork\n\n## 1. Classical References to Lacquer (*Arakku*)\nIn the Sangam anthologies, the resinous exudate of the insect *Kerria lacca* is known as **Arakku (அரக்கு)**. Celebrated for its fiery crimson pigment and glass-like waterproofing qualities, it was extensively employed across royal carpentry and weapon manufacture.\n\nIn *Perumpanarruppadai*, the royal chariot of King Ilandiraiyan of Kanchi is praised:\n> \"செந்நெறி பொருந்திய அரக்கு ஊட்டிய ஆழி...\n> தேர் கொடி நுடங்கப் பொலிந்தன வீதி...\"\n*(The chariot wheels with wooden spokes deeply saturated in glowing red lacquer rolled majestically, their pennants fluttering down the palace avenues).*\n\nIn *Malaipadukadam*, the poet describes tribal hunters and foresters collecting wild insect resin from the branches of *Kusum* (*Schleichera oleosa*) and *Palash* trees along the slopes of Naviram mountain.\n\n## 2. Textual Inventory of Lacquered Artifacts\n1. **Chariot Spokes (*Thaer-Aazhi-Aaram*)**: Teak and rosewood spokes turned smooth on lathes and burnished with molten lac to resist rain and river gravel abrasion.\n2. **Turned Wooden Platters (*Mara-Vattil*)**: Lathe-turned food vessels, cosmetic boxes (*Seppu*), and children's toys treated with non-toxic herbal lacquers.\n3. **Bow Staves & Spear Grips**: Seasoned bamboo and hardwood weapons wrapped in sinew and sealed with waterproof lacquer coats to prevent moisture warping in monsoon warfare.\n"
  },
  {
    "file": "knowledge/inscriptions/insc-ambasamudram-pandya-lacquer-wood-turners-charters.md",
    "slug": "insc-ambasamudram-pandya-lacquer-wood-turners-charters",
    "category": "inscription",
    "name_en": "Ambasamudram Pandya Royal Charters on Lacquer Wood-Turners (Arakku-Thatchar)",
    "name_ta": "அம்பாசமுத்திரம் பாண்டியர் அரக்கு மரக் குடைவோர் பட்டயக் கல்வெட்டுகள்",
    "era": "Early Pandya Era",
    "year_start": 750,
    "year_end": 900,
    "thinai": "marutham",
    "summary_en": "Pandya royal rock inscriptions from Ambasamudram and Brahmadesam on the Tambraparni river granting tax concessions to the guild of lacquer turners (Arakku-Thatchar) who produced turned wooden lacquerware, temple cosmetic boxes, and ceremonial flagstaffs.",
    "summary_ta": "அம்பாசமுத்திரம் மற்றும் பிரம்மதேசம் பகுதிகளில் கண்டறியப்பட்ட தாமிரபரணி நதிக்கரை அரக்கு மரக் குடைவோர் கில்டுக்கு (அரக்குத் தச்சர்) பாண்டிய மன்னர்கள் வழங்கிய வரிச்சலுகைகள் மற்றும் நிலக்கொடைப் பதிவுகள்.",
    "sources": [
      "South Indian Inscriptions Vol. XIV (Early Pandyas)",
      "Epigraphia Indica Vol. IX",
      "Sethi: Traditional Woodcraft Guilds of Tamilakam"
    ],
    "content": "---\nid: insc-ambasamudram-pandya-lacquer-wood-turners-charters\ntitle: Ambasamudram Pandya Royal Charters on Lacquer Wood-Turners (Arakku-Thatchar)\ntype: inscription\nera: Early Pandya Era (c. 750 - 900 CE)\nthinai: marutham (Artisanal Guild Epigraphy)\nstatus: canonical\n---\n\n# Ambasamudram Pandya Royal Charters on Lacquer Wood-Turners (Arakku-Thatchar)\n\n## 1. Epigraphical Provenance\nAmbasamudram (ancient *Ilangoikudi*), located on the fertile banks of the perennial Tambraparni river in Tirunelveli district, was an acclaimed hub for hereditary woodworking guilds.\n\nRock-cut inscriptions on the walls of the Erichcha-Udayar and Brahmadesam temples record royal charters issued under the Early Pandya kings (Varaguna I and Srimara Srivallabha).\n\n## 2. Inscriptional Epigraphical Details\nThe charters enumerate:\n- **Arakku-Kani**: Tax-free residential and agricultural land endowments dedicated to master lathe turners (*Arakku-Thatchar*).\n- **Kudaivu-Pari**: Relief from traditional transit duties (*Sungam*) on cartloads of natural forest resin (*Arakku*) and softwoods brought down from the adjacent Agasthyamalai mountain forests.\n- **Temple Endowments**: Mandates requiring the guild to supply annually twelve turned lacquer containers (*Arakku-Seppu*) for preserving sacred unguents, saffron, and sandalwood paste for royal temple liturgies.\n"
  },
  {
    "file": "knowledge/inscriptions/insc-madurai-chola-temple-chariot-lacquer-coating-epigraphs.md",
    "slug": "insc-madurai-chola-temple-chariot-lacquer-coating-epigraphs",
    "category": "inscription",
    "name_en": "Madurai Chola Temple Chariot Resin Sealing & Weatherproof Lacquer Epigraphs",
    "name_ta": "மதுரை சோழர் திருக்கோயில் மரத்தேர் அரக்குப் பூச்சு மற்றும் வண்ணப்பூச்சுப் பதிவுகள்",
    "era": "Imperial Chola Era",
    "year_start": 1050,
    "year_end": 1250,
    "thinai": "marutham",
    "summary_en": "Chola-Pandya epigraphs in the Meenakshi Sundareswarar temple complex recording royal provisions of seedlac, cold-pressed castor oil, and dammar tree resins allocated for periodic recoating and weatherproofing of colossal wooden temple chariots (Thiruther).",
    "summary_ta": "மதுரை மீனாட்சி சுந்தரேசுவரர் திருக்கோயில் பிரகாரக் கல்வெட்டுகள்; பிரம்மாண்டமான மரத் திருத்தேர்கள் மழையினாலும் வெயிலினாலும் சேதமடையாமல் பாதுகாக்க அரக்கு, ஆமணக்கு எண்ணெய் மற்றும் குங்கிலியப் பூச்சுக்கான நிபந்தனைகள்.",
    "sources": [
      "South Indian Inscriptions Vol. V",
      "Madurai Temple Inscriptions (TN State Dept of Archaeology)"
    ],
    "content": "---\nid: insc-madurai-chola-temple-chariot-lacquer-coating-epigraphs\ntitle: Madurai Chola Temple Chariot Resin Sealing & Weatherproof Lacquer Epigraphs\ntype: inscription\nera: Imperial Chola Era (c. 1050 - 1250 CE)\nthinai: marutham (Monumental Timber Preservation)\nstatus: canonical\n---\n\n# Madurai Chola Temple Chariot Resin Sealing & Weatherproof Lacquer Epigraphs\n\n## 1. Context of Monumental Chariot Preservation\nThe colossal multi-tiered wooden temple chariots (*Perunther*) of Tamilakam—often weighing over 40 to 80 tons and carved with thousands of intricate mythological relief sculptures in *Ilupai* and teakwood—required constant chemical shielding against tropical monsoonal rot and insect attack.\n\n## 2. Inscriptional Allocations of Resins\nThe Madurai epigraphical records detail:\n- **Mara-Varna-Padi (மர வண்ணப்பூச்சுக் கொடை)**: Annual allotments of dried seedlac (*Arakku-Mani*), Dammar resin (*Kungiliyam*), and red ochre (*Semman*) to hereditary painters (*Varnakkaran*).\n- **Application Cadence**: Directives requiring the recoating of the chariot wheels, axle-trees, and base panel friezes prior to the annual Chithirai festival procession.\n- **Protective Efficacy**: The resinous shellac barrier formed an impermeable, highly elastic polymer that expanded and contracted with temperature fluctuations without cracking the delicate wood carvings underneath.\n"
  },
  {
    "file": "knowledge/concepts/concept-forest-insect-lac-resin-harvesting-and-seedlac-purification-arakku.md",
    "slug": "concept-forest-insect-lac-resin-harvesting-and-seedlac-purification-arakku",
    "category": "concept",
    "name_en": "Kerria Lacca Insect Resin Harvesting, Hot Water Dewaxing & Seedlac Purification (Arakku)",
    "name_ta": "காட்டு அரக்குப் பூச்சிப் பிசின் அறுவடை, வெந்நீர் மெழுகு நீக்கம் மற்றும் சுத்திகரிப்பு நுட்பம்",
    "era": "Early Historic Era",
    "year_start": -400,
    "year_end": 500,
    "thinai": "kurinji",
    "summary_en": "The bio-chemical extraction and refining of natural lac (Arakku): collecting encrusted twigs (sticklac) of Kerria lacca insects from forest host trees, crushing, washing in hot water baths to dissolve water-soluble red dye (laccaic acid), and melting through cloth sieves into purified seedlac and shellac buttons.",
    "summary_ta": "காட்டு மரங்களில் வளரும் அரக்குப் பூச்சியின் பிசினை (கொம்பு அரக்கு) சேகரித்து, இடித்து, வெந்நீரில் கழுவி சிவப்புச் சாயத்தைப் பிரித்தெடுத்து, துணி வடிகட்டிகள் வழியே உருக்கி மெழுகற்ற தூய அரக்காக மாற்றிய பண்டைய உயிரி-வேதியியல் நுட்பம்.",
    "sources": [
      "Bose et al.: Chemistry of Lac & Natural Resins",
      "Watt: Commercial Products of India (Lac)",
      "Glover: Lac Cultivation in India"
    ],
    "content": "---\nid: concept-forest-insect-lac-resin-harvesting-and-seedlac-purification-arakku\ntitle: Kerria Lacca Insect Resin Harvesting, Hot Water Dewaxing & Seedlac Purification (Arakku)\ntype: concept\nera: Early Historic Era (c. 400 BCE - 500 CE)\nthinai: kurinji (Natural Polymer Chemistry)\nstatus: canonical\n---\n\n# Kerria Lacca Insect Resin Harvesting, Hot Water Dewaxing & Seedlac Purification (Arakku)\n\n## 1. Biology and Forest Harvesting of Sticklac\n**Lac** is the scarlet, resinous secretion produced by the tiny scale insect **Kerria lacca** (family Kerriidae). In ancient Tamilakam, the insects colonized specific host trees in the dry deciduous foothills of the Western and Eastern Ghats:\n- *Schleichera oleosa* (*Kusum / Poovan*)\n- *Butea monosperma* (*Palash / Murukku*)\n- *Ziziphus mauritiana* (*Ber / Elandhai*)\n\nTribal forest gatherers (*Kaadar* / *Kanikkar*) harvested the encrusted twigs, known technically as **sticklac** (*Kombu-Arakku*).\n\n## 2. Chemical Refining & Separation\nRaw sticklac contains roughly 68% resinous polyesters, 10% water-soluble dye, 6% natural wax, and 16% woody debris and insect debris.\n\n### The Refining Sequence:\n1. **Crushing & Grading**: The encrustations were scraped from the twigs and pounded gently in stone mortars into grain-sized granules.\n2. **Water Washing (*Arakku-Kazhuvuthal*)**: The crushed granules were soaked in vats of warm water and agitated by foot or wooden pestles. The water-soluble anthraquinone dye (**laccaic acid**) dissolved into the bath, yielding a valuable red textile mordant dye.\n3. **Decantation & Dewaxing**: The remaining insoluble resin grains (**seedlac** / *Arakku-Mani*) were skimmed and dried on mats in the shade.\n4. **Thermal Bag Filtration**: The seedlac was packed into long, narrow woven cotton tubes and suspended near an open charcoal hearth. As the tube was twisted under heat (110–120°C), molten purified resin extruded through the cloth weave, leaving behind woody impurities and wax.\n"
  },
  {
    "file": "knowledge/concepts/concept-thermal-friction-lathe-turnery-with-pigmented-lac-sticks.md",
    "slug": "concept-thermal-friction-lathe-turnery-with-pigmented-lac-sticks",
    "category": "concept",
    "name_en": "High-Speed Wood Lathe Turnery, Thermal Friction Melting & Pigmented Lac Stick Burnishing",
    "name_ta": "அதிவேகக் குடைவுப் பட்டறை, உராய்வு வெப்ப உருக்கம் மற்றும் வண்ண அரக்கு மினுக்கு நுட்பம்",
    "era": "Early Historic Era",
    "year_start": -300,
    "year_end": 500,
    "thinai": "mullai",
    "summary_en": "The pyrotechnic lathe physics of Tamil lacquerware (Arakku-Kudaivu): spinning seasoned hardwood items on bow-driven or treadle lathes, pressing dry sticks of purified lac pigmented with mineral ochre, vermilion (Chinduram), or turmeric against the whirling wood to generate frictional heat (120-140°C) that melts and bonds the lacquer, followed by screw-pine leaf burnishing.",
    "summary_ta": "வில்-குடைவுப் பட்டறையில் வேகமாகச் சுழலும் மர உருளைகள் மீது தாது வண்ணங்கள் கலந்த அரக்குக் குச்சிகளை அழுத்தி, உராய்வு வெப்பத்தினால் (120-140°C) அரக்கை உருகவைத்து மரத்தோடு பிணைத்து, தாழம்பூ மடலால் தேய்த்து பளபளப்பாக்கும் மரக்கலை நுட்பம்.",
    "sources": [
      "Mukharji: Art-Manufactures of India",
      "Dhamija: Indian Folk Arts and Crafts",
      "Saraf: Indian Crafts"
    ],
    "content": "---\nid: concept-thermal-friction-lathe-turnery-with-pigmented-lac-sticks\ntitle: High-Speed Wood Lathe Turnery, Thermal Friction Melting & Pigmented Lac Stick Burnishing\ntype: concept\nera: Early Historic Era (c. 300 BCE - 500 CE)\nthinai: mullai (Pyrotechnic Friction Mechanics & Woodcraft)\nstatus: canonical\n---\n\n# High-Speed Wood Lathe Turnery, Thermal Friction Melting & Pigmented Lac Stick Burnishing\n\n## 1. The Bow-Lathe Mechanism (*Villu-Kudaivu*)\nThe ancient Tamil wood-turning lathe consisted of two forged iron pivots (*Aani-munaigal*) driven into upright wooden posts pegged into the earth. The seasoned wood blank (typically *Wrightia tinctoria* / *Veppalai*, or teak) was mounted between the centers and rotated reciprocally by a hemp bowstring wrapped around the workpiece.\n\n## 2. Formulation of Pigmented Lac Sticks (*Battis*)\nPurified seedlac was heated over a charcoal brazier and compounded with mineral pigments:\n- **Vermilion / Red**: Cinnabar (*Chinduram*) or red iron oxide (*Semman*).\n- **Yellow**: Finely powdered turmeric (*Manjal*) or yellow orpiment (*Aritharam*).\n- **Black**: Calcined bone charcoal or lampblack (*Mai*).\n- **Green**: Indigo leaf extract blended with yellow orpiment.\n\nThe molten compound was rolled by hand on wet stone slabs into uniform cylindrical sticks (*Arakku-kuchi*).\n\n## 3. Frictional Thermoplastic Bonding\nWhen the wood workpiece reaches a rotational speed exceeding 800–1200 RPM, the turner presses the lac stick firmly against the spinning surface:\n1. **Frictional Heat Generation**: The mechanical shear generates localized frictional heat:\n   $$Q = \\mu \\cdot F_N \\cdot v_{\\text{surface}}$$\n   Where $\\mu$ is the friction coefficient, $F_N$ is normal force applied by the artisan's hand, and $v$ is tangential surface velocity.\n2. **Phase Change & Fusion**: As the temperature surpasses 120°C, the lac softens and melts instantly, flowing into the micro-porosities and vascular bundles of the wood.\n3. **Burnishing with Pandanus Leaf**: Immediately following application, a dry strip of screw-pine leaf (*Thazhai*) containing natural silica and waxes is pressed hard against the spinning workpiece, polishing the surface to an mirror-smooth, waterproof finish.\n"
  },
  {
    "file": "knowledge/concepts/concept-resin-dammar-waterproof-varnishing-and-wood-sealing.md",
    "slug": "concept-resin-dammar-waterproof-varnishing-and-wood-sealing",
    "category": "concept",
    "name_en": "Shorea Dammar Resin Dissolution in Plant Oils, Penetrative Wood Sealing & Waterproof Varnishes",
    "name_ta": "குங்கிலியப் பிசின் எண்ணெய் கரைசல், மர உட்புகு சீரமைப்பு மற்றும் நீர்ப்புகா வார்னிஷ் பூச்சு",
    "era": "Early Historic Era",
    "year_start": -300,
    "year_end": 400,
    "thinai": "mullai",
    "summary_en": "The chemical formulation of ancient Tamil waterproof wood varnishes (Mara-Varnam): dissolving pulverized Dammar tree resin (Kungiliyam / Shorea roxburghii) in warm cold-pressed castor, linseed, or sesame oils, creating a deeply penetrative, flexible oil-resin varnish that seals monumental timber from fungi, moisture, and marine borers.",
    "summary_ta": "மரங்களை அழுகாமல் பாதுகாக்க குங்கிலியப் பிசினை ஆமணக்கு அல்லது நல்லெண்ணெயில் காய்ச்சி வடித்த இயற்கை வார்னிஷ்; மரத் துளைகளுக்குள் ஆழமாக இறங்கி பூஞ்சை, ஈரம் மற்றும் மரவண்டுகளிடமிருந்து பாதுகாக்கும் வேதியியல் நுட்பம்.",
    "sources": [
      "Kerr: Natural Varnishes of Southern India",
      "Mantell: The Technology of Natural Resins",
      "Indian Forester Records on Shorea Resins"
    ],
    "content": "---\nid: concept-resin-dammar-waterproof-varnishing-and-wood-sealing\ntitle: Shorea Dammar Resin Dissolution in Plant Oils, Penetrative Wood Sealing & Waterproof Varnishes\ntype: concept\nera: Early Historic Era (c. 300 BCE - 400 CE)\nthinai: mullai (Organic Polymer Technology)\nstatus: canonical\n---\n\n# Shorea Dammar Resin Dissolution in Plant Oils, Penetrative Wood Sealing & Waterproof Varnishes\n\n## 1. Dammar Resin Chemistry (*Kungiliyam*)\n**Kungiliyam** is an aromatic triterpenoid oleoresin tapped from towering Dipterocarp forest trees, particularly *Shorea roxburghii* (syn. *Shorea talura*) and *Canarium strictum* (black dammar), native to the moist evergreen forests of the Western Ghats.\n\nUnlike insect lac, dammar contains complex triterpenic acids and resenes that are insoluble in water but readily soluble in drying plant oils when heated.\n\n## 2. Oil-Varnish Formulation Physics\n1. **Oil Heating**: Cold-pressed castor oil (*Vilakkennai* / ricinoleic acid triglyceride) or linseed oil is gently boiled in a copper cauldron to drive off residual moisture.\n2. **Resin Digestion**: Finely powdered dammar crystals are gradually stirred into the hot oil (160–180°C). The thermal energy breaks the cross-linked resin clusters, forming a homogeneous colloidal solution.\n3. **Viscosity Control**: The hot varnish exhibits low surface tension, allowing it to penetrate deep into wood tracheids through capillary action:\n   $$h = \\frac{2\\gamma \\cos\\theta}{\\rho g r}$$\n   Where $\\gamma$ is the surface tension of the oil-resin mixture and $r$ is the pore radius of the wood vessel.\n\n## 3. Barrier Performance\nUpon air exposure, the unsaturated fatty acid chains in the oil undergo oxidative cross-linking (polymerization), while the dammar resenes form a tough, water-repellent, elastic glass that shields ship timbers, chariot frames, and domestic structural beams for decades.\n"
  },
  {
    "file": "knowledge/concepts/concept-temple-chariot-and-weapon-shaft-weatherproof-lacquer-coatings.md",
    "slug": "concept-temple-chariot-and-weapon-shaft-weatherproof-lacquer-coatings",
    "category": "concept",
    "name_en": "Monumental Wooden Temple Chariots, Bow Staves & Weapon Shaft Weatherproof Lacquer Shielding",
    "name_ta": "திருக்கோயில் மரத்தேர்ச் சிற்பங்கள் மற்றும் வில்-படைக்கலக் கைப்பிடி அரக்குப் பாதுகாப்பு",
    "era": "Classical to Medieval Era",
    "year_start": 300,
    "year_end": 1300,
    "thinai": "marutham",
    "summary_en": "The conservation technology of multi-layered lacquer and herbal resin varnishing applied to massive wooden temple chariots (Rathas), archery bow staves, and military lance shafts to impart tensile flexibility, weather resistance, and brilliant aesthetic polychromy.",
    "summary_ta": "பெரும் மரத் தேர்கள், விற்கள் மற்றும் ஈட்டித் தண்டுகள் மீது பல அடுக்குகளாகப் பூசப்பட்ட மூலிகை அரக்கு மற்றும் குங்கிலிய வண்ணப்பூச்சுகள்; இழுவிசை நெகிழ்வுத்தன்மை, நீர்ப்புகா உறுதி மற்றும் நீண்ட கால வண்ணப் பாதுகாப்பை வழங்கிய பாதுகாப்புத் தொழில்நுட்பம்.",
    "sources": [
      "Dagens: Architecture in the Ajitagama",
      "Saraswati: The Chariots of Tamil Nadu",
      "Nilakanta Sastri: The Cholas"
    ],
    "content": "---\nid: concept-temple-chariot-and-weapon-shaft-weatherproof-lacquer-coatings\ntitle: Monumental Wooden Temple Chariots, Bow Staves & Weapon Shaft Weatherproof Lacquer Shielding\ntype: concept\nera: Classical to Medieval Era (c. 300 - 1300 CE)\nthinai: marutham (Monumental Timber Preservation)\nstatus: canonical\n---\n\n# Monumental Wooden Temple Chariots, Bow Staves & Weapon Shaft Weatherproof Lacquer Shielding\n\n## 1. Multi-Layer Coating Architecture\nPreserving outdoor monumental timber in a tropical climate with alternating torrential monsoon rain and intense solar ultraviolet radiation required a specialized **multi-stratum coating system**:\n\n1. **Substrate Primer (*Adithalam*)**: Deep soaking with hot dammar-castor oil varnish that saturates dry wood fibers and arrests fungal rot.\n2. **Leveling Ground (*Semman-Kuzhambu*)**: Fine red ochre clay mixed with gum arabic or animal glue rubbed into grain pores to produce a perfectly flat surface.\n3. **Lacquer Color Layers**: Multiple brushings of purified seedlac dissolved in fermented alcohol (*Kallu-saaru*) pigmented with cinnabar, lampblack, or mineral yellow.\n4. **Final Protective Clear Glaze**: High-sheen dewaxed shellac burnished with oil rags, forming an impenetrable barrier against moisture, humidity, and UV degradation.\n\n## 2. Archery & Weapon Applications\nFor composite recurve bows (*Villu*) and spear shafts (*Vel*), flexibility was paramount. Pure lac films are naturally pliable; unlike brittle synthetic varnishes, shellac expands and flexes synchronously with bending wood fibers under maximum draw tension without cracking or spalling off.\n"
  },
  {
    "file": "knowledge/characters/char-ambasamudram-master-lacquer-turner-arakku-thatchan.md",
    "slug": "char-ambasamudram-master-lacquer-turner-arakku-thatchan",
    "category": "character",
    "name_en": "Master Wood Turner & Lacquer Polish Artisan: Arakku Thatchan of Ambasamudram",
    "name_ta": "அம்பாசமுத்திரம் பெருங்குடைவு மரக்கலைஞர் மற்றும் அரக்குத் தச்சன்",
    "era": "Early Pandya Era",
    "year_start": 750,
    "year_end": 850,
    "thinai": "marutham",
    "summary_en": "Epitome of the skilled Tamil wood turners in the Tambraparni valley celebrated for lathe-turned lacquer platters, ritual unguent containers (Seppu), children's toys, and polished furniture crafted from indigenous riverine hardwoods.",
    "summary_ta": "தாமிரபரணி நதிக்கரையில் அமைந்துள்ள அம்பாசமுத்திரத்தில் வில்-குடைவுப் பட்டறை அமைத்து வண்ண அரக்குக் குச்சிகளைக் கொண்டு அரசப் பேழைகள் மற்றும் மினுக்கு மரப் பொருட்களை உருவாக்கிய தலைமைத் தச்சர்.",
    "sources": [
      "Ambasamudram Temple Inscriptions",
      "Traditional Woodcraft of Southern Tamil Nadu"
    ],
    "content": "---\nid: char-ambasamudram-master-lacquer-turner-arakku-thatchan\ntitle: Master Wood Turner & Lacquer Polish Artisan: Arakku Thatchan of Ambasamudram\ntype: character\nera: Early Pandya Era (c. 750 - 850 CE)\nthinai: marutham (Artisanal Wood Turnery)\nstatus: canonical\n---\n\n# Master Wood Turner & Lacquer Polish Artisan: Arakku Thatchan of Ambasamudram\n\n## 1. Craft Lineage & Workshop Practice\nStationed in the artisan quarter flanking the Tambraparni river, the **Arakku Thatchan** inherited a multi-generational legacy of precision woodcraft. His proximity to both the evergreen forests of the Western Ghats (for timber and raw lac) and the riverine royal markets ensured access to premium raw materials.\n\n## 2. Mastered Techniques\n- **Selective Timber Seasoning**: Submerging freshly cut *Veppalai* logs in river mud for six months to purge fermentable starches and prevent subsequent insect borers.\n- **Bi-directional Bow Turning**: Effortlessly coordinating the reciprocating bow with one hand while manipulating gouges and scrapers with his toes and other hand.\n- **Friction Polishing**: Applying multi-colored bands of red, yellow, and black lac in a single rapid turnery session, followed by pandanus leaf burnishing.\n\n## 3. Enduring Heritage\nHis guild laid the technical foundation for the celebrated Ambasamudram and Cheranmahadevi turned wooden toy and lacquerware industries that thrive to this day.\n"
  },
  {
    "file": "knowledge/characters/char-madurai-temple-wood-finisher-mara-varnakkaran.md",
    "slug": "char-madurai-temple-wood-finisher-mara-varnakkaran",
    "category": "character",
    "name_en": "Royal Chariot Polisher & Herbal Resin Finisher: Mara-Varnakkaran of Madurai",
    "name_ta": "மதுரை சோழர் அரசத் தேர் மற்றும் மர வண்ணப்பூச்சுக் கலைஞர்",
    "era": "Imperial Chola Era",
    "year_start": 1050,
    "year_end": 1150,
    "thinai": "marutham",
    "summary_en": "The chief preservative varnish specialist of the royal temple foundries in Madurai, responsible for formulating dammar-castor oil sealants and pigmented shellac coatings to preserve colossal temple chariots and palace woodwork.",
    "summary_ta": "மதுரைக் கோயில்கள் மற்றும் அரண்மனைத் தேர்களை மழை, பூச்சி மற்றும் வெயிலிலிருந்து காக்க குங்கிலிய வார்னிஷ் மற்றும் பல வண்ண அரக்குப் பூச்சுகளைத் தயாரித்துப் பூசிய தலைமை வண்ணப்பூச்சுக் கலைஞர்.",
    "sources": [
      "Madurai Inscriptions (SII Vol. V)",
      "Tamil Temple Vastu & Silpa Traditions"
    ],
    "content": "---\nid: char-madurai-temple-wood-finisher-mara-varnakkaran\ntitle: Royal Chariot Polisher & Herbal Resin Finisher: Mara-Varnakkaran of Madurai\ntype: character\nera: Imperial Chola Era (c. 1050 - 1150 CE)\nthinai: marutham (Monumental Chariot Preservation)\nstatus: canonical\n---\n\n# Royal Chariot Polisher & Herbal Resin Finisher: Mara-Varnakkaran of Madurai\n\n## 1. Office and Responsibilities\nIn the great urban temple economy of Madurai, the **Mara-Varnakkaran** presided over the conservation of colossal wooden processional architecture. Operating from the temple workshops, his task was to maintain the structural integrity and brilliant iconography of the royal chariots.\n\n## 2. Chemical Formulations\n1. **Anti-Termite Pre-Treatments**: Infusing timber with bitter extracts of neem (*Azadirachta indica*) and wild ginger before applying resin primers.\n2. **Hot Oil-Dammar Cooking**: Supervising the perilous thermal dissolution of crystalline dammar resins in boiling castor oil cauldrons.\n3. **Polychrome Execution**: Embellishing figurative reliefs of deities, dancers, and mythical creatures (*Yalis*) with vibrant red, vermilion, and gold-leaf coatings sealed under protective shellac glazes.\n"
  },
  {
    "file": "knowledge/places/place-ambasamudram-ancient-lacquer-turnery-haven.md",
    "slug": "place-ambasamudram-ancient-lacquer-turnery-haven",
    "category": "place",
    "name_en": "Ambasamudram: Ancient Lacquer Woodcraft Haven & Tambraparni Turnery Guilds",
    "name_ta": "அம்பாசமுத்திரம் - பண்டைய அரக்கு மரக் குடைவுத் தளம் மற்றும் தாமிரபரணி தச்சர் குடியிருப்பு",
    "era": "Pandya Classical to Medieval Era",
    "year_start": 700,
    "year_end": 1600,
    "thinai": "marutham",
    "summary_en": "Historic riverine town on the upper Tambraparni river in southern Tamil Nadu renowned for over a millennium of fine wood turning, natural lacquerware manufacture (Arakku-Seppu), and skilled artisanal woodworking guilds.",
    "summary_ta": "தென் தமிழகத்தில் தாமிரபரணி நதிக்கரையில் அமைந்துள்ள வரலாற்றுச் சிறப்புமிக்க மரக் குடைவுத் தொழிற்பட்டினம்; ஆயிரம் ஆண்டுகளுக்கும் மேலாக அரக்கு மரப் பாண்டங்கள் மற்றும் அழகிய மரச் சிற்பங்களை உருவாக்கிய தச்சர் தலைநகர்.",
    "sources": [
      "Tirunelveli District Gazetteer",
      "ASI Reports on Tambraparni Valley Crafts",
      "South Indian Inscriptions Vol. XIV"
    ],
    "content": "---\nid: place-ambasamudram-ancient-lacquer-turnery-haven\ntitle: Ambasamudram: Ancient Lacquer Woodcraft Haven & Tambraparni Turnery Guilds\ntype: place\nera: Pandya Classical to Medieval Era (c. 700 - 1600 CE)\nthinai: marutham (Riverine Woodcraft Geography)\nstatus: canonical\n---\n\n# Ambasamudram: Ancient Lacquer Woodcraft Haven & Tambraparni Turnery Guilds\n\n## 1. Geographic & Environmental Advantage\n**Ambasamudram** (lat 8.7000° N, lng 77.4500° E), historically known as *Ilangoikudi*, lies in the fertile upper floodplain of the Tambraparni river, directly downstream from the evergreen rainforests of the Agasthyamalai biosphere reserve. \n\nThis location provided an incomparable natural resource junction:\n- Abundant softwoods ideal for turning (*Wrightia tinctoria* / *Veppalai*).\n- Direct access to forest-harvested insect lac (*Arakku*) and dammar tree resins (*Kungiliyam*).\n- Clean river water for washing seedlac and floating timber rafts down from the mountains.\n\n## 2. Artisanal Legacy & Guild Organization\nUnder the patronage of the Early Pandyas and Later Cholas, Ambasamudram emerged as the premier lacquerware and wood-turning center of the southern Tamil country. Hereditary artisan guilds (*Thatchar*) established large open-air lathe workshops along the riverbanks, producing:\n- Lacquered cosmetic caskets (*Arakku-Seppu*)\n- Cylindrical spice and medicine containers\n- Turnery legs for royal cots and temple litters\n- Children's rattles and toys (*Marapachi*)\n\n## 3. Modern Continuation\nThe wood-turning tradition pioneered in ancient Ambasamudram continues to be practiced by traditional artisan families, preserving classical techniques of friction-melting natural lac sticks on spinning wood.\n"
  }
]
EDGES = [
  [
    "text-perumpanarruppadai-lacquered-woodwork-and-turnery-poetry",
    "celebrates_lacquered_chariots",
    "concept-temple-chariot-and-weapon-shaft-weatherproof-lacquer-coatings",
    "cultural",
    "Sangam Classical Era",
    "Sangam verses praising red-lacquered royal chariot wheels and spokes",
    "Perumpanarruppadai 45-60"
  ],
  [
    "insc-ambasamudram-pandya-lacquer-wood-turners-charters",
    "grants_charters_to_guild_at",
    "place-ambasamudram-ancient-lacquer-turnery-haven",
    "epigraphical",
    "Early Pandya Era",
    "Pandya royal charters granting tax concessions to wood-turner guilds",
    "SII Vol. XIV"
  ],
  [
    "insc-madurai-chola-temple-chariot-lacquer-coating-epigraphs",
    "records_resin_applications_for",
    "concept-temple-chariot-and-weapon-shaft-weatherproof-lacquer-coatings",
    "epigraphical",
    "Imperial Chola Era",
    "Inscriptions detailing annual seedlac and dammar allocations for chariots",
    "SII Vol. V"
  ],
  [
    "concept-forest-insect-lac-resin-harvesting-and-seedlac-purification-arakku",
    "supplies_purified_resin_for",
    "concept-thermal-friction-lathe-turnery-with-pigmented-lac-sticks",
    "technological",
    "Early Historic Era",
    "Extracted seedlac compounded into colored sticks for friction lathe polishing",
    "Watt: Commercial Products"
  ],
  [
    "concept-thermal-friction-lathe-turnery-with-pigmented-lac-sticks",
    "practiced_by_master_turners_at",
    "place-ambasamudram-ancient-lacquer-turnery-haven",
    "industrial",
    "Early Historic Era",
    "Turnery guilds on the Tambraparni practicing high-speed bow-lathe friction lacquering",
    "Ambasamudram Crafts"
  ],
  [
    "concept-resin-dammar-waterproof-varnishing-and-wood-sealing",
    "combined_with_shellac_in",
    "concept-temple-chariot-and-weapon-shaft-weatherproof-lacquer-coatings",
    "chemical",
    "Early Historic Era",
    "Dammar-castor oil primers sealed under weather-resistant shellac glazes",
    "Kerr 1890"
  ],
  [
    "char-ambasamudram-master-lacquer-turner-arakku-thatchan",
    "turned_lacquerware_at",
    "place-ambasamudram-ancient-lacquer-turnery-haven",
    "social",
    "Early Pandya Era",
    "Master artisan crafting turned cosmetic boxes and lacquered furniture",
    "Tambraparni Guilds"
  ],
  [
    "char-madurai-temple-wood-finisher-mara-varnakkaran",
    "applied_weatherproof_coatings",
    "concept-temple-chariot-and-weapon-shaft-weatherproof-lacquer-coatings",
    "technological",
    "Imperial Chola Era",
    "Formulating protective resin varnishes for monumental temple chariots",
    "Madurai Inscriptions"
  ],
  [
    "char-ambasamudram-master-lacquer-turner-arakku-thatchan",
    "mastered_friction_turnery",
    "concept-thermal-friction-lathe-turnery-with-pigmented-lac-sticks",
    "technological",
    "Early Pandya Era",
    "Frictional thermal melting of lac sticks against whirring lathe workpieces",
    "Traditional Woodcraft"
  ],
  [
    "concept-forest-insect-lac-resin-harvesting-and-seedlac-purification-arakku",
    "praised_in_sangam_verse",
    "text-perumpanarruppadai-lacquered-woodwork-and-turnery-poetry",
    "cultural",
    "Sangam Classical Era",
    "Sangam descriptions of wild insect resin harvesting and crimson dyes",
    "Malaipadukadam 100-115"
  ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 20 Corpus 3: Natural Lacquer & Wood Turnery into Moolam Chronicles & Life Graph...")
    os.makedirs(MOOLAM_KNOWLEDGE, exist_ok=True)

    # Phase 1: Write Markdown Files
    print("\n[Phase 1] Writing 10 Markdown Knowledge Dossiers...")
    for d in DOSSIERS:
        full_path = os.path.join("/mnt/h/DevTools/Projects/learn-ai/moolam-chronicles", d["file"])
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(d["content"].strip() + "\n")
        print(f"  ✓ Wrote: {d['file']}")

    # Phase 2: PostgreSQL Lore Nodes Upsert
    print(f"\n[Phase 2] Connecting to PostgreSQL at {DB_URL}...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    nodes_upserted = 0
    for d in DOSSIERS:
        slug = d["slug"]
        cur.execute("""
            INSERT INTO lore_nodes (
                slug, node_type, name_en, name_ta, era, year_start, year_end,
                thinai, summary_en, summary_ta, properties, sources
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
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
                properties = EXCLUDED.properties,
                sources = EXCLUDED.sources;
        """, (
            slug,
            d["category"],
            d["name_en"],
            d["name_ta"],
            d["era"],
            d["year_start"],
            d["year_end"],
            d["thinai"],
            d["summary_en"],
            d["summary_ta"],
            json.dumps({"category": d["category"], "canonical_file": d["file"]}),
            d["sources"]
        ))
        nodes_upserted += 1
        print(f"  ✓ Upserted node: {slug}")

    conn.commit()
    print(f"Phase 2 complete: {nodes_upserted} lore nodes upserted.")

    # Phase 3: Relational Cross-Domain Edges
    print(f"\n[Phase 3] Inserting {len(EDGES)} Relational Cross-Domain Edges...")
    edges_inserted = 0
    for edge in EDGES:
        src, rel, tgt, layer, era, desc, evidence = edge
        cur.execute("""
            DELETE FROM lore_edges 
            WHERE source_slug = %s AND target_slug = %s AND relation_type = %s;
        """, (src, tgt, rel))

        cur.execute("""
            INSERT INTO lore_edges (
                id, source_slug, relation_type, target_slug,
                layer, era, description, evidence_source
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            );
        """, (
            str(uuid.uuid4()), src, rel, tgt, layer, era, desc, evidence
        ))
        edges_inserted += 1
        print(f"  ✓ Linked: ({src}) --[{rel}]--> ({tgt})")

    conn.commit()
    print(f"Phase 3 complete: {edges_inserted} edges processed.")

    # Phase 4: Vector Embeddings
    print("\n[Phase 4] Generating 1024-dim BGE-M3 Embeddings via Ollama...")
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
                f"shelf-{d['category']}",
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

    print(f"\n🎉 Batch 20 Corpus 3: Natural Lacquer & Wood Turnery Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
