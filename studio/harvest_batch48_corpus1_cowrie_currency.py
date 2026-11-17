#!/usr/bin/env python3
"""
Harvester: Batch 48 - Ancient Tamil Cowrie Shell Currency, Fractional Reckoning, Amuletic Regalia & Maldivian-Coromandel Maritime Trade
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
        "slug": "text-kanakku-adhigaram-and-ennadi-chuvadi-on-palagarai-cowrie-fractional-reckoning",
        "category": "text",
        "file": "text-kanakku-adhigaram-and-ennadi-chuvadi-on-palagarai-cowrie-fractional-reckoning.md",
        "name_en": "Kanakku Adhigaram, Ennadi Chuvadi & Inscriptions on Palagarai Cowrie Fractional Reckoning",
        "name_ta": "கணக்கதிகாரம், எண்ணடிச் சுவடி மற்றும் கல்வெட்டுகளில் பலகறை (சோழி) பின்னக் கணக்கியல்",
        "era": "Chola to Nayak Era",
        "year_start": 900,
        "year_end": 1800,
        "thinai": "neithal",
        "summary_en": "Tamil mathematical treatises (Kanakku Adhigaram by Kariya Nayanar and Ennadi Chuvadi palm-leaf primers) and medieval inscriptions documenting cowrie shells (palagarai / sozhi) as both physical micro-currency and tactile counters for base-fraction arithmetic tables (munthiri, kani, ma).",
        "summary_ta": "காரிய நாயனாரின் கணக்கதிகாரம், திண்ணைப் பள்ளிக்கூட எண்ணடிச் சுவடிகள் மற்றும் கல்வெட்டுகளில் சில்லறை நாணயமாகவும் பின்ன எண்களைக் கணக்கிடும் கருவியாகவும் பலகறை (சோழி) பயன்படுத்தப்பட்ட வரலாறு.",
        "sources": [
            "Kanakku Adhigaram",
            "Ennadi Chuvadi",
            "South Indian Inscriptions"
        ],
        "content": "# Kanakku Adhigaram & Ennadi Chuvadi on Palagarai Cowrie Reckoning\n\nIn medieval and early modern Tamil Nadu, the money cowrie (*palagarai* or *sozhi*) bridged everyday bazaar commerce and formal mathematical pedagogy:\n\n**Textual & Pedagogical Attestations:**\n- **Kanakku Adhigaram (Kariya Nayanar)**: This 15th-century Tamil mathematical compendium presents practical merchant word-problems (*palagarai kanakku*) calculating exchange conversions between cowrie shells (*palagarai*), copper coins (*kasu* and *panam*), and gold *pon*, alongside grain and land-tax sub-divisions.\n- **Ennadi Chuvadi & Thinnai School Reckoning**: In traditional Tamil *thinnai* veranda schools, students memorized fractional multiplication tables (*keezhalavu*: *araikkani*, *kani* = 1/80, *munthiri* = 1/320, *keel-munthiri*) by laying out and grouping physical *sozhi* shells on sanded floor boards (*manal-palagai*).\n- **Epigraphic Tax & Bazar Records**: Medieval Tamil inscriptions record petty market cesses (*palagarai-vari*) and fractional temple lamp endowments reckoned down to cowrie equivalents."
    },
    {
        "slug": "concept-monetaria-moneta-nacreous-porcelain-biology-and-munnir-palan-theevu-ballast-trade",
        "category": "concept",
        "file": "concept-monetaria-moneta-nacreous-porcelain-biology-and-munnir-palan-theevu-ballast-trade.md",
        "name_en": "Monetaria moneta Nacreous Shell Biology & Munnir-Palan-Theevu (Maldives) Ballast Trade",
        "name_ta": "மோனெட்டாரியா மொனெட்டா (பலகறை) பீங்கான் ஓட்டு உயிரியலும் முன்னீர்ப் பழந்தீவு (மாலத்தீவு) கப்பல் வணிகமும்",
        "era": "Chola to Colonial Era",
        "year_start": 950,
        "year_end": 1850,
        "thinai": "neithal",
        "summary_en": "Marine biology of the money cowrie (Monetaria moneta) and ring cowrie (Monetaria annulus) and the Indian Ocean bilateral trade circuit exchanging Kaveri delta rice and Coromandel cotton textiles for billions of Maldivian coral-lagoon cowries carried as ship ballast.",
        "summary_ta": "பலகறைச் சோழியின் (Monetaria moneta) உறுதியான பீங்கான் ஓட்டு அமைப்பும், சோழர் காலத்தில் முன்னீர்ப் பழந்தீவு எனப்பட்ட மாலத்தீவுகளிலிருந்து அரிசி மற்றும் பருத்தித் துணிக்கு மாற்றாகக் கப்பல் அடிभारமாகக் (Ballast) கொண்டுவரப்பட்ட கடல் வணிகமும்.",
        "sources": [
            "Thanjavur Rajaraja Chola I Inscriptions",
            "Ibn Battuta Maldivian Cowrie Trade Accounts",
            "Indian Ocean Malacology and Monetary History"
        ],
        "content": "# Monetaria moneta Biology & Munnir-Palan-Theevu Ballast Trade\n\nWhy did a small marine gastropod shell become the most durable fractional currency across the Indian Ocean world for over a millennium?\n\n**Malacological & Maritime Foundations:**\n- **Counterfeit-Proof Porcelain Structure**: The money cowrie (*Monetaria moneta*, formerly *Cypraea moneta*) secretes a tightly involute, cross-lamellar aragonite shell with a glossy, enamel-like nacreous glaze, a thickened polygonal callus margin, and a narrow toothed aperture. It could not be forged by potters or smiths, did not corrode in humid monsoon air, and had virtually uniform unit weight (~1.0–1.5 grams).\n- **Munnir-Palan-Theevu (The Maldives)**: Rajaraja Chola I's naval expedition to the \"Twelve Thousand Ancient Islands of the Sea\" (*Munnir-Palan-Theevu Pannirayiram*) secured the world's premier ecological nursery of *Monetaria moneta* in shallow warm coral-reef lagoons.\n- **Rice-for-Cowrie Ballast Equilibrium**: Because the coral atolls of the Maldives produced no cereal grain or cotton, Coromandel and Bengal dhows sailed southwest laden with parboiled rice, coarse *kora* cloth, and ironware, and returned with holds ballasted by millions of sacked cowrie shells."
    },
    {
        "slug": "concept-palagarai-micro-denomination-market-economics-and-copper-kasu-exchange-ratios",
        "category": "concept",
        "file": "concept-palagarai-micro-denomination-market-economics-and-copper-kasu-exchange-ratios.md",
        "name_en": "Palagarai Micro-Denomination Market Economics & Copper Kasu / Panam Exchange Ratios",
        "name_ta": "பலகறை சில்லறைச் சந்தைப் பொருளாதாரம் மற்றும் செப்புக் காசு, பணம் மாற்று விகிதங்கள்",
        "era": "Chola to Nayak Era",
        "year_start": 900,
        "year_end": 1800,
        "thinai": "marutham",
        "summary_en": "Monetary economics of cowrie shells (palagarai) in South Indian village and urban bazaars: providing high-velocity liquidity below the value of the smallest minted copper coin (kasu) for buying single portions of greens, buttermilk, betel leaves, oil, and river ferry tolls.",
        "summary_ta": "தென்னிந்திய நாளங்காடி மற்றும் கிராமச் சந்தைகளில் செப்புக் காசுக்கும் கீழான மிகச் சிறிய மதிப்புடைய பரிவர்த்தனைகளுக்குப் (கீரை, மோர், வெற்றிலை, படகுக் கூலி) பலகறைச் சோழிகள் வழங்கிய சில்லறைப் பணப்புழக்கப் பொருளாதாரம்.",
        "sources": [
            "Kanakku Adhigaram",
            "South Indian Coinage and Monetary History",
            "Coromandel Port Factory Records"
        ],
        "content": "# Palagarai Micro-Denomination Economics & Kasu Exchange Ratios\n\nIn pre-modern agrarian economies with very low price levels for daily subsistence staples, even the smallest minted copper coin (*kasu* or *duddu*) was too large for single-item retail purchases:\n\n**Monetary Mechanics:**\n- **Sub-Metallic Liquidity**: A single copper *kasu* typically exchanged for **20 to 80 cowrie shells (*palagarai*)** depending on coastal proximity and seasonal dhow arrivals (with 4 *cochins/gandas* of 4 shells = 16, and 5 *gandas* = 20 shells or 1 *ponn/panam* sub-unit).\n- **Daily Bazaar Micro-Transactions**: With two or four *palagarai* shells, a household could purchase a bundle of pot-herbs (*keerai*), a ladle of buttermilk, three betel leaves with an areca nut, a wick's measure of lamp oil, or pay a river coracle (*parisal*) ferry toll.\n- **Self-Regulating Supply**: When copper bullion was scarce, *palagarai* expanded money supply at the base of the pyramid so rural artisans, weavers, and paddy labourers never suffered deflationary coin famine."
    },
    {
        "slug": "technology-atoll-coconut-frond-cowrie-trapping-pit-retting-and-sieve-calibration",
        "category": "technology",
        "file": "technology-atoll-coconut-frond-cowrie-trapping-pit-retting-and-sieve-calibration.md",
        "name_en": "Lagoon Coconut-Frond Cowrie Trapping, Sand-Pit Biological Retting & Sieve Calibration",
        "name_ta": "காயல் தென்னங்கீற்றுச் சோழிப் பிடிப்பு, மணற்குழி பதப்படுத்துதல் மற்றும் சல்லடை தரப் பிரிப்பு",
        "era": "Chola to Early Modern Era",
        "year_start": 900,
        "year_end": 1850,
        "thinai": "neithal",
        "summary_en": "Harvesting and post-harvest processing of money cowries: submerging woven coconut palm fronds in shallow reef lagoons for gastropods to cling to, burying live shells in beach sand pits to decompose soft tissue without dulling the nacreous glaze, freshwater washing, and size grading.",
        "summary_ta": "கடல் காயல்களில் தென்னங்கீற்றுகளை மிதக்கவிட்டுப் பலகறைச் சோழிகளைப் பிடித்து, ஓட்டின் பளபளப்பு குறையாமல் கடற்கரை மணற்குழிகளில் புதைத்துச் சுத்தம் செய்து, சல்லடை மூலம் அளவு பிரிக்கும் தொழில்நுட்பம்.",
        "sources": [
            "Maldivian and Coromandel Maritime Trade Accounts",
            "Ethnography of Indian Ocean Shell Fisheries",
            "Madras Presidency Fisheries Bulletins"
        ],
        "content": "# Lagoon Coconut-Frond Trapping, Sand-Pit Retting & Sieve Grading\n\nTransforming live reef gastropods into gleaming, odourless monetary shells required a controlled biological and mechanical processing sequence:\n\n**Harvesting & Processing Workflow:**\n1. **Coconut-Frond Lagoon Traps**: During spring tides and lunar spawning cycles, island and coastal fishers wove fresh green coconut palm fronds (*thennan-keetru*) lashed to stakes in knee-deep coral lagoons. Hundreds of herbivorous *Monetaria moneta* crawled onto the underside of the fronds to graze on microalgae and were shaken into canoes at low tide.\n2. **Beach Sand-Pit Retting**: Boiling shells in water crazes and dulls their glassy porcelain enamel. Instead, harvesters buried the catch in shallow, sun-warmed pits dug above the high-tide mark lined with palm mats. Over 10–14 days, ants and marine bacteria consumed the internal mollusc tissue completely.\n3. **Surf Washing & Sieve Sorting**: The empty shells were agitated in seawater baskets to flush sand from the toothed aperture, sun-dried on coral flats, and graded through perforated brass or rattan sieves so small, knotted yellow-white *moneta* currency shells were separated from larger, purple-ringed *Monetaria annulus* shells."
    },
    {
        "slug": "technology-cowrie-dorsum-grinding-aperture-piercing-and-cotton-cord-string-bundling",
        "category": "technology",
        "file": "technology-cowrie-dorsum-grinding-aperture-piercing-and-cotton-cord-string-bundling.md",
        "name_en": "Cowrie Dorsum Abrasion, Aperture Chipping & Standardized Cotton-Cord Currency Stringing",
        "name_ta": "பலகறை முதுகுத் தேய்ப்பு, துளையிடல் மற்றும் பருத்திக் கயிற்று நாணயக் கோவைக் கட்டுமானம்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 1950,
        "thinai": "neithal",
        "summary_en": "Craft mechanics of modifying cowrie shells for currency stringing, divination calibration, and textile embroidery: grinding or chipping open the convex dorsal dome on sandstone slabs, polishing the edges on wet stone, and threading shells in standardized strings of 80 or 100.",
        "summary_ta": "பலகறைச் சோழிகளின் குவிந்த முதுகுப் பகுதியைக் கல்லில் உரசித் துளையிட்டு, எண்ணிக்கைக்கு ஏற்பப் பருத்திக் கயிற்றில் நாணயக் கோவைகளாகவும் அணிகலன்களாகவும் கோர்க்கும் தொழில்நுட்பம்.",
        "sources": [
            "South Indian Lapidary and Shell-Craft Traditions",
            "Coromandel Bazaar Shroff Practices",
            "Ethnographic Costume and Harness Craft of Tamil Nadu"
        ],
        "content": "# Cowrie Dorsum Grinding, Chipping & Cotton-Cord String Bundling\n\nBecause a natural cowrie shell has only a narrow, toothed ventral slit, stringing it onto a cord or sewing it flat onto leather or cloth required opening the dorsal dome (*mudugu*):\n\n**Lapidary & Stringing Techniques:**\n1. **Percussive Dorsal Chipping**: For bulk currency strings and animal harnesses, artisans seated the shell ventral-side down in a wooden dimple block and struck the thin apex of the dorsal hump with a light iron chisel tip, punching a clean oval eyelet without shattering the thick callused base.\n2. **Wet Sandstone Flat-Grinding**: For precision *sozhi-prashnam* divination dice and flat garment embroidery, the entire rounded dorsal dome was ground down on a coarse wetted sandstone slab (*saanai-kal*) until the internal columella whorl was exposed and both faces lay parallel, stabilizing the probability of landing \"mouth-up\" (*malli*) vs \"mouth-down\" (*kavizh*).\n3. **Standardized Cord Strings (*Kovai*)**: Pierced shells were threaded onto twisted cotton or palmyra-fibre cords in counted twenties (*ganda* groups) knotted at intervals of 80 or 100 shells for rapid wholesale reckoning without recounting individual shells."
    },
    {
        "slug": "artifact-palagarai-currency-strings-kotta-bags-and-calibrated-divination-sozhi-sets",
        "category": "artifact",
        "file": "artifact-palagarai-currency-strings-kotta-bags-and-calibrated-divination-sozhi-sets.md",
        "name_en": "Palagarai Currency Strings, 12,000-Shell Kotta Sacks & Calibrated Astamangala Sozhi Sets",
        "name_ta": "பலகறை நாணயக் கோவைகள், பன்னீராயிரம் சோழி கொண்ட கொட்டா மூட்டைகள் மற்றும் பிரசன்னச் சோழிகள்",
        "era": "Chola to Modern Era",
        "year_start": 900,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Monetary and ritual cowrie artifacts: knotted cotton strings of 80 or 100 palagarai shells, wholesale woven coconut-leaf baskets (kotta) holding 12,000 shells, four-shell Thaayam board-game dice, and 108-shell consecrated Sozhi-Prashnam divination sets.",
        "summary_ta": "பலகறை சார்ந்த நாணய மற்றும் சடங்குப் பொருட்கள்: 80 அல்லது 100 சோழி கொண்ட கயிற்றுக் கோவைகள், 12,000 சோழிகள் கொண்ட 'கொட்டா' ஓலைப் பொதிகள், தாயக் காய் சோழிகள் மற்றும் 108 பிரசன்னச் சோழிகள்.",
        "sources": [
            "Kanakku Adhigaram",
            "Coromandel Maritime Custom-House Tariffs",
            "Prashna Marga & Tamil Astrological Manuals"
        ],
        "content": "# Palagarai Currency Strings, Kotta Sacks & Divination Sozhi Sets\n\nAcross Coromandel ports, village markets, and astrologers' verandas, cowrie shells were packaged and curated into distinct functional artifacts:\n\n**Monetary, Gaming & Astrological Forms:**\n- **The Wholesale *Kotta* (12,000-Shell Parcel)**: Maritime dhows discharging at Nagore and Nagapattinam packed cowries in braided coconut-frond and coir-mat parcels called *kotta* (or *kotta-pothi*), standardized at **12,000 shells** per bundle (roughly 14–16 kg), which served as the unit of port customs valuation.\n- **Retail Drawstring Pouches (*Surukku-Pai*)**: Market women and ferrymen carried 50 to 200 loose *palagarai* in pleated cloth drawstring pouches alongside copper *kasu*.\n- **Thaayam Gaming Sets (4 or 6 Shells)**: Four matched, dorsally ground *sozhi* shells served as binary probability dice for the ancient cross-and-circle board game *Thaayam*.\n- **Consecrated 108 *Prashna Sozhi***: Astrologers (*Jothidar*) maintained a silk-wrapped pouch of 108 unblemished, size-matched golden *Monetaria moneta* shells purified in turmeric and sandalwood water for casting horary *Ashtamangala Prashnam*."
    },
    {
        "slug": "artifact-sozhi-katti-equine-bovine-amulet-harnesses-and-embroidered-ceremonial-textiles",
        "category": "artifact",
        "file": "artifact-sozhi-katti-equine-bovine-amulet-harnesses-and-embroidered-ceremonial-textiles.md",
        "name_en": "Sozhi-Katti Bull & Horse Evil-Eye Harnesses, Boomathu-Maadu Regalia & Cowrie Embroidery",
        "name_ta": "சோழிக்கட்டி காளை மற்றும் குதிரை திருஷ்டி அணிகள், பூம்பூம் மாட்டு அலங்காரம் மற்றும் சோழித் தையல்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "mullai",
        "summary_en": "Ornamental and apotropaic cowrie regalia in Tamil material culture: leather and red-woollen forehead bands (sozhi-pattai) and neck collars studded with interlocking cowries on Kangayam bulls, temple horses, decorated Boomathu-Maadu oracle cattle, and folk dance costumes.",
        "summary_ta": "கால்நடைகள் மற்றும் நாட்டுப்புறக் கலைகளில் பலகறை அணிகலன்கள்: காங்கேயம் காளைகள், கோயில் குதிரைகள் மற்றும் பூம்பூம் மாடுகளின் நெற்றிப்பட்டம், கழுத்துச் சலங்கைக் கயிறுகளில் கட்டப்படும் திருஷ்டிச் சோழி மாலைகள்.",
        "sources": [
            "Ethnography of South Indian Pastoralists and Nomadic Communities",
            "Temple Vahana and Processional Animal Trappings",
            "Tamil Folk Performing Arts Material Culture"
        ],
        "content": "# Sozhi-Katti Bull/Horse Harnesses & Cowrie-Embroidered Regalia\n\nBeyond currency, the gleaming white porcelain cowrie shell served as a premier apotropaic shield against the envious \"evil eye\" (*kan-drishti*) and as an acoustic-visual ornament on ceremonial animals:\n\n**Pastoral & Ritual Trappings:**\n- **Equine & Bovine Forehead Bands (*Netti-Pattai* & *Sozhi-Malai*)**: Prize draught bullocks (*Kangayam* and *Pulikulam* bulls), Jallikattu bulls, and temple processional horses wear braided red felt and leather bridles densely stitched with double rows of dorsally ground cowries alternating with brass bells (*salangai*) and blue glass beads.\n- **Boomathu-Maadu (Oracle Bull) Caparisons**: Itinerant *Boom-Boom Maattukkarar* fortune-tellers drape their sacred trained bulls in patchwork cotton blankets (*jhool*), horn-tassels, and cowrie-encrusted headstalls that clatter rhythmically when the bull nods its head.\n- **Lambadi / Kuravar & Karagattam Regalia**: Women's ceremonial bodices, mirror-work bags, and *Karagattam* / *Poikkal Kudirai* (dummy-horse) dance headpieces edge every seam with cascading fringes of cowrie shells."
    },
    {
        "slug": "concept-sozhi-prashnam-binary-aperture-divination-and-apotropaic-evil-eye-symbolism",
        "category": "concept",
        "file": "concept-sozhi-prashnam-binary-aperture-divination-and-apotropaic-evil-eye-symbolism.md",
        "name_en": "Sozhi-Prashnam Binary Aperture Combinatorics & Apotropaic Eye-Womb Symbolism",
        "name_ta": "சோழிப் பிரசன்ன இருநிலை நிகழ்தகவுக் கணிதமும் கண் திருஷ்டி காக்கும் குறியீட்டுத் தத்துவமும்",
        "era": "Sangam to Modern Era",
        "year_start": -200,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Mathematical combinatorics and symbolic anthropology of the cowrie shell in Tamil culture: binary outcomes (malli aperture-up vs kavizh dome-up) generating binomial distributions in Sozhi-Prashnam divination and Thaayam, alongside the eye-like ventral slit deflecting drishti.",
        "summary_ta": "சோழி உருட்டலில் மல்லி (வாய் மேல்) மற்றும் கவிழ் (முதுகு மேல்) ஆகிய இருநிலை நிகழ்தகவுக் கணிதத்தின் மூலம் சோழிப் பிரசன்னம் மற்றும் தாயம் கணிக்கும் முறையும், பாதி திறந்த கண் போன்ற அமைப்பு திருஷ்டியைத் தடுக்கும் தத்துவமும்.",
        "sources": [
            "Ashtamangala Prashna Sastra",
            "Tamil Jothida Sozhi Prashna Nool",
            "Symbolic Anthropology of Cowrie Shells in South India"
        ],
        "content": "# Sozhi-Prashnam Binary Combinatorics & Apotropaic Eye Symbolism\n\nThe cowrie shell occupies a unique cognitive intersection in Tamil culture as both a binary random-number generator and a protective anatomical talisman:\n\n**Combinatorial & Symbolic Logic:**\n- **Binary State Geometry (*Malli* vs *Kavizh*)**: A cowrie shell tossed onto a flat mat can settle in only two stable equilibrium states: **Malli** (ventral toothed slit facing upward, counted as `1` or active/open) or **Kavizh** (smooth convex dorsal dome facing upward, counted as `0` or closed).\n- **Prashna Divination Arithmetic**: In *Sozhi-Prashnam*, the astrologer divides 108 shells into three random heaps (*mudhal, idai, kadai*) and casts Remainder Modulo-8 (*Ashtamangala*) or Modulo-12 (*Rasi*) counts, combining binomial probability with planetary house calculations to answer queries on lost property, illness, and voyage safety.\n- **Ocular & Fertility Homology**: Because the serrated ventral aperture resembles a half-closed human eyelid fringed with lashes (and the life-giving womb), wearing a cowrie reflects the hostile gaze of *kan-drishti* back upon the onlooker—often bursting or cracking the shell in place of harming the wearer."
    },
    {
        "slug": "institution-palagarai-vaanigar-money-changers-kasu-kadai-shroffs-and-chola-dhow-brokers",
        "category": "institution",
        "file": "institution-palagarai-vaanigar-money-changers-kasu-kadai-shroffs-and-chola-dhow-brokers.md",
        "name_en": "Palagarai-Vaanigar Cowrie Merchants, Kasu-Kadai Money-Changers & Coromandel Port Brokers",
        "name_ta": "பலகறை வணிகர் குழாம், காசுக்கடை நாணய மாற்றுவோர் மற்றும் சோழ மண்டலத் துறைமுகத் தரகர்கள்",
        "era": "Chola to Colonial Era",
        "year_start": 950,
        "year_end": 1850,
        "thinai": "neithal",
        "summary_en": "Commercial institutions managing the import, valuation, and retail circulation of cowrie currency: Chola-era maritime merchant guilds (Nanadesi / Marakkayar dhow owners) importing Maldivian kotta parcels, and street-corner Kasu-Kadai money-changers converting copper coins into palagarai.",
        "summary_ta": "பலகறை நாணய இறக்குமதி மற்றும் சில்லறைப் பரிமாற்றத்தை நிர்வகித்த வணிக நிறுவனங்கள்: மாலத்தீவிலிருந்து சோழி மூட்டைகளைக் கொண்டுவந்த மரைக்காயர் மற்றும் நானாதேசி கப்பல் வணிகர்கள், காசுக்கடை நாணய மாற்றுவோர்.",
        "sources": [
            "South Indian Inscriptions (Merchant Guilds)",
            "Coromandel Coast Maritime Trade Chronicles",
            "Madras Mint and Bazaar Shroff Reports"
        ],
        "content": "# Palagarai-Vaanigar Merchants, Kasu-Kadai Shroffs & Port Brokers\n\nMaintaining a stable two-tier currency system linking Indian Ocean shell imports with inland temple and village markets depended on specialized financial intermediaries:\n\n**Guild & Market Operations:**\n- **Maritime Dhow Shippers (*Marakkayar* & *Chulia* Merchants)**: Operating out of Nagore, Nagapattinam, Kayalpattinam, and Porto Novo (Parangipettai), Tamil Muslim (*Marakkayar*) and Hindu Chetti shipowners contracted directly with the Maldivian Sultanate's royal treasury to buy whole cargos of *kotta* cowrie parcels in exchange for Tanjore delta rice and woven lungis.\n- **Kasu-Kadai Street Shroffs (*kambattam / sarraf*)**: At the entrance of every daily market (*nalangadi*) and weekly shandy (*sandhai*), a money-changer sat behind a low wooden counting board with heaps of graded *palagarai* shells and stacks of copper *kasu*. Morning shoppers exchanged a copper coin for a counted measure of shells, and evening vegetable vendors redeemed their accumulated shells back into copper or silver coin for a tiny commission (*vattam*)."
    },
    {
        "slug": "place-nagore-ancient-coromandel-cowrie-currency-and-indian-ocean-trade-haven",
        "category": "place",
        "file": "place-nagore-ancient-coromandel-cowrie-currency-and-indian-ocean-trade-haven.md",
        "name_en": "Nagore: Ancient Coromandel Port, Maldivian Cowrie Entrepot & Indian Ocean Trade Haven",
        "name_ta": "நாகூர் - சோழ மண்டலக் கடற்கரைத் துறைமுகம், மாலத்தீவு பலகறை இறக்குமதி மற்றும் கடல் வணிகத் தளம்",
        "era": "Chola to Modern Era",
        "year_start": 950,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Historic Coromandel coastal port at the mouth of the Vettar river just north of Nagapattinam (10.8160° N, 79.8420° E), serving for centuries as a primary maritime entrepot where Tamil dhow fleets exported Kaveri delta rice and imported Maldivian cowrie shells (palagarai), chanks, and aromatics.",
        "summary_ta": "நாகப்பட்டினத்திற்கு வடக்கே வெட்டாறு கடலோடு கலக்கும் இடத்தில் அமைந்துள்ள நாகூர் துறைமுகம் (10.8160° N, 79.8420° E): காவிரி டெல்டா அரிசியை ஏற்றுமதி செய்து மாலத்தீவு பலகறைச் சோழிகள் மற்றும் சங்குகளை இறக்குமதி செய்த வரலாற்றுத் தளம்.",
        "sources": [
            "Thanjavur District Manual (Nagore & Nagapattinam Ports)",
            "Coromandel-Maldives Maritime Trade Records",
            "Nagore Dargah & Chola Coast Historical Geography"
        ],
        "content": "# Nagore: Ancient Coromandel Cowrie Currency & Indian Ocean Trade Haven\n\nPositioned at the estuary of the Vettar distributary of the Kaveri river on the Coromandel Coast (10.8160° N, 79.8420° E), the twin port complex of **Nagore–Nagapattinam** functioned as the maritime gateway of the Chola heartland:\n\n**Maritime & Monetary Heritage:**\n- **The Kaveri Rice–Maldivian Cowrie Axis**: Backed directly by the fertile *marutham* paddy granary of Thanjavur and Tiruvarur, Nagore's river-bar anchorage allowed two- and three-masted *thoni* and *kappal* vessels to load Kaveri rice and Kumbakonam/Nagore check textiles for the southwest monsoon voyage to the Maldives, Aceh, and Ceylon.\n- **Shell Warehousing & Inland Distribution**: Returning ships discharged thousands of *kotta* sacks of *Monetaria moneta* cowries and sacred *Turbinella pyrum* chanks onto Nagore's sandy foreshore, where *Palagarai-Vaanigar* brokers graded and dispatched shell currency inland along the Kaveri river road to temple towns across Tamilakam."
    }
]

EDGES = [
    [
        "text-kanakku-adhigaram-and-ennadi-chuvadi-on-palagarai-cowrie-fractional-reckoning",
        "documents",
        "concept-palagarai-micro-denomination-market-economics-and-copper-kasu-exchange-ratios",
        "material_culture",
        "Chola to Nayak Era",
        "Kanakku Adhigaram and Ennadi Chuvadi codify the arithmetic conversion tables linking palagarai cowrie shells to copper kasu and panam.",
        "Kanakku Adhigaram & Ennadi Chuvadi"
    ],
    [
        "concept-monetaria-moneta-nacreous-porcelain-biology-and-munnir-palan-theevu-ballast-trade",
        "supplies",
        "concept-palagarai-micro-denomination-market-economics-and-copper-kasu-exchange-ratios",
        "material_culture",
        "Chola to Colonial Era",
        "Counterfeit-proof Monetaria moneta shells imported as ship ballast from the Maldives supplied the physical monetary base for Tamil bazaar micro-transactions.",
        "Indian Ocean Monetary History"
    ],
    [
        "technology-atoll-coconut-frond-cowrie-trapping-pit-retting-and-sieve-calibration",
        "harvests",
        "concept-monetaria-moneta-nacreous-porcelain-biology-and-munnir-palan-theevu-ballast-trade",
        "material_culture",
        "Chola to Early Modern Era",
        "Submerged coconut-frond traps and beach sand-pit retting harvested and cleaned Monetaria moneta shells without dulling their porcelain glaze.",
        "Shell Fisheries Ethnography"
    ],
    [
        "technology-atoll-coconut-frond-cowrie-trapping-pit-retting-and-sieve-calibration",
        "feeds",
        "technology-cowrie-dorsum-grinding-aperture-piercing-and-cotton-cord-string-bundling",
        "material_culture",
        "Chola to Early Modern Era",
        "Sieve-calibrated cowrie shells are dorsally chipped or ground on wet sandstone slabs to be threaded onto cotton cords.",
        "South Indian Shell-Craft"
    ],
    [
        "technology-cowrie-dorsum-grinding-aperture-piercing-and-cotton-cord-string-bundling",
        "produces",
        "artifact-palagarai-currency-strings-kotta-bags-and-calibrated-divination-sozhi-sets",
        "material_culture",
        "Chola to Modern Era",
        "Dorsal piercing and sandstone grinding produce standardized 80/100-shell currency strings and flat-balanced Thaayam and Prashnam divination dice.",
        "Bazaar Shroff Practices"
    ],
    [
        "technology-cowrie-dorsum-grinding-aperture-piercing-and-cotton-cord-string-bundling",
        "fashions",
        "artifact-sozhi-katti-equine-bovine-amulet-harnesses-and-embroidered-ceremonial-textiles",
        "material_culture",
        "Sangam to Modern Era",
        "Dorsally opened cowrie shells are stitched onto red felt and leather bridles to create Sozhi-Katti bull and horse harnesses.",
        "Pastoralist Craft Surveys"
    ],
    [
        "concept-sozhi-prashnam-binary-aperture-divination-and-apotropaic-evil-eye-symbolism",
        "governs",
        "artifact-palagarai-currency-strings-kotta-bags-and-calibrated-divination-sozhi-sets",
        "material_culture",
        "Sangam to Modern Era",
        "Binary Malli/Kavizh equilibrium states govern the mathematical casting of 108 consecrated Sozhi-Prashnam shells and 4-shell Thaayam dice.",
        "Ashtamangala Prashna Sastra"
    ],
    [
        "concept-sozhi-prashnam-binary-aperture-divination-and-apotropaic-evil-eye-symbolism",
        "animates",
        "artifact-sozhi-katti-equine-bovine-amulet-harnesses-and-embroidered-ceremonial-textiles",
        "material_culture",
        "Sangam to Modern Era",
        "The eyelid-like ventral aperture of the cowrie shell imbues Sozhi-Katti cattle and equine harnesses with apotropaic power against kan-drishti.",
        "Symbolic Anthropology of South India"
    ],
    [
        "institution-palagarai-vaanigar-money-changers-kasu-kadai-shroffs-and-chola-dhow-brokers",
        "distributes",
        "artifact-palagarai-currency-strings-kotta-bags-and-calibrated-divination-sozhi-sets",
        "material_culture",
        "Chola to Colonial Era",
        "Maritime dhow brokers and street-corner Kasu-Kadai money-changers imported 12,000-shell kotta sacks and retailed counted palagarai strings.",
        "Coromandel Trade Chronicles"
    ],
    [
        "institution-palagarai-vaanigar-money-changers-kasu-kadai-shroffs-and-chola-dhow-brokers",
        "operates_in",
        "place-nagore-ancient-coromandel-cowrie-currency-and-indian-ocean-trade-haven",
        "material_culture",
        "Chola to Modern Era",
        "Marakkayar and Chetti maritime merchants operated out of Nagore port at the Vettar estuary to exchange Kaveri rice for Maldivian cowries.",
        "Thanjavur District Manual"
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
