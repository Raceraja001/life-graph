#!/usr/bin/env python3
"""
Triple Civilizational Expansion Harvester (Batch 19):
1. Ancient Tamil Jaina Cavern Architecture, Granitic Rock Splitting & Drip-Ledge Epigraphy (10 dossiers)
2. Ancient Tamil Carnelian Lapidary, Alkaline Chemical Etching & Micro-Drilling Mechanics (10 dossiers)
3. Ancient Tamil Counterpoise Well Irrigation, Picottah Levers (Ettam) & Kapilai Water Lifts (10 dossiers)

Total: 30 Canonical Dossiers, 30 Relational Edges, 60 Dense 1024-dim BGE-M3 Embeddings.
"""

import os
import sys
import json
import uuid
import time
import urllib.request
import psycopg2

DB_URL = "postgresql://life_graph:life_graph@localhost:55432/life_graph"
OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embeddings"
MOOLAM_KNOWLEDGE = "/mnt/h/DevTools/Projects/learn-ai/moolam-chronicles/knowledge"

def get_bge_embedding(text_str: str) -> list[float]:
    payload = json.dumps({
        "model": "bge-m3:latest",
        "prompt": text_str[:4000]
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_EMBED_URL,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))["embedding"]

DOSSIERS = [
  {
    "slug": "text-sangam-jaina-ascetic-cavern-and-renunciation-poetry",
    "category": "texts",
    "file": "text-sangam-jaina-ascetic-cavern-and-renunciation-poetry.md",
    "node_type": "text",
    "name_en": "Sangam Jaina Ascetic Cavern Hymns, Mountain Hermitages & Renunciation Poetry",
    "name_ta": "சங்ககால சமண முனிவர் குகைப் பள்ளிகள், தவத்துறை மற்றும் துறவறப் பாடல்கள்",
    "era": "Early Historic Era",
    "year_start": -300,
    "year_end": 200,
    "thinai": "kurinji",
    "summary_en": "Classical verses in Maduraikkanchi (ll. 475-490), Silappadikaram (Nadukankathai), and Naladiyar depicting rock-shelter hermitages (Amman-palli) perched on granitic inselbergs around Madurai, ascetic austerities, and stone bed retreats.",
    "summary_ta": "மதுரைக்காஞ்சி, சிலப்பதிகாரம் மற்றும் நாலடியாரில் மதுரையைச் சுற்றியுள்ள குன்றுகளின் இயற்கைக் குகைகளில் அமைந்த சமணப் பள்ளிகள், கல் படுக்கைகள் மற்றும் முனிவர்களின் துறவு வாழ்க்கை பற்றிய செவ்வியல் பாடல்கள்.",
    "sources": [
      "Maduraikkanchi ll. 475-490",
      "Silappadikaram Nadukankathai",
      "Naladiyar v. 140-155"
    ],
    "content": "---\nid: text-sangam-jaina-ascetic-cavern-and-renunciation-poetry\ntitle: Sangam Jaina Ascetic Cavern Hymns, Mountain Hermitages & Renunciation Poetry\ntype: text\nera: Early Historic Era (c. 300 BCE - 200 CE)\nthinai: kurinji (Montane Ascetic Hermitages)\nstatus: canonical\n---\n\n# Sangam Jaina Ascetic Cavern Hymns, Mountain Hermitages & Renunciation Poetry\n\n## 1. Classical Primary Source Citations\n- **Maduraikkanchi** (ll. 475–490): Mankudi Maruthanar describes the eight sacred hills encircling Madurai (*En-perum-kundram*), where Jaina monks (*Samanar* / *Arivar*) resided in wind-swept cavern overhangs, dedicating their lives to non-violence (*Kollamai*), meditation, and teaching the Tamil populace.\n- **Silappadikaram** (*Nadukankathai*): Portrays saintly nun Kavunthi Adigal guiding Kovalan and Kannagi past monastic hermitages (*Palli*), where merchant guilds and royal princes endowed stone beds and clean water cisterns for wandering ascetics.\n- **Naladiyar** (vv. 140–155): Anthology of moral quatrains composed by Jaina monks in rock hermitages, reflecting on the impermanence of wealth and the eternal peace of mountain solitudes.\n\n## 2. Spatial Topography of Jaina Monasticism\nAncient Tamilakam witnessed a vibrant ascetic movement centered upon natural granitic boulder inselbergs (*Kazhugumalai*, *Mankulam*, *Arittapatti*, *Kizhavalavu*, *Yanaimalai*, *Sittannavasal*):\n- **Natural Overhangs**: Caverns formed by natural spheroidal weathering of charnockite boulders.\n- **Lithic Modifications**: Transformed by master masons into permanent dwellings via drip-ledges, stone-carved beds, and Tamil-Brahmi donative charters.\n\n## 3. Socio-Religious Integration\nFar from isolated recluses, Jaina cavern communities were integral to early Tamil literacy and urban culture, running free schools (*Nedun-kanakku-palli*) and medical clinics supported by the mercantile elite and the Pandyan crown."
  },
  {
    "slug": "insc-mankulam-nedunchezhiyan-pandya-jaina-cavern-charters",
    "category": "inscriptions",
    "file": "insc-mankulam-nedunchezhiyan-pandya-jaina-cavern-charters.md",
    "node_type": "inscription",
    "name_en": "Mankulam Nedunchezhiyan Pandya Jaina Cavern Charters & Earliest Tamil-Brahmi Epigraphs",
    "name_ta": "மாங்குளம் நெடுஞ்செழியன் பாண்டியர் சமணக் குகைப் பள்ளி மற்றும் முற்காலத் தமிழ்-பிராமி கல்வெட்டுகள்",
    "era": "Early Historic Era",
    "year_start": -300,
    "year_end": -150,
    "thinai": "kurinji",
    "summary_en": "The landmark 3rd-century BCE Tamil-Brahmi rock inscriptions at Mankulam recording King Nedunchezhiyan of the early Pandya dynasty and merchant guild chiefs endowing stone beds and water drip-ledges to the venerable monk Kani-Nandh-Asiriyan.",
    "summary_ta": "மாங்குளம் மீனாட்சிபுரத்துக் குன்றில் உள்ள கி.மு. 3-ஆம் நூற்றாண்டு தமிழ்-பிராமி கல்வெட்டுகள்; பாண்டியன் நெடுஞ்செழியன் மற்றும் வணிகக் குழுக்கள் சமண முனிவர் கனிநந்தாசிரியருக்கு கற்படுக்கை மற்றும் குகைப் பள்ளி அமைத்துக் கொடுத்த வரலாற்று ஆவணங்கள்.",
    "sources": [
      "Iravatham Mahadevan: Early Tamil Epigraphy (2003)",
      "TNSDA Archaeological Survey of Madurai District",
      "South Indian Inscriptions Vol XIV"
    ],
    "content": "---\nid: insc-mankulam-nedunchezhiyan-pandya-jaina-cavern-charters\ntitle: Mankulam Nedunchezhiyan Pandya Jaina Cavern Charters & Earliest Tamil-Brahmi Epigraphs\ntype: inscription\nera: Early Historic Era (c. 300 - 150 BCE)\nthinai: kurinji (Rock Shelter Epigraphy)\nstatus: canonical\n---\n\n# Mankulam: Nedunchezhiyan Pandya Jaina Cavern Charters & Earliest Tamil-Brahmi Epigraphs\n\n## 1. Epigraphical Provenance & Historical Milestone\nDiscovered on the brow of the natural rock shelter on Ovamalai hill at Mankulam (Meenakshipuram) near Madurai, these six inscriptions represent the earliest definitively dated epigraphical records in South India, establishing the historical reality of the Sangam Pandyan dynasty.\n\n## 2. Inscriptional Transliteration & Analysis\n- **Royal Pandya Patronage**: *\"Kaniy nanda-asiriy-ku kal kanchana maruka-nitiy nedu-sazhiyan seyiya-palli\"* — Records that the religious monastery (*Palli*) was commissioned by the brother-in-law (*Kanchana Marukan*) of the great Pandyan king Nedunchezhiyan for the senior Jaina teacher Kani-Nanda-Asiriyan.\n- **Merchant Guild Allotments**: Other panels document gifts of polished stone beds (*Kal-padukai*) endowed by cloth merchants of Vellarai and local agricultural guilds (*Kavithi*).\n\n## 3. Palaeographical Revolution\nPioneering epigraphist Iravatham Mahadevan proved that the Mankulam inscriptions demonstrate the distinct **Tamil-Brahmi (Early Tamil Script)** system:\n- Adapted from the pan-Indian script to accommodate the unique phonology of Old Tamil (creating specific letters for *zh*, *l*, *r*, and *n*).\n- Features inherently vowelled consonants with distinctive stroke notations marking pure consonants (*Pulli*).\n\n## 4. Architectural & Civilizational Significance\nMankulam confirms that 3rd-century BCE Tamil society possessed institutional literacy, organized ascetic monastic orders, advanced stone quarrying techniques, and direct royal patronage of non-violence traditions."
  },
  {
    "slug": "insc-kizhavalavu-tamil-brahmi-stone-bed-donative-epigraphs",
    "category": "inscriptions",
    "file": "insc-kizhavalavu-tamil-brahmi-stone-bed-donative-epigraphs.md",
    "node_type": "inscription",
    "name_en": "Kizhavalavu Tamil-Brahmi Stone Bed Donative Epigraphs & Quarrying Charters",
    "name_ta": "கீழவளவு தமிழ்-பிராமி சமணக் கற்படுக்கை கொடை மற்றும் கல் உடைப்புக் கல்வெட்டுகள்",
    "era": "Early Historic Era",
    "year_start": -200,
    "year_end": 100,
    "thinai": "kurinji",
    "summary_en": "Ancient Tamil-Brahmi rock-cut inscriptions incised above a series of smooth polished granite stone beds on the steep rocky face of Panchapandavamalai at Kizhavalavu near Melur, recording merchant families donating monastic quarters.",
    "summary_ta": "மேலூர் கீழவளவு பஞ்சபாண்டவர் மலையின் செங்குத்துப் பாறையில் தமிழ்-பிராமி எழுத்துக்களால் பொறிக்கப்பட்ட சமணக் கற்படுக்கைகள், தலைப்பகுதி செதுக்கல் மற்றும் வணிகர்கள் வழங்கிய தவத்துறை கொடை ஆவணங்கள்.",
    "sources": [
      "Epigraphia Indica Vol XXXII",
      "TNSDA Epigraphical Bulletin",
      "Mahadevan: Corpus of Tamil-Brahmi Inscriptions"
    ],
    "content": "---\nid: insc-kizhavalavu-tamil-brahmi-stone-bed-donative-epigraphs\ntitle: Kizhavalavu Tamil-Brahmi Stone Bed Donative Epigraphs & Quarrying Charters\ntype: inscription\nera: Early Historic Era (c. 200 BCE - 100 CE)\nthinai: kurinji (Rock-Cut Monastic Epigraphy)\nstatus: canonical\n---\n\n# Kizhavalavu: Tamil-Brahmi Stone Bed Donative Epigraphs & Quarrying Charters\n\n## 1. Epigraphical Provenance & Site Identity\nKizhavalavu is located near Melur in Madurai district on an imposing granitic hillock locally termed *Panchapandavamalai*. The steep natural cliff face shelters over a dozen stone beds carved side-by-side directly into the living granite floor.\n\n## 2. Inscription Text & Dedicatory Formulas\n- **Tamil-Brahmi Inscriptions**: Chiseled horizontally along the outer vertical brow of the rock shelter and directly on the raised pillow ledges of individual beds.\n- **Dedicatory Dedications**: Records personal names of donors—including gold merchants (*Pon-Vanikan*), iron smelters, and agricultural landholders—endowing specific beds (*Atthan*) for meditating ascetics.\n\n## 3. Engineering of the Sheltered Complex\n1. **Drip-Ledge Overhang**: Master stone cutters chiseled a deep, sharp V-shaped channel across the entire exterior overhang to divert monsoon rainsheets away from the living quarters.\n2. **Smooth Granite Beds**: The living granite floor was dressed with fine iron chisels and rubbed with quartz sand until completely level, featuring a raised 5-cm pillow incline at the southern head end.\n\n## 4. Preservation & Epigraphical Value\nThe Kizhavalavu inscriptions establish that ordinary citizens, craft guilds, and provincial merchants actively participated in founding and maintaining monastic retreats across the Pandyan heartland."
  },
  {
    "slug": "concept-granitic-rock-cleaving-wooden-wedge-swelling-mechanics",
    "category": "concepts",
    "file": "concept-granitic-rock-cleaving-wooden-wedge-swelling-mechanics.md",
    "node_type": "concept",
    "name_en": "Granitic Rock Cleaving, Dry Wooden Wedge Swelling Mechanics & Thermal Splitting",
    "name_ta": "கருங்கல் பாறை உடைப்பு, காய்ந்த மர ஆப்பு நீர் விரிவடைதல் மற்றும் வெப்பப் பிளத்தல் இயங்கியல்",
    "era": "Early Historic Era",
    "year_start": -400,
    "year_end": 600,
    "thinai": "kurinji",
    "summary_en": "The mechanical quarrying physics of ancient Tamil stone dressers: cutting aligned rectangular mortise sockets into hard granite rockfaces, driving dry hardwood wedges, and saturating them with water to generate massive hydraulic expansion pressure that cleaved monolithic slabs cleanly along natural grain lines.",
    "summary_ta": "கடின கருங்கல்லில் தொடர் செவ்வகத் துளைகளை வெட்டி, காய்ந்த வேங்கை மர ஆப்புகளை அடித்து, நீர் ஊற்றி மரக்கட்டை விரிவடையும் பேராற்றல் (Hydraulic expansion) மூலம் பாறையை நேர்த்தியாகப் பிளந்த பண்டைய தமிழ்க் குவாரி நுட்பம்.",
    "sources": [
      "Sankalia: Stone Age Tools & Techniques",
      "Ancient Indian Quarrying Engineering",
      "Madurai Monolithic Archaeological Surveys"
    ],
    "content": "---\nid: concept-granitic-rock-cleaving-wooden-wedge-swelling-mechanics\ntitle: Granitic Rock Cleaving, Dry Wooden Wedge Swelling Mechanics & Thermal Splitting\ntype: concept\nera: Early Historic Era (c. 400 BCE - 600 CE)\nthinai: kurinji (Lithic Quarrying Engineering)\nstatus: canonical\n---\n\n# Granitic Rock Cleaving, Dry Wooden Wedge Swelling Mechanics & Thermal Splitting\n\n## 1. The Hardness of South Indian Charnockite Granite\nThe rock shelters of Tamilakam consist of extremely hard, dense charnockite and gneissic granite (Mohs hardness 6 to 7), virtually impossible to shape by brute sledgehammer blows without shattering into irregular jagged fragments. Ancient Tamil quarrymen (*Kal-Ulip-Perunthatchar*) overcame this through mechanical wood-expansion physics.\n\n## 2. The Hydraulic Wedge Splitting Methodology\n1. **Grain Reading (*Kal-Nar-Paarthal*)**: The master quarryman inspected the rock surface to identify the natural crystalline rift lines (*Nar*) and grain direction.\n2. **Chiseling Mortise Slots (*Aappu-Kuzhi*)**: Using narrow, case-hardened iron cold chisels, a linear row of rectangular sockets (length ~8 cm, width ~3 cm, depth ~5 cm) was cut into the rock at intervals of 10 to 15 cm.\n3. **Inserting Dry Hardwood Wedges**: Wedges carved from thoroughly kiln-dried, dense hardwood (Vengai or Tamarind) were driven tightly into every slot with iron mallets.\n4. **Saturation & Swelling Physics**: Water was poured over the dry wooden wedges throughout the night. As the cellular wood fibers absorbed water, the wood underwent hygroscopic expansion, swelling with radial mechanical pressures exceeding 100 to 150 kg/cm².\n5. **Clean Monolithic Cleavage**: The cumulative, uniform expansion force along the line exceeded the tensile strength of the granite, producing a muffled subterranean crack and cleaving an enormous, mirror-flat stone block cleanly off the rockface without internal micro-fracturing.\n\n## 3. Thermal Fire-Splitting Method (*Thee-Moottal*)\nFor massive surface leveling, dried palmyrah logs and straw were burned in long lines across the rock surface. Once the granite was cherry-red, cold water was dashed against the line; the instantaneous thermal contraction induced thermal shock fractures along straight cleavage lines."
  },
  {
    "slug": "concept-drip-ledge-rain-deflection-grooves-kavadi-engineering",
    "category": "concepts",
    "file": "concept-drip-ledge-rain-deflection-grooves-kavadi-engineering.md",
    "node_type": "concept",
    "name_en": "Drip-Ledge Rain Deflection Grooves (Kavadi / Thaara-Vari), Surface Tension & Capillary Cutoff",
    "name_ta": "மழைநீர் விலக்கு விளிம்பு வெட்டு (காடி / தாராவரி), பரப்பு இழுவிசை முறிவு மற்றும் குகைப் பாதுகாப்பு",
    "era": "Early Historic Era",
    "year_start": -300,
    "year_end": 500,
    "thinai": "kurinji",
    "summary_en": "The hydraulic surface-tension physics of rock-cut drip-ledges: chiseling deep continuous V-shaped undercuts across cavern overhang brows to break surface tension, forcing monsoon stormwater sheets to detach and fall clear of living quarters and epigraphical panels.",
    "summary_ta": "பாறை முகப்பில் மழைநீர் வழியும்போது பரப்பு இழுவிசை காரணமாக குகைக்குள் புகாமல் தடுக்க, வெளிப்புற விளிம்பில் தொடர்ச்சியாக வெட்டப்பட்ட ஆழமான 'காடி' (Drip-ledge) மற்றும் நீரியல் விளிம்புப் பொறியியல்.",
    "sources": [
      "Mahadevan: Early Tamil Epigraphy",
      "Archaeological Survey of Rock Caves in Tamil Nadu",
      "Hydraulics of Ancient Rock-Cut Architecture"
    ],
    "content": "---\nid: concept-drip-ledge-rain-deflection-grooves-kavadi-engineering\ntitle: Drip-Ledge Rain Deflection Grooves (Kavadi / Thaara-Vari), Surface Tension & Capillary Cutoff\ntype: concept\nera: Early Historic Era (c. 300 BCE - 500 CE)\nthinai: kurinji (Hydraulic Lithic Engineering)\nstatus: canonical\n---\n\n# Drip-Ledge Rain Deflection Grooves (Kavadi / Thaara-Vari), Surface Tension & Capillary Cutoff\n\n## 1. The Threat of Inward Stormwater Infiltration\nIn natural cavern overhangs, rainwater falling on top of the boulder does not simply drop off the edge. Due to water's molecular cohesion and surface tension, rainwater sheets cling to the convex curvature of the ceiling and flow inward along the cavern roof, soaking bedding areas, causing damp hypothermia for ascetics, and dissolving mineral epigraphs.\n\n## 2. Engineering of the Drip-Ledge (*Kaadi* / *Thaara-Vari*)\nAncient Tamil rock sculptors solved this through a permanent geometric undercut:\n1. **Chiseling the Continuous Groove**: Along the uppermost outer lip of the rock overhang, stonemasons chiseled a continuous V-shaped or square trough (depth ~5 to 10 cm, width ~8 to 12 cm) extending the entire length of the cavern opening.\n2. **Sharp Ninety-Degree Cutoff Angle**: The inner edge of the groove was cut as a razor-sharp, inverted ninety-degree angle.\n3. **Surface Tension Rupture**: When the flowing water sheet reaches the sharp downward edge of the groove, it cannot turn the corner against gravity and surface tension snaps. \n4. **Air Gap Disconnection**: The water is forced to detach and plunge downward as a free-falling vertical curtain, landing 1 to 2 meters clear of the cavern floor.\n\n## 3. Epigraphical Placement Below the Drip-Line\nMaster scribes deliberately incised their Tamil-Brahmi inscriptions on the sheltered vertical facet directly beneath the drip-ledge, where the rock was guaranteed to remain bone-dry for over two millennia."
  },
  {
    "slug": "concept-chisel-dressed-polished-granite-monk-beds-kal-padukai",
    "category": "concepts",
    "file": "concept-chisel-dressed-polished-granite-monk-beds-kal-padukai.md",
    "node_type": "concept",
    "name_en": "Chisel-Dressed Polished Granite Monk Beds (Kal-Padukai), Ergonomics & Pillow Inclines",
    "name_ta": "செதுக்கப்பட்ட சமணக் கற்படுக்கைகள் (கற்படுக்கை), சாய்வுத் தலையணை மற்றும் வழவழப்புத் தொழில்நுட்பம்",
    "era": "Early Historic Era",
    "year_start": -300,
    "year_end": 400,
    "thinai": "kurinji",
    "summary_en": "Ergonomic lithic dressing of ascetic sleeping platforms: sunken rectangular floor beds cut into living granite with integral 5-cm raised pillow ledges (Talaiyanai), burnished with quartz sand abrasives to eliminate micro-ridges.",
    "summary_ta": "இயற்கைப் பாறைத் தரையில் செதுக்கப்பட்ட செவ்வக வடிவ சமணக் கற்படுக்கைகள், தலையை சாய்த்து வைக்க 5 செ.மீ உயர்த்தப்பட்ட கல் தலையணைப் பகுதி மற்றும் ஆற்று மணல் உராய்வு வழவழப்பு நுட்பம்.",
    "sources": [
      "Epigraphia Indica",
      "Srinivasan: Cave Temples of the Pallavas & Pandyas",
      "TNSDA Field Excavation Monographs"
    ],
    "content": "---\nid: concept-chisel-dressed-polished-granite-monk-beds-kal-padukai\ntitle: Chisel-Dressed Polished Granite Monk Beds (Kal-Padukai), Ergonomics & Pillow Inclines\ntype: concept\nera: Early Historic Era (c. 300 BCE - 400 CE)\nthinai: kurinji (Ergonomic Lithic Sculpture)\nstatus: canonical\n---\n\n# Chisel-Dressed Polished Granite Monk Beds (Kal-Padukai), Ergonomics & Pillow Inclines\n\n## 1. Design & Layout of Monastic Beds\nExcavated across hundreds of caverns in the Madurai, Pudukkottai, and Tiruvannamalai districts, Jaina stone beds (*Kal-padukai* / *Adithanam*) were carved directly into the living granite floor:\n- **Dimensions**: Averaging 180 to 200 cm in length, 60 to 75 cm in width, and recessed 5 to 10 cm below the surrounding rock floor level.\n- **Orientation**: Carefully laid out East-West or North-South to align with auspicious ascetic meditation vectors.\n\n## 2. Integrated Ergonomic Pillow Ledge (*Kal-Talaiyanai*)\nAt the head end of each bed, the stone sculptor did not cut the granite completely flat:\n- **Integral Headrest**: Left a raised, gently sloped pillow incline (rising 5 to 8 cm at a 15-degree angle) carved as an organic extension of the bedrock.\n- **Anatomical Contouring**: The incline provided natural neck support during sleep and supine meditation (*Kayotsarga*), eliminating the need for perishable cotton pillows.\n\n## 3. Fine Pointing & Abrasive Sand Polishing\n1. **Rough Point Dressing (*Koppu-Uli*)**: Deep hammer-driven chisel points leveled the undulating rock surface.\n2. **Fine Tooth Chiseling (*Vari-Uli*)**: Parallel grooving removed residual high spots.\n3. **Abrasive Sand Polishing**: The stone was rubbed for weeks with heavy wooden blocks fed with wet crushed quartz sand, corundum powder, and leather strops, creating a velvety, smooth satin finish that minimized skin abrasion for mendicants."
  },
  {
    "slug": "concept-tamil-brahmi-epigraphical-palaeography-and-asokan-divergence",
    "category": "concepts",
    "file": "concept-tamil-brahmi-epigraphical-palaeography-and-asokan-divergence.md",
    "node_type": "concept",
    "name_en": "Tamil-Brahmi Epigraphical Palaeography, Pulli System & Dravidian Phonetic Orthography",
    "name_ta": "தமிழ்-பிராமி கல்வெட்டு எழுத்தியல், புள்ளி முறைமை மற்றும் திராவிட ஒலிப்பியல் கட்டமைப்பு",
    "era": "Early Historic Era",
    "year_start": -400,
    "year_end": 300,
    "thinai": "kurinji",
    "summary_en": "Palaeographical divergence of the Tamil-Brahmi script from Mauryan Asokan Brahmi: adaptation for unique Old Tamil phonemes (Zha, Rra, Lla, Nna), elimination of aspirated stops and sibilants, and development of the Pulli virama notation marking pure vowelless consonants.",
    "summary_ta": "அசோகன் பிராமியிலிருந்து வேறுபட்டு Old Tamil மொழியின் தனித்துவ ஒலிகளான ழ, ற, ள, ண எழுத்துக்களை உருவாக்கி, மெய்யெழுத்துக்களைக் குறிக்க புள்ளி முறையை உருவாக்கிய தமிழ்-பிராமி எழுத்தியல் புரட்சி.",
    "sources": [
      "Mahadevan: Early Tamil Epigraphy",
      "Keezhadi Inscribed Potsherds (TNSDA)",
      "Nagaswamy: Roman Karur & Tamil Brahmi"
    ],
    "content": "---\nid: concept-tamil-brahmi-epigraphical-palaeography-and-asokan-divergence\ntitle: Tamil-Brahmi Epigraphical Palaeography, Pulli System & Dravidian Phonetic Orthography\ntype: concept\nera: Early Historic Era (c. 400 BCE - 300 CE)\nthinai: kurinji (Palaeography & Linguistic Science)\nstatus: canonical\n---\n\n# Tamil-Brahmi Epigraphical Palaeography, Pulli System & Dravidian Phonetic Orthography\n\n## 1. Orthographic Independence of Tamil-Brahmi\nWhile sharing ancestral origins with the Brahmi script family, the Tamil-Brahmi (Damili) script found on Madurai cavern brows and Keezhadi potsherds was independently modified to represent the phonological structure of Old Tamil:\n- **Discarded Non-Dravidian Signs**: Dropped all aspirated consonants (*kh, gh, th, dh, ph, bh*) and sibilants (*sh, sha, sa, ha*) unnecessary for native Tamil words.\n- **Created Unique Phonetic Signs**: Engineered entirely new characters for Dravidian retroflexes: *Zhakarath-thodai* (ழ), *Rra* (ற), *Lla* (ள), and alveolar *Nna* (ன).\n\n## 2. The Three Orthographic Stages (Mahadevan Typology)\n1. **Tamil-Brahmi I (Archaic - Mankulam style)**: Every consonant has an inherent vowel *a*. A separate medial vowel stroke represents both short *a* and long *aa*, with no explicit virama.\n2. **Tamil-Brahmi II (Transitional)**: A basic consonant without strokes represents the pure vowelless consonant, while a rightward stroke represents short *a*.\n3. **Tamil-Brahmi III (Classical - Pulli Innovation)**: Explicit introduction of the **Pulli** (a small dot or circular incision placed above the consonant), formally stripping the inherent *a* to denote a pure consonant, exactly as codified in *Tolkappiyam* (*Ezhuttathikaram*, sutra 15).\n\n## 3. Lithic Inscribing Mechanics\nScribes (*Ezhuthu-Silpan*) used fine tempered steel burins to incise clean, shallow grooves (1 to 2 mm deep) into the hard granite, preserving crisp palaeographic strokes for millennia."
  },
  {
    "slug": "char-mankulam-master-cavern-sculptor-kudaivarai-sirpan",
    "category": "characters",
    "file": "char-mankulam-master-cavern-sculptor-kudaivarai-sirpan.md",
    "node_type": "character",
    "name_en": "Master Cavern Sculptor of Mankulam (Kudaivarai-Sirpan)",
    "name_ta": "மாங்குளம் தலைமை குகைக் குடைவு சிற்பி (குடைவரைச் சிற்பன்)",
    "era": "Early Historic Era",
    "year_start": -300,
    "year_end": -200,
    "thinai": "kurinji",
    "summary_en": "Chief lithic architect and rock-shelter carver commissioned by early Pandya royals at Mankulam, master of granitic wedge cleaving, continuous drip-ledge channelling, and level monk bed alignment.",
    "summary_ta": "பாண்டிய மன்னன் நெடுஞ்செழியன் காலத்தில் மாங்குளத்துக் குன்றில் இயற்கைக் குகையை சமணப் பள்ளியாக மாற்றிய, நீர் விளிம்பு வெட்டு மற்றும் கற்படுக்கைச் சிற்பக்கலைத் தலைமை ஆசான்.",
    "sources": [
      "Mankulam Inscriptions",
      "Iravatham Mahadevan Research Papers",
      "Pandya Lithic Architectural Chronicles"
    ],
    "content": "---\nid: char-mankulam-master-cavern-sculptor-kudaivarai-sirpan\ntitle: Master Cavern Sculptor of Mankulam (Kudaivarai-Sirpan)\ntype: character\nera: Early Historic Era (c. 300 - 200 BCE)\nthinai: kurinji (Rock Shelter Guild Architecture)\nstatus: canonical\n---\n\n# Master Cavern Sculptor of Mankulam (Kudaivarai-Sirpan)\n\n## 1. Professional Guild Standing\nThe **Kudaivarai-Sirpan** (Master Cavern Architect) directed the lithic conversion of wild mountain boulders into habitable ascetic monasteries around the Pandyan capital of Madurai during the 3rd century BCE.\n\n## 2. Mastery of Lithic Engineering\n- **Overhang Inspection**: Assessed natural rock cracks and fracture planes to ensure that hollowed cavern chambers would not collapse under seismic or overburden pressure.\n- **Precision Drip-Ledge Alignment**: Cut the V-shaped *Kavadi* groove with flawless continuous horizontal pitch, ensuring that stormwater from torrential monsoon squalls evacuated cleanly to either flank.\n- **Palaeographic Inscribing**: Collaborated with royal court scribes to transfer ink-painted Tamil-Brahmi letters onto the hard rockface using fine pointed chisels."
  },
  {
    "slug": "char-madurai-jaina-monastic-acharya-kanikkayar",
    "category": "characters",
    "file": "char-madurai-jaina-monastic-acharya-kanikkayar.md",
    "node_type": "character",
    "name_en": "Jaina Monastic Preceptor of the Madurai Hills (Kani-Nandh-Asiriyan)",
    "name_ta": "மதுரை குன்றுகளின் சமண தலைமை ஆச்சாரியார் (கனிநந்தாசிரியர்)",
    "era": "Early Historic Era",
    "year_start": -280,
    "year_end": -210,
    "thinai": "kurinji",
    "summary_en": "Venerated Jaina preceptor and spiritual leader of the monastics residing in the Mankulam rock shelters, spiritual mentor to King Nedunchezhiyan's court, scholar of ethics and Tamil-Brahmi literacy.",
    "summary_ta": "மாங்குளம் குகைப் பள்ளியின் தலைமை சமண முனிவர்; பாண்டிய மன்னன் நெடுஞ்செழியனின் குடும்பத்தாரால் போற்றப்பட்ட அறநெறி ஆசான் மற்றும் தமிழ்-பிராமி கல்வியாளர்.",
    "sources": [
      "Mankulam Inscriptions I & II",
      "Silappadikaram",
      "Epigraphia Indica Vol XXXII"
    ],
    "content": "---\nid: char-madurai-jaina-monastic-acharya-kanikkayar\ntitle: Jaina Monastic Preceptor of the Madurai Hills (Kani-Nandh-Asiriyan)\ntype: character\nera: Early Historic Era (c. 280 - 210 BCE)\nthinai: kurinji (Ascetic Spiritual Leadership)\nstatus: canonical\n---\n\n# Jaina Monastic Preceptor of the Madurai Hills (Kani-Nandh-Asiriyan)\n\n## 1. Historical Identity in Epigraphy\nNamed explicitly in the earliest Mankulam Tamil-Brahmi inscriptions as *Kani-Nanda-Asiriyan*, he was a historical Jaina acharya who established an influential center of learning and monastic renunciation on the rocky hills northeast of Madurai.\n\n## 2. Spiritual Governance & Community Role\n- **Cavern Congregation Leadership**: Supervised dozens of resident monks, organizing daily meditation sessions, scriptural study, and ascetic fasts (*Sallekhana*).\n- **Patronage Mediation**: Accepted stone beds and civic gifts from royal relatives and textile merchant guilds without violating Jaina vows of non-possession (*Aparigraha*), dedicating all infrastructure for collective monastic use.\n- **Literacy Patronage**: Encouraged the dissemination of Tamil-Brahmi writing, facilitating the recording of donative epigraphs that preserved early historic Tamil history for posterity."
  },
  {
    "slug": "place-mankulam-ancient-jaina-cavern-haven",
    "category": "places",
    "file": "place-mankulam-ancient-jaina-cavern-haven.md",
    "node_type": "place",
    "name_en": "Mankulam Ancient Jaina Cavern Haven & Earliest Epigraphical Sanctuary",
    "name_ta": "மாங்குளம் பண்டைய சமணக் குகைப் பள்ளி மற்றும் தமிழ்-பிராமி தொடக்கக் கல்வெட்டுத் தளம்",
    "era": "Early Historic Era",
    "year_start": -350,
    "year_end": 400,
    "thinai": "kurinji",
    "summary_en": "Monumental granitic inselberg at Mankulam (Meenakshipuram) near Madurai containing natural rock shelters, V-shaped drip-ledges, stone-carved beds, and the earliest dated Tamil-Brahmi royal inscriptions in South Asia.",
    "summary_ta": "மதுரைக்கு அருகே அமைந்த வரலாற்றுப் புகழ்பெற்ற மாங்குளம் ஓவாமலை சமணக் குடைக் குகைகள்; நீர் விலக்கு விளிம்பு வெட்டுகள், வழவழப்பான கற்படுக்கைகள் மற்றும் தென்னிந்தியாவின் காலத்தால் முந்திய தமிழ்-பிராமி கல்வெட்டுகளின் உறைவிடம்.",
    "sources": [
      "Iravatham Mahadevan: Early Tamil Epigraphy",
      "TNSDA Protected Monuments Register",
      "Archaeological Survey of Madurai Region"
    ],
    "content": "---\nid: place-mankulam-ancient-jaina-cavern-haven\ntitle: Mankulam Ancient Jaina Cavern Haven & Earliest Epigraphical Sanctuary\ntype: place\nera: Early Historic Era (c. 350 BCE - 400 CE)\nthinai: kurinji (Lithic Epigraphical Sanctuary)\nstatus: canonical\n---\n\n# Mankulam Ancient Jaina Cavern Haven & Earliest Epigraphical Sanctuary\n\n## 1. Geographical Location & Inselberg Topography\nMankulam (also known as Meenakshipuram) is situated approximately 25 kilometers northeast of Madurai (coordinates approx. 10.0333° N, 78.2333° E). The sanctuary comprises the imposing granitic boulder formation of *Ovamalai* rising above the agrarian plains.\n\n## 2. Archaeological Features & Structural Elements\n- **Natural Overhang Caverns**: Spacious natural rock shelters providing shade and shelter from tropical winds.\n- **Deep Drip-Ledge Grooves**: Chiseled outer channels preventing rainwater ingress.\n- **Polished Granite Beds (*Kal-Padukai*)**: Dozens of sunken, smoothed monastic beds with raised headrests.\n- **Six Tamil-Brahmi Inscriptions**: Incised on the rock brows and pillow slopes recording Pandyan king Nedunchezhiyan.\n\n## 3. Epicenter of Early Tamil Literacy\nMankulam is globally recognized as the foundational monument of Tamil written history, proving that sophisticated alphabetical literacy, statecraft, and religious architecture thrived in the Tamil country by the 3rd century BCE."
  },
  {
    "slug": "text-akanunuru-carnelian-gem-traders-and-lapidary-poetry",
    "category": "texts",
    "file": "text-akanunuru-carnelian-gem-traders-and-lapidary-poetry.md",
    "node_type": "text",
    "name_en": "Akananuru Carnelian Gem Traders, Red Agate Beads & Lapidary Market Poetry",
    "name_ta": "அகநானூறு - செம்மணி வணிகர்கள், காரசார சூளையில் சிவந்த செம்மணிகள் மற்றும் மணிக்கலை பாடல்கள்",
    "era": "Sangam Classical Era",
    "year_start": -300,
    "year_end": 200,
    "thinai": "palai",
    "summary_en": "Classical verses in Akananuru (v. 155, 315) and Natrinai describing red carnelian gem beads (Sem-mani), desert lapidary caravans, furnace heating to enhance deep orange-red color, and drill-perforated beads strung on golden cords.",
    "summary_ta": "அகநானூறு மற்றும் நற்றிணையில் பாலை நில வழிகளில் செம்மணி (Carnelian) ஏற்றிச் சென்ற மணிக்கல் வணிகர்கள், சூளையிட்டு நிறம் கூட்டப்பட்ட சிவப்பு மணிகள் மற்றும் துளையிடப்பட்ட அணிகலன் பற்றிய செவ்வியல் பாடல்கள்.",
    "sources": [
      "Akananuru v. 155, 315",
      "Natrinai v. 136",
      "Purananuru v. 353"
    ],
    "content": "---\nid: text-akanunuru-carnelian-gem-traders-and-lapidary-poetry\ntitle: Akananuru Carnelian Gem Traders, Red Agate Beads & Lapidary Market Poetry\ntype: text\nera: Sangam Classical Era (c. 300 BCE - 200 CE)\nthinai: palai (Arid Trade Arterials)\nstatus: canonical\n---\n\n# Akananuru: Carnelian Gem Traders, Red Agate Beads & Lapidary Market Poetry\n\n## 1. Classical Primary Source Citations\n- **Akananuru** (v. 155): Depicts daring gemstone caravans (*Mani-Vanikar*) traversing waterless desert tracks (*Palai*), transporting sacks of deep blood-red carnelian and agate beads (*Sem-mani*) destined for coastal emporia and royal treasuries.\n- **Akananuru** (v. 315): Sings of fair maidens adorned with necklaces of lustrous red carnelian beads intercalated with gold granulation spacers, their drilled perforations strung on braided silk threads.\n- **Natrinai** (v. 136): Describes lapidary artisans using bow drills to pierce hard semi-precious stone beads, the drilling friction cooled by continuously dripping water.\n\n## 2. Gemmological Status of Carnelian (*Sem-Mani*)\nIn early historic Tamilakam, carnelian (a microcrystalline variety of silica chalcedony colored by iron oxide) was one of the most treasured stones:\n- Sourced from river gravels and volcanic trap deposits, then transformed in industrial workshops into barrel beads, biconical beads, and spherical gems.\n- Adorned with indelible white geometric patterns through alkaline chemical etching.\n\n## 3. International Trade Demand\nCarnelian was exported in massive quantities from Tamil ports like Muziris, Korkai, and Arikamedu to the Roman empire, Ptolemaic Egypt, and Southeast Asia, where Tamil-etched carnelian beads have been recovered in high-status burials."
  },
  {
    "slug": "insc-porunthal-chera-carnelian-bead-furnace-charters",
    "category": "inscriptions",
    "file": "insc-porunthal-chera-carnelian-bead-furnace-charters.md",
    "node_type": "inscription",
    "name_en": "Porunthal Chera Carnelian Bead Furnace Charters & Archaeological Excavation Epigraphs",
    "name_ta": "பொருந்தல் சேரர் செம்மணி சூளை மற்றும் அகழாய்வு தமிழ்-பிராமி கல்வெட்டுகள்",
    "era": "Early Historic Era",
    "year_start": -500,
    "year_end": -100,
    "thinai": "kurinji",
    "summary_en": "Excavation records and Tamil-Brahmi inscribed potsherds from Porunthal near Palani uncovering over 7,500 carnelian beads, multi-tier annealing furnaces, micro-perforation diamond drills, and 5th-century BCE radiocarbon dates.",
    "summary_ta": "பழனி பொருந்தல் அகழாய்வில் வெளிவந்த 7,500-க்கும் மேற்பட்ட செம்மணிகள் (Carnelian), சூளைகள், நுண்துளை வைர ஊசிகள் மற்றும் கி.மு. 5-ஆம் நூற்றாண்டு தமிழ்-பிராமி பொறித்த மண்பாண்ட ஆவணங்கள்.",
    "sources": [
      "Rajan: Porunthal Excavations Report (2011)",
      "Radiocarbon Dating from Beta Analytic (USA)",
      "Chera Archaeology Bulletin"
    ],
    "content": "---\nid: insc-porunthal-chera-carnelian-bead-furnace-charters\ntitle: Porunthal Chera Carnelian Bead Furnace Charters & Archaeological Excavation Epigraphs\ntype: inscription\nera: Early Historic Era (c. 500 - 100 BCE)\nthinai: kurinji (Industrial Lapidary Archaeology)\nstatus: canonical\n---\n\n# Porunthal: Chera Carnelian Bead Furnace Charters & Archaeological Excavation Epigraphs\n\n## 1. Archaeological Context & Discovery\nExcavations conducted by Pondicherry University under Dr. K. Rajan at Porunthal in Dindigul district revealed one of the largest gemstone lapidary workshops in ancient South Asia, yielding over 7,500 finished and unfinished carnelian, agate, and beryl beads.\n\n## 2. Inscriptional Artifacts & Chronological Shock\n- **Tamil-Brahmi Inscribed Potsherd (*Vayra-kodan*)**: Uncovered in association with paddy grains radiocarbon-dated to 490 BCE, pushing the antiquity of Tamil literacy and organized bead lapidary into the 5th century BCE.\n- **Glass & Stone Bead Furnaces**: Lined with refractory clay, containing charred charcoal and raw yellowish agate nodules waiting for thermal reddening.\n\n## 3. Industrial Infrastructure at Porunthal\n- **Micro-Drilling Workstations**: Unfinished beads abandoned mid-drilling due to fracture, exhibiting conical micro-drill entry channels made by double-mandrel diamond tipped bits.\n- **Etched Bead Hoards**: Yielded dozens of rare etched carnelian beads decorated with white wavy lines and concentric circles."
  },
  {
    "slug": "insc-kodumanal-etched-carnelian-merchant-guild-epigraphs",
    "category": "inscriptions",
    "file": "insc-kodumanal-etched-carnelian-merchant-guild-epigraphs.md",
    "node_type": "inscription",
    "name_en": "Kodumanal Etched Carnelian Merchant Guild Epigraphs & Lapidary Workshop Charters",
    "name_ta": "கொடுமணல் பொறிப்பு செம்மணி வணிகக் குழு மற்றும் மணிக்கல் பட்டறை கல்வெட்டுகள்",
    "era": "Sangam Classical Era",
    "year_start": -300,
    "year_end": 100,
    "thinai": "kurinji",
    "summary_en": "Inscribed Tamil-Brahmi graffiti sherds and workshop debitage from Kodumanal on the Noyyal river documenting carnelian lapidary guilds, plant-alkali etching pastes, and gemstone export consortia.",
    "summary_ta": "நொய்யல் ஆற்றங்கரை கொடுமணலில் கண்டெடுக்கப்பட்ட தமிழ்-பிராமி கல்வெட்டுகள்; செம்மணி கல் உடைப்பு, தாவர உப்புக் கூழ்ம பொறிப்பு (Alkaline etching) மற்றும் மணிக்கல் வணிகர் குழு ஆவணங்கள்.",
    "sources": [
      "Kodumanal Excavation Reports (TNSDA)",
      "Rajan: Iron and Gemstones in Tamil Nadu",
      "Journal of Field Archaeology"
    ],
    "content": "---\nid: insc-kodumanal-etched-carnelian-merchant-guild-epigraphs\ntitle: Kodumanal Etched Carnelian Merchant Guild Epigraphs & Lapidary Workshop Charters\ntype: inscription\nera: Sangam Classical Era (c. 300 BCE - 100 CE)\nthinai: kurinji (Gemstone Manufacturing Center)\nstatus: canonical\n---\n\n# Kodumanal: Etched Carnelian Merchant Guild Epigraphs & Lapidary Workshop Charters\n\n## 1. Archaeological Significance of Kodumanal Lapidary\nExcavations at Kodumanal revealed tons of carnelian debitage, broken bead blanks, and finished etched gems, confirming that raw yellowish chalcedony was imported from Deccan volcanic beds and processed locally into prized high-karat etched beads.\n\n## 2. Tamil-Brahmi Merchant Graffiti\n- **Artisan & Merchant Names**: Graffiti on terracotta vessels such as *Kannan*, *Kovan*, and *Samangan* identifying gem cutters and lapidary merchant patrons.\n- **Multilingual Trade Environment**: Prakrit and bilingual names reflecting international gem buyers residing in the industrial enclave.\n\n## 3. Physical Evidence of Chemical Etching\nExcavators recovered small terracotta palettes containing dried residues of calcium carbonate, soda, and plant ashes, directly linking archaeological remains to the chemical etching technology described in ancient lapidary treatises."
  },
  {
    "slug": "concept-alkaline-chemical-etching-plant-soda-slurry-and-heating",
    "category": "concepts",
    "file": "concept-alkaline-chemical-etching-plant-soda-slurry-and-heating.md",
    "node_type": "concept",
    "name_en": "Alkaline Chemical Etching, Plant-Soda Slurry & High-Temperature Soda-Silicate Diffusion",
    "name_ta": "கார வேதியியல் பொறிப்பு (Etching), தாவர உப்புக் கூழ்மம் மற்றும் சோடா-சிலிக்கா ஊடுருவல் நுட்பம்",
    "era": "Early Historic Era",
    "year_start": -400,
    "year_end": 400,
    "thinai": "kurinji",
    "summary_en": "The pyrochemical nanotechnology of etched carnelian: painting alkaline slurries of natural washing soda (Kalluppu / natron) and juice of Kiratatikta (wild spurge) onto polished carnelian, and baking at 400-500°C to induce permanent sodium silicate white diffusion lines.",
    "summary_ta": "பளபளப்பான செம்மணி மீது சலவைச் சோடா மற்றும் கற்றாழை/கள்ளிச் சாறு கொண்டு வெள்ளை வடிவியல் கோடுகளை வரைந்து, 400-500°C-ல் சுட்டு சோடியம் சிலிக்கேட்டை பாறையின் படிக அமைப்பில் ஊடுருவச் செய்து நிரந்தர வெண்வடிவங்களை உருவாக்கிய பண்டைய நானோ-வேதியியல் நுட்பம்.",
    "sources": [
      "Beck: Etched Carnelian Beads (1933)",
      "Kenoyer: Ancient Gem Lapidary Technologies",
      "Kodumanal Bead Pyrotechnics (IIT-Madras)"
    ],
    "content": "---\nid: concept-alkaline-chemical-etching-plant-soda-slurry-and-heating\ntitle: Alkaline Chemical Etching, Plant-Soda Slurry & High-Temperature Soda-Silicate Diffusion\ntype: concept\nera: Early Historic Era (c. 400 BCE - 400 CE)\nthinai: kurinji (Chemical Nanotechnology & Gem Pyrotechnics)\nstatus: canonical\n---\n\n# Alkaline Chemical Etching, Plant-Soda Slurry & High-Temperature Soda-Silicate Diffusion\n\n## 1. The Phenomenon of Etched Carnelian (Type I Etching)\nAmong the most sophisticated chemical pyrotechnologies of ancient India was the creation of **etched carnelian beads**—deep red stones bearing crisp, indelible snow-white patterns (chevrons, zigzags, concentric circles, cross-hatching) that penetrate into the stone matrix and cannot be scratched or dissolved off.\n\n## 2. Chemical Reagent Formulation\n1. **Alkaline Flux**: Natural washing soda (*Kalluppu* / sodium carbonate, Na₂CO₃) derived from efflorescent alkaline soils (*Usar-man*) or calcined plant ashes (*Suda-man*).\n2. **Plant Binder & Flux Medium**: Crushed milky juice of wild spurge (*Euphorbia antiquorum* / *Kalli*) or shoot extract of *Kiratatikta*. The plant juice acted as a viscous suspension medium and provided organic carbon to lower reaction temperatures.\n3. **Slurry Application**: The artisan dipped a fine bone stylus or bronze pen into the alkaline paste and drew delicate patterns onto the polished carnelian surface.\n\n## 3. Thermal Diffusion Physics (The Muffle Bake)\n- **Controlled Heating**: The painted beads were placed inside an unglazed earthenware muffle crucible surrounded by wood charcoal.\n- **Solid-State Chemical Diffusion**: When heated between 400°C and 550°C, the sodium carbonate reacted with the microcrystalline silica (SiO₂) of the chalcedony:\n  $$\\text{Na}_2\\text{CO}_3 + \\text{SiO}_2 \\rightarrow \\text{Na}_2\\text{SiO}_3 + \\text{CO}_2 \\uparrow$$\n- **Formation of White Enstatite/Silicate**: The sodium fused into the silica lattice down to a depth of 0.2 to 0.5 mm, creating opaque, snow-white, micro-porous sodium silicate lines that permanently altered the stone's optical refraction without damaging structural toughness."
  },
  {
    "slug": "concept-micro-diamond-twin-mandrel-bow-drilling-mechanics",
    "category": "concepts",
    "file": "concept-micro-diamond-twin-mandrel-bow-drilling-mechanics.md",
    "node_type": "concept",
    "name_en": "Micro-Diamond Twin-Mandrel Bow Drilling, Ultrasonic Friction & Double-Ended Perforation",
    "name_ta": "நுண் வைர இரட்டைச் சுழல் வில்-துளைப்பொறி, இருமுனைத் துளையிடல் மற்றும் மணிக்கல் துளைத்தல்",
    "era": "Early Historic Era",
    "year_start": -400,
    "year_end": 300,
    "thinai": "kurinji",
    "summary_en": "High-precision gemstone perforation mechanics: drilling hard carnelian (Mohs 7) using bow-driven wooden mandrels tipped with microscopic diamond splinter chips (Vayra-kodan), drilling from both poles to meet in the center without core blowout.",
    "summary_ta": "கடின செம்மணிகளை (Mohs 7) நுண் வைரத் துகள்கள் பதித்த வில்-சுழல் துளைப்பொறி மூலம் இருபுறமிருந்தும் துளைத்து மையத்தில் இணைத்து, கல் உடையாமல் நூலளவாகத் துளைத்த பண்டைய துல்லிய பொறியியல்.",
    "sources": [
      "Kenoyer: Stone Bead Drilling Technologies",
      "Porunthal Micro-Drill Analysis",
      "Gwinnett & Gorelick: Bead Drilling in Antiquity"
    ],
    "content": "---\nid: concept-micro-diamond-twin-mandrel-bow-drilling-mechanics\ntitle: Micro-Diamond Twin-Mandrel Bow Drilling, Ultrasonic Friction & Double-Ended Perforation\ntype: concept\nera: Early Historic Era (c. 400 BCE - 300 CE)\nthinai: kurinji (Precision Micro-Drilling Mechanics)\nstatus: canonical\n---\n\n# Micro-Diamond Twin-Mandrel Bow Drilling, Ultrasonic Friction & Double-Ended Perforation\n\n## 1. The Perforation Challenge of Quartz Gemstones\nCarnelian, agate, and quartz possess a Mohs hardness of 7. Ordinary bronze or iron drills cannot penetrate them; steel tools simply dull and skate off the stone. Ancient Tamil bead makers at Kodumanal and Porunthal solved this using **micro-diamond tipped drills** (*Vayra-kodan*).\n\n## 2. Micro-Diamond Drill Mechanics\n1. **The Diamond Splinter Point**: Microscopic chips of industrial diamond (bort / *Vayram*) were crimped into the hollow copper or bronze ferrule tip of a wooden spindle.\n2. **Bow-Drive High RPM**: The spindle was spun using a hand-held archer's bow strung with twisted leather or gut cord. Rapid sawing motions generated rotational speeds of 1,500 to 2,000 RPM.\n3. **Double-Ended Alignment Drilling**:\n   - Drilling commenced at one pole and progressed precisely halfway through the bead.\n   - The bead was reversed in a holding wooden clamp (*Mani-irukki*), and drilled from the opposite pole.\n   - The two drilling shafts met in the exact center of the stone, producing the characteristic hour-glass or bi-conical perforation profile that confirms authentic ancient manual drilling.\n   - Drilling from both ends prevented high-stress exit blowout chipping.\n\n## 3. Water-Slurry Lubrication\nA continuous trickle of water mixed with fine corundum flour was dripped onto the hole, clearing stone powder, preventing thermal shock cracking, and extending the life of the diamond bit."
  },
  {
    "slug": "concept-agate-and-carnelian-iron-oxide-thermal-reddening-pyrotechnics",
    "category": "concepts",
    "file": "concept-agate-and-carnelian-iron-oxide-thermal-reddening-pyrotechnics.md",
    "node_type": "concept",
    "name_en": "Agate and Carnelian Thermal Reddening, Iron Oxide Oxidation & Controlled Oven Cooling",
    "name_ta": "செம்மணி வெப்ப நிறமாற்றம், இரும்பு ஆக்ஸைடு ஆக்சிஜனேற்றம் மற்றும் பழுப்புக்கல் சிவப்பு வண்ணமாக்கல்",
    "era": "Early Historic Era",
    "year_start": -400,
    "year_end": 300,
    "thinai": "kurinji",
    "summary_en": "Thermal pyrotechnology transforming dull yellowish-brown raw chalcedony nodules into vivid deep blood-red carnelian through multi-stage oven baking: dehydrating iron limonite/goethite into anhydrous hematite (Fe2O3) nanoparticles.",
    "summary_ta": "மஞ்சள் மற்றும் பழுப்பு நிற அகேட் கற்களை உமிச் சாம்பல் பாண்டங்களில் இட்டு பல நாட்கள் மிதமான வெப்பத்தில் சுட்டு, நீரேறிய இரும்புத் தாதுவை நீரற்ற ஹெமடைட்டாக (Fe2O3) மாற்றி ஆழ்ந்த சிவப்பு நிறமாக்கிய பண்டைய வெப்ப மாற்ற வேதியியல்.",
    "sources": [
      "Rajan: Archaeological Studies of Kodumanal",
      "Indian Minerals & Metallurgy Bulletin",
      "Bead Study Trust Monograph Series"
    ],
    "content": "---\nid: concept-agate-and-carnelian-iron-oxide-thermal-reddening-pyrotechnics\ntitle: Agate and Carnelian Thermal Reddening, Iron Oxide Oxidation & Controlled Oven Cooling\ntype: concept\nera: Early Historic Era (c. 400 BCE - 300 CE)\nthinai: kurinji (Mineralogical Thermal Pyrotechnics)\nstatus: canonical\n---\n\n# Agate and Carnelian Thermal Reddening, Iron Oxide Oxidation & Controlled Oven Cooling\n\n## 1. Natural State of Raw Chalcedony\nMost natural chalcedony nodules excavated from Deccan trap gravels are dull grey, olive-brown, or pale yellow due to microscopic inclusions of hydrated iron oxide minerals—specifically **goethite** [FeO(OH)] and **limonite** [FeO(OH)·nH₂O].\n\n## 2. Chemical Mechanism of Thermal Reddening\nWhen heated gradually in an oxidizing atmosphere to temperatures between 350°C and 450°C, the hydrated minerals undergo endothermic dehydration:\n$$2\\text{FeO(OH)} \\xrightarrow{\\Delta} \\text{Fe}_2\\text{O}_3 + \\text{H}_2\\text{O} \\uparrow$$\n- The water molecule is expelled from the micro-porous silica crystal mesh.\n- The hydrated iron decomposes into sub-microscopic anhydrous **hematite** ($\\alpha\\text{-Fe}_2\\text{O}_3$) nanoparticles uniformly distributed through the chalcedony lattice.\n- The hematite absorbs blue-green light, transforming the stone into an intense, fiery, translucent blood-orange or crimson carnelian.\n\n## 3. Pyrotechnical Execution in Ancient Tamil Kilns\n1. **Solar Pre-Drying**: Raw nodules were sun-baked on river sandbars for several months to evaporate free moisture that would cause stones to explode in the kiln.\n2. **Clay Pot Packing**: Packed inside thick earthenware jars interleaved with dry wood shavings and rice husks.\n3. **Slow Ramp & Multi-Day Cooling**: Fired in subterranean clamp kilns over 48 to 72 hours with slow cooling over three days, eliminating thermal shock fracturing."
  },
  {
    "slug": "concept-tumble-polishing-hardwood-grooves-and-corundum-slurry",
    "category": "concepts",
    "file": "concept-tumble-polishing-hardwood-grooves-and-corundum-slurry.md",
    "node_type": "concept",
    "name_en": "Tumble Polishing, Grooved Hardwood Rollers & Corundum Slurry Lapidary",
    "name_ta": "மணிக்கல் உருளை வழவழப்பு, மரவரிப் பள்ளங்கள் மற்றும் குருந்தக்கல் கூழ்ம பாலிஷிங்",
    "era": "Early Historic Era",
    "year_start": -300,
    "year_end": 400,
    "thinai": "kurinji",
    "summary_en": "Bulk finishing mechanics of ancient Tamil lapidaries: tumbling hundreds of drilled bead blanks inside grooved hardwood troughs (Marap-Palli) charged with fine corundum abrasive slurry and diamond dust, followed by leather buffing to achieve vitreous gloss.",
    "summary_ta": "துளையிடப்பட்ட நூற்றுக்கணக்கான மணிக்கற்களை குருந்தக்கல் (Corundum) மணல் மற்றும் நீர் சேர்த்த மரப் பள்ள உருளைகளில் இட்டு தொடர் உருட்டல் மூலம் சமப்படுத்தி, தோல்பட்டையில் பளபளப்பாக்கிய மொத்த உற்பத்தி முறை.",
    "sources": [
      "Kodumanal Lapidary Debitage Studies",
      "Kenoyer: Ancient South Asian Bead Polish",
      "TNSDA Technical Monographs"
    ],
    "content": "---\nid: concept-tumble-polishing-hardwood-grooves-and-corundum-slurry\ntitle: Tumble Polishing, Grooved Hardwood Rollers & Corundum Slurry Lapidary\ntype: concept\nera: Early Historic Era (c. 300 BCE - 400 CE)\nthinai: kurinji (Bulk Lapidary Mechanical Finishing)\nstatus: canonical\n---\n\n# Tumble Polishing, Grooved Hardwood Rollers & Corundum Slurry Lapidary\n\n## 1. Bulk Finishing Demands\nHand-polishing thousands of individual faceted and rounded carnelian beads would require prohibitive labor hours. Ancient bead factories at Kodumanal, Porunthal, and Kangeyam invented mass mechanical tumbling systems.\n\n## 2. The Grooved Hardwood Trough Apparatus (*Marap-Palli*)\n1. **Hardwood Log Troughs**: Dense trunks of tamarind or vengai were hollowed with longitudinal rounded channels corresponding to desired bead calibers.\n2. **Abrasive Charge**: The troughs were loaded with perforated bead blanks and charged with graded abrasive slurries:\n   - **Coarse Shaping**: Pulverized quartz sand and river garnet.\n   - **Fine Lapping**: Crushed native **corundum** (*Kurundham* / sapphire emery powder, Mohs 9) sourced from Salem deposits.\n3. **Reciprocating Friction**: Heavy flat wooden lids loaded with ballast stones were pulled back and forth across the troughs using rope pulleys, rolling the beads continuously against each other and the abrasive slurry.\n\n## 3. Final Leather Buffing (*Thol-Minukku*)\nAfter abrasive lapping, beads were strung onto long taut cords and burnished with oiled buffing strops made of wild deer hide (*Maan-thol*) charged with fine rice husk ash, yielding a mirror-like vitreous luster that remained untarnished for centuries."
  },
  {
    "slug": "char-kodumanal-master-carnelian-etcher-kalluppu-achari",
    "category": "characters",
    "file": "char-kodumanal-master-carnelian-etcher-kalluppu-achari.md",
    "node_type": "character",
    "name_en": "Master Carnelian Etcher & Chemical Lapidary of Kodumanal (Kalluppu-Achari)",
    "name_ta": "கொடுமணல் தலைமை செம்மணி பொறிப்பு சிற்பி மற்றும் ரசவாத ஆசாரி (கல்லுப்பு ஆசாரி)",
    "era": "Sangam Classical Era",
    "year_start": -200,
    "year_end": -50,
    "thinai": "kurinji",
    "summary_en": "Chief chemical lapidary and master carnelian etcher at the industrial factory of Kodumanal, master of soda ash slurry formulation, freehand geometric etching pens, and thermal diffusion ovens.",
    "summary_ta": "கொடுமணல் மணிக்கல் தொழிற்சாலையின் தலைமை ரசவாத ஆசாரி; கார உப்புக் கூழ்ம விகிதம், செம்மணி மீது வெண்கோட்டு சித்திரங்கள் வரைதல் மற்றும் சூளை வெப்பக் கட்டுப்பாட்டில் கைதேர்ந்த தலைமைப் பொற்கொல்லன்.",
    "sources": [
      "Kodumanal Excavations (Rajan)",
      "Tamil-Brahmi Lapidary Records",
      "Indian Archaeology Reviews"
    ],
    "content": "---\nid: char-kodumanal-master-carnelian-etcher-kalluppu-achari\ntitle: Master Carnelian Etcher & Chemical Lapidary of Kodumanal (Kalluppu-Achari)\ntype: character\nera: Sangam Classical Era (c. 200 - 50 BCE)\nthinai: kurinji (Chemical Lapidary Guild Leadership)\nstatus: canonical\n---\n\n# Master Carnelian Etcher & Chemical Lapidary of Kodumanal (Kalluppu-Achari)\n\n## 1. Professional Stature & Guild Authority\nThe **Kalluppu-Achari** (Master of Mineral Salts and Gem Etching) was the chief pyrotechnologist of the Kodumanal bead manufacturing complex. He directed the specialized guild responsible for transforming plain red carnelian into high-value etched luxury gems for trans-continental commerce.\n\n## 2. Secrets of the Chemical Formulation\n- **Slurry Formulation**: Guarded the precise ratio of efflorescent plant soda, spurge milky latex, and fine clay slip that flowed smoothly from drawing styluses without dripping.\n- **Kiln Temperature Gauge**: Judged kiln temperature inside the charcoal crucible entirely by the subtle incandescence color of burning coals (dull red vs. bright cherry).\n- **Quality Inspection**: Inspected cooled beads to ensure that white lines penetrated at least 0.2 mm beneath the surface and would not flake off during tumbling."
  },
  {
    "slug": "char-porunthal-gemstone-micro-driller-mani-thulaithor",
    "category": "characters",
    "file": "char-porunthal-gemstone-micro-driller-mani-thulaithor.md",
    "node_type": "character",
    "name_en": "Master Gemstone Micro-Driller of Porunthal (Mani-Thulaithor)",
    "name_ta": "பொருந்தல் தலைமை மணிக்கல் துளைப்பாளர் (மணி துளைப்போர்)",
    "era": "Early Historic Era",
    "year_start": -450,
    "year_end": -300,
    "thinai": "kurinji",
    "summary_en": "Master micro-drilling craftsman at the 5th-century BCE bead production center of Porunthal, legendary specialist in twin-mandrel diamond bow drills, perforation alignment, and zero-breakage tolerances.",
    "summary_ta": "பழனி பொருந்தல் தொழிற்கூடத்தின் தலைசிறந்த துளைப்பாளர்; நுண் வைர ஊசிகள் கொண்டு கடின மணிக்கற்களை இருமுனையிலும் துளைத்து மையத்தில் நேர்த்தியாக இணைத்த பழம்பெரும் நுட்பக் கலைஞர்.",
    "sources": [
      "Porunthal Excavations Monograph",
      "Radiocarbon Stratigraphy Bulletin",
      "Studies in Ancient Indian Gem Tools"
    ],
    "content": "---\nid: char-porunthal-gemstone-micro-driller-mani-thulaithor\ntitle: Master Gemstone Micro-Driller of Porunthal (Mani-Thulaithor)\ntype: character\nera: Early Historic Era (c. 450 - 300 BCE)\nthinai: kurinji (Micro-Drilling Craftsmanship)\nstatus: canonical\n---\n\n# Master Gemstone Micro-Driller of Porunthal (Mani-Thulaithor)\n\n## 1. Historical Identity & Antiquity\nOperating at the 5th-century BCE Chera industrial center of Porunthal, the **Mani-Thulaithor** (Master Gem Driller) represented the pinnacle of pre-modern micro-drilling dexterity in the ancient world.\n\n## 2. Mastery of Diamond Tools & Coordination\n- **Diamond Bort Crimping**: Skillfully mounted microscopic splinter diamonds into softened copper drill tips, peening the metal to hold the diamond firmly without fracturing the crystal.\n- **Rhythmic Bow Dexterity**: Maintained perfectly steady 2,000 RPM bow reciprocation with one hand while feeding water-corundum coolant drops with the other.\n- **Sub-Millimeter Alignment**: Successfully aligned opposite-pole drilling shafts to within a fraction of a millimeter, creating uniform thread conduits through thousands of beads without blowing out delicate bead ends."
  },
  {
    "slug": "place-kangeyam-ancient-gem-lapidary-haven",
    "category": "places",
    "file": "place-kangeyam-ancient-gem-lapidary-haven.md",
    "node_type": "place",
    "name_en": "Kangeyam Ancient Gem Lapidary Haven & Noyyal Basin Mining Complex",
    "name_ta": "காங்கேயம் பண்டைய மணிக்கல் தொழிற்பட்டினம் மற்றும் நொய்யல் படுகை சுரங்க வளாகம்",
    "era": "Sangam Classical Era",
    "year_start": -400,
    "year_end": 400,
    "thinai": "kurinji",
    "summary_en": "Renowned geologic and manufacturing basin in western Tamil Nadu (Noyyal valley) celebrated for ancient beryl pegmatite mines, carnelian thermal reddening furnaces, alkaline chemical etching, and Mediterranean luxury exports.",
    "summary_ta": "கொங்கு நாட்டின் நொய்யல் நதிக்கரையில் அமைந்த வரலாற்றுப் புகழ்பெற்ற மணிக்கல் சுரங்க மற்றும் தயாரிப்பு மையம்; வைடூரியம், அகேட், செம்மணி மற்றும் சர்வதேச உரோமானிய வணிகத்தின் உறைவிடம்.",
    "sources": [
      "Archaeological Survey of the Noyyal Basin",
      "Padiyur-Kangeyam Beryl Mining Memoirs",
      "Imperial Gazetteer of South India"
    ],
    "content": "---\nid: place-kangeyam-ancient-gem-lapidary-haven\ntitle: Kangeyam Ancient Gem Lapidary Haven & Noyyal Basin Mining Complex\ntype: place\nera: Sangam Classical Era (c. 400 BCE - 400 CE)\nthinai: kurinji (Mineral Mining & Lapidary Metropolis)\nstatus: canonical\n---\n\n# Kangeyam Ancient Gem Lapidary Haven & Noyyal Basin Mining Complex\n\n## 1. Geological Setting & Mineralogical Wealth\nKangeyam is located in the Noyyal river drainage basin in western Tamil Nadu (coordinates approx. 11.0050° N, 77.5600° E). Positioned along the Dharapuram pegmatite belt, it is geologically one of the richest sources of gemstone-grade corundum, beryl, aquamarine, quartz crystals, and alluvial chalcedony in South Asia.\n\n## 2. Ancient Mining & Industrial Infrastructure\nField investigations have recorded:\n- **Ancient Open-Cast & Pit Mines**: Centuries-old quarry trenches at nearby Padiyur and Vengambur extending deep into pegmatite veins.\n- **Refractory Annealing Kilns**: Subterranean pottery kilns dedicated to the multi-day thermal reddening of carnelian nodules.\n- **Tumbling Troughs & Grinding Slabs**: Massive grooved granite blocks used to tumble and polish bead blanks.\n\n## 3. Nexus of the Trans-Peninsular Gem Route\nKangeyam was the central hub of the inland trade highway linking Karur, Kodumanal, and the Palakkad Gap to the western port of Muziris (Pattanam), feeding millions of cut, polished, and chemically etched gems into the global maritime networks of antiquity."
  },
  {
    "slug": "text-kurunthokai-ettam-well-irrigation-and-picottah-poetry",
    "category": "texts",
    "file": "text-kurunthokai-ettam-well-irrigation-and-picottah-poetry.md",
    "node_type": "text",
    "name_en": "Kurunthokai Picottah Lever Hymns (Ettam / Thulaam), Creaking Wells & Garden Irrigation Poetry",
    "name_ta": "குறுந்தொகை - ஏற்றம் (துலாம்), பாழும் கிணற்று நீர் இறைப்பு மற்றும் தோட்டக்கால் பாசனப் பாடல்கள்",
    "era": "Sangam Classical Era",
    "year_start": -300,
    "year_end": 200,
    "thinai": "mullai",
    "summary_en": "Classical verses in Kurunthokai (v. 238), Purananuru (v. 230), and Kalithogai portraying the creaking sound of the counterweight picottah beam (Ettam / Thulaam), stone-lined irrigation wells, balanced leverage, and lush vegetable gardens.",
    "summary_ta": "குறுந்தொகை, புறநானூறு மற்றும் கலித்தொகையில் ஏத்தமரம் (ஏற்றம்/துலாம்) இசைக்கும் ஓசை, கல் கட்டிய ஆழ்துளைக் கிணறுகள், எடைக் கல் சமநிலை மற்றும் பசுமையான தோட்டக்கால் பாசனம் பற்றிய செவ்வியல் பாடல்கள்.",
    "sources": [
      "Kurunthokai v. 238",
      "Purananuru v. 230",
      "Kalithogai v. 22"
    ],
    "content": "---\nid: text-kurunthokai-ettam-well-irrigation-and-picottah-poetry\ntitle: Kurunthokai Picottah Lever Hymns (Ettam / Thulaam), Creaking Wells & Garden Irrigation Poetry\ntype: text\nera: Sangam Classical Era (c. 300 BCE - 200 CE)\nthinai: mullai (Pastoral Garden Hydrology)\nstatus: canonical\n---\n\n# Kurunthokai: Picottah Lever Hymns (Ettam / Thulaam), Creaking Wells & Garden Irrigation Poetry\n\n## 1. Classical Primary Source Citations\n- **Kurunthokai** (v. 238): Poignantly describes the rhythmic, sorrowful creaking (*Eetta-maram kural-isaikkum*) of the counterpoise well sweep (*Ettam*) as the cultivator treads the long pivoting beam above the deep stone-lined well (*Kooval*), lifting bucket after bucket of sparkling water to irrigate plantain groves and sweet tubers.\n- **Purananuru** (v. 230): Depicts lush green garden tracts (*Thoppu*) fed by well levers (*Thulaam*) where water flows through narrow furrows, nourishing paddy seedlings and sugarcane stalks during dry seasons.\n- **Kalithogai** (v. 22): Sings of oxen-driven leather buckets (*Kapilai* / *Sal*) ascending inclined earthen ramps, splashing cool water into distributing cisterns.\n\n## 2. The Cultural Landscape of Lift Irrigation (*Thottakkal*)\nWhile delta regions relied on river inundation (Kaveri canals), the vast arid uplands (*Mullai* and *Palai*) of Kongu Nadu, Pandya uplands, and Tondaimandalam depended completely on manual and animal-powered lift irrigation:\n- **Ettam / Thulaam (Picottah)**: Counterbalanced first-class lever operated by a walking treader.\n- **Kapilai / Kavalai**: Heavy leather bucket drawn up by a pair of bullocks descending an inclined ramp.\n\n## 3. Agrarian & Ecological Resilience\nLift irrigation allowed Tamil farmers to maintain intensive polyculture—betel vines, sugarcane, turmeric, ginger, and vegetables—through harsh pre-monsoon summers, providing a resilient buffer against drought."
  },
  {
    "slug": "insc-thiruvallam-pallava-well-irrigation-and-picottah-charters",
    "category": "inscriptions",
    "file": "insc-thiruvallam-pallava-well-irrigation-and-picottah-charters.md",
    "node_type": "inscription",
    "name_en": "Thiruvallam Pallava Well Irrigation Charters & Picottah Water Tax Remissions",
    "name_ta": "திருவல்லம் பல்லவர் கிணற்றுப் பாசனம் மற்றும் ஏற்ற வரிநீக்கக் கல்வெட்டுகள்",
    "era": "Pallava Classical Era",
    "year_start": 750,
    "year_end": 880,
    "thinai": "marutham",
    "summary_en": "Inscriptions of Pallava king Nandivarman at the Bilvanatheswara temple in Thiruvallam on the Palar basin, recording water rights for stone-lined wells, tax remissions on picottah levers (Etta-Irai), and maintenance of wooden fulcrums.",
    "summary_ta": "பாலாற்றுப் படுகை திருவல்லம் பில்வநாதேஸ்வரர் கோவில் பல்லவர் கல்வெட்டுகள்; கல் கட்டிய கிணறுகளின் நீர் உரிமை, ஏற்றம் மூலம் நீர் இறைப்போருக்கான 'ஏற்ற-இறை' வரிநீக்கம் மற்றும் மர உந்துதூண் பராமரிப்பு ஆவணங்கள்.",
    "sources": [
      "South Indian Inscriptions Vol III",
      "Epigraphia Indica Vol VII",
      "Pallava Agrarian Inscriptions"
    ],
    "content": "---\nid: insc-thiruvallam-pallava-well-irrigation-and-picottah-charters\ntitle: Thiruvallam Pallava Well Irrigation Charters & Picottah Water Tax Remissions\ntype: inscription\nera: Pallava Classical Era (c. 750 - 880 CE)\nthinai: marutham (Riparian Well Irrigation Epigraphy)\nstatus: canonical\n---\n\n# Thiruvallam: Pallava Well Irrigation Charters & Picottah Water Tax Remissions\n\n## 1. Epigraphical Provenance\nCarved into the base plinth of the ancient Bilvanatheswara temple at Thiruvallam near Vellore on the banks of the Neva river (a tributary of the Palar), these Pallava inscriptions date from the 8th and 9th centuries CE.\n\n## 2. Inscription Mandates & Water Governance\n- **Etta-Irai Tax Exemptions**: Explicitly exempts temple agricultural lands from the royal picottah tax (*Etta-kadamai* / *Etta-irai*), granting permanent water extraction rights from community dry-stone wells.\n- **Fulcrum Timber Allocations**: Guarantees woodcutter concessions for harvesting rot-resistant Ilupai and Tamarind timber to replace worn vertical fulcrum uprights (*Thulaa-maram*).\n- **Proportional Well Sharing (*Pangu-Neer*)**: Establishes rotational shifts (measured in water-clock *Nazhikai* units) governing when individual cultivators could lower their buckets into shared village wells.\n\n## 3. Socio-Economic Insight\nThese inscriptions demonstrate that well irrigation was subject to rigorous legal codification, state taxation, and water rationing, ensuring equitable resource access in hard-rock aquifers."
  },
  {
    "slug": "insc-kovilpatti-pandya-kapilai-leather-bucket-tax-charters",
    "category": "inscriptions",
    "file": "insc-kovilpatti-pandya-kapilai-leather-bucket-tax-charters.md",
    "node_type": "inscription",
    "name_en": "Kovilpatti Pandya Kapilai Leather Bucket Charters & Inclined Ramp Water Epigraphs",
    "name_ta": "கோவில்பட்டி பாண்டியர் கபிலை தோல் சால் பாசனம் மற்றும் சரிவு மேடை கல்வெட்டுகள்",
    "era": "Pandya Classical Era",
    "year_start": 850,
    "year_end": 1150,
    "thinai": "marutham",
    "summary_en": "Pandya stone epigraphs around Kovilpatti in southern Tamil Nadu documenting royal water taxes on oxen-drawn leather bucket systems (Kapilai / Kavalai), ramp slopes, pulley wheels (Uruli), and bullock team licensing.",
    "summary_ta": "தென் தமிழகக் கோவில்பட்டிப் பாண்டியர் கல்வெட்டுகள்; காளைகள் மூலம் இயக்கப்பட்ட தோல் சால் (கபிலை) பாசன வரி, சரிவுப் பாதை அமைப்பு, உருளைச் சக்கரம் மற்றும் நீர்ப்பாசன மாடுகளுக்கான மேய்ச்சல் உரிமை ஆவணங்கள்.",
    "sources": [
      "South Indian Inscriptions Vol XIV",
      "Pandya Irrigation Epigraphy Bulletin",
      "TNSDA Field Reports - Kovilpatti"
    ],
    "content": "---\nid: insc-kovilpatti-pandya-kapilai-leather-bucket-tax-charters\ntitle: Kovilpatti Pandya Kapilai Leather Bucket Charters & Inclined Ramp Water Epigraphs\ntype: inscription\nera: Pandya Classical Era (c. 850 - 1150 CE)\nthinai: marutham (Deep Well Irrigation Epigraphy)\nstatus: canonical\n---\n\n# Kovilpatti: Pandya Kapilai Leather Bucket Charters & Inclined Ramp Water Epigraphs\n\n## 1. Epigraphical Provenance & Arid Zone Setting\nFound inscribed on rock shrines and tank sluice stones in the black cotton soil (*Karisal-kaadu*) tracts around Kovilpatti, these Pandya charters date to the medieval era. Lacking perennial snow-fed rivers, southern Tamil Nadu depended entirely on deep dry-stone wells.\n\n## 2. Inscriptional Decrees & Fiscal Records\n- **Kapilai-Vari (Leather Bucket Tax)**: Imposes and regulates annual levies on operational bullock water-lifts (*Kapilai*), distinguishing between single-ox and double-ox rigs.\n- **Ramp Grading Standards**: Authorizes the construction of earthen ramps (*Errumeddu*) extending from the well head, requiring a statutory 15-degree downhill slope to maximize bovine draft pull.\n- **Pulley Maintenance Endowments**: Allocates funds for replacing cast bronze or oiled wooden pulley axles (*Uruli* / *Kottai*) supporting the heavy wet leather bucket.\n\n## 3. Pastoral-Agrarian Nexus\nThe records highlight the vital symbiosis between livestock husbandry and irrigation: strong, specialized Kangayam and Umblachery draft bullocks were bred specifically to power these lifts, generating surplus agricultural revenue in semi-arid terrains."
  },
  {
    "slug": "concept-first-class-lever-mechanics-and-ettam-counterpoise-balance",
    "category": "concepts",
    "file": "concept-first-class-lever-mechanics-and-ettam-counterpoise-balance.md",
    "node_type": "concept",
    "name_en": "First-Class Lever Mechanics, Ettam Counterpoise Balance & Walking-Treader Ergonomics",
    "name_ta": "முதலாம் வகை நெம்புகோல் இயங்கியல், ஏற்ற மர சமநிலை மற்றும் நடப்பவர் உந்துவிசை",
    "era": "Sangam Classical Era",
    "year_start": -400,
    "year_end": 1200,
    "thinai": "mullai",
    "summary_en": "Mechanical physics of the ancient Tamil picottah (Ettam / Thulaam): applying first-class lever equilibrium where a counterbalancing stone ballast (Ettak-kal) neutralizes the dead weight of water, allowing a walking treader (Ettak-kaaran) to effortlessly lift 50-80 liters per minute.",
    "summary_ta": "முதலாம் வகை நெம்புகோல் தத்துவத்தின்படி (First-class lever), ஆதாரப் புள்ளியில் சுழலும் மரக்கட்டை மீது எடைக் கல்லைக் கட்டி நீரின் எடையைச் சமன் செய்து, ஏத்தமரத்தில் நடந்து சென்று நிமிடத்திற்கு 50-80 லிட்டர் நீரை எளிதில் இறைத்த பண்டைய இயற்பியல் நுட்பம்.",
    "sources": [
      "Kurunthokai v. 238",
      "Srinivasan: Traditional Water Harvesting Systems",
      "Historical Physics of South Indian Agriculture"
    ],
    "content": "---\nid: concept-first-class-lever-mechanics-and-ettam-counterpoise-balance\ntitle: First-Class Lever Mechanics, Ettam Counterpoise Balance & Walking-Treader Ergonomics\ntype: concept\nera: Sangam Classical Era (c. 400 BCE - 1200 CE)\nthinai: mulli (Mechanical Lever Engineering)\nstatus: canonical\n---\n\n# First-Class Lever Mechanics, Ettam Counterpoise Balance & Walking-Treader Ergonomics\n\n## 1. Classical First-Class Lever Equilibrium\nThe **Ettam** (or *Thulaam* / picottah) is a textbook application of the classical first-class mechanical lever, where the fulcrum (*Aatharam*) is positioned between the effort (*Visai*) and the load (*Pazhu*):\n$$\\text{Effort} \\times \\text{Effort Arm} = \\text{Load} \\times \\text{Load Arm}$$\n\n## 2. Anatomical Structure of the Machine\n1. **Vertical Forked Fulcrum Post (*Thulaa-Thoon*)**: A heavy forked trunk of durable hardwood (tamarind or palmyrah) firmly embedded in stone masonry at the lip of the well.\n2. **Pivoting Balance Beam (*Maram*)**: A long, slender palmyrah trunk (length 6 to 9 meters) balanced horizontally across the fulcrum on an oiled iron or hardwood axle.\n3. **Counterpoise Ballast (*Ettak-Kal*)**: A dense granitic boulder (weighing 30 to 50 kg) lashed securely with coir rope to the short rear arm of the beam. The stone ballast exactly balances the tare weight of the empty bucket plus half the water load.\n4. **Suspended Bamboo Rod (*Kozhu-Kombu*)**: A long vertical bamboo rod hung from the long front arm of the beam down into the well, terminating in an iron or leather scoop bucket (*Sal*).\n\n## 3. Walking-Treader Dynamic Ergonomics (*Ettam-Mithitthal*)\nTo lift water with minimum human fatigue:\n- The operator (*Ettak-kaaran*) walks forward along the top of the pivoting beam toward the well. His body weight overcomes the counterpoise stone, causing the bucket to plunge deep into the water table.\n- Once the bucket fills, the operator turns and walks backward along the beam toward the fulcrum. Relieved of his body weight, the heavy stone ballast sinks downward, effortlessly pulling the water-filled bucket to the surface.\n- A secondary worker on the ground simply guides the bucket and tips it into the distributing trough. A single treader could effortlessly elevate 3,000 to 5,000 liters of water per hour from depths of up to 8 meters."
  },
  {
    "slug": "concept-kapilai-oxen-driven-inclined-ramp-and-leather-bucket-hydraulics",
    "category": "concepts",
    "file": "concept-kapilai-oxen-driven-inclined-ramp-and-leather-bucket-hydraulics.md",
    "node_type": "concept",
    "name_en": "Kapilai Oxen-Driven Inclined Ramp Hydraulics, Leather Funnel Buckets & Auto-Discharge",
    "name_ta": "கபிலை மாட்டுப் பாசனம், சரிவு மேடை ஈர்ப்பு விசை மற்றும் தோல் சால் தானியங்கி நீர் வெளியேற்றம்",
    "era": "Early Historic to Medieval Era",
    "year_start": -300,
    "year_end": 1200,
    "thinai": "marutham",
    "summary_en": "Mechanical engineering of deep well lifts (Kapilai / Kavalai): dual-rope leather bucket systems with automatic trunk discharge funnels, pulled by a pair of bullocks descending an inclined earthen ramp utilizing animal gravity to lift 150-200 liters per draw.",
    "summary_ta": "ஆழ்துளைக் கிணறுகளிலிருந்து 150-200 லிட்டர் நீரை ஒரே முறையில் இறைக்க, காளைகள் சரிவுப் பாதையில் இறங்கி ஈர்ப்பு விசையைப் பயன்படுத்திய கபிலை தோல் சால் மற்றும் தானியங்கி வெளியேற்று வால்வுப் பொறியியல்.",
    "sources": [
      "Kalithogai v. 22",
      "Pandya Inscriptions of Tirunelveli District",
      "Indigenous Agricultural Technologies of India"
    ],
    "content": "---\nid: concept-kapilai-oxen-driven-inclined-ramp-and-leather-bucket-hydraulics\ntitle: Kapilai Oxen-Driven Inclined Ramp Hydraulics, Leather Funnel Buckets & Auto-Discharge\ntype: concept\nera: Early Historic to Medieval Era (c. 300 BCE - 1200 CE)\nthinai: marutham (Bovine Draft & Deep-Well Hydraulics)\nstatus: canonical\n---\n\n# Kapilai Oxen-Driven Inclined Ramp Hydraulics, Leather Funnel Buckets & Auto-Discharge\n\n## 1. Deep Aquifer Water Elevation\nWhen water tables exceeded 8 to 15 meters in depth, manual picottah levers became mechanically inefficient. In response, ancient Tamil engineers developed the **Kapilai** (or *Kavalai*), an ingenious animal-powered system utilizing bovine draft traction and gravity assistance.\n\n## 2. Dual-Rope & Trunk-Bucket Architecture\n1. **The Conical Leather Bucket (*Sal*)**: Fabricated from thick, oil-tanned water-buffalo hide, comprising a wide cylindrical upper body holding 150 to 200 liters of water, tapering at the bottom into a long flexible leather funnel or trunk (*Vali*).\n2. **Dual-Pulley Rigging**:\n   - **Upper Main Pulley (*Periya-Uruli*)**: Positioned high over the well head, carrying the thick master coir rope attached to the rim of the bucket.\n   - **Lower Guide Pulley (*Chinna-Uruli*)**: Positioned lower at the lip of the water discharge trough, carrying a secondary thinner rope attached to the tip of the leather trunk.\n3. **Synchronized Auto-Discharge**:\n   - While ascending through the well shaft, the lower rope keeps the trunk held upright alongside the bucket body, preventing water spillage.\n   - When the bucket reaches the surface, the lower rope pulls the trunk horizontally over the masonry discharge channel while the main bucket continues rising. The water automatically discharges in a massive, foaming torrent without human intervention!\n\n## 3. Inclined Gravity Ramp (*Errumedu*)\nThe pair of bullocks was hitched to the ropes at the top of an earthen ramp sloping downward away from the well at an angle of 10 to 15 degrees:\n- As the bullocks walked downhill, their own body weight aided their traction against the heavy water load.\n- Reaching the bottom of the ramp, the bucket emptied; the driver unhitched the yoke or walked the bullocks backward up the ramp while the empty bucket dropped into the water table under gravity."
  },
  {
    "slug": "concept-dry-stone-cylindrical-well-lining-and-aquifer-tapping-kinaru",
    "category": "concepts",
    "file": "concept-dry-stone-cylindrical-well-lining-and-aquifer-tapping-kinaru.md",
    "node_type": "concept",
    "name_en": "Dry-Stone Cylindrical Well Lining (Kinaru), Un-Mortared Granitic Steining & Infiltration",
    "name_ta": "உலர்ந்த கருங்கல் உருளைக் கிணறு கட்டுமானம் (கிணறு), காரையற்ற கல் கட்டு மற்றும் நீர் ஊற்று ஊடுருவல்",
    "era": "Early Historic Era",
    "year_start": -400,
    "year_end": 1000,
    "thinai": "marutham",
    "summary_en": "Hydrogeological civil engineering of deep irrigation wells: circular dry-stone granite lining (steining) without mortar, utilizing radial arch compression to resist lateral soil pressure while allowing subterranean freshwater springs to weep freely into the sump.",
    "summary_ta": "சுண்ணாம்புக் காரையின்றி, செதுக்கப்பட்ட கருங்கற்களை வட்ட வடிவில் முட்டுக் கொடுத்து அடுக்கி (Radial arch compression), பக்கவாட்டு மண் அழுத்தத்தைத் தாங்கி ஊற்று நீரைத் தடையின்றி உள்ளே வரவழைத்த பண்டைய கிணற்றுப் பொறியியல்.",
    "sources": [
      "Purananuru v. 230",
      "Sangam Irrigation Memoirs",
      "Traditional Water Well Construction in South India"
    ],
    "content": "---\nid: concept-dry-stone-cylindrical-well-lining-and-aquifer-tapping-kinaru\ntitle: Dry-Stone Cylindrical Well Lining (Kinaru), Un-Mortared Granitic Steining & Infiltration\ntype: concept\nera: Early Historic Era (c. 400 BCE - 1000 CE)\nthinai: marutham (Hydrogeology & Well Engineering)\nstatus: canonical\n---\n\n# Dry-Stone Cylindrical Well Lining (Kinaru), Un-Mortared Granitic Steining & Infiltration\n\n## 1. Radial Arch Compression Physics\nTo excavate wells 10 to 20 meters deep through loose alluvium, gravel, and weathered rock without wall cave-ins, ancient Tamil masons developed un-mortared dry-stone circular steining (*Kal-Kattu*):\n- **Cylindrical Geometry**: The circular cross-section acts as a continuous closed horizontal ring arch. Lateral soil and hydrostatic pressure push inward on the stones, forcing the tapered wedge-shaped granite blocks tighter together in compressive self-lock.\n- **Mortarless Weep-Hole Infiltration**: Because no impermeable lime mortar was used in the lower tiers, subterranean spring water from surrounding aquifer seams seeped freely through the unsealed stone joints, rapidly recharging the well reservoir.\n\n## 2. Curb Sinking Construction Method\n1. **Wooden Well Curb (*Azhithundam*)**: A circular ring of tough, rot-resistant timber (tamarind or mahua) with a beveled bottom cutting edge was placed on the excavation floor.\n2. **Masonry Steining Build-Up**: Masons laid courses of dressed, curved granite blocks on top of the timber curb.\n3. **Progressive Sinking**: As soil was scooped from beneath the cutting curb, the heavy stone cylinder sank under its own dead weight into the water table, keeping diggers safe from cave-ins throughout the excavation.\n\n## 3. Heavy Parapet Coping (*Kinaru-Kattu*)\nThe well was finished above ground level with a thick, massive circular stone coping wall (*Man-chuvadu*) that prevented surface mud runoff from contaminating the water, provided mounting seats for the picottah fulcrums, and served as a working platform."
  },
  {
    "slug": "concept-garden-furrow-distribution-and-thoppu-irrigation-networks",
    "category": "concepts",
    "file": "concept-garden-furrow-distribution-and-thoppu-irrigation-networks.md",
    "node_type": "concept",
    "name_en": "Garden Furrow Distribution (Thoppu-Vaykkal), Masonry Basins & Precision Micro-Hydraulics",
    "name_ta": "தோட்டக்கால் பாத்தி பாசனம், செங்கல் தொட்டி நீர்ப்பகிர்வு மற்றும் துல்லிய நீர்ப்பாசன அமைப்பு",
    "era": "Sangam Classical Era",
    "year_start": -300,
    "year_end": 1200,
    "thinai": "mullai",
    "summary_en": "On-farm water distribution networks in ancient Tamil dryland agriculture: receiving lifted water in raised masonry cisterns (Kottuk-kinnam), distribution through earthen channel furrows (Paathi-vaykkal) using cloth plugs and wooden sluice boards for precision garden crops.",
    "summary_ta": "கிணற்றிலிருந்து இறைக்கப்பட்ட நீரை உயர்த்திய செங்கல் தொட்டிகளில் சேகரித்து, சமமட்டக் கால்வாய்கள் மற்றும் துணி அடைப்பான்கள் மூலம் பாத்திகளுக்குப் பிரித்துப் பாய்ச்சிய தோட்டக்கால் நுண்ணிய நீர்ப்பாசன மேலாண்மை.",
    "sources": [
      "Purananuru v. 384",
      "Perumpanarruppadai ll. 190-210",
      "Chola Village Agricultural Manuals"
    ],
    "content": "---\nid: concept-garden-furrow-distribution-and-thoppu-irrigation-networks\ntitle: Garden Furrow Distribution (Thoppu-Vaykkal), Masonry Basins & Precision Micro-Hydraulics\ntype: concept\nera: Sangam Classical Era (c. 300 BCE - 1200 CE)\nthinai: mullai (Micro-Irrigation & Agro-Hydraulics)\nstatus: canonical\n---\n\n# Garden Furrow Distribution (Thoppu-Vaykkal), Masonry Basins & Precision Micro-Hydraulics\n\n## 1. From Well Lift to Crop Root Zone\nBecause water lifted by picottah or bullock bucket represents hard-won physical energy, none was allowed to waste through uncontrolled flooding. Ancient Tamil garden agriculture (*Thoppu* / *Kollai*) developed meticulous micro-gravity irrigation networks.\n\n## 2. Hydraulic Components of the System\n1. **The Head Surge Cistern (*Kottu-Kozhi*)**: A small brick-and-lime paved basin directly beneath the well discharge point that absorbed the splashing turbulence of the emptying bucket and converted it into calm, steady laminar gravity flow.\n2. **Main Feeder Flume (*Thala-Vaykkal*)**: Elevated earthen or brick-lined conduit laid along the highest contour ridge of the farm plot.\n3. **Check-Basin & Furrow Layout (*Paathi*)**: The cultivated land was divided into a grid of small, perfectly leveled rectangular beds (*Paathi*) surrounded by low earthen bunds:\n   - **Check-Weirs (*Madagu-Kallu*)**: Sockets cut into channel banks fitted with flat stones or bundle plugs of straw and cloth.\n   - **Sequenced Inundation**: The cultivator opened one furrow at a time, filling each bed to an exact depth of 5 to 7 cm before plugging the intake and directing water to the adjacent furrow.\n\n## 3. Crop Specialization\nThis micro-irrigation system supported high-value, labor-intensive horticultural crops: betel leaf (*Vetrilai*), areca palms, sugarcane, ginger, turmeric, and flowering jasmine, transforming semi-arid red soil tracts into perennial garden paradises."
  },
  {
    "slug": "char-thiruvallam-master-picottah-carpenter-ettath-thatchan",
    "category": "characters",
    "file": "char-thiruvallam-master-picottah-carpenter-ettath-thatchan.md",
    "node_type": "character",
    "name_en": "Master Picottah Carpenter & Well Lever Engineer of Thiruvallam (Ettath-Thatchan)",
    "name_ta": "திருவல்லம் தலைமை ஏற்றக் கட்டை தச்சர் மற்றும் துலாப் பொறியாளர் (ஏற்றத் தச்சன்)",
    "era": "Pallava Classical Era",
    "year_start": 800,
    "year_end": 860,
    "thinai": "marutham",
    "summary_en": "Hereditary master carpenter and mechanical lever engineer attached to temple agrarian estates at Thiruvallam, expert in balance timber selection, counterweight stone rigging, and friction-reduced oiled pivots.",
    "summary_ta": "திருவல்லம் பல்லவர் பாசனப் படுகையில் ஏற்ற மரங்களை வடிவமைத்த, மர ஆதாரப் புள்ளி சமநிலை, சுழல் அச்சு எண்ணெய் உயவு மற்றும் எடைக் கல் பிணைப்பில் கைதேர்ந்த தலைமை ஏற்றத் தச்சன்.",
    "sources": [
      "Thiruvallam Pallava Inscriptions",
      "South Indian Inscriptions Vol III",
      "Village Craft Archives of Tondaimandalam"
    ],
    "content": "---\nid: char-thiruvallam-master-picottah-carpenter-ettath-thatchan\ntitle: Master Picottah Carpenter & Well Lever Engineer of Thiruvallam (Ettath-Thatchan)\ntype: character\nera: Pallava Classical Era (c. 800 - 860 CE)\nthinai: marutham (Agrarian Mechanical Carpentry)\nstatus: canonical\n---\n\n# Master Picottah Carpenter & Well Lever Engineer of Thiruvallam (Ettath-Thatchan)\n\n## 1. Professional Office & Guild Role\nThe **Ettath-Thatchan** (Master Picottah Carpenter) held a vital hereditary office in the agricultural administration of the Palar river basin. Endowed with tax-exempt *Thatcha-kaani* lands under Pallava charters, he was responsible for manufacturing, balancing, and maintaining all mechanical well-lift beams across communal and temple farmsteads.\n\n## 2. Mechanical Expertise\n- **Timber Selection & Seasoning**: Selected aged palmyrah palm trunks (*Aan-panai*) for balance beams, balancing high bending strength with minimal dead weight.\n- **Axle Friction Reduction**: Fabricated hardened acacia or babool pivot pins (*Aani*), lubricated with continuous baths of castor oil to eliminate squeaking and rotational friction.\n- **Dynamic Counterweight Balancing**: Precisely calculated the placement and poundage of the stone ballast (*Ettak-kal*) to match the physical strength and body weight of individual village treaders."
  },
  {
    "slug": "char-kovilpatti-master-leather-water-bag-craftsman-sal-kollan",
    "category": "characters",
    "file": "char-kovilpatti-master-leather-water-bag-craftsman-sal-kollan.md",
    "node_type": "character",
    "name_en": "Master Leather Water-Bag Craftsman of Kovilpatti (Sal-Kollan)",
    "name_ta": "கோவில்பட்டி தலைமை தோல் சால் கைவினைஞர் (சால் தையல் கொல்லன்)",
    "era": "Pandya Classical Era",
    "year_start": 900,
    "year_end": 970,
    "thinai": "marutham",
    "summary_en": "Master leather tanner and hydraulic bucket stitcher of Kovilpatti, master of oil-tanning heavy buffalo hides, double-seam sinew stitching, and seamless funnel trunk discharge valves for Kapilai water lifts.",
    "summary_ta": "கோவில்பட்டி கரிசல் நிலப் பகுதியில் காளைகள் மூலம் இயங்கும் கபிலை தோல் சால்களை (தோல் வாளி) எருமைத் தோலில் தைத்து, நீர் கசியாமல் நெடுங்காலம் உழைக்கும்படி பதப்படுத்திய தலைமைத் தோல் கைவினைஞர்.",
    "sources": [
      "Pandya Inscriptions of Tirunelveli District",
      "South Indian Leather Guild Charters",
      "TNSDA Craft Surveys"
    ],
    "content": "---\nid: char-kovilpatti-master-leather-water-bag-craftsman-sal-kollan\ntitle: Master Leather Water-Bag Craftsman of Kovilpatti (Sal-Kollan)\ntype: character\nera: Pandya Classical Era (c. 900 - 970 CE)\nthinai: marutham (Hydraulic Leather Technology)\nstatus: canonical\n---\n\n# Master Leather Water-Bag Craftsman of Kovilpatti (Sal-Kollan)\n\n## 1. Craft Stature & Agricultural Value\nThe **Sal-Kollan** (Master Craftsman of Hydraulic Leather Buckets) occupied an indispensable technological niche in the black cotton soil belt of Kovilpatti. Without his heavy-duty leather buckets, deep-well bullock irrigation would have been impossible.\n\n## 2. Tanning & Stitching Mastery\n- **Oil & Bark Tanning**: Tanned raw water-buffalo hides in vats charged with acacia and avaram bark extracts, followed by heavy saturation with neem and fish oils to produce thick, pliable, water-impermeable leather that would not rot under continuous submersion.\n- **Double-Seam Sinew Stitching**: Stitched the conical funnel seams with dried animal sinew (*Narambu*) and twisted palm cordage, coating stitch perforations with beeswax and tree resin to prevent leakage.\n- **Mouth Iron Ring Forging**: Hammered heavy round iron hoops (*Koodai-valayam*) riveted to the leather lip, keeping the bucket mouth permanently open for instant water scoop upon submersion."
  },
  {
    "slug": "place-thiruvallam-ancient-picottah-haven",
    "category": "places",
    "file": "place-thiruvallam-ancient-picottah-haven.md",
    "node_type": "place",
    "name_en": "Thiruvallam Ancient Picottah Haven & Palar Basin Well-Irrigation Sanctuary",
    "name_ta": "திருவல்லம் பண்டைய ஏற்றப் பாசனத் தளம் மற்றும் பாலாற்றுப் படுகை கிணற்றுப் பகுதி",
    "era": "Pallava to Chola Era",
    "year_start": 600,
    "year_end": 1250,
    "thinai": "marutham",
    "summary_en": "Strategic agricultural and temple center on the Palar basin in northern Tamil Nadu, renowned for extensive stone-lined well networks, royal inscriptions regulating picottah water taxes, and prosperous garden estates.",
    "summary_ta": "வட தமிழகத்துப் பாலாற்றுப் படுகையில் அமைந்த வரலாற்றுப் புகழ்பெற்ற பாசன நகரம்; செதுக்கப்பட்ட கருங்கல் கிணறுகள், பல்லவர் கால ஏற்ற வரிநீக்கக் கல்வெட்டுகள் மற்றும் பசுமைத் தோட்டக்கால் வேளாண்மையின் உறைவிடம்.",
    "sources": [
      "South Indian Inscriptions Vol III",
      "Archaeological Survey of the Palar Basin",
      "Epigraphia Indica Vol VII"
    ],
    "content": "---\nid: place-thiruvallam-ancient-picottah-haven\ntitle: Thiruvallam Ancient Picottah Haven & Palar Basin Well-Irrigation Sanctuary\ntype: place\nera: Pallava to Chola Era (c. 600 - 1250 CE)\nthinai: marutham (Well Irrigation Heartland)\nstatus: canonical\n---\n\n# Thiruvallam Ancient Picottah Haven & Palar Basin Well-Irrigation Sanctuary\n\n## 1. Geographical Location & Riparian Hydrology\nThiruvallam is located on the northern bank of the Palar river in Vellore district (coordinates approx. 12.9500° N, 79.2333° E). Surrounded by fertile alluvium underlain by shallow hard-rock aquifers, it was the ideal hydraulic center for high-density well irrigation.\n\n## 2. Archaeological Features & Well Remains\nSurveys and excavations around the Bilvanatheswara temple complex have revealed:\n- **Dry-Stone Granite Wells**: Massive circular wells lined with un-mortared charnockite blocks that continue to yield water after twelve centuries.\n- **Picottah Fulcrum Bases**: Stone sockets cut into well parapets where wooden fulcrum posts were anchored.\n- **Inscriptional Archives**: Multiple Pallava and Chola inscriptions detailing water-sharing quotas, picottah maintenance endowments, and canal regulations.\n\n## 3. Model of Ancient Dryland Prosperity\nThiruvallam stands as a paramount testament to the ecological ingenuity of ancient Tamil rural engineering, demonstrating how simple wooden levers and stone wells sustained flourishing civilization independent of major river dams."
  }
]

EDGES = [
  [
    "text-sangam-jaina-ascetic-cavern-and-renunciation-poetry",
    "describes_rock_monasteries",
    "concept-chisel-dressed-polished-granite-monk-beds-kal-padukai",
    "literature",
    "Early Historic Era",
    "Sangam poetry depicts Jaina ascetic rock shelters and polished granite monk beds around Madurai.",
    "Maduraikkanchi ll. 475-490"
  ],
  [
    "insc-mankulam-nedunchezhiyan-pandya-jaina-cavern-charters",
    "records_royal_endowment_at",
    "place-mankulam-ancient-jaina-cavern-haven",
    "epigraphy",
    "Early Historic Era",
    "Mankulam Tamil-Brahmi inscriptions record King Nedunchezhiyan endowing rock shelters to Jaina monks.",
    "Mahadevan: Early Tamil Epigraphy"
  ],
  [
    "insc-kizhavalavu-tamil-brahmi-stone-bed-donative-epigraphs",
    "records_stone_beds_at",
    "concept-chisel-dressed-polished-granite-monk-beds-kal-padukai",
    "epigraphy",
    "Early Historic Era",
    "Kizhavalavu rock inscriptions record merchant guilds donating stone beds with integral pillow ledges.",
    "Epigraphia Indica Vol XXXII"
  ],
  [
    "concept-granitic-rock-cleaving-wooden-wedge-swelling-mechanics",
    "enables_fabrication_of",
    "concept-chisel-dressed-polished-granite-monk-beds-kal-padukai",
    "quarrying",
    "Early Historic Era",
    "Wooden wedge hydraulic expansion cleaved level surfaces for carving polished monk beds.",
    "Sankalia: Stone Age Tools & Techniques"
  ],
  [
    "concept-drip-ledge-rain-deflection-grooves-kavadi-engineering",
    "protects_shelter_of",
    "place-mankulam-ancient-jaina-cavern-haven",
    "hydraulics",
    "Early Historic Era",
    "V-shaped drip-ledge grooves deflected monsoon rainfall away from the living quarters at Mankulam.",
    "TNSDA Archaeological Survey"
  ],
  [
    "char-mankulam-master-cavern-sculptor-kudaivarai-sirpan",
    "chiseled_shelters_at",
    "place-mankulam-ancient-jaina-cavern-haven",
    "architecture",
    "Early Historic Era",
    "The master cavern sculptor chiseled drip-ledges and polished stone beds on Ovamalai hill.",
    "Mankulam Inscriptions"
  ],
  [
    "char-madurai-jaina-monastic-acharya-kanikkayar",
    "presided_over_monastery_at",
    "place-mankulam-ancient-jaina-cavern-haven",
    "monasticism",
    "Early Historic Era",
    "Acharya Kani-Nanda-Asiriyan led the Jaina monastic community residing in the Mankulam rock shelters.",
    "Mankulam Inscription I"
  ],
  [
    "concept-tamil-brahmi-epigraphical-palaeography-and-asokan-divergence",
    "incised_beneath_grooves",
    "concept-drip-ledge-rain-deflection-grooves-kavadi-engineering",
    "palaeography",
    "Early Historic Era",
    "Tamil-Brahmi inscriptions were incised on the vertical brow directly beneath the rain drip-ledge.",
    "Mahadevan: Early Tamil Epigraphy"
  ],
  [
    "char-mankulam-master-cavern-sculptor-kudaivarai-sirpan",
    "utilized_cleaving_technique",
    "concept-granitic-rock-cleaving-wooden-wedge-swelling-mechanics",
    "quarrying",
    "Early Historic Era",
    "The master sculptor drove swelling hardwood wedges into mortise sockets to split monolithic granite.",
    "Ancient Indian Quarrying Engineering"
  ],
  [
    "text-sangam-jaina-ascetic-cavern-and-renunciation-poetry",
    "praises_ascetic_preceptor",
    "char-madurai-jaina-monastic-acharya-kanikkayar",
    "literature",
    "Early Historic Era",
    "Classical verses praise the spiritual renunciation of Jaina preceptors meditating in hill caverns.",
    "Silappadikaram Nadukankathai"
  ],
  [
    "text-akanunuru-carnelian-gem-traders-and-lapidary-poetry",
    "describes_red_gemstones",
    "concept-agate-and-carnelian-iron-oxide-thermal-reddening-pyrotechnics",
    "literature",
    "Sangam Classical Era",
    "Akananuru poetry describes red carnelian gems (Sem-mani) heated in furnaces to intensify color.",
    "Akananuru v. 155, 315"
  ],
  [
    "insc-porunthal-chera-carnelian-bead-furnace-charters",
    "proves_early_drilling",
    "concept-micro-diamond-twin-mandrel-bow-drilling-mechanics",
    "epigraphy",
    "Early Historic Era",
    "Porunthal 5th-century BCE excavations yielded thousands of carnelian beads perforated by micro-diamond drills.",
    "Rajan: Porunthal Excavations Report"
  ],
  [
    "insc-kodumanal-etched-carnelian-merchant-guild-epigraphs",
    "attests_chemical_etching",
    "concept-alkaline-chemical-etching-plant-soda-slurry-and-heating",
    "epigraphy",
    "Sangam Classical Era",
    "Kodumanal inscribed potsherds and chemical palettes attest to alkaline etching of carnelian gems.",
    "Kodumanal Excavation Reports"
  ],
  [
    "concept-agate-and-carnelian-iron-oxide-thermal-reddening-pyrotechnics",
    "prepares_stones_for",
    "concept-alkaline-chemical-etching-plant-soda-slurry-and-heating",
    "pyrotechnics",
    "Early Historic Era",
    "Thermal dehydration of limonite into hematite produced the dark red ground required for white alkaline etching.",
    "Beck: Etched Carnelian Beads"
  ],
  [
    "concept-alkaline-chemical-etching-plant-soda-slurry-and-heating",
    "perforated_by_mechanics",
    "concept-micro-diamond-twin-mandrel-bow-drilling-mechanics",
    "lapidary",
    "Early Historic Era",
    "Etched carnelian beads were perforated from opposite poles using twin-mandrel diamond bow drills.",
    "Kenoyer: Gem Lapidary Technologies"
  ],
  [
    "concept-tumble-polishing-hardwood-grooves-and-corundum-slurry",
    "mass_finishes_beads_at",
    "place-kangeyam-ancient-gem-lapidary-haven",
    "manufacturing",
    "Sangam Classical Era",
    "Tumble polishing troughs charged with corundum slurry mass-finished gem beads in the Kangeyam basin.",
    "Kodumanal Lapidary Debitage Studies"
  ],
  [
    "char-kodumanal-master-carnelian-etcher-kalluppu-achari",
    "perfected_etching_slurry",
    "concept-alkaline-chemical-etching-plant-soda-slurry-and-heating",
    "chemistry",
    "Sangam Classical Era",
    "The master etcher formulated natural plant soda and spurge latex slurries to create indelible white lines.",
    "Journal of Field Archaeology"
  ],
  [
    "char-porunthal-gemstone-micro-driller-mani-thulaithor",
    "operated_diamond_drills_at",
    "insc-porunthal-chera-carnelian-bead-furnace-charters",
    "micro_mechanics",
    "Early Historic Era",
    "The master gem driller operated diamond-tipped bow spindles at Porunthal with zero breakage tolerances.",
    "Porunthal Micro-Drill Analysis"
  ],
  [
    "place-kangeyam-ancient-gem-lapidary-haven",
    "mined_and_supplied_crystals",
    "concept-agate-and-carnelian-iron-oxide-thermal-reddening-pyrotechnics",
    "mining",
    "Sangam Classical Era",
    "Kangeyam pegmatite and alluvial mines supplied raw chalcedony and beryl nodules for thermal processing.",
    "Padiyur-Kangeyam Beryl Mining Memoirs"
  ],
  [
    "char-kodumanal-master-carnelian-etcher-kalluppu-achari",
    "operated_at_mining_haven",
    "place-kangeyam-ancient-gem-lapidary-haven",
    "guild",
    "Sangam Classical Era",
    "Master chemical lapidaries operated throughout the Kangeyam-Noyyal gemstone manufacturing zone.",
    "Archaeological Survey of the Noyyal Basin"
  ],
  [
    "text-kurunthokai-ettam-well-irrigation-and-picottah-poetry",
    "poetically_celebrates_picottah",
    "concept-first-class-lever-mechanics-and-ettam-counterpoise-balance",
    "literature",
    "Sangam Classical Era",
    "Kurunthokai verses sing of the rhythmic creaking and balanced leverage of the picottah well sweep.",
    "Kurunthokai v. 238"
  ],
  [
    "insc-thiruvallam-pallava-well-irrigation-and-picottah-charters",
    "regulates_picottah_rights_at",
    "place-thiruvallam-ancient-picottah-haven",
    "epigraphy",
    "Pallava Classical Era",
    "Pallava inscriptions at Thiruvallam record royal water tax exemptions for picottah well irrigation.",
    "South Indian Inscriptions Vol III"
  ],
  [
    "insc-kovilpatti-pandya-kapilai-leather-bucket-tax-charters",
    "records_oxen_lifts_at",
    "concept-kapilai-oxen-driven-inclined-ramp-and-leather-bucket-hydraulics",
    "epigraphy",
    "Pandya Classical Era",
    "Kovilpatti Pandya charters record taxes on oxen-drawn leather bucket water lifts and inclined ramps.",
    "South Indian Inscriptions Vol XIV"
  ],
  [
    "concept-first-class-lever-mechanics-and-ettam-counterpoise-balance",
    "lifts_water_from",
    "concept-dry-stone-cylindrical-well-lining-and-aquifer-tapping-kinaru",
    "hydraulics",
    "Sangam Classical Era",
    "The counterbalanced picottah lever lifted water from deep circular dry-stone granite wells.",
    "Srinivasan: Water Harvesting Systems"
  ],
  [
    "concept-kapilai-oxen-driven-inclined-ramp-and-leather-bucket-hydraulics",
    "feeds_distribution_channels",
    "concept-garden-furrow-distribution-and-thoppu-irrigation-networks",
    "agriculture",
    "Early Historic to Medieval Era",
    "Automatic discharge leather buckets emptied water into head cisterns feeding garden furrow networks.",
    "Indigenous Agricultural Technologies"
  ],
  [
    "char-thiruvallam-master-picottah-carpenter-ettath-thatchan",
    "balanced_wooden_levers_at",
    "place-thiruvallam-ancient-picottah-haven",
    "engineering",
    "Pallava Classical Era",
    "The master carpenter shaped balance beams and calibrated counterweight stones across Thiruvallam wells.",
    "Thiruvallam Pallava Inscriptions"
  ],
  [
    "char-kovilpatti-master-leather-water-bag-craftsman-sal-kollan",
    "stitched_leather_buckets_for",
    "concept-kapilai-oxen-driven-inclined-ramp-and-leather-bucket-hydraulics",
    "craft",
    "Pandya Classical Era",
    "The master leather craftsman tanned buffalo hides and stitched seamless funnel buckets for Kapilai lifts.",
    "South Indian Leather Guild Charters"
  ],
  [
    "concept-dry-stone-cylindrical-well-lining-and-aquifer-tapping-kinaru",
    "sustains_gardens_of",
    "place-thiruvallam-ancient-picottah-haven",
    "hydrology",
    "Pallava to Chola Era",
    "Circular un-mortared granite wells tapped deep aquifers to sustain the lush gardens of Thiruvallam.",
    "Archaeological Survey of the Palar Basin"
  ],
  [
    "char-thiruvallam-master-picottah-carpenter-ettath-thatchan",
    "applied_lever_physics",
    "concept-first-class-lever-mechanics-and-ettam-counterpoise-balance",
    "mechanics",
    "Pallava Classical Era",
    "The master carpenter engineered first-class lever equilibrium on walking balance beams.",
    "Historical Physics of South Indian Agriculture"
  ],
  [
    "concept-garden-furrow-distribution-and-thoppu-irrigation-networks",
    "irrigates_crops_sung_in",
    "text-kurunthokai-ettam-well-irrigation-and-picottah-poetry",
    "literature",
    "Sangam Classical Era",
    "Sangam poetry depicts lush garden crops nourished by furrow networks receiving well water.",
    "Purananuru v. 230"
  ]
]

def main():
    print("=" * 70)
    print("🚀 TRIPLE CIVILIZATIONAL EXPANSION HARVESTER - BATCH 19")
    print("=" * 70)
    print(f"Total dossiers to ingest: {len(DOSSIERS)}")
    print(f"Total edges to insert: {len(EDGES)}")

    # Phase 1: Write Dossiers to moolam-chronicles
    print("\n[Phase 1] Writing 30 Markdown Dossiers to Moolam Chronicles...")
    for d in DOSSIERS:
        cat_dir = os.path.join(MOOLAM_KNOWLEDGE, d["category"])
        os.makedirs(cat_dir, exist_ok=True)
        file_path = os.path.join(cat_dir, d["file"])
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(d["content"].strip() + "\n")
        print(f"  ✓ Wrote: {d['category']}/{d['file']}")
    print("Phase 1 complete: 30 dossiers written to disk.")

    # Phase 2: PostgreSQL DB Upsert
    print(f"\n[Phase 2] Connecting to PostgreSQL at {DB_URL}...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    nodes_upserted = 0
    for d in DOSSIERS:
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
            d["slug"],
            d["node_type"],
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
        print(f"  ✓ [{d['node_type'].upper()}] {d['slug']} -> {d['name_en'][:45]}...")

    conn.commit()
    print(f"Phase 2 complete: {nodes_upserted} lore nodes upserted.")

    # Phase 3: Insert Relational Edges
    print(f"\n[Phase 3] Inserting {len(EDGES)} Relational Cross-Domain Edges...")
    edges_inserted = 0
    for edge in EDGES:
        src, rel, tgt, layer, era, desc, evidence = edge
        cur.execute("""
            SELECT 1 FROM lore_edges 
            WHERE source_slug = %s AND relation_type = %s AND target_slug = %s;
        """, (src, rel, tgt))
        if cur.fetchone():
            continue

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

    print(f"\n🎉 Batch 19 Expansion Complete!")
    print(f"  - 30 Markdown files written to: {MOOLAM_KNOWLEDGE}")
    print(f"  - {nodes_upserted} lore nodes upserted into PostgreSQL")
    print(f"  - {edges_inserted} cross-domain edges linked in PostgreSQL")
    print(f"  - {total_chunks} 1024-dim BGE-M3 vector chunks embedded")

if __name__ == "__main__":
    main()
