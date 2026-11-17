#!/usr/bin/env python3
"""
Harvester: Batch 42 - Ancient Tamil Palm-Leaf Mathematics, Katapayadi Decimal Place-Value & Astronomical Ephemerides
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
        "slug": "text-kanakku-adhigaram-and-ennadi-chuvadi-mathematical-treatises",
        "category": "text",
        "file": "text-kanakku-adhigaram-and-ennadi-chuvadi-mathematical-treatises.md",
        "name_en": "Kanakku Adhigaram & Ennadi Chuvadi Palm-Leaf Versified Mathematical Treatises",
        "name_ta": "கணக்கதிகாரம் மற்றும் எண்ணடிச் சுவடி மரபுவழிக் கணித நூல்கள்",
        "era": "Early Medieval to Vijayanagara Era",
        "year_start": 600,
        "year_end": 1500,
        "thinai": "marutham",
        "summary_en": "Canonical classical Tamil mathematical manuals (Kanakku Adhigaram by Kari Nayanar, Ennadi Chuvadi) composed in poetic metrical stanzas, encapsulating rules for decimal arithmetic, land survey geometry, grain volume measurement, and micro-fractions.",
        "summary_ta": "பண்டைய தமிழ்க் கணித நூல்கள்: காரி நாயனாரின் கணக்கதிகாரம் மற்றும் எண்ணடிச் சுவடி ஆகியவற்றில் செய்யுள் வடிவில் விளக்கப்பட்ட எண் கணிதம், நில அளவியல் மற்றும் பின்னக் கணக்கீடுகள்.",
        "sources": [
            "Kanakku Adhigaram (Ed. S. V. Govindan)",
            "Ennadi Chuvadi Palm-Leaf Folios",
            "History of Mathematics in Tamil Nadu"
        ],
        "content": "# Kanakku Adhigaram & Ennadi Chuvadi Treatises\n\nClassical Tamil civilization developed a sophisticated, versified pedagogical mathematical literature:\n\n**Literary Testimonies:**\n- **Kanakku Adhigaram (by Kari Nayanar)**: Features hundreds of mnemonic venba verses formulating complex arithmetic algorithms, geometric area conversions for irregular plots (*vanna-kalam*), currency conversions, and compound interest calculations.\n- **Ennadi Chuvadi**: Primer manuscript taught in village schools (*Thinnai Pallikoodam*), teaching children memorized oral recitation of decimal multiplication tables and microscopic fractions.\n- **Asthadi & Pon-Kanakku**: Specialized manuals used by revenue accountants and goldsmiths to calculate fineness of gold alloyed with copper and silver."
    },
    {
        "slug": "concept-katapayadi-alphanumeric-encryption-and-decimal-place-value",
        "category": "concept",
        "file": "concept-katapayadi-alphanumeric-encryption-and-decimal-place-value.md",
        "name_en": "Katapayadi Alphanumeric Mnemonic Encryption, Base-10 Decimal Place-Value & Micro-Fractions",
        "name_ta": "கடபயாதி எண்சொல் குறியீட்டு முறை, பதின்ம இடமதிப்பு மற்றும் நுண்ணிய பின்னங்கள்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "The foundational mathematical system of ancient Tamil scholars: Katapayadi cipher assigning numerals (0-9) to consonants for encoding astronomical constants in easily memorizable poetic phrases, paired with a complete base-10 positional decimal system and fraction scales down to 1/2,160,000 (keezh-munthiri).",
        "summary_ta": "பண்டைய தமிழரின் எண்முறை: மெய் எழுத்துக்களுக்கு எண்களை ஒதுக்கும் கடபயாதி முறை, 10-அடிமான பதின்ம இடமதிப்பு மற்றும் கீழ் முந்திரி (1/2,160,000) வரையிலான நுண்ணிய பின்ன அளவீடுகள்.",
        "sources": [
            "Indian Journal of History of Science",
            "Ancient Tamil Metrology and Mathematics",
            "Tamil Epigraphical Numerical Symbols"
        ],
        "content": "# Katapayadi Alphanumeric Encryption & Decimal Metrics\n\nAncient Tamil mathematics seamlessly married verbal poetics with rigorous numeric calculation:\n\n**Mathematical Architecture:**\n- **Katapayadi System**: Consonants from *ka*, *ta*, *pa*, *ya* series were mapped to digits 1 through 9, while vowels and zero had designated representations. Astronomical planetary longitudes and sine tables were written as lyrical verses that could be decoded into exact digits read from right to left (*ankanam vamato gatih*).\n- **Positional Decimal System**: Tamil inscriptional epigraphy and palm-leaf manuscripts preserve native numerical characters for 1 to 9, 10, 100, and 1,000, supporting arithmetic calculations without Roman numeral cumbersomeness.\n- **Micro-Fractional Metrology**: Scaled down to infinitesimal magnitudes:\n  $$\\\\text{Munthiri} = \\\\frac{1}{320}, \\\\quad \\\\text{Immi} = \\\\frac{1}{21,760}, \\\\quad \\\\text{Keezh-Munthiri} = \\\\frac{1}{2,160,000}$$\n  Used by royal treasury auditors to weigh atomized gold dust and spice fractions."
    },
    {
        "slug": "technology-panchangam-astronomical-ephemeris-computation-and-shadow-gnomon",
        "category": "technology",
        "file": "technology-panchangam-astronomical-ephemeris-computation-and-shadow-gnomon.md",
        "name_en": "Panchangam Astronomical Ephemeris Computation, Gnomon Shadow Geometry & Tidal Calendars",
        "name_ta": "பஞ்சாங்க வானியல் கணக்கீடு, நிழல் குச்சி (சங்கு-கோல்) வடிவவியல் மற்றும் கடல் அலை நாள்காட்டி",
        "era": "Early Historic to Modern Era",
        "year_start": -300,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "The scientific algorithm of Tamil computational astronomy: solar gnomon (Kanku-Kool) shadow tracking to determine equinoxes and local latitude, computing the five limbs of the Panchangam (tithi, vara, nakshatra, yoga, karana), and lunar-tide cycle predictions for navigation.",
        "summary_ta": "பண்டைய வானியல் கணக்கீட்டு முறை: 12-அங்குல நிழல் குச்சி கொண்டு சூரிய நகர்வு மற்றும் அட்சரேகை அறிதல், பஞ்சாங்கம் கணித்தல் மற்றும் கடல்சார் படகுப் பயண அலை ஏற்ற-இறக்க அட்டவணைகள்.",
        "sources": [
            "Indian Astronomy: A Source Book",
            "Vaan-Nool Manuscript Studies (Saraswathi Mahal)",
            "Journal of Astronomical History and Heritage"
        ],
        "content": "# Panchangam Ephemeris Computation & Gnomon Geometry\n\nPredicting celestial motions and maritime tidal currents required systematic geometric and trigonometric computation:\n\n**Computational Principles:**\n1. **Gnomon Shadow Trigonometry (*Kanku-Kool*)**: A standardized 12-finger (*angula*) vertical staff was erected at noon on a leveled circular platform. Measuring the equinoctial noon shadow length ($s$) gave the exact terrestrial latitude ($\\phi$) via:\n   $$\\\\tan \\\\phi = \\\\frac{s}{12}$$\n2. **Panchangam Elements**: Astrologer-mathematicians calculated five celestial variables: Tithi (lunar phase), Vara (solar day), Nakshatra (lunar mansion), Yoga (angular sum of sun and moon), and Karana (half-tithi).\n3. **Marine Tidal Prediction (*Vava-Kallu*)**: Tide tables coordinated the syzygy alignment of New Moon (*Amavasai*) and Full Moon (*Pournami*) with Gulf of Mannar reef currents to guide sailing and pearl-diving fleets."
    },
    {
        "slug": "artifact-ezhuthani-iron-stylus-palm-leaf-folios-and-astronomical-tables",
        "category": "artifact",
        "file": "artifact-ezhuthani-iron-stylus-palm-leaf-folios-and-astronomical-tables.md",
        "name_en": "Ezhuthani Tempered Iron Stylus, Talipot Palm-Leaf Folios & Mathematical Grids",
        "name_ta": "எழுத்தாணி, பதப்படுத்தப்பட்ட தாளிப்பனை ஏடுகள் மற்றும் கணிதக் கட்ட அட்டவணைகள்",
        "era": "Iron Age to Modern Era",
        "year_start": -600,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Physical tools of the Tamil mathematician and astronomer: needle-sharp tempered steel styli (ezhuthani) with knifepoint scraping edges, cured Borassus and Corypha palm-leaf manuscripts inscribed with intricate numerical multiplication tables, and circular sine matrices.",
        "summary_ta": "பண்டைய தமிழ்க் கணிதவியலாளரின் உபகரணங்கள்: இரும்பு எழுத்தாணிகள், பதப்படுத்தப்பட்ட பனை ஏடுகள், பெருக்கல் வாய்ப்பாட்டு அட்டவணைகள் மற்றும் கோள வடிவ வானியல் வரைபடங்கள்.",
        "sources": [
            "Saraswathi Mahal Library Palm-Leaf Catalog",
            "Government Oriental Manuscripts Library Madras",
            "U.V. Swaminatha Iyer Library Archives"
        ],
        "content": "# Ezhuthani Iron Stylus & Palm-Leaf Mathematical Folios\n\nThe physical manifestation of Tamil mathematical knowledge was etched onto resilient organic media:\n\n**Instrument Characteristics:**\n- **Ezhuthani Typology**: Crafted with a sharp conical steel stylus tip for incising microscopic Tamil numerals without splitting leaf veins, paired with an integral curved blade on the rear end used to slice manuscripts to uniform length.\n- **Folio Preparation**: Ribbons of palmyra (*Borassus*) or talipot (*Corypha*) leaves were boiled in turmeric-infused water, pressed between wooden boards, and sun-cured.\n- **Inking & Preservation**: Incised grooves were highlighted by smearing lampblack mixed with crushed leaf juice of *Eclipta prostrata* (*Karisalanganni*), protecting the leaves from insect boring for centuries."
    },
    {
        "slug": "concept-ancient-tamil-fraction-system-and-land-survey-geometry",
        "category": "concept",
        "file": "concept-ancient-tamil-fraction-system-and-land-survey-geometry.md",
        "name_en": "Ancient Tamil Fractional Metrology, Land Survey Geometry & Agricultural Taxation",
        "name_ta": "பண்டைய தமிழ்ப் பின்னக் கணக்கீடு, நில அளவியல் வடிவவியல் மற்றும் இறை வரி விதிப்பு",
        "era": "Sangam to Chola Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "marutham",
        "summary_en": "The complex land measurement and geometric survey system codified during the Imperial Chola era: standard survey rods (16-span Ulgalanda-Kool), computation of trapezoidal field areas, and proportional tax distribution scaled down to fractions of a square millimeter.",
        "summary_ta": "சோழர் கால நில அளவியல் கணிதம்: 16-சாண் உலகளந்தான் கோல் கொண்டு நிலங்களை முக்கோணங்களாகவும் சரிவகங்களாகவும் பிரித்து பரப்பு காணும் முறை மற்றும் வரி நிர்ணயம்.",
        "sources": [
            "Chola Land Revenue Epigraphy",
            "Brihadeeswara Temple Inscriptions",
            "Studies in South Indian Agrarian History"
        ],
        "content": "# Tamil Fractional Metrology & Land Survey Geometry\n\nUnder Chola administrative standardization, surveying millions of acres of wetland (*nanjai*) required rigorous practical geometry:\n\n**Survey Protocols:**\n- **Standard Measuring Rods**: Royal surveyors utilized certified wooden or brass-tipped rods such as the *Ulgalanda-Kool* (16 spans / ~3.6 meters) to measure cadastral boundaries.\n- **Triangulation of Irregular Fields**: Complex curvilinear riverfront plots were divided into right-angled triangles and trapezoids, calculating area via:\n  $$\\\\text{Area} = \\\\frac{a+b}{2} \\\\times h$$\n- **Tax Precision**: Royal land grants (*Kani*) recorded ownership down to fractions of a *Kani* ($1/320$, $1/64,000$), ensuring tax assessments reflected exact yield without arbitrary rounding."
    },
    {
        "slug": "institution-kanakkappillai-corporation-of-royal-accountants-and-astronomers",
        "category": "institution",
        "file": "institution-kanakkappillai-corporation-of-royal-accountants-and-astronomers.md",
        "name_en": "Kanakkappillai Corporation: Royal Revenue Accountants, Scribes & Village Astronomers",
        "name_ta": "கணக்கப்பிள்ளை சபை: அரச கணக்காயர், ஆவண எழுதுவோர் மற்றும் கிராமக் கணிதவியலாளர் மன்றம்",
        "era": "Sangam to Vijayanagara Era",
        "year_start": -300,
        "year_end": 1600,
        "thinai": "marutham",
        "summary_en": "The corporate body of Tamil hereditary accountants, scribes, and astronomers (Kanakkappillai / Kanakkalar): maintaining the village land registry (Nilam-Kanakku), calculating monsoon water allowances, verifying grain measures, and computing auspicious agricultural calendars.",
        "summary_ta": "கிராம நில ஆவணங்களை நிர்வகித்த கணக்காயர்களின் பெருமன்றம்: நிலப் பதிவேடு மேலாண்மை, பாசன நீர் பங்கீட்டுக் கணக்கு, தானிய வரி சரிபார்ப்பு மற்றும் பஞ்சாங்கக் கணிப்பு.",
        "sources": [
            "South Indian Inscriptions: Village Administration Charters",
            "Uttiramerur Inscriptional Assemblies",
            "Tamil Scribe Guild History"
        ],
        "content": "# Kanakkappillai Corporation: Royal Accountants\n\nVillage autonomy and imperial state taxation in ancient Tamil Nadu were anchored by the hereditary accountant corps:\n\n**Institutional Responsibilities:**\n- **Cadastral Recordkeeping (*Nilam-Kanakku*)**: Recorded every cadastral boundary change, sale deed, and temple tax exemption on palm-leaf bundles stored in royal repositories (*Vari-Pothagam*).\n- **Water Allowance Calculations**: Computed daily sluice discharge rates (*madai-neer*) based on upstream reservoir levels, allocating proportional hours of irrigation to individual farmers.\n- **Agrarian Calendar Promulgation**: Announced the dates of seasonal star asterisms (*Rohini*, *Karthigai*) to trigger collective ploughing and sowing across river deltas."
    },
    {
        "slug": "technology-arithmetic-multiplication-algorithms-and-thinnai-pedagogy",
        "category": "technology",
        "file": "technology-arithmetic-multiplication-algorithms-and-thinnai-pedagogy.md",
        "name_en": "Mental Arithmetic Algorithms, Sand-Tray Script Scribing & Thinnai School Pedagogy",
        "name_ta": "மனக்கணக்கு கணக்கீட்டு உத்திகள், மணல் பலகை எழுத்துப் பயிற்சி மற்றும் திண்ணைப் பள்ளிக் கூடம்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Pedagogical engineering of ancient Tamil mathematics: oral mnemonic chanting of multiplication tables (*En-Chuvadi*), tracing numerals in fine river sand on school verandahs (*Thinnai*), rapid mental arithmetic shortcuts, and abacus-like pebble tallying.",
        "summary_ta": "பாரம்பரிய தமிழ்க் கணிதக் கல்வி முறை: எண் சுவடி மனப்பாடப் பயிற்சி, திண்ணைப் பள்ளிகளில் ஆற்று மணலில் விரலால் எழுதிப் பழகும் முறை மற்றும் மனக்கணக்கு வித்தைகள்.",
        "sources": [
            "History of Indigenous Education in South India",
            "Traditional Tamil Pedagogy Memoirs",
            "Bulletin of the Institute of Traditional Cultures"
        ],
        "content": "# Mental Arithmetic Algorithms & Thinnai Pedagogy\n\nIndigenous Tamil primary education placed numerical mastery on equal footing with linguistic literacy (*Ennum Ezhuthum Kannena Thagum*):\n\n**Instructional Sequence:**\n1. **Sand Tracing (*Manal-Ezhuthu*)**: Young students sat on verandahs of village teachers (*Kanakkalar*) and traced numerals and alphabets into shallow beds of fine quartz river sand using their index fingers.\n2. **Oral Rhythmic Chanting**: Multiplication and fraction tables were chanted rhythmically in unison until memorized irrevocably.\n3. **Cross-Multiplication Mental Shortcuts**: Complex products were resolved mentally using decomposition methods (*Urdhva Tiryagbhyam* principles adapted into Tamil venba rules), computing large commodity transactions without needing paper."
    },
    {
        "slug": "place-vedaranyam-ancient-chola-astronomical-haven",
        "category": "place",
        "file": "place-vedaranyam-ancient-chola-astronomical-haven.md",
        "name_en": "Vedaranyam: Ancient Chola Astronomical Haven, Marine Tide Computation & Coastal Solstice Citadel",
        "name_ta": "வேதாரண்யம் - பண்டைய சோழர் வானியல் ஆய்வுத் தளம், கடல் அலை கணக்கீடு மற்றும் கடலோர அயனச் சோலை",
        "era": "Iron Age to Modern Era",
        "year_start": -400,
        "year_end": 2000,
        "thinai": "neithal",
        "summary_en": "Historic coastal sanctuary on the Palk Strait in Nagapattinam district, famous for its ancient salt swamps, maritime astronomical observation towers, tidal calendar computation, and Chola temple meridian alignments.",
        "summary_ta": "நாகப்பட்டினம் மாவட்டத்தில் பால்க் ஜலசந்தியின் முகத்துவாரத்தில் அமைந்த வரலாற்று சிறப்புமிக்க தளம்: சோழர் கால வானியல் ஆய்வு கூடம், கடல் அலை ஏற்ற இறக்கக் கணிப்பு மற்றும் கோயில் உச்சி சூரிய மையக் கணக்கீட்டு மையம்.",
        "sources": [
            "Nagapattinam District Gazetteer",
            "South Indian Inscriptions: Vedaranyam Temple Epigraphs",
            "Maritime History of Coromandel Coast"
        ],
        "content": "# Vedaranyam: Ancient Chola Astronomical Haven\n\nVedaranyam (Thirumaraikkadu), situated at the apex where the Coromandel coastline curves westward toward Palk Bay, served as a prime astronomical haven:\n\n**Geographical & Scientific Importance:**\n- Its unobstructed horizon over the open Bay of Bengal enabled ancient Tamil astronomers to track horizon rise and set azimuths of the Sun, Moon, and navigational stars with zero topographic distortion.\n- Master mathematicians stationed at the historic Vedaranyeswarar temple computed lunar-tidal schedules that governed salt manufacturing, ship departures across the Bay of Bengal, and equinoctial festivals.\n- Epigraphical records preserve royal grants providing for astrologer-mathematicians (*Kani-Udiyan*) who updated the regional maritime calendar continuously."
    },
    {
        "slug": "concept-solstice-equinox-solar-shadow-tracking-and-meridian-alignments",
        "category": "concept",
        "file": "concept-solstice-equinox-solar-shadow-tracking-and-meridian-alignments.md",
        "name_en": "Solstice-Equinox Solar Tracking, Temple Meridian Alignments & True-North Orientation",
        "name_ta": "அயன-சம இரவு சூரிய நகர்வு கணக்கீடு, கோயில் உச்சிக் கோடு மற்றும் உண்மை வடக்கு நோக்கு முக அமைப்பு",
        "era": "Sangam to Chola Era",
        "year_start": -300,
        "year_end": 1300,
        "thinai": "marutham",
        "summary_en": "Astronomical and geometric alignment techniques used by Tamil temple architects (Sthapathis): establishing true cardinal north via the Indian circle method (matsya-figure intersection of gnomon shadow arcs), and calculating solstitial beam penetration into temple sanctums.",
        "summary_ta": "பண்டைய கட்டடக் கலை வானியல்: வட்ட நிழல் கதிர் முறையில் இரு நிழல் புள்ளிகளை இணைத்து துல்லியமான உண்மை வடக்கு திசையை அறிதல் மற்றும் கருவறைக்குள் சூரிய ஒளி விழும் நாள் கணிப்பு.",
        "sources": [
            "Manasara Vastu Sastra Tamil Recensions",
            "Archaeological Alignment Studies in Chola Temples",
            "Current Science: Archaeoastronomy of Tamil Temples"
        ],
        "content": "# Solstice Tracking & Temple Meridian Alignments\n\nMonumental Tamil temple architecture was grounded in rigorous solar geometry:\n\n**Alignment Methodology:**\n- **The Indian Circle Gnomon Method**: To determine true cardinal axes, a central gnomon was erected on a leveled surface before dawn. A circle was drawn with a radius equal to the gnomon height. As the morning and afternoon shadows touched the circle, two intersection points were marked; a line connecting them established true East-West, and its perpendicular bisector yielded true North-South.\n- **Sanctum Solar Illumination (*Surya Puja*)**: Sanctums in temples like Modikondan and Thanjavur were oriented so that on the exact days of the vernal and autumnal equinoxes, the rising sun's rays penetrated through multiple concentric doorways to illuminate the central icon."
    },
    {
        "slug": "artifact-kanakku-kool-standardized-survey-rods-and-abacus-counting-boards",
        "category": "artifact",
        "file": "artifact-kanakku-kool-standardized-survey-rods-and-abacus-counting-boards.md",
        "name_en": "Kanakku-Kool Calibrated Survey Rods, Brass Gnomons & Pebble Counting Boards",
        "name_ta": "கணக்குக் கோல் அளவீட்டுத் தண்டுகள், பித்தளை நிழல் குச்சிகள் மற்றும் சிப்பி-கூழாங்கல் கணக்குப் பலகைகள்",
        "era": "Iron Age to Modern Era",
        "year_start": -500,
        "year_end": 2000,
        "thinai": "marutham",
        "summary_en": "Material culture of ancient Tamil metrology and reckoning: bronze-banded wooden measuring rods with incised royal hallmarks, cast brass gnomon rods, and wooden counting trays filled with cowrie shells and polished quartz pebbles.",
        "summary_ta": "பண்டைய அளவியல் மற்றும் கணக்கீட்டு சாதனங்கள்: அரச முத்திரை பொறிக்கப்பட்ட மர அளவுகோல்கள், பித்தளை நிழல் கம்பிகள் மற்றும் சோழிகள்-கற்கள் கொண்டு கணக்கிடும் பலகைகள்.",
        "sources": [
            "Government Museum Chennai Metrological Artifacts",
            "Thanjavur Royal Palace Museum Collections",
            "Epigraphia Indica"
        ],
        "content": "# Kanakku-Kool Survey Rods & Pebble Counting Boards\n\nThe tools of the Tamil accountant and surveyor combined precision craftsmanship with portable utility:\n\n**Diagnostic Implements:**\n- **Kanakku-Kool Survey Rods**: Octagonal rods of seasoned teak or ebony, fitted with bronze protective ferrules and incised with calibrated divisions (*viral*, *saan*, *adi*), bearing royal fish or tiger hallmarks to prevent survey tampering.\n- **Cast Brass Gnomon (*Sanku*)**: Turned solid brass cylinders with turned finial points, calibrated to precisely 12 finger-widths.\n- **Pebble Reckoning Boards (*Kuri-Palagai*)**: Shallow compartmented wooden trays where accountants arranged colored pebbles and cowrie shells (*sozhimuttai*) to tally decimal places during revenue audits."
    }
]

EDGES = [
    [
        "text-kanakku-adhigaram-and-ennadi-chuvadi-mathematical-treatises",
        "codifies",
        "concept-katapayadi-alphanumeric-encryption-and-decimal-place-value",
        "material_culture",
        "Early Medieval to Vijayanagara Era",
        "Tamil mathematical treatises set down Katapayadi encryption rules and decimal algorithms in metrical verse.",
        "Kanakku Adhigaram"
    ],
    [
        "concept-katapayadi-alphanumeric-encryption-and-decimal-place-value",
        "underpins",
        "technology-panchangam-astronomical-ephemeris-computation-and-shadow-gnomon",
        "material_culture",
        "Iron Age to Modern Era",
        "Positional decimal place-value and micro-fractions enable exact planetary ephemeris computation.",
        "Indian Astronomy"
    ],
    [
        "technology-panchangam-astronomical-ephemeris-computation-and-shadow-gnomon",
        "inscribes",
        "artifact-ezhuthani-iron-stylus-palm-leaf-folios-and-astronomical-tables",
        "material_culture",
        "Early Historic to Modern Era",
        "Astronomers and astrologers incise computed ephemerides onto cured palm-leaf folios using steel styli.",
        "Saraswathi Mahal Archives"
    ],
    [
        "concept-ancient-tamil-fraction-system-and-land-survey-geometry",
        "guides",
        "institution-kanakkappillai-corporation-of-royal-accountants-and-astronomers",
        "material_culture",
        "Sangam to Chola Era",
        "Cadastral geometric rules and fractional metrology guide village accountants in revenue assessments.",
        "Chola Land Inscriptions"
    ],
    [
        "institution-kanakkappillai-corporation-of-royal-accountants-and-astronomers",
        "teaches",
        "technology-arithmetic-multiplication-algorithms-and-thinnai-pedagogy",
        "material_culture",
        "Sangam to Vijayanagara Era",
        "Accountant lineages operated Thinnai schools to train children in mental arithmetic and sand script writing.",
        "Traditional Tamil Pedagogy"
    ],
    [
        "place-vedaranyam-ancient-chola-astronomical-haven",
        "hosts",
        "technology-panchangam-astronomical-ephemeris-computation-and-shadow-gnomon",
        "material_culture",
        "Iron Age to Modern Era",
        "Vedaranyam coast provided astronomical observation stations for tidal reckoning and solstitial tracking.",
        "Nagapattinam Gazetteer"
    ],
    [
        "concept-solstice-equinox-solar-shadow-tracking-and-meridian-alignments",
        "calibrates",
        "artifact-kanakku-kool-standardized-survey-rods-and-abacus-counting-boards",
        "material_culture",
        "Sangam to Chola Era",
        "Solar shadow tracking with gnomons calibrates standardized measuring rods and temple orientations.",
        "Manasara Vastu"
    ],
    [
        "institution-kanakkappillai-corporation-of-royal-accountants-and-astronomers",
        "wields",
        "artifact-kanakku-kool-standardized-survey-rods-and-abacus-counting-boards",
        "material_culture",
        "Sangam to Vijayanagara Era",
        "Royal accountants used certified survey rods and pebble counting trays for tax audits.",
        "Government Museum Catalog"
    ],
    [
        "technology-arithmetic-multiplication-algorithms-and-thinnai-pedagogy",
        "preserves",
        "text-kanakku-adhigaram-and-ennadi-chuvadi-mathematical-treatises",
        "material_culture",
        "Iron Age to Modern Era",
        "Oral recitation and sand-tracing pedagogy preserved classical mathematical treatises across generations.",
        "Indigenous Education Studies"
    ],
    [
        "text-kanakku-adhigaram-and-ennadi-chuvadi-mathematical-treatises",
        "celebrates",
        "place-vedaranyam-ancient-chola-astronomical-haven",
        "material_culture",
        "Early Medieval to Vijayanagara Era",
        "Treatises cite the coastal meridian of Vedaranyam as a prime reference point for tidal calculations.",
        "Vaan-Nool Manuscripts"
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
