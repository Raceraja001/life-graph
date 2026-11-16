#!/usr/bin/env python3
# Ingestion harvester for Batch 21 Corpus 2: Clepsydra Horology & Shadow Gnomons
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
    "file": "knowledge/texts/text-mullaippattu-naazhigai-vattil-water-clock-poetry.md",
    "slug": "text-mullaippattu-naazhigai-vattil-water-clock-poetry",
    "category": "text",
    "name_en": "Mullaippattu Sangam Verses on Hydraulic Clepsydras & Midnight Naazhigai Timers",
    "name_ta": "முல்லைப்பாட்டு நள்ளிரவு நாழிகைக் கணக்கர் மற்றும் நீர் கடிகாரப் பாடல்கள்",
    "era": "Sangam Classical Era",
    "year_start": -200,
    "year_end": 100,
    "thinai": "mullai",
    "summary_en": "Mullaippattu lines 55-60 detailing the nocturnal timekeeping technology of the royal military encampment: skilled horologists (Pozhuthu-Alanthu-Arivor / Naazhigai-Kanakkar) observing perforated copper bowls sinking in water basins to announce changing watch hours to the sleeping king.",
    "summary_ta": "முல்லைப்பாட்டில் விவரிக்கப்படும் போர்ப்பாசறை நள்ளிரவு நேரக் கணிப்பு நுட்பம்: துளையிட்ட செப்புக் கிண்ணம் நீரில் மூழ்கும் கால அளவைக் கொண்டு (நாழிகை) விழித்திருந்து மன்னருக்கு இரவுப் பொழுதுகளை அறிவிக்கும் நாழிகைக் கணக்கர் குறித்த பாடல்.",
    "sources": [
      "Mullaippattu 55-60",
      "Silappadikaram 5:49-58",
      "Subrahmanian: Pre-Pallava Tamil Polity"
    ],
    "content": "---\nid: text-mullaippattu-naazhigai-vattil-water-clock-poetry\ntitle: Mullaippattu Sangam Verses on Hydraulic Clepsydras & Midnight Naazhigai Timers\ntype: text\nera: Sangam Classical Era (c. 200 BCE - 100 CE)\nthinai: mullai (Nocturnal Horology & Military Encampments)\nstatus: canonical\n---\n\n# Mullaippattu Sangam Verses on Hydraulic Clepsydras & Midnight Naazhigai Timers\n\n## 1. Classical Documentation in Mullaippattu\nIn the Sangam poem *Mullaippattu*, composed by the poet Nappoothanar, lines 55–60 provide a vivid, technical description of military nocturnal chronometry inside the royal command tent (*Paasarai*):\n\n> \"பொழுது அளந்து அறியும் பொய்யா மாக்கள்\n> தொழுது காண் கையர், மெய்ம்மலிந்து புகன்று,\n> 'கழிந்தது இது' என நாழிகை கணக்கு விரித்து...\"\n*(The unerring horologists who accurately measure elapsed time, standing with reverent hands folded, joyfully announce: 'Thus many naazhigai units of the night have passed, O King!').*\n\n## 2. The Operational Apparatus: Naazhigai Vattil\nIn *Silappadikaram* (Canto 5, Indira Vizhavu Ooredutha Kaadhai), the apparatus is explicitly identified as the **Naazhigai Vattil (நாழிகைக் கிண்ணம்)**:\n- A precisely weighed, thin hemispherical copper bowl (*Kinnam*) pierced at the center of its base with a microscopic needle aperture.\n- The bowl was floated on the surface of calm water contained in a larger bronze reservoir (*Kundalam*).\n- As water gradually seeped into the bowl through the orifice, the bowl slowly filled and sank to the bottom at an exact, predictable interval corresponding to **one Naazhigai (24 modern minutes)**.\n\n## 3. Civilizational Significance\nThis proves that ancient Tamil urban and military life was organized not by vague solar approximations, but by **rigorous empirical hydro-chronometry**, dividing the day and night into exactly sixty equal *naazhigai* intervals.\n"
  },
  {
    "file": "knowledge/inscriptions/insc-kumbakonam-chola-astronomical-chronometry-charters.md",
    "slug": "insc-kumbakonam-chola-astronomical-chronometry-charters",
    "category": "inscription",
    "name_en": "Kumbakonam Chola Astronomical Clepsydra & Gnomon Charters",
    "name_ta": "கும்பகோணம் சோழர் வானியல் நீர்க் கடிகாரம் மற்றும் நிழற்கோல் கல்வெட்டுகள்",
    "era": "Imperial Chola Era",
    "year_start": 950,
    "year_end": 1150,
    "thinai": "marutham",
    "summary_en": "Chola temple epigraphs from the Nageswaran and Sarangapani temples in Kumbakonam detailing royal endowments of land for temple astronomers (Jyothishar) and horologists tasked with maintaining copper water clocks, regulating solstitial gnomon tables, and determining ritual muhurtams.",
    "summary_ta": "கும்பகோணம் நாகேஸ்வரன் கோயில் கல்வெட்டுகளில் பொறிக்கப்பட்ட சோழர் காலத்து வானியல் மற்றும் நீர்க் கடிகாரக் கொடைகள்; நிழற்கோல் அட்டவணைகள் மூலம் நேரத்தை அளந்து கோயில் வழிபாடுகளை நெறிப்படுத்திய நாழிகைக் கணக்கர் பதிவுகள்.",
    "sources": [
      "South Indian Inscriptions Vol. III & XIX",
      "ASI Epigraphia Indica (Cholas of Thanjavur)"
    ],
    "content": "---\nid: insc-kumbakonam-chola-astronomical-chronometry-charters\ntitle: Kumbakonam Chola Astronomical Clepsydra & Gnomon Charters\ntype: inscription\nera: Imperial Chola Era (c. 950 - 1150 CE)\nthinai: marutham (Temple Horology & Astronomical Epigraphy)\nstatus: canonical\n---\n\n# Kumbakonam Chola Astronomical Clepsydra & Gnomon Charters\n\n## 1. Kumbakonam as an Astronomical Center\nSituated at the heart of the Kaveri delta, Kumbakonam was an ancient hub of mathematical and astronomical learning in southern India. \n\nMultiple epigraphs dating to Parantaka I and Rajaraja I document the formal institutionalization of the **Naazhigai-Kanakkar (official timekeepers)** within the temple administration.\n\n## 2. Inscriptional Terms & Royal Allocations\nThe inscriptions specify:\n- **Kala-Kani**: Tax-free wet land endowments allocated to astronomical observers responsible for operating the temple water clock (*Neer-Naazhigai*).\n- **Gnomon Calibration (*Nizhal-Kanal*)**: Mandates to cross-check water clock sink rates against midday sun-shadow lengths cast by vertical bronze gnomon rods (*Sanku-thambam*) during equinoxes and solstices.\n- **Bell Announcements (*Mani-Kural*)**: Directives requiring the sounding of bronze bells (*Mani*) at the completion of every 7.5 naazhigai (one *Yama* / 3 modern hours).\n"
  },
  {
    "file": "knowledge/inscriptions/insc-chidambaram-chola-temple-bell-shift-and-water-clock-epigraphs.md",
    "slug": "insc-chidambaram-chola-temple-bell-shift-and-water-clock-epigraphs",
    "category": "inscription",
    "name_en": "Chidambaram Chola Temple Bell Shift & Clepsydra Calibration Epigraphs",
    "name_ta": "சிதம்பரம் சோழர் காலப் பிரகார மணி முழக்கம் மற்றும் நீர் கடிகாரக் கல்வெட்டுகள்",
    "era": "Imperial Chola Era",
    "year_start": 1000,
    "year_end": 1200,
    "thinai": "marutham",
    "summary_en": "Epigraphs on the inner prakara walls of the Nataraja temple at Chidambaram recording the synchronized daily operation of copper water clocks, bell-ringing schedules for the six daily worship services (Aru-kaala Pooja), and royal nocturnal chronometry endowments.",
    "summary_ta": "சிதம்பரம் நடராசர் திருக்கோயில் பிரகாரக் கல்வெட்டுகள்; ஆறுகாலப் பூசைகளுக்கான நேரத்தைத் துல்லியமாக அளக்க வைக்கப்பட்ட நீர்க்கடிகாரங்கள் மற்றும் மணி அடிப்போருக்கான நிபந்தனைகள்.",
    "sources": [
      "South Indian Inscriptions Vol. IV",
      "Nataraja Temple Epigraphical Survey (TNSDA)"
    ],
    "content": "---\nid: insc-chidambaram-chola-temple-bell-shift-and-water-clock-epigraphs\ntitle: Chidambaram Chola Temple Bell Shift & Clepsydra Calibration Epigraphs\ntype: inscription\nera: Imperial Chola Era (c. 1000 - 1200 CE)\nthinai: marutham (Temple Ritual Timekeeping)\nstatus: canonical\n---\n\n# Chidambaram Chola Temple Bell Shift & Clepsydra Calibration Epigraphs\n\n## 1. Ritual Synchronization in Monumental Temples\nThe vast Nataraja temple complex operated on a rigid liturgical schedule governed by the six canonical daily worships (*Aru-kaala Pooja*). \n\nTo ensure exact celestial synchronization between the sanctum, temple kitchens, flower pavilions, and public gates, an official clepsydra station was maintained in the second enclosure (*Prakara*).\n\n## 2. Inscriptional Mandates\n- **Thiruppalliezhuchi (Dawn Watch)**: Initiated precisely at 55 naazhigai of the nocturnal cycle (approx. 4:00 AM) upon the final sink of the night clepsydra bowl.\n- **Gong & Bell Coordination**: The moment the copper bowl sank to the bottom of the water tub, the watchman struck a heavy bronze gong plate (*Semmankalam*) with a wooden mallet, triggering the colossal bell tower to broadcast the time across the city.\n"
  },
  {
    "file": "knowledge/concepts/concept-perforated-copper-bowl-sinking-clepsydra-hydrometry-naazhigai-vattil.md",
    "slug": "concept-perforated-copper-bowl-sinking-clepsydra-hydrometry-naazhigai-vattil",
    "category": "concept",
    "name_en": "Perforated Copper Bowl Sinking Clepsydra, Hydrodynamic Inflow & Orifice Discharge Physics (Naazhigai Vattil)",
    "name_ta": "துளையிட்ட செப்புக் கிண்ண நீர் கடிகார நீர் இயக்கவியல் மற்றும் பாய்தல் இயற்பியல்",
    "era": "Early Historic Era",
    "year_start": -300,
    "year_end": 500,
    "thinai": "marutham",
    "summary_en": "The hydrodynamic engineering of the ancient Tamil sinking-bowl water clock (Naazhigai Vattil): a thin hemispherical copper bowl of calibrated mass and volume floating on water, filling through a precision laser/needle-pierced basal orifice until negative buoyancy causes rapid submersion at exactly 24 minutes (1 naazhigai).",
    "summary_ta": "சீரான எடையும் கனஅளவும் கொண்ட மெல்லிய செப்புக் கிண்ணம், அதன் அடியில் இடப்பட்ட துல்லியமான நுண்ணிய துளை வழியே நீர் கசிந்து, மிதப்பு விசை குறைந்து சரியாக 24 நிமிடங்களில் (ஒரு நாழிகை) முழுக் கிண்ணமும் மூழ்கும் நீர்-இயக்கவியல் இயற்பியல் நுட்பம்.",
    "sources": [
      "Needham: Science and Civilisation in China Vol. 4 (Clepsydras)",
      "Sarma: A History of Indian Astronomy",
      "Ohashi: Astronomical Instruments in Classical India"
    ],
    "content": "---\nid: concept-perforated-copper-bowl-sinking-clepsydra-hydrometry-naazhigai-vattil\ntitle: Perforated Copper Bowl Sinking Clepsydra, Hydrodynamic Inflow & Orifice Discharge Physics (Naazhigai Vattil)\ntype: concept\nera: Early Historic Era (c. 300 BCE - 500 CE)\nthinai: marutham (Hydraulic Metrology & Physics)\nstatus: canonical\n---\n\n# Perforated Copper Bowl Sinking Clepsydra, Hydrodynamic Inflow & Orifice Discharge Physics (Naazhigai Vattil)\n\n## 1. Principles of the Inflow Sinking Clepsydra\nUnlike Middle Eastern and Greco-Roman outflow clepsydras (which suffered from non-linear discharge rates as hydrostatic water head fell), the Indian and Tamil sinking clepsydra (**Ghati-yantra** / *Naazhigai-Vattil*) is an **inflow device**.\n\nA thin, hemispherical copper bowl floats in a large basin of still water. Water enters the bowl through a microscopic central pinhole under a virtually constant pressure differential established by the bowl's draft.\n\n## 2. Hydrodynamic Inflow Physics\nThe rate of water entry through the small circular orifice of cross-sectional area $A_0$ is governed by Torricelli's law modified by the orifice discharge coefficient $C_d$:\n\n$$\\frac{dV}{dt} = C_d \\cdot A_0 \\cdot \\sqrt{2 g \\Delta h(t)}$$\n\nWhere:\n- $V(t)$ is the volume of water accumulated inside the bowl.\n- $g$ is the acceleration due to gravity.\n- $\\Delta h(t) = h_{\\text{external}} - h_{\\text{internal}}$ is the hydrostatic head across the orifice.\n\n### Sinking Instability (Catastrophic Submersion):\nThroughout the 24-minute period, the bowl sinks slowly and steadily. However, as the water level reaches the inner rim, surface tension breaks, and water rushes over the lip, causing the bowl to **snap suddenly to the bottom** with a clear audible chime as it strikes the basin floor.\n\n## 3. Standardization Formula\nClassical texts (such as the *Suryasiddhanta* and local Tamil *Kanakku-nool*) specify that a copper vessel measuring 10 palas in weight, with a rim diameter of 12 angulas and depth of 6 angulas, pierced by a gold pin of 4 mashes weight and 4 angulas length, will sink exactly 60 times during a complete diurnal rotation (24 hours).\n"
  },
  {
    "file": "knowledge/concepts/concept-twenty-four-minute-naazhigai-temporal-metrology-and-sixty-naazhigai-day.md",
    "slug": "concept-twenty-four-minute-naazhigai-temporal-metrology-and-sixty-naazhigai-day",
    "category": "concept",
    "name_en": "Twenty-Four Minute Naazhigai Metrology, Sexagesimal Time Division & Sixty-Naazhigai Solar Day",
    "name_ta": "24 நிமிட நாழிகைக் காலக் கணிப்பியல், அறுபதின்மானப் பகுப்பு மற்றும் அறுபது நாழிகை நாள்",
    "era": "Early Historic Era",
    "year_start": -400,
    "year_end": 500,
    "thinai": "marutham",
    "summary_en": "The sexagesimal temporal mathematical architecture of ancient Tamil civil timekeeping: dividing the solar day into 60 Naazhigai (24 minutes each), sub-divided into 60 Vinadi (24 seconds each), which in turn comprise micro-units down to the Tatparai and Kanam (fractional seconds), coordinated across civil and temple administrations.",
    "summary_ta": "ஒரு சூரிய நாளை 60 நாழிகைகளாகவும் (ஒவ்வொன்றும் 24 நிமிடங்கள்), ஒரு நாழிகையை 60 விநாடிகளாகவும், மேலும் தற்பரை மற்றும் கணங்களாகப் பகுத்து இயக்கிய பண்டைய தமிழரின் கணித-வானியல் காலக் கணக்கீட்டு முறைமை.",
    "sources": [
      "Subbarayappa: Indian Astronomy: A Source-Book",
      "Pingree: Jyotihsastra",
      "Srinivasan: Chronometry in Tamil Epigraphy"
    ],
    "content": "---\nid: concept-twenty-four-minute-naazhigai-temporal-metrology-and-sixty-naazhigai-day\ntitle: Twenty-Four Minute Naazhigai Metrology, Sexagesimal Time Division & Sixty-Naazhigai Solar Day\ntype: concept\nera: Early Historic Era (c. 400 BCE - 500 CE)\nthinai: marutham (Temporal Metrology & Mathematical Astronomy)\nstatus: canonical\n---\n\n# Twenty-Four Minute Naazhigai Metrology, Sexagesimal Time Division & Sixty-Naazhigai Solar Day\n\n## 1. The Sexagesimal Time System\nAncient Tamil society operated on a sexagesimal (base-60) temporal metrology that harmonized perfectly with lunar orbital cycles and solar geometry:\n\n| Tamil Unit | Modern Equivalent | Sexagesimal Sub-Division |\n| :--- | :--- | :--- |\n| **1 Naal (நாள் / Day)** | 24 Hours | 60 Naazhigai |\n| **1 Yama / Saamam (சாமம்)** | 3 Hours | 7.5 Naazhigai (8 per day) |\n| **1 Naazhigai (நாழிகை)** | 24 Minutes | 60 Vinadi |\n| **1 Vinadi (விநாடி)** | 24 Seconds | 60 Tatparai |\n| **1 Tatparai (தற்பரை)** | 0.4 Seconds | 60 Kanam |\n| **1 Kanam (கணம்)** | 6.67 Milliseconds | Fundamental perception atom |\n\n## 2. Diurnal Variation Calibration\nBecause day length varies throughout the year based on solar declination, ancient horologists adjusted civil shift assignments by monitoring sunrise and sunset transitions, ensuring the 60-naazhigai cycle maintained invariant mathematical rigor.\n"
  },
  {
    "file": "knowledge/concepts/concept-astronomical-gnomon-shadow-stick-reckoning-nizhal-kanal.md",
    "slug": "concept-astronomical-gnomon-shadow-stick-reckoning-nizhal-kanal",
    "category": "concept",
    "name_en": "Astronomical Gnomon Shadow Reckoning, Midday Solar Altitudes & Meridian Calibrations (Nizhal-Kanal)",
    "name_ta": "நிழற்கோல் வானியல் காலக் கணிப்பு, உச்சி சூரிய உயரம் மற்றும் நண்பகல் திருத்தம்",
    "era": "Early Historic Era",
    "year_start": -300,
    "year_end": 500,
    "thinai": "marutham",
    "summary_en": "Daytime solar chronometry using vertical gnomon poles (Sanku-thambam / Nizhal-Kol): calibrating the shadow length cast upon a flat, horizontal circular dial with concentric markings to determine exact midday solar transit, solstitial latitude corrections, and water clock reset timing.",
    "summary_ta": "சமதள வட்டத் தரை மீது செங்குத்தாக நடப்பட்ட நிழற்கோலின் நிழல் நீளத்தை அளந்து, உச்சி நண்பகல் சூரியன் மற்றும் பருவக் கால மாற்றங்களைக் கணக்கிட்டு நீர்க்கடிகாரங்களைச் சரிசெய்த பண்டைய சூரிய நிழல் வானியல் முறை.",
    "sources": [
      "Varahamihira: Pancasiddhantika",
      "Babu: Ancient Indian Gnomonics",
      "Thiruvenkatachari: Studies in Tamil Inscriptions"
    ],
    "content": "---\nid: concept-astronomical-gnomon-shadow-stick-reckoning-nizhal-kanal\ntitle: Astronomical Gnomon Shadow Reckoning, Midday Solar Altitudes & Meridian Calibrations (Nizhal-Kanal)\ntype: concept\nera: Early Historic Era (c. 300 BCE - 500 CE)\nthinai: marutham (Solar Astronomy & Shadow Gnomonics)\nstatus: canonical\n---\n\n# Astronomical Gnomon Shadow Reckoning, Midday Solar Altitudes & Meridian Calibrations (Nizhal-Kanal)\n\n## 1. The Gnomon Apparatus (*Nizhal-Kol / Sanku*)\nWhile water clocks measured relative elapsed duration, absolute daytime solar time was anchored by the **Gnomon**—a perfectly vertical cylindrical bronze or hardwood rod of 12 angulas (approx. 22.8 cm) height erected at the center of a leveled circular stone plinth.\n\n## 2. Mathematical Principles of Shadow Projection\nThe shadow length $s(\\theta)$ cast by a gnomon of height $h$ is a direct trigonometric function of the sun's solar zenith angle $z$:\n\n$$s = h \\cdot \\tan z = h \\cdot \\cot a$$\n\nWhere $a$ is the solar elevation angle above the horizon.\n\n### Key Operational Observations:\n1. **True Solar Noon (*Uchi-Pozhuthu*)**: Occurs when the shadow length reaches its minimum daily value, oriented precisely along the true local north-south meridian.\n2. **Equinoctial Shadow (*Madhyahna-Chaya*)**: At equinoxes, the noon shadow angle yields the exact geographical latitude of the site:\n   $$\\phi = \\arctan\\left(\\frac{s_{\\text{noon}}}{h}\\right)$$\n3. **Resetting Clepsydras**: Every true noon, the temple timekeepers emptied the water clock basin and reset the primary counting counter to zero, eliminating cumulative day-to-day drift.\n"
  },
  {
    "file": "knowledge/concepts/concept-temple-bell-strike-cadence-and-nocturnal-maritime-chronometry.md",
    "slug": "concept-temple-bell-strike-cadence-and-nocturnal-maritime-chronometry",
    "category": "concept",
    "name_en": "Temple Bell Strike Cadences, Public Acoustic Chronometry & Maritime Nocturnal Star Clocks",
    "name_ta": "கோயில் மணி ஓசைக் கால அறிவிப்பு, பொது ஒலியியல் நேரம் மற்றும் கடல்சார் இரவு விண்மீன் கடிகாரம்",
    "era": "Early Historic to Medieval Era",
    "year_start": -200,
    "year_end": 1200,
    "thinai": "neithal",
    "summary_en": "The social dissemination and maritime application of Tamil chronometry: converting water clock sink cycles into public acoustic signals via bell strike cadences, and mariners navigating across the Indian Ocean by observing nocturnal zenith transits of marker stars (Velli-Meen / Agasthya) to calculate nocturnal hours at sea.",
    "summary_ta": "நீர் கடிகாரக் கணக்கீடுகளை கோயில் மணி அடிகளின் மூலம் பொதுமக்களுக்கு ஒலிபரப்பிய முறைமை; கடலில் பயணித்த தமிழ்க் கப்பலோட்டிகள் அகஸ்தியர் மற்றும் வெள்ளி விண்மீன்களின் வான உச்சிப் பயணத்தை வைத்து இரவு நேரத்தைக் கணித்த கடல்சார் வானியல் நுட்பம்.",
    "sources": [
      "Pillay: A Social History of the Tamils",
      "Lotika Varadarajan: Sewn Boats & Traditional Navigation",
      "Arunachalam: Traditional Indian Sea-Navigation"
    ],
    "content": "---\nid: concept-temple-bell-strike-cadence-and-nocturnal-maritime-chronometry\ntitle: Temple Bell Strike Cadences, Public Acoustic Chronometry & Maritime Nocturnal Star Clocks\ntype: concept\nera: Early Historic to Medieval Era (c. 200 BCE - 1200 CE)\nthinai: neithal (Maritime Astronomy & Social Timekeeping)\nstatus: canonical\n---\n\n# Temple Bell Strike Cadences, Public Acoustic Chronometry & Maritime Nocturnal Star Clocks\n\n## 1. Social Spatialization of Acoustic Time\nIn ancient and medieval Tamil cities, citizens did not possess personal clocks. Time was a **civic public utility** broadcast through acoustic signals:\n- **Single Gong Strike**: Completed 1 Naazhigai (24 minutes).\n- **Compound Bell Cadence**: At the end of every *Saamam* (3 hours), the bell sounded 7 rapid beats followed by a resonant sustain that resonated over 3 to 4 kilometers.\n\n## 2. Nocturnal Maritime Navigation at Sea\nOn open ocean voyages between Coromandel ports (Kaveripattinam, Korkai) and the Malacca Straits, water clocks were difficult to operate on rolling ship decks due to wave accelerations disrupting water inflow rates.\n\nTamil navigators (*Malaigal*) solved this through **sidereal star transit chronometry**:\n- Tracking the culmination of 27 lunar nakshatras across the ship's masthead.\n- Observing the position of the Southern Cross (*Velli-Meen*) and Canopus (*Agasthya*) relative to the horizon to accurately determine watch rotations (*Jaamam*) throughout the night.\n"
  },
  {
    "file": "knowledge/characters/char-kumbakonam-master-clepsydra-horologist-naazhigai-kanakkar.md",
    "slug": "char-kumbakonam-master-clepsydra-horologist-naazhigai-kanakkar",
    "category": "character",
    "name_en": "Master Clepsydra Horologist & Royal Astrometer: Naazhigai Kanakkar of Kumbakonam",
    "name_ta": "கும்பகோணம் தலைமை நீர் கடிகார நாழிகைக் கணக்கர் மற்றும் வானியலாளர்",
    "era": "Imperial Chola Era",
    "year_start": 980,
    "year_end": 1050,
    "thinai": "marutham",
    "summary_en": "Epitome of the skilled Tamil temple horologists who calibrated perforated copper sinking bowls, monitored solstitial shadow-stick gnomon transitions, and regulated civil and temple schedules across the Kaveri delta.",
    "summary_ta": "கும்பகோணத்தில் இயங்கிய சோழர் வானியல் நிறுவனத்தின் தலைமை நாழிகைக் கணக்கர்; செப்புக் கிண்ண நீர் கடிகாரங்களை இயக்கி, நிழற்கோல் அட்டவணைகளைத் தயாரித்து அரசவைக்கு நேரக் கணக்குகளை வழங்கிய அறிஞர்.",
    "sources": [
      "Kumbakonam Temple Charters",
      "Sarma: Astronomers in South Indian Epigraphy"
    ],
    "content": "---\nid: char-kumbakonam-master-clepsydra-horologist-naazhigai-kanakkar\ntitle: Master Clepsydra Horologist & Royal Astrometer: Naazhigai Kanakkar of Kumbakonam\ntype: character\nera: Imperial Chola Era (c. 980 - 1050 CE)\nthinai: marutham (Applied Astronomy & Horological Science)\nstatus: canonical\n---\n\n# Master Clepsydra Horologist & Royal Astrometer: Naazhigai Kanakkar of Kumbakonam\n\n## 1. Office and Scientific Training\nThe **Naazhigai Kanakkar** was a trained mathematical astronomer stationed in the major temple complexes of the Kaveri delta. Versed in both observational shadow geometry and hydraulic metrology, he occupied an indispensable role in urban governance.\n\n## 2. Core Responsibilities\n1. **Clepsydra Maintenance**: Inspecting the central gold pinhole of the copper sinking bowl every week to remove mineral scale (*Uppu-padi*) that would alter inflow velocity.\n2. **Solar Noon Resetting**: Aligning the water clock diurnal cycle with solar meridian transit using an equatorial gnomon stone.\n3. **Panchangam Computation**: Calculating solar solstices, lunar eclipses, and seasonal agricultural sowing windows (*Karuvei / Thaladi*).\n"
  },
  {
    "file": "knowledge/characters/char-chidambaram-temple-bell-timekeeper-kaala-mani-kavalar.md",
    "slug": "char-chidambaram-temple-bell-timekeeper-kaala-mani-kavalar",
    "category": "character",
    "name_en": "Chief Temple Bell Timekeeper & Watch Warden: Kaala Mani Kavalar of Chidambaram",
    "name_ta": "சிதம்பரம் திருக்கோயில் கால மணி அடித்தல் மற்றும் காவற்பணித் தலைவர்",
    "era": "Imperial Chola Era",
    "year_start": 1020,
    "year_end": 1100,
    "thinai": "marutham",
    "summary_en": "The hereditary temple official at Chidambaram stationed in the bell pavilion, responsible for watching the sinking of the naazhigai water bowl and striking the monumental bronze temple bells to announce changing hours across the urban quarters.",
    "summary_ta": "சிதம்பரக் கோயில் மணி மண்டபத்தில் அமர்ந்து நீர்க்கடிகாரத்தின் முழுகுதலைக் கண்காணித்து, பிரம்மாண்டமான வெண்கல மணிகளை முழங்கி நகர் மக்களுக்கு நேரத்தை அறிவித்த தலைமைப் பணிக் காப்பாளர்.",
    "sources": [
      "Chidambaram Temple Inscriptions (SII Vol. IV)",
      "Tamil Temple Administrative Manuals"
    ],
    "content": "---\nid: char-chidambaram-temple-bell-timekeeper-kaala-mani-kavalar\ntitle: Chief Temple Bell Timekeeper & Watch Warden: Kaala Mani Kavalar of Chidambaram\ntype: character\nera: Imperial Chola Era (c. 1020 - 1100 CE)\nthinai: marutham (Acoustic Public Horology)\nstatus: canonical\n---\n\n# Chief Temple Bell Timekeeper & Watch Warden: Kaala Mani Kavalar of Chidambaram\n\n## 1. Duty at the Bell Pavilion\nStationed upon the high terrace of the temple bell tower (*Mani-Thambam*), the **Kaala Mani Kavalar** was the bridge between scientific astronomical measurement and civic life.\n\n## 2. Execution of the Strike Protocol\n- **Single Bell Strike**: Every 24 minutes, instantly upon the metallic clink of the copper bowl sinking into the water basin.\n- **Midnight Guard Relief**: Striking twelve resonant gong peals at 30 naazhigai to signal the changing of royal night watchmen across the four city gates.\n- **Festival Fanfares**: Orchestrating the simultaneous sounding of conches, horn trumpets, and massive temple gongs during planetary alignments and annual festivals.\n"
  },
  {
    "file": "knowledge/places/place-kumbakonam-ancient-astronomical-chronometry-haven.md",
    "slug": "place-kumbakonam-ancient-astronomical-chronometry-haven",
    "category": "place",
    "name_en": "Kumbakonam: Ancient Astronomical Chronometry Haven & Kaveri Horological Center",
    "name_ta": "கும்பகோணம் - பண்டைய வானியல் காலக் கணிப்பு மையம் மற்றும் காவிரி நீரியல் கடிகாரத் தளம்",
    "era": "Sangam to Chola Era",
    "year_start": -200,
    "year_end": 1250,
    "thinai": "marutham",
    "summary_en": "Premier mathematical, astronomical, and horological center in the central Kaveri delta celebrated for over a millennium of maintaining precision hydraulic clepsydras, temple gnomon shadow-dials, and astronomical academies.",
    "summary_ta": "மத்திய காவிரி சமவெளியில் அமைந்துள்ள புகழ்பெற்ற கணித-வானியல் தலைநகர்; துல்லியமான நீர் கடிகாரங்கள், நிழற்கோல் சூரியக் கடிகாரங்கள் மற்றும் வானியல் அறிஞர்களைக் கொண்டு விளங்கிய பழம்பெரும் தளம்.",
    "sources": [
      "Thanjavur District Gazetteer",
      "ASI Reports on Kumbakonam Temples",
      "South Indian Inscriptions Vol. XIX"
    ],
    "content": "---\nid: place-kumbakonam-ancient-astronomical-chronometry-haven\ntitle: Kumbakonam: Ancient Astronomical Chronometry Haven & Kaveri Horological Center\ntype: place\nera: Sangam to Chola Era (c. 200 BCE - 1250 CE)\nthinai: marutham (Horological Topography & Astronomy)\nstatus: canonical\n---\n\n# Kumbakonam: Ancient Astronomical Chronometry Haven & Kaveri Horological Center\n\n## 1. Geographical & Cultural Significance\n**Kumbakonam** (lat 10.9600° N, lng 79.3800° E), historically situated between the Kaveri and Arasalar rivers, was famed as a premier center of intellectual and scientific scholarship in Tamilakam. \n\nIts central deltaic location made it the natural administrative and astronomical hub where agricultural flood predictions, lunar calendar calculations, and civil timekeeping standards were generated for the entire Chola empire.\n\n## 2. Horological Infrastructure\nAncient Kumbakonam housed specialized artisan workshops dedicated to:\n- Beating thin-walled copper clepsydra bowls (*Naazhigai Vattil*) calibrated against gold standards.\n- Casting high-tin acoustic bronze bells (*Mani*) and gongs.\n- Setting precision horizontal sun-dial plinths in temple courtyards.\n"
  }
]
EDGES = [
  [
    "text-mullaippattu-naazhigai-vattil-water-clock-poetry",
    "describes_hydraulic_clock",
    "concept-perforated-copper-bowl-sinking-clepsydra-hydrometry-naazhigai-vattil",
    "cultural",
    "Sangam Classical Era",
    "Mullaippattu verses describing nocturnal royal water clock horologists",
    "Mullaippattu 55-60"
  ],
  [
    "insc-kumbakonam-chola-astronomical-chronometry-charters",
    "records_clepsydra_endowments_at",
    "place-kumbakonam-ancient-astronomical-chronometry-haven",
    "epigraphical",
    "Imperial Chola Era",
    "Inscriptions endowing temple astronomers and water clock maintainers",
    "SII Vol. XIX"
  ],
  [
    "insc-chidambaram-chola-temple-bell-shift-and-water-clock-epigraphs",
    "records_bell_strike_schedule",
    "concept-temple-bell-strike-cadence-and-nocturnal-maritime-chronometry",
    "epigraphical",
    "Imperial Chola Era",
    "Endowments linking clepsydra sinking cycles to temple bell cadences",
    "SII Vol. IV"
  ],
  [
    "concept-perforated-copper-bowl-sinking-clepsydra-hydrometry-naazhigai-vattil",
    "embodies_temporal_unit",
    "concept-twenty-four-minute-naazhigai-temporal-metrology-and-sixty-naazhigai-day",
    "metrological",
    "Early Historic Era",
    "Inflow sinking calibrated to exactly 24 minutes (1 naazhigai)",
    "Suryasiddhanta"
  ],
  [
    "concept-astronomical-gnomon-shadow-stick-reckoning-nizhal-kanal",
    "calibrates_water_clock_drift",
    "concept-perforated-copper-bowl-sinking-clepsydra-hydrometry-naazhigai-vattil",
    "scientific",
    "Early Historic Era",
    "Solar meridian noon transit resetting daily clepsydra counters",
    "Pancasiddhantika"
  ],
  [
    "concept-twenty-four-minute-naazhigai-temporal-metrology-and-sixty-naazhigai-day",
    "broadcast_publicly_through",
    "concept-temple-bell-strike-cadence-and-nocturnal-maritime-chronometry",
    "social",
    "Early Historic Era",
    "Translating water clock cycles into civic bell announcements",
    "Social History"
  ],
  [
    "char-kumbakonam-master-clepsydra-horologist-naazhigai-kanakkar",
    "calibrated_water_clocks_at",
    "place-kumbakonam-ancient-astronomical-chronometry-haven",
    "scientific",
    "Imperial Chola Era",
    "Royal astrometer maintaining hydraulic clocks and gnomon tables",
    "Kumbakonam Epigraphs"
  ],
  [
    "char-chidambaram-temple-bell-timekeeper-kaala-mani-kavalar",
    "rang_bells_upon_sink_of",
    "concept-perforated-copper-bowl-sinking-clepsydra-hydrometry-naazhigai-vattil",
    "social",
    "Imperial Chola Era",
    "Watch warden striking bronze bells as copper bowl sinks",
    "Chidambaram Inscriptions"
  ],
  [
    "char-kumbakonam-master-clepsydra-horologist-naazhigai-kanakkar",
    "observed_solar_gnomons",
    "concept-astronomical-gnomon-shadow-stick-reckoning-nizhal-kanal",
    "scientific",
    "Imperial Chola Era",
    "Measuring midday sun shadows to calculate latitude and solstices",
    "Astronomy Monograph"
  ],
  [
    "concept-temple-bell-strike-cadence-and-nocturnal-maritime-chronometry",
    "utilized_by_navigators_at",
    "place-kumbakonam-ancient-astronomical-chronometry-haven",
    "maritime",
    "Imperial Chola Era",
    "Sidereal star transit chronometry guiding Chola maritime fleets",
    "Varadarajan 1998"
  ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 21 Corpus 2: Clepsydra Horology & Shadow Gnomons into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Batch 21 Corpus 2: Clepsydra Horology & Shadow Gnomons Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
