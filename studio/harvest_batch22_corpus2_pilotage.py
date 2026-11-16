#!/usr/bin/env python3
# Ingestion harvester for Batch 22 Corpus 2: Coastal Marine Pilotage & Navigation
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
    "file": "knowledge/texts/text-akanunuru-maritime-pilotage-and-sandbar-sounding-poetry.md",
    "slug": "text-akanunuru-maritime-pilotage-and-sandbar-sounding-poetry",
    "category": "text",
    "name_en": "Akananuru & Maduraikkanji Verses on Estuarine Pilotage & Sandbar Sounding",
    "name_ta": "அகநானூறு மற்றும் மதுரைக்காஞ்சி முகத்துவாரக் கப்பல் வழிகாட்டல் பாடல்கள்",
    "era": "Sangam Classical Era",
    "year_start": -200,
    "year_end": 100,
    "thinai": "neithal",
    "summary_en": "Akananuru 152 and Maduraikkanji lines 315-325 depicting ocean-going merchant vessels (Vangam) anchoring offshore while local coastal pilots (Kadal-Kaan / Paravai-Kavalar) in shallow outrigger boats sound shifting sandbars and tow ships into safe estuarine harbors.",
    "summary_ta": "நடுக்கடலில் வந்து நிற்கும் பெருங்கப்பல்களை உள்ளூர்த் துறைமுகத் தலைவர்கள் சிறிய படகுகளில் சென்று, மணல்திட்டு ஆழங்களை அளந்து, பாதுகாப்பாக முகத்துவாரத் துறைமுகங்களுக்குள் இழுத்து வரும் காட்சிகளை விவரிக்கும் சங்கப் பாடல்கள்.",
    "sources": [
      "Akananuru 152",
      "Maduraikkanji 315-325",
      "Pattinappalai 170-185"
    ],
    "content": "---\nid: text-akanunuru-maritime-pilotage-and-sandbar-sounding-poetry\ntitle: Akananuru & Maduraikkanji Verses on Estuarine Pilotage & Sandbar Sounding\ntype: text\nera: Sangam Classical Era (c. 200 BCE - 100 CE)\nthinai: neithal (Estuarine Navigation & Maritime Commerce)\nstatus: canonical\n---\n\n# Akananuru & Maduraikkanji Verses on Estuarine Pilotage & Sandbar Sounding\n\n## 1. Classical Descriptions of Harbor Pilotage\nThe estuarine rivermouths of ancient Tamilakam—where the Kaveri, Vaigai, and Tambraparni emptied into the Bay of Bengal and Gulf of Mannar—were fraught with dynamic, shifting sandbars (*Manal-Thittu*).\n\nIn *Akananuru* 152, the arrival of foreign merchant vessels is portrayed:\n> \"முந்நீர் வழங் நாவாய் மூழ்கு மணல் அடைப்பத்\n> துறைவழிக் காட்டும் தோணிக் கிழவன்...\"\n*(As shifting sands block the rivermouth for deep-draft ocean ships, the master of the pilot boat steps forward to guide them safely along the submerged channel).*\n\nIn *Maduraikkanji*, the port of Korkai is described where deep-sea vessels furl their white sails (*Paai-kazhuthal*) and submit to the guidance of seasoned local pilots who know every submerged shoal.\n"
  },
  {
    "file": "knowledge/inscriptions/insc-devipattinam-pandya-harbor-pilot-and-mooring-charters.md",
    "slug": "insc-devipattinam-pandya-harbor-pilot-and-mooring-charters",
    "category": "inscription",
    "name_en": "Devipattinam Pandya Harbor Pilotage & Channel Mooring Charters",
    "name_ta": "தேவிபட்டினம் பாண்டியர் துறைமுக வழிகாட்டல் மற்றும் நங்கூரக் கல்வெட்டுகள்",
    "era": "Pandya Classical Era",
    "year_start": 700,
    "year_end": 950,
    "thinai": "neithal",
    "summary_en": "Pandya stone epigraphs from the coastal temple at Devipattinam (Navapashanam) recording port dues, pilotage rights, and royal directives for maintaining navigation channel markers and stone mooring posts in the Palk Bay.",
    "summary_ta": "பாக் வளைகுடாவில் அமைந்துள்ள தேவிபட்டினக் கடற்கரைக் கல்வெட்டுகள்; கப்பல் வழிகாட்டிகளுக்கான உரிமைகள், நங்கூரக் கட்டணங்கள் மற்றும் வழித்தட அடையாளப் பராமரிப்பு குறித்த பாண்டியர் பட்டயங்கள்.",
    "sources": [
      "South Indian Inscriptions Vol. XIV",
      "Ramanathapuram District Epigraphical Survey"
    ],
    "content": "---\nid: insc-devipattinam-pandya-harbor-pilot-and-mooring-charters\ntitle: Devipattinam Pandya Harbor Pilotage & Channel Mooring Charters\ntype: inscription\nera: Pandya Classical Era (c. 700 - 950 CE)\nthinai: neithal (Maritime Law & Port Epigraphy)\nstatus: canonical\n---\n\n# Devipattinam Pandya Harbor Pilotage & Channel Mooring Charters\n\n## 1. Geographical Significance of Devipattinam\nDevipattinam, located on the Palk Bay coast north of Rameswaram, provided a naturally sheltered shallow roadstead protected from the open swells of the Bay of Bengal. \n\nThe site features nine submerged natural stone outcrops (*Navapashanam*) historically utilized as calm-water mooring bollards.\n\n## 2. Inscriptional Directives\n- **Thurai-Kaan-Kani**: Land grants endowed to hereditary fishermen-pilots who mapped the submerged coral heads and sand spits.\n- **Kalam-Kattum-Irai**: Mooring taxes paid by visiting coastal traders in exchange for pilotage guidance through the shallow reefs of the Palk Strait.\n"
  },
  {
    "file": "knowledge/inscriptions/insc-pamban-strait-naval-channel-pilotage-epigraphs.md",
    "slug": "insc-pamban-strait-naval-channel-pilotage-epigraphs",
    "category": "inscription",
    "name_en": "Pamban Strait Marine Channel Pilotage & Reef Passage Charters",
    "name_ta": "பாம்பன் நீரிணை கடல் வழித்தட வழிகாட்டல் மற்றும் பவளப்பாறைப் பட்டயங்கள்",
    "era": "Medieval Pandya to Chola Era",
    "year_start": 900,
    "year_end": 1200,
    "thinai": "neithal",
    "summary_en": "Epigraphical records from Rameswaram and Mandapam detailing the specialized guild of channel pilots who navigated royal naval fleets and merchant vessels through the treacherous submerged sandstone reefs of the Pamban Passage.",
    "summary_ta": "இராமேஸ்வரம் மற்றும் மண்டபம் பகுதிகளில் கண்டறியப்பட்ட கல்வெட்டுகள்; பாம்பன் நீரிணையின் ஆபத்தான பாறை இடுக்குகளில் சோழ மற்றும் பாண்டியப் போர்க் கப்பல்களை வழிநடத்திய மாலுமிகள் பற்றிய சான்றுகள்.",
    "sources": [
      "Epigraphia Indica Vol. XXXVI",
      "Sastri: The Pandyan Kingdom (Maritime Chapters)"
    ],
    "content": "---\nid: insc-pamban-strait-naval-channel-pilotage-epigraphs\ntitle: Pamban Strait Marine Channel Pilotage & Reef Passage Charters\ntype: inscription\nera: Medieval Pandya to Chola Era (c. 900 - 1200 CE)\nthinai: neithal (Strait Navigation & Naval History)\nstatus: canonical\n---\n\n# Pamban Strait Marine Channel Pilotage & Reef Passage Charters\n\n## 1. Strategic Naval Bottleneck\nThe **Pamban Strait** between peninsular India and Rameswaram Island was the linchpin of coastal trade between the Malabar coast, Sri Lanka, and the Coromandel coast. The submerged sandstone reef (*Adam's Bridge* foundation) created narrow, shallow tidal gaps that only expert local pilots could navigate.\n\n## 2. Inscriptional Evidence\nEpigraphs record the appointment of **Neer-Vazhi-Kattuvar** (channel pilot officers) endowed by royal charter to light beacon fires on sand dunes and board incoming deep-water vessels to safely steer them across the reefs during high spring tides.\n"
  },
  {
    "file": "knowledge/concepts/concept-bamboo-sounding-pole-and-lead-fathom-bathymetry-thandukal.md",
    "slug": "concept-bamboo-sounding-pole-and-lead-fathom-bathymetry-thandukal",
    "category": "concept",
    "name_en": "Bamboo Sounding Poles, Tallow-Tipped Lead Fathom Bathymetry & Shoal Detection (Thandukal)",
    "name_ta": "மூங்கில் ஆழக்கோல், கொழுப்புப் பூசிய ஈயக் குண்டு மற்றும் நீராழக் கணிப்பு நுட்பம்",
    "era": "Early Historic Era",
    "year_start": -400,
    "year_end": 500,
    "thinai": "neithal",
    "summary_en": "The nautical bathymetry techniques of ancient Tamil mariners: utilizing graduated bamboo sounding poles (Thandukal) in estuarine shallows and tallow-tipped heavy lead sounding weights dropped on hemp cords in deep water to measure fathoms (Bhaagam) and sample seafloor sediment (sand, shell, mud) to identify safe anchorage.",
    "summary_ta": "கழிமுகங்களில் மூங்கில் ஆழக்கோல் (தண்டுகல்) கொண்டும், ஆழ்கடலில் கொழுப்புப் பூசிய ஈயக் குண்டுகளைக் கயிற்றில் கட்டி இறக்கியும் நீரின் ஆழத்தையும் கடல்தள மண்ணையும் (மணல், சங்கு, சேறு) அறிந்து நங்கூரமிட்ட பண்டைய நீரியல் நுட்பம்.",
    "sources": [
      "Hornell: The Origins and Ethnological Significance of Indian Boat Designs",
      "Deloche: Ancient Transport Technology in India"
    ],
    "content": "---\nid: concept-bamboo-sounding-pole-and-lead-fathom-bathymetry-thandukal\ntitle: Bamboo Sounding Poles, Tallow-Tipped Lead Fathom Bathymetry & Shoal Detection (Thandukal)\ntype: concept\nera: Early Historic Era (c. 400 BCE - 500 CE)\nthinai: neithal (Nautical Bathymetry & Hydrography)\nstatus: canonical\n---\n\n# Bamboo Sounding Poles, Tallow-Tipped Lead Fathom Bathymetry & Shoal Detection (Thandukal)\n\n## 1. Sounding in Shallow Estuaries: Thandukal\nIn the shallow, turbulent waters of river estuaries and lagoon mouths, pilot boats (*Thoni*) operated directly ahead of large merchant ships. A crewman stood at the prow continuously plunging a notched **bamboo sounding pole (*Thandukal*)** into the water:\n- **Graduations**: Marked in spans (*San*) and cubits (*Muzham*).\n- **Acoustic Feedback**: Tapping the riverbed revealed whether the bottom was soft shifting silt, firm sand, or destructive submerged coral.\n\n## 2. Deep-Water Bathymetry: The Lead Line (*Eeya-Kundu*)\nIn open roadsteads, pilots dropped a conical lead weight (5–8 kg) attached to a calibrated hemp rope marked at fathom intervals (**Bhaagam** $\\approx 1.8\\text{ meters}$):\n- **Tallow Cup (*Koluppu-Kuzhi*)**: The hollow base of the lead weight was packed with sticky animal fat or tallow.\n- When the weight struck bottom, sediment adhered to the tallow:\n  - Clean quartz sand indicated safe dragging-resistant anchorage.\n  - Soft green mud warned of poor holding ground.\n  - Shell fragments signaled adjacent live reefs.\n"
  },
  {
    "file": "knowledge/concepts/concept-direction-finding-shore-sighting-birds-disak-kaakkai-navigation.md",
    "slug": "concept-direction-finding-shore-sighting-birds-disak-kaakkai-navigation",
    "category": "concept",
    "name_en": "Direction-Finding Shore-Sighting Birds & Avian Oceanic Navigation (Disak-Kaakkai)",
    "name_ta": "திசைகாட்டும் கடற்காகங்கள் மற்றும் பறவைசார் கடல்வழி வழிகாட்டல் முறை",
    "era": "Early Historic Era",
    "year_start": -500,
    "year_end": 300,
    "thinai": "neithal",
    "summary_en": "The biological navigation practice of keeping trained shore-sighting birds (Disak-Kaakkai / coastal crows) aboard ocean-going vessels. When mariners lost land sighting in monsoonal squalls, birds were released; their instinctual flight path directly toward the nearest continental landmass guided the helmsman to safety.",
    "summary_ta": "கப்பல்களில் திசைகாட்டும் காகங்களை கூண்டுகளில் வளர்த்து, நடுக்கடலில் திசை தெரியாதபோது அவற்றை வானில் பறக்கவிட்டு, அவை நிலத்தை நோக்கிப் பறக்கும் திசையைப் பின்பற்றி கரையை அடைந்த பண்டைய கடல்சார் உயிரி-வழிகாட்டல் நுட்பம்.",
    "sources": [
      "Digha Nikaya (Kevatta Sutta on Disa-kaka)",
      "Hornell: Coastal Navigation in South India",
      "Purananuru 238"
    ],
    "content": "---\nid: concept-direction-finding-shore-sighting-birds-disak-kaakkai-navigation\ntitle: Direction-Finding Shore-Sighting Birds & Avian Oceanic Navigation (Disak-Kaakkai)\ntype: concept\nera: Early Historic Era (c. 500 BCE - 300 CE)\nthinai: neithal (Bio-Navigation & Maritime Anthropology)\nstatus: canonical\n---\n\n# Direction-Finding Shore-Sighting Birds & Avian Oceanic Navigation (Disak-Kaakkai)\n\n## 1. Principles of Avian Shore Sighting\nBefore the invention of the magnetic mariner's compass, ancient Tamil sailors utilized the acute sensory biology of shore-dwelling land birds, principally the Indian house crow (*Corvus splendens* / *Disak-Kaakkai*).\n\nUnlike pelagic seabirds (such as shearwaters or petrels) which can alight and rest on ocean waves, land birds refuse to settle on water.\n\n## 2. Navigational Procedure\n1. When clouds or sea-fog obscured the sun and stars for days, a pilot released a caged crow from the ship's mast.\n2. The bird circled upward to gain altitude ($h \\approx 100 - 300\\text{ meters}$), extending its visible horizon:\n   $$d \\approx 3.57 \\sqrt{h} \\text{ km}$$\n3. If land lay within 50–70 km, the bird flew in an unwavering straight line toward the coast. The helmsman immediately steered the ship along the bird's flight azimuth.\n4. If no land was in sight, the exhausted bird returned to alight on the ship's rigging, signaling that the vessel was still in deep pelagic waters.\n"
  },
  {
    "file": "knowledge/concepts/concept-estuarine-sandbar-shoal-dynamics-and-tidal-surge-fluvial-drift.md",
    "slug": "concept-estuarine-sandbar-shoal-dynamics-and-tidal-surge-fluvial-drift",
    "category": "concept",
    "name_en": "Estuarine Sandbar Dynamics, Rivermouth Shoal Morphologies & Tidal Surge Navigation",
    "name_ta": "கழிமுக மணல்திட்டு நகர்வு, ஆற்றுவாய் நீரியல் மற்றும் கடல் அலை ஏற்ற வழிகாட்டல்",
    "era": "Early Historic Era",
    "year_start": -300,
    "year_end": 500,
    "thinai": "neithal",
    "summary_en": "The hydrodynamic knowledge possessed by Tamil estuarine pilots: reading river discharge velocities, seasonal monsoon longshore sand drift, and riding flood tidal surges across dangerous submerged sand spits to bring laden ships into protected lagoon docks.",
    "summary_ta": "ஆற்று நீரின் பாய்ச்சல், பருவமழைக் காலக் கடல் மணல் நகர்வு மற்றும் கடல் அலை ஏற்றத்தின் (பொங்குமுகம்) வேகத்தைக் கணித்து, ஆபத்தான மணல் திட்டுக்களைக் கடந்து கப்பல்களை உள்முகத் துறைமுகங்களில் சேர்த்த நீரியல் அறிவு.",
    "sources": [
      "Pattillach: Coastal Geomorphology of the Coromandel",
      "Rao: Progress and Prospects of Marine Archaeology in India"
    ],
    "content": "---\nid: concept-estuarine-sandbar-shoal-dynamics-and-tidal-surge-fluvial-drift\ntitle: Estuarine Sandbar Dynamics, Rivermouth Shoal Morphologies & Tidal Surge Navigation\ntype: concept\nera: Early Historic Era (c. 300 BCE - 500 CE)\nthinai: neithal (Fluvial Geomorphology & Estuarine Hydrodynamics)\nstatus: canonical\n---\n\n# Estuarine Sandbar Dynamics, Rivermouth Shoal Morphologies & Tidal Surge Navigation\n\n## 1. The Dynamic Coromandel Rivermouth Bar\nAlong the east coast of Tamil Nadu, longshore littoral drift transports millions of tons of quartz sand northward between March and October. \n\nAt river mouths (such as Poompuhar, Marakkanam, and Korkai), this sand forms a semi-permanent submerged barrier spit (*Kazi-thittu*):\n- Deep water on the ocean approach ($>10\\text{ m}$).\n- A shallow bar with depths dropping to less than $1.5\\text{ m}$ at low tide.\n- Deep, calm water inside the protected lagoon or estuary ($4 - 6\\text{ m}$).\n\n## 2. Riding the Flood Tide Surge (*Pongu-Mugam*)\nPilots timed the crossing of the bar precisely to coincide with **peak flood tide**:\n- The incoming tidal surge added 1.0 to 1.5 meters of additional depth over the bar.\n- Pilot crews in multiple oared skiffs lashed tow-lines to the vessel's bow and pulled vigorously in unison with the surging tide, skimming the keel over the sand crest into the tranquil inner harbor before the ebb tide set in.\n"
  },
  {
    "file": "knowledge/concepts/concept-nocturnal-bioluminescent-plankton-current-tracking-kadal-meruku.md",
    "slug": "concept-nocturnal-bioluminescent-plankton-current-tracking-kadal-meruku",
    "category": "concept",
    "name_en": "Nocturnal Marine Bioluminescence, Dinoflagellate Current Mapping & Rip Tide Tracking (Kadal-Meruku)",
    "name_ta": "இரவு நேரக் கடல் வெளிச்சம், உயிரி-ஒளிர்வு நீரோட்டக் கணிப்பு மற்றும் சுழல் அடையாளம்",
    "era": "Early Historic Era",
    "year_start": -300,
    "year_end": 500,
    "thinai": "neithal",
    "summary_en": "Nocturnal navigation using ocean bioluminescence (Kadal-Meruku): observing blue-green photon emission from sheared dinoflagellate colonies (Noctiluca scintillans) along wave crests and ship rudders to identify underwater reef boundaries, dangerous rip tides, and speed of oceanic currents.",
    "summary_ta": "இரவு நேரக் கடலில் நீல-பச்சை நிறத்தில் மின்னும் பாசி மற்றும் கடல்வாழ் நுண்ணுயிரிகளின் ஒளியை (கடல் மெருக்கு) உற்றுநோக்கி, ஆபத்தான பவளப்பாறைகள், நீரோட்டத்தின் வேகம் மற்றும் சுழல்களைக் கண்டறிந்த பண்டைய வழிகாட்டல் முறை.",
    "sources": [
      "Hastings: The Chemistry and Biology of Marine Bioluminescence",
      "Arunachalam: Indigenous Navigation in the Indian Ocean"
    ],
    "content": "---\nid: concept-nocturnal-bioluminescent-plankton-current-tracking-kadal-meruku\ntitle: Nocturnal Marine Bioluminescence, Dinoflagellate Current Mapping & Rip Tide Tracking (Kadal-Meruku)\ntype: concept\nera: Early Historic Era (c. 300 BCE - 500 CE)\nthinai: neithal (Bio-Oceanography & Night Navigation)\nstatus: canonical\n---\n\n# Nocturnal Marine Bioluminescence, Dinoflagellate Current Mapping & Rip Tide Tracking (Kadal-Meruku)\n\n## 1. The Phenomenon of Kadal-Meruku\nOn pitch-dark tropical nights, mechanical shear stress induced by waves, breaking shoals, and moving ship hulls triggers **bioluminescence** in millions of marine dinoflagellates (*Noctiluca scintillans*):\n$$\\text{Luciferin} + \\text{O}_2 \\xrightarrow{\\text{Luciferase}} \\text{Oxyluciferin} + h\\nu \\text{ (intense blue-green light, } \\lambda \\approx 470\\text{ nm)}$$\n\n## 2. Navigational Reading of Luminescence\nExperienced Tamil pilots utilized this glowing wake as a natural hydrographic display:\n1. **Shoal Warning**: When an invisible submerged sandbar or coral reef approached within 1–2 fathoms, turbulent ground-swells caused the water above the reef to glow with an intense, eerie luminescence, warning pilots to drop anchor.\n2. **Current Velocity**: The brightness and trail length of the luminescent wake streaming behind the steering oar (*Sukkaan*) allowed helmsmen to estimate ship speed and detect counter-flowing rip currents.\n"
  },
  {
    "file": "knowledge/characters/char-devipattinam-master-estuarine-pilot-kadal-kaan-thalaivan.md",
    "slug": "char-devipattinam-master-estuarine-pilot-kadal-kaan-thalaivan",
    "category": "character",
    "name_en": "Master Estuarine Harbor Pilot & Sea Warden: Kadal-Kaan Thalaivan of Devipattinam",
    "name_ta": "தேவிபட்டினம் தலைமை முகத்துவாரக் கப்பல் வழிகாட்டி மற்றும் கடல் காப்பாளர்",
    "era": "Pandya Classical Era",
    "year_start": 700,
    "year_end": 800,
    "thinai": "neithal",
    "summary_en": "The veteran Pandya harbor pilot of Devipattinam who commanded fleets of oared sounding skiffs, maintained deep channel markers across the Palk Bay, and steered international merchant vessels through shifting estuarine sandbars.",
    "summary_ta": "பாக் வளைகுடாவில் மணல் திட்டுக்கள் நிறைந்த பாதைகளில் கப்பல்களை வழிநடத்தி, நங்கூரத் தளங்களைப் பராமரித்த பாண்டியர் அரசவை தலைமைத் துறைமுக வழிகாட்டி.",
    "sources": [
      "Devipattinam Inscriptions",
      "Maritime History of South India"
    ],
    "content": "---\nid: char-devipattinam-master-estuarine-pilot-kadal-kaan-thalaivan\ntitle: Master Estuarine Harbor Pilot & Sea Warden: Kadal-Kaan Thalaivan of Devipattinam\ntype: character\nera: Pandya Classical Era (c. 700 - 800 CE)\nthinai: neithal (Harbor Pilotage & Guild Governance)\nstatus: canonical\n---\n\n# Master Estuarine Harbor Pilot & Sea Warden: Kadal-Kaan Thalaivan of Devipattinam\n\n## 1. Professional Office\nThe **Kadal-Kaan Thalaivan** held royal authority over the port entrance. No foreign or inland cargo vessel could cross the estuarine bar without his flag-signal and pilot crew aboard.\n\n## 2. Specialized Skills\n- Reading water surface color gradations (from pale sandy brown indicating 1 fathom to deep indigo indicating 10 fathoms).\n- Coordinating multi-skiff towing teams during spring flood tides.\n"
  },
  {
    "file": "knowledge/characters/char-pamban-strait-shallow-channel-navigator-neer-vazhi-kattuvon.md",
    "slug": "char-pamban-strait-shallow-channel-navigator-neer-vazhi-kattuvon",
    "category": "character",
    "name_en": "Pamban Strait Channel Helmsman & Reef Pilot: Neer-Vazhi Kattuvon",
    "name_ta": "பாம்பன் நீரிணைப் பவளப்பாறை வழிகாட்டி மற்றும் கடல் மாலுமி",
    "era": "Medieval Pandya to Chola Era",
    "year_start": 950,
    "year_end": 1050,
    "thinai": "neithal",
    "summary_en": "The elite shallow-water reef navigator stationed at the Pamban gap who guided Imperial Chola naval battle fleets and merchant vanguard ships through razor-sharp submerged sandstone reefs.",
    "summary_ta": "பாம்பன் நீரிணையின் ஆபத்தான பாறை இடுக்குகளில் சோழ கடற்படையின் பிரம்மாண்டக் கப்பல்களை விபத்தின்றிச் செலுத்திய தலைசிறந்த பவளப்பாறை வழிகாட்டி மாலுமி.",
    "sources": [
      "Pamban Maritime Epigraphs",
      "Nilakanta Sastri: The Colas (Naval Expeditions)"
    ],
    "content": "---\nid: char-pamban-strait-shallow-channel-navigator-neer-vazhi-kattuvon\ntitle: Pamban Strait Channel Helmsman & Reef Pilot: Neer-Vazhi Kattuvon\ntype: character\nera: Medieval Pandya to Chola Era (c. 950 - 1050 CE)\nthinai: neithal (Reef Pilotage & Naval Strategy)\nstatus: canonical\n---\n\n# Pamban Strait Channel Helmsman & Reef Pilot: Neer-Vazhi Kattuvon\n\n## 1. Navigational Genius\nNavigating the Pamban Reef required intimate knowledge of daily tidal harmonics, current reversals, and underwater passages barely wider than a ship's beam.\n\n## 2. Wartime Deployments\nDuring Rajendra Chola's naval mobilization toward Sri Lanka and Srivijaya, pilots of his guild steered hundreds of war ships through the narrow strait without losing a single rudder.\n"
  },
  {
    "file": "knowledge/places/place-devipattinam-ancient-estuarine-pilotage-haven.md",
    "slug": "place-devipattinam-ancient-estuarine-pilotage-haven",
    "category": "place",
    "name_en": "Devipattinam: Ancient Estuarine Pilotage Haven & Palk Bay Port",
    "name_ta": "தேவிபட்டினம் - பண்டைய முகத்துவாரக் கப்பல் வழிகாட்டல் துறைமுகம் மற்றும் பாக் வளைகுடா தளம்",
    "era": "Pandya Classical Era",
    "year_start": 500,
    "year_end": 1300,
    "thinai": "neithal",
    "summary_en": "Historic maritime harbor and pilgrim haven on the Palk Bay in southern Tamil Nadu, celebrated for sheltered calm-water roadsteads, submerged stone mooring arrays (Navapashanam), and expert coastal harbor pilots.",
    "summary_ta": "தென் தமிழகத்தில் பாக் வளைகுடாக் கரையில் அமைந்துள்ள வரலாற்றுச் சிறப்புமிக்க துறைமுகம்; அலைகளற்ற இயற்கை நங்கூரத் தளம் மற்றும் நவதானியக் கல் அமைப்புகளைக் கொண்ட பழம்பெரும் தளம்.",
    "sources": [
      "Ramanathapuram Gazetteer",
      "ASI Reports on Palk Bay Maritime Archaeology"
    ],
    "content": "---\nid: place-devipattinam-ancient-estuarine-pilotage-haven\ntitle: Devipattinam: Ancient Estuarine Pilotage Haven & Palk Bay Port\ntype: place\nera: Pandya Classical Era (c. 500 - 1300 CE)\nthinai: neithal (Maritime Geography & Harbor Topography)\nstatus: canonical\n---\n\n# Devipattinam: Ancient Estuarine Pilotage Haven & Palk Bay Port\n\n## 1. Geographical Protection\n**Devipattinam** (lat 9.4833° N, lng 78.9000° E) lies nestled in the crescent indentation of the Palk Bay, shielded from the violent southwest monsoon storms by the landmass of Rameswaram Island.\n\nIts calm, shallow waters served as the primary gathering roadstead where merchant ships congregated before entering the shallow Pamban channels.\n\n## 2. Nautical Infrastructure\nAncient Devipattinam maintained:\n- High timber beacon towers lighting coastal sand-dunes.\n- Outrigger pilot skiff fleets manned by hereditary Parathavar mariners.\n- Submerged stone bollard systems for safe overnight mooring.\n"
  }
]
EDGES = [
  [
    "text-akanunuru-maritime-pilotage-and-sandbar-sounding-poetry",
    "describes_estuarine_pilotage",
    "concept-bamboo-sounding-pole-and-lead-fathom-bathymetry-thandukal",
    "cultural",
    "Sangam Classical Era",
    "Akananuru poetry depicting pilots sounding shallow sandbars for ocean ships",
    "Akananuru 152"
  ],
  [
    "insc-devipattinam-pandya-harbor-pilot-and-mooring-charters",
    "records_pilotage_rights_at",
    "place-devipattinam-ancient-estuarine-pilotage-haven",
    "epigraphical",
    "Pandya Classical Era",
    "Pandya charters granting pilotage land tenures and mooring duties",
    "SII Vol. XIV"
  ],
  [
    "insc-pamban-strait-naval-channel-pilotage-epigraphs",
    "records_reef_pilots_near",
    "place-devipattinam-ancient-estuarine-pilotage-haven",
    "naval",
    "Medieval Pandya to Chola Era",
    "Inscriptions detailing channel pilots guiding fleets across sandstone reefs",
    "Epigraphia Indica XXXVI"
  ],
  [
    "concept-bamboo-sounding-pole-and-lead-fathom-bathymetry-thandukal",
    "detects_submerged_shoals_in",
    "concept-estuarine-sandbar-shoal-dynamics-and-tidal-surge-fluvial-drift",
    "hydrographic",
    "Early Historic Era",
    "Sounding poles and tallow-tipped leads mapping shifting deltaic spits",
    "Hornell 1920"
  ],
  [
    "concept-direction-finding-shore-sighting-birds-disak-kaakkai-navigation",
    "guides_vessels_toward",
    "place-devipattinam-ancient-estuarine-pilotage-haven",
    "navigational",
    "Early Historic Era",
    "Released coastal crows flying directly toward mainland harbor havens",
    "Kevatta Sutta"
  ],
  [
    "concept-nocturnal-bioluminescent-plankton-current-tracking-kadal-meruku",
    "alerts_pilots_to_reefs_in",
    "concept-estuarine-sandbar-shoal-dynamics-and-tidal-surge-fluvial-drift",
    "oceanographic",
    "Early Historic Era",
    "Dinoflagellate glowing wakes revealing underwater breaking bars at night",
    "Hastings 1996"
  ],
  [
    "char-devipattinam-master-estuarine-pilot-kadal-kaan-thalaivan",
    "commanded_pilotage_at",
    "place-devipattinam-ancient-estuarine-pilotage-haven",
    "social",
    "Pandya Classical Era",
    "Chief harbor pilot directing sounding skiffs and towing incoming ships",
    "Devipattinam Inscriptions"
  ],
  [
    "char-pamban-strait-shallow-channel-navigator-neer-vazhi-kattuvon",
    "steered_naval_fleets_through",
    "concept-bamboo-sounding-pole-and-lead-fathom-bathymetry-thandukal",
    "naval",
    "Medieval Pandya to Chola Era",
    "Master reef navigator steering royal warships through narrow sandstone gaps",
    "The Colas"
  ],
  [
    "char-devipattinam-master-estuarine-pilot-kadal-kaan-thalaivan",
    "timed_tidal_crossings_in",
    "concept-estuarine-sandbar-shoal-dynamics-and-tidal-surge-fluvial-drift",
    "technological",
    "Pandya Classical Era",
    "Riding peak flood tide surges to skim keels over shallow rivermouth bars",
    "Pattillach 1992"
  ],
  [
    "concept-nocturnal-bioluminescent-plankton-current-tracking-kadal-meruku",
    "praised_in_sangam_verse",
    "text-akanunuru-maritime-pilotage-and-sandbar-sounding-poetry",
    "cultural",
    "Sangam Classical Era",
    "Sangam descriptions of phosphorescent ocean wakes and night navigation",
    "Maduraikkanji"
  ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Batch 22 Corpus 2: Coastal Marine Pilotage & Navigation into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Batch 22 Corpus 2: Coastal Marine Pilotage & Navigation Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
