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
    "file": "knowledge/texts/text-purananuru-martial-aerophones-kombu-and-thaarai-poetry.md",
    "slug": "text-purananuru-martial-aerophones-kombu-and-thaarai-poetry",
    "category": "text",
    "name_en": "Sangam Purananuru Martial Aerophone Poetry: Kombu, Thaarai & War Horn Bugles",
    "name_ta": "புறநானூற்றுப் போர்க் காற்று இசைக் கருவிகள்: கொம்பு, தாரை மற்றும் போர்க் காளங்கள்",
    "era": "Sangam Classical Era",
    "year_start": -300,
    "year_end": 200,
    "thinai": "vanchi",
    "summary_en": "Purananuru and Padirruppathu verses detailing the acoustic terror and tactical signaling of ancient Tamil martial aerophones: curved brass buffalo-horns (Kombu), deafening straight trumpets (Thaarai / Nedum-Kaalam), and the sacred spiraled conch (Valampuri Sangu) coordinating royal phalanxes.",
    "summary_ta": "சங்க காலப் போர்க்களங்களில் படைகளை நெறிப்படுத்தவும் எதிரணியை அச்சுறுத்தவும் முழங்கப்பட்ட பித்தளைக் கொம்பு, நீண்ட நேர்த்தாரை மற்றும் வலம்புரிச் சங்குகளின் போரியல் ஒலியியல் நுட்பங்களை விவரிக்கும் புறநானூற்றுப் பாடல்கள்.",
    "sources": [
      "Purananuru 269, 287, 392",
      "Padirruppathu 42",
      "Subramanian: Sangam Music & War Instruments"
    ],
    "content": "---\nid: text-purananuru-martial-aerophones-kombu-and-thaarai-poetry\ntitle: Sangam Purananuru Martial Aerophone Poetry: Kombu, Thaarai & War Horn Bugles\ntype: text\nera: Sangam Classical Era (c. 300 BCE - 200 CE)\nthinai: vanchi (Military Invading & Tactical Warfare)\nstatus: canonical\n---\n\n# Sangam Purananuru Martial Aerophone Poetry: Kombu, Thaarai & War Horn Bugles\n\n## 1. The Acoustic Landscape of Sangam Battlefields\nIn early historic Tamil warfare (*Vanchi* thinai), aerophones played an indispensable role not merely as musical instruments, but as **high-amplitude long-distance communication systems** and psychological weapons. \n\nThe Sangam anthologies—principally *Purananuru* and *Padirruppathu*—document the coordinated sonic orchestration between percussive royal war drums (*Murasu*) and lip-reed aerophones:\n1. **Kombu (கொம்பு)**: Originally carved from the curved horns of wild water buffaloes (*Maa-maruppu*) and later cast in hollow sheet-brass (*Vengalam*), producing a booming, guttural acoustic wave that traveled across undulating terrain.\n2. **Thaarai (தாரை)**: A straight, narrow, elongated conical metal trumpet over 2 meters in length, capable of penetrating the din of roaring elephants, clashing bronze swords, and thundering hooves.\n3. **Valampuri Sangu (வலம்புரிச் சங்கு)**: The prized dextral spiral marine chank shell (*Turbinella pyrum*), blown through a pierced apex to initiate offensive maneuvers and signal dawn encampment deployments.\n\n## 2. Textual Excerpts & Epigraphical Echoes\n*Purananuru* verse 287 portrays the terrifying cacophony before an infantry clash:\n> \"தாரையும் தட்டையும் தழங்கு குரல் முரசும்...\n> போர்க்களம் அதிரப் பொங்கின காளங்கள்...\"\n*(The straight thaarai trumpets, the clashing tattain, and the thundering murasu war drum resounded in unison, shaking the battleground as the war horns roared).*\n\nIn *Padirruppathu* 42, the Chera army’s dawn march is described where the piercing frequencies of the *Thaarai* carry over several kilometers, cutting through morning coastal fog and signaling coordinating units.\n\n## 3. Archaeological Grounding\nExcavations at Adichanallur and Kodumanal have unearthed copper and bronze tubing, flared conical bells, and mouthpieces, confirming that by the mid-1st millennium BCE, Tamil metallurgical guilds had mastered the casting and jointing of thin-walled acoustic brass horns.\n"
  },
  {
    "file": "knowledge/inscriptions/insc-vellore-pallava-war-horn-and-herald-charters.md",
    "slug": "insc-vellore-pallava-war-horn-and-herald-charters",
    "category": "inscription",
    "name_en": "Vellore Pallava War-Horn Caster & Military Herald Inscriptions",
    "name_ta": "வேலூர் பல்லவர் போர்க் கொம்பு வார்ப்போர் மற்றும் படைக் காளக் கல்வெட்டுகள்",
    "era": "Pallava Era",
    "year_start": 600,
    "year_end": 850,
    "thinai": "vanchi",
    "summary_en": "Pallava granitic hero-stone and temple epigraphs in the Palar river basin recording royal tax exemptions and endowments for hereditary metalsmith guilds specialized in casting martial brass horns (Kombu), herald trumpets, and military sounding gears.",
    "summary_ta": "பல்லவப் படை வீரர்களுக்கான போர்க் கொம்புகள் மற்றும் எக்காளங்களை வார்க்கும் பித்தலைக் கொல்லர்களுக்கு அளிக்கப்பட்ட வரிவிலக்குகள் மற்றும் நிலக்கொடைகளைப் பதிவு செய்யும் வேலூர்ப் பாலாற்றுப் படுகைக் கல்வெட்டுகள்.",
    "sources": [
      "South Indian Inscriptions Vol. XII (Pallavas)",
      "Epigraphia Carnatica & Tondaimandalam Hero-Stones"
    ],
    "content": "---\nid: insc-vellore-pallava-war-horn-and-herald-charters\ntitle: Vellore Pallava War-Horn Caster & Military Herald Inscriptions\ntype: inscription\nera: Pallava Era (c. 600 - 850 CE)\nthinai: vanchi (Military Fortification & Heraldry)\nstatus: canonical\n---\n\n# Vellore Pallava War-Horn Caster & Military Herald Inscriptions\n\n## 1. Epigraphical Context & Discovery\nThe rocky defiles around Vellore and the middle Palar basin constituted a strategic military defensive frontier (*Kottam*) contested between the Pallavas of Kanchipuram, the Western Gangas, and the emerging Cholas. \n\nSeveral hero-stones (*Nadukal*) and rock charters in this region record the specific honors and land grants conferred upon **martial brass-casters (*Kombu-Kollar*)** and official military heralds (*Kaalam-Ooruvon*).\n\n## 2. Textual Decipherment & Operational Terms\nThe inscriptions use distinct technical designations:\n- **Kombu-Kani (கொம்புக் காணி)**: Hereditary tax-free land tenures granted to foundry craftsmen who forged sheet-brass curved horns and straight heraldic pipes for frontier garrisons.\n- **Thaarai-Irai-Ili (தாரை இறையிலி)**: Royal decree exempting trumpet blowers and battlefield signallers from agricultural corvée labor.\n- **Vettuvar-Kombu**: Specific mention of martial horns utilized during frontier cattle raids (*Karanthai* and *Vetchi* engagements).\n\n## 3. Sociotechnical Significance\nThese epigraphs establish that military instrument fabrication was not casual blacksmithy but a state-regulated metallurgical craft requiring precise wall-thickness control and acoustic frequency tuning to maintain battlefield tactical signal consistency across regiment wings.\n"
  },
  {
    "file": "knowledge/inscriptions/insc-thiruvannamalai-chola-temple-aerophone-ritual-epigraphs.md",
    "slug": "insc-thiruvannamalai-chola-temple-aerophone-ritual-epigraphs",
    "category": "inscription",
    "name_en": "Thiruvannamalai Chola Sacred Conch & Brass Aerophone Ritual Charters",
    "name_ta": "திருவண்ணாமலை சோழர் சங்கு மற்றும் திருக்காளத் தானக் கல்வெட்டுகள்",
    "era": "Imperial Chola Era",
    "year_start": 950,
    "year_end": 1200,
    "thinai": "marutham",
    "summary_en": "Imperial Chola epigraphs on the prakara walls of the Arunachaleswara temple enumerating dedicated endowments of gold and paddy for 108 conch shell blowers (Sangu-Ooruvor), twin brass trumpet heralds (Thaarai-Kaalam), and acoustic horn musicians.",
    "summary_ta": "திருவண்ணாமலைக் கோயில் பிரகாரச் சுவர்களில் பொறிக்கப்பட்ட 108 வலம்புரிச் சங்கு ஊதுவோர், தாரை மற்றும் திருக்காள இசைஞர்களுக்கான பொன் மற்றும் நெல் கொடைப் பதிவுகள்.",
    "sources": [
      "South Indian Inscriptions Vol. VIII",
      "Thiruvannamalai Epigraphical Survey (ASI)"
    ],
    "content": "---\nid: insc-thiruvannamalai-chola-temple-aerophone-ritual-epigraphs\ntitle: Thiruvannamalai Chola Sacred Conch & Brass Aerophone Ritual Charters\ntype: inscription\nera: Imperial Chola Era (c. 950 - 1200 CE)\nthinai: marutham (Temple Ritual Acoustics)\nstatus: canonical\n---\n\n# Thiruvannamalai Chola Sacred Conch & Brass Aerophone Ritual Charters\n\n## 1. Acoustic Spatialization in Imperial Chola Temples\nUnder Rajaraja I and Rajendra I, the monumental stone temples of Tamil Nadu functioned as massive acoustic resonators. To punctuate the astronomical transitions of the day (*Sandhi* rituals) and signal royal processions, immense ensembles of aerophones were permanently endowed.\n\n## 2. Inscriptional Records of Instrument Endowments\nThe Thiruvannamalai epigraphs (SII Vol. VIII) meticulously specify:\n- **Sangu-Pani (சங்குப் பணி)**: Allotment of daily paddy measures (*Nel-padi*) for twenty-four hereditary conch shell blowers who performed during the *Sandhya* rituals and royal abhishekams.\n- **Tiruchinnam & Thaarai**: Inscriptions detailing the donation of cast-bronze herald trumpets (*Tiruchinnam*) weighing over 4 kagas of purified metal, adorned with royal tiger (*Puli*) emblems.\n- **Kombu-Murasu Synergy**: Directives ordering that the sounding of the temple *Kombu* must precede the opening of the main sanctum doors, broadcasting the sacred moment across the entire surrounding agrarian township.\n"
  },
  {
    "file": "knowledge/concepts/concept-curved-brass-kombu-acoustic-horn-conical-bore-dynamics.md",
    "slug": "concept-curved-brass-kombu-acoustic-horn-conical-bore-dynamics",
    "category": "concept",
    "name_en": "Curved Brass Kombu Horn Acoustics, Conical Bore Dynamics & Lip-Reed Resonance",
    "name_ta": "வளைந்த பித்தளைக் கொம்பு ஒலி இயக்கவியல் மற்றும் இதழ்-அதிர்வு நுட்பம்",
    "era": "Early Historic Era",
    "year_start": -400,
    "year_end": 400,
    "thinai": "vanchi",
    "summary_en": "The physics of the curved Tamil Kombu: fabricated by hammering and brazing two half-sections of sheet brass into an expanding curved conical bore. Lip-reed excitation couples with the acoustic air column to generate high-energy fundamental and low odd-harmonic frequencies that penetrate landscape obstacles.",
    "summary_ta": "இரு பாதிப் பித்தளைத் தகடுகளை வளைத்து பற்றவைத்து உருவாக்கப்பட்ட கூம்பு வடிவக் கொம்பின் ஒலியியல்: உதட்டு-அதிர்வின் மூலம் காற்றுத் தூம்பைத் தூண்டி, அடர்ந்த காடுகள் மற்றும் மேட்டுநிலைகளைக் கடந்து பல மைல் தூரம் கேட்கும் ஆழ்ந்த அதிர்வெண் ஒலியை உருவாக்கும் இயற்பியல் நுட்பம்.",
    "sources": [
      "Fletcher & Rossing: The Physics of Musical Instruments",
      "Campbell: Brass Instruments Acoustic Analysis",
      "Raman: Acoustics of Indian Horns"
    ],
    "content": "---\nid: concept-curved-brass-kombu-acoustic-horn-conical-bore-dynamics\ntitle: Curved Brass Kombu Horn Acoustics, Conical Bore Dynamics & Lip-Reed Resonance\ntype: concept\nera: Early Historic Era (c. 400 BCE - 400 CE)\nthinai: vanchi (Acoustic Military Physics)\nstatus: canonical\n---\n\n# Curved Brass Kombu Horn Acoustics, Conical Bore Dynamics & Lip-Reed Resonance\n\n## 1. Geometry and Construction Mechanics\nThe ancient Tamil **Kombu** is an aerophone with a characteristic S-shaped or C-curved profile mimicking the arc of an Indian water-buffalo horn (*Bubalus bubalis*). \n\n### Metallurgical Fabrication:\n1. **Sheet Beating**: High-tensile sheet brass (70% copper, 30% zinc) or bronze is beaten cold with horn mallets into two symmetrical longitudinal halves with an expanding radius.\n2. **Lap-Brazing (*Iya-poruthu*)**: The two halves are joined along their curved seams using copper-tin-zinc hard solder (*Vengala-poruthu*), creating an airtight seam.\n3. **Internal Bore Profile**: The bore expands smoothly from an initial mouthpiece aperture of approximately 8–10 mm to a flared terminal bell of 80–120 mm over a total tube length of 1.4 to 1.8 meters.\n\n## 2. Acoustic Physics: Conical Bore Impedance\nUnlike cylindrical tubes (like flutes) which produce only odd harmonics, an expanding conical bore supports a complete harmonic series, allowing the player to produce distinct harmonic pitches:\n\n$$f_n = \\frac{n \\cdot v}{2 (L + \\Delta L)}$$\n\nWhere:\n- $v \\approx 343\\text{ m/s}$ is the speed of sound in air.\n- $L$ is the acoustic tube length along the curved axis.\n- $\\Delta L$ is the end correction for the flared bell aperture.\n- $n \\in \\{1, 2, 3, 4\\}$ denotes the harmonic resonance mode.\n\n### Low-Frequency Long-Range Propagation:\nThe curved geometry not only facilitates compact carriage by infantry horn-bearers, but the low fundamental frequency (typically in the 80–150 Hz range) suffers minimal atmospheric attenuation and diffraction loss around hillocks, boulder fields, and dense deciduous forests (*Mullai* / *Kurinji* terrain).\n"
  },
  {
    "file": "knowledge/concepts/concept-straight-thaarai-herald-trumpet-high-register-overtone-physics.md",
    "slug": "concept-straight-thaarai-herald-trumpet-high-register-overtone-physics",
    "category": "concept",
    "name_en": "Straight Thaarai Herald Trumpet Physics, High-Register Overtone Harmonic Series & Directional Projection",
    "name_ta": "நீண்ட நேர்தாரை எக்காள ஒலி இயற்பியல் மற்றும் மேல்தர இசைவடிவ நுட்பம்",
    "era": "Early Historic Era",
    "year_start": -300,
    "year_end": 500,
    "thinai": "vanchi",
    "summary_en": "The directional acoustic mechanics of the long straight brass trumpet (Thaarai / Ekkalam): constructed with telescoping sections of drawn brass tubing, generating a highly directional, piercing high-frequency acoustic beam that cuts through ambient battlefield noise to convey command signals.",
    "summary_ta": "நேரான நீண்ட பித்தலைக் குழாய்களால் உருவாக்கப்பட்ட தாரை அல்லது எக்காளத்தின் திசைசார் ஒலியியல்: போர்க்களத்தின் பேரிரைச்சலையும் கிழித்துக்கொண்டு பல மைல் தூரத்திலுள்ள படைப்பிரிவுகளுக்கு ஆணை பிறப்பிக்கும் கூர்மையான உயர் அலைவரிசை அதிர்வெண்களை உருவாக்கும் நுட்பம்.",
    "sources": [
      "Bate: The Trumpet and Trombone",
      "Benade: Fundamentals of Musical Acoustics",
      "ASI Epigraphical Notes on Sangam Warfare"
    ],
    "content": "---\nid: concept-straight-thaarai-herald-trumpet-high-register-overtone-physics\ntitle: Straight Thaarai Herald Trumpet Physics, High-Register Overtone Harmonic Series & Directional Projection\ntype: concept\nera: Early Historic Era (c. 300 BCE - 500 CE)\nthinai: vanchi (Tactical Acoustic Signaling)\nstatus: canonical\n---\n\n# Straight Thaarai Herald Trumpet Physics, High-Register Overtone Harmonic Series & Directional Projection\n\n## 1. Acoustic Architecture of the Thaarai\nThe **Thaarai** (or *Nedum-Kaalam* / *Ekkalam*) is a long, straight, telescoping tubular aerophone constructed from two or three concentric brass sections that friction-fit into one another.\n\n### Structural Parameters:\n- **Total Length**: 1.8 to 2.4 meters.\n- **Bore Profile**: Predominantly narrow cylindrical tubing along 80% of its length, terminating in a sharply expanding hyperbolic brass bell.\n- **Mouthpiece (*Vaai-kinnam*)**: Shallow, cup-shaped bronze rim facilitating high-pressure lip compression (*embouchure*).\n\n## 2. Directional Projection & Sound Pressure\nBecause the sound wavelength at upper harmonics ($\\lambda \\approx 0.3\\text{ m}$ at 1000 Hz) is smaller than or comparable to the diameter of the flared bell, the sound radiation pattern exhibits high **directionality**:\n\n$$D(\\theta) \\propto \\frac{2 J_1(k a \\sin\\theta)}{k a \\sin\\theta}$$\n\nWhere:\n- $k = 2\\pi / \\lambda$ is the acoustic wavenumber.\n- $a$ is the radius of the trumpet bell opening.\n- $J_1$ is the first-order Bessel function of the first kind.\n\nThis directional \"beaming\" allowed a mounted herald or elephant-back signaller to point the trumpet directly toward a specific wing of the battlefield (vanguard, flank, or reserve rear-guard) and project high-frequency overtones (1000–3000 Hz) directly to the target commander.\n"
  },
  {
    "file": "knowledge/concepts/concept-valampuri-sangu-spiral-conch-shell-resonance-acoustics.md",
    "slug": "concept-valampuri-sangu-spiral-conch-shell-resonance-acoustics",
    "category": "concept",
    "name_en": "Valampuri Sangu Right-Spiraled Turbinella Conch Acoustic Resonance & Standing Wave Acoustics",
    "name_ta": "வலம்புரிச் சங்கு சுழல் அதிர்வெண் மற்றும் நிலை அலை ஒலி நுட்பம்",
    "era": "Early Historic Era",
    "year_start": -500,
    "year_end": 500,
    "thinai": "neithal",
    "summary_en": "The bio-acoustic physics of the marine chank shell (Turbinella pyrum): cutting the apical whorl creates a natural logarithmic spiral acoustic resonator. Standing waves established inside the logarithmic calcium carbonate chambers produce pure fundamental tones with extraordinary harmonic clarity.",
    "summary_ta": "மன்னார் வளைகுடாவில் மூழ்கி எடுக்கப்படும் வலம்புரிச் சங்கின் நுனி துளையிடப்பட்டு உருவாக்கப்படும் இயற்கை மடக்கைச் சுழல் ஒலியியல்: கால்சியம் கார்பனேட் அறைகளுக்குள் நிலை அலைகளை உருவாக்கி, அதிர்வுமிக்க தூய ஒலியை வெளிப்படுத்தும் கடல்சார் உயிரி-ஒலியியல் நுட்பம்.",
    "sources": [
      "Hornell: The Sacred Chank of India (1914)",
      "Mahadevan: Marine Shell Lapidary of Sangam Tamilakam",
      "Acoustical Society of India Monograph on Conch Resonators"
    ],
    "content": "---\nid: concept-valampuri-sangu-spiral-conch-shell-resonance-acoustics\ntitle: Valampuri Sangu Right-Spiraled Turbinella Conch Acoustic Resonance & Standing Wave Acoustics\ntype: concept\nera: Early Historic Era (c. 500 BCE - 500 CE)\nthinai: neithal (Bio-Acoustics & Marine Archaeology)\nstatus: canonical\n---\n\n# Valampuri Sangu Right-Spiraled Turbinella Conch Acoustic Resonance & Standing Wave Acoustics\n\n## 1. Natural Logarithmic Spiral Geometry\nThe shell of the marine gastropod **Turbinella pyrum** grows according to a precise equiangular or **logarithmic spiral**:\n\n$$r(\\theta) = a \\cdot e^{b\\theta}$$\n\nWhere $r$ is the radial distance from the columella axis, and $b$ is the spiral growth constant.\n\nIn rare dextral specimens (*Valampuri*), the whorls spiral clockwise, held in profound reverence across Tamil civilization for both ritual purity and unique resonance properties.\n\n## 2. Acoustic Processing & Modification\n1. **Apex Truncation (*Sangu-Thundithal*)**: The apex is carefully cut with an iron saw or ground flat on a wet sandstone lap until the first internal whorl chamber is exposed.\n2. **Lip Adaptation**: A bronze or silver rim is fitted onto the exposed apical opening to form a smooth lip-cushion.\n3. **Internal Acoustic Chamber**: The internal volute forms an expanding, coiled acoustic horn with hard, non-porous aragonite walls that reflect over 98% of incident acoustic energy, creating a standing wave of exceptional quality factor ($Q$).\n\n## 3. Acoustic Properties & Spectral Characteristics\nWhen blown by an experienced practitioner, the conch produces a rich, stable fundamental tone typically around 250–350 Hz (near C4-E4), accompanied by strong second and third harmonics. The dense crystalline structure of the shell prevents wall vibrations, ensuring that almost all mechanical breath energy is converted into directed acoustic radiation.\n"
  },
  {
    "file": "knowledge/concepts/concept-murasu-kattil-war-drum-and-aerophone-battle-orchestration.md",
    "slug": "concept-murasu-kattil-war-drum-and-aerophone-battle-orchestration",
    "category": "concept",
    "name_en": "Murasu-Kattil War Drum Coordination, Aerophone Signal Coding & Sangam Tactical Battlefield Orchestration",
    "name_ta": "முரசுக் கட்டில் போர் முரசு மற்றும் காற்று இசைக் கருவிகளின் கள ஆணை உத்தி",
    "era": "Sangam Classical Era",
    "year_start": -300,
    "year_end": 200,
    "thinai": "vanchi",
    "summary_en": "The integrated acoustic signaling doctrine of ancient Tamil military commands: pairing low-frequency percussive shockwaves from the sacred Veeramurasu drum with sharp aerophone melodic codes (Kombu and Thaarai) to execute flanking, charges, retreats, and encirclement maneuvers.",
    "summary_ta": "பண்டைத் தமிழகப் போர்க்களங்களில் முரசுக் கட்டிலில் வைக்கப்பட்ட வீரமுரசின் பேரொலியுடன் பித்தளைக் கொம்புகள் மற்றும் தாரைகளின் அலைவரிசைகளை ஒருங்கிணைத்து, படைகளை முன்னேற்றவும், சுற்றிவளைக்கவும், பின்வாங்கவும் ஆணையிட்ட போரியல் தகவல் தொடர்பு முறைமை.",
    "sources": [
      "Purananuru 50, 68",
      "Padirruppathu 17",
      "Nilakanta Sastri: The Pandyan Kingdom & Military Institutions"
    ],
    "content": "---\nid: concept-murasu-kattil-war-drum-and-aerophone-battle-orchestration\ntitle: Murasu-Kattil War Drum Coordination, Aerophone Signal Coding & Sangam Tactical Battlefield Orchestration\ntype: concept\nera: Sangam Classical Era (c. 300 BCE - 200 CE)\nthinai: vanchi (Tactical Military Communications)\nstatus: canonical\n---\n\n# Murasu-Kattil War Drum Coordination, Aerophone Signal Coding & Sangam Tactical Battlefield Orchestration\n\n## 1. The Command System: Murasu-Kattil\nIn ancient Tamil royal ideology, the **Veeramurasu** (royal battle drum) was an embodiment of royal sovereignty, enshrined upon a sacred sandalwood couch (*Murasu-Kattil*) and bathed in purified water and peacock plumes.\n\nOn the battlefield, the *Murasu* served as the **primary rhythmic pulse** that synchronized troop cadences and stimulated adrenaline among warrior regiments (*Maravar*).\n\n## 2. Dual Acoustic Architecture: Rhythm + Signal\nBecause percussive drumbeats are omnidirectional and difficult to differentiate in rapid tactical changes, the Sangam army paired them with **aerophone melodic codes**:\n\n| Instrument | Acoustic Domain | Tactical Signal Function |\n| :--- | :--- | :--- |\n| **Veeramurasu** | 40–100 Hz Sub-bass | Battle line synchronization, marching tempo, psychological dread. |\n| **Kombu (Horn)** | 100–300 Hz Mid-bass | Formation reshaping: V-shaped phalanx (*Parunthu-vyoogam*), spear wall. |\n| **Thaarai (Trumpet)** | 800–2500 Hz High-register | Immediate charge command, cavalry intercept, tactical retreat. |\n| **Valampuri Sangu** | 250–500 Hz Mid-register | Dawn mobilization, cessation of daylight fighting, royal heraldry. |\n\n## 3. Signal Transmission Range\nUnder favorable thermal inversion conditions at dawn and dusk, the acoustic output of the combined *Kombu-Thaarai* ensemble exceeded 110 dB SPL at 1 meter, maintaining intelligibility over a radius of 3 to 5 kilometers across open plains.\n"
  },
  {
    "file": "knowledge/characters/char-vellore-master-horn-caster-kombu-kollan.md",
    "slug": "char-vellore-master-horn-caster-kombu-kollan",
    "category": "character",
    "name_en": "Master Kombu Caster & Brass Aerophone Founder: Kombu Kollan of Vellore",
    "name_ta": "வேலூர்ப் பெருங்கொம்பு வார்ப்பாளர் மற்றும் பித்தளைக் கொல்லர்",
    "era": "Pallava Era",
    "year_start": 650,
    "year_end": 750,
    "thinai": "vanchi",
    "summary_en": "Epitome of the skilled Tamil military metalsmiths in the Palar valley who mastered the casting, seam-brazing, and acoustic tuning of curved martial horns (Kombu) and heraldic trumpets for royal frontier garrisons.",
    "summary_ta": "வேலூர் மற்றும் பாலாற்றுப் படைத்தளங்களுக்குத் தேவையான வளைந்த போர்க் கொம்புகள், எக்காளங்கள் மற்றும் முழவுப் பூண்களைத் துல்லியமான ஒலியியல் அதிர்வெண்களுடன் வார்த்தளித்த தலைசிறந்த பித்தளைக் கொல்லர்.",
    "sources": [
      "Vellore District Epigraphs",
      "Pallava Metallurgy & Weapon Guild Records"
    ],
    "content": "---\nid: char-vellore-master-horn-caster-kombu-kollan\ntitle: Master Kombu Caster & Brass Aerophone Founder: Kombu Kollan of Vellore\ntype: character\nera: Pallava Era (c. 650 - 750 CE)\nthinai: vanchi (Military Metallurgy & Guild Craft)\nstatus: canonical\n---\n\n# Master Kombu Caster & Brass Aerophone Founder: Kombu Kollan of Vellore\n\n## 1. Professional Identity & Lineage\nOperating in the fortified settlements flanking the Palar river gorge near Vellore, the **Kombu Kollan** was a master metalsmith belonging to the hereditary artisan guild (*Kammalar*), specifically tasked with producing acoustic instruments for military communication.\n\n## 2. Technical Specializations\n1. **Alloy Optimization**: Formulating high-tin bronze and sheet brass alloys that resisted cracking under repeated high-amplitude breath vibration and rough battlefield conditions.\n2. **Acoustic Seam Jointing**: Utilizing specialized hard-soldering fluxes containing calcined borax and copper filings to ensure seamless lap joints along curved horn contours.\n3. **Mouthpiece Carving**: Hand-turning cup-shaped bronze mouthpieces calibrated to the specific lip morphology of royal heralds.\n\n## 3. Historical Impact\nHis foundries equipped the border garrisons of the northern Tamil country, establishing standardized acoustic signal instruments that enabled rapid mobilization against northern frontier cavalry raids.\n"
  },
  {
    "file": "knowledge/characters/char-madurai-royal-herald-trumpeter-thaarai-ooruvon.md",
    "slug": "char-madurai-royal-herald-trumpeter-thaarai-ooruvon",
    "category": "character",
    "name_en": "Pandya Royal Herald & High-Register Battle Trumpeter: Thaarai Ooruvon",
    "name_ta": "பாண்டியர் போர்க்களப் பெருந்தாரை ஊதுவோன்",
    "era": "Sangam Classical Era",
    "year_start": -200,
    "year_end": 100,
    "thinai": "vanchi",
    "summary_en": "The revered royal herald and battlefield trumpeter in the Pandya capital of Madurai, stationed upon the royal elephant or command chariot to translate kingly tactical orders into piercing acoustic trumpet blasts that directed thousands of warriors.",
    "summary_ta": "மதுரை பாண்டிய மன்னரின் ஆணைகளைத் துல்லியமான எக்காள ஒலிகளாக மாற்றி போர்க்களத்தில் ஆயிரக்கணக்கான வீரர்களுக்கு வழிகாட்டிய அரசவைப் பெருந்தாரை ஊதுவோன்.",
    "sources": [
      "Purananuru 287",
      "Maduraikkanji 360-385",
      "Tamil Heroic Poetry (Kailasapathy)"
    ],
    "content": "---\nid: char-madurai-royal-herald-trumpeter-thaarai-ooruvon\ntitle: Pandya Royal Herald & High-Register Battle Trumpeter: Thaarai Ooruvon\ntype: character\nera: Sangam Classical Era (c. 200 BCE - 100 CE)\nthinai: vanchi (Tactical Field Command)\nstatus: canonical\n---\n\n# Pandya Royal Herald & High-Register Battle Trumpeter: Thaarai Ooruvon\n\n## 1. Role in the Royal Command Structure\nThe **Thaarai Ooruvon** (herald trumpeter) held a distinguished position in the immediate retinue of the Pandya monarch. Stationed alongside the royal umbrella (*Venkorra-kudai*) on the commanding war elephant (*Pattathu-yaanai*), he possessed the lung capacity and acoustic discipline required to project signals across vast battlefronts.\n\n## 2. Mastery of Battlefield Codification\n- **Staccato Pulses**: Rapid repeated blasts signaling an immediate spear charge by the front-line infantry.\n- **Descending Slurs**: Extended decrescendo pitches commanding tactical orderly retreat and regrouping behind shield ramparts.\n- **Twin Trumpet Counterpoint**: Sounding in tandem with a secondary trumpeter to designate left-flank or right-flank encirclement.\n\n## 3. Cultural Veneration\nThe herald was protected by code of honor; in ancient Tamil chivalric ethics (*Aram*), unarmed heralds bearing only sounding horns could not be targeted by archers or spearmen during active combat.\n"
  },
  {
    "file": "knowledge/places/place-vellore-ancient-martial-aerophone-haven.md",
    "slug": "place-vellore-ancient-martial-aerophone-haven",
    "category": "place",
    "name_en": "Vellore: Ancient Martial Aerophone Foundry Haven & Palar Military Redoubt",
    "name_ta": "வேலூர் - பண்டைய போர்க் காற்றுக்கருவி வார்ப்புத் தளம் மற்றும் பாலாற்றுப் படைத்தளம்",
    "era": "Pallava to Vijayanagara Era",
    "year_start": 600,
    "year_end": 1600,
    "thinai": "vanchi",
    "summary_en": "Strategic granitic fortified valley and riverine foundry center on the Palar river in northern Tamil Nadu, acclaimed for centuries of producing military brass horns (Kombu), straight herald trumpets (Thaarai), and armory sounding equipment.",
    "summary_ta": "வட தமிழகத்தில் பாலாற்றுப் படுகையில் அமைந்துள்ள வரலாற்றுச் சிறப்புமிக்க மலைக்கோட்டைத் தளம்; பல நூற்றாண்டுகளாக போர்க் கொம்புகள், எக்காளங்கள் மற்றும் படைக்கலங்களை வார்த்தளித்த முதன்மைத் தொழிற்பட்டறை மையம்.",
    "sources": [
      "District Gazetteer of North Arcot",
      "ASI Reports on Vellore Fort and Palar Archaeology",
      "South Indian Inscriptions Vol. I & VIII"
    ],
    "content": "---\nid: place-vellore-ancient-martial-aerophone-haven\ntitle: Vellore: Ancient Martial Aerophone Foundry Haven & Palar Military Redoubt\ntype: place\nera: Pallava to Vijayanagara Era (c. 600 - 1600 CE)\nthinai: vanchi (Fortified Metallurgy & Military Geography)\nstatus: canonical\n---\n\n# Vellore: Ancient Martial Aerophone Foundry Haven & Palar Military Redoubt\n\n## 1. Geographical & Strategic Topography\nSituated at the mouth of the rocky Palar river gorge flanked by precipitous granite hills, **Vellore** (lat 12.9165° N, lng 79.1325° E) controlled the primary highland pass between the Mysore plateau and the Coromandel plains. \n\nIts abundant granitic boulders provided natural defensive redoubts, while the local river sands and scrub forests yielded charcoal and quartz mold sands ideal for precision non-ferrous foundry operations.\n\n## 2. The Metallurgy of Military Sounding Equipment\nThroughout the Pallava, Chola, and later Nayaka eras, Vellore housed specialized artisan wards (*Kollar-Cheri*) dedicated to casting:\n- Heavy curved brass war horns (*Kombu*) capable of piercing mountain winds.\n- Multi-section straight trumpets (*Thaarai / Ekkalam*).\n- Massive bronze gong plates (*Semmankalam*) and war-drum brass hardware.\n\n## 3. Archaeological & Living Heritage\nExcavations along the Palar floodplains have repeatedly yielded bronze crucibles, tuyere nozzles, and fragments of brazed sheet-metal instruments, attesting to the continuous tradition of military instrument craftsmanship that defended the northern frontier of the Tamil country.\n"
  }
]
EDGES = [
  [
    "text-purananuru-martial-aerophones-kombu-and-thaarai-poetry",
    "celebrates_martial_horns",
    "concept-curved-brass-kombu-acoustic-horn-conical-bore-dynamics",
    "cultural",
    "Sangam Classical Era",
    "Sangam poetry detailing brass war horn acoustic signaling",
    "Purananuru 269"
  ],
  [
    "insc-vellore-pallava-war-horn-and-herald-charters",
    "records_horn_casters_at",
    "place-vellore-ancient-martial-aerophone-haven",
    "epigraphical",
    "Pallava Era",
    "Inscriptions detailing royal brass horn caster land grants",
    "SII Vol. XII"
  ],
  [
    "insc-thiruvannamalai-chola-temple-aerophone-ritual-epigraphs",
    "records_sacred_conch_rituals",
    "concept-valampuri-sangu-spiral-conch-shell-resonance-acoustics",
    "epigraphical",
    "Imperial Chola Era",
    "Endowments for conch blowers and temple horn musicians",
    "SII Vol. VIII"
  ],
  [
    "concept-curved-brass-kombu-acoustic-horn-conical-bore-dynamics",
    "paired_with_high_register_trumpet",
    "concept-straight-thaarai-herald-trumpet-high-register-overtone-physics",
    "technological",
    "Early Historic Era",
    "Acoustic frequency pairing between bass horns and high-register trumpets",
    "Campbell: Brass Instruments"
  ],
  [
    "concept-straight-thaarai-herald-trumpet-high-register-overtone-physics",
    "signaled_tactical_commands_in",
    "concept-murasu-kattil-war-drum-and-aerophone-battle-orchestration",
    "military",
    "Early Historic Era",
    "High-frequency directional overtones directing tactical battlefield phalanxes",
    "Purananuru 287"
  ],
  [
    "char-vellore-master-horn-caster-kombu-kollan",
    "cast_brass_aerophones_at",
    "place-vellore-ancient-martial-aerophone-haven",
    "social",
    "Pallava Era",
    "Master foundry metalsmith crafting war horns in the Palar valley",
    "Vellore Epigraphs"
  ],
  [
    "char-madurai-royal-herald-trumpeter-thaarai-ooruvon",
    "blew_heraldic_trumpet_in",
    "text-purananuru-martial-aerophones-kombu-and-thaarai-poetry",
    "cultural",
    "Sangam Classical Era",
    "Royal herald trumpeter praised in Sangam martial poetry",
    "Maduraikkanji"
  ],
  [
    "char-vellore-master-horn-caster-kombu-kollan",
    "engineered_conical_horns",
    "concept-curved-brass-kombu-acoustic-horn-conical-bore-dynamics",
    "technological",
    "Pallava Era",
    "Brazing sheet brass halves into expanding conical horn contours",
    "Pallava Metallurgy"
  ],
  [
    "concept-murasu-kattil-war-drum-and-aerophone-battle-orchestration",
    "directed_by_royal_herald",
    "char-madurai-royal-herald-trumpeter-thaarai-ooruvon",
    "military",
    "Sangam Classical Era",
    "Herald signaling coordinated commands with royal war drums",
    "Purananuru 50"
  ],
  [
    "concept-valampuri-sangu-spiral-conch-shell-resonance-acoustics",
    "sounded_in_orchestration",
    "concept-murasu-kattil-war-drum-and-aerophone-battle-orchestration",
    "military",
    "Early Historic Era",
    "Sacred conch shell initiating battlefield deployments",
    "Hornell 1914"
  ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 20 Corpus 1: Martial Aerophones & War Horns into Moolam Chronicles & Life Graph...")
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
                id, slug, name_en, name_ta, era, year_start, year_end,
                thinai, node_type, summary_en, summary_ta, sources,
                layer, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, NOW()
            )
            ON CONFLICT (slug) DO UPDATE SET
                name_en = EXCLUDED.name_en,
                name_ta = EXCLUDED.name_ta,
                era = EXCLUDED.era,
                year_start = EXCLUDED.year_start,
                year_end = EXCLUDED.year_end,
                thinai = EXCLUDED.thinai,
                node_type = EXCLUDED.node_type,
                summary_en = EXCLUDED.summary_en,
                summary_ta = EXCLUDED.summary_ta,
                sources = EXCLUDED.sources,
                layer = EXCLUDED.layer;
        """, (
            str(uuid.uuid4()),
            slug,
            d["name_en"],
            d["name_ta"],
            d["era"],
            d["year_start"],
            d["year_end"],
            d["thinai"],
            d["category"],
            d["summary_en"],
            d["summary_ta"],
            d["sources"],
            "historical_proof"
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

    print(f"\n🎉 Batch 20 Corpus 1: Martial Aerophones & War Horns Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
