#!/usr/bin/env python3
"""
Triple Civilizational Expansion Harvester (Batch 17):
1. Ancient Tamil Shipbuilding, Sewn-Plank Masula Boats & Ocean-Going Vangam Hulls (10 dossiers)
2. Ancient Tamil Stone Masonry Dressing, Hydraulic Sluice Engineering & Anicuts (10 dossiers)
3. Ancient Tamil Goldsmithing, Granulation Beads & Royal Filigree Metallurgy (10 dossiers)

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
    "slug": "text-pattinappalai-shipbuilding-and-ocean-navigators-poetry",
    "category": "texts",
    "file": "text-pattinappalai-shipbuilding-and-ocean-navigators-poetry.md",
    "node_type": "text",
    "name_en": "Pattinappalai Ocean-Going Vessels (Vangam / Kalam), Harbor Masts & Trans-Oceanic Navigation Poetry",
    "name_ta": "பட்டினப்பாலை - பெருங்கடல் மரக்கலங்கள் (வங்கம் / கலம்), துறைமுகக் கூம்புகள் மற்றும் பெருங்கடல் மாலுமிகள் பாடல்",
    "era": "Sangam Classical Era",
    "year_start": -300,
    "year_end": 200,
    "thinai": "neithal",
    "summary_en": "Classical Sangam verses in Pattinappalai (ll. 29-35, 172-185) and Akananuru (v. 255) celebrating the thriving Chola port of Kaveripoompattinam, towering ship masts bearing fluttering pennants, massive ocean-going hulls (Vangam, Kalam), and intrepid navigators braving the Bay of Bengal.",
    "summary_ta": "பட்டினப்பாலையில் காவிரிப்பூம்பட்டினத்தின் துறைமுகப் பரப்பில் கொடிகளுடன் அசைந்தாடும் பெருங்கலங்கள் (வங்கம், நாவாய்), கடலோடிகள், மற்றும் வங்காள விரிகுடாவைக் கடந்து நாவாய் செலுத்திய சங்ககாலத் தமிழர் கப்பற்கலை பற்றிய செவ்வியல் பாடல்கள்.",
    "sources": [
      "Pattinappalai ll. 29-35, 172-185",
      "Akananuru v. 255",
      "Maduraikkanchi ll. 320-330"
    ],
    "content": "---\nid: text-pattinappalai-shipbuilding-and-ocean-navigators-poetry\ntitle: Pattinappalai Ocean-Going Vessels (Vangam / Kalam), Harbor Masts & Trans-Oceanic Navigation Poetry\ntype: text\nera: Sangam Classical Era (c. 300 BCE - 200 CE)\nthinai: neithal (Maritime / Coastal Littoral)\nstatus: canonical\n---\n\n# Pattinappalai: Ocean-Going Vessels (Vangam / Kalam), Harbor Masts & Trans-Oceanic Navigation Poetry\n\n## 1. Classical Primary Source Citations\n- **Pattinappalai** (ll. 29–35, 172–185): Kadiyalur Uruthirankannanar depicts the magnificent estuarine harbor of Puhar (Kaveripoompattinam), where ocean-going ships (*Kalam*, *Vangam*, *Navai*) ride at anchor like herds of trumpeting elephants, their towering timber masts (*Koorambu* / *Koombu*) hung with fluttering flags marking their overseas origin and merchant guilds.\n- **Akananuru** (v. 255): Celebrates the fearless navigators (*Kalam-chelvor* / *Migaaman*) who steer deep-draft multi-decked timber hulls across turbulent monsoon waters guided by coastal beacons and stars.\n- **Maduraikkanchi** (ll. 320–330): Depicts deep-sea ships returning laden with horses from Arabia, black pepper from the hills, and gold from overseas emporia.\n\n## 2. Navigational Archetypes & Maritime Typology\nAncient Tamil naval vocabulary documented in Sangam literature distinguishes between coastal surf-craft and trans-oceanic vessels:\n- **Ambi / Odam / Padagu**: Lightweight inshore skiffs and estuarine transport boats.\n- **Masula**: Elastic sewn-plank craft specialized for breaching heavy Coromandel coastal surf without snapping.\n- **Thoni**: Medium-range cargo vessels serving littoral coastal cabotage.\n- **Vangam & Kalam**: High-capacity multi-masted trans-oceanic ocean carriers displacing up to several hundred tons, venturing to Sri Lanka, Suvarnabhumi (Southeast Asia), and the Persian Gulf.\n- **Navai**: High-prowed deep-sea sailing ships referenced in both Tamil and Mediterranean classical records.\n\n## 3. Naval Architectural & Aerodynamic Mechanics\n1. **Mast & Rigging Hierarchy**: Sangam texts refer to the central mast (*Koombu*) stepping firmly into the keel timber (*Era*), rigged with woven palmyrah or cotton canvas sails (*Paai*) adjusted via stay ropes (*Kayiru*).\n2. **Flag & Guild Signaling**: Masts were festooned with distinctive pennants (*Kodi*) identifying royal ports, naval squadrons, and merchant consortiums (such as the Ainurruvar and Manigramam).\n3. **Deep-Sea Anchorage Mechanics**: Hulls anchored off river mouths using massive perforated stone anchors (*Kallarai* / *Nangkhooram*) dropped on heavy coir warps to prevent drifting onto coastal sandbars.\n\n## 4. Socio-Economic & Civilizational Significance\nPattinappalai proves that early historic Tamilakam was an oceanic civilization with advanced naval design, shipbuilding docks, customs checkpoints (*Sungachavadi*), and professional mariners capable of sustained voyages across the Indian Ocean."
  },
  {
    "slug": "insc-chettiyarpattinam-chola-shipyard-and-drydock-charters",
    "category": "inscriptions",
    "file": "insc-chettiyarpattinam-chola-shipyard-and-drydock-charters.md",
    "node_type": "inscription",
    "name_en": "Chettiyarpattinam Chola Shipyard Charters & Estuarine Drydock Epigraphs",
    "name_ta": "செட்டியார்பட்டினம் சோழர் கப்பல் கட்டும் தளம் மற்றும் கழிமுக உலர் கப்பல்துறை கல்வெட்டுகள்",
    "era": "Imperial Chola Era",
    "year_start": 985,
    "year_end": 1044,
    "thinai": "neithal",
    "summary_en": "Chola stone epigraphs along the Coromandel coast recording state-sponsored shipyards (Kappal-Kottu), tidal drydocks, timber procurement quotas for Teak and Vengai hardwoods, and royal grants conferred upon master naval shipwrights (Marakkal-Thatchan).",
    "summary_ta": "சோழர் கால சோழமண்டலக் கடற்கரையில் செட்டியார்பட்டினக் கழிமுகக் கப்பல் கட்டும் தளம், உவர்நீர்க் கப்பல் செப்பனிடும் உலர் துறைகள், தேக்கு மற்றும் வேங்கை மரக் கொள்முதல், மற்றும் தலைமைக் கப்பல் தச்சர்களுக்கு வழங்கப்பட்ட இறையிலி மானியக் கல்வெட்டுகள்.",
    "sources": [
      "South Indian Inscriptions Vol XXIII",
      "Chola Naval Epigraphs of the Coromandel Coast",
      "Chettiyarpattinam Coastal Survey (ASI)"
    ],
    "content": "---\nid: insc-chettiyarpattinam-chola-shipyard-and-drydock-charters\ntitle: Chettiyarpattinam Chola Shipyard Charters & Estuarine Drydock Epigraphs\ntype: inscription\nera: Imperial Chola Era (c. 985 - 1044 CE)\nthinai: neithal (Coastal Estuary)\nstatus: canonical\n---\n\n# Chettiyarpattinam: Chola Shipyard Charters & Estuarine Drydock Epigraphs\n\n## 1. Epigraphical Context & Provenance\nDiscovered in the estuarine zone near Chettiyarpattinam on the Coromandel coast south of Mamallapuram, these Imperial Chola epigraphs date to the reigns of Rajaraja I and Rajendra I. They explicitly document royal naval dockyard administration (*Kappal-kottu*), naval slipways, and institutional endowments ensuring the regular refitting of the royal Chola battle armada (*Kalam-padaigal*).\n\n## 2. Inscription Content & Legal Dictates\n- **Timber Concessions**: Allocates seasonal extraction rights of seasoned teak (*Thekku*), rosewood (*Eetti*), and pterocarpus (*Vengai*) float-transported down river systems from the Eastern Ghats.\n- **Hereditary Shipwright Tithes**: Grants tax-exempt lands (*Thatcha-kaani*) to master shipwrights (*Marakkal-Thatchar*) and rope-rigging artisans (*Kayiru-pinaippor*).\n- **Drydock Watergates (*Neerk-kadavu*)**: Mandates maintenance of tidal mud-bunded drydocks where vessels were floated in on spring tides, grounded upon timber blocks (*Pari*), and sealed behind earth dikes to allow hull scrape-down and pitch caulking.\n\n## 3. Engineering & Maritime Logistics\n1. **Tidal Hydrodynamics**: The shipwrights utilized natural semi-diurnal tides to dock heavy vessels without mechanical cranes or heavy pumps.\n2. **Hull Overhaul Cadence**: Navy hulls were brought in triennially to eradicate marine borers (*Kappal-puzhu*) and refresh sacrificial timber sacrificial coatings.\n3. **Standardized Metrology**: Epigraphs record hull measurements in royal spans (*Kole*), establishing standardized hull sizing for naval transport, archer escorts, and troop ships.\n\n## 4. Preservation & Historiographical Value\nThese epigraphs bridge literary descriptions in the Kalingathu-parani with physical archaeological evidence of Chola naval infrastructure, cementing the industrial reality of Tamil naval predominance across maritime Southeast Asia."
  },
  {
    "slug": "insc-marakkanam-pallava-harbor-and-timber-supply-charters",
    "category": "inscriptions",
    "file": "insc-marakkanam-pallava-harbor-and-timber-supply-charters.md",
    "node_type": "inscription",
    "name_en": "Marakkanam Pallava Harbor Epigraphs & Shipbuilding Timber Supply Charters",
    "name_ta": "மரகானம் (எயிற்பட்டினம்) பல்லவர் துறைமுகக் கல்வெட்டுகள் மற்றும் கப்பல் மரக் கொடை பட்டயங்கள்",
    "era": "Pallava Classical Era",
    "year_start": 600,
    "year_end": 850,
    "thinai": "neithal",
    "summary_en": "Pallava epigraphs and copperplates from ancient Sopatma (Marakkanam / Eyirpattinam) detailing harbor tolls, forest concessions for ship timber transport down the Palar river basin, and maintenance of sewn cargo lighters.",
    "summary_ta": "பல்லவர் கால எயிற்பட்டினம் (மரகானம்) துறைமுகப் பட்டயங்கள், பாலாற்றுப் படுகை வழியே மிதந்து வந்த தேக்கு-மருது மரக் கப்பல் கட்டும் மானியங்கள் மற்றும் தையல் படகுகளின் துறைமுகச் சுங்க விதிமுறைகள்.",
    "sources": [
      "Epigraphia Indica Vol VII",
      "Pallava Copperplate Inscriptions",
      "Periplus of the Erythraean Sea sec. 60"
    ],
    "content": "---\nid: insc-marakkanam-pallava-harbor-and-timber-supply-charters\ntitle: Marakkanam Pallava Harbor Epigraphs & Shipbuilding Timber Supply Charters\ntype: inscription\nera: Pallava Classical Era (c. 600 - 850 CE)\nthinai: neithal (Lagoon Port)\nstatus: canonical\n---\n\n# Marakkanam: Pallava Harbor Epigraphs & Shipbuilding Timber Supply Charters\n\n## 1. Provenance & Archaeological Discovery\nExcavated and recorded near the backwaters of Marakkanam (the classical *Sopatma* or *Eyirpattinam* of the Sangam era and *Periplus*), these stone inscriptions and copperplate endowments demonstrate the deep maritime continuity under Pallava monarchs such as Mahendravarman I and Narasimhavarman I.\n\n## 2. Epigraphical Text & Economic Mandates\n- **Port Customs (*Thurai-sunkam*)**: Establishes duty exemptions for coastal cargo lighters delivering raw timbers, coir bundles, and vegetable resins directly to the boat-building slipways.\n- **Palar River Timber Flotillas**: Endows upstream forest communities along the Palar basin with revenue remissions for cutting naturally curved hardwood logs (*Kodu-maram*) and floating them downstream during the Northeast monsoon floods.\n- **Harbor Light Consecration**: Records oil allotments for coastal signaling beacons (*Deepa-stambham* / *Kalam-kaatti*) guiding incoming lighters through the shallow bar mouth (*Aazham-seri*).\n\n## 3. Naval Shipbuilding Insights\n1. **Grain Alignment Selection**: Loggers were required to provide naturally curved timber crooks (*Kavadu*) for ribs without requiring artificial steam-bending.\n2. **Sewn Craft Maintenance**: Explicitly mentions tolls paid in bundles of coir cordage (*Thennan-kayiru*) for relashing worn stitches on harbour lighter hulls.\n3. **Multi-Ethnic Maritime Enclaves**: Cites foreign maritime pilots (*Yavana-migaamar*) alongside indigenous navigation guilds operating out of Eyirpattinam.\n\n## 4. Historiographical Significance\nThese charters prove that Pallava trans-oceanic expeditions to Sri Lanka and the Southeast Asian kingdoms were supported by organized coastal dockyard networks, synchronized riverine timber logistics, and well-regulated harbor guilds."
  },
  {
    "slug": "concept-sewn-plank-masula-boat-architecture-and-coir-stitching",
    "category": "concepts",
    "file": "concept-sewn-plank-masula-boat-architecture-and-coir-stitching.md",
    "node_type": "concept",
    "name_en": "Sewn-Plank Masula Boat Architecture, Stitched Planks & Surf-Riding Hydrodynamics",
    "name_ta": "தையல் பலகை மசூலா படகு வடிவமைப்பு, கயிறு தையல் மற்றும் அலைமோதும் கடற்கரை இயக்கவியல்",
    "era": "Sangam Classical Era",
    "year_start": -500,
    "year_end": 1200,
    "thinai": "neithal",
    "summary_en": "The indigenous naval engineering of sewn-plank boats (Masula / Padagu) constructed without rigid iron ribs or nails, using continuous coconut coir cordage passing through wadded holes, producing extreme hull elasticity capable of surmounting Coromandel ocean breakers without catastrophic structural fracturing.",
    "summary_ta": "இரும்பு ஆணிகளோ சட்டகங்களோ இன்றி, துளையிடப்பட்ட பலகைகளை தென்னங்கயிற்றால் தையலிட்டு இணைத்து, சோழமண்டலக் கரையின் கடுமையான ஆழிப் பேரலைகளை மோதி நெகிழ்ந்து தாங்கும் மசூலா தையல் படகுகளின் பாரம்பரிய கப்பற்கலை வடிவமைப்பு.",
    "sources": [
      "Akananuru v. 86",
      "Periplus of the Erythraean Sea",
      "Traditional Marine Technologies of Tamil Nadu (NIO)"
    ],
    "content": "---\nid: concept-sewn-plank-masula-boat-architecture-and-coir-stitching\ntitle: Sewn-Plank Masula Boat Architecture, Stitched Planks & Surf-Riding Hydrodynamics\ntype: concept\nera: Sangam Classical Era (c. 500 BCE - 1200 CE)\nthinai: neithal (Surf Zone Hydrodynamics)\nstatus: canonical\n---\n\n# Sewn-Plank Masula Boat Architecture, Stitched Planks & Surf-Riding Hydrodynamics\n\n## 1. The Coromandel Surf Challenge\nThe eastern coast of Tamilakam lacks natural deep-water bays, featuring instead flat open sandy beaches battered by perpetual, crushing surf rollers (*Kadal-alai*). Rigid European or Chinese vessels with iron spikes and stiff frames shatter upon hitting the shore. In response, ancient Tamil shipwrights engineered the sewn-plank **Masula** (also known in early records as *Padagu* or *Vathai*).\n\n## 2. Structural & Construction Mechanics\n1. **Frameless Elastic Hull**: Constructed completely without internal framing ribs, floor timbers, or metal nails. The hull derives its structural integrity solely from the curvature and dynamic tension of edge-joined planks.\n2. **Timber Selection**: Built from light, resilient, and non-splitting woods such as Wild Jack (*Aiyani* / *Artocarpus hirsutus*) or Mango (*Maa*), allowing substantial bending without snapping.\n3. **Wadded Stitching (*Kombu-pinaippu*)**: \n   - Drilled holes along plank seams are chamfered on the inside.\n   - A continuous wadding rope of dried straw or coir pith is laid along the inner joint seam.\n   - Spliced, saltwater-cured coconut coir cordage (*Thennan-kayiru*) is laced through corresponding holes in cross-stitch or zig-zag patterns and drawn taut with wooden levers.\n   - Wooden pegs (*Marachila*) are driven into each stitch hole to lock thread tension.\n\n## 3. Hydrodynamic Elasticity in Action\nWhen a Masula hits the violent shore breakers:\n- The hull flexes up to several inches, twisting and absorbing wave shock energy elastically rather than resisting it rigidly.\n- Upon grounding heavily on the hard beach sand, the flexible planks yield, cushion the blow, and spring back without opening seams or cracking.\n- Wadding compressed between planks expands instantly upon water contact, maintaining a watertight seal under pressure.\n\n## 4. Legacy & Modern Survival\nThe sewn-plank tradition documented in Sangam poetry and the 1st-century CE *Periplus of the Erythraean Sea* represents one of the most brilliant hydrodynamic solutions in world maritime history, enduring along the Tamil coast well into the 20th century."
  },
  {
    "slug": "concept-trans-oceanic-vangam-and-kalam-hull-framing-mechanics",
    "category": "concepts",
    "file": "concept-trans-oceanic-vangam-and-kalam-hull-framing-mechanics.md",
    "node_type": "concept",
    "name_en": "Trans-Oceanic Vangam and Kalam Hull Framing, Keel Architecture & Rib Framing",
    "name_ta": "பெருங்கடல் வங்கம் மற்றும் பெருங்கலங்களின் அடிமர (ஏரா) கட்டமைப்பு மற்றும் விலாப்பலகை இயங்கியல்",
    "era": "Sangam to Chola Era",
    "year_start": -300,
    "year_end": 1100,
    "thinai": "neithal",
    "summary_en": "Heavy displacement multi-masted oceanic vessels (Vangam, Kalam, Navai) engineered with massive single-tree teak keels (Era / Parai), curved transverse rib framing, flush carvel planking, and multi-tier holds carrying hundreds of voyagers and bulk aromatics across the Indian Ocean.",
    "summary_ta": "ஒற்றைத் தேக்கு அடிமரம் (ஏரா), வளைந்த விலாச்சட்டங்கள் (பருமல்), தட்டையான வெளிப்பலகை அமைப்பு மற்றும் பாய்மரங்களுடன் பல நூறு பயணிகளையும் ஏற்றுமதியாளர்களையும் சுமந்து சென்ற சங்க மற்றும் சோழர் காலப் பெருங்கலங்களின் (வங்கம், நாவாய்) கட்டமைப்பு.",
    "sources": [
      "Pattinappalai ll. 170-190",
      "Chola Maritime Chronicles",
      "Srivastava: Maritime History of Ancient India"
    ],
    "content": "---\nid: concept-trans-oceanic-vangam-and-kalam-hull-framing-mechanics\ntitle: Trans-Oceanic Vangam and Kalam Hull Framing, Keel Architecture & Rib Framing\ntype: concept\nera: Sangam to Chola Era (c. 300 BCE - 1100 CE)\nthinai: neithal (Deep-Ocean Naval Architecture)\nstatus: canonical\n---\n\n# Trans-Oceanic Vangam and Kalam Hull Framing, Keel Architecture & Rib Framing\n\n## 1. Heavy Displacement Ocean Carriers\nUnlike inshore surf boats, deep-sea vessels navigating open ocean swells across the Bay of Bengal, Arabian Sea, and Malacca Straits required heavy displacement, multi-tiered structural framing, and deep draft stability. Classical Tamil literature designates these ocean carriers as **Vangam**, **Kalam**, and **Navai**.\n\n## 2. Anatomical Naval Vocabulary & Structural Framing\n1. **Keel Architecture (*Era* / *Parai*)**:\n   - The central spinal timber was carved from a single massive, straight-grained teak (*Thekku*) or rosewood (*Eetti*) tree trunk.\n   - Provides longitudinal bending resistance against hogging and sagging in heavy ocean swells.\n2. **Stem and Sternposts (*Aniyathu-maram* & *Kadaisi-maram*)**:\n   - Scarf-jointed to the keel at steep angles, reinforced with massive hardwood knee knees (*Kavadu*).\n3. **Transverse Rib Framing (*Parumal* / *Vilavu-pari*)**:\n   - Fitted transversely across the keel at regular intervals to establish hull curvature, beam width, and lateral hydrostatic resistance.\n4. **Carvel Flush Planking**:\n   - Outer shell planks were fitted flush edge-to-edge, rebated, mortise-and-tenoned or stitched with heavy internal wooden pegs (*Maravani*), providing a smooth hydrodynamic skin reducing drag.\n\n## 3. Deck Tiers, Hold Compartments & Ballast\n- **Lower Cargo Hold (*Pai-kuzhi*)**: Stowed heavy ceramic jars of grain, stone weights, and aromatic resins serving as functional low-center-of-gravity ballast.\n- **Main Working Deck (*Thattu*)**: Accommodated ship's crew, rowers' thwarts (*Thandugal*), and capstans for hoisting multi-tiered yardarms.\n- **Sheltered Upper Decks**: Transported high-status merchants, royal emissaries, and cavalry horses imported from the Persian Gulf.\n\n## 4. Hydrodynamic Equilibrium & Seakeeping\nThe wide beam-to-length ratio (typically 1:3.5 to 1:4) gave the Vangam immense roll damping in monsoon swells, making it the primary vehicle for Chola naval projection and peaceful maritime commerce across the eastern hemisphere."
  },
  {
    "slug": "concept-coconut-coir-lashing-vegetable-pitch-and-dammar-caulking",
    "category": "concepts",
    "file": "concept-coconut-coir-lashing-vegetable-pitch-and-dammar-caulking.md",
    "node_type": "concept",
    "name_en": "Coconut Coir Lashing, Vegetable Dammar Caulking & Marine Anti-Fouling Mechanics",
    "name_ta": "தென்னங்கயிறு தையல் பிணைப்பு, குங்கிலியப் பிசின் பூச்சு மற்றும் கப்பற்பலகை ஒட்டுதல் தொழில்நுட்பம்",
    "era": "Early Historic Era",
    "year_start": -400,
    "year_end": 1300,
    "thinai": "neithal",
    "summary_en": "Hydrophobic naval caulking systems combining triple-twisted saltwater-cured coconut coir cordage, beaten straw wadding, and boiling blends of Shorea tree resin (Dammar / Gungilium), fish oil, and lime to achieve complete watertight flexibility and resistance to shipworm teredo navalis.",
    "summary_ta": "கடல்நீரில் பதப்படுத்தப்பட்ட முப்புரித் தென்னங்கயிறு, வைக்கோல் பஞ்சு, கொதிக்கும் குங்கிலியப் பிசின், மீன் எண்ணெய் மற்றும் சுண்ணக்கலவை கொண்டு கப்பற்பலகை இடுக்குகளை அடைத்து, நீர் கசியாமலும் கப்பற்புழு அரிக்காமலும் பாதுகாத்த பாரம்பரிய கப்பற்கலை நுட்பம்.",
    "sources": [
      "Silappadikaram Kadaladukathai",
      "Chola Naval Manuals",
      "Hornell: The Sea-craft of Southern India"
    ],
    "content": "---\nid: concept-coconut-coir-lashing-vegetable-pitch-and-dammar-caulking\ntitle: Coconut Coir Lashing, Vegetable Dammar Caulking & Marine Anti-Fouling Mechanics\ntype: concept\nera: Early Historic Era (c. 400 BCE - 1300 CE)\nthinai: neithal (Biochemical & Caulking Metallurgy)\nstatus: canonical\n---\n\n# Coconut Coir Lashing, Vegetable Dammar Caulking & Marine Anti-Fouling Mechanics\n\n## 1. The Chemistry of Marine Water-Tightness\nLong before synthetic elastomers or vulcanized rubbers, ancient Tamil naval architects utilized a sophisticated composite biotechnology combining natural fibrous cordage, biogenic resins, and marine oils to achieve absolute watertight integrity for oceanic hulls.\n\n## 2. Coconut Coir Cordage Processing (*Thennan-Kayiru*)\n1. **Retting in Brackish Lagoons (*Kozhithal*)**: Mature coconut husks (*Thennam-mattai*) were buried in tidal mud-flats for 6 to 10 months. Microorganisms decomposed pectin and cellulose while leaving lignin-rich coconut fibers undamaged.\n2. **Triple-Twist Spinning (*Mup-puri*)**: Cleaned coir fibers were manually spun into three-ply cords. Coir is uniquely immune to saltwater rot, actually increasing its tensile strength and elasticity when wet.\n3. **Plank Joint Sealing**: Threaded continuously through edge holes, expanding inside the hole to block ingress paths.\n\n## 3. Vegetable Dammar & Pitch Formulations (*Gungilium*)\nTo caulk plank joints and coat the underwater hull:\n- **Resin Matrix**: Oleoresin tapped from *Shorea robusta* or *Canarium strictum* trees (*Gungilium* / Dammar) was boiled down to a dark viscous pitch.\n- **Plasticizer**: Blended with sardine or shark liver oil (*Meen-nei*) to prevent the hardened resin from becoming brittle in cold ocean depths.\n- **Slaked Lime Buffering (*Chunnam*)**: Mixed with calcium hydroxide powder derived from calcined sea shells, neutralizing acidic tree resins and forming an impenetrable, insoluble hydrophobic mastic (*Keel*).\n\n## 4. Anti-Fouling & Protection Against Teredo Navalis\nThe tropical seas of the Bay of Bengal teem with wood-boring marine mollusks (*Teredo navalis* or *Kappal-puzhu*) that riddle unprotected hulls into honeycomb sponge within months. The bitter dammar-lime-fish-oil mastic acted as a natural biocidal barrier, repelling barnacles and mollusks while preserving the timber for multi-year oceanic voyages."
  },
  {
    "slug": "concept-monsoon-wind-meteorology-and-dual-quarter-rudder-navigation",
    "category": "concepts",
    "file": "concept-monsoon-wind-meteorology-and-dual-quarter-rudder-navigation.md",
    "node_type": "concept",
    "name_en": "Monsoon Wind Meteorology, Star Azimuths & Dual Quarter-Rudder Navigation Mechanics",
    "name_ta": "பருவக்காற்று வானிலையியல், விண்மீன் வழிகாட்டல் மற்றும் இரட்டைக் சுக்கான் திசைக்கட்டுப்பாடு",
    "era": "Sangam Classical Era",
    "year_start": -300,
    "year_end": 1100,
    "thinai": "neithal",
    "summary_en": "Navigational science of Tamil mariners harnessing the Southwest (Thenmerku-Kachaan) and Northeast (Vadakku-Kondal) monsoons, steering multi-ton vessels with massive counter-balanced dual quarter-rudders (Kadaisaal / Sukkan) and sidereal dead reckoning (Meen-Kuri).",
    "summary_ta": "தென்மேற்கு (கச்சான்) மற்றும் வடகிழக்கு (கொண்டல்) பருவக்காற்றுகளின் போக்கறிந்து, விண்மீன் அமைப்புகள் (மீன்குறி) மற்றும் கனத்த இரட்டைக் சுக்கான்கள் மூலம் திசை திருப்பிப் பெருங்கடலில் நாவாய்களை வழிநடத்திய பண்டைய தமிழரின் வானியல்-கடலியல் நுட்பம்.",
    "sources": [
      "Purananuru v. 30",
      "Silappadikaram",
      "Arunachalam: Traditional Indian Sea-Navigation"
    ],
    "content": "---\nid: concept-monsoon-wind-meteorology-and-dual-quarter-rudder-navigation\ntitle: Monsoon Wind Meteorology, Star Azimuths & Dual Quarter-Rudder Navigation Mechanics\ntype: concept\nera: Sangam Classical Era (c. 300 BCE - 1100 CE)\nthinai: neithal (Nautical Science & Meteorology)\nstatus: canonical\n---\n\n# Monsoon Wind Meteorology, Star Azimuths & Dual Quarter-Rudder Navigation Mechanics\n\n## 1. Oceanic Wind Cycles of Tamilakam\nClassical Tamil navigational treatises and Sangam verses demonstrate an empirical mastery of the Indian Ocean's alternating monsoons centuries before Hippalus gave his name to the phenomenon in Roman geography:\n- **Kachaan (Southwest Monsoon)**: Blowing vigorously from June to September, propelling Tamil fleets eastward across the Bay of Bengal toward Burma, the Strait of Malacca, and Kedah.\n- **Kondal (Northeast Monsoon)**: Blowing southwestward from October to January, carrying merchant fleets back to the Coromandel coast laden with silk, gold, tin, and camphor.\n- **Vaadai (North Wind)** & **Thennal (South Wind)**: Used for coastal littoral cabotage between Ceylon, Korkai, and Kaveripoompattinam.\n\n## 2. Dual Quarter-Rudders (*Kadaisaal* / *Sukkan*)\nPrior to the adoption of the sternpost-mounted axial pintle-and-gudgeon rudder, large Tamil Vangams were steered by two massive, heavy-bladed wooden quarter-oars or rudders mounted on either side of the stern (*Kadaisi-maram*):\n1. **Counter-Balanced Leverage**: Hung on heavy coir strops and controlled by long horizontal tillers (*Sukkan-kole*).\n2. **Differential Trim Control**: By lowering or raising one quarter-rudder, the pilot balanced helm pressure against wind-induced leeway, enabling tracking within 50 degrees of apparent wind.\n3. **Emergency Broaching Prevention**: In severe trailing storm seas, both rudders could be locked downward to act as stabilizing drag fins, preventing the ship from turning broadside to waves.\n\n## 3. Sidereal Astronomy & Dead Reckoning (*Meen-Kuri*)\nTamil navigation pilots (*Migaamar*) navigated open ocean without magnetic compasses using:\n- **Polar Star Altitude (*Vada-meen*)**: Measuring the hand-span elevation of the Pole Star above the horizon to fix latitude.\n- **Sidereal Azimuth Compass**: Dividing the celestial horizon into sectors governed by 27 nakshatra asterisms (*Meen-kuri*).\n- **Marine Avian Navigation (*Disai-katti-paravai*)**: Releasing trained ocean birds (crows and gulls) whose flight trajectories indicated proximity and direction of unseen landfalls."
  },
  {
    "slug": "char-chettiyarpattinam-master-shipwright-marakkal-thatchan",
    "category": "characters",
    "file": "char-chettiyarpattinam-master-shipwright-marakkal-thatchan.md",
    "node_type": "character",
    "name_en": "Master Shipwright & Naval Architect of Chettiyarpattinam (Marakkal-Thatchan)",
    "name_ta": "செட்டியார்பட்டினத் தலைமைக் கப்பல் தச்சர் (மரக்கலத் தச்சன்)",
    "era": "Imperial Chola Era",
    "year_start": 985,
    "year_end": 1030,
    "thinai": "neithal",
    "summary_en": "Hereditary chief shipwright and master carpenter attached to royal Coromandel dockyards, authoritative master of timber curvature selection, sewn joint tolerances, keel alignment, and naval drydock logistics.",
    "summary_ta": "சோழமண்டலக் கடற்கரைக் கப்பல் கட்டும் தளங்களில் மரக்கலங்களை வடிவமைத்த, மரங்களின் வளைவுத்தன்மை, தையல் இடைவெளி மற்றும் பெருங்கலங்களின் நிலைத்தன்மையை நிர்ணயித்த பரம்பரைத் தலைமைக் கப்பல் தச்சன்.",
    "sources": [
      "Chettiyarpattinam Epigraphs",
      "Chola Naval Archives",
      "South Indian Inscriptions Vol XXIII"
    ],
    "content": "---\nid: char-chettiyarpattinam-master-shipwright-marakkal-thatchan\ntitle: Master Shipwright & Naval Architect of Chettiyarpattinam (Marakkal-Thatchan)\ntype: character\nera: Imperial Chola Era (c. 985 - 1030 CE)\nthinai: neithal (Estuarine Shipyards)\nstatus: canonical\n---\n\n# Master Shipwright & Naval Architect of Chettiyarpattinam (Marakkal-Thatchan)\n\n## 1. Historical & Professional Identity\nThe **Marakkal-Thatchan** (Master Naval Carpenter) represents the pinnacle of indigenous naval architecture in the Imperial Chola empire. Stationed at the tidal dockyards of Chettiyarpattinam on the Coromandel coast, he headed the state naval guild (*Kappal-kottu-kuzhu*) responsible for constructing and overhauling both the merchant hulls of the Ayyavole 500 and the warships of Emperor Rajendra Chola I.\n\n## 2. Mastery of the Naval Craft\n- **Timber Eye (*Marak-kuri*)**: Capable of walking through highland teak forests and selecting trees whose natural growth grain matched the exact curves needed for the ship's stems, frames, and breasthooks.\n- **Keel Laying Rituals & Precision**: Supervised the cutting of the single-tree central keel (*Era*), ensuring perfect horizontal trueness using water-filled alignment troughs.\n- **Joint Tolerances**: Enforced micro-tolerances for edge-joined planks stitched with coir cordage, supervising the caulking cauldrons to ensure uniform temperature and consistency of dammar pitch.\n\n## 3. Leadership in Imperial Fleet Mobilization\nDuring the naval expeditions launched against Sri Vijaya and Kadaram, the Marakkal-Thatchan orchestrated the rapid mobilization of hundreds of transport and strike vessels, managing timber stocks, drydock rotations, and workforce deployments across the northern Coromandel estuaries."
  },
  {
    "slug": "char-nagapattinam-ocean-navigator-kalam-selvan-nayagan",
    "category": "characters",
    "file": "char-nagapattinam-ocean-navigator-kalam-selvan-nayagan.md",
    "node_type": "character",
    "name_en": "Chief Ocean Navigator & Deep-Sea Fleet Pilot of Nagapattinam (Kalam-Selvan Nayagan)",
    "name_ta": "நாகப்பட்டினப் பெருங்கடல் மாலுமி மற்றும் நாவாய்த் தலைவன் (கலம்செல்வன் நாயகன்)",
    "era": "Imperial Chola Era",
    "year_start": 1000,
    "year_end": 1070,
    "thinai": "neithal",
    "summary_en": "Master oceanic pilot and fleet captain stationed at Nagapattinam, veteran of high-seas expeditions to Sri Vijaya, Kedah, and Canton, master of sounding-lead depth sounding, wave swell patterns, and astronomical star azimuths.",
    "summary_ta": "நாகப்பட்டினம் நாவாய்த் துறையிலிருந்து ஸ்ரீவிஜயம், கடாரம் மற்றும் சீனா வரை சோழர் கடற்படைகளை வழிநடத்திய, விண்மீன் வழிசெலுத்தல் மற்றும் கடல் ஆழமறியும் தொழில்நுட்பங்களில் கைதேர்ந்த பெருங்கடல் நாவாய்த் தலைவன்.",
    "sources": [
      "Nagapattinam Chola Copperplates",
      "Leiden Inscriptions",
      "Song Dynasty Maritime Annals"
    ],
    "content": "---\nid: char-nagapattinam-ocean-navigator-kalam-selvan-nayagan\ntitle: Chief Ocean Navigator & Deep-Sea Fleet Pilot of Nagapattinam (Kalam-Selvan Nayagan)\ntype: character\nera: Imperial Chola Era (c. 1000 - 1070 CE)\nthinai: neithal (Deep-Sea Navigation)\nstatus: canonical\n---\n\n# Chief Ocean Navigator & Deep-Sea Fleet Pilot of Nagapattinam (Kalam-Selvan Nayagan)\n\n## 1. Historical & Navigational Stature\nThe **Kalam-Selvan Nayagan** (Lord of Oceanic Vessels) commanded the grand naval squadrons that embarked from Nagapattinam, the primary naval bastion of the Chola empire. Commanding flagship *Perunavai* vessels, he navigated the vast open reaches of the Bay of Bengal and Andaman Sea into the Straits of Malacca.\n\n## 2. Nautical Science & Practical Oceanography\n- **Sidereal Mastery**: Retained mental star catalogs tracking the nocturnal transit of stellar constellations to calculate latitude and heading.\n- **Sounding & Bottom Analysis (*Kallarai-paarthal*)**: Dropped greased lead weights to retrieve seabed samples, determining distance from coastlines by examining mud composition, shell grit, and sand color.\n- **Swell Interpretation**: Distinguished between direct wind chop and deep oceanic groundswells originating thousands of miles away, enabling early detection of cyclonic depressions.\n\n## 3. Diplomatic & Commercial Envoy\nBeyond piloting armada squadrons, he acted as an accredited commercial ambassador for the Tamil mercantile guilds, negotiating anchorage fees, warehouse rights, and tribute transactions at the ports of Sri Vijaya and Chinese maritime prefectures."
  },
  {
    "slug": "place-chettiyarpattinam-ancient-shipyard-haven",
    "category": "places",
    "file": "place-chettiyarpattinam-ancient-shipyard-haven.md",
    "node_type": "place",
    "name_en": "Chettiyarpattinam Ancient Shipyard Haven & Coromandel Estuarine Dockyards",
    "name_ta": "செட்டியார்பட்டினம் சோழர் கப்பல் கட்டும் துறைமுகம் மற்றும் உவர்நீர் உலர் கப்பல்துறை",
    "era": "Sangam to Chola Era",
    "year_start": -200,
    "year_end": 1250,
    "thinai": "neithal",
    "summary_en": "Major ancient and medieval maritime shipyard and drydock haven situated in an estuarine inlet on the northern Coromandel coast of Tamil Nadu, celebrated for continuous building of ocean-going stitched timber hulls, timber seasoning yards, and launchways.",
    "summary_ta": "வட சோழமண்டலக் கடற்கரையின் உப்பங்கழி முகத்துவாரத்தில் அமைந்திருந்த வரலாற்றுப் புகழ்பெற்ற தமிழ்க் கப்பல் கட்டும் தளம், உலர் கப்பல்துறை மற்றும் நாவாய் இறங்குதளம்.",
    "sources": [
      "Chettiyarpattinam Coastal Archaeological Survey",
      "South Indian Inscriptions",
      "ASI Coastal Heritage Sites"
    ],
    "content": "---\nid: place-chettiyarpattinam-ancient-shipyard-haven\ntitle: Chettiyarpattinam Ancient Shipyard Haven & Coromandel Estuarine Dockyards\ntype: place\nera: Sangam to Chola Era (c. 200 BCE - 1250 CE)\nthinai: neithal (Estuarine Harbor)\nstatus: canonical\n---\n\n# Chettiyarpattinam Ancient Shipyard Haven & Coromandel Estuarine Dockyards\n\n## 1. Geographical Location & Coastal Topography\nChettiyarpattinam is situated in a sheltered tidal estuary along the northern Coromandel coastline of Tamil Nadu, south of Sadras and Mamallapuram (coordinates approx. 12.5167° N, 80.1500° E). Sheltered from the direct fury of high-energy coastal breakers by an outer sand-spit, its deep tidal backwaters provided the ideal protected environment for building, launching, and refitting large wooden vessels.\n\n## 2. Archaeological Discoveries & Infrastructure Remains\nField surveys and excavations have exposed:\n- **Tidal Sluice Channels**: Sluice channels cut into clayey silt where vessels were berthed for seasonal drydocking.\n- **Ballast Mounds & Iron Smelting Slag**: Dense scatters of non-local ballast stones, terracotta pitch-melting pots, and iron smithing debitage from anchor forging.\n- **Seasoning Pits**: Submerged timber holding pits where logs of teak and hard poon were soaked in brackish water to leach out sap and confer insect resistance before seasoning.\n\n## 3. Role in Chola Naval Supremacy\nChettiyarpattinam operated as an indispensable northern auxiliary yard to Nagapattinam and Kaveripoompattinam, specializing in hull assembly, mast step fabrication, and lashing of sewn-plank transport craft."
  },
  {
    "slug": "text-karikala-chola-kallanai-hydraulic-chronicles-and-sangam-odes",
    "category": "texts",
    "file": "text-karikala-chola-kallanai-hydraulic-chronicles-and-sangam-odes.md",
    "node_type": "text",
    "name_en": "Karikala Chola Kallanai Hydraulic Chronicles & Porunararruppadai River Taming Odes",
    "name_ta": "கரிகால் சோழன் கல்லணை நீரியல் ஆவணங்கள் மற்றும் பொருநராற்றுப்படை காவிரி அணைப்புப் பாடல்கள்",
    "era": "Sangam Classical Era",
    "year_start": -100,
    "year_end": 200,
    "thinai": "marutham",
    "summary_en": "Sangam court poetry in Porunararruppadai (ll. 235-248) and medieval historical chronicles recording King Karikala Chola's epochal engineering feat of taming the roaring Kaveri floods, building stone dykes and the Grand Anicut to divert lifegiving waters into the delta.",
    "summary_ta": "பொருநராற்றுப்படையில் கரிகால் பெருவளத்தானின் காவிரிப் பெருவெள்ளத்தை அடக்கி, கல்லணை கட்டி, சோழநாட்டை சோறுடைத்த வளநாடாக மாற்றிய நீரியல் பொறியியலைப் போற்றும் செவ்வியல் பாடல்கள் மற்றும் வரலாற்று ஆவணங்கள்.",
    "sources": [
      "Porunararruppadai ll. 235-248",
      "Pattinappalai ll. 280-295",
      "Periyapuranam Karikala Vamsam"
    ],
    "content": "---\nid: text-karikala-chola-kallanai-hydraulic-chronicles-and-sangam-odes\ntitle: Karikala Chola Kallanai Hydraulic Chronicles & Porunararruppadai River Taming Odes\ntype: text\nera: Sangam Classical Era (c. 100 BCE - 200 CE)\nthinai: marutham (Riparian Delta Agronomy)\nstatus: canonical\n---\n\n# Karikala Chola: Kallanai Hydraulic Chronicles & Porunararruppadai River Taming Odes\n\n## 1. Classical Primary Source Citations\n- **Porunararruppadai** (ll. 235–248): Mudaththamakanniyar praises the munificence and engineering vision of King Karikala Chola (*Karikala Peruvazhuthi*), singing how the roaring Kaveri—which once flooded wastefully into the sea—was disciplined to fill irrigation tanks, moisten paddy fields, and yield grain in surplus.\n- **Pattinappalai** (ll. 280–295): Documents how Karikala cleared dense forests, excavated water reservoirs (*Kulam*), constructed embankments (*Kaveri-karai*), and made the Chola homeland a granary of the southern world.\n- **Later Chola Inscriptions & Epics**: Celebrates Karikala as the legendary monarch who compelled neighboring chieftains to carry earth and quarry granite to erect the stone dykes of the Kaveri.\n\n## 2. The Hydraulic Dilemma of the Kaveri Delta\nBefore the Grand Anicut (*Kallanai*), the Kaveri river bifurcated upstream of Trichy into two major channels:\n1. **The Kaveri**: Shallow channel feeding the fertile delta plains.\n2. **The Kollidam (Coleroon)**: Wide, steep-gradient northern channel with low bed levels that captured almost the entire monsoon flood volume, carrying precious water uselessly out to the Bay of Bengal while delta crops withered.\n\n## 3. Engineering Vision of Karikala\nKarikala recognized that unless an obstruction was built across the head of the bifurcation to raise the upstream water level, irrigation into the delta channels would fail during dry spells. His construction of the 329-meter long stone masonry weir (*Kallanai*) tamed the river's gradient, holding back the flood and diverting life-giving silt and water across millions of delta acres."
  },
  {
    "slug": "insc-thiruvanaikoil-chola-grand-anicut-maintenance-charters",
    "category": "inscriptions",
    "file": "insc-thiruvanaikoil-chola-grand-anicut-maintenance-charters.md",
    "node_type": "inscription",
    "name_en": "Thiruvanaikoil Chola Grand Anicut Maintenance Charters & Hydraulic Guild Grants",
    "name_ta": "திருவானைக்கோவில் சோழர் கல்லணை பராமரிப்பு மற்றும் நீரியல் தச்சர் மானியக் கல்வெட்டுகள்",
    "era": "Medieval Chola Era",
    "year_start": 950,
    "year_end": 1150,
    "thinai": "marutham",
    "summary_en": "Inscriptions at Thiruvanaikoil (Jambukeswaram) near the Kaveri-Kollidam bifurcation recording royal endowments (Kallanai-Puram), tax remissions for stone cutters, and village water committees (Eri-Variyam) mandated to quarry and replace flood-scoured stones.",
    "summary_ta": "காவிரி-கொள்ளிடம் பிரிவிடமான திருவானைக்கோவில் கல்வெட்டுகள், கல்லணை பராமரிப்புக்காக வழங்கப்பட்ட 'கல்லணைப்புறம்' நில மானியங்கள், கல்வெட்டுத் தச்சர்களுக்கான வரிநீக்கங்கள் மற்றும் ஏரி-வாரிய நீர்ப்பகிர்வு ஆவணங்கள்.",
    "sources": [
      "South Indian Inscriptions Vol III",
      "Epigraphia Indica Vol XI",
      "Jambukeswaram Temple Inscriptions"
    ],
    "content": "---\nid: insc-thiruvanaikoil-chola-grand-anicut-maintenance-charters\ntitle: Thiruvanaikoil Chola Grand Anicut Maintenance Charters & Hydraulic Guild Grants\ntype: inscription\nera: Medieval Chola Era (c. 950 - 1150 CE)\nthinai: marutham (River Island Hydrology)\nstatus: canonical\n---\n\n# Thiruvanaikoil: Chola Grand Anicut Maintenance Charters & Hydraulic Guild Grants\n\n## 1. Epigraphical Provenance\nInscribed upon the granite plinths and mandapa pillars of the ancient Jambukeswaram (Thiruvanaikoil) temple complex located on the riverine island between the Kaveri and Kollidam rivers, these royal Chola epigraphs date to the reigns of Parantaka I, Rajaraja I, and Kulothunga I.\n\n## 2. Inscription Decrees & Maintenance Mandates\n- **Kallanai-Puram Endowments**: Grants designated agricultural lands whose revenues were exclusively earmarked for repairing breaches, quarrying replacement stones, and paying stone-dressing artisans.\n- **Stone-Cutter Tax Remissions (*Uli-Kaani*)**: Hereditary stone masons (*Kal-Thatchar*) settled in villages around Thiruvanaikoil were exempted from agricultural and house taxes in exchange for perpetual readiness to shore up flood aprons.\n- **Coordination with Eri-Variyam**: Village water management committees were legally obligated to supply labor teams during summer low-water periods to clear silt deposits upstream of the weir.\n\n## 3. Societal Organization of Water Governance\nThese inscriptions reflect a highly decentralized yet state-backed hydraulic administration. The royal court provided statutory charters and tax protection, while local agricultural assemblies (*Sabhas* and *Urar*) managed physical weir maintenance, guaranteeing continuous agricultural productivity for centuries."
  },
  {
    "slug": "insc-veeranam-parantaka-chola-reservoir-sluice-endowments",
    "category": "inscriptions",
    "file": "insc-veeranam-parantaka-chola-reservoir-sluice-endowments.md",
    "node_type": "inscription",
    "name_en": "Veeranam Parantaka Chola Reservoir Sluice Endowments & Vadavaru Feeder Charters",
    "name_ta": "வீராணம் பராந்தக சோழர் ஏரி மதகு கொடைகள் மற்றும் வடவாறு கால்வாய் கல்வெட்டுகள்",
    "era": "Imperial Chola Era",
    "year_start": 907,
    "year_end": 955,
    "thinai": "marutham",
    "summary_en": "Imperial stone inscriptions commemorating King Parantaka Chola I's creation of the massive Veeranam reservoir (Veeranarayana Eri), documenting dressed granitic sluice headworks, intake weirs on the Kollidam, and maintenance tithes.",
    "summary_ta": "முதலாம் பராந்தக சோழன் வெட்டிய வீரநாராயணப் பேரேரியின் (வீராணம் ஏரி) செதுக்கப்பட்ட கருங்கல் மதகுகள், கொள்ளிடத்திலிருந்து நீர் கொண்டுவரும் வடவாற்றுக் கால்வாய் மற்றும் மதகு பராமரிப்புக் கொடைகளைப் பதிவுசெய்த கல்வெட்டுகள்.",
    "sources": [
      "South Indian Inscriptions Vol VIII",
      "Kattumannarkoil Epigraphs",
      "Chola Irrigation Inscriptions"
    ],
    "content": "---\nid: insc-veeranam-parantaka-chola-reservoir-sluice-endowments\ntitle: Veeranam Parantaka Chola Reservoir Sluice Endowments & Vadavaru Feeder Charters\ntype: inscription\nera: Imperial Chola Era (c. 907 - 955 CE)\nthinai: marutham (Mega-Reservoir Engineering)\nstatus: canonical\n---\n\n# Veeranam: Parantaka Chola Reservoir Sluice Endowments & Vadavaru Feeder Charters\n\n## 1. Epigraphical Context & Discovery\nLocated in Kattumannarkoil and surrounding villages along the colossal embankment of the Veeranam lake (originally *Veeranarayana Eri*) in Cuddalore district, these epigraphs commemorate the mega-engineering projects commissioned by King Parantaka Chola I (reigned 907–955 CE).\n\n## 2. Inscriptional Records of Engineering Scope\n- **The Vadavaru Feeder Canal**: Documents the excavation of a massive canal tapping water from the Lower Anicut region on the Kollidam river and conveying it northward across 20 kilometers into the reservoir.\n- **Granite Sluice Specifications (*Madagu-kole*)**: Records the dimensions of precision-dressed granitic sluices, upright pier slots for wooden drop-gates, and underwater conduits (*Thumbu*).\n- **Maintenance Endowments (*Eri-Patti*)**: Mandates that a toll of paddy be collected from every cultivated acre irrigated by Veeranam's waters to maintain boats for silt dredging and repair riprap stone facing on the earthen bund.\n\n## 3. Monumental Civil Works\nThe lake bund extends over 14 kilometers in length with a massive water-holding capacity, irrigating over 40,000 acres. These inscriptions demonstrate that the Cholas integrated river weir diversion (Kallanai style) with vast off-river storage reservoirs (Veeranam style) to buffer against irregular monsoon droughts."
  },
  {
    "slug": "concept-cyclopean-granite-dressing-and-clay-silt-hydraulic-foundations",
    "category": "concepts",
    "file": "concept-cyclopean-granite-dressing-and-clay-silt-hydraulic-foundations.md",
    "node_type": "concept",
    "name_en": "Cyclopean Granite Dressing, Sinking Foundation Mechanics & Clay-Silt Bedding",
    "name_ta": "மூலக்கல் கருங்கல் செதுக்கல், ஆற்று மணற்படுக்கை அமிழ்தல் அடித்தளம் மற்றும் களிமண் பிணைப்பு",
    "era": "Sangam Classical Era",
    "year_start": -100,
    "year_end": 500,
    "thinai": "marutham",
    "summary_en": "The profound geotechnical engineering of the Grand Anicut: un-hewn and cyclopean dressed granitic boulders rolled into the swift flowing riverbed, which sank through shifting sands until resting on impervious clay, bound together solely by gravitational interlock and river silt cementation.",
    "summary_ta": "சுண்ணாம்புக் காரையின்றி, ஓடும் ஆற்றுப் பெருவெள்ளத்தில் பிரம்மாண்ட கருங்கற்களை உருட்டி இறக்கி, மணல் பரப்பில் அமிழ்ந்து கீழே உள்ள வண்டல் களிமண் மீது நிலைத்து நிற்கும் கல்லணையின் தனித்துவமான புவி-நீரியல் அடித்தளப் பொறியியல்.",
    "sources": [
      "Memoir on the Grand Anicut (Sir Arthur Cotton, 1856)",
      "Chola Hydraulic Engineering Studies",
      "ASI Architectural Survey"
    ],
    "content": "---\nid: concept-cyclopean-granite-dressing-and-clay-silt-hydraulic-foundations\ntitle: Cyclopean Granite Dressing, Sinking Foundation Mechanics & Clay-Silt Bedding\ntype: concept\nera: Sangam Classical Era (c. 100 BCE - 500 CE)\nthinai: marutham (Geotechnical & Hydraulic Engineering)\nstatus: canonical\n---\n\n# Cyclopean Granite Dressing, Sinking Foundation Mechanics & Clay-Silt Bedding\n\n## 1. The Geotechnical Miracle of the Sinking Dam\nWhen British hydraulic engineer Sir Arthur Cotton inspected the Grand Anicut (*Kallanai*) in the early 19th century, he was astonished to discover that a 1,800-year-old stone dam had been built across a swift alluvial river without rock foundations, cement mortar, or timber piling.\n\n## 2. Construction Methodology & Sinking Mechanics\n1. **Rolling Massive Granite Blocks**: Un-mortared granitic boulders weighing several tons were transported from the Pachaimalai hills and systematically rolled into the raging floodwaters of the Kaveri.\n2. **Scour-Induced Settlement**: The rushing current washed away the loose sand beneath the boulders, causing the heavy stones to sink deeper into the riverbed.\n3. **Impermeable Substratum Resting**: Successive tiers of boulders were piled on top of the sinking stones until they reached the dense, impermeable clay-silt layer beneath the alluvial sand.\n4. **Natural Silt Cementation**: The Kaveri's fine alluvial silt filtered into the interstitial crevices between the rough dressed stones, consolidating under water pressure into a water-resistant, self-sealing conglomerate bond.\n\n## 3. Structural Stability Without Mortar\n- **Elastic Gravitational Equilibrium**: Because the dam was not a rigid monolithic block of mortar, it had the flexibility to settle differentially without developing catastrophic structural shear cracks.\n- **Thermal Expansion Accommodation**: Un-mortared stone joints accommodated seasonal temperature shifts between scorching dry summers and submerged monsoon floods without buckling.\n\n## 4. Worldwide Engineering Legacy\nSir Arthur Cotton studied the foundation principles of Kallanai and adopted them directly in the design of the Godavari and Krishna anicuts, acknowledging that modern Western hydraulic engineering learned foundation design on sand beds directly from ancient Tamil masons."
  },
  {
    "slug": "concept-curved-weir-geometry-and-hydraulic-energy-dissipation-aprons",
    "category": "concepts",
    "file": "concept-curved-weir-geometry-and-hydraulic-energy-dissipation-aprons.md",
    "node_type": "concept",
    "name_en": "Curved Weir Geometry, Downstream Talus Aprons & Energy Dissipation Mechanics",
    "name_ta": "வளைந்த தடுப்பணை வடிவவியல், சரிவுத் தளம் (ஏப்ரான்) மற்றும் வெள்ள ஆற்றல் சிதைப்பு நுட்பம்",
    "era": "Sangam Classical Era",
    "year_start": -100,
    "year_end": 1000,
    "thinai": "marutham",
    "summary_en": "Hydrodynamic design of the 329-meter serpentine curved masonry weir crest, sweeping diagonal flow vectors, and sloping downstream dry-stone boulder aprons that dissipate scouring hydraulic turbulence and protect riverbed stability.",
    "summary_ta": "329 மீட்டர் நீள பாம்பு வடிவிலான நெளிந்த அணை அமைப்பு, நேர்முக வெள்ள அழுத்தத்தை பக்கவாட்டில் திருப்பி ஆற்றலைச் சிதறடிக்கும் கீழ்ப்புறச் சரிவுத் தளக் கற்கள் (Talus Aprons) மற்றும் அரிப்பைத் தடுக்கும் நீரியல் கட்டமைப்பு.",
    "sources": [
      "Baird Smith: Irrigation in Southern India (1853)",
      "Pattabiramin: The Grand Anicut of Karikala Chola",
      "PWD Heritage Water Records"
    ],
    "content": "---\nid: concept-curved-weir-geometry-and-hydraulic-energy-dissipation-aprons\ntitle: Curved Weir Geometry, Downstream Talus Aprons & Energy Dissipation Mechanics\ntype: concept\nera: Sangam Classical Era (c. 100 BCE - 1000 CE)\nthinai: marutham (Hydrodynamics & Weir Geometry)\nstatus: canonical\n---\n\n# Curved Weir Geometry, Downstream Talus Aprons & Energy Dissipation Mechanics\n\n## 1. Serpentine Weir Alignment\nThe Grand Anicut does not cross the Kaveri river in a straight perpendicular line. Instead, it forms an elegant serpentine curve stretching 329 meters (1,080 feet) in length with a width of 12 to 18 meters (40 to 60 feet):\n- **Diagonal Flow Vector Deflection**: The curved weir crest strikes the approaching river current obliquely. Instead of absorbing the full perpendicular hydrostatic shock of the flood, it deflects the main force of the water sideways toward the Kollidam overflow channel.\n- **Increased Discharge Length**: The curved perimeter increases the effective crest overflow length, allowing higher discharge volumes per second without raising the upstream flood crest to dangerous levee-breaching heights.\n\n## 2. Downstream Energy Dissipation Aprons (*Talus*)\nWhen high-velocity water cascades over a weir crest, its kinetic energy can scour the soft sandy riverbed immediately below the dam, undermining the structure from downstream. Ancient Tamil engineers solved this through:\n1. **Sloping Stone Glacis**: The downstream face was built as a gentle slope rather than a vertical drop, keeping the overflow sheet clinging to the masonry.\n2. **Loose Boulder Talus Apron**: Extending 20 to 30 meters downstream from the toe of the weir was an apron of loose, interlocking granitic boulders.\n3. **Hydraulic Jump Formation**: The rough boulder apron tripped the fast laminar flow into a turbulent hydraulic jump, dissipating energy before the water reached the unprotected sand bed further downstream.\n\n## 3. Resilience Against Millennial Floods\nBecause the boulder apron consisted of individual heavy blocks, any minor localized scouring simply caused the stones to settle into the scour holes, naturally armoring the bed without human intervention."
  },
  {
    "slug": "concept-silt-scouring-sluices-and-kumizhi-thumbu-headworks",
    "category": "concepts",
    "file": "concept-silt-scouring-sluices-and-kumizhi-thumbu-headworks.md",
    "node_type": "concept",
    "name_en": "Silt-Scouring Sluices, Upstream Flushing Regulators & Kumizhi-Thumbu Mechanics",
    "name_ta": "வண்டல் வடித்தல் மதகுகள், நீரடி அடிமதகு ஒழுங்குமுறை மற்றும் குமிழித் தூம்பு இயங்கியல்",
    "era": "Sangam to Chola Era",
    "year_start": -200,
    "year_end": 1100,
    "thinai": "marutham",
    "summary_en": "Traditional Tamil hydraulic sluice systems utilizing bottom-perforated stone cylinders (Kumizhi-Thumbu) and under-sluice vents that vortex-flush accumulated riverbed silt downstream during peak flow, preserving reservoir storage capacity and preventing delta canal choking.",
    "summary_ta": "நீரின் கீழ்மட்ட வண்டல் படிவுகளை சுழல் விசை மூலம் வெளியேற்றி, பாசனக் கால்வாய்கள் மணலால் தூர்ந்து போகாமல் பாதுகாக்கும் இரு துளைக் குமிழித் தூம்பு மற்றும் அடிமதகு நீர்ப்பொறியியல் நுட்பங்கள்.",
    "sources": [
      "Inscriptions of the Tamil Country - Irrigation Sluices",
      "Nagaswamy: Water Management in Ancient Tamil Nadu",
      "Studies in Ancient Tamil Hydraulics"
    ],
    "content": "---\nid: concept-silt-scouring-sluices-and-kumizhi-thumbu-headworks\ntitle: Silt-Scouring Sluices, Upstream Flushing Regulators & Kumizhi-Thumbu Mechanics\ntype: concept\nera: Sangam to Chola Era (c. 200 BCE - 1100 CE)\nthinai: marutham (Subsurface Hydraulic Mechanics)\nstatus: canonical\n---\n\n# Silt-Scouring Sluices, Upstream Flushing Regulators & Kumizhi-Thumbu Mechanics\n\n## 1. The Silt Problem in Tropical Irrigation\nTropical monsoon rivers carry immense suspended sediment loads (* வண்டல் / Vandal*). If water is drawn into irrigation canals from the bottom of an impoundment, canals rapidly choke with sand; if water is drawn solely from the top, the reservoir itself silts up, destroying storage capacity within decades. Ancient Tamil engineers solved this through the **Kumizhi-Thumbu** (conical vortex sluice).\n\n## 2. Architecture & Working Principles of the Kumizhi-Thumbu\n1. **Vertical Cylindrical Intake Tower (*Neer-Koodu*)**:\n   - A dressed granite cylindrical or square tower erected inside the tank water near the bund.\n   - Pierced with two sets of intake vents: one at the very bottom near the silt bed (*Ser-Thumbu*), and another higher up for clear water (*Neer-Thumbu*).\n2. **Vortex Scouring Effect**:\n   - When the stone plug is lifted via an overhead lever, water plunging into the vertical shaft generates a swirling vortex.\n   - The centrifugal suction draws heavy silt from the tank floor through the bottom orifice, mixing it into a slurry with the clear surface water.\n3. **Underwater Conduit (*Thumbu*)**:\n   - The slurry passes through a horizontal slab-built masonry conduit passing beneath the tank bund into the main irrigation canal.\n   - The nutrient-rich silt is deposited onto agricultural paddy fields as natural organic fertilizer rather than clogging the reservoir bed.\n\n## 3. Scouring Sluices on River Anicuts\nOn river weirs like Kallanai, under-sluices (*Madagu*) were opened during the first muddy spate of the monsoon. The intense underflow velocity scoured sediment off the riverbed upstream of the weir, flushing it down the non-irrigated Kollidam channel and leaving clear water for the Kaveri canals."
  },
  {
    "slug": "concept-chola-river-embankment-and-flood-diversion-canal-networks",
    "category": "concepts",
    "file": "concept-chola-river-embankment-and-flood-diversion-canal-networks.md",
    "node_type": "concept",
    "name_en": "Chola River Embankment Engineering (Kaveri Karai) & Flood Diversion Canals",
    "name_ta": "சோழர் கால காவிரி ஆற்றுக் கரைகள் (கரை கட்டுதல்) மற்றும் வெள்ளப் பகிர்வுக் கால்வாய் வலையமைப்பு",
    "era": "Sangam to Imperial Chola Era",
    "year_start": -100,
    "year_end": 1200,
    "thinai": "marutham",
    "summary_en": "Vast civil engineering networks comprising hundreds of kilometers of stone-reinforced earth levees (Kaveri-Karai) commissioned by Karikala Chola, bifurcating Kaveri into Kollidam, Vennaru, and Arasalaru to irrigate millions of delta acres.",
    "summary_ta": "கரிகாலன் தொடங்கி பிற்காலச் சோழர் வரை காவிரி ஆற்றின் இருபுறமும் கட்டிய நூற்றுக்கணக்கான கல்-மண் கரைகள், கொள்ளிடம், வெண்ணாறு, அரசலாறு என வெள்ள நீரைப் பிரித்துப் பாய்ச்சிய பாசனக் கால்வாய் வலையமைப்பு.",
    "sources": [
      "Thiruvalangadu Copperplates",
      "Chola Delta Irrigation Chronicles",
      "Nilakanta Sastri: The Colas"
    ],
    "content": "---\nid: concept-chola-river-embankment-and-flood-diversion-canal-networks\ntitle: Chola River Embankment Engineering (Kaveri Karai) & Flood Diversion Canals\ntype: concept\nera: Sangam to Imperial Chola Era (c. 100 BCE - 1200 CE)\nthinai: marutham (Macro-Regional Delta Canal Networks)\nstatus: canonical\n---\n\n# Chola River Embankment Engineering (Kaveri Karai) & Flood Diversion Canals\n\n## 1. Monumental Levee Construction (*Kaveri-Karai*)\nSangam odes, epigraphical records, and historical traditions celebrate King Karikala Chola's initiative of constructing massive earthen and stone-faced flood embankments along the entire length of the lower Kaveri river. Prior to this, uncontrolled floods periodically submerged agricultural settlements, destroying crops and turning paddy fields into saline marshes.\n\n## 2. River Embankment Structural Design\n1. **Compacted Earth Core with Turf Anchoring**: Broad earthen embankments were built with clayey delta soil, stabilized by planting deep-rooting grasses (*Vetiver*) and tamarind trees.\n2. **Stone Riprap Armor (*Kark-kattu*)**: Points subject to violent erosive eddy currents were armored with dry-stone granitic boulders pitching on 1:2 slopes.\n3. **Spillway Overflows (*Kalingula*)**: Deliberate low stone crests allowed controlled overflow into diversion channels when water levels exceeded critical safety thresholds.\n\n## 3. The Delta Canal Hierarchy\nThe Chola canal system divided the delta into an intricate vascular network:\n- **Major River Branches**: Kaveri, Kollidam, Vennaru, Vadavaru, and Arasalaru.\n- **Main Feeder Canals (*Perum-Kaal*)**: Diverted directly from river regulators.\n- **Village Supply Canals (*Nattu-Kaal*)**: Distributed water to agricultural village boundaries.\n- **Field Inflow & Drainage Channels (*Vaykkal* & *Vadik-kaal*)**: Allowed fresh water to enter while drawing out waterlogged alkaline drainage, preventing soil salinity.\n\n## 4. Socio-Economic Multiplier\nThis integrated hydraulic system turned Thanjavur into the wealthiest rice-producing region in South Asia, funding the construction of the Great Living Chola Temples and underwriting the cultural golden age of Tamil civilization."
  },
  {
    "slug": "char-kallanai-master-hydraulic-architect-neerarru-sirpan",
    "category": "characters",
    "file": "char-kallanai-master-hydraulic-architect-neerarru-sirpan.md",
    "node_type": "character",
    "name_en": "Master Hydraulic Architect of the Grand Anicut (Neerarru-Sirpan)",
    "name_ta": "கல்லணைத் தலைமை நீரியல் சிற்பி மற்றும் அணைப் பொறியாளர் (நீராற்றுச் சிற்பன்)",
    "era": "Sangam Classical Era",
    "year_start": -50,
    "year_end": 50,
    "thinai": "marutham",
    "summary_en": "Visionary chief water architect serving King Karikala Chola, master of river velocity calculations, subsurface silt dynamics, boulder settling logistics, and downstream overflow gradients.",
    "summary_ta": "கரிகால் சோழனின் அரசவையில் காவிரி ஆற்றின் பெருவெள்ள வேகம், மணற்படுக்கை அமிழ்தல் மற்றும் கல்லணையின் வளைந்த தடுப்பணை வடிவத்தை கணித்து வடிவமைத்த முதன்மை நீரியல் சிற்பி.",
    "sources": [
      "Kallanai Oral Traditions & Epigraphical Lore",
      "Sangam Architectural Commentaries",
      "Chola Irrigation Archives"
    ],
    "content": "---\nid: char-kallanai-master-hydraulic-architect-neerarru-sirpan\ntitle: Master Hydraulic Architect of the Grand Anicut (Neerarru-Sirpan)\ntype: character\nera: Sangam Classical Era (c. 50 BCE - 50 CE)\nthinai: marutham (Hydraulic Engineering Leadership)\nstatus: canonical\n---\n\n# Master Hydraulic Architect of the Grand Anicut (Neerarru-Sirpan)\n\n## 1. Historical Identity & Engineering Role\nThe **Neerarru-Sirpan** (Master River Sculptor / Hydraulic Architect) represents the brilliant chief engineer who directed the monumental construction of the Grand Anicut under Karikala Chola. Working across the Kaveri-Kollidam bifurcation, he translated royal decree into physical reality, commanding stone quarry transport, riverbed surveying, and hydrodynamic alignment.\n\n## 2. Technical Expertise\n- **Flood Velocity Gauge (*Vellap-paai-alavu*)**: Calculated river velocity during flood stages using floating timber markers, determining the threshold force required to dislodge boulder beds.\n- **Serpentine Alignment Layout**: Sited the curving trajectory of the dam across the sandbars to maximize flow deflection into the Kollidam while preserving gravity flow into the Kaveri.\n- **Foundation Sinking Logistics**: Devised the system of dropping successive tiers of boulders into the scoured sand until they struck the underlying clay bed.\n\n## 3. Legacy in Civil Engineering\nHis pioneering design principles established a tradition of delta water engineering that remained unbroken for two millennia, earning the veneration of later Chola kings and modern British hydraulic pioneers alike."
  },
  {
    "slug": "char-thiruvanaikoil-master-stone-mason-kal-thatchan",
    "category": "characters",
    "file": "char-thiruvanaikoil-master-stone-mason-kal-thatchan.md",
    "node_type": "character",
    "name_en": "Master Granite Mason & Sluice Carver of Thiruvanaikoil (Kal-Thatchan)",
    "name_ta": "திருவானைக்கோவில் தலைமைக் கல் தச்சன் மற்றும் மதகு சிற்பி (கல் தச்சன்)",
    "era": "Medieval Chola Era",
    "year_start": 950,
    "year_end": 1020,
    "thinai": "marutham",
    "summary_en": "Senior hereditary master stone mason responsible for quarrying hard granitic blocks from the Pachaimalai hills, dressing precision-slotted sluice uprights, and assembling cyclopean weir aprons across the Kaveri basin.",
    "summary_ta": "பச்சைமலைக் குன்றுகளிலிருந்து கருங்கற்களை வெட்டி எடுத்து, கல்லணை மதகுகள், குமிழித் தூம்புகள் மற்றும் அணைப் பழுதுநீக்கும் பணிகளை வழிநடத்திய தலைமைப் பெருந்தச்சன்.",
    "sources": [
      "Thiruvanaikoil Inscriptions",
      "South Indian Inscriptions Vol III",
      "Temple Masonry Guild Charters"
    ],
    "content": "---\nid: char-thiruvanaikoil-master-stone-mason-kal-thatchan\ntitle: Master Granite Mason & Sluice Carver of Thiruvanaikoil (Kal-Thatchan)\ntype: character\nera: Medieval Chola Era (c. 950 - 1020 CE)\nthinai: marutham (Lithic Engineering & Masonry Guilds)\nstatus: canonical\n---\n\n# Master Granite Mason & Sluice Carver of Thiruvanaikoil (Kal-Thatchan)\n\n## 1. Professional Status & Guild Standing\nStationed on the island of Thiruvanaikoil adjacent to the Grand Anicut, the **Kal-Thatchan** (Master Stone Mason) served as the hereditary leader of the granite masonry guilds (*Sirpa-Kammalar*). Beneficiary of tax-free *Thatcha-kaani* lands endowed by Chola monarchs, he was responsible for the ongoing structural integrity of all stone water regulators across the delta headworks.\n\n## 2. Lithic Masonry Mastery\n- **Granite Cleaving (*Kal-Pilathal*)**: Expert in driving dry wooden wedges into natural grain crevices of hard charnockite and granite rockfaces, saturating the wedges with water to expand and split cleanly dressed mega-blocks.\n- **Precision Sluice Slotting**: Carved continuous vertical guide grooves into stone piers (*Kattalai-thoon*) to hold wooden drop gates (*Palagai-kadavu*) against massive hydrostatic head pressure.\n- **Apron Keying**: Dressed interlocking tongue-and-groove granite boulders for weir crests, preventing stones from being plucked out by high-velocity flood overflows.\n\n## 3. Civic & Sacred Role\nHe bridged the sacred and utilitarian worlds of Tamil stone engineering, carving temple mandapas at Jambukeswaram while maintaining the life-giving sluices that watered the kingdom's paddy fields."
  },
  {
    "slug": "place-thiruvanaikoil-ancient-hydraulic-haven",
    "category": "places",
    "file": "place-thiruvanaikoil-ancient-hydraulic-haven.md",
    "node_type": "place",
    "name_en": "Thiruvanaikoil Ancient Hydraulic Haven & Kaveri-Kollidam Delta Bifurcation",
    "name_ta": "திருவானைக்கோவில் பண்டைய நீரியல் தளம் மற்றும் காவிரி-கொள்ளிடம் பிரிவிட நீர்க்கோட்டம்",
    "era": "Sangam to Chola Era",
    "year_start": -100,
    "year_end": 1250,
    "thinai": "marutham",
    "summary_en": "Strategic riverine island and hydraulic masonry sanctuary situated at the Kaveri and Kollidam river bifurcation in the central Tamil delta, renowned for historic flood defenses, water temple hydrology, and maintenance headquarters for the Grand Anicut.",
    "summary_ta": "காவிரியும் கொள்ளிடமும் பிரியும் திருவரங்கம்-திருவானைக்கோவில் தீவுப்பகுதியில் அமைந்த வரலாற்றுப் புகழ்பெற்ற நீரியல் தளம், வெள்ளப் பாதுகாப்பு மதகுகள் மற்றும் கல்லணைப் பராமரிப்பு முகாம்.",
    "sources": [
      "Thiruvanaikoil Temple Sthalapuranam & Epigraphs",
      "Archaeological Survey of the Kaveri Delta",
      "Imperial Gazetteer of India"
    ],
    "content": "---\nid: place-thiruvanaikoil-ancient-hydraulic-haven\ntitle: Thiruvanaikoil Ancient Hydraulic Haven & Kaveri-Kollidam Delta Bifurcation\ntype: place\nera: Sangam to Chola Era (c. 100 BCE - 1250 CE)\nthinai: marutham (River Island Hydrology)\nstatus: canonical\n---\n\n# Thiruvanaikoil Ancient Hydraulic Haven & Kaveri-Kollidam Delta Bifurcation\n\n## 1. Geographical Location & Riparian Hydrology\nThiruvanaikoil (Jambukeswaram) is situated on the fertile riverine island formed by the splitting of the Kaveri and Kollidam rivers near Tiruchirappalli (coordinates approx. 10.8533° N, 78.7050° E). Positioned immediately upstream of the Grand Anicut (*Kallanai*), it has functioned since early antiquity as the hydraulic nerve center of the entire Kaveri delta.\n\n## 2. Sacred Water Architecture & Subsurface Springs\nThiruvanaikoil is consecrated as the *Appu Sthalam* (Water Element Shrine) among the Pancha Bhoota Stalam sanctuaries of Tamilakam:\n- **Submerged Sanctum (*Neer-Karuvarai*)**: The central Shiva Lingam is perennially submerged in a natural subterranean freshwater spring fed by subsurface infiltration from the Kaveri.\n- **Hydraulic Conduit Engineering**: Ancient stone underground channels circulate river water through temple tanks and discharge it back into the river system.\n\n## 3. Epicenter of Delta Masonry Guilds\nBecause of its proximity to the Grand Anicut, Thiruvanaikoil was the permanent residential quarter for the royal stone carvers, hydraulic technicians, and divers (*Neer-muzhuguvor*) tasked with monitoring the riverbed, repairing embankment breaches, and maintaining the vital sluice infrastructure that sustained the Chola Empire."
  },
  {
    "slug": "text-silappadikaram-gold-bazaar-and-goldsmith-guild-poetry",
    "category": "texts",
    "file": "text-silappadikaram-gold-bazaar-and-goldsmith-guild-poetry.md",
    "node_type": "text",
    "name_en": "Silappadikaram Gold Bazaar Hymns (Pon-Angadi) & Master Jeweler Guild Chronicles",
    "name_ta": "சிலப்பதிகாரம் - பொன்னங்காடி வீதி, பொற்கொல்லர் தொழிற்கூடம் மற்றும் ஆபரணக் கலைப் பாடல்கள்",
    "era": "Sangam Classical Era",
    "year_start": 100,
    "year_end": 300,
    "thinai": "marutham",
    "summary_en": "Epic verses in Silappadikaram (Puhar Kandam, ll. 180-210) vividly describing the gleaming gold market (Pon-Angadi) of Kaveripoompattinam, four grades of refined gold, blowpipe charcoal hearths, and royal jewelers crafting exquisite ornaments.",
    "summary_ta": "சிலப்பதிகாரத்தில் காவிரிப்பூம்பட்டினத்தின் பொன்னங்காடித் தெருக்கள், நான்கு வகைப்பட்ட பசும்பொன் (கிளிச்சிறை, சாம்பூனதம், ஆடகம், சாதரூபம்), துருத்தி கொண்டு பொன்னை உருக்கிய பொற்கொல்லர்களின் அணிகலன் கைவினை பற்றிய செவ்வியல் பாடல்கள்.",
    "sources": [
      "Silappadikaram Kadaladukathai ll. 180-210",
      "Silappadikaram Kolaikkalakkathai",
      "Adiyarkkunallar Commentary"
    ],
    "content": "---\nid: text-silappadikaram-gold-bazaar-and-goldsmith-guild-poetry\ntitle: Silappadikaram Gold Bazaar Hymns (Pon-Angadi) & Master Jeweler Guild Chronicles\ntype: text\nera: Sangam Classical Era (c. 100 - 300 CE)\nthinai: marutham (Urban Market Metrology)\nstatus: canonical\n---\n\n# Silappadikaram: Gold Bazaar Hymns (Pon-Angadi) & Master Jeweler Guild Chronicles\n\n## 1. Classical Primary Source Citations\n- **Silappadikaram** (*Kadaladukathai*, ll. 180–210): Prince-poet Ilango Adigal describes the opulent gold bazaar (*Pon-Angadi*) of Kaveripoompattinam, where master goldsmiths (*Pon-Kollan* / *Kammalar*) sat before charcoal hearths, blowing air through slender copper blowpipes to melt gold in miniature crucibles.\n- **Silappadikaram** (*Kolaikkalakkathai*): Portrays the royal master goldsmith of Madurai, adorned with ceremonial turbans and royal rings, wielding measuring balances (*Kozhu*) and touchstones (*Urai-kal*) to assay royal jewelry.\n- **Adiyarkkunallar Commentary**: Details the classical Tamil classification of four distinct grades of refined gold: *Kilichchirai*, *Sambunatham*, *Adakam*, and *Satharupam*.\n\n## 2. The Fourfold Gold Classification of Tamilakam\n1. **Kilichchirai (Parrot-Green Tint Gold)**: Highly prized gold with a subtle greenish-yellow hue, refined through selective alloying.\n2. **Sambunatham (Jambu River Gold)**: Naturally radiant alluvial gold panned from crystalline riverbeds.\n3. **Adakam (Reddish Deep Gold)**: Lustrous copper-rich gold displaying a warm reddish fire.\n4. **Satharupam (Pristine Pale Gold)**: Pure, unalloyed virgin gold used for royal crowns and sacred consecration icons.\n\n## 3. Metallurgy, Guilds & Royal Patronage\nGoldsmiths operated through highly organized municipal guilds governed by code of conduct, assay standards, and standardized weights (*Manjadi* and *Kundrimani* red-seed carats). Silappadikaram proves that urban Tamilakam practiced world-class jewelry fabrication centuries before medieval European guild systems took shape."
  },
  {
    "slug": "insc-keezhadi-early-pandya-gold-assay-and-artisan-charters",
    "category": "inscriptions",
    "file": "insc-keezhadi-early-pandya-gold-assay-and-artisan-charters.md",
    "node_type": "inscription",
    "name_en": "Keezhadi Early Pandya Gold Assay Epigraphs & Touchstone Lapidary Charters",
    "name_ta": "கீழடி முற்காலப் பாண்டியர் தங்க மதிப்பீடு, உரைகல் மற்றும் பொற்கொல்லர் கல்வெட்டுகள்",
    "era": "Early Historic Era",
    "year_start": -580,
    "year_end": -200,
    "thinai": "marutham",
    "summary_en": "Tamil-Brahmi inscribed potsherds, touchstones, bone blowpipes, and crucible fragments excavated at Keezhadi on the Vaigai basin, confirming urban goldsmith guilds, standardized gold purity testing, and micro-granulation workshops.",
    "summary_ta": "வைகை ஆற்றங்கரை கீழடி அகழாய்வில் கண்டெடுக்கப்பட்ட தமிழ்-பிராமி பொறித்த மண்பாண்டங்கள், தங்க உரைகற்கள் (உரைகல்), நுண்மணிகளாலான தங்க அணிகலன்கள் மற்றும் முற்காலப் பாண்டியர் பொற்கொல்லர் தொழிற்கூடச் சான்றுகள்.",
    "sources": [
      "Keezhadi Archaeological Excavation Reports (TNSDA)",
      "Tamil-Brahmi Inscriptions of the Vaigai Valley",
      "Iravatham Mahadevan: Early Tamil Epigraphy"
    ],
    "content": "---\nid: insc-keezhadi-early-pandya-gold-assay-and-artisan-charters\ntitle: Keezhadi Early Pandya Gold Assay Epigraphs & Touchstone Lapidary Charters\ntype: inscription\nera: Early Historic Era (c. 580 - 200 BCE)\nthinai: marutham (Vaigai Industrial Archaeology)\nstatus: canonical\n---\n\n# Keezhadi: Early Pandya Gold Assay Epigraphs & Touchstone Lapidary Charters\n\n## 1. Archaeological Discovery & Provenance\nExcavated by the Tamil Nadu State Department of Archaeology (TNSDA) at Keezhadi on the Vaigai river basin near Madurai, carbon-dated to the 6th century BCE, these artifacts and graffiti-inscribed potsherds establish the earliest urban metallurgical workshops in Tamil Nadu.\n\n## 2. Inscriptional Artifacts & Material Evidence\n- **Touchstone with Streak Residue (*Urai-kal*)**: Smooth black chert and jasper touchstone bars found with microscopic streaks of high-purity gold still embedded in their micro-crevices.\n- **Tamil-Brahmi Inscribed Sherds**: Personal artisan names such as *Kathan*, *Aathan*, and *Uthiran* inscribed on terracotta crucibles and storage jars.\n- **Crucible Metallurgy**: Refractory clay crucibles capable of withstanding temperatures exceeding 1,100°C, showing vitrified slag lining with trapped gold prills.\n\n## 3. Micro-Granulation Bead Technology\nExcavations yielded micro-granulation gold filigree ornaments consisting of microscopic spherical beads less than 1 mm in diameter welded to thin gold foils. Scientific scanning electron microscope (SEM) analysis confirms that 6th-century BCE artisans in Keezhadi practiced eutectic colloidal soldering without modern torches or chemical fluxes.\n\n## 4. Significance for South Asian Chronology\nKeezhadi pushes back the dawn of urban metallurgy, literacy, and sophisticated gold craftsmanship in Tamilakam to the early 6th century BCE, contemporaneous with the Second Urbanization of the Gangetic plain."
  },
  {
    "slug": "insc-kodumanal-cheran-filigree-goldsmith-guild-charters",
    "category": "inscriptions",
    "file": "insc-kodumanal-cheran-filigree-goldsmith-guild-charters.md",
    "node_type": "inscription",
    "name_en": "Kodumanal Chera Goldsmith Guild Charters & Wire-Drawing Lapidary Epigraphs",
    "name_ta": "கொடுமணல் சேரர் பொற்கொல்லர் தொழிற்குழு மற்றும் தங்கக் கம்பி இழுப்புப் பட்டயங்கள்",
    "era": "Sangam Classical Era",
    "year_start": -300,
    "year_end": 100,
    "thinai": "kurinji",
    "summary_en": "Inscribed Tamil-Brahmi graffiti, draw-plates, miniature crucibles, and gemstone-inlaid filigree gold ornaments unearthed at Kodumanal on the Noyyal river, recording prosperous Chera merchant guilds and master goldsmith fraternities.",
    "summary_ta": "நொய்யல் ஆற்றங்கரை கொடுமணல் அகழாய்வில் வெளிவந்த தமிழ்-பிராமி எழுத்துப் பொறிப்புகள், தங்கக் கம்பி இழுப்புத் தகடுகள் (Drawplates), நுண் பொன்மணிகள் மற்றும் சேரர் காலப் பொற்கொல்லர் வணிகக் குழுச் சான்றுகள்.",
    "sources": [
      "Kodumanal Excavation Reports (Rajan)",
      "Chera Epigraphy & Gemstone Metallurgy",
      "Indian Archaeology - A Review"
    ],
    "content": "---\nid: insc-kodumanal-cheran-filigree-goldsmith-guild-charters\ntitle: Kodumanal Chera Goldsmith Guild Charters & Wire-Drawing Lapidary Epigraphs\ntype: inscription\nera: Sangam Classical Era (c. 300 BCE - 100 CE)\nthinai: kurinji (Semi-Arid Gemstone Basin)\nstatus: canonical\n---\n\n# Kodumanal: Chera Goldsmith Guild Charters & Wire-Drawing Lapidary Epigraphs\n\n## 1. Archaeological Context & Site Identity\nKodumanal, situated on the north bank of the Noyyal river in western Tamil Nadu (ancient Kongu Nadu), was the premier industrial manufacturing center of the Sangam Chera kingdom, mentioned as *Kodumanam* in *Pathitrupathu*.\n\n## 2. Inscriptional & Industrial Discoveries\n- **Inscribed Merchant Sherds**: Over 600 Tamil-Brahmi inscribed potsherds identifying gem merchants, carnelian lapidaries, and goldsmiths (*Pon-Kollan*).\n- **Perforated Drawplates**: Hardened stone and bronze drawplates with graduated conical apertures through which annealed gold ingots were drawn into micro-filigree wire.\n- **Composite Jewelry Finds**: Beryl and sapphire gemstones from the Kangeyam mines set into delicate repoussé gold collets adorned with gold granulation balls.\n\n## 3. High-Temperature Furnace Technology\nArchaeologists uncovered specialized multi-tier furnaces lined with crushed quartz and charcoal dust, equipped with forced-draft tuyeres. These furnaces provided sustained, oxidizing, and reducing atmospheres necessary to separate copper, silver, and gold from mixed ore concentrates.\n\n## 4. International Trade Linkages\nKodumanal supplied filigree gold and beryl jewelry to Roman merchants sailing from Muziris on the Malabar coast, proving that interior Tamil craft centers were directly tied into trans-continental luxury supply chains."
  },
  {
    "slug": "concept-micro-granulation-gold-bead-fabrication-and-eutectic-bonding",
    "category": "concepts",
    "file": "concept-micro-granulation-gold-bead-fabrication-and-eutectic-bonding.md",
    "node_type": "concept",
    "name_en": "Micro-Granulation Gold Bead Fabrication, Eutectic Colloidal Soldering & Surface Tension Physics",
    "name_ta": "நுண் பொன்மணி உருட்டல் (கிரானுலேஷன்), கூழ்ம வெல்டிங் மற்றும் பரப்பு இழுவிசை உலோகவியல்",
    "era": "Early Historic Era",
    "year_start": -500,
    "year_end": 300,
    "thinai": "marutham",
    "summary_en": "The high-precision pyrotechnology of ancient Tamil goldsmiths creating microscopic spherical gold spheres (0.3 to 1.0 mm) via molten metal surface tension drops onto carbon beds, and bonding them onto gold substrates using copper salt colloidal mixtures that melt via solidus-liquidus eutectic reactions without destroying sphere geometry.",
    "summary_ta": "கரித்தூள் மீது உருகிய தங்கத் துளிகளை விழவைத்து பரப்பு இழுவிசை மூலம் 0.3-1.0 மி.மீ நுண் உருண்டை பொன்மணிகளை உருவாக்கி, தாமிர உப்புக் கூழ்மம் கொண்டு உருகுநிலை வேதியியல் மூலம் பற்றவைத்த (Eutectic bonding) சங்ககால நுட்பம்.",
    "sources": [
      "Keezhadi Gold Artifacts Metallurgy (IIT-Madras)",
      "Kodumanal Bead Technology",
      "Untracht: Jewelry Concepts and Technology"
    ],
    "content": "---\nid: concept-micro-granulation-gold-bead-fabrication-and-eutectic-bonding\ntitle: Micro-Granulation Gold Bead Fabrication, Eutectic Colloidal Soldering & Surface Tension Physics\ntype: concept\nera: Early Historic Era (c. 500 BCE - 300 CE)\nthinai: marutham (Pyrometallurgical Nanotechnology)\nstatus: canonical\n---\n\n# Micro-Granulation Gold Bead Fabrication, Eutectic Colloidal Soldering & Surface Tension Physics\n\n## 1. The Wonder of Ancient Micro-Granulation\nAmong the most technically demanding pyrotechnologies of antiquity was **granulation**—the art of decorating gold sheet surfaces with thousands of microscopic, perfect spheres of gold (*Pon-mani*) measuring between 0.3 mm and 1.0 mm in diameter, forming geometric chevrons, rosettes, and clusters without flooding or melting the delicate beads.\n\n## 2. Spherical Granule Production Mechanics\n1. **Gold Snipping**: Pure gold wire was cut into exact microscopic lengths using razor-sharp iron shears.\n2. **Charcoal Bed Melting**: Snippings were placed into alternating layers of fine powdered wood charcoal inside a clay crucible.\n3. **Surface Tension Spheroidization**: When heated above 1,064°C, each snipping melted into a liquid droplet. Because liquid gold does not wet carbon, surface tension pulled each droplet into a perfect sphere.\n4. **Graded Sieving**: Upon cooling, the beads were washed and separated through fine woven hair sieves into uniform diameter sizes.\n\n## 3. Eutectic Colloidal Soldering (*Chempon-Inaippu*)\nIf ordinary solder were used, it would flow through capillary action and submerge the tiny spheres into an unsightly blob. Ancient Tamil jewelers avoided this using **eutectic copper reaction soldering**:\n- **Glue & Copper Salt Mix**: Organic glue (tragacanth plant gum or quince seed mucilage) was mixed with copper carbonate (malachite powder) and painted onto the gold substrate.\n- **Granule Placement**: Micro-granules were arranged using fine bone needles into desired patterns, held in place by the tacky gum.\n- **Reducing Flame Heating**: When heated in a reducing charcoal hearth, the organic gum charred, releasing carbon monoxide that reduced copper carbonate into metallic copper.\n- **Eutectic Reaction**: At 890°C—far below the melting point of pure gold (1,064°C)—copper diffused into the gold at the micro-contact points, creating a localized gold-copper alloy that melted instantaneously, fusing the spheres cleanly with invisible joints.\n\n## 4. Preservation & Modern Analysis\nSEM imaging of Keezhadi and Pattanam granulation beads confirms localized copper diffusion at joint necks, proving that early Tamil goldsmiths mastered solidus-liquidus eutectic phase-transition thermodynamics over 2,500 years ago."
  },
  {
    "slug": "concept-royal-filigree-wire-drawing-and-repousse-leafwork",
    "category": "concepts",
    "file": "concept-royal-filigree-wire-drawing-and-repousse-leafwork.md",
    "node_type": "concept",
    "name_en": "Royal Filigree Wire Drawing, Repoussé Sheet Gold Relief & Chasing Mechanics",
    "name_ta": "அரச தங்கக் கம்பி இழுப்பு (பிலிகிரி), புடைப்புத் தகட்டு வேலை (ரிபூசே) மற்றும் செதுக்குக் கலை",
    "era": "Sangam Classical Era",
    "year_start": -300,
    "year_end": 500,
    "thinai": "marutham",
    "summary_en": "Artisanal wire-drawing through hardened bronze and stone perforated drawplates to produce hair-thin gold wires, braided into intricate lace patterns, combined with repoussé hammering from behind thin gold sheets supported by warm tree-pitch beds to create 3D royal emblems.",
    "summary_ta": "துளையிட்ட கடினத் தகடுகள் வழியே இழுக்கப்பட்ட தலைமுடி போன்ற மெல்லிய தங்கக் கம்பிகளை முறுக்கிப் பின்னிய பிலிகிரி கலை, மற்றும் மரப்பிசின் தளம் மீது தங்கத் தகட்டைப் பின்புறமிருந்து அடித்து உருவங்களை எழுப்பிய புடைப்புச் செதுக்கு நுட்பம்.",
    "sources": [
      "Silappadikaram Commentary",
      "TNSDA Archaeological Gold Catalogues",
      "Maryon: Metalwork and Enamelling"
    ],
    "content": "---\nid: concept-royal-filigree-wire-drawing-and-repousse-leafwork\ntitle: Royal Filigree Wire Drawing, Repoussé Sheet Gold Relief & Chasing Mechanics\ntype: concept\nera: Sangam Classical Era (c. 300 BCE - 500 CE)\nthinai: marutham (Gold Plasticity & Metal Forming)\nstatus: canonical\n---\n\n# Royal Filigree Wire Drawing, Repoussé Sheet Gold Relief & Chasing Mechanics\n\n## 1. Extreme Malleability & Ductility of Gold\nBecause gold has the highest ductility of any metal, a single gram can be drawn into a wire over two kilometers long or beaten into a sheet one-tenth of a micron thick. Sangam jewelers (*Pon-thatchar*) exploited these crystal lattice properties to create two pinnacle art forms: **Filigree** (*Thangak-kambi velai*) and **Repoussé** (*Pudaip-punarpu*).\n\n## 2. Filigree Wire-Drawing Technology\n1. **Annealing & Swaging**: Cast gold ingots were swaged into thin square rods on an anvil, periodically heated to dull red heat (*Pudam*) and quenched to relieve work-hardening stress.\n2. **Perforated Drawplates (*Kambi-tholai*)**: The rod's tip was hammered into a taper, lubricated with animal fat or sesame oil, and pulled using iron tongs through successively smaller conical holes in hardened bronze or stone drawplates.\n3. **Twisting & Flattening**: Drawn round wires were twisted together into two-ply cords, then rolled through polished flat rollers to create serrated, light-catching lace ribbons.\n4. **Skeletal Frameworks**: The wires were bent into scrolling tendrils, floral arabesques, and royal peacocks, held inside a thicker perimeter frame wire.\n\n## 3. Repoussé Relief & Pitch-Bed Chasing\nTo create high-relief gold diadems, royal pendants (*Thali*), and armlets:\n- **Pitch Bowl Cushion (*Pisin-kinnam*)**: A shallow iron bowl filled with a warm, yielding compound of tree pitch, brick dust, and beeswax provided supportive backing.\n- **Reverse Embossing (Repoussé)**: A thin gold leaf was pressed onto the cooled pitch bed. The artisan tapped rounded iron punches from the back, pushing the metal out into three-dimensional volumetric curves.\n- **Front Surface Chasing**: The sheet was reversed, and sharp fine-line chasing chisels detailed facial expressions, tiger claws, and floral petals on the front surface.\n\n## 4. Royal Regalia Integration\nThese techniques created lightweight, hollow-form jewelry of monumental visual presence, minimizing precious metal weight while maximizing shimmering light refraction during royal court ceremonies."
  },
  {
    "slug": "concept-urai-kal-touchstone-assaying-and-gold-purity-metrology",
    "category": "concepts",
    "file": "concept-urai-kal-touchstone-assaying-and-gold-purity-metrology.md",
    "node_type": "concept",
    "name_en": "Urai-Kal Touchstone Assaying, Streak Density Metrology & Four Gold Classifications",
    "name_ta": "உரைகல் மதிப்பீடு, உரசுக்கோடு நிற அடர்த்தி மற்றும் நால்வகை பசும்பொன் தூய்மையியல்",
    "era": "Sangam Classical Era",
    "year_start": -400,
    "year_end": 1200,
    "thinai": "marutham",
    "summary_en": "Standardized non-destructive assaying using velvety black jasper touchstones (Urai-kal), rubbing the alloy against the stone to compare streak color and density against standard needle alloys (Uruli-nool), classifying gold into Kilichchirai, Sambunatham, Adakam, and Satharupam.",
    "summary_ta": "கருமையான யஸ்பர் உரைகற்களில் தங்கத்தை உரசி, உரசுக்கோட்டின் நிறம் மற்றும் பளபளப்பை நிலையான பொன் ஊசிகளுடன் ஒப்பிட்டுத் தூய்மையை அளந்த சங்ககாலத் தரக்கட்டுப்பாடு, மற்றும் நால்வகைத் தங்க வகைப்பாடுகள்.",
    "sources": [
      "Silappadikaram Arumpadavurai",
      "Keezhadi Touchstone Artifact Analysis",
      "Arthashastra and Sangam Trade Metrology"
    ],
    "content": "---\nid: concept-urai-kal-touchstone-assaying-and-gold-purity-metrology\ntitle: Urai-Kal Touchstone Assaying, Streak Density Metrology & Four Gold Classifications\ntype: concept\nera: Sangam Classical Era (c. 400 BCE - 1200 CE)\nthinai: marutham (Analytical Metrology & Assay Science)\nstatus: canonical\n---\n\n# Urai-Kal Touchstone Assaying, Streak Density Metrology & Four Gold Classifications\n\n## 1. Non-Destructive Quality Verification\nIn the thriving commercial emporia of ancient Tamilakam, where gold flowed in from Rome, local river panning, and imperial tributes, standardized assaying was essential to prevent debasement and fraudulent alloying. The primary analytical instrument was the **Urai-kal** (touchstone).\n\n## 2. Petrology & Properties of the Touchstone\n- **Material Selection**: Sourced from fine-grained, velvety black siliceous stones, specifically radiolarian chert, lydite, or fine basanite jasper.\n- **Micro-Rough Abrasive Texture**: The stone's surface was ground with fine corundum powder to create a uniform microscopic tooth capable of biting off a microscopic streak of metal without scratching or marring jewelry.\n- **High Visual Contrast**: The jet-black background provided maximum visual contrast against the shimmering gold, silver, and copper streaks.\n\n## 3. The Assaying Procedure\n1. **Drawing the Test Streak**: The mystery alloy was rubbed firmly across the touchstone, leaving an opaque streak of metal particles approximately 2 cm long.\n2. **Comparison with Standard Needles (*Urai-Oosi*)**: Alongside the test streak, the master assayer drew parallel streaks using a set of standardized reference needles with known ratios of gold, copper, and silver.\n3. **Acid Etching & Luster Comparison**: By visually matching the color hue (reddish for copper, whitish for silver, brilliant yellow for high karat) and observing streak dissolution when exposed to mild organic fruit acids (lime juice / sour tamarind extract), the assayer calculated purity to within 1-2% accuracy.\n\n## 4. Botanical Carat Standards (*Kundrimani* & *Manjadi*)\nWeights were standardized against natural botanical seeds possessing near-invariant mass:\n- **Kundrimani** (*Abrus precatorius*): Red seed with black spot, averaging ~105 to 115 milligrams.\n- **Manjadi** (*Adenanthera pavonina*): Uniform scarlet tree seed, exactly equivalent to two Kundrimani seeds (~210 to 230 milligrams).\n- **Kalanju**: Standard gold coin weight unit equivalent to 20 to 24 Manjadi seeds (~4.5 to 5.0 grams)."
  },
  {
    "slug": "concept-die-struck-gold-coin-minting-and-punch-marked-symbolism",
    "category": "concepts",
    "file": "concept-die-struck-gold-coin-minting-and-punch-marked-symbolism.md",
    "node_type": "concept",
    "name_en": "Die-Struck Gold Coin Minting, Anvil Punches & Dynastic Emblem Metallurgy",
    "name_ta": "அச்சுப் பொறித்த தங்க நாணய வார்ப்பு, பட்டடை முத்திரை மற்றும் மூவேந்தர் சின்னங்கள்",
    "era": "Sangam to Imperial Pandya Era",
    "year_start": -200,
    "year_end": 1200,
    "thinai": "marutham",
    "summary_en": "Hot-strike coin minting utilizing engraved bronze and iron dies, striking measured flans of refined gold with heavy sledgehammers on iron anvils, embossing dynastic symbols: Chera Bow, Chola Tiger, and Pandya Double Carp with pristine sharpness.",
    "summary_ta": "எடை குறிப்பிட்ட தங்கக் கட்டிகளை சூடாக்கி, இரும்புப் பட்டடையில் செதுக்கப்பட்ட முத்திரை அச்சுகள் கொண்டு சம்மட்டியால் அடித்து, சேரரின் வில், சோழரின் புலி, பாண்டியரின் இரட்டைக்கயல் சின்னங்களைப் பொறித்த நாணயவியல் நுட்பம்.",
    "sources": [
      "Krishnamurthy: Sangam Coins",
      "Bopearachchi: Early Tamil Coinage",
      "Madurai Pandya Numismatics"
    ],
    "content": "---\nid: concept-die-struck-gold-coin-minting-and-punch-marked-symbolism\ntitle: Die-Struck Gold Coin Minting, Anvil Punches & Dynastic Emblem Metallurgy\ntype: concept\nera: Sangam to Imperial Pandya Era (c. 200 BCE - 1200 CE)\nthinai: marutham (Numismatic Pyrotechnology)\nstatus: canonical\n---\n\n# Die-Struck Gold Coin Minting, Anvil Punches & Dynastic Emblem Metallurgy\n\n## 1. Evolution from Punch-Marked to Die-Struck Coinage\nEarly historic Tamil coinage transitioned from irregular silver and gold punch-marked bars (*Karshapana*) stamped with separate punches into sophisticated circular double-die struck gold coins minted under the authority of the Three Crowned Kings (*Moovendhar*):\n- **Cheras**: Bow-and-arrow dynastic crest.\n- **Cholas**: Roaring tiger seated facing right, often paired with fish and bow emblems.\n- **Pandyas**: Two vertical carps (*Irattai-Kayal*) flanked by royal flywhisks (*Chauri*) and umbrella (*Venkottrak-kudai*).\n\n## 2. Die-Struck Minting Methodology\n1. **Flan Preparation (*Kalanju-thundu*)**:\n   - High-purity gold was melted, poured into cast rods, and sliced into exact weight disks (*Flans*).\n   - Alternatively, droplets of molten gold were dropped onto flat surfaces to form spherical flans, flattened on an anvil.\n2. **Intaglio Die Engraving**:\n   - Master engravers carved negative designs into case-hardened iron or high-tin bronze punch dies (*Achu*).\n   - The anvil die held the obverse emblem, while a handheld upper punch die held the reverse symbol.\n3. **Hot-Strike Plastic Deformation**:\n   - The flan was heated to red-hot plasticity (~600°C) to reduce yield strength.\n   - Positioned between the upper and lower dies, a single heavy blow of an iron hammer forced the plastic gold into the die recesses, imparting sharp, high-relief iconography.\n\n## 3. Metrological Purity & Economic Sovereignty\nSangam and medieval gold coins (such as the Chola *Maduranthaka Madai* and Pandya *Varahan*) carried verified weights and assayed purities, circulating as accepted international currency across the Indian Ocean from Arabia to China."
  },
  {
    "slug": "char-keezhadi-master-goldsmith-pon-kollan",
    "category": "characters",
    "file": "char-keezhadi-master-goldsmith-pon-kollan.md",
    "node_type": "character",
    "name_en": "Master Goldsmith & Micro-Granulation Artisan of Keezhadi (Pon-Kollan)",
    "name_ta": "கீழடி தலைமை பொற்கொல்லன் மற்றும் நுண்மணி சிற்பி (பொன்கொல்லன்)",
    "era": "Early Historic Era",
    "year_start": -500,
    "year_end": -300,
    "thinai": "marutham",
    "summary_en": "Legendary Vaigai valley master goldsmith, master of clay crucible smelting, charcoal blowpipe flame temperature regulation, and eutectic microscopic bead alignment.",
    "summary_ta": "வைகைக் கரைக் கீழடி தொழிற்கூடத்தில் களிமண் மூசைகளில் பொன்னை உருக்கி, ஊதுகுழல் கொண்டு தீச்சுடரைக் கட்டுப்படுத்தி, நுண்ணிய பொன்மணிகளால் அணிகலன் செய்த தலைமைப்பு பொற்கொல்லன்.",
    "sources": [
      "Keezhadi Inscribed Sherds & Crucible Finds",
      "Vaigai Valley Craft History",
      "Tamil-Brahmi Artisan Records"
    ],
    "content": "---\nid: char-keezhadi-master-goldsmith-pon-kollan\ntitle: Master Goldsmith & Micro-Granulation Artisan of Keezhadi (Pon-Kollan)\ntype: character\nera: Early Historic Era (c. 500 - 300 BCE)\nthinai: marutham (Vaigai Metallurgical Workshops)\nstatus: canonical\n---\n\n# Master Goldsmith & Micro-Granulation Artisan of Keezhadi (Pon-Kollan)\n\n## 1. Persona & Social Status\nThe **Pon-Kollan** of Keezhadi embodies the early historic master goldsmith who directed the urban metallurgical quarter along the Vaigai river. Revered for his technological mastery, he held a respected status in the municipal guild council, serving both the early Pandya royal household and wealthy overseas merchants.\n\n## 2. Mastery of Pyrotechnology & Flame Dynamics\n- **Blowpipe Breath Control (*Thuruthi-Vaai*)**: Mastered the delicate art of sustaining oxidizing versus reducing micro-flames through slender bone and copper blowpipes over charcoal braziers.\n- **Crucible Formulation**: Formulated refractory clay crucibles blended with sand and rice husk ash that survived extreme thermal shocks without disintegrating.\n- **Granule Sorting & Alignment**: Using fine animal bristles and copper needles, he arranged thousands of sub-millimeter gold beads into intricate royal ear ornaments (*Kuzhai*) and sacred amulets.\n\n## 3. Historiographical Significance\nHis physical workshop, touchstones, crucibles, and inscribed personal potsherds discovered in archaeological strata authenticate the deep technological sophistication of early Tamil civilization."
  },
  {
    "slug": "char-pattanam-royal-filigree-jeweler-chempon-achari",
    "category": "characters",
    "file": "char-pattanam-royal-filigree-jeweler-chempon-achari.md",
    "node_type": "character",
    "name_en": "Royal Filigree Jeweler & Gem Inlayer of Pattanam (Chempon-Achari)",
    "name_ta": "பட்டணம் சேரர் அரச பொற்கொல்லர் மற்றும் ரத்தின பதிப்பு ஆச்சாரி (செம்பொன் ஆசாரி)",
    "era": "Sangam Classical Era",
    "year_start": -100,
    "year_end": 200,
    "thinai": "marutham",
    "summary_en": "Master goldsmith and royal gem setter at the ancient emporium of Pattanam (Muziris), celebrated for drawing ultrafine gold wires, mounting Mediterranean beryls and carnelian into repoussé gold crowns and pectoral collarettes.",
    "summary_ta": "மேலைக் கடற்கரை பட்டணம் (முசிறி) துறைமுகத்தில் சேர மன்னர்களுக்கும் உரோமானிய வணிகர்களுக்கும் நுண் கம்பிகளாலான தங்க அணிகலன்கள், வைர-வைடூரியப் பதிப்புகளைச் செய்த அரச பொற்கலைஞர்.",
    "sources": [
      "Pattanam Excavation Reports (KCHR)",
      "Chera Court Chronicles",
      "Periplus of the Erythraean Sea"
    ],
    "content": "---\nid: char-pattanam-royal-filigree-jeweler-chempon-achari\ntitle: Royal Filigree Jeweler & Gem Inlayer of Pattanam (Chempon-Achari)\ntype: character\nera: Sangam Classical Era (c. 100 BCE - 200 CE)\nthinai: marutham (Chera Coastal Emporium)\nstatus: canonical\n---\n\n# Royal Filigree Jeweler & Gem Inlayer of Pattanam (Chempon-Achari)\n\n## 1. Cosmopolitan Artisan of Muziris\nOperating within the vibrant maritime trade hub of Pattanam (the ancient port of Muziris on the Periyar delta), the **Chempon-Achari** (Master of Red Gold) served the royal Chera court while catering to wealthy Roman, Nabataean, and Persian traders who brought gold bullion and Roman aurei to exchange for pepper and beryls.\n\n## 2. Technical Specializations\n- **Gem Setting & Collet Fabrication**: Mastered bezel setting (*Mani-kattu*), forming custom gold collars to secure untreated beryl prisms, carnelians, and amethysts without adhesive glues.\n- **Wire Drawing & Braiding**: Drew gold wire down to less than 0.1 mm thickness, braiding it into flexible loop-in-loop chains and hollow mesh filigree beads.\n- **Foreign Metal Assay**: Assayed foreign Roman gold coins on touchstones, testing purity before melting them down into royal regalia or re-minting into Chera punch-marked coinages.\n\n## 3. Cultural Synthesis\nHis work reflects a unique synthesis of indigenous Tamil filigree techniques with Mediterranean ornamental motifs, representing the heights of global craftsmanship in early antiquity."
  },
  {
    "slug": "place-pattanam-ancient-gold-lapidary-haven",
    "category": "places",
    "file": "place-pattanam-ancient-gold-lapidary-haven.md",
    "node_type": "place",
    "name_en": "Pattanam Ancient Gold & Gem Lapidary Haven (Muziris Delta)",
    "name_ta": "பட்டணம் பண்டைய பொற்கொல்லர் மற்றும் மணி பதிப்புத் துறைமுகம் (முசிறிப் படுகை)",
    "era": "Sangam Classical Era",
    "year_start": -300,
    "year_end": 400,
    "thinai": "neithal",
    "summary_en": "Globally renowned ancient Chera port and industrial manufacturing center on the Periyar delta in Kerala, excavated with thousands of micro-granulated gold beads, cameo blanks, crucible glass, and Roman coin hoards.",
    "summary_ta": "பெரியார் கழிமுகப் பகுதியில் அகழாய்வு செய்யப்பட்ட பண்டைய சேரர் பெருந்துறைமுகம்; ஆயிரக்கணக்கான நுண் பொன்மணிகள், பொற்கொல்லர் மூசைகள், ரத்தினக் கற்கள் மற்றும் சர்வதேச வணிகத் தொழிற்கூடங்கள் நிறைந்த தளம்.",
    "sources": [
      "Pattanam Archaeological Excavations (Cherian)",
      "Archaeology of Early Historic South India",
      "National Geographic Muziris Survey"
    ],
    "content": "---\nid: place-pattanam-ancient-gold-lapidary-haven\ntitle: Pattanam Ancient Gold & Gem Lapidary Haven (Muziris Delta)\ntype: place\nera: Sangam Classical Era (c. 300 BCE - 400 CE)\nthinai: neithal (Estuarine Emporium)\nstatus: canonical\n---\n\n# Pattanam Ancient Gold & Gem Lapidary Haven (Muziris Delta)\n\n## 1. Geographical Location & Site Identity\nPattanam is located in the Periyar river delta near Kodungallur in Kerala (coordinates approx. 10.1542° N, 76.2167° E). Widely identified by archaeologists as the core urban and port site of legendary **Muziris** (Muciri of Sangam literature), it served as the western maritime gateway of the Tamil world.\n\n## 2. Archaeological Discoveries & Metallurgical Wealth\nExhaustive excavations by the Kerala Council for Historical Research (KCHR) yielded:\n- **Over 4,000 Micro-Granulation Gold Beads**: Ranging from micro-spheres to multifaceted barrel beads, rosette appliques, and filigree chains.\n- **Roman Gold Coin Hoards**: Hundreds of Roman imperial gold aurei and silver denarii dating from Augustus to Nero.\n- **Lapidary Workshops**: Ingot moulds, jeweller's touchstones, blowpipes, glass mosaic tiles, and thousands of semi-precious stone beads (carnelian, agate, jasper, quartz, and beryl).\n- **Wharf & Canoe Wharf Infrastructure**: A 6-meter-long dugout canoe carved from a single anjili tree trunk, secured with iron nails and bollards.\n\n## 3. Global Industrial Nexus\nPattanam was not merely an exchange transit port, but an enormous manufacturing powerhouse where raw imported gold bullion from the Mediterranean was refined, drawn into wire, granulated, and transformed into high-value ornaments for both local royalty and export back across the Indian Ocean."
  }
]

EDGES = [
  [
    "text-pattinappalai-shipbuilding-and-ocean-navigators-poetry",
    "documents_shipbuilding_culture",
    "concept-trans-oceanic-vangam-and-kalam-hull-framing-mechanics",
    "literature",
    "Sangam Classical Era",
    "Pattinappalai poetry describes towering masts and massive ocean-going hulls (Vangam, Kalam) at Kaveripoompattinam.",
    "Pattinappalai ll. 172-185"
  ],
  [
    "insc-chettiyarpattinam-chola-shipyard-and-drydock-charters",
    "regulates_shipyards_at",
    "place-chettiyarpattinam-ancient-shipyard-haven",
    "epigraphy",
    "Imperial Chola Era",
    "Chola epigraphs record royal shipyard dockyards and timber concessions at Chettiyarpattinam.",
    "South Indian Inscriptions Vol XXIII"
  ],
  [
    "insc-marakkanam-pallava-harbor-and-timber-supply-charters",
    "supplies_timber_for",
    "concept-sewn-plank-masula-boat-architecture-and-coir-stitching",
    "epigraphy",
    "Pallava Classical Era",
    "Marakkanam Pallava charters record forest concessions providing timber for sewn cargo lighters.",
    "Epigraphia Indica Vol VII"
  ],
  [
    "concept-sewn-plank-masula-boat-architecture-and-coir-stitching",
    "utilizes_sealing_by",
    "concept-coconut-coir-lashing-vegetable-pitch-and-dammar-caulking",
    "technology",
    "Sangam Classical Era",
    "Sewn-plank Masula boats utilize triple-twisted coconut coir stitching and dammar pitch caulking.",
    "Traditional Marine Technologies of Tamil Nadu"
  ],
  [
    "concept-trans-oceanic-vangam-and-kalam-hull-framing-mechanics",
    "guided_by_navigation",
    "concept-monsoon-wind-meteorology-and-dual-quarter-rudder-navigation",
    "technology",
    "Sangam to Chola Era",
    "Ocean-going Vangam hulls were steered through monsoon winds using dual quarter-rudders and stellar dead reckoning.",
    "Arunachalam: Traditional Indian Sea-Navigation"
  ],
  [
    "char-chettiyarpattinam-master-shipwright-marakkal-thatchan",
    "operates_shipyard_at",
    "place-chettiyarpattinam-ancient-shipyard-haven",
    "craft",
    "Imperial Chola Era",
    "The master shipwright oversaw hull construction and drydocks at the Chettiyarpattinam haven.",
    "Chettiyarpattinam Coastal Survey"
  ],
  [
    "char-nagapattinam-ocean-navigator-kalam-selvan-nayagan",
    "navigates_vessels_of",
    "concept-trans-oceanic-vangam-and-kalam-hull-framing-mechanics",
    "navigation",
    "Imperial Chola Era",
    "The chief fleet pilot of Nagapattinam commanded oceanic Vangam fleets across the Bay of Bengal.",
    "Leiden Copperplates"
  ],
  [
    "char-chettiyarpattinam-master-shipwright-marakkal-thatchan",
    "applies_lashing_methods",
    "concept-coconut-coir-lashing-vegetable-pitch-and-dammar-caulking",
    "technology",
    "Imperial Chola Era",
    "The master shipwright directed caulking cauldrons and coir stitch tolerances.",
    "Chola Naval Archives"
  ],
  [
    "text-pattinappalai-shipbuilding-and-ocean-navigators-poetry",
    "honors_ocean_navigators",
    "char-nagapattinam-ocean-navigator-kalam-selvan-nayagan",
    "literature",
    "Sangam Classical Era",
    "Sangam odes celebrate the courage and star-reckoning of Tamil deep-sea pilots.",
    "Pattinappalai ll. 29-35"
  ],
  [
    "place-chettiyarpattinam-ancient-shipyard-haven",
    "harbors_elastic_craft",
    "concept-sewn-plank-masula-boat-architecture-and-coir-stitching",
    "geography",
    "Sangam to Chola Era",
    "Chettiyarpattinam tidal docks maintained both heavy Vangams and surf-riding sewn Masula lighters.",
    "ASI Coastal Heritage Records"
  ],
  [
    "text-karikala-chola-kallanai-hydraulic-chronicles-and-sangam-odes",
    "chronicles_dam_engineering",
    "concept-cyclopean-granite-dressing-and-clay-silt-hydraulic-foundations",
    "literature",
    "Sangam Classical Era",
    "Sangam texts celebrate Karikala Chola taming the Kaveri floods through cyclopean stone masonry foundations.",
    "Porunararruppadai ll. 235-248"
  ],
  [
    "insc-thiruvanaikoil-chola-grand-anicut-maintenance-charters",
    "grants_maintenance_near",
    "place-thiruvanaikoil-ancient-hydraulic-haven",
    "epigraphy",
    "Medieval Chola Era",
    "Thiruvanaikoil inscriptions record tax-free land grants for maintaining the Grand Anicut.",
    "South Indian Inscriptions Vol III"
  ],
  [
    "insc-veeranam-parantaka-chola-reservoir-sluice-endowments",
    "records_sluice_engineering",
    "concept-silt-scouring-sluices-and-kumizhi-thumbu-headworks",
    "epigraphy",
    "Imperial Chola Era",
    "Veeranam inscriptions record dressed granite sluice headworks and feeder canals.",
    "South Indian Inscriptions Vol VIII"
  ],
  [
    "concept-cyclopean-granite-dressing-and-clay-silt-hydraulic-foundations",
    "complements_geometry_of",
    "concept-curved-weir-geometry-and-hydraulic-energy-dissipation-aprons",
    "hydraulics",
    "Sangam Classical Era",
    "Sinking boulder foundations provided the structural stability needed for the curved weir geometry.",
    "Memoir on the Grand Anicut (Cotton)"
  ],
  [
    "concept-curved-weir-geometry-and-hydraulic-energy-dissipation-aprons",
    "diverts_into_networks",
    "concept-chola-river-embankment-and-flood-diversion-canal-networks",
    "hydraulics",
    "Sangam Classical Era",
    "The curved weir deflected flood waters into delta diversion canals and embankment channels.",
    "PWD Heritage Water Records"
  ],
  [
    "char-kallanai-master-hydraulic-architect-neerarru-sirpan",
    "designed_foundations_of",
    "concept-cyclopean-granite-dressing-and-clay-silt-hydraulic-foundations",
    "engineering",
    "Sangam Classical Era",
    "The master hydraulic architect engineered the sinking un-mortared granite boulder foundations.",
    "Kallanai Oral Traditions"
  ],
  [
    "char-thiruvanaikoil-master-stone-mason-kal-thatchan",
    "carved_sluices_at",
    "place-thiruvanaikoil-ancient-hydraulic-haven",
    "masonry",
    "Medieval Chola Era",
    "The master mason carved precision-slotted granite sluices and maintained weir aprons from Thiruvanaikoil.",
    "Jambukeswaram Temple Inscriptions"
  ],
  [
    "concept-silt-scouring-sluices-and-kumizhi-thumbu-headworks",
    "preserves_flow_in",
    "concept-chola-river-embankment-and-flood-diversion-canal-networks",
    "hydraulics",
    "Sangam to Chola Era",
    "Kumizhi-thumbu silt-scouring sluices prevented irrigation canals from silting up.",
    "Studies in Ancient Tamil Hydraulics"
  ],
  [
    "char-kallanai-master-hydraulic-architect-neerarru-sirpan",
    "calculated_curve_of",
    "concept-curved-weir-geometry-and-hydraulic-energy-dissipation-aprons",
    "engineering",
    "Sangam Classical Era",
    "The chief architect calculated the serpentine curvature to dissipate Kaveri flood energy.",
    "Chola Irrigation Archives"
  ],
  [
    "place-thiruvanaikoil-ancient-hydraulic-haven",
    "coordinates_maintenance_with",
    "insc-thiruvanaikoil-chola-grand-anicut-maintenance-charters",
    "geography",
    "Medieval Chola Era",
    "Thiruvanaikoil served as the hydraulic headquarters and guild center for the Grand Anicut.",
    "Archaeological Survey of the Kaveri Delta"
  ],
  [
    "text-silappadikaram-gold-bazaar-and-goldsmith-guild-poetry",
    "describes_bazaar_crafts",
    "concept-royal-filigree-wire-drawing-and-repousse-leafwork",
    "literature",
    "Sangam Classical Era",
    "Silappadikaram verses celebrate the gold bazaar of Puhar and master artisans drawing fine gold wire.",
    "Silappadikaram Kadaladukathai ll. 180-210"
  ],
  [
    "insc-keezhadi-early-pandya-gold-assay-and-artisan-charters",
    "attests_micro_metallurgy",
    "concept-micro-granulation-gold-bead-fabrication-and-eutectic-bonding",
    "epigraphy",
    "Early Historic Era",
    "Keezhadi graffiti sherds and crucibles authenticate 6th century BCE micro-granulation gold technology.",
    "Keezhadi Archaeological Excavation Reports"
  ],
  [
    "insc-kodumanal-cheran-filigree-goldsmith-guild-charters",
    "documents_wire_drawing",
    "concept-royal-filigree-wire-drawing-and-repousse-leafwork",
    "epigraphy",
    "Sangam Classical Era",
    "Kodumanal drawplates and inscribed sherds document Chera wire-drawing and filigree goldsmith guilds.",
    "Kodumanal Excavation Reports (Rajan)"
  ],
  [
    "concept-micro-granulation-gold-bead-fabrication-and-eutectic-bonding",
    "quality_controlled_by",
    "concept-urai-kal-touchstone-assaying-and-gold-purity-metrology",
    "metallurgy",
    "Early Historic Era",
    "High-purity gold required for micro-granulation was verified using Urai-kal touchstone streak analysis.",
    "Keezhadi Gold Artifacts Metallurgy"
  ],
  [
    "concept-die-struck-gold-coin-minting-and-punch-marked-symbolism",
    "assayed_via_touchstone",
    "concept-urai-kal-touchstone-assaying-and-gold-purity-metrology",
    "numismatics",
    "Sangam to Imperial Pandya Era",
    "Die-struck gold coins were metrologically verified for fineness using touchstone needle comparison.",
    "Krishnamurthy: Sangam Coins"
  ],
  [
    "char-keezhadi-master-goldsmith-pon-kollan",
    "manufactured_beads_via",
    "concept-micro-granulation-gold-bead-fabrication-and-eutectic-bonding",
    "craft",
    "Early Historic Era",
    "The master goldsmith of Keezhadi practiced eutectic colloidal bonding to create micro-granulation beads.",
    "Keezhadi Crucible & Gold Finds"
  ],
  [
    "char-pattanam-royal-filigree-jeweler-chempon-achari",
    "crafted_jewelry_at",
    "place-pattanam-ancient-gold-lapidary-haven",
    "craft",
    "Sangam Classical Era",
    "The royal filigree jeweler of Muziris crafted gold beryl collarettes at Pattanam.",
    "Pattanam Excavation Reports"
  ],
  [
    "char-pattanam-royal-filigree-jeweler-chempon-achari",
    "expert_in_repousse",
    "concept-royal-filigree-wire-drawing-and-repousse-leafwork",
    "craft",
    "Sangam Classical Era",
    "The royal jeweler combined drawn gold wire filigree with pitch-backed repoussé relief embossing.",
    "Chera Court Chronicles"
  ],
  [
    "text-silappadikaram-gold-bazaar-and-goldsmith-guild-poetry",
    "details_four_classifications",
    "concept-urai-kal-touchstone-assaying-and-gold-purity-metrology",
    "literature",
    "Sangam Classical Era",
    "Silappadikaram commentary records the four classical classifications of gold assayed by touchstone.",
    "Silappadikaram Arumpadavurai"
  ],
  [
    "place-pattanam-ancient-gold-lapidary-haven",
    "excavated_with_micro_granulation",
    "concept-micro-granulation-gold-bead-fabrication-and-eutectic-bonding",
    "archaeology",
    "Sangam Classical Era",
    "Pattanam excavations yielded thousands of micro-granulated gold beads and crucibles.",
    "KCHR Pattanam Artifact Catalogues"
  ]
]

def main():
    print("=" * 70)
    print("🚀 TRIPLE CIVILIZATIONAL EXPANSION HARVESTER - BATCH 17")
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

    print(f"\n🎉 Batch 17 Expansion Complete!")
    print(f"  - 30 Markdown files written to: {MOOLAM_KNOWLEDGE}")
    print(f"  - {nodes_upserted} lore nodes upserted into PostgreSQL")
    print(f"  - {edges_inserted} cross-domain edges linked in PostgreSQL")
    print(f"  - {total_chunks} 1024-dim BGE-M3 vector chunks embedded")

if __name__ == "__main__":
    main()
