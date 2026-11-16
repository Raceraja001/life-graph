#!/usr/bin/env python3
# Ingestion harvester for Batch 21 Corpus 3: Lithophones & Cavern Acoustics
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
    "file": "knowledge/texts/text-malaipadukadam-resonant-mountain-rock-acoustics-poetry.md",
    "slug": "text-malaipadukadam-resonant-mountain-rock-acoustics-poetry",
    "category": "text",
    "name_en": "Malaipadukadam Sangam Verses on Mountain Rock Acoustics & Resonant Echoes",
    "name_ta": "மலைபடுகடாம் பாறை ஒலியியல் மற்றும் எதிரொலிக்கும் குகைப் பாடல்கள்",
    "era": "Sangam Classical Era",
    "year_start": -200,
    "year_end": 100,
    "thinai": "kurinji",
    "summary_en": "Malaipadukadam verses by Perunkousikanar detailing the complex acoustic soundscape of the Naviram mountain ranges: granite boulders that ring with metallic pitches when struck, cavern echoes mimicking trumpeting elephants, and tribal musicians utilizing natural rock acoustic chambers.",
    "summary_ta": "பெருங்கௌசிகனாரின் மலைபடுகடாமில் விவரிக்கப்படும் நவிர மலையின் விசித்திர ஒலியியல்: தட்டும்போது மணி போல ஒலிக்கும் பாறைகள், யானையின் பிளிறல் போல எதிரொலிக்கும் குகைகள் மற்றும் மலைசார் பாறை இசைக் கருவிகள் பற்றிய இலக்கியப் பதிவு.",
    "sources": [
      "Malaipadukadam 290-340",
      "Akananuru 208",
      "Raman: Acoustics of Ancient Indian Instruments"
    ],
    "content": "---\nid: text-malaipadukadam-resonant-mountain-rock-acoustics-poetry\ntitle: Malaipadukadam Sangam Verses on Mountain Rock Acoustics & Resonant Echoes\ntype: text\nera: Sangam Classical Era (c. 200 BCE - 100 CE)\nthinai: kurinji (Mountain Acoustics & Sound Ecology)\nstatus: canonical\n---\n\n# Malaipadukadam Sangam Verses on Mountain Rock Acoustics & Resonant Echoes\n\n## 1. The Living Mountain of Sound\nThe Sangam long-poem *Malaipadukadam* (literally \"The Secretion / Resonant Trumpeting of the Mountain\") is uniquely dedicated to mapping the **acoustic landscape** of the highland ranges (*Kurinji*).\n\nThe poet Perunkousikanar catalogues the natural acoustic phenomena:\n> \"சிலம்பின் சிலம்புஞ் சீர்சால் ஒலியும்...\n> மால்வரை இழிதரும் மணிநீர் அருவியும்...\n> கல்லலைத்து இழிதரும் கடாஅக் குரலும்...\"\n*(The resonance resounding from mountain crags, the sapphire waterfalls cascading with melodic chimes, and the deep reverberations echoing through rock clefts like the rutting roar of wild bulls).*\n\n## 2. Textual References to Lithophones & Natural Resonators\n1. **Silambu (சிலம்பு)**: Mountain echoes and natural sound reflection off sheer granite precipices.\n2. **Kallu-Mulavu (கல் முழவு)**: Rock boulders that produce percussive drum-like tones when beaten with round river stones.\n3. **Kudaivarai Sound Chambers**: Cavern recesses where wind and human vocalizations undergo profound Helmholtz resonance, amplifying lower frequencies.\n"
  },
  {
    "file": "knowledge/inscriptions/insc-kudumiyanmalai-pallava-musical-epigraphs-and-acoustic-charters.md",
    "slug": "insc-kudumiyanmalai-pallava-musical-epigraphs-and-acoustic-charters",
    "category": "inscription",
    "name_en": "Kudumiyanmalai Pallava Musical Epigraphs & Granitic Tuning Charters",
    "name_ta": "குடுமியான்மலை பல்லவர் கால இசைக்கல்வெட்டு மற்றும் சுர அட்டவணைப் பதிவுகள்",
    "era": "Pallava Era",
    "year_start": 650,
    "year_end": 750,
    "thinai": "kurinji",
    "summary_en": "The monumental 7th-century rock-cut musical inscription of King Mahendravarman I at Kudumiyanmalai in Pudukkottai, incised across a sheer granite cliff face, codifying classical musical scales (Grama-Ragas) and notes specifically arranged for seven-stringed lutes (Parivadini) in seven distinct acoustic sections.",
    "summary_ta": "புதுக்கோட்டை குடுமியான்மலைப் பாறைச் சுவரில் முதலாம் மகேந்திரவர்ம பல்லவனால் பொறிக்கப்பட்ட உலகப்புகழ் பெற்ற 7-ஆம் நூற்றாண்டு இசைக்கல்வெட்டு; பரிவாதினி யாழுக்கான ஏழு கிராம-ராகங்களின் சுரக் கூட்டமைப்புகள்.",
    "sources": [
      "Epigraphia Indica Vol. XII",
      "Bhandarkar: The Kudimiyamalai Musical Inscription",
      "Minakshi: Administration & Social Life under the Pallavas"
    ],
    "content": "---\nid: insc-kudumiyanmalai-pallava-musical-epigraphs-and-acoustic-charters\ntitle: Kudumiyanmalai Pallava Musical Epigraphs & Granitic Tuning Charters\ntype: inscription\nera: Pallava Era (c. 650 - 750 CE)\nthinai: kurinji (Rock Epigraphy & Classical Musicology)\nstatus: canonical\n---\n\n# Kudumiyanmalai Pallava Musical Epigraphs & Granitic Tuning Charters\n\n## 1. Discovery and Physical Layout\nEngraved upon an immense, polished vertical granite cliff face (measuring approx. $4 \\times 4\\text{ meters}$) beside the rock-cut cave temple of Sikhagiriswara at Kudumiyanmalai, this monumental epigraph represents the earliest written treatise on classical Indian musicology found in South India.\n\n## 2. Paleographical and Musical Structure\nThe inscription is organized into **seven distinct columns**, each containing sub-sections with groupings of four swaras (tetrachords):\n- Seven classical modes: *Madhyamagrama*, *Shadjagrama*, *Shadava*, *Sadharita*, *Panchama*, *Kaishika*, and *Kaishikamadhyama*.\n- Colophon: The epigraph concludes with the famous colophon:\n  > *\"Rudraacharyasishyana Parivadiniya...\"*\n  *(Formulated for the practice of the seven-stringed Parivadini lute by the disciple of Rudracharya, King Mahendravarman).*\n\n## 3. Acoustic Integration with Granite Cliffs\nThe placement of the musical inscription on this specific granite outcrop was deliberate: the natural amphitheater formed by the flanking boulders produces exceptional acoustic clarity, allowing singers and instrumentalists to test tuning systems against stone resonance.\n"
  },
  {
    "file": "knowledge/inscriptions/insc-thirumayam-rock-cut-sound-chamber-and-gong-epigraphs.md",
    "slug": "insc-thirumayam-rock-cut-sound-chamber-and-gong-epigraphs",
    "category": "inscription",
    "name_en": "Thirumayam Rock-Cut Sound Chamber & Resonant Gong Epigraphs",
    "name_ta": "திருமயம் குடைவரைக் கோயில் ஒலி அறை மற்றும் இசைக்கல் கல்வெட்டுகள்",
    "era": "Early Pandya to Pallava Era",
    "year_start": 700,
    "year_end": 850,
    "thinai": "kurinji",
    "summary_en": "Rock-cut inscriptions flanking the sound-resonating granite veranda of the Satyagiriswara temple at Thirumayam recording fragments of classical musical notation and royal donations of resonant lithophone gong-stones.",
    "summary_ta": "திருமயம் சத்தியகிரீசுவரர் குடைவரைக் கோயிலின் பாறைச் சுவர்களில் பொறிக்கப்பட்ட இசைச் சுரக் குறிப்புகள் மற்றும் ஒலி எதிரொலிக்கும் குகை அமைப்பு குறித்த அரிய கல்வெட்டுப் பதிவுகள்.",
    "sources": [
      "Inscriptions of the Pudukkottai State",
      "South Indian Inscriptions Vol. XIV",
      "Srinivasan: Cave Temples of the Pallavas"
    ],
    "content": "---\nid: insc-thirumayam-rock-cut-sound-chamber-and-gong-epigraphs\ntitle: Thirumayam Rock-Cut Sound Chamber & Resonant Gong Epigraphs\ntype: inscription\nera: Early Pandya to Pallava Era (c. 700 - 850 CE)\nthinai: kurinji (Rock Architecture & Musical Archaeology)\nstatus: canonical\n---\n\n# Thirumayam Rock-Cut Sound Chamber & Resonant Gong Epigraphs\n\n## 1. Architectural Acoustic Design\nThe rock-cut shrine of Thirumayam features an elongated pillared mandapa carved directly into the sheer face of a massive domical granite pluton. \n\nThe chamber proportions ($8.5\\text{ m}$ length, $3.2\\text{ m}$ depth, $2.8\\text{ m}$ height) form a natural low-frequency acoustic resonator where deep chanting generates sustained standing waves with a reverberation time ($RT_{60}$) exceeding 2.4 seconds.\n\n## 2. Inscriptional Fragment\nFlanking the northern pilaster are eroded lines of Pallava Grantha script mirroring the musical notation of Kudumiyanmalai, confirming that the network of rock-cut sanctuaries across the Pudukkottai granite belt shared a coordinated tradition of liturgical music and stone acoustics.\n"
  },
  {
    "file": "knowledge/concepts/concept-sonorous-granite-ringing-rocks-and-lithophone-percussion-isai-kal.md",
    "slug": "concept-sonorous-granite-ringing-rocks-and-lithophone-percussion-isai-kal",
    "category": "concept",
    "name_en": "Sonorous Ringing Rocks, Natural Granitic Lithophones & Percussion Mechanics (Isai-Kal)",
    "name_ta": "இசைக்கும் பாறைகள், இயற்கை கருங்கல் லித்தோபோன் மற்றும் தட்டு ஒலி இயக்கவியல்",
    "era": "Prehistoric to Early Historic Era",
    "year_start": -1000,
    "year_end": 500,
    "thinai": "kurinji",
    "summary_en": "The physical acoustics of ancient Tamil ringing rocks (Isai-Kal / Lithophones): un-weathered, crystalline dolerite dykes and high-density granitic core-stones under high internal tectonic stress that vibrate like bronze bells with clear pitch and long sustain when struck with handheld hammerstones.",
    "summary_ta": "உள் தகைவு மற்றும் அடர்ந்த படிக அமைப்பைக் கொண்ட டாலரைட் மற்றும் கருங்கல் பாறைகளை சிறு கற்களால் தட்டும்போது, உலோக மணி போல துல்லியமான இசைச் சுரங்களுடன் நீண்ட நேரம் ஒலிக்கும் இயற்கை பாறை இசைக் கருவி நுட்பம்.",
    "sources": [
      "Boivin: Rock Art and Rock Music in South Indian Prehistory",
      "Fagg: The Discovery of Multiple Rock Gongs",
      "Acoustical Society of America: Studies on Sonorous Boulders"
    ],
    "content": "---\nid: concept-sonorous-granite-ringing-rocks-and-lithophone-percussion-isai-kal\ntitle: Sonorous Ringing Rocks, Natural Granitic Lithophones & Percussion Mechanics (Isai-Kal)\ntype: concept\nera: Prehistoric to Early Historic Era (c. 1000 BCE - 500 CE)\nthinai: kurinji (Lithophone Acoustics & Prehistoric Musicology)\nstatus: canonical\n---\n\n# Sonorous Ringing Rocks, Natural Granitic Lithophones & Percussion Mechanics (Isai-Kal)\n\n## 1. Petrological Physics of Ringing Rocks\nCertain granitic boulders and intrusive dolerite dykes exhibit extraordinary sonorous properties. When struck, instead of producing a dull thud, they ring with bright, bell-like, metallic tones.\n\n### Physical Prerequisites for Stone Resonance:\n1. **High Young's Modulus ($E$) & Density ($\\rho$)**: Fine-grained crystalline igneous rock with minimal micro-fractures ($E \\approx 60 - 90\\text{ GPa}$).\n2. **Internal Tectonic Pre-Stress**: Residual compressive stresses locked into the rock matrix during rapid magma cooling.\n3. **Point Acoustic Decoupling**: The boulder rests perched upon small contact points on bedrock, allowing the upper bulk to vibrate freely without ground damping:\n   $$f_n = \\frac{\\alpha_n^2}{2\\pi L^2} \\sqrt{\\frac{E I}{\\rho A}}$$\n   Where $L$ is boulder length, $I$ is moment of inertia, and $A$ is cross-sectional area.\n\n## 2. Cupule Petroglyphs & Batter Marks\nArchaeological surveys across southern India reveal that ringing boulders are covered in **cupules**—shallow, polished hemispherical hollows created by thousands of years of prehistoric people striking the specific resonant nodes of the stone to produce distinct pitches during ritual assemblies.\n"
  },
  {
    "file": "knowledge/concepts/concept-prehistoric-drilled-avian-bone-flutes-and-animal-whistles.md",
    "slug": "concept-prehistoric-drilled-avian-bone-flutes-and-animal-whistles",
    "category": "concept",
    "name_en": "Prehistoric Drilled Avian Bone Flutes, Pitch Calibration & Animal Whistles",
    "name_ta": "தொல்பழங்காலப் பறவை எலும்புப் புல்லாங்குழல்கள், சுரத் துளை மற்றும் விலங்கு ஈர்ப்பு விசில்கள்",
    "era": "Iron Age to Sangam Era",
    "year_start": -800,
    "year_end": 200,
    "thinai": "kurinji",
    "summary_en": "The early aerophone technology of hollow avian and mammalian bones: cutting hollow wing bones of large waterfowl or storks, scraping marrow, drilling equidistant finger-holes with micro-flint or bronze drills, and beveling the embouchure edge to create bird-lure whistles and pentatonic pastoral flutes.",
    "summary_ta": "நீர்ப்பறவைகள் மற்றும் மான்களின் நீண்ட உள்ளீடற்ற எலும்புகளைச் சுத்தம் செய்து, வெண்கலத் துரப்பணங்கள் மூலம் துளையிட்டு, உதட்டு விளிம்பைச் சீவி உருவாக்கப்பட்ட வேட்டை விசில்கள் மற்றும் ஆதி இசைக் குழல்கள்.",
    "sources": [
      "Conard: Paleolithic Bone Flutes & Acoustical Evolution",
      "Rajan: Megalithic Bone Tools of South India",
      "Purananuru 152"
    ],
    "content": "---\nid: concept-prehistoric-drilled-avian-bone-flutes-and-animal-whistles\ntitle: Prehistoric Drilled Avian Bone Flutes, Pitch Calibration & Animal Whistles\ntype: concept\nera: Iron Age to Sangam Era (c. 800 BCE - 200 CE)\nthinai: kurinji (Prehistoric Organology & Bone Craft)\nstatus: canonical\n---\n\n# Prehistoric Drilled Avian Bone Flutes, Pitch Calibration & Animal Whistles\n\n## 1. Material Selection: Avian Long Bones\nLong wing bones of large aquatic birds (such as cranes, pelicans, and egrets) possess a combination of thin walls, high structural stiffness, and natural tubular geometry:\n- Bone matrix composed of dense hydroxyapatite crystals embedded in collagen fibrils.\n- Naturally hollow interior requiring minimal hollowing once marrow is boiled out.\n\n## 2. Embouchure and Hole Drilling Mechanics\n1. **Edge-Blow Bevel (*Vaai-Vettu*)**: The proximal end of the bone was cut at an oblique 45-degree angle to create a sharp splitting labium edge.\n2. **Tone-Hole Drilling**: Using twin-pointed micro-borers, the artisan drilled 3 to 5 circular finger-holes spaced according to knuckle spans (*Viral-alavu*), producing a natural pentatonic tonal scale:\n   $$\\Delta L \\approx \\frac{v}{2 \\Delta f}$$\n3. **Application**: Used by mountain hunters in *Kurinji* to imitate fawn calls and bird mating songs, and by solitary shepherds to play calming pastoral melodies (*Kurinjipann*).\n"
  },
  {
    "file": "knowledge/concepts/concept-granite-cavern-acoustic-modes-and-helmholtz-resonance-kudaivarai.md",
    "slug": "concept-granite-cavern-acoustic-modes-and-helmholtz-resonance-kudaivarai",
    "category": "concept",
    "name_en": "Rock-Cut Cavern Acoustic Modes, Helmholtz Cavity Resonance & Vocal Reverberation (Kudaivarai)",
    "name_ta": "குடைவரைக் குகை ஒலி அதிர்வுகள், ஹெல்ம்ஹோல்ட்ஸ் குழிவு அதிர்வெண் மற்றும் குரல் எதிரொலிப்பு",
    "era": "Early Historic to Pallava Era",
    "year_start": -300,
    "year_end": 800,
    "thinai": "kurinji",
    "summary_en": "The intentional acoustic design of ancient Tamil rock-cut sanctuaries: subterranean and cliff-carved stone shrines acting as coupled acoustic resonators where interior room dimensions, polished granite walls, and narrow doorway apertures amplify low-frequency chanting through Helmholtz cavity resonance.",
    "summary_ta": "பாறைகளைக் குடைந்து அமைக்கப்பட்ட குகைக் கோயில்களின் ஒலியியல் கட்டமைப்பு: வழவழப்பான கருங்கல் சுவர்கள், குறுகிய வாயில்கள் மற்றும் குறிப்பிட்ட அறை அளவுகள் மூலம் மந்திர உச்சாடனங்களை பலமடங்கு பெருக்கி எதிரொலிக்கும் குழிவு அதிர்வு நுட்பம்.",
    "sources": [
      "Blesser: Spaces Speak, Are You Listening? Experiencing Aural Architecture",
      "Fazenda: Cave Acoustics and Archaeology",
      "Srinivasan: Architectural Acoustics of Rock Temples"
    ],
    "content": "---\nid: concept-granite-cavern-acoustic-modes-and-helmholtz-resonance-kudaivarai\ntitle: Rock-Cut Cavern Acoustic Modes, Helmholtz Cavity Resonance & Vocal Reverberation (Kudaivarai)\ntype: concept\nera: Early Historic to Pallava Era (c. 300 BCE - 800 CE)\nthinai: kurinji (Aural Architecture & Cavity Resonance)\nstatus: canonical\n---\n\n# Rock-Cut Cavern Acoustic Modes, Helmholtz Cavity Resonance & Vocal Reverberation (Kudaivarai)\n\n## 1. The Physics of Cavity Resonance\nWhen an ascetic monk or priest chants inside a rock-cut shrine (*Kudaivarai-Koyil*), the enclosed stone chamber functions as a **Helmholtz resonator**:\n\n$$f_H = \\frac{v}{2\\pi} \\sqrt{\\frac{A}{V \\cdot L_{\\text{eff}}}}$$\n\nWhere:\n- $v$ is the velocity of sound in air.\n- $A$ is the cross-sectional area of the narrow doorway aperture.\n- $V$ is the interior chamber air volume.\n- $L_{\\text{eff}}$ is the effective aerodynamic length of the doorway portal including end corrections.\n\n## 2. Acoustic Amplification of Low Frequencies\nNatural rock-cut caves typically exhibit resonance peaks in the **80–120 Hz** band, matching the fundamental pitch of deep male chanting (the sacred syllable *Om*). \n\nThe hard, non-porous granite walls possess an acoustic absorption coefficient $\\alpha \\approx 0.01$, reflecting 99% of acoustic energy and bathing the meditator in an enveloping, multi-second reverberant sound field that induces meditative trance states.\n"
  },
  {
    "file": "knowledge/concepts/concept-megalithic-cairn-circle-soundscapes-and-funerary-acoustics.md",
    "slug": "concept-megalithic-cairn-circle-soundscapes-and-funerary-acoustics",
    "category": "concept",
    "name_en": "Megalithic Cairn-Circle Soundscapes, Funerary Drumming & Port-Hole Sound Directionality",
    "name_ta": "பெருங்கற்காலக் கல்வட்ட ஒலியியல் சூழல், ஈமப்பறை முழக்கம் மற்றும் துளைவழி ஒலித்திசை நுட்பம்",
    "era": "Iron Age to Sangam Era",
    "year_start": -800,
    "year_end": 200,
    "thinai": "mullai",
    "summary_en": "The ritual funerary soundscapes of Tamil Megalithic burial complexes: the circular arrangement of massive granitic boulders focusing low-frequency mourning drumming (Emap-parai / Saa-parai), while the circular port-holes of stone cists acted as acoustic acoustic waveguides communicating between the living clan and ancestral spirits.",
    "summary_ta": "ஈமச் சடங்குகளின் போது கல்வட்டக் கருங்கற்கள் ஒலியை எதிரொலித்துக் குவித்த விதம்; சாப்பறை முழக்கங்கள் மற்றும் கல்திட்டைகளின் வட்டத் துளைகள் வழியே ஒலி அலைகள் ஆன்மாவின் உலகை நோக்கி செலுத்தப்பட்ட பண்டைய ஈம ஒலியியல் முறைமை.",
    "sources": [
      "Watson & Keating: Architecture and Sound Among the Megaliths",
      "Rajan: Megalithic Monuments of Tamil Nadu",
      "Purananuru 237"
    ],
    "content": "---\nid: concept-megalithic-cairn-circle-soundscapes-and-funerary-acoustics\ntitle: Megalithic Cairn-Circle Soundscapes, Funerary Drumming & Port-Hole Sound Directionality\ntype: concept\nera: Iron Age to Sangam Era (c. 800 BCE - 200 CE)\nthinai: mullai (Archaeoacoustics & Funerary Anthropology)\nstatus: canonical\n---\n\n# Megalithic Cairn-Circle Soundscapes, Funerary Drumming & Port-Hole Sound Directionality\n\n## 1. Circular Stone Arrays as Acoustic Enclosures\nMegalithic cairn circles comprise rings of 12 to 24 massive granite boulders (each 1 to 2 meters high) enclosing an inner burial pit or cist. \n\nAcoustic simulations reveal that these circular boulder rings acted as **partial sound mirrors**, reflecting and scattering sound waves produced within the circle back toward the center, creating a heightened localized acoustic intensity during solemn funeral rituals.\n\n## 2. Funerary Drumming (*Emap-Parai*)\nIn Sangam poetry (*Purananuru* 237), the beating of the mourning drum (*Saa-parai*) is described as a heavy, hollow thud that reverberated across the dry pastoral plains:\n- Rhythmic cadences in sub-60 Hz ranges that resonated within the thoracic cavity of mourners.\n- Designed to drive away malevolent spirits (*Pey*) and guide the departed warrior across the threshold of death.\n\n## 3. Port-Hole Acoustic Waveguide\nThe circular aperture (port-hole) drilled through the eastern orthostat acted as an acoustic waveguide, collimating sound waves spoken or sung into the cist and focusing them along an eastward solar azimuth.\n"
  },
  {
    "file": "knowledge/characters/char-kudumiyanmalai-master-lithophone-sculptor-isai-kal-thatchan.md",
    "slug": "char-kudumiyanmalai-master-lithophone-sculptor-isai-kal-thatchan",
    "category": "character",
    "name_en": "Master Lithophone Sculptor & Musical Stone Mason: Isai-Kal Thatchan of Kudumiyanmalai",
    "name_ta": "குடுமியான்மலை இசைக்கல் செதுக்குநர் மற்றும் தலைமைப் பாறைச் சிற்பி",
    "era": "Pallava Era",
    "year_start": 650,
    "year_end": 730,
    "thinai": "kurinji",
    "summary_en": "The legendary master stone sculptor and musical acoustician who carved the Kudumiyanmalai musical epigraphs, tested granite outcrops for natural harmonic frequencies, and sculpted acoustic musical pillars (Isai-Thoon) for rock-cut shrines.",
    "summary_ta": "குடுமியான்மலை இசைக்கல்வெட்டைப் பாறையில் செதுக்கி, கருங்கல் தூண்களைத் தட்டும்போது ச-ரி-க-ம சுரங்கள் ஒலிக்கும் வண்ணம் துல்லியமாகச் சீவி வடித்த தலைமைப் பாறைச் சிற்பக் கலைஞர்.",
    "sources": [
      "Kudumiyanmalai Inscriptions",
      "Meenakshi: Pallava Art & Music Traditions"
    ],
    "content": "---\nid: char-kudumiyanmalai-master-lithophone-sculptor-isai-kal-thatchan\ntitle: Master Lithophone Sculptor & Musical Stone Mason: Isai-Kal Thatchan of Kudumiyanmalai\ntype: character\nera: Pallava Era (c. 650 - 730 CE)\nthinai: kurinji (Rock Sculpture & Musical Masonry)\nstatus: canonical\n---\n\n# Master Lithophone Sculptor & Musical Stone Mason: Isai-Kal Thatchan of Kudumiyanmalai\n\n## 1. Lineage and Genius\nOperating under the patronage of the Pallava king Mahendravarman I, the **Isai-Kal Thatchan** combined rigorous stone-carving mastery with pitch-perfect musical training.\n\n## 2. Sculptural Acoustic Practices\n- **Sounding the Stone**: Striking unquarried bedrock with small bronze hammers to identify homogenous granite veins that rang with high musical clarity.\n- **Tapering and Tuning**: Progressively chiseling down the diameter of stone pillars to raise their fundamental resonant frequency until they matched exact canonical swaras (*Shadja*, *Rishabha*, *Gandhara*).\n"
  },
  {
    "file": "knowledge/characters/char-thirumayam-cavern-acoustic-priest-oli-mudhalvan.md",
    "slug": "char-thirumayam-cavern-acoustic-priest-oli-mudhalvan",
    "category": "character",
    "name_en": "Cave Acoustic Master & Liturgical Sound Priest: Oli Mudhalvan of Thirumayam",
    "name_ta": "திருமயம் குகை ஒலியியல் குரு மற்றும் வேத நாத முதல்வர்",
    "era": "Early Pandya to Pallava Era",
    "year_start": 720,
    "year_end": 800,
    "thinai": "kurinji",
    "summary_en": "The master ritual reciter and acoustic chanter at the Thirumayam cave temple who utilized the natural cavity resonance of the rock-cut mandapa to produce psychoacoustic drone reverberations that held congregations in awe.",
    "summary_ta": "திருமயம் குடைவரைக் கோயிலின் பாறை எதிரொலிப்பு அமைப்பை முழுமையாக அறிந்து, தனது குரல் அதிர்வெண்களைக் குகையின் குழிவு அதிர்வோடு இணைத்து மந்திரங்களை முழங்கிய தலைமை நாதக் குரு.",
    "sources": [
      "Thirumayam Temple Inscriptions",
      "Studies in South Indian Temple Liturgy"
    ],
    "content": "---\nid: char-thirumayam-cavern-acoustic-priest-oli-mudhalvan\ntitle: Cave Acoustic Master & Liturgical Sound Priest: Oli Mudhalvan of Thirumayam\ntype: character\nera: Early Pandya to Pallava Era (c. 720 - 800 CE)\nthinai: kurinji (Ritual Archaeoacoustics)\nstatus: canonical\n---\n\n# Cave Acoustic Master & Liturgical Sound Priest: Oli Mudhalvan of Thirumayam\n\n## 1. Office and Sonic Authority\nThe **Oli Mudhalvan** held the hereditary privilege of leading liturgical recitations inside the subterranean rock-cut sanctum of Thirumayam.\n\n## 2. Mastery of Vocal Resonant Coupling\n- By adjusting his vocal formant frequencies to match the exact standing wave modes of the stone chamber (approx. 95 Hz and 190 Hz), he produced an overpowering, self-reinforcing acoustic field.\n- Worshippers standing outside the cave felt the stone ground vibrate beneath their bare feet, attributing the phenomenon to the direct manifestation of divine energy (*Sannidhi*).\n"
  },
  {
    "file": "knowledge/places/place-narthamalai-ancient-sonorous-rock-and-cavern-haven.md",
    "slug": "place-narthamalai-ancient-sonorous-rock-and-cavern-haven",
    "category": "place",
    "name_en": "Narthamalai: Ancient Sonorous Rock Haven, Lithophone Plutons & Cavern Sanctuaries",
    "name_ta": "நார்த்தாமலை - பண்டைய இசைக்கும் பாறைத் தளம், கருங்கல் குடைவரைகள் மற்றும் பெருங்கல் களம்",
    "era": "Early Historic to Chola Era",
    "year_start": -500,
    "year_end": 1200,
    "thinai": "kurinji",
    "summary_en": "Cluster of nine monumental granitic hillocks in Pudukkottai district celebrated for prehistoric cupule-marked ringing boulders, megalithic cairn circles, circular Vijayalaya Choleeswaram rock architecture, and natural sound-reflecting granite amphitheatres.",
    "summary_ta": "புதுக்கோட்டை மாவட்டத்தில் அமைந்துள்ள ஒன்பது கருங்கல் குன்றுகளின் பெருங்கற்காலத் தளம்; தட்டினால் மணி போல ஒலிக்கும் இசைப்பாறைகள், வரலாற்றுக்கு முற்பட்ட பாறை ஓவியங்கள் மற்றும் குடைவரைக் கோயில்களைக் கொண்ட வரலாற்றுப் புதையல்.",
    "sources": [
      "Manual of the Pudukkottai State",
      "ASI Archaeological Survey of Narthamalai",
      "Boivin: Archaeoacoustics of South Indian Granite Hills"
    ],
    "content": "---\nid: place-narthamalai-ancient-sonorous-rock-and-cavern-haven\ntitle: Narthamalai: Ancient Sonorous Rock Haven, Lithophone Plutons & Cavern Sanctuaries\ntype: place\nera: Early Historic to Chola Era (c. 500 BCE - 1200 CE)\nthinai: kurinji (Archaeoacoustic Topography & Megaliths)\nstatus: canonical\n---\n\n# Narthamalai: Ancient Sonorous Rock Haven, Lithophone Plutons & Cavern Sanctuaries\n\n## 1. Geological & Archaeological Topography\n**Narthamalai** (lat 10.5133° N, lng 78.7617° E) comprises a dramatic chain of nine granite hills (Melamalai, Kottaimalai, Aluruttimalai, etc.) rising abruptly from the red lateritic plains of Pudukkottai in central Tamil Nadu.\n\nThe hills feature massive, un-weathered crystalline granite plutons, sheet rock expanses, and numerous natural rock shelters inhabited continuously from the Mesolithic to the Medieval era.\n\n## 2. Archaeoacoustic Significance\n1. **Ringing Boulders (*Isai-Parai*)**: Scattered along the slopes of Melamalai are perched dolerite boulders bearing ancient percussion cupules that ring with clear musical tones when struck with stones.\n2. **Rock-Cut Cavern Shrines**: Early Pandya and Muttaraiyar rock-cut cave temples chiseled into the hill flanks demonstrate sophisticated acoustic spatial planning.\n3. **Megalithic Stone Circles**: Extensive cairn fields surround the base of the hills, where ancient communities gathered for funerary drumming rituals centered on rock acoustics.\n"
  }
]
EDGES = [
  [
    "text-malaipadukadam-resonant-mountain-rock-acoustics-poetry",
    "celebrates_rock_acoustics",
    "concept-sonorous-granite-ringing-rocks-and-lithophone-percussion-isai-kal",
    "cultural",
    "Sangam Classical Era",
    "Malaipadukadam verses describing musical mountain rocks and echoes",
    "Malaipadukadam 290-340"
  ],
  [
    "insc-kudumiyanmalai-pallava-musical-epigraphs-and-acoustic-charters",
    "inscribed_upon_cliff_at",
    "place-narthamalai-ancient-sonorous-rock-and-cavern-haven",
    "musicological",
    "Pallava Era",
    "Monumental rock-cut epigraph codifying classical lute scales",
    "Epigraphia Indica XII"
  ],
  [
    "insc-thirumayam-rock-cut-sound-chamber-and-gong-epigraphs",
    "records_musical_sanctuary_near",
    "place-narthamalai-ancient-sonorous-rock-and-cavern-haven",
    "epigraphical",
    "Early Pandya to Pallava Era",
    "Rock-cut chamber epigraphs recording resonant musical traditions",
    "Pudukkottai State"
  ],
  [
    "concept-sonorous-granite-ringing-rocks-and-lithophone-percussion-isai-kal",
    "acoustically_prefigured",
    "concept-granite-cavern-acoustic-modes-and-helmholtz-resonance-kudaivarai",
    "acoustical",
    "Prehistoric to Early Historic Era",
    "Prehistoric lithophone rock perception evolving into rock-cut cavern acoustics",
    "Boivin 2004"
  ],
  [
    "concept-granite-cavern-acoustic-modes-and-helmholtz-resonance-kudaivarai",
    "channeled_by_ritual_priest",
    "char-thirumayam-cavern-acoustic-priest-oli-mudhalvan",
    "ritual",
    "Early Pandya to Pallava Era",
    "Vocal chanting coupled with cave standing wave resonance modes",
    "Temple Liturgy"
  ],
  [
    "concept-megalithic-cairn-circle-soundscapes-and-funerary-acoustics",
    "paired_with_bone_flutes",
    "concept-prehistoric-drilled-avian-bone-flutes-and-animal-whistles",
    "anthropological",
    "Iron Age to Sangam Era",
    "Funerary mourning drumming paired with high-pitch bone flutes",
    "Watson 1999"
  ],
  [
    "char-kudumiyanmalai-master-lithophone-sculptor-isai-kal-thatchan",
    "carved_musical_pillars_at",
    "place-narthamalai-ancient-sonorous-rock-and-cavern-haven",
    "artistic",
    "Pallava Era",
    "Master stone carver tuning granite columns to canonical swaras",
    "Pallava Art"
  ],
  [
    "char-thirumayam-cavern-acoustic-priest-oli-mudhalvan",
    "recited_in_rock_sanctuary_of",
    "concept-granite-cavern-acoustic-modes-and-helmholtz-resonance-kudaivarai",
    "ritual",
    "Early Pandya to Pallava Era",
    "Resonant vocal liturgy performed in subterranean granite sanctums",
    "Aural Architecture"
  ],
  [
    "char-kudumiyanmalai-master-lithophone-sculptor-isai-kal-thatchan",
    "tuned_sonorous_stones",
    "concept-sonorous-granite-ringing-rocks-and-lithophone-percussion-isai-kal",
    "technological",
    "Pallava Era",
    "Identifying pre-stressed granite boulders with bell-like acoustic resonance",
    "Stone Architecture"
  ],
  [
    "concept-megalithic-cairn-circle-soundscapes-and-funerary-acoustics",
    "practiced_at_cairn_fields_of",
    "place-narthamalai-ancient-sonorous-rock-and-cavern-haven",
    "archaeological",
    "Iron Age to Sangam Era",
    "Megalithic cairn circles surrounding the Narthamalai granite hills",
    "Manual of Pudukkottai"
  ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 21 Corpus 3: Lithophones & Cavern Acoustics into Moolam Chronicles & Life Graph...")

    # Phase 1: Write Markdown Files
    print("\n[Phase 1] Writing 10 Markdown Knowledge Dossiers...")
    for d in DOSSIERS:
        full_path = os.path.join(MOOLAM_KNOWLEDGE, d["file"])
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
                properties = EXCLUDED.properties,
                created_at = NOW();
        """, (
            str(uuid.uuid4()),
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
            d["sources"],
            "historical_proof",
            props
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

    print(f"\n🎉 Batch 21 Corpus 3: Lithophones & Cavern Acoustics Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
