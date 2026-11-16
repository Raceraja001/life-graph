#!/usr/bin/env python3
# Ingestion harvester for Ancient Tamil Copperplate Charters & Royal Seals
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
        "file": "knowledge/texts/text-thirumandiram-copperplate-mystical-diagrams-and-sacred-yantras-verse.md",
        "slug": "text-thirumandiram-copperplate-mystical-diagrams-and-sacred-yantras-verse",
        "category": "text",
        "name_en": "Thirumandiram: Classical Verses on Copperplate Inscriptions & Sacred Yantra Metallurgy",
        "name_ta": "திருமந்திரம் - செப்பேடு பொறிப்பு, எழுத்து முறைமை மற்றும் எந்திர வடிவியல் பாடல்கள்",
        "era": "Post-Sangam to Medieval Era",
        "year_start": 400,
        "year_end": 700,
        "thinai": "marutham",
        "summary_en": "Thirumoolar's Saiva Siddhanta magnum opus describing the esoteric engraving of geometric yantras and sacred syllables upon cold-hammered copper sheets (chembu-th தகடு).",
        "summary_ta": "திருமூலர் அருளிய திருமந்திரத்தில் செம்புத் தகடுகளில் எந்திரங்கள், மூல மந்திரங்களை வரிவடிவாகப் பொறிக்கும் முறைமை மற்றும் உலோக ஆன்மீகப் பொறியியல் விவரிக்கப்படுகிறது.",
        "sources": [
            "Thirumandiram Tantra 4 (Yantra Bhedam)",
            "Saiva Agamic Metal Inscription Rules"
        ],
        "content": "# Thirumandiram: Classical Verses on Copperplate Engraving\n\nThirumandiram composed by the mystic saint Thirumoolar contains profound philosophical and technical references to the metallurgy of copperplate engraving in ancient Tamil culture. In the fourth tantra, dedicated to sacred geometry and yantra science, Thirumoolar details the physical preparation of pure copper plates (chembu-th தகடு) for permanent incising.\n\nThe verses emphasize that copper was selected above other metals for its electro-magnetic conductivity and spiritual receptivity. The plates were cold-hammered to uniform thickness, polished to mirror brilliance with fine sand, and incised with razor-sharp steel chisels (ezhuthani).\n\nThirumoolar's work reflects an era when copperplate literacy was transitioning from purely sacred geometric talismans to imperial legal and territorial charters (sasanam) throughout peninsular India."
    },
    {
        "file": "knowledge/concepts/concept-lost-wax-dynastic-seal-ring-casting-ilanchinai-valayam.md",
        "slug": "concept-lost-wax-dynastic-seal-ring-casting-ilanchinai-valayam",
        "category": "concept",
        "name_en": "Lost-Wax Dynastic Royal Seal-Ring Metallurgy (Ilanchinai-Valayam & Mudhirai)",
        "name_ta": "இலாஞ்சினை வளையம் - சோழ பாண்டிய அரச முத்திரை வார்ப்பு மற்றும் செப்பேட்டு வளையப் பூட்டு",
        "era": "Sangam to Chola Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "marutham",
        "summary_en": "Metallurgy of monumental bronze seal rings (ilanchinai-valayam) cast using lost-wax methods to bind and legally authenticate imperial multi-plate copper grants with dynastic crests.",
        "summary_ta": "சோழ, பாண்டிய அரசர்களின் புலி, கயல் சின்னங்கள் பொறிக்கப்பட்டு, பல செப்பேடுகளை ஒன்றாகக் கோர்த்துப் பூட்டும் வெண்கல அரச முத்திரை வார்ப்பு முறைமை.",
        "sources": [
            "Thiruvalangadu Copperplates Monograph (Archaeological Survey of India)",
            "Epigraphia Indica Vol III"
        ],
        "content": "# Lost-Wax Dynastic Royal Seal-Ring Metallurgy (Ilanchinai-Valayam)\n\nThe pinnacle of imperial epigraphical security in ancient Tamil kingdoms was the massive cast bronze seal-ring (ilanchinai-valayam). Multi-leaf copperplate grants, which could number over thirty heavy plates, were perforated at one margin and strung onto a thick circular copper rod.\n\nTo guarantee that no plates could be inserted or removed fraudulently, the ends of the rod were fused inside a hollow lost-wax bronze seal matrix. The molten bronze was poured into the ceramic mold, forming a massive circular medallic seal up to eight inches in diameter and weighing over ten kilograms.\n\nThe face of the seal displayed the intricate heraldic emblems of the issuing dynasty in high relief: the Chola tiger seated majestically alongside the twin Pandya fish, flanked by the Chera bow, royal parasol, fly-whisks, and the monarch's grand Sanskrit motto in Grantha script."
    },
    {
        "file": "knowledge/concepts/concept-cold-hammered-copper-plate-engraving-with-steel-burins-seppedu.md",
        "slug": "concept-cold-hammered-copper-plate-engraving-with-steel-burins-seppedu",
        "category": "concept",
        "name_en": "Cold-Hammered Copper Plate Engraving with Hardened Steel Burins (Seppedu & Ezhuthu-Koli)",
        "name_ta": "செப்பேடு செதுக்குதல் - எஃகு உளி கொண்டு செப்புத் தகடுகளில் கல்வெட்டெழுத்து பொறிக்கும் கலை",
        "era": "Post-Sangam to Late Medieval Era",
        "year_start": 300,
        "year_end": 1600,
        "thinai": "marutham",
        "summary_en": "Calligraphic metal-engraving technique wherein master scribes used hardened crucible steel gravers (ezhuthu-koli) to incise flowing Vatteluttu and Tamil-Grantha legal scripts into annealed copper leaves.",
        "summary_ta": "பதப்படுத்தப்பட்ட செப்புத் தகடுகளின் மீது தகுந்த எஃகு உளிகளைக் கொண்டு வட்டெழுத்து மற்றும் தமிழ் கிரந்த வரிவடிவங்களை ஆழமாகப் பொறிக்கும் செப்பேட்டுக் கலை நுட்பம்.",
        "sources": [
            "Indian Epigraphy (D.C. Sircar)",
            "Pallava and Chola Copperplate Palaeography"
        ],
        "content": "# Cold-Hammered Copper Plate Engraving (Seppedu)\n\nThe manufacturing of imperial copperplate charters (seppedu) represented a flawless integration of metallurgy and artistic calligraphy. Ingot copper was melted in charcoal retorts and cast into flat ingots, which were then cold-hammered and repeatedly annealed in water to create thin, uniform sheets resistant to brittleness.\n\nThe edges were slightly raised or thickened to protect the engraved lettering from rubbing abrasions when plates were stacked. The royal text was first written upon the polished copper surface with ink or chalk by the court scribe (karanathan).\n\nMaster engravers (sasana-thatchar), utilizing v-shaped gravers forged from ultra-hard wootz steel, incised the characters with astonishing fluidity. The incisions were deep and precise, creating durable legal title deeds that have survived intact underground for over a thousand years."
    },
    {
        "file": "knowledge/concepts/concept-chola-epigraphical-diplomatics-and-poetic-preambles-meykeerthi.md",
        "slug": "concept-chola-epigraphical-diplomatics-and-poetic-preambles-meykeerthi",
        "category": "concept",
        "name_en": "Imperial Epigraphical Diplomatics & Poetic Royal Eulogies (Meykeerthi Architecture)",
        "name_ta": "மெய்க்கீர்த்தி - சோழர் செப்பேடுகளின் வரலாற்றுப் புகழுரை மற்றும் அரச ஆவண முறைமை",
        "era": "Imperial Chola Era",
        "year_start": 985,
        "year_end": 1250,
        "thinai": "marutham",
        "summary_en": "Standardized diplomatic formula of Chola copper charters, beginning with metric royal eulogies (meykeerthi) documenting imperial conquests, followed by cadastral village surveys and witness rosters.",
        "summary_ta": "சோழர் செப்பேடுகளில் அரசரின் வெற்றிகளைப் போற்றும் மரபுசார் மெய்க்கீர்த்தி, நில எல்லைகளின் வரப்பு விவரங்கள் மற்றும் அரசு அதிகாரிகளின் கையொப்ப அமைப்பு முறைமை.",
        "sources": [
            "Rajaraja Chola Meykeerthi Corpus",
            "Studies in South Indian Epigraphy Vol IV"
        ],
        "content": "# Chola Epigraphical Diplomatics & Meykeerthi Architecture\n\nIntroduced by Rajaraja Chola I in 985 CE, the meykeerthi ('true fame') revolutionized Tamil epigraphical record-keeping. Prior to this innovation, royal charters lacked standardized historical preambles.\n\nA classical copperplate charter followed a rigid, legally binding diplomatic architecture:\n1. *Invocatory Verse*: Salutations to Shiva or Vishnu.\n2. *Meykeerthi*: High poetic Tamil verse chronicling the reigning monarch's military triumphs, overseas conquests, and royal titles in chronological order.\n3. *Donative Core*: Precise legal description of the land grant (brahmadeya or devadana), specifying tax exemptions and royal revenue offsets.\n4. *Cadastral Survey*: Boundary demarcation (karai-alavu) describing physical landmarks where royal riding elephants walked the perimeter.\n5. *Signatories*: Attestation signatures of the prime minister, revenue collectors, and master engraver."
    },
    {
        "file": "knowledge/concepts/concept-temple-archival-copperplate-vaults-and-ring-sealing-sasanam.md",
        "slug": "concept-temple-archival-copperplate-vaults-and-ring-sealing-sasanam",
        "category": "concept",
        "name_en": "Temple Archival Copperplate Vaults & Document Repositories (Sasana-Kottam & Pothagam)",
        "name_ta": "சாசனக் கோட்டம் - கோயில் செப்பேட்டு நிலவறை ஆவணக் காப்பகம் மற்றும் ஆவணப் பாதுகாப்பு",
        "era": "Pallava to Vijayanagara Era",
        "year_start": 600,
        "year_end": 1600,
        "thinai": "marutham",
        "summary_en": "Architectural secure vaults within grand temple complexes designed with sandstone lockers and cedar chests to preserve sealed copperplate grants, land registers, and royal edicts.",
        "summary_ta": "பெருங்கோயில்களின் கருங்கல் நிலவறைகளில் செப்பேட்டுப் பட்டயங்கள், நில ஆவணங்களைப் பாதுகாப்பாக வைக்கும் சாசனக் கோட்டக் காப்பக கட்டமைப்பு.",
        "sources": [
            "Thanjavur Brihadisvara Inscriptions",
            "Temple Archives of Tamil Nadu (R. Nagaswamy)"
        ],
        "content": "# Temple Archival Copperplate Vaults (Sasana-Kottam)\n\nBecause copperplate charters represented the ultimate legal deeds to vast tax-exempt agrarian domains, ancient Tamil institutions engineered secure subterranean repositories known as sasana-kottam or pothaga-shala.\n\nBuilt within the inner enclosures of major stone temple complexes, these archive vaults featured thick granite walls and sandstone wall-crypts designed to protect records against fires, looting armies, and monsoonal humidity. Multi-plate charters were stored inside polished sandalwood or cedar boxes lined with raw silk and powdered turmeric to deter burrowing insects.\n\nDuplicate summaries were engraved upon the exterior stone temple baseboards, ensuring that even if the physical plates were sealed away or hidden during foreign invasions, the public legal covenants remained legible to all."
    },
    {
        "file": "knowledge/inscriptions/insc-thiruvidaimaruthur-chola-royal-copperplate-scriptorium-charters.md",
        "slug": "insc-thiruvidaimaruthur-chola-royal-copperplate-scriptorium-charters",
        "category": "inscription",
        "name_en": "Thiruvidaimaruthur Chola Epigraphs on Royal Copperplate Scriptorium & Chancery Grants",
        "name_ta": "திருவிடைமருதூர் சோழர் கல்வெட்டுகள் - அரச செப்பேட்டு எழுத்துக் கூடம் மற்றும் ஆவண சாசனம்",
        "era": "Imperial Chola Era",
        "year_start": 980,
        "year_end": 1120,
        "thinai": "marutham",
        "summary_en": "Granite inscriptions from the Mahalingaswamy temple at Thiruvidaimaruthur recording royal chancery officers who drafted copperplate land endowments and maintained court archives.",
        "summary_ta": "திருவிடைமருதூர் மகாலிங்கசுவாமி கோயிலில் உள்ள கல்வெட்டுகள்; சோழ அரச ஆவணங்களைச் செப்பேடுகளில் செதுக்கும் அரச எழுத்தாளர் மற்றும் ஆவணக் காப்பக அதிகாரிகளைப் பதிவு செய்கின்றன.",
        "sources": [
            "South Indian Inscriptions Vol V",
            "Thiruvidaimaruthur Epigraphical Survey"
        ],
        "content": "# Thiruvidaimaruthur Chola Copperplate Scriptorium Epigraphs\n\nThe sprawling temple complex of Thiruvidaimaruthur in the fertile Kaveri delta functioned as a principal regional hub of the Chola royal chancery (olai-nayagam).\n\nThese epigraphs record imperial decrees issued by Rajendra Chola I and Virarajendra concerning the execution of multi-plate copper grants. The texts specifically name the resident master engraver who was endowed with permanent residential quarters and tax-free lands (thatcha-kaani) to maintain an active scriptorium.\n\nThe inscriptions stipulate that all regional village land sales and temple endowments were required to be verified against the master copperplate seals deposited in the temple's archival treasury before obtaining legal validity."
    },
    {
        "file": "knowledge/inscriptions/insc-thiruvalangadu-imperial-thirty-one-plate-charter-and-seal-epigraphs.md",
        "slug": "insc-thiruvalangadu-imperial-thirty-one-plate-charter-and-seal-epigraphs",
        "category": "inscription",
        "name_en": "Thiruvalangadu Imperial 31-Plate Copperplate Charter & Seal Ring Epigraphs",
        "name_ta": "திருவாலங்காடு செப்பேடுகள் - 31 செப்புத் தகடுகள் கொண்ட சோழர் முத்திரை சாசனக் கல்வெட்டு",
        "era": "Imperial Chola Era",
        "year_start": 1018,
        "year_end": 1025,
        "thinai": "marutham",
        "summary_en": "The world-famous 31-plate copper charter of Rajendra Chola I from Thiruvalangadu, recording 800 verses of Sanskrit and Tamil detailing the grand conquests and royal donations of the Chola dynasty.",
        "summary_ta": "முதலாம் இராசேந்திர சோழனின் 31 செப்புத் தகடுகளைக் கொண்ட பிரம்மாண்ட சாசனம்; சோழர்களின் வம்சாவளி, வெற்றிகள் மற்றும் பழையனூர் கிராம தானத்தை விவரிக்கும் வரலாற்றுப் பொக்கிஷம்.",
        "sources": [
            "South Indian Inscriptions Vol III (Part III)",
            "Thiruvalangadu Plates Monograph"
        ],
        "content": "# Thiruvalangadu 31-Plate Imperial Copper Charter\n\nDiscovered buried in a sealed bronze chest near the Vadaranyeswarar temple at Thiruvalangadu, this monumental charter represents the greatest surviving single copperplate document from the ancient world.\n\nThe charter consists of 31 massive copper plates measuring sixteen inches in width, weighing a staggering 70 kilograms. The plates are held together by a massive circular copper ring locked by a bronze royal seal displaying the seated tiger, twin fish, and Sanskrit royal motto.\n\nThe text begins with an extensive Sanskrit section composed by the court poet Narayana, followed by a monumental Tamil section detailing the circumambulation of village boundaries by royal she-elephants (pidagai-soozh-nadanthu) and granting Palayanur village as a tax-free endowment."
    },
    {
        "file": "knowledge/characters/char-thiruvidaimaruthur-master-copperplate-engraver-sasana-karanathan.md",
        "slug": "char-thiruvidaimaruthur-master-copperplate-engraver-sasana-karanathan",
        "category": "character",
        "name_en": "Thiruvidaimaruthur Master Copperplate Engraver & Calligrapher (Sasana Karanathan)",
        "name_ta": "திருவிடைமருதூர் தலைமைச் செப்பேட்டுச் சிற்பி மற்றும் சாசனக் கணக்கன்",
        "era": "Imperial Chola Era",
        "year_start": 1000,
        "year_end": 1070,
        "thinai": "marutham",
        "summary_en": "Chief court engraver and master calligrapher responsible for transferring imperial royal orders onto mirror-polished copper leaves with razor-sharp steel chisels.",
        "summary_ta": "அரச ஆணைகளைச் செப்புத் தகடுகளில் அழகிய வரிவடிவங்களாகச் செதுக்கி, பிழையறச் சாசனங்களை உருவாக்கிய சோழ அரசவை தலைமைச் சிற்பி.",
        "sources": [
            "Chola Court Officer Registers",
            "Epigraphia Indica Vol IX"
        ],
        "content": "# Thiruvidaimaruthur Master Copperplate Engraver (Sasana Karanathan)\n\nThe Sasana Karanathan held an esteemed station in the imperial administrative machine. Honored with the courtly designation Rajaraja-Perun-Thatchan, he directed a guild of specialized metal artisans, draft-scribes, and seal-casters.\n\nBefore setting steel chisel to copper, he reviewed the raw palm-leaf royal draft (thiru-mandira-olai) signed by the emperor. He supervised the surface smoothing and edge-beading of the copper sheets, ensuring that each plate had uniform margins and line spacing.\n\nWith astonishing patience, he carved thousands of ornate characters in both Tamil-Grantha and classical Tamil scripts, signing his master craftsman lineage at the bottom of the final plate as an eternal legal witness."
    },
    {
        "file": "knowledge/characters/char-tanjore-royal-chancery-seal-keeper-ilanchinai-kaavalan.md",
        "slug": "char-tanjore-royal-chancery-seal-keeper-ilanchinai-kaavalan",
        "category": "character",
        "name_en": "Tanjore Royal Chancery Seal-Keeper & Archive Chancellor (Ilanchinai Kaavalan)",
        "name_ta": "தஞ்சாவூர் சோழ அரச ஆவணக் காப்பாளர் மற்றும் இலாஞ்சினைக் காவலன்",
        "era": "Imperial Chola Era",
        "year_start": 1010,
        "year_end": 1085,
        "thinai": "marutham",
        "summary_en": "High imperial officer entrusted with the sacred custody of the Chola royal dynastic signet ring matrix, responsible for casting wax seal closures on ratified copper charters.",
        "summary_ta": "சோழ அரசரின் புலி முத்திரை அச்சினைத் தன் பாதுகாப்பில் வைத்து, அரச சாசனங்களை முறைப்படி சீலிட்டு உறுதி செய்த தலைமை ஆவண அதிகாரி.",
        "sources": [
            "Brihadisvara Temple Court Charters",
            "Chola Bureaucracy Studies (Y. Subbarayalu)"
        ],
        "content": "# Tanjore Royal Chancery Seal-Keeper (Ilanchinai Kaavalan)\n\nThe Ilanchinai Kaavalan was among the most confidential ministers of the Chola sovereign. Stationed in the imperial chancery at Thanjavur, he maintained exclusive personal custody over the bronze dynastic seal matrices.\n\nNo royal grant or international maritime pact was legally binding until the Ilanchinai Kaavalan verified the signatures of the ministerial council and poured the molten bronze over the ring ends to permanently seal the charter. He kept meticulous catalog registers of every issued plate set in the imperial archives.\n\nHis integrity was paramount; treason or unauthorized seal impressions carried immediate confiscation of ancestral estates and capital punishment under imperial Chola statutes."
    },
    {
        "file": "knowledge/places/place-thiruvidaimaruthur-ancient-chola-copperplate-scriptorium-haven.md",
        "slug": "place-thiruvidaimaruthur-ancient-chola-copperplate-scriptorium-haven",
        "category": "place",
        "name_en": "Thiruvidaimaruthur: Ancient Chola Copperplate Scriptorium & Chancery Haven",
        "name_ta": "திருவிடைமருதூர் - பண்டைய சோழர் செப்பேட்டு எழுத்துக் கூடம் மற்றும் ஆவணக் களரி",
        "era": "Prehistoric to Modern Era",
        "year_start": -300,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Venerable temple city in the Kaveri delta celebrated across imperial Chola history as a preeminent administrative center for royal copperplate charters, scribal academies, and judicial archives.",
        "summary_ta": "காவிரிப் படுகையில் அமைந்துள்ள வரலாற்றுச் சிறப்புமிக்க திருத்தலம்; சோழர் காலத்தில் அரச செப்பேடுகள் உருவாக்கப்பட்டு, காக்கப்பட்ட முதன்மை ஆவணக் காப்பகத் தளம்.",
        "sources": [
            "South Indian Inscriptions Vol XXIII",
            "Kaveri Delta Cultural Geography"
        ],
        "content": "# Thiruvidaimaruthur: Ancient Chola Copperplate Scriptorium Haven\n\nSituated on the fertile alluvium of the Kaveri delta near Kumbakonam, Thiruvidaimaruthur has stood for two millennia as a supreme intellectual, artistic, and administrative capital of Tamilakam. The grand Mahalingaswamy temple at its heart was not only a spiritual sanctuary but the de facto supreme archive of regional governance.\n\nDuring the zenith of the Chola empire under Rajaraja I and Rajendra I, Thiruvidaimaruthur housed an elite corps of epigraphers, Sanskrit scholars, and master metal smiths. The temple walls themselves constitute an open-air stone library of hundreds of inscriptions recording land audits, musical endowments, and judicial rulings.\n\nExcavations and epigraphical recoveries have substantiated that dozens of seminal copperplate charters were drafted, verified, and sealed within its sacred precincts."
    }
]
EDGES = [
    [
        "text-thirumandiram-copperplate-mystical-diagrams-and-sacred-yantras-verse",
        "documents_technique",
        "concept-cold-hammered-copper-plate-engraving-with-steel-burins-seppedu",
        "historical_proof",
        "Post-Sangam to Medieval Era",
        "Thirumandiram provides foundational literary evidence of cold-hammered copperplate engraving techniques.",
        "Thirumandiram Tantra 4"
    ],
    [
        "concept-cold-hammered-copper-plate-engraving-with-steel-burins-seppedu",
        "secured_by",
        "concept-lost-wax-dynastic-seal-ring-casting-ilanchinai-valayam",
        "historical_proof",
        "Sangam to Chola Era",
        "Engraved copperplate charters were bound through perforations by lost-wax cast bronze dynastic seal rings.",
        "Thiruvalangadu Copperplates Monograph"
    ],
    [
        "concept-cold-hammered-copper-plate-engraving-with-steel-burins-seppedu",
        "incorporates_formula",
        "concept-chola-epigraphical-diplomatics-and-poetic-preambles-meykeerthi",
        "historical_proof",
        "Imperial Chola Era",
        "Master engravers opened imperial copperplate charters with the standardized metric meykeerthi eulogies.",
        "Rajaraja Chola Meykeerthi Corpus"
    ],
    [
        "concept-cold-hammered-copper-plate-engraving-with-steel-burins-seppedu",
        "stored_in",
        "concept-temple-archival-copperplate-vaults-and-ring-sealing-sasanam",
        "historical_proof",
        "Pallava to Vijayanagara Era",
        "Completed multi-plate charters were preserved inside underground sandstone crypts within temple complexes.",
        "Temple Archives of Tamil Nadu"
    ],
    [
        "char-thiruvidaimaruthur-master-copperplate-engraver-sasana-karanathan",
        "operates_in",
        "place-thiruvidaimaruthur-ancient-chola-copperplate-scriptorium-haven",
        "historical_proof",
        "Imperial Chola Era",
        "The master engraver supervised the royal copperplate scriptorium and metal workshops at Thiruvidaimaruthur.",
        "South Indian Inscriptions Vol V"
    ],
    [
        "char-thiruvidaimaruthur-master-copperplate-engraver-sasana-karanathan",
        "executes_engraving",
        "concept-cold-hammered-copper-plate-engraving-with-steel-burins-seppedu",
        "historical_proof",
        "Imperial Chola Era",
        "Master engravers incised deep calligraphic characters into annealed copper plates using hardened wootz steel burins.",
        "Indian Epigraphy"
    ],
    [
        "char-tanjore-royal-chancery-seal-keeper-ilanchinai-kaavalan",
        "casts_seal",
        "concept-lost-wax-dynastic-seal-ring-casting-ilanchinai-valayam",
        "historical_proof",
        "Imperial Chola Era",
        "The chancellor poured molten bronze into wax molds to fuse dynastic royal seals over multi-plate charter rings.",
        "Brihadisvara Temple Court Charters"
    ],
    [
        "insc-thiruvidaimaruthur-chola-royal-copperplate-scriptorium-charters",
        "attests_place",
        "place-thiruvidaimaruthur-ancient-chola-copperplate-scriptorium-haven",
        "historical_proof",
        "Imperial Chola Era",
        "Thiruvidaimaruthur temple inscriptions verify the historical existence of royal scriptorium and chancery grants.",
        "South Indian Inscriptions Vol V"
    ],
    [
        "insc-thiruvalangadu-imperial-thirty-one-plate-charter-and-seal-epigraphs",
        "exemplifies_format",
        "concept-lost-wax-dynastic-seal-ring-casting-ilanchinai-valayam",
        "historical_proof",
        "Imperial Chola Era",
        "The 31-plate Thiruvalangadu charter exemplifies the monumental lost-wax bronze seal ring holding 70 kg of copper plates.",
        "South Indian Inscriptions Vol III"
    ],
    [
        "place-thiruvidaimaruthur-ancient-chola-copperplate-scriptorium-haven",
        "maintains_vault",
        "concept-temple-archival-copperplate-vaults-and-ring-sealing-sasanam",
        "historical_proof",
        "Prehistoric to Modern Era",
        "Thiruvidaimaruthur preserved one of the largest subterranean archival vaults for copperplate land covenants.",
        "Kaveri Delta Cultural Geography"
    ]
]

def get_bge_embedding(text: str):
    resp = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
    resp.raise_for_status()
    return resp.json()["embedding"]

def main():
    print("Ingesting Ancient Tamil Copperplate Charters & Royal Seals into Moolam Chronicles & Life Graph...")

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

    print(f"\n🎉 Ancient Tamil Copperplate Charters & Royal Seals Ingestion Complete! ({nodes_upserted} nodes, {edges_inserted} edges, {total_chunks} chunks)")

if __name__ == "__main__":
    main()
